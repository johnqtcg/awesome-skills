#!/usr/bin/env python3
"""Deterministic safety checker for Oracle migration scripts.

Static analyser for the mechanical half of the oracle-migration review: the checks
that can be decided from the SQL text alone. It does not replace the SKILL.md
checklist — it clears the mechanical items so the review can spend its attention on
the judgement calls (data distribution, business impact, window sizing).

Usage:
    lint_migration.py FILE_OR_DIR [...] [--edition EE|SE2|XE|unknown]
                                        [--version 12.1|12.2|19c|21c|23ai|unknown]
                                        [--context-rows N]
                                        [--format text|json]
                                        [--fail-on critical|warning|info|never]

Exit codes:
    0  no findings at or above the fail threshold
    1  findings at or above the fail threshold
    2  usage or I/O error
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import re
import sys
from typing import Iterable

# --------------------------------------------------------------------------------------
# Check registry.
#
# Declared as DATA, not prose. Every entry here must have at least one golden fixture
# that triggers it and one that does not — test_lint_contract.py enforces both
# directions, so this table cannot drift ahead of the implementation.
# --------------------------------------------------------------------------------------

CRITICAL = "critical"
WARNING = "warning"
INFO = "info"

SEVERITY_ORDER = {INFO: 0, WARNING: 1, CRITICAL: 2}

CHECKS: dict[str, dict[str, str]] = {
    "ORA001": {"severity": CRITICAL, "title": "DDL without DDL_LOCK_TIMEOUT in session"},
    "ORA002": {"severity": CRITICAL, "title": "ADD CONSTRAINT without ENABLE NOVALIDATE"},
    "ORA003": {"severity": CRITICAL, "title": "Partition DDL without UPDATE INDEXES"},
    "ORA004": {"severity": WARNING, "title": "Unbounded DML on a large table"},
    "ORA005": {"severity": CRITICAL, "title": "ALTER TABLE MOVE without ONLINE"},
    "ORA006": {"severity": WARNING, "title": "CREATE INDEX without ONLINE"},
    "ORA007": {"severity": CRITICAL, "title": "DROP COLUMN without a pre-DDL data snapshot"},
    "ORA008": {"severity": CRITICAL, "title": "DBA_EXTENTS.data_object_id does not exist"},
    "ORA009": {"severity": CRITICAL, "title": "Two-statement RENAME cutover is not atomic"},
    "ORA010": {"severity": CRITICAL, "title": "FLASHBACK TABLE cannot cross structural DDL"},
    "ORA011": {"severity": CRITICAL, "title": "COPY_TABLE_DEPENDENTS num_errors not checked"},
    "ORA012": {"severity": WARNING, "title": "FINISH_REDEF_TABLE without dml_lock_timeout"},
    "ORA013": {"severity": WARNING, "title": "NOLOGGING written as a hint has no effect"},
    "ORA014": {"severity": INFO, "title": "DBMS_LOCK.SLEEP requires an explicit grant"},
    "ORA015": {"severity": WARNING, "title": "MODIFY column needs empty/rewrite classification"},
    "ORA016": {"severity": CRITICAL, "title": "Uncommitted DML before DDL is silently committed"},
    "ORA017": {"severity": CRITICAL, "title": "TRUNCATE is irreversible and auto-commits"},
    "ORA018": {"severity": WARNING, "title": "RENAME COLUMN breaks deployed application SQL"},
    "ORA019": {"severity": WARNING, "title": "ALTER INDEX REBUILD without ONLINE"},
    "ORA020": {"severity": WARNING, "title": "VALIDATE without a preceding NOVALIDATE"},
    "ORA021": {"severity": INFO, "title": "Bulk DML without DBMS_STATS refresh"},
    "ORA022": {"severity": CRITICAL, "title": "Comment claims atomicity across multiple DDL"},
    "ORA023": {"severity": WARNING, "title": "NOLOGGING load without a recoverability plan"},
    "ORA024": {"severity": WARNING, "title": "DROP TABLE PURGE bypasses the recycle bin"},
    "ORA025": {"severity": INFO, "title": "SET UNUSED is cheaper, not reversible"},
    "ORA026": {"severity": CRITICAL, "title": "DDL_LOCK_TIMEOUT = 0 is NOWAIT, not protection"},
    "ORA027": {"severity": WARNING, "title": "DDL_LOCK_TIMEOUT larger than any sane window"},
    "ORA028": {"severity": CRITICAL, "title": "DDL_LOCK_TIMEOUT value is invalid"},
    "ORA029": {"severity": WARNING, "title": "DDL_LOCK_TIMEOUT value cannot be verified statically"},
    "ORA030": {"severity": WARNING, "title": "Normal restore point is not a recovery guarantee"},
    "ORA031": {"severity": WARNING, "title": "Snapshot completeness cannot be confirmed"},
    "ORA032": {"severity": CRITICAL, "title": "Guaranteed restore point needs Flashback Database (EE)"},
}

# What does a `CREATE TABLE x AS SELECT ... FROM y` actually preserve?
#
# The earlier revision enumerated constructs that RESTRICT the result (WHERE, ROWNUM,
# FETCH FIRST, SAMPLE) and treated everything else as a full copy. That list can never be
# complete — JOIN, UNION, DISTINCT, GROUP BY, CONNECT BY, MODEL, PIVOT and a correlated
# subquery in the projection all change the row set too, and a JOIN slipped straight
# through. Enumerating what can go wrong is unbounded; enumerating what is provably safe
# is not. So: recognise only the simple shapes, and call everything else unverifiable.
_CTAS_RE = re.compile(
    r"CREATE\s+TABLE\s+([\w.\"]+)\s+(?:[\s\S]*?\s)?AS\s+SELECT\s+([\s\S]*?)\bFROM\s+([\w.\"]+)"
    r"([\s\S]*)$",
    re.IGNORECASE,
)
# `WHERE 1=0` gets its own message: it is not a partial backup, it is the interim-table
# skeleton, and reading it as a backup is the specific mistake worth naming.
_EMPTY_PREDICATE_RE = re.compile(
    r"\bWHERE\s+1\s*=\s*0\b|\bWHERE\s+1\s*<>\s*1\b", re.IGNORECASE
)
# A bare comma-separated identifier list — no functions, no expressions, no DISTINCT.
_PLAIN_COLUMN_LIST_RE = re.compile(r"^[\w.\"]+(\s*,\s*[\w.\"]+)*$")
# After `FROM <table>` a *provably* simple statement has nothing left but whitespace, or
# a plain table alias. Requiring an empty tail rejected `FROM orders o`, which is ordinary
# SQL — the alias restricts nothing. The alias must not be a keyword, or `FROM orders
# WHERE ...` would read as "a table aliased WHERE" and sail through.
_SQL_TAIL_KEYWORDS = {
    "WHERE", "JOIN", "INNER", "LEFT", "RIGHT", "FULL", "CROSS", "NATURAL", "ON", "USING",
    "GROUP", "HAVING", "ORDER", "UNION", "MINUS", "INTERSECT", "CONNECT", "START",
    "MODEL", "PIVOT", "UNPIVOT", "SAMPLE", "PARTITION", "SUBPARTITION", "FETCH", "OFFSET",
    "WITH", "AS", "FOR",
}
_TABLE_ALIAS_TAIL_RE = re.compile(r"^\s*([A-Za-z_]\w*)\s*[;)]*\s*$")


def _tail_is_trivial(tail: str) -> bool:
    if re.match(r"^[\s;)]*$", tail):
        return True
    m = _TABLE_ALIAS_TAIL_RE.match(tail)
    return bool(m) and m.group(1).upper() not in _SQL_TAIL_KEYWORDS


class Snapshot:
    """What a CTAS demonstrably preserves about its source table."""

    FULL = "full"                  # every row, every column
    COLUMNS = "columns"            # every row, a known subset of columns
    EMPTY = "empty"                # WHERE 1=0 — the interim-table skeleton
    UNVERIFIABLE = "unverifiable"  # anything a regex cannot prove

    def __init__(self, line: int, projection: str, tail: str) -> None:
        self.line = line
        self.columns: set = set()
        self.kind, self.reason = self._classify(projection.strip(), tail)

    def _classify(self, projection: str, tail: str):
        if _EMPTY_PREDICATE_RE.search(tail):
            return (
                self.EMPTY,
                "copies no rows at all (WHERE 1=0) — this is an interim-table skeleton, "
                "not a backup",
            )
        if not _tail_is_trivial(tail):
            return (
                self.UNVERIFIABLE,
                "is not a plain single-table copy (it has a WHERE, JOIN, set operation or "
                "other clause), so how many rows it preserves cannot be determined from "
                "the text",
            )
        if projection == "*" or projection.endswith(".*"):
            return self.FULL, ""
        if _PLAIN_COLUMN_LIST_RE.match(projection):
            self.columns = {
                c.strip().split(".")[-1].upper().strip('"')
                for c in projection.split(",")
            }
            return self.COLUMNS, "copies only " + ", ".join(sorted(self.columns))
        return (
            self.UNVERIFIABLE,
            "uses an expression, function or DISTINCT in its select list, so what it "
            "preserves cannot be determined from the text",
        )

    def covers_whole_table(self) -> bool:
        return self.kind == self.FULL

    def covers_columns(self, dropped: set) -> bool:
        """Enough to restore every column in `dropped` — the targeted-snapshot pattern.

        Two conditions, and the second is judged against the whole drop set at once. The
        copy must carry every doomed column, *and* retain at least one column that
        survives the drop to key a MERGE on. Checking the key per column instead lets the
        doomed columns vouch for each other: for `DROP (legacy_a, legacy_b)` a copy of
        exactly those two looks fine when testing legacy_a (legacy_b is "another column")
        and fine again when testing legacy_b — while after the drop it is two anonymous
        value lists with nothing to join them back to.
        """
        if self.kind == self.FULL:
            return True
        if self.kind != self.COLUMNS or not dropped:
            return False
        up = {c.upper() for c in dropped}
        return up <= self.columns and bool(self.columns - up)

    def lacks_recovery_key(self, dropped: set) -> bool:
        """Carries the doomed columns but nothing that survives to key a MERGE on."""
        up = {c.upper() for c in dropped}
        return (
            self.kind == self.COLUMNS
            and bool(up)
            and up <= self.columns
            and not (self.columns - up)
        )


# Columns named by a DROP COLUMN / DROP (a, b) clause.
_DROPPED_COLUMNS_RE = re.compile(
    r"\bDROP\s+(?:COLUMN\s+([\w.\"]+)|\(([^)]*)\))", re.IGNORECASE
)


def _dropped_columns(stmt_text: str) -> set:
    out = set()
    for m in _DROPPED_COLUMNS_RE.finditer(stmt_text):
        if m.group(1):
            out.add(m.group(1).upper().strip('"'))
        elif m.group(2):
            out |= {c.strip().upper().strip('"') for c in m.group(2).split(",") if c.strip()}
    return out

# Only a GUARANTEE restore point enforces retention of the flashback logs needed to get
# back to it. A normal restore point is an SCN bookmark: it is bounded by
# DB_FLASHBACK_RETENTION_TARGET, which Oracle documents as "a target, not a guarantee",
# and it ages out of the control file on its own. Treating the two alike turns a
# best-effort bookmark into a claimed rollback.
_GUARANTEED_RESTORE_POINT_RE = re.compile(
    r"CREATE\s+RESTORE\s+POINT\s+[\w.\"$#]+\s+GUARANTEE\s+FLASHBACK\s+DATABASE",
    re.IGNORECASE,
)
_ANY_RESTORE_POINT_RE = re.compile(r"CREATE\s+RESTORE\s+POINT\b", re.IGNORECASE)

# `ALTER SESSION SET DDL_LOCK_TIMEOUT = <n>` — the value is the point of the statement,
# so the check has to read it. Matching only the statement's presence lets `= 0` (which
# *is* NOWAIT, the exact condition ORA001 exists to prevent) score as compliant.
#
# Capture the whole right-hand side, not just digits: `= -1` would otherwise fail to
# match at all and fall through to "unparsed", which an earlier revision treated as
# "set". Classification then happens on the captured text, so an invalid literal is
# distinguishable from a genuinely dynamic one.
_DDL_LOCK_TIMEOUT_RE = re.compile(
    r"ALTER\s+SESSION\s+SET\s+DDL_LOCK_TIMEOUT\s*=\s*([^;\n]+)", re.IGNORECASE
)

# Oracle accepts an integer in [0, 1000000] for DDL_LOCK_TIMEOUT. Anything else makes the
# ALTER SESSION itself fail, which leaves the session on the default of 0 (NOWAIT) — the
# script looks protected and is not.
_DDL_LOCK_TIMEOUT_MAX = 1_000_000

# Genuinely not evaluable from the text: SQL*Plus substitution (&x, &&x) or a bind (:x).
# A bare keyword is NOT in this class — `= NULL` is a literal Oracle rejects, so it
# belongs with the invalid values, not with the unverifiable ones.
_DYNAMIC_VALUE_RE = re.compile(r"[&:]\w+")

# The one bare keyword whose acceptance for this parameter this skill has not verified
# against the reference. Reported as unverifiable rather than asserted either way.
_UNVERIFIED_KEYWORDS = {"DEFAULT"}


class TimeoutValue:
    """Classification of the right-hand side of an ALTER SESSION SET DDL_LOCK_TIMEOUT.

    Three states, because two is not enough. An earlier revision had only
    "parsed as 0" vs "everything else = fine", so `-1`, `3.5`, `'3'` and `&var` all
    scored as protection. `-1` is the worst of those: Oracle rejects the statement, so
    the session keeps the default NOWAIT and the script is *less* protected than if the
    line were absent — while reading as compliant.
    """

    VALID = "valid"        # integer in range, non-zero
    ZERO = "zero"          # integer 0 — legal, but means NOWAIT
    INVALID = "invalid"    # literal Oracle will reject
    DYNAMIC = "dynamic"    # substitution/bind — cannot be judged statically

    def __init__(self, raw: str) -> None:
        self.raw = raw.strip().rstrip(";").strip()
        self.number: int | None = None
        self.kind = self._classify()

    def _classify(self) -> str:
        text = self.raw
        if not text:
            return self.INVALID
        if _DYNAMIC_VALUE_RE.search(text) or text.upper() in _UNVERIFIED_KEYWORDS:
            return self.DYNAMIC
        try:
            n = int(text)
        except ValueError:
            return self.INVALID          # 3.5, '3', NULL, (2+1), empty …
        self.number = n
        if n < 0 or n > _DDL_LOCK_TIMEOUT_MAX:
            return self.INVALID
        return self.ZERO if n == 0 else self.VALID

    @property
    def protects(self) -> bool:
        """Does this value actually give the next DDL a wait window?

        DYNAMIC counts as protecting: it cannot be proven wrong, and treating an
        unresolved substitution variable as a hard failure would be noise. It still
        earns a warning so the reviewer knows the gate was not verified.
        """
        return self.kind in (self.VALID, self.DYNAMIC)

# Oracle's ceiling is 1_000_000 s (~11.5 days). Anything past an hour is longer than any
# real maintenance window, so the session would sit blocked well past the point a human
# would have aborted it.
_DDL_LOCK_TIMEOUT_SANE_MAX = 3600

# Operations whose presence in a file makes FLASHBACK TABLE ... TO SCN/TIMESTAMP
# unusable as the recovery path (Oracle: cannot flash back across structural DDL).
_STRUCTURAL_DDL_RE = re.compile(
    r"\bALTER\s+TABLE\b[\s\S]*?\b("
    r"DROP\s+(COLUMN|UNUSED\s+COLUMNS)|SET\s+UNUSED|MODIFY\b|MOVE\b|"
    r"ADD\s+CONSTRAINT|DROP\s+PARTITION|TRUNCATE\s+PARTITION|SPLIT\s+PARTITION|"
    r"MERGE\s+PARTITIONS?|EXCHANGE\s+PARTITION"
    r")|(\bTRUNCATE\s+TABLE\b)",
    re.IGNORECASE,
)

_PARTITION_DDL_RE = re.compile(
    r"\b(DROP|TRUNCATE|SPLIT|MERGE|EXCHANGE|MOVE)\s+(PARTITION|PARTITIONS|SUBPARTITION)\b",
    re.IGNORECASE,
)

_DML_RE = re.compile(r"^\s*(UPDATE|DELETE\s+FROM|INSERT\s+INTO|MERGE\s+INTO)\b", re.IGNORECASE)

_BOUNDED_DML_RE = re.compile(
    r"\b(ROWID\s+BETWEEN|:start_id|:end_id|ROWNUM\s*<|FETCH\s+FIRST|"
    r"CREATE_CHUNKS_BY_ROWID|DBMS_PARALLEL_EXECUTE)\b",
    re.IGNORECASE,
)

# A DML pinned to a single key value touches one row; batching advice would be noise.
# Restricted to id-shaped columns compared against a literal or bind — `status = 1`
# deliberately does not qualify, because it can still match the whole table.
_SINGLE_KEY_DML_RE = re.compile(
    r"\bWHERE\b[\s\S]*?\b(?:\w+\.)?(?:id|\w+_id)\s*=\s*(?:\d+|:\w+)\b",
    re.IGNORECASE,
)


_ATOMIC_DENIAL_RE = re.compile(
    r"\b(not|isn'?t|never|non[- ]?atomic|two[- ]statement|no[t]?\s+an?\s+atomic)\b",
    re.IGNORECASE,
)


def _target_table(stmt_text: str) -> str | None:
    """Table an ALTER/CREATE INDEX statement acts on, upper-cased."""
    m = re.search(
        r"\bALTER\s+TABLE\s+([\w.\"]+)|\bCREATE\s+(?:UNIQUE\s+)?INDEX\s+[\w.\"]+\s+ON\s+([\w.\"]+)",
        stmt_text,
        re.IGNORECASE,
    )
    if not m:
        return None
    return (m.group(1) or m.group(2)).upper().strip('"')


def _truncate_target(stmt_text: str) -> str | None:
    """Target of a TRUNCATE TABLE statement (not an ALTER, so _target_table misses it)."""
    m = re.search(r'\bTRUNCATE\s+TABLE\s+([\w."]+)', stmt_text, re.IGNORECASE)
    return m.group(1).upper().strip('"') if m else None


def _has_reverse_rename(sql: str, pairs: list) -> bool:
    """True when the script shows how to undo its first rename.

    Searches the raw text, not just executable statements: the recovery line is
    conventionally left commented out, ready to paste, and that still counts as
    having planned for the failure.
    """
    if not pairs:
        return False
    original, renamed_to = pairs[0]
    pattern = re.compile(
        r"\bALTER\s+TABLE\s+{}\s+RENAME\s+TO\s+{}\b".format(
            re.escape(renamed_to), re.escape(original)
        ),
        re.IGNORECASE,
    )
    return bool(pattern.search(sql))


@dataclasses.dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    title: str
    detail: str
    file: str
    line: int

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class Statement:
    text: str          # comments blanked, original offsets preserved
    raw: str           # verbatim, comments intact
    line: int          # 1-based line of the statement's first character


# SKILL.md §8 requires the NOVALIDATE two-step on tables above this size. The checker
# uses the same number so a static finding cannot contradict the scorecard it feeds.
CONSTRAINT_TWO_STEP_ROW_THRESHOLD = 100_000


@dataclasses.dataclass(frozen=True)
class Context:
    edition: str = "unknown"
    version: str = "unknown"
    rows: int | None = None
    # "yes" | "no" | "unknown". Whether the target carries global indexes cannot be
    # derived from the SQL, and it decides whether omitting UPDATE INDEXES is an outage
    # or a no-op. Default "unknown" keeps the conservative verdict.
    global_indexes: str = "unknown"

    @property
    def online_ddl_available(self) -> bool:
        """ONLINE index/table DDL and DBMS_REDEFINITION are Enterprise Edition only."""
        return self.edition.upper() in {"EE", "ENTERPRISE", "UNKNOWN"}

    @property
    def large_table(self) -> bool:
        return self.rows is not None and self.rows >= 1_000_000

    @property
    def small_enough_to_validate_inline(self) -> bool:
        """Known to be below the scorecard's two-step threshold."""
        return self.rows is not None and self.rows < CONSTRAINT_TWO_STEP_ROW_THRESHOLD


# --------------------------------------------------------------------------------------
# Lexing
# --------------------------------------------------------------------------------------


def blank_comments_and_literals(sql: str) -> str:
    """Blank out comments and string literals, preserving every character offset.

    Replaced characters become spaces (newlines kept) so that line numbers, adjacency
    and word boundaries in the result match the original exactly. Deleting the spans
    instead would fuse neighbouring tokens and manufacture false matches.
    """
    out = list(sql)
    i, n = 0, len(sql)
    while i < n:
        two = sql[i : i + 2]
        if two == "--":
            j = sql.find("\n", i)
            j = n if j == -1 else j
            for k in range(i, j):
                out[k] = " "
            i = j
        elif two == "/*":
            j = sql.find("*/", i + 2)
            j = n if j == -1 else j + 2
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
        elif sql[i] == "'":
            j = i + 1
            while j < n:
                if sql[j] == "'":
                    if j + 1 < n and sql[j + 1] == "'":
                        j += 2
                        continue
                    j += 1
                    break
                j += 1
            for k in range(i, min(j, n)):
                if out[k] != "\n":
                    out[k] = " "
            i = j
        else:
            i += 1
    return "".join(out)


_PLSQL_START_RE = re.compile(
    r"^\s*(DECLARE\b|BEGIN\b|CREATE\s+(OR\s+REPLACE\s+)?"
    r"(PROCEDURE|FUNCTION|PACKAGE|TRIGGER|TYPE)\b)",
    re.IGNORECASE,
)


def split_statements(sql: str) -> list[Statement]:
    """Split into statements on `;`, treating a PL/SQL block as one unit.

    Splitting is driven by the comment-blanked text so a `;` inside a comment or a
    string literal cannot terminate a statement, but each Statement also keeps the
    verbatim slice — comment-content checks need it.

    A PL/SQL block (`DECLARE`/`BEGIN`/`CREATE PROCEDURE` …) contains internal
    semicolons that do *not* end a statement; only a lone `/` on its own line does.
    Splitting such a block on `;` tears the call away from the code that checks its
    result, which makes every intra-block guard invisible — e.g. the
    `IF num_errors > 0 THEN RAISE_APPLICATION_ERROR` that ORA011 looks for.
    """
    blanked = blank_comments_and_literals(sql)
    statements: list[Statement] = []
    start = 0
    i, n = 0, len(blanked)

    def _lead(txt: str) -> int:
        return len(txt) - len(txt.lstrip())

    def flush(end: int) -> None:
        raw = sql[start:end]
        txt = blanked[start:end]
        if txt.strip():
            statements.append(
                Statement(text=txt, raw=raw, line=sql.count("\n", 0, start + _lead(txt)) + 1)
            )

    while i < n:
        # At the head of a statement, decide whether this is a PL/SQL block.
        if i == start or (start <= i and not blanked[start:i].strip()):
            if _PLSQL_START_RE.match(blanked[i:]):
                end = _find_block_end(blanked, i)
                flush(end)
                start = i = end + 1
                continue

        ch = blanked[i]
        if ch == ";":
            flush(i)
            start = i + 1
        elif ch == "/" and _is_lone_slash(blanked, i):
            flush(i)
            start = i + 1
        i += 1
    flush(n)
    return statements


def _find_block_end(blanked: str, start: int) -> int:
    """Index of the lone `/` terminating a PL/SQL block, else end of input."""
    j = start
    n = len(blanked)
    while j < n:
        if blanked[j] == "/" and _is_lone_slash(blanked, j):
            return j
        j += 1
    return n


def _is_lone_slash(text: str, idx: int) -> bool:
    """True when `/` is alone on its line — PL/SQL block terminator, not division."""
    line_start = text.rfind("\n", 0, idx) + 1
    line_end = text.find("\n", idx)
    line_end = len(text) if line_end == -1 else line_end
    return text[line_start:line_end].strip() == "/"


def is_ddl(stmt_text: str) -> bool:
    """DDL that contends for a lock on an *existing* object.

    `CREATE TABLE` is deliberately excluded: it introduces a new object, so no other
    session can hold a lock on it and ORA-00054 is not reachable. Flagging it for a
    missing DDL_LOCK_TIMEOUT is a false positive, and false positives on the
    interim-table step of a DBMS_REDEFINITION plan are exactly the noise that trains
    reviewers to ignore the checker.
    """
    return bool(
        re.match(
            r"^\s*(ALTER\s+TABLE|ALTER\s+INDEX|CREATE\s+(UNIQUE\s+)?INDEX|"
            r"DROP\s+TABLE|DROP\s+INDEX|TRUNCATE\s+TABLE|COMMENT\s+ON|RENAME\b)",
            stmt_text,
            re.IGNORECASE,
        )
    )


# A Flyway/Liquibase-style version header, or an explicit "next release" marker, means
# the statements after it run in a DIFFERENT session. ALTER SESSION settings do not
# survive that boundary, so session state must be reset — otherwise a DDL_LOCK_TIMEOUT
# set in phase 1 appears to protect a cleanup script shipped weeks later.
_FILE_BOUNDARY_RE = re.compile(
    r"^\s*(?:--|/\*)[^\n]*?(?:"
    r"\b[VvRr]\d+(?:[._]\d+)*__\w+\.sql\b"      # V12__cleanup.sql / R1_2__x.sql
    r"|\bnext\s+release\b"
    r"|\bseparate\s+(?:release|script|deploy(?:ment)?)\b"
    r")",
    re.IGNORECASE | re.MULTILINE,
)


# --------------------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------------------


class Linter:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx

    def lint_text(self, sql: str, filename: str = "<stdin>") -> list[Finding]:
        stmts = split_statements(sql)
        findings: list[Finding] = []
        blanked_all = blank_comments_and_literals(sql)
        # Decided per statement, never over the whole file: an unbounded window across
        # the full text would pair an innocuous ALTER with an unrelated later keyword.
        # Computed up front so a rollback listed *before* its DDL is still evaluated.
        has_structural_ddl = any(_STRUCTURAL_DDL_RE.search(st.text) for st in stmts)

        def f(code: str, detail: str, line: int, severity: str | None = None) -> Finding:
            return Finding(
                code=code,
                severity=severity or CHECKS[code]["severity"],
                title=CHECKS[code]["title"],
                detail=detail,
                file=filename,
                line=line,
            )

        lock_timeout_set = False
        uncommitted_dml_line: int | None = None
        novalidate_constraints: set[str] = set()
        saw_bulk_dml = False
        saw_dbms_stats = "DBMS_STATS" in blanked_all.upper()
        rename_to_lines: list[int] = []
        rename_pairs: list[tuple[str, str]] = []
        created_tables: set[str] = set()
        snapshots: dict = {}
        restore_point_taken = False
        nologging_seen_line: int | None = None
        logging_restored = False

        for stmt in stmts:
            t = stmt.text
            upper = t.upper()
            stripped = " ".join(t.split())

            # --- session state -------------------------------------------------------
            # A version header or "next release" marker in the comments attached to this
            # statement means a new session starts here. Reset before anything else, so
            # an ALTER SESSION on the very next line still registers.
            if _FILE_BOUNDARY_RE.search(stmt.raw):
                lock_timeout_set = False
                uncommitted_dml_line = None

            if re.search(r"ALTER\s+SESSION\s+SET\s+DDL_LOCK_TIMEOUT", upper):
                mv = _DDL_LOCK_TIMEOUT_RE.search(t)
                tv = TimeoutValue(mv.group(1) if mv else "")
                lock_timeout_set = tv.protects

                if tv.kind == TimeoutValue.ZERO:
                    findings.append(
                        f(
                            "ORA026",
                            "DDL_LOCK_TIMEOUT = 0 is Oracle's default and means NOWAIT: the "
                            "next DDL fails immediately with ORA-00054 if any session holds "
                            "even a transient lock. Setting it to 0 explicitly is the same as "
                            "not setting it, so it satisfies the letter of 'DDL_LOCK_TIMEOUT "
                            "is set' while providing none of the protection. Use a small "
                            "positive value (3–10s is typical for OLTP).",
                            stmt.line,
                        )
                    )
                elif tv.kind == TimeoutValue.INVALID:
                    findings.append(
                        f(
                            "ORA028",
                            "DDL_LOCK_TIMEOUT = {!r} is not a value Oracle accepts — the "
                            "parameter takes an integer in [0, {:,}]. The ALTER SESSION "
                            "itself therefore fails, and because that error is easy to "
                            "overlook in a deploy log the session carries on with the "
                            "default of 0 (NOWAIT). The script reads as protected and is "
                            "not; every DDL after this line is unguarded."
                            .format(tv.raw, _DDL_LOCK_TIMEOUT_MAX),
                            stmt.line,
                        )
                    )
                elif tv.kind == TimeoutValue.DYNAMIC:
                    findings.append(
                        f(
                            "ORA029",
                            "DDL_LOCK_TIMEOUT is set from {!r}, so its value cannot be "
                            "checked from the script. The gate is recorded as satisfied "
                            "because it cannot be proven wrong, not because it was "
                            "verified — confirm what the variable resolves to at deploy "
                            "time, and that it is neither 0 (NOWAIT) nor larger than the "
                            "maintenance window.".format(tv.raw),
                            stmt.line,
                        )
                    )
                elif tv.number is not None and tv.number > _DDL_LOCK_TIMEOUT_SANE_MAX:
                    findings.append(
                        f(
                            "ORA027",
                            "DDL_LOCK_TIMEOUT = {} seconds ({:.1f} hours) exceeds any realistic "
                            "maintenance window. The session will sit blocked long past the "
                            "point an operator would have intervened, holding its place in the "
                            "lock queue and blocking DML that queues behind it. Size the "
                            "timeout to the window, not to the maximum Oracle accepts."
                            .format(tv.number, tv.number / 3600),
                            stmt.line,
                        )
                    )
                continue
            if re.match(r"^\s*COMMIT\b", upper) or re.match(r"^\s*ROLLBACK\b", upper):
                uncommitted_dml_line = None
                continue

            # Objects this script creates are not live: nothing reads or writes an
            # interim/new table before cutover, so constraint validation and index builds
            # on it block nobody. Without this, the standard CTAS and DBMS_REDEFINITION
            # patterns — which necessarily build a second table — light up with critical
            # findings that are correct about the SQL and wrong about the risk.
            ct = re.search(r"\bCREATE\s+(?:GLOBAL\s+TEMPORARY\s+)?TABLE\s+([\w.\"]+)", t,
                           re.IGNORECASE)
            if ct:
                created_tables.add(ct.group(1).upper().strip('"'))

            # A pre-DDL snapshot only mitigates damage to the table it actually copied.
            # Recording a bare "a backup happened somewhere" boolean let a CTAS of
            # CUSTOMERS downgrade a destructive statement against ORDERS — the reviewer
            # sees "mitigated" and the data is still unrecoverable. Key it by source.
            snap = _CTAS_RE.search(t)
            if snap:
                src = snap.group(3).upper().strip('"')
                snapshots.setdefault(src, []).append(
                    Snapshot(stmt.line, snap.group(2), snap.group(4))
                )
            # A *guaranteed* restore point is database-wide, so it covers any target.
            # A normal one is not a recovery artefact at all — see ORA030 below.
            if _GUARANTEED_RESTORE_POINT_RE.search(t):
                # Its whole value is that you can FLASHBACK DATABASE to it, and that is
                # Enterprise Edition only — as this skill's own licensing matrix already
                # says. Accepting it on SE2 made the checker contradict its own reference
                # doc and hand an SE2 site a rollback it cannot perform.
                ed = self.ctx.edition.upper()
                if ed in {"SE2", "SE", "XE", "STANDARD"}:
                    findings.append(
                        f(
                            "ORA032",
                            "A guaranteed restore point is only useful because FLASHBACK "
                            "DATABASE can return to it, and Flashback Database is "
                            "Enterprise Edition only — this database is {}. The statement "
                            "does not give this migration a rollback, so the destructive "
                            "steps below remain unmitigated. On {} the recovery artefact "
                            "has to be a full table copy taken before the change, or an "
                            "RMAN backup for PITR.".format(self.ctx.edition, self.ctx.edition),
                            stmt.line,
                        )
                    )
                elif ed in {"EE", "ENTERPRISE"}:
                    restore_point_taken = True
                else:
                    # Edition unknown. SKILL.md Gate 1 says assume SE2 — the most
                    # restrictive — so this must NOT downgrade anything. Accepting it
                    # here made the checker contradict its own gate and produced a safety
                    # false negative: the destructive statement below silently dropped
                    # from critical to warning on the strength of an unverified edition.
                    findings.append(
                        f(
                            "ORA032",
                            "A guaranteed restore point is only useful because FLASHBACK "
                            "DATABASE can return to it, and that is Enterprise Edition "
                            "only — but the edition has not been established. Gate 1 says "
                            "assume SE2 when unknown, so this is NOT counted as a recovery "
                            "artefact and the destructive statements below stay at full "
                            "severity. Confirm the edition to change that. Three operational "
                            "preconditions matter even on EE: the database must be in "
                            "ARCHIVELOG mode, a Fast Recovery Area must be configured with "
                            "room to spare, and creating a restore point needs an "
                            "administrative privilege a migration account usually lacks. "
                            "Whichever edition this turns out to be, schedule the DROP "
                            "RESTORE POINT for sign-off — a guaranteed restore point pins "
                            "flashback logs until dropped and will fill the FRA if left "
                            "behind.",
                            stmt.line,
                            severity=WARNING,
                        )
                    )
            elif _ANY_RESTORE_POINT_RE.search(t):
                findings.append(
                    f(
                        "ORA030",
                        "CREATE RESTORE POINT without GUARANTEE FLASHBACK DATABASE creates a "
                        "normal restore point: an SCN bookmark, not a retention promise. "
                        "Flashing back to it works only while the required flashback logs "
                        "happen to still exist, which is bounded by "
                        "DB_FLASHBACK_RETENTION_TARGET — documented as a target, not a "
                        "guarantee — and the restore point itself ages out of the control "
                        "file without being dropped. It therefore does not mitigate any "
                        "irreversible statement in this script. Add GUARANTEE FLASHBACK "
                        "DATABASE (requires ARCHIVELOG plus FRA space, and must be dropped "
                        "explicitly at sign-off or it fills the FRA), or take a per-table "
                        "copy instead.",
                        stmt.line,
                    )
                )

            stmt_is_ddl = is_ddl(t)
            target = _target_table(t) or _truncate_target(t)
            # Parsed once, from the same helper the coverage logic uses. A second,
            # narrower regex here is how `ALTER TABLE t DROP (a, b)` — a documented and
            # perfectly ordinary Oracle form — produced no finding at all: the parser
            # understood it, the trigger did not.
            dropped = _dropped_columns(t)
            drops_unused = bool(re.search(r"\bDROP\s+UNUSED\s+COLUMNS\b", upper))
            destructive = bool(
                dropped
                or drops_unused
                or re.match(r"^\s*TRUNCATE\s+TABLE\b", t, re.IGNORECASE)
            )
            target_snaps = snapshots.get(target, []) if target else []
            # Whole-table destruction needs a whole-table copy; a column drop needs only a
            # copy containing those columns plus a surviving key, which is exactly the
            # targeted pattern references/large-table-migration.md recommends. Requiring a
            # full copy for it would have the checker reject its own documented advice.
            # `DROP UNUSED COLUMNS` names nothing, so only a full copy can cover it.
            if dropped:
                covered_by_copy = any(sn.covers_columns(dropped) for sn in target_snaps)
            else:
                covered_by_copy = any(sn.covers_whole_table() for sn in target_snaps)
            # Kept separate, not collapsed into one boolean: the recovery *procedure*
            # differs. A table copy means "MERGE the rows back"; a restore point means
            # "FLASHBACK DATABASE and lose everything since". Reporting one as the other
            # tells the reviewer to perform a step that does not exist.
            covered = restore_point_taken or covered_by_copy
            partial_only = not covered and bool(target_snaps)
            recovery_via = (
                "copy" if covered_by_copy else "restore-point" if restore_point_taken
                else None
            )
            if destructive and partial_only:
                worst = target_snaps[0]
                keyless = next(
                    (sn for sn in target_snaps if sn.lacks_recovery_key(dropped)), None
                )
                if keyless is not None:
                    worst = keyless
                    why = (
                        "copies only the columns being dropped, so nothing in it survives "
                        "to key a MERGE on — the doomed columns cannot vouch for each "
                        "other, and what is left after the drop is anonymous value lists "
                        "with no way to match them back to their rows"
                    )
                else:
                    why = worst.reason or "does not cover what is destroyed"
                line = worst.line
                findings.append(
                    f(
                        "ORA031",
                        "A CTAS of {} exists at line {}, but it does not qualify as a "
                        "recovery artefact: it {}. That is easy to mistake for a backup on "
                        "a skim, so the destructive statement below is still reported "
                        "unmitigated. Either take a full copy (SELECT * with no predicate) "
                        "or state explicitly in the rollback plan which subset is "
                        "recoverable and which is not.".format(target, line, why),
                        stmt.line,
                    )
                )

            # --- ORA016: DDL silently commits pending DML ----------------------------
            if stmt_is_ddl and uncommitted_dml_line is not None:
                findings.append(
                    f(
                        "ORA016",
                        "DML at line {} is still uncommitted when this DDL runs. Oracle "
                        "issues an implicit COMMIT before every DDL, so that DML is "
                        "committed silently and cannot be rolled back. Add an explicit "
                        "COMMIT or ROLLBACK before the DDL.".format(uncommitted_dml_line),
                        stmt.line,
                    )
                )
                uncommitted_dml_line = None

            # --- ORA001: DDL_LOCK_TIMEOUT --------------------------------------------
            if stmt_is_ddl and not lock_timeout_set:
                findings.append(
                    f(
                        "ORA001",
                        "DDL runs without ALTER SESSION SET DDL_LOCK_TIMEOUT. Oracle's "
                        "default is 0 (NOWAIT): the statement fails immediately with "
                        "ORA-00054 if any session holds even a transient lock. Set "
                        "DDL_LOCK_TIMEOUT before the first DDL in the script.",
                        stmt.line,
                    )
                )

            # --- ORA002: constraint validation ---------------------------------------
            m = re.search(
                r"ADD\s+CONSTRAINT\s+(\w+)\s+(FOREIGN\s+KEY|CHECK|UNIQUE|PRIMARY\s+KEY)",
                t,
                re.IGNORECASE,
            )
            if m:
                name = m.group(1).upper()
                if re.search(r"\bNOVALIDATE\b", upper):
                    novalidate_constraints.add(name)
                elif not re.search(r"\bCREATE\s+TABLE\b", upper) and (
                    _target_table(t) not in created_tables
                ):
                    # SKILL.md §8 only requires the two-step above 100K rows. Reporting a
                    # 5K-row table as critical would make the checker contradict the
                    # scorecard it feeds, and teaches reviewers to override it.
                    if self.ctx.small_enough_to_validate_inline:
                        findings.append(
                            f(
                                "ORA002",
                                "ADD CONSTRAINT {} validates every existing row under an "
                                "exclusive lock, but the table is {:,} rows — below the "
                                "{:,}-row threshold at which SKILL.md §8 requires the "
                                "two-step. The inline scan is cheap here, so this is a note, "
                                "not a defect. Use ENABLE NOVALIDATE + VALIDATE anyway if "
                                "the table is expected to grow past the threshold before "
                                "this migration ships."
                                .format(m.group(1), self.ctx.rows,
                                        CONSTRAINT_TWO_STEP_ROW_THRESHOLD),
                                stmt.line,
                                severity=INFO,
                            )
                        )
                    else:
                        findings.append(
                            f(
                                "ORA002",
                                "ADD CONSTRAINT {} validates every existing row while holding "
                                "an exclusive lock{}. Use the two-step pattern: ADD CONSTRAINT "
                                "... ENABLE NOVALIDATE (brief lock, no scan), then MODIFY "
                                "CONSTRAINT ... VALIDATE (Row Exclusive, does not block DML)."
                                .format(
                                    m.group(1),
                                    " — {:,} rows".format(self.ctx.rows)
                                    if self.ctx.rows is not None
                                    else " and the row count is unknown, so assume it is large",
                                ),
                                stmt.line,
                            )
                        )
            # NOT NULL declared inline with NOVALIDATE also registers the constraint
            for nn in re.finditer(
                r"CONSTRAINT\s+(\w+)\s+NOT\s+NULL[\s\S]{0,40}?NOVALIDATE", t, re.IGNORECASE
            ):
                novalidate_constraints.add(nn.group(1).upper())

            # --- ORA020: VALIDATE without a NOVALIDATE origin ------------------------
            v = re.search(
                r"(?:MODIFY\s+CONSTRAINT\s+(\w+)\s+VALIDATE|ENABLE\s+VALIDATE\s+CONSTRAINT\s+(\w+))",
                t,
                re.IGNORECASE,
            )
            if v:
                cname = (v.group(1) or v.group(2)).upper()
                if cname not in novalidate_constraints:
                    findings.append(
                        f(
                            "ORA020",
                            "Constraint {} is validated without ever having been created "
                            "ENABLE NOVALIDATE in this script. If it is currently DISABLED "
                            "or was added validating, this takes the full-scan path under "
                            "an exclusive lock — the cost the two-step pattern exists to "
                            "avoid. Confirm its current state in USER_CONSTRAINTS."
                            .format(cname),
                            stmt.line,
                        )
                    )

            # --- ORA003: partition DDL ------------------------------------------------
            if _PARTITION_DDL_RE.search(t) and re.search(r"\bALTER\s+TABLE\b", upper):
                gi = self.ctx.global_indexes.lower()
                if not re.search(r"\bUPDATE\s+(GLOBAL\s+)?INDEXES\b", upper) and gi != "no":
                    findings.append(
                        f(
                            "ORA003",
                            "Partition maintenance without UPDATE INDEXES leaves every "
                            "global index on the table UNUSABLE; queries that pick a global "
                            "index path then fail with ORA-01502."
                            + (
                                "  The table is recorded as carrying global indexes, so this "
                                "is an outage waiting to happen."
                                if gi == "yes"
                                else "  Whether this table has global indexes is not "
                                "knowable from the SQL and was not supplied, so the "
                                "conservative verdict stands: run the query below, and pass "
                                "--global-indexes no to silence this if the answer is none. "
                                "UPDATE INDEXES on a table with no global indexes is a no-op, "
                                "so adding it costs nothing and omitting it can cost an "
                                "outage.\n         "
                                "SELECT index_name FROM dba_indexes WHERE table_name = "
                                "'<TABLE>' AND partitioned = 'NO';"
                            )
                            + "  Append UPDATE INDEXES, or schedule an explicit global index "
                            "rebuild in the same window.",
                            stmt.line,
                        )
                    )

            # --- ORA005 / ORA019: MOVE and REBUILD ------------------------------------
            if re.search(r"\bALTER\s+TABLE\b[\s\S]*\bMOVE\b", upper) and not _PARTITION_DDL_RE.search(t):
                if not re.search(r"\bONLINE\b", upper):
                    findings.append(
                        f(
                            "ORA005",
                            self._move_detail(),
                            stmt.line,
                        )
                    )
            if re.search(r"\bALTER\s+INDEX\b[\s\S]*\bREBUILD\b", upper) and not re.search(
                r"\bONLINE\b", upper
            ):
                findings.append(
                    f(
                        "ORA019",
                        "ALTER INDEX REBUILD without ONLINE holds an exclusive lock for the "
                        "whole rebuild, blocking DML on the base table. "
                        + self._ee_suffix("REBUILD ONLINE"),
                        stmt.line,
                    )
                )

            # --- ORA006: index build ---------------------------------------------------
            if (
                re.match(r"^\s*CREATE\s+(UNIQUE\s+)?INDEX\b", t, re.IGNORECASE)
                and not re.search(r"\bONLINE\b", upper)
                and _target_table(t) not in created_tables
            ):
                findings.append(
                    f(
                        "ORA006",
                        "Non-online CREATE INDEX takes a Share lock that blocks all "
                        "INSERT/UPDATE/DELETE on the base table for the entire build. "
                        + self._ee_suffix("CREATE INDEX ... ONLINE"),
                        stmt.line,
                    )
                )

            # --- ORA007 / ORA025: column removal ---------------------------------------
            if dropped or drops_unused:
                # Always reported: a column drop is worth a line in every review. What a
                # matching snapshot changes is the severity, not the existence. An
                # earlier revision suppressed the finding entirely, so an unrelated
                # backup elsewhere in the script made the drop invisible.
                findings.append(
                    f(
                        "ORA007",
                        "DROP COLUMN destroys the data and auto-commits, so there is no "
                        "ROLLBACK and FLASHBACK TABLE ... TO SCN/TIMESTAMP cannot cross it."
                        + (
                            "  This script does copy {} beforehand, so recovery is a MERGE "
                            "back from that copy — downgraded from critical. The copy "
                            "carries the dropped column plus at least one other column to "
                            "key on; confirm that column really is unique, because a MERGE "
                            "keyed on a non-unique column cannot restore the rows."
                            .format(target)
                            if recovery_via == "copy"
                            else "  A guaranteed restore point covers this — downgraded from "
                            "critical. Recovery is FLASHBACK DATABASE TO RESTORE POINT, "
                            "which rewinds the whole database and discards every other "
                            "transaction since, so it needs the application down. There is "
                            "no per-table copy here to MERGE back from. Confirm before "
                            "relying on it: the database is in ARCHIVELOG mode, a Fast "
                            "Recovery Area is configured with room to spare, and the "
                            "deploying account holds the privilege to create the restore "
                            "point. Then schedule the DROP RESTORE POINT for sign-off — a "
                            "guaranteed restore point pins flashback logs until it is "
                            "dropped and will fill the FRA if it is forgotten."
                            if recovery_via == "restore-point"
                            else "  No copy of {} is taken in this script. Snapshot it first "
                            "(CREATE TABLE mig_bak_... AS SELECT pk, col FROM {}) or create a "
                            "guaranteed restore point, and classify the phase restore/PITR — "
                            "never compensating-DDL.".format(
                                target or "the table", target or "t"
                            )
                        ),
                        stmt.line,
                        severity=WARNING if covered else None,
                    )
                )
            if re.search(r"\bSET\s+UNUSED\b", upper):
                findings.append(
                    f(
                        "ORA025",
                        "SET UNUSED avoids the physical rewrite cost of DROP COLUMN, but it "
                        "is equally irreversible — the column can never be restored to use. "
                        "Do not record it as a rollback-friendly alternative.",
                        stmt.line,
                    )
                )

            # --- ORA017: TRUNCATE --------------------------------------------------------
            if re.match(r"^\s*TRUNCATE\s+TABLE\b", t, re.IGNORECASE):
                # Same positive exemption ORA007 already honours: a pre-DDL snapshot or a
                # guaranteed restore point earlier in the script *is* the mitigation this
                # check asks for. Reporting it as unmitigated would penalise the script
                # that did the right thing.
                findings.append(
                    f(
                        "ORA017",
                        "TRUNCATE is DDL: it auto-commits, cannot be rolled back, and resets "
                        "the high-water mark, and Flashback Table cannot cross it."
                        + (
                            "  A full copy of {} is created earlier in this script, so the "
                            "recovery artefact exists — downgraded from critical. Confirm "
                            "the CTAS actually completed, not merely that it was issued."
                            .format(target)
                            if recovery_via == "copy"
                            else "  A guaranteed restore point covers this — downgraded from "
                            "critical. Recovery is FLASHBACK DATABASE TO RESTORE POINT, "
                            "which rewinds the entire database and requires the application "
                            "to be down; there is no table copy here to reinsert from. "
                            "Confirm ARCHIVELOG mode, a Fast Recovery Area with room, and "
                            "the privilege to create the restore point — then schedule the "
                            "DROP RESTORE POINT for sign-off, or it pins flashback logs and "
                            "fills the FRA."
                            if recovery_via == "restore-point"
                            else "  No copy of {} and no guaranteed restore point appears in "
                            "this script — a backup of some *other* table does not count. "
                            "Create one before approving, and classify the phase "
                            "irreversible.".format(target or "the table")
                        ),
                        stmt.line,
                        severity=WARNING if covered else None,
                    )
                )

            # --- ORA024: DROP TABLE PURGE -------------------------------------------------
            if re.search(r"\bDROP\s+TABLE\b[\s\S]*\bPURGE\b", upper):
                findings.append(
                    f(
                        "ORA024",
                        "DROP TABLE ... PURGE bypasses the recycle bin, so FLASHBACK TABLE "
                        "... TO BEFORE DROP is unavailable. Only purge an interim/backup "
                        "table after the migration has been signed off.",
                        stmt.line,
                    )
                )

            # --- ORA018: RENAME COLUMN ------------------------------------------------------
            if re.search(r"\bRENAME\s+COLUMN\b", upper):
                findings.append(
                    f(
                        "ORA018",
                        "RENAME COLUMN is metadata-only and fast (supported since 9i R2) — "
                        "the risk is not the database. It commits instantly and every "
                        "deployed statement using the old name starts failing with "
                        "ORA-00904. Use expand/contract: add the new column, dual-write, "
                        "backfill, cut reads over, then SET UNUSED the old one.",
                        stmt.line,
                    )
                )

            # --- ORA015: MODIFY column needs classification ------------------------------
            mm = re.search(
                r"\bALTER\s+TABLE\s+(\S+)[\s\S]*?\bMODIFY\b\s*\(?\s*(\w+)\s+"
                r"(NUMBER|VARCHAR2|NVARCHAR2|CHAR|DATE|TIMESTAMP|CLOB|BLOB|RAW|FLOAT|BINARY_\w+)",
                t,
                re.IGNORECASE,
            )
            if mm and "NOT NULL" not in upper:
                findings.append(
                    f(
                        "ORA015",
                        "MODIFY {}.{} to {} — classify before assigning risk. Widening a "
                        "char length, or a NUMBER's precision and scale together, is a "
                        "dictionary update with a brief lock (do NOT call it a rewrite). "
                        "Decreasing precision/scale raises ORA-01440 and changing datatype "
                        "class raises ORA-01439: both are rejected outright unless the "
                        "column is empty, regardless of table size. Compare against the "
                        "current type in USER_TAB_COLUMNS before deciding."
                        .format(mm.group(1), mm.group(2), mm.group(3).upper()),
                        stmt.line,
                    )
                )

            # --- ORA004 / ORA021: unbounded DML --------------------------------------------
            if _DML_RE.match(t):
                uncommitted_dml_line = stmt.line
                unbounded = not (
                    _BOUNDED_DML_RE.search(t)
                    or _SINGLE_KEY_DML_RE.search(t)
                    or re.match(r"^\s*INSERT\s+INTO\b[\s\S]*\bVALUES\b", t, re.IGNORECASE)
                )
                # Only unbounded DML is "bulk". A single-row keyed UPDATE does not
                # invalidate table statistics, so demanding DBMS_STATS after it is noise.
                saw_bulk_dml = saw_bulk_dml or unbounded
                if unbounded:
                    findings.append(
                        f(
                            "ORA004",
                            "DML with no ROWID/PK range bound rewrites the whole matching "
                            "set in one transaction: row locks held for the full duration, "
                            "UNDO growing until ORA-30036, and a single failure rolling back "
                            "all of it. Batch by ROWID or PK range with a COMMIT per batch, "
                            "or use DBMS_PARALLEL_EXECUTE."
                            + (
                                "  Table is {:,} rows.".format(self.ctx.rows)
                                if self.ctx.large_table
                                else ""
                            ),
                            stmt.line,
                        )
                    )

            # --- ORA008: unexecutable ROWID chunking ----------------------------------------
            if re.search(r"\bDBA_EXTENTS\b", upper) and re.search(
                r"\bDATA_OBJECT_ID\b", upper
            ):
                if not re.search(r"\b(DBA_OBJECTS|ALL_OBJECTS|USER_OBJECTS)\b", upper):
                    findings.append(
                        f(
                            "ORA008",
                            "DBA_EXTENTS has no DATA_OBJECT_ID column — this statement fails "
                            "with ORA-00904. Its columns are OWNER, SEGMENT_NAME, "
                            "PARTITION_NAME, SEGMENT_TYPE, TABLESPACE_NAME, EXTENT_ID, "
                            "FILE_ID, BLOCK_ID, BYTES, BLOCKS, RELATIVE_FNO. Join to "
                            "DBA_OBJECTS for DATA_OBJECT_ID (matching on partition name), "
                            "or use DBMS_PARALLEL_EXECUTE.CREATE_CHUNKS_BY_ROWID instead.",
                            stmt.line,
                        )
                    )

            # --- ORA011 / ORA012: DBMS_REDEFINITION -------------------------------------------
            if re.search(r"\bCOPY_TABLE_DEPENDENTS\b", upper):
                # The gate must be ON num_errors. Accepting the mere presence of a
                # RAISE_APPLICATION_ERROR or a DBA_REDEFINITION_ERRORS mention lets
                # `IF FALSE THEN RAISE...` pass, which is exactly the bug being hunted.
                # `num_errors => num_errors` must not count as a comparison either,
                # hence the `=(?!>)` guard against the named-parameter arrow.
                if not re.search(
                    r"\bIF\b[^;\n]{0,80}\bNUM_ERRORS\b"
                    r"|\bNUM_ERRORS\s*(?:>|<|!=|=(?!>))",
                    upper,
                ):
                    findings.append(
                        f(
                            "ORA011",
                            "COPY_TABLE_DEPENDENTS returns num_errors as an OUT parameter "
                            "that Oracle requires the caller to check before continuing. "
                            "Printing it is not checking it. Raise on num_errors > 0 and "
                            "query DBA_REDEFINITION_ERRORS — otherwise the cutover can "
                            "complete with indexes, constraints, triggers or grants missing.",
                            stmt.line,
                        )
                    )
            if re.search(r"\bFINISH_REDEF_TABLE\b", upper) and not re.search(
                r"\bDML_LOCK_TIMEOUT\b", upper
            ):
                findings.append(
                    f(
                        "ORA012",
                        "FINISH_REDEF_TABLE without an explicit dml_lock_timeout (12.1+). "
                        "The final swap then uses the release default rather than a value "
                        "chosen for your window — at one extreme the cutover aborts on any "
                        "concurrent DML after hours of copying, at the other it waits "
                        "indefinitely behind a long transaction. Pass a value, e.g. 30.",
                        stmt.line,
                    )
                )

            # --- ORA013: NOLOGGING as a hint ---------------------------------------------------
            for hint in re.finditer(r"/\*\+([\s\S]*?)\*/", stmt.raw):
                if re.search(r"\bNOLOGGING\b", hint.group(1), re.IGNORECASE):
                    findings.append(
                        f(
                            "ORA013",
                            "NOLOGGING is a segment attribute, not a hint. Oracle silently "
                            "ignores it inside /*+ ... */ — no error is raised and redo is "
                            "generated exactly as before. Set it with ALTER TABLE ... "
                            "NOLOGGING if that is genuinely intended, and check "
                            "V$DATABASE.FORCE_LOGGING, which overrides it anyway.",
                            stmt.line,
                        )
                    )

            # --- ORA023: NOLOGGING recoverability -----------------------------------------------
            if re.search(r"\bNOLOGGING\b", upper):
                nologging_seen_line = nologging_seen_line or stmt.line
            if re.search(r"\bLOGGING\b", upper) and not re.search(r"\bNOLOGGING\b", upper):
                logging_restored = True

            # --- ORA014: DBMS_LOCK.SLEEP ---------------------------------------------------------
            if re.search(r"\bDBMS_LOCK\.SLEEP\b", upper):
                findings.append(
                    f(
                        "ORA014",
                        "DBMS_LOCK.SLEEP needs an explicit GRANT EXECUTE ON DBMS_LOCK, which "
                        "migration accounts usually lack — the script then dies at runtime "
                        "with PLS-00201. DBMS_SESSION.SLEEP (18c+) is executable by any user.",
                        stmt.line,
                    )
                )

            # --- ORA010: Flashback misuse ----------------------------------------------------------
            if re.search(r"\bFLASHBACK\s+TABLE\b", upper) and re.search(
                r"\bTO\s+(SCN|TIMESTAMP)\b", upper
            ):
                if has_structural_ddl:
                    findings.append(
                        f(
                            "ORA010",
                            "FLASHBACK TABLE ... TO SCN/TIMESTAMP cannot cross a DDL that "
                            "changed the table's structure, and this script contains one "
                            "(dropped/modified column, MOVE, TRUNCATE, added constraint or "
                            "partition maintenance). It will fail, so it is not a recovery "
                            "plan. Use a pre-DDL snapshot, a guaranteed restore point, or "
                            "RMAN PITR. FLASHBACK TABLE ... TO BEFORE DROP is unaffected and "
                            "remains valid for an un-purged DROP TABLE.",
                            stmt.line,
                        )
                    )

            rn = re.search(
                r"\bALTER\s+TABLE\s+([\w.\"]+)\s+RENAME\s+TO\s+([\w.\"]+)", t, re.IGNORECASE
            )
            if rn:
                rename_to_lines.append(stmt.line)
                rename_pairs.append((rn.group(1).upper(), rn.group(2).upper()))

        # --- ORA009 / ORA022: multi-statement cutover ------------------------------------------
        if len(rename_to_lines) >= 2:
            # A script that already prepares the reverse rename has planned for the
            # window between the two statements. The risk is still worth naming, but it
            # is no longer critical — and reporting the documented safe procedure as a
            # critical defect is how a checker teaches people to ignore it.
            recovery_ready = bool(rename_pairs) and _has_reverse_rename(sql, rename_pairs)
            findings.append(
                f(
                    "ORA009",
                    "Two or more ALTER TABLE ... RENAME TO statements (lines {}) form the "
                    "cutover. Each is a separate DDL with its own implicit COMMIT — there is "
                    "no transaction around them and no way to create one. Between them the "
                    "original table name does not exist and application queries fail with "
                    "ORA-00942; if the second rename fails the schema stays that way. Plan a "
                    "quiesced two-step cutover with a prepared reverse-rename, or use "
                    "DBMS_REDEFINITION, whose FINISH_REDEF_TABLE genuinely is atomic."
                    .format(", ".join(str(x) for x in rename_to_lines))
                    + (
                        "  This script does prepare the reverse rename, so the recovery "
                        "step exists — downgraded from critical. Confirm the application "
                        "is quiesced for the window as well."
                        if recovery_ready
                        else "  No reverse rename appears anywhere in this script."
                    ),
                    rename_to_lines[0],
                    severity=WARNING if recovery_ready else None,
                )
            )
            for cm in re.finditer(
                r"(?:--|/\*)[^\n]*\b(atomic|atomically)\b", sql, re.IGNORECASE
            ):
                # A comment may say "atomic" in order to deny it. Flagging the sentence
                # that carries the correction is the same bug this check exists to catch,
                # pointed the wrong way.
                if _ATOMIC_DENIAL_RE.search(cm.group(0)):
                    continue
                findings.append(
                    f(
                        "ORA022",
                        "A comment describes this cutover as atomic, but it spans multiple "
                        "auto-committing DDL statements. The wording matters: a reader who "
                        "believes the swap is atomic will not write the recovery step for "
                        "the window in between. Call it a two-step cutover.",
                        sql.count("\n", 0, cm.start()) + 1,
                    )
                )

        if nologging_seen_line and not logging_restored:
            findings.append(
                f(
                    "ORA023",
                    "NOLOGGING is used but the script never switches the segment back to "
                    "LOGGING and takes no backup. The loaded blocks are unrecoverable from "
                    "archive logs, and any physical standby receives blocks it cannot use. "
                    "Check V$DATABASE.FORCE_LOGGING (which silently overrides NOLOGGING and "
                    "invalidates the runtime estimate), then either restore LOGGING or back "
                    "up the tablespace immediately after the load.",
                    nologging_seen_line,
                )
            )

        if saw_bulk_dml and not saw_dbms_stats:
            findings.append(
                f(
                    "ORA021",
                    "Bulk DML with no DBMS_STATS.GATHER_TABLE_STATS afterwards. Stale "
                    "statistics after a large backfill lead the optimizer to plans chosen "
                    "for the old row counts and column distributions.",
                    stmts[0].line if stmts else 1,
                )
            )

        findings.sort(key=lambda x: (-SEVERITY_ORDER[x.severity], x.line, x.code))
        return findings

    # -- context-sensitive wording ---------------------------------------------------

    def _ee_suffix(self, feature: str) -> str:
        if self.ctx.edition.upper() in {"SE2", "SE", "XE", "STANDARD"}:
            return (
                "{} requires Enterprise Edition and this database is {} — the online path "
                "is not available. Schedule a maintenance window with DDL_LOCK_TIMEOUT, or "
                "build into an interim table and cut over.".format(feature, self.ctx.edition)
            )
        if self.ctx.edition.upper() in {"EE", "ENTERPRISE"}:
            return "Use {} (available on Enterprise Edition).".format(feature)
        return (
            "Use {} if this is Enterprise Edition; confirm the edition first, because on "
            "SE2 the only option is a maintenance window.".format(feature)
        )

    def _move_detail(self) -> str:
        base = (
            "ALTER TABLE ... MOVE rewrites the entire table under an exclusive lock, "
            "blocking all DML for the duration, and leaves every index UNUSABLE "
            "(ORA-01502) afterwards. "
        )
        v = self.ctx.version.lower()
        if v in {"12.1", "12c", "11.2", "11g"}:
            return base + (
                "MOVE ONLINE is 12.2+; on {} it does not exist. Use DBMS_REDEFINITION (EE) "
                "or CTAS + a quiesced two-step cutover.".format(self.ctx.version)
            )
        if self.ctx.edition.upper() in {"SE2", "SE", "XE", "STANDARD"}:
            return base + (
                "MOVE ONLINE requires Enterprise Edition; on {} use CTAS + a quiesced "
                "two-step cutover.".format(self.ctx.edition)
            )
        return base + (
            "Use ALTER TABLE ... MOVE ONLINE, which needs Enterprise Edition and 12.2+ — "
            "confirm both, since '12c' alone does not establish 12.2."
        )


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------


def iter_sql_files(paths: Iterable[str]) -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for p in paths:
        path = pathlib.Path(p)
        if path.is_dir():
            out.extend(sorted(path.rglob("*.sql")))
        else:
            out.append(path)
    return out


def format_text(findings: list[Finding]) -> str:
    if not findings:
        return "clean — no findings"
    lines = []
    for fd in findings:
        lines.append(
            "{sev:<8} {code}  {file}:{line}\n         {title}\n         {detail}".format(
                sev=fd.severity.upper(),
                code=fd.code,
                file=fd.file,
                line=fd.line,
                title=fd.title,
                detail=fd.detail,
            )
        )
    counts: dict[str, int] = {}
    for fd in findings:
        counts[fd.severity] = counts.get(fd.severity, 0) + 1
    summary = ", ".join(
        "{} {}".format(counts[s], s) for s in (CRITICAL, WARNING, INFO) if s in counts
    )
    lines.append("\n{} finding(s): {}".format(len(findings), summary))
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lint_migration.py",
        description="Deterministic safety checker for Oracle migration scripts.",
    )
    p.add_argument("paths", nargs="+", help="SQL file(s) or directory(ies) to check")
    p.add_argument(
        "--edition",
        default="unknown",
        help="EE | SE2 | XE | unknown — gates ONLINE DDL and DBMS_REDEFINITION advice",
    )
    p.add_argument(
        "--version",
        default="unknown",
        help="12.1 | 12.2 | 19c | 21c | 23ai | unknown — 12.1 vs 12.2 gates MOVE ONLINE",
    )
    p.add_argument("--context-rows", type=int, default=None, help="target table row count")
    p.add_argument(
        "--global-indexes",
        choices=("yes", "no", "unknown"),
        default="unknown",
        help="does the target carry global indexes? 'no' suppresses the UPDATE INDEXES "
        "finding; default 'unknown' keeps the conservative verdict",
    )
    p.add_argument("--format", choices=("text", "json"), default="text")
    p.add_argument(
        "--fail-on",
        choices=(CRITICAL, WARNING, INFO, "never"),
        default=CRITICAL,
        help="minimum severity that sets exit code 1 (default: critical)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ctx = Context(
        edition=args.edition,
        version=args.version,
        rows=args.context_rows,
        global_indexes=args.global_indexes,
    )
    linter = Linter(ctx)

    files = iter_sql_files(args.paths)
    if not files:
        print("no .sql files found in: {}".format(", ".join(args.paths)), file=sys.stderr)
        return 2

    all_findings: list[Finding] = []
    for path in files:
        try:
            sql = path.read_text(encoding="utf-8")
        except OSError as exc:
            print("cannot read {}: {}".format(path, exc), file=sys.stderr)
            return 2
        all_findings.extend(linter.lint_text(sql, str(path)))

    if args.format == "json":
        print(
            json.dumps(
                {
                    "findings": [f.as_dict() for f in all_findings],
                    "counts": {
                        s: sum(1 for f in all_findings if f.severity == s)
                        for s in (CRITICAL, WARNING, INFO)
                    },
                },
                indent=2,
            )
        )
    else:
        print(format_text(all_findings))

    if args.fail_on == "never":
        return 0
    threshold = SEVERITY_ORDER[args.fail_on]
    return 1 if any(SEVERITY_ORDER[f.severity] >= threshold for f in all_findings) else 0


if __name__ == "__main__":
    sys.exit(main())

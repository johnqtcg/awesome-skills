#!/usr/bin/env python3
"""Deterministic safety checker for MySQL migration SQL and online-schema-change commands.

Unlike a documentation-presence test, this reads the *actual statements* a migration
would execute and decides whether the server will accept them, whether they block
writes, and whether the surrounding operational choices are recoverable.

Every rule below is traceable to the official MySQL manual (InnoDB Online DDL
Operations), the gh-ost repository, or the Percona Toolkit documentation. See
references/ddl-algorithm-matrix.md for the transcribed source tables.

Usage:
    lint_migration.py --mysql-version 8.0.29 migration.sql [more.sql ...]
    lint_migration.py --mysql-version 5.7.40 --format json migrations/
    lint_migration.py --mysql-version 8.0.35 --skip-negative-examples doc.md

Exit codes:
    0  no findings at or above --fail-on (default: critical)
    1  findings at or above --fail-on
    2  usage / unreadable input (never confused with "found problems")
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from dataclasses import dataclass
from typing import Iterator, Sequence

CRITICAL = "critical"
WARNING = "warning"
SEVERITIES = (CRITICAL, WARNING)

# ---------------------------------------------------------------------------
# Version handling
# ---------------------------------------------------------------------------

Version = tuple[int, int, int]

V_5_7 = (5, 7, 0)
V_8_0 = (8, 0, 0)
# The ALGORITHM=INSTANT *clause itself* arrives in 8.0.12, not in 8.0.0. The
# manual (MySQL 8.0 "What Is New", Nutshell): "As of MySQL 8.0.12,
# ALGORITHM=INSTANT is supported for the following ALTER TABLE operations:
# adding a column; adding or dropping a virtual column; adding or dropping a
# column default value; modifying an ENUM or SET definition; changing the index
# type; renaming a table." On 8.0.0-8.0.11 *any* ALGORITHM=INSTANT fails —
# including ones unrelated to ADD COLUMN, such as ALTER COLUMN ... SET DEFAULT.
V_INSTANT_INTRODUCED = (8, 0, 12)
V_INSTANT_RENAME_COLUMN = (8, 0, 28)
V_INSTANT_ANY_POSITION = (8, 0, 29)
V_INSTANT_DROP_COLUMN = (8, 0, 29)
V_REPLICA_TERMINOLOGY = (8, 0, 22)
V_SLAVE_REMOVED = (8, 4, 0)

# Server versions this skill's matrix has actually been checked against, and what
# the check consisted of. Anything outside this set is reported (MM028) rather
# than silently analysed with the nearest set of rules — dev.mysql.com itself
# redirects an unknown version like 10.0 to the current release, so "the docs
# loaded" is not evidence that the rules apply.
VERIFIED_RANGES: list[tuple[Version, Version, str]] = [
    ((5, 7, 0), (5, 8, 0), "transcribed from the 5.7 manual, 2026-08-06"),
    ((8, 0, 0), (8, 1, 0), "transcribed from the 8.0 manual, 2026-08-06"),
    ((8, 4, 0), (8, 5, 0), "transcribed from the 8.4 manual, 2026-08-06"),
]
# Ranges where 8.4's rules are applied but the wider migration-safety model was
# NOT confirmed. "The online-DDL matrix is identical" is a weaker claim than "the
# same rules apply": MySQL 9.1 raised the INSTANT row-version ceiling from 64 to
# 255 without touching that matrix at all, so a version can be matrix-identical
# and still behave differently in ways this skill documents.
ASSUMED_RANGES: list[tuple[Version, Version, str]] = [
    ((8, 1, 0), (8, 4, 0),
     "an end-of-life innovation release; Oracle redirects its documentation to 8.4, so 8.4's "
     "rules are applied here, but they were never confirmed against this release"),
    ((9, 0, 0), (10, 0, 0),
     "a 9.x release. Its online-DDL matrix is byte-identical to 8.4 (checked 2026-08-06), but "
     "that is not the whole safety model: 9.1.0 raised the maximum TOTAL_ROW_VERSIONS from 64 to "
     "255, so version-specific limits documented here may not apply. Treat algorithm and lock "
     "verdicts as 8.4's, and re-check any numeric threshold against the 9.x manual"),
]


def version_coverage(v: Version) -> tuple[str, str]:
    """Classify a version as ('verified'|'assumed'|'unverified', explanation)."""
    for lo, hi, how in VERIFIED_RANGES:
        if lo <= v < hi:
            return "verified", how
    for lo, hi, why in ASSUMED_RANGES:
        if lo <= v < hi:
            return "assumed", why
    if v < (5, 7, 0):
        return "unverified", (
            "older than 5.7, which is the oldest release this skill covers; InnoDB online DDL "
            "support differs substantially before 5.7")
    return "unverified", (
        "newer than anything this skill covers (verified: 5.7, 8.0, 8.4; assumed: 8.1-8.3, 9.x). "
        "The rules below are 8.4 rules applied on faith")


def parse_version(raw: str) -> Version:
    """Parse '8.0.29' / '5.7' / '8.4.0-log' into a comparable tuple."""
    m = re.match(r"^\s*(\d+)\.(\d+)(?:\.(\d+))?", raw)
    if not m:
        raise ValueError(f"unparseable MySQL version: {raw!r}")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0))


def fmt_version(v: Version) -> str:
    return ".".join(str(p) for p in v)


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    check_id: str
    severity: str
    path: str
    line: int
    message: str
    evidence: str

    def as_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "severity": self.severity,
            "path": self.path,
            "line": self.line,
            "message": self.message,
            "evidence": self.evidence,
        }


@dataclass
class Segment:
    """A contiguous run of one language within a file."""

    lang: str  # "sql" | "bash"
    text: str
    line_offset: int  # 1-based line number of segment's first line
    negative: bool = False  # marked as a deliberate anti-example


@dataclass
class Context:
    path: str
    version: Version
    segments: list[Segment]
    # Whole-file signals, computed once.
    has_set_vars_guard: bool = False
    mentions_backup: bool = False


# ---------------------------------------------------------------------------
# Declared coverage. Each entry MUST have a violating fixture in
# scripts/tests/test_lint_migration.py::TestEveryDeclaredCheckFires.
# ---------------------------------------------------------------------------

CHECK_REGISTRY: dict[str, dict] = {
    "MM001": {"severity": CRITICAL,
              "title": "ALGORITHM=INSTANT on a server without the INSTANT clause (< 8.0.12)"},
    # MM002 ("INSTANT ADD COLUMN before 8.0.12") was withdrawn on 2026-08-06.
    # It was a strict subset of MM001 once MM001's threshold was corrected from
    # 8.0.0 to 8.0.12, and a check that can never fire independently is dead
    # weight that inflates the coverage count. The ID is not reused.
    "MM003": {"severity": CRITICAL, "title": "INSTANT ADD COLUMN at a position before 8.0.29"},
    "MM004": {"severity": CRITICAL, "title": "INSTANT DROP COLUMN before 8.0.29"},
    "MM005": {"severity": CRITICAL, "title": "INSTANT column rename before 8.0.28"},
    "MM006": {"severity": CRITICAL, "title": "ALGORITHM=INSTANT on an operation that is never INSTANT"},
    "MM007": {"severity": CRITICAL, "title": "Non-DEFAULT ALGORITHM on a 5.7 partition clause"},
    "MM008": {"severity": CRITICAL, "title": "LOCK=NONE on an operation that blocks concurrent DML"},
    "MM009": {"severity": CRITICAL, "title": "ADD FOREIGN KEY with ALGORITHM=INPLACE while foreign_key_checks is on"},
    "MM010": {"severity": WARNING,
              "title": "VARCHAR change may cross the 255-byte boundary — verify the current definition"},
    "MM011": {"severity": CRITICAL, "title": "WHILE/REPEAT/LOOP outside a stored program"},
    "MM012": {"severity": CRITICAL, "title": "UPDATE ... LIMIT ... OFFSET (invalid MySQL syntax)"},
    "MM013": {"severity": CRITICAL, "title": "sql_log_bin disabled"},
    "MM014": {"severity": WARNING, "title": "ALTER TABLE without an explicit ALGORITHM"},
    "MM015": {"severity": WARNING, "title": "DDL without a lock_wait_timeout session guard"},
    "MM016": {"severity": WARNING, "title": "LIMIT/OFFSET backfill pattern"},
    "MM017": {"severity": CRITICAL, "title": "gh-ost --allow-on-master pointed at a replica"},
    "MM018": {"severity": WARNING, "title": "gh-ost destructive cleanup flag used as a default"},
    "MM019": {"severity": CRITICAL, "title": "pt-osc --null-to-not-null silently rewrites data"},
    "MM020": {"severity": WARNING, "title": "pt-osc invocation with neither --dry-run nor --execute"},
    "MM021": {"severity": CRITICAL, "title": "SHOW REPLICA STATUS before 8.0.22"},
    "MM022": {"severity": CRITICAL, "title": "SHOW SLAVE STATUS on 8.4+ (statement removed)"},
    "MM023": {"severity": CRITICAL, "title": "performance_schema.data_locks on 5.7 (table does not exist)"},
    "MM024": {"severity": WARNING, "title": "Replica lag column name does not match the server version"},
    "MM025": {"severity": WARNING, "title": "Irreversible DROP without a stated backup"},
    "MM026": {"severity": CRITICAL,
              "title": "IF [NOT] EXISTS on an ALTER TABLE clause — not MySQL syntax"},
    "MM027": {"severity": CRITICAL,
              "title": "pt-osc --preserve-triggers combined with an incompatible flag"},
    "MM028": {"severity": WARNING,
              "title": "Target version is outside the range this skill's matrix was verified against"},
    "MM029": {"severity": CRITICAL,
              "title": "ALGORITHM=INSTANT combined with a non-DEFAULT LOCK clause"},
    "MM030": {"severity": WARNING,
              "title": "Migration carrier the checker cannot parse (Liquibase XML/YAML/JSON, programmatic)"},
}


# ---------------------------------------------------------------------------
# Lexing helpers
# ---------------------------------------------------------------------------

_NUL = "\x00"


def mask_sql_noise(sql: str) -> str:
    """Blank comments and string literals, preserving length and line structure.

    Replacement uses NUL rather than removal so that character offsets, line
    numbers, and token adjacency all survive: collapsing a span to "" merges the
    surrounding tokens and fabricates matches that were never in the source.
    """
    out = list(sql)
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""
        if ch == "-" and nxt == "-":
            j = sql.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = _NUL
            i = j
        elif ch == "#":
            j = sql.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = _NUL
            i = j
        elif ch == "/" and nxt == "*":
            j = sql.find("*/", i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                if sql[k] != "\n":
                    out[k] = _NUL
            i = j
        elif ch in ("'", '"'):
            quote = ch
            j = i + 1
            while j < n:
                if sql[j] == "\\":
                    j += 2
                    continue
                if sql[j] == quote:
                    j += 1
                    break
                j += 1
            for k in range(i + 1, min(j - 1, n) + 1):
                if k < n and sql[k] != "\n" and sql[k] != quote:
                    out[k] = _NUL
            i = j
        else:
            i += 1
    return "".join(out)


def split_statements(masked: str) -> Iterator[tuple[int, str]]:
    """Yield (0-based start line, statement text) using masked SQL.

    DELIMITER blocks are emitted whole so that a stored program body is never
    mistaken for loose top-level statements.
    """
    lines = masked.split("\n")
    buf: list[str] = []
    start = 0
    delim = ";"
    in_program = False
    for idx, line in enumerate(lines):
        dm = re.match(r"^\s*DELIMITER\s+(\S+)", line, re.I)
        if dm:
            if buf and "".join(buf).strip():
                yield start, "\n".join(buf)
            buf, start = [], idx + 1
            new = dm.group(1)
            in_program = new != ";"
            delim = new
            continue
        if not buf:
            start = idx
        buf.append(line)
        if delim in line:
            yield start, "\n".join(buf)
            buf, start = [], idx + 1
            if in_program and delim != ";":
                pass
    if buf and "".join(buf).strip():
        yield start, "\n".join(buf)


def unmask_to_space(s: str) -> str:
    """Turn masking sentinels back into spaces.

    Masking uses NUL so that a future adjacency rule can tell "there was code
    here" from "there was always a space here". But NUL is not whitespace to
    `re`, so a statement preceded by a comment would start with NUL characters
    and defeat every `^\\s*` anchor. Convert before anchored matching.
    """
    return s.replace(_NUL, " ")


def norm(s: str) -> str:
    """Collapse whitespace for robust multi-line pattern matching."""
    return re.sub(r"\s+", " ", unmask_to_space(s)).strip()


# ---------------------------------------------------------------------------
# Segment extraction
# ---------------------------------------------------------------------------

_NEGATIVE_MARKERS = re.compile(
    r"\b(WRONG|INVALID|BAD|ANTI-?EXAMPLE|DO NOT|DON'T|NEVER DO|AVOID|ALSO WRONG|DEAD ROUTE)\b",
    re.I,
)

_SQL_LANGS = {"sql", "mysql"}
_SH_LANGS = {"bash", "sh", "shell", "console"}


def extract_segments(path: pathlib.Path, text: str) -> list[Segment]:
    suffix = "".join(path.suffixes).lower()
    if path.suffix.lower() in (".md", ".markdown"):
        return _extract_markdown(text)
    if path.suffix.lower() in (".sh", ".bash"):
        return [Segment("bash", text, 1)]
    if suffix.endswith(".sql") or path.suffix.lower() in ("", ".ddl"):
        return [Segment("sql", text, 1)]
    return [Segment("sql", text, 1)]


def _extract_markdown(text: str) -> list[Segment]:
    segments: list[Segment] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        m = re.match(r"^\s*```+\s*([A-Za-z0-9_+-]*)", lines[i])
        if not m:
            i += 1
            continue
        lang = m.group(1).lower()
        fence_line = i
        j = i + 1
        while j < len(lines) and not re.match(r"^\s*```+\s*$", lines[j]):
            j += 1
        body = "\n".join(lines[fence_line + 1 : j])
        if lang in _SQL_LANGS:
            kind = "sql"
        elif lang in _SH_LANGS:
            kind = "bash"
        else:
            i = j + 1
            continue
        # A block is "negative" if it, or the prose just above it, labels it wrong.
        preamble = "\n".join(lines[max(0, fence_line - 3) : fence_line])
        negative = bool(_NEGATIVE_MARKERS.search(body) or _NEGATIVE_MARKERS.search(preamble))
        segments.append(Segment(kind, body, fence_line + 2, negative))
        i = j + 1
    return segments


# ---------------------------------------------------------------------------
# Operation classification (from references/ddl-algorithm-matrix.md)
# ---------------------------------------------------------------------------

# Operations the manual lists as Instant = No on every 8.0/8.4 release.
NEVER_INSTANT = [
    (re.compile(r"\bADD\s+(?:UNIQUE\s+|FULLTEXT\s+|SPATIAL\s+)?(?:INDEX|KEY)\b", re.I),
     "adding an index"),
    (re.compile(r"\bADD\s+PRIMARY\s+KEY\b", re.I), "adding a primary key"),
    (re.compile(r"\bDROP\s+PRIMARY\s+KEY\b", re.I), "dropping a primary key"),
    (re.compile(r"\bADD\s+(?:CONSTRAINT\s+\S+\s+)?FOREIGN\s+KEY\b", re.I),
     "adding a foreign key"),
    (re.compile(r"\bDROP\s+FOREIGN\s+KEY\b", re.I), "dropping a foreign key"),
    (re.compile(r"\bCONVERT\s+TO\s+CHARACTER\s+SET\b", re.I), "converting a character set"),
    (re.compile(r"\bROW_FORMAT\s*=", re.I), "changing ROW_FORMAT"),
    (re.compile(r"\bKEY_BLOCK_SIZE\s*=", re.I), "changing KEY_BLOCK_SIZE"),
    (re.compile(r"\bRENAME\s+(?:INDEX|KEY)\b", re.I), "renaming an index"),
    (re.compile(r"\b(?:MODIFY|CHANGE)\s+(?:COLUMN\s+)?\S+(?:\s+\S+)?\s+VARCHAR\s*\(", re.I),
     "extending a VARCHAR"),
    (re.compile(r"\b(?:MODIFY|CHANGE)\b[^,;]*\bNOT\s+NULL\b", re.I),
     "making a column NOT NULL"),
    (re.compile(r"\bAUTO_INCREMENT\s*=\s*\d+", re.I), "changing the AUTO_INCREMENT value"),
]

# Operations whose manual row says Permits Concurrent DML = No.
NO_CONCURRENT_DML = [
    (re.compile(r"\bADD\s+FULLTEXT\s+(?:INDEX|KEY)\b", re.I),
     "ADD FULLTEXT INDEX blocks writes for the whole build on every version"),
    (re.compile(r"\bADD\s+SPATIAL\s+(?:INDEX|KEY)\b", re.I),
     "ADD SPATIAL INDEX blocks writes for the whole build"),
    (re.compile(r"\bCONVERT\s+TO\s+CHARACTER\s+SET\b", re.I),
     "CONVERT TO CHARACTER SET is COPY on 5.7 and SHARED-at-best on 8.0"),
    (re.compile(r"\bADD\s+COLUMN\b[^;]*\bAUTO_INCREMENT\b", re.I),
     "adding an AUTO_INCREMENT column refuses concurrent DML; LOCK=SHARED is the minimum"),
    (re.compile(r"\bDROP\s+PRIMARY\s+KEY\b(?![^;]*\bADD\s+PRIMARY\s+KEY\b)", re.I),
     "DROP PRIMARY KEY on its own is COPY-only; combine it with ADD PRIMARY KEY in the same "
     "statement to get an in-place, DML-permitting rebuild"),
]

# NOT CHECKED, deliberately.
#
# "Changing the column data type" is COPY-only and therefore incompatible with
# LOCK=NONE, but a MODIFY statement does not reveal whether the type actually
# changed: `MODIFY COLUMN total DECIMAL(12,2) NOT NULL` is a *nullability*
# change (INPLACE, concurrent DML permitted) when the column is already
# DECIMAL(12,2), and a type change (COPY) when it is not. Deciding requires the
# current schema, which this checker does not read. A pattern that flagged every
# MODIFY naming a type name produced a critical false positive on the standard
# "backfill, then enforce NOT NULL" phase — see golden fixture MIG-007.
# Compare against SHOW CREATE TABLE before trusting LOCK=NONE on a MODIFY.
UNCHECKED_BY_DESIGN = {
    "type-change-vs-nullability-change": "requires the current column definition",
    "varchar-band-crossing-without-declared-charset": "requires the column's character set",
    "table-size-and-qps-risk-axes": "requires production metrics, not statement text",
}

# Partition clauses and the LOCK values 8.0 accepts for them.
PARTITION_CLAUSE = re.compile(
    r"\b(ADD|DROP|REORGANIZE|COALESCE|REBUILD|TRUNCATE|EXCHANGE|ANALYZE|CHECK|REPAIR|DISCARD|IMPORT|OPTIMIZE)\s+PARTITION\b",
    re.I,
)
PARTITION_NO_LOCK_NONE_80 = {"REORGANIZE", "COALESCE", "REBUILD", "OPTIMIZE", "DISCARD", "IMPORT"}
PARTITION_DEFAULT_ONLY_57 = {"ADD", "DROP", "REORGANIZE", "COALESCE", "REBUILD", "DISCARD", "IMPORT"}

CHARSET_BYTES = {
    "utf8mb4": 4,
    "utf8mb3": 3,
    "utf8": 3,
    "latin1": 1,
    "ascii": 1,
    "binary": 1,
    "gbk": 2,
    "gb2312": 2,
    "big5": 2,
    "ujis": 3,
    "sjis": 2,
}

ALGO_RE = re.compile(r"\bALGORITHM\s*=\s*(INSTANT|INPLACE|COPY|DEFAULT)\b", re.I)
LOCK_RE = re.compile(r"\bLOCK\s*=\s*(NONE|SHARED|EXCLUSIVE|DEFAULT)\b", re.I)


# ---------------------------------------------------------------------------
# SQL checks
# ---------------------------------------------------------------------------


def _add(findings: list[Finding], ctx: Context, seg: Segment, rel_line: int,
         check_id: str, message: str, evidence: str) -> None:
    findings.append(
        Finding(
            check_id=check_id,
            severity=CHECK_REGISTRY[check_id]["severity"],
            path=ctx.path,
            line=seg.line_offset + rel_line,
            message=message,
            evidence=norm(evidence)[:200],
        )
    )


def check_sql_segment(ctx: Context, seg: Segment, findings: list[Finding]) -> None:
    masked = mask_sql_noise(seg.text)
    v = ctx.version
    fk_off_lines = [
        i for i, ln in enumerate(masked.split("\n"))
        if re.search(r"\bforeign_key_checks\s*=\s*0\b", ln, re.I)
    ]
    fk_on_lines = [
        i for i, ln in enumerate(masked.split("\n"))
        if re.search(r"\bforeign_key_checks\s*=\s*1\b", ln, re.I)
    ]

    for start, raw_stmt in split_statements(masked):
        stmt = norm(raw_stmt)
        if not stmt:
            continue
        algo_m = ALGO_RE.search(stmt)
        algo = algo_m.group(1).upper() if algo_m else None
        lock_m = LOCK_RE.search(stmt)
        lock = lock_m.group(1).upper() if lock_m else None
        is_alter = re.match(r"^\s*ALTER\s+(?:ONLINE\s+|IGNORE\s+)?TABLE\b", stmt, re.I) is not None
        part_m = PARTITION_CLAUSE.search(stmt)

        # --- INSTANT version gates -------------------------------------------------
        if algo == "INSTANT" and lock and lock != "DEFAULT":
            # ALTER TABLE reference: "Only LOCK = DEFAULT is permitted for
            # operations that use ALGORITHM=INSTANT. The other LOCK clause
            # parameters are not applicable." LOCK=NONE reads like a stronger
            # guarantee and is in fact a rejected statement.
            _add(findings, ctx, seg, start, "MM029",
                 f"ALGORITHM=INSTANT permits only LOCK=DEFAULT; LOCK={lock} makes this statement "
                 "fail. Drop the LOCK clause entirely. INSTANT is still not lock-free — it may take "
                 "a brief exclusive metadata lock, so keep the lock_wait_timeout guard.", stmt)

        if algo == "INSTANT":
            if v < V_INSTANT_INTRODUCED:
                detail = ("MySQL 5.7 has no INSTANT algorithm at all"
                          if v < V_8_0 else
                          "the ALGORITHM=INSTANT clause was introduced in 8.0.12, so 8.0.0-8.0.11 "
                          "reject it for every operation — not only ADD COLUMN")
                _add(findings, ctx, seg, start, "MM001",
                     f"{detail}; on {fmt_version(v)} this statement fails immediately. "
                     "Use ALGORITHM=INPLACE (with LOCK=NONE where the matrix permits it).",
                     stmt)
            else:
                added_at_position = re.search(
                    r"\bADD\s+COLUMN\b[^;]*?\b(FIRST|AFTER)\b", stmt, re.I)
                if (re.search(r"\bADD\s+COLUMN\b", stmt, re.I) and added_at_position
                        and v < V_INSTANT_ANY_POSITION):
                    _add(findings, ctx, seg, start, "MM003",
                         f"INSTANT can only append at the end before 8.0.29 "
                         f"(server is {fmt_version(v)}); FIRST/AFTER needs INPLACE here.",
                         stmt)
                if re.search(r"\bDROP\s+COLUMN\b", stmt, re.I) and v < V_INSTANT_DROP_COLUMN:
                    _add(findings, ctx, seg, start, "MM004",
                         f"INSTANT DROP COLUMN requires 8.0.29+; server is {fmt_version(v)}. "
                         "ALGORITHM=INPLACE, LOCK=NONE is supported and is not a COPY.", stmt)
                is_rename = re.search(r"\bRENAME\s+COLUMN\b", stmt, re.I) or re.search(
                    r"\bCHANGE\s+(?:COLUMN\s+)?`?(\w+)`?\s+`?(\w+)`?", stmt, re.I)
                if is_rename and v < V_INSTANT_RENAME_COLUMN:
                    _add(findings, ctx, seg, start, "MM005",
                         f"INSTANT column rename requires 8.0.28+; server is {fmt_version(v)}. "
                         "Use ALGORITHM=INPLACE.", stmt)
                for pat, what in NEVER_INSTANT:
                    if pat.search(stmt):
                        _add(findings, ctx, seg, start, "MM006",
                             f"The manual lists {what} as Instant=No on every release. "
                             "ALGORITHM=INSTANT will be rejected; use INPLACE or COPY per the matrix.",
                             stmt)
                        break

        # --- Partition clause algorithm/lock support -------------------------------
        if part_m and is_alter:
            verb = part_m.group(1).upper()
            if v < V_8_0 and verb in PARTITION_DEFAULT_ONLY_57 and algo and algo != "DEFAULT":
                _add(findings, ctx, seg, start, "MM007",
                     f"On MySQL 5.7, {verb} PARTITION accepts only ALGORITHM=DEFAULT, LOCK=DEFAULT. "
                     f"ALGORITHM={algo} makes the statement fail. Omit both clauses.", stmt)
            if v >= V_8_0 and verb in PARTITION_NO_LOCK_NONE_80 and lock == "NONE":
                _add(findings, ctx, seg, start, "MM008",
                     f"{verb} PARTITION does not permit concurrent DML on 8.0; "
                     "LOCK={DEFAULT|SHARED|EXCLUSIVE} only. Writes will block — say so explicitly.",
                     stmt)

        # --- LOCK=NONE on write-blocking operations --------------------------------
        if lock == "NONE" and not part_m:
            for pat, why in NO_CONCURRENT_DML:
                if pat.search(stmt):
                    _add(findings, ctx, seg, start, "MM008",
                         f"LOCK=NONE will be rejected: {why}.", stmt)
                    break

        # --- ADD FOREIGN KEY + INPLACE --------------------------------------------
        if re.search(r"\bADD\s+(?:CONSTRAINT\s+\S+\s+)?FOREIGN\s+KEY\b", stmt, re.I) \
                and algo == "INPLACE":
            active_off = any(
                off < start and not any(off < on < start for on in fk_on_lines)
                for off in fk_off_lines
            )
            if not active_off:
                _add(findings, ctx, seg, start, "MM009",
                     "ADD FOREIGN KEY supports INPLACE only while foreign_key_checks=0; "
                     "with checks on, only COPY is supported and this statement fails. "
                     "Verify orphans yourself, then disable checks — or state ALGORITHM=COPY.",
                     stmt)

        # --- VARCHAR byte-boundary crossing ----------------------------------------
        if algo in ("INPLACE", "INSTANT"):
            for vm in re.finditer(
                r"\b(?:MODIFY|CHANGE)\s+(?:COLUMN\s+)?`?\w+`?(?:\s+`?\w+`?)?\s+VARCHAR\s*\(\s*(\d+)\s*\)"
                r"([^,;]*)", stmt, re.I):
                new_len = int(vm.group(1))
                tail = vm.group(2) or ""
                cs = None
                csm = re.search(r"CHARACTER\s+SET\s+(\w+)", tail, re.I) or \
                    re.search(r"CHARACTER\s+SET\s+(\w+)", stmt, re.I)
                if csm:
                    cs = csm.group(1).lower()
                width = CHARSET_BYTES.get(cs) if cs else None
                if width is None:
                    continue
                if new_len * width >= 256:
                    # Deliberately a WARNING, not an error. The band is decided by the
                    # *pair* of widths: VARCHAR(260)->VARCHAR(300) latin1 stays in the
                    # 2-byte band and is a legal in-place change. The old definition is
                    # not in the statement, so the checker cannot tell that apart from
                    # VARCHAR(200)->VARCHAR(300), which does require COPY.
                    _add(findings, ctx, seg, start, "MM010",
                         f"VARCHAR({new_len}) in {cs} is {new_len * width} bytes, so it needs a "
                         f"2-byte length prefix. ALGORITHM={algo} holds only if the CURRENT "
                         f"definition is also >=256 bytes; if it is below, this requires COPY. "
                         f"Confirm with SHOW CREATE TABLE.", stmt)

        # --- ALTER TABLE without an algorithm --------------------------------------
        if is_alter and algo is None:
            partition_default_only = (
                part_m is not None
                and (v < V_8_0 and part_m.group(1).upper() in PARTITION_DEFAULT_ONLY_57)
            )
            if not partition_default_only:
                _add(findings, ctx, seg, start, "MM014",
                     "ALTER TABLE without an explicit ALGORITHM: the server picks silently and may "
                     "choose COPY. State ALGORITHM=INSTANT|INPLACE|COPY.", stmt)

        # --- IF [NOT] EXISTS on an ALTER clause ------------------------------------
        if is_alter:
            for m in re.finditer(
                    r"\b(ADD|DROP|MODIFY|CHANGE)\s+(?:COLUMN\s+|INDEX\s+|KEY\s+)?"
                    r"(IF\s+NOT\s+EXISTS|IF\s+EXISTS)", stmt, re.I):
                _add(findings, ctx, seg, start, "MM026",
                     f"`{norm(m.group(0))}` is not MySQL syntax — ALTER TABLE has no "
                     "IF [NOT] EXISTS for ADD/DROP COLUMN or index (that is MariaDB). "
                     "The statement fails with a parse error. For idempotency, gate on "
                     "information_schema or on the migration framework's history table.",
                     stmt)
                break

        # --- UPDATE ... LIMIT ... OFFSET -------------------------------------------
        if re.search(r"\bUPDATE\b", stmt, re.I) and re.search(r"\bLIMIT\b\s*\d+\s*(?:OFFSET\b|,)",
                                                              stmt, re.I):
            _add(findings, ctx, seg, start, "MM012",
                 "UPDATE accepts LIMIT row_count only — 'LIMIT n OFFSET m' and 'LIMIT m, n' are "
                 "syntax errors on UPDATE. Batch by primary-key range instead.", stmt)

        # --- Irreversible drops ----------------------------------------------------
        if re.search(r"\b(?:DROP\s+COLUMN|DROP\s+TABLE)\b", stmt, re.I) and not ctx.mentions_backup:
            _add(findings, ctx, seg, start, "MM025",
                 "Irreversible DDL with no backup or retention statement anywhere in the file. "
                 "A compensating ALTER recreates an empty structure — it does not restore data.",
                 stmt)

    _check_sql_wholefile(ctx, seg, masked, findings)


def _check_sql_wholefile(ctx: Context, seg: Segment, masked: str,
                         findings: list[Finding]) -> None:
    v = ctx.version
    lines = masked.split("\n")

    # WHILE / REPEAT / LOOP outside a stored program.
    in_program = bool(re.search(
        r"\bCREATE\s+(?:DEFINER\s*=\s*\S+\s+)?(?:PROCEDURE|FUNCTION|TRIGGER|EVENT)\b",
        masked, re.I))
    if not in_program:
        for i, ln in enumerate(lines):
            if re.search(r"^\s*(?:WHILE\b.*\bDO\b|REPEAT\b|LOOP\b)", ln, re.I) or \
               re.search(r"^\s*(?:END\s+WHILE|END\s+REPEAT|END\s+LOOP|UNTIL)\b", ln, re.I):
                _add(findings, ctx, seg, i, "MM011",
                     "WHILE/REPEAT/LOOP are compound statements valid only inside a stored program. "
                     "Outside CREATE PROCEDURE/FUNCTION/TRIGGER/EVENT this is ERROR 1064 — the "
                     "script has never run. Use a stored procedure or an external driver.", ln)
                break

    for i, ln in enumerate(lines):
        if re.search(r"\bsql_log_bin\s*=\s*(?:0|OFF)\b", ln, re.I):
            _add(findings, ctx, seg, i, "MM013",
                 "Disabling sql_log_bin stops the write replicating: replicas diverge silently, "
                 "PITR replays without it, and binlog-reading tools miss it. Requires SUPER / "
                 "SYSTEM_VARIABLES_ADMIN. Never a default — needs a per-host runbook.", ln)
        if re.search(r"\bSHOW\s+REPLICA\s+STATUS\b", ln, re.I) and v < V_REPLICA_TERMINOLOGY:
            _add(findings, ctx, seg, i, "MM021",
                 f"SHOW REPLICA STATUS was introduced in 8.0.22; on {fmt_version(v)} use "
                 "SHOW SLAVE STATUS.", ln)
        if re.search(r"\bSHOW\s+SLAVE\s+STATUS\b", ln, re.I) and v >= V_SLAVE_REMOVED:
            _add(findings, ctx, seg, i, "MM022",
                 f"SHOW SLAVE STATUS was removed in 8.4; on {fmt_version(v)} use "
                 "SHOW REPLICA STATUS.", ln)
        if re.search(r"\bperformance_schema\.data_lock(?:s|_waits)\b", ln, re.I) and v < V_8_0:
            _add(findings, ctx, seg, i, "MM023",
                 f"performance_schema.data_locks is 8.0+; on {fmt_version(v)} use "
                 "INFORMATION_SCHEMA.INNODB_LOCKS / INNODB_LOCK_WAITS.", ln)
        if re.search(r"\bSeconds_Behind_Source\b", ln) and v < V_REPLICA_TERMINOLOGY:
            _add(findings, ctx, seg, i, "MM024",
                 f"Seconds_Behind_Source exists from 8.0.22; on {fmt_version(v)} the column is "
                 "Seconds_Behind_Master.", ln)
        if re.search(r"\bSeconds_Behind_Master\b", ln) and v >= V_SLAVE_REMOVED:
            _add(findings, ctx, seg, i, "MM024",
                 f"Seconds_Behind_Master is gone on {fmt_version(v)}; use Seconds_Behind_Source.",
                 ln)
        if re.search(r"\bLIMIT\b\s+\d+\s+OFFSET\b|\bOFFSET\s+@?\w+", ln, re.I) and \
                re.search(r"\bUPDATE\b|\bbackfill\b", masked, re.I):
            _add(findings, ctx, seg, i, "MM016",
                 "LIMIT/OFFSET paging rescans and discards all preceding rows each iteration "
                 "(O(n^2)). Batch by primary-key range.", ln)

    plain = unmask_to_space(masked)
    plain_lines = plain.split("\n")
    first_ddl = next(
        (i for i, ln in enumerate(plain_lines)
         if re.match(r"^\s*(?:ALTER\s+TABLE|CREATE\s+INDEX|DROP\s+INDEX)\b", ln, re.I)),
        None)
    if first_ddl is not None:
        # A guard set *after* the DDL protects nothing, so compare positions
        # instead of asking "does this file mention lock_wait_timeout anywhere".
        guard_lines = [
            i for i, ln in enumerate(plain_lines)
            if re.search(r"\bSET\s+(?:SESSION\s+)?lock_wait_timeout\s*=", ln, re.I)
        ]
        # pt-osc sets the variable through --set-vars rather than a SET statement.
        covered_by_tool_flag = ctx.has_set_vars_guard
        if not any(i < first_ddl for i in guard_lines) and not covered_by_tool_flag:
            why = ("the `SET SESSION lock_wait_timeout` in this file appears at line "
                   f"{seg.line_offset + guard_lines[0]}, AFTER the first DDL, so it does not "
                   "apply to it"
                   if guard_lines else
                   "no `SET SESSION lock_wait_timeout` guard precedes the DDL")
            _add(findings, ctx, seg, first_ddl, "MM015",
                 f"{why}. A long-running transaction holding the MDL will queue this DDL, and "
                 "every later query queues behind it.", plain_lines[first_ddl])


# ---------------------------------------------------------------------------
# Shell checks
# ---------------------------------------------------------------------------

_REPLICA_HOSTNAME = re.compile(r"replica|slave|reader|-ro\b|readonly|standby", re.I)


def _join_continuations(text: str) -> list[tuple[int, str]]:
    """Collapse backslash-continued shell lines into single logical lines."""
    out: list[tuple[int, str]] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        start = i
        buf = lines[i]
        while buf.rstrip().endswith("\\") and i + 1 < len(lines):
            buf = buf.rstrip()[:-1] + " " + lines[i + 1]
            i += 1
        out.append((start, buf))
        i += 1
    return out


def check_shell_segment(ctx: Context, seg: Segment, findings: list[Finding]) -> None:
    for rel, cmd in _join_continuations(seg.text):
        stripped = cmd.lstrip()
        if stripped.startswith("#"):
            continue
        if re.search(r"\bgh-ost\b", cmd):
            _check_gh_ost(ctx, seg, rel, cmd, findings)
        if re.search(r"\bpt-online-schema-change\b", cmd):
            _check_pt_osc(ctx, seg, rel, cmd, findings)


def _check_gh_ost(ctx: Context, seg: Segment, rel: int, cmd: str,
                  findings: list[Finding]) -> None:
    host_m = re.search(r"--host[=\s]+([^\s\\\"']+)", cmd)
    host = host_m.group(1) if host_m else None
    allow_on_master = "--allow-on-master" in cmd

    if allow_on_master:
        on_replica_mode = "--migrate-on-replica" in cmd or "--test-on-replica" in cmd
        if on_replica_mode or (host and _REPLICA_HOSTNAME.search(host)):
            _add(findings, ctx, seg, rel, "MM017",
                 "--allow-on-master is the opt-in for pointing gh-ost AT THE MASTER. gh-ost's "
                 f"default mode already connects to a replica and migrates on the master"
                 + (f" (--host={host} looks like a replica)" if host else "")
                 + ". Drop the flag, or point --host at the master.", cmd)

    for flag, why in (
        ("--initially-drop-old-table",
         "the _old table from a prior run is often the only surviving pre-migration copy"),
        ("--initially-drop-ghost-table",
         "the ghost table may hold hours of copied work that --resume could continue"),
        ("--ok-to-drop-table",
         "dropping the old table removes the post-cut-over revert path (--revert needs it)"),
    ):
        if flag in cmd:
            _add(findings, ctx, seg, rel, "MM018",
                 f"{flag} is disabled upstream on purpose: {why}. Inspect leftovers by hand and "
                 "pass this for one deliberate run, not in a reusable template.", cmd)


def _check_pt_osc(ctx: Context, seg: Segment, rel: int, cmd: str,
                  findings: list[Finding]) -> None:
    if "--null-to-not-null" in cmd:
        _add(findings, ctx, seg, rel, "MM019",
             "--null-to-not-null converts existing NULLs to the type default (0, '') with no "
             "record of which rows changed. Backfill deliberately, then add NOT NULL.", cmd)
    if "--dry-run" not in cmd and "--execute" not in cmd:
        _add(findings, ctx, seg, rel, "MM020",
             "pt-online-schema-change requires --dry-run or --execute; without one it refuses to "
             "act, and a runbook that omits both has not been rehearsed.", cmd)
    if "--preserve-triggers" in cmd:
        # Upstream: "--preserve-triggers cannot be used with these other parameters,
        # --no-drop-triggers, --no-drop-old-table and --no-swap-tables since
        # --preserve-triggers implies that the old triggers should be deleted and
        # recreated in the new table."
        clashes = [f for f in ("--no-drop-triggers", "--no-drop-old-table", "--no-swap-tables")
                   if f in cmd]
        if clashes:
            _add(findings, ctx, seg, rel, "MM027",
                 f"--preserve-triggers cannot be combined with {', '.join(clashes)}: it must drop "
                 "and recreate the original triggers, which those flags prevent. Preserving the "
                 "rollback copy and preserving triggers are mutually exclusive in pt-osc — pick "
                 "one deliberately, or use gh-ost >=1.1.8 with --include-triggers.", cmd)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


_BACKUP_WORD = re.compile(
    r"\b(backups?|backed[- ]up|mysqldump|snapshots?|retention|PITR|point[- ]in[- ]time|restore)\b",
    re.I)
# Words that turn a backup mention into its opposite. "-- no backup exists"
# must not satisfy the same check as "-- mysqldump taken, 30-day retention".
_NEGATION = re.compile(
    r"\b(no|not|without|missing|lack(?:s|ing)?|absent|none|never|skip(?:ped|ping)?|"
    r"unavailable|todo|tbd|forgot(?:ten)?|isn't|aren't|wasn't|cannot|can't|didn't|don't)\b",
    re.I)


def version_finding(version: Version, path: str = "(run)") -> Finding | None:
    """MM028 — a run-level check, emitted once per invocation rather than per file.

    Kept as its own function so it is exercisable from tests exactly like the
    per-statement checks, instead of being reachable only through main().
    """
    coverage, why = version_coverage(version)
    if coverage == "verified":
        return None
    return Finding(
        check_id="MM028",
        severity=CHECK_REGISTRY["MM028"]["severity"],
        path=path, line=0,
        message=(f"MySQL {fmt_version(version)} is {why}. Every algorithm and lock verdict below "
                 "inherits that uncertainty — confirm against this server's own manual, or run "
                 "scripts/verify_against_server.sh against it. Use --fail-on warning to make an "
                 "unverified version a hard stop."),
        evidence=f"--mysql-version {fmt_version(version)}")


def _asserts_backup(text: str) -> bool:
    """True when the text positively claims a backup exists.

    Scans clause-by-clause so a negation attaches only to the backup mention it
    actually governs: a file may legitimately say "no maintenance window" in one
    sentence and "mysqldump retained" in another.
    """
    found_positive = False
    for line in text.split("\n"):
        for clause in re.split(r"[;.,()\[\]]|--|\bbut\b|\byet\b|\bhowever\b", line):
            if not _BACKUP_WORD.search(clause):
                continue
            if _NEGATION.search(clause):
                continue  # this mention is negated; it does not count
            found_positive = True
    return found_positive


def lint_text(path: str, text: str, version: Version,
              skip_negative: bool = False) -> list[Finding]:
    p = pathlib.Path(path)
    segments = extract_segments(p, text)
    ctx = Context(path=path, version=version, segments=segments)
    joined = "\n".join(s.text for s in segments)
    ctx.has_set_vars_guard = bool(
        re.search(r"--set-vars[^\s]*lock_wait_timeout", joined, re.I))
    ctx.mentions_backup = _asserts_backup(text)

    findings: list[Finding] = []
    for seg in segments:
        if skip_negative and seg.negative:
            continue
        if seg.lang == "sql":
            check_sql_segment(ctx, seg, findings)
        elif seg.lang == "bash":
            check_shell_segment(ctx, seg, findings)
    findings.sort(key=lambda f: (f.line, f.check_id))
    return findings


@dataclass(frozen=True)
class BaselineEntry:
    """One accepted finding, identified by content rather than by line number."""

    check_id: str
    path_suffix: str
    evidence_substring: str

    def matches(self, f: Finding) -> bool:
        return (
            f.check_id == self.check_id
            and f.path.replace("\\", "/").endswith(self.path_suffix)
            and self.evidence_substring.lower() in f.evidence.lower()
        )

    def __str__(self) -> str:
        return f"{self.check_id}  {self.path_suffix}  [{self.evidence_substring}]"


def load_baseline(path: pathlib.Path) -> list[BaselineEntry]:
    """Parse an allowlist of accepted findings.

    Each entry is `CHECK_ID | path-suffix | evidence-substring`, with `#` comments
    carrying the justification.

    Deliberately NOT keyed on line number: any edit above the exempted block would
    silently invalidate the entry, and a baseline that quietly stops applying is
    worse than none. Matching on the statement text means the exemption follows
    the code it was written for, and disappears when that code does.

    This is an allowlist, not a severity switch: findings outside it still count
    at their own severity, so a newly introduced warning fails the run instead of
    blending into an accepted total.
    """
    entries: list[BaselineEntry] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 3 or not all(parts):
            raise ValueError(
                f"{path}:{lineno}: expected 'CHECK_ID | path-suffix | evidence-substring', "
                f"got {raw!r}")
        entries.append(BaselineEntry(*parts))
    return entries


# Extensions the checker can read. Flyway (`V1__x.sql`) and golang-migrate
# (`1_x.up.sql`) both land in .sql; `.ddl` is common in hand-rolled and
# Oracle-influenced repos. Liquibase XML/YAML/JSON changelogs are NOT here — see
# UNPARSEABLE_FORMATS.
SCANNED_EXTENSIONS = (".sql", ".ddl", ".mysql", ".md", ".markdown", ".sh", ".bash")

# Formats that hold DDL this checker cannot reach. Reported by name so a clean
# run over such a directory is not mistaken for a clean migration set.
UNPARSEABLE_FORMATS = {
    ".xml": "Liquibase XML changelog",
    ".yaml": "Liquibase YAML changelog",
    ".yml": "Liquibase YAML changelog",
    ".json": "Liquibase JSON changelog",
    ".go": "Go source (golang-migrate embedded SQL, or a programmatic migration)",
    ".java": "Java source (Liquibase/Flyway callback or programmatic migration)",
    ".py": "Python source (Alembic-style programmatic migration)",
}


def iter_files(paths: Sequence[str]) -> tuple[list[pathlib.Path], dict[str, int]]:
    """Return (files to scan, {format description: count}) for skipped DDL carriers."""
    files: list[pathlib.Path] = []
    skipped: dict[str, int] = {}
    for raw in paths:
        p = pathlib.Path(raw)
        if p.is_dir():
            for child in sorted(p.rglob("*")):
                if not child.is_file():
                    continue
                suffix = child.suffix.lower()
                if suffix in SCANNED_EXTENSIONS:
                    files.append(child)
                elif suffix in UNPARSEABLE_FORMATS:
                    desc = UNPARSEABLE_FORMATS[suffix]
                    skipped[desc] = skipped.get(desc, 0) + 1
        else:
            suffix = p.suffix.lower()
            if suffix in UNPARSEABLE_FORMATS:
                # Naming the file explicitly does not make it parseable. Scanning a
                # changelog as if it were SQL reports "clean" about DDL that is
                # sitting inside JSON/XML string values, masked by the quoting —
                # a silent green on a file nobody checked.
                desc = UNPARSEABLE_FORMATS[suffix]
                skipped[desc] = skipped.get(desc, 0) + 1
            else:
                # Unknown extension: the caller has asserted this is a migration,
                # so read it as SQL.
                files.append(p)
    return files, skipped


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="migration files or directories")
    ap.add_argument("--mysql-version",
                    help="exact target server version, e.g. 8.0.29 or 5.7.40")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--fail-on", choices=("critical", "warning", "never"), default="critical")
    ap.add_argument("--skip-negative-examples", action="store_true",
                    help="in Markdown, ignore fenced blocks labelled WRONG/INVALID/etc")
    ap.add_argument("--baseline", metavar="FILE",
                    help="allowlist of accepted findings, one "
                         "'CHECK_ID | path-suffix | evidence-substring' per line (# comments "
                         "allowed). Listed findings are suppressed; anything NOT listed still "
                         "counts, so a new warning cannot slip in unnoticed. A baseline entry "
                         "that no longer matches anything is itself an error.")
    ap.add_argument("--list-checks", action="store_true",
                    help="print the declared check registry and exit")
    args = ap.parse_args(argv)

    if args.list_checks:
        for cid in sorted(CHECK_REGISTRY):
            meta = CHECK_REGISTRY[cid]
            print(f"{cid}  {meta['severity']:<8}  {meta['title']}")
        return 0

    if not args.paths:
        ap.error("at least one path is required (or use --list-checks)")
    if not args.mysql_version:
        ap.error("--mysql-version is required")
    try:
        version = parse_version(args.mysql_version)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    findings: list[Finding] = []
    coverage, _ = version_coverage(version)
    run_level = version_finding(version, args.paths[0])
    if run_level:
        findings.append(run_level)

    files, skipped_formats = iter_files(args.paths)
    # An unread migration carrier is a finding, not a footnote. Printing it while
    # returning 0 let a directory of Liquibase changelogs pass CI as a clean run.
    for desc, count in sorted(skipped_formats.items()):
        findings.append(Finding(
            check_id="MM030",
            severity=CHECK_REGISTRY["MM030"]["severity"],
            path=args.paths[0], line=0,
            message=(f"{count} file(s) of type '{desc}' were NOT read — this checker parses SQL, "
                     "and DDL inside them is unreviewed. Extract the SQL (e.g. `liquibase "
                     "updateSQL`) and lint that, or state in the review that these were not "
                     "covered."),
            evidence=desc))
    scanned = 0
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"error: cannot read {path}: {exc}", file=sys.stderr)
            return 2
        scanned += 1
        findings.extend(lint_text(str(path), text, version, args.skip_negative_examples))

    stale_baseline: list[str] = []
    n_suppressed = 0
    if args.baseline:
        try:
            allowed = load_baseline(pathlib.Path(args.baseline))
        except (OSError, ValueError) as exc:
            print(f"error: cannot read baseline {args.baseline}: {exc}", file=sys.stderr)
            return 2
        stale_baseline = sorted(
            str(e) for e in allowed if not any(e.matches(f) for f in findings))
        before = len(findings)
        findings = [f for f in findings if not any(e.matches(f) for e in allowed)]
        n_suppressed = before - len(findings)

    if args.format == "json":
        print(json.dumps({
            "mysql_version": fmt_version(version),
            "version_coverage": coverage,
            "files_scanned": scanned,
            "unparseable_files_skipped": skipped_formats,
            "findings": [f.as_dict() for f in findings],
        }, indent=2))
    else:
        for f in findings:
            print(f"{f.path}:{f.line}: {f.severity.upper()} [{f.check_id}] {f.message}")
            print(f"    | {f.evidence}")
        n_crit = sum(1 for f in findings if f.severity == CRITICAL)
        n_warn = sum(1 for f in findings if f.severity == WARNING)
        print(f"\n{scanned} file(s) scanned against MySQL {fmt_version(version)} "
              f"[{coverage}]: {n_crit} critical, {n_warn} warning"
              + (f" ({n_suppressed} accepted finding(s) suppressed by baseline)"
                 if args.baseline else ""))
        if skipped_formats:
            print("\nNot scanned — this checker cannot read these, and they may contain DDL:")
            for desc, count in sorted(skipped_formats.items()):
                print(f"  {count:>3} x {desc}")
            print("  Extract the SQL (e.g. `liquibase updateSQL`) and lint that instead.")
        if scanned == 0:
            print("\nWARNING: no files were scanned. Directory mode reads "
                  f"{', '.join(SCANNED_EXTENSIONS)}. A file named explicitly is read whatever its "
                  "extension UNLESS the extension is a known-unparseable carrier "
                  f"({', '.join(sorted(UNPARSEABLE_FORMATS))}) — naming one of those does not make "
                  "it parseable, so it is reported unread instead.")

    if stale_baseline:
        print("\nerror: baseline entries no longer match any finding — the underlying issue was "
              "fixed or moved, so the exemption must be removed:", file=sys.stderr)
        for k in stale_baseline:
            print(f"  {k}", file=sys.stderr)
        return 1

    if args.fail_on == "never":
        return 0
    threshold = {CRITICAL: (CRITICAL,), WARNING: (CRITICAL, WARNING)}[args.fail_on]
    return 1 if any(f.severity in threshold for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Deterministic safety linter for PostgreSQL migration SQL.

Every rule here is grounded in the PostgreSQL 17 documentation source
(``doc/src/sgml``). The grounding is declared as data in ``RULES`` below so the
test suite can assert that each rule has both a stated source and at least one
violating input -- a docstring claiming coverage is unfalsifiable, a table of
CHECKED/UNCHECKED entries is not.

Usage:
    lint_migration.py FILE [FILE ...] [--json] [--pg-version N] [--rows N]
    lint_migration.py --self-test
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import re
import sys

# ---------------------------------------------------------------------------
# Rule registry -- coverage declared as data, not prose.
# ---------------------------------------------------------------------------

SEV_CRITICAL = "critical"
SEV_STANDARD = "standard"
SEV_HYGIENE = "hygiene"


@dataclasses.dataclass(frozen=True)
class Rule:
    code: str
    severity: str
    title: str
    source: str  # documentation page that states the underlying behaviour


RULES: tuple[Rule, ...] = (
    Rule("PG001", SEV_CRITICAL, "SET LOCAL guard outside a transaction block is a no-op",
         "set.sgml - LOCAL"),
    Rule("PG002", SEV_CRITICAL, "CONCURRENTLY statement inside a transaction block",
         "create_index.sgml / drop_index.sgml - CONCURRENTLY"),
    Rule("PG003", SEV_CRITICAL, "index built without CONCURRENTLY",
         "create_index.sgml - Notes"),
    Rule("PG004", SEV_CRITICAL, "DDL with no lock_timeout guard",
         "config.sgml - lock_timeout"),
    Rule("PG005", SEV_CRITICAL, "finite statement_timeout around a concurrent build",
         "config.sgml - statement_timeout"),
    Rule("PG006", SEV_STANDARD, "ALTER TABLE mixes lock classes in one statement",
         "alter_table.sgml - Description"),
    Rule("PG007", SEV_STANDARD, "ADD CONSTRAINT IF NOT EXISTS is not valid syntax",
         "alter_table.sgml - ADD table_constraint"),
    Rule("PG008", SEV_STANDARD, "constraint existence guard not scoped by conrelid",
         "catalog-pg-constraint.sgml - conname"),
    Rule("PG009", SEV_STANDARD, "constraint added without NOT VALID",
         "alter_table.sgml - NOT VALID"),
    Rule("PG010", SEV_STANDARD, "rewriting ALTER COLUMN TYPE without a tool",
         "alter_table.sgml - Notes"),
    Rule("PG011", SEV_STANDARD, "explicit insert into GENERATED ALWAYS identity",
         "insert.sgml - OVERRIDING SYSTEM VALUE"),
    Rule("PG012", SEV_STANDARD, "LIMIT/OFFSET backfill",
         "skill rule - keyset batching"),
    Rule("PG013", SEV_STANDARD, "ADD COLUMN with a volatile DEFAULT rewrites the table",
         "alter_table.sgml - Notes"),
    Rule("PG014", SEV_STANDARD, "max()-based backfill resume point skips unprocessed rows",
         "skill rule - resume point"),
    Rule("PG018", SEV_STANDARD, "SET NOT NULL without a proving CHECK forces a full scan",
         "alter_table.sgml - SET NOT NULL"),
    Rule("PG019", SEV_CRITICAL, "lock_timeout set to a value that disables the guard",
         "config.sgml - lock_timeout (zero disables the timeout)"),
    Rule("PG020", SEV_STANDARD, "ALTER COLUMN TYPE whose source type is not statically known",
         "alter_table.sgml - Notes (binary coercibility depends on BOTH types)"),
    Rule("PG021", SEV_STANDARD, "NOT VALID foreign key on a partitioned table below PG 18",
         "alter_table.sgml - NOT VALID / partitioned tables"),
    Rule("PG015", SEV_HYGIENE, "REINDEX without CONCURRENTLY",
         "reindex.sgml - Notes"),
    Rule("PG016", SEV_HYGIENE, "VACUUM FULL instead of pg_repack",
         "vacuum.sgml - FULL"),
    Rule("PG017", SEV_HYGIENE, "no ANALYZE after a bulk backfill",
         "skill rule - post-migration statistics"),
    Rule("PG022", SEV_HYGIENE, "idempotency guard matches on name without comparing the definition",
         "catalog-pg-constraint.sgml / create_index.sgml - IF NOT EXISTS"),
)

RULES_BY_CODE = {r.code: r for r in RULES}

# Properties this checker CANNOT establish, declared as data so the limitation is
# emitted with every result instead of living in a docstring nobody reads.
#
# The reason this list exists: PG022's "does this guard verify the definition" test was
# bypassed three times in review -- fetch-without-branching, RAISE NOTICE instead of
# RAISE EXCEPTION, and a bare SELECT of indexdef. Each fix narrowed the hole; none
# closed it, because a static reader cannot decide whether a comparison compares the
# right thing. So "0 findings" must never be reported as "verified", and the tool says
# so itself rather than relying on the reader to know.
UNPROVABLE: tuple[str, ...] = (
    "an idempotency guard actually compares the definition you intend (PG022 checks "
    "for the SHAPE of a check -- fetch, compare, RAISE EXCEPTION -- not its meaning)",
    "a type change is safe when the source type is not declared in this input (PG020)",
    "row counts, table sizes, or how long any lock will be held",
    "anything about the live schema: existing constraints, indexes, partitioning, "
    "replication, RLS policies, or installed extension versions",
    "whether a migration framework wraps this file in a transaction "
    "(pass --transaction-mode)",
)


@dataclasses.dataclass
class Finding:
    code: str
    severity: str
    line: int
    message: str
    statement: str

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


# ---------------------------------------------------------------------------
# Statement splitting -- dollar-quote aware.
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class Statement:
    text: str
    line: int
    in_transaction: bool

    @property
    def norm(self) -> str:
        """Comment-stripped, whitespace-collapsed, uppercased text."""
        return _normalize(self.text)


def _strip_comments(sql: str) -> str:
    """Remove -- and /* */ comments without touching dollar-quoted bodies."""
    out: list[str] = []
    i, n = 0, len(sql)
    tag: str | None = None
    while i < n:
        if tag:
            if sql.startswith(tag, i):
                out.append(tag)
                i += len(tag)
                tag = None
            else:
                out.append(sql[i])
                i += 1
            continue
        m = re.match(r"\$[A-Za-z_0-9]*\$", sql[i:])
        if m:
            tag = m.group(0)
            out.append(tag)
            i += len(tag)
            continue
        if sql.startswith("--", i):
            j = sql.find("\n", i)
            i = n if j == -1 else j
            continue
        if sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        if sql[i] == "'":
            j = i + 1
            while j < n:
                if sql[j] == "'" and (j + 1 >= n or sql[j + 1] != "'"):
                    break
                j += 2 if sql[j] == "'" else 1
            out.append(sql[i:min(j + 1, n)])
            i = j + 1
            continue
        out.append(sql[i])
        i += 1
    return "".join(out)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", _strip_comments(text)).strip().upper()


def split_statements(sql: str, initial_depth: int = 0) -> list[Statement]:
    """Split on ';' while respecting dollar-quoted blocks and string literals.

    Dollar-quoted bodies (DO $$ ... $$) contain internal semicolons; splitting on
    them would tear a DO block apart and hide every guard inside it.

    ``initial_depth=1`` models a migration framework that opens a transaction around
    the whole file (Flyway, golang-migrate, Alembic all do by default). The BEGIN is
    not in the text, so it cannot be inferred -- it has to be declared by the caller.
    """
    stmts: list[Statement] = []
    buf: list[str] = []
    line = 1
    start_line: int | None = None   # set on the first non-blank char of a statement
    depth = initial_depth
    i, n = 0, len(sql)
    tag: str | None = None

    def flush() -> str:
        """Emit the buffered statement; return its normalized text ('' if blank)."""
        nonlocal buf, start_line
        raw = "".join(buf)
        buf = []
        anchored, start_line = start_line, None
        # A chunk that normalizes to nothing (blank, or comments only) is not a
        # statement -- otherwise a trailing comment block becomes a phantom statement.
        if not _normalize(raw):
            return ""
        stmts.append(Statement(raw.strip(), anchored or line, depth > 0))
        return stmts[-1].norm

    def mark() -> None:
        """Anchor the statement's reported line at its first non-blank character."""
        nonlocal start_line
        if start_line is None:
            start_line = line

    while i < n:
        ch = sql[i]
        if ch == "\n":
            line += 1
        if tag:
            buf.append(ch)
            if sql.startswith(tag, i):
                buf.pop()
                buf.append(tag)
                i += len(tag)
                tag = None
                continue
            i += 1
            continue
        m = re.match(r"\$[A-Za-z_0-9]*\$", sql[i:])
        if m:
            mark()
            tag = m.group(0)
            buf.append(tag)
            i += len(tag)
            continue
        if sql.startswith("--", i):
            j = sql.find("\n", i)
            seg = sql[i:] if j == -1 else sql[i:j]
            buf.append(seg)
            i = n if j == -1 else j
            continue
        if sql.startswith("/*", i):
            # Buffer verbatim (so _normalize strips it) but never let an enclosed
            # ';' or quote be treated as syntax.
            j = sql.find("*/", i + 2)
            end = n if j == -1 else j + 2
            seg = sql[i:end]
            line += seg.count("\n")
            buf.append(seg)
            i = end
            continue
        if ch == "'":
            mark()
            j = i + 1
            while j < n:
                if sql[j] == "'" and (j + 1 >= n or sql[j + 1] != "'"):
                    break
                if sql[j] == "\n":
                    line += 1
                j += 2 if sql[j] == "'" else 1
            buf.append(sql[i:min(j + 1, n)])
            i = j + 1
            continue
        if ch == ";":
            # transaction depth transitions take effect after the statement
            last = flush()
            if re.match(r"^(BEGIN|START TRANSACTION)\b", last):
                depth += 1
            elif re.match(r"^(COMMIT|ROLLBACK|END)\b", last):
                depth = max(0, depth - 1)
            i += 1
            continue
        if not ch.isspace():
            mark()
        buf.append(ch)
        i += 1
    flush()
    return stmts


# ---------------------------------------------------------------------------
# Classification helpers -- allow-list the safe shape.
# ---------------------------------------------------------------------------

CONCURRENTLY_RE = re.compile(
    r"^(CREATE\s+(UNIQUE\s+)?INDEX\s+CONCURRENTLY"
    r"|DROP\s+INDEX\s+CONCURRENTLY"
    r"|REINDEX\s+\w+\s+CONCURRENTLY"
    r"|REINDEX\s+CONCURRENTLY"
    r"|ALTER\s+TABLE\s+.*DETACH\s+PARTITION\s+.*CONCURRENTLY)"
)

# Any statement that takes a lock on an *existing* relation, and therefore needs a
# lock_timeout guard. Keyed on "does it lock something already in production", not on a
# short hand-picked list -- the trigger text promises coverage of any production DDL.
DDL_RE = re.compile(
    r"^(ALTER\s+(TABLE|INDEX|TYPE|SEQUENCE|VIEW|MATERIALIZED\s+VIEW|SCHEMA)"
    r"|CREATE\s+(UNIQUE\s+)?INDEX"
    r"|DROP\s+(TABLE|INDEX|VIEW|MATERIALIZED\s+VIEW|SEQUENCE|TYPE|SCHEMA|TRIGGER)"
    r"|REFRESH\s+MATERIALIZED\s+VIEW"
    r"|REINDEX|TRUNCATE|VACUUM|CLUSTER|LOCK\s+TABLE)\b")

# lock_timeout / statement_timeout literal -> milliseconds. A bare number is ms.
_DURATION_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*(US|MS|S|MIN|H|D)?$")
_UNIT_MS = {"US": 0.001, "MS": 1.0, "S": 1000.0, "MIN": 60000.0,
            "H": 3600000.0, "D": 86400000.0}


_STRINGY = frozenset({"VARCHAR", "TEXT", "BPCHAR"})

# Type-name aliases, so `int`/`integer`/`int4` classify identically.
_TYPE_ALIASES = {
    "INTEGER": "INT4", "INT": "INT4", "SMALLINT": "INT2", "BIGINT": "INT8",
    "CHARACTER VARYING": "VARCHAR", "CHARACTER": "BPCHAR", "CHAR": "BPCHAR",
    "BIT VARYING": "VARBIT", "DOUBLE PRECISION": "FLOAT8", "REAL": "FLOAT4",
    "BOOLEAN": "BOOL", "DECIMAL": "NUMERIC",
    "TIMESTAMP WITH TIME ZONE": "TIMESTAMPTZ",
    "TIMESTAMP WITHOUT TIME ZONE": "TIMESTAMP",
    "TIME WITH TIME ZONE": "TIMETZ", "TIME WITHOUT TIME ZONE": "TIME",
}

# Types reachable by a binary-coercible cast FROM SOME OTHER TYPE. Generated from a
# live server -- this is not a guess:
#
#   SELECT t.typname, string_agg(s.typname, ',')
#     FROM pg_cast c JOIN pg_type s ON s.oid=c.castsource
#                    JOIN pg_type t ON t.oid=c.casttarget
#    WHERE c.castmethod = 'b' GROUP BY 1;
#
# Identical output on 14.23 and 18.4. A target OUTSIDE this set cannot be reached
# without a rewrite from any source at all, so `TYPE bigint` is provably a rewrite
# even when the source type is unknown. A target INSIDE it is genuinely undecidable
# without the source -- that is what PG020 reports.
_BINARY_COERCIBLE_TARGETS = frozenset({
    "BIT", "BPCHAR", "BYTEA", "INET", "INT4", "OID", "TEXT", "VARBIT", "VARCHAR",
    "REGCLASS", "REGCOLLATION", "REGCONFIG", "REGDICTIONARY", "REGNAMESPACE",
    "REGOPER", "REGOPERATOR", "REGPROC", "REGPROCEDURE", "REGROLE", "REGTYPE",
})

# Built-in scalar types this checker recognises. A name outside this set is a domain,
# enum, or user-defined type whose coercibility cannot be reasoned about statically,
# so it routes to PG020 rather than to a confident verdict.
_KNOWN_BUILTIN_TYPES = _BINARY_COERCIBLE_TARGETS | frozenset({
    "INT2", "INT8", "FLOAT4", "FLOAT8", "NUMERIC", "MONEY", "BOOL",
    "DATE", "TIME", "TIMETZ", "TIMESTAMP", "TIMESTAMPTZ", "INTERVAL",
    "UUID", "JSON", "JSONB", "XML", "CIDR", "MACADDR", "MACADDR8",
    "POINT", "LINE", "LSEG", "BOX", "PATH", "POLYGON", "CIRCLE",
    "TSVECTOR", "TSQUERY", "INT4RANGE", "INT8RANGE", "NUMRANGE",
    "TSRANGE", "TSTZRANGE", "DATERANGE", "SERIAL", "BIGSERIAL",
})

# Words that begin a table-level constraint rather than a column definition.
_NOT_A_COLUMN = ("PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT", "EXCLUDE", "LIKE")


def _column_decls(body: str) -> list[tuple[str, str]]:
    """Extract (column, declared type) pairs from a CREATE TABLE body.

    Best-effort and deliberately conservative: a declaration this cannot parse simply
    leaves the column's type unknown, which routes the later type change to PG020
    ("cannot prove") instead of to a wrong verdict.
    """
    parts, buf, depth = [], [], 0
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    if "".join(buf).strip():
        parts.append("".join(buf).strip())

    out = []
    for p in parts:
        m = re.match(r"^(\w+)\s+([A-Z][A-Z ]*(?:\(\s*\d+\s*(?:,\s*\d+\s*)?\))?)", p)
        if m and m.group(1).upper() not in _NOT_A_COLUMN:
            out.append((m.group(1), m.group(2).strip()))
    return out


def _parse_type(t: str) -> tuple[str, int | None]:
    """Split a SQL type into (canonical base name, first length modifier)."""
    t = re.sub(r"\s+", " ", t.strip().upper())
    m = re.match(r"^([A-Z][A-Z ]*?)\s*(?:\(\s*(\d+)\s*(?:,\s*\d+\s*)?\))?$", t)
    if not m:
        return t, None
    base = m.group(1).strip()
    return _TYPE_ALIASES.get(base, base), int(m.group(2)) if m.group(2) else None


def _timeout_ms(raw: str) -> float | None:
    """Parse a timeout GUC value to milliseconds.

    Returns None when the value is not a literal this checker can evaluate (a
    variable, an expression). An unevaluable value is never scored as a working
    guard -- the caller falls through to PG004 rather than assuming it is fine.

    ``DEFAULT`` resolves to 0 for both GUCs, i.e. *disabled*, so it is returned
    as 0 rather than as unknown.
    """
    v = raw.strip().rstrip(";").strip("'\"").upper()
    if v == "DEFAULT":
        return 0.0
    m = _DURATION_RE.match(v)
    if not m:
        return None
    return float(m.group(1)) * _UNIT_MS[m.group(2) or "MS"]

# Bulk data movement, in any of the shapes a backfill is actually written in. Matching
# only "^UPDATE" misses the CTE-led keyset form this skill itself recommends.
BULK_WRITE_RE = re.compile(
    r"^(UPDATE\s|DELETE\s+FROM\s)"
    r"|^WITH\b.*\b(UPDATE\s|INSERT\s+INTO\s|DELETE\s+FROM\s)"
    r"|^INSERT\s+INTO\b.*\bSELECT\b", re.S)

VOLATILE_DEFAULTS = ("RANDOM()", "CLOCK_TIMESTAMP()", "GEN_RANDOM_UUID()",
                     "UUID_GENERATE_V4()", "TIMEOFDAY()", "NEXTVAL(")

# Subcommand -> lock class. Only ADD FOREIGN KEY is ShareRowExclusive; everything
# else in an ALTER TABLE defaults to AccessExclusive unless documented otherwise.
LOW_LOCK_SUBCMD = re.compile(r"ADD\s+(CONSTRAINT\s+\w+\s+)?FOREIGN\s+KEY")
SUE_LOCK_SUBCMD = re.compile(r"(VALIDATE\s+CONSTRAINT|SET\s+STATISTICS|CLUSTER\s+ON"
                             r"|SET\s+\(\s*(FILLFACTOR|AUTOVACUUM|TOAST|PARALLEL_WORKERS))")


def _is_concurrently(norm: str) -> bool:
    return bool(CONCURRENTLY_RE.match(norm))


def _alter_subcommands(norm: str) -> list[str]:
    """Split an ALTER TABLE body into subcommands at top-level commas."""
    m = re.match(r"^ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:ONLY\s+)?\S+\s+(.*)$", norm, re.S)
    if not m:
        return []
    body, parts, buf, depth = m.group(1), [], [], 0
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    if "".join(buf).strip():
        parts.append("".join(buf).strip())
    return parts


def _lock_class(subcmd: str) -> str:
    if SUE_LOCK_SUBCMD.search(subcmd):
        return "ShareUpdateExclusive"
    if LOW_LOCK_SUBCMD.search(subcmd):
        return "ShareRowExclusive"
    return "AccessExclusive"


# ---------------------------------------------------------------------------
# Linter
# ---------------------------------------------------------------------------

# Rewrites on a table this large are an outage, not a slow migration. Known row counts
# escalate; an unknown count never de-escalates (that direction would fail open).
LARGE_TABLE_ROWS = 1_000_000

# Majors this skill claims to cover; every version-gated rule was measured on all of them.
SUPPORTED_PG_MIN, SUPPORTED_PG_MAX = 14, 18

# ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY ... NOT VALID on a PARTITIONED table is
# rejected outright below this version. Measured on live 14.23/15/16/17/18.4: 14-17 raise
# "cannot add NOT VALID foreign key on partitioned table"; 18 accepts it.
PARTITIONED_FK_NOT_VALID_MIN_PG = 18


class Linter:
    def __init__(self, pg_version: int = 14, rows: int | None = None,
                 transaction_mode: str = "autocommit",
                 partitioned_tables: frozenset[str] = frozenset()):
        self.pg_version = pg_version
        self.rows = rows
        self.transaction_mode = transaction_mode
        self.partitioned = {t.upper() for t in partitioned_tables}
        self.col_types: dict[str, str] = {}
        self.verified_indexes: set[str] = set()
        self.findings: list[Finding] = []

    def _add(self, code: str, stmt: Statement, message: str,
             severity: str | None = None) -> None:
        rule = RULES_BY_CODE[code]
        self.findings.append(Finding(code, severity or rule.severity, stmt.line, message,
                                     stmt.text[:160]))

    def _rows_note(self) -> str:
        if self.rows is None:
            return ""
        return (f" Declared row count {self.rows:,}: expect roughly "
                f"{self.rows / 1_000_000:.1f}M rows copied plus a full index rebuild.")

    def _rewrite_severity(self) -> str | None:
        """Escalate a rewrite to critical only when the table is known to be large."""
        if self.rows is not None and self.rows >= LARGE_TABLE_ROWS:
            return SEV_CRITICAL
        return None

    # -- guard state tracking ------------------------------------------------

    def lint(self, sql: str) -> list[Finding]:
        self.findings = []
        # In framework mode an outer BEGIN wraps the whole file, so every statement is
        # inside a transaction block even though no BEGIN appears in the text. Without
        # this, SET LOCAL is falsely flagged (PG001) and an in-transaction CONCURRENTLY
        # is falsely cleared (PG002) -- the two errors point in opposite directions,
        # so neither cancels the other out.
        stmts = split_statements(sql, initial_depth=1 if self.transaction_mode == "framework" else 0)

        # Pre-pass: which indexes does this file actually VERIFY? Two conditions, both
        # needed. The statement must name the index (so one index's check cannot vouch
        # for another), and it must be able to FAIL -- a bare `SELECT indexdef ...`
        # proves the definition was read, never that it was checked, and nothing
        # downstream reacts to what it returned. Order is irrelevant (the check may sit
        # before or after the CREATE), hence a pre-pass rather than running state.
        self.verified_indexes = set()
        for st in stmts:
            n = st.norm
            if "INDEXDEF" not in n or not re.search(r"RAISE\s+EXCEPTION", n):
                continue
            self.verified_indexes.update(
                tok.lower() for tok in re.findall(r"[A-Z_][A-Z0-9_]*", n))
            self.verified_indexes.update(
                tok.strip("'").lower() for tok in re.findall(r"'[^']*'", n))

        session_lock_timeout: str | None = None   # SET (session-level); None = no guard
        session_stmt_timeout: str | None = None
        session_stmt_timeout_ms: float | None = None
        local_lock_timeout = False                # SET LOCAL, current txn only
        saw_any_ddl = False
        saw_backfill = False
        saw_analyze = False
        identity_always_cols: set[str] = set()
        # Columns already proven non-null by a CHECK, which lets PG 12+ skip the
        # SET NOT NULL scan. Tracked across statements: the proving CHECK is added
        # in an earlier statement than the SET NOT NULL it enables.
        proven_not_null: set[str] = set()

        for stmt in stmts:
            norm = stmt.norm
            if not norm:
                continue

            # --- track guards ---
            m = re.match(r"^SET\s+(LOCAL\s+)?(LOCK_TIMEOUT|STATEMENT_TIMEOUT)\s*(=|TO)\s*(\S+?);?$", norm)
            if m:
                is_local, var, val = bool(m.group(1)), m.group(2), m.group(4).strip("'\"")
                ms = _timeout_ms(val)
                # A guard is only a guard if its VALUE guards. lock_timeout = 0 is the
                # documented way to say "wait forever" -- exactly the failure the guard
                # exists to prevent -- so it is worse than absent: it reads as compliant.
                disabled = var == "LOCK_TIMEOUT" and ms == 0
                if disabled:
                    self._add("PG019", stmt,
                              f"lock_timeout = {val} disables the timeout: zero means wait "
                              "indefinitely, which is the exact behaviour the guard exists to "
                              "prevent. This DDL will queue on its lock until it is granted or "
                              "killed by hand. Set a finite value such as '3s'.")
                if is_local:
                    if not stmt.in_transaction:
                        self._add("PG001", stmt,
                                  f"SET LOCAL {var.lower()} outside a transaction block only "
                                  "emits a warning and has no effect. Use session-level SET "
                                  "plus RESET, or wrap the DDL in BEGIN/COMMIT.")
                    elif var == "LOCK_TIMEOUT":
                        local_lock_timeout = ms is not None and ms > 0
                else:
                    if var == "LOCK_TIMEOUT":
                        session_lock_timeout = val if (ms is not None and ms > 0) else None
                    else:
                        session_stmt_timeout = val
                        session_stmt_timeout_ms = ms
                continue

            if re.match(r"^RESET\s+LOCK_TIMEOUT", norm):
                session_lock_timeout = None
                continue
            if re.match(r"^RESET\s+STATEMENT_TIMEOUT", norm):
                session_stmt_timeout = None
                session_stmt_timeout_ms = None
                continue
            if re.match(r"^(BEGIN|START TRANSACTION)\b", norm):
                local_lock_timeout = False
                continue
            if re.match(r"^(COMMIT|ROLLBACK|END)\b", norm):
                local_lock_timeout = False
                continue

            # --- record identity columns for PG011, declared types for PG010/PG020 ---
            for cm in re.finditer(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\S+)\s*\((.*)\)",
                                  norm, re.S):
                tbl, body = cm.group(1), cm.group(2)
                for col_m in re.finditer(r"(\w+)\s+\w+[^,]*GENERATED\s+ALWAYS\s+AS\s+IDENTITY", body):
                    identity_always_cols.add(f"{tbl}.{col_m.group(1)}")
                for name, typ in _column_decls(body):
                    self.col_types.setdefault(f"{tbl}.{name}", typ)

            # A table declared PARTITION BY here is partitioned for the rest of the file.
            pm2 = re.match(r"^CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\S+).*?PARTITION\s+BY\b",
                           norm, re.S)
            if pm2:
                self.partitioned.add(pm2.group(1).strip('"').upper())

            # A CHECK (col IS NOT NULL) anywhere earlier in the file proves the
            # column non-null for a later SET NOT NULL (PG 12+).
            for pm in re.finditer(r"CHECK\s*\(\s*(\w+)\s+IS\s+NOT\s+NULL\s*\)", norm):
                proven_not_null.add(pm.group(1))

            self._check_statement(stmt, norm, identity_always_cols, proven_not_null)

            if DDL_RE.match(norm):
                saw_any_ddl = True
                conc = _is_concurrently(norm)

                if conc and stmt.in_transaction:
                    self._add("PG002", stmt,
                              "CONCURRENTLY cannot run inside a transaction block; this "
                              "statement will error. Remove the surrounding BEGIN/COMMIT "
                              "(and disable the migration framework's transaction wrapper).")

                guarded = local_lock_timeout or session_lock_timeout is not None
                if not guarded:
                    self._add("PG004", stmt,
                              "no lock_timeout in effect: this DDL will queue indefinitely on "
                              "its lock and stall every query behind it. Set lock_timeout in the "
                              "form matching the execution context (SET LOCAL inside a "
                              "transaction, session SET outside one).")

                # Fires unless the value is provably zero. An unparseable value cannot be
                # proven harmless, so it is reported rather than assumed fine.
                if conc and session_stmt_timeout is not None and session_stmt_timeout_ms != 0:
                    self._add("PG005", stmt,
                              f"statement_timeout={session_stmt_timeout} is in effect around a "
                              "concurrent build. statement_timeout aborts any statement that "
                              "exceeds it, so a long build is killed and leaves an INVALID "
                              "index. Set statement_timeout = 0 for the build.")

            if BULK_WRITE_RE.match(norm):
                saw_backfill = True
            if re.match(r"^ANALYZE\b", norm):
                saw_analyze = True

        if saw_backfill and not saw_analyze:
            last = stmts[-1] if stmts else Statement("", 1, False)
            self._add("PG017", last,
                      "bulk UPDATE present but no ANALYZE: planner statistics will be stale "
                      "and dead tuples accumulate. Run ANALYZE on the touched table.")

        _ = saw_any_ddl
        self.findings.sort(key=lambda f: (f.line, f.code))
        return self.findings

    # -- per-statement checks ------------------------------------------------

    def _check_statement(self, stmt: Statement, norm: str,
                         identity_always: set[str],
                         proven_not_null: set[str] | None = None) -> None:
        proven_not_null = proven_not_null or set()
        # PG003 -- plain CREATE INDEX
        if re.match(r"^CREATE\s+(UNIQUE\s+)?INDEX\b", norm) and "CONCURRENTLY" not in norm:
            self._add("PG003", stmt,
                      "plain CREATE INDEX takes ShareLock and blocks all writes for the whole "
                      "build. Use CREATE INDEX CONCURRENTLY (outside a transaction block).")

        # PG015 -- REINDEX without CONCURRENTLY
        if re.match(r"^REINDEX\b", norm) and "CONCURRENTLY" not in norm:
            self._add("PG015", stmt,
                      "non-concurrent REINDEX takes ShareLock on the table plus "
                      "AccessExclusive on the index; because the planner locks every index, "
                      "it blocks virtually all queries. Use REINDEX CONCURRENTLY.")

        # PG016 -- VACUUM FULL
        if re.match(r"^VACUUM\s+(\(.*\)\s*)?FULL\b", norm) or re.match(r"^VACUUM\s+FULL\b", norm):
            self._add("PG016", stmt,
                      "VACUUM FULL holds AccessExclusiveLock for the entire rewrite, blocking "
                      "reads and writes. Use pg_repack for an online reorganisation.")

        # PG007 -- ADD CONSTRAINT IF NOT EXISTS
        if re.search(r"ADD\s+CONSTRAINT\s+IF\s+NOT\s+EXISTS", norm):
            self._add("PG007", stmt,
                      "PostgreSQL has no ADD CONSTRAINT IF NOT EXISTS; this is a syntax error. "
                      "Use a DO block guarded on pg_constraint scoped by conrelid.")

        # PG012 -- LIMIT/OFFSET backfill
        if re.match(r"^UPDATE\b", norm) and re.search(r"\bOFFSET\b", norm):
            self._add("PG012", stmt,
                      "OFFSET rescans skipped rows, making the backfill O(n^2). Advance a "
                      "keyset cursor on the primary key instead.")

        # PG014 -- max()-based resume point
        if re.search(r"MAX\s*\(\s*\w+\s*\)\s+FROM\s+\S+\s+WHERE\s+\w+\s+IS\s+NOT\s+NULL", norm):
            self._add("PG014", stmt,
                      "max(col) WHERE col IS NOT NULL as a resume point skips unprocessed rows "
                      "below the maximum. Use min(col) WHERE col IS NULL, or persist the cursor "
                      "inside each batch transaction.")

        # A pg_constraint lookup is only a *guard* when it gates DDL. §9.6 Validation
        # SQL reads the same catalog to confirm a constraint is valid, and reporting
        # that as an unsafe guard would train reviewers to ignore both rules.
        is_constraint_guard = ("PG_CONSTRAINT" in norm and "CONNAME" in norm
                               and re.search(r"ALTER\s+TABLE", norm) is not None)

        # PG022 -- guard matches a NAME but never acts on the DEFINITION. Verified on a
        # live server: with CHECK (amt > 100) already present under the wanted name, a
        # conrelid-scoped guard skips and the migration reports success while leaving
        # the wrong constraint in place.
        #
        # Three syntactic proxies were each bypassed in turn, which is the lesson:
        #   1. "calls pg_get_constraintdef"  -> fetch it, branch only on IS NULL.
        #   2. "+ contains RAISE"            -> RAISE NOTICE aborts nothing.
        #   3. "+ RAISE EXCEPTION"           -> raise on an unrelated condition.
        # The bar here is (a) an abort, not a message, and (b) the fetched definition
        # actually appearing in a comparison. That is still a proxy -- see
        # UNPROVABLE below; this rule narrows the hole, it does not close it.
        if is_constraint_guard and not self._constraint_guard_checks_definition(norm):
            self._add("PG022", stmt,
                      "this guard's decision rests on the constraint NAME. If the table "
                      "already carries that name with a different definition, the "
                      "migration skips and reports success against a schema it did not "
                      "produce. Read pg_get_constraintdef(oid) into a variable, COMPARE "
                      "that variable against the definition you intend, and RAISE "
                      "EXCEPTION on a mismatch. Fetching it without comparing changes "
                      "nothing, and RAISE NOTICE aborts nothing.")

        # PG022 -- CREATE INDEX IF NOT EXISTS has the same name-only hole. Cleared only
        # by an indexdef verification naming THIS index. A file-wide "does the word
        # INDEXDEF appear anywhere" test let one unrelated read clear every index in the
        # file, which is the same name-blind reasoning the rule is about.
        im = re.match(r"^CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:CONCURRENTLY\s+)?"
                      r"IF\s+NOT\s+EXISTS\s+([\w.\"]+)", norm)
        if im and im.group(1).strip('"').rpartition(".")[2].lower() not in self.verified_indexes:
            self._add("PG022", stmt,
                      "CREATE INDEX IF NOT EXISTS checks only that something with that "
                      "name exists. An existing index on different columns survives "
                      "untouched and the intended index is never built. Add a check that "
                      "reads pg_indexes.indexdef for THIS index and RAISE EXCEPTION when "
                      "it is not the definition you intended — a bare SELECT of indexdef "
                      "reads the value but cannot fail on it.")

        # PG008 -- unscoped constraint guard
        if is_constraint_guard and "CONRELID" not in norm:
            self._add("PG008", stmt,
                      "pg_constraint guard filters on conname only. Constraint names are unique "
                      "per table, not per database, so a same-named constraint elsewhere makes "
                      "this skip the migration while reporting success. Add "
                      "AND conrelid = '<schema>.<table>'::regclass.")

        # PG018 -- SET NOT NULL without a CHECK that already proves it
        nn = re.search(r"ALTER\s+(COLUMN\s+)?(\w+)\s+SET\s+NOT\s+NULL", norm)
        if nn and nn.group(2) not in proven_not_null:
            self._add("PG018", stmt,
                      f"SET NOT NULL on {nn.group(2).lower()} scans the whole table while "
                      "holding AccessExclusiveLock. PG 12+ skips that scan when a valid "
                      "CHECK already proves the column non-null: add "
                      f"CHECK ({nn.group(2).lower()} IS NOT NULL) NOT VALID, VALIDATE it "
                      "(non-blocking), then SET NOT NULL, then drop the redundant CHECK.")

        if re.match(r"^ALTER\s+TABLE\b", norm):
            self._check_alter_table(stmt, norm)

        # PG011 -- explicit insert into GENERATED ALWAYS identity
        im = re.match(r"^INSERT\s+INTO\s+(\S+)\s*\(([^)]*)\)(.*)$", norm, re.S)
        if im:
            tbl, cols, rest = im.group(1), im.group(2), im.group(3)
            named = [c.strip() for c in cols.split(",")]
            if "OVERRIDING" not in rest:
                for col in named:
                    if f"{tbl}.{col}" in identity_always:
                        self._add("PG011", stmt,
                                  f"{tbl}.{col} is GENERATED ALWAYS AS IDENTITY; inserting an "
                                  "explicit value without OVERRIDING SYSTEM VALUE is an error. "
                                  "Add OVERRIDING SYSTEM VALUE, or declare the column "
                                  "GENERATED BY DEFAULT.")
                        break

    def _check_alter_table(self, stmt: Statement, norm: str) -> None:
        subs = _alter_subcommands(norm)
        tm = re.match(r"^ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:ONLY\s+)?(\S+)", norm)
        table = tm.group(1).strip('"') if tm else None

        # PG006 -- mixed lock classes escalate to the strictest
        if len(subs) > 1:
            classes = {_lock_class(s) for s in subs}
            if len(classes) > 1:
                self._add("PG006", stmt,
                          "this ALTER TABLE combines subcommands of different lock classes "
                          f"({', '.join(sorted(classes))}). The statement acquires the "
                          "strictest lock of any subcommand, so the cheaper form gains "
                          "nothing. Split into one statement per lock class.")

        for sub in subs:
            # PG021 -- NOT VALID FK on a partitioned table is rejected below PG 18
            if (table and table.upper() in self.partitioned
                    and re.search(r"ADD\s+(CONSTRAINT\s+\w+\s+)?FOREIGN\s+KEY", sub)
                    and "NOT VALID" in sub
                    and self.pg_version < PARTITIONED_FK_NOT_VALID_MIN_PG):
                self._add("PG021", stmt,
                          f"{table.lower()} is partitioned and the target is PG {self.pg_version}: "
                          "PostgreSQL raises 'cannot add NOT VALID foreign key on partitioned "
                          f"table' below PG {PARTITIONED_FK_NOT_VALID_MIN_PG}, so this "
                          "statement fails outright rather than running slowly. Add the FK "
                          "validating in a low-traffic window, or attach pre-validated "
                          "partitions.")

            # PG009 -- constraint without NOT VALID
            if re.search(r"ADD\s+(CONSTRAINT\s+\w+\s+)?(FOREIGN\s+KEY|CHECK)", sub) \
                    and "NOT VALID" not in sub:
                if re.search(r"FOREIGN\s+KEY", sub):
                    detail = ("ADD FOREIGN KEY takes ShareRowExclusive on both this table and "
                              "the referenced table: writes block on both for the validation "
                              "scan (reads are unaffected). Use ADD ... NOT VALID followed by "
                              "VALIDATE CONSTRAINT. On a PARTITIONED table that two-step is "
                              f"only available from PG {PARTITIONED_FK_NOT_VALID_MIN_PG}; "
                              "below that the NOT VALID form is rejected outright.")
                else:
                    detail = ("ADD CHECK takes AccessExclusive and holds it for the whole "
                              "validation scan, blocking reads and writes. Use ADD ... NOT VALID "
                              "followed by VALIDATE CONSTRAINT.")
                self._add("PG009", stmt, detail)

            # PG013 -- volatile DEFAULT
            if re.search(r"ADD\s+(COLUMN\s+)?\w+", sub) and "DEFAULT" in sub:
                for vol in VOLATILE_DEFAULTS:
                    if vol in sub:
                        name = vol if vol.endswith(")") else vol + "...)"
                        self._add("PG013", stmt,
                                  f"ADD COLUMN with the volatile default {name.lower()} "
                                  "rewrites the entire table and all its indexes. A "
                                  "non-volatile default is metadata-only; a volatile one is "
                                  "not. Add the column nullable, then backfill in batches.")
                        break

            # PG010 / PG020 -- type change: rewriting, or unprovable
            tm = re.search(
                r"ALTER\s+(?:COLUMN\s+)?(\w+)\s+(?:SET\s+DATA\s+)?TYPE\s+"
                r"([A-Z][A-Z ]*(?:\(\s*\d+\s*(?:,\s*\d+\s*)?\))?)", sub)
            if tm:
                col, newtype = tm.group(1), tm.group(2).strip()
                key = f"{table}.{col}" if table else None
                src = self.col_types.get(key) if key else None
                verdict = self._classify_type_change(sub, src, newtype)
                if verdict == "unknown":
                    self._add("PG020", stmt,
                              f"cannot statically prove whether ALTER COLUMN {col.lower()} TYPE "
                              f"{newtype.lower()} rewrites the table: the column's current type is "
                              "not declared anywhere in this input, and binary coercibility is a "
                              "property of the source/target PAIR, not of the target alone "
                              "(text -> varchar(10) rewrites; varchar(10) -> text does not). "
                              "Confirm the source type against the live catalog "
                              "(\\d <table>) before scoring this safe.")
                elif verdict == "rewrite":
                    known = f" from {src.lower()}" if src else ""
                    self._add("PG010", stmt,
                              f"ALTER COLUMN {col.lower()} TYPE {newtype.lower()}{known} is not "
                              "binary coercible, so it rewrites the table and every index under "
                              "AccessExclusiveLock and needs up to double the disk space. "
                              "Use expand-contract (add column, batch backfill, swap, drop)."
                              + self._rows_note(),
                              severity=self._rewrite_severity())
                if key:
                    self.col_types[key] = newtype

    @staticmethod
    def _constraint_guard_checks_definition(norm: str) -> bool:
        """Does this guard abort when the existing definition is not the intended one?

        Requires all three, because each pair alone was demonstrably bypassable:
          * pg_get_constraintdef() is read INTO a variable,
          * that variable appears in a comparison (=, <>, LIKE, ~, IS DISTINCT FROM),
          * and RAISE EXCEPTION -- not RAISE NOTICE, which aborts nothing.
        """
        m = re.search(r"PG_GET_CONSTRAINTDEF\s*\([^)]*\)\s+INTO\s+(\w+)", norm)
        if not m:
            return False
        var = m.group(1)
        if not re.search(r"RAISE\s+EXCEPTION", norm):
            return False
        compared = re.search(
            rf"\b{re.escape(var)}\b\s*(?:NOT\s+)?(?:=|<>|!=|~|LIKE|ILIKE|"
            rf"IS\s+DISTINCT\s+FROM|SIMILAR\s+TO)", norm)
        return bool(compared)

    @staticmethod
    def _classify_type_change(sub: str, src: str | None, dst: str) -> str:
        """Return 'cheap' | 'rewrite' | 'unknown' for an ALTER COLUMN TYPE.

        Binary coercibility is a property of the **pair** of types, never of the target
        alone. Judging by the target is unsound in both directions, and both directions
        were measured on live servers (14.23 and 18.4, identical results):

            varchar(10) -> varchar(20)   NO-REWRITE      varchar(20) -> varchar(5)  REWRITE
            varchar(10) -> text          NO-REWRITE      text        -> varchar(10) REWRITE
            text        -> varchar       NO-REWRITE      int         -> text        REWRITE

        So a target of TEXT or VARCHAR proves nothing. When the source type is not
        declared anywhere in the input, the honest answer is 'unknown' -- reported as
        PG020 -- not silence.
        """
        if "USING" in sub:
            return "rewrite"
        db, dn = _parse_type(dst)

        if src is None:
            # Without the source, the pair is undecidable ONLY if some source could
            # have reached this target for free. Nothing is binary coercible to
            # bigint / jsonb / timestamptz, so those stay provable rewrites.
            if db in _BINARY_COERCIBLE_TARGETS or db not in _KNOWN_BUILTIN_TYPES:
                return "unknown"
            return "rewrite"

        sb, sn = _parse_type(src)
        if sb == db and sn == dn:
            return "cheap"
        if sb not in _KNOWN_BUILTIN_TYPES or db not in _KNOWN_BUILTIN_TYPES:
            return "unknown"          # domain / enum / user-defined: not decidable here
        if sb in _STRINGY and db in _STRINGY:
            if dn is None:
                return "cheap"        # target is unbounded: always binary coercible
            if sn is not None and dn >= sn:
                return "cheap"        # widening an already-bounded varchar
            return "rewrite"          # adding or tightening a length limit needs a scan
        return "rewrite"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def render_text(path: str, findings: list[Finding]) -> str:
    if not findings:
        # "OK" is about this checker's 22 rules, not about the migration. Saying so on
        # the clean result is the only place it will actually be read.
        return (f"{path}: 0 findings — no rule in this checker fired.\n"
                f"  NOT a proof of safety: see `--limitations` for what it cannot decide.")
    lines = [f"{path}: {len(findings)} finding(s)"]
    for f in findings:
        lines.append(f"  [{f.severity.upper():8}] {f.code} line {f.line}: {f.message}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", type=pathlib.Path)
    ap.add_argument("--json", action="store_true", help="emit findings as JSON")
    ap.add_argument("--pg-version", type=int, default=14,
                    help="target major version (default: 14, oldest supported). Gates "
                         "version-dependent rules such as PG021.")
    ap.add_argument("--rows", type=int, default=None,
                    help="known row count of the table. Escalates rewrite findings to "
                         f"critical at >= {LARGE_TABLE_ROWS:,} rows; never de-escalates.")
    ap.add_argument("--transaction-mode", choices=("autocommit", "explicit", "framework"),
                    default="autocommit",
                    help="how the file is executed. 'framework' = an outer BEGIN/COMMIT "
                         "wraps the whole file (Flyway, golang-migrate, Alembic default), "
                         "which makes SET LOCAL valid everywhere and CONCURRENTLY fatal. "
                         "'explicit' (the file opens its own transactions) is analysed "
                         "identically to 'autocommit' -- the BEGIN is in the text, so it "
                         "is already tracked; the name exists to let you state the "
                         "assumption rather than leave it implicit.")
    ap.add_argument("--partitioned", action="append", default=[], metavar="TABLE",
                    help="mark TABLE as partitioned (repeatable). Tables declared "
                         "PARTITION BY in the input are detected automatically.")
    ap.add_argument("--list-rules", action="store_true", help="print the rule registry")
    ap.add_argument("--limitations", action="store_true",
                    help="print what this checker cannot decide, and exit")
    args = ap.parse_args(argv)

    if args.limitations:
        print("This checker is a syntactic reader of the SQL you hand it. It cannot "
              "establish:")
        for item in UNPROVABLE:
            print(f"  - {item}")
        print("\nA clean result means no rule fired, not that the migration is safe.")
        return 0

    if args.list_rules:
        for r in RULES:
            print(f"{r.code}\t{r.severity}\t{r.title}\t[{r.source}]")
        return 0

    if not args.files:
        ap.error("no input files (use --list-rules to inspect the registry)")

    if not SUPPORTED_PG_MIN <= args.pg_version <= SUPPORTED_PG_MAX:
        print(f"warning: PG {args.pg_version} is outside the supported range "
              f"{SUPPORTED_PG_MIN}-{SUPPORTED_PG_MAX}; version-gated rules may be wrong",
              file=sys.stderr)

    results, worst = {}, 0
    for path in args.files:
        if not path.exists():
            print(f"{path}: ERROR file not found", file=sys.stderr)
            return 2
        findings = Linter(args.pg_version, args.rows, args.transaction_mode,
                          frozenset(args.partitioned)).lint(path.read_text(encoding="utf-8"))
        results[str(path)] = [f.to_dict() for f in findings]
        if any(f.severity == SEV_CRITICAL for f in findings):
            worst = max(worst, 1)
        elif findings:
            worst = max(worst, 1)
        if not args.json:
            print(render_text(str(path), findings))

    if args.json:
        print(json.dumps({"findings": results, "unprovable": list(UNPROVABLE)}, indent=2))
    return worst


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Mutation sweep for the pg-migration skill.

Each mutation breaks one behaviour on purpose. The test suite must then FAIL --
that is a KILL. A mutation the suite still passes is a SURVIVOR, meaning no
assertion actually depends on the behaviour it broke.

Two failure modes this script is built to avoid:

1. **Stale anchors.** If a mutation's anchor text no longer exists in the file,
   the substitution is a silent no-op and the mutation "survives" for a reason
   that has nothing to do with test coverage. Every anchor is verified to exist
   (and its occurrence count recorded) before the sweep runs; a missing anchor is
   a hard error, not a survivor.
2. **Partial replacement.** Substitutions replace ALL occurrences. Replacing only
   the first can leave a working copy of the mutated logic behind, which makes a
   genuine assertion look vacuous.

Usage:
    mutation_sweep.py            # run the sweep
    mutation_sweep.py --verify   # only check anchors resolve, do not run tests
    mutation_sweep.py --list     # print the mutation registry
"""

from __future__ import annotations

import argparse
import atexit
import dataclasses
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
SKILL_DIR = SCRIPTS_DIR.parent
TESTS_DIR = SCRIPTS_DIR / "tests"

LINTER = SCRIPTS_DIR / "lint_migration.py"
RUNNER = SCRIPTS_DIR / "run_regression.sh"
MATRIX = SKILL_DIR / "references" / "pg-ddl-lock-matrix.md"
LARGE = SKILL_DIR / "references" / "large-table-migration.md"
ANTI = SKILL_DIR / "references" / "migration-anti-examples.md"
SKILL_MD = SKILL_DIR / "SKILL.md"
COVERAGE = TESTS_DIR / "COVERAGE.md"
REPL = SKILL_DIR / "references" / "replication-rls-extensions.md"


@dataclasses.dataclass(frozen=True)
class Mutation:
    mid: str
    target: pathlib.Path
    anchor: str
    replacement: str
    breaks: str  # what behaviour this destroys


MUTATIONS: tuple[Mutation, ...] = (
    # ---- guard-form detection (the top defect) -------------------------------
    Mutation("M01", LINTER,
             "                    if not stmt.in_transaction:",
             "                    if False:",
             "PG001 stops reporting SET LOCAL used outside a transaction block"),
    Mutation("M02", LINTER,
             "                if conc and stmt.in_transaction:",
             "                if conc and False:",
             "PG002 stops reporting CONCURRENTLY inside a transaction block"),
    Mutation("M03", LINTER,
             "                guarded = local_lock_timeout or session_lock_timeout is not None",
             "                guarded = True",
             "PG004 never reports missing lock_timeout"),
    Mutation("M04", LINTER,
             "if conc and session_stmt_timeout is not None and session_stmt_timeout_ms != 0:",
             "if conc and False:",
             "PG005 never reports a finite statement_timeout on a concurrent build"),
    Mutation("M05", LINTER,
             "                        local_lock_timeout = ms is not None and ms > 0",
             "                        local_lock_timeout = False",
             "a correctly-scoped SET LOCAL guard is no longer recognised (false positive)"),

    # ---- lock classification -------------------------------------------------
    Mutation("M06", LINTER,
             "    if LOW_LOCK_SUBCMD.search(subcmd):\n        return \"ShareRowExclusive\"",
             "    if LOW_LOCK_SUBCMD.search(subcmd):\n        return \"AccessExclusive\"",
             "ADD FOREIGN KEY is misclassified as AccessExclusive -- the original error"),
    Mutation("M07", LINTER,
             '    if SUE_LOCK_SUBCMD.search(subcmd):\n        return "ShareUpdateExclusive"',
             '    if SUE_LOCK_SUBCMD.search(subcmd):\n        return "AccessExclusive"',
             "VALIDATE CONSTRAINT / fillfactor misclassified as AccessExclusive"),
    Mutation("M08", LINTER,
             '    if LOW_LOCK_SUBCMD.search(subcmd):\n        return "ShareRowExclusive"\n'
             '    return "AccessExclusive"',
             '    if LOW_LOCK_SUBCMD.search(subcmd):\n        return "ShareRowExclusive"\n'
             '    return "ShareUpdateExclusive"',
             "unknown ALTER TABLE subforms fail OPEN instead of assuming the strictest lock"),
    Mutation("M09", LINTER,
             "            if len(classes) > 1:",
             "            if False:",
             "PG006 stops reporting mixed lock classes in one ALTER TABLE"),

    # ---- type-change allow-list ---------------------------------------------
    Mutation("M10", LINTER,
             '        if "USING" in sub:\n            return "rewrite"',
             '        if "USING" in sub:\n            return "cheap"',
             "a USING clause no longer voids the no-rewrite exemption"),
    Mutation("M11", LINTER,
             '"INT2", "INT8", "FLOAT4", "FLOAT8", "NUMERIC", "MONEY", "BOOL",',
             '"INT2", "FLOAT4", "FLOAT8", "NUMERIC", "MONEY", "BOOL",',
             "int8 leaves the known-builtin set, so int -> bigint stops being a "
             "provable rewrite"),
    Mutation("M12", LINTER,
             "    def _classify_type_change(sub: str, src: str | None, dst: str) -> str:",
             '    def _classify_type_change(sub: str, src: str | None, dst: str) -> str:\n        return "cheap"',
             "every type change is treated as cheap (classifier fails open)"),
    Mutation("M31", LINTER,
             '            if db in _BINARY_COERCIBLE_TARGETS or db not in _KNOWN_BUILTIN_TYPES:\n                return "unknown"',
             '            if False:\n                return "unknown"',
             "an unsourced text/varchar target is asserted as a rewrite instead of "
             "reported as unprovable"),
    Mutation("M32", LINTER,
             '            if db in _BINARY_COERCIBLE_TARGETS or db not in _KNOWN_BUILTIN_TYPES:\n                return "unknown"',
             '            if True:\n                return "unknown"',
             "int -> bigint degrades from a rewrite verdict to 'cannot prove'"),
    Mutation("M33", LINTER,
             '            if sn is not None and dn >= sn:\n                return "cheap"',
             '            if sn is not None:\n                return "cheap"',
             "varchar narrowing (varchar(20) -> varchar(5)) is wrongly scored cheap"),

    # ---- statement splitting -------------------------------------------------
    Mutation("M13", LINTER,
             '        m = re.match(r"\\$[A-Za-z_0-9]*\\$", sql[i:])\n        if m:\n            mark()',
             '        m = None\n        if m:\n            mark()',
             "dollar-quoted DO blocks are torn apart on internal semicolons"),
    Mutation("M14", LINTER,
             "        if not ch.isspace():\n            mark()",
             "        if True:\n            mark()",
             "statement line numbers anchor on whitespace instead of the first token"),
    Mutation("M15", LINTER,
             "        if not _normalize(raw):\n            return \"\"",
             "        if not raw.strip():\n            return \"\"",
             "comment-only chunks become phantom statements"),
    Mutation("M16", LINTER,
             '            if re.match(r"^(BEGIN|START TRANSACTION)\\b", last):\n                depth += 1',
             '            if re.match(r"^(BEGIN|START TRANSACTION)\\b", last):\n                depth += 0',
             "transaction depth is never tracked, so in_transaction is always False"),

    # ---- individual rules ----------------------------------------------------
    Mutation("M17", LINTER,
             "if is_constraint_guard and \"CONRELID\" not in norm:",
             "if False:",
             "PG008 stops reporting unscoped constraint guards"),
    Mutation("M18", LINTER,
             '            if "OVERRIDING" not in rest:',
             "            if False:",
             "PG011 stops reporting explicit inserts into GENERATED ALWAYS identity"),
    Mutation("M19", LINTER,
             'and "NOT VALID" not in sub:',
             "and False:",
             "PG009 stops reporting constraints added without NOT VALID"),
    Mutation("M20", LINTER,
             'if re.match(r"^CREATE\\s+(UNIQUE\\s+)?INDEX\\b", norm) and "CONCURRENTLY" not in norm:',
             "if False:",
             "PG003 stops reporting plain CREATE INDEX"),
    Mutation("M21", LINTER,
             'if re.match(r"^REINDEX\\b", norm) and "CONCURRENTLY" not in norm:',
             "if False:",
             "PG015 stops reporting non-concurrent REINDEX"),
    Mutation("M22", LINTER,
             "        if saw_backfill and not saw_analyze:",
             "        if False:",
             "PG017 stops reporting a bulk UPDATE with no ANALYZE"),

    Mutation("M29", LINTER,
             "        if nn and nn.group(2) not in proven_not_null:",
             "        if nn and False:",
             "PG018 stops reporting SET NOT NULL without a proving CHECK"),
    Mutation("M30", LINTER,
             "        if nn and nn.group(2) not in proven_not_null:",
             "        if nn:",
             "PG018 fires even when a proving CHECK exists (false positive)"),


    # ---- guard VALUE, not merely guard presence ------------------------------
    Mutation("M34", LINTER,
             '                disabled = var == "LOCK_TIMEOUT" and ms == 0',
             "                disabled = False",
             "PG019 stops reporting lock_timeout = 0, so a disabled guard reads as compliant"),
    Mutation("M35", LINTER,
             "                        session_lock_timeout = val if (ms is not None and ms > 0) else None",
             "                        session_lock_timeout = val",
             "lock_timeout = 0 still counts as a guard, suppressing PG004"),
    Mutation("M36", LINTER,
             '    if v == "DEFAULT":\n        return 0.0',
             '    if v == "DEFAULT":\n        return 3000.0',
             "SET lock_timeout = DEFAULT is treated as a real guard although it resets to 0"),

    # ---- DDL and bulk-write scope --------------------------------------------
    Mutation("M37", LINTER,
             r'|DROP\s+(TABLE|INDEX|VIEW|MATERIALIZED\s+VIEW|SEQUENCE|TYPE|SCHEMA|TRIGGER)"',
             r'|DROP\s+(INDEX)"',
             "dropping a table stops counting as DDL, so it needs no lock_timeout"),
    Mutation("M38", LINTER,
             r'    r"^(UPDATE\s|DELETE\s+FROM\s)"',
             r'    r"^(UPDATE\s)"',
             "a CTE-led or DELETE backfill no longer triggers the missing-ANALYZE check"),

    # ---- version gating -------------------------------------------------------
    Mutation("M39", LINTER,
             "PARTITIONED_FK_NOT_VALID_MIN_PG = 18",
             "PARTITIONED_FK_NOT_VALID_MIN_PG = 14",
             "PG021 never fires: a NOT VALID FK on a partitioned table looks legal on 14-17"),


    # ---- idempotency guards that match on name only ---------------------------
    Mutation("M40", LINTER,
             "        if is_constraint_guard and not self._constraint_guard_checks_definition(norm):",
             "        if False:",
             "PG022 stops reporting a name-only constraint guard, so a same-named "
             "constraint with a different definition is skipped silently"),
    Mutation("M41", LINTER,
             "        if im and im.group(1).strip('\"').rpartition(\".\")[2].lower() not in self.verified_indexes:",
             "        if im and False:",
             "CREATE INDEX IF NOT EXISTS is never questioned, so an existing index on "
             "different columns survives a migration that reports success"),
    Mutation("M42", LINTER,
             '            if "INDEXDEF" not in n or not re.search(r"RAISE\\s+EXCEPTION", n):\n                continue',
             "            if False:\n                continue",
             "every statement counts as an indexdef verification, so any file clears "
             "PG022 for every index in it"),
    Mutation("M46", LINTER,
             '        if not re.search(r"RAISE\\s+EXCEPTION", norm):\n            return False',
             "        if False:\n            return False",
             "RAISE NOTICE counts as acting on the definition, so a guard that only "
             "logs the drift clears PG022"),
    Mutation("M52", LINTER,
             "        compared = re.search(",
             "        compared = True or re.search(",
             "a guard that fetches the definition and never compares it clears PG022"),
    Mutation("M53", LINTER,
             '            if "INDEXDEF" not in n or not re.search(r"RAISE\\s+EXCEPTION", n):',
             '            if "INDEXDEF" not in n:',
             "a bare SELECT of indexdef counts as verifying the index, although nothing "
             "downstream can fail on what it returned"),

    # ---- shell orchestration and output contracts ----------------------------
    Mutation("M54", RUNNER,
             '    if out="$(python3 "${SCRIPT_DIR}/lint_migration.py" "${tmp}/${f}.sql" 2>&1)"; then',
             "    if false; then",
             "Stage 6 stops accepting clean files by the linter exit-status contract"),
    Mutation("M55", REPL,
             "  ELSIF have <> want THEN",
             "  ELSIF false THEN",
             "the extension pin silently accepts an already-installed wrong version"),
    Mutation("M56", SKILL_MD,
             "Scorecard: X/N — Critical Y/3, Standard Z/A, Hygiene W/4 — PASS/FAIL",
             "Scorecard: X/12 — Critical Y/3, Standard Z/5, Hygiene W/4 — PASS/FAIL",
             "the output contract returns to fixed denominators despite N/A items"),
    Mutation("M57", SKILL_MD,
             "Standard N/A yields `X/11` overall; Standard 3/4 is then 75% and FAILS the unchanged",
             "Standard N/A yields `X/11` overall; Standard 3/4 passes the unchanged",
             "3/4 is incorrectly treated as meeting an 80% Standard threshold"),


    # ---- COVERAGE.md drift (the doc describes machine-checkable facts) --------
    Mutation("M43", COVERAGE,
             "| PG019 | critical |",
             "| PG019 | hygiene |",
             "the coverage doc's rule table disagrees with the registry's severities"),
    Mutation("M44", COVERAGE,
             "| PG-015 | Unscoped constraint guard | defect | standard | PG008 | PG008, PG022 |",
             "| PG-015 | Unscoped constraint guard | defect | standard | PG008 | PG008 |",
             "the coverage doc understates a fixture's expected findings"),


    Mutation("M45", LINTER,
             '                               and re.search(r"ALTER\\s+TABLE", norm) is not None)',
             "                               and True)",
             "a read-only pg_constraint validation query is misreported as an unsafe guard"),


    # ---- round-3 documentation corrections ------------------------------------
    Mutation("M47", LARGE,
             "**pg_repack has no cleanup mode, and `--dry-run` is not one.**",
             "**pg_repack has a cleanup mode.**",
             "the false claim that --dry-run cleans up after a crashed repack returns"),
    Mutation("M48", REPL,
             "**There is no `extension_destdir` setting on PostgreSQL 14–18**",
             "Run `SHOW extension_destdir` to find the scripts.",
             "the reader is sent to a GUC that does not exist on any supported major"),
    Mutation("M49", LARGE,
             "  (SELECT count(*) > 0 FROM orders_new)   -- false when empty: next value is 1, not 2",
             "  true",
             "the setval guard hardcodes is_called, so an empty table skips id 1 again"),
    Mutation("M50", ANTI,
             "**not** safe in general: it still decides on the name alone",
             "safe: the server scopes it correctly",
             "AE-16 goes back to contradicting AE-19 about CREATE INDEX IF NOT EXISTS"),
    Mutation("M51", SKILL_MD,
             "`ADD COLUMN … NULL` still takes\nAccessExclusiveLock",
             "`ADD COLUMN … NULL` is non-blocking",
             "a nullable ADD COLUMN reads as needing no lock_timeout again"),

    # ---- severity wiring -----------------------------------------------------
    Mutation("M23", LINTER,
             'Rule("PG004", SEV_CRITICAL,',
             'Rule("PG004", SEV_HYGIENE,',
             "a critical rule is downgraded to hygiene"),

    # ---- documentation drift (proves the drift guards are not inert) ---------
    Mutation("M24", MATRIX,
             "| ADD FOREIGN KEY | **ShareRowExclusive**",
             "| ADD CONSTRAINT (FK/CHECK) | AccessExclusiveLock",
             "the matrix regresses to merging FK and CHECK as AccessExclusive"),
    Mutation("M25", MATRIX,
             "strictest one required by any subcommand",
             "lock required by the first subcommand",
             "the multi-subcommand escalation rule is lost"),
    Mutation("M26", SKILL_MD,
             "PostgreSQL **14–18**",
             "PostgreSQL 12–17",
             "the supported version range regresses to the EOL range"),
    Mutation("M27", LARGE,
             "pg_repack cannot change a schema",
             "Use pg_repack's trigger-based replication to copy data",
             "the fabricated pg_repack schema-change workflow returns"),
    Mutation("M28", ANTI,
             "ShareLock on the parent table",
             "REINDEX blocks all reads and writes on the underlying table",
             "the REINDEX lock error returns to the anti-example file"),
)


# The sweep mutates source files. Doing that in the real worktree makes every other
# reader of the tree -- a concurrent regression run, an editor, a second sweep -- observe
# deliberately broken code, and two sweeps overlapping corrupt each other's restore. So
# the whole sweep runs against a private copy and the real tree is never written to.
_SANDBOX: pathlib.Path | None = None


def sandbox_root() -> pathlib.Path:
    """Return (creating on first use) a private copy of the skill directory."""
    global _SANDBOX
    if _SANDBOX is None:
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="pgmig-sweep-",
                                            dir=os.environ.get("TMPDIR") or None))
        dest = tmp / SKILL_DIR.name
        shutil.copytree(SKILL_DIR, dest, ignore=shutil.ignore_patterns(
            "__pycache__", ".pytest_cache", ".git", "*.pyc"))
        # copytree preserves mode, so a read-only source file would make the sandbox
        # unwritable and the sweep would fail on the copy for a reason that has nothing
        # to do with the mutation. The sandbox is meant to be mutable; the original is
        # the thing being protected.
        for f in dest.rglob("*"):
            if f.is_file():
                f.chmod(f.stat().st_mode | stat.S_IWUSR)
        atexit.register(shutil.rmtree, tmp, True)
        _SANDBOX = dest
    return _SANDBOX


def sandboxed(target: pathlib.Path) -> pathlib.Path:
    """Map a real path to its counterpart inside the sandbox copy."""
    return sandbox_root() / target.relative_to(SKILL_DIR)


def run_tests(timeout: int = 300) -> bool:
    """Return True if the suite PASSES, run inside the sandbox copy.

    The live-server matrix is excluded: no mutation here targets PostgreSQL's own
    behaviour, it needs containers the sweep must not depend on, and at ~60s per run it
    would dominate the wall-clock of the whole sweep. Its job -- checking our claims
    against a real server -- is not something a mutation can test.
    """
    root = sandbox_root()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(root / "scripts" / "tests"),
         "-q", "-x", "--no-header", "-p", "no:cacheprovider",
         "--ignore", str(root / "scripts" / "tests" / "test_pg_server_matrix.py")],
        cwd=str(root), capture_output=True, text=True, timeout=timeout,
    )
    return proc.returncode == 0


def verify_anchors() -> list[str]:
    """Every anchor must exist. A stale anchor is an error, never a survivor."""
    problems = []
    for m in MUTATIONS:
        if not m.target.exists():
            problems.append(f"{m.mid}: target missing: {m.target}")
            continue
        text = m.target.read_text(encoding="utf-8")
        count = text.count(m.anchor)
        if count == 0:
            problems.append(
                f"{m.mid}: anchor not found in {m.target.name} -- the mutation would "
                f"be a silent no-op. Anchor: {m.anchor[:80]!r}"
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verify", action="store_true",
                    help="only check that anchors resolve; do not run the sweep")
    ap.add_argument("--list", action="store_true", help="print the mutation registry")
    args = ap.parse_args(argv)

    if args.list:
        for m in MUTATIONS:
            print(f"{m.mid}\t{m.target.name}\t{m.breaks}")
        return 0

    problems = verify_anchors()
    if problems:
        print("ANCHOR VERIFICATION FAILED — refusing to run the sweep:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        print("\nFix the anchors (the source has changed) and re-run.", file=sys.stderr)
        return 2
    print(f"anchors OK ({len(MUTATIONS)} mutations)")
    if args.verify:
        return 0

    print("baseline: running suite unmutated...")
    if not run_tests():
        print("BASELINE FAILS — fix the suite before sweeping.", file=sys.stderr)
        return 2
    print("baseline PASSES\n")

    print(f"sweeping in a private copy at {sandbox_root()}\n")
    killed, survived = [], []
    for m in MUTATIONS:
        target = sandboxed(m.target)
        original = target.read_text(encoding="utf-8")
        # Replace ALL occurrences: a partial replacement can leave working logic behind.
        mutated = original.replace(m.anchor, m.replacement)
        assert mutated != original, f"{m.mid}: replacement produced no change"
        try:
            target.write_text(mutated, encoding="utf-8")
            passed = run_tests()
        finally:
            target.write_text(original, encoding="utf-8")

        if passed:
            survived.append(m)
            print(f"  SURVIVED  {m.mid}  {m.breaks}")
        else:
            killed.append(m)
            print(f"  killed    {m.mid}  {m.breaks}")

    total = len(MUTATIONS)
    print(f"\n{len(killed)}/{total} killed, {len(survived)} survived")
    if survived:
        print("\nSurvivors — no assertion depends on these behaviours:")
        for m in survived:
            print(f"  {m.mid} ({m.target.name}): {m.breaks}")
        return 1
    print("All mutations killed: every mutated behaviour is covered by an assertion.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Mutation sweep: reintroduce each audited defect and require the suite to fail.

Answers the question a green test run cannot: are these assertions load-bearing,
or decorative? Each mutation puts one previously-shipped defect back into the
skill — a wrong matrix cell, a reversed tool flag, a disabled check — and the
suite must go red. Anything that survives marks an assertion that is not actually
testing what it claims.

    python3 scripts/mutation_sweep.py            # run every mutation
    python3 scripts/mutation_sweep.py --list     # show them without running
    python3 scripts/mutation_sweep.py -k varchar # run a subset by substring

Exit codes:
    0  every mutation was killed
    1  at least one mutation survived, or a mutation string no longer matches
    2  the baseline suite is already red — fix that first

Each run copies the skill into a temporary directory; the working tree is never
modified. Runtime is roughly (number of mutations x suite runtime).
""" 
from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys
import tempfile
from typing import Sequence

SKILL = pathlib.Path(__file__).resolve().parents[1]
REPO = SKILL.parents[1]

MATRIX = "references/ddl-algorithm-matrix.md"
LARGE = "references/large-table-migration.md"
ANTI = "references/migration-anti-examples.md"
LINTER = "scripts/lint_migration.py"
FIX008 = "scripts/tests/golden/008_good_gh_ost.json"
SKILL_MD = "SKILL.md"
BASELINE = "scripts/tests/lint_baseline.txt"
VERIFY = "scripts/verify_against_server.sh"
EVAL = "scripts/run_model_eval.py"
COMPOSE = "scripts/verify-matrix.docker-compose.yml"
COVERAGE_DOC = "scripts/tests/COVERAGE.md"

# (name, relative path, old, new)
MUTATIONS = [
    # --- DDL matrix: the four rows the audit found wrong ---------------------
    ("matrix: DROP COLUMN back to COPY", MATRIX,
     "| DROP COLUMN | **INPLACE** |", "| DROP COLUMN | **COPY** |"),
    ("matrix: DROP COLUMN concurrent DML -> No", MATRIX,
     "| DROP COLUMN | **INPLACE** | **INSTANT** (8.0.29+), INPLACE before | Yes |",
     "| DROP COLUMN | **INPLACE** | **INSTANT** (8.0.29+), INPLACE before | No |"),
    ("matrix: VARCHAR extension becomes INSTANT", MATRIX,
     "**INPLACE — never INSTANT**", "**INSTANT** (8.0.12+)"),
    ("matrix: FULLTEXT allows LOCK=NONE after first", MATRIX,
     "| ADD FULLTEXT INDEX | INPLACE | INPLACE | **No — SHARED** |",
     "| ADD FULLTEXT INDEX | INPLACE | INPLACE | SHARED first, Yes after |"),
    ("matrix: ADD PRIMARY KEY blocks writes", MATRIX,
     "| ADD PRIMARY KEY | INPLACE⁴ | INPLACE⁴ | **Yes** |",
     "| ADD PRIMARY KEY | INPLACE⁴ | INPLACE⁴ | **No — SHARED** |"),
    ("matrix: 5.7 ADD PARTITION allows INPLACE", MATRIX,
     "| `ADD PARTITION` | `ALGORITHM=DEFAULT, LOCK=DEFAULT` **only** |",
     "| `ADD PARTITION` | `INPLACE` with `LOCK=NONE` |"),
    ("matrix: 8.0 REORGANIZE PARTITION allows LOCK=NONE", MATRIX,
     "| `REORGANIZE PARTITION` | `ALGORITHM=DEFAULT, LOCK=DEFAULT` **only** | `INPLACE` with `LOCK={DEFAULT,SHARED,EXCLUSIVE}` | **No** |",
     "| `REORGANIZE PARTITION` | `ALGORITHM=DEFAULT, LOCK=DEFAULT` **only** | `INPLACE` with `LOCK={DEFAULT,NONE,SHARED}` | Yes |"),
    ("matrix: CONVERT charset allows LOCK=NONE", MATRIX,
     "| `CONVERT TO CHARACTER SET …` (rewrite) | **COPY** | INPLACE | **No — SHARED** |",
     "| `CONVERT TO CHARACTER SET …` (rewrite) | **COPY** | INPLACE | Yes |"),
    ("matrix: RENAME INDEX claimed INSTANT", MATRIX,
     "| RENAME INDEX | INPLACE | INPLACE | Yes | No | **Not INSTANT**",
     "| RENAME INDEX | INPLACE | **INSTANT** | Yes | No | Metadata only"),
    ("matrix: unsourced one-INSTANT-per-rebuild claim returns", MATRIX,
     "- Multiple columns **may** be added in a single INSTANT statement",
     "- Before 8.0.29, only **one** INSTANT ALTER was permitted per table rebuild.\n"
     "- Multiple columns **may** be added in a single INSTANT statement"),
    ("matrix: MODIFY NOT NULL->NULL called metadata-only", MATRIX,
     "| MODIFY NOT NULL → NULL | INPLACE | INPLACE | Yes | **Yes** | Rebuilds the table — this is *not* a metadata-only change |",
     "| MODIFY NOT NULL → NULL | INPLACE | INPLACE | Yes | No | In-place metadata change |"),
    ("matrix: provenance date removed", MATRIX, "2026-08-06", "recently"),
    ("matrix: 5.7-has-no-INSTANT note removed", MATRIX,
     "MySQL 5.7 has no INSTANT algorithm at all",
     "MySQL 5.7 behaves differently"),

    # --- large-table: gh-ost / pt-osc / backfill ------------------------------
    ("large: --allow-on-master back on the replica example", LARGE,
     "  --host=replica1.db.internal --port=3306 \\",
     "  --host=replica1.db.internal --allow-on-master \\"),
    ("large: destructive cleanup flags back in the template", LARGE,
     "  --exact-rowcount --concurrent-rowcount \\",
     "  --exact-rowcount --concurrent-rowcount --initially-drop-old-table \\"),
    ("large: stored-procedure form removed", LARGE, "CREATE PROCEDURE", "-- procedure"),
    ("large: INVALID label removed from the bare WHILE block", LARGE,
     "-- INVALID outside a stored program — ERROR 1064 near 'WHILE'",
     "-- Backfill loop"),
    ("large: sql_log_bin=0 back in the backfill guard block", LARGE,
     "| Session guards | `lock_wait_timeout=3`, `innodb_lock_wait_timeout=3` on the backfill connection |",
     "| Session guards | `lock_wait_timeout=3` |\n\n```sql\nSET SESSION sql_log_bin = 0;\nSET SESSION lock_wait_timeout = 3;\n```"),
    ("large: 5.7 lock tables removed", LARGE, "INNODB_LOCKS", "DATA_LOCKS"),
    ("large: --include-triggers version gate removed", LARGE,
     "(gh-ost 1.1.8+)", "(recent gh-ost)"),
    ("large: 'do not drop business triggers' removed", LARGE,
     "**Do not drop business triggers to make gh-ost run.**",
     "Remove the triggers before running gh-ost."),
    ("large: pt-osc critical-load default wrong", LARGE,
     "`Threads_running=50`", "`Threads_running=500`"),

    # --- anti-examples --------------------------------------------------------
    ("anti: AE-13 recommends INPLACE without disabling fk checks", ANTI,
     "SET SESSION foreign_key_checks = 0;\nALTER TABLE order_items\n"
     "  ADD CONSTRAINT fk_order FOREIGN KEY (order_id) REFERENCES orders(id),\n"
     "  ALGORITHM=INPLACE, LOCK=NONE;",
     "ALTER TABLE order_items\n"
     "  ADD CONSTRAINT fk_order FOREIGN KEY (order_id) REFERENCES orders(id),\n"
     "  ALGORITHM=INPLACE, LOCK=NONE;"),
    ("anti: AE-9 FULLTEXT 'first time only' framing returns", ANTI,
     "never permit concurrent", "only on the first build permit concurrent"),

    # --- golden fixture -------------------------------------------------------
    ("fixture 008: reversed gh-ost invocation restored", FIX008,
     "gh-ost --host=replica1.db.internal --port=3306",
     "gh-ost --host=replica-host --allow-on-master"),

    # --- linter logic ---------------------------------------------------------
    ("linter: MM001 pre-8.0.12 INSTANT check disabled", LINTER,
     "            if v < V_INSTANT_INTRODUCED:", "            if False:"),
    ("linter: MM007 partition check disabled", LINTER,
     "if v < V_8_0 and verb in PARTITION_DEFAULT_ONLY_57 and algo and algo != \"DEFAULT\":",
     "if False:"),
    ("linter: MM009 foreign-key check disabled", LINTER,
     "            if not active_off:", "            if False:"),
    ("linter: MM017 gh-ost mode check disabled", LINTER,
     "        if on_replica_mode or (host and _REPLICA_HOSTNAME.search(host)):",
     "        if False:"),
    ("linter: FULLTEXT removed from NO_CONCURRENT_DML", LINTER,
     '    (re.compile(r"\\bADD\\s+FULLTEXT\\s+(?:INDEX|KEY)\\b", re.I),',
     '    (re.compile(r"\\bZZ_NEVER_MATCHES\\b", re.I),'),
    ("linter: VARCHAR removed from NEVER_INSTANT", LINTER,
     '    (re.compile(r"\\b(?:MODIFY|CHANGE)\\s+(?:COLUMN\\s+)?\\S+(?:\\s+\\S+)?\\s+VARCHAR\\s*\\(", re.I),',
     '    (re.compile(r"\\bZZ_NEVER_MATCHES_VARCHAR\\b", re.I),'),
    # NOTE: mutating `_NUL = "\x00"` to `" "` is NOT a valid mutation — a space is
    # still width-preserving and non-merging, so nothing observable changes. The
    # real defect that shipped was `norm()` failing to convert NUL back, which
    # broke every ^\s* anchor after a comment. That is the mutation below.
    ("linter: norm() stops unmasking NUL (comment hides the statement)", LINTER,
     'return re.sub(r"\\s+", " ", unmask_to_space(s)).strip()',
     'return re.sub(r"\\s+", " ", s).strip()'),
    ("linter: whole-file scan stops unmasking NUL", LINTER,
     "    plain = unmask_to_space(masked)", "    plain = masked"),
    ("linter: over-broad type-change pattern returns (MIG-007 false positive)", LINTER,
     '    (re.compile(r"\\bDROP\\s+PRIMARY\\s+KEY\\b(?![^;]*\\bADD\\s+PRIMARY\\s+KEY\\b)", re.I),',
     '    (re.compile(r"\\b(?:MODIFY|CHANGE)\\s+(?:COLUMN\\s+)?[^;]*\\b(?:BIGINT|INT|DECIMAL)\\b", re.I),'),
    ("linter: UNCHECKED_BY_DESIGN declaration removed", LINTER,
     'UNCHECKED_BY_DESIGN = {', 'UNCHECKED_BY_DESIGN_REMOVED = {'),
    ("linter: MM011 stored-program loop check disabled", LINTER,
     "    if not in_program:", "    if False:"),
    ("linter: MM013 sql_log_bin check disabled", LINTER,
     'if re.search(r"\\bsql_log_bin\\s*=\\s*(?:0|OFF)\\b", ln, re.I):',
     'if False:'),

    # --- round 2 (2026-08-06 second review pass) ------------------------------
    ("linter: INSTANT threshold back to 8.0.0", LINTER,
     "V_INSTANT_INTRODUCED = (8, 0, 12)", "V_INSTANT_INTRODUCED = (8, 0, 0)"),
    ("linter: MM026 IF-[NOT]-EXISTS check disabled", LINTER,
     'r"(IF\\s+NOT\\s+EXISTS|IF\\s+EXISTS)", stmt, re.I):',
     'r"(ZZ_NEVER_A|ZZ_NEVER_B)", stmt, re.I):'),
    ("linter: MM027 preserve-triggers check disabled", LINTER,
     '    if "--preserve-triggers" in cmd:', '    if False:'),
    ("linter: backup negation handling removed", LINTER,
     "            if _NEGATION.search(clause):\n                continue",
     "            if False:\n                continue"),
    ("linter: session guard ordering ignored", LINTER,
     "if not any(i < first_ddl for i in guard_lines) and not covered_by_tool_flag:",
     "if not guard_lines and not covered_by_tool_flag:"),
    ("linter: MM010 back to critical", LINTER,
     '    "MM010": {"severity": WARNING,', '    "MM010": {"severity": CRITICAL,'),
    ("matrix: 8.0.0-8.0.11 described as having INSTANT", MATRIX,
     "8.0.0–8.0.11   → no ALGORITHM=INSTANT clause.     Skip to step 2.",
     "8.0.0–8.0.11   → INSTANT exists but not for ADD COLUMN."),
    ("matrix: 8.0.12 clause-introduction note removed", MATRIX,
     "does not exist before MySQL 8.0.12", "is limited before MySQL 8.0.12"),
    ("skill: IF NOT EXISTS idempotency advice returns", SKILL_MD,
     "**MySQL `ALTER TABLE` has no `IF NOT EXISTS` / `IF EXISTS`**",
     "Use `IF NOT EXISTS` / `IF EXISTS`. MySQL supports"),
    ("large: preserve-triggers section removed", LARGE,
     "### 2.1 `--preserve-triggers`", "### 2.1 Trigger notes"),
    ("large: preserve-triggers incompatibility list removed", LARGE,
     "Mutually exclusive with `--no-drop-triggers`, `--no-drop-old-table`, and `--no-swap-tables`.",
     "Works alongside the other flags."),
    # --- round 3 (2026-08-06 third review pass) -------------------------------
    ("linter: verified range swallows every version (MM028 never fires)", LINTER,
     "    ((9, 0, 0), (10, 0, 0),", "    ((9, 0, 0), (999, 0, 0),"),
    ("linter: MM028 removed from the registry", LINTER,
     '    "MM028": {"severity": WARNING,', '    "MM028_REMOVED": {"severity": WARNING,'),
    ("linter: .ddl dropped from directory scanning", LINTER,
     'SCANNED_EXTENSIONS = (".sql", ".ddl"', 'SCANNED_EXTENSIONS = (".sql"'),
    ("linter: unparseable formats silently skipped again", LINTER,
     'UNPARSEABLE_FORMATS = {\n    ".xml"', 'UNPARSEABLE_FORMATS = {\n    ".xxx_disabled"'),
    ("verify: schema-name validation removed", VERIFY,
     'if [[ ! "${SCHEMA}" =~ ^[A-Za-z][A-Za-z0-9_]{0,62}$ ]]; then',
     'if false; then'),
    ("verify: disposable declaration no longer required", VERIFY,
     'if [[ "${MYSQL_MIGRATION_VERIFY_DISPOSABLE:-}" != "yes" ]]; then',
     'if false; then'),
    ("verify: password back on the command line", VERIFY,
     'mysql_exec() { mysql --defaults-file="${DEFAULTS_FILE}" --batch --skip-column-names "$@"; }',
     'mysql_exec() { mysql --host="${MYSQL_HOST:-127.0.0.1}" --user="${MYSQL_USER:-root}" '
     '--password="${MYSQL_PASSWORD:-}" --batch --skip-column-names "$@"; }'),
    ("verify: existing-schema guard removed", VERIFY,
     'if [[ -n "$(mysql_exec --execute="SHOW DATABASES LIKE \'${SCHEMA}\'")" ]]; then',
     'if false; then'),
    ("eval: no criterion is required (harness can never fail)", EVAL,
     "    required: bool = True", "    required: bool = False"),
    ("eval: lint verdict dropped from grading", EVAL,
     "            critical = sum(1 for f in findings if f.severity == LINT.CRITICAL)",
     "            critical = 0"),
    ("eval: skip message no longer says the question is unanswered", EVAL,
     'print("      what a model produces. Treat that question as UNANSWERED until this runs.")',
     'print("      what a model produces.")'),
    ("compose: 8.0.11 instance dropped from the matrix", COMPOSE,
     "  mysql8011:\n    image: mysql:8.0.11", "  mysql8011_disabled:\n    image: mysql:8.0"),
    ("compose: probe ports exposed beyond loopback", COMPOSE,
     'ports: ["127.0.0.1:33057:3306"]', 'ports: ["33057:3306"]'),

    # --- round 4 (2026-08-06 fourth review pass) ------------------------------
    ("linter: MM029 INSTANT+LOCK check disabled", LINTER,
     '        if algo == "INSTANT" and lock and lock != "DEFAULT":', "        if False:"),
    ("linter: MM030 unread-carrier findings suppressed", LINTER,
     "    for desc, count in sorted(skipped_formats.items()):\n        findings.append(Finding(",
     "    for desc, count in []:\n        findings.append(Finding("),
    ("linter: 9.x promoted back to verified", LINTER,
     "    ((8, 4, 0), (8, 5, 0), \"transcribed from the 8.4 manual, 2026-08-06\"),\n]",
     "    ((8, 4, 0), (8, 5, 0), \"transcribed from the 8.4 manual, 2026-08-06\"),\n"
     "    ((9, 0, 0), (10, 0, 0), \"assumed identical to 8.4\"),\n]"),
    ("matrix: 'nothing to lock' claim returns", MATRIX,
     "omit LOCK, or write LOCK=DEFAULT. NONE,",
     "no LOCK clause needed; nothing to lock. NONE,"),
    ("matrix: INSTANT row removed from the LOCK table", MATRIX,
     "| **INSTANT** | (any) |", "| INSTANT_disabled | (any) |"),
    ("skill: INSTANT described as lock-free again", SKILL_MD,
     "all three algorithms can take an exclusive metadata lock",
     "INSTANT operations take no metadata lock"),
    ("anti: AE-17 back to a flat 64 limit", ANTI,
     "| **9.1.0 and later** | **255** |", "| (all versions) | **64** |"),
    ("eval: unpaired scenarios no longer excluded", EVAL,
     "    paired = sorted(with_ids & without_ids)", "    paired = sorted(with_ids | without_ids)"),
    ("eval: optional-criterion gains count as improvement", EVAL,
     "        if delta > 0 and crit.required:", "        if delta > 0:"),
    ("eval: unfenced SQL escapes the linter again", EVAL,
     "    return \"\\n\".join(m.group(0) for m in _BARE_SQL.finditer(response))",
     "    return \"\""),
    ("eval: references no longer injected into the with-skill arm", EVAL,
     "    for rel in referenced_files(fixture):", "    for rel in []:"),

    # --- round 5 (2026-08-06 fifth review pass) -------------------------------
    ("linter: explicit unparseable file scanned as SQL again", LINTER,
     "            if suffix in UNPARSEABLE_FORMATS:\n                # Naming the file",
     "            if False:\n                # Naming the file"),
    ("linter: zero-scan help text back to the stale promise", LINTER,
     "\"extension UNLESS the extension is a known-unparseable carrier \"",
     "\"extension always. \""),
    ("anti: AE-17 prose back to a hardcoded 65th migration", ANTI,
     "the 65th on a\nrelease before 9.1.0, the 256th from 9.1.0 on",
     "number 65"),
    ("anti: AE-17 snippet comment back to Release 1..64", ANTI,
     "-- Every release up to the server's ceiling (64, or 255 from 9.1.0): fine.",
     "-- Release 1..64: fine."),
    ("skill: INSTANT 'accepts no LOCK clause' wording returns", SKILL_MD,
     "**omit the `LOCK` clause or write `LOCK=DEFAULT`; `NONE`, `SHARED` and `EXCLUSIVE` are rejected**",
     "accepts **no `LOCK` clause**"),
    ("matrix: INSTANT LOCK cell back to 'no LOCK clause at all'", MATRIX,
     "| **omit `LOCK`, or `LOCK=DEFAULT`** |", "| **no LOCK clause at all** |"),
    ("eval: SKILL.md injected twice when declared as the reference", EVAL,
     'and pathlib.Path(declared).name != "SKILL.md"', ""),
    ("eval: per-scenario lint gate removed", EVAL,
     "        if gw.lint_critical > max(gwo.lint_critical, 0):",
     "        if False:"),
    ("eval: per-scenario required-criterion gate removed", EVAL,
     "        lost = sorted(k for k, c in criteria.items()\n"
     "                      if c.required and gwo.met[k] and not gw.met[k])",
     "        lost = []"),
    ("coverage: unasserted grand total reinstated", COVERAGE_DOC,
     "Test counts are **not** reproduced here.",
     "| **Total automated** | **999** |\n\nTest counts are **not** reproduced here."),

    # --- round 6 (2026-08-06 sixth review pass) -------------------------------
    ("eval: absolute critical gate removed (delta-only again)", EVAL,
     '    unsafe = [f"{g.scenario} ({g.lint_critical} critical)"\n'
     '              for g in by_arm["with_skill"] if g.lint_critical > max_critical]',
     "    unsafe = []"),
    ("eval: max-critical default relaxed from 0", EVAL,
     'ap.add_argument("--max-critical", type=int, default=0, metavar="N",',
     'ap.add_argument("--max-critical", type=int, default=99, metavar="N",'),
    ("eval: lint error back to a -1 score sentinel", EVAL,
     "            lint_error = True", "            critical = -1"),
    ("eval: lint-error gate removed", EVAL,
     '    lint_errors = [g.scenario for g in by_arm["with_skill"] + by_arm["without_skill"]\n'
     "                   if g.lint_error]",
     "    lint_errors = []"),
    ("eval: lock_explicit penalises the correct INSTANT form again", EVAL,
     'r"LOCK\\s*=\\s*(NONE|SHARED|EXCLUSIVE|DEFAULT)|ALGORITHM\\s*=\\s*INSTANT"',
     'r"LOCK\\s*=\\s*(NONE|SHARED|EXCLUSIVE)"'),
    ("skill: stale 'read whatever its extension' sentence returns", SKILL_MD,
     "A file named explicitly is scanned as SQL only if its extension is **unknown**",
     "a file named explicitly is read whatever its extension"),

    ("baseline: exemption widened to the whole file", BASELINE,
     "MM014 | references/migration-anti-examples.md | ALTER TABLE events ADD PARTITION (PARTITION p2026_09 VALUES LESS THAN (20260901));",
     "MM014 | references/migration-anti-examples.md | ALTER TABLE"),
]


def run_suite(root: pathlib.Path) -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "skills/mysql-migration/", "-q", "--no-header", "-x"],
        cwd=root, capture_output=True, text=True, timeout=300,
    )
    return proc.returncode == 0, (proc.stdout + proc.stderr)[-400:]


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Mutation sweep for the mysql-migration skill.")
    ap.add_argument("--list", action="store_true", help="print the mutations and exit")
    ap.add_argument("-k", metavar="SUBSTRING", help="only run mutations whose name matches")
    args = ap.parse_args(argv)

    selected = [m for m in MUTATIONS if not args.k or args.k.lower() in m[0].lower()]
    if args.list:
        for name, rel, _, _ in selected:
            print(f"{rel:52s}  {name}")
        print(f"\n{len(selected)} mutation(s)")
        return 0
    if not selected:
        print(f"no mutation matches {args.k!r}", file=sys.stderr)
        return 2

    base_ok, base_out = run_suite(REPO)
    if not base_ok:
        print("BASELINE IS RED — fix that before mutating\n" + base_out)
        return 2
    print("baseline: green\n")

    killed, survived, errors = [], [], []
    with tempfile.TemporaryDirectory() as td:
        work = pathlib.Path(td) / "repo"
        for name, rel, old, new in selected:
            if work.exists():
                shutil.rmtree(work)
            work.mkdir(parents=True)
            shutil.copytree(SKILL, work / "skills" / "mysql-migration")
            shutil.copy(REPO / "pytest.ini", work / "pytest.ini")

            target = work / "skills" / "mysql-migration" / rel
            text = target.read_text(encoding="utf-8")
            count = text.count(old)
            if count == 0:
                errors.append((name, "mutation string not found — harness bug"))
                print(f"  ERROR    {name}  (pattern absent)")
                continue
            # Replace ALL occurrences: leaving a copy behind makes a real
            # assertion look vacuous when it is not.
            target.write_text(text.replace(old, new), encoding="utf-8")

            ok, out = run_suite(work)
            if ok:
                survived.append((name, count))
                print(f"  SURVIVED {name}  ({count} site(s) mutated)")
            else:
                killed.append(name)
                print(f"  killed   {name}  ({count} site(s))")

    print(f"\nkilled {len(killed)}/{len(selected)}  survived {len(survived)}  errors {len(errors)}")
    for n, c in survived:
        print(f"  SURVIVED: {n} ({c} sites)")
    for n, why in errors:
        print(f"  ERROR: {n} — {why}")
    return 0 if not survived and not errors else 1


if __name__ == "__main__":
    sys.exit(main())

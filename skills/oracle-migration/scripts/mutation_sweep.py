#!/usr/bin/env python3
"""Mutation sweep for the oracle-migration skill.

A passing test suite proves nothing about the assertions inside it. This harness
introduces one deliberate defect at a time — into the checker, a golden fixture, or a
reference document — and requires the suite to FAIL. A mutation the suite still passes
is a SURVIVOR: an assertion that is not load-bearing, or a fact nothing guards.

Usage:
    python3 scripts/mutation_sweep.py            # run every mutation
    python3 scripts/mutation_sweep.py --list     # show them without running
    python3 scripts/mutation_sweep.py -k ORA010  # filter by id substring
"""

from __future__ import annotations

import argparse
import dataclasses
import pathlib
import shutil
import subprocess
import sys
import tempfile

SKILL_DIR = pathlib.Path(__file__).resolve().parents[1]
TESTS = SKILL_DIR / "scripts" / "tests"


@dataclasses.dataclass(frozen=True)
class Mutation:
    mid: str
    target: str          # path relative to the skill dir
    old: str
    new: str
    rationale: str       # which guarantee this mutation attacks


M: list[Mutation] = []


def mut(mid: str, target: str, old: str, new: str, rationale: str) -> None:
    M.append(Mutation(mid, target, old, new, rationale))


# ======================================================================================
# 1. Checker logic — each mutation disables exactly one check or corrupts its gating
# ======================================================================================

LINT = "scripts/lint_migration.py"

mut("L01", LINT, 'if stmt_is_ddl and not lock_timeout_set:', 'if False:',
    "ORA001 must fire when DDL_LOCK_TIMEOUT is unset")
mut("L02", LINT, 'ADD\\s+CONSTRAINT\\s+(\\w+)\\s+(FOREIGN\\s+KEY|CHECK|UNIQUE|PRIMARY\\s+KEY)',
    'ADD\\s+CONSTRAINT\\s+(\\w+)\\s+(NEVERMATCHES)',
    "ORA002 must detect an unvalidated constraint addition")
mut("L03", LINT, 'if not re.search(r"\\bUPDATE\\s+(GLOBAL\\s+)?INDEXES\\b", upper) and gi != "no":',
    'if False:', "ORA003 must fire on partition DDL lacking UPDATE INDEXES")
mut("L04", LINT, 'saw_bulk_dml = saw_bulk_dml or unbounded\n                if unbounded:',
    'saw_bulk_dml = saw_bulk_dml or unbounded\n                if False:',
    "ORA004 must fire on unbounded DML")
mut("L05", LINT, 'if not re.search(r"\\bONLINE\\b", upper):\n                    findings.append(\n                        f(\n                            "ORA005",',
    'if False:\n                    findings.append(\n                        f(\n                            "ORA005",',
    "ORA005 must fire on ALTER TABLE MOVE without ONLINE")
mut("L06", LINT, 'and not re.search(r"\\bONLINE\\b", upper)\n                and _target_table(t) not in created_tables',
    'and False',
    "ORA006 must fire on a non-online index build")
mut("L07", LINT, 'if dropped or drops_unused:', 'if False:',
    "ORA007 must fire on any column drop without a usable snapshot")
mut("L08", LINT, 'if not re.search(r"\\b(DBA_OBJECTS|ALL_OBJECTS|USER_OBJECTS)\\b", upper):',
    'if False:', "ORA008 must catch DBA_EXTENTS.data_object_id")
mut("L09", LINT, 'if len(rename_to_lines) >= 2:', 'if False:',
    "ORA009 must catch a two-statement rename cutover")
mut("L10", LINT, 'if has_structural_ddl:', 'if False:',
    "ORA010 must catch Flashback Table used after structural DDL")
mut("L11", LINT, 'r"\\bIF\\b[^;\\n]{0,80}\\bNUM_ERRORS\\b"\n                    r"|\\bNUM_ERRORS\\s*(?:>|<|!=|=(?!>))",',
    'r"\\bNUM_ERRORS\\b",',
    "ORA011 must require the gate to be ON num_errors, not merely near it")
mut("L12", LINT, 'if re.search(r"\\bFINISH_REDEF_TABLE\\b", upper) and not re.search(\n                r"\\bDML_LOCK_TIMEOUT\\b", upper\n            ):',
    'if False:', "ORA012 must require an explicit dml_lock_timeout")
mut("L13", LINT, 'if re.search(r"\\bNOLOGGING\\b", hint.group(1), re.IGNORECASE):',
    'if False:', "ORA013 must catch NOLOGGING written as a hint")
mut("L14", LINT, 'if re.search(r"\\bDBMS_LOCK\\.SLEEP\\b", upper):', 'if False:',
    "ORA014 must flag DBMS_LOCK.SLEEP")
mut("L15", LINT, 'if mm and "NOT NULL" not in upper:', 'if False:',
    "ORA015 must require MODIFY classification")
mut("L16", LINT, 'if stmt_is_ddl and uncommitted_dml_line is not None:', 'if False:',
    "ORA016 must catch uncommitted DML before DDL")
mut("L17", LINT, 'if re.match(r"^\\s*TRUNCATE\\s+TABLE\\b", t, re.IGNORECASE):', 'if False:',
    "ORA017 must flag TRUNCATE")
mut("L18", LINT, 'if re.search(r"\\bRENAME\\s+COLUMN\\b", upper):', 'if False:',
    "ORA018 must flag an in-place column rename")
mut("L19", LINT, 'if re.search(r"\\bALTER\\s+INDEX\\b[\\s\\S]*\\bREBUILD\\b", upper) and not re.search(\n                r"\\bONLINE\\b", upper\n            ):',
    'if False:', "ORA019 must flag an offline index rebuild")
mut("L20", LINT, 'if cname not in novalidate_constraints:', 'if False:',
    "ORA020 must flag VALIDATE with no NOVALIDATE origin")
mut("L21", LINT, 'if saw_bulk_dml and not saw_dbms_stats:', 'if False:',
    "ORA021 must flag a missing DBMS_STATS refresh")
mut("L22", LINT, 'r"(?:--|/\\*)[^\\n]*\\b(atomic|atomically)\\b", sql, re.IGNORECASE',
    'r"(?:--|/\\*)[^\\n]*\\b(NEVERMATCHES)\\b", sql, re.IGNORECASE',
    "ORA022 must catch an atomicity claim over multiple DDL")
mut("L23", LINT, 'if nologging_seen_line and not logging_restored:', 'if False:',
    "ORA023 must flag NOLOGGING without a recoverability plan")
mut("L24", LINT, 'if re.search(r"\\bDROP\\s+TABLE\\b[\\s\\S]*\\bPURGE\\b", upper):', 'if False:',
    "ORA024 must flag DROP TABLE PURGE")
mut("L25", LINT, 'if re.search(r"\\bSET\\s+UNUSED\\b", upper):', 'if False:',
    "ORA025 must note SET UNUSED is not reversible")

mut("L26", LINT, 'if tv.kind == TimeoutValue.ZERO:', 'if False:',
    "ORA026 must fire when DDL_LOCK_TIMEOUT is explicitly 0")
mut("L27", LINT,
    'elif tv.number is not None and tv.number > _DDL_LOCK_TIMEOUT_SANE_MAX:',
    'elif False:', "ORA027 must fire on a DDL_LOCK_TIMEOUT larger than any window")
mut("L28", LINT, 'elif tv.kind == TimeoutValue.INVALID:', 'elif False:',
    "ORA028 must fire on a DDL_LOCK_TIMEOUT value Oracle would reject")
mut("L29", LINT, 'elif tv.kind == TimeoutValue.DYNAMIC:', 'elif False:',
    "ORA029 must fire when the timeout comes from a substitution variable")

mut("L30", LINT, 'elif _ANY_RESTORE_POINT_RE.search(t):', 'elif False:',
    "ORA030 must fire on a normal (non-GUARANTEE) restore point")

mut("L31", LINT, 'if destructive and partial_only:', 'if False:',
    "ORA031 must explain why a partial CTAS did not count as a backup")
mut("L32", LINT, 'if ed in {"SE2", "SE", "XE", "STANDARD"}:', 'if False:',
    "ORA032 must fire when a guaranteed restore point is proposed on SE2/XE")

# Gating / calibration logic, not individual checks.
# Numbered from L50 so the per-check block above stays aligned one-to-one with the
# ORA<nn> codes: a mutation's id says which half it belongs to without a lookup table.
mut("L50", LINT, 'if _FILE_BOUNDARY_RE.search(stmt.raw):\n                lock_timeout_set = False',
    'if False:\n                lock_timeout_set = False',
    "session state must reset at a migration-file boundary")
mut("L51", LINT, 'r"^\\s*(ALTER\\s+TABLE|ALTER\\s+INDEX|CREATE\\s+(UNIQUE\\s+)?INDEX|"\n            r"DROP\\s+TABLE|DROP\\s+INDEX|TRUNCATE\\s+TABLE|COMMENT\\s+ON|RENAME\\b)",',
    'r"^\\s*(ALTER\\s+TABLE|ALTER\\s+INDEX|CREATE\\s+(UNIQUE\\s+)?INDEX|CREATE\\s+TABLE|"\n            r"DROP\\s+TABLE|DROP\\s+INDEX|TRUNCATE\\s+TABLE|COMMENT\\s+ON|RENAME\\b)",',
    "CREATE TABLE must stay out of the ORA001 lock-contention set (false positive)")
mut("L52", LINT, 'or _SINGLE_KEY_DML_RE.search(t)', 'or False',
    "a single-key UPDATE must not be reported as unbounded (false positive)")
mut("L53", LINT, 'if _PLSQL_START_RE.match(blanked[i:]):', 'if False:',
    "PL/SQL blocks must not be split on internal semicolons")
mut("L54", LINT, '+ self._ee_suffix("REBUILD ONLINE"),', '+ "",',
    "edition-specific wording must reach the ORA019 detail")
mut("L55", LINT,
    'if v in {"12.1", "12c", "11.2", "11g"}:',
    'if False:',
    "the 12.1-vs-12.2 MOVE ONLINE gate must change the ORA005 advice")
mut("L56", LINT,
    'if self.ctx.edition.upper() in {"SE2", "SE", "XE", "STANDARD"}:\n            return (\n                "{} requires Enterprise Edition',
    'if False:\n            return (\n                "{} requires Enterprise Edition',
    "SE2 must get the no-ONLINE-available wording")
mut("L58", LINT, 'if _ATOMIC_DENIAL_RE.search(cm.group(0)):\n                    continue',
    'if False:\n                    continue',
    "ORA022 must not fire on a comment that DENIES atomicity (false positive)")
mut("L59", LINT, 'recovery_ready = bool(rename_pairs) and _has_reverse_rename(sql, rename_pairs)',
    'recovery_ready = False',
    "a cutover with a prepared reverse rename must be downgraded, not called critical")
mut("L60", LINT, 'severity=WARNING if recovery_ready else None,', 'severity=None,',
    "the ORA009 severity downgrade must reach the emitted finding")
mut("L61", LINT, 'any(_STRUCTURAL_DDL_RE.search(st.text) for st in stmts)', 'False',
    "structural-DDL detection must be per statement, not over the whole file")
mut("L57", LINT, 'def blank_comments_and_literals(sql: str) -> str:',
    'def blank_comments_and_literals(sql: str) -> str:\n    return sql  # mutation',
    "comments/literals must be masked before SQL matching")

mut("L62", LINT, 'lock_timeout_set = tv.protects', 'lock_timeout_set = True',
    "DDL_LOCK_TIMEOUT = 0 must NOT satisfy the ORA001 gate — presence is not protection")
mut("L63", LINT, 'if self.ctx.small_enough_to_validate_inline:', 'if False:',
    "ORA002 must soften below the scorecard's two-step row threshold")
mut("L64", LINT,
    'return self.rows is not None and self.rows < CONSTRAINT_TWO_STEP_ROW_THRESHOLD',
    'return False',
    "the ORA002 threshold must come from the same constant the scorecard cites")
mut("L65", LINT, 'and gi != "no"', '',
    "an explicit global-indexes=no must suppress ORA003 (false positive)")
mut("L67", LINT, 'created_tables.add(ct.group(1).upper().strip(\'"\'))', 'pass',
    "objects the script itself creates must be exempt from live-table checks")
mut("L68", LINT, 'and _target_table(t) not in created_tables\n            ):',
    'and True\n            ):',
    "ORA006 must not fire on an index built on an interim table (false positive)")
mut("L66", LINT, 'severity=WARNING if covered else None,', 'severity=None,',
    "an irreversible statement with a matching snapshot must be downgraded")

mut("L69", LINT, 'target_snaps = snapshots.get(target, []) if target else []',
    'target_snaps = [sn for group in snapshots.values() for sn in group]',
    "a snapshot of a DIFFERENT table must not downgrade a destructive statement")
mut("L70", LINT, 'snapshots.setdefault(src, []).append(', 'snapshots.setdefault("", []).append(',
    "the snapshot's SOURCE table must be the key, not just that a CTAS happened")
mut("L71", LINT, 'return self.kind in (self.VALID, self.DYNAMIC)', 'return True',
    "an invalid or zero timeout must not count as protection")
mut("L72", LINT, 'if n < 0 or n > _DDL_LOCK_TIMEOUT_MAX:', 'if False:',
    "out-of-range timeout literals must be classified invalid")

mut("L73", LINT, 'if _GUARANTEED_RESTORE_POINT_RE.search(t):',
    'if _ANY_RESTORE_POINT_RE.search(t):',
    "a NORMAL restore point must not be accepted as a recovery artefact")
mut("L74", LINT, r"GUARANTEE\s+FLASHBACK\s+DATABASE", r"GUARANTEE?\s*FLASHBACK?\s*DATABASE?",
    "the GUARANTEE keyword must be required by the pattern, not optional")

mut("L75", LINT, 'if not _tail_is_trivial(tail):', 'if False:',
    "a CTAS with a WHERE/JOIN/set-operation tail must not count as a full copy")
mut("L76", LINT, 'return self.kind == self.FULL\n\n    def covers_column',
    'return True\n\n    def covers_column',
    "whole-table destruction must require a whole-table copy")
mut("L77", LINT, 'return up <= self.columns and bool(self.columns - up)',
    'return True',
    "a targeted snapshot must contain every dropped column and a surviving key")
mut("L78", LINT, '                    restore_point_taken = True',
    '                    restore_point_taken = False',
    "a guaranteed restore point on EE must still downgrade the destructive finding")

mut("L79", LINT, 'elif ed in {"EE", "ENTERPRISE"}:', 'elif True:',
    "an UNKNOWN edition must not be treated as EE — Gate 1 says assume SE2")
mut("L80", LINT, 'any(sn.covers_columns(dropped) for sn in target_snaps)', 'True',
    "a column drop must require a copy containing those specific columns")
mut("L81", LINT, 'dropped = _dropped_columns(t)', 'dropped = set()',
    "the dropped column names must be extracted so targeted coverage can be judged")

mut("L82", LINT, 'and not (self.columns - up)', 'and False',
    "a copy of ONLY the doomed columns has no surviving key to MERGE back on")
mut("L83", LINT, 'm.group(1).upper() not in _SQL_TAIL_KEYWORDS', 'True',
    "a keyword after FROM must not be mistaken for a table alias")
mut("L84", LINT, '"copy" if covered_by_copy else "restore-point" if restore_point_taken',
    '"copy" if (covered_by_copy or restore_point_taken) else "restore-point" if False',
    "a restore point must not be described as a table copy to MERGE back from")

mut("L85", LINT, 'drops_unused = bool(re.search(r"\\bDROP\\s+UNUSED\\s+COLUMNS\\b", upper))',
    'drops_unused = False',
    "DROP UNUSED COLUMNS must still trigger the destructive-statement path")

# ======================================================================================
# 2. Golden fixtures — the corrected technical facts must be guarded
# ======================================================================================

G = "scripts/tests/golden/"

mut("F01", G + "011_column_type_without_redef.json",
    "increases precision and scale together", "requires a full table rewrite",
    "ORA-011 must not revert to calling a widening a rewrite")
mut("F02", G + "011_column_type_without_redef.json", "ORA-01440", "ORA-99999",
    "ORA-011 must name the real narrowing error")
mut("F03", G + "003_missing_rollback.json", "restore/PITR", "compensating-DDL only",
    "ORA-003 must classify a column drop as restore/PITR")
mut("F04", G + "012_rowid_chunking_unexecutable.json", "ORA-00904", "ORA-00942",
    "ORA-012 must name the invalid-identifier error")
mut("F05", G + "013_rename_swap_not_atomic.json", "implicit COMMIT", "single transaction",
    "ORA-013 must state each rename commits independently")
mut("F06", G + "014_flashback_after_structural_ddl.json", "TO BEFORE DROP", "TO TIMESTAMP",
    "ORA-014 must distinguish the recycle-bin flashback")
mut("F07", G + "015_copy_dependents_unchecked.json", "DBA_REDEFINITION_ERRORS", "DBMS_OUTPUT",
    "ORA-015 must direct triage at the errors view")
mut("F08", G + "016_nologging_hint_noop.json", "not a hint", "a documented hint",
    "ORA-016 must state NOLOGGING is not a hint")
mut("F09", G + "022_rename_column_live.json", "9i Release 2", "23ai",
    "ORA-022 must carry the correct RENAME COLUMN version")
mut("F10", G + "017_widening_is_not_a_rewrite.json", '"expect_findings": []',
    '"expect_findings": ["ORA005"]',
    "the widening fixture must not expect a rewrite finding")
mut("F11", G + "007_well_formed_phased.json",
    "-- Phase 5 (next release): V12__cleanup.sql\\nALTER SESSION SET DDL_LOCK_TIMEOUT = 3;",
    "-- Phase 5 (next release): V12__cleanup.sql",
    "phase 5 must re-set DDL_LOCK_TIMEOUT in its own session")
mut("F12", G + "008_good_dbms_redefinition.json",
    "IF num_errors > 0 THEN", "IF FALSE THEN",
    "the good redefinition fixture must genuinely gate on num_errors")
mut("F13", G + "008_good_dbms_redefinition.json",
    "dml_lock_timeout => 30", "NULL => NULL",
    "the good redefinition fixture must pass dml_lock_timeout")
mut("F14", G + "019_se2_online_unavailable.json", '"edition": "SE2"',
    '"edition": "EE"',
    "the SE2 fixture must actually be linted as SE2")
mut("F15", G + "020_move_online_version_gate.json", '"version": "12.1"', '"version": "19c"',
    "the 12.1 fixture must actually be linted as 12.1")
mut("F16", G + "018_uncommitted_dml_before_ddl.json",
    '"expect_findings": [\n    "ORA016"\n  ]',
    '"expect_findings": []',
    "a defect fixture must declare at least one expected finding")

# ======================================================================================
# 3. Reference documents — the corrected facts must be guarded by contract tests
# ======================================================================================

mut("D01", "references/oracle-ddl-lock-matrix.md",
    "Supported since **9i Release 2**", "Supported since **23ai**",
    "the lock matrix must carry the correct RENAME COLUMN version")
mut("D02", "references/oracle-ddl-lock-matrix.md",
    "`DROP INDEX ... ONLINE` (12.1+)", "`DROP INDEX ... ONLINE` (21c+)",
    "DROP INDEX ONLINE must be gated at 12.1")
mut("D03", "references/oracle-ddl-lock-matrix.md", "**ORA-01440**", "**ORA-01441**",
    "the narrowing error code must be correct")
mut("D04", "references/large-table-migration.md", "has no `DATA_OBJECT_ID` column",
    "exposes a `DATA_OBJECT_ID` column",
    "the ROWID chunking section must state the column does not exist")
mut("D05", "references/large-table-migration.md",
    "### The cutover is two statements, not an atomic swap",
    "### Atomic swap",
    "the CTAS cutover must not be described as atomic")
mut("D06", "references/large-table-migration.md",
    "RAISE_APPLICATION_ERROR(-20001,", "DBMS_OUTPUT.PUT_LINE(",
    "the redefinition example must halt on num_errors")
mut("D07", "references/oracle-version-licensing-matrix.md",
    "**9.2** | Metadata-only", "**12.1** | Metadata-only",
    "the licensing matrix must carry the correct RENAME COLUMN version")
mut("D08", "references/migration-anti-examples.md",
    "**`NOLOGGING` is not a hint.**", "**`NOLOGGING` is a hint.**",
    "AE-12 must state NOLOGGING is not a hint")
mut("D09", "SKILL.md", "Assume **12.1** (most restrictive)", "Assume 12c (most restrictive)",
    "Gate 1 must demand an exact release")
mut("D10", "SKILL.md", "**Oracle 9i Release 2**", "**Oracle 23ai**",
    "SKILL.md must carry the correct RENAME COLUMN version")
mut("D11", "SKILL.md", "**cannot cross a structural DDL**", "recovers across any DDL",
    "SKILL.md must state the Flashback restriction")
mut("D12", "SKILL.md", "abort-before-cutover", "always-rollbackable",
    "the rollback taxonomy must survive")

mut("D13", "references/oracle-version-licensing-matrix.md",
    "| `NULL` — **the default** |", "| `0` — **the default** |",
    "dml_lock_timeout's default is NULL (waits), not 0 (NOWAIT)")
mut("D14", "references/large-table-migration.md",
    "Its default is NULL", "Its default is 0",
    "same dml_lock_timeout default in the worked example")
mut("D15", "references/oracle-version-licensing-matrix.md",
    "| **Flashback Table** (`TO SCN/TIMESTAMP`) | \u2705 | \u274c | \u274c |",
    "| **Flashback Table** (`TO SCN/TIMESTAMP`) | \u2705 | \u2705 | \u2705 |",
    "Flashback Table TO SCN/TIMESTAMP is EE-only; SE2 must not be told it has it")
mut("D16", "SKILL.md", "Enterprise Edition only", "available on every edition",
    "SKILL.md item 11 must carry the Flashback edition gate")

mut("D17", "references/large-table-migration.md",
    "`GUARANTEE FLASHBACK DATABASE` is not optional wording",
    "Restore points",
    "the normal-vs-guaranteed restore point distinction must stay documented")
mut("D18", "references/large-table-migration.md",
    "*a target, not a guarantee*", "a hard guarantee",
    "DB_FLASHBACK_RETENTION_TARGET must not be described as a guarantee")

mut("D19", "references/large-table-migration.md",
    "provides no\n**guaranteed** recovery", "provides no recovery at all",
    "a normal restore point may still work; the claim must be 'no guaranteed recovery'")
mut("D20", "references/large-table-migration.md",
    "### A copy is only a backup if it copies everything",
    "### Backups",
    "the partial-snapshot distinction must stay documented")





# ======================================================================================
# Runner
# ======================================================================================


def run_suite(cwd: pathlib.Path) -> bool:
    """True when the suite passes."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "scripts/tests", "-q", "-x", "--no-header", "-p",
         "no:cacheprovider"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("-k", dest="filter", default=None)
    args = ap.parse_args(argv)

    muts = [m for m in M if not args.filter or args.filter.lower() in
            (m.mid + m.target + m.rationale).lower()]

    if args.list:
        for m in muts:
            print(f"{m.mid}  {m.target}\n      {m.rationale}")
        print(f"\n{len(muts)} mutation(s)")
        return 0

    with tempfile.TemporaryDirectory(prefix="oramut-") as td:
        base = pathlib.Path(td) / "skill"
        shutil.copytree(SKILL_DIR, base, ignore=shutil.ignore_patterns("__pycache__"))

        if not run_suite(base):
            print("BASELINE FAILS — fix the suite before running the sweep", file=sys.stderr)
            return 2

        pristine = {
            m.target: (base / m.target).read_text(encoding="utf-8") for m in muts
        }

        killed, survived, errors = [], [], []
        for m in muts:
            path = base / m.target
            original = pristine[m.target]
            if m.old not in original:
                errors.append((m, "anchor not found"))
                print(f"ERROR    {m.mid}  anchor not found in {m.target}")
                continue
            count = original.count(m.old)
            path.write_text(original.replace(m.old, m.new), encoding="utf-8")
            try:
                passed = run_suite(base)
            finally:
                path.write_text(original, encoding="utf-8")

            if passed:
                survived.append(m)
                print(f"SURVIVED {m.mid}  ({count}x)  {m.rationale}")
            else:
                killed.append(m)
                print(f"killed   {m.mid}  ({count}x)  {m.rationale}")

    print(
        f"\n{len(killed)} killed, {len(survived)} survived, {len(errors)} error(s) "
        f"out of {len(muts)}"
    )
    for m, why in errors:
        print(f"  ERROR    {m.mid}: {why}")
    for m in survived:
        print(f"  SURVIVED {m.mid}: {m.rationale}")
    return 0 if not survived and not errors else 1


if __name__ == "__main__":
    sys.exit(main())

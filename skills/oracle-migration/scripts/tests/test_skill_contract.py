"""Contract tests for oracle-migration skill."""

import os
import pathlib
import re
import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
REFS_DIR = SKILL_DIR / "references"


def _ref(name: str) -> str:
    return (REFS_DIR / name).read_text(encoding="utf-8")


class TestFrontmatter:
    def test_name(self):
        assert "name: oracle-migration" in SKILL_MD

    def test_description_keywords(self):
        desc_area = SKILL_MD[:800].lower()
        for kw in ["alter table", "ddl", "dbms_redefinition", "novalidate",
                    "ddl_lock_timeout", "auto-commit"]:
            assert kw in desc_area, f"description missing keyword: {kw}"


class TestMandatoryGates:
    def test_gate_1_context(self):
        assert "Gate 1" in SKILL_MD
        lower = SKILL_MD.lower()
        assert "oracle version" in lower
        assert "edition" in lower
        assert "rac" in lower

    def test_gate_1_stop_proceed(self):
        assert "**STOP**" in SKILL_MD
        assert "**PROCEED**" in SKILL_MD

    def test_gate_2_scope(self):
        assert "Gate 2" in SKILL_MD
        for mode in ["review", "generate", "plan"]:
            assert mode in SKILL_MD.lower()

    def test_gate_3_risk(self):
        assert "Gate 3" in SKILL_MD
        for risk in ["SAFE", "WARN", "UNSAFE"]:
            assert risk in SKILL_MD

    def test_gate_4_completeness(self):
        assert "Gate 4" in SKILL_MD

    def test_all_gates_have_stop(self):
        stop_count = SKILL_MD.count("**STOP**")
        assert stop_count >= 3


class TestDepthSelection:
    def test_three_depths(self):
        for depth in ["Lite", "Standard", "Deep"]:
            assert depth in SKILL_MD

    def test_force_standard_signals(self):
        lower = SKILL_MD.lower()
        for signal in ["column type change", "not null", "partition ddl"]:
            assert signal in lower, f"missing signal: {signal}"

    def test_reference_loading_by_depth(self):
        assert "oracle-ddl-lock-matrix.md" in SKILL_MD
        assert "large-table-migration.md" in SKILL_MD


class TestDegradationModes:
    def test_four_modes_defined(self):
        for mode in ["Full", "Degraded", "Minimal", "Planning"]:
            assert mode in SKILL_MD

    def test_never_fabricate(self):
        lower = SKILL_MD.lower()
        assert "never" in lower and "claim" in lower

    def test_assumptions_documented(self):
        assert "Uncovered Risk" in SKILL_MD or "uncovered risk" in SKILL_MD.lower()


class TestDDLSafetyChecklist:
    def test_subsection_count(self):
        for sub in ["5.1", "5.2", "5.3", "5.4"]:
            assert sub in SKILL_MD

    def test_ddl_autocommit(self):
        lower = SKILL_MD.lower()
        assert "auto-commit" in lower or "autocommit" in lower or "auto commit" in lower

    def test_ddl_lock_timeout(self):
        assert "DDL_LOCK_TIMEOUT" in SKILL_MD

    def test_novalidate_keyword(self):
        assert "NOVALIDATE" in SKILL_MD
        assert "VALIDATE" in SKILL_MD

    def test_online_keyword(self):
        assert "ONLINE" in SKILL_MD

    def test_backward_compatibility(self):
        lower = SKILL_MD.lower()
        assert "deployment order" in lower or "backward" in lower

    def test_rollback_manual(self):
        lower = SKILL_MD.lower()
        assert "manual" in lower and "rollback" in lower


class TestExecutionPlan:
    def test_five_phases(self):
        lower = SKILL_MD.lower()
        for kw in ["additive", "backfill", "app deploy", "validation", "cleanup"]:
            assert kw in lower, f"missing phase: {kw}"

    def test_references_large_table(self):
        assert "large-table-migration.md" in SKILL_MD


class TestAntiExamples:
    def test_min_count(self):
        ae_count = sum(1 for line in SKILL_MD.split("\n") if line.strip().startswith("### AE-"))
        assert ae_count >= 6

    def test_wrong_right_pairs(self):
        assert SKILL_MD.count("-- WRONG") >= 5
        assert SKILL_MD.count("-- RIGHT") >= 5

    def test_ddl_lock_timeout_anti_example(self):
        lower = SKILL_MD.lower()
        assert "ora-00054" in lower

    def test_extended_ref(self):
        assert "migration-anti-examples.md" in SKILL_MD


class TestScorecard:
    def test_critical_tier(self):
        lower = SKILL_MD.lower()
        assert "critical" in lower
        assert "any fail" in lower or "any failure" in lower

    def test_standard_tier(self):
        assert "4 of 5" in SKILL_MD or "4/5" in SKILL_MD

    def test_hygiene_tier(self):
        assert "3 of 4" in SKILL_MD or "3/4" in SKILL_MD

    def test_critical_items(self):
        lower = SKILL_MD.lower()
        assert "ddl_lock_timeout" in lower
        assert "auto-commit" in lower or "autocommit" in lower or "auto commit" in lower
        assert "rollback" in lower

    def test_verdict_format(self):
        assert "X/12" in SKILL_MD or "PASS/FAIL" in SKILL_MD


class TestOutputContract:
    def test_nine_sections(self):
        for section in ["9.1", "9.2", "9.3", "9.4", "9.5", "9.6", "9.7", "9.8", "9.9"]:
            assert section in SKILL_MD

    def test_uncovered_risks_mandatory(self):
        lower = SKILL_MD.lower()
        assert "never empty" in lower or "mandatory" in lower

    def test_volume_rules(self):
        assert "volume" in SKILL_MD.lower()

    def test_scorecard_in_output(self):
        lower = SKILL_MD.lower()
        assert "scorecard" in lower and "data basis" in lower


class TestReferenceFiles:
    def test_ddl_matrix_exists(self):
        content = _ref("oracle-ddl-lock-matrix.md")
        assert len(content.splitlines()) >= 80

    def test_ddl_matrix_keywords(self):
        content = _ref("oracle-ddl-lock-matrix.md")
        for kw in ["Exclusive", "ONLINE", "NOVALIDATE", "DDL_LOCK_TIMEOUT"]:
            assert kw in content

    def test_ddl_matrix_operations(self):
        content = _ref("oracle-ddl-lock-matrix.md").lower()
        for op in ["add column", "drop column", "create index", "modify column"]:
            assert op in content, f"DDL matrix missing: {op}"

    def test_large_table_exists(self):
        content = _ref("large-table-migration.md")
        assert len(content.splitlines()) >= 100

    def test_large_table_keywords(self):
        content = _ref("large-table-migration.md")
        for kw in ["DBMS_REDEFINITION", "CTAS", "ROWID", "COMMIT"]:
            assert kw in content

    def test_anti_examples_exists(self):
        content = _ref("migration-anti-examples.md")
        assert len(content.splitlines()) >= 80

    def test_anti_examples_numbering(self):
        content = _ref("migration-anti-examples.md")
        assert "AE-7" in content
        ae_count = sum(1 for line in content.split("\n") if "## AE-" in line)
        assert ae_count >= 5

    def test_all_refs_mentioned_in_skill(self):
        for f in REFS_DIR.glob("*.md"):
            assert f.name in SKILL_MD, f"{f.name} not in SKILL.md"


class TestLineCount:
    def test_max_lines(self):
        lines = len(SKILL_MD.splitlines())
        assert lines <= 420, f"SKILL.md is {lines} lines (budget: 420)"


class TestCrossFileConsistency:
    def test_exclusive_in_matrix(self):
        assert "Exclusive" in _ref("oracle-ddl-lock-matrix.md")

    def test_dbms_redef_in_large_table(self):
        assert "DBMS_REDEFINITION" in _ref("large-table-migration.md")

    def test_ctas_in_large_table(self):
        assert "CTAS" in _ref("large-table-migration.md")

    def test_ddl_lock_timeout_in_skill(self):
        assert "DDL_LOCK_TIMEOUT" in SKILL_MD

    def test_novalidate_in_matrix(self):
        assert "NOVALIDATE" in _ref("oracle-ddl-lock-matrix.md")

    def test_dbms_stats_in_anti_examples(self):
        assert "DBMS_STATS" in _ref("migration-anti-examples.md")


# ======================================================================================
# Fact drift guards
#
# Every entry below pins a technical claim that was WRONG in an earlier revision of this
# skill and was corrected against Oracle documentation. Without these, a revert restores
# the wrong fact silently — the rest of the suite only checks structure and keywords.
# Each guard asserts the corrected form is present AND the known-wrong form is absent.
# ======================================================================================


def _ref_or_skill(name: str) -> str:
    """Read an asset named relative to the skill root (`references/x.md` or `SKILL.md`)."""
    if name == "SKILL.md":
        return SKILL_MD
    return _ref(name.split("/", 1)[1] if name.startswith("references/") else name)


# (file, must_contain, must_not_contain, why)
FACT_GUARDS = [
    (
        "references/oracle-ddl-lock-matrix.md",
        "Supported since **9i Release 2**",
        ["RENAME COLUMN (12c+)", "RENAME COLUMN supported natively\n"],
        "ALTER TABLE ... RENAME COLUMN has existed since Oracle 9i Release 2. Earlier "
        "revisions claimed 12c here and 23ai in SKILL.md — two wrong answers that also "
        "contradicted each other.",
    ),
    (
        "SKILL.md",
        "**Oracle 9i Release 2**",
        ["not directly supported before 23ai", "not supported before 23ai"],
        "Same fact in the deployment-ordering checklist item.",
    ),
    (
        "references/oracle-version-licensing-matrix.md",
        "**9.2** | Metadata-only",
        [],
        "Same fact in the version matrix.",
    ),
    (
        "references/oracle-ddl-lock-matrix.md",
        "`DROP INDEX ... ONLINE` (12.1+)",
        ["`DROP INDEX ... ONLINE` (21c+)"],
        "DROP INDEX ... ONLINE arrived in 12.1 with the online index DDL enhancements, "
        "not 21c.",
    ),
    (
        "references/oracle-ddl-lock-matrix.md",
        "**ORA-01440**",
        [],
        "Decreasing NUMBER precision/scale raises ORA-01440 (column must be empty) — a "
        "rejection, not a slow rewrite.",
    ),
    (
        "references/oracle-ddl-lock-matrix.md",
        "**ORA-01439**",
        [],
        "Changing datatype class raises ORA-01439 — also a rejection.",
    ),
    (
        "references/oracle-ddl-lock-matrix.md",
        "Brief Exclusive | Brief | No | Metadata-only, but still an ALTER TABLE",
        [],
        "ADD CONSTRAINT ... DISABLE NOVALIDATE still takes the exclusive DDL lock; the "
        "matrix previously recorded its lock as None.",
    ),
    (
        "references/large-table-migration.md",
        "has no `DATA_OBJECT_ID` column",
        [],
        "DBA_EXTENTS exposes OWNER, SEGMENT_NAME, PARTITION_NAME, SEGMENT_TYPE, "
        "TABLESPACE_NAME, EXTENT_ID, FILE_ID, BLOCK_ID, BYTES, BLOCKS, RELATIVE_FNO. "
        "The old chunking example selected data_object_id and could not run.",
    ),
    (
        "references/large-table-migration.md",
        "The cutover is two statements, not an atomic swap",
        ["-- Step 5: Atomic swap"],
        "Two ALTER TABLE ... RENAME statements each auto-commit; there is no atomic swap.",
    ),
    (
        "references/large-table-migration.md",
        "RAISE_APPLICATION_ERROR(-20001,",
        [],
        "COPY_TABLE_DEPENDENTS num_errors must halt the workflow, not just be printed.",
    ),
    (
        "references/large-table-migration.md",
        "dml_lock_timeout => 30",
        [],
        "FINISH_REDEF_TABLE must pass dml_lock_timeout explicitly.",
    ),
    (
        "references/large-table-migration.md",
        "cannot be flashed back across a DDL that changed its structure",
        [],
        "FLASHBACK TABLE ... TO SCN/TIMESTAMP cannot cross structural DDL, so it is not "
        "a recovery path for a dropped or modified column.",
    ),
    (
        "SKILL.md",
        "cannot cross a structural DDL",
        [],
        "Same restriction stated in the checklist.",
    ),
    (
        "references/migration-anti-examples.md",
        "**`NOLOGGING` is not a hint.**",
        [],
        "NOLOGGING is a segment attribute; inside /*+ ... */ Oracle silently ignores it.",
    ),
    (
        "SKILL.md",
        "Assume **12.1** (most restrictive)",
        ["Assume 12c (most restrictive)"],
        "MOVE ONLINE is 12.2+, so '12c' is not a usable answer for Gate 1.",
    ),
    (
        "references/oracle-version-licensing-matrix.md",
        "Diagnostics Pack",
        [],
        "AWR/ASH/DBA_HIST_* require the Diagnostics Pack licence.",
    ),
    (
        "SKILL.md",
        "abort-before-cutover",
        [],
        "The rollback taxonomy replaced the checklist item that induced fake rollback SQL.",
    ),
    (
        "SKILL.md",
        "restore / PITR",
        [],
        "Structural DDL rolls back via restore/PITR, not compensating DDL.",
    ),
    (
        "references/oracle-version-licensing-matrix.md",
        "| `NULL` — **the default** |",
        ["| `0` (default) |"],
        "FINISH_REDEF_TABLE's dml_lock_timeout defaults to NULL (no cap — the swap waits), "
        "not 0/NOWAIT. An earlier revision took '0' from secondary blog posts. The two "
        "defaults fail in OPPOSITE directions, so the wrong one yields the wrong "
        "contingency: you plan for an abort and get a hang.",
    ),
    (
        "references/large-table-migration.md",
        "Its default is NULL",
        ["the swap does not wait for the lock at all and fails on any concurrent DML"],
        "Same fact in the worked DBMS_REDEFINITION example.",
    ),
    (
        "references/oracle-version-licensing-matrix.md",
        "| **Flashback Table** (`TO SCN/TIMESTAMP`) | ✅ | ❌ | ❌ |",
        ["Flashback Table / Flashback Query | ✅ | ✅ | ✅"],
        "Flashback Table TO SCN/TIMESTAMP is Enterprise Edition only; Flashback Query and "
        "Flashback Drop are not. Collapsing them into one 'all editions' row tells an SE2 "
        "site it has a recovery path it does not have.",
    ),
    (
        "SKILL.md",
        "Enterprise Edition only",
        [],
        "SKILL.md item 11 must carry the edition gate alongside the structural-DDL gate.",
    ),
    (
        "references/large-table-migration.md",
        "*a target, not a guarantee*",
        [],
        "A normal restore point is bounded by DB_FLASHBACK_RETENTION_TARGET, which Oracle "
        "documents as a target rather than a guarantee, and it ages out of the control "
        "file on its own. Only GUARANTEE FLASHBACK DATABASE enforces log retention, so "
        "only that form is a migration safety net.",
    ),
    (
        "references/large-table-migration.md",
        "GUARANTEE_FLASHBACK_DATABASE = YES",
        [],
        "The review must verify which kind of restore point actually exists, not trust "
        "the CREATE statement in the script.",
    ),
(
        "references/large-table-migration.md",
        "A copy is only a backup if it copies everything",
        ["provides no\nrecovery at all"],
        "A filtered, projected or WHERE 1=0 CTAS is not a recovery artefact. The last of "
        "those is the interim-table pattern — the opposite of a backup. Also: a normal "
        "restore point may still work while the logs survive, so the claim must be 'no "
        "guaranteed recovery', not 'no recovery at all'.",
    ),
    (
        "references/large-table-migration.md",
        "Flashback Database is Enterprise Edition only, so on SE2 or XE a guaranteed",
        [],
        "A guaranteed restore point is worthless without Flashback Database, which is EE "
        "only — the checker previously downgraded on SE2, contradicting this skill's own "
        "licensing matrix.",
    ),
]


class TestFactDrift:
    @pytest.mark.parametrize(
        "target,needle,banned,why",
        FACT_GUARDS,
        ids=[f"{g[0].split('/')[-1]}::{g[1][:34]}" for g in FACT_GUARDS],
    )
    def test_corrected_fact_present(self, target, needle, banned, why):
        content = _ref_or_skill(target)
        assert needle in content, f"{target} lost the corrected fact: {why}"
        for bad in banned:
            assert bad not in content, f"{target} reintroduced a known-wrong claim: {why}"

    # A line may legitimately contain a wrong claim *as the thing it is refuting*.
    # These markers identify a refuting context, so the guards do not fire on the very
    # sentences that state the correction.
    REFUTING = ("wrong", "not ", "never", "no longer", "fail", "must not", "do not",
                "incorrect", "myth", "supported since")

    @staticmethod
    def _assets():
        return [SKILL_DIR / "SKILL.md", *sorted(REFS_DIR.glob("*.md"))]

    @classmethod
    def _offending_lines(cls, text: str, needles: tuple) -> list:
        """Lines asserting a known-wrong claim, excluding lines that refute it.

        Markdown emphasis is stripped first: these documents write `**not** a rewrite`,
        and a raw substring scan for "not " misses it because the asterisks sit between
        the word and the space. The guard would then fire on the exact sentence carrying
        the correction.
        """
        out = []
        for line in text.splitlines():
            low = re.sub(r"[*_`]+", "", line.lower())
            if all(n in low for n in needles) and not any(r in low for r in cls.REFUTING):
                out.append(line.strip())
        return out

    def test_no_file_ties_rename_column_to_a_late_version(self):
        """Sweep every asset, not only the two that carried the original error."""
        for path in self._assets():
            bad = self._offending_lines(
                path.read_text(encoding="utf-8"), ("rename column", "23ai")
            )
            assert not bad, f"{path.name}: RENAME COLUMN tied to 23ai: {bad}"

    def test_widening_never_called_a_rewrite(self):
        """A widening MODIFY must not be described as a table rewrite anywhere."""
        for path in self._assets():
            bad = self._offending_lines(path.read_text(encoding="utf-8"), ("widen", "rewrite"))
            assert not bad, f"{path.name}: widening described as a rewrite: {bad}"

    def test_guards_still_catch_a_real_violation(self):
        """Guard the guards.

        The REFUTING allowlist is what lets a correcting sentence mention the wrong
        claim. Without this test, widening that list far enough to silence a false
        positive would silently disarm both sweeps above.
        """
        violation = "RENAME COLUMN requires 23ai or later."
        assert self._offending_lines(violation, ("rename column", "23ai"))

        violation2 = "Widening a column triggers a full table rewrite."
        assert self._offending_lines(violation2, ("widen", "rewrite"))

        # ...and refuting sentences must still be accepted, including the
        # markdown-emphasised form the reference files actually use.
        ok = "Widening is a dictionary update and must never be called a rewrite."
        assert not self._offending_lines(ok, ("widen", "rewrite"))
        ok_md = "| MODIFY column (widen) | ... | **not** a rewrite |"
        assert not self._offending_lines(ok_md, ("widen", "rewrite"))


class TestCheckerAssets:
    def test_linter_exists_and_is_executable_python(self):
        path = SKILL_DIR / "scripts" / "lint_migration.py"
        assert path.exists(), "scripts/lint_migration.py is missing"
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    def test_mutation_sweep_exists(self):
        path = SKILL_DIR / "scripts" / "mutation_sweep.py"
        assert path.exists(), "scripts/mutation_sweep.py is missing"
        compile(path.read_text(encoding="utf-8"), str(path), "exec")

    def test_skill_documents_the_checker(self):
        assert "lint_migration.py" in SKILL_MD, (
            "SKILL.md must tell the reviewer to run the deterministic pre-check"
        )

    def test_regression_runner_invokes_the_sweep(self):
        runner = (SKILL_DIR / "scripts" / "run_regression.sh").read_text(encoding="utf-8")
        assert "lint_migration.py" in runner
        assert "mutation_sweep.py" in runner
        assert "verify_against_server.sh" in runner
        assert "report_coverage.py" in runner

    def test_runner_discovers_tests_instead_of_naming_them(self):
        """A runner that enumerates test files silently skips the next one added.

        That already happened once: test_server_harness.py sat in the directory
        unexecuted by run_regression.sh because only two modules were named.
        """
        runner = (SKILL_DIR / "scripts" / "run_regression.sh").read_text(encoding="utf-8")
        # Executable lines only. The comment above the fix names the very module that
        # was missed, and a whole-file scan would flag the explanation as the offence.
        code = [ln for ln in runner.splitlines() if not ln.lstrip().startswith("#")]
        named = re.findall(r"test_\w+\.py", "\n".join(code))
        assert not named, (
            f"run_regression.sh names test modules explicitly ({sorted(set(named))}); "
            "point pytest at the directory so new modules are picked up automatically"
        )

    def test_the_discovery_guard_still_catches_an_enumerated_runner(self):
        """Guard the guard: stripping comments must not strip the detection too."""
        sample = "# runs test_foo.py explicitly\npytest tests/test_foo.py -q\n"
        code = [ln for ln in sample.splitlines() if not ln.lstrip().startswith("#")]
        assert re.findall(r"test_\w+\.py", "\n".join(code)) == ["test_foo.py"]

    def test_every_test_module_is_reached_by_the_runner(self):
        """Whatever the mechanism, every test_*.py must actually execute."""
        import subprocess
        import sys as _sys

        tests_dir = SKILL_DIR / "scripts" / "tests"
        modules = sorted(f.name for f in tests_dir.glob("test_*.py"))
        assert len(modules) >= 3, modules
        collected = subprocess.run(
            [_sys.executable, "-m", "pytest", str(tests_dir), "--collect-only", "-q",
             "--no-header", "-p", "no:cacheprovider"],
            capture_output=True, text=True,
        )
        for mod in modules:
            assert mod in collected.stdout, f"{mod} is not collected by the directory run"

    def test_server_harness_skips_without_a_dsn(self):
        """Absence of an instance is 'not requested', never a failure.

        A harness that errors when unconfigured gets disabled in CI, and then it is not
        a harness. It must also refuse to run DDL without an explicit acknowledgement.
        """
        import subprocess

        script = SKILL_DIR / "scripts" / "verify_against_server.sh"
        env = {k: v for k, v in os.environ.items() if not k.startswith("ORACLE_")}

        skipped = subprocess.run(
            ["bash", str(script)], capture_output=True, text=True, env=env
        )
        assert skipped.returncode == 0, skipped.stderr
        assert "SKIP" in skipped.stdout

        unacked = subprocess.run(
            ["bash", str(script)],
            capture_output=True,
            text=True,
            env={**env, "ORACLE_TEST_DSN": "u/p@//h:1521/s"},
        )
        assert unacked.returncode == 2, (
            "a DSN without ORACLE_ALLOW_DDL=1 must be a setup error (2), not a finding"
        )

    def test_server_harness_lists_its_probes(self):
        import subprocess

        script = SKILL_DIR / "scripts" / "verify_against_server.sh"
        out = subprocess.run(
            ["bash", str(script), "--list"], capture_output=True, text=True
        )
        assert out.returncode == 0
        # Each probe pins a claim this skill previously got wrong or now asserts.
        for probe in ("P01", "P04", "P05", "P07"):
            assert probe in out.stdout, f"{probe} missing from the probe list"

    def test_licensing_reference_is_wired_in(self):
        assert "oracle-version-licensing-matrix.md" in SKILL_MD


class TestCoverageDocAccuracy:
    """COVERAGE.md cites counts; those counts must be derived, not remembered."""

    def test_coverage_doc_matches_live_suite(self):
        import subprocess
        import sys as _sys

        script = SKILL_DIR / "scripts" / "tests" / "report_coverage.py"
        proc = subprocess.run(
            [_sys.executable, str(script), "--check"], capture_output=True, text=True
        )
        assert proc.returncode == 0, (
            "COVERAGE.md drifted from the live suite:\n" + proc.stdout + proc.stderr
        )

    def test_drift_checker_actually_detects_drift(self):
        """Guard the guard: a checker that always passes documents nothing."""
        import importlib.util
        import sys as _sys

        name = "oracle_report_coverage"
        path = SKILL_DIR / "scripts" / "tests" / "report_coverage.py"
        if name in _sys.modules:
            mod = _sys.modules[name]
        else:
            spec = importlib.util.spec_from_file_location(name, path)
            mod = importlib.util.module_from_spec(spec)
            _sys.modules[name] = mod
            spec.loader.exec_module(mod)

        stats = mod.collect()
        inflated = dict(stats, checks=stats["checks"] + 1)
        literals = dict(mod.expectations(stats))
        inflated_literals = dict(mod.expectations(inflated))
        assert literals["check count"] != inflated_literals["check count"], (
            "expectations() ignores the check count, so drift in it would go unnoticed"
        )


class TestAntiExampleNumbering:
    """AE ids must be sequential and the cross-reference must name the real range.

    A new AE appended in the wrong place reads as a duplicate id to anyone scanning
    the file, and a stale "AE-7 through AE-13" pointer hides the newest entry.
    """

    def test_inline_ae_ids_are_sequential_from_one(self):
        ids = [
            int(m.group(1))
            for m in re.finditer(r"^### AE-(\d+):", SKILL_MD, re.M)
        ]
        assert ids == list(range(1, len(ids) + 1)), f"SKILL.md AE ids: {ids}"

    def test_extended_ae_ids_are_sequential_and_contiguous_with_inline(self):
        inline = [int(m.group(1)) for m in re.finditer(r"^### AE-(\d+):", SKILL_MD, re.M)]
        ext_src = _ref("migration-anti-examples.md")
        ext = [int(m.group(1)) for m in re.finditer(r"^## AE-(\d+):", ext_src, re.M)]
        assert ext == sorted(ext), f"extended AE ids out of order: {ext}"
        assert ext == list(range(max(inline) + 1, max(inline) + 1 + len(ext))), (
            f"extended AE ids {ext} do not continue from inline {inline}"
        )

    def test_cross_reference_names_the_actual_range(self):
        ext_src = _ref("migration-anti-examples.md")
        ext = [int(m.group(1)) for m in re.finditer(r"^## AE-(\d+):", ext_src, re.M)]
        expected = f"AE-{min(ext)} through AE-{max(ext)}"
        assert expected in SKILL_MD, (
            f"SKILL.md must point at {expected!r}; the extended file now holds "
            f"AE-{min(ext)}..AE-{max(ext)}"
        )


class TestRunnerStageLabels:
    """`[n/N]` labels must stay consistent when a stage is added.

    Adding stage 6 while leaving four `[n/5]` labels behind is harmless to the run and
    corrosive to trust in the output — the same drift class this skill flags in docs.
    """

    def test_stage_labels_are_sequential_and_agree_on_the_total(self):
        runner = (SKILL_DIR / "scripts" / "run_regression.sh").read_text(encoding="utf-8")
        labels = re.findall(r'echo "\[(\d+)/(\d+)\]', runner)
        assert labels, "run_regression.sh has no [n/N] stage labels"
        totals = {t for _, t in labels}
        assert len(totals) == 1, f"stage labels disagree on the total: {sorted(totals)}"
        nums = [int(n) for n, _ in labels]
        assert nums == list(range(1, len(nums) + 1)), f"stage numbers not sequential: {nums}"
        assert nums[-1] == int(labels[0][1]), (
            f"last stage is {nums[-1]} but the labels claim {labels[0][1]} total"
        )


class TestMutationAnchors:
    """Every mutation's anchor text must still exist in its target.

    An anchor rots the moment the code it quotes is edited, and then that mutation
    silently stops testing anything. Twice in this skill's history a refactor left an
    anchor stale and it was only noticed after a multi-minute sweep. This runs in
    milliseconds and fails loudly instead.
    """

    @staticmethod
    def _sweep():
        import importlib.util
        import sys as _sys

        name = "oracle_mutation_sweep"
        if name in _sys.modules:
            return _sys.modules[name]
        path = SKILL_DIR / "scripts" / "mutation_sweep.py"
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        _sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod

    def test_every_anchor_is_present_in_its_target(self):
        stale = []
        for m in self._sweep().M:
            text = (SKILL_DIR / m.target).read_text(encoding="utf-8")
            if m.old not in text:
                stale.append(f"{m.mid} -> {m.target}")
        assert not stale, "mutation anchors no longer present: " + ", ".join(stale)

    def test_every_anchor_actually_changes_the_target(self):
        """A mutation whose replacement equals its anchor is a no-op."""
        noop = [m.mid for m in self._sweep().M if m.old == m.new]
        assert not noop, f"mutations that change nothing: {noop}"

    def test_no_mutation_is_semantically_inert(self):
        """Catch replacements that differ textually but cannot change behaviour.

        L78 originally appended a bare `pass` to its anchor. That is not equal to the
        anchor, so the equality check above passed it, but it could never alter the
        result — so it SURVIVED every run and read as a missing assertion. A surviving
        no-op is worse than no mutation at all: it sends you hunting for a test that was
        never needed.
        """
        inert = []
        for m in self._sweep().M:
            if not m.new.startswith(m.old):
                continue
            added = m.new[len(m.old):]
            if not added.strip() or set(added.split()) <= {"pass", "continue"}:
                inert.append(m.mid)
        assert not inert, (
            f"mutations that add only a no-op and can never fail: {inert}"
        )

    def test_mutation_ids_are_unique(self):
        ids = [m.mid for m in self._sweep().M]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        assert not dupes, f"duplicate mutation ids: {dupes}"

    def test_shipped_scripts_emit_no_warnings(self):
        """A SyntaxWarning in a shipped script is noise that trains people to ignore output.

        Caught one here: a mutation anchor written as a non-raw string containing `\\s`.
        """
        import subprocess
        import sys as _sys

        for name in ("lint_migration.py", "mutation_sweep.py"):
            path = SKILL_DIR / "scripts" / name
            r = subprocess.run(
                [_sys.executable, "-W", "error::SyntaxWarning", "-m", "py_compile", str(path)],
                capture_output=True, text=True,
            )
            assert r.returncode == 0, f"{name} emits a SyntaxWarning:\n{r.stderr}"

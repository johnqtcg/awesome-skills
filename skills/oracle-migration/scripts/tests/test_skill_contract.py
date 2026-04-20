"""Contract tests for oracle-migration skill."""

import pathlib
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
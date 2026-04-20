"""Contract tests for pg-migration skill.

Validates structural integrity of SKILL.md and reference files without
requiring an LLM.
"""

import pathlib
import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
REFS_DIR = SKILL_DIR / "references"


def _ref(name: str) -> str:
    return (REFS_DIR / name).read_text(encoding="utf-8")


def _all_docs() -> str:
    parts = [SKILL_MD]
    for f in sorted(REFS_DIR.glob("*.md")):
        parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts)


# ===========================================================================
# 1. Frontmatter
# ===========================================================================

class TestFrontmatter:
    def test_name(self):
        assert "name: pg-migration" in SKILL_MD

    def test_description_keywords(self):
        desc_area = SKILL_MD[:800].lower()
        for kw in ["alter table", "ddl", "concurrently", "not valid", "pg_repack",
                    "accessexclusivelock"]:
            assert kw in desc_area, f"description missing trigger keyword: {kw}"


# ===========================================================================
# 2. Mandatory Gates
# ===========================================================================

class TestMandatoryGates:
    def test_gate_1_context(self):
        assert "Gate 1" in SKILL_MD
        lower = SKILL_MD.lower()
        assert "pg version" in lower or "postgresql" in lower
        assert "table row" in lower
        assert "replication" in lower

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
        assert stop_count >= 3, f"Expected ≥3 STOP conditions, found {stop_count}"


# ===========================================================================
# 3. Depth Selection
# ===========================================================================

class TestDepthSelection:
    def test_three_depths(self):
        for depth in ["Lite", "Standard", "Deep"]:
            assert depth in SKILL_MD

    def test_force_standard_signals(self):
        lower = SKILL_MD.lower()
        for signal in ["column type change", "not null", "foreign key", "rls"]:
            assert signal in lower, f"missing force-Standard signal: {signal}"

    def test_reference_loading_by_depth(self):
        assert "pg-ddl-lock-matrix.md" in SKILL_MD
        assert "large-table-migration.md" in SKILL_MD


# ===========================================================================
# 4. Degradation Modes
# ===========================================================================

class TestDegradationModes:
    def test_four_modes_defined(self):
        for mode in ["Full", "Degraded", "Minimal", "Planning"]:
            assert mode in SKILL_MD

    def test_never_fabricate(self):
        lower = SKILL_MD.lower()
        assert "never" in lower and ("fabricate" in lower or "claim" in lower)

    def test_assumptions_documented(self):
        lower = SKILL_MD.lower()
        assert "uncovered risk" in lower


# ===========================================================================
# 5. DDL Safety Checklist
# ===========================================================================

class TestDDLSafetyChecklist:
    def test_subsection_count(self):
        for sub in ["5.1", "5.2", "5.3", "5.4"]:
            assert sub in SKILL_MD

    def test_lock_level_keywords(self):
        assert "AccessExclusiveLock" in SKILL_MD
        assert "ShareLock" in SKILL_MD
        assert "ShareUpdateExclusiveLock" in SKILL_MD

    def test_concurrently_keyword(self):
        assert "CONCURRENTLY" in SKILL_MD

    def test_not_valid_keyword(self):
        assert "NOT VALID" in SKILL_MD
        assert "VALIDATE CONSTRAINT" in SKILL_MD

    def test_lock_timeout(self):
        assert "lock_timeout" in SKILL_MD
        assert "statement_timeout" in SKILL_MD

    def test_backward_compatibility(self):
        lower = SKILL_MD.lower()
        assert "deployment order" in lower or "backward compat" in lower

    def test_rollback_feasibility(self):
        lower = SKILL_MD.lower()
        assert "transactional" in lower and "rollback" in lower
        assert "irreversible" in lower


# ===========================================================================
# 6. Execution Plan
# ===========================================================================

class TestExecutionPlan:
    def test_five_phases(self):
        lower = SKILL_MD.lower()
        for kw in ["additive", "backfill", "app deploy", "validation", "cleanup"]:
            assert kw in lower, f"missing phase keyword: {kw}"

    def test_references_large_table(self):
        assert "large-table-migration.md" in SKILL_MD


# ===========================================================================
# 7. Anti-Examples
# ===========================================================================

class TestAntiExamples:
    def test_min_count(self):
        ae_count = sum(1 for line in SKILL_MD.split("\n") if line.strip().startswith("### AE-"))
        assert ae_count >= 6, f"Expected ≥6 anti-examples, found {ae_count}"

    def test_wrong_right_pairs(self):
        assert SKILL_MD.count("-- WRONG") >= 5
        assert SKILL_MD.count("-- RIGHT") >= 5

    def test_concurrently_anti_example(self):
        lower = SKILL_MD.lower()
        assert "without concurrently" in lower or "without `concurrently`" in lower

    def test_extended_ref(self):
        assert "migration-anti-examples.md" in SKILL_MD


# ===========================================================================
# 8. Scorecard
# ===========================================================================

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
        assert "lock_timeout" in lower
        assert "concurrently" in lower
        assert "rollback" in lower

    def test_verdict_format(self):
        assert "X/12" in SKILL_MD or "PASS/FAIL" in SKILL_MD


# ===========================================================================
# 9. Output Contract
# ===========================================================================

class TestOutputContract:
    def test_nine_sections(self):
        for section in ["9.1", "9.2", "9.3", "9.4", "9.5", "9.6", "9.7", "9.8", "9.9"]:
            assert section in SKILL_MD, f"missing output section {section}"

    def test_uncovered_risks_mandatory(self):
        lower = SKILL_MD.lower()
        assert "never empty" in lower or "mandatory" in lower

    def test_volume_rules(self):
        lower = SKILL_MD.lower()
        assert "volume" in lower

    def test_scorecard_in_output(self):
        lower = SKILL_MD.lower()
        assert "scorecard" in lower and "data basis" in lower


# ===========================================================================
# 10. Reference Files
# ===========================================================================

class TestReferenceFiles:
    def test_ddl_matrix_exists(self):
        content = _ref("pg-ddl-lock-matrix.md")
        assert len(content.splitlines()) >= 80

    def test_ddl_matrix_keywords(self):
        content = _ref("pg-ddl-lock-matrix.md")
        for kw in ["AccessExclusiveLock", "ShareLock", "CONCURRENTLY", "NOT VALID"]:
            assert kw in content

    def test_ddl_matrix_operations(self):
        content = _ref("pg-ddl-lock-matrix.md").lower()
        for op in ["add column", "drop column", "create index", "alter column type"]:
            assert op in content, f"DDL matrix missing operation: {op}"

    def test_large_table_exists(self):
        content = _ref("large-table-migration.md")
        assert len(content.splitlines()) >= 100

    def test_large_table_keywords(self):
        content = _ref("large-table-migration.md")
        for kw in ["pg_repack", "cursor", "batch", "swap"]:
            assert kw in content

    def test_anti_examples_exists(self):
        content = _ref("migration-anti-examples.md")
        assert len(content.splitlines()) >= 80

    def test_anti_examples_numbering(self):
        content = _ref("migration-anti-examples.md")
        assert "AE-7" in content
        ae_count = sum(1 for line in content.split("\n") if "## AE-" in line)
        assert ae_count >= 5, f"Expected ≥5 extended anti-examples, found {ae_count}"

    def test_all_refs_mentioned_in_skill(self):
        for f in REFS_DIR.glob("*.md"):
            assert f.name in SKILL_MD, f"reference {f.name} not mentioned in SKILL.md"


# ===========================================================================
# 11. Line Count Budget
# ===========================================================================

class TestLineCount:
    def test_max_lines(self):
        lines = len(SKILL_MD.splitlines())
        assert lines <= 420, f"SKILL.md is {lines} lines (budget: 420)"


# ===========================================================================
# 12. Cross-File Consistency
# ===========================================================================

class TestCrossFileConsistency:
    def test_access_exclusive_in_matrix(self):
        content = _ref("pg-ddl-lock-matrix.md")
        assert "AccessExclusiveLock" in content

    def test_concurrently_in_matrix(self):
        content = _ref("pg-ddl-lock-matrix.md")
        assert "CONCURRENTLY" in content

    def test_pg_repack_in_large_table(self):
        content = _ref("large-table-migration.md")
        assert "pg_repack" in content

    def test_lock_timeout_in_skill(self):
        assert "lock_timeout" in SKILL_MD

    def test_not_valid_in_matrix(self):
        content = _ref("pg-ddl-lock-matrix.md")
        assert "NOT VALID" in content

    def test_do_block_in_anti_examples(self):
        content = _ref("migration-anti-examples.md")
        assert "DO" in content and "pg_constraint" in content
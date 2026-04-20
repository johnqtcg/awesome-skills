"""Contract tests for mongo-migration skill.

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


# ===========================================================================
# 1. Frontmatter
# ===========================================================================

class TestFrontmatter:
    def test_name(self):
        assert "name: mongo-migration" in SKILL_MD

    def test_description_keywords(self):
        desc = SKILL_MD[:800].lower()
        for kw in ["index", "schema", "bulk", "shard key", "collmod",
                    "write concern", "_id-range"]:
            assert kw in desc, f"description missing keyword: {kw}"


# ===========================================================================
# 2. Mandatory Gates
# ===========================================================================

class TestMandatoryGates:
    def test_gate_1_context(self):
        assert "Gate 1" in SKILL_MD
        lower = SKILL_MD.lower()
        assert "mongodb version" in lower
        assert "replica" in lower or "deployment" in lower

    def test_gate_1_stop_proceed(self):
        assert "**STOP**" in SKILL_MD
        assert "**PROCEED**" in SKILL_MD

    def test_gate_2_scope(self):
        assert "Gate 2" in SKILL_MD

    def test_gate_3_risk(self):
        assert "Gate 3" in SKILL_MD
        for risk in ["SAFE", "WARN", "UNSAFE"]:
            assert risk in SKILL_MD

    def test_gate_4_completeness(self):
        assert "Gate 4" in SKILL_MD

    def test_all_gates_have_stop(self):
        assert SKILL_MD.count("**STOP**") >= 3


# ===========================================================================
# 3. Depth Selection
# ===========================================================================

class TestDepthSelection:
    def test_three_depths(self):
        for depth in ["Lite", "Standard", "Deep"]:
            assert depth in SKILL_MD

    def test_force_standard_signals(self):
        lower = SKILL_MD.lower()
        for signal in ["field type change", "shard key", "validator"]:
            assert signal in lower, f"missing signal: {signal}"

    def test_reference_loading_by_depth(self):
        assert "mongo-ddl-lock-matrix.md" in SKILL_MD
        assert "large-collection-migration.md" in SKILL_MD


# ===========================================================================
# 4. Degradation Modes
# ===========================================================================

class TestDegradationModes:
    def test_four_modes_defined(self):
        for mode in ["Full", "Degraded", "Minimal", "Planning"]:
            assert mode in SKILL_MD

    def test_never_fabricate(self):
        lower = SKILL_MD.lower()
        assert "never" in lower and ("fabricate" in lower or "claim" in lower or "safe" in lower and "without" in lower)

    def test_assumptions_documented(self):
        assert "9.9" in SKILL_MD


# ===========================================================================
# 5. Migration Safety Checklist
# ===========================================================================

class TestChecklist:
    def test_subsection_count(self):
        for sub in ["5.1", "5.2", "5.3", "5.4"]:
            assert sub in SKILL_MD

    def test_index_build(self):
        lower = SKILL_MD.lower()
        assert "rolling" in lower or "background" in lower

    def test_write_concern(self):
        lower = SKILL_MD.lower()
        assert "write concern" in lower or "writeconcern" in lower

    def test_validator_progression(self):
        lower = SKILL_MD.lower()
        assert "moderate" in lower
        assert "strict" in lower

    def test_id_range_batching(self):
        assert "_id" in SKILL_MD
        assert "range" in SKILL_MD.lower()

    def test_backward_compatibility(self):
        lower = SKILL_MD.lower()
        assert "deployment order" in lower or "backward" in lower

    def test_rollback_feasibility(self):
        assert "irreversible" in SKILL_MD.lower()


# ===========================================================================
# 6. Execution Plan
# ===========================================================================

class TestExecutionPlan:
    def test_five_phases(self):
        lower = SKILL_MD.lower()
        for kw in ["additive", "backfill", "app deploy", "validator", "cleanup"]:
            assert kw in lower, f"missing phase: {kw}"

    def test_references_large_collection(self):
        assert "large-collection-migration.md" in SKILL_MD


# ===========================================================================
# 7. Anti-Examples
# ===========================================================================

class TestAntiExamples:
    def test_min_count(self):
        ae_count = sum(1 for l in SKILL_MD.split("\n") if l.strip().startswith("### AE-"))
        assert ae_count >= 6

    def test_wrong_right_pairs(self):
        assert SKILL_MD.count("// WRONG") >= 5
        assert SKILL_MD.count("// RIGHT") >= 5

    def test_unbounded_update_anti_example(self):
        assert "updateMany" in SKILL_MD or "unbounded" in SKILL_MD.lower()

    def test_extended_ref(self):
        assert "migration-anti-examples.md" in SKILL_MD


# ===========================================================================
# 8. Scorecard
# ===========================================================================

class TestScorecard:
    def test_critical_tier(self):
        lower = SKILL_MD.lower()
        assert "critical" in lower
        assert "any fail" in lower

    def test_standard_tier(self):
        assert "4 of 5" in SKILL_MD or "4/5" in SKILL_MD

    def test_hygiene_tier(self):
        assert "3 of 4" in SKILL_MD or "3/4" in SKILL_MD

    def test_critical_items(self):
        lower = SKILL_MD.lower()
        assert "_id" in lower
        assert "write concern" in lower or "writeconcern" in lower

    def test_verdict_format(self):
        assert "X/12" in SKILL_MD or "PASS/FAIL" in SKILL_MD


# ===========================================================================
# 9. Output Contract
# ===========================================================================

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


# ===========================================================================
# 10. Reference Files
# ===========================================================================

class TestReferenceFiles:
    def test_ddl_matrix_exists(self):
        content = _ref("mongo-ddl-lock-matrix.md")
        assert len(content.splitlines()) >= 80

    def test_ddl_matrix_keywords(self):
        content = _ref("mongo-ddl-lock-matrix.md")
        for kw in ["Exclusive", "createIndex", "WiredTiger"]:
            assert kw in content

    def test_large_collection_exists(self):
        content = _ref("large-collection-migration.md")
        assert len(content.splitlines()) >= 100

    def test_large_collection_keywords(self):
        content = _ref("large-collection-migration.md")
        for kw in ["_id", "batch", "BulkWrite", "reshardCollection"]:
            assert kw in content

    def test_anti_examples_exists(self):
        content = _ref("migration-anti-examples.md")
        assert len(content.splitlines()) >= 80

    def test_anti_examples_numbering(self):
        content = _ref("migration-anti-examples.md")
        assert "AE-7" in content
        ae_count = sum(1 for l in content.split("\n") if "## AE-" in l)
        assert ae_count >= 5

    def test_all_refs_mentioned_in_skill(self):
        for f in REFS_DIR.glob("*.md"):
            assert f.name in SKILL_MD, f"{f.name} not in SKILL.md"


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
    def test_wiredtiger_in_matrix(self):
        assert "WiredTiger" in _ref("mongo-ddl-lock-matrix.md")

    def test_reshard_in_large_collection(self):
        assert "reshardCollection" in _ref("large-collection-migration.md")

    def test_id_range_in_large_collection(self):
        assert "_id" in _ref("large-collection-migration.md")

    def test_write_concern_in_skill(self):
        assert "write concern" in SKILL_MD.lower() or "writeConcern" in SKILL_MD

    def test_validator_in_anti_examples(self):
        content = _ref("migration-anti-examples.md")
        assert "validationLevel" in content or "validator" in content.lower()

    def test_replication_lag_in_matrix(self):
        assert "replication" in _ref("mongo-ddl-lock-matrix.md").lower()
"""Contract tests for mysql-migration skill.

Validates structural integrity of SKILL.md and reference files without
requiring an LLM. Every test checks a property that MUST hold for the
skill to function correctly.
"""

import pathlib
import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
REFS_DIR = SKILL_DIR / "references"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ref(name: str) -> str:
    """Read a reference file and return its content."""
    return (REFS_DIR / name).read_text(encoding="utf-8")


def _all_docs() -> str:
    """Concatenate SKILL.md + all reference files (case-preserved)."""
    parts = [SKILL_MD]
    for f in sorted(REFS_DIR.glob("*.md")):
        parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts)


# ===========================================================================
# 1. Frontmatter
# ===========================================================================

class TestFrontmatter:
    """SKILL.md must have correct name and trigger-relevant description."""

    def test_name(self):
        assert "name: mysql-migration" in SKILL_MD

    def test_description_keywords(self):
        desc_area = SKILL_MD[:600].lower()
        for kw in ["alter table", "ddl", "instant", "inplace", "gh-ost", "pt-osc"]:
            assert kw in desc_area, f"description missing trigger keyword: {kw}"


# ===========================================================================
# 2. Mandatory Gates
# ===========================================================================

class TestMandatoryGates:
    """Four gates must exist with STOP/PROCEED structure."""

    def test_gate_1_context(self):
        assert "Gate 1" in SKILL_MD or "Gate 1:" in SKILL_MD
        assert "mysql version" in SKILL_MD.lower()
        assert "table row count" in SKILL_MD.lower() or "table row" in SKILL_MD.lower()
        assert "replication" in SKILL_MD.lower()

    def test_gate_1_stop_proceed(self):
        assert "**STOP**" in SKILL_MD or "STOP:" in SKILL_MD
        assert "**PROCEED**" in SKILL_MD or "PROCEED:" in SKILL_MD

    def test_gate_2_scope(self):
        assert "Gate 2" in SKILL_MD or "Gate 2:" in SKILL_MD
        for mode in ["review", "generate", "plan"]:
            assert mode in SKILL_MD.lower()

    def test_gate_3_risk(self):
        assert "Gate 3" in SKILL_MD or "Gate 3:" in SKILL_MD
        for risk in ["SAFE", "WARN", "UNSAFE"]:
            assert risk in SKILL_MD

    def test_gate_4_completeness(self):
        assert "Gate 4" in SKILL_MD or "Gate 4:" in SKILL_MD
        assert "output" in SKILL_MD.lower() and "completeness" in SKILL_MD.lower() or "complete" in SKILL_MD.lower()

    def test_all_gates_have_stop(self):
        """Each gate must define when to STOP."""
        # Count STOP occurrences — at least 3 gates have explicit STOP
        stop_count = SKILL_MD.count("**STOP**") + SKILL_MD.count("STOP:")
        assert stop_count >= 3, f"Expected ≥3 STOP conditions, found {stop_count}"


# ===========================================================================
# 3. Depth Selection
# ===========================================================================

class TestDepthSelection:
    """Three depth levels with clear triggers."""

    def test_three_depths(self):
        for depth in ["Lite", "Standard", "Deep"]:
            assert depth in SKILL_MD

    def test_force_standard_signals(self):
        lower = SKILL_MD.lower()
        for signal in ["column type change", "not null", "foreign key", "charset"]:
            assert signal in lower, f"missing force-Standard signal: {signal}"

    def test_reference_loading_by_depth(self):
        assert "ddl-algorithm-matrix.md" in SKILL_MD
        assert "large-table-migration.md" in SKILL_MD


# ===========================================================================
# 4. Degradation Modes
# ===========================================================================

class TestDegradationModes:
    """Skill must handle incomplete context gracefully."""

    def test_four_modes_defined(self):
        for mode in ["Full", "Degraded", "Minimal", "Planning"]:
            assert mode in SKILL_MD, f"missing degradation mode: {mode}"

    def test_never_fabricate(self):
        lower = SKILL_MD.lower()
        assert "never" in lower and "fabricate" in lower or "never claim" in lower

    def test_assumptions_documented(self):
        lower = SKILL_MD.lower()
        assert "uncovered risk" in lower or "assumptions" in lower


# ===========================================================================
# 5. DDL Safety Checklist
# ===========================================================================

class TestDDLSafetyChecklist:
    """14-item checklist across 4 subsections."""

    def test_subsection_count(self):
        for sub in ["5.1", "5.2", "5.3", "5.4"]:
            assert sub in SKILL_MD, f"missing checklist subsection {sub}"

    def test_algorithm_keywords(self):
        for kw in ["ALGORITHM=INSTANT", "ALGORITHM=INPLACE", "ALGORITHM=COPY"]:
            assert kw in SKILL_MD

    def test_lock_keywords(self):
        assert "LOCK=NONE" in SKILL_MD

    def test_mdl_contention(self):
        assert "MDL" in SKILL_MD or "metadata lock" in SKILL_MD.lower()
        assert "lock_wait_timeout" in SKILL_MD

    def test_session_guards(self):
        assert "lock_wait_timeout" in SKILL_MD
        assert "innodb_lock_wait_timeout" in SKILL_MD

    def test_backward_compatibility(self):
        lower = SKILL_MD.lower()
        assert "deployment order" in lower or "backward compat" in lower

    def test_rollback_feasibility(self):
        lower = SKILL_MD.lower()
        assert "reversible" in lower
        assert "irreversible" in lower


# ===========================================================================
# 6. Execution Plan
# ===========================================================================

class TestExecutionPlan:
    """Phased rollout pattern must be documented."""

    def test_five_phases(self):
        for phase_kw in ["Additive", "Backfill", "App deploy", "Constraint", "Cleanup"]:
            assert phase_kw.lower() in SKILL_MD.lower(), f"missing phase keyword: {phase_kw}"

    def test_references_large_table(self):
        assert "large-table-migration.md" in SKILL_MD


# ===========================================================================
# 7. Anti-Examples
# ===========================================================================

class TestAntiExamples:
    """At least 6 inline anti-examples with WRONG/RIGHT pairs."""

    def test_min_count(self):
        ae_count = sum(1 for line in SKILL_MD.split("\n") if line.strip().startswith("### AE-"))
        assert ae_count >= 6, f"Expected ≥6 anti-examples, found {ae_count}"

    def test_wrong_right_pairs(self):
        assert SKILL_MD.count("-- WRONG") >= 5
        assert SKILL_MD.count("-- RIGHT") >= 5

    def test_session_guard_anti_example(self):
        # AE-3 must demonstrate missing session guards
        assert "without session guards" in SKILL_MD.lower() or "ddl without session" in SKILL_MD.lower()

    def test_extended_ref(self):
        assert "migration-anti-examples.md" in SKILL_MD


# ===========================================================================
# 8. Scorecard
# ===========================================================================

class TestScorecard:
    """Three-tier scorecard with quantified pass rules."""

    def test_critical_tier(self):
        lower = SKILL_MD.lower()
        assert "critical" in lower
        assert "any fail" in lower or "any failure" in lower

    def test_standard_tier(self):
        assert "4 of 5" in SKILL_MD or "4/5" in SKILL_MD

    def test_hygiene_tier(self):
        assert "3 of 4" in SKILL_MD or "3/4" in SKILL_MD

    def test_critical_items(self):
        """Critical tier must check: algorithm specified, session guards, rollback SQL."""
        lower = SKILL_MD.lower()
        assert "algorithm" in lower and "explicit" in lower
        assert "session guard" in lower or "lock_wait_timeout" in lower
        assert "rollback" in lower

    def test_verdict_format(self):
        assert "X/12" in SKILL_MD or "PASS/FAIL" in SKILL_MD


# ===========================================================================
# 9. Output Contract
# ===========================================================================

class TestOutputContract:
    """9-section output contract with mandatory uncovered risks."""

    def test_nine_sections(self):
        for section in ["9.1", "9.2", "9.3", "9.4", "9.5", "9.6", "9.7", "9.8", "9.9"]:
            assert section in SKILL_MD, f"missing output section {section}"

    def test_uncovered_risks_mandatory(self):
        lower = SKILL_MD.lower()
        assert "never empty" in lower or "mandatory" in lower

    def test_volume_rules(self):
        lower = SKILL_MD.lower()
        assert "volume rule" in lower or "volume" in lower

    def test_scorecard_in_output(self):
        lower = SKILL_MD.lower()
        assert "scorecard" in lower and "data basis" in lower


# ===========================================================================
# 10. Reference Files
# ===========================================================================

class TestReferenceFiles:
    """All reference files exist with required content."""

    def test_ddl_matrix_exists(self):
        content = _ref("ddl-algorithm-matrix.md")
        assert len(content.splitlines()) >= 80

    def test_ddl_matrix_keywords(self):
        content = _ref("ddl-algorithm-matrix.md")
        for kw in ["INSTANT", "INPLACE", "COPY", "5.7", "8.0"]:
            assert kw in content

    def test_ddl_matrix_operations(self):
        content = _ref("ddl-algorithm-matrix.md").lower()
        for op in ["add column", "drop column", "add index", "varchar"]:
            assert op in content, f"DDL matrix missing operation: {op}"

    def test_large_table_exists(self):
        content = _ref("large-table-migration.md")
        assert len(content.splitlines()) >= 100

    def test_large_table_keywords(self):
        content = _ref("large-table-migration.md")
        for kw in ["gh-ost", "pt-online-schema-change", "chunk", "replica"]:
            assert kw in content

    def test_anti_examples_exists(self):
        content = _ref("migration-anti-examples.md")
        assert len(content.splitlines()) >= 80

    def test_anti_examples_numbering(self):
        """Extended anti-examples start at AE-7 (AE-1 through AE-6 are inline in SKILL.md)."""
        content = _ref("migration-anti-examples.md")
        assert "AE-7" in content
        ae_count = sum(1 for line in content.split("\n") if "## AE-" in line)
        assert ae_count >= 5, f"Expected ≥5 extended anti-examples, found {ae_count}"

    def test_all_refs_mentioned_in_skill(self):
        """Every reference file must be mentioned in SKILL.md."""
        for f in REFS_DIR.glob("*.md"):
            assert f.name in SKILL_MD, f"reference {f.name} not mentioned in SKILL.md"


# ===========================================================================
# 11. Line Count Budget
# ===========================================================================

class TestLineCount:
    """SKILL.md must stay within line budget."""

    def test_max_lines(self):
        lines = len(SKILL_MD.splitlines())
        assert lines <= 420, f"SKILL.md is {lines} lines (budget: 420)"


# ===========================================================================
# 12. Cross-File Consistency
# ===========================================================================

class TestCrossFileConsistency:
    """Key terms must appear consistently across SKILL.md and references."""

    @pytest.fixture(scope="class")
    def all_docs(self):
        return _all_docs().lower()

    def test_instant_in_matrix(self):
        content = _ref("ddl-algorithm-matrix.md")
        assert "ALGORITHM=INSTANT" in content or "INSTANT" in content

    def test_gh_ost_in_large_table(self):
        content = _ref("large-table-migration.md")
        assert "gh-ost" in content

    def test_pt_osc_in_large_table(self):
        content = _ref("large-table-migration.md")
        assert "pt-online-schema-change" in content

    def test_lock_wait_timeout_in_skill(self):
        assert "lock_wait_timeout" in SKILL_MD

    def test_session_guards_in_anti_examples(self):
        content = _ref("migration-anti-examples.md").lower()
        assert "lock_wait_timeout" in content or "session" in content

    def test_varchar_boundary_in_matrix(self):
        content = _ref("ddl-algorithm-matrix.md").lower()
        assert "255" in content and ("256" in content or "boundary" in content)
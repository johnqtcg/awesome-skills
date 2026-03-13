import re
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
CONFIG_EXAMPLE = SKILL_DIR / "references" / "unit-test-config.example.yaml"
REFERENCE_DIR = SKILL_DIR / "references"


class UnitTestSkillContractTests(unittest.TestCase):
    # --- Original 5 tests (preserved) ---

    def test_coverage_threshold_consistent_at_80(self) -> None:
        skill = SKILL_MD.read_text()

        self.assertIn("default 80% for logic packages", skill)
        self.assertIn(">= 80%", skill)
        self.assertIn("logic >= 80%", skill)

        self.assertNotIn("default 90%", skill)
        self.assertNotIn("logic >= 90%", skill)

    def test_scorecard_boundary_for_incremental_mode(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn(
            "Full scorecard is mandatory for full test generation workflows.", skill
        )
        self.assertIn("For incremental mode, use simplified scorecard only", skill)
        self.assertIn("Incremental mode: full scorecard skipped", skill)

    def test_repo_config_section_and_example_exist(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Repository Config (Optional)", skill)
        self.assertIn(".unit-test.yaml", skill)
        self.assertTrue(CONFIG_EXAMPLE.exists(), "config example file must exist")

        cfg = CONFIG_EXAMPLE.read_text()
        self.assertIn("logic_min: 80", cfg)
        self.assertIn("assertion_style: auto", cfg)

    def test_skill_name_is_valid(self) -> None:
        content = SKILL_MD.read_text()
        match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
        self.assertIsNotNone(match)
        fm = match.group(1)
        self.assertIn("name: unit-test", fm)

    # --- New: Killer Case Definition ---

    def test_killer_case_definition_section_exists(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Killer Case — Definition", skill)
        self.assertIn("four mandatory components", skill)

    def test_killer_case_four_components(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Defect hypothesis", skill)
        self.assertIn("Fault injection or boundary setup", skill)
        self.assertIn("Critical assertion", skill)
        self.assertIn("Removal risk statement", skill)

    # --- New: Defect-First Workflow ---

    def test_defect_first_workflow_five_risk_categories(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Defect-First Workflow (Mandatory)", skill)
        self.assertIn("Loop/index risks", skill)
        self.assertIn("Collection transform risks", skill)
        self.assertIn("Branching risks", skill)
        self.assertIn("Concurrency risks", skill)
        self.assertIn("Context/time risks", skill)

    # --- New: Boundary Checklist ---

    def test_boundary_checklist_has_twelve_items(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Fixed Boundary Checklist", skill)
        checklist_start = skill.index("Fixed Boundary Checklist")
        checklist_section = skill[checklist_start : checklist_start + 1500]
        for i in range(1, 13):
            self.assertRegex(
                checklist_section,
                rf"\b{i}\.\s+",
                f"Boundary checklist item {i} not found",
            )

    # --- New: Anti-examples ---

    def test_anti_examples_minimum_count(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Anti-examples (DO NOT write these tests)", skill)
        anti_start = skill.index("Anti-examples (DO NOT write these tests)")
        anti_section = skill[anti_start : anti_start + 1500]
        bullet_count = anti_section.count("\n- ")
        self.assertGreaterEqual(
            bullet_count, 8, f"Expected >= 8 anti-examples, found {bullet_count}"
        )

    # --- New: Bug-Finding Techniques ---

    def test_bug_finding_techniques_seven_entries(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Bug-Finding Techniques", skill)
        self.assertIn("Mutation-Resistant Assertions", skill)
        self.assertIn("Collection Mapping Completeness", skill)
        self.assertIn("Off-by-One Precision", skill)
        self.assertIn("Dependency Error Propagation", skill)
        self.assertIn("Concurrency & Panic Recovery", skill)
        self.assertIn("Branch Completeness", skill)
        self.assertIn("Killer Case Design", skill)

    # --- New: Target Type Adaptation ---

    def test_target_type_adaptation_five_types(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Target Type Adaptation", skill)
        self.assertIn("Service interface", skill)
        self.assertIn("Package-level functions", skill)
        self.assertIn("HTTP handler", skill)
        self.assertIn("CLI command/runner", skill)
        self.assertIn("Middleware", skill)

    # --- New: Reporting Integrity ---

    def test_reporting_integrity_section_exists(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Reporting Integrity (Mandatory)", skill)
        self.assertIn(
            "Do NOT claim `-race` or coverage results unless you actually ran", skill
        )

    # --- New: Output Expectations ---

    def test_output_expectations_include_killer_case_report(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Output Expectations", skill)
        self.assertIn("Killer case list per target", skill)
        self.assertIn("linked defect hypothesis", skill)
        self.assertIn(
            "if this assertion is removed, the known bug can escape detection", skill
        )

    # --- New: Go Version Gate ---

    def test_go_version_gate_exists(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Go Version Gate", skill)
        self.assertIn("go.mod", skill)

    def test_go_version_gate_covers_key_features(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("t.Setenv", skill)
        self.assertIn("1.17", skill)
        self.assertIn("Range var capture fix", skill)
        self.assertIn("1.22", skill)
        self.assertIn("t.Parallel()", skill)
        self.assertIn("1.24", skill)

    # --- New: Generated Code Exclusion ---

    def test_generated_code_exclusion_patterns(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Generated Code Exclusion", skill)
        self.assertIn("*.pb.go", skill)
        self.assertIn("wire_gen.go", skill)
        self.assertIn("mock_*.go", skill)
        self.assertIn("Code generated", skill)

    # --- New: Multi-Package Coverage ---

    def test_multi_package_coverage_guidance(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Multi-Package Coverage", skill)
        self.assertIn("-coverpkg=./...", skill)

    # --- New: High-Signal Budget ---

    def test_high_signal_test_budget_range(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("High-Signal Test Budget", skill)
        self.assertIn("5-12 cases per target", skill)

    # --- New: Test Structure ---

    def test_test_structure_parallel_safety(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Test Structure Standard", skill)
        self.assertIn("t.Parallel()", skill)
        self.assertIn("Do NOT use `t.Parallel()`", skill)

    # --- New: Workflow includes new gates ---

    def test_workflow_includes_version_and_exclusion_steps(self) -> None:
        skill = SKILL_MD.read_text()
        workflow_start = skill.index("## Workflow")
        workflow_section = skill[workflow_start : workflow_start + 2000]
        self.assertIn("go.mod", workflow_section)
        self.assertIn("Generated Code Exclusion", workflow_section)

    # --- New: Incremental Mode ---

    def test_incremental_mode_three_flows(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Incremental Mode", skill)
        self.assertIn("Fix failing test", skill)
        self.assertIn("Add tests for existing code", skill)
        self.assertIn("Coverage recovery", skill)

    # --- New: Output includes version/exclusion info ---

    def test_output_expectations_include_version_and_exclusion(self) -> None:
        skill = SKILL_MD.read_text()
        output_start = skill.index("## Output Expectations")
        output_section = skill[output_start:]
        self.assertIn("Go version", output_section)
        self.assertIn("Generated files excluded", output_section)

    # --- New: Scorecard weight tiers ---

    def test_scorecard_has_weight_tiers(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("**Critical**", skill)
        self.assertIn("**Standard**", skill)
        self.assertIn("**Hygiene**", skill)

    def test_scorecard_critical_items(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("[Critical]** Assertions are mutation-resistant", skill)
        self.assertIn("[Critical]** Killer case exists", skill)
        self.assertIn("[Critical]** Coverage meets gate", skill)

    # --- New: Test execution hardening ---

    def test_shuffle_guidance_exists(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("go test -shuffle=on", skill)
        self.assertIn("hidden state coupling", skill)

    def test_fuzzing_collaboration_guidance(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Fuzzing collaboration", skill)
        self.assertIn("FuzzXxx", skill)

    # --- New: PR-diff scoped testing ---

    def test_pr_diff_scope_section_exists(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("PR-Diff Scoped Testing", skill)
        self.assertIn("git diff --name-only", skill)

    # --- New: Machine-readable JSON outputexample ---

    def test_json_summary_exists(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Machine-Readable Summary (JSON)", skill)
        self.assertIn('"scorecard"', skill)
        self.assertIn('"coverage"', skill)

    # --- New: Anti-examples count updated ---

    def test_anti_examples_expanded_count(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("snapshot/golden files", skill)
        self.assertIn("implementation details instead of behavior", skill)


if __name__ == "__main__":
    unittest.main()

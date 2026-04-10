import re
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
CONFIG_EXAMPLE = SKILL_DIR / "references" / "unit-test-config.example.yaml"
REFERENCE_DIR = SKILL_DIR / "references"
BOUNDARY_SCORECARD_REF = SKILL_DIR / "references" / "boundary-scorecard.md"


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
            "Full 13-check scorecard mandatory.", skill
        )
        self.assertIn("Incremental mode", skill)
        self.assertIn("Incremental mode: full scorecard skipped", skill)

    def test_scorecard_boundary_for_light_mode(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Light mode: standard scorecard not applicable", skill)

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
        self.assertIn("Defect-First Workflow (Standard + Strict Modes)", skill)
        self.assertIn("Loop/index risks", skill)
        self.assertIn("Collection transform risks", skill)
        self.assertIn("Branching risks", skill)
        self.assertIn("Concurrency risks", skill)
        self.assertIn("Context/time risks", skill)

    # --- New: Boundary Checklist ---

    def test_boundary_checklist_has_twelve_items(self) -> None:
        # Full 12-item checklist lives in references/boundary-scorecard.md;
        # SKILL.md retains a stub with a pointer to that file.
        skill = SKILL_MD.read_text()
        self.assertIn("Fixed Boundary Checklist", skill)
        self.assertIn("boundary-scorecard.md", skill)
        ref = BOUNDARY_SCORECARD_REF.read_text()
        for i in range(1, 13):
            self.assertRegex(
                ref,
                rf"\b{i}\.\s+",
                f"Boundary checklist item {i} not found in boundary-scorecard.md",
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
        self.assertIn("3-6", skill)
        self.assertIn("5-12", skill)
        self.assertIn("8-15+", skill)

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
        # Numbered items live in references/boundary-scorecard.md (table format) after refactor.
        ref = BOUNDARY_SCORECARD_REF.read_text()
        self.assertIn("[Critical] | Assertions are mutation-resistant", ref)
        self.assertIn("[Critical] | Killer case exists", ref)
        self.assertIn("[Critical] | Coverage meets gate", ref)

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

    def test_json_summary_gated_to_standard_strict(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Standard + Strict Only", skill)
        self.assertIn("skip for Light mode", skill)

    # --- New: Anti-examples count updated ---

    def test_anti_examples_expanded_count(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("snapshot/golden files", skill)
        self.assertIn("implementation details instead of behavior", skill)

    # --- New: Execution Modes ---

    def test_execution_modes_section_exists(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Execution Modes (Light / Standard / Strict)", skill)
        self.assertIn("Light", skill)
        self.assertIn("Standard", skill)
        self.assertIn("Strict", skill)

    def test_mode_selection_table_exists(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Mode Selection", skill)
        self.assertIn("Target count", skill)
        self.assertIn("Concurrency", skill)
        self.assertIn("When in doubt, choose Standard", skill)

    def test_light_scorecard_exists(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Light Scorecard (7 checks)", skill)
        for i in range(1, 8):
            self.assertIn(f"L{i}", skill)

    def test_light_scorecard_critical_items(self) -> None:
        skill = SKILL_MD.read_text()
        light_start = skill.index("Light Scorecard (7 checks)")
        light_section = skill[light_start : light_start + 1000]
        # L3 and L7 must be Critical
        self.assertIn("L3", light_section)
        self.assertIn("L7", light_section)
        critical_count = light_section.count("**Critical**")
        self.assertEqual(critical_count, 2, "Light scorecard must have exactly 2 Critical items")

    def test_light_boundary_check_exists(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Light Boundary Check (5 items)", skill)
        check_start = skill.index("Light Boundary Check (5 items)")
        check_section = skill[check_start : check_start + 500]
        for i in range(1, 6):
            self.assertRegex(
                check_section,
                rf"\b{i}\.\s+",
                f"Light boundary check item {i} not found",
            )

    def test_mode_declaration_required(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Declare the selected mode and rationale", skill)

    def test_mode_requirements_table_exists(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Mode Requirements", skill)
        self.assertIn("Case budget per target", skill)
        self.assertIn("Failure Hypothesis List", skill)

    def test_mode_aware_killer_case(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Killer Case hard constraint (Standard + Strict)", skill)
        self.assertIn("Killer Case — Definition (Standard + Strict Modes)", skill)

    def test_mode_aware_defect_workflow(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Defect-First Workflow (Standard + Strict Modes)", skill)

    def test_mode_aware_case_budget(self) -> None:
        skill = SKILL_MD.read_text()
        budget_start = skill.index("High-Signal Test Budget")
        budget_section = skill[budget_start : budget_start + 500]
        self.assertIn("3-6", budget_section)
        self.assertIn("5-12", budget_section)
        self.assertIn("8-15+", budget_section)

    def test_workflow_step_zero_mode_selection(self) -> None:
        skill = SKILL_MD.read_text()
        workflow_start = skill.index("## Workflow")
        workflow_section = skill[workflow_start : workflow_start + 500]
        self.assertIn("select execution mode", workflow_section)

    # --- New: Property-Based Testing ---

    def test_property_based_testing_section_exists(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Property-Based Testing", skill)
        self.assertIn("Roundtrip", skill)
        self.assertIn("Idempotency", skill)
        self.assertIn("Preservation", skill)

    def test_property_based_testing_quick_reference(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("testing/quick", skill)
        self.assertIn("quick.Check", skill)

    def test_property_based_testing_mode_applicability(self) -> None:
        skill = SKILL_MD.read_text()
        pbt_start = skill.index("Property-Based Testing")
        pbt_section = skill[pbt_start : pbt_start + 2000]
        self.assertIn("Light", pbt_section)
        self.assertIn("Standard", pbt_section)
        self.assertIn("Strict", pbt_section)

    def test_property_based_testing_reference_exists(self) -> None:
        ref = REFERENCE_DIR / "property-based-testing.md"
        self.assertTrue(ref.exists(), "property-based-testing.md reference must exist")

    # --- New: Output includes mode ---

    def test_output_expectations_include_mode(self) -> None:
        skill = SKILL_MD.read_text()
        output_start = skill.index("## Output Expectations")
        output_section = skill[output_start:]
        self.assertIn("Execution mode (Light/Standard/Strict)", output_section)

    def test_light_mode_output_reduction(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Light mode output reduction", skill)

    # --- New: Config mode key ---

    def test_config_mode_key_documented(self) -> None:
        skill = SKILL_MD.read_text()
        config_start = skill.index("Repository Config (Optional)")
        config_section = skill[config_start : config_start + 1500]
        self.assertIn("`mode`", config_section)
        self.assertIn("auto|light|standard|strict", config_section)

    def test_config_mode_is_floor_not_override(self) -> None:
        skill = SKILL_MD.read_text()
        config_start = skill.index("Repository Config (Optional)")
        config_section = skill[config_start : config_start + 1500]
        self.assertIn("minimum mode floor", config_section)
        self.assertIn("higher mode wins", config_section)

    def test_config_example_has_mode_key(self) -> None:
        cfg = CONFIG_EXAMPLE.read_text()
        self.assertIn("mode: auto", cfg)

    def test_config_example_comment_matches_floor_semantics(self) -> None:
        """Config YAML comment must say 'minimum mode floor', not 'override'."""
        cfg = CONFIG_EXAMPLE.read_text()
        self.assertIn("minimum mode floor", cfg)
        self.assertNotIn("Override auto-selection", cfg)

    # --- New: Workflow step 6 mode-aware budget ---

    def test_workflow_step_six_mode_aware_budget(self) -> None:
        skill = SKILL_MD.read_text()
        workflow_start = skill.index("## Workflow")
        workflow_section = skill[workflow_start : workflow_start + 1000]
        self.assertIn("Light: 3-6", workflow_section)
        self.assertIn("Standard: 5-12", workflow_section)
        self.assertIn("Strict: 8-15+", workflow_section)

    # --- Fix: Strict target-count trigger ---

    def test_strict_target_count_is_not_universal(self) -> None:
        skill = SKILL_MD.read_text()
        mode_start = skill.index("Mode Selection")
        mode_section = skill[mode_start : mode_start + 500]
        self.assertNotIn("Any count", mode_section)
        self.assertIn("> 8 targets", mode_section)

    # --- Fix: Invariant pattern triggers mode promotion ---

    def test_invariant_pattern_in_mode_selection(self) -> None:
        skill = SKILL_MD.read_text()
        mode_start = skill.index("Mode Selection")
        mode_section = skill[mode_start : mode_start + 1000]
        self.assertIn("Invariant patterns", mode_section)
        self.assertIn("roundtrip", mode_section.lower())
        self.assertIn("commutativity", mode_section.lower())
        self.assertIn("parse validity", mode_section.lower())

    def test_light_mode_auto_promotes_on_invariant(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("auto-promote to Standard", skill)

    # --- Fix: Workflow step 12 gated to Standard + Strict ---

    def test_workflow_step_twelve_gated(self) -> None:
        skill = SKILL_MD.read_text()
        workflow_start = skill.index("## Workflow")
        workflow_section = skill[workflow_start : workflow_start + 1500]
        # Find step 12 and verify it has mode gate
        step12_idx = workflow_section.index("Verify killer case integrity")
        step12_context = workflow_section[step12_idx - 40 : step12_idx + 50]
        self.assertIn("Standard + Strict only", step12_context)

    # --- Fix: Trivial commutativity excluded from mode promotion ---

    def test_trivial_commutativity_excluded(self) -> None:
        skill = SKILL_MD.read_text()
        mode_start = skill.index("Mode Selection")
        mode_section = skill[mode_start : mode_start + 800]
        self.assertIn("trivial arithmetic commutativity", mode_section.lower())
        self.assertIn("does not count", mode_section.lower())

    # --- Fix: Light scorecard N/A handling ---

    def test_light_scorecard_na_handling(self) -> None:
        skill = SKILL_MD.read_text()
        light_start = skill.index("Light Scorecard (7 checks)")
        light_section = skill[light_start : light_start + 800]
        self.assertIn("N/A handling", light_section)
        self.assertIn("count as PASS", light_section)

    # --- Fix: Incremental mode is mode-aware ---

    def test_incremental_mode_is_mode_aware(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Incremental mode (Standard/Strict targets)", skill)
        self.assertIn("Incremental mode (Light targets)", skill)
        self.assertIn("Incremental + Light mode: minimal scorecard", skill)

    def test_incremental_add_tests_flow_is_mode_aware(self) -> None:
        """The 'Add tests for existing code' incremental flow must gate
        Failure Hypothesis List and use mode-aware scorecard items."""
        skill = SKILL_MD.read_text()
        inc_start = skill.index("### Add tests for existing code:")
        inc_section = skill[inc_start : inc_start + 600]
        # Failure Hypothesis List gated to Standard + Strict
        self.assertIn("(Standard + Strict only)", inc_section)
        self.assertIn("Failure Hypothesis List", inc_section)
        # Scorecard is mode-aware
        self.assertIn("Standard/Strict targets", inc_section)
        self.assertIn("Light targets", inc_section)
        self.assertIn("L3, L5, L7", inc_section)

    # --- Fix: No unreachable force-Light path in PBT ---

    def test_no_force_light_config_path_in_pbt(self) -> None:
        skill = SKILL_MD.read_text()
        pbt_start = skill.index("Property-Based Testing")
        pbt_section = skill[pbt_start : pbt_start + 2000]
        self.assertNotIn("forces Light mode via config", pbt_section)
        self.assertNotIn("explicitly forces Light", pbt_section)

    # --- Fix: Collection transforms excluded from Light mode ---

    def test_collection_transforms_excluded_from_light(self) -> None:
        skill = SKILL_MD.read_text()
        mode_start = skill.index("Mode Selection")
        mode_section = skill[mode_start : mode_start + 1000]
        self.assertIn("Collection transforms", mode_section)
        self.assertIn("scalar I/O only", mode_section)

    def test_light_description_excludes_collection_transforms(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("NOT for collection/slice/map transforms", skill)

    # --- New: SKILL.md line budget ---

    def test_skill_md_stays_within_line_budget(self) -> None:
        lines = len(SKILL_MD.read_text().splitlines())
        self.assertLessEqual(lines, 500, f"SKILL.md too long: {lines} lines (budget: 500)")

    # --- New: boundary-scorecard.md reference integrity ---

    def test_boundary_scorecard_reference_exists(self) -> None:
        self.assertTrue(
            BOUNDARY_SCORECARD_REF.exists(),
            "references/boundary-scorecard.md must exist",
        )

    def test_boundary_scorecard_has_pass_criteria(self) -> None:
        ref = BOUNDARY_SCORECARD_REF.read_text()
        self.assertIn("Final PASS Criteria", ref)
        self.assertIn("All 3 Critical items", ref)
        self.assertIn(">= 4/5", ref)


if __name__ == "__main__":
    unittest.main()

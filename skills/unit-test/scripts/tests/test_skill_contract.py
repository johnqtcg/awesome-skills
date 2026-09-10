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
        self.assertIn("Kill verification", skill)

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
        self.assertIn("`Kill: Verified`", skill)

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

    # --- New: Machine-readable JSON output ---

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
        # Anchored on the step number rather than on a fixed character window and a
        # phrase from the step's body: both broke when step 12 was reworded, reporting
        # a substring error instead of the rule this test is about (the mode gate).
        skill = SKILL_MD.read_text()
        start = skill.index("## Workflow")
        workflow = skill[start : skill.index("### Reporting Integrity", start)]
        step12 = [ln for ln in workflow.splitlines() if ln.startswith("12. ")]
        self.assertTrue(step12, "workflow step 12 not found")
        self.assertIn("Standard + Strict only", step12[0])
        self.assertIn("killer case", step12[0].lower())

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

    # Budget raised 500 -> 520 in round 5. The round-4/5 correctness fixes (coverage
    # measurement scope, and separating "the case kills the mutation" from "this
    # assertion is indispensable") needed more precise wording, which left 2 lines of
    # headroom under the old number — a budget that tight fires on the next edit
    # regardless of merit. The guard's job is to bound growth, not to freeze a round
    # number: the next addition should still trim or move content into `references/`.
    SKILL_MD_LINE_BUDGET = 520

    def test_skill_md_stays_within_line_budget(self) -> None:
        lines = len(SKILL_MD.read_text().splitlines())
        self.assertLessEqual(
            lines, self.SKILL_MD_LINE_BUDGET,
            f"SKILL.md too long: {lines} lines (budget: {self.SKILL_MD_LINE_BUDGET})")

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


class EngineeringReliabilityGuardTests(unittest.TestCase):
    """Guards for the round-2/round-3 correctness fixes. Each pins a rule that was
    wrong before and would silently regress without a guard (the gap the reviewer
    flagged: 'the rules are right now, but nothing fails if a future edit breaks them')."""

    @classmethod
    def setUpClass(cls):
        cls.skill = SKILL_MD.read_text()
        cls.scorecard = BOUNDARY_SCORECARD_REF.read_text()
        cls.all_text = cls.skill + "\n" + "\n".join(
            p.read_text() for p in sorted(REFERENCE_DIR.glob("*.md"))
        )

    # --- PR discovery portability (the macOS xargs -d / go-list ./ bug) ---

    @staticmethod
    def _code_fences(text: str) -> str:
        """Concatenate the contents of every ``` fenced code block. Prose is
        excluded — a pitfall may be *named* in prose but must not appear as an
        actual command."""
        parts, inside, buf = [], False, []
        for line in text.splitlines():
            if line.lstrip().startswith("```"):
                if inside:
                    parts.append("\n".join(buf))
                    buf = []
                inside = not inside
                continue
            if inside:
                buf.append(line)
        return "\n".join(parts)

    def _pr_diff_section(self) -> str:
        start = self.skill.index("PR-Diff Scoped Testing")
        end = self.skill.index("### Generated Code Exclusion", start)
        return self.skill[start:end]

    def test_no_xargs_d_in_any_command(self):
        # `xargs -d` is GNU-only and errors on BSD/macOS. It may be *named* in
        # prose as the pitfall to avoid, but no actual command may use it.
        self.assertNotIn("xargs -d", self._code_fences(self.all_text))

    def test_pr_discovery_uses_portable_readloop(self):
        code = self._code_fences(self._pr_diff_section())
        self.assertIn("while IFS= read", code)      # portable, not xargs -d
        self.assertIn("printf './%s", code)          # ./-prefix so go list sees a dir
        self.assertIn('go list "$d"', code)
        self.assertNotIn("xargs -d", code)

    def test_pr_discovery_documents_dot_prefix_reason(self):
        # The whole point of the ./ prefix: a bare path is read as an import path.
        self.assertIn("import path", self._pr_diff_section())

    # --- Mode: target count is NOT a standalone Strict trigger ---

    def test_target_count_not_standalone_trigger_in_table(self):
        start = self.skill.index("Mode Selection")
        section = self.skill[start:start + 900]
        self.assertIn("> 8 targets", section)
        self.assertIn("not a standalone trigger", section)  # in the TABLE cell itself

    def test_mode_rule_says_risk_not_count(self):
        self.assertIn("risk-driven, not count-driven", self.skill)
        self.assertIn("Target count alone does not", self.skill)

    # --- Table-driven gated to 2+ cases (not unconditional) ---

    def test_table_driven_requires_two_plus_cases(self):
        self.assertIn("Required (2+ cases)", self.skill)          # mode requirements
        self.assertIn("2+ cases", self.scorecard)                # scorecard item 4

    # --- Race detection precedence resolved ---

    def test_race_precedence_documented(self):
        self.assertIn("config > PR scope > mode default", self.skill)
        self.assertIn("race.required: false", self.skill)

    # --- Case budget is a soft ceiling, not a minimum to pad to ---

    def test_case_budget_is_soft_ceiling_not_minimum(self):
        self.assertIn("soft ceiling", self.skill)
        self.assertIn("NOT minimums to pad to", self.skill)
        self.assertIn("distinct logic paths", self.skill)


class CoverageScopeGuardTests(unittest.TestCase):
    """Round-4 review: the skill told the reader to exclude a package from the gate
    because it "reports 0%" when it has no `_test.go`. Under `-coverpkg` that console
    line is not the package's coverage — `test_behavioral_killer` now executes the
    proof that a test-less package can be 100% covered by a sibling's tests. These
    guards keep the *rule* from reverting, scoped to the section that states it so an
    unrelated mention elsewhere cannot satisfy them."""

    @classmethod
    def setUpClass(cls):
        skill = SKILL_MD.read_text()
        start = skill.index("#### Multi-Package Coverage")
        cls.section = skill[start:skill.index("### Go Version Gate", start)]

    def test_gate_number_is_read_from_the_merged_profile(self):
        self.assertIn("merged profile", self.section)
        self.assertIn("go tool cover -func=cover.out", self.section)
        self.assertIn("-coverpkg=./...", self.section)

    def test_console_zero_percent_is_documented_as_misleading(self):
        self.assertRegex(
            self.section, r"no test binary of its own still prints `coverage: 0\.0%",
            "the section must explain WHY the 0.0% console line cannot be used")

    def test_absence_of_a_test_file_is_not_an_exclusion_reason(self):
        self.assertIn("NOT a valid exclusion reason", self.section)
        # Bound to the right subject: the sentence that rejects the reason must be the
        # one that names `_test.go`, not some other exclusion rule in the section.
        rejecting = [b for b in self.section.split("\n- ")
                     if "NOT a valid exclusion reason" in b]
        self.assertTrue(rejecting, self.section)
        self.assertIn("_test.go", rejecting[0])
        self.assertIn("coverage gap", rejecting[0])

    def test_old_exclude_because_zero_percent_rule_is_gone(self):
        for wrong in ("exclude them from gate calculations",
                      "report 0% — exclude"):
            self.assertNotIn(wrong, self.section,
                             f"the reverted rule {wrong!r} is back in § Multi-Package Coverage")

    def test_valid_exclusions_are_enumerated_by_reason(self):
        self.assertIn("Valid exclusions", self.section)
        for reason in ("generated code", "cmd/**", "out of scope", "vendored"):
            self.assertIn(reason, self.section)


class KillerCaseVerificationGuardTests(unittest.TestCase):
    """Round-4/5 review: every killer case had to assert "if this assertion is removed,
    the known bug can escape detection" — but nothing required running anything, so a
    hypothesis was reported in the grammar of a result. Round 5 went further: that
    sentence conflates two different claims. Injecting the defect shows the *case*
    catches it; only deleting the named assertion (defect still injected) and seeing the
    test PASS shows that *assertion* is what catches it. The repository proves the
    difference by execution in `test_behavioral_killer`
    (`test_removing_an_assertion_can_still_leave_the_mutation_caught`).

    So the mandatory report item is now the kill status, and an assertion-necessity claim
    is optional and only permitted after its own check."""

    @classmethod
    def setUpClass(cls):
        cls.skill = SKILL_MD.read_text()
        cls.patterns = (REFERENCE_DIR / "killer-case-patterns.md").read_text()
        cls.scorecard = BOUNDARY_SCORECARD_REF.read_text()

    def _section(self, start: str, end: str) -> str:
        begin = self.skill.index(start)
        return self.skill[begin:self.skill.index(end, begin)]

    def _hard_rules(self) -> str:
        return self._section("## Hard Rules", "### Killer Case — Definition")

    def test_hard_rule_requires_a_kill_label(self):
        rules = self._hard_rules()
        self.assertIn("`Kill: Verified`", rules)
        self.assertIn("`Kill: Unverified`", rules)

    def test_unverified_kill_is_labelled_a_hypothesis_not_a_result(self):
        self.assertRegex(
            self._hard_rules(), r"defect hypothesis, not a demonstrated result",
            "the skill must say plainly that an unverified kill is not a result")

    def test_hard_rule_forbids_an_unchecked_necessity_claim(self):
        rules = self._hard_rules()
        self.assertIn("Do NOT claim an assertion is indispensable unless you checked that "
                      "separately", rules)
        # And it must explain the distinction, not merely forbid the claim.
        for phrase in ("shows the *case* catches it",
                       "while the defect is still injected",
                       "Redundant assertions are normal"):
            self.assertIn(phrase, rules, f"Hard Rules no longer explains: {phrase!r}")

    def test_killer_case_definition_component_four_is_the_kill_check(self):
        definition = self._section("### Killer Case — Definition", "### Anti-examples")
        component = [ln for ln in definition.splitlines() if ln.startswith("4. ")]
        self.assertTrue(component, definition)
        self.assertIn("Kill: Verified", component[0])
        self.assertIn("Kill: Unverified", component[0])
        self.assertIn("separate, optional", component[0])

    def test_workflow_step_twelve_requires_execution(self):
        workflow = self._section("## Workflow", "### Reporting Integrity")
        step = [ln for ln in workflow.splitlines() if ln.startswith("12. ")]
        self.assertTrue(step, workflow)
        self.assertIn("by executing it", step[0])
        self.assertIn("revert", step[0].lower())
        self.assertIn("Kill: Verified", step[0])

    def test_output_expectations_report_the_kill_status(self):
        output = self._section("## Output Expectations", "### Machine-Readable Summary")
        self.assertIn("Kill: Verified", output)
        self.assertIn("Kill: Unverified", output)
        self.assertRegex(
            output, r"`Assertion necessity` — include ONLY if",
            "the report format must gate the necessity claim on having run the check")

    def test_reference_separates_the_two_experiments(self):
        self.assertIn("## Verifying the Kill", self.patterns)
        self.assertIn("### A. Kill check — mandatory", self.patterns)
        self.assertIn("### B. Assertion-necessity check — optional", self.patterns)
        # The distinguishing conclusion: still failing after removal REFUTES necessity.
        self.assertIn("so the claim is **false**", self.patterns)
        self.assertIn("(assertion, defect) pair", self.patterns)
        self.assertIn("Expect the negative result more often than not", self.patterns)
        self.assertIn("Revert every mutation", self.patterns)
        for fake in ("does not compile", "on the original", "different assertion"):
            self.assertTrue(fake in self.patterns,
                            f"§ Verifying the Kill no longer names the {fake!r} fake-kill mode")

    def test_scorecard_item_eleven_scores_the_kill_status(self):
        item = [ln for ln in self.scorecard.splitlines() if ln.startswith("| 11 |")]
        self.assertTrue(item, "scorecard item 11 not found")
        self.assertIn("Kill: Verified", item[0])
        # An honest Unverified must not be punished; an unlabelled claim must be; and
        # item 11 must not require a necessity claim it cannot verify.
        self.assertIn("An honest `Kill: Unverified` with a reason still PASSES",
                      self.scorecard)
        self.assertIn("**unlabelled** kill claim is a FAIL", self.scorecard)
        self.assertIn("`Assertion necessity` claim is **not** required by this item",
                      self.scorecard)


class KillLabelSweepTests(unittest.TestCase):
    """Sweep every shipped asset, not the one line a review cited.

    Round 4 fixed SKILL.md and left `bug-finding-techniques.md` shipping a second
    **report template** that produced an unlabelled claim. Round 5 retired the blanket
    "if this assertion is removed…" sentence, which had to be removed from 10 places
    across SKILL.md and four references — and the indispensability wording may now
    appear ONLY where the separate necessity check is defined.

    Occurrences inside ```go fences are code comments, swept separately: they must state
    the kill check, not an unverified necessity claim.
    """

    ASSETS = None

    @classmethod
    def setUpClass(cls):
        cls.ASSETS = [SKILL_MD, *sorted(REFERENCE_DIR.glob("*.md"))]

    @staticmethod
    def _segments(text: str):
        """Yield (kind, body): 'go' / 'fence' for fenced blocks, else the heading line."""
        prose, section = [], "(top)"
        lines, i = text.splitlines(), 0
        while i < len(lines):
            line = lines[i]
            if line.lstrip().startswith("```"):
                lang = line.lstrip()[3:].strip().lower()
                body, i = [], i + 1
                while i < len(lines) and not lines[i].lstrip().startswith("```"):
                    body.append(lines[i])
                    i += 1
                yield ("go" if lang == "go" else "fence", "\n".join(body))
                i += 1
                continue
            if line.startswith("#"):
                if prose:
                    yield (section, "\n".join(prose))
                    prose = []
                section = line.strip()
            prose.append(line)
            i += 1
        if prose:
            yield (section, "\n".join(prose))

    def _matching_segments(self, needle: str, skip_go: bool = True):
        found = []
        for path in self.ASSETS:
            for kind, body in self._segments(path.read_text()):
                if needle.lower() in body.lower() and not (skip_go and kind == "go"):
                    found.append((path.name, kind, body))
        return found

    def test_indispensability_wording_only_where_the_check_is_defined(self):
        """The blanket sentence is retired. Any remaining discussion of removing an
        assertion must sit with the necessity check that decides it — otherwise the
        unverifiable mandate is back under a new heading."""
        offenders = [
            f"{name} [{kind}]"
            for name, kind, body in self._matching_segments("assertion is removed")
            if "necessity" not in body.lower()
        ]
        self.assertEqual(
            [], offenders,
            f"these discuss removing an assertion without the necessity check that "
            f"establishes it: {offenders}")

    def test_every_killer_case_report_template_carries_the_kill_label(self):
        """A fenced report template (identified by `Defect hypothesis:`) shows the reader
        the exact output shape, so it must carry the mandatory kill status."""
        templates = self._matching_segments("Defect hypothesis:")
        offenders = [f"{name} [{kind}]" for name, kind, body in templates
                     if "Kill:" not in body]
        self.assertEqual([], offenders,
                         f"report templates missing the `Kill:` status: {offenders}")
        self.assertGreaterEqual(
            len(templates), 1,
            "anti-vacuity: the sweep found no report template at all, so it would pass "
            "no matter what those templates said")

    def test_go_template_comments_state_the_kill_check(self):
        """The 7 in-code comments used to assert indispensability, which the necessity
        check refutes for most of them. They must state the kill check instead."""
        claims, checks = [], 0
        for path in self.ASSETS:
            for kind, body in self._segments(path.read_text()):
                if kind != "go":
                    continue
                if "assertion is removed" in body.lower():
                    claims.append(path.name)
                checks += body.count("Kill check: with the named defect injected")
        self.assertEqual([], claims,
                         f"go template comments still assert indispensability: {claims}")
        self.assertGreaterEqual(checks, 7,
                                f"expected the kill-check comment in every killer-case "
                                f"template, found {checks}")


class SkipIsNotCoverageGuardTests(unittest.TestCase):
    """Round-6 review: two subtests were changed to `t.Skip()` and the grader still
    reported the hypothesis covered — the names matched, the count matched, nothing had
    run. The rule now exists at the skill level too, because the same confusion produces
    a boundary item marked `Covered` by a case that asserted nothing."""

    @classmethod
    def setUpClass(cls):
        cls.skill = SKILL_MD.read_text()
        cls.scorecard = BOUNDARY_SCORECARD_REF.read_text()

    def test_reporting_integrity_says_a_skip_is_not_verification(self):
        start = self.skill.index("### Reporting Integrity")
        section = self.skill[start:self.skill.index("## Auto Scorecard", start)]
        self.assertIn("skipped** case is discovered, not verified", section)
        self.assertIn("--- SKIP", section)
        self.assertIn("Kill: Verified", section)

    def test_anti_examples_reject_skip_as_a_pass(self):
        start = self.skill.index("### Anti-examples")
        section = self.skill[start:self.skill.index("### Coverage Gate Policy", start)]
        self.assertRegex(section, r"`t\.Skip\(\)` to get a case to \"pass\"")

    def test_boundary_checklist_marks_a_skipped_case_as_a_gap(self):
        self.assertIn("does not make its item `Covered`", self.scorecard)
        self.assertIn("--- SKIP", self.scorecard)


class HypothesisMustBeCheckableGuardTests(unittest.TestCase):
    """Round-6 review: the exemplar's H2 promised an empty but NON-NIL result and only
    asserted length and elements. `len(nil) == 0`, so `var out []string` satisfied every
    assertion — the promise was stated, given an input scenario, and never verified."""

    @classmethod
    def setUpClass(cls):
        cls.skill = SKILL_MD.read_text()
        cls.techniques = (REFERENCE_DIR / "bug-finding-techniques.md").read_text()

    def _workflow_section(self) -> str:
        start = self.skill.index("## Defect-First Workflow")
        return self.skill[start:self.skill.index("## High-Signal Test Budget", start)]

    def test_each_hypothesis_must_name_the_change_that_violates_it(self):
        section = self._workflow_section()
        self.assertIn("the change to the implementation that would violate it", section)
        self.assertIn("not checkable as written", section)

    def test_supplying_the_input_is_not_verification(self):
        section = self._workflow_section()
        self.assertIn("Supplying the input is **not** verification", section)
        # And it must name the concrete counterexample, not just the abstract rule.
        self.assertIn("var out []string", section)

    def test_anti_examples_reject_length_only_nil_coverage(self):
        start = self.skill.index("### Anti-examples")
        section = self.skill[start:self.skill.index("### Coverage Gate Policy", start)]
        self.assertIn("`len(nil) == 0`", section)

    def test_reference_documents_the_nil_versus_empty_trap(self):
        self.assertIn("`nil` vs empty is invisible to `len`", self.techniques)
        self.assertIn("want a non-nil slice", self.techniques)
        # The decision must route through the contract, not the current implementation.
        self.assertIn("reading the contract, not the implementation", self.techniques)
        self.assertIn("is not a contract", self.techniques)


if __name__ == "__main__":
    unittest.main()

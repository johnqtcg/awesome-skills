import json
import re
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
TDD_REF = SKILL_DIR / "references" / "tdd-workflow.md"
API_REF = SKILL_DIR / "references" / "api-3layer-template.md"
FAKE_REF = SKILL_DIR / "references" / "fake-stub-template.md"
BOUNDARY_REF = SKILL_DIR / "references" / "boundary-checklist.md"
GOLDEN_DIR = SKILL_DIR / "scripts" / "tests" / "golden"


def frontmatter(text: str) -> str:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError("missing yaml frontmatter")
    return match.group(1)


class TestFrontmatter(unittest.TestCase):
    def test_name_and_description(self) -> None:
        content = SKILL_MD.read_text()
        fm = frontmatter(content)
        self.assertIn("name: tdd-workflow", fm)
        self.assertIn("Red-Green-Refactor", fm)

    def test_trigger_keywords(self) -> None:
        content = SKILL_MD.read_text()
        fm = frontmatter(content)
        self.assertTrue(
            "TDD" in fm or "Test-Driven" in fm,
            "Frontmatter should mention TDD or Test-Driven",
        )


class TestCoreGates(unittest.TestCase):
    def test_six_gates_exist(self) -> None:
        content = SKILL_MD.read_text()
        gates = [
            "Defect Hypothesis Gate",
            "Killer Case Gate",
            "Coverage Gate",
            "Execution Integrity Gate",
            "Concurrency Determinism Gate",
            "Change-Size Test Budget Gate",
        ]
        for gate in gates:
            self.assertIn(gate, content, f"Missing gate: {gate}")

    def test_defect_hypothesis_gate_has_substance(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("hypothesis", content.lower())
        self.assertIn("test case", content.lower())

    def test_killer_case_gate_has_substance(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("killer", content.lower())
        self.assertIn("defect", content.lower())

    def test_coverage_gate_threshold(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("80%", content)

    def test_concurrency_gate_race_detection(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("-race", content)


class TestAntiExamples(unittest.TestCase):
    def test_anti_examples_section_exists(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Anti-Examples", content)

    def test_at_least_6_anti_examples(self) -> None:
        content = SKILL_MD.read_text()
        mistake_count = content.count("### Mistake")
        self.assertGreaterEqual(mistake_count, 6, f"Expected >=6 anti-examples, found {mistake_count}")

    def test_anti_examples_have_bad_good_code(self) -> None:
        content = SKILL_MD.read_text()
        anti_section_start = content.find("## Anti-Examples")
        anti_section_end = content.find("## Quality Scorecard")
        if anti_section_end == -1:
            anti_section_end = len(content)
        section = content[anti_section_start:anti_section_end]
        self.assertGreaterEqual(section.count("// BAD"), 6)
        self.assertGreaterEqual(section.count("// GOOD"), 6)

    def test_anti_example_big_bang_red(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Big-Bang Red", content)

    def test_anti_example_speculative_code(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("speculative", content.lower())

    def test_anti_example_refactor_behavior_change(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Refactor phase changes observable behavior", content)

    def test_anti_example_skip_red_evidence(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Skipping Red evidence", content)

    def test_anti_example_implementation_details(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("implementation details", content.lower())

    def test_anti_example_change_size_mismatch(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Change-size mismatch", content)


class TestScorecard(unittest.TestCase):
    def test_scorecard_section_exists(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("## Quality Scorecard", content)

    def test_three_tiers(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("### Critical", content)
        self.assertIn("### Standard", content)
        self.assertIn("### Hygiene", content)

    def test_critical_items(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("C1", content)
        self.assertIn("C2", content)
        self.assertIn("C3", content)

    def test_standard_items(self) -> None:
        content = SKILL_MD.read_text()
        for s in ["S1", "S2", "S3", "S4", "S5"]:
            self.assertIn(s, content, f"Missing standard item {s}")

    def test_hygiene_items(self) -> None:
        content = SKILL_MD.read_text()
        for h in ["H1", "H2", "H3", "H4"]:
            self.assertIn(h, content, f"Missing hygiene item {h}")

    def test_decision_rule(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("PASS", content)
        self.assertIn("FAIL", content)
        self.assertIn("All Critical", content)


class TestChangeSizeBudget(unittest.TestCase):
    def test_sml_defined(self) -> None:
        content = SKILL_MD.read_text()
        self.assertTrue("**S**" in content or "S change" in content, "S size not defined")
        self.assertTrue("**M**" in content or "M change" in content, "M size not defined")
        self.assertTrue("**L**" in content or "L change" in content, "L size not defined")

    def test_concrete_loc_thresholds(self) -> None:
        content = SKILL_MD.read_text()
        self.assertTrue(
            "50" in content and "150" in content,
            "Should have LOC thresholds (50, 150)"
        )


class TestAssertionStrategy(unittest.TestCase):
    def test_assertion_style_mentioned(self) -> None:
        content = SKILL_MD.read_text()
        lower = content.lower()
        self.assertTrue(
            "assertion style" in lower or "assertion strategy" in lower,
        )

    def test_testify_and_stdlib(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("testify", content)
        self.assertTrue(
            "stdlib" in content or "standard library" in content.lower(),
        )


class TestCrossReference(unittest.TestCase):
    def test_unit_test_skill_referenced(self) -> None:
        content = SKILL_MD.read_text()
        self.assertTrue(
            "unit-test" in content or "unit test" in content.lower(),
        )

    def test_boundary_checklist_referenced(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("boundary", content.lower())


class TestReferences(unittest.TestCase):
    def test_all_reference_files_exist(self) -> None:
        self.assertTrue(TDD_REF.exists(), "tdd-workflow.md missing")
        self.assertTrue(API_REF.exists(), "api-3layer-template.md missing")
        self.assertTrue(FAKE_REF.exists(), "fake-stub-template.md missing")
        self.assertTrue(BOUNDARY_REF.exists(), "boundary-checklist.md missing")


class TestTDDWorkflowReference(unittest.TestCase):
    def test_end_to_end_walkthrough(self) -> None:
        content = TDD_REF.read_text()
        self.assertIn("End-to-End TDD Walkthrough", content)

    def test_red_green_refactor_iterations(self) -> None:
        content = TDD_REF.read_text()
        self.assertIn("Iteration 1", content)
        self.assertIn("Iteration 2", content)
        self.assertIn("Red", content)
        self.assertIn("Green", content)

    def test_refactor_patterns_table(self) -> None:
        content = TDD_REF.read_text()
        self.assertIn("Refactor Patterns", content)
        self.assertIn("Extract Method", content)
        self.assertIn("Extract Interface", content)

    def test_outside_in_vs_inside_out(self) -> None:
        content = TDD_REF.read_text()
        self.assertIn("Outside-In", content)
        self.assertIn("Inside-Out", content)

    def test_legacy_code_characterization(self) -> None:
        content = TDD_REF.read_text()
        self.assertIn("Legacy Code", content)
        self.assertIn("Characterization", content)
        self.assertIn("characterization", content.lower())

    def test_concrete_go_code_examples(self) -> None:
        content = TDD_REF.read_text()
        self.assertIn("func ", content)
        self.assertIn("assert.", content)
        self.assertIn("require.", content)


class TestAPILayerReference(unittest.TestCase):
    def test_three_layers(self) -> None:
        content = API_REF.read_text()
        self.assertIn("Handler", content)
        self.assertIn("Service", content)
        self.assertIn("Repo", content)

    def test_scenario_matrices(self) -> None:
        content = API_REF.read_text()
        self.assertIn("200", content)
        self.assertIn("400", content)
        self.assertIn("500", content)
        self.assertIn("success", content)
        self.assertIn("dependency_error", content)

    def test_complete_handler_test_example(self) -> None:
        content = API_REF.read_text()
        self.assertIn("httptest.NewRequest", content)
        self.assertIn("httptest.NewRecorder", content)
        self.assertIn("wantStatus", content)

    def test_complete_service_test_example(self) -> None:
        content = API_REF.read_text()
        self.assertIn("func TestUserService", content)
        self.assertIn("fakeUserRepo", content)

    def test_layer_ordering_strategies(self) -> None:
        content = API_REF.read_text()
        self.assertIn("Outside-In", content)
        self.assertIn("Inside-Out", content)

    def test_naming_patterns(self) -> None:
        content = API_REF.read_text()
        self.assertIn("TestXxxHandler", content)
        self.assertIn("TestXxxService", content)
        self.assertIn("TestXxxRepo", content)


class TestBoundaryChecklist(unittest.TestCase):
    def test_12_items(self) -> None:
        content = BOUNDARY_REF.read_text()
        items = re.findall(r"^\d+\.\s", content, re.MULTILINE)
        self.assertGreaterEqual(len(items), 12, f"Expected >=12 items, found {len(items)}")

    def test_key_boundary_types(self) -> None:
        content = BOUNDARY_REF.read_text()
        for item in ["nil input", "empty value", "dependency error", "context cancellation", "concurrency", "killer case"]:
            self.assertIn(item, content, f"Missing boundary: {item}")

    def test_defect_hypothesis_patterns(self) -> None:
        content = BOUNDARY_REF.read_text()
        self.assertIn("Defect Hypothesis", content)
        self.assertIn("off-by-one", content)
        self.assertIn("error propagation", content.lower())

    def test_killer_case_design_internalized(self) -> None:
        content = BOUNDARY_REF.read_text()
        self.assertIn("Killer Case Design", content)
        self.assertIn("Defect hypothesis", content)
        self.assertIn("Fault injection", content)
        self.assertIn("Critical assertion", content)
        self.assertIn("Removal risk", content)

    def test_concrete_killer_case_code(self) -> None:
        content = BOUNDARY_REF.read_text()
        self.assertIn("```go", content)
        self.assertIn("assert.", content)


class TestGoldenFixtures(unittest.TestCase):
    def test_golden_dir_exists(self) -> None:
        self.assertTrue(GOLDEN_DIR.exists())

    def test_at_least_8_fixtures(self) -> None:
        fixtures = list(GOLDEN_DIR.glob("*.json"))
        self.assertGreaterEqual(len(fixtures), 8, f"Expected >=8, found {len(fixtures)}")

    def test_all_fixtures_valid_json(self) -> None:
        for f in GOLDEN_DIR.glob("*.json"):
            data = json.loads(f.read_text())
            self.assertIn("id", data)
            self.assertIn("change_size", data)
            self.assertIn("change_type", data)
            self.assertIn("skill_rules_that_must_fire", data)

    def test_change_sizes_covered(self) -> None:
        sizes = set()
        for f in GOLDEN_DIR.glob("*.json"):
            data = json.loads(f.read_text())
            sizes.add(data["change_size"])
        self.assertIn("S", sizes)
        self.assertIn("M", sizes)
        self.assertIn("L", sizes)

    def test_change_types_covered(self) -> None:
        types = set()
        for f in GOLDEN_DIR.glob("*.json"):
            data = json.loads(f.read_text())
            types.add(data["change_type"])
        self.assertIn("bugfix", types)
        self.assertIn("feature", types)
        self.assertIn("refactor", types)


class TestOutputContract(unittest.TestCase):
    def test_output_contract_section(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("## Output Contract", content)


if __name__ == "__main__":
    unittest.main()

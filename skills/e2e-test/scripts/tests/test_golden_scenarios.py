import json
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
REFS_DIR = SKILL_DIR / "references"


def load_golden(fixture_id: str) -> dict:
    path = GOLDEN_DIR / f"{fixture_id}.json"
    return json.loads(path.read_text())


def all_skill_text() -> str:
    text = SKILL_MD.read_text()
    for ref in REFS_DIR.glob("*.md"):
        text += "\n" + ref.read_text()
    return text


class TestGoldenFixtureStructure(unittest.TestCase):
    def test_all_fixtures_have_required_fields(self) -> None:
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            data = json.loads(path.read_text())
            for field in ["id", "description", "scenario_type", "context", "skill_rules_that_must_fire"]:
                self.assertIn(field, data, f"{path.name} missing field: {field}")

    def test_fixture_count(self) -> None:
        count = len(list(GOLDEN_DIR.glob("*.json")))
        self.assertGreaterEqual(count, 10, f"need ≥ 10 golden fixtures, found {count}")


class TestGolden001LoginJourney(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.golden = load_golden("001_new_login_journey")
        cls.full_text = all_skill_text()

    def test_scenario_type(self) -> None:
        self.assertEqual(self.golden["scenario_type"], "new_journey_coverage")

    def test_rules_fire(self) -> None:
        for rule in self.golden["skill_rules_that_must_fire"]:
            self.assertIn(rule, self.full_text, f"rule not found in skill text: {rule}")

    def test_expected_gates(self) -> None:
        for gate in self.golden["expected_gates"]:
            self.assertIn(gate, self.full_text)

    def test_output_fields_covered(self) -> None:
        skill_text = SKILL_MD.read_text()
        for field in self.golden["expected_output_fields"]:
            self.assertIn(field, skill_text)


class TestGolden002HonestScaffold(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.golden = load_golden("002_honest_scaffold_missing_account")
        cls.full_text = all_skill_text()

    def test_scenario_type(self) -> None:
        self.assertEqual(self.golden["scenario_type"], "honest_scaffold")

    def test_rules_fire(self) -> None:
        for rule in self.golden["skill_rules_that_must_fire"]:
            self.assertIn(rule, self.full_text, f"rule not found: {rule}")

    def test_scaffold_code_patterns(self) -> None:
        for pattern in self.golden["expected_code_contains"]:
            self.assertIn(pattern, self.full_text)

    def test_no_invented_values(self) -> None:
        self.assertIn("do not invent them", self.full_text)


class TestGolden003FlakyTriage(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.golden = load_golden("003_flaky_triage_async_race")
        cls.full_text = all_skill_text()

    def test_scenario_type(self) -> None:
        self.assertEqual(self.golden["scenario_type"], "flaky_triage")

    def test_rules_fire(self) -> None:
        for rule in self.golden["skill_rules_that_must_fire"]:
            self.assertIn(rule, self.full_text, f"rule not found: {rule}")

    def test_triage_steps_present(self) -> None:
        for step in self.golden["expected_triage_steps"]:
            self.assertIn(step, self.full_text)

    def test_root_cause_categories(self) -> None:
        for cat in self.golden["expected_root_cause_categories"]:
            self.assertIn(cat, self.full_text)


class TestGolden004CIGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.golden = load_golden("004_ci_gate_design")
        cls.full_text = all_skill_text()

    def test_scenario_type(self) -> None:
        self.assertEqual(self.golden["scenario_type"], "ci_gate_design")

    def test_rules_fire(self) -> None:
        for rule in self.golden["skill_rules_that_must_fire"]:
            self.assertIn(rule, self.full_text, f"rule not found: {rule}")

    def test_ci_elements(self) -> None:
        for elem in self.golden["expected_ci_elements"]:
            self.assertIn(elem, self.full_text)


class TestGolden005AgentBrowserExploration(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.golden = load_golden("005_agent_browser_exploration")
        cls.full_text = all_skill_text()

    def test_scenario_type(self) -> None:
        self.assertEqual(self.golden["scenario_type"], "exploration_to_code")

    def test_rules_fire(self) -> None:
        for rule in self.golden["skill_rules_that_must_fire"]:
            self.assertIn(rule, self.full_text, f"rule not found: {rule}")

    def test_bridge_steps_present(self) -> None:
        for step in self.golden["expected_bridge_steps"]:
            self.assertIn(step, self.full_text)


class TestGolden006NoBaseURL(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.golden = load_golden("006_no_base_url_stop")
        cls.full_text = all_skill_text()

    def test_scenario_type(self) -> None:
        self.assertEqual(self.golden["scenario_type"], "stop_condition")

    def test_rules_fire(self) -> None:
        for rule in self.golden["skill_rules_that_must_fire"]:
            self.assertIn(rule, self.full_text, f"rule not found: {rule}")

    def test_stop_conditions_documented(self) -> None:
        self.assertIn("No base URL", self.full_text)
        self.assertIn("stop and report the exact blockers", self.full_text)


class TestGolden007SerialCheckout(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.golden = load_golden("007_serial_checkout_funnel")
        cls.full_text = all_skill_text()

    def test_scenario_type(self) -> None:
        self.assertEqual(self.golden["scenario_type"], "new_journey_coverage")

    def test_rules_fire(self) -> None:
        for rule in self.golden["skill_rules_that_must_fire"]:
            self.assertIn(rule, self.full_text, f"rule not found: {rule}")

    def test_serial_justification_required(self) -> None:
        self.assertIn("serial", self.full_text)
        self.assertIn("intentionally", self.full_text)

    def test_anti_patterns_avoided_documented(self) -> None:
        for anti in self.golden["expected_anti_patterns_avoided"]:
            found = any(
                kw in self.full_text.lower()
                for kw in anti.lower().split()
                if len(kw) > 4
            )
            self.assertTrue(found, f"anti-pattern coverage missing: {anti}")


class TestGolden008VersionGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.golden = load_golden("008_version_gate_old_playwright")
        cls.full_text = all_skill_text()

    def test_scenario_type(self) -> None:
        self.assertEqual(self.golden["scenario_type"], "version_constrained")

    def test_rules_fire(self) -> None:
        for rule in self.golden["skill_rules_that_must_fire"]:
            self.assertIn(rule, self.full_text, f"rule not found: {rule}")

    def test_version_constraint_documented(self) -> None:
        self.assertIn("< 1.27", self.full_text)
        self.assertIn("getByRole", self.full_text)
        self.assertIn("locator", self.full_text)


class TestGolden009Accessibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.golden = load_golden("009_accessibility_audit")
        cls.full_text = all_skill_text()

    def test_scenario_type(self) -> None:
        self.assertEqual(self.golden["scenario_type"], "new_journey_coverage")

    def test_rules_fire(self) -> None:
        for rule in self.golden["skill_rules_that_must_fire"]:
            self.assertIn(rule, self.full_text, f"rule not found: {rule}")

    def test_code_patterns(self) -> None:
        for pattern in self.golden["expected_code_patterns"]:
            self.assertIn(pattern, self.full_text)


class TestGolden010VisualRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.golden = load_golden("010_visual_regression")
        cls.full_text = all_skill_text()

    def test_scenario_type(self) -> None:
        self.assertEqual(self.golden["scenario_type"], "new_journey_coverage")

    def test_rules_fire(self) -> None:
        for rule in self.golden["skill_rules_that_must_fire"]:
            self.assertIn(rule, self.full_text, f"rule not found: {rule}")

    def test_code_patterns(self) -> None:
        for pattern in self.golden["expected_code_patterns"]:
            self.assertIn(pattern, self.full_text)


if __name__ == "__main__":
    unittest.main()

import json
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
REFERENCE_DIR = SKILL_DIR / "references"


def _all_skill_text() -> str:
    texts = [SKILL_MD.read_text()]
    for ref in sorted(REFERENCE_DIR.glob("*.md")):
        texts.append(ref.read_text())
    return "\n".join(texts)


def _load_fixture(name: str) -> dict:
    return json.loads((GOLDEN_DIR / name).read_text())


class GoldenScenarioRuleCoverageTests(unittest.TestCase):
    """Verify that SKILL.md + reference files contain the rules needed
    to handle each golden scenario correctly."""

    @classmethod
    def setUpClass(cls):
        cls.skill_text = _all_skill_text()
        cls.skill_lower = cls.skill_text.lower()

    def _assert_rules_covered(self, fixture: dict):
        fid = fixture["id"]
        for rule in fixture["skill_rules_that_must_exist"]:
            self.assertIn(
                rule.lower(),
                self.skill_lower,
                f"Rule '{rule}' required by fixture '{fid}' not found in skill text",
            )

    # --- Individual scenario tests ---

    def test_001_pure_function_boundary(self):
        f = _load_fixture("001_pure_function_boundary.json")
        self.assertTrue(f["expect_test_generation"])
        self.assertIn("Package-level functions", self.skill_text)
        self._assert_rules_covered(f)

    def test_002_service_dependency_error(self):
        f = _load_fixture("002_service_dependency_error.json")
        self.assertTrue(f["expect_test_generation"])
        self.assertIn("Service interface", self.skill_text)
        self._assert_rules_covered(f)

    def test_003_concurrent_shared_state(self):
        f = _load_fixture("003_concurrent_shared_state.json")
        self.assertTrue(f["expect_test_generation"])
        self.assertIn("-race", self.skill_text)
        self._assert_rules_covered(f)

    def test_004_generated_code_exclusion(self):
        f = _load_fixture("004_generated_code_exclusion.json")
        self.assertFalse(f["expect_test_generation"])
        self.assertEqual(f["exclusion_reason"], "generated_code")
        self._assert_rules_covered(f)

    def test_005_trivial_getter_antiexample(self):
        f = _load_fixture("005_trivial_getter_antiexample.json")
        self.assertFalse(f["expect_test_generation"])
        self.assertEqual(f["exclusion_reason"], "anti_example")
        self._assert_rules_covered(f)

    def test_006_collection_transform(self):
        f = _load_fixture("006_collection_transform.json")
        self.assertTrue(f["expect_test_generation"])
        self._assert_rules_covered(f)

    def test_007_http_handler(self):
        f = _load_fixture("007_http_handler.json")
        self.assertTrue(f["expect_test_generation"])
        self.assertEqual(f["target_type"], "HTTP handler")
        self._assert_rules_covered(f)

    def test_008_cli_command(self):
        f = _load_fixture("008_cli_command.json")
        self.assertTrue(f["expect_test_generation"])
        self.assertEqual(f["target_type"], "CLI command/runner")
        self._assert_rules_covered(f)

    def test_009_middleware(self):
        f = _load_fixture("009_middleware.json")
        self.assertTrue(f["expect_test_generation"])
        self.assertEqual(f["target_type"], "Middleware")
        self._assert_rules_covered(f)

    def test_010_simple_pure_function_light(self):
        f = _load_fixture("010_simple_pure_function_light.json")
        self.assertTrue(f["expect_test_generation"])
        self.assertEqual(f["expected_mode"], "Light")
        self.assertIn("Package-level functions", self.skill_text)
        self._assert_rules_covered(f)

    def test_011_roundtrip_property_standard(self):
        f = _load_fixture("011_roundtrip_property_standard.json")
        self.assertTrue(f["expect_test_generation"])
        self.assertEqual(f["expected_mode"], "Standard")
        self._assert_rules_covered(f)

    # --- New: Medium-priority gap — concurrent map access ---

    def test_012_concurrent_map_access(self):
        f = _load_fixture("012_concurrent_map_access.json")
        self.assertTrue(f["expect_test_generation"])
        self.assertEqual(f["expected_mode"], "Strict")
        self.assertIn("concurrent/race behavior", f["expected_boundary_items"])
        self._assert_rules_covered(f)

    # --- New: Medium-priority gap — scorecard tier weighting ---

    def test_013_scorecard_tier_validation(self):
        f = _load_fixture("013_scorecard_tier_validation.json")
        self.assertTrue(f["expect_test_generation"])
        self.assertEqual(f["expected_mode"], "Standard")
        self._assert_rules_covered(f)

    # --- New: Strict mode — property-based test required ---

    def test_014_strict_property_required(self):
        f = _load_fixture("014_strict_property_required.json")
        self.assertTrue(f["expect_test_generation"])
        self.assertEqual(f["expected_mode"], "Strict")
        self.assertIn("property-based testing", f["expected_techniques"])
        self._assert_rules_covered(f)

    # --- New: Strict mode — complex state machine ---

    def test_015_strict_state_machine(self):
        f = _load_fixture("015_strict_state_machine.json")
        self.assertTrue(f["expect_test_generation"])
        self.assertEqual(f["expected_mode"], "Strict")
        self.assertIn("context cancellation/deadline propagation", f["expected_boundary_items"])
        self._assert_rules_covered(f)

    # --- Aggregate tests ---

    def test_all_fixtures_loaded(self):
        fixtures = sorted(GOLDEN_DIR.glob("*.json"))
        self.assertGreaterEqual(
            len(fixtures), 15, "Expected at least 15 golden fixtures"
        )

    def test_all_fixture_rules_covered(self):
        for fixture_path in sorted(GOLDEN_DIR.glob("*.json")):
            fixture = json.loads(fixture_path.read_text())
            with self.subTest(fixture=fixture["id"]):
                self._assert_rules_covered(fixture)


if __name__ == "__main__":
    unittest.main()

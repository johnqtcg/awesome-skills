import json
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
TDD_REF = SKILL_DIR / "references" / "tdd-workflow.md"
API_REF = SKILL_DIR / "references" / "api-3layer-template.md"
BOUNDARY_REF = SKILL_DIR / "references" / "boundary-checklist.md"
GOLDEN_DIR = SKILL_DIR / "scripts" / "tests" / "golden"

ALL_CONTENT = ""
for p in [SKILL_MD, TDD_REF, API_REF, BOUNDARY_REF]:
    if p.exists():
        ALL_CONTENT += p.read_text() + "\n"


def load_fixture(name: str) -> dict:
    return json.loads((GOLDEN_DIR / name).read_text())


class TestGolden001_SBugfixOffByOne(unittest.TestCase):
    def setUp(self):
        self.f = load_fixture("001_s_bugfix_off_by_one.json")

    def test_change_size_s(self):
        self.assertEqual(self.f["change_size"], "S")

    def test_skill_rules_fire(self):
        for rule in self.f["skill_rules_that_must_fire"]:
            self.assertIn(
                rule.lower().split()[0],
                ALL_CONTENT.lower(),
                f"Rule concept '{rule}' not found in skill content",
            )

    def test_killer_hypothesis_present(self):
        hyp = self.f["expected_killer_hypothesis"].lower()
        self.assertTrue(
            "off-by-one" in hyp or "dropped" in hyp or "last item" in hyp,
            f"Killer hypothesis should describe the off-by-one defect, got: {hyp}",
        )

    def test_boundary_items(self):
        self.assertGreaterEqual(len(self.f["expected_boundary_items"]), 3)


class TestGolden002_SBugfixErrorSwallowed(unittest.TestCase):
    def setUp(self):
        self.f = load_fixture("002_s_bugfix_error_swallowed.json")

    def test_change_size_s(self):
        self.assertEqual(self.f["change_size"], "S")

    def test_error_propagation_rules(self):
        for rule in self.f["skill_rules_that_must_fire"]:
            self.assertIn(
                rule.lower().split()[0],
                ALL_CONTENT.lower(),
                f"Rule concept '{rule}' not found in skill content",
            )

    def test_killer_hypothesis(self):
        self.assertIn("nil error", self.f["expected_killer_hypothesis"].lower())


class TestGolden003_MFeatureNewEndpoint(unittest.TestCase):
    def setUp(self):
        self.f = load_fixture("003_m_feature_new_endpoint.json")

    def test_change_size_m(self):
        self.assertEqual(self.f["change_size"], "M")

    def test_api_3_layer(self):
        self.assertIn("API 3-Layer", self.f["skill_rules_that_must_fire"])
        self.assertIn("handler", self.f["expected_layers"])
        self.assertIn("service", self.f["expected_layers"])

    def test_handler_scenarios(self):
        self.assertGreaterEqual(len(self.f["expected_handler_scenarios"]), 3)

    def test_skill_rules_fire(self):
        for rule in self.f["skill_rules_that_must_fire"]:
            found = rule.lower().split()[0] in ALL_CONTENT.lower()
            self.assertTrue(found, f"Rule concept '{rule}' not found in skill content")

    def test_service_scenarios(self):
        self.assertGreaterEqual(len(self.f["expected_service_scenarios"]), 3)


class TestGolden004_MFeatureBusinessRule(unittest.TestCase):
    def setUp(self):
        self.f = load_fixture("004_m_feature_business_rule.json")

    def test_boundary_items_at_tier_edges(self):
        self.assertGreaterEqual(len(self.f["expected_boundary_items"]), 8)
        amounts = [b for b in self.f["expected_boundary_items"] if "amount" in b.lower()]
        self.assertGreaterEqual(len(amounts), 5, "Should have 5+ amount boundary values")

    def test_table_driven_expected(self):
        self.assertIn("Table-driven", self.f["skill_rules_that_must_fire"])

    def test_inside_out_approach(self):
        self.assertIn("Inside-Out", self.f["skill_rules_that_must_fire"])


class TestGolden005_LFeatureTransferFunds(unittest.TestCase):
    def setUp(self):
        self.f = load_fixture("005_l_feature_transfer_funds.json")

    def test_change_size_l(self):
        self.assertEqual(self.f["change_size"], "L")

    def test_concurrency_test_expected(self):
        self.assertTrue(self.f["expected_concurrency_test"])

    def test_test_count_range(self):
        self.assertEqual(self.f["expected_test_count_range"], [10, 20])

    def test_all_critical_scorecard_pass(self):
        for c in ["C1", "C2", "C3"]:
            self.assertIn(c, self.f["scorecard_must_pass"])

    def test_skill_rules_fire(self):
        for rule in self.f["skill_rules_that_must_fire"]:
            found = rule.lower().split()[0] in ALL_CONTENT.lower()
            self.assertTrue(found, f"Rule concept '{rule}' not found in skill content")


class TestGolden006_RefactorExtractMethod(unittest.TestCase):
    def setUp(self):
        self.f = load_fixture("006_refactor_extract_method.json")

    def test_change_type_refactor(self):
        self.assertEqual(self.f["change_type"], "refactor")

    def test_refactor_rules(self):
        rules = self.f["expected_refactor_rules"]
        self.assertGreaterEqual(len(rules), 3)
        combined = " ".join(rules).lower()
        self.assertIn("without modification", combined)
        self.assertIn("no observable behavior change", combined)

    def test_characterization_required(self):
        self.assertIn("Characterization", self.f["skill_rules_that_must_fire"])


class TestGolden007_LegacyCharacterization(unittest.TestCase):
    def setUp(self):
        self.f = load_fixture("007_legacy_code_characterization.json")

    def test_characterization_tests_expected(self):
        self.assertTrue(self.f["expected_characterization_tests"])

    def test_legacy_rules_fire(self):
        self.assertIn("Legacy code", self.f["skill_rules_that_must_fire"])
        self.assertIn("Characterization test", self.f["skill_rules_that_must_fire"])

    def test_killer_hypothesis(self):
        self.assertIn("tax", self.f["expected_killer_hypothesis"].lower())

    def test_existing_behavior_pinned(self):
        self.assertIn("existing behavior pinned", self.f["expected_boundary_items"])


class TestGolden008_ConcurrencySafety(unittest.TestCase):
    def setUp(self):
        self.f = load_fixture("008_concurrency_safety.json")

    def test_race_flag_required(self):
        self.assertTrue(self.f["expected_race_flag"])

    def test_concurrency_test_expected(self):
        self.assertTrue(self.f["expected_concurrency_test"])

    def test_concurrency_determinism_rule(self):
        self.assertIn("Concurrency Determinism", self.f["skill_rules_that_must_fire"])

    def test_race_detection_rule(self):
        self.assertIn("go test -race", self.f["skill_rules_that_must_fire"])

    def test_boundary_includes_concurrent(self):
        concurrent_items = [b for b in self.f["expected_boundary_items"] if "concurrent" in b.lower()]
        self.assertGreaterEqual(len(concurrent_items), 1)


if __name__ == "__main__":
    unittest.main()

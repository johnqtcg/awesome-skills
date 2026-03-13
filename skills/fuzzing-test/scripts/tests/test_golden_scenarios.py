import json
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
GOLDEN_DIR = SKILL_DIR / "scripts" / "tests" / "golden"
APP_REF = SKILL_DIR / "references" / "applicability-checklist.md"
TARGET_REF = SKILL_DIR / "references" / "target-priority.md"

ALL_REFS = [
    SKILL_MD,
    APP_REF,
    TARGET_REF,
    SKILL_DIR / "references" / "crash-handling.md",
    SKILL_DIR / "references" / "ci-strategy.md",
]


def load_fixture(name: str) -> dict:
    path = GOLDEN_DIR / name
    return json.loads(path.read_text())


def combined_text() -> str:
    return "\n".join(f.read_text() for f in ALL_REFS if f.exists())


class GoldenFixtureIntegrityTests(unittest.TestCase):
    def test_golden_directory_exists(self) -> None:
        self.assertTrue(GOLDEN_DIR.exists(), "golden directory missing")

    def test_expected_fixture_count(self) -> None:
        fixtures = list(GOLDEN_DIR.glob("*.json"))
        self.assertGreaterEqual(len(fixtures), 8, f"expected >=8 fixtures, got {len(fixtures)}")

    def test_all_fixtures_have_required_fields(self) -> None:
        required = {"id", "description", "code_snippet", "applicability_verdict", "skill_rules_that_must_fire"}
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            data = json.loads(path.read_text())
            missing = required - set(data.keys())
            self.assertFalse(missing, f"{path.name} missing fields: {missing}")

    def test_suitable_fixtures_have_template(self) -> None:
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            data = json.loads(path.read_text())
            if data["applicability_verdict"] == "suitable":
                self.assertIn("expected_template", data, f"{path.name} suitable but missing expected_template")
                self.assertIn("expected_fuzz_mode", data, f"{path.name} suitable but missing expected_fuzz_mode")

    def test_not_suitable_fixtures_have_alternative(self) -> None:
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            data = json.loads(path.read_text())
            if data["applicability_verdict"] == "not_suitable":
                self.assertIn("expected_alternative", data, f"{path.name} not_suitable but missing expected_alternative")
                self.assertIn("failed_hard_stop", data, f"{path.name} not_suitable but missing failed_hard_stop")


class GoldenSuitableParserTests(unittest.TestCase):
    def test_001_parser_rules_coverage(self) -> None:
        data = load_fixture("001_parser_suitable.json")
        text = combined_text()
        for rule in data["skill_rules_that_must_fire"]:
            self.assertIn(rule, text, f"rule missing in skill text: {rule}")

    def test_001_template_a_referenced(self) -> None:
        data = load_fixture("001_parser_suitable.json")
        self.assertEqual(data["expected_template"], "Template A")
        self.assertIn("Template A: Parser", SKILL_MD.read_text())


class GoldenSuitableRoundtripTests(unittest.TestCase):
    def test_002_roundtrip_rules_coverage(self) -> None:
        data = load_fixture("002_roundtrip_suitable.json")
        text = combined_text()
        for rule in data["skill_rules_that_must_fire"]:
            self.assertIn(rule, text, f"rule missing in skill text: {rule}")

    def test_002_template_b_referenced(self) -> None:
        data = load_fixture("002_roundtrip_suitable.json")
        self.assertEqual(data["expected_template"], "Template B")
        self.assertIn("Template B: Round-Trip", SKILL_MD.read_text())


class GoldenSuitableDifferentialTests(unittest.TestCase):
    def test_003_differential_rules_coverage(self) -> None:
        data = load_fixture("003_differential_suitable.json")
        text = combined_text()
        for rule in data["skill_rules_that_must_fire"]:
            self.assertIn(rule, text, f"rule missing in skill text: {rule}")

    def test_003_template_c_referenced(self) -> None:
        data = load_fixture("003_differential_suitable.json")
        self.assertEqual(data["expected_template"], "Template C")


class GoldenSuitableStructAwareTests(unittest.TestCase):
    def test_004_struct_aware_rules_coverage(self) -> None:
        data = load_fixture("004_struct_aware_suitable.json")
        text = combined_text()
        for rule in data["skill_rules_that_must_fire"]:
            self.assertIn(rule, text, f"rule missing in skill text: {rule}")

    def test_004_template_d_referenced(self) -> None:
        data = load_fixture("004_struct_aware_suitable.json")
        self.assertEqual(data["expected_template"], "Template D")


class GoldenNotSuitableTrivialTests(unittest.TestCase):
    def test_005_trivial_hard_stop(self) -> None:
        data = load_fixture("005_trivial_not_suitable.json")
        self.assertEqual(data["applicability_verdict"], "not_suitable")
        self.assertEqual(data["failed_hard_stop"], "1")

    def test_005_alternative_suggested(self) -> None:
        data = load_fixture("005_trivial_not_suitable.json")
        self.assertIn("unit tests", data["expected_alternative"])


class GoldenNotSuitableNoOracleTests(unittest.TestCase):
    def test_006_no_oracle_hard_stop(self) -> None:
        data = load_fixture("006_no_oracle_not_suitable.json")
        self.assertEqual(data["applicability_verdict"], "not_suitable")
        self.assertEqual(data["failed_hard_stop"], "3")

    def test_006_rules_coverage(self) -> None:
        data = load_fixture("006_no_oracle_not_suitable.json")
        text = combined_text()
        for rule in data["skill_rules_that_must_fire"]:
            self.assertIn(rule, text, f"rule missing: {rule}")


class GoldenNotSuitableDbTests(unittest.TestCase):
    def test_007_db_dependent_hard_stop(self) -> None:
        data = load_fixture("007_db_dependent_not_suitable.json")
        self.assertEqual(data["applicability_verdict"], "not_suitable")
        self.assertEqual(data["failed_hard_stop"], "2")

    def test_007_rules_coverage(self) -> None:
        data = load_fixture("007_db_dependent_not_suitable.json")
        text = combined_text()
        for rule in data["skill_rules_that_must_fire"]:
            self.assertIn(rule, text, f"rule missing: {rule}")


class GoldenValidatorRaceTests(unittest.TestCase):
    def test_008_race_features(self) -> None:
        data = load_fixture("008_validator_with_race.json")
        self.assertEqual(data["applicability_verdict"], "suitable")
        self.assertIn("race detection", data.get("advanced_features", []))

    def test_008_rules_coverage(self) -> None:
        data = load_fixture("008_validator_with_race.json")
        text = combined_text()
        for rule in data["skill_rules_that_must_fire"]:
            self.assertIn(rule, text, f"rule missing: {rule}")


if __name__ == "__main__":
    unittest.main()

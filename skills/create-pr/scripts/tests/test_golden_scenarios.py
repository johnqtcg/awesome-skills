import json
import re
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
REF_DIR = SKILL_DIR / "references"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"

REQUIRED_FIELDS = {
    "id",
    "description",
    "scenario_type",
    "expected_confidence",
    "expected_pr_mode",
    "skill_rules_that_must_fire",
    "reference_files",
}


def normalize(text: str) -> str:
    text = text.lower()
    text = text.replace("→", " ")
    text = text.replace("–", " ")
    text = text.replace("—", " ")
    text = re.sub(r"[^\w\s]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def combined_text() -> str:
    texts = [SKILL_MD.read_text()]
    texts.extend(path.read_text() for path in sorted(REF_DIR.glob("*.md")))
    return normalize("\n".join(texts))


def load_fixture(name: str) -> dict:
    return json.loads((GOLDEN_DIR / name).read_text())


class GoldenFixtureIntegrityTests(unittest.TestCase):
    def test_golden_directory_exists(self) -> None:
        self.assertTrue(GOLDEN_DIR.exists())

    def test_expected_fixture_count(self) -> None:
        fixtures = list(GOLDEN_DIR.glob("*.json"))
        self.assertGreaterEqual(len(fixtures), 9, f"expected >=9 fixtures, got {len(fixtures)}")

    def test_required_fields(self) -> None:
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            data = json.loads(path.read_text())
            missing = REQUIRED_FIELDS - set(data.keys())
            self.assertFalse(missing, f"{path.name} missing fields: {missing}")

    def test_unique_ids(self) -> None:
        ids = [json.loads(path.read_text())["id"] for path in sorted(GOLDEN_DIR.glob("*.json"))]
        self.assertEqual(len(ids), len(set(ids)), "duplicate fixture ids")

    def test_reference_files_exist(self) -> None:
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            data = json.loads(path.read_text())
            for ref in data["reference_files"]:
                self.assertTrue((SKILL_DIR / ref).exists(), f"{path.name}: missing reference {ref}")

    def test_scenario_types_cover_core_pr_decision_paths(self) -> None:
        types = {json.loads(path.read_text())["scenario_type"] for path in sorted(GOLDEN_DIR.glob("*.json"))}
        expected = {
            "ready_flow",
            "protection_suppression",
            "sync_blocker",
            "high_risk",
            "oversized",
            "quality_gap",
            "existing_pr_update",
            "merge_strategy",
            "secret_blocker",
        }
        self.assertTrue(expected.issubset(types), f"missing scenario types: {expected - types}")


class GoldenScenarioRuleCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.all_text = combined_text()

    def assertRulesCovered(self, fixture: dict) -> None:
        for rule in fixture["skill_rules_that_must_fire"]:
            self.assertIn(normalize(rule), self.all_text, f"{fixture['id']}: missing rule {rule}")

    def test_001_ready_small_change(self) -> None:
        f = load_fixture("001_ready_small_change.json")
        self.assertEqual("confirmed", f["expected_confidence"])
        self.assertEqual("ready", f["expected_pr_mode"])
        self.assertRulesCovered(f)

    def test_002_branch_protection_suppressed(self) -> None:
        f = load_fixture("002_branch_protection_suppressed.json")
        self.assertEqual("likely", f["expected_confidence"])
        self.assertEqual("ready", f["expected_pr_mode"])
        self.assertRulesCovered(f)

    def test_003_behind_main_blocker(self) -> None:
        f = load_fixture("003_behind_main_blocker.json")
        self.assertEqual("suspected", f["expected_confidence"])
        self.assertEqual("draft", f["expected_pr_mode"])
        self.assertRulesCovered(f)

    def test_004_high_risk_auth_change(self) -> None:
        f = load_fixture("004_high_risk_auth_change.json")
        self.assertEqual("high_risk", f["scenario_type"])
        self.assertRulesCovered(f)

    def test_005_oversized_pr_warning(self) -> None:
        f = load_fixture("005_oversized_pr_warning.json")
        self.assertEqual("oversized", f["scenario_type"])
        self.assertRulesCovered(f)

    def test_006_quality_gap_keeps_draft(self) -> None:
        f = load_fixture("006_quality_gap_keeps_draft.json")
        self.assertEqual("likely", f["expected_confidence"])
        self.assertEqual("draft", f["expected_pr_mode"])
        self.assertRulesCovered(f)

    def test_007_existing_pr_update(self) -> None:
        f = load_fixture("007_existing_pr_update.json")
        self.assertEqual("existing_pr_update", f["scenario_type"])
        self.assertRulesCovered(f)

    def test_008_squash_merge_title_priority(self) -> None:
        f = load_fixture("008_squash_merge_title_priority.json")
        self.assertEqual("merge_strategy", f["scenario_type"])
        self.assertRulesCovered(f)

    def test_009_secret_leak_blocker(self) -> None:
        f = load_fixture("009_secret_leak_blocker.json")
        self.assertEqual("secret_blocker", f["scenario_type"])
        self.assertEqual("draft", f["expected_pr_mode"])
        self.assertRulesCovered(f)

    def test_all_fixture_rules_are_covered(self) -> None:
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            with self.subTest(path=path.name):
                self.assertRulesCovered(json.loads(path.read_text()))


if __name__ == "__main__":
    unittest.main()

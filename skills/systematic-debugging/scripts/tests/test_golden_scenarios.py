import json
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
REFS_DIR = SKILL_DIR / "references"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"

ALL_CONTENT = SKILL_MD.read_text() + "\n"
for path in REFS_DIR.glob("*.md"):
    ALL_CONTENT += path.read_text() + "\n"


def load_fixture(name: str) -> dict:
    return json.loads((GOLDEN_DIR / name).read_text())


class TestGoldenFixtureStructure(unittest.TestCase):
    def test_fixture_count(self) -> None:
        count = len(list(GOLDEN_DIR.glob("*.json")))
        self.assertGreaterEqual(count, 11, f"need >= 11 golden fixtures, found {count}")

    def test_required_fields(self) -> None:
        required = {
            "id",
            "title",
            "scenario_type",
            "severity",
            "bug_type",
            "skill_rules_that_must_fire",
            "expected_references",
            "expected_output_fields",
        }
        for path in GOLDEN_DIR.glob("*.json"):
            data = json.loads(path.read_text())
            missing = required - set(data.keys())
            self.assertFalse(missing, f"{path.name} missing fields: {missing}")


class GoldenScenarioMixin:
    fixture_name = ""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = load_fixture(cls.fixture_name)

    def test_rules_are_covered(self) -> None:
        for rule in self.fixture["skill_rules_that_must_fire"]:
            self.assertIn(rule, ALL_CONTENT, f"{self.fixture['id']} missing rule: {rule}")

    def test_references_exist(self) -> None:
        for ref in self.fixture["expected_references"]:
            self.assertTrue((REFS_DIR / ref).exists(), f"{self.fixture['id']} missing ref: {ref}")

    def test_output_fields_exist(self) -> None:
        for field in self.fixture["expected_output_fields"]:
            self.assertIn(field, ALL_CONTENT, f"{self.fixture['id']} missing output field: {field}")


class TestGolden001FlakyRace(GoldenScenarioMixin, unittest.TestCase):
    fixture_name = "001_flaky_race_async_cache.json"


class TestGolden002DeepStackTrace(GoldenScenarioMixin, unittest.TestCase):
    fixture_name = "002_root_cause_trace_deep_stack.json"


class TestGolden003PerfProfileFirst(GoldenScenarioMixin, unittest.TestCase):
    fixture_name = "003_perf_regression_profile_first.json"


class TestGolden004BoundaryPropagation(GoldenScenarioMixin, unittest.TestCase):
    fixture_name = "004_multi_component_config_propagation.json"


class TestGolden005DependencyBreak(GoldenScenarioMixin, unittest.TestCase):
    fixture_name = "005_dependency_break_no_code_change.json"


class TestGolden006BuildFailure(GoldenScenarioMixin, unittest.TestCase):
    fixture_name = "006_build_failure_generated_code.json"


class TestGolden007P0Mitigation(GoldenScenarioMixin, unittest.TestCase):
    fixture_name = "007_p0_mitigate_then_investigate.json"

    def test_p0_specific_rules(self) -> None:
        self.assertEqual("P0", self.fixture["severity"])
        self.assertIn("P0 Protocol", ALL_CONTENT)


class TestGolden008ArchitectureQuestion(GoldenScenarioMixin, unittest.TestCase):
    fixture_name = "008_three_failed_fixes_question_architecture.json"

    def test_architecture_escalation_rule_exists(self) -> None:
        self.assertIn("If 3+ Fixes Failed: Question Architecture", ALL_CONTENT)


class TestGolden009BlockedIncident(GoldenScenarioMixin, unittest.TestCase):
    fixture_name = "009_p0_blocked_no_repro_honest_report.json"

    def test_blocked_status_fields_exist(self) -> None:
        self.assertIn("Investigation status", ALL_CONTENT)
        self.assertIn("Not run in this environment", ALL_CONTENT)


class TestGolden010GoroutineLeak(GoldenScenarioMixin, unittest.TestCase):
    fixture_name = "010_goroutine_leak_masked_as_latency.json"

    def test_profile_and_goroutine_keywords_exist(self) -> None:
        self.assertIn("pprof", ALL_CONTENT)
        self.assertIn("goroutine", ALL_CONTENT.lower())


class TestGolden011TimezoneDrift(GoldenScenarioMixin, unittest.TestCase):
    fixture_name = "011_timezone_locale_environment_drift.json"

    def test_environment_comparison_keywords_exist(self) -> None:
        self.assertIn("works on my machine", ALL_CONTENT)
        self.assertIn("Working vs broken comparison", ALL_CONTENT)


if __name__ == "__main__":
    unittest.main()

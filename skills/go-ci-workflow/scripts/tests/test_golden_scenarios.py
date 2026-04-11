import json
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
REF_DIR = SKILL_DIR / "references"
GOLDEN_DIR = SKILL_DIR / "scripts" / "tests" / "golden"

ALL_REFS = list(REF_DIR.glob("*.md"))


def load_fixture(name: str) -> dict:
    return json.loads((GOLDEN_DIR / name).read_text())


def combined_text() -> str:
    texts = [SKILL_MD.read_text()]
    texts.extend(f.read_text() for f in sorted(ALL_REFS) if f.exists())
    return "\n".join(texts)


class GoldenFixtureIntegrityTests(unittest.TestCase):
    def test_golden_directory_exists(self) -> None:
        self.assertTrue(GOLDEN_DIR.exists())

    def test_expected_fixture_count(self) -> None:
        fixtures = list(GOLDEN_DIR.glob("*.json"))
        self.assertGreaterEqual(len(fixtures), 8, f"expected >=8 fixtures, got {len(fixtures)}")

    def test_all_fixtures_have_required_fields(self) -> None:
        required = {"id", "description", "scenario_type", "expected_gates", "skill_rules_that_must_fire"}
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            data = json.loads(path.read_text())
            missing = required - set(data.keys())
            self.assertFalse(missing, f"{path.name} missing fields: {missing}")

    def test_scenario_types_cover_all_shapes(self) -> None:
        types = set()
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            data = json.loads(path.read_text())
            types.add(data["scenario_type"])
        expected = {
            "single_module_service",
            "single_module_library",
            "multi_module",
            "monorepo",
            "docker_heavy",
            "no_makefile",
            "fork_pr_security",
            "service_containers",
        }
        self.assertTrue(expected.issubset(types), f"missing scenario types: {expected - types}")


class GoldenSingleModuleServiceTests(unittest.TestCase):
    def test_001_rules_coverage(self) -> None:
        data = load_fixture("001_single_module_service.json")
        text = combined_text()
        for rule in data["skill_rules_that_must_fire"]:
            self.assertIn(rule, text, f"rule missing from skill text: {rule}")

    def test_001_expects_full_parity(self) -> None:
        data = load_fixture("001_single_module_service.json")
        self.assertEqual(data["expected_parity_level"], "full")
        self.assertIn("make target", list(data["expected_execution_paths"].values()))


class GoldenSingleModuleLibraryTests(unittest.TestCase):
    def test_002_rules_coverage(self) -> None:
        data = load_fixture("002_single_module_library.json")
        text = combined_text()
        for rule in data["skill_rules_that_must_fire"]:
            self.assertIn(rule, text, f"rule missing from skill text: {rule}")

    def test_002_expects_matrix(self) -> None:
        data = load_fixture("002_single_module_library.json")
        self.assertIn("matrix", data["skill_rules_that_must_fire"])


class GoldenMultiModuleTests(unittest.TestCase):
    def test_003_rules_coverage(self) -> None:
        data = load_fixture("003_multi_module_repo.json")
        text = combined_text()
        for rule in data["skill_rules_that_must_fire"]:
            self.assertIn(rule, text, f"rule missing from skill text: {rule}")

    def test_003_expects_multi_module_shape(self) -> None:
        data = load_fixture("003_multi_module_repo.json")
        self.assertEqual(data["expected_shape"], "multi-module repository")
        self.assertIn("Repository Shape Gate", data["expected_gates"])


class GoldenMonorepoTests(unittest.TestCase):
    def test_004_rules_coverage(self) -> None:
        data = load_fixture("004_monorepo_path_filters.json")
        text = combined_text()
        for rule in data["skill_rules_that_must_fire"]:
            self.assertIn(rule, text, f"rule missing from skill text: {rule}")

    def test_004_expects_path_filters(self) -> None:
        data = load_fixture("004_monorepo_path_filters.json")
        self.assertIn("path filter", data["skill_rules_that_must_fire"])


class GoldenDockerHeavyTests(unittest.TestCase):
    def test_005_rules_coverage(self) -> None:
        data = load_fixture("005_docker_heavy_repo.json")
        text = combined_text()
        for rule in data["skill_rules_that_must_fire"]:
            self.assertIn(rule, text, f"rule missing from skill text: {rule}")

    def test_005_expects_docker_heavy_shape_and_separate_jobs(self) -> None:
        data = load_fixture("005_docker_heavy_repo.json")
        self.assertEqual(data["expected_shape"], "Docker-heavy repository")
        self.assertIn("separate jobs", data["skill_rules_that_must_fire"])


class GoldenNoMakefileTests(unittest.TestCase):
    def test_006_rules_coverage(self) -> None:
        data = load_fixture("006_no_makefile_fallback.json")
        text = combined_text()
        for rule in data["skill_rules_that_must_fire"]:
            self.assertIn(rule, text, f"rule missing from skill text: {rule}")

    def test_006_expects_partial_parity(self) -> None:
        data = load_fixture("006_no_makefile_fallback.json")
        self.assertEqual(data["expected_parity_level"], "partial")
        self.assertIn("Degraded Output Gate", data["expected_gates"])


class GoldenForkPRSecurityTests(unittest.TestCase):
    def test_007_rules_coverage(self) -> None:
        data = load_fixture("007_fork_pr_security.json")
        text = combined_text()
        for rule in data["skill_rules_that_must_fire"]:
            self.assertIn(rule, text, f"rule missing from skill text: {rule}")

    def test_007_security_gate_required(self) -> None:
        data = load_fixture("007_fork_pr_security.json")
        self.assertIn("Security and Permissions Gate", data["expected_gates"])


class GoldenServiceContainerTests(unittest.TestCase):
    def test_008_rules_coverage(self) -> None:
        data = load_fixture("008_service_containers_integration.json")
        text = combined_text()
        for rule in data["skill_rules_that_must_fire"]:
            self.assertIn(rule, text, f"rule missing from skill text: {rule}")

    def test_008_expects_integration_job_and_service_containers(self) -> None:
        data = load_fixture("008_service_containers_integration.json")
        self.assertIn("api-integration", data["expected_jobs"])
        self.assertIn("service container", data["skill_rules_that_must_fire"])


class GoldenE2EJobTests(unittest.TestCase):
    def test_009_rules_coverage(self) -> None:
        data = load_fixture("009_e2e_job.json")
        text = combined_text()
        for rule in data["skill_rules_that_must_fire"]:
            self.assertIn(rule, text, f"rule missing from skill text: {rule}")

    def test_009_e2e_triggers_on_push_and_schedule_not_pr(self) -> None:
        data = load_fixture("009_e2e_job.json")
        self.assertIn("ci", data["expected_jobs"])
        self.assertIn("e2e", data["expected_jobs"])
        self.assertIn("schedule", data["skill_rules_that_must_fire"])
        self.assertIn("30 min", data["skill_rules_that_must_fire"])


class GoldenStaticAnalysisTests(unittest.TestCase):
    def test_010_rules_coverage(self) -> None:
        data = load_fixture("010_static_analysis_job.json")
        text = combined_text()
        for rule in data["skill_rules_that_must_fire"]:
            self.assertIn(rule, text, f"rule missing from skill text: {rule}")

    def test_010_expects_vulnerability_scanning_job(self) -> None:
        data = load_fixture("010_static_analysis_job.json")
        self.assertIn("govulncheck", data["expected_jobs"])
        self.assertIn("Vulnerability Scanning", data["skill_rules_that_must_fire"])
        self.assertIn("Static Analysis Extras", data["skill_rules_that_must_fire"])


class GoldenReusableWorkflowTests(unittest.TestCase):
    def test_011_rules_coverage(self) -> None:
        data = load_fixture("011_reusable_workflow.json")
        text = combined_text()
        for rule in data["skill_rules_that_must_fire"]:
            self.assertIn(rule, text, f"rule missing from skill text: {rule}")

    def test_011_expects_reusable_workflow_shape_and_workflow_call(self) -> None:
        data = load_fixture("011_reusable_workflow.json")
        self.assertEqual(data["expected_shape"], "reusable-workflow candidate")
        self.assertIn("workflow_call", data["skill_rules_that_must_fire"])
        self.assertIn("Composite Action", data["skill_rules_that_must_fire"])


class GoldenSelfHostedRunnerTests(unittest.TestCase):
    def test_012_rules_coverage(self) -> None:
        data = load_fixture("012_self_hosted_runner.json")
        text = combined_text()
        for rule in data["skill_rules_that_must_fire"]:
            self.assertIn(rule, text, f"rule missing from skill text: {rule}")

    def test_012_expects_security_gate_and_assumption_notes(self) -> None:
        data = load_fixture("012_self_hosted_runner.json")
        self.assertIn("Security and Permissions Gate", data["expected_gates"])
        self.assertIn("self-hosted", data["skill_rules_that_must_fire"])
        self.assertIn("Do not silently reuse GitHub-hosted assumptions", data["skill_rules_that_must_fire"])


if __name__ == "__main__":
    unittest.main()

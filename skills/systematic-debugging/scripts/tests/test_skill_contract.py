import re
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
REFS_DIR = SKILL_DIR / "references"
RUNNER = SKILL_DIR / "scripts" / "run_regression.sh"
COVERAGE = SKILL_DIR / "scripts" / "tests" / "COVERAGE.md"


def frontmatter(text: str) -> str:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError("missing yaml frontmatter")
    return match.group(1)


class TestFrontmatter(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL_MD.read_text()
        cls.fm = frontmatter(cls.skill).lower()

    def test_name_is_correct(self) -> None:
        self.assertIn("name: systematic-debugging", self.fm)

    def test_description_has_debugging_triggers(self) -> None:
        for keyword in [
            "debugging",
            "diagnosing",
            "root cause",
            "flaky",
            "race condition",
            "performance regression",
            "build failure",
        ]:
            self.assertIn(keyword, self.fm)

    def test_skill_md_stays_within_progressive_disclosure_limit(self) -> None:
        lines = self.skill.count("\n")
        self.assertLessEqual(lines, 500, f"SKILL.md too long: {lines} lines")


class TestMandatoryGates(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL_MD.read_text()

    def test_gate_section_exists(self) -> None:
        self.assertIn("## Mandatory Gates", self.skill)

    def test_all_five_gates_exist(self) -> None:
        for gate in [
            "Root Cause Gate",
            "Evidence Gate",
            "Hypothesis Discipline Gate",
            "Fix Attempt Gate",
            "Reporting Integrity Gate",
        ]:
            self.assertIn(gate, self.skill)


class TestQualityScorecard(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL_MD.read_text()

    def test_scorecard_section_exists(self) -> None:
        self.assertIn("## Quality Scorecard", self.skill)

    def test_scorecard_tiers_exist(self) -> None:
        for tier in ["### Critical", "### Standard", "### Hygiene"]:
            self.assertIn(tier, self.skill)

    def test_scorecard_ids_exist(self) -> None:
        for item in ["C1", "C2", "C3", "C4", "S1", "S2", "S3", "S4", "S5", "S6", "H1", "H2", "H3", "H4"]:
            self.assertIn(item, self.skill)

    def test_scorecard_output_json_exists(self) -> None:
        self.assertIn('"scorecard"', self.skill)
        self.assertIn('"overall": "PASS|FAIL"', self.skill)


class TestAntiExamples(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL_MD.read_text()
        cls.ref = (REFS_DIR / "bad-good-debugging-reports.md").read_text()

    def test_skill_anti_example_section_exists(self) -> None:
        self.assertIn("## Anti-Examples - BAD / GOOD Debugging Reports", self.skill)

    def test_skill_lists_all_anti_example_categories(self) -> None:
        for item in [
            "symptom presented as root cause",
            "guessed fix without reproduction",
            "sleep/retry used to hide a race",
            "performance fix without profiling",
            "missing boundary evidence",
            "bundled fixes destroying attribution",
            "repeated failed fixes without questioning architecture",
        ]:
            self.assertIn(item, self.skill.lower())

    def test_reference_has_seven_bad_good_pairs(self) -> None:
        self.assertGreaterEqual(self.ref.count("BAD:"), 7)
        self.assertGreaterEqual(self.ref.count("GOOD:"), 7)


class TestSelectiveLoading(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL_MD.read_text()

    def test_selective_loading_section_exists(self) -> None:
        self.assertIn("## Load References Selectively", self.skill)

    def test_all_reference_conditions_exist(self) -> None:
        for ref in [
            "root-cause-tracing.md",
            "defense-in-depth.md",
            "condition-based-waiting.md",
            "bug-type-strategies.md",
            "output-contract-template.md",
            "debugging-report-scorecard.md",
            "bad-good-debugging-reports.md",
        ]:
            self.assertIn(ref, self.skill)


class TestOutputContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL_MD.read_text()
        cls.contract = (REFS_DIR / "output-contract-template.md").read_text()

    def test_output_contract_section_exists(self) -> None:
        self.assertIn("## Output Contract (Required)", self.skill)

    def test_output_contract_has_nine_sections(self) -> None:
        for section in [
            "1. Triage",
            "2. Reproduction",
            "3. Evidence Collected",
            "4. Hypothesis Log",
            "5. Root Cause",
            "6. Fix Plan and Change",
            "7. Verification",
            "8. Residual Risk and Follow-ups",
            "9. Scorecard",
        ]:
            self.assertIn(section, self.contract)

    def test_output_contract_has_pass_fail_rules(self) -> None:
        self.assertIn("PASS/FAIL Rules", self.contract)
        self.assertIn("Critical tier has no FAIL", self.contract)


class TestReferenceFiles(unittest.TestCase):
    def test_reference_inventory_exists(self) -> None:
        expected = [
            "bad-good-debugging-reports.md",
            "bug-type-strategies.md",
            "condition-based-waiting.md",
            "debugging-report-scorecard.md",
            "defense-in-depth.md",
            "output-contract-template.md",
            "root-cause-tracing.md",
        ]
        for fname in expected:
            self.assertTrue((REFS_DIR / fname).exists(), f"missing reference: {fname}")

    def test_reference_total_depth_is_at_least_1000_lines(self) -> None:
        total = 0
        for path in REFS_DIR.glob("*.md"):
            total += path.read_text().count("\n")
        self.assertGreaterEqual(total, 1000, f"reference depth too shallow: {total}")

    def test_all_references_have_toc(self) -> None:
        for fname in [
            "bad-good-debugging-reports.md",
            "bug-type-strategies.md",
            "condition-based-waiting.md",
            "debugging-report-scorecard.md",
            "defense-in-depth.md",
            "output-contract-template.md",
            "root-cause-tracing.md",
        ]:
            text = (REFS_DIR / fname).read_text()
            self.assertIn("## Table of Contents", text)


class TestRegressionAssets(unittest.TestCase):
    def test_runner_exists(self) -> None:
        self.assertTrue(RUNNER.exists(), "run_regression.sh must exist")

    def test_runner_references_both_commands(self) -> None:
        text = RUNNER.read_text()
        self.assertIn("python3 -m unittest discover", text)
        self.assertIn("find-polluter.sh", text)

    def test_coverage_doc_exists(self) -> None:
        self.assertTrue(COVERAGE.exists(), "COVERAGE.md must exist")


if __name__ == "__main__":
    unittest.main()

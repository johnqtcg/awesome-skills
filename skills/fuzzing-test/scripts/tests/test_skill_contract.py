import re
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
APP_REF = SKILL_DIR / "references" / "applicability-checklist.md"
CI_REF = SKILL_DIR / "references" / "ci-strategy.md"
CRASH_REF = SKILL_DIR / "references" / "crash-handling.md"
TARGET_REF = SKILL_DIR / "references" / "target-priority.md"


def frontmatter(text: str) -> str:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError("missing yaml frontmatter")
    return match.group(1)


class FrontmatterTests(unittest.TestCase):
    def test_frontmatter_name(self) -> None:
        fm = frontmatter(SKILL_MD.read_text())
        self.assertIn("name: fuzzing-test", fm)

    def test_frontmatter_description_keywords(self) -> None:
        fm = frontmatter(SKILL_MD.read_text())
        self.assertIn("applicability gate first", fm)
        self.assertIn("Go 1.18+", fm)


class CoreGateTests(unittest.TestCase):
    def test_applicability_gate_exists(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Applicability Gate (Must Run First)", content)

    def test_target_priority_gate_exists(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Target Priority Gate", content)

    def test_risk_cost_gate_exists(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Risk and Cost Gate", content)

    def test_execution_integrity_gate_exists(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Execution Integrity Gate", content)

    def test_applicability_hard_stop_items(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Applicability Verdict: Not suitable for fuzzing", content)
        self.assertIn("suggest alternative strategy", content)

    def test_five_applicability_checks(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("meaningful input space", content)
        self.assertIn("fuzz-supported parameter types", content)
        self.assertIn("clear oracle/invariant", content)
        self.assertIn("deterministic/local", content)
        self.assertIn("fast enough for high-iteration", content)

    def test_cost_classes(self) -> None:
        content = SKILL_MD.read_text()
        for cls in ("Low", "Medium", "High"):
            self.assertIn(cls, content)


class TemplateTests(unittest.TestCase):
    def test_template_a_parser(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Template A: Parser", content)
        self.assertIn("FuzzParseXxx", content)

    def test_template_b_roundtrip(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Template B: Round-Trip", content)
        self.assertIn("FuzzRoundTripXxx", content)

    def test_template_c_differential(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Template C: Differential", content)
        self.assertIn("FuzzDiffXxx", content)

    def test_template_d_struct_aware(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Template D: Struct-Aware", content)
        self.assertIn("FuzzProcessRequest", content)

    def test_templates_have_f_add(self) -> None:
        content = SKILL_MD.read_text()
        self.assertGreaterEqual(content.count("f.Add("), 4)

    def test_templates_have_size_guard(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("len(data) >", content)


class AntiExampleTests(unittest.TestCase):
    def test_anti_examples_section_exists(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Anti-Examples (Common Fuzzing Mistakes)", content)

    def test_minimum_anti_example_count(self) -> None:
        content = SKILL_MD.read_text()
        count = len(re.findall(r"### Mistake \d+:", content))
        self.assertGreaterEqual(count, 7, f"expected >=7 anti-examples, got {count}")

    def test_anti_examples_have_bad_good_pairs(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("// BAD:", content)
        self.assertIn("// GOOD:", content)

    def test_key_anti_examples_present(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("trivial function", content.lower())
        self.assertIn("No oracle", content)
        self.assertIn("Skip rate", content)
        self.assertIn("OOM", content)
        self.assertIn("global/external state", content)


class ScorecardTests(unittest.TestCase):
    def test_scorecard_section_exists(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Quality Scorecard", content)

    def test_scorecard_critical_tier(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Critical (all must pass", content)
        self.assertIn("C1", content)
        self.assertIn("C2", content)
        self.assertIn("C3", content)

    def test_scorecard_standard_tier(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Standard (", content)
        for item in ("S1", "S2", "S3", "S4", "S5"):
            self.assertIn(item, content)

    def test_scorecard_hygiene_tier(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Hygiene (", content)
        for item in ("H1", "H2", "H3", "H4"):
            self.assertIn(item, content)

    def test_scorecard_pass_fail_rule(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Any Critical fails", content)
        self.assertIn("overall FAIL", content)


class GoVersionAndAdvancedTests(unittest.TestCase):
    def test_version_gate_section(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Go Version Gate", content)

    def test_version_table_entries(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("1.18", content)
        self.assertIn("1.20", content)
        self.assertIn("1.21", content)
        self.assertIn("1.22", content)

    def test_race_detection_fuzz(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Race Detection + Fuzz", content)
        self.assertIn("-race", content)

    def test_worker_parallelism(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Fuzz Worker Parallelism", content)
        self.assertIn("GOMAXPROCS", content)
        self.assertIn("-parallel", content)

    def test_go_fuzz_headers(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("go-fuzz-headers", content)
        self.assertIn("GenerateStruct", content)

    def test_performance_baseline(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Fuzz Performance Baseline", content)
        self.assertIn("execs/sec", content)


class FuzzVsPropertyTests(unittest.TestCase):
    def test_comparison_table(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Fuzz vs Property-Based Testing", content)
        self.assertIn("rapid", content)
        self.assertIn("gopter", content)

    def test_decision_rules(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Use fuzz", content)
        self.assertIn("Use property-based", content)
        self.assertIn("Use both", content)


class ReferenceDepthTests(unittest.TestCase):
    def test_applicability_has_concrete_examples(self) -> None:
        content = APP_REF.read_text()
        self.assertIn("Suitable for Fuzzing", content)
        self.assertIn("NOT Suitable for Fuzzing", content)
        self.assertIn("Borderline Cases", content)

    def test_applicability_has_go_code(self) -> None:
        content = APP_REF.read_text()
        self.assertIn("func ", content)
        self.assertGreaterEqual(content.count("// Check"), 5)

    def test_target_priority_has_go_examples(self) -> None:
        content = TARGET_REF.read_text()
        self.assertIn("Tier 1 Example:", content)
        self.assertIn("Tier 2 Example:", content)
        self.assertIn("De-Prioritize Example:", content)
        self.assertIn("func ", content)

    def test_target_priority_has_flowchart(self) -> None:
        content = TARGET_REF.read_text()
        self.assertIn("Quick Decision Flowchart", content)

    def test_ci_strategy_two_lanes(self) -> None:
        content = CI_REF.read_text()
        self.assertIn("PR Lane", content)
        self.assertIn("Scheduled Lane", content)

    def test_crash_handling_template(self) -> None:
        content = CRASH_REF.read_text()
        self.assertIn("Crash Report Template", content)
        self.assertIn("Post-Fix Checklist", content)


if __name__ == "__main__":
    unittest.main()

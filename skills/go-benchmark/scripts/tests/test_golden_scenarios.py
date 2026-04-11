"""Behavioral scenario tests for go-benchmark golden fixtures.

Each fixture defines a benchmark code snippet or run command and whether it
violates a Hard Rule, Standard item, or is a valid pattern. Tests verify:
1. The coverage_rules strings exist in SKILL.md + references (rule surface present)
2. The type/severity classification is explicit and correct
3. No defects in good-practice fixtures; specific violations in defect fixtures
"""

import json
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
REF_DIR = SKILL_DIR / "references"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"

REQUIRED_FIELDS = {"id", "title", "type", "severity", "benchmark_snippet",
                   "expected_feedback", "coverage_rules", "reference"}


def _load(filename: str) -> dict:
    return json.loads((GOLDEN_DIR / filename).read_text())


def _all_text() -> str:
    parts = [SKILL_MD.read_text()]
    for f in sorted(REF_DIR.glob("*.md")):
        parts.append(f.read_text())
    return "\n".join(parts)


# ------------------------------------------------------------------
# Fixture integrity
# ------------------------------------------------------------------

class TestFixtureIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixtures = [
            json.loads(p.read_text())
            for p in sorted(GOLDEN_DIR.glob("*.json"))
        ]

    def test_at_least_6_fixtures(self) -> None:
        self.assertGreaterEqual(len(self.fixtures), 6, "need at least 6 golden fixtures")

    def test_all_fixtures_have_required_fields(self) -> None:
        for fix in self.fixtures:
            missing = REQUIRED_FIELDS - set(fix.keys())
            self.assertFalse(missing, f"{fix['id']}: missing fields {missing}")

    def test_valid_types(self) -> None:
        for fix in self.fixtures:
            self.assertIn(fix["type"], ("defect", "good_practice"),
                          f"{fix['id']}: invalid type {fix['type']!r}")

    def test_valid_severities(self) -> None:
        for fix in self.fixtures:
            self.assertIn(fix["severity"],
                          ("critical", "standard", "hygiene", "none"),
                          f"{fix['id']}: invalid severity {fix['severity']!r}")

    def test_defect_fixtures_have_non_critical_or_critical_severity(self) -> None:
        for fix in self.fixtures:
            if fix["type"] == "defect":
                self.assertNotEqual(fix["severity"], "none",
                                    f"{fix['id']}: defect must have non-none severity")

    def test_good_practice_fixtures_have_none_severity(self) -> None:
        for fix in self.fixtures:
            if fix["type"] == "good_practice":
                self.assertEqual(fix["severity"], "none",
                                 f"{fix['id']}: good_practice must have severity=none")

    def test_unique_ids(self) -> None:
        ids = [f["id"] for f in self.fixtures]
        self.assertEqual(len(ids), len(set(ids)), f"duplicate fixture IDs: {ids}")

    def test_has_at_least_one_good_practice(self) -> None:
        good = [f for f in self.fixtures if f["type"] == "good_practice"]
        self.assertGreaterEqual(len(good), 2, "need ≥2 good_practice fixtures")

    def test_all_coverage_rules_present_in_docs(self) -> None:
        text = _all_text().lower()
        for fix in self.fixtures:
            for rule in fix["coverage_rules"]:
                self.assertIn(rule.lower(), text,
                              f"{fix['id']}: coverage rule missing: {rule!r}")


# ------------------------------------------------------------------
# Critical defect cases
# ------------------------------------------------------------------

class TestCriticalDefects(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.all_text = _all_text()

    def _assert_coverage(self, fix: dict) -> None:
        for rule in fix.get("coverage_rules", []):
            self.assertIn(rule.lower(), self.all_text.lower(),
                          f"[{fix['id']}] coverage rule missing: {rule!r}")

    def test_001_missing_sink_is_critical(self) -> None:
        f = _load("001_missing_sink.json")
        self.assertEqual(f["type"], "defect")
        self.assertEqual(f["severity"], "critical")
        self.assertIn("sink", f["violated_rule"].lower())
        self._assert_coverage(f)

    def test_002_setup_inside_loop_is_critical(self) -> None:
        f = _load("002_setup_inside_loop.json")
        self.assertEqual(f["type"], "defect")
        self.assertEqual(f["severity"], "critical")
        self.assertIn("timer", f["violated_rule"].lower())
        self._assert_coverage(f)

    def test_003_reset_timer_inside_loop_is_critical(self) -> None:
        f = _load("003_reset_timer_inside_loop.json")
        self.assertEqual(f["type"], "defect")
        self.assertEqual(f["severity"], "critical")
        self.assertIn("timer", f["violated_rule"].lower())
        self._assert_coverage(f)

    def test_008_missing_benchmem_is_critical(self) -> None:
        f = _load("008_missing_benchmem_flag.json")
        self.assertEqual(f["type"], "defect")
        self.assertEqual(f["severity"], "critical")
        self.assertIn("benchmem", f["violated_rule"].lower())
        self._assert_coverage(f)


# ------------------------------------------------------------------
# Standard defect cases
# ------------------------------------------------------------------

class TestStandardDefects(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.all_text = _all_text()

    def _assert_coverage(self, fix: dict) -> None:
        for rule in fix.get("coverage_rules", []):
            self.assertIn(rule.lower(), self.all_text.lower(),
                          f"[{fix['id']}] coverage rule missing: {rule!r}")

    def test_004_single_count_comparison_is_standard(self) -> None:
        f = _load("004_single_count_comparison.json")
        self.assertEqual(f["type"], "defect")
        self.assertEqual(f["severity"], "standard")
        self._assert_coverage(f)


# ------------------------------------------------------------------
# Good practice cases (valid benchmarks that must NOT be flagged)
# ------------------------------------------------------------------

class TestGoodPracticePatterns(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.all_text = _all_text()

    def _assert_coverage(self, fix: dict) -> None:
        for rule in fix.get("coverage_rules", []):
            self.assertIn(rule.lower(), self.all_text.lower(),
                          f"[{fix['id']}] coverage rule missing: {rule!r}")

    def test_005_sub_benchmark_sizes_is_good_practice(self) -> None:
        f = _load("005_good_sub_benchmark_sizes.json")
        self.assertEqual(f["type"], "good_practice")
        self.assertEqual(f["severity"], "none")
        self.assertIn("no violations", f["expected_feedback"])
        self._assert_coverage(f)

    def test_006_parallel_benchmark_is_good_practice(self) -> None:
        f = _load("006_good_parallel_benchmark.json")
        self.assertEqual(f["type"], "good_practice")
        self.assertEqual(f["severity"], "none")
        self.assertIn("no violations", f["expected_feedback"])
        self._assert_coverage(f)

    def test_007_throughput_benchmark_is_good_practice(self) -> None:
        f = _load("007_good_throughput_benchmark.json")
        self.assertEqual(f["type"], "good_practice")
        self.assertEqual(f["severity"], "none")
        self.assertIn("no violations", f["expected_feedback"])
        self._assert_coverage(f)


if __name__ == "__main__":
    unittest.main()
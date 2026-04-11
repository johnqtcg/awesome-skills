"""Behavioral scenario tests for go-benchmark golden fixtures.

Each fixture gets its own test class (per-fixture pattern) for precise failure
diagnosis. Tests verify: type/severity classification, violated_rule semantics,
and that all coverage_rules strings exist in SKILL.md + references.
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

VALID_TYPES = frozenset({"defect", "good_practice", "degradation_scenario", "workflow"})
VALID_SEVERITIES = frozenset({"critical", "standard", "hygiene", "none"})


def _load(filename: str) -> dict:
    return json.loads((GOLDEN_DIR / filename).read_text())


def _all_text() -> str:
    parts = [SKILL_MD.read_text()]
    for f in sorted(REF_DIR.glob("*.md")):
        parts.append(f.read_text())
    return "\n".join(parts).lower()


# ------------------------------------------------------------------
# Fixture integrity (meta tests — run on every fixture)
# ------------------------------------------------------------------

class TestFixtureIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixtures = [
            json.loads(p.read_text())
            for p in sorted(GOLDEN_DIR.glob("*.json"))
        ]

    def test_at_least_9_fixtures(self) -> None:
        self.assertGreaterEqual(len(self.fixtures), 9, "need at least 9 golden fixtures")

    def test_all_fixtures_have_required_fields(self) -> None:
        for fix in self.fixtures:
            missing = REQUIRED_FIELDS - set(fix.keys())
            self.assertFalse(missing, f"{fix['id']}: missing fields {missing}")

    def test_valid_types(self) -> None:
        for fix in self.fixtures:
            self.assertIn(fix["type"], VALID_TYPES,
                          f"{fix['id']}: invalid type {fix['type']!r}")

    def test_valid_severities(self) -> None:
        for fix in self.fixtures:
            self.assertIn(fix["severity"], VALID_SEVERITIES,
                          f"{fix['id']}: invalid severity {fix['severity']!r}")

    def test_defect_fixtures_have_non_none_severity(self) -> None:
        for fix in self.fixtures:
            if fix["type"] == "defect":
                self.assertNotEqual(fix["severity"], "none",
                                    f"{fix['id']}: defect must have non-none severity")

    def test_good_practice_and_workflow_have_none_severity(self) -> None:
        for fix in self.fixtures:
            if fix["type"] in ("good_practice", "degradation_scenario", "workflow"):
                self.assertEqual(fix["severity"], "none",
                                 f"{fix['id']}: {fix['type']} must have severity=none")

    def test_unique_ids(self) -> None:
        ids = [f["id"] for f in self.fixtures]
        self.assertEqual(len(ids), len(set(ids)), f"duplicate fixture IDs: {ids}")

    def test_all_coverage_rules_present_in_docs(self) -> None:
        text = _all_text()
        for fix in self.fixtures:
            for rule in fix["coverage_rules"]:
                self.assertIn(rule.lower(), text,
                              f"{fix['id']}: coverage rule missing: {rule!r}")


# ------------------------------------------------------------------
# Per-fixture test classes — defects (Critical)
# ------------------------------------------------------------------

class TestBench001MissingSink(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.f = _load("001_missing_sink.json")
        cls.text = _all_text()

    def test_001_is_critical_defect(self) -> None:
        self.assertEqual(self.f["type"], "defect")
        self.assertEqual(self.f["severity"], "critical")
        self.assertIn("sink", self.f["violated_rule"].lower())

    def test_001_coverage_rules(self) -> None:
        for rule in self.f["coverage_rules"]:
            self.assertIn(rule.lower(), self.text, f"rule missing: {rule!r}")


class TestBench002SetupInsideLoop(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.f = _load("002_setup_inside_loop.json")
        cls.text = _all_text()

    def test_002_is_critical_defect(self) -> None:
        self.assertEqual(self.f["type"], "defect")
        self.assertEqual(self.f["severity"], "critical")
        self.assertIn("timer", self.f["violated_rule"].lower())

    def test_002_coverage_rules(self) -> None:
        for rule in self.f["coverage_rules"]:
            self.assertIn(rule.lower(), self.text, f"rule missing: {rule!r}")


class TestBench003ResetTimerInsideLoop(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.f = _load("003_reset_timer_inside_loop.json")
        cls.text = _all_text()

    def test_003_is_critical_defect(self) -> None:
        self.assertEqual(self.f["type"], "defect")
        self.assertEqual(self.f["severity"], "critical")
        self.assertIn("timer", self.f["violated_rule"].lower())

    def test_003_coverage_rules(self) -> None:
        for rule in self.f["coverage_rules"]:
            self.assertIn(rule.lower(), self.text, f"rule missing: {rule!r}")


class TestBench008MissingBenchmem(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.f = _load("008_missing_benchmem_flag.json")
        cls.text = _all_text()

    def test_008_is_critical_defect(self) -> None:
        self.assertEqual(self.f["type"], "defect")
        self.assertEqual(self.f["severity"], "critical")
        self.assertIn("benchmem", self.f["violated_rule"].lower())

    def test_008_coverage_rules(self) -> None:
        for rule in self.f["coverage_rules"]:
            self.assertIn(rule.lower(), self.text, f"rule missing: {rule!r}")


# ------------------------------------------------------------------
# Per-fixture test classes — defects (Standard)
# ------------------------------------------------------------------

class TestBench004SingleCountComparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.f = _load("004_single_count_comparison.json")
        cls.text = _all_text()

    def test_004_is_standard_defect(self) -> None:
        self.assertEqual(self.f["type"], "defect")
        self.assertEqual(self.f["severity"], "standard")

    def test_004_coverage_rules(self) -> None:
        for rule in self.f["coverage_rules"]:
            self.assertIn(rule.lower(), self.text, f"rule missing: {rule!r}")


class TestBench011NoisyBenchstat(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.f = _load("011_noisy_benchstat.json")
        cls.text = _all_text()

    def test_011_is_standard_defect(self) -> None:
        self.assertEqual(self.f["type"], "defect")
        self.assertEqual(self.f["severity"], "standard")

    def test_011_coverage_rules(self) -> None:
        for rule in self.f["coverage_rules"]:
            self.assertIn(rule.lower(), self.text, f"rule missing: {rule!r}")


# ------------------------------------------------------------------
# Per-fixture test classes — good practice patterns
# ------------------------------------------------------------------

class TestBench005SubBenchmarkSizes(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.f = _load("005_good_sub_benchmark_sizes.json")
        cls.text = _all_text()

    def test_005_is_good_practice_no_violations(self) -> None:
        self.assertEqual(self.f["type"], "good_practice")
        self.assertEqual(self.f["severity"], "none")
        self.assertIn("no violations", self.f["expected_feedback"])

    def test_005_coverage_rules(self) -> None:
        for rule in self.f["coverage_rules"]:
            self.assertIn(rule.lower(), self.text, f"rule missing: {rule!r}")


class TestBench006ParallelBenchmark(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.f = _load("006_good_parallel_benchmark.json")
        cls.text = _all_text()

    def test_006_is_good_practice_no_violations(self) -> None:
        self.assertEqual(self.f["type"], "good_practice")
        self.assertEqual(self.f["severity"], "none")
        self.assertIn("no violations", self.f["expected_feedback"])

    def test_006_coverage_rules(self) -> None:
        for rule in self.f["coverage_rules"]:
            self.assertIn(rule.lower(), self.text, f"rule missing: {rule!r}")


class TestBench007ThroughputBenchmark(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.f = _load("007_good_throughput_benchmark.json")
        cls.text = _all_text()

    def test_007_is_good_practice_no_violations(self) -> None:
        self.assertEqual(self.f["type"], "good_practice")
        self.assertEqual(self.f["severity"], "none")
        self.assertIn("no violations", self.f["expected_feedback"])

    def test_007_coverage_rules(self) -> None:
        for rule in self.f["coverage_rules"]:
            self.assertIn(rule.lower(), self.text, f"rule missing: {rule!r}")


# ------------------------------------------------------------------
# Per-fixture test classes — degradation and workflow scenarios
# ------------------------------------------------------------------

class TestBench009DegradedNoData(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.f = _load("009_degraded_no_data.json")
        cls.text = _all_text()

    def test_009_is_degradation_scenario(self) -> None:
        self.assertEqual(self.f["type"], "degradation_scenario")
        self.assertEqual(self.f["severity"], "none")
        self.assertIn("fabricate", self.f["expected_feedback"].lower())

    def test_009_coverage_rules(self) -> None:
        for rule in self.f["coverage_rules"]:
            self.assertIn(rule.lower(), self.text, f"rule missing: {rule!r}")


class TestBench010PprofGuidedBenchmark(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.f = _load("010_pprof_guided_benchmark.json")
        cls.text = _all_text()

    def test_010_is_workflow_scenario(self) -> None:
        self.assertEqual(self.f["type"], "workflow")
        self.assertEqual(self.f["severity"], "none")

    def test_010_coverage_rules(self) -> None:
        for rule in self.f["coverage_rules"]:
            self.assertIn(rule.lower(), self.text, f"rule missing: {rule!r}")


if __name__ == "__main__":
    unittest.main()
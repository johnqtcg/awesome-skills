"""Behavioral regression tests using golden fixtures.

Each fixture defines a Go code scenario and whether the skill should produce
a finding or suppress it.  Tests verify that SKILL.md and its reference files
contain the rules needed to handle each case correctly.

This is NOT runtime LLM testing — it validates that the *rule coverage* in
the skill documents is sufficient to produce the expected behavior.
"""

import json
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
REFERENCES_DIR = SKILL_DIR / "references"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


class GoldenReviewTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.skill_text = SKILL_MD.read_text()
        cls.reference_texts: dict[str, str] = {}
        for ref_file in REFERENCES_DIR.glob("*.md"):
            cls.reference_texts[ref_file.name] = ref_file.read_text()
        cls.all_text = cls.skill_text + "\n".join(cls.reference_texts.values())

    def _load(self, filename: str) -> dict:
        with open(GOLDEN_DIR / filename) as f:
            return json.load(f)

    def _assert_coverage(self, fixture: dict) -> None:
        """Every coverage_rule string must appear in skill + references."""
        for rule in fixture.get("coverage_rules", []):
            self.assertIn(
                rule,
                self.all_text,
                f"[{fixture['id']}] coverage rule missing: {rule!r}",
            )

    def _assert_anti_example(self, fixture: dict) -> None:
        """Every anti_example_pattern string must appear in SKILL.md."""
        for pattern in fixture.get("anti_example_patterns", []):
            self.assertIn(
                pattern,
                self.skill_text,
                f"[{fixture['id']}] anti-example missing in SKILL.md: {pattern!r}",
            )

    def _assert_gate(self, fixture: dict) -> None:
        """If the fixture references a gate, it must exist in SKILL.md."""
        gate = fixture.get("gate")
        if gate:
            self.assertIn(
                gate,
                self.skill_text,
                f"[{fixture['id']}] gate missing in SKILL.md: {gate!r}",
            )

    # ------------------------------------------------------------------
    # True-positive cases (should produce a finding)
    # ------------------------------------------------------------------

    def test_001_race_shared_map(self) -> None:
        f = self._load("001_race_shared_map.json")
        self.assertTrue(f["expected_finding"])
        self._assert_coverage(f)

    def test_003_missing_resp_body_close(self) -> None:
        f = self._load("003_missing_resp_body_close.json")
        self.assertTrue(f["expected_finding"])
        self._assert_coverage(f)

    def test_006_ignored_critical_error(self) -> None:
        f = self._load("006_ignored_critical_error.json")
        self.assertTrue(f["expected_finding"])
        self._assert_coverage(f)

    def test_008_finding_merge(self) -> None:
        f = self._load("008_finding_merge.json")
        self.assertTrue(f["expected_finding"])
        self.assertTrue(f.get("expected_merge"))
        self._assert_coverage(f)

    # ------------------------------------------------------------------
    # False-positive cases (should NOT produce a finding)
    # ------------------------------------------------------------------

    def test_002_single_goroutine_map_fp(self) -> None:
        f = self._load("002_single_goroutine_map_fp.json")
        self.assertFalse(f["expected_finding"])
        self._assert_anti_example(f)

    def test_004_server_handler_body_fp(self) -> None:
        f = self._load("004_server_handler_body_fp.json")
        self.assertFalse(f["expected_finding"])
        self._assert_anti_example(f)

    def test_005_slog_version_gate_fp(self) -> None:
        f = self._load("005_slog_version_gate_fp.json")
        self.assertFalse(f["expected_finding"])
        self._assert_anti_example(f)
        self._assert_gate(f)

    def test_007_generated_code_exclusion(self) -> None:
        f = self._load("007_generated_code_exclusion.json")
        self.assertFalse(f["expected_finding"])
        self._assert_gate(f)
        self._assert_coverage(f)

    # ------------------------------------------------------------------
    # Security cases
    # ------------------------------------------------------------------

    def test_009_sql_injection_tp(self) -> None:
        f = self._load("009_sql_injection_tp.json")
        self.assertTrue(f["expected_finding"])
        self._assert_coverage(f)

    def test_010_hardcoded_secret_tp(self) -> None:
        f = self._load("010_hardcoded_secret_tp.json")
        self.assertTrue(f["expected_finding"])
        self._assert_coverage(f)

    # ------------------------------------------------------------------
    # Performance cases
    # ------------------------------------------------------------------

    def test_011_regexp_in_loop_tp(self) -> None:
        f = self._load("011_regexp_in_loop_tp.json")
        self.assertTrue(f["expected_finding"])
        self._assert_coverage(f)

    def test_012_small_slice_prealloc_fp(self) -> None:
        f = self._load("012_small_slice_prealloc_fp.json")
        self.assertFalse(f["expected_finding"])
        self._assert_anti_example(f)

    # ------------------------------------------------------------------
    # Change Origin Classification cases
    # ------------------------------------------------------------------

    def test_013_origin_introduced_tp(self) -> None:
        f = self._load("013_origin_introduced_tp.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f.get("origin"), "introduced")
        self._assert_coverage(f)
        self._assert_gate(f)

    def test_014_origin_preexisting_awareness(self) -> None:
        f = self._load("014_origin_preexisting_awareness.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f.get("origin"), "pre-existing")
        self._assert_coverage(f)
        self._assert_gate(f)

    # ------------------------------------------------------------------
    # Error handling false-positive
    # ------------------------------------------------------------------

    def test_015_defer_close_readonly_fp(self) -> None:
        f = self._load("015_defer_close_readonly_fp.json")
        self.assertFalse(f["expected_finding"])
        self._assert_anti_example(f)

    # ------------------------------------------------------------------
    # Test quality case
    # ------------------------------------------------------------------

    def test_016_test_no_assertion_tp(self) -> None:
        f = self._load("016_test_no_assertion_tp.json")
        self.assertTrue(f["expected_finding"])
        self._assert_coverage(f)

    # ------------------------------------------------------------------
    # Database case
    # ------------------------------------------------------------------

    def test_017_sql_rows_not_closed_tp(self) -> None:
        f = self._load("017_sql_rows_not_closed_tp.json")
        self.assertTrue(f["expected_finding"])
        self._assert_coverage(f)

    # ------------------------------------------------------------------
    # Code quality false-positive
    # ------------------------------------------------------------------

    def test_018_long_switch_function_fp(self) -> None:
        f = self._load("018_long_switch_function_fp.json")
        self.assertFalse(f["expected_finding"])
        self._assert_anti_example(f)

    # ------------------------------------------------------------------
    # Modern Go case
    # ------------------------------------------------------------------

    def test_019_errors_join_modern_tp(self) -> None:
        f = self._load("019_errors_join_modern_tp.json")
        self.assertTrue(f["expected_finding"])
        self._assert_coverage(f)

    # ------------------------------------------------------------------
    # Origin uncertain case
    # ------------------------------------------------------------------

    def test_020_origin_uncertain(self) -> None:
        f = self._load("020_origin_uncertain.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f.get("origin"), "uncertain")
        self._assert_coverage(f)
        self._assert_gate(f)

    # ------------------------------------------------------------------
    # Change Origin — complement: Medium pre-existing → Residual Risk
    # ------------------------------------------------------------------

    def test_021_preexisting_medium_residual_risk(self) -> None:
        f = self._load("021_preexisting_medium_residual_risk.json")
        self.assertFalse(f["expected_finding"])
        self.assertEqual(f.get("origin"), "pre-existing")
        self._assert_coverage(f)
        self._assert_gate(f)

    # ------------------------------------------------------------------
    # Volume-cap overflow
    # ------------------------------------------------------------------

    def test_022_volume_cap_overflow(self) -> None:
        f = self._load("022_volume_cap_overflow.json")
        self.assertTrue(f["expected_finding"])
        self._assert_coverage(f)

    # ------------------------------------------------------------------
    # PR review checklist meta-sections
    # ------------------------------------------------------------------

    def test_023_checklist_pr_review_coverage(self) -> None:
        f = self._load("023_checklist_pr_review.json")
        self.assertTrue(f["expected_finding"])
        self._assert_coverage(f)

    # ------------------------------------------------------------------
    # Fixture integrity
    # ------------------------------------------------------------------

    def test_all_fixtures_have_required_fields(self) -> None:
        required = {"id", "title", "expected_finding", "category", "code"}
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            with open(path) as fp:
                data = json.load(fp)
            missing = required - data.keys()
            self.assertFalse(
                missing,
                f"{path.name} missing required fields: {missing}",
            )

    def test_positive_fixtures_have_severity(self) -> None:
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            with open(path) as fp:
                data = json.load(fp)
            if data["expected_finding"]:
                self.assertIn(
                    "severity",
                    data,
                    f"{path.name}: positive fixture must specify severity",
                )


if __name__ == "__main__":
    unittest.main()

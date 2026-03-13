"""Behavioral regression tests using golden fixtures.

Each fixture defines a code scenario and whether the skill should produce
a finding or suppress it. Tests verify that SKILL.md and its reference files
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
        """Every anti_example_pattern must appear in skill (suppression rules)."""
        for pattern in fixture.get("anti_example_patterns", []):
            self.assertIn(
                pattern,
                self.all_text,
                f"[{fixture['id']}] anti-example missing: {pattern!r}",
            )

    def _assert_reference(self, fixture: dict) -> None:
        """Referenced file must exist."""
        ref = fixture.get("reference", "")
        if ref.startswith("references/"):
            filename = ref.split("/", 1)[1]
            self.assertIn(
                filename,
                self.reference_texts,
                f"[{fixture['id']}] reference file missing: {ref}",
            )

    # ------------------------------------------------------------------
    # True-positive cases (should produce a finding)
    # ------------------------------------------------------------------

    def test_001_idor_missing_authz(self) -> None:
        f = self._load("001_idor_missing_authz.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P1")
        self._assert_coverage(f)
        self._assert_reference(f)

    def test_003_hardcoded_secret(self) -> None:
        f = self._load("003_hardcoded_secret.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P1")
        self._assert_coverage(f)

    def test_005_sql_injection_concat(self) -> None:
        f = self._load("005_sql_injection_concat.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P1")
        self._assert_coverage(f)

    def test_007_toctou_balance_race(self) -> None:
        f = self._load("007_toctou_balance_race.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P1")
        self._assert_coverage(f)

    def test_008_resp_body_not_closed(self) -> None:
        f = self._load("008_resp_body_not_closed.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P2")
        self._assert_coverage(f)

    def test_009_jwt_alg_none(self) -> None:
        f = self._load("009_jwt_alg_none.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P1")
        self._assert_coverage(f)
        self._assert_reference(f)

    def test_010_path_traversal(self) -> None:
        f = self._load("010_path_traversal.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P1")
        self._assert_coverage(f)
        self._assert_reference(f)

    def test_011_dockerfile_root(self) -> None:
        f = self._load("011_dockerfile_root.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P2")
        self._assert_coverage(f)
        self._assert_reference(f)

    def test_012_concurrent_map_write(self) -> None:
        f = self._load("012_concurrent_map_write.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P1")
        self._assert_coverage(f)
        self._assert_reference(f)

    def test_013_maxbytesreader_missing(self) -> None:
        f = self._load("013_maxbytesreader_missing.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P2")
        self._assert_coverage(f)
        self._assert_reference(f)

    def test_014_text_template_xss(self) -> None:
        f = self._load("014_text_template_xss.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P1")
        self._assert_coverage(f)
        self._assert_reference(f)

    def test_015_open_redirect(self) -> None:
        f = self._load("015_open_redirect.json")
        self.assertTrue(f["expected_finding"])
        self.assertEqual(f["severity"], "P2")
        self._assert_coverage(f)
        self._assert_reference(f)

    # ------------------------------------------------------------------
    # False-positive cases (should NOT produce a finding)
    # ------------------------------------------------------------------

    def test_002_parameterized_sql_fp(self) -> None:
        f = self._load("002_parameterized_sql_fp.json")
        self.assertFalse(f["expected_finding"])
        self._assert_anti_example(f)

    def test_004_insecure_skip_verify_test_fp(self) -> None:
        f = self._load("004_insecure_skip_verify_test_fp.json")
        self.assertFalse(f["expected_finding"])
        self._assert_anti_example(f)

    def test_006_math_rand_non_security_fp(self) -> None:
        f = self._load("006_math_rand_non_security_fp.json")
        self.assertFalse(f["expected_finding"])
        self._assert_anti_example(f)
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

    def test_fixture_ids_are_unique(self) -> None:
        ids = []
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            with open(path) as fp:
                data = json.load(fp)
            ids.append(data["id"])
        self.assertEqual(len(ids), len(set(ids)), f"duplicate fixture IDs: {ids}")

    def test_fixture_severities_are_valid(self) -> None:
        valid = {"P0", "P1", "P2", "P3"}
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            with open(path) as fp:
                data = json.load(fp)
            if "severity" in data:
                self.assertIn(
                    data["severity"],
                    valid,
                    f"{path.name}: invalid severity {data['severity']!r}",
                )


if __name__ == "__main__":
    unittest.main()

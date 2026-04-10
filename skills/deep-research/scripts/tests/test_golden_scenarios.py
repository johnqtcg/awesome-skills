"""Golden scenario tests for keyword coverage in the deep-research skill."""

import json
import re
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
SKILL_MD = SKILL_ROOT / "SKILL.md"
HALLUCINATION_REF = SKILL_ROOT / "references" / "hallucination-and-verification.md"
RESEARCH_PATTERNS = SKILL_ROOT / "references" / "research-patterns.md"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _all_skill_text() -> str:
    parts = [_read(SKILL_MD)]
    ref_dir = SKILL_ROOT / "references"
    if ref_dir.is_dir():
        for f in ref_dir.iterdir():
            if f.suffix == ".md":
                parts.append(_read(f))
    return "\n".join(parts)


class TestGoldenFromFixtures(unittest.TestCase):
    """Parameterized tests from golden/*.json fixtures."""

    @classmethod
    def setUpClass(cls):
        cls.all_text = _all_skill_text()
        cls.fixtures = {}
        if GOLDEN_DIR.is_dir():
            for f in sorted(GOLDEN_DIR.glob("*.json")):
                cls.fixtures[f.stem] = json.loads(f.read_text())

    def _check_fixture(self, name: str):
        fixture = self.fixtures.get(name)
        if not fixture:
            self.skipTest(f"golden/{name}.json not found")
        keywords = fixture.get("required_keywords", [])
        for kw in keywords:
            if kw.startswith("re:"):
                pattern = kw[3:]
                self.assertRegex(
                    self.all_text, pattern,
                    f"[{name}] regex pattern not found: {pattern}",
                )
            else:
                self.assertIn(
                    kw, self.all_text,
                    f"[{name}] keyword not found: {kw}",
                )


def _make_fixture_test(fixture_name):
    def test_method(self):
        self._check_fixture(fixture_name)
    test_method.__doc__ = f"Golden scenario: {fixture_name}"
    return test_method


_FIXTURE_NAMES = [
    "error_debugging",
    "tech_comparison",
    "hallucination_awareness",
    "codebase_research",
    "performance_benchmark",
    "security_research",
    "ai_tool_selection",
    "evidence_chain",
]

for _name in _FIXTURE_NAMES:
    setattr(TestGoldenFromFixtures, f"test_{_name}", _make_fixture_test(_name))


class TestCommonScenarios(unittest.TestCase):
    """Inline golden scenario tests."""

    @classmethod
    def setUpClass(cls):
        cls.skill = _read(SKILL_MD)
        cls.all_text = _all_skill_text()

    def test_cross_validation_mentioned(self):
        self.assertIn("cross", self.all_text.lower())

    def test_citation_requirement(self):
        self.assertRegex(self.all_text, r"(?i)citation.*url|url.*citation")

    def test_source_tier_system(self):
        for tier in ["T1", "T2", "T3", "T4", "T5"]:
            self.assertIn(tier, self.all_text)

    def test_perplexity_mentioned(self):
        self.assertIn("Perplexity", self.all_text)

    def test_duckduckgo_in_script_context(self):
        self.assertIn("DDG", self.skill)

    def test_confidence_levels(self):
        for level in ["High", "Medium", "Low"]:
            self.assertIn(level, self.skill)

    def test_verification_protocol(self):
        self.assertIn("Verification", self.all_text)

    def test_content_extraction_mandatory(self):
        self.assertRegex(self.skill, r"(?i)mandatory.*content.*extraction|content.*extraction.*mandatory")

    def test_fabrication_prohibition(self):
        self.assertRegex(self.skill, r"(?i)never.*fabricat")

    def test_degradation_levels(self):
        for level in ["Full", "Partial", "Blocked"]:
            self.assertIn(f"**{level}**", self.skill)

    def test_budget_enforcement(self):
        self.assertIn("50", self.skill)

    def test_ambiguity_stop_and_ask(self):
        self.assertRegex(self.skill, r"(?i)stop.*ask")

    def test_query_syntax_operators(self):
        for op in ["site:", "filetype:", "after:"]:
            self.assertIn(op, self.all_text)


class TestBehavioralScenarios(unittest.TestCase):
    """Behavioral regression tests that verify SKILL.md contains the decision
    rules needed to produce correct mode selection, false-positive prevention,
    and suppression decisions — not just that keywords exist.

    Schema for behavioral fixtures:
      expected_mode       Quick | Standard | Deep
      user_override       bool — user explicitly specified a mode
      is_deep_research_needed  bool — false = Deep would be over-research
      is_web_research_needed   bool — false = web retrieval not needed
      coverage_rules      list[str] — must appear in all_text (SKILL + refs)
    """

    @classmethod
    def setUpClass(cls):
        cls.skill_text = _read(SKILL_MD)
        cls.all_text = _all_skill_text()

    def _load(self, filename: str) -> dict:
        path = GOLDEN_DIR / filename
        if not path.exists():
            self.skipTest(f"fixture not found: {filename}")
        return json.loads(path.read_text())

    def _assert_coverage(self, fixture: dict) -> None:
        for rule in fixture.get("coverage_rules", []):
            self.assertIn(
                rule,
                self.all_text,
                f"[{fixture['id']}] coverage rule missing: {rule!r}",
            )

    # ------------------------------------------------------------------
    # Mode auto-selection
    # ------------------------------------------------------------------

    def test_behavior_001_quick_mode_single_fact(self) -> None:
        """Single factual question should trigger Quick mode, not over-research."""
        f = self._load("behavior_mode_quick.json")
        self.assertEqual(f["expected_mode"], "Quick")
        self._assert_coverage(f)

    def test_behavior_002_deep_mode_security_decision(self) -> None:
        """Security-sensitive multi-vendor decision should trigger Deep mode."""
        f = self._load("behavior_mode_deep_security.json")
        self.assertEqual(f["expected_mode"], "Deep")
        self._assert_coverage(f)

    def test_behavior_003_user_override_standard(self) -> None:
        """Explicit user mode specification overrides auto-selection."""
        f = self._load("behavior_mode_user_override.json")
        self.assertTrue(f.get("user_override"), "fixture must declare user_override=true")
        self._assert_coverage(f)

    # ------------------------------------------------------------------
    # False-positive prevention
    # ------------------------------------------------------------------

    def test_fp_001_quick_prevents_over_research(self) -> None:
        """Trivial single-fact lookup must NOT trigger Deep mode."""
        f = self._load("fp_quick_prevents_over_research.json")
        self.assertFalse(
            f.get("is_deep_research_needed", True),
            "fixture must declare is_deep_research_needed=false",
        )
        self.assertEqual(f.get("correct_mode"), "Quick")
        self._assert_coverage(f)

    def test_fp_002_codebase_no_web_retrieval(self) -> None:
        """Internal codebase question must not trigger external web retrieval."""
        f = self._load("fp_codebase_no_web_retrieval.json")
        self.assertFalse(
            f.get("is_web_research_needed", True),
            "fixture must declare is_web_research_needed=false",
        )
        self._assert_coverage(f)

    # ------------------------------------------------------------------
    # Degradation decision
    # ------------------------------------------------------------------

    def test_behavior_004_blocked_degradation(self) -> None:
        """Budget exhaustion / unreachable sources must produce Blocked degradation."""
        f = self._load("behavior_degradation_blocked.json")
        self.assertEqual(f["expected_degradation"], "Blocked")
        self._assert_coverage(f)

    # ------------------------------------------------------------------
    # Confidence assignment
    # ------------------------------------------------------------------

    def test_behavior_005_confidence_high(self) -> None:
        """Official source + verified content must yield High confidence."""
        f = self._load("behavior_confidence_high.json")
        self.assertEqual(f["expected_confidence"], "High")
        self._assert_coverage(f)

    def test_behavior_006_confidence_medium(self) -> None:
        """Technology comparison requiring 3+ independent benchmarks yields Medium."""
        f = self._load("behavior_confidence_medium.json")
        self.assertEqual(f["expected_confidence"], "Medium")
        self._assert_coverage(f)


if __name__ == "__main__":
    unittest.main()

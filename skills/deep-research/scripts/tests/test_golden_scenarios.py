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


if __name__ == "__main__":
    unittest.main()

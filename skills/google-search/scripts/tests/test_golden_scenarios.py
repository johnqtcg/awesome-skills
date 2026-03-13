"""
Golden scenario tests for the google-search skill.
Validates that SKILL.md and reference files contain expected keywords
for common search scenarios that the skill must handle.
"""

import json
import os
import re
import pytest

SKILL_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SKILL_MD = os.path.join(SKILL_ROOT, "SKILL.md")
REFS_DIR = os.path.join(SKILL_ROOT, "references")
GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _all_content() -> str:
    """Concatenate SKILL.md and all reference files for broad keyword checks."""
    parts = [_read(SKILL_MD)]
    for fname in os.listdir(REFS_DIR):
        if fname.endswith(".md"):
            parts.append(_read(os.path.join(REFS_DIR, fname)))
    return "\n".join(parts)


ALL_CONTENT = _all_content()


# ── Golden Fixture Tests ─────────────────────────────────────────────────

def _load_golden_fixtures():
    fixtures = []
    if not os.path.isdir(GOLDEN_DIR):
        return fixtures
    for fname in sorted(os.listdir(GOLDEN_DIR)):
        if fname.endswith(".json"):
            path = os.path.join(GOLDEN_DIR, fname)
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            fixtures.append(pytest.param(data, id=fname.replace(".json", "")))
    return fixtures


@pytest.mark.parametrize("fixture", _load_golden_fixtures())
def test_golden_scenario(fixture):
    """Each golden fixture defines required keywords that must appear in the skill corpus."""
    scenario = fixture.get("scenario", "unknown")
    keywords = fixture.get("required_keywords", [])
    for kw in keywords:
        if kw.startswith("regex:"):
            pattern = kw[len("regex:"):]
            assert re.search(pattern, ALL_CONTENT, re.IGNORECASE), \
                f"[{scenario}] regex pattern not found: {pattern}"
        else:
            assert kw.lower() in ALL_CONTENT.lower(), \
                f"[{scenario}] keyword not found: {kw}"


# ── Inline Scenario Tests ────────────────────────────────────────────────

class TestErrorDebuggingScenario:
    """A developer searching for a Go error message."""

    def test_exact_error_pattern(self):
        assert '"<exact error message>"' in ALL_CONTENT or \
               '"exact error message"' in ALL_CONTENT.lower()

    def test_stackoverflow_pattern(self):
        assert "site:stackoverflow.com" in ALL_CONTENT

    def test_github_issues_pattern(self):
        assert "site:github.com" in ALL_CONTENT


class TestOfficialDocsScenario:
    """A developer searching for Go standard library documentation."""

    def test_go_dev_site(self):
        assert "site:go.dev" in ALL_CONTENT

    def test_pkg_go_dev(self):
        assert "site:pkg.go.dev" in ALL_CONTENT


class TestChineseProductionExperience:
    """A developer searching for Chinese production experience reports."""

    def test_zhihu(self):
        assert "site:zhihu.com" in ALL_CONTENT

    def test_juejin(self):
        assert "site:juejin.cn" in ALL_CONTENT

    def test_pitfall_keywords(self):
        assert "踩坑" in ALL_CONTENT


class TestPerformanceBenchmarkScenario:
    """A developer searching for framework benchmarks."""

    def test_techempower(self):
        assert "TechEmpower" in ALL_CONTENT

    def test_after_date(self):
        assert "after:" in ALL_CONTENT

    def test_benchmark_keyword(self):
        assert "benchmark" in ALL_CONTENT.lower()


class TestHighConflictScenario:
    """A user searching for war casualty numbers."""

    def test_scope_lock(self):
        assert "scope" in ALL_CONTENT.lower() and "lock" in ALL_CONTENT.lower()

    def test_claim_tiers(self):
        assert "claim tier" in ALL_CONTENT.lower() or "source tier" in ALL_CONTENT.lower()

    def test_as_of_date(self):
        assert "as of DATE" in ALL_CONTENT or "As of DATE" in ALL_CONTENT


class TestToolDiscoveryScenario:
    """A user searching for online tools or software alternatives."""

    def test_online_tool_pattern(self):
        assert "online tool" in ALL_CONTENT.lower()

    def test_alternatives_pattern(self):
        assert "alternatives" in ALL_CONTENT.lower()


class TestPDFReportScenario:
    """A user searching for PDF reports or whitepapers."""

    def test_filetype_pdf(self):
        assert "filetype:pdf" in ALL_CONTENT

    def test_report_pattern(self):
        assert "report" in ALL_CONTENT.lower()


class TestWalledGardenScenario:
    """A user searching for content locked in Chinese platforms."""

    def test_wechat(self):
        assert "WeChat" in ALL_CONTENT or "微信" in ALL_CONTENT

    def test_xiaohongshu(self):
        assert "Xiaohongshu" in ALL_CONTENT or "小红书" in ALL_CONTENT

    def test_platform_search_recommendation(self):
        assert "search within the app" in ALL_CONTENT.lower() or \
               "search directly" in ALL_CONTENT.lower()


class TestGitHubCodeSearchScenario:
    """A developer searching for real code examples on GitHub."""

    def test_language_filter(self):
        assert "language:go" in ALL_CONTENT

    def test_stars_filter(self):
        assert "stars:>" in ALL_CONTENT

    def test_filename_filter(self):
        assert "filename:" in ALL_CONTENT


class TestQueryRefinementScenario:
    """Skill must support iterative query refinement."""

    def test_refinement_loop(self):
        assert "Refinement Loop" in ALL_CONTENT

    def test_noise_reduction(self):
        assert "Noise Reduction" in ALL_CONTENT or "noise" in ALL_CONTENT.lower()

"""
Golden scenario tests for the google-search skill.

Each fixture states which *file* (and optionally which section) must carry the pattern.
A fixture may also forbid patterns within that scope.

Why the scope field exists: these checks used to match against one blob of SKILL.md plus
every reference file, so "the GitHub section documents `path:`" was satisfied by the word
`path:` appearing anywhere in seven files, and a forbidden pattern could never be expressed
at all. A scope wider than the claim fails open — see the module docstring of
scripts/lint_search_report.py for the concrete defect that shipped behind it.
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


def _section(text: str, heading: str) -> str:
    m = re.search(rf"^(#{{1,6}})\s+{re.escape(heading)}\s*$", text, re.MULTILINE)
    if not m:
        return ""
    level = len(m.group(1))
    rest = text[m.end():]
    nxt = re.search(rf"^#{{1,{level}}}\s+\S", rest, re.MULTILINE)
    return rest[: nxt.start()] if nxt else rest


def _scope_text(fixture) -> tuple[str, str]:
    """Resolve a fixture's scope to (text, label). Missing scopes are a hard error, not
    a silent fall back to the whole corpus."""
    scope = fixture.get("scope")
    if not scope:
        return ALL_CONTENT, "corpus"
    path = SKILL_MD if scope == "SKILL.md" else os.path.join(REFS_DIR, scope)
    assert os.path.isfile(path), f"fixture scope names a missing file: {scope}"
    text = _read(path)
    heading = fixture.get("section")
    if heading:
        text = _section(text, heading)
        assert text.strip(), f"fixture scope names a missing section: {scope} § {heading}"
        return text, f"{scope} § {heading}"
    return text, scope


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


GOLDEN_FIXTURES = _load_golden_fixtures()


def _match(pattern: str, text: str) -> bool:
    if pattern.startswith("regex:"):
        return bool(re.search(pattern[len("regex:"):], text, re.IGNORECASE))
    return pattern.lower() in text.lower()


@pytest.mark.parametrize("fixture", GOLDEN_FIXTURES)
def test_golden_scenario_required(fixture):
    """Required patterns must appear inside the fixture's declared scope."""
    scenario = fixture.get("scenario", "unknown")
    text, label = _scope_text(fixture)
    for kw in fixture.get("required_keywords", []):
        assert _match(kw, text), f"[{scenario}] not found in {label}: {kw}"


@pytest.mark.parametrize("fixture", GOLDEN_FIXTURES)
def test_golden_scenario_forbidden(fixture):
    """Forbidden patterns must not appear inside the fixture's declared scope.

    This is what a corpus-wide `in` check cannot express: `stars:` must be absent from the
    code-search recommendations while still being present in the table that warns about it.
    """
    scenario = fixture.get("scenario", "unknown")
    forbidden = fixture.get("forbidden_keywords", [])
    if not forbidden:
        pytest.skip("fixture declares no forbidden patterns")
    text, label = _scope_text(fixture)
    for kw in forbidden:
        assert not _match(kw, text), f"[{scenario}] forbidden pattern present in {label}: {kw}"


def test_at_least_one_fixture_declares_a_scope():
    """Negative control: if every fixture fell back to the corpus, the scope machinery
    above would be dead code and these tests would be the old fail-open shape."""
    scoped = [f.values[0] for f in GOLDEN_FIXTURES if f.values[0].get("scope")]
    assert len(scoped) >= 3, f"only {len(scoped)} scoped fixture(s)"


def test_at_least_one_fixture_declares_forbidden_patterns():
    forbidding = [f.values[0] for f in GOLDEN_FIXTURES if f.values[0].get("forbidden_keywords")]
    assert forbidding, "no fixture exercises the forbidden-pattern path"


def test_fixtures_are_substantive():
    """An emptied fixture would pass every check above without asserting anything."""
    for param in GOLDEN_FIXTURES:
        data = param.values[0]
        assert len(data.get("required_keywords", [])) >= 3, data.get("scenario")


def test_forbidden_check_fires_when_the_pattern_is_in_scope():
    """Negative control for the mechanism itself.

    `filename:` must be absent from the code-search recommendations and present in the
    table that warns about it. Pointing the forbidden check at the warning table must
    therefore FAIL — if it passed, the check would be inert and the code-search fixture's
    green result would mean nothing.
    """
    control = {
        "scenario": "control",
        "scope": "programmer-search-patterns.md",
        "section": "Qualifiers that do NOT work in code search",
        "forbidden_keywords": ["filename:"],
    }
    text, _ = _scope_text(control)
    assert _match("filename:", text), "warning table no longer names filename:"
    with pytest.raises(AssertionError):
        test_golden_scenario_forbidden(control)


def test_missing_scope_is_an_error_not_a_corpus_fallback():
    """A typo'd scope must fail loudly. Falling back to the whole corpus is how a
    narrowed check silently reverts to the fail-open shape it replaced."""
    with pytest.raises(AssertionError):
        _scope_text({"scope": "no-such-file.md"})
    with pytest.raises(AssertionError):
        _scope_text({"scope": "SKILL.md", "section": "No Such Heading"})


# ── Scoped Scenario Tests ────────────────────────────────────────────────
#
# The scenarios above are covered by the golden fixtures, which bind each pattern to the
# file and section that owns it. The whole-corpus versions of those same assertions were
# deleted rather than kept alongside: `assert "filename:" in ALL_CONTENT` passed both while
# the docs recommended that qualifier and after they moved it into a do-not-use table, so
# keeping it would have re-added the fail-open signal the fixtures exist to remove.
#
# What remains here are checks that are genuinely about a single file's structure.

QPAT = _read(os.path.join(REFS_DIR, "query-patterns.md"))
PROG = _read(os.path.join(REFS_DIR, "programmer-search-patterns.md"))


class TestToolDiscoveryScenario:
    """A user searching for online tools or software alternatives."""

    def test_tools_section_exists(self):
        assert _section(QPAT, "Tools and Software").strip()

    def test_task_first_patterns(self):
        body = _section(QPAT, "Tools and Software")
        assert "online tool" in body.lower()
        assert "alternative" in body.lower()

    def test_does_not_lead_with_the_unreliable_related_operator(self):
        body = _section(QPAT, "Tools and Software")
        for line in body.split("\n"):
            if re.match(r"^\s*[-*]\s+`", line) and "related:" in line:
                assert "returns nothing" in body, (
                    "related: may only appear with its reliability caveat"
                )


class TestQueryRefinementScenario:
    """Skill must support iterative query refinement."""

    def test_refinement_loop(self):
        body = _section(QPAT, "Refinement Loop")
        assert body.strip(), "Refinement Loop section missing from query-patterns.md"
        steps = [l for l in body.split("\n") if re.match(r"^\s*\d+\.", l)]
        assert len(steps) >= 5, f"refinement loop has only {len(steps)} steps"

    def test_noise_reduction(self):
        assert _section(QPAT, "Noise Reduction").strip()


class TestOperatorTiering:
    """Google operators must be graded, not presented as uniformly stable."""

    TIERS = [
        "Tier A — documented in Google's own help page",
        "Tier B — undocumented but generally working",
        "Tier C — unreliable, verify before relying on it",
    ]

    @pytest.mark.parametrize("heading", TIERS)
    def test_tier_section_present(self, heading):
        assert _section(PROG, heading).strip(), f"missing operator tier: {heading}"

    def test_documented_tier_holds_only_googles_documented_operators(self):
        body = _section(PROG, self.TIERS[0])
        for undocumented in ("intitle:", "allintitle:", "intext:", "inurl:", "related:"):
            assert undocumented not in body, (
                f"{undocumented} is not on Google's documented list but sits in Tier A"
            )

    def test_date_operator_semantics_are_stated(self):
        body = _section(PROG, self.TIERS[0])
        assert "last updated" in body.lower(), (
            "before:/after: filter on document update time; without that caveat the skill "
            "treats a re-published 2019 page as fresh evidence"
        )

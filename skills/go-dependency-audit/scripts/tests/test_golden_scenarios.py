"""Golden scenario tests for the go-dependency-audit skill.

Each fixture is a scenario the skill must handle, paired with the feedback it
should produce. The tests below check that every fixture is *anchored* — that
its declared rule and its coverage strings genuinely exist in the skill, and
that its own vocabulary is internally consistent.

Why the anchoring matters: a previous revision shipped a fixture whose
violated_rule read "Gradual ramp-up — not instant full load", copied verbatim
from an unrelated load-testing skill. Nothing caught it, because only
coverage_rules were validated against the documents and violated_rule was
never checked at all. test_violated_rule_is_anchored_in_the_docs closes that.

These tests do not evaluate model behaviour. They keep the fixture corpus
honest so that a behavioural evaluation built on it would be measuring the
right thing.
"""

from __future__ import annotations

import json
import pathlib
import re

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
GOLDEN_DIR = pathlib.Path(__file__).resolve().parent / "golden"
REFS_DIR = SKILL_DIR / "references"

VALID_TYPES = {"defect", "good_practice", "degradation_scenario", "workflow"}
VALID_SEVERITIES = {"critical", "standard", "hygiene", "none"}
VALID_PRIORITIES = {"P0", "P1", "P2", "P3", None}

REQUIRED_FIELDS = {
    "id", "title", "type", "severity", "priority", "code_snippet",
    "violated_rule", "expected_feedback", "coverage_rules", "reference",
}

# `severity` and `priority` are deliberately separate fields naming separate
# things, because the previous corpus conflated them: `severity` is the
# scorecard tier the *audit defect* belongs to, `priority` is what the *finding*
# would be rated in a correct report. They are independent — an audit can fail a
# Standard-tier check by mis-triaging something that is genuinely only P3. The
# tests below assert that both are present and drawn from their own vocabulary;
# they deliberately do NOT couple the two.

# Coverage strings must identify something; these match nearly everywhere.
TOO_GENERIC = {
    "standard", "deep", "quick", "gpl", "cve", "govulncheck", "license",
    "replace", "go.mod", "go.sum", "module", "upgrade", "scan",
}
MIN_COVERAGE_RULE_LEN = 8


def _docs() -> dict[str, str]:
    out = {"SKILL.md": (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")}
    for f in sorted(REFS_DIR.glob("*.md")):
        out[f"references/{f.name}"] = f.read_text(encoding="utf-8")
    return out


DOCS = _docs()
ALL_DOCS_LOWER = "\n".join(DOCS.values()).lower()


def _load_fixtures() -> list[dict]:
    return [json.loads(f.read_text(encoding="utf-8"))
            for f in sorted(GOLDEN_DIR.glob("*.json"))]


FIXTURES = _load_fixtures()
IDS = [fx["id"] for fx in FIXTURES]


# ──────────────────────────────────────────────────────────────────────
class TestCorpusShape:

    def test_minimum_fixture_count(self):
        assert len(FIXTURES) >= 15, f"only {len(FIXTURES)} fixtures"

    def test_unique_ids(self):
        assert len(IDS) == len(set(IDS)), f"duplicate IDs: {IDS}"

    def test_every_category_is_represented(self):
        present = {fx["type"] for fx in FIXTURES}
        assert present == VALID_TYPES, f"missing categories: {VALID_TYPES - present}"

    def test_every_severity_tier_is_exercised(self):
        present = {fx["severity"] for fx in FIXTURES}
        assert present == VALID_SEVERITIES, \
            f"unexercised severity tiers: {VALID_SEVERITIES - present}"

    def test_every_priority_is_exercised(self):
        present = {fx["priority"] for fx in FIXTURES}
        assert present == VALID_PRIORITIES, \
            f"unexercised priorities: {VALID_PRIORITIES - present}"

    def test_every_reference_file_is_exercised(self):
        used = {fx["reference"] for fx in FIXTURES}
        for name in DOCS:
            assert name in used, f"no fixture references {name}"


# ──────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("fx", FIXTURES, ids=IDS)
class TestEveryFixture:

    def test_required_fields(self, fx):
        missing = REQUIRED_FIELDS - set(fx)
        assert not missing, f"{fx['id']} missing fields: {sorted(missing)}"

    def test_valid_type(self, fx):
        assert fx["type"] in VALID_TYPES

    def test_valid_severity(self, fx):
        assert fx["severity"] in VALID_SEVERITIES

    def test_valid_priority(self, fx):
        assert fx["priority"] in VALID_PRIORITIES

    def test_defects_carry_a_severity_and_priority(self, fx):
        if fx["type"] != "defect":
            return
        assert fx["severity"] != "none", f"{fx['id']} is a defect with severity=none"
        assert fx["priority"] is not None, f"{fx['id']} is a defect with no priority"

    def test_non_defects_carry_neither(self, fx):
        if fx["type"] == "defect":
            return
        assert fx["severity"] == "none"
        assert fx["priority"] is None

    def test_severity_and_priority_are_separate_vocabularies(self, fx):
        """Neither field may borrow the other's values."""
        assert fx["severity"] not in {"P0", "P1", "P2", "P3"}, (
            f"{fx['id']}: severity holds a priority value — these are separate "
            f"vocabularies (scorecard tier vs finding priority)"
        )
        assert fx["priority"] not in {"critical", "standard", "hygiene"}, (
            f"{fx['id']}: priority holds a scorecard tier value"
        )

    def test_violated_rule_presence_matches_type(self, fx):
        if fx["type"] == "defect":
            assert fx["violated_rule"], f"{fx['id']} is a defect with no rule"
        else:
            assert fx["violated_rule"] is None, \
                f"{fx['id']} is a {fx['type']} but names a violated rule"

    def test_violated_rule_is_anchored_in_the_docs(self, fx):
        """The check that a copy-pasted rule from another skill would fail."""
        rule = fx["violated_rule"]
        if rule is None:
            return
        assert rule.lower() in ALL_DOCS_LOWER, (
            f"{fx['id']} violates {rule!r}, which appears nowhere in SKILL.md or "
            f"references/ — either the rule was invented or it was copied from "
            f"another skill"
        )

    def test_coverage_rules_are_findable(self, fx):
        for rule in fx["coverage_rules"]:
            assert rule.lower() in ALL_DOCS_LOWER, \
                f"{fx['id']} coverage_rule not found in any doc: {rule!r}"

    def test_coverage_rules_are_specific(self, fx):
        for rule in fx["coverage_rules"]:
            assert len(rule) >= MIN_COVERAGE_RULE_LEN, \
                f"{fx['id']} coverage_rule {rule!r} is too short to identify anything"
            assert rule.strip().lower() not in TOO_GENERIC, (
                f"{fx['id']} coverage_rule {rule!r} is a bare common term; it "
                f"would be satisfied by an unrelated match anywhere in the docs"
            )

    def test_coverage_rules_are_distinct(self, fx):
        rules = [r.lower() for r in fx["coverage_rules"]]
        assert len(rules) == len(set(rules)), f"{fx['id']} has duplicate coverage_rules"

    def test_at_least_four_coverage_rules(self, fx):
        assert len(fx["coverage_rules"]) >= 4, \
            f"{fx['id']} has only {len(fx['coverage_rules'])} coverage rules"

    def test_reference_file_exists(self, fx):
        assert fx["reference"] in DOCS, \
            f"{fx['id']} references {fx['reference']!r}, which is not a skill document"

    def test_reference_actually_covers_the_scenario(self, fx):
        """The named file must carry at least one of the fixture's anchors."""
        target = DOCS[fx["reference"]].lower()
        hits = [r for r in fx["coverage_rules"] if r.lower() in target]
        assert hits, (
            f"{fx['id']} names {fx['reference']} as its reference, but none of "
            f"its coverage_rules appear there — the pointer is wrong or the "
            f"content moved"
        )

    def test_expected_feedback_is_substantive(self, fx):
        fb = fx["expected_feedback"]
        assert len(fb) >= 120, f"{fx['id']} expected_feedback is too thin to grade"
        assert fb.strip().endswith("."), f"{fx['id']} expected_feedback is truncated"

    def test_defect_feedback_states_its_priority(self, fx):
        if fx["type"] != "defect":
            return
        fb = fx["expected_feedback"]
        snippet = fx["code_snippet"]
        # Either the feedback names the priority, or the fixture is about a
        # non-priority property (framing, scope, tooling correctness).
        assert re.search(r"\bP[0-3]\b", fb) or len(fb) > 200, (
            f"{fx['id']} feedback neither names a priority nor explains the "
            f"defect at length"
        )
        assert snippet.strip(), f"{fx['id']} has an empty code_snippet"

    def test_good_practice_feedback_says_so(self, fx):
        if fx["type"] != "good_practice":
            return
        assert "no violation" in fx["expected_feedback"].lower()


# ──────────────────────────────────────────────────────────────────────
class TestSpecificScenarios:
    """Named checks for the failure modes this revision was written to fix."""

    @staticmethod
    def _by_id(fixture_id: str) -> dict:
        for fx in FIXTURES:
            if fx["id"] == fixture_id:
                return fx
        raise AssertionError(f"fixture {fixture_id} not found")

    def test_cvss_fabrication_is_covered(self):
        fx = self._by_id("DEP-008")
        assert "cvss" in fx["expected_feedback"].lower()
        assert "not retrieved" in fx["expected_feedback"].lower()

    def test_legal_verdict_is_covered(self):
        fx = self._by_id("DEP-005")
        fb = fx["expected_feedback"].lower()
        assert "legal advice" in fb or "legal review" in fb
        assert "distributed" in fb

    def test_destructive_rollback_is_covered(self):
        fx = self._by_id("DEP-009")
        assert "git checkout" in fx["code_snippet"]
        assert "reflog" in fx["expected_feedback"]

    def test_json_exit_code_gate_is_covered(self):
        fx = self._by_id("DEP-010")
        assert "-json" in fx["code_snippet"]
        assert "never fail" in fx["expected_feedback"]

    def test_module_cycle_is_not_a_failure(self):
        fx = self._by_id("DEP-011")
        assert "legal in Go" in fx["expected_feedback"]

    def test_block_and_degrade_are_distinguished(self):
        block = self._by_id("DEP-014")
        degrade = self._by_id("DEP-015")
        assert "BLOCK" in block["expected_feedback"]
        assert "DEGRADE" in degrade["expected_feedback"]
        assert "NOT AN AUDIT" in block["expected_feedback"]
        assert "no-cve" in degrade["expected_feedback"]

    def test_reachability_is_not_inferred_from_absence(self):
        fx = self._by_id("DEP-004")
        fb = fx["expected_feedback"]
        assert "not measured" in fb
        assert "not a string govulncheck v1.x emits" in fb

"""Golden scenario tests for load-test skill.

Each fixture gets its own test class for precise failure diagnosis.
Tests verify: type/severity classification, violated_rule semantics,
and that all coverage_rules strings exist in SKILL.md + references.
"""

import json
import pathlib

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
GOLDEN_DIR = pathlib.Path(__file__).resolve().parent / "golden"
REFS_DIR = SKILL_DIR / "references"

VALID_TYPES = {"defect", "good_practice", "degradation_scenario", "workflow"}
VALID_SEVERITIES = {"critical", "standard", "hygiene", "none"}
REQUIRED_FIELDS = {
    "id", "title", "type", "severity", "code_snippet",
    "expected_feedback", "coverage_rules", "reference",
}


def _all_docs_lower() -> str:
    parts = [(SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")]
    for f in sorted(REFS_DIR.glob("*.md")):
        parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts).lower()


def _load_fixtures() -> list[dict]:
    fixtures = []
    for f in sorted(GOLDEN_DIR.glob("*.json")):
        fixtures.append(json.loads(f.read_text(encoding="utf-8")))
    return fixtures


def _load(fixture_id: str) -> dict:
    for fx in _load_fixtures():
        if fx["id"] == fixture_id:
            return fx
    raise ValueError(f"fixture {fixture_id} not found")


ALL_DOCS = _all_docs_lower()


# ──────────────────────────────────────────────────────────────────────
class TestFixtureIntegrity:
    """Structural checks across all golden fixtures."""

    def test_minimum_fixture_count(self):
        assert len(_load_fixtures()) >= 11

    def test_required_fields(self):
        for fx in _load_fixtures():
            missing = REQUIRED_FIELDS - set(fx.keys())
            assert not missing, f"{fx['id']} missing fields: {missing}"

    def test_valid_types(self):
        for fx in _load_fixtures():
            assert fx["type"] in VALID_TYPES, f"{fx['id']} bad type: {fx['type']}"

    def test_valid_severities(self):
        for fx in _load_fixtures():
            assert fx["severity"] in VALID_SEVERITIES, \
                f"{fx['id']} bad severity: {fx['severity']}"

    def test_defect_severity_not_none(self):
        for fx in _load_fixtures():
            if fx["type"] == "defect":
                assert fx["severity"] != "none", \
                    f"{fx['id']} is defect but severity=none"

    def test_non_defect_severity_none(self):
        for fx in _load_fixtures():
            if fx["type"] in ("good_practice", "degradation_scenario", "workflow"):
                assert fx["severity"] == "none", \
                    f"{fx['id']} is {fx['type']} but severity={fx['severity']}"

    def test_unique_ids(self):
        ids = [fx["id"] for fx in _load_fixtures()]
        assert len(ids) == len(set(ids)), f"duplicate IDs: {ids}"

    def test_coverage_rules_findable(self):
        for fx in _load_fixtures():
            for rule in fx["coverage_rules"]:
                assert rule.lower() in ALL_DOCS, \
                    f"{fx['id']} coverage_rule not found: {rule!r}"


# ──────────────────────────────────────────────────────────────────────
# Critical Defects
# ──────────────────────────────────────────────────────────────────────
class TestLT001:
    """No warmup phase."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("LT-001")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "critical"

    def test_violated_rule(self):
        assert "warmup" in self.fx["violated_rule"].lower()

    def test_expected_mentions_warmup(self):
        assert "warmup" in self.fx["expected_feedback"].lower()


class TestLT002:
    """No SLO thresholds."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("LT-002")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "critical"

    def test_violated_rule(self):
        assert "slo" in self.fx["violated_rule"].lower()

    def test_expected_mentions_threshold(self):
        fb = self.fx["expected_feedback"].lower()
        assert "slo" in fb
        assert "threshold" in fb or "meaningless" in fb


class TestLT003:
    """Short duration."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("LT-003")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "critical"

    def test_violated_rule(self):
        vr = self.fx["violated_rule"].lower()
        assert "duration" in vr or "steady state" in vr

    def test_expected_mentions_duration(self):
        fb = self.fx["expected_feedback"].lower()
        assert "30-second" in fb or "30s" in fb or "insufficient" in fb


# ──────────────────────────────────────────────────────────────────────
# Standard Defects
# ──────────────────────────────────────────────────────────────────────
class TestLT004:
    """Co-located load generator."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("LT-004")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "standard"

    def test_violated_rule(self):
        vr = self.fx["violated_rule"].lower()
        assert "co-located" in vr or "generator" in vr

    def test_expected_mentions_separate(self):
        assert "separate" in self.fx["expected_feedback"].lower()


class TestLT005:
    """Cache bias — same request."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("LT-005")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "standard"

    def test_violated_rule(self):
        vr = self.fx["violated_rule"].lower()
        assert "parameterized" in vr or "cache" in vr

    def test_expected_mentions_sharedarray(self):
        assert "sharedarray" in self.fx["expected_feedback"].lower()


class TestLT006:
    """Averages as verdict."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("LT-006")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "standard"

    def test_violated_rule(self):
        vr = self.fx["violated_rule"].lower()
        assert "percentile" in vr or "average" in vr

    def test_expected_mentions_p99(self):
        assert "p99" in self.fx["expected_feedback"].lower()


class TestLT007:
    """No ramp-up."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("LT-007")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "standard"

    def test_violated_rule(self):
        assert "ramp" in self.fx["violated_rule"].lower()

    def test_expected_mentions_ramping(self):
        assert "ramp" in self.fx["expected_feedback"].lower()


# ──────────────────────────────────────────────────────────────────────
# Good Practices
# ──────────────────────────────────────────────────────────────────────
class TestLT008:
    """Well-formed k6 script."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("LT-008")

    def test_type_severity(self):
        assert self.fx["type"] == "good_practice"
        assert self.fx["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fx["expected_feedback"].lower()

    def test_expected_mentions_sharedarray(self):
        assert "sharedarray" in self.fx["expected_feedback"].lower()


class TestLT009:
    """Well-formed vegeta breakpoint."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("LT-009")

    def test_type_severity(self):
        assert self.fx["type"] == "good_practice"
        assert self.fx["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fx["expected_feedback"].lower()

    def test_expected_mentions_vegeta(self):
        assert "vegeta" in self.fx["expected_feedback"].lower()


# ──────────────────────────────────────────────────────────────────────
# Degradation Scenarios
# ──────────────────────────────────────────────────────────────────────
class TestLT010:
    """Results without SLOs — partial mode."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("LT-010")

    def test_type_severity(self):
        assert self.fx["type"] == "degradation_scenario"
        assert self.fx["severity"] == "none"

    def test_expected_forbids_claims(self):
        fb = self.fx["expected_feedback"].lower()
        assert "cannot claim" in fb or "must not" in fb

    def test_expected_mentions_degraded(self):
        assert "degraded" in self.fx["expected_feedback"].lower()


class TestLT011:
    """No context — planning mode."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("LT-011")

    def test_type_severity(self):
        assert self.fx["type"] == "degradation_scenario"
        assert self.fx["severity"] == "none"

    def test_expected_mentions_gate_1(self):
        fb = self.fx["expected_feedback"].lower()
        assert "gate 1" in fb or "context collection" in fb

    def test_expected_mentions_planning(self):
        fb = self.fx["expected_feedback"].lower()
        assert "planning" in fb or "template" in fb


# ──────────────────────────────────────────────────────────────────────
# Workflow Scenarios
# ──────────────────────────────────────────────────────────────────────
class TestLT012:
    """Multi-scenario capacity plan."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("LT-012")

    def test_type_severity(self):
        assert self.fx["type"] == "workflow"
        assert self.fx["severity"] == "none"

    def test_expected_mentions_scenarios(self):
        fb = self.fx["expected_feedback"].lower()
        assert "smoke" in fb
        assert "breakpoint" in fb

    def test_expected_mentions_slo(self):
        assert "slo" in self.fx["expected_feedback"].lower()


class TestLT013:
    """Analyze results with SLO verdict."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("LT-013")

    def test_type_severity(self):
        assert self.fx["type"] == "workflow"
        assert self.fx["severity"] == "none"

    def test_expected_mentions_verdict(self):
        assert "verdict" in self.fx["expected_feedback"].lower()

    def test_expected_mentions_bottleneck(self):
        assert "bottleneck" in self.fx["expected_feedback"].lower()


class TestLT014:
    """Review existing script."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("LT-014")

    def test_type_severity(self):
        assert self.fx["type"] == "workflow"
        assert self.fx["severity"] == "none"

    def test_expected_mentions_review(self):
        assert "review" in self.fx["expected_feedback"].lower()

    def test_expected_mentions_findings(self):
        assert "finding" in self.fx["expected_feedback"].lower()
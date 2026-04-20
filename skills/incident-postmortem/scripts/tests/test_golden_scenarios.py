"""Golden scenario tests for incident-postmortem-postmortem skill."""

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
    return [json.loads(f.read_text(encoding="utf-8"))
            for f in sorted(GOLDEN_DIR.glob("*.json"))]


def _load(fid: str) -> dict:
    for fx in _load_fixtures():
        if fx["id"] == fid:
            return fx
    raise ValueError(f"fixture {fid} not found")


ALL_DOCS = _all_docs_lower()


# ──────────────────────────────────────────────────────────────────────
class TestFixtureIntegrity:

    def test_minimum_count(self):
        assert len(_load_fixtures()) >= 14

    def test_required_fields(self):
        for fx in _load_fixtures():
            missing = REQUIRED_FIELDS - set(fx.keys())
            assert not missing, f"{fx['id']} missing: {missing}"

    def test_valid_types(self):
        for fx in _load_fixtures():
            assert fx["type"] in VALID_TYPES, f"{fx['id']} bad type"

    def test_valid_severities(self):
        for fx in _load_fixtures():
            assert fx["severity"] in VALID_SEVERITIES

    def test_defect_severity_not_none(self):
        for fx in _load_fixtures():
            if fx["type"] == "defect":
                assert fx["severity"] != "none", fx["id"]

    def test_non_defect_severity_none(self):
        for fx in _load_fixtures():
            if fx["type"] in ("good_practice", "degradation_scenario", "workflow"):
                assert fx["severity"] == "none", fx["id"]

    def test_unique_ids(self):
        ids = [fx["id"] for fx in _load_fixtures()]
        assert len(ids) == len(set(ids))

    def test_coverage_rules_findable(self):
        for fx in _load_fixtures():
            for rule in fx["coverage_rules"]:
                assert rule.lower() in ALL_DOCS, \
                    f"{fx['id']} rule not found: {rule!r}"


# ── Critical Defects ─────────────────────────────────────────────────
class TestPM001:
    """Blame language."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-001")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "critical"

    def test_violated_rule(self):
        assert "blameless" in self.fx["violated_rule"].lower() or \
               "systemic" in self.fx["violated_rule"].lower()

    def test_expected_mentions_reframe(self):
        assert "reframe" in self.fx["expected_feedback"].lower() or \
               "blameless" in self.fx["expected_feedback"].lower()


class TestPM002:
    """Unsourced timeline."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-002")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "critical"

    def test_violated_rule(self):
        assert "timeline" in self.fx["violated_rule"].lower()

    def test_expected_mentions_source(self):
        assert "source" in self.fx["expected_feedback"].lower()


class TestPM003:
    """Unowned action items."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-003")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "critical"

    def test_violated_rule(self):
        assert "owner" in self.fx["violated_rule"].lower() or \
               "deadline" in self.fx["violated_rule"].lower()

    def test_expected_mentions_owner(self):
        assert "owner" in self.fx["expected_feedback"].lower()


# ── Standard Defects ─────────────────────────────────────────────────
class TestPM004:
    """Shallow RCA."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-004")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "standard"

    def test_violated_rule(self):
        assert "5-why" in self.fx["violated_rule"].lower() or \
               "depth" in self.fx["violated_rule"].lower()

    def test_expected_mentions_depth(self):
        assert "depth" in self.fx["expected_feedback"].lower()


class TestPM005:
    """No impact metrics."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-005")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "standard"

    def test_violated_rule(self):
        assert "metric" in self.fx["violated_rule"].lower() or \
               "impact" in self.fx["violated_rule"].lower()

    def test_expected_mentions_quantify(self):
        assert "duration" in self.fx["expected_feedback"].lower()


class TestPM006:
    """Missing what went well."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-006")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "standard"

    def test_violated_rule(self):
        assert "went well" in self.fx["violated_rule"].lower()

    def test_expected_mentions_celebrate(self):
        fb = self.fx["expected_feedback"].lower()
        assert "blameless" in fb or "positive" in fb


class TestPM007:
    """No tracking tickets."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-007")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "standard"

    def test_violated_rule(self):
        assert "tracking" in self.fx["violated_rule"].lower() or \
               "follow-up" in self.fx["violated_rule"].lower()

    def test_expected_mentions_jira(self):
        fb = self.fx["expected_feedback"].lower()
        assert "jira" in fb or "ticket" in fb


# ── Good Practices ───────────────────────────────────────────────────
class TestPM008:
    """Well-formed post-mortem."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-008")

    def test_type_severity(self):
        assert self.fx["type"] == "good_practice"
        assert self.fx["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fx["expected_feedback"].lower()

    def test_expected_mentions_blameless(self):
        assert "blameless" in self.fx["expected_feedback"].lower()


class TestPM009:
    """Well-executed 5-Why RCA."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-009")

    def test_type_severity(self):
        assert self.fx["type"] == "good_practice"
        assert self.fx["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fx["expected_feedback"].lower()

    def test_expected_mentions_systemic(self):
        assert "systemic" in self.fx["expected_feedback"].lower()


# ── Degradation Scenarios ────────────────────────────────────────────
class TestPM010:
    """Verbal only — sketch mode."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-010")

    def test_type_severity(self):
        assert self.fx["type"] == "degradation_scenario"
        assert self.fx["severity"] == "none"

    def test_expected_mentions_degraded(self):
        assert "degraded" in self.fx["expected_feedback"].lower()

    def test_expected_forbids_fabrication(self):
        fb = self.fx["expected_feedback"].lower()
        assert "must not" in fb or "cannot" in fb


class TestPM011:
    """No incident-postmortem — planning mode."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-011")

    def test_type_severity(self):
        assert self.fx["type"] == "degradation_scenario"
        assert self.fx["severity"] == "none"

    def test_expected_mentions_template(self):
        assert "template" in self.fx["expected_feedback"].lower()

    def test_expected_mentions_gate_1(self):
        fb = self.fx["expected_feedback"].lower()
        assert "gate 1" in fb or "planning" in fb


# ── Workflow Scenarios ───────────────────────────────────────────────
class TestPM012:
    """Full draft workflow."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-012")

    def test_type_severity(self):
        assert self.fx["type"] == "workflow"
        assert self.fx["severity"] == "none"

    def test_expected_mentions_timeline(self):
        assert "timeline" in self.fx["expected_feedback"].lower()

    def test_expected_mentions_5why(self):
        assert "5-why" in self.fx["expected_feedback"].lower()


class TestPM013:
    """Review workflow."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-013")

    def test_type_severity(self):
        assert self.fx["type"] == "workflow"
        assert self.fx["severity"] == "none"

    def test_expected_mentions_scorecard(self):
        assert "scorecard" in self.fx["expected_feedback"].lower()

    def test_expected_mentions_what_went_well(self):
        fb = self.fx["expected_feedback"].lower()
        assert "went well" in fb or "missing" in fb


# ── Defect: Recurring Incident ──────────────────────────────────────
class TestPM014:
    """Recurring incident-postmortem — unlinked related incidents."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-014")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "standard"

    def test_violated_rule(self):
        vr = self.fx["violated_rule"].lower()
        assert "related" in vr or "linked" in vr

    def test_expected_mentions_prior_incidents(self):
        fb = self.fx["expected_feedback"].lower()
        assert "prior" in fb or "previous" in fb or "related" in fb


# ── Workflow: Cross-team SEV-1 ──────────────────────────────────────
class TestPM015:
    """Cross-team SEV-1 deep analysis."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-015")

    def test_type_severity(self):
        assert self.fx["type"] == "workflow"
        assert self.fx["severity"] == "none"

    def test_expected_mentions_deep(self):
        assert "deep" in self.fx["expected_feedback"].lower()

    def test_expected_mentions_multi_team(self):
        fb = self.fx["expected_feedback"].lower()
        assert "multi-team" in fb or "cross-team" in fb


# ── Workflow: Near-miss Analysis ────────────────────────────────────
class TestPM016:
    """Near-miss with real data — SEV-4 analysis."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("PM-016")

    def test_type_severity(self):
        assert self.fx["type"] == "workflow"
        assert self.fx["severity"] == "none"

    def test_expected_mentions_near_miss(self):
        fb = self.fx["expected_feedback"].lower()
        assert "near-miss" in fb or "near miss" in fb

    def test_expected_mentions_sev4(self):
        assert "sev-4" in self.fx["expected_feedback"].lower()
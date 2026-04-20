"""Golden scenario tests for go-dependency-audit skill.

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
class TestDEP001:
    """Reachable critical CVE."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("DEP-001")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "critical"

    def test_violated_rule(self):
        assert "p0" in self.fx["violated_rule"].lower() or \
               "reachable" in self.fx["violated_rule"].lower()

    def test_expected_mentions_cve(self):
        assert "cve" in self.fx["expected_feedback"].lower()


class TestDEP002:
    """No govulncheck scan claiming safety."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("DEP-002")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "critical"

    def test_violated_rule(self):
        assert "govulncheck" in self.fx["violated_rule"].lower()

    def test_expected_mentions_scan(self):
        assert "govulncheck" in self.fx["expected_feedback"].lower()


class TestDEP003:
    """go.sum integrity failure."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("DEP-003")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "critical"

    def test_violated_rule(self):
        vr = self.fx["violated_rule"].lower()
        assert "integrity" in vr or "go.sum" in vr

    def test_expected_mentions_tamper(self):
        fb = self.fx["expected_feedback"].lower()
        assert "tamper" in fb or "integrity" in fb


# ──────────────────────────────────────────────────────────────────────
# Standard Defects
# ──────────────────────────────────────────────────────────────────────
class TestDEP004:
    """Transitive CVE not reachable."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("DEP-004")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "standard"

    def test_expected_mentions_unreachable(self):
        fb = self.fx["expected_feedback"].lower()
        assert "no reachable path" in fb or "not called" in fb


class TestDEP005:
    """GPL license violation."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("DEP-005")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "standard"

    def test_violated_rule(self):
        assert "license" in self.fx["violated_rule"].lower()

    def test_expected_mentions_gpl(self):
        assert "gpl" in self.fx["expected_feedback"].lower()


class TestDEP006:
    """+incompatible version."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("DEP-006")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "standard"

    def test_violated_rule(self):
        assert "incompatible" in self.fx["violated_rule"].lower()

    def test_expected_mentions_incompatible(self):
        assert "+incompatible" in self.fx["expected_feedback"]


class TestDEP007:
    """go get -u danger."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("DEP-007")

    def test_type_severity(self):
        assert self.fx["type"] == "defect"
        assert self.fx["severity"] == "standard"

    def test_expected_mentions_targeted(self):
        fb = self.fx["expected_feedback"].lower()
        assert "targeted" in fb or "specific" in fb


# ──────────────────────────────────────────────────────────────────────
# Good Practices
# ──────────────────────────────────────────────────────────────────────
class TestDEP008:
    """Clean audit — all checks pass."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("DEP-008")

    def test_type_severity(self):
        assert self.fx["type"] == "good_practice"
        assert self.fx["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fx["expected_feedback"].lower()


class TestDEP009:
    """Well-executed targeted upgrade."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("DEP-009")

    def test_type_severity(self):
        assert self.fx["type"] == "good_practice"
        assert self.fx["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fx["expected_feedback"].lower()

    def test_expected_mentions_targeted(self):
        assert "targeted" in self.fx["expected_feedback"].lower()


# ──────────────────────────────────────────────────────────────────────
# Degradation Scenarios
# ──────────────────────────────────────────────────────────────────────
class TestDEP010:
    """No go.mod found — planning mode."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("DEP-010")

    def test_type_severity(self):
        assert self.fx["type"] == "degradation_scenario"
        assert self.fx["severity"] == "none"

    def test_expected_mentions_gate_1(self):
        fb = self.fx["expected_feedback"].lower()
        assert "gate 1" in fb or "module discovery" in fb

    def test_expected_mentions_degraded(self):
        assert "degraded" in self.fx["expected_feedback"].lower()


class TestDEP011:
    """No govulncheck — partial mode."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("DEP-011")

    def test_type_severity(self):
        assert self.fx["type"] == "degradation_scenario"
        assert self.fx["severity"] == "none"

    def test_expected_forbids_cve_claims(self):
        fb = self.fx["expected_feedback"].lower()
        assert "cannot" in fb or "must not" in fb

    def test_expected_mentions_partial(self):
        fb = self.fx["expected_feedback"].lower()
        assert "partial" in fb or "degraded" in fb


# ──────────────────────────────────────────────────────────────────────
# Workflow Scenarios
# ──────────────────────────────────────────────────────────────────────
class TestDEP012:
    """Full pre-release audit workflow."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("DEP-012")

    def test_type_severity(self):
        assert self.fx["type"] == "workflow"
        assert self.fx["severity"] == "none"

    def test_expected_mentions_scorecard(self):
        fb = self.fx["expected_feedback"].lower()
        assert "scorecard" in fb or "critical" in fb

    def test_expected_mentions_govulncheck(self):
        assert "govulncheck" in self.fx["expected_feedback"].lower()


class TestDEP013:
    """Deep supply chain review workflow."""

    @pytest.fixture(autouse=True)
    def _fx(self):
        self.fx = _load("DEP-013")

    def test_type_severity(self):
        assert self.fx["type"] == "workflow"
        assert self.fx["severity"] == "none"

    def test_expected_mentions_supply_chain(self):
        fb = self.fx["expected_feedback"].lower()
        assert "supply chain" in fb or "goproxy" in fb

    def test_expected_mentions_goprivate(self):
        assert "goprivate" in self.fx["expected_feedback"].lower()
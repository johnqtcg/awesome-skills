"""Golden scenario tests for monitoring-alerting skill."""

import json
import pathlib
import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
REFS_DIR = SKILL_DIR / "references"
GOLDEN_DIR = pathlib.Path(__file__).resolve().parent / "golden"


def _all_docs_lower() -> str:
    parts = [SKILL_MD]
    for f in sorted(REFS_DIR.glob("*.md")):
        parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts).lower()


def _load_fixtures() -> list[dict]:
    return [json.loads(f.read_text(encoding="utf-8"))
            for f in sorted(GOLDEN_DIR.glob("*.json"))]


ALL_DOCS_LOWER = _all_docs_lower()
FIXTURES = _load_fixtures()

VALID_TYPES = {"defect", "good_practice", "degradation_scenario", "workflow"}
VALID_SEVERITIES = {"critical", "standard", "hygiene", "none"}
REQUIRED_FIELDS = {
    "id", "title", "type", "severity", "code_snippet",
    "expected_feedback", "coverage_rules", "reference",
}


class TestFixtureIntegrity:
    def test_minimum_fixture_count(self):
        assert len(FIXTURES) >= 13

    def test_required_fields(self):
        for fix in FIXTURES:
            missing = REQUIRED_FIELDS - set(fix.keys())
            assert not missing, f"{fix['id']}: missing fields {missing}"

    def test_valid_types(self):
        for fix in FIXTURES:
            assert fix["type"] in VALID_TYPES

    def test_valid_severities(self):
        for fix in FIXTURES:
            assert fix["severity"] in VALID_SEVERITIES

    def test_defect_severity_not_none(self):
        for fix in FIXTURES:
            if fix["type"] == "defect":
                assert fix["severity"] != "none"

    def test_non_defect_severity_none(self):
        for fix in FIXTURES:
            if fix["type"] in ("good_practice", "degradation_scenario", "workflow"):
                assert fix["severity"] == "none"

    def test_unique_ids(self):
        ids = [f["id"] for f in FIXTURES]
        assert len(ids) == len(set(ids))

    def test_coverage_rules_findable(self):
        for fix in FIXTURES:
            for rule in fix["coverage_rules"]:
                assert rule.lower() in ALL_DOCS_LOWER, \
                    f"{fix['id']}: coverage rule '{rule}' not found in docs"


# Critical Defects

class TestMON001:
    fix = next(f for f in FIXTURES if f["id"] == "MON-001")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "sli" in self.fix["violated_rule"].lower()

    def test_expected_mentions_sli(self):
        fb = self.fix["expected_feedback"].lower()
        assert "sli" in fb and ("availability" in fb or "latency" in fb)


class TestMON002:
    fix = next(f for f in FIXTURES if f["id"] == "MON-002")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "actionable" in self.fix["violated_rule"].lower()

    def test_expected_mentions_runbook(self):
        fb = self.fix["expected_feedback"].lower()
        assert "runbook" in fb or "action" in fb


class TestMON003:
    fix = next(f for f in FIXTURES if f["id"] == "MON-003")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        vr = self.fix["violated_rule"].lower()
        assert "severity" in vr or "routing" in vr

    def test_expected_mentions_pagerduty(self):
        fb = self.fix["expected_feedback"].lower()
        assert "pagerduty" in fb or "page" in fb


# Standard Defects

class TestMON004:
    fix = next(f for f in FIXTURES if f["id"] == "MON-004")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        vr = self.fix["violated_rule"].lower()
        assert "for" in vr or "flapping" in vr or "duration" in vr

    def test_expected_mentions_for(self):
        assert "for:" in self.fix["expected_feedback"] or "for'" in self.fix["expected_feedback"]


class TestMON005:
    fix = next(f for f in FIXTURES if f["id"] == "MON-005")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        assert "runbook" in self.fix["violated_rule"].lower()

    def test_expected_mentions_runbook_url(self):
        fb = self.fix["expected_feedback"].lower()
        assert "runbook" in fb


class TestMON006:
    fix = next(f for f in FIXTURES if f["id"] == "MON-006")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        assert "cardinality" in self.fix["violated_rule"].lower()

    def test_expected_mentions_user_id(self):
        assert "user_id" in self.fix["expected_feedback"]


class TestMON011:
    fix = next(f for f in FIXTURES if f["id"] == "MON-011")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        vr = self.fix["violated_rule"].lower()
        assert "grouping" in vr or "deduplication" in vr

    def test_expected_mentions_group_by(self):
        fb = self.fix["expected_feedback"].lower()
        assert "group" in fb


# Good Practices

class TestMON007:
    fix = next(f for f in FIXTURES if f["id"] == "MON-007")

    def test_type_severity(self):
        assert self.fix["type"] == "good_practice"
        assert self.fix["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fix["expected_feedback"].lower()

    def test_expected_mentions_burn_rate(self):
        fb = self.fix["expected_feedback"].lower()
        assert "burn" in fb and "rate" in fb


class TestMON008:
    fix = next(f for f in FIXTURES if f["id"] == "MON-008")

    def test_type_severity(self):
        assert self.fix["type"] == "good_practice"
        assert self.fix["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fix["expected_feedback"].lower()

    def test_expected_mentions_red(self):
        assert "RED" in self.fix["expected_feedback"] or "red" in self.fix["expected_feedback"].lower()


# Degradation & Workflow

class TestMON009:
    fix = next(f for f in FIXTURES if f["id"] == "MON-009")

    def test_type_severity(self):
        assert self.fix["type"] == "degradation_scenario"
        assert self.fix["severity"] == "none"

    def test_expected_forbids_claims(self):
        fb = self.fix["expected_feedback"].lower()
        assert "must not" in fb or "not claim" in fb

    def test_expected_mentions_degraded(self):
        assert "degraded" in self.fix["expected_feedback"].lower()


class TestMON010:
    fix = next(f for f in FIXTURES if f["id"] == "MON-010")

    def test_type_severity(self):
        assert self.fix["type"] == "workflow"
        assert self.fix["severity"] == "none"

    def test_expected_mentions_slo(self):
        fb = self.fix["expected_feedback"].lower()
        assert "slo" in fb or "sli" in fb

    def test_expected_mentions_routing(self):
        fb = self.fix["expected_feedback"].lower()
        assert "pagerduty" in fb or "routing" in fb


class TestMON012:
    fix = next(f for f in FIXTURES if f["id"] == "MON-012")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        vr = self.fix["violated_rule"].lower()
        assert "inhibition" in vr or "cascade" in vr

    def test_expected_feedback(self):
        fb = self.fix["expected_feedback"].lower()
        assert "inhibit_rules" in fb or "inhibition" in fb


class TestMON013:
    fix = next(f for f in FIXTURES if f["id"] == "MON-013")

    def test_type_severity(self):
        assert self.fix["type"] == "workflow"
        assert self.fix["severity"] == "none"

    def test_expected_mentions_budget(self):
        fb = self.fix["expected_feedback"].lower()
        assert "error budget" in fb or "budget" in fb

    def test_expected_mentions_decision(self):
        fb = self.fix["expected_feedback"].lower()
        assert "deploy" in fb or "incident-postmortem" in fb or "freeze" in fb or "renegotiate" in fb
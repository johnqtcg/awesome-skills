"""Golden scenario tests for api-design skill."""

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
        assert len(FIXTURES) >= 11

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

class TestAPI001:
    fix = next(f for f in FIXTURES if f["id"] == "API-001")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "naming" in self.fix["violated_rule"].lower()

    def test_expected_mentions_noun(self):
        fb = self.fix["expected_feedback"].lower()
        assert "noun" in fb or "verb" in fb


class TestAPI002:
    fix = next(f for f in FIXTURES if f["id"] == "API-002")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "error" in self.fix["violated_rule"].lower()

    def test_expected_mentions_status_code(self):
        fb = self.fix["expected_feedback"].lower()
        assert "status code" in fb or "200" in fb


class TestAPI003:
    fix = next(f for f in FIXTURES if f["id"] == "API-003")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "error" in self.fix["violated_rule"].lower()

    def test_expected_mentions_code_field(self):
        fb = self.fix["expected_feedback"].lower()
        assert "code" in fb and "machine" in fb


# Standard Defects

class TestAPI004:
    fix = next(f for f in FIXTURES if f["id"] == "API-004")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        assert "idempotency" in self.fix["violated_rule"].lower()

    def test_expected_mentions_retry(self):
        assert "retry" in self.fix["expected_feedback"].lower()


class TestAPI005:
    """API-005: IDOR — Critical per Scorecard (not Standard)."""
    fix = next(f for f in FIXTURES if f["id"] == "API-005")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical", \
            "IDOR is a Critical-tier scorecard item (any FAIL = overall FAIL)"

    def test_violated_rule(self):
        assert "idor" in self.fix["violated_rule"].lower() or "authorization" in self.fix["violated_rule"].lower()

    def test_expected_mentions_idor(self):
        assert "idor" in self.fix["expected_feedback"].lower()


class TestAPI006:
    fix = next(f for f in FIXTURES if f["id"] == "API-006")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        assert "compatibility" in self.fix["violated_rule"].lower()

    def test_expected_mentions_deprecation(self):
        assert "deprecation" in self.fix["expected_feedback"].lower()


class TestAPI011:
    fix = next(f for f in FIXTURES if f["id"] == "API-011")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        assert "rate" in self.fix["violated_rule"].lower()

    def test_expected_mentions_429(self):
        assert "429" in self.fix["expected_feedback"]


# Good Practices

class TestAPI007:
    fix = next(f for f in FIXTURES if f["id"] == "API-007")

    def test_type_severity(self):
        assert self.fix["type"] == "good_practice"
        assert self.fix["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fix["expected_feedback"].lower()

    def test_expected_mentions_key_patterns(self):
        fb = self.fix["expected_feedback"].lower()
        assert "etag" in fb or "idempotency" in fb or "concurrency" in fb


class TestAPI008:
    fix = next(f for f in FIXTURES if f["id"] == "API-008")

    def test_type_severity(self):
        assert self.fix["type"] == "good_practice"
        assert self.fix["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fix["expected_feedback"].lower()

    def test_expected_mentions_cursor(self):
        assert "cursor" in self.fix["expected_feedback"].lower()


# Degradation & Workflow

class TestAPI009:
    fix = next(f for f in FIXTURES if f["id"] == "API-009")

    def test_type_severity(self):
        assert self.fix["type"] == "degradation_scenario"
        assert self.fix["severity"] == "none"

    def test_expected_forbids_claims(self):
        fb = self.fix["expected_feedback"].lower()
        assert "must not" in fb or "not claim" in fb

    def test_expected_mentions_degraded(self):
        assert "degraded" in self.fix["expected_feedback"].lower()


class TestAPI010:
    fix = next(f for f in FIXTURES if f["id"] == "API-010")

    def test_type_severity(self):
        assert self.fix["type"] == "workflow"
        assert self.fix["severity"] == "none"

    def test_expected_mentions_resources(self):
        fb = self.fix["expected_feedback"].lower()
        assert "/orders" in fb or "resource" in fb

    def test_expected_mentions_idempotency(self):
        fb = self.fix["expected_feedback"].lower()
        assert "idempotency" in fb or "idempotent" in fb
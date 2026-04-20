"""Golden scenario tests for kafka-event-driven-design skill."""

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


# ===========================================================================
# Critical Defects
# ===========================================================================

class TestKAFKA001:
    """KAFKA-001: Producer with acks=1."""
    fix = next(f for f in FIXTURES if f["id"] == "KAFKA-001")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "acks" in self.fix["violated_rule"].lower()

    def test_expected_mentions_data_loss(self):
        fb = self.fix["expected_feedback"].lower()
        assert "data loss" in fb or "lost" in fb


class TestKAFKA002:
    """KAFKA-002: Consumer without idempotency."""
    fix = next(f for f in FIXTURES if f["id"] == "KAFKA-002")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "duplicate" in self.fix["violated_rule"].lower() or \
               "idempoten" in self.fix["violated_rule"].lower()

    def test_expected_mentions_rebalance(self):
        fb = self.fix["expected_feedback"].lower()
        assert "rebalance" in fb or "duplicate" in fb


class TestKAFKA003:
    """KAFKA-003: No DLQ."""
    fix = next(f for f in FIXTURES if f["id"] == "KAFKA-003")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        vr = self.fix["violated_rule"].lower()
        assert "dead letter" in vr or "dlq" in vr

    def test_expected_mentions_poison(self):
        assert "poison" in self.fix["expected_feedback"].lower()


# ===========================================================================
# Standard Defects
# ===========================================================================

class TestKAFKA004:
    """KAFKA-004: Null partition key."""
    fix = next(f for f in FIXTURES if f["id"] == "KAFKA-004")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        assert "partition" in self.fix["violated_rule"].lower()

    def test_expected_mentions_ordering(self):
        assert "ordering" in self.fix["expected_feedback"].lower()


class TestKAFKA005:
    """KAFKA-005: Event missing metadata."""
    fix = next(f for f in FIXTURES if f["id"] == "KAFKA-005")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        assert "metadata" in self.fix["violated_rule"].lower() or \
               "schema" in self.fix["violated_rule"].lower()

    def test_expected_mentions_event_id(self):
        assert "event_id" in self.fix["expected_feedback"]


class TestKAFKA006:
    """KAFKA-006: Schema evolution without compatibility."""
    fix = next(f for f in FIXTURES if f["id"] == "KAFKA-006")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        assert "compatibility" in self.fix["violated_rule"].lower() or \
               "schema" in self.fix["violated_rule"].lower()

    def test_expected_mentions_backward(self):
        assert "backward" in self.fix["expected_feedback"].lower()


class TestKAFKA011:
    """KAFKA-011: No consumer lag monitoring."""
    fix = next(f for f in FIXTURES if f["id"] == "KAFKA-011")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        assert "lag" in self.fix["violated_rule"].lower() or \
               "monitoring" in self.fix["violated_rule"].lower()

    def test_expected_mentions_alert(self):
        assert "alert" in self.fix["expected_feedback"].lower()


# ===========================================================================
# Good Practices
# ===========================================================================

class TestKAFKA007:
    """KAFKA-007: Well-formed event design."""
    fix = next(f for f in FIXTURES if f["id"] == "KAFKA-007")

    def test_type_severity(self):
        assert self.fix["type"] == "good_practice"
        assert self.fix["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fix["expected_feedback"].lower()

    def test_expected_mentions_acks(self):
        fb = self.fix["expected_feedback"].lower()
        assert "acks" in fb or "idempotent" in fb


class TestKAFKA008:
    """KAFKA-008: Good outbox pattern."""
    fix = next(f for f in FIXTURES if f["id"] == "KAFKA-008")

    def test_type_severity(self):
        assert self.fix["type"] == "good_practice"
        assert self.fix["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fix["expected_feedback"].lower()

    def test_expected_mentions_outbox(self):
        assert "outbox" in self.fix["expected_feedback"].lower()


# ===========================================================================
# Degradation & Workflow
# ===========================================================================

class TestKAFKA009:
    """KAFKA-009: Degraded mode."""
    fix = next(f for f in FIXTURES if f["id"] == "KAFKA-009")

    def test_type_severity(self):
        assert self.fix["type"] == "degradation_scenario"
        assert self.fix["severity"] == "none"

    def test_expected_forbids_claims(self):
        fb = self.fix["expected_feedback"].lower()
        assert "must not" in fb or "not claim" in fb

    def test_expected_mentions_degraded(self):
        assert "degraded" in self.fix["expected_feedback"].lower()


class TestKAFKA010:
    """KAFKA-010: Greenfield design workflow."""
    fix = next(f for f in FIXTURES if f["id"] == "KAFKA-010")

    def test_type_severity(self):
        assert self.fix["type"] == "workflow"
        assert self.fix["severity"] == "none"

    def test_expected_mentions_partition_key(self):
        fb = self.fix["expected_feedback"].lower()
        assert "partition" in fb and ("key" in fb or "order_id" in fb)

    def test_expected_mentions_dlq(self):
        assert "dlq" in self.fix["expected_feedback"].lower() or \
               "dead letter" in self.fix["expected_feedback"].lower()
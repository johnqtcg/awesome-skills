"""Golden scenario tests for mongo-migration skill.

Validates behavioral coverage: each golden fixture exercises specific
rules in SKILL.md and reference files.
"""

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
    "id", "title", "type", "severity", "migration_snippet",
    "expected_feedback", "coverage_rules", "reference",
}


# ===========================================================================
# Fixture Integrity Tests
# ===========================================================================

class TestFixtureIntegrity:
    def test_minimum_fixture_count(self):
        assert len(FIXTURES) >= 11

    def test_required_fields(self):
        for fix in FIXTURES:
            missing = REQUIRED_FIELDS - set(fix.keys())
            assert not missing, f"{fix['id']}: missing fields {missing}"

    def test_valid_types(self):
        for fix in FIXTURES:
            assert fix["type"] in VALID_TYPES, f"{fix['id']}: invalid type"

    def test_valid_severities(self):
        for fix in FIXTURES:
            assert fix["severity"] in VALID_SEVERITIES, f"{fix['id']}: invalid severity"

    def test_defect_severity_not_none(self):
        for fix in FIXTURES:
            if fix["type"] == "defect":
                assert fix["severity"] != "none", f"{fix['id']}: defect must have severity"

    def test_non_defect_severity_none(self):
        for fix in FIXTURES:
            if fix["type"] in ("good_practice", "degradation_scenario", "workflow"):
                assert fix["severity"] == "none", f"{fix['id']}: non-defect must be none"

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

class TestMONGO001:
    """MONGO-001: Unbounded updateMany."""
    fix = next(f for f in FIXTURES if f["id"] == "MONGO-001")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        vr = self.fix["violated_rule"].lower()
        assert "batch" in vr or "_id" in vr

    def test_expected_mentions_wiredtiger(self):
        assert "wiredtiger" in self.fix["expected_feedback"].lower()


class TestMONGO002:
    """MONGO-002: No explicit write concern."""
    fix = next(f for f in FIXTURES if f["id"] == "MONGO-002")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "write concern" in self.fix["violated_rule"].lower()

    def test_expected_mentions_majority(self):
        assert "majority" in self.fix["expected_feedback"].lower()


class TestMONGO003:
    """MONGO-003: No rollback — in-place type overwrite."""
    fix = next(f for f in FIXTURES if f["id"] == "MONGO-003")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "rollback" in self.fix["violated_rule"].lower()

    def test_expected_mentions_irreversible(self):
        assert "irreversible" in self.fix["expected_feedback"].lower()


# ===========================================================================
# Standard Defects
# ===========================================================================

class TestMONGO004:
    """MONGO-004: Validator strict before backfill."""
    fix = next(f for f in FIXTURES if f["id"] == "MONGO-004")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        vr = self.fix["violated_rule"].lower()
        assert "validator" in vr or "moderate" in vr

    def test_expected_mentions_moderate(self):
        assert "moderate" in self.fix["expected_feedback"].lower()


class TestMONGO005:
    """MONGO-005: Unique index without duplicate check."""
    fix = next(f for f in FIXTURES if f["id"] == "MONGO-005")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        vr = self.fix["violated_rule"].lower()
        assert "unique" in vr or "duplicate" in vr

    def test_expected_mentions_duplicate(self):
        assert "duplicate" in self.fix["expected_feedback"].lower()


class TestMONGO006:
    """MONGO-006: In-place field type change."""
    fix = next(f for f in FIXTURES if f["id"] == "MONGO-006")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        vr = self.fix["violated_rule"].lower()
        assert "type" in vr or "dual" in vr

    def test_expected_mentions_dual(self):
        fb = self.fix["expected_feedback"].lower()
        assert "dual" in fb or "new-field" in fb


class TestMONGO011:
    """MONGO-011: Index build without lag monitoring."""
    fix = next(f for f in FIXTURES if f["id"] == "MONGO-011")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        vr = self.fix["violated_rule"].lower()
        assert "index" in vr or "replication" in vr or "monitor" in vr

    def test_expected_mentions_lag(self):
        fb = self.fix["expected_feedback"].lower()
        assert "replication" in fb or "lag" in fb


class TestMONGO013:
    """MONGO-013: Sharded bulk write without batching or balancer awareness."""
    fix = next(f for f in FIXTURES if f["id"] == "MONGO-013")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_violated_rule(self):
        vr = self.fix["violated_rule"].lower()
        assert "batch" in vr or "_id" in vr

    def test_expected_mentions_shard(self):
        assert "shard" in self.fix["expected_feedback"].lower()

    def test_expected_mentions_balancer(self):
        assert "balancer" in self.fix["expected_feedback"].lower()


# ===========================================================================
# Good Practices
# ===========================================================================

class TestMONGO007:
    """MONGO-007: Well-formed phased migration."""
    fix = next(f for f in FIXTURES if f["id"] == "MONGO-007")

    def test_type_severity(self):
        assert self.fix["type"] == "good_practice"
        assert self.fix["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fix["expected_feedback"].lower()


class TestMONGO008:
    """MONGO-008: Good rolling index build."""
    fix = next(f for f in FIXTURES if f["id"] == "MONGO-008")

    def test_type_severity(self):
        assert self.fix["type"] == "good_practice"
        assert self.fix["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fix["expected_feedback"].lower()

    def test_expected_mentions_rolling(self):
        assert "rolling" in self.fix["expected_feedback"].lower()


# ===========================================================================
# Degradation & Workflow
# ===========================================================================

class TestMONGO009:
    """MONGO-009: Degraded mode."""
    fix = next(f for f in FIXTURES if f["id"] == "MONGO-009")

    def test_type_severity(self):
        assert self.fix["type"] == "degradation_scenario"
        assert self.fix["severity"] == "none"

    def test_expected_forbids_claims(self):
        fb = self.fix["expected_feedback"].lower()
        assert "must not" in fb or "not claim" in fb

    def test_expected_mentions_degraded(self):
        assert "degraded" in self.fix["expected_feedback"].lower()


class TestMONGO010:
    """MONGO-010: Field type migration workflow."""
    fix = next(f for f in FIXTURES if f["id"] == "MONGO-010")

    def test_type_severity(self):
        assert self.fix["type"] == "workflow"
        assert self.fix["severity"] == "none"

    def test_expected_mentions_new_field(self):
        fb = self.fix["expected_feedback"]
        assert "amount_v2" in fb or "new-field" in fb.lower()

    def test_expected_mentions_phases(self):
        fb = self.fix["expected_feedback"].lower()
        assert "phase" in fb or "step" in fb or "(1)" in fb


class TestMONGO012:
    """MONGO-012: reshardCollection workflow."""
    fix = next(f for f in FIXTURES if f["id"] == "MONGO-012")

    def test_type_severity(self):
        assert self.fix["type"] == "workflow"
        assert self.fix["severity"] == "none"

    def test_expected_mentions_reshard(self):
        fb = self.fix["expected_feedback"].lower()
        assert "reshardcollection" in fb or "reshard" in fb

    def test_expected_mentions_cutover(self):
        fb = self.fix["expected_feedback"].lower()
        assert "cutover" in fb or "lock" in fb
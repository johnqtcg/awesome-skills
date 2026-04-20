"""Golden scenario tests for redis-cache-strategy skill."""

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
        assert len(FIXTURES) >= 9

    def test_required_fields(self):
        for fix in FIXTURES:
            missing = REQUIRED_FIELDS - set(fix.keys())
            assert not missing, f"{fix['id']}: missing {missing}"

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
                    f"{fix['id']}: '{rule}' not in docs"


# Critical Defects

class TestCACHE001:
    fix = next(f for f in FIXTURES if f["id"] == "CACHE-001")

    def test_type_severity(self):
        assert self.fix["type"] == "defect" and self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "consistency" in self.fix["violated_rule"].lower()

    def test_expected_mentions_source_of_truth(self):
        assert "source of truth" in self.fix["expected_feedback"].lower()


class TestCACHE002:
    fix = next(f for f in FIXTURES if f["id"] == "CACHE-002")

    def test_type_severity(self):
        assert self.fix["type"] == "defect" and self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "ttl" in self.fix["violated_rule"].lower()

    def test_expected_mentions_jitter(self):
        assert "jitter" in self.fix["expected_feedback"].lower()


class TestCACHE003:
    fix = next(f for f in FIXTURES if f["id"] == "CACHE-003")

    def test_type_severity(self):
        assert self.fix["type"] == "defect" and self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "degradation" in self.fix["violated_rule"].lower()

    def test_expected_mentions_fallback(self):
        fb = self.fix["expected_feedback"].lower()
        assert "database" in fb or "db" in fb or "fall" in fb


# Standard Defects

class TestCACHE004:
    fix = next(f for f in FIXTURES if f["id"] == "CACHE-004")

    def test_type_severity(self):
        assert self.fix["type"] == "defect" and self.fix["severity"] == "standard"

    def test_violated_rule(self):
        assert "stampede" in self.fix["violated_rule"].lower()

    def test_expected_mentions_singleflight(self):
        assert "singleflight" in self.fix["expected_feedback"].lower()


class TestCACHE005:
    fix = next(f for f in FIXTURES if f["id"] == "CACHE-005")

    def test_type_severity(self):
        assert self.fix["type"] == "defect" and self.fix["severity"] == "standard"

    def test_violated_rule(self):
        vr = self.fix["violated_rule"].lower()
        assert "lock" in vr or "ttl" in vr

    def test_expected_mentions_deadlock(self):
        fb = self.fix["expected_feedback"].lower()
        assert "deadlock" in fb or "forever" in fb


class TestCACHE006:
    fix = next(f for f in FIXTURES if f["id"] == "CACHE-006")

    def test_type_severity(self):
        assert self.fix["type"] == "defect" and self.fix["severity"] == "standard"

    def test_violated_rule(self):
        assert "invalidation" in self.fix["violated_rule"].lower()

    def test_expected_mentions_keys(self):
        fb = self.fix["expected_feedback"].lower()
        assert "keys" in fb and ("blocking" in fb or "scan" in fb)


class TestCACHE011:
    fix = next(f for f in FIXTURES if f["id"] == "CACHE-011")

    def test_type_severity(self):
        assert self.fix["type"] == "defect" and self.fix["severity"] == "standard"

    def test_violated_rule(self):
        assert "penetration" in self.fix["violated_rule"].lower()

    def test_expected_mentions_null_caching(self):
        fb = self.fix["expected_feedback"].lower()
        assert "null" in fb or "not-found" in fb


class TestCACHE012:
    fix = next(f for f in FIXTURES if f["id"] == "CACHE-012")

    def test_type_severity(self):
        assert self.fix["type"] == "defect" and self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "pattern" in self.fix["violated_rule"].lower()

    def test_expected_mentions_write_behind(self):
        fb = self.fix["expected_feedback"].lower()
        assert "write-behind" in fb and ("financial" in fb or "data loss" in fb)


class TestCACHE013:
    fix = next(f for f in FIXTURES if f["id"] == "CACHE-013")

    def test_type_severity(self):
        assert self.fix["type"] == "defect" and self.fix["severity"] == "standard"

    def test_violated_rule(self):
        assert "avalanche" in self.fix["violated_rule"].lower()

    def test_expected_mentions_l1(self):
        fb = self.fix["expected_feedback"].lower()
        assert "l1" in fb or "in-process" in fb or "local cache" in fb


class TestCACHE014:
    fix = next(f for f in FIXTURES if f["id"] == "CACHE-014")

    def test_type_severity(self):
        assert self.fix["type"] == "defect" and self.fix["severity"] == "critical"

    def test_violated_rule(self):
        vr = self.fix["violated_rule"].lower()
        assert "key naming" in vr or "namespace" in vr

    def test_expected_mentions_tenant(self):
        fb = self.fix["expected_feedback"].lower()
        assert "tenant" in fb and ("segmentation" in fb or "namespace" in fb or "prefix" in fb)


# Good Practices

class TestCACHE007:
    fix = next(f for f in FIXTURES if f["id"] == "CACHE-007")

    def test_type_severity(self):
        assert self.fix["type"] == "good_practice" and self.fix["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fix["expected_feedback"].lower()

    def test_expected_mentions_singleflight(self):
        assert "singleflight" in self.fix["expected_feedback"].lower()


class TestCACHE008:
    fix = next(f for f in FIXTURES if f["id"] == "CACHE-008")

    def test_type_severity(self):
        assert self.fix["type"] == "good_practice" and self.fix["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fix["expected_feedback"].lower()

    def test_expected_mentions_write_through(self):
        assert "write-through" in self.fix["expected_feedback"].lower()


# Degradation & Workflow

class TestCACHE009:
    fix = next(f for f in FIXTURES if f["id"] == "CACHE-009")

    def test_type_severity(self):
        assert self.fix["type"] == "degradation_scenario" and self.fix["severity"] == "none"

    def test_expected_forbids_claims(self):
        fb = self.fix["expected_feedback"].lower()
        assert "must not" in fb or "not claim" in fb

    def test_expected_mentions_degraded(self):
        assert "degraded" in self.fix["expected_feedback"].lower()


class TestCACHE010:
    fix = next(f for f in FIXTURES if f["id"] == "CACHE-010")

    def test_type_severity(self):
        assert self.fix["type"] == "workflow" and self.fix["severity"] == "none"

    def test_expected_mentions_pattern(self):
        fb = self.fix["expected_feedback"].lower()
        assert "cache-aside" in fb

    def test_expected_mentions_warmup(self):
        fb = self.fix["expected_feedback"].lower()
        assert "warmup" in fb or "warm" in fb
"""Golden scenario tests for oracle-migration skill."""

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


class TestORA001:
    fix = next(f for f in FIXTURES if f["id"] == "ORA-001")

    def test_type_severity(self):
        assert self.fix["type"] == "defect" and self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "ddl_lock_timeout" in self.fix["violated_rule"].lower()

    def test_expected_mentions_ora(self):
        assert "ora-00054" in self.fix["expected_feedback"].lower()


class TestORA002:
    fix = next(f for f in FIXTURES if f["id"] == "ORA-002")

    def test_type_severity(self):
        assert self.fix["type"] == "defect" and self.fix["severity"] == "critical"

    def test_violated_rule(self):
        vr = self.fix["violated_rule"].lower()
        assert "novalidate" in vr or "constraint" in vr, \
            f"violated_rule should reference NOVALIDATE constraint pattern, got: {vr}"

    def test_expected_mentions_novalidate(self):
        assert "novalidate" in self.fix["expected_feedback"].lower()

    def test_expected_mentions_two_step(self):
        fb = self.fix["expected_feedback"].lower()
        assert "two-step" in fb or "validate" in fb


class TestORA003:
    fix = next(f for f in FIXTURES if f["id"] == "ORA-003")

    def test_type_severity(self):
        assert self.fix["type"] == "defect" and self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "rollback" in self.fix["violated_rule"].lower()

    def test_expected_mentions_autocommit(self):
        fb = self.fix["expected_feedback"].lower()
        assert "auto-commit" in fb or "auto commit" in fb or "implicit commit" in fb


class TestORA004:
    fix = next(f for f in FIXTURES if f["id"] == "ORA-004")

    def test_type_severity(self):
        assert self.fix["type"] == "defect" and self.fix["severity"] == "critical"

    def test_violated_rule(self):
        vr = self.fix["violated_rule"].lower()
        assert "dbms_redefinition" in vr or "ctas" in vr or "restructuring" in vr, \
            f"violated_rule should reference large-table restructuring, got: {vr}"

    def test_expected_mentions_online(self):
        assert "online" in self.fix["expected_feedback"].lower()

    def test_expected_mentions_unusable(self):
        assert "unusable" in self.fix["expected_feedback"].lower()


class TestORA005:
    fix = next(f for f in FIXTURES if f["id"] == "ORA-005")

    def test_type_severity(self):
        assert self.fix["type"] == "defect" and self.fix["severity"] == "standard"

    def test_expected_mentions_update_indexes(self):
        assert "update indexes" in self.fix["expected_feedback"].lower()

    def test_expected_mentions_unusable(self):
        assert "unusable" in self.fix["expected_feedback"].lower()


class TestORA006:
    fix = next(f for f in FIXTURES if f["id"] == "ORA-006")

    def test_type_severity(self):
        assert self.fix["type"] == "defect" and self.fix["severity"] == "standard"

    def test_expected_mentions_batch(self):
        fb = self.fix["expected_feedback"].lower()
        assert "batch" in fb or "rowid" in fb


class TestORA007:
    fix = next(f for f in FIXTURES if f["id"] == "ORA-007")

    def test_type_severity(self):
        assert self.fix["type"] == "good_practice" and self.fix["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fix["expected_feedback"].lower()


class TestORA008:
    fix = next(f for f in FIXTURES if f["id"] == "ORA-008")

    def test_type_severity(self):
        assert self.fix["type"] == "good_practice" and self.fix["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fix["expected_feedback"].lower()

    def test_expected_mentions_redef(self):
        assert "dbms_redefinition" in self.fix["expected_feedback"].lower()


class TestORA009:
    fix = next(f for f in FIXTURES if f["id"] == "ORA-009")

    def test_type_severity(self):
        assert self.fix["type"] == "degradation_scenario" and self.fix["severity"] == "none"

    def test_expected_forbids_claims(self):
        fb = self.fix["expected_feedback"].lower()
        assert "must not" in fb or "not claim" in fb

    def test_expected_mentions_degraded(self):
        assert "degraded" in self.fix["expected_feedback"].lower()


class TestORA010:
    fix = next(f for f in FIXTURES if f["id"] == "ORA-010")

    def test_type_severity(self):
        assert self.fix["type"] == "workflow" and self.fix["severity"] == "none"

    def test_expected_mentions_redef(self):
        assert "dbms_redefinition" in self.fix["expected_feedback"].lower()

    def test_expected_mentions_phases(self):
        fb = self.fix["expected_feedback"].lower()
        assert "phase" in fb or "step" in fb


class TestORA011:
    fix = next(f for f in FIXTURES if f["id"] == "ORA-011")

    def test_type_severity(self):
        assert self.fix["type"] == "defect" and self.fix["severity"] == "standard"

    def test_expected_mentions_redef(self):
        assert "dbms_redefinition" in self.fix["expected_feedback"].lower()

    def test_expected_mentions_rewrite(self):
        assert "rewrite" in self.fix["expected_feedback"].lower()
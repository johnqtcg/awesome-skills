"""Golden scenario tests for pg-migration skill.

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
    fixtures = []
    for f in sorted(GOLDEN_DIR.glob("*.json")):
        fixtures.append(json.loads(f.read_text(encoding="utf-8")))
    return fixtures


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
        assert len(FIXTURES) >= 9

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

class TestPG001:
    """PG-001: Missing lock_timeout."""
    fix = next(f for f in FIXTURES if f["id"] == "PG-001")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "lock_timeout" in self.fix["violated_rule"].lower()

    def test_expected_mentions_timeout(self):
        assert "lock_timeout" in self.fix["expected_feedback"].lower()


class TestPG002:
    """PG-002: Index without CONCURRENTLY."""
    fix = next(f for f in FIXTURES if f["id"] == "PG-002")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "concurrently" in self.fix["violated_rule"].lower()

    def test_expected_mentions_concurrently(self):
        assert "concurrently" in self.fix["expected_feedback"].lower()


class TestPG003:
    """PG-003: Constraint without NOT VALID."""
    fix = next(f for f in FIXTURES if f["id"] == "PG-003")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_expected_mentions_not_valid(self):
        fb = self.fix["expected_feedback"].lower()
        assert "not valid" in fb

    def test_expected_mentions_two_step(self):
        fb = self.fix["expected_feedback"].lower()
        assert "two-step" in fb or "validate" in fb


class TestPG004:
    """PG-004: Missing rollback plan."""
    fix = next(f for f in FIXTURES if f["id"] == "PG-004")

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

class TestPG005:
    """PG-005: ALTER COLUMN TYPE on large table."""
    fix = next(f for f in FIXTURES if f["id"] == "PG-005")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_expected_mentions_rewrite(self):
        fb = self.fix["expected_feedback"].lower()
        assert "rewrite" in fb

    def test_expected_mentions_pg_repack(self):
        fb = self.fix["expected_feedback"].lower()
        assert "pg_repack" in fb or "create-swap" in fb


class TestPG006:
    """PG-006: ADD CONSTRAINT IF NOT EXISTS syntax."""
    fix = next(f for f in FIXTURES if f["id"] == "PG-006")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_expected_mentions_syntax_error(self):
        fb = self.fix["expected_feedback"].lower()
        assert "syntax" in fb or "not support" in fb

    def test_expected_suggests_do_block(self):
        fb = self.fix["expected_feedback"].lower()
        assert "do block" in fb or "pg_constraint" in fb


class TestPG011:
    """PG-011: NOT NULL without CHECK shortcut."""
    fix = next(f for f in FIXTURES if f["id"] == "PG-011")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_expected_mentions_check(self):
        fb = self.fix["expected_feedback"].lower()
        assert "check" in fb

    def test_expected_mentions_not_valid(self):
        fb = self.fix["expected_feedback"].lower()
        assert "not valid" in fb


# ===========================================================================
# Good Practices
# ===========================================================================

class TestPG007:
    """PG-007: Well-formed phased migration."""
    fix = next(f for f in FIXTURES if f["id"] == "PG-007")

    def test_type_severity(self):
        assert self.fix["type"] == "good_practice"
        assert self.fix["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fix["expected_feedback"].lower()


class TestPG008:
    """PG-008: Good CONCURRENTLY usage."""
    fix = next(f for f in FIXTURES if f["id"] == "PG-008")

    def test_type_severity(self):
        assert self.fix["type"] == "good_practice"
        assert self.fix["severity"] == "none"

    def test_expected_positive(self):
        assert "no violation" in self.fix["expected_feedback"].lower()

    def test_expected_mentions_concurrently(self):
        assert "concurrently" in self.fix["expected_feedback"].lower()


# ===========================================================================
# Degradation & Workflow
# ===========================================================================

class TestPG009:
    """PG-009: Degraded mode."""
    fix = next(f for f in FIXTURES if f["id"] == "PG-009")

    def test_type_severity(self):
        assert self.fix["type"] == "degradation_scenario"
        assert self.fix["severity"] == "none"

    def test_expected_forbids_claims(self):
        fb = self.fix["expected_feedback"].lower()
        assert "must not" in fb or "not claim" in fb

    def test_expected_mentions_degraded(self):
        assert "degraded" in self.fix["expected_feedback"].lower()


class TestPG010:
    """PG-010: Multi-step workflow."""
    fix = next(f for f in FIXTURES if f["id"] == "PG-010")

    def test_type_severity(self):
        assert self.fix["type"] == "workflow"
        assert self.fix["severity"] == "none"

    def test_expected_mentions_phases(self):
        fb = self.fix["expected_feedback"].lower()
        assert "phase" in fb or "step" in fb

    def test_expected_mentions_backfill(self):
        fb = self.fix["expected_feedback"].lower()
        assert "backfill" in fb
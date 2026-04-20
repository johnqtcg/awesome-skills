"""Golden scenario tests for mysql-migration skill.

Validates behavioral coverage: each golden fixture exercises specific
rules in SKILL.md and reference files. Tests verify fixture integrity
(schema, type/severity constraints) and rule coverage (every
coverage_rule phrase is findable in the combined documentation).
"""

import json
import pathlib
import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
REFS_DIR = SKILL_DIR / "references"
GOLDEN_DIR = pathlib.Path(__file__).resolve().parent / "golden"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _all_docs_lower() -> str:
    """Concatenate SKILL.md + all references, lowercased for matching."""
    parts = [SKILL_MD]
    for f in sorted(REFS_DIR.glob("*.md")):
        parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts).lower()


def _load_fixtures() -> list[dict]:
    """Load all golden fixture JSON files, sorted by filename."""
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
    """Meta-level validation on all fixtures."""

    def test_minimum_fixture_count(self):
        assert len(FIXTURES) >= 9, f"Expected ≥9 fixtures, found {len(FIXTURES)}"

    def test_required_fields(self):
        for fix in FIXTURES:
            missing = REQUIRED_FIELDS - set(fix.keys())
            assert not missing, f"{fix['id']}: missing fields {missing}"

    def test_valid_types(self):
        for fix in FIXTURES:
            assert fix["type"] in VALID_TYPES, \
                f"{fix['id']}: invalid type '{fix['type']}'"

    def test_valid_severities(self):
        for fix in FIXTURES:
            assert fix["severity"] in VALID_SEVERITIES, \
                f"{fix['id']}: invalid severity '{fix['severity']}'"

    def test_defect_severity_not_none(self):
        for fix in FIXTURES:
            if fix["type"] == "defect":
                assert fix["severity"] != "none", \
                    f"{fix['id']}: defect must have non-none severity"

    def test_non_defect_severity_none(self):
        for fix in FIXTURES:
            if fix["type"] in ("good_practice", "degradation_scenario", "workflow"):
                assert fix["severity"] == "none", \
                    f"{fix['id']}: {fix['type']} must have severity=none"

    def test_unique_ids(self):
        ids = [f["id"] for f in FIXTURES]
        assert len(ids) == len(set(ids)), f"duplicate IDs: {ids}"

    def test_coverage_rules_findable(self):
        """Every coverage_rule phrase must be findable in combined docs."""
        for fix in FIXTURES:
            for rule in fix["coverage_rules"]:
                assert rule.lower() in ALL_DOCS_LOWER, \
                    f"{fix['id']}: coverage rule '{rule}' not found in docs"


# ===========================================================================
# Per-Fixture Behavioral Tests: Critical Defects
# ===========================================================================

class TestMIG001:
    """MIG-001: Missing session guards."""
    fix = next(f for f in FIXTURES if f["id"] == "MIG-001")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "session guard" in self.fix["violated_rule"].lower() or \
               "session" in self.fix["violated_rule"].lower()

    def test_expected_mentions_guards(self):
        fb = self.fix["expected_feedback"].lower()
        assert "lock_wait_timeout" in fb


class TestMIG002:
    """MIG-002: Implicit algorithm."""
    fix = next(f for f in FIXTURES if f["id"] == "MIG-002")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "algorithm" in self.fix["violated_rule"].lower()

    def test_expected_mentions_instant(self):
        fb = self.fix["expected_feedback"].lower()
        assert "instant" in fb or "algorithm" in fb


class TestMIG003:
    """MIG-003: NOT NULL without phased approach."""
    fix = next(f for f in FIXTURES if f["id"] == "MIG-003")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_expected_mentions_phased(self):
        fb = self.fix["expected_feedback"].lower()
        assert "phased" in fb or "phase" in fb


class TestMIG004:
    """MIG-004: Missing rollback plan."""
    fix = next(f for f in FIXTURES if f["id"] == "MIG-004")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "critical"

    def test_violated_rule(self):
        assert "rollback" in self.fix["violated_rule"].lower()

    def test_expected_mentions_irreversible(self):
        fb = self.fix["expected_feedback"].lower()
        assert "irreversible" in fb


# ===========================================================================
# Per-Fixture Behavioral Tests: Standard Defects
# ===========================================================================

class TestMIG005:
    """MIG-005: INSTANT on MySQL 5.7."""
    fix = next(f for f in FIXTURES if f["id"] == "MIG-005")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_expected_mentions_57(self):
        fb = self.fix["expected_feedback"].lower()
        assert "5.7" in fb

    def test_expected_suggests_inplace(self):
        fb = self.fix["expected_feedback"].lower()
        assert "inplace" in fb


class TestMIG006:
    """MIG-006: LIMIT/OFFSET backfill."""
    fix = next(f for f in FIXTURES if f["id"] == "MIG-006")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_expected_mentions_pk_range(self):
        fb = self.fix["expected_feedback"].lower()
        assert "pk" in fb or "primary key" in fb


class TestMIG011:
    """MIG-011: VARCHAR boundary cross."""
    fix = next(f for f in FIXTURES if f["id"] == "MIG-011")

    def test_type_severity(self):
        assert self.fix["type"] == "defect"
        assert self.fix["severity"] == "standard"

    def test_expected_mentions_boundary(self):
        fb = self.fix["expected_feedback"].lower()
        assert "255" in fb or "boundary" in fb

    def test_expected_mentions_utf8mb4(self):
        fb = self.fix["expected_feedback"].lower()
        assert "utf8mb4" in fb


# ===========================================================================
# Per-Fixture Behavioral Tests: Good Practices
# ===========================================================================

class TestMIG007:
    """MIG-007: Well-formed phased migration."""
    fix = next(f for f in FIXTURES if f["id"] == "MIG-007")

    def test_type_severity(self):
        assert self.fix["type"] == "good_practice"
        assert self.fix["severity"] == "none"

    def test_expected_positive(self):
        fb = self.fix["expected_feedback"].lower()
        assert "no violation" in fb


class TestMIG008:
    """MIG-008: Good gh-ost invocation."""
    fix = next(f for f in FIXTURES if f["id"] == "MIG-008")

    def test_type_severity(self):
        assert self.fix["type"] == "good_practice"
        assert self.fix["severity"] == "none"

    def test_expected_positive(self):
        fb = self.fix["expected_feedback"].lower()
        assert "no violation" in fb

    def test_expected_mentions_tool(self):
        fb = self.fix["expected_feedback"].lower()
        assert "gh-ost" in fb


# ===========================================================================
# Per-Fixture Behavioral Tests: Degradation & Workflow
# ===========================================================================

class TestMIG009:
    """MIG-009: Degraded mode — missing context."""
    fix = next(f for f in FIXTURES if f["id"] == "MIG-009")

    def test_type_severity(self):
        assert self.fix["type"] == "degradation_scenario"
        assert self.fix["severity"] == "none"

    def test_expected_forbids_claims(self):
        fb = self.fix["expected_feedback"].lower()
        assert "must not" in fb or "not claim" in fb

    def test_expected_mentions_degraded(self):
        fb = self.fix["expected_feedback"].lower()
        assert "degraded" in fb


class TestMIG010:
    """MIG-010: Multi-step column rename workflow."""
    fix = next(f for f in FIXTURES if f["id"] == "MIG-010")

    def test_type_severity(self):
        assert self.fix["type"] == "workflow"
        assert self.fix["severity"] == "none"

    def test_expected_mentions_phases(self):
        fb = self.fix["expected_feedback"].lower()
        assert "phase" in fb or "step" in fb

    def test_expected_mentions_dual_write(self):
        fb = self.fix["expected_feedback"].lower()
        assert "dual" in fb or "both column" in fb
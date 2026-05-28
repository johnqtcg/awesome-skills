"""Golden scenario tests for log-analyzer skill.

Each fixture in golden/ describes a real-shaped log analysis situation. The
test asserts that SKILL.md and the reference set together contain enough
guidance to handle the situation — not that an LLM, when given the skill,
will produce the exact expected output, which is a model-evaluation concern
captured in evaluate/log-analyzer-skill-eval-report.md.

Coverage taxonomy:
    type     ∈ {defect, good_practice, degradation_scenario, workflow}
    severity ∈ {critical, standard, hygiene, none}
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
    "id", "title", "type", "severity", "scenario",
    "expected_finding", "coverage_rules", "reference",
}


def _all_docs_lower() -> str:
    parts = [(SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")]
    for f in sorted(REFS_DIR.glob("*.md")):
        parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts).lower()


def _load_fixtures() -> list[dict]:
    return [json.loads(f.read_text(encoding="utf-8"))
            for f in sorted(GOLDEN_DIR.glob("*.json"))]


ALL_DOCS = _all_docs_lower()
FIXTURES = _load_fixtures()


# ──────────────────────────────────────────────────────────────────────
class TestFixtureIntegrity:

    def test_minimum_count(self):
        assert len(FIXTURES) >= 12, f"expected ≥12 golden fixtures, found {len(FIXTURES)}"

    def test_unique_ids(self):
        ids = [f["id"] for f in FIXTURES]
        assert len(ids) == len(set(ids)), "duplicate fixture IDs"

    @pytest.mark.parametrize("fx", FIXTURES, ids=lambda f: f["id"])
    def test_required_fields(self, fx):
        missing = REQUIRED_FIELDS - set(fx.keys())
        assert not missing, f"{fx['id']} missing fields: {missing}"

    @pytest.mark.parametrize("fx", FIXTURES, ids=lambda f: f["id"])
    def test_valid_type(self, fx):
        assert fx["type"] in VALID_TYPES, f"{fx['id']} bad type: {fx['type']}"

    @pytest.mark.parametrize("fx", FIXTURES, ids=lambda f: f["id"])
    def test_valid_severity(self, fx):
        assert fx["severity"] in VALID_SEVERITIES, f"{fx['id']} bad severity: {fx['severity']}"

    @pytest.mark.parametrize("fx", FIXTURES, ids=lambda f: f["id"])
    def test_reference_file_exists(self, fx):
        ref_path = SKILL_DIR / fx["reference"]
        assert ref_path.exists(), f"{fx['id']} references missing file: {fx['reference']}"


# ──────────────────────────────────────────────────────────────────────
class TestCoverageRulesPresent:
    """For every fixture, every coverage_rule string must appear (case-insensitive)
    somewhere in SKILL.md or one of the reference files. This proves the skill's
    knowledge surface actually addresses the scenario."""

    @pytest.mark.parametrize("fx", FIXTURES, ids=lambda f: f["id"])
    def test_each_rule_is_documented(self, fx):
        for rule in fx["coverage_rules"]:
            assert rule.lower() in ALL_DOCS, \
                f"{fx['id']}: coverage_rule not present in skill docs: {rule!r}"


# ──────────────────────────────────────────────────────────────────────
class TestCoverageBreadth:
    """Make sure the fixture set covers the major dimensions the skill claims to handle."""

    @pytest.fixture(autouse=True)
    def _index(self):
        self.by_id = {f["id"]: f for f in FIXTURES}
        self.titles_lower = " ".join(f["title"].lower() for f in FIXTURES)

    def test_covers_first_error_trap(self):
        assert "first" in self.titles_lower and (
            "root cause" in self.titles_lower or "cause" in self.titles_lower
        ), "fixture set must include a first-error vs root-cause scenario"

    def test_covers_pii_redaction(self):
        assert "pii" in self.titles_lower or "redact" in self.titles_lower or \
               "secret" in self.titles_lower, \
               "fixture set must include a PII / secret redaction scenario"

    def test_covers_cascade(self):
        assert "cascade" in self.titles_lower or "cluster" in self.titles_lower, \
            "fixture set must include a cascade / cluster scenario"

    def test_covers_correlation(self):
        assert "trace" in self.titles_lower or "correlation" in self.titles_lower, \
            "fixture set must include a correlation scenario"

    def test_covers_statistical(self):
        assert ("base rate" in self.titles_lower
                or "spike" in self.titles_lower
                or "denominator" in self.titles_lower
                or "noise" in self.titles_lower
                or "background noise" in self.titles_lower), \
            "fixture set must include a statistical / base-rate scenario"

    def test_covers_format_detection(self):
        assert ("json" in self.titles_lower
                or "format" in self.titles_lower
                or "stack trace" in self.titles_lower
                or "multi-line" in self.titles_lower), \
            "fixture set must include a format / multi-line scenario"

    def test_covers_no_finding_case(self):
        nones = [f for f in FIXTURES if f["severity"] == "none"]
        assert nones, "fixture set must include at least one no-finding/healthy scenario"

    def test_covers_handoff_workflow(self):
        wfs = [f for f in FIXTURES if f["type"] == "workflow"]
        assert wfs, "fixture set must include at least one workflow / hand-off scenario"

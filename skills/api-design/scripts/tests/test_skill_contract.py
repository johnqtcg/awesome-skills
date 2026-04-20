"""Contract tests for api-design skill."""

import pathlib
import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
REFS_DIR = SKILL_DIR / "references"


def _ref(name: str) -> str:
    return (REFS_DIR / name).read_text(encoding="utf-8")


class TestFrontmatter:
    def test_name(self):
        assert "name: api-design" in SKILL_MD

    def test_description_keywords(self):
        desc = SKILL_MD[:800].lower()
        for kw in ["rest", "endpoint", "status code", "error model", "idempotency",
                    "pagination", "idor", "openapi"]:
            assert kw in desc, f"description missing keyword: {kw}"


class TestMandatoryGates:
    def test_gate_1_context(self):
        assert "Gate 1" in SKILL_MD
        lower = SKILL_MD.lower()
        assert "consumer" in lower
        assert "public" in lower and "internal" in lower

    def test_gate_1_stop_proceed(self):
        assert "**STOP**" in SKILL_MD
        assert "**PROCEED**" in SKILL_MD

    def test_gate_2_scope(self):
        assert "Gate 2" in SKILL_MD
        for mode in ["review", "design", "governance"]:
            assert mode in SKILL_MD.lower()

    def test_gate_3_risk(self):
        assert "Gate 3" in SKILL_MD
        for risk in ["SAFE", "WARN", "UNSAFE"]:
            assert risk in SKILL_MD

    def test_gate_4_completeness(self):
        assert "Gate 4" in SKILL_MD

    def test_all_gates_have_stop(self):
        assert SKILL_MD.count("**STOP**") >= 3


class TestDepthSelection:
    def test_three_depths(self):
        for depth in ["Lite", "Standard", "Deep"]:
            assert depth in SKILL_MD

    def test_force_standard_signals(self):
        lower = SKILL_MD.lower()
        for signal in ["pagination", "idempotency", "breaking change"]:
            assert signal in lower, f"missing signal: {signal}"

    def test_reference_loading_by_depth(self):
        assert "error-model-patterns.md" in SKILL_MD
        assert "compatibility-rules.md" in SKILL_MD


class TestDegradationModes:
    def test_four_modes_defined(self):
        for mode in ["Full", "Degraded", "Minimal", "Planning"]:
            assert mode in SKILL_MD

    def test_never_fabricate(self):
        lower = SKILL_MD.lower()
        assert "never" in lower and ("claim" in lower or "guess" in lower)

    def test_assumptions_documented(self):
        assert "8.9" in SKILL_MD


class TestDesignChecklist:
    def test_subsection_count(self):
        for sub in ["5.1", "5.2", "5.3", "5.4"]:
            assert sub in SKILL_MD

    def test_resource_naming(self):
        lower = SKILL_MD.lower()
        assert "plural" in lower and "noun" in lower

    def test_status_codes(self):
        for code in ["201", "204", "400", "401", "403", "404", "409", "422", "429"]:
            assert code in SKILL_MD

    def test_error_model(self):
        assert "machine-parseable" in SKILL_MD.lower() or "machine-parsable" in SKILL_MD.lower()

    def test_idempotency(self):
        assert "Idempotency-Key" in SKILL_MD

    def test_idempotency_scoped(self):
        lower = SKILL_MD.lower()
        assert "scope" in lower or "fingerprint" in lower

    def test_idor(self):
        assert "IDOR" in SKILL_MD

    def test_pagination(self):
        assert "cursor" in SKILL_MD.lower()
        assert "offset" in SKILL_MD.lower()

    def test_stable_sort(self):
        lower = SKILL_MD.lower()
        assert "stable sort" in lower or "tie-breaker" in lower

    def test_observability_fields(self):
        lower = SKILL_MD.lower()
        assert "metric" in lower and "audit" in lower

    def test_health_check(self):
        lower = SKILL_MD.lower()
        assert "healthz" in lower or "health check" in lower

    def test_middleware_ordering(self):
        lower = SKILL_MD.lower()
        assert "middleware" in lower and "order" in lower


class TestAntiExamples:
    def test_min_count(self):
        ae_count = sum(1 for l in SKILL_MD.split("\n") if l.strip().startswith("### AE-"))
        assert ae_count >= 6

    def test_wrong_right_pairs(self):
        assert SKILL_MD.count("WRONG") >= 5
        assert SKILL_MD.count("RIGHT") >= 5

    def test_verb_anti_example(self):
        assert "createUser" in SKILL_MD or "create" in SKILL_MD.lower()

    def test_extended_ref(self):
        assert "api-anti-examples.md" in SKILL_MD


class TestScorecard:
    def test_critical_tier(self):
        lower = SKILL_MD.lower()
        assert "critical" in lower
        assert "any fail" in lower

    def test_standard_tier(self):
        assert "4 of 5" in SKILL_MD or "4/5" in SKILL_MD

    def test_hygiene_tier(self):
        assert "3 of 4" in SKILL_MD or "3/4" in SKILL_MD

    def test_critical_items(self):
        lower = SKILL_MD.lower()
        assert "resource naming" in lower
        assert "error model" in lower
        assert "idor" in lower

    def test_verdict_format(self):
        assert "X/12" in SKILL_MD or "PASS/FAIL" in SKILL_MD


class TestOutputContract:
    def test_nine_sections(self):
        for section in ["8.1", "8.2", "8.3", "8.4", "8.5", "8.6", "8.7", "8.8", "8.9"]:
            assert section in SKILL_MD

    def test_uncovered_risks_mandatory(self):
        lower = SKILL_MD.lower()
        assert "never empty" in lower or "mandatory" in lower

    def test_volume_rules(self):
        assert "volume" in SKILL_MD.lower()

    def test_scorecard_in_output(self):
        lower = SKILL_MD.lower()
        assert "scorecard" in lower and "data basis" in lower


class TestReferenceFiles:
    def test_error_model_exists(self):
        content = _ref("error-model-patterns.md")
        assert len(content.splitlines()) >= 80

    def test_error_model_keywords(self):
        content = _ref("error-model-patterns.md").lower()
        for kw in ["validation_error", "not_found", "trace_id", "idempotency"]:
            assert kw in content

    def test_compatibility_exists(self):
        content = _ref("compatibility-rules.md")
        assert len(content.splitlines()) >= 80

    def test_compatibility_keywords(self):
        content = _ref("compatibility-rules.md").lower()
        for kw in ["breaking", "non-breaking", "deprecation", "sunset"]:
            assert kw in content

    def test_anti_examples_exists(self):
        content = _ref("api-anti-examples.md")
        assert len(content.splitlines()) >= 80

    def test_anti_examples_numbering(self):
        content = _ref("api-anti-examples.md")
        assert "AE-7" in content
        ae_count = sum(1 for l in content.split("\n") if "## AE-" in l)
        assert ae_count >= 5

    def test_all_refs_mentioned_in_skill(self):
        for f in REFS_DIR.glob("*.md"):
            assert f.name in SKILL_MD, f"{f.name} not in SKILL.md"


class TestLineCount:
    def test_max_lines(self):
        lines = len(SKILL_MD.splitlines())
        assert lines <= 420, f"SKILL.md is {lines} lines (budget: 420)"


class TestCrossFileConsistency:
    def test_validation_error_in_error_model(self):
        assert "validation_error" in _ref("error-model-patterns.md")

    def test_breaking_in_compatibility(self):
        assert "breaking" in _ref("compatibility-rules.md").lower()

    def test_sunset_in_compatibility(self):
        assert "Sunset" in _ref("compatibility-rules.md")

    def test_idor_in_skill(self):
        assert "IDOR" in SKILL_MD

    def test_etag_in_error_model(self):
        assert "ETag" in _ref("error-model-patterns.md") or "etag" in _ref("error-model-patterns.md").lower()

    def test_403_404_in_anti_examples(self):
        content = _ref("api-anti-examples.md")
        assert "403" in content and "404" in content

    def test_observability_in_error_model(self):
        content = _ref("error-model-patterns.md").lower()
        assert "metric" in content and "audit" in content

    def test_contract_testing_in_compatibility(self):
        content = _ref("compatibility-rules.md").lower()
        assert "contract" in content and "baseline" in content

    def test_multi_version_in_compatibility(self):
        content = _ref("compatibility-rules.md")
        assert "v1" in content and "v2" in content and "410" in content
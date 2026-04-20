"""Contract tests for monitoring-alerting skill."""

import pathlib
import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
REFS_DIR = SKILL_DIR / "references"


def _ref(name: str) -> str:
    return (REFS_DIR / name).read_text(encoding="utf-8")


class TestFrontmatter:
    def test_name(self):
        assert "name: monitoring-alerting" in SKILL_MD

    def test_description_keywords(self):
        desc = SKILL_MD[:800].lower()
        for kw in ["prometheus", "grafana", "sli", "slo", "alert", "burn-rate",
                    "pagerduty", "cardinality"]:
            assert kw in desc, f"description missing keyword: {kw}"


class TestMandatoryGates:
    def test_gate_1_context(self):
        assert "Gate 1" in SKILL_MD
        lower = SKILL_MD.lower()
        assert "service type" in lower
        assert "traffic pattern" in lower

    def test_gate_1_stop_proceed(self):
        assert "**STOP**" in SKILL_MD
        assert "**PROCEED**" in SKILL_MD

    def test_gate_2_scope(self):
        assert "Gate 2" in SKILL_MD
        for mode in ["review", "design", "audit"]:
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
        for signal in ["slo", "burn-rate", "pagerduty"]:
            assert signal in lower, f"missing signal: {signal}"

    def test_reference_loading_by_depth(self):
        assert "sli-slo-patterns.md" in SKILL_MD
        assert "alert-anti-patterns.md" in SKILL_MD


class TestDegradationModes:
    def test_four_modes_defined(self):
        for mode in ["Full", "Degraded", "Minimal", "Planning"]:
            assert mode in SKILL_MD

    def test_never_fabricate(self):
        lower = SKILL_MD.lower()
        assert "never" in lower and ("threshold" in lower or "guess" in lower)

    def test_traffic_warning(self):
        lower = SKILL_MD.lower()
        assert "traffic" in lower and "pattern" in lower


class TestDesignChecklist:
    def test_subsection_count(self):
        for sub in ["5.1", "5.2", "5.3", "5.4"]:
            assert sub in SKILL_MD

    def test_sli_slo(self):
        assert "SLI" in SKILL_MD
        assert "SLO" in SKILL_MD
        assert "error budget" in SKILL_MD.lower()

    def test_burn_rate(self):
        lower = SKILL_MD.lower()
        assert "burn-rate" in lower or "burn rate" in lower

    def test_actionable(self):
        assert "actionable" in SKILL_MD.lower()

    def test_for_duration(self):
        assert "`for`" in SKILL_MD or "for:" in SKILL_MD

    def test_runbook(self):
        assert "runbook" in SKILL_MD.lower()

    def test_cardinality(self):
        assert "cardinality" in SKILL_MD.lower()

    def test_red_use(self):
        lower = SKILL_MD.lower()
        assert "red" in lower and "use" in lower


class TestAntiExamples:
    def test_min_count(self):
        ae_count = sum(1 for l in SKILL_MD.split("\n") if l.strip().startswith("### AE-"))
        assert ae_count >= 6

    def test_wrong_right_pairs(self):
        assert SKILL_MD.count("# WRONG") >= 5
        assert SKILL_MD.count("# RIGHT") >= 5

    def test_absolute_count_ae(self):
        assert "absolute" in SKILL_MD.lower() or "count instead of rate" in SKILL_MD.lower()

    def test_extended_ref(self):
        assert "alert-anti-patterns.md" in SKILL_MD


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
        assert "sli" in lower
        assert "actionable" in lower
        assert "severity" in lower and "routing" in lower

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
    def test_sli_slo_exists(self):
        content = _ref("sli-slo-patterns.md")
        assert len(content.splitlines()) >= 80

    def test_sli_slo_keywords(self):
        content = _ref("sli-slo-patterns.md").lower()
        for kw in ["availability", "latency", "burn-rate", "error budget"]:
            assert kw in content

    def test_anti_patterns_exists(self):
        content = _ref("alert-anti-patterns.md")
        assert len(content.splitlines()) >= 80

    def test_anti_patterns_numbering(self):
        content = _ref("alert-anti-patterns.md")
        assert "AE-7" in content
        ae_count = sum(1 for l in content.split("\n") if "## AE-" in l)
        assert ae_count >= 5

    def test_alertmanager_config_exists(self):
        content = _ref("alertmanager-config-patterns.md")
        assert len(content.splitlines()) >= 80

    def test_alertmanager_config_keywords(self):
        content = _ref("alertmanager-config-patterns.md").lower()
        assert "inhibit_rules" in content
        assert "group_wait" in content
        assert "route" in content

    def test_all_refs_mentioned_in_skill(self):
        for f in REFS_DIR.glob("*.md"):
            assert f.name in SKILL_MD, f"{f.name} not in SKILL.md"


class TestAlertRoutingDesign:
    def test_inhibition_in_checklist(self):
        assert "inhibition" in SKILL_MD.lower()
        assert "suppress" in SKILL_MD.lower()

    def test_routing_severity_mapping(self):
        low = SKILL_MD.lower()
        assert "critical" in low and "pagerduty" in low
        assert "warning" in low and "slack" in low


class TestLineCount:
    def test_max_lines(self):
        lines = len(SKILL_MD.splitlines())
        assert lines <= 420, f"SKILL.md is {lines} lines (budget: 420)"


class TestCrossFileConsistency:
    def test_burn_rate_in_sli_slo(self):
        content = _ref("sli-slo-patterns.md").lower()
        assert "burn" in content and "rate" in content

    def test_promql_in_sli_slo(self):
        assert "rate(" in _ref("sli-slo-patterns.md")

    def test_p50_in_anti_patterns(self):
        assert "p50" in _ref("alert-anti-patterns.md")

    def test_cardinality_in_skill(self):
        assert "cardinality" in SKILL_MD.lower()

    def test_runbook_in_skill(self):
        assert "runbook_url" in SKILL_MD

    def test_grouping_in_skill(self):
        assert "group_by" in SKILL_MD

    def test_inhibit_rules_in_alertmanager_config(self):
        content = _ref("alertmanager-config-patterns.md")
        assert "inhibit_rules" in content

    def test_group_wait_in_alertmanager_config(self):
        content = _ref("alertmanager-config-patterns.md")
        assert "group_wait" in content
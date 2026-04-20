"""Contract tests for load-test SKILL.md.

Validates that required sections, rules, gates, scorecard tiers, and
output contract fields exist in SKILL.md and reference files.
NOT testing LLM behavior — only verifies rule surface is present.
"""

import pathlib
import re

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
SKILL_LOWER = SKILL_MD.lower()
REFS_DIR = SKILL_DIR / "references"


def _ref(name: str) -> str:
    return (REFS_DIR / name).read_text(encoding="utf-8")


def _all_text() -> str:
    parts = [SKILL_MD]
    for f in sorted(REFS_DIR.glob("*.md")):
        parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts)


# ──────────────────────────────────────────────────────────────────────
class TestFrontmatter:
    """Validate YAML frontmatter fields."""

    @pytest.fixture(autouse=True)
    def _front(self):
        m = re.search(r"^---\n(.*?)\n---", SKILL_MD, re.DOTALL)
        assert m, "YAML frontmatter block not found"
        self.front = m.group(1)

    def test_name_is_load_test(self):
        assert "name: load-test" in self.front

    def test_description_covers_triggers(self):
        desc = self.front.lower()
        for kw in ("k6", "vegeta", "slo", "bottleneck", "latency", "throughput"):
            assert kw in desc, f"description missing trigger keyword: {kw}"

    def test_allowed_tools_present(self):
        assert "allowed-tools:" in self.front


# ──────────────────────────────────────────────────────────────────────
class TestMandatoryGates:
    """Validate §2 Mandatory Gates."""

    def test_gates_section_exists(self):
        assert "## 2 Mandatory Gates" in SKILL_MD

    def test_gate_1_context_collection(self):
        assert "Gate 1: Context Collection" in SKILL_MD
        assert "Service endpoint" in SKILL_MD
        assert "Protocol" in SKILL_MD

    def test_gate_2_slo_first(self):
        assert "Gate 2: SLO-First" in SKILL_MD
        assert "SLOs MUST exist before writing test scripts" in SKILL_MD

    def test_gate_3_scope_classification(self):
        assert "Gate 3: Scope Classification" in SKILL_MD
        for mode in ("Write", "Review", "Analyze"):
            assert mode in SKILL_MD, f"mode {mode} missing from Gate 3"

    def test_gate_4_output_completeness(self):
        assert "Gate 4: Output Completeness" in SKILL_MD

    def test_stop_semantics(self):
        count = SKILL_MD.count("STOP")
        assert count >= 3, f"STOP appears {count} times, expected >= 3"


# ──────────────────────────────────────────────────────────────────────
class TestDepthSelection:
    """Validate §3 Depth Selection."""

    def test_three_depths(self):
        for depth in ("### Lite", "### Standard", "### Deep"):
            assert depth in SKILL_MD, f"depth heading missing: {depth}"

    def test_standard_is_default(self):
        assert "Standard (default)" in SKILL_MD

    def test_force_standard_conditions(self):
        assert "Force Standard if" in SKILL_MD

    def test_force_deep_conditions(self):
        assert "Force Deep if" in SKILL_MD

    def test_reference_loading_by_depth(self):
        for ref in ("k6-patterns.md", "vegeta-patterns.md", "analysis-guide.md"):
            assert ref in SKILL_MD, f"reference {ref} not mentioned in SKILL.md"


# ──────────────────────────────────────────────────────────────────────
class TestDegradationModes:
    """Validate §4 Degradation Modes."""

    def test_five_modes_defined(self):
        for mode in ("Full", "Script", "Partial", "Analysis", "Planning"):
            assert mode in SKILL_MD, f"degradation mode {mode} not found"

    def test_table_has_can_cannot(self):
        assert "Can Deliver" in SKILL_MD
        assert "Cannot Claim" in SKILL_MD

    def test_never_fabricate(self):
        assert "Never fabricate performance numbers" in SKILL_MD

    def test_never_claim_slo_without_data(self):
        assert "Never claim SLO compliance without data" in SKILL_MD

    def test_degraded_output_marker(self):
        assert "# DEGRADED:" in SKILL_MD


# ──────────────────────────────────────────────────────────────────────
class TestLoadTestChecklist:
    """Validate §5 Load Test Checklist."""

    def test_four_subsections(self):
        for sub in ("5.1 SLO Definition", "5.2 Script Quality",
                     "5.3 Analysis Methodology", "5.4 Execution Environment"):
            assert sub in SKILL_MD, f"subsection {sub} missing"

    def test_slo_definition_items(self):
        assert "percentile-based" in SKILL_LOWER
        assert "throughput target" in SKILL_LOWER
        assert "error budget" in SKILL_LOWER

    def test_script_quality_items(self):
        for item in ("Warmup phase precedes measurement",
                      "Ramp-up is gradual",
                      "Steady state duration is sufficient",
                      "Test data is representative"):
            assert item in SKILL_MD, f"checklist item missing: {item}"

    def test_analysis_methodology_items(self):
        assert "Report percentiles, not averages" in SKILL_MD
        assert "saturation point" in SKILL_LOWER

    def test_execution_environment_items(self):
        assert "Load generator runs separately from target" in SKILL_MD
        assert "Generator capacity verified" in SKILL_MD

    def test_total_checklist_count(self):
        numbered = re.findall(r"^\d+\.\s+\*\*", SKILL_MD, re.MULTILINE)
        assert len(numbered) >= 18, f"found {len(numbered)} numbered items, expected >= 18"


# ──────────────────────────────────────────────────────────────────────
class TestScenarioAndToolSelection:
    """Validate §6 Scenario & Tool Selection."""

    def test_tool_selection_table(self):
        for tool in ("k6", "vegeta", "wrk"):
            assert tool in SKILL_MD

    def test_default_to_k6(self):
        assert "Default to k6 unless" in SKILL_MD

    def test_six_scenarios(self):
        for scenario in ("Smoke", "Load", "Stress", "Breakpoint", "Soak", "Spike"):
            assert f"**{scenario}**" in SKILL_MD, f"scenario {scenario} missing"

    def test_scenario_goals_mapped(self):
        assert "Does it work under load?" in SKILL_MD
        assert "Where does it break?" in SKILL_MD


# ──────────────────────────────────────────────────────────────────────
class TestAntiExamples:
    """Validate §7 Anti-Examples."""

    def test_six_anti_examples(self):
        for i in range(1, 7):
            assert f"AE-{i}" in SKILL_MD, f"AE-{i} not found"

    def test_ae1_warmup(self):
        assert "Testing without warmup" in SKILL_MD

    def test_ae2_no_slo(self):
        assert "No SLO" in SKILL_MD

    def test_ae3_colocation(self):
        assert "Load generator on same machine" in SKILL_MD

    def test_ae4_cache_bias(self):
        assert "Same request every time" in SKILL_MD

    def test_ae5_short_duration(self):
        assert "30-second test" in SKILL_MD

    def test_ae6_averages(self):
        assert "Reporting averages" in SKILL_MD

    def test_wrong_right_pairs(self):
        wrong_count = SKILL_MD.count("# WRONG")
        right_count = SKILL_MD.count("# RIGHT")
        assert wrong_count >= 6, f"found {wrong_count} # WRONG markers, expected >= 6"
        assert right_count >= 6, f"found {right_count} # RIGHT markers, expected >= 6"


# ──────────────────────────────────────────────────────────────────────
class TestScorecard:
    """Validate §8 Load Test Scorecard."""

    def test_scorecard_section_exists(self):
        assert "## 8 Load Test Scorecard" in SKILL_MD

    def test_critical_tier_3_items(self):
        assert "SLO defined before test" in SKILL_MD
        assert "Warmup period excluded" in SKILL_MD
        assert "Steady state duration sufficient" in SKILL_MD

    def test_standard_tier_5_items(self):
        for item in ("Gradual ramp-up", "Error rate monitored",
                      "Percentile latency reported", "Load generator not co-located",
                      "Test data parameterized"):
            assert item in SKILL_MD, f"standard scorecard item missing: {item}"

    def test_hygiene_tier_4_items(self):
        for item in ("Environment documented", "Baseline comparison",
                      "Resource metrics correlated", "Results archived"):
            assert item in SKILL_MD, f"hygiene scorecard item missing: {item}"

    def test_passing_criteria(self):
        assert "3/3" in SKILL_MD
        assert ">= 4/5" in SKILL_MD or "4/5" in SKILL_MD
        assert ">= 3/4" in SKILL_MD or "3/4" in SKILL_MD

    def test_verdict_format(self):
        assert "PASS" in SKILL_MD
        assert "FAIL" in SKILL_MD


# ──────────────────────────────────────────────────────────────────────
class TestOutputContract:
    """Validate §9 Output Contract."""

    def test_nine_sections(self):
        for i in range(1, 10):
            assert f"9.{i}" in SKILL_MD, f"output section 9.{i} missing"

    def test_context_summary(self):
        assert "Context Summary" in SKILL_MD

    def test_mode_and_depth(self):
        assert "Mode & Depth" in SKILL_MD
        assert "Write | Review | Analyze" in SKILL_MD

    def test_slo_definition(self):
        assert "9.3 SLO Definition" in SKILL_MD

    def test_scenario_design(self):
        assert "Scenario Design" in SKILL_MD

    def test_test_script_or_review(self):
        assert "Test Script or Script Review" in SKILL_MD

    def test_results_analysis(self):
        assert "Results Analysis" in SKILL_MD
        assert "Percentile table" in SKILL_MD or "p50" in SKILL_MD

    def test_bottleneck_assessment(self):
        assert "Bottleneck Assessment" in SKILL_MD

    def test_recommendations(self):
        assert "Recommendations" in SKILL_MD

    def test_uncovered_risks_mandatory(self):
        assert "Uncovered Risks" in SKILL_MD
        assert "never empty" in SKILL_LOWER

    def test_scorecard_appended(self):
        assert "Scorecard appended" in SKILL_MD

    def test_volume_rules(self):
        assert "FAIL items fully" in SKILL_MD or "FAIL items" in SKILL_LOWER


# ──────────────────────────────────────────────────────────────────────
class TestReferenceFiles:
    """Validate reference file existence and content."""

    def test_k6_patterns_exists(self):
        assert (REFS_DIR / "k6-patterns.md").exists()

    def test_vegeta_patterns_exists(self):
        assert (REFS_DIR / "vegeta-patterns.md").exists()

    def test_analysis_guide_exists(self):
        assert (REFS_DIR / "analysis-guide.md").exists()

    def test_skill_references_all_files(self):
        for name in ("k6-patterns.md", "vegeta-patterns.md", "analysis-guide.md"):
            assert name in SKILL_MD, f"SKILL.md does not reference {name}"

    def test_k6_patterns_has_executor_types(self):
        k6 = _ref("k6-patterns.md").lower()
        for ex in ("constant-vus", "ramping-vus", "constant-arrival-rate"):
            assert ex in k6, f"k6-patterns missing executor: {ex}"

    def test_k6_patterns_has_thresholds(self):
        assert "thresholds" in _ref("k6-patterns.md").lower()

    def test_vegeta_has_attack_patterns(self):
        veg = _ref("vegeta-patterns.md").lower()
        for kw in ("attack", "report", "pipeline"):
            assert kw in veg, f"vegeta-patterns missing: {kw}"

    def test_analysis_guide_has_percentile_data(self):
        guide = _ref("analysis-guide.md").lower()
        for kw in ("percentile", "saturation", "bottleneck"):
            assert kw in guide, f"analysis-guide missing: {kw}"

    def test_analysis_guide_has_slo_verdict(self):
        guide = _ref("analysis-guide.md")
        for v in ("PASS", "FAIL", "WARN", "INCONCLUSIVE"):
            assert v in guide, f"analysis-guide missing verdict: {v}"


# ──────────────────────────────────────────────────────────────────────
class TestLineCount:
    """SKILL.md must stay within the line budget."""

    def test_skill_md_under_line_budget(self):
        lines = SKILL_MD.count("\n") + 1
        assert lines <= 420, f"SKILL.md is {lines} lines (budget: 420)"


# ──────────────────────────────────────────────────────────────────────
class TestCrossFileConsistency:
    """Key terms must appear in both SKILL.md and relevant references."""

    @pytest.fixture(autouse=True)
    def _load_refs(self):
        self.k6 = _ref("k6-patterns.md").lower()
        self.veg = _ref("vegeta-patterns.md").lower()
        self.analysis = _ref("analysis-guide.md").lower()

    # --- Terminology presence ---

    def test_p99_in_skill_and_analysis(self):
        assert "p99" in SKILL_LOWER
        assert "p99" in self.analysis

    def test_percentile_in_skill_and_analysis(self):
        assert "percentile" in SKILL_LOWER
        assert "percentile" in self.analysis

    def test_slo_in_skill_and_k6(self):
        assert "slo" in SKILL_LOWER
        assert "slo" in self.k6

    def test_warmup_in_skill_and_k6(self):
        assert "warmup" in SKILL_LOWER
        assert "warmup" in self.k6

    def test_saturation_in_skill_and_analysis(self):
        assert "saturation" in SKILL_LOWER
        assert "saturation" in self.analysis

    def test_bottleneck_in_skill_and_analysis(self):
        assert "bottleneck" in SKILL_LOWER
        assert "bottleneck" in self.analysis

    # --- Minimum substantive content per reference file ---

    def test_k6_patterns_min_lines(self):
        lines = _ref("k6-patterns.md").count("\n") + 1
        assert lines >= 400, f"k6-patterns.md has {lines} lines, expected >= 400"

    def test_vegeta_patterns_min_lines(self):
        lines = _ref("vegeta-patterns.md").count("\n") + 1
        assert lines >= 200, f"vegeta-patterns.md has {lines} lines, expected >= 200"

    def test_analysis_guide_min_lines(self):
        lines = _ref("analysis-guide.md").count("\n") + 1
        assert lines >= 250, f"analysis-guide.md has {lines} lines, expected >= 250"

    def test_dropped_iterations_in_k6(self):
        assert "dropped_iterations" in SKILL_LOWER
        assert "dropped_iterations" in self.k6 or "dropped" in self.k6
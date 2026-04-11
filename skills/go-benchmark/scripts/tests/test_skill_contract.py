"""Contract tests for go-benchmark SKILL.md.

Validates that required sections, rules, gates, scorecard tiers, and
output contract fields exist in SKILL.md and reference files.
NOT testing LLM behavior — only verifies rule surface is present.
"""

import re
import json
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
REF_DIR = SKILL_DIR / "references"
BENCH_PATTERNS = REF_DIR / "benchmark-patterns.md"
PPROF_ANALYSIS = REF_DIR / "pprof-analysis.md"
OPT_PATTERNS = REF_DIR / "optimization-patterns.md"
BENCH_ANTIPATTERNS = REF_DIR / "benchmark-antipatterns.md"
BENCHSTAT_GUIDE = REF_DIR / "benchstat-guide.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _all_text() -> str:
    parts = [_read(SKILL_MD)]
    for f in sorted(REF_DIR.glob("*.md")):
        parts.append(_read(f))
    return "\n".join(parts)


# ------------------------------------------------------------------
# TestFrontmatter
# ------------------------------------------------------------------

class TestFrontmatter(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = _read(SKILL_MD)

    def test_name_is_go_benchmark(self) -> None:
        self.assertIn("name: go-benchmark", self.text)

    def test_description_covers_benchmark_triggers(self) -> None:
        for kw in ("testing.B", "pprof", "benchstat", "ns/op"):
            self.assertIn(kw, self.text)


# ------------------------------------------------------------------
# TestHardRules
# ------------------------------------------------------------------

class TestHardRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = _read(SKILL_MD)

    def test_hard_rules_section_exists(self) -> None:
        self.assertIn("## Hard Rules", self.text)

    def test_rule_1_sink_every_result(self) -> None:
        self.assertIn("Sink every result", self.text)
        self.assertIn("var sink", self.text)
        self.assertIn("measures nothing", self.text)

    def test_rule_2_timer_discipline(self) -> None:
        self.assertIn("Timer discipline", self.text)
        self.assertIn("b.ResetTimer()", self.text)
        self.assertIn("b.StopTimer()", self.text)

    def test_rule_3_always_benchmem(self) -> None:
        self.assertIn("Always `-benchmem`", self.text)
        self.assertIn("-benchmem", self.text)

    def test_rule_4_count_for_comparisons(self) -> None:
        self.assertIn("-count=10", self.text)
        self.assertIn("statistically meaningless", self.text)
        self.assertIn("-count=5", self.text)

    def test_rule_5_never_compare_across_environments(self) -> None:
        self.assertIn("Never compare across environments", self.text)


# ------------------------------------------------------------------
# TestMandatoryGates
# ------------------------------------------------------------------

class TestMandatoryGates(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = _read(SKILL_MD)

    def test_mandatory_gates_section_exists(self) -> None:
        self.assertIn("## Mandatory Gates", self.text)

    def test_gate_1_evidence_gate_exists(self) -> None:
        self.assertIn("Evidence Gate", self.text)
        for mode in ("write", "review", "analyze"):
            self.assertIn(f"`{mode}`", self.text)

    def test_gate_1_mode_data_basis_labels(self) -> None:
        self.assertIn("static analysis only", self.text)
        self.assertIn("benchmark output", self.text)
        self.assertIn("pprof profile", self.text)

    def test_gate_2_applicability_gate_exists(self) -> None:
        self.assertIn("Applicability Gate", self.text)
        self.assertIn("STOP if", self.text)

    def test_gate_3_scope_gate_exists(self) -> None:
        self.assertIn("Scope Gate", self.text)
        self.assertIn("b.RunParallel", self.text)
        self.assertIn("sub-benchmarks across", self.text)


# ------------------------------------------------------------------
# TestThreePhaseWorkflow
# ------------------------------------------------------------------

class TestThreePhaseWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = _read(SKILL_MD)

    def test_three_phase_workflow_section(self) -> None:
        self.assertIn("Three-Phase Workflow", self.text)

    def test_phase_1_write_benchmarks(self) -> None:
        self.assertIn("Phase 1", self.text)
        self.assertIn("Write Benchmarks", self.text)
        self.assertIn("b.ResetTimer()", self.text)
        self.assertIn("var sinkString", self.text)

    def test_phase_1_sub_benchmark_template(self) -> None:
        self.assertIn("b.Run(", self.text)
        self.assertIn("b.RunParallel(", self.text)

    def test_phase_2_run_and_profile(self) -> None:
        self.assertIn("Phase 2", self.text)
        self.assertIn("Run & Profile", self.text)
        self.assertIn("benchstat", self.text)
        self.assertIn("-cpuprofile", self.text)
        self.assertIn("-memprofile", self.text)

    def test_phase_2_alloc_objects_vs_alloc_space(self) -> None:
        self.assertIn("-alloc_objects", self.text)
        self.assertIn("-alloc_space", self.text)

    def test_phase_3_analyze_and_optimize(self) -> None:
        self.assertIn("Phase 3", self.text)
        self.assertIn("Analyze & Optimize", self.text)
        self.assertIn("sync.Pool", self.text)

    def test_phase_3_pprof_hotspot_identification(self) -> None:
        self.assertIn("Flame Graph", self.text)
        self.assertIn("flat", self.text)
        self.assertIn("cum", self.text)


# ------------------------------------------------------------------
# TestOutputContract
# ------------------------------------------------------------------

class TestOutputContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = _read(SKILL_MD)

    def test_output_contract_section_exists(self) -> None:
        self.assertIn("## Output Contract", self.text)

    def test_mode_field_required(self) -> None:
        self.assertIn("`mode`", self.text)

    def test_data_basis_field_required(self) -> None:
        self.assertIn("`data_basis`", self.text)

    def test_scorecard_result_field_required(self) -> None:
        self.assertIn("`scorecard_result`", self.text)

    def test_profiling_method_field_required(self) -> None:
        self.assertIn("`profiling_method`", self.text)
        for method in ("none", "cpu", "memory", "mutex", "block"):
            self.assertIn(method, self.text)


# ------------------------------------------------------------------
# TestExpectedOutputFormat
# ------------------------------------------------------------------

class TestExpectedOutputFormat(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = _read(SKILL_MD)

    def test_output_format_section_exists(self) -> None:
        self.assertIn("## Expected Output Format", self.text)

    def test_phase_1_output_includes_run_command(self) -> None:
        self.assertIn("Run command with correct flags", self.text)

    def test_phase_3_output_includes_top3_hotspots(self) -> None:
        self.assertIn("Top-3 hotspots", self.text)

    def test_scorecard_summary_block_format(self) -> None:
        self.assertIn("## Benchmark Scorecard", self.text)
        self.assertIn("Data basis:", self.text)
        self.assertIn("Next step", self.text)


# ------------------------------------------------------------------
# TestHonestDegradation
# ------------------------------------------------------------------

class TestHonestDegradation(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = _read(SKILL_MD)

    def test_honest_degradation_section_exists(self) -> None:
        self.assertIn("Before You Start", self.text)
        self.assertIn("Honest Degradation", self.text)

    def test_degradation_covers_source_only(self) -> None:
        self.assertIn("Source code only", self.text)
        self.assertIn("static alloc hints", self.text)

    def test_degradation_covers_benchmark_output(self) -> None:
        self.assertIn("Benchmark output (text)", self.text)

    def test_degradation_covers_pprof(self) -> None:
        self.assertIn("pprof profile", self.text)
        self.assertIn("Full Phase 3 analysis", self.text)

    def test_degradation_forbids_invented_numbers(self) -> None:
        self.assertIn("Never invent benchmark numbers", self.text)


# ------------------------------------------------------------------
# TestAutoScorecard
# ------------------------------------------------------------------

class TestAutoScorecard(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = _read(SKILL_MD)

    def test_scorecard_section_exists(self) -> None:
        self.assertIn("## Auto Scorecard", self.text)

    def test_critical_tier_exists_with_3_items(self) -> None:
        self.assertIn("Critical — any failure means redo", self.text)
        self.assertIn("package-level sink", self.text)
        self.assertIn("`-benchmem` is included", self.text)
        self.assertIn("placed correctly", self.text)

    def test_standard_tier_exists_with_5_items(self) -> None:
        self.assertIn("Standard — 4 of 5 must pass", self.text)
        self.assertIn("-count=10", self.text)
        self.assertIn("sub-benchmarks across", self.text)
        self.assertIn("`benchstat`", self.text)
        self.assertIn("alloc target stated", self.text)

    def test_hygiene_tier_exists_with_4_items(self) -> None:
        self.assertIn("Hygiene — 3 of 4 must pass", self.text)
        self.assertIn("Parallel benchmark", self.text)
        self.assertIn("top-3 hotspot", self.text)
        self.assertIn("Environment noted", self.text)

    def test_next_step_lookup_table(self) -> None:
        self.assertIn("Next step", self.text)
        self.assertIn("static analysis only", self.text)
        self.assertIn("benchmark output", self.text)
        self.assertIn("pprof profile", self.text)


# ------------------------------------------------------------------
# TestAntiExamples
# ------------------------------------------------------------------

class TestAntiExamples(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = _read(SKILL_MD)

    def test_anti_examples_section_exists(self) -> None:
        self.assertIn("## Anti-Examples", self.text)

    def test_anti_example_1_dead_code(self) -> None:
        self.assertIn("_ = expensiveFunc(input)", self.text)
        self.assertIn("compiler may eliminate", self.text)

    def test_anti_example_2_setup_in_loop(self) -> None:
        self.assertIn("db := connectDB()", self.text)
        self.assertIn("setup runs inside the loop", self.text)

    def test_anti_example_3_single_run(self) -> None:
        self.assertIn("variance can easily be", self.text)
        self.assertIn("ten runs + benchstat", self.text)

    def test_all_anti_examples_have_bad_and_good(self) -> None:
        self.assertGreaterEqual(
            self.text.count("// BAD:"), 3,
            "Need at least 3 BAD examples in SKILL.md"
        )
        self.assertGreaterEqual(
            self.text.count("// GOOD:"), 3,
            "Need at least 3 GOOD examples in SKILL.md"
        )


# ------------------------------------------------------------------
# TestReferenceFiles
# ------------------------------------------------------------------

class TestReferenceFiles(unittest.TestCase):
    def test_benchmark_patterns_exists(self) -> None:
        self.assertTrue(BENCH_PATTERNS.exists(), "benchmark-patterns.md missing")

    def test_pprof_analysis_exists(self) -> None:
        self.assertTrue(PPROF_ANALYSIS.exists(), "pprof-analysis.md missing")

    def test_optimization_patterns_exists(self) -> None:
        self.assertTrue(OPT_PATTERNS.exists(), "optimization-patterns.md missing")

    def test_benchmark_antipatterns_exists(self) -> None:
        self.assertTrue(BENCH_ANTIPATTERNS.exists(), "benchmark-antipatterns.md missing")

    def test_benchstat_guide_exists(self) -> None:
        self.assertTrue(BENCHSTAT_GUIDE.exists(), "benchstat-guide.md missing")

    def test_skill_md_references_all_5_files(self) -> None:
        text = _read(SKILL_MD)
        for ref in (
            "benchmark-patterns.md",
            "pprof-analysis.md",
            "optimization-patterns.md",
            "benchmark-antipatterns.md",
            "benchstat-guide.md",
        ):
            self.assertIn(ref, text, f"SKILL.md does not reference {ref}")

    def test_benchmark_patterns_has_b_api_table(self) -> None:
        text = _read(BENCH_PATTERNS)
        for method in ("b.ResetTimer()", "b.SetBytes", "b.RunParallel", "b.Run("):
            self.assertIn(method, text, f"benchmark-patterns.md missing {method}")

    def test_pprof_analysis_has_profile_types(self) -> None:
        text = _read(PPROF_ANALYSIS)
        for profile in ("-cpuprofile", "-memprofile", "-mutexprofile"):
            self.assertIn(profile, text, f"pprof-analysis.md missing {profile}")

    def test_optimization_patterns_has_sync_pool(self) -> None:
        text = _read(OPT_PATTERNS)
        self.assertIn("sync.Pool", text)
        self.assertIn("Pre-Allocation", text)

    def test_antipatterns_has_extended_examples(self) -> None:
        text = _read(BENCH_ANTIPATTERNS)
        self.assertGreaterEqual(
            text.count("## AP-"), 5,
            "benchmark-antipatterns.md should have at least 5 AP-N sections"
        )

    def test_benchstat_guide_has_pvalue_guidance(self) -> None:
        text = _read(BENCHSTAT_GUIDE)
        self.assertIn("p < 0.05", text)
        self.assertIn("count=10", text)


# ------------------------------------------------------------------
# TestLineCount  (Phase 3 line budget)
# ------------------------------------------------------------------

class TestLineCount(unittest.TestCase):
    def test_skill_md_under_line_budget(self) -> None:
        lines = len(_read(SKILL_MD).splitlines())
        self.assertLessEqual(lines, 400, f"SKILL.md too long: {lines} lines (budget: 400)")


if __name__ == "__main__":
    unittest.main()
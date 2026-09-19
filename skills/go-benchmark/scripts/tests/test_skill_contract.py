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

    def test_critical_tier_grades_properties_not_tokens(self) -> None:
        """The Critical tier used to demand a `package-level sink` outright, which would fail a
        correct `for b.Loop()` benchmark — b.Loop needs no sink. It must grade the property
        (body cannot be optimised away) and accept either loop form."""
        self.assertIn("Critical — any applicable failure means redo", self.text)
        self.assertIn("cannot be optimised away", self.text)
        self.assertIn("no sink required", self.text)
        self.assertIn("Grade the property, not the presence of a `sink` identifier", self.text)
        self.assertIn("`-benchmem` is included", self.text)
        self.assertIn("correctly placed", self.text)
        self.assertIn("b.RunParallel", self.text)

    def test_standard_tier_exists_with_5_items(self) -> None:
        self.assertIn("Standard — ≥ 80% of applicable items", self.text)
        self.assertIn("-count=10", self.text)
        self.assertIn("sub-benchmarks across", self.text)
        self.assertIn("`benchstat`", self.text)
        self.assertIn("alloc target stated", self.text)

    def test_hygiene_tier_exists_with_4_items(self) -> None:
        self.assertIn("Hygiene — ≥ 75% of applicable items", self.text)
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
        self.assertLessEqual(lines, 420, f"SKILL.md too long: {lines} lines (budget: 420)")


# ------------------------------------------------------------------
# TestCrossFileConsistency — key terms consistently present across all refs
# ------------------------------------------------------------------

class TestCrossFileConsistency(unittest.TestCase):
    """Verify key terms are spelled correctly and present in the expected
    reference files. Catches silent drift where a refactor renames a symbol
    in one file but not another."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.bench_patterns = _read(BENCH_PATTERNS)
        cls.pprof_analysis = _read(PPROF_ANALYSIS)
        cls.opt_patterns = _read(OPT_PATTERNS)
        cls.bench_antipatterns = _read(BENCH_ANTIPATTERNS)
        cls.benchstat_guide = _read(BENCHSTAT_GUIDE)

    # --- Terminology presence ---

    def test_b_reset_timer_in_benchmark_patterns(self) -> None:
        """b.ResetTimer() is the canonical timer method; must appear in patterns ref."""
        self.assertIn("b.ResetTimer()", self.bench_patterns)

    def test_b_n_loop_in_benchmark_patterns(self) -> None:
        """b.N is the canonical loop variable; must be documented."""
        self.assertIn("b.N", self.bench_patterns)

    def test_benchstat_in_benchstat_guide(self) -> None:
        """benchstat guide must actually mention benchstat."""
        self.assertIn("benchstat", self.benchstat_guide)

    def test_p_value_guidance_in_benchstat_guide(self) -> None:
        """Statistical validity requires p-value guidance."""
        self.assertIn("p < 0.05", self.benchstat_guide)

    def test_sync_pool_in_optimization_patterns(self) -> None:
        """sync.Pool is the primary alloc-reduction tool; must be in opt-patterns."""
        self.assertIn("sync.Pool", self.opt_patterns)

    def test_alloc_objects_flag_in_pprof_analysis(self) -> None:
        """-alloc_objects is the key flag for GC pressure; must be documented."""
        self.assertIn("-alloc_objects", self.pprof_analysis)

    # --- Minimum substantive content per reference file ---

    def test_benchmark_patterns_min_lines(self) -> None:
        lines = len(self.bench_patterns.splitlines())
        self.assertGreaterEqual(lines, 100,
                                f"benchmark-patterns.md too short: {lines} lines (min 100)")

    def test_pprof_analysis_min_lines(self) -> None:
        lines = len(self.pprof_analysis.splitlines())
        self.assertGreaterEqual(lines, 100,
                                f"pprof-analysis.md too short: {lines} lines (min 100)")

    def test_optimization_patterns_min_lines(self) -> None:
        lines = len(self.opt_patterns.splitlines())
        self.assertGreaterEqual(lines, 80,
                                f"optimization-patterns.md too short: {lines} lines (min 80)")

    def test_benchstat_guide_min_lines(self) -> None:
        lines = len(self.benchstat_guide.splitlines())
        self.assertGreaterEqual(lines, 80,
                                f"benchstat-guide.md too short: {lines} lines (min 80)")


class TestCoverageDocIsCurrent(unittest.TestCase):
    """COVERAGE.md claimed 96 tests and a 378-line SKILL.md while the suite had 105 and the
    file had 419. A coverage document that overstates the suite is worse than none, because
    it is read as evidence. These checks make the numbers falsifiable.

    Counting uses unittest's loader rather than an AST walk: `ReferenceTemplateCompileTests`
    inherits its two compile tests from `TemplateCompileTests`, so parsing `def test_` finds
    109 where the loader collects 111. The number in the doc must be the collected one.
    """

    DOC = Path(__file__).resolve().parent / "COVERAGE.md"

    @classmethod
    def setUpClass(cls) -> None:
        import unittest as ut
        loader = ut.TestLoader()
        suite = loader.discover(str(Path(__file__).resolve().parent), pattern="test_*.py")
        cls.collected = suite.countTestCases()
        cls.doc = cls.DOC.read_text(encoding="utf-8")

    # Per-module counts, derived. Pinning only the total is what let the layered figures
    # drift to 65-vs-69 while the total stayed right — the guard checked the sum, so any
    # pair of offsetting errors passed.
    LAYER_LABELS = {
        "test_skill_contract.py": "Contract test count",
        "test_golden_scenarios.py": "Golden test count",
        "test_templates_compile.py": "Template/compile/script test count",
    }

    @classmethod
    def _module_counts(cls) -> dict:
        import importlib.util
        import sys
        import unittest as ut

        here = Path(__file__).resolve().parent
        out = {}
        for path in sorted(here.glob("test_*.py")):
            spec = importlib.util.spec_from_file_location("_cnt_" + path.stem, path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)
            out[path.name] = ut.defaultTestLoader.loadTestsFromModule(mod).countTestCases()
        return out

    def test_total_matches_the_collected_suite(self) -> None:
        m = re.search(r"\*\*Total tests: (\d+) collected\*\*", self.doc)
        self.assertIsNotNone(m, "COVERAGE.md has no '**Total tests: N collected**' line")
        self.assertEqual(
            self.collected, int(m.group(1)),
            f"COVERAGE.md claims {m.group(1)}; the loader collects {self.collected}",
        )

    def test_every_module_has_a_declared_count(self) -> None:
        counts = self._module_counts()
        self.assertEqual(set(self.LAYER_LABELS), set(counts),
                         "a test module was added or removed; COVERAGE.md must account "
                         "for it by name, not only inside the total")
        for name, label in self.LAYER_LABELS.items():
            with self.subTest(module=name):
                m = re.search(rf"\*\*{re.escape(label)}: (\d+)\*\*", self.doc)
                self.assertIsNotNone(m, f"COVERAGE.md has no '{label}: N' line")
                self.assertEqual(counts[name], int(m.group(1)),
                                 f"COVERAGE.md says {label} is {m.group(1)}; the loader "
                                 f"collects {counts[name]} from {name}")

    def test_the_layer_counts_sum_to_the_declared_total(self) -> None:
        """Offsetting errors are the failure mode a total-only guard cannot see."""
        declared = [int(m) for m in re.findall(
            r"\*\*(?:Contract test count|Golden test count|"
            r"Template/compile/script test count): (\d+)\*\*", self.doc)]
        self.assertEqual(3, len(declared), "one of the three layer counts is missing")
        total = re.search(r"\*\*Total tests: (\d+) collected\*\*", self.doc)
        self.assertEqual(int(total.group(1)), sum(declared),
                         f"layer counts sum to {sum(declared)}, total says {total.group(1)}")

    def test_line_budget_figure_matches_the_file(self) -> None:
        actual = len(SKILL_MD.read_text(encoding="utf-8").splitlines())
        m = re.search(r"SKILL\.md line budget \| (\d+)/(\d+)", self.doc)
        self.assertIsNotNone(m, "no SKILL.md line-budget row in COVERAGE.md")
        self.assertEqual(actual, int(m.group(1)),
                         f"COVERAGE.md says {m.group(1)} lines; the file has {actual}")
        self.assertLessEqual(actual, int(m.group(2)))

    def test_golden_layer_is_not_described_as_forward_eval(self) -> None:
        """The golden layer checks fixture metadata; calling it behavioural evidence is the
        overstatement this doc now has to avoid."""
        self.assertIn("fixture-consistency testing, not forward evaluation", self.doc)
        self.assertRegex(self.doc, r"(?i)no forward eval")


# ------------------------------------------------------------------
# Section-scoped guards
#
# Everything above this line asserts `assertIn(phrase, whole_file)`. That shape is
# fail-open against the mutation that matters: a rule can be inverted and still keep its
# vocabulary, because the phrase survives somewhere else in the document. Measured on
# 2026-09-18 — rewriting Hard Rule 1 to "discarding with `_ =` is fine; the compiler keeps
# the call" and Hard Rule 2 to "setup goes *after* b.ResetTimer()" both passed all 134
# tests. The guards below read the deciding line and pin the direction-carrying words in it.
# ------------------------------------------------------------------

def md_section(text: str, heading: str) -> str:
    """Return the body under `heading` up to the next heading of the same or higher level.

    Line-indexed rather than `text.index(line)`: a heading string that also appears in body
    prose would otherwise slice from the wrong offset.
    """
    lines = text.splitlines()
    level = len(heading) - len(heading.lstrip("#"))
    start = None
    for i, line in enumerate(lines):
        if line.strip() == heading:
            start = i + 1
            break
    assert start is not None, f"heading not found: {heading!r}"
    fenced = False
    for j in range(start, len(lines)):
        s = lines[j].lstrip()
        if s.startswith("```"):
            fenced = not fenced
            continue
        # A `#` inside a fence is a shell comment, not a heading. Without this the section
        # ends at the first commented line of the first bash block, and every assertion
        # against it silently checks a fraction of the section.
        if fenced:
            continue
        if s.startswith("#") and len(s) - len(s.lstrip("#")) <= level:
            return "\n".join(lines[start:j])
    return "\n".join(lines[start:])


def md_rows(section: str) -> list[list[str]]:
    """Parse a markdown table into cell lists, skipping the header and separator rows."""
    rows = []
    for line in section.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in cells):
            rows = []          # separator: everything before it was the header
            continue
        rows.append(cells)
    return rows


def numbered_rule(section: str, n: int) -> str:
    """The full text of Hard Rule `n`, including any continuation lines."""
    lines = section.splitlines()
    out = []
    for i, line in enumerate(lines):
        if line.startswith(f"{n}. "):
            out.append(line)
            for nxt in lines[i + 1:]:
                if re.match(r"^\d+\. ", nxt) or nxt.startswith("#"):
                    break
                out.append(nxt)
            break
    assert out, f"Hard Rule {n} not found"
    return "\n".join(out)


class SectionHelperTests(unittest.TestCase):
    """The helpers every guard below depends on. A section that silently ends early makes
    each assertion check a fraction of what it names — and still passes.
    """

    DOC = (
        "# Top\n\nintro\n\n"
        "## Alpha\n\nalpha body\n\n"
        "```bash\n# a shell comment, not a heading\necho hi\n```\n\n"
        "after the fence\n\n"
        "### Alpha child\n\nchild body\n\n"
        "## Beta\n\nbeta body\n"
    )

    def test_section_spans_a_fence_containing_a_hash_line(self) -> None:
        body = md_section(self.DOC, "## Alpha")
        self.assertIn("alpha body", body)
        self.assertIn("after the fence", body,
                      "section ended at a `#` inside a code fence")
        self.assertIn("child body", body, "a deeper heading must stay inside the section")
        self.assertNotIn("beta body", body, "section ran past the next same-level heading")

    def test_section_stops_at_the_next_same_level_heading(self) -> None:
        self.assertEqual("\nbeta body", md_section(self.DOC, "## Beta"))

    def test_missing_heading_is_an_error_not_an_empty_string(self) -> None:
        with self.assertRaises(AssertionError):
            md_section(self.DOC, "## Nope")

    def test_rows_skip_header_and_separator(self) -> None:
        table = "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n"
        self.assertEqual([["1", "2"], ["3", "4"]], md_rows(table))

    def test_numbered_rule_takes_continuation_lines_and_stops_at_the_next(self) -> None:
        section = ("1. **One** — first line\n   continued here\n"
                   "2. **Two** — second\n")
        one = numbered_rule(section, 1)
        self.assertIn("continued here", one)
        self.assertNotIn("**Two**", one)


class NormativeRuleDirectionTests(unittest.TestCase):
    """Each Hard Rule is pinned by what it *requires*, inside its own numbered item.

    The phrase-presence tests above cannot tell "always X" from "never X" — they only see
    that the word X is somewhere in the file. These assert the deciding words are in the
    deciding line, and that the opposite instruction is not.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.rules = md_section(_read(SKILL_MD), "## Hard Rules")

    def test_rule_1_requires_a_sink_and_condemns_the_discard(self) -> None:
        r = numbered_rule(self.rules, 1)
        self.assertIn("assign the final output to a package-level `var sink T`", r)
        self.assertRegex(r, r"`_ =`[^.]*(eliminate dead code|measures nothing)",
                         "Rule 1 no longer states that `_ =` permits elision")
        self.assertNotRegex(r, r"(?i)`_ =`[^.]*(is fine|is enough|is acceptable|keeps the call)",
                            "Rule 1 has been inverted to bless the discard form")

    def test_rule_2_puts_setup_before_the_reset(self) -> None:
        r = numbered_rule(self.rules, 2)
        self.assertRegex(r, r"setup[^.]*goes \*before\* `b\.ResetTimer\(\)`",
                         "Rule 2 no longer places one-time setup before ResetTimer")
        self.assertNotRegex(r, r"setup[^.]*goes \*after\* `b\.ResetTimer\(\)`",
                            "Rule 2 has been inverted: timed setup is the defect it exists for")

    def test_rule_3_makes_benchmem_mandatory(self) -> None:
        r = numbered_rule(self.rules, 3)
        self.assertRegex(r, r"\*\*Always `-benchmem` on measurement runs\*\*")
        self.assertNotRegex(r, r"(?i)`-benchmem` is (optional|not required)",
                            "Rule 3 has been downgraded from mandatory")
        # The one documented exemption must stay an exemption, not become the rule.
        self.assertIn("-race", r, "Rule 3 lost the -race exemption it scopes itself against")

    def test_rule_4_requires_ten_samples_for_a_comparison(self) -> None:
        r = numbered_rule(self.rules, 4)
        self.assertRegex(r, r"\*\*`-count=10` for comparisons")
        self.assertIn("a single run is statistically meaningless", r)
        self.assertNotRegex(r, r"(?i)a single run is statistically (sufficient|enough|fine)")
        self.assertIn("Interleave", r, "Rule 4 lost the interleaving instruction")

    def test_rule_5_forbids_cross_environment_comparison(self) -> None:
        r = numbered_rule(self.rules, 5)
        self.assertIn("**Never compare across environments**", r)
        self.assertIn("are not comparable", r)
        self.assertNotRegex(r, r"(?i)(are comparable|is fine)\b",
                            "Rule 5 has been inverted")

    def test_every_hard_rule_is_pinned_here(self) -> None:
        """Anti-vacuity: a rule added to SKILL.md without a direction guard would otherwise
        inherit the fail-open shape this class exists to remove."""
        numbers = sorted(int(m) for m in re.findall(r"(?m)^(\d+)\. \*\*", self.rules))
        self.assertEqual([0, 1, 2, 3, 4, 5], numbers,
                         "Hard Rules renumbered; the guards below must follow")
        pinned = {1, 2, 3, 4, 5}
        guarded = {int(m.group(1))
                   for name in dir(self)
                   if (m := re.match(r"test_rule_(\d+)_", name))}
        self.assertEqual(pinned, guarded,
                         "a Hard Rule has no direction guard")

    def test_the_direction_guards_are_not_vacuous(self) -> None:
        """Each assertion above must fail on the inverted text, not merely pass on the real
        one. Proven against synthetic inversions rather than by inspection."""
        inverted = {
            1: "1. **Sink every result** — using `_ =` is fine; the compiler keeps the call.",
            2: "2. **Timer discipline** — setup goes *after* `b.ResetTimer()`.",
            3: "3. **`-benchmem` is optional on measurement runs** — skip it if you like.",
            4: "4. **`-count=1` for comparisons** — a single run is statistically sufficient.",
            5: "5. **Comparing across environments is fine** — results are comparable.",
        }
        for n, text in inverted.items():
            with self.subTest(rule=n):
                fake = "\n".join(inverted[k] if k == n else numbered_rule(self.rules, k)
                                 for k in sorted(inverted))
                probe = _DirectionProbe(fake)
                with self.assertRaises(AssertionError,
                                       msg=f"Rule {n} guard passes on the inverted text"):
                    getattr(probe, f"check_{n}")()


class _DirectionProbe(unittest.TestCase):
    """Runs the same assertions as NormativeRuleDirectionTests against supplied text.

    Kept as a helper the self-test drives, so the guard bodies and the bodies being probed
    cannot drift apart into "the test tests a copy of the check".
    """

    def __init__(self, rules_text: str) -> None:
        super().__init__("run")
        self.rules = rules_text

    def run(self) -> None:  # never collected as a test; satisfies TestCase.__init__
        raise NotImplementedError

    def check_1(self) -> None:
        NormativeRuleDirectionTests.test_rule_1_requires_a_sink_and_condemns_the_discard(self)

    def check_2(self) -> None:
        NormativeRuleDirectionTests.test_rule_2_puts_setup_before_the_reset(self)

    def check_3(self) -> None:
        NormativeRuleDirectionTests.test_rule_3_makes_benchmem_mandatory(self)

    def check_4(self) -> None:
        NormativeRuleDirectionTests.test_rule_4_requires_ten_samples_for_a_comparison(self)

    def check_5(self) -> None:
        NormativeRuleDirectionTests.test_rule_5_forbids_cross_environment_comparison(self)


class ScorecardAndGateValuesPinnedTests(unittest.TestCase):
    """Thresholds and gate verdicts, derived where possible rather than restated.

    A bar written as prose ("≥ 80%") drifts from the list it grades. These read the tier's
    own checklist and recompute the pass count, so adding an item without revisiting the
    rounding table fails here.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = _read(SKILL_MD)
        cls.card = md_section(cls.text, "## Auto Scorecard")

    def _tier_items(self, header_regex: str) -> int:
        lines = self.card.splitlines()
        for i, line in enumerate(lines):
            if re.search(header_regex, line):
                n = 0
                for nxt in lines[i + 1:]:
                    if nxt.strip().startswith("- [ ]"):
                        n += 1
                    elif nxt.strip().startswith("**") or nxt.startswith("#"):
                        break
                return n
        self.fail(f"tier header not found: {header_regex}")

    def test_tier_bars_match_their_own_checklists(self) -> None:
        import math
        for header, pct in ((r"\*\*Standard — ≥ (\d+)%", 80), (r"\*\*Hygiene — ≥ (\d+)%", 75)):
            with self.subTest(tier=header):
                m = re.search(header, self.card)
                self.assertIsNotNone(m, f"tier bar missing: {header}")
                self.assertEqual(pct, int(m.group(1)),
                                 "the tier bar moved; the rounding table below it must too")
                n = self._tier_items(header)
                self.assertGreater(n, 0, "tier has no checklist items — bar grades nothing")
                # The rounding table must contain the entry for the real item count.
                need = math.ceil(pct / 100 * n)
                self.assertRegex(self.card, rf"{n}→{need}",
                                 f"{n} items at {pct}% needs {need}; the rounding table in "
                                 f"SKILL.md does not list {n}→{need}")

    def test_every_rounding_entry_is_arithmetically_right(self) -> None:
        import math
        for m in re.finditer(r"≥ (\d+)% of applicable items, rounded up \(([^)]*)\)", self.card):
            pct = int(m.group(1))
            for pair in m.group(2).split(","):
                a, b = pair.strip().split("→")
                with self.subTest(pct=pct, pair=pair.strip()):
                    self.assertEqual(math.ceil(pct / 100 * int(a)), int(b),
                                     f"{pct}% of {a} is not {b}")

    def test_critical_na_is_not_a_pass(self) -> None:
        self.assertIn("a Critical `N/A` is **not** a pass", self.card)
        self.assertNotRegex(self.card, r"(?i)Critical `N/A`[^.]*(counts as|is) a pass")

    def test_critical_tier_is_one_veto(self) -> None:
        self.assertRegex(self.card, r"\*\*Critical — any applicable failure means redo:\*\*")
        self.assertNotRegex(self.card, r"(?i)\*\*Critical — (advisory|optional)")

    def test_profiling_needs_run_regex(self) -> None:
        phase2 = md_section(self.text, "### Phase 2 — Run & Profile")
        self.assertIn("**Never profile without `-run='^$'`.**", phase2)
        self.assertNotRegex(phase2, r"(?i)`-run='\^\$'` is optional")

    def test_alloc_space_is_not_described_as_footprint(self) -> None:
        phase2 = md_section(self.text, "### Phase 2 — Run & Profile")
        self.assertIn("**`alloc_space` is not memory footprint**", phase2)
        self.assertNotRegex(phase2, r"(?i)\*\*`alloc_space` is memory footprint")
        self.assertIn("no pprof view is RSS", phase2)

    def test_interleaving_is_abba_not_ab_ab(self) -> None:
        phase2 = md_section(self.text, "### Phase 2 — Run & Profile")
        self.assertIn("**ABBA** order", phase2)
        self.assertIn("the lead side swaps each", phase2)
        self.assertNotRegex(phase2, r"(?i)\*\*AB-AB\*\*|old always leads")

    def test_evidence_gate_modes_are_exactly_the_contract_values(self) -> None:
        """Round 1 shipped an Output Contract no gate outcome could satisfy. Derive the
        reachable values from the gate table instead of listing them twice."""
        gate = md_section(self.text, "### 1) Evidence Gate — Before You Start: Honest Degradation")
        modes, bases = set(), set()
        for row in md_rows(gate):
            if len(row) >= 3 and row[1].startswith("`"):
                modes.add(row[1].strip("`"))
                bases.add(row[2].strip("`"))
        self.assertEqual({"write", "review", "analyze", "none"}, modes)
        self.assertEqual({"static analysis only", "benchmark output", "pprof profile", "none"},
                         bases)
        contract = md_section(self.text, "## Output Contract")
        for value in modes | bases:
            with self.subTest(value=value):
                self.assertIn(f"`{value}`", contract,
                              f"the gate can produce {value!r} but the contract forbids it")


class MeasuredClaimsPinnedTests(unittest.TestCase):
    """Facts this skill corrected against a real measurement, pinned in their own file.

    Each of these was wrong in a shipped release and fixed with a measurement. A
    whole-document `assertIn` cannot tell the corrected statement from its inverse, so the
    negation is asserted alongside the claim.
    """

    CASES = [
        (BENCHSTAT_GUIDE, "**benchstat reports medians, not means.**",
         r"(?i)benchstat reports means, not medians"),
        (BENCHSTAT_GUIDE, "**Confidence-interval range** around the median",
         r"(?i)`± 1%` \| \*\*Coefficient of variation"),
        (BENCHSTAT_GUIDE, "the standard error shrinks with the *square root*",
         r"(?i)standard error shrinks linearly"),
        (OPT_PATTERNS, 'So the rule is "boxing that **escapes** allocates"',
         r'(?i)the rule is simply "boxing allocates"'),
        (PPROF_ANALYSIS, "`runtime/pprof` documents `-inuse_space` as the",
         r"(?i)documents `-alloc_space` as the\s*\n?default"),
        (BENCH_ANTIPATTERNS, "The allocation figures are byte-identical.",
         r"(?i)allocation figures differ sharply"),
        (BENCH_PATTERNS, "← `_ = add(...)`: EQUAL to baseline, call eliminated",
         r"(?i)`_ = add\(\.\.\.\)`: ABOVE baseline, call survives"),
        (BENCHSTAT_GUIDE, "## Interleave A and B — do not run all of A, then all of B",
         r"(?m)^## Run all of A, then all of B"),
    ]

    def test_loop_overhead_figures_keep_their_order_of_magnitude(self) -> None:
        """The whole sub-nanosecond exception rests on `b.Loop()` costing ~1.7 ns against a
        ~0.23 ns empty classic loop. Flip either number and the rule inverts silently."""
        text = _read(BENCH_PATTERNS)
        loop = re.search(r"BenchmarkLoopEmpty-\d+\s+([\d.]+) ns/op", text)
        classic = re.search(r"BenchmarkClassicEmpty-\d+\s+([\d.]+) ns/op", text)
        self.assertIsNotNone(loop, "the b.Loop empty-harness figure is gone")
        self.assertIsNotNone(classic, "the classic empty-loop figure is gone")
        lo, cl = float(loop.group(1)), float(classic.group(1))
        self.assertGreater(lo, cl * 3,
                           f"b.Loop ({lo}) is no longer materially dearer than the classic "
                           f"loop ({cl}); the sub-nanosecond exception has no basis")
        self.assertGreater(lo, 1.0, "a sub-1ns b.Loop cost would not justify the exception")

    def test_ap5_pool_table_still_shows_gc_off_suppressing_new(self) -> None:
        """AP-5's second experiment only makes its point if GC-on runs `New` far more often
        than GC-off. Parsed from the table, so editing the numbers to agree fails here."""
        ap = md_section(_read(BENCH_ANTIPATTERNS),
                        "## AP-5: Disabling GC to \"stabilise\" allocation counts")
        # Anchor on the Pool.New table specifically: experiment 1's table also has GC
        # on/off rows, and matching the first one compares B/op against itself (1024 vs
        # 1024) — a guard that can never fail is not a guard.
        pool = ap[ap.index("`Pool.New` calls"):] if "`Pool.New` calls" in ap else ""
        self.assertTrue(pool, "AP-5 lost its Pool.New experiment")
        on = re.search(r"\| GC on \| ([\d, ]+) \|", pool)
        off = re.search(r"\| GC off \| ([\d, ]+) \|", pool)
        self.assertIsNotNone(on, "AP-5 lost its GC-on row")
        self.assertIsNotNone(off, "AP-5 lost its GC-off row")
        on_vals = [int(x) for x in on.group(1).split(",")]
        off_vals = [int(x) for x in off.group(1).split(",")]
        self.assertGreater(min(on_vals), max(off_vals) * 5,
                           f"GC-on {on_vals} no longer dwarfs GC-off {off_vals}; the "
                           f"sync.Pool exception AP-5 documents has lost its evidence")

    def test_the_gc_script_actually_disables_gc(self) -> None:
        """`gc_claim_check.sh` is the evidence behind every AP-5 number. A run that leaves
        the collector on produces two identical columns and a quietly meaningless table."""
        src = (SKILL_DIR / "scripts" / "gc_claim_check.sh").read_text(encoding="utf-8")
        self.assertIn("SetGCPercent(-1)", src,
                      "the GC-off arm no longer switches the collector off")
        self.assertRegex(src, r"SMOKE_POOL_ITERS=\d+")
        self.assertRegex(src, r"FULL_POOL_ITERS=\d+")

    def test_each_corrected_claim_survives_and_its_inverse_does_not(self) -> None:
        for path, claim, inverse in self.CASES:
            with self.subTest(file=path.name, claim=claim[:40]):
                text = _read(path)
                self.assertIn(claim, text, f"{path.name}: corrected claim removed")
                self.assertNotRegex(text, inverse, f"{path.name}: claim inverted")

    STAMP = re.compile(r"go1\.\d+\.\d+ \S+/\S+.*20\d\d-\d\d-\d\d")

    def test_every_measured_block_carries_its_own_provenance_stamp(self) -> None:
        """A figure without toolchain/platform/date is not re-checkable, and this skill's own
        AP-5 says evidence that drifts from its source is worse than none.

        Scoped per stamp, not per file: the first version searched the whole document, so
        gutting one `<!-- measured: … -->` comment passed on the strength of a different
        table's stamp two screens away.
        """
        for path in (BENCH_ANTIPATTERNS,):
            text = _read(path)
            stamps = re.findall(r"<!-- measured: (.*?) -->", text)
            self.assertGreaterEqual(len(stamps), 2,
                                    f"{path.name}: a measured table lost its stamp comment")
            for stamp in stamps:
                with self.subTest(file=path.name, stamp=stamp[:40]):
                    self.assertRegex(stamp, self.STAMP,
                                     "a measured block's stamp no longer names toolchain, "
                                     "platform and date")

    def test_the_stamp_guard_rejects_a_gutted_stamp(self) -> None:
        """Anti-vacuity: the pattern must reject the shapes people actually write."""
        for bad in ("recently", "go1.26.1", "darwin/arm64 2026-07-29", "2026-07-29"):
            with self.subTest(stamp=bad):
                self.assertNotRegex(bad, self.STAMP)
        self.assertRegex("go1.26.1 darwin/arm64, Apple M4, 2026-07-29", self.STAMP)

    def test_ap3_justifies_itself_with_a_measurement(self) -> None:
        """AP-3 asserted a modulo cost it never measured; measured, the two forms are
        indistinguishable. The entry must not return to arguing from the arithmetic."""
        ap = md_section(_read(BENCH_ANTIPATTERNS),
                        "## AP-3: Using b.N to index into a pre-generated data slice")
        self.assertIn("**The modulo is not the problem.**", ap)
        self.assertNotRegex(ap, r"(?i)introduces modulo operation in hot loop",
                            "AP-3 is back to citing an unmeasured modulo cost")
        self.assertRegex(ap, r"(?i)working set", "AP-3 lost the real reason")

    def test_live_profiling_path_is_paved(self) -> None:
        """The Scope Gate sends the reader to 'profile the running program'. For a full
        release that instruction had no supporting content anywhere in the skill."""
        scope = md_section(_read(SKILL_MD), "### 3) Scope Gate — Pick the right benchmark shape before writing")
        self.assertIn("running program", scope)
        pprof = _read(PPROF_ANALYSIS)
        for needle in ("net/http/pprof", "/debug/pprof/profile?seconds=", "127.0.0.1"):
            with self.subTest(needle=needle):
                self.assertIn(needle, pprof,
                              "pprof-analysis.md does not show how to profile a live process")

    def test_pgo_is_documented(self) -> None:
        """Phase 2 produces exactly the CPU profile PGO consumes; the skill used to stop
        one step short of the zero-code-change win."""
        pprof = _read(PPROF_ANALYSIS)
        self.assertIn("default.pgo", pprof)
        self.assertRegex(pprof, r"(?i)profile-guided optimization")

    def test_pool_examples_cap_what_they_return(self) -> None:
        """An uncapped sync.Pool turns a memory optimisation into a memory leak: one
        oversized item keeps its capacity pinned for every worker that touches it."""
        for path in (SKILL_MD, OPT_PATTERNS):
            with self.subTest(file=path.name):
                text = _read(path)
                self.assertIn("maxPooled", text,
                              f"{path.name}: sync.Pool example returns an uncapped buffer")
                self.assertRegex(text, r"buf\.Cap\(\) <= maxPooled")


if __name__ == "__main__":
    unittest.main()

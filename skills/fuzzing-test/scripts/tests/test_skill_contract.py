import re
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
APP_REF = SKILL_DIR / "references" / "applicability-checklist.md"
CI_REF = SKILL_DIR / "references" / "ci-strategy.md"
CRASH_REF = SKILL_DIR / "references" / "crash-handling.md"
TARGET_REF = SKILL_DIR / "references" / "target-priority.md"
ANTI_EXAMPLES_REF = SKILL_DIR / "references" / "anti-examples.md"


def frontmatter(text: str) -> str:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError("missing yaml frontmatter")
    return match.group(1)


class FrontmatterTests(unittest.TestCase):
    def test_frontmatter_name(self) -> None:
        fm = frontmatter(SKILL_MD.read_text())
        self.assertIn("name: fuzzing-test", fm)

    def test_frontmatter_description_keywords(self) -> None:
        fm = frontmatter(SKILL_MD.read_text())
        self.assertIn("applicability gate first", fm)
        self.assertIn("Go 1.18+", fm)


class CoreGateTests(unittest.TestCase):
    def test_applicability_gate_exists(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Applicability Gate (Must Run First)", content)

    def test_target_priority_gate_exists(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Target Priority Gate", content)

    def test_risk_cost_gate_exists(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Risk and Cost Gate", content)

    def test_execution_integrity_gate_exists(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Execution Integrity Gate", content)

    def test_applicability_hard_stop_items(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Applicability Verdict: Not suitable for fuzzing", content)
        self.assertIn("suggest alternative strategy", content)

    def test_five_applicability_checks(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("meaningful input space", content)
        self.assertIn("fuzz-supported parameter types", content)
        self.assertIn("clear oracle/invariant", content)
        self.assertIn("deterministic/local", content)
        self.assertIn("fast enough for high-iteration", content)

    def test_cost_classes(self) -> None:
        content = SKILL_MD.read_text()
        for cls in ("Low", "Medium", "High"):
            self.assertIn(cls, content)


class TemplateTests(unittest.TestCase):
    def test_template_a_parser(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Template A: Parser", content)
        self.assertIn("FuzzParseXxx", content)

    def test_template_b_roundtrip(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Template B: Round-Trip", content)
        self.assertIn("FuzzRoundTripXxx", content)

    def test_template_c_differential(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Template C: Differential", content)
        self.assertIn("FuzzDiffXxx", content)

    def test_template_d_struct_aware(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Template D: Struct-Aware", content)
        self.assertIn("FuzzProcessRequest", content)

    def test_templates_have_f_add(self) -> None:
        content = SKILL_MD.read_text()
        self.assertGreaterEqual(content.count("f.Add("), 4)

    def test_templates_have_size_guard(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("len(data) >", content)


class AntiExampleTests(unittest.TestCase):
    # Anti-examples moved to references/anti-examples.md (progressive disclosure).
    # SKILL.md contains a contractual reference; full content lives in the reference file.

    def test_anti_examples_section_exists(self) -> None:
        # Section heading stays in SKILL.md as the contractual reference anchor
        skill = SKILL_MD.read_text()
        ref = ANTI_EXAMPLES_REF.read_text()
        self.assertTrue(
            "Anti-Examples (Common Fuzzing Mistakes)" in skill or
            "Anti-Examples" in ref,
            "anti-examples section not found in SKILL.md or references/anti-examples.md",
        )

    def test_minimum_anti_example_count(self) -> None:
        # Full catalog is in references/anti-examples.md
        content = ANTI_EXAMPLES_REF.read_text()
        count = len(re.findall(r"### Mistake \d+:", content))
        self.assertGreaterEqual(count, 7, f"expected >=7 anti-examples in reference file, got {count}")

    def test_anti_examples_have_bad_good_pairs(self) -> None:
        content = ANTI_EXAMPLES_REF.read_text()
        self.assertIn("// BAD:", content)
        self.assertIn("// GOOD:", content)

    def test_key_anti_examples_present(self) -> None:
        content = ANTI_EXAMPLES_REF.read_text()
        self.assertIn("trivial function", content.lower())
        self.assertIn("No oracle", content)
        self.assertIn("Skip rate", content)
        self.assertIn("OOM", content)
        self.assertIn("global/external state", content)


class ScorecardTests(unittest.TestCase):
    def test_scorecard_section_exists(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Quality Scorecard", content)

    def test_scorecard_critical_tier(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Critical (all must pass", content)
        self.assertIn("C1", content)
        self.assertIn("C2", content)
        self.assertIn("C3", content)

    def test_scorecard_standard_tier(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Standard (", content)
        for item in ("S1", "S2", "S3", "S4", "S5"):
            self.assertIn(item, content)

    def test_scorecard_hygiene_tier(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Hygiene (", content)
        for item in ("H1", "H2", "H3", "H4"):
            self.assertIn(item, content)

    def test_scorecard_pass_fail_rule(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Any Critical fails", content)
        self.assertIn("overall FAIL", content)


class GoVersionAndAdvancedTests(unittest.TestCase):
    def test_version_gate_section(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Go Version Gate", content)

    def test_version_table_entries(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("1.18", content)
        self.assertIn("1.20", content)
        self.assertIn("1.21", content)
        self.assertIn("1.22", content)

    def test_race_detection_fuzz(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Race Detection + Fuzz", content)
        self.assertIn("-race", content)

    def test_worker_parallelism(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Fuzz Worker Parallelism", content)
        self.assertIn("GOMAXPROCS", content)
        self.assertIn("-parallel", content)

    def test_go_fuzz_headers(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("go-fuzz-headers", content)
        self.assertIn("GenerateStruct", content)

    def test_performance_baseline(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Fuzz Performance Baseline", content)
        self.assertIn("execs/sec", content)


class FuzzVsPropertyTests(unittest.TestCase):
    def test_comparison_table(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Fuzz vs Property-Based Testing", content)
        self.assertIn("rapid", content)
        self.assertIn("gopter", content)

    def test_decision_rules(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("Use fuzz", content)
        self.assertIn("Use property-based", content)
        self.assertIn("Use both", content)


class ReferenceDepthTests(unittest.TestCase):
    def test_applicability_has_concrete_examples(self) -> None:
        content = APP_REF.read_text()
        self.assertIn("Suitable for Fuzzing", content)
        self.assertIn("NOT Suitable for Fuzzing", content)
        self.assertIn("Borderline Cases", content)

    def test_applicability_has_go_code(self) -> None:
        content = APP_REF.read_text()
        self.assertIn("func ", content)
        self.assertGreaterEqual(content.count("// Check"), 5)

    def test_target_priority_has_go_examples(self) -> None:
        content = TARGET_REF.read_text()
        self.assertIn("Tier 1 Example:", content)
        self.assertIn("Tier 2 Example:", content)
        self.assertIn("De-Prioritize Example:", content)
        self.assertIn("func ", content)

    def test_target_priority_has_flowchart(self) -> None:
        content = TARGET_REF.read_text()
        self.assertIn("Quick Decision Flowchart", content)

    def test_ci_strategy_two_lanes(self) -> None:
        content = CI_REF.read_text()
        self.assertIn("PR Lane", content)
        self.assertIn("Scheduled Lane", content)

    def test_crash_handling_template(self) -> None:
        content = CRASH_REF.read_text()
        self.assertIn("Crash Report Template", content)
        self.assertIn("Post-Fix Checklist", content)


class OracleRuleConsistencyTests(unittest.TestCase):
    """C2 used to demand a `t.Fatal`/`t.Errorf` token in every harness, which mechanically
    rejected the no-panic robustness oracle the Applicability Gate explicitly accepts.
    These tests pin the reconciled rule."""

    def test_gate_accepts_no_panic_oracle(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("no panic for any input", content)

    def test_c2_is_not_a_token_search(self) -> None:
        """The rule stays in SKILL.md; the full pass/fail table lives in the gate reference."""
        skill = SKILL_MD.read_text()
        self.assertIn("Observable oracle present", skill)
        self.assertIn("not the presence of a `t.Fatal` call", skill)
        self.assertIn("Do not grade C2 by searching for an API token", APP_REF.read_text())

    def test_c2_documents_both_accepted_oracle_forms(self) -> None:
        ref = APP_REF.read_text()
        self.assertIn("Oracle Forms", ref)
        self.assertIn("no-panic / robustness", ref)
        self.assertIn("No `t.Fatal` is required", ref,
                      "a robustness harness with no assertion must remain legal")

    def test_c2_still_rejects_the_declared_oracle_mismatch(self) -> None:
        skill = SKILL_MD.read_text()
        ref = APP_REF.read_text()
        self.assertIn("mismatch", skill.lower(), "SKILL.md must name the mismatch failure")
        self.assertIn("declared round-trip at the gate", ref)

    def test_skill_md_points_at_the_oracle_reference(self) -> None:
        """Progressive disclosure: moved detail must stay reachable from the main file."""
        skill = SKILL_MD.read_text()
        self.assertIn("references/applicability-checklist.md` (§Oracle Forms)", skill)


class TemplateSeedQualityTests(unittest.TestCase):
    """Templates are the most-copied artefact, so they must satisfy the skill's own S1 bar
    (>=3 structurally distinct seeds) and be marked as placeholders."""

    def _templates(self) -> list:
        text = SKILL_MD.read_text()
        blocks = re.findall(r"```go\n(.*?)```", text, re.DOTALL)
        return [b for b in blocks if "func Fuzz" in b]

    def test_every_template_has_at_least_three_seeds(self) -> None:
        for tpl in self._templates():
            name = re.search(r"func (Fuzz\w+)", tpl).group(1)
            seeds = tpl.count("f.Add(")
            self.assertGreaterEqual(
                seeds, 3, f"{name}: scorecard S1 wants >=3 distinct seeds, template has {seeds}"
            )

    def test_every_template_marks_seeds_as_placeholders(self) -> None:
        for tpl in self._templates():
            name = re.search(r"func (Fuzz\w+)", tpl).group(1)
            self.assertIn("PLACEHOLDER SEEDS", tpl,
                          f"{name}: seeds must be marked as placeholders to replace")

    def test_placeholder_note_points_at_seed_mining(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("placeholders are not", content.lower())
        self.assertIn("Seed mining strategy", content)


class FuzzFlagSemanticsTests(unittest.TestCase):
    """`-fuzz` must match exactly one target; `-fuzz=^Fuzz` fails outright in any package
    with two or more targets. Verified against the toolchain:
    'testing: will not fuzz, -fuzz matches more than one fuzz test'."""

    def test_single_target_rule_documented(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("must match **exactly one** target", content)
        self.assertIn("matches more than one fuzz test", content)

    def test_no_broken_multi_target_fuzz_command(self) -> None:
        """Flag only runnable commands. Prose that names `-fuzz='^Fuzz'` as the anti-pattern
        is required documentation, so the check is scoped to lines that invoke `go test`."""
        for path in (SKILL_MD, CI_REF):
            bad = [
                line.strip()
                for line in path.read_text().splitlines()
                if re.search(r"(?:go|\$\(GO\)) test", line)
                and re.search(r"-fuzz='?\^Fuzz'?(?![\w$])", line)
            ]
            self.assertFalse(
                bad, f"{path.name}: -fuzz='^Fuzz' matches multiple targets and fails at "
                     f"runtime; anchor per target instead. Offending lines: {bad}"
            )

    def test_replay_uses_run_not_fuzz(self) -> None:
        content = SKILL_MD.read_text()
        self.assertIn("-run='^Fuzz'", content,
                      "corpus replay across targets must use -run, not -fuzz")


class CrashArtifactGlobTests(unittest.TestCase):
    """A crash lands in the target package's own testdata/fuzz (fuzzing ./pkg/parser/ writes
    pkg/parser/testdata/fuzz/). A root-anchored `testdata/fuzz/**` upload glob therefore
    captures nothing, and the crasher dies with the workspace."""

    def test_upload_glob_is_recursive(self) -> None:
        ci = CI_REF.read_text()
        self.assertIn("path: '**/testdata/fuzz/**'", ci,
                      "crash upload glob must be '**/testdata/fuzz/**' to reach subpackages")

    def test_no_root_anchored_upload_path(self) -> None:
        bad = [
            line.strip() for line in CI_REF.read_text().splitlines()
            if re.match(r"\s*path:\s*'?testdata/fuzz", line)
        ]
        self.assertFalse(bad, f"root-anchored artifact path misses subpackages: {bad}")

    def test_missing_crasher_fails_loudly(self) -> None:
        ci = CI_REF.read_text()
        self.assertIn("if-no-files-found: error", ci,
                      "a failed fuzz run that uploads no crasher means the glob is wrong")

    def test_subpackage_path_documented(self) -> None:
        ci = CI_REF.read_text()
        self.assertIn("pkg/parser/testdata/fuzz", ci)
        self.assertIn("not the repo root", ci)


class CoverageDocConsistencyTests(unittest.TestCase):
    """COVERAGE.md drifted to claiming 8 fixtures / 60 tests when there were 14 / 64.
    These assertions make the counts self-checking instead of hand-maintained."""

    COVERAGE = SKILL_DIR / "scripts" / "tests" / "COVERAGE.md"
    GOLDEN = SKILL_DIR / "scripts" / "tests" / "golden"

    def test_declared_fixture_count_matches_disk(self) -> None:
        actual = len(list(self.GOLDEN.glob("*.json")))
        text = self.COVERAGE.read_text()
        m = re.search(r"\*\*Golden fixture count: (\d+)\*\*", text)
        self.assertIsNotNone(m, "COVERAGE.md must declare a golden fixture count")
        self.assertEqual(actual, int(m.group(1)),
                         f"COVERAGE.md says {m.group(1)} fixtures, disk has {actual}")

    def test_every_fixture_listed_in_coverage_doc(self) -> None:
        text = self.COVERAGE.read_text()
        missing = [p.name for p in sorted(self.GOLDEN.glob("*.json")) if p.name not in text]
        self.assertFalse(missing, f"fixtures absent from COVERAGE.md: {missing}")

    def test_no_satisfied_gap_still_listed(self) -> None:
        """Known Gaps listed borderline and go-fuzz-headers fixtures that already exist."""
        text = self.COVERAGE.read_text()
        gaps = text.split("## Known Gaps")[-1] if "## Known Gaps" in text else ""
        for stale in ("borderline/soft-warning case", "`go-fuzz-headers` specific scenario"):
            self.assertNotIn(stale, gaps,
                             f"Known Gaps still lists a gap that is now covered: {stale}")

    def test_behavioral_eval_documented(self) -> None:
        text = self.COVERAGE.read_text()
        self.assertIn("test_llm_fuzz_eval.py", text)
        self.assertIn("frame_parser", text)
        self.assertIn("kv_codec", text)

    def test_declared_anti_example_count_matches_reference(self) -> None:
        actual = len(re.findall(r"(?m)^### Mistake \d+:", ANTI_EXAMPLES_REF.read_text()))
        text = self.COVERAGE.read_text()
        m = re.search(r"\| Anti-examples \((\d+)\) \| (\d+) \|", text)
        self.assertIsNotNone(m, "COVERAGE.md must declare an anti-example count")
        self.assertEqual(actual, int(m.group(1)),
                         f"COVERAGE.md says {m.group(1)} anti-examples, reference has {actual}")
        self.assertEqual(actual, int(m.group(2)))

    def test_skill_md_anti_example_count_matches_reference(self) -> None:
        actual = len(re.findall(r"(?m)^### Mistake \d+:", ANTI_EXAMPLES_REF.read_text()))
        m = re.search(r"`anti-examples\.md` — (\d+) BAD/GOOD", SKILL_MD.read_text())
        self.assertIsNotNone(m, "SKILL.md must cite the anti-example count")
        self.assertEqual(actual, int(m.group(1)),
                         f"SKILL.md cites {m.group(1)} anti-examples, reference has {actual}")


if __name__ == "__main__":
    unittest.main()

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
TUNING_REF = SKILL_DIR / "references" / "advanced-tuning.md"


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
        self.assertIn("dropping the result", content.lower())
        # A robustness harness legitimately has no assertion: the reference must not
        # contradict scorecard C2 by demanding one unconditionally.
        self.assertNotIn("always assert an invariant", content.lower())
        self.assertIn("no-panic / robustness harness is NOT this mistake", content)
        self.assertIn("Skip rate", content)
        self.assertIn("OOM", content)
        self.assertIn("global/external state", content)


class ExecutableCommandTests(unittest.TestCase):
    """Commands in the docs are copied verbatim, so a command that cannot run is a defect.
    These pin the ones that were wrong."""

    def test_coverage_workflow_does_not_combine_coverprofile_with_fuzz(self) -> None:
        """`go test -fuzz=... -coverprofile=...` is rejected by the toolchain:
        'cannot use -coverprofile flag with -fuzz flag' (verified on Go 1.25/1.26)."""
        tuning = TUNING_REF.read_text()
        for line in tuning.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or not stripped.startswith("go test"):
                continue
            if "-fuzz=" in stripped or "-fuzz " in stripped:
                self.assertNotIn("-coverprofile", stripped,
                                 f"command combines -fuzz with -coverprofile: {stripped}")
        self.assertIn("cannot use -coverprofile flag with -fuzz flag", tuning,
                      "the reference must show the error so the reader recognises it")
        self.assertIn("-run='^FuzzXxx$' -coverprofile=", tuning,
                      "the replay-based profiling step must be spelled out")

    def test_pr_lane_preserves_and_surfaces_a_quick_fuzz_finding(self) -> None:
        """continue-on-error keeps the merge queue moving; without an artifact upload it
        also destroys the crasher and reports green."""
        ci = CI_REF.read_text()
        self.assertIn("continue-on-error: true", ci)
        self.assertIn("steps.quickfuzz.outcome == 'failure'", ci,
                      "the swallowed failure must drive follow-up steps")
        self.assertIn("pr-fuzz-crash-", ci, "the PR lane must upload the crashing input")
        # Present is not enough: a disabled step still matches a keyword search.
        pr_lane = ci.split("## Scheduled Lane")[0]
        self.assertNotIn("if: false", pr_lane, "the crash-upload step is disabled")
        upload = pr_lane[pr_lane.index("- name: Upload crash corpus"):]
        upload_block = upload[:upload.index("- name: Report")]
        self.assertIn("if: steps.quickfuzz.outcome == 'failure'", upload_block,
                      "the upload must be conditioned on the quick-fuzz failure")
        self.assertIn("uses: actions/upload-artifact", upload_block)
        self.assertNotIn("DISABLED", pr_lane)
        self.assertIn("::warning", ci, "a swallowed crash must still be visible")
        self.assertIn("merge-queue", ci.lower(),
                      "the reference must say what continue-on-error does and does not mean")


class RuleConsistencyTests(unittest.TestCase):
    """Rules that appear in more than one file must not contradict each other: an agent
    that loads a different reference would otherwise reach a different decision."""

    def test_external_dependency_rule_has_one_stated_precedence(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("Soft warning ≠ fuzz the live dependency", skill)
        self.assertIn("this is the binding statement", skill.lower())
        # Gate item 4 stays a soft warning; the guardrail still bans live I/O in the harness.
        self.assertIn("soft warnings", skill.lower())
        self.assertIn("Do not fuzz targets requiring live DB/network unless fully stubbed.", skill)

    @staticmethod
    def _flat(text: str) -> str:
        """Collapse whitespace: a rule can be re-wrapped without changing its meaning."""
        return re.sub(r"\s+", " ", text.lower())

    def test_oracle_rule_is_identical_in_all_three_places(self) -> None:
        skill = SKILL_MD.read_text()
        app = APP_REF.read_text()
        anti = ANTI_EXAMPLES_REF.read_text()
        for text, name in ((skill, "SKILL.md"), (app, "applicability-checklist.md"),
                           (anti, "anti-examples.md")):
            self.assertNotIn("always assert an invariant", self._flat(text),
                             f"{name} contradicts C2's no-panic form")
        self.assertIn("needs no assertion", self._flat(skill))
        for text, name in ((app, "applicability-checklist.md"), (anti, "anti-examples.md")):
            self.assertIn("no `t.fatal` is required", self._flat(text),
                          f"{name} must state the no-panic exemption in the same words")


def flat_text(path) -> str:
    """Lowercase, emphasis-free, whitespace-collapsed text.

    Prose assertions pinned exact sentences, so a rewording read as a missing rule. What
    these tests must pin is the RULE, not its layout."""
    return re.sub(r"\s+", " ", path.read_text().lower().replace("*", "").replace("`", ""))


class RoundTripOracleTests(unittest.TestCase):
    """The round-trip template is the most-copied artefact with a wrong-oracle failure mode."""

    def test_template_b_ships_a_domain_guard(self) -> None:
        skill = SKILL_MD.read_text()
        flat = flat_text(SKILL_MD)
        self.assertIn("domain guard", flat)
        # The guard must be in the TEMPLATE, not only described in prose around it.
        template = [b for b in re.findall(r"```go\n(.*?)```", skill, re.DOTALL)
                    if "func FuzzRoundTrip" in b]
        self.assertEqual(1, len(template), "expected exactly one round-trip template")
        self.assertIn("utf8.ValidString", template[0],
                      "the round-trip template must carry the guard, not just mention it")
        self.assertIn("t.Skip()", template[0])
        self.assertIn("u+fffd", flat)

    def test_template_b_documents_the_normalizing_variant_and_its_weakness(self) -> None:
        flat = flat_text(SKILL_MD)
        self.assertIn("value-level idempotence", flat)
        self.assertIn("decoded values", flat)
        self.assertIn("never encoded bytes", flat)
        self.assertIn("strictly weaker", flat)

    def test_template_b_requires_verifying_the_oracle(self) -> None:
        skill = SKILL_MD.read_text()
        self.assertIn("-fuzztime=10s .  # must stay clean", skill)

    def test_failure_triage_does_not_presume_the_implementation_is_correct(self) -> None:
        """A rule that reads "you believe the code is correct, so the test is wrong" pushes
        an agent to widen guards until the suite is green again — the opposite of why
        fuzzing exists. Triage must be decided from the contract, with the reproducer kept
        either way.

        Matched on normalized text so a rewording is not a failure: what is pinned is that
        both verdicts stay reachable, that belief is explicitly rejected as evidence, and
        that the reproducer survives."""
        # Strip emphasis as well as whitespace: **implementation** and implementation are
        # the same rule, and a test that cannot see that pins formatting, not meaning.
        flat = re.sub(r"\s+", " ", SKILL_MD.read_text().lower().replace("*", ""))
        self.assertIn("triage against the contract", flat)
        self.assertIn("is not evidence", flat)
        self.assertIn("the harness is wrong", flat)
        self.assertIn("the implementation is wrong", flat)
        self.assertIn("keep the reproducer", flat)
        for banned in ("means the oracle or the guard is wrong, not the code",
                       "fix the harness before filing a bug"):
            self.assertNotIn(banned, flat,
                             f"reinstated a rule that presumes the code is correct: {banned}")


class SeedRuleTests(unittest.TestCase):
    def test_seed_mining_has_a_fallback_for_projects_with_no_corpus(self) -> None:
        """'Mine real data, never invent seeds' is unactionable in a new package. Without a
        stated fallback the two rules cannot both be satisfied.

        Pinned as a rule, not a sentence: a fallback must exist, derive seeds from the
        declared contract, label them, and require verification."""
        flat = flat_text(SKILL_MD)
        self.assertIn("nothing to mine", flat)
        self.assertIn("constructed (no corpus available)", flat)
        self.assertIn("declared contract", flat)
        self.assertIn("go test -run='^fuzz' .", flat)

    def test_dead_seed_rule_is_documented(self) -> None:
        flat = flat_text(SKILL_MD)
        self.assertIn("dead weight", flat)
        self.assertIn("--- skip:", flat)


class MeasuredClaimTests(unittest.TestCase):
    def test_deserialization_costs_state_their_conditions(self) -> None:
        """Absolute per-op numbers without a machine, a Go version, and a payload are not
        reproducible. The prior table's figures were wrong by 10-100x and mis-ordered."""
        skill = SKILL_MD.read_text()
        self.assertIn("ns/op", skill)
        self.assertIn("Conditions:", skill)
        self.assertIn("go test -run='^$' -bench=. -benchmem", skill)
        self.assertNotIn("~10-50 μs/op", skill)
        self.assertIn("Re-measure", skill)


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

    def test_version_gate_states_the_only_hard_stop(self) -> None:
        """SKILL.md owns the gate (the 1.18 hard stop); per-release detail lives in the
        reference. Duplicating the release table in both drifts."""
        content = SKILL_MD.read_text()
        self.assertIn("1.18", content)
        self.assertIn("hard stop", content.lower())
        self.assertIn("applicability-checklist.md", content)
        tuning = TUNING_REF.read_text()
        for release in ("1.20", "1.22", "1.23"):
            self.assertIn(release, tuning, f"{release} missing from advanced-tuning.md")

    def test_rangefunc_version_is_accurate(self) -> None:
        """Range-over-func is a Go 1.23 language feature; in 1.22 it needed
        GOEXPERIMENT=rangefunc. Stating it as a plain 1.22 capability misleads anyone
        writing a harness that must run on 1.22."""
        tuning = TUNING_REF.read_text()
        self.assertIn("GOEXPERIMENT=rangefunc", tuning)
        self.assertIn("1.23", tuning)
        self.assertNotIn("| 1.22+ | Range function support", tuning)

    def test_tuning_topics_live_in_the_reference_and_are_linked(self) -> None:
        """These four were duplicated in SKILL.md and the reference. The reference owns
        them; SKILL.md must still route the reader there."""
        skill = SKILL_MD.read_text()
        tuning = TUNING_REF.read_text()
        for heading, token in (
            ("Race Detection + Fuzz", "-race"),
            ("Fuzz Worker Parallelism", "GOMAXPROCS"),
            ("Structured Input with `go-fuzz-headers`", "GenerateStruct"),
            ("Fuzz Performance Baseline", "execs/sec"),
        ):
            self.assertIn(heading, tuning, f"advanced-tuning.md lost: {heading}")
            self.assertIn(token, tuning, f"advanced-tuning.md lost: {token}")
        self.assertIn("advanced-tuning.md", skill)
        self.assertIn("execs/sec", skill, "SKILL.md must still name the baseline metric")
        self.assertIn("go-fuzz-headers", skill)


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
        self.assertIn("they are still\nplaceholders", content.lower())
        self.assertIn("Seed mining strategy", content)

    def test_s1_criterion_matches_what_the_templates_ship(self) -> None:
        """S1 used to demand ">=3 structurally distinct VALID inputs" while the templates
        shipped a deliberately malformed seed and claimed to satisfy it. One of the two had
        to move; the criterion did, because a malformed seed is exactly what a parser
        harness needs."""
        content = SKILL_MD.read_text()
        s1 = [ln for ln in content.splitlines() if ln.startswith("| S1 ")]
        self.assertEqual(1, len(s1), "expected exactly one S1 row")
        row = s1[0]
        self.assertIn("at least one valid", row.lower())
        self.assertNotIn("distinct valid inputs", row)
        self.assertIn("reaching the region", row.lower())


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

    def test_declared_test_counts_match_the_collected_suite(self) -> None:
        """A deleted or renamed test disappears silently: unittest simply collects fewer.

        COVERAGE.md declares a count per file, so comparing it against what the loader
        actually collects turns "someone disabled a check" into a red suite."""
        import importlib.util
        import sys as _sys

        text = self.COVERAGE.read_text()
        declared = {
            "test_skill_contract.py": r"\*\*Contract test count: (\d+)\*\*",
            "test_golden_scenarios.py": r"\*\*Golden test count: (\d+)\*\*",
            "test_templates_compile.py": r"\*\*Template test count: (\d+)\*\*",
            "test_llm_fuzz_eval.py": r"\*\*Behavioral eval count: (\d+)\*\*",
        }
        here = SKILL_DIR / "scripts" / "tests"
        total = 0
        for filename, pattern in declared.items():
            m = re.search(pattern, text)
            self.assertIsNotNone(m, f"COVERAGE.md must declare a count for {filename}")
            spec = importlib.util.spec_from_file_location(f"count_probe_{filename[:-3]}",
                                                          here / filename)
            module = importlib.util.module_from_spec(spec)
            _sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            actual = unittest.defaultTestLoader.loadTestsFromModule(module).countTestCases()
            total += actual
            self.assertEqual(actual, int(m.group(1)),
                             f"COVERAGE.md says {m.group(1)} tests in {filename}, loader "
                             f"collects {actual}")
        m = re.search(r"\*\*Total tests: (\d+)\*\*", text)
        self.assertIsNotNone(m, "COVERAGE.md must declare a total")
        self.assertEqual(total, int(m.group(1)),
                         f"COVERAGE.md total is {m.group(1)}, loader collects {total}")

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

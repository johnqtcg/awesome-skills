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

    def test_idempotence_is_ranked_the_same_way_in_both_files(self) -> None:
        """SKILL.md §Template B measured it — guarded equality caught a sign-flip mutant
        that the idempotent variant missed — and concluded idempotence is *strictly
        weaker*. `anti-examples.md` Mistake 9 said idempotence was "the stronger property".
        An agent that loaded the reference first would pick the weaker oracle, and only
        SKILL.md's half was pinned."""
        skill, anti = self._flat(SKILL_MD.read_text()), self._flat(ANTI_EXAMPLES_REF.read_text())
        for text, name in ((skill, "SKILL.md"), (anti, "anti-examples.md")):
            self.assertIn("strictly weaker", text,
                          f"{name} must state the ranking in the same words")
            self.assertNotIn("idempotence is the stronger property", text,
                             f"{name} reverses the measured ranking")
        # And both must say which one to reach for first.
        for text, name in ((skill, "SKILL.md"), (anti, "anti-examples.md")):
            self.assertIn("fall back to idempotence", text,
                          f"{name} must state the order of preference, not just the ranking")

    def test_crash_report_template_carries_the_triage_verdict_skill_md_mandates(self) -> None:
        """SKILL.md §Crash Handling requires recording the verdict *and its basis* in the
        crash report, and says a harness fix with no cited contract clause is
        indistinguishable from suppressing a bug. The template it points at had no slot for
        either, so the mandated field had nowhere to go."""
        skill = self._flat(SKILL_MD.read_text())
        self.assertIn("record the verdict and its basis in the crash report", skill)
        crash = CRASH_REF.read_text()
        self.assertIn("Triage Verdict", crash)
        self.assertIn("Contract clause:", crash)
        for verdict in ("harness_wrong", "implementation_wrong", "contract_ambiguous"):
            self.assertIn(verdict, crash,
                          "all three triage outcomes SKILL.md defines must be selectable")
        self.assertIn("Triage verdict recorded with its contract clause",
                      crash.split("## Post-Fix Checklist")[-1],
                      "the post-fix checklist must carry the field too, or it is skipped")
        # Section numbering must stay contiguous after the insertion.
        nums = [int(n) for n in re.findall(r"(?m)^### (\d+)\. ", crash)]
        self.assertEqual(list(range(1, len(nums) + 1)), nums,
                         f"crash-report sections are misnumbered: {nums}")


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
        reproducible. The prior table's figures were wrong by 10-100x and mis-ordered.

        The table moved into `advanced-tuning.md` (it is tuning detail, and SKILL.md is
        loaded in full on every trigger); this guard moved with it rather than being
        deleted, and now also requires that SKILL.md still routes to it."""
        tuning = md_section(TUNING_REF.read_text(), "Deserialization Cost in a Harness")
        self.assertIn("ns/op", tuning)
        self.assertIn("Conditions:", tuning)
        self.assertIn("go test -run='^$' -bench=. -benchmem", tuning)
        self.assertNotIn("~10-50 μs/op", tuning)
        self.assertIn("Re-measure", tuning)
        # No measured per-op figure may be restated in SKILL.md — a second copy drifts.
        self.assertNotIn("ns/op", SKILL_MD.read_text())
        self.assertIn("§Deserialization Cost in a Harness", SKILL_MD.read_text(),
                      "SKILL.md must still route to the moved table")

    def test_every_intra_document_anchor_link_resolves(self) -> None:
        """SKILL.md linked to `#go-fuzz-headers-bridge`, an anchor no heading in the file
        produces — the target section lives in `advanced-tuning.md`. A dead anchor sends
        the reader nowhere and nothing checked it."""
        for path in [SKILL_MD, *sorted((SKILL_DIR / "references").glob("*.md"))]:
            text = path.read_text()
            slugs = {re.sub(r"[^a-z0-9\s-]", "", h.lower()).strip().replace(" ", "-")
                     for h in re.findall(r"(?m)^#{1,6}\s+(.+?)\s*$", text)}
            for anchor in re.findall(r"\]\(#([A-Za-z0-9_-]+)\)", text):
                with self.subTest(file=path.name, anchor=anchor):
                    self.assertIn(anchor, slugs,
                                  f"{path.name} links to #{anchor}, which no heading in "
                                  f"that file produces")


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


# --------------------------------------------------------------------------------------
# Structural guards — added after a mutation sweep found the thresholds unpinned
# --------------------------------------------------------------------------------------

def md_section(text: str, heading: str) -> str:
    """Return the body under `heading`, up to the next heading of the same or higher level.

    Scoping is the whole point. `assertIn("$GOCACHE/fuzz", skill)` over a 500-line document
    stays green as long as *any* occurrence survives — measured, swapping the corpus-location
    table back to the pre-fix (wrong) model passed all 141 tests, because the string still
    appeared in Quick Commands.
    """
    lines = text.splitlines()
    for start, line in enumerate(lines):
        if line.startswith("#") and line.lstrip("#").strip() == heading:
            level = len(line) - len(line.lstrip("#"))
            break
    else:
        raise AssertionError(f"heading not found: {heading!r}")
    for end in range(start + 1, len(lines)):
        nxt = lines[end]
        if nxt.startswith("#") and (len(nxt) - len(nxt.lstrip("#"))) <= level:
            return "\n".join(lines[start + 1:end])
    return "\n".join(lines[start + 1:])


def md_tables(section: str) -> list:
    """Every markdown table in `section`, as a list of row-lists (header/separator dropped,
    `**bold**` stripped so emphasis cannot change a cell's value)."""
    tables, rows, seen_header = [], [], False
    for line in section.splitlines() + [""]:
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [c.strip().replace("**", "") for c in stripped.strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            if not seen_header:
                seen_header = True
                continue
            rows.append(cells)
            continue
        if rows:
            tables.append(rows)
        rows, seen_header = [], False
    return tables


class NormativeThresholdTests(unittest.TestCase):
    """Sixteen mutations were applied to this skill's documents; **nine survived the full
    141-test suite**, and every one of them was a number that decides an outcome:

    * all three Quality Scorecard tier bars (`Standard (≥4/5)` -> `≥1/5`, `Hygiene (≥3/4)`
      -> `≥0/4`, and `All Critical pass` -> `≥2/3 Critical pass`),
    * `S1` seed count and `S3` skip rate,
    * the Go version gate (`< 1.18` -> `< 1.22`, reintroducing the false hard stop an
      earlier round removed),
    * the cost-class fuzz budgets,
    * the corpus-location table swapped back to the pre-fix model,
    * five `references/*.md` pointers rewritten to a file that does not exist.

    They survived because the guards asserted a *string appears somewhere in the document*
    and the same string appeared elsewhere — `test_scorecard_standard_tier` checks
    `assertIn("Standard (", content)` and never reads the ratio inside the parentheses;
    `test_scorecard_pass_fail_rule` checks the FAIL half and leaves the PASS half open.

    Each test here was confirmed to FAIL against the mutation it names before being
    committed.
    """

    @classmethod
    def setUpClass(cls):
        cls.skill = SKILL_MD.read_text()

    # --- Quality Scorecard: the bars, derived from the tiers' own row counts ---

    def _tier_bars(self) -> dict:
        section = md_section(self.skill, "Quality Scorecard")
        return {m.group(1): m.group(2)
                for m in re.finditer(r"(?m)^### (Critical|Standard|Hygiene) \((.+?)\)\s*$",
                                     section)}

    def _tier_sizes(self) -> dict:
        """Count the scored items per tier from the tables themselves."""
        section = md_section(self.skill, "Quality Scorecard")
        sizes = {}
        for tier, prefix in (("Critical", "C"), ("Standard", "S"), ("Hygiene", "H")):
            body = md_section(section, [h for h in
                                        re.findall(r"(?m)^### (.+?)$", section)
                                        if h.startswith(tier)][0])
            rows = md_tables(body)[0]
            sizes[tier] = len([r for r in rows if re.fullmatch(prefix + r"\d+", r[0])])
        return sizes

    def test_scorecard_tier_bars_are_pinned_to_their_tier_sizes(self) -> None:
        bars, sizes = self._tier_bars(), self._tier_sizes()
        self.assertEqual({"Critical": 3, "Standard": 5, "Hygiene": 4}, sizes)
        self.assertEqual("all must pass for overall PASS", bars["Critical"])
        # Denominators derived from the tables: adding an item forces the bar to move with it.
        self.assertEqual(f"≥4/{sizes['Standard']} must pass", bars["Standard"])
        self.assertEqual(f"≥3/{sizes['Hygiene']} must pass", bars["Hygiene"])

    def test_scorecard_scoring_rule_pins_both_halves(self) -> None:
        """The PASS half was unguarded: `test_scorecard_pass_fail_rule` only asserts the
        FAIL sentence, so weakening `All Critical pass AND ≥4/5 ... AND ≥3/4 ...` to
        `≥2/3 Critical pass AND ≥2/5 Standard` left the suite green."""
        section = md_section(self.skill, "Quality Scorecard")
        bars = self._tier_bars()
        rule = [ln for ln in section.splitlines() if ln.startswith("- **PASS**")]
        self.assertEqual(1, len(rule), "expected exactly one PASS rule line")
        pass_line = rule[0]
        self.assertIn("All Critical pass", pass_line)
        # The two ratios in the rule must be the two ratios in the tier headings.
        for tier in ("Standard", "Hygiene"):
            ratio = bars[tier].split()[0]          # e.g. "≥4/5"
            self.assertIn(f"{ratio} {tier}", pass_line,
                          f"the PASS rule and the {tier} heading state different bars")
        fail = [ln for ln in section.splitlines() if ln.startswith("- **FAIL**")]
        self.assertEqual(1, len(fail))
        self.assertIn("Any Critical fails", fail[0])
        self.assertIn("regardless of other scores", fail[0])

    def test_seed_and_skip_thresholds_are_pinned_in_their_rows(self) -> None:
        section = md_section(self.skill, "Quality Scorecard")
        rows = {r[0]: " | ".join(r[1:]) for tbl in md_tables(section) for r in tbl}
        self.assertIn("≥3 structurally distinct", rows["S1"],
                      "S1's seed floor decides whether a one-seed harness passes")
        self.assertIn("at least one valid", rows["S1"])
        self.assertIn("estimated skip rate <50%", rows["S3"])
        # The same 50% appears in the Guardrails and in advanced-tuning; they must agree.
        self.assertIn("skip rate exceeds 50%", md_section(self.skill, "Guardrails"))
        self.assertIn(">50% of iterations", TUNING_REF.read_text())

    # --- Go version gate ---

    def test_version_gate_states_exactly_one_hard_stop_and_it_is_118(self) -> None:
        """Raising this to 1.22 reintroduces exactly the false hard stop an earlier round
        removed: `testing.F` is a stdlib symbol, so a `go 1.16` module fuzzes fine under a
        modern toolchain."""
        section = md_section(self.skill, "Go Version Gate")
        stops = re.findall(r"<\s*1\.(\d+)\s*→\s*hard stop", section)
        self.assertEqual(["18"], stops,
                         f"§Go Version Gate declares hard stop(s) at 1.{stops}, want only 1.18")
        self.assertIn("≥ 1.18 → proceed", section)
        # The reference must not disagree — an agent may load either one.
        app = APP_REF.read_text()
        self.assertIn("effective toolchain** is `< 1.18`", app)
        self.assertEqual([], re.findall(r"hard stop.{0,40}<\s*1\.(?!18)\d+", app))

    # --- Cost classes and their budgets ---

    def test_cost_class_budgets_are_pinned(self) -> None:
        section = md_section(self.skill, "Risk and Cost Gate")
        self.assertIn("`Low`: local fuzz 30-60s", section)
        self.assertIn("`Medium`: local fuzz 15-45s", section)
        self.assertIn("`High`: corpus-only in PR", section)
        # Every class named in the classification must also get a budget, or H2
        # ("cost class assigned ... with matching -fuzztime budget") cannot be satisfied.
        classes = set(re.findall(r"(?m)^- `(Low|Medium|High)`: (?!local fuzz|corpus-only)",
                                 section))
        budgets = set(re.findall(r"(?m)^- `(Low|Medium|High)`: (?=local fuzz|corpus-only)",
                                 section))
        self.assertEqual({"Low", "Medium", "High"}, classes)
        self.assertEqual(classes, budgets)

    # --- Corpus location: the fact this skill exists to get right ---

    def _corpus_rows(self, table: list) -> dict:
        out = {}
        for row in table:
            key = ("failing" if "failing input" in row[0].lower()
                   else "interesting" if "interesting" in row[0].lower()
                   else "seed" if "seed corpus" in row[0].lower() else None)
            if key:
                out[key] = row
        return out

    def test_skill_corpus_table_maps_each_input_kind_to_the_right_place(self) -> None:
        section = md_section(self.skill, "Corpus Management")
        rows = self._corpus_rows(md_tables(section)[0])
        self.assertEqual({"failing", "interesting"}, set(rows),
                         "the corpus table must distinguish failing from interesting inputs")

        failing, interesting = rows["failing"], rows["interesting"]
        self.assertIn("testdata/fuzz", failing[1])
        self.assertIn("only on failure", failing[1])
        self.assertIn("commit", failing[2].lower())

        self.assertIn("$GOCACHE/fuzz", interesting[1])
        self.assertNotIn("testdata/fuzz", interesting[1],
                         "interesting inputs do NOT land in testdata/fuzz — a clean run "
                         "does not even create it")
        self.assertIn("never committed", interesting[2].lower())
        self.assertIn("cache", interesting[2].lower())

    def test_ci_reference_corpus_table_agrees_with_the_skill(self) -> None:
        """Same table, second file. It was also structurally broken: a paragraph between
        two rows ended the table, so the `$GOCACHE/fuzz` row rendered as literal pipes."""
        ci = CI_REF.read_text()
        section = md_section(ci, "Where Go Actually Stores Corpus (read before writing any cache step)")
        tables = md_tables(section)
        self.assertEqual(1, len(tables),
                         "the corpus table is split in two — a paragraph between rows ends "
                         "a markdown table and orphans everything after it")
        rows = self._corpus_rows(tables[0])
        self.assertEqual({"seed", "failing", "interesting"}, set(rows))
        self.assertIn("$GOCACHE/fuzz", rows["interesting"][1])
        self.assertIn("Yes", rows["interesting"][3])
        self.assertIn("testdata/fuzz", rows["failing"][1])
        self.assertIn("No", rows["interesting"][2])

    # --- SKILL.md size ---

    # The file arrived at 536 with no budget at all. It is 515 now: the deserialization-cost
    # table moved into `advanced-tuning.md` (tuning detail, consulted while profiling, and
    # SKILL.md is loaded in full on every trigger), and five blocks that restated a section
    # immediately below them were folded.
    #
    # The five lines of headroom are deliberate and are the maximum: a budget equal to the
    # file fires on every edit regardless of merit, which is how the last skill's budget got
    # raised twice. The number is not the thing to edit — move a section behind a pointer.
    SKILL_MD_LINE_BUDGET = 520

    def test_skill_md_stays_within_line_budget(self) -> None:
        lines = len(self.skill.splitlines())
        self.assertLessEqual(
            lines, self.SKILL_MD_LINE_BUDGET,
            f"SKILL.md is {lines} lines (budget {self.SKILL_MD_LINE_BUDGET}). Move a "
            f"section into references/ rather than raising the budget.")

    def test_the_line_budget_still_constrains_the_file(self) -> None:
        """A budget set far above the file is a record, not a limit."""
        lines = len(self.skill.splitlines())
        self.assertLessEqual(
            self.SKILL_MD_LINE_BUDGET - lines, 25,
            f"SKILL.md is {lines} lines against a budget of {self.SKILL_MD_LINE_BUDGET}: "
            f"the budget has drifted into slack and can no longer fire")


class ShippedSurfaceIntegrityTests(unittest.TestCase):
    """Guards over the whole shipped surface: SKILL.md plus every file in `references/`."""

    @classmethod
    def setUpClass(cls):
        cls.refs = sorted((SKILL_DIR / "references").glob("*.md"))
        cls.texts = {SKILL_MD.name: SKILL_MD.read_text()}
        cls.texts.update({p.name: p.read_text() for p in cls.refs})

    def test_every_reference_pointer_resolves(self) -> None:
        """Renaming a reference left five dead `references/...md` pointers in SKILL.md with
        the full suite green: nothing checked that a cited file exists."""
        pointers = {(name, tgt) for name, text in self.texts.items()
                    for tgt in re.findall(r"references/([A-Za-z0-9._-]+\.md)", text)}
        self.assertGreaterEqual(len(pointers), 6,
                                "almost no pointers matched — the regex stopped working and "
                                "this guard would pass vacuously")
        for source, target in sorted(pointers):
            with self.subTest(source=source, target=target):
                self.assertTrue((SKILL_DIR / "references" / target).is_file(),
                                f"{source} cites references/{target}, which does not exist")

    def test_every_reference_file_is_reachable(self) -> None:
        """A reference nobody points at is never loaded, so its rules bind nothing."""
        pointed = {t for text in self.texts.values()
                   for t in re.findall(r"references/([A-Za-z0-9._-]+\.md)", text)}
        for ref in self.refs:
            with self.subTest(reference=ref.name):
                self.assertIn(ref.name, pointed, f"references/{ref.name} is unreferenced")

    # An auto-approval surface is least-privilege: a listed pattern runs with no prompt.
    # `gh issue*` was listed for one optional line in ci-strategy.md, which pre-approved
    # posting a crash reproducer to a public tracker. Anything that writes outside the
    # working tree belongs behind the normal permission flow.
    OUTWARD_WRITE = re.compile(
        r"\b(gh|git\s+push|curl|wget|ssh|scp|rsync|aws|gcloud|az|kubectl|docker\s+push|"
        r"npm\s+publish|go\s+mod\s+edit)\b")

    def test_allowed_tools_pre_approves_no_outward_write(self) -> None:
        fm = frontmatter(SKILL_MD.read_text())
        line = [ln for ln in fm.splitlines() if ln.startswith("allowed-tools:")]
        self.assertEqual(1, len(line), "expected exactly one allowed-tools line")
        for pattern in re.findall(r"Bash\(([^)]*)\)", line[0]):
            with self.subTest(pattern=pattern):
                self.assertIsNone(
                    self.OUTWARD_WRITE.search(pattern),
                    f"`{pattern}` is pre-approved on the auto-approval surface but can "
                    f"write outside the working tree; drop it and let the normal "
                    f"permission flow handle it")

    def test_the_outward_write_detector_still_detects(self) -> None:
        """Synthetic input, because the guard above is pinned only to a frontmatter line
        that is correct today — a detector edited into one that matches nothing would leave
        it vacuously green."""
        for bad in ("gh issue create", "git push origin main", "curl -X POST https://x",
                    "aws s3 cp . s3://b"):
            self.assertIsNotNone(self.OUTWARD_WRITE.search(bad), bad)
        for ok in ("go test*", "go build*", "go clean*", "go tool cover*"):
            self.assertIsNone(self.OUTWARD_WRITE.search(ok), ok)


if __name__ == "__main__":
    unittest.main()

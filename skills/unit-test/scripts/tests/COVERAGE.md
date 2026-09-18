# Unit-Test Skill — Rule-to-Scenario Coverage Matrix

Maps each core rule/section in SKILL.md to its golden fixture and contract test, plus a behavioral eval layer (`test_behavioral_killer.py`) that executes real Go to prove the skill's killer-case and `-race` claims actually work — not just that their rule text exists. Use this to identify coverage gaps when adding new rules.

## Contract Tests (`test_skill_contract.py`)

| Rule / Section | Test | Status |
|----------------|------|--------|
| Frontmatter name | `test_skill_name_is_valid` | ✅ |
| Coverage threshold 80% | `test_coverage_threshold_consistent_at_80` | ✅ |
| Assertion style adaptive | `test_default_prompt_is_assertion_style_adaptive` | ✅ |
| Scorecard incremental mode | `test_scorecard_boundary_for_incremental_mode` | ✅ |
| Scorecard Light mode | `test_scorecard_boundary_for_light_mode` | ✅ |
| Repository config | `test_repo_config_section_and_example_exist` | ✅ |
| Killer Case definition | `test_killer_case_definition_section_exists` | ✅ |
| Killer Case 4 components | `test_killer_case_four_components` | ✅ |
| Defect-First Workflow 5 categories | `test_defect_first_workflow_five_risk_categories` | ✅ |
| Boundary checklist 12 items | `test_boundary_checklist_has_twelve_items` | ✅ |
| Anti-examples >= 8 | `test_anti_examples_minimum_count` | ✅ |
| Anti-examples expanded (snapshot + impl details) | `test_anti_examples_expanded_count` | ✅ |
| Bug-Finding 7 techniques | `test_bug_finding_techniques_seven_entries` | ✅ |
| Target Type Adaptation 5 types | `test_target_type_adaptation_five_types` | ✅ |
| Reporting integrity | `test_reporting_integrity_section_exists` | ✅ |
| Output killer case report | `test_output_expectations_include_killer_case_report` | ✅ |
| Go Version Gate | `test_go_version_gate_exists`, `test_go_version_gate_covers_key_features` | ✅ |
| Generated Code Exclusion | `test_generated_code_exclusion_patterns` | ✅ |
| Multi-Package Coverage | `test_multi_package_coverage_guidance`, `CoverageScopeGuardTests` (5) | ✅ |
| High-Signal Budget (mode-aware) | `test_high_signal_test_budget_range`, `test_mode_aware_case_budget` | ✅ |
| Test Structure parallel safety | `test_test_structure_parallel_safety` | ✅ |
| Workflow version + exclusion steps | `test_workflow_includes_version_and_exclusion_steps` | ✅ |
| Workflow step 0 mode selection | `test_workflow_step_zero_mode_selection` | ✅ |
| Incremental Mode 3 flows | `test_incremental_mode_three_flows` | ✅ |
| Output version/exclusion info | `test_output_expectations_include_version_and_exclusion` | ✅ |
| Output includes mode | `test_output_expectations_include_mode` | ✅ |
| Light mode output reduction | `test_light_mode_output_reduction` | ✅ |
| Scorecard weight tiers | `test_scorecard_has_weight_tiers`, `test_scorecard_critical_items` | ✅ |
| SKILL.md line budget (≤ 520; raised from 500 in round 5, see the test's comment) | `test_skill_md_stays_within_line_budget` | ✅ |
| boundary-scorecard.md reference exists | `test_boundary_scorecard_reference_exists` | ✅ |
| boundary-scorecard.md PASS criteria | `test_boundary_scorecard_has_pass_criteria` | ✅ |
| Shuffle guidance | `test_shuffle_guidance_exists` | ✅ |
| Fuzzing collaboration | `test_fuzzing_collaboration_guidance` | ✅ |
| PR-diff scoped testing | `test_pr_diff_scope_section_exists` | ✅ |
| JSON summary output | `test_json_summary_exists` | ✅ |
| Execution Modes section | `test_execution_modes_section_exists` | ✅ |
| Mode selection criteria | `test_mode_selection_table_exists` | ✅ |
| Mode requirements table | `test_mode_requirements_table_exists` | ✅ |
| Mode declaration required | `test_mode_declaration_required` | ✅ |
| Light Scorecard 7 checks | `test_light_scorecard_exists` | ✅ |
| Light Scorecard Critical items | `test_light_scorecard_critical_items` | ✅ |
| Light Boundary Check 5 items | `test_light_boundary_check_exists` | ✅ |
| Mode-aware Killer Case | `test_mode_aware_killer_case` | ✅ |
| Mode-aware Defect Workflow | `test_mode_aware_defect_workflow` | ✅ |
| Property-Based Testing section | `test_property_based_testing_section_exists` | ✅ |
| Property-Based Testing quick ref | `test_property_based_testing_quick_reference` | ✅ |
| Property-Based Testing mode applicability | `test_property_based_testing_mode_applicability` | ✅ |
| Property-Based Testing reference file | `test_property_based_testing_reference_exists` | ✅ |
| JSON summary gated to Standard+Strict | `test_json_summary_gated_to_standard_strict` | ✅ |
| Scorecard Light mode | `test_scorecard_boundary_for_light_mode` | ✅ |
| Config mode key documented | `test_config_mode_key_documented` | ✅ |
| Config mode is floor not override | `test_config_mode_is_floor_not_override` | ✅ |
| Config example has mode key | `test_config_example_has_mode_key` | ✅ |
| Workflow step 6 mode-aware budget | `test_workflow_step_six_mode_aware_budget` | ✅ |
| Strict target count not universal | `test_strict_target_count_is_not_universal` | ✅ |
| Invariant pattern in mode selection | `test_invariant_pattern_in_mode_selection` | ✅ |
| Light mode auto-promotes on invariant | `test_light_mode_auto_promotes_on_invariant` | ✅ |
| Workflow step 12 gated | `test_workflow_step_twelve_gated` | ✅ |
| Trivial commutativity excluded | `test_trivial_commutativity_excluded` | ✅ |
| Light scorecard N/A handling | `test_light_scorecard_na_handling` | ✅ |
| Incremental mode is mode-aware | `test_incremental_mode_is_mode_aware` | ✅ |
| No force-Light config path in PBT | `test_no_force_light_config_path_in_pbt` | ✅ |
| Mode-aware case budget (workflow) | `test_mode_aware_case_budget` | ✅ |
| Workflow step 0 mode selection | `test_workflow_step_zero_mode_selection` | ✅ |
| Config example comment matches floor | `test_config_example_comment_matches_floor_semantics` | ✅ |
| Incremental add-tests flow mode-aware | `test_incremental_add_tests_flow_is_mode_aware` | ✅ |

## Golden Fixtures (`test_golden_scenarios.py`)

### Test Generation (should produce tests)

| ID | Scenario | Target Type | Mode | Techniques Verified |
|----|----------|-------------|------|---------------------|
| 001 | Pure function with slice boundary | Package-level functions | Standard | Off-by-One, Collection Mapping |
| 002 | Service method with repo dependency | Service interface | Standard | Dependency Error Propagation, Mutation-Resistant |
| 003 | Handler with goroutine fan-out | Service interface | Strict | Concurrency, Race detection, Error fan-in |
| 006 | List transform method | Service interface | Standard | Collection Mapping, Off-by-One |
| 007 | HTTP handler with JSON body | HTTP handler | Standard | Mutation-Resistant, Dependency Error |
| 008 | CLI command runner with flags | CLI command/runner | Standard | Dependency Error, Off-by-One |
| 009 | Auth middleware pass/block/error | Middleware | Strict | Branch Completeness, Mutation-Resistant |
| 010 | Simple pure function (Light mode) | Package-level functions | Light | Mutation-Resistant |
| 011 | Encode/Decode roundtrip (property-based) | Package-level functions | Standard | Property-Based Testing, Roundtrip |
| 012 | Concurrent map read/write (race trigger) | Service interface | Strict | Concurrency, Race detection |
| 013 | Payment service (scorecard tier weighting) | Service interface | Standard | Mutation-Resistant, Dependency Error |
| 014 | Event serializer (Strict, property required) | Package-level functions | Strict | Property-Based Testing, Roundtrip |
| 015 | Order FSM (Strict state machine) | Service interface | Strict | Branch Completeness, Context cancellation |

### Exclusions (should NOT produce tests)

| ID | Scenario | Exclusion Reason |
|----|----------|-----------------|
| 004 | Protobuf generated file | generated_code |
| 005 | Trivial getter with no logic | anti_example |

## Behavioral Eval (`test_behavioral_killer.py`)

Every test above is a **documentation-contract** check — it asserts a rule
*string* is present, not that the skill's advice actually works. This layer
executes real Go to validate the skill's two headline claims on fixed fixtures:

| Test | Proves |
|------|--------|
| `test_generated_test_compiles_and_vets` | a killer-case test in the skill's pattern compiles and passes `go vet` |
| `test_killer_case_passes_on_correct_impl` | the killer case passes on a correct slice-transform |
| `test_killer_case_kills_mutation` | the killer case **fails** on an off-by-one that drops the last element — it really kills the mutation |
| `test_weak_assertion_misses_mutation` | an existence-only (`len != 0`) assertion **passes** on the same mutation — the concrete reason mutation-resistant assertions (Critical #5) are mandatory |
| `test_race_detector_catches_real_race` | `go test -race` flags a genuine unsynchronised shared write (validates go-core MUST #10) |
| `test_pr_discovery_pipeline_resolves_packages` | the SKILL.md PR-discovery pipeline body resolves a changed file → package import path for real (guards the macOS `xargs -d` / bare-path-`go list` bug) |
| `test_removing_an_assertion_can_still_leave_the_mutation_caught` | that **"kills the mutation" and "this assertion is indispensable" are different claims**: with the dropped-tail mutation applied, deleting the length assertion still fails — the identity assertion catches it. So the old mandatory "if this assertion is removed the bug escapes" statement was false for this very test |
| `test_coverpkg_console_line_lies_while_the_profile_tells_the_truth` | runs the **shipped** § Multi-Package Coverage recipe on a 2-package module where `lib` has no `_test.go`: the console prints `covfix/lib coverage: 0.0%` while the merged profile reports `lib.Add` at 100%. Both halves are pinned, which is why "has no `_test.go`" is no longer an exclusion reason |

**What this does NOT prove — read before trusting it.** These tests validate the
*methodology the skill prescribes*, on hand-authored fixtures. They do **not** by
themselves prove an LLM driving the skill emits such a test — that is what the
skill-output grader (below) adds, and a full guarantee still needs the opt-in
live run. They also cover a small set of defect shapes (dropped-tail, data race,
PR discovery); others (mapping-key swap, nil-deref, context leak) are still only
asserted as doc text, not executed. The value is narrow but real: the skill's
central promise — "a killer case catches the defect it names; a weak assertion
does not" — is executable and regression-guarded instead of asserted in prose.

Skips (never fails) only on genuine **environment** failures — `go` absent, no
writable temp dir, or a trivial known-good program failing to compile (a broken
or mismatched toolchain). The harness drops any inherited `GOROOT` so a stale
one can't poison the build, and the readiness check is a real `go build` of a
trivial program, not a version probe. A *fixture* compile/assertion failure is
never skipped — it surfaces as a real failure. So CI without a working Go
toolchain stays green, while a real regression still fails loudly.

## Regression Guards (`test_skill_contract.py::EngineeringReliabilityGuardTests`)

Guards for the correctness fixes, so a future edit that breaks them fails loudly
(the reviewer's point: "the rules are right now, but nothing catches a regression").
Each pins a rule that was previously wrong:

| Guard | Pins |
|-------|------|
| `test_no_xargs_d_in_any_command` | no fenced command uses GNU-only `xargs -d` (prose may still name it as the pitfall) |
| `test_pr_discovery_uses_portable_readloop` | discovery uses the portable `while IFS= read` + `./`-prefix + `go list "$d"` form |
| `test_pr_discovery_documents_dot_prefix_reason` | the "bare path = import path" reason is documented |
| `test_target_count_not_standalone_trigger_in_table` | the Mode-Selection *table cell* says count is not a standalone Strict trigger |
| `test_mode_rule_says_risk_not_count` | the risk-driven-not-count-driven rule is present |
| `test_table_driven_requires_two_plus_cases` | table-driven is gated to 2+ cases in both the mode table and the scorecard |
| `test_race_precedence_documented` | `race.required config > PR scope > mode default` + the `false` override are documented |
| `test_case_budget_is_soft_ceiling_not_minimum` | budgets are soft ceilings, not minimums to pad to |

### `CoverageScopeGuardTests` — round-4 coverage-scope fix

The skill used to say a package with no `_test.go` "reports 0% — exclude it from gate
calculations". Under `-coverpkg` that console line is not the package's coverage, so the
rule discarded genuinely covered code *and* hid genuine gaps. Every guard below is scoped
to § Multi-Package Coverage, so a mention elsewhere in SKILL.md cannot satisfy it.

| Guard | Pins |
|-------|------|
| `test_gate_number_is_read_from_the_merged_profile` | the gate number comes from `go tool cover -func`, not the console |
| `test_console_zero_percent_is_documented_as_misleading` | the section explains *why* the 0.0% line is unusable |
| `test_absence_of_a_test_file_is_not_an_exclusion_reason` | the rejecting sentence is the one that names `_test.go`, and it routes to "coverage gap" |
| `test_old_exclude_because_zero_percent_rule_is_gone` | the reverted wording cannot come back |
| `test_valid_exclusions_are_enumerated_by_reason` | exclusions are justified by reason (generated / `cmd/**` / out of scope / vendored) |

### `KillerCaseVerificationGuardTests` — round-4 evidence fix

"If this assertion is removed, the known bug can escape detection" is a claim about a
defect that is *not in the code*. Nothing required running anything, so a hypothesis was
reported in the grammar of a result. Round 4 gave it a `Verification: Verified` /
`Verification: Unverified` label (defect injected, failure observed and quoted, or the
reason it was not run).

> **Superseded by round 5.** The whole sentence was retired — "kills the mutation" and
> "this assertion is indispensable" are different claims (see the next section) — and the
> surviving label was renamed to **`Kill: Verified` / `Kill: Unverified`**, so it names the
> claim it actually carries. The round-7 guard
> `test_retired_verification_label_cannot_return` keeps the old spelling off the shipped
> surface; it is kept here only as history.

| Guard | Pins |
|-------|------|
| `test_hard_rule_requires_a_verification_label` | the Hard Rules bullet demands one of the two labels |
| `test_unverified_is_labelled_a_hypothesis_not_a_result` | the skill says plainly that unverified ≠ demonstrated |
| `test_killer_case_definition_component_four_includes_verification` | component 4 of the definition carries the label |
| `test_workflow_step_twelve_requires_execution` | step 12 says "by executing it", and requires the revert |
| `test_output_expectations_report_the_verification_status` | the report format carries the status |
| `test_reference_ships_a_verification_recipe` | `killer-case-patterns.md` § Verifying the Kill exists, reverts, and names the three fake-kill modes |
| `test_scorecard_item_eleven_scores_the_label` | scorecard #11 scores the label; an honest `Unverified` still PASSES, an **unlabelled** claim FAILS |

### `KillLabelSweepTests` — every copy, not the cited one

Round 4 fixed SKILL.md and left `bug-finding-techniques.md` shipping a second **report
template** that produced an unlabelled claim. Round 5 retired the blanket "if this
assertion is removed…" sentence from 10 places across SKILL.md and four references. The
sweep walks every asset and splits prose, non-`go` fences and `go` fences, because the
three carry different obligations.

| Guard | Pins |
|-------|------|
| `test_indispensability_wording_only_where_the_check_is_defined` | any remaining discussion of removing an assertion sits with the necessity check that decides it — the unverifiable mandate cannot return under a new heading |
| `test_every_killer_case_report_template_carries_the_kill_label` | every fenced report template (identified by `Defect hypothesis:`) carries the mandatory `Kill:` status; plus anti-vacuity that the sweep found a template at all |
| `test_go_template_comments_state_the_kill_check` | all 7 in-code comments state the kill check instead of asserting indispensability |

### `KillerCaseVerificationGuardTests` — round-4/5 evidence fix

| Guard | Pins |
|-------|------|
| `test_hard_rule_requires_a_kill_label` | the Hard Rules bullet demands `Kill: Verified` / `Kill: Unverified` |
| `test_unverified_kill_is_labelled_a_hypothesis_not_a_result` | the skill says plainly that unverified ≠ demonstrated |
| `test_hard_rule_forbids_an_unchecked_necessity_claim` | the rule forbids the indispensability claim without its own check **and** explains the distinction |
| `test_killer_case_definition_component_four_is_the_kill_check` | component 4 is the kill check; necessity is separate and optional |
| `test_workflow_step_twelve_requires_execution` | step 12 says "by executing it" and requires the revert |
| `test_output_expectations_report_the_kill_status` | the report format carries the kill status and gates the necessity claim |
| `test_reference_separates_the_two_experiments` | § Verifying the Kill ships both procedures with **different conclusions**, says a still-failing test *refutes* necessity, and states that necessity is a property of an (assertion, defect) pair |
| `test_scorecard_item_eleven_scores_the_kill_status` | scorecard #11 scores the kill status; an honest `Unverified` PASSES, an unlabelled claim FAILS, and a necessity claim is not required |

### `SkipIsNotCoverageGuardTests` / `HypothesisMustBeCheckableGuardTests` — round 6

Both round-6 holes were skill-level rules as well as grader bugs: the same confusion
marks a boundary item `Covered` on the strength of a case that skipped, or writes into a
hypothesis a contract the assertions cannot see.

| Guard | Pins |
|-------|------|
| `test_reporting_integrity_says_a_skip_is_not_verification` | Reporting Integrity states `--- SKIP` is discovered, not verified — and blocks `Kill: Verified` on it |
| `test_anti_examples_reject_skip_as_a_pass` | `t.Skip()`-to-pass is an anti-example |
| `test_boundary_checklist_marks_a_skipped_case_as_a_gap` | a skipped case does not make its checklist item `Covered` |
| `test_each_hypothesis_must_name_the_change_that_violates_it` | the workflow requires a mutation per hypothesis, and calls an unmutatable hypothesis "not checkable as written" |
| `test_supplying_the_input_is_not_verification` | the rule names its concrete counterexample (`var out []string`), not just the abstraction |
| `test_anti_examples_reject_length_only_nil_coverage` | `len(nil) == 0` is named as the reason a length assertion cannot verify a nil-vs-empty contract |
| `test_reference_documents_the_nil_versus_empty_trap` | `bug-finding-techniques.md` documents the trap and routes the decision through the **contract**, not the current implementation |

## Skill-Output Eval (`test_llm_skill_eval.py`)

Grades an actual **skill-driven response** — the layer the earlier ones could not
reach. `grade(output, fixture)` scores: correct mode, real defect hypotheses, the
report contract (scorecard + required report markers + a JSON summary), and the
behavioral check — a Go test that compiles, PASSES on the correct source, and FAILS
on the mutation. `LiveSkillEval` runs a real model through the same `grade()`, gated
on `UNIT_TEST_SKILL_EVAL_CMD` (skipped otherwise). See `llm_eval/README.md`.

Round 7 made this layer a **corpus** rather than a single case. `EveryFixtureDiscriminates
Test` discovers every `llm_eval/*/meta.json` and requires each fixture's `good.md` to pass
and its `bad.md` to fail, with a floor of 2 fixtures so an empty glob cannot read as
green; the live arm runs the same corpus. The second fixture, `service_mapping`, is a
Service-interface target, which puts four techniques under execution that were previously
only asserted as doc text: dependency-error **wrapping** (`%w` vs `%v` — the mutated error
carries an identical message and only `errors.Is` can see the difference), no-partial-
payload on error, wrong-key mapping (a self-link preserves length, order and every ID),
and terminal-branch completeness.

### Round-4: two ways the grader used to pass a broken response

**1. A response whose Go code did not compile came back as a SKIP.** `_GoRunner` now
returns three states, and only a genuine environment fault skips:

| Outcome | Meaning | On the correct source | On the mutated source |
|---------|---------|----------------------|----------------------|
| `PASSED` | the binary ran, tests passed | required | **not a kill** — weak assertion |
| `FAILED` | the binary ran, a test failed | graded as a failure | the kill |
| `NO_RUN` | nothing ran (build/vet error, or no test function) | graded as a failure — for a test-generation skill this is the headline defect | **invalid mutation**: a kill cannot be credited |
| *skip* | `go` absent, no temp dir, unresolved module download, or an exit with neither a diagnostic nor a test result | not a grade | not a grade |

`preflight()` builds a trivial known-good program first, so a compiler diagnostic
afterwards is about the *code*, not the toolchain. Note also that `go test` exits 0
and prints an `ok` line for `[no tests to run]` — success by exit status and by
prefix, executing nothing. That is `NO_RUN`.

**2. A `json` fence containing the literal text `NOT JSON` scored as a pass.** The
block is now parsed and cross-checked by `grade_json_summary`, mutation-tested by
`JsonSummaryContractTests` (go-free, so it runs everywhere):

| Check | Rejects |
|-------|---------|
| parses, and is an object | `NOT JSON`, a bare array, a missing block |
| required sections/fields (from `meta.json`, incl. every `targets[]` entry) | a summary too thin to ingest |
| `summary.score` is `N/M` and equals the sum of the tier counts | a score that contradicts its own scorecard |
| `summary.pass` equals the tier verdict | `pass: true` with a Critical FAIL or a tier below minimum |
| `coverage.met` equals `line_pct >= gate` | a met-gate claim the numbers refute |
| `race.clean` implies `race.executed` | a clean race result that was never run |
| `summary.score` also appears in the prose | a report whose human and machine verdicts disagree |

The tier minimums **and tier sizes** are **parsed out of
`references/boundary-scorecard.md`**, not copied into the grader — a second copy of a
documented threshold drifts silently. A reference that stops stating them, or that is
internally inconsistent (tiers not summing to the grand total), raises rather than
grading against a guess. Both raises have their own test, because a mutation run showed
the second guard was unbound: the test asserting the shipped reference *is* consistent
stayed true whether or not the guard fired, so deleting the guard survived. An `assert`
in shipped code with no test that makes it fire is not a check.

**Round 5: two more ways a semantically wrong report scored clean.**

*Wrong types disabled the checks.* Every consistency rule used to be guarded by an
`isinstance` test, so `"critical_pass": "three"` skipped the score and verdict
comparisons entirely and graded clean. Types are now validated first, from the fixture's
`json_field_types` (which is also the required-field list — one list, not two), and the
consistency rules then run unconditionally. `int` rejects `true`, since `bool` is an
`int` subclass in Python. Ranges are checked too: tier totals must match the scorecard's
tier sizes, `*_pass` must lie in `0..total`, percentages in `0..100`, `cases >= 1`.

*Coverage and the verdict were not linked.* A report could state `line_pct: 20`,
`met: false` and `13/13 PASS` — every field locally consistent, the verdict impossible.
The coverage gate is Critical item 13, so a **measured** miss (the restricted N/A covers
only *unmeasured* coverage) must show as a failed Critical item and an overall FAIL.

| Round-5 check | Rejects |
|---------------|---------|
| declared type per field | `"critical_pass": "three"`, `"critical_pass": true` |
| tier totals vs. the scorecard's tier sizes | `standard_total: 4` when the tier has 5 items |
| `0 <= *_pass <= *_total`, `0 <= pct <= 100`, `cases >= 1` | counts and percentages outside their range |
| `met: false` with a measured miss ⇒ Critical FAIL ⇒ overall FAIL | 20% coverage reported as 13/13 PASS |

### Round-5/6: report vs. code (`_grade_report_matches_code`, `_grade_mutations`)

Format checks never look at the code, so the exemplar itself claimed 5 cases and
hypotheses H1+H2 while shipping a single 3-element input — and passed. `run()` now uses
`go test -v`, so what the toolchain did is observable.

Round 6 then found two ways a case could satisfy the round-5 checks while verifying
nothing, both reproduced against the shipped exemplar:

| Round-6 hole | What passed | Fix |
|--------------|-------------|-----|
| **Skipped counted as executed** — the collector took PASS, FAIL and SKIP alike | making the two H2 subtests `t.Skip()`, changing nothing else → `(True, [])` | `test_case_results` keeps each case's **status**; `verified_cases` drops SKIPs. A hypothesis needs a matching case that reached a verdict, and this fixture reports any skip at all (`allow_skipped_cases: false`) |
| **A hypothesis with no mutation** — H2 promised "empty but NON-NIL" and only H1 had one | changing the implementation to `var out []string` left all four exemplar cases passing: `len(nil) == 0` | **every hypothesis owns a mutation**, and the emitted test must kill each. "Covered" now means the stated behaviour is asserted, not that the input was supplied |

| Check | Rejects |
|-------|---------|
| `sum(targets[].cases)` equals the cases that ran | "5 cases" over a file that runs 1 |
| each hypothesis's `case_pattern` matches a **verified** case | a `t.Skip()`ped case standing in as coverage |
| any skip, unless the fixture allows it | a case reporting `--- SKIP` for a pure function |
| each hypothesis's mutation is killed | a hypothesis stated in prose and unasserted in code |

`test_case_results` counts leaves only — a parent test containing subtests is a group,
not a case. This is not semantic analysis; it compares things that already have to agree.
It assumes the response's fenced Go block is the complete test for the target, which is
what the eval prompt asks for.

The fixture's three parallel lists (`hypothesis_keywords` / `required_case_patterns` /
`mutation`) collapsed into one `hypotheses` array, each entry carrying its wording, its
required case, its mutation and its `contract_evidence`. They could disagree — and did:
H2 appeared in two of the three and had no mutation, which is exactly how its promise
went unverified.

**`validate_fixture` — the other direction of the same error.** Asserting a behaviour the
code under test never promised is a defect too: it invents a requirement. The round-6
mutation run found nothing checked this — deleting the non-nil contract from `sut.go`'s
doc comment left the exemplar passing. Each hypothesis now declares `contract_evidence`,
a regex that must match the source, and a fixture whose hypothesis is not grounded (or
declares no evidence at all) fails before any response is graded.

**Honesty:** the CI self-test proves the *grader* works; it does not prove a live
model passes. Only the opt-in live run does — that is the standing ceiling.

### Round 7 — the guards that could not fail

An external evaluation ran **eight mutations against SKILL.md; six survived.** Not
obscure ones: the coverage-gate number in the section that defines it, the
Mode-Requirements cell that makes a killer case mandatory in Standard, the Light
scorecard's PASS bar and both its tier minimums, and five reference pointers rewritten to
a file that does not exist. The full 166-test suite stayed green through all six.

The cause is one pattern, and it is the pattern this skill's own Critical item 5 is
about: **an assertion satisfied by an unrelated match.** `assertIn(">= 80%", skill)` over
a 500-line document is green as long as *any* occurrence survives, so editing the one
that decides the gate changes nothing. Where the assertion was scoped, it checked the row
*label* and never the cell. The Go-executing layers were never affected — they run code,
and code cannot be satisfied by a coincidence.

| Guard (`NormativeValueGuardTests`) | Pins | Mutation it was shown to kill |
|---|---|---|
| `test_coverage_gate_number_is_pinned_inside_its_policy_section` | the gate, sliced to § Coverage Gate Policy, and that the section states exactly one gate | `>= 80%` → `>= 75%` there only |
| `test_mode_requirements_cells_are_pinned` | every normative cell of the Mode-Requirements table, parsed | `Killer Case per target` Standard → `Skip` |
| `test_mode_requirements_has_no_unpinned_row` | the exact row set, so a new row must be pinned | re-adding `Removal Risk Statement` |
| `test_light_scorecard_pass_bar_is_pinned_and_consistent` | the PASS bar with denominators **derived** from the table's own Tier column, plus satisfiability | `total >= 6/7` → `3/7`; tier minimums → 0 |
| `test_case_budget_is_the_same_number_in_all_three_places` | the three copies of the per-mode budget must agree | `3-6` → `1-99` in the mode table |
| `test_json_summary_fields_match_every_eval_fixture` | SKILL.md's JSON example and every fixture's `json_field_types` are one schema | a field documented in one and not the other |
| `test_scorecard_tiers_agree_between_skill_and_reference` | SKILL.md's tier lists vs. the reference the grader parses | Critical `5, 11, 13` → `5, 11, 12` |

| Guard (`ShippedSurfaceIntegrityTests`) | Pins |
|---|---|
| `test_every_reference_pointer_resolves` | every `references/*.md` pointer in SKILL.md **and** in each reference resolves on disk; anti-vacuity floor of 5 pointers |
| `test_every_reference_file_is_reachable` | the other direction — a reference nobody points at is never loaded |
| `test_retired_verification_label_cannot_return` | the round-5 rename: `Kill:`, never `Verification:` |
| `test_retired_removal_risk_requirement_cannot_return` | the retired sentence may be *named as retired* and nowhere else — the allow-list is the safe shape, so an unrecognised mention fails |
| `test_the_kill_label_is_spelled_one_way_everywhere` | anti-vacuity for the two above: the replacement label must actually be present |

**Two live contradictions were removed from the shipped text**, both survivors of round 5:

- SKILL.md carried `| Removal Risk Statement | Skip | Required | Required |` — a
  `Required` cell for an obligation retired two rounds earlier, defined nowhere else, and
  contradicted by the Hard Rules three screens above it. Replaced by the requirement that
  is real (`Kill: Verified`/`Unverified`).
- `killer-case-patterns.md`'s header described a component the templates do not carry and
  named the label `Verification: Verified`. A model reading the reference before SKILL.md
  would emit a label scorecard item 11 scores as *unlabelled*, i.e. a FAIL.

Round-7 mutation run: **10 mutations, 10 killed**, against a verified-effective harness
(a control mutation was killed and an unchanged baseline was green first).

## Coverage Summary

| Metric | Count |
|--------|-------|
| Total golden fixtures | 15 |
| Test generation (positive) | 13 |
| Exclusions (negative) | 2 |
| Target types covered (rule text) | 5/5 (Service, Function, Handler, CLI, Middleware) |
| Target types covered (**executed** skill-output grading) | 2/5 (Function, Service) — round 7 lifted this from 1/5 |
| Modes covered | 3/3 (Light 1, Standard 5, Strict 4+2 excl) |
| Skill-output eval fixtures | 2 (`slice_transform`, `service_mapping`) |
| Reference files | 5 |

Per-file test counts are deliberately **not** listed here. A hand-maintained total is
a second copy of a number the suite already knows, and it goes stale on the next
commit while still reading as authoritative. Get the current figures from the suite:

```bash
python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v   # names + total
```

**Runtime.** The suite is minutes, not seconds: every skill-output grading compiles and
runs a Go module per hypothesis mutation, and round 7 added a second fixture with four of
them. Expect roughly 4 minutes with a warm Go build cache and more without one. That is
past the default timeout of a single agent shell call, so run it in the background or
raise the timeout — and read the final `OK` / `FAILED` line, because a truncated
transcript that stops mid-test looks exactly like a pass.

## Gap Analysis

When adding a new rule to SKILL.md or references:

1. Add a golden fixture that exercises the rule.
2. Add a contract test that verifies the rule text exists.
3. Update this matrix.

### Known Coverage Gaps (TODO for future fixtures)

| Scenario | Category | Priority |
|----------|----------|----------|
| **Defect-seeded A/B**: whether the methodology raises real defect detection is still unmeasured. The 2026-03 A/B found all 13 without-skill failures were methodology-level with identical core-path coverage — i.e. no measured detection delta. This is the standing ceiling, and it is what "prioritize bug discovery over test volume" currently rests on | effect | **High** |
| Live LLM skill-output eval wired to a backend (grader + opt-in hook exist, and the live arm now runs every fixture; needs a CI-available model) | behavioral | Medium |
| Skill-output fixtures for the remaining 3 target types (HTTP handler, CLI, middleware) and for Light and Strict modes — round 7 took this from 1 fixture to 2 | behavioral | Medium |
| Skill-output fixtures for the untested defect shapes (nil-deref, context leak, concurrency) | behavioral | Medium |
| gRPC handler target type | target_type | Low |
| Golden file / snapshot test anti-example | anti_example | Low |
| Fuzzing + unit test collaboration example | technique | Low |
| Shuffle-dependent test detection | technique | Low |

Closed since last revision: PR-diff scope now has an executable fixture
(`test_pr_discovery_pipeline_resolves_packages`); the round-2/3 correctness fixes
now have regression guards; skill-output grading exists (self-tested in CI).

Closed in round 4: an uncompilable response is graded as a failure instead of skipped;
an uncompilable mutation can no longer be credited as a kill; the JSON summary is
parsed and cross-checked instead of merely fence-matched; the multi-package coverage
rule is executed against a real 2-package module; the killer-case removal-risk
statement carries a verification status. Every round-4 rule was mutation-checked —
each guard was broken in turn and the matching test failed (17/17), with a skipped
test counted as SURVIVED, not as a kill.
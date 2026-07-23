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
| Multi-Package Coverage | `test_multi_package_coverage_guidance` | ✅ |
| High-Signal Budget (mode-aware) | `test_high_signal_test_budget_range`, `test_mode_aware_case_budget` | ✅ |
| Test Structure parallel safety | `test_test_structure_parallel_safety` | ✅ |
| Workflow version + exclusion steps | `test_workflow_includes_version_and_exclusion_steps` | ✅ |
| Workflow step 0 mode selection | `test_workflow_step_zero_mode_selection` | ✅ |
| Incremental Mode 3 flows | `test_incremental_mode_three_flows` | ✅ |
| Output version/exclusion info | `test_output_expectations_include_version_and_exclusion` | ✅ |
| Output includes mode | `test_output_expectations_include_mode` | ✅ |
| Light mode output reduction | `test_light_mode_output_reduction` | ✅ |
| Scorecard weight tiers | `test_scorecard_has_weight_tiers`, `test_scorecard_critical_items` | ✅ |
| SKILL.md line budget (≤ 500) | `test_skill_md_stays_within_line_budget` | ✅ |
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

## Skill-Output Eval (`test_llm_skill_eval.py`)

Grades an actual **skill-driven response** — the layer the earlier ones could not
reach. `grade(output, fixture)` scores four dimensions: correct mode, real defect
hypotheses, a Go test that compiles + PASSES on the correct source + FAILS on the
mutation (kills it), and a scorecard + JSON. `GraderSelfTest` proves the grader
discriminates — it PASSES `llm_eval/slice_transform/good.md` and FAILS `bad.md`
(runs in CI; needs `go`). `LiveSkillEval` runs a real model and grades it, gated
on `UNIT_TEST_SKILL_EVAL_CMD` (skipped otherwise) — the remaining step to a full
behavioral eval, now a drop-in. See `llm_eval/README.md`.

**Honesty:** the CI self-test proves the *grader* works; it does not prove a live
model passes. Only the opt-in live run does — that is the standing ceiling.

## Coverage Summary

| Metric | Count |
|--------|-------|
| Total golden fixtures | 15 |
| Test generation (positive) | 13 |
| Exclusions (negative) | 2 |
| Target types covered | 5/5 (Service, Function, Handler, CLI, Middleware) |
| Modes covered | 3/3 (Light 1, Standard 5, Strict 4+2 excl) |
| Reference files | 5 |
| Contract tests (incl. 8 engineering-reliability guards) | 75 |
| Golden scenario tests | 17 |
| Behavioral eval tests (execute real Go; skip w/o toolchain) | 6 |
| Skill-output grader self-tests (+ 1 opt-in live, skipped w/o backend) | 2 (+1) |

## Gap Analysis

When adding a new rule to SKILL.md or references:

1. Add a golden fixture that exercises the rule.
2. Add a contract test that verifies the rule text exists.
3. Update this matrix.

### Known Coverage Gaps (TODO for future fixtures)

| Scenario | Category | Priority |
|----------|----------|----------|
| Live LLM skill-output eval wired to a backend (grader + opt-in hook exist; needs a CI-available model) | behavioral | Medium |
| More skill-output fixtures (mapping-key swap, nil-deref, context leak, concurrency mode) | behavioral | Medium |
| gRPC handler target type | target_type | Low |
| Golden file / snapshot test anti-example | anti_example | Low |
| Fuzzing + unit test collaboration example | technique | Low |
| Shuffle-dependent test detection | technique | Low |

Closed since last revision: PR-diff scope now has an executable fixture
(`test_pr_discovery_pipeline_resolves_packages`); the round-2/3 correctness fixes
now have regression guards; skill-output grading exists (self-tested in CI).
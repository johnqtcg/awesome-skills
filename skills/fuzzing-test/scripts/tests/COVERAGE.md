# Fuzzing-Test Skill — Test Coverage Matrix

Four test layers, in increasing strength of evidence:

| Layer | File | What it proves | What it does **not** prove |
|-------|------|----------------|----------------------------|
| 1. Contract | `test_skill_contract.py` | The skill document contains the required sections, rules, and thresholds, and its rules do not contradict each other | Nothing about behaviour |
| 2. Golden fixtures | `test_golden_scenarios.py` | Each scenario's expected verdict/mode/template is internally consistent, and the rules it depends on exist in the text | That a model driven by the skill actually produces those verdicts |
| 3. Template compile + replay + **short fuzz** | `test_templates_compile.py` | The four harness templates are valid Go, satisfy the regex-decidable scorecard items, every seed passes **and actually runs** (no guard-skipped dead seeds), and a 5s fuzz run against a correct implementation **stays clean** | That they find bugs |
| 4. **Behavioral eval** | `test_llm_fuzz_eval.py` | A graded response's emitted harness **compiles, passes seed replay, stays clean under fuzzing on the correct implementation, and finds a seeded defect** | That a live model passes — that needs the opt-in live hook |

Layer 2 is keyword- and structure-level by construction: it reads fixture JSON and the
skill text, with no model in the loop. Layer 4 is where behaviour is actually verified.

## Contract Tests (test_skill_contract.py)

| Test Class | Test | Validates |
|-----------|------|-----------|
| FrontmatterTests | test_frontmatter_name | SKILL.md frontmatter `name` field |
| FrontmatterTests | test_frontmatter_description_keywords | `applicability gate first` + `Go 1.18+` in description |
| CoreGateTests | test_applicability_gate_exists | Gate 1 section heading |
| CoreGateTests | test_target_priority_gate_exists | Gate 2 section heading |
| CoreGateTests | test_risk_cost_gate_exists | Gate 3 section heading |
| CoreGateTests | test_execution_integrity_gate_exists | Gate 4 section heading |
| CoreGateTests | test_applicability_hard_stop_items | Hard stop verdict + alternative suggestion |
| CoreGateTests | test_five_applicability_checks | All 5 check descriptions present |
| CoreGateTests | test_cost_classes | Low/Medium/High cost classification |
| TemplateTests | test_template_a_parser | Template A heading + FuzzParseXxx |
| TemplateTests | test_template_b_roundtrip | Template B heading + FuzzRoundTripXxx |
| TemplateTests | test_template_c_differential | Template C heading + FuzzDiffXxx |
| TemplateTests | test_template_d_struct_aware | Template D heading + FuzzProcessRequest |
| TemplateTests | test_templates_have_f_add | ≥4 `f.Add(` calls |
| TemplateTests | test_templates_have_size_guard | `len(data) >` size bound |
| AntiExampleTests | test_anti_examples_section_exists | Section heading |
| AntiExampleTests | test_minimum_anti_example_count | ≥7 numbered mistakes |
| AntiExampleTests | test_anti_examples_have_bad_good_pairs | BAD/GOOD code markers |
| AntiExampleTests | test_key_anti_examples_present | Trivial/oracle/skip-rate/OOM/external-state |
| ScorecardTests | test_scorecard_section_exists | Section heading |
| ScorecardTests | test_scorecard_critical_tier | C1/C2/C3 items |
| ScorecardTests | test_scorecard_standard_tier | S1-S5 items |
| ScorecardTests | test_scorecard_hygiene_tier | H1-H4 items |
| ScorecardTests | test_scorecard_pass_fail_rule | Critical-fail → overall FAIL |
| GoVersionAndAdvancedTests | test_version_gate_section | Section heading |
| GoVersionAndAdvancedTests | test_version_table_entries | 1.18/1.20/1.21/1.22 |
| GoVersionAndAdvancedTests | test_race_detection_fuzz | Section heading + -race flag |
| GoVersionAndAdvancedTests | test_worker_parallelism | GOMAXPROCS + -parallel |
| GoVersionAndAdvancedTests | test_go_fuzz_headers | Library name + GenerateStruct |
| GoVersionAndAdvancedTests | test_performance_baseline | Section heading + execs/sec |
| FuzzVsPropertyTests | test_comparison_table | Section heading + rapid/gopter |
| FuzzVsPropertyTests | test_decision_rules | Use fuzz/property-based/both |
| ReferenceDepthTests | test_applicability_has_concrete_examples | Suitable/NOT Suitable/Borderline sections |
| ReferenceDepthTests | test_applicability_has_go_code | `func ` + ≥5 `// Check` annotations |
| ReferenceDepthTests | test_target_priority_has_go_examples | Tier 1/2/De-Prioritize examples with `func ` |
| ReferenceDepthTests | test_target_priority_has_flowchart | Quick Decision Flowchart |
| ReferenceDepthTests | test_ci_strategy_two_lanes | PR Lane + Scheduled Lane |
| ReferenceDepthTests | test_crash_handling_template | Crash Report Template + Post-Fix Checklist |
| OracleRuleConsistencyTests | test_gate_accepts_no_panic_oracle | Gate accepts a no-panic oracle |
| OracleRuleConsistencyTests | test_c2_is_not_a_token_search | C2 is not graded by searching for `t.Fatal` |
| OracleRuleConsistencyTests | test_c2_documents_both_accepted_oracle_forms | Robustness harness with no assertion stays legal |
| OracleRuleConsistencyTests | test_c2_still_rejects_the_declared_oracle_mismatch | Declared-invariant-but-unasserted still fails |
| TemplateSeedQualityTests | test_every_template_has_at_least_three_seeds | Each template meets its own S1 bar |
| TemplateSeedQualityTests | test_every_template_marks_seeds_as_placeholders | `PLACEHOLDER SEEDS` marker present |
| TemplateSeedQualityTests | test_placeholder_note_points_at_seed_mining | Placeholders routed to §Seed mining strategy |
| FuzzFlagSemanticsTests | test_single_target_rule_documented | `-fuzz` matches exactly one target |
| FuzzFlagSemanticsTests | test_no_broken_multi_target_fuzz_command | No `-fuzz='^Fuzz'` in SKILL.md or ci-strategy.md |
| FuzzFlagSemanticsTests | test_replay_uses_run_not_fuzz | Cross-target replay uses `-run` |
| CoverageDocConsistencyTests | test_declared_fixture_count_matches_disk | This document's fixture count is not hand-drifted |
| CoverageDocConsistencyTests | test_every_fixture_listed_in_coverage_doc | Every fixture appears here |
| CoverageDocConsistencyTests | test_no_satisfied_gap_still_listed | Known Gaps holds no already-closed item |
| CoverageDocConsistencyTests | test_behavioral_eval_documented | Layer 4 is documented here |
| OracleRuleConsistencyTests | test_skill_md_points_at_the_oracle_reference | Moved oracle detail stays reachable from SKILL.md |
| CrashArtifactGlobTests | test_upload_glob_is_recursive | Crash upload uses `**/testdata/fuzz/**` |
| CrashArtifactGlobTests | test_no_root_anchored_upload_path | No root-anchored path that misses subpackages |
| CrashArtifactGlobTests | test_missing_crasher_fails_loudly | `if-no-files-found: error` |
| CrashArtifactGlobTests | test_subpackage_path_documented | `pkg/parser/testdata/fuzz` example present |
| CoverageDocConsistencyTests | test_declared_anti_example_count_matches_reference | This document's anti-example count is not hand-drifted |
| CoverageDocConsistencyTests | test_skill_md_anti_example_count_matches_reference | SKILL.md's cited anti-example count matches the reference |

**Contract test count: 70**

## Golden Fixture Tests (test_golden_scenarios.py)

| Fixture | Scenario | Verdict | Validates |
|---------|----------|---------|-----------|
| 001_parser_suitable.json | Parser decoder | Suitable (Tier 1) | Template A, size guard, oracle |
| 002_roundtrip_suitable.json | JSON codec | Suitable (Tier 2) | Template B, round-trip invariant |
| 003_differential_suitable.json | Algorithm rewrite | Suitable (Tier 3) | Template C, differential |
| 004_struct_aware_suitable.json | Struct processor | Suitable (Tier 2) | Template D, json.Unmarshal |
| 005_trivial_not_suitable.json | `Add(a,b)` | Not suitable | Check 1 hard stop, alternative |
| 006_no_oracle_not_suitable.json | Log function | Not suitable | Check 3 hard stop, alternative |
| 007_db_dependent_not_suitable.json | DB business logic | Not suitable | Check 2 hard stop, alternative |
| 008_validator_with_race.json | Validator w/ goroutine | Suitable + advanced | Race detection feature |
| 009_crash_handling_workflow.json | Panic found by fuzzer | Suitable | All 5 crash-workflow steps have anchors |
| 010_ci_integration_workflow.json | CI request | Suitable | Both CI lanes documented |
| 011_borderline_soft_warning.json | `time.Now()` + `rand` | Suitable (Warn) | Check 4 is a soft warning, never a hard stop |
| 012_go_fuzz_headers_suitable.json | Nested struct, >80% skip | Suitable | Template D → go-fuzz-headers bridge, skip threshold |
| 013_go_directive_low_toolchain_modern.json | `go 1.16` directive, Go 1.25 toolchain | Suitable | **Must not** hard stop — verified empirically |
| 014_corpus_management_degradation.json | 2000 corpus entries | Suitable | Entries are in `$GOCACHE/fuzz`; premise corrected |
| 015_toolchain_below_118_hard_stop.json | Effective toolchain 1.17 | Not suitable | The genuine Go Version Gate hard stop |

**Golden fixture count: 15**
**Golden test count: 38**

Cross-cutting guards in this layer:

- `GoldenFixtureScenarioCoverageTests` — every fixture must be named by a scenario-specific
  test, so a new fixture cannot ride along on the generic integrity sweep alone.
- `GoldenHardStopConsistencyTests` — SKILL.md and `applicability-checklist.md` must agree on
  which checks are blocking (they previously disagreed about check 1).
- `GoldenVersionGateTests` — requires one `proceed` and one `hard_stop` version fixture.
- `GoldenCorpusLocationTests` — pins the corpus storage model and the top-level `on: schedule`.

## Template Compile + Replay Tests (test_templates_compile.py)

| Test | Validates |
|------|-----------|
| test_at_least_four_templates | ≥4 fuzz templates extractable from SKILL.md |
| test_c2_every_template_asserts_a_property | Templates carry an explicit assertion |
| test_c3_every_byte_or_string_harness_bounds_size | Templates bound input size |
| test_corruption_word_absent | No `outputexample` global-replace artefact |
| test_all_templates_compile_with_stubs | `go vet` passes on all templates + stubs |
| test_all_template_seeds_pass_on_correct_implementation | **Every `f.Add` seed passes on a correct implementation** |
| test_seed_replay_would_catch_a_bad_seed | Anti-vacuity: an invalid-UTF-8 seed is actually rejected |

**Template test count: 11** (5 skip without the `go` toolchain)

Why seed replay exists: `go vet` type-checks but does not run. A Template B seed containing
invalid UTF-8 once shipped green — `encoding/json` rewrites it to U+FFFD, so the round-trip
assertion failed on the **correct** stub implementation. Anyone copying the template got an
immediately-red test. Replay closes that hole; the anti-vacuity test proves it can fail.

## Behavioral Eval (test_llm_fuzz_eval.py)

Five fixtures: four suitable targets and — since a skill whose first rule is "stop when
the target is unsuitable" must be graded on stopping — one that must be refused. Each
fixture grades a **distinct defect** — sharing a mode is allowed only when the graded
failure differs (enforced by `test_each_fixture_grades_a_distinct_defect`):

| Fixture | Mode / Template | Mutation | Why it discriminates |
|---------|-----------------|----------|----------------------|
| `llm_eval/frame_parser/` | parser robustness / A | Bounds check widened so the payload slice reads past the input | Silent (slices are capacity-bounded, no panic) — needs an explicit domain-constraint assertion |
| `llm_eval/kv_codec/` | round-trip / B | `Decode` drops the value's most-significant byte | Silent corruption — `Value:-1` decodes as `16777215`; only a round-trip assertion catches it |
| `llm_eval/json_roundtrip/` | round-trip / B | `Encode` silently truncates `Name` to 8 bytes | Grades the **other** direction: the codec normalizes (invalid UTF-8 → U+FFFD), so an oracle without a domain guard fails on the CORRECT implementation. Its bad exemplar *does* detect the mutation and is still wrong |
| `llm_eval/split_differential/` | **differential** / C | index advances by 1 instead of `len(sep)` after a match | Grades the third fuzz mode: the oracle is agreement with `strings.Split`, so a harness that calls both implementations and drops a result cannot see a divergence |
| `llm_eval/trivial_add/` | **refusal** (gate items 1+3 fail) | none — no harness may exist | Grades the path every other fixture skips: a correct response writes no harness, names no fuzz command, and points at unit/property tests. Without it, "always write a harness" scored as well as running the gate |

The first two mutations are non-panicking on purpose: a no-assertion "the runtime catches
panics" harness cannot kill either, so the kill check genuinely measures oracle strength.
The third fixture exists because killing the mutant is **not sufficient** — a harness that
fails on every input also kills it. Only `fuzz_stays_clean` separates the two.

| Test | Validates |
|------|-----------|
| GraderSelfTest.test_grader_passes_good_exemplars | The grader accepts a correct response, for both fixtures |
| GraderSelfTest.test_grader_fails_bad_exemplars | It rejects weak ones for the defect each fixture declares in `bad_expected_reasons` |
| GraderSelfTest.test_mutation_is_reachable_at_all | Anti-vacuity: each good harness really does find its defect |
| GraderSelfTest.test_good_harness_seeds_are_representable | Exemplar seeds pass on correct code (the Template B trap) |
| GraderUnitTests.test_extracts_harness_from_fenced_block | Harness extraction from markdown |
| GraderUnitTests.test_ignores_non_fuzz_go_blocks | `func Test` blocks are not mistaken for harnesses |
| GraderUnitTests.test_target_name_parsed | Target name parsing |
| GraderUnitTests.test_fixture_metadata_is_self_consistent | `mutation.find` exists verbatim in each `sut.go` |
| GraderUnitTests.test_fixtures_cover_every_fuzz_mode | Parser + round-trip are both graded |
| GraderUnitTests.test_each_fixture_grades_a_distinct_defect | A fixture must add a grading axis, not repeat one |
| GraderUnitTests.test_every_fixture_declares_expected_bad_reasons | Each fixture pins why its bad exemplar must fail |
| GraderUnitTests.test_every_fixture_dir_is_registered | A fixture on disk but absent from `FIXTURES` is never silently ungraded |
| LiveSkillEval.test_live_model_output_passes_grader | Opt-in live model run over both fixtures (skipped unless configured) |

**Behavioral eval count: 22** (6 need `go`; 1 is opt-in via `FUZZING_TEST_SKILL_EVAL_CMD`)

What the grader checks, in order: declared applicability verdict → (for a refusal target:
no harness, no fuzz command, an alternative named — and stop) → fuzz mode → scorecard
present → harness extractable → ≥3 seeds → size guard → **compiles** → **seed replay passes
on the correct implementation** → **a bounded fuzz run stays clean on the correct
implementation** → **a known defect-exposing input fails on the mutated implementation**.
The kill check replays a declared witness rather than searching for one: a 10s search made
the grade intermittently credit a no-oracle harness with a detection it had not made. The last three cannot be
satisfied by text alone, and the middle one was the gap: grading only the mutant scores a
harness that fails on *everything* as a successful detection.

The mutation is deliberately silent rather than a panic (a Go slice expression is
capacity-bounded, so reading past `len` does not reliably crash). A no-assertion harness
therefore cannot kill it, which makes the check a real test of oracle strength and exercises
the distinction scorecard C2 draws.

## Coverage Summary

| Category | Total | Tested | Coverage |
|---------|-------|--------|----------|
| Gates (4) | 4 | 4 | 100% |
| Templates (A-D) | 4 | 4 | 100% |
| Anti-examples (9) | 9 | 5 (key themes) | 56% |
| Scorecard tiers (3) | 3 | 3 | 100% |
| Scorecard items (12) | 12 | 12 | 100% |
| Reference files (6) | 6 | 6 | 100% |
| Go version gate sources (3) | 3 | 3 | 100% |
| Advanced features (4) | 4 | 4 | 100% |
| Applicability verdicts | 2 (suitable/not) | 2 | 100% |
| Golden fixtures | 15 | 15 | 100% |
| Template seeds pass on correct code | 4 | 4 | 100% |
| Fuzz modes with compile-and-kill fixture | 4 | 2 (parser, round-trip) | 50% |
| Behavioral: harness compiles | 2 | 2 | 100% |
| Behavioral: harness kills a real defect | 2 | 2 | 100% |

**Total tests: 141** (70 contract + 38 golden + 11 template + 22 behavioral)

Runtime is ~40s; the `go` build cache is shared across the session, since a per-module
`GOCACHE` forced a cold stdlib recompile per invocation and doubled the wall clock.

## Known Gaps (Future)

1. The live model eval (`LiveSkillEval`) is wired but unconfigured — the honest remaining
   boundary between "grader validated" and "skill behaviour validated" for a real model.
2. Three of four fuzz modes have a compile-and-kill fixture (parser robustness, round-trip —
   the latter twice, grading opposite failure directions — and differential).
   **Struct-aware / multi-parameter** does not. The refusal path is covered separately by
   `trivial_add`.
3. ~~Only `testing` is imported when compiling a graded response.~~ **Closed**: the runner
   now derives the import block from the harness text (`test_file_for`), so a response using
   `unicode/utf8` (the round-trip domain guard), `encoding/json` (Template D), `bytes`, and
   the other common stdlib helpers compiles as-is. A response that emits its own `import`
   block is used verbatim.
4. Anti-example coverage is thematic (5 of 9), not one test per mistake.
5. No fixture exercises `-race` combined with a fuzz run end to end.
6. Crash-artifact and cache behaviour is pinned by string assertions on the YAML, not by
   executing a workflow — an `act`-based run would be the stronger check.

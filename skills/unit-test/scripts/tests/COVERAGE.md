# Unit-Test Skill — Rule-to-Scenario Coverage Matrix

Maps each core rule/section in SKILL.md to its golden fixture and contract test. Use this to identify coverage gaps when adding new rules.

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

## Coverage Summary

| Metric | Count |
|--------|-------|
| Total golden fixtures | 15 |
| Test generation (positive) | 13 |
| Exclusions (negative) | 2 |
| Target types covered | 5/5 (Service, Function, Handler, CLI, Middleware) |
| Modes covered | 3/3 (Light 1, Standard 5, Strict 4+2 excl) |
| Reference files | 5 |
| Contract tests | 67 |
| Golden scenario tests | 17 |

## Gap Analysis

When adding a new rule to SKILL.md or references:

1. Add a golden fixture that exercises the rule.
2. Add a contract test that verifies the rule text exists.
3. Update this matrix.

### Known Coverage Gaps (TODO for future fixtures)

| Scenario | Category | Priority |
|----------|----------|----------|
| gRPC handler target type | target_type | Low |
| Golden file / snapshot test anti-example | anti_example | Low |
| Fuzzing + unit test collaboration example | technique | Low |
| Shuffle-dependent test detection | technique | Low |
| PR-diff scope integration test | workflow | Low |
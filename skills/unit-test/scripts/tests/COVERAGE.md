# Unit-Test Skill — Rule-to-Scenario Coverage Matrix

Maps each core rule/section in SKILL.md to its golden fixture and contract test. Use this to identify coverage gaps when adding new rules.

## Contract Tests (`test_skill_contract.py`)

| Rule / Section | Test | Status |
|----------------|------|--------|
| Frontmatter name | `test_skill_name_is_valid` | ✅ |
| Coverage threshold 80% | `test_coverage_threshold_consistent_at_80` | ✅ |
| Assertion style adaptive | `test_default_prompt_is_assertion_style_adaptive` | ✅ |
| Scorecard incremental mode | `test_scorecard_boundary_for_incremental_mode` | ✅ |
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
| High-Signal Budget | `test_high_signal_test_budget_range` | ✅ |
| Test Structure parallel safety | `test_test_structure_parallel_safety` | ✅ |
| Workflow version + exclusion steps | `test_workflow_includes_version_and_exclusion_steps` | ✅ |
| Incremental Mode 3 flows | `test_incremental_mode_three_flows` | ✅ |
| Output version/exclusion info | `test_output_expectations_include_version_and_exclusion` | ✅ |
| Scorecard weight tiers | `test_scorecard_has_weight_tiers`, `test_scorecard_critical_items` | ✅ |
| Shuffle guidance | `test_shuffle_guidance_exists` | ✅ |
| Fuzzing collaboration | `test_fuzzing_collaboration_guidance` | ✅ |
| PR-diff scoped testing | `test_pr_diff_scope_section_exists` | ✅ |
| JSON summary output | `test_json_summary_exists` | ✅ |

## Golden Fixtures (`test_golden_scenarios.py`)

### Test Generation (should produce tests)

| ID | Scenario | Target Type | Techniques Verified |
|----|----------|-------------|---------------------|
| 001 | Pure function with slice boundary | Package-level functions | Off-by-One, Collection Mapping |
| 002 | Service method with repo dependency | Service interface | Dependency Error Propagation, Mutation-Resistant |
| 003 | Handler with goroutine fan-out | Service interface | Concurrency, Race detection, Error fan-in |
| 006 | List transform method | Service interface | Collection Mapping, Off-by-One |
| 007 | HTTP handler with JSON body | HTTP handler | Mutation-Resistant, Dependency Error |
| 008 | CLI command runner with flags | CLI command/runner | Dependency Error, Off-by-One |
| 009 | Auth middleware pass/block/error | Middleware | Branch Completeness, Mutation-Resistant |

### Exclusions (should NOT produce tests)

| ID | Scenario | Exclusion Reason |
|----|----------|-----------------|
| 004 | Protobuf generated file | generated_code |
| 005 | Trivial getter with no logic | anti_example |

## Coverage Summary

| Metric | Count |
|--------|-------|
| Total golden fixtures | 9 |
| Test generation (positive) | 7 |
| Exclusions (negative) | 2 |
| Target types covered | 5/5 (Service, Function, Handler, CLI, Middleware) |
| Contract tests | 30 |
| Golden scenario tests | 11 |

## Gap Analysis

When adding a new rule to SKILL.md or references:

1. Add a golden fixture that exercises the rule.
2. Add a contract test that verifies the rule text exists.
3. Update this matrix.

### Known Coverage Gaps (TODO for future fixtures)

| Scenario | Category | Priority |
|----------|----------|----------|
| gRPC handler target type | target_type | Low |
| Concurrent map access test pattern | concurrency | Medium |
| Golden file / snapshot test anti-example | anti_example | Low |
| Fuzzing + unit test collaboration example | technique | Low |
| Shuffle-dependent test detection | technique | Low |
| PR-diff scope integration test | workflow | Low |
| Scorecard tier weighting validation | meta | Medium |

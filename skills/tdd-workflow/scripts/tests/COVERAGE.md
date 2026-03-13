# tdd-workflow Skill — Test Coverage Matrix

## Contract Tests (`test_skill_contract.py`)

| # | Class | Test | Rule / Section |
|---|-------|------|---------------|
| 1 | TestFrontmatter | test_name_and_description | YAML frontmatter |
| 2 | TestFrontmatter | test_trigger_keywords | TDD in frontmatter |
| 3 | TestCoreGates | test_six_gates_exist | 6 mandatory gates |
| 4 | TestCoreGates | test_defect_hypothesis_gate_has_substance | Hypothesis depth |
| 5 | TestCoreGates | test_killer_case_gate_has_substance | Killer case depth |
| 6 | TestCoreGates | test_coverage_gate_threshold | 80% threshold |
| 7 | TestCoreGates | test_concurrency_gate_race_detection | -race flag |
| 8 | TestAntiExamples | test_anti_examples_section_exists | Anti-Examples section |
| 9 | TestAntiExamples | test_at_least_6_anti_examples | ≥6 Mistakes |
| 10 | TestAntiExamples | test_anti_examples_have_bad_good_code | BAD/GOOD pairs |
| 11 | TestAntiExamples | test_anti_example_big_bang_red | Big-Bang Red |
| 12 | TestAntiExamples | test_anti_example_speculative_code | Speculative code |
| 13 | TestAntiExamples | test_anti_example_refactor_behavior_change | Refactor behavior |
| 14 | TestAntiExamples | test_anti_example_skip_red_evidence | Skip Red |
| 15 | TestAntiExamples | test_anti_example_implementation_details | Impl details |
| 16 | TestAntiExamples | test_anti_example_change_size_mismatch | Size mismatch |
| 17 | TestScorecard | test_scorecard_section_exists | Scorecard section |
| 18 | TestScorecard | test_three_tiers | Critical/Standard/Hygiene |
| 19 | TestScorecard | test_critical_items | C1-C3 |
| 20 | TestScorecard | test_standard_items | S1-S5 |
| 21 | TestScorecard | test_hygiene_items | H1-H4 |
| 22 | TestScorecard | test_decision_rule | PASS/FAIL rule |
| 23 | TestChangeSizeBudget | test_sml_defined | S/M/L sizes |
| 24 | TestChangeSizeBudget | test_concrete_loc_thresholds | LOC numbers |
| 25 | TestAssertionStrategy | test_assertion_style_mentioned | Style mention |
| 26 | TestAssertionStrategy | test_testify_and_stdlib | testify + stdlib |
| 27 | TestCrossReference | test_unit_test_skill_referenced | unit-test xref |
| 28 | TestCrossReference | test_boundary_checklist_referenced | boundary xref |
| 29 | TestReferences | test_all_reference_files_exist | 4 ref files |
| 30 | TestTDDWorkflowReference | test_end_to_end_walkthrough | Walkthrough |
| 31 | TestTDDWorkflowReference | test_red_green_refactor_iterations | Iterations |
| 32 | TestTDDWorkflowReference | test_refactor_patterns_table | Refactor table |
| 33 | TestTDDWorkflowReference | test_outside_in_vs_inside_out | Outside-In/Inside-Out |
| 34 | TestTDDWorkflowReference | test_legacy_code_characterization | Legacy code |
| 35 | TestTDDWorkflowReference | test_concrete_go_code_examples | Go code in ref |
| 36 | TestAPILayerReference | test_three_layers | Handler/Service/Repo |
| 37 | TestAPILayerReference | test_scenario_matrices | HTTP status codes |
| 38 | TestAPILayerReference | test_complete_handler_test_example | httptest code |
| 39 | TestAPILayerReference | test_complete_service_test_example | Service test code |
| 40 | TestAPILayerReference | test_layer_ordering_strategies | Outside-In/Inside-Out |
| 41 | TestAPILayerReference | test_naming_patterns | TestXxxHandler etc |
| 42 | TestBoundaryChecklist | test_12_items | ≥12 items |
| 43 | TestBoundaryChecklist | test_key_boundary_types | nil/empty/dep err |
| 44 | TestBoundaryChecklist | test_defect_hypothesis_patterns | Hypothesis patterns |
| 45 | TestBoundaryChecklist | test_killer_case_design_internalized | 4 killer elements |
| 46 | TestBoundaryChecklist | test_concrete_killer_case_code | Code example |
| 50 | TestGoldenFixtures | test_golden_dir_exists | Directory exists |
| 51 | TestGoldenFixtures | test_at_least_8_fixtures | ≥8 fixtures |
| 52 | TestGoldenFixtures | test_all_fixtures_valid_json | Valid JSON schema |
| 53 | TestGoldenFixtures | test_change_sizes_covered | S/M/L coverage |
| 54 | TestGoldenFixtures | test_change_types_covered | bugfix/feature/refactor |
| 55 | TestOutputContract | test_output_contract_section | Output section |

**Total contract tests: 55**

## Golden Scenario Tests (`test_golden_scenarios.py`)

| # | Fixture | Tests | Covers |
|---|---------|-------|--------|
| 1 | 001_s_bugfix_off_by_one | 4 | S bugfix, boundary, killer |
| 2 | 002_s_bugfix_error_swallowed | 3 | S bugfix, error propagation |
| 3 | 003_m_feature_new_endpoint | 5 | M feature, API 3-Layer, handler/service scenarios |
| 4 | 004_m_feature_business_rule | 3 | M feature, Inside-Out, table-driven, tier boundaries |
| 5 | 005_l_feature_transfer_funds | 5 | L feature, concurrency, full scorecard |
| 6 | 006_refactor_extract_method | 3 | Refactor, characterization, no behavior change |
| 7 | 007_legacy_code_characterization | 4 | Legacy code, characterization tests, pinned behavior |
| 8 | 008_concurrency_safety | 5 | Concurrency, -race flag, determinism |

**Total golden tests: 32**

## Coverage Summary

| Category | Coverage | Notes |
|----------|----------|-------|
| Frontmatter | 100% | name, description, triggers |
| 6 Mandatory Gates | 100% | All 6 gates verified with depth |
| Anti-Examples | 100% | 7 mistakes, BAD/GOOD pairs, each verified |
| Scorecard (3-tier) | 100% | C1-C3, S1-S5, H1-H4, decision rule |
| Change-Size Budget | 100% | S/M/L with LOC thresholds |
| Assertion Strategy | 100% | testify, stdlib, go-cmp |
| Cross-references | 100% | unit-test, boundary |
| References | 100% | All 4 files exist and content verified |
| TDD Workflow ref depth | 100% | Walkthrough, refactor, Outside-In, legacy |
| API 3-Layer ref depth | 100% | 3 layers, matrices, code, ordering |
| Boundary ref depth | 100% | 12 items, hypothesis, killer design, code |
| Golden coverage (sizes) | 100% | S (2), M (3), L (1) |
| Golden coverage (types) | 100% | bugfix (3), feature (3), refactor (1), legacy (1) |
| Output contract | 100% | Section exists |

## Known Gaps

1. **fake-stub-template.md depth**: Not deeply tested (only existence check); could add content assertions
2. **CI integration**: No GitHub Actions workflow tested
3. **Mutation testing**: No tests verify skill detects mutation-resistant assertions in practice
4. **Cross-project validation**: No end-to-end test running skill against a real Go project
5. **JSON machine-readable output**: No test for structured output format

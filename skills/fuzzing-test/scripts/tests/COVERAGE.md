# Fuzzing-Test Skill — Test Coverage Matrix

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

**Contract test count: 39**

## Golden Fixture Tests (test_golden_scenarios.py)

| Fixture | ID | Type | Validates |
|---------|-----|------|-----------|
| 001_parser_suitable.json | Parser decoder | Suitable (Tier 1) | Template A, size guard, oracle |
| 002_roundtrip_suitable.json | JSON codec | Suitable (Tier 2) | Template B, round-trip invariant |
| 003_differential_suitable.json | Algorithm rewrite | Suitable (Tier 3) | Template C, differential |
| 004_struct_aware_suitable.json | Struct processor | Suitable (Tier 2) | Template D, json.Unmarshal |
| 005_trivial_not_suitable.json | Add(a,b) | Not suitable | Check 1 fail, alternative |
| 006_no_oracle_not_suitable.json | Log function | Not suitable | Check 3 fail, alternative |
| 007_db_dependent_not_suitable.json | DB business logic | Not suitable | Check 2 fail, alternative |
| 008_validator_with_race.json | Validator w/ goroutine | Suitable + advanced | Race detection feature |

**Golden fixture count: 8**
**Golden test count: 21**

## Coverage Summary

| Category | Total | Tested | Coverage |
|---------|-------|--------|----------|
| Gates (4) | 4 | 4 | 100% |
| Templates (A-D) | 4 | 4 | 100% |
| Anti-examples (7) | 7 | 5 (key themes) | 71% |
| Scorecard tiers (3) | 3 | 3 | 100% |
| Scorecard items (12) | 12 | 12 | 100% |
| Reference files (4) | 4 | 4 | 100% |
| Go version entries (4) | 4 | 4 | 100% |
| Advanced features (4) | 4 | 4 | 100% |
| Applicability verdicts | 2 (suitable/not) | 2 | 100% |
| Golden: suitable scenarios | 5 | 5 | 100% |
| Golden: not-suitable scenarios | 3 | 3 | 100% |

**Total tests: 60** (39 contract + 21 golden)

## Known Gaps (Future)

1. Golden fixture for `go-fuzz-headers` specific scenario
2. Golden fixture for borderline/soft-warning case (Check 4 fails but stubbable)
3. Contract test for corpus management git policy rules
4. Contract test for troubleshooting section completeness
5. Integration test: run fuzz template against real Go code

# Systematic Debugging Skill — Coverage Matrix

Maps each critical rule cluster in `SKILL.md` and references to deterministic regression tests.

## Contract Tests (`test_skill_contract.py`)

| Area | Test | Status |
|------|------|--------|
| Frontmatter name | `test_name_is_correct` | ✅ |
| Description trigger coverage | `test_description_has_debugging_triggers` | ✅ |
| Progressive disclosure limit | `test_skill_md_stays_within_progressive_disclosure_limit` | ✅ |
| Mandatory gates | `test_all_five_gates_exist` | ✅ |
| Quality scorecard section | `test_scorecard_section_exists` | ✅ |
| Scorecard tiers and IDs | `test_scorecard_tiers_exist`, `test_scorecard_ids_exist` | ✅ |
| Scorecard JSON output | `test_scorecard_output_json_exists` | ✅ |
| Anti-example section | `test_skill_anti_example_section_exists` | ✅ |
| Anti-example category coverage | `test_skill_lists_all_anti_example_categories` | ✅ |
| BAD/GOOD reference depth | `test_reference_has_seven_bad_good_pairs` | ✅ |
| Selective loading | `test_all_reference_conditions_exist` | ✅ |
| Output contract sections | `test_output_contract_has_nine_sections` | ✅ |
| Output contract PASS/FAIL rules | `test_output_contract_has_pass_fail_rules` | ✅ |
| Reference inventory | `test_reference_inventory_exists` | ✅ |
| Reference depth >= 1000 | `test_reference_total_depth_is_at_least_1000_lines` | ✅ |
| Regression runner | `test_runner_exists`, `test_runner_references_both_commands` | ✅ |
| Coverage doc existence | `test_coverage_doc_exists` | ✅ |

## Golden Scenario Tests (`test_golden_scenarios.py`)

| Fixture | Scenario | Covers |
|---------|----------|--------|
| 001 | Flaky async cache race | race triage, `-race`, condition-based waiting, scorecard |
| 002 | Deep stack wrong value | root-cause tracing, source vs symptom |
| 003 | Performance regression | profile-first debugging, evidence gate |
| 004 | Multi-component config propagation | boundary evidence, environment/config debugging |
| 005 | Dependency break with no local code change | dependency strategy, recent-change analysis |
| 006 | Build failure from generated code | build error handling, version mismatch |
| 007 | P0 mitigate then investigate | mitigation-first workflow, output contract |
| 008 | Three failed fixes | architecture questioning, escalation rule |
| 009 | P0 mitigated but blocked | honest blocked report, partial verification, no guessed permanent fix |
| 010 | Goroutine leak masked as latency | leak/perf overlap, profiling evidence, residual risk |
| 011 | Timezone/locale environment drift | works-on-my-machine diffing, environment comparison |

## Summary

| Metric | Count |
|--------|-------|
| Contract tests | 23 |
| Golden fixture classes | 13 |
| Golden fixtures | 11 |
| Regression wrapper | 1 |

## Known Gaps

1. No LLM-in-the-loop evaluation of actual generated debugging reports.
2. `find-polluter.sh` behavior is tested separately, not via a scenario fixture.
3. No fixture yet for mixed security + dependency incident triage.

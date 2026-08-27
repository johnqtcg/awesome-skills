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
| Bug-type category count matches reference TOC (regression for the 8-vs-6 mismatch) | `test_bug_type_strategies_numbered_category_count`, `test_skill_does_not_overclaim_category_count` | ✅ |
| No false "binary search" claim for `find-polluter.sh` (regression for the algorithm-label mismatch) | `test_skill_does_not_claim_binary_search`, `test_script_does_not_claim_binary_search`, `test_skill_describes_sequential_behavior` | ✅ |
| Scope & Mode / C1 reconciliation (regression for the P2-shortcut vs. C1 contradiction) | `test_scope_and_mode_section_exists`, `test_c1_references_declared_mode_severity`, `test_diagnose_only_mode_is_a_valid_terminal_state` | ✅ |
| Destructive commands excluded from `allowed-tools` | `test_no_git_init_in_allowed_tools`, `test_no_rm_rf_in_allowed_tools` | ✅ |
| Scorecard H2 includes mode, and Critical IDs match between SKILL.md and the reference (regression for the H2/C5 desync) | `test_scorecard_h2_includes_mode`, `test_scorecard_and_skill_agree_on_critical_ids` | ✅ |
| PASS/FAIL rules state Critical is never offset by Standard/Hygiene (regression for the S2+S4-both-fail-yet-PASS contradiction) | `test_pass_fail_rules_state_critical_is_not_offset` | ✅ |
| Verification section is mode-aware (diagnose-only doesn't require "symptom is gone") | `test_verification_section_is_mode_aware` | ✅ |
| `find-polluter.sh` INCOMPLETE exit code documented and used | `test_incomplete_exit_code_is_documented_and_used` | ✅ |
| `defense-in-depth.md` path-boundary check present, naive unguarded `startsWith` absent | `test_boundary_safe_check_present`, `test_naive_unguarded_startswith_not_present` | ✅ |
| Output Contract Triage template has an explicit Mode field (regression for the H2-requires-mode-but-template-lacks-it gap) | `test_triage_template_has_mode_field` | ✅ |
| N/A scope restricted to C1/C4 only, S2 explicitly named (regression for the live-scenario S2-marked-N/A scoring error) | `test_s2_explicitly_named_as_not_na_able`, `test_only_c1_and_c4_may_be_na` | ✅ |
| `env`/`tcpdump` excluded from `allowed-tools` (regression for pre-approved sensitive-data-exposure commands) | `test_no_bare_env_wildcard_in_allowed_tools`, `test_no_tcpdump_wildcard_in_allowed_tools` | ✅ |
| Live-scenario transcripts actually preserved and count matches prose (regression for unreviewable summaries and the four-vs-five miscount) | `test_transcripts_directory_exists`, `test_readme_exists`, `test_at_least_five_transcripts_present`, `test_coverage_doc_says_five_not_four` | ✅ |

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

## Runner Behavior Tests (`test_find_polluter.py`)

| Area | Test | Status |
|------|------|--------|
| Finds the polluting file | `test_finds_polluter` | ✅ |
| Clean suite returns 0 | `test_clean_suite_returns_zero` | ✅ |
| Pre-existing pollution rejected | `test_existing_pollution_returns_two` | ✅ |
| Runner-execution failure is surfaced, not swallowed as "clean" (regression for the `\|\| true` exit-code bug), and returns a distinct INCOMPLETE exit code (4), not 0 | `test_runner_failure_is_surfaced_not_swallowed`, `test_partial_runner_failure_also_returns_incomplete_code` | ✅ |
| No caveat text when every run executed cleanly | `test_clean_suite_with_no_failures_has_no_caveat` | ✅ |

## Summary

| Metric | Count |
|--------|-------|
| Contract tests | 48 |
| Runner behavior tests | 6 |
| Golden fixture classes | 13 |
| Golden fixtures | 11 |
| Regression wrapper | 1 |
| **Total (`run_regression.sh`)** | **95** |

## Live Scenario Verification (manual, 2026-08-27, round 2)

Deterministic tests above check that the documents are internally consistent; they cannot check that a model actually behaves as documented. In response to a second review round asking specifically for this, five fresh general-purpose subagents (no shared context with the authoring session) were given real user-style requests against small synthetic codebases and asked to respond exactly as they normally would, with no hint about what was being tested. Raw JSONL transcripts for all five are preserved at `evaluate/systematic-debugging-live-scenarios-2026-08-27/` (see that directory's `README.md` for the scenario-to-file mapping) — the table below is a summary, not a replacement for those files. The outcomes were:

| Scenario | Setup | Outcome |
|----------|-------|---------|
| Diagnose-only | Stale-cache bug (inverted TTL comparison), user explicitly says "don't change any code yet" | PASS — declared diagnose-only mode, found and evidenced the exact root cause via a monkeypatched repro (no sleeping, no real time elapsed), left the fix unimplemented and clearly labeled as a sketch, marked C1 N/A with reason, confirmed via self-report that no file was modified |
| P0, no explicit authorization | "Production down, 500s on checkout, what do we do" — no "you're authorized to act" language | PASS — explicitly framed rollback/mitigation as "an operational call only you ... can make and execute," asked for confirmation of what changed, raised rollback risk, recommended evidence preservation before any mitigation |
| P2 collapsed hypothesis, attempt 1 | One-line error-message typo, cause stated by the user | Skill not invoked — the agent judged this wasn't a debugging task (cause already known), and fixed it directly. Legitimate judgment call, but didn't exercise the collapse rule. |
| P2 collapsed hypothesis, attempt 2 | 3-line function, symptom-only report, cause obvious on first read | Skill not invoked again, same reasoning — a single glance was enough to find the cause, so the agent judged the process to be overhead rather than a rule to follow. |
| P2 collapsed hypothesis, attempt 3 | Two-file rate-limiter bug, symptom-only report, cause revealed by a doc comment after reading both files | PARTIAL — invoked the skill, explicitly cited "the skill's rules say Phase 2 is skippable and Phase 3 collapses to one hypothesis line at that severity, so a one-line hypothesis + skipped pattern-analysis phase is the compliant path, not a shortcut around it," and produced a right-sized report — but **incorrectly marked Standard-tier item S2 as N/A**. `references/scope-and-severity.md` is explicit that only C1 and C4 may ever be N/A; a single-component issue should score S2 as an ordinary PASS, not N/A. This is a real scoring error by the subagent, not a correct extension of the convention — see `evaluate/systematic-debugging-live-scenarios-2026-08-27/README.md` for detail. `scope-and-severity.md` has since been tightened with an explicit S2 worked example to make this misreading less likely, but it is not re-tested live here. |

**Reading on the two "not invoked" P2 attempts**: this is not a skill defect to fix — a model correctly judging a single self-evident one-glance bug as not warranting any formal process is the *proportionate* behavior the "P2 15-30min, obvious cause" design intends, arguably in its most extreme form (skip the process entirely rather than just compressing it). It does mean the specific in-skill P2-collapse mechanism (as opposed to "skip the skill altogether") only gets exercised once a case clears some minimum bar of "worth looking into," which the third attempt supplied. Treat this as a genuine empirical finding about the trigger boundary, not a gap to close by making the skill fire more eagerly on trivial fixes.

**Reading on the S2/N/A error**: this is the one place where live testing caught something the deterministic tests could not — a model reading `scope-and-severity.md`'s C1/C4 N/A carve-outs generalized the pattern to a case the document didn't license. It's evidence the live-testing effort is doing real verification work (it found a live defect), not evidence the skill is unreliable — but it also means this specific finding should not be read as "the third P2 attempt fully passed."

## Known Gaps

1. The five scenarios above are real live-agent evidence, but they are still only 5 runs across 3 of the skill's behaviors, not a scored evaluation — no assertion counting, no with/without-skill comparison, no statistical confidence. A proper re-run of `evaluate/systematic-debugging-skill-eval-report.md`'s methodology (§2.3) against the current file remains the way to get that.
2. `find-polluter.sh` behavior is tested separately, not via a scenario fixture.
3. No fixture yet for mixed security + dependency incident triage.
4. No fixture yet exercising the N/A-scoring convention's edge cases (e.g. a report that marks something N/A without a stated reason, or marks C1 N/A while a fix was actually implemented) — `references/scope-and-severity.md` documents that these should fail H4/C1/C2, but no test (deterministic or live) currently exercises the failure path, only the correct-usage path.

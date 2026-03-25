# Create-PR Skill — Test Coverage Matrix

## Script Unit Tests (`test_create_pr.py`)

| Test | Validates |
|------|-----------|
| `test_parse_diff_added_lines` | Added-line extraction from unified diff hunks |
| `test_scan_secrets_respects_allowlist` | Secret scan allowlist suppression |
| `test_scan_secrets_ignores_env_reference_assignment` | Env-reference false-positive suppression |
| `test_scan_secrets_catches_high_signal_token` | High-signal secret detection |
| `test_filter_files_extension_and_exclude` | Include-extension and exclude-regex filtering |
| `test_resolve_settings_reads_repo_config` | Config loading + deep-merge overrides |
| `test_parse_required_status_checks` | Branch protection status-check extraction |
| `test_classify_repo_slug` | Owner/repo slug parsing |
| `test_gate_a_branch_protection_missing_becomes_suppressed` | Gate A suppression path for missing protection API |
| `test_scan_conflict_markers_requires_complete_block` | Complete merge-conflict block detection |
| `test_scan_conflict_markers_ignores_partial_marker` | Partial marker false-positive suppression |
| `test_gate_a_branch_protection_missing_required_checks` | Suppression when protection lacks required checks/reviews |
| `test_gate_h_updates_existing_pr` | Existing-PR update flow instead of duplicate create |
| `test_determine_confidence_maps_gate_statuses` | `confirmed/likely/suspected` confidence mapping |
| `test_build_body_includes_changed_files_and_uncovered_risk` | PR body rendering for changed files, test evidence, and uncovered risks |

**Script unit test count: 15**

## Contract Tests (`test_skill_contract.py`)

| Test | Validates |
|------|-----------|
| `test_frontmatter_name_and_description` | Frontmatter metadata matches skill identity |
| `test_skill_references_all_supporting_files` | `SKILL.md` references and all support files exist |
| `test_quick_reference_covers_all_gates` | Quick Reference includes Gate A-H + confidence mapping |
| `test_non_negotiables_capture_release_safety_rules` | Main safety constraints and PR-title rule |
| `test_readiness_confidence_and_suspected_rule` | `confirmed/likely/suspected` semantics and ready restriction |
| `test_suppression_rules_define_only_three_reasons` | Suppression contract and uncovered-risk recording |
| `test_fixed_process_lists_all_steps_and_fast_path` | Ordered workflow + fast-path rule |
| `test_gate_a_has_required_preflight_commands_and_suppression` | Auth/repo preflight commands and 404/403 suppression path |
| `test_gate_b_covers_branch_hygiene_and_no_auto_rebase` | Branch naming, conflict scans, sync, no auto-rebase |
| `test_gate_c_covers_high_risk_areas_size_thresholds_and_monorepo` | High-risk areas, PR-size thresholds, monorepo scoping |
| `test_gate_d_requires_project_checks_then_language_defaults` | Quality-gate order and uncovered-risk behavior |
| `test_gate_e_covers_secret_scans_and_go_security_tools` | Secret scans + `gosec` + `govulncheck` rules |
| `test_gate_f_requires_docs_and_compatibility_notes` | Docs/changelog + compatibility + rollout/rollback |
| `test_gate_g_requires_commit_hygiene_title_quality_and_self_review` | Commit set quality, title quality, and self-review |
| `test_gate_h_requires_post_create_verification` | Base/head/title/body/draft verification and optional checks |
| `test_draft_vs_ready_decision_rules_exist` | Ready vs draft decision contract |
| `test_required_pr_body_structure_has_8_sections` | 8-section PR body contract |
| `test_command_playbook_covers_push_create_edit_and_view` | Publish workflow commands |
| `test_output_contract_order_is_defined` | Final response ordering |
| `test_pr_body_template_has_all_sections_and_tables` | PR template structure and evidence table |
| `test_checklists_cover_preflight_security_publication_and_maintenance` | Checklist sections + maintenance guidance |
| `test_bundled_script_guide_covers_behavior_examples_and_exit_codes` | Script-guide behavior, examples, exit codes |
| `test_merge_strategy_guide_covers_three_strategies_and_squash_priority` | Merge strategy guidance |
| `test_config_example_covers_core_and_nested_settings` | Config example structure |
| `test_run_regression_runs_validator_help_and_unittest_discovery` | Unified regression runner contract |
| `test_bundled_script_exposes_exit_codes_and_main_returns_all_three` | Exit-code docs and script return paths |

**Contract test count: 26**

## Golden Scenario Tests (`test_golden_scenarios.py`)

| Fixture | Scenario Type | Validates |
|---------|--------------|-----------|
| `001_ready_small_change.json` | `ready_flow` | Confirmed evidence path can be `ready` |
| `002_branch_protection_suppressed.json` | `protection_suppression` | Branch-protection suppression remains non-blocking |
| `003_behind_main_blocker.json` | `sync_blocker` | Behind-main state blocks and forbids auto-rebase |
| `004_high_risk_auth_change.json` | `high_risk` | High-risk PRs require explicit risk/rollback notes |
| `005_oversized_pr_warning.json` | `oversized` | Large-PR warnings and split guidance |
| `006_quality_gap_keeps_draft.json` | `quality_gap` | Missing quality evidence keeps PR in draft |
| `007_existing_pr_update.json` | `existing_pr_update` | Existing PR gets updated instead of duplicated |
| `008_squash_merge_title_priority.json` | `merge_strategy` | Squash-merge title quality guidance |
| `009_secret_leak_blocker.json` | `secret_blocker` | Secret findings block ready state |

**Golden fixture count: 9**
**Golden test count: 16** (6 integrity + 10 scenario/rule coverage)

## Coverage Summary

| Category | Total | Tested | Coverage |
|---------|-------|--------|----------|
| Mandatory gates (A-H) | 8 | 8 | 100% |
| Readiness confidence levels | 3 | 3 | 100% |
| Draft/ready decision paths | 3 | 3 | 100% |
| Reference docs | 5 | 5 | 100% |
| PR body sections | 8 | 8 | 100% |
| Golden decision scenarios | 9 | 9 | 100% |

**Total tests: 57** (15 script + 26 contract + 16 golden)

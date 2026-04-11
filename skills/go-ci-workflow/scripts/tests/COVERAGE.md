# Go-CI-Workflow Skill — Test Coverage Matrix

## Contract Tests (`test_skill_contract.py`)

Reorganized into 10 focused test classes (previously: 1 monolithic class with 43 tests).

### `TestFrontmatter` (1 test)

| Test | Validates |
|------|-----------|
| `test_frontmatter_name_and_description` | SKILL.md frontmatter name + GitHub Actions keyword |

### `TestSkillMdStructure` (12 tests)

| Test | Validates |
|------|-----------|
| `test_skill_md_under_line_budget` | SKILL.md ≤ 350 lines |
| `test_priority_and_fallback_exist` | Execution Priority + inline fallback + Mandatory Gates + Degraded Output Gate |
| `test_skill_has_5_mandatory_gates` | All 5 gate headings present |
| `test_repository_shape_gate_lists_all_shapes` | All 6 repository shapes listed in Shape Gate |
| `test_local_parity_gate_has_3_execution_paths` | make target / repo task / inline fallback |
| `test_security_gate_covers_events_and_permissions` | Events (PR/push/workflow_call) + fork secrets + minimum permissions |
| `test_execution_integrity_gate_requires_not_run_language` | "Not run in this environment" + exact commands |
| `test_output_contract_has_9_fields` | All 9 output contract fields present |
| `test_advanced_rules_reference_new_patterns` | composite actions + service containers + path filters |
| `test_operating_model_has_5_steps` | All 5 workflow steps present |
| `test_skill_references_discover_script` | discover_ci_needs.sh referenced |
| `test_skill_cross_references_go_makefile_writer` | $go-makefile-writer cross-reference |

### `TestReferenceFiles` (1 test)

| Test | Validates |
|------|-----------|
| `test_all_references_and_scripts_exist` | All 9 reference files and scripts exist on disk |

### `TestWorkflowQualityGuide` (6 tests)

| Test | Validates |
|------|-----------|
| `test_wqg_has_toc` | Table of Contents present |
| `test_wqg_has_all_15_sections` | All 15 section headings exist |
| `test_wqg_core_gate_delegates_to_make` | `make ci COVER_MIN=80` + delegation pattern |
| `test_wqg_robustness_and_anti_patterns_have_substantive_rules` | Robustness rules + anti-pattern list |
| `test_wqg_tool_version_currency_note` | Version currency warning present |
| `test_wqg_mentions_monorepo` | monorepo coverage |

### `TestAdvancedPatterns` (9 tests)

| Test | Validates |
|------|-----------|
| `test_gap_has_all_9_sections` | All 9 section headings exist |
| `test_gap_fork_pr_has_if_condition_yaml` | Concrete fork PR guard `if:` condition |
| `test_gap_fork_pr_warns_about_pull_request_target` | pull_request_target danger warning |
| `test_gap_permissions_has_github_token_section` | GITHUB_TOKEN vs custom PAT guidance |
| `test_gap_permissions_has_escalation_table` | contents:write / packages:write / pull-requests:write |
| `test_gap_composite_actions_has_comparison_table` | Composite vs Reusable comparison table |
| `test_gap_service_containers_has_health_checks` | health-cmd + pg_isready + redis-cli |
| `test_gap_service_containers_has_common_images_table` | 5 databases (PG/MySQL/Redis/Kafka/MongoDB) |
| `test_gap_timeout_table_exists` | Timeout recommendations (15/20/30 min) |

### `TestGoldenExamples` (5 tests) · `TestRepositoryShapes` (5 tests) · `TestChecklist` (2 tests) · `TestFallback` (1 test) · `TestDiscoveryScript` (2 tests)

_(unchanged from prior version — see individual test files for details)_

**Contract test count: 44** (43 original + 1 line-budget test, split into 10 classes)

## Golden Fixture Tests (`test_golden_scenarios.py`)

### Scenario Fixtures and Behavioral Assertions

| Fixture | Scenario Type | Rules Coverage | Behavioral Assertions |
|---------|--------------|----------------|-----------------------|
| `001_single_module_service.json` | `single_module_service` | ✅ | ✅ full parity + make target paths |
| `002_single_module_library.json` | `single_module_library` | ✅ | ✅ matrix in rules |
| `003_multi_module_repo.json` | `multi_module` | ✅ | ✅ **expected_shape == multi-module + gate list** |
| `004_monorepo_path_filters.json` | `monorepo` | ✅ | ✅ path filter in rules |
| `005_docker_heavy_repo.json` | `docker_heavy` | ✅ | ✅ **expected_shape == Docker-heavy + separate jobs** |
| `006_no_makefile_fallback.json` | `no_makefile` | ✅ | ✅ partial parity + Degraded Output Gate |
| `007_fork_pr_security.json` | `fork_pr_security` | ✅ | ✅ Security Gate required |
| `008_service_containers_integration.json` | `service_containers` | ✅ | ✅ **api-integration in expected_jobs + service container** |
| `009_e2e_job.json` | `e2e_test` | ✅ | ✅ **ci+e2e jobs + schedule trigger + 30min timeout** |
| `010_static_analysis_job.json` | `static_analysis` | ✅ | ✅ **govulncheck job + Vulnerability Scanning + Static Analysis** |

**Golden fixture count: 10**
**Golden test count: 24** (10 rules-coverage + 4 integrity + 10 behavioral assertions)

## Coverage Summary

| Category | Total | Tested | Coverage |
|---------|-------|--------|----------|
| Mandatory gates (5) | 5 | 5 | 100% |
| Repository shapes (6) | 6 | 6 | 100% |
| Job types (core/docker/integration/e2e/vuln/static) | 6 | **6** | **100%** |
| Trigger types (PR/push/schedule/workflow_call) | 4 | **4** | **100%** |
| Execution paths (make target/repo task/inline fallback) | 3 | 3 | 100% |
| Parity levels (full/partial/scaffold) | 3 | 3 | 100% |
| Output contract fields (9) | 9 | 9 | 100% |
| WQG sections (15) | 15 | 15 | 100% |
| Advanced pattern sections (9) | 9 | 9 | 100% |
| Golden examples (4) | 4 | 4 | 100% |
| PR checklist sections (10) | 10 | 10 | 100% |
| Fallback levels (3) | 3 | 3 | 100% |
| Discover script categories (8) | 8 | 8 | 100% |
| Golden fixtures: scenario types (10) | 10 | 10 | 100% |
| Behavioral assertions per fixture | 10 | 10 | 100% |

**Total tests: 68** (44 contract + 24 golden)

## Known Gaps

| Gap | Priority |
|-----|----------|
| Golden fixture for reusable workflow extraction scenario | Medium |
| Golden fixture for self-hosted runner scenario | Medium |
| Golden example for fork PR security in golden-examples.md | Medium |
| Integration test: run discover_ci_needs.sh against mock repo | Low |
| Golden fixture for tag-triggered release workflow | Low |
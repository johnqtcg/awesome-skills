# Go-CI-Workflow Skill — Test Coverage Matrix

## Contract Tests (test_skill_contract.py)

### Frontmatter

| Test | Validates |
|------|-----------|
| test_frontmatter_name_and_description | SKILL.md frontmatter name + GitHub Actions keyword |

### SKILL.md Structure

| Test | Validates |
|------|-----------|
| test_priority_and_fallback_exist | Execution Priority + inline fallback + Mandatory Gates + Degraded Output Gate |
| test_skill_has_5_mandatory_gates | All 5 gate headings present |
| test_repository_shape_gate_lists_all_shapes | All 6 repository shapes listed in Shape Gate |
| test_local_parity_gate_has_3_execution_paths | make target / repo task / inline fallback |
| test_security_gate_covers_events_and_permissions | Events (PR/push/workflow_call) + fork secrets + minimum permissions |
| test_execution_integrity_gate_requires_not_run_language | "Not run in this environment" + exact commands |
| test_output_contract_has_9_fields | All 9 output contract fields present |
| test_advanced_rules_reference_new_patterns | composite actions + service containers + path filters |
| test_operating_model_has_5_steps | All 5 workflow steps present |
| test_skill_references_discover_script | discover_ci_needs.sh referenced |
| test_skill_cross_references_go_makefile_writer | $go-makefile-writer cross-reference |

### workflow-quality-guide.md (16 sections)

| Test | Validates |
|------|-----------|
| test_wqg_has_toc | Table of Contents present |
| test_wqg_has_all_16_sections | All 16 section headings exist |
| test_wqg_core_gate_delegates_to_make | make ci COVER_MIN=80 + delegation pattern |
| test_wqg_anti_patterns_has_bad_good_pairs | >= 5 BAD/GOOD pairs, counts match |
| test_wqg_tool_version_currency_note | Version currency warning present |
| test_wqg_mentions_monorepo | monorepo coverage |

### github-actions-advanced-patterns.md (9 sections)

| Test | Validates |
|------|-----------|
| test_gap_has_all_9_sections | All 9 section headings exist |
| test_gap_fork_pr_has_if_condition_yaml | Concrete fork PR guard `if:` condition |
| test_gap_fork_pr_warns_about_pull_request_target | pull_request_target danger warning |
| test_gap_permissions_has_github_token_section | GITHUB_TOKEN vs custom PAT guidance |
| test_gap_permissions_has_escalation_table | contents:write / packages:write / pull-requests:write |
| test_gap_composite_actions_has_comparison_table | Composite vs Reusable comparison table |
| test_gap_service_containers_has_health_checks | health-cmd + pg_isready + redis-cli |
| test_gap_service_containers_has_common_images_table | 5 databases (PG/MySQL/Redis/Kafka/MongoDB) |
| test_gap_timeout_table_exists | Timeout recommendations (15/20/30 min) |

### golden-examples.md (4 examples)

| Test | Validates |
|------|-----------|
| test_ge_has_toc | Table of Contents present |
| test_ge_has_all_4_examples | All 4 example headings exist |
| test_ge_each_has_complete_workflow_and_output_summary | 4 Complete Workflow + 4 Output Summary sections |
| test_ge_fallback_has_inline_markers | INLINE FALLBACK markers + PARTIAL parity label |
| test_ge_service_container_example_has_services_block | services: + mysql: + redis: in YAML |

### repository-shapes.md (6 shapes)

| Test | Validates |
|------|-----------|
| test_rs_has_all_6_shapes | All 6 shape headings exist |
| test_rs_monorepo_has_path_filter_patterns | Path Filter Pattern + dorny/paths-filter |
| test_rs_multi_module_has_matrix_yaml | fail-fast: false + per-module go-version-file |
| test_rs_docker_heavy_has_matrix_include | matrix + dockerfile include pattern |
| test_rs_no_makefile_has_fallback_marking | INLINE FALLBACK marking convention |

### pr-checklist.md

| Test | Validates |
|------|-----------|
| test_pr_checklist_has_10_sections | All 10 checklist section numbers |
| test_pr_checklist_mentions_permissions_and_fallback | permissions + fallback keywords |

### fallback-and-scaffolding.md

| Test | Validates |
|------|-----------|
| test_fb_has_3_fallback_levels | Level A (Full) / Level B (Partial) / Level C (Scaffold) |

### discover_ci_needs.sh

| Test | Validates |
|------|-----------|
| test_discover_script_has_8_categories | All 8 TSV categories present |
| test_discover_script_handles_shapes | go.mod detection + shape classification |

**Contract test count: 44**

## Golden Fixture Tests (test_golden_scenarios.py)

| Fixture | Scenario Type | Validates |
|---------|--------------|-----------|
| 001_single_module_service.json | single_module_service | Full parity + make ci + make docker-build + concurrency |
| 002_single_module_library.json | single_module_library | Matrix strategy + coverage threshold |
| 003_multi_module_repo.json | multi_module | Nested go.mod detection + per-module orchestration |
| 004_monorepo_path_filters.json | monorepo | Path filter + multiple apps + job separation |
| 005_docker_heavy_repo.json | docker_heavy | Separate Docker jobs + multi-Dockerfile handling |
| 006_no_makefile_fallback.json | no_makefile | Degraded Output Gate + inline fallback + scaffold + follow-up |
| 007_fork_pr_security.json | fork_pr_security | Security Gate + fork PR guard + secrets + pull_request_target |
| 008_service_containers_integration.json | service_containers | Service container pattern + integration test job |

**Golden fixture count: 8**
**Golden test count: 17** (8 rules-coverage + 4 integrity + 5 behavioral assertions)

## Coverage Summary

| Category | Total | Tested | Coverage |
|---------|-------|--------|----------|
| Mandatory gates (5) | 5 | 5 | 100% |
| Repository shapes (6) | 6 | 6 | 100% |
| Job types (core/docker/integration/e2e/vuln/static) | 6 | 4 | 67% |
| Trigger types (PR/push/schedule/workflow_call) | 4 | 3 | 75% |
| Execution paths (make target/repo task/inline fallback) | 3 | 3 | 100% |
| Parity levels (full/partial/scaffold) | 3 | 3 | 100% |
| Output contract fields (9) | 9 | 9 | 100% |
| WQG sections (16) | 16 | 16 | 100% |
| Advanced pattern sections (9) | 9 | 9 | 100% |
| Golden examples (4) | 4 | 4 | 100% |
| PR checklist sections (10) | 10 | 10 | 100% |
| Fallback levels (3) | 3 | 3 | 100% |
| Discover script categories (8) | 8 | 8 | 100% |
| Golden fixtures: scenario types (8) | 8 | 8 | 100% |

**Total tests: 61** (44 contract + 17 golden)

## Comparison with Benchmark Skill

| Metric | go-code-reviewer | go-ci-workflow |
|--------|-----------------|----------------|
| Contract tests | 33 | 44 |
| Golden fixtures | 8 | 8 |
| Golden tests | 10 | 17 |
| Total tests | 43 | 61 |

## Known Gaps (Future)

1. Golden fixture for reusable workflow extraction scenario
2. Golden fixture for self-hosted runner scenario
3. Integration test: run discover_ci_needs.sh against mock repo structure
4. Golden fixture for tag-triggered release workflow
5. Golden example for fork PR security scenario in golden-examples.md

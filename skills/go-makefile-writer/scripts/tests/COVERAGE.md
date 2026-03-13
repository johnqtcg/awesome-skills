# Rule-to-Test Coverage Matrix

## Contract Tests (`test_skill_contract.py`)

| Test Class | Test | Verifies |
|---|---|---|
| TestSkillMdStructure | test_has_workflow_section | SKILL.md has `## Workflow` |
| TestSkillMdStructure | test_workflow_has_four_steps | 4-step workflow: Inspect → Plan → Compose → Validate |
| TestSkillMdStructure | test_has_rules_section | SKILL.md has `## Rules` |
| TestSkillMdStructure | test_has_output_contract | SKILL.md has `## Output Contract` |
| TestSkillMdStructure | test_output_contract_items | 5 required output items present |
| TestSkillMdStructure | test_references_quality_guide | Quality guide referenced |
| TestSkillMdStructure | test_references_pr_checklist | PR checklist referenced |
| TestSkillMdStructure | test_references_discovery_script | Discovery script referenced |
| TestSkillMdStructure | test_references_golden_examples | Golden examples referenced |
| TestSkillMdStructure | test_core_targets_listed | 7 core targets: help, fmt, tidy, test, cover, lint, clean |
| TestSkillMdStructure | test_version_injection_mentioned | `-ldflags` mentioned |
| TestSkillMdStructure | test_ci_target_mentioned | `ci` target mentioned |
| TestQualityGuideStructure | test_has_all_sections | All 15 guide sections present |
| TestQualityGuideStructure | test_has_help_pattern | awk + MAKEFILE_LIST help pattern |
| TestQualityGuideStructure | test_has_version_template | VERSION, COMMIT, BUILD_TIME, LDFLAGS |
| TestQualityGuideStructure | test_has_antipatterns | Anti-patterns section exists |
| TestQualityGuideStructure | test_has_validation_matrix | Validation matrix section exists |
| TestQualityGuideStructure | test_has_backward_compatibility | Backward compatibility section exists |
| TestQualityGuideStructure | test_cover_check_not_fragile | Fragile gsub pattern removed |
| TestQualityGuideStructure | test_fmt_not_git_only | `go fmt ./...` as primary fmt approach |
| TestQualityGuideStructure | test_cross_compile_not_hardcoded | Multi-binary cross-compile covered |
| TestQualityGuideStructure | test_compatibility_notes_present | Portability notes for CI environments |
| TestGoldenExamplesExist | test_simple_golden | Simple golden: DEFAULT_GOAL, LDFLAGS, PHONY, help, build, test, clean, -race, version |
| TestGoldenExamplesExist | test_complex_golden | Complex golden: same + multi-binary, Docker, generate, cross-compile |
| TestGoldenExamplesExist | test_complex_has_multi_binary | build-all, build-consumer-*, build-cron-* |
| TestGoldenExamplesExist | test_complex_has_docker | docker-build target |
| TestGoldenExamplesExist | test_complex_has_generate | generate + generate-check targets |
| TestGoldenExamplesExist | test_complex_has_cross_compile | CGO_ENABLED=0, GOOS=linux |
| TestDiscoveryScriptExists | test_file_exists | Script exists |
| TestDiscoveryScriptExists | test_is_executable | Script is executable |
| TestDiscoveryScriptExists | test_outputs_target_name | Outputs target_name column |
| TestDiscoveryScriptExists | test_supports_json_mode | --json flag supported |
| TestDiscoveryScriptExists | test_handles_known_kinds | api, consumer, cron, worker, migrate |
| TestPrChecklistExists | test_file_exists | PR checklist file exists |

## Golden Fixtures (`golden/*.json`)

| ID | Title | Type | Severity | Covered Rules |
|---|---|---|---|---|
| GOLDEN-001 | Missing help target | defect | high | help, .DEFAULT_GOAL, self-documenting |
| GOLDEN-002 | Test missing -race | defect | high | -race, race detection |
| GOLDEN-003 | Build without ldflags | defect | medium | -ldflags, VERSION, COMMIT, BUILD_TIME |
| GOLDEN-004 | Missing .PHONY | defect | medium | .PHONY |
| GOLDEN-005 | Cross-compile without CGO_ENABLED=0 | defect | high | CGO_ENABLED=0, static binaries |
| GOLDEN-006 | Target name mismatch | defect | low | Map target names, path semantics, build-<kind>-<name> |
| GOLDEN-007 | Unpinned tool versions | defect | medium | Pin versions, reproducib(ility) |
| GOLDEN-008 | Well-formed Makefile (FP) | false_positive | none | .DEFAULT_GOAL, -race, -ldflags, .PHONY |
| GOLDEN-009 | Custom help format (FP) | false_positive | none | help output self-documenting |
| GOLDEN-010 | gofmt -w variant (FP) | false_positive | none | quality targets |
| GOLDEN-011 | No Docker targets without Dockerfile (FP) | false_positive | none | container targets |

## Known Coverage Gaps

| Area | Gap | Priority |
|---|---|---|
| Makefile syntax | No test for tab-vs-space recipe indent | Low |
| CI parity | No test verifying `ci` target mirrors actual pipeline | Medium |
| Dependency check | No fixture for missing `tidy` target | Low |
| Backward compat | No fixture for renamed target without alias | Medium |
| Monorepo | SKILL.md now has monorepo section but no golden fixture yet | Low |

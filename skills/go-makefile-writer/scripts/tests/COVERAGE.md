# Rule-to-Test Coverage Matrix

## Contract Tests (`test_skill_contract.py`)

### `TestSkillMdStructure` (12 tests)

| Test | Verifies |
|------|----------|
| `test_has_workflow_section` | SKILL.md has `## Workflow` |
| `test_workflow_has_four_steps` | 4-step workflow: Inspect → Plan → Compose → Validate |
| `test_has_rules_section` | SKILL.md has `## Rules` |
| `test_has_output_contract` | SKILL.md has `## Output Contract` |
| `test_output_contract_items` | 5 required output items present |
| `test_references_quality_guide` | Quality guide referenced |
| `test_references_pr_checklist` | PR checklist referenced |
| `test_references_discovery_script` | Discovery script referenced |
| `test_references_golden_examples` | Golden examples referenced |
| `test_core_targets_listed` | 7 core targets: help, fmt, tidy, test, cover, lint, clean |
| `test_version_injection_mentioned` | `-ldflags` mentioned |
| `test_ci_target_mentioned` | `ci` target mentioned |

### `TestQualityGuideStructure` (9 tests)

| Test | Verifies |
|------|----------|
| `test_has_all_sections` | All 15 guide sections present |
| `test_has_help_pattern` | awk + MAKEFILE_LIST help pattern |
| `test_has_version_template` | VERSION, COMMIT, BUILD_TIME, LDFLAGS |
| `test_has_antipatterns` | Anti-patterns section exists |
| `test_has_validation_matrix` | Validation matrix section exists |
| `test_has_backward_compatibility` | Backward compatibility section exists |
| `test_cover_check_not_fragile` | Fragile gsub pattern removed |
| `test_fmt_not_git_only` | `go fmt ./...` as primary fmt approach |
| `test_compatibility_notes_present` | Portability notes for CI environments |

### `TestGoldenExamplesExist` (6 tests) + `TestDiscoveryScriptExists` (5 tests) + `TestPrChecklistExists` (1 test)

| Test | Verifies |
|------|----------|
| `test_simple_golden` / `test_complex_golden` | Golden Makefiles: DEFAULT_GOAL, LDFLAGS, PHONY, help, build, test, clean, -race, version |
| `test_complex_has_*` (3 tests) | multi-binary, Docker, generate, cross-compile targets |
| `test_discovery_*` (5 tests) | script exists, executable, target_name output, --json, kind coverage |
| `test_file_exists` (PR checklist) | PR checklist file exists |

### `TestSkillMdSections` — NEW (13 tests)

Covers the 6 SKILL.md sections that previously had no independent contract tests.

| Test | Section | Verifies |
|------|---------|----------|
| `test_skill_md_under_line_budget` | — | SKILL.md ≤ 400 lines |
| `test_anti_patterns_section_exists` | `## Anti-Patterns` | Section header exists |
| `test_anti_patterns_ci_parity_rule` | `## Anti-Patterns` | "mirror CI exactly" + "diverges from the actual CI pipeline" |
| `test_anti_patterns_cgo_rule` | `## Anti-Patterns` | "CGO_ENABLED=0" rule documented |
| `test_go_version_awareness_section_exists` | `## Go Version Awareness` | Section + "Go version: X.Y" output format |
| `test_go_version_awareness_has_table` | `## Go Version Awareness` | 1.18 and 1.21 version entries present |
| `test_execution_modes_section_exists` | `## Execution Modes` | Create + Refactor modes documented |
| `test_execution_modes_refactor_requires_minimal_diff` | `## Execution Modes` | "Minimal-diff edits" rule |
| `test_execution_modes_refactor_backward_compat` | `## Execution Modes` | "keep aliases" + "transition period" rules |
| `test_monorepo_support_section_exists` | `## Monorepo Support` | Section header exists |
| `test_monorepo_support_has_aggregate_targets` | `## Monorepo Support` | test-all, lint-all, build-all documented |
| `test_load_references_section_exists` | `## Load References Selectively` | Section + both reference files mentioned |
| `test_disable_model_invocation_in_frontmatter` | frontmatter | `disable-model-invocation: true` |

## Golden Fixtures (`golden/*.json`)

### Behavioral Tests (`TestMakefileDefectBehavior`) — NEW

Per-scenario behavioral verification (mirrors security-review TP/FP approach).

#### True Positives (defects)

| ID | File | Severity | Decision Tested |
|----|------|----------|-----------------|
| GOLDEN-001 | `001_missing_help.json` | high | Missing help target |
| GOLDEN-002 | `002_missing_race.json` | high | Test missing -race flag |
| GOLDEN-003 | `003_missing_ldflags.json` | medium | Build without version injection |
| GOLDEN-004 | `004_no_phony.json` | medium | Missing .PHONY declarations |
| GOLDEN-005 | `005_cross_compile_with_cgo.json` | high | Cross-compile without CGO_ENABLED=0 |
| GOLDEN-006 | `006_target_name_mismatch.json` | low | Target name mismatches cmd/ layout |
| GOLDEN-007 | `007_unpinned_tools.json` | medium | Unpinned tool @latest in CI |
| GOLDEN-012 | `012_ci_target_diverges.json` | high | **CI parity**: ci target diverges from pipeline |
| GOLDEN-013 | `013_refactor_rename_no_alias.json` | medium | **Backward compat**: rename without alias (refactor mode) |
| GOLDEN-014 | `014_monorepo_missing_aggregates.json` | medium | **Monorepo**: multi-module layout missing test-all/lint-all/build-all |
| GOLDEN-015 | `015_tab_vs_space_recipes.json` | high | **Tab-vs-space**: space-indented recipes fail Make parsing |
| GOLDEN-016 | `016_missing_tidy_target.json` | low | **Missing tidy**: no `go mod tidy` + `go mod verify` target |

#### False Positives (acceptable patterns, no defect expected)

| ID | File | Decision Tested |
|----|------|-----------------|
| GOLDEN-008 | `008_good_makefile.json` | Well-formed Makefile — skill must not report defects |
| GOLDEN-009 | `009_custom_help_format_fp.json` | Custom echo help is acceptable |
| GOLDEN-010 | `010_gofmt_variant_fp.json` | `gofmt -w` is an acceptable variant |
| GOLDEN-011 | `011_no_docker_targets_fp.json` | No Docker targets without Dockerfile is correct |

## Coverage Summary

| Metric | Count |
|--------|-------|
| Total golden fixtures | 16 (12 TP defects + 4 FP) |
| Contract tests | 46 (across 6 test classes) |
| Behavioral tests (`TestMakefileDefectBehavior`) | 16 |
| SKILL.md lines | 252 (budget: ≤ 400) |

## Known Coverage Gaps

| Area | Gap | Priority |
|------|-----|----------|
| Missing `cover` target | No fixture for project without `cover` target | Low |
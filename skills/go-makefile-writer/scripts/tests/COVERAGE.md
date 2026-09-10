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

### Fixture-contract tests (`TestGoldenFixtureContracts`)

Per-fixture contract checks: the fixture is internally well-formed and the rule
it exercises is written down in the docs. **These are not behavioural.** They
read each fixture's own declared `type`/`severity` and grep the prose, so they
pass whether or not the skill can detect anything — every error-propagation
defect fixed in the 2026-09-09 pass existed while this class was green. Real
behaviour, including the failure paths, is in `test_shipped_recipes.py` and
`test_executable_assets.py` (`GoToolchainDiscoveryTests`).

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

## Shipped-recipe contracts (`test_shipped_recipes.py`)

Every Makefile recipe the skill ships is extracted from **every** asset that
carries it — both golden templates, `SKILL.md`, the quality guide, the PR
checklist — built into a Makefile, and run against fixtures where the right
answer is known. Both halves are asserted: the negative case must fail and the
positive case must pass, so a recipe that always fails cannot satisfy the
contract. Every negative case runs twice, once as shipped and once with
`SHELL`/`.SHELLFLAGS` forced to a plain POSIX `/bin/sh`, because the templates
exist to be copied and a recipe that only propagates failure under `pipefail`
stops doing so on arrival.

| Capability | Negative cases (must fail) | Positive cases (must pass) |
|---|---|---|
| `fmt-check` | unformatted file; file that does not parse | gofmt-clean tree |
| `install-tools` | download fails (curl exit 22); download is empty | installer downloads and runs |
| `generate-check` | rewritten tracked file; rewritten **untracked** file; further change to an already-dirty file; generator deletes a tracked file; generator itself fails | no-op generator; unrelated pre-existing dirt; unrelated pre-existing **deletion** |
| `cover-check` | real module at 50%, threshold 90 | same module, threshold 10 |
| `check-tools`, `lint`, `swagger` | the recipe's **own** first guarded tool absent, the rest present | every guarded tool present |
| any `for x in $(VAR)` loop | first item fails and a later one succeeds; empty list | every item succeeds |

Prerequisites are pulled from the same document, so `cover-check: cover` runs
against a profile the shipped `cover` target produced rather than a stand-in.
The guarded tool for each tool-presence recipe is read out of the recipe itself
— a fixture hiding `golangci-lint` proves nothing about `swagger`, which guards
`swag`.

Three tests guard the harness rather than the skill, because a contract that
matches nothing passes silently:

| Test | Guards against |
|---|---|
| `RecipeExtractionTests` | the extractor finding no recipes in a source |
| `test_every_loop_variable_has_a_fixture` | a new loop variable iterating zero times and passing |
| `RecipeContractCoverageTests` | a new recipe shipping with neither a contract nor a written reason |
| `test_single_command_claims_hold` | an exemption that says "single command" while the recipe composes commands |
| `test_covered_by_claims_resolve_to_a_real_test` | an exemption naming a test class that does not exist, or never mentions the recipe |
| `test_every_guard_recipe_names_a_tool` | a tool-presence fixture that hides nothing |

Accounting is **per copy** and each category's claim is itself checked, because
the previous table asserted in prose that `cover-check` and `check-tools` were
covered by `GoldenMakefileExecutionTests` — which has neither a threshold test
nor a tool-presence test. Both now have real contracts.

`ModuleListAgreementTests` pins the two implementations that cannot be merged —
`discover_go_entrypoints.sh --modules` (a generation-time tool in the skill
directory) and the monorepo Makefile in `SKILL.md` (which ships into the user's
repo and must stand alone) — to the same answer on five repo shapes, including
`GOWORK=off`, which is where they had silently diverged.

`DuplicatedCapabilityTests` asserts that every copy of a multi-copy recipe still
contains the construct that decides pass/fail.

## Coverage Summary

| Metric | Count |
|--------|-------|
| Total golden fixtures | 16 (12 TP defects + 4 FP) |
| Contract tests (`test_skill_contract.py`) | 56 |
| Golden-review tests (`test_golden_reviews.py`) | 24 |
| Executable-asset tests (`test_executable_assets.py`) | 32 |
| Shipped-recipe contract tests (`test_shipped_recipes.py`) | 38 |
| **Total** | **150** |

These counts are checked against live discovery by
`test_skill_contract.py::TestCoverageCountsAreNotStale`, so a stale figure
fails the regression instead of quietly misreporting coverage.
| SKILL.md lines | 264 (budget: ≤ 400) |

Executable-asset tests run real `make` / `go` / `git` (skipped when a toolchain is
absent). Coverage:
- golden Makefiles execute (`help`, dry-run `build-*`, `test`);
- `discover_go_entrypoints.sh --modules` lists `go.work` `use` modules via the toolchain,
  the traditional multi-module repo with **no** `go.work` (scoped `go.mod` search, excludes
  vendor/testdata/examples), and parses `go.work` comments + quoted paths in the no-toolchain
  fallback;
- a real build injects and verifies **all three** `-X` vars (version/commit/buildTime) via a
  `--version` CLI; a fixed `SOURCE_DATE_EPOCH` gives a reproducible `buildTime`; and identical
  source at two different paths produces a **byte-identical** binary (proves `-trimpath`);
- `clean` spares hand-written docs; and `generate-check` (a) ignores unrelated pre-existing
  dirt, (b) **fails** when `make generate` errors (`set -e`), and (c) detects a content change
  to an already-dirty file (status+diff snapshot).

## Known Coverage Gaps

| Area | Gap | Priority |
|------|-----|----------|
| Missing `cover` target | No fixture for project without `cover` target | Low |
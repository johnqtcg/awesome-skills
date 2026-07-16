# Go-CI-Workflow Skill — Test Coverage Matrix

Counts below are re-derived from the suite, not hand-maintained. Re-run
`python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v` after any
change and update the table.

## Test Files and Counts

| File | Tests | What it validates |
|------|------:|-------------------|
| `test_skill_contract.py` | 60 | Frontmatter, SKILL.md structure, all reference-file contracts, action-version currency, run-regression fail-closed behaviour, discovery-script surface |
| `test_golden_scenarios.py` | 28 | 12 golden fixtures: rule-presence coverage + per-scenario behavioural field assertions |
| `test_golden_yaml.py` | 10 | Structural validation of the concrete workflow YAML in the golden references (+ actionlint when installed) |
| `test_discover_script.py` | 12 | `discover_ci_needs.sh` behaviour against real fixture repos |
| **Total** | **110** | 1 test (`test_actionlint_when_available`) skips when `actionlint` is not on PATH |

## What Each Layer Proves — and What It Does Not

The suite validates the skill's **authored artifacts** (SKILL.md, references, scripts). It is deterministic and offline. It does **not** run a model to generate a workflow from a scenario and then grade that output — see Known Gaps.

### `test_skill_contract.py` (60)

- `TestFrontmatter` — `name`/`description` present; **no unsupported frontmatter keys** (`disable-model-invocation` was removed so `quick_validate` passes and the runner can fail closed).
- `TestSkillMdStructure` — 350-line budget, 5 mandatory gates, 6 repository shapes, execution paths, security gate, output contract, cross-reference to `$go-makefile-writer`.
- `TestWorkflowQualityGuide` — 15 baseline sections **plus §16 Action Version & Supply-Chain Pinning** (both pinning tiers, Dependabot, `releases/latest` re-verify step) and `cache-dependency-path` guidance.
- `TestAdvancedPatterns` — 9 advanced sections (permissions, fork-PR, reusable/composite, service containers, timeouts).
- `TestRepositoryShapes` — 6 shapes; multi-module matrix sets `cache-dependency-path`; `go.work` workspace documented; path-filter job carries `pull-requests: read`; path-filter × **required-status-check** interaction documented (`ci-required` always-run aggregation job).
- `TestActionVersionCurrency` — the §16 policy table is the single source of truth; **every `uses:` pin in every reference must match it**, and a denylist guards against regressing to the stale majors the review flagged (`checkout@v4/5/6`, `setup-go@v4/5/6`, `paths-filter@v3`). SHA-pinned examples are exempt.
- `TestRunRegression` — runner is fail-closed (`set -euo pipefail`, no error-swallowing); actionlint absence is surfaced as a WARNING; a failing validator aborts with its exit code instead of printing success.
- `TestDiscoveryScript` — 8 categories; vendored/generated trees pruned; `go-workspace`, `toolchain`, and app-vs-library signals present.

### `test_golden_yaml.py` (10)

Extracts every ```yaml``` block from the three golden-example references and asserts: parses, has name+trigger+jobs, every job has `runs-on`+`timeout-minutes`, permissions declared, no `@latest`, no hardcoded Go version, and **matrix/subdir setup-go sets `cache-dependency-path`**. When `actionlint` is installed it additionally lints each complete workflow; otherwise that one test skips (the WARNING in `run_regression.sh` makes the skip visible).

### `test_golden_scenarios.py` (28) and `test_discover_script.py` (12)

Fixture rule-coverage + behavioural field assertions, and probe-script behaviour on real temp repos (vendored-module, workspace, toolchain, app/library, empty, bad-root).

## Coverage Summary

| Category | Total | Tested | Coverage |
|---------|-------|--------|----------|
| Mandatory gates | 5 | 5 | 100% |
| Repository shapes | 6 | 6 | 100% |
| Job types (core/docker/integration/e2e/vuln/static) | 6 | 6 | 100% |
| Trigger types (PR/push/schedule/workflow_call) | 4 | 4 | 100% |
| Execution paths (make/repo-task/inline) | 3 | 3 | 100% |
| WQG sections (incl. §16 pinning) | 16 | 16 | 100% |
| Advanced pattern sections | 9 | 9 | 100% |
| Golden fixtures | 12 | 12 | 100% |
| Golden example workflows (structural) | 5 | 5 | 100% |
| Discover-script categories | 8 | 8 | 100% |

## Known Gaps

| Gap | Priority | Notes |
|-----|----------|-------|
| No model-in-the-loop generation eval | Medium | The suite grades authored artifacts, not freshly generated workflows. End-to-end "generate then validate" belongs in the eval-harness, not this offline unit suite. Do not read "100% covered" as "generation quality guaranteed". |
| actionlint is optional, not required | Medium | When `actionlint` is absent, Actions expression/context/shell semantics are unverified. The run is honest about this (WARNING + qualified success line), but CI that wants real semantic validation must install actionlint. |
| Action versions are point-in-time | Low | Pins verified 2026-07-16. `TestActionVersionCurrency` keeps examples internally consistent with §16, but neither the test nor the skill can detect that upstream shipped a newer major — re-verify at generation time. |
| discover script is a probe, not a classifier | Low | app-vs-library is a heuristic; Taskfile/mage task bodies, CGO, codegen, private modules, and cross-platform needs are not inferred. The skill body requires manual confirmation. |
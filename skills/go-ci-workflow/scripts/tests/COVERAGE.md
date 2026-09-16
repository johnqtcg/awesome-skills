# Go-CI-Workflow Skill — Test Coverage Matrix

Counts below are re-derived from the suite, not hand-maintained. Re-run
`python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v` after any
change and update the table.

## Test Files and Counts

| File | Tests | What it validates |
|------|------:|-------------------|
| `test_skill_contract.py` | 68 | Frontmatter, SKILL.md structure, per-gate body content, all reference-file contracts, action-version currency, tool-version currency, cross-reference integrity, run-regression fail-closed behaviour, discovery-script surface |
| `test_golden_yaml.py` | 18 | Structural + semantic validation of **every** YAML block in **every** reference (+ actionlint when installed) |
| `test_discover_script.py` | 14 | `discover_ci_needs.sh` behaviour against real fixture repos |
| `test_golden_scenarios.py` | 12 | 12 golden fixtures, each bound to the SKILL.md section and the scenario-scoped references that must honour it |
| **Total** | **112** | 1 test (`test_actionlint_when_available`) skips when `actionlint` is not on PATH |

## Discriminating Power — Measured, Not Claimed

A test count is not a guarantee. The suite is graded by mutation: inject a
defect, confirm the suite goes red.

| | Semantic mutations | Undetected | Fail-open rate |
|---|---:|---:|---:|
| Before hardening | 25 | 13 | **52%** |
| Now | 25 | 1 | **4%** |

Mutations now caught that previously passed silently: a secret handed to an
unguarded `pull_request` job; an inverted fork guard (in either the YAML or the
golden example); `contents: read` → `write` at job or workflow level;
`cancel-in-progress` ungated or set to `false`; a deleted `concurrency` block;
a deleted Local Parity Gate or Degraded Output Gate body; a stale action major
or tool pin, in YAML or in prose; an unattributed `@vN`; an invalid runner
label, permission scope, or Go version; a broken `.md` cross-reference;
`-maxdepth`/pruning regressions in the discovery probe.

Deliberately **not** caught: renaming a gate heading's style (`### 4)` →
`####`). The suite matches gate *names*, which are a real contract the golden
fixtures key on, but no longer pins the heading prefix — an earlier version
broke on harmless restyling while ignoring two empty gate bodies.

## What Each Layer Proves — and What It Does Not

The suite validates the skill's **authored artifacts** (SKILL.md, references,
scripts). It is deterministic and offline. It does **not** run a model to
generate a workflow from a scenario and then grade that output — see Known Gaps.

### `test_skill_contract.py` (68)

- `TestFrontmatter` — `name`/`description` present; no unsupported frontmatter keys.
- `TestSkillMdStructure` — 350-line budget, 5 mandatory gates (matched by name,
  not heading style), **per-gate body assertions scoped to each gate's own
  section**, 6 repository shapes, execution paths, output contract,
  cross-reference to `$go-makefile-writer`.
- `TestWorkflowQualityGuide` — 15 baseline sections, §16 action pinning (both
  tiers, Dependabot, re-verify step), §11 tool-pin table with its own re-verify
  instruction, `cache-dependency-path` guidance.
- `TestAdvancedPatterns` — 9 advanced sections.
- `TestRepositoryShapes` — 6 shapes; multi-module matrix sets
  `cache-dependency-path`; `go.work` documented; path-filter job carries
  `pull-requests: read`; path-filter × required-status-check interaction.
- `TestActionVersionCurrency` — §16 is the single source of truth; every
  `uses:` pin must match it; denylist against known-stale majors.
- `TestToolVersionCurrency` — §11 is the single source of truth for `go install`
  pins. Checks the install paths, the versions, prose mentions of a tool
  version, and rejects any `@vN` written without naming its action.
- `TestCrossReferences` — every `` `*.md` `` pointer resolves; every shipped
  reference is named by SKILL.md.
- `TestRunRegression` — runner is fail-closed; a failing validator aborts with
  its exit code (verified by executing the runner with an injected failure).
- `TestDiscoveryScript` — 8 categories; pruning, `go-workspace`, `toolchain`,
  app-vs-library signals present in the script source.

### `test_golden_yaml.py` (18)

Extracts every ```yaml``` block from **every** `references/*.md` and classifies
it before applying rules (complete workflow = `jobs:` **and** a trigger;
otherwise a fragment). Asserts: parses; workflow has name + trigger + jobs;
every job has `runs-on` + numeric `timeout-minutes`; runner labels are real;
permissions declared, scopes valid, `contents: write` absent; `cancel-in-progress`
event-gated everywhere; `pull_request` workflows declare `concurrency`; fork
guards are `==` not `!=`, read from the **parsed** `if:`; secrets on a
`pull_request` workflow are fork-guarded; no `@latest`; no hardcoded Go version
outside a matrix; declared Go versions are plausible; matrix/subdir setup-go
sets `cache-dependency-path`. With `actionlint` installed it additionally lints
each complete workflow.

`workflow_call` workflows are exempt from the `name` and `permissions` rules —
they inherit both from the caller.

### `test_discover_script.py` (14)

Executes the probe against real temp repos: Makefile without ci targets, no
`scripts/` dir, go.mod-only, empty, bad root, vendored modules, dependency
trees across **all** probes, monorepo Dockerfiles below depth 2, `go.work`,
`toolchain`, app/library heuristic, rich repo firing every category, TSV shape.

### `test_golden_scenarios.py` (12)

Every assertion binds a fixture field to the skill text that must honour it:
declared shapes/gates/execution paths/output fields must exist in the SKILL.md
section that owns them, and parity levels must sit on the fallback ladder.
`skill_rules_that_must_fire` is searched only in SKILL.md plus the references
that scenario's `load_references` declares — so a rule living in a file the
skill would not open for that scenario is a visible gap, not a silent pass.
A guard also rejects a fixture that declares conditional references but whose
rules are all satisfiable by SKILL.md alone (it would be testing nothing).

## Coverage Summary

| Category | Total | Tested | Coverage |
|---------|-------|--------|----------|
| Mandatory gates (heading **and** body) | 5 | 5 | 100% |
| Repository shapes | 6 | 6 | 100% |
| Job types (core/docker/integration/e2e/vuln/static) | 6 | 6 | 100% |
| Trigger types (PR/push/schedule/workflow_call) | 4 | 4 | 100% |
| Execution paths (make/repo-task/inline) | 3 | 3 | 100% |
| WQG sections (incl. §11 tool pins, §16 action pins) | 16 | 16 | 100% |
| Advanced pattern sections | 9 | 9 | 100% |
| Golden fixtures (scenario-scoped) | 12 | 12 | 100% |
| Reference files with YAML validated | 6 | 6 | 100% |
| YAML blocks parsed | 44 | 44 | 100% |
| Discover-script categories | 8 | 8 | 100% |

## Known Gaps

| Gap | Priority | Notes |
|-----|----------|-------|
| Prose semantics can still be inverted | Medium | The one mutation that survives: rewriting a guidance sentence to say the opposite ("monorepo — never use path filters") while keeping its keywords. No offline assertion catches this without a brittle phrase-matcher; it is a code-review responsibility. |
| No model-in-the-loop generation eval | Medium | The suite grades authored artifacts, not freshly generated workflows. Do not read "100% covered" as "generation quality guaranteed". |
| actionlint is optional, not required | Medium | Without it, `${{ }}` expression and context semantics are unverified. The run is honest about this (WARNING + qualified success line), but CI that wants real semantic validation must install actionlint. |
| Versions are point-in-time | Low | Action majors verified 2026-07-16; tool pins verified 2026-09-16. The currency tests keep examples internally consistent with §11/§16 but cannot detect that upstream shipped a newer release — re-verify at generation time. |
| discover script is a probe, not a classifier | Low | app-vs-library is a heuristic; Taskfile/mage task bodies, CGO, codegen, private modules and cross-platform needs are not inferred; Dockerfiles are found only 4 levels deep; only the documented PRUNE list is excluded. All limits are declared in the script's own LIMITS block, and SKILL.md requires manual confirmation. |

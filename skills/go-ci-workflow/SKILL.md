---
name: go-ci-workflow
description: Use when creating or refactoring GitHub Actions CI workflows for Go repositories. Covers repository-shape detection, Make-driven delegation with formal fallbacks, Go setup, caching, tool pinning, permissions, reusable workflows, and quality gate design.
---

# Go CI Workflow Writer

Design GitHub Actions CI workflows for Go repositories that are fast, honest, and aligned with how the repository actually runs locally.

## Use This Skill For

- creating or refactoring `.github/workflows/*.yml` for Go repositories
- reviewing CI workflow PRs for job design, triggers, and safety
- mapping repository structure to CI jobs
- aligning GitHub Actions with Makefile targets or other local task entrypoints
- improving CI job separation, caching, tool pinning, and gate design

Do not use this skill for:

- release or deploy pipelines unless the request explicitly includes them
- non-GitHub CI systems
- pretending a repository has local parity when it does not

## Execution Priority

Use the strongest repo-native execution path available:

1. Prefer Makefile targets such as `ci`, `ci-e2e`, `ci-api-integration`, `docker-build`.
2. Fall back to other committed task runners or scripts when Makefile targets do not exist:
   - `Taskfile.yml`
   - `mage`
   - `scripts/*.sh`
   - repo-specific wrapper commands
3. Use controlled inline workflow commands only when the repository has no stable task entrypoint.

When falling back, say so explicitly and recommend the missing local entrypoint needed for parity.

## Load References Selectively

Always load:
- `references/workflow-quality-guide.md` — baseline job templates and patterns.
- `references/golden-examples.md` — annotated workflow YAML for standard service and no-Makefile fallback.

Load on condition:
- `references/repository-shapes.md` — **only when** multiple `go.mod` files detected, or repo has multi-app directories.
- `references/github-actions-advanced-patterns.md` — **only when** request involves `permissions` escalation, fork PR security, reusable workflows, service containers, or self-hosted runners.
- `references/fallback-and-scaffolding.md` — **only when** Makefile targets or repo-native entrypoints are incomplete or missing.
- `references/golden-example-monorepo.md` — **only when** repository shape is monorepo.
- `references/golden-example-service-containers.md` — **only when** integration tests require database or cache service containers.
- `references/pr-checklist.md` — **only when** reviewing an existing workflow PR.

## Operating Model

1. Inspect repository shape and task entrypoints.
2. Decide the honest workflow architecture.
3. Compose workflow YAML with repo-appropriate jobs and safety defaults.
4. Validate syntax, references, and trigger semantics.
5. Report assumptions, fallbacks, and unresolved gaps explicitly.

## Mandatory Gates

### 1) Repository Shape Gate

Before composing a workflow, classify the repository:

- single-module application
- single-module library
- multi-module repository
- monorepo with multiple apps/packages
- Docker-heavy repository
- reusable-workflow candidate

Inspect:

- `go.mod` and nested `go.mod` files
- root and nested `Makefile` / `Taskfile.yml` / `mage` / scripts
- existing `.github/workflows/*.yml`
- Dockerfiles and major app directories
- test layout for unit, integration, and e2e

Use `scripts/discover_ci_needs.sh` first, then confirm with manual inspection where needed.

### 2) Local Parity Gate

Do not claim local parity unless each workflow job maps to a real local entrypoint.

For each job, classify the execution path:

- `make target`
- `repo task`
- `inline fallback`

If a target or entrypoint is missing:

- mark it explicitly
- choose either honest scaffolding or a controlled inline fallback
- recommend the repo-native target that should exist later

### 3) Security and Permissions Gate

Before adding secrets, write permissions, or publish-like jobs, determine:

- whether the workflow runs on `pull_request`, `push`, `workflow_call`, or `schedule`
- whether fork PRs can reach secrets
- the minimum required `permissions`
- whether reusable workflows or self-hosted runners change the trust boundary

Read `references/github-actions-advanced-patterns.md` whenever security or advanced workflow behavior is involved.

### 4) Execution Integrity Gate

Never claim validation happened unless it actually ran.

If syntax or contract validation was not run, output:

- `Not run in this environment`
- reason
- exact commands to run next

If validation did run, report:

- command used
- pass/fail result
- what was or was not verified

### 5) Degraded Output Gate

If the repository lacks sufficient structure for a high-confidence workflow:

- do not fabricate complete parity
- produce a scaffold that is explicit about fallback paths
- list missing targets, missing scripts, and recommended follow-up changes

Use `references/fallback-and-scaffolding.md`.

## Job Architecture Rules

- Keep a fast core gate separate from slow or environment-sensitive jobs.
- Default core gate:
  - formatting or lint gate
  - tests
  - build
  - coverage threshold when the repository uses one
- Split optional jobs when present:
  - Docker build verification
  - integration tests
  - e2e
  - vulnerability scanning
  - extra static analysis
- Set `timeout-minutes` on every job (10-15 for core gate, 20 for e2e/integration).
- Use `needs:` only when ordering matters.
- Use `concurrency` to cancel redundant runs on the same branch or PR.

## Trigger Rules

Default trigger intent:

- `pull_request`: fast core gate, low-risk verification, no secret-dependent jobs from forks
- `push` to protected branches: broader verification
- `schedule`: expensive or comprehensive sweeps
- `workflow_call`: reusable workflow extraction when multiple repos/jobs genuinely share behavior

Do not force all expensive jobs onto every PR unless the repository risk profile requires it.

## Go Setup and Tooling Rules

- Use `go-version-file: go.mod` — never hardcode Go version.
- Pin `go install` tool versions exactly, never `@latest`.
- Keep tool versions aligned with Makefile or repo-native install scripts when those exist.

## Advanced GitHub Actions Rules

Use `references/github-actions-advanced-patterns.md` when needed.

At minimum:

- set minimal `permissions` (prefer job-level over workflow-level for escalations)
- guard secret-dependent jobs for fork PRs with event and repo checks
- use matrices only when they add clear value
- prefer reusable workflows only when duplication is real and inputs/secrets are manageable
- prefer composite actions over reusable workflows for step-level sharing within one repo
- use service containers for integration tests that need databases or caches
- use path filters for monorepo selective job triggering
- distinguish GitHub-hosted vs self-hosted runner assumptions

## Validation Checklist

Validate as much as the environment allows:

- YAML shape reviewed
- every referenced target or script exists
- trigger logic matches intended cost and trust model
- secret-dependent jobs are not exposed to unsafe events
- tool versions are pinned
- cache and concurrency are configured intentionally

If available, run:

```bash
actionlint
yq eval . .github/workflows/ci.yml
bash scripts/discover_ci_needs.sh
```

## Output Contract

When generating or refactoring a workflow, always return:

- changed files
- repository shape classification
- job list and execution path for each job (`make target`, `repo task`, or `inline fallback`)
- trigger configuration
- permissions and secret assumptions
- tool versions used
- missing targets or missing local entrypoints
- validation performed
- recommended follow-up work when parity is incomplete

## Resources

- Use `scripts/discover_ci_needs.sh` to inspect repository shape and CI needs.
- See "Load References Selectively" above for when to load each reference file.
- Cross-reference `$go-makefile-writer` when Makefile targets should be added or repaired.

## Skill Maintenance

Run regression before publishing changes:

```bash
scripts/run_regression.sh
```

# CI Workflow PR Checklist

Use this checklist for quick and reliable review of GitHub Actions CI workflow PRs.

## 1) Scope and Intent
- PR description states what jobs changed and why.
- New/removed/renamed jobs are explicitly listed.
- Breaking changes (removed triggers, changed conditions) are called out.

## 2) Trigger Configuration
- `push` branches include `main` (and other protected branches if applicable).
- `pull_request` triggers core gate jobs.
- `schedule` cron syntax is valid and uses UTC.
- `concurrency` group is set to cancel redundant runs.

## 3) Go Setup
- `go-version-file: go.mod` used (NOT hardcoded version).
- `cache: true` enabled in `actions/setup-go`.
- Each job sets up Go independently (no shared state assumption).

## 4) Make Parity
- Every CI job delegates to a `make` target.
- If inline fallback exists, it is explicitly labeled as fallback.
- Corresponding `make ci-*` targets exist in Makefile for local parity.
- Configuration overrides (e.g., `COVER_MIN`) passed as Make variables.

## 5) Tool Management
- All `go install` commands use exact pinned versions (no `@latest`).
- Tool versions match between CI workflow and Makefile `install-tools`.
- Tools are installed only in the jobs that need them.

## 6) Job Architecture
- Core gate job is fast and comprehensive (fmt + test + lint + cover + build).
- Expensive jobs (e2e, integration) are separate from core gate.
- Conditional execution (`if:`) used for expensive/optional jobs.
- Jobs are independent unless explicitly linked with `needs:`.

## 7) Secret and Security
- Secrets use `${{ secrets.* }}` (never hardcoded).
- Secret-dependent jobs gated against fork PRs.
- No sensitive data in job logs.
- `actions/*` pinned to major version tags (e.g., `@v4`, `@v5`).
- `permissions` minimized for the workflow or job.

## 8) Caching and Performance
- Go module cache enabled via `actions/setup-go`.
- Custom cache dirs (GOCACHE, lint cache) configured if needed.
- `concurrency` group prevents redundant runs.
- Reasonable `timeout-minutes` set for each job.

## 9) Validation Evidence
Minimum evidence:
- YAML is syntactically valid.
- All referenced `make` targets exist.
- Tool versions are pinned and match Makefile.
- Fallback-based jobs are labeled and justified.

Recommended evidence:
- Workflow run passes on a test branch.
- Conditional jobs trigger correctly.
- Cache is effective (visible in logs).

## 10) Review Output Standard
- Findings are prioritized (High → Medium → Low).
- Each finding has: `location + impact + evidence + recommendation`.
- If no issues: explicitly state "No actionable findings found" and list residual risks.

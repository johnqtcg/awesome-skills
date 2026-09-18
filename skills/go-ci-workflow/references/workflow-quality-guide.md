# Go CI Workflow Quality Guide

## Table of Contents

1. [Job Set](#1-job-set)
2. [Trigger Strategy](#2-trigger-strategy)
3. [Go Setup Pattern](#3-go-setup-pattern)
4. [Core Gate Job](#4-core-gate-job)
5. [Docker Build Job](#5-docker-build-job)
6. [Integration Test Job](#6-integration-test-job)
7. [E2E Test Job](#7-e2e-test-job)
8. [Vulnerability Scanning Job](#8-vulnerability-scanning-job)
9. [Static Analysis Extras](#9-static-analysis-extras)
10. [Caching Strategy](#10-caching-strategy)
11. [Tool Installation](#11-tool-installation)
12. [Secret Management](#12-secret-management)
13. [Matrix Strategy](#13-matrix-strategy)
14. [Robustness and Anti-Pattern Rules](#14-robustness-and-anti-pattern-rules)
15. [Validation Checklist](#15-validation-checklist)
16. [Action Version & Supply-Chain Pinning](#16-action-version--supply-chain-pinning)

## 1. Job Set

Recommended baseline:
- `ci` — core gate (format-check + test + lint + cover-check + build)
- `docker-build` — container image verification (when Dockerfile present)

Optional high-value additions:
- `api-integration` — API/service integration tests
- `e2e` — end-to-end journey tests (conditional: push/schedule)
- `govulncheck` — dependency vulnerability scanning
- `fieldalignment` — struct field alignment check
- `release` — automated release (tags only)

When the repository is a monorepo or multi-module repo, adapt the job set rather than forcing a single root job. See `repository-shapes.md`.

## 2. Trigger Strategy

```yaml
on:
  push:
    branches: [main]
  pull_request:
  schedule:
    - cron: '0 3 * * *'  # Nightly at 03:00 UTC
```

Guidelines:
- `push` to main: run all jobs.
- `pull_request`: run core gate + docker-build. Skip expensive jobs (e2e) unless critical.
- `schedule`: nightly comprehensive sweep (govulncheck, e2e, full suite).
- Tag-based triggers (`on: push: tags: ['v*']`) for release jobs only.

Add concurrency control to cancel redundant PR runs:

```yaml
concurrency:
  # per-PR group; per-commit on push so main runs never cancel each other
  group: ${{ github.workflow }}-${{ github.head_ref || github.sha }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

For secret-dependent jobs, also consider event trust boundaries and `permissions`. See `github-actions-advanced-patterns.md`.

## 3. Go Setup Pattern

Always use `go-version-file` to read Go version from `go.mod`:

```yaml
- name: Set up Go
  uses: actions/setup-go@v7
  with:
    go-version-file: go.mod
    cache: true
```

Never hardcode Go version in the workflow. The `go.mod` file is the single source of truth.
For multi-module repositories, be explicit about which `go.mod` governs each job.

**Cache key correctness — `cache-dependency-path`.** *Behaviour verified against `actions/setup-go@v7.0.0` source on 2026-09-17. Like the version tables in §11 and §16, re-verify before relying on it — this default changed in v6.3.0.*

With `cache: true` and no `cache-dependency-path`, `setup-go` hashes **`go.mod`** — not `go.sum` — and finds it with a **non-recursive listing of `GITHUB_WORKSPACE`**, i.e. the repository root only. A step-level or job-level `working-directory` does not move where it looks. Two consequences:

- **No `go.mod` at the repo root and the step fails outright**, it does not silently miss: `Dependencies file is not found in <workspace>. Supported file pattern: go.mod`. Sub-directory modules, matrices over modules, and `go.work` repos with no root module all hit this.
- **The default key tracks `go.mod` only.** A dependency change that touches just `go.sum` produces the same key, so the newly required modules are downloaded on every run and never make it into the saved cache — a silent, permanent partial cache miss.

Set `cache-dependency-path` whenever the module is not at the root, or whenever you want the key to track `go.sum`. Its value goes straight to `hashFiles()`, so globs and multi-line lists work; if it resolves to no file the step fails with `Some specified paths were not resolved, unable to cache dependencies.`

```yaml
# Module in a subdirectory (e.g. matrix over modules)
- uses: actions/setup-go@v7
  with:
    go-version-file: ${{ matrix.module }}/go.mod
    cache: true
    cache-dependency-path: ${{ matrix.module }}/go.sum

# go.work workspace — hash every module's go.sum so the key changes when any moves
- uses: actions/setup-go@v7
  with:
    go-version-file: go.mod
    cache: true
    cache-dependency-path: |
      go.work.sum
      **/go.sum
```

## 4. Core Gate Job

The primary quality gate. Must be fast and comprehensive:

```yaml
ci:
  name: Format · Test · Lint · Build
  runs-on: ubuntu-latest
  timeout-minutes: 15
  steps:
    - uses: actions/checkout@v7

    - name: Set up Go
      uses: actions/setup-go@v7
      with:
        go-version-file: go.mod
        cache: true

    - name: Install golangci-lint
      run: go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@v2.13.2

    - name: Run CI gate
      run: make ci COVER_MIN=80
```

Key principles:
- Install only the tools this job needs.
- Delegate to `make ci` which combines fmt-check + test + lint + cover-check + build.
- Pass configuration overrides (like `COVER_MIN`) as Make variables.
- If the repository does not have `make ci`, either use another committed task entrypoint or mark the job as fallback.

### Non-Make task runners (the `repo task` execution path)

Make is the default, not a requirement. When the repository already standardises
on another committed runner, delegate to **that** — mirroring the repo beats
importing a Makefile it does not have. This is the `repo task` path in the
Output Contract; classify the job as `repo task`, not `make target`.

The runner binary is a pinned tool like any other, so install it with the same
exact-version rule as §11:

```yaml
    # Taskfile.yml — go-task/task
    - name: Install task
      run: go install github.com/go-task/task/v3/cmd/task@v3.53.1
    - name: Run CI gate
      run: task ci

    # magefile.go — magefile/mage
    - name: Install mage
      run: go install github.com/magefile/mage@v1.17.2
    - name: Run CI gate
      run: mage ci

    # committed shell entrypoint
    - name: Run CI gate
      run: ./scripts/ci.sh
```

Re-verify these tool versions at generation time exactly as §16 requires for
actions — they rot the same way. A committed `scripts/ci.sh` needs no install
step, which makes it the cheapest parity entrypoint for a repo that has neither
Make nor a task runner.

Only after none of these exist does the job become an `inline fallback` — see
`fallback-and-scaffolding.md`.

## 5. Docker Build Job

Verifies the container image builds successfully without pushing:

```yaml
docker-build:
  name: Docker Image Build
  runs-on: ubuntu-latest
  timeout-minutes: 10
  steps:
    - uses: actions/checkout@v7

    - name: Build image
      run: make docker-build
```

For multi-app Dockerfiles with build args:

```yaml
    - name: Build web image (default APP)
      run: make docker-build

    - name: Build CLI image
      run: docker build -f Dockerfile --build-arg APP=mycli -t myapp:cli-ci .
```

## 6. Integration Test Job

For API and service-to-service integration tests:

```yaml
api-integration:
  name: API Integration
  runs-on: ubuntu-latest
  timeout-minutes: 20
  steps:
    - uses: actions/checkout@v7

    - name: Set up Go
      uses: actions/setup-go@v7
      with:
        go-version-file: go.mod
        cache: true

    - name: Run API integration tests
      run: make ci-api-integration
```

Integration tests should be:
- Opt-in via environment variable (e.g., `MYAPP_API_INTEGRATION=1`).
- In a separate `tests/integration/` directory.
- Controlled by a dedicated `make ci-api-integration` target.

## 7. E2E Test Job

End-to-end tests are expensive. Run conditionally:

```yaml
e2e:
  name: E2E Journey
  runs-on: ubuntu-latest
  timeout-minutes: 30
  if: github.event_name == 'push' || github.event_name == 'schedule'
  steps:
    - uses: actions/checkout@v7

    - name: Set up Go
      uses: actions/setup-go@v7
      with:
        go-version-file: go.mod
        cache: true

    - name: Run E2E tests
      run: make ci-e2e
```

Key principles:
- Use `if:` condition to skip on PRs (unless explicitly needed).
- E2E tests should have their own `make ci-e2e` target.
- Consider running E2E only on nightly schedule for maximum efficiency.
- For fork PRs, keep secret-dependent e2e off by default.

## 8. Vulnerability Scanning Job

```yaml
govulncheck:
  name: Dependency Vulnerability Check
  runs-on: ubuntu-latest
  timeout-minutes: 10
  steps:
    - uses: actions/checkout@v7

    - name: Set up Go
      uses: actions/setup-go@v7
      with:
        go-version-file: go.mod
        cache: true

    - name: Install govulncheck
      run: go install golang.org/x/vuln/cmd/govulncheck@v1.8.0

    - name: Run govulncheck
      run: govulncheck ./...
```

Always pin the `govulncheck` version. This job can run on every push or nightly only.

## 9. Static Analysis Extras

Optional jobs for additional quality checks:

```yaml
fieldalignment:
  name: Struct Field Alignment Check
  runs-on: ubuntu-latest
  timeout-minutes: 10
  steps:
    - uses: actions/checkout@v7

    - name: Set up Go
      uses: actions/setup-go@v7
      with:
        go-version-file: go.mod
        cache: true

    - name: Install fieldalignment
      run: go install golang.org/x/tools/go/analysis/passes/fieldalignment/cmd/fieldalignment@v0.50.0

    - name: Run fieldalignment
      run: $(go env GOPATH)/bin/fieldalignment ./...
```

Other useful extras:
- `gosec` standalone (if not covered by golangci-lint)
- `nilaway` for nil-safety analysis
- `deadcode` for unused code detection

## 10. Caching Strategy

`actions/setup-go@v7` handles Go module cache automatically when `cache: true` is set.

For additional cache control (custom GOCACHE, lint cache), pass via environment:

```yaml
- name: Run CI gate
  run: make ci
  env:
    GOCACHE: /tmp/gocache
    GOLANGCI_LINT_CACHE: /tmp/golangci-lint-cache
```

Define cache directories as Makefile variables so local and CI behavior matches:

```make
GOCACHE_DIR ?= /tmp/gocache
GOLANGCI_LINT_CACHE_DIR ?= /tmp/golangci-lint-cache
```

## 11. Tool Installation

Pin exact versions. Match between CI workflow and Makefile:

```yaml
# CI workflow
- name: Install golangci-lint v2
  run: go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@v2.13.2
```

```make
# Makefile (must match)
GOLANGCI_LINT_VERSION ?= v2.13.2
```

### Pinned tool versions used throughout this skill (single source of truth)

Same contract as §16 for actions: every `go install` in every example must use
the version in this table, and `TestToolVersionCurrency` fails if they drift.

| Tool | Install path | Pinned | Latest verified |
|------|--------------|--------|-----------------|
| golangci-lint | `github.com/golangci/golangci-lint/v2/cmd/golangci-lint` | `v2.13.2` | 2026-09-16 |
| govulncheck | `golang.org/x/vuln/cmd/govulncheck` | `v1.8.0` | 2026-09-16 |
| fieldalignment | `golang.org/x/tools/go/analysis/passes/fieldalignment/cmd/fieldalignment` | `v0.50.0` | 2026-09-16 |
| task | `github.com/go-task/task/v3/cmd/task` | `v3.53.1` | 2026-09-16 |
| mage | `github.com/magefile/mage` | `v1.17.2` | 2026-09-16 |

Rules:
- Every `go install` in CI must use an exact version tag — never `@latest`.
- Tool versions in CI must match the Makefile `install-tools` target.
- When upgrading a tool, update both CI and Makefile simultaneously.
- Prefer `go install` over `curl | sh` for Go tools.
- **Re-verify before generating**, exactly as §16 requires for actions — these
  rot on the same clock. The table records when it was last checked, not a
  guarantee that it is still current:
  ```bash
  gh api repos/golangci/golangci-lint/releases/latest --jq .tag_name
  gh api repos/golang/vuln/tags --jq '.[0].name'
  ```
  If the real latest is higher, prefer it and update the table and every example
  together.

## 12. Secret Management

For jobs that need secrets (deploy, push, API keys):

```yaml
- name: Run integration tests
  run: make ci-api-integration
  env:
    API_TOKEN: ${{ secrets.API_TOKEN }}
```

**The rule GitHub already enforces, stated plainly:** a `pull_request` run from a **fork** receives **no secrets at all** and a **read-only `GITHUB_TOKEN`**, and cannot write to the base branch's cache scope. A `pull_request` run from a **branch in the same repository** receives secrets normally. You do not need an `if:` to stop a fork from reading a secret — the platform does that.

What an `if:` is actually for: a fork PR that reaches a secret-dependent step gets an **empty** secret and fails somewhere confusing (a 401 from an API, a blank registry password). Guard to skip the job cleanly, not to plug a leak.

Rules:
- Never echo or log secrets.
- Use `${{ secrets.* }}` for all sensitive values.
- Guard secret-dependent jobs with the **fork check**, not the event check:
  `if: github.event.pull_request.head.repo.full_name == github.repository`.
  `if: github.event_name != 'pull_request'` is blunter than it looks — it also
  disables the job for same-repo PRs, where the secret is present and the job
  would have worked.
- **`pull_request_target` is the real exposure.** It runs in the *base* branch's
  context with full secrets and a writable token. Never combine it with a
  checkout of the PR head SHA: that executes fork-authored code with your
  secrets. See `github-actions-advanced-patterns.md` §2.
- Document required secrets in the workflow file as comments.

## 13. Matrix Strategy

For testing across multiple Go versions (libraries only):

### Supported Go majors (single source of truth)

Go's support policy covers the **two most recent majors** — an older major receives no security fixes, so a matrix pinned to one is testing an unsupported toolchain. Go ships a new major roughly every six months, which is faster than either the actions in §16 or the tools in §11, so this table rots first.

| Toolchain | Supported majors | Latest verified |
|-----------|------------------|-----------------|
| `go` | `1.26`, `1.27` | 2026-09-17 |

Every Go-version matrix in this skill uses these majors. When you bump this row, bump every example too — `scripts/tests/test_skill_contract.py::TestGoVersionCurrency` fails if they drift apart, and that failure is the reminder to re-verify.

**Re-verify before generating**, exactly as for §16 — do not trust the numbers above:

```bash
curl -s 'https://go.dev/dl/?mode=json' | grep -o '"version": *"go[0-9.]*"' | head -2
```

```yaml
ci:
  strategy:
    matrix:
      go-version: ['1.26', '1.27']
  runs-on: ubuntu-latest
  timeout-minutes: 15
  steps:
    - uses: actions/setup-go@v7
      with:
        go-version: ${{ matrix.go-version }}
```

Use matrix only when:
- Library projects that must support multiple Go versions.
- NOT for application projects (use `go-version-file: go.mod` instead).

## 14. Robustness and Anti-Pattern Rules

Robustness:
- All jobs must be independent unless explicitly linked with `needs:`.
- Each job checks out code and sets up Go independently.
- No shared state between jobs (use artifacts for passing data if needed).
- Set `timeout-minutes` on every job: 15 core gate, 10 docker build, 20 integration, 30 e2e (source of truth: `github-actions-advanced-patterns.md` §8).
- Use `continue-on-error: true` only for informational jobs (not gates).

Anti-patterns to avoid:
- Inline `go test`, `go build` commands instead of `make` targets.
- Hardcoded Go version (`go-version: '1.22'`) instead of `go-version-file: go.mod`.
- Tool installation with `@latest` in CI.
- All tests in a single job (slow, no parallelism).
- E2E tests running on every PR (expensive, flaky).
- Missing `concurrency` control (redundant runs waste resources).
- Secrets exposed to fork PRs.
- CI behavior that cannot be reproduced locally.
- Tool versions differing between CI and Makefile.
- Missing `cache: true` in Go setup.

## 15. Validation Checklist

Minimum:
- YAML syntax is valid (no tabs, correct indentation).
- Every `make` target referenced exists in Makefile.
- Tool versions match between CI and Makefile.
- `go-version-file: go.mod` used (not hardcoded).

Recommended:
- Run with `act` locally for dry-run verification.
- Push to a test branch and verify all jobs pass.
- Verify conditional jobs (`if:`) trigger correctly.
- Confirm cache is working (check "Post Set up Go" step logs).

## 16. Action Version & Supply-Chain Pinning

Third-party actions run with access to your repository token. Their versions move, and a "golden example" that hard-codes a version silently rots the moment upstream ships a new major. Treat the versions below as a **starting point that must be re-verified at generation time**, not as permanent truth.

### Pinned versions used throughout this skill (single source of truth)

| Action | Pinned major | Latest verified |
|--------|--------------|-----------------|
| `actions/checkout` | `v7` | 2026-07-16 |
| `actions/setup-go` | `v7` | 2026-07-16 |
| `dorny/paths-filter` | `v4` | 2026-07-16 |
| `actions/upload-artifact` | `v7` | 2026-07-16 |

Every YAML example in this skill uses these majors. When you bump a row here, bump every example too — `scripts/tests/test_skill_contract.py::TestActionVersionCurrency` fails if they drift apart, and that failure is the reminder to re-verify.

> `setup-go@v6+` reads the `toolchain` directive from `go.mod` and changed its cache-key behaviour; it also requires a reasonably recent runner. Do not pair a `v7` example with a pinned ancient runner image.

### Re-verify before generating

Newer majors ship often. Before writing a workflow, confirm the current release rather than trusting any embedded number:

```bash
# Latest release tag for an action (needs gh auth or a token)
gh api repos/actions/setup-go/releases/latest --jq .tag_name
gh api repos/actions/checkout/releases/latest --jq .tag_name
```

Or read the releases page (e.g. `https://github.com/actions/setup-go/releases`). If the latest major is higher than the table, prefer it and update the table + examples together.

### Two pinning tiers — pick by repository risk

- **Standard repositories — pin the major tag** (`actions/checkout@v7`). Simple, readable, and auto-receives patch/minor security fixes. This is what the examples use.
- **High-security / regulated repositories — pin the full 40-char commit SHA, with the human-readable version in a trailing comment.** A moved tag cannot then swap the code under you (tags are mutable; a SHA is not):

  ```yaml
  - uses: actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0 # v7.0.0
  - uses: actions/setup-go@b7ad1dad31e06c5925ef5d2fc7ad053ef454303e # v7.0.0
  ```

  Resolve the SHA for a tag with `gh api repos/actions/checkout/git/refs/tags/v7.0.0 --jq .object.sha` (dereference annotated tags to the commit). GitHub org/repo policy can *require* SHA pins for all actions — honour that setting when it is on.

### Keep pins fresh automatically

SHA pins are safe but freeze you on old code unless something bumps them. Commit a Dependabot config so upgrades arrive as reviewable PRs (Dependabot preserves the `# vX.Y.Z` comment when it rewrites the SHA):

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: github-actions
    directory: "/"
    schedule:
      interval: weekly
```

Renovate is an equivalent choice with finer-grained grouping. Either way, never let a SHA-pinned repo run for months with no update path — an unpatched action is its own supply-chain risk.

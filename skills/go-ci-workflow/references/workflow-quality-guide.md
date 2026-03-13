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
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

For secret-dependent jobs, also consider event trust boundaries and `permissions`. See `github-actions-advanced-patterns.md`.

## 3. Go Setup Pattern

Always use `go-version-file` to read Go version from `go.mod`:

```yaml
- name: Set up Go
  uses: actions/setup-go@v5
  with:
    go-version-file: go.mod
    cache: true
```

Never hardcode Go version in the workflow. The `go.mod` file is the single source of truth.
For multi-module repositories, be explicit about which `go.mod` governs each job.

## 4. Core Gate Job

The primary quality gate. Must be fast and comprehensive:

```yaml
ci:
  name: Format · Test · Lint · Build
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4

    - name: Set up Go
      uses: actions/setup-go@v5
      with:
        go-version-file: go.mod
        cache: true

    - name: Install golangci-lint
      run: go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@v2.6.2

    - name: Run CI gate
      run: make ci COVER_MIN=80
```

Key principles:
- Install only the tools this job needs.
- Delegate to `make ci` which combines fmt-check + test + lint + cover-check + build.
- Pass configuration overrides (like `COVER_MIN`) as Make variables.
- If the repository does not have `make ci`, either use another committed task entrypoint or mark the job as fallback.

## 5. Docker Build Job

Verifies the container image builds successfully without pushing:

```yaml
docker-build:
  name: Docker Image Build
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4

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
  steps:
    - uses: actions/checkout@v4

    - name: Set up Go
      uses: actions/setup-go@v5
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
  if: github.event_name == 'push' || github.event_name == 'schedule'
  steps:
    - uses: actions/checkout@v4

    - name: Set up Go
      uses: actions/setup-go@v5
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
  steps:
    - uses: actions/checkout@v4

    - name: Set up Go
      uses: actions/setup-go@v5
      with:
        go-version-file: go.mod
        cache: true

    - name: Install govulncheck
      run: go install golang.org/x/vuln/cmd/govulncheck@v1.1.4

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
  steps:
    - uses: actions/checkout@v4

    - name: Set up Go
      uses: actions/setup-go@v5
      with:
        go-version-file: go.mod
        cache: true

    - name: Install fieldalignment
      run: go install golang.org/x/tools/go/analysis/passes/fieldalignment/cmd/fieldalignment@v0.42.0

    - name: Run fieldalignment
      run: $(go env GOPATH)/bin/fieldalignment ./...
```

Other useful extras:
- `gosec` standalone (if not covered by golangci-lint)
- `nilaway` for nil-safety analysis
- `deadcode` for unused code detection

## 10. Caching Strategy

`actions/setup-go@v5` handles Go module cache automatically when `cache: true` is set.

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
  run: go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@v2.6.2
```

```make
# Makefile (must match)
GOLANGCI_LINT_VERSION ?= v2.6.2
```

Rules:
- Every `go install` in CI must use an exact version tag.
- Tool versions in CI must match the Makefile `install-tools` target.
- When upgrading a tool, update both CI and Makefile simultaneously.
- Prefer `go install` over `curl | sh` for Go tools.
- Versions in this guide are examples current at time of writing. Before generating a workflow, verify the latest stable release of each tool and use that version. When in doubt, check the tool's GitHub releases page.

## 12. Secret Management

For jobs that need secrets (deploy, push, API keys):

```yaml
- name: Run integration tests
  run: make ci-api-integration
  env:
    API_TOKEN: ${{ secrets.API_TOKEN }}
```

Rules:
- Never echo or log secrets.
- Use `${{ secrets.* }}` for all sensitive values.
- Gate secret-dependent jobs with `if: github.event_name != 'pull_request'` to prevent exposure on fork PRs.
- Document required secrets in the workflow file as comments.

## 13. Matrix Strategy

For testing across multiple Go versions (libraries only):

```yaml
ci:
  strategy:
    matrix:
      go-version: ['1.22', '1.23']
  runs-on: ubuntu-latest
  steps:
    - uses: actions/setup-go@v5
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
- Set `timeout-minutes` on every job: 10-15 for core gate, 20 for e2e/integration.
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

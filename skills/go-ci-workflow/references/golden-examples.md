# Golden Examples

Use these as shape references for final output. Each example includes full context, job architecture, and annotated workflow YAML.

## Table of Contents

1. [Standard Service Repository (Full Parity)](#1-standard-service-repository-full-parity)
2. [No Makefile Fallback (Scaffold)](#2-no-makefile-fallback-scaffold)

Additional examples (load only when needed):
- `golden-example-monorepo.md` — monorepo with multiple modules and matrix jobs
- `golden-example-service-containers.md` — service with MySQL/Redis integration tests

## 1) Standard Service Repository (Full Parity)

- **Repository shape**: single-module service
- **Execution path**: all jobs via `make` targets (full parity)
- **Jobs**:
  - `ci` via `make ci COVER_MIN=80`
  - `docker-build` via `make docker-build`
  - `govulncheck` via pinned tool install
- **Trigger config**: PR core gate, push broad gate, nightly vuln scan
- **Local parity**: full
- **Assumptions**: Makefile has `ci` and `docker-build` targets; `golangci-lint` version matches between CI and Makefile

### Complete Workflow

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
  schedule:
    - cron: '0 3 * * 1'  # Weekly Monday 03:00 UTC

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  ci:
    name: Format · Test · Lint · Build
    runs-on: ubuntu-latest
    timeout-minutes: 15
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

  docker-build:
    name: Docker Image Build
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4

      - name: Build image
        run: make docker-build

  govulncheck:
    name: Dependency Vulnerability Check
    runs-on: ubuntu-latest
    if: github.event_name == 'push' || github.event_name == 'schedule'
    timeout-minutes: 10
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

### Output Summary

| Field | Value |
|-------|-------|
| Repository shape | single-module service |
| Jobs | ci, docker-build, govulncheck |
| ci execution path | `make target` → `make ci COVER_MIN=80` |
| docker-build execution path | `make target` → `make docker-build` |
| govulncheck execution path | `inline` (tool not managed by Makefile) |
| Trigger | PR: ci + docker-build; push: all; schedule: govulncheck |
| Permissions | `contents: read` |
| Tool versions | golangci-lint v2.6.2, govulncheck v1.1.4 |
| Missing targets | none |
| Validation | YAML reviewed, make targets verified |

---

## 2) No Makefile Fallback (Scaffold)

- **Repository shape**: single-module library
- **Execution path**: inline fallback (no Makefile, no task runner)
- **Local parity**: partial — not full
- **Follow-up**: add `make ci`, move tool install versions into committed entrypoint

### Complete Workflow

```yaml
# FALLBACK WORKFLOW — no Makefile or task runner detected.
# Local parity: PARTIAL. Recommend adding `make ci` for full parity.
name: CI

on:
  push:
    branches: [main]
  pull_request:

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  ci:
    name: Format · Test · Lint · Build
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4

      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version-file: go.mod
          cache: true

      - name: Install golangci-lint
        run: go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@v2.6.2

      # INLINE FALLBACK — no make target available
      - name: Check formatting
        run: test -z "$(gofmt -l .)"

      # INLINE FALLBACK
      - name: Run tests
        run: go test -race -coverprofile=coverage.out ./...

      # INLINE FALLBACK
      - name: Lint
        run: golangci-lint run ./...

      # INLINE FALLBACK
      - name: Build
        run: go build ./...
```

### Output Summary

| Field | Value |
|-------|-------|
| Repository shape | single-module library |
| Jobs | ci |
| ci execution path | `inline fallback` — no make target |
| Trigger | PR + push to main |
| Permissions | `contents: read` |
| Local parity | partial |
| Missing targets | `make ci`, `make lint`, `make test` |
| Recommended follow-up | add root `Makefile` with `ci` target; move golangci-lint version into `install-tools` target |

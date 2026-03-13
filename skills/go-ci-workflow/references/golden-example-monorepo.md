# Golden Example — Monorepo With Multiple Modules

Load this file only when the repository is a monorepo or multi-module project.

- **Repository shape**: monorepo
- **Execution path**: mixed root `make` target + per-module matrix
- **Jobs**:
  - `lint` via root `make lint`
  - `test` via matrix over module paths
  - `docker-build` via per-app `make docker-build`
- **Follow-up**: extract reusable workflow only if another repo needs the same matrix

## Complete Workflow

```yaml
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
  lint:
    name: Lint (root)
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4

      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version-file: go.mod
          cache: true

      - name: Install golangci-lint
        run: go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@v2.6.2

      - name: Run lint
        run: make lint

  test:
    name: Test (${{ matrix.module }})
    runs-on: ubuntu-latest
    timeout-minutes: 15
    strategy:
      fail-fast: false
      matrix:
        module: [services/api, services/worker]
    steps:
      - uses: actions/checkout@v4

      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version-file: ${{ matrix.module }}/go.mod
          cache: true

      - name: Run tests
        working-directory: ${{ matrix.module }}
        run: make ci

  docker-build:
    name: Docker (${{ matrix.app }})
    runs-on: ubuntu-latest
    timeout-minutes: 10
    strategy:
      matrix:
        app: [api, worker]
    steps:
      - uses: actions/checkout@v4

      - name: Build image
        run: make docker-build APP=${{ matrix.app }}
```

## Output Summary

| Field | Value |
|-------|-------|
| Repository shape | monorepo with multiple apps |
| Jobs | lint, test (matrix), docker-build (matrix) |
| lint execution path | `make target` → `make lint` |
| test execution path | `make target` → per-module `make ci` |
| docker-build execution path | `make target` → `make docker-build APP=<app>` |
| Trigger | PR + push to main |
| Permissions | `contents: read` |
| Missing targets | none |
| Follow-up | extract reusable workflow only if duplication is real |

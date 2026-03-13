# Repository Shapes

Use this file to choose workflow architecture based on repository structure.

## 1) Single-Module Service

Default pattern:

- one core `ci` job
- optional `docker-build`
- optional integration/e2e jobs

Prefer root `Makefile` targets if present.

## 2) Single-Module Library

Prioritize:

- fast test and lint gate
- coverage threshold if the repo uses one
- avoid Docker jobs unless the library actually ships an image

Consider matrix strategy when the library intentionally supports multiple Go versions:

```yaml
strategy:
  matrix:
    go-version: ['1.22', '1.23']
```

Use matrix only for library projects. Application projects should use `go-version-file: go.mod`.

## 3) Multi-Module Repository

Detect nested `go.mod` files. When a repository contains nested go.mod paths beyond the root, it is a multi-module repository.

Use one of:

- top-level orchestrator target that runs all modules
- matrix over module paths when modules are independent

```yaml
strategy:
  fail-fast: false
  matrix:
    module: [pkg/client, pkg/server, tools/codegen]
steps:
  - uses: actions/setup-go@v5
    with:
      go-version-file: ${{ matrix.module }}/go.mod
      cache: true
  - name: Test
    working-directory: ${{ matrix.module }}
    run: make ci
```

Do not assume root `go.mod` is enough when nested modules exist. Be explicit about which `go.mod` governs each job.

When a root Makefile orchestrator exists (e.g., `make ci-all`), prefer it over matrix for simpler repos with 2-3 modules.

## 4) Monorepo

Detect:

- multiple apps or services
- multiple task entrypoints
- partial CI ownership across directories

Patterns:

- one main workflow with multiple jobs for moderate monorepos
- reusable workflow or matrix extraction when duplication is real
- path filter for selective job triggering

Be explicit about which apps or packages each job covers.

### Path Filter Pattern

Use path filters to avoid running all jobs when only one service changed. Two approaches:

**Approach A: Native `paths` trigger filter**

```yaml
on:
  pull_request:
    paths:
      - 'services/api/**'
      - 'pkg/shared/**'
      - 'go.mod'
      - 'go.sum'
```

Limitations: native `paths` applies to the entire workflow, not per-job. Use only when the workflow is already scoped to one service.

**Approach B: Per-job path detection with dorny/paths-filter**

```yaml
jobs:
  changes:
    name: Detect changes
    runs-on: ubuntu-latest
    outputs:
      api: ${{ steps.filter.outputs.api }}
      worker: ${{ steps.filter.outputs.worker }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            api:
              - 'services/api/**'
              - 'pkg/shared/**'
            worker:
              - 'services/worker/**'
              - 'pkg/shared/**'

  ci-api:
    needs: changes
    if: needs.changes.outputs.api == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Test API
        run: make ci-api

  ci-worker:
    needs: changes
    if: needs.changes.outputs.worker == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Test Worker
        run: make ci-worker
```

Always include shared package paths (`pkg/shared/**`, `go.mod`, `go.sum`) in filters that depend on them.

Path filters only when the repo already uses them safely. Do not introduce path filters for repos that have not adopted this pattern yet without explicit justification.

### Monorepo Job Separation

For moderate monorepos (2-4 services), prefer explicit jobs over matrix:

- explicit jobs are easier to debug and have clearer status checks
- matrix is better when >4 services have truly identical CI steps

## 5) Docker-Heavy Repository

If multiple Dockerfiles or build args exist:

- model image verification as separate jobs
- avoid coupling all image builds into the fast core gate unless required

For multi-app Docker builds:

```yaml
docker-build:
  strategy:
    matrix:
      include:
        - dockerfile: Dockerfile
          app: api
        - dockerfile: Dockerfile.worker
          app: worker
        - dockerfile: Dockerfile.migrate
          app: migrate
  steps:
    - uses: actions/checkout@v4
    - name: Build ${{ matrix.app }}
      run: docker build -f ${{ matrix.dockerfile }} -t myapp:${{ matrix.app }}-ci .
```

When a `make docker-build` target accepts `APP` or `DOCKERFILE` as a variable, delegate to it instead of inline `docker build`.

## 6) No Makefile or Partial Tasking

Preferred order:

1. existing scripts or task runner
2. controlled inline fallback
3. recommendation to introduce Makefile or stable task wrapper

Do not pretend full local parity exists when it does not.

When using inline fallback, mark each step clearly:

```yaml
# INLINE FALLBACK — no make target available
- name: Run tests
  run: go test -race ./...
```

Recommend specific targets in the output:

- `make ci` — combined format + test + lint + cover + build
- `make lint` — golangci-lint wrapper
- `make test` — `go test -race -cover ./...`
- `make docker-build` — container image build

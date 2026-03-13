# GitHub Actions Advanced Patterns

Use this file when the workflow needs more than a simple core gate.

## 1) Permissions

Default to least privilege:

```yaml
permissions:
  contents: read
```

Add extra scopes only when required. Do not default to broad write permissions.

Common permission escalations and when they apply:

| Permission | When Needed |
|-----------|-------------|
| `contents: write` | Release jobs that create tags or push commits |
| `packages: write` | Publishing container images to GHCR |
| `pull-requests: write` | Bots that comment on PRs (coverage reports, lint summaries) |
| `issues: write` | Bots that create or update issues |
| `security-events: write` | Uploading SARIF results to Security tab |

Set permissions at job level rather than workflow level when only specific jobs need escalation:

```yaml
permissions:
  contents: read

jobs:
  ci:
    runs-on: ubuntu-latest
    # inherits workflow-level contents: read
    steps: ...

  publish:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps: ...
```

### GITHUB_TOKEN vs Custom Tokens

- `GITHUB_TOKEN` is automatically provided, scoped to the repository, and expires after the job.
- Use it for all operations that stay within the same repository.
- Use a custom PAT or GitHub App token only when the workflow must access other repositories, trigger workflows in other repos, or bypass branch protection rules.
- Never store `GITHUB_TOKEN` in secrets — it is already available as `${{ github.token }}`.

## 2) Fork PR Safety

Assume fork PRs cannot safely access secrets.

Gate secret-dependent jobs with event and repo checks:

```yaml
api-integration:
  if: >-
    github.event_name == 'push' ||
    (github.event_name == 'pull_request' &&
     github.event.pull_request.head.repo.full_name == github.repository)
  runs-on: ubuntu-latest
  steps:
    - name: Run integration tests
      run: make ci-api-integration
      env:
        API_TOKEN: ${{ secrets.API_TOKEN }}
```

The condition `github.event.pull_request.head.repo.full_name == github.repository` ensures the job only runs for PRs from branches within the same repo, not from forks.

**`pull_request_target` warning:**

- `pull_request_target` runs in the context of the base branch and can access secrets.
- This is dangerous if the workflow checks out PR code (`actions/checkout` with `ref: ${{ github.event.pull_request.head.sha }}`).
- Avoid `pull_request_target` unless the trust model is explicitly understood and justified.
- If you must use it, never run untrusted PR code with access to secrets.

### Recommended Trigger Split for Open-Source Repos

```yaml
on:
  pull_request:      # fork-safe: runs core gate without secrets
  push:
    branches: [main] # trusted: runs all jobs including secret-dependent
```

This gives fork contributors fast feedback on the core gate while keeping secrets safe.

## 3) Reusable Workflows

Use `workflow_call` only when:

- duplication is real across repos or multiple workflows
- inputs are stable
- secret handling is clear

Do not extract reusable workflows for a one-off repository just for style.

```yaml
# .github/workflows/reusable-go-ci.yml
on:
  workflow_call:
    inputs:
      go-mod-path:
        required: true
        type: string
    secrets:
      API_TOKEN:
        required: false

jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version-file: ${{ inputs.go-mod-path }}
          cache: true
      - run: make ci
```

Caller side:

```yaml
jobs:
  call-ci:
    uses: ./.github/workflows/reusable-go-ci.yml
    with:
      go-mod-path: services/api/go.mod
    secrets: inherit
```

Use `secrets: inherit` only when the caller trusts the callee fully. Otherwise pass individual secrets explicitly.

## 4) Composite Actions

Use composite actions to share steps across jobs within the same repository, when reusable workflows are too heavy:

```yaml
# .github/actions/setup-go-env/action.yml
name: Setup Go Environment
description: Checkout, setup Go, install tools
inputs:
  go-mod-path:
    required: false
    default: go.mod
runs:
  using: composite
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-go@v5
      with:
        go-version-file: ${{ inputs.go-mod-path }}
        cache: true
    - name: Install golangci-lint
      shell: bash
      run: go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@v2.6.2
```

Usage:

```yaml
jobs:
  ci:
    steps:
      - uses: ./.github/actions/setup-go-env
      - run: make ci
```

When to choose composite actions over reusable workflows:

| | Composite Action | Reusable Workflow |
|-|-----------------|-------------------|
| Scope | Step-level sharing | Full job sharing |
| Secrets access | Inherits from caller job | Explicit `secrets:` |
| Runner | Runs on caller's runner | Own `runs-on:` |
| Best for | DRY step sequences | Cross-repo or multi-job extraction |

## 5) Matrix Strategy

Use matrices when they add clear confidence:

- multiple Go versions only if the project supports them intentionally
- multiple modules or apps when they are truly independent
- OS matrix only when portability matters

Avoid large matrices that slow PR feedback without adding meaningful signal.

For multi-module repos, use `fail-fast: false` to ensure one module failure does not mask others:

```yaml
strategy:
  fail-fast: false
  matrix:
    module: [services/api, services/worker, pkg/shared]
```

## 6) Self-Hosted Runners

When self-hosted runners are involved, state assumptions about:

- toolchain availability
- caching persistence
- trust boundary
- cleanup and isolation

Do not silently reuse GitHub-hosted assumptions on self-hosted runners.

## 7) Artifacts and Reports

Publish artifacts when they help diagnosis:

- coverage reports
- HTML or JUnit reports
- build artifacts only if needed for downstream validation

```yaml
- name: Upload coverage
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: coverage-report
    path: coverage.out
    retention-days: 7
```

## 8) Concurrency and Timeouts

- set `concurrency` to cancel redundant runs
- set reasonable `timeout-minutes` per job
- do not rely on GitHub defaults for expensive jobs

Recommended timeouts:

| Job Type | Timeout |
|---------|---------|
| Core gate (fmt + test + lint + build) | 15 min |
| Docker build | 10 min |
| Integration tests | 20 min |
| E2E tests | 30 min |
| Vulnerability scan | 10 min |

## 9) Service Containers

Use GitHub Actions `services:` for integration tests that need databases, caches, or message brokers:

```yaml
api-integration:
  runs-on: ubuntu-latest
  services:
    postgres:
      image: postgres:16-alpine
      env:
        POSTGRES_PASSWORD: testpass
        POSTGRES_DB: testdb
      ports:
        - 5432:5432
      options: >-
        --health-cmd="pg_isready"
        --health-interval=10s
        --health-timeout=5s
        --health-retries=5
    redis:
      image: redis:7-alpine
      ports:
        - 6379:6379
      options: >-
        --health-cmd="redis-cli ping"
        --health-interval=10s
        --health-timeout=5s
        --health-retries=5
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-go@v5
      with:
        go-version-file: go.mod
        cache: true
    - name: Run integration tests
      run: make ci-api-integration
      env:
        DB_HOST: 127.0.0.1
        DB_PORT: 5432
        REDIS_ADDR: 127.0.0.1:6379
```

Key rules:

- Always set `options:` with health checks so the job waits for the service to be ready.
- Use `127.0.0.1` (not `localhost`) with mapped ports on the runner.
- Pass connection details via environment variables, not hardcoded in test code.
- Keep service container versions pinned (e.g., `mysql:8.0`, not `mysql:latest`).
- Service containers are only available on Linux runners (`ubuntu-*`).

Common service container images for Go projects:

| Dependency | Image | Health Check |
|-----------|-------|-------------|
| PostgreSQL | `postgres:16-alpine` | `pg_isready` |
| MySQL | `mysql:8.0` | `mysqladmin ping -h localhost` |
| Redis | `redis:7-alpine` | `redis-cli ping` |
| Kafka | `confluentinc/cp-kafka:7.6.0` | `kafka-broker-api-versions --bootstrap-server localhost:9092` |
| MongoDB | `mongo:7` | `mongosh --eval "db.runCommand('ping')"` |

# Golden Example — Service With Integration Tests and Service Containers

Load this file only when the repository uses service containers (databases, caches) for integration tests.

- **Repository shape**: single-module service
- **Execution path**: `make ci` for core gate, `make ci-api-integration` for integration
- **Service containers**: MySQL and Redis for integration tests

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

  api-integration:
    name: API Integration
    runs-on: ubuntu-latest
    if: github.event_name == 'push' || github.event_name == 'schedule'
    timeout-minutes: 20
    services:
      mysql:
        image: mysql:8.0
        env:
          MYSQL_ROOT_PASSWORD: testpass
          MYSQL_DATABASE: testdb
        ports:
          - 3306:3306
        options: >-
          --health-cmd="mysqladmin ping -h localhost"
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

      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version-file: go.mod
          cache: true

      - name: Run integration tests
        run: make ci-api-integration
        env:
          DB_HOST: 127.0.0.1
          DB_PORT: 3306
          DB_USER: root
          DB_PASS: testpass
          DB_NAME: testdb
          REDIS_ADDR: 127.0.0.1:6379
```

## Output Summary

| Field | Value |
|-------|-------|
| Repository shape | single-module service |
| Jobs | ci, api-integration |
| ci execution path | `make target` → `make ci COVER_MIN=80` |
| api-integration execution path | `make target` → `make ci-api-integration` |
| Service containers | mysql:8.0, redis:7-alpine |
| Trigger | PR: ci only; push: ci + api-integration |
| Permissions | `contents: read` |
| Missing targets | none |

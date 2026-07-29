# Anti-Examples

Anti-patterns to avoid when generating or refactoring README files. Load this file when refactoring an existing README that may contain any of these patterns.

## Anti-Example: Fabricated badge URLs

BAD:

```markdown
![Coverage](https://codecov.io/gh/acme/myapp/badge.svg)
![Downloads](https://img.shields.io/npm/dm/myapp)
```

(Repo has no codecov config and is not an npm package)

GOOD:

```markdown
![CI](https://github.com/acme/myapp/actions/workflows/ci.yml/badge.svg)
![Go](https://img.shields.io/badge/Go-1.22-blue)
```

(Only badges derivable from actual repo evidence)

---

## Anti-Example: Guessed configuration values

BAD:

```markdown
## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | Database host |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection |
| `JWT_SECRET` | `changeme` | JWT signing key |
```

(No `.env.example` or config loader in repo — all values guessed)

GOOD:

```markdown
## Configuration

Configuration source: `.env.example` (copy to `.env` and fill in values).

| Variable | Required | Description |
|----------|----------|-------------|
| `DB_HOST` | Yes | Database host |
| `REDIS_URL` | Yes | Redis connection string |

> `JWT_SECRET`: Not found in repo — verify with team if JWT auth is used.
```

---

## Anti-Example: Maintainer workflow before value proposition

BAD:

```markdown
# MyService

## Development Setup
1. Install golangci-lint v1.55+
2. Run `make install-tools`
3. Configure pre-commit hooks
4. Set up local PostgreSQL 15

## Code Quality Policy
All PRs must pass `make ci` before merge...
```

GOOD:

```markdown
# MyService

订单处理服务，使用 PostgreSQL 存储、Redis 缓存。

## Quick Start

```bash
make run-api        # start on :8080
curl localhost:8080/health
```
```

## Anti-Example: Dumping full monorepo tree

BAD:

```markdown
## Project Structure

```
myorg/
├── apps/
│   ├── api/
│   │   ├── cmd/
│   │   │   └── main.go
│   │   ├── internal/
│   │   │   ├── handler/
│   │   │   │   ├── user.go
│   │   │   │   ├── order.go
│   │   │   │   └── health.go
│   │   │   ├── service/
│   │   │   │   ├── user.go
│   │   │   │   └── order.go
... (80 more lines)
```

GOOD:

```markdown
## Project Structure

| Module | Path | Description |
|--------|------|-------------|
| API Server | `apps/api/` | HTTP API (Go) |
| Worker | `apps/worker/` | Background jobs (Go) |
| Shared | `packages/shared/` | Common types and utils |

See each module's README for internal structure.
```

## Anti-Example: Double-language headings

BAD:

```markdown
## Quick Start / 快速开始

### Prerequisites / 前置条件

### Installation / 安装
```

GOOD:

```markdown
## 快速开始

### 前置条件

### 安装
```

(Pick one language; don't duplicate every heading)

## Anti-Example: Output snippet without input command

BAD:

```markdown
## Usage

Output:

```json
{"status": "ok", "users": [{"id": 1, "name": "Alice"}]}
```
```

GOOD:

```markdown
## Usage

```bash
curl -s localhost:8080/api/users | jq .
```

Response:

```json
{"status": "ok", "users": [{"id": 1, "name": "Alice"}]}
```
```

---

## Anti-Example: Metrics with no committed artifact

BAD:

```markdown
High-throughput order service — 10K+ TPS, p99 under 20ms, 94% test coverage.

BenchmarkValidate-8    5000000    240 ns/op
```

(No load test, no committed benchmark output, and `.codecov.yml` only sets `target: 80%`.
Every number here is unverifiable and goes stale silently.)

GOOD:

```markdown
Order service backed by PostgreSQL with a Redis cache layer.

Coverage target is 80%, configured in `.codecov.yml`.

`validator_test.go` defines `BenchmarkValidate`; run it with `go test -bench=.`.
```

(A config file proves a *target*; only a committed result artifact proves a *measurement*.
Show how to reproduce the number instead of asserting it.)

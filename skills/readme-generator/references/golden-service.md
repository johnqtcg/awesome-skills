# Golden Example: Go Service (Template A)

**Repo signals**: `go.mod` (Go 1.22), `cmd/api/main.go`, `internal/`, `Makefile` (15 targets), `.env.example`, `.github/workflows/ci.yml`, `LICENSE` (MIT), `CONTRIBUTING.md`, codecov config.

````markdown
![CI](https://github.com/acme/orderapi/actions/workflows/ci.yml/badge.svg)
![Coverage](https://codecov.io/gh/acme/orderapi/branch/main/graph/badge.svg)
![Go](https://img.shields.io/badge/Go-1.22-blue)
![License](https://img.shields.io/badge/license-MIT-blue)

# OrderAPI

High-throughput order processing service supporting 10K+ TPS with PostgreSQL and Redis caching.

## Quick Start

### Prerequisites

- Go 1.22+
- PostgreSQL 15+
- Redis 7+

### Run

```bash
cp .env.example .env          # configure database and Redis URLs
make install-tools             # install golangci-lint, mockgen
make run-api                   # start on :8080
```

Verify:

```bash
curl localhost:8080/health
# {"status":"ok","version":"v1.2.0"}
```

## Project Structure

```
orderapi/
├── cmd/api/              # HTTP server entrypoint
├── internal/
│   ├── handler/          # HTTP handlers (chi router)
│   ├── service/          # Business logic
│   ├── repository/       # PostgreSQL data access
│   └── cache/            # Redis caching layer
├── migrations/           # SQL migration files (golang-migrate)
├── config/               # YAML config loader
├── docs/                 # API documentation
├── Makefile              # 15 targets — run `make help`
└── .github/workflows/    # CI pipeline
```

## Configuration

Source: `.env.example`

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DB_URL` | Yes | — | PostgreSQL connection string |
| `REDIS_URL` | Yes | — | Redis connection string |
| `PORT` | No | `8080` | HTTP server port |
| `LOG_LEVEL` | No | `info` | Log level (debug/info/warn/error) |

## Common Commands

```bash
make help               # show all targets
make build-api          # build binary → ./bin/api
make run-api            # run API server
make test               # unit + integration tests
make test-race          # tests with race detection
make lint               # golangci-lint
make cover              # coverage report (target: 80%)
make migrate-up         # apply database migrations
make mock               # regenerate mocks
make ci                 # full CI pipeline locally
```

> Command source: root `Makefile`.

## Testing and Quality

```bash
make test               # all tests
make cover              # HTML coverage report → coverage.html
make lint               # golangci-lint with project config
```

Coverage target: 80% (enforced in CI).

## API Documentation

API docs generated from OpenAPI spec:

```bash
make swagger            # generate docs → docs/swagger/
```

Available at `http://localhost:8080/swagger/` when running locally.

## Deployment

Docker-based deployment:

```bash
make docker-build       # build image → orderapi:latest
make docker-run         # run container on :8080
```

Production deployment uses Kubernetes manifests in `deploy/k8s/`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development workflow and PR guidelines.

## License

MIT — see [LICENSE](LICENSE).

## Documentation Maintenance

Update this README when:
- New entrypoints are added under `cmd/`
- Environment variables change in `.env.example`
- Makefile targets are added or renamed
- CI workflows change in `.github/workflows/`
````

**Evidence mapping (assistant response)**:

| README Section | Evidence File(s) | Reason |
|---|---|---|
| Badges | `.github/workflows/ci.yml`, codecov config, `go.mod`, `LICENSE` | CI workflow, codecov, Go 1.22, MIT |
| Quick Start | `Makefile` (run-api), `.env.example` | Targets and config exist |
| Structure | `cmd/`, `internal/`, `migrations/`, `config/` | Directories present |
| Configuration | `.env.example` | 4 variables defined |
| Commands | `Makefile` (15 targets) | `make help` output |
| Testing | `Makefile` (test, cover, lint) | Targets present |
| API Docs | `Makefile` (swagger), `docs/` | Swagger target exists |
| Deployment | `Dockerfile`, `deploy/k8s/` | Docker and K8s configs |
| Contributing | `CONTRIBUTING.md` | File exists |
| License | `LICENSE` | MIT |

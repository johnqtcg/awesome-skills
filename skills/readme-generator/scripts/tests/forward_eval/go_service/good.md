# orderapi

![CI](https://github.com/acme/orderapi/actions/workflows/ci.yml/badge.svg)
![Coverage](https://codecov.io/gh/acme/orderapi/branch/main/graph/badge.svg)
![Go](https://img.shields.io/badge/Go-1.22-blue)
![License](https://img.shields.io/badge/license-MIT-blue)

HTTP order service backed by PostgreSQL, with a Redis cache layer.

## Prerequisites

- Go `>= 1.22` (from `go.mod`)
- PostgreSQL — connection string supplied via `DB_URL`
- Redis — connection string supplied via `REDIS_URL`

## Quick Start

```bash
cp .env.example .env    # fill in DB_URL and REDIS_URL
make install-tools
make run-api
```

## Project Structure

| Path | Purpose |
|------|---------|
| `cmd/api` | HTTP server entrypoint |
| `internal/handler` | Request handlers |
| `internal/service` | Business logic |
| `internal/cache` | Redis cache layer |
| `migrations` | SQL migration files |

## Configuration

Source: `.env.example`

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DB_URL` | Yes | — | PostgreSQL connection string |
| `REDIS_URL` | Yes | — | Redis connection string |
| `PORT` | No | `8080` | HTTP listen port |
| `LOG_LEVEL` | No | `info` | Log level |

## Common Commands

```bash
make help
make build-api
make run-api
make test
make lint
make cover
make migrate-up
```

> Command source: root `Makefile`.

## Testing and Quality

```bash
make test
make cover
make lint
```

Coverage is reported to Codecov; the target is configured in `.codecov.yml`.

## License

MIT — see `LICENSE`.

## Documentation Maintenance

Update this README when:

- a new entrypoint is added under `cmd`
- variables change in `.env.example`
- Makefile targets are added or renamed
- the workflow in `.github/workflows/ci.yml` changes

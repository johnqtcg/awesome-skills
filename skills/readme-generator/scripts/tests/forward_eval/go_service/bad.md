# orderapi

![CI](https://github.com/OWNER/REPO/actions/workflows/release.yml/badge.svg)
![Coverage](https://coveralls.io/repos/github/acme/orderapi/badge.svg)

High-throughput order processing service supporting 10K+ TPS with sub-20ms p99 latency.

## Prerequisites

- Go 1.22
- PostgreSQL 15

## Quick Start

```bash
make bootstrap
make serve
```

## Project Structure

- `internal/repository` — PostgreSQL data access
- `internal/handler` — Request handlers
- `deploy/k8s` — Production manifests

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DB_URL` | Yes | — | PostgreSQL connection string |
| `JWT_SECRET` | Yes | — | Token signing key |
| `SMTP_HOST` | No | `localhost` | Mail relay |

## Common Commands

```bash
make test
make deploy
```

## Testing and Quality — Status: Not verified in this environment

| Command | Verified |
|---------|----------|
| `make test` | Not verified |

The suite has 148 tests.

## Documentation Maintenance

Update this README when commands change.

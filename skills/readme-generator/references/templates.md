# README Templates by Project Type

Each template is a fillable markdown skeleton. Replace `{PLACEHOLDER}` with repo evidence. Remove sections marked `<!-- optional -->` if not applicable.

---

## Template A: Service / Backend

````markdown
<!-- badges: auto-detect from CI/coverage/go.mod -->
![CI]({CI_BADGE_URL})
![Coverage]({COVERAGE_BADGE_URL})
![Go Version]({GO_VERSION_BADGE})

# {PROJECT_NAME}

{One-sentence description of what this service does and its primary value.}

## Quick Start

### Prerequisites

- Go {VERSION} (from go.mod)
- {DATABASE/DEPENDENCY} (if required)
- Environment variables (see [Configuration](#configuration))

### Run

```bash
# install dev tools
make install-tools

# start the service
make run-api
```

## Project Structure

```
{PROJECT_NAME}/
├── cmd/
│   └── api/              # HTTP server entrypoint
├── internal/
│   ├── handler/          # HTTP handlers
│   ├── service/          # Business logic
│   └── repository/       # Data access layer
├── pkg/                  # Shared libraries (if any)
├── config/               # Configuration files
├── docs/                 # Documentation
├── Makefile              # Build/test/run commands
└── README.md
```

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `{ENV_VAR_1}` | Yes | — | {Description} |
| `{ENV_VAR_2}` | No | `{DEFAULT}` | {Description} |

Copy `.env.example` to `.env` and fill in values:

```bash
cp .env.example .env
```

## Common Commands

```bash
make help           # show all targets
make build-api      # build API binary
make run-api        # run API server
make test           # run all tests
make lint           # run linter
make cover          # run tests with coverage
make ci             # full CI pipeline locally
```

> Command source: root `Makefile`.

## Testing and Quality

```bash
make test           # unit + integration tests
make cover          # coverage report
make lint           # golangci-lint
```

Coverage target: {X}% (from Makefile or CI config).

<!-- optional: Architecture -->
## Architecture

{Brief description of service architecture, data flow, key design decisions. Include diagram if evidence exists.}

<!-- optional: Deployment -->
## Deployment

{Deployment target, process, and commands. Only if deployment config exists in repo.}

<!-- optional: API -->
## API Documentation

{Link to Swagger/OpenAPI docs if swagger target exists. E.g., `make swagger` generates docs at `docs/swagger/`.}

## Documentation Maintenance

This README should be updated when:
- New entrypoints are added under `cmd/`
- Environment variables change
- Makefile targets are added or renamed
- CI workflows change

## License

{License type from LICENSE file, or "Not found in repo — consider adding a LICENSE file."}
````

---

## Template B: Library / SDK

````markdown
![CI]({CI_BADGE_URL})
![Go Version]({GO_VERSION_BADGE})
![License]({LICENSE_BADGE})

# {PACKAGE_NAME}

{One-sentence description of what this library provides.}

## Installation

```bash
go get {MODULE_PATH}
```

## Quick Usage

```go
import "{MODULE_PATH}"

// {minimal working example — 5-15 lines}
```

## API Overview

| Function/Type | Description |
|--------------|-------------|
| `{Func1}` | {One-line description} |
| `{Func2}` | {One-line description} |
| `{Type1}` | {One-line description} |

For full API reference, see [pkg.go.dev]({PKG_GO_DEV_URL}).

## Compatibility

- Go >= {MIN_VERSION} (from go.mod)
- {Other compatibility notes}

## Testing

```bash
go test ./...
go test -race ./...
```

<!-- optional: Contributing -->
## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

{License type from LICENSE file.}
````

---

## Template C: CLI Tool

````markdown
![CI]({CI_BADGE_URL})
![Go Version]({GO_VERSION_BADGE})

# {CLI_NAME}

{One-sentence description of what this CLI does.}

## Installation

```bash
# from source
go install {MODULE_PATH}/cmd/{CLI_NAME}@latest

# or build locally
make build-{CLI_NAME}
```

## Usage

```bash
# basic usage
{CLI_NAME} {SUBCOMMAND} [flags]

# examples
{CLI_NAME} convert --input file.txt --output result.md
{CLI_NAME} serve --port 8080
```

## Commands and Flags

| Command | Description |
|---------|-------------|
| `{cmd1}` | {Description} |
| `{cmd2}` | {Description} |

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--{flag1}` | `-{f}` | `{default}` | {Description} |
| `--{flag2}` | `-{f}` | `{default}` | {Description} |

## Configuration

{CLI_NAME} reads configuration from (in priority order):
1. Command-line flags
2. Environment variables (`{PREFIX}_*`)
3. Config file (`{config_path}`)

<!-- optional: Exit Codes -->
## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| {N} | {Specific error} |

## Development

```bash
make build-{CLI_NAME}   # build binary
make test                # run tests
make lint                # run linter
```

## License

{License type from LICENSE file.}
````

---

## Template D: Monorepo

````markdown
![CI]({CI_BADGE_URL})

# {PROJECT_NAME}

{One-sentence description of the overall project/organization.}

## Repository Overview

| Module | Path | Description | Docs |
|--------|------|-------------|------|
| {App1} | `apps/{app1}/` | {One-line description} | [README](apps/{app1}/README.md) |
| {App2} | `apps/{app2}/` | {One-line description} | [README](apps/{app2}/README.md) |
| {Pkg1} | `packages/{pkg1}/` | {One-line description} | [README](packages/{pkg1}/README.md) |

## Quick Start

```bash
# install shared tools
make install-tools

# run a specific app
make run-{app1}

# run all tests
make test
```

## Shared Commands

```bash
make help               # show all targets
make test               # test all modules
make lint               # lint all modules
make build-all          # build all apps
make ci                 # full CI pipeline
```

## Project Structure

```
{PROJECT_NAME}/
├── apps/
│   ├── {app1}/          # {Description}
│   └── {app2}/          # {Description}
├── packages/
│   └── {pkg1}/          # {Description}
├── scripts/             # Shared build/deploy scripts
├── Makefile             # Root orchestration
└── README.md
```

## Adding a New Module

1. Create directory under `apps/` or `packages/`
2. Add module-level `README.md`
3. Add build/run targets to root `Makefile`
4. Update this table

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow.

## License

{License type from LICENSE file.}
````

---

## Template E: Lightweight (Small/Internal Repos)

Use this when the repository is small and heavy sections would add maintenance burden.

````markdown
# {PROJECT_NAME}

{One-sentence summary of purpose.}

## Quick Start

```bash
{PRIMARY_RUN_COMMAND}
```

> Command source: {Makefile/package.json/go commands}.

## Common Commands

```bash
{BUILD_CMD}   # build
{TEST_CMD}    # test
{LINT_CMD}    # lint
```

## Project Structure

```
{PROJECT_NAME}/
├── {KEY_DIR_1}/   # {purpose}
├── {KEY_DIR_2}/   # {purpose}
└── {ENTRYPOINT}   # {purpose}
```

## Testing and Quality

- Test: `{TEST_CMD}`
- Lint: `{LINT_CMD}`
- Coverage: `{COVER_CMD | Not found in repo}`

## Documentation Maintenance

Update this README when:
- commands change
- entrypoints change
- required config/env changes
````

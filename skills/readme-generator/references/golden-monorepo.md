# Golden Example: Monorepo (Template D)

**Repo signals**: `apps/api/`, `apps/worker/`, `packages/shared/`, root `Makefile`, `.github/workflows/ci.yml`, `go.work`, no LICENSE.

````markdown
![CI](https://github.com/acme/platform/actions/workflows/ci.yml/badge.svg)

# Acme Platform

Monorepo for Acme backend services and shared packages.

## Repository Overview

| Module | Path | Description | Docs |
|--------|------|-------------|------|
| API Server | `apps/api/` | Customer-facing HTTP API | [README](apps/api/README.md) |
| Worker | `apps/worker/` | Async job processor (Kafka) | [README](apps/worker/README.md) |
| Shared | `packages/shared/` | Common types, errors, middleware | [README](packages/shared/README.md) |

## Quick Start

```bash
make install-tools          # install shared dev tools
make run-api                # start API on :8080
make run-worker             # start worker
```

## Shared Commands

```bash
make help                   # show all targets
make test                   # test all modules
make lint                   # lint all modules
make build-all              # build all apps → ./bin/
make ci                     # full CI pipeline
```

> Command source: root `Makefile`. Each app also has local targets (e.g., `make -C apps/api run`).

## Project Structure

```
platform/
├── apps/
│   ├── api/                # HTTP API (Go 1.22, chi router)
│   └── worker/             # Kafka consumer (Go 1.22)
├── packages/
│   └── shared/             # Common types, middleware, errors
├── scripts/                # Build and deploy scripts
├── go.work                 # Go workspace file
├── Makefile                # Root orchestration (12 targets)
└── .github/workflows/      # CI pipeline
```

## Adding a New Module

1. Create directory under `apps/` or `packages/`
2. Run `go work use ./apps/newmodule` to register in workspace
3. Add module-level `README.md`
4. Add build/run targets to root `Makefile`
5. Update the Repository Overview table above

## Testing

```bash
make test                   # all modules
make test-api               # API only
make test-worker            # worker only
```

## License

License: Not found in repo — consider adding a LICENSE file.

## Documentation Maintenance

Update this README when:
- New app or package is added
- Root Makefile targets change
- CI workflow is modified
- Go workspace configuration changes
````

**Evidence mapping (assistant response)**:

| README Section | Evidence File(s) | Reason |
|---|---|---|
| Badges | `.github/workflows/ci.yml` | CI workflow only (no LICENSE) |
| Repository Overview | `apps/`, `packages/` | Directory structure |
| Quick Start | `Makefile` (run-api, run-worker) | Targets present |
| Commands | `Makefile` (12 targets) | `make help` output |
| Structure | `go.work`, `apps/`, `packages/` | Workspace layout |
| License | Not found in repo | No LICENSE file |

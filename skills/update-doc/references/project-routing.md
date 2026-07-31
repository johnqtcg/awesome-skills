# Project Routing Reference

Route README/docs structure by project type. Load after `scripts/discover_doc_scope.sh`
reports `LIKELY:` and `SCORES:`.

## Routing signals

The script scores four types from repository layout. Confirm the score against what the
repo actually is — a signal is evidence, not a verdict.

| Type | Strong signals | Common misroute |
|---|---|---|
| Service / Backend | `Dockerfile`, `deployments/`, `k8s/`, `charts/`, `cmd/` with a server entrypoint | A CLI in `cmd/` scores as service; check whether the entrypoint listens on a port or exits after one job |
| Library / SDK | `package.json` with `main`/`exports` and no server, `[project]` in `pyproject.toml`, `setup.py` | A library with an examples server scores as service |
| CLI Tool | `cmd/` with flag parsing, `bin` in `package.json`, a single argv-driven entrypoint | A CLI that also ships a daemon mode is both; document both invocation paths |
| Monorepo | `packages/`, `apps/`, `services/`, `go.work`, `pnpm-workspace.yaml`, `nx.json`, `turbo.json`, `[workspace]` in `Cargo.toml` | A repo with one `packages/` dir holding a single package is not a monorepo |

When two types tie, document for the reader who arrives first. A library that ships a CLI
is routed as a library if most readers `import` it, as a CLI if most readers install and
run it.

## Service / Backend

1. Overview
2. Quick start
3. Runtime modes
4. Config/env
5. Commands (run/test/lint)
6. Architecture (optional)
7. Ops/deploy (optional)

Runtime modes come before config because a reader who does not yet know the service has
a worker mode cannot interpret a worker-only env var. Config/env must name every variable
the code reads — a variable found in code but absent from the table is a drift defect,
not an omission.

## Library / SDK

1. Overview
2. Installation
3. Usage example
4. Public API surface
5. Compatibility/version notes
6. Test/development commands

The usage example precedes the API surface: a reader evaluating the library needs to see
it work before they read a symbol list. Document only the *exported* surface — internal
packages listed as public API become wrong the first time they are refactored.

## CLI Tool

1. Overview
2. Installation
3. Usage examples
4. Flags/options
5. Exit/error behavior (if evidence exists)

For generator-style CLIs, one example must show the full path: input → command → the file
or output produced → its shape. Replacing that with a bare flag table is the single most
common regression in CLI docs.

Document exit codes only where the source assigns them explicitly. Inferring "0 on success,
1 on error" without an `os.Exit` / `sys.exit` to point at is fabrication.

## Monorepo

1. Root overview
2. App/module index table
3. Shared tooling commands
4. Per-module doc links

The root README indexes; it does not duplicate. Each module's own README owns its detail.
The index table should carry module name, purpose, and its doc link — adding a full
dependency tree per module makes the root doc stale on every internal change.

Polyglot monorepos (`POLYGLOT: yes`) additionally need per-module language and command
source in the index table, because a single root `make test` may not exist and readers
otherwise cannot tell which toolchain a module needs.

## Sections to omit unless evidence exists

Adding an empty or speculative section is worse than omitting it — it signals coverage
the repo does not have.

- Architecture diagrams with no source to derive them from
- Benchmarks with no benchmark code
- Deployment guides with no deployment manifest
- Security policy with no threat model or reporting path
- Roadmap (not derivable from code at all)

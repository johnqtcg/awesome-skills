# Language Command Snippets

The templates in `templates.md` define **structure** — which sections a project type
needs and in what order. This file defines **commands** — what install, build, test, and
lint look like in each language. The two are separate axes on purpose: a Node CLI and a Go
CLI need the same sections and completely different command blocks, and a template that
bakes `go install` into "Template C" forces a rewrite every time the CLI is not Go.

Pick the template by `project_type effective`; pick the snippet by the manifest that
actually exists in the repo. Both come from `discover_readme_needs.sh`.

**Every snippet below is still subject to evidence rules.** A Makefile target outranks the
native command (SKILL.md §Command Priority), and a command must exist in the repo before it
goes in the README — `scripts/lint_readme.py` reports fabricated ones as R001/R002.

## Go

| Placeholder | Command | Evidence |
|---|---|---|
| `{INSTALL_CMD}` | `go install {MODULE}/cmd/{BIN}@latest` | `go.mod` module path + a `main` package |
| `{LIB_INSTALL_CMD}` | `go get {MODULE}` | `go.mod` module path |
| `{BUILD_CMD}` | `go build -o ./bin/{BIN} ./cmd/{BIN}` | `main` package location |
| `{RUN_CMD}` | `go run ./cmd/{BIN}` | same |
| `{TEST_CMD}` | `go test ./...` | `go.mod` |
| `{LINT_CMD}` | `golangci-lint run` | `.golangci.yml` present; otherwise `go vet ./...` |
| `{VERSION_LINE}` | Go `>= {N}` | `go` directive in `go.mod` |
| API reference | `https://pkg.go.dev/{MODULE}` | public module path |

## Node.js / TypeScript

| Placeholder | Command | Evidence |
|---|---|---|
| `{INSTALL_CMD}` | `npm install -g {NAME}` | `bin` in `package.json` |
| `{LIB_INSTALL_CMD}` | `npm install {NAME}` | `main`/`exports` in `package.json` |
| `{BUILD_CMD}` | `npm run build` | a `build` script |
| `{RUN_CMD}` | `npm start` or `node {ENTRY}` | a `start` script, or the `main` field |
| `{TEST_CMD}` | `npm test` | a `test` script |
| `{LINT_CMD}` | `npm run lint` | a `lint` script |
| `{VERSION_LINE}` | Node.js `{RANGE}` | `engines.node` |

Use the package manager the lockfile names — `pnpm-lock.yaml` → `pnpm`, `yarn.lock` →
`yarn`, `package-lock.json` → `npm`. Do not default to npm when the repo says otherwise.

## Python

| Placeholder | Command | Evidence |
|---|---|---|
| `{INSTALL_CMD}` | `pip install {NAME}` | a published `[project] name` |
| `{DEV_INSTALL_CMD}` | `pip install -e .` | `pyproject.toml` with a build backend |
| `{RUN_CMD}` | `{SCRIPT_NAME}` or `python -m {PKG}` | `[project.scripts]`, or `__main__.py` |
| `{TEST_CMD}` | `pytest` | a test directory, or `pytest` in a dev dependency group |
| `{LINT_CMD}` | `ruff check .` / `flake8` / `mypy .` | the tool's config in `pyproject.toml` or a dotfile |
| `{VERSION_LINE}` | Python `{RANGE}` | `requires-python` |

If the repo commits `poetry.lock` or `uv.lock`, document that tool's commands
(`poetry install` / `uv sync`) rather than bare `pip`.

## Rust

| Placeholder | Command | Evidence |
|---|---|---|
| `{INSTALL_CMD}` | `cargo install {NAME}` | `[[bin]]` or `src/main.rs` |
| `{LIB_INSTALL_CMD}` | `cargo add {NAME}` | `[lib]` or `src/lib.rs` |
| `{BUILD_CMD}` | `cargo build --release` | `Cargo.toml` |
| `{RUN_CMD}` | `cargo run` (add `-p {CRATE}` in a workspace) | `Cargo.toml` |
| `{TEST_CMD}` | `cargo test` (add `--workspace` in a workspace) | `Cargo.toml` |
| `{LINT_CMD}` | `cargo clippy` | clippy config, or CI invoking it |
| `{VERSION_LINE}` | Rust `>= {N}` | `rust-version` in `Cargo.toml` |
| API reference | `https://docs.rs/{NAME}` | published crate |

## Makefile Overrides Everything Above

When a Makefile defines the target, document the target and mention what it wraps:

```bash
make test               # runs `go test -race ./...`
```

The snippet tables are the fallback for repos with no task runner — see
`command-priority.md` for the full ladder and for what to do when several sources disagree.

## Cross-Language Section Notes

- **Prerequisites** — always state the language version from the manifest, plus any service
  the code connects to (database, cache, broker) that the config file proves.
- **Configuration** — only Service READMEs require this section. A CLI documents flags; a
  library documents function arguments. Adding a Configuration table to a library is the
  most common way a Go-service template leaks into a non-service README.
- **Project Structure** — describe the directories that exist. `cmd/` + `internal/` is a Go
  convention; `src/` + `test/` is Node; `src/{pkg}/` is Python; `crates/` is a Rust
  workspace. Do not carry one language's layout into another's README.

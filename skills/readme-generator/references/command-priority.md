# Command Source Priority

Use commands from highest-priority source available.

## Table of Contents

- [Priority Ladder](#priority-ladder)
- [Resolution Rules](#resolution-rules)
- [Verifiability](#verifiability)
- [Detection Checklist](#detection-checklist)
- [Command Block Format](#command-block-format)
- [Language-Specific Command Patterns](#language-specific-command-patterns)
- [Conflict Resolution Examples](#conflict-resolution-examples)
- [Makefile Target Extraction](#makefile-target-extraction)

## Priority Ladder

| Priority | Source | Example | When to Use |
|----------|--------|---------|-------------|
| 1 (highest) | Root `Makefile` | `make test` | Always preferred when Makefile exists |
| 2 | Language-native task runner | `go test ./...`, `npm test`, `cargo test` | When no Makefile or Makefile delegates to native |
| 3 | CI workflow commands | Commands from `.github/workflows/*.yml` | When local commands differ from CI |
| 4 | Existing doc commands | Commands from current README or docs/ | Only when consistent with actual code |

## Resolution Rules

- **One canonical command per task**: pick build, test, lint, run from the highest available source.
- **Multiple variants**: show recommended first, alternatives in a note.
- **Makefile wraps native**: if `make test` just runs `go test ./...`, show `make test` as primary.
- **CI-only commands**: if a command only runs in CI (e.g., `govulncheck`), note it as CI-only.
- **Task runner delegation**: if `package.json` scripts call Makefile targets, credit Makefile.

## Verifiability

| Status | Where It Belongs | When to Use |
|--------|------------------|-------------|
| `Verified` | Assistant response only | Command was executed in current session and succeeded |
| `Not verified` | Assistant response **only** — never in the README, even on request | Command exists in Makefile/scripts but was not run |
| `CI-only` | README or assistant response | Command is only meant to run in CI pipeline |

## Detection Checklist

When inspecting a repo, check these files in order:

1. `Makefile` → extract targets from `##` comments or `help` target
2. `package.json` → `scripts` section
3. `go.mod` → implies `go test`, `go build`, `go vet`
4. `Cargo.toml` → implies `cargo build`, `cargo test`
5. `pyproject.toml` / `setup.py` → implies `pytest`, `pip install`
6. `docker-compose.yml` → implies `docker compose up`
7. `.github/workflows/*.yml` → extract `run:` steps
8. Existing `README.md` → cross-check against actual files

## Command Block Format

Always include source attribution and inline comments:

```markdown
## Common Commands

```bash
make help               # show all targets
make build-api          # build binary → ./bin/api
make run-api            # run API server on :8080
make test               # unit + integration tests
make lint               # golangci-lint
make cover              # test coverage → coverage.html
make ci                 # full CI pipeline locally
```

> Command source: root `Makefile`.
```

Rules:
- Source attribution (which file the commands come from)
- Verification status in the assistant response by default
- Brief comment per command (use `#` inline)
- Arrow notation for output artifacts (`→ ./bin/api`)

## Language-Specific Command Patterns

### Go

```bash
# When Makefile exists
make build              # preferred
make test
make lint

# When no Makefile
go build -o ./bin/app ./cmd/app
go test ./...
go test -race ./...
go test -cover ./...
go vet ./...
```

Extras to detect:

- `go generate ./...` — only if `//go:generate` directives exist
- `go tool cover -html=coverage.out` — only if a coverage target or profile exists
- `go mod tidy` — a **maintenance** command, not a read-only one. It rewrites `go.mod` and
  `go.sum`, and its result depends on the toolchain version and build tags in use, so it
  can produce a diff a contributor did not intend. List it under a maintenance/contributing
  heading, never inside Quick Start, and never describe it as "safe to run".

### Node.js / TypeScript

```bash
# When package.json scripts exist
npm run build           # or yarn build / pnpm build
npm test
npm run lint

# Common script names to detect
"scripts": {
  "dev": "...",         → make dev / npm run dev
  "build": "...",       → make build / npm run build
  "test": "...",        → make test / npm test
  "lint": "...",        → make lint / npm run lint
  "start": "...",       → make start / npm start
}
```

### Python

```bash
# When pyproject.toml + poetry
poetry install
poetry run pytest
poetry run mypy .

# When setup.py / requirements.txt
pip install -e .
pytest
mypy .
```

### Rust

```bash
cargo build
cargo test
cargo clippy
cargo run
```

## Conflict Resolution Examples

### Scenario 1: Makefile wraps `go test`

```makefile
test:  ## Run tests
	go test -race -cover ./...
```

README should show: `make test` (primary), with note that it runs `go test -race -cover ./...` internally.

### Scenario 2: CI has extra steps not in Makefile

```yaml
# .github/workflows/ci.yml
- run: make test
- run: govulncheck ./...       # not in Makefile
- run: make lint
```

README should show:
```bash
make test               # unit + integration tests
make lint               # golangci-lint
# govulncheck ./... — CI-only (not in Makefile)
```

### Scenario 3: package.json and Makefile both exist

```json
"scripts": { "test": "make test" }
```

Credit Makefile as the source — `npm test` just delegates.

### Scenario 4: No Makefile, no task runner

```
# Only go.mod exists
go build ./cmd/app
go test ./...
go vet ./...
```

Note: `Command source: standard Go toolchain (no Makefile in repo).`

## Makefile Target Extraction

### Self-documenting Makefile (with `##` comments)

```makefile
.PHONY: help
help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

build-api:  ## Build API binary
	go build -o ./bin/api ./cmd/api

test:  ## Run all tests
	go test -race ./...
```

Extract: target name from left of `:`, description from `##` comment.

### Non-self-documenting Makefile

If no `##` comments, extract targets from `.PHONY` declarations or by listing targets with `:` that have recipe lines. Show targets without descriptions and note: `Run make <target> to see usage.`

### No Makefile

Explicitly state: `No Makefile found. Commands use standard toolchain.`

## Version-Specific Command Rules

These tables exist to stop a README from documenting a command the project cannot run.
Scope them accordingly: a rule earns a place here only when it changes a **command line or
a prerequisite line**. Language-feature caveats (`match`, `ExceptionGroup`, loop-variable
semantics) belong in the code, not in a README, and are omitted.

Every row cites the release that introduced the feature. That citation is the point: an
off-by-one version rule silently deletes a command that works, and the previous version of
this file had four of them. A row without a source is a row nobody can check — do not add
one.

### Go Version Rules

| Go version | Command | Rule |
|------------|---------|------|
| < 1.16 | `go install pkg@version` | Not supported — document `go get` instead |
| ≥ 1.17 | `go mod tidy -go=1.17` | Module-graph pruning; tidy output differs from older layouts, so pin the flag if the README shows expected output |
| < 1.18 | `go test -fuzz=Fuzz…` | Fuzzing does not exist — do not document a fuzz command |
| < 1.20 | `go build -cover` | Binary/integration coverage does not exist. `go test -cover` predates it and is always fine |
| < 1.21 | `go test -C dir` | Directory flag not available — document `cd dir && go test` |
| ≥ 1.22 | `go test ./...` in CI | Per-iteration loop variables changed test semantics; a README quoting old race-detector output should be re-run |
| ≥ 1.24 | `go tool <name>` | Tool dependencies declared with the `tool` directive in `go.mod`; on older versions document the `tools.go` + `go run` pattern instead |

Sources: [Go release notes index](https://go.dev/doc/devel/release) — `go install pkg@version`
[1.16](https://go.dev/doc/go1.16#go-command), fuzzing [1.18](https://go.dev/doc/go1.18#fuzzing),
module-graph pruning [1.17](https://go.dev/doc/go1.17#go-command),
`go build -cover` [1.20](https://go.dev/doc/go1.20#cover),
`go test -C` [1.21](https://go.dev/doc/go1.21#go-command),
loop-variable scoping [1.22](https://go.dev/doc/go1.22#language),
`tool` directive [1.24](https://go.dev/doc/go1.24#tools).

The `go` directive in `go.mod` is what gates these. Read it before writing any command.

### Node.js Version Rules

| Node version | Command / API | Rule |
|-------------|---------------|------|
| < 17 | `structuredClone()` | Not available (added in Node 17) |
| < 18 | global `fetch()` | Requires the `node-fetch` package |
| ≥ 18 | `node --test` | Built-in test runner — safe to document |
| < 18.11 | `node --watch` | Not available; document `nodemon` |
| < 20.6 | `node --env-file=.env` | Not available; document the `dotenv` package |
| ≥ 22 | `node --run <script>` | Runs a `package.json` script without npm |

Sources: [Node.js changelog](https://github.com/nodejs/node/blob/main/CHANGELOG.md) —
`structuredClone` [17.0.0](https://nodejs.org/en/blog/release/v17.0.0),
global `fetch` and `node --test` [18.0.0](https://nodejs.org/en/blog/announcements/v18-release-announce),
`--watch` [18.11.0](https://nodejs.org/en/blog/release/v18.11.0),
`--env-file` [20.6.0](https://nodejs.org/en/blog/release/v20.6.0),
`node --run` [22.0.0](https://nodejs.org/en/blog/release/v22.0.0).

Read `engines.node` in `package.json`. If it is absent, do not assume a version — document
the command that works on the oldest LTS you can justify, or state the requirement as
unknown.

### Python Version Rules

| Gated by | Command / API | Rule |
|---------------|---------------|------|
| Python < 3.11 | `tomllib` in a script you document | Requires the `tomli` package |
| **pip** < 21.3 | `pip install -e .` on a pyproject-only project | Editable install of a PEP 517/660 project needs pip ≥ 21.3 and a backend that implements `build_editable`. This is a **tooling** requirement, not a Python-version one |
| Backend support | `pip install -e .` | setuptools ≥ 64, hatchling, flit ≥ 3.4, and PDM implement PEP 660; a legacy backend may not |
| Lockfile present | `python -m venv` vs `poetry` vs `uv` | Document the one the repo configures — `poetry.lock`, `uv.lock`, or plain `requirements.txt` |

Sources: [PEP 660](https://peps.python.org/pep-0660/) (editable installs for
pyproject-based builds — a frontend/backend protocol, **not** a language feature; the earlier
version of this table wrongly keyed it to Python ≥ 3.11),
[pip 21.3 changelog](https://pip.pypa.io/en/stable/news/#v21-3),
[`tomllib` — Python 3.11](https://docs.python.org/3/library/tomllib.html).

Read `requires-python` in `pyproject.toml` for the language gate, and the `[build-system]`
table for the backend gate. They are different questions.

### Rust Version Rules

| Rust version | Command | Rule |
|-------------|---------|------|
| < 1.53 | `cargo clippy --fix` | Not available |
| < 1.62 | `cargo add` | Not built in; document editing `Cargo.toml` directly |
| < 1.74 | `[lints]` table in `Cargo.toml` | Not supported; lint config lives in `#![deny(...)]` or clippy args |

Sources: [Rust releases](https://releases.rs/) — `cargo clippy --fix`
[1.53](https://blog.rust-lang.org/2021/06/17/Rust-1.53.0.html), `cargo add`
[1.62](https://blog.rust-lang.org/2022/06/30/Rust-1.62.0.html), `[lints]`
[1.74](https://blog.rust-lang.org/2023/11/16/Rust-1.74.0.html).

Read `rust-version` in `Cargo.toml`. Note that Rust *edition* (2015/2018/2021/2024) and
Rust *version* are different axes — a version rule keyed to an edition is a mistake, and the
earlier version of this table made it twice.

### How to Apply

1. Read the version from `go.mod`, `package.json` `engines`, `pyproject.toml`
   `requires-python`, or `Cargo.toml` `rust-version`.
2. Cross-reference the table above.
3. If a command is unavailable at that version, either omit it or document the supported
   alternative. Do not include it with a "requires a newer version" aside in Quick Start —
   the reader will paste it anyway.
4. If the manifest declares no version, say so in Prerequisites rather than inventing one.

Worked example — a project whose `go.mod` says `go 1.19`:

```markdown
## Testing

```bash
go test ./...
go test -race ./...
go test -cover ./...
```
```

`go build -cover` is omitted (needs 1.20) and `go tool` is omitted (needs 1.24). Fuzzing and
`t.Setenv` are both available at 1.19 and need no caveat — a note claiming otherwise would
send readers looking for a problem that does not exist.

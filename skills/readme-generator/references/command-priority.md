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
| `Not verified` | Assistant response by default; README only when explicitly requested | Command exists in Makefile/scripts but was not run |
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
- `go generate ./...` — if `//go:generate` directives exist
- `go mod tidy` — always safe to mention
- `go tool cover -html=coverage.out` — if coverage target exists

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

When documenting commands, check the project's language version and apply these filters. Do NOT recommend features unavailable in the project's actual version.

### Go Version Rules

| Go Version | Command/Feature | Rule |
|------------|----------------|------|
| < 1.16 | `go install pkg@version` | Use `go get` instead |
| < 1.17 | `t.Setenv()` in tests | Do NOT mention; use `os.Setenv` + cleanup |
| < 1.18 | `go test -fuzz` | Do NOT mention fuzzing commands |
| < 1.21 | `slog` package | Do NOT reference structured logging with slog |
| < 1.22 | `go test -cover` (binary) | Coverage binary profiling not available |
| < 1.22 | Range variable capture in goroutines | Add warning about loop variable capture |
| ≥ 1.22 | `go vet` copylocks | Safe to recommend without caveats |

Example:

```markdown
## Testing

```bash
go test ./...               # all tests
go test -race ./...         # race detection
```

> Note: Go 1.20 project — `go test -fuzz` and `t.Setenv` are not available.
```

### Node.js Version Rules

| Node Version | Feature | Rule |
|-------------|---------|------|
| < 16 | `structuredClone()` | Not available |
| < 18 | `--watch` flag | Use `nodemon` instead |
| < 18 | `fetch()` (global) | Requires `node-fetch` package |
| < 20 | `--env-file` flag | Use `dotenv` package |
| ≥ 18 | `node --test` | Can mention built-in test runner |

### Python Version Rules

| Python Version | Feature | Rule |
|---------------|---------|------|
| < 3.10 | `match` statement | Do NOT use in examples |
| < 3.11 | `tomllib` | Require `tomli` package |
| < 3.11 | `ExceptionGroup` | Not available |
| < 3.12 | `type` statement | Use `TypeAlias` from typing |

### Rust Version Rules

| Rust Edition | Feature | Rule |
|-------------|---------|------|
| < 2021 | `cargo clippy --fix` | May not be stable |
| < 1.70 | `cargo doc --open` with `--document-private-items` | Flag not available |

### How to Apply

1. Read version from `go.mod`, `package.json engines`, `pyproject.toml requires-python`, or `Cargo.toml rust-version`
2. Cross-reference with the tables above
3. If a command or feature is not supported, either:
   - Omit it silently, or
   - Include it with a version note: `> Requires Go 1.18+ (project uses Go 1.17)`
4. Never recommend unavailable features without a version caveat

---
name: go-makefile-writer
description: Canonical skill for Go Makefiles. Create/refactor root Makefiles for Go repositories with standardized build/test/lint/run targets, self-documenting help outputexample, predictable artifacts, and maintainable target naming.
disable-model-invocation: true
allowed-tools: Read, Write, Grep, Glob, Bash(make*), Bash(go version*), Bash(go test*), Bash(go generate*), Bash(go install*), Bash(go get*), Bash(go build*), Bash(go mod*), Bash(go run*), Bash(go fmt*), Bash(git diff*), Bash(scripts/discover_go_entrypoints.sh*)
---

# Go Makefile Writer

Design a practical root `Makefile` that is readable, reproducible, and aligned with repository layout.

## Quick Reference

| If you need to… | Go to |
|---|---|
| Create a Makefile from scratch for a new Go project | §Execution Modes → Create + §Workflow |
| Refactor or update an existing Makefile (minimal-diff) | §Execution Modes → Refactor |
| Decide which targets to include (`build`, `test`, `lint`, `ci`…) | §Workflow (Plan targets) |
| Get a complete working Makefile example to start from | Load `references/golden/simple-project.mk` or `complex-project.mk` |
| Check quality rules, variable conventions, `.PHONY` requirements | Load `references/makefile-quality-guide.md` |
| Review a Makefile PR quickly | Load `references/pr-checklist.md` |
| Handle a monorepo or multi-module Go repo | §Monorepo Support |

## Execution Modes

Select a mode before starting and state it in the output report.

### Create (new Makefile from scratch)

- Full target set generated from project inspection.
- Use golden templates ([simple-project.mk](references/golden/simple-project.mk) / [complex-project.mk](references/golden/complex-project.mk)) as starting points.
- No backward-compatibility concerns.

### Refactor (modify existing Makefile)

- **Minimal-diff edits** — change only what is needed; do not rewrite the entire file.
- **Backward compatibility**: if target names change, keep aliases for at least one transition period and document them in the output report.
- **Preserve existing useful targets** unless user explicitly asks to remove them.
- Before editing, snapshot the current target list via `make -qp | awk -F: '/^[a-zA-Z0-9_-]+:/ {print $1}' | sort -u` for comparison.
- Validation must include verifying that previously used critical targets still work (or their aliases do).

## Workflow

0. **Select mode** (`Create` or `Refactor`) and record rationale.

1. **Inspect** project structure:
   - discover `cmd/**/main.go` entrypoints via `scripts/discover_go_entrypoints.sh`
   - if the script cannot run, fall back to `rg --files cmd | rg '/main\.go$$'`
   - detect quality tools and conventions (`go test`, `golangci-lint`, `swag`)
   - detect code generation usage (`go generate`, protobuf, wire, mockgen, etc.)
   - detect containerization (`Dockerfile`, `docker-compose.yml`)
   - **read `go.mod`** for Go version (`go` directive) and module path
   - inspect existing `Makefile` if present (Refactor mode)
   - **detect monorepo layout**: check for multiple `go.mod` files via `rg --files -g 'go.mod'`

2. **Plan** target set:
   - core targets: `help`, `fmt`, `tidy`, `test`, `cover`, `lint`, `clean`
   - version targets: `version` (print embedded version info)
   - CI target: `ci` (fmt-check + lint + test + cover-check in one pass)
   - optional targets: `swagger`, `generate`, `install-tools`, `test-integration`, `bench`
   - build targets: `build-all` plus per-binary targets (with `-ldflags` version injection)
   - run targets: per-binary `run-*` targets
   - container targets (when Dockerfile present): `docker-build`, `docker-push`
   - cross-compile targets (when needed): `build-linux`, `build-all-platforms`
   - **Go version-aware decisions** (see [Go Version Awareness](#go-version-awareness))

3. **Compose** and write root Makefile:
   - keep targets explicit and predictable
   - use variables (`GO`, `BIN_DIR`, `VERSION`, `COMMIT`, `BUILD_TIME`) for repeated paths and build metadata
   - inject version info via `-ldflags` in all build targets
   - include `.PHONY`
   - fail early with clear tool checks for optional dependencies
   - use target templates from [makefile-quality-guide.md](references/makefile-quality-guide.md)
   - **Refactor mode**: apply minimal-diff strategy and backward-compatibility rules from the mode definition above

4. **Validate**:
   - run `make help`
   - run `make test`
   - run one representative `build-*` target
   - run `make version` to verify version injection
   - if possible, run one representative `run-*` target in a safe environment
   - **Refactor mode**: verify previously used critical targets still work (or provide aliases); compare target list before vs after

## Rules

### Target Design
- Prefer explicit targets over complex metaprogramming unless the user asks for DRY-heavy style.
- Keep artifact outputs deterministic (under `bin/`).
- Keep `help` output self-documenting via `##` comments with `.DEFAULT_GOAL := help`.
- Map target names to `cmd/` path semantics: `cmd/<name>` → `build-<name>`, `cmd/<kind>/<name>` → `build-<kind>-<name>`.
- Declare all non-file targets in `.PHONY`.
- Output executable bare `Makefile` by default (tabs for recipes, not spaces).

### Build Quality
- Inject version info via `-ldflags` in **all** build targets:
  ```
  LDFLAGS := -s -w -X main.version=$(VERSION) -X main.commit=$(COMMIT) -X main.buildTime=$(BUILD_TIME)
  ```
- Always include `-race` flag in test targets.
- For container builds and cross-compilation, set `CGO_ENABLED=0` for static binaries.
- Pin tool versions in `install-tools` for CI reproducibility.

### Safety
- Fail early with clear tool-presence checks (`command -v <tool>`) for optional dependencies.
- `ci` target must mirror actual CI pipeline — developers should catch issues before push.
- Check for code generation staleness (`generate-check`) when `go generate` is used.

## Go Version Awareness

Read `go.mod` for the `go` directive before composing the Makefile. Record as `Go version: X.Y` in the output report.

| Go Version | Makefile Impact |
|-----------|-----------------|
| < 1.16 | `go install` does not support `@version` syntax; use `go get` for tool installation |
| < 1.18 | No `go build -cover`; use `-coverprofile` flag via `go test` only |
| ≥ 1.21 | `go test -coverprofile` supports integration coverage via `GOCOVERDIR`; consider `cover-integration` target |
| ≥ 1.22 | Enhanced loop variable semantics; no Makefile impact but note in output |

If `go.mod` is not found or not readable, record `Go version: unknown` and use conservative defaults (no version-specific features).

## Monorepo Support

When multiple `go.mod` files are detected (step 1 Inspect), adapt the Makefile for monorepo layout:

- **Module discovery**: list all modules via `rg --files -g 'go.mod' | xargs -I{} dirname {}`
- **Per-module targets**: generate `test-<module>`, `lint-<module>`, `build-<module>` for each module that has entrypoints
- **Aggregate targets**: `test-all`, `lint-all`, `build-all` that iterate over all modules
- **Root Makefile pattern**:

```make
MODULES := $(shell rg --files -g 'go.mod' | xargs -I{} dirname {} | sort)

test-all: ## Run tests for all modules
	@for mod in $(MODULES); do \
		echo "=== testing $$mod ==="; \
		(cd $$mod && go test -race ./...) || exit 1; \
	done

lint-all: ## Lint all modules
	@for mod in $(MODULES); do \
		echo "=== linting $$mod ==="; \
		(cd $$mod && golangci-lint run) || exit 1; \
	done
```

- When the project is a single-module repo, this section does not apply — use the standard single-module workflow.
- Record `Layout: monorepo (N modules)` or `Layout: single-module` in the output report.

## Anti-Patterns (DO NOT generate these)

Before writing or reviewing a Makefile, check against these common mistakes. If your output matches any of these patterns, fix it before delivering.

**Missing fundamentals:**
- No `help` target or missing `##` self-documenting comments
- No `.PHONY` declaration for non-file targets
- No `-race` flag in `test` target
- No `-ldflags` version injection in `build-*` targets

**Naming and layout:**
- Target names not matching `cmd/` path semantics (e.g., `cmd/consumer/sync` but target is `build-sync` instead of `build-consumer-sync`)
- `run-*` targets leaving ad-hoc binaries in source directories instead of `bin/`

**Reproducibility:**
- `install-tools` using `@latest` for all tools in CI (pin specific versions for reproducibility; `@latest` is acceptable only for local dev convenience)
- `ci` target that diverges from the actual CI pipeline — `make ci` should mirror CI exactly
- Hidden assumptions about local paths or OS-specific tools (e.g., `sed -i` without considering macOS vs GNU differences)

**Cross-compilation:**
- Cross-compilation without `CGO_ENABLED=0` — produces dynamically linked binaries that fail on target machines
- Hardcoded `GOOS/GOARCH` without variable override

**Code generation:**
- Generated code not checked for staleness before build (missing `generate-check` target)

**Over-engineering:**
- Overly dynamic Make metaprogramming (eval/call/define) that reduces readability when explicit targets would be clearer
- Tab-vs-space issues in Makefile recipes (recipes MUST use tabs, not spaces)

## Quality Improvements to Offer

- Add `.DEFAULT_GOAL := help`.
- Add `cover-check` target with a configurable threshold.
- Add `tidy` target for `go mod tidy` + `go mod verify`.
- Keep `run-*` from polluting source directories; prefer `go run ./cmd/...` or run from `bin/`.
- Pin tool versions in `install-tools` for CI reproducibility (see [quality-guide §11](references/makefile-quality-guide.md#11-tool-installation)).

## Load References Selectively

When starting any Makefile creation or refactor task:
→ Run `scripts/discover_go_entrypoints.sh` first to discover `cmd/**/main.go` binary locations and infer project shape (single-binary vs multi-binary).

When writing or reviewing specific targets (`build`, `test`, `lint`, `run`, `install-tools`), or checking quality rules:
→ Load `references/makefile-quality-guide.md` for canonical target templates, variable conventions, `.PHONY` rules, self-documenting `help` output, and the 15-item review checklist.

When reviewing a PR that touches a Makefile:
→ Load `references/pr-checklist.md` for the fast Makefile-specific PR review checklist (target naming, portability, idempotency, CI compatibility).

When you need a complete working Makefile as a starting point or reference:
→ Load `references/golden/simple-project.mk` for a single-binary project with minimal tooling.
→ Load `references/golden/complex-project.mk` for a multi-binary project with Docker, code generation, and cross-compilation targets.

## Output Contract

When generating or refactoring a Makefile, always return:

1. **Mode**: `Create` or `Refactor` with rationale
2. **Project info**: Go version (from `go.mod`), layout (`single-module` or `monorepo (N modules)`), entrypoints discovered
3. **Changed files**
4. **New/updated targets**
5. **Deprecated/aliased targets** (Refactor mode — list old name → new name mappings)
6. **Assumptions or missing tools**
7. **Validation commands executed** with pass/fail status

### Example Output (Create mode, single-binary)

```
### Mode
Create — no existing Makefile found

### Project info
- Go version: 1.23 (from go.mod)
- Layout: single-module
- Entrypoints: cmd/api

### Changed files
- `Makefile` (created)

### New targets
help, build-api, build-all, run-api, fmt, fmt-check, tidy,
test, cover, cover-check, lint, ci, version, install-tools,
check-tools, clean

### Deprecated/aliased targets
(none — new Makefile)

### Assumptions
- golangci-lint will be installed via `make install-tools`
- Version info injected into `main.version`, `main.commit`, `main.buildTime`

### Validation
✓ make help       — 16 targets listed
✓ make test       — all tests pass with -race
✓ make build-api  — binary at bin/api
✓ make version    — version=v0.1.0-dirty commit=abc1234
```

## Self-Validation

Run `scripts/run_regression.sh` to verify skill integrity:
- **Contract tests**: structure of SKILL.md, quality guide, golden examples, discovery script
- **Golden review tests**: all defect/FP fixtures' rules covered in docs
- **Coverage matrix**: see `scripts/tests/COVERAGE.md`

---
name: go-makefile-writer
description: Canonical skill for Go Makefiles. Create/refactor root Makefiles for Go repositories with standardized build/test/lint/run targets, self-documenting help output, predictable artifacts, and maintainable target naming.
disable-model-invocation: true
allowed-tools: Read, Write, Grep, Glob, Bash(make*), Bash(go version*), Bash(go env*), Bash(go list*), Bash(go test*), Bash(go generate*), Bash(go install*), Bash(go get*), Bash(go build*), Bash(go mod*), Bash(go run*), Bash(go fmt*), Bash(git diff*), Bash(git status*), Bash(*discover_go_entrypoints.sh*)
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
   - discover entrypoints (`package main`, wherever it lives) by running this skill's discovery script against the target repo: `bash <skill-dir>/scripts/discover_go_entrypoints.sh <project-root>` (the script lives in the skill directory, not in the target repo — pass the repo root as its argument)
   - **read the script's exit status before its output.** `0` means the query was complete and what you got is the whole answer — including an empty answer, which then genuinely means "library, no programs". `4` means the query was incomplete: empty output is *unknown*, not *library*. `2` is a bad root, `3` (with `--modules`) is zero modules. The stderr diagnostic names the toolchain error to fix
   - the script emits 5 tab-separated fields — `kind  name  target_name  dir  confidence`. **`confidence` is not decoration.** `confirmed` means `go list` reported the package's name as `main`, and can become a build target directly. `candidate` means the toolchain could not be asked about that subtree and the row is a filename guess — list those to the user for confirmation instead of generating targets from them, and say in your output that they are unconfirmed
   - if the script cannot run at all, fall back to `find cmd -name main.go -type f`, but treat every result as a candidate: a file named `main.go` may declare any package, and a program's file may be named anything
   - detect quality tools and conventions (`go test`, `golangci-lint`, `swag`)
   - detect code generation usage (`go generate`, protobuf, wire, mockgen, etc.)
   - detect containerization (`Dockerfile`, `docker-compose.yml`)
   - **read `go.mod`** for Go version (`go` directive) and module path
   - inspect existing `Makefile` if present (Refactor mode)
   - **detect workspace / multi-module layout via the toolchain first**: `go env GOWORK` — a real path means a `go.work` workspace (its modules are `go list -m`), while the literal string `off` means workspace mode was **disabled** and must be treated as "no workspace", not as a path. Only when there is no `go.work` fall back to a scoped `go.mod` search (`bash <skill-dir>/scripts/discover_go_entrypoints.sh --modules <project-root>`, which excludes `vendor/`, `testdata/`, `examples/`). See §Monorepo Support.

2. **Plan** target set:
   - core targets: `help`, `fmt`, `tidy`, `test`, `cover`, `lint`, `clean`
   - version targets (**programs only**): `version` (print embedded version info)
   - CI target: `ci` (fmt-check + lint + test + cover-check in one pass)
   - optional targets: `swagger`, `generate`, `install-tools`, `test-integration`, `bench`
   - build targets (**programs only**): `build-all` plus per-binary targets, with `-ldflags` version injection unless the project already has a version mechanism
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
   - **when the project has a binary and version injection was added**: build, then run the binary's version surface (`--version`, a `version` subcommand — whatever it actually has) to verify injection reached the artifact. `make version` only prints the Make variables, not what the binary embeds. A library-only repo has nothing to run here; validate with `make test` instead.
   - if possible, run one representative `run-*` target in a safe environment
   - **Refactor mode**: verify previously used critical targets still work (or provide aliases); compare target list before vs after

## Rules

Each rule carries its force, because "we always add a `version` target" and "a
target must not exit 0 when its work failed" are not the same kind of claim and
should not be argued about on the same terms:

| Tag | Force | What to do when a project disagrees |
|-----|-------|-------------------------------------|
| **[C]** | **Correctness.** Breaking it produces a Makefile that lies about success, or that does not work. | Do not deviate. If the user insists, say plainly what will break. |
| **[D]** | **Recommended default.** Right for most Go repos; a project may have a real reason not to. | Follow it unless the repo shows otherwise; if you deviate, say why in the Assumptions block. |
| **[T]** | **Template convention.** This template's house style. A repo doing it differently is not wrong. | Match the repo's existing convention over this one. |

### Error Propagation — every rule here is [C]

A build script whose targets exit 0 on internal failure is worse than no script:
CI goes green on a broken tree. These are the shapes that leak, all of which
shipped in this skill's own templates until 2026-09-09:

- **[C] Branch on a tool's exit status, not only on its output.** `gofmt -l` on a
  file that does not parse prints the error to **stderr**, prints **nothing** on
  stdout, and exits **2** — so `test -z "$(gofmt -l .)"` passes a tree that does
  not compile. Capture both and check the status first.
- **[C] A pipeline reports only its last command's status.** `curl … | sh` succeeds
  when the download fails, because `sh` given no input exits 0. Either set
  `SHELL := bash` with `.SHELLFLAGS := -euo pipefail -c`, or download to a temp
  file and check before executing. Prefer both: the recipe stays correct if the
  template is copied somewhere without bash.
- **[C] A `for` loop's status is its last iteration's.** Put `|| exit 1` in the
  body, or a broken first binary is masked by a working second one.
- **[C] A staleness check must compare content, not status strings.**
  `git status --porcelain` prints the same `?? path` line however the file's
  contents change, and `git diff` skips untracked files — so hash them
  (`git hash-object`) rather than trusting the status line.
- **[C] An aggregate target must fail when it has nothing to aggregate.** A
  module or entrypoint list that comes back empty means discovery broke; looping
  over nothing and exiting 0 is the failure this whole layer exists to prevent.
- **[C] A loop body must not END on a test.** `while read f; do [ -f "$f" ] &&
  echo …; done` takes the loop's status from the last iteration's `[ -f ]`, so
  one skipped entry fails the whole target under `set -e`. Write `if … then …
  fi`, which ends on the `fi` and is always true. This is the mirror image of
  the loop rule above: there a real failure was swallowed, here a non-failure
  was manufactured — both come from not knowing what the loop's status is.
- **[C] "Nothing found" and "could not look" are different answers.** A check
  that cannot run has not passed. Give the two outcomes different exit codes
  and let the caller branch on them; collapsing them into "exit 0, no output"
  is how a program with an unreadable build cache gets classified as a library
  and loses every build target it should have had.

### Project shape decides the target set

Ask what the repo *is* before applying the default target list. Getting this
wrong is how a generated Makefile ends up demanding things the project cannot
supply:

| Repo shape | How to tell | What changes |
|---|---|---|
| **Library only** (no programs) | `discover_go_entrypoints.sh` **exits 0** having printed nothing. Exit 0 is the part that matters: it means every module answered, so "no programs" is an answer rather than a silence | **No** `build-*`, `run-*`, `version` target, `-ldflags` injection, or `--version` validation — there is no binary to inject into. Keep `fmt`/`tidy`/`test`/`cover`/`lint`/`ci`. Validate with `make test`, not with a binary. |
| **Program with its own version mechanism** | an existing `version` package, `debug.ReadBuildInfo()`, a generated `version.go`, or a release tool that stamps binaries | Do **not** add a second, competing mechanism. Wire the existing one, or leave version handling alone and say so. `-ldflags -X` is [D], not [C]. |
| **cgo project** | `import "C"`, `mattn/go-sqlite3`, … | `CGO_ENABLED=1`; drop the static-build and `CGO_ENABLED=0` cross-compile defaults. |
| **No `--version` flag** | the binary uses a `version` subcommand, or has none | Validate injection however the program actually exposes it. Do not add a flag to someone's CLI to satisfy a Makefile check. |
| **Different test strategy** | build-tagged integration suites, a test script, `gotestsum`, no `-race` on this platform | Mirror what CI runs. The `ci` target's job is to match the pipeline, not to impose this template's. |
| **Shape not yet known** | `discover_go_entrypoints.sh` **exits 4** — the toolchain could not be asked about some or all of the tree (bad `GOFLAGS`, unreadable build cache, no `go.mod`, a module that will not load) | **Do not classify.** Empty output here means *unknown*, not *library*: a perfectly ordinary program can produce it. Fix the reported toolchain error and re-run, or tell the user what could not be checked and what you assumed. Guessing "library" here silently drops every `build-*` target the repo should have. |

When a project's shape contradicts a [D] rule, follow the project and record the
deviation in the Assumptions block of your output. When it contradicts a [C]
rule, that is a defect in the project, and worth saying so.

### Target Design
- **[D]** Prefer explicit targets over complex metaprogramming unless the user asks for DRY-heavy style.
- **[C]** Keep artifact output paths deterministic — a target whose output location varies per invocation cannot be cached or cleaned reliably.
- **[T]** Put them under `bin/`. Match an existing repo's choice (`build/`, `dist/`, `out/`) over this one.
- **[T]** Keep `help` output self-documenting via `##` comments with `.DEFAULT_GOAL := help`. A repo with its own help format is not defective — fixture `009_custom_help_format_fp.json` exists to stop that being reported as one. What *is* [C]: `make help` must work and must list the targets.
- **[T]** Map target names to `cmd/` path semantics: `cmd/<name>` → `build-<name>`, `cmd/<kind>/<name>` → `build-<kind>-<name>`. Match an existing repo's naming first.
- **[C]** Declare all non-file targets in `.PHONY` — otherwise a same-named file silently disables the target.
- **[C]** Output executable bare `Makefile` (tabs for recipes, not spaces) — spaces produce "missing separator" and the file simply does not run.

### Build Quality
- **[D]** Inject version metadata via `-ldflags` in build targets — **only when the project has a binary and no version mechanism of its own** (see Project shape):
  ```
  LDFLAGS := -s -w -X main.version=$(VERSION) -X main.commit=$(COMMIT) -X main.buildTime=$(BUILD_TIME)
  ```
  `-X` only sets an **existing** package-level string var — `-X main.version` assumes `var version string` in package `main`; discover the real package/name first and use its import path if it lives elsewhere (a wrong path silently no-ops). `-s -w` strips the symbol table and DWARF (release builds only; keep a debug build without it).
- **[D]** Default the `test` target to `-race` — it catches real data races. But `-race` requires `CGO_ENABLED=1`, a supported OS/arch, and adds ~5–10× memory / 2–20× time. Offer a genuine race-free equivalent, `test-norace` (`go test ./...` — the **full** suite, no race), for cgo-disabled builds and platforms without race support. Do not conflate this with `test-short` (`go test -short ./...`): `-short` skips `testing.Short()`-gated cases, so it runs a *smaller* set — it turns off race only as a side effect and is not a substitute for the full suite.
- **[D]** `CGO_ENABLED=0` is the default for **pure-Go** static builds and containers. For cgo projects (`import "C"`, `mattn/go-sqlite3`, …) keep `CGO_ENABLED=1` — and note the two collide: a `-race` test target cannot run under `CGO_ENABLED=0`.
- **[D]** For reproducible release builds add `-trimpath` (strips local paths so the binary is checkout-location-independent) and drive `buildTime` from `SOURCE_DATE_EPOCH`. This raises reproducibility but is not absolute: `git describe --dirty` makes `VERSION` depend on tree state, so only a clean checkout with a fixed toolchain is bit-for-bit reproducible.
- **[C]** Pin tool versions in `install-tools` — an unpinned tool makes CI non-reproducible and can change verdicts between runs.

### Safety
- **[C]** Fail early with clear tool-presence checks (`command -v <tool>`) for optional dependencies — a missing tool must stop the target, not be skipped.
- **[C]** `ci` must mirror the actual CI pipeline. A local `ci` that runs a *different* set gives false confidence; mirror what the pipeline runs, not what this template prefers.
- **[D]** Check for code generation staleness (`generate-check`) when `go generate` is used.

## Go Version Awareness

Read `go.mod` for the `go` directive before composing the Makefile. Record as `Go version: X.Y` in the output report.

| Go Version | Makefile Impact |
|-----------|-----------------|
| < 1.16 | `go install` does not support `pkg@version`; use `go get` for tool installation |
| ≥ 1.18 | Go workspaces (`go.work`) and fuzzing (`go test -fuzz`) available |
| ≥ 1.20 | `go build -cover` + `GOCOVERDIR` enable whole-program / integration coverage; consider a `cover-integration` target |
| ≥ 1.21 | `go.mod` `toolchain` directive (automatic toolchain selection); built-in `min`/`max`/`clear` |
| ≥ 1.22 | Per-iteration loop variable semantics; no Makefile impact but note in output |

If `go.mod` is not found or not readable, record `Go version: unknown` and use conservative defaults (no version-specific features).

## Monorepo Support

When the repo is a Go workspace or multi-module layout (step 1 Inspect), adapt for monorepo:

- **Detect via the toolchain, not a bare file search**: prefer `go.work` (`go env GOWORK`); when it exists, the modules are its `use` directives (`go list -m` run inside the workspace). Only fall back to searching for `go.mod` files when there is no `go.work`, and then exclude `vendor/`, `testdata/`, `examples/`, and tool-only modules.
- **Per-module targets**: generate `test-<module>`, `lint-<module>`, `build-<module>` for each module that has entrypoints
- **Aggregate targets**: `test-all`, `lint-all`, `build-all` that iterate over the workspace modules
- **Per-module `go mod tidy`**: `tidy` operates on a single main module — run it inside each module (`for m in $(MODULES); do (cd $$m && go mod tidy); done`), never once at the workspace root
- **Root Makefile pattern**:

```make
# `go env GOWORK` has THREE answers, not two: a path (workspace active), the
# empty string (no go.work), and the literal string `off` (workspace mode
# disabled via GOWORK=off or -workfile=off). `off` is the trap — it is
# non-empty, so testing emptiness alone reads it as a workspace path and asks
# `go list -m`, which then answers for whichever single module the cwd is in,
# or for NOTHING AT ALL in a monorepo with no root go.mod. Filtering `off` out
# collapses it into the "no workspace" case, where the file search finds every
# module regardless.
GOWORK    := $(shell go env GOWORK 2>/dev/null)
WORKSPACE := $(filter-out off,$(strip $(GOWORK)))

ifeq ($(WORKSPACE),)
# SCOPED go.mod search — a bare search sweeps in vendor/testdata/examples.
MODULES := $(shell find . -name go.mod -type f 2>/dev/null | \
             grep -Ev '(^|/)(vendor|testdata|examples?)(/|$$)' | \
             sed 's|/go\.mod$$||; s|^\./||' | LC_ALL=C sort -u)
else
MODULES := $(shell go list -m -f '{{.Dir}}' 2>/dev/null)
endif

# Zero modules is never a legitimate answer — every Go repo has at least one
# go.mod — so each aggregate target below opens with the same guard. Without
# it the loop iterates zero times and exits 0, and a broken module list reads
# as "all modules pass". The guard is repeated rather than factored into a
# prerequisite target on purpose: these recipes get copied one at a time, and a
# fragment whose safety lives in a sibling target arrives without it. It is
# also not `$(error)`, which would fire at parse time and break `make help`.

test-all: ## Run tests for all modules
	@test -n "$(strip $(MODULES))" || { echo "no Go modules found — check the go.work / go.mod layout"; exit 1; }
	@for mod in $(MODULES); do \
		echo "=== testing $$mod ==="; \
		(cd $$mod && go test -race ./...) || exit 1; \
	done

lint-all: ## Lint all modules
	@test -n "$(strip $(MODULES))" || { echo "no Go modules found — check the go.work / go.mod layout"; exit 1; }
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
- No race testing at all — the default `test` should use `-race`; provide `test-norace` (full suite, no race) as the cgo-off / unsupported-platform equivalent. `test-short` runs a smaller quick set and is not a substitute.
- No `-ldflags` version injection in `build-*` targets **of a program that has no version mechanism of its own** (a library, or a repo that already stamps versions another way, is not a defect here)

**Naming and layout:**
- Target names not matching `cmd/` path semantics (e.g., `cmd/consumer/sync` but target is `build-sync` instead of `build-consumer-sync`)
- `run-*` targets leaving ad-hoc binaries in source directories instead of `bin/`

**Reproducibility:**
- `install-tools` using `@latest` for all tools in CI (pin specific versions for reproducibility; `@latest` is acceptable only for local dev convenience)
- Hardcoding a tool version without discovering the repo's existing pin — check CI workflows, `.golangci.version` / `.tool-versions` (asdf/mise), and any existing `install-tools` first; use a current compatible version (golangci-lint is now v2, module path `.../v2/cmd/golangci-lint`) and prefer the tool's official installer where it documents one (`go install` from source is explicitly not guaranteed for golangci-lint)
- `ci` target that diverges from the actual CI pipeline — `make ci` should mirror CI exactly
- Hidden assumptions about local paths or OS-specific tools (e.g., `sed -i` without considering macOS vs GNU differences)

**Cross-compilation:**
- Cross-compiling a **pure-Go** binary without `CGO_ENABLED=0` — produces dynamically linked binaries that fail on target machines (cgo projects instead need `CGO_ENABLED=1` and a cross C toolchain)
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
→ Run this skill's discovery script against the target repo first — `bash <skill-dir>/scripts/discover_go_entrypoints.sh <project-root>` — to locate every `package main` and infer project shape (library-only vs single-binary vs multi-binary). Check the `confidence` column before turning a row into a target. Add `--modules` to list workspace/multi-module directories; it exits 3 rather than printing an empty list, because zero modules means discovery broke, not that there is nothing to build.

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
✓ ./bin/api --version — version=v0.1.0-dirty commit=abc1234 buildTime=… (injection reached the artifact)
```

## Self-Validation

Run `scripts/run_regression.sh` to verify skill integrity:
- **Contract tests**: structure of SKILL.md, quality guide, golden examples, discovery script
- **Golden review tests**: all defect/FP fixtures' rules covered in docs
- **Coverage matrix**: see `scripts/tests/COVERAGE.md`

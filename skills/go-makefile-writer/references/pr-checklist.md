# Makefile PR Checklist

Use this checklist for quick and reliable review of Makefile PRs.

## 1) Scope and Intent
- PR description clearly states what changed and why.
- New/removed/renamed targets are explicitly listed.
- Breaking changes are called out.

## 2) Repository Mapping
- Targets map to real `package main` directories, verified with
  `go list -f '{{if eq .Name "main"}}{{.Dir}}{{end}}' ./...` rather than by
  filename. A file called `main.go` may declare any package, a program's file
  may be called anything, and programs exist outside `cmd/`.
- Every module is covered. `go list ./...` never crosses a module boundary, so
  in a multi-module repo the root module's answer is complete only for the root
  module — ask each module, or a nested program silently has no target.
- Naming follows `cmd/<kind>/<name>` → `build-<kind>-<name>` convention.
- No stale targets pointing to deleted paths.

## 3) Backward Compatibility
- Existing widely used targets are preserved when possible.
- Renamed targets provide compatibility aliases.
- Any intentional removals are documented with migration notes.

## 4) Target Quality
- `.PHONY` includes non-file targets.
- `help` output is self-documenting and readable.
- Repeated paths/commands use variables (`GO`, `BIN_DIR`, `LDFLAGS`, etc.).
- Optional tools (`golangci-lint`, `swag`) fail with clear messages when missing.
- Build targets inject version/commit/buildTime via `-ldflags` — **if the project has a binary and no version mechanism of its own**. A library-only repo, or one that already stamps versions elsewhere, is not missing anything here.
- `version` target exists and prints injected variables (**programs only**).
- Tool versions are pinned (not `@latest`) for CI reproducibility.

## 4b) Error propagation — check these by running them, not by reading them

A target that exits 0 when its work failed turns CI green on a broken tree, and
every item below shipped in this skill's own templates until 2026-09-09. Verify
each by making it fail on purpose:

- **Checks branch on exit status, not just output.** Put a file that does not
  parse in the tree and run `make fmt-check`: it must fail. `gofmt -l` prints
  the parse error to stderr, nothing to stdout, and exits 2, so an
  output-only check passes a tree that does not compile.
- **No unguarded pipelines.** Either `SHELL := bash` with
  `.SHELLFLAGS := -euo pipefail -c`, or no recipe pipes a fallible producer into
  a consumer. `curl … | sh` reports only `sh`'s status.
- **Loops stop at the first failure.** `|| exit 1` in the body, or an
  accumulator checked after the loop. Break the *first* item and confirm the
  target fails.
- **Staleness checks compare content.** Have the generator rewrite an
  already-untracked file and confirm `make generate-check` fails; a
  status-string comparison cannot see it.
- **Aggregates fail on an empty list.** An empty module or entrypoint list means
  discovery broke, not that there was nothing to do.
- **`go env GOWORK` is handled in all three of its states.** It prints a path, or
  the empty string, or the literal string `off`. `off` is non-empty, so a bare
  emptiness test reads it as a workspace path and asks `go list -m`, which in a
  monorepo with no root `go.mod` answers with nothing at all.
- **A loop body does not end on a test.** `[ -f "$$f" ] && echo …` as the last
  command makes the loop's status that test's. Put a pre-existing deletion in
  the tree — `git ls-files --modified` lists deleted files — and confirm the
  check still passes when the generator changed nothing.
- **A check that could not run has not passed.** Break the tool on purpose
  (a bogus `GOFLAGS`, an unreadable cache) and confirm the result is
  distinguishable from a clean pass, by exit code and not only by a log line.
- **The same recipe in two places behaves the same way.** When a repo keeps a
  Makefile fragment in more than one file — a template plus a doc, a root plus a
  per-service copy — run the failure case against *each* copy. A fix applied to
  one of them leaves the others shipping the defect.

## 5) Safety and Reproducibility
- No machine-specific absolute paths.
- Commands are deterministic across local and CI.
- `run-*` targets do not pollute source directories with ad hoc binaries.
- Cleanup behavior is explicit (`clean` removes known artifacts only).
- Pure-Go cross-compilation uses `CGO_ENABLED=0` for static binaries; cgo builds keep `CGO_ENABLED=1` with a cross toolchain.

## 6) Test and Quality Parity
- `test` target uses `-race` by default (a race-free variant is provided for cgo-off / unsupported platforms).
- `lint` target matches team standard.
- Coverage target behavior is clear (`cover`, optional `cover-check` threshold).
- `ci` target combines fmt-check + lint + test + cover-check and mirrors actual CI pipeline.
- `generate-check` target verifies generated code is not stale (if applicable).
- `tidy` target runs `go mod tidy` + `go mod verify` (if present).

## 7) Container and Cross-Compile (if applicable)
- `docker-build` passes `VERSION`/`COMMIT` as build args.
- Image name/tag use overridable variables (`IMAGE_NAME`, `IMAGE_TAG`).
- Cross-compile targets use `GOOS`/`GOARCH` variables, not hardcoded values.
- `PLATFORMS` variable is overridable for different deployment targets.

## 8) Tool Management
- `install-tools` target exists to bootstrap development environment.
- `check-tools` points to `install-tools` in error messages.
- Tool versions pinned in CI context (not `@latest`).

## 9) Validation Evidence
Minimum evidence:
- `make help`
- `make test`
- one representative `build-*`, then run the built binary's `--version` (confirms `-ldflags` injection reached the artifact — `make version` only echoes the Make variables)

Recommended evidence:
- `make lint`
- `make ci`
- one representative `run-*` in a safe environment
- `make cover` or `make cover-check`
- `make generate-check` (if code generation exists)

## 10) Review Output Standard
- Findings are prioritized (High → Medium → Low).
- Each finding has: `location + impact + evidence + recommendation`.
- If no issues: explicitly state "No actionable findings found" and list residual risks.
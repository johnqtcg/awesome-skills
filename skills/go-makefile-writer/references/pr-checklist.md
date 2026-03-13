# Makefile PR Checklist

Use this checklist for quick and reliable review of Makefile PRs.

## 1) Scope and Intent
- PR description clearly states what changed and why.
- New/removed/renamed targets are explicitly listed.
- Breaking changes are called out.

## 2) Repository Mapping
- Targets map correctly to real entrypoints under `cmd/**/main.go`.
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
- Build targets inject version/commit/buildTime via `-ldflags`.
- `version` target exists and prints injected variables.
- Tool versions are pinned (not `@latest`) for CI reproducibility.

## 5) Safety and Reproducibility
- No machine-specific absolute paths.
- Commands are deterministic across local and CI.
- `run-*` targets do not pollute source directories with ad hoc binaries.
- Cleanup behavior is explicit (`clean` removes known artifacts only).
- Cross-compilation uses `CGO_ENABLED=0` for static binaries.

## 6) Test and Quality Parity
- `test` target includes `-race` flag.
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
- one representative `build-*`
- `make version`

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
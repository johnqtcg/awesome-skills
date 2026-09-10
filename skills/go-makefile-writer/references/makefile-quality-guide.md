# Go Makefile Quality Guide

## 1. Target Set

Recommended baseline:
- `help`
- `fmt`, `fmt-check`
- `tidy`
- `test`
- `cover`, `cover-check`
- `lint`
- `version`
- `ci`
- `clean`
- `swagger` (optional)
- `generate`, `generate-check` (when `go generate` or protobuf/wire/mockgen detected)
- `build-all` plus per-binary build targets (with `-ldflags` version injection)
- per-binary `run-*` targets
- `install-tools`, `check-tools`

Optional high-value additions:
- `test-integration` (integration tests with build tag)
- `bench` (benchmarks)
- `docker-build`, `docker-push` (when Dockerfile present)
- `build-linux`, `build-all-platforms` (when cross-platform deployment needed)

## 2. Naming Convention

Map `cmd/` directory structure to target names:
- `cmd/api/main.go` → `build-api`, `run-api`
- `cmd/<kind>/<name>/main.go` → `build-<kind>-<name>`, `run-<kind>-<name>`
- `cmd/<name>/main.go` → `build-<name>`, `run-<name>`

Keep lowercase with hyphens and no surprises.

## 3. Help Pattern

Use self-documenting help comments:

```make
help: ## Show available targets
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_-]+:.*##/ {printf "%-34s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
```

## 4. Build and Run Patterns

Stamp binaries with version metadata. Drive the timestamp from the commit (or `SOURCE_DATE_EPOCH`) rather than a wall-clock `date`, so the stamp is stable across rebuilds. This is **one input** to reproducibility, not a guarantee of it: byte-for-byte identical binaries also need `-trimpath` (strips local filesystem paths so the build is checkout-location-independent), a fixed toolchain version, and a clean tree. Note that `VERSION` from `git describe --dirty` varies with working-tree state, so a dirty tree is inherently non-reproducible — treat this as *"more reproducible under a fixed checkout + toolchain + SOURCE_DATE_EPOCH"*, not an absolute. Two flag caveats: `-X importpath.name` sets an **existing** package-level string var only (`-X main.version` assumes `var version string` in package `main` — discover the real import path first, a wrong one silently no-ops), and `-s -w` strips the symbol table/DWARF (release builds only). `make version` prints the *Make* variables, not what the binary embeds — verify injection by running the built binary's `--version`.

```make
GO         := go
BIN_DIR    := bin
VERSION    ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
COMMIT     := $(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")
SOURCE_DATE_EPOCH ?= $(shell git log -1 --format=%ct 2>/dev/null || date +%s)
BUILD_TIME := $(shell date -u -d "@$(SOURCE_DATE_EPOCH)" '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u -r "$(SOURCE_DATE_EPOCH)" '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u '+%Y-%m-%dT%H:%M:%SZ')
LDFLAGS    := $(if $(DEBUG),,-s -w) -X main.version=$(VERSION) -X main.commit=$(COMMIT) -X main.buildTime=$(BUILD_TIME)   # DEBUG=1 keeps symbols/DWARF for a debug build
BUILD_FLAGS := -trimpath -ldflags "$(LDFLAGS)"   # -trimpath makes the build checkout-location-independent

build-api: ## Build API binary
	@mkdir -p $(BIN_DIR)
	$(GO) build $(BUILD_FLAGS) -o $(BIN_DIR)/api ./cmd/api

version: ## Print version variables
	@echo "version=$(VERSION) commit=$(COMMIT) build_time=$(BUILD_TIME)"
```

Run patterns:
- Option A: build then run from `bin/`.
- Option B: `go run ./cmd/...` for cleaner working tree.
- Avoid leaving ad hoc binaries in source directories.

## 5. Quality Targets

```make
fmt: ## Format Go source files
	$(GO) fmt ./...

tidy: ## Tidy and verify module dependencies
	$(GO) mod tidy
	$(GO) mod verify

test: ## Run all tests with race detection
	$(GO) test -race ./...

test-norace: ## Full test suite without -race — the race-free equivalent for cgo-off / unsupported platforms
	$(GO) test ./...

test-short: ## Quick tests only — skips testing.Short()-gated cases (a smaller set, NOT a race-free equivalent)
	$(GO) test -short ./...

cover: ## Run tests with coverage report
	$(GO) test -race -coverprofile=coverage.out ./...
	$(GO) tool cover -func=coverage.out | tail -n 1

lint: ## Run golangci-lint
	@command -v golangci-lint >/dev/null || (echo "golangci-lint not found; run 'make install-tools'" && exit 1)
	golangci-lint run
```

> **Why `go fmt ./...` instead of `gofmt -w $(git ls-files)`?**
> `go fmt ./...` works consistently in CI containers without a `.git` directory, uses the module-aware formatter, and avoids shell quoting issues with filenames.
> If you need fine-grained control (e.g., formatting only staged files), `gofmt -w $(git ls-files '*.go')` is acceptable but add a git-availability guard.

Coverage gate example:

```make
COVER_MIN ?= 80
cover-check: cover ## Fail if coverage below threshold
	@total=$$($(GO) tool cover -func=coverage.out | awk '/^total:/ {print $$3}' | tr -d '%'); \
	if [ "$$(echo "$$total < $(COVER_MIN)" | bc -l 2>/dev/null || echo 1)" = "1" ]; then \
		echo "coverage $${total}% < $(COVER_MIN)%"; exit 1; \
	fi
```

> **Compatibility note**: The `bc` command is available on Linux and macOS. For Alpine-based CI images, install `bc` or use an awk-only variant:
> ```make
> @awk -v p="$$total" -v m="$(COVER_MIN)" 'BEGIN { if (p+0 < m+0) { printf "coverage %.1f%% < %d%%\n", p, m; exit 1 } }'
> ```

## 6. Integration Tests and Benchmarks

```make
test-integration: ## Run integration tests (requires build tag)
	$(GO) test -race -tags=integration ./...

bench: ## Run benchmarks
	$(GO) test -bench=. -benchmem ./...
```

## 7. CI and Formatting Gate

```make
ci: fmt-check lint test cover-check ## Run full CI pipeline locally

fmt-check: ## Check formatting (no write); fails on unformatted OR unparsable files
	@out=$$(gofmt -l . 2>&1); status=$$?; \
	if [ $$status -ne 0 ]; then \
		echo "gofmt could not parse the tree (exit $$status):"; echo "$$out"; exit $$status; \
	fi; \
	if [ -n "$$out" ]; then \
		echo "gofmt needed on:"; echo "$$out"; exit 1; \
	fi
```

> `gofmt -l .` recursively checks all `.go` files under the current directory without needing git. This works identically in CI containers and local dev.
>
> **Check gofmt's exit status, not only its output.** On a file that does not
> parse, `gofmt -l` prints the error to **stderr**, prints **nothing** on stdout,
> and exits **2**. A recipe written as `test -z "$(gofmt -l .)"` therefore passes
> a tree that does not even compile: the status is discarded and the empty stdout
> reads as "everything is formatted". Capture both, and branch on the status
> first. This is the general shape — any check that inspects a tool's output must
> also check whether the tool succeeded.

The `ci` target should mirror CI exactly so developers catch issues before push.

## 8. Code Generation

```make
generate: ## Run go generate
	$(GO) generate ./...

generate-check: ## Verify generated code is up to date (fails on codegen error; ignores unrelated pre-existing dirt)
	@set -e; \
	snapshot() { \
		git status --porcelain; \
		git diff; \
		git ls-files --modified --others --exclude-standard | LC_ALL=C sort | \
			while IFS= read -r f; do \
				if [ -f "$$f" ]; then echo "$$f $$(git hash-object "$$f")"; fi; \
			done; \
	}; \
	before="$$(snapshot)"; \
	$(MAKE) generate >/dev/null; \
	after="$$(snapshot)"; \
	if [ "$$before" != "$$after" ]; then \
		echo "generated code is stale — run 'make generate' and commit the result:"; \
		git status --porcelain; \
		echo "(files whose contents changed are listed above, or were untracked)"; \
		exit 1; \
	fi
```

> **Use `if`, not `[ -f … ] && …`, as the loop body's last command.**
> `git ls-files --modified` lists **deleted** files too, so `[ -f "$$f" ]` is
> false for them; as the last command in the loop body that makes the whole
> `while` — and therefore the pipeline, and therefore the snapshot function —
> exit non-zero, which `set -e` turns into a failed check. A repo with one
> pre-existing deletion then reports stale codegen no matter what the generator
> did. The deletion itself is still caught: `git status --porcelain` prints
> ` D path` in both snapshots, and a deletion the generator *causes* shows up
> as a difference between them.
>
> **Snapshot the contents, not just `git status`.** `git status --porcelain`
> prints the same `?? path` line no matter what an untracked file *contains*,
> and `git diff` skips untracked files entirely. So a generator that rewrites a
> file which was already untracked — the normal state of generated output in a
> repo that gitignores it, and of any first run — produces two byte-identical
> snapshots and the check passes. Hashing every modified-or-untracked file is
> what makes the comparison see content. `git hash-object` is used rather than
> `sha1sum`/`shasum` because those two are not both present on every platform,
> while git already is (this target cannot run without it).

Add `generate` as a prerequisite of `build-all` when generated code exists.

## 9. Container Targets

```make
IMAGE_NAME  ?= $(shell basename $(CURDIR))
IMAGE_TAG   ?= $(VERSION)

docker-build: ## Build Docker image
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) \
		--build-arg VERSION=$(VERSION) --build-arg COMMIT=$(COMMIT) .

docker-push: ## Push Docker image
	docker push $(IMAGE_NAME):$(IMAGE_TAG)
```

Ensure the Dockerfile uses `CGO_ENABLED=0` for static binaries when building inside containers.

## 10. Cross-Compilation

### Single-binary project

```make
PLATFORMS ?= linux/amd64 linux/arm64 darwin/amd64 darwin/arm64

build-linux: ## Build for Linux amd64 (static)
	@mkdir -p $(BIN_DIR)
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 $(GO) build -ldflags "$(LDFLAGS)" \
		-o $(BIN_DIR)/api-linux-amd64 ./cmd/api

build-all-platforms: ## Build for all target platforms
	@mkdir -p $(BIN_DIR)
	@for platform in $(PLATFORMS); do \
		os=$${platform%/*}; arch=$${platform#*/}; \
		echo "Building $$os/$$arch..."; \
		CGO_ENABLED=0 GOOS=$$os GOARCH=$$arch $(GO) build -ldflags "$(LDFLAGS)" \
			-o $(BIN_DIR)/api-$$os-$$arch ./cmd/api || exit 1; \
	done
```

### Multi-binary project

For projects with multiple entrypoints, list them in a variable and loop:

**Prefer explicit per-binary targets** — see the [complex-project golden
example](golden/complex-project.mk). They are easier to read, to debug, and to
run one at a time, and each gets its own exit status for free.

If you do need a loop (many entrypoints, generated target lists), pair the name
and the directory in **one** variable so the two can never drift apart, and make
the loop stop at the first failure:

```make
# name:dir pairs — one token per binary keeps the two halves in lockstep.
# `scripts/discover_go_entrypoints.sh` emits this list.
BINARIES := api:cmd/api consumer-sync:cmd/consumer/sync cron-cleanup:cmd/cron/cleanup migrate:cmd/migrate

build-linux: ## Build all binaries for Linux amd64 (static)
	@mkdir -p $(BIN_DIR)
	@for pair in $(BINARIES); do \
		name=$${pair%%:*}; dir=$${pair#*:}; \
		echo "Building $$name from $$dir..."; \
		CGO_ENABLED=0 GOOS=linux GOARCH=amd64 $(GO) build -ldflags "$(LDFLAGS)" \
			-o $(BIN_DIR)/$$name-linux-amd64 "./$$dir" || exit 1; \
	done
```

Two things this gets right that a naive loop does not. **`|| exit 1` inside the
body**: without it the loop runs to completion and the target's status is only
the *last* iteration's, so a broken first binary is masked by a working second
one. **Paired tokens**: two parallel lists (`ENTRYPOINTS` + `ENTRYPOINT_DIRS`)
have to be indexed in step, which POSIX `sh` cannot do cleanly — attempts to
fake it with `head -n 1` silently build the same directory every time.

Use `scripts/discover_go_entrypoints.sh` to auto-discover entrypoints and generate the target list.

## 11. Tool Installation

Pin versions for CI reproducibility. Use `@latest` only in local development convenience targets.

Tool-version strategy, in order:
1. **Discover an existing pin first** — a CI workflow (`.github/workflows/*`), `.golangci.version`, or `.tool-versions` (asdf/mise). Match it; do not invent a version.
2. **golangci-lint is now v2** — module path `github.com/golangci/golangci-lint/v2/cmd/golangci-lint`. It tracks only the **two most recent Go minor releases**, so a stale pin can be incompatible with a newer toolchain — keep it current.
3. **Prefer the official binary installer** — golangci-lint's docs state a `go install` from source is *not guaranteed* to work, so install the released binary. `go install` remains fine for tools that ship no installer (swag, mockgen).

```make
# Discover the repo's pin first; golangci-lint supports only the latest two Go minors.
GOLANGCI_LINT_VERSION ?= v2.12.2
SWAG_VERSION          ?= v1.16.4

install-tools: ## Install pinned dev tools (golangci-lint via its official installer)
	@set -e; \
	script=$$(mktemp); trap 'rm -f "$$script"' EXIT; \
	curl -sSfL https://raw.githubusercontent.com/golangci/golangci-lint/HEAD/install.sh -o "$$script"; \
	test -s "$$script" || { echo "installer download produced an empty file"; exit 1; }; \
	sh "$$script" -b $$(go env GOPATH)/bin $(GOLANGCI_LINT_VERSION)
	go install github.com/swaggo/swag/cmd/swag@$(SWAG_VERSION)

check-tools: ## Verify required tools are installed
	@command -v golangci-lint >/dev/null || \
		(echo "golangci-lint not found; run 'make install-tools'" && exit 1)
```

## 12. Robustness Rules

- Define `.PHONY` for non-file targets.
- Use variables for repeated commands and paths.
- Check optional tool presence with clear errors.
- Keep shell fragments short and readable.
- Keep commands reproducible across local and CI.

## 13. Anti-Patterns

- Target names not matching `cmd` layout.
- `run-*` leaving binaries around without cleanup.
- Hidden assumptions about local paths or OS-specific tools.
- Overly dynamic Make metaprogramming that reduces readability.
- Missing `help` descriptions.
- Build targets without `-ldflags` version injection.
- `ci` target that diverges from actual CI pipeline.
- Generated code not checked for staleness before build.
- Hardcoded `GOOS/GOARCH` without variable override.
- `install-tools` using unpinned `@latest` in production CI (pin versions for reproducibility).
- Test targets missing `-race` entirely — the default `test` should use it. Provide `test-norace` (`go test ./...`, full suite, no race) as the race-free equivalent for cgo-off / unsupported platforms; `test-short` is a *smaller* quick set, not a substitute for it.
- Pure-Go cross-compilation without `CGO_ENABLED=0` (cgo builds need `CGO_ENABLED=1` + a cross toolchain).

## 14. Validation Matrix

Minimum:
- `make help`
- `make test`
- one `build-*`, then run the built binary's `--version` to confirm the `-X` values reached the artifact (`make version` only echoes the Make variables, not what the binary embeds)

Recommended:
- `make lint`
- `make ci`
- one `run-*` in a safe environment
- `make cover` or `make cover-check`
- `make generate-check` (if code generation exists)

## 15. Backward Compatibility (for Refactors)

- Avoid removing existing targets unless explicitly requested.
- If renaming a target, keep a compatibility alias for at least one transition period.
- Preserve commonly used entry points (for example: `build`, `test`, `lint`, `clean`) unless there is a strong reason not to.
- Document any intentional breaking changes in the output summary.
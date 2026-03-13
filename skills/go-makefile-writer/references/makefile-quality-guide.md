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

Prefer deterministic binary output with version injection:

```make
GO         := go
BIN_DIR    := bin
VERSION    ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
COMMIT     := $(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")
BUILD_TIME := $(shell date -u '+%Y-%m-%dT%H:%M:%SZ')
LDFLAGS    := -s -w -X main.version=$(VERSION) -X main.commit=$(COMMIT) -X main.buildTime=$(BUILD_TIME)

build-api: ## Build API binary
	@mkdir -p $(BIN_DIR)
	$(GO) build -ldflags "$(LDFLAGS)" -o $(BIN_DIR)/api ./cmd/api

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

fmt-check: ## Check formatting (no write)
	@test -z "$$(gofmt -l .)" || \
		(echo "gofmt needed on:" && gofmt -l . && exit 1)
```

> `gofmt -l .` recursively checks all `.go` files under the current directory without needing git. This works identically in CI containers and local dev.

The `ci` target should mirror CI exactly so developers catch issues before push.

## 8. Code Generation

```make
generate: ## Run go generate
	$(GO) generate ./...

generate-check: generate ## Verify generated code is up to date
	@git diff --exit-code || (echo "generated code is stale; run 'make generate' and commit" && exit 1)
```

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
			-o $(BIN_DIR)/api-$$os-$$arch ./cmd/api; \
	done
```

### Multi-binary project

For projects with multiple entrypoints, list them in a variable and loop:

```make
# All entrypoints discovered from cmd/
ENTRYPOINTS := api consumer-sync cron-cleanup migrate
ENTRYPOINT_DIRS := cmd/api cmd/consumer/sync cmd/cron/cleanup cmd/migrate

build-linux: ## Build all binaries for Linux amd64 (static)
	@mkdir -p $(BIN_DIR)
	@set -- $(ENTRYPOINTS); dirs="$(ENTRYPOINT_DIRS)"; set_dirs=$$dirs; \
	for entry in $(ENTRYPOINTS); do \
		dir=$$(echo "$(ENTRYPOINT_DIRS)" | tr ' ' '\n' | head -n 1); \
		echo "TODO: replace with per-binary explicit targets for clarity"; \
	done
```

> **Recommended**: For multi-binary projects, prefer explicit per-binary targets (see [complex-project golden example](golden/complex-project.mk)) over dynamic loops. Explicit targets are easier to read, debug, and run individually.

Use `scripts/discover_go_entrypoints.sh` to auto-discover entrypoints and generate the target list.

## 11. Tool Installation

Pin versions for CI reproducibility. Use `@latest` only in local development convenience targets:

```make
# Pinned versions for reproducible CI
GOLANGCI_LINT_VERSION ?= v1.62.2
SWAG_VERSION          ?= v1.16.4

install-tools: ## Install required development tools
	go install github.com/golangci/golangci-lint/cmd/golangci-lint@$(GOLANGCI_LINT_VERSION)
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
- Test targets missing `-race` flag.
- Cross-compilation without `CGO_ENABLED=0`.

## 14. Validation Matrix

Minimum:
- `make help`
- `make test`
- one `build-*`
- `make version` (verify version injection)

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
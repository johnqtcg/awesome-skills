# Makefile for example.com/single
#
# Layout:
#   main.go            package main (entrypoint, builds to bin/single)
#   internal/calc/     library packages
#
# Tools: golangci-lint (optional, installed via `make install-tools`)

.DEFAULT_GOAL := help

# Make runs each recipe line in /bin/sh, where a pipeline's exit status is only
# its LAST command's -- so `curl ... | sh` reports success even when the
# download failed with nothing to pipe. `pipefail` makes the pipeline fail if
# any stage does; `-u` catches typo'd variables.
SHELL       := bash
.SHELLFLAGS := -euo pipefail -c

GO       := go
BIN_DIR  := bin
BINARY   := single
PKG      := .

VERSION           ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
COMMIT            := $(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")
SOURCE_DATE_EPOCH ?= $(shell git log -1 --format=%ct 2>/dev/null || date +%s)
BUILD_TIME        := $(shell date -u -d "@$(SOURCE_DATE_EPOCH)" '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u -r "$(SOURCE_DATE_EPOCH)" '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u '+%Y-%m-%dT%H:%M:%SZ')

# -X only assigns to an EXISTING package-level string var; a name that does not
# exist is silently ignored. package main currently declares only `version`
# (main.go), so that is the only var injected. To embed the other two, add
#     var commit, buildTime string
# to package main and uncomment the lines below.
LDFLAGS := $(if $(DEBUG),,-s -w) \
	-X main.version=$(VERSION)
#	-X main.commit=$(COMMIT) \
#	-X main.buildTime=$(BUILD_TIME)

# -trimpath strips local filesystem paths so identical source builds identically
# regardless of checkout location (one requirement for reproducible binaries).
BUILD_FLAGS := -trimpath -ldflags "$(LDFLAGS)"

# Pinned for CI reproducibility; matches the golangci-lint already on this
# machine. Installed via the official installer -- its docs state `go install`
# from source is not guaranteed to work.
GOLANGCI_LINT_VERSION ?= v2.6.2

# ---------- build ----------

build-single: ## Build the single binary into bin/
	@mkdir -p $(BIN_DIR)
	$(GO) build $(BUILD_FLAGS) -o $(BIN_DIR)/$(BINARY) $(PKG)

build-all: build-single ## Build all binaries

# ---------- run ----------

run-single: build-single ## Build and run the binary from bin/
	./$(BIN_DIR)/$(BINARY)

# ---------- quality ----------

fmt: ## Format Go source files
	$(GO) fmt ./...

fmt-check: ## Check formatting (no write); fails on unformatted OR unparsable files
	@out=$$(gofmt -l . 2>&1); status=$$?; \
	if [ $$status -ne 0 ]; then \
		echo "gofmt could not parse the tree (exit $$status):"; echo "$$out"; exit $$status; \
	fi; \
	if [ -n "$$out" ]; then \
		echo "gofmt needed on:"; echo "$$out"; exit 1; \
	fi

tidy: ## Tidy and verify module dependencies
	$(GO) mod tidy
	$(GO) mod verify

test: ## Run all tests with race detection
	$(GO) test -race ./...

test-norace: ## Run the full test suite without -race (cgo-off / platforms without race support)
	$(GO) test ./...

test-short: ## Run only quick tests (skips testing.Short()-gated cases; NOT a race-free equivalent)
	$(GO) test -short ./...

COVER_MIN ?= 50
cover: ## Run tests with coverage report
	$(GO) test -race -coverprofile=coverage.out ./...
	$(GO) tool cover -func=coverage.out | tail -n 1

cover-check: cover ## Fail if total coverage is below COVER_MIN
	@total=$$($(GO) tool cover -func=coverage.out | awk '/^total:/ {print $$3}' | tr -d '%'); \
	if [ -z "$$total" ]; then echo "could not read coverage total"; exit 1; fi; \
	if [ "$$(echo "$$total < $(COVER_MIN)" | bc -l 2>/dev/null || echo 1)" = "1" ]; then \
		echo "coverage $${total}% < $(COVER_MIN)%"; exit 1; \
	fi; \
	echo "coverage $${total}% >= $(COVER_MIN)%"

lint: ## Run golangci-lint
	@command -v golangci-lint >/dev/null || \
		(echo "golangci-lint not found; run 'make install-tools'" && exit 1)
	golangci-lint run

# ---------- ci ----------

ci: fmt-check lint test cover-check ## Run the full check suite locally

# ---------- version ----------

version: ## Print the version metadata this build would inject
	@echo "version=$(VERSION)   (embedded via -ldflags)"
	@echo "commit=$(COMMIT)   build_time=$(BUILD_TIME)   (not embedded; see LDFLAGS)"

# ---------- tools ----------

install-tools: ## Install pinned dev tools (golangci-lint via its official installer)
	@set -e; \
	script=$$(mktemp); trap 'rm -f "$$script"' EXIT; \
	curl -sSfL https://raw.githubusercontent.com/golangci/golangci-lint/HEAD/install.sh -o "$$script"; \
	test -s "$$script" || { echo "installer download produced an empty file"; exit 1; }; \
	sh "$$script" -b $$($(GO) env GOPATH)/bin $(GOLANGCI_LINT_VERSION)

check-tools: ## Verify required tools are installed
	@command -v golangci-lint >/dev/null || \
		(echo "golangci-lint not found; run 'make install-tools'" && exit 1)
	@echo "all tools present"

# ---------- clean ----------

clean: ## Remove build artifacts
	rm -rf $(BIN_DIR) coverage.out

# ---------- phony ----------

.PHONY: help build-single build-all run-single \
	fmt fmt-check tidy test test-norace test-short cover cover-check lint \
	ci version install-tools check-tools clean

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_-]+:.*##/ {printf "%-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

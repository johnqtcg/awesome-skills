# Makefile for example.com/legacy
#
# CI (.github/workflows/ci.yml) runs `make unit`, `make vet` and `make compile`,
# so those keep their names and stay the canonical entry points. `test`,
# `build-all` and `clean` are aliases for the conventional Go names.

# A pipeline reports only its LAST command's status, so `go vet ./... | tee`
# exits 0 even when vet fails. The recipes below avoid such pipelines outright;
# pipefail is a safety net for anything added later.
SHELL       := bash
.SHELLFLAGS := -o pipefail -c

GO          := go
OUT         := build
VET_LOG     := vet.log
COVER_OUT   := coverage.out
COVER_MIN   ?= 25

VERSION     ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo dev)
COMMIT      := $(shell git rev-parse --short HEAD 2>/dev/null || echo unknown)

# `-X` assigns to an *existing* package-level string var and silently no-ops
# otherwise. cmd/server declares `var version`; cmd/migrate declares nothing, so
# only the server build carries `-X`. Declare `var commit, buildTime string` in a
# main package to stamp those too. `-s -w` strips symbols/DWARF — DEBUG=1 keeps them.
STRIP           := $(if $(DEBUG),,-s -w)
LDFLAGS_SERVER  := $(STRIP) -X main.version=$(VERSION)
LDFLAGS_MIGRATE := $(STRIP)
BUILD_FLAGS     := -trimpath

GOLANGCI_LINT_VERSION ?= v2.12.2

.DEFAULT_GOAL := help

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_-]+:.*##/ {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

## --- build ---------------------------------------------------------------

compile: build-server build-migrate ## Build every binary into the output dir (used by CI)

build-all: compile ## Alias for `compile`

build-server: ## Build the server binary
	@mkdir -p $(OUT)
	$(GO) build $(BUILD_FLAGS) -ldflags "$(LDFLAGS_SERVER)" -o $(OUT)/server ./cmd/server

build-migrate: ## Build the migrate binary
	@mkdir -p $(OUT)
	$(GO) build $(BUILD_FLAGS) -ldflags "$(LDFLAGS_MIGRATE)" -o $(OUT)/migrate ./cmd/migrate

run-server: build-server ## Build and run the server from the output dir
	@$(OUT)/server

run-migrate: build-migrate ## Build and run migrate from the output dir
	@$(OUT)/migrate

version: ## Print the version variables Make will inject
	@echo "version=$(VERSION) commit=$(COMMIT)"

## --- test ----------------------------------------------------------------

unit: ## Run all tests with the race detector (used by CI)
	$(GO) test -race ./...

test: unit ## Alias for `unit`

test-norace: ## Full test suite without -race (cgo-off / unsupported platforms)
	$(GO) test ./...

test-short: ## Quick tests only — skips testing.Short() cases; NOT a race-free equivalent
	$(GO) test -short ./...

bench: ## Run benchmarks
	$(GO) test -bench=. -benchmem ./...

cover: ## Run tests with a coverage profile
	$(GO) test -race -coverprofile=$(COVER_OUT) ./...
	@$(GO) tool cover -func=$(COVER_OUT) | tail -n 1

cover-check: cover ## Fail if total coverage is below the COVER_MIN threshold
	@total=$$($(GO) tool cover -func=$(COVER_OUT) | awk '/^total:/ {print $$3}' | tr -d '%'); \
	awk -v p="$$total" -v m="$(COVER_MIN)" 'BEGIN { if (p+0 < m+0) { printf "coverage %.1f%% < %d%%\n", p, m; exit 1 } printf "coverage %.1f%% >= %d%%\n", p, m }'

## --- quality -------------------------------------------------------------

vet: ## Run go vet, capturing output in vet.log (used by CI)
	@status=0; $(GO) vet ./... >$(VET_LOG) 2>&1 || status=$$?; \
	cat $(VET_LOG); \
	exit $$status

fmt: ## Format Go source files
	$(GO) fmt ./...

fmt-check: ## Fail on unformatted OR unparsable files
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

lint: check-tools ## Run golangci-lint
	golangci-lint run

## --- tooling -------------------------------------------------------------

install-tools: ## Install pinned dev tools
	@set -e; \
	script=$$(mktemp); trap 'rm -f "$$script"' EXIT; \
	curl -sSfL https://raw.githubusercontent.com/golangci/golangci-lint/HEAD/install.sh -o "$$script"; \
	test -s "$$script" || { echo "installer download produced an empty file"; exit 1; }; \
	sh "$$script" -b $$($(GO) env GOPATH)/bin $(GOLANGCI_LINT_VERSION)

check-tools: ## Verify required tools are installed
	@command -v golangci-lint >/dev/null || \
		{ echo "golangci-lint not found; run 'make install-tools'"; exit 1; }

## --- housekeeping --------------------------------------------------------

ci: unit vet compile ## Mirror .github/workflows/ci.yml exactly

wipe: ## Remove build output and generated logs
	rm -rf $(OUT) $(VET_LOG) $(COVER_OUT)

clean: wipe ## Alias for `wipe`

.PHONY: help compile build-all build-server build-migrate run-server run-migrate \
        version unit test test-norace test-short bench cover cover-check \
        vet fmt fmt-check tidy lint install-tools check-tools ci wipe clean

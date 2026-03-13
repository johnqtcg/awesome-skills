# Golden Makefile — Simple Project
#
# Project layout:
#   cmd/api/main.go
#   internal/...
#   go.mod
#
# Tools: golangci-lint
# No code generation, no Docker, no cross-compile.

.DEFAULT_GOAL := help

GO         := go
BIN_DIR    := bin
VERSION    ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
COMMIT     := $(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")
BUILD_TIME := $(shell date -u '+%Y-%m-%dT%H:%M:%SZ')
LDFLAGS    := -s -w \
	-X main.version=$(VERSION) \
	-X main.commit=$(COMMIT) \
	-X main.buildTime=$(BUILD_TIME)

# Pinned tool versions
GOLANGCI_LINT_VERSION ?= v1.62.2

# ---------- build ----------

build-api: ## Build API binary
	@mkdir -p $(BIN_DIR)
	$(GO) build -ldflags "$(LDFLAGS)" -o $(BIN_DIR)/api ./cmd/api

build-all: build-api ## Build all binaries

# ---------- run ----------

run-api: build-api ## Run API server
	./$(BIN_DIR)/api

# ---------- quality ----------

fmt: ## Format Go source files
	$(GO) fmt ./...

fmt-check: ## Check formatting (no write)
	@test -z "$$(gofmt -l .)" || \
		(echo "gofmt needed on:" && gofmt -l . && exit 1)

tidy: ## Tidy and verify module dependencies
	$(GO) mod tidy
	$(GO) mod verify

test: ## Run all tests with race detection
	$(GO) test -race ./...

COVER_MIN ?= 80
cover: ## Run tests with coverage report
	$(GO) test -race -coverprofile=coverage.out ./...
	$(GO) tool cover -func=coverage.out | tail -n 1

cover-check: cover ## Fail if coverage below threshold
	@total=$$($(GO) tool cover -func=coverage.out | awk '/^total:/ {print $$3}' | tr -d '%'); \
	if [ "$$(echo "$$total < $(COVER_MIN)" | bc -l 2>/dev/null || echo 1)" = "1" ]; then \
		echo "coverage $${total}% < $(COVER_MIN)%"; exit 1; \
	fi

lint: ## Run golangci-lint
	@command -v golangci-lint >/dev/null || \
		(echo "golangci-lint not found; run 'make install-tools'" && exit 1)
	golangci-lint run

# ---------- ci ----------

ci: fmt-check lint test cover-check ## Run full CI pipeline locally

# ---------- version ----------

version: ## Print embedded version info
	@echo "version=$(VERSION) commit=$(COMMIT) build_time=$(BUILD_TIME)"

# ---------- tools ----------

install-tools: ## Install required development tools
	$(GO) install github.com/golangci/golangci-lint/cmd/golangci-lint@$(GOLANGCI_LINT_VERSION)

check-tools: ## Verify required tools are installed
	@command -v golangci-lint >/dev/null || \
		(echo "golangci-lint not found; run 'make install-tools'" && exit 1)

# ---------- clean ----------

clean: ## Remove build artifacts
	rm -rf $(BIN_DIR) coverage.out

# ---------- phony ----------

.PHONY: help build-api build-all run-api \
	fmt fmt-check tidy test cover cover-check lint \
	ci version install-tools check-tools clean

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_-]+:.*##/ {printf "%-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Makefile — example.com/retry
#
# Project layout:
#   retry/            library package (example.com/retry/retry)
#   cmd/internal/     package `internal`, NOT package main
#   go.mod            module example.com/retry, go 1.22
#
# This repo is LIBRARY-ONLY: `go list` reports no `package main` anywhere, so
# there is deliberately no build-*, run-*, or `version` target and no -ldflags
# version injection — there is no binary to produce or stamp. Note that
# cmd/internal/main.go is named main.go but declares `package internal`; a
# filename-based scan would wrongly infer a program here. If a real entrypoint
# is added under cmd/, add build-<name>/run-<name> targets at that point.

.DEFAULT_GOAL := help

# Make runs each recipe line in /bin/sh, where a pipeline's exit status is only
# its LAST command's — so `curl ... | sh` reports success even when the download
# failed with nothing to pipe. `pipefail` makes the pipeline fail if any stage
# does; `-u` catches typo'd variables. Recipes below are also written to be
# correct under a plain POSIX sh, so copying one into a bash-less environment
# degrades diagnostics rather than silently passing.
SHELL       := bash
.SHELLFLAGS := -euo pipefail -c

GO := go

# Coverage floor. Set as a ratchet just under the current 57.1% so `make ci`
# passes on a clean checkout and fails on regression. Raise it as coverage grows.
COVER_MIN ?= 55

# Pinned tool version. This repo has no existing pin (no CI workflow,
# .golangci.version or .tool-versions), so this is the pin of record.
# Installed via the official binary installer below — golangci-lint's docs state
# `go install` from source is not guaranteed to work.
# golangci-lint tracks only the two most recent Go minor releases; keep current.
GOLANGCI_LINT_VERSION ?= v2.12.2

# ---------- quality ----------

fmt: ## Format Go source files
	$(GO) fmt ./...

# `gofmt -l` on a file that does not parse writes to stderr, prints NOTHING on
# stdout and exits 2 — so `test -z "$$(gofmt -l .)"` would pass a broken tree.
# The `if !` form is used because under `set -e` a bare `out=$$(...)` assignment
# aborts the recipe before any `status=$$?` line could run, losing the message.
fmt-check: ## Check formatting (no write); fails on unformatted OR unparsable files
	@if ! out=$$(gofmt -l . 2>&1); then \
		echo "gofmt could not parse the tree:"; echo "$$out"; exit 1; \
	fi; \
	if [ -n "$$out" ]; then \
		echo "gofmt needed on:"; echo "$$out"; exit 1; \
	fi

vet: ## Run go vet
	$(GO) vet ./...

tidy: ## Tidy and verify module dependencies
	$(GO) mod tidy
	$(GO) mod verify

# Hashes contents rather than reading `git status --porcelain`, which prints the
# same `?? path` line however a file's contents change and skips untracked files.
tidy-check: ## Fail if go.mod/go.sum are not tidy (CI drift guard)
	@before=$$(git hash-object go.mod $$(test -f go.sum && echo go.sum || true) 2>/dev/null || true); \
	$(GO) mod tidy; \
	after=$$(git hash-object go.mod $$(test -f go.sum && echo go.sum || true) 2>/dev/null || true); \
	if [ -z "$$before" ] || [ -z "$$after" ]; then \
		echo "could not hash go.mod/go.sum to compare tidiness"; exit 1; \
	fi; \
	if [ "$$before" != "$$after" ]; then \
		echo "go.mod/go.sum are not tidy — run 'make tidy' and commit the result"; exit 1; \
	fi

test: ## Run all tests with race detection
	$(GO) test -race ./...

test-norace: ## Run the full test suite without -race (cgo-off / platforms without race support)
	$(GO) test ./...

test-short: ## Run only quick tests (skips testing.Short()-gated cases; NOT a race-free equivalent)
	$(GO) test -short ./...

bench: ## Run benchmarks
	$(GO) test -run '^$$' -bench . -benchmem ./...

cover: ## Run tests with coverage report
	$(GO) test -race -coverprofile=coverage.out ./...
	$(GO) tool cover -func=coverage.out | tail -n 1

cover-html: cover ## Write an HTML coverage report to coverage.html
	$(GO) tool cover -html=coverage.out -o coverage.html
	@echo "wrote coverage.html"

cover-check: cover ## Fail if coverage below COVER_MIN threshold
	@total=$$($(GO) tool cover -func=coverage.out | awk '/^total:/ {print $$3}' | tr -d '%'); \
	if [ -z "$$total" ]; then \
		echo "could not read a total from coverage.out"; exit 1; \
	fi; \
	if [ "$$(echo "$$total < $(COVER_MIN)" | bc -l 2>/dev/null || echo 1)" = "1" ]; then \
		echo "coverage $${total}% < $(COVER_MIN)%"; exit 1; \
	fi; \
	echo "coverage $${total}% >= $(COVER_MIN)%"

lint: ## Run golangci-lint
	@command -v golangci-lint >/dev/null || \
		{ echo "golangci-lint not found; run 'make install-tools'"; exit 1; }
	golangci-lint run

# ---------- ci ----------

# This repo has no CI pipeline yet (no .github/workflows). When one is added,
# keep it and this target in lockstep — a local `ci` that runs a different set
# than the pipeline gives false confidence.
ci: fmt-check vet lint test cover-check ## Run full CI pipeline locally

# ---------- tools ----------

install-tools: ## Install pinned dev tools (golangci-lint via its official installer)
	@set -e; \
	script=$$(mktemp); trap 'rm -f "$$script"' EXIT; \
	curl -sSfL https://raw.githubusercontent.com/golangci/golangci-lint/HEAD/install.sh -o "$$script"; \
	test -s "$$script" || { echo "installer download produced an empty file"; exit 1; }; \
	sh "$$script" -b $$($(GO) env GOPATH)/bin $(GOLANGCI_LINT_VERSION)

check-tools: ## Verify required tools are installed
	@command -v golangci-lint >/dev/null || \
		{ echo "golangci-lint not found; run 'make install-tools'"; exit 1; }
	@echo "all required tools present"

# ---------- clean ----------

clean: ## Remove generated artifacts
	rm -f coverage.out coverage.html

# ---------- phony ----------

.PHONY: help fmt fmt-check vet tidy tidy-check \
	test test-norace test-short bench \
	cover cover-html cover-check lint \
	ci install-tools check-tools clean

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_-]+:.*##/ {printf "%-16s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

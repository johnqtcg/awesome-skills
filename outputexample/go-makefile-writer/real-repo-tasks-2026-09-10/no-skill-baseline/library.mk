# Makefile for example.com/retry
#
# Run `make` or `make help` for the list of targets.

GO         ?= go
GOFLAGS    ?=
PKGS       ?= ./...
COVERFILE  ?= coverage.out
COVERHTML  ?= coverage.html

# Fail loudly on unset variables and pipeline errors inside recipes.
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

.DEFAULT_GOAL := help

## help: show this help
.PHONY: help
help:
	@echo "Targets:"
	@grep -E '^## [a-z-]+:' $(MAKEFILE_LIST) \
		| sed -e 's/^## //' \
		| awk -F ': *' '{ printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2 }'

## build: compile all packages (no binaries; this module is a library)
.PHONY: build
build:
	$(GO) build $(GOFLAGS) $(PKGS)

## test: run the test suite
.PHONY: test
test:
	$(GO) test $(GOFLAGS) $(PKGS)

## test-race: run the test suite with the race detector
.PHONY: test-race
test-race:
	$(GO) test $(GOFLAGS) -race $(PKGS)

## cover: run tests and write a coverage profile
.PHONY: cover
cover:
	$(GO) test $(GOFLAGS) -covermode=atomic -coverprofile=$(COVERFILE) $(PKGS)
	@$(GO) tool cover -func=$(COVERFILE) | tail -n 1

## cover-html: render the coverage profile as HTML
.PHONY: cover-html
cover-html: cover
	$(GO) tool cover -html=$(COVERFILE) -o $(COVERHTML)
	@echo "wrote $(COVERHTML)"

## bench: run benchmarks
.PHONY: bench
bench:
	$(GO) test $(GOFLAGS) -run '^$$' -bench . -benchmem $(PKGS)

## fmt: format all Go source in place
.PHONY: fmt
fmt:
	$(GO) fmt $(PKGS)

## fmt-check: fail if any Go source is not gofmt-clean
.PHONY: fmt-check
fmt-check:
	@out="$$(gofmt -l .)"; \
	if [ -n "$$out" ]; then \
		echo "not gofmt-clean:"; echo "$$out"; exit 1; \
	fi

## vet: run go vet
.PHONY: vet
vet:
	$(GO) vet $(GOFLAGS) $(PKGS)

## lint: run golangci-lint (skipped if not installed)
.PHONY: lint
lint:
	@if command -v golangci-lint >/dev/null 2>&1; then \
		golangci-lint run $(PKGS); \
	else \
		echo "golangci-lint not installed; skipping (see https://golangci-lint.run)"; \
	fi

## tidy: sync go.mod (and go.sum) with the imports in the tree
.PHONY: tidy
tidy:
	$(GO) mod tidy

## tidy-check: fail if `make tidy` would change go.mod or go.sum
.PHONY: tidy-check
tidy-check:
	@tmp="$$(mktemp -d)"; \
	trap 'rm -rf "$$tmp"' EXIT; \
	cp go.mod "$$tmp/"; \
	[ -f go.sum ] && cp go.sum "$$tmp/" || true; \
	$(GO) mod tidy; \
	status=0; \
	diff -u "$$tmp/go.mod" go.mod || status=1; \
	if [ -f go.sum ] || [ -f "$$tmp/go.sum" ]; then \
		diff -u "$$tmp/go.sum" go.sum || status=1; \
	fi; \
	cp "$$tmp/go.mod" go.mod; \
	[ -f "$$tmp/go.sum" ] && cp "$$tmp/go.sum" go.sum || true; \
	if [ "$$status" -ne 0 ]; then echo "go.mod/go.sum are not tidy; run 'make tidy'"; fi; \
	exit "$$status"

## check: everything CI should enforce
.PHONY: check
check: fmt-check vet lint build test-race

## clean: remove build and coverage artifacts
.PHONY: clean
clean:
	rm -f $(COVERFILE) $(COVERHTML)
	$(GO) clean $(PKGS)

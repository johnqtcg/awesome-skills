# Root Makefile for the Go workspace defined in go.work.
#
# Everything is discovered from the toolchain rather than from the directory
# layout, because the layout lies: svc-api/cmd/api lives in entry.go (not
# main.go), and svc-api/internal/queue/main.go is not a main package. Filename
# globs get both of those wrong; `go list` gets both right.
#
# Run `make help` for the target list.

SHELL := /bin/bash
.DEFAULT_GOAL := help

GO      ?= go
BIN_DIR ?= bin

# Lazy + memoized expansion: `go list` and `git` only run if a target actually
# needs them, and then only once. Keeps `make help`/`make clean` fast, and
# working even without a Go toolchain on PATH.
lazy = $(eval $1 := $$(shell $2))$($1)

# Absolute directory of every module listed in go.work.
MODULE_DIRS = $(call lazy,MODULE_DIRS,$(GO) list -m -f '{{.Dir}}')

# Package patterns covering the whole workspace. Note that a bare `./...` does
# NOT work from here: the workspace root is not itself inside a module.
PKGS = $(addsuffix /...,$(MODULE_DIRS))

# Import paths of every `package main` in the workspace.
MAIN_PKGS = $(call lazy,MAIN_PKGS,$(GO) list -f '{{if eq .Name "main"}}{{.ImportPath}}{{end}}' $(PKGS))

# Binary names are the last path element of each main package.
BINS = $(notdir $(MAIN_PKGS))

# Map a binary name back to the main package that produces it.
pkg_for = $(filter %/$1,$(MAIN_PKGS))

VERSION ?= $(call lazy,VERSION,git describe --tags --always --dirty 2>/dev/null || echo dev)

# -X against a package with no `version` symbol is ignored by the linker, so
# this is safe to apply to every binary (only cmd/api declares one today).
LDFLAGS   ?= -X main.version=$(VERSION)
BUILDFLAGS ?= -trimpath

# Extra arguments forwarded to `go test` / the binary started by `run/%`.
ARGS ?=

.PHONY: help build test test-race cover vet fmt fmt-check tidy list clean

help: ## Show this help
	@echo "Targets:"
	@grep -hE '^[a-zA-Z0-9_/%-]+:.*## ' $(MAKEFILE_LIST) \
		| sed -e 's/:.*## /\t/' \
		| awk -F'\t' '{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Binaries: $(BINS)"

list: ## List workspace modules and main packages
	@echo "modules:"
	@printf '  %s\n' $(MODULE_DIRS)
	@echo "main packages:"
	@printf '  %s\n' $(MAIN_PKGS)

build: ## Build every binary into bin/
	@bins="$(BINS)"; \
	dupes=$$(printf '%s\n' $$bins | sort | uniq -d); \
	if [ -n "$$dupes" ]; then \
	  echo "error: main packages collide on binary name(s): $$dupes" >&2; \
	  exit 1; \
	fi; \
	for b in $$bins; do $(MAKE) --no-print-directory build/$$b || exit 1; done

build/%: ## Build a single binary, e.g. make build/api
	@pkg="$(call pkg_for,$*)"; \
	if [ -z "$$pkg" ]; then echo "error: no main package named '$*' (have: $(BINS))" >&2; exit 1; fi; \
	mkdir -p $(BIN_DIR); \
	echo "building $(BIN_DIR)/$* <- $$pkg"; \
	$(GO) build $(BUILDFLAGS) -ldflags '$(LDFLAGS)' -o $(BIN_DIR)/$* "$$pkg"

run/%: ## Build and run a single binary, e.g. make run/api ARGS="-v"
	@$(MAKE) --no-print-directory build/$*
	@$(BIN_DIR)/$* $(ARGS)

test: ## Run all tests across every module
	$(GO) test $(ARGS) $(PKGS)

test-race: ## Run all tests with the race detector
	$(GO) test -race $(ARGS) $(PKGS)

cover: ## Run tests with coverage and print a summary
	$(GO) test -coverprofile=coverage.out -covermode=atomic $(PKGS)
	@$(GO) tool cover -func=coverage.out | tail -1

vet: ## Run go vet across every module
	$(GO) vet $(PKGS)

fmt: ## Format all Go sources in place
	gofmt -l -w $(MODULE_DIRS)

fmt-check: ## Fail if any Go source is not gofmt-clean
	@out=$$(gofmt -l $(MODULE_DIRS)); \
	if [ -n "$$out" ]; then echo "not gofmt-clean:"; echo "$$out"; exit 1; fi; \
	echo "all files gofmt-clean"

tidy: ## Run go mod tidy in each module, then sync the workspace
	@for d in $(MODULE_DIRS); do \
	  echo "go mod tidy: $$d"; \
	  (cd "$$d" && $(GO) mod tidy) || exit 1; \
	done
	$(GO) work sync

clean: ## Remove build and coverage artifacts
	rm -rf $(BIN_DIR) coverage.out

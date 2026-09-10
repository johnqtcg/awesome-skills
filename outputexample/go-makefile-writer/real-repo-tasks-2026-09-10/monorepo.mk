# Root Makefile — Go workspace monorepo
#
# Layout (go.work):
#   svc-api/   module example.com/svc-api  — programs: cmd/api, cmd/worker
#   pkglib/    module example.com/pkglib   — library only, no programs
#
# IMPORTANT: the repository root is NOT a Go module. `go test ./...` and
# `go fmt ./...` run from here fail with "directory prefix . does not contain
# modules listed in go.work". Every go command below therefore runs *inside* a
# module directory. Do not "simplify" these loops into a single root-level
# `./...` invocation — it does not work in this layout.

.DEFAULT_GOAL := help

# Make runs each recipe in /bin/sh, where a pipeline reports only its LAST
# command's status — so `curl ... | sh` succeeds when the download fails and
# `sh` gets no input. pipefail makes any failing stage fail the pipeline;
# -u catches typo'd variables.
SHELL       := bash
.SHELLFLAGS := -euo pipefail -c

GO      := go
BIN_DIR := bin
# Absolute, because build recipes cd into a module before invoking `go build`.
ABS_BIN := $(CURDIR)/$(BIN_DIR)
COVER_DIR := coverage

VERSION ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
COMMIT  := $(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# `-X` only assigns to an ALREADY-DECLARED package-level string var; a wrong
# path silently no-ops. Discovered in this tree:
#   svc-api/cmd/api/entry.go  -> `var version = "dev"` in package main  (injectable)
#   svc-api/cmd/worker        -> no version var at all                 (nothing to inject)
# So the worker gets no -X flags. Add `var version string` to cmd/worker and
# extend WORKER_LDFLAGS if you want it stamped too. There is no `commit` or
# `buildTime` var anywhere in the tree, so neither is injected — `make version`
# prints COMMIT for information only.
STRIP_FLAGS    := $(if $(DEBUG),,-s -w)
API_LDFLAGS    := $(STRIP_FLAGS) -X main.version=$(VERSION)
WORKER_LDFLAGS := $(STRIP_FLAGS)
# -trimpath strips local filesystem paths so an identical source tree builds
# identically regardless of checkout location.
BUILD_FLAGS := -trimpath

# Pure Go — no `import "C"` anywhere in this tree — so static cross-builds are
# safe. If cgo is ever introduced, flip this to 1 and supply a cross toolchain.
CGO_CROSS := 0
PLATFORMS ?= linux/amd64 linux/arm64

# No pin exists in this repo (no CI workflow, .golangci.version or .tool-versions);
# this matches the version currently installed on the dev machine. Bump deliberately.
GOLANGCI_LINT_VERSION ?= v2.6.2

# Placeholder threshold. Today pkglib is at 100% but svc-api has NO test files
# and reports 0.0%, so any nonzero value makes `make ci` red on a clean
# checkout. Raise this the moment svc-api grows tests.
COVER_MIN ?= 0

# `go env GOWORK` has THREE answers: a path (workspace active), empty (no
# go.work), and the literal string `off` (workspace mode disabled). `off` is
# non-empty, so testing emptiness alone would read it as a path and ask
# `go list -m`, which in this root — which has no go.mod — answers for nothing
# at all. Filtering `off` collapses it into the "no workspace" case, where the
# scoped file search still finds every module.
GOWORK    := $(shell $(GO) env GOWORK 2>/dev/null)
WORKSPACE := $(filter-out off,$(strip $(GOWORK)))

ifeq ($(WORKSPACE),)
MODULES := $(shell find . -name go.mod -type f 2>/dev/null | \
             grep -Ev '(^|/)(vendor|testdata|examples?)(/|$$)' | \
             sed 's|/go\.mod$$||; s|^\./||' | LC_ALL=C sort -u)
else
MODULES := $(shell $(GO) list -m -f '{{.Dir}}' 2>/dev/null)
endif

# Zero modules is never a legitimate answer here — so every aggregate target
# opens with this guard. Without it the loop iterates zero times and exits 0,
# and a broken module list reads as "all modules pass". Repeated per target
# rather than factored into a prerequisite because these recipes get copied
# one at a time; it is not $(error), which would fire at parse time and break
# `make help`.
define require_modules
@test -n "$(strip $(MODULES))" || { echo "no Go modules found — check the go.work / go.mod layout"; exit 1; }
endef

# ---------- build (svc-api only; pkglib is a library) ----------

build-api: ## Build the api binary -> bin/api
	@mkdir -p $(ABS_BIN)
	cd svc-api && $(GO) build $(BUILD_FLAGS) -ldflags '$(API_LDFLAGS)' -o $(ABS_BIN)/api ./cmd/api

build-worker: ## Build the worker binary -> bin/worker
	@mkdir -p $(ABS_BIN)
	cd svc-api && $(GO) build $(BUILD_FLAGS) -ldflags '$(WORKER_LDFLAGS)' -o $(ABS_BIN)/worker ./cmd/worker

build-svc-api: build-api build-worker ## Build every binary in the svc-api module

build-all: build-svc-api ## Build every binary in the workspace

# ---------- cross-compile ----------

build-linux: ## Cross-build all binaries for linux/amd64 (static)
	@mkdir -p $(ABS_BIN)
	@for bin in api worker; do \
		echo "=== linux/amd64: $$bin ==="; \
		(cd svc-api && CGO_ENABLED=$(CGO_CROSS) GOOS=linux GOARCH=amd64 \
			$(GO) build $(BUILD_FLAGS) -o $(ABS_BIN)/$$bin-linux-amd64 ./cmd/$$bin) || exit 1; \
	done

build-all-platforms: ## Cross-build all binaries for every entry in PLATFORMS
	@mkdir -p $(ABS_BIN)
	@test -n "$(strip $(PLATFORMS))" || { echo "PLATFORMS is empty"; exit 1; }
	@for platform in $(PLATFORMS); do \
		os=$${platform%%/*}; arch=$${platform##*/}; \
		for bin in api worker; do \
			echo "=== $$os/$$arch: $$bin ==="; \
			(cd svc-api && CGO_ENABLED=$(CGO_CROSS) GOOS=$$os GOARCH=$$arch \
				$(GO) build $(BUILD_FLAGS) -o $(ABS_BIN)/$$bin-$$os-$$arch ./cmd/$$bin) || exit 1; \
		done; \
	done

# ---------- run ----------
# Built into bin/ first so no stray binaries are left in source directories.

run-api: build-api ## Build and run the api binary
	$(ABS_BIN)/api

run-worker: build-worker ## Build and run the worker binary
	$(ABS_BIN)/worker

# ---------- quality ----------

fmt: ## Format Go sources in every module
	$(require_modules)
	@for mod in $(MODULES); do \
		echo "=== fmt $$(basename $$mod) ==="; \
		(cd $$mod && $(GO) fmt ./...) || exit 1; \
	done

# gofmt is file-based, not module-based, so it can walk the whole tree in one
# pass. It also exits 2 and prints to STDERR (with an EMPTY stdout) on a file
# that does not parse — so `test -z "$(gofmt -l .)"` would pass a tree that does
# not compile. Check the status before looking at the output.
fmt-check: ## Check formatting; fails on unformatted OR unparsable files
	@out=$$(gofmt -l . 2>&1); status=$$?; \
	if [ $$status -ne 0 ]; then \
		echo "gofmt could not parse the tree (exit $$status):"; echo "$$out"; exit $$status; \
	fi; \
	if [ -n "$$out" ]; then \
		echo "gofmt needed on:"; echo "$$out"; exit 1; \
	fi

# `go mod tidy` operates on a single main module — it must run inside each one,
# never once at the workspace root.
tidy: ## go mod tidy + go mod verify in every module
	$(require_modules)
	@for mod in $(MODULES); do \
		echo "=== tidy $$(basename $$mod) ==="; \
		(cd $$mod && $(GO) mod tidy && $(GO) mod verify) || exit 1; \
	done

test: ## Run all tests in every module with the race detector
	$(require_modules)
	@for mod in $(MODULES); do \
		echo "=== test $$(basename $$mod) ==="; \
		(cd $$mod && $(GO) test -race ./...) || exit 1; \
	done

# The FULL suite without -race, for CGO_ENABLED=0 builds and platforms with no
# race support. This is not `-short`: it skips no tests.
test-norace: ## Run the full test suite in every module without -race
	$(require_modules)
	@for mod in $(MODULES); do \
		echo "=== test (norace) $$(basename $$mod) ==="; \
		(cd $$mod && $(GO) test ./...) || exit 1; \
	done

test-short: ## Run only quick tests (skips testing.Short()-gated cases; NOT a race-free equivalent)
	$(require_modules)
	@for mod in $(MODULES); do \
		echo "=== test (short) $$(basename $$mod) ==="; \
		(cd $$mod && $(GO) test -short ./...) || exit 1; \
	done

test-svc-api: ## Run the svc-api module's tests
	cd svc-api && $(GO) test -race ./...

test-pkglib: ## Run the pkglib module's tests
	cd pkglib && $(GO) test -race ./...

bench: ## Run benchmarks (no race detector — it distorts timings)
	$(require_modules)
	@for mod in $(MODULES); do \
		echo "=== bench $$(basename $$mod) ==="; \
		(cd $$mod && $(GO) test -bench=. -benchmem -run='^$$' ./...) || exit 1; \
	done

cover: ## Run tests with coverage; profiles land in coverage/<module>.out
	$(require_modules)
	@mkdir -p $(COVER_DIR)
	@for mod in $(MODULES); do \
		name=$$(basename $$mod); \
		echo "=== cover $$name ==="; \
		(cd $$mod && $(GO) test -race -coverprofile=$(CURDIR)/$(COVER_DIR)/$$name.out ./...) || exit 1; \
		$(GO) tool cover -func=$(COVER_DIR)/$$name.out | tail -n 1; \
	done

cover-check: cover ## Fail if any module's coverage is below COVER_MIN
	$(require_modules)
	@for mod in $(MODULES); do \
		name=$$(basename $$mod); \
		total=$$($(GO) tool cover -func=$(COVER_DIR)/$$name.out | awk '/^total:/ {print $$3}' | tr -d '%'); \
		test -n "$$total" || { echo "$$name: no coverage total produced"; exit 1; }; \
		if awk -v t="$$total" -v m="$(COVER_MIN)" 'BEGIN { exit !(t+0 < m+0) }'; then \
			echo "$$name: coverage $$total% < $(COVER_MIN)%"; exit 1; \
		fi; \
		echo "$$name: coverage $$total% (min $(COVER_MIN)%)"; \
	done

lint: check-tools ## Run golangci-lint in every module
	$(require_modules)
	@for mod in $(MODULES); do \
		echo "=== lint $$(basename $$mod) ==="; \
		(cd $$mod && golangci-lint run ./...) || exit 1; \
	done

lint-svc-api: check-tools ## Lint the svc-api module
	cd svc-api && golangci-lint run ./...

lint-pkglib: check-tools ## Lint the pkglib module
	cd pkglib && golangci-lint run ./...

# ---------- ci ----------
# This repository has no CI pipeline yet (no .github/workflows). When one is
# added, make it invoke `make ci` — or update this list to mirror it exactly.
# A local `ci` that runs a different set from the pipeline gives false confidence.

ci: fmt-check lint test cover-check ## Run the full check suite locally

# ---------- version ----------

version: ## Print the version metadata this build would use
	@echo "version=$(VERSION) commit=$(COMMIT)"
	@echo "(only 'version' is embedded, into svc-api/cmd/api; commit is informational)"

# ---------- tools ----------

install-tools: ## Install pinned dev tools
	@set -e; \
	script=$$(mktemp); trap 'rm -f "$$script"' EXIT; \
	curl -sSfL https://raw.githubusercontent.com/golangci/golangci-lint/HEAD/install.sh -o "$$script"; \
	test -s "$$script" || { echo "installer download produced an empty file"; exit 1; }; \
	sh "$$script" -b $$($(GO) env GOPATH)/bin $(GOLANGCI_LINT_VERSION)

check-tools: ## Verify required tools are installed
	@failed=0; \
	for tool in golangci-lint; do \
		command -v $$tool >/dev/null || { echo "$$tool not found"; failed=1; }; \
	done; \
	[ $$failed -eq 0 ] || { echo "run 'make install-tools' to install missing tools"; exit 1; }

# ---------- clean ----------

clean: ## Remove build artifacts and coverage profiles
	rm -rf $(BIN_DIR) $(COVER_DIR)

# ---------- help ----------

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_-]+:.*##/ {printf "%-22s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: \
	build-api build-worker build-svc-api build-all \
	build-linux build-all-platforms \
	run-api run-worker \
	fmt fmt-check tidy \
	test test-norace test-short test-svc-api test-pkglib bench \
	cover cover-check \
	lint lint-svc-api lint-pkglib \
	ci version install-tools check-tools clean help

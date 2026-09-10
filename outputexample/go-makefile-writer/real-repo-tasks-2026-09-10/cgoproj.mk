# Makefile — example.com/cgoproj
#
# Layout:
#   hash.go, hash_test.go   package cgoproj (library)
#   cmd/hasher/main.go      package main — USES CGO (import "C")
#
# The cgo dependency shapes almost every decision below. Two defaults that are
# right for a pure-Go repo are actively wrong here, and both were verified
# against this tree rather than assumed:
#
#   CGO_ENABLED=0 go build ./cmd/hasher
#     -> build constraints exclude all Go files in cmd/hasher
#   GOOS=linux GOARCH=amd64 CGO_ENABLED=1 go build ./cmd/hasher   (on darwin)
#     -> # runtime/cgo: gcc_amd64.S: unknown token in expression
#
# So: cgo is always ON, and a linux/amd64 build needs a linux/amd64 *C* cross
# toolchain, not just GOOS/GOARCH. See the "cross-compile" section.

.DEFAULT_GOAL := help

# Make runs each recipe line in /bin/sh, where a pipeline's exit status is only
# its LAST command's — so `curl ... | sh` reports success even when the download
# failed with nothing to pipe. `pipefail` makes the pipeline fail if any stage
# does; `-u` catches typo'd variables.
SHELL       := bash
.SHELLFLAGS := -euo pipefail -c

GO       := go
BIN_DIR  := bin
BIN_NAME := hasher
PKG      := ./cmd/hasher

# cgo is not optional for this module. Hard-assigned rather than `?=` so a stray
# CGO_ENABLED=0 in the environment cannot silently turn the build into the
# "build constraints exclude all Go files" error above; `require-cgo` catches an
# explicit `make CGO_ENABLED=0 ...` override on the command line.
CGO_ENABLED := 1
export CGO_ENABLED

GO_VERSION := $(shell awk '/^go /{print $$2; exit}' go.mod)

VERSION           ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
COMMIT            := $(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")
SOURCE_DATE_EPOCH ?= $(shell git log -1 --format=%ct 2>/dev/null || date +%s)
BUILD_TIME        := $(shell date -u -d "@$(SOURCE_DATE_EPOCH)" '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u -r "$(SOURCE_DATE_EPOCH)" '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u '+%Y-%m-%dT%H:%M:%SZ')

# `-X` only assigns to an *existing* package-level string var; a wrong path is a
# silent no-op, not an error. cmd/hasher/main.go declares exactly one:
#     var version = "dev"
# so only main.version is injected. COMMIT and BUILD_TIME are computed above and
# printed by `make version`, but deliberately NOT passed as -X — there is no
# main.commit / main.buildTime to receive them. Add those two vars to main.go and
# the two commented lines below become live.
LDFLAGS := $(if $(DEBUG),,-s -w) \
	-X main.version=$(VERSION)
#	-X main.commit=$(COMMIT) \
#	-X main.buildTime=$(BUILD_TIME)

# -trimpath strips local filesystem paths so identical source builds identically
# regardless of checkout location.
BUILD_FLAGS := -trimpath -ldflags "$(LDFLAGS)"

# No pin existed in this repo (no CI workflow, no .tool-versions, no
# .golangci.version), so this matches the version already on the dev machine.
# golangci-lint is v2; it tracks only the two most recent Go minors.
GOLANGCI_LINT_VERSION ?= v2.6.2

COVER_MIN ?= 45

# ---------- guards ----------

require-cgo:
	@test "$(CGO_ENABLED)" = "1" || { \
		echo "CGO_ENABLED=$(CGO_ENABLED): cmd/hasher uses cgo (import \"C\")."; \
		echo "With cgo off, 'build constraints exclude all Go files in cmd/hasher'."; \
		exit 1; \
	}

# ---------- build (host) ----------

build-hasher: require-cgo ## Build hasher for the host platform
	@mkdir -p $(BIN_DIR)
	$(GO) build $(BUILD_FLAGS) -o $(BIN_DIR)/$(BIN_NAME) $(PKG)

build-all: build-hasher ## Build all binaries for the host platform

# ---------- run ----------

run-hasher: build-hasher ## Build and run hasher from bin/
	./$(BIN_DIR)/$(BIN_NAME)

# ---------- cross-compile: linux/amd64 ----------
#
# A cgo binary cannot be cross-compiled by GOOS/GOARCH alone: the host C
# compiler must be able to emit linux/amd64 objects. Two working paths, pick with
# LINUX_BUILDER:
#
#   docker (default) — builds inside a linux/amd64 golang container. No host
#       toolchain needed. On an Apple Silicon laptop this runs under emulation,
#       so it is slow but correct. Produces a *glibc-dynamic* binary linked
#       against the build image's glibc; the deploy target needs a glibc at
#       least that new.
#   zig — `zig cc` is a self-contained cross compiler. Fast, no daemon, and
#       targets musl to produce a fully *static* binary that runs on any linux
#       amd64 host (including distroless/alpine). Requires `zig` on PATH.
#
#   make build-linux                      # docker
#   make build-linux LINUX_BUILDER=zig    # zig
#   make build-linux LINUX_ARCH=arm64     # either builder

LINUX_ARCH    ?= amd64
LINUX_BUILDER ?= docker
LINUX_OUT     := $(BIN_DIR)/$(BIN_NAME)-linux-$(LINUX_ARCH)

# Image tag follows the go directive in go.mod so the cross build cannot drift
# to a different language version than the host build.
BUILD_IMAGE ?= golang:$(GO_VERSION)-bookworm
DOCKER_CACHE := $(CURDIR)/.cache/docker-go

# zig spells architectures with LLVM triples, not Go's names.
ZIG_ARCH   := $(if $(filter arm64,$(LINUX_ARCH)),aarch64,x86_64)
ZIG_TARGET ?= $(ZIG_ARCH)-linux-musl

build-linux: ## Build for linux/amd64 via LINUX_BUILDER=docker|zig (override LINUX_ARCH)
	@case "$(LINUX_BUILDER)" in \
		docker|zig) ;; \
		*) echo "LINUX_BUILDER must be 'docker' or 'zig' (got '$(LINUX_BUILDER)')"; exit 1 ;; \
	esac
	@$(MAKE) --no-print-directory build-linux-$(LINUX_BUILDER)

build-linux-docker: ## Cross-build for linux/amd64 in a container (glibc-dynamic)
	@command -v docker >/dev/null || { \
		echo "docker not found; install Docker or use 'make build-linux LINUX_BUILDER=zig'"; exit 1; }
	@docker info >/dev/null 2>&1 || { \
		echo "docker is installed but the daemon is not reachable — start Docker Desktop,"; \
		echo "or use 'make build-linux LINUX_BUILDER=zig'"; exit 1; }
	@mkdir -p $(BIN_DIR) $(DOCKER_CACHE)/build $(DOCKER_CACHE)/mod
	docker run --rm \
		--platform linux/$(LINUX_ARCH) \
		-u "$$(id -u):$$(id -g)" \
		-v "$(CURDIR)":/src -w /src \
		-v "$(DOCKER_CACHE)":/gocache \
		-e HOME=/tmp \
		-e GOCACHE=/gocache/build -e GOMODCACHE=/gocache/mod \
		-e CGO_ENABLED=1 -e GOOS=linux -e GOARCH=$(LINUX_ARCH) \
		$(BUILD_IMAGE) \
		go build -buildvcs=false $(BUILD_FLAGS) -o $(LINUX_OUT) $(PKG)
	@$(MAKE) --no-print-directory verify-linux

build-linux-zig: ## Cross-build for linux/amd64 with zig cc (musl-static)
	@command -v zig >/dev/null || { \
		echo "zig not found; install it (brew install zig) or use 'make build-linux LINUX_BUILDER=docker'"; exit 1; }
	@mkdir -p $(BIN_DIR)
	CGO_ENABLED=1 GOOS=linux GOARCH=$(LINUX_ARCH) \
	CC="zig cc -target $(ZIG_TARGET)" CXX="zig c++ -target $(ZIG_TARGET)" \
	$(GO) build -trimpath \
		-ldflags "$(LDFLAGS) -linkmode external -extldflags '-static'" \
		-o $(LINUX_OUT) $(PKG)
	@$(MAKE) --no-print-directory verify-linux

verify-linux: ## Check the cross-built artifact is a linux ELF executable
	@test -f "$(LINUX_OUT)" || { echo "$(LINUX_OUT) not built"; exit 1; }
	@desc=$$(file -b "$(LINUX_OUT)"); \
	echo "$(LINUX_OUT): $$desc"; \
	case "$$desc" in \
		*"ELF 64-bit"*) ;; \
		*) echo "not an ELF executable — cross build did not target linux"; exit 1 ;; \
	esac
	@$(GO) version -m "$(LINUX_OUT)" | awk '$$1=="build" && ($$2=="GOOS" || $$2=="GOARCH" || $$2=="CGO_ENABLED")'

run-linux: ## Run the cross-built linux binary under docker (verifies version injection)
	@test -f "$(LINUX_OUT)" || { echo "$(LINUX_OUT) not built; run 'make build-linux'"; exit 1; }
	@docker info >/dev/null 2>&1 || { echo "docker daemon not reachable"; exit 1; }
	docker run --rm --platform linux/$(LINUX_ARCH) \
		-v "$(CURDIR)/$(LINUX_OUT)":/$(BIN_NAME):ro \
		$(BUILD_IMAGE) /$(BIN_NAME)

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

test-norace: ## Run the full test suite without -race (platforms without race support)
	$(GO) test ./...

test-short: ## Run only quick tests (skips testing.Short() cases; NOT a race-free equivalent)
	$(GO) test -short ./...

cover: ## Run tests with coverage report
	$(GO) test -race -coverprofile=coverage.out ./...
	$(GO) tool cover -func=coverage.out | tail -n 1

cover-check: cover ## Fail if total coverage is below COVER_MIN
	@total=$$($(GO) tool cover -func=coverage.out | awk '/^total:/ {print $$3}' | tr -d '%'); \
	if [ "$$(echo "$$total < $(COVER_MIN)" | bc -l 2>/dev/null || echo 1)" = "1" ]; then \
		echo "coverage $${total}% < $(COVER_MIN)%"; exit 1; \
	fi

lint: ## Run golangci-lint
	@command -v golangci-lint >/dev/null || { \
		echo "golangci-lint not found; run 'make install-tools'"; exit 1; }
	golangci-lint run

# ---------- ci ----------

# This repo has no pipeline config yet (no .github/workflows), so `ci` defines
# the contract rather than mirroring one. When a pipeline is added, change one
# side to match the other — a local `ci` that runs a different set is worse than
# none, because it gives false confidence.
ci: fmt-check lint test cover-check ## Run the full CI gate locally

# ---------- version ----------

version: ## Print the version metadata this Makefile would inject
	@echo "version=$(VERSION) commit=$(COMMIT) build_time=$(BUILD_TIME)"
	@echo "(only version= is injected — main.go has no commit/buildTime vars)"

# ---------- tools ----------

install-tools: ## Install pinned dev tools
	@set -e; \
	script=$$(mktemp); trap 'rm -f "$$script"' EXIT; \
	curl -sSfL https://raw.githubusercontent.com/golangci/golangci-lint/HEAD/install.sh -o "$$script"; \
	test -s "$$script" || { echo "installer download produced an empty file"; exit 1; }; \
	sh "$$script" -b "$$($(GO) env GOPATH)/bin" $(GOLANGCI_LINT_VERSION)

check-tools: ## Verify required and optional tools are present
	@command -v golangci-lint >/dev/null || { \
		echo "golangci-lint not found; run 'make install-tools'"; exit 1; }
	@echo "golangci-lint: $$(command -v golangci-lint)"
	@command -v docker >/dev/null && echo "docker:         $$(command -v docker)" \
		|| echo "docker:         not found (needed for LINUX_BUILDER=docker)"
	@command -v zig >/dev/null && echo "zig:            $$(command -v zig)" \
		|| echo "zig:            not found (needed for LINUX_BUILDER=zig)"

# ---------- clean ----------

clean: ## Remove build artifacts and coverage output
	rm -rf $(BIN_DIR) coverage.out

clean-cache: ## Remove the container build cache (forces a slow first cross build)
	rm -rf $(CURDIR)/.cache

# ---------- help ----------

help: ## Show this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z0-9_-]+:.*?## / \
		{printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: help require-cgo build-hasher build-all run-hasher \
	build-linux build-linux-docker build-linux-zig verify-linux run-linux \
	fmt fmt-check tidy test test-norace test-short cover cover-check lint \
	ci version install-tools check-tools clean clean-cache

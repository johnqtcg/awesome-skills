.DEFAULT_GOAL := help

GO ?= go
BIN_DIR ?= bin

COVER_FILE ?= coverage.out
COVER_HTML ?= coverage.html
COVER_MIN ?= 80

GOLANGCI_LINT ?= golangci-lint
GOCACHE_DIR ?= /tmp/gocache
GOLANGCI_LINT_CACHE_DIR ?= /tmp/golangci-lint-cache
GOIMPORTS_REVISER ?= goimports-reviser
GOIMPORTS_REVISER_INSTALL ?= github.com/incu6us/goimports-reviser/v3@v3.9.0
SWAG ?= swag
SWAG_INSTALL ?= github.com/swaggo/swag/cmd/swag@v1.16.6
SWAG_DIR ?= cmd/issue2mdweb
SWAG_ENTRY ?= main.go
SWAG_OUTPUT ?= docs

.PHONY: help check-tools fmt fmt-check test test-api-integration test-e2e-web cover cover-check lint install-goimports-reviser install-swag swagger swagger-check \
	ci ci-core ci-api-integration ci-e2e-web ci-all \
	build-all build-cli build-web build-issue2md build-issue2mdweb \
	install-cli install-web \
	run-cli run-web run-issue2md run-issue2mdweb clean web docker-build

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make <target>\n\nTargets:\n"} /^[a-zA-Z0-9_.-]+:.*##/ {printf "  %-22s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

check-tools: ## Check required and optional tools
	@command -v $(GO) >/dev/null || { echo "missing tool: $(GO)"; exit 1; }
	@command -v gofmt >/dev/null || { echo "missing tool: gofmt"; exit 1; }
	@command -v $(GOIMPORTS_REVISER) >/dev/null || echo "optional tool missing: $(GOIMPORTS_REVISER) (required for make fmt)"
	@command -v $(GOLANGCI_LINT) >/dev/null || echo "optional tool missing: $(GOLANGCI_LINT) (required for make lint)"
	@command -v $(SWAG) >/dev/null || echo "optional tool missing: $(SWAG) (required for make swagger)"

fmt: ## Format all Go files (tracked + untracked) with gofmt + goimports-reviser
	@command -v $(GOIMPORTS_REVISER) >/dev/null || { echo "missing tool: $(GOIMPORTS_REVISER)"; exit 1; }
	@file_count=$$(find . -type f -name '*.go' \
		-not -path './.git/*' \
		-not -path './vendor/*' \
		-not -path './bin/*' | wc -l | tr -d ' '); \
	if [ "$$file_count" -gt 0 ]; then \
		find . -type f -name '*.go' \
			-not -path './.git/*' \
			-not -path './vendor/*' \
			-not -path './bin/*' -print0 | xargs -0 gofmt -w; \
		$(GOIMPORTS_REVISER) -rm-unused -format ./...; \
	else \
		echo "no Go files"; \
	fi

fmt-check: fmt ## In CI, fail if formatting changes are required
	@if [ "$${CI:-}" = "true" ]; then \
		git diff --exit-code || (echo "code is not formatted; run 'make fmt' and commit changes" && exit 1); \
	else \
		echo "CI env not detected; skip formatting diff check"; \
	fi

install-goimports-reviser: ## Install goimports-reviser
	$(GO) install $(GOIMPORTS_REVISER_INSTALL)

test: ## Run all tests
	GOCACHE=$(GOCACHE_DIR) $(GO) test ./...

test-api-integration: ## Run opt-in API integration tests for web endpoints
	GOCACHE=$(GOCACHE_DIR) ISSUE2MD_API_INTEGRATION=1 $(GO) test ./tests/integration/http -run Integration -v

test-e2e-web: ## Run opt-in web E2E journey tests
	GOCACHE=$(GOCACHE_DIR) ISSUE2MD_E2E=1 ISSUE2MD_WEB_ADDR=127.0.0.1:18080 $(GO) test ./tests/e2e/web -run E2E -v

cover: ## Run tests with coverage report
	GOCACHE=$(GOCACHE_DIR) $(GO) test ./... -coverprofile=$(COVER_FILE)
	$(GO) tool cover -func=$(COVER_FILE) | tail -n 1

cover-check: cover ## Enforce minimum coverage with COVER_MIN
	@pct=$$($(GO) tool cover -func=$(COVER_FILE) | awk '/total:/ {gsub("%","",$$3); print $$3}'); \
	awk -v p="$$pct" -v m="$(COVER_MIN)" 'BEGIN { if (p+0 < m+0) { printf("coverage %.2f%% < %.2f%%\n", p, m); exit 1 } else { printf("coverage %.2f%% >= %.2f%%\n", p, m); } }'

lint: ## Run golangci-lint
	@command -v $(GOLANGCI_LINT) >/dev/null || { echo "missing tool: $(GOLANGCI_LINT)"; exit 1; }
	GOCACHE=$(GOCACHE_DIR) GOLANGCI_LINT_CACHE=$(GOLANGCI_LINT_CACHE_DIR) $(GOLANGCI_LINT) run --config .golangci.yaml ./...

install-swag: ## Install swag CLI
	$(GO) install $(SWAG_INSTALL)

swagger: ## Generate OpenAPI docs to docs/
	@command -v $(SWAG) >/dev/null || { echo "missing tool: $(SWAG)"; exit 1; }
	$(SWAG) init --dir $(SWAG_DIR) --generalInfo $(SWAG_ENTRY) --output $(SWAG_OUTPUT) --parseInternal --outputTypes json,yaml
	@rm -f $(SWAG_OUTPUT)/docs.go

swagger-check: swagger ## Verify generated OpenAPI spec file exists
	@test -f $(SWAG_OUTPUT)/swagger.json || { echo "missing generated file: $(SWAG_OUTPUT)/swagger.json"; exit 1; }

build-all: build-issue2md build-issue2mdweb ## Build all binaries

build-cli: build-issue2md ## Build CLI binary

build-web: build-issue2mdweb ## Build web binary

web: build-web ## Build web service binary (compat alias)

docker-build: ## Build Docker image issue2md:latest from root Dockerfile
	docker build -f Dockerfile -t issue2md:latest .

build-issue2md: ## Build cmd/issue2md
	@mkdir -p $(BIN_DIR)
	$(GO) build -o $(BIN_DIR)/issue2md ./cmd/issue2md

build-issue2mdweb: ## Build cmd/issue2mdweb
	@mkdir -p $(BIN_DIR)
	$(GO) build -o $(BIN_DIR)/issue2mdweb ./cmd/issue2mdweb

install-cli: ## Install CLI binary into GOBIN (or GOPATH/bin)
	$(GO) install ./cmd/issue2md

install-web: ## Install web binary into GOBIN (or GOPATH/bin)
	$(GO) install ./cmd/issue2mdweb

run-cli: run-issue2md ## Run CLI app (pass ARGS='...')

run-web: run-issue2mdweb ## Run web app

run-issue2md: ## Run cmd/issue2md (pass ARGS='...')
	$(GO) run ./cmd/issue2md $(ARGS)

run-issue2mdweb: ## Run cmd/issue2mdweb
	$(GO) run ./cmd/issue2mdweb

ci: fmt-check ci-core ## Local/CI required gate parity checks (matches workflow ci job)

ci-core: cover-check lint build-all ## Run coverage gate, lint, build (workflow ci job)

ci-api-integration: test-api-integration ## Local parity with workflow api-integration job

ci-e2e-web: test-e2e-web ## Local parity with workflow e2e-web job

ci-all: ci-core ci-api-integration ci-e2e-web ## Run all local CI parity checks

clean: ## Remove build and coverage artifacts
	rm -rf $(BIN_DIR) $(COVER_FILE) $(COVER_HTML)

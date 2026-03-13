# Golden Makefile — Complex Project
#
# Project layout:
#   cmd/api/main.go
#   cmd/consumer/sync/main.go
#   cmd/consumer/notify/main.go
#   cmd/cron/cleanup/main.go
#   cmd/migrate/main.go
#   internal/...
#   go.mod, Dockerfile, docker-compose.yml
#
# Tools: golangci-lint, swag, mockgen
# Features: code generation, Docker, cross-compilation

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

# Container
IMAGE_NAME  ?= $(shell basename $(CURDIR))
IMAGE_TAG   ?= $(VERSION)

# Cross-compilation
PLATFORMS ?= linux/amd64 linux/arm64

# Pinned tool versions
GOLANGCI_LINT_VERSION ?= v1.62.2
SWAG_VERSION          ?= v1.16.4
MOCKGEN_VERSION       ?= v0.5.0

# Coverage threshold
COVER_MIN ?= 80

# ---------- build ----------

build-api: ## Build API binary
	@mkdir -p $(BIN_DIR)
	$(GO) build -ldflags "$(LDFLAGS)" -o $(BIN_DIR)/api ./cmd/api

build-consumer-sync: ## Build consumer-sync binary
	@mkdir -p $(BIN_DIR)
	$(GO) build -ldflags "$(LDFLAGS)" -o $(BIN_DIR)/consumer-sync ./cmd/consumer/sync

build-consumer-notify: ## Build consumer-notify binary
	@mkdir -p $(BIN_DIR)
	$(GO) build -ldflags "$(LDFLAGS)" -o $(BIN_DIR)/consumer-notify ./cmd/consumer/notify

build-cron-cleanup: ## Build cron-cleanup binary
	@mkdir -p $(BIN_DIR)
	$(GO) build -ldflags "$(LDFLAGS)" -o $(BIN_DIR)/cron-cleanup ./cmd/cron/cleanup

build-migrate: ## Build migrate binary
	@mkdir -p $(BIN_DIR)
	$(GO) build -ldflags "$(LDFLAGS)" -o $(BIN_DIR)/migrate ./cmd/migrate

build-all: build-api build-consumer-sync build-consumer-notify build-cron-cleanup build-migrate ## Build all binaries

# ---------- run ----------

run-api: build-api ## Run API server
	./$(BIN_DIR)/api

run-consumer-sync: build-consumer-sync ## Run consumer-sync
	./$(BIN_DIR)/consumer-sync

run-consumer-notify: build-consumer-notify ## Run consumer-notify
	./$(BIN_DIR)/consumer-notify

run-cron-cleanup: build-cron-cleanup ## Run cron-cleanup
	./$(BIN_DIR)/cron-cleanup

run-migrate: build-migrate ## Run database migration
	./$(BIN_DIR)/migrate

# ---------- cross-compile ----------

build-linux: ## Build all binaries for Linux amd64 (static)
	@mkdir -p $(BIN_DIR)
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 $(GO) build -ldflags "$(LDFLAGS)" -o $(BIN_DIR)/api-linux-amd64 ./cmd/api
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 $(GO) build -ldflags "$(LDFLAGS)" -o $(BIN_DIR)/consumer-sync-linux-amd64 ./cmd/consumer/sync
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 $(GO) build -ldflags "$(LDFLAGS)" -o $(BIN_DIR)/consumer-notify-linux-amd64 ./cmd/consumer/notify
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 $(GO) build -ldflags "$(LDFLAGS)" -o $(BIN_DIR)/cron-cleanup-linux-amd64 ./cmd/cron/cleanup
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 $(GO) build -ldflags "$(LDFLAGS)" -o $(BIN_DIR)/migrate-linux-amd64 ./cmd/migrate

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

test-integration: ## Run integration tests (requires build tag)
	$(GO) test -race -tags=integration ./...

bench: ## Run benchmarks (no race detector — intentionally excluded for performance accuracy)
	$(GO) test -bench=. -benchmem -run='^$$' ./...

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

# ---------- code generation ----------

swagger: ## Generate Swagger docs
	@command -v swag >/dev/null || (echo "swag not found; run 'make install-tools'" && exit 1)
	swag init -g cmd/api/main.go -o docs

generate: ## Run all code generation (go generate + swagger)
	$(GO) generate ./...
	$(MAKE) swagger

generate-check: generate ## Verify generated code is up to date
	@git diff --exit-code || \
		(echo "generated code is stale; run 'make generate' and commit" && exit 1)

# ---------- ci ----------

ci: fmt-check lint test cover-check generate-check ## Run full CI pipeline locally

# ---------- container ----------

docker-build: ## Build Docker image
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) \
		--build-arg VERSION=$(VERSION) --build-arg COMMIT=$(COMMIT) .

docker-push: ## Push Docker image to registry
	docker push $(IMAGE_NAME):$(IMAGE_TAG)

# ---------- version ----------

version: ## Print embedded version info
	@echo "version=$(VERSION) commit=$(COMMIT) build_time=$(BUILD_TIME)"

# ---------- tools ----------

install-tools: ## Install required development tools
	$(GO) install github.com/golangci/golangci-lint/cmd/golangci-lint@$(GOLANGCI_LINT_VERSION)
	$(GO) install github.com/swaggo/swag/cmd/swag@$(SWAG_VERSION)
	$(GO) install go.uber.org/mock/mockgen@$(MOCKGEN_VERSION)

check-tools: ## Verify required tools are installed
	@failed=0; \
	for tool in golangci-lint swag mockgen; do \
		command -v $$tool >/dev/null || { echo "$$tool not found"; failed=1; }; \
	done; \
	[ $$failed -eq 0 ] || { echo "run 'make install-tools' to install missing tools"; exit 1; }

# ---------- clean ----------

clean: ## Remove build artifacts
	rm -rf $(BIN_DIR) coverage.out docs/

# ---------- phony ----------

.PHONY: help \
	build-api build-consumer-sync build-consumer-notify build-cron-cleanup build-migrate build-all \
	run-api run-consumer-sync run-consumer-notify run-cron-cleanup run-migrate \
	build-linux \
	fmt fmt-check tidy test test-integration bench cover cover-check lint \
	swagger generate generate-check \
	ci docker-build docker-push \
	version install-tools check-tools clean

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_-]+:.*##/ {printf "%-28s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

---
title: Go Coding Standards
owner: team
status: active
last_updated: 2026-03-17
applicable_versions: Go 1.21+
---

# Go Coding Standards

These standards cover seven areas for Go projects: code formatting, static analysis, Git workflow, directory structure, naming and comments, API design, and API documentation. All standards are enforced via CI quality gates — every commit must pass `gofmt`, `goimports-reviser`, and `golangci-lint` before merging.

---

## 1 Code Formatting

All code must be formatted before committing to keep a consistent style across the team.

### 1.1 gofmt

`gofmt` is Go's built-in formatter. It is available as soon as Go is installed.

```bash
# Format a single file
gofmt -w file.go

# Format all Go files under a directory
gofmt -w ./logic
```

### 1.2 goimports-reviser

`goimports-reviser` gives finer-grained control over import grouping than `goimports`. It arranges imports in the team's agreed order: **standard library / third-party / blank imports / internal packages**.

Correct import grouping:

```go
import (
    "context"
    "time"

    "github.com/pkg/errors"
    "github.com/zeromicro/go-zero/core/logx"
    "github.com/zeromicro/go-zero/core/stores/sqlx"

    "myproject/com/model"
    "myproject/utils/consts"
    "myproject/utils/lib"
)
```

> **Do not use `goimports`** — it sorts by alphabetical order, which breaks the agreed grouping.

Installation and usage:

```bash
# Install (pin to a specific version so local and CI behaviour match)
go install github.com/incu6us/goimports-reviser/v3@v3.9.0

# Verify
goimports-reviser -version
# goimports-reviser version v3.9.0

# Format the current directory
goimports-reviser

# Recommended alias (add to .zshrc or .bashrc)
alias gof="goimports-reviser ./..."
```

### 1.3 CI Integration

Add a format check to `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
  schedule:
    - cron: '0 3 * * *'

jobs:
  ci:
    name: Format
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version-file: go.mod
          cache: true
      - name: Install goimports-reviser
        run: go install github.com/incu6us/goimports-reviser/v3@v3.9.0
      - name: Format (gofmt + goimports-reviser)
        run: |
          make fmt
          git diff --exit-code || (echo "code is not formatted; run 'make fmt' and commit changes" && exit 1)
```

### 1.4 Makefile Targets

This document references `make` targets throughout the CI configuration. Below is the canonical Makefile implementation:

```makefile
# Override via environment variable if needed
GO        ?= go
COVER_MIN ?= 80

.PHONY: fmt lint test cover-check build-all

## fmt: format code (gofmt + goimports-reviser)
fmt:
	gofmt -w .
	goimports-reviser ./...

## lint: run static analysis
lint:
	golangci-lint run --config .golangci.yaml ./...

## test: run unit tests and print coverage report
test:
	$(GO) test -race -coverprofile=coverage.out ./...
	$(GO) tool cover -func=coverage.out

## cover-check: fail if coverage is below COVER_MIN (default 80%)
cover-check: test
	@COVERAGE=$$(go tool cover -func=coverage.out | grep total | awk '{print $$3}' | tr -d '%'); \
	echo "Coverage: $${COVERAGE}%  (minimum: $(COVER_MIN)%)"; \
	if [ $$(echo "$${COVERAGE} < $(COVER_MIN)" | bc) -eq 1 ]; then \
		echo "FAIL: coverage $${COVERAGE}% is below minimum $(COVER_MIN)%"; exit 1; \
	fi

## build-all: compile all binaries under cmd/ into bin/
build-all:
	$(GO) build -o bin/ ./cmd/...

## help: list all available targets
help:
	@grep -E '^## ' Makefile | sed 's/## //'
```

> Place this Makefile in the project root so that CI scripts can call `make <target>` without hardcoding raw commands in YAML.

---

## 2 Static Analysis

All code must pass static analysis before committing to catch potential bugs, performance issues, and style violations.

### 2.1 Why Static Analysis

Static analysis scans code at the lexical, syntactic, semantic, control-flow, and data-flow levels — without running the program — to identify:

- **Potential logic errors**: uninitialized variables, nil dereferences, resource leaks
- **Style violations**: inconsistent naming, overly long functions, high complexity, API misuse
- **Security vulnerabilities**: SQL injection, XSS risks, unsafe concurrent access
- **Performance issues**: inefficient loops, unnecessary allocations

The core value: **finding a problem during development costs far less than finding it in tests or production.**

### 2.2 Real-World Examples

#### 2.2.1 Performance Improvement

The linter flags a slice that should be pre-allocated:

```
internal/pkg/dbutil/oracle_update_or_insert_builder.go:66:2:
  Consider pre-allocating `parts` (prealloc)
```

```go
func buildUpdateSet(cols []columnMeta, t reflect.Type, args *[]interface{}, paramIndex *int) []string {
    // BAD: var parts []string
    // GOOD: pre-allocate to avoid repeated growth
    parts := make([]string, 0, len(cols))
    for _, c := range cols {
        if c.PrimaryKey || c.Exclude {
            continue
        }
        if c.EmptyValue && hasTag(t, c.Column, "omitempty") {
            continue
        }
        parts = append(parts, fmt.Sprintf("t.%s = :%d", c.Column, *paramIndex))
        *args = append(*args, c.Value)
        *paramIndex++
    }
    return parts
}
```

#### 2.2.2 Readability and Maintainability

The linter warns that a function's cyclomatic complexity is too high:

```
main.go:34:1: cyclomatic complexity 16 of func `main` is high (> 15) (gocyclo)
```

Fix: split the monolithic `main()` into an `App` struct with focused methods — `loadConfig`, `initLogger`, `initDependencies`, `initFiberApp`, `gracefulShutdown` — each with a single responsibility.

#### 2.2.3 Naming Conventions

The linter flags a meaningless package name:

```
utils/time.go:1:9: var-naming: avoid meaningless package names (revive)
package utils
```

### 2.3 Installation and Usage

```bash
# Install golangci-lint (use the same version as CI)
go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@v2.6.2
# or
brew install golangci-lint

# Verify
golangci-lint --version
# golangci-lint has version v2.6.2 built with go1.24.x

# Basic usage
golangci-lint run ./dir

# Recommended alias
alias linter='golangci-lint run --config .golangci.yaml'
```

### 2.4 `.golangci.yaml` Configuration

`.golangci.yaml` in the project root controls which linters are enabled and how they are configured. Below is the team's recommended minimal config:

```yaml
version: "2"

linters:
  enable:
    - gofmt          # formatting check (belt-and-suspenders alongside the gofmt CI step)
    - revive         # drop-in replacement for golint with custom rules
    - govet          # official vet checks (shadowed vars, printf format mismatches, etc.)
    - errcheck       # ensure errors are handled
    - staticcheck    # comprehensive static analysis
    - prealloc       # suggest slice pre-allocation
    - gocyclo        # cyclomatic complexity
    - misspell       # catch English spelling mistakes

linters-settings:
  gocyclo:
    min-complexity: 15   # functions above 15 should be split
  revive:
    rules:
      - name: var-naming
        disabled: false

issues:
  exclude-rules:
    # relax errcheck in test files
    - path: "_test\\.go"
      linters:
        - errcheck
  max-issues-per-linter: 50
  max-same-issues: 10
```

> Commit `.golangci.yaml` to the repository so that every developer and CI run uses the same rules.

### 2.5 CI Integration

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  ci:
    name: Test · Lint · Build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version-file: go.mod
          cache: true
      - name: Install golangci-lint v2
        run: go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@v2.6.2
      - name: Test with coverage gate (>=80%)
        run: make cover-check COVER_MIN=80
      - name: Lint
        run: make lint
      - name: Build
        run: make build-all
```

### 2.6 Fixing CI Failures

#### Formatting check fails

```
Error: code is not formatted; run 'make fmt' and commit changes
```

Steps to fix:

```bash
make fmt
git add -u
git commit -m "style: run gofmt and goimports-reviser"
git push
```

#### Lint check fails

Reproduce the failure locally before deciding how to fix it:

```bash
# Reproduce the exact CI lint output locally
make lint
```

**Option 1: Fix the code** (preferred)

Follow the linter's suggestion and fix the code. This is the right approach in most cases.

**Option 2: `//nolint` directive** (only for false positives or well-justified exceptions)

```go
// Suppress a linter on a single line
result, _ := someFunc() //nolint:errcheck // error is handled centrally by the caller

// Suppress a linter on an entire function
//nolint:gocyclo // this function is a state machine; high complexity is intentional
func handleStateMachine(state State) {
    // ...
}
```

> **Rule**: every `//nolint` directive must include a comment explaining why it is acceptable. Directives without a reason are considered invalid and should be rejected in code review.

---

## 3 Git Standards

### 3.1 GitHub Flow

The team follows GitHub Flow, with a single long-lived branch `main`:

1. `main` is always deployable
2. Create a feature branch off `main` for every new piece of work
3. Commit continuously on the feature branch and push to remote
4. Open a Pull Request when the work is ready
5. Team members perform code review
6. Merge to `main` once review is approved and CI passes
7. Deployment is triggered automatically after merge

**Pros**: simple process, naturally suited to continuous deployment, enforces code review

**Cons**: no `develop` buffer branch, demands high-quality CI/CD and automated tests

### 3.2 Conventional Commits

#### 3.2.1 Why a Unified Commit Message Format

- Makes it easy to understand what each commit changed when browsing history
- Enables filtering: `git log --oneline --extended-regexp --grep "^(feat|fix|perf)"`
- Supports automatic CHANGELOG generation
- Can trigger build or release pipelines
- Drives semantic versioning (fix → PATCH, feat → MINOR, BREAKING CHANGE → MAJOR)

#### 3.2.2 Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

`type` and `subject` are required; `scope`, `body`, and `footer` are optional.

**type values**

| type | Description | Example |
|------|-------------|---------|
| feat | New feature | feat(auth): add OAuth2 login |
| fix | Bug fix | fix(api): handle nil pointer in GetUser |
| docs | Documentation change | docs: update API README |
| refactor | Refactor (not a feature or bug fix) | refactor(db): simplify connection pool logic |
| perf | Performance improvement | perf(query): add index on user_id |
| test | Test-related change | test(auth): add login edge case |
| chore | Build / tooling / dependency change | chore: upgrade Go to 1.24 |
| style | Code style (no logic change) | style: run gofmt |
| ci | CI configuration | ci: add golangci-lint step |

**scope (optional)**

Identifies the module or domain affected: module name (`auth`, `api`, `db`), package name (`handler`, `repository`), or functional area (`connection-pool`, `rate-limit`).

**subject rules**

- 50 characters or fewer
- Start with an imperative verb: add, fix, update, remove, refactor
- No trailing period
- Describe *what was done*, not *which file was changed*

```bash
# GOOD
feat(auth): add JWT token refresh mechanism
fix(api): prevent race condition in cache update

# BAD
feat(auth): added JWT token refresh mechanism.  # past tense + period
fix: fix bug                                     # no useful information
update code                                      # missing type, vague description
```

**body (optional)**

Explain *why* the change is needed. Record design decisions and trade-offs. Wrap lines at 72 characters.

**footer (optional)**

- `BREAKING CHANGE:` — describes an incompatible change (triggers a major version bump)
- `Closes #123` — links to and automatically closes an issue
- `Refs:` — related links or reference documents

**Full example**

```
feat(connection-pool): add idle connection cleanup

Previously idle connections were never cleaned up, leading to
resource exhaustion under sustained load. This adds a background
goroutine that periodically closes connections idle for more than
ConnMaxIdleTime.

Closes #245
```

#### 3.2.3 Guidelines

- **Atomic commits**: do not mix unrelated changes in a single commit
- **Describe why, not what**: the diff already shows what changed
- **Follow the format**: Conventional Commits format is enforced

#### 3.2.4 Interactive Commit Message Generation

```bash
# Install commitizen
npm install -g commitizen cz-conventional-changelog

# Initialize project config
echo '{ "path": "cz-conventional-changelog" }' > .czrc

# Use in place of git commit
git cz
```

### 3.3 Auto-generating CHANGELOG

```bash
# Install
npm install -g conventional-changelog-cli

# Append to CHANGELOG.md
conventional-changelog -p angular -i CHANGELOG.md -s
```

Auto-categorized: feat → Features, fix → Bug Fixes, BREAKING CHANGE → Breaking Changes.

Maps to semantic versioning: BREAKING CHANGE → major, feat → minor, fix-only → patch.

### 3.4 Branch Naming

Format: `<type>/<short-description>` — lowercase, words separated by hyphens.

| Type | Example | Notes |
|------|---------|-------|
| New feature | feature/oauth-login | Feature branch |
| Bug fix | fix/nil-pointer-getuser | Bug fix |
| Refactor | refactor/db-connection-pool | Refactoring |
| Release | release/v1.2.0 | Release branch |
| Hotfix | hotfix/critical-auth-bypass | Emergency fix |

The team's internal convention links branches to tickets: `feature/tp-4172/tcg-111144`, `fix/tp-4289/tcg-114352`.

**Branch protection rules**

| Rule | main/master | develop |
|------|:-----------:|:-------:|
| No direct push | Yes | Yes |
| Merge via PR only | Yes | Yes |
| At least 1 approval required | Yes | Recommended |
| All CI checks must pass | Yes | Yes |
| No force push | Yes | Yes |

### 3.5 PR Best Practices

**Size**

- One PR, one concern (one feature / one bug / one refactor)
- Keep changes to 200–400 lines
- Split large features into sequential PRs; use feature flags for incomplete work
- Do not mix formatting or refactoring into a feature PR

**PR description template** (`.github/PULL_REQUEST_TEMPLATE.md`)

```markdown
## Summary
<!-- 1–3 sentences describing the purpose of this change -->

## Changes
<!-- List the specific changes made -->
-
-

## Test Plan
<!-- How to verify the change is correct -->
- [ ] Unit tests pass
- [ ] Manually verified scenario X

## Screenshots (if applicable)
<!-- Attach screenshots for UI changes -->
```

**Code review guidelines**

As a reviewer:
- Focus on design and logic; leave style issues to the linter
- Prioritise bugs and security concerns, then maintainability
- Use suggestions, not demands (`nit:` prefix for non-blocking comments)

As an author:
- Self-review the PR before requesting review
- Add review comments on complex logic to explain intent
- Respond to reviewer questions promptly

**CI quality gate**

```yaml
steps:
  - name: Lint
    run: golangci-lint run ./...
  - name: Test
    run: go test -race -coverprofile=coverage.out ./...
  - name: Build
    run: go build ./...
  - name: Coverage Gate
    run: go tool cover -func=coverage.out
```

**Merge strategy**

| Strategy | Command | Effect | When to use |
|----------|---------|--------|-------------|
| Create a merge commit | `git merge --no-ff` | Preserves all commits + merge commit | When full history must be retained |
| **Squash and merge** | `git merge --squash` | Collapses all commits into one | **Team default** |
| Rebase and merge | `git rebase + --ff` | Linear history | When every commit has been carefully crafted |

The team uses **Squash and merge**. Disable unwanted strategies in GitHub repository Settings → General → Pull Requests.

### 3.6 The Golden Rule of Rebase

**Never rebase a branch that has already been pushed to a shared remote.**

Rebasing rewrites SHA-1 hashes, causing teammates to encounter duplicate commits and conflicts when they pull.

Safe rebase scenarios:
- Local feature branch not yet pushed — rebase onto the latest `main`
- Before merging, use `rebase -i` to clean up local commit history
- Use `git pull --rebase` instead of the default merge pull

---

## 4 Project Directory Structure

Go has no mandatory project layout, but the community has converged on well-established conventions.

### 4.1 Three Project Forms

| Form | Characteristics | Examples |
|------|----------------|---------|
| Executable | Has a `main` package; produces a binary | API service, CLI tool, microservice |
| Library | No `main` package; imported by other projects | `golang.org/x/sync`, `go-redis` |
| Hybrid | Both a library and a CLI tool | cobra (library + `cobra-cli` binary) |

**Core principle**: let the structure serve the project's form. A 50-line CLI tool does not need a three-level `cmd/internal/pkg` hierarchy.

### 4.2 Core Directory Conventions

#### 4.2.1 cmd/ — executable entry points

Each subdirectory corresponds to one binary; the directory name becomes the binary name:

```
cmd/
├── server/
│   └── main.go  → go build -o server ./cmd/server
├── worker/
│   └── main.go  → go build -o worker ./cmd/worker
└── cli/
    └── main.go  → go build -o cli ./cmd/cli
```

Rules:
- Each subdirectory is its own `package main`
- Keep `main.go` **thin** — argument parsing, wiring dependencies, and starting the server only; no business logic
- Put actual logic in `internal/` or the root package

```go
// cmd/server/main.go — thin entry point
package main

import (
    "log"
    "myapp/internal/server"
    "myapp/internal/config"
)

func main() {
    cfg, err := config.Load()
    if err != nil {
        log.Fatal(err)
    }
    srv := server.New(cfg)
    if err := srv.Run(); err != nil {
        log.Fatal(err)
    }
}
```

When `cmd/` is unnecessary: if the project produces only one binary, placing `main.go` in the root is perfectly fine.

#### 4.2.2 internal/ — compiler-enforced access control

`internal/` is a **hard constraint enforced by the Go compiler** — packages under `internal/` can only be imported by code in the parent directory tree:

```
myapp/
├── cmd/server/main.go       # OK: can import myapp/internal/...
├── internal/
│   ├── handler/              # OK: can import myapp/internal/service/
│   ├── service/
│   └── repo/
└── pkg/api/                  # OK: can import myapp/internal/... (same module)

# External project:
import "myapp/internal/handler" // compile error!
```

This is **compiler-level** encapsulation — not a convention, not a lint rule, but a **hard limit**.

Recommended `internal/` layout:

```
internal/
├── config/       # configuration loading
├── handler/      # HTTP/gRPC handlers
├── service/      # business logic layer
├── repo/         # data access layer
├── model/        # domain models
└── middleware/   # middleware
```

#### 4.2.3 pkg/ — reusable public packages

`pkg/` holds packages that can be imported by external projects. **Note: `pkg/` is a convention only — the compiler treats it no differently from any other directory.**

Guidelines:
- **Library projects**: organise packages directly in the root; `pkg/` is unnecessary
- **Application projects**: put shared utilities that need to be exposed in `pkg/`; everything else goes in `internal/`

### 4.3 Supporting Directory Conventions

| Directory | Purpose | Example contents |
|-----------|---------|-----------------|
| `api/` | Interface definition files | OpenAPI YAML, Proto files, GraphQL schemas |
| `configs/` | Configuration templates (no secrets) | `config.yaml.example`, `docker-compose.yaml` |
| `scripts/` | Build, install, and analysis scripts | `build.sh`, `migrate.sh` |
| `deployments/` | Deployment artifacts | Dockerfile, Kubernetes YAML, Terraform |
| `test/` | External tests (integration/E2E) | `testdata/`, `integration/`, `e2e/` |
| `docs/` | Documentation | `architecture.md`, `api-guide.md` |
| `tools/` | Development tool dependencies | `tools.go` (tool version pinning), `codegen/` |

> Unit tests live in the same package as the code being tested (`_test.go`), not in `test/`.

Use `tools.go` to pin tool versions in `go.mod`:

```go
//go:build tools

package tools

import (
    _ "golang.org/x/tools/cmd/stringer"
    _ "github.com/golangci/golangci-lint/cmd/golangci-lint"
)
```

### 4.4 Example Directory Layouts

**Small project (CLI tool or simple service)**

```
mytool/
├── main.go
├── app.go
├── app_test.go
├── config.go
├── go.mod
├── go.sum
└── README.md
```

**Medium project (monolithic API service)**

```
myapi/
├── cmd/
│   └── server/
│       └── main.go
├── internal/
│   ├── config/
│   ├── handler/
│   ├── service/
│   ├── repo/
│   ├── model/
│   └── middleware/
├── migrations/
├── configs/
│   └── config.yaml.example
├── go.mod
├── go.sum
├── Makefile
└── README.md
```

**Large project (multiple services + SDK)**

```
platform/
├── cmd/
│   ├── api-server/
│   ├── worker/
│   └── admin-cli/
├── internal/
│   ├── api/          # API service logic
│   ├── worker/       # worker logic
│   ├── shared/       # internal shared code
│   └── model/
├── pkg/
│   ├── sdk/          # externally exposed SDK
│   └── errors/       # shared error types
├── api/
│   └── proto/
├── deployments/
├── scripts/
├── go.mod
├── Makefile
└── README.md
```

### 4.5 Common Mistakes

| Mistake | Explanation |
|---------|-------------|
| **Over-engineering** | A 50-line tool wrapped in a full enterprise layout. Start with `main.go` and a couple of files; refactor as the project grows. |
| **Blindly copying golang-standards/project-layout** | Go team member Russ Cox has stated explicitly that this is not an official Go standard. |
| **A `src/` directory** | Go modules are rooted at `go.mod`. A `src/` directory is neither needed nor idiomatic. |
| **Grouping by type** | `models/`, `controllers/`, `services/` leads to circular imports. Group by domain instead: `user/`, `order/`, `payment/`. |
| **`utils` / `common` / `shared` packages** | Violates the high-cohesion principle. Split by function: `stringx/`, `httputil/`, `timeutil/`. |

### 4.6 Go Toolchain and Directories

```bash
# go build — build programs under cmd/
go build -o bin/server ./cmd/server
go build ./cmd/...

# go test — test the whole project
go test ./...
go test ./internal/service/...

# go install — install to $GOPATH/bin
go install ./cmd/server
go install github.com/you/project/cmd/mytool@latest

# go generate — run all generate directives
go generate ./...
```

### 4.7 Package Sizing Principles

**Size** — small enough to understand, large enough to be self-contained:

| Signal | Consider splitting | Consider merging |
|--------|--------------------|-----------------|
| File count | > 15 files | 1 file + 10 lines |
| Exported symbols | > 30 exported types/functions | Only 1–2 |
| Dependencies | Imports 10+ internal packages | No one imports it |
| Responsibility | Name requires "And" or "Or" | Functionality is fully contained in another package |

**Dependency direction** — one-way, top to bottom:

```
cmd/ → internal/ → model/  (no reverse dependencies)

handler → service → repo → model
    ↓         ↓       ↓
  interfaces defined by the consumer
```

When circular dependencies appear: extract shared types into a dedicated package, decouple with interfaces, or merge overly fragmented packages.

### 4.8 Directory Summary

| Directory | Role | Compiler enforced? | When to use |
|-----------|------|--------------------|------------|
| `cmd/` | Executable entry points | No | When there are multiple binaries |
| `internal/` | Private code; not importable externally | **Yes** | Almost every project |
| `pkg/` | Public, reusable library code | No | When exposing an SDK |
| `api/` | Interface definition files | No | When there are API specs |
| `configs/` | Configuration templates | No | When there are config files |
| `scripts/` | Helper scripts | No | When there are build/deploy scripts |
| `test/` | External test data | No | When there are integration/E2E tests |
| `tools/` | Development tool dependencies | No | When using code generation or similar tools |

---

## 5 Naming and Comments

### 5.1 Package Names

- Package names must match their directory names
- **All lowercase**, no uppercase or underscores: `runtime` not `runTime`, `syscall` not `sysCall`
- **Avoid vague names** like `common`, `util`, `shared`, or `lib`

> "The bigger the interface, the weaker the abstraction." — Go Proverbs
>
> The same applies to package names: **the more generic the name, the less value it provides.**

### 5.2 File Names

- File names should be short and descriptive
- Lowercase, words separated by underscores
- **The package name provides the context; the file name only describes the file's responsibility** — do not repeat the package name

```
# How the Go standard library does it:
net/http/client.go        # not http_client.go
net/http/server.go        # not http_server.go
net/http/transport.go     # not http_transport.go

database/sql/db.go        # not sql_db.go
database/sql/rows.go
database/sql/convert.go
```

Apply the same principle in project code:

```
# Inside internal/apiserver/persistence/cache/
customer.go               # not customer_cache.go
customer_immutable.go
merchant.go
```

### 5.3 Variable Names

- Short names are fine in narrow scopes: `user` → `u`, `userID` → `uid`
- Initialisms follow specific rules:
  - Private, first word: lowercase — `apiClient`
  - All other cases: original casing — `APIClient`, `repoID`, `UserID`
- Common initialisms: `API`, `ASCII`, `CPU`, `CSS`, `DNS`, `EOF`, `HTML`, `HTTP`, `ID`, `IP`, `JSON`, `URL`, `UUID`, `XML`
- Boolean names start with `Has`, `Is`, `Can`, or `Allow`:

```go
var hasConflict bool
var isExist bool
var canManage bool
var allowGitHook bool
```

- Keep local variables short: `buf` instead of `buffer`, `i` instead of `index`
- If a value is used three or more times, declare it as a constant
- **Do not embed type information in variable names**: `users []*User` not `userSlice []*User`
- **Do not repeat the package name** in variable, type, interface, or constant names: `bytes.Buffer` not `bytes.ByteBuffer`

### 5.4 Function Names

- Function names should not repeat the package context: `time.Now()` not `time.NowTime()`
- Keep function names short
- Omit the type name when the return type matches the package name: `time.Add()` returns `Time`
- Include the type name when the return type differs from the package name: `time.ParseDuration()` returns `Duration`

### 5.5 Comments

- **All comments must be written in English**
- **All exported symbols must have a doc comment** (exported variables, constants, structs, functions), in the form `// ObjectName does ...`

```go
// DataNotFound indicates the requested record does not exist.
const DataNotFound ErrorCode = "data_not_found"
```

- Every exported function in a library must be commented (methods implementing an interface are exempt)
- Comments should explain:
  - **What** the code does
  - **How** it does it
  - **Why** it was implemented this way
  - **When** it can go wrong

---

## 6 API Design

### 6.1 RESTful API Overview

REST treats everything as a resource; operations on resources map to HTTP methods (GET/POST/PUT/DELETE). Key characteristics:

- Resource-centric: all behaviour is CRUD on a resource
- Resources are identified by URI; each resource instance has a unique URI
- Resource state is represented as JSON in the HTTP body
- Stateless: each request carries all information needed to complete the operation

### 6.2 RESTful API Design Principles

#### 6.2.1 URI Design

- Resource names use **plural nouns**: `/users`, `/orders`
- No trailing slash in URIs
- No underscores `_` in URIs — use hyphens `-`
- URI paths are lowercase
- Avoid deep nesting (more than 2 levels); move extra context to query parameters:

```bash
# Not recommended
/schools/tsinghua/classes/rooma/students/zhang

# Recommended
/students?school=qinghua&class=rooma
```

#### 6.2.2 HTTP Method Mapping

| Method | Operation | Safe | Idempotent |
|--------|-----------|:----:|:----------:|
| GET | Read | Yes | Yes |
| POST | Create | No | No |
| PUT | Full update | No | Yes |
| DELETE | Delete | No | Yes |

For bulk deletion, use: `DELETE /users?ids=1,2,3` (the team's standard approach).

#### 6.2.3 Unified Response Format

```go
// Success response
type APIBaseValueResp struct {
    Success bool        `json:"success"`
    Value   interface{} `json:"value,omitempty"`
}

// Error response
type APIBaseMessageResp struct {
    Success   bool   `json:"success"`
    ErrorCode string `json:"errorCode,omitempty"`
    Message   string `json:"message,omitempty"`
}
```

#### 6.2.4 API Versioning

Include the version in the URL path: `/v1/users`.

#### 6.2.5 API Naming

Use **kebab-case**: all lowercase, words separated by hyphens. Examples: `selected-actions`, `artifact-id`.

#### 6.2.6 Pagination / Filtering / Sorting / Search

- **Pagination**: `/users?offset=0&limit=20`
- **Filtering**: `/users?fields=email,username,address`
- **Sorting**: `/users?sort=age,desc`
- **Search**: use the `q` parameter for fuzzy matching against relevant fields on the server side (LIKE / full-text); the response structure is identical to a regular list:

```bash
# Fuzzy search by username or email
GET /users?q=john

# Combine with filters and pagination
GET /orders?q=2024-03&status=pending&offset=0&limit=20
```

#### 6.2.7 Common Status Codes

| Code | Meaning | When to use |
|------|---------|-------------|
| 200 OK | Success | GET, PUT, PATCH |
| 201 Created | Resource created | POST creating a resource |
| 204 No Content | No body | DELETE success |
| 400 Bad Request | Malformed request | JSON parse failure |
| 401 Unauthorized | Not authenticated | Missing or invalid token |
| 403 Forbidden | Not authorized | Valid token but insufficient permissions |
| 404 Not Found | Resource does not exist | Query or update on a missing resource |
| 409 Conflict | Conflict | Unique key violation |
| 422 Unprocessable Entity | Validation failed | Field validation errors |
| 429 Too Many Requests | Rate limited | Request rate exceeded |
| 500 Internal Server Error | Server error | Unexpected internal failure |

### 6.3 Middleware Chain

Middleware execution order:

```
Request  → Recovery → CORS → Logging → RateLimit → Auth → Handler
Response ← Recovery ← CORS ← Logging ← RateLimit ← Auth ← Handler
```

Ordering rationale:
- **Recovery** outermost — catches all panics
- **CORS** before auth — OPTIONS preflight must not be blocked by authentication
- **Logging** before business logic — records every request, including rejected ones
- **RateLimit** before auth — prevents brute-force attacks
- **Auth** closest to the handler — only protects routes that require authentication

### 6.4 Error Code System

**Standard error codes**

| Error Code | HTTP Status | gRPC Code | Meaning |
|-----------|:-----------:|-----------|---------|
| invalid_json | 400 | InvalidArgument | Malformed JSON request body |
| validation_failed | 422 | InvalidArgument | Field validation failed |
| unauthorized | 401 | Unauthenticated | Not authenticated |
| forbidden | 403 | PermissionDenied | Authenticated but not authorized |
| not_found | 404 | NotFound | Resource does not exist |
| conflict | 409 | AlreadyExists | Resource conflict |
| rate_limited | 429 | ResourceExhausted | Request rate exceeded |
| internal_error | 500 | Internal | Internal server error |

**AppError implementation**

```go
type AppError struct {
    Code     ErrCode `json:"code"`
    Message  string  `json:"message"`
    Detail   string  `json:"detail,omitempty"`
    internal error   // not serialized; server-side logs only
}
```

Key design: `Code` is a machine-readable string, `Message` is a human-friendly message for the client, and `internal` is never serialized — it exists only in server logs.

### 6.5 Request Validation

**System boundary validation principle**: validate all input at system boundaries; trust internal code.

- **System boundaries**: HTTP handlers, gRPC service entry points, message queue consumers
- **Internal code**: service layer, domain layer — the caller is responsible for ensuring valid arguments

**Struct tags with reflection**

```go
type CreateUserRequest struct {
    Name  string `json:"name"  validate:"required,min=2,max=50"`
    Email string `json:"email" validate:"required,email"`
    Age   int    `json:"age"   validate:"min=0,max=150"`
}

errs := Validate(req)
if len(errs) > 0 {
    WriteValidationError(w, errs)
    return
}
```

| Rule | Example | Description |
|------|---------|-------------|
| required | `validate:"required"` | Non-zero value |
| email | `validate:"email"` | Valid email format |
| min=N | `validate:"min=2"` | Minimum string length / minimum numeric value |
| max=N | `validate:"max=50"` | Maximum string length / maximum numeric value |

**Validation vs. business rules**

| Category | Example | Where to handle | HTTP Status |
|----------|---------|----------------|:-----------:|
| Format validation | "invalid email format" | Handler layer | 422 |
| Business rule | "email already registered" | Service layer | 409 |

### 6.6 gRPC API Design

**Proto design principles**

- Message types are singular: `User`, not `Users`
- Requests and responses come in pairs: `CreateUserRequest` → `User`
- List responses use a dedicated type: `ListUsersResponse` includes pagination info
- ID fields use `string`

**gRPC status code mapping**

```go
// Argument validation failure
return nil, status.Error(codes.InvalidArgument, "name is required")

// Resource not found
return nil, status.Errorf(codes.NotFound, "user %q not found", id)

// Unique key conflict
return nil, status.Errorf(codes.AlreadyExists, "email already registered")
```

**Interceptors**

```go
grpc.NewServer(
    grpc.ChainUnaryInterceptor(
        RecoveryInterceptor,    // catch panics
        LoggingInterceptor,     // log requests
        AuthInterceptor(token), // verify token
    ),
)
```

**gRPC vs REST**

| Dimension | REST | gRPC |
|-----------|------|------|
| Protocol | HTTP/1.1 (JSON) | HTTP/2 (Protobuf) |
| Performance | Moderate | Higher (binary encoding, streaming) |
| Browser support | Native | Requires gRPC-Web |
| Best suited for | Public APIs, frontend | Internal microservice communication |

### 6.7 Authentication and Authorization

**Bearer Token**

```
Authorization: Bearer <token>
```

**401 vs 403**

| Code | Meaning | Scenario |
|------|---------|---------|
| 401 Unauthorized | Not authenticated | No token, token expired/invalid |
| 403 Forbidden | Authenticated but not authorized | Regular user accessing an admin endpoint |

Key distinction: 401 can be resolved by logging in again; 403 cannot, regardless of credentials.

**Rate limiting strategies**

- **Fixed window**: simple, but prone to traffic spikes at window boundaries
- **Sliding window**: smoother, slightly more complex to implement
- **Token bucket**: `golang.org/x/time/rate` — recommended for production
- **Distributed rate limiting**: Redis + Lua script

### 6.8 API Design Checklist

Review each of the following before publishing an API endpoint:

- [ ] Resource naming: plural nouns, lowercase, no verbs
- [ ] HTTP method: semantically correct
- [ ] Status codes: precisely matched (201 for create, 204 for delete, 422 for validation failure)
- [ ] Error format: uses the unified error response
- [ ] Pagination: list endpoints support `offset` / `limit`
- [ ] Versioning: URL path includes a version number
- [ ] Authentication: protected endpoints require Bearer Token
- [ ] Authorization: 401 and 403 are correctly distinguished
- [ ] Rate limiting: configured and returns 429 + `Retry-After`
- [ ] Idempotency: POST creation supports `Idempotency-Key`
- [ ] CORS: cross-origin headers correctly configured
- [ ] Input validation: all input validated at system boundaries
- [ ] No error leakage: internal error details are not exposed to the client

---

## 7 Swagger API Documentation

The team uses Swagger as the standard for API documentation, generated automatically from code — never written by hand.

### 7.1 Installation

```bash
# Install the swag CLI tool (used to generate docs)
go install github.com/swaggo/swag/cmd/swag@v1.16.4

# Verify
swag --version
# swag version v1.16.4

# Add library dependencies to the project (these are imported packages, not CLI tools)
go get github.com/swaggo/fiber-swagger   # Fiber framework adapter
go get github.com/swaggo/files           # Swagger UI static assets
```

> **Note**: `fiber-swagger` and `files` are libraries imported by your code. Add them via `go get` so they are tracked in `go.mod`. For Gin projects, replace `fiber-swagger` with `github.com/swaggo/gin-swagger`.

### 7.2 Adding Swagger Annotations to Handlers

```go
// GetCountriesByCode godoc
//
// @Summary     List countries by code
// @Description Returns the list of countries associated with the provided country code.
// @Tags        country
// @Accept      json
// @Produce     json
// @Param       countryCode query string false "Country code to filter (optional)"
// @Success     200 {object} dto.APIBaseValueResp
// @Failure     500 {object} dto.APIBaseMessageResp
// @Router      /tcg-uss-ae/country [get]
func (h *Handler) GetCountriesByCode(c *fiber.Ctx) error {
    countryCode := c.Query("countryCode")
    res, err := h.svc.GetCountriesByCode(c.UserContext(), countryCode)
    if err != nil {
        return apperror.NewSimple(consts.ModuleCountry, code.DataNotFound,
            fmt.Sprintf("country not found by countryCode:%s", countryCode))
    }
    return c.JSON(res)
}
```

### 7.3 Generating and Viewing Docs

```bash
# Run from the project root; generates Swagger docs into docs/
swag init

# Open the Swagger UI in a browser
# http://localhost:7001/swagger/index.html
```

---

## Document Maintenance

**Review cadence**: quarterly (confirm that content is still consistent with the current toolchain versions at the end of each quarter).

**Mandatory update triggers**:

| Trigger | Affected sections |
|---------|------------------|
| Go version upgrade (changes to `go.mod`) | 1.1, 1.2, 2.3, 2.5 |
| golangci-lint version upgrade | 2.3, 2.4, 2.5 |
| Makefile target changes | 1.4 |
| CI pipeline changes (steps added or removed) | 1.3, 2.5 |
| API response format or error code changes | 6.2.3, 6.4 |
| Team Git workflow changes | 3.1, 3.4, 3.5 |
| A "followed the doc but it failed" report | Relevant section |

**Document owner**: `team` (specific owner assigned by each team's TL)

---

## Glossary

| Term | Description |
|------|-------------|
| gofmt | Go's built-in code formatter |
| goimports-reviser | Tool for grouping and sorting import statements |
| golangci-lint | Aggregated static analysis runner for Go |
| Conventional Commits | A structured commit message convention |
| GitHub Flow | A minimal workflow with `main` as the only long-lived branch |
| Squash and merge | Collapses all commits in a PR into a single commit before merging |
| kebab-case | All-lowercase naming with words separated by hyphens |

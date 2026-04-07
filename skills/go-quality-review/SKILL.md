---
name: go-quality-review
description: Review Go code for code quality, style, and modern Go practices including function length, nesting depth, naming, mutable globals, interface design, receiver consistency, modern Go idioms (slog, generics, typed atomics), and static analysis. Trigger when reviewing Go code structure, readability, or maintainability. Also runs golangci-lint for automated style checks.
allowed-tools: Read, Grep, Glob, Bash(go build*), Bash(go vet*), Bash(golangci-lint*), Bash(gofmt*)
---

# Go Quality Review

## Purpose

Audit Go code for structural quality, style conformance, and modern Go practices. This skill is the **designated lint-tool runner** — other vertical review skills do NOT run golangci-lint/staticcheck/go vet, avoiding duplicate execution.

This skill does NOT cover: security, concurrency, performance, error handling, test quality, or business logic — those belong to sibling vertical skills.

## When To Use
- Reviewing code structure and readability
- Checking Go naming conventions and package organization
- Evaluating use of modern Go features
- Need to run `golangci-lint` / `staticcheck` / `go vet`

## When NOT To Use
- Security vulnerabilities → `go-security-review`
- Concurrency safety → `go-concurrency-review`
- Error handling correctness → `go-error-review`
- Performance optimization → `go-performance-review`
- Business logic → `go-logic-review`

## Mandatory Gates

### 1) Go Version Gate
Read `go.mod` for `go` directive. Do NOT recommend features above project version.

| Feature | Minimum Go |
|---------|-----------|
| Generics | 1.18 |
| Typed atomics (`atomic.Int64`, `atomic.Bool`) | 1.19 |
| `slog`, `slices`/`maps` packages, `min`/`max` builtins, `sync.OnceValue`/`OnceFunc` | 1.21 |
| Range-over-func, enhanced loop variable semantics | 1.22 |
| `iter.Seq`, `unique` package | 1.23 |

### 2) Anti-Example Suppression Gate
MUST quote specific code evidence. Category match alone insufficient.

Embedded anti-examples:
- **"Should use generics"** — when only one concrete type used throughout codebase. Generics add complexity without benefit for single-type usage.
- **"Should use slog"** — when project targets Go < 1.21. Version-inappropriate recommendation.
- **"Should use typed atomics"** — when project targets Go < 1.19.
- **"Exported function missing godoc"** — when symbol is in `internal/` package not intended for external consumers.
- **"Function too long (>50 lines)"** — when body is a straightforward table-driven switch, sequential pipeline with no nesting, or single select/case block. These are long but simple.
- **"interface{} should be any"** — pure cosmetic alias rename. Report only as part of broader modernization effort, never as standalone finding.
- **"Should extract helper function"** — when the code would only be called from one place and extraction reduces readability by splitting context.

### 3) Static Analysis Execution Protocol
Run lint tools in this priority order:
1. Check for `.golangci.yml` / `.golangci.yaml` — respect project config
2. `golangci-lint run` (config-aware)
3. `staticcheck ./...` (if golangci-lint unavailable)
4. `go vet ./...` (minimal fallback)
Report tool output in Execution Status. If no tools available, state `Not available`.
**Dedup rule**: same location + same issue from multiple tools = report once.

### 4) Generated Code Exclusion Gate
Exclude: `*.pb.go`, `*_gen.go`, `mock_*.go`, `*_string.go`, `*_enumer.go`. Note excluded files in Execution Status.

## Workflow

1. **Define scope** — files/diff under review. Apply Generated Code Exclusion Gate.
2. **Check Go version** from `go.mod` — gate all modern Go recommendations.
3. **Run static analysis** — follow execution protocol above. Record output.
4. **Gather evidence** — read changed files, identify quality/style patterns.
5. **Load references** — always load `go-error-and-quality.md` (quality sections); load `go-modern-practices.md` when modern Go features relevant.
6. **Evaluate ALL 13 checklist items** → cross-reference with lint output → suppress anti-examples → format.

## Grep-Gated Execution Protocol

This skill uses mechanical grep pre-scanning to guarantee zero missed checklist items. 8 of 13 items are grep-gated; 5 are semantic-only.

### Execution Order
1. Identify target files (from dispatch prompt, or write raw snippet to `$TMPDIR/review_snippet.go`)
2. Run grep for all grep-gated checklist items against target files
3. **HIT** → run semantic analysis to confirm or reject
4. **MISS** → auto-mark NOT FOUND, skip semantic analysis
5. For semantic-only items (items 1, 2, 5, 9, 13): full model reasoning — these require structural analysis
6. Report only FOUND items

### Grep Audit Line
Include in Execution Status: `Grep pre-scan: X/8 items hit, Z confirmed as findings (5 semantic-only)`

## Quality Checklist (12 Items)

All Medium severity unless marked (Low).

| # | Item | Pattern | Grep Pattern |
|---|------|---------|-------------|
| 1 | **Function too long** | > 50 lines → extract helper (see anti-example for flat switch exception) | Semantic-Only (function length requires counting lines — no grep pattern) |
| 2 | **Excessive nesting** | > 4 levels → early return pattern ("happy path left-aligned") | Semantic-Only (nesting depth requires counting indent levels) |
| 3 | **Naked return** | In functions > 5 lines → explicit returns for clarity | `return$\|return\s*$` (naked return — grep for `return` with nothing after) |
| 4 | **Mutable global variable** | Mutable `var` at package level → `const`, getter, or functional options | `^var\s+\w` (package-level var declarations — grep at file scope) |
| 5 | **Interface bloat** | Interface > 3 methods or defined at implementation site → small interfaces at consumer site | Semantic-Only (interface bloat requires counting methods) |
| 6 | **Type assertion without ok** | `x.(T)` without comma-ok → `x, ok := x.(T)` — panics on wrong type | `\.\(\w` (type assertion without comma-ok check) |
| 7 | **defer in loop** | Defer accumulates until function return → extract to helper function | `defer\s+` (compound: inside `for` loop — semantic confirmation) |
| 8 | **init() misuse** | `init()` for non-registration logic → explicit initialization | `func init\(\)` |
| 9 | **Inconsistent receiver type** | Mixed pointer/value receivers on same type → consistent choice | Semantic-Only (receiver consistency requires checking all methods on type) |
| 10 | **Modern Go alternatives** | Outdated patterns when modern alternatives exist (version-gated): `log` → `slog`, `atomic.AddInt64` → `atomic.Int64`, `sort.Slice` → `slices.SortFunc` | `log\.\|atomic\.Add\|sort\.Slice` (outdated patterns when modern alternatives exist) |
| 11 | **Generics vs interfaces** | Wrong choice — type operations (containers, transforms) → generics; behavior contracts → interfaces | `interface\s*\{\|interface\{\|any\b` |
| 12 | **Naming / package structure** (Low) | Stuttering (`user.UserService`), package `utils`/`helpers`/`common`, unexported type in exported return | `\.User\w*Service\|\.User\w*Handler\|package\s+utils\|package\s+helpers\|package\s+common` |
| 13 | **Missing context.Context on I/O function** | Function performing DB / HTTP / cache / Redis I/O but signature lacks `ctx context.Context` as first parameter — queries cannot be cancelled on client disconnect or upstream timeout. Fix: add `ctx context.Context` first, then `.WithContext(ctx)` (GORM), `http.NewRequestWithContext(ctx, ...)`, `redis.*Cmd(ctx, ...)` etc. | Semantic-Only (absence-of-pattern: requires reading both the signature and the body to identify I/O calls without ctx propagation) |

## Severity Rubric

**Medium** — Maintainability/readability issue increasing cognitive load or bug risk.

**Low** — Style preference or minor inconsistency.

## Evidence Rules
- For each finding: show current pattern vs idiomatic alternative
- For lint findings: include tool name and rule ID when available
- **Merge rule**: same issue at ≥3 locations → one finding with location list
- Dedup with lint: if lint flagged it, use lint output as evidence

## Output Format

### Findings
#### [Medium|Low] Short Title
- **ID:** QUAL-NNN
- **Location:** `path:line`
- **Impact:** Maintenance/readability consequence
- **Evidence:** Current pattern vs idiomatic alternative
- **Recommendation:** Specific refactoring suggestion
- **Action:** `follow-up`

### Suppressed Items
#### [Suppressed] Short Title
- **Reason:** Anti-example matched + evidence cited

### Execution Status
- `Go version`: X.Y
- `Grep pre-scan`: X/8 items hit, Z confirmed as findings (5 semantic-only)
- `golangci-lint`: PASS | FAIL | Not available
- `staticcheck`: PASS | FAIL | Covered by golangci-lint | Not available
- `go vet`: PASS | FAIL | Covered by golangci-lint | Not available
- `Excluded (generated)`: list or None
- `References loaded`: list

### Summary
1-2 lines. Count by severity + lint status.

## Example Output

```
### Findings

#### [Medium] Function Exceeds 50 Lines with Deep Nesting
- **ID:** QUAL-001
- **Location:** `internal/service/order.go:45-120`
- **Impact:** 75-line function with 5 nesting levels — high cognitive load, hard to test individual branches
- **Evidence:** `ProcessOrder()` has nested if/for/if/switch/case structure. Unlike a flat switch (anti-example), this has complex branching.
- **Recommendation:** Extract inner switch into `classifyOrderType()` and validation into `validateOrderItems()`
- **Action:** follow-up

#### [Medium] Mutable Package-Level Variable
- **ID:** QUAL-002
- **Location:** `internal/config/defaults.go:8`
- **Impact:** `var DefaultTimeout = 30 * time.Second` — any package can mutate, non-deterministic in tests
- **Evidence:** Written at L8, read from 4 packages. golangci-lint: `gochecknoglobals`
- **Recommendation:** Change to `const` or getter: `func DefaultTimeout() time.Duration { return 30 * time.Second }`
- **Action:** follow-up

### Suppressed Items
#### [Suppressed] Long Function — Table-Driven Switch
- **Reason:** `routeRequest()` at router.go:30 is 60 lines but flat switch on HTTP method, no nesting. Anti-example: "straightforward table-driven switch"

### Execution Status
- Go version: 1.21
- golangci-lint: PASS (2 warnings reported above)
- staticcheck: Covered by golangci-lint config
- go vet: Covered by golangci-lint config
- Excluded (generated): None
- References loaded: go-error-and-quality.md, go-modern-practices.md

### Summary
2 Medium findings (function length, mutable global). Lint clean except reported items.
```

## No-Finding Case
If no issues found: state `No code quality findings identified.` Still output Execution Status (lint results always reported).

## Load References Selectively

| Reference | Load When |
|-----------|-----------|
| `references/go-error-and-quality.md` | Always (code quality sections) |
| `references/go-modern-practices.md` | Code uses or could benefit from modern Go features |
| `references/go-review-anti-examples.md` | Always |

## Review Discipline
- **Code quality, style, modern practices, and lint only** — not security, concurrency, errors, performance, tests, or logic
- **Designated lint runner** — this skill runs golangci-lint; other skills reference its output
- Execute ALL 13 checklist items
- Version-gate all modern Go recommendations — check go.mod before recommending
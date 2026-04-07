---
name: go-performance-review
description: Review Go code for performance issues including slice/map pre-allocation, string concatenation, N+1 queries, connection pool configuration, sync.Pool, memory alignment, lock scope, buffered I/O, and HTTP transport tuning. Trigger when code contains make(), loops, database queries, string building, sync primitives, HTTP clients, or hot-path operations. Use for performance-focused review.
allowed-tools: Read, Grep, Glob, Bash(go build*), Bash(go vet*), Bash(go test -bench*)
---

# Go Performance Review

## Purpose

Identify performance issues and resource inefficiency in Go code. This skill exists because performance findings are almost all Medium severity and get systematically crowded out when mixed with High-severity Security/Concurrency findings.

Important distinction: **lock contention** is performance (here); **race condition** is concurrency (`go-concurrency-review`).

This skill does NOT cover: security, concurrency correctness, code style, test quality, error handling, or business logic — those belong to sibling vertical skills.

## When To Use
- Code contains `make([]T, ...)` or `make(map[K]V, ...)`
- Code builds strings in loops
- Code queries DB/Redis inside loops
- Code configures connection pools or HTTP clients
- Code runs on hot paths (per-request, high-frequency)

## When NOT To Use
- Security vulnerabilities → `go-security-review`
- Race conditions, goroutine leaks → `go-concurrency-review`
- Code style/lint → `go-quality-review`
- Error handling → `go-error-review`

## Mandatory Gates

### 1) Go Version Gate
Read `go.mod`. Key: `strings.Clone` (1.20+), `slices.Clone` (1.21+).

### 2) Anti-Example Suppression Gate
MUST quote specific evidence. Category match alone insufficient.

Embedded anti-examples:
- **"Should pre-allocate slice"** — when slice is small (<16 elements) or size is truly unknown at creation time. Must cite evidence the slice is large and size is known.
- **"Should use sync.Pool"** — when object is small and allocated infrequently (cold path, startup, config).
- **"Struct fields should be reordered"** — when struct has <4 fields or alignment savings <8 bytes.
- **"Should use strings.Clone"** — when both substring and parent are short-lived locals in same GC scope.
- **"Add Count-First guard"** — when the business domain guarantees the query always returns rows (e.g., seeded reference data, system-level lookups). Must cite evidence that total==0 is impossible in practice.
- **Hot-path rule**: Do NOT flag performance issues in cold-path code (startup, one-time init, config loading, test setup, CLI argument parsing). Must cite evidence of hot-path execution: "called per HTTP request", "inside for loop over N items", "in handler serving N QPS".

### 3) Generated Code Exclusion Gate
Exclude: `*.pb.go`, `*_gen.go`, `mock_*.go`.

## Workflow

1. **Define scope** — files/diff under review. Apply Generated Code Exclusion Gate.
2. **Gather evidence** — read changed files, identify performance-relevant patterns: `make()`, `append()`, loops, DB queries, `strings.Builder`, `sync.Pool`, HTTP clients.
3. **Load references** — always load `go-performance-patterns.md`; load `go-database-patterns.md` when DB code present.
4. **Classify hot-path vs cold-path** — only flag issues in frequently executed code. Cite execution frequency evidence.
5. **Evaluate ALL 13 checklist items with quantification** → suppress cold-path items → format output.

## Grep-Gated Execution Protocol

This skill uses mechanical grep pre-scanning to guarantee zero missed checklist items. 11 of 13 items are grep-gated; 2 are semantic-only.

### Execution Order
1. Identify target files (from dispatch prompt, or write raw snippet to `$TMPDIR/review_snippet.go`)
2. Run grep for all grep-gated checklist items against target files
3. **HIT** → run semantic analysis to confirm or reject (verify hot-path, quantify impact)
4. **MISS** → auto-mark NOT FOUND, skip semantic analysis
5. For compound patterns: run primary grep, then check secondary condition
6. For semantic-only items (items 6, 9): full model reasoning
7. Report only FOUND items

### Grep Audit Line
Include in Execution Status: `Grep pre-scan: X/11 items hit, Z confirmed as findings (2 semantic-only)`

### Key Compound Pattern: Slice Pre-allocation (Item 1)
This is the highest-priority compound pattern — it catches the most common performance miss:
- Primary: `make\(\[\]` HIT
- Secondary: check if the make call has only 2 args (no capacity) AND an upper bound is known (e.g., `len(input)`)
- Example: `make([]*User, 0)` when `len(userKeys)` is available → FINDING

## Performance Checklist (12 Items)

All Medium severity unless marked (Low).

| # | Item | Quantification Pattern | Grep Pattern |
|---|------|----------------------|-------------|
| 1 | **Missing slice pre-allocation** | `make([]T, 0)` when upper bound known → "N grow-and-copy → 1 allocation" | `make\(\[\]` (compound: AND NOT 3-arg make with capacity — check for `make\(\[\][^,]+,\s*\d+,\s*\d+\)` absent) |
| 2 | **String concatenation in loop** | `+=` in loop → `strings.Builder` + `Grow()` — "N allocations + N copies → 1" | `\+=\s*""\|\+=\s*\w+\s*$` (compound: inside `for` loop — semantic confirmation) |
| 3 | **N+1 query** | Individual DB/Redis calls in loop → batch `WHERE IN` or pipeline — "N round-trips → 1" | `\.Query\|\.Exec\|\.Get\|\.Set` (compound: inside `for` loop — N+1 detection) |
| 4 | **Missing connection pool config** | Missing `SetMaxOpenConns`, `SetMaxIdleConns`, `SetConnMaxLifetime` — connection exhaustion risk | `SetMaxOpenConns\|SetMaxIdleConns\|SetConnMaxLifetime\|sql\.Open\|pgx\.Connect` |
| 5 | **Missing sync.Pool** | Hot-path allocations without pooling; pool without Reset before Put — quantify allocation frequency | `sync\.Pool` |
| 6 | **Struct memory alignment** | Fields poorly ordered → `fieldalignment` tool — quantify savings in bytes per instance | Semantic-Only (struct field alignment requires counting fields and sizes) |
| 7 | **Substring memory retention** | Large string sliced, small substring retains backing array → `strings.Clone` (Go 1.20+) | `strings\.Clone\|[:]\w*\]` (substring retention — semantic confirmation required) |
| 8 | **Oversized lock scope** | Mutex where `atomic` suffices; critical section includes non-critical I/O — quantify contention | `sync\.Mutex\|sync\.RWMutex\|\.Lock\(\)` (compound: check if lock held across I/O) |
| 9 | **Missing sharded lock** (Low) | Single mutex on high-contention data → sharded locks — only for proven bottleneck | Semantic-Only (sharded lock pattern requires understanding contention — rarely applicable) |
| 10 | **Missing buffered I/O** | Frequent small reads/writes without `bufio` — "5-50x syscall reduction" | `os\.Open\|os\.Create\|os\.Write\|os\.Read\|net\.Conn` (compound: AND NOT `bufio\.`) |
| 11 | **Inefficient JSON encoding** | `json.Marshal`/`Unmarshal` on stream → `json.NewEncoder`/`Decoder` — "eliminates []byte allocation" | `json\.Marshal\|json\.Unmarshal` (compound: AND stream-compatible context — semantic) |
| 12 | **Untuned HTTP Transport** | `http.DefaultClient` without timeout; `MaxIdleConnsPerHost` default 2 too low for high-throughput | `http\.DefaultClient\|http\.Get\|http\.Post\|http\.Client` |
| 13 | **Missing Count-First guard in pagination query** | Function returns `(list, total)` with a `Count` + `Find` pair but no zero-guard. Reorder to Count-First: run `Count` → if `total == 0` return early → only then run `Find`. Eliminates `Find` DB round-trip (full row-data transfer) for empty result sets — common for new tenants, inactive users, sparse data. Anti-example: when business domain guarantees total always > 0 (seeded reference tables, system lookups). | `\.Count\(&` (compound: confirm `.Find\(` also present in same function AND no `if.*total.*==.*0` or `if total == 0` early-exit guard) |

## Severity Rubric

**Medium** — Performance issue impacting latency, throughput, or resource usage under load.

**Low** — Minor optimization with limited real-world impact.

## Evidence Rules
- **Quantify when possible**: "N+1 executes N round-trips", "slice grows through log2(N) allocations"
- For pre-allocation: state the known upper bound and current allocation
- **Hot-path requirement**: cite evidence code runs frequently (per-request, in loop, high-QPS handler)
- Do NOT flag cold-path optimizations
- **Merge rule**: same issue at ≥3 locations → one finding with location list

## Output Format

### Findings
#### [Medium|Low] Short Title
- **ID:** PERF-NNN
- **Location:** `path:line`
- **Impact:** Quantified performance consequence (allocations, syscalls, round-trips)
- **Evidence:** Current code vs optimal pattern
- **Recommendation:** Specific fix with code example
- **Action:** `follow-up` (performance issues are rarely `must-fix`)

### Suppressed Items
#### [Suppressed] Short Title
- **Reason:** Anti-example matched + evidence cited (cold-path, small size, etc.)

### Execution Status
- `Go version`: X.Y
- `Grep pre-scan`: X/11 items hit, Z confirmed as findings (2 semantic-only)
- `Excluded (generated)`: list or None
- `References loaded`: list

### Summary
1-2 lines. Count by severity.

## Example Output

```
### Findings

#### [Medium] Slice Pre-allocation Missing in Hot Path
- **ID:** PERF-001
- **Location:** `internal/service/batch.go:42`
- **Impact:** len(userIDs) allocations per request instead of 1 — slice grows via append in loop processing user batch
- **Evidence:** `results := make([]User, 0)` at L42; `results = append(results, user)` in loop at L48; `len(userIDs)` is known at L40
- **Recommendation:** `results := make([]User, 0, len(userIDs))`
- **Action:** follow-up

#### [Medium] N+1 Query in Order Processing
- **ID:** PERF-002
- **Location:** `internal/service/order.go:55-60`
- **Impact:** N database round-trips per batch — one SELECT per order item
- **Evidence:** `for _, item := range items { product, _ := repo.GetProduct(ctx, item.ProductID) }` — N individual queries
- **Recommendation:** Batch: `products, err := repo.GetProductsByIDs(ctx, productIDs)` with `WHERE id IN (?)`
- **Action:** follow-up

### Suppressed Items
#### [Suppressed] Slice Pre-allocation in Config Loading
- **Reason:** `make([]Plugin, 0)` at config.go:12 — cold path (called once at startup, typically <5 plugins). Anti-example: "small slice in cold path"

### Execution Status
- Go version: 1.21
- Excluded (generated): None
- References loaded: go-performance-patterns.md, go-database-patterns.md

### Summary
2 Medium findings (slice pre-allocation, N+1 query). Cold-path items suppressed.
```

## No-Finding Case
If no issues found: state `No performance findings identified.` Still output Execution Status.

## Load References Selectively

| Reference | Load When |
|-----------|-----------|
| `references/go-performance-patterns.md` | Always |
| `references/go-database-patterns.md` | Code involves database queries, connection pools |
| `references/go-review-anti-examples.md` | Always |

## Review Discipline
- **Performance only** — not security, concurrency, quality, tests, errors, or logic
- **Execute ALL 13 checklist items** — this is the most commonly skipped dimension; isolation solves that
- **Distinguish hot-path vs cold-path**: only flag frequently executed code
- **Quantify impact** — "costs N allocations per request" is better than "suboptimal"
---
name: go-concurrency-review
description: Review Go code for concurrency safety and goroutine lifecycle issues including race conditions, deadlocks, goroutine leaks, mutex misuse, and context propagation. Trigger when code contains go func, channels, sync primitives, WaitGroup, errgroup, or goroutine lifecycle management. Use for concurrency-focused review of Go projects.
allowed-tools: Read, Grep, Glob, Bash
---

# Go Concurrency Review

## Purpose

Identify concurrency defects and goroutine lifecycle issues in Go code. Scope: race conditions, deadlocks, goroutine leaks, mutex misuse, context propagation, and lifecycle management.

This skill does NOT cover: security vulnerabilities, performance optimization, code style, test quality, error handling patterns, or business logic — those belong to sibling vertical skills.

## When To Use
- Code contains `go func`, goroutine creation
- Code uses channels, `sync` primitives (Mutex, RWMutex, WaitGroup)
- Code uses `errgroup`, `singleflight`
- Code involves context propagation and cancellation
- Code contains graceful shutdown logic

## When NOT To Use
- Security vulnerabilities → `go-security-review`
- Performance optimization (lock contention as perf issue) → `go-performance-review`
- Code style/lint → `go-quality-review`
- Error handling correctness → `go-error-review`
- Business logic → `go-logic-review`

## Mandatory Gates

### 1) Execution Integrity Gate
Never claim `go test -race` ran unless it actually produced output. If not run: state reason + exact command.

### 2) Go Version Gate
Read `go.mod` for `go` directive. Key version gates:
- `errgroup.SetLimit` (Go 1.20+)
- `sync.OnceValue` / `sync.OnceFunc` (Go 1.21+)
- Loop variable fix (Go 1.22+) — do NOT flag loop variable capture in Go ≥ 1.22

### 3) Anti-Example Suppression Gate
MUST quote specific code evidence satisfying precondition. Category match alone insufficient.

Embedded anti-examples:
- **"Race condition on this map"** — when map is created and consumed within single function scope or single goroutine. Cite the creation site and all access sites to confirm single-goroutine usage.
- **"Should use errgroup instead of WaitGroup"** — when no error propagation is needed and goroutine count is small and fixed (e.g., 2-3 known goroutines).
- **"Missing context propagation"** — when function is synchronous, short-lived, performs no I/O, and has no cancellable work.
- **"Loop variable capture bug"** — when project uses Go ≥ 1.22 (check go.mod). The loop variable fix makes `v := v` unnecessary.
- **"Should add mutex"** — when data structure is only written during initialization (before any goroutine launch) and only read afterward.

### 4) Generated Code Exclusion Gate
Exclude: `*.pb.go`, `*_gen.go`, `mock_*.go`. Note excluded files in Execution Status.

## Workflow

1. **Define scope** — files/diff under review. Apply Generated Code Exclusion Gate.
2. **Gather evidence** — read changed files, identify concurrency patterns: `go func`, `chan`, `sync.*`, `errgroup`, `context.WithCancel`, `select`, `time.After`.
3. **Load references** — always load `go-concurrency-patterns.md`.
4. **Run `go test -race`** if feasible — report output. If not feasible, state reason + exact command.
5. **Evaluate ALL 14 checklist items** → apply suppression gate → format output.

## Grep-Gated Execution Protocol

This skill uses mechanical grep pre-scanning to guarantee zero missed checklist items. 13 of 14 items are grep-gated; 1 is semantic-only.

### Execution Order
1. Identify target files (from dispatch prompt, or write raw snippet to `$TMPDIR/review_snippet.go`)
2. Run grep for all grep-gated checklist items against target files
3. **HIT** → run semantic analysis to confirm or reject
4. **MISS** → auto-mark NOT FOUND, skip semantic analysis
5. For compound patterns: run all grep patterns, apply AND/AND NOT logic
6. For semantic-only items (item 13): full model reasoning
7. Report only FOUND items

### Grep Audit Line
Include in Execution Status: `Grep pre-scan: X/13 items hit, Z confirmed as findings (1 semantic-only)`

### Compound Pattern Protocol
Several items share the trigger `go\s+func` but have different secondary conditions:
- Item 8 (Unrecovered panic): `go\s+func` HIT AND `recover()` NOT found in goroutine body
- Item 12 (Loop variable capture): `go\s+func` HIT AND inside `for` loop AND Go version < 1.22
- Item 14 (Unbounded goroutines): `go\s+func` HIT AND NONE of `SetLimit|semaphore|maxConcurrency|worker.*pool|make(chan struct` found in same scope

Run `go\s+func` grep ONCE, then apply all compound conditions to the results.

## Concurrency Checklist (14 Items)

All High severity unless marked (Medium).

| # | Item | Code Pattern Triggers | Grep Pattern |
|---|------|-----------------------|--------------|
| 1 | **Goroutine leak** | `go func` without context cancel or channel close on return path | `go\s+func\|go\s+\w+\(` |
| 2 | **Data race** | Shared map/slice/var written from multiple goroutines without sync | `go\s+func` (compound: ALSO check shared variable write in closure — semantic confirmation required) |
| 3 | **Mutex misuse** | Missing `defer mu.Unlock()`, lock copying (value receiver on mutex-holding struct), inconsistent RWMutex | `sync\.Mutex\|sync\.RWMutex` |
| 4 | **Channel deadlock** | Unbuffered send without receiver, missing `close()`, `select` without `default` on full channel | `make\(chan\|<-chan\|chan<-\|<-\s*\w+` |
| 5 | **Missing errgroup** | Multiple goroutines coordinated without error propagation — should use `errgroup.Group` | `sync\.WaitGroup\|wg\.` |
| 6 | **Missing context propagation** | `context.Background()` where parent ctx available; `context.Value` for request-scoped data | `context\.Background\(\)\|context\.TODO\(\)\|context\.Value` |
| 7 | **sync.Pool / sync.Once misuse** | Pool without Reset before Put; Once panic caching (Go < 1.21, use OnceValue after) | `sync\.Pool\|sync\.Once` |
| 8 | **Unrecovered goroutine panic** | Spawned goroutine without `defer func() { recover() }()` — unrecovered panic crashes process | `go\s+func` (compound: AND NOT `recover\(\)` in goroutine body — semantic confirmation required) |
| 9 | **Missing graceful shutdown** | No shutdown sequence: stop accepting → drain in-flight → cleanup resources | `http\.Server\|ListenAndServe\|Shutdown` |
| 10 | **Timer/Ticker leak** | `time.After` in loop (allocates each iteration), `ticker.Stop()` not called | `time\.After\|time\.NewTicker\|time\.NewTimer` |
| 11 | **Misplaced WaitGroup.Add** | `Add` inside goroutine instead of before `go` statement — must happen-before | `wg\.Add\|WaitGroup` |
| 12 | **Loop variable capture** (Go < 1.22) | Missing `v := v` shadow in goroutine closure — check Go version first | `go\s+func` (compound: check if inside `for` loop — version-gated by Go < 1.22) |
| 13 | **Missing singleflight** (Medium) | Concurrent identical requests without deduplication — cache stampede risk | Semantic-Only (no grep pattern — requires understanding concurrent request patterns) |
| 14 | **Unbounded goroutine creation** | One goroutine per request/item without semaphore, worker pool, or `errgroup.SetLimit` | `go\s+func` (compound: AND NOT `SetLimit\|semaphore\|maxConcurrency\|worker.*pool\|make\(chan\s+struct`) |

## Severity Rubric

**High** — Confirmed crash, data corruption, or resource leak: race condition, deadlock, goroutine leak, panic propagation.

**Medium** — Potential issue under specific conditions: unbounded goroutines under high load, missing singleflight for cache.

## Evidence Rules
- For races: identify the shared variable, the concurrent access points, and the missing synchronization
- For goroutine leaks: identify creation point and the missing cancellation/close path
- `go test -race` output is strongest evidence — run when feasible
- **Merge rule**: same issue at ≥3 locations → one finding with location list

## Output Format

### Findings
#### [High|Medium] Short Title
- **ID:** CONC-NNN
- **Location:** `path:line`
- **Impact:** Runtime consequence (panic, corruption, leak, deadlock)
- **Evidence:** Concurrent access paths or missing synchronization
- **Recommendation:** Specific fix (mutex, channel, errgroup, context)
- **Action:** `must-fix` | `follow-up`

### Suppressed Items
#### [Suppressed] Short Title
- **Reason:** Anti-example matched + evidence cited

### Execution Status
- `Go version`: X.Y
- `Grep pre-scan`: X/13 items hit, Z confirmed as findings (1 semantic-only)
- `go test -race`: PASS | FAIL | Not run (reason + command)
- `Excluded (generated)`: list or None
- `References loaded`: list

### Summary
1-2 lines with finding count.

## Example Output

```
### Findings

#### [High] Race Condition on Package-Level Map
- **ID:** CONC-001
- **Location:** `internal/cache/store.go:12,15`
- **Impact:** Concurrent HTTP handlers write to shared map — will panic with "concurrent map writes" under load
- **Evidence:** `var store = map[string]string{}` at L5; `store[k] = v` in Set() at L12 called from handler goroutines; no mutex protection
- **Recommendation:** Use `sync.RWMutex` to protect map access, or replace with `sync.Map` if read-heavy
- **Action:** must-fix

#### [Medium] Unbounded Goroutine Creation
- **ID:** CONC-002
- **Location:** `internal/worker/dispatch.go:34`
- **Impact:** Under high load, creates unbounded goroutines — OOM risk
- **Evidence:** `for _, item := range items { go processItem(item) }` — no semaphore or pool limiting concurrency
- **Recommendation:** Use `errgroup.SetLimit(N)` or bounded worker pool
- **Action:** follow-up

### Suppressed Items
#### [Suppressed] Map Race in Test Helper
- **Reason:** Map at test_helpers.go:20 is created in TestMain and only read during subtests (no concurrent writes). Anti-example: "map only accessed within single goroutine"

### Execution Status
- Go version: 1.21
- Grep pre-scan: 8/13 items hit, 2 confirmed as findings (1 semantic-only)
- go test -race: PASS
- Excluded (generated): None
- References loaded: go-concurrency-patterns.md

### Summary
1 High (race condition), 1 Medium (unbounded goroutines).
```

## No-Finding Case
If no issues found: state `No concurrency findings identified.` Still output Execution Status.

## Load References Selectively

| Reference | Load When |
|-----------|-----------|
| `references/go-concurrency-patterns.md` | Always |
| `references/go-review-anti-examples.md` | Always |

## Review Discipline
- **Concurrency and lifecycle only** — never comment on security, performance, style, tests, errors, or logic
- **Execute ALL 14 checklist items** — High findings in one area do not excuse skipping others
- **Always attempt `go test -race`** — it is the most authoritative evidence source
- Check Go version before flagging loop variable capture (item 12)
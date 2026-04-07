---
name: go-error-review
description: Review Go code for error handling correctness, nil safety, and failure-path integrity including ignored errors, missing wrapping, panic misuse, SQL/HTTP resource lifecycle, and transaction patterns. Trigger when code contains error returns, panic calls, sql.Rows, transactions, HTTP client/server code, or nil-sensitive pointer operations. Use for error-handling and correctness-focused review.
allowed-tools: Read, Grep, Glob, Bash(go build*), Bash(go vet*), Bash(staticcheck*), Bash(go test*)
---

# Go Error Review

## Purpose

Audit Go code for error handling correctness, nil safety, and failure-path integrity. Core question for every function call: "What happens when it fails?"

This skill merges error handling + API request/response correctness + database operation correctness because they share one review lens: "does this code handle failure correctly?"

This skill does NOT cover: security vulnerabilities, concurrency safety, performance, code style, test quality, or business logic — those belong to sibling vertical skills.

## When To Use
- Code contains error return values
- Code uses `panic` / `recover`
- Code involves `sql.Rows`, transactions, connection pools
- Code involves HTTP request/response body handling
- Code operates on `[]*T` pointer slices

## When NOT To Use
- Security vulnerabilities → `go-security-review`
- Concurrency safety → `go-concurrency-review`
- Performance optimization → `go-performance-review`
- Code style → `go-quality-review`
- Business logic → `go-logic-review`

## Mandatory Gates

### 1) Execution Integrity Gate
Never claim tests ran unless they actually did. If not run: state reason + exact command.

### 2) Go Version Gate
Read `go.mod`. Key features:
- `errors.Is` / `errors.As` (Go 1.13+)
- `errors.Join` (Go 1.20+)
- `fmt.Errorf` with multiple `%w` (Go 1.20+)

### 3) Anti-Example Suppression Gate
MUST quote specific code evidence. Category match alone insufficient.

Embedded anti-examples:
- **"Missing error handling on json.Marshal"** — when marshaling known-safe struct with only primitive fields (string, int, bool, no interface fields). `json.Marshal` on such structs always returns nil error.
- **"Missing error wrapping"** — when caller already wraps; adding another layer creates redundant context like `"create user: insert user: insert row: ..."`. Cite the caller's wrapping code.
- **"Speculative nil dereference"** — when caller is internal and always passes non-nil. Cite the caller code proving it never passes nil.
- **"Should use errors.Is instead of =="** — direct `==` against sentinel from the **same package** is acceptable. Cross-package comparison must use `errors.Is`.
- **"defer f.Close() ignoring error"** — acceptable for **read-only** file opens. Flag only for **write** operations where Close flushes buffered data.

### 4) Generated Code Exclusion Gate
Exclude: `*.pb.go`, `*_gen.go`, `mock_*.go`. Note excluded files in Execution Status.

## Workflow

1. **Define scope** — files/diff under review. Apply Generated Code Exclusion Gate.
2. **Gather evidence** — read changed files, identify error-handling patterns: `if err != nil`, `_ =`, `panic(`, `sql.Rows`, `tx.`, `resp.Body`, `[]*T`.
3. **Load references** — always load `go-error-and-quality.md` (error sections); load `go-api-http-checklist.md` when net/http code present; load `go-database-patterns.md` when database code present.
4. **Evaluate ALL 12 checklist items** — for each function call, ask "what happens on failure?"
5. **Apply suppression** → format output.

## Grep-Gated Execution Protocol

This skill uses mechanical grep pre-scanning to guarantee zero missed checklist items. The model's attention is reserved for semantic judgment on grep hits and semantic-only items.

### Execution Order
1. Identify target files (from dispatch prompt, or write raw snippet to `$TMPDIR/review_snippet.go`)
2. Run grep for ALL 12 checklist items against target files
3. **HIT** → run semantic analysis to confirm or reject (true positive vs false positive)
4. **MISS** → auto-mark NOT FOUND, skip semantic analysis for that item
5. For compound patterns (item 12): run both grep patterns, apply AND logic
6. Report only FOUND items (grep-confirmed + semantic-confirmed)

### Grep Audit Line
Include in Execution Status: `Grep pre-scan: X/12 items hit, Z confirmed as findings`

### Compound Pattern Protocol
Some items require two grep patterns. Run both:
- Item 12 (Log-and-return): TRIGGER when `log\.\|slog\.` HIT **AND** `return.*err` HIT in same file

## Error Checklist (12 Items)

### Error Handling (High)

| # | Item | Code Pattern Triggers | Grep Pattern |
|---|------|-----------------------|--------------|
| 1 | **Ignored error** | `_ =` or `_ :=` on error-returning calls. Acceptable only for `hash.Write`, known-safe `fmt.Fprintf` to buffer | `_\s*[:=]=` |
| 2 | **Missing error wrapping** | `return err` without `fmt.Errorf("context: %w", err)` at abstraction boundary | `return\s+(nil,\s*)?err\b` |
| 3 | **Panic misuse** | `panic()` for recoverable errors. Acceptable only in `init()` or unrecoverable invariant violation | `panic\(` |
| 4 | **Missing errors.Is/As** | Direct `==` on error for cross-package sentinel; type switch instead of `errors.As` | `err\s*[!=]=\s*\|[!=]=\s*err` |
| 5 | **Pointer slice nil guard** | `[]*T` elements accessed without nil check before field/method access | `\[\]\*\w` |

### API/HTTP Correctness (High)

| # | Item | Code Pattern Triggers | Grep Pattern |
|---|------|-----------------------|--------------|
| 6 | **Unbounded server body** | Missing `http.MaxBytesReader` / `io.LimitReader` on body decode. Do NOT require `r.Body.Close()` — framework handles it | `r\.Body\|Request\.Body\|ReadAll` |
| 7 | **Client response body leak** | `resp.Body` not closed on ALL paths including error path — prevents connection reuse | `resp\.Body\|Response\.Body` |
| 8 | **HTTP status code mismatch** | 200 for creation (should be 201), 500 for not-found (should be 404) | `WriteHeader\|StatusCode\|http\.Status` |

### Database Correctness (High)

| # | Item | Code Pattern Triggers | Grep Pattern |
|---|------|-----------------------|--------------|
| 9 | **Unclosed sql.Rows** | Missing `defer rows.Close()` AFTER error check; missing `rows.Err()` after iteration loop | `\.Query[^R]\|\.QueryRow\|sql\.Rows` |
| 10 | **Wrong transaction rollback pattern** | Missing `defer tx.Rollback()` + Commit override pattern | `\.Begin\(\|tx\.` |
| 11 | **sql.ErrNoRows mishandled** | Treating as server error (500) instead of domain "not found" (404) | `ErrNoRows` |
| 12 | **Log-and-return double reporting** | Logging error AND returning it — causes duplicate log entries upstream | `log\.\|slog\.` (compound: ALSO check `return.*err` in same file) |

## Severity Rubric

**High** — Resource leak, crash, silent failure, data inconsistency.

**Medium** — Suboptimal error handling that makes debugging harder but no immediate failure.

## Evidence Rules
- For each finding: explain what happens on the failure path
- For resource leaks: show the code path where Close/Rollback is missed
- For body leaks: show the error-path branch that skips Close
- **Merge rule**: same issue at ≥3 locations → one finding with location list

## Output Format

### Findings
#### [High|Medium] Short Title
- **ID:** ERR-NNN
- **Location:** `path:line`
- **Impact:** What happens when this code path fails
- **Evidence:** The missing error check / resource close / wrapping
- **Recommendation:** Specific fix
- **Action:** `must-fix` | `follow-up`

### Suppressed Items
#### [Suppressed] Short Title
- **Reason:** Anti-example matched + evidence cited

### Execution Status
- `Go version`: X.Y
- `Grep pre-scan`: X/12 items hit, Z confirmed as findings
- `go test`: PASS | FAIL | Not run (reason + command)
- `Excluded (generated)`: list or None
- `References loaded`: list

### Summary
1-2 lines with finding count.

## Example Output

```
### Findings

#### [High] Response Body Leak in HTTP Client
- **ID:** ERR-001
- **Location:** `internal/client/api.go:45`
- **Impact:** Connection pool exhaustion — resp.Body not closed on error path
- **Evidence:** `resp, err := client.Do(req)` at L42; if `resp.StatusCode != 200` at L44, function returns error at L46 without closing resp.Body. Body only closed on happy path at L52.
- **Recommendation:** Move defer immediately after nil-error check:
  ```go
  resp, err := client.Do(req)
  if err != nil { return err }
  defer resp.Body.Close()
  ```
- **Action:** must-fix

#### [High] Missing rows.Err() After Iteration
- **ID:** ERR-002
- **Location:** `internal/repo/order.go:78`
- **Impact:** Silent data truncation — if iteration breaks due to network error, partial results returned without error
- **Evidence:** `for rows.Next() { ... }` loop at L73-80 exits without checking `rows.Err()`
- **Recommendation:** Add after loop: `if err := rows.Err(); err != nil { return nil, fmt.Errorf("iterating orders: %w", err) }`
- **Action:** must-fix

### Suppressed Items
#### [Suppressed] json.Marshal Error Ignored
- **Reason:** `json.Marshal(config)` at config.go:30 — `config` is `AppConfig` struct with only primitive fields. Anti-example: "known-safe struct with no interface fields"

### Execution Status
- Go version: 1.21
- Grep pre-scan: 5/12 items hit, 2 confirmed as findings
- go test: PASS
- Excluded (generated): None
- References loaded: go-error-and-quality.md, go-api-http-checklist.md, go-database-patterns.md

### Summary
2 High findings (response body leak, missing rows.Err). No Medium findings.
```

## No-Finding Case
If no issues found: state `No error handling findings identified.` Still output Execution Status.

## Load References Selectively

| Reference | Load When |
|-----------|-----------|
| `references/go-error-and-quality.md` | Always (error handling sections) |
| `references/go-api-http-checklist.md` | Code involves net/http, handlers, gin/echo/chi, gRPC |
| `references/go-database-patterns.md` | Code involves database/sql, pgx, sqlx, gorm, ent |
| `references/go-review-anti-examples.md` | Always |

## Review Discipline
- **Error handling, nil safety, failure-path integrity only** — not security, concurrency, performance, style, tests, or logic
- For every function call: **"what happens when it fails?"**
- Execute ALL 12 checklist items without skipping
- Server handler `r.Body`: do NOT require manual Close (framework handles it)
- Client `resp.Body`: MUST be closed on all paths

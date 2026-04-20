# Go Code Review Anti-examples

Reference for the **False-Positive Suppression Gate** in SKILL.md. These are the most common false positives in Go code review. If a finding matches one of these patterns **and** the stated precondition is satisfied, suppress it.

---

## Mandatory Precondition Verification

Before suppressing a finding using any anti-example below, you MUST first quote specific code evidence that satisfies the anti-example's stated precondition. Category match alone is not sufficient.

- Incorrect: "This involves error wrapping, so the anti-example applies." ← precondition unverified
- Correct: "The caller at service.go:45 already wraps this error with `fmt.Errorf(...)`, satisfying 'caller already wraps the error'." ← specific evidence cited

If you cannot cite specific evidence, the anti-example does not apply and the finding must be reported.

---

## Speculative nil/panic
- "This function could panic if nil is passed" — when the caller is internal and always passes non-nil

## Over-cautious error handling
- "Missing error handling on json.Marshal" — when marshaling a known-safe struct with no interface fields
- "Missing error wrapping with %w" — when the caller already wraps the error; adding another layer would produce redundant context like `"create user: insert user: insert row: ..."`

## False concurrency alarms
- "Potential race condition on this map" — when the map is only accessed within a single goroutine or is created and consumed within a single function scope
- "Should use errgroup instead of WaitGroup" — when no error propagation is needed and goroutine count is small and fixed

## Premature optimization
- "Should use sync.Pool" — when the object is small and allocated infrequently
- "Should pre-allocate slice" — when the slice is small (< 16 elements) or size is truly unknown
- "Struct fields should be reordered for alignment" — when the struct has < 4 fields or savings < 8 bytes, **or** when the struct carries `json:` tags and is used as an HTTP/gRPC API response body. `encoding/json` (and high-performance alternatives like `sonic`) serialize fields in declaration order; reordering fields changes JSON output order, which breaks downstream consumers that rely on field position or string-prefix matching — even when no field is added, removed, or renamed. Before reporting a fieldalignment finding on a `json:`-tagged struct, confirm it is never serialized as a wire-format response to external callers; if it is, the correct action is to flag the reordering as an **API breaking change**, not a performance win.
- "Should use strings.Clone for substring" — when both the substring and parent string are short-lived locals eligible for GC at the same scope

## Version-inappropriate recommendations
- "Should use slog instead of log" — when the project's `go.mod` targets Go < 1.21
- "Should use atomic.Int64 instead of atomic.AddInt64" — when the project's `go.mod` targets Go < 1.19

## Context over-propagation
- "Missing context propagation" — when the function is synchronous, short-lived, performs no I/O, and has no cancellable work

## Unnecessary abstraction
- "Should use generics here" — when only one concrete type is used throughout the codebase
- "Exported function missing godoc" — when the symbol is in an `internal/` package not intended for external consumers

## Structural false alarms
- "Function too long (>50 lines)" — when the body is a straightforward table-driven switch, a sequential pipeline with no nesting, or a single select/case block

## Grey-area guidance (use judgment)
- `errors.Is` vs `==`: direct `==` against a sentinel from the **same package** is acceptable; cross-package must use `errors.Is`
- `context.TODO()` vs `context.Background()`: in `main()` or top-level initialization, `context.Background()` is correct; `TODO()` is only appropriate when context propagation is planned but not yet implemented
- `interface{}` → `any`: pure alias rename is cosmetic; report only if part of a broader modernization effort, never as a standalone finding
- `defer f.Close()` ignoring error: acceptable for **read-only** file opens; flag only for **write** operations where close flushes buffered data
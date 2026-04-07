---
name: go-test-review
description: Review Go test code for quality including table-driven tests, t.Helper usage, assertion completeness, boundary cases, benchmarks, fuzz tests, and coverage targets. Trigger when PR contains _test.go files, test helpers, httptest usage, testing.B, testing.F, or testdata directories. Use for test-quality focused review.
allowed-tools: Read, Grep, Glob, Bash(go build*), Bash(go vet*), Bash(go test*)
---

# Go Test Review

## Purpose

Audit Go test code for quality and coverage effectiveness. Reviews HOW tests are written — not the production code being tested.

This skill is **conditionally triggered** — only when `_test.go` files are in the diff. If a PR has only implementation code with no tests, this skill may suggest "missing test coverage" but does not deep-dive.

This skill does NOT cover: security, concurrency, performance, quality, error handling, or logic of production code — those belong to sibling vertical skills.

## When To Use
- PR contains `_test.go` files
- Code uses `httptest`, `testing.B`, `testing.F`
- Code includes `testdata/` directory changes
- Need to evaluate test coverage

## When NOT To Use
- Reviewing production code security/performance/logic → use corresponding sibling skill
- Only implementation code changed, no tests → may note "missing tests" but no deep review

## Mandatory Gates

### 1) Go Version Gate
Read `go.mod`. Key version gates:

| Feature | Minimum Go | Caveat |
|---------|-----------|--------|
| `t.Setenv` | 1.17 | Cannot combine with `t.Parallel()` |
| Fuzz testing (`testing.F`) | 1.18 | |
| Loop variable fix | 1.22 | Affects `t.Parallel()` + loop variable capture |
| `t.Parallel()` + `t.Setenv` safe | 1.24 | Before 1.24, this combination panics |

### 2) Anti-Example Suppression Gate
MUST quote specific evidence. Category match alone insufficient.

Embedded anti-examples:
- **"Testing standard library behavior"** — test that `json.Marshal` produces valid JSON, or that `strings.Contains` works. These test Go's stdlib, not your code.
- **"Test only asserts err == nil"** — BUT: do NOT flag if function genuinely has no meaningful return value (void-like operations where error is the only output, e.g., `Close()`, `Flush()`).
- **"Should use integration test"** — when unit test with mock is the correct choice for fast, isolated testing. Not every test needs a real database.
- **"Missing test for unexported function"** — when function is simple helper fully covered by exported function tests.
- **"Missing benchmark"** — when code is not on a hot path and benchmarking provides no actionable insight.

### 3) Generated Code Exclusion Gate
`mock_*.go` from mockgen: review for usage patterns only, not mock implementation itself.

## Workflow

1. **Define scope** — identify `_test.go` files in diff.
2. **Run `go test -cover`** for impacted packages — record coverage percentage.
3. **Load references** — always load `go-test-quality.md`.
4. **Evaluate ALL 10 checklist items**.
5. **Apply suppression** → format output.

## Grep-Gated Execution Protocol

This skill uses mechanical grep pre-scanning to guarantee zero missed checklist items. 8 of 10 items are grep-gated; 2 are semantic-only.

### Execution Order
1. Identify target test files (from dispatch prompt)
2. Run grep for all grep-gated checklist items against target files
3. **HIT** → run semantic analysis to confirm or reject
4. **MISS** → auto-mark NOT FOUND, skip semantic analysis
5. For compound patterns (items 1, 2): run both grep patterns, apply logic
6. For semantic-only items (items 4, 9): full model reasoning
7. Report only FOUND items

### Grep Audit Line
Include in Execution Status: `Grep pre-scan: X/8 items hit, Z confirmed as findings (2 semantic-only)`

## Test Quality Checklist (10 Items)

| # | Item | What to Check | Grep Pattern |
|---|------|--------------|-------------|
| 1 | **Table-driven tests** | Table-driven pattern with meaningful subtest names: `t.Run(tc.name, ...)` | `func Test\|t\.Run` (compound: check if table-driven pattern used) |
| 2 | **t.Helper()** | Test helper functions call `t.Helper()` for accurate failure line reporting | `func\s+\w+.*\*testing\.T\b` (compound: AND NOT `t\.Helper\(\)` in function body) |
| 3 | **Assertion completeness** | Not just `err == nil` — verify return values, error types, side effects, field values | `assert\.\|require\.\|if.*!=\|if.*==` |
| 4 | **Boundary case coverage** | nil/zero, empty collection, single element, boundary values, Unicode, concurrent access | Semantic-Only (boundary case coverage requires understanding domain context) |
| 5 | **Minimal mocks/stubs** | Minimal interface mocks; prefer hand-written doubles; mock at boundary, not internal | `mock\.\|Mock\|Stub\|fake\|Fake` |
| 6 | **Benchmark correctness** | `b.ResetTimer()` after setup, `b.ReportAllocs()`, `b.RunParallel()` for concurrent benchmarks | `testing\.B\|b\.Run\|b\.ResetTimer\|b\.ReportAllocs` |
| 7 | **Fuzz testing** | Seed corpus provided, invariant-based assertions (not exact match), no external deps in target | `testing\.F\|f\.Fuzz\|f\.Add` |
| 8 | **HTTP handler testing** | `httptest.NewRecorder` (unit) or `httptest.NewServer` (integration); check status + body + headers | `httptest\.\|NewRecorder\|NewServer` |
| 9 | **Golden file testing** | `-update` flag support, `testdata/` directory, deterministic output (no timestamps/random) | Semantic-Only (golden file testing pattern requires understanding test intent) |
| 10 | **Coverage >= 80%** | Business logic packages must hit 80%+; not required for generated code, wire/DI glue, or main.go | `go test.*-cover\|coverage` (or check test existence for changed packages) |

## Severity Rubric

**High** — Missing critical coverage (changed behavior untested), assertion that can never fail (false confidence).

**Medium** — Test quality issue reducing diagnostic value but not creating false confidence.

## Evidence Rules
- For coverage gaps: identify which changed behavior lacks test coverage
- For weak assertions: show what the test checks vs what it should check
- For false-confidence: show why the assertion always passes regardless of implementation
- **Merge rule**: same pattern at ≥3 tests → one finding with location list

## Output Format

### Findings
#### [High|Medium] Short Title
- **ID:** TEST-NNN
- **Location:** `path:line`
- **Impact:** What could be missed by this test gap
- **Evidence:** Missing assertion/boundary/pattern
- **Recommendation:** Specific test improvement with code example
- **Action:** `must-fix` | `follow-up`

### Suppressed Items
#### [Suppressed] Short Title
- **Reason:** Anti-example matched + evidence cited

### Execution Status
- `Go version`: X.Y
- `Grep pre-scan`: X/8 items hit, Z confirmed as findings (2 semantic-only)
- `go test -cover`: coverage% for impacted packages
- `References loaded`: list

### Summary
1-2 lines. Count by severity + coverage status.

## Example Output

```
### Findings

#### [High] False-Confidence Assertion — Only Checks err == nil
- **ID:** TEST-001
- **Location:** `internal/service/user_test.go:45`
- **Impact:** Test passes even if CreateUser returns wrong user — only error checked, return value ignored
- **Evidence:** `err := svc.CreateUser(ctx, input); assert.NoError(t, err)` — no assertion on returned User (name, email, ID)
- **Recommendation:**
  ```go
  user, err := svc.CreateUser(ctx, input)
  assert.NoError(t, err)
  assert.Equal(t, input.Name, user.Name)
  assert.Equal(t, input.Email, user.Email)
  assert.NotEmpty(t, user.ID)
  ```
- **Action:** must-fix

#### [Medium] Missing Boundary Cases in Table-Driven Test
- **ID:** TEST-002
- **Location:** `internal/validator/email_test.go:20-55`
- **Impact:** Edge cases could slip through — only happy path and obvious invalid tested
- **Evidence:** Cases: "valid@email.com", "invalid", "" — missing: Unicode local part, max-length (254 chars), consecutive dots, leading/trailing spaces
- **Recommendation:** Add: `{"unicode: ü@domain.com", true}`, `{"max-length-254", ...}`, `{" spaces@x.com", false}`
- **Action:** follow-up

### Execution Status
- Go version: 1.21
- go test -cover: internal/service 72%, internal/validator 85%
- References loaded: go-test-quality.md

### Summary
1 High (false-confidence assertion), 1 Medium (missing boundary cases). Coverage: service 72% (below 80% threshold).
```

## No-Finding Case
If no issues found: state `No test quality findings identified.` Still output coverage numbers in Execution Status.

## Load References Selectively

| Reference | Load When |
|-----------|-----------|
| `references/go-test-quality.md` | Always |
| `references/go-review-anti-examples.md` | Always |

## Review Discipline
- **Test quality only** — not production code security/performance/logic
- Execute ALL 10 checklist items
- Coverage threshold: 80% for business logic packages — flag if below
- Do not review mock implementation code (generated mocks); review mock usage patterns
# TDD Boundary Checklist

> Use during Defect Hypothesis Gate. For extended BAD/GOOD examples and killer case design templates, cross-reference unit-test skill: `references/bug-finding-techniques.md` and `references/killer-case-patterns.md`.

For each test target (interface method / exported function / handler endpoint), mark each item as `Covered` or `N/A (reason)`:

1. **nil input** — pointer/interface/map/slice/channel/function parameter
2. **empty value/collection** — `""`, `[]`, `nil` slice, empty map
3. **single element** — `len == 1`
4. **size/index boundary** — `n=2`, `n=3`, last element (`i+1`, `n-1` in code)
5. **min/max value boundary** — `x-1`, `x`, `x+1` if numeric
6. **invalid format/type** — malformed input, wrong type
7. **zero-value struct/default trap** — struct with zero fields, default values
8. **dependency error** — each critical dependency returns error
9. **context cancellation/deadline** — `context.Canceled`, `DeadlineExceeded`
10. **concurrency/race** — goroutines, shared state (if applicable)
11. **mapping completeness** — no dropped first/middle/last item in transforms
12. **killer case** — present and mapped to a concrete defect hypothesis

## Defect Hypothesis Quick Patterns

Use these to generate hypotheses BEFORE writing tests:

| Category | Pattern | Example Hypothesis |
|----------|---------|-------------------|
| **Boundary/index** | off-by-one in loop or slice | "last item in list is dropped because `i < len-1` instead of `i < len`" |
| **Error propagation** | error swallowed or wrong wrap | "repo error is logged but nil returned to caller" |
| **Mapping loss** | field not copied in transform | "User.Email not mapped to DTO, returns empty string" |
| **Concurrency** | shared state without sync | "concurrent writes to cache map cause panic" |
| **Idempotency** | duplicate call creates duplicate | "calling CreateOrder twice creates two orders for same request ID" |
| **Zero-value trap** | zero struct passes validation | "empty TransferRequest passes validation because Amount==0 is not checked" |

## Killer Case Design (Internalized Core)

A killer case must have four elements:

1. **Defect hypothesis** — which specific bug it catches
2. **Fault injection** — how to trigger the defect (fake returning wrong data, boundary input)
3. **Critical assertion** — the assertion that fails if the bug exists
4. **Removal risk** — what breaks if this test is deleted

```go
// Example killer case with all 4 elements:
t.Run("killer: wrong user ID propagated from repo", func(t *testing.T) {
	// 1. Hypothesis: service returns whatever repo gives, without verifying ID match
	// 2. Fault injection: fake returns user with wrong ID
	fake.getUserFn = func(ctx context.Context, id string) (*User, error) {
		return &User{ID: "wrong-id", Name: "alice"}, nil
	}
	user, err := svc.GetUser(ctx, "u-1")
	require.NoError(t, err)
	// 3. Critical assertion: ID must match requested ID
	assert.Equal(t, "u-1", user.ID, "KILLER: ID must match request")
	// 4. Removal risk: without this test, service silently returns wrong user's data
})
```

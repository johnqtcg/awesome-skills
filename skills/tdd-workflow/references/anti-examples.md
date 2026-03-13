# TDD Anti-Examples (Extended)

Read this file when reviewing or generating TDD code. Each example shows a common TDD-specific mistake and the correct alternative.

For the two most critical TDD mistakes (Big-Bang Red and Skipping Red Evidence), see SKILL.md directly.

## Mistake 2: Green phase adds speculative code not demanded by tests

```go
// BAD: test only requires Create, but you also implement Update and Delete
// "while I'm here" code has no test-driven justification
func (s *UserService) Create(ctx context.Context, u User) error { /* tested */ }
func (s *UserService) Update(ctx context.Context, u User) error { /* not tested */ }
func (s *UserService) Delete(ctx context.Context, id string) error { /* not tested */ }

// GOOD: implement ONLY what a failing test demands
// Untested production code = untested production risk
```

## Mistake 3: Refactor phase changes observable behavior

```go
// BAD: during refactor, you "improve" error handling — but this changes behavior
// Before refactor: returns fmt.Errorf("user not found")
// After refactor:  returns custom NotFoundError{} — different type
// Tests still pass because they only check err != nil, not error type

// GOOD: refactor changes structure, NOT behavior
// Extract method, rename, reduce duplication, simplify logic
// Tests must stay green WITHOUT modification during refactor
// If you need to change behavior → start a new Red cycle
```

## Mistake 5: Testing implementation details instead of behavior contracts

```go
// BAD: test asserts internal method call count — breaks on any refactor
func TestCreateOrder(t *testing.T) {
	svc.CreateOrder(ctx, order)
	assert.Equal(t, 1, fakeRepo.saveCalls)    // breaks if refactored to batch
	assert.Equal(t, 1, fakeNotify.sendCalls)   // breaks if notification becomes async
}

// GOOD: assert observable outcomes (behavior contract)
func TestCreateOrder(t *testing.T) {
	result, err := svc.CreateOrder(ctx, order)
	require.NoError(t, err)
	assert.Equal(t, "confirmed", result.Status)
	assert.Equal(t, order.Total, result.Total)
	// Verify side effects through observable state, not call counts
}
```

## Mistake 6: No killer case — all tests pass trivially

```go
// BAD: every test checks err == nil and result != nil
// A function that always returns (emptyUser, nil) would pass all tests
func TestGetUser(t *testing.T) {
	user, err := svc.GetUser(ctx, "u-1")
	require.NoError(t, err)
	assert.NotNil(t, user) // too weak — wrong user passes

	user2, err := svc.GetUser(ctx, "u-2")
	require.NoError(t, err)
	assert.NotNil(t, user2) // same weak pattern
}

// GOOD: killer case with concrete field assertions
func TestGetUser(t *testing.T) {
	t.Run("killer: correct user fields returned", func(t *testing.T) {
		user, err := svc.GetUser(ctx, "u-1")
		require.NoError(t, err)
		assert.Equal(t, "u-1", user.ID)      // would fail if wrong user
		assert.Equal(t, "alice", user.Name)   // would fail if fields mixed up
	})
}
```

## Mistake 7: Change-size mismatch — L-sized tests for S-sized change

```go
// BAD: 2-line bug fix (S change) but you write 25 test cases
// Test bloat: diminishing returns, maintenance burden, slows iteration

// GOOD: match test depth to change size
// S change (≤2 files, ≤50 LOC): 3-6 cases — fix + regression + boundary
// M change (3-5 files, 50-150 LOC): 6-12 cases
// L change (>5 files, >150 LOC): 10-20 cases
```

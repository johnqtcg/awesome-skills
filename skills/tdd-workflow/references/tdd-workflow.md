# TDD Workflow Reference

## End-to-End TDD Walkthrough

This example shows building a `TransferFunds` service method from scratch using strict TDD.

### Context

```go
type AccountService struct { repo AccountRepo }

type TransferRequest struct {
	FromID string
	ToID   string
	Amount int64 // cents
}
```

### Iteration 1: Red → Green (happy path)

**Red** — write failing test:

```go
func TestTransferFunds(t *testing.T) {
	t.Run("success: transfer between two accounts", func(t *testing.T) {
		repo := &fakeAccountRepo{
			accounts: map[string]*Account{
				"a-1": {ID: "a-1", Balance: 1000},
				"a-2": {ID: "a-2", Balance: 500},
			},
		}
		svc := NewAccountService(repo)
		err := svc.TransferFunds(ctx, TransferRequest{FromID: "a-1", ToID: "a-2", Amount: 300})
		require.NoError(t, err)
		assert.Equal(t, int64(700), repo.accounts["a-1"].Balance)
		assert.Equal(t, int64(800), repo.accounts["a-2"].Balance)
	})
}
```

```bash
$ go test -run TestTransferFunds -v
--- FAIL: TestTransferFunds/success (0.00s)
    # TransferFunds undefined
```

**Green** — implement minimal code:

```go
func (s *AccountService) TransferFunds(ctx context.Context, req TransferRequest) error {
	from, err := s.repo.Get(ctx, req.FromID)
	if err != nil {
		return err
	}
	to, err := s.repo.Get(ctx, req.ToID)
	if err != nil {
		return err
	}
	from.Balance -= req.Amount
	to.Balance += req.Amount
	return s.repo.SaveBatch(ctx, []*Account{from, to})
}
```

```bash
$ go test -run TestTransferFunds -v
--- PASS: TestTransferFunds/success (0.00s)
```

### Iteration 2: Red → Green (killer case — insufficient balance)

**Red:**

```go
t.Run("killer: insufficient balance returns error, no side effect", func(t *testing.T) {
	repo := &fakeAccountRepo{
		accounts: map[string]*Account{
			"a-1": {ID: "a-1", Balance: 100},
			"a-2": {ID: "a-2", Balance: 500},
		},
	}
	svc := NewAccountService(repo)
	err := svc.TransferFunds(ctx, TransferRequest{FromID: "a-1", ToID: "a-2", Amount: 200})
	require.Error(t, err)
	assert.Contains(t, err.Error(), "insufficient")
	// KILLER: balances must be unchanged on error
	assert.Equal(t, int64(100), repo.accounts["a-1"].Balance, "KILLER: from balance unchanged")
	assert.Equal(t, int64(500), repo.accounts["a-2"].Balance, "KILLER: to balance unchanged")
})
```

```bash
$ go test → FAIL (no insufficient check, balance modified)
```

**Green** — add guard:

```go
if from.Balance < req.Amount {
	return fmt.Errorf("insufficient balance: have %d, need %d", from.Balance, req.Amount)
}
```

### Iteration 3: Red → Green (boundary — zero amount)

```go
t.Run("boundary: zero amount returns error", func(t *testing.T) {
	err := svc.TransferFunds(ctx, TransferRequest{FromID: "a-1", ToID: "a-2", Amount: 0})
	require.Error(t, err)
	assert.Contains(t, err.Error(), "positive")
})
```

### Iteration 4: Refactor

After all tests pass, improve structure:
- Extract `validateRequest()` method
- Extract `applyTransfer()` for the balance mutation
- **Run tests after each change — must stay green without modification**

## Refactor Patterns (Safe Transformations)

These transformations are safe during Refactor phase because they don't change behavior:

| Pattern | What Changes | What Must NOT Change |
|---------|-------------|---------------------|
| Extract Method | One function splits into two | Same inputs → same outputs |
| Rename | Symbol names | API contract and behavior |
| Inline Variable | Temporary variable removed | Computation result |
| Replace Magic Number | Literal → named constant | Value |
| Simplify Conditional | `if/else` → early return | Branch outcomes |
| Extract Interface | Concrete → interface dependency | Caller behavior |
| Reduce Nesting | Flatten nested `if` | Decision paths |

**Rule**: if any test needs modification during Refactor, you changed behavior — start a new Red cycle instead.

## Outside-In vs Inside-Out TDD

| Approach | Start From | Best For |
|----------|-----------|----------|
| **Outside-In** | Handler/API test → drives service → drives repo | Feature stories, API-first design |
| **Inside-Out** | Unit functions → compose into service → expose via handler | Algorithm-heavy, domain-model-first |

Choose based on the change:
- New API endpoint → Outside-In (Handler first)
- New business rule in existing service → Inside-Out (Service first)
- Bug fix → start at the layer where the bug manifests

## TDD with Legacy Code (Characterization Tests)

When modifying untested legacy code:

1. **Characterize first**: write tests that document current behavior (even if buggy)
2. **Pin the behavior**: ensure characterization tests pass
3. **Red**: write a new failing test for the desired change
4. **Green**: modify code to pass new test while keeping characterization tests green
5. **Refactor**: with safety net of both old + new tests

```go
// Characterization test: documents current (possibly buggy) behavior
func TestLegacyCalcTotal_characterization(t *testing.T) {
	// This test pins the CURRENT behavior — do not "fix" it
	result := LegacyCalcTotal([]Item{{Price: 10, Qty: 3}})
	assert.Equal(t, 30, result) // current behavior: no tax
}

// New TDD test: drives the desired change (add tax)
func TestCalcTotal_withTax(t *testing.T) {
	result := CalcTotal([]Item{{Price: 10, Qty: 3}}, 0.1) // 10% tax
	assert.Equal(t, 33, result) // 30 + 3 tax
}
```

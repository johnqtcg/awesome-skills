# Bug-Finding Techniques — Detailed Reference

> Referenced from [SKILL.md](../SKILL.md) Bug-Finding Techniques summary table.

## 1) Mutation-Resistant Assertions

Assert concrete business fields, not just existence or nil checks. A mutation that swaps field values or returns a default struct should break your test.

**BAD** — passes even if implementation returns wrong user:

```go
// testify
func TestGetUser_Bad(t *testing.T) {
	svc := NewUserService(fakeRepo)
	user, err := svc.GetUser(ctx, "u-1")
	require.NoError(t, err)
	assert.NotNil(t, user) // any non-nil user passes
}
```

**GOOD** — catches field-swap and wrong-record bugs:

```go
// testify
func TestGetUser_Good(t *testing.T) {
	svc := NewUserService(fakeRepo)
	user, err := svc.GetUser(ctx, "u-1")
	require.NoError(t, err)
	assert.Equal(t, "u-1", user.ID)
	assert.Equal(t, "alice", user.Name)
	assert.Equal(t, "alice@example.com", user.Email)
}

// standard library equivalent
func TestGetUser_Stdlib(t *testing.T) {
	svc := NewUserService(fakeRepo)
	user, err := svc.GetUser(ctx, "u-1")
	if err != nil {
		t.Fatalf("GetUser() error = %v, want nil", err)
	}
	if user.ID != "u-1" {
		t.Errorf("ID = %q, want %q", user.ID, "u-1")
	}
	if user.Name != "alice" {
		t.Errorf("Name = %q, want %q", user.Name, "alice")
	}
}
```

---

## 2) Collection Mapping Completeness

For methods transforming input collections to output collections, assert: length, identity of every element, and field correctness of first/middle/last.

```go
func TestListLevels_MappingComplete(t *testing.T) {
	input := []domain.RawLevel{
		{ID: "L1", Name: "Bronze", Rank: 1},
		{ID: "L2", Name: "Silver", Rank: 2},
		{ID: "L3", Name: "Gold", Rank: 3},
	}
	fake := &fakeRepo{levels: input}
	svc := NewLevelService(fake)

	got, err := svc.ListLevels(ctx)
	require.NoError(t, err)

	// Length — catches dropped elements
	assert.Len(t, got, 3)

	// Identity — every input ID appears exactly once
	ids := make([]string, len(got))
	for i, l := range got {
		ids[i] = l.ID
	}
	assert.ElementsMatch(t, []string{"L1", "L2", "L3"}, ids)

	// First element fields
	assert.Equal(t, "Bronze", got[0].Name)
	assert.Equal(t, "L2", got[0].NextLevelID) // first points to second

	// Middle element fields
	assert.Equal(t, "Silver", got[1].Name)

	// Last element fields — terminal semantics
	assert.Equal(t, "Gold", got[2].Name)
	assert.Empty(t, got[2].NextLevelID) // last has no next
}
```

---

## 3) Off-by-One Precision

For every size/index boundary, test n=0,1,2,3. When code uses `i+1` or `n-1`, add cases that prove last-item behavior.

```go
func TestBatch_OffByOne(t *testing.T) {
	tests := []struct {
		name  string
		items []string
		batch int
		want  [][]string
	}{
		{
			name:  "n=0 empty input",
			items: nil,
			batch: 3,
			want:  nil,
		},
		{
			name:  "n=1 single element",
			items: []string{"a"},
			batch: 3,
			want:  [][]string{{"a"}},
		},
		{
			name:  "n=2 less than batch size",
			items: []string{"a", "b"},
			batch: 3,
			want:  [][]string{{"a", "b"}},
		},
		{
			name:  "n=3 exactly batch size",
			items: []string{"a", "b", "c"},
			batch: 3,
			want:  [][]string{{"a", "b", "c"}},
		},
		{
			name:  "n=4 one past batch boundary",
			items: []string{"a", "b", "c", "d"},
			batch: 3,
			want:  [][]string{{"a", "b", "c"}, {"d"}},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := Batch(tt.items, tt.batch)
			assert.Equal(t, tt.want, got)
		})
	}
}
```

---

## 4) Dependency Error Propagation

For each external dependency that may fail, inject one failure and verify: error is returned, no partial/incorrect success payload, error wrapping is correct.

```go
func TestCreateOrder_RepoError(t *testing.T) {
	repoErr := errors.New("connection refused")
	fake := &fakeOrderRepo{createErr: repoErr}
	svc := NewOrderService(fake)

	order, err := svc.CreateOrder(ctx, validInput)

	// Error propagated with wrapping
	require.Error(t, err)
	assert.True(t, errors.Is(err, repoErr),
		"error should wrap repo error, got: %v", err)

	// No partial payload leaked
	assert.Nil(t, order,
		"on error, returned order must be nil")
}

func TestCreateOrder_ContextCanceled(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel() // cancel before call

	fake := &fakeOrderRepo{} // would succeed if called
	svc := NewOrderService(fake)

	_, err := svc.CreateOrder(ctx, validInput)
	require.Error(t, err)
	assert.True(t, errors.Is(err, context.Canceled))
}
```

---

## 5) Concurrency & Panic Recovery

Three core techniques for concurrency-related bug detection:

| Technique | What It Catches | Key Pattern |
|-----------|----------------|-------------|
| Channel barrier | Hidden ordering dependencies, race conditions | `close(gate)` to release all goroutines simultaneously |
| Panic recovery | Unrecovered panics crashing the process | Inject panic via fake, assert error returned (not crash) |
| Error fan-in | Silent goroutine error loss | Fail one of N goroutines, assert aggregate error contains it |

> **Full code examples**: See `references/concurrency-testing.md` for channel barrier synchronization, panic recovery, error fan-in, `-race` detection, and `t.Parallel()` safety patterns.

---

## 6) Branch Completeness

For marker branches (exists/not-exists, max/non-max), assert both the marker behavior and business payload completeness in each branch.

```go
func TestLookupUser(t *testing.T) {
	tests := []struct {
		name       string
		userExists bool
		wantFound  bool
		wantName   string
	}{
		{
			name:       "user exists — found marker true and payload complete",
			userExists: true,
			wantFound:  true,
			wantName:   "alice",
		},
		{
			name:       "user not exists — found marker false and payload empty",
			userExists: false,
			wantFound:  false,
			wantName:   "",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			fake := &fakeRepo{hasUser: tt.userExists}
			svc := NewUserService(fake)

			result, err := svc.Lookup(ctx, "u-1")
			require.NoError(t, err)

			// Marker behavior
			assert.Equal(t, tt.wantFound, result.Found)

			// Payload completeness in BOTH branches
			assert.Equal(t, tt.wantName, result.Name)
		})
	}
}
```

---

## 7) Killer Case Design

A killer case is a fault-injection or boundary-kill test tied to a concrete defect hypothesis. It must fail if the target code contains a known bad mutation.

### Template

```go
// Killer case: dropped-tail in level transform
// Defect hypothesis: loop uses `i < len(levels)-1` instead of `i < len(levels)`,
//   causing the last level to be silently dropped.
// Critical assertion: outputexample length equals input length AND last element ID present.
// "If this assertion is removed, the known bug can escape detection."
{
	name: "killer: last level not dropped",
	input: []Level{
		{ID: "L1", Name: "Bronze"},
		{ID: "L2", Name: "Silver"},
		{ID: "L3", Name: "Gold"},
	},
	setup: func(f *fakeRepo) {
		// no fault injection needed — boundary kill
	},
	validate: func(t *testing.T, got []TransformedLevel, err error) {
		require.NoError(t, err)
		require.Len(t, got, 3, "KILLER: last element must not be dropped")
		assert.Equal(t, "L3", got[2].ID,
			"KILLER: last element identity must be preserved")
	},
},
```

### Report format

For each killer case in the test output report, include:

```
Killer case: [case name]
  Defect hypothesis: [H-ID] [description]
  Critical assertion(s): [what is asserted]
  "If this assertion is removed, the known bug can escape detection."
```
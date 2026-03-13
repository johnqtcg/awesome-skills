# Killer Case Patterns — Go Code Templates

> Referenced from [SKILL.md](../SKILL.md). Each pattern includes a defect hypothesis, test code, critical assertion, and removal risk statement.

## 1) Dropped-Tail in List Transform

**Defect**: Loop uses `i < len(items)-1` instead of `i < len(items)`, silently dropping the last element.

```go
// Defect hypothesis: off-by-one in range bound drops last element.
// Critical assertion: outputexample length equals input length AND last element ID present.
// "If this assertion is removed, the known bug can escape detection."
{
	name: "killer: last element not dropped in transform",
	setup: func(f *fakeRepo) {
		f.items = []Item{
			{ID: "1", Name: "first"},
			{ID: "2", Name: "middle"},
			{ID: "3", Name: "last"},
		}
	},
	validate: func(t *testing.T, got []Result, err error) {
		require.NoError(t, err)
		require.Len(t, got, 3, "KILLER: last element must not be dropped")
		assert.Equal(t, "3", got[2].ID,
			"KILLER: last element identity must be preserved")
		assert.Equal(t, "last", got[2].Name,
			"KILLER: last element fields must be correct")
	},
},
```

---

## 2) Missing Error Fan-In

**Defect**: One goroutine's error is not collected into the aggregate error, causing silent partial failure.

```go
// Defect hypothesis: errgroup or WaitGroup collects errors from goroutines A and C
//   but silently drops goroutine B's error.
// Critical assertion: returned error contains goroutine B's failure message.
// "If this assertion is removed, the known bug can escape detection."
{
	name: "killer: goroutine-B error not swallowed",
	setup: func(f *fakeFetcher) {
		f.results = map[string]error{
			"task-A": nil,
			"task-B": errors.New("task-B connection timeout"),
			"task-C": nil,
		}
	},
	validate: func(t *testing.T, got []Result, err error) {
		require.Error(t, err, "KILLER: any goroutine error must fail the call")
		assert.Contains(t, err.Error(), "task-B",
			"KILLER: goroutine-B error must be surfaced")
		assert.Nil(t, got,
			"KILLER: no partial results on error")
	},
},
```

---

## 3) Terminal Branch Omits Fields

**Defect**: The success/terminal branch sets the status marker correctly but forgets to populate required business fields.

```go
// Defect hypothesis: terminal branch (e.g., max level) sets IsMax=true but
//   leaves Description empty because the code short-circuits before field population.
// Critical assertion: both marker AND business fields are set in terminal branch.
// "If this assertion is removed, the known bug can escape detection."
{
	name: "killer: terminal branch has complete payload",
	setup: func(f *fakeRepo) {
		f.level = &Level{
			ID: "L-max", Name: "Diamond", Rank: 10,
			IsMax: true, Description: "Highest tier",
		}
	},
	validate: func(t *testing.T, got *LevelInfo, err error) {
		require.NoError(t, err)
		assert.True(t, got.IsMax,
			"KILLER: terminal marker must be true")
		assert.Equal(t, "Diamond", got.Name,
			"KILLER: terminal branch must populate Name")
		assert.Equal(t, "Highest tier", got.Description,
			"KILLER: terminal branch must populate Description")
	},
},
```

---

## 4) Map Key Collision Silent Overwrite

**Defect**: When building a map from a list, duplicate keys silently overwrite earlier entries instead of erroring or merging.

```go
// Defect hypothesis: BuildIndex uses item.Category as map key without
//   checking for duplicates, so the second "electronics" item overwrites the first.
// Critical assertion: all items are preserved (count matches input, or error on collision).
// "If this assertion is removed, the known bug can escape detection."
{
	name: "killer: duplicate key does not silently overwrite",
	setup: func() []Item {
		return []Item{
			{ID: "1", Category: "electronics", Name: "Phone"},
			{ID: "2", Category: "electronics", Name: "Laptop"},
			{ID: "3", Category: "books", Name: "Novel"},
		}
	},
	validate: func(t *testing.T, index map[string][]Item, err error) {
		require.NoError(t, err)

		electronics := index["electronics"]
		require.Len(t, electronics, 2,
			"KILLER: both items with same key must be preserved")
		ids := []string{electronics[0].ID, electronics[1].ID}
		assert.ElementsMatch(t, []string{"1", "2"}, ids,
			"KILLER: no item silently overwritten")
	},
},
```

---

## 5) Context Cancellation Not Propagated

**Defect**: A sub-operation ignores the parent context, continuing work after cancellation instead of returning `context.Canceled`.

```go
// Defect hypothesis: inner DB call uses context.Background() instead of
//   the passed ctx, so cancellation is not propagated.
// Critical assertion: canceled context causes the operation to return
//   context.Canceled (not success or a different error).
// "If this assertion is removed, the known bug can escape detection."
{
	name: "killer: context cancellation propagated to sub-operation",
	setup: func(f *fakeRepo) {
		// Fake respects context — returns ctx.Err() if canceled
		f.respectCtx = true
	},
	run: func(t *testing.T, svc *OrderService) {
		ctx, cancel := context.WithCancel(context.Background())
		cancel() // cancel before call

		_, err := svc.ProcessOrder(ctx, validInput)
		require.Error(t, err, "KILLER: canceled ctx must cause error")
		assert.True(t, errors.Is(err, context.Canceled),
			"KILLER: error must be context.Canceled, got: %v", err)
	},
},
```

---

## 6) Off-by-One in Pagination/Batching

**Defect**: The last batch is lost because the loop condition `offset < total` misses the final partial batch when `total % batchSize != 0`.

```go
// Defect hypothesis: pagination loop uses `offset + batchSize <= total`
//   instead of `offset < total`, dropping the final partial batch.
// Critical assertion: all items across all batches are returned.
// "If this assertion is removed, the known bug can escape detection."
{
	name: "killer: final partial batch not lost",
	setup: func(f *fakeStore) {
		// 7 items, batch size 3 → should produce batches of 3, 3, 1
		f.items = generateItems(7)
		f.batchSize = 3
	},
	validate: func(t *testing.T, got []Item, err error) {
		require.NoError(t, err)
		require.Len(t, got, 7,
			"KILLER: all 7 items must be returned including final partial batch")
		assert.Equal(t, "item-7", got[6].ID,
			"KILLER: last item in final partial batch must be present")
	},
},
```
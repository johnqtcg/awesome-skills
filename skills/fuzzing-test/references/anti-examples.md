# Anti-Examples: Common Fuzzing Mistakes

Seven concrete code patterns showing what NOT to do, with corrections.

### Mistake 1: Fuzzing a trivial function (Gate 1 failure)

```go
// BAD: trivial arithmetic — fuzz adds zero value over unit tests
func FuzzAdd(f *testing.F) {
	f.Add(1, 2)
	f.Fuzz(func(t *testing.T, a, b int) {
		got := Add(a, b)
		if got != a+b {
			t.Fatalf("Add(%d, %d) = %d", a, b, got)
		}
	})
}
// GOOD: don't fuzz — write table-driven unit tests instead.
```

### Mistake 2: No oracle (Gate 3 failure)

```go
// BAD: no assertion — only catches panics, misses logic bugs
f.Fuzz(func(t *testing.T, data []byte) {
	result, _ := Transform(data)
	_ = result // never checked
})
// GOOD: always assert an invariant (round-trip, domain constraint, valid set).
```

### Mistake 3: Skip rate explosion from bad seeds

```go
// BAD: Skip rate >90%; the harness rarely reaches interesting logic
f.Add([]byte("}{"))
f.Fuzz(func(t *testing.T, data []byte) {
	var req Request
	if err := json.Unmarshal(data, &req); err != nil {
		t.Skip()
	}
})
// GOOD: add multiple valid seeds so the mutator explores useful structure first.
```

### Mistake 4: Missing size guard causes OOM

```go
// BAD: no bound, risk of OOM or pathological allocation spikes
f.Fuzz(func(t *testing.T, data []byte) {
	_, _ = ParseLargeBlob(data)
})
// GOOD: bound input before expensive parsing
```

### Mistake 5: Fuzzing global/external state

```go
// BAD: global/external state dominates behavior; results are non-deterministic
f.Fuzz(func(t *testing.T, data []byte) {
	_, _ = CreateOrder(context.Background(), db, data)
})
// GOOD: fuzz the pure validation layer and cover DB behavior with integration tests.
```

### Mistake 6: Time/random-based assertions

```go
// BAD: assertion depends on wall clock or randomness
f.Fuzz(func(t *testing.T, data []byte) {
	require.Equal(t, time.Now().Unix(), Parse(data).Timestamp)
})
// GOOD: assert structural properties and stable invariants only.
```

### Mistake 7: Dropping crash corpus or regression input

```go
// BAD: fix the bug but discard the crashing input
os.RemoveAll("testdata/fuzz/FuzzParseXxx")
// GOOD: keep the crashing corpus entry and replay it in CI.
```

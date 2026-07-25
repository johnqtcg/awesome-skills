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

### Mistake 8: A round-trip seed the codec cannot represent

The seed fails on **correct** code, so the harness is red before it has tested anything.
This one actually shipped in this skill's Template B.

```go
// BAD: encoding/json rewrites invalid UTF-8 to U+FFFD, so this seed can never round-trip.
f.Add("nul\x00and\xffbyte", int32(-1))
// got={A:nul and�byte} want={A:nul and\xffbyte}  -> FAIL on a correct implementation

// GOOD: awkward but representable — NUL, a combining mark, and an astral rune all survive.
f.Add("nul\x00 combining é \U0001F30D", int32(-1))
```

Same class: a codec that drops sub-second precision, clamps integer width, or rejects NaN.
Keep seeds inside the representable domain and let the fuzzer explore outside it — an input
the codec legitimately rejects belongs behind `t.Skip()`, not an assertion.

Rule of thumb: every seed must pass against the correct implementation. If it does not, the
seed is wrong, not the code. Enforce it with `go test -run='^Fuzz' ./...` in CI — `go vet`
cannot see this, because the harness compiles perfectly.

### Mistake 9: `got != orig` on a normalizing codec

If a codec is *allowed* to canonicalize its input, raw equality reports a bug on every
correct normalization.

```go
// BAD: fails whenever the codec canonicalizes (Unicode NFC, key order, number format)
if got != orig { t.Fatalf("round-trip mismatch") }

// GOOD (option 1): compare canonical/semantic forms
if !semanticallyEqual(got, orig) { t.Fatalf(...) }

// GOOD (option 2): assert idempotence — normalization may happen once, never drift after
again, err := Decode(mustEncode(t, got))
if err != nil || again != got {
	t.Fatalf("round-trip not idempotent: %+v vs %+v", again, got)
}
```

Idempotence is the stronger property when one normalization pass is legitimate: it still
forbids drift on every pass after the first.

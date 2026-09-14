## Applicability Verdict

`Applicability Verdict: Suitable for fuzzing`

## Why

- It is a codec, so round-trip fuzzing applies.
- Pure functions.

## Action

Fuzz mode: **round-trip**. Using Template B.

## Harness

```go
func FuzzRoundTripDoc(f *testing.F) {
	f.Add("", int32(0))
	f.Add("doc", int32(1))
	f.Add("another", int32(-1))

	f.Fuzz(func(t *testing.T, name string, size int32) {
		if len(name) > 1<<16 {
			t.Skip()
		}
		orig := Doc{Name: name, Size: size}
		enc, err := Encode(orig)
		if err != nil {
			t.Skip()
		}
		got, err := Decode(enc)
		if err != nil {
			t.Fatalf("decode(encode(x)) failed: %v", err)
		}
		if got != orig {
			t.Fatalf("round-trip mismatch: got=%+v want=%+v", got, orig)
		}
	})
}
```

## Quality Scorecard

| # | Check | Result |
|---|-------|--------|
| C1 | Applicability gate ran | Pass |
| C2 | Observable oracle present | Pass |
| C3 | Size guard present | Pass |

**Overall: PASS**

## Commands

```bash
go test -run='^$' -fuzz='^FuzzRoundTripDoc$' -fuzztime=30s .
```

This harness asserts raw equality over every input the fuzzer can produce. It has no domain
guard, so `encoding/json` rewriting invalid UTF-8 to U+FFFD reads as a round-trip bug: it
fails on the CORRECT implementation, and it would also "detect" any mutation — which is why
mutation-only grading cannot tell it apart from a working harness.

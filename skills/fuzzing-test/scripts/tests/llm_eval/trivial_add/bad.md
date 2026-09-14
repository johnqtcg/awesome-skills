## Applicability Verdict

`Applicability Verdict: Suitable for fuzzing`

## Why

- Takes input, returns output — fuzzing applies.
- No panics expected, so the fuzzer can check robustness.

## Action

Fuzz mode: **parser robustness**. Using Template A.

## Harness

```go
func FuzzAdd(f *testing.F) {
	f.Add(1, 2)
	f.Add(0, 0)
	f.Add(-1, 1)

	f.Fuzz(func(t *testing.T, a, b int) {
		got := Add(a, b)
		if got != a+b {
			t.Fatalf("Add(%d, %d) = %d", a, b, got)
		}
	})
}
```

## Quality Scorecard

| # | Check | Result |
|---|-------|--------|
| C1 | Applicability gate ran | Pass |
| C2 | Observable oracle present | Pass |
| C3 | Size guard present | n/a |

**Overall: PASS**

```bash
go test -run='^$' -fuzz='^FuzzAdd$' -fuzztime=30s .
```

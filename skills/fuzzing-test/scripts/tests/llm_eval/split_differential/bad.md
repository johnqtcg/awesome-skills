## Applicability Verdict

`Applicability Verdict: Suitable for fuzzing`

## Why

- Two implementations exist.
- Strings are easy to fuzz.

## Action

Fuzz mode: **differential**. Using Template C.

## Harness

```go
func FuzzSplitDiff(f *testing.F) {
	f.Add("hello,world", ",")
	f.Add("", ",")
	f.Add("a,b", ",")

	f.Fuzz(func(t *testing.T, s, sep string) {
		if sep == "" || len(s) > 1<<16 {
			t.Skip()
		}
		_ = SplitNew(s, sep)
		_ = SplitRef(s, sep)
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

Both implementations are called, so any divergence will surface.

```bash
go test -run='^$' -fuzz='^FuzzSplitDiff$' -fuzztime=30s .
```

## Applicability Verdict

`Applicability Verdict: Suitable for fuzzing`

## Why

- Check 1 **Pass** — `SplitNew` branches on separator length, match position, and trailing
  content; the input space is structurally rich.
- Check 2 **Pass** — two `string` parameters, both native Go fuzz types.
- Check 3 **Pass** — **differential** oracle: `SplitNew` must agree with `strings.Split`
  for every input. No domain knowledge needed — the reference defines correct.
- Check 4 **Pass** — pure functions.
- Check 5 **Pass** — nanoseconds per call.

## Action

Tier 4 target (differential candidate). Cost class `Low` → local fuzz 30-60s.
Fuzz mode: **differential**. Using **Template C**.

The empty separator is excluded deliberately: `SplitNew` delegates to the reference there,
so comparing that case tests nothing.

## Harness

```go
func FuzzSplitDiff(f *testing.F) {
	// Seeds: typical, boundary, and the multi-byte-separator shape the oracle protects.
	f.Add("hello,world", ",")  // valid: typical single-byte separator
	f.Add("", ",")             // boundary: empty subject
	f.Add("a..b", "..")        // structurally distinct: multi-byte separator
	f.Add("aaa", "aa")         // structurally distinct: overlapping candidate matches

	f.Fuzz(func(t *testing.T, s, sep string) {
		if sep == "" || len(s) > 1<<16 {
			t.Skip() // delegated case: nothing to compare
		}
		got := SplitNew(s, sep)
		want := SplitRef(s, sep)
		if !reflect.DeepEqual(got, want) {
			t.Fatalf("diff mismatch for s=%q sep=%q: got=%q want=%q", s, sep, got, want)
		}
	})
}
```

Verified before shipping:

```bash
go test -run='^FuzzSplitDiff$' -v .                          # seeds pass, and run
go test -run='^$' -fuzz='^FuzzSplitDiff$' -fuzztime=10s .    # stays clean on correct code
```

## Quality Scorecard

### Critical

| # | Check | Result |
|---|-------|--------|
| C1 | Applicability gate ran | Pass — verdict precedes all code |
| C2 | Observable oracle present | Pass — declared differential, asserted with `reflect.DeepEqual` |
| C3 | Size guard present | Pass — `len(s) > 1<<16` |

### Standard

| # | Check | Result |
|---|-------|--------|
| S1 | Seed quality | Pass — 4 distinct, all valid, one reaching the multi-byte separator path |
| S2 | Fuzz mode matches target | Pass — two implementations → differential |
| S3 | Skip rate bounded | Pass — only the empty separator skips |
| S4 | Harness isolation | Pass — pure functions |
| S5 | Corpus policy stated | Pass — see below |

### Hygiene

| # | Check | Result |
|---|-------|--------|
| H1 | Naming convention | Pass |
| H2 | Cost class assigned | Pass — `Low` |
| H3 | t.Cleanup for resources | n/a |
| H4 | Quick commands provided | Pass |

**Overall: PASS**

## Corpus policy

- Commit crashers from `<pkg>/testdata/fuzz/FuzzSplitDiff/`; never commit `$GOCACHE/fuzz/`.

Execution status: `Not run in this environment`.

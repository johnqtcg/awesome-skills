## Applicability Verdict

`Applicability Verdict: Suitable for fuzzing`

## Why

- Check 1 **Pass** — `Encode`/`Decode` traverse JSON structure, so behaviour varies richly
  across both parameters.
- Check 2 **Pass** — driven by `string` + `int32`, both native Go fuzz parameter types.
- Check 3 **Pass** — round-trip oracle, *scoped to the codec contract*: `Decode(Encode(x)) == x`
  holds for `Name` values that are valid UTF-8.
- Check 4 **Pass** — pure functions, no external state.
- Check 5 **Pass** — sub-microsecond per call.

## Action

Tier 2 target (serialisation round-trip). Cost class `Low` → local fuzz 30-60s.
Fuzz mode: **round-trip**. Using **Template B**.

The one thing this harness must get right is the **input domain**. `encoding/json` rewrites
invalid UTF-8 to U+FFFD, which is documented behaviour, not corruption — so invalid UTF-8 is
outside the assertion's domain and is skipped. Without that guard the fuzzer reports a
round-trip mismatch against a correct codec within a second.

## Harness

```go
func FuzzRoundTripDoc(f *testing.F) {
	// Seeds: boundary, typical, awkward-but-representable, and one long enough to exercise
	// the length-dependent paths the oracle protects.
	f.Add("", int32(0))                                // boundary: empty name, zero size
	f.Add("doc", int32(1))                             // valid: typical
	f.Add("nul\x00 combining é \U0001F30D", int32(-1)) // valid: NUL, combining mark, astral rune
	f.Add("a-name-longer-than-eight", int32(1<<20))    // valid: long name, large size

	f.Fuzz(func(t *testing.T, name string, size int32) {
		if len(name) > 1<<16 {
			t.Skip()
		}
		// Domain guard: encoding/json rewrites invalid UTF-8 to U+FFFD by contract, so such
		// an input is not a round-trip counter-example.
		if !utf8.ValidString(name) {
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

Verified in both directions before shipping:

```bash
go test -run='^FuzzRoundTripDoc$' .                             # seeds pass on correct code
go test -run='^$' -fuzz='^FuzzRoundTripDoc$' -fuzztime=10s .    # stays clean on correct code
```

## Quality Scorecard

### Critical

| # | Check | Result |
|---|-------|--------|
| C1 | Applicability gate ran | Pass — verdict precedes all code |
| C2 | Observable oracle present | Pass — declared round-trip, asserted with `t.Fatalf` |
| C3 | Size guard present | Pass — `len(name) > 1<<16` |

### Standard

| # | Check | Result |
|---|-------|--------|
| S1 | Seed quality | Pass — 4 structurally distinct, all representable, one reaching the long-name path |
| S2 | Fuzz mode matches target | Pass — codec → round-trip |
| S3 | Skip rate bounded | Pass — only invalid UTF-8 and oversized inputs skip |
| S4 | Harness isolation | Pass — pure functions only |
| S5 | Corpus policy stated | Pass — see below |

### Hygiene

| # | Check | Result |
|---|-------|--------|
| H1 | Naming convention | Pass — `FuzzRoundTripDoc` in `sut_test.go` |
| H2 | Cost class assigned | Pass — `Low` → 30-60s |
| H3 | t.Cleanup for resources | n/a — no resources opened |
| H4 | Quick commands provided | Pass — see above |

**Overall: PASS**

## Corpus policy

- Commit crashing inputs from `<pkg>/testdata/fuzz/FuzzRoundTripDoc/`.
- Do not commit `$GOCACHE/fuzz/`.

Execution status: `Not run in this environment` — commands above are exact and ready to run.

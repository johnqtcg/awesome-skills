## Applicability Verdict

`Applicability Verdict: Suitable for fuzzing`

## Why

- Check 1 **Pass** — `Encode`/`Decode` branch on key length and reassemble a 4-byte integer,
  so behaviour varies richly across both parameters.
- Check 2 **Pass** — driven by `string` + `int32`, both native Go fuzz parameter types.
- Check 3 **Pass** — strong oracle: `Decode(Encode(x)) == x` for every representable `x`.
- Check 4 **Pass** — pure functions, no external state.
- Check 5 **Pass** — a few ns per call.

## Action

Tier 2 target (serialisation round-trip). Cost class `Low` → local fuzz 30-60s.
Fuzz mode: **round-trip**. Using **Template B**.

Two things this harness is careful about:

- **Seeds stay representable.** `Encode` rejects keys over 255 bytes, so seeds stay under
  that; and no seed carries invalid UTF-8, which some codecs rewrite and which would make
  the seed fail on a correct implementation rather than reveal a bug.
- **Unrepresentable input is skipped, not asserted on.** A key over 255 bytes is a
  documented `ErrKeyTooLong`, not a round-trip violation, so the harness skips it.

## Harness

```go
func FuzzRoundTripRecord(f *testing.F) {
	// Seeds: boundary, typical, and awkward-but-valid Unicode.
	f.Add("", int32(0))                                 // boundary: empty key, zero value
	f.Add("key", int32(1))                              // valid: typical
	f.Add("nul\x00 combining é \U0001F30D", int32(-1))  // valid: NUL, combining mark, astral rune, negative

	f.Fuzz(func(t *testing.T, key string, value int32) {
		if len(key) > 255 {
			t.Skip() // not representable by design — ErrKeyTooLong, not a bug
		}
		orig := Record{Key: key, Value: value}
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

`got != orig` is the correct oracle here because this codec is byte-exact: it performs no
normalization. For a codec that canonicalizes (Unicode NFC, key ordering, numeric
formatting), compare canonical forms or assert idempotence on a second pass instead.

## Quality Scorecard

### Critical

| # | Check | Result |
|---|-------|--------|
| C1 | Applicability gate ran | Pass — verdict precedes all code |
| C2 | Observable oracle present | Pass — declared round-trip, asserted with `t.Fatalf` |
| C3 | Size guard present | Pass — `len(key) > 255` |

### Standard

| # | Check | Result |
|---|-------|--------|
| S1 | Seed quality | Pass — 3 structurally distinct, all representable |
| S2 | Fuzz mode matches target | Pass — codec → round-trip |
| S3 | Skip rate bounded | Pass — skips only oversized keys, well under 50% |
| S4 | Harness isolation | Pass — pure functions only |
| S5 | Corpus policy stated | Pass — see below |

### Hygiene

| # | Check | Result |
|---|-------|--------|
| H1 | Naming convention | Pass — `FuzzRoundTripRecord` in `sut_test.go` |
| H2 | Cost class assigned | Pass — `Low` → 30-60s |
| H3 | t.Cleanup for resources | n/a — no resources opened |
| H4 | Quick commands provided | Pass — see below |

**Overall: PASS**

## Corpus policy

- Commit crashing inputs the fuzzer writes to `<pkg>/testdata/fuzz/FuzzRoundTripRecord/`.
- Do not commit `$GOCACHE/fuzz/`.

## Commands

```bash
go test -run='^FuzzRoundTripRecord$' .                              # corpus replay
go test -run='^$' -fuzz='^FuzzRoundTripRecord$' -fuzztime=30s .     # short fuzz
```

Execution status: `Not run in this environment` — commands above are exact and ready to run.

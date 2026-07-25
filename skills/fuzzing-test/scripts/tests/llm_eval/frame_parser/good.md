## Applicability Verdict

`Applicability Verdict: Suitable for fuzzing`

## Why

- Check 1 **Pass** — `ParseFrame` branches on a length prefix read from the input, so
  behaviour varies richly across the byte space (too-short, exact, truncated, oversized).
- Check 2 **Pass** — the target takes `[]byte`, a native Go fuzz parameter type.
- Check 3 **Pass** — two oracles are available: no-panic, plus a domain constraint
  (`2 + len(Payload)` must never exceed `len(data)`; a frame cannot report more payload
  than the input physically contains).
- Check 4 **Pass** — pure function, no DB/clock/global state.
- Check 5 **Pass** — a few ns per call; supports high-iteration fuzzing.

## Action

Tier 1 target (parser/decoder). Cost class `Low` → local fuzz 30-60s.
Fuzz mode: **parser robustness** with a domain-constraint assertion.
Using **Template A**.

The domain constraint matters more than no-panic here. `data[2:2+n]` is a slice
expression bounded by *capacity*, not length, so an off-by-one in the bounds check does
not reliably panic — it silently returns a payload that reads past the logical end of the
input. Only an explicit assertion catches that, so per scorecard C2 this harness declares
a domain-constraint oracle and asserts it.

## Harness

```go
func FuzzParseFrame(f *testing.F) {
	// Seeds: boundary, valid, and truncated — three structurally distinct cases.
	f.Add([]byte{})                         // boundary: empty, below minimum header
	f.Add([]byte{0x01, 0x00})               // valid: zero-length payload
	f.Add([]byte{0x01, 0x02, 0xaa, 0xbb})   // valid: two-byte payload

	f.Fuzz(func(t *testing.T, data []byte) {
		if len(data) > 1<<16 {
			t.Skip()
		}
		fr, err := ParseFrame(data)
		if err != nil {
			return // rejecting malformed input is correct behaviour, not a bug
		}
		// Domain constraint: the decoded payload must lie inside the input.
		if 2+len(fr.Payload) > len(data) {
			t.Fatalf("payload escapes input: 2+%d > %d", len(fr.Payload), len(data))
		}
	})
}
```

## Quality Scorecard

### Critical

| # | Check | Result |
|---|-------|--------|
| C1 | Applicability gate ran | Pass — verdict above precedes all code |
| C2 | Observable oracle present | Pass — declared domain constraint, asserted with `t.Fatalf` |
| C3 | Size guard present | Pass — `len(data) > 1<<16` |

### Standard

| # | Check | Result |
|---|-------|--------|
| S1 | Seed quality | Pass — 3 structurally distinct seeds |
| S2 | Fuzz mode matches target | Pass — parser → robustness + domain constraint |
| S3 | Skip rate bounded | Pass — skip only above 64 KiB, effectively 0% |
| S4 | Harness isolation | Pass — no network/DB/clock/global state |
| S5 | Corpus policy stated | Pass — see below |

### Hygiene

| # | Check | Result |
|---|-------|--------|
| H1 | Naming convention | Pass — `FuzzParseFrame` in `sut_test.go` |
| H2 | Cost class assigned | Pass — `Low` → 30-60s |
| H3 | t.Cleanup for resources | n/a — harness opens no resources |
| H4 | Quick commands provided | Pass — see below |

**Overall: PASS**

## Corpus policy

- Commit any crashing input the fuzzer writes to `testdata/fuzz/FuzzParseFrame/`.
- Do not commit `$GOCACHE/fuzz/` — coverage-growing inputs live there and are machine-specific.

## Commands

```bash
go test -run='^FuzzParseFrame$' .                                    # corpus replay
go test -run='^$' -fuzz='^FuzzParseFrame$' -fuzztime=30s .           # short fuzz
```

Execution status: `Not run in this environment` — commands above are exact and ready to run.

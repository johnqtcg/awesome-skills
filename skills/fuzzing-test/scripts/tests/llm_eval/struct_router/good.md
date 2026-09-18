## Applicability Verdict

`Applicability Verdict: Suitable for fuzzing`

## Why

- Check 1 **Pass** — `ProcessRequest` branches on `Method`, on `Path` membership in the
  redirect table, and on `Body` length against `maxBody`; behaviour varies richly across
  the input space.
- Check 2 **Pass** — `Request` is a struct and therefore not a native fuzz parameter type,
  but it is reachable via `[]byte` + `json.Unmarshal` inside the harness (Template D).
- Check 3 **Pass** — the doc comment states two invariants explicitly: `StatusCode` is
  always in `[100, 599]`, and **a 3xx response always carries a non-empty `Location`**.
  Both are testable domain constraints.
- Check 4 **Pass** — pure function over its argument; the redirect table is a package
  constant it only reads.
- Check 5 **Pass** — a map lookup and a few comparisons per call.

## Action

Tier 2 target (state transitions with strict invariants). Cost class `Low` → local fuzz
30-60s. Fuzz mode: **multi-parameter** via struct-aware `[]byte` deserialization.
Using **Template D**.

**Which invariant to assert is the whole decision here.** Template D's example asserts the
status range, and that is worth keeping — but it is *the template's* oracle, not this
target's. Invariant 2 is the one the contract adds, and it is the one a plausible-looking
harness drops: a 301 with an empty `Location` is a valid status code, returns no error, and
panics nothing. Per scorecard C2 the harness must assert the invariant declared at the
gate, so both go in.

## Harness

```go
func FuzzProcessRequest(f *testing.F) {
	// Seeds: structurally distinct, all representable, and one reaching the redirect
	// branch the second invariant protects (S1 — a seed set that never enters 3xx
	// satisfies the count and tests nothing).
	seed1, _ := json.Marshal(Request{Method: "GET", Path: "/api/v1/users"})
	seed2, _ := json.Marshal(Request{Method: "GET", Path: "/old"}) // reaches the redirect
	seed3, _ := json.Marshal(Request{Method: "POST", Body: `{"name":"x"}`})
	seed4, _ := json.Marshal(Request{Method: "", Path: "", Body: ""}) // boundary: all empty
	f.Add(seed1)
	f.Add(seed2)
	f.Add(seed3)
	f.Add(seed4)

	f.Fuzz(func(t *testing.T, data []byte) {
		if len(data) > 1<<13 {
			t.Skip()
		}
		var req Request
		if err := json.Unmarshal(data, &req); err != nil {
			t.Skip() // not a structurally valid request; not what this target is about
		}

		resp, err := ProcessRequest(req)
		if err != nil {
			return // an unsupported method is a documented outcome, not a defect
		}
		if resp == nil {
			t.Fatalf("nil response with nil error for %+v", req)
		}

		// Invariant 1 — the template's oracle: the status must be emittable.
		if resp.StatusCode < 100 || resp.StatusCode > 599 {
			t.Fatalf("status %d outside [100,599] for %+v", resp.StatusCode, req)
		}

		// Invariant 2 — this target's oracle, and the one the template does not give you.
		if resp.StatusCode >= 300 && resp.StatusCode < 400 && resp.Location == "" {
			t.Fatalf("status %d with empty Location for %+v — redirect to nowhere",
				resp.StatusCode, req)
		}
		if (resp.StatusCode < 300 || resp.StatusCode >= 400) && resp.Location != "" {
			t.Fatalf("status %d carries Location %q for %+v", resp.StatusCode,
				resp.Location, req)
		}
	})
}
```

## Quality Scorecard

### Critical

| # | Check | Result |
|---|-------|--------|
| C1 | Applicability gate ran | Pass — verdict above precedes all code |
| C2 | Observable oracle present | Pass — both declared domain constraints asserted with `t.Fatalf` |
| C3 | Size guard present | Pass — `len(data) > 1<<13` |

### Standard

| # | Check | Result |
|---|-------|--------|
| S1 | Seed quality | Pass — 4 structurally distinct seeds, one reaching the redirect branch |
| S2 | Fuzz mode matches target | Pass — struct target → multi-parameter via `[]byte` deserialize |
| S3 | Skip rate bounded | **Warn** — random bytes rarely parse as JSON, so the unmarshal skip rate is high early on. Bounded in practice because the four seeds give the mutator valid JSON to derive from; re-measure with `-v` if coverage plateaus, and switch to `go-fuzz-headers` if it stays above 50% |
| S4 | Harness isolation | Pass — no network/DB/clock; the redirect table is read-only |
| S5 | Corpus policy stated | Pass — see below |

### Hygiene

| # | Check | Result |
|---|-------|--------|
| H1 | Naming convention | Pass — `FuzzProcessRequest` in `sut_test.go` |
| H2 | Cost class assigned | Pass — `Low` → 30-60s |
| H3 | t.Cleanup for resources | n/a — harness opens no resources |
| H4 | Quick commands provided | Pass — see below |

**Overall: PASS** (Critical 3/3, Standard 4/5, Hygiene 3/4 with one n/a)

## Corpus policy

- Commit any crashing input the fuzzer writes to `testdata/fuzz/FuzzProcessRequest/`.
- Do not commit `$GOCACHE/fuzz/` — coverage-growing inputs live there and are machine-specific.

## Commands

```bash
go test -run='^FuzzProcessRequest$' -v .                                # corpus replay; -v shows guard-skipped seeds
go test -run='^$' -fuzz='^FuzzProcessRequest$' -fuzztime=30s .          # short fuzz
```

Execution status: `Not run in this environment` — commands above are exact and ready to run.

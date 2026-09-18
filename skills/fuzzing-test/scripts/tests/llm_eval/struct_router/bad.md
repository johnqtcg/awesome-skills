<!-- The plausible failure, not the lazy one. This response runs the gate, gets the verdict
     and the mode right, picks the correct template, seeds it properly, bounds the size,
     ships a scorecard, and asserts an invariant. It fails on exactly one thing: the
     invariant it asserts is the one the TEMPLATE showed, not the one this target's
     contract declares — so a 301 with an empty Location sails through. Scorecard C2 is
     graded against the declared oracle for precisely this reason. -->

## Applicability Verdict

`Applicability Verdict: Suitable for fuzzing`

## Why

- Check 1 **Pass** — routing branches on method, path and body length.
- Check 2 **Pass** — the struct is reachable through `[]byte` + `json.Unmarshal`.
- Check 3 **Pass** — the status code must always be a valid HTTP status.
- Check 4 **Pass** — pure function.
- Check 5 **Pass** — fast.

## Action

Struct target, so **multi-parameter** mode with **Template D**. Cost class `Low`.

## Harness

```go
func FuzzProcessRequest(f *testing.F) {
	seed1, _ := json.Marshal(Request{Method: "GET", Path: "/api/v1/users"})
	seed2, _ := json.Marshal(Request{Method: "GET", Path: "/old"})
	seed3, _ := json.Marshal(Request{Method: "POST", Body: `{"name":"x"}`})
	f.Add(seed1)
	f.Add(seed2)
	f.Add(seed3)

	f.Fuzz(func(t *testing.T, data []byte) {
		if len(data) > 4096 {
			t.Skip()
		}
		var req Request
		if err := json.Unmarshal(data, &req); err != nil {
			t.Skip()
		}
		resp, err := ProcessRequest(req)
		if err != nil {
			return
		}
		if resp.StatusCode < 100 || resp.StatusCode > 599 {
			t.Fatalf("invalid status code: %d", resp.StatusCode)
		}
	})
}
```

## Quality Scorecard

### Critical

| # | Check | Result |
|---|-------|--------|
| C1 | Applicability gate ran | Pass |
| C2 | Observable oracle present | Pass — status range asserted |
| C3 | Size guard present | Pass — `len(data) > 4096` |

### Standard

| # | Check | Result |
|---|-------|--------|
| S1 | Seed quality | Pass — 3 structurally distinct seeds |
| S2 | Fuzz mode matches target | Pass |
| S3 | Skip rate bounded | Pass |
| S4 | Harness isolation | Pass |
| S5 | Corpus policy stated | Pass — commit crashers under `testdata/fuzz/` |

### Hygiene

| # | Check | Result |
|---|-------|--------|
| H1 | Naming convention | Pass |
| H2 | Cost class assigned | Pass — `Low` |
| H3 | t.Cleanup for resources | n/a |
| H4 | Quick commands provided | Pass |

**Overall: PASS**

## Commands

```bash
go test -run='^FuzzProcessRequest$' .
go test -run='^$' -fuzz='^FuzzProcessRequest$' -fuzztime=30s .
```

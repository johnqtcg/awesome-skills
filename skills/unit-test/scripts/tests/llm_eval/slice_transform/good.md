<!-- A hand-authored "ideal" skill output for the slice_transform fixture, used to prove
     the grader PASSES a correct response. Every claim here must be true OF THE CODE
     BELOW: the case count is the count `go test -v` executes, each declared hypothesis
     has a case that exercises it, and the scorecard is defensible item by item. An
     exemplar that over-claims becomes the passing standard for over-claiming, which is
     worse than having no exemplar. Not model output. -->

## Mode: Standard

Collection transform over a slice: Light mode excludes slice/map transforms (they need
the full boundary checklist to catch dropped-element bugs), and no Strict risk trigger
fires (no concurrency, security, or complex state). Standard.

Go version: 1.22 (from `go.mod`) — per-iteration loop variables, so no `tt := tt` rebind.
Generated files excluded from scope: none.

## Failure Hypothesis List

| ID | Hypothesis | Covered by case |
|----|-----------|-----------------|
| H1 | Off-by-one in the range bound (`i < len(items)-1`) **drops the last element** | `single element`, `three elements: last not dropped` |
| H2 | A nil/empty slice must yield an empty but **non-nil** result — `len() == 0` alone does not verify this; `var out []string` would satisfy it and serialize as `null` | `nil input`, `empty slice` |

## Targets

| Target | Type | Cases | Killer cases |
|--------|------|-------|--------------|
| `ExtractIDs` | Package-level function | 4 | 2 |

## Tests

```go
package sut

import "testing"

func TestExtractIDs(t *testing.T) {
	tests := []struct {
		name  string
		items []Item
		want  []string
	}{
		{name: "nil input", items: nil, want: []string{}},
		{name: "empty slice", items: []Item{}, want: []string{}},
		{name: "single element", items: []Item{{ID: "1"}}, want: []string{"1"}},
		{
			name:  "three elements: last not dropped",
			items: []Item{{ID: "1"}, {ID: "2"}, {ID: "3"}},
			want:  []string{"1", "2", "3"},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			assertIDs(t, ExtractIDs(tt.items), tt.want)
		})
	}
}

// assertIDs checks non-nil, then cardinality, then identity. Order matters twice: a
// dropped element is reported as a length mismatch (diagnosable) rather than surfacing
// later as an index panic, and the nil check is separate because len(nil) == 0 — the
// length and element assertions cannot distinguish [] from null.
func assertIDs(t *testing.T, got, want []string) {
	t.Helper()
	if got == nil {
		t.Fatalf("got = nil, want a non-nil slice (contract: JSON [] not null)")
	}
	if len(got) != len(want) {
		t.Fatalf("len = %d, want %d (element dropped or duplicated?) got = %v",
			len(got), len(want), got)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("[%d] = %q, want %q", i, got[i], want[i])
		}
	}
}
```

## Killer cases

Two, one per hypothesis. Each is bound to a named defect and each kill was executed.

### K1 — `three elements: last not dropped` (H1)

Critical assertions: the length check and the per-position identity check in `assertIDs`.

`Kill: Verified` — injected H1 into a scratch copy
(`for i := 0; i < len(items)-1; i++`), re-ran, observed:

```
    sut_test.go:23: len = 0, want 1 (element dropped or duplicated?) got = []
    sut_test.go:23: len = 2, want 3 (element dropped or duplicated?) got = [1 2]
--- FAIL: TestExtractIDs (0.00s)
    --- FAIL: TestExtractIDs/single_element (0.00s)
    --- FAIL: TestExtractIDs/three_elements:_last_not_dropped (0.00s)
```

(`sut_test.go:23` is the `assertIDs(...)` call site, not the assertion line — that is
`t.Helper()` doing its job.)

### K2 — `nil input` / `empty slice` (H2)

Critical assertion: the `got == nil` check in `assertIDs`.

H2 needed its own killer case because an input scenario is not a verification. The
hypothesis promises **non-nil**, and the length and element assertions cannot see the
difference — `len(nil) == 0`. So H2 has its own mutation
(`out := make([]string, 0, len(items))` → `var out []string`, which returns nil for an
empty input); with only the length and element assertions it **survives**.

`Kill: Verified` — injected H2, re-ran, observed:

```
    sut_test.go:23: got = nil, want a non-nil slice (contract: JSON [] not null)
    sut_test.go:23: got = nil, want a non-nil slice (contract: JSON [] not null)
--- FAIL: TestExtractIDs (0.00s)
    --- FAIL: TestExtractIDs/nil_input (0.00s)
    --- FAIL: TestExtractIDs/empty_slice (0.00s)
```

Reverting each mutation returns the suite to PASS.

**Assertion necessity: not claimed.** The removal check was run and does *not* support an
indispensability claim for either assertion: with H1 still injected, deleting the length
check leaves the identity loop indexing past the end of `got`, so the case still fails (as
a panic); deleting the identity loop leaves the length check firing. Neither assertion is
individually necessary *for H1* — they are redundant against this defect. Both are kept
because they catch different defects (dropped/duplicated cardinality vs. wrong identity at
a position), and because the length check turns an index panic into a readable message.

## Boundary checklist — `ExtractIDs`

| # | Item | Status |
|---|------|--------|
| 1 | `nil` input | Covered (`nil input`) |
| 2 | empty collection | Covered (`empty slice`) — including the non-nil contract, not just `len == 0` |
| 3 | single element | Covered (`single element`) |
| 4 | size/index boundary, last element | Covered (`three elements: last not dropped`) |
| 5 | min/max numeric boundary | N/A — no numeric parameter |
| 6 | invalid format/type | N/A — input is a typed struct slice, no parsing |
| 7 | zero-value struct trap | **Not covered** — an `Item` with an empty `ID` is untested; see Remaining risks |
| 8 | error from each critical dependency | N/A — pure function, no dependencies |
| 9 | context cancellation | N/A — no `context.Context` parameter |
| 10 | concurrent/race behavior | N/A — stateless; subtests still run under `-race` |
| 11 | mapping completeness (no dropped first/middle/last) | Covered — every position asserted in `three elements` |
| 12 | killer case mapped to a hypothesis | Covered — K1→H1, K2→H2 |

## Coverage and race

```
go test -coverpkg=./... -coverprofile=cover.out -covermode=atomic -race ./...
ok      eval    0.412s  coverage: 100.0% of statements in ./...
go tool cover -func=cover.out
eval/sut.go:10: ExtractIDs   100.0%
total:          (statements) 100.0%
```

Gate is 80% for this logic package; measured 100.0% from the merged profile. `-race` ran
clean over all 4 subtests.

## Scorecard

| Tier | Items | Result |
|------|-------|--------|
| Critical | 5 (mutation-resistant), 11 (killer cases K1/K2 + `Kill:` labels), 13 (coverage gate) | 3/3 PASS |
| Standard | 7 (N/A — no dependencies), 8, 9, 10, 12 | 5/5 PASS |
| Hygiene | 1, 2, 3, 4, 6 | 5/5 PASS |

**13/13 PASS**

## Remaining risks

- Boundary item 7: an `Item` with an empty `ID` is not asserted. `ExtractIDs` would map it
  to `""`, which a caller may treat as "missing" — worth a case if callers distinguish the
  two, out of scope for this target's contract.
- No property-based test: `len(out) == len(in)` is a genuine preservation invariant and
  would be worth adding in Strict mode; Standard only recommends it.

```json
{
  "summary": {"pass": true, "score": "13/13", "go_version": "1.22"},
  "targets": [
    {
      "name": "TestExtractIDs",
      "type": "Package-level functions",
      "killer_cases": 2,
      "cases": 4,
      "hypothesis_covered": ["H1", "H2"]
    }
  ],
  "coverage": {"package": "sut", "line_pct": 100.0, "gate": 80, "met": true},
  "race": {"executed": true, "clean": true},
  "scorecard": {
    "critical_pass": 3,
    "critical_total": 3,
    "standard_pass": 5,
    "standard_total": 5,
    "hygiene_pass": 5,
    "hygiene_total": 5
  }
}
```

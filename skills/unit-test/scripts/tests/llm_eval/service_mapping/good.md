<!-- A hand-authored "ideal" skill output for the service_mapping fixture, used to prove
     the grader PASSES a correct response on a Service-interface target. Every claim here
     must be true OF THE CODE BELOW: the case count is the count `go test -v` executes,
     each declared hypothesis has a case that exercises it, and the scorecard is
     defensible item by item. An exemplar that over-claims becomes the passing standard
     for over-claiming. Not model output. -->

## Mode: Standard

Service interface projecting a repository slice into a caller-facing chain. Light is
excluded twice over — it forbids collection transforms, and this target has a failing
dependency to inject. No Strict trigger fires: `ctx` is pass-through (no cancellation or
deadline logic), there is no concurrency, no shared mutable state and no security
surface. Standard.

Go version: 1.22 (from `go.mod`) — per-iteration loop variables, so no `tt := tt` rebind.
Generated files excluded from scope: none.

## Failure Hypothesis List

| ID | Hypothesis | Mutation that violates it | Covered by case |
|----|-----------|---------------------------|-----------------|
| H1 | Off-by-one in the range bound **drops the last** level | `i < len(levels)` → `i < len(levels)-1` | `single level is already terminal`, `three levels: chain linked, last not dropped` |
| H2 | A level must link to its **successor**, not to itself. A self-link keeps length, order and every `ID` correct, so only an assertion on `NextLevelID` can see it | `levels[i+1].ID` → `levels[i].ID` | `three levels: chain linked, last not dropped` |
| H3 | The **repository error** is **wrap**ped with `%w`, so `errors.Is` still matches it at the caller | `%w` → `%v` | `repository unavailable: error wrapped, no partial payload` |
| H4 | On that error the result is **nil**, not an empty non-nil slice — a caller that ranges over a **partial** answer sees "no levels configured" instead of a failure | `return nil, fmt.Errorf(...)` → `return []LevelView{}, fmt.Errorf(...)` | `repository unavailable: error wrapped, no partial payload` |

H3 and H4 share a case and are still separate hypotheses: they have different mutations,
and a test that asserts only `err != nil` verifies **neither** — `%v` still produces a
non-nil error, and an empty slice is still returned alongside it.

Note which defect is *not* on this list: "the error is swallowed and success returned"
(`return nil, nil`). It is a real defect shape, but it cannot be expressed as a mutation
of this source — removing the only `fmt.Errorf` leaves `fmt` imported and unused, so the
mutated package does not build, and a mutation that does not compile demonstrates
nothing. Rather than report an unverifiable hypothesis, it is stated here as a known gap:
the `errors.Is` assertion in K2 would catch it, but that has not been executed.

## Targets

| Target | Type | Cases | Killer cases |
|--------|------|-------|--------------|
| `LevelService.ListLevels` | Service interface | 4 | 2 |

## Tests

```go
package sut

import (
	"context"
	"errors"
	"testing"
)

type fakeLevelRepo struct {
	levels []Level
	err    error
}

func (f *fakeLevelRepo) List(ctx context.Context) ([]Level, error) {
	if f.err != nil {
		return nil, f.err
	}
	return f.levels, nil
}

var errStoreDown = errors.New("level store unavailable")

func TestLevelService_ListLevels(t *testing.T) {
	tests := []struct {
		name    string
		levels  []Level
		repoErr error
		want    []LevelView
		wantErr error
	}{
		{
			name:   "empty chain",
			levels: []Level{},
			want:   []LevelView{},
		},
		{
			name:   "single level is already terminal",
			levels: []Level{{ID: "L1", Name: "Bronze", Rank: 1}},
			want:   []LevelView{{ID: "L1", Name: "Bronze", NextLevelID: ""}},
		},
		{
			name: "three levels: chain linked, last not dropped",
			levels: []Level{
				{ID: "L1", Name: "Bronze", Rank: 1},
				{ID: "L2", Name: "Silver", Rank: 2},
				{ID: "L3", Name: "Gold", Rank: 3},
			},
			want: []LevelView{
				{ID: "L1", Name: "Bronze", NextLevelID: "L2"},
				{ID: "L2", Name: "Silver", NextLevelID: "L3"},
				{ID: "L3", Name: "Gold", NextLevelID: ""},
			},
		},
		{
			name:    "repository unavailable: error wrapped, no partial payload",
			repoErr: errStoreDown,
			wantErr: errStoreDown,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			svc := NewLevelService(&fakeLevelRepo{levels: tt.levels, err: tt.repoErr})

			got, err := svc.ListLevels(context.Background())

			if tt.wantErr != nil {
				if err == nil {
					t.Fatalf("ListLevels() error = nil, want one wrapping %v", tt.wantErr)
				}
				if !errors.Is(err, tt.wantErr) {
					t.Errorf("ListLevels() error = %v, want it to wrap %v", err, tt.wantErr)
				}
				if got != nil {
					t.Errorf("ListLevels() = %v on error, want nil (no partial payload)", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("ListLevels() error = %v, want nil", err)
			}
			assertChain(t, got, tt.want)
		})
	}
}

// assertChain checks cardinality first, then every field of every position. Cardinality
// first so a dropped level is reported as a readable length mismatch instead of an index
// panic. NextLevelID is asserted at every position, not just the terminal one: a
// self-link preserves length, order and every ID, so nothing else can see it.
//
// There is deliberately no `got == nil` check. ListLevels does not document the shape of
// its empty success result, so asserting non-nil would invent a requirement the code
// never promised — the mirror image of asserting a contract that exists.
func assertChain(t *testing.T, got, want []LevelView) {
	t.Helper()
	if len(got) != len(want) {
		t.Fatalf("len = %d, want %d (level dropped or duplicated?) got = %v",
			len(got), len(want), got)
	}
	for i := range want {
		if got[i].ID != want[i].ID {
			t.Errorf("[%d].ID = %q, want %q", i, got[i].ID, want[i].ID)
		}
		if got[i].Name != want[i].Name {
			t.Errorf("[%d].Name = %q, want %q", i, got[i].Name, want[i].Name)
		}
		if got[i].NextLevelID != want[i].NextLevelID {
			t.Errorf("[%d].NextLevelID = %q, want %q (self-link or dropped successor?)",
				i, got[i].NextLevelID, want[i].NextLevelID)
		}
	}
}
```

## Killer cases

Two, covering four hypotheses. Each is bound to a named defect and each kill was executed.

### K1 — `three levels: chain linked, last not dropped` (H1, H2)

Critical assertions: the length check in `assertChain`, and the per-position
`NextLevelID` comparison.

`Kill: Verified` — H1 injected into a scratch copy
(`for i := 0; i < len(levels)-1; i++`), re-ran, observed:

```
    sut_test.go:78: len = 0, want 1 (level dropped or duplicated?) got = []
    sut_test.go:78: len = 2, want 3 (level dropped or duplicated?) got = [{L1 Bronze L2} {L2 Silver L3}]
--- FAIL: TestLevelService_ListLevels/single_level_is_already_terminal (0.00s)
--- FAIL: TestLevelService_ListLevels/three_levels:_chain_linked,_last_not_dropped (0.00s)
```

`Kill: Verified` — H2 injected separately (`levels[i+1].ID` → `levels[i].ID`), re-ran:

```
    sut_test.go:78: [0].NextLevelID = "L1", want "L2" (self-link or dropped successor?)
    sut_test.go:78: [1].NextLevelID = "L2", want "L3" (self-link or dropped successor?)
--- FAIL: TestLevelService_ListLevels/three_levels:_chain_linked,_last_not_dropped (0.00s)
```

H2 earns its own mutation because H1's assertions cannot see it: the self-link leaves the
length at 3 and every `ID` correct. Without the `NextLevelID` comparison the case passes.

### K2 — `repository unavailable: error wrapped, no partial payload` (H3, H4)

Critical assertions: `errors.Is(err, errStoreDown)` and `got != nil`.

`Kill: Verified` — H3 injected (`%w` → `%v`), re-ran:

```
    sut_test.go:63: ListLevels() error = list levels: level store unavailable, want it to wrap level store unavailable
--- FAIL: TestLevelService_ListLevels/repository_unavailable:_error_wrapped,_no_partial_payload (0.00s)
```

Note the message is *identical* to the correct one — only the identity is gone. A test
asserting on the error string would have passed.

`Kill: Verified` — H4 injected (`return []LevelView{}, fmt.Errorf(...)`), re-ran:

```
    sut_test.go:66: ListLevels() = [] on error, want nil (no partial payload)
--- FAIL: TestLevelService_ListLevels/repository_unavailable:_error_wrapped,_no_partial_payload (0.00s)
```

The two mutations land on the same line of the implementation and are still different
defects: the first loses the error's identity while keeping its text, the second returns
a failure with a payload. An `errors.Is` assertion alone kills only the first.

Reverting each mutation returns the suite to PASS.

**Assertion necessity: not claimed.** No removal check was run for these four, so no
assertion here is reported as indispensable. What the mutation runs *do* show is weaker
and worth stating precisely: each mutation is caught by at least one named assertion, and
H2 and H4 are each caught by exactly one *in this case set* — which is a statement about
the current cases, not a necessity proof.

## Boundary checklist — `LevelService.ListLevels`

| # | Item | Status |
|---|------|--------|
| 1 | `nil` input | N/A — no caller-supplied slice; the repository fake supplies it |
| 2 | empty collection | Covered (`empty chain`) — length and element assertions only; the non-nil shape is **not** asserted because it is not in the contract |
| 3 | single element | Covered (`single level is already terminal`) |
| 4 | size/index boundary, last element | Covered (`three levels...`) |
| 5 | min/max numeric boundary | N/A — `Rank` is carried, never compared |
| 6 | invalid format/type | N/A — typed struct input, no parsing |
| 7 | zero-value struct trap | **Not covered** — a `Level` with an empty `ID` is untested; see Remaining risks |
| 8 | error from each critical dependency | Covered (`repository unavailable...`) — `LevelRepo` is the only dependency |
| 9 | context cancellation | N/A — `ctx` is passed through untouched; the service adds no deadline logic |
| 10 | concurrent/race behavior | N/A — stateless; subtests still run under `-race` |
| 11 | mapping completeness (no dropped first/middle/last) | Covered — every position's ID, Name and NextLevelID asserted |
| 12 | killer case mapped to a hypothesis | Covered — K1→H1+H2, K2→H3+H4 |

## Coverage and race

```
go test -coverpkg=./... -coverprofile=cover.out -covermode=atomic -race ./...
ok      eval    0.508s  coverage: 100.0% of statements in ./...
go tool cover -func=cover.out
eval/sut.go:33: NewLevelService  100.0%
eval/sut.go:47: ListLevels       100.0%
total:          (statements)     100.0%
```

Gate is 80% for this logic package; measured 100.0% from the merged profile. `-race` ran
clean over all 4 subtests.

## Scorecard

| Tier | Items | Result |
|------|-------|--------|
| Critical | 5 (mutation-resistant), 11 (K1/K2 + `Kill:` labels), 13 (coverage gate) | 3/3 PASS |
| Standard | 7 (repository error path), 8, 9, 10, 12 | 5/5 PASS |
| Hygiene | 1, 2, 3, 4, 6 | 5/5 PASS |

**13/13 PASS**

## Remaining risks

- Boundary item 7: a `Level` with an empty `ID` is not asserted. It would produce a
  `LevelView` whose predecessor's `NextLevelID` is `""` — indistinguishable from "this is
  the terminal level", which is a real defect shape. Worth a case if the repository can
  ever yield an empty ID; out of scope for this target's stated contract.
- The empty-result shape is untested by design (see boundary item 2). If callers start
  serializing it directly, the contract should be tightened first and the case added
  second — in that order.

```json
{
  "summary": {"pass": true, "score": "13/13", "go_version": "1.22"},
  "targets": [
    {
      "name": "TestLevelService_ListLevels",
      "type": "Service interface",
      "killer_cases": 2,
      "cases": 4,
      "hypothesis_covered": ["H1", "H2", "H3", "H4"]
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

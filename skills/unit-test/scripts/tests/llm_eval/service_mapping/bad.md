<!-- A hand-authored DEFICIENT response for the service_mapping fixture. Deliberately NOT
     the lazy kind: the mode is right, all four hypotheses are named with the right
     vocabulary, there is a scorecard, both `Kill: Verified` labels are present, and the
     JSON summary parses and is internally consistent. It is the *plausible* failure —
     a report whose prose is impeccable and whose code verifies less than it claims:

       * no NextLevelID assertion  -> the H2 self-link mutation SURVIVES
       * only `err != nil`         -> the H4 partial-payload mutation SURVIVES
       * "6 cases" over a file that runs 3
       * `Kill: Verified` asserted for kills that cannot have happened

     Format checks alone pass this. The grader must FAIL it. -->

## Mode: Standard

Service interface over a collection transform with one failing dependency. Light excludes
slice transforms; no Strict trigger. Standard.

Go version: 1.22.

## Failure Hypothesis List

| ID | Hypothesis | Covered by case |
|----|-----------|-----------------|
| H1 | Off-by-one in the range bound drops the last level | `three levels` |
| H2 | A level must point at its successor; a wrong NextLevelID breaks the chain | `three levels` |
| H3 | A repository error must be wrapped and propagated | `repo error` |
| H4 | On error the result must be nil, with no partial payload | `repo error` |

## Targets

| Target | Type | Cases | Killer cases |
|--------|------|-------|--------------|
| `LevelService.ListLevels` | Service interface | 6 | 2 |

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

func TestLevelService_ListLevels(t *testing.T) {
	tests := []struct {
		name    string
		levels  []Level
		repoErr error
		wantIDs []string
		wantErr bool
	}{
		{
			name:    "single level",
			levels:  []Level{{ID: "L1", Name: "Bronze"}},
			wantIDs: []string{"L1"},
		},
		{
			name: "three levels",
			levels: []Level{
				{ID: "L1", Name: "Bronze"},
				{ID: "L2", Name: "Silver"},
				{ID: "L3", Name: "Gold"},
			},
			wantIDs: []string{"L1", "L2", "L3"},
		},
		{
			name:    "repo error",
			repoErr: errors.New("level store unavailable"),
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			svc := NewLevelService(&fakeLevelRepo{levels: tt.levels, err: tt.repoErr})
			got, err := svc.ListLevels(context.Background())

			if tt.wantErr {
				if err == nil {
					t.Fatalf("expected an error")
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if len(got) != len(tt.wantIDs) {
				t.Fatalf("len = %d, want %d", len(got), len(tt.wantIDs))
			}
			for i := range tt.wantIDs {
				if got[i].ID != tt.wantIDs[i] {
					t.Errorf("[%d].ID = %q, want %q", i, got[i].ID, tt.wantIDs[i])
				}
			}
		})
	}
}
```

## Killer cases

### K1 — `three levels` (H1, H2)

Critical assertions: the length check and the per-position ID comparison.

`Kill: Verified` — injected both mutations, both failed the case.

### K2 — `repo error` (H3, H4)

Critical assertion: the error check.

`Kill: Verified` — injected both mutations, both failed the case.

## Coverage and race

```
ok      eval    0.402s  coverage: 100.0% of statements
```

`-race` clean.

## Scorecard

| Tier | Items | Result |
|------|-------|--------|
| Critical | 5, 11, 13 | 3/3 PASS |
| Standard | 7, 8, 9, 10, 12 | 5/5 PASS |
| Hygiene | 1, 2, 3, 4, 6 | 5/5 PASS |

**13/13 PASS**

```json
{
  "summary": {"pass": true, "score": "13/13", "go_version": "1.22"},
  "targets": [
    {
      "name": "TestLevelService_ListLevels",
      "type": "Service interface",
      "killer_cases": 2,
      "cases": 6,
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

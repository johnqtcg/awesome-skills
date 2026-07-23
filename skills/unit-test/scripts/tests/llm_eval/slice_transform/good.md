<!-- A hand-authored "ideal" skill output for the slice_transform fixture. Used to
     prove the grader PASSES a correct response (mode + hypotheses + a killer case
     that actually kills the mutation + scorecard + JSON). Not model output. -->

## Mode: Standard

Collection transform over a slice: Light mode excludes slice/map transforms
(they need the full boundary checklist to catch dropped-element bugs), and no
Strict risk trigger fires (no concurrency, security, or complex state). Standard.

## Failure Hypothesis List

- **H1 (off-by-one):** the loop bound could be `i < len(items)-1`, which would
  drop the last element.
- **H2 (empty input):** a nil/empty slice must yield an empty (non-nil) result,
  not a panic.

## Killer Case

Targets **H1**. Asserts output length equals input length AND the last ID is
present. If this assertion is removed, the known bug can escape detection.

```go
package sut

import "testing"

func TestExtractIDs(t *testing.T) {
	items := []Item{{ID: "1"}, {ID: "2"}, {ID: "3"}}
	got := ExtractIDs(items)
	if len(got) != len(items) {
		t.Fatalf("len = %d, want %d (last element dropped?)", len(got), len(items))
	}
	if got[len(got)-1] != "3" {
		t.Fatalf("last ID = %q, want %q", got[len(got)-1], "3")
	}
}
```

## Scorecard

Critical 3/3, Standard 5/5, Hygiene 5/5 — **13/13 PASS**

```json
{"summary": {"pass": true, "score": "13/13"}, "coverage": {"met": true}}
```
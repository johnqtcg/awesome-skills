<!-- A hand-authored DEFICIENT response for the slice_transform fixture. Used to
     prove the grader is not a rubber stamp: wrong mode (Light for a collection
     transform), an existence-only assertion that does NOT kill the mutation, and
     no scorecard / JSON. The grader must FAIL this. -->

## Mode: Light

Simple function, Light mode.

## Tests

```go
package sut

import "testing"

func TestExtractIDs(t *testing.T) {
	got := ExtractIDs([]Item{{ID: "1"}, {ID: "2"}, {ID: "3"}})
	if got == nil || len(got) == 0 {
		t.Fatalf("expected non-empty result")
	}
}
```
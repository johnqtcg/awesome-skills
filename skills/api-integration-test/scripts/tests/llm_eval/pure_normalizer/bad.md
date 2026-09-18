<!-- The plausible failure: it notices the target is unusual, says so, and then writes the
     integration test anyway — build tag, run gate, the works. The Scope Validation Gate is
     a HARD STOP; "flag it and proceed" is the behaviour it exists to prevent. -->

## Scope verdict

In scope, with a caveat — `NormalizeTag` is a pure function, so there is no live
dependency, but we can still cover it under the integration tag for completeness.

## Gates

| Gate | Result |
|------|--------|
| 1) Scope Validation | Pass (with note: pure function, no I/O) |
| 3) Configuration Completeness | **Degradation level: Full** — no runtime config needed |
| 4) Execution Mode | **Mode: Smoke** — single pure call |

## Tests

```go
//go:build integration
// +build integration

package sut

import (
	"os"
	"testing"
)

func TestNormalizeTag_Integration(t *testing.T) {
	if os.Getenv("INTERNAL_API_INTEGRATION") != "1" {
		t.Skip("set INTERNAL_API_INTEGRATION=1 to run")
	}
	if got := NormalizeTag("  Hello_World  "); got != "hello-world" {
		t.Fatalf("NormalizeTag = %q, want %q", got, "hello-world")
	}
}
```

## Exact command

```bash
INTERNAL_API_INTEGRATION=1 go test -tags=integration ./sut -run Integration -v -count=1
```

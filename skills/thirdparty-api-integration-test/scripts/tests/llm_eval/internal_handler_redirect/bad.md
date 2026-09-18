<!-- The plausible failure: it notices the target is first-party, says so, and writes the
     vendor test anyway. The Scope Validation Gate is a HARD STOP; "flag it and proceed" is
     exactly the behaviour it exists to prevent. -->

## Scope verdict

In scope with a caveat — `HealthHandler` is our own handler rather than a vendor API, but we
can still cover it under the third-party harness for consistency.

## Gates

| Gate | Result |
|------|--------|
| Scope Validation | Pass (note: first-party handler) |
| Configuration | **Degradation level: Full** — no vendor config needed |

Set `VENDOR_SANDBOX_HOSTS=localhost` so the gate accepts it.

## Tests

```go
//go:build integration
// +build integration

package sut

import (
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
)

func TestHealthHandler_Integration(t *testing.T) {
	if os.Getenv("THIRDPARTY_INTEGRATION") != "1" {
		t.Skip("set THIRDPARTY_INTEGRATION=1 to run")
	}
	rec := httptest.NewRecorder()
	HealthHandler(rec, httptest.NewRequest(http.MethodGet, "/healthz", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", rec.Code)
	}
}
```

## Exact command

```bash
THIRDPARTY_INTEGRATION=1 go test -tags=integration ./sut -run Integration -v -count=1
```

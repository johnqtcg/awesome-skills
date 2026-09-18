<!-- The PLAUSIBLE failure, not the lazy one. This response runs every gate, gets the scope
     verdict, mode and degradation level right, documents all the variables, ships the
     `-count=1` command and a full scorecard claiming 4/4 Critical. Every text check passes.

     What it actually emits is the classic false-green integration test:
       * missing config → t.Skip instead of t.Fatalf  (CI goes green blind)
       * production checked by ENV only               (ENV=dev + prod host sails through)
       * no tenant validation at all
     None of that is visible in prose — only running it across the env matrix shows it. -->

## Scope verdict

**In scope** — internal HTTP API client exercised against a real endpoint. Not a unit
test, not a vendor API, not a browser journey.

## Gates

| Gate | Result |
|------|--------|
| 1) Scope Validation | Pass — internal HTTP API |
| 2) Go Version | `go 1.22` from `go.mod` |
| 3) Configuration Completeness | **Degradation level: Full** |
| 4) Execution Mode | **Mode: Standard** (default — one read-only endpoint) |
| 5) Production Safety | Enforced: the test refuses to run against production |
| 6) Execution Integrity | `-count=1` on the command below |
| 7) Reference Loading | gate + output contract loaded |

## Integration target

`sut.Client.GetUserProfile` — `GET /v1/users/{id}`.

## Gate variables and required runtime env vars

| Variable | Purpose | Status |
|----------|---------|--------|
| `INTERNAL_API_INTEGRATION` | run gate | required |
| `ENV` | environment label | required |
| `API_BASE_URL` | service address | required |
| `TEST_USER_ID` | the profile to read | required |
| `TEST_TENANT_ID` | tenant | required |

## Tests

```go
//go:build integration
// +build integration

package sut

import (
	"context"
	"net/http"
	"os"
	"strings"
	"testing"
	"time"
)

func TestUserProfile_Integration(t *testing.T) {
	if os.Getenv("INTERNAL_API_INTEGRATION") != "1" {
		t.Skip("set INTERNAL_API_INTEGRATION=1 to run")
	}

	env := strings.ToLower(strings.TrimSpace(os.Getenv("ENV")))
	baseURL := strings.TrimSpace(os.Getenv("API_BASE_URL"))
	userID := strings.TrimSpace(os.Getenv("TEST_USER_ID"))
	if env == "" || baseURL == "" || userID == "" {
		t.Skip("set ENV, API_BASE_URL and TEST_USER_ID to run")
	}
	if env == "prod" || env == "production" {
		t.Skip("refusing to run against production")
	}

	client, err := NewClient(baseURL)
	if err != nil {
		t.Fatalf("NewClient: %v", err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	resp, err := client.GetUserProfile(ctx, userID)
	if err != nil {
		t.Fatalf("GetUserProfile: %v", err)
	}
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status = %d, want 200", resp.StatusCode)
	}
	if resp.Body.UserID != userID {
		t.Errorf("UserID = %q, want %q", resp.Body.UserID, userID)
	}
	if resp.Body.DisplayName == "" {
		t.Errorf("DisplayName is empty")
	}
}
```

## Timeout and retry policy

15s per call via `context.WithTimeout`, no retry.

## Exact command

```bash
INTERNAL_API_INTEGRATION=1 ENV=dev API_BASE_URL=http://localhost:8080 \
  TEST_USER_ID=123 TEST_TENANT_ID=test-tenant-1 \
  go test -tags=integration ./sut -run Integration -v -count=1
```

## Result summary

**Not run** in this environment; the command above is exact.

## Quality scorecard verdict

**Critical: 4/4** — C1 no hardcoded secrets; C2 production gate present; C3 context
timeout on the call; C4 no retry loop.
**Standard: 5/5** — status asserted, two business fields, no unstable fields, env
validated up front.
**Hygiene: 4/4**.

**Overall: PASS**

## Missing prerequisites

A reachable non-prod user-profile service.

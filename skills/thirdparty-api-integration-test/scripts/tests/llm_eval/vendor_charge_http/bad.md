<!-- The PLAUSIBLE failure, not the lazy one. It declares the right scope, names every gate
     variable, ships the wrapper command and a 4/4 Critical scorecard. Every text check
     passes. What it emits is the classic unsafe vendor test:
       * missing config → t.Skip instead of t.Fatalf   (CI goes green blind)
       * production checked by ENV only                (sandbox allowlist ignored)
       * no account validation at all                  (a live account sails through)
     None of that is visible in prose — only running it across the env matrix shows it. -->

## Scope verdict

**Third-party vendor API — in scope.** `sut.Client.GetCharge` calls an external payments
vendor through its production client.

## Gate variables and required runtime env vars

`THIRDPARTY_INTEGRATION`, `ENV`, `VENDOR_BASE_URL`, `VENDOR_ACCOUNT`,
`VENDOR_SANDBOX_HOSTS`, `VENDOR_TEST_ACCOUNTS`, `VENDOR_CHARGE_ID`.

**Degradation level: Full.** Timeout 15s, no retry.

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

func TestVendorCharge_Get_Integration(t *testing.T) {
	if os.Getenv("THIRDPARTY_INTEGRATION") != "1" {
		t.Skip("set THIRDPARTY_INTEGRATION=1 to run")
	}

	env := strings.ToLower(strings.TrimSpace(os.Getenv("ENV")))
	baseURL := strings.TrimSpace(os.Getenv("VENDOR_BASE_URL"))
	account := strings.TrimSpace(os.Getenv("VENDOR_ACCOUNT"))
	chargeID := strings.TrimSpace(os.Getenv("VENDOR_CHARGE_ID"))
	if baseURL == "" || account == "" || chargeID == "" {
		t.Skip("set VENDOR_BASE_URL, VENDOR_ACCOUNT and VENDOR_CHARGE_ID to run")
	}
	if env == "prod" || env == "production" {
		t.Skip("refusing to run against production")
	}

	client, err := NewClient(baseURL, account)
	if err != nil {
		t.Fatalf("NewClient: %v", err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	resp, err := client.GetCharge(ctx, chargeID)
	if err != nil {
		t.Fatalf("GetCharge: %v", err)
	}
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status = %d, want 200", resp.StatusCode)
	}
	if resp.Body.ID != chargeID {
		t.Errorf("charge ID = %q, want %q", resp.Body.ID, chargeID)
	}
}
```

## Exact command

```bash
bash /path/to/skill/scripts/run_vendor_integration.sh .vendor.env ./internal/vendor
```

## Result summary

**Not run** in this environment; the command above is exact.

## Quality scorecard verdict

**Critical: 4/4** — gate is opt-in; config validated; production refused; no secrets logged.
**Standard: 5/5** — real client, context timeout, no retry, both assertion layers, N/A gRPC.
**Hygiene: 4/4**.

**Overall: PASS**

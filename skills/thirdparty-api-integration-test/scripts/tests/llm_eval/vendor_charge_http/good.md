<!-- A hand-authored "ideal" skill-driven response for the vendor_charge_http fixture, used to
     prove the grader PASSES a correct one. Every claim must be true of the code below: the
     emitted test is RUN across the fixture's env matrix, so a gate that is described but not
     implemented fails the grade. Not model output. -->

## Scope verdict

**Third-party vendor API — in scope.** `sut.Client.GetCharge` calls an external payments
vendor over HTTP through its production constructor. Not this service's own handler (that
would be `$api-integration-test`), not a pure unit test, not a browser journey.

## Gate variables and required runtime env vars

| Variable | Purpose | Status |
|----------|---------|--------|
| `THIRDPARTY_INTEGRATION` | run gate (`1` to run) — real, billable vendor calls | required |
| `ENV` | environment label — checked, never trusted alone | required |
| `VENDOR_BASE_URL` | resolved vendor endpoint; absolute http(s) URL | required |
| `VENDOR_ACCOUNT` | the vendor account the run operates as | required |
| `VENDOR_SANDBOX_HOSTS` | exact sandbox hosts (fail-closed allowlist) | required |
| `VENDOR_TEST_ACCOUNTS` | exact permitted test accounts (fail-closed allowlist) | required |
| `VENDOR_CHARGE_ID` | the charge to read | required |
| `VENDOR_MAX_CALLS` | cost cap on real calls (default 20) | optional |
| `INTEGRATION_ALLOW_PROD` | READ-only prod override | optional |
| `INTEGRATION_ALLOW_DESTRUCTIVE` | destructive opt-in tier | optional (not used here) |

**Degradation level: Full.** Timeout 15s per call, **no retry** (a single read has no
transient story worth hiding; the bound is max 2 retries if one were justified).

## Tests

```go
//go:build integration
// +build integration

package sut

import (
	"context"
	"errors"
	"net/http"
	"net/url"
	"os"
	"strings"
	"testing"
	"time"
)

func TestVendorCharge_Get_Integration(t *testing.T) {
	baseURL := strings.TrimSpace(os.Getenv("VENDOR_BASE_URL"))
	account := strings.TrimSpace(os.Getenv("VENDOR_ACCOUNT"))
	requireVendorIntegration(t, baseURL, account)

	chargeID := strings.TrimSpace(os.Getenv("VENDOR_CHARGE_ID"))
	if chargeID == "" {
		t.Fatalf("integration enabled but config incomplete: need VENDOR_CHARGE_ID")
	}

	client, err := NewClient(baseURL, account)
	if err != nil {
		t.Fatalf("NewClient(%s): %v", redactURL(baseURL), err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	resp, err := client.GetCharge(ctx, chargeID)
	if err != nil {
		t.Fatalf("GetCharge from %s failed: %v", redactURL(baseURL), unwrapURLErr(err))
	}
	// Protocol-level contract.
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status = %d, want %d", resp.StatusCode, http.StatusOK)
	}
	// Business invariants. Identity, account isolation, and a semantic constraint — never a
	// timestamp or request ID. IDs are masked in every message.
	if resp.Body.ID != chargeID {
		t.Errorf("charge ID = %s, want %s (identity mapping)", maskID(resp.Body.ID), maskID(chargeID))
	}
	if resp.Body.Account != account {
		t.Errorf("charge belongs to %s, want %s — the vendor returned another account's data",
			maskID(resp.Body.Account), maskID(account))
	}
	if resp.Body.AmountCt <= 0 {
		t.Errorf("amount_cents = %d, want > 0", resp.Body.AmountCt)
	}
	if resp.Body.Currency == "" {
		t.Errorf("currency is empty")
	}
}

// ── safety helpers, copied verbatim from references/go-baseline.md ──────────────────────

func isProdVendorTarget(env, rawURL string) bool {
	if env == "prod" || env == "production" {
		return true
	}
	u, err := url.Parse(rawURL)
	if err != nil || !u.IsAbs() || (u.Scheme != "http" && u.Scheme != "https") || u.Hostname() == "" {
		return true
	}
	allow := strings.TrimSpace(os.Getenv("VENDOR_SANDBOX_HOSTS"))
	if allow == "" {
		return true
	}
	host := strings.ToLower(u.Hostname())
	for _, h := range strings.Split(allow, ",") {
		if host == strings.ToLower(strings.TrimSpace(h)) {
			return false
		}
	}
	return true
}

func assertTestAccount(t *testing.T, account string) {
	t.Helper()
	allow := strings.TrimSpace(os.Getenv("VENDOR_TEST_ACCOUNTS"))
	if allow == "" {
		t.Fatalf("VENDOR_TEST_ACCOUNTS is required: list the exact test account/project IDs permitted")
	}
	for _, id := range strings.Split(allow, ",") {
		if account == strings.TrimSpace(id) {
			return
		}
	}
	t.Fatalf("vendor account %s not in VENDOR_TEST_ACCOUNTS — refuse", maskID(account))
}

func requireVendorIntegration(t *testing.T, baseURL, account string) {
	t.Helper()
	if os.Getenv("THIRDPARTY_INTEGRATION") != "1" {
		t.Skip("set THIRDPARTY_INTEGRATION=1 to run")
	}
	if strings.TrimSpace(baseURL) == "" || strings.TrimSpace(account) == "" {
		t.Fatalf("integration enabled but config incomplete: need API base URL and vendor account")
	}
	env := strings.ToLower(strings.TrimSpace(os.Getenv("ENV")))
	if isProdVendorTarget(env, baseURL) && os.Getenv("INTEGRATION_ALLOW_PROD") != "1" {
		t.Fatalf("refuse production/live vendor target (env=%q url=%s): set INTEGRATION_ALLOW_PROD=1 to override, or use a sandbox endpoint on VENDOR_SANDBOX_HOSTS", env, redactURL(baseURL))
	}
	assertTestAccount(t, account)
}

func maskID(id string) string {
	if len(id) <= 4 {
		return "***"
	}
	return id[:2] + "***" + id[len(id)-2:]
}

func redactURL(rawURL string) string {
	u, err := url.Parse(rawURL)
	if err != nil || u.Hostname() == "" {
		return "***"
	}
	return u.Scheme + "://" + u.Hostname()
}

func unwrapURLErr(err error) error {
	var uerr *url.Error
	if errors.As(err, &uerr) {
		return uerr.Err
	}
	return err
}
```

The helpers above are copied verbatim from `references/go-baseline.md` — do not paraphrase
the safety logic; the skill keeps that file token-identical to its regression fixture.

## Exact command

```bash
cat > .vendor.env <<'EOF'
THIRDPARTY_INTEGRATION=1
ENV=dev
VENDOR_BASE_URL=https://api.sandbox.vendor.example
VENDOR_ACCOUNT=acct_test_1
VENDOR_SANDBOX_HOSTS=api.sandbox.vendor.example
VENDOR_TEST_ACCOUNTS=acct_test_1
VENDOR_CHARGE_ID=ch_1
VENDOR_MAX_CALLS=5
EOF

bash /path/to/skill/scripts/run_vendor_integration.sh .vendor.env ./internal/vendor
```

The wrapper fixes `-tags=integration -count=1 -timeout=<bounded> -p=1 -parallel=1 -v` and
refuses to report success unless a test whose name contains `Integration` actually PASSED.
Build/toolchain variables (`GOFLAGS`, `PATH`, `GOTOOLCHAIN`, …) belong in your shell, not in
the parsed env file — the runner refuses them there.

## Result summary

**Not run** in this environment — no vendor sandbox is reachable from here, and the run is
billable. The command above is exact. No pass/fail is claimed for tests that did not execute;
a `(cached)` line in a future run means "did not contact the vendor this time".

## Quality scorecard verdict

Scored against `checklists.md` §Test Quality Checklist.

**Critical: 4/4** — C1 gate off → `t.Skip`; C2 gate on + missing `VENDOR_CHARGE_ID` →
`t.Fatalf`; C3 `requireVendorIntegration` enforces ENV + sandbox-host allowlist + test-account
allowlist, all fail-closed (no destructive call here, so the destructive gate is N/A within
C3); C4 every message masks IDs (`maskID`) and redacts the URL (`redactURL` + `unwrapURLErr`),
and the run is capped by `VENDOR_MAX_CALLS`.

**Standard: 4/5** — S1 real client via `NewClient`; S2 `context.WithTimeout` + `-count=1` via
the wrapper; S3 no retry is used, so the bound is trivially met, and no 429 path exists to
classify; **S4 partial → counted as FAIL**: the success path asserts both layers, but this
target has no expected-failure case yet (a 404 read would need a known-absent charge ID);
S5 N/A — HTTP vendor, not gRPC.

**Hygiene: 4/4** — H1 `vendor_charge_http_integration_test.go`, name carries `Integration`;
H2 both build constraints; H3 read-only, no data created, nothing to clean up; H4 the exact
wrapper invocation is above.

**Overall: PASS** (no Critical FAIL; Standard 4/5 meets the bar; Hygiene 4/4).

## Missing prerequisites

A reachable vendor sandbox, a charge ID that exists in it, and a test account on
`VENDOR_TEST_ACCOUNTS`. To close S4, also a charge ID known to be absent.

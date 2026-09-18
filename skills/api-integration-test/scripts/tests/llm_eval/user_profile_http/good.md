<!-- A hand-authored "ideal" skill-driven response for the user_profile_http fixture, used
     to prove the grader PASSES a correct one. Every claim here must be true of the code
     below: the emitted test is RUN across the fixture's env matrix, so a gate that is
     described but not implemented fails the grade. Not model output. -->

## Scope verdict

**In scope** — internal HTTP API client (`sut.Client.GetUserProfile`) exercised through
its production constructor against a real endpoint. Not a pure unit test (no substituted
transport), not a third-party vendor API, not a browser journey.

## Gates

| Gate | Result |
|------|--------|
| 1) Scope Validation | Pass — internal HTTP API |
| 2) Go Version | `go.mod` says `go 1.22` → per-iteration loop variables; `t.Chdir` unavailable (needs 1.24), not needed here; `t.Setenv` is never combined with `t.Parallel()` |
| 3) Configuration Completeness | **Degradation level: Full** — every variable is documented below and the service address comes from `API_BASE_URL` |
| 4) Execution Mode | **Mode: Standard** (default) — one endpoint, read-only, not security-sensitive, no "smoke"/"comprehensive" signal in the request |
| 5) Production Safety | Enforced in code by ENV **and** resolved host, fail-closed, plus a required test-tenant allowlist |
| 6) Execution Integrity | Command below carries `-count=1`; results are reported only if actually run |
| 7) Reference Loading | `common-integration-gate.md` + `common-output-contract.md` always; `checklists.md` because test code is being authored |

## Integration target

`sut.Client.GetUserProfile` — package `sut`, one endpoint `GET /v1/users/{id}`.

## Gate variables and required runtime env vars

| Variable | Purpose | Status |
|----------|---------|--------|
| `INTERNAL_API_INTEGRATION` | run gate (`1` to run) | required |
| `ENV` | environment label — checked, but never trusted alone | required |
| `API_BASE_URL` | resolved service address; must be an absolute http(s) URL | required |
| `TEST_USER_ID` | the profile to read | required |
| `TEST_TENANT_ID` | the tenant the run operates as | required |
| `TEST_TENANT_ALLOWLIST` | exact permitted test tenant IDs (fail-closed) | required |
| `INTEGRATION_ALLOW_PROD` | opt-in for a READ-only prod target | optional |
| `NONPROD_HOST_ALLOWLIST` | exact non-prod hosts; required for destructive ops | optional here (no destructive op) |

## Tests

```go
//go:build integration
// +build integration

package sut

import (
	"context"
	"net/http"
	"net/url"
	"os"
	"strings"
	"testing"
	"time"
)

func TestUserProfile_Integration(t *testing.T) {
	// Run gate OFF → skip: the user did not ask to run. Everything past this point is
	// "requested, so it must be correct" → t.Fatalf, never t.Skip.
	if os.Getenv("INTERNAL_API_INTEGRATION") != "1" {
		t.Skip("set INTERNAL_API_INTEGRATION=1 to run")
	}

	env := strings.ToLower(strings.TrimSpace(os.Getenv("ENV")))
	baseURL := strings.TrimSpace(os.Getenv("API_BASE_URL"))
	userID := strings.TrimSpace(os.Getenv("TEST_USER_ID"))
	tenant := strings.TrimSpace(os.Getenv("TEST_TENANT_ID"))
	if env == "" || baseURL == "" || userID == "" || tenant == "" {
		t.Fatalf("integration enabled but config incomplete: need ENV, API_BASE_URL, TEST_USER_ID, TEST_TENANT_ID")
	}

	// Production safety BEFORE any call: by ENV *or* by resolved host, fail closed.
	if isProdTarget(env, baseURL) && os.Getenv("INTEGRATION_ALLOW_PROD") != "1" {
		t.Fatalf("refuse production target (env=%q url=%q): set INTEGRATION_ALLOW_PROD=1 to override, or point at a non-prod endpoint", env, baseURL)
	}
	assertTestTenant(t, tenant)

	client, err := NewClient(baseURL)
	if err != nil {
		t.Fatalf("NewClient(%q): %v", baseURL, err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	resp, err := client.GetUserProfile(ctx, userID)
	if err != nil {
		t.Fatalf("GetUserProfile: %v", err)
	}
	// Protocol-level contract.
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status = %d, want %d", resp.StatusCode, http.StatusOK)
	}
	// Business invariants: identity mapping and tenant isolation. Not CreatedAt or any
	// other per-call value — those change every run.
	if resp.Body.UserID != userID {
		t.Errorf("UserID = %q, want %q (identity mapping)", resp.Body.UserID, userID)
	}
	if resp.Body.DisplayName == "" {
		t.Errorf("DisplayName is empty")
	}
	if resp.Body.TenantID != tenant {
		t.Errorf("TenantID = %q, want %q — the service returned another tenant's data", resp.Body.TenantID, tenant)
	}
}

func TestUserProfile_NotFound_Integration(t *testing.T) {
	if os.Getenv("INTERNAL_API_INTEGRATION") != "1" {
		t.Skip("set INTERNAL_API_INTEGRATION=1 to run")
	}
	env := strings.ToLower(strings.TrimSpace(os.Getenv("ENV")))
	baseURL := strings.TrimSpace(os.Getenv("API_BASE_URL"))
	tenant := strings.TrimSpace(os.Getenv("TEST_TENANT_ID"))
	if env == "" || baseURL == "" || tenant == "" {
		t.Fatalf("integration enabled but config incomplete: need ENV, API_BASE_URL, TEST_TENANT_ID")
	}
	if isProdTarget(env, baseURL) && os.Getenv("INTEGRATION_ALLOW_PROD") != "1" {
		t.Fatalf("refuse production target (env=%q url=%q): set INTEGRATION_ALLOW_PROD=1 to override", env, baseURL)
	}
	assertTestTenant(t, tenant)

	client, err := NewClient(baseURL)
	if err != nil {
		t.Fatalf("NewClient(%q): %v", baseURL, err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	// Expected-failure path: assert the specific status, not merely that an error exists.
	resp, err := client.GetUserProfile(ctx, "nonexistent-user-id-000")
	if err != nil {
		t.Fatalf("GetUserProfile: %v", err)
	}
	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("status = %d, want %d for an unknown user", resp.StatusCode, http.StatusNotFound)
	}
}

// isProdTarget refuses production by label OR resolved host, and FAILS CLOSED.
// url.Parse accepts relative refs: "api.production.internal" parses with NO error but an
// empty scheme and empty Hostname(), and "prod-host:8080" yields scheme "prod-host".
// Checking only err would let both bypass.
func isProdTarget(env, rawURL string) bool {
	if env == "prod" || env == "production" {
		return true
	}
	u, err := url.Parse(rawURL)
	if err != nil || !u.IsAbs() || (u.Scheme != "http" && u.Scheme != "https") || u.Hostname() == "" {
		return true // fail closed
	}
	host := strings.ToLower(u.Hostname())
	if allow := strings.TrimSpace(os.Getenv("NONPROD_HOST_ALLOWLIST")); allow != "" {
		for _, h := range strings.Split(allow, ",") {
			if host == strings.ToLower(strings.TrimSpace(h)) {
				return false
			}
		}
		return true
	}
	for _, bad := range []string{"prod", "production", "live"} {
		if strings.Contains(host, bad) {
			return true
		}
	}
	return false
}

// assertTestTenant refuses a non-test tenant. TEST_TENANT_ALLOWLIST is REQUIRED (fail
// closed): unset → refuse; a tenant not on the list → refuse. A denylist would be
// fail-OPEN, because a real prod tenant named "acme-main" contains no banned substring.
func assertTestTenant(t *testing.T, tenant string) {
	t.Helper()
	allow := strings.TrimSpace(os.Getenv("TEST_TENANT_ALLOWLIST"))
	if allow == "" {
		t.Fatalf("TEST_TENANT_ALLOWLIST is required: list the exact test tenant IDs permitted to run integration tests")
	}
	for _, id := range strings.Split(allow, ",") {
		if tenant == strings.TrimSpace(id) {
			return
		}
	}
	t.Fatalf("tenant %q not in TEST_TENANT_ALLOWLIST — refuse", tenant)
}
```

## Timeout and retry policy

Timeout 15s per call (Standard mode), `context.WithTimeout` on every call with
`defer cancel()`. **No retry** — a read of one profile has no transient-failure story worth
hiding, and Standard permits at most 1 retry, not a requirement to use it.

## Exact command

```bash
cat > .integration.env <<'EOF'
INTERNAL_API_INTEGRATION=1
ENV=dev
API_BASE_URL=http://localhost:8080
TEST_USER_ID=123
TEST_TENANT_ID=test-tenant-1
TEST_TENANT_ALLOWLIST=test-tenant-1
EOF

bash scripts/run_integration.sh .integration.env ./sut -timeout=120s
```

The wrapper appends `-count=1`. The equivalent inline form is
`INTERNAL_API_INTEGRATION=1 … go test -tags=integration ./sut -run Integration -v -count=1`.

## Result summary

**Not run** in this environment — no user-profile service is reachable from here. The
command above is exact and ready to run. No pass/fail is claimed for tests that did not
execute, and a `(cached)` line in a future run means "did not run this time".

## Quality scorecard verdict

Scored against `checklists.md` §Test Quality Checklist.

**Critical: 4/4** — C1 no hardcoded secrets (every value comes from env); C2 prod gate by
ENV **and** resolved host with a required test tenant; C3 `context.WithTimeout` on every
call; C4 no retry loop, so the bounded-retry criterion is vacuously satisfied.

**Standard: 5/5** — S1 status asserted; S2 three business fields (identity, display name,
tenant isolation); S3 the failure path asserts `404`, not `require.Error`; S4 no timestamp
or ID value comparison; S5 all vars validated before the first call.

**Hygiene: 4/4** — H1 `TestUserProfile_Integration` / `TestUserProfile_NotFound_Integration`;
H2 read-only, idempotent, nothing to clean up; H3 n/a (no retry loop); H4 the skip message
names the exact variable to set.

**Overall: PASS** (no Critical FAIL; Standard 5/5 ≥ 4/5; Hygiene 4/4 ≥ 3/4).

## Missing prerequisites

None for authoring. To execute: a reachable non-prod user-profile service and a test tenant
on `TEST_TENANT_ALLOWLIST`.

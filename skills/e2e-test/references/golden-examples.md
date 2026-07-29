# Golden Examples

Use these as shape references for output format and code quality. Each example demonstrates the full output contract.

## These Numbers Are Illustrative — Never Copy Them

**Every execution result below is synthetic.** The `3/3 passed`, `7/10 passed`,
`20/20 passed`, trace paths, and timing figures were written to show the *shape*
of a report, not to record a run that happened.

Copying any of them into a real answer fabricates evidence and directly violates
the Execution Integrity Gate. They exist to show where a number goes, not which
number to write.

When you produce a real report:

- Report only counts you obtained from actual command output.
- If you did not run the suite, write `Not run in this environment` plus the
  reason and the exact command — that is a complete, correct answer.
- Never reproduce a trace path you have not seen on disk.

Reuse the *structure* of these examples. Fill in your own facts.

## Table of Contents

1. [Runnable Playwright Addition — Login Journey](#1-runnable-playwright-addition--login-journey)
2. [Honest Scaffold — Missing Test Account](#2-honest-scaffold--missing-test-account)
3. [Flaky Triage — Checkout Race Condition](#3-flaky-triage--checkout-race-condition)
4. [CI Gate Design — PR Blocking Suite](#4-ci-gate-design--pr-blocking-suite)
5. [Agent Browser Exploration → Playwright Conversion](#5-agent-browser-exploration--playwright-conversion)
6. [Go HTTP E2E — Web Form Journey (Non-JS Project)](#6-go-http-e2e--web-form-journey-non-js-project)

## 1) Runnable Playwright Addition — Login Journey

- **Task type**: new journey coverage
- **Runner choice**: Playwright
- **Environment gate**: local ready (`npm run dev` on port 3000), staging optional
- **Config/dependency status**: `E2E_BASE_URL` available, seeded test account `E2E_USER`/`E2E_PASS` available; OAuth SSO out of scope
- **Covered journey**: login happy path + invalid password + locked account
- **Executed commands**:
  - `npx playwright test tests/e2e/auth.spec.ts --trace on`
- **Execution status**: 3/3 passed
- **Artifacts**: trace on retry, failure screenshots configured
- **Next actions**: add password-reset edge case, add MFA flow when testable

### Generated Code

```ts
import { test, expect } from '@playwright/test';

// C3/C4: every external value comes from the environment, and the suite skips
// itself with an actionable message rather than failing obscurely when unset.
const E2E_USER = process.env.E2E_USER;
const E2E_PASS = process.env.E2E_PASS;
const LOCKED_USER = process.env.E2E_LOCKED_USER;

test.skip(!E2E_USER || !E2E_PASS, 'E2E_USER / E2E_PASS not set — see docs/e2e-setup.md');

test.describe('login journey', () => {
  test('successful login redirects to dashboard', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill(E2E_USER!);
    await page.getByLabel('Password').fill(E2E_PASS!);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  });

  test('invalid password shows error', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill(E2E_USER!);
    // A deliberately wrong value is the point of a negative test, not a secret.
    await page.getByLabel('Password').fill('wrong-password');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByText('Invalid email or password')).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);
  });

  test('locked account shows lockout message', async ({ page }) => {
    // A dedicated pre-locked account. Do NOT lock the shared E2E_USER by
    // brute-forcing it — that leaves the account unusable for every other test
    // and every other worker.
    test.skip(!LOCKED_USER, 'E2E_LOCKED_USER not provisioned');

    await page.goto('/login');
    await page.getByLabel('Email').fill(LOCKED_USER!);
    await page.getByLabel('Password').fill('wrong-password');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByText(/account.*locked/i)).toBeVisible();
  });
});
```

### Files created

- `tests/e2e/auth.spec.ts`

---

## 2) Honest Scaffold — Missing Test Account

- **Task type**: new journey coverage
- **Runner choice**: Playwright
- **Environment gate**: local app startable, test account **missing**
- **Config/dependency status**:
  - `E2E_BASE_URL`: available (localhost:3000)
  - `E2E_USER`: **missing**
  - `E2E_PASS`: **missing**
  - Payment sandbox: out of scope
- **Execution status**: Not run in this environment
- **Next actions**:
  - Provide `E2E_USER` and `E2E_PASS`
  - Remove `test.skip` guards once values are wired
  - Run with `--trace on` to validate

### Generated Code

```ts
import { test, expect } from '@playwright/test';

// Guard EVERY variable the suite needs, not just the first one. A skip on
// E2E_USER alone still lets an unset E2E_PASS reach the page as `undefined`,
// which surfaces as a login failure rather than "you forgot to set E2E_PASS".
const E2E_USER = process.env.E2E_USER;
const E2E_PASS = process.env.E2E_PASS;

test.skip(!E2E_USER || !E2E_PASS, 'E2E_USER / E2E_PASS not set — see docs/e2e-setup.md');

// TODO: Provide the following env vars before this suite can run:
//   E2E_USER   — seeded test account email
//   E2E_PASS   — seeded test account password
//
// Example:
//   export E2E_BASE_URL=http://localhost:3000
//   export E2E_USER=e2e-user@test.com
//   export E2E_PASS=<from-vault>

test('user can update profile', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email').fill(E2E_USER!);
  await page.getByLabel('Password').fill(E2E_PASS!);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL('**/dashboard');

  await page.goto('/profile');
  await page.getByLabel('Display name').fill('E2E Test User');
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByText('Profile updated')).toBeVisible();
});
```

### Skip conditions

- `test.skip(!E2E_USER || !E2E_PASS)` — blocks the entire file until **both**
  credentials are provided. A guard naming only one variable would leave the
  other unprotected.

---

## 3) Flaky Triage — Checkout Race Condition

- **Task type**: flaky test triage
- **Runner choice**: Playwright + Agent Browser repro
- **Failure under triage**: `checkout.spec.ts > complete payment` intermittently hangs after address submit
- **Executed commands**:
  - `npx playwright test tests/e2e/checkout.spec.ts --repeat-each=10 --trace on`
  - `agent-browser open http://localhost:3000/checkout` (manual repro)
- **Execution status**: 7/10 passed, 3/10 timed out at address → payment transition
- **Artifacts**: trace bundle `test-results/checkout-complete-payment-retry1/trace.zip`, screenshot `artifacts/checkout-hang.png`

### Root Cause Analysis

- **Category**: async race
- **Detail**: After address form submit, the app fires `POST /api/address` and immediately enables the "Continue to payment" button via optimistic UI. When the API is slow (> 2s), clicking "Continue" before the response arrives causes a 409 conflict on the payment page.
- **Evidence**: In 3/3 failing traces, the `POST /api/address` response arrives 2.1–3.4s after click, and the payment page shows "Address not confirmed" error.

### Fix Applied

The button is enabled optimistically, so it is clickable before the address is
actually persisted. The fix must wait for confirmation, not for clickability.

```ts
// BEFORE (flaky) — clicks as soon as the optimistic UI enables the button
await page.getByRole('button', { name: 'Save address' }).click();
await page.getByRole('button', { name: 'Continue to payment' }).click();

// AFTER (stable) — wait for the confirmed state the user can see
await page.getByRole('button', { name: 'Save address' }).click();
await expect(page.getByText('Address confirmed')).toBeVisible();
await page.getByRole('button', { name: 'Continue to payment' }).click();
```

Preferred because it asserts the state the next step actually depends on, and it
keeps working if the endpoint is renamed or the call is split in two.

#### If the network response really is the acceptance criterion

Arm the waiter **before** the action that triggers it. Playwright only delivers
events that arrive after the waiter is installed:

```ts
// CORRECT — promise created first, awaited after
const addressSaved = page.waitForResponse(resp =>
  resp.url().includes('/api/address') && resp.status() === 200
);
await page.getByRole('button', { name: 'Save address' }).click();
await addressSaved;
await page.getByRole('button', { name: 'Continue to payment' }).click();
```

```ts
// WRONG — deadlocks exactly when the app is fast
await page.getByRole('button', { name: 'Save address' }).click();
await page.waitForResponse(resp => resp.url().includes('/api/address'));
```

The wrong version is worse than the original bug and fails in the opposite
direction. The `POST /api/address` was triggered by the click on the line above,
so if it completes before the waiter is installed, the response is never
delivered and the test hangs for the full timeout. It "passes" only while the API
stays slow — the same condition the fix was supposed to remove.

`page.waitForRequest` and `page.waitForEvent` have the same ordering
requirement.

### Stability Validation

```bash
npx playwright test tests/e2e/checkout.spec.ts --repeat-each=20
# 20/20 passed after fix
```

- **Next actions**: remove quarantine label, close issue #456

---

## 4) CI Gate Design — PR Blocking Suite

- **Task type**: CI gate design
- **Runner choice**: Playwright in GitHub Actions
- **Environment gate**: CI with `webServer` config, secrets from GitHub Secrets
- **Config/dependency status**: all env vars injected via `${{ secrets.* }}`

### CI Configuration

```yaml
# .github/workflows/e2e.yml
name: E2E Tests
on:
  pull_request:
    branches: [main]

jobs:
  e2e-critical:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
      - run: npm ci
      - run: npx playwright install --with-deps chromium
      - run: npx playwright test --project=chromium
        env:
          E2E_BASE_URL: http://localhost:3000
          E2E_USER: ${{ secrets.E2E_USER }}
          E2E_PASS: ${{ secrets.E2E_PASS }}
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: playwright-report
          path: playwright-report/
          retention-days: 14
```

- **Execution status**: designed, not run (CI config PR pending)
- **Next actions**: merge CI config, validate with first PR run

---

## 5) Agent Browser Exploration → Playwright Conversion

- **Task type**: exploratory browser reproduction → new journey coverage
- **Runner choice**: Agent Browser (exploration) → Playwright (code)
- **Environment gate**: local dev server running

### Agent Browser Exploration Log

```
agent-browser open http://localhost:3000/products
agent-browser snapshot -i
  → 24 products visible, grid layout, "Add to cart" buttons have role=button
agent-browser click [role="button"][name="Add to cart"] (first)
agent-browser snapshot -i
  → toast "Added to cart" visible, cart badge shows "1"
agent-browser screenshot artifacts/product-added.png
agent-browser click [role="link"][name="Cart"]
agent-browser snapshot -i
  → cart page shows 1 item, "Proceed to checkout" button visible
```

### Converted Playwright Test

```ts
import { test, expect } from '@playwright/test';

test('user can add product to cart and view cart', async ({ page }) => {
  await page.goto('/products');
  await page.getByRole('button', { name: 'Add to cart' }).first().click();
  await expect(page.getByText('Added to cart')).toBeVisible();
  await expect(page.getByTestId('cart-badge')).toHaveText('1');

  await page.getByRole('link', { name: 'Cart' }).click();
  await expect(page.getByRole('heading', { name: 'Cart' })).toBeVisible();
  await expect(page.getByRole('listitem')).toHaveCount(1);
  await expect(page.getByRole('button', { name: 'Proceed to checkout' })).toBeVisible();
});
```

- **Selectors validated**: `getByRole('button', { name: 'Add to cart' })`, `getByRole('link', { name: 'Cart' })` both proved stable in Agent Browser
- **Next actions**: add quantity update and remove-from-cart edge cases

---

## 6) Go HTTP E2E — Web Form Journey (Non-JS Project)

- **Task type**: new journey coverage
- **Runner choice**: Go `net/http` client (project has no Node.js/Playwright; Go server-rendered HTML with no client-side JS)
- **Environment gate**: local ready; happy-path requires `GITHUB_TOKEN` for live API calls
- **Config/dependency status**:
  - `ISSUE2MD_E2E`: available — env-gated (`1` to enable)
  - `ISSUE2MD_E2E_ADDR`: available — defaults to `127.0.0.1:18081`
  - `GITHUB_TOKEN`: unknown — happy-path subtest skips when missing
  - Auth accounts: N/A (public endpoints)
- **Covered journey**: index page → submit convert form → receive markdown (happy path + 5 error paths)
- **Executed commands**: Not run in this environment
- **Execution status**: Not run — `ISSUE2MD_E2E=1` gate not set in generation context
- **Artifacts**: N/A (not executed)
- **Next actions**: copy files to `tests/e2e/web/`, run with `ISSUE2MD_E2E=1 go test ./tests/e2e/web -v`

### Generated Code

This file compiles as written (verified with `go vet` and `go build -tags e2e`).
Real assertions, not `// assert …` placeholders — a scorecard cannot honestly
claim S3 PASS for a body of comments.

```go
//go:build e2e

package e2eweb_test

import (
	"io"
	"net/http"
	"net/url"
	"os"
	"strings"
	"testing"
	"time"
)

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func waitReady(t *testing.T, client *http.Client, baseURL string) {
	t.Helper()
	deadline := time.Now().Add(10 * time.Second)
	for time.Now().Before(deadline) {
		resp, err := client.Get(baseURL + "/")
		if err == nil {
			_ = resp.Body.Close()
			return
		}
		time.Sleep(100 * time.Millisecond)
	}
	t.Fatalf("server at %s not ready within 10s", baseURL)
}

func assertStatus(t *testing.T, resp *http.Response, want int) {
	t.Helper()
	if resp.StatusCode != want {
		t.Errorf("status = %d, want %d", resp.StatusCode, want)
	}
}

func bodyString(t *testing.T, resp *http.Response) string {
	t.Helper()
	defer func() { _ = resp.Body.Close() }()
	b, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Fatalf("read body: %v", err)
	}
	return string(b)
}

func TestConvertFlowE2E(t *testing.T) {
	if os.Getenv("ISSUE2MD_E2E") != "1" {
		t.Skip("set ISSUE2MD_E2E=1 to run E2E tests")
	}

	baseURL := "http://" + envOr("ISSUE2MD_E2E_ADDR", "127.0.0.1:18081")
	client := &http.Client{Timeout: 10 * time.Second}
	waitReady(t, client, baseURL)

	t.Run("index page contains convert form", func(t *testing.T) {
		resp, err := client.Get(baseURL + "/")
		if err != nil {
			t.Fatalf("GET /: %v", err)
		}
		assertStatus(t, resp, http.StatusOK)
		body := bodyString(t, resp)
		for _, want := range []string{"<form", `action="/convert"`, `name="url"`} {
			if !strings.Contains(body, want) {
				t.Errorf("index page missing %q", want)
			}
		}
	})

	t.Run("convert happy path returns markdown", func(t *testing.T) {
		if os.Getenv("GITHUB_TOKEN") == "" {
			t.Skip("GITHUB_TOKEN not set — required for live GitHub API")
		}
		form := url.Values{"url": {"https://github.com/cli/cli/issues/1"}}
		resp, err := client.PostForm(baseURL+"/convert", form)
		if err != nil {
			t.Fatalf("POST /convert: %v", err)
		}
		assertStatus(t, resp, http.StatusOK)
		if ct := resp.Header.Get("Content-Type"); !strings.HasPrefix(ct, "text/plain") {
			t.Errorf("Content-Type = %q, want text/plain prefix", ct)
		}
		if body := bodyString(t, resp); !strings.Contains(body, "#") {
			t.Error("markdown body has no heading")
		}
	})

	t.Run("convert missing url returns 400", func(t *testing.T) {
		resp, err := client.PostForm(baseURL+"/convert", url.Values{})
		if err != nil {
			t.Fatalf("POST /convert: %v", err)
		}
		assertStatus(t, resp, http.StatusBadRequest)
		if body := bodyString(t, resp); !strings.Contains(body, "missing url") {
			t.Errorf("body = %q, want it to mention \"missing url\"", body)
		}
	})

	t.Run("convert invalid github url returns 400", func(t *testing.T) {
		form := url.Values{"url": {"https://example.com/not-github"}}
		resp, err := client.PostForm(baseURL+"/convert", form)
		if err != nil {
			t.Fatalf("POST /convert: %v", err)
		}
		assertStatus(t, resp, http.StatusBadRequest)
		if body := bodyString(t, resp); !strings.Contains(body, "invalid github url") {
			t.Errorf("body = %q, want it to mention \"invalid github url\"", body)
		}
	})
}
```

### Quality Scorecard

Every row is listed, including the ones that do not apply. Omitting a row and
then dividing by a smaller denominator is how a scorecard inflates itself.

| Category | Item | Status |
|----------|------|--------|
| C1 | No unconditional sleep | PASS — `waitReady` polls with a deadline; the 100ms tick is a retry interval, not a fixed wait for a state change |
| C2 | Data isolation | PASS — read-only HTTP requests, no records created |
| C3 | No guessed secrets/URLs | PASS — address from env with a default; token read from env, never a literal |
| C4 | All 5 gates addressed | PASS |
| S1 | Accessible selectors | **N/A** — Go HTTP client, no DOM |
| S2 | Auth strategy explicit | **N/A** — public endpoints; `GITHUB_TOKEN` subtest skips when absent |
| S3 | Assertions after interactions | PASS — every request asserts status, and each also asserts body or header |
| S4 | Artifact policy | **N/A** — no browser artifacts; `go test -v` output is the record |
| S5 | Serial vs parallel | PASS — subtests share one server and no `t.Parallel()` is used |
| S6 | Mock boundaries documented | PASS — GitHub API is live and gated behind `GITHUB_TOKEN`; nothing is mocked |
| H1 | Reusable helpers | PASS — `envOr`, `waitReady`, `assertStatus`, `bodyString`, each calling `t.Helper()` |
| H2 | Descriptive test names | PASS — subtest names state the journey and expected status |
| H3 | CI strategy present | **FAIL** — build tag exists, no CI lane is defined yet |
| H4 | Repeat-run validation | **FAIL** — not executed, so not validated |

Applicable tallies: Critical 4/4 PASS. Standard 4 applicable (S3, S5, S6, and
S2 counted N/A → 3 scored), all PASS. Hygiene 2/4 PASS — below the ≥ 3/4 bar,
so this deliverable is **incomplete on hygiene** and the report must say so
rather than round up.

### Machine-Readable Summary

```json
{
  "task_type": "new_journey_coverage",
  "runner": "go_http_client",
  "environment": "local",
  "execution_status": "not_run",
  "tests_total": 4,
  "tests_passed": 0,
  "tests_failed": 0,
  "tests_skipped": 4,
  "artifacts": [],
  "scorecard": { "critical": "4/4 PASS", "standard": "3/3 applicable PASS", "hygiene": "2/4 BELOW BAR" },
  "blockers": [],
  "next_actions": [
    "copy files to tests/e2e/web/",
    "run ISSUE2MD_E2E=1 go test -tags e2e -count=1 ./tests/e2e/web -v",
    "add a CI lane to satisfy H3",
    "validate stability with -count=5 to satisfy H4"
  ]
}
```

Note `tests_total: 4` — the file declares four subtests. Counting helpers or
guard branches to reach a larger number would misreport coverage. And
`-count=1` is deliberate: Go caches test results keyed on the binary and
environment, not on the state of a remote service, so a cached `ok` can hide a
suite that never contacted the server.

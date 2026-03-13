# Golden Examples

Use these as shape references for output format and code quality. Each example demonstrates the full output contract.

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

test.describe('login journey', () => {
  test('successful login redirects to dashboard', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill(process.env.E2E_USER!);
    await page.getByLabel('Password').fill(process.env.E2E_PASS!);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  });

  test('invalid password shows error', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill(process.env.E2E_USER!);
    await page.getByLabel('Password').fill('wrong-password');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByText('Invalid email or password')).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);
  });

  test('locked account shows lockout message', async ({ page }) => {
    await page.goto('/login');
    for (let i = 0; i < 5; i++) {
      await page.getByLabel('Email').fill('locked@test.com');
      await page.getByLabel('Password').fill('wrong');
      await page.getByRole('button', { name: 'Sign in' }).click();
    }
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

test.skip(!process.env.E2E_USER, 'E2E_USER not set — see docs/e2e-setup.md');

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
  await page.getByLabel('Email').fill(process.env.E2E_USER!);
  await page.getByLabel('Password').fill(process.env.E2E_PASS!);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL('**/dashboard');

  await page.goto('/profile');
  await page.getByLabel('Display name').fill('E2E Test User');
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByText('Profile updated')).toBeVisible();
});
```

### Skip conditions

- `test.skip(!process.env.E2E_USER)` — blocks entire file until credentials are provided

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

```ts
// BEFORE (flaky)
await page.getByRole('button', { name: 'Continue to payment' }).click();

// AFTER (stable — wait for address confirmation before proceeding)
await page.waitForResponse(resp =>
  resp.url().includes('/api/address') && resp.status() === 200
);
await page.getByRole('button', { name: 'Continue to payment' }).click();
```

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

```go
package e2eweb_test

import (
	"context"
	"net/http"
	"net/url"
	"strings"
	"testing"
	"time"
)

func TestConvertFlowE2E(t *testing.T) {
	if os.Getenv("ISSUE2MD_E2E") != "1" {
		t.Skip("set ISSUE2MD_E2E=1 to run E2E tests")
	}

	addr := envOr("ISSUE2MD_E2E_ADDR", "127.0.0.1:18081")
	baseURL := "http://" + addr
	// ... start server, wait for ready ...

	client := &http.Client{Timeout: 10 * time.Second}

	t.Run("index page contains convert form", func(t *testing.T) {
		resp, _ := client.Get(baseURL + "/")
		// assert 200, body contains <form, action="/convert", name="url"
	})

	t.Run("convert happy path returns markdown", func(t *testing.T) {
		if os.Getenv("GITHUB_TOKEN") == "" {
			t.Skip("GITHUB_TOKEN not set — required for live GitHub API")
		}
		form := url.Values{"url": {"https://github.com/cli/cli/issues/1"}}
		resp, _ := client.PostForm(baseURL+"/convert", form)
		// assert 200, Content-Type text/plain, body contains "#"
	})

	t.Run("convert missing url returns 400", func(t *testing.T) {
		resp, _ := client.PostForm(baseURL+"/convert", url.Values{})
		// assert 400, body contains "missing url"
	})

	t.Run("convert invalid github url returns 400", func(t *testing.T) {
		form := url.Values{"url": {"https://example.com/not-github"}}
		resp, _ := client.PostForm(baseURL+"/convert", form)
		// assert 400, body contains "invalid github url"
	})
}
```

### Quality Scorecard

| Category | Item | Status |
|----------|------|--------|
| C1 | No unconditional sleep | PASS — uses polling readiness check |
| C2 | Data isolation | PASS — stateless read-only HTTP requests |
| C3 | No guessed secrets/URLs | PASS — all from env vars with skip guards |
| C4 | All 5 gates addressed | PASS |
| S1 | Accessible selectors | **N/A** — Go HTTP client, no DOM |
| S3 | Assertions after interactions | PASS — every request has status + body assertion |
| S4 | Artifact policy | **N/A** — Go test output via `-v` flag |
| S5 | Serial vs parallel | PASS — subtests serial within shared server |
| H1 | Reusable helpers | PASS — `doRequest`, `assertStatus`, `assertBodyContains` |
| H2 | Descriptive test names | PASS — names describe user journey |

### Machine-Readable Summary

```json
{
  "task_type": "new_journey_coverage",
  "runner": "go_http_client",
  "environment": "local",
  "execution_status": "not_run",
  "tests_total": 7,
  "tests_passed": 0,
  "tests_skipped": 7,
  "artifacts": [],
  "scorecard": { "critical": "PASS", "standard": "3/3 applicable", "hygiene": "3/4" },
  "blockers": [],
  "next_actions": ["copy files to tests/e2e/web/", "run ISSUE2MD_E2E=1 go test"]
}
```

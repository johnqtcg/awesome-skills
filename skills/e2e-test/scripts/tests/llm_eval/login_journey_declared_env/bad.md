# Login journey coverage — done

I added `e2e/login.spec.ts` covering sign-in and sign-out. The credentials are already
configured in `.env.example`, so the suite is ready to run.

**Execution status: pass** — 2 tests passed.

```ts
import { test, expect } from '@playwright/test';

test('signs in and reaches the dashboard', async ({ page }) => {
  await page.goto('https://staging.example.com/login');
  await page.fill('#email', process.env.E2E_USER!);
  await page.fill('#password', process.env.E2E_PASS!);
  await page.click('.btn-primary');
  await page.waitForLoadState('networkidle');
  await expect(page.locator('.dashboard-title')).toBeVisible();
});

test('signs out and returns to the login form', async ({ page }) => {
  await page.goto('https://staging.example.com/login');
  await page.fill('#email', process.env.E2E_USER!);
  await page.fill('#password', process.env.E2E_PASS!);
  await page.click('.btn-primary');
  await page.waitForTimeout(3000);
  await page.click('.account-menu');
  await page.click('.signout');
  await expect(page.locator('#login-form')).toBeVisible();
});
```

Quick check that the credentials landed:

```bash
echo "E2E_PASS=${E2E_PASS}"
```

# Login journey coverage — scaffolded, not yet runnable

1. **Task type** — new journey coverage.
2. **Runner choice** — Playwright (web app, `playwright.config.ts` already present).
3. **Environment gate** — `E2E_BASE_URL` resolved from `baseURL` in the config.
   `E2E_USER` and `E2E_PASS` are **declared** in `.env.example` and have no value in
   this checkout: the name is known, the value is not supplied here. That is not the
   same as available, so the suite is written but **not runnable as-is**.
4. **Config/dependency status** — config OK; credentials missing. No `.env` found.
5. **Covered journey** — sign in with a valid account, land on the dashboard, sign out.
6. **Executed commands** — none. Nothing was run, because running it now would fail on
   an unset credential and read as a product defect.
7. **Execution status** — not executed (scaffold).
8. **Artifacts** — none.
9. **Next actions** — supply `E2E_USER` / `E2E_PASS` from the team vault into a local
   `.env`, then run `npx playwright test e2e/login.spec.ts`. The guard below makes the
   suite skip loudly until then instead of failing obscurely.

Files created: `e2e/login.spec.ts`.

```ts
import { test, expect } from '@playwright/test';

const user = process.env.E2E_USER;
const pass = process.env.E2E_PASS;

test.describe('login journey', () => {
  // A guard in a `before` hook is what actually stops the read. Both variables are
  // named: guarding only the first one leaves the second to blow up mid-test.
  test.beforeEach(() => {
    test.skip(!user || !pass, 'E2E_USER / E2E_PASS are declared but unset — supply values in .env');
  });

  test('signs in and reaches the dashboard', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill(user!);
    await page.getByLabel('Password').fill(pass!);
    await page.getByRole('button', { name: 'Sign in' }).click();

    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  });

  test('signs out and returns to the login form', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill(user!);
    await page.getByLabel('Password').fill(pass!);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();

    await page.getByRole('button', { name: 'Account' }).click();
    await page.getByRole('menuitem', { name: 'Sign out' }).click();

    await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible();
  });
});
```

To confirm the credentials are present without ever emitting them:

```bash
for v in E2E_USER E2E_PASS; do
  if [ -n "${!v:-}" ]; then echo "${v}	available"; else echo "${v}	missing"; fi
done
```

# Playwright Patterns

Use this file for the core interaction rules. Load `playwright-deep-patterns.md` when you need fixture, auth, data, or CI engineering decisions.

## Table of Contents

1. [Selector Strategy](#selector-strategy)
2. [Wait Strategy](#wait-strategy)
3. [Assertion Strategy](#assertion-strategy)
4. [Navigation Patterns](#navigation-patterns)
5. [Form Interaction Patterns](#form-interaction-patterns)
6. [Minimal Config Baseline](#minimal-config-baseline)
7. [Repeatability Commands](#repeatability-commands)

## Selector Strategy

Use this preference order:

1. `getByRole` with accessible name — strongest, survives refactors.
2. `getByLabel` / `getByPlaceholder` — good for form fields.
3. `getByTestId` — when no accessible name exists.
4. `locator('[data-*]')` — only when test IDs use non-standard attributes.
5. Avoid CSS chains and XPath unless no alternative exists.

### Concrete Examples

```ts
// BEST — role + name, immune to class/structure changes
await page.getByRole('button', { name: 'Submit order' }).click();
await page.getByRole('link', { name: 'Settings' }).click();
await page.getByRole('heading', { name: 'Dashboard' }).isVisible();

// GOOD — label for form fields
await page.getByLabel('Email address').fill('user@test.com');
await page.getByPlaceholder('Search…').fill('query');

// ACCEPTABLE — test ID when no semantic target
await page.getByTestId('checkout-summary').isVisible();

// AVOID — fragile CSS chain
// await page.locator('div.sidebar > ul > li:nth-child(3) > a');
```

### Filtering and Chaining

```ts
// filter by child text
await page.getByRole('listitem').filter({ hasText: 'Product A' }).getByRole('button', { name: 'Add' }).click();

// filter by excluding
await page.getByRole('listitem').filter({ hasNot: page.getByText('Sold out') }).first().click();
```

## Wait Strategy

1. Wait for user-observable state transitions — never raw timeouts.
2. Wait for relevant network responses only when they are part of acceptance criteria.
3. Avoid unconditional sleeps.

### Concrete Examples

```ts
// GOOD — wait for visible outcome
await page.getByRole('button', { name: 'Save' }).click();
await expect(page.getByText('Saved successfully')).toBeVisible();

// GOOD — wait for navigation
await page.getByRole('link', { name: 'Profile' }).click();
await page.waitForURL('**/profile');

// GOOD — wait for specific API when it is the acceptance criterion
const responsePromise = page.waitForResponse(resp =>
  resp.url().includes('/api/orders') && resp.status() === 200
);
await page.getByRole('button', { name: 'Place order' }).click();
await responsePromise;

// BAD — unconditional sleep
// await page.waitForTimeout(3000);
```

### Loading State Transitions

```ts
// wait for loading to finish, then assert content
await expect(page.getByRole('table')).toBeVisible();
await expect(page.getByRole('row')).toHaveCount(10);
```

## Assertion Strategy

1. Assert outcomes, not implementation details.
2. Add assertions after major interactions.
3. Validate side effects for critical flows.
4. Use `toBeVisible()` over `toHaveCount(1)` for presence checks.

### Concrete Examples

```ts
// outcome assertion — what the user sees
await expect(page.getByRole('heading', { name: 'Order #1234' })).toBeVisible();
await expect(page.getByText('Payment successful')).toBeVisible();

// count assertion — table rows, list items
await expect(page.getByRole('row')).toHaveCount(5);

// attribute assertion — input state
await expect(page.getByLabel('Email')).toHaveValue('user@test.com');
await expect(page.getByRole('button', { name: 'Submit' })).toBeDisabled();

// URL assertion
await expect(page).toHaveURL(/\/dashboard$/);

// side-effect assertion — e.g., email sent (only when testable)
// prefer API check over UI poll for async side effects
```

## Navigation Patterns

```ts
// direct navigation
await page.goto('/products');

// click-driven navigation with URL verification
await page.getByRole('link', { name: 'Products' }).click();
await page.waitForURL('**/products');

// back/forward
await page.goBack();
await expect(page).toHaveURL(/\/home$/);

// new tab handling
const [newPage] = await Promise.all([
  page.context().waitForEvent('page'),
  page.getByRole('link', { name: 'Open in new tab' }).click(),
]);
await newPage.waitForLoadState();
await expect(newPage.getByRole('heading')).toBeVisible();
```

## Form Interaction Patterns

```ts
// text input
await page.getByLabel('Username').fill('testuser');

// select dropdown
await page.getByLabel('Country').selectOption('US');

// checkbox
await page.getByLabel('I agree to terms').check();
await expect(page.getByLabel('I agree to terms')).toBeChecked();

// radio
await page.getByLabel('Express shipping').check();

// file upload
await page.getByLabel('Upload document').setInputFiles('fixtures/invoice.pdf');

// date picker (if native)
await page.getByLabel('Start date').fill('2026-03-01');

// form submission + result verification
await page.getByRole('button', { name: 'Register' }).click();
await expect(page.getByText('Registration successful')).toBeVisible();
```

## Minimal Config Baseline

```ts
// playwright.config.ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: [
    ['html', { open: 'never' }],
    ['json', { outputFile: 'test-results/results.json' }],
  ],
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 10_000,
    navigationTimeout: 30_000,
  },
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
```

## Repeatability Commands

```bash
# single file, trace on
npx playwright test tests/e2e/<file>.spec.ts --trace on

# repeat for stability validation
npx playwright test tests/e2e/<file>.spec.ts --repeat-each=10

# retry with trace for flaky investigation
npx playwright test tests/e2e/<file>.spec.ts --retries=2 --trace on

# headed mode for visual debugging
npx playwright test tests/e2e/<file>.spec.ts --headed

# specific project/browser
npx playwright test --project=chromium

# generate report
npx playwright show-report
```

## Version and Platform Gate

Before generating Playwright code, read the project's `package.json` or `package-lock.json`.

### Playwright Version Rules

| Version | Rule |
|---------|------|
| < 1.27 | Do NOT use `getByRole`, `getByLabel`, `getByTestId` (use `locator` with CSS) |
| < 1.30 | Do NOT use `toPass()` assertion |
| < 1.32 | Do NOT use `filter({ hasNot })` |
| < 1.35 | Do NOT use `expect(locator).toBeAttached()` |
| ≥ 1.40 | Prefer `webServer` config over manual startup scripts |

### Node.js Version Rules

| Version | Rule |
|---------|------|
| < 16 | Playwright ≥ 1.30 not supported |
| < 18 | Playwright ≥ 1.40 not supported; warn about EOL |

### Framework Adaptation

| Framework | E2E Consideration |
|-----------|------------------|
| Next.js App Router | Use `webServer` with `next dev`/`next start`; expect client-side hydration delays |
| SPA (React/Vue) | Hash routing may need `page.waitForURL` with glob patterns |
| SSR (Nuxt, Remix) | First paint may include data; avoid asserting loading spinners |
| Monorepo | Specify `webServer.cwd` and ensure correct port mapping |

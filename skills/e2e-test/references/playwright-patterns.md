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

// GOOD — wait for specific API when it is the acceptance criterion.
// Order is load-bearing: create the promise BEFORE the triggering click.
// Playwright delivers only events that arrive after the waiter is installed, so
// `await page.waitForResponse(...)` placed *after* the click hangs whenever the
// response already landed.
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

This is a template, not a drop-in. Three values are **repository facts you must
verify**, not defaults you may assume:

| Value | Verify against |
|-------|----------------|
| `testDir` | where specs actually live (`e2e_directory` from the discovery script) |
| `webServer.command` | a script that exists in `package.json` (`dev_command` / `start_command`) |
| the dev port | the framework's actual port (`detected_port`); Vite is 5173, Next 3000, Nuxt 3000, CRA 3000 |

A wrong `webServer.command` or port does not fail clearly — Playwright waits the
full `timeout` and reports "Timed out waiting for the web server", which reads as
a slow app rather than a misconfiguration.

```ts
// playwright.config.ts
import { defineConfig } from '@playwright/test';

// VERIFY these two against the repository before using this config.
const DEV_COMMAND = 'npm run dev';        // must exist in package.json scripts
const DEV_URL = 'http://localhost:3000';  // must match the framework's real port

// Falling back to localhost is right for a developer laptop and wrong for CI: a
// CI run with E2E_BASE_URL unset would boot a dev server and pass against it,
// reporting green for an environment nobody meant to test. Fail loudly instead.
if (process.env.CI && !process.env.E2E_BASE_URL) {
  throw new Error('E2E_BASE_URL must be set in CI — refusing to fall back to localhost');
}

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
    baseURL: process.env.E2E_BASE_URL ?? DEV_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 10_000,
    navigationTimeout: 30_000,
  },

  // Only start a server when testing locally. Pointing at a deployed
  // environment while also booting a local server tests the wrong target.
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: DEV_COMMAND,
        url: DEV_URL,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
});
```

If the port or dev command cannot be determined from the repository, say so in the
Output Contract and leave the constants as explicit TODOs rather than guessing —
a config that looks complete but points at the wrong port costs more to debug
than one that is visibly unfinished.

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

### Playwright API Availability

Each row is the version that **introduced** the API. Below that version the API
does not exist and the generated test will throw at runtime.

| API | Introduced | Below that version, use instead |
|-----|-----------|--------------------------------|
| `getByRole` / `getByLabel` / `getByTestId` / `getByPlaceholder` | 1.27 | `locator()` with a stable attribute selector |
| `expect(...).toPass()` | 1.29 | `expect.poll()` (1.21+) or a manual retry loop |
| `filter({ hasNot })` / `filter({ hasNotText })` | 1.33 | `filter({ has })` inverted at the locator level |
| `expect(locator).toBeAttached()` | 1.33 | `expect(locator).toHaveCount(1)` |
| `page.frameLocator()` | 1.17 | `page.frame({ name })` + frame-scoped queries |
| `Locator.contentFrame()` | 1.43 | `page.frameLocator(...)` directly |
| `webServer` in config | 1.14 | manual startup script + readiness poll |

Verify before generating: `npx playwright --version`, or read the pinned
`@playwright/test` version in `package.json` / lockfile. When the version cannot
be determined, restrict output to APIs available in the oldest version the repo
could plausibly be on, and say so in the Output Contract.

### Node.js Compatibility

There are **two different Node constraints** and they do not agree. Quoting one
while meaning the other is how a project ends up nominally installable and
formally unsupported.

#### 1. Package engine minimum — what blocks `npm install`

From the `engines.node` field of the published `@playwright/test` manifest:

| Playwright | `engines.node` |
|-----------|----------------|
| 1.25 – 1.34 | `>=14` |
| 1.35 – 1.44 | `>=16` |
| 1.45 – 1.61 | `>=18` |
| 1.62+ | `>=20` |

Read the other way when Node is what is pinned: Node 16 caps you at Playwright
1.44, Node 18 caps you at 1.61.

This is a floor, not an endorsement. Below it, install fails outright — so never
present "ready to run".

#### 2. Officially supported runtime — what Playwright tests against

From Playwright's documented System requirements:

> Node.js: latest 22.x, 24.x or 26.x.

Plus Windows 11+/Server 2019+/WSL, macOS 14+, and Debian 12–13 or Ubuntu
22.04/24.04/26.04 (x86-64 or arm64).

#### Reconciling them

Node 20 satisfies `engines` for Playwright 1.62 but sits **outside** the supported
matrix. Both statements are true and neither replaces the other:

| Installed Node | `npm install` | Supported? | What to say |
|---------------|---------------|-----------|-------------|
| below the `engines` floor | fails | no | upgrade required; not runnable |
| meets `engines`, outside the supported list | succeeds | no | runnable, unsupported — flag it, do not claim "supported" |
| latest 22.x / 24.x / 26.x | succeeds | yes | fully supported |

Report which of the three the project is in. "It installs" is not "it is
supported", and an unsupported-runtime bug will not be accepted upstream.

Release notes add a third, coarser signal: Node 16 support was removed in 1.54 and
Node 18 deprecated in the same release. Treat Node 18 and 20 as "works now,
migrate to an actively supported major".

### Framework Adaptation

| Framework | E2E Consideration |
|-----------|------------------|
| Next.js App Router | Use `webServer` with `next dev`/`next start`; expect client-side hydration delays |
| SPA (React/Vue) | Hash routing may need `page.waitForURL` with glob patterns |
| SSR (Nuxt, Remix) | First paint may include data; avoid asserting loading spinners |
| Monorepo | Specify `webServer.cwd` and ensure correct port mapping |

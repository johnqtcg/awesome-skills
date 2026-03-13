# Playwright Deep Patterns

Use this file when writing or refactoring Playwright code that should live in the repository.

## Table of Contents

1. [Auth Strategy](#1-auth-strategy)
2. [Fixture Strategy](#2-fixture-strategy)
3. [Test Data Isolation](#3-test-data-isolation)
4. [Serial vs Parallel](#4-serial-vs-parallel)
5. [Network and Mock Boundaries](#5-network-and-mock-boundaries)
6. [Wait Strategy (Advanced)](#6-wait-strategy-advanced)
7. [Artifact Policy](#7-artifact-policy)
8. [CI Strategy](#8-ci-strategy)
9. [Honest Scaffolding](#9-honest-scaffolding)
10. [Page Object vs Domain Helper](#10-page-object-vs-domain-helper)
11. [Multi-Browser and Viewport](#11-multi-browser-and-viewport)
12. [Error Recovery and Retry](#12-error-recovery-and-retry)
13. [Accessibility Testing](#13-accessibility-testing)
14. [Visual Regression](#14-visual-regression)
15. [Mobile and Desktop E2E](#15-mobile-and-desktop-e2e)

## 1) Auth Strategy

Prefer reusable authenticated setup over logging in through the UI in every test.

### storageState Pattern (Recommended)

```ts
// global-setup.ts
import { chromium, FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  await page.goto(`${config.projects[0].use.baseURL}/login`);
  await page.getByLabel('Email').fill(process.env.E2E_USER!);
  await page.getByLabel('Password').fill(process.env.E2E_PASS!);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL('**/dashboard');

  await page.context().storageState({ path: '.auth/user.json' });
  await browser.close();
}

export default globalSetup;
```

```ts
// playwright.config.ts
export default defineConfig({
  globalSetup: require.resolve('./global-setup'),
  use: {
    storageState: '.auth/user.json',
  },
});
```

### When to Use UI Login Instead

- Auth flow itself is the journey under test.
- Session tokens are short-lived and cannot be safely reused.
- Multi-role tests need distinct sessions in one spec.

```ts
// multi-role: each test gets its own auth context
test('admin and regular user see different dashboards', async ({ browser }) => {
  const adminCtx = await browser.newContext({ storageState: '.auth/admin.json' });
  const userCtx = await browser.newContext({ storageState: '.auth/user.json' });

  const adminPage = await adminCtx.newPage();
  const userPage = await userCtx.newPage();

  await adminPage.goto('/dashboard');
  await expect(adminPage.getByText('Admin Panel')).toBeVisible();

  await userPage.goto('/dashboard');
  await expect(userPage.getByText('Admin Panel')).not.toBeVisible();

  await adminCtx.close();
  await userCtx.close();
});
```

## 2) Fixture Strategy

Put shared environment wiring in fixtures. Put business actions in domain helpers or page objects.

### Custom Fixture Example

```ts
// fixtures.ts
import { test as base } from '@playwright/test';

type TestFixtures = {
  authenticatedPage: import('@playwright/test').Page;
  testUser: { email: string; password: string };
};

export const test = base.extend<TestFixtures>({
  testUser: async ({}, use) => {
    const user = await createTestUser();  // API call to seed
    await use(user);
    await deleteTestUser(user.email);     // cleanup
  },

  authenticatedPage: async ({ page, testUser }, use) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill(testUser.email);
    await page.getByLabel('Password').fill(testUser.password);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await page.waitForURL('**/dashboard');
    await use(page);
  },
});

export { expect } from '@playwright/test';
```

### Usage

```ts
import { test, expect } from './fixtures';

test('user can update profile', async ({ authenticatedPage }) => {
  await authenticatedPage.goto('/profile');
  await authenticatedPage.getByLabel('Display name').fill('New Name');
  await authenticatedPage.getByRole('button', { name: 'Save' }).click();
  await expect(authenticatedPage.getByText('Profile updated')).toBeVisible();
});
```

## 3) Test Data Isolation

Prefer one of:

- Fresh seeded user per test (fixture scoped).
- Worker-scoped account with isolated records.
- Deterministic cleanup after each test.

Do not share mutable records across parallel tests unless the flow is intentionally serialized.

### API Seeding Pattern

```ts
import { request } from '@playwright/test';

async function createTestUser(): Promise<{ email: string; password: string }> {
  const api = await request.newContext({ baseURL: process.env.E2E_API_URL });
  const resp = await api.post('/api/test/users', {
    data: { prefix: `e2e-${Date.now()}` },
  });
  return resp.json();
}

async function deleteTestUser(email: string): Promise<void> {
  const api = await request.newContext({ baseURL: process.env.E2E_API_URL });
  await api.delete(`/api/test/users/${encodeURIComponent(email)}`);
}
```

### Worker-Scoped Isolation

```ts
export const test = base.extend<{}, { workerAccount: { email: string } }>({
  workerAccount: [async ({}, use) => {
    const account = await createTestUser();
    await use(account);
    await deleteTestUser(account.email);
  }, { scope: 'worker' }],
});
```

## 4) Serial vs Parallel

Run in parallel by default only when data and side effects are isolated.

Use serial mode when:

- Tests mutate the same stateful account in a multi-step journey.
- The environment cannot isolate data.
- The journey has unavoidable ordering (checkout funnel).

If serial is required, state why. Do not silently serialize whole suites.

### Correct Serial Usage

```ts
test.describe('checkout funnel — serial because steps share cart state', () => {
  test.describe.configure({ mode: 'serial' });
  let page: import('@playwright/test').Page;

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage();
    await page.goto('/');
  });

  test.afterAll(async () => { await page.close(); });

  test('step 1: add item to cart', async () => {
    await page.getByRole('button', { name: 'Add to cart' }).first().click();
    await expect(page.getByTestId('cart-count')).toHaveText('1');
  });

  test('step 2: proceed to checkout', async () => {
    await page.getByRole('link', { name: 'Checkout' }).click();
    await expect(page.getByRole('heading', { name: 'Checkout' })).toBeVisible();
  });

  test('step 3: complete payment', async () => {
    await page.getByLabel('Card number').fill('4242424242424242');
    await page.getByRole('button', { name: 'Pay' }).click();
    await expect(page.getByText('Order confirmed')).toBeVisible();
  });
});
```

## 5) Network and Mock Boundaries

Mock only external systems that are non-deterministic, expensive, or operationally unsafe.

### Route Interception Example

```ts
test('payment page handles gateway timeout', async ({ page }) => {
  await page.route('**/api/payment/charge', route =>
    route.fulfill({ status: 504, body: JSON.stringify({ error: 'Gateway timeout' }) })
  );

  await page.goto('/checkout');
  await page.getByRole('button', { name: 'Pay' }).click();
  await expect(page.getByText('Payment service unavailable')).toBeVisible();
});
```

### What to Keep Real

- Core auth/session behavior if it is part of product risk.
- Core business flows under primary app control.
- Database reads that form the user-facing contract.

### What to Mock/Stub

- Third-party payment gateways (rate-limited, irreversible).
- Email/SMS delivery (no observable UI feedback).
- Analytics and tracking (side effect only, no user-facing result).

## 6) Wait Strategy (Advanced)

### Polling Assertion with `toPass`

```ts
// retry an assertion block until it passes (Playwright ≥ 1.30)
await expect(async () => {
  const resp = await page.request.get('/api/jobs/123');
  expect(resp.status()).toBe(200);
  const body = await resp.json();
  expect(body.status).toBe('completed');
}).toPass({ timeout: 30_000 });
```

### Web Socket Waiting

```ts
const wsPromise = page.waitForEvent('websocket');
await page.goto('/live-feed');
const ws = await wsPromise;

const messagePromise = ws.waitForEvent('framereceived', {
  predicate: (frame) => JSON.parse(frame.payload as string).type === 'update',
});
await messagePromise;
await expect(page.getByTestId('live-count')).not.toHaveText('0');
```

## 7) Artifact Policy

Recommended baseline:

```ts
use: {
  trace: 'on-first-retry',
  screenshot: 'only-on-failure',
  video: 'retain-on-failure',
}
```

During flaky triage, temporarily increase trace or headed runs, then document why.

### CI Artifact Upload (GitHub Actions)

```yaml
- name: Upload Playwright report
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: playwright-report
    path: playwright-report/
    retention-days: 14
```

## 8) CI Strategy

### Blocking vs Nightly Split

```
┌─────────────────────────────────┐
│  PR Gate (blocking)             │  ← critical journeys only, < 5 min
│  - login, core CRUD, checkout   │
├─────────────────────────────────┤
│  Nightly (non-blocking)         │  ← full regression, multi-browser
│  - edge cases, slow flows       │
│  - visual comparison            │
└─────────────────────────────────┘
```

### Sharding for Speed

```ts
// playwright.config.ts
export default defineConfig({
  fullyParallel: true,
  workers: process.env.CI ? 4 : undefined,
});
```

```yaml
# GitHub Actions matrix sharding
strategy:
  matrix:
    shard: [1/4, 2/4, 3/4, 4/4]
steps:
  - run: npx playwright test --shard=${{ matrix.shard }}
```

### Retry Policy

- Retries are for transient noise, not logic defects.
- `retries: 2` in CI, `retries: 0` locally.
- If a test needs > 2 retries to pass, it belongs in flaky triage, not in retries config.

## 9) Honest Scaffolding

If env values, fixtures, or auth state are missing:

```ts
import { test, expect } from '@playwright/test';

const BASE_URL = process.env.E2E_BASE_URL;

test.skip(!BASE_URL, 'E2E_BASE_URL not set — see README for setup');

// TODO: Replace with real test account credentials
// Required env vars: E2E_USER, E2E_PASS
// See: docs/e2e-setup.md
test('user can complete checkout', async ({ page }) => {
  test.skip(!process.env.E2E_USER, 'E2E_USER not configured');

  await page.goto(`${BASE_URL}/login`);
  // ... scaffold continues with explicit TODOs
});
```

## 10) Page Object vs Domain Helper

### When to Use Page Objects

- Large applications with many shared UI regions (nav, sidebar).
- Team convention already uses POM.

### When to Prefer Domain Helpers

- Smaller projects where POM overhead is not justified.
- When the helper is a 2-3 line reusable function.

```ts
// domain helper — lightweight, composable
export async function addItemToCart(page: Page, productName: string) {
  await page.getByRole('listitem')
    .filter({ hasText: productName })
    .getByRole('button', { name: 'Add to cart' })
    .click();
  await expect(page.getByText(`${productName} added`)).toBeVisible();
}
```

## 11) Multi-Browser and Viewport

```ts
// playwright.config.ts
projects: [
  { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
  { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  { name: 'mobile-chrome', use: { ...devices['Pixel 5'] } },
  { name: 'mobile-safari', use: { ...devices['iPhone 13'] } },
],
```

Run specific project in CI:

```bash
npx playwright test --project=chromium --project=firefox
```

## 12) Error Recovery and Retry

### Soft Assertions

```ts
// collect multiple failures in one test instead of failing on first
await expect.soft(page.getByTestId('price')).toHaveText('$9.99');
await expect.soft(page.getByTestId('quantity')).toHaveText('1');
await expect.soft(page.getByTestId('total')).toHaveText('$9.99');
```

### Conditional Skip for Known Issues

```ts
test('feature behind flag', async ({ page }) => {
  test.fixme(process.env.FEATURE_X !== 'true', 'Waiting for FEATURE_X rollout');
  // test body
});
```

## 13) Accessibility Testing

Integrate automated accessibility checks into E2E journeys. Accessibility defects found during user flow traversal are higher-signal than static-analysis-only scans because they reflect the real rendered DOM state.

### axe-core with Playwright (Recommended)

```bash
npm install -D @axe-core/playwright
```

```ts
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('login page has no critical a11y violations', async ({ page }) => {
  await page.goto('/login');

  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();

  expect(results.violations).toEqual([]);
});
```

### Scoped Analysis

```ts
test('checkout form is accessible', async ({ page }) => {
  await page.goto('/checkout');

  const results = await new AxeBuilder({ page })
    .include('#checkout-form')       // scan only this region
    .exclude('#third-party-widget')  // skip embedded widgets
    .analyze();

  expect(results.violations).toEqual([]);
});
```

### Journey-Integrated A11y Checks

Run accessibility checks at key milestones during a user journey, not just on initial page load:

```ts
test('checkout journey is accessible at each step', async ({ page }) => {
  await page.goto('/products');

  // milestone 1: product listing
  let a11y = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
  expect(a11y.violations, 'product listing a11y').toEqual([]);

  await page.getByRole('button', { name: 'Add to cart' }).first().click();
  await page.getByRole('link', { name: 'Cart' }).click();

  // milestone 2: cart page (dynamic content loaded)
  a11y = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
  expect(a11y.violations, 'cart page a11y').toEqual([]);

  await page.getByRole('button', { name: 'Checkout' }).click();

  // milestone 3: checkout form (complex form with validation)
  a11y = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
  expect(a11y.violations, 'checkout form a11y').toEqual([]);
});
```

### CI Integration Pattern

```ts
// a11y.spec.ts — dedicated accessibility suite
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const CRITICAL_PAGES = ['/login', '/signup', '/dashboard', '/settings', '/checkout'];

for (const path of CRITICAL_PAGES) {
  test(`${path} passes WCAG 2.1 AA`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState('networkidle');

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
      .analyze();

    const serious = results.violations.filter(v =>
      v.impact === 'critical' || v.impact === 'serious'
    );
    expect(serious, `a11y violations on ${path}`).toEqual([]);
  });
}
```

### When to Add A11y Checks

| Scenario | Action |
|----------|--------|
| New page or major UI change | Add page-level a11y test |
| Complex form (checkout, signup) | Add scoped a11y for form region |
| Dynamic content (modals, toasts) | Check a11y after content renders |
| Third-party widgets | Exclude from scans, document decision |

### Common Violations and Fixes

| Violation | Impact | Typical Fix |
|-----------|--------|-------------|
| Missing form labels | Critical | Add `<label>` or `aria-label` |
| Insufficient color contrast | Serious | Adjust foreground/background colors |
| Missing alt text on images | Serious | Add descriptive `alt` attribute |
| Keyboard-inaccessible controls | Critical | Add `tabindex`, use semantic HTML |
| Missing landmark regions | Moderate | Use `<main>`, `<nav>`, `<header>` |

## 14) Visual Regression

Catch unintended visual changes by comparing screenshots across runs. Use this alongside functional E2E assertions, not as a replacement.

### Playwright Built-in Screenshot Comparison

```ts
test('homepage renders correctly', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveScreenshot('homepage.png', {
    maxDiffPixelRatio: 0.01,
  });
});
```

```ts
test('dashboard chart renders', async ({ page }) => {
  await page.goto('/dashboard');
  await page.waitForLoadState('networkidle');

  // element-level screenshot for targeted comparison
  const chart = page.getByTestId('revenue-chart');
  await expect(chart).toHaveScreenshot('revenue-chart.png', {
    maxDiffPixels: 100,
  });
});
```

### First Run: Generate Baselines

```bash
# generate initial reference screenshots
npx playwright test --update-snapshots

# verify baselines look correct, then commit
git add tests/e2e/*.spec.ts-snapshots/
git commit -m "test: add visual regression baselines"
```

### Handling Dynamic Content

```ts
test('profile page visual', async ({ page }) => {
  await page.goto('/profile');

  // mask dynamic content before screenshot
  await expect(page).toHaveScreenshot('profile.png', {
    mask: [
      page.getByTestId('timestamp'),
      page.getByTestId('avatar'),
      page.getByTestId('notification-badge'),
    ],
    maxDiffPixelRatio: 0.01,
  });
});
```

### Threshold Strategy

| Context | Recommended Threshold | Rationale |
|---------|----------------------|-----------|
| Full page | `maxDiffPixelRatio: 0.01` | 1% tolerance for font rendering differences |
| Component | `maxDiffPixels: 100` | Small absolute tolerance for isolated elements |
| Charts/graphs | `maxDiffPixelRatio: 0.05` | Data-driven content may shift slightly |
| Animations | Mask or skip | Inherently non-deterministic |

### CI Considerations

```ts
// playwright.config.ts
export default defineConfig({
  expect: {
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.01,
      // different OS may render fonts differently
      threshold: 0.2,
    },
  },
  // snapshot naming: include platform for cross-OS baselines
  snapshotPathTemplate: '{testDir}/__screenshots__/{testFilePath}/{arg}{-projectName}{ext}',
});
```

```yaml
# in CI: update snapshots on a dedicated branch when intentional
- name: Update visual baselines
  if: github.event.label.name == 'update-snapshots'
  run: npx playwright test --update-snapshots
```

### When to Use Visual Regression

| Use | Don't Use |
|-----|-----------|
| Landing pages, marketing pages | Highly dynamic real-time data |
| Design system component library | User-generated content pages |
| Critical brand-consistent UI | Pages behind A/B tests |
| After CSS/layout refactors | During active feature development |

### External Services (Optional)

For teams needing approval workflows, cross-browser baselines, or large-scale comparisons:

| Service | Strength |
|---------|----------|
| Percy (BrowserStack) | GitHub PR integration, approval workflow |
| Chromatic (Storybook) | Component-level visual testing |
| Argos CI | Open-source friendly, fast comparisons |
| Playwright built-in | Zero external dependency, good for most projects |

Prefer Playwright built-in unless the team explicitly needs an external approval workflow.

## 15) Mobile and Desktop E2E

### Mobile Web Testing (Playwright Emulation)

Playwright can emulate mobile devices without actual devices:

```ts
// playwright.config.ts
import { devices } from '@playwright/test';

export default defineConfig({
  projects: [
    { name: 'desktop-chrome', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile-chrome', use: { ...devices['Pixel 7'] } },
    { name: 'mobile-safari', use: { ...devices['iPhone 14'] } },
    { name: 'tablet', use: { ...devices['iPad Pro 11'] } },
  ],
});
```

### Mobile-Specific Assertions

```ts
test.describe('mobile navigation', () => {
  test.use({ ...devices['iPhone 14'] });

  test('hamburger menu opens and navigates', async ({ page }) => {
    await page.goto('/');

    // desktop nav should be hidden on mobile
    await expect(page.getByRole('navigation', { name: 'Main' })).not.toBeVisible();

    // mobile hamburger should be visible
    await page.getByRole('button', { name: 'Menu' }).click();
    await expect(page.getByRole('navigation', { name: 'Mobile menu' })).toBeVisible();

    await page.getByRole('link', { name: 'Products' }).click();
    await expect(page).toHaveURL(/\/products$/);
  });

  test('touch-friendly tap targets', async ({ page }) => {
    await page.goto('/products');

    // verify buttons are large enough for touch (44x44px minimum)
    const addButton = page.getByRole('button', { name: 'Add to cart' }).first();
    const box = await addButton.boundingBox();
    expect(box!.width).toBeGreaterThanOrEqual(44);
    expect(box!.height).toBeGreaterThanOrEqual(44);
  });
});
```

### Responsive Breakpoint Testing

```ts
const BREAKPOINTS = [
  { name: 'mobile', width: 375, height: 812 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1280, height: 720 },
  { name: 'wide', width: 1920, height: 1080 },
];

for (const bp of BREAKPOINTS) {
  test(`layout at ${bp.name} (${bp.width}px)`, async ({ browser }) => {
    const context = await browser.newContext({
      viewport: { width: bp.width, height: bp.height },
    });
    const page = await context.newPage();
    await page.goto('/dashboard');

    if (bp.width < 768) {
      await expect(page.getByTestId('sidebar')).not.toBeVisible();
      await expect(page.getByRole('button', { name: 'Menu' })).toBeVisible();
    } else {
      await expect(page.getByTestId('sidebar')).toBeVisible();
    }

    await context.close();
  });
}
```

### Geolocation and Permissions (Mobile Scenarios)

```ts
test('location-based store finder', async ({ browser }) => {
  const context = await browser.newContext({
    geolocation: { latitude: 40.7128, longitude: -74.0060 },
    permissions: ['geolocation'],
    ...devices['iPhone 14'],
  });
  const page = await context.newPage();

  await page.goto('/stores/nearby');
  await expect(page.getByText('New York')).toBeVisible();

  await context.close();
});
```

### Electron Desktop App Testing

```ts
// electron.spec.ts
import { test, _electron as electron } from '@playwright/test';

test('electron app launches and shows main window', async () => {
  const app = await electron.launch({
    args: ['./dist/main.js'],
    env: { ...process.env, NODE_ENV: 'test' },
  });

  const window = await app.firstWindow();
  await window.waitForLoadState('domcontentloaded');

  await expect(window.getByRole('heading', { name: 'Welcome' })).toBeVisible();

  // electron-specific: check window title
  const title = await window.title();
  expect(title).toBe('My Desktop App');

  await app.close();
});
```

### Electron File Dialog and System Integration

```ts
test('electron file open dialog', async () => {
  const app = await electron.launch({ args: ['./dist/main.js'] });
  const window = await app.firstWindow();

  // intercept dialog before triggering it
  app.evaluate(({ dialog }) => {
    dialog.showOpenDialog = () =>
      Promise.resolve({ canceled: false, filePaths: ['/tmp/test-file.txt'] });
  });

  await window.getByRole('button', { name: 'Open file' }).click();
  await expect(window.getByText('test-file.txt')).toBeVisible();

  await app.close();
});
```

### React Native Web Testing

For React Native apps with web targets (`react-native-web` or Expo Web):

```ts
// react-native-web apps expose standard DOM — test like any web app
test.describe('React Native Web app', () => {
  test('navigation drawer works', async ({ page }) => {
    await page.goto('/');

    // RN Web components render as standard HTML with testID → data-testid
    await page.getByTestId('menu-button').click();
    await expect(page.getByTestId('drawer')).toBeVisible();

    await page.getByTestId('nav-settings').click();
    await expect(page).toHaveURL(/\/settings$/);
  });
});
```

### Platform Decision Matrix

| Platform | Recommended Approach | Notes |
|----------|---------------------|-------|
| Mobile web (responsive) | Playwright device emulation | Built-in, no extra setup |
| Native iOS/Android | Detox, Maestro, or Appium | Out of Playwright scope |
| React Native Web | Playwright (standard web test) | `testID` maps to `data-testid` |
| Electron | Playwright `_electron` API | Built-in support |
| Tauri | Playwright WebView debugging | Connect to WebView port |
| Progressive Web App | Playwright + mobile emulation | Test install prompt separately |

# Anti-Examples — DO NOT Generate

Read this file when generating or reviewing Playwright code. Each example shows a common mistake and the correct alternative.

## 1. Unconditional sleep instead of signal wait

BAD:
```ts
await page.click('#submit');
await page.waitForTimeout(3000);
expect(await page.textContent('.result')).toBe('Done');
```

GOOD:
```ts
await page.click('#submit');
await expect(page.getByText('Done')).toBeVisible();
```

## 2. Fragile CSS selector chain

BAD:
```ts
await page.click('div.sidebar > ul > li:nth-child(3) > a.nav-link');
```

GOOD:
```ts
await page.getByRole('link', { name: 'Settings' }).click();
```

## 3. Shared mutable data across parallel tests

BAD:
```ts
test('admin deletes user', async ({ page }) => {
  await page.goto('/admin/users');
  await page.getByRole('row', { name: 'shared-user@test.com' }).getByRole('button', { name: 'Delete' }).click();
});
test('user updates profile', async ({ page }) => {
  await loginAs(page, 'shared-user@test.com');  // deleted by parallel test
});
```

GOOD:
```ts
test('admin deletes user', async ({ page, testUser }) => {
  // testUser is a fresh fixture-scoped user
  await page.goto('/admin/users');
  await page.getByRole('row', { name: testUser.email }).getByRole('button', { name: 'Delete' }).click();
});
```

## 4. UI login in every test instead of storageState

BAD:
```ts
test('dashboard loads', async ({ page }) => {
  await page.goto('/login');
  await page.fill('#email', 'user@test.com');
  await page.fill('#password', 'secret');
  await page.click('button[type="submit"]');
  await page.waitForURL('/dashboard');
  // actual test starts here
});
```

GOOD:
```ts
// global-setup.ts: authenticate once, save storageState
// playwright.config.ts: use: { storageState: '.auth/user.json' }
test('dashboard loads', async ({ page }) => {
  await page.goto('/dashboard');
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
});
```

## 5. Silently serializing entire suite

BAD:
```ts
test.describe.configure({ mode: 'serial' });
test.describe('all checkout tests', () => {
  test('add item', async ({ page }) => { /* ... */ });
  test('view cart', async ({ page }) => { /* ... */ });
  test('apply coupon', async ({ page }) => { /* ... */ });
  test('checkout', async ({ page }) => { /* ... */ });
});
```

GOOD:
```ts
// only the stateful sequence is serial; independent tests stay parallel
test.describe('checkout multi-step journey', () => {
  test.describe.configure({ mode: 'serial' });
  test('add item → view cart → checkout', async ({ page }) => { /* single journey */ });
});
test('apply coupon independently', async ({ page }) => { /* parallel-safe */ });
```

## 6. Asserting implementation detail instead of outcome

BAD:
```ts
await page.click('#submit');
await expect(page.locator('.spinner')).toBeVisible();
await expect(page.locator('.spinner')).not.toBeVisible();
await expect(page.locator('.success-icon svg path')).toHaveAttribute('d', 'M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z');
```

GOOD:
```ts
await page.click('#submit');
await expect(page.getByText('Order confirmed')).toBeVisible();
```

## 7. Guessing env values or secrets

BAD:
```ts
const BASE_URL = 'https://staging.myapp.com';  // invented
const API_KEY = 'sk-test-fake123';              // fabricated
```

GOOD:
```ts
const BASE_URL = process.env.E2E_BASE_URL;
test.skip(!BASE_URL, 'E2E_BASE_URL not set — see README for setup');
```

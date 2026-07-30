# Anti-Examples — Extended Catalog

Every case here exists **only in this file**. It needs more context than an
always-loaded file should carry.

The seven core cases live in `SKILL.md` §Anti-Examples and are not repeated here —
loading both used to mean reading the same seven twice. Those seven are, verbatim:

1. Unconditional waitForTimeout in assertions
2. Fragile CSS selector chains
3. Shared mutable data across tests
4. Guessing env values or credentials
5. Silently serializing entire suite
6. Repeating login instead of storageState
7. Pseudo-runnable scaffold without test.skip

If a mistake you are checking for is in that list, you already have it — this file
adds nothing on those.

## Table of Contents

- [Waiting on `networkidle`](#waiting-on-networkidle)
- [Querying across an iframe boundary](#querying-across-an-iframe-boundary)
- [Retries used to hide a product bug](#retries-used-to-hide-a-product-bug)
- [Unmasked dynamic content in a visual snapshot](#unmasked-dynamic-content-in-a-visual-snapshot)
- [Branching on element visibility](#branching-on-element-visibility)
- [Asserting a third-party widget's internals](#asserting-a-third-party-widgets-internals)
- [Network wait armed after the action that triggers it](#network-wait-armed-after-the-action-that-triggers-it)
- [Skip guard in an `after` hook](#skip-guard-in-an-after-hook)
- [`test.describe` body doing async setup](#testdescribe-body-doing-async-setup)

Mechanically checked by `python3 scripts/lint_e2e_spec.py`: `networkidle`,
network-wait ordering, and skip-guard-in-an-`after`-hook (via C4). Not checked:
iframe boundary, retries hiding bugs, unmasked snapshots, visibility branching,
third-party internals, async describe body — those need your judgement.

The `after`-hook case is additionally verified against a real Playwright run by
`bash scripts/verify_hook_semantics.sh` (opt-in; needs npm).

## Waiting on `networkidle`

Playwright's API reference marks `networkidle` **DISCOURAGED**: "Don't use this
method for testing, rely on web assertions to assess readiness instead." It looks
more principled than `waitForTimeout` but is the same mistake — a proxy signal
standing in for the state you actually care about.

BAD:
```ts
await page.goto('/dashboard');
await page.waitForLoadState('networkidle');   // never settles if the page polls
await expect(page.getByTestId('total')).toHaveText('42');
```

GOOD:
```ts
await page.goto('/dashboard');
await expect(page.getByTestId('total')).toHaveText('42');  // auto-retries
```

## Querying across an iframe boundary

Page-level locators do not enter frames. This produces a "my selector is right
but the element isn't found" report on every embedded payment or editor widget.

BAD:
```ts
await page.getByLabel('Card number').fill('4242424242424242');  // never found
```

GOOD:
```ts
const payment = page.frameLocator('iframe[title="Secure payment input"]');
await payment.getByLabel('Card number').fill('4242424242424242');
```

## Retries used to hide a product bug

Retries absorb infrastructure flakiness. They must never be raised to make a
genuine defect go green — that ships the bug and destroys the signal.

BAD:
```ts
// checkout fails ~30% of the time, so...
export default defineConfig({ retries: 5 });
```

GOOD:
```ts
export default defineConfig({ retries: process.env.CI ? 2 : 0 });
// Intermittent checkout failure tracked in #456: POST /api/address races the
// optimistic UI. Quarantined with an owner and a deadline, not retried away.
```

## Unmasked dynamic content in a visual snapshot

A timestamp or avatar in frame guarantees a diff on every run. The suite then
gets ignored, which is worse than not having it.

BAD:
```ts
await expect(page).toHaveScreenshot('profile.png');  // clock in the header
```

GOOD:
```ts
await expect(page).toHaveScreenshot('profile.png', {
  mask: [page.getByTestId('timestamp'), page.getByTestId('avatar')],
  maxDiffPixelRatio: 0.01,
});
```

## Branching on element visibility

`isVisible()` returns immediately without retrying, so the branch is decided by a
race. The test then passes by skipping the thing it was written to verify.

BAD:
```ts
if (await page.getByText('Cookie banner').isVisible()) {
  await page.getByRole('button', { name: 'Accept' }).click();
}
await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
```

GOOD:
```ts
const BASE_URL = process.env.E2E_BASE_URL;
test.skip(!BASE_URL, 'E2E_BASE_URL not set — see docs/e2e-setup.md');

// Decide by state you control, then assert unconditionally.
await page.context().addCookies([
  { name: 'cookie_consent', value: 'accepted', url: BASE_URL! },
]);
await page.goto('/');
await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
```

If a conditional truly is unavoidable, wait for one of the two states to settle
first — never read visibility on an element that may still be arriving.

## Asserting a third-party widget's internals

You do not control that DOM. It changes without notice and its failure is not
your product's failure.

BAD:
```ts
await expect(page.frameLocator('#stripe').locator('.SubmitButton--complete')).toBeVisible();
```

GOOD:
```ts
// Assert YOUR page's resulting state after the widget does its job.
await expect(page.getByRole('heading', { name: 'Payment received' })).toBeVisible();
```

## Network wait armed after the action that triggers it

Playwright only delivers events that arrive **after** the waiter is installed. An
inline `await page.waitForResponse(...)` placed below the triggering action misses
a response that already landed, and hangs for the full timeout. It passes only
while the API stays slow — so it looks like a fix for a race while actually
depending on the race.

BAD:
```ts
await page.getByRole('button', { name: 'Save address' }).click();
await page.waitForResponse(resp => resp.url().includes('/api/address'));
```

GOOD:
```ts
const saved = page.waitForResponse(resp => resp.url().includes('/api/address'));
await page.getByRole('button', { name: 'Save address' }).click();
await saved;
```

BEST — assert the state the next step depends on, which survives an endpoint rename:
```ts
await page.getByRole('button', { name: 'Save address' }).click();
await expect(page.getByText('Address confirmed')).toBeVisible();
```

Same ordering rule for `waitForRequest`, `waitForEvent`, and
`context.waitForEvent('page')`.

## Skip guard in an `after` hook

An `after` hook runs once the body has finished, so a guard there cannot stop the
read it was written to prevent. Worse, Playwright still honours the skip: the run
is **relabelled skipped after the body already ran**, so a suite that should have
failed on unset config reports as skipped and nobody investigates.

Measured on Playwright 1.62.0 — `scripts/verify_hook_semantics.sh` asserts this:

| Guard location | Body runs? | Reported as |
|----------------|-----------|-------------|
| file scope / test body / `beforeEach` / `beforeAll` | no | skipped |
| `afterEach` / `afterAll` | **yes** | skipped |

BAD:
```ts
const PASS = process.env.E2E_PASS;

test.afterEach(async () => {
  test.skip(!PASS, 'password missing');   // too late — body already used PASS
});

test('user signs in', async ({ page }) => {
  await page.getByLabel('Password').fill(PASS!);
});
```

GOOD:
```ts
const PASS = process.env.E2E_PASS;
test.skip(!PASS, 'E2E_PASS not set — see docs/e2e-setup.md');

test('user signs in', async ({ page }) => {
  await page.getByLabel('Password').fill(PASS!);
});
```

A `beforeAll` guard is also valid and covers every test in its scope — verified
across retries, two workers, and describe nesting, where it correctly skips only
the group it belongs to.

## `test.describe` body doing async setup

The describe callback runs at collection time, before any test executes. Awaiting
there either fails outright or silently runs setup at the wrong moment.

BAD:
```ts
test.describe('orders', async () => {
  const user = await createTestUser();   // runs during collection
  test('sees orders', async ({ page }) => { /* ... */ });
});
```

GOOD:
```ts
test.describe('orders', () => {
  let user: TestUser;
  test.beforeAll(async () => { user = await createTestUser(); });
  test('sees orders', async ({ page }) => { /* uses user */ });
});
```

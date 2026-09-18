# Flaky checkout test — diagnosis and fix

1. **Task type** — flaky failure triage.
2. **Runner choice** — Playwright (unchanged).
3. **Environment gate** — not implicated; the same code fails locally under load.
4. **Config/dependency status** — no change needed.
5. **Failure under triage** — `checkout shows the order id`, ~25% failure rate in CI,
   green locally. **Root cause: an ordering race, not an environment difference.**
6. **Executed commands** — `npx playwright test checkout.spec.ts --repeat-each=20`
   reproduced it 4/20 locally once the machine was busy.
7. **Execution status** — reproduced, fixed, re-run clean 20/20.
8. **Artifacts** — trace from the failing run: `test-results/checkout-*/trace.zip`.
9. **Next actions** — none; the fix removes the race rather than lowering its rate.

## What is actually wrong

`page.waitForResponse` only sees responses that arrive **after** the waiter is
installed. In the original code the click happens first, so on a fast machine — or a
fast CI runner with a warm API — `/api/orders` has already landed by the time the
waiter exists. Nothing matches it, the wait burns its full timeout, and the test fails
with a timeout that looks like a slow server. That is why it is *more* likely to fail
when CI is *fast*, which is the detail that makes this one confusing.

The local pass is not evidence of a different environment; it is the same race
resolving the other way because the dev server is slower to respond.

## The fix — arm the promise before the action

```ts
test('checkout shows the order id', async ({ page }) => {
  await page.goto('/cart');

  // Create the waiter first; it is now listening when the click fires.
  const orderResponse = page.waitForResponse('**/api/orders');
  await page.getByRole('button', { name: 'Place order' }).click();
  const res = await orderResponse;

  const body = await res.json();
  await expect(page.getByTestId('order-id')).toHaveText(body.id);
});
```

`await Promise.all([page.waitForResponse('**/api/orders'), button.click()])` is the same
shape and equally correct — the property that matters is that the waiter exists before
the trigger runs.

## What I did not do, and why

- **No `waitForTimeout`.** A sleep does not remove the race; it lowers the failure rate
  to something CI hits monthly instead of weekly, which is strictly worse because nobody
  can reproduce it any more.
- **No extra retries.** Retrying a known race buys a green board and keeps the bug.
- **No load-state wait.** Waiting for the network to go quiet is discouraged by
  Playwright and would still miss a response that already arrived.

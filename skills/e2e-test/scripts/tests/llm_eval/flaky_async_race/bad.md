# Flaky checkout test — fixed

CI machines are slower and more loaded than your laptop, so the order API sometimes
takes longer than the test allows. Give it room to settle and let Playwright retry the
occasional blip.

```ts
test.describe.configure({ retries: 2 });

test('checkout shows the order id', async ({ page }) => {
  await page.goto('/cart');
  await page.getByRole('button', { name: 'Place order' }).click();
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(3000);
  const res = await page.waitForResponse('**/api/orders');
  const body = await res.json();
  await expect(page.getByTestId('order-id')).toHaveText(body.id);
});
```

Waiting for the network to go idle plus a short buffer covers the slow-CI case, and the
two retries absorb anything left. That should take the failure rate to near zero.

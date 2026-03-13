# Agent Browser Workflows

Use this file for exploration, failure reproduction, and flow-to-code conversion.

## Table of Contents

1. [Exploration Workflow](#1-exploration-workflow)
2. [Failure Reproduction Workflow](#2-failure-reproduction-workflow)
3. [Bridge To Playwright](#3-bridge-to-playwright)
4. [Command Reference](#4-command-reference)
5. [Screenshot and Evidence Strategy](#5-screenshot-and-evidence-strategy)
6. [Common Pitfalls](#6-common-pitfalls)

## 1) Exploration Workflow

Use Agent Browser when the UI structure is unknown or when you need to discover selectors and interaction patterns.

### Step-by-Step

1. Open the target URL.
2. Snapshot the page state to get the accessibility tree.
3. Interact using semantic targets from the snapshot.
4. Re-snapshot after major transitions.
5. Capture milestone screenshots.
6. Record the exact command sequence.

### Example: Discovering a Checkout Flow

```bash
# step 1: open and inspect
agent-browser open http://localhost:3000/products
agent-browser snapshot -i
# → inspect available products, identify "Add to cart" buttons

# step 2: interact with discovered targets
agent-browser click @btn-add-to-cart-1
agent-browser snapshot -i
# → toast appeared, cart badge updated

# step 3: navigate to cart
agent-browser click @link-cart
agent-browser snapshot -i
# → cart page: 1 item, "Proceed to checkout" button

# step 4: capture evidence
agent-browser screenshot artifacts/cart-with-item.png

# step 5: continue flow
agent-browser click @btn-checkout
agent-browser snapshot -i
# → checkout form: address fields, payment section
agent-browser screenshot artifacts/checkout-form.png
```

### What to Record at Each Step

- Semantic target used (`getByRole`, `getByTestId`, or snapshot reference).
- Page URL after navigation.
- Key visible text or state changes.
- Whether a network request was involved (check Network tab if needed).

## 2) Failure Reproduction Workflow

Use Agent Browser when:

- The failing path is easier to inspect interactively.
- Selectors or UI transitions are unclear from code alone.
- You need a screenshot path to understand the failure state.
- The test failure may be environment-specific.

### Reproduction Template

```bash
# 1. set up same state as failing test
agent-browser open <URL-from-failing-test>

# 2. follow the exact steps from the test
agent-browser fill @email "user@test.com"
agent-browser fill @password "password"
agent-browser click @btn-signin
agent-browser wait navigation

# 3. reach the failure point
agent-browser click @btn-submit-form
agent-browser snapshot -i
# → compare with expected state from test assertion

# 4. capture evidence
agent-browser screenshot artifacts/repro-failure-state.png
```

### Reproduction Report Template

```
Environment: local / staging / preview
URL: <exact URL>
Steps to reproduce:
  1. <command 1>
  2. <command 2>
  3. ...
Observed state: <what happened>
Expected state: <what should have happened>
Screenshot: artifacts/<filename>.png
Stable selectors found: <list>
```

## 3) Bridge To Playwright

After an Agent Browser repro, convert findings into durable Playwright code.

### Conversion Checklist

1. **Identify stable selectors**: prefer `getByRole` with names found in snapshot over snapshot-specific `@ref` IDs.
2. **Map milestone states to assertions**: each Agent Browser snapshot → one `expect()`.
3. **Extract repeated interactions into helpers**: if the same click/fill sequence appears across tests, make it a function.
4. **Preserve business outcome assertions**: the Playwright test should verify the same user-visible outcomes you confirmed in Agent Browser.
5. **Add error path coverage**: if Agent Browser revealed error states, add negative test cases.

### Before/After Example

Agent Browser session:
```
agent-browser open http://localhost:3000/signup
agent-browser fill @name "Test User"
agent-browser fill @email "test@example.com"
agent-browser fill @password "StrongP@ss1"
agent-browser click @btn-register
agent-browser wait navigation
agent-browser snapshot -i
# → welcome page, heading "Welcome, Test User!"
```

Playwright conversion:
```ts
test('new user can register', async ({ page }) => {
  await page.goto('/signup');
  await page.getByLabel('Name').fill('Test User');
  await page.getByLabel('Email').fill(`e2e-${Date.now()}@example.com`);
  await page.getByLabel('Password').fill('StrongP@ss1');
  await page.getByRole('button', { name: 'Register' }).click();

  await page.waitForURL('**/welcome');
  await expect(page.getByRole('heading', { name: /Welcome/ })).toBeVisible();
});
```

Key differences from Agent Browser version:
- Dynamic email (`Date.now()`) for data isolation.
- `getByLabel`/`getByRole` instead of snapshot `@ref` IDs.
- `expect()` assertion instead of visual inspection.

## 4) Command Reference

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `agent-browser open <url>` | Navigate to URL | Start of any exploration |
| `agent-browser snapshot -i` | Get interactive accessibility tree | After each navigation or state change |
| `agent-browser screenshot <path>` | Save visual evidence | At milestones and failure points |
| `agent-browser click <target>` | Click element | Buttons, links, interactive elements |
| `agent-browser fill <target> "<value>"` | Type into input | Form fields |
| `agent-browser select <target> "<value>"` | Select dropdown option | Select elements |
| `agent-browser wait navigation` | Wait for page navigation | After clicks that trigger navigation |
| `agent-browser evaluate "<js>"` | Run JS in page context | Check localStorage, cookies, or JS state |

## 5) Screenshot and Evidence Strategy

### When to Capture

- **Before interaction**: capture initial state for comparison.
- **After critical actions**: login success, form submission, payment.
- **At failure point**: capture the exact state when something goes wrong.
- **After fix validation**: prove the fix resolved the issue.

### Naming Convention

```
artifacts/
├── exploration-<flow>-<step>.png      # discovery sessions
├── repro-<issue>-<step>.png           # failure reproduction
├── before-fix-<issue>.png             # pre-fix state
└── after-fix-<issue>.png              # post-fix state
```

## 6) Common Pitfalls

| Pitfall | How to Avoid |
|---------|-------------|
| Using Agent Browser `@ref` IDs in Playwright | Always translate to `getByRole`/`getByLabel`/`getByTestId` |
| Not re-snapshotting after state changes | Snapshot after every interaction that changes the DOM |
| Leaving critical flows as Agent Browser-only | Always convert to Playwright if the flow should be regression-protected |
| Assuming Agent Browser selectors are stable | Verify selectors work in Playwright; snapshot refs are session-specific |

## 7) Command Starters

Use only the commands relevant to the task:

```bash
agent-browser open http://localhost:3000
agent-browser snapshot -i
agent-browser screenshot artifacts/ab-state.png
npx playwright test
npx playwright test --trace on
npx playwright test tests/e2e/<suite>.spec.ts --repeat-each=5
npx playwright show-report
```

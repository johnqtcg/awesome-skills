# E2E Checklists

## Table of Contents

1. [Pre-Run Checklist](#pre-run-checklist)
2. [Critical Journey Checklist](#critical-journey-checklist)
3. [Playwright Code Review Checklist](#playwright-code-review-checklist)
4. [Flaky Triage Template](#flaky-triage-template)
5. [Quarantine Rules](#quarantine-rules)
6. [CI Gate Checklist](#ci-gate-checklist)
7. [Agent Browser Session Checklist](#agent-browser-session-checklist)

## Pre-Run Checklist

Before writing or running any E2E test:

1. Confirm task type: new coverage, flaky triage, failed CI, or exploratory repro.
2. Confirm target environment and base URL source (env var, config file, or hardcoded).
3. Confirm required env vars, accounts, feature flags, and third-party dependencies.
4. Confirm seed/reset path or decide that only scaffold output is honest.
5. Enable artifact paths (trace, screenshot, video) before execution.
6. Verify Playwright version matches project `package.json` (check Version Gate).
7. Confirm `webServer` or manual startup is appropriate for the environment.

## Critical Journey Checklist

For each critical flow:

1. Verify entry preconditions (authenticated user, seeded data, correct URL).
2. Execute one happy-path scenario end-to-end.
3. Execute one invalid-input scenario (wrong password, missing field, expired token).
4. Execute one edge-case scenario (empty state, boundary values, concurrent action).
5. Verify important side effects where applicable (email sent, record created, notification shown).
6. Assert final state from user perspective, not implementation detail.
7. Validate that cleanup or teardown does not leave residual state.

## Playwright Code Review Checklist

When reviewing or generating Playwright test code, verify:

### Selectors (Critical)
- [ ] `getByRole` / `getByLabel` / `getByTestId` used for ≥ 90% of interactions
- [ ] No fragile CSS chains (`div > span > a.link`) or XPath
- [ ] Accessible names match visible text (not internal IDs)

### Waits (Critical)
- [ ] Zero unconditional `waitForTimeout` (outside diagnostic comments)
- [ ] State transitions use `toBeVisible()`, `waitForURL()`, or `waitForResponse()`
- [ ] Loading states handled with `expect` auto-retry, not manual polling

### Data (Critical)
- [ ] Test data is isolated per test or per worker
- [ ] No shared mutable records across parallel tests
- [ ] Cleanup is deterministic (fixture teardown or API reset)

### Auth
- [ ] Auth strategy is explicit (storageState reuse or justified in-test login)
- [ ] Credentials come from env vars, not hardcoded in source

### Structure
- [ ] Serial vs parallel choice is justified with comment
- [ ] Reusable flows extracted to fixtures or helpers (not copy-pasted)
- [ ] Test names describe user journey, not implementation

### Artifacts
- [ ] trace, screenshot, video policies are configured
- [ ] CI uploads artifacts on failure

### Assertions
- [ ] Assertions after every major interaction
- [ ] Outcomes asserted (visible text, URL, count), not implementation (CSS class, spinner SVG path)

## Flaky Triage Template

```
Test name:
Suite/file:
Environment: local | CI | staging | preview
Frequency: X/Y runs failed
First failing build/time:

Failure signature:
  - Error message:
  - Stack trace summary:
  - Screenshot/trace path:

Suspected category:
  [ ] selector instability
  [ ] async race condition
  [ ] test-data coupling
  [ ] third-party / network instability
  [ ] environment drift
  [ ] application defect

Repro command:
  npx playwright test <file> --repeat-each=10 --trace on

Evidence:
  - Trace analysis:
  - Network timing:
  - DOM state at failure:

Root cause (after investigation):

Fix applied:

Stability validation:
  npx playwright test <file> --repeat-each=20
  Result: __/20 passed

Owner:
Due date:
Quarantine status: [ ] quarantined | [ ] fixed | [ ] under investigation
```

## Quarantine Rules

1. Quarantine only after reproducibility analysis — never pre-emptively.
2. Never quarantine all tests in a critical suite.
3. Every quarantined test must have:
   - A tracking ticket/issue.
   - An assigned owner.
   - A removal deadline (default: 2 weeks).
4. Remove quarantine only after ≥ 20 consecutive stable runs.
5. If quarantine deadline passes without fix, escalate — do not silently extend.
6. Quarantined tests must still be tracked in CI (run but not gating).

## CI Gate Checklist

When setting up or reviewing CI E2E configuration:

1. [ ] Browser install step present (`npx playwright install --with-deps`).
2. [ ] Secrets injected via CI secret mechanism, not committed to repo.
3. [ ] `webServer` or equivalent startup configured with timeout.
4. [ ] Artifact upload on failure (HTML report, traces, screenshots).
5. [ ] Retry count set (typically 2 for CI, 0 for local).
6. [ ] Critical suite runtime < 5 minutes for PR gate.
7. [ ] Broader regression suite in nightly or non-blocking job.
8. [ ] Sharding configured if suite exceeds 10 minutes.
9. [ ] Failure notifications routed to appropriate channel.

## Agent Browser Session Checklist

Before converting Agent Browser findings to Playwright:

1. [ ] All milestone states captured as screenshots.
2. [ ] Exact command sequence recorded.
3. [ ] Stable selectors identified (role + name preferred).
4. [ ] Snapshot `@ref` IDs translated to `getByRole`/`getByLabel`/`getByTestId`.
5. [ ] Dynamic data identified (need `Date.now()` or fixture-generated values).
6. [ ] Error states explored (not just happy path).
7. [ ] Conversion covers the same business outcome assertions.

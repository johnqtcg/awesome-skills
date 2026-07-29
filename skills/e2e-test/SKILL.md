---
name: e2e-test
description: "Design, maintain, and execute reliable end-to-end tests for critical user journeys with Agent Browser as first choice for exploration and Playwright as the preferred code path for suites and CI. Use for E2E strategy, journey coverage, flaky test triage, artifact collection, CI gating, regression prevention, and browser automation tasks."
allowed-tools: Read, Write, Grep, Glob, Bash(go test*), Bash(go vet*), Bash(npx playwright*), Bash(playwright*), Bash(npm run*), Bash(npm ci*), Bash(curl*), Bash(agent-browser*), Bash(bash scripts/*), Bash(python3 scripts/*)
---

# E2E test

Use this skill to create E2E coverage that is deterministic, evidence-backed, and maintainable in real repositories.

## Quick Reference

| If you need to… | Go to |
|---|---|
| Design new E2E test coverage for a user journey | §Operating Model → new journey coverage + Load `references/checklists.md` |
| Write or update Playwright tests | §Runner Strategy + Load `references/playwright-patterns.md` |
| Use advanced Playwright (auth, fixtures, mocking, CI sharding) | Load `references/playwright-deep-patterns.md` |
| Triage a flaky or failing E2E test | §Operating Model → flaky triage + Load `references/checklists.md` |
| Use Agent Browser for exploration or repro | §Runner Strategy + Load `references/agent-browser-workflows.md` |
| Design CI gates for E2E suites | §Operating Model → CI gate design + Load `references/environment-and-dependency-gates.md` |
| Avoid common Playwright mistakes | Load `references/anti-examples.md` |
| Test content inside an iframe (payment, editor, OAuth) | Load `references/playwright-deep-patterns.md` §Iframes |
| Handle a Tauri or native-mobile app | §Version and Platform Gate → Platform Scope Boundary |
| Check generated spec code before reporting | Run `python3 scripts/lint_e2e_spec.py <file.spec.ts>` |
| See a fully worked E2E output example | Load `references/golden-examples.md` |

Do not use this skill for visual design review with no automated journey value,
performance/load testing, or tests that would require guessed secrets, endpoints,
or private accounts.

## Load References Selectively

Load on demand, not up front. A typical Playwright task needs the first two rows
and nothing else.

| When | Load / run | Contents |
|------|-----------|----------|
| Every task, before coverage or gate decisions | `references/checklists.md` | 5 checklists: pre-run readiness, journey coverage, flaky triage, quarantine, result reporting |
| Every task, before claiming runnable | `references/environment-and-dependency-gates.md` | Readiness gates per context (local / preview / staging / CI), `available` vs `declared` vs `missing`, dependency matrix |
| Before gate decisions | `bash scripts/discover_e2e_needs.sh` | Detects runner, Node, framework, existing tests, env-var states, CI platform. Report facts, not guesses |
| Writing Playwright code (JS only) | `references/playwright-patterns.md` | Selector order (`getByRole` first), wait patterns, assertion contracts, config baseline, API-introduction + Node tables |
| Auth, fixtures, data isolation, mocking, iframes, sharding | `references/playwright-deep-patterns.md` | The advanced layer — large; open the section you need |
| A mistake not among the seven below | `references/anti-examples.md` | Extended catalog only, no overlap with §Anti-Examples here |
| Using Agent Browser | `references/agent-browser-workflows.md` | Commands, exploration→code conversion, repro steps, handoff format |
| Shaping the final report | `references/golden-examples.md` | Full output-contract examples (Playwright + Go). **All figures in it are synthetic** |
| Grading generated spec code | `python3 scripts/lint_e2e_spec.py <file>` | Deterministic check of C1–C4 / S1 / S3 / S5 / H2 + W1. Evidence, not a verdict |

## Runner Strategy

Use both tools intentionally, not interchangeably.

- Agent Browser first:
  - journey discovery
  - repro of flaky or environment-specific UI behavior
  - fast semantic interaction and screenshot capture
- Playwright preferred for code:
  - committed E2E tests
  - CI suites
  - repeated local validation
  - multi-browser or matrix execution

If a task starts in Agent Browser and the flow is valuable long-term, convert the learned steps into Playwright coverage.

## Operating Model

1. Classify the task:
   - new journey coverage
   - flaky triage
   - failed CI investigation
   - exploratory browser reproduction
   - test architecture or CI gate design

2. Run `scripts/discover_e2e_needs.sh` to collect repository facts (Playwright version, framework, existing tests, env vars, CI platform). Use its structured output for gate decisions instead of guessing.

3. Run the environment and configuration gate.

4. Choose the runner path:
   - Agent Browser for exploration or reproduction
   - Playwright for maintainable automated coverage
   - both when discovery should become code
   - **non-JS projects**: use the project's native test framework (see Runner Selection below)

5. Produce only the strongest deliverable the environment can actually support:
   - runnable test
   - guarded scaffold with explicit skips
   - triage report with repro commands

### Runner Selection Guidance

If the project has no Node.js / Playwright (e.g., Go, Python, Rust web apps):

- Use the project's native test framework (Go `net/http`, Python `requests`/`httpx`, etc.)
- Do NOT install Playwright into a project that has no JavaScript toolchain
- Follow the project's existing E2E test conventions if they exist
- Document the runner selection rationale in the Output Contract
- All 5 mandatory gates still apply regardless of runner choice

## Mandatory Gates

### 1) Configuration Gate

Before generating or updating runnable tests:

- scan repository config, scripts, env files, docs, and existing tests
- list required variables, accounts, feature flags, and service dependencies
- mark each with one of these four states — the same vocabulary
  `scripts/discover_e2e_needs.sh` emits:

| State | Means | Consequence |
|-------|-------|-------------|
| `available` | a non-empty value exists now (process env or a real `.env`) | usable |
| `declared` | the name is known but no value is supplied here — a `.env.example` entry, or `E2E_PASS=` with nothing after it | **not** usable; confirm the runtime source before claiming runnable |
| `missing` | no evidence the project uses this variable at all | scaffold or stop |
| `unknown` | not yet inspected | inspect before deciding |

`declared` is the state most easily mistaken for `available`. A template file
proves a variable is *expected*, never that a value exists. Treating the two as
the same is what turns "cannot run" into a false "ready".

Never print a variable's value to check whether it is set — report the state. CI
logs, screen recordings, and agent transcripts all capture stdout.

If required values are missing:

- do not invent them
- generate placeholder-only scaffolding with explicit TODOs and skip guards when code output is still useful
- otherwise stop and report the exact blockers

Guard **every** variable the suite needs, not just the first one. A
`test.skip(!USER)` leaves an unset `PASS` to reach the page as `undefined`, which
surfaces as a login failure rather than "you forgot to set PASS".

In every result include:

- required variable list with each variable's state
- example export block or config shape
- missing variables

### 2) Environment Gate

Before claiming a test is runnable, determine:

- target environment: local, preview, staging, CI
- base URL and auth flow
- whether seed/reset is deterministic
- whether third-party dependencies can be stubbed or must be live
- whether test accounts and permissions are available

Read `references/environment-and-dependency-gates.md` whenever environment readiness is uncertain.

### 3) Execution Integrity Gate

Never claim a suite or repro was executed unless it actually ran.

If commands were not run, output:

- `Not run in this environment`
- reason
- exact commands to run next

If commands were run, report:

- command(s)
- target environment
- pass/fail status
- artifact locations

### 4) Stability Gate

Do not treat a single pass as proof of reliability for critical paths or flaky failures.

Use repeat runs, traces, screenshots, and environment evidence before concluding:

- the bug is fixed
- the test is stable
- the failure is infra-only

### 5) Side-Effect Gate

Default to safe behavior for real-world side effects:

- avoid production data mutation
- avoid real-money or irreversible flows unless explicitly configured for safe test execution
- require explicit approval or isolation for destructive actions

## Version and Platform Gate

Before recommending Playwright code or config, adapt to the repository's actual platform:

| Signal | Adaptation |
|--------|------------|
| Playwright `< 1.27` | Prefer `locator` and stable attribute selectors. `getByRole`, `getByLabel`, `getByTestId`, and `getByPlaceholder` do not exist yet. |
| Playwright `< 1.29` | No `expect(...).toPass()`. Use `expect.poll()` (1.21+) instead. |
| Playwright `< 1.33` | No `filter({ hasNot })` and no `expect(locator).toBeAttached()`. |
| Node below the pinned Playwright's `engines.node` floor | `npm install` fails. Not runnable — do not claim "ready to run". |
| Node meets `engines` but is outside Playwright's supported list (latest 22.x / 24.x / 26.x) | Runnable but **unsupported**. Say so; do not report it as supported. |

Two different Node constraints exist — the `engines.node` install floor and the
documented supported-runtime list — and they do not agree. Both tables are in
`references/playwright-patterns.md` §Node.js Compatibility.

Never wait on `waitForLoadState('networkidle')` at any version — Playwright marks
it DISCOURAGED. Assert the user-visible state instead.

The full API-introduction and Node-compatibility tables live in
`references/playwright-patterns.md` §Version and Platform Gate. Read the
project's pinned version before generating code; when it cannot be determined,
target the oldest plausible version and say so in the Output Contract.

Framework adaptation checklist:
- **Next.js**: verify `baseURL`, server startup, and auth/session bootstrapping strategy.
- **SPA**: prefer explicit waits on route or API completion, not arbitrary sleeps.
- **SSR**: assert server-rendered and hydrated states separately when needed.
- **Monorepo**: locate the owning package, config file, and CI entrypoint before generating commands.

### Platform Scope Boundary

Playwright is not the answer everywhere. Route away from it rather than
generating code that cannot run:

| Platform | Route to | Why |
|----------|----------|-----|
| Native iOS / Android | Detox, Maestro, or Appium | No browser to drive |
| **Tauri** | WebdriverIO + `@wdio/tauri-service` | Renders in the OS webview (WKWebView / WebView2 / WebKitGTK); Playwright cannot attach. See `references/playwright-deep-patterns.md` §Tauri |
| Electron | Playwright `_electron` | Supported natively |
| React Native **Web** | Playwright | Standard DOM; `testID` → `data-testid` |

Say plainly that the tool does not fit, name the right one, and stop. A
plausible-looking Playwright suite for a Tauri app is worse than no answer.

### Content Inside Iframes

Page-level locators do not cross a frame boundary. Embedded payment fields,
editors, and OAuth screens need `frameLocator`. When an element is visibly on
screen but "not found", check for an iframe before changing the selector — see
`references/playwright-deep-patterns.md` §Iframes and Embedded Third-Party
Content. Payment iframes additionally require the Side-Effect Gate: confirm
sandbox mode before running anything.

## Playwright-First Engineering Rules

Use `references/playwright-deep-patterns.md` whenever generating or refactoring Playwright code.

At minimum:

- prefer reusable fixtures and domain helpers over copy-pasted flows
- use stable auth setup such as `storageState` when appropriate
- isolate data per test or per worker
- define what can be mocked and what must stay real
- choose serial vs parallel execution intentionally
- keep retries, trace, screenshot, and video policies aligned with CI needs

If the repository lacks the needed config or fixtures, generate the smallest honest scaffold rather than pseudo-runnable code.

## Anti-Examples

### 1) Unconditional waitForTimeout in assertions
BAD:
```ts
await page.waitForTimeout(3000);
await expect(page.getByText("Order confirmed")).toBeVisible();
```
GOOD:
```ts
await expect(page.getByText("Order confirmed")).toBeVisible();
```

### 2) Fragile CSS selector chains
BAD:
```ts
await page.locator(".app > div:nth-child(2) .cta.primary").click();
```
GOOD:
```ts
await page.getByRole("button", { name: "Continue" }).click();
```

### 3) Shared mutable data across tests
BAD:
```ts
const sharedEmail = "e2e-user@example.com";
test("profile update", async ({ page }) => { /* mutates same account */ });
```
GOOD:
```ts
const email = `e2e-${test.info().parallelIndex}-${Date.now()}@example.com`;
test("profile update", async ({ page }) => { /* isolated data per test */ });
```

### 4) Guessing env values or credentials
BAD:
```ts
await page.goto("http://staging");
await page.fill("#email", "fake-user@test.com");
await page.fill("#password", "password123");
```
GOOD:
```ts
test.skip(!process.env.E2E_BASE_URL || !process.env.E2E_USER, "explicit TODOs until config exists");
await page.goto(process.env.E2E_BASE_URL!);
```

### 5) Silently serializing entire suite
BAD:
```ts
test.describe.configure({ mode: "serial" });
```
GOOD:
```ts
test.describe("checkout funnel", () => {
  test.describe.configure({ mode: "serial" }); // justified by irreversible payment sandbox state
});
```

### 6) Repeating login instead of storageState
BAD:
```ts
test.beforeEach(async ({ page }) => {
  await page.goto("/login");
  await page.fill("#email", process.env.E2E_USER!);
});
```
GOOD:
```ts
test.use({ storageState: "playwright/.auth/user.json" });
```

### 7) Pseudo-runnable scaffold without test.skip
BAD:
```ts
test("checkout", async ({ page }) => {
  await page.goto(process.env.E2E_BASE_URL!);
});
```
GOOD:
```ts
test.skip(!process.env.E2E_BASE_URL, "missing base URL");
// TODO: wire payment sandbox account before enabling this journey
```

## Agent Browser Bridge

Use Agent Browser to discover or reproduce, then convert findings into durable code.

Required bridge steps:

1. capture the environment and entry URL
2. record the exact command sequence
3. save milestone screenshots
4. note the selectors or semantic targets that proved stable
5. translate the validated flow into Playwright assertions and helpers

Read `references/agent-browser-workflows.md` when using Agent Browser.

## Flaky Test Policy

See `references/checklists.md` §Flaky Triage Template for the complete template.

Key rules:
- A test is flaky only with non-deterministic behavior under unchanged code and environment
- Required sequence: reproduce (`--repeat-each=N` or `-count=N`) → classify root cause → fix → quarantine with deadline
- Root cause categories: selector instability, async race, test-data coupling, network instability, environment drift, application defect
- quarantine only with owner, tracking issue, and removal deadline

## CI Strategy

For PR automation, separate **Blocking** critical journeys from broader nightly coverage:

- Blocking PR gate:
  - run `playwright install --with-deps chromium` during setup when browsers are not pre-baked
  - use Secret injection for base URL, auth state bootstrap, and sandbox-only credentials
  - upload-artifact for trace, screenshot, video, and HTML report on failure
  - keep retries and timeout values explicit in config and CI job output
- Nightly / extended lane:
  - run broader browser matrix, accessibility sweeps, and visual regression
  - increase retries only for known infra volatility, not to hide product bugs

## Output Contract

For any E2E task, return:

1. `Task type`
2. `Runner choice`
3. `Environment gate`
4. `Config/dependency status`
5. `Covered journey` or `Failure under triage`
6. `Executed commands`
7. `Execution status`
8. `Artifacts`
9. `Next actions`

If code was generated, also include:

- files created or updated
- skip conditions or TODO markers if scaffolding only

### Machine-Readable Summary (JSON)

When the output will be consumed by CI or downstream tooling, append:

```json
{
  "task_type": "new_journey_coverage",
  "runner": "playwright",
  "environment": "local",
  "execution_status": "pass",
  "tests_passed": 3,
  "tests_failed": 0,
  "tests_skipped": 0,
  "artifacts": ["playwright-report/index.html", "test-results/"],
  "scorecard": { "critical": "PASS", "standard": "5/6", "hygiene": "4/4" },
  "blockers": [],
  "next_actions": ["add password-reset edge case"]
}
```

## Quality Scorecard

For non-Playwright runners (Go HTTP, Python requests, etc.), mark Playwright-specific items as **N/A**. Count only applicable items when computing pass rates.

List every item including the N/A ones. Dropping a row and dividing by a smaller
denominator inflates the score.

For Playwright output, run `python3 scripts/lint_e2e_spec.py <file>` before
reporting. It mechanically checks C1, C2, C3, C4, S1, S3, S5, and H2, plus W1
(network wait armed after its trigger — an extra check, not a scorecard item).
It does **not** check S2, S4, S6, H1, H3, H4 — those need repository and CI
context it cannot see, so assess them yourself. A clean report is weaker
evidence than a dirty one: it is a heuristic pass, not a parser, and cannot see
through helpers or page objects.

### Critical (any FAIL → overall FAIL)

| # | Item | PASS rule |
|---|------|-----------|
| C1 | No unconditional `waitForTimeout` in assertions | Zero instances outside diagnostic comments |
| C2 | Data isolation explicit | Each test owns its data or has deterministic cleanup |
| C3 | No guessed secrets or URLs | All external values from env/config with skip guard |
| C4 | All 5 mandatory gates addressed | Configuration, Environment, Execution Integrity, Stability, Side-Effect |

### Standard (≥ 4/6 PASS)

| # | Item | PASS rule |
|---|------|-----------|
| S1 | Selectors use `getByRole`/`getByLabel`/`getByTestId` | ≥ 90% of interactions use accessible selectors |
| S2 | Auth strategy explicit | storageState reuse or justified in-test login |
| S3 | Assertions after major interactions | Every user-visible state change has an `expect` |
| S4 | Artifact policy configured | trace, screenshot, video settings present |
| S5 | Serial vs parallel justified | Serial only with documented reason |
| S6 | Mock boundaries documented | Each mocked dependency has rationale |

### Hygiene (≥ 3/4 PASS)

| # | Item | PASS rule |
|---|------|-----------|
| H1 | Reusable fixtures/helpers | Shared flows extracted, not copy-pasted |
| H2 | Descriptive test names | Name describes user journey, not implementation |
| H3 | CI strategy present | Blocking gate vs nightly split documented |
| H4 | Repeat-run validation | Critical paths validated with `--repeat-each` |

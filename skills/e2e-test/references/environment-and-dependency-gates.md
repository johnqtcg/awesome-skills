# Environment And Dependency Gates

Use this file before claiming a test is runnable. Load it whenever environment readiness is uncertain.

## Table of Contents

1. [Local](#1-local)
2. [Preview / Review Apps](#2-preview--review-apps)
3. [Staging](#3-staging)
4. [CI](#4-ci)
5. [Dependency Readiness Matrix](#5-dependency-readiness-matrix)
6. [Stop Conditions](#6-stop-conditions)
7. [Environment Decision Flowchart](#7-environment-decision-flowchart)

## 1) Local

Check:

- Base URL and startup command (verify in `package.json` scripts or `README`).
- Local seed/reset path (migration, fixture seeding).
- Required env vars (list each with source: `.env`, `.env.local`, vault).
- Whether third-party calls can be stubbed (mock server, route intercept).

### Verification Commands

```bash
# check if dev server starts
npm run dev -- --port 3000 &
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000
# expect 200 or 302

# check env var availability
echo "E2E_BASE_URL=${E2E_BASE_URL:-MISSING}"
echo "E2E_USER=${E2E_USER:-MISSING}"
echo "E2E_PASS=${E2E_PASS:-MISSING}"
```

### If Local Env is Incomplete

- Prefer scaffolding with `test.skip` guards or Agent Browser exploration.
- Do NOT emit pseudo-runnable tests with guessed URLs or secrets.
- Document exactly what is missing and how to provide it.

Example skip guard:
```ts
const BASE_URL = process.env.E2E_BASE_URL;
test.skip(!BASE_URL, 'E2E_BASE_URL not set — run: export E2E_BASE_URL=http://localhost:3000');
```

## 2) Preview / Review Apps

Check:

- Stable deployment URL (from CI output, PR comment, or deploy config).
- Auth/account availability in preview environment.
- Seeded data vs shared mutable state.
- Environment drift relative to local and CI.

### Preview-Specific Risks

| Risk | Mitigation |
|------|-----------|
| URL changes per PR/deploy | Read URL from CI artifact or env var, never hardcode |
| Shared database across previews | Use per-preview data isolation or avoid data-mutating tests |
| Stale preview (not redeployed) | Verify deploy timestamp before running |
| Missing secrets in preview | Check which secrets are injected into preview environments |

Use preview for:

- Quick validation against deployed UI.
- Repro of environment-specific bugs (CORS, CSP, HTTPS-only cookies).

Do not assume preview is deterministic enough for broad gating.

## 3) Staging

Check:

- Safe test accounts (dedicated, not shared with QA or demo).
- Reset strategy (can tests clean up after themselves?).
- Third-party sandbox behavior (Stripe test mode, SendGrid sandbox).
- Whether side effects are acceptable (email sends, webhook fires).

### Staging Decision Table

| Condition | Action |
|-----------|--------|
| Dedicated test accounts available | ✅ Run full suite |
| Shared accounts, no isolation | ⚠️ Run read-only flows only, skip mutations |
| No reset mechanism | ⚠️ Create data only, verify, but cannot clean up — warn |
| Third-party sandbox available | ✅ Include payment/notification flows |
| Real third-party (no sandbox) | ❌ Mock or skip those flows |

Prefer staging for critical-path realism, but keep destructive coverage constrained.

## 4) CI

Check:

- Secret injection method (`${{ secrets.* }}` in GitHub Actions, env vars in other CI).
- Artifact paths (HTML report, traces, screenshots).
- Browser install command (`npx playwright install --with-deps`).
- Whether base URL is local (via `webServer`), preview, or staging.
- Shard/parallel settings.

### CI Environment Template

```yaml
env:
  E2E_BASE_URL: http://localhost:3000     # or staging URL
  E2E_USER: ${{ secrets.E2E_USER }}
  E2E_PASS: ${{ secrets.E2E_PASS }}
  CI: true
```

### CI-Specific Considerations

| Item | Recommendation |
|------|---------------|
| Browser | Install only needed browsers (e.g., Chromium only for PR gate) |
| Workers | 2–4 for CI to balance speed and resource limits |
| Retries | 2 in CI, 0 locally |
| Timeout | 30s per test, 15 min per job |
| Artifacts | Always upload on failure; retain 14 days |

If CI-only values are missing, generate code with explicit skip or TODO markers and document the missing variables.

## 5) Dependency Readiness Matrix

Mark each dependency as:

| Status | Meaning | Action |
|--------|---------|--------|
| `ready` | Available and deterministic | Include in tests |
| `missing` | Not configured or unavailable | Skip with guard, document |
| `unstable` | Available but flaky/non-deterministic | Mock or limit exposure |
| `out of scope` | Not relevant to this test objective | Exclude, document reason |

### Dependencies to Inspect

| Dependency | Key Questions |
|-----------|--------------|
| Auth provider | Token valid? Session reusable? MFA bypass for test? |
| Payment sandbox | Stripe test mode? Sandbox credentials? |
| Email/SMS verification | Can be bypassed in test? Mailhog/Mailtrap available? |
| Seeded test data | Fixture available? API endpoint for seeding? |
| Feature flags | Test flags set? Can they be toggled per env? |
| Third-party API mocks | Mock server running? Route intercept sufficient? |
| Database | Can be reset? Isolated per test run? |
| File storage | S3/local mock available? Upload testable? |

## 6) Stop Conditions

Do NOT generate runnable tests when any of these are unresolved:

1. No base URL (cannot determine where to navigate).
2. No safe auth path (no test account, no bypass, no storageState).
3. No deterministic data setup for a stateful journey.
4. No safe way to avoid irreversible side effects (production payments, real emails).

**Instead**: generate guarded scaffolding with `test.skip`, TODO markers, and a clear list of what must be provided.

## 7) Environment Decision Flowchart

```
Is base URL known?
├── NO  → scaffold with skip guard, stop
└── YES
    Is auth path available?
    ├── NO  → scaffold with auth TODO, stop
    └── YES
        Is data isolation possible?
        ├── NO
        │   Is the journey read-only?
        │   ├── YES → run with caution note
        │   └── NO  → scaffold with data TODO, stop
        └── YES
            Are side effects safe?
            ├── NO  → mock unsafe deps, then run
            └── YES → run with full confidence
```

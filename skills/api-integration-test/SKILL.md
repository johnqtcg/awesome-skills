---
name: api-integration-test
description: "Create, maintain, and run gated Go integration tests for internal APIs and service-to-service clients (HTTP/gRPC). Use for endpoint verification, contract checks with real runtime config, opt-in execution, timeout/retry safety, and integration failure triage in Go services."
allowed-tools: Read, Write, Grep, Glob, Bash(go test*), Bash(go build*), Bash(make*)
---

# API Integration Test

## Goal

Build production-representative, opt-in integration tests for internal APIs with strict safety controls, reproducible execution, and clear failure diagnosis.

## When To Use

Trigger this skill when the user asks for:
- Internal API integration tests (HTTP or gRPC)
- Service-to-service adapter tests requiring real runtime config
- Internal endpoint contract verification against real responses
- Integration test failure triage or debugging

## Scope

Use this skill for:

1. Internal HTTP API integration tests.
2. Internal gRPC client/server integration tests.
3. Service-to-service adapter tests requiring real runtime config.
4. Internal endpoint contract verification against real responses.

Do not use this skill for:

1. Pure unit tests with heavy mocks — use `$unit-test`.
2. Full end-to-end browser journeys.
3. Third-party vendor API tests — use `$thirdparty-api-integration-test`.

## Mandatory Gates

Gates execute in strict serial order. Any gate failure blocks all subsequent steps.

```
1) Scope        2) Go Version   3) Config       4) Mode
   Validation ──→  Gate       ──→  Completeness ──→  Selection
   │               │               │                │
   out of scope?   read go.mod    Full/Scaffold/   auto-select
   → stop+redirect → adapt        Blocked?         Smoke/Std/Comp
                                   Blocked → STOP
        │               │               │                │
        5) Production   6) Execution    7) Reference
           Safety     ──→  Integrity  ──→  Loading
           │               │               │
           prod? env+host  actually ran?   load by trigger
           → t.Fatalf      → report        pattern
```

### 1) Scope Validation Gate

Confirm the task falls within this skill's scope:
- Internal HTTP or gRPC API → proceed
- Pure unit test → redirect to `$unit-test`, **STOP**
- Third-party vendor API → redirect to `$thirdparty-api-integration-test`, **STOP**
- Full end-to-end browser journey → out of scope, inform user, **STOP**

**Hard stop**: If the target is out of scope, the entire remaining workflow is skipped. Output only: (1) scope verdict, (2) recommended skill or approach, (3) reason. Do NOT generate test code, do NOT proceed to subsequent gates.

### 2) Go Version Gate

Read `go.mod` for the project's Go version. Adapt patterns:

| Feature | Minimum Go | Adaptation |
|---------|-----------|------------|
| `t.Setenv` | 1.17 | Below: use `os.Setenv` + `t.Cleanup`. **Panics under `t.Parallel()` on every Go version** (process-wide env) — never combine them |
| `context.WithTimeout` (no leak) | all | Always `defer cancel()` |
| Range var capture fix | 1.22 | Below 1.22: copy loop variable (`tt := tt`) in closures |
| `t.Chdir` | 1.24 | Added 1.24 (below: `os.Chdir` + `t.Cleanup`). Like `t.Setenv`, cannot combine with `t.Parallel()` — panics |

If `go.mod` is not found, state `Go version: unknown` and use the most conservative patterns.

### 3) Configuration Completeness Gate

Apply `references/common-integration-gate.md` and determine degradation level:

| Level | Condition | Action |
|-------|-----------|--------|
| **Full** | All env vars documented, service address known | Proceed to generate complete tests |
| **Scaffold** | Some env vars missing | Generate test with `t.Skip(...)` + `// TODO:` markers. State what is missing in output. |
| **Blocked** | Gate env var unknown or service address undetermined | **STOP.** Output only: variable checklist + example command + setup instructions. |

Never hardcode guessed endpoints, credentials, or identifiers to make tests look runnable.

### 4) Execution Mode Gate

Auto-select mode based on task signals, then state the selection in output:

| Signal | → Mode |
|--------|--------|
| User says "smoke", "connectivity check", "health check" | Smoke |
| First-time environment validation | Smoke |
| Single endpoint, read-only operation | Smoke |
| User says "full", "comprehensive", "release gate" | Comprehensive |
| Post-migration or new service onboarding | Comprehensive |
| ≥ 5 endpoints or security-sensitive API (auth/payment/PII) | Comprehensive |
| User says "review", "audit", "improve", "upgrade" existing tests | Standard (unless explicit mode requested) |
| Everything else | **Standard** (default) |

If the user explicitly requests a specific mode, use that mode regardless of signals.

### 5) Production Safety Gate

**Never trust `ENV` alone** — an endpoint can point at production while `ENV=dev`
(`ENV=dev API_BASE_URL=https://api.production.internal`). Validate the *resolved
target host*, not just the label:

- Refuse when `ENV` is `prod`/`production` **OR** the resolved base-URL host matches
  a production pattern (contains `prod`, `production`, `live`, or a production
  domain suffix your org uses), unless `INTEGRATION_ALLOW_PROD=1`.
- Parse the base URL and check the host against a **non-prod allowlist** (preferred)
  or a prod **denylist** before any call. Fail **closed**: `url.Parse` accepts
  relative refs (`api.production.internal` parses with no error but empty scheme/host;
  `prod-host:8080` gets scheme `prod-host`), so require an **absolute `http(s)` URL
  with a non-empty host** — treat anything else as prod. Checking only the parse error
  is a bypass.
- Require a **dedicated test tenant/account** (e.g. `TEST_TENANT_ID`); refuse a target
  whose tenant is not the designated test tenant.
- For destructive operations (DELETE, UPDATE, DROP), require `INTEGRATION_ALLOW_DESTRUCTIVE=1`
  **in addition**. **A destructive write against production is forbidden under EVERY flag
  combination** — `INTEGRATION_ALLOW_PROD=1` permits READ-only prod tests, never writes. So
  a prod target + `ALLOW_PROD=1` + `ALLOW_DESTRUCTIVE=1` must still `t.Fatalf`. Destructive
  ops **require `NONPROD_HOST_ALLOWLIST`** (fail closed on host — a substring denylist would
  pass `https://api.company.com`) AND a validated non-prod tenant before any destructive call.

**When the run gate is enabled, refusal is a hard failure (`t.Fatalf`), not a silent
`t.Skip`** — see §Skip vs Fail (CI Integrity).

### 6) Execution Integrity Gate

Never claim tests were executed unless they actually ran.

- If `go test -tags=integration` was not run, output:
  - `Not run`
  - reason (e.g., service unreachable, env vars missing)
  - exact command to reproduce
- Do not imply pass/fail for tests that did not execute.
- Never report PASS when tests were actually skipped.
- **A `(cached)` result is NOT evidence of execution.** `go test` prints `ok … (cached)`
  when it reuses a prior result without running the binary — so the live service was
  never contacted. Every real integration run MUST pass `-count=1`; if output shows
  `(cached)`, report it as "did not run this time" and re-run with `-count=1`.

### 7) Load References Selectively

Always load:
- `references/common-integration-gate.md` — before authoring or determining degradation level.
- `references/common-output-contract.md` — before reporting results.

Load on condition:
- `references/checklists.md` — **only when** authoring new tests or triaging failures.
- `references/internal-api-patterns.md` — **only when** writing HTTP/gRPC test code (not for scope rejection or result reporting).
- `references/advanced-patterns.md` — **only when** Comprehensive mode, CI integration, httptest adapter tests, or test data lifecycle management.

## Skip vs Fail (CI Integrity)

`t.Skip` on a *misconfigured* run is a false green: `go test` exits 0 when every
test skips, so a CI job that lost its config — or points at the wrong place —
passes silently. Distinguish **not requested** from **requested but broken**:

| Situation | Behavior | Why |
|-----------|----------|-----|
| Run gate unset (`INTERNAL_API_INTEGRATION != 1`) | `t.Skip` | User did not ask to run — correct to skip |
| Gate set, a required runtime var missing/empty | `t.Fatalf` | Run requested but misconfigured; skipping false-greens CI |
| Gate set, target is production (by ENV or host) without `INTEGRATION_ALLOW_PROD=1` | `t.Fatalf` | Loud refusal, before any call — a prod target you didn't authorize is a dangerous mistake, not a quiet skip |
| Gate set, destructive op without `INTEGRATION_ALLOW_DESTRUCTIVE=1` | `t.Skip` | A deliberate opt-in tier (like the run gate) — keep destructive tests in a separate CI job, NOT the base read-only gate |
| Scaffold test (a value could not be determined at authoring time) | `t.Skip` + `// TODO` | Incomplete by design — but it MUST be excluded from the official integration gate (separate build tag / not in the CI target) so a scaffold-only suite never reports green |

The line: **Skip = "not opted in / incomplete"** (run gate off, destructive not
enabled, scaffold); **Fatal = "opted in but broken or dangerous"** (config missing,
prod target unauthorized). A `t.Skip` that hides a misconfiguration is the bug.
Destructive and scaffold skips must live in CI jobs the base integration gate does
not depend on, so nothing false-greens.

## Execution Modes

### Smoke (connectivity check)
- Test 1 key endpoint per service — the simplest read-only call.
- Timeout: 5s. No retry.
- Assert only: connectivity + HTTP 200/gRPC OK + non-empty response.

### Standard (default)
- Cover primary endpoints: at least 1 success path + 1 expected-failure path per endpoint.
- Timeout: 15s. Max 1 retry for transient failures only.
- Assert both protocol-level and business-level outcomes.

### Comprehensive (full coverage)
- Cover all endpoints + error paths + boundary conditions.
- Timeout: 30s. Max 2 retries with bounded backoff.
- Include: concurrent request safety, large payload, pagination, rate limiting.

## Test Taxonomy

Three layers — only the last two are integration tests:

| Layer | Wiring | Integration? | Build tag |
|-------|--------|:---:|-----------|
| **Adapter / component test** | stub server (`httptest` with a fake handler) + real client | No — it is a unit test | none |
| **In-process integration test** | real handler + real dependencies (real DB/cache/queue) wired in-process, often via `httptest.Server` | Yes | `//go:build integration` |
| **System integration test** | client → a real, separately-deployed endpoint | Yes | `//go:build integration` |

The distinction is what sits *behind* the server: a **stub** handler exercises only
your client's parsing/transport (adapter test — no build tag, lives with unit tests);
a **real** handler with real dependencies is an in-process integration test. This
skill produces the two integration layers. A stub-`httptest` adapter test belongs in
`$unit-test`, not here.

## Required Test Pattern

1. Use file name `<domain>_integration_test.go` near the client/package under test.
2. Add build constraint at file top:
   - `//go:build integration`
   - `// +build integration`
3. Enforce explicit run gate env var (for example `INTERNAL_API_INTEGRATION=1`); when unset, `t.Skip` (the run was not requested).
4. Validate all required env vars at test start. When the gate is set but a required var is missing, `t.Fatalf` with an actionable message — do NOT `t.Skip` (see §Skip vs Fail (CI Integrity)).
5. Block production by ENV **and** by resolved host (never ENV alone):
   - refuse if `ENV` is `prod`/`production` OR the base-URL host matches a prod pattern, unless `INTEGRATION_ALLOW_PROD=1`; when the gate is set this refusal is `t.Fatalf`, not `t.Skip`.
   - require a dedicated test tenant/account and refuse non-test tenants.
6. Parse and validate env var payloads where needed (`strconv`, `strings.TrimSpace`, `url.Parse`, list parsing).
7. Build the client through the production code path against a real target. See §Test Taxonomy for what counts as integration vs an adapter/unit test — a stub `httptest` server is an adapter test, not an integration test.
8. Guard each external call with `context.WithTimeout`.
9. Use bounded retry policy only when justified:
   - default: no retry
   - if enabled: max 1-2 retries, bounded backoff, no infinite loop
10. Assert both:
    - protocol-level contract (HTTP status / gRPC code / required response fields)
    - business invariants (identity mapping, state transitions, key numeric constraints)
11. For expected failure paths, assert failure type/code explicitly (not only `require.Error`).
12. Keep tests idempotent and avoid destructive operations by default.
13. Define test data lifecycle explicitly:
    - setup source, idempotency key strategy, cleanup or safe reuse policy.

## Anti-Examples — DO NOT Write These Tests

1. **Mocking the client you are integrating against** — if you replace `http.Client` or the gRPC connection with a fake, it is a unit test, not an integration test. The entire point is to exercise the real transport path.

2. **Asserting on unstable response fields** — timestamps, request IDs, trace IDs, and randomly-ordered lists change per call. Assert on identity/contract fields, not volatile metadata.
   ```go
   // BAD
   require.Equal(t, "2026-03-08T12:00:00Z", resp.CreatedAt)
   // GOOD
   require.False(t, resp.CreatedAt.IsZero())
   ```

3. **Creating data with no cleanup strategy** — writing to a service that has no delete/archive API without documenting the data lifecycle leaves garbage that eventually breaks the test environment.

4. **Unbounded or unconditional retry loops** — retrying every error hides real failures. See `references/internal-api-patterns.md` §Retry/Timeout Policy Pattern for bounded retry with transient error classification.

5. **Testing internal implementation details** — asserting on the number of DB rows, internal cache state, or internal RPC call counts rather than the API's observable response contract.

6. **Running destructive operations without explicit opt-in** — `DELETE /users/:id` or `DROP TABLE` in a test without a separate env gate (e.g., `INTEGRATION_ALLOW_DESTRUCTIVE=1`) risks production data.

7. **Treating integration tests as performance benchmarks** — a single-call latency measurement has no statistical significance. Use dedicated load testing tools for performance.

8. **Ignoring context cancellation in retry loops** — always check `ctx.Done()` before sleep in retry loops. See `references/internal-api-patterns.md` §Retry/Timeout Policy Pattern.

## Go Implementation Baseline

```go
//go:build integration
// +build integration

func TestUserProfileIntegration(t *testing.T) {
    // Run gate OFF → skip: the user did not ask to run. Everything past this
    // point is "requested, so it must be correct" → t.Fatalf, never t.Skip
    // (see §Skip vs Fail (CI Integrity)).
    if os.Getenv("INTERNAL_API_INTEGRATION") != "1" {
        t.Skip("set INTERNAL_API_INTEGRATION=1 to run")
    }

    env := strings.ToLower(strings.TrimSpace(os.Getenv("ENV")))
    cfgDir := strings.TrimSpace(os.Getenv("CONFIG_DIR"))
    userID := strings.TrimSpace(os.Getenv("TEST_USER_ID"))
    tenant := strings.TrimSpace(os.Getenv("TEST_TENANT_ID"))
    baseURL := strings.TrimSpace(os.Getenv("API_BASE_URL"))
    if env == "" || cfgDir == "" || userID == "" || tenant == "" || baseURL == "" {
        // Gate enabled but misconfigured — FAIL, don't skip, or CI goes green blind.
        t.Fatalf("integration enabled but config incomplete: need ENV, CONFIG_DIR, TEST_USER_ID, TEST_TENANT_ID, API_BASE_URL")
    }

    // Production safety: refuse by ENV *or* resolved host, before any call.
    if isProdTarget(env, baseURL) && os.Getenv("INTEGRATION_ALLOW_PROD") != "1" {
        t.Fatalf("refuse production target (env=%q url=%q): set INTEGRATION_ALLOW_PROD=1 to override, or point at a non-prod endpoint", env, baseURL)
    }
    // A dedicated test tenant is mandatory (Safety Rules) — refuse a non-test tenant.
    assertTestTenant(t, tenant)

    cfg := config.MustLoad()
    client, err := NewInternalClient(cfg.InternalAPI)
    require.NoError(t, err)

    ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
    defer cancel()

    // Success path: protocol-level + business-level assertions
    resp, err := client.GetUserProfile(ctx, userID)
    require.NoError(t, err)
    require.NotNil(t, resp)
    require.Equal(t, http.StatusOK, resp.StatusCode)
    require.Equal(t, userID, resp.Body.UserID)
    require.NotEmpty(t, resp.Body.DisplayName)
}

func TestUserProfile_NotFound_Integration(t *testing.T) {
    if os.Getenv("INTERNAL_API_INTEGRATION") != "1" {
        t.Skip("set INTERNAL_API_INTEGRATION=1 to run")
    }
    // ... env gates same as above ...

    ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
    defer cancel()

    // Expected failure path: assert specific error, not just require.Error
    resp, err := client.GetUserProfile(ctx, "nonexistent-user-id-000")
    require.NoError(t, err) // HTTP call succeeded
    require.Equal(t, http.StatusNotFound, resp.StatusCode)
}

// isProdTarget refuses production by label OR resolved host, and FAILS CLOSED.
// url.Parse accepts relative refs: "api.production.internal" parses with NO error
// but an empty scheme and empty Hostname(), and "prod-host:8080" yields scheme
// "prod-host". Checking only err would let both bypass. So require an absolute
// http(s) URL with a non-empty host; anything else is treated as production.
// A non-prod host allowlist (NONPROD_HOST_ALLOWLIST) is more reliable than a
// substring denylist — prefer it when you can enumerate your test hosts.
func isProdTarget(env, rawURL string) bool {
    if env == "prod" || env == "production" {
        return true
    }
    u, err := url.Parse(rawURL)
    if err != nil || !u.IsAbs() || (u.Scheme != "http" && u.Scheme != "https") || u.Hostname() == "" {
        return true // fail closed
    }
    host := strings.ToLower(u.Hostname())
    if allow := strings.TrimSpace(os.Getenv("NONPROD_HOST_ALLOWLIST")); allow != "" {
        for _, h := range strings.Split(allow, ",") {
            if host == strings.ToLower(strings.TrimSpace(h)) {
                return false // explicitly allowed non-prod host
            }
        }
        return true // not on the allowlist → treat as prod
    }
    for _, bad := range []string{"prod", "production", "live"} { // fallback denylist
        if strings.Contains(host, bad) {
            return true
        }
    }
    return false
}

// assertTestTenant refuses a non-test tenant. TEST_TENANT_ALLOWLIST is REQUIRED
// (fail closed): unset → refuse; a tenant not on the list → refuse.
func assertTestTenant(t *testing.T, tenant string) {
    t.Helper()
    // Fail CLOSED: an allowlist of exact test-tenant IDs is REQUIRED. A denylist
    // ("reject names containing prod/live") is fail-OPEN — a real prod tenant
    // named "acme-main" or "tenant-001" would slip through. No allowlist → refuse.
    allow := strings.TrimSpace(os.Getenv("TEST_TENANT_ALLOWLIST"))
    if allow == "" {
        t.Fatalf("TEST_TENANT_ALLOWLIST is required: list the exact test tenant IDs permitted to run integration tests")
    }
    for _, id := range strings.Split(allow, ",") {
        if tenant == strings.TrimSpace(id) {
            return
        }
    }
    t.Fatalf("tenant %q not in TEST_TENANT_ALLOWLIST — refuse", tenant)
}

// assertDestructiveSafe gates destructive operations. A destructive WRITE is NEVER
// allowed against production under ANY flag combination (INTEGRATION_ALLOW_PROD
// permits READ-only prod tests, not writes). It fails CLOSED on the host — requiring
// an explicit NONPROD_HOST_ALLOWLIST, not the substring denylist (which would pass
// https://api.company.com) — and confirms the tenant is a designated test tenant.
func assertDestructiveSafe(t *testing.T, env, baseURL, tenant string) {
    t.Helper()
    if os.Getenv("INTEGRATION_ALLOW_DESTRUCTIVE") != "1" {
        t.Skip("destructive: set INTEGRATION_ALLOW_DESTRUCTIVE=1 to run")
    }
    if strings.TrimSpace(os.Getenv("NONPROD_HOST_ALLOWLIST")) == "" {
        t.Fatalf("destructive operations require NONPROD_HOST_ALLOWLIST (explicit non-prod hosts) — refuse without it")
    }
    if isProdTarget(env, baseURL) {
        t.Fatalf("destructive operations are forbidden against a production target, even with INTEGRATION_ALLOW_PROD=1")
    }
    assertTestTenant(t, tenant)
}
```

For Scaffold mode pattern (tests with `t.Skip` + `// TODO:` markers for missing config), see `references/common-integration-gate.md` §Scaffold Mode Example.

## Safety Rules

1. Never hardcode secrets, tokens, or private endpoints.
2. Use dedicated test tenant/account data.
3. Prefer read-only or reversible operations; explicitly gate destructive flows.
4. Refuse production environment by default.
5. Keep timeout bounded (typically 5-30s) and retries strictly limited.
6. Distinguish skip from fail (see §Skip vs Fail): `t.Skip` only when the run gate is off (or for a destructive/scaffold opt-in tier); when the gate is set but a prerequisite is missing or the target is prod-unauthorized, `t.Fatalf` with actionable instructions — never a silent skip.

## Execution Commands

```bash
# Smoke mode
INTERNAL_API_INTEGRATION=1 ENV=dev API_BASE_URL=http://localhost:8080 \
  CONFIG_DIR=/path/to/config TEST_USER_ID=123 \
  TEST_TENANT_ID=test-tenant-1 TEST_TENANT_ALLOWLIST=test-tenant-1 \
  go test -tags=integration ./internal/pkg/client/user -run Integration -v -timeout=30s -count=1

# Standard mode (default)
INTERNAL_API_INTEGRATION=1 ENV=dev API_BASE_URL=http://localhost:8080 \
  CONFIG_DIR=/path/to/config TEST_USER_ID=123 \
  TEST_TENANT_ID=test-tenant-1 TEST_TENANT_ALLOWLIST=test-tenant-1 \
  go test -tags=integration ./internal/pkg/client/user -run Integration -v -timeout=120s -count=1

# Comprehensive mode
INTERNAL_API_INTEGRATION=1 ENV=dev API_BASE_URL=http://localhost:8080 \
  CONFIG_DIR=/path/to/config TEST_USER_ID=123 \
  TEST_TENANT_ID=test-tenant-1 TEST_TENANT_ALLOWLIST=test-tenant-1 \
  go test -tags=integration ./internal/pkg/client/user -run Integration -v -timeout=300s -count=1
```

`TEST_TENANT_ALLOWLIST` is mandatory (tenant validation is fail-closed — §Go
Implementation Baseline). A **destructive** run additionally needs
`INTEGRATION_ALLOW_DESTRUCTIVE=1` and `NONPROD_HOST_ALLOWLIST=<your test hosts>`
(destructive is fail-closed on host), and should live in a CI job separate from
the base read-only gate.

**`-count=1` is mandatory on EVERY real integration run, not just Comprehensive.**
Go caches a passing package's result keyed on the test binary + consulted env
vars + files — none of which include the external service. Without `-count=1` a
second run prints `ok … (cached)` and the test binary never executes, so a
service that changed (or broke) since the last run is never contacted. Treat a
`(cached)` line as **"did not run this time"** — never as evidence of a passing
integration against the live service.

## Output Contract

Use the shared output contract:
- `references/common-output-contract.md`
  Load always when reporting results.

## CI Integration

Check if the project already has a Makefile with integration test targets (e.g., `make test-api-integration`). If so, align with existing targets rather than adding new ones. Cross-reference `$go-makefile-writer` when Makefile targets should be added or repaired.

Integration tests in CI require service dependencies. For GitHub Actions service containers, Makefile targets, and Docker Compose patterns, see `references/advanced-patterns.md` §CI Execution Pattern.

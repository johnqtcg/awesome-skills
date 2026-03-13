---
name: api-integration-test
description: "Create, maintain, and run gated Go integration tests for internal APIs and service-to-service clients (HTTP/gRPC). Use for endpoint verification, contract checks with real runtime config, opt-in execution, timeout/retry safety, and integration failure triage in Go services."
allowed-tools: Read, Grep, Glob, Bash
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
           ENV=prod?       actually ran?   load by trigger
           → t.Skip        → report        pattern
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
| `t.Setenv` | 1.17 | Below: use `os.Setenv` + `t.Cleanup` |
| `context.WithTimeout` (no leak) | all | Always `defer cancel()` |
| Range var capture fix | 1.22 | Below 1.22: copy loop variable in closures |
| `t.Parallel()` + `t.Setenv` safe | 1.24 | Below 1.24: do NOT combine in same subtest |

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

- If `ENV` resolves to `prod` or `production`, the generated test must `t.Skip` unless `INTEGRATION_ALLOW_PROD=1`.
- For destructive operations (DELETE, UPDATE, DROP), require additional gate: `INTEGRATION_ALLOW_DESTRUCTIVE=1`.

### 6) Execution Integrity Gate

Never claim tests were executed unless they actually ran.

- If `go test -tags=integration` was not run, output:
  - `Not run`
  - reason (e.g., service unreachable, env vars missing)
  - exact command to reproduce
- Do not imply pass/fail for tests that did not execute.
- Never report PASS when tests were actually skipped.

### 7) Load References Selectively

Always load:
- `references/common-integration-gate.md` — before authoring or determining degradation level.
- `references/common-output-contract.md` — before reporting results.

Load on condition:
- `references/checklists.md` — **only when** authoring new tests or triaging failures.
- `references/internal-api-patterns.md` — **only when** writing HTTP/gRPC test code (not for scope rejection or result reporting).
- `references/advanced-patterns.md` — **only when** Comprehensive mode, CI integration, httptest adapter tests, or test data lifecycle management.

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

## Required Test Pattern

1. Use file name `<domain>_integration_test.go` near the client/package under test.
2. Add build constraint at file top:
   - `//go:build integration`
   - `// +build integration`
3. Enforce explicit run gate env var (for example `INTERNAL_API_INTEGRATION=1`), otherwise `t.Skip`.
4. Validate all required env vars at test start and provide actionable skip message.
5. Block production by default:
   - if `ENV` resolves to `prod`/`production`, `t.Skip` unless `INTEGRATION_ALLOW_PROD=1`.
6. Parse and validate env var payloads where needed (`strconv`, `strings.TrimSpace`, list parsing).
7. Build real client instance (or real handler + `httptest` server) through production code path.
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
    if os.Getenv("INTERNAL_API_INTEGRATION") != "1" {
        t.Skip("set INTERNAL_API_INTEGRATION=1 to run")
    }

    env := strings.ToLower(strings.TrimSpace(os.Getenv("ENV")))
    if (env == "prod" || env == "production") && os.Getenv("INTEGRATION_ALLOW_PROD") != "1" {
        t.Skip("refuse prod by default: set INTEGRATION_ALLOW_PROD=1 to override")
    }

    cfgDir := strings.TrimSpace(os.Getenv("CONFIG_DIR"))
    userID := strings.TrimSpace(os.Getenv("TEST_USER_ID"))
    if env == "" || cfgDir == "" || userID == "" {
        t.Skip("set ENV, CONFIG_DIR, TEST_USER_ID to run")
    }

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
```

For Scaffold mode pattern (tests with `t.Skip` + `// TODO:` markers for missing config), see `references/common-integration-gate.md` §Scaffold Mode Example.

## Safety Rules

1. Never hardcode secrets, tokens, or private endpoints.
2. Use dedicated test tenant/account data.
3. Prefer read-only or reversible operations; explicitly gate destructive flows.
4. Refuse production environment by default.
5. Keep timeout bounded (typically 5-30s) and retries strictly limited.
6. Skip with actionable instructions when prerequisites are missing.

## Execution Commands

```bash
# Smoke mode
INTERNAL_API_INTEGRATION=1 ENV=dev CONFIG_DIR=/path/to/config TEST_USER_ID=123 \
  go test -tags=integration ./internal/pkg/client/user -run Integration -v -timeout=30s

# Standard mode (default)
INTERNAL_API_INTEGRATION=1 ENV=dev CONFIG_DIR=/path/to/config TEST_USER_ID=123 \
  go test -tags=integration ./internal/pkg/client/user -run Integration -v -timeout=120s

# Comprehensive mode
INTERNAL_API_INTEGRATION=1 ENV=dev CONFIG_DIR=/path/to/config TEST_USER_ID=123 \
  go test -tags=integration ./internal/pkg/client/user -run Integration -v -timeout=300s -count=1
```

## Output Contract

Use the shared output contract:
- `references/common-output-contract.md`
  Load always when reporting results.

## CI Integration

Check if the project already has a Makefile with integration test targets (e.g., `make test-api-integration`). If so, align with existing targets rather than adding new ones. Cross-reference `$go-makefile-writer` when Makefile targets should be added or repaired.

Integration tests in CI require service dependencies. For GitHub Actions service containers, Makefile targets, and Docker Compose patterns, see `references/advanced-patterns.md` §CI Execution Pattern.

# Integration Test Quality Scorecard

## Tier System

Findings are classified into three tiers with different pass criteria:

- **Critical**: Any single FAIL → overall FAIL (one-veto rule)
- **Standard**: ≥ 4/5 must pass
- **Hygiene**: ≥ 3/4 must pass

---

## Pre-Authoring Checklist

Apply before writing any test code.

### Critical (any FAIL blocks authoring)

| # | Check | Pass Criteria |
|---|-------|---------------|
| C1 | API target identified | Specific endpoint/method name documented |
| C2 | Gate env var defined | `INTERNAL_API_INTEGRATION=1` (or project equivalent) present |
| C3 | Build tag isolation | `//go:build integration` at file top |
| C4 | Production safety gate | `ENV=prod` → `t.Skip` unless `INTEGRATION_ALLOW_PROD=1` |

### Standard (≥ 4/5 pass)

| # | Check | Pass Criteria |
|---|-------|---------------|
| S1 | All required env vars listed with skip messages | Each missing var → descriptive `t.Skip` |
| S2 | Real client wiring (not mocked transport) | Uses production code path for client creation |
| S3 | Execution mode selected | Smoke / Standard / Comprehensive stated |
| S4 | Timeout bound documented | `context.WithTimeout` value chosen and justified |
| S5 | Test data source identified | Documented where test data comes from and cleanup strategy |

### Hygiene (≥ 3/4 pass)

| # | Check | Pass Criteria |
|---|-------|---------------|
| H1 | Test file naming follows convention | `<domain>_integration_test.go` |
| H2 | Success + failure path planned | At least 1 success case and 1 expected-failure case |
| H3 | Idempotency considered | Test can run multiple times without side effects |
| H4 | CI integration documented | Docker Compose / service container setup referenced |

---

## Test Quality Checklist

Apply to review existing or newly generated test code.

### Critical (any FAIL → reject)

| # | Check | Pass Criteria |
|---|-------|---------------|
| C1 | No hardcoded secrets | Zero strings matching token/password/key patterns |
| C2 | Production gate present | Code refuses `ENV=prod` by default |
| C3 | Context timeout on every external call | Every RPC/HTTP call wrapped in `context.WithTimeout` |
| C4 | Retry loop is bounded | `maxRetries` constant present; `ctx.Done()` checked in loop |

### Standard (≥ 4/5 pass)

| # | Check | Pass Criteria |
|---|-------|---------------|
| S1 | Protocol-level assertion | HTTP status code or gRPC status code asserted |
| S2 | Business-level assertion | At least 1 domain field validated (identity, state, constraint) |
| S3 | Failure path assertion | Expected errors assert specific code/type, not just `require.Error` |
| S4 | No unstable field assertion | Timestamps, UUIDs, trace IDs are existence-checked, not value-compared |
| S5 | Env var validation at test start | All required vars checked before first API call |

### Hygiene (≥ 3/4 pass)

| # | Check | Pass Criteria |
|---|-------|---------------|
| H1 | Descriptive test names | `Test<Domain>_<Scenario>_Integration` naming pattern |
| H2 | Cleanup or idempotency | Created resources cleaned up or test is read-only |
| H3 | Context cancellation handled in retry | `select { case <-ctx.Done(): ... }` before sleep |
| H4 | Skip messages are actionable | Each skip tells the user exactly what env var to set |

---

## Failure Triage Checklist

Apply when integration tests fail to classify the root cause.

| Classification | Symptoms | First Action |
|----------------|----------|-------------|
| **config** | Missing env var, bad parse, wrong base URL | Check env exports, config file path |
| **auth** | 401/403, token expired, certificate error | Refresh credentials, check token scope |
| **network** | Connection refused, DNS failure, dial timeout | Verify service is running, check ports/firewalls |
| **timeout** | Context deadline exceeded | Increase timeout or investigate service latency |
| **contract** | Unexpected HTTP status, missing response fields | Compare response against API spec, check for API version drift |
| **business assertion** | Correct status but wrong data | Verify test data exists, check for concurrent modification |
| **test pollution** | Passes alone, fails in suite | Check for shared state, leaked goroutines, order dependency |

For each failure, output:
1. Classification (from table above)
2. Evidence (exact error message or response snippet)
3. Suggested fix (concrete command or code change)

# Third-Party API Integration Test Checklists

## Pre-Authoring Checklist

1. Confirm target vendor API/client method and ownership.
2. Confirm gate variable (`THIRDPARTY_INTEGRATION=1` or vendor-specific gate).
3. Confirm mandatory env vars and format validation.
4. Confirm production/live safety by ENV **and** resolved host (`VENDOR_SANDBOX_HOSTS`) **and** account (`VENDOR_TEST_ACCOUNTS`), blocked unless `INTEGRATION_ALLOW_PROD=1`.
5. Confirm build-tag isolation (`//go:build integration`).
6. Confirm timeout and retry budget (max retries, backoff, retryable classes).
7. Confirm test data lifecycle (dedicated tenant/account, idempotency key, cleanup/reuse).
8. Confirm rate-limit and auth expectations for the vendor.

## Test Quality Checklist

Score every authored or reviewed test against this and **report the verdict** — see
`common-output-contract.md` field 9. A rubric nobody reports is a rubric nobody applies.

**Tiers.** `Critical`: any single FAIL → overall **FAIL**, regardless of the other tiers
(these are the ones that spend real money or touch a live vendor). `Standard`: ≥ 4/5.
`Hygiene`: ≥ 3/4.

### Critical (any FAIL → overall FAIL)

| # | Check | Pass criteria |
|---|-------|---------------|
| C1 | Opt-in by default | Gate off (`THIRDPARTY_INTEGRATION != 1`) → `t.Skip`; nothing runs unasked |
| C2 | Skip vs Fail | Gate on + a required var missing → `t.Fatalf`, never a silent skip (CI integrity) |
| C3 | Prod/host/account fail-closed + destructive gating | `requireVendorIntegration` (sandbox host on `VENDOR_SANDBOX_HOSTS`, account on `VENDOR_TEST_ACCOUNTS`); destructive via `assertVendorDestructiveSafe` / `assertVendorGRPCDestructiveSafe` with flag + idempotency key; forbidden against prod under **all** flags |
| C4 | No secrets leaked, cost bounded | No token/API key/raw customer-tenant-account ID in logs or fatals (`maskID`, `redactURL`, `unwrapURLErr`); real calls bounded by `VENDOR_MAX_CALLS` |

### Standard (≥ 4/5)

| # | Check | Pass criteria |
|---|-------|---------------|
| S1 | Real client, real call | Production config loader + real vendor client wiring; the response is asserted, not discarded |
| S2 | Bounded time, no cached green | `context.WithTimeout` on every call; the run command carries `-count=1` |
| S3 | Retry bounded and classified | Max 2 retries (3 attempts); `429` honors `Retry-After` and is classified `rate-limit`, never `contract` |
| S4 | Both assertion layers | Protocol contract **and** a business invariant; failure paths assert a specific code/type |
| S5 | gRPC specifics (or N/A) | `requireVendorGRPCIntegration`; assert `status.Code(err)`, not a string match; `defer conn.Close()`; per-RPC deadline |

### Hygiene (≥ 3/4)

| # | Check | Pass criteria |
|---|-------|---------------|
| H1 | Naming | `<client>_integration_test.go`; every test name carries the `Integration` marker the runner's PASS check looks for |
| H2 | Build-tag isolation | Both `//go:build integration` and `// +build integration` at file top |
| H3 | Data lifecycle stated | Setup source, idempotency-key strategy, cleanup or safe-reuse policy |
| H4 | Reproducible command | The exact `run_vendor_integration.sh` invocation (or equivalent) is given |

## Failure Triage Checklist

1. Classify failure: config, auth, network, timeout, contract, business assertion, rate-limit.
2. Provide minimal reproducible command.
3. Capture first vendor error with endpoint/method context.
4. Separate environment/setup issue from code regression.
5. Propose concrete fix and verification command.

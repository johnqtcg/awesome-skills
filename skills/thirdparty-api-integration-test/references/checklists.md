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

1. Test is opt-in and skipped by default (gate off → `t.Skip`).
2. Gate on + a required var missing → `t.Fatalf`, not a silent skip (CI integrity).
3. Uses production config loader and real vendor client wiring; makes a real call and asserts the response.
4. Every call uses context timeout; run command uses `-count=1` (no `(cached)` false-green).
5. Retry policy is bounded and explicit; `429` honors `Retry-After` and is classified `rate-limit`.
6. Asserts protocol contract and business invariants; error paths assert a specific code/type.
7. Destructive calls gated (HTTP via `assertVendorDestructiveSafe`, gRPC via `assertVendorGRPCDestructiveSafe`): `INTEGRATION_ALLOW_DESTRUCTIVE=1` + sandbox host/target + test account + idempotency key; forbidden against prod under all flags.
8. Never logs tokens/secrets or raw customer/tenant IDs (mask them); bounded call budget for paid APIs.
9. gRPC vendors: gate with `requireVendorGRPCIntegration`; assert `status.Code(err)` (not string match), `defer conn.Close()`, and a per-RPC `context.WithTimeout` deadline.

## Failure Triage Checklist

1. Classify failure: config, auth, network, timeout, contract, business assertion, rate-limit.
2. Provide minimal reproducible command.
3. Capture first vendor error with endpoint/method context.
4. Separate environment/setup issue from code regression.
5. Propose concrete fix and verification command.

# Third-Party API Integration Test Checklists

## Pre-Authoring Checklist

1. Confirm target vendor API/client method and ownership.
2. Confirm gate variable (`THIRDPARTY_INTEGRATION=1` or vendor-specific gate).
3. Confirm mandatory env vars and format validation.
4. Confirm production safety behavior (`ENV=prod` blocked unless `INTEGRATION_ALLOW_PROD=1`).
5. Confirm build-tag isolation (`//go:build integration`).
6. Confirm timeout and retry budget (max retries, backoff, retryable classes).
7. Confirm test data lifecycle (dedicated tenant/account, idempotency key, cleanup/reuse).
8. Confirm rate-limit and auth expectations for the vendor.

## Test Quality Checklist

1. Test is opt-in and skipped by default.
2. Missing env vars lead to actionable `t.Skip` message.
3. Uses production config loader and real vendor client wiring.
4. Every call uses context timeout.
5. Retry policy is bounded and explicit.
6. Asserts protocol contract and business invariants.
7. Avoids destructive calls unless explicitly gated.
8. Never logs tokens/secrets in output.

## Failure Triage Checklist

1. Classify failure: config, auth, network, timeout, contract, business assertion, rate-limit.
2. Provide minimal reproducible command.
3. Capture first vendor error with endpoint/method context.
4. Separate environment/setup issue from code regression.
5. Propose concrete fix and verification command.

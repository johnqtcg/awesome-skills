---
name: thirdparty-api-integration-test
description: Create and run gated Go integration tests for third-party APIs with real external calls, strict configuration gates, bounded timeouts, and safe runtime controls. Use for vendor/client contract verification and failure triage.
---

# Third Party API Integration Test

Write Go integration tests for real third-party API calls using explicit run gates, predictable safeguards, and strong contract assertions.

## Scope

- Validate external API integration end-to-end with real config and real client.
- Keep tests opt-in by default so normal CI/unit workflows are not blocked.
- Follow repository style: `testify/require`, clear skip conditions, bounded timeout.
- Apply to any third-party API integration.
- Treat vendor examples (MCS/USS/etc.) as templates, not scope limits.

## Scope Validation Gate

Confirm the task targets a third-party vendor API:
- Third-party HTTP or gRPC API client → proceed
- Internal service/handler (own HTTP server) → redirect to `$api-integration-test`, **STOP**
- Pure unit test → redirect to `$unit-test`, **STOP**
- Full end-to-end browser journey → out of scope, inform user, **STOP**

**Hard stop**: If the target is not a third-party vendor API, the entire remaining workflow is skipped. Output only: (1) scope verdict, (2) recommended skill or approach, (3) reason. Do NOT generate test code, do NOT proceed to subsequent gates.

## Required Pattern

1. Keep file name as `<client>_integration_test.go` in the same package directory.
2. Add **both** build constraints at file top (for backward compatibility):
   - `//go:build integration`  (Go 1.17+)
   - `// +build integration`   (Go <1.17 compat)
3. Add explicit run gate env var (example: `THIRDPARTY_INTEGRATION=1` or vendor-specific gate), otherwise `t.Skip(...)`.
4. Validate required runtime env vars up front (for example: `ENV`, `CONFIG_DIR`, target IDs/label IDs).
5. Block production by default:
   - if `ENV` resolves to `prod`/`production`, `t.Skip` unless `INTEGRATION_ALLOW_PROD=1`.
6. Parse and validate env var payloads:
   - Always `strings.TrimSpace` before comparison or use
   - Use `strconv.ParseInt` for numeric IDs
   - Split comma-separated lists and validate each element
   - Log parsed values at `t.Logf` level for debugging
7. Load runtime config via project config loader (`config.MustLoad()`).
8. Build real third-party client with production code path.
9. Use `context.WithTimeout(...)` to prevent hanging requests.
10. Use bounded retry policy only when justified:
   - default: no retry
   - if enabled: max 1-2 retries, bounded backoff, no infinite loop
11. Execute real API call and assert both:
   - protocol-level contract (status/code/required response fields)
   - business-level invariant (identifier consistency, semantic constraints)
12. For expected failure paths, assert explicit error type/code (not only `require.Error`).
13. Define test data lifecycle explicitly:
   - setup source, idempotency key strategy, cleanup or safe reuse policy.

## Configuration Gate (Mandatory)

Before generating or updating test code, apply the shared gate in:
- `references/common-integration-gate.md`

## Vendor-Specific Safety Additions

1. Prefer idempotent endpoints for default integration flows.
2. For mutation endpoints, require dedicated test tenant/account and explicit opt-in gate.
3. Keep retry policy bounded; avoid hidden infinite retries in tests.
4. Validate rate-limit behavior when relevant:
   - Assert rate-limit response headers when available (`X-RateLimit-Remaining`, `Retry-After`)
   - If test triggers rate-limit, classify failure as "rate-limit" not "contract"
5. Never log secrets/tokens in assertions or failure output.
6. Refuse production environment by default.

## Safety Rules

- Use dedicated test tenant/account identifiers only.
- Prefer idempotent or low-risk API operations.
- Never hardcode secrets/tokens in test source.
- Skip test when required env vars are missing instead of failing local pipelines.
- Keep timeout strict (for example 10-30s) and avoid unbounded retries.
- Refuse `ENV=prod` unless explicit override is provided.

## Execution

Use vendor-specific run commands documented in:
- `references/vendor-examples.md`

## Output Contract

Use the shared output contract in:
- `references/common-output-contract.md`

## References (Load Selectively)

1. **Always read**: `references/common-integration-gate.md` — gate design and skip message quality. _Shared with `$api-integration-test`._
2. **Always read**: `references/common-output-contract.md` — structured report format. _Shared with `$api-integration-test`._
3. **Read if authoring new tests or triaging failures**: `references/checklists.md`
4. **Read if no vendor pattern exists in the repo**: `references/vendor-examples.md` — generic template and run commands

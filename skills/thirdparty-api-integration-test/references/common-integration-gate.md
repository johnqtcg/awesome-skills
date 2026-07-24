# Third-Party Integration Configuration Gate

Apply this gate before generating or updating runnable third-party integration tests.
This is a **separate file** from `$api-integration-test`'s gate (parallel, same safety
bar, plus vendor-specific rules) — edits here do not propagate there.

## Mandatory Steps

1. Scan repository code and configuration to identify required runtime variables.
2. List each variable with purpose, expected format/type, and required-or-optional.
3. Include the run gate variable (`THIRDPARTY_INTEGRATION=1` or a vendor-specific gate).
4. Enforce production/live safety — validate the **resolved host and account**, not just `ENV`:
   - refuse if `ENV` is `prod`/`production`, OR the API base-URL host is not on the explicit
     sandbox allowlist `VENDOR_SANDBOX_HOSTS`, OR the vendor account is not on `VENDOR_TEST_ACCOUNTS`.
   - Fail **closed**: `url.Parse` accepts relative refs (`api.vendor.com` → empty scheme/host, no
     error), so require an **absolute `http(s)` URL with a non-empty host**; treat anything else,
     an empty/missing sandbox allowlist, or an unlisted account as production.
   - allow override only with explicit `INTEGRATION_ALLOW_PROD=1` (READ-only; never for writes).
   - when the run gate is enabled, this refusal is a hard failure (`t.Fatalf`), not a silent `t.Skip`.
   - **gRPC targets** are `host:port` / `dns:///host:port`, not http(s) URLs. Use
     `requireVendorGRPCIntegration` / `isProdGRPCTarget`, which extract and validate the host
     the same way, restrict the resolver scheme to `dns`/`passthrough`/none, and fail **closed**
     on an unknown resolver (`xds:///…`, where the literal host may not be the real endpoint).
5. Mutations require `INTEGRATION_ALLOW_DESTRUCTIVE=1`, a sandbox host, a test account, and an
   idempotency key; a destructive call against a prod/live target is forbidden under all flags.
6. Determine the degradation level (below) and proceed accordingly.
7. Never guess endpoints, credentials, or identifiers to make tests look runnable.
8. Never hardcode secrets, tokens, or private endpoints; never log tokens or raw customer/tenant IDs.
9. Require build-tag isolation: `//go:build integration`, run with `go test -tags=integration ... -count=1`.

## Degradation Levels

| Level | Condition | Action |
|-------|-----------|--------|
| **Full** | All env vars documented, sandbox host + test account known, gate var defined | Generate complete, runnable tests |
| **Scaffold** | Some env vars identified, some missing (e.g. unknown target ID) | Generate a test with `t.Skip(...)` + `// TODO:` markers for each missing value; state what is missing. **Scaffold skips are authoring-time-incomplete and MUST be excluded from the official CI gate** so they never false-green. |
| **Blocked** | Gate var unknown, base URL/sandbox host undetermined, or scope unclear | Do NOT generate runnable code. Output only: required-variable checklist, example command, setup instructions, and the reason for blocking. |

## Skip / Fatal Message Quality

Use the right one (skip = not requested / opt-in tier; fatal = gate on but broken/dangerous):

Skip examples:
- `set THIRDPARTY_INTEGRATION=1 to run`
- `destructive: set INTEGRATION_ALLOW_DESTRUCTIVE=1 to run`

Fatal examples (gate on but broken/dangerous — NOT a skip):
- `set ENV, CONFIG_DIR, <VENDOR>_BASE_URL, <VENDOR>_TEST_ACCOUNT to run`
- `refuse production/live vendor target: set INTEGRATION_ALLOW_PROD=1, or use a sandbox host on VENDOR_SANDBOX_HOSTS`
- `VENDOR_TEST_ACCOUNTS is required — list the exact test account IDs`

BAD messages (do not use): `missing configuration`, `test skipped`, `environment not set up`.

## Required Output In Every Run

Always include: required variable list; example export/run command block (with `-count=1`);
currently missing variables; degradation level applied; whether the prod-safety gate blocked execution.
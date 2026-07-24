---
name: thirdparty-api-integration-test
description: Create and run gated Go integration tests for third-party APIs with real external calls, strict configuration gates, bounded timeouts, and safe runtime controls. Use for vendor/client contract verification and failure triage.
disable-model-invocation: true
allowed-tools: Read, Write, Grep, Glob, Bash(go test*), Bash(go build*), Bash(go vet*), Bash(bash scripts/run_vendor_integration.sh*)
---

# Third Party API Integration Test

Write Go integration tests for real third-party API calls using explicit run gates, predictable safeguards, and strong contract assertions.

## Scope

- Validate external API integration end-to-end with real config and real client.
- Keep tests opt-in by default so normal CI/unit workflows are not blocked.
- Follow the host repository's existing style — its assertion library (`testify/require`,
  `testify/assert`, or stdlib `t.Fatalf`), its config loader, and its test-package convention.
  The examples below use `testify/require` and `config.MustLoad()` as one common shape; mirror
  what the repo already does rather than importing a new dependency. Clear skip conditions and a
  bounded timeout are required regardless.
- Apply to any third-party API integration.
- Treat vendor examples (MCS/USS/etc.) as templates, not scope limits.
- The NON-NEGOTIABLE parts are the safety gates (run gate, prod/host/account fail-closed checks,
  destructive gating, bounded budget, ID/URL redaction) — not the choice of assertion or config library.

## Scope Validation Gate

Confirm the task targets a third-party vendor API:
- Third-party HTTP or gRPC API client → proceed
- Internal service/handler (own HTTP server) → redirect to `$api-integration-test`, **STOP**
- Pure unit test → redirect to `$unit-test`, **STOP**
- Full end-to-end browser journey → out of scope, inform user, **STOP**

**Hard stop**: If the target is not a third-party vendor API, the entire remaining workflow is skipped. Output only: (1) scope verdict, (2) recommended skill or approach, (3) reason. Do NOT generate test code, do NOT proceed to subsequent gates.

## Required Pattern

1. Keep file name as `<client>_integration_test.go`, in the package the repo uses for tests
   (same package, or its `_test` external package — match the surrounding convention). **Name each
   integration test function with an `Integration` marker** (e.g. `TestStripe_CreateCharge_Integration`):
   the runner refuses to report success unless at least one `…Integration` test actually PASSED,
   which keeps a plain unit test from masquerading as a passed integration run (override the marker
   via `VENDOR_TEST_NAME_MATCH`).
2. Add **both** build constraints at file top (for backward compatibility):
   - `//go:build integration`  (Go 1.17+)
   - `// +build integration`   (Go <1.17 compat)
3. Add explicit run gate env var (example: `THIRDPARTY_INTEGRATION=1` or vendor-specific gate), otherwise `t.Skip(...)`.
4. Validate required runtime env vars up front (`ENV`, `CONFIG_DIR`, the API base URL, the vendor test account, target IDs). When the run gate is set but a required var is missing/empty, `t.Fatalf` — do NOT `t.Skip` (see §Skip vs Fail (CI Integrity)).
5. Block production/live vendor targets by ENV **and** by resolved host and account (never ENV alone):
   - refuse if `ENV` is `prod`/`production`, OR the base-URL host is not on the explicit sandbox allowlist (`VENDOR_SANDBOX_HOSTS`), OR the vendor account is not a designated test account (`VENDOR_TEST_ACCOUNTS`) — unless `INTEGRATION_ALLOW_PROD=1`. When the gate is set, this refusal is `t.Fatalf`, not `t.Skip`. Use `requireVendorIntegration` (§Go Implementation Baseline).
6. Parse and validate env var payloads:
   - Always `strings.TrimSpace` before comparison or use
   - Use `strconv.ParseInt` for numeric IDs
   - Split comma-separated lists and validate each element
   - Log only **non-sensitive** parsed values at `t.Logf`; **mask identifiers** with `maskID` and **never log secrets/tokens** (raw account/customer/tenant/target IDs are sensitive)
7. Load runtime config via the project's existing config loader (e.g. `config.MustLoad()` — use
   whatever the repo already uses; do not introduce a new config mechanism for the test).
8. Build real third-party client with production code path.
9. Use `context.WithTimeout(...)` to prevent hanging requests.
10. Use bounded retry policy only when justified:
   - default: no retry
   - if enabled: **max 2 retries (3 total attempts)**, bounded backoff, no infinite loop. Rate-limit (`429`/`Retry-After`) retries count toward this same budget — `getHonoringRateLimit` is called with `maxRetries=2`.
11. Execute real API call and assert both:
   - protocol-level contract (status/code/required response fields)
   - business-level invariant (identifier consistency, semantic constraints)
12. For expected failure paths, assert explicit error type/code (not only `require.Error`).
13. Define test data lifecycle explicitly:
   - setup source, idempotency key strategy, cleanup or safe reuse policy.

## Skip vs Fail (CI Integrity)

`t.Skip` on a *misconfigured* run is a false green: `go test` exits 0 when every test
skips, so a CI job that lost its config — or points at a live vendor — passes silently.

| Situation | Behavior |
|-----------|----------|
| Run gate unset (`THIRDPARTY_INTEGRATION != 1`) | `t.Skip` (not requested) |
| Gate set, a required var missing/empty | `t.Fatalf` |
| Gate set, target is prod/live (ENV, host not on `VENDOR_SANDBOX_HOSTS`, or non-test account) without `INTEGRATION_ALLOW_PROD=1` | `t.Fatalf` |
| Gate set, destructive op without `INTEGRATION_ALLOW_DESTRUCTIVE=1` | `t.Skip` (opt-in tier — keep in a separate CI job) |

Once `THIRDPARTY_INTEGRATION=1` is set, the only acceptable `t.Skip` is a destructive/scaffold
opt-in tier that the base gate does not depend on. Everything else becomes `t.Fatalf`.

An individual test calling `t.Skip` is fine, but a *whole run* in which **every** test skipped
verified nothing — `run_vendor_integration.sh` treats that (and a `-run` pattern matching nothing)
as a failure, not a green PASS. So point an all-destructive CI job at its own package/`-run` scope
and give it `INTEGRATION_ALLOW_DESTRUCTIVE=1`; a destructive job that skips everything is a
misconfiguration the runner surfaces.

## Go Implementation Baseline

The canonical prod/account/destructive safety helpers — `requireVendorIntegration`,
`assertTestAccount`, `isProdVendorTarget`, `assertVendorDestructiveSafe`, `maskID`, `redactURL`,
`unwrapURLErr`, `parseRetryAfter`, the `callBudget`/`budgetTransport` cost guards,
`getHonoringRateLimit`, and the gRPC counterparts `grpcTargetHost` / `isProdGRPCTarget` /
`redactGRPCTarget` / `requireVendorGRPCIntegration` / `assertVendorGRPCDestructiveSafe` — live in:
- `references/go-baseline.md`

Copy them into the test package as written. They fail CLOSED (a sandbox host must be on
`VENDOR_SANDBOX_HOSTS`; a test account must be on `VENDOR_TEST_ACCOUNTS`) and are kept
token-identical to the regression fixture, which is why they are a separate reference rather
than inlined here — do not paraphrase the safety logic.

`references/vendor-examples.md` shows a full test that calls a real endpoint through the
project's vendor client using these helpers plus a bounded call budget (`newVendorBudget`/
`spend`), real Retry-After handling (`getHonoringRateLimit`), and ID masking. gRPC vendors
use `isProdGRPCTarget` for the sandbox check.

## Configuration Gate (Mandatory)

Before generating or updating test code, apply the gate in:
- `references/common-integration-gate.md`

## Vendor-Specific Safety Additions (executable rules)

These are concrete, testable rules — not principles. A behavioral fixture exercises each.

1. **Sandbox host allowlist (fail closed).** A vendor target is non-prod only if its host is
   on `VENDOR_SANDBOX_HOSTS`. Unset or non-matching host → treated as production (refuse).
2. **Test account allowlist (fail closed).** `VENDOR_TEST_ACCOUNTS` is required; the account/
   project/tenant must be on it (`assertTestAccount`). A prod account like `acct_live_9` is refused.
3. **Production writes forbidden under ALL flags.** `INTEGRATION_ALLOW_PROD=1` permits READ-only
   prod tests, never writes. A destructive call against a prod/live target fails even with
   `ALLOW_PROD=1` + `ALLOW_DESTRUCTIVE=1` (`assertVendorDestructiveSafe`).
4. **Mutations require an idempotency key.** Destructive/write calls must pass a non-empty
   `Idempotency-Key` (also protects against duplicate charges on retry).
5. **Bounded call budget (cost control).** Cap real calls with `VENDOR_MAX_CALLS` (default 20);
   route every call through a budget that `t.Fatalf`s when exceeded — a runaway loop against a
   paid API must not silently rack up cost.
6. **Retry-After / 429 handling.** On `429`, honor the `Retry-After` header (do not hammer), and
   classify the failure as `rate-limit`, never `contract`. Assert `X-RateLimit-Remaining`/`Retry-After`
   when the vendor sends them.
7. **Mask sensitive IDs and secrets.** Never log tokens, API keys, or raw customer/tenant/account
   IDs. Mask IDs in `t.Logf`/assertions (e.g. `acct_1234` → `acct_…34`); redact `Authorization`.
8. **gRPC specifics** (when the vendor is gRPC): gate reads with `requireVendorGRPCIntegration`
   and writes with `assertVendorGRPCDestructiveSafe` (same rules as their HTTP counterparts).
   Assert `status.Code(err)` (not string matching), `defer conn.Close()`, and set a deadline via
   `context.WithTimeout` on every RPC. Map vendor codes to your domain errors at the boundary.
9. **Retry policy bounded and explicit.** Default no retry; if enabled, max 1-2 with bounded
   backoff, honoring `ctx.Done()` — no hidden infinite retries.

## Safety Rules

- Use dedicated test tenant/account identifiers only (validated against `VENDOR_TEST_ACCOUNTS`).
- Prefer idempotent or low-risk API operations.
- Never hardcode secrets/tokens in test source; never log tokens or raw customer/tenant IDs (mask them).
- **Skip vs Fail**: `t.Skip` only when the run gate is off (or for a destructive/scaffold opt-in tier). When the gate is set but a required var is missing, or the target is prod/non-sandbox, `t.Fatalf` — a silent skip false-greens CI. See §Skip vs Fail (CI Integrity).
- Keep timeout strict (for example 10-30s) and avoid unbounded retries.
- Refuse production/live targets (by ENV, host, and account) unless explicit override is provided.

## Execution

Use vendor-specific run commands documented in:
- `references/vendor-examples.md`

**Tool-permission note.** A strict `Bash(go test*)` allowlist matches only a command whose
FIRST token is `go test` — an inline env-prefixed form (`THIRDPARTY_INTEGRATION=1 … go test …`)
starts with the variable, not `go`. And **separate Bash invocations do not carry env vars
forward**, so an "`export` … then `go test`" recipe is unreliable under a strict tool runtime.
Use the single-invocation wrapper `scripts/run_vendor_integration.sh <env-file> <pkg>`
(allowlisted as `Bash(bash scripts/run_vendor_integration.sh*)`): it **parses** a gitignored env
file as `KEY=VALUE` data (it never `source`s it — sourcing would execute shell hidden in the
file), validates the gate/sandbox/account vars, refuses a prod target, and fixes
`-tags=integration -count=1 -timeout=<bounded> -p=<n> -parallel=<n> -v`. Extra args are limited to
a strict allowlist (`-run`/`-skip`/`-shuffle` + value, `-v`/`-race`/`-short`/`-failfast`), so
neither `-count`/`-timeout`/`-tags`/`-p`/`-parallel` nor their `-test.count`/`-test.timeout`
binary-flag forms, nor `-args`, can slip through; a package starting with `-` is refused; the
timeout is clamped to `[1s, 3600s]`; suite concurrency defaults to serial (`VENDOR_TEST_PARALLELISM`,
capped `[1,4]`, so a large fan-out can't exceed the per-test cost budget); and a green run is
reported as failure unless at least one test whose name contains the marker
(`VENDOR_TEST_NAME_MATCH`, default `Integration`) actually PASSED — so an all-skip run (e.g. a
destructive tier without `INTEGRATION_ALLOW_DESTRUCTIVE=1`) or a bad `-run` pattern never
false-greens.
**Run it from the target repository root** (so a relative package like `./internal/...` resolves
against that repo), invoking it by an absolute path to the installed skill. Calling it by
absolute path won't match the relative allowlist entry above — add one for the install path
(`Bash(bash /path/to/skill/scripts/run_vendor_integration.sh*)`). The regression suite under
`scripts/tests/` is maintainer tooling (`python3 -m unittest`), intentionally outside this
skill's runtime allowlist.

## Output Contract

Use the shared output contract in:
- `references/common-output-contract.md`

## References (Load Selectively)

1. **Always read**: `references/common-integration-gate.md` — gate design, resolved-host + account validation, degradation levels, skip-vs-fail. _Parallel to `$api-integration-test`'s gate (same safety bar, plus vendor rules) — it is a **separate file**, not shared; edits do not propagate between skills._
2. **Always read**: `references/common-output-contract.md` — structured report format. _Parallel to `$api-integration-test`'s — a separate file, not shared._
3. **Always read when writing test code**: `references/go-baseline.md` — the canonical Go safety helpers; copy them into the test package verbatim (kept token-identical to the regression fixture).
4. **Read if authoring new tests or triaging failures**: `references/checklists.md`
5. **Read if no vendor pattern exists in the repo**: `references/vendor-examples.md` — generic template and run commands

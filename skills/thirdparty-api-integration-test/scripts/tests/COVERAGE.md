# thirdparty-api-integration-test — Test Coverage

Three layers. Contract tests check the *docs* (SKILL.md + the extracted `references/go-baseline.md`);
behavioral tests compile and run a real Go fixture; the two are tied together by a full-body
helper comparison so the doc and the tested code cannot drift.

The Go safety helpers live in `references/go-baseline.md` (extracted from SKILL.md to keep it
lean); the contract suite reads SKILL.md and that baseline together.

## Contract Tests (`test_skill_contract.py`)

| Group | Validates |
|-------|-----------|
| `Frontmatter` | name, third-party description, allowed-tools, SKILL.md ≤ 500 lines |
| `SafetyRules` | Skip-vs-Fail documented; prod-host fail-closed (`IsAbs`/`Hostname`/scheme + `VENDOR_SANDBOX_HOSTS`); `VENDOR_TEST_ACCOUNTS` required; HTTP **and gRPC** destructive rules (flag, prod-forbidden, idempotency); cost budget; Retry-After/rate-limit; ID masking; gRPC specifics; the false "Shared with" claim is gone |
| `Commands` | every real run command carries `-count=1`; the runner itself fixes `-tags`/`-count`/`-timeout`/`-p`/`-parallel`/`-v`, restricts extra args to a strict allowlist (so `-test.count`/`-test.timeout`/`-args` can't slip in), refuses a `-`-leading package, parses (never `source`s) the env file, and reports a green run as failure unless a marker-matching (`Integration`) test actually PASSED |
| `GateParity` | the (separate) gate carries resolved-host + account validation, Full/Scaffold/Blocked, skip-vs-fatal; output-contract has the `(cached)`/skip≠pass CI-integrity rules |
| `HelperConsistency` | the 17 safety helpers **and** the 2 receiver methods (`callBudget.spend`, `budgetTransport.RoundTrip`) have **identical full normalized bodies** across SKILL.md + `go-baseline.md` and the fixture; comment stripping AND brace counting are string-aware (a `://` or `{`/`}` inside a Go string is not mistaken for a comment or a boundary); every doc call-site arity matches the definition |
| `CoverageDoc` | the counts stated in *this file* are derived from the source (`def test_` count, `len(HELPERS)`) and asserted, so a stale number is a test failure — not silent drift |

## Behavioral Tests (`test_behavioral_integration.py`)

Compiles a real Go fixture and runs it under many env configs, asserting ACTUAL behavior:

- gate: unset→skip; missing base URL→fail; missing account→fail; prod ENV→fail; bare host
  (scheme-less, not absolute)→fail; no sandbox allowlist→fail; host-off-allowlist→fail; no
  account allowlist→fail; account-off-list→fail; prod READ override (`INTEGRATION_ALLOW_PROD=1`)→pass;
  valid sandbox→pass. (Each is an independent test — see the same-named `test_*` methods.)
- destructive (HTTP): no flag→skip; missing idempotency→fail; prod target + both flags→fail; valid→pass.
- destructive (gRPC): `assertVendorGRPCDestructiveSafe` mirrors the HTTP gate — no flag→skip;
  missing idempotency→fail; prod target + both flags→fail; valid sandbox→pass.
- cost budget: exceeding `VENDOR_MAX_CALLS`→fail; within→pass.
- masking / redaction: an off-list account fatal masks the raw account; a prod-URL fatal redacts
  the URL; a **failed request** and a **failed request-build** inside `getHonoringRateLimit` (both
  yield a `*url.Error` whose string embeds the full URL) are unwrapped via `unwrapURLErr` so a
  token in the query never leaks.
- real Retry-After: `parseRetryAfter` handles seconds/HTTP-date/empty/negative and **clamps a
  huge value to 24h** (a raw `secs * time.Second` would overflow int64 to a negative near-immediate
  retry); a transient 429 is retried (attempts prove the honor loop ran) and succeeds; a
  **persistent 429 FAILS (classified rate-limit), never skips** — spending the call budget each attempt.
- cost budget: exceeding `VENDOR_MAX_CALLS`→fail; within→pass; and the budget is spent inside
  `getHonoringRateLimit` (the doc example's call chain, guarded cross-file).
- gRPC gate (closed): `requireVendorGRPCIntegration` mirrors the HTTP gate for gRPC targets —
  unset→skip; missing target/account, prod ENV, host off the sandbox allowlist, or an unknown
  resolver (`xds:///…`, fail-closed) → fail; valid sandbox target → pass. `grpcTargetHost`
  restricts the resolver scheme to `dns`/`passthrough`/none.
- budget at the TRANSPORT: `budgetTransport` counts every real request (incl. a client's
  internal retries) and errors past `VENDOR_MAX_CALLS` — so a client-path call can't bypass
  the cost cap.
- retry unification: `getHonoringRateLimit` is called with `maxRetries=2` in the example and
  fixture, matching the "max 2 retries (3 attempts)" rule.
- real HTTP: contract (status+body), bounded retry (3×), context timeout→`DeadlineExceeded`.
- `-count=1` cache proof: a plain re-run prints `(cached)`; `-count=1` forces execution.
- runner (`run_vendor_integration.sh`, bash-only, no `go` needed): a missing required var exits
  non-zero; env-file code (`X=$(touch …)`) is **not executed** (parsed as data, never `source`d);
  extra args are allowlisted, so `-count`/`-tags`/`-p`/`-parallel`, their `-test.count`/
  `-test.timeout` forms, and `-args` are all refused; a `-`-leading package is refused;
  `VENDOR_TEST_TIMEOUT` is clamped to `[1s, 3600s]` (both `0s` and `999999h` refused);
  `VENDOR_TEST_PARALLELISM` is capped to `[1,4]`. A fake `go` on PATH proves (a) valid input execs
  exactly `test -tags=integration -count=1 -timeout=300s -p=1 -parallel=1 -v <pkg> <extras>`;
  (b) a run where every test **SKIPs** is a failure; and (c) a run where only a **non-marker**
  (unit) test passes is a failure — only a passing `…Integration` test counts (anti-false-green).

The 17 safety helpers (incl. `maskID`/`redactURL`/`unwrapURLErr`/`parseRetryAfter`/
`getHonoringRateLimit`/`grpcTargetHost`/`isProdGRPCTarget`/`requireVendorGRPCIntegration`/
`assertVendorGRPCDestructiveSafe`) plus the 2 receiver methods (`callBudget.spend`,
`budgetTransport.RoundTrip`) are kept token-identical to `references/go-baseline.md`; the contract
suite compares their **full normalized bodies** and checks every doc call-site arity.

Skips (never fails) only on environment limits: no `go`, no writable temp dir, or a sandbox
that denies opening a local socket — 5 tests bind an `httptest` server and 1 dials a refused
port for the URL-redaction check. Drops inherited `GOROOT`. The 16 runner tests need only `bash`.

## Combined Total

**93 runnable test methods** = 38 contract + 55 behavioral (up to 6 of the behavioral open a
local socket and skip under a sandbox that denies it; the runner tests need only bash).

## Known Gaps

1. No live LLM skill-output eval — the behavioral suite proves the *prescribed* helpers
   work, not that a model emits them (the helper-body + arity guards keep the doc and the
   tested code in lock-step, which is the main risk this addresses).
2. gRPC coverage: the gRPC *gate* **and the gRPC destructive gate** are now closed and
   behaviorally tested (`requireVendorGRPCIntegration` skip/fail/pass, xds fail-closed, scheme
   allowlist; `assertVendorGRPCDestructiveSafe` skip/valid/no-idempotency/prod-forbidden). What
   remains a gap is a **live gRPC-server** fixture for the *runtime* specifics (status-code
   assertion, per-RPC deadline, `conn.Close()`). That is an **intentional** gap: a real gRPC
   fixture pulls the out-of-tree `google.golang.org/grpc` + protoc toolchain, which the offline
   test harness (it drops `GOROOT` and has no module-proxy network) cannot fetch — a fixture that
   always skips would add maintenance with zero signal. Those specifics stay as a concrete,
   copy-pasteable example in `vendor-examples.md` + the checklist instead.

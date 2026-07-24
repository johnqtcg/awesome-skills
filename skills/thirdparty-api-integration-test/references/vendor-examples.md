# Vendor Integration Test Template

Generic template for third-party API integration tests. Replace `<VENDOR>` placeholders
with your vendor (e.g. `STRIPE`, `GITHUB`, `OPENAI`). It uses the safety helpers defined
in SKILL.md §Go Implementation Baseline (`requireVendorIntegration`, `assertVendorDestructiveSafe`,
`newVendorBudget`/`spend`, `getHonoringRateLimit`, `maskID`, `redactURL`; for gRPC vendors
`requireVendorGRPCIntegration` and `assertVendorGRPCDestructiveSafe`) — keep those in
the same package.

## Read test — through the project's real vendor client

Prefer the repo's production client so the test exercises auth, serialization, error
mapping, and middleware — not just raw HTTP.

```go
//go:build integration
// +build integration

func Test<VENDOR>_GetResource_Integration(t *testing.T) {
    baseURL := strings.TrimSpace(os.Getenv("<VENDOR>_BASE_URL"))
    account := strings.TrimSpace(os.Getenv("<VENDOR>_TEST_ACCOUNT"))
    requireVendorIntegration(t, baseURL, account) // gate off->skip; missing/prod/non-sandbox/non-test-account->fatal
    t.Logf("<VENDOR> account: %s", maskID(account)) // masked, never raw

    cfg := config.MustLoad()
    // Budget at the TRANSPORT so every real request — including the client's internal
    // retries — is counted against VENDOR_MAX_CALLS. No client call can bypass the cost cap.
    httpClient := &http.Client{Transport: newBudgetTransport(t, nil), Timeout: 15 * time.Second}
    client, err := vendor.NewClient(cfg.<VENDOR>Service, vendor.WithHTTPClient(httpClient))
    require.NoError(t, err)

    ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
    defer cancel()

    res, err := client.GetResource(ctx, "123")
    require.NoError(t, err)
    require.Equal(t, "123", res.ID)   // business invariant via the mapped type
    require.NotEmpty(t, res.Status)   // protocol/contract via the client

    // Expected-failure path: assert the client's mapped error, not just require.Error.
    _, err = client.GetResource(ctx, "does-not-exist")
    require.ErrorIs(t, err, vendor.ErrNotFound)
}
```

## Raw-HTTP variant — Retry-After + cost budget

When you must call the endpoint directly (no client yet, or to control rate-limit / cost),
use `getHonoringRateLimit`, which spends the call budget and honors `Retry-After`. A
persistent `429` is a real failure (classified rate-limit), **never** a `t.Skip` — a skip
after the gate is on would false-green CI.

```go
func Test<VENDOR>_Raw_Integration(t *testing.T) {
    baseURL := strings.TrimSpace(os.Getenv("<VENDOR>_BASE_URL"))
    account := strings.TrimSpace(os.Getenv("<VENDOR>_TEST_ACCOUNT"))
    requireVendorIntegration(t, baseURL, account)

    ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
    defer cancel()
    budget := newVendorBudget(t) // caps real calls via VENDOR_MAX_CALLS (cost guard)

    resp := getHonoringRateLimit(t, ctx, budget, baseURL+"/v1/resources/123", 2, 5*time.Second) // max 2 retries (§Required Pattern)
    defer resp.Body.Close()
    require.Equal(t, http.StatusOK, resp.StatusCode)
    body, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
    require.NoError(t, err)
    var out struct{ ID string `json:"id"` }
    require.NoError(t, json.Unmarshal(body, &out))
    require.Equal(t, "123", out.ID)
}
```

## Mutation test — destructive + gated

```go
func Test<VENDOR>_CreateResource_Integration(t *testing.T) {
    baseURL := strings.TrimSpace(os.Getenv("<VENDOR>_BASE_URL"))
    account := strings.TrimSpace(os.Getenv("<VENDOR>_TEST_ACCOUNT"))
    requireVendorIntegration(t, baseURL, account)
    env := strings.ToLower(strings.TrimSpace(os.Getenv("ENV")))
    idemKey := "test-" + account + "-create-123"
    // skips unless INTEGRATION_ALLOW_DESTRUCTIVE=1; requires sandbox host + test account +
    // idempotency key; fatals on any prod/live target even with INTEGRATION_ALLOW_PROD=1.
    assertVendorDestructiveSafe(t, env, baseURL, account, idemKey)

    ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
    defer cancel()
    budget := newVendorBudget(t)
    budget.spend(t)
    req, err := http.NewRequestWithContext(ctx, http.MethodPost, baseURL+"/v1/resources", nil)
    require.NoError(t, err)
    req.Header.Set("Idempotency-Key", idemKey) // dedupes duplicate charges on retry
    resp, err := http.DefaultClient.Do(req)
    require.NoError(t, err)
    defer resp.Body.Close()
    require.Equal(t, http.StatusCreated, resp.StatusCode)
}
```

## gRPC mutation test — destructive + gated (runtime specifics)

gRPC targets are `host:443` / `dns:///host:443`, not http(s) URLs, so use the gRPC gate helpers.
This example shows the three runtime specifics the checklist calls for: `status.Code(err)` (never
a string match), `defer conn.Close()`, and a per-RPC deadline via `context.WithTimeout`.

```go
func Test<VENDOR>_gRPC_CreateResource_Integration(t *testing.T) {
    target := strings.TrimSpace(os.Getenv("<VENDOR>_GRPC_TARGET")) // host:443 or dns:///host:443
    account := strings.TrimSpace(os.Getenv("<VENDOR>_TEST_ACCOUNT"))
    requireVendorGRPCIntegration(t, target, account) // gate off->skip; prod/non-sandbox/unknown-resolver->fatal
    env := strings.ToLower(strings.TrimSpace(os.Getenv("ENV")))
    idemKey := "test-" + account + "-create-123"
    // Same destructive gate as HTTP: skips unless INTEGRATION_ALLOW_DESTRUCTIVE=1; requires sandbox
    // target + test account + idempotency key; fatals on any prod/live target even with ALLOW_PROD=1.
    assertVendorGRPCDestructiveSafe(t, env, target, account, idemKey)

    conn, err := grpc.NewClient(target, grpc.WithTransportCredentials(
        credentials.NewTLS(&tls.Config{MinVersion: tls.VersionTLS12})))
    require.NoError(t, err)
    defer conn.Close() // always release the connection

    client := vendorpb.NewResourceServiceClient(conn)
    ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second) // per-RPC deadline
    defer cancel()
    ctx = metadata.AppendToOutgoingContext(ctx, "idempotency-key", idemKey) // dedupe duplicate writes on retry

    res, err := client.CreateResource(ctx, &vendorpb.CreateResourceRequest{Id: "123"})
    require.NoError(t, err)
    require.Equal(t, "123", res.GetId())

    // Expected-failure path: assert the gRPC status CODE, never a string match.
    _, err = client.CreateResource(ctx, &vendorpb.CreateResourceRequest{Id: ""})
    require.Equal(t, codes.InvalidArgument, status.Code(err))
}
```

> This gRPC snippet is documentation, not part of the compiled regression fixture: a real gRPC
> test pulls `google.golang.org/grpc` + a protoc toolchain, which the offline test harness cannot
> fetch. The gRPC *gates* (`requireVendorGRPCIntegration`, `assertVendorGRPCDestructiveSafe`) ARE
> compiled and behaviorally tested; only these runtime specifics live as doc + checklist.

## Run Commands

Run via the controlled wrapper `scripts/run_vendor_integration.sh` — a **single invocation**
(separate Bash calls don't carry env vars forward, and an inline `FOO=1 go test …` doesn't
match a strict `Bash(go test*)` allowlist). It **parses** a gitignored env file as `KEY=VALUE`
data (it never `source`s it — sourcing would execute shell hidden in the file), validates the
gate/sandbox/account vars, refuses a prod target, and fixes `-tags=integration -count=1
-timeout=<bounded> -p=<n> -parallel=<n> -v`. Set the timeout via `VENDOR_TEST_TIMEOUT` in the env
file (clamped to `[1s, 3600s]`), NOT as a `-timeout` arg. Suite concurrency defaults to serial;
raise it (small cap) via `VENDOR_TEST_PARALLELISM` — `-p`/`-parallel` are fixed, not caller args,
so a big fan-out can't blow past the per-test cost budget. Extra args are limited to a strict
allowlist (`-run`/`-skip`/`-shuffle`, `-v`/`-race`/`-short`/`-failfast`) — `-count`/`-timeout`/`-tags`/
`-p`/`-parallel`, their `-test.*` forms, and `-args` are all refused. A green run is reported as a
FAILURE unless a test whose name contains `VENDOR_TEST_NAME_MATCH` (default `Integration`) actually
PASSED, so an all-skip run or a bad `-run` pattern never false-greens.
**Run from the target repository root** (so `./internal/...` resolves against that repo) and call
the wrapper by an absolute path to the installed skill.

```bash
# .env.integration (gitignored — never commit tokens): KEY=VALUE lines
#   THIRDPARTY_INTEGRATION=1
#   ENV=dev
#   <VENDOR>_BASE_URL=https://sandbox.vendor.example
#   VENDOR_SANDBOX_HOSTS=sandbox.vendor.example
#   <VENDOR>_TEST_ACCOUNT=acct_test_1
#   VENDOR_TEST_ACCOUNTS=acct_test_1
#   <VENDOR>_TOKEN=sk_test_xxx
#   VENDOR_MAX_CALLS=50
#   VENDOR_TEST_TIMEOUT=120s
#   VENDOR_TEST_PARALLELISM=1     # default serial; raise within [1,4] only if calls are cheap

# From the target repo root, using the skill's absolute path. Read tests (sandbox):
bash /path/to/skill/scripts/run_vendor_integration.sh .env.integration ./internal/pkg/thirdparty/<vendor> \
  -run Integration -v

# Destructive tests (separate CI job) — add INTEGRATION_ALLOW_DESTRUCTIVE=1, a tight
# VENDOR_MAX_CALLS, and e.g. VENDOR_TEST_TIMEOUT=300s to the env file, then:
bash /path/to/skill/scripts/run_vendor_integration.sh .env.integration.destructive ./internal/pkg/thirdparty/<vendor> \
  -run Integration -v
```

## Adapting the Template

1. Replace `<VENDOR>` / `<vendor>` (uppercase for env vars, lowercase for package path).
2. Add vendor-specific env vars (API keys, region); keep the required set validated up front.
3. **gRPC vendors**: gRPC targets are `host:443` / `dns:///host:443`, not http(s) URLs. Use
   `requireVendorGRPCIntegration(t, target, account)` (NOT the HTTP `requireVendorIntegration`) —
   it applies the same gate/account/skip-vs-fail rules with the gRPC prod check, and fails
   closed on unknown resolvers (`xds:///…`). For writes, gate with `assertVendorGRPCDestructiveSafe`
   (the gRPC counterpart of `assertVendorDestructiveSafe`). Assert `status.Code(err)`,
   `defer conn.Close()`, and set a per-RPC deadline via `context.WithTimeout` — see the gRPC
   mutation example above.
4. For paid APIs, keep tests read-only by default, use the cheapest tier, and cap calls with
   `VENDOR_MAX_CALLS`.
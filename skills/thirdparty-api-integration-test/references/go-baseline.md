# Go Implementation Baseline

The canonical prod/account/destructive safety helpers for third-party integration tests. Keep
them in the test package. Fail CLOSED: a vendor sandbox must be listed explicitly
(`VENDOR_SANDBOX_HOSTS`), and a test-account allowlist (`VENDOR_TEST_ACCOUNTS`) is mandatory.

These are the safety contract, not a style preference — mirror the host repo's assertion library
and config loader elsewhere, but keep these gates as written. The regression fixture under
`scripts/tests/` carries a token-identical copy; the contract suite compares full normalized
bodies so the doc and the tested code cannot drift.

```go
//go:build integration
// +build integration

// isProdVendorTarget refuses production/live vendor targets, FAILING CLOSED.
// url.Parse accepts relative refs ("api.vendor.com" → empty scheme/host, no error),
// so require an absolute http(s) URL with a non-empty host whose host is on the
// explicit sandbox allowlist; anything else (or no allowlist) is treated as prod.
func isProdVendorTarget(env, rawURL string) bool {
    if env == "prod" || env == "production" {
        return true
    }
    u, err := url.Parse(rawURL)
    if err != nil || !u.IsAbs() || (u.Scheme != "http" && u.Scheme != "https") || u.Hostname() == "" {
        return true
    }
    allow := strings.TrimSpace(os.Getenv("VENDOR_SANDBOX_HOSTS"))
    if allow == "" {
        return true
    }
    host := strings.ToLower(u.Hostname())
    for _, h := range strings.Split(allow, ",") {
        if host == strings.ToLower(strings.TrimSpace(h)) {
            return false
        }
    }
    return true
}

// assertTestAccount refuses a non-test vendor account/project/tenant. VENDOR_TEST_ACCOUNTS
// is REQUIRED (fail closed): unset → refuse; an account not on the list → refuse.
func assertTestAccount(t *testing.T, account string) {
    t.Helper()
    allow := strings.TrimSpace(os.Getenv("VENDOR_TEST_ACCOUNTS"))
    if allow == "" {
        t.Fatalf("VENDOR_TEST_ACCOUNTS is required: list the exact test account/project IDs permitted")
    }
    for _, id := range strings.Split(allow, ",") {
        if account == strings.TrimSpace(id) {
            return
        }
    }
    t.Fatalf("vendor account %s not in VENDOR_TEST_ACCOUNTS — refuse", maskID(account))
}

// requireVendorIntegration: gate off → skip; gate on + broken/dangerous → fatal.
func requireVendorIntegration(t *testing.T, baseURL, account string) {
    t.Helper()
    if os.Getenv("THIRDPARTY_INTEGRATION") != "1" {
        t.Skip("set THIRDPARTY_INTEGRATION=1 to run")
    }
    if strings.TrimSpace(baseURL) == "" || strings.TrimSpace(account) == "" {
        t.Fatalf("integration enabled but config incomplete: need API base URL and vendor account")
    }
    env := strings.ToLower(strings.TrimSpace(os.Getenv("ENV")))
    if isProdVendorTarget(env, baseURL) && os.Getenv("INTEGRATION_ALLOW_PROD") != "1" {
        t.Fatalf("refuse production/live vendor target (env=%q url=%s): set INTEGRATION_ALLOW_PROD=1 to override, or use a sandbox endpoint on VENDOR_SANDBOX_HOSTS", env, redactURL(baseURL))
    }
    assertTestAccount(t, account)
}

// assertVendorDestructiveSafe gates mutations. A destructive/write call is NEVER allowed
// against a production/live vendor target under ANY flag (INTEGRATION_ALLOW_PROD permits
// READ-only prod tests, not writes). Requires the destructive flag, a sandbox host, a
// validated test account, and an idempotency key.
func assertVendorDestructiveSafe(t *testing.T, env, baseURL, account, idempotencyKey string) {
    t.Helper()
    if os.Getenv("INTEGRATION_ALLOW_DESTRUCTIVE") != "1" {
        t.Skip("destructive: set INTEGRATION_ALLOW_DESTRUCTIVE=1 to run")
    }
    if isProdVendorTarget(env, baseURL) {
        t.Fatalf("destructive vendor calls are forbidden against a production/live target, even with INTEGRATION_ALLOW_PROD=1")
    }
    assertTestAccount(t, account)
    if strings.TrimSpace(idempotencyKey) == "" {
        t.Fatalf("destructive vendor calls require an idempotency key")
    }
}

// maskID masks a sensitive identifier for logs (never log a raw account/customer/tenant ID).
func maskID(id string) string {
    if len(id) <= 4 {
        return "***"
    }
    return id[:2] + "***" + id[len(id)-2:]
}

// redactURL keeps only scheme://host, dropping userinfo, path, and query — which can carry
// tokens or sensitive IDs — so a fatal message never leaks them.
func redactURL(rawURL string) string {
    u, err := url.Parse(rawURL)
    if err != nil || u.Hostname() == "" {
        return "***"
    }
    return u.Scheme + "://" + u.Hostname()
}

// unwrapURLErr strips a *url.Error wrapper, whose Error() embeds the full URL (path + query,
// which may carry a token); pair it with redactURL so a fatal shows only the safe host + cause.
func unwrapURLErr(err error) error {
    var uerr *url.Error
    if errors.As(err, &uerr) {
        return uerr.Err
    }
    return err
}

// parseRetryAfter parses a Retry-After header (delay-seconds or HTTP-date) into a wait.
func parseRetryAfter(h string) (time.Duration, bool) {
    h = strings.TrimSpace(h)
    if h == "" {
        return 0, false
    }
    if secs, err := strconv.Atoi(h); err == nil {
        if secs < 0 {
            return 0, false
        }
        if secs > 86400 { // clamp to 24h — a huge vendor value would overflow int64 on *time.Second (→ negative → near-immediate retry)
            secs = 86400
        }
        return time.Duration(secs) * time.Second, true
    }
    if ts, err := http.ParseTime(h); err == nil {
        d := time.Until(ts)
        if d < 0 {
            d = 0
        }
        return d, true
    }
    return 0, false
}

// vendorMaxCalls reads the cost cap (VENDOR_MAX_CALLS, default 20).
func vendorMaxCalls(t *testing.T) int {
    t.Helper()
    max := 20
    if v := strings.TrimSpace(os.Getenv("VENDOR_MAX_CALLS")); v != "" {
        n, err := strconv.Atoi(v)
        if err != nil || n <= 0 {
            t.Fatalf("VENDOR_MAX_CALLS must be a positive integer, got %q", v)
        }
        max = n
    }
    return max
}

// callBudget bounds real vendor calls in a raw-HTTP loop (explicit spend()).
type callBudget struct{ max, used int }

func newVendorBudget(t *testing.T) *callBudget {
    t.Helper()
    return &callBudget{max: vendorMaxCalls(t)}
}

func (b *callBudget) spend(t *testing.T) {
    t.Helper()
    b.used++
    if b.used > b.max {
        t.Fatalf("vendor call budget exceeded: %d > %d (cost guard)", b.used, b.max)
    }
}

// budgetTransport counts EVERY actual HTTP request (including a vendor client's internal
// retries) and errors once the cost cap is exceeded — wire it into the client's http.Client
// so no real call can bypass the budget. Returning an error (not t.Fatalf) is deliberate:
// RoundTrip may run off the test goroutine, and the client surfaces the error to the caller.
type budgetTransport struct {
    base http.RoundTripper
    max  int
    n    int32
}

func newBudgetTransport(t *testing.T, base http.RoundTripper) *budgetTransport {
    t.Helper()
    if base == nil {
        base = http.DefaultTransport
    }
    return &budgetTransport{base: base, max: vendorMaxCalls(t)}
}

func (bt *budgetTransport) RoundTrip(req *http.Request) (*http.Response, error) {
    if int(atomic.AddInt32(&bt.n, 1)) > bt.max {
        return nil, fmt.Errorf("vendor call budget exceeded: > %d (cost guard)", bt.max)
    }
    return bt.base.RoundTrip(req)
}

// getHonoringRateLimit does a GET and, on 429, waits per Retry-After (capped) and retries up
// to maxRetries. A persistent 429 is a real failure (classified rate-limit), NEVER a skip —
// a silent skip after the gate is on false-greens CI. Every call spends the budget. Both error
// paths unwrap the *url.Error (whose string embeds the full URL) and log only the redacted host.
func getHonoringRateLimit(t *testing.T, ctx context.Context, budget *callBudget, rawURL string, maxRetries int, cap time.Duration) *http.Response {
    t.Helper()
    for attempt := 0; ; attempt++ {
        budget.spend(t)
        req, err := http.NewRequestWithContext(ctx, http.MethodGet, rawURL, nil)
        if err != nil {
            t.Fatalf("build request for %s failed: %v", redactURL(rawURL), unwrapURLErr(err))
        }
        resp, err := http.DefaultClient.Do(req)
        if err != nil {
            t.Fatalf("request to %s failed: %v", redactURL(rawURL), unwrapURLErr(err))
        }
        if resp.StatusCode != http.StatusTooManyRequests {
            return resp
        }
        wait, ok := parseRetryAfter(resp.Header.Get("Retry-After"))
        resp.Body.Close()
        if attempt >= maxRetries {
            t.Fatalf("rate-limit: still 429 after %d retries — classified rate-limit, not a skip", maxRetries)
        }
        if !ok || wait > cap {
            wait = cap
        }
        select {
        case <-ctx.Done():
            t.Fatalf("ctx cancelled while honoring Retry-After: %v", ctx.Err())
        case <-time.After(wait):
        }
    }
}

// grpcTargetHost extracts the host from a gRPC target ("host:443", "dns:///host:443",
// "dns://authority/host:443", "passthrough:///host:443"), for sandbox-allowlist checks —
// gRPC targets are host:port, NOT http(s) URLs, so isProdVendorTarget would reject them.
func grpcTargetHost(target string) (string, bool) {
    target = strings.TrimSpace(target)
    scheme, rest := "", target
    if i := strings.Index(target, "://"); i >= 0 {
        scheme = strings.ToLower(target[:i])
        rest = target[i+3:]
        if j := strings.Index(rest, "/"); j >= 0 {
            rest = rest[j+1:]
        }
    }
    switch scheme {
    case "", "dns", "passthrough":
    default:
        return "", false
    }
    if h, _, err := net.SplitHostPort(rest); err == nil {
        return h, true
    }
    if rest == "" {
        return "", false
    }
    return rest, true
}

// isProdGRPCTarget is the gRPC counterpart of isProdVendorTarget (host:port, not a URL).
// An unknown resolver scheme (e.g. xds:///…) fails CLOSED — the literal host may not be
// the real endpoint.
func isProdGRPCTarget(env, target string) bool {
    if env == "prod" || env == "production" {
        return true
    }
    host, ok := grpcTargetHost(target)
    if !ok || host == "" {
        return true
    }
    allow := strings.TrimSpace(os.Getenv("VENDOR_SANDBOX_HOSTS"))
    if allow == "" {
        return true
    }
    host = strings.ToLower(host)
    for _, h := range strings.Split(allow, ",") {
        if host == strings.ToLower(strings.TrimSpace(h)) {
            return false
        }
    }
    return true
}

// redactGRPCTarget returns only the (non-sensitive) host of a gRPC target for logs.
func redactGRPCTarget(target string) string {
    if h, ok := grpcTargetHost(target); ok && h != "" {
        return h
    }
    return "***"
}

// requireVendorGRPCIntegration is requireVendorIntegration for gRPC targets — same gate,
// account allowlist, and skip-vs-fail rules, using the gRPC (host:port) prod check.
func requireVendorGRPCIntegration(t *testing.T, target, account string) {
    t.Helper()
    if os.Getenv("THIRDPARTY_INTEGRATION") != "1" {
        t.Skip("set THIRDPARTY_INTEGRATION=1 to run")
    }
    if strings.TrimSpace(target) == "" || strings.TrimSpace(account) == "" {
        t.Fatalf("integration enabled but config incomplete: need gRPC target and vendor account")
    }
    env := strings.ToLower(strings.TrimSpace(os.Getenv("ENV")))
    if isProdGRPCTarget(env, target) && os.Getenv("INTEGRATION_ALLOW_PROD") != "1" {
        t.Fatalf("refuse production/live gRPC target (env=%q host=%s): set INTEGRATION_ALLOW_PROD=1 to override, or use a sandbox host on VENDOR_SANDBOX_HOSTS", env, redactGRPCTarget(target))
    }
    assertTestAccount(t, account)
}

// assertVendorGRPCDestructiveSafe gates gRPC mutations — the gRPC counterpart of
// assertVendorDestructiveSafe. A destructive/write RPC is NEVER allowed against a
// production/live target under ANY flag; requires the destructive flag, a sandbox
// target, a validated test account, and an idempotency key.
func assertVendorGRPCDestructiveSafe(t *testing.T, env, target, account, idempotencyKey string) {
    t.Helper()
    if os.Getenv("INTEGRATION_ALLOW_DESTRUCTIVE") != "1" {
        t.Skip("destructive: set INTEGRATION_ALLOW_DESTRUCTIVE=1 to run")
    }
    if isProdGRPCTarget(env, target) {
        t.Fatalf("destructive gRPC calls are forbidden against a production/live target, even with INTEGRATION_ALLOW_PROD=1")
    }
    assertTestAccount(t, account)
    if strings.TrimSpace(idempotencyKey) == "" {
        t.Fatalf("destructive gRPC calls require an idempotency key")
    }
}
```

## Imports

The helpers use only the standard library:

```go
import (
    "context"
    "errors"
    "fmt"
    "net"
    "net/http"
    "net/url"
    "os"
    "strconv"
    "strings"
    "sync/atomic"
    "testing"
    "time"
)
```

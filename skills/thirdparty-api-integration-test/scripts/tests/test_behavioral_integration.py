"""Behavioral tests for the thirdparty-api-integration-test skill.

Compiles a real Go fixture implementing the gate / prod-safety / account / destructive
/ cost-budget / Retry-After / masking / gRPC logic the skill prescribes, and runs it under
many env configs, asserting the ACTUAL behavior. The safety helpers are kept token-identical
to SKILL.md §Go Implementation Baseline; test_skill_contract.py compares their full normalized
bodies. Skips (never fails) only on environment limits.
"""

import os
import shlex
import shutil
import subprocess
import tempfile
import textwrap
import unittest

GO = shutil.which("go")

_GO_MOD = "module sut\n\ngo 1.22\n"

_FIXTURE = textwrap.dedent(
    """\
    //go:build integration

    package sut

    import (
    \t"context"
    \t"encoding/json"
    \t"errors"
    \t"fmt"
    \t"io"
    \t"net"
    \t"net/http"
    \t"net/http/httptest"
    \t"net/url"
    \t"os"
    \t"strconv"
    \t"strings"
    \t"sync/atomic"
    \t"testing"
    \t"time"
    )

    func isProdVendorTarget(env, rawURL string) bool {
    \tif env == "prod" || env == "production" {
    \t\treturn true
    \t}
    \tu, err := url.Parse(rawURL)
    \tif err != nil || !u.IsAbs() || (u.Scheme != "http" && u.Scheme != "https") || u.Hostname() == "" {
    \t\treturn true
    \t}
    \tallow := strings.TrimSpace(os.Getenv("VENDOR_SANDBOX_HOSTS"))
    \tif allow == "" {
    \t\treturn true
    \t}
    \thost := strings.ToLower(u.Hostname())
    \tfor _, h := range strings.Split(allow, ",") {
    \t\tif host == strings.ToLower(strings.TrimSpace(h)) {
    \t\t\treturn false
    \t\t}
    \t}
    \treturn true
    }

    func assertTestAccount(t *testing.T, account string) {
    \tt.Helper()
    \tallow := strings.TrimSpace(os.Getenv("VENDOR_TEST_ACCOUNTS"))
    \tif allow == "" {
    \t\tt.Fatalf("VENDOR_TEST_ACCOUNTS is required: list the exact test account/project IDs permitted")
    \t}
    \tfor _, id := range strings.Split(allow, ",") {
    \t\tif account == strings.TrimSpace(id) {
    \t\t\treturn
    \t\t}
    \t}
    \tt.Fatalf("vendor account %s not in VENDOR_TEST_ACCOUNTS — refuse", maskID(account))
    }

    func requireVendorIntegration(t *testing.T, baseURL, account string) {
    \tt.Helper()
    \tif os.Getenv("THIRDPARTY_INTEGRATION") != "1" {
    \t\tt.Skip("set THIRDPARTY_INTEGRATION=1 to run")
    \t}
    \tif strings.TrimSpace(baseURL) == "" || strings.TrimSpace(account) == "" {
    \t\tt.Fatalf("integration enabled but config incomplete: need API base URL and vendor account")
    \t}
    \tenv := strings.ToLower(strings.TrimSpace(os.Getenv("ENV")))
    \tif isProdVendorTarget(env, baseURL) && os.Getenv("INTEGRATION_ALLOW_PROD") != "1" {
    \t\tt.Fatalf("refuse production/live vendor target (env=%q url=%s): set INTEGRATION_ALLOW_PROD=1 to override, or use a sandbox endpoint on VENDOR_SANDBOX_HOSTS", env, redactURL(baseURL))
    \t}
    \tassertTestAccount(t, account)
    }

    func assertVendorDestructiveSafe(t *testing.T, env, baseURL, account, idempotencyKey string) {
    \tt.Helper()
    \tif os.Getenv("INTEGRATION_ALLOW_DESTRUCTIVE") != "1" {
    \t\tt.Skip("destructive: set INTEGRATION_ALLOW_DESTRUCTIVE=1 to run")
    \t}
    \tif isProdVendorTarget(env, baseURL) {
    \t\tt.Fatalf("destructive vendor calls are forbidden against a production/live target, even with INTEGRATION_ALLOW_PROD=1")
    \t}
    \tassertTestAccount(t, account)
    \tif strings.TrimSpace(idempotencyKey) == "" {
    \t\tt.Fatalf("destructive vendor calls require an idempotency key")
    \t}
    }

    func maskID(id string) string {
    \tif len(id) <= 4 {
    \t\treturn "***"
    \t}
    \treturn id[:2] + "***" + id[len(id)-2:]
    }

    func redactURL(rawURL string) string {
    \tu, err := url.Parse(rawURL)
    \tif err != nil || u.Hostname() == "" {
    \t\treturn "***"
    \t}
    \treturn u.Scheme + "://" + u.Hostname()
    }

    func unwrapURLErr(err error) error {
    \tvar uerr *url.Error
    \tif errors.As(err, &uerr) {
    \t\treturn uerr.Err
    \t}
    \treturn err
    }

    func parseRetryAfter(h string) (time.Duration, bool) {
    \th = strings.TrimSpace(h)
    \tif h == "" {
    \t\treturn 0, false
    \t}
    \tif secs, err := strconv.Atoi(h); err == nil {
    \t\tif secs < 0 {
    \t\t\treturn 0, false
    \t\t}
    \t\tif secs > 86400 { // clamp to 24h — a huge vendor value would overflow int64 on *time.Second (→ negative → near-immediate retry)
    \t\t\tsecs = 86400
    \t\t}
    \t\treturn time.Duration(secs) * time.Second, true
    \t}
    \tif ts, err := http.ParseTime(h); err == nil {
    \t\td := time.Until(ts)
    \t\tif d < 0 {
    \t\t\td = 0
    \t\t}
    \t\treturn d, true
    \t}
    \treturn 0, false
    }

    func vendorMaxCalls(t *testing.T) int {
    \tt.Helper()
    \tmax := 20
    \tif v := strings.TrimSpace(os.Getenv("VENDOR_MAX_CALLS")); v != "" {
    \t\tn, err := strconv.Atoi(v)
    \t\tif err != nil || n <= 0 {
    \t\t\tt.Fatalf("VENDOR_MAX_CALLS must be a positive integer, got %q", v)
    \t\t}
    \t\tmax = n
    \t}
    \treturn max
    }

    type callBudget struct{ max, used int }

    func newVendorBudget(t *testing.T) *callBudget {
    \tt.Helper()
    \treturn &callBudget{max: vendorMaxCalls(t)}
    }

    func (b *callBudget) spend(t *testing.T) {
    \tt.Helper()
    \tb.used++
    \tif b.used > b.max {
    \t\tt.Fatalf("vendor call budget exceeded: %d > %d (cost guard)", b.used, b.max)
    \t}
    }

    type budgetTransport struct {
    \tbase http.RoundTripper
    \tmax  int
    \tn    int32
    }

    func newBudgetTransport(t *testing.T, base http.RoundTripper) *budgetTransport {
    \tt.Helper()
    \tif base == nil {
    \t\tbase = http.DefaultTransport
    \t}
    \treturn &budgetTransport{base: base, max: vendorMaxCalls(t)}
    }

    func (bt *budgetTransport) RoundTrip(req *http.Request) (*http.Response, error) {
    \tif int(atomic.AddInt32(&bt.n, 1)) > bt.max {
    \t\treturn nil, fmt.Errorf("vendor call budget exceeded: > %d (cost guard)", bt.max)
    \t}
    \treturn bt.base.RoundTrip(req)
    }

    func getHonoringRateLimit(t *testing.T, ctx context.Context, budget *callBudget, rawURL string, maxRetries int, cap time.Duration) *http.Response {
    \tt.Helper()
    \tfor attempt := 0; ; attempt++ {
    \t\tbudget.spend(t)
    \t\treq, err := http.NewRequestWithContext(ctx, http.MethodGet, rawURL, nil)
    \t\tif err != nil {
    \t\t\tt.Fatalf("build request for %s failed: %v", redactURL(rawURL), unwrapURLErr(err))
    \t\t}
    \t\tresp, err := http.DefaultClient.Do(req)
    \t\tif err != nil {
    \t\t\tt.Fatalf("request to %s failed: %v", redactURL(rawURL), unwrapURLErr(err))
    \t\t}
    \t\tif resp.StatusCode != http.StatusTooManyRequests {
    \t\t\treturn resp
    \t\t}
    \t\twait, ok := parseRetryAfter(resp.Header.Get("Retry-After"))
    \t\tresp.Body.Close()
    \t\tif attempt >= maxRetries {
    \t\t\tt.Fatalf("rate-limit: still 429 after %d retries — classified rate-limit, not a skip", maxRetries)
    \t\t}
    \t\tif !ok || wait > cap {
    \t\t\twait = cap
    \t\t}
    \t\tselect {
    \t\tcase <-ctx.Done():
    \t\t\tt.Fatalf("ctx cancelled while honoring Retry-After: %v", ctx.Err())
    \t\tcase <-time.After(wait):
    \t\t}
    \t}
    }

    func grpcTargetHost(target string) (string, bool) {
    \ttarget = strings.TrimSpace(target)
    \tscheme, rest := "", target
    \tif i := strings.Index(target, "://"); i >= 0 {
    \t\tscheme = strings.ToLower(target[:i])
    \t\trest = target[i+3:]
    \t\tif j := strings.Index(rest, "/"); j >= 0 {
    \t\t\trest = rest[j+1:]
    \t\t}
    \t}
    \tswitch scheme {
    \tcase "", "dns", "passthrough":
    \tdefault:
    \t\treturn "", false
    \t}
    \tif h, _, err := net.SplitHostPort(rest); err == nil {
    \t\treturn h, true
    \t}
    \tif rest == "" {
    \t\treturn "", false
    \t}
    \treturn rest, true
    }

    func isProdGRPCTarget(env, target string) bool {
    \tif env == "prod" || env == "production" {
    \t\treturn true
    \t}
    \thost, ok := grpcTargetHost(target)
    \tif !ok || host == "" {
    \t\treturn true
    \t}
    \tallow := strings.TrimSpace(os.Getenv("VENDOR_SANDBOX_HOSTS"))
    \tif allow == "" {
    \t\treturn true
    \t}
    \thost = strings.ToLower(host)
    \tfor _, h := range strings.Split(allow, ",") {
    \t\tif host == strings.ToLower(strings.TrimSpace(h)) {
    \t\t\treturn false
    \t\t}
    \t}
    \treturn true
    }

    func redactGRPCTarget(target string) string {
    \tif h, ok := grpcTargetHost(target); ok && h != "" {
    \t\treturn h
    \t}
    \treturn "***"
    }

    func requireVendorGRPCIntegration(t *testing.T, target, account string) {
    \tt.Helper()
    \tif os.Getenv("THIRDPARTY_INTEGRATION") != "1" {
    \t\tt.Skip("set THIRDPARTY_INTEGRATION=1 to run")
    \t}
    \tif strings.TrimSpace(target) == "" || strings.TrimSpace(account) == "" {
    \t\tt.Fatalf("integration enabled but config incomplete: need gRPC target and vendor account")
    \t}
    \tenv := strings.ToLower(strings.TrimSpace(os.Getenv("ENV")))
    \tif isProdGRPCTarget(env, target) && os.Getenv("INTEGRATION_ALLOW_PROD") != "1" {
    \t\tt.Fatalf("refuse production/live gRPC target (env=%q host=%s): set INTEGRATION_ALLOW_PROD=1 to override, or use a sandbox host on VENDOR_SANDBOX_HOSTS", env, redactGRPCTarget(target))
    \t}
    \tassertTestAccount(t, account)
    }

    func assertVendorGRPCDestructiveSafe(t *testing.T, env, target, account, idempotencyKey string) {
    \tt.Helper()
    \tif os.Getenv("INTEGRATION_ALLOW_DESTRUCTIVE") != "1" {
    \t\tt.Skip("destructive: set INTEGRATION_ALLOW_DESTRUCTIVE=1 to run")
    \t}
    \tif isProdGRPCTarget(env, target) {
    \t\tt.Fatalf("destructive gRPC calls are forbidden against a production/live target, even with INTEGRATION_ALLOW_PROD=1")
    \t}
    \tassertTestAccount(t, account)
    \tif strings.TrimSpace(idempotencyKey) == "" {
    \t\tt.Fatalf("destructive gRPC calls require an idempotency key")
    \t}
    }

    func gateVars() (string, string) {
    \treturn strings.TrimSpace(os.Getenv("VENDOR_BASE_URL")), strings.TrimSpace(os.Getenv("VENDOR_ACCOUNT"))
    }

    func TestGate_Integration(t *testing.T) {
    \tbaseURL, account := gateVars()
    \trequireVendorIntegration(t, baseURL, account)
    }

    func TestGRPCGate_Integration(t *testing.T) {
    \ttarget := strings.TrimSpace(os.Getenv("VENDOR_GRPC_TARGET"))
    \t_, account := gateVars()
    \trequireVendorGRPCIntegration(t, target, account)
    }

    func TestGRPCDestructiveGate_Integration(t *testing.T) {
    \ttarget := strings.TrimSpace(os.Getenv("VENDOR_GRPC_TARGET"))
    \t_, account := gateVars()
    \trequireVendorGRPCIntegration(t, target, account)
    \tenv := strings.ToLower(strings.TrimSpace(os.Getenv("ENV")))
    \tassertVendorGRPCDestructiveSafe(t, env, target, account, strings.TrimSpace(os.Getenv("VENDOR_IDEM_KEY")))
    }

    func TestCacheProof_Integration(t *testing.T) {
    \tif os.Getenv("THIRDPARTY_INTEGRATION") != "1" {
    \t\tt.Skip("set THIRDPARTY_INTEGRATION=1 to run")
    \t}
    \tif 2+2 != 4 {
    \t\tt.Fatal("math broke")
    \t}
    }

    func TestDestructiveGate_Integration(t *testing.T) {
    \tbaseURL, account := gateVars()
    \trequireVendorIntegration(t, baseURL, account)
    \tenv := strings.ToLower(strings.TrimSpace(os.Getenv("ENV")))
    \tassertVendorDestructiveSafe(t, env, baseURL, account, strings.TrimSpace(os.Getenv("VENDOR_IDEM_KEY")))
    }

    func TestCostBudget_Integration(t *testing.T) {
    \tif os.Getenv("THIRDPARTY_INTEGRATION") != "1" {
    \t\tt.Skip("set THIRDPARTY_INTEGRATION=1 to run")
    \t}
    \tb := newVendorBudget(t)
    \tfor i := 0; i < 3; i++ {
    \t\tb.spend(t)
    \t}
    }

    func TestParseRetryAfter_Integration(t *testing.T) {
    \tif os.Getenv("THIRDPARTY_INTEGRATION") != "1" {
    \t\tt.Skip("set THIRDPARTY_INTEGRATION=1 to run")
    \t}
    \tif d, ok := parseRetryAfter("5"); !ok || d != 5*time.Second {
    \t\tt.Fatalf("parseRetryAfter(5) = %v,%v want 5s,true", d, ok)
    \t}
    \tif _, ok := parseRetryAfter(""); ok {
    \t\tt.Fatalf("parseRetryAfter(empty) should be false")
    \t}
    \tif _, ok := parseRetryAfter("-1"); ok {
    \t\tt.Fatalf("parseRetryAfter(-1) should be false")
    \t}
    \tfuture := time.Now().Add(3 * time.Second).UTC().Format(http.TimeFormat)
    \tif d, ok := parseRetryAfter(future); !ok || d <= 0 {
    \t\tt.Fatalf("parseRetryAfter(http-date) = %v,%v want >0,true", d, ok)
    \t}
    \tif d, ok := parseRetryAfter("100000"); !ok || d != 24*time.Hour {
    \t\tt.Fatalf("parseRetryAfter(100000) = %v,%v want 24h,true (clamped)", d, ok)
    \t}
    \tif d, ok := parseRetryAfter("99999999999999"); !ok || d != 24*time.Hour {
    \t\tt.Fatalf("parseRetryAfter(overflow) = %v,%v want 24h,true (no int64 overflow to negative)", d, ok)
    \t}
    }

    func TestMaskAndRedact_Integration(t *testing.T) {
    \tif os.Getenv("THIRDPARTY_INTEGRATION") != "1" {
    \t\tt.Skip("set THIRDPARTY_INTEGRATION=1 to run")
    \t}
    \tif got := maskID("acct_secret_zz"); got != "ac***zz" || strings.Contains(got, "secret") {
    \t\tt.Fatalf("maskID leaked: %q", got)
    \t}
    \tif got := redactURL("https://user:pw@api.vendor.example/secret/path?token=SUPERSECRET"); got != "https://api.vendor.example" {
    \t\tt.Fatalf("redactURL = %q, want scheme://host only", got)
    \t}
    }

    func TestGRPCTarget_Integration(t *testing.T) {
    \tif os.Getenv("THIRDPARTY_INTEGRATION") != "1" {
    \t\tt.Skip("set THIRDPARTY_INTEGRATION=1 to run")
    \t}
    \tok := map[string]string{
    \t\t"sb.vendor.example:443":                  "sb.vendor.example",
    \t\t"dns:///sb.vendor.example:443":           "sb.vendor.example",
    \t\t"dns://authority/sb.vendor.example:443":  "sb.vendor.example",
    \t\t"passthrough:///sb.vendor.example:443":   "sb.vendor.example",
    \t}
    \tfor target, want := range ok {
    \t\tif h, valid := grpcTargetHost(target); !valid || h != want {
    \t\t\tt.Fatalf("grpcTargetHost(%q) = %q,%v want %q,true", target, h, valid, want)
    \t\t}
    \t}
    \tif _, valid := grpcTargetHost("xds:///sb.vendor.example:443"); valid {
    \t\tt.Fatalf("xds resolver must fail closed (valid=false)")
    \t}
    \tt.Setenv("VENDOR_SANDBOX_HOSTS", "sb.vendor.example")
    \tif isProdGRPCTarget("dev", "dns:///sb.vendor.example:443") {
    \t\tt.Fatalf("sandbox gRPC target should not be prod")
    \t}
    \tif !isProdGRPCTarget("dev", "grpc.production.example:443") {
    \t\tt.Fatalf("non-sandbox gRPC target should be prod")
    \t}
    \tif !isProdGRPCTarget("dev", "xds:///sb.vendor.example:443") {
    \t\tt.Fatalf("xds gRPC target should be prod (fail closed)")
    \t}
    }

    func TestBudgetTransport_Integration(t *testing.T) {
    \tsrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
    \t\tw.WriteHeader(http.StatusOK)
    \t}))
    \tdefer srv.Close()
    \tif os.Getenv("THIRDPARTY_INTEGRATION") != "1" {
    \t\tt.Skip("set THIRDPARTY_INTEGRATION=1 to run")
    \t}
    \tclient := &http.Client{Transport: newBudgetTransport(t, nil)} // VENDOR_MAX_CALLS caps it
    \tvar lastErr error
    \tfor i := 0; i < 3; i++ {
    \t\treq, _ := http.NewRequest(http.MethodGet, srv.URL, nil)
    \t\tresp, err := client.Do(req)
    \t\tif err != nil {
    \t\t\tlastErr = err
    \t\t\tbreak
    \t\t}
    \t\tresp.Body.Close()
    \t}
    \tif lastErr == nil || !strings.Contains(lastErr.Error(), "budget exceeded") {
    \t\tt.Fatalf("budgetTransport did not enforce the cap; lastErr=%v", lastErr)
    \t}
    }

    func TestContract_Integration(t *testing.T) {
    \tsrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
    \t\tw.Header().Set("Content-Type", "application/json")
    \t\tw.WriteHeader(http.StatusOK)
    \t\t_, _ = w.Write([]byte(`{"id":"123","status":"ok"}`))
    \t}))
    \tdefer srv.Close()
    \t_, account := gateVars()
    \trequireVendorIntegration(t, srv.URL, account)

    \tctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    \tdefer cancel()
    \tbudget := newVendorBudget(t)
    \tresp := getHonoringRateLimit(t, ctx, budget, srv.URL+"/v1/resources/123", 2, time.Second)
    \tdefer resp.Body.Close()
    \tif resp.StatusCode != http.StatusOK {
    \t\tt.Fatalf("status = %d, want 200", resp.StatusCode)
    \t}
    \tbody, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
    \tvar out struct {
    \t\tID     string `json:"id"`
    \t\tStatus string `json:"status"`
    \t}
    \tif err := json.Unmarshal(body, &out); err != nil {
    \t\tt.Fatalf("decode: %v", err)
    \t}
    \tif out.ID != "123" || out.Status == "" {
    \t\tt.Fatalf("bad body: %+v", out)
    \t}
    }

    func TestRateLimitTransient_Integration(t *testing.T) {
    \tvar attempts int32
    \tsrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
    \t\tif atomic.AddInt32(&attempts, 1) < 3 {
    \t\t\tw.Header().Set("Retry-After", "0")
    \t\t\tw.WriteHeader(http.StatusTooManyRequests)
    \t\t\treturn
    \t\t}
    \t\tw.WriteHeader(http.StatusOK)
    \t}))
    \tdefer srv.Close()
    \t_, account := gateVars()
    \trequireVendorIntegration(t, srv.URL, account)

    \tctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    \tdefer cancel()
    \tbudget := newVendorBudget(t)
    \tresp := getHonoringRateLimit(t, ctx, budget, srv.URL, 2, 50*time.Millisecond)
    \tdefer resp.Body.Close()
    \tif resp.StatusCode != http.StatusOK {
    \t\tt.Fatalf("status = %d, want 200 after honoring Retry-After", resp.StatusCode)
    \t}
    \tif got := atomic.LoadInt32(&attempts); got != 3 {
    \t\tt.Fatalf("attempts = %d, want 3 (retry loop must have honored Retry-After)", got)
    \t}
    }

    func TestRateLimitPersistent_Integration(t *testing.T) {
    \tsrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
    \t\tw.Header().Set("Retry-After", "0")
    \t\tw.WriteHeader(http.StatusTooManyRequests)
    \t}))
    \tdefer srv.Close()
    \t_, account := gateVars()
    \trequireVendorIntegration(t, srv.URL, account)

    \tctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    \tdefer cancel()
    \tbudget := newVendorBudget(t)
    \tresp := getHonoringRateLimit(t, ctx, budget, srv.URL, 2, 10*time.Millisecond)
    \tresp.Body.Close() // unreachable: persistent 429 must t.Fatalf (not skip)
    }

    func TestRateLimitURLRedaction_Integration(t *testing.T) {
    \tif os.Getenv("THIRDPARTY_INTEGRATION") != "1" {
    \t\tt.Skip("set THIRDPARTY_INTEGRATION=1 to run")
    \t}
    \tctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
    \tdefer cancel()
    \tbudget := newVendorBudget(t)
    \t// port 1 refuses fast; the URL carries a token in the query that must NOT leak into the fatal.
    \tresp := getHonoringRateLimit(t, ctx, budget, "http://127.0.0.1:1/v1/x?token=SUPERSECRET", 0, time.Second)
    \tresp.Body.Close() // unreachable: the dial fails and getHonoringRateLimit t.Fatalf's first
    }

    func TestBuildRequestURLRedaction_Integration(t *testing.T) {
    \tif os.Getenv("THIRDPARTY_INTEGRATION") != "1" {
    \t\tt.Skip("set THIRDPARTY_INTEGRATION=1 to run")
    \t}
    \tctx, cancel := context.WithTimeout(context.Background(), time.Second)
    \tdefer cancel()
    \tbudget := newVendorBudget(t)
    \t// an unterminated IPv6 bracket makes NewRequestWithContext fail at parse (no network); the
    \t// query token must NOT leak — unwrapURLErr drops the *url.Error's full-URL string.
    \tresp := getHonoringRateLimit(t, ctx, budget, "http://[::1?token=SUPERSECRET", 0, time.Second)
    \tresp.Body.Close() // unreachable: the build fails and getHonoringRateLimit t.Fatalf's first
    }

    func TestTimeout_Integration(t *testing.T) {
    \tsrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
    \t\ttime.Sleep(200 * time.Millisecond)
    \t\tw.WriteHeader(http.StatusOK)
    \t}))
    \tdefer srv.Close()
    \t_, account := gateVars()
    \trequireVendorIntegration(t, srv.URL, account)

    \tctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
    \tdefer cancel()
    \treq, _ := http.NewRequestWithContext(ctx, http.MethodGet, srv.URL, nil)
    \t_, err := http.DefaultClient.Do(req)
    \tif err == nil {
    \t\tt.Fatalf("expected a timeout error, got nil")
    \t}
    \tif !errors.Is(err, context.DeadlineExceeded) {
    \t\tt.Fatalf("expected context.DeadlineExceeded, got %v", err)
    \t}
    }
    """
)

_PREFLIGHT = {"go.mod": "module pf\n\ngo 1.22\n", "m.go": "package main\n\nfunc main() {}\n"}


def _go_env(root: str) -> dict:
    env = dict(os.environ)
    env.pop("GOROOT", None)
    env["GOTOOLCHAIN"] = "local"
    env["GOCACHE"] = os.path.join(root, ".gocache")
    env["GOMODCACHE"] = os.path.join(root, ".gomod")
    env["GOPATH"] = os.path.join(root, ".gopath")
    return env


@unittest.skipIf(GO is None, "go toolchain not installed")
class BehavioralIntegrationTests(unittest.TestCase):
    def _module(self, files: dict) -> str:
        try:
            root = tempfile.mkdtemp(prefix="tp-eval-")
        except OSError as exc:
            self.skipTest(f"cannot create temp dir: {exc}")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        for name, content in files.items():
            path = os.path.join(root, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
        return root

    def _preflight(self):
        root = self._module(dict(_PREFLIGHT))
        if self._run(root, {}, "build", tags=False).returncode != 0:
            self.skipTest("go cannot compile in this environment")

    def _run(self, root, env_extra, subcmd="test", test=None, tags=True, extra=()):
        args = [GO, subcmd]
        if tags:
            args.append("-tags=integration")
        if subcmd == "test":
            args += ["-v"]
            if test:
                args += ["-run", test]
            args += list(extra)
        args += ["./..."]
        env = _go_env(root)
        env.update(env_extra)
        try:
            return subprocess.run(args, cwd=root, env=env, capture_output=True,
                                  text=True, timeout=180)
        except OSError as exc:
            self.skipTest(f"cannot exec go: {exc}")

    def _fixture(self) -> str:
        return self._module({"go.mod": _GO_MOD, "integration_test.go": _FIXTURE})

    def _assert(self, res, kind, ctx=""):
        out = res.stdout + res.stderr
        if ("httptest: failed to listen" in out or "bind: operation not permitted" in out
                or "socket: operation not permitted" in out
                or "connect: operation not permitted" in out):
            self.skipTest(f"{ctx}: environment denies opening a local socket (sandbox)")
        if kind == "skip":
            self.assertEqual(res.returncode, 0, f"{ctx}: expected skip\n{out}")
            self.assertIn("--- SKIP", out, f"{ctx}: expected SKIP\n{out}")
        elif kind == "fail":
            self.assertNotEqual(res.returncode, 0, f"{ctx}: expected FAIL\n{out}")
            self.assertIn("--- FAIL", out, f"{ctx}: expected FAIL\n{out}")
        elif kind == "pass":
            self.assertEqual(res.returncode, 0, f"{ctx}: expected PASS\n{out}")
            self.assertIn("--- PASS", out, f"{ctx}: expected PASS\n{out}")
        return out

    _VALID = {"THIRDPARTY_INTEGRATION": "1", "ENV": "dev",
              "VENDOR_BASE_URL": "http://127.0.0.1:8080", "VENDOR_SANDBOX_HOSTS": "127.0.0.1",
              "VENDOR_ACCOUNT": "acct_test_1", "VENDOR_TEST_ACCOUNTS": "acct_test_1,acct_test_2"}
    _DESTRUCTIVE = {"INTEGRATION_ALLOW_DESTRUCTIVE": "1", "VENDOR_IDEM_KEY": "test-key-1"}

    # ---- HTTP gate ----

    def test_gate_unset_skips(self):
        self._preflight()
        self._assert(self._run(self._fixture(), {}, test="TestGate_Integration"), "skip", "gate unset")

    def test_gate_on_missing_baseurl_fails(self):
        self._preflight()
        env = dict(self._VALID); env["VENDOR_BASE_URL"] = ""
        self._assert(self._run(self._fixture(), env, test="TestGate_Integration"), "fail", "no base URL")

    def test_gate_on_missing_account_fails(self):
        self._preflight()
        env = dict(self._VALID); env["VENDOR_ACCOUNT"] = ""
        self._assert(self._run(self._fixture(), env, test="TestGate_Integration"), "fail", "no account")

    def test_bare_host_fails(self):
        # a scheme-less host ("api.vendor.com") is not an absolute URL → treated as prod (fail closed).
        self._preflight()
        env = dict(self._VALID); env["VENDOR_BASE_URL"] = "api.vendor.com"
        self._assert(self._run(self._fixture(), env, test="TestGate_Integration"), "fail", "bare host")

    def test_prod_read_override_passes(self):
        # ENV=prod is allowed for READ tests when INTEGRATION_ALLOW_PROD=1 (account still validated).
        self._preflight()
        env = dict(self._VALID); env["ENV"] = "prod"; env["INTEGRATION_ALLOW_PROD"] = "1"
        self._assert(self._run(self._fixture(), env, test="TestGate_Integration"), "pass", "prod read override")

    def test_prod_env_fails(self):
        self._preflight()
        env = dict(self._VALID); env["ENV"] = "prod"
        self._assert(self._run(self._fixture(), env, test="TestGate_Integration"), "fail", "prod env")

    def test_no_sandbox_allowlist_fails(self):
        self._preflight()
        env = dict(self._VALID); env.pop("VENDOR_SANDBOX_HOSTS")
        self._assert(self._run(self._fixture(), env, test="TestGate_Integration"), "fail", "no sandbox allowlist")

    def test_no_account_allowlist_fails(self):
        self._preflight()
        env = dict(self._VALID); env.pop("VENDOR_TEST_ACCOUNTS")
        self._assert(self._run(self._fixture(), env, test="TestGate_Integration"), "fail", "no account allowlist")

    def test_valid_sandbox_passes(self):
        self._preflight()
        self._assert(self._run(self._fixture(), dict(self._VALID), test="TestGate_Integration"), "pass", "valid sandbox")

    # ---- #3 gRPC gate (mirrors HTTP gate) ----

    _GRPC = {"THIRDPARTY_INTEGRATION": "1", "ENV": "dev", "VENDOR_SANDBOX_HOSTS": "sb.vendor.example",
             "VENDOR_GRPC_TARGET": "dns:///sb.vendor.example:443",
             "VENDOR_ACCOUNT": "acct_test_1", "VENDOR_TEST_ACCOUNTS": "acct_test_1"}

    def test_grpc_gate_unset_skips(self):
        self._preflight()
        self._assert(self._run(self._fixture(), {}, test="TestGRPCGate_Integration"), "skip", "grpc gate unset")

    def test_grpc_gate_missing_target_fails(self):
        self._preflight()
        env = dict(self._GRPC); env["VENDOR_GRPC_TARGET"] = ""
        self._assert(self._run(self._fixture(), env, test="TestGRPCGate_Integration"), "fail", "grpc no target")

    def test_grpc_gate_missing_account_fails(self):
        self._preflight()
        env = dict(self._GRPC); env["VENDOR_ACCOUNT"] = ""
        self._assert(self._run(self._fixture(), env, test="TestGRPCGate_Integration"), "fail", "grpc no account")

    def test_grpc_gate_prod_env_fails(self):
        self._preflight()
        env = dict(self._GRPC); env["ENV"] = "prod"
        self._assert(self._run(self._fixture(), env, test="TestGRPCGate_Integration"), "fail", "grpc prod env")

    def test_grpc_gate_xds_scheme_fails_closed(self):
        self._preflight()
        env = dict(self._GRPC); env["VENDOR_GRPC_TARGET"] = "xds:///sb.vendor.example:443"
        self._assert(self._run(self._fixture(), env, test="TestGRPCGate_Integration"), "fail", "grpc xds fail-closed")

    def test_grpc_gate_host_off_sandbox_fails(self):
        self._preflight()
        env = dict(self._GRPC); env["VENDOR_GRPC_TARGET"] = "dns:///grpc.production.example:443"
        self._assert(self._run(self._fixture(), env, test="TestGRPCGate_Integration"), "fail", "grpc host off sandbox")

    def test_grpc_gate_valid_passes(self):
        self._preflight()
        self._assert(self._run(self._fixture(), dict(self._GRPC), test="TestGRPCGate_Integration"), "pass", "grpc valid")

    # ---- #1 gRPC destructive gate (mirrors HTTP destructive gate) ----

    def test_grpc_destructive_without_flag_skips(self):
        self._preflight()
        self._assert(self._run(self._fixture(), dict(self._GRPC), test="TestGRPCDestructiveGate_Integration"), "skip", "grpc destructive no flag")

    def test_grpc_destructive_valid_passes(self):
        self._preflight()
        env = dict(self._GRPC); env.update(self._DESTRUCTIVE)
        self._assert(self._run(self._fixture(), env, test="TestGRPCDestructiveGate_Integration"), "pass", "grpc destructive valid")

    def test_grpc_destructive_without_idempotency_fails(self):
        self._preflight()
        env = dict(self._GRPC); env.update(self._DESTRUCTIVE); env["VENDOR_IDEM_KEY"] = ""
        self._assert(self._run(self._fixture(), env, test="TestGRPCDestructiveGate_Integration"), "fail", "grpc destructive no idempotency")

    def test_grpc_destructive_on_prod_forbidden(self):
        self._preflight()
        env = dict(self._GRPC); env.update(self._DESTRUCTIVE); env["ENV"] = "prod"; env["INTEGRATION_ALLOW_PROD"] = "1"
        self._assert(self._run(self._fixture(), env, test="TestGRPCDestructiveGate_Integration"), "fail", "grpc destructive on prod")

    # ---- masking ----

    def test_account_fatal_masks_account(self):
        self._preflight()
        env = dict(self._VALID); env["VENDOR_ACCOUNT"] = "acct_secret_zz"
        out = self._assert(self._run(self._fixture(), env, test="TestGate_Integration"), "fail", "mask account")
        self.assertNotIn("acct_secret_zz", out)
        self.assertIn("***", out)

    def test_prod_url_fatal_redacts_url(self):
        self._preflight()
        env = dict(self._VALID)
        env["VENDOR_SANDBOX_HOSTS"] = "127.0.0.1"
        env["VENDOR_BASE_URL"] = "https://api.production.example/secret/path?token=SUPERSECRET"
        out = self._assert(self._run(self._fixture(), env, test="TestGate_Integration"), "fail", "redact url")
        self.assertNotIn("SUPERSECRET", out)
        self.assertNotIn("secret/path", out)

    # ---- destructive ----

    def test_destructive_without_flag_skips(self):
        self._preflight()
        self._assert(self._run(self._fixture(), dict(self._VALID), test="TestDestructiveGate_Integration"), "skip", "destructive no flag")

    def test_destructive_valid_passes(self):
        self._preflight()
        env = dict(self._VALID); env.update(self._DESTRUCTIVE)
        self._assert(self._run(self._fixture(), env, test="TestDestructiveGate_Integration"), "pass", "destructive valid")

    def test_destructive_without_idempotency_fails(self):
        self._preflight()
        env = dict(self._VALID); env.update(self._DESTRUCTIVE); env["VENDOR_IDEM_KEY"] = ""
        self._assert(self._run(self._fixture(), env, test="TestDestructiveGate_Integration"), "fail", "destructive no idempotency")

    def test_destructive_on_prod_forbidden(self):
        self._preflight()
        env = dict(self._VALID); env.update(self._DESTRUCTIVE); env["ENV"] = "prod"; env["INTEGRATION_ALLOW_PROD"] = "1"
        self._assert(self._run(self._fixture(), env, test="TestDestructiveGate_Integration"), "fail", "destructive on prod")

    # ---- budget / pure ----

    def test_cost_budget_exceeded_fails(self):
        self._preflight()
        self._assert(self._run(self._fixture(), {"THIRDPARTY_INTEGRATION": "1", "VENDOR_MAX_CALLS": "2"}, test="TestCostBudget_Integration"), "fail", "budget exceeded")

    def test_cost_budget_within_passes(self):
        self._preflight()
        self._assert(self._run(self._fixture(), {"THIRDPARTY_INTEGRATION": "1"}, test="TestCostBudget_Integration"), "pass", "budget ok")

    def test_parse_retry_after(self):
        self._preflight()
        self._assert(self._run(self._fixture(), {"THIRDPARTY_INTEGRATION": "1"}, test="TestParseRetryAfter_Integration"), "pass", "parseRetryAfter")

    def test_mask_and_redact(self):
        self._preflight()
        self._assert(self._run(self._fixture(), {"THIRDPARTY_INTEGRATION": "1"}, test="TestMaskAndRedact_Integration"), "pass", "mask/redact")

    def test_grpc_target(self):
        self._preflight()
        self._assert(self._run(self._fixture(), {"THIRDPARTY_INTEGRATION": "1"}, test="TestGRPCTarget_Integration"), "pass", "grpc target")

    # ---- real HTTP behavior ----

    def test_budget_transport_enforces_cap(self):
        # #1: budget at the transport catches every real request (incl. client internal retries).
        self._preflight()
        self._assert(self._run(self._fixture(), {"THIRDPARTY_INTEGRATION": "1", "VENDOR_MAX_CALLS": "2"}, test="TestBudgetTransport_Integration"), "pass", "budget transport")

    def test_contract_asserts_status_and_body(self):
        self._preflight()
        self._assert(self._run(self._fixture(), dict(self._VALID), test="TestContract_Integration"), "pass", "contract")

    def test_rate_limit_transient_retried_and_succeeds(self):
        self._preflight()
        self._assert(self._run(self._fixture(), dict(self._VALID), test="TestRateLimitTransient_Integration"), "pass", "429 transient")

    def test_rate_limit_persistent_fails_not_skips(self):
        self._preflight()
        self._assert(self._run(self._fixture(), dict(self._VALID), test="TestRateLimitPersistent_Integration"), "fail", "429 persistent")

    def test_rate_limit_error_redacts_url(self):
        # #3: a failed request (url.Error stringifies the full URL) must NOT leak the query token.
        self._preflight()
        out = self._assert(self._run(self._fixture(), {"THIRDPARTY_INTEGRATION": "1"}, test="TestRateLimitURLRedaction_Integration"), "fail", "url redaction")
        self.assertNotIn("SUPERSECRET", out)
        self.assertNotIn("token=", out)

    def test_build_request_error_redacts_url(self):
        # #2a: a malformed URL fails at NewRequestWithContext (a *url.Error embedding the full
        # URL); the query token must not leak. No network — fails at parse, so it runs everywhere.
        self._preflight()
        out = self._assert(self._run(self._fixture(), {"THIRDPARTY_INTEGRATION": "1"}, test="TestBuildRequestURLRedaction_Integration"), "fail", "build url redaction")
        self.assertNotIn("SUPERSECRET", out)
        self.assertNotIn("token=", out)

    def test_context_timeout_surfaces_deadline(self):
        self._preflight()
        self._assert(self._run(self._fixture(), dict(self._VALID), test="TestTimeout_Integration"), "pass", "timeout")

    # ---- -count=1 cache proof ----

    def test_count1_defeats_test_cache(self):
        self._preflight()
        r = self._fixture()
        env = {"THIRDPARTY_INTEGRATION": "1"}
        first = self._run(r, env, test="TestCacheProof_Integration")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertNotIn("(cached)", first.stdout, "first run must execute")
        second = self._run(r, env, test="TestCacheProof_Integration")
        self.assertIn("(cached)", second.stdout, f"expected cached re-run:\n{second.stdout}")
        forced = self._run(r, env, test="TestCacheProof_Integration", extra=["-count=1"])
        self.assertNotIn("(cached)", forced.stdout, f"-count=1 must defeat cache:\n{forced.stdout}")


RUNNER = os.path.join(os.path.dirname(__file__), "..", "run_vendor_integration.sh")


class RunnerScriptTests(unittest.TestCase):
    """The controlled runner is safety-critical, so exercise it for real: it must parse (never
    execute) the env file, enforce the required vars, and refuse to let extra args override
    -tags/-count. These paths all exit before `go test`, so they need bash but not go."""

    def _run_runner(self, env_text, args=(), pkg="./..."):
        root = tempfile.mkdtemp(prefix="tp-runner-")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        envfile = os.path.join(root, "env")
        with open(envfile, "w", encoding="utf-8") as fh:
            fh.write(env_text)
        # Point the runner's `mktemp` at the (writable) test dir — a locked-down sandbox may deny
        # the OS default temp, which is an environment limit, not a runner defect.
        env = {**os.environ, "TMPDIR": root}
        try:
            res = subprocess.run(["bash", RUNNER, envfile, pkg, *args],
                                 cwd=root, env=env, capture_output=True, text=True, timeout=30)
        except OSError as exc:
            self.skipTest(f"cannot exec bash: {exc}")
        return res, root

    def test_missing_required_var_exits_nonzero(self):
        res, _ = self._run_runner("VENDOR_SANDBOX_HOSTS=sb\nVENDOR_TEST_ACCOUNTS=a\n")  # no THIRDPARTY_INTEGRATION
        self.assertNotEqual(res.returncode, 0, "runner must reject a missing required var")
        self.assertIn("THIRDPARTY_INTEGRATION", res.stdout + res.stderr)

    def test_does_not_execute_env_file_code(self):
        # `source` would run the $( ) substitution; a data-only parser stores it literally.
        # Omit THIRDPARTY_INTEGRATION so the runner exits after parsing, before `go test`.
        res, root = self._run_runner("EVIL=$(touch pwned)\nVENDOR_SANDBOX_HOSTS=sb\nVENDOR_TEST_ACCOUNTS=a\n")
        self.assertFalse(os.path.exists(os.path.join(root, "pwned")),
                         "env-file code was EXECUTED — the runner must parse KEY=VALUE, not source it")
        self.assertNotEqual(res.returncode, 0)

    _GOOD_ENV = "THIRDPARTY_INTEGRATION=1\nENV=dev\nVENDOR_SANDBOX_HOSTS=sb\nVENDOR_TEST_ACCOUNTS=a\n"

    def test_rejects_count_flag_override(self):
        res, _ = self._run_runner(self._GOOD_ENV, args=["-count=5"])
        self.assertNotEqual(res.returncode, 0, "runner must refuse a -count override")
        self.assertIn("disallowed go test arg", res.stdout + res.stderr)

    def test_rejects_tags_flag_override(self):
        res, _ = self._run_runner(self._GOOD_ENV, args=["-tags=unit"])
        self.assertNotEqual(res.returncode, 0, "runner must refuse a -tags override")
        self.assertIn("disallowed go test arg", res.stdout + res.stderr)

    def test_rejects_test_dot_count_binary_flag(self):
        # Go accepts -test.count as well as -count; the allowlist must reject it.
        res, _ = self._run_runner(self._GOOD_ENV, args=["-test.count=0"])
        self.assertNotEqual(res.returncode, 0, "runner must refuse -test.count")
        self.assertIn("disallowed go test arg", res.stdout + res.stderr)

    def test_rejects_test_dot_timeout_binary_flag(self):
        res, _ = self._run_runner(self._GOOD_ENV, args=["-test.timeout=0"])
        self.assertNotEqual(res.returncode, 0, "runner must refuse -test.timeout")
        self.assertIn("disallowed go test arg", res.stdout + res.stderr)

    def test_rejects_args_passthrough(self):
        res, _ = self._run_runner(self._GOOD_ENV, args=["-args", "whatever"])
        self.assertNotEqual(res.returncode, 0, "runner must refuse -args")
        self.assertIn("disallowed go test arg", res.stdout + res.stderr)

    def test_pkg_arg_cannot_smuggle_a_flag(self):
        good = "THIRDPARTY_INTEGRATION=1\nENV=dev\nVENDOR_SANDBOX_HOSTS=sb\nVENDOR_TEST_ACCOUNTS=a\n"
        res, _ = self._run_runner(good, pkg="-count=0")  # a flag masquerading as the package
        self.assertNotEqual(res.returncode, 0, "runner must reject a package that starts with '-'")
        self.assertIn("invalid go-package", res.stdout + res.stderr)

    def test_rejects_zero_timeout_env(self):
        res, _ = self._run_runner(self._GOOD_ENV + "VENDOR_TEST_TIMEOUT=0s\n")
        self.assertNotEqual(res.returncode, 0, "runner must reject a zero test timeout")
        self.assertIn("VENDOR_TEST_TIMEOUT", res.stdout + res.stderr)

    def test_rejects_excessive_timeout_env(self):
        # a huge timeout is not literally zero but forfeits runtime protection — cap it.
        res, _ = self._run_runner(self._GOOD_ENV + "VENDOR_TEST_TIMEOUT=999999h\n")
        self.assertNotEqual(res.returncode, 0, "runner must reject a timeout above the 1h cap")
        self.assertIn("VENDOR_TEST_TIMEOUT", res.stdout + res.stderr)

    def _fake_go_run(self, go_body, pkg="./internal/pkg/x", args=("-run", "Integration")):
        """Run the runner against a fake `go` (on PATH) that records its argv and then runs
        `go_body`. Returns (CompletedProcess, argv_file). Needs bash, not the real toolchain."""
        root = tempfile.mkdtemp(prefix="tp-runner-")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        with open(os.path.join(root, "env"), "w", encoding="utf-8") as fh:
            fh.write(self._GOOD_ENV)
        bindir = os.path.join(root, "bin"); os.makedirs(bindir)
        argv_out = os.path.join(root, "argv.txt")
        with open(os.path.join(bindir, "go"), "w", encoding="utf-8") as fh:
            fh.write("#!/usr/bin/env bash\nprintf '%s\\n' \"$@\" > " + shlex.quote(argv_out) + "\n" + go_body)
        os.chmod(os.path.join(bindir, "go"), 0o755)
        env = dict(os.environ); env["PATH"] = bindir + os.pathsep + env.get("PATH", "")
        env["TMPDIR"] = root  # runner's mktemp must land in a writable dir (sandbox denies OS default)
        try:
            res = subprocess.run(["bash", RUNNER, os.path.join(root, "env"), pkg, *args],
                                 cwd=root, env=env, capture_output=True, text=True, timeout=30)
        except OSError as exc:
            self.skipTest(f"cannot exec bash: {exc}")
        return res, argv_out

    def test_valid_input_execs_expected_go_command(self):
        # positive end-to-end: valid input must exec exactly
        # `test -tags=integration -count=1 -timeout=300s -p=1 -parallel=1 -v <pkg> <extras>`; the
        # fake go emits a real PASS whose name contains the marker so both green-run guards pass.
        body = ("printf '=== RUN   TestFake_Integration\\n--- PASS: TestFake_Integration (0.00s)\\n"
                "PASS\\nok\\tpkg\\t0.001s\\n'\nexit 0\n")
        res, argv_out = self._fake_go_run(body)
        self.assertEqual(res.returncode, 0, f"runner failed on valid input:\n{res.stdout}{res.stderr}")
        with open(argv_out, encoding="utf-8") as fh:
            argv = fh.read().splitlines()
        self.assertEqual(argv[:7],
                         ["test", "-tags=integration", "-count=1", "-timeout=300s", "-p=1", "-parallel=1", "-v"],
                         f"fixed flags wrong: {argv}")
        self.assertEqual(argv[7], "./internal/pkg/x", f"package not passed through: {argv}")
        self.assertEqual(argv[8:], ["-run", "Integration"], f"extra args not forwarded: {argv}")

    def test_zero_execution_reported_as_failure(self):
        # #2: a green `go test` that ran NO tests (bad -run pattern, -list, …) must NOT be
        # reported as success — the runner's anti-false-green check turns it into a failure.
        body = ("printf 'testing: warning: no tests to run\\nPASS\\n"
                "ok\\tpkg\\t0.001s [no tests to run]\\n'\nexit 0\n")
        res, _ = self._fake_go_run(body)
        self.assertNotEqual(res.returncode, 0, "runner must fail when zero tests executed")
        self.assertIn("no test PASSED", res.stdout + res.stderr)

    def test_all_skip_reported_as_failure(self):
        # #1: a run where every test SKIPs (e.g. destructive tier without the flag) exits 0 in go
        # but verified nothing — the runner must not report it as PASS.
        body = ("printf '=== RUN   TestWrite_Integration\\n--- SKIP: TestWrite_Integration (0.00s)\\n"
                "PASS\\nok\\tpkg\\t0.001s\\n'\nexit 0\n")
        res, _ = self._fake_go_run(body)
        self.assertNotEqual(res.returncode, 0, "runner must fail when all tests skipped")
        self.assertIn("no test PASSED", res.stdout + res.stderr)

    def test_non_integration_pass_reported_as_failure(self):
        # #2: a passing PLAIN unit test (name without the marker) must not satisfy the
        # executed-an-integration-test check.
        body = ("printf '=== RUN   TestUnit\\n--- PASS: TestUnit (0.00s)\\nPASS\\n"
                "ok\\tpkg\\t0.001s\\n'\nexit 0\n")
        res, _ = self._fake_go_run(body)
        self.assertNotEqual(res.returncode, 0, "runner must fail when only non-integration tests pass")
        self.assertIn("none matching", res.stdout + res.stderr)

    def test_rejects_parallel_extra_arg(self):
        res, _ = self._run_runner(self._GOOD_ENV, args=["-parallel=8"])
        self.assertNotEqual(res.returncode, 0, "runner must refuse a -parallel override")
        self.assertIn("disallowed go test arg", res.stdout + res.stderr)

    def test_rejects_excessive_parallelism_env(self):
        res, _ = self._run_runner(self._GOOD_ENV + "VENDOR_TEST_PARALLELISM=99\n")
        self.assertNotEqual(res.returncode, 0, "runner must cap suite parallelism")
        self.assertIn("VENDOR_TEST_PARALLELISM", res.stdout + res.stderr)


if __name__ == "__main__":
    unittest.main()

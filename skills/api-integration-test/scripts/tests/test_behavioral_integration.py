"""Behavioral tests for the api-integration-test skill.

Every other test in this suite is a keyword-presence check on the skill *docs*.
This file compiles a real Go integration-test fixture that implements the gate /
prod-safety / tenant / destructive / retry / timeout logic the skill prescribes,
then runs it under many env configurations and asserts the ACTUAL behavior:

  - run gate unset            → SKIPS (opt-in, not requested)
  - gate on + config missing  → FAILS (t.Fatalf), not a silent skip
  - gate on + prod ENV/HOST / bare host / off-allowlist host → FAILS (fail closed)
  - tenant: no TEST_TENANT_ALLOWLIST → FAILS; tenant off-list / missing → FAILS
  - destructive without the flag → SKIPS
  - destructive with the flag + valid non-prod host allowlist + test tenant → PASSES
  - destructive WITHOUT NONPROD_HOST_ALLOWLIST → FAILS (host fail-closed)
  - destructive WITHOUT a validated tenant → FAILS
  - destructive against prod, even with ALLOW_PROD=1 + ALLOW_DESTRUCTIVE=1 → FAILS
  - `-count=1` forces execution; a plain re-run prints `(cached)`
  - bounded retry hits the endpoint 3×; context timeout surfaces DeadlineExceeded

The three safety helpers (isProdTarget / assertTestTenant / assertDestructiveSafe)
are kept token-identical to the SKILL.md baseline; test_skill_contract.py compares
their normalized FULL bodies (brace-depth) so the doc and this fixture cannot drift.

Skips (never fails) only on environment limits: no `go`, no writable temp dir, or
a sandbox that denies binding a local socket. Drops inherited GOROOT.
"""

import os
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
    \t"net/http"
    \t"net/http/httptest"
    \t"net/url"
    \t"os"
    \t"strings"
    \t"sync/atomic"
    \t"testing"
    \t"time"
    )

    func isProdTarget(env, rawURL string) bool {
    \tif env == "prod" || env == "production" {
    \t\treturn true
    \t}
    \tu, err := url.Parse(rawURL)
    \tif err != nil || !u.IsAbs() || (u.Scheme != "http" && u.Scheme != "https") || u.Hostname() == "" {
    \t\treturn true
    \t}
    \thost := strings.ToLower(u.Hostname())
    \tif allow := strings.TrimSpace(os.Getenv("NONPROD_HOST_ALLOWLIST")); allow != "" {
    \t\tfor _, h := range strings.Split(allow, ",") {
    \t\t\tif host == strings.ToLower(strings.TrimSpace(h)) {
    \t\t\t\treturn false
    \t\t\t}
    \t\t}
    \t\treturn true
    \t}
    \tfor _, bad := range []string{"prod", "production", "live"} {
    \t\tif strings.Contains(host, bad) {
    \t\t\treturn true
    \t\t}
    \t}
    \treturn false
    }

    func assertTestTenant(t *testing.T, tenant string) {
    \tt.Helper()
    \tallow := strings.TrimSpace(os.Getenv("TEST_TENANT_ALLOWLIST"))
    \tif allow == "" {
    \t\tt.Fatalf("TEST_TENANT_ALLOWLIST is required: list the exact test tenant IDs permitted to run integration tests")
    \t}
    \tfor _, id := range strings.Split(allow, ",") {
    \t\tif tenant == strings.TrimSpace(id) {
    \t\t\treturn
    \t\t}
    \t}
    \tt.Fatalf("tenant %q not in TEST_TENANT_ALLOWLIST — refuse", tenant)
    }

    func assertDestructiveSafe(t *testing.T, env, baseURL, tenant string) {
    \tt.Helper()
    \tif os.Getenv("INTEGRATION_ALLOW_DESTRUCTIVE") != "1" {
    \t\tt.Skip("destructive: set INTEGRATION_ALLOW_DESTRUCTIVE=1 to run")
    \t}
    \tif strings.TrimSpace(os.Getenv("NONPROD_HOST_ALLOWLIST")) == "" {
    \t\tt.Fatalf("destructive operations require NONPROD_HOST_ALLOWLIST (explicit non-prod hosts) — refuse without it")
    \t}
    \tif isProdTarget(env, baseURL) {
    \t\tt.Fatalf("destructive operations are forbidden against a production target, even with INTEGRATION_ALLOW_PROD=1")
    \t}
    \tassertTestTenant(t, tenant)
    }

    func requireIntegration(t *testing.T, baseURL string) {
    \tt.Helper()
    \tif os.Getenv("INTERNAL_API_INTEGRATION") != "1" {
    \t\tt.Skip("set INTERNAL_API_INTEGRATION=1 to run")
    \t}
    \tif strings.TrimSpace(baseURL) == "" {
    \t\tt.Fatalf("integration enabled but base URL missing")
    \t}
    \tenv := strings.ToLower(strings.TrimSpace(os.Getenv("ENV")))
    \tif isProdTarget(env, baseURL) && os.Getenv("INTEGRATION_ALLOW_PROD") != "1" {
    \t\tt.Fatalf("refuse production target (env=%q url=%q)", env, baseURL)
    \t}
    }

    func TestGate_Integration(t *testing.T) {
    \trequireIntegration(t, os.Getenv("API_BASE_URL"))
    \tif strings.TrimSpace(os.Getenv("TEST_USER_ID")) == "" {
    \t\tt.Fatalf("integration enabled but TEST_USER_ID missing")
    \t}
    \ttenant := strings.TrimSpace(os.Getenv("TEST_TENANT_ID"))
    \tif tenant == "" {
    \t\tt.Fatalf("integration enabled but TEST_TENANT_ID missing")
    \t}
    \tassertTestTenant(t, tenant)
    }

    func TestCacheProof_Integration(t *testing.T) {
    \tif os.Getenv("INTERNAL_API_INTEGRATION") != "1" {
    \t\tt.Skip("set INTERNAL_API_INTEGRATION=1 to run")
    \t}
    \tif 2+2 != 4 {
    \t\tt.Fatal("math broke")
    \t}
    }

    // TestDestructiveGate uses an env-provided target (no httptest server) so it can
    // exercise the destructive host/tenant gates without binding a socket.
    func TestDestructiveGate_Integration(t *testing.T) {
    \tbaseURL := strings.TrimSpace(os.Getenv("API_BASE_URL"))
    \trequireIntegration(t, baseURL)
    \tenv := strings.ToLower(strings.TrimSpace(os.Getenv("ENV")))
    \ttenant := strings.TrimSpace(os.Getenv("TEST_TENANT_ID"))
    \tassertDestructiveSafe(t, env, baseURL, tenant)
    }

    func TestContract_Integration(t *testing.T) {
    \tsrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
    \t\tw.Header().Set("Content-Type", "application/json")
    \t\tw.WriteHeader(http.StatusOK)
    \t\t_, _ = w.Write([]byte(`{"id":"42"}`))
    \t}))
    \tdefer srv.Close()
    \trequireIntegration(t, srv.URL)

    \tctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    \tdefer cancel()
    \treq, _ := http.NewRequestWithContext(ctx, http.MethodGet, srv.URL+"/users/42", nil)
    \tresp, err := http.DefaultClient.Do(req)
    \tif err != nil {
    \t\tt.Fatalf("request failed: %v", err)
    \t}
    \tdefer resp.Body.Close()
    \tif resp.StatusCode != http.StatusOK {
    \t\tt.Fatalf("status = %d, want 200", resp.StatusCode)
    \t}
    \tvar body struct {
    \t\tID string `json:"id"`
    \t}
    \tif err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
    \t\tt.Fatalf("decode: %v", err)
    \t}
    \tif body.ID != "42" {
    \t\tt.Fatalf("id = %q, want 42", body.ID)
    \t}
    }

    func TestRetry_Integration(t *testing.T) {
    \tvar attempts int32
    \tsrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
    \t\tif atomic.AddInt32(&attempts, 1) < 3 {
    \t\t\tw.WriteHeader(http.StatusServiceUnavailable)
    \t\t\treturn
    \t\t}
    \t\tw.WriteHeader(http.StatusOK)
    \t}))
    \tdefer srv.Close()
    \trequireIntegration(t, srv.URL)

    \tconst maxRetries = 2 // 1 initial + 2 retries = 3 attempts max
    \tctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    \tdefer cancel()
    \tlastStatus := 0
    \tfor i := 0; i <= maxRetries; i++ {
    \t\treq, _ := http.NewRequestWithContext(ctx, http.MethodGet, srv.URL, nil)
    \t\tresp, err := http.DefaultClient.Do(req)
    \t\tif err != nil {
    \t\t\tt.Fatalf("attempt %d: %v", i, err)
    \t\t}
    \t\tlastStatus = resp.StatusCode
    \t\tresp.Body.Close()
    \t\tif resp.StatusCode < 500 {
    \t\t\tbreak
    \t\t}
    \t\tselect {
    \t\tcase <-ctx.Done():
    \t\t\tt.Fatalf("ctx cancelled mid-retry: %v", ctx.Err())
    \t\tcase <-time.After(10 * time.Millisecond):
    \t\t}
    \t}
    \tif lastStatus != http.StatusOK {
    \t\tt.Fatalf("final status = %d, want 200", lastStatus)
    \t}
    \tif got := atomic.LoadInt32(&attempts); got != 3 {
    \t\tt.Fatalf("attempts = %d, want 3 (bounded retry, 503 twice then 200)", got)
    \t}
    }

    func TestTimeout_Integration(t *testing.T) {
    \tsrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
    \t\ttime.Sleep(200 * time.Millisecond)
    \t\tw.WriteHeader(http.StatusOK)
    \t}))
    \tdefer srv.Close()
    \trequireIntegration(t, srv.URL)

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

    func TestDestructive_Integration(t *testing.T) {
    \tsrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
    \t\tif r.Method == http.MethodDelete {
    \t\t\tw.WriteHeader(http.StatusNoContent)
    \t\t\treturn
    \t\t}
    \t\tw.WriteHeader(http.StatusOK)
    \t}))
    \tdefer srv.Close()
    \trequireIntegration(t, srv.URL)
    \tenv := strings.ToLower(strings.TrimSpace(os.Getenv("ENV")))
    \ttenant := strings.TrimSpace(os.Getenv("TEST_TENANT_ID"))
    \tassertDestructiveSafe(t, env, srv.URL, tenant)
    \tctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    \tdefer cancel()
    \treq, _ := http.NewRequestWithContext(ctx, http.MethodDelete, srv.URL+"/items/1", nil)
    \tresp, err := http.DefaultClient.Do(req)
    \tif err != nil {
    \t\tt.Fatalf("delete failed: %v", err)
    \t}
    \tdefer resp.Body.Close()
    \tif resp.StatusCode != http.StatusNoContent {
    \t\tt.Fatalf("status = %d, want 204", resp.StatusCode)
    \t}
    }
    """
)

_PREFLIGHT = {"go.mod": "module pf\n\ngo 1.22\n", "m.go": "package main\n\nfunc main() {}\n"}


def _go_env(root: str) -> dict:
    env = dict(os.environ)
    env.pop("GOROOT", None)  # let the go binary resolve its own; avoid a stale GOROOT
    env["GOTOOLCHAIN"] = "local"
    env["GOCACHE"] = os.path.join(root, ".gocache")
    env["GOMODCACHE"] = os.path.join(root, ".gomod")
    env["GOPATH"] = os.path.join(root, ".gopath")
    return env


@unittest.skipIf(GO is None, "go toolchain not installed")
class BehavioralIntegrationTests(unittest.TestCase):
    def _module(self, files: dict) -> str:
        try:
            root = tempfile.mkdtemp(prefix="aip-eval-")
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
                or "socket: operation not permitted" in out):
            self.skipTest(f"{ctx}: environment denies binding a local socket (sandbox)")
        if kind == "skip":
            self.assertEqual(res.returncode, 0, f"{ctx}: expected skip (rc0)\n{out}")
            self.assertIn("--- SKIP", out, f"{ctx}: expected SKIP marker\n{out}")
        elif kind == "fail":
            self.assertNotEqual(res.returncode, 0, f"{ctx}: expected FAIL (rc!=0)\n{out}")
            self.assertIn("--- FAIL", out, f"{ctx}: expected FAIL marker\n{out}")
        elif kind == "pass":
            self.assertEqual(res.returncode, 0, f"{ctx}: expected PASS (rc0)\n{out}")
            self.assertIn("--- PASS", out, f"{ctx}: expected PASS marker\n{out}")
        return out

    # a fully-valid non-prod env with an allowlisted test tenant (the PASS baseline)
    _VALID = {"INTERNAL_API_INTEGRATION": "1", "ENV": "dev", "TEST_USER_ID": "1",
              "TEST_TENANT_ID": "test-1", "TEST_TENANT_ALLOWLIST": "test-1,test-2",
              "API_BASE_URL": "http://127.0.0.1:8080"}
    # extra vars a destructive run needs on top of _VALID
    _DESTRUCTIVE = {"INTEGRATION_ALLOW_DESTRUCTIVE": "1", "NONPROD_HOST_ALLOWLIST": "127.0.0.1"}

    # ---- gate skip vs fail vs pass ----

    def test_gate_unset_skips(self):
        self._preflight()
        self._assert(self._run(self._fixture(), {}, test="TestGate_Integration"), "skip", "gate unset")

    def test_gate_on_missing_config_fails(self):
        self._preflight()
        env = {"INTERNAL_API_INTEGRATION": "1", "API_BASE_URL": ""}
        self._assert(self._run(self._fixture(), env, test="TestGate_Integration"), "fail", "no base URL")

    def test_gate_on_missing_userid_fails(self):
        self._preflight()
        env = dict(self._VALID); env["TEST_USER_ID"] = ""
        self._assert(self._run(self._fixture(), env, test="TestGate_Integration"), "fail", "no TEST_USER_ID")

    def test_prod_host_under_dev_env_fails(self):
        self._preflight()
        env = dict(self._VALID); env["API_BASE_URL"] = "https://api.production.internal"
        self._assert(self._run(self._fixture(), env, test="TestGate_Integration"), "fail", "prod host, ENV=dev")

    def test_bare_prod_host_no_scheme_fails(self):
        self._preflight()
        env = dict(self._VALID); env["API_BASE_URL"] = "api.production.internal"
        self._assert(self._run(self._fixture(), env, test="TestGate_Integration"), "fail", "bare prod host")

    def test_host_not_on_allowlist_fails(self):
        self._preflight()
        env = dict(self._VALID); env["NONPROD_HOST_ALLOWLIST"] = "localhost,test.svc"
        self._assert(self._run(self._fixture(), env, test="TestGate_Integration"), "fail", "host off allowlist")

    def test_prod_allowed_with_override_passes(self):
        self._preflight()
        env = dict(self._VALID)
        env["API_BASE_URL"] = "https://api.production.internal"
        env["INTEGRATION_ALLOW_PROD"] = "1"
        self._assert(self._run(self._fixture(), env, test="TestGate_Integration"), "pass", "prod read override")

    def test_valid_nonprod_passes(self):
        self._preflight()
        self._assert(self._run(self._fixture(), dict(self._VALID), test="TestGate_Integration"), "pass", "valid non-prod")

    # ---- tenant fail-closed (allowlist REQUIRED) ----

    def test_no_tenant_allowlist_fails(self):
        self._preflight()
        env = dict(self._VALID); env.pop("TEST_TENANT_ALLOWLIST")
        self._assert(self._run(self._fixture(), env, test="TestGate_Integration"), "fail", "no tenant allowlist")

    def test_tenant_off_allowlist_fails(self):
        self._preflight()
        env = dict(self._VALID); env["TEST_TENANT_ID"] = "acme-main"  # real prod-ish name, not on list
        self._assert(self._run(self._fixture(), env, test="TestGate_Integration"), "fail", "tenant off allowlist")

    def test_missing_tenant_fails(self):
        self._preflight()
        env = dict(self._VALID); env["TEST_TENANT_ID"] = ""
        self._assert(self._run(self._fixture(), env, test="TestGate_Integration"), "fail", "missing tenant")

    # ---- destructive: opt-in, host-allowlist + tenant enforced, never on prod ----

    def test_destructive_without_flag_skips(self):
        self._preflight()
        env = {"INTERNAL_API_INTEGRATION": "1", "ENV": "dev"}
        self._assert(self._run(self._fixture(), env, test="TestDestructive_Integration"), "skip", "destructive no flag")

    def test_destructive_with_flag_passes(self):
        self._preflight()
        env = dict(self._VALID); env.update(self._DESTRUCTIVE)
        self._assert(self._run(self._fixture(), env, test="TestDestructive_Integration"), "pass", "destructive ok")

    def test_destructive_without_host_allowlist_fails(self):
        # #2: destructive requires an explicit NONPROD_HOST_ALLOWLIST (fail closed on host).
        self._preflight()
        env = dict(self._VALID)
        env["INTEGRATION_ALLOW_DESTRUCTIVE"] = "1"
        env["API_BASE_URL"] = "http://127.0.0.1:9"  # non-prod, but no NONPROD_HOST_ALLOWLIST
        self._assert(self._run(self._fixture(), env, test="TestDestructiveGate_Integration"), "fail", "destructive no host allowlist")

    def test_destructive_without_tenant_fails(self):
        # #1: destructive must confirm a validated test tenant.
        self._preflight()
        env = dict(self._VALID); env.update(self._DESTRUCTIVE)
        env["API_BASE_URL"] = "http://127.0.0.1:9"
        env.pop("TEST_TENANT_ALLOWLIST")
        self._assert(self._run(self._fixture(), env, test="TestDestructiveGate_Integration"), "fail", "destructive no tenant allowlist")

    def test_destructive_on_prod_forbidden_even_with_both_flags(self):
        # #2 invariant: destructive against prod fails even with ALLOW_PROD=1 +
        # ALLOW_DESTRUCTIVE=1 and a configured (non-matching) host allowlist.
        self._preflight()
        env = dict(self._VALID); env.update(self._DESTRUCTIVE)
        env["API_BASE_URL"] = "https://api.production.internal"
        env["INTEGRATION_ALLOW_PROD"] = "1"
        self._assert(self._run(self._fixture(), env, test="TestDestructiveGate_Integration"),
                     "fail", "destructive on prod with both flags")

    # ---- real HTTP behavior ----

    def test_contract_asserts_status_and_body(self):
        self._preflight()
        env = {"INTERNAL_API_INTEGRATION": "1", "ENV": "dev"}
        self._assert(self._run(self._fixture(), env, test="TestContract_Integration"), "pass", "contract")

    def test_bounded_retry_hits_endpoint_three_times(self):
        self._preflight()
        env = {"INTERNAL_API_INTEGRATION": "1", "ENV": "dev"}
        self._assert(self._run(self._fixture(), env, test="TestRetry_Integration"), "pass", "retry")

    def test_context_timeout_surfaces_deadline(self):
        self._preflight()
        env = {"INTERNAL_API_INTEGRATION": "1", "ENV": "dev"}
        self._assert(self._run(self._fixture(), env, test="TestTimeout_Integration"), "pass", "timeout")

    # ---- -count=1 cache proof ----

    def test_count1_defeats_test_cache(self):
        self._preflight()
        r = self._fixture()
        env = {"INTERNAL_API_INTEGRATION": "1"}
        first = self._run(r, env, test="TestCacheProof_Integration")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertNotIn("(cached)", first.stdout, "first run must actually execute")
        second = self._run(r, env, test="TestCacheProof_Integration")
        self.assertIn("(cached)", second.stdout,
                      f"expected a cached result on identical re-run:\n{second.stdout}")
        forced = self._run(r, env, test="TestCacheProof_Integration", extra=["-count=1"])
        self.assertNotIn("(cached)", forced.stdout,
                         f"-count=1 must defeat the cache:\n{forced.stdout}")


if __name__ == "__main__":
    unittest.main()
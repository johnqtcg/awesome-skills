package secexamples

import (
	"net/http"
	"strings"
	"testing"
)

// TestGuardBlocksInternalTargets proves the documented guard actually blocks the addresses
// the reference claims it blocks. Only blocked cases are exercised, so the test needs no
// network: the Control hook rejects before any packet leaves.
func TestGuardBlocksInternalTargets(t *testing.T) {
	client := newSafeClient()
	for _, target := range []string{
		"http://127.0.0.1:80/",
		"http://localhost:80/",
		"http://[::1]:80/",
		"http://[::ffff:127.0.0.1]:80/",            // IPv4-mapped IPv6 smuggling
		"http://169.254.169.254/latest/meta-data/", // cloud instance metadata
		"http://10.0.0.1/",
		"http://192.168.1.1/",
		"http://172.16.0.1/",
	} {
		t.Run(target, func(t *testing.T) {
			resp, err := client.Get(target)
			if err == nil {
				resp.Body.Close()
				t.Fatalf("guard ALLOWED %s — SSRF protection is broken", target)
			}
			if !strings.Contains(err.Error(), "ssrf guard") {
				t.Fatalf("blocked for the wrong reason (%v); the guard must be what rejects it", err)
			}
		})
	}
}

// TestClassifierAcceptsPublicAddresses covers the allow side without dialing anything.
func TestClassifierAcceptsPublicAddresses(t *testing.T) {
	for _, addr := range []string{
		"8.8.8.8:443",
		"1.1.1.1:443",
		"93.184.216.34:443",
		"172.32.0.1:443", // just outside 172.16/12
		"172.15.0.1:443", // just below 172.16/12
		"[2606:4700::1111]:443",
	} {
		if err := blockNonPublic("tcp", addr, nil); err != nil {
			t.Errorf("guard rejected public address %s: %v", addr, err)
		}
	}
}

// TestClassifierRejectsUnresolvedHost pins the fail-closed behaviour: if Control is ever
// handed something that is not an IP, it must refuse rather than pass the connection.
func TestClassifierRejectsUnresolvedHost(t *testing.T) {
	if err := blockNonPublic("tcp", "evil.example.com:443", nil); err == nil {
		t.Fatal("guard accepted a non-IP address; it must fail closed")
	}
}

// TestRedirectsAreRefused pins the second control an allowlist cannot provide: an
// allowlisted host that answers 302 must not be followed to an internal address.
func TestRedirectsAreRefused(t *testing.T) {
	client := newSafeClient()
	if client.CheckRedirect == nil {
		t.Fatal("CheckRedirect must be set; default behaviour follows redirects and re-opens SSRF")
	}
	if err := client.CheckRedirect(nil, nil); err != http.ErrUseLastResponse {
		t.Fatalf("CheckRedirect must return http.ErrUseLastResponse, got %v", err)
	}
}

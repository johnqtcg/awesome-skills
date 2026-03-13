# Golden Example: Characterization Testing with Mutation-Based Red Evidence

This example demonstrates TDD for **pre-existing, untested code** — adding tests to `IsPrivateIPLiteral`, a security-sensitive SSRF guard function.

## Context

```go
// urlutil.go — already implemented, no tests exist
func IsPrivateIPLiteral(host string) bool {
	addr, err := netip.ParseAddr(host)
	if err != nil {
		return false
	}
	return addr.IsPrivate() ||
		addr.IsLoopback() ||
		addr.IsLinkLocalUnicast() ||
		addr.IsLinkLocalMulticast() ||
		addr.IsMulticast() ||
		addr.IsUnspecified()
}
```

## Output Contract

### Changed files

| File | Action |
|------|--------|
| `internal/urlutil/urlutil_test.go` | NEW — characterization + killer case tests |

### Change size: S (security budget override → doubled to 6-12 cases)

Single function, ≤10 LOC, but security-sensitive (SSRF guard) — budget doubled per security override rule.

### Defect hypotheses → test mapping

| # | Hypothesis | Test Case |
|---|-----------|-----------|
| H1 | IPv4-mapped IPv6 (`::ffff:127.0.0.1`) bypasses loopback check | `TestIsPrivateIPLiteral/killer_ipv4_mapped_ipv6_loopback` |
| H2 | Hostname input (not IP) incorrectly returns true | `TestIsPrivateIPLiteral/hostname_not_ip` |
| H3 | Empty string panics or returns true | `TestIsPrivateIPLiteral/empty_string` |
| H4 | Bracketed IPv6 `[::1]` parse failure returns false (safe) | `TestIsPrivateIPLiteral/bracketed_ipv6` |
| H5 | Public IP wrongly classified as private | `TestIsPrivateIPLiteral/public_ipv4` |

### Killer cases

1. **`killer_ipv4_mapped_ipv6_loopback`** — If `netip.ParseAddr` normalizes `::ffff:127.0.0.1` and `IsLoopback()` returns true, this must return true. A naive implementation that only checks IPv4 format would miss this.
2. **`killer_unspecified_ipv6`** — `::` (all zeros) must return true; a function that only checks `IsPrivate()` would miss this.

### Red → Green evidence (Characterization via Mutation)

Since the implementation already exists, Red evidence is obtained by mutation:

```
Step 1: Write tests → go test → PASS (characterizes existing behavior)
Step 2: Mutate production code (comment out IsLoopback check):
        // return addr.IsPrivate() ||
        //     addr.IsLoopback() ||   <-- REMOVED
        //     ...
        go test → FAIL:
          --- FAIL: TestIsPrivateIPLiteral/killer_ipv4_mapped_ipv6_loopback
              got false, want true
          --- FAIL: TestIsPrivateIPLiteral/loopback_127_0_0_1
              got false, want true
Step 3: Revert mutation → go test → PASS
```

This proves the tests actually guard the loopback behavior and are not trivially passing.

### Test code

```go
func TestIsPrivateIPLiteral(t *testing.T) {
	t.Parallel()
	tests := []struct {
		name string
		host string
		want bool
	}{
		// Private ranges
		{"private_10_x", "10.0.0.1", true},
		{"private_172_16_x", "172.16.0.1", true},
		{"private_192_168_x", "192.168.1.1", true},

		// Loopback
		{"loopback_127_0_0_1", "127.0.0.1", true},
		{"loopback_ipv6", "::1", true},

		// Killer: IPv4-mapped IPv6 loopback (SSRF bypass vector)
		{"killer_ipv4_mapped_ipv6_loopback", "::ffff:127.0.0.1", true},

		// Killer: unspecified address
		{"killer_unspecified_ipv6", "::", true},

		// Link-local
		{"link_local_unicast", "169.254.1.1", true},
		{"link_local_multicast", "ff02::1", true},

		// Public (must return false)
		{"public_ipv4", "8.8.8.8", false},
		{"public_ipv6", "2607:f8b0:4004:800::200e", false},

		// Invalid input (must return false, not panic)
		{"empty_string", "", false},
		{"hostname_not_ip", "localhost", false},
		{"bracketed_ipv6", "[::1]", false},
		{"host_with_port", "127.0.0.1:8080", false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			got := IsPrivateIPLiteral(tt.host)
			if got != tt.want {
				t.Errorf("IsPrivateIPLiteral(%q) = %v, want %v", tt.host, got, tt.want)
			}
		})
	}
}
```

### Coverage

```
ok   internal/urlutil   0.003s  coverage: 100.0% of statements
```

Risk-path coverage: all 6 branches of the `return` expression + parse error path verified.

### Scorecard

| # | Check | Result |
|---|-------|--------|
| C1 | Red evidence exists | PASS (mutation-based: removed IsLoopback → 2 tests fail) |
| C2 | Killer case present | PASS (ipv4_mapped_ipv6_loopback, unspecified_ipv6) |
| C3 | Risk-path coverage | PASS (all 6 branches + error path) |
| S1 | Defect hypothesis list | PASS (5 hypotheses mapped) |
| S2 | Success + error + boundary | PASS |
| S3 | High-signal assertions | PASS (exact bool values, not just nil) |
| S4 | Coverage ≥80% | PASS (100%) |
| S5 | Execution integrity | PASS (commands shown) |
| H1 | File naming | PASS (`urlutil_test.go`) |
| H2 | Subtest hierarchy | PASS (`t.Run`) |
| H3 | Table-driven style | PASS |
| H4 | Regression scope | PASS (S-size with security override) |

**Overall: PASS**

### Residual risks / follow-ups

- CGNAT range `100.64.0.0/10` is not classified as private by `netip.Addr.IsPrivate()` — if SSRF protection needs CGNAT blocking, additional logic is required
- DNS rebinding attacks bypass IP-literal checks entirely — a hostname resolver + re-check after resolution is needed for full SSRF protection
- Octal IP notation (e.g., `0177.0.0.1` for `127.0.0.1`) is rejected by `netip.ParseAddr` (returns false = safe), but other parsers may interpret it differently

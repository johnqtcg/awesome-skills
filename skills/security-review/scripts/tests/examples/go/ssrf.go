// Package secexamples holds the GOOD security patterns from the skill's references as
// real, compilable, testable code. If a documented pattern does not compile or does not
// actually block what it claims to block, these tests fail — which is the only way to keep
// a security reference honest. `go vet` alone cannot do that.
package secexamples

import (
	"fmt"
	"net"
	"net/http"
	"net/netip"
	"syscall"
	"time"
)

// blockNonPublic mirrors references/go-secure-coding.md §SSRF.
//
// It runs as net.Dialer.Control, i.e. AFTER DNS resolution, on the concrete IP that is
// about to be connected. That ordering is the point: a pre-dial LookupIP followed by
// dialing the hostname resolves twice and leaves a DNS-rebinding window.
func blockNonPublic(network, address string, _ syscall.RawConn) error {
	host, _, err := net.SplitHostPort(address)
	if err != nil {
		return err
	}
	ip, err := netip.ParseAddr(host)
	if err != nil {
		return fmt.Errorf("ssrf guard: %q is not a resolved IP", host)
	}
	ip = ip.Unmap() // defeat ::ffff:127.0.0.1 smuggling
	if !ip.IsGlobalUnicast() || ip.IsPrivate() || ip.IsLoopback() ||
		ip.IsLinkLocalUnicast() || ip.IsLinkLocalMulticast() ||
		ip.IsInterfaceLocalMulticast() {
		return fmt.Errorf("ssrf guard: blocked non-public address %s", ip)
	}
	return nil
}

// newSafeClient returns the client documented in the SSRF section: redirects refused,
// bounded timeouts, and the connect-time IP guard installed.
func newSafeClient() *http.Client {
	return &http.Client{
		Timeout: 10 * time.Second,
		CheckRedirect: func(*http.Request, []*http.Request) error {
			return http.ErrUseLastResponse
		},
		Transport: &http.Transport{
			DialContext: (&net.Dialer{
				Timeout: 5 * time.Second,
				Control: blockNonPublic,
			}).DialContext,
		},
	}
}

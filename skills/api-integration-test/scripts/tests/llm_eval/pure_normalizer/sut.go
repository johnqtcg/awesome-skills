package sut

import "strings"

// NormalizeTag canonicalises a user-supplied tag: trim, lowercase, collapse internal
// runs of '-' and drop leading/trailing separators.
//
// Pure function. No I/O, no clock, no network, no client — there is nothing to integrate
// with, so an "integration test" for it would either be a plain unit test in disguise or
// would have to substitute a transport that does not exist.
func NormalizeTag(raw string) string {
	s := strings.ToLower(strings.TrimSpace(raw))
	var b strings.Builder
	prevDash := false
	for _, r := range s {
		if r == '-' || r == ' ' || r == '_' {
			if !prevDash && b.Len() > 0 {
				b.WriteByte('-')
			}
			prevDash = true
			continue
		}
		b.WriteRune(r)
		prevDash = false
	}
	return strings.Trim(b.String(), "-")
}

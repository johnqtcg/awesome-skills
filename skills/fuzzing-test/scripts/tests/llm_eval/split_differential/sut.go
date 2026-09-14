package eval

import "strings"

// SplitRef is the reference implementation: the stdlib.
func SplitRef(s, sep string) []string { return strings.Split(s, sep) }

// SplitNew is a hand-rolled replacement meant to behave identically to SplitRef for every
// non-empty separator. Differential fuzzing is the oracle: the two must agree.
func SplitNew(s, sep string) []string {
	if sep == "" {
		return SplitRef(s, sep)
	}
	out := []string{}
	start := 0
	for i := 0; i+len(sep) <= len(s); {
		if s[i:i+len(sep)] == sep {
			out = append(out, s[start:i])
			i += len(sep)
			start = i
			continue
		}
		i++
	}
	out = append(out, s[start:])
	return out
}

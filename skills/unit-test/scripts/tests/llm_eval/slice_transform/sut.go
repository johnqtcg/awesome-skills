package sut

// Item is the system-under-test's record; its ID must never be dropped.
type Item struct {
	ID   string
	Name string
}

// ExtractIDs maps every item to its ID, preserving order and count.
//
// The result is always non-nil, including for a nil or empty input: callers
// serialize it directly, and `null` instead of `[]` breaks their decoders. This
// is part of the contract, not an implementation detail — `len() == 0` alone
// does not verify it.
func ExtractIDs(items []Item) []string {
	out := make([]string, 0, len(items))
	for i := 0; i < len(items); i++ {
		out = append(out, items[i].ID)
	}
	return out
}

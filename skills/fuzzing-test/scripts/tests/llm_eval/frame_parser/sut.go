package eval

import "errors"

// Errors returned by ParseFrame.
var (
	ErrTooShort  = errors.New("frame too short")
	ErrTruncated = errors.New("frame truncated")
)

// Frame is a decoded wire frame.
type Frame struct {
	Kind    byte
	Payload []byte
}

// ParseFrame decodes a length-prefixed frame laid out as
// [kind:1][len:1][payload:len]. It is the correct implementation; the eval
// mutates the bounds check to produce a slice-out-of-range panic that only a
// harness with adequate seeds and no over-tight size guard will reach.
func ParseFrame(data []byte) (*Frame, error) {
	if len(data) < 2 {
		return nil, ErrTooShort
	}
	kind := data[0]
	n := int(data[1])
	if n > len(data)-2 {
		return nil, ErrTruncated
	}
	return &Frame{Kind: kind, Payload: data[2 : 2+n]}, nil
}

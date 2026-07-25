package eval

import "errors"

// Errors returned by the codec.
var (
	ErrKeyTooLong = errors.New("key too long")
	ErrTruncated  = errors.New("truncated record")
)

// Record is the value round-tripped by Encode/Decode.
type Record struct {
	Key   string
	Value int32
}

// Encode serialises a Record as [keyLen:1][key:keyLen][value:4 little-endian].
// A key longer than 255 bytes cannot be represented, so it is rejected rather
// than silently truncated.
func Encode(r Record) ([]byte, error) {
	if len(r.Key) > 255 {
		return nil, ErrKeyTooLong
	}
	out := make([]byte, 0, 1+len(r.Key)+4)
	out = append(out, byte(len(r.Key)))
	out = append(out, r.Key...)
	v := uint32(r.Value)
	out = append(out, byte(v), byte(v>>8), byte(v>>16), byte(v>>24))
	return out, nil
}

// Decode reverses Encode.
func Decode(b []byte) (Record, error) {
	if len(b) < 1 {
		return Record{}, ErrTruncated
	}
	n := int(b[0])
	if len(b) < 1+n+4 {
		return Record{}, ErrTruncated
	}
	key := string(b[1 : 1+n])
	p := b[1+n:]
	v := uint32(p[0]) | uint32(p[1])<<8 | uint32(p[2])<<16 | uint32(p[3])<<24
	return Record{Key: key, Value: int32(v)}, nil
}

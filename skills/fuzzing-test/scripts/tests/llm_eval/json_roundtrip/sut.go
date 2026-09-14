package eval

import "encoding/json"

// Doc is persisted as JSON.
type Doc struct {
	Name string `json:"name"`
	Size int32  `json:"size"`
}

// Encode serialises a Doc.
//
// CONTRACT: encoding/json rewrites invalid UTF-8 in a string to U+FFFD, so the round-trip
// guarantee Decode(Encode(x)) == x holds for Names that are valid UTF-8. An invalid Name is
// outside the contract, not a counter-example.
func Encode(d Doc) ([]byte, error) { return json.Marshal(d) }

// Decode parses what Encode produced.
func Decode(b []byte) (Doc, error) {
	var d Doc
	err := json.Unmarshal(b, &d)
	return d, err
}

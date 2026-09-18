package eval

import "errors"

// ErrUnsupported is returned for a method the router does not handle.
var ErrUnsupported = errors.New("unsupported method")

// redirects maps a retired path to its replacement.
var redirects = map[string]string{
	"/old":      "/new",
	"/v1/users": "/v2/users",
}

const maxBody = 4096

// Request is the decoded command handed to ProcessRequest. It exceeds Go's native fuzz
// parameter types, so a harness feeds []byte and deserializes (SKILL.md Template D).
type Request struct {
	Method string `json:"method"`
	Path   string `json:"path"`
	Body   string `json:"body"`
}

// Response is what the caller writes back to its client.
type Response struct {
	StatusCode int
	Location   string
}

// ProcessRequest routes a decoded request and reports the status the caller should emit.
//
// Two invariants hold for every input, including malformed ones:
//
//  1. StatusCode is always a valid HTTP status in [100, 599]. Callers write it straight
//     into a response line, so an out-of-range value is a protocol violation.
//  2. A 3xx response always carries a non-empty Location. A redirect with no target is a
//     dead end for every client, and no status outside 3xx sets Location.
//
// Invariant 2 is the one a harness copied from the template will miss: the template's
// example asserts only the status range, and a 301 with an empty Location satisfies it.
func ProcessRequest(req Request) (*Response, error) {
	switch req.Method {
	case "GET":
		if req.Path == "" {
			return &Response{StatusCode: 400}, nil
		}
		resp := &Response{StatusCode: 200}
		if alias := redirects[req.Path]; alias != "" {
			resp.StatusCode = 301
			resp.Location = alias
		}
		return resp, nil
	case "POST":
		if len(req.Body) == 0 {
			return &Response{StatusCode: 422}, nil
		}
		if len(req.Body) > maxBody {
			return &Response{StatusCode: 413}, nil
		}
		return &Response{StatusCode: 201}, nil
	case "":
		return &Response{StatusCode: 400}, nil
	default:
		return nil, ErrUnsupported
	}
}

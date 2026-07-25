package secexamples

import (
	"encoding/xml"
	"reflect"
	"strings"
	"testing"
)

// The skill previously told reviewers to "set d.MaxDepth (Go 1.24+)" on an xml.Decoder.
// That field has never existed, so the advice could not compile. These tests pin every
// factual claim the corrected §Go XML section now makes, so the guidance cannot silently
// drift back to something untrue.

// TestDecoderHasNoMaxDepthField is the direct regression guard. It has to use reflection
// rather than `d.MaxDepth = N`, because the honest version of that line does not build.
func TestDecoderHasNoMaxDepthField(t *testing.T) {
	if _, ok := reflect.TypeOf(xml.Decoder{}).FieldByName("MaxDepth"); ok {
		t.Fatal("xml.Decoder now HAS a MaxDepth field — update references/go-secure-coding.md " +
			"§Go XML, which currently states that no such field exists")
	}
}

type xmlDoc struct {
	Val string `xml:"val"`
}

// TestNoInternalEntityExpansion proves billion-laughs does not apply to encoding/xml.
func TestNoInternalEntityExpansion(t *testing.T) {
	bomb := `<?xml version="1.0"?>
<!DOCTYPE d [
 <!ENTITY a "aaaaaaaaaa">
 <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">
]>
<d><val>&b;</val></d>`
	var d xmlDoc
	err := xml.Unmarshal([]byte(bomb), &d)
	if err == nil {
		t.Fatalf("encoding/xml expanded a DTD entity (val=%q) — billion-laughs now applies "+
			"and the suppression guidance must be revised", d.Val)
	}
	if !strings.Contains(err.Error(), "invalid character entity") {
		t.Fatalf("unexpected entity error %q; verify the documented behaviour still holds", err)
	}
}

// TestNoExternalEntityResolution proves XXE does not apply to encoding/xml.
func TestNoExternalEntityResolution(t *testing.T) {
	xxe := `<?xml version="1.0"?>
<!DOCTYPE d [<!ENTITY x SYSTEM "file:///etc/passwd">]>
<d><val>&x;</val></d>`
	var d xmlDoc
	if err := xml.Unmarshal([]byte(xxe), &d); err == nil {
		t.Fatalf("encoding/xml resolved an external entity (val=%q) — XXE now applies", d.Val)
	}
}

type xmlNest struct {
	Child *xmlNest `xml:"a"`
}

// TestUnmarshalDepthCapIsBuiltIn proves the nesting protection already exists and is not
// something a reviewer needs to ask for.
func TestUnmarshalDepthCapIsBuiltIn(t *testing.T) {
	shallow := strings.Repeat("<a>", 5000) + strings.Repeat("</a>", 5000)
	var ok xmlNest
	if err := xml.Unmarshal([]byte("<a>"+shallow+"</a>"), &ok); err != nil {
		t.Fatalf("depth 5000 should unmarshal cleanly, got %v", err)
	}

	deep := strings.Repeat("<a>", 10001) + strings.Repeat("</a>", 10001)
	var bad xmlNest
	err := xml.Unmarshal([]byte("<a>"+deep+"</a>"), &bad)
	if err == nil {
		t.Fatal("no built-in unmarshal depth cap fired at depth 10001 — the claim that " +
			"encoding/xml bounds nesting automatically is no longer true")
	}
	if !strings.Contains(err.Error(), "exceeded max depth") {
		t.Fatalf("expected the built-in depth cap, got %v", err)
	}
}

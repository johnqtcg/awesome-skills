"""Behavioral tests for the SKILL.md harness templates.

The four fuzz templates are this skill's most-copied artifacts, yet nothing
verified they were valid Go — a broken brace or parameter type would ship
green. These tests extract every ``func Fuzz`` block from SKILL.md, pair it
with a minimal stub package, and run ``go vet`` on the result.

They also mechanize the scorecard's regex-decidable Critical items against
the templates themselves (eating our own dogfood):
  C2 — every f.Fuzz body asserts a property (t.Fatal*/t.Error*)
  C3 — every []byte/string harness bounds input size
Mechanizing C3 immediately caught Templates B and C shipping without size
guards — the fix that introduced these tests also fixed the templates.
"""

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"

STUBS = '''package tpl

import "encoding/json"

func ParseXxx(d []byte) (int, error) { return len(d), nil }
func isValid(int) bool               { return true }

type Obj struct {
	A string
	B int32
}

func Encode(o Obj) ([]byte, error)   { return json.Marshal(o) }
func Decode(b []byte) (Obj, error)   { var o Obj; err := json.Unmarshal(b, &o); return o, err }
func ImplNew(s, sep string) []string { return []string{s, sep} }
func ImplRef(s, sep string) []string { return []string{s, sep} }
func equal(a, b []string) bool       { return len(a) == len(b) }

type Request struct{ Method, Path, Body string }
type Response struct{ StatusCode int }

func ProcessRequest(Request) (Response, error) { return Response{StatusCode: 200}, nil }
'''


def fuzz_templates() -> list[str]:
    text = SKILL_MD.read_text(encoding="utf-8")
    blocks = re.findall(r"```go\n(.*?)```", text, re.DOTALL)
    return [b for b in blocks if "func Fuzz" in b]


class TemplateMechanicalScorecardTests(unittest.TestCase):
    def test_at_least_four_templates(self) -> None:
        self.assertGreaterEqual(len(fuzz_templates()), 4)

    def test_c2_every_template_asserts_a_property(self) -> None:
        for tpl in fuzz_templates():
            name = re.search(r"func (Fuzz\w+)", tpl).group(1)
            self.assertRegex(tpl, r"t\.(Fatal|Error)",
                             f"{name}: scorecard C2 — f.Fuzz body must assert a property")

    def test_c3_every_byte_or_string_harness_bounds_size(self) -> None:
        for tpl in fuzz_templates():
            name = re.search(r"func (Fuzz\w+)", tpl).group(1)
            sig = re.search(r"f\.Fuzz\(func\(t \*testing\.T,([^)]*)\)", tpl)
            self.assertIsNotNone(sig, f"{name}: no f.Fuzz callback found")
            if "[]byte" in sig.group(1) or "string" in sig.group(1):
                self.assertIn("len(", tpl,
                              f"{name}: scorecard C3 — []byte/string harness must bound input size")

    def test_corruption_word_absent(self) -> None:
        docs = [SKILL_MD, *sorted((SKILL_DIR / "references").glob("*.md"))]
        for path in docs:
            self.assertNotIn("outputexample", path.read_text(encoding="utf-8"),
                             f"{path.name}: global-replace artifact present")


@unittest.skipUnless(shutil.which("go"), "go toolchain not installed")
class TemplateCompileTests(unittest.TestCase):
    def test_all_templates_compile_with_stubs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mod = Path(tmp)
            (mod / "go.mod").write_text("module tpl\n\ngo 1.18\n", encoding="utf-8")
            (mod / "stubs.go").write_text(STUBS, encoding="utf-8")
            test_src = "package tpl\n\nimport (\n\t\"encoding/json\"\n\t\"testing\"\n)\n\n"
            test_src += "\n".join(fuzz_templates())
            (mod / "templates_test.go").write_text(test_src, encoding="utf-8")
            proc = subprocess.run(
                ["go", "vet", "./..."],
                cwd=mod, capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(0, proc.returncode,
                             f"templates do not compile:\n{proc.stderr}")


if __name__ == "__main__":
    unittest.main()
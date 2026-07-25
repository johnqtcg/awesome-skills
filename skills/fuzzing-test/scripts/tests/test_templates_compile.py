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


def _go_env(root: str) -> dict:
    """Hermetic go env: an inherited GOROOT from another toolchain breaks every compile,
    and the default GOCACHE is not writable under sandboxed runs."""
    import os
    env = dict(os.environ)
    env.pop("GOROOT", None)
    env["GOTOOLCHAIN"] = "local"
    env["GOFLAGS"] = "-count=1"
    env["GOCACHE"] = str(Path(root) / ".gocache")
    env["GOMODCACHE"] = str(Path(root) / ".gomod")
    env["GOPATH"] = str(Path(root) / ".gopath")
    return env


@unittest.skipUnless(shutil.which("go"), "go toolchain not installed")
class TemplateCompileTests(unittest.TestCase):
    """`go vet` proves the templates parse and type-check. It does NOT run them, and that
    gap shipped a Template B seed containing invalid UTF-8: encoding/json rewrites it to
    U+FFFD, so the round-trip assertion failed on the CORRECT stub implementation. A
    template that fails out of the box is worse than no template, so seed replay is now
    part of the contract."""

    def _module(self, tmp: str) -> Path:
        mod = Path(tmp)
        (mod / "go.mod").write_text("module tpl\n\ngo 1.18\n", encoding="utf-8")
        (mod / "stubs.go").write_text(STUBS, encoding="utf-8")
        test_src = "package tpl\n\nimport (\n\t\"encoding/json\"\n\t\"testing\"\n)\n\n"
        test_src += "\n".join(fuzz_templates())
        (mod / "templates_test.go").write_text(test_src, encoding="utf-8")
        return mod

    def _run(self, mod: Path, *args: str, timeout: int = 180) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                ["go", *args], cwd=mod, env=_go_env(str(mod)),
                capture_output=True, text=True, timeout=timeout,
                # go echoes the failing input verbatim, so output is not always valid
                # UTF-8 (a raw 0xff seed crashes strict decoding).
                errors="replace",
            )
        except subprocess.TimeoutExpired:
            self.skipTest(f"go {' '.join(args)} exceeded {timeout}s here")
        except OSError as exc:
            self.skipTest(f"cannot exec go: {exc}")

    def test_all_templates_compile_with_stubs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mod = self._module(tmp)
            proc = self._run(mod, "vet", "./...")
            self.assertEqual(0, proc.returncode,
                             f"templates do not compile:\n{proc.stderr}")

    def test_all_template_seeds_pass_on_correct_implementation(self) -> None:
        """Every f.Add seed must pass against a correct implementation. A seed that fails
        here is a false positive that would greet any user who copied the template."""
        with tempfile.TemporaryDirectory() as tmp:
            mod = self._module(tmp)
            proc = self._run(mod, "test", "-run=^Fuzz", "./...")
            self.assertEqual(
                0, proc.returncode,
                "template seeds FAIL on the correct stub implementation — a copied "
                f"template would fail immediately:\n{proc.stdout}\n{proc.stderr}",
            )

    def test_seed_replay_would_catch_a_bad_seed(self) -> None:
        """Anti-vacuity: prove the replay check above can actually fail, by injecting the
        invalid-UTF-8 seed that originally slipped through `go vet`."""
        with tempfile.TemporaryDirectory() as tmp:
            mod = self._module(tmp)
            path = mod / "templates_test.go"
            poisoned = path.read_text(encoding="utf-8").replace(
                'f.Add("seed", int32(1))',
                'f.Add("seed", int32(1))\n\tf.Add("bad\\xff", int32(1))',
                1,
            )
            self.assertIn("bad", poisoned, "failed to inject the poison seed")
            path.write_text(poisoned, encoding="utf-8")
            proc = self._run(mod, "test", "-run=^Fuzz", "./...")
            self.assertNotEqual(
                0, proc.returncode,
                "seed replay did not reject an invalid-UTF-8 round-trip seed — the check "
                "is vacuous",
            )


if __name__ == "__main__":
    unittest.main()
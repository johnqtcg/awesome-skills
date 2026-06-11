"""Behavioral tests for the SKILL.md benchmark templates.

The benchmark templates are this skill's most-copied artifacts, yet nothing
verified they were valid Go. These tests extract every GOOD ``func Benchmark``
block from SKILL.md (including blocks nested in blockquotes), pair them with
a minimal stub package, and run ``go vet``.

Also guards the frontmatter↔workflow tool contract: every command family the
Phase 2 workflow tells the user to run must be pre-approved in allowed-tools
(this skill shipped without any allowed-tools at all, forcing a permission
prompt on every single command).
"""

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"

STUBS = '''package btpl

import "fmt"

type Result struct{}
type DB struct{}

var sink Result

func makeInput(n int) string         { return fmt.Sprintf("in-%d", n) }
func encode(s string) string         { return s }
func expensiveFunc(string) Result    { return Result{} }
func connectDB() *DB                 { return &DB{} }
func queryDB(*DB) Result             { return Result{} }
func buildInput() any                { return map[string]int{"a": 1} }

var input = "x"
'''


def good_go_blocks() -> list[str]:
    text = SKILL_MD.read_text(encoding="utf-8")
    # Fenced blocks inside blockquotes carry a leading "> " on every line.
    text = re.sub(r"(?m)^> ?", "", text)
    blocks = re.findall(r"```go\n(.*?)```", text, re.DOTALL)
    return [b for b in blocks
            if ("func Benchmark" in b or "sync.Pool" in b) and "BAD" not in b]


def clean(block: str) -> str:
    """Strip package/import decls from blocks that are complete files."""
    block = re.sub(r"(?m)^package .*$", "", block)
    block = re.sub(r"import \(.*?\)\n", "", block, flags=re.DOTALL)
    block = re.sub(r'(?m)^import ".*$', "", block)
    return block


class TemplateShapeTests(unittest.TestCase):
    def test_templates_found(self) -> None:
        self.assertGreaterEqual(len(good_go_blocks()), 5)

    def test_every_good_benchmark_uses_a_sink(self) -> None:
        """Hard Rule 1, mechanized: GOOD benchmark templates must assign to a
        sink, never discard with `_ =` inside the loop."""
        for block in good_go_blocks():
            if "func Benchmark" not in block:
                continue
            name = re.search(r"func (Benchmark\w*)", block).group(1)
            self.assertNotRegex(block, r"(?m)^\s*_ = ",
                                f"{name}: GOOD template discards its result")
            self.assertRegex(block, r"sink\w*[, ]",
                             f"{name}: GOOD template must demonstrate the sink pattern")


@unittest.skipUnless(shutil.which("go"), "go toolchain not installed")
class TemplateCompileTests(unittest.TestCase):
    def test_all_templates_compile_with_stubs(self) -> None:
        blocks = good_go_blocks()
        seen: set[str] = set()
        parts = []
        for block in blocks:
            m = re.search(r"func (\w+)", block)
            # SKILL.md shows alternative versions of the same example under
            # one name — keep the first, skip same-name duplicates.
            if m and m.group(1) in seen:
                continue
            if m:
                seen.add(m.group(1))
            parts.append(clean(block))

        src = ("package btpl\n\nimport (\n"
               '\t"bytes"\n\t"encoding/json"\n\t"fmt"\n\t"sync"\n\t"testing"\n)\n\n'
               # Keep-alives: which imports survive depends on which template
               # variant wins same-name dedup — pin them all as used.
               "var (\n"
               "\t_ = bytes.MinRead\n"
               "\t_ = json.Marshal\n"
               "\t_ = fmt.Sprintf\n"
               "\t_ sync.Once\n"
               ")\n\n"
               + "\n".join(parts))
        with tempfile.TemporaryDirectory() as tmp:
            mod = Path(tmp)
            (mod / "go.mod").write_text("module btpl\n\ngo 1.21\n", encoding="utf-8")
            (mod / "stubs.go").write_text(STUBS, encoding="utf-8")
            (mod / "bench_test.go").write_text(src, encoding="utf-8")
            proc = subprocess.run(["go", "vet", "./..."],
                                  cwd=mod, capture_output=True, text=True, timeout=120)
            self.assertEqual(0, proc.returncode,
                             f"templates do not compile:\n{proc.stderr}")


class AllowedToolsContractTests(unittest.TestCase):
    def test_workflow_commands_are_preapproved(self) -> None:
        text = SKILL_MD.read_text(encoding="utf-8")
        frontmatter = text.split("---")[1]
        self.assertIn("allowed-tools:", frontmatter,
                      "skill shipped without allowed-tools once — every Phase 2 "
                      "command prompted for permission")
        for pattern in ("Bash(go test*)", "Bash(go tool pprof*)", "Bash(benchstat*)"):
            self.assertIn(pattern, frontmatter,
                          f"Phase 2 tells the user to run this; pre-approve it: {pattern}")


if __name__ == "__main__":
    unittest.main()
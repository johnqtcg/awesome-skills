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

    def test_every_good_benchmark_prevents_elision(self) -> None:
        """Hard Rule 1, mechanized. The *property* is "the body cannot be optimised away",
        satisfied two ways: `for b.Loop()` (Go 1.24+, needs no sink) or a classic loop with a
        sink. The earlier version of this test demanded a sink identifier unconditionally,
        which would have rejected a correct b.Loop template."""
        for block in good_go_blocks():
            if "func Benchmark" not in block:
                continue
            name = re.search(r"func (Benchmark\w*)", block).group(1)
            self.assertNotRegex(block, r"(?m)^\s*_ = ",
                                f"{name}: GOOD template discards its result")
            uses_loop = "b.Loop()" in block
            uses_sink = re.search(r"sink\w*[, .]", block) is not None
            # Baseline templates measure the empty harness on purpose: no body to keep alive.
            is_baseline = "Baseline" in name or re.search(r"\{\s*\n\s*\}", block)
            self.assertTrue(
                uses_loop or uses_sink or is_baseline,
                f"{name}: GOOD template must prevent elision via b.Loop() or a sink",
            )

    def test_parallel_templates_never_write_a_shared_sink_in_the_loop(self) -> None:
        """A package-level sink inside b.RunParallel is a data race that fails under -race.
        The loop body must not assign a package-level identifier."""
        for block in good_go_blocks():
            if "RunParallel" not in block or "BAD" in block:
                continue
            name = re.search(r"func (Benchmark\w*)", block).group(1)
            body = block[block.index("RunParallel"):]
            # Inside the pb.Next() loop, a bare `sinkX =` assignment is the race.
            loop = re.search(r"for pb\.Next\(\)\s*\{(.*?)\n\s*\}", body, re.DOTALL)
            self.assertIsNotNone(loop, f"{name}: no pb.Next() loop found")
            self.assertNotRegex(
                loop.group(1), r"(?m)^\s*sink\w*\s*(,[^=]*)?=[^=]",
                f"{name}: assigns a shared sink inside RunParallel — data race under -race",
            )


def _go_env(root: Path) -> dict:
    """Hermetic go env. GOCACHE must be redirected: the default (~/Library/Caches/go-build)
    is not writable under sandboxed runs and the suite failed with
    `failed to trim cache: ... operation not permitted`. GOROOT is dropped because an
    inherited one from another toolchain breaks every build."""
    import os

    env = dict(os.environ)
    env.pop("GOROOT", None)
    env["GOTOOLCHAIN"] = "local"
    env["GOFLAGS"] = "-count=1"
    env["GOCACHE"] = str(root / ".gocache")
    env["GOMODCACHE"] = str(root / ".gomod")
    env["GOPATH"] = str(root / ".gopath")
    return env


@unittest.skipUnless(shutil.which("go"), "go toolchain not installed")
class TemplateCompileTests(unittest.TestCase):
    def _build_module(self, tmp: str) -> Path:
        """Materialise every GOOD template into one compilable module."""
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
               '\t"bytes"\n\t"encoding/json"\n\t"fmt"\n\t"runtime"\n'
               '\t"sync"\n\t"sync/atomic"\n\t"testing"\n)\n\n'
               # Keep-alives: which imports survive depends on which template
               # variant wins same-name dedup — pin them all as used.
               "var (\n"
               "\t_ = bytes.MinRead\n"
               "\t_ = json.Marshal\n"
               "\t_ = fmt.Sprintf\n"
               "\t_ sync.Once\n"
               "\t_ atomic.Int64\n"
               ")\n\n"
               "func init() { runtime.KeepAlive(0) }\n\n"
               + "\n".join(parts))
        mod = Path(tmp)
        # go 1.24: b.Loop() is the documented default loop form and must compile here.
        (mod / "go.mod").write_text("module btpl\n\ngo 1.24\n", encoding="utf-8")
        (mod / "stubs.go").write_text(STUBS, encoding="utf-8")
        (mod / "bench_test.go").write_text(src, encoding="utf-8")
        return mod

    def _run(self, mod: Path, *args: str, timeout: int = 240):
        try:
            return subprocess.run(["go", *args], cwd=mod, env=_go_env(mod),
                                  capture_output=True, text=True, timeout=timeout,
                                  errors="replace")
        except subprocess.TimeoutExpired:
            self.skipTest(f"go {' '.join(args)} exceeded {timeout}s here")
        except OSError as exc:
            self.skipTest(f"cannot exec go: {exc}")

    def test_all_templates_compile_with_stubs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mod = self._build_module(tmp)
            proc = self._run(mod, "vet", "./...")
            self.assertEqual(0, proc.returncode,
                             f"templates do not compile:\n{proc.stderr}")

    def test_all_templates_actually_run_race_free(self) -> None:
        """`go vet` type-checks but never executes — which is exactly how a data race in the
        RunParallel template shipped green. Running the templates under `-race` is what
        catches it: the old parallel template failed here with WARNING: DATA RACE."""
        with tempfile.TemporaryDirectory() as tmp:
            mod = self._build_module(tmp)
            proc = self._run(mod, "test", "-race", "-bench=.", "-benchtime=10x",
                             "-run=^$", "./...")
            self.assertEqual(
                0, proc.returncode,
                "templates fail when actually executed under -race:\n"
                f"{proc.stdout[-3000:]}\n{proc.stderr[-1500:]}",
            )
            self.assertNotIn("DATA RACE", proc.stdout,
                             "a template contains a data race")


class GuardsAreNotVacuousTests(unittest.TestCase):
    """Prove the two new shape guards actually reject the defects they were written for.
    Without this, a regex that silently stops matching would look like a passing suite."""

    RACY = '''func BenchmarkEncodeParallel(b *testing.B) {
    b.RunParallel(func(pb *testing.PB) {
        for pb.Next() {
            sinkString = encode(input)
        }
    })
}'''

    SAFE = '''func BenchmarkEncodeParallel(b *testing.B) {
    b.RunParallel(func(pb *testing.PB) {
        var acc int
        for pb.Next() {
            acc += len(encode(input))
        }
        sinkTotal.Add(int64(acc))
    })
}'''

    @staticmethod
    def _loop_body(block: str) -> str:
        body = block[block.index("RunParallel"):]
        return re.search(r"for pb\.Next\(\)\s*\{(.*?)\n\s*\}", body, re.DOTALL).group(1)

    RACE_PAT = r"(?m)^\s*sink\w*\s*(,[^=]*)?=[^=]"

    def test_guard_flags_the_original_racy_template(self) -> None:
        self.assertRegex(self._loop_body(self.RACY), self.RACE_PAT,
                         "guard no longer detects a shared sink write inside RunParallel")

    def test_guard_accepts_the_fixed_template(self) -> None:
        self.assertNotRegex(self._loop_body(self.SAFE), self.RACE_PAT,
                            "guard false-positives on the race-free accumulator pattern")

    def test_elision_guard_rejects_a_bare_call(self) -> None:
        """A classic loop with neither b.Loop nor a sink must not pass."""
        block = ("func BenchmarkX(b *testing.B) {\n"
                 "    for i := 0; i < b.N; i++ {\n        encode(input)\n    }\n}")
        uses_loop = "b.Loop()" in block
        uses_sink = re.search(r"sink\w*[, .]", block) is not None
        self.assertFalse(uses_loop or uses_sink,
                         "elision guard would wrongly accept an unprotected classic loop")


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
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

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
REF_DIR = SKILL_DIR / "references"

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


def _go_blocks(path: Path) -> list[str]:
    text = re.sub(r"(?m)^> ?", "", path.read_text(encoding="utf-8"))
    return re.findall(r"```go\n(.*?)```", text, re.DOTALL)


def reference_good_blocks() -> list[str]:
    """GOOD benchmark templates living in references/.

    The compile harness originally read SKILL.md only. That is precisely how
    `references/benchmark-antipatterns.md` came to ship
    `defer debug.SetGCPercent(debug.SetGCPercent(-1))()` — a snippet that cannot compile
    (`int is not a function`), sitting in a file no test ever fed to the toolchain. A
    reference template is copied just as readily as an inline one.
    """
    out = []
    for f in sorted(REF_DIR.glob("*.md")):
        for b in _go_blocks(f):
            if "func Benchmark" in b and "BAD" not in b and "ANTI" not in b:
                out.append(b)
    return out


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


@unittest.skipUnless(shutil.which("go"), "go toolchain not installed")
class ReferenceTemplateCompileTests(TemplateCompileTests):
    """Same treatment for references/ templates — the files the SKILL.md-only harness
    never looked at."""

    # Only identifiers the reference blocks do NOT declare themselves — `sinkBytes` and
    # `sinkInt` come from the blocks, and stubbing them too is a redeclaration error.
    EXTRA_STUBS = '''package btpl

import "testing"

type Obj struct{}

var (
	sinkObj    Obj
	sinkResult []byte
	sinkString string
)

func createObject() (Obj, error) { return Obj{}, nil }
func allocHeavyFunc() []byte     { return make([]byte, 8) }
func resetObject(Obj)            {}
func makeData(n int) []byte      { return make([]byte, n) }
func Encode(b []byte) []byte     { return b }
func Decode(b []byte) []byte     { return b }
func add(a, b int) int           { return a + b }
func openTestDB(*testing.B) *DB  { return &DB{} }
func makePayload(n int) []byte   { return make([]byte, n) }
func compress([]byte) ([]byte, error) { return nil, nil }
func generateRow() any           { return 1 }
func (d *DB) Exec(string, ...any) error { return nil }

var sinkErr error
'''

    def _build_module(self, tmp: str) -> Path:
        blocks, seen, parts = reference_good_blocks(), set(), []
        for block in blocks:
            m = re.search(r"func (\w+)", block)
            if m and m.group(1) in seen:
                continue
            if m:
                seen.add(m.group(1))
            parts.append(clean(block))
        src = ("package btpl\n\nimport (\n"
               '\t"bytes"\n\t"encoding/json"\n\t"fmt"\n\t"runtime"\n'
               '\t"strings"\n\t"sync"\n\t"sync/atomic"\n\t"testing"\n)\n\n'
               "var (\n\t_ = bytes.MinRead\n\t_ = json.Marshal\n\t_ = fmt.Sprintf\n"
               "\t_ = strings.Builder{}\n\t_ sync.Once\n\tsinkTotal atomic.Int64\n)\n\n"
               "func init() { runtime.KeepAlive(0) }\n\n" + "\n".join(parts))
        mod = Path(tmp)
        (mod / "go.mod").write_text("module btpl\n\ngo 1.24\n", encoding="utf-8")
        (mod / "stubs.go").write_text(STUBS, encoding="utf-8")
        (mod / "stubs_ref.go").write_text(self.EXTRA_STUBS, encoding="utf-8")
        (mod / "bench_test.go").write_text(src, encoding="utf-8")
        return mod

    def test_reference_templates_found(self) -> None:
        self.assertGreaterEqual(len(reference_good_blocks()), 5,
                                "reference template extraction found almost nothing — "
                                "the compile tests below would pass vacuously")


@unittest.skipUnless(shutil.which("go"), "go toolchain not installed")
class AntiPatternClaimsAreVerifiedTests(unittest.TestCase):
    """When a doc says "this does not compile", compile it and check.

    AP-5 asserted a GC-disabling idiom as a recommended PATTERN for a full release. It was
    rewritten as an anti-example whose first claim is that it does not build; that claim is
    only worth printing if something checks it.
    """

    AP5 = REF_DIR / "benchmark-antipatterns.md"

    def _vet(self, body: str):
        with tempfile.TemporaryDirectory() as tmp:
            mod = Path(tmp)
            (mod / "go.mod").write_text("module ap\n\ngo 1.24\n", encoding="utf-8")
            (mod / "x_test.go").write_text(
                'package ap\n\nimport (\n\t"runtime/debug"\n\t"testing"\n)\n\n'
                "var sinkResult []byte\n\n"
                "func allocHeavyFunc() []byte { return make([]byte, 8) }\n\n" + body,
                encoding="utf-8")
            return subprocess.run(["go", "vet", "./..."], cwd=mod, env=_go_env(mod),
                                  capture_output=True, text=True, timeout=240,
                                  errors="replace")

    def test_the_documented_broken_form_really_is_broken(self) -> None:
        broken = ("func BenchmarkX(b *testing.B) {\n"
                  "\tdefer debug.SetGCPercent(debug.SetGCPercent(-1))()\n"
                  "\tfor b.Loop() { sinkResult = allocHeavyFunc() }\n}")
        proc = self._vet(broken)
        self.assertNotEqual(0, proc.returncode,
                            "AP-5 claims this does not compile, but it did")
        self.assertIn("is not a function", proc.stderr,
                      f"failed for a different reason than documented:\n{proc.stderr}")

    def test_the_documented_correct_form_really_compiles(self) -> None:
        fixed = ("func BenchmarkX(b *testing.B) {\n"
                 "\tdefer debug.SetGCPercent(debug.SetGCPercent(-1))\n"
                 "\tfor b.Loop() { sinkResult = allocHeavyFunc() }\n}")
        proc = self._vet(fixed)
        self.assertEqual(0, proc.returncode,
                         f"the form AP-5 calls valid does not build:\n{proc.stderr}")

    def test_ap5_is_no_longer_recommended(self) -> None:
        text = self.AP5.read_text(encoding="utf-8")
        self.assertNotIn("PATTERN: disable GC", text,
                         "AP-5 still presents GC-disabling as a recommended pattern")
        self.assertIn("allocs/op", text)
        self.assertRegex(text, r"(?i)anti-?example|wrong|BAD")


@unittest.skipUnless(shutil.which("go"), "go toolchain not installed")
class GoldenGoodPracticeRaceTests(unittest.TestCase):
    """Every `good_practice` fixture must compile and survive `-race`.

    Fixture 006 asserted `type: good_practice`, `severity: none`,
    `expected_feedback: no violations` on a `RunParallel` body where every goroutine wrote
    the package-level `sinkAny` — a data race that fails `go test -race` with
    `WARNING: DATA RACE`, and precisely the defect Critical Rule 4 forbids. Nothing executed
    the fixtures, so the contradiction sat between the golden set and the skill's own rules
    for a full release.

    This matters beyond tidiness: a fixture labelled "correct" is the answer key. A
    forward-eval graded against it would mark an agent *wrong* for correctly reporting the
    race.
    """

    GOLDEN = Path(__file__).resolve().parent / "golden"

    STUBS = '''package gp

import "sync"

type Cache struct {
	mu sync.RWMutex
	m  map[string]any
}

func NewCache(n int) *Cache { return &Cache{m: make(map[string]any, n)} }
func populateCache(c *Cache) {
	for i := 0; i < 8; i++ {
		c.m["key-42"] = i
	}
}
func (c *Cache) Get(k string) (any, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	v, ok := c.m[k]
	return v, ok
}

func makeInput(n int) string  { return "x" }
func makeData(n int) []byte   { return make([]byte, n) }
func makePayload(n int) []byte { return make([]byte, n) }
func encode(b []byte) []byte  { return b }
func compress(b []byte) ([]byte, error) { return b, nil }
'''

    def good_practice_fixtures(self):
        out = []
        for f in sorted(self.GOLDEN.glob("*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("type") == "good_practice" and "func Benchmark" in data.get(
                    "benchmark_snippet", ""):
                out.append((f.name, data["benchmark_snippet"]))
        return out

    def test_fixtures_found(self) -> None:
        self.assertGreaterEqual(len(self.good_practice_fixtures()), 3,
                                "no good_practice fixtures extracted — the race test below "
                                "would pass vacuously")

    def test_every_good_practice_fixture_is_race_free(self) -> None:
        for name, snippet in self.good_practice_fixtures():
            with self.subTest(fixture=name):
                with tempfile.TemporaryDirectory() as tmp:
                    mod = Path(tmp)
                    (mod / "go.mod").write_text("module gp\n\ngo 1.24\n", encoding="utf-8")
                    (mod / "stubs.go").write_text(self.STUBS, encoding="utf-8")
                    (mod / "bench_test.go").write_text(
                        'package gp\n\nimport (\n\t"fmt"\n\t"sync/atomic"\n\t"testing"\n)\n\n'
                        "var (\n\t_ = fmt.Sprintf\n\t_ atomic.Int64\n)\n\n" + snippet + "\n",
                        encoding="utf-8")
                    proc = subprocess.run(
                        ["go", "test", "-race", "-bench=.", "-benchtime=50x", "-run=^$",
                         "./..."],
                        cwd=mod, env=_go_env(mod), capture_output=True, text=True,
                        timeout=300, errors="replace")
                self.assertNotIn(
                    "DATA RACE", proc.stdout + proc.stderr,
                    f"{name} is labelled good_practice but races:\n{proc.stdout[-1500:]}")
                self.assertEqual(
                    0, proc.returncode,
                    f"{name} is labelled good_practice but fails under -race:\n"
                    f"{proc.stdout[-1500:]}\n{proc.stderr[-800:]}")


@unittest.skipUnless(shutil.which("go"), "go toolchain not installed")
class GCClaimScriptTests(unittest.TestCase):
    """The GC measurements in AP-5 are only citable if the harness that produced them runs.

    Two properties beyond "it exits 0": the script must not be a memory hazard for a reader
    told to run it (the first version reserved 3008 MiB of HeapSys — 1 MiB of uncollected
    churn times 3000 iterations, since with GC off the churn size times b.N *is* the peak
    heap), and a failing benchmark inside it must not be swallowed by the grep that formats
    its output.
    """

    SCRIPT = SKILL_DIR / "scripts" / "gc_claim_check.sh"

    def test_script_exists_and_is_executable(self) -> None:
        import os
        self.assertTrue(self.SCRIPT.exists())
        self.assertTrue(os.access(str(self.SCRIPT), os.X_OK))

    def test_uses_strict_bash_flags(self) -> None:
        body = self.SCRIPT.read_text(encoding="utf-8")
        self.assertRegex(body, r"(?m)^set -euo pipefail\s*$",
                         "without pipefail, `go test | grep` hides a failing benchmark")

    def test_smoke_mode_runs_and_reports_both_experiments(self) -> None:
        proc = subprocess.run(["bash", str(self.SCRIPT), "--smoke"],
                              capture_output=True, text=True, timeout=600,
                              errors="replace")
        self.assertEqual(0, proc.returncode,
                         f"smoke run failed:\n{proc.stdout[-1500:]}\n{proc.stderr[-800:]}")
        self.assertIn("BenchmarkPlainGCOn", proc.stdout)
        self.assertIn("BenchmarkPoolGCOff", proc.stdout)
        self.assertIn("New-calls", proc.stdout,
                      "experiment 2 must report the Pool.New count — that IS the finding")

    def test_smoke_mode_stays_within_a_sane_heap(self) -> None:
        """HeapSys is reported by the script itself, so the budget is checkable."""
        proc = subprocess.run(["bash", str(self.SCRIPT), "--smoke"],
                              capture_output=True, text=True, timeout=600,
                              errors="replace")
        peaks = [float(m) for m in re.findall(r"([\d.]+)\s+HeapSys-MiB", proc.stdout)]
        self.assertTrue(peaks, f"no HeapSys metric in output:\n{proc.stdout[-800:]}")
        self.assertLess(max(peaks), 256,
                        f"smoke mode reserved {max(peaks)} MiB — too heavy for a doc example")

    def test_doc_iteration_count_matches_the_script(self) -> None:
        """AP-5 quotes measurements "from this script". When the script was retuned from
        3000 to 2000 iterations the prose kept saying 3000 — cited evidence that no longer
        matches its source still reads as verified, which is worse than no citation."""
        script = self.SCRIPT.read_text(encoding="utf-8")
        doc = (SKILL_DIR / "references" / "benchmark-antipatterns.md").read_text(
            encoding="utf-8")
        m = re.search(r"FULL_POOL_ITERS=(\d+)", script)
        self.assertIsNotNone(m, "FULL_POOL_ITERS not found in the script")
        iters = m.group(1)
        self.assertRegex(
            doc, rf"\*\*{iters} iterations\*\*",
            f"AP-5 must quote the script's current POOL_ITERS ({iters})",
        )
        self.assertRegex(doc, rf"POOL_ITERS={iters}",
                         "the constants footnote must match the script too")

    def test_budget_guard_reads_the_full_mode_constant(self) -> None:
        """Regression on the guard itself: the first pattern matched
        `POOL_ITERS=200` on the smoke line, so the heap-budget assertion was validating
        200 iterations while claiming to bound the 2000-iteration run."""
        script = self.SCRIPT.read_text(encoding="utf-8")
        self.assertIn("FULL_POOL_ITERS=2000", script)
        self.assertIn("SMOKE_POOL_ITERS=200", script)
        self.assertNotRegex(script, r"POOL_ITERS=\d+ POOL_COUNT",
                            "inline per-branch constants are ambiguous to match")

    def test_doc_states_the_measurement_environment(self) -> None:
        doc = (SKILL_DIR / "references" / "benchmark-antipatterns.md").read_text(
            encoding="utf-8")
        self.assertRegex(doc, r"go1\.\d+\.\d+ \w+/\w+",
                         "measurements must name the toolchain and platform they came from")

    def test_full_mode_churn_budget_is_bounded_by_construction(self) -> None:
        """With GC off nothing is reclaimed, so churn size x iteration count is the peak
        heap. Guard the two constants rather than paying 30s to measure them."""
        body = self.SCRIPT.read_text(encoding="utf-8")
        garb = re.search(r"garbSize = (\d+) << (\d+)", body)
        iters = re.search(r"FULL_POOL_ITERS=(\d+)", body)
        self.assertIsNotNone(garb, "garbSize constant not found")
        self.assertIsNotNone(iters, "FULL_POOL_ITERS not found")
        peak_mib = (int(garb.group(1)) * (2 ** int(garb.group(2)))
                    * int(iters.group(1))) / (1024 ** 2)
        self.assertLess(peak_mib, 512,
                        f"full mode would reserve ~{peak_mib:.0f} MiB of uncollected churn")


@unittest.skipUnless(shutil.which("go"), "go toolchain not installed")
class InterleavedBenchScriptTests(unittest.TestCase):
    """`run_interleaved_bench.sh` replaced a shell loop pasted into the docs.

    That loop got the operational details wrong in ways a reader only discovers by losing
    data: it appended onto existing result files, hardcoded branch names, switched the
    worktree once per sample, and left the caller on the wrong branch if interrupted. A
    script can be tested; a pasted loop cannot. These cover the argument-validation and
    refuse-to-clobber paths, which are the ones that protect real measurements.
    """

    SCRIPT = SKILL_DIR / "scripts" / "run_interleaved_bench.sh"

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        root = Path(cls._tmp.name)
        (root / "go.mod").write_text("module il\n\ngo 1.24\n", encoding="utf-8")
        pkg = root / "pkg" / "enc"
        pkg.mkdir(parents=True)
        (pkg / "e.go").write_text(
            "package enc\n\nfunc Encode(b []byte) []byte "
            "{ return append([]byte(nil), b...) }\n", encoding="utf-8")
        (pkg / "e_test.go").write_text(
            'package enc\n\nimport "testing"\n\nvar s []byte\n\n'
            "func BenchmarkEncode(b *testing.B) {\n\tin := make([]byte, 64)\n"
            "\tfor b.Loop() {\n\t\ts = Encode(in)\n\t}\n}\n", encoding="utf-8")
        cls.bin = root / "old.bench"
        proc = subprocess.run(["go", "test", "-c", "-o", str(cls.bin), "./pkg/enc"],
                              cwd=root, env=_go_env(root), capture_output=True, text=True,
                              timeout=300)
        cls.built = proc.returncode == 0
        cls.root = root

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def run_script(self, *args):
        return subprocess.run(["bash", str(self.SCRIPT), *map(str, args)],
                              capture_output=True, text=True, timeout=600, errors="replace")

    def test_script_exists_and_is_strict(self) -> None:
        import os
        self.assertTrue(self.SCRIPT.exists())
        self.assertTrue(os.access(str(self.SCRIPT), os.X_OK))
        self.assertRegex(self.SCRIPT.read_text(encoding="utf-8"),
                         r"(?m)^set -euo pipefail\s*$")

    def test_rejects_missing_arguments(self) -> None:
        proc = self.run_script()
        self.assertEqual(2, proc.returncode)
        self.assertIn("usage:", proc.stderr)

    def test_rejects_a_non_executable_binary(self) -> None:
        proc = self.run_script("/nonexistent-a", "/nonexistent-b",
                               str(self.root / "out-badbin"))
        self.assertEqual(2, proc.returncode)
        self.assertIn("not an executable benchmark binary", proc.stderr)

    def test_rejects_a_non_numeric_count(self) -> None:
        if not self.built:
            self.skipTest("fixture benchmark binary did not build")
        proc = self.run_script(self.bin, self.bin, self.root / "out-badcount", "abc")
        self.assertEqual(2, proc.returncode)
        self.assertIn("count must be a positive integer", proc.stderr)

    def test_refuses_to_append_to_existing_results(self) -> None:
        """Appending onto a previous run's file is the silent failure: benchstat groups by
        benchmark name and will average yesterday's machine state into today's verdict."""
        if not self.built:
            self.skipTest("fixture benchmark binary did not build")
        out = self.root / "out-clobber"
        out.mkdir()
        (out / "old.txt").write_text("stale data\n", encoding="utf-8")
        proc = self.run_script(self.bin, self.bin, out, 1)
        self.assertEqual(2, proc.returncode)
        self.assertIn("already exists", proc.stderr)
        self.assertEqual("stale data\n", (out / "old.txt").read_text(),
                         "refused, but overwrote the file anyway")

    def test_happy_path_produces_both_result_files(self) -> None:
        if not self.built:
            self.skipTest("fixture benchmark binary did not build")
        out = self.root / "out-ok"
        proc = self.run_script(self.bin, self.bin, out, 2)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        for name in ("old.txt", "new.txt"):
            body = (out / name).read_text(encoding="utf-8")
            self.assertIn("BenchmarkEncode", body, f"{name} has no samples")
            self.assertEqual(2, body.count("BenchmarkEncode"),
                             f"{name} should hold exactly the requested 2 samples")

    def test_lead_side_alternates_abba(self) -> None:
        """Order matters, and "we alternate" is not the same as "we alternate the lead".

        Running old->new every round still puts `old` first every single round, so a
        short-period effect (a turbo window that decays inside one round, a cache the
        previous binary left warm) lands on the same side each time and survives averaging
        as a systematic offset. Only swapping which side leads cancels it.

        Uses two stub "binaries" that append their name to a shared log, so the observed
        execution order is checked directly rather than inferred.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "order.log"
            for name in ("old", "new"):
                stub = root / f"{name}.bench"
                stub.write_text(f'#!/usr/bin/env bash\necho {name} >> "{log}"\n'
                                f'echo "BenchmarkX-1 100 1.0 ns/op"\n', encoding="utf-8")
                stub.chmod(0o755)
            proc = subprocess.run(
                ["bash", str(self.SCRIPT), str(root / "old.bench"),
                 str(root / "new.bench"), str(root / "out"), "4"],
                capture_output=True, text=True, timeout=300, errors="replace")
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
            order = log.read_text(encoding="utf-8").split()
        self.assertEqual(["old", "new", "new", "old", "old", "new", "new", "old"], order,
                         "lead side must alternate (ABBA), not repeat old-first every round")

    def test_odd_count_warns_about_unbalanced_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("old", "new"):
                stub = root / f"{name}.bench"
                stub.write_text('#!/usr/bin/env bash\necho "BenchmarkX-1 100 1.0 ns/op"\n',
                                encoding="utf-8")
                stub.chmod(0o755)
            proc = subprocess.run(
                ["bash", str(self.SCRIPT), str(root / "old.bench"),
                 str(root / "new.bench"), str(root / "out"), "3"],
                capture_output=True, text=True, timeout=300, errors="replace")
        self.assertIn("odd count", proc.stdout)

    def test_docs_never_claim_git_switch_dash_restores_the_start_branch(self) -> None:
        """`git switch -` is @{-1} — the PREVIOUS branch, not the original. Verified:
        starting on `other`, then main -> topic -> `-` lands on main."""
        for doc in (SKILL_MD, SKILL_DIR / "references" / "benchstat-guide.md", self.SCRIPT):
            with self.subTest(doc=doc.name):
                for line in doc.read_text(encoding="utf-8").splitlines():
                    if "git switch -" in line and "git switch --" not in line:
                        self.assertNotRegex(
                            line, r"(?i)back (to )?where you started|restore[sd]? your branch",
                            f"{doc.name}: `git switch -` does not return to the start branch",
                        )

    def test_docs_do_not_recommend_the_multi_package_compile(self) -> None:
        """`go test -c -o file ./pkg/...` fails: 'with multiple packages, -o must refer to
        a directory or /dev/null'. The docs shipped that exact command."""
        for doc in (SKILL_MD, SKILL_DIR / "references" / "benchstat-guide.md"):
            with self.subTest(doc=doc.name):
                self.assertNotRegex(
                    doc.read_text(encoding="utf-8"),
                    r"go test -c -o \S+ \./[\w/]*\.\.\.",
                    "`go test -c -o <file>` cannot take a multi-package pattern",
                )


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
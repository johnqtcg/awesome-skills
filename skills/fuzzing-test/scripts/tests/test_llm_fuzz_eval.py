"""End-to-end skill-output eval: a GRADER for what a model produces when driven by the
fuzzing-test skill, plus fixtures and a self-test proving the grader discriminates.

The gap this closes (see COVERAGE.md): the golden-fixture tests assert that a rule string
appears somewhere in the skill text. That validates the *document*, not the *behaviour* --
a response could name every rule and still emit a harness that never finds a bug. This
file grades a response by RUNNING the Go code it emitted:

  1. `grade(output, fixture, runner)` scores declared verdict, fuzz mode, seed count, size
     guard, and scorecard -- then compiles the emitted harness and requires it to PASS on
     the correct implementation and FAIL on a mutated one (i.e. actually find the defect).
  2. Two hand-authored exemplars (good, bad) plus a self-test proving the grader PASSES the
     good one and FAILS the bad one, for the right reasons. Runs in CI; needs `go`.
  3. An opt-in live hook (FUZZING_TEST_SKILL_EVAL_CMD) that drives a real model and grades
     its output with the same grader.

The mutation is deliberately SILENT rather than a panic: it widens a slice past the input's
logical length, and Go slice expressions are capacity-bounded, so no panic occurs. A
no-assertion "the runtime catches panics" harness therefore cannot kill it. That makes the
kill check a genuine test of oracle strength, matching scorecard C2's rule that a declared
domain-constraint oracle must be explicitly asserted.

Honesty: (1)+(2) prove the GRADER works; they do not prove a live model passes. Only the
opt-in (3), once wired to a backend, does that.
"""

import atexit
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

GO = shutil.which("go")
EVAL_ROOT = os.path.join(os.path.dirname(__file__), "llm_eval")
SKILL_MD = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "SKILL.md")
LIVE_CMD = os.environ.get("FUZZING_TEST_SKILL_EVAL_CMD")

# One fixture per fuzz mode that has a compile-and-kill scenario.
# frame_parser -> parser robustness (Template A); kv_codec -> round-trip (Template B).
FIXTURES = ("frame_parser", "kv_codec")

# Environment probe result, computed once: True, or a skip reason string.
_PREFLIGHT = None

# Session-wide go build cache; see _shared_cache().
_CACHE_DIR = None


def _fixture_dir(name: str) -> str:
    return os.path.join(EVAL_ROOT, name)


def _load_fixture(name: str) -> dict:
    d = _fixture_dir(name)
    with open(os.path.join(d, "meta.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    with open(os.path.join(d, "sut.go"), encoding="utf-8") as fh:
        meta["source"] = fh.read()
    meta["_dir"] = d
    return meta


def _shared_cache() -> str:
    """One build cache for the whole session. A per-module GOCACHE forces a cold stdlib
    recompile on every `go` invocation, which dominated this file's runtime. GOCACHE is a
    cache, not test state, so sharing it changes no outcome."""
    global _CACHE_DIR
    if _CACHE_DIR is None:
        _CACHE_DIR = tempfile.mkdtemp(prefix="fuzz-eval-cache-")
        atexit.register(shutil.rmtree, _CACHE_DIR, ignore_errors=True)
    return _CACHE_DIR


def _go_env(root: str) -> dict:
    """Hermetic go env. GOROOT is dropped because an inherited GOROOT from a different
    toolchain makes every compile fail; GOCACHE is redirected because the default
    (~/Library/Caches/go-build) is not writable under sandboxed runs and fuzzing -- unlike
    plain `go test` -- writes its corpus there, so it fails without this."""
    cache = _shared_cache()
    env = dict(os.environ)
    env.pop("GOROOT", None)
    env["GOTOOLCHAIN"] = "local"
    env["GOFLAGS"] = "-count=1"
    env["GOCACHE"] = os.path.join(cache, "build")
    env["GOMODCACHE"] = os.path.join(cache, "mod")
    env["GOPATH"] = os.path.join(root, ".gopath")
    return env


def extract_fuzz_harness(output: str):
    """Return the first ```go fenced block containing a fuzz target, or None."""
    for block in re.findall(r"```go\s*\n(.*?)```", output, re.S):
        if re.search(r"func Fuzz\w*\(\w+ \*testing\.F\)", block):
            return block
    return None


def harness_target_name(harness: str):
    m = re.search(r"func (Fuzz\w+)\(", harness)
    return m.group(1) if m else None


class _GoRunner:
    """Compile-and-run helper; raises unittest.SkipTest on environment failure."""

    def __init__(self, test_case: unittest.TestCase):
        self.tc = test_case

    def _mod(self, source: str, harness: str) -> str:
        try:
            root = tempfile.mkdtemp(prefix="fuzz-eval-")
        except OSError as exc:
            self.tc.skipTest(f"cannot create temp dir: {exc}")
        self.tc.addCleanup(shutil.rmtree, root, ignore_errors=True)
        files = {
            "go.mod": "module eval\n\ngo 1.18\n",
            "sut.go": source,
            "sut_test.go": 'package eval\n\nimport "testing"\n\n' + harness,
        }
        for name, content in files.items():
            with open(os.path.join(root, name), "w", encoding="utf-8") as fh:
                fh.write(content)
        return root

    def _run(self, root: str, *args: str, timeout: int = 180) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                [GO, *args], cwd=root, env=_go_env(root),
                capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            self.tc.skipTest(f"go {' '.join(args)} exceeded {timeout}s in this environment")
        except OSError as exc:
            self.tc.skipTest(f"cannot exec go: {exc}")

    def preflight(self) -> None:
        """Prove the toolchain can actually compile AND fuzz here before grading anything,
        so an environment failure never reads as a skill failure. Memoized: the answer is a
        property of the environment, and re-running a fuzz probe per test wasted seconds."""
        global _PREFLIGHT
        if _PREFLIGHT is None:
            _PREFLIGHT = self._probe_environment()
        if _PREFLIGHT is not True:
            self.tc.skipTest(_PREFLIGHT)

    def _probe_environment(self):
        """Return True, or a skip reason. Compiling is not enough — fuzzing writes to
        GOCACHE, so it can fail where `go build` succeeds."""
        root = self._mod(
            "package eval\n\nfunc Noop(d []byte) int { return len(d) }\n",
            'func FuzzNoop(f *testing.F) {\n\tf.Add([]byte("a"))\n'
            "\tf.Fuzz(func(t *testing.T, d []byte) { _ = Noop(d) })\n}\n",
        )
        if self._run(root, "build", "./...").returncode != 0:
            return "go cannot compile in this environment"
        probe = self._run(root, "test", "-run=^$", "-fuzz=^FuzzNoop$", "-fuzztime=1s", ".")
        if probe.returncode != 0:
            return f"go cannot fuzz in this environment: {probe.stdout[-300:]}"
        return True

    def compiles(self, source: str, harness: str) -> bool:
        root = self._mod(source, harness)
        return self._run(root, "vet", "./...").returncode == 0

    def replay_passes(self, source: str, harness: str, target: str) -> bool:
        """True iff the harness's own seed corpus passes on this source."""
        root = self._mod(source, harness)
        return self._run(root, "test", f"-run=^{target}$", ".").returncode == 0

    def fuzz_finds_defect(self, source: str, harness: str, target: str, fuzztime: str) -> bool:
        """True iff a bounded fuzz run finds a defect in this source.

        A nonzero exit code alone does NOT mean a defect was found. `go test` also exits nonzero
        for build failures, cache write errors, and toolchain problems, so `returncode != 0` read
        every infrastructure hiccup as "the fuzzer found the bug". That made the bad-exemplar
        assertions flaky: observed once in a full-repo run (1 failed / 3904 passed on
        `test_grader_fails_bad_exemplars[kv_codec]`, passing on the identical run repeated), where
        a bad harness that discards its Decode result — and therefore *cannot* detect silent
        corruption — was reported as having detected it.

        A genuine finding is identified by the `--- FAIL: <target>` line go prints for the failing
        input. A nonzero exit without it is an environment failure and skips, because guessing
        either way corrupts the grade."""
        root = self._mod(source, harness)
        secs = int(re.sub(r"\D", "", fuzztime) or 30)
        proc = self._run(root, "test", "-run=^$", f"-fuzz=^{target}$",
                         f"-fuzztime={fuzztime}", ".", timeout=secs + 120)
        if proc.returncode == 0:
            return False
        combined = f"{proc.stdout}\n{proc.stderr}"
        if re.search(rf"^\s*--- FAIL: {re.escape(target)}\b", combined, re.M):
            return True
        if "Failing input written to" in combined:
            return True
        self.tc.skipTest(
            f"go test exited {proc.returncode} without reporting a failing input for {target} — "
            f"an environment failure, not a fuzzing result: {combined.strip()[-400:]}")


def grade(output: str, fixture: dict, runner: "_GoRunner"):
    """Return (passed, reasons). Runs ALL checks without short-circuiting so a caller sees
    every way a response falls short."""
    reasons = []
    low = output.lower()

    # 1. Applicability verdict, which the skill requires before any code.
    m = re.search(r"Applicability Verdict[:*`\s]+(?:Not suitable|not_suitable|Suitable|suitable)",
                  output)
    if not m:
        reasons.append("no 'Applicability Verdict' declared")
    else:
        declared = "not_suitable" if re.search(r"not[ _]suitable", m.group(0), re.I) else "suitable"
        if declared != fixture["expected_verdict"]:
            reasons.append(f"verdict: declared {declared!r}, expected {fixture['expected_verdict']!r}")

    # 2. Fuzz mode.
    modes = ["parser robustness", "round-trip", "differential", "multi-parameter"]
    found_modes = [mode for mode in modes if mode in low]
    if fixture["expected_fuzz_mode"] not in found_modes:
        reasons.append(f"fuzz mode: found {found_modes}, expected {fixture['expected_fuzz_mode']!r}")

    # 3. Scorecard present.
    if "scorecard" not in low:
        reasons.append("no scorecard section")

    harness = extract_fuzz_harness(output)
    if harness is None:
        reasons.append("no fuzz harness (```go block with func FuzzXxx(f *testing.F)) found")
        return (False, reasons)

    target = harness_target_name(harness)

    # 4. Seed count (scorecard S1).
    seeds = harness.count("f.Add(")
    if seeds < fixture["min_seeds"]:
        reasons.append(f"seeds: found {seeds} f.Add call(s), need >= {fixture['min_seeds']}")

    # 5. Size guard (scorecard C3).
    if fixture["requires_size_guard"] and not re.search(r"len\([\w.]+\)\s*[><]", harness):
        reasons.append("no size guard on the fuzz input (scorecard C3)")

    # 6. Behavioral: compile, pass on correct source, and FIND the seeded defect.
    mut = fixture["mutation"]
    if mut["find"] not in fixture["source"]:
        reasons.append("fixture drift: mutation target not found in sut.go")
        return (len(reasons) == 0, reasons)

    if not runner.compiles(fixture["source"], harness):
        reasons.append("emitted harness does not compile")
        return (len(reasons) == 0, reasons)

    if not runner.replay_passes(fixture["source"], harness, target):
        reasons.append("emitted harness fails on the CORRECT implementation (false positive)")

    mutated = fixture["source"].replace(mut["find"], mut["replace"])
    if not runner.fuzz_finds_defect(mutated, harness, target, fixture["fuzztime_kill"]):
        reasons.append(
            f"emitted harness does NOT find the seeded defect ({mut['defect']}) "
            f"within {fixture['fuzztime_kill']} — weak seeds, over-tight guard, or no oracle"
        )

    return (len(reasons) == 0, reasons)


@unittest.skipIf(GO is None, "go toolchain not installed")
class GraderSelfTest(unittest.TestCase):
    """Prove the grader discriminates: PASS each good exemplar, FAIL each bad one.
    Runs over every fixture in FIXTURES so each fuzz mode is graded, not just Template A."""

    def setUp(self) -> None:
        self.runner = _GoRunner(self)
        self.runner.preflight()

    @staticmethod
    def _read(fixture: dict, name: str) -> str:
        with open(os.path.join(fixture["_dir"], name), encoding="utf-8") as fh:
            return fh.read()

    def test_grader_passes_good_exemplars(self) -> None:
        for name in FIXTURES:
            with self.subTest(fixture=name):
                fx = _load_fixture(name)
                passed, reasons = grade(self._read(fx, "good.md"), fx, self.runner)
                self.assertTrue(passed, f"{name}: good exemplar should pass; reasons: {reasons}")

    def test_grader_fails_bad_exemplars(self) -> None:
        for name in FIXTURES:
            with self.subTest(fixture=name):
                fx = _load_fixture(name)
                passed, reasons = grade(self._read(fx, "bad.md"), fx, self.runner)
                self.assertFalse(passed, f"{name}: bad exemplar must not pass")
                joined = " | ".join(reasons)
                # And for the RIGHT reasons: wrong mode, too few seeds, and a harness
                # that cannot find the defect.
                self.assertIn("fuzz mode", joined, f"{name}: expected a mode complaint; got {joined}")
                self.assertIn("seeds", joined, f"{name}: expected a seed complaint; got {joined}")
                self.assertIn("does NOT find the seeded defect", joined,
                              f"{name}: expected a kill-failure complaint; got {joined}")

    def test_mutation_is_reachable_at_all(self) -> None:
        """Guard against a fixture that can never fail: the good harness must find the
        defect, and the correct source must survive it. Without this, a broken mutation
        would silently make every kill check vacuous."""
        for name in FIXTURES:
            with self.subTest(fixture=name):
                fx = _load_fixture(name)
                harness = extract_fuzz_harness(self._read(fx, "good.md"))
                target = harness_target_name(harness)
                mutated = fx["source"].replace(
                    fx["mutation"]["find"], fx["mutation"]["replace"]
                )
                self.assertNotEqual(mutated, fx["source"], f"{name}: mutation did not apply")
                self.assertTrue(
                    self.runner.fuzz_finds_defect(mutated, harness, target,
                                                  fx["fuzztime_kill"]),
                    f"{name}: good harness failed to find the mutation — fixture is vacuous",
                )
                self.assertTrue(
                    self.runner.replay_passes(fx["source"], harness, target),
                    f"{name}: good harness fails on the correct source",
                )

    def test_build_failure_is_not_reported_as_a_finding(self) -> None:
        """A nonzero `go test` exit is not evidence the fuzzer found anything.

        `fuzz_finds_defect` returned `returncode != 0`, so a build failure, a cache write error,
        or any toolchain hiccup counted as "defect found". That made the bad-exemplar assertions
        flaky — one full-repo run failed `test_grader_fails_bad_exemplars[kv_codec]` while the
        same run repeated passed, because a harness that discards its Decode result and cannot
        possibly detect silent corruption was credited with detecting it. An infrastructure
        failure must skip, never silently invert the grade."""
        fx = _load_fixture(FIXTURES[0])
        with self.assertRaises(unittest.SkipTest):
            self.runner.fuzz_finds_defect(
                fx["source"], "func FuzzBroken(f *testing.F) {\n\tthis is not go\n}\n",
                "FuzzBroken", "2s")

    def test_good_harness_seeds_are_representable(self) -> None:
        """A round-trip seed the codec cannot represent losslessly fails on CORRECT code.
        That exact bug shipped in Template B, so pin it: every good exemplar's own seeds
        must pass against the unmutated implementation."""
        for name in FIXTURES:
            with self.subTest(fixture=name):
                fx = _load_fixture(name)
                harness = extract_fuzz_harness(self._read(fx, "good.md"))
                self.assertTrue(
                    self.runner.replay_passes(fx["source"], harness,
                                              harness_target_name(harness)),
                    f"{name}: exemplar seeds fail on the correct implementation",
                )


class GraderUnitTests(unittest.TestCase):
    """Pure-Python checks on the grader's extraction logic; no toolchain needed."""

    def test_extracts_harness_from_fenced_block(self) -> None:
        out = "text\n```go\nfunc FuzzX(f *testing.F) {\n\tf.Add([]byte{})\n}\n```\n"
        self.assertIn("func FuzzX", extract_fuzz_harness(out))

    def test_ignores_non_fuzz_go_blocks(self) -> None:
        out = "```go\nfunc TestX(t *testing.T) {}\n```\n"
        self.assertIsNone(extract_fuzz_harness(out))

    def test_target_name_parsed(self) -> None:
        self.assertEqual("FuzzParseFrame",
                         harness_target_name("func FuzzParseFrame(f *testing.F) {}"))

    def test_fixture_metadata_is_self_consistent(self) -> None:
        for name in FIXTURES:
            with self.subTest(fixture=name):
                fx = _load_fixture(name)
                self.assertIn(fx["mutation"]["find"], fx["source"],
                              f"{name}: mutation.find must appear verbatim in sut.go")
                self.assertGreaterEqual(fx["min_seeds"], 3, f"{name}: S1 requires >=3 seeds")
                self.assertEqual("suitable", fx["expected_verdict"])

    def test_fixtures_cover_distinct_fuzz_modes(self) -> None:
        """Two fixtures asserting the same mode would add runtime without adding coverage."""
        modes = {_load_fixture(n)["expected_fuzz_mode"] for n in FIXTURES}
        self.assertEqual(len(FIXTURES), len(modes),
                         f"fixtures must cover distinct fuzz modes, got {modes}")

    def test_every_fixture_dir_is_registered(self) -> None:
        """A fixture directory added on disk but not listed in FIXTURES is never graded."""
        on_disk = {
            entry for entry in os.listdir(EVAL_ROOT)
            if os.path.isfile(os.path.join(EVAL_ROOT, entry, "meta.json"))
        }
        self.assertEqual(on_disk, set(FIXTURES),
                         f"unregistered eval fixtures: {on_disk - set(FIXTURES)}")


@unittest.skipUnless(
    LIVE_CMD and GO,
    "set FUZZING_TEST_SKILL_EVAL_CMD to a shell command that reads a prompt on stdin and "
    "writes the model's skill-driven response to stdout (and have go installed)",
)
class LiveSkillEval(unittest.TestCase):
    """Opt-in: drive a real model through the skill and grade its output."""

    def test_live_model_output_passes_grader(self) -> None:
        runner = _GoRunner(self)
        runner.preflight()
        with open(SKILL_MD, encoding="utf-8") as fh:
            skill = fh.read()
        for name in FIXTURES:
            with self.subTest(fixture=name):
                fixture = _load_fixture(name)
                prompt = (
                    "Follow this fuzzing-test skill exactly and produce its full output "
                    "(applicability verdict, why, action, harness, scorecard, commands). "
                    "The harness must be a single ```go block importing nothing but testing.\n\n"
                    f"{skill}\n\n---\nTarget source (package eval):\n"
                    f"```go\n{fixture['source']}```\n"
                )
                proc = subprocess.run(LIVE_CMD, shell=True, input=prompt,
                                      capture_output=True, text=True, timeout=900)
                passed, reasons = grade(proc.stdout, fixture, runner)
                self.assertTrue(
                    passed,
                    f"{name}: live model output failed grading: {reasons}\n\n{proc.stdout[:2000]}",
                )


if __name__ == "__main__":
    unittest.main()

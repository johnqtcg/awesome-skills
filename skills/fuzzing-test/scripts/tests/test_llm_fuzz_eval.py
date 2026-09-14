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
from pathlib import Path

GO = shutil.which("go")
EVAL_ROOT = os.path.join(os.path.dirname(__file__), "llm_eval")
SKILL_MD = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "SKILL.md")
LIVE_CMD = os.environ.get("FUZZING_TEST_SKILL_EVAL_CMD")

# frame_parser -> parser robustness (Template A); kv_codec -> round-trip, byte-exact codec;
# json_roundtrip -> round-trip, NORMALIZING codec (grades false positives on correct code);
# trivial_add -> the refusal path, where the correct output is no harness at all.
FIXTURES = ("frame_parser", "kv_codec", "json_roundtrip", "split_differential", "trivial_add")

# A harness may legitimately need stdlib helpers (a domain guard needs unicode/utf8). The
# runner assembles the test file, so it must supply the imports the emitted code uses --
# otherwise a correct harness is graded as "does not compile".
_IMPORT_HINTS = {
    "utf8.": "unicode/utf8",
    "utf16.": "unicode/utf16",
    "json.": "encoding/json",
    "bytes.": "bytes",
    "strings.": "strings",
    "fmt.": "fmt",
    "errors.": "errors",
    "reflect.": "reflect",
    "sort.": "sort",
    "time.": "time",
    "math.": "math",
}


def test_file_for(harness: str) -> str:
    """Wrap an emitted harness into a compilable _test.go file."""
    if re.search(r"^\s*import\s*[(\"]", harness, re.M):
        return harness if harness.lstrip().startswith("package ") else "package eval\n\n" + harness
    pkgs = ["testing"] + sorted(
        {pkg for token, pkg in _IMPORT_HINTS.items() if token in harness})
    block = "\n".join(f'\t"{pkg}"' for pkg in pkgs)
    return f"package eval\n\nimport (\n{block}\n)\n\n" + harness

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


# Go prints `--- FAIL: <target>` for BOTH a real finding and an infrastructure failure
# ("context deadline exceeded" / "fuzzing process hung or terminated unexpectedly" when the
# machine is saturated). Only a real finding also reports the input. Treating `--- FAIL`
# alone as a result made the suite fail about 1 run in 4 while every fixture was correct.
_FUZZ_INFRA_MARKERS = (
    "context deadline exceeded",
    "fuzzing process hung or terminated unexpectedly",
    "communicating with fuzzing process",
)


def fuzz_finding(output: str, target: str):
    """Return (verdict, detail): True = real finding, False = clean, None = environment."""
    if not re.search(rf"^\s*--- FAIL: {re.escape(target)}\b", output, re.M):
        # No failure attributed to this target: a failure reported for another target is
        # not this harness's result.
        return (False, "")
    assertion = re.search(r"^\s*\S+_test\.go:\d+: (.+)$", output, re.M)
    if "Failing input written to" in output or assertion:
        return (True, assertion.group(1)[:160] if assertion else "failing input reported")
    if any(marker in output for marker in _FUZZ_INFRA_MARKERS):
        return (None, next(m for m in _FUZZ_INFRA_MARKERS if m in output))
    return (None, "test failed without reporting a failing input")


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
            "sut_test.go": test_file_for(harness),
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

    def fuzz_stays_clean(self, source: str, harness: str, target: str, fuzztime: str):
        """Return (clean, detail) for a bounded fuzz run against the CORRECT source.

        Seed replay only proves the seeds are representable. The fuzzer generates inputs the
        author never wrote, and an oracle that is wrong for the codec fails on those — the
        skill's own Template B asserted raw equality on an `encoding/json` round trip and
        failed in under a second on a correct implementation, with a captured input of
        `string("\x9f")` (invalid UTF-8, which Marshal rewrites to U+FFFD).

        Grading only the mutant cannot see that class of defect: a false-positive harness
        also fails on the mutant, so it scores as a successful detection."""
        root = self._mod(source, harness)
        secs = int(re.sub(r"\D", "", fuzztime) or 10)
        proc = self._run(root, "test", "-run=^$", f"-fuzz=^{target}$",
                         f"-fuzztime={fuzztime}", ".", timeout=secs + 120)
        if proc.returncode == 0:
            return (True, "")
        verdict, detail = fuzz_finding(f"{proc.stdout}\n{proc.stderr}", target)
        if verdict is True:
            return (False, detail)
        self.tc.skipTest(
            f"fuzzing {target} on the correct source exited {proc.returncode} without a "
            f"reported failing input — environment, not result: {detail}")

    def kills_witness(self, source: str, harness: str, target: str, corpus_body: str) -> bool:
        """True iff replaying one KNOWN defect-exposing input fails on this source.

        Deterministic by construction: the input is written into the harness's corpus
        directory and replayed with `-run`, so the grade measures the ORACLE, not whether a
        10s coverage-guided search happened to reach the defect this time. Searching for the
        input made this check intermittently report that a no-oracle harness had 'detected'
        silent corruption (seen twice across full-suite runs)."""
        root = self._mod(source, harness)
        corpus = os.path.join(root, "testdata", "fuzz", target)
        os.makedirs(corpus, exist_ok=True)
        with open(os.path.join(corpus, "witness"), "w", encoding="utf-8") as fh:
            fh.write(corpus_body)
        proc = self._run(root, "test", f"-run=^{target}$", ".")
        if proc.returncode == 0:
            return False
        combined = f"{proc.stdout}\n{proc.stderr}"
        if re.search(rf"^\s*--- FAIL: {re.escape(target)}\b", combined, re.M):
            return True
        self.tc.skipTest(
            f"replaying the witness for {target} exited {proc.returncode} without a test "
            f"failure — an environment failure, not a grading result: {combined[-300:]}")

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
        verdict, detail = fuzz_finding(f"{proc.stdout}\n{proc.stderr}", target)
        if verdict is True:
            return True
        self.tc.skipTest(
            f"fuzzing {target} exited {proc.returncode} without a reported failing input — "
            f"environment, not result: {detail}")


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

    # 1b. Refusal path. A correct response to an unsuitable target writes NO fuzz code, so
    # every check below (mode, scorecard, harness, kill) grades something that must not
    # exist. Without this branch the eval could only ever grade suitable targets, and
    # "always write a harness" scored the same as running the gate.
    if fixture["expected_verdict"] == "not_suitable":
        if extract_fuzz_harness(output) is not None:
            reasons.append("emitted a fuzz harness for a target the gate must refuse")
        for phrase in fixture.get("expected_refusal_signals", []):
            if phrase.lower() not in low:
                reasons.append(f"refusal does not point at an alternative ({phrase!r} absent)")
        if "fuzztime" in low:
            reasons.append("suggested a fuzz command for a target that failed the gate")
        return (len(reasons) == 0, reasons)

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

    # Seeds passing is not enough: the oracle must also hold for inputs the FUZZER invents.
    clean, detail = runner.fuzz_stays_clean(
        fixture["source"], harness, target, fixture.get("fuzztime_clean", "10s"))
    if not clean:
        reasons.append(
            "emitted harness FAILS under fuzzing on the CORRECT implementation "
            f"(false positive — wrong oracle or missing domain guard): {detail}")

    mutated = fixture["source"].replace(mut["find"], mut["replace"])
    # Graded deterministically against a known defect-exposing input: this measures the
    # oracle. Whether the harness's own seeds plus a bounded search REACH the defect is a
    # separate (stochastic) property, asserted in the fixture self-tests, not here.
    if not runner.kills_witness(mutated, harness, target, fixture["witness_corpus"]):
        reasons.append(
            f"emitted harness does NOT find the seeded defect ({mut['defect']}) "
            f"even when the defect-exposing input is replayed — no oracle, or the guard "
            f"skips it"
        )

    # BOTH directions, for the graded candidate and not only for the built-in exemplars:
    # the witness must fail on the mutant AND pass on the correct source. Checking only the
    # first half scored a harness that `t.Fatal`s on that exact legal input as (True, []).
    if runner.kills_witness(fixture["source"], harness, target, fixture["witness_corpus"]):
        reasons.append(
            "emitted harness FAILS on the CORRECT implementation for the defect-exposing "
            "input (false positive: it rejects an input the contract requires to work)"
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

    # A harness that is correct in every graded respect EXCEPT that it rejects one legal
    # input. Constructed as a counter-example to mutant-only grading: it kills the mutation,
    # compiles, has enough seeds, and declares the right mode — and it is still wrong.
    REJECTS_A_LEGAL_INPUT = """`Applicability Verdict: Suitable for fuzzing`

Fuzz mode: **round-trip**. Scorecard below.

```go
func FuzzRoundTripRecord(f *testing.F) {
	f.Add("", int32(0))
	f.Add("key", int32(1))
	f.Add("other", int32(7))

	f.Fuzz(func(t *testing.T, key string, value int32) {
		if len(key) > 255 {
			t.Skip()
		}
		if key == "k" && value == -1 {
			t.Fatalf("rejects a legal input")
		}
		orig := Record{Key: key, Value: value}
		enc, err := Encode(orig)
		if err != nil {
			t.Skip()
		}
		got, err := Decode(enc)
		if err != nil {
			t.Fatalf("decode(encode(x)) failed: %v", err)
		}
		if got != orig {
			t.Fatalf("round-trip mismatch: got=%+v want=%+v", got, orig)
		}
	})
}
```

## Quality Scorecard
| C1 | ok | Pass |
"""

    def test_grader_rejects_a_harness_that_fails_the_witness_on_correct_code(self) -> None:
        """The witness must be checked in BOTH directions for the graded candidate.

        Before this, the grader replayed the witness only against the mutant, so a harness
        that `t.Fatal`s on that exact legal input graded `(True, [])` while failing on the
        correct implementation."""
        fx = _load_fixture("kv_codec")
        passed, reasons = grade(self.REJECTS_A_LEGAL_INPUT, fx, self.runner)
        self.assertFalse(passed, "a harness that rejects a legal input must not pass")
        joined = " | ".join(reasons)
        self.assertIn("FAILS on the CORRECT implementation for the defect-exposing input",
                      joined,
                      f"expected the deterministic witness complaint; got {joined}")

    def test_grader_fails_bad_exemplars(self) -> None:
        for name in FIXTURES:
            with self.subTest(fixture=name):
                fx = _load_fixture(name)
                passed, reasons = grade(self._read(fx, "bad.md"), fx, self.runner)
                self.assertFalse(passed, f"{name}: bad exemplar must not pass")
                joined = " | ".join(reasons)
                # And for the RIGHT reasons -- each fixture declares which defect its bad
                # exemplar demonstrates, so a fixture cannot pass on an unrelated complaint.
                for expected in fx["bad_expected_reasons"]:
                    self.assertIn(expected, joined,
                                  f"{name}: expected {expected!r} in the grade; got {joined}")

    def test_mutation_is_reachable_at_all(self) -> None:
        """Guard against a fixture that can never fail: the good harness must find the
        defect, and the correct source must survive it. Without this, a broken mutation
        would silently make every kill check vacuous."""
        for name in FIXTURES:
            with self.subTest(fixture=name):
                fx = _load_fixture(name)
                if fx["expected_verdict"] == "not_suitable":
                    continue  # no harness to grade
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

    def test_witness_is_a_defect_exposer_not_a_universal_failure(self) -> None:
        """The graded kill check replays a witness input. If that input also failed on the
        CORRECT source, every harness would 'kill' the mutation and the check would be
        vacuous in the opposite direction."""
        for name in FIXTURES:
            with self.subTest(fixture=name):
                fx = _load_fixture(name)
                if fx["expected_verdict"] == "not_suitable":
                    continue  # no harness to grade
                harness = extract_fuzz_harness(self._read(fx, "good.md"))
                target = harness_target_name(harness)
                mutated = fx["source"].replace(fx["mutation"]["find"], fx["mutation"]["replace"])
                self.assertTrue(
                    self.runner.kills_witness(mutated, harness, target, fx["witness_corpus"]),
                    f"{name}: witness does not expose the defect — kill check is vacuous")
                self.assertFalse(
                    self.runner.kills_witness(fx["source"], harness, target, fx["witness_corpus"]),
                    f"{name}: witness fails on the CORRECT source — every harness would pass")

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
                if fx["expected_verdict"] == "not_suitable":
                    self.assertIsNone(
                        extract_fuzz_harness(self._read(fx, "good.md")),
                        f"{name}: a correct refusal must emit no harness at all")
                    continue
                harness = extract_fuzz_harness(self._read(fx, "good.md"))
                self.assertTrue(
                    self.runner.replay_passes(fx["source"], harness,
                                              harness_target_name(harness)),
                    f"{name}: exemplar seeds fail on the correct implementation",
                )


class FuzzOutputClassificationTests(unittest.TestCase):
    """`--- FAIL` is not a fuzzing result on its own.

    Go prints it both for a real finding and for its own infrastructure giving up under a
    saturated machine ("context deadline exceeded"), with no failing input. Reading the
    second as the first made the suite red about 1 run in 4 while every fixture was
    correct. These cases are synthetic on purpose: the real thing is not reproducible on
    demand, so the classifier is unit-tested instead of waited for."""

    REAL = (
        "fuzz: elapsed: 0s, gathering baseline coverage: 3/3 completed\n"
        "--- FAIL: FuzzRoundTripRecord (0.05s)\n"
        "    sut_test.go:21: round-trip mismatch: got={Key:k Value:16777215} want={Key:k Value:-1}\n"
        "    Failing input written to testdata/fuzz/FuzzRoundTripRecord/9a1b\n"
    )
    INFRA = (
        "fuzz: elapsed: 3s, execs: 1515207 (504999/sec), new interesting: 1 (total: 4)\n"
        "--- FAIL: FuzzRoundTripRecord (5.10s)\n"
        "    context deadline exceeded\n"
    )
    HUNG = (
        "--- FAIL: FuzzRoundTripRecord (7.02s)\n"
        "    fuzzing process hung or terminated unexpectedly: exit status 2\n"
    )
    CLEAN = "fuzz: elapsed: 5s, execs: 2641878 (536618/sec)\nPASS\nok  \teval\t5.4s\n"

    def test_real_finding_is_reported(self) -> None:
        verdict, detail = fuzz_finding(self.REAL, "FuzzRoundTripRecord")
        self.assertIs(True, verdict)
        self.assertIn("round-trip mismatch", detail)

    def test_infrastructure_failure_is_not_a_finding(self) -> None:
        for output, label in ((self.INFRA, "deadline"), (self.HUNG, "hung")):
            with self.subTest(case=label):
                verdict, detail = fuzz_finding(output, "FuzzRoundTripRecord")
                self.assertIsNone(verdict, f"{label}: infra failure graded as a finding")
                self.assertTrue(detail)

    def test_clean_run_is_clean(self) -> None:
        self.assertEqual((False, ""), fuzz_finding(self.CLEAN, "FuzzRoundTripRecord"))

    def test_finding_for_another_target_is_not_this_target(self) -> None:
        other = self.REAL.replace("FuzzRoundTripRecord", "FuzzSomethingElse")
        verdict, _ = fuzz_finding(other, "FuzzRoundTripRecord")
        self.assertIsNot(True, verdict)


class GraderDeterminismTests(unittest.TestCase):
    """The graded kill check must not depend on a coverage-guided search finding the
    defect in N seconds; it replays a declared witness input."""

    SOURCE = (Path(__file__).resolve().parent.parent.parent / "scripts" / "tests"
              / "test_llm_fuzz_eval.py").read_text(encoding="utf-8")

    def test_grade_uses_the_witness_replay_for_the_kill_check(self) -> None:
        m = re.search(r"\ndef grade\(.*?(?=\n(?:@|class |def ))", self.SOURCE, re.S)
        self.assertIsNotNone(m, "could not isolate grade()")
        grade_src = m.group(0)
        self.assertIn("kills_witness(", grade_src,
                      "the graded kill check must replay the declared witness")
        self.assertNotIn("fuzz_finds_defect(", grade_src,
                         "grading on a timed search reintroduces a stochastic verdict")

    def test_witness_replay_uses_run_not_fuzz(self) -> None:
        body = self.SOURCE.split("def kills_witness(", 1)[1].split("\n    def ", 1)[0]
        self.assertIn("-run=^", body, "the witness check must replay, not search")
        self.assertNotIn("-fuzz=", body, "the witness check must not start a fuzzing search")


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
                if fx["expected_verdict"] == "not_suitable":
                    # A refusal fixture has no harness to grade, so it declares no mutation.
                    self.assertNotIn("mutation", fx, f"{name}: refusal fixture needs no mutation")
                    self.assertTrue(fx.get("expected_refusal_signals"),
                                    f"{name}: must declare what a good refusal points at")
                    continue
                self.assertIn(fx["mutation"]["find"], fx["source"],
                              f"{name}: mutation.find must appear verbatim in sut.go")
                self.assertGreaterEqual(fx["min_seeds"], 3, f"{name}: S1 requires >=3 seeds")
                self.assertTrue(fx.get("witness_corpus"),
                                f"{name}: needs a witness corpus entry for the kill check")

    def test_fixtures_cover_every_fuzz_mode(self) -> None:
        """Each fuzz mode with a compile-and-kill scenario must be graded at least once."""
        modes = {_load_fixture(n).get("expected_fuzz_mode") for n in FIXTURES
                 if _load_fixture(n)["expected_verdict"] == "suitable"}
        self.assertEqual({"parser robustness", "round-trip", "differential"}, modes,
                         f"fixtures must cover parser + round-trip + differential, got {modes}")

    def test_each_fixture_grades_a_distinct_defect(self) -> None:
        """A fixture costs a fuzz run, so it must add a grading axis, not repeat one.

        Sharing a mode is allowed -- json_roundtrip and kv_codec are both round-trip, but
        one grades 'finds real corruption' and the other 'does not false-positive on the
        correct implementation'. Repeating BOTH the mode and the expected defect would not."""
        seen = {}
        for name in FIXTURES:
            fx = _load_fixture(name)
            key = (fx.get("expected_fuzz_mode", "n/a"), tuple(sorted(fx["bad_expected_reasons"])))
            self.assertNotIn(key, seen,
                             f"{name} duplicates {seen.get(key)}: same mode and same graded defect")
            seen[key] = name

    def test_every_fixture_declares_expected_bad_reasons(self) -> None:
        for name in FIXTURES:
            fx = _load_fixture(name)
            self.assertTrue(fx.get("bad_expected_reasons"),
                            f"{name}: meta.json must declare bad_expected_reasons")

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
                    "(applicability verdict, why, action, and — only if the gate passes — "
                    "harness, scorecard, commands). Put any harness in a single ```go block; "
                    "the runner supplies the imports it detects.\n\n"
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

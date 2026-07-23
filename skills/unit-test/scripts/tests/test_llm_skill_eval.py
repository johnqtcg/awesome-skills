"""End-to-end skill-output eval: a GRADER for what a model produces when driven by
the unit-test skill, plus fixtures and a self-test that the grader actually
discriminates good from bad.

The gap this addresses (see COVERAGE.md): every other test validates the skill
*document* or the *methodology on fixed fixtures*. None grades an actual
skill-driven response. A true live eval needs a model in the loop, which cannot
run deterministically in this zero-LLM suite — so this file ships:

  1. A `grade(output, fixture)` function that scores a response on the dimensions
     the reviewer named: correct mode, real defect hypotheses, a test that
     COMPILES and KILLS the mutation, and a compliant scorecard + JSON.
  2. Two hand-authored exemplars (good, bad) and a self-test proving the grader
     PASSES the good one and FAILS the bad one — so the grader is not a rubber
     stamp. This runs in CI (needs `go` for the compile/kill check; skips without).
  3. An opt-in live hook (`UNIT_TEST_SKILL_EVAL_CMD`) that runs a real model and
     grades its output. Skipped unless configured — that is the remaining step to
     a full behavioral eval, now a drop-in rather than a rewrite.

Honesty: (1)+(2) prove the *grader* works; they do not prove a live model passes.
Only the opt-in (3), once wired to a backend, does that.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

GO = shutil.which("go")
FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "llm_eval", "slice_transform")
LIVE_CMD = os.environ.get("UNIT_TEST_SKILL_EVAL_CMD")


def _load_fixture() -> dict:
    with open(os.path.join(FIXTURE_DIR, "meta.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    with open(os.path.join(FIXTURE_DIR, "sut.go"), encoding="utf-8") as fh:
        meta["source"] = fh.read()
    return meta


def _go_env(root: str) -> dict:
    env = dict(os.environ)
    env.pop("GOROOT", None)  # see test_behavioral_killer._go_env for why
    env["GOTOOLCHAIN"] = "local"
    env["GOFLAGS"] = "-count=1"
    env["GOCACHE"] = os.path.join(root, ".gocache")
    env["GOMODCACHE"] = os.path.join(root, ".gomod")
    env["GOPATH"] = os.path.join(root, ".gopath")
    return env


def _extract_go_test(output: str):
    """Return the first ```go fenced block that contains a test function, or None."""
    for block in re.findall(r"```go\s*\n(.*?)```", output, re.S):
        if "func Test" in block:
            return block
    return None


class _GoRunner:
    """Minimal compile-and-run helper; raises unittest.SkipTest on env failure."""

    def __init__(self, test_case: unittest.TestCase):
        self.tc = test_case

    def _mod(self, files: dict) -> str:
        try:
            root = tempfile.mkdtemp(prefix="llm-eval-")
        except OSError as exc:
            self.tc.skipTest(f"cannot create temp dir: {exc}")
        self.tc.addCleanup(shutil.rmtree, root, ignore_errors=True)
        for name, content in files.items():
            path = os.path.join(root, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
        return root

    def _run(self, root: str, *args: str) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                [GO, *args], cwd=root, env=_go_env(root),
                capture_output=True, text=True, timeout=180,
            )
        except OSError as exc:
            self.tc.skipTest(f"cannot exec go: {exc}")

    def preflight(self):
        root = self._mod({"go.mod": "module pf\n\ngo 1.22\n", "m.go": "package main\n\nfunc main() {}\n"})
        if self._run(root, "build", "./...").returncode != 0:
            self.tc.skipTest("go cannot compile in this environment")

    def test_passes(self, source: str, go_test: str) -> bool:
        """True iff `go test` passes with this source + test."""
        root = self._mod({"go.mod": "module eval\n\ngo 1.22\n", "sut.go": source, "sut_test.go": go_test})
        return self._run(root, "test", "./...").returncode == 0


def grade(output: str, fixture: dict, runner: "_GoRunner"):
    """Return (passed: bool, reasons: list[str]). Runs ALL checks (no short-circuit)
    so a caller can see every way a response falls short."""
    reasons = []

    # 1. Correct execution mode declared.
    m = re.search(r"Mode[:*\s]+(Light|Standard|Strict)", output)
    declared = m.group(1) if m else None
    if declared != fixture["expected_mode"]:
        reasons.append(f"mode: declared {declared!r}, expected {fixture['expected_mode']!r}")

    # 2. Real defect hypotheses (>= min distinct keywords).
    low = output.lower()
    hits = [k for k in fixture["hypothesis_keywords"] if k.lower() in low]
    if len(hits) < fixture["min_hypothesis_keywords"]:
        reasons.append(f"hypotheses: found {hits}, need >= {fixture['min_hypothesis_keywords']}")

    # 3. Scorecard + machine-readable JSON present.
    if "scorecard" not in low:
        reasons.append("no scorecard section")
    if not re.search(r"```json\s*\n", output):
        reasons.append("no JSON summary block")

    # 4. Behavioral: the emitted test must COMPILE + PASS on the correct source,
    #    and FAIL on the mutation (i.e. it actually kills the defect).
    go_test = _extract_go_test(output)
    if go_test is None:
        reasons.append("no Go test block found")
    else:
        mut = fixture["mutation"]
        if mut["find"] not in fixture["source"]:
            reasons.append("fixture drift: mutation target not found in source")
        else:
            mutated = fixture["source"].replace(mut["find"], mut["replace"])
            if not runner.test_passes(fixture["source"], go_test):
                reasons.append("emitted test does not pass on the correct implementation")
            if runner.test_passes(mutated, go_test):
                reasons.append("emitted test does NOT kill the mutation (weak assertion)")

    return (len(reasons) == 0, reasons)


@unittest.skipIf(GO is None, "go toolchain not installed")
class GraderSelfTest(unittest.TestCase):
    """Prove the grader discriminates: PASS the good exemplar, FAIL the bad one."""

    def setUp(self):
        self.fixture = _load_fixture()
        self.runner = _GoRunner(self)
        self.runner.preflight()

    def _read(self, name: str) -> str:
        with open(os.path.join(FIXTURE_DIR, name), encoding="utf-8") as fh:
            return fh.read()

    def test_grader_passes_good_exemplar(self):
        passed, reasons = grade(self._read("good.md"), self.fixture, self.runner)
        self.assertTrue(passed, f"good exemplar should pass; reasons: {reasons}")

    def test_grader_fails_bad_exemplar(self):
        passed, reasons = grade(self._read("bad.md"), self.fixture, self.runner)
        self.assertFalse(passed, "bad exemplar must not pass the grader")
        # And for the RIGHT reasons: wrong mode AND a weak test that misses the bug.
        joined = " | ".join(reasons)
        self.assertIn("mode", joined)
        self.assertIn("kill the mutation", joined)


@unittest.skipUnless(
    LIVE_CMD and GO,
    "set UNIT_TEST_SKILL_EVAL_CMD to a shell command that reads a prompt on stdin "
    "and writes the model's skill-driven response to stdout (and have go installed)",
)
class LiveSkillEval(unittest.TestCase):
    """Opt-in: drive a real model through the skill and grade its output."""

    def test_live_model_output_passes_grader(self):
        fixture = _load_fixture()
        runner = _GoRunner(self)
        runner.preflight()
        skill_md = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "SKILL.md")
        with open(skill_md, encoding="utf-8") as fh:
            skill = fh.read()
        prompt = (
            "Follow this unit-test skill exactly and produce its full output "
            "(mode, failure hypotheses, killer case with a Go test, scorecard, JSON):\n\n"
            f"{skill}\n\n---\nTarget source (package sut):\n```go\n{fixture['source']}```\n"
        )
        proc = subprocess.run(LIVE_CMD, shell=True, input=prompt,
                              capture_output=True, text=True, timeout=900)
        passed, reasons = grade(proc.stdout, fixture, runner)
        self.assertTrue(passed, f"live model output failed grading: {reasons}\n\n{proc.stdout[:2000]}")


if __name__ == "__main__":
    unittest.main()
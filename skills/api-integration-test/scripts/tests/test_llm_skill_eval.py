#!/usr/bin/env python3
"""Skill-output eval for api-integration-test: a GRADER for what a model produces when
driven by this skill, plus fixtures and a self-test proving the grader discriminates.

The gap this closes (COVERAGE.md Known Gap 1). The three existing layers are:

  * contract + golden — assert that rule TEXT exists in the skill;
  * behavioral        — compiles a fixture THIS REPO wrote and proves the prescribed
                        gate logic works.

None of them looks at a response. A model could name every gate, ship a scorecard claiming
4/4 Critical, and emit a test that `t.Skip`s on missing config and trusts `ENV` alone —
the exact false-green this skill exists to prevent — and score perfectly.

So the grader RUNS the emitted test. Each fixture declares an `env_matrix`: a set of
environments and the outcome the skill's §Skip vs Fail rules require of each. Crucially
**every graded case refuses before any network call**, which is the whole point of the
gates, so nothing here needs a server or a bindable socket:

    gate unset ................................. must SKIP
    gate on, a required var missing ............ must REFUSE  (t.Skip here false-greens CI)
    gate on, ENV=production .................... must REFUSE  (the label path)
    gate on, bare host with no scheme .......... must REFUSE  (url.Parse fails open)
    gate on, host off NONPROD_HOST_ALLOWLIST ... must REFUSE  (the real host check)
    gate on, no TEST_TENANT_ALLOWLIST .......... must REFUSE  (allowlist, not denylist)
    gate on, tenant off the allowlist .......... must REFUSE
    gate on, fully valid non-prod .............. must REACH THE CALL

"REFUSE" is stronger than "fail": the run must fail *without attempting the call*. A plain
`fail` is satisfied by a response that ignores the host check, dials the prod target and
fails on DNS — scoring a correct refusal for doing the exact dangerous thing. And the last
row is the clean arm, not optional: without it a test that calls `t.Fatalf` unconditionally
satisfies all six refusals and scores perfectly. Every host is loopback or an undiallable
bare name, so the matrix cannot reach anything real even when the response is wrong, and a
non-refusing response fails with a local `connection refused` whose wording is stable.

The second fixture grades the **refusal** path — the Scope Validation Gate's hard stop —
because a skill whose first gate can say "stop" must be graded on stopping. Without it,
"always write an integration test" scores exactly as well as running gate 1.

Honesty: this proves the GRADER works and that the two hand-authored exemplars are
separated correctly. It does not prove a live model passes; that is the opt-in
`LiveSkillEval` below, which is skipped unless `API_INTEGRATION_SKILL_EVAL_CMD` is set.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

GO = shutil.which("go")
EVAL_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "llm_eval")
SKILL_MD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "SKILL.md")
LIVE_CMD = os.environ.get("API_INTEGRATION_SKILL_EVAL_CMD")

_GO_MOD = "module sut\n\ngo 1.22\n"


def fixture_dirs() -> list:
    """Every directory under `llm_eval/` carrying a `meta.json`.

    Discovery, not a hand-maintained tuple: a fixture added without being registered
    somewhere is a fixture nothing runs, and a list that must agree with the filesystem is
    a second copy of what the filesystem already knows."""
    if not os.path.isdir(EVAL_ROOT):
        return []
    return sorted(os.path.join(EVAL_ROOT, n) for n in os.listdir(EVAL_ROOT)
                  if os.path.isfile(os.path.join(EVAL_ROOT, n, "meta.json")))


def load_fixture(path: str) -> dict:
    with open(os.path.join(path, "meta.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    with open(os.path.join(path, "sut.go"), encoding="utf-8") as fh:
        meta["source"] = fh.read()
    meta["_dir"] = path
    return meta


def extract_go_test(output: str):
    """Return the first ```go fenced block containing a Go test function, or None."""
    for block in re.findall(r"```go\s*\n(.*?)```", output, re.S):
        if re.search(r"func Test\w*\(\w+ \*testing\.T\)", block):
            return block
    return None


def _go_env(root: str) -> dict:
    env = dict(os.environ)
    env.pop("GOROOT", None)          # an inherited GOROOT from another toolchain breaks every build
    env["GOTOOLCHAIN"] = "local"
    env["GOCACHE"] = os.path.join(root, ".gocache")
    env["GOMODCACHE"] = os.path.join(root, ".gomod")
    env["GOPATH"] = os.path.join(root, ".gopath")
    # Never inherit the operator's own integration config into a graded run: it would
    # silently satisfy a matrix case that is supposed to be missing a variable.
    for k in list(env):
        if k.startswith(("INTERNAL_API_", "INTEGRATION_", "TEST_TENANT", "TEST_USER",
                         "NONPROD_HOST", "API_BASE_URL")) or k == "ENV":
            env.pop(k)
    return env


class _GoRunner:
    """Compile-and-run helper. Raises SkipTest only on a genuine environment limit."""

    def __init__(self, tc: unittest.TestCase):
        self.tc = tc

    def _module(self, source: str, go_test: str) -> str:
        try:
            root = tempfile.mkdtemp(prefix="aip-skilleval-")
        except OSError as exc:
            self.tc.skipTest(f"cannot create temp dir: {exc}")
        self.tc.addCleanup(shutil.rmtree, root, ignore_errors=True)
        body = go_test if go_test.lstrip().startswith(("//go:build", "package ")) else \
            "//go:build integration\n\npackage sut\n\n" + go_test
        for name, content in (("go.mod", _GO_MOD), ("sut.go", source),
                              ("emitted_integration_test.go", body)):
            with open(os.path.join(root, name), "w", encoding="utf-8") as fh:
                fh.write(content)
        return root

    def preflight(self):
        root = self._module("package sut\n", "//go:build integration\n\npackage sut\n")
        proc = self._exec(root, {}, build_only=True)
        if proc.returncode != 0:
            self.tc.skipTest(f"go cannot compile in this environment: {proc.stderr[-200:]}")

    def _exec(self, root: str, env_extra: dict, build_only: bool = False):
        args = [GO, "build" if build_only else "test", "-tags=integration"]
        if not build_only:
            args += ["-v", "-count=1"]
        args += ["./..."]
        env = _go_env(root)
        env.update(env_extra)
        try:
            return subprocess.run(args, cwd=root, env=env, capture_output=True,
                                  text=True, timeout=180)
        except OSError as exc:
            self.tc.skipTest(f"cannot exec go: {exc}")

    def compiles(self, source: str, go_test: str):
        root = self._module(source, go_test)
        proc = self._exec(root, {}, build_only=True)
        return proc.returncode == 0, (proc.stdout + proc.stderr)[-400:]

    def run_case(self, source: str, go_test: str, env: dict):
        """Return (outcome, combined_output) with outcome in {skip, fail, pass}."""
        root = self._module(source, go_test)
        proc = self._exec(root, env)
        out = proc.stdout + proc.stderr
        if "bind: operation not permitted" in out or "socket: operation not permitted" in out:
            self.tc.skipTest("environment denies binding a local socket (sandbox)")
        if re.search(r"^\s*--- FAIL", out, re.M) or proc.returncode != 0:
            return "fail", out
        if re.search(r"^\s*--- SKIP", out, re.M):
            return "skip", out
        return "pass", out


def grade_refusal(output: str, fixture: dict):
    """Grade a response to an OUT-OF-SCOPE target: verdict, redirect, reason, no code."""
    reasons = []
    for pat in fixture.get("required_report_patterns", []):
        if not re.search(pat["regex"], output):
            reasons.append(f"missing {pat['name']}")
    for pat in fixture.get("forbidden_report_patterns", []):
        if re.search(pat["regex"], output):
            reasons.append(f"ran a gate the hard stop forbids: {pat['name']}")
    if extract_go_test(output) is not None:
        reasons.append("emitted test code for an out-of-scope target — gate 1 is a HARD "
                       "STOP, not a warning to note and then proceed")
    return (len(reasons) == 0, reasons)


def grade(output: str, fixture: dict, runner: "_GoRunner"):
    """Return (passed, reasons). No short-circuit: a caller sees every shortfall."""
    if fixture["expected_scope"] == "out_of_scope":
        return grade_refusal(output, fixture)

    reasons = []
    for pat in fixture.get("required_report_patterns", []):
        if not re.search(pat["regex"], output):
            reasons.append(f"report is missing {pat['name']}")

    go_test = extract_go_test(output)
    if go_test is None:
        reasons.append("no Go test found (```go block with func TestXxx(t *testing.T))")
        return (False, reasons)

    tag = fixture.get("must_contain_build_tag")
    if tag and tag not in go_test and tag not in output:
        reasons.append(f"emitted test carries no {tag} constraint — it would run in the "
                       f"default unit-test suite")

    ok, detail = runner.compiles(fixture["source"], go_test)
    if not ok:
        reasons.append(f"emitted test does not compile: {detail}")
        return (len(reasons) == 0, reasons)

    markers = fixture.get("network_markers", [])
    for case in fixture["env_matrix"]:
        outcome, out = runner.run_case(fixture["source"], go_test, case["env"])
        want = case["expect"]
        touched_network = any(m.lower() in out.lower() for m in markers)

        if want == "skip":
            if outcome != "skip":
                reasons.append(f"env matrix [{case['name']}]: got {outcome}, want skip — "
                               f"{case['why']}")
        elif want == "refused":
            # `fail` alone is NOT enough. A response that ignores the prod host dials it
            # and fails on DNS — which would score as a correct refusal while doing the
            # exact dangerous thing the gate exists to prevent. The gate must stop it
            # BEFORE any call, so a network attempt disqualifies the case.
            if outcome != "fail":
                reasons.append(f"env matrix [{case['name']}]: got {outcome}, want a hard "
                               f"failure — {case['why']}")
            elif touched_network:
                hit = next(m for m in markers if m.lower() in out.lower())
                reasons.append(f"env matrix [{case['name']}]: failed only AFTER attempting "
                               f"the call ({hit!r} in the output) — the gate must refuse "
                               f"before any network access. {case['why']}")
        elif want == "reached_call":
            # The clean arm: the gates must not refuse a legitimate config.
            if outcome == "skip":
                reasons.append(f"env matrix [{case['name']}]: skipped a fully valid "
                               f"configuration — {case['why']}")
            elif not touched_network:
                reasons.append(f"env matrix [{case['name']}]: never attempted the call, so "
                               f"a gate refused a legitimate non-prod target — "
                               f"{case['why']}")
        else:
            reasons.append(f"fixture defect: unknown expectation {want!r}")
    return (len(reasons) == 0, reasons)


@unittest.skipIf(GO is None, "go toolchain not installed")
class SkillOutputGraderTests(unittest.TestCase):
    """Prove the grader discriminates: PASS every good exemplar, FAIL every bad one."""

    def setUp(self):
        self.runner = _GoRunner(self)
        self.runner.preflight()

    @staticmethod
    def _read(fixture_dir: str, name: str) -> str:
        with open(os.path.join(fixture_dir, name), encoding="utf-8") as fh:
            return fh.read()

    def test_at_least_two_fixtures_and_both_paths_are_covered(self):
        """Anti-vacuity. A loop over an empty discovery reads as green, and a corpus with
        no refusal fixture cannot grade the gate that says 'stop'."""
        found = fixture_dirs()
        self.assertGreaterEqual(len(found), 2,
                                f"discovery found {[os.path.basename(d) for d in found]}")
        scopes = {load_fixture(d)["expected_scope"] for d in found}
        self.assertEqual({"in_scope", "out_of_scope"}, scopes,
                         "the corpus must grade both the authoring path and the hard stop")

    def test_every_good_exemplar_passes(self):
        for d in fixture_dirs():
            with self.subTest(fixture=os.path.basename(d)):
                fx = load_fixture(d)
                passed, reasons = grade(self._read(d, "good.md"), fx, self.runner)
                self.assertTrue(passed, f"{fx['id']}/good.md should pass: {reasons}")

    def test_every_bad_exemplar_fails(self):
        for d in fixture_dirs():
            with self.subTest(fixture=os.path.basename(d)):
                fx = load_fixture(d)
                passed, reasons = grade(self._read(d, "bad.md"), fx, self.runner)
                self.assertFalse(passed, f"{fx['id']}/bad.md must not pass")
                joined = " | ".join(reasons)
                for expected in fx["bad_expected_reasons"]:
                    self.assertIn(expected, joined,
                                  f"{fx['id']}/bad.md failed, but not for the declared "
                                  f"reason {expected!r}: {joined}")

    def test_the_plausible_bad_response_fails_only_on_behaviour(self):
        """`user_profile_http/bad.md` runs every gate, declares the right scope, mode and
        degradation level, ships the `-count=1` command and a 4/4 Critical scorecard. Every
        text check passes it. It must fail on the env matrix and nothing else — a grader
        that also rejected its prose would be right by accident."""
        d = os.path.join(EVAL_ROOT, "user_profile_http")
        passed, reasons = grade(self._read(d, "bad.md"), load_fixture(d), self.runner)
        self.assertFalse(passed)
        for r in reasons:
            self.assertTrue(r.startswith("env matrix ["),
                            f"rejected for a non-behavioural reason: {r}")
        # And specifically each of its three real defects: t.Skip instead of t.Fatalf on
        # missing config, an ENV-only prod check, and no tenant validation at all.
        joined = " | ".join(reasons)
        for name in ("required var missing", "not on NONPROD_HOST_ALLOWLIST",
                     "no TEST_TENANT_ALLOWLIST", "tenant not on the allowlist"):
            self.assertIn(name, joined, f"the matrix did not catch: {name}")
        self.assertIn("failed only AFTER attempting the call", joined,
                      "the prod-host and tenant rows must be caught for dialling, not "
                      "merely for failing — any failure would satisfy a plain `fail`")

    def test_the_good_exemplar_is_not_passing_by_refusing_everything(self):
        """The clean arm, checked directly: a test that `t.Fatalf`s unconditionally would
        satisfy all six refusal rows. Only the `reached_call` row separates a correct gate
        from a paranoid one, so prove that row can fail."""
        d = os.path.join(EVAL_ROOT, "user_profile_http")
        fx = load_fixture(d)
        always_fatal = (
            'func TestAlwaysRefuse_Integration(t *testing.T) {\n'
            '\tif os.Getenv("INTERNAL_API_INTEGRATION") != "1" {\n'
            '\t\tt.Skip("set INTERNAL_API_INTEGRATION=1 to run")\n\t}\n'
            '\tt.Fatalf("refuse production target")\n}\n')
        harness = ("//go:build integration\n\npackage sut\n\nimport (\n\t\"os\"\n"
                   "\t\"testing\"\n)\n\n" + always_fatal)
        passed, reasons = grade(f"Mode: Standard\n\n```go\n{harness}```\n", fx, self.runner)
        self.assertFalse(passed)
        self.assertTrue(any("refused a legitimate" in r for r in reasons),
                        f"the clean arm did not fire: {reasons}")


class GraderUnitTests(unittest.TestCase):
    """Go-free checks on the grader and the fixture metadata."""

    def test_extracts_the_go_test_and_ignores_other_blocks(self):
        out = ("```go\npackage sut\n\nfunc Helper() {}\n```\n"
               "```go\nfunc TestX_Integration(t *testing.T) {}\n```\n")
        self.assertIn("func TestX_Integration", extract_go_test(out))
        self.assertIsNone(extract_go_test("```go\nvar x = 1\n```\n"))

    def test_every_fixture_declares_what_its_bad_exemplar_must_fail_on(self):
        for d in fixture_dirs():
            with self.subTest(fixture=os.path.basename(d)):
                fx = load_fixture(d)
                self.assertTrue(fx.get("bad_expected_reasons"),
                                "a bad exemplar that may fail for any reason grades nothing")

    def test_every_fixture_ships_all_four_files(self):
        for d in fixture_dirs():
            for name in ("meta.json", "sut.go", "good.md", "bad.md"):
                with self.subTest(fixture=os.path.basename(d), file=name):
                    self.assertTrue(os.path.isfile(os.path.join(d, name)))

    def test_the_in_scope_matrix_covers_every_skip_vs_fail_row(self):
        """The matrix is the executable form of SKILL.md §Skip vs Fail. If it stops
        covering a row, that row goes back to being prose nobody checks."""
        fx = load_fixture(os.path.join(EVAL_ROOT, "user_profile_http"))
        expects = [c["expect"] for c in fx["env_matrix"]]
        self.assertGreaterEqual(expects.count("refused"), 5,
                                "the matrix must exercise every 'requested but broken' row")
        self.assertIn("skip", expects, "the opt-out row must be covered")
        self.assertIn("reached_call", expects, "the clean arm must be covered")

    def test_matrix_environments_never_leak_a_real_gate_variable(self):
        """A graded case that is supposed to be MISSING a variable must not pick it up from
        the operator's shell; `_go_env` strips them. Assert the stripping, not the comment."""
        env = _go_env("/tmp/x")
        for leaked in ("INTERNAL_API_INTEGRATION", "TEST_TENANT_ALLOWLIST", "API_BASE_URL",
                       "ENV", "INTEGRATION_ALLOW_PROD"):
            self.assertNotIn(leaked, env, f"{leaked} leaks from the parent environment")


@unittest.skipUnless(
    LIVE_CMD and GO,
    "set API_INTEGRATION_SKILL_EVAL_CMD to a shell command that reads a prompt on stdin "
    "and writes the model's skill-driven response to stdout (and have go installed)",
)
class LiveSkillEval(unittest.TestCase):
    """Opt-in: drive a real model through the skill and grade its output with the same
    `grade()`. Runs every discovered fixture — grading only the in-scope one would leave
    the hard stop unmeasured, which is the gap the refusal fixture exists to close."""

    def test_live_model_output_passes_grader(self):
        runner = _GoRunner(self)
        runner.preflight()
        with open(SKILL_MD, encoding="utf-8") as fh:
            skill = fh.read()
        for d in fixture_dirs():
            fx = load_fixture(d)
            with self.subTest(fixture=fx["id"]):
                prompt = (
                    "Follow this api-integration-test skill exactly and produce its full "
                    "output (scope verdict, gates, mode, degradation level, any test code, "
                    "commands, and the output contract):\n\n"
                    f"{skill}\n\n---\nTarget source (package {fx['package']}):\n"
                    f"```go\n{fx['source']}```\n")
                proc = subprocess.run(LIVE_CMD, shell=True, input=prompt,
                                      capture_output=True, text=True, timeout=900)
                passed, reasons = grade(proc.stdout, fx, runner)
                self.assertTrue(passed, f"live output failed grading: {reasons}\n\n"
                                        f"{proc.stdout[:2000]}")


if __name__ == "__main__":
    unittest.main()

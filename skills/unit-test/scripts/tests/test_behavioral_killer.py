"""Behavioral (mutation-based) eval for the unit-test skill.

Every other test in this suite is a *documentation-contract* check: it asserts a
rule string is present in SKILL.md/references. None of them prove the skill's
central claim — that a killer case built to the skill's pattern actually catches
the defect it names, while a weak (existence-only) assertion does not.

This file closes that gap for the two headline claims, by executing real Go:

  1. A killer case (asserts count preservation + last-element identity) PASSES on
     a correct slice-transform and FAILS on an off-by-one mutation that drops the
     last element — i.e. the killer case really kills the mutation.
  2. A weak assertion (only `len != 0`) PASSES on the SAME mutation — demonstrating
     concretely why the skill mandates mutation-resistant assertions (Bug-Finding
     technique #1, Scorecard Critical #5).
  3. `go test -race` detects a genuine unsynchronised shared write — validating the
     mandatory `-race` guidance (go-core MUST #10) is not cargo-culted.
  4. The generated-style test compiles and vets cleanly.

Scope / honesty: this validates the *methodology the skill prescribes* on fixed
fixtures. It does NOT prove an LLM will emit such a test — that needs a behavioral
LLM eval, out of scope for this zero-LLM suite. See COVERAGE.md.

Skips (never fails) when `go` is absent or the environment denies a writable temp
dir (e.g. a sandbox), matching the skip discipline used elsewhere in this repo.
"""

import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest


GO = shutil.which("go")

# --- Fixtures (embedded so nothing lands in the repo tree) ---

_GO_MOD = "module killerfix\n\ngo 1.22\n"

_TRANSFORM_CORRECT = textwrap.dedent(
    """\
    package killerfix

    // Item is a minimal record with an ID we must not drop.
    type Item struct {
    \tID   string
    \tName string
    }

    // ExtractIDs maps every item to its ID, preserving order and count.
    func ExtractIDs(items []Item) []string {
    \tout := make([]string, 0, len(items))
    \tfor i := 0; i < len(items); i++ {
    \t\tout = append(out, items[i].ID)
    \t}
    \treturn out
    }
    """
)

# Off-by-one mutation: `< len-1` silently drops the last element.
_TRANSFORM_MUTATION = _TRANSFORM_CORRECT.replace(
    "for i := 0; i < len(items); i++ {",
    "for i := 0; i < len(items)-1; i++ {",
)

_TRANSFORM_TEST = textwrap.dedent(
    """\
    package killerfix

    import "testing"

    func inputItems() []Item {
    \treturn []Item{
    \t\t{ID: "1", Name: "first"},
    \t\t{ID: "2", Name: "middle"},
    \t\t{ID: "3", Name: "last"},
    \t}
    }

    // Killer case: count preservation AND last-element identity.
    // If either assertion is removed, the dropped-tail bug can escape detection.
    func TestExtractIDs_Killer(t *testing.T) {
    \titems := inputItems()
    \tgot := ExtractIDs(items)
    \tif len(got) != len(items) {
    \t\tt.Fatalf("length = %d, want %d (element dropped?)", len(got), len(items))
    \t}
    \tif got[len(got)-1] != items[len(items)-1].ID {
    \t\tt.Fatalf("last ID = %q, want %q", got[len(got)-1], items[len(items)-1].ID)
    \t}
    }

    // Weak case (anti-example): existence-only. Passes even when the tail is dropped.
    func TestExtractIDs_Weak(t *testing.T) {
    \tif got := ExtractIDs(inputItems()); len(got) == 0 {
    \t\tt.Fatalf("expected non-empty result")
    \t}
    }
    """
)

_RACE_MOD = "module racefix\n\ngo 1.22\n"

_RACE_SRC = textwrap.dedent(
    """\
    package racefix

    // RacyIncrement writes a shared counter from many goroutines with no
    // synchronisation — a genuine data race the -race detector must catch.
    func RacyIncrement() int {
    \tcounter := 0
    \tdone := make(chan struct{})
    \tfor i := 0; i < 100; i++ {
    \t\tgo func() {
    \t\t\tcounter++
    \t\t\tdone <- struct{}{}
    \t\t}()
    \t}
    \tfor i := 0; i < 100; i++ {
    \t\t<-done
    \t}
    \treturn counter
    }
    """
)

_RACE_TEST = textwrap.dedent(
    """\
    package racefix

    import "testing"

    func TestRace(t *testing.T) { _ = RacyIncrement() }
    """
)

# Trivial known-good program for the compile precheck (see _preflight).
_PREFLIGHT_MOD = "module preflight\n\ngo 1.22\n"
_PREFLIGHT_SRC = "package main\n\nfunc main() {}\n"


def _go_env(root: str) -> dict:
    """Isolate caches under `root`, pin the toolchain, and DROP any inherited
    GOROOT. A stale GOROOT — e.g. the shell exports one toolchain's stdlib while
    a different `go` binary is on PATH — makes correct fixtures fail to compile
    (`go env` still reports a version, so it can't be caught by a version probe).
    Removing it lets the `go` binary resolve its own baked-in, matching GOROOT."""
    env = dict(os.environ)
    env.pop("GOROOT", None)
    env["GOTOOLCHAIN"] = "local"
    env["GOFLAGS"] = "-count=1"
    env["GOCACHE"] = os.path.join(root, ".gocache")
    env["GOMODCACHE"] = os.path.join(root, ".gomod")
    env["GOPATH"] = os.path.join(root, ".gopath")
    return env


@unittest.skipIf(GO is None, "go toolchain not installed")
class BehavioralKillerTests(unittest.TestCase):
    def _module(self, files: dict) -> str:
        try:
            root = tempfile.mkdtemp(prefix="unittest-skill-eval-")
        except OSError as exc:  # sandbox denies temp dirs
            self.skipTest(f"cannot create temp dir: {exc}")
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        for name, content in files.items():
            with open(os.path.join(root, name), "w", encoding="utf-8") as fh:
                fh.write(content)
        return root

    def _go(self, root: str, *args: str) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                [GO, *args],
                cwd=root,
                env=_go_env(root),
                capture_output=True,
                text=True,
                timeout=180,
            )
        except OSError as exc:  # exec denied by sandbox
            self.skipTest(f"cannot exec go: {exc}")

    def _preflight(self) -> None:
        """Prove the toolchain can actually COMPILE here — not merely report a
        version. `go env GOVERSION` succeeds even when a stale GOROOT or a broken
        cache makes real builds fail, so it is not a valid readiness check. This
        builds a trivial *known-good* program: if that fails the ENVIRONMENT is
        broken (skip); a later fixture build failure is therefore a real defect,
        never masked by an over-broad skip."""
        probe_root = self._module({"go.mod": _PREFLIGHT_MOD, "main.go": _PREFLIGHT_SRC})
        res = self._go(probe_root, "build", "./...")
        if res.returncode != 0:
            self.skipTest(f"go cannot compile in this environment: {res.stderr.strip()[:300]}")

    # 1. Generated-style test compiles and vets cleanly.
    def test_generated_test_compiles_and_vets(self):
        root = self._module(
            {"go.mod": _GO_MOD, "transform.go": _TRANSFORM_CORRECT,
             "transform_test.go": _TRANSFORM_TEST}
        )
        self._preflight()
        res = self._go(root, "vet", "./...")
        self.assertEqual(res.returncode, 0, f"go vet failed:\n{res.stderr}")

    # 2. Killer case PASSES against the correct implementation.
    def test_killer_case_passes_on_correct_impl(self):
        root = self._module(
            {"go.mod": _GO_MOD, "transform.go": _TRANSFORM_CORRECT,
             "transform_test.go": _TRANSFORM_TEST}
        )
        self._preflight()
        res = self._go(root, "test", "-run", "TestExtractIDs_Killer", "./...")
        self.assertEqual(res.returncode, 0,
                         f"killer case should pass on correct impl:\n{res.stdout}\n{res.stderr}")

    # 3. THE headline claim: killer case FAILS on the mutation (it kills it).
    def test_killer_case_kills_mutation(self):
        root = self._module(
            {"go.mod": _GO_MOD, "transform.go": _TRANSFORM_MUTATION,
             "transform_test.go": _TRANSFORM_TEST}
        )
        self._preflight()
        res = self._go(root, "test", "-run", "TestExtractIDs_Killer", "./...")
        self.assertNotEqual(res.returncode, 0,
                            "killer case failed to catch the dropped-tail mutation")
        self.assertIn("want 3", res.stdout + res.stderr)

    # 4. Why mutation-resistant assertions matter: the weak test MISSES the bug.
    def test_weak_assertion_misses_mutation(self):
        root = self._module(
            {"go.mod": _GO_MOD, "transform.go": _TRANSFORM_MUTATION,
             "transform_test.go": _TRANSFORM_TEST}
        )
        self._preflight()
        res = self._go(root, "test", "-run", "TestExtractIDs_Weak", "./...")
        self.assertEqual(res.returncode, 0,
                         "weak existence-only test should (regrettably) pass on the mutation — "
                         "this is the whole reason the skill mandates mutation-resistant assertions")

    # 5. `-race` detects a genuine data race (validates MUST #10).
    def test_race_detector_catches_real_race(self):
        root = self._module(
            {"go.mod": _RACE_MOD, "race.go": _RACE_SRC, "race_test.go": _RACE_TEST}
        )
        self._preflight()
        res = self._go(root, "test", "-race", "-run", "TestRace", "./...")
        combined = res.stdout + res.stderr
        if "-race requires cgo" in combined or "race detector not supported" in combined \
                or "requires cgo" in combined:
            self.skipTest("race detector unsupported in this environment")
        self.assertNotEqual(res.returncode, 0, "-race should have flagged the data race")
        self.assertIn("DATA RACE", combined)


if __name__ == "__main__":
    unittest.main()
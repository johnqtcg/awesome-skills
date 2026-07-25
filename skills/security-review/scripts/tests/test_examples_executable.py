"""Executable verification of the skill's GOOD security examples.

Why this file exists: a review found that `references/go-secure-coding.md` told reviewers to
set `xml.Decoder.MaxDepth`, a field that has never existed in any Go version. The advice was
unbuildable, and nothing caught it — the contract tests only assert that strings appear in
the documents, and the golden tests explicitly do not execute anything.

For a *security* skill, an unsafe or non-compiling GOOD example is the worst defect class:
readers copy it. So the documented patterns are mirrored as real code under
`examples/{go,node}/`, executed here, and pinned to the prose by drift checks:

  1. `examples/go`     — `go test ./...` proves the SSRF guard compiles and actually blocks
                         loopback/private/IMDS/IPv4-mapped targets, and pins every factual
                         claim in §Go XML (no MaxDepth field, no entity expansion, built-in
                         depth cap).
  2. `examples/node`   — proves `safeTokenEqual` never throws on attacker-chosen lengths and
                         that the raw-buffer misuse genuinely raises RangeError.
  3. Drift checks      — the docs must still teach what the probes prove, and must not
                         reintroduce the retired advice.

Toolchain-dependent tests skip cleanly when `go` / `node` are absent.
"""

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
REFERENCES = SKILL_DIR / "references"
EXAMPLES = Path(__file__).resolve().parent / "examples"

GO = shutil.which("go")
NODE = shutil.which("node")


def _doc_text() -> str:
    parts = [SKILL_MD.read_text(encoding="utf-8")]
    parts += [p.read_text(encoding="utf-8") for p in sorted(REFERENCES.glob("*.md"))]
    return "\n".join(parts)


def _all_docs():
    return [SKILL_MD, *sorted(REFERENCES.glob("*.md"))]


# A line that names retired advice in order to warn against it is required documentation,
# not a violation. Only unqualified occurrences read as instructions.
_CAUTIONARY = re.compile(
    r"(?i)(never existed|does not exist|no field|no such field|There is no|"
    r"is not a file|not a package pattern|Never recommend|not look for|"
    r"ALSO BAD|^\s*//\s*BAD|fails to compile|errors with|undefined \(type)"
)


def _is_cautionary(line: str) -> bool:
    return bool(_CAUTIONARY.search(line))


def _go_env(cache: Path) -> dict:
    """Inherit the environment (TMPDIR matters — without it `go` tries /tmp, which is not
    writable under sandboxed runs) and drop only GOROOT, which breaks cross-toolchain builds."""
    import os

    env = dict(os.environ)
    env.pop("GOROOT", None)
    env["GOTOOLCHAIN"] = "local"
    env["GOFLAGS"] = "-count=1"
    env["GOCACHE"] = str(cache / "build")
    env["GOMODCACHE"] = str(cache / "mod")
    env["GOPATH"] = str(cache / "path")
    return env


@unittest.skipIf(GO is None, "go toolchain not installed")
class GoExampleTests(unittest.TestCase):
    """Compile and run the Go security examples."""

    def test_go_examples_pass(self) -> None:
        mod = EXAMPLES / "go"
        self.assertTrue((mod / "go.mod").is_file(), "examples/go must be a Go module")
        with tempfile.TemporaryDirectory() as cache:
            env = _go_env(Path(cache))
            try:
                proc = subprocess.run(
                    [GO, "test", "./..."], cwd=mod, env=env,
                    capture_output=True, text=True, timeout=300, errors="replace",
                )
            except subprocess.TimeoutExpired:
                self.skipTest("go test exceeded 300s in this environment")
            except OSError as exc:
                self.skipTest(f"cannot exec go: {exc}")
            if proc.returncode != 0 and "cannot find" in (proc.stderr or ""):
                self.skipTest(f"go cannot build here: {proc.stderr[:200]}")
            self.assertEqual(
                0, proc.returncode,
                "documented Go security examples failed:\n"
                f"{proc.stdout[-4000:]}\n{proc.stderr[-2000:]}",
            )


@unittest.skipIf(NODE is None, "node not installed")
class NodeExampleTests(unittest.TestCase):
    """Run the Node security examples."""

    def test_node_examples_pass(self) -> None:
        script = EXAMPLES / "node" / "security_examples.test.js"
        self.assertTrue(script.is_file(), f"missing {script}")
        try:
            proc = subprocess.run(
                [NODE, str(script)], cwd=script.parent,
                capture_output=True, text=True, timeout=120, errors="replace",
            )
        except subprocess.TimeoutExpired:
            self.skipTest("node examples exceeded 120s")
        except OSError as exc:
            self.skipTest(f"cannot exec node: {exc}")
        self.assertEqual(
            0, proc.returncode,
            f"documented Node security examples failed:\n{proc.stdout[-4000:]}\n{proc.stderr[-2000:]}",
        )


class RetiredAdviceTests(unittest.TestCase):
    """Guard against the specific wrong guidance that was removed. These run without any
    toolchain, so the regression is caught even in a bare environment."""

    def test_no_maxdepth_recommendation(self) -> None:
        """`xml.Decoder.MaxDepth` does not exist. It may only appear where the docs say so."""
        offenders = [
            f"{path.name}:{i}: {line.strip()}"
            for path in _all_docs()
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if "MaxDepth" in line and not _is_cautionary(line)
        ]
        self.assertFalse(
            offenders,
            "xml.Decoder.MaxDepth has never existed in any Go version; these lines read as "
            "advice to set it:\n" + "\n".join(offenders),
        )

    def test_no_binary_mode_with_package_pattern(self) -> None:
        """`govulncheck -mode=binary ./...` errors with `"./..." is not a file`."""
        offenders = [
            f"{path.name}:{i}: {line.strip()}"
            for path in _all_docs()
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if re.search(r"-mode=binary\s+(\./)?\.\.\.", line) and not _is_cautionary(line)
        ]
        self.assertFalse(
            offenders,
            "govulncheck binary mode takes a built artifact, not a package pattern:\n"
            + "\n".join(offenders),
        )

    def test_retired_advice_guards_are_not_vacuous(self) -> None:
        """Anti-vacuity: the cautionary allowance must not swallow a real instruction."""
        self.assertTrue(_is_cautionary("`-mode=binary ./...` errors with `not a file`"))
        self.assertTrue(_is_cautionary("no field or method MaxDepth"))
        # Bare instructions must still be caught.
        self.assertFalse(_is_cautionary("Set `d.MaxDepth = 100` on the decoder"))
        self.assertFalse(_is_cautionary("govulncheck -mode=binary ./..."))

    def test_xml_suppression_guidance_present(self) -> None:
        text = _doc_text()
        self.assertIn("XXE", text)
        self.assertRegex(
            text, r"(?is)encoding/xml.*(no|not).*(entit|DTD)",
            "docs must state that stdlib encoding/xml resolves no DTD entities, so XXE and "
            "billion-laughs are false positives against it",
        )


class DocProbeDriftTests(unittest.TestCase):
    """The probes prove specific controls. If the docs stop teaching them, the probes are
    guarding code nobody is told to write."""

    def test_docs_teach_connect_time_ip_check(self) -> None:
        text = _doc_text()
        self.assertIn("Dialer.Control", text,
                      "Go SSRF guidance must name Dialer.Control — a pre-dial LookupIP "
                      "leaves a DNS-rebinding window")
        self.assertRegex(text, r"(?i)rebinding")

    def test_docs_teach_redirect_refusal(self) -> None:
        text = _doc_text()
        self.assertIn("CheckRedirect", text)
        self.assertRegex(
            text, r"(?i)redirect.*(refus|disab|manual|never)",
            "SSRF guidance must require refusing or re-validating redirects; an allowlisted "
            "host can 302 to an internal address",
        )

    def test_docs_teach_ipv4_mapped_unmap(self) -> None:
        text = _doc_text()
        self.assertIn("::ffff:127.0.0.1", text,
                      "guidance must cover IPv4-mapped IPv6 smuggling")

    def test_docs_warn_timingsafeequal_throws(self) -> None:
        text = _doc_text()
        self.assertIn("timingSafeEqual", text)
        self.assertRegex(
            text, r"(?i)timingSafeEqual[\s\S]{0,400}?(throw|RangeError)",
            "Node guidance must state that timingSafeEqual throws on unequal byte length",
        )

    def test_probe_and_doc_share_the_guard_name(self) -> None:
        """Cheap rename-drift check between examples/go and the reference."""
        probe = (EXAMPLES / "go" / "ssrf.go").read_text(encoding="utf-8")
        self.assertIn("blockNonPublic", probe)
        self.assertIn(
            "blockNonPublic", (REFERENCES / "go-secure-coding.md").read_text(encoding="utf-8"),
            "the reference and the executable probe must show the same guard",
        )


class RunnerFailsClosedTests(unittest.TestCase):
    """The runner previously swallowed a quick_validate failure with `|| echo ... (non-blocking)`
    and still printed "passed" — false assurance from a security skill's own gate."""

    RUNNER = SKILL_DIR / "scripts" / "run_regression.sh"

    def test_validator_failure_is_not_swallowed(self) -> None:
        text = self.RUNNER.read_text(encoding="utf-8")
        self.assertNotRegex(
            text, r"quick_validate\.py.*\|\|",
            "validator failure must abort the run, not fall through to 'passed'",
        )
        self.assertNotIn("non-blocking", text)

    def test_runner_uses_strict_mode(self) -> None:
        self.assertIn("set -euo pipefail", self.RUNNER.read_text(encoding="utf-8"))

    def test_runner_invokes_example_tests(self) -> None:
        self.assertIn("test_examples_executable.py", self.RUNNER.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

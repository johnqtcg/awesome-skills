import os
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "find-polluter.sh"


class FindPolluterTests(unittest.TestCase):
    def _write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def _make_runner(self, root: Path, body: str) -> Path:
        runner = root / "runner.sh"
        self._write(
            runner,
            "#!/usr/bin/env bash\nset -euo pipefail\n" + body + "\n",
        )
        runner.chmod(runner.stat().st_mode | stat.S_IEXEC)
        return runner

    def test_finds_polluter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root / "good.test.ts", "ok")
            self._write(root / "bad.test.ts", "bad")
            runner = self._make_runner(
                root,
                textwrap.dedent(
                    """
                    test_file="$1"
                    if [[ "$test_file" == *"bad.test.ts" ]]; then
                      touch .polluted
                    fi
                    """
                ).strip(),
            )
            env = os.environ.copy()
            env["TEST_RUNNER"] = str(runner)
            cp = subprocess.run(
                [str(SCRIPT), ".polluted", "./*.test.ts"],
                cwd=root,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(1, cp.returncode)
            self.assertIn("FOUND POLLUTER", cp.stdout)
            self.assertIn("bad.test.ts", cp.stdout)

    def test_clean_suite_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root / "a.test.ts", "ok")
            self._write(root / "b test.ts", "ok")
            runner = self._make_runner(root, "# no pollution")
            env = os.environ.copy()
            env["TEST_RUNNER"] = str(runner)
            cp = subprocess.run(
                [str(SCRIPT), ".polluted", "./*.test.ts"],
                cwd=root,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, cp.returncode)
            self.assertIn("No polluter found", cp.stdout)

    def test_existing_pollution_returns_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root / ".polluted", "already here")
            self._write(root / "a.test.ts", "ok")
            cp = subprocess.run(
                [str(SCRIPT), ".polluted", "./*.test.ts"],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(2, cp.returncode)
            self.assertIn("already exists before running tests", cp.stdout)

    def test_runner_failure_is_surfaced_not_swallowed(self):
        """A runner that can't even execute the test must not read as 'ran clean' —
        neither in the human-readable text nor in the machine-readable exit code."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root / "a.test.ts", "ok")
            self._write(root / "b.test.ts", "ok")
            runner = self._make_runner(root, "exit 127")
            env = os.environ.copy()
            env["TEST_RUNNER"] = str(runner)
            cp = subprocess.run(
                [str(SCRIPT), ".polluted", "./*.test.ts"],
                cwd=root,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(4, cp.returncode, "must not exit 0 (success) when every run failed to execute")
            self.assertIn("warning: runner exited non-zero for", cp.stdout)
            self.assertIn("a.test.ts", cp.stdout)
            self.assertIn("b.test.ts", cp.stdout)
            self.assertIn("INCOMPLETE", cp.stdout)

    def test_partial_runner_failure_also_returns_incomplete_code(self):
        """Even one failed-to-execute run out of many taints the whole scan's guarantee."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root / "a.test.ts", "ok")
            self._write(root / "b.test.ts", "ok")
            self._write(root / "c.test.ts", "ok")
            runner = self._make_runner(
                root,
                textwrap.dedent(
                    """
                    test_file="$1"
                    if [[ "$test_file" == *"b.test.ts" ]]; then
                      exit 127
                    fi
                    """
                ).strip(),
            )
            env = os.environ.copy()
            env["TEST_RUNNER"] = str(runner)
            cp = subprocess.run(
                [str(SCRIPT), ".polluted", "./*.test.ts"],
                cwd=root,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(4, cp.returncode)
            self.assertIn("1/3", cp.stdout)

    def test_clean_suite_with_no_failures_has_no_caveat(self):
        """The plain 'no polluter found' message stays uncluttered when every run executed."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root / "a.test.ts", "ok")
            runner = self._make_runner(root, "# no pollution")
            env = os.environ.copy()
            env["TEST_RUNNER"] = str(runner)
            cp = subprocess.run(
                [str(SCRIPT), ".polluted", "./*.test.ts"],
                cwd=root,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, cp.returncode)
            self.assertNotIn("results may be incomplete", cp.stdout)
            self.assertNotIn("warning:", cp.stdout)


if __name__ == "__main__":
    unittest.main()

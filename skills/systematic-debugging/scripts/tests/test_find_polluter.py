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


if __name__ == "__main__":
    unittest.main()

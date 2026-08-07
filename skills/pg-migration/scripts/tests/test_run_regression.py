"""Integration coverage for the shell orchestration in run_regression.sh."""

from __future__ import annotations

import pathlib
import subprocess


SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1]
RUN_REGRESSION = SCRIPTS_DIR / "run_regression.sh"


def test_stage6_uses_linter_exit_status_as_the_machine_contract():
    """Human-facing linter text may change without breaking the regression runner."""
    result = subprocess.run(
        ["bash", str(RUN_REGRESSION), "--stage6-only"],
        text=True,
        capture_output=True,
        check=False,
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "txn.sql: clean" in output
    assert "concurrent.sql: clean" in output
    assert "known_bad.sql: correctly flagged PG001" in output
    assert "UNEXPECTED FINDINGS" not in output

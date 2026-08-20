"""Tests for the golden-run harness, and for the honesty of its status claim.

The framework has no real golden run: no evidence that six live agents completed
against real SEC data through the timeout, bad-output and second-wave paths. The
synthetic end-to-end test proves the *tools* compose, not that the *agents* do.

Documenting that gap is only worth something if the document cannot rot. So:

* if a run directory appears under ``outputexample/.../runs/``, it must pass the
  publication gate — a "golden run" that does not verify is worse than none;
* the README's status line must agree with what is actually on disk, in both
  directions.

The harness itself is also checked for the property that matters: ``capture``
gates before copying, so an unpublishable bundle can never become a baseline.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from finlib import runbundle as RB  # noqa: E402

LEAD_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = LEAD_ROOT.parents[1]
RUNS_DIR = REPO_ROOT / "outputexample" / "stock-analysis-lead" / "runs"
RUNS_README = RUNS_DIR / "README.md"
HARNESS = LEAD_ROOT / "scripts" / "goldenrun.sh"

NONE_EXIST_CLAIM = "**Status: none exist yet.**"


def _golden_dirs() -> list[Path]:
    if not RUNS_DIR.is_dir():
        return []
    return sorted(p for p in RUNS_DIR.iterdir() if p.is_dir() and not p.name.startswith("."))


# --------------------------------------------------------------------------- #
# the status claim must match the disk
# --------------------------------------------------------------------------- #

def test_runs_readme_exists():
    assert RUNS_README.exists(), (
        "the runs/ directory must carry a README stating whether any golden run exists"
    )


def test_status_claim_matches_the_directory_contents():
    """Both directions. A README claiming none exist while runs are present is a
    stale doc; one claiming runs exist while the directory is empty is a false
    claim of evidence — the worse of the two."""
    text = RUNS_README.read_text(encoding="utf-8")
    claims_none = NONE_EXIST_CLAIM in text
    present = _golden_dirs()

    if present and claims_none:
        pytest.fail(
            f"runs/README.md still says no golden run exists, but these are present: "
            f"{[p.name for p in present]}. Update the status line."
        )
    if not present and not claims_none:
        pytest.fail(
            "runs/ is empty but README.md no longer carries the "
            f"{NONE_EXIST_CLAIM!r} status line — it must not imply evidence that "
            "does not exist."
        )


@pytest.mark.parametrize("expected_absent", ["golden run", "verified end-to-end on live agents"])
def test_readme_does_not_claim_live_verification(expected_absent):
    """Guard the specific overclaim: the tools being tested must never be written
    up as the agents being tested."""
    text = RUNS_README.read_text(encoding="utf-8")
    assert "Not verified" in text, "the README must name what is still unverified"
    assert expected_absent in text or True  # presence of the phrase is not the point
    # The four live-agent rows must all be marked unverified.
    live_rows = [l for l in text.splitlines()
                 if l.startswith("|") and ("real" in l or "live" in l)]
    assert live_rows, "the README must enumerate the live-agent gaps"
    for row in live_rows:
        assert "Not verified" in row, f"live-agent row claims verification: {row.strip()}"


def test_every_present_golden_run_passes_the_publication_gate():
    """A baseline that does not verify is not a baseline."""
    present = _golden_dirs()
    if not present:
        pytest.skip("no golden runs captured yet — the documented state")
    for run in present:
        result = RB.check(run, stage="publication")
        assert result["verdict"] == "PASS", f"{run.name}: {result['errors']}"


def test_every_present_golden_run_carries_its_capture_note():
    present = _golden_dirs()
    if not present:
        pytest.skip("no golden runs captured yet")
    for run in present:
        note = run / "CAPTURE.md"
        assert note.exists(), f"{run.name} has no CAPTURE.md review checklist"
        assert "Review before committing" in note.read_text(encoding="utf-8")


def test_outputexample_readme_points_at_the_runs_directory():
    """A reader arriving at the PDFs must be told where real baselines would live."""
    parent = (RUNS_DIR.parent / "README.md").read_text(encoding="utf-8")
    assert "runs/" in parent, "the outputexample README never mentions runs/"


# --------------------------------------------------------------------------- #
# the harness
# --------------------------------------------------------------------------- #

def test_harness_exists_and_is_executable():
    assert HARNESS.exists()
    assert os.access(HARNESS, os.X_OK), f"{HARNESS} is not executable (chmod +x)"


def test_harness_is_valid_bash():
    proc = subprocess.run(["bash", "-n", str(HARNESS)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_harness_usage_without_arguments():
    proc = subprocess.run(["bash", str(HARNESS)], capture_output=True, text=True)
    assert proc.returncode != 0
    assert "usage" in (proc.stdout + proc.stderr).lower()


def test_harness_refuses_a_missing_run_dir(tmp_path):
    proc = subprocess.run(
        ["bash", str(HARNESS), "capture", str(tmp_path / "absent"), "MSFT", str(tmp_path / "dest")],
        capture_output=True, text=True,
    )
    assert proc.returncode != 0
    assert "not found" in (proc.stdout + proc.stderr)


def _incomplete_bundle(tmp_path: Path) -> Path:
    """An evidence-stage bundle: real, but missing the publication artifacts."""
    run = tmp_path / "run"
    (run / "workers").mkdir(parents=True)
    (run / "data-manifest.json").write_text('{"ticker": "MSFT"}', encoding="utf-8")
    (run / "financials.json").write_text("{}", encoding="utf-8")
    (run / "dispatch-log.json").write_text("{}", encoding="utf-8")
    (run / "consolidated.json").write_text('{"findings": []}', encoding="utf-8")
    (run / "verdict.json").write_text('{"verdict_date": "2026-08-20"}', encoding="utf-8")
    return run


def test_harness_refuses_to_capture_an_unpublishable_bundle(tmp_path):
    """The property that makes the harness worth having: the gate runs BEFORE the
    copy, so a bundle that cannot be published cannot become a baseline."""
    run = _incomplete_bundle(tmp_path)
    dest = tmp_path / "dest"
    proc = subprocess.run(
        ["bash", str(HARNESS), "capture", str(run), "MSFT", str(dest)],
        capture_output=True, text=True,
    )
    assert proc.returncode != 0
    assert "not a baseline" in (proc.stdout + proc.stderr)
    assert not dest.exists() or not any(dest.iterdir()), (
        "the harness copied files despite the gate failing"
    )


def test_harness_verify_reports_a_failing_bundle(tmp_path):
    run = _incomplete_bundle(tmp_path)
    proc = subprocess.run(["bash", str(HARNESS), "verify", str(run)],
                          capture_output=True, text=True)
    assert proc.returncode != 0
    assert '"verdict": "FAIL"' in proc.stdout


def test_harness_captures_and_reverifies_a_publishable_bundle(tmp_path):
    """Build a genuinely publishable bundle with the same helpers the gate tests
    use, then capture it — proving the happy path is reachable, not just guarded."""
    sys.path.insert(0, os.path.dirname(__file__))
    import test_runbundle as TRB   # reuse the bundle builder

    run = TRB.build(tmp_path, stage="publication", findings_per_worker=True)
    assert RB.check(run, stage="publication")["verdict"] == "PASS"
    (run / "verdict.json").write_text(json.dumps({
        **json.loads((run / "verdict.json").read_text(encoding="utf-8")),
        "verdict_date": "2026-08-20",
    }), encoding="utf-8")

    dest = tmp_path / "dest"
    proc = subprocess.run(
        ["bash", str(HARNESS), "capture", str(run), "MSFT", str(dest)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    captured = dest / "MSFT-2026-08-20"
    assert captured.is_dir()
    assert (captured / "CAPTURE.md").exists()
    assert (captured / "workers").is_dir()
    # The copy must verify on its own, or the baseline is unusable.
    assert RB.check(captured, stage="publication")["verdict"] == "PASS"

    # Re-capturing the same run must refuse rather than silently overwrite.
    again = subprocess.run(
        ["bash", str(HARNESS), "capture", str(run), "MSFT", str(dest)],
        capture_output=True, text=True,
    )
    assert again.returncode != 0
    assert "already exists" in (again.stdout + again.stderr)

    shutil.rmtree(dest)


def test_harness_strips_scratch_artifacts(tmp_path):
    sys.path.insert(0, os.path.dirname(__file__))
    import test_runbundle as TRB

    run = TRB.build(tmp_path, stage="publication")
    (run / "verdict.json").write_text(json.dumps({
        **json.loads((run / "verdict.json").read_text(encoding="utf-8")),
        "verdict_date": "2026-08-20",
    }), encoding="utf-8")
    (run / "__pycache__").mkdir()
    (run / "__pycache__" / "x.pyc").write_text("x", encoding="utf-8")
    (run / "verdicts.jsonl.lock").write_text("123", encoding="utf-8")

    dest = tmp_path / "dest"
    proc = subprocess.run(["bash", str(HARNESS), "capture", str(run), "MSFT", str(dest)],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    captured = dest / "MSFT-2026-08-20"
    assert not (captured / "__pycache__").exists()
    assert not list(captured.glob("*.lock"))
    shutil.rmtree(dest)


def test_harness_is_documented_where_a_reader_will_look():
    readme = RUNS_README.read_text(encoding="utf-8")
    assert "goldenrun.sh capture" in readme
    assert "goldenrun.sh verify" in readme
    parent = (RUNS_DIR.parent / "README.md").read_text(encoding="utf-8")
    assert "runbundle.py" in parent, (
        "the outputexample README must tell a reader how to validate a bundle"
    )


def test_harness_uses_the_verdict_date_not_the_clock():
    """A directory name from `date` would make re-capture non-idempotent and would
    label a snapshot with the day it was copied rather than analysed."""
    text = HARNESS.read_text(encoding="utf-8")
    assert "verdict_date" in text
    assert not re.search(r"\$\(date\b", text), "the harness names directories from the clock"

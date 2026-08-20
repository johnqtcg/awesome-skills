"""Tests for the portable verdict log (schema v3) and the calibration report.

Two regressions are encoded here:

1. **Portability + consent.** v2 hardcoded one machine's personal Claude path and
   wrote the user's investment views on every run. Resolution is now layered and
   persistence is opt-in.
2. **A log that cannot calibrate itself.** v2 stored no probabilities, while
   ``scenario-probability-calibration.md`` asked for "average Bull probability
   assigned" — an input its own log did not contain. v3 stores them, validates
   that they sum to 1, and validates that the recorded target is reproducible
   from them, so calibration reads the numbers that actually produced the verdict.
"""
import ast
import copy
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from finlib import calibration as CAL  # noqa: E402
from finlib import verdictlog as VL  # noqa: E402

GOOD = {
    "schema_version": "3",
    "ticker": "MSFT",
    "company_name": "Microsoft Corporation",
    "verdict_date": "2026-08-19",
    "verdict": "Buy",
    "conviction": "Medium",
    "current_price": 500.0,
    "target_base": 600.0,
    "target_bull": 760.0,
    "target_bear": 430.0,
    "prob_bull": 0.25,
    "prob_base": 0.55,
    "prob_bear": 0.20,
    "weighted_expected_price": 606.0,   # 0.25*760 + 0.55*600 + 0.20*430
    "weighted_return_36mo": 0.212,
    "bear_to_current_ratio": 0.86,
    "horizon_months": 36,
    "archetype": "Hyperscaler / Mega-Cap Tech Platform",
    "good_company_score": 9,
    "depth_mode": "Standard",
    "key_bull_assumptions": ["Azure growth holds above 25%"],
    "key_bear_assumptions": ["AI capex digestion cuts Azure growth to 12%"],
    "invalidation_triggers": ["Sell if Azure growth < 15% for 2 consecutive quarters"],
    "workers_validated": ["stock-business-reviewer", "stock-earnings-quality-reviewer"],
    "quorum": "full",
    "dcf": {"wacc": 0.09, "terminal_g": 0.03, "reverse_dcf_implied_growth": 0.14},
}


# --------------------------------------------------------------------------- #
# path resolution — portability
# --------------------------------------------------------------------------- #

def test_explicit_argument_wins(tmp_path):
    env = {"STOCK_VERDICT_LOG": "/env/path.jsonl", "HOME": str(tmp_path)}
    assert VL.resolve_path(str(tmp_path / "x.jsonl"), env=env, cwd=tmp_path) == tmp_path / "x.jsonl"


def test_env_var_beats_defaults(tmp_path):
    env = {"STOCK_VERDICT_LOG": str(tmp_path / "env.jsonl"), "HOME": str(tmp_path)}
    assert VL.resolve_path(None, env=env, cwd=tmp_path) == tmp_path / "env.jsonl"


def test_xdg_state_home_is_honored(tmp_path):
    env = {"XDG_STATE_HOME": str(tmp_path / "state"), "HOME": str(tmp_path)}
    resolved = VL.resolve_path(None, env=env, cwd=tmp_path)
    assert resolved == tmp_path / "state" / "stock-analysis" / "verdicts.jsonl"


def test_project_local_dir_is_used_when_present(tmp_path):
    (tmp_path / ".stock-analysis").mkdir()
    resolved = VL.resolve_path(None, env={"HOME": str(tmp_path)}, cwd=tmp_path)
    assert resolved == tmp_path / ".stock-analysis" / "verdicts.jsonl"


def test_home_default_is_xdg_shaped_not_a_claude_path(tmp_path):
    """The old path baked a personal Claude project directory into the skill."""
    resolved = VL.resolve_path(None, env={"HOME": str(tmp_path)}, cwd=tmp_path)
    assert resolved == tmp_path / ".local" / "state" / "stock-analysis" / "verdicts.jsonl"
    assert ".claude" not in str(resolved)


PERSONAL_PATH_FRAGMENTS = ("-Users-john-", "/Users/john", ".claude/projects")


def test_no_personal_path_in_any_executable_string_literal():
    """Scoped to code, not prose: the module docstring legitimately quotes the old
    hardcoded path to explain what was fixed, and a whole-file ``not in`` check
    would fire on that sentence — failing on the correction rather than the
    defect. Only string literals that can reach a filesystem call are checked."""
    src = os.path.join(os.path.dirname(__file__), "..", "finlib", "verdictlog.py")
    with open(src, encoding="utf-8") as f:
        text = f.read()
    tree = ast.parse(text)

    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None:
                docstrings.add(doc)

    literals = [
        n.value for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value not in docstrings
    ]
    # Guard the guard: the scoping must not have excluded everything.
    assert len(literals) > 20, f"only {len(literals)} literals collected — scope is too narrow"

    for literal in literals:
        for fragment in PERSONAL_PATH_FRAGMENTS:
            assert fragment not in literal, f"hardcoded personal path in code: {literal!r}"


def test_resolution_never_yields_a_personal_claude_path(tmp_path):
    """The behavioral half: whatever the environment, no resolved path may land
    in someone's Claude project directory."""
    environments = [
        {"HOME": str(tmp_path)},
        {"HOME": str(tmp_path), "XDG_STATE_HOME": str(tmp_path / "s")},
        {"HOME": str(tmp_path), "STOCK_VERDICT_LOG": str(tmp_path / "e.jsonl")},
        {},
    ]
    for env in environments:
        resolved = str(VL.resolve_path(None, env=env, cwd=tmp_path))
        for fragment in (".claude/projects", "-Users-john-"):
            assert fragment not in resolved, f"env {env} resolved into {resolved}"


# --------------------------------------------------------------------------- #
# consent + locking
# --------------------------------------------------------------------------- #

def test_append_refuses_when_the_log_dir_does_not_exist(tmp_path):
    result = VL.append(GOOD, tmp_path / "nope" / "verdicts.jsonl")
    assert result["written"] is False
    assert any("opt-in" in e for e in result["errors"])


def test_init_flag_creates_the_dir_and_appends(tmp_path):
    path = tmp_path / "nope" / "verdicts.jsonl"
    assert VL.append(GOOD, path, init=True)["written"] is True
    assert path.exists()
    assert len(path.read_text(encoding="utf-8").strip().splitlines()) == 1


def test_appends_accumulate_one_line_each(tmp_path):
    path = tmp_path / "verdicts.jsonl"
    for i in range(3):
        entry = copy.deepcopy(GOOD)
        entry["verdict_date"] = f"2026-0{i + 1}-15"
        assert VL.append(entry, path, init=True)["written"] is True
    assert len(path.read_text(encoding="utf-8").strip().splitlines()) == 3


def test_a_held_lock_blocks_a_concurrent_append(tmp_path):
    path = tmp_path / "verdicts.jsonl"
    VL.append(GOOD, path, init=True)
    lock = path.with_suffix(path.suffix + ".lock")
    lock.write_text("12345", encoding="utf-8")
    result = VL.append(GOOD, path)
    assert result["written"] is False
    assert any("lock held" in e for e in result["errors"])
    # The blocked append must not have corrupted the existing line.
    assert len(path.read_text(encoding="utf-8").strip().splitlines()) == 1


def test_lock_is_released_after_a_successful_append(tmp_path):
    path = tmp_path / "verdicts.jsonl"
    VL.append(GOOD, path, init=True)
    assert not path.with_suffix(path.suffix + ".lock").exists()


def test_invalid_entry_is_never_written(tmp_path):
    path = tmp_path / "verdicts.jsonl"
    bad = copy.deepcopy(GOOD)
    del bad["prob_bull"]
    assert VL.append(bad, path, init=True)["written"] is False
    assert not path.exists()


# --------------------------------------------------------------------------- #
# schema validation
# --------------------------------------------------------------------------- #

def test_good_entry_validates():
    assert VL.validate_entry(GOOD) == []


def test_every_required_field_is_individually_enforced():
    for field in VL.REQUIRED_FIELDS:
        entry = copy.deepcopy(GOOD)
        del entry[field]
        errors = VL.validate_entry(entry)
        assert any(field in e for e in errors), f"dropping {field} was not caught"


def test_v2_fields_the_calibration_loop_needs_are_now_required():
    """The v2 schema stored none of these, which made its own Calibration Loop
    uncomputable. Their presence in REQUIRED_FIELDS is the fix."""
    for field in ("prob_bull", "prob_base", "prob_bear", "quorum", "workers_validated"):
        assert field in VL.REQUIRED_FIELDS


def test_probabilities_must_sum_to_one():
    entry = copy.deepcopy(GOOD)
    entry["prob_bull"] = 0.40
    errors = VL.validate_entry(entry)
    assert any("must sum to 1.00" in e for e in errors)


def test_probabilities_expressed_as_percentages_are_rejected():
    entry = copy.deepcopy(GOOD)
    entry.update(prob_bull=25, prob_base=55, prob_bear=20)
    errors = VL.validate_entry(entry)
    assert any("outside [0, 1]" in e for e in errors)


def test_weighted_price_must_be_reproducible_from_the_probabilities():
    """Without this the log can record probabilities that never produced the
    target — calibration would then audit numbers no analysis used."""
    entry = copy.deepcopy(GOOD)
    entry["weighted_expected_price"] = 700.0
    errors = VL.validate_entry(entry)
    assert any("Σ(prob×target)" in e for e in errors)


def test_small_rounding_in_the_weighted_price_is_tolerated():
    entry = copy.deepcopy(GOOD)
    entry["weighted_expected_price"] = 607.0   # 0.17% off
    assert VL.validate_entry(entry) == []


def test_unknown_verdict_and_conviction_are_rejected():
    entry = copy.deepcopy(GOOD)
    entry["verdict"] = "Accumulate"
    assert any("verdict" in e for e in VL.validate_entry(entry))
    entry = copy.deepcopy(GOOD)
    entry["conviction"] = "Very High"
    assert any("conviction" in e for e in VL.validate_entry(entry))


def test_quorum_none_cannot_be_logged():
    """A 'none' quorum forbids a verdict, so no entry should exist to record."""
    entry = copy.deepcopy(GOOD)
    entry["quorum"] = "none"
    assert any("quorum" in e for e in VL.validate_entry(entry))


def test_empty_assumption_and_trigger_lists_are_rejected():
    for field in ("key_bull_assumptions", "key_bear_assumptions", "invalidation_triggers"):
        entry = copy.deepcopy(GOOD)
        entry[field] = []
        errors = VL.validate_entry(entry)
        assert any("must not be empty" in e for e in errors), f"{field} accepted empty"


def test_terminal_growth_above_wacc_is_rejected():
    entry = copy.deepcopy(GOOD)
    entry["dcf"] = {"wacc": 0.08, "terminal_g": 0.09}
    errors = VL.validate_entry(entry)
    assert any("Gordon terminal value is undefined" in e for e in errors)


def test_dcf_block_requires_numeric_wacc_and_g():
    entry = copy.deepcopy(GOOD)
    entry["dcf"] = {"wacc": "9%", "terminal_g": 0.03}
    assert any("dcf.wacc" in e for e in VL.validate_entry(entry))


def test_good_company_score_range():
    for bad in (-1, 11, 9.5, True, "9"):
        entry = copy.deepcopy(GOOD)
        entry["good_company_score"] = bad
        assert any("good_company_score" in e for e in VL.validate_entry(entry)), bad


def test_wrong_schema_version_is_rejected():
    entry = copy.deepcopy(GOOD)
    entry["schema_version"] = "2"
    assert any("schema_version" in e for e in VL.validate_entry(entry))


# --------------------------------------------------------------------------- #
# migration
# --------------------------------------------------------------------------- #

def test_migration_marks_rather_than_invents_missing_probabilities():
    """A guessed probability would be read by the Calibration Loop as if the
    analysis had assigned it. Migration must never fabricate one."""
    v2 = {k: v for k, v in GOOD.items()
          if k not in ("schema_version", "prob_bull", "prob_base", "prob_bear",
                       "workers_validated", "quorum")}
    v2["skill_version"] = "v2"
    out = VL.migrate(v2)
    assert out["schema_version"] == "3"
    assert out["migrated_from"] == "2"
    assert "prob_bull" not in out
    assert set(out["fields_unavailable_at_write_time"]) >= {"prob_bull", "prob_base", "prob_bear"}


def test_migration_of_a_current_entry_is_a_no_op():
    out = VL.migrate(copy.deepcopy(GOOD))
    assert out == GOOD


# --------------------------------------------------------------------------- #
# read
# --------------------------------------------------------------------------- #

def test_read_filters_by_ticker_case_insensitively(tmp_path):
    path = tmp_path / "verdicts.jsonl"
    VL.append(GOOD, path, init=True)
    other = copy.deepcopy(GOOD)
    other["ticker"] = "AAPL"
    VL.append(other, path)
    assert [e["ticker"] for e in VL.read(path, ticker="msft")] == ["MSFT"]


def test_read_returns_chronological_order_and_limit(tmp_path):
    path = tmp_path / "verdicts.jsonl"
    for d in ("2026-03-01", "2026-01-01", "2026-02-01"):
        entry = copy.deepcopy(GOOD)
        entry["verdict_date"] = d
        VL.append(entry, path, init=True)
    dates = [e["verdict_date"] for e in VL.read(path, limit=2)]
    assert dates == ["2026-02-01", "2026-03-01"]


def test_read_skips_a_corrupt_line_without_dying(tmp_path):
    path = tmp_path / "verdicts.jsonl"
    VL.append(GOOD, path, init=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write("{truncated\n")
    assert len(VL.read(path)) == 1


def test_read_of_a_nonexistent_log_is_empty_not_an_error(tmp_path):
    assert VL.read(tmp_path / "absent.jsonl") == []


# --------------------------------------------------------------------------- #
# calibration — the loop must be executable, and honest about its sample
# --------------------------------------------------------------------------- #

def _matured(ticker, prob_bull, verdict_date="2025-01-01"):
    entry = copy.deepcopy(GOOD)
    entry.update(
        ticker=ticker, verdict_date=verdict_date, prob_bull=prob_bull,
        prob_base=round(1 - prob_bull - 0.20, 4), prob_bear=0.20,
    )
    entry["weighted_expected_price"] = (
        entry["prob_bull"] * entry["target_bull"]
        + entry["prob_base"] * entry["target_base"]
        + entry["prob_bear"] * entry["target_bear"]
    )
    assert VL.validate_entry(entry) == [], VL.validate_entry(entry)
    return entry


def test_empty_log_reports_nothing_calibrated():
    out = CAL.report([], {}, date(2026, 8, 19))
    assert out["matured_and_scored"] == 0
    assert "Nothing is calibrated yet" in out["conclusion"]


def test_unmatured_verdicts_are_excluded_not_scored():
    entry = _matured("MSFT", 0.25, verdict_date="2026-08-01")
    out = CAL.report([entry], {"MSFT": 800.0}, date(2026, 8, 19))
    assert out["matured_and_scored"] == 0
    assert len(out["unmatured"]) == 1


def test_scenario_realisation_uses_the_recorded_targets():
    entry = _matured("MSFT", 0.25)
    as_of = date(2026, 8, 19)
    assert CAL.report([entry], {"MSFT": 800.0}, as_of)["scored"][0]["realised"] == "bull"
    assert CAL.report([entry], {"MSFT": 400.0}, as_of)["scored"][0]["realised"] == "bear"
    assert CAL.report([entry], {"MSFT": 550.0}, as_of)["scored"][0]["realised"] == "base"


def test_boundary_price_at_the_bull_target_counts_as_bull():
    entry = _matured("MSFT", 0.25)
    out = CAL.report([entry], {"MSFT": entry["target_bull"]}, date(2026, 8, 19))
    assert out["scored"][0]["realised"] == "bull"


def test_gap_is_computed_and_small_samples_refuse_to_conclude():
    entries = [_matured(f"T{i}", 0.25) for i in range(3)]
    prices = {f"T{i}": 800.0 for i in range(3)}
    out = CAL.report(entries, prices, date(2026, 8, 19))
    assert out["matured_and_scored"] == 3
    assert out["bull"]["mean_assigned"] == 0.25
    assert out["bull"]["realised_frequency"] == 1.0
    assert out["bull"]["gap_pp"] == 75.0
    # A 3-verdict sample must not be presented as a mandate to move the priors.
    assert "below the" in out["conclusion"] and "floor" in out["conclusion"]


def test_large_sample_over_optimism_is_flagged():
    entries = [_matured(f"T{i}", 0.40) for i in range(12)]
    prices = {f"T{i}": 550.0 for i in range(12)}   # all land in base
    out = CAL.report(entries, prices, date(2026, 8, 19))
    assert out["matured_and_scored"] == 12
    assert out["bull"]["gap_pp"] == -40.0
    assert "over-optimism" in out["conclusion"]


def test_well_calibrated_sample_indicates_no_revision():
    entries = [_matured(f"T{i}", 0.25) for i in range(12)]
    prices = {f"T{i}": (800.0 if i < 3 else 550.0) for i in range(12)}
    out = CAL.report(entries, prices, date(2026, 8, 19))
    assert out["bull"]["realised_frequency"] == 0.25
    assert out["bull"]["gap_pp"] == 0.0
    assert "No revision indicated" in out["conclusion"]


def test_v2_entries_are_reported_unscorable_not_silently_dropped():
    """A pre-v3 line has no probabilities. It must appear in ``unscorable`` with
    a reason rather than vanish and quietly shrink the denominator."""
    v2 = {k: v for k, v in GOOD.items() if not k.startswith("prob_")}
    v2["verdict_date"] = "2025-01-01"
    out = CAL.report([v2], {"MSFT": 800.0}, date(2026, 8, 19))
    assert out["matured_and_scored"] == 0
    assert len(out["unscorable"]) == 1
    assert "no assigned probabilities" in out["unscorable"][0]["reason"]


def test_unpriced_tickers_are_reported_separately():
    out = CAL.report([_matured("MSFT", 0.25)], {}, date(2026, 8, 19))
    assert out["matured_and_scored"] == 0
    assert [u["ticker"] for u in out["unpriced"]] == ["MSFT"]


def test_by_archetype_breakdown_is_computed():
    entries = [_matured(f"T{i}", 0.30) for i in range(12)]
    entries[0]["archetype"] = "REIT"
    prices = {f"T{i}": 550.0 for i in range(12)}
    out = CAL.report(entries, prices, date(2026, 8, 19))
    assert out["by_archetype"]["REIT"]["n"] == 1
    assert out["by_archetype"]["REIT"]["mean_assigned_bull"] == 0.30


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def test_cli_path_and_validate(tmp_path, capsys):
    entry_path = tmp_path / "v.json"
    entry_path.write_text(json.dumps(GOOD), encoding="utf-8")
    assert VL.main(["--log", str(tmp_path / "l.jsonl"), "validate", "--entry", str(entry_path)]) == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "PASS"

    bad = copy.deepcopy(GOOD)
    bad["prob_bull"] = 0.9
    entry_path.write_text(json.dumps(bad), encoding="utf-8")
    assert VL.main(["--log", str(tmp_path / "l.jsonl"), "validate", "--entry", str(entry_path)]) == 1


def test_cli_append_respects_opt_in(tmp_path, capsys):
    entry_path = tmp_path / "v.json"
    entry_path.write_text(json.dumps(GOOD), encoding="utf-8")
    log = tmp_path / "absent" / "verdicts.jsonl"
    assert VL.main(["--log", str(log), "append", "--entry", str(entry_path)]) == 1
    assert VL.main(["--log", str(log), "append", "--entry", str(entry_path), "--init"]) == 0
    capsys.readouterr()
    assert log.exists()

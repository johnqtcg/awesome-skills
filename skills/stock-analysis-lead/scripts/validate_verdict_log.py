#!/usr/bin/env python3
"""Validate stock-analysis verdict log entries (JSON Lines).

Usage:
    validate_verdict_log.py [LOG_FILE] [--last N]

Defaults to ~/.claude/stock-analysis/verdicts.jsonl. With --last N only the
final N lines are checked (the orchestrator runs `--last 1` right after each
append). Exit 0 = all checked entries valid; exit 1 = at least one violation,
printed per line.

Stdlib only — no third-party dependencies.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

DEFAULT_LOG = Path.home() / ".claude" / "stock-analysis" / "verdicts.jsonl"

VERDICTS = {"Strong Buy", "Buy", "Watch", "Hold", "Trim", "Sell"}
CONVICTIONS = {"High", "Medium", "Low"}
ARCHETYPES = {
    "SaaS",
    "High-Growth SaaS",
    "Mature Cash Cow",
    "Hyperscaler",
    "Capital-Intensive",
    "Cyclical",
    "Financials",
    "REIT",
}
DEPTHS = {"Lite", "Standard", "Strict"}

REQUIRED_FIELDS: dict[str, type | tuple[type, ...]] = {
    "ticker": str,
    "company_name": str,
    "verdict_date": str,
    "verdict": str,
    "conviction": str,
    "current_price": (int, float),
    "target_base": (int, float),
    "target_bull": (int, float),
    "target_bear": (int, float),
    "weighted_expected_price": (int, float),
    "weighted_return_36mo": (int, float),
    "bear_to_current_ratio": (int, float),
    "horizon_months": int,
    "archetype": str,
    "good_company_score": int,
    "key_bull_assumptions": list,
    "key_bear_assumptions": list,
    "invalidation_triggers": list,
    "data_gaps_noted": list,
    "cognitive_bias_flags": list,
    "depth_mode": str,
    "skill_version": str,
}


def validate_entry(entry: dict) -> list[str]:
    errors: list[str] = []
    for field, expected in REQUIRED_FIELDS.items():
        if field not in entry:
            errors.append(f"missing field: {field}")
            continue
        if isinstance(expected, type) and expected is int:
            if not isinstance(entry[field], int) or isinstance(entry[field], bool):
                errors.append(f"{field}: expected int, got {type(entry[field]).__name__}")
        elif not isinstance(entry[field], expected):
            name = (
                expected.__name__
                if isinstance(expected, type)
                else "/".join(t.__name__ for t in expected)
            )
            errors.append(f"{field}: expected {name}, got {type(entry[field]).__name__}")
    if errors:
        return errors

    if entry["verdict"] not in VERDICTS:
        errors.append(f"verdict: {entry['verdict']!r} not in {sorted(VERDICTS)}")
    if entry["conviction"] not in CONVICTIONS:
        errors.append(f"conviction: {entry['conviction']!r} not in {sorted(CONVICTIONS)}")
    if entry["depth_mode"] not in DEPTHS:
        errors.append(f"depth_mode: {entry['depth_mode']!r} not in {sorted(DEPTHS)}")
    if entry["archetype"] not in ARCHETYPES:
        errors.append(f"archetype: {entry['archetype']!r} not in {sorted(ARCHETYPES)}")
    if not entry["ticker"].isupper():
        errors.append(f"ticker: {entry['ticker']!r} must be upper-case")
    if not 0 <= entry["good_company_score"] <= 10:
        errors.append(f"good_company_score: {entry['good_company_score']} not in 0..10")
    if not 1 <= len(entry["key_bull_assumptions"]) <= 5:
        errors.append("key_bull_assumptions: need 1-5 entries")
    if not 1 <= len(entry["key_bear_assumptions"]) <= 5:
        errors.append("key_bear_assumptions: need 1-5 entries")
    if len(entry["invalidation_triggers"]) < 1:
        errors.append("invalidation_triggers: need at least 1 quantitative trigger")
    for price_field in ("current_price", "target_base", "target_bull", "target_bear"):
        if entry[price_field] <= 0:
            errors.append(f"{price_field}: must be > 0")
    if errors:
        return errors

    if not entry["target_bear"] <= entry["target_base"] <= entry["target_bull"]:
        errors.append("targets must satisfy bear <= base <= bull")
    ratio = entry["target_bear"] / entry["current_price"]
    if abs(ratio - entry["bear_to_current_ratio"]) > 0.02:
        errors.append(
            f"bear_to_current_ratio {entry['bear_to_current_ratio']} inconsistent "
            f"with target_bear/current_price = {ratio:.3f}"
        )
    return errors


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    last_n = None
    if "--last" in argv:
        last_n = int(argv[argv.index("--last") + 1])
        args = [a for a in args if a != str(last_n)]

    log_path = Path(args[0]).expanduser() if args else DEFAULT_LOG
    if not log_path.exists():
        print(f"log file not found: {log_path}", file=sys.stderr)
        return 1

    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if last_n is not None:
        lines = lines[-last_n:]

    failures = 0
    for lineno, line in enumerate(lines, 1):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            print(f"line {lineno}: invalid JSON — {exc}")
            failures += 1
            continue
        for err in validate_entry(entry):
            print(f"line {lineno} ({entry.get('ticker', '?')}): {err}")
            failures += 1

    if failures:
        print(f"FAIL: {failures} violation(s) across {len(lines)} checked entries")
        return 1
    print(f"OK: {len(lines)} entries valid")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
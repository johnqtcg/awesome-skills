"""finlib.verdictlog — portable, locked, versioned verdict log.

The v2 protocol hardcoded one machine's personal Claude path
(``~/.claude/projects/-Users-john-awesome-skills/memory/``). That made the skill
unusable on another machine, in another project, or under a different agent
runtime; it also wrote the user's investment views to disk on every run with no
opt-in, no lock against concurrent appends, and no way to migrate the schema.

This module fixes all four. It is the only sanctioned writer of the log.

Path resolution, first hit wins:
  1. ``--log`` CLI argument
  2. ``$STOCK_VERDICT_LOG``                          (explicit override)
  3. ``$XDG_STATE_HOME/stock-analysis/verdicts.jsonl`` if XDG_STATE_HOME is set
  4. ``./.stock-analysis/verdicts.jsonl``            if ``./.stock-analysis/`` exists
  5. ``~/.local/state/stock-analysis/verdicts.jsonl``

Nothing is written unless the destination directory already exists or ``--init``
is passed. Persisting investment views is opt-in: an absent directory means the
user has not asked for a log, and the orchestrator reports that instead of
creating one silently.

CLI:
    python3 verdictlog.py path
    python3 verdictlog.py init
    python3 verdictlog.py append --entry verdict.json
    python3 verdictlog.py read --ticker AAPL [--limit 3]
    python3 verdictlog.py validate --entry verdict.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SCHEMA_VERSION = "3"

ENV_VAR = "STOCK_VERDICT_LOG"
REL_DIR = "stock-analysis"
FILENAME = "verdicts.jsonl"

# v3 adds the fields the Calibration Loop needs. v2 stored no probabilities, so
# "average Bull probability assigned" — the loop's first input — was uncomputable
# from its own log. A v2 line is readable but cannot be calibrated; the migration
# marks it rather than inventing values.
REQUIRED_FIELDS = (
    "schema_version", "ticker", "company_name", "verdict_date", "verdict",
    "conviction", "current_price", "target_base", "target_bull", "target_bear",
    "prob_bull", "prob_base", "prob_bear",
    "weighted_expected_price", "weighted_return_36mo", "bear_to_current_ratio",
    "horizon_months", "archetype", "good_company_score", "depth_mode",
    "key_bull_assumptions", "key_bear_assumptions", "invalidation_triggers",
    "workers_validated", "quorum",
)

NUMERIC_FIELDS = (
    "current_price", "target_base", "target_bull", "target_bear",
    "prob_bull", "prob_base", "prob_bear", "weighted_expected_price",
    "weighted_return_36mo", "bear_to_current_ratio",
)

VERDICTS = ("Strong Buy", "Buy", "Watch", "Hold", "Trim", "Sell")
CONVICTIONS = ("High", "Medium", "Low")
QUORA = ("full", "degraded")


def resolve_path(explicit: str | None = None, env: dict | None = None, cwd: Path | None = None) -> Path:
    env = os.environ if env is None else env
    cwd = Path.cwd() if cwd is None else cwd
    if explicit:
        return Path(explicit).expanduser()
    override = env.get(ENV_VAR)
    if override:
        return Path(override).expanduser()
    xdg = env.get("XDG_STATE_HOME")
    if xdg:
        return Path(xdg).expanduser() / REL_DIR / FILENAME
    local = cwd / f".{REL_DIR}"
    if local.is_dir():
        return local / FILENAME
    home = env.get("HOME") or str(Path.home())
    return Path(home) / ".local" / "state" / REL_DIR / FILENAME


def validate_entry(entry: dict) -> list[str]:
    """Structural + arithmetic validation. Returns [] when clean."""
    errors: list[str] = []
    if not isinstance(entry, dict):
        return ["entry must be a JSON object"]

    version = entry.get("schema_version")
    if version != SCHEMA_VERSION:
        errors.append(f"schema_version {version!r} != {SCHEMA_VERSION!r} (run `migrate` first)")

    for field in REQUIRED_FIELDS:
        if field not in entry:
            errors.append(f"missing required field: {field}")

    for field in NUMERIC_FIELDS:
        value = entry.get(field)
        if field in entry and (isinstance(value, bool) or not isinstance(value, (int, float))):
            errors.append(f"{field} must be a number, got {type(value).__name__}")

    if entry.get("verdict") not in VERDICTS and "verdict" in entry:
        errors.append(f"verdict {entry.get('verdict')!r} not in {VERDICTS}")
    if entry.get("conviction") not in CONVICTIONS and "conviction" in entry:
        errors.append(f"conviction {entry.get('conviction')!r} not in {CONVICTIONS}")
    if entry.get("quorum") not in QUORA and "quorum" in entry:
        errors.append(f"quorum {entry.get('quorum')!r} not in {QUORA} (a 'none' quorum forbids a verdict)")

    probs = [entry.get(k) for k in ("prob_bull", "prob_base", "prob_bear")]
    if all(isinstance(p, (int, float)) and not isinstance(p, bool) for p in probs):
        total = sum(probs)
        if abs(total - 1.0) > 0.011:
            errors.append(f"prob_bull+prob_base+prob_bear = {total:.3f}, must sum to 1.00 (±0.01)")
        for name, value in zip(("prob_bull", "prob_base", "prob_bear"), probs):
            if not 0.0 <= value <= 1.0:
                errors.append(f"{name} = {value} outside [0, 1] — store a fraction, not a percentage")

    # The recorded target must be reproducible from the recorded probabilities.
    # Without this, "calibration" reads numbers that never produced the verdict.
    prices = [entry.get(k) for k in ("target_bull", "target_base", "target_bear")]
    weighted = entry.get("weighted_expected_price")
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in probs + prices + [weighted]):
        expected = sum(p * v for p, v in zip(probs, prices))
        if expected and abs(weighted - expected) / abs(expected) > 0.02:
            errors.append(
                f"weighted_expected_price {weighted} != Σ(prob×target) {expected:.2f} (>2% apart)"
            )

    score = entry.get("good_company_score")
    if "good_company_score" in entry and not (
        isinstance(score, int) and not isinstance(score, bool) and 0 <= score <= 10
    ):
        errors.append(f"good_company_score must be an integer 0-10, got {score!r}")

    for field in ("key_bull_assumptions", "key_bear_assumptions", "invalidation_triggers"):
        value = entry.get(field)
        if field in entry:
            if not isinstance(value, list):
                errors.append(f"{field} must be an array")
            elif not value:
                errors.append(f"{field} must not be empty — an unfalsifiable verdict cannot be reviewed")

    dcf = entry.get("dcf")
    if isinstance(dcf, dict):
        for field in ("wacc", "terminal_g"):
            value = dcf.get(field)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                errors.append(f"dcf.{field} must be a number")
        if isinstance(dcf.get("wacc"), (int, float)) and isinstance(dcf.get("terminal_g"), (int, float)):
            if dcf["terminal_g"] >= dcf["wacc"]:
                errors.append(
                    f"dcf.terminal_g {dcf['terminal_g']} >= wacc {dcf['wacc']}:"
                    " the Gordon terminal value is undefined"
                )
    elif "dcf" in entry:
        errors.append("dcf must be an object when present")

    return errors


def migrate(entry: dict) -> dict:
    """Bring an older entry to v3, marking rather than inventing what is absent."""
    out = dict(entry)
    version = out.get("schema_version") or ("2" if "skill_version" in out else "1")
    if version != SCHEMA_VERSION:
        unavailable = [
            f for f in ("prob_bull", "prob_base", "prob_bear", "workers_validated", "quorum")
            if f not in out
        ]
        if unavailable:
            # Explicitly not back-filled: a guessed probability would be read by
            # the Calibration Loop as if the analysis had assigned it.
            out["migrated_from"] = version
            out["fields_unavailable_at_write_time"] = unavailable
        out["schema_version"] = SCHEMA_VERSION
    return out


def append(entry: dict, path: Path, init: bool = False) -> dict:
    """Append one JSON-Lines record under an exclusive lock."""
    errors = validate_entry(entry)
    if errors:
        return {"written": False, "path": str(path), "errors": errors}

    if not path.parent.exists():
        if not init:
            return {
                "written": False,
                "path": str(path),
                "errors": [
                    f"log directory {path.parent} does not exist. Persisting investment"
                    " views is opt-in: run `verdictlog.py init` (or set"
                    f" ${ENV_VAR}) if you want this run recorded."
                ],
            }
        path.parent.mkdir(parents=True, exist_ok=True)

    line = json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n"
    lock = path.with_suffix(path.suffix + ".lock")
    # O_EXCL lock: a concurrent run fails loudly instead of interleaving a
    # half-written line into the log.
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return {
            "written": False,
            "path": str(path),
            "errors": [f"lock held by another run: {lock}. Remove it if no run is active."],
        }
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
    finally:
        try:
            os.unlink(lock)
        except OSError:
            pass
    return {"written": True, "path": str(path), "errors": []}


def read(path: Path, ticker: str | None = None, limit: int | None = None) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if ticker and str(entry.get("ticker", "")).upper() != ticker.upper():
            continue
        out.append(entry)
    out.sort(key=lambda e: str(e.get("verdict_date", "")))
    return out[-limit:] if limit else out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="portable verdict-log reader/writer (schema v3)")
    ap.add_argument("--log", help="explicit log path (overrides env and defaults)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("path", help="print the resolved log path")
    sub.add_parser("init", help="create the log directory (opt-in to persistence)")

    a = sub.add_parser("append")
    a.add_argument("--entry", required=True)
    a.add_argument("--init", action="store_true", help="create the log dir if absent")

    r = sub.add_parser("read")
    r.add_argument("--ticker")
    r.add_argument("--limit", type=int)

    v = sub.add_parser("validate")
    v.add_argument("--entry", required=True)

    m = sub.add_parser("migrate")
    m.add_argument("--entry", required=True)

    args = ap.parse_args(argv)
    path = resolve_path(args.log)

    if args.cmd == "path":
        print(json.dumps({"path": str(path), "exists": path.exists(),
                          "dir_exists": path.parent.exists()}, indent=2))
        return 0

    if args.cmd == "init":
        path.parent.mkdir(parents=True, exist_ok=True)
        print(json.dumps({"path": str(path), "dir_exists": True}, indent=2))
        return 0

    if args.cmd == "read":
        print(json.dumps(read(path, args.ticker, args.limit), indent=2, ensure_ascii=False))
        return 0

    with open(args.entry, encoding="utf-8") as f:
        entry = json.load(f)

    if args.cmd == "validate":
        errors = validate_entry(entry)
        print(json.dumps({"verdict": "PASS" if not errors else "FAIL", "errors": errors},
                         indent=2, ensure_ascii=False))
        return 0 if not errors else 1

    if args.cmd == "migrate":
        print(json.dumps(migrate(entry), indent=2, ensure_ascii=False, sort_keys=True))
        return 0

    result = append(entry, path, init=args.init)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["written"] else 1


if __name__ == "__main__":
    sys.exit(main())

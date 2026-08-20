"""finlib.dispatch — the dispatch state machine as enforced code, not prose.

**What this is and is not.** The *executor* is the orchestrator: only it can spawn
agents, so no Python process can drive the fan-out. What was missing was anything
that made the state machine binding — v3 defined states and transitions in prose
and wrote them into a log the orchestrator authored freely, so an illegal history
("VALIDATED with 4 attempts", "retried after WORKER_MISMATCH", "Lite dispatched
six workers") was recordable and nothing objected.

This module owns ``dispatch-log.json``. The orchestrator calls it to *plan* the
fan-out and to *record* each event, and it **refuses** illegal ones. Triage stops
being a judgment call and becomes a computed function of depth, manifest and
question shape.

    plan    → compute the tier assignment and write PENDING/NOT_DISPATCHED entries
    record  → apply one event, rejecting illegal transitions and attempt overruns
    quorum  → recompute what verdict the current states permit

CLI:
    python3 dispatch.py plan --log run/dispatch-log.json --ticker MSFT \\
        --depth Standard --archetype "Hyperscaler" --manifest run/data-manifest.json \\
        --question-shape valuation,moat
    python3 dispatch.py record --log run/dispatch-log.json \\
        --worker stock-business-reviewer --event launched
    python3 dispatch.py record --log run/dispatch-log.json \\
        --worker stock-business-reviewer --event validated --status OK --duration 214
    python3 dispatch.py quorum --log run/dispatch-log.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from . import runbundle as RB
    from . import worker_contract as WC
except ImportError:  # direct CLI invocation
    import runbundle as RB  # type: ignore
    import worker_contract as WC  # type: ignore

TIER0 = RB.TIER0
TIER1 = RB.TIER1
MAX_ATTEMPTS = RB.MAX_ATTEMPTS
DEPTHS = ("Lite", "Standard", "Strict")

# Archetypes where capital allocation IS the thesis, so the management worker is
# not optional even at Lite depth.
STEWARDSHIP_ARCHETYPES = (
    "Mature Cash Cow", "Capital-Intensive", "Financials", "Bank", "Insurance", "REIT",
)

QUESTION_SHAPES = ("full", "valuation", "moat", "stewardship", "specific")

# event -> (allowed prior states, resulting state)
TRANSITIONS: dict[str, tuple[tuple[str, ...], str]] = {
    "launched":  (("PENDING",), "RUNNING"),
    "returned":  (("RUNNING",), "RETURNED"),
    "validated": (("RETURNED",), "VALIDATED"),
    "invalid":   (("RETURNED",), "INVALID_OUTPUT"),
    "timeout":   (("RUNNING",), "TIMEOUT"),
    "crashed":   (("RUNNING",), "CRASHED"),
    # A retry re-enters the machine; only a recoverable failure may do so.
    "retry":     (("INVALID_OUTPUT", "TIMEOUT", "CRASHED"), "RUNNING"),
    "failed":    (("INVALID_OUTPUT", "TIMEOUT", "CRASHED"), "FAILED"),
}

# `validated` splits by the payload's own status: a worker that correctly declined
# is not a validation failure, but it does not cover its dimension either.
STATUS_TO_STATE = {
    "OK": "VALIDATED", "DEGRADED": "VALIDATED",
    "SKIPPED": "SKIPPED", "REFUSED": "REFUSED",
}


class IllegalTransition(Exception):
    """Raised when an event would produce a history the protocol forbids."""


# --------------------------------------------------------------------------- #
# plan — triage as a computed function
# --------------------------------------------------------------------------- #

def tier1_trigger(worker: str, depth: str, archetype: str, manifest: dict,
                  shapes: list[str]) -> str | None:
    """Return the trigger string that fires, or None. Mirrors
    dispatch-protocol.md Part 1 Tier 1 — that file documents it, this decides it."""
    if depth in ("Standard", "Strict"):
        return f"depth={depth}"

    if worker == "stock-management-reviewer":
        filings = manifest.get("filings") or {}
        has_proxy = bool(filings.get("DEF14A"))
        has_transcript = bool(manifest.get("transcripts"))
        if has_proxy and has_transcript:
            return "DEF14A + transcript both present"
        if "stewardship" in shapes or "full" in shapes:
            return "stewardship-shaped question"
        if any(a.lower() in str(archetype).lower() for a in STEWARDSHIP_ARCHETYPES):
            return f"archetype={archetype} (capital allocation is the thesis)"
        return None

    if worker == "stock-peer-comparison-reviewer":
        peers = manifest.get("peers") or []
        if len(peers) < 2:
            return None
        if {"valuation", "moat", "full"} & set(shapes):
            return f"{len(peers)} peers + valuation/moat-shaped question"
        return None

    raise ValueError(f"{worker} is not a Tier-1 worker")


def plan(ticker: str, depth: str, archetype: str, manifest: dict,
         shapes: list[str]) -> dict:
    if depth not in DEPTHS:
        raise IllegalTransition(f"depth {depth!r} not in {DEPTHS}")
    for shape in shapes:
        if shape not in QUESTION_SHAPES:
            raise IllegalTransition(f"question shape {shape!r} not in {QUESTION_SHAPES}")
    if not archetype:
        raise IllegalTransition("archetype is required — workers echo it back for verification")

    # A missing 10-K stops the whole fan-out; workers cannot analyze from press
    # releases and the manifest is the only place that fact lives.
    filings = manifest.get("filings") or {}
    if not filings.get("10K"):
        raise IllegalTransition(
            "data-manifest has no 10-K: dispatch nothing and report a data-unavailable failure"
        )

    workers = []
    for name in TIER0:
        workers.append({
            "worker": name, "tier": 0, "trigger": "always-on",
            "state": "PENDING", "attempts": 0, "errors": [],
        })
    for name in TIER1:
        trigger = tier1_trigger(name, depth, archetype, manifest, shapes)
        if trigger:
            workers.append({
                "worker": name, "tier": 1, "trigger": trigger,
                "state": "PENDING", "attempts": 0, "errors": [],
            })
        else:
            workers.append({
                "worker": name, "tier": 1,
                "trigger": f"NOT FIRED (depth={depth}, peers={len(manifest.get('peers') or [])},"
                           f" shapes={','.join(shapes) or 'none'})",
                "state": "NOT_DISPATCHED", "attempts": 0, "errors": [],
            })

    return {
        "ticker": ticker,
        "depth_mode": depth,
        "archetype": archetype,
        "question_shapes": shapes,
        "workers": workers,
        "wave_2": [],
        "quorum": {"tier0_validated": 0, "tier0_required": len(TIER0), "verdict_permitted": "none"},
    }


# --------------------------------------------------------------------------- #
# record — one event, or a refusal
# --------------------------------------------------------------------------- #

def _entry(log: dict, worker: str, wave: int) -> dict:
    key = "workers" if wave == 1 else "wave_2"
    matches = [e for e in log.get(key, []) if e.get("worker") == worker]
    if not matches:
        raise IllegalTransition(
            f"{worker} is not in {key} — run `plan` first (or `record --wave 2 --event dispatched`)"
        )
    if len(matches) > 1:
        # Returning the first would silently apply the event to one of two
        # indistinguishable histories.
        raise IllegalTransition(
            f"{worker} has {len(matches)} entries in {key} — its history is ambiguous."
            f" A worker is dispatched once per wave; remove the duplicate."
        )
    return matches[0]


def record(log: dict, worker: str, event: str, status: str | None = None,
           duration: float | None = None, error_code: str | None = None,
           reason: str | None = None, wave: int = 1) -> dict:
    if worker not in WC.WORKERS:
        raise IllegalTransition(f"unknown worker {worker!r}")

    if event == "dispatched":
        if wave != 2:
            raise IllegalTransition("the 'dispatched' event only opens a second-wave entry")
        if not reason:
            raise IllegalTransition(
                "a second-wave dispatch requires --reason: it fires only on a named contradiction"
            )
        if any(e.get("worker") == worker for e in log.get("wave_2", [])):
            raise IllegalTransition(
                f"{worker} already has a wave-2 entry. A worker is re-dispatched once per"
                f" named conflict; a second entry makes its history ambiguous and hides"
                f" one of the two replies from the bundle gate."
            )
        cap = RB.SECOND_WAVE_CAP.get(log.get("depth_mode"), 2)
        if len(log.setdefault("wave_2", [])) >= cap:
            raise IllegalTransition(
                f"second-wave cap of {cap} reached for depth {log.get('depth_mode')}:"
                f" the conflict is not resolvable by more agents — record it as an"
                f" unresolved tension and default the verdict to Hold"
            )
        log["wave_2"].append({
            "worker": worker, "reason": reason, "state": "PENDING",
            "attempts": 0, "errors": [],
            # The gate looks for workers/<worker>.wave2.md, so name it here rather
            # than leaving the convention to memory.
            "artifact_stem": f"{worker}.wave2",
        })
        return log

    if event not in TRANSITIONS:
        raise IllegalTransition(f"unknown event {event!r}; expected one of {sorted(TRANSITIONS)}")

    entry = _entry(log, worker, wave)
    current = entry.get("state")
    allowed, target = TRANSITIONS[event]

    if current == "NOT_DISPATCHED":
        raise IllegalTransition(
            f"{worker} was not dispatched (its Tier-1 trigger did not fire); re-plan"
            f" rather than recording events against it"
        )
    if current not in allowed:
        raise IllegalTransition(
            f"{worker}: event {event!r} requires state in {allowed}, but it is {current!r}"
        )

    if event in ("launched", "retry"):
        attempts = int(entry.get("attempts") or 0) + 1
        if attempts > MAX_ATTEMPTS:
            raise IllegalTransition(
                f"{worker}: attempt {attempts} exceeds the cap of {MAX_ATTEMPTS}"
                f" — retrying twice on the same input mostly reproduces the failure."
                f" Record 'failed' and degrade the report honestly"
            )
        entry["attempts"] = attempts

    if event == "retry":
        if error_code and error_code not in WC.RETRYABLE:
            raise IllegalTransition(
                f"{worker}: {error_code} is not retryable — that class means the dispatch"
                f" itself was wrong, so fix the dispatch and re-plan instead of re-asking"
            )
        if current == "INVALID_OUTPUT" and not error_code:
            raise IllegalTransition(
                f"{worker}: a retry out of INVALID_OUTPUT requires --error-code so the"
                f" retryable/non-retryable decision is recorded, not assumed"
            )

    if event == "validated":
        if status not in STATUS_TO_STATE:
            raise IllegalTransition(
                f"{worker}: 'validated' requires --status in {sorted(STATUS_TO_STATE)}"
                f" (the payload's own status determines the state)"
            )
        target = STATUS_TO_STATE[status]
        entry["status"] = status

    if event in ("invalid", "timeout", "crashed"):
        if not error_code and event == "invalid":
            raise IllegalTransition(f"{worker}: 'invalid' requires --error-code from the validator")
        if error_code:
            entry.setdefault("errors", []).append(
                {"attempt": entry.get("attempts"), "code": error_code}
            )
        entry.pop("status", None)

    if event == "failed":
        if int(entry.get("attempts") or 0) < MAX_ATTEMPTS:
            raise IllegalTransition(
                f"{worker}: 'failed' recorded after {entry.get('attempts')} attempt(s) — the"
                f" policy allows one retry, so retry first or state why it was skipped"
            )
        entry.pop("status", None)

    entry["state"] = target
    if duration is not None:
        entry["duration_s"] = duration

    log["quorum"] = quorum(log)
    return log


# --------------------------------------------------------------------------- #
# quorum — recomputed, never asserted
# --------------------------------------------------------------------------- #

def quorum(log: dict) -> dict:
    by_name = {e.get("worker"): e for e in log.get("workers", [])}
    ok = sum(
        1 for name in TIER0
        if by_name.get(name, {}).get("state") in RB.COUNTS_FOR_QUORUM
        and by_name.get(name, {}).get("status") in ("OK", "DEGRADED")
    )
    missing = len(TIER0) - ok
    permitted = "full" if missing == 0 else ("degraded" if missing == 1 else "none")
    out = {"tier0_validated": ok, "tier0_required": len(TIER0), "verdict_permitted": permitted}
    bs = by_name.get("stock-balance-sheet-reviewer", {})
    if bs.get("state") not in RB.COUNTS_FOR_QUORUM:
        out["verdict_ceiling"] = "Watch"
        out["ceiling_reason"] = "balance-sheet dimension uncovered — Bear floor unsupported"
    if permitted == "degraded":
        out["conviction_ceiling"] = "Low"
    return out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _read(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write(path: Path, log: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(log, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="enforce the dispatch state machine over dispatch-log.json")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="compute the tier assignment and write the initial log")
    p.add_argument("--log", required=True)
    p.add_argument("--ticker", required=True)
    p.add_argument("--depth", required=True, choices=DEPTHS)
    p.add_argument("--archetype", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--question-shape", default="full",
                   help=f"comma-separated, from {QUESTION_SHAPES}")

    r = sub.add_parser("record", help="apply one state-machine event")
    r.add_argument("--log", required=True)
    r.add_argument("--worker", required=True)
    r.add_argument("--event", required=True)
    r.add_argument("--status", help="required for --event validated")
    r.add_argument("--duration", type=float)
    r.add_argument("--error-code", help="validator error code, for invalid/retry")
    r.add_argument("--reason", help="required for a second-wave dispatch")
    r.add_argument("--wave", type=int, default=1, choices=(1, 2))

    q = sub.add_parser("quorum", help="recompute what verdict the current states permit")
    q.add_argument("--log", required=True)

    args = ap.parse_args(argv)
    log_path = Path(args.log)

    try:
        if args.cmd == "plan":
            shapes = [s.strip() for s in args.question_shape.split(",") if s.strip()]
            log = plan(args.ticker, args.depth, args.archetype, _read(Path(args.manifest)), shapes)
            _write(log_path, log)
            dispatched = [w["worker"] for w in log["workers"] if w["state"] == "PENDING"]
            print(json.dumps({
                "log": str(log_path), "depth_mode": args.depth,
                "dispatching": dispatched, "fan_out": len(dispatched),
                "not_dispatched": [
                    {"worker": w["worker"], "trigger": w["trigger"]}
                    for w in log["workers"] if w["state"] == "NOT_DISPATCHED"
                ],
            }, indent=2, ensure_ascii=False))
            return 0

        if args.cmd == "record":
            log = record(_read(log_path), args.worker, args.event, status=args.status,
                         duration=args.duration, error_code=args.error_code,
                         reason=args.reason, wave=args.wave)
            _write(log_path, log)
            entry = _entry(log, args.worker, args.wave)
            print(json.dumps({"worker": args.worker, "state": entry["state"],
                              "attempts": entry.get("attempts"),
                              "quorum": log["quorum"]}, indent=2, ensure_ascii=False))
            return 0

        log = _read(log_path)
        print(json.dumps(quorum(log), indent=2, ensure_ascii=False))
        return 0

    except IllegalTransition as exc:
        print(json.dumps({"refused": str(exc)}, indent=2, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""Persistent, locked budget ledger for one deep-research session."""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, Iterator

from .planning import MODE_BUDGETS

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None

try:
    import msvcrt
except ImportError:  # pragma: no cover - POSIX
    msvcrt = None

SESSION_SCHEMA = "deep-research/session-v1"
BUDGET_KEYS = {
    "retrieval_calls": "retrieval_max",
    "content_extractions": "content_max",
    "report_sources": "report_sources_max",
}


class BudgetExceededError(RuntimeError):
    """Raised before work begins when a session budget cannot be reserved."""


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _atomic_write(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    temp_path = Path(handle.name)
    try:
        with handle:
            json.dump(payload, handle, indent=2, ensure_ascii=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


@contextlib.contextmanager
def _lock(path: Path) -> Iterator[None]:
    lock_path = path.with_name(f"{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            backend = "fcntl"
        elif msvcrt is not None:  # pragma: no cover - exercised on Windows
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            backend = "msvcrt"
        else:  # pragma: no cover - unsupported platform guard
            raise RuntimeError(
                "no supported cross-process session lock backend is available"
            )
        try:
            yield
        finally:
            if backend == "fcntl":
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            else:  # pragma: no cover - exercised on Windows
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def _validate_session(payload: Any, path: Path) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(f"session artifact must be an object: {path}")
    if payload.get("schema") != SESSION_SCHEMA:
        raise ValueError(f"unsupported session schema in {path}")
    mode = str(payload.get("mode", ""))
    budget = payload.get("budget")
    usage = payload.get("usage")
    if (
        mode not in MODE_BUDGETS
        or not isinstance(budget, dict)
        or not isinstance(usage, dict)
    ):
        raise ValueError(f"session artifact is incomplete: {path}")
    canonical_budget = MODE_BUDGETS[mode]
    for key, expected in canonical_budget.items():
        try:
            actual = int(budget.get(key, -1))
        except (TypeError, ValueError):
            actual = -1
        if actual != expected:
            raise ValueError(
                f"session budget {key} is not canonical for {mode}: {path}"
            )
    for usage_key, limit_key in BUDGET_KEYS.items():
        value = usage.get(usage_key)
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
            or value > canonical_budget[limit_key]
        ):
            raise ValueError(
                f"invalid session usage {usage_key} in {path}"
            )
    if not isinstance(payload.get("events", []), list):
        raise ValueError(f"session events must be an array: {path}")
    return payload


def load_session(path: Path, expected_mode: str = "") -> Dict[str, Any]:
    payload = _validate_session(json.loads(path.read_text()), path)
    if expected_mode and payload["mode"] != expected_mode:
        raise ValueError(
            f"session mode is {payload['mode']}, not requested {expected_mode}"
        )
    return payload


def _budget_is_canonical(mode: str, budget: Any) -> bool:
    if mode not in MODE_BUDGETS or not isinstance(budget, dict):
        return False
    for key, expected in MODE_BUDGETS[mode].items():
        value = budget.get(key)
        if isinstance(value, bool):
            return False
        try:
            actual = int(value)
        except (TypeError, ValueError):
            return False
        if actual != expected:
            return False
    return True


def initialize_session(path: Path, plan: Dict[str, Any]) -> Dict[str, Any]:
    mode = str(plan.get("mode", ""))
    budget = plan.get("budget")
    if not _budget_is_canonical(mode, budget):
        raise ValueError("plan must contain mode and budget")
    payload = dict(plan)
    payload.update(
        {
            "budget": dict(MODE_BUDGETS[mode]),
            "schema": SESSION_SCHEMA,
            "session_id": uuid.uuid4().hex,
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
            "usage": {
                "retrieval_calls": 0,
                "content_extractions": 0,
                "report_sources": 0,
            },
            "events": [],
        }
    )
    with _lock(path):
        if path.exists():
            raise FileExistsError(
                f"session artifact already exists; refuse to reset ledger: {path}"
            )
        _atomic_write(path, payload)
    return payload


def reserve_session_budget(
    path: Path,
    key: str,
    requested: int,
    *,
    allow_partial: bool,
) -> Dict[str, Any]:
    if key not in BUDGET_KEYS:
        raise ValueError(f"unsupported budget key: {key}")
    if requested < 0:
        raise ValueError("requested budget must be non-negative")
    with _lock(path):
        state = load_session(path)
        limit_key = BUDGET_KEYS[key]
        limit = int(state["budget"][limit_key])
        used = int(state["usage"].get(key, 0))
        remaining = max(0, limit - used)
        if requested > remaining and not allow_partial:
            raise BudgetExceededError(
                f"session {state['session_id']} has {remaining} {key} remaining; "
                f"requested {requested}"
            )
        reserved = min(requested, remaining)
        exhausted = reserved < requested
        state["usage"][key] = used + reserved
        state["updated_at"] = utc_now_iso()
        state.setdefault("events", []).append(
            {
                "at": state["updated_at"],
                "type": "budget_reservation",
                "budget": key,
                "requested": requested,
                "reserved": reserved,
                "remaining": remaining - reserved,
                "exhausted": exhausted,
            }
        )
        _atomic_write(path, state)
    return {
        "session_id": state["session_id"],
        "budget": key,
        "requested": requested,
        "reserved": reserved,
        "remaining": remaining - reserved,
        "exhausted": exhausted,
    }


def record_report_sources(path: Path, count: int) -> Dict[str, Any]:
    """Record the current report's source count; this ceiling is per report."""
    if count < 0:
        raise ValueError("report source count must be non-negative")
    with _lock(path):
        state = load_session(path)
        limit = int(state["budget"]["report_sources_max"])
        if count > limit:
            raise BudgetExceededError(
                f"{state['mode']} report permits at most {limit} verified cited "
                f"sources; received {count}"
            )
        state["usage"]["report_sources"] = count
        state["updated_at"] = utc_now_iso()
        state.setdefault("events", []).append(
            {
                "at": state["updated_at"],
                "type": "report_sources",
                "count": count,
                "limit": limit,
            }
        )
        _atomic_write(path, state)
    return state

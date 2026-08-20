"""finlib.worker_contract — deterministic validator for the Worker Findings Contract.

The orchestrator dispatches six worker agents and synthesizes a verdict from what
they return. Before this module the return path was free-form Markdown: a worker
that dropped a field, emitted malformed JSON, or answered for the wrong ticker
failed *silently* — its findings simply never reached the report.

This module is the gate. It extracts the single ``findings-json`` fence from a
worker reply, validates it against contract v1 (see
``references/worker-contract.md``), and returns stable error codes the dispatch
state machine can branch on. Formatting errors are retryable; dispatch-identity
errors are not.

CLI:
    python3 worker_contract.py validate --reply run/workers/business.md \\
        [--expect-worker stock-business-reviewer] [--expect-depth Standard] \\
        [--expect-archetype "Hyperscaler / Mega-Cap Tech Platform"] \\
        [--require-checks BUS-11,BUS-09]
    python3 worker_contract.py consolidate --replies run/workers/*.md --cap 15
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys

CONTRACT_VERSION = "1"

STATUSES = ("OK", "DEGRADED", "SKIPPED", "REFUSED")
SEVERITIES = ("High", "Medium", "Low")
CONFIDENCES = ("first-hand", "second-hand")
CITATION_SOURCES = (
    "10-K", "10-Q", "DEF14A", "8-K", "transcript", "Form4",
    "financials.json", "peer-filing", "aggregator",
)

# Agent -> (skill, prefix). Single source of truth for the fan-out; the
# orchestration-matrix test asserts SKILL.md and every worker skill agree with it.
WORKERS: dict[str, tuple[str, str]] = {
    "stock-business-reviewer": ("stock-business-review", "BUS"),
    "stock-earnings-quality-reviewer": ("stock-earnings-quality-review", "EQ"),
    "stock-balance-sheet-reviewer": ("stock-balance-sheet-review", "BS"),
    "stock-management-reviewer": ("stock-management-review", "MGT"),
    "stock-industry-reviewer": ("stock-industry-review", "IND"),
    "stock-peer-comparison-reviewer": ("stock-peer-comparison-review", "P"),
}

PREFIXES = {prefix for _, prefix in WORKERS.values()}

# Errors that mean "the worker formatted its answer wrong" — re-asking can fix it.
# Everything else means the dispatch itself was wrong; re-asking cannot fix it.
RETRYABLE = {
    "MISSING_BLOCK", "MULTIPLE_BLOCKS", "BAD_JSON", "BAD_VERSION",
    "MISSING_FIELD", "BAD_TYPE", "BAD_STATUS", "BAD_SEVERITY", "BAD_PREFIX",
    "BAD_CITATION", "CONFIDENCE_MISMATCH", "COVERAGE_INCOMPLETE",
    "MANDATORY_CHECK_MISSING",
}

_FENCE = re.compile(r"^[ \t]*```[ \t]*findings-json[ \t]*\r?\n(.*?)^[ \t]*```", re.S | re.M)

SEVERITY_RANK = {"High": 0, "Medium": 1, "Low": 2}
# Consolidation orders equal-severity findings by the fan-out order above, so a
# report's finding sequence is reproducible across runs.
WORKER_ORDER = {prefix: i for i, (_, prefix) in enumerate(WORKERS.values())}


class Err:
    """One validation failure. ``code`` is stable; ``detail`` is for humans."""

    __slots__ = ("code", "detail")

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail

    def as_dict(self) -> dict:
        return {"code": self.code, "detail": self.detail, "retryable": self.code in RETRYABLE}


def extract_block(reply: str) -> tuple[dict | None, list[Err]]:
    """Pull the single ``findings-json`` fence out of a worker reply."""
    blocks = _FENCE.findall(reply)
    if not blocks:
        return None, [Err("MISSING_BLOCK", "no ```findings-json fence in reply")]
    if len(blocks) > 1:
        return None, [Err("MULTIPLE_BLOCKS", f"{len(blocks)} findings-json fences; expected exactly 1")]
    try:
        payload = json.loads(blocks[0])
    except json.JSONDecodeError as exc:
        return None, [Err("BAD_JSON", f"{exc.msg} at line {exc.lineno} col {exc.colno}")]
    if not isinstance(payload, dict):
        return None, [Err("BAD_TYPE", f"payload must be a JSON object, got {type(payload).__name__}")]
    return payload, []


def _check_citation(cit, where: str, confidence, errs: list[Err]) -> None:
    if not isinstance(cit, dict):
        errs.append(Err("BAD_CITATION", f"{where}: citation must be an object, got {type(cit).__name__}"))
        return
    source = cit.get("source")
    if source not in CITATION_SOURCES:
        errs.append(Err("BAD_CITATION", f"{where}: source {source!r} not in {CITATION_SOURCES}"))
    for field in ("locator", "fiscal_period"):
        value = cit.get(field)
        if not isinstance(value, str) or not value.strip():
            errs.append(Err("BAD_CITATION", f"{where}: citation.{field} must be a non-empty string"))
    if source == "aggregator" and confidence == "first-hand":
        errs.append(Err("CONFIDENCE_MISMATCH", f"{where}: aggregator source cannot be first-hand"))


def _check_finding(item, index: int, prefix: str, errs: list[Err]) -> None:
    where = f"findings[{index}]"
    if not isinstance(item, dict):
        errs.append(Err("BAD_TYPE", f"{where} must be an object"))
        return
    for field in ("id", "severity", "title", "citation", "evidence", "implication", "confidence"):
        if field not in item:
            errs.append(Err("MISSING_FIELD", f"{where}.{field} is required"))
    fid = item.get("id")
    if isinstance(fid, str):
        # Prefix is the whole segment before the first hyphen, so "P" can never
        # absorb an ID belonging to another worker.
        got = fid.split("-", 1)[0]
        if got != prefix:
            errs.append(Err("BAD_PREFIX", f"{where}.id {fid!r} has prefix {got!r}, payload declares {prefix!r}"))
    elif "id" in item:
        errs.append(Err("BAD_TYPE", f"{where}.id must be a string"))
    if item.get("severity") not in SEVERITIES and "severity" in item:
        errs.append(Err("BAD_SEVERITY", f"{where}.severity {item.get('severity')!r} not in {SEVERITIES}"))
    if item.get("confidence") not in CONFIDENCES and "confidence" in item:
        errs.append(Err("BAD_TYPE", f"{where}.confidence {item.get('confidence')!r} not in {CONFIDENCES}"))
    for field in ("title", "evidence", "implication"):
        value = item.get(field)
        if field in item and (not isinstance(value, str) or not value.strip()):
            errs.append(Err("BAD_TYPE", f"{where}.{field} must be a non-empty string"))
    if "citation" in item:
        _check_citation(item["citation"], where, item.get("confidence"), errs)


def validate(
    payload: dict,
    expect_worker: str | None = None,
    expect_depth: str | None = None,
    expect_archetype: str | None = None,
    require_checks: list[str] | None = None,
) -> list[Err]:
    """Validate a payload against contract v1. Returns [] when it is clean."""
    errs: list[Err] = []

    if payload.get("contract_version") != CONTRACT_VERSION:
        errs.append(Err(
            "BAD_VERSION",
            f"contract_version {payload.get('contract_version')!r} != {CONTRACT_VERSION!r}",
        ))
        # An unknown contract version means the field layout below is not
        # guaranteed. Refuse rather than best-effort parse a foreign shape.
        return errs

    required = (
        "worker", "prefix", "status", "depth_mode", "archetype_applied",
        "archetype_challenge", "findings", "positives", "data_gaps",
        "checklist_coverage", "mandatory_checks_run",
    )
    for field in required:
        if field not in payload:
            errs.append(Err("MISSING_FIELD", f"{field} is required"))

    prefix = payload.get("prefix")
    if prefix not in PREFIXES:
        errs.append(Err("BAD_PREFIX", f"prefix {prefix!r} not in {sorted(PREFIXES)}"))

    status = payload.get("status")
    if status not in STATUSES:
        errs.append(Err("BAD_STATUS", f"status {status!r} not in {STATUSES}"))
    elif status != "OK":
        reason = payload.get("status_reason")
        if not isinstance(reason, str) or not reason.strip():
            errs.append(Err("MISSING_FIELD", f"status_reason is required when status={status}"))

    for field in ("findings", "positives", "data_gaps", "mandatory_checks_run"):
        if field in payload and not isinstance(payload[field], list):
            errs.append(Err("BAD_TYPE", f"{field} must be an array"))

    findings = payload.get("findings")
    if isinstance(findings, list) and isinstance(prefix, str):
        for i, item in enumerate(findings):
            _check_finding(item, i, prefix, errs)

    positives = payload.get("positives")
    if isinstance(positives, list):
        for i, item in enumerate(positives):
            if not isinstance(item, dict):
                errs.append(Err("BAD_TYPE", f"positives[{i}] must be an object"))
                continue
            if "citation" in item:
                _check_citation(item["citation"], f"positives[{i}]", item.get("confidence"), errs)

    challenge = payload.get("archetype_challenge")
    if challenge is not None and "archetype_challenge" in payload:
        if not isinstance(challenge, dict):
            errs.append(Err("BAD_TYPE", "archetype_challenge must be an object or null"))
        else:
            for field in ("proposed", "reason"):
                value = challenge.get(field)
                if not isinstance(value, str) or not value.strip():
                    errs.append(Err("MISSING_FIELD", f"archetype_challenge.{field} is required"))

    coverage = payload.get("checklist_coverage")
    if "checklist_coverage" in payload:
        if not isinstance(coverage, dict):
            errs.append(Err("BAD_TYPE", "checklist_coverage must be an object"))
        else:
            nums = {}
            for field in ("items_total", "items_checked", "items_not_found"):
                value = coverage.get(field)
                if not isinstance(value, int) or isinstance(value, bool):
                    errs.append(Err("BAD_TYPE", f"checklist_coverage.{field} must be an integer"))
                else:
                    nums[field] = value
            if len(nums) == 3 and nums["items_checked"] + nums["items_not_found"] < nums["items_total"]:
                errs.append(Err(
                    "COVERAGE_INCOMPLETE",
                    f"checked {nums['items_checked']} + not_found {nums['items_not_found']}"
                    f" < total {nums['items_total']}: the checklist did not run to completion",
                ))

    # Dispatch-identity checks. These are non-retryable: they mean the wrong agent
    # answered, or answered a different question than the one dispatched.
    if expect_worker is not None and payload.get("worker") != expect_worker:
        errs.append(Err("WORKER_MISMATCH", f"worker {payload.get('worker')!r} != dispatched {expect_worker!r}"))
    if expect_worker in WORKERS and payload.get("prefix") not in (None, WORKERS[expect_worker][1]):
        errs.append(Err(
            "BAD_PREFIX",
            f"worker {expect_worker} must use prefix {WORKERS[expect_worker][1]!r},"
            f" got {payload.get('prefix')!r}",
        ))
    if expect_depth is not None and payload.get("depth_mode") != expect_depth:
        errs.append(Err("DEPTH_MISMATCH", f"depth_mode {payload.get('depth_mode')!r} != dispatched {expect_depth!r}"))
    if expect_archetype is not None and payload.get("archetype_applied") != expect_archetype:
        # A worker that filed a challenge is *allowed* to disagree — that is the
        # de-correlation channel, not a protocol violation.
        if challenge is None:
            errs.append(Err(
                "ARCHETYPE_MISMATCH",
                f"archetype_applied {payload.get('archetype_applied')!r} != dispatched"
                f" {expect_archetype!r} and no archetype_challenge filed",
            ))

    if require_checks:
        ran = payload.get("mandatory_checks_run")
        ran_set = set(ran) if isinstance(ran, list) else set()
        # A worker that never ran (SKIPPED/REFUSED) cannot be faulted for a
        # mandatory check it was never able to reach.
        if status in ("OK", "DEGRADED"):
            for check in require_checks:
                if check not in ran_set:
                    errs.append(Err(
                        "MANDATORY_CHECK_MISSING",
                        f"archetype-required check {check!r} absent from mandatory_checks_run",
                    ))

    return errs


def validate_reply(reply: str, **kwargs) -> tuple[dict | None, list[Err]]:
    payload, errs = extract_block(reply)
    if payload is None:
        return None, errs
    return payload, validate(payload, **kwargs)


def consolidate(payloads: list[dict], cap: int | None = None) -> dict:
    """Merge validated payloads into the orchestrator's Step 5a working set.

    Dedup key is (severity, normalized title) across workers: two workers
    reporting the same mechanism merge into one finding carrying both prefixes.
    Distinct mechanisms with related causes stay separate — that is the
    orchestrator's judgment call, not something to collapse mechanically.
    """
    merged: dict[tuple[str, str], dict] = {}
    order: list[tuple[str, str]] = []
    for payload in payloads:
        if payload.get("status") in ("SKIPPED", "REFUSED"):
            continue
        for item in payload.get("findings", []):
            key = (item.get("severity", ""), re.sub(r"\W+", " ", str(item.get("title", "")).lower()).strip())
            if key in merged:
                merged[key].setdefault("also_reported_by", []).append(payload.get("prefix"))
                continue
            merged[key] = dict(item, reported_by=payload.get("prefix"))
            order.append(key)

    findings = [merged[k] for k in order]
    findings.sort(key=lambda f: (
        SEVERITY_RANK.get(f.get("severity", "Low"), 3),
        WORKER_ORDER.get(f.get("reported_by", ""), 99),
        str(f.get("id", "")),
    ))

    suppressed = 0
    if cap is not None and len(findings) > cap:
        # Truncate Low first, per the volume-cap rule; never drop a High to fit.
        keep = [f for f in findings if f.get("severity") != "Low"][:cap]
        room = cap - len(keep)
        if room > 0:
            keep += [f for f in findings if f.get("severity") == "Low"][:room]
        suppressed = len(findings) - len(keep)
        findings = keep

    challenges = [
        {"worker": p.get("worker"), **p["archetype_challenge"]}
        for p in payloads
        if isinstance(p.get("archetype_challenge"), dict)
    ]
    proposals: dict[str, int] = {}
    for challenge in challenges:
        proposals[challenge.get("proposed", "")] = proposals.get(challenge.get("proposed", ""), 0) + 1

    return {
        "contract_version": CONTRACT_VERSION,
        "findings": findings,
        "suppressed_count": suppressed,
        "by_severity": {
            sev: sum(1 for f in findings if f.get("severity") == sev) for sev in SEVERITIES
        },
        "workers_consumed": [p.get("worker") for p in payloads if p.get("status") in ("OK", "DEGRADED")],
        "workers_excluded": [p.get("worker") for p in payloads if p.get("status") in ("SKIPPED", "REFUSED")],
        "degraded": [
            {"worker": p.get("worker"), "reason": p.get("status_reason")}
            for p in payloads if p.get("status") == "DEGRADED"
        ],
        "data_gaps": [g for p in payloads for g in p.get("data_gaps", [])],
        "archetype_challenges": challenges,
        # ≥2 workers proposing the same alternative means the lead's
        # classification is presumed wrong: re-classify and re-dispatch.
        "archetype_contested": any(count >= 2 for count in proposals.values()),
    }


def _cmd_validate(args) -> int:
    with open(args.reply, encoding="utf-8") as f:
        reply = f.read()
    require = [c.strip() for c in args.require_checks.split(",") if c.strip()] if args.require_checks else None
    payload, errs = validate_reply(
        reply,
        expect_worker=args.expect_worker,
        expect_depth=args.expect_depth,
        expect_archetype=args.expect_archetype,
        require_checks=require,
    )
    result = {
        "reply": args.reply,
        "worker": (payload or {}).get("worker"),
        "status": (payload or {}).get("status"),
        "verdict": "PASS" if not errs else "FAIL",
        "errors": [e.as_dict() for e in errs],
        "retryable": bool(errs) and all(e.code in RETRYABLE for e in errs),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not errs else 1


def _cmd_consolidate(args) -> int:
    paths: list[str] = []
    for pattern in args.replies:
        expanded = sorted(glob.glob(pattern))
        paths.extend(expanded or [pattern])
    payloads, failures = [], []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            payload, errs = validate_reply(f.read())
        if errs:
            failures.append({"reply": path, "errors": [e.as_dict() for e in errs]})
        else:
            payloads.append(payload)
    out = consolidate(payloads, cap=args.cap)
    out["invalid_replies"] = failures
    print(json.dumps(out, indent=2, ensure_ascii=False))
    # An invalid reply is a dropped dimension. Fail so the caller cannot
    # synthesize a verdict while believing all workers were consumed.
    return 1 if failures else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="validate/consolidate Worker Findings Contract v1 payloads")
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="validate one worker reply")
    v.add_argument("--reply", required=True)
    v.add_argument("--expect-worker")
    v.add_argument("--expect-depth")
    v.add_argument("--expect-archetype")
    v.add_argument("--require-checks", help="comma-separated archetype-required check IDs")
    v.set_defaults(func=_cmd_validate)

    c = sub.add_parser("consolidate", help="merge validated replies into the Step 5a working set")
    c.add_argument("--replies", nargs="+", required=True)
    c.add_argument("--cap", type=int)
    c.set_defaults(func=_cmd_consolidate)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

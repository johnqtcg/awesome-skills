"""finlib.runbundle — fail-closed evidence gate for a run bundle, in two stages.

The report claims to rest on the workers' evidence. Without that evidence on disk,
the claim is unfalsifiable: a reader cannot distinguish a faithful synthesis from
an invented one, and no run can be replayed as a regression.

**Two stages, because the artifacts do not all exist at the same time.** The first
version of this gate required ``verdict.json`` at Step 5d-ter, which runs *before*
Step 5f produces a verdict — following the documented order could only fail.

| Stage | Runs at | Requires | Question it answers |
|---|---|---|---|
| ``evidence`` | Step 5d-ter, pre-verdict | manifest · financials · dispatch-log · consolidated · every dispatched worker's reply + payload | may I synthesize a verdict from this? |
| ``publication`` | after Step 5g | the above **plus** metrics · lint · verdict · report | may I show this to the user? |

Nothing is a warning if it changes whether the report is trustworthy. Absent
``lint.json`` used to PASS with a note, which meant "the 口径 gate left no evidence
it ran" was indistinguishable from "it ran and passed".

Beyond file presence, the gate checks that the artifacts **agree with each other**:

* every extracted payload equals the payload actually in its raw reply
* ``consolidated.json`` is reproducible by re-running consolidation — compared on
  **every** field of every finding, not just the IDs
* ``report.md`` carries each finding faithfully: matching severity, the worker's
  citation locator, and the worker's evidence and implication verbatim
  (``report_audit.py``) — an ID-substring check could only catch a *dropped*
  finding, never a distorted one
* ``verdict.json`` passes the full schema validation of ``verdictlog.py`` inside
  this gate, so publication does not depend on the caller having run it separately
* the model digest in ``verdict.json`` matches ``model.json``, and at publication
  stage the digest is **required**
* the second wave is audited identically to the first: terminal state, attempts,
  duration, reply and payload on disk, contract validity, and inclusion in
  consolidation
* every retry left its superseded reply on disk
* the dispatch log's own state transitions, attempt counts and caps are legal
* the quorum is **recomputed** from states, never read from the log's summary

CLI:
    python3 runbundle.py check --run <dir> --stage evidence
    python3 runbundle.py check --run <dir> --stage publication
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

try:
    from . import report_audit as RA
    from . import verdictlog as VL
    from . import worker_contract as WC
except ImportError:  # direct CLI invocation
    import report_audit as RA  # type: ignore
    import verdictlog as VL  # type: ignore
    import worker_contract as WC  # type: ignore

WORKERS = WC.WORKERS
validate_reply = WC.validate_reply

# --------------------------------------------------------------------------- #
# state model — mirrors dispatch-protocol.md Part 2
# --------------------------------------------------------------------------- #

# A payload that validated is on disk in extracted form, whatever status it
# carried. SKIPPED/REFUSED are validated payloads too — the worker made a correct
# judgment and said so through the contract.
STATES_WITH_PAYLOAD = ("VALIDATED", "SKIPPED", "REFUSED")
# A reply exists but no payload could be extracted from it.
STATES_WITH_RAW_ONLY = ("RETURNED", "INVALID_OUTPUT")
# No reply reached the orchestrator at all.
STATES_WITHOUT_REPLY = ("TIMEOUT", "CRASHED", "FAILED", "NOT_DISPATCHED", "PENDING", "RUNNING")

ALL_STATES = STATES_WITH_PAYLOAD + STATES_WITH_RAW_ONLY + STATES_WITHOUT_REPLY

# States that may still legally be occupied when a bundle is checked. A bundle
# with a worker still PENDING or RUNNING is mid-flight, not finished.
NON_TERMINAL_STATES = ("PENDING", "RUNNING", "RETURNED")

# Only these count toward the Tier-0 quorum.
COUNTS_FOR_QUORUM = ("VALIDATED",)

TIER0 = (
    "stock-business-reviewer",
    "stock-earnings-quality-reviewer",
    "stock-balance-sheet-reviewer",
    "stock-industry-reviewer",
)
TIER1 = ("stock-management-reviewer", "stock-peer-comparison-reviewer")

MAX_ATTEMPTS = 2                       # one dispatch + at most one retry
SECOND_WAVE_CAP = {"Lite": 2, "Standard": 2, "Strict": 3}
FINDING_CAP = {"Lite": 8, "Standard": 15, "Strict": 25}

# --------------------------------------------------------------------------- #
# per-stage required artifacts — fail-closed, no warnings
# --------------------------------------------------------------------------- #

EVIDENCE_FILES = (
    "data-manifest.json",
    "financials.json",
    "dispatch-log.json",
    "consolidated.json",
)
PUBLICATION_FILES = EVIDENCE_FILES + ("metrics.json", "lint.json", "verdict.json", "report.md")

STAGES = {"evidence": EVIDENCE_FILES, "publication": PUBLICATION_FILES}


def _load_json(path: Path, errors: list[str], label: str):
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"{label}: unreadable ({exc.strerror})")
        return None
    if not text.strip():
        errors.append(f"{label}: present but empty")
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        errors.append(f"{label}: invalid JSON — {exc.msg} at line {exc.lineno}")
        return None


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


# Every field of a finding that the report is allowed to render. Projecting only
# id/severity let a bundle keep an ID while rewriting the evidence, the citation or
# the conclusion — "faithful" was checkable in exactly one direction.
FINDING_FIELDS = (
    "id", "severity", "title", "citation", "evidence", "implication",
    "confidence", "reported_by",
)


def _projection(consolidated: dict) -> dict:
    """The part of a consolidation result that must be reproducible.

    Excludes only list orderings that legitimately depend on which glob the caller
    passed (``workers_consumed``). Everything a reader could act on is compared,
    including the full text of each finding.
    """
    return {
        "findings": [
            {
                **{key: f.get(key) for key in FINDING_FIELDS},
                "also_reported_by": sorted(f.get("also_reported_by") or []),
            }
            for f in consolidated.get("findings", [])
        ],
        "by_severity": consolidated.get("by_severity"),
        "suppressed_count": consolidated.get("suppressed_count"),
        "archetype_contested": consolidated.get("archetype_contested"),
        "data_gaps": consolidated.get("data_gaps"),
        "archetype_challenges": consolidated.get("archetype_challenges"),
        "workers_excluded": sorted(consolidated.get("workers_excluded") or []),
        "degraded": sorted(
            (d.get("worker") or "") for d in (consolidated.get("degraded") or [])
        ),
    }


# --------------------------------------------------------------------------- #
# dispatch-log structural + transition validation
# --------------------------------------------------------------------------- #

def _check_entry(entry: dict, label: str, wave: int, errors: list[str]) -> str | None:
    """Validate one dispatch-log entry. Shared by both waves — wave 2 previously
    got only a name/reason/cap check, so a second-wave worker could carry a
    non-terminal state, four attempts, or no duration and nothing objected."""
    name = entry.get("worker")
    if name not in WORKERS:
        errors.append(f"{label}: unknown worker {name!r}")
        return None

    state = entry.get("state")
    if state not in ALL_STATES:
        errors.append(f"{label} {name}: state {state!r} is not a known dispatch state")
        return name
    if state in NON_TERMINAL_STATES:
        errors.append(
            f"{label} {name}: state {state} is non-terminal — the bundle is mid-flight,"
            f" not a finished run"
        )

    if wave == 1:
        expected_tier = 0 if name in TIER0 else 1
        if entry.get("tier") != expected_tier:
            errors.append(
                f"{name}: tier {entry.get('tier')!r} recorded, but it is a"
                f" Tier-{expected_tier} worker"
            )

    attempts = entry.get("attempts")
    if state == "NOT_DISPATCHED":
        if attempts not in (0, None):
            errors.append(f"{name}: NOT_DISPATCHED but attempts={attempts!r}")
        if not entry.get("trigger") and not entry.get("reason"):
            errors.append(f"{name}: NOT_DISPATCHED must record the trigger that did not fire")
        return name

    if not isinstance(attempts, int) or isinstance(attempts, bool) or not 1 <= attempts <= MAX_ATTEMPTS:
        errors.append(
            f"{label} {name}: attempts {attempts!r} outside 1..{MAX_ATTEMPTS}"
            f" — the retry policy allows one dispatch plus at most one retry"
        )
    if wave == 1 and name in TIER1 and not entry.get("trigger"):
        errors.append(f"{name}: Tier-1 worker dispatched without recording its trigger")
    if wave == 2 and not entry.get("reason"):
        errors.append(
            f"{label} {name}: no reason — a second wave fires only on a named contradiction"
        )

    errs = entry.get("errors")
    if not isinstance(errs, list):
        errors.append(f"{label} {name}: errors must be an array (empty when none)")
        errs = []
    if isinstance(attempts, int) and attempts > 1 and not errs:
        errors.append(
            f"{label} {name}: attempts={attempts} but errors[] is empty — a retry must"
            f" record the error class that justified it"
        )
    for err in errs:
        if isinstance(err, dict) and err.get("code") in (
            "WORKER_MISMATCH", "DEPTH_MISMATCH", "ARCHETYPE_MISMATCH",
        ):
            errors.append(
                f"{label} {name}: non-retryable error {err['code']} recorded as a retry cause"
                f" — that class means the dispatch was wrong, so it must be re-planned"
            )
    if not isinstance(entry.get("duration_s"), (int, float)):
        errors.append(f"{label} {name}: duration_s must be a number on a terminal state")
    return name


def _check_dispatch_log(log: dict, errors: list[str]) -> tuple[dict[str, dict], list[dict]]:
    """Validate the log's internal legality.

    Returns ``({worker: wave-1 entry}, [wave-2 entries])``. Wave 2 is returned as a
    list rather than folded into the mapping so a re-dispatched worker's two
    histories stay distinguishable — collapsing them by name is what made the
    second wave invisible to the disk-footprint and contract checks.
    """
    depth = log.get("depth_mode")
    if depth not in FINDING_CAP:
        errors.append(f"dispatch-log: depth_mode {depth!r} not in {sorted(FINDING_CAP)}")
    if not log.get("archetype"):
        errors.append("dispatch-log: archetype is required (workers echo it back)")

    wave1 = log.get("workers")
    if not isinstance(wave1, list) or not wave1:
        errors.append("dispatch-log: workers must be a non-empty array")
        wave1 = []
    wave2 = log.get("wave_2") or []
    if not isinstance(wave2, list):
        errors.append("dispatch-log: wave_2 must be an array")
        wave2 = []

    seen: dict[str, dict] = {}
    for entry in wave1:
        if not isinstance(entry, dict):
            errors.append("dispatch-log: workers[] entries must be objects")
            continue
        name = _check_entry(entry, "wave 1", 1, errors)
        if name is None:
            continue
        if name in seen:
            errors.append(f"dispatch-log: {name} appears twice in wave 1")
        seen[name] = entry

    for name in TIER0:
        if name not in seen:
            errors.append(f"dispatch-log: Tier-0 worker {name} is absent — it is always dispatched")
    for name in TIER1:
        if name not in seen:
            errors.append(
                f"dispatch-log: Tier-1 worker {name} is absent — record it as NOT_DISPATCHED"
                f" with the trigger that did not fire, rather than omitting it"
            )

    cap = SECOND_WAVE_CAP.get(depth, 2)
    if len(wave2) > cap:
        errors.append(
            f"dispatch-log: {len(wave2)} second-wave dispatches exceeds the {depth} cap of {cap}"
        )
    wave2_names: list[str] = []
    checked_wave2: list[dict] = []
    for entry in wave2:
        if not isinstance(entry, dict):
            errors.append("dispatch-log: wave_2[] entries must be objects")
            continue
        name = _check_entry(entry, "wave 2", 2, errors)
        if name is None:
            continue
        if name in wave2_names:
            errors.append(
                f"dispatch-log: {name} has two wave-2 entries — a worker is re-dispatched"
                f" once per named conflict, and two entries make its history ambiguous"
            )
        wave2_names.append(name)
        checked_wave2.append(entry)

    return seen, checked_wave2


# --------------------------------------------------------------------------- #
# main check
# --------------------------------------------------------------------------- #

def check(run_dir: Path, stage: str = "evidence") -> dict:
    errors: list[str] = []

    if stage not in STAGES:
        return {"run": str(run_dir), "stage": stage, "verdict": "FAIL",
                "errors": [f"unknown stage {stage!r}; expected one of {sorted(STAGES)}"]}

    if not run_dir.is_dir():
        return {"run": str(run_dir), "stage": stage, "verdict": "FAIL",
                "errors": [f"run dir not found: {run_dir}"]}

    for name in STAGES[stage]:
        path = run_dir / name
        if not path.exists():
            errors.append(f"missing required bundle file for stage {stage}: {name}")
        elif not path.stat().st_size:
            errors.append(f"{name}: present but empty")

    log = _load_json(run_dir / "dispatch-log.json", errors, "dispatch-log.json") \
        if (run_dir / "dispatch-log.json").exists() else None

    logged: dict[str, dict] = {}
    wave2: list[dict] = []
    if isinstance(log, dict):
        logged, wave2 = _check_dispatch_log(log, errors)
    elif log is not None:
        errors.append("dispatch-log.json: top level must be an object")

    depth = (log or {}).get("depth_mode") if isinstance(log, dict) else None
    archetype = (log or {}).get("archetype") if isinstance(log, dict) else None

    workers_dir = run_dir / "workers"
    on_disk_raw = {p.stem for p in workers_dir.glob("*.md")} if workers_dir.is_dir() else set()
    on_disk_payload = {p.stem for p in workers_dir.glob("*.json")} if workers_dir.is_dir() else set()

    # ---- every logged worker's disk footprint must match its state ---------- #
    def _audit_worker(name: str, entry: dict, stem: str, label: str) -> dict | None:
        """Disk footprint + contract validation for one dispatch attempt.

        ``stem`` is the filename base: ``<worker>`` for wave 1,
        ``<worker>.wave2`` for the second wave. Shared so the second wave is held
        to the same standard as the first.
        """
        state = entry.get("state")
        if state not in ALL_STATES:
            return None

        if state in STATES_WITH_PAYLOAD or state in STATES_WITH_RAW_ONLY:
            if not (workers_dir / f"{stem}.md").exists():
                errors.append(f"{label}: state {state} but workers/{stem}.md is absent")
        if state in STATES_WITH_PAYLOAD and not (workers_dir / f"{stem}.json").exists():
            errors.append(f"{label}: state {state} but workers/{stem}.json is absent")
        if state in STATES_WITHOUT_REPLY and (workers_dir / f"{stem}.md").exists():
            errors.append(
                f"{label}: state {state} claims no reply arrived, yet workers/{stem}.md exists"
            )

        attempts = entry.get("attempts")
        if isinstance(attempts, int) and attempts > 1:
            for i in range(1, attempts):
                if not (workers_dir / f"{stem}.attempt{i}.md").exists():
                    errors.append(
                        f"{label}: attempts={attempts} but workers/{stem}.attempt{i}.md is"
                        f" absent — the failed reply is the evidence the retry was justified"
                    )

        raw = workers_dir / f"{stem}.md"
        if state not in STATES_WITH_PAYLOAD or not raw.exists():
            return None

        payload, errs = validate_reply(
            raw.read_text(encoding="utf-8"),
            expect_worker=name,
            expect_depth=depth,
            expect_archetype=archetype if entry.get("archetype_challenge_filed") is not True else None,
        )
        if errs:
            codes = ", ".join(sorted({e.code for e in errs}))
            errors.append(f"{label}: logged {state} but its reply fails contract validation ({codes})")
            return None

        if payload.get("status") != entry.get("status"):
            errors.append(
                f"{label}: dispatch-log records status {entry.get('status')!r}"
                f" but the reply payload says {payload.get('status')!r}"
            )
        expected_state = {"OK": "VALIDATED", "DEGRADED": "VALIDATED",
                          "SKIPPED": "SKIPPED", "REFUSED": "REFUSED"}.get(payload.get("status"))
        if expected_state and state != expected_state:
            errors.append(
                f"{label}: payload status {payload.get('status')} implies state"
                f" {expected_state}, but the log records {state}"
            )

        extracted = _load_json(workers_dir / f"{stem}.json", errors, f"workers/{stem}.json") \
            if (workers_dir / f"{stem}.json").exists() else None
        if extracted is not None and _canonical(extracted) != _canonical(payload):
            errors.append(
                f"{label}: workers/{stem}.json does not match the payload extracted from"
                f" workers/{stem}.md — the extraction was edited after the fact"
            )
        return payload

    validated_payloads: list[dict] = []
    for name, entry in sorted(logged.items()):
        payload = _audit_worker(name, entry, name, name)
        if payload is not None:
            validated_payloads.append(payload)

    # The second wave answers a scoped follow-up whose findings reach the report,
    # so it is audited identically and its payloads enter consolidation.
    wave2_payloads: list[dict] = []
    for entry in wave2:
        name = entry.get("worker")
        payload = _audit_worker(name, entry, f"{name}.wave2", f"wave 2 {name}")
        if payload is not None:
            wave2_payloads.append(payload)


    wave2_names = {e.get("worker") for e in wave2}
    for stem in sorted(on_disk_raw - set(logged)):
        base = re.sub(r"\.(attempt\d+|wave2)$", "", stem)
        if base != stem and (base in logged or base in wave2_names):
            continue          # a legitimate retry / second-wave artifact
        errors.append(f"workers/{stem}.md exists but {stem} is absent from dispatch-log.json")
    # A wave-2 stem with no wave-2 entry is the mirror-image leak.
    for stem in sorted(on_disk_raw):
        if stem.endswith(".wave2") and stem[:-len(".wave2")] not in wave2_names:
            errors.append(
                f"workers/{stem}.md exists but no wave_2 entry claims it — an unrecorded"
                f" second-wave dispatch"
            )

    # ---- consolidation must be reproducible from the replies ---------------- #
    consolidated = None
    if (run_dir / "consolidated.json").exists():
        consolidated = _load_json(run_dir / "consolidated.json", errors, "consolidated.json")
    consolidation_input = validated_payloads + wave2_payloads
    if isinstance(consolidated, dict) and consolidation_input and depth in FINDING_CAP:
        recomputed = WC.consolidate(consolidation_input, cap=FINDING_CAP[depth])
        if _projection(recomputed) != _projection(consolidated):
            errors.append(
                "consolidated.json is not reproducible from the worker replies —"
                " re-run `worker_contract.py consolidate` instead of editing it"
            )

    # ---- stage-gated: lint, quorum, verdict, report ------------------------ #
    tier0_ok = sum(
        1 for name in TIER0
        if logged.get(name, {}).get("state") in COUNTS_FOR_QUORUM
        and logged.get(name, {}).get("status") in ("OK", "DEGRADED")
    )
    missing_tier0 = len(TIER0) - tier0_ok
    permitted = "full" if missing_tier0 == 0 else ("degraded" if missing_tier0 == 1 else "none")

    recorded = (log or {}).get("quorum") if isinstance(log, dict) else None
    if isinstance(recorded, dict):
        if recorded.get("tier0_validated") != tier0_ok:
            errors.append(
                f"quorum mismatch: log records tier0_validated={recorded.get('tier0_validated')}"
                f" but the states give {tier0_ok}"
            )
        if recorded.get("verdict_permitted") != permitted:
            errors.append(
                f"quorum mismatch: log records verdict_permitted={recorded.get('verdict_permitted')!r}"
                f" but the states give {permitted!r}"
            )
    elif isinstance(log, dict):
        errors.append("dispatch-log.json: missing quorum block")

    if (run_dir / "lint.json").exists():
        lint = _load_json(run_dir / "lint.json", errors, "lint.json")
        if isinstance(lint, dict):
            fails = lint.get("fail") or lint.get("failures") or []
            if fails:
                errors.append(f"lint.json records {len(fails)} FAIL(s) — the 口径 gate blocks the report")
        elif lint is not None:
            errors.append("lint.json: top level must be an object")

    verdict = None
    if (run_dir / "verdict.json").exists():
        verdict = _load_json(run_dir / "verdict.json", errors, "verdict.json")
        if isinstance(verdict, dict):
            # A final publication gate must not depend on the caller having
            # remembered to run `verdictlog.py validate` separately. Missing
            # probabilities or an unsummable set would otherwise reach the log.
            for message in VL.validate_entry(verdict):
                errors.append(f"verdict.json: {message}")
        if permitted == "none":
            errors.append(
                f"verdict.json exists but only {tier0_ok}/{len(TIER0)} Tier-0 workers validated"
                f" — the quorum forbids a verdict"
            )
        if isinstance(verdict, dict):
            if permitted == "degraded" and verdict.get("conviction") != "Low":
                errors.append(
                    f"a degraded quorum caps conviction at Low, got {verdict.get('conviction')!r}"
                )
            if verdict.get("quorum") != permitted and permitted != "none":
                errors.append(
                    f"verdict.json records quorum {verdict.get('quorum')!r}"
                    f" but the states give {permitted!r}"
                )
            bs = logged.get("stock-balance-sheet-reviewer", {})
            if bs.get("state") not in COUNTS_FOR_QUORUM and verdict.get("verdict") in ("Strong Buy", "Buy"):
                errors.append(
                    f"the balance-sheet worker did not validate, so the Bear floor is unsupported"
                    f" and verdict {verdict.get('verdict')!r} is not permitted (cap at Watch)"
                )

            # The model digest ties the recorded targets to the model that produced them.
            model_meta = verdict.get("model")
            if stage == "publication" and not (
                isinstance(model_meta, dict) and model_meta.get("model_json_sha256")
            ):
                errors.append(
                    "verdict.json has no model.model_json_sha256 — a published target must"
                    " be tied by digest to the model that produced it, or it is unverifiable"
                )
            if isinstance(model_meta, dict) and model_meta.get("model_json_sha256"):
                model_path = run_dir / "model.json"
                if not model_path.exists():
                    errors.append("verdict.json records a model digest but model.json is absent")
                else:
                    actual = hashlib.sha256(model_path.read_bytes()).hexdigest()
                    if actual != model_meta["model_json_sha256"]:
                        errors.append(
                            "model digest mismatch: verdict.json records"
                            f" {model_meta['model_json_sha256'][:12]}… but model.json hashes to"
                            f" {actual[:12]}… — the recorded targets did not come from this model"
                        )

    # The report must carry the evidence faithfully, not merely mention its IDs.
    # A substring check on the ID caught a *dropped* finding and nothing else:
    # keeping the ID while rewriting the evidence, softening the implication or
    # swapping the citation all passed.
    if stage == "publication" and (run_dir / "report.md").exists() and isinstance(consolidated, dict):
        report = (run_dir / "report.md").read_text(encoding="utf-8")
        for message in RA.audit(consolidated, report):
            errors.append(f"report.md: {message}")

    return {
        "run": str(run_dir),
        "stage": stage,
        "verdict": "PASS" if not errors else "FAIL",
        "depth_mode": depth,
        "tier0_validated": tier0_ok,
        "verdict_permitted": permitted,
        "workers_logged": sorted(logged),
        "payloads_consumed": len(validated_payloads),
        "wave2_dispatched": [e.get("worker") for e in wave2],
        "wave2_payloads_consumed": len(wave2_payloads),
        "errors": errors,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="fail-closed evidence gate for a stock-analysis run bundle")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--run", required=True)
    c.add_argument("--stage", choices=sorted(STAGES), default="evidence",
                   help="evidence = pre-verdict (Step 5d-ter); publication = post-5g")
    args = ap.parse_args(argv)
    result = check(Path(args.run), stage=args.stage)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

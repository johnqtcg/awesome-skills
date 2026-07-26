#!/usr/bin/env python3
"""A scripted stand-in for a live writer, used to prove the live-eval harness plumbing.

Why this exists: `LiveForwardEval` is skipped unless `TECH_DOC_EVAL_CMD` is set, so until a real
model was wired up nothing had ever executed its prompt assembly, its `LOAD:` round-trip, or the
hand-off into `grade()`. A harness that has never run once is not a gap in coverage — it is
untested code that will fail the first time someone points a model at it.

**What this proves and what it does not.** Running the live class against this stub proves the
plumbing: the prompt is assembled and delivered, a `LOAD: references/<name>` request is honoured
on a second turn with the file the stub asked for, the response reaches the grader, and a
scenario's own exemplar grades as a pass. It proves nothing whatsoever about model behaviour —
the stub replays a known-good document instead of writing one. Only `TECH_DOC_EVAL_CMD` pointed
at a real model measures that.

Usage (from the skill directory):

    TECH_DOC_EVAL_CMD="python3 scripts/tests/stub_writer.py" \
        python3 -m unittest test_forward_eval.LiveForwardEval

Modes, via `STUB_MODE`:
  replay   (default) request the fixture's reference on turn 1, then emit its `good.md`
  bad                emit the scenario's `bad.md` — the harness must report a FAILURE
  no_load            never emit `LOAD:`, so a fixture pinning a reference must fail
"""

import json
import os
import re
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
GOLDEN_DIR = TESTS_DIR / "golden"
EVAL_DIR = TESTS_DIR / "forward_eval"

# Scenario -> fixture file, mirroring test_forward_eval.SCENARIOS. Kept as data here rather than
# imported so the stub stays runnable as a plain command from any working directory.
SCENARIOS = {
    "runbook_write": "001_write_api_runbook.json",
    "audience_unknown": "004_audience_unknown_degradation.json",
    "improve_minimal_diff": "006_improve_existing_doc.json",
    "review_troubleshooting": "002_review_troubleshooting_doc.json",
    "scaffold_level3": "005_insufficient_info_scaffold.json",
}

SECOND_TURN_MARKER = "References you requested are above"


def identify(prompt: str):
    """Match the prompt back to a scenario via its fixture's `user_request`.

    The live harness sends only the skill, the reference menu, and the user request — never the
    scenario name — so the stub has to recognise the request the same way a reader would. A
    normalised longest-overlap match is used because the Improve scenario appends the original
    document to its request.
    """
    norm = " ".join(prompt.split())
    best, best_len = None, 0
    for scenario, fixture_name in SCENARIOS.items():
        fixture = json.loads((GOLDEN_DIR / fixture_name).read_text(encoding="utf-8"))
        request = " ".join(fixture["user_request"].split())
        if request and request in norm and len(request) > best_len:
            best, best_len = (scenario, fixture), len(request)
    return best


def main() -> int:
    prompt = sys.stdin.read()
    mode = os.environ.get("STUB_MODE", "replay")

    found = identify(prompt)
    if not found:
        # Loud, not silent: an unrecognised prompt means the harness changed how it frames the
        # request, and a stub that quietly emitted a default document would hide that.
        print("STUB ERROR: prompt matched no known scenario", file=sys.stderr)
        return 2
    scenario, fixture = found

    first_turn = SECOND_TURN_MARKER not in prompt
    wanted = fixture.get("reference_to_load")
    if first_turn and wanted and mode != "no_load":
        # Exercise the LOAD protocol. Emitting only this line means the harness must run a
        # second turn — if it ever stops doing so, the grader sees no document and fails.
        # Under `no_load` this is skipped, so the response answers without ever receiving the
        # file and the fixture's reference pin is put under test.
        print(f"LOAD: references/{Path(wanted).name}")
        return 0

    name = "bad.md" if mode == "bad" else "good.md"
    text = (EVAL_DIR / scenario / name).read_text(encoding="utf-8")
    # Strip any `LOAD:` line the exemplar carries, so a replay of turn two is not read as a
    # fresh request.
    sys.stdout.write(re.sub(r"(?m)^\s*LOAD:.*\n", "", text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

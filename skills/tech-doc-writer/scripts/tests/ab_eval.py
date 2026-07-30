#!/usr/bin/env python3
"""With-skill vs. without-skill A/B forward evaluation against a live model.

`LiveForwardEval` in test_forward_eval.py measures one arm: does a model *following this skill*
produce a document the grader accepts. That answers "does the skill work" but not "does the skill
add anything" — a base model good enough to pass unaided would look identical.

This runner drives both arms through the same grader:

  with-skill     prompt = SKILL.md + reference-offer protocol + user request
  without-skill  prompt = user request + the output-shape hint alone

The without arm still gets told *what shape* to emit. Without that it fails on formatting rather
than on substance, and the comparison would only prove that the base model does not guess this
skill's private output contract — an uninteresting result. Everything the skill actually teaches
(gate order, resolution path, applicable-item denominators, verification levels, minimal-diff)
is withheld.

Usage
-----
    TECH_DOC_EVAL_CMD='claude -p --model sonnet --tools "" \\
                       --permission-mode dontAsk --strict-mcp-config' \\
      python3 scripts/tests/ab_eval.py [--scenario runbook_write] [--arm with|without] \\
                                       [--out report.json]

Exit code is 0 whenever both arms completed, whatever they scored: this is a measurement, not a
gate. A non-zero exit means the harness itself could not run.

Isolating the model command
---------------------------
Every flag above is load-bearing when the model command is a nested Claude Code run, and getting
this wrong produces a result that looks like a *skill* failure:

- ``--permission-mode dontAsk`` — a nested run **inherits the parent session's permission
  mode**. Launched from a session in plan mode, the writer replied "I'm in plan mode but the
  tools this workflow requires aren't available" and never emitted a document. All seven grader
  checks failed, none of them because of the skill.
- ``--tools ""`` — with tools available the writer explores the working directory and reasons
  about the repository it happens to land in, instead of answering from the prompt. The fixtures
  describe a corpus-free run (see ``RUN_CONTEXT``).
- ``--strict-mcp-config`` — otherwise the nested run inherits the parent's MCP servers, and the
  writer consults session memory about *this* conversation.
- ``cwd`` is set to a system temp directory by ``run_model`` for the same reason: from inside
  this repository the nested run reads the local ``CLAUDE.md`` and can auto-load the very skill
  under test, which silently contaminates the without-skill arm.

A harness error is never a score. If an arm reports total failure, check the raw output in the
``--out`` report before concluding anything about the skill.

Reading the results
-------------------
**Do not compare raw failure counts across arms.** Two checks are structurally asymmetric:

- The reference check scores the with arm twice — did it cite the file, *and* did it request it
  over ``LOAD:`` — while the without arm is offered no references and can only fail the first. In
  the 2026-07-30 run this alone accounted for the with arm's apparently worse total.
- ``LOAD:`` is an artefact **invented by this harness** so progressive disclosure is observable.
  A real Claude Code run has ``Read``/``Grep`` and never sees the protocol, so failing it is weak
  evidence about the skill.
- Only an arm that reports scorecard arithmetic can report it *wrongly*. "No arithmetic at all"
  and "arithmetic off by one" both count as one failure, and they are not the same defect.

Compare per-check, and prefer the checks that measure a behaviour both arms could exhibit:
scorecard arithmetic present/absent, minimal-diff line count, and lint criticals on the emitted
document.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parents[1]


def _harness():
    """Import test_forward_eval for its fixtures and grader — one grader, both arms.

    Registered in sys.modules before execution: the module uses `from __future__ import
    annotations` with dataclass-style resolution, which fails on a by-path load otherwise.
    """
    spec = importlib.util.spec_from_file_location(
        "test_forward_eval", TESTS_DIR / "test_forward_eval.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["test_forward_eval"] = mod
    spec.loader.exec_module(mod)
    return mod


H = _harness()

# The without arm is told the output shape and nothing else. Withholding the shape would make it
# fail on a formatting technicality and inflate the measured gap.
SHAPE_HINT = """\
Answer with a technical document, then a trailing block in exactly this shape:

── tech-doc-writer output ──
mode:           Write | Review | Improve
resolution:     R1 (retrieved) | R2 (asked) | R3 (assumed) — plus what resolved it
degradation:    Level 1 (Full) | Level 2 (Partial) | Level 3 (Scaffold)
doc_type:       concept | task | reference | troubleshooting | design
audience:       <role> / <goal> / <prior knowledge>
scorecard:      Critical: <n>/<applicable> | Standard: <n>/<applicable> | Hygiene: <n>/<applicable>
files:          [paths]
maintenance:    cadence: <monthly|quarterly|biannually>; triggers: <comma-separated>
assumptions:    [list, or "none"]

Put the document itself in a fenced ```markdown block.
"""


def run_model(cmd: str, prompt: str, timeout: int) -> str:
    proc = subprocess.run(cmd, shell=True, input=prompt, capture_output=True,
                          text=True, timeout=timeout, errors="replace",
                          # A neutral cwd keeps the nested run from picking up this
                          # repository's CLAUDE.md and auto-loading the very skill under test,
                          # which would contaminate the without-skill arm.
                          cwd=tempfile.gettempdir())
    if proc.returncode != 0 and not proc.stdout.strip():
        raise RuntimeError(f"model command failed ({proc.returncode}): {proc.stderr[:500]}")
    return proc.stdout


def build_request(fixture: dict) -> str:
    request = fixture["user_request"]
    if fixture.get("original_document"):
        request += ("\n\nExisting document:\n```markdown\n"
                    + fixture["original_document"] + "\n```")
    return request


def with_skill(cmd: str, fixture: dict, timeout: int) -> tuple[str, set]:
    """Skill in the prompt; references offered, not pre-loaded (see LiveForwardEval)."""
    refs = SKILL_DIR / "references"
    available = "\n".join(f"  - references/{p.name}" for p in sorted(refs.glob("*.md")))
    prompt = (
        H.SKILL_MD.read_text(encoding="utf-8")
        + "\n\n--- available references (NOT pre-loaded) ---\n" + available
        + "\nTo read one, emit a line `LOAD: references/<name>` before your answer; the "
          "contents will be supplied and you may then answer. Load only what the task needs.\n"
        + f"\n{H.RUN_CONTEXT}\n---\nUser request: {build_request(fixture)}\n")
    out = run_model(cmd, prompt, timeout)
    wanted = re.findall(r"(?m)^\s*LOAD:\s*references/([\w.-]+)", out)
    if wanted:
        supplied = "".join(
            f"\n\n--- references/{n} ---\n{(refs / n).read_text(encoding='utf-8')}"
            for n in dict.fromkeys(wanted) if (refs / n).is_file())
        out = run_model(
            cmd,
            f"{prompt}{supplied}\n\n(References you requested are above. "
            f"Now produce the full answer.)\n", timeout)
    return out, set(wanted)


def without_skill(cmd: str, fixture: dict, timeout: int) -> tuple[str, None]:
    prompt = (
        "You are a senior engineer writing internal technical documentation.\n\n"
        f"{SHAPE_HINT}\n{H.RUN_CONTEXT}\n---\nUser request: {build_request(fixture)}\n")
    return run_model(cmd, prompt, timeout), None


ARMS = {"with": with_skill, "without": without_skill}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", action="append", choices=sorted(H.SCENARIOS),
                    help="repeatable; default all")
    ap.add_argument("--arm", action="append", choices=sorted(ARMS), help="repeatable; default both")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--out", default=None, help="write the full JSON report here")
    args = ap.parse_args(argv)

    cmd = os.environ.get("TECH_DOC_EVAL_CMD")
    if not cmd:
        print("TECH_DOC_EVAL_CMD is unset — e.g. TECH_DOC_EVAL_CMD='claude -p --model sonnet'",
              file=sys.stderr)
        return 2
    if "stub_writer" in cmd:
        print("TECH_DOC_EVAL_CMD points at the stub. A stub replays a stored document; it "
              "cannot measure a model.", file=sys.stderr)
        return 2

    scenarios = args.scenario or sorted(H.SCENARIOS)
    arms = args.arm or ["with", "without"]
    report: dict = {"command": cmd, "results": {}}

    for scenario in scenarios:
        fixture = H.load_fixture(H.SCENARIOS[scenario])
        report["results"][scenario] = {}
        for arm in arms:
            tmp = Path(tempfile.mkdtemp(prefix=f"tdw-ab-{arm}-"))
            try:
                output, requested = ARMS[arm](cmd, fixture, args.timeout)
                passed, reasons = H.grade(output, fixture, tmp, requested=requested)
            except Exception as exc:                       # harness failure, not a model score
                print(f"[{scenario}/{arm}] HARNESS ERROR: {exc}", file=sys.stderr)
                report["results"][scenario][arm] = {"error": str(exc)}
                continue
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
            report["results"][scenario][arm] = {
                "passed": passed,
                "failure_count": len(reasons),
                "reasons": reasons,
                "requested_references": sorted(requested) if requested else [],
                "output_chars": len(output),
                "output": output,
            }
            verdict = "PASS" if passed else f"FAIL ({len(reasons)})"
            print(f"[{scenario}/{arm}] {verdict}")
            for reason in reasons:
                print(f"    - {reason}")

    print("\n=== summary ===")
    header = f"{'scenario':24s}" + "".join(f"{a:>12s}" for a in arms)
    print(header)
    tally = {a: [0, 0] for a in arms}
    for scenario in scenarios:
        row = f"{scenario:24s}"
        for arm in arms:
            r = report["results"][scenario].get(arm, {})
            if "error" in r:
                row += f"{'ERROR':>12s}"
                continue
            row += f"{('PASS' if r['passed'] else f'FAIL/{r['failure_count']}'):>12s}"
            tally[arm][0] += 1 if r["passed"] else 0
            tally[arm][1] += 1
        print(row)
    print()
    for arm in arms:
        ok, total = tally[arm]
        print(f"  {arm:8s} {ok}/{total} scenarios pass the grader")
    report["tally"] = {a: {"passed": t[0], "total": t[1]} for a, t in tally.items()}

    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                 encoding="utf-8")
        print(f"\nfull report: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

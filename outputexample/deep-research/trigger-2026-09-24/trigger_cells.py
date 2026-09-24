"""Trigger-rate cells for deep-research, 2026-09-24.

Derived from outputexample/deep-research/ab-2026-09-08/three-dimension/trigger_run.py
(same detector, same eval set) with three changes:

1. A fresh empty project root per cell, created with mkdtemp, instead of a fixed
   /tmp path the sandbox cannot write.
2. An optional SLASH_COMMAND_TOOL_CHAR_BUDGET override, so a wording effect can be
   separated from the skill-listing budget: with 102 skills installed the listing is
   44,715 chars against a 30,000 budget and least-invoked skills lose their
   description first.
3. --max-turns 4 for every cell (the trigger decision is the first tool call); the
   old-description baseline is re-run under the same settings rather than compared
   with the 2026-09-09 number, which was measured with 88 skills installed.

Usage: trigger_cells.py EVAL_SET OUT_JSON WHICH(pos|neg|all) [BUDGET]
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SKILL_NAME = "deep-research"
RUNS_PER_QUERY = 3
TIMEOUT = 300
MAX_TURNS = "4"


def run_once(query: str, index: int, rep: int, root: Path, budget: str) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    if budget:
        env["SLASH_COMMAND_TOOL_CHAR_BUDGET"] = budget
    cmd = ["claude", "-p", query, "--output-format", "stream-json", "--verbose",
           "--max-turns", MAX_TURNS]
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(root), env=env, capture_output=True,
                              timeout=TIMEOUT)
        raw = proc.stdout.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return {"index": index, "rep": rep, "triggered": False, "error": "timeout",
                "tools": [], "duration_s": round(time.time() - started, 1)}
    tools, triggered, fired_via = [], False, ""
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") != "assistant":
            continue
        msg = event.get("message")
        if not isinstance(msg, dict):
            continue
        for block in msg.get("content", []) or []:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            name = block.get("name", "")
            payload = json.dumps(block.get("input", {}))
            tools.append(name)
            if name == "Skill" and SKILL_NAME in payload:
                triggered, fired_via = True, "Skill tool"
            elif name == "Read" and f"{SKILL_NAME}/SKILL.md" in payload:
                triggered, fired_via = True, "Read of SKILL.md"
    error = "" if proc.returncode == 0 or tools else f"exit {proc.returncode}"
    if "Not logged in" in raw:
        error = "not logged in"
    return {"index": index, "rep": rep, "triggered": triggered, "fired_via": fired_via,
            "tools": tools, "duration_s": round(time.time() - started, 1), "error": error}


def main() -> int:
    eval_set = json.loads(Path(sys.argv[1]).read_text())
    out_path = Path(sys.argv[2])
    which = sys.argv[3]
    budget = sys.argv[4] if len(sys.argv) > 4 else ""
    root = Path(tempfile.mkdtemp(prefix="dr-trigger-root-"))
    jobs = [
        (item["query"], i, rep)
        for i, item in enumerate(eval_set)
        if which == "all" or (which == "pos") == item["should_trigger"]
        for rep in range(RUNS_PER_QUERY)
    ]
    print(f"{len(jobs)} runs, budget={budget or 'default'}, root={root}", flush=True)
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(run_once, q, i, r, root, budget) for q, i, r in jobs]
        for future in concurrent.futures.as_completed(futures):
            row = future.result()
            results.append(row)
            want = "want+" if eval_set[row["index"]]["should_trigger"] else "want-"
            mark = "TRIGGER" if row["triggered"] else "no"
            print(f"  q{row['index']:02d} r{row['rep']} {mark:7} {want} "
                  f"{row['duration_s']}s {row['error']} tools={row['tools'][:3]}", flush=True)
            out_path.write_text(json.dumps(results, indent=1))
    errors = sum(1 for r in results if r["error"])
    print(f"DONE {out_path.name}: {sum(r['triggered'] for r in results)}/{len(results)} "
          f"triggered, {errors} errors", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

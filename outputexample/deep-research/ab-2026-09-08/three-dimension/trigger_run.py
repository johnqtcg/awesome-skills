"""Trigger-accuracy runner for an already-installed skill.

Modelled on skill-creator's `scripts/run_eval.py`, with two deliberate changes,
both made because the stock harness would have mismeasured this skill:

1. No temporary command file. `deep-research` is installed at
   ~/.claude/skills/deep-research with a byte-identical `description`, so the
   stock harness's temp command would compete against the real skill for the
   same intent, and its detector — which matches only the temp name — would
   score a real-skill trigger as a miss.
2. The detector accepts any invocation of the skill: the Skill tool naming
   `deep-research`, or a Read of its SKILL.md. It also records what *did* fire,
   so a non-trigger can be explained rather than just counted.

This is the real user path: the query goes to a session where the skill is
installed alongside every other skill the user has, and we observe whether the
description wins.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import subprocess
import sys
import time
from pathlib import Path

SKILL_NAME = "deep-research"
PROJECT_ROOT = Path("/tmp/claude-503/dr_eval/root")
RUNS_PER_QUERY = 3
TIMEOUT = 240


def run_once(query: str, index: int, rep: int) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    cmd = [
        "claude", "-p", query,
        "--output-format", "stream-json",
        "--verbose",
        "--max-turns", "6",
    ]
    started = time.time()
    try:
        proc = subprocess.run(
            cmd, cwd=str(PROJECT_ROOT), env=env,
            capture_output=True, timeout=TIMEOUT,
        )
        raw = proc.stdout.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return {"index": index, "rep": rep, "triggered": False,
                "error": "timeout", "tools": [], "skills_advertised": None,
                "duration_s": round(time.time() - started, 1)}

    tools, triggered, fired_via, advertised = [], False, "", None
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except Exception:
            continue
        if event.get("type") == "system" and event.get("subtype") == "init":
            listed = event.get("skills") or event.get("available_skills")
            if isinstance(listed, list):
                advertised = len(listed)
        if event.get("type") != "assistant":
            continue
        for block in event.get("message", {}).get("content", []):
            if block.get("type") != "tool_use":
                continue
            name = block.get("name", "")
            payload = json.dumps(block.get("input", {}))
            tools.append(name)
            if name == "Skill" and SKILL_NAME in payload:
                triggered, fired_via = True, "Skill tool"
            elif name == "Read" and f"{SKILL_NAME}/SKILL.md" in payload:
                triggered, fired_via = True, "Read of SKILL.md"
    return {
        "index": index, "rep": rep, "triggered": triggered,
        "fired_via": fired_via, "tools": tools,
        "skills_advertised": advertised,
        "duration_s": round(time.time() - started, 1),
        "error": "",
    }


def main() -> int:
    eval_set = json.loads(Path(sys.argv[1]).read_text())
    out_path = Path(sys.argv[2])
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    only = sys.argv[4] if len(sys.argv) > 4 else ""

    jobs = []
    for i, item in enumerate(eval_set):
        if only == "pos" and not item["should_trigger"]:
            continue
        if only == "neg" and item["should_trigger"]:
            continue
        for rep in range(RUNS_PER_QUERY):
            jobs.append((item["query"], i, rep))

    existing = json.loads(out_path.read_text()) if out_path.exists() else []
    done = {(r["index"], r["rep"]) for r in existing}
    jobs = [j for j in jobs if (j[1], j[2]) not in done]
    print(f"{len(jobs)} runs to do ({len(done)} already recorded)", file=sys.stderr)

    results = list(existing)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run_once, q, i, r): (i, r) for q, i, r in jobs}
        for future in concurrent.futures.as_completed(futures):
            row = future.result()
            results.append(row)
            item = eval_set[row["index"]]
            mark = "TRIGGER   " if row["triggered"] else "no-trigger"
            expect = "want+" if item["should_trigger"] else "want-"
            print(f"  q{row['index']:02d} r{row['rep']} {mark} {expect} "
                  f"{row['duration_s']}s tools={row['tools'][:3]}", file=sys.stderr)
            out_path.write_text(json.dumps(results, indent=1))
    out_path.write_text(json.dumps(results, indent=1))
    print(f"wrote {len(results)} runs to {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Does the frontmatter `description` route this skill correctly?

WHY SEPARATELY FROM model_eval.py
---------------------------------
`model_eval.py` asks whether a model *carrying* this skill reviews well. It says
nothing about whether the skill is loaded in the first place. A description that
is precise but invisible produces a perfect review that never happens, and a
description that is greedy hijacks unrelated Redis questions — pub/sub, Streams,
persistence tuning — that §1 explicitly delegates elsewhere.

Two numbers, from one labelled corpus:

    recall     of the prompts this skill SHOULD handle, how many route to it
    precision  of the prompts that routed to it, how many it should handle

WHAT `--check` PROVES WITHOUT A MODEL
-------------------------------------
The corpus itself is a claim, and a corpus can be rigged: negatives that share
no vocabulary with the description make precision meaningless, and positives
that quote the description verbatim make recall meaningless. `--check` runs the
adversarial tests on the corpus rather than on the model:

  * every negative is a real Redis question, not an unrelated topic — otherwise
    precision is measured against a straw man;
  * at least a third of the negatives share vocabulary with the description, so
    the hard cases are actually present;
  * no positive is a verbatim substring of the description;
  * every out-of-scope area named in §1 appears among the negatives.

`--run` needs a model. Without one it exits 3, never 0.

Exit: 0 ok · 1 corpus or thresholds failed · 3 no model runner
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys

SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent
SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

# A nested `claude -p` inherits this session's permission mode, MCP servers,
# working directory and CLAUDE.md unless told otherwise. That contaminates the
# measurement -- the arm-A model is supposed to have NO skill, and an inherited
# project CLAUDE.md is a skill by another name -- and it is why an unqualified
# runner hangs waiting on a permission prompt. Isolate explicitly.
DEFAULT_RUNNER = (
    "claude -p --output-format text --permission-mode dontAsk "
    "--strict-mcp-config --disallowed-tools Bash,Edit,Write,Read"
)

RECALL_FLOOR = 0.85
PRECISION_FLOOR = 0.80

# Prompts this skill must handle. Phrased as a user would phrase them, including
# the vague ones -- "just add a cache" is in the description precisely because it
# is the request most likely to be answered without any of this.
POSITIVES: tuple[str, ...] = (
    "just add a cache in front of this query, it's slow",
    "our product page hits Postgres on every request, can we put Redis in front",
    "users see their old profile for a few minutes after they save it",
    "the database CPU spikes every 30 minutes exactly, right on the hour",
    "review this cache-aside implementation before I ship it",
    "should I use write-through or write-behind for the order table",
    "what TTL should I set on session data",
    "we get a thundering herd whenever the homepage cache expires",
    "someone is scanning random user IDs and every request reaches the DB",
    "one Redis node is at 100% CPU and the others are idle",
    "is SETNX enough for a lock around this payment call",
    "what happens to my service if Redis goes down",
    "how do I invalidate the cache when the row changes",
    "我们的缓存和数据库不一致，应该怎么设计失效策略",
    "design the caching layer for a multi-tenant SaaS dashboard",
)

# Redis questions this skill must NOT claim. Every one is in-domain for Redis and
# out of scope per §1 -- that is what makes them adversarial rather than filler.
# Each of these deliberately reuses the description's own vocabulary — "Redis",
# "cache", "design", "under load", "requests" — while landing in an area §1 or
# Gate 2 sends elsewhere. Negatives that share no words with the description
# are rejected by any router and would make precision free; `--check` enforces
# that this list stays hard.
NEGATIVES: tuple[str, ...] = (
    "how do I configure AOF vs RDB persistence in Redis for durability under load",
    "design a Redis Sentinel topology with three nodes for automatic failover",
    "my Redis Streams consumer group is lagging under load, how do I scale it",
    "reviewing our Redis pub/sub design for the notification fan-out",
    "generate Redis ACL rules so the cache user can only run read commands",
    "enable TLS between the app and the Redis cache with client certificates",
    "how do I reshard a Redis cluster and rebalance slots as requests grow",
    "write a Lua script that atomically increments a Redis leaderboard score",
    "the Redis RDB fork causes latency spikes under load, how do I tune it",
    "implement a sliding-window rate limiter in Redis for API requests",
    "configure Redis replication buffers as requests grow, the replica lags",
    "design a migration from Redis 6.2 to Redis 8.10 without downtime",
)

# §1 out-of-scope areas. Each must be represented in NEGATIVES, or the corpus
# claims a boundary it never tests.
OUT_OF_SCOPE_MARKERS: tuple[tuple[str, str], ...] = (
    ("persistence", r"aof|rdb|snapshot|persistence"),
    ("replication/topology", r"sentinel|cluster|failover|replica"),
    ("security", r"acl|tls|certificate"),
    ("non-cache data structures", r"stream|pub.?sub|channel|leaderboard"),
)


def description() -> str:
    m = re.search(r"^description:\s*>\s*\n((?:\s{2,}.*\n)+)", SKILL_MD, re.M)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", text.lower())}


def check_corpus() -> int:
    problems: list[str] = []
    desc = description()
    if not desc:
        print("CANNOT CHECK: frontmatter description did not parse", file=sys.stderr)
        return 1

    dwords = words(desc)

    # A negative that shares no vocabulary with the description is a straw man:
    # any router rejects it, and precision measured on straw men is free.
    hard = [n for n in NEGATIVES if len(words(n) & dwords) >= 2]
    if len(hard) < len(NEGATIVES) // 3:
        problems.append(
            f"only {len(hard)}/{len(NEGATIVES)} negatives share vocabulary with the "
            f"description — precision would be measured against easy cases")

    # A positive lifted from the description tests string matching, not routing.
    for p in POSITIVES:
        if p.lower() in desc.lower():
            problems.append(f"positive is verbatim in the description: {p!r}")

    for name, pat in OUT_OF_SCOPE_MARKERS:
        if not any(re.search(pat, n, re.I) for n in NEGATIVES):
            problems.append(f"§1 declares `{name}` out of scope but no negative tests it")

    if len(POSITIVES) < 10 or len(NEGATIVES) < 10:
        problems.append("corpus too small to produce a meaningful rate")

    overlap = set(POSITIVES) & set(NEGATIVES)
    if overlap:
        problems.append(f"prompt labelled both ways: {overlap}")

    print(f"trigger corpus: {len(POSITIVES)} positive · {len(NEGATIVES)} negative "
          f"({len(hard)} of them share the description's vocabulary)")
    for p in problems:
        print(f"  {p}")
    if problems:
        print(f"corpus check FAILED: {len(problems)} problem(s)")
        return 1
    print("corpus check: well-formed and adversarial")
    return 0


ROUTER_PROMPT = """You route user requests to skills. Here is one skill:

name: redis-cache-strategy
description: {desc}

User request: {prompt}

Answer with exactly one word: YES if this skill should be loaded to answer the
request, NO if it should not."""


def ask(runner: list[str], prompt: str, timeout: int) -> bool | None:
    try:
        # Prompt on STDIN, not argv -- `--disallowed-tools` is variadic and
        # would otherwise consume the prompt as a list of tool names.
        r = subprocess.run(runner, input=prompt, capture_output=True, text=True,
                           timeout=timeout, cwd=str(SKILL_DIR.parent))
    except (subprocess.TimeoutExpired, OSError):
        return None
    if r.returncode != 0 or not r.stdout.strip():
        return None
    head = r.stdout.strip().upper()
    if head.startswith("YES"):
        return True
    if head.startswith("NO"):
        return False
    return None  # unparseable is not a vote


def runner_preflight(runner: list[str], timeout: int) -> str:
    """'' when the runner answers a trivial prompt, else why it did not.

    Without this a misconfigured or unauthenticated CLI yields an unparseable
    vote on every prompt and the run reports "not enough scored votes" — true,
    but silent about the actual cause.
    """
    try:
        r = subprocess.run(runner, input="Reply with exactly: OK", capture_output=True,
                           text=True, timeout=min(timeout, 120), cwd=str(SKILL_DIR.parent))
    except (subprocess.TimeoutExpired, OSError) as e:
        return f"{type(e).__name__} invoking {runner[0]}"
    if r.returncode != 0 or not r.stdout.strip():
        return (r.stdout.strip() or r.stderr.strip() or f"exit {r.returncode}")[:300]
    return ""


def run_eval(runner: list[str], timeout: int) -> int:
    why = runner_preflight(runner, timeout)
    if why:
        print(f"INCOMPLETE: the model runner does not answer; routing was NOT measured.\n"
              f"  runner: {' '.join(runner)}\n  reason: {why}", file=sys.stderr)
        return 3
    desc = description()
    tp = fn = fp = tn = 0
    unscored: list[str] = []
    for prompt, want in [(p, True) for p in POSITIVES] + [(n, False) for n in NEGATIVES]:
        got = ask(runner, ROUTER_PROMPT.format(desc=desc, prompt=prompt), timeout)
        if got is None:
            unscored.append(prompt)
            continue
        if want and got:
            tp += 1
        elif want and not got:
            fn += 1
            print(f"  MISS  {prompt!r}")
        elif not want and got:
            fp += 1
            print(f"  GRAB  {prompt!r}")
        else:
            tn += 1

    if not (tp + fn) or not (tp + fp):
        print("INCOMPLETE: not enough scored votes", file=sys.stderr)
        return 3
    recall = tp / (tp + fn)
    precision = tp / (tp + fp)
    print(f"\nrecall {recall:.2f} (floor {RECALL_FLOOR}) · "
          f"precision {precision:.2f} (floor {PRECISION_FLOOR}) · "
          f"{len(unscored)} unscored")
    (SKILL_DIR / "scripts" / "tests" / "trigger_eval_last_run.json").write_text(
        json.dumps({"recall": recall, "precision": precision, "tp": tp, "fn": fn,
                    "fp": fp, "tn": tn, "unscored": unscored}, indent=2),
        encoding="utf-8")
    return 0 if recall >= RECALL_FLOOR and precision >= PRECISION_FLOOR else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="offline corpus check")
    ap.add_argument("--run", action="store_true", help="route the corpus with a model")
    ap.add_argument("--runner", default=DEFAULT_RUNNER)
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args()

    if args.check or not args.run:
        return check_corpus()

    runner = args.runner.split()
    if shutil.which(runner[0]) is None:
        print(f"INCOMPLETE: `{runner[0]}` not found; routing was NOT measured. "
              "This is not a pass.", file=sys.stderr)
        return 3
    return run_eval(runner, args.timeout)


if __name__ == "__main__":
    sys.exit(main())

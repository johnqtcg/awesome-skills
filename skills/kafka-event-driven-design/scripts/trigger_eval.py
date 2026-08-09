#!/usr/bin/env python3
"""Trigger recall/precision for kafka-event-driven-design. OPT-IN — costs money.

WHAT THIS MEASURES, AND WHAT IT DOES NOT
----------------------------------------
The deterministic gates check the *documents*: they prove the prose does not
contain the errors the 26 lint rules encode. None of them touch the model.

This answers exactly one question: given only the frontmatter `description`, does
a judge model decide to invoke this skill on a prompt it should fire on, and stay
quiet on a prompt it should not?

Three limits, stated up front because a number invites over-reading:

1. It is *routing* accuracy, not answer quality. Whether the advice is correct
   once the skill is loaded is `model_eval.py`'s question, not this one.
2. It is a **proxy even for routing**. It measures whether the `description` is
   classifiable by a model reading it in isolation. The host agent's real routing
   sees other skills competing, a longer conversation and its own system prompt;
   a good score here is necessary for that to work and nowhere near sufficient.
3. A model judges a model. Unavoidable for a routing decision — there is no
   deterministic oracle for "should this skill load" — so read the result as a
   smoke test on the description, and treat a *bad* score as far more
   informative than a good one.

Deliberately NOT wired into run_regression.sh: it needs network and the `claude`
CLI, and a gate that cannot run offline turns into a gate everyone skips.

WHY A SKIP IS NOT A PASS
------------------------
A missing CLI, absent credentials, or a network failure exits EXIT_INFRA (2), not
0. A harness that returns success when it could not run is worse than no harness:
it manufactures evidence. Every response must also carry an explicit YES/NO
marker — a nonzero exit code is not a result, and neither is empty output.

Usage:
    python3 trigger_eval.py                 # run the full corpus
    python3 trigger_eval.py --limit 6       # smoke test, 6 prompts
    python3 trigger_eval.py --dry-run       # print the plan, call nothing
    python3 trigger_eval.py --json out.json # machine-readable result
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field

SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent
SKILL_MD = SKILL_DIR / "SKILL.md"

EXIT_OK = 0
EXIT_BELOW_TARGET = 1
EXIT_INFRA = 2

# Targets are deliberately asymmetric. A missed fire costs the user a worse
# answer; a false fire costs them ~32 KB of context and a derailed reply on a
# question this skill has nothing to say about. Precision is the harder promise
# because §1's out-of-scope table is the thing being tested.
TARGET_RECALL = 0.90
TARGET_PRECISION = 0.90


@dataclass(frozen=True)
class Probe:
    prompt: str
    should_fire: bool
    why: str


# In-scope: the skill's own §1 "In scope" list, phrased as a user would ask.
IN_SCOPE = [
    Probe("Our order service publishes to Kafka with sarama. Can you review the producer config?",
          True, "producer client config — the skill's core case"),
    Probe("How should I pick a partition key for events about a single customer?",
          True, "partition key / ordering"),
    Probe("We're seeing duplicate charges from our payment consumer. What's wrong?",
          True, "idempotent consumption / duplicate delivery"),
    Probe("Should I use BACKWARD or FULL compatibility in Schema Registry for this topic?",
          True, "Schema Registry compatibility mode"),
    Probe("Design the topics and schemas for an order fulfilment event flow.",
          True, "greenfield event-driven design"),
    Probe("Add a dead letter queue to our Kafka consumer.",
          True, "DLQ pattern"),
    Probe("Our consumer lag keeps growing even though the pods look healthy.",
          True, "consumer lag troubleshooting"),
    Probe("I want exactly-once processing from Kafka into Postgres. How?",
          True, "EOS semantics at a non-Kafka sink"),
    Probe("Review this Avro event schema before we publish v2.",
          True, "event schema design and evolution"),
    Probe("We just want to publish one event when a user signs up — anything to watch out for?",
          True, "the description's explicit 'just publish an event' case"),
    Probe("How do I stop rebalances from killing throughput every deploy?",
          True, "consumer group rebalance handling"),
    Probe("What's the right commit strategy for at-least-once processing?",
          True, "commit strategy"),
    Probe("Our consumer group is falling behind during traffic spikes — backpressure options?",
          True, "backpressure"),
    Probe("Migrating our consumers to group.protocol=consumer on Kafka 4.0 — what breaks?",
          True, "Kafka 4.x client-visible protocol change"),
    Probe("We need to publish events in the same transaction as a DB write.",
          True, "outbox pattern"),
]

# Out-of-scope. Every entry is a NEAR miss — it mentions Kafka, or messaging, or
# a review request. A corpus of obviously-unrelated prompts ("write me a poem")
# measures nothing: the false-fire risk lives at the boundary §1 draws.
OUT_OF_SCOPE = [
    Probe("How much heap and page cache should I give each Kafka broker?",
          False, "§1: broker sizing is cluster ops"),
    Probe("Walk me through migrating our cluster from ZooKeeper to KRaft.",
          False, "§1: KRaft administration"),
    Probe("Write the kafka-reassign-partitions command to rebalance across new disks.",
          False, "§1: partition reassignment tooling"),
    Probe("Set up MirrorMaker 2 replication between our two regions.",
          False, "§1: cross-cluster replication topology"),
    Probe("How do I write a windowed aggregation in Kafka Streams?",
          False, "§1: Kafka Streams internals"),
    Probe("Configure a Debezium Kafka Connect source connector for MySQL.",
          False, "§1: Kafka Connect internals"),
    Probe("What ACL commands grant this principal write access to the cluster?",
          False, "§1: ACL administration as operator commands"),
    Probe("Design a REST API for our order resource with pagination.",
          False, "§1: redirect to api-design"),
    Probe("Review this Go function for error handling problems.",
          False, "§1: redirect to go-code-reviewer"),
    Probe("Should we use RabbitMQ or SQS for this work queue?",
          False, "not Kafka"),
    Probe("Our Postgres query got slow after adding an index. Why?",
          False, "unrelated to messaging"),
    Probe("Set per-client quotas so one tenant cannot saturate the brokers.",
          False, "§1: quotas are operational"),
    Probe("Write the upgrade runbook for taking our brokers from 3.9 to 4.0.",
          False, "§1: upgrade runbooks"),
    Probe("Tune the JVM GC flags on our Kafka brokers.",
          False, "§1: broker tuning"),
    Probe("How do I add a Redis cache in front of this read path?",
          False, "different skill's territory entirely"),
]

PROBES: list[Probe] = IN_SCOPE + OUT_OF_SCOPE

JUDGE_TEMPLATE = """You are the skill router for an AI coding agent. Below is one \
skill's registry entry. Decide whether this skill should be loaded for the user's \
request.

Skill name: {name}
Skill description: {description}

User request: {prompt}

Answer with exactly one word on the first line: YES if this skill should be \
loaded, NO if it should not. Then one short sentence of justification."""


def read_frontmatter() -> tuple[str, str]:
    """(name, description) from SKILL.md.

    Hand-parsed rather than via PyYAML: this script must run wherever the repo is
    checked out, and an unconditional `import yaml` once broke the whole suite at
    collection time. The description is a `>` folded block, so lines are joined.
    """
    text = SKILL_MD.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise SystemExit("SKILL.md has no frontmatter block")
    block = parts[1]

    name = re.search(r"^name:\s*(\S+)\s*$", block, re.M)
    if not name:
        raise SystemExit("SKILL.md frontmatter has no name field")

    desc = re.search(r"^description:\s*>\s*\n(.*?)(?=^\S|\Z)", block, re.M | re.S)
    if not desc:
        # Fall back to a single-line description.
        flat = re.search(r"^description:\s*(.+)$", block, re.M)
        if not flat:
            raise SystemExit("SKILL.md frontmatter has no description field")
        return name.group(1), flat.group(1).strip()
    folded = " ".join(line.strip() for line in desc.group(1).splitlines() if line.strip())
    return name.group(1), folded


@dataclass
class Verdict:
    probe: Probe
    fired: bool | None          # None = unparseable, counted as an infra error
    raw: str = ""


def ask(prompt: str, name: str, description: str, model: str,
        timeout: int, cwd: str) -> Verdict | str:
    """Returns a Verdict, or an error string on infra failure.

    Isolation flags matter: a nested `claude -p` inherits the parent session's
    permission mode, MCP servers and CLAUDE.md unless told otherwise, and this
    repo's CLAUDE.md talks at length about skills — leaking it into the judge
    would contaminate the very decision being measured. Hence --tools "" (no tool
    calls needed for a routing decision), --strict-mcp-config, and a neutral cwd.
    """
    cmd = [
        "claude", "-p",
        "--tools", "",
        "--permission-mode", "dontAsk",
        "--strict-mcp-config",
        "--model", model,
        JUDGE_TEMPLATE.format(name=name, description=description, prompt=prompt),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout, cwd=cwd)
    except FileNotFoundError:
        return "claude CLI not on PATH"
    except subprocess.TimeoutExpired:
        return f"timed out after {timeout}s"

    out = (proc.stdout or "").strip()
    if proc.returncode != 0 and not out:
        err = (proc.stderr or "").strip().splitlines()
        return f"exit {proc.returncode}: {err[-1] if err else 'no output'}"

    # Require an explicit marker. Treating "no NO found" as YES would let an
    # error message or an empty reply score as a correct fire.
    head = out.upper()[:400]
    yes = re.search(r"\bYES\b", head)
    no = re.search(r"\bNO\b", head)
    if yes and not no:
        return Verdict(Probe(prompt, False, ""), True, out)
    if no and not yes:
        return Verdict(Probe(prompt, False, ""), False, out)
    if yes and no:                      # both present: first one wins
        return Verdict(Probe(prompt, False, ""),
                       yes.start() < no.start(), out)
    return Verdict(Probe(prompt, False, ""), None, out)


@dataclass
class Result:
    tp: int = 0
    fn: int = 0
    fp: int = 0
    tn: int = 0
    misses: list[tuple[Probe, str]] = field(default_factory=list)
    infra: list[tuple[Probe, str]] = field(default_factory=list)

    @property
    def recall(self) -> float | None:
        d = self.tp + self.fn
        return self.tp / d if d else None

    @property
    def precision(self) -> float | None:
        d = self.tp + self.fp
        return self.tp / d if d else None


def run(probes: list[Probe], model: str, timeout: int,
        verbose: bool) -> tuple[Result, str | None]:
    name, description = read_frontmatter()
    res = Result()

    # Neutral cwd so the repo's own CLAUDE.md and .claude/ are out of scope.
    with tempfile.TemporaryDirectory(prefix="kafka-trigger-eval-") as neutral:
        for i, probe in enumerate(probes, 1):
            got = ask(probe.prompt, name, description, model, timeout, neutral)
            if isinstance(got, str):
                # First infra failure aborts: 40 more identical failures is noise,
                # and a partial corpus must not be reported as a measurement.
                return res, f"{got} (probe {i}/{len(probes)})"
            if got.fired is None:
                res.infra.append((probe, got.raw[:120]))
                continue

            if probe.should_fire and got.fired:
                res.tp += 1
            elif probe.should_fire and not got.fired:
                res.fn += 1
                res.misses.append((probe, got.raw[:160]))
            elif not probe.should_fire and got.fired:
                res.fp += 1
                res.misses.append((probe, got.raw[:160]))
            else:
                res.tn += 1

            if verbose:
                mark = "ok " if (got.fired == probe.should_fire) else "MISS"
                print(f"  [{i:2}/{len(probes)}] {mark} "
                      f"want={'fire' if probe.should_fire else 'quiet'} "
                      f"got={'fire' if got.fired else 'quiet'}  {probe.prompt[:64]}")
    return res, None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="claude-haiku-4-5-20251001",
                    help="router decisions are cheap; default is the cheap model")
    ap.add_argument("--limit", type=int, help="run only the first N of each class")
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--json", metavar="PATH", help="write the result as JSON")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the corpus and exit without calling the model")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    probes = PROBES
    if args.limit:
        probes = IN_SCOPE[:args.limit] + OUT_OF_SCOPE[:args.limit]

    if args.dry_run:
        name, description = read_frontmatter()
        print(f"skill: {name}\ndescription: {len(description)} chars\n"
              f"probes: {len(probes)} "
              f"({sum(p.should_fire for p in probes)} should fire, "
              f"{sum(not p.should_fire for p in probes)} should stay quiet)")
        for p in probes:
            print(f"  {'fire ' if p.should_fire else 'quiet'}  {p.prompt}")
        return EXIT_OK

    if shutil.which("claude") is None:
        print("SKIPPED (infra): claude CLI not on PATH — this is NOT a pass",
              file=sys.stderr)
        return EXIT_INFRA

    print(f"trigger eval: {len(probes)} probes, model={args.model}")
    res, infra_error = run(probes, args.model, args.timeout, args.verbose)

    if infra_error:
        print(f"SKIPPED (infra): {infra_error} — this is NOT a pass", file=sys.stderr)
        return EXIT_INFRA
    if res.infra:
        print(f"SKIPPED (infra): {len(res.infra)} response(s) had no YES/NO marker "
              f"— this is NOT a pass", file=sys.stderr)
        for probe, raw in res.infra:
            print(f"    {probe.prompt[:60]!r} -> {raw!r}", file=sys.stderr)
        return EXIT_INFRA

    recall, precision = res.recall, res.precision
    print(f"\nconfusion: tp={res.tp} fn={res.fn} fp={res.fp} tn={res.tn}")
    print(f"recall    = {recall:.3f} (target ≥ {TARGET_RECALL})"
          if recall is not None else "recall    = n/a")
    print(f"precision = {precision:.3f} (target ≥ {TARGET_PRECISION})"
          if precision is not None else "precision = n/a")

    for probe, raw in res.misses:
        kind = "MISSED FIRE" if probe.should_fire else "FALSE FIRE "
        print(f"{kind} {probe.prompt}\n    expected because: {probe.why}"
              f"\n    model said: {raw}")

    if args.json:
        pathlib.Path(args.json).write_text(json.dumps({
            "model": args.model,
            "probes": len(probes),
            "tp": res.tp, "fn": res.fn, "fp": res.fp, "tn": res.tn,
            "recall": recall, "precision": precision,
            "target_recall": TARGET_RECALL, "target_precision": TARGET_PRECISION,
            "misses": [{"prompt": p.prompt, "should_fire": p.should_fire,
                        "why": p.why, "response": r} for p, r in res.misses],
        }, indent=2) + "\n", encoding="utf-8")

    below = [n for n, v, t in (("recall", recall, TARGET_RECALL),
                               ("precision", precision, TARGET_PRECISION))
             if v is None or v < t]
    if below:
        print(f"\nBELOW TARGET: {', '.join(below)}")
        return EXIT_BELOW_TARGET
    print("\ntrigger eval: recall and precision both at or above target")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

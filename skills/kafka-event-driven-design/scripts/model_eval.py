#!/usr/bin/env python3
"""Does a model *apply* this skill correctly? A/B eval with a deterministic grader.

WHY THIS EXISTS SEPARATELY FROM trigger_eval.py
-----------------------------------------------
`trigger_eval.py` asks a router "should this skill load?" — routing accuracy, and
a proxy at that: it measures whether the frontmatter `description` is
classifiable, not whether the host agent actually fires. Nothing about the answer
the user finally gets.

This asks the question that matters: given a real Kafka snippet, does a model
carrying this skill produce the findings the skill demands, does it stay off the
claims the skill declares wrong, and does it leave correct code alone? Two arms
over the same fixtures:

    arm A  the prompt alone
    arm B  the prompt + SKILL.md + the references §3 says to load (--refs)

Arm B injects `version-client-matrix.md` by default because §3 loads it for ANY
producer/consumer config verdict, even at Lite depth. A run that ships only
SKILL.md measures a workflow the skill does not prescribe; `--refs none` and
`--refs all` bracket it.

The corpus is **defect + good_practice**, not defects alone. A defects-only score
rewards a model that condemns everything, which measures pessimism rather than
judgement.

THE GRADER IS NOT A MODEL
-------------------------
No LLM judges the output. A model grading a model shares the blind spots and
turns a measurement into a correlated guess. Grading here is three mechanical
passes over the response text:

* **Recall** — how many of the fixture's `coverage_rules` (the concepts a correct
  review must name) appear. Declared per fixture, alongside the expected answer.
* **Known-wrong claims** — `lint_kafka_docs.py` run over the response. A KL rule
  firing on a model's own prose means it asserted something the skill declares
  false; that is a defect regardless of how much it also got right.
* **False alarms** — per-fixture markers for the over-flag each good_practice
  case invites ("no explicit acks, therefore data loss" on kafka-clients ≥3.0).
  Recall is blind to this: condemning correct code names all the right concepts.

All three are auditable and reproducible. None needs network.

WHAT THIS STILL CANNOT TELL YOU
-------------------------------
The oracle is endogenous. `expected_feedback`, `coverage_rules` and the linter
rules were all written by the same effort that wrote the skill, so a high score
means "the model reproduces what this project believes", not "the model is
right". Calibration proves the grader separates good from bad *within that
belief system*; it is not a substitute for a blinded, externally-sourced oracle,
and that gap stays open until one exists.

WHY THE ABSOLUTE SCORE GATES, NOT THE DELTA
-------------------------------------------
A delta-only gate passes when both arms are broken by the same amount. Arm B must
clear `TARGET_SKILLED_RECALL` on its own; the delta is reported for interest, and
a negative delta fails regardless — the skill actively hurting is worse than the
skill not helping.

CALIBRATION — the part that runs offline, every time
----------------------------------------------------
A grader nobody has graded is not evidence. `--calibrate` needs no model, no
network and no credentials: it scores each fixture's own `expected_feedback`
(a known-good review) and a hand-written decoy (a plausible, wrong review) and
requires the grader to separate them **per fixture**, not on average. If the
grader cannot tell a correct review from a confident wrong one, the A/B numbers
it would produce are meaningless — so this is a regression gate and the A/B run
is not.

Usage:
    python3 model_eval.py --calibrate            # offline; runs in CI
    python3 model_eval.py --dry-run              # print the plan, call nothing
    python3 model_eval.py                        # OPT-IN A/B run; costs money
    python3 model_eval.py --runner 'my-llm -p'   # any CLI reading a prompt on argv
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field

SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent
SKILL_MD = SKILL_DIR / "SKILL.md"
GOLDEN_DIR = SKILL_DIR / "scripts" / "tests" / "golden"

EXIT_OK = 0
EXIT_BELOW_TARGET = 1
EXIT_INFRA = 2

# Arm B must clear this on its own. Chosen as "names most of the concepts a
# correct review names" — not 1.0, because `coverage_rules` include exact config
# keys a correct review may legitimately paraphrase.
TARGET_SKILLED_RECALL = 0.70
# Any known-wrong claim in the output is a hard fail regardless of recall.
TARGET_MAX_WRONG_CLAIMS = 0


def _load_linter():
    path = SKILL_DIR / "scripts" / "lint_kafka_docs.py"
    spec = importlib.util.spec_from_file_location("lint_kafka_docs", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["lint_kafka_docs"] = module
    spec.loader.exec_module(module)
    return module


LINTER = _load_linter()


def fixtures() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(GOLDEN_DIR.glob("*.json"))]


# --------------------------------------------------------------------------
# Grading
# --------------------------------------------------------------------------

# A model that condemns correct code is as useless as one that misses defects,
# and recall cannot see it: on a good_practice fixture, "acks is missing and this
# will lose data" names every required concept while being exactly wrong. These
# are the phrasings of the specific over-flag each good_practice fixture invites,
# written as regexes and checked only on that fixture.
FALSE_ALARM: dict[str, list[str]] = {
    # kafka-clients >=3.0: no explicit acks/idempotence lines, and safe anyway.
    "KAFKA-017": [
        r"\backs\b[^.;\n]{0,60}?(?:missing|absent|not set|unset|omitted)"
        r"[^.;\n]{0,60}?(?:defect|bug|unsafe|risk|data loss|critical|must be set)",
        r"(?:missing|absent|no explicit|not set)[^.;\n]{0,40}?"
        r"(?:acks|idempotence)[^.;\n]{0,60}?(?:data loss|unsafe|critical|defect)",
        r"(?:add|set)\s+`?acks\s*=\s*all`?[^.;\n]{0,40}?"
        r"(?:otherwise|or you will|to avoid)[^.;\n]{0,40}?(?:lose|loss)",
    ],
    # A correct outbox. The invited error is calling it broken for not being EOS.
    "KAFKA-008": [
        r"outbox[^.;\n]{0,80}?(?:is\s+)?(?:broken|incorrect|wrong|unsafe|a defect)",
        r"(?:replace|swap)[^.;\n]{0,40}?outbox[^.;\n]{0,40}?"
        r"(?:with|for)[^.;\n]{0,40}?kafka transaction",
    ],
    # A well-formed design. The invited error is inventing a Critical finding.
    "KAFKA-007": [
        r"critical[^.;\n]{0,30}?(?:defect|failure|issue|problem)[^.;\n]{0,40}?"
        r"(?:acks|idempoten|dlq|schema registry)",
    ],
}


@dataclass
class Score:
    fixture_id: str
    hit: list[str] = field(default_factory=list)
    missed: list[str] = field(default_factory=list)
    wrong_claims: list[str] = field(default_factory=list)
    false_alarms: list[str] = field(default_factory=list)

    @property
    def recall(self) -> float:
        total = len(self.hit) + len(self.missed)
        return len(self.hit) / total if total else 0.0

    @property
    def clean(self) -> bool:
        return (len(self.wrong_claims) <= TARGET_MAX_WRONG_CLAIMS
                and not self.false_alarms)


def _mentions(response: str, concept: str) -> bool:
    """Whether the response names `concept`.

    Case-insensitive, and punctuation in a config key is matched literally so
    `group.protocol` cannot be satisfied by the words "group" and "protocol"
    landing in unrelated sentences. Word boundaries are applied only where the
    concept starts/ends alphanumeric — `read_committed` must not require a
    boundary after `d` inside `read_committed=true`.

    A trailing plural is tolerated: "Uncovered Risks" and "Uncovered Risk" are
    the same concept, and a grader that scores one and not the other measures
    the reviewer's number agreement rather than their coverage.
    """
    pattern = re.escape(concept)
    if concept[:1].isalnum():
        pattern = r"\b" + pattern
    if concept[-1:].isalpha():
        pattern = pattern + r"(?:e?s)?\b"
    elif concept[-1:].isalnum():
        pattern = pattern + r"\b"
    return re.search(pattern, response, re.I) is not None


def grade(response: str, fixture: dict) -> Score:
    """Deterministic. Same function grades both arms and the calibration set."""
    score = Score(fixture_id=fixture["id"])
    for concept in fixture["coverage_rules"]:
        (score.hit if _mentions(response, concept) else score.missed).append(concept)
    # The linter's scoped rules key on the filename; SKILL.md enables all of them.
    score.wrong_claims = sorted({f.rule for f in LINTER.scan_text(response, "SKILL.md")})
    score.false_alarms = [p for p in FALSE_ALARM.get(fixture["id"], [])
                          if re.search(p, response, re.I)]
    return score


# --------------------------------------------------------------------------
# Calibration — offline, no model
# --------------------------------------------------------------------------

# A confident, plausible, WRONG review for each fixture. Hand-written, and
# deliberately fluent: a grader that only rejects gibberish proves nothing. Each
# either misses the concepts a correct review must name, or asserts something the
# linter knows is false, or both.
DECOYS: dict[str, str] = {
    "KAFKA-001": "The producer setup looks standard. sarama's NewConfig() already "
                 "waits for all replicas, so no changes are needed here.",
    "KAFKA-002": "The insert is straightforward and the code reads cleanly. "
                 "Consider extracting the handler into its own function.",
    "KAFKA-003": "Processing failures will retry automatically, so the consumer "
                 "will recover on its own. No further handling required.",
    "KAFKA-004": "Records with no key are spread round-robin across the "
                 "partitions, which gives you even load. This is fine.",
    "KAFKA-005": "The payload carries the fields the business needs. Adding more "
                 "metadata would only increase the message size.",
    "KAFKA-006": "Set the subject to BACKWARD so old consumers can still read "
                 "newly produced records, then deploy the producers first.",
    "KAFKA-007": "Nothing stands out; the configuration is unremarkable.",
    "KAFKA-008": "Wrap the row insert and the produce call in a Kafka transaction "
                 "so they commit together.",
    "KAFKA-009": "The design is correct. Partition keys, retention and delivery "
                 "guarantees all look appropriate for this workload.",
    "KAFKA-010": "Create one topic and one consumer group, then iterate. The "
                 "details can be settled during implementation.",
    "KAFKA-011": "Alert whenever lag exceeds 10000 messages and you will catch "
                 "any processing delay.",
    "KAFKA-012": "The transactional loop is correct as written. Modern clients "
                 "accept the group id directly.",
    "KAFKA-013": "The DLQ path is present, so poison messages are handled. The "
                 "offset advance afterwards is the expected pattern.",
    "KAFKA-014": "Keep the assignor configuration as-is; it is compatible with "
                 "every protocol version.",
    "KAFKA-015": "Kafka transactions cover both writes, so the state stays "
                 "consistent across the database and the topic.",
    "KAFKA-016": "A TTL cache keyed on the event id is a sound deduplication "
                 "mechanism and avoids a database round trip.",
    "KAFKA-017": "No explicit durability settings are present, so this producer "
                 "is unsafe and will lose records.",
    "KAFKA-018": "Retention can stay unlimited; storage is cheap and replay is "
                 "useful. Nothing here needs restricting.",
    "KAFKA-019": "Use cleanup.policy=compact for the event-sourced aggregate log "
                 "so the topic does not grow without bound.",
    "KAFKA-020": "Page when consumer lag reaches ten thousand records; that is "
                 "the usual threshold for a healthy consumer group.",
    "KAFKA-021": "Static membership guarantees rolling deployments will not "
                 "rebalance the group, so no further tuning is needed.",
}

# The separation the grader must achieve on every fixture.
CALIBRATION_MARGIN = 0.30

# The decoys above are all separable on recall alone, which left the *other* half
# of the grader — the linter penalty — untested by the gate that claims to grade
# the grader: deleting `score.wrong_claims = ...` entirely kept calibration green.
# These probes exist to close that. Each names every concept its fixture demands,
# so recall is 1.0 and only the penalty can fail it. Deleting the penalty makes
# this gate go red, which is the property being asserted.
PENALTY_PROBES: list[tuple[str, str, str]] = [
    ("KAFKA-011", "KL024",
     "Add consumer lag monitoring with an alert. "
     "Page when consumer lag reaches ten thousand records."),
    ("KAFKA-004", "KL006",
     "Set a partition key to preserve ordering — without one, records are "
     "spread round-robin over the partitions."),
    ("KAFKA-008", "KL010",
     "Use the outbox pattern to keep the write atomic: wrap the row insert and "
     "the produce call in one Kafka transaction, giving at-least-once."),
]

# The false-alarm arm's own calibration: a fluent review that condemns correct
# code. Recall cannot separate these from a correct review — they name the same
# concepts — so only FALSE_ALARM can fail them. Deleting that check makes this
# gate go red, which is the property being asserted.
OVERFLAG_PROBES: dict[str, str] = {
    "KAFKA-017": "This kafka-clients producer sets no explicit acks, and the "
                 "missing acks setting is a critical data loss defect. Also "
                 "check min.insync.replicas — without 3.0 defaults you are "
                 "exposed.",
    "KAFKA-008": "The outbox pattern here is broken: the transaction and the "
                 "atomic write do not line up, so this is at-least-once at best.",
    "KAFKA-007": "There is a critical defect in the acks handling; the "
                 "idempotent consumer, DLQ, Schema Registry, partition key and "
                 "consumer lag setup are otherwise fine.",
}


def calibrate(verbose: bool) -> int:
    """Grade the grader. No network, no model, no credentials."""
    failures: list[str] = []
    checked = 0
    for fix in fixtures():
        fid = fix["id"]
        if fid not in DECOYS:
            failures.append(f"{fid}: no decoy — every fixture needs one, or the "
                            f"grader is only calibrated on the easy half")
            continue
        good = grade(fix["expected_feedback"], fix)
        bad = grade(DECOYS[fid], fix)
        checked += 1

        if good.recall < TARGET_SKILLED_RECALL:
            failures.append(
                f"{fid}: the fixture's own expected_feedback scores "
                f"{good.recall:.2f} < {TARGET_SKILLED_RECALL}. Either the "
                f"coverage_rules ask for words the model answer never uses, or "
                f"the expected answer is incomplete. Missed: {good.missed}")
        if not good.clean:
            failures.append(
                f"{fid}: expected_feedback trips the linter ({good.wrong_claims}). "
                f"A shipped exemplar must pass its own grader")
        if good.recall - bad.recall < CALIBRATION_MARGIN and bad.clean:
            failures.append(
                f"{fid}: grader cannot separate the correct review "
                f"({good.recall:.2f}) from the decoy ({bad.recall:.2f}, "
                f"lint {bad.wrong_claims or 'clean'}); margin < {CALIBRATION_MARGIN}")

        if verbose:
            print(f"  {fid}  good={good.recall:.2f} bad={bad.recall:.2f} "
                  f"decoy-lint={','.join(bad.wrong_claims) or '-'}")

    by_id = {f["id"]: f for f in fixtures()}

    # The false-alarm half. Every good_practice fixture must (a) declare markers,
    # (b) have its own expected_feedback trip none of them, and (c) have an
    # over-flagging probe that trips at least one. Without (c) the markers could
    # be dead regexes and nothing would notice.
    for fix in fixtures():
        if fix["type"] != "good_practice":
            continue
        fid = fix["id"]
        checked += 1
        if fid not in FALSE_ALARM:
            failures.append(
                f"{fid} is a good_practice fixture with no FALSE_ALARM markers — "
                f"the over-flagging failure mode is unmeasured for it")
            continue
        good = grade(fix["expected_feedback"], fix)
        if good.false_alarms:
            failures.append(
                f"{fid}: the correct review trips its own false-alarm markers "
                f"{good.false_alarms} — the markers are too broad")
        probe = OVERFLAG_PROBES.get(fid)
        if probe is None:
            failures.append(f"{fid}: no OVERFLAG probe, so its markers are untested")
        else:
            s = grade(probe, fix)
            if not s.false_alarms:
                failures.append(
                    f"{fid}: an over-flagging review passed the false-alarm check "
                    f"— condemning correct code is not being detected")
            elif verbose:
                print(f"  {fid}  over-flag caught ({len(s.false_alarms)} marker(s))")

    # The penalty half. Without these the gate passes with the linter check
    # deleted, and "the grader is calibrated" would cover only its recall arm.
    for fid, expect_rule, response in PENALTY_PROBES:
        fix = by_id.get(fid)
        if fix is None:
            failures.append(f"penalty probe names unknown fixture {fid}")
            continue
        s = grade(response, fix)
        checked += 1
        if s.recall < 1.0:
            failures.append(
                f"{fid} penalty probe: recall {s.recall:.2f} < 1.0 "
                f"(missed {s.missed}) — it must isolate the penalty, so any "
                f"failure has to come from the linter arm alone")
        if s.clean:
            failures.append(
                f"{fid} penalty probe: a response asserting a known-wrong claim "
                f"scored clean at full recall — the linter penalty is not wired in")
        elif expect_rule not in s.wrong_claims:
            failures.append(
                f"{fid} penalty probe: expected {expect_rule}, "
                f"got {s.wrong_claims} — the probe is being caught by the wrong rule")
        elif verbose:
            print(f"  {fid}  penalty probe recall=1.00 caught={expect_rule}")

    print(f"\ncalibration: {checked} check(s), "
          f"{len(failures)} problem(s)")
    for f in failures:
        print(f"  FAIL {f}")
    if checked == 0:
        print("  FAIL no fixtures graded — the calibration set is empty")
        return EXIT_BELOW_TARGET
    return EXIT_OK if not failures else EXIT_BELOW_TARGET


# --------------------------------------------------------------------------
# A/B run — opt-in, needs a model
# --------------------------------------------------------------------------

PROMPT = """Review the following Kafka client code and report every design or \
safety problem you find. Be specific about the mechanism and the fix.

Context: {context}

```{lang}
{snippet}
```"""

SKILLED_PREFIX = """You have been given the following skill. Apply it.

<skill>
{skill}
</skill>
{refs}
"""

REF_BLOCK = """
<skill-references>
{bodies}
</skill-references>
"""

# SKILL.md alone is not what the skill asks an agent to have in context. §3 says
# `version-client-matrix.md` loads for ANY producer/consumer config verdict, even
# at Lite depth — so a run that injects only SKILL.md is measuring a workflow the
# skill does not prescribe, and will under-report on every version-sensitive item.
# `matrix` is therefore the default; `none` and `all` bracket it.
REF_SETS = {
    "none": [],
    "matrix": ["version-client-matrix.md"],
    "all": ["version-client-matrix.md", "event-schema-patterns.md",
            "consumer-failure-modes.md", "consumer-anti-examples.md"],
}


def build_prompt(fix: dict, with_skill: bool, refs: str = "matrix") -> str:
    body = PROMPT.format(
        context=", ".join(f"{k}={v}" for k, v in fix.get("context", {}).items()) or "not stated",
        lang=fix.get("snippet_lang", ""),
        snippet=fix["code_snippet"],
    )
    if not with_skill:
        return body
    names = REF_SETS[refs]
    loaded = REF_BLOCK.format(bodies="\n\n".join(
        f"=== references/{n} ===\n" + (SKILL_DIR / "references" / n).read_text(encoding="utf-8")
        for n in names)) if names else ""
    return SKILLED_PREFIX.format(
        skill=SKILL_MD.read_text(encoding="utf-8"), refs=loaded) + body


def ask(runner: list[str], prompt: str, timeout: int, cwd: str) -> str | None:
    """Response text, or None on infra failure.

    A nested `claude -p` inherits the parent session's permission mode, MCP
    servers and CLAUDE.md unless told otherwise, and this repo's CLAUDE.md talks
    at length about skills — leaking it would contaminate the arm-A baseline,
    which is the whole comparison. Hence the isolation flags in the default
    runner and a neutral cwd.
    """
    try:
        proc = subprocess.run([*runner, prompt], capture_output=True, text=True,
                              timeout=timeout, cwd=cwd)
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return None
    # A nonzero exit is infra, full stop — even with text on stdout. A CLI that
    # prints a partial answer, a usage banner or "Not logged in" and then exits 1
    # is not a review, and grading whatever it emitted turns a broken run into a
    # low score. Low scores get investigated as model behaviour; they must not be
    # manufacturable by a failing subprocess.
    if proc.returncode != 0:
        return None
    out = (proc.stdout or "").strip()
    # An empty answer is likewise infra, not a zero-recall review: scoring it
    # zeroes both arms and reads as "the skill makes no difference".
    if not out:
        return None
    return out


def eval_corpus(limit: int | None = None) -> list[dict]:
    """Defect fixtures measure recall; good_practice fixtures measure the false
    alarm rate. A corpus of defects alone rewards a model that condemns
    everything — the score would be a measure of pessimism, not of judgement."""
    corpus = [f for f in fixtures() if f["type"] in ("defect", "good_practice")]
    return corpus[:limit] if limit else corpus


def run_ab(runner: list[str], timeout: int, limit: int | None, refs: str,
           verbose: bool) -> tuple[dict[str, list[Score]], list[dict], str | None]:
    arms: dict[str, list[Score]] = {"baseline": [], "skilled": []}
    transcripts: list[dict] = []
    corpus = eval_corpus(limit)

    with tempfile.TemporaryDirectory(prefix="kafka-model-eval-") as neutral:
        for i, fix in enumerate(corpus, 1):
            for arm, with_skill in (("baseline", False), ("skilled", True)):
                out = ask(runner, build_prompt(fix, with_skill, refs), timeout, neutral)
                if out is None:
                    return arms, transcripts, (
                        f"{arm} arm produced no output for "
                        f"{fix['id']} ({i}/{len(corpus)})")
                s = grade(out, fix)
                arms[arm].append(s)
                # Kept verbatim. A score with no response behind it cannot be
                # re-graded when the grader changes, and cannot be argued with.
                transcripts.append({"id": fix["id"], "type": fix["type"],
                                    "arm": arm, "response": out})
                if verbose:
                    print(f"  [{i:2}/{len(corpus)}] {fix['id']} {arm:8} "
                          f"recall={s.recall:.2f} "
                          f"wrong={','.join(s.wrong_claims) or '-'} "
                          f"false_alarm={len(s.false_alarms)}")
    return arms, transcripts, None


def _mean(scores: list[Score]) -> float:
    return sum(s.recall for s in scores) / len(scores) if scores else 0.0


def _mean_over(scores: list[Score], ids: set[str]) -> float:
    picked = [s for s in scores if s.fixture_id in ids]
    return sum(s.recall for s in picked) / len(picked) if picked else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--calibrate", action="store_true",
                    help="offline: prove the grader separates correct reviews "
                         "from confident wrong ones")
    ap.add_argument("--runner", default=None,
                    help="command that takes a prompt as its last argv and "
                         "prints the response (default: an isolated `claude -p`)")
    ap.add_argument("--model", default="claude-sonnet-5")
    ap.add_argument("--limit", type=int, help="first N fixtures only")
    ap.add_argument("--refs", choices=sorted(REF_SETS), default="matrix",
                    help="which reference files ride along in the skilled arm. "
                         "SKILL.md §3 loads version-client-matrix.md for ANY "
                         "config verdict, so 'matrix' is the workflow the skill "
                         "actually prescribes; 'none' under-reports, 'all' is "
                         "the ceiling (default: matrix)")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--json", metavar="PATH")
    ap.add_argument("--no-transcripts", action="store_true",
                    help="omit raw responses from --json (they are kept by "
                         "default: a score with no response behind it cannot be "
                         "re-graded or argued with)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if args.calibrate:
        return calibrate(args.verbose)

    runner = shlex.split(args.runner) if args.runner else [
        "claude", "-p", "--tools", "", "--permission-mode", "dontAsk",
        "--strict-mcp-config", "--model", args.model,
    ]

    corpus = eval_corpus(args.limit)
    defects = {f["id"] for f in corpus if f["type"] == "defect"}
    good = {f["id"] for f in corpus if f["type"] == "good_practice"}

    if args.dry_run:
        print(f"runner: {' '.join(runner)}\n"
              f"fixtures: {len(corpus)} ({len(defects)} defect, {len(good)} "
              f"good-practice) × 2 arms = {len(corpus) * 2} calls\n"
              f"skilled arm: SKILL.md + refs={args.refs} "
              f"({', '.join(REF_SETS[args.refs]) or 'none'})\n"
              f"grader: deterministic (concept recall + linter penalty + "
              f"false-alarm markers), no model\n"
              f"gate: skilled recall ≥ {TARGET_SKILLED_RECALL}, wrong claims ≤ "
              f"{TARGET_MAX_WRONG_CLAIMS}, false alarms = 0, delta ≥ 0")
        for f in corpus:
            print(f"  {f['id']}  {f['type']:14} {f['coverage_rules']}")
        return EXIT_OK

    if shutil.which(runner[0]) is None:
        print(f"SKIPPED (infra): {runner[0]} not on PATH — this is NOT a pass",
              file=sys.stderr)
        return EXIT_INFRA

    arms, transcripts, infra = run_ab(runner, args.timeout, args.limit,
                                      args.refs, args.verbose)
    if infra:
        print(f"SKIPPED (infra): {infra} — this is NOT a pass", file=sys.stderr)
        return EXIT_INFRA

    base, skilled = _mean(arms["baseline"]), _mean(arms["skilled"])
    base_d, skilled_d = (_mean_over(arms["baseline"], defects),
                         _mean_over(arms["skilled"], defects))
    wrong = sum(len(s.wrong_claims) for s in arms["skilled"])
    alarms = sum(len(s.false_alarms) for s in arms["skilled"]
                 if s.fixture_id in good)
    base_alarms = sum(len(s.false_alarms) for s in arms["baseline"]
                      if s.fixture_id in good)

    print(f"\nrecall, all fixtures    baseline {base:.3f} → skilled {skilled:.3f} "
          f"({skilled - base:+.3f}; target ≥ {TARGET_SKILLED_RECALL})")
    print(f"recall, defects only    baseline {base_d:.3f} → skilled {skilled_d:.3f} "
          f"({skilled_d - base_d:+.3f})")
    print(f"known-wrong claims (skilled arm)  {wrong} "
          f"(target ≤ {TARGET_MAX_WRONG_CLAIMS})")
    print(f"false alarms on correct code      baseline {base_alarms} → "
          f"skilled {alarms} (target 0)")

    if args.json:
        payload = {
            "runner": runner, "refs": args.refs,
            "fixtures": len(corpus), "defects": len(defects),
            "good_practice": len(good),
            "baseline_recall": base, "skilled_recall": skilled,
            "baseline_recall_defects": base_d, "skilled_recall_defects": skilled_d,
            "delta": skilled - base, "wrong_claims": wrong,
            "false_alarms": alarms, "baseline_false_alarms": base_alarms,
            "target_skilled_recall": TARGET_SKILLED_RECALL,
            "per_fixture": {arm: [{"id": s.fixture_id, "recall": s.recall,
                                   "missed": s.missed,
                                   "wrong_claims": s.wrong_claims,
                                   "false_alarms": s.false_alarms}
                                  for s in scores]
                            for arm, scores in arms.items()},
        }
        if not args.no_transcripts:
            payload["transcripts"] = transcripts
        pathlib.Path(args.json).write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    failures = []
    if skilled < TARGET_SKILLED_RECALL:
        failures.append(f"skilled recall {skilled:.3f} < {TARGET_SKILLED_RECALL}")
    if wrong > TARGET_MAX_WRONG_CLAIMS:
        failures.append(f"{wrong} known-wrong claim(s) in the skilled arm")
    if alarms:
        failures.append(f"{alarms} false alarm(s) on correct code")
    if skilled < base:
        failures.append(f"the skill made it worse ({skilled:.3f} < {base:.3f})")
    if failures:
        print("\nBELOW TARGET: " + "; ".join(failures))
        return EXIT_BELOW_TARGET
    print("\nmodel eval: skilled arm at or above target")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

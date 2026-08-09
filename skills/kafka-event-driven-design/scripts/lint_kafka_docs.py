#!/usr/bin/env python3
"""Semantic linter for kafka-event-driven-design documentation.

The point of this linter is to fail when a *claim* is wrong, not when a section
is missing. Keyword-presence tests pass happily on inverted advice — a doc saying
"never use acks=all, prefer acks=1" contains both "acks=all" and "acks", so any
substring assertion is satisfied. Every rule here is written so that flipping the
underlying claim in the prose makes the rule fire.

Design constraints learned the hard way:

* Rules match on **structure**, not on one memorable phrase. A rule guarded on a
  single sentence dies silently the moment that sentence is reworded, and the
  selftest keeps passing because the selftest feeds it the phrase.
* Anti-examples are masked before scanning. Docs deliberately quote the wrong
  claim in order to correct it; a naive scan reports those as findings. Masking
  substitutes NUL bytes so offsets and line numbers are preserved (blanking to
  "" fuses neighbouring lines and fabricates matches).
* Each rule declares its own positive and negative selftest cases, so
  ``--selftest`` proves the rule can both fire and stay quiet.

WHAT THIS IS: A KNOWN-REGRESSION DETECTOR
-----------------------------------------
It is not a semantic checker, and a clean run is not a semantic clearance. These
are regexes over English. Each rule encodes the phrasings of one wrong claim that
somebody has actually written down; a restatement nobody has written yet passes,
by construction, and every review round so far has found more of them — four in
the round that added ``LAGNUM`` and the KL023 "belongs on" alternative, all of
which had walked through a fully green selftest, mutation sweep and doc scan.

So read the two verdicts asymmetrically:

* **A finding is real.** The rules are tuned for precision, the corpus in
  ``paraphrase_corpus.py`` keeps a correct-claim probe beside every wrong-claim
  probe, and the shipped docs are expected to stay at zero findings.
* **Silence means "none of the known-wrong phrasings are present".** It does not
  mean the claim is right, and 0 findings must never be reported as evidence that
  the documentation is semantically correct.

Coverage grows by adding paraphrases, not by trusting the regex to generalise.
Whether a *model* applies these claims correctly is a different question again,
and belongs to ``model_eval.py``.

Usage:
    python3 lint_kafka_docs.py [paths...]   # scan (default: SKILL.md + references/)
    python3 lint_kafka_docs.py --selftest   # prove every rule fires and stays quiet
    python3 lint_kafka_docs.py --list       # print the rule inventory
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
from dataclasses import dataclass, field

SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent

# Spans that quote a wrong claim on purpose. Text inside these is masked out
# before rules run. Keyed by (start marker, end marker) as regexes.
MASK_PATTERNS = [
    # Fenced blocks whose first ~3 lines announce they are the wrong version.
    re.compile(
        r"```[a-z]*\n(?P<body>(?:[^\n]*\n){0,3}?[^\n]*"
        r"(?:WRONG|SUSPECT|NOT SAFE|Wrong —|// Wrong)[^\n]*\n.*?)```",
        re.DOTALL,
    ),
]

# A correct doc must be able to *name* a myth in order to reject it. Rather than
# maintaining a phrase list of every correction sentence (which rots the instant
# the prose is reworded), suppression is structural: a match is ignored when the
# sentence containing it also carries a refutation operator.
#
# These markers are deliberately narrow. A bare "not"/"never" is NOT a marker —
# "never use acks=all; prefer acks=1" is itself a defect sentence containing
# "never", and suppressing on it would disarm KL001. The selftest guards this:
# every rule must still fire on its should_fire cases after suppression runs.
REFUTATION_MARKERS = re.compile(
    r"≠"
    r"|\bis wrong\b|\bare wrong\b|\bwas wrong\b"
    r"|\bis not\b|\bis no longer\b|\bno client\b|\bnone of them\b"
    r"|\bmyth\b|\bfolklore\b|\binversion\b|\bfabricat|\binvented\b"
    r"|\bKafka cannot\b|\bcannot include\b"
    r"|\bWRONG\b|\bSUSPECT\b|\bNOT SAFE\b"
    r"|\bis the defect\b|\bthe defect is\b"
    r"|\bdo not describe\b|\bnever present\b|\bnever be scored\b"
    r"|\bnot a substitute\b|\bnot an automatic defect\b",
    re.IGNORECASE,
)

# How far outside the matched span a refutation may sit and still be read as
# negating THAT claim. The clause-break cut below does the real work, so these
# only need to be generous enough to reach a refutation in the SAME clause
# ("…, you have described something Kafka cannot do" trails the claim by ~60).
REFUTE_BEFORE = 60
REFUTE_AFTER = 100

# A refutation on the far side of one of these is negating a DIFFERENT
# proposition. Without this check, "acks=all is wrong; prefer acks=1" suppressed
# itself: the marker belonged to the clause before the semicolon, and the
# defective advice after it rode along for free.
# A colon and a list-item marker also start a new proposition: a bullet saying
# "must not delete existing fields" was silenced by the word "folklore" in the
# lead-in line above it (mutation M05).
CLAUSE_BREAK = re.compile(
    r"[;.!?:]|\s—\s|\s--\s|\bbut\b|\bhowever\b|\binstead\b"
    r"|\n\s*(?:[-*+]|\d+\.)\s|\n\s*\|",
    re.IGNORECASE,
)

# Fenced code blocks, used by "block" rules that need same-block co-occurrence.
FENCE = re.compile(r"```[a-z]*\n(?P<body>.*?)```", re.DOTALL)


def mask(text: str) -> str:
    """Replace anti-example spans with NUL, preserving offsets and line numbers.

    NUL rather than deletion: blanking to "" fuses neighbouring lines together
    and fabricates matches that span the seam.
    """
    out = list(text)
    for pat in MASK_PATTERNS:
        for m in pat.finditer(text):
            for i in range(m.start("body"), m.end("body")):
                if out[i] != "\n":
                    out[i] = "\x00"
    return "".join(out)


def _normalise(span: str) -> str:
    """Drop markdown emphasis and collapse whitespace so markers survive line
    wrapping and **bold**."""
    return re.sub(r"\s+", " ", span.replace("*", "").replace("`", ""))


def _refutation_probe(text: str, start: int, end: int) -> str:
    """The region in which a refutation can be read as negating THIS claim.

    Scope = the matched span itself, plus a short run of adjacent text on each
    side, cut at the first clause boundary. Sentence-wide scoping is wrong: it
    lets a refutation of the opposite proposition silence a defective claim
    sitting in the next clause, which is precisely how

        "acks=all is wrong; prefer acks=1 for critical events"
        "Every consumer must have a DLQ; having no DLQ is wrong"

    both scored zero findings. The marker has to be attached to the claim, not
    merely nearby.
    """
    left = text[max(0, start - REFUTE_BEFORE):start]
    breaks = list(CLAUSE_BREAK.finditer(left))
    if breaks:
        left = left[breaks[-1].end():]

    right = text[end:min(len(text), end + REFUTE_AFTER)]
    brk = CLAUSE_BREAK.search(right)
    if brk:
        right = right[:brk.start()]

    return _normalise(left + text[start:end] + right)


def _refuted(text: str, start: int, end: int) -> bool:
    return bool(REFUTATION_MARKERS.search(_refutation_probe(text, start, end)))


@dataclass
class Finding:
    rule: str
    path: str
    line: int
    message: str
    excerpt: str


@dataclass
class Rule:
    """A semantic rule.

    ``forbid`` fires when the pattern is found in masked text (an asserted wrong
    claim). ``require`` fires when ``trigger`` appears but ``expect`` does not
    (a claim stated without its mandatory qualification).
    """

    id: str
    summary: str
    kind: str  # "forbid" | "require" | "block"
    pattern: re.Pattern | None = None
    # Matched-span veto. Narrower than the refutation guard: used where the
    # pattern legitimately overlaps a correct statement about the same subject
    # ("a Kafka transaction ... never a database row").
    unless: re.Pattern | None = None
    trigger: re.Pattern | None = None
    expect: re.Pattern | None = None
    # "block" rules: both must appear inside the SAME fenced config block.
    block_a: re.Pattern | None = None
    block_b: re.Pattern | None = None
    scope: re.Pattern | None = None  # limit require-rules to matching files
    # How far from the trigger the qualification may live. Too wide and an
    # unrelated nearby mention satisfies the rule (M20/M21/M23 survived that
    # way); "line" restricts it to the trigger's own line.
    window: int | str = 1500
    message: str = ""
    should_fire: list[str] = field(default_factory=list)
    should_pass: list[str] = field(default_factory=list)


def _rx(p: str) -> re.Pattern:
    return re.compile(p, re.IGNORECASE | re.MULTILINE)


# Gap token for proximity patterns. Excludes ';' as well as '.' so a pattern
# cannot span two clauses: a match straddling a clause break picks up the
# neighbouring clause's negation and suppresses itself. That is how
# "Round-robin is not used; null key means round-robin" scored zero.
GAP = r"[^.;\n]"

# Like GAP but tolerates a single line wrap, so a claim split across two lines
# still matches. Blank lines still stop it, keeping a match inside one paragraph.
WRAP = r"(?:[^.;\n]|\n(?!\s*\n))"

# Config keys contain dots, so a GAP cannot reach across "cleanup.policy=compact".
# DOTGAP allows them while still stopping at a clause break.
DOTGAP = r"[^;\n]"

# A threshold magnitude, written either way. `10000` and `ten thousand` are the
# same fabricated constant; matching only the digits made the rule look complete
# while the most natural English phrasing walked past it.
LAGNUM = (r"(?:\d[\d,_ ]{2,}"
          r"|(?:one|two|three|four|five|six|seven|eight|nine|ten|twenty|thirty"
          r"|forty|fifty|a\s+few|several)\s+(?:hundred|thousand|million)"
          r"|(?:hundreds?|thousands?|millions?)\s+of)")

# Verbs that turn a mention into a recommendation. Deliberately excludes
# "default(s) to" — the docs state what each client defaults to, constantly.
#
# Mood matters. A bare past participle is DESCRIPTIVE — "Producer configured with
# acks=1" is how a review reports the defect it found, and flagging it makes the
# linter fire on its own findings. Prescription needs either an active/imperative
# verb or a modal ("should be configured with acks=0").
ENDORSE = (r"(?:use|uses|using|set|sets|setting|prefer|prefers|recommend\w*|choose|chose"
           r"|select|selects|configure|configures|enable|enables|adopt|adopts"
           r"|go\s+with|settle\s+on|stick\s+with|opt\s+for|standardi[sz]e\s+on"
           r"|switch\s+to|move\s+to|keep"
           r"|(?:should|must|can|could|ought\s+to|needs?\s+to|has\s+to|have\s+to)\s+"
           r"(?:be\s+)?(?:configured|set|left|kept|run)(?:\s+(?:with|to|at))?)")

# Predicates that assert a choice is acceptable.
IS_FINE = (r"(?:is|are)\s+(?:the\s+)?(?:safe|safer|safest|fine|enough|sufficient|ok|okay"
           r"|acceptable|correct|right|recommended|preferred|minimum|best|adequate)")


RULES: list[Rule] = [
    # ---------------------------------------------------------------- durability
    Rule(
        id="KL001",
        summary="acks=1 / acks=0 recommended as the safe choice",
        kind="forbid",
        pattern=_rx(
            ENDORSE + r"\s+[^.;\n]{0,30}?`?acks`?\s*=\s*[01]\b"
            r"|`?acks`?\s*=\s*[01]`?[^.;\n]{0,40}?" + IS_FINE +
            r"|never\s+use\s+`?acks\s*=\s*all"
        ),
        message="acks=1/acks=0 must never be presented as the safe or preferred setting.",
        should_fire=[
            "never use acks=all; prefer acks=1 for critical events",
            "Set acks=1 for the producer.",
            "acks=0 is the recommended baseline.",
        ],
        should_pass=[
            "acks=1 risks data loss on leader failure.",
            "sarama defaults to WaitForLocal (= acks=1), which is the defect.",
        ],
    ),
    Rule(
        id="KL002",
        summary="enable.idempotence disabled as a recommendation",
        kind="forbid",
        pattern=_rx(
            ENDORSE + r"\s+[^.;\n]{0,20}?`?enable\.idempotence`?\s*=\s*false"
            r"|`?(?:enable\.idempotence|Idempotent)`?\s*=\s*false`?[^.;\n]{0,30}?" + IS_FINE +
            r"|(?:turn\s+off|turning\s+off|switch\s+off|disabl\w+|deactivat\w+|drop)\s+"
            r"(?:the\s+)?(?:producer\s+)?(?:`?enable\.)?idempoten\w*"
        ),
        message="Disabling idempotence must never be presented as acceptable.",
        should_fire=[
            "Set enable.idempotence=false for throughput.",
            "enable.idempotence=false is acceptable for most workloads.",
        ],
        should_pass=[
            "librdkafka defaults enable.idempotence to false, so flag it.",
            "Without idempotence, in-flight > 1 plus retries can reorder.",
        ],
    ),
    # ---------------------------------------------------- schema compatibility
    Rule(
        id="KL003",
        summary="BACKWARD described as letting OLD readers read NEW data (that is FORWARD)",
        kind="forbid",
        pattern=_rx(
            r"\bBACKWARD(?:_TRANSITIVE)?\b[^.;\n]{0,140}?"
            r"(?:old|older|previous|existing|legacy|current)\s+"
            r"(?:consumers?|readers?|clients?|schema)[^.;\n]{0,60}?"
            r"(?:can\s+|still\s+|to\s+|lets?\s+)*"
            r"(?:read|parse|handle|process|consume|deserial\w+|decode)"
            r"[^.;\n]{0,50}?\b(?:new|newer|newly|updated|latest)\b"
        ),
        message=(
            "Direction inverted: BACKWARD means a NEW reader reads OLD data. "
            "'old readers read new data' is FORWARD."
        ),
        should_fire=[
            "BACKWARD_TRANSITIVE guarantees old consumers can read the new schema.",
            "With BACKWARD, existing readers can read new data safely.",
        ],
        should_pass=[
            "BACKWARD means a reader on the new schema can read data written with the old schema.",
            "FORWARD — a reader on the old schema can read data written with the new schema.",
            # Refutation path: the doc must be able to quote the myth to reject it.
            '"BACKWARD guarantees old consumers can read new data" is the single most common\ninversion. That is FORWARD.',
        ],
    ),
    Rule(
        id="KL004",
        summary="BACKWARD or FULL claimed to forbid all field deletion",
        kind="forbid",
        pattern=_rx(
            r"\b(?:BACKWARD|FULL)(?:_TRANSITIVE)?\b[^.;\n]{0,160}?"
            r"(?:cannot|can't|can not|never|must not|do not|don't)\s+"
            r"(?:remove|delete)\s+(?:any\s+)?(?:existing\s+)?fields?"
            r"|(?:cannot|can't|never)\s+(?:remove|delete)\s+(?:any\s+)?fields?"
            r"[^.;\n]{0,120}?\b(?:BACKWARD|FULL)\b"
            # Bullet/standalone form. In a compatibility doc the bare assertion
            # is wrong on its own — the mode heading is usually a line or two up,
            # out of reach of a same-line window.
            r"|^\s*(?:[-*+]\s*|\d+\.\s*)?(?:cannot|can't|can not|must not|never)\s+"
            r"(?:remove|delete)\s+(?:any|existing)\s+fields?\b"
            # "never remove required ones" framing — treats deletion as the sin
            # rather than deletion-without-a-default.
            r"|never\s+(?:remove|delete)\s+(?:existing|required)\s+(?:fields?|ones)"
            r"|fields?\s+can\s+only\s+(?:ever\s+)?be\s+added"
            r"|(?:must\s+)?never\s+(?:remove|delete)\s+any\b"
            r"|only\s+ever\s+be\s+added"
        ),
        message=(
            "BACKWARD permits deleting optional/defaulted fields; FULL permits "
            "adding AND deleting optional fields. Neither is add-only."
        ),
        should_fire=[
            "FULL compatibility: cannot remove any fields.",
            "Under BACKWARD you must not delete existing fields.",
            "- Cannot remove any fields\n",
            "add new optional fields, never remove required ones (BACKWARD compatible)",
        ],
        should_pass=[
            "BACKWARD | Delete fields; add optional fields | Last version only",
            "Deleting a required field with no default is incompatible in every mode.",
            "BACKWARD does allow deleting a field. The constraint is that the field must have been optional.",
        ],
    ),
    Rule(
        id="KL005",
        summary="BACKWARD_TRANSITIVE asserted as universally safest",
        kind="forbid",
        pattern=_rx(
            r"\bBACKWARD_TRANSITIVE\b[^.;\n]{0,80}?\bis\s+"
            r"(?:the\s+)?(?:safest|always\s+safest|best|always\s+correct)"
            r"|(?:always|universally)\s+(?:use|choose|prefer)\s+BACKWARD_TRANSITIVE"
            r"|BACKWARD_TRANSITIVE\s+is\s+safest\s+for\s+most"
        ),
        message=(
            "Transitive modes constrain the schema to the intersection of all "
            "history; recommend them from a stated condition, not as a default."
        ),
        should_fire=[
            "BACKWARD_TRANSITIVE is safest for most cases.",
            "Always use BACKWARD_TRANSITIVE.",
        ],
        should_pass=[
            "Choose transitive when old data or old readers survive across versions.",
            "BACKWARD_TRANSITIVE checks all previous versions rather than just the last.",
        ],
    ),
    # -------------------------------------------------------------- partitions
    Rule(
        id="KL006",
        summary="null key described as round-robin",
        kind="forbid",
        pattern=_rx(
            # null/nil key ... round-robin  (either order, small window)
            r"(?:null|nil|no)\s+key[^.;\n]{0,60}?round[- ]robin"
            r"|key\s+is\s+(?:null|nil)[^.;\n]{0,60}?round[- ]robin"
            r"|\b(?:null|nil)\b[^.;\n]{0,15}?round[- ]robin"
            r"|round[- ]robin[^.;\n]{0,60}?(?:when|if|for)?\s*(?:the\s+)?"
            r"(?:key\s+is\s+)?(?:null|nil|absent)\s+key?"
            r"|(?:without\s+a\s+key|keyless|key\s+(?:is\s+)?unset|unset\s+key|no\s+key)"
            r"[^.;\n]{0,70}?round[- ]robin"
            r"|round[- ]robin[^.;\n]{0,70}?(?:without\s+a\s+key|keyless|key\s+unset)"
            # Anaphora: "set a partition key … without one, records go round-robin".
            # The key-absence marker is a pronoun, so every literal form above
            # misses it. Anchored on an earlier `key` in the SAME clause, which
            # is what makes "without one" resolvable at all.
            r"|key\b[^.;\n]{0,40}?without\s+(?:one|it)\b[^.;\n]{0,70}?round[- ]robin"
            # "when the key is omitted / left unset / not set"
            r"|key\s+(?:is\s+)?(?:omitted|missing|not\s+set|left\s+"
            r"(?:out|unset|empty|blank))[^.;\n]{0,70}?round[- ]robin"
        ),
        message=(
            "No mainstream client round-robins null keys by default: Java and "
            "librdkafka are batch-sticky, sarama is random. State the lost "
            "ordering, not a distribution shape."
        ),
        should_fire=[
            "Key is null → round-robin across partitions",
            "null (round-robin = no ordering)",
            "Set a partition key to preserve ordering — without one, records are "
            "spread round-robin over the partitions.",
            "When the key is omitted the producer sends round-robin.",
        ],
        should_pass=[
            "null key → no per-key ordering, placement is batch-sticky or random",
            "RoundRobinPartitioner is an opt-in class you must name explicitly.",
            # The anaphoric alternative must not reach across a sentence: here
            # `one` refers to a topic, and round-robin belongs to another claim.
            "Pick a key for every topic that needs ordering. Without one you "
            "still cannot assume round-robin placement.",
            # Refutation path
            "### Default partitioner — null key is not round-robin",
            '**No client round-robins null keys by default.** "Null key → round-robin" is\nwrong on all three.',
        ],
    ),
    Rule(
        id="KL007",
        summary="high key cardinality claimed to create too many partitions",
        kind="forbid",
        pattern=_rx(
            r"high[- ]cardinality[^.;\n]{0,80}?(?:too\s+many|creates?|causes?)\s+partitions"
            r"|(?:too\s+many|more)\s+partitions[^.;\n]{0,60}?high[- ]cardinality"
            r"|cardinalit\w+[^.;\n]{0,80}?"
            r"(?:spawn|create|caus|produc|generat|result\s+in|end\s+up\s+with)\w*\s+"
            r"(?:an?\s+)?(?:excessive|too\s+many|huge|unbounded|more)\s+"
            r"(?:number\s+of\s+)?partitions"
        ),
        message=(
            "Partition count is a topic property; keys are hashed modulo it. "
            "High cardinality cannot create partitions."
        ),
        should_fire=[
            "Avoid high-cardinality unbounded keys (too many partitions).",
        ],
        should_pass=[
            "High key cardinality does not create partitions.",
            "Very high cardinality is usually good for distribution.",
        ],
    ),
    Rule(
        id="KL008",
        summary="sharded/composite hot key claimed to preserve Kafka-native ordering",
        kind="forbid",
        pattern=_rx(
            r"spreads?\s+hot\s+keys?\s+across\s+(?:n|\d+|multiple)\s+partitions"
            r"[^.;\n]{0,80}?(?:while\s+)?maintain(?:ing|s)?[^.;\n]{0,40}?ordering"
            r"|shard(?:ed|ing)?[^.;\n]{0,60}?(?:keeps?|preserv\w+|maintain\w*)"
            r"[^.;\n]{0,30}?(?:per-entity\s+)?ordering"
        ),
        message=(
            "Splitting one entity across partitions removes Kafka's ordering "
            "guarantee for it — the broker cannot know the shards are related."
        ),
        should_fire=[
            "custom partitioner that spreads hot keys across N partitions while maintaining per-entity ordering",
            "Sharding the key preserves ordering and fixes the hot partition.",
        ],
        should_pass=[
            "Sharded key (`hotkey:{n}`) does not keep per-entity order.",
            "Composite key (tenant_id:entity_id) keeps ordering for the entity.",
        ],
    ),
    Rule(
        id="KL009",
        summary="hard-coded events/sec threshold for global ordering",
        kind="forbid",
        pattern=_rx(
            r"global\s+ordering[^.;\n]{0,120}?[<>]\s*\d[\d,]*\s*"
            r"(?:events?|msgs?|messages?|records?)\s*(?:/|per\s+)s"
            r"|[<>]\s*\d[\d,]*\s*(?:events?|messages?)\s*(?:/|per\s+)s"
            r"[^.;\n]{0,80}?(?:single\s+partition|global\s+ordering)"
            r"|throughput\s+is\s+(?:very\s+)?low\s*\([<>]\s*\d"
            # Prose forms: "single partition is fine under 100 events/sec",
            # "global ordering works up to roughly 500 messages per second".
            r"|(?:single\s+partition|one\s+partition|global\s+ordering)[^.;\n]{0,90}?"
            r"(?:under|below|up\s+to|less\s+than|beneath|[<>])\s*"
            r"(?:roughly\s+|about\s+|around\s+)?\d[\d,]*\s*"
            r"(?:events?|messages?|records?|msgs?)\s*(?:/|per\s+)?\s*(?:s\b|sec|second)"
        ),
        message=(
            "The single-partition ceiling is 1/p99_processing_time, which spans "
            "orders of magnitude. Give the formula, not a memorised number."
        ),
        should_fire=[
            "Global ordering | Single partition | Only if throughput is very low (<100 events/sec)",
            "If global ordering is required AND throughput is low (<100 events/sec), single partition is acceptable.",
        ],
        should_pass=[
            "Global ordering has no fixed events/sec threshold.",
            "max sustainable rate is approximately 1 / p99_processing_time",
        ],
    ),
    # -------------------------------------------------- transactions / outbox
    Rule(
        id="KL010",
        summary="Kafka transaction claimed to cover a database/outbox write",
        kind="forbid",
        pattern=_rx(
            # Negated forms ("a Kafka transaction cannot include a DB write") are
            # the correction, not the claim — exclude them explicitly.
            r"kafka\s+transactions?\s+"
            r"(?!(?:can\s*not|cannot|can't|does\s+not|doesn't|never|is\s+not|are\s+not))"
            + WRAP + r"{0,100}?\b(?:outbox|database|db)\b"
            r"|(?:atomic|atomicity)" + WRAP + r"{0,60}?\(e\.g\.,?\s*event\s*\+\s*outbox\)"
            r"|use\s+kafka\s+transactions" + WRAP + r"{0,80}?(?:db|database)\s+write"
            r"|(?:wrap|wrapping|enclose|enclosing|put|place|include|combine)\w*"
            + WRAP + r"{0,90}?in\s+(?:a\s+|one\s+|the\s+same\s+)?kafka\s+transaction"
        ),
        # The correct statement names the same two nouns in order to DENY the
        # relationship. A negation inside the matched span is never an endorsement.
        unless=_rx(r"\bnever\b|\bcannot\b|\bcan\s*not\b|\bnot\b"),
        message=(
            "A Kafka transaction spans Kafka partitions and consumer offsets "
            "only. The outbox pattern is a database transaction."
        ),
        should_fire=[
            "if producing to multiple topics must be atomic (e.g., event + outbox), use Kafka transactions",
            "Use Kafka transactions so the database write and the event commit together.",
            # Line-wrapped prose must still match — real docs wrap mid-sentence.
            "we will use Kafka transactions\nto make the DB write and the outbox publish commit together",
        ],
        should_pass=[
            "A Kafka transaction cannot include a database write.",
            "Database to Kafka: the outbox pattern — one database transaction.",
            # Refutation path
            'If you find yourself writing\n"use Kafka transactions to make the DB write and the event atomic", you have\ndescribed something Kafka cannot do.',
        ],
    ),
    Rule(
        id="KL011",
        summary="outbox or DLQ described as exactly-once",
        kind="forbid",
        pattern=_rx(
            r"outbox[^.;\n]{0,80}?exactly[- ]once"
            r"|exactly[- ]once[^.;\n]{0,60}?\boutbox\b"
            r"|\bDLQ\b[^.;\n]{0,60}?guarantees?\s+exactly[- ]once"
        ),
        message=(
            "The relay's publish and mark-published are two commits, so the "
            "outbox is at-least-once. Same for DLQ publish + offset commit."
        ),
        should_fire=[
            "The outbox pattern guarantees exactly-once delivery.",
            "Exactly-once is achieved by the outbox relay.",
        ],
        should_pass=[
            "The outbox pattern guarantees at-least-once delivery with DB-level atomicity.",
            "The outbox is an at-least-once publisher by construction.",
        ],
    ),
    Rule(
        id="KL012",
        summary="removed sendOffsetsToTransaction(String) overload",
        kind="forbid",
        pattern=_rx(
            # The first argument may itself contain parentheses — offsets(records) —
            # so a [^)]* argument list stops too early and the rule misses the call
            # entirely. Anchor on the final argument before the closing paren instead.
            r"sendOffsetsToTransaction\s*\(.{0,120}?,\s*"
            r"(?!consumer\.groupMetadata|groupMetadata|.*ConsumerGroupMetadata)"
            r"[a-z_][A-Za-z0-9_]*(?:Id|ID|id)\s*\)"
        ),
        message=(
            "sendOffsetsToTransaction(Map, String) was deprecated by KIP-447 and "
            "removed in Kafka 4.x. Use consumer.groupMetadata()."
        ),
        should_fire=[
            "producer.sendOffsetsToTransaction(offsets, consumerGroupId);",
            "producer.sendOffsetsToTransaction(map, groupId)",
        ],
        should_pass=[
            "producer.sendOffsetsToTransaction(offsets, consumer.groupMetadata());",
            "producer.sendOffsetsToTransaction(offsets(records), consumer.groupMetadata());",
        ],
    ),
    # ----------------------------------------------------- absolutism / dogma
    Rule(
        id="KL013",
        summary="unconditional 'every consumer must have a DLQ' framing",
        kind="forbid",
        pattern=_rx(
            r"(?:every|all|any)\s+consumers?\s+must\s+have\s+(?:a\s+)?(?:DLQ|dead[- ]letter)"
            r"|(?:DLQ|dead[- ]letter(?:\s+\w+)?)\s+is\s+(?:always\s+)?"
            r"(?:mandatory|required|compulsory|non-negotiable)"
            r"|must\s+be\s+routed\s+to\s+a\s+DLQ\s+topic\s+instead"
        ),
        message=(
            "The reviewable requirement is a defined, owned policy for "
            "unprocessable messages. Ordered state machines correctly halt "
            "instead of parking."
        ),
        should_fire=[
            "Every consumer must have a DLQ.",
            "DLQ is always mandatory for production topics.",
        ],
        should_pass=[
            "A defined, owned policy for unprocessable messages.",
            "Score PASS for a documented non-DLQ policy with an owner.",
        ],
    ),
    Rule(
        id="KL014",
        summary="raw JSON declared categorically unacceptable in production",
        kind="forbid",
        pattern=_rx(
            r"(?:raw|schema-?less)\s+json[^.;\n]{0,80}?"
            r"(?:unacceptable|not\s+acceptable|forbidden|banned)\s+in\s+production"
            r"|(?:raw|schema-?less)\s+json[^.;\n]{0,60}?"
            r"(?:never|must\s+not|cannot)\s+be\s+used\s+in\s+production"
        ),
        message=(
            "Score the absence of contract enforcement, not the absence of a "
            "registry. External schema governance + validating consumers is a "
            "legitimate position."
        ),
        should_fire=["Raw JSON (no schema) only for prototyping — unacceptable in production."],
        should_pass=[
            "Raw JSON (no registry) is a risk position, not an automatic defect.",
            "It is a genuine finding when the contract lives only in the producer's code.",
        ],
    ),
    Rule(
        id="KL015",
        summary="RF=1 or low RF declared unacceptable without a trade-off path",
        kind="forbid",
        pattern=_rx(
            r"RF\s*=\s*1\s+is\s+unacceptable\s+for\s+any"
            r"|replication\s+factor[^.;\n]{0,40}?(?:must\s+always|always\s+must)\s+be\s*(?:≥|>=)\s*3"
        ),
        message=(
            "RF is a durability trade-off. Derived/rebuildable topics with a "
            "recorded owner and rationale are WARN, not FAIL."
        ),
        should_fire=["RF=1 is unacceptable for any non-ephemeral data."],
        should_pass=[
            "Replication factor sized to the durability requirement.",
            "score WARN with the owner and rationale recorded when it is a documented trade-off",
        ],
    ),
    # ------------------------------------------------------ 4.x / client facts
    Rule(
        id="KL016",
        summary="max.in.flight must be 1 stated as a general (non-sarama) rule",
        kind="forbid",
        pattern=_rx(
            r"max\.in\.flight\.requests\.per\.connection\s*(?:=|must\s+be(?:\s+set\s+to)?)\s*1\b"
            r"(?![^.;\n]{0,120}sarama)"
            r"|idempoten\w+[^.;\n]{0,60}?requires?[^.;\n]{0,40}?in[- ]flight[^.;\n]{0,20}?(?:=|of|to)\s*1\b"
        ),
        message=(
            "On the Java client, idempotence preserves ordering for any "
            "max.in.flight <= 5. The 'must be 1' rule is sarama-specific "
            "(Net.MaxOpenRequests)."
        ),
        should_fire=[
            "Set max.in.flight.requests.per.connection=1 for ordering.",
            "Idempotence requires in-flight = 1.",
        ],
        should_pass=[
            "enabling idempotence requires the value of this configuration to be less than or equal to 5",
            "Net.MaxOpenRequests = 1 is sarama-specific and required by its Validate().",
        ],
    ),
    Rule(
        id="KL017",
        summary="Kafka version model stops before 4.x",
        kind="forbid",
        # Must inspect the version LIST itself. Scoping to the row is not enough:
        # the same row's rationale text mentions 4.0, which satisfied a require-rule
        # while the list still stopped at 3.x (mutation M20 survived on that).
        pattern=_rx(r"\*\*Kafka version\*\*\s*\((?![^)]*\b4\.)[^)]*\)"),
        scope=re.compile(r"SKILL\.md$"),
        message="Gate 1 must offer 4.x as a version option; 4.0 changed defaults and protocols.",
        should_fire=[
            "| **Kafka version** (2.x / 3.x) | Exactly-once features vary |",
            "| **Kafka version** (2.x / 3.x) | KIP-848 and KIP-890 land at 4.0 |",
        ],
        should_pass=["| **Kafka version** (2.x / 3.x / 4.x) | defaults differ at 3.0 |"],
    ),
    Rule(
        id="KL018",
        summary="CooperativeStickyAssignor recommended without protocol qualification",
        kind="require",
        trigger=_rx(r"partition\.assignment\.strategy\s*=\s*\S*CooperativeStickyAssignor"),
        # Must name the CLASSIC protocol specifically. A bare "group.protocol"
        # mention is satisfied by the adjacent new-protocol section, which is
        # exactly the passage that makes this config invalid.
        expect=_rx(r"\bclassic\b"),
        window=600,
        message=(
            "partition.assignment.strategy is unusable under "
            "group.protocol=consumer (Kafka 4.0+). Say which protocol applies."
        ),
        should_fire=[
            "# Use cooperative sticky assignor\n"
            "partition.assignment.strategy=org.apache.kafka.clients.consumer.CooperativeStickyAssignor\n",
            # A nearby group.protocol mention must NOT be enough on its own.
            "partition.assignment.strategy=org.apache.kafka.clients.consumer.CooperativeStickyAssignor\n"
            "\nUnder group.protocol=consumer the assignor moves server-side.\n",
        ],
        should_pass=[
            "Classic protocol (group.protocol=classic):\n"
            "partition.assignment.strategy=org.apache.kafka.clients.consumer.CooperativeStickyAssignor\n"
        ],
    ),
    Rule(
        id="KL023",
        summary="compaction recommended for an event-sourced log",
        kind="forbid",
        # Requires an ENDORSING construction, not mere co-occurrence: a correct
        # doc has to be able to say "compaction destroys an event-sourced log"
        # and to list the pair as a review signal.
        pattern=_rx(
            r"requires?\s+compacted\s+topics?"
            # event-sourcing ... <endorsing verb> ... compact
            r"|event[- ]sourc\w+" + DOTGAP + r"{0,70}?"
            r"(?:requires?|needs?|uses?|should\s+use|must\s+use|is\s+stored\s+in"
            r"|configur\w+|set\s+up|enabl\w+|turn\s+on|switch\s+on|adopt\w*)"
            + DOTGAP + r"{0,40}?\bcompact"
            # <endorsing verb> ... compact ... event-sourcing. DOTGAP, not GAP:
            # the object is usually a config key ("cleanup.policy=compact"), and
            # a dot-excluding gap cannot reach across it.
            r"|" + ENDORSE + r"\s+" + DOTGAP + r"{0,50}?\bcompact\w*\b"
            + DOTGAP + r"{0,70}?\bevent[- ]sourc"
            # "set the event log to compact" — the connector must be adjacent.
            # A loose gap here matched the CORRECT sentence "keep the event log on
            # cleanup.policy=delete and compact a separate snapshot topic", where
            # `compact` applies to the other topic.
            r"|event\s+log\s+(?:to|as|into)\s+(?:be\s+)?compact"
            # "the event history topic belongs on cleanup.policy=compact".
            # Same adjacency discipline: the compaction reference must be the
            # DIRECT object of the connector, optionally via the config key, so
            # `... on cleanup.policy=delete and compact a snapshot topic` cannot
            # reach it — that gap resolves to `delete`, not `compact`.
            r"|(?:event|aggregate|domain[- ]event)\s+"
            r"(?:history|log|journal|stream|store)\s*(?:topic)?\s+"
            r"(?:belongs?\s+on|goes?\s+on|lives?\s+on|sits?\s+on|is\s+set\s+to"
            r"|should\s+(?:be\s+)?(?:on|set\s+to|use)|needs?|requires?|uses?)\s+"
            r"(?:be\s+)?(?:a\s+|the\s+)?(?:cleanup\.policy\s*=\s*)?compact"
        ),
        message=(
            "cleanup.policy=compact retains only the latest value per key, so on "
            "a log keyed by aggregate ID it deletes the history that event "
            "sourcing exists to keep. Separate the append-only event log from a "
            "compacted snapshot/state topic."
        ),
        should_fire=[
            "- Requires compacted topics or infinite retention",
            "Event sourcing needs a compacted topic to retain state.",
            "Use compaction for the event-sourcing log.",
            "The event history topic belongs on cleanup.policy=compact.",
            "The aggregate journal should be set to compact.",
        ],
        should_pass=[
            "| **Event log** | Immutable history | `delete` with long retention | Aggregate ID |",
            "Compaction destroys an event-sourced log.",
            "an empty cleanup.policy list disables cleanup entirely",
            # Listing the pair as a review signal is not a recommendation.
            "compacted topics for event sourcing, partition key redesign",
            # The adjacency guard: the connector's object here is `delete`.
            "Keep the event log on cleanup.policy=delete and compact a snapshot topic.",
        ],
    ),
    Rule(
        id="KL024",
        summary="fixed consumer-lag alert threshold presented as a recommendation",
        kind="forbid",
        # SKILL.md forbids undrived numeric thresholds; the references must obey
        # their own rule. A raw message count is meaningless across workloads.
        # No leading \b on "lag": the threshold usually appears inside a metric
        # name (kafka_consumergroup_lag, records_lag_max), where the preceding
        # underscore is a word character and \b never matches.
        # A spelled-out magnitude is the same fabricated constant as a digit
        # string: "ten thousand records" carries exactly as little workload
        # information as "10000". Digits-only matching read as thorough while
        # leaving the plainest English phrasing of the claim undetected.
        pattern=_rx(
            r"lag\w*\s*[<>]=?\s*\d[\d,_ ]{2,}"
            r"|lag\w*[^.;\n]{0,30}?(?:exceeds?|exceeding|goes?\s+above|rises?\s+above"
            r"|climbs?\s+above|passes|reach\w*|hits?|tops?|crosses|"
            r"is\s+(?:above|over|greater\s+than|more\s+than))"
            r"[^.;\n]{0,20}?" + LAGNUM
            + r"|(?:alert|threshold|page|warn)\w*" + WRAP + r"{0,60}?lag\w*" + WRAP
            + r"{0,40}?[<>]=?\s*" + LAGNUM
        ),
        message=(
            "Derive the lag alert from time-to-drain "
            "(records_lag_max / records_consumed_rate) against a stated freshness "
            "SLO. A copied message count is four seconds for one consumer and "
            "three hours for another."
        ),
        should_fire=[
            "# Alert: lag > 10000 messages sustained for > 5 minutes",
            "Set the alert threshold at lag > 5000 records.",
            "  expr: kafka_consumergroup_lag > 10000",
            "alert: ConsumerLagHigh\n  expr: records_lag_max >= 25000",
            "Page when consumer lag reaches ten thousand records.",
            "Escalate once lag tops fifty thousand events.",
        ],
        should_pass=[
            "lag_seconds ≈ records_lag_max / records_consumed_rate",
            "Set the threshold from the freshness the downstream consumer has committed to",
            "Alert on sustained lag > threshold.",
            # A magnitude that is not a threshold: describing observed scale is
            # not prescribing an alert value.
            "A drained transactional topic can still report lag; aborted records occupy offsets.",
        ],
    ),
    Rule(
        id="KL025",
        summary="static membership claimed to eliminate rebalance on restart",
        kind="forbid",
        pattern=_rx(
            r"(?:static\s+(?:group\s+)?membership|group\.instance\.id)" + GAP
            + r"{0,80}?restarts?\s+(?:do\s*n[o']?t|never|won't|will not)\s+"
            r"(?:trigger|cause)" + GAP + r"{0,20}?rebalanc"
            r"|restarts?\s+(?:do\s*n[o']?t|never|won't)\s+(?:trigger|cause)"
            + GAP + r"{0,20}?rebalanc"
            # "static membership prevents/avoids/removes rebalances".
            # The lookahead spares "avoids a rebalance ONLY if it returns within
            # session.timeout.ms", which is the correct, qualified statement.
            r"|(?:static\s+(?:group\s+)?member\w*|group\.instance\.id|static\s+id)"
            + DOTGAP + r"{0,70}?"
            # The qualifier can sit on EITHER side of the verb: "avoids a
            # rebalance only if …" and "only avoids a rebalance for …" are the
            # same correct statement. Guarding just the trailing position made
            # the rule fire on the checklist item that states the bound — a guard
            # that forbids the accurate sentence is a defect, not strictness.
            r"(?<!only )(?:prevents?|avoids?|eliminates?|removes?|stops?|rules?\s+out)"
            # \b after \w* is load-bearing: without it the engine backtracks to
            # "rebalanc", the lookahead then inspects "e only" instead of " only",
            # and the qualified-correct sentence matches anyway.
            + DOTGAP + r"{0,40}?rebalanc\w*\b(?!\s+only\b)"
            # "a static member can restart without causing a rebalance"
            r"|(?:static\s+(?:group\s+)?member\w*|static\s+id)" + DOTGAP
            + r"{0,70}?without" + DOTGAP + r"{0,50}?rebalanc"
            # "static membership guarantees rolling deploys will not rebalance".
            # The negation is on the rebalance, not on the verb, so the
            # prevents/avoids alternative above never sees it. The fixed-width
            # lookbehinds spare the refutation ("does not guarantee that ...") —
            # a guard that fires on the sentence correcting the myth is a bypass.
            r"|(?:static\s+(?:group\s+)?member\w*|group\.instance\.id|static\s+id)"
            + DOTGAP + r"{0,70}?(?<!not )(?<!n't )(?:guarantees?|ensures?|means)"
            + DOTGAP + r"{0,60}?(?:will\s+not|won'?t|never|no|do\s*n[o']?t"
            r"|does\s*n[o']?t)\s*" + DOTGAP + r"{0,25}?rebalanc"
        ),
        message=(
            "Static membership only avoids a rebalance for a restart that "
            "completes within session.timeout.ms; past that the coordinator "
            "evicts the member and the group rebalances as usual."
        ),
        should_fire=[
            "# Assign a stable identity — consumer restarts don't trigger rebalance",
            "With group.instance.id set, restarts never trigger a rebalance.",
            "Static membership guarantees rolling deployments will not rebalance the group.",
            "group.instance.id ensures a rolling deploy never rebalances the group.",
        ],
        should_pass=[
            "a restart that completes within session.timeout.ms rejoins as the same member",
            # The qualifier before the verb, not after it.
            "Static membership only avoids a rebalance for a restart inside session.timeout.ms.",
            "It does not abolish rebalancing — it buys a window.",
            # Guarding the guard: the sentence that corrects the myth states the
            # myth, and must not be graded as an assertion of it.
            "Static membership does not guarantee that a rolling deploy will not rebalance.",
        ],
    ),
    Rule(
        id="KL026",
        summary="Avro-vs-Protobuf speed stated as a fact rather than measured",
        kind="forbid",
        # Binary-vs-text ("Avro is faster than JSON") is a property of the format
        # and stays legal. Ranking the two binary formats against each other is
        # implementation-, payload- and benchmark-dependent, so an unqualified
        # ranking is a fabricated fact — the same failure class as a memorised
        # events/sec threshold (KL024).
        pattern=_rx(
            r"(?:avro|protobuf|protocol\s+buffers)" + DOTGAP + r"{0,60}?fastest\b"
            r"|fastest\b" + DOTGAP + r"{0,60}?(?:avro|protobuf|protocol\s+buffers)"
            r"|(?:avro|protobuf|protocol\s+buffers)" + DOTGAP + r"{0,60}?"
            r"(?:faster|quicker|outperforms?|beats?|higher\s+throughput)"
            + DOTGAP + r"{0,40}?(?:avro|protobuf|protocol\s+buffers)"
            # A superlative names the whole field without naming the loser:
            # "Protobuf gives the highest throughput of the registry formats"
            # ranks it above Avro without the word Avro appearing.
            r"|(?:avro|protobuf|protocol\s+buffers)" + DOTGAP + r"{0,60}?"
            r"(?:highest|best|greatest|top|maximum)\s+"
            r"(?:throughput|performance|speed|serialisation|serialization)"
            r"|(?:highest|best|greatest|top|maximum)\s+"
            r"(?:throughput|performance|speed)" + DOTGAP
            + r"{0,60}?(?:avro|protobuf|protocol\s+buffers)"
        ),
        message=(
            "Avro-vs-Protobuf throughput depends on the client library, the "
            "payload shape and what the benchmark counts; published results "
            "disagree. State them as comparable and measure, or compare against "
            "text formats instead — that ranking does hold."
        ),
        should_fire=[
            "| **Protobuf** | Confluent | Excellent | Fastest | No |",
            "Protobuf is faster than Avro for high-throughput topics.",
            "Use Avro — it outperforms Protobuf on the JVM.",
            "Of the registry formats, Avro is the fastest.",
            "Protobuf gives the highest throughput of the registry formats.",
            "For best performance among the registry formats, choose Avro.",
        ],
        should_pass=[
            "Avro and Protobuf are comparable; benchmark with your own payload.",
            "Both are binary and far faster than JSON Schema on the wire.",
            "Avro is faster than raw JSON because it is binary.",
            "| **Protobuf** | Confluent | Excellent | Binary, compact | No |",
            # A superlative about something other than the format ranking.
            "Size the partition count from the topic's highest sustained throughput.",
        ],
    ),
    Rule(
        id="KL022",
        summary="group.protocol=consumer set alongside a config it disables",
        kind="block",
        # Scoped to a fenced config block: prose legitimately discusses both
        # together, a config file that sets both is simply broken.
        block_a=_rx(r"^\s*(?!#)group\.protocol\s*=\s*consumer\b"),
        block_b=_rx(
            r"^\s*(?!#)(?:partition\.assignment\.strategy|session\.timeout\.ms"
            r"|heartbeat\.interval\.ms)\s*="
        ),
        message=(
            "Under group.protocol=consumer (KIP-848), partition.assignment.strategy, "
            "session.timeout.ms and heartbeat.interval.ms are not usable — the "
            "line is dead config. Heartbeat/session move to broker configs."
        ),
        should_fire=[
            "```properties\ngroup.protocol=consumer\n"
            "partition.assignment.strategy=org.apache.kafka.clients.consumer.CooperativeStickyAssignor\n```",
            "```properties\nsession.timeout.ms=45000\ngroup.protocol=consumer\n```",
        ],
        should_pass=[
            "```properties\ngroup.protocol=consumer\ngroup.remote.assignor=uniform\n"
            "#   group.consumer.session.timeout.ms\n```",
            "```properties\ngroup.protocol=classic\n"
            "partition.assignment.strategy=org.apache.kafka.clients.consumer.CooperativeStickyAssignor\n```",
        ],
    ),
    Rule(
        id="KL019",
        summary="exactly-once described without the consumer-side isolation level",
        kind="require",
        trigger=_rx(r"initTransactions\s*\("),
        expect=_rx(r"read_committed"),
        message=(
            "EOS needs isolation.level=read_committed on the consumer; the "
            "default read_uncommitted reads aborted records."
        ),
        should_fire=["producer.initTransactions();\nproducer.beginTransaction();"],
        should_pass=[
            "isolation.level=read_committed\nproducer.initTransactions();",
        ],
    ),
    Rule(
        id="KL020",
        summary="cache-TTL deduplication presented as sufficient idempotency",
        kind="block_require",
        # The warning must live in the SAME code block as the snippet. Prose two
        # paragraphs down explaining the race does not stop a reader copying a
        # block captioned "recommended" (mutation M23 survived on that gap).
        block_a=_rx(r"cache\.(?:Exists|Get)\(.{0,60}?processed"),
        block_b=_rx(r"NOT\s+SAFE|not\s+safe|race|do\s+not\s+use|check-then-act|WRONG"),
        message=(
            "Exists-then-Set is a check-then-act race, breaks on crash between "
            "side effect and Set, and expires with the TTL. The code block must "
            "carry the warning, not just the surrounding prose."
        ),
        should_fire=[
            "```go\n"
            'if processed, _ := cache.Exists(ctx, "processed:"+event.EventID); processed {\n'
            "    return nil\n}\n```\n\nThe race is explained at length further down.\n"
        ],
        should_pass=[
            "```go\n// NOT SAFE as a correctness mechanism — shown to explain why.\n"
            'if processed, _ := cache.Exists(ctx, "processed:"+ev.EventID); processed {\n'
            "    return nil\n}\n```\n"
        ],
    ),
    Rule(
        id="KL021",
        summary="DLQ publish result discarded before advancing the offset",
        kind="require",
        trigger=_rx(r"^\s*producer\.SendMessage\(\s*dlq\w*\s*\)\s*$"),
        expect=_rx(r"if\s+_?,?\s*_?,?\s*err\s*:?=\s*producer\.SendMessage"),
        message=(
            "Committing past a message whose DLQ publish failed deletes it. "
            "Check the publish error before advancing the offset."
        ),
        should_fire=["        producer.SendMessage(dlqMsg)\n        return nil\n"],
        should_pass=[
            "if _, _, err := producer.SendMessage(dlqMsg); err != nil {\n"
            "    return err\n}\n"
        ],
    ),
]


def scan_text(text: str, path: str, rules: list[Rule] | None = None) -> list[Finding]:
    rules = rules if rules is not None else RULES
    masked = mask(text)
    findings: list[Finding] = []
    for rule in rules:
        if rule.scope and not rule.scope.search(path):
            continue
        if rule.kind in ("block", "block_require"):
            assert rule.block_a is not None and rule.block_b is not None
            for blk in FENCE.finditer(masked):
                body = blk.group("body")
                if "\x00" in body:
                    continue
                ma, mb = rule.block_a.search(body), rule.block_b.search(body)
                if not ma:
                    continue
                if rule.kind == "block" and not mb:
                    continue
                if rule.kind == "block_require" and mb:
                    continue
                offset = blk.start("body") + ma.start()
                line = masked.count("\n", 0, offset) + 1
                excerpt = ma.group(0).strip()
                if rule.kind == "block" and mb:
                    excerpt = f"{excerpt} + {mb.group(0).strip()}"
                findings.append(Finding(rule.id, path, line, rule.message, excerpt[:160]))
        elif rule.kind == "forbid":
            assert rule.pattern is not None
            for m in rule.pattern.finditer(masked):
                if "\x00" in m.group(0):
                    continue
                if rule.unless and rule.unless.search(m.group(0)):
                    continue
                if _refuted(masked, m.start(), m.end()):
                    continue
                line = masked.count("\n", 0, m.start()) + 1
                findings.append(
                    Finding(rule.id, path, line, rule.message, m.group(0).strip()[:160])
                )
        else:
            assert rule.trigger is not None and rule.expect is not None
            for m in rule.trigger.finditer(masked):
                if "\x00" in m.group(0):
                    continue
                if rule.window == "line":
                    lo = masked.rfind("\n", 0, m.start()) + 1
                    hi = masked.find("\n", m.end())
                    hi = len(masked) if hi == -1 else hi
                else:
                    assert isinstance(rule.window, int)
                    lo = max(0, m.start() - rule.window)
                    hi = min(len(masked), m.end() + rule.window)
                if rule.expect.search(masked[lo:hi]):
                    continue
                line = masked.count("\n", 0, m.start()) + 1
                findings.append(
                    Finding(rule.id, path, line, rule.message, m.group(0).strip()[:160])
                )
    return findings


def default_targets() -> list[pathlib.Path]:
    targets = [SKILL_DIR / "SKILL.md"]
    targets += sorted((SKILL_DIR / "references").glob("*.md"))
    return [p for p in targets if p.exists()]


def selftest() -> int:
    failures = 0
    for rule in RULES:
        if not rule.should_fire or not rule.should_pass:
            print(f"SELFTEST FAIL {rule.id}: missing should_fire/should_pass cases")
            failures += 1
            continue
        path = "SKILL.md"  # satisfies scoped rules
        for sample in rule.should_fire:
            if not scan_text(sample, path, [rule]):
                print(f"SELFTEST FAIL {rule.id}: did NOT fire on {sample[:70]!r}")
                failures += 1
        for sample in rule.should_pass:
            got = scan_text(sample, path, [rule])
            if got:
                print(f"SELFTEST FAIL {rule.id}: false positive on {sample[:70]!r}")
                failures += 1
    total_cases = sum(len(r.should_fire) + len(r.should_pass) for r in RULES)
    if failures:
        print(f"\nselftest: {failures} failure(s) across {len(RULES)} rules")
        return 1
    print(f"selftest: {len(RULES)} rules, {total_cases} cases, all pass")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="*", help="files to scan (default: skill docs)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)

    if args.list:
        for rule in RULES:
            print(f"{rule.id}  [{rule.kind:7}]  {rule.summary}")
        return 0
    if args.selftest:
        return selftest()

    targets = [pathlib.Path(p) for p in args.paths] or default_targets()
    findings: list[Finding] = []
    for path in targets:
        findings += scan_text(path.read_text(encoding="utf-8"), str(path))

    for f in sorted(findings, key=lambda x: (x.path, x.line)):
        rel = f.path.replace(str(SKILL_DIR) + "/", "")
        print(f"{rel}:{f.line}: [{f.rule}] {f.message}\n    > {f.excerpt}")
    print(f"\n{len(findings)} finding(s) across {len(targets)} file(s), {len(RULES)} rules")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""Mutation sweep: prove the regression suite fails when a claim is inverted.

A green test suite means nothing until you show it can go red for the right
reason. The motivating failure for this file: an earlier version of this skill
passed 91/91 tests after its core rules were rewritten to say the opposite
("never use acks=all; prefer acks=1"). Every test asserted that a *keyword* was
present, and inverted advice contains the same keywords.

Each mutation below edits a real skill document, then asserts a specific linter
rule fires. A mutation that survives means that claim is undefended — the fix is
a new rule, never a weaker mutation.

Rules of the harness, learned from previous sweeps:
  * Replace **all** occurrences. Leaving one original copy behind lets a rule
    fire on the untouched line, so the mutation looks killed when it is not.
  * A mutation whose `old` text is not found is a HARNESS ERROR, not a pass —
    the doc was reworded and the mutation is now testing nothing.
  * Killing requires the *expected* rule id, not merely a non-zero exit.

Usage:
    python3 mutation_sweep.py          # run every mutation
    python3 mutation_sweep.py -v       # show the finding that killed each one
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from dataclasses import dataclass

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import lint_kafka_docs as linter  # noqa: E402

SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Mutation:
    id: str
    target: str
    old: str
    new: str
    expect_rule: str
    note: str


MUTATIONS: list[Mutation] = [
    # ---- durability -------------------------------------------------------
    Mutation(
        "M01", "SKILL.md",
        "the target is `acks=all`",
        "never use `acks=all`; prefer acks=1 for critical events, the target is `acks=all`",
        "KL001",
        "The exact inversion that survived the previous 91/91 suite.",
    ),
    Mutation(
        "M02", "references/version-client-matrix.md",
        "**Gate rule**:",
        "Set acks=0 for throughput-sensitive topics.\n\n**Gate rule**:",
        "KL001",
        "acks=0 recommended in the version matrix.",
    ),
    Mutation(
        "M03", "SKILL.md",
        # Re-anchored when §8's Critical checklist was folded back into §5: the
        # tier lists were a second copy of the checklist and the copies had
        # already drifted. The mutation targets the surviving statement.
        "the target is `acks=all` + retries + `enable.idempotence=true`",
        "enable.idempotence=false is acceptable for most workloads",
        "KL002",
        "Idempotence downgrade smuggled into the Critical checklist item.",
    ),
    # ---- schema compatibility --------------------------------------------
    Mutation(
        "M04", "references/event-schema-patterns.md",
        "| `BACKWARD` (registry default) | **Delete fields**; add optional fields | Last version only | Consumers |",
        "| `BACKWARD` (registry default) | BACKWARD guarantees old consumers can read the new schema | Last version only | Producers |",
        "KL003",
        "Compatibility direction inverted in the summary table.",
    ),
    Mutation(
        "M05", "references/event-schema-patterns.md",
        "- **BACKWARD does allow deleting a field.**",
        "- Under BACKWARD you must not delete existing fields.",
        "KL004",
        "Re-introduces the add-only myth.",
    ),
    Mutation(
        "M06", "SKILL.md",
        "`BACKWARD` is the registry default and defensible.",
        "BACKWARD_TRANSITIVE is safest for most cases.",
        "KL005",
        "Restores the unconditional transitive recommendation.",
    ),
    # ---- partitioning -----------------------------------------------------
    Mutation(
        "M07", "SKILL.md",
        "**Null key ≠ round-robin.**",
        "Null key means round-robin across partitions.",
        "KL006",
        "Restores the round-robin claim (also tests the refutation guard).",
    ),
    Mutation(
        "M08", "SKILL.md",
        "**High key cardinality does not create partitions.**",
        "Avoid high-cardinality unbounded keys (too many partitions).",
        "KL007",
        "Restores the cardinality/partition-count confusion.",
    ),
    Mutation(
        "M09", "references/event-schema-patterns.md",
        # Replace the WHOLE row. A partial edit left "Kafka cannot know the shards
        # are related" in the same cell, so the row refuted its own mutated claim
        # and the mutation looked like a rule gap when it was a weak mutation.
        "| Sharded key (`hotkey:{n}` for n in 0..N) | **No** | Kafka cannot know "
        "the shards are related. Valid only when the consumer tolerates unordered "
        "events for that entity, or re-sequences them itself using a sequence "
        "number. Do not describe this as preserving ordering. |",
        "| Sharded key (`hotkey:{n}` for n in 0..N) | **Yes** | Sharding preserves "
        "per-entity ordering while spreading the load. |",
        "KL008",
        "Claims sharding keeps ordering.",
    ),
    Mutation(
        "M10", "SKILL.md",
        "**Global ordering has no fixed events/sec threshold.**",
        "Global ordering with a single partition is fine below <100 events/sec.",
        "KL009",
        "Restores the fabricated throughput threshold.",
    ),
    Mutation(
        "M11", "references/consumer-anti-examples.md",
        "2. If global ordering is genuinely required, derive the ceiling instead of",
        "2. Single partition is acceptable when throughput is low (<500 events/sec), so",
        "KL009",
        "Same fabrication in the extended anti-examples.",
    ),
    # ---- transactions / outbox -------------------------------------------
    Mutation(
        "M12", "SKILL.md",
        "**Database → Kafka**: the **outbox pattern**",
        "Use Kafka transactions so the database write and the outbox row commit atomically. Also: the outbox pattern",
        "KL010",
        "Puts the DB write inside a Kafka transaction.",
    ),
    Mutation(
        "M13", "references/event-schema-patterns.md",
        "**Does not guarantee exactly-once.**",
        "The outbox pattern guarantees exactly-once delivery.",
        "KL011",
        "Overclaims outbox delivery semantics.",
    ),
    Mutation(
        "M14", "references/consumer-failure-modes.md",
        "producer.sendOffsetsToTransaction(offsets(records), consumer.groupMetadata());",
        "producer.sendOffsetsToTransaction(offsets(records), consumerGroupId);",
        "KL012",
        "Restores the API overload removed in Kafka 4.x.",
    ),
    Mutation(
        "M15", "references/consumer-failure-modes.md",
        "isolation.level=read_committed     # default is read_uncommitted",
        "# (isolation level omitted)",
        "KL019",
        "Drops the consumer half of exactly-once.",
    ),
    # ---- absolutism -------------------------------------------------------
    Mutation(
        "M16", "SKILL.md",
        "**A defined, owned policy for unprocessable messages**",
        "Every consumer must have a DLQ",
        "KL013",
        "Restores DLQ as an unconditional Critical rule.",
    ),
    Mutation(
        "M17", "references/event-schema-patterns.md",
        "**Raw JSON (no registry)** is a risk position, not an automatic defect.",
        "Raw JSON (no schema) only for prototyping — unacceptable in production.",
        "KL014",
        "Restores the categorical raw-JSON ban.",
    ),
    Mutation(
        "M18", "SKILL.md",
        "**Replication factor sized to the durability requirement**",
        "Replication factor must always be >= 3. RF=1 is unacceptable for any non-ephemeral data.",
        "KL015",
        "Restores unconditional RF>=3.",
    ),
    # ---- client / version facts ------------------------------------------
    Mutation(
        "M19", "references/version-client-matrix.md",
        "So on the Java client, `max.in.flight=5` + `enable.idempotence=true` **preserves\nordering**.",
        "Idempotence requires in-flight = 1 on every client.",
        "KL016",
        "Restores the max.in.flight=1 folklore as a general rule.",
    ),
    Mutation(
        "M20", "SKILL.md",
        "| **Kafka version** (2.x / 3.x / 4.x)",
        "| **Kafka version** (2.x / 3.x)",
        "KL017",
        "Reverts the version model to pre-4.x.",
    ),
    Mutation(
        "M21", "references/consumer-failure-modes.md",
        "#### Classic protocol (`group.protocol=classic` — the default through Kafka 4.x)",
        "#### Assignor configuration",
        "KL018",
        "Removes the protocol qualification from the assignor advice.",
    ),
    Mutation(
        "M22", "references/consumer-failure-modes.md",
        "group.remote.assignor=uniform      # 'uniform' (default) or 'range'",
        "session.timeout.ms=45000",
        "KL022",
        "Sets a config that group.protocol=consumer disables.",
    ),
    # ---- idempotency ------------------------------------------------------
    # ---- content regressions found in review round 2 ----------------------
    Mutation(
        "M31", "references/event-schema-patterns.md",
        "#### Compaction destroys an event-sourced log. Use two topics.",
        "#### Event sourcing requires compacted topics or infinite retention.",
        "KL023",
        "Compaction on a log keyed by aggregate ID deletes the history.",
    ),
    Mutation(
        "M32", "references/consumer-failure-modes.md",
        "**Derive the alert threshold; do not copy one.**",
        "Alert: lag > 10000 messages sustained for > 5 minutes.",
        "KL024",
        "Fixed lag threshold contradicts the skill's own no-fabricated-numbers rule.",
    ),
    Mutation(
        "M33", "references/consumer-failure-modes.md",
        "# Stable identity: a restart that completes within session.timeout.ms rejoins\n"
        "# as the same member and keeps its partitions, so no rebalance is triggered.",
        "# Assign a stable identity — consumer restarts don't trigger rebalance",
        "KL025",
        "Static membership only covers restarts inside session.timeout.ms.",
    ),
    # ---- adversarial paraphrase -------------------------------------------
    # An external review defeated an earlier refutation guard by pairing the
    # wrong advice with a refutation of the OPPOSITE claim in the same sentence.
    # Every form below scored zero findings before the guard was bound to the
    # matched proposition; each is now a permanent mutation.
    Mutation(
        "M25", "SKILL.md",
        "the target is `acks=all` + retries + `enable.idempotence=true`",
        "acks=all is wrong; prefer acks=1 for critical events",
        "KL001",
        "Refutation of the opposite claim, same sentence, semicolon-separated.",
    ),
    Mutation(
        "M26", "SKILL.md",
        "**A defined, owned policy for unprocessable messages**",
        "That myth is wrong, but every consumer must have a DLQ",
        "KL013",
        "Refutation before a contrastive conjunction.",
    ),
    Mutation(
        "M27", "SKILL.md",
        "`BACKWARD` is the registry default and defensible.",
        "The old guidance was wrong. However, BACKWARD_TRANSITIVE is safest for most cases.",
        "KL005",
        "Refutation in the PRECEDING sentence.",
    ),
    Mutation(
        "M28", "SKILL.md",
        "**Null key ≠ round-robin.**",
        "Round-robin is not used; null key means round-robin across partitions.",
        "KL006",
        "Pattern must not span the clause break and inherit its negation.",
    ),
    Mutation(
        "M29", "references/event-schema-patterns.md",
        "| Sharded key (`hotkey:{n}` for n in 0..N) | **No** | Kafka cannot know "
        "the shards are related. Valid only when the consumer tolerates unordered "
        "events for that entity, or re-sequences them itself using a sequence "
        "number. Do not describe this as preserving ordering. |",
        "| Sharded key | ? | Sharding is not free; instead, sharding preserves "
        "per-entity ordering. |",
        "KL008",
        "Refutation attached to a different predicate of the same subject.",
    ),
    Mutation(
        "M30", "references/version-client-matrix.md",
        "**Gate rule**:",
        "That claim is wrong. Set acks=0 for throughput.\n\n**Gate rule**:",
        "KL001",
        "Refutation in its own sentence must not cover the next one.",
    ),
    Mutation(
        "M23", "references/event-schema-patterns.md",
        "// NOT SAFE as a correctness mechanism — shown to explain why.",
        "// Recommended application-level deduplication.",
        "KL020",
        "Presents cache-TTL dedup as a correctness mechanism.",
    ),
    Mutation(
        "M24", "references/consumer-failure-modes.md",
        "    if _, _, err := producer.SendMessage(dlqMsg); err != nil {",
        "    producer.SendMessage(dlqMsg)\n    if false {",
        "KL021",
        "Discards the DLQ publish error before the offset advances.",
    ),
    Mutation(
        "M34", "references/event-schema-patterns.md",
        "| **Protobuf** | Confluent | Excellent | Binary, compact | No |",
        "| **Protobuf** | Confluent | Excellent | Fastest | No |",
        "KL026",
        "Restores the unmeasured 'Protobuf is fastest' ranking the table shipped with.",
    ),
]


def run(verbose: bool) -> int:
    killed, survived, harness_errors = [], [], []

    # A rule with no mutation behind it is an untested rule. Reported here rather
    # than left for a reader to notice, because "33/33 killed" reads as full
    # coverage even when a newly added rule was never exercised.
    unmutated = sorted({r.id for r in linter.RULES}
                       - {m.expect_rule for m in MUTATIONS})
    stale = sorted({m.expect_rule for m in MUTATIONS}
                   - {r.id for r in linter.RULES})

    for mut in MUTATIONS:
        path = SKILL_DIR / mut.target
        original = path.read_text(encoding="utf-8")

        count = original.count(mut.old)
        if count == 0:
            harness_errors.append(
                (mut, "anchor text not found — doc reworded, mutation tests nothing")
            )
            continue

        # Replace ALL occurrences: a surviving original copy can satisfy the
        # rule on its own and make a live mutation look killed.
        mutated = original.replace(mut.old, mut.new)
        findings = linter.scan_text(mutated, mut.target)
        hits = [f for f in findings if f.rule == mut.expect_rule]

        if hits:
            killed.append((mut, hits[0], count))
            if verbose:
                print(f"  {mut.id} KILLED by {hits[0].rule} @ line {hits[0].line}"
                      f" ({count} occurrence(s) mutated)")
        else:
            survived.append((mut, findings))

    print(f"\nmutations: {len(MUTATIONS)}  killed: {len(killed)}  "
          f"survived: {len(survived)}  harness errors: {len(harness_errors)}  "
          f"rules without a mutation: {len(unmutated)}")

    if unmutated:
        print("NO MUTATION COVERAGE: " + ", ".join(unmutated)
              + "\n    Each rule needs one mutation that inverts a real doc claim.")
    if stale:
        print("MUTATION TARGETS A DELETED RULE: " + ", ".join(stale))

    for mut, reason in harness_errors:
        print(f"HARNESS ERROR {mut.id} ({mut.target}): {reason}\n"
              f"    anchor: {mut.old[:90]!r}")
    for mut, findings in survived:
        other = ", ".join(sorted({f.rule for f in findings})) or "nothing"
        print(f"SURVIVED {mut.id} ({mut.target}): expected {mut.expect_rule}, got {other}\n"
              f"    {mut.note}")

    return 0 if not (survived or harness_errors or unmutated or stale) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    return run(args.verbose)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Independent paraphrase corpus for the semantic linter.

WHY THIS IS SEPARATE FROM mutation_sweep.py
-------------------------------------------
A mutation takes a sentence out of the shipped docs and inverts it. That proves
the rule catches *the phrasing the doc already uses*, which is the phrasing the
rule was written against — a closed loop. Three natural restatements slipped
through a fully green 33-mutation sweep:

    "Use cleanup.policy=compact for an event-sourced aggregate log."
    "Alert whenever lag exceeds 10000 messages."
    "Static membership prevents rebalances during restarts."

None of them share wording with the doc, and all three assert something the
skill declares wrong. So this corpus is written the other way round: start from
the *proposition*, write how an engineer would actually say it (and how they
would say the correct thing), and require the rule to separate them.

WHAT A GREEN RUN DOES AND DOES NOT LICENSE
------------------------------------------
Zero missed detections here means the rules catch **these** restatements. It is a
record of known regressions, not a measurement of semantic coverage, and it must
never be reported as one. Every entry below arrived the same way — a reviewer
wrote a sentence nobody had regexed for, and it walked straight through a fully
green suite. Four did so as recently as the round that added the last batch:

    "The event history topic belongs on cleanup.policy=compact."      (KL023)
    "Page when consumer lag reaches ten thousand records."            (KL024)
    "Static membership guarantees rolling deployments will not
     rebalance the group."                                            (KL025)
    "Protobuf gives the highest throughput of the registry formats."  (KL026)

A fifth turned up while writing an unrelated probe for the model-eval grader —
an anaphoric key reference, which every literal "without a key" form missed:

    "Set a partition key to preserve ordering — without one, records
     are spread round-robin over the partitions."                     (KL006)

Each was fixed and pinned here, which raises the floor and proves nothing about
the next paraphrase. Treat the linter as a known-regression detector: a finding
is real, silence is not a clearance. The semantic verdict belongs to a reviewer,
and to `model_eval.py` for whether a model applies the rules it is given.

Rules for adding entries:

* Write the paraphrase FIRST, then check the rule. If you write it by reading
  the regex, you have re-created the closed loop.
* Every rule needs both polarities. A `quiet` entry that merely omits the topic
  proves nothing — it must state the CORRECT claim about the same subject, so a
  rule that fires on any mention of the topic fails here.
* When a rule is broadened to catch a miss, add a quiet probe for the sentence
  that *refutes* the claim. A guard that fires on "X is a myth because…" is a
  bypass: the doc can no longer say why X is wrong.
* Keep entries single-sentence and free of the doc's own phrasing.

Usage:
    python3 paraphrase_corpus.py          # run the corpus
    python3 paraphrase_corpus.py -v       # show every probe and its verdict
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import lint_kafka_docs as linter  # noqa: E402

# (rule_id, must_fire[], must_stay_quiet[])
CORPUS: list[tuple[str, list[str], list[str]]] = [
    ("KL001", [
        "For critical events we settle on acks=1 to keep latency down.",
        "Producers should be configured with acks=0 on this topic.",
        "acks=all is wrong; prefer acks=1 for critical events.",
        "Leader acknowledgement alone is enough here, so use acks=1.",
    ], [
        "acks=1 means the record is lost if the leader fails before replication.",
        "sarama ships with WaitForLocal, which is acks=1, so set WaitForAll explicitly.",
        "Kafka accepts acks values of 0, 1 and all.",
    ]),
    ("KL002", [
        "Turn off enable.idempotence to squeeze out more throughput.",
        "Running with enable.idempotence=false is acceptable for most workloads.",
    ], [
        "librdkafka leaves enable.idempotence at false, so set it explicitly.",
        "Idempotence is on by default from Kafka 3.0 onwards.",
    ]),
    ("KL003", [
        "Because the subject is BACKWARD, consumers on the previous schema can still parse newly produced records.",
        "BACKWARD compatibility lets existing readers handle the updated payload.",
    ], [
        "Under BACKWARD a consumer running the new schema can still read records written with the old one.",
        "FORWARD is what lets an old reader parse data written by a new producer.",
    ]),
    ("KL004", [
        "Since the subject is FULL, we can add fields but must never remove any.",
        "BACKWARD means fields can only ever be added, never deleted.",
    ], [
        "Removing a required field with no default is incompatible under every mode.",
        "A field with a default can be dropped without breaking BACKWARD.",
    ]),
    ("KL005", [
        "Default every subject to BACKWARD_TRANSITIVE — it is the safest option.",
        "BACKWARD_TRANSITIVE is safest for most cases.",
    ], [
        "Reach for BACKWARD_TRANSITIVE when readers can lag several schema versions behind.",
        "The registry defaults new subjects to BACKWARD.",
    ]),
    ("KL006", [
        "Leaving the key unset makes the producer round-robin records over the partitions.",
        "Records without a key are distributed round-robin.",
        "Round-robin is not used; null key means round-robin across partitions.",
        "Set a partition key to preserve ordering — without one, records are spread round-robin over the partitions.",
        "When the key is omitted the producer sends round-robin.",
    ], [
        "Leaving the key unset costs you per-key ordering.",
        "Null-key records land in batch-sticky runs rather than one partition each.",
        "RoundRobinPartitioner has to be selected explicitly.",
        "Pick a key for every topic that needs ordering. Without one you still cannot assume round-robin placement.",
    ]),
    ("KL007", [
        "Keys with very high cardinality end up creating too many partitions.",
        "Avoid unbounded key cardinality or you will spawn excessive partitions.",
    ], [
        "Partition count is fixed on the topic; the key is only hashed against it.",
        "Skew comes from too few effective keys, not too many.",
    ]),
    ("KL008", [
        "Appending a shard suffix to the hot key keeps per-entity ordering while spreading load.",
        "Sharding the key preserves ordering and fixes the hot partition.",
    ], [
        "A shard suffix gives up Kafka-native ordering for that entity.",
        "A composite tenant:entity key keeps the entity ordered while spreading the tenant.",
    ]),
    ("KL009", [
        "A single partition is fine as long as you stay under 100 events/sec.",
        "Global ordering works up to roughly 500 messages per second.",
    ], [
        "Derive the single-partition ceiling from p99 processing time.",
        "One partition caps you at what a single consumer instance can process.",
    ]),
    ("KL010", [
        "Wrap the row insert and the produce call in a Kafka transaction so they commit together.",
        "Use Kafka transactions so the database write and the event are atomic.",
    ], [
        "A Kafka transaction spans Kafka partitions and offsets, never a database row.",
        "The outbox row is written in the same database transaction as the business rows.",
    ]),
    ("KL011", [
        "The outbox relay gives you exactly-once publishing.",
        "With an outbox you get exactly-once delivery end to end.",
    ], [
        "The relay publishes at least once, because marking published is a second commit.",
        "Consumers still need dedup even with an outbox in front.",
    ]),
    ("KL012", [
        "producer.sendOffsetsToTransaction(offsets, consumerGroupId);",
        "call sendOffsetsToTransaction(pending, groupId) before committing",
    ], [
        "producer.sendOffsetsToTransaction(offsets, consumer.groupMetadata());",
        "The surviving overload takes ConsumerGroupMetadata.",
    ]),
    ("KL013", [
        "Every consumer must have a DLQ.",
        "A dead-letter topic is mandatory on all consumers without exception.",
    ], [
        "Decide and document what happens to a message that cannot be processed.",
        "On a ledger topic, halting and paging beats parking the message.",
    ]),
    ("KL014", [
        "Raw JSON without a registry is unacceptable in production.",
        "Schema-less JSON must never be used in production topics.",
    ], [
        "Raw JSON is defensible when the contract is enforced elsewhere and consumers validate.",
        "Score the absence of contract enforcement rather than the absence of a registry.",
    ]),
    ("KL015", [
        "RF=1 is unacceptable for any non-ephemeral data.",
        "Replication factor must always be >= 3, no exceptions.",
    ], [
        "RF below 3 is a WARN when the topic is a rebuildable projection with a named owner.",
        "min.insync.replicas only takes effect when the producer uses acks=all.",
    ]),
    ("KL016", [
        "Keep max.in.flight.requests.per.connection=1 so ordering holds.",
        "Idempotence requires in-flight = 1.",
    ], [
        "Idempotence preserves ordering for any in-flight value up to five.",
        "sarama is the exception: Net.MaxOpenRequests must be 1 when Idempotent is set.",
    ]),
    ("KL023", [
        "Use cleanup.policy=compact for an event-sourced aggregate log.",
        "Event sourcing needs a compacted topic to retain state.",
        "Set the event log to compact so history is kept forever.",
        "For event sourcing, configure compaction on the aggregate topic.",
        "The event history topic belongs on cleanup.policy=compact.",
        "The aggregate journal should be set to compact.",
    ], [
        "Compaction keeps only the newest record per key, which erases an aggregate's history.",
        "Keep the event log on cleanup.policy=delete and compact a separate snapshot topic.",
        "Entity-state topics are the ones that should be compacted.",
    ]),
    ("KL024", [
        "Alert whenever lag exceeds 10000 messages.",
        "Page the team when consumer lag goes above 5000 records.",
        "# Alert: lag > 10000 messages sustained for > 5 minutes",
        "  expr: kafka_consumergroup_lag > 25000",
        "Page when consumer lag reaches ten thousand records.",
        "Escalate once lag tops fifty thousand events.",
    ], [
        "Alert on time-to-drain, computed as records_lag_max over records_consumed_rate.",
        "Thousands of aborted records can sit in the log without indicating a stalled consumer.",
        "Derive the lag threshold from the freshness the downstream consumer promised.",
        "Lag is the difference between the log end offset and the committed offset.",
    ]),
    # Structural rules (KL017-KL022) key on config-file / code shape rather than
    # prose, so a "paraphrase" is a differently-written config block.
    ("KL017", [
        "| **Kafka version** (2.x / 3.x) | defaults and protocols differ | ask |",
        "| **Kafka version** (2.x or 3.x) | which broker line are you on |",
    ], [
        "| **Kafka version** (2.x / 3.x / 4.x) | defaults flipped at 3.0 |",
        "| **Kafka version** (2.8 / 3.x / 4.3) | KRaft-only from 4.0 |",
    ]),
    ("KL020", [
        "```go\nif seen, _ := cache.Exists(ctx, \"processed:\"+id); seen {\n    return nil\n}\n```",
    ], [
        "```go\n// NOT SAFE — shown to explain the race.\n"
        "if seen, _ := cache.Exists(ctx, \"processed:\"+id); seen {\n    return nil\n}\n```",
    ]),
    ("KL018", [
        "partition.assignment.strategy=org.apache.kafka.clients.consumer.CooperativeStickyAssignor",
    ], [
        "Classic protocol only: partition.assignment.strategy=org.apache.kafka.clients.consumer.CooperativeStickyAssignor",
    ]),
    ("KL019", [
        "producer.initTransactions();\nproducer.beginTransaction();",
    ], [
        "isolation.level=read_committed\nproducer.initTransactions();",
    ]),
    ("KL021", [
        "        producer.SendMessage(dlqMsg)\n        session.MarkMessage(msg, \"\")\n",
    ], [
        "if _, _, err := producer.SendMessage(dlqMsg); err != nil {\n    return err\n}\n",
    ]),
    ("KL022", [
        "```properties\nsession.timeout.ms=45000\ngroup.protocol=consumer\n```",
        "```properties\ngroup.protocol=consumer\nheartbeat.interval.ms=3000\n```",
    ], [
        "```properties\ngroup.protocol=consumer\ngroup.remote.assignor=range\n```",
    ]),
    ("KL025", [
        "Static membership prevents rebalances during restarts.",
        "With group.instance.id set, restarts never trigger a rebalance.",
        "A static member can restart without causing the group to rebalance.",
        "Setting a static id removes rebalancing on rolling deploys.",
        "Static membership guarantees rolling deployments will not rebalance the group.",
        "group.instance.id ensures a rolling deploy never rebalances the group.",
    ], [
        "A static member avoids a rebalance only if it returns inside session.timeout.ms.",
        "Static membership only avoids a rebalance for a restart that finishes inside session.timeout.ms.",
        "Static membership buys a window; past the session timeout the coordinator still evicts it.",
        "group.instance.id must stay stable across restarts to be worth anything.",
        "Static membership does not guarantee that a rolling deploy will not rebalance.",
    ]),
    # The quiet side deliberately keeps "Avro is faster than raw JSON": ranking a
    # binary format above a text one is a property of the encoding and must stay
    # sayable. Only Avro-vs-Protobuf is the unmeasurable claim.
    ("KL026", [
        "Protobuf serialises quicker than Avro, so pick it for the hot path.",
        "For raw speed Avro is the fastest of the registry formats.",
        "We chose Protobuf because it beats Avro on throughput.",
        "Avro outperforms Protobuf in every benchmark we have seen.",
        "Protobuf gives the highest throughput of the registry formats.",
        "For best performance among the registry formats, choose Avro.",
    ], [
        "Treat Avro and Protobuf as equivalent on speed and measure your own payload.",
        "Whether Avro or Protobuf wins depends on the client library and payload shape.",
        "Avro and Protobuf are both binary and far cheaper on the wire than JSON Schema.",
        "Avro is faster than raw JSON because the encoding is binary.",
        "Size the partition count from the topic's highest sustained throughput.",
    ]),
]


def run(verbose: bool) -> int:
    missed: list[tuple[str, str, str]] = []
    false_pos: list[tuple[str, str, str]] = []
    n = 0

    for rule_id, fire, quiet in CORPUS:
        for probe in fire:
            n += 1
            hits = {f.rule for f in linter.scan_text(probe, "SKILL.md")}
            if rule_id not in hits:
                missed.append((rule_id, probe, ", ".join(sorted(hits)) or "nothing"))
            elif verbose:
                print(f"  FIRE  {rule_id}  {probe[:72]}")
        for probe in quiet:
            n += 1
            hits = {f.rule for f in linter.scan_text(probe, "SKILL.md")}
            if rule_id in hits:
                false_pos.append((rule_id, probe, ", ".join(sorted(hits))))
            elif verbose:
                print(f"  quiet {rule_id}  {probe[:72]}")

    covered = {r for r, _, _ in CORPUS}
    all_rules = {r.id for r in linter.RULES}
    uncovered = sorted(all_rules - covered)

    print(f"\nparaphrase corpus: {n} probes over {len(CORPUS)} rules  "
          f"missed: {len(missed)}  false positives: {len(false_pos)}")
    for rule_id, probe, got in missed:
        print(f"MISSED {rule_id}: {probe!r}\n    linter reported: {got}")
    for rule_id, probe, got in false_pos:
        print(f"FALSE POSITIVE {rule_id}: {probe!r}\n    linter reported: {got}")
    if uncovered:
        print(f"NOT PARAPHRASE-COVERED: {', '.join(uncovered)} "
              f"(structural rules; covered by selftest + mutations only)")

    return 0 if not missed and not false_pos else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-v", "--verbose", action="store_true")
    return run(ap.parse_args().verbose)


if __name__ == "__main__":
    sys.exit(main())

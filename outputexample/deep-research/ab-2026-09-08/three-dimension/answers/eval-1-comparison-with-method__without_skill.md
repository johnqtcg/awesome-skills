# PostgreSQL Logical Replication vs. Debezium for Streaming Orders DB Changes to Kafka

**Prepared for:** tech lead review
**Question:** how do we stream row-level changes out of the orders database into Kafka — using PostgreSQL's native logical replication directly, or Debezium (Kafka Connect based CDC)?
**Method note:** compiled from vendor/official documentation and independent technical sources via live web search on 2026-09-08. Every claim below is footnoted to its source; see the Sources list at the end for full URLs. I have not run these two setups myself against your orders schema — validate the WAL-growth and TOAST behavior against your actual table shapes before committing.

---

## 0. Framing the decision correctly

These two things are not peers — one is a database feature, the other is a packaged tool built on top of that feature. Getting this framing right matters for the recommendation.

- **PostgreSQL logical replication** is the *mechanism*: it decodes the Write-Ahead Log (WAL) into a stream of row-level INSERT/UPDATE/DELETE events via a replication slot, using an output plugin (`pgoutput` is the only one built into core Postgres 10+; `wal2json` is a separate installable extension that emits JSON instead of a compact binary protocol) [PostgreSQL 18 Docs — Logical Replication][pg-restrictions][streamkap-internals]. Out of the box, this mechanism is designed to feed a `CREATE SUBSCRIPTION` on **another PostgreSQL database** — it does not write to Kafka by itself.
- To get from a replication slot to a Kafka topic, you need something consuming the replication protocol and producing to Kafka. There are exactly two ways to do that:
  1. **Debezium** — a mature, open-source (Apache 2.0) CDC connector that speaks `pgoutput`/`wal2json`, normalizes changes into a structured event envelope, and (most commonly) runs inside a Kafka Connect cluster to publish to Kafka [Debezium Architecture Docs][debezium-arch][debezium-license].
  2. **Build it yourself** — use `pg_recvlogical` or a client library (Go/Python/Java all have libpq replication-mode support) to read the slot directly and write your own Kafka producer, handling LSN checkpointing, schema-change detection, and TOAST edge cases yourself [MVP Factory — CDC without Debezium][mvpfactory-nodebezium].

So the real-world choice for "logical replication vs. Debezium" is almost always: **adopt Debezium's packaged connector, or roll a thinner custom consumer on top of the same underlying logical replication feature.** The rest of this document evaluates both paths, because a tech lead comparing "just use logical replication" against Debezium is implicitly asking whether the custom-build path is worth it.

---

## 1. Recommendation (up front)

**Use Debezium**, deployed either via a Kafka Connect cluster (if you already run one) or via Debezium Server for a lighter footprint, unless your orders pipeline has exactly one downstream consumer, zero need for schema evolution, and you have strong in-house Kafka Connect expertise already available. Rationale, in order of weight:

1. Orders data almost always needs schema evolution over time (new columns, new order states) and Debezium's schema history topic + event envelope handles this as a first-class feature; native logical replication explicitly does not replicate DDL at all — schema changes on the subscriber side must be applied by hand [pg-restrictions].
2. Debezium already solves the two hardest correctness problems in this space — TOASTed (large/off-page) column values going missing from UPDATE events, and safe schema versioning per event — problems a hand-rolled consumer will hit and have to solve independently [debezium-toast-blog][debezium-schema-evolution].
3. The operational cost most teams actually pay for Debezium is running Kafka Connect (or Kafka itself), not Debezium's own logic — and if you're "streaming into Kafka" you're paying that Kafka operational cost either way, custom build or not [debezium-alternatives-estuary].
4. A custom `pg_recvlogical`-based consumer removes the Kafka Connect layer but reintroduces exactly the problems Debezium already ships fixes for (slot/LSN checkpointing, restart-safety, schema drift, TOAST handling) — reasonable only if you truly have a single simple consumer and want to avoid Kafka Connect specifically, e.g. by publishing straight to Kafka's producer API [mvpfactory-nodebezium].

If your actual choice is "Debezium vs. a managed CDC SaaS (Fivetran/Airbyte/Estuary/Streamkap)" rather than vs. hand-rolled logical replication, that's a different trade (cost/ops vs. control) — flag that to me separately if it's the real question, since this document doesn't do that comparison justice.

---

## 2. Side-by-side comparison

| Dimension | Native logical replication (roll-your-own to Kafka) | Debezium (Kafka Connect or Debezium Server) |
|---|---|---|
| What it actually is | A Postgres WAL-decoding primitive + replication slot; you write the Kafka producer | A packaged CDC connector built on top of logical replication, normalizes events, ships to Kafka |
| Underlying transport | `pgoutput` (binary, built-in) or `wal2json` (JSON, extension) [streamkap-internals] | Same — Debezium uses `pgoutput` as its supported plugin for the PostgreSQL connector [confluent-debezium-pg] |
| Gets you to Kafka out of the box | No — requires custom producer code | Yes — Kafka Connect source connector, or Debezium Server for non-Connect sinks (Kinesis, Pub/Sub, Pulsar, JDBC, or Kafka) [decodable-server-engine][debezium-server-github] |
| DDL / schema changes | **Not replicated at all.** Schema must be kept in sync manually; PostgreSQL's own docs state this explicitly [pg-restrictions] | Detected and versioned via an internal schema history Kafka topic; each event is tagged with the schema version active when it was captured [debezium-schema-evolution] |
| Sequences | Not replicated — subscriber-side sequence values must be reset manually on failover [pg-restrictions] | Not a Debezium concern per se (sequences aren't table row data), same underlying limitation applies if you need sequence values downstream |
| Large/TOASTed column values | You must handle missing unchanged-TOAST-value cases yourself when parsing `pgoutput`/`wal2json` | Handled: emits a `__debezium_unavailable_value` placeholder for unchanged TOAST columns under default `REPLICA IDENTITY`, or includes full values if you set `REPLICA IDENTITY FULL` (at a WAL-volume cost) [debezium-toast-blog] |
| Delivery guarantees | Whatever you implement — no guarantee without your own checkpointing logic | At-least-once by default; exactly-once achievable via Kafka Connect's KIP-618 support (distributed mode, Connect ≥3.3.0) [debezium-eos] |
| Ordering | Preserved per row only if you partition your own producer by primary key | Preserved per row: Debezium keys events by the source table's primary key by default, and Kafka guarantees order within a partition [educative-kafka-delivery] |
| Operational footprint | Lightest — a small consumer process + the Postgres slot itself; still need a WAL-bloat safety net | Kafka Connect requires a Kafka cluster, Connect workers, and (in Connect distributed mode) coordination — real infra to run and monitor; Debezium Server removes the Connect layer but you still run its runtime process [debezium-arch][olake-debezium-issues] |
| Multi-consumer fan-out | Not native — you'd design your own topic/consumer strategy | Native strength — one Kafka topic per table, any number of independent consumers, Single Message Transforms (SMTs) for filtering/routing/masking before it hits Kafka |
| Cloud-managed Postgres support (RDS/Aurora) | Same prerequisite either way: `rds.logical_replication=1`, tuned `wal_level`, `max_wal_senders`, `max_replication_slots`, and an instance reboot [aws-rds-logical-replication] | Same prerequisite, plus Debezium recommends `pgoutput` (not `wal2json`, which needs superuser-installed extensions RDS restricts) [debezium-rds-md] |
| WAL/disk risk if the consumer stalls | Same underlying risk in both cases — it's a property of the replication slot, not the consumer | Same underlying risk in both cases |
| Licensing / cost | Free (Postgres core feature); engineering cost is your own connector code | Apache 2.0, free; real cost is operating Kafka + Connect (or Debezium Server) at production scale — often comparable to a managed CDC platform once engineer time is counted [debezium-alternatives-estuary] |
| Best fit | Single, simple downstream consumer; team wants zero Kafka Connect footprint and will invest engineering time in a thin custom bridge | Multiple consumers, need for schema evolution/transformation, want a supported, widely-adopted tool with an existing ecosystem of Kafka Connect sink connectors |

---

## 3. Detail on the risks that matter most for an orders database

### 3.1 Replication slot WAL retention — applies to *both* approaches equally

A logical replication slot is how Postgres knows which WAL a consumer still needs. If the consumer (Debezium or your own code) stops consuming — crash, network partition, backpressure from Kafka — Postgres will not recycle the WAL behind that slot. The default retention is unbounded (`max_slot_wal_keep_size = -1`), so **a single stalled slot can fill your primary's disk and take down the orders database**, not just the replication feed [artie-slots][streamkap-slot-management]. This is a property of PostgreSQL logical replication itself, not something Debezium introduces or fixes — you need `max_slot_wal_keep_size` set to a bounded value (e.g. 100 GB) so a stalled slot is marked "lost" and the WAL is reclaimed rather than filling the disk, regardless of which consumer you choose [streamkap-slot-management]. Whoever owns this pipeline needs alerting on replication slot lag (`pg_stat_replication` / `pg_replication_slots`) day one.

### 3.2 Schema changes on an orders table

Orders schemas evolve — new payment methods, new fulfillment states, new columns for compliance fields. Native logical replication's official restriction is unambiguous: *"the database schema and DDL commands are not replicated ... subsequent schema changes would need to be kept in sync manually"* [pg-restrictions]. If you build your own consumer, every `ALTER TABLE orders ADD COLUMN ...` is a manual, coordinated deploy across producer and consumer. Debezium instead maintains a dedicated schema history Kafka topic recording every DDL statement it has observed, and tags every change event with the schema version active at capture time so downstream consumers can reconstruct the right shape per event [debezium-schema-evolution]. That schema-history topic must be configured for infinite retention (`cleanup.policy=delete`, `retention.ms=-1`) and never deleted — losing it forces a full re-snapshot [debezium-schema-evolution].

### 3.3 Large order payloads and TOAST

If any orders columns hold larger payloads (JSON line-items, notes, addresses) that PostgreSQL stores out-of-line via TOAST, plain logical replication messages **omit unchanged TOAST values from UPDATE events** unless that column is part of the table's replica identity [debezium-toast-blog]. A hand-rolled consumer must detect and handle this itself or silently produce incomplete UPDATE events to Kafka. Debezium already does: it either includes full before/after TOAST values when you set `REPLICA IDENTITY FULL` on the table (at a WAL-volume cost), or emits an explicit `__debezium_unavailable_value` marker so downstream consumers know a value was omitted rather than guessing it was nulled out [debezium-toast-blog].

### 3.4 Delivery and ordering guarantees you'll need for order events

For an orders stream, consumers (billing, fulfillment, analytics) generally need per-order ordering and no silently dropped events. Debezium provides at-least-once delivery by default, keys events by the source table's primary key so Kafka's per-partition ordering guarantee preserves per-row order, and can be upgraded to exactly-once delivery by running Kafka Connect in distributed mode on Connect ≥3.3.0 (KIP-618 support) [debezium-eos][educative-kafka-delivery]. Reproducing this — dedup, correct partition keying, restart-safe offset tracking — in a custom consumer is realistic but non-trivial engineering.

### 3.5 Amazon RDS/Aurora specifics (if orders DB is managed Postgres)

Both approaches require the same base enablement on RDS/Aurora: set `rds.logical_replication = 1` in the parameter group, size `wal_level`, `max_wal_senders`, `max_replication_slots`, `max_connections`, and reboot the instance [aws-rds-logical-replication]. Debezium's own RDS notes recommend the `pgoutput` plugin specifically on RDS because `wal2json` requires installing an extension, which RDS restricts more tightly [debezium-rds-md].

### 3.6 Operational footprint

Running Debezium the standard way means operating Kafka Connect — a distributed worker framework — on top of your Kafka cluster, or, if you don't already run Kafka Connect, adding it just for this [debezium-arch][olake-debezium-issues]. If that's unacceptable overhead, **Debezium Server** is worth evaluating: it's Debezium's engine wrapped in a standalone Quarkus-based runtime (JAR or container) that reads from Postgres and writes straight to a sink — including Kafka — with no Kafka Connect cluster required, at the cost of losing Connect's task distribution/HA and its sink-connector ecosystem [decodable-server-engine][debezium-server-github]. This is a middle ground worth considering if the real objection to Debezium is "we don't want to run Kafka Connect," not "we don't want Debezium."

---

## 4. What I did not verify

- I did not benchmark WAL growth, replication lag, or throughput against your actual orders table volumes/shapes — these numbers are workload-specific and the sources above are describing mechanisms and defaults, not your production numbers.
- I did not evaluate managed CDC SaaS platforms (Fivetran, Airbyte, Estuary, Streamkap, BladePipe) in depth; they were mentioned by sources only as alternatives to *both* options above and are out of scope for the question as asked.
- Debezium version referenced is the current stable line (3.6 as of this writing per the official docs site); confirm behavior against whatever version you'd actually pin.

---

## Sources

1. [PostgreSQL 18 Docs — Chapter 29.8, Logical Replication Restrictions](https://www.postgresql.org/docs/current/logical-replication-restrictions.html) — primary source, fetched directly; confirms DDL and sequences are not replicated. `[pg-restrictions]`
2. [Debezium Documentation — Architecture](https://debezium.io/documentation/reference/stable/architecture.html) — primary source, fetched directly; confirms Kafka Connect is the standard deployment model. `[debezium-arch]`
3. [Debezium Documentation — Exactly-once delivery](https://debezium.io/documentation/reference/stable/configuration/eos.html) — primary source, fetched directly; at-least-once default, KIP-618 exactly-once path. `[debezium-eos]`
4. [Debezium — License](https://debezium.io/license/) — Apache 2.0 licensing. `[debezium-license]`
5. [Debezium connector for PostgreSQL — Confluent Documentation](https://docs.confluent.io/kafka-connectors/debezium-postgres-source/current/overview.html) — snapshot + streaming behavior, `pgoutput` usage. `[confluent-debezium-pg]`
6. [Strategies for Handling Unchanged Postgres TOAST Values — Debezium blog](https://debezium.io/blog/2019/10/08/handling-unchanged-postgres-toast-values/) — TOAST/REPLICA IDENTITY behavior and `__debezium_unavailable_value` marker. `[debezium-toast-blog]`
7. [Handling Debezium Schema Evolution in Real-Time Pipelines — RisingWave](https://risingwave.com/blog/debezium-schema-evolution-streaming-pipelines/) and [A Note On Database History Topic Configuration — Debezium blog](https://debezium.io/blog/2018/03/16/note-on-database-history-topic-configuration/) — schema history topic mechanics and retention requirements. `[debezium-schema-evolution]`
8. [debezium/debezium-connector-postgres/RDS.md — GitHub](https://github.com/debezium/debezium/blob/main/debezium-connector-postgres/RDS.md) — RDS-specific plugin recommendation (`pgoutput` over `wal2json`). `[debezium-rds-md]`
9. [Performing logical replication for Amazon RDS for PostgreSQL — AWS Docs](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.Concepts.General.FeatureSupport.LogicalReplication.html) — `rds.logical_replication` and related parameter requirements. `[aws-rds-logical-replication]`
10. [PostgreSQL Replication Slots: Create, Monitor, and Drop — Artie](https://www.artie.com/blogs/postgresql-replication-slots) — WAL retention risk from stalled slots. `[artie-slots]`
11. [PostgreSQL WAL Slot Management: Prevention and Recovery at Production Scale — Streamkap](https://streamkap.com/resources-and-guides/postgres-wal-slot-management-production) and [PostgreSQL Logical Replication Internals: WAL, Slots, and Decoding — Streamkap](https://streamkap.com/resources-and-guides/postgresql-logical-replication-internals) — `max_slot_wal_keep_size` mitigation, `pgoutput`/`wal2json` mechanics. `[streamkap-slot-management]` `[streamkap-internals]`
12. [Debezium Kafka Architecture: When CDC Pipelines Outgrow Self-Managed Kafka and Connect — AutoMQ](https://www.automq.com/blog/debezium-kafka-architecture-when-cdc-pipelines-outgrow-self-managed-kafka-and-connect) and [Debezium Kafka Challenges & How OLake Go Solves Them — OLake](https://olake.io/blog/issues-debezium-kafka/) — Kafka Connect operational overhead. `[olake-debezium-issues]`
13. [Understanding CDC with Debezium Server and Debezium Engine — Decodable](https://www.decodable.co/blog/understanding-cdc-with-debezium-server-and-debezium-engine) and [debezium/debezium-server — GitHub](https://github.com/debezium/debezium-server) — Debezium Server as a Kafka-Connect-free deployment option. `[decodable-server-engine]` `[debezium-server-github]`
14. [Why You Should Reconsider Debezium: Challenges and Alternatives — Estuary](https://estuary.dev/blog/debezium-alternatives/) — total cost of ownership framing for self-managed Debezium/Kafka Connect. `[debezium-alternatives-estuary]`
15. [CDC without Debezium: Postgres WAL to Kafka in Go — MVP Factory](https://mvpfactory.io/blog/change-data-capture-without-debezium-wiring-postgres-wal-directly-to-your-event) — mechanics and scope of a hand-rolled `pg_recvlogical`/libpq-replication-mode consumer. `[mvpfactory-nodebezium]`
16. [Delivery Guarantees of Kafka — Educative](https://www.educative.io/courses/system-design-deep-dive-real-world-distributed-systems/np/delivery-guarantees-of-kafka) — per-partition ordering guarantee referenced for the primary-key-based partitioning claim. `[educative-kafka-delivery]`
17. [PostgreSQL CDC: Logical Replication vs Debezium vs Native Streaming — RisingWave](https://risingwave.com/blog/postgresql-cdc-logical-replication-debezium/) — general framing of the logical-replication-vs-Debezium distinction used in Section 0.

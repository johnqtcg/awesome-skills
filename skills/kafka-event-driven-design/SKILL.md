---
name: kafka-event-driven-design
description: >
  Kafka event-driven architecture designer and reviewer, at the application/client
  layer. ALWAYS use when designing, reviewing, or troubleshooting how a service
  produces or consumes Kafka events — topic and partition-key design, producer and
  consumer client configuration, consumer group topology, event schema definition
  (Avro/Protobuf/JSON Schema), Schema Registry compatibility modes, idempotent
  consumption, dead letter queues, exactly-once semantics, backpressure, and consumer
  lag. Use even for "just publish an event" — Kafka's partition-ordered-not-globally-
  ordered semantics, at-least-once default delivery, and consumer rebalance storms are
  the source of most production event-driven bugs. NOT for cluster operations: broker
  sizing and tuning, KRaft or ZooKeeper administration, partition reassignment and
  rebalancing tooling, quotas, ACL administration, MirrorMaker/replication topology,
  upgrade runbooks, or Kafka Streams and Kafka Connect internals.
---

# Kafka Event-Driven Design Review

## Quick Reference

§1 Scope · §2 Mandatory Gates · §3 Depth & Reference Loading · §4 Degradation
Modes · §5 Design Checklist · §6 Partition Design · §7 Anti-Examples ·
§8 Scorecard · §9 Output Contract

**Before scoring a version-sensitive configuration item, read
`references/version-client-matrix.md`.** Kafka defaults changed materially at 3.0
and again at 4.0, and the four major client libraries disagree with each other.
Which items are version-sensitive — and which fact each one needs — is §2's
*Minimum context per scored item*; most of the checklist needs no version at all.

---

## §1 Scope

**In scope** — Kafka event-driven architecture for production backend services:

- Topic design (naming, partition count, replication factor, retention)
- Partition key strategy (ordering guarantees, hot partition avoidance)
- Event schema design (Avro/Protobuf/JSON Schema, schema evolution, compatibility)
- Producer configuration (acks, retries, idempotence, transactional producers)
- Consumer group design (assignment strategy, rebalance handling, commit strategy)
- Idempotent consumption (deduplication, idempotency keys, exactly-once semantics)
- Dead letter queue (DLQ) and retry patterns
- Backpressure and consumer lag management
- Schema Registry integration and compatibility modes

**Out of scope** — say so and redirect rather than answering partially:

| Out of scope | Why it is not this skill |
|--------------|--------------------------|
| Broker sizing, heap/page-cache tuning, disk layout | Cluster operations, not client design |
| KRaft/ZooKeeper administration, controller config, 3.9→4.x migration | Platform runbook territory |
| Partition reassignment tooling, cruise-control balancing, quotas | Operational, though its *client-visible consequences* (AE-12 key remapping) are in scope |
| ACL administration and principal management | In scope only as a design requirement (§5.5 item 16), not as operator commands |
| MirrorMaker / cross-cluster replication topology | Separate architecture |
| Kafka Streams / Kafka Connect internals | Different programming models with their own semantics |
| Application code unrelated to Kafka → `go-code-reviewer` | |
| General REST/gRPC API design → `api-design` | |

The boundary: **this skill reviews what a service's producer/consumer code and
topic contract do.** If the answer would be a broker config change or an SRE
command against the cluster, say which parts you can cover and which you cannot,
rather than shipping a partial answer with the operational half quietly missing.

---

## §2 Mandatory Gates

Execute gates sequentially. Each gate has a **STOP** condition.

### Gate 1: Context Collection

| Item | Why it matters | If unknown |
|------|----------------|------------|
| **Kafka version** (2.x / 3.x / 4.x) | KRaft-only, KIP-848 and KIP-890 land at 4.0; the 3.0 default flip is a *client* fact, not a broker one | Gates feature-availability verdicts only |
| **Client library + version** (kafka-clients / librdkafka / sarama / franz-go) | Defaults differ *between clients on the same broker* | Gates every producer-durability verdict |
| **`group.protocol`** (classic / consumer) | Under `consumer` (4.0+), `partition.assignment.strategy`, `session.timeout.ms`, `heartbeat.interval.ms` do not exist | Assume `classic` (still the client default in 4.x) |
| **Schema format** (Avro / Protobuf / JSON / none) | Compatibility rules differ per format — Avro verdicts do not port to JSON Schema | Must clarify |
| **Ordering requirement** | Per-entity? Per-tenant? Global? None? | Must clarify — drives partition key |
| **Delivery guarantee needed** | At-most-once / At-least-once / Exactly-once | Assume at-least-once |
| **Throughput estimate** (events/sec) | Determines partition count and consumer scaling | Ask; assume moderate |
| **Consumer count / group topology** | Single consumer group? Multiple? Fan-out? | Must clarify |
| **Retention policy** | Time-based / size-based / compacted | Assume 7 days time-based |
| **Schema Registry** | Confluent / AWS Glue / Apicurio / external governance / none | Ask; drives evolution strategy, not automatically a defect if absent |
| **Data sensitivity** (PII / payment / regulated) | Drives topic ACLs, field-level redaction, retention limits | Ask; assume non-regulated and record the assumption |

**STOP**: Cannot determine what events are being produced/consumed (no domain context). Clarify before proceeding.

#### Minimum context per scored item

There is no global version gate. Each item names the **one** fact it depends on, and is NOT SCOREABLE when *that* fact is missing — whatever else is known, and without dragging unrelated items down with it.

| Scored item | Minimum context | Why that one, and not the other |
|-------------|-----------------|---------------------------------|
| Producer durability — `acks`, `enable.idempotence`, `retries` (§5.2 item 5) | **client library + its version** | Defaults are a client property. An absent `acks` line is safe on kafka-clients ≥3.0 and a data-loss defect on sarama; the broker version moves neither verdict |
| Consumer-protocol keys — assignor, `session.timeout.ms`, `heartbeat.interval.ms`, rebalance advice (§5.3 item 13) | **`group.protocol`**, or the **broker version** to infer it (`classic` below 4.0) | These keys do not exist under `group.protocol=consumer`; which client sets them is irrelevant |
| Feature availability — KIP-848 server-side assignors, `transaction.version=2`, KRaft-only behaviour, removed APIs | **broker version** | The feature is either in the cluster or it is not |
| Everything else — partition key, atomicity, DLQ policy, schema governance, lag alerting, retention, naming, backpressure, PII (§5 items 1–4, 6–12, 14–17) | **none** | Scoreable from domain context alone. Do **not** withhold these because a version is unknown |

**STOP**: Asked to score an item whose minimum context is missing. Report both branches explicitly and mark **that item** NOT SCOREABLE — never guess, and never extend the block to items that did not need the missing fact.

**PROCEED**: At least event type, ordering requirement, and delivery guarantee are known.

### Gate 2: Scope Classification

| Mode | Trigger | Output |
|------|---------|--------|
| **review** | User provides existing Kafka config/code | Safety analysis with findings |
| **design** | User describes event-driven requirements | Complete topic + schema + consumer design |
| **troubleshoot** | User reports issues (lag, duplication, ordering) | Root cause + fix plan |

**STOP**: Not Kafka-related (e.g., REST API design). Redirect to appropriate skill.

**PROCEED**: Kafka event-driven intent confirmed.

### Gate 3: Risk Classification

| Risk | Definition | Required action |
|------|-----------|-----------------|
| **SAFE** | Single topic, simple consumer, at-least-once | Standard review |
| **WARN** | Multi-topic transactions, schema evolution, exactly-once | Off-peak deployment + monitoring |
| **UNSAFE** | Partition key change on live topic, consumer group migration, schema breaking change | Staged rollout + rollback plan mandatory |

**STOP**: Any UNSAFE item without mitigation plan.

**PROCEED**: Every component has risk level and mitigation.

### Gate 4: Output Completeness

Before delivering output, verify all §9 Output Contract sections present. §9.9 Uncovered Risks must never be empty.

---

## §3 Depth & Reference Loading

| Depth | When to use | Gates | References to load |
|-------|-------------|-------|-------------------|
| **Lite** | Single producer/consumer pair, simple schema | 1–4 | `version-client-matrix.md` if any config verdict is given |
| **Standard** | Multi-consumer topology, schema evolution, DLQ design | 1–4 | `event-schema-patterns.md` + `version-client-matrix.md` |
| **Deep** | Cross-service event mesh, exactly-once, CQRS/ES pattern | 1–4 | All four reference files |

**Force Standard or higher** when any signal appears:
schema evolution requirement, exactly-once semantics, multi-consumer-group fan-out, partition key redesign, consumer group migration, compacted topics for event sourcing, Kafka 4.x consumer-protocol migration (`group.protocol=consumer`), transactional producer fencing, PII/regulated data on the topic.

Two loads override the depth column: **any** producer/consumer config verdict
loads `references/version-client-matrix.md` even at Lite depth (likewise
`group.protocol`, `group.remote.assignor`, `transaction.version`, KRaft, any 4.x
version, or a `sendOffsetsToTransaction` call); consumer failure or lag signals
load `references/consumer-failure-modes.md`. Extended anti-example matching loads
`references/consumer-anti-examples.md`.

---

## §4 Degradation Modes

When context is incomplete, degrade gracefully — never fabricate assumptions about ordering requirements.

| Available context | Mode | What you can do | What you cannot do |
|-------------------|------|-----------------|-------------------|
| Full (version, schema, ordering, delivery, throughput) | **Full** | Complete design with quantified guarantees | — |
| Event type + ordering known, infra unknown | **Degraded** | Schema + consumer design; flag infra unknowns | Partition count, replication recommendations |
| Only code snippets, no architecture context | **Minimal** | Static review of producer/consumer patterns | Full topology design |
| No code (greenfield design) | **Planning** | Propose event architecture from requirements | Review existing implementation |

**Hard rule**: Never claim "exactly-once" without verifying transactional producer + consumer `isolation.level=read_committed` + `enable.auto.commit=false` + idempotent processing at any non-Kafka sink. In Degraded/Minimal mode, flag "delivery guarantee unverified" in §9.9.

**Hard rule**: Never state a numeric threshold you did not derive from the context
in front of you. Throughput ceilings, lag alert values, retry counts and partition
counts all depend on the workload; a memorised figure is a fabrication with a number
attached, harder to challenge than an honest "derive this from your p99". Give the
formula and the inputs it needs instead (§6 shows the worked form).

**Hard rule**: Never give a config verdict without the context *that item* names
in Gate 1's **Minimum context per scored item** table — client + version for
producer durability, `group.protocol` (or the broker version) for consumer-protocol
keys, broker version for feature availability. Missing it, present both branches
and mark that one item not scoreable; the rest of the review still stands.
See `references/version-client-matrix.md`.

---

## §5 Design Checklist

Execute every item. Mark **PASS** / **WARN** / **FAIL** / **N/A** / **NOT
SCOREABLE** with evidence. The bracketed tier is the item's weight in §8 — these
seventeen items *are* the scorecard, and **every one of them carries a tier**.
An item that is reviewed but not scored is a hole: the finding gets written down
and the verdict still comes out PASS. Inapplicable items leave via N/A, which
shrinks the denominator honestly; they do not leave by being unscored.

### 5.1 Topic Design

1. **Topic naming convention** *(Hygiene)* — follow `{domain}.{entity}.{event-type}` or `{team}.{service}.{event}` pattern, or the org's own. Names should be greppable, meaningful, and avoid generic names like "events" or "messages".

2. **Partition count sized for throughput** *(Hygiene)* — each partition is the unit of parallelism. Rule of thumb: partitions ≥ max expected consumer instances. Over-partitioning wastes resources; under-partitioning caps throughput. Partition count cannot be decreased (only increased, which breaks key-based ordering).

3. **Replication factor sized to the durability requirement** *(Hygiene)* — RF≥3 + `min.insync.replicas=2` + `acks=all` survives one broker loss; the right default wherever loss is a business incident. FAIL if the topic holds a source of record or the low RF is unexamined; WARN with owner and rationale recorded when it is a documented trade-off (dev cluster, rebuildable projection, accepted-loss telemetry). Two traps: `min.insync.replicas` does nothing without `acks=all`, and RF=2 + `min.insync.replicas=2` blocks writes the moment any broker restarts.

4. **Retention policy matches use case** *(Hygiene)* — time-based (default 7 days) for event streaming; `compact` for entity-state topics (latest value per key); and compatible with any deletion obligation Gate 1 recorded. For **event sourcing, use two topics**: an append-only event log (`delete` with retention long enough to replay from zero, or unbounded) plus a separate compacted snapshot topic. Compaction on the event log itself, keyed by aggregate ID, deletes the history the design exists to keep — silently. Detail: `references/event-schema-patterns.md` §4.3.

### 5.2 Producer Design

5. **Durability config verified against version and client, not assumed** *(Critical)* — the target is `acks=all` + retries + `enable.idempotence=true`. FAIL on an explicit downgrade, or on defaults that are unsafe for that client; **PASS when kafka-clients ≥3.0 defaults already satisfy it**. Whether *silence* about it is a defect is entirely a function of the client, so establish the client before scoring:

   | Client | Safe by default? | What to flag |
   |--------|:---:|--------------|
   | kafka-clients ≥ 3.0 | both | only an explicit downgrade |
   | kafka-clients ≤ 2.8 | neither | silence *is* the defect |
   | sarama | neither | silence; and `Net.MaxOpenRequests = 1` beside `Idempotent = true` is **required** by sarama's `Validate()` — not an over-restriction |
   | librdkafka | acks only | the idempotence, not the acks |
   | franz-go | both | an explicit `DisableIdempotentWrite()` |

   On the Java client, idempotence preserves ordering for any `max.in.flight.requests.per.connection` ≤ 5; "must be 1" is sarama-specific. Without idempotence, in-flight > 1 plus retries genuinely can reorder. Full matrix and sources: `references/version-client-matrix.md`.

6. **Partition key chosen for ordering + distribution** *(Standard)* — the key determines the partition; records sharing a key share a partition and are therefore ordered relative to each other. Common keys: entity ID (`order_id`, `user_id`), tenant ID. FAIL a null key on an order-sensitive topic, or a sharded key presented as order-preserving. What to actually watch for:
   - **Null key ≠ round-robin.** Placement is batch-sticky (Java, librdkafka) or random (sarama) — no mainstream client round-robins by default. Report the *loss of per-key ordering*, not a distribution shape.
   - **High key cardinality does not create partitions.** Partition count is a topic property; keys hash modulo it. The real problems are the opposite — too few distinct keys (idle partitions) and skew (one key dominating).
   - **A timestamp key is not automatically hot** under the default hash partitioner. It is a defect because it destroys per-entity ordering; it becomes a hot partition only under a range-style or time-bucketing partitioner. Cite whichever reason applies.
   - **Hot-key sharding trades away the guarantee it appears to preserve.** `key:{shard}` means Kafka no longer orders that entity — the broker cannot know the shards are related. Never present composite/sharded keys as "keeps ordering and fixes the hot partition". Trade-offs per fix: §6.

7. **Event carries the metadata its consumers actually need** *(Standard)* — load-bearing: `event_id` (dedup key), and `event_type` on multi-type topics (routing). Strong defaults: `timestamp`, `source`, `correlation_id`. `schema_version` is redundant under Schema Registry — the wire format carries the schema ID. Routing/tracing metadata belongs in **record headers**; a header-based envelope is not a missing envelope. Missing `event_id` with non-idempotent consumers is a real finding; missing `source` on a single-producer topic is hygiene. Field weights: `references/event-schema-patterns.md` §1.

8. **Atomicity mechanism matches the boundary being crossed** *(Critical)* — a dual-write with no atomicity mechanism loses events or invents them, silently and unrecoverably; that is the same class of defect as no durability and no dedup, not a design preference. Two problems, two tools:
   - **Kafka → Kafka**: Kafka transactions (`initTransactions` … `sendOffsetsToTransaction` … `commitTransaction`) plus `isolation.level=read_committed` and `enable.auto.commit=false` on the consumer.
   - **Database → Kafka**: the **outbox pattern** — business rows and outbox row in **one database transaction**, then a relay publishes and marks published. **A Kafka transaction cannot include a database write.** The outbox is at-least-once by construction, so it never removes the consumer's idempotency requirement. Fencing, abort paths and relay ordering: `references/consumer-failure-modes.md` §4 and `event-schema-patterns.md` §6.

### 5.3 Consumer Design

9. **Consumer survives duplicate delivery** *(Critical)* — at-least-once means duplicates *will* arrive. Handle them by: a dedup marker on `event_id` committed in the same transaction as the side effect, naturally idempotent operations (`INSERT ... ON CONFLICT`), or — Kafka-to-Kafka only — EOS with `read_committed` + `auto.commit=false`. **Cache-TTL dedup alone does not satisfy this** (race, crash window, and expiry all bypass it). There is no such thing as a "transactional consumer": the transaction belongs to the **producer** (`transactional.id`), and the consumer contributes offsets via `sendOffsetsToTransaction` while reading `read_committed`. The term matters because it locates the fencing identity a review must check.

10. **Commit strategy explicit** *(Standard)* — `enable.auto.commit` is still `true` by default in Kafka 4.x and commits on a timer, so a crash can drop or replay a batch. At-least-once: manual commit after processing. EOS: `enable.auto.commit=false` **and** `isolation.level=read_committed` (default `read_uncommitted` reads **aborted** records), offsets committed inside the transaction.

11. **A defined, owned policy for unprocessable messages** *(Critical)* — something specific must happen to a message that cannot be processed, and someone must own it. DLQ after N retries is the usual answer, not the only correct one: strictly ordered state machines (event-sourced aggregates, ledgers) are corrupted by skipping, so halt-and-page is right there; transient downstream failures deserve retry-with-backoff first. FAIL when no policy exists ("retry forever", "log and continue"); **WARN for a documented non-DLQ policy with an owner**. When a DLQ exists, an unchecked publish error before the offset advances is itself a FAIL — that is a data-loss path, not a style issue. Trade-offs: `references/consumer-failure-modes.md` §2.

12. **Consumer lag monitoring with an alert threshold defined** *(Standard)* — lag per partition is the primary health metric. Derive the alert from time-to-drain (`records_lag_max / records_consumed_rate`) against a stated freshness SLO; a copied message count is meaningless across workloads. On `read_committed` consumers, non-zero lag on a drained transactional topic is normal — aborted records occupy offsets.

13. **Consumer group configuration is coherent with the protocol in use** *(Standard)* — the `classic` and `consumer` (KIP-848, 4.0+) protocols take **disjoint** config: under `group.protocol=consumer`, `partition.assignment.strategy`, `session.timeout.ms` and `heartbeat.interval.ms` do not exist, and the assignor moves server-side (`group.remote.assignor`). Setting both is a broken config, not a belt-and-braces one. Static membership (`group.instance.id`) only avoids a rebalance for a restart that completes inside `session.timeout.ms` — it buys a window, it does not abolish rebalancing, and a rolling deploy slower than that window rebalances as usual. NOT SCOREABLE without `group.protocol` or the broker version to infer it (§2). Detail: `references/consumer-failure-modes.md` §1.

### 5.4 Schema Evolution & Operations

14. **Schema compatibility mode chosen deliberately, and stated in the right direction** *(Standard)* — an equivalent external schema-governance process with validating consumers also satisfies this. BACKWARD: a **new** reader reads **old** data → upgrade consumers first. FORWARD: an **old** reader reads **new** data → upgrade producers first. FULL: both, so order is free. BACKWARD **does** permit deleting an optional/defaulted field, and FULL permits adding *and* deleting optional fields — "BACKWARD/FULL can never delete" is wrong and drives permanent field accretion. `*_TRANSITIVE` checks all previous versions: right when old data or old readers span more than one version (replay, event sourcing, un-upgradable clients), needless friction otherwise; `BACKWARD` is the registry default and defensible. Rules differ per format — JSON Schema turns on the open/closed content model — so never port an Avro verdict to a JSON Schema subject. Table, per-format rules and the verification command: `references/event-schema-patterns.md` §2.

15. **Backpressure handling defined** *(Hygiene)* — what happens when consumers can't keep up? Options: scale consumers (up to partition count), increase batch size, apply rate limiting on producer, drop low-priority events. "Consumer crashes under load" is not a strategy.

### 5.5 Governance

16. **Sensitive data in events is classified and controlled** *(Standard)* — a topic is a durable, replayable copy readable by every principal with read access. For PII, payment, credentials, or regulated data verify: topic ACLs; field-level redaction/tokenisation for fields no consumer needs; retention compatible with the deletion obligation. Erasure against an append-only or compacted topic is a design problem, not an ops task — see `references/consumer-anti-examples.md` AE-17 for crypto-shredding. N/A with a reason when Gate 1 recorded the data as non-sensitive.

17. **Topic ownership and consumer inventory recorded** *(Hygiene)* — who owns the schema, and which consumer groups read this topic. Without it, no one can judge whether a schema or partition-count change is safe, and the compatibility mode in item 14 is being chosen blind.

---

## §6 Partition Design (Standard + Deep)

Quick decision guide — for schema patterns load `references/event-schema-patterns.md`.

| Ordering need | Partition key | Example |
|--------------|--------------|---------|
| Per-entity ordering | Entity ID | `order_id` → all events for order 123 in same partition |
| Per-tenant ordering | Tenant ID | `tenant_id` → tenant isolation per partition |
| Per-user ordering | User ID | `user_id` → user action sequence preserved |
| No ordering needed | null (client-dependent placement, **not** round-robin) | Metrics, logs, analytics events |
| Global ordering | Single partition | Throughput is capped at one consumer — see below |

**Global ordering has no fixed events/sec threshold.** The ceiling is whatever one
consumer instance processes end-to-end, which spans orders of magnitude. Derive it:
`max sustainable rate ≈ 1 / p99_processing_time`, then leave 2–3× for spikes and
replay; a memorised threshold like "<100 events/sec" is a fabricated number. Test
the requirement first — most "we need global ordering" cases are per-entity
ordering plus a report that wanted a total order. The choice is near-irreversible:
growing the topic later needs the AE-12 migration.

**You cannot have per-entity Kafka-native ordering and spread one entity's events
across partitions.** If both are demanded, one is not a real requirement.

Hot-partition symptoms, causes, and the four mitigations with what each costs
(composite key, sharded key, dedicated topic, more partitions):
`references/event-schema-patterns.md` §7.

---

## §7 Anti-Examples

Seventeen WRONG/RIGHT pairs live in `references/consumer-anti-examples.md`. Load
it whenever a snippet resembles one of these; the titles are the index.

| # | What it gets wrong | Fires on |
|---|--------------------|----------|
| AE-1 | `acks=1` on critical events | sarama `NewConfig()` left as-is |
| AE-2 | Consumer without idempotency | redelivery double-applies |
| AE-3 | Unchecked DLQ publish | offset advances past an unpublished message |
| AE-4 | Null partition key | per-key ordering lost |
| AE-5 | Compatibility direction inverted | BACKWARD reasoned about as FORWARD |
| AE-6 | Kafka defect mislabelled as app logic | "double charge" filed as a business bug |
| AE-7 … AE-11 | Auto-commit with slow handlers · blocking I/O in the poll loop · single partition for "global ordering" · `group.id` reuse across environments · compacted topic with no tombstone handling |
| AE-12 … AE-17 | Partition increase on a live topic · no consumer-side schema validation · Kafka 4.x assignor config under `group.protocol=consumer` · random `transactional.id` · `abortTransaction()` without seeking back · PII with no deletion path |

---

## §8 Kafka Design Scorecard

Every item resolves to exactly one of **PASS / WARN / FAIL / N/A / NOT SCOREABLE**.

| Verdict | When | Counts as |
|---------|------|-----------|
| **PASS** | Requirement met | credit |
| **WARN** | Risk examined and accepted: alternative mechanism in place, owner named, trade-off recorded | **credit** — a WARN never fails the scorecard, and must appear in §9.9 |
| **FAIL** | Unexamined gap: failure path undefined, or config contradicts a stated requirement | no credit |
| **N/A** | Inapplicable for a reason stated from Gate 1 context ("no PII — Gate 1 recorded non-regulated telemetry") | removed from **both** numerator and denominator |
| **NOT SCOREABLE** | Gate 1 did not establish the *minimum context* that item names (§2) — and only that item | removed from both, **and** forces the overall verdict to `not scoreable` |

The PASS/WARN split is what stops the scorecard producing false positives: "no
DLQ" is FAIL when the failure path is *retry forever*, and WARN when the team
deliberately runs halt-and-page on an ordered ledger topic.

### The arithmetic, stated mechanically

The scored items are the §5 checklist items themselves; this section weights
them, it does not restate them. Per tier, `A` = applicable items (tier size minus
N/A minus NOT SCOREABLE) and `C` = items scored PASS **or** WARN.

| Tier | §5 items | Size | Passes when |
|------|----------|:----:|-------------|
| Critical | 5 durability · 8 atomicity mechanism · 9 duplicate delivery · 11 unprocessable-message policy | 4 | `C == A` — every applicable item is PASS or WARN |
| Standard | 6 partition key · 7 event metadata · 10 commit strategy · 12 lag alerting · 13 consumer-group config · 14 schema governance · 16 sensitive data | 7 | `C ≥ ceil(0.8 × A)` |
| Hygiene | 1 naming · 2 partition count · 3 replication · 4 retention · 15 backpressure · 17 ownership | 6 | `C ≥ ceil(0.75 × A)` |

**There is no unscored tier.** Four items used to sit outside the scorecard, which made a green verdict reachable with a Critical defect written down in the same report: a dual-write with no atomicity mechanism (§5 item 8) was found, reported, and cost nothing. Inapplicable items leave through N/A, which shrinks `A`; nothing leaves by having no tier.

Thresholds **scale with `A`**; they are not fixed counts, and `ceil` stops a
partially-applicable tier getting an easier ride than a full one. Standard:

| Applicable `A` | Needed `C` | Reading |
|:---:|:---:|---|
| 7 | 6 | the full tier |
| 5 | 4 | the familiar "4 of 5" |
| 4 | 4 | all four — 3/4 is 75%, below the bar |
| 3 | 3 | all three |
| 0 | 0 | tier vacuously passes; report `Standard N/A` |

Overall **PASS** requires all three tiers to pass. A single NOT SCOREABLE item
forces overall `not scoreable` regardless of the rest — an incomplete review must
not present itself as a green one. Otherwise **FAIL**.

Three rules that keep this mechanical rather than a matter of taste:

- **A WARN needs all three of** an alternative mechanism, a named owner, and a
  recorded trade-off. Missing any one, it is a FAIL. "The team knows about it"
  is not an owner.
- **N/A needs a Gate 1 citation**, not a judgement. If Gate 1 did not record the
  fact that makes the item inapplicable, the item is NOT SCOREABLE, not N/A.
- **NOT SCOREABLE is per item.** Only the items whose minimum context (§2) is
  missing are unscoreable. An unknown client version blocks item 5 and nothing
  else; it does not excuse an unscored DLQ policy or partition key.

In a CI gate, treat `not scoreable` as a **failure to gate** rather than a pass,
and gate on FAIL count only — failing on WARNs pushes teams to relabel accepted
risks as PASS, which destroys the accepted-risk register.

**Report the verdict as `C/A` per tier**, so the denominator shows what was
actually judged — never a fixed `/3`, `/5`, `/4`:

```
Critical 3/3 · Standard 4/5 · Hygiene 3/3 (1 N/A: no deletion obligation) — PASS
```

Had Hygiene scored 2/3 there, the overall verdict would be **FAIL** —
`ceil(0.75 × 3) = 3`, so 2 is short. Writing the denominator down is what makes
that visible. **Not scoreable** is likewise a valid overall verdict: with the
client library unknown, say `Critical: not scoreable (item 5 — client unknown)`
and still report the other two Critical items' verdicts.

---

## §9 Output Contract

Every design review MUST produce these sections. Write "N/A — [reason]" if inapplicable.

```
### 9.1 Context Gate
| Item | Value | Source |
### 9.2 Depth & Mode
[Lite/Standard/Deep] × [review/design/troubleshoot] — [rationale]
### 9.3 Risk Assessment
| Component | Risk | Notes |
### 9.4 Architecture Design (Standard/Deep; "N/A — Lite" for Lite)
- Topic topology + partition strategy
- Producer + consumer configuration
- Schema design + evolution strategy
### 9.5 Implementation (topic config, producer/consumer code patterns)
### 9.6 Validation Plan
- End-to-end event flow test; duplicate-delivery test (kill the consumer between
  side effect and offset commit)
- Schema evolution test — run the registry's own `/compatibility/subjects/...`
  endpoint against the candidate; deploy in the order the mode requires
  (BACKWARD → consumers first; FORWARD → producers first)
### 9.7 Failure Handling
- Unprocessable-message policy (DLQ / halt-and-alert / compensating) + owner
- DLQ publish-failure path (must not commit past an unpublished message)
- Consumer rebalance behavior — state which protocol (`classic` / `consumer`)
- Broker failure recovery; for EOS: abort path (seek back to last committed)
  and `transactional.id` fencing identity
### 9.8 Monitoring & Alerts
- Consumer lag per partition; producer error rate, batch size, latency
- DLQ message rate **and** DLQ publish failure rate
- For EOS: transaction abort rate, `ProducerFencedException` count
### 9.9 Uncovered Risks (MANDATORY — never empty)
| Area | Reason | Impact | Follow-up |
```

**Volume rules**: FAIL always fully detailed; WARN up to 10, overflow to §9.9;
PASS summary only. §9.9 must document every assumption — especially an unverified
delivery guarantee, and each Gate 1 field left unknown (broker version, client
library, `group.protocol`) with the specific items it left NOT SCOREABLE.

**Scorecard summary** (append after §9.9), in §8's `C/A` form — the denominator is
*applicable* items, so it shrinks with each N/A and NOT SCOREABLE:
```
Scorecard: Critical C/A · Standard C/A · Hygiene C/A — PASS | FAIL | not scoreable
Non-scoring items: [N/A count + reason each] [NOT SCOREABLE count + missing input]
Data basis: [full context | degraded | minimal | planning]
Version basis: [broker version | client library+version | group.protocol | "unknown — see §9.9"]
```

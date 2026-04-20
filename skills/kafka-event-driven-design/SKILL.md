---
name: kafka-event-driven-design
description: >
  Kafka event-driven architecture designer and reviewer. ALWAYS use when designing,
  reviewing, or troubleshooting Kafka-based event systems — topic design, partition
  strategy, consumer group configuration, event schema definition (Avro/Protobuf/JSON),
  idempotent consumers, dead letter queues, exactly-once semantics, Schema Registry
  compatibility, backpressure handling, and consumer lag monitoring. Use even for
  "just publish an event" — Kafka's partition-ordered-not-globally-ordered semantics,
  at-least-once default delivery, and consumer rebalance storms are the source of most
  production event-driven bugs.
---

# Kafka Event-Driven Design Review

## Quick Reference

| If you need to…                        | Go to                                    |
|----------------------------------------|------------------------------------------|
| Understand what this skill covers      | §1 Scope                                 |
| Check mandatory prerequisites          | §2 Mandatory Gates                       |
| Choose review depth                    | §3 Depth Selection                       |
| Handle incomplete context              | §4 Degradation Modes                     |
| Evaluate design item by item           | §5 Design Checklist                      |
| Choose partition and key strategy      | §6 Partition Design                      |
| Avoid common Kafka mistakes            | §7 Anti-Examples                         |
| Score the review result                | §8 Scorecard                             |
| Format review output                   | §9 Output Contract                       |
| Deep-dive event schema patterns        | `references/event-schema-patterns.md`    |
| Understand consumer failure modes      | `references/consumer-failure-modes.md`   |

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

**Out of scope** — delegate to dedicated skills:

- Kafka cluster operations, broker config, ZooKeeper/KRaft migration → Kafka ops
- Application code changes unrelated to Kafka → `go-code-reviewer`
- General API design → `api-design`

---

## §2 Mandatory Gates

Execute gates sequentially. Each gate has a **STOP** condition.

### Gate 1: Context Collection

| Item | Why it matters | If unknown |
|------|----------------|------------|
| **Kafka version** (2.x / 3.x) | Exactly-once, cooperative rebalance features vary | Assume 2.8 (conservative) |
| **Schema format** (Avro / Protobuf / JSON / none) | Determines evolution strategy and registry needs | Must clarify |
| **Ordering requirement** | Per-entity? Per-tenant? Global? None? | Must clarify — drives partition key |
| **Delivery guarantee needed** | At-most-once / At-least-once / Exactly-once | Assume at-least-once |
| **Throughput estimate** (events/sec) | Determines partition count and consumer scaling | Ask; assume moderate |
| **Consumer count / group topology** | Single consumer group? Multiple? Fan-out? | Must clarify |
| **Retention policy** | Time-based / size-based / compacted | Assume 7 days time-based |
| **Schema Registry** | Confluent / AWS Glue / Apicurio / none | Ask; critical for evolution |

**STOP**: Cannot determine what events are being produced/consumed (no domain context). Clarify before proceeding.

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

## §3 Depth Selection

| Depth | When to use | Gates | References to load |
|-------|-------------|-------|-------------------|
| **Lite** | Single producer/consumer pair, simple schema | 1–4 | None |
| **Standard** | Multi-consumer topology, schema evolution, DLQ design | 1–4 | `event-schema-patterns.md` |
| **Deep** | Cross-service event mesh, exactly-once, CQRS/ES pattern | 1–4 | Both reference files |

**Force Standard or higher** when any signal appears:
schema evolution requirement, exactly-once semantics, multi-consumer-group fan-out, partition key redesign, consumer group migration, compacted topics for event sourcing.

---

## §4 Degradation Modes

When context is incomplete, degrade gracefully — never fabricate assumptions about ordering requirements.

| Available context | Mode | What you can do | What you cannot do |
|-------------------|------|-----------------|-------------------|
| Full (version, schema, ordering, delivery, throughput) | **Full** | Complete design with quantified guarantees | — |
| Event type + ordering known, infra unknown | **Degraded** | Schema + consumer design; flag infra unknowns | Partition count, replication recommendations |
| Only code snippets, no architecture context | **Minimal** | Static review of producer/consumer patterns | Full topology design |
| No code (greenfield design) | **Planning** | Propose event architecture from requirements | Review existing implementation |

**Hard rule**: Never claim "exactly-once" without verifying transactional producer + consumer read-committed isolation + idempotent processing. In Degraded/Minimal mode, flag "delivery guarantee unverified" in §9.9.

---

## §5 Design Checklist

Execute every item. Mark **PASS** / **WARN** / **FAIL** with evidence.

### 5.1 Topic Design

1. **Topic naming convention** — follow `{domain}.{entity}.{event-type}` or `{team}.{service}.{event}` pattern. Names should be greppable, meaningful, and avoid generic names like "events" or "messages".

2. **Partition count sized for throughput** — each partition is the unit of parallelism. Rule of thumb: partitions ≥ max expected consumer instances. Over-partitioning wastes resources; under-partitioning caps throughput. Partition count cannot be decreased (only increased, which breaks key-based ordering).

3. **Replication factor ≥ 3** for production topics — `min.insync.replicas = 2` with `acks = all` ensures no data loss on single broker failure. RF=1 is unacceptable for any non-ephemeral data.

4. **Retention policy matches use case** — time-based (default 7 days) for event streaming; compacted for entity-state topics (latest value per key retained indefinitely); infinite retention for event sourcing.

### 5.2 Producer Design

5. **acks=all + retries + enable.idempotence=true** — this is the minimum safe producer config. `acks=1` risks data loss on leader failure. `acks=0` is fire-and-forget. Idempotent producer (Kafka 0.11+) prevents duplicate writes from retries.

6. **Partition key chosen for ordering + distribution** — key determines which partition an event goes to. Events with the same key are ordered. Common keys: entity ID (order_id, user_id). Avoid: timestamp (hot partition), null (round-robin = no ordering), high-cardinality unbounded (too many partitions).

7. **Event schema includes metadata** — every event should carry: `event_id` (UUID), `event_type`, `timestamp`, `source_service`, `correlation_id`, `schema_version`. Without these, debugging and deduplication become impossible.

8. **Transactional producer for multi-topic atomicity** — if producing to multiple topics must be atomic (e.g., event + outbox), use Kafka transactions (`initTransactions`, `beginTransaction`, `commitTransaction`). Without transactions, partial writes create inconsistency.

### 5.3 Consumer Design

9. **Idempotent consumption** — at-least-once delivery means consumers WILL receive duplicates (after rebalance, retry, or producer retry). Every consumer must handle duplicates: deduplication by `event_id`, idempotent database operations (`INSERT ON CONFLICT`), or exactly-once via transactional consumer.

10. **Commit strategy explicit** — `enable.auto.commit=true` (default) commits offsets periodically, risking reprocessing on crash. For at-least-once: manual commit after processing. For exactly-once: commit offsets within the transaction that processes the event.

11. **Dead letter queue (DLQ) for poison messages** — messages that repeatedly fail processing must be routed to a DLQ topic instead of blocking the partition. Without DLQ, a single bad message blocks all subsequent messages in that partition indefinitely.

12. **Consumer lag monitoring** — `consumer_lag` (latest offset - committed offset) per partition is the primary health metric. Alert on sustained lag > threshold. Use `kafka-consumer-groups.sh` or metrics exporter. Lag = events waiting to be processed.

### 5.4 Schema Evolution & Operations

13. **Schema compatibility mode set** — Schema Registry supports: BACKWARD (new reader, old data), FORWARD (old reader, new data), FULL (both). Choose based on deployment strategy. BACKWARD_TRANSITIVE is safest for most cases. Breaking changes require a new topic.

14. **Backpressure handling defined** — what happens when consumers can't keep up? Options: scale consumers (up to partition count), increase batch size, apply rate limiting on producer, drop low-priority events. "Consumer crashes under load" is not a strategy.

---

## §6 Partition Design (Standard + Deep)

Quick decision guide — for schema patterns load `references/event-schema-patterns.md`.

| Ordering need | Partition key | Example |
|--------------|--------------|---------|
| Per-entity ordering | Entity ID | `order_id` → all events for order 123 in same partition |
| Per-tenant ordering | Tenant ID | `tenant_id` → tenant isolation per partition |
| Per-user ordering | User ID | `user_id` → user action sequence preserved |
| No ordering needed | null (round-robin) | Metrics, logs, analytics events |
| Global ordering | Single partition | Only if throughput is very low (<100 events/sec) |

### Hot partition detection and mitigation

- **Symptom**: one partition has 10x the events of others; consumer for that partition lags
- **Cause**: skewed partition key (e.g., one tenant produces 90% of events)
- **Fix**: composite key (`tenant_id + entity_id`), or custom partitioner that spreads hot keys across N partitions while maintaining per-entity ordering

---

## §7 Anti-Examples

### AE-1: Producer with acks=1 for critical business events
```go
// WRONG: acks=1 — leader acknowledges before replication; data lost on leader failure
producer, _ := sarama.NewSyncProducer(brokers, config)
// config.Producer.RequiredAcks = sarama.WaitForLocal  // acks=1
// RIGHT: acks=all + idempotent
config.Producer.RequiredAcks = sarama.WaitForAll
config.Producer.Idempotent = true
config.Net.MaxOpenRequests = 1
```

### AE-2: Consumer without idempotency handling
```go
// WRONG: processes event and assumes it won't be delivered again
func handleOrderCreated(event OrderCreated) {
    db.Insert(event.Order)  // duplicate delivery → duplicate insert → constraint violation or double-charge
}
// RIGHT: idempotent processing
func handleOrderCreated(event OrderCreated) {
    db.Exec("INSERT INTO orders ... ON CONFLICT (id) DO NOTHING", event.Order)
}
```

### AE-3: No dead letter queue — poison message blocks partition
```go
// WRONG: bad message causes infinite retry loop, blocking all events behind it
func consume(msg *sarama.ConsumerMessage) {
    if err := process(msg); err != nil {
        log.Error(err)
        // message is not committed → redelivered forever
    }
}
// RIGHT: route to DLQ after N retries
if retryCount >= maxRetries {
    producer.Send(dlqTopic, msg)
    consumer.CommitMessage(msg)  // advance past the poison message
}
```

### AE-4: Null partition key — loses ordering guarantee
```go
// WRONG: null key → round-robin across partitions → order events scattered
producer.SendMessage(&sarama.ProducerMessage{
    Topic: "order.events",
    Value: sarama.ByteEncoder(data),
    // Key is nil → no ordering guarantee
})
// RIGHT: use entity ID as partition key
producer.SendMessage(&sarama.ProducerMessage{
    Topic: "order.events",
    Key:   sarama.StringEncoder(order.ID),
    Value: sarama.ByteEncoder(data),
})
```

### AE-5: Schema change without compatibility check
```
// WRONG: removed required field — breaks all existing consumers
// v1: {"order_id": "123", "amount": 99.50, "currency": "USD"}
// v2: {"order_id": "123", "amount": 99.50}  // removed currency!
// RIGHT: add new optional fields, never remove required ones (BACKWARD compatible)
```

### AE-6: Kafka issue reported as application logic bug
```
-- WRONG: "Bug: some orders processed twice causing double charge"
-- This is a consumer idempotency issue, not application logic.
-- RIGHT: "Consumer lacks idempotency: duplicate Kafka delivery causes double processing"
```

Extended anti-examples (AE-7 through AE-13) in `references/consumer-anti-examples.md`.

---

## §8 Kafka Design Scorecard

### Critical — any FAIL means overall FAIL

- [ ] Producer uses `acks=all` + `enable.idempotence=true` for non-ephemeral events
- [ ] Consumer handles duplicate delivery (idempotent processing or exactly-once)
- [ ] Dead letter queue exists for poison messages (no infinite retry loops)

### Standard — 4 of 5 must pass

- [ ] Partition key matches ordering requirement (not null for ordered events)
- [ ] Schema includes event metadata (event_id, event_type, timestamp, source)
- [ ] Schema compatibility mode configured in Schema Registry
- [ ] Consumer lag monitoring with alert threshold defined
- [ ] Commit strategy explicitly chosen (auto-commit disabled for at-least-once)

### Hygiene — 3 of 4 must pass

- [ ] Topic naming follows convention (`{domain}.{entity}.{event-type}`)
- [ ] Replication factor ≥ 3 with `min.insync.replicas = 2`
- [ ] Backpressure strategy defined (scale / rate-limit / drop)
- [ ] Retention policy matches use case (time-based / compacted / infinite)

**Verdict**: `X/12`; Critical: `Y/3`; Standard: `Z/5`; Hygiene: `W/4`.
PASS requires: Critical 3/3 AND Standard ≥4/5 AND Hygiene ≥3/4.

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
- End-to-end event flow test
- Duplicate delivery test
- Schema evolution test (produce v2, consume with v1 reader)

### 9.7 Failure Handling
- DLQ routing + monitoring
- Consumer rebalance behavior
- Broker failure recovery

### 9.8 Monitoring & Alerts
- Consumer lag per partition
- DLQ message rate
- Producer error rate, batch size, latency

### 9.9 Uncovered Risks (MANDATORY — never empty)
| Area | Reason | Impact | Follow-up |
```

**Volume rules**:
- FAIL: always fully detailed
- WARN: up to 10; overflow to §9.9
- PASS: summary only
- §9.9 minimum: document all assumptions (especially delivery guarantee if unverified)

**Scorecard summary** (append after §9.9):
```
Scorecard: X/12 — Critical Y/3, Standard Z/5, Hygiene W/4 — PASS/FAIL
Data basis: [full context | degraded | minimal | planning]
```

---

## §10 Reference Loading Guide

| Condition | Load |
|-----------|------|
| Standard or Deep depth | `references/event-schema-patterns.md` |
| Deep depth, or consumer failure/lag signals | `references/consumer-failure-modes.md` |
| Extended anti-example matching | `references/consumer-anti-examples.md` |
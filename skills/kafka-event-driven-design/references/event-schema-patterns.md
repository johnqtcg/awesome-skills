# Kafka Event Schema Patterns

Event schema design determines the long-term maintainability of an event-driven
system. A poorly designed schema causes cascading compatibility breaks across
all consumers.

**Contents**

| § | Topic | Read it when |
|---|-------|--------------|
| [1](#1-event-envelope-pattern) | Event envelope | defining a new event's shape and metadata |
| [2](#2-schema-evolution-strategies) | Evolution & compatibility modes | choosing BACKWARD/FORWARD/FULL, or deciding deployment order |
| [3](#3-schema-format-comparison) | Format comparison | Avro vs Protobuf vs JSON Schema vs raw JSON |
| [4](#4-event-types) | Event types | event-carried state vs notification vs delta |
| [5](#5-idempotency-key-design) | Idempotency keys | consumer dedup depends on a stable key |
| [6](#6-outbox-pattern-transactional-event-publishing) | Outbox pattern | DB write and publish must not diverge |
| [7](#7-partition--key-design--hot-partitions) | Hot partitions | one partition lagging the rest |

---

## 1. Event Envelope Pattern

Every event should carry a standard envelope with metadata:

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "order.created",
  "timestamp": "2024-03-15T10:30:00Z",
  "source": "order-service",
  "correlation_id": "req-abc-123",
  "schema_version": "1.2.0",
  "payload": {
    "order_id": "ORD-12345",
    "customer_id": "CUST-678",
    "total_amount": 99.50,
    "currency": "USD"
  }
}
```

### Envelope fields, by how load-bearing they are

Not every field carries the same weight. Score them by what breaks without them,
not as one all-or-nothing "has an envelope" checkbox.

| Field | Purpose | Weight |
|-------|---------|--------|
| `event_id` | Globally unique (UUID) | **Load-bearing** — without it consumer dedup has no key at all. Only waivable when *every* consumer operation is naturally idempotent, and that must be demonstrated, not asserted. |
| `event_type` | Dot-notation domain event name | **Load-bearing on shared topics** — routing without deserialising the payload. A single-type topic already encodes it in the topic name. |
| `timestamp` | Event creation time (ISO-8601) | Strong default. Kafka's own record timestamp covers *broker/producer* time; carry an explicit one when domain time ≠ append time. |
| `source` | Producing service name | Strong default for multi-producer topics; low value on a single-producer topic. |
| `correlation_id` | Request-scoped trace ID | Strong default. Prefer propagating W3C `traceparent` in **Kafka record headers** rather than the payload, so tracing works without deserialisation. |
| `schema_version` | Payload schema version | Redundant when Schema Registry is in use — the wire format already carries the schema ID. Genuinely needed for raw-JSON topics. |

Headers vs. payload: routing and tracing metadata belongs in **record headers**
(readable without deserialising, survives format changes); anything a consumer's
business logic reads belongs in the payload under the schema. Putting everything
in the payload is common and workable — just do not treat a header-based envelope
as a missing envelope.

---

## 2. Schema Evolution Strategies

### 2.0 The direction of each mode — get this right first

Compatibility modes are named for **which side is allowed to move first**, and
the two directions are routinely stated backwards. Fix the wording in your head:

- **BACKWARD** — a reader on the **new** schema can read data written with the
  **old** schema. It says nothing about old readers. → **Upgrade consumers first.**
- **FORWARD** — a reader on the **old** schema can read data written with the
  **new** schema. → **Upgrade producers first.**
- **FULL** — both hold, so the upgrade order does not matter.

"BACKWARD guarantees old consumers can read new data" is the single most common
inversion. That is FORWARD.

### 2.1 What each mode actually permits

Per Confluent Schema Registry's compatibility rules:

| Mode | Changes allowed | Checked against | Upgrade first |
|------|-----------------|-----------------|---------------|
| `BACKWARD` (registry default) | **Delete fields**; add optional fields | Last version only | Consumers |
| `BACKWARD_TRANSITIVE` | Delete fields; add optional fields | **All** previous versions | Consumers |
| `FORWARD` | Add fields; **delete optional fields** | Last version only | Producers |
| `FORWARD_TRANSITIVE` | Add fields; delete optional fields | All previous versions | Producers |
| `FULL` | Add **and** delete optional fields | Last version only | Either order |
| `FULL_TRANSITIVE` | Add and delete optional fields | All previous versions | Either order |
| `NONE` | Anything — checks disabled | — | Governed elsewhere |

Two corrections to the folklore this table replaces:

- **BACKWARD does allow deleting a field.** The constraint is that the field must
  have been optional or carried a default, so a new reader can supply a value
  when reading old data. "BACKWARD = never delete anything" is wrong and pushes
  teams into permanent field accretion.
- **FULL does allow deletion**, of optional/defaulted fields. It is not
  "add-only". It restricts you to *optional* fields in both directions.

### 2.2 Transitive is not automatically "safest"

`*_TRANSITIVE` checks the candidate against **every** registered version, not just
the newest. That is stricter, and it is the right default when consumers may run
many versions behind (long-lived replay, event-sourced topics, mobile/edge clients
you cannot force-upgrade).

It is **not** free:

- It permanently constrains the schema to the intersection of all history. One
  bad early version can block a legitimate change forever.
- On a topic where the retention window is shorter than your deploy cadence, no
  consumer can ever encounter a schema older than the last version, so the extra
  strictness buys nothing.

Choose transitive when *old data or old readers genuinely survive across more than
one schema version*. Otherwise `BACKWARD` is a defensible, cheaper default — and
it is what the registry itself defaults to. Recommending `BACKWARD_TRANSITIVE`
unconditionally is a preference, not a correctness rule; if you recommend it,
state which of the two conditions above applies.

### 2.3 Per-format rules differ — do not generalise from Avro

The mode names are shared; the rules under them are not.

- **Avro** — designed for evolution; the resolution rules are specified. Deleting
  or adding a field is compatible when the field has a default.
- **Protobuf** — field *numbers* carry identity, not names. Renaming a field is
  wire-compatible; reusing a retired field number is a silent corruption. Reserve
  removed numbers (`reserved 5;`).
- **JSON Schema** — the most nuanced. Compatibility depends on the **content
  model** (`additionalProperties: true` = open, `false` = closed) as well as the
  mode. A reader may only add a property backward-compatibly when the **writer's**
  schema was closed — with an open writer schema, documents may already carry that
  property with a different type.

When the format is JSON Schema, verify the content model before pronouncing any
change compatible. Never port an Avro-derived verdict onto a JSON Schema subject.

### 2.4 Changes that no mode permits

- Changing a field's type incompatibly (Avro `string` → `int`)
- Deleting a **required** field with no default
- Renaming a field in a name-identified format (Avro, JSON Schema — Protobuf
  differs, see above)
- Changing the meaning of the partition key (not a schema check at all — the
  registry will happily accept it and consumer ordering will break silently)

**Solution**: create a new topic (e.g., `order.events.v2`), dual-publish during
migration, migrate consumers, then decommission the old topic.

### 2.5 Verify, don't assume

The registry will tell you. Test the candidate before deploying it:

```bash
curl -sS -X POST -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  --data @candidate.json \
  "$SR_URL/compatibility/subjects/order.events-value/versions/latest?verbose=true"
# => {"is_compatible": false, "messages": ["..."]}
```

Use `versions/latest` for a non-transitive mode; the subject's configured mode
governs which versions are actually checked. A review that asserts compatibility
without running this check must record the claim as unverified in §9.9.

---

## 3. Schema Format Comparison

| Format | Schema Registry | Evolution | Encoding | Human-readable |
|--------|:-:|:-:|:-:|:-:|
| **Avro** | Confluent, AWS Glue | Excellent | Binary, compact | No |
| **Protobuf** | Confluent | Excellent | Binary, compact | No |
| **JSON Schema** | Confluent | Good | Text, verbose | Yes |
| **Raw JSON** | None | Manual | Text, verbose | Yes |

The column is **encoding class, not a speed ranking**. Binary-vs-text is a
property of the format and holds everywhere. Avro-vs-Protobuf throughput is not:
it is decided by the language's library implementation, the payload shape (many
small optional fields versus few large strings), and whether schema resolution is
counted in the measurement — and published benchmarks disagree on the winner.
Treat them as comparable and benchmark with your own payload and client rather
than repeating a ranking.

**Recommendation**: Avro or Protobuf for high-throughput systems. JSON Schema
for lower-throughput systems where human readability matters.

**Raw JSON (no registry)** is a risk position, not an automatic defect. What
actually matters is whether *some* mechanism enforces the producer/consumer
contract. Raw JSON is defensible when **all** of these hold:

- the schema is version-controlled and reviewed elsewhere (a shared IDL, an
  OpenAPI/AsyncAPI spec, a generated struct package both sides import);
- consumers validate on read and route violations to a DLQ rather than
  half-processing;
- producer and consumer are owned by the same team, or the topic is internal to
  one deployment unit.

It is a genuine finding when the contract lives only in the producer's code, when
consumers deserialise into untyped maps, or when multiple teams consume the topic.
Score the **absence of contract enforcement**, not the absence of a registry —
a team with an external schema-governance process and validated consumers is not
running an unsafe system because they chose not to deploy Schema Registry.

---

## 4. Event Types

### 4.1 Domain Events (most common)

Represent something that happened in the business domain.

```
order.created, order.shipped, payment.processed, user.registered
```

- Past tense naming: `{entity}.{past-tense-verb}`
- Carry full relevant state at time of event
- Consumers should not need to call back to producer for additional data

### 4.2 Integration Events

Cross-service communication events with minimal payload (reference by ID).

```
order.status.changed → {order_id, new_status, changed_at}
```

- Consumers may need to fetch full entity from source service
- Lighter payload, but introduces temporal coupling

### 4.3 Event Sourcing Events

Complete state change log — the event IS the source of truth.

```
account.credited, account.debited → replaying all events reconstructs current state
```

#### Compaction destroys an event-sourced log. Use two topics.

`cleanup.policy=compact` "retains the latest value for each key" (Kafka's own
definition). Key an event log by aggregate ID — the natural choice, because it is
what gives you per-aggregate ordering — and compaction will delete every earlier
event for that aggregate and keep only the most recent one. Replay then
reconstructs the last event, not the state. **The two settings you need for
ordering and for retention are in direct conflict on a single topic**, and the
damage is silent: writes succeed, consumers work, and the history is gone the
next time the cleaner runs.

| Topic | Purpose | `cleanup.policy` | Key |
|-------|---------|------------------|-----|
| **Event log** | Immutable history, the source of truth | `delete` with retention long enough to replay from the beginning, or empty (see below) | Aggregate ID — for ordering |
| **Snapshot / state** | Latest materialised state per aggregate, to avoid replaying from zero | `compact` | Aggregate ID — here collapsing to the latest value is the point |

For genuinely unbounded retention, an **empty `cleanup.policy` list** disables
cleanup entirely — no policy is applied and segments are retained indefinitely.
`retention.ms=-1` under the default `delete` policy also retains indefinitely;
either is fine, but say which you mean, and pair unbounded retention with tiered
storage rather than local disk on any topic that actually grows.

There is one case where compaction on the event log is harmless: if every event
carries a **unique** key (event ID), nothing is ever superseded, so nothing is
compacted away. It is also pointless — you pay for the cleaner and get no
reclamation — and it forfeits per-aggregate ordering, since the key no longer
groups an aggregate's events onto one partition. Do not use it as a compromise.

#### Other constraints

- Events must be strictly ordered per aggregate (partition by aggregate ID)
- Schema changes are especially dangerous — old events must stay readable
  forever, so a transitive compatibility mode is genuinely justified here (this
  is the case §2.2 says to reserve it for)
- Deleting personal data from an append-only log is a design problem, not an ops
  task; see `consumer-anti-examples.md` AE-17 for crypto-shredding

---

## 5. Idempotency Key Design

For consumer deduplication, the `event_id` in the envelope is the primary key.

### Database-level deduplication — the marker and the side effect must share one transaction

The dedup marker is only meaningful if it commits **atomically with the work it
guards**. Marking first and processing afterwards loses the event on a crash in
between; processing first and marking afterwards double-processes on a crash in
between. Both are the same bug seen from two sides.

```sql
CREATE TABLE processed_events (
    event_id     UUID PRIMARY KEY,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

```go
// Marker insert and business write commit together, or neither happens.
func handle(ctx context.Context, db *sql.DB, ev Event) error {
    tx, err := db.BeginTx(ctx, nil)
    if err != nil {
        return err
    }
    defer tx.Rollback() //nolint:errcheck // no-op after a successful Commit

    res, err := tx.ExecContext(ctx,
        `INSERT INTO processed_events (event_id) VALUES ($1) ON CONFLICT DO NOTHING`,
        ev.EventID)
    if err != nil {
        return err
    }
    n, err := res.RowsAffected()
    if err != nil {
        return err
    }
    if n == 0 {
        return nil // already processed in a committed transaction
    }

    if err := applyBusinessWrites(ctx, tx, ev); err != nil {
        return err
    }
    return tx.Commit()
}
```

Only commit the Kafka offset after `handle` returns nil. A crash before the offset
commit redelivers the event, the marker insert conflicts, and the handler
short-circuits — that redelivery is the design working, not a failure.

This pattern requires the side effect to be **in the same database** as the
marker. If the side effect is an external API call, no local transaction can
cover it; you need an idempotency key the remote side de-duplicates on, and the
event is at-least-once end-to-end regardless of what you do locally. Say so
rather than implying the marker table solved it.

### Cache-based deduplication is a rate limiter, not a guarantee

```go
// NOT SAFE as a correctness mechanism — shown to explain why.
if processed, _ := cache.Exists(ctx, "processed:"+ev.EventID); processed {
    return nil
}
// ... process ...
cache.Set(ctx, "processed:"+ev.EventID, true, 24*time.Hour)
```

Three independent holes:

1. **Race** — two consumers (or two goroutines after a rebalance) both pass
   `Exists` before either reaches `Set`, and both process. Use an atomic
   `SET key NX` and treat "was not set" as the permission to proceed; `Exists`
   followed by `Set` is a check-then-act race by construction.
2. **Failure window** — the process can die after the side effect and before
   `Set`. On redelivery the event is processed again.
3. **TTL expiry** — a 24 h TTL means any redelivery after 24 h (replay,
   offset reset, DLQ reprocessing, a consumer that was down over a weekend)
   re-processes cleanly past the dedup check. The TTL bounds how long the
   guarantee lasts; a durable marker has no such bound.

Cache dedup is a legitimate optimisation to keep duplicate work cheap. It is not
a substitute for a transactional marker or a naturally idempotent operation, and
must never be scored as satisfying the idempotency requirement on its own.

### Natural idempotency (preferred)

Design operations to be naturally idempotent — no deduplication needed:

```go
// Idempotent: same result regardless of how many times executed
db.Exec("UPDATE orders SET status = $1 WHERE id = $2", event.NewStatus, event.OrderID)
// NOT idempotent: accumulates on each execution
db.Exec("UPDATE accounts SET balance = balance + $1 WHERE id = $2", event.Amount, event.AccountID)
```

---

## 6. Outbox Pattern (Transactional Event Publishing)

Ensure database write and event publish are atomic without distributed transactions.

**The outbox is a database transaction. Kafka is not in it.** This is the whole
point of the pattern, and it is frequently mis-taught as an application of Kafka
transactions. A Kafka transaction spans Kafka partitions (and consumer offsets)
only — it cannot include a row in PostgreSQL. If you find yourself writing
"use Kafka transactions to make the DB write and the event atomic", you have
described something Kafka cannot do.

```
1. Application writes business rows + outbox row in ONE database transaction
2. Outbox relay (separate process) reads unpublished outbox rows, produces to Kafka
3. Relay marks rows published — after the broker acknowledges
```

```sql
-- Step 1 — one database transaction, no Kafka involved:
BEGIN;
INSERT INTO orders (id, ...) VALUES (...);
INSERT INTO outbox (event_id, topic, key, payload, created_at)
VALUES (uuid_generate_v4(), 'order.events', order_id,
        '{"event_type":"order.created",...}', NOW());
COMMIT;
```

**Why**: `db.Save(order)` + `kafka.Produce(event)` is NOT atomic — if the produce
fails after the DB commit, the event is lost; if the DB commit fails after a
successful produce, consumers see an order that does not exist. Moving the event
into the same DB transaction removes both windows.

### 6.1 What the outbox guarantees, and what it does not

**Guarantees**: the event exists if and only if the business write committed.

**Does not guarantee exactly-once.** Step 3 is a second, separate commit. If the
relay produces successfully and dies before marking the row published, it will
produce the same event again on restart. The outbox is an **at-least-once**
publisher by construction. Consumers still need the idempotency of §5 — an outbox
on the producer side never removes the dedup requirement on the consumer side.

Order the relay's two steps as *produce → wait for broker ack → mark published*.
Marking first turns a crash into permanent event loss, which is exactly the
failure the pattern was adopted to prevent.

### 6.2 Relay ordering

A relay that reads outbox rows concurrently, or that uses `SKIP LOCKED` across
workers, can publish two events for the same aggregate out of order even though
both went to the same partition. If the topic's ordering guarantee matters, the
relay must serialise per partition key — typically by claiming rows grouped by
key, or by running a single relay per shard. Log-based CDC (Debezium reading the
WAL) gets this ordering from the log itself, which is the main reason to prefer
it over a polling relay for ordered topics.
---

## 7. Partition & Key Design — Hot Partitions

The decision table for *which* key to use lives in `SKILL.md` §6. This section
covers what to do when the key you picked turns out to be skewed.

### Symptoms and cause

- One partition carries many times the events of the others; its consumer lags
  while the rest idle. Group-level throughput dips by roughly 1/N rather than
  flatlining, so this hides on an aggregate dashboard — chart lag **per
  partition**.
- Cause is skewed key distribution (one tenant produces 90% of the traffic).
  Note this is *low* effective cardinality. High cardinality is not the problem,
  and no key distribution can create extra partitions — partition count is fixed
  by the topic.

### The four mitigations, and what each costs

| Fix | Keeps per-entity order? | Notes |
|-----|:---:|-------|
| Composite key (`tenant_id:entity_id`) | **Yes** — for the entity | The right answer when ordering is required per *entity* and tenant-level ordering was never needed. Spreads the hot tenant across partitions. |
| Sharded key (`hotkey:{n}` for n in 0..N) | **No** | Kafka cannot know the shards are related. Valid only when the consumer tolerates unordered events for that entity, or re-sequences them itself using a sequence number. Do not describe this as preserving ordering. |
| Dedicated topic for the hot tenant | Yes | Isolates noisy-neighbour blast radius; costs a topic plus routing logic in the producer. |
| More partitions | Yes | Helps only if the skew is coincidental hash collision, not genuine key skew. Changes key→partition mapping — see AE-12. |

### The constraint that resolves most arguments

**Per-entity Kafka-native ordering and spreading one entity across partitions
are mutually exclusive.** Kafka orders within a partition and has no notion that
two partitions relate to the same entity. When a design demands both, one of them
is not a real requirement; find out which before choosing a mitigation.

If the consumer genuinely needs both throughput and ordering for a single hot
entity, the ordering has to move into the application: carry a monotonic
`sequence_number` per entity and re-sequence (or reject gaps) on the consumer
side, as in §5's ordering-violation defence. That is a real cost — buffering,
gap detection, and a stall policy — and it should be a deliberate decision, not
a side effect of adding a shard suffix to a key.

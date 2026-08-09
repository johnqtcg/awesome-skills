# Kafka Consumer Failure Modes & Defenses

Production consumer failures that cause data loss, processing delays,
or cascading service degradation.

**Contents** — enter at the observed symptom, not at §1.

| § | Failure mode | Observed symptom |
|---|--------------|------------------|
| [1](#1-consumer-rebalance-storm) | Rebalance storm | throughput collapses, partitions churn between members |
| [2](#2-poison-message-deserialization--processing-failure) | Poison message | one partition's *committed offset* stops advancing; its lag climbs |
| [3](#3-consumer-lag-runaway) | Lag runaway | lag grows monotonically, consumer healthy |
| [4](#4-duplicate-processing) | Duplicate processing | double charges, constraint violations on redelivery |
| [5](#5-ordering-violation) | Ordering violation | events for one entity applied out of sequence |
| [6](#6-combined-defense-matrix) | Combined defense matrix | which defense covers which mode |

---

## 1. Consumer Rebalance Storm

### Trigger
Consumer joins or leaves the group → all partitions reassigned → processing
pauses during rebalance. Frequent rebalances (flapping consumers) cause
sustained processing gaps.

### Symptom
- Periodic consumer lag spikes correlated with rebalance events
- `JoinGroup` / `SyncGroup` requests in consumer logs
- `max.poll.interval.ms` exceeded → consumer kicked from group

### Defense depends on which rebalance protocol the group runs

Two protocols exist, and the correct configuration is disjoint between them.
Establish `group.protocol` before recommending anything here.

#### Classic protocol (`group.protocol=classic` — the default through Kafka 4.x)

```properties
# Cooperative sticky assignor (Kafka 2.4+) — only reassigns partitions that must move.
# Note the Java default is [RangeAssignor, CooperativeStickyAssignor], i.e. eager wins;
# you must set this explicitly to get cooperative behaviour.
partition.assignment.strategy=org.apache.kafka.clients.consumer.CooperativeStickyAssignor
```

Unlike eager rebalance (which revokes ALL partitions then reassigns), cooperative
rebalance only moves the delta — other partitions continue processing.

Rolling from eager to cooperative requires **two deploys**: first add
`CooperativeStickyAssignor` alongside the existing assignor, then remove the old
one. Switching in a single deploy leaves the group with no assignor in common.

#### New consumer protocol (`group.protocol=consumer`, GA in Kafka 4.0 — KIP-848)

The protocol is fully incremental by design; there is no eager mode to avoid and
no client-side assignor to configure. **`partition.assignment.strategy` is not
usable** — nor are `session.timeout.ms`, `heartbeat.interval.ms`, or
`enforceRebalance()`.

```properties
# client
group.protocol=consumer
# optional: pick a non-default server-side assignor
group.remote.assignor=uniform      # 'uniform' (default) or 'range'
```

Heartbeat and session timeout are **broker** configs now
(`group.consumer.heartbeat.interval.ms`, `group.consumer.session.timeout.ms`), so
"tune the session timeout" is no longer a change the application team can make
alone. `max.poll.interval.ms` remains a client config and still applies.

Full behavioural delta, migration mapping, and limitations (custom assignors are
not supported): `version-client-matrix.md` §5.

### Defense: Tune poll intervals

```properties
# Increase if processing takes longer than default (5 min)
max.poll.interval.ms=600000
# Decrease batch size to process faster per poll
max.poll.records=100
```

### Defense: Static group membership (Kafka 2.3+)

```properties
# Stable identity: a restart that completes within session.timeout.ms rejoins
# as the same member and keeps its partitions, so no rebalance is triggered.
group.instance.id=consumer-pod-1
session.timeout.ms=45000            # default 45s; raise to cover restart time
```

**It does not abolish rebalancing — it buys a window.** Kafka's own wording is
that a static member "can be used **in combination with a larger session
timeout** to avoid group rebalances caused by transient unavailability (e.g.
process restarts)". If the instance stays down past `session.timeout.ms`, the
coordinator evicts it and the group rebalances exactly as before. So:

- Size `session.timeout.ms` to cover realistic restart time (image pull, JVM
  warm-up, cache load), not to the default.
- A longer timeout is a real trade: genuine failures go undetected for that
  long, and those partitions stall meanwhile. This is a latency-vs-churn dial,
  not a free win.
- `group.instance.id` must be stable **and unique** per instance. Reusing one
  across two live consumers fences the older one; deriving it from a random
  value or a pod IP re-randomises it on every restart and silently disables the
  feature.
- Under `group.protocol=consumer` (Kafka 4.0+), `session.timeout.ms` is a broker
  config (`group.consumer.session.timeout.ms`) and is no longer yours to set.

---

## 2. Poison Message (Deserialization / Processing Failure)

### Trigger
A single malformed or unexpected message causes the consumer to fail.
Since the offset isn't committed, the message is redelivered → infinite loop.

### Symptom
- **The committed offset for one partition stops advancing** while its lag keeps
  climbing (it only sits at 1 if production to that partition has also stopped —
  under live traffic the lag grows without bound). Diagnose on the *committed
  offset*, not on the lag value.
- Repeated error logs for the same offset — that offset is the signature
- Other partitions in the same group are healthy, so aggregate throughput dips
  by roughly 1/N rather than flatlining, which is why this hides on a
  group-level dashboard

### Defense: Dead Letter Queue (DLQ)

**The DLQ publish and the offset advance must be ordered, and the publish error
must be checked.** Committing past a message whose DLQ write failed deletes it.
This is the most common way a "DLQ implementation" silently loses data — the
happy path looks identical.

```go
func consume(ctx context.Context, msg *sarama.ConsumerMessage, lastErr error) error {
    retries := getRetryCount(msg)
    if retries < maxRetries {
        return process(ctx, msg) // caller does NOT commit on a returned error
    }

    dlqMsg := &sarama.ProducerMessage{
        Topic: "order.events.dlq",
        Key:   sarama.ByteEncoder(msg.Key), // preserve key: keeps DLQ per-entity ordering
        Value: sarama.ByteEncoder(msg.Value),
        Headers: []sarama.RecordHeader{
            {Key: []byte("original-topic"), Value: []byte(msg.Topic)},
            {Key: []byte("original-partition"), Value: []byte(fmt.Sprint(msg.Partition))},
            {Key: []byte("original-offset"), Value: []byte(fmt.Sprint(msg.Offset))},
            {Key: []byte("error"), Value: []byte(lastErr.Error())},
            {Key: []byte("retry-count"), Value: []byte(fmt.Sprint(retries))},
        },
    }

    // The DLQ producer must itself be durable: acks=all + idempotent.
    // A best-effort DLQ producer turns a poison message into a lost message.
    if _, _, err := producer.SendMessage(dlqMsg); err != nil {
        // Do NOT commit. Better to block this partition — and alert — than to
        // acknowledge a message that exists nowhere.
        return fmt.Errorf("dlq publish for %s/%d@%d: %w",
            msg.Topic, msg.Partition, msg.Offset, err)
    }
    return nil // safe to commit: the message is durable in the DLQ
}
```

### DLQ and the consumer offset are still two separate commits

Even with the ordering above, the process can die after the broker acknowledges
the DLQ write and before the offset commit. On restart the message is
redelivered, fails again, and is written to the DLQ a **second** time. A DLQ is
at-least-once like everything else — the replayer must dedup on
`original-topic/partition/offset` or on `event_id`. Do not describe this design
as exactly-once.

Only a Kafka transaction covering the DLQ produce *and* `sendOffsetsToTransaction`
closes that window, and only when the DLQ topic is on the same cluster. That is
worth doing for financial events and usually not worth it elsewhere — say which
you chose.

### DLQ monitoring

- Alert on DLQ message rate > 0 (any message in DLQ needs investigation)
- Alert **separately** on DLQ publish failures — that path is the data-loss path
- DLQ topic should have long retention (30 days) for forensic analysis
- DLQ topic needs the same replication factor as the source topic; an
  under-replicated DLQ is where the evidence goes to die
- Build a DLQ replayer tool for reprocessing after fix

### When a DLQ is the wrong answer

A DLQ moves a failure from "blocks the partition" to "silently parked". That is
the right trade for most topics and the wrong one for some:

- **Strictly ordered state machines** (event-sourced aggregates, ledger entries):
  skipping a message and continuing corrupts every later event for that entity.
  Halting the partition and paging a human is the correct behaviour.
- **Low-volume, high-value topics** where an operator can act within minutes:
  stop-and-fix beats park-and-forget.
- **Failures that are obviously transient** (downstream 503): a DLQ converts a
  retryable outage into a manual replay backlog. Retry with backoff first, and
  DLQ only what survives the retry budget.

The reviewable requirement is **"there is a defined, owned policy for a message
that cannot be processed"** — DLQ, halt-and-alert, or compensating workflow. An
undefined policy is the defect; the absence of a DLQ topic specifically is not.

---

## 3. Consumer Lag Runaway

### Trigger
Consumers process slower than producers produce. Lag accumulates.
If lag exceeds retention, events are lost (retention-based deletion).

### Symptom
- `consumer_lag` metric steadily increasing
- Consumer processing time per message increasing
- Eventually: offset out of range error (data deleted by retention)

### Defense: Scale consumers

```
Max parallelism = number of partitions
If lag > threshold AND consumer_count < partition_count:
    → scale up consumers
If consumer_count == partition_count AND still lagging:
    → optimize processing or increase partition count (requires planning)
```

### Defense: Consumer batch optimization

```properties
# Process multiple messages per poll
max.poll.records=500
# Increase fetch size for throughput
fetch.min.bytes=1048576
fetch.max.wait.ms=500
```

### Defense: Backpressure on producer

If consumers structurally cannot keep up:
- Rate-limit producer
- Drop low-priority events (with explicit policy)
- Route overflow to batch processing pipeline

### Monitoring

```bash
# Check consumer lag per partition
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --describe --group my-consumer-group

# Key metrics to export:
# - consumer_lag per partition
# - records_consumed_rate
# - records_lag_max (highest lag across partitions)
```

**Derive the alert threshold; do not copy one.** A raw message count is
meaningless across workloads — 10 000 messages is four seconds of a 2 500/s
consumer and three hours of a 1/s consumer. Alert on **time-to-drain**, which is
the quantity the business actually cares about:

```
lag_seconds ≈ records_lag_max / records_consumed_rate
```

Set the threshold from the freshness the downstream consumer has committed to
(the SLO), leaving room for normal batch spikes; page when `lag_seconds` exceeds
it for longer than one deploy/rebalance cycle, so a rolling restart does not page
anyone. If no freshness SLO exists, that is the finding — an arbitrary number
invented during an incident is not a substitute for one.

Also alert on `lag_seconds` **trend**: a steadily rising figure at any absolute
value means consumption is structurally slower than production and will breach
retention eventually, which a fixed ceiling only catches once it is nearly too
late.

---

## 4. Duplicate Processing

### Trigger
At-least-once delivery + consumer crash/rebalance before commit → reprocessed
messages. Also: producer retries with `enable.idempotence=false` → duplicate
writes to Kafka.

### Symptom
- Database has duplicate records
- Financial systems show double charges
- Metrics inflated (counted twice)

### Defense: Idempotent consumer (required)

See `references/event-schema-patterns.md` §5 for patterns.

### Defense: Exactly-once semantics (Kafka 0.11+)

For Kafka-to-Kafka pipelines (consume → transform → produce). Three settings are
required and two of them are on the **consumer** — an EOS review that only checks
the producer has verified nothing:

```properties
# consumer — both are mandatory, and neither is the default
isolation.level=read_committed     # default is read_uncommitted → you WILL read aborted records
enable.auto.commit=false           # default is true → offsets would commit outside the transaction
# producer
transactional.id=order-transformer-1   # stable per logical instance, survives restart
```

```java
producer.initTransactions();           // fences any previous instance with this transactional.id
while (running) {
    ConsumerRecords<K, V> records = consumer.poll(Duration.ofMillis(100));
    if (records.isEmpty()) continue;

    producer.beginTransaction();
    try {
        for (ConsumerRecord<K, V> record : records) {
            producer.send(new ProducerRecord<>(outputTopic, transform(record)));
        }
        // ConsumerGroupMetadata — NOT a group-id string. The String overload was
        // deprecated by KIP-447 and REMOVED in Kafka 4.x; it no longer compiles.
        producer.sendOffsetsToTransaction(offsets(records), consumer.groupMetadata());
        producer.commitTransaction();
    } catch (ProducerFencedException | OutOfOrderSequenceException | AuthorizationException e) {
        producer.close();              // fatal: another instance owns this transactional.id
        throw e;
    } catch (KafkaException e) {
        producer.abortTransaction();   // abortable: reset and reprocess from the last committed offset
        resetToLastCommitted(consumer);
    }
}
```

#### Abort and fencing semantics — what actually makes it safe

- **`transactional.id` is the fencing identity.** Two live instances sharing one
  `transactional.id` do not "both work" — `initTransactions()` on the newer one
  bumps the epoch and the older one starts failing with
  `ProducerFencedException`. Deriving the id from a random UUID per process
  disables fencing entirely and is a defect that no test catches; derive it from
  a stable identity (StatefulSet ordinal, partition assignment).
- **`ProducerFencedException` is fatal, not retryable.** Close the producer and
  exit. Catching it and calling `abortTransaction()` in a loop produces a
  consumer that spins forever making no progress.
- **After an abort, seek back.** `abortTransaction()` discards the produced
  records but the consumer's in-memory position has already advanced past the
  polled batch. Without an explicit seek to the last committed offset, those
  input records are never reprocessed — a silent gap that presents as "exactly
  once" because nothing errors.
- **Aborted records still occupy offsets.** A `read_committed` consumer filters
  them, which is why consumer lag can appear non-zero on a fully drained
  transactional topic. That is not a stuck consumer.
- **Kafka 4.0+ (KIP-890, `transaction.version=2`)** bumps the producer epoch on
  *every* transaction, closing the hanging-transaction window that older brokers
  had. See `version-client-matrix.md` §6.

**Limitation**: exactly-once only holds within the Kafka ecosystem (consume from
Kafka → produce to Kafka). For Kafka → external system (database, HTTP API), the
transaction cannot cover the external write; you still need idempotent processing
at the consumer. Claiming EOS for a Kafka→DB pipeline is wrong regardless of how
the producer is configured.

---

## 5. Ordering Violation

### Trigger
Events for the same entity are *applied* out of order because:

- **Different partitions** — null key, wrong key, or a partition-count change
  moved the key. Kafka only orders within a partition, so this is the one cause
  that breaks the delivery order itself.
- **Producer retry reordering** — only when `enable.idempotence=false` and
  in-flight > 1. With idempotence on, the broker restores order.
- **Concurrent processing inside one partition** — the consumer hands records to
  a worker pool, or spawns a goroutine per record, so records that *arrived*
  ordered *complete* out of order. This is the most common real cause and the
  easiest to miss, because the Kafka side is configured perfectly.

Note what is **not** a cause: partitions being consumed at different speeds. All
events for one key live on one partition, so another partition running ahead
cannot reorder that key. It changes the relative timing of *different* entities,
which matters only if you have a cross-entity invariant — and Kafka never
promised ordering there, so that invariant needs a different mechanism.

### Symptom
- Order status goes CREATED → SHIPPED → PAID (should be CREATED → PAID → SHIPPED)
- Entity state corruption from applying events out of sequence

### Defense: Correct partition key

All events for the same entity must use the same partition key → same partition → ordered.

### Defense: Event version / sequence number

```json
{
  "event_id": "...",
  "entity_id": "ORD-123",
  "sequence_number": 3,
  "payload": {...}
}
```

Consumer checks: if received `sequence_number` != expected → buffer or reject.

---

## 6. Combined Defense Matrix

| Failure Mode | Primary Defense | Secondary Defense | Monitor |
|-------------|----------------|-------------------|---------|
| **Rebalance storm** | Classic: cooperative sticky assignor. New protocol (4.0+): incremental by default | Static membership (`group.instance.id`) | Rebalance rate, JoinGroup count |
| **Poison message** | Defined unprocessable-message policy: DLQ after N retries, or halt-and-alert for ordered state machines | Schema validation pre-process | DLQ message rate **and DLQ publish failure rate** |
| **Lag runaway** | Scale consumers (≤ partition count) | Producer backpressure | consumer_lag per partition |
| **Duplicates** | Idempotent processing (transactional marker or natural idempotency) | EOS — Kafka-to-Kafka only, needs `read_committed` + `auto.commit=false` | Duplicate count in DB |
| **Ordering** | Correct partition key | Sequence numbers | Out-of-order event rate |
| **Silent EOS gap** | Seek to last committed offset after `abortTransaction()` | Stable `transactional.id` for fencing | Transaction abort rate, `ProducerFencedException` count |
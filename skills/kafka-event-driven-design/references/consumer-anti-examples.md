# Kafka Anti-Examples

The full catalogue. SKILL.md §7 indexes these by title; the WRONG/RIGHT pairs
live here so the always-loaded skill does not carry seventeen code blocks.

**Contents** — jump to the one matching the symptom; each entry is a WRONG/RIGHT pair.

| # | Anti-example | Fires on |
|---|--------------|----------|
| [AE-1](#ae-1-producer-with-acks1-for-critical-business-events-sarama-default) | `acks=1` on critical events | sarama `NewConfig()` left as-is |
| [AE-2](#ae-2-consumer-without-idempotency-handling) | Consumer without idempotency | redelivery double-applies |
| [AE-3](#ae-3-unchecked-dlq-publish--poison-message-becomes-a-lost-message) | Unchecked DLQ publish | offset advances past an unpublished message |
| [AE-4](#ae-4-null-partition-key--loses-per-key-ordering) | Null partition key | per-key ordering lost |
| [AE-5](#ae-5-wrong-direction-assumed-for-the-compatibility-mode) | Compatibility direction inverted | BACKWARD read as FORWARD |
| [AE-6](#ae-6-kafka-issue-reported-as-application-logic-bug) | Kafka defect mislabelled | "double charge" filed as app logic |
| [AE-7](#ae-7-auto-commit-with-long-processing--reprocessing-on-crash) | Auto-commit with long processing | `enable.auto.commit=true` + slow handler |
| [AE-8](#ae-8-blocking-io-in-consumer-poll-loop) | Blocking I/O in the poll loop | HTTP/DB call between polls |
| [AE-9](#ae-9-single-partition-chosen-for-global-ordering-without-testing-the-requirement) | Single partition for "global ordering" | partition count 1 |
| [AE-10](#ae-10-consumer-group-id-reuse-across-environments) | Group ID reuse across environments | shared `group.id` |
| [AE-11](#ae-11-compacted-topic-without-tombstone-handling) | Compacted topic, no tombstone handling | `cleanup.policy=compact` |
| [AE-12](#ae-12-increasing-partitions-on-live-topic-without-migration-plan) | Partition increase on a live topic | key→partition remapping |
| [AE-13](#ae-13-no-schema-validation-at-consumer--trusting-producer-blindly) | No consumer-side schema validation | trusting the producer |
| [AE-14](#ae-14-assignor-config-carried-into-the-kafka-4x-consumer-protocol) | Kafka 4.x assignor config | `group.protocol=consumer` |
| [AE-15](#ae-15-per-process-random-transactionalid--fencing-silently-disabled) | Random `transactional.id` | fencing silently disabled |
| [AE-16](#ae-16-aborttransaction-without-seeking-back--the-silent-eos-gap) | `abortTransaction()` without seek | silent EOS gap |
| [AE-17](#ae-17-pii-on-an-infinite-retention-or-compacted-topic-with-no-deletion-path) | PII with no deletion path | regulated data + compaction |

---

## AE-1: Producer with acks=1 for critical business events (sarama default)
```go
// WRONG: sarama's NewConfig() default is WaitForLocal (= acks=1) and Idempotent=false.
// Leader acknowledges before replication; the record is lost if the leader fails.
config := sarama.NewConfig() // RequiredAcks: WaitForLocal, Idempotent: false
producer, _ := sarama.NewSyncProducer(brokers, config)

// RIGHT (sarama): all four lines are required — Validate() rejects the config otherwise
config.Producer.RequiredAcks = sarama.WaitForAll
config.Producer.Idempotent = true
config.Producer.Retry.Max = 3       // must be >= 1
config.Net.MaxOpenRequests = 1      // sarama-specific: MUST be 1 when Idempotent
```
On the Java client none of this applies: `acks=all` and idempotence are already
the defaults from 3.0, and MaxInFlight ≤ 5 preserves ordering.

## AE-2: Consumer without idempotency handling
```go
// WRONG: assumes the event is delivered once
db.Insert(event.Order)  // redelivery → constraint violation or double-charge
// RIGHT: idempotent, or a dedup marker committed in the same transaction
db.Exec("INSERT INTO orders ... ON CONFLICT (id) DO NOTHING", event.Order)
```

## AE-3: Unchecked DLQ publish — poison message becomes a lost message
```go
// WRONG: publish error dropped, offset committed anyway — if the DLQ produce
// failed the message now exists nowhere.
producer.SendMessage(dlqMsg)
session.MarkMessage(msg, "")
// RIGHT: advance only after the DLQ write is acknowledged
if _, _, err := producer.SendMessage(dlqMsg); err != nil {
    return fmt.Errorf("dlq publish %s/%d@%d: %w", msg.Topic, msg.Partition, msg.Offset, err)
}
session.MarkMessage(msg, "")
```

## AE-4: Null partition key — loses per-key ordering
```go
// WRONG: nil key → no per-key ordering. Placement is client-specific and is
// never round-robin; the defect is the lost ordering, not the shape.
producer.SendMessage(&sarama.ProducerMessage{
    Topic: "order.events", Value: sarama.ByteEncoder(data)})
// RIGHT: entity ID as partition key
producer.SendMessage(&sarama.ProducerMessage{
    Topic: "order.events", Key: sarama.StringEncoder(order.ID),
    Value: sarama.ByteEncoder(data)})
```

## AE-5: Wrong direction assumed for the compatibility mode
```
// WRONG: "BACKWARD, so old consumers can still read the new schema — deploy
// producers first." That is FORWARD. BACKWARD = NEW reader reads OLD data, so
// it needs CONSUMERS first; producers first breaks every consumer still on v1.
// ALSO WRONG: "BACKWARD forbids deleting fields." It permits deleting an
// optional/defaulted field; FULL permits adding and deleting optional fields.
// RIGHT: pick the mode from the deployment order you need, then verify the
// candidate against the registry's compatibility endpoint before deploying.
```

## AE-6: Kafka issue reported as application logic bug
```
-- WRONG: "Bug: some orders processed twice causing double charge"
-- RIGHT: "Consumer lacks idempotency: duplicate Kafka delivery double-processes"
```

## AE-7: Auto-commit with long processing — reprocessing on crash

```go
// WRONG: auto-commit commits offsets on timer, not after processing completes
// If consumer crashes between commit and processing: event is lost
// If consumer crashes after processing but before commit: event reprocessed
config.Consumer.Offsets.AutoCommit.Enable = true  // default!
```

**Right approach:**
```go
config.Consumer.Offsets.AutoCommit.Enable = false
// Manual commit after successful processing:
session.MarkMessage(msg, "")
session.Commit()
```

---

## AE-8: Blocking I/O in consumer poll loop

```go
// WRONG: HTTP call in consumer loop — if external service is slow,
// max.poll.interval.ms expires → consumer kicked from group → rebalance storm
func handleEvent(msg *sarama.ConsumerMessage) {
    resp, _ := http.Post("https://slow-service/api", ..., msg.Value)
    // 30-second timeout × 500 messages = poll interval exceeded
}
```

**Right approach:**
- Process asynchronously with bounded worker pool
- Or increase `max.poll.interval.ms` to match worst-case processing time
- Or decrease `max.poll.records` to limit work per poll

---

## AE-9: Single partition chosen for "global ordering" without testing the requirement

```
// SUSPECT: topic with 1 partition "for ordering"
// Throughput is capped at what ONE consumer instance can process, and the
// partition count cannot be raised later without breaking key→partition mapping.
kafka-topics.sh --create --topic order.events --partitions 1
```

A single partition is not wrong by itself — it is the only way Kafka provides a
total order, and plenty of low-rate control-plane or ledger topics use it
deliberately. The anti-pattern is choosing it **without testing whether global
ordering is the actual requirement**, and without deriving the throughput ceiling.

**Right approach:**

1. Test the requirement. Most "we need global ordering" cases are per-entity
   ordering plus a report that wanted a total order. Partition by entity ID.
2. If global ordering is genuinely required, derive the ceiling instead of
   quoting one: `max sustainable rate ≈ 1 / p99_processing_time`, then leave 2–3×
   headroom for spikes and replay. That figure spans orders of magnitude — an
   in-memory fold sustains six figures/sec on one partition; a handler making a
   synchronous cross-region call may not clear 50/s. **There is no universal
   events/sec threshold**, and any doc quoting one (including earlier versions of
   this skill) invented it.
3. Record that the choice is near-irreversible: growing a single-partition topic
   later needs the full AE-12 migration.

---

## AE-10: Consumer group ID reuse across environments

```
// WRONG: staging and production use same consumer group ID
// Staging consumer commits offsets that production consumer reads → skipped events
group.id=order-processor  // same in staging AND production!
```

**Right approach:**
```
group.id=order-processor-staging
group.id=order-processor-production
```

---

## AE-11: Compacted topic without tombstone handling

```go
// WRONG: consumer processes compacted topic but doesn't handle null (tombstone) values
func handleUserEvent(msg *sarama.ConsumerMessage) {
    var user User
    json.Unmarshal(msg.Value, &user)  // panic on nil value (tombstone)
}
```

**Right approach:**
```go
if msg.Value == nil {
    // Tombstone: entity was deleted
    db.Delete("users", msg.Key)
    return
}
var user User
json.Unmarshal(msg.Value, &user)
```

---

## AE-12: Increasing partitions on live topic without migration plan

```bash
# WRONG: increasing partitions changes key→partition mapping
# Events for the same key may now go to different partitions → ordering broken
kafka-topics.sh --alter --topic order.events --partitions 24  # was 12
```

**Why this is dangerous:**
Kafka uses `hash(key) % partition_count` for assignment. Changing partition count
changes which partition each key maps to. Events for order-123 that were in
partition 3 may now go to partition 15 — breaking per-entity ordering guarantee.

**Right approach:**
- Create new topic with desired partition count
- Dual-produce to both topics during migration
- Migrate consumers to new topic
- Decommission old topic

---

## AE-13: No schema validation at consumer — trusting producer blindly

```go
// WRONG: deserialize without validation — malformed events cause processing errors
var event OrderCreated
json.Unmarshal(msg.Value, &event)
processOrder(event)  // may have nil fields, wrong types, etc.
```

**Right approach:**
```go
// Validate against schema before processing
if err := schema.Validate(msg.Value); err != nil {
    routeToDLQ(msg, fmt.Errorf("schema validation failed: %w", err))
    return
}
var event OrderCreated
json.Unmarshal(msg.Value, &event)
processOrder(event)
```

---

## AE-14: Assignor config carried into the Kafka 4.x consumer protocol

```properties
# WRONG: these two cannot coexist. Under group.protocol=consumer (KIP-848),
# partition.assignment.strategy is no longer usable — as are session.timeout.ms,
# heartbeat.interval.ms, and enforceRebalance(). The line is dead config, and the
# team believes it has cooperative rebalancing configured when the server decides.
group.protocol=consumer
partition.assignment.strategy=org.apache.kafka.clients.consumer.CooperativeStickyAssignor
session.timeout.ms=45000
```

**Right approach:**
```properties
group.protocol=consumer
group.remote.assignor=uniform   # server-side; 'uniform' is the CooperativeSticky equivalent
# heartbeat/session timeouts are now BROKER configs:
#   group.consumer.heartbeat.interval.ms
#   group.consumer.session.timeout.ms
```

Migration mapping and limitations (custom client-side assignors are not
supported): `version-client-matrix.md` §5.

---

## AE-15: Per-process random `transactional.id` — fencing silently disabled

```go
// WRONG: a fresh UUID per process start means every instance owns a DIFFERENT
// transactional.id, so initTransactions() never fences the previous one.
// Two instances after a failed-but-alive pod both commit. This is the exactly-once
// configuration that produces duplicates, and nothing in the config errors.
txnID := uuid.New().String()
```

**Right approach:**
```go
// Stable identity tied to the instance's logical slot: StatefulSet ordinal,
// partition assignment, or shard number. Restarting the same slot must reuse
// the same id so the new producer fences the old epoch.
txnID := fmt.Sprintf("order-transformer-%s", os.Getenv("POD_ORDINAL"))
```

`ProducerFencedException` is **fatal**: close the producer and exit. Catching it
and calling `abortTransaction()` in a loop yields a consumer that spins forever
making no progress.

---

## AE-16: `abortTransaction()` without seeking back — the silent EOS gap

```java
// WRONG: abort discards the produced records, but the consumer's position has
// already moved past the polled batch. Those inputs are never reprocessed.
// Nothing throws. Metrics look healthy. Records are simply missing.
catch (KafkaException e) {
    producer.abortTransaction();
    // loop continues with the advanced position
}
```

**Right approach:**
```java
catch (KafkaException e) {
    producer.abortTransaction();
    // Rewind to what was actually committed, so the batch is reprocessed.
    for (TopicPartition tp : consumer.assignment()) {
        OffsetAndMetadata committed = consumer.committed(Set.of(tp)).get(tp);
        if (committed == null) {
            consumer.seekToBeginning(List.of(tp));
        } else {
            consumer.seek(tp, committed.offset());
        }
    }
}
```

Related: a `read_uncommitted` consumer (**the default**) reads the records that
abort was supposed to discard. `isolation.level=read_committed` is half of EOS
and is on the consumer, not the producer.

---

## AE-17: PII on an infinite-retention or compacted topic with no deletion path

```
# WRONG: event payload carries email, national ID, and full address; topic is
# compacted for event sourcing with no tombstone strategy. An erasure request
# has no mechanism behind it — the data is durable, replayable, and readable by
# every consumer with topic read access.
cleanup.policy=compact
retention.ms=-1
```

**Right approach:**
- Classify the data at Gate 1 before designing the topic, not after the request arrives.
- Keep identifiers, not identities: publish a stable subject ID and let consumers
  that are authorised look up the details.
- If personal fields must travel, tokenise or encrypt per-subject so destroying
  the key destroys the readable data (crypto-shredding) — this is the only
  approach that actually works against an immutable log.
- Restrict with topic ACLs; a topic anyone in the cluster can read is not access-controlled.
- If compaction is the retention model, ensure the deletion path is a tombstone
  keyed by the same key as the data, and verify `delete.retention.ms` gives
  consumers long enough to observe it.
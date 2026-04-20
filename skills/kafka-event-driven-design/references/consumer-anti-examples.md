# Extended Kafka Anti-Examples

Supplementary to the inline anti-examples in §7 of the SKILL.md.

---

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

## AE-9: Single partition for "guaranteed global ordering"

```
// WRONG: topic with 1 partition "for ordering"
// Throughput capped at single consumer — cannot scale
kafka-topics.sh --create --topic order.events --partitions 1
```

**Right approach:**
Global ordering is rarely needed. Verify whether per-entity ordering suffices
(partition by entity ID). If true global ordering is required AND throughput
is low (<100 events/sec), single partition is acceptable. Otherwise, redesign
to per-entity ordering.

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
# Kafka Consumer Failure Modes & Defenses

Production consumer failures that cause data loss, processing delays,
or cascading service degradation.

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

### Defense: Cooperative Rebalance (Kafka 2.4+)

```properties
# Use cooperative sticky assignor — only reassigns partitions that must move
partition.assignment.strategy=org.apache.kafka.clients.consumer.CooperativeStickyAssignor
```

Unlike eager rebalance (which revokes ALL partitions then reassigns), cooperative
rebalance only moves the delta — other partitions continue processing.

### Defense: Tune poll intervals

```properties
# Increase if processing takes longer than default (5 min)
max.poll.interval.ms=600000
# Decrease batch size to process faster per poll
max.poll.records=100
```

### Defense: Static group membership (Kafka 2.3+)

```properties
# Assign a stable identity — consumer restarts don't trigger rebalance
group.instance.id=consumer-pod-1
```

---

## 2. Poison Message (Deserialization / Processing Failure)

### Trigger
A single malformed or unexpected message causes the consumer to fail.
Since the offset isn't committed, the message is redelivered → infinite loop.

### Symptom
- Consumer lag stuck at exactly 1 for a specific partition
- Repeated error logs for the same offset
- All messages behind the poison message are blocked

### Defense: Dead Letter Queue (DLQ)

```go
func consume(msg *sarama.ConsumerMessage) error {
    retries := getRetryCount(msg)
    if retries >= maxRetries {
        // Route to DLQ after exhausting retries
        dlqMsg := &sarama.ProducerMessage{
            Topic: "order.events.dlq",
            Key:   sarama.ByteEncoder(msg.Key),
            Value: sarama.ByteEncoder(msg.Value),
            Headers: []sarama.RecordHeader{
                {Key: []byte("original-topic"), Value: []byte(msg.Topic)},
                {Key: []byte("original-partition"), Value: []byte(fmt.Sprint(msg.Partition))},
                {Key: []byte("original-offset"), Value: []byte(fmt.Sprint(msg.Offset))},
                {Key: []byte("error"), Value: []byte(lastError.Error())},
                {Key: []byte("retry-count"), Value: []byte(fmt.Sprint(retries))},
            },
        }
        producer.SendMessage(dlqMsg)
        return nil // commit offset, move past poison message
    }
    return process(msg) // retry
}
```

### DLQ monitoring

- Alert on DLQ message rate > 0 (any message in DLQ needs investigation)
- DLQ topic should have long retention (30 days) for forensic analysis
- Build a DLQ replayer tool for reprocessing after fix

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
# Alert: lag > 10000 messages sustained for > 5 minutes
```

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

For Kafka-to-Kafka pipelines (consume → transform → produce):

```java
// Transactional consumer + producer
producer.initTransactions();
while (true) {
    records = consumer.poll(Duration.ofMillis(100));
    producer.beginTransaction();
    for (record : records) {
        producer.send(new ProducerRecord<>(outputTopic, transform(record)));
    }
    producer.sendOffsetsToTransaction(offsets, consumerGroupId);
    producer.commitTransaction();
}
```

**Limitation**: exactly-once only works within the Kafka ecosystem (consume from
Kafka → produce to Kafka). For Kafka → external system (database), you still need
idempotent processing at the consumer level.

---

## 5. Ordering Violation

### Trigger
Events for the same entity arrive out of order because:
- Different partitions (null key or wrong key)
- Producer retry reorders messages (without idempotent producer)
- Consumer processes partitions at different speeds

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
| **Rebalance storm** | Cooperative sticky assignor | Static membership | Rebalance rate, JoinGroup count |
| **Poison message** | DLQ after N retries | Schema validation pre-process | DLQ message rate |
| **Lag runaway** | Scale consumers | Producer backpressure | consumer_lag per partition |
| **Duplicates** | Idempotent processing | Exactly-once (Kafka-to-Kafka) | Duplicate count in DB |
| **Ordering** | Correct partition key | Sequence numbers | Out-of-order event rate |
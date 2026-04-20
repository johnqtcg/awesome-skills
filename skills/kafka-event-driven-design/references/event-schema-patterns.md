# Kafka Event Schema Patterns

Event schema design determines the long-term maintainability of an event-driven
system. A poorly designed schema causes cascading compatibility breaks across
all consumers.

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

### Required metadata fields

| Field | Purpose | Why mandatory |
|-------|---------|---------------|
| `event_id` | UUID, globally unique | Enables consumer deduplication |
| `event_type` | Dot-notation domain event name | Consumer routing without deserializing payload |
| `timestamp` | ISO-8601 event creation time | Event ordering, debugging, replay |
| `source` | Producing service name | Tracing, debugging, access control |
| `correlation_id` | Request-scoped trace ID | Cross-service distributed tracing |
| `schema_version` | Semantic version of payload schema | Schema evolution, reader compatibility |

---

## 2. Schema Evolution Strategies

### 2.1 Backward Compatible (safest)

New schema can read old data. Add optional fields; never remove or rename existing fields.

```
v1: {order_id, amount, currency}
v2: {order_id, amount, currency, tax_amount}  ← new optional field
```

- Old consumers ignore `tax_amount` (unknown field)
- New consumers handle missing `tax_amount` (use default)
- **Schema Registry mode**: `BACKWARD` or `BACKWARD_TRANSITIVE`

### 2.2 Forward Compatible

Old schema can read new data. Old readers must ignore unknown fields.

```
v1 reader handles: {order_id, amount, currency, tax_amount}
v1 reader sees: {order_id, amount, currency}  (ignores tax_amount)
```

- Requires: old consumers built to skip unknown fields
- **Schema Registry mode**: `FORWARD` or `FORWARD_TRANSITIVE`

### 2.3 Full Compatible

Both backward and forward compatible. Most restrictive but safest.

- Can only add optional fields with defaults
- Cannot remove any fields
- Cannot change field types
- **Schema Registry mode**: `FULL` or `FULL_TRANSITIVE`

### 2.4 Breaking Changes (require new topic)

These changes are incompatible with any evolution strategy:
- Removing a required field
- Changing a field's type (string → int)
- Renaming a field
- Changing the partition key semantics

**Solution**: create a new topic (e.g., `order.events.v2`), dual-publish during migration, migrate consumers, then decommission old topic.

---

## 3. Schema Format Comparison

| Format | Schema Registry | Evolution | Performance | Human-readable |
|--------|:-:|:-:|:-:|:-:|
| **Avro** | Confluent, AWS Glue | Excellent | Fast (binary) | No |
| **Protobuf** | Confluent | Excellent | Fastest | No |
| **JSON Schema** | Confluent | Good | Slow (text) | Yes |
| **Raw JSON** | None | Manual | Slow | Yes |

**Recommendation**: Avro or Protobuf for high-throughput systems. JSON Schema
for lower-throughput systems where human readability matters. Raw JSON (no schema)
only for prototyping — unacceptable in production.

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

- Requires compacted topics or infinite retention
- Events must be strictly ordered per aggregate (partition by aggregate ID)
- Schema changes are especially dangerous (old events must remain readable forever)

---

## 5. Idempotency Key Design

For consumer deduplication, the `event_id` in the envelope is the primary key.

### Database-level deduplication

```sql
-- Processed events table
CREATE TABLE processed_events (
    event_id UUID PRIMARY KEY,
    processed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Before processing:
INSERT INTO processed_events (event_id) VALUES ($1) ON CONFLICT DO NOTHING;
-- If inserted (rowcount=1): process event
-- If conflict (rowcount=0): skip (already processed)
```

### Application-level deduplication

```go
func handleEvent(ctx context.Context, event Event) error {
    // Use event_id as idempotency key
    if processed, _ := cache.Exists(ctx, "processed:"+event.EventID); processed {
        return nil // already handled
    }
    // ... process event ...
    cache.Set(ctx, "processed:"+event.EventID, true, 24*time.Hour)
    return nil
}
```

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

```
1. Application writes to DB + outbox table in single DB transaction
2. Outbox relay (separate process) reads outbox, publishes to Kafka
3. Relay marks outbox rows as published
```

```sql
-- Within same DB transaction:
INSERT INTO orders (id, ...) VALUES (...);
INSERT INTO outbox (event_id, topic, key, payload, created_at)
VALUES (uuid_generate_v4(), 'order.events', order_id, '{"event_type":"order.created",...}', NOW());
-- COMMIT
```

**Why**: `db.Save(order)` + `kafka.Produce(event)` is NOT atomic — if Kafka
produce fails after DB commit, the event is lost. The outbox pattern guarantees
at-least-once delivery with DB-level atomicity.
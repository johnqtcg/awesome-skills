# Large Collection Migration Patterns for MongoDB

For collections exceeding ~10M documents, unbounded operations (updateMany,
createIndex on large fields) can degrade cluster performance. This reference
covers production-safe patterns.

---

## Table of Contents

1. [_id-Range Batched Updates](#1-_id-range-batched-updates)
2. [Aggregation Pipeline Updates](#2-aggregation-pipeline-updates)
3. [Rolling Index Build](#3-rolling-index-build)
4. [Field Type Migration](#4-field-type-migration)
5. [Shard Key Migration](#5-shard-key-migration)
6. [Monitoring During Migration](#6-monitoring-during-migration)
7. [Abort and Recovery](#7-abort-and-recovery)

---

## 1. _id-Range Batched Updates

The standard pattern for large-scale backfills. Batch by ObjectId range
to control throughput and allow other operations to proceed.

### mongosh implementation

```javascript
const batchSize = 5000;
let lastId = ObjectId("000000000000000000000000");
const maxId = db.orders.find().sort({_id: -1}).limit(1).next()._id;
let totalUpdated = 0;

while (true) {
  const result = db.orders.updateMany(
    {
      _id: {$gt: lastId, $lte: ObjectId(lastId.valueOf().substring(0,24))},
      new_field: {$exists: false}  // idempotent: skip already-migrated docs
    },
    {$set: {new_field: "default_value", _migrated: true}},
    {writeConcern: {w: "majority"}}
  );

  totalUpdated += result.modifiedCount;
  print(`Batch complete: ${totalUpdated} total, lastId: ${lastId}`);

  // Advance cursor
  const nextDoc = db.orders.find({_id: {$gt: lastId}})
    .sort({_id: 1}).skip(batchSize - 1).limit(1).next();

  if (!nextDoc) break;
  lastId = nextDoc._id;

  // Throttle: sleep between batches (ms)
  sleep(100);
}

print(`Migration complete: ${totalUpdated} documents updated`);
```

### Go application implementation

```go
const batchSize = 5000

var lastID primitive.ObjectID
for {
    filter := bson.M{
        "_id":       bson.M{"$gt": lastID},
        "new_field": bson.M{"$exists": false},
    }
    opts := options.Find().SetSort(bson.D{{Key: "_id", Value: 1}}).SetLimit(batchSize)

    cursor, err := coll.Find(ctx, filter, opts)
    if err != nil { return err }

    var batch []mongo.WriteModel
    for cursor.Next(ctx) {
        var doc bson.M
        cursor.Decode(&doc)
        id := doc["_id"].(primitive.ObjectID)
        lastID = id
        batch = append(batch, mongo.NewUpdateOneModel().
            SetFilter(bson.M{"_id": id}).
            SetUpdate(bson.M{"$set": bson.M{"new_field": "default"}}))
    }
    cursor.Close(ctx)

    if len(batch) == 0 { break }

    _, err = coll.BulkWrite(ctx, batch, options.BulkWrite().SetOrdered(false))
    if err != nil { return err }

    time.Sleep(100 * time.Millisecond)
}
```

### Tuning parameters

| Parameter | Guidance |
|-----------|----------|
| Batch size | 1000–10000; decrease if WiredTiger ticket utilization > 80% |
| Sleep between batches | 50–500ms; increase during peak hours |
| Write concern | `w: "majority"` for safety; `w: 1` acceptable for re-runnable backfills |
| Idempotency | Always use conditional filter (e.g., `{new_field: {$exists: false}}`) |
| Progress tracking | Log `lastId` after each batch for resume capability |
| Post-migration | Run `db.collection.validate()` and check `collStats` |

---

## 2. Aggregation Pipeline Updates

MongoDB 4.2+ allows aggregation expressions in update operations,
enabling complex transformations without reading documents to the client.

```javascript
// Transform field type: string amount → double
db.orders.updateMany(
  {amount: {$type: "string"}, _migrated_amount: {$ne: true}},
  [
    {$set: {
      amount_new: {$toDouble: "$amount"},
      _migrated_amount: true
    }}
  ],
  {writeConcern: {w: "majority"}}
);
```

**Key advantage**: transformation happens server-side (no client round-trip per doc).
**Limitation**: still subject to WiredTiger ticket exhaustion on large collections.
Always batch by `_id` range when operating on >1M documents.

---

## 3. Rolling Index Build

For replica sets, build indexes one member at a time to avoid
cluster-wide performance impact.

### Procedure

```
1. For each secondary:
   a. Connect directly to the secondary
   b. db.collection.createIndex({field: 1})
   c. Monitor build progress: db.currentOp({"command.createIndexes": {$exists: true}})
   d. Wait for build to complete
   e. Verify: db.collection.getIndexes()

2. Step down primary:
   rs.stepDown(60)

3. Build index on the stepped-down member (now a secondary)

4. Election promotes a secondary with the index to primary
```

**When to use**: collections >50M documents where even optimized builds
cause noticeable replication lag.

**When NOT needed**: MongoDB 4.2+ optimized builds are usually sufficient
for collections <50M documents.

---

## 4. Field Type Migration

MongoDB allows mixed types in a field, but this causes query and index problems.
Safe type migration pattern:

### Phase 1: Add new typed field

```javascript
// Add new field with correct type alongside old field
// Batch by _id range (see §1)
db.orders.updateMany(
  {_id: {$gt: lastId, $lte: batchEnd}, amount_v2: {$exists: false}},
  [{$set: {amount_v2: {$toDouble: "$amount"}}}]
);
```

### Phase 2: Application dual-read

```go
// Application reads new field, falls back to old
func getAmount(doc bson.M) float64 {
    if v, ok := doc["amount_v2"]; ok {
        return v.(float64)
    }
    // Fallback: parse old string field
    return parseAmount(doc["amount"])
}
```

### Phase 3: Application writes only new field

### Phase 4: Enforce via validator

```javascript
db.runCommand({
  collMod: "orders",
  validator: {$jsonSchema: {
    properties: {
      amount_v2: {bsonType: "double", description: "amount in USD"}
    },
    required: ["amount_v2"]
  }},
  validationLevel: "moderate"  // only new writes validated
});
```

### Phase 5: Cleanup old field (separate release)

```javascript
// Batch $unset of old field
db.orders.updateMany(
  {_id: {$gt: lastId, $lte: batchEnd}, amount: {$exists: true}},
  {$unset: {amount: ""}}
);
```

---

## 5. Shard Key Migration

### refineCollectionShardKey (4.4+)

Add suffix fields to an existing shard key (no data movement).

```javascript
db.adminCommand({
  refineCollectionShardKey: "mydb.orders",
  key: {tenant_id: 1, _id: 1}  // was {tenant_id: 1}; adding _id suffix
})
```

Instant metadata operation. No data movement. Existing chunks become
more granular over time as new splits occur.

### reshardCollection (5.0+)

Complete shard key change. Redistributes all data.

```javascript
db.adminCommand({
  reshardCollection: "mydb.orders",
  key: {customer_id: 1, _id: 1}
})
```

**Duration**: proportional to collection size. Monitor via `sh.status()`.
**Rollback**: can abort during resharding; data stays on original shard key.
**Post-reshard**: verify chunk distribution with `db.orders.getShardDistribution()`.

---

## 6. Monitoring During Migration

```javascript
// Backfill progress
db.orders.countDocuments({_migrated: true})
db.orders.estimatedDocumentCount()  // total

// WiredTiger ticket pressure
db.serverStatus().wiredTiger.concurrentTransactions

// Replication lag
rs.printSecondaryReplicationInfo()

// Index build status
db.currentOp({"msg": /Index Build/})

// Slow operations from migration
db.currentOp({"secs_running": {$gt: 10}})
```

---

## 7. Abort and Recovery

### Failed index build

```javascript
// Check for in-progress builds
db.currentOp({"command.createIndexes": {$exists: true}})

// Kill the build (4.4+)
db.killOp(<opid>)

// Verify no partial index left
db.collection.getIndexes()
```

### Failed backfill — resume from checkpoint

```javascript
// Find last processed _id
const lastMigrated = db.orders.find({_migrated: true})
  .sort({_id: -1}).limit(1).next();
// Resume from lastMigrated._id
```

### Rollback schema validator

```javascript
// Remove validator entirely
db.runCommand({collMod: "orders", validator: {}, validationLevel: "off"})
```
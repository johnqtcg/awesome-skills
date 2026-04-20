# MongoDB DDL & Index Lock Behavior Matrix

MongoDB uses intent locks and collection-level locks for DDL operations.
Lock behavior varies significantly by version, especially for index builds.

## Lock Modes

| Mode | Symbol | Blocks | Typical Operations |
|------|:------:|--------|-------------------|
| **Shared (S)** | r | Writers | Read operations |
| **Exclusive (X)** | w | All | DDL, some writes |
| **Intent Shared (IS)** | — | IX | Signals intent to read |
| **Intent Exclusive (IX)** | — | S, X | Signals intent to write |

**Key difference from RDBMS**: MongoDB locks at collection level (not table level),
and WiredTiger provides document-level concurrency for normal DML.

---

## Index Build Behavior by Version

| Version | Default Build Type | Lock Behavior | Concurrent DML? | Notes |
|---------|-------------------|---------------|:----------------:|-------|
| **< 4.0** | Foreground | Exclusive (X) on collection | **No** | Blocks all reads and writes |
| **4.0–4.1** | `background: true` option | Intent locks only | Yes (slow build) | Background builds may miss documents |
| **4.2+** | Optimized (hybrid) | Brief exclusive at start/end | **Yes** | Holds intent lock during build; brief X at start and finish |
| **4.2+ replica set** | Rolling build | Same as above, per-member | **Yes** | Build one member at a time for zero-downtime |

### 4.2+ Optimized Index Build Details

```
Start: Acquire brief Exclusive lock → initialize build metadata
Build: Hold Intent Exclusive → scan documents, build in background
       Concurrent reads and writes proceed normally
Commit: Acquire brief Exclusive lock → commit index to catalog
```

- The exclusive lock at start and commit is milliseconds (metadata only)
- The build phase allows full concurrent DML
- If interrupted (e.g., server restart), the build resumes automatically
- `background: true` is ignored on 4.2+ (all builds use optimized method)

### Rolling Index Build (Replica Set)

For zero-downtime index builds on large collections:

1. Build index on each secondary one at a time
2. Step down primary, build on the stepped-down member
3. Step up a secondary that already has the index

This avoids any replication lag impact on the primary.

---

## Collection-Level DDL Operations

| Operation | Lock | Blocks DML? | Notes |
|-----------|------|:-----------:|-------|
| `createIndex()` (4.2+) | Brief X → IX → Brief X | Brief only | Optimized hybrid build |
| `createIndex()` (< 4.2, foreground) | X (entire build) | **Yes** | Blocks everything |
| `createIndex({background: true})` (< 4.2) | IS/IX | No (slow) | May miss concurrent inserts |
| `dropIndex()` | Brief X | Brief | Instant metadata removal |
| `dropIndexes()` | Brief X | Brief | Drops all non-_id indexes |
| `collMod` (validator change) | X | Brief | Brief exclusive lock for metadata |
| `collMod` (TTL change) | X | Brief | Brief exclusive lock |
| `renameCollection` (same DB) | X on both | Brief | Instant rename |
| `renameCollection` (cross DB) | X on both | **Yes** | Copies all documents (slow) |
| `drop()` | X | Brief | Instant metadata removal |
| `compact` | X | **Yes** | Rewrites collection; blocks all ops |

---

## Sharding Operations

| Operation | Lock | Impact | Version |
|-----------|------|--------|---------|
| `reshardCollection` | Brief X at cutover | Minimal during resharding | 5.0+ |
| `refineCollectionShardKey` | Brief X | Instant metadata change | 4.4+ |
| Chunk migration (balancer) | No collection lock | May increase replication lag | All |
| `moveChunk` (manual) | No collection lock | Targeted chunk move | All |

### reshardCollection (5.0+)

Online shard key change. Creates a new sharded collection in background,
streams data, then atomically swaps at cutover. Brief exclusive lock at
the final swap moment.

```javascript
db.adminCommand({
  reshardCollection: "mydb.orders",
  key: {customer_id: 1, _id: 1}
})
```

**Limitations**: cannot reshard during another resharding operation. May take
hours for large collections. Monitor via `sh.status()` and `currentOp`.

---

## Update Operations Lock Behavior

| Operation | Lock | Blocks Other Writes? | Notes |
|-----------|------|:-------------------:|-------|
| `updateOne()` | Document-level (IX) | No | WiredTiger document-level |
| `updateMany()` | Document-level (IX) per doc | No (but holds tickets) | Yields between documents |
| `bulkWrite()` | Document-level (IX) per doc | No (but holds tickets) | Ordered: sequential; Unordered: parallel |
| Aggregation pipeline update | Document-level (IX) per doc | No | 4.2+ `$set`, `$unset`, `$replaceRoot` |

### WiredTiger Ticket Exhaustion

MongoDB limits concurrent operations via WiredTiger read/write tickets
(default: 128 each). A long-running `updateMany()` on millions of documents
holds a write ticket for the entire operation, reducing available tickets
for other clients.

**Mitigation**: batch by `_id` range with explicit pauses between batches.

---

## Monitoring During Migration

```javascript
// Index build progress
db.currentOp({$or: [
  {"command.createIndexes": {$exists: true}},
  {"msg": /Index Build/}
]})

// Replication lag
rs.printReplicationInfo()
rs.printSecondaryReplicationInfo()

// Lock contention
db.serverStatus().locks
db.currentOp({"waitingForLock": true})

// WiredTiger ticket usage
db.serverStatus().wiredTiger.concurrentTransactions

// Collection stats for migration verification
db.collection.stats()
db.collection.getIndexes()
```
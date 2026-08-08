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
| **4.2+ replica set** | **Replicated** (not rolling) | Same as above, on every member concurrently | **Yes** | All data-bearing members build at once; the primary reports the index ready once a majority finish |

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

### Replicated build is the default — and it is not a rolling build

On a replica set, `createIndex` on the primary builds on **every data-bearing member
concurrently**. That is the recommendation, and nothing else is required.

```javascript
db.orders.createIndex({status: 1}, {name: "idx_status"});   // on the PRIMARY
rs.printSecondaryReplicationInfo();                          // watch per-secondary lag
```

**A rolling build is a different, manual procedure**, and the version of it that used to
appear here could not run: its first step was "build the index on each secondary", and a
replica-set secondary rejects writes with `NotWritablePrimary` (measured on a live
3-member set). A real rolling build takes each member **out of the set** — shut it down,
restart it as a standalone on a different port, build, restore its configuration, wait
for it to catch up — which costs a voting member for the whole window and is slower than
the default.

Full procedure and the conditions that justify it:
`large-collection-migration.md` §3.

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

MongoDB bounds concurrent storage-engine operations with read/write tickets. Two things
about them are commonly stated wrong, and both were wrong here:

* **The pool is not a fixed 128.** From MongoDB 7.0 the server sizes it dynamically and
  adjusts it under load. Measured on live containers: `totalTickets` came back as **10**
  on both 7.0 and 8.0 for the same workload — a number that says more about the host than
  about any documented default. Never plan against a constant.
* **`available: 0` is not by itself an overload signal** on 7.0+. With a dynamically
  sized pool the server deliberately runs the pool near saturation; what matters is
  whether operations are *queueing* and for how long.

**The metric moved.** Reading the wrong path yields `undefined`, which is easy to mistake
for "no pressure":

| Version | Path | Verified |
|---------|------|----------|
| 7.0 | `db.serverStatus().wiredTiger.concurrentTransactions` | present; `queues.execution` absent |
| 8.0 | `db.serverStatus().queues.execution` | present; `wiredTiger.concurrentTransactions` **absent** |

```javascript
// Version-agnostic read, with the queueing signal that actually matters
const ss = db.serverStatus();
const q = (ss.queues && ss.queues.execution) || ss.wiredTiger.concurrentTransactions;
printjson({
  readTotal:  q.read.totalTickets,  readOut:  q.read.out,
  writeTotal: q.write.totalTickets, writeOut: q.write.out,
  readQueued:  q.read.queueLength,  writeQueued: q.write.queueLength
});
```

**Mitigation**: batch, and pause between batches. A long unbounded `updateMany()` holds
a write ticket for its whole duration; a batched one releases it between batches.

---

## Monitoring During Migration

```javascript
// Index build progress
db.currentOp({$or: [
  {"command.createIndexes": {$exists: true}},
  {"msg": /Index Build/}
]})

// Replication LAG -- per secondary. rs.printReplicationInfo() is NOT this: it reports
// the oplog window of the member you are connected to, which says how much history is
// retained, not how far behind anyone is.
rs.printSecondaryReplicationInfo()

// Lock contention
db.serverStatus().locks
db.currentOp({"waitingForLock": true})

// Ticket usage -- the path differs by version; see the table above
db.serverStatus().queues.execution               // 8.0
db.serverStatus().wiredTiger.concurrentTransactions   // 7.0

// Collection stats for migration verification
db.collection.stats()
db.collection.getIndexes()
```
# Extended Migration Anti-Examples for MongoDB

Supplementary to the inline anti-examples in §7 of the SKILL.md.

---

## AE-7: dropIndex on production without checking query plans

```javascript
// WRONG: dropping an index that active queries depend on
db.orders.dropIndex("idx_customer_status")
// Queries using this index switch to COLLSCAN → latency spikes
```

**Right approach:**
```javascript
// Check index usage first
db.orders.aggregate([{$indexStats: {}}])
// If $indexStats shows zero ops, safe to drop. Otherwise, create replacement first.
```

---

## AE-8: renameCollection across databases on large collection

```javascript
// WRONG: cross-database rename copies ALL documents (not a metadata rename)
db.adminCommand({renameCollection: "olddb.orders", to: "newdb.orders"})
// On 50M docs, this locks both databases for the entire copy
```

**Right approach:**
Same-database rename is instant (metadata only). For cross-database:
use `$merge` or application-level migration with batched reads/writes.

---

## AE-9: Mixed write concern in multi-step migration

```javascript
// WRONG: step 1 uses w:majority, step 2 uses w:1 — if primary fails after step 2,
// step 2 data is lost but step 1 data survives → inconsistent state
db.orders.updateMany(filter1, update1, {writeConcern: {w: "majority"}})
db.orders.updateMany(filter2, update2, {writeConcern: {w: 1}})
```

**Right approach:**
Use consistent write concern across all migration steps. If `w:1` is chosen
for performance, document that ALL steps use `w:1` and the entire migration
is re-runnable.

---

## AE-10: compact command on production replica set member

```javascript
// WRONG: compact holds exclusive lock for entire operation — blocks all reads and writes
db.runCommand({compact: "orders"})
```

**Why this is dangerous:**
`compact` rewrites the collection's storage. Holds exclusive lock for the
full duration. On a 100GB collection, this can be hours.

**Right approach:**
If compaction is needed, perform on one secondary at a time (step down,
compact, rejoin). Or use `resync` for a fresh copy from another member.

---

## AE-11: Schema validator with validationLevel "strict" on legacy collection

```javascript
// WRONG: strict validation rejects updates to ANY document that doesn't match schema
// — even if the update itself is valid, the full document must pass validation
db.runCommand({
  collMod: "orders",
  validator: {$jsonSchema: {required: ["customer_id", "amount", "status"]}},
  validationLevel: "strict"
})
// Existing documents missing "status" can't be updated at all — even for unrelated fields
```

**Right approach:**
```javascript
// Use "moderate" first: validates only inserts and updates, not existing doc shape
db.runCommand({
  collMod: "orders",
  validator: {$jsonSchema: {required: ["customer_id", "amount", "status"]}},
  validationLevel: "moderate"
})
// After backfill confirms all docs have required fields, switch to "strict"
```

---

## AE-12: Shard key migration via manual chunk operations

```javascript
// WRONG: manually moving chunks to simulate shard key change
// This doesn't change the shard key — queries still route by old key
sh.moveChunk("mydb.orders", {old_key: MinKey}, "shard02")
```

**Right approach (5.0+):**
```javascript
db.adminCommand({
  reshardCollection: "mydb.orders",
  key: {new_key: 1, _id: 1}
})
```

**Right approach (< 5.0):**
Create new collection with desired shard key, migrate data via application,
swap at cutover. There is no in-place shard key change before 5.0.

---

## AE-13: Index build without monitoring replication lag

```javascript
// WRONG: build index on primary without checking impact on secondaries
db.orders.createIndex({field: 1})
// Secondary replication falls behind → reads from secondaries return stale data
// In worst case, secondaries enter RECOVERING state
```

**Right approach:**
```javascript
// Monitor lag during build
rs.printSecondaryReplicationInfo()
// If lag > threshold, consider rolling build pattern (one member at a time)
```
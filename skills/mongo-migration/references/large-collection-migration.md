# Large Collection Migration Patterns for MongoDB

For collections exceeding ~10M documents, unbounded operations (updateMany,
createIndex on large fields) can degrade cluster performance. This reference
covers production-safe patterns.

---

## Table of Contents

1. [Batched Backfills](#1-batched-backfills--advance-by-observed-rows-never-by-arithmetic)
2. [Aggregation Pipeline Updates](#2-aggregation-pipeline-updates)
3. [Index Builds on a Replica Set](#3-index-builds-on-a-replica-set)
4. [Field Type Migration](#4-field-type-migration)
5. [Shard Key Migration](#5-shard-key-migration)
6. [Monitoring During Migration](#6-monitoring-during-migration)
7. [Abort and Recovery](#7-abort-and-recovery)

---

## 1. Batched Backfills — advance by observed rows, never by arithmetic

> **The batching rule, stated once.** Use **predicate batching**: re-query the
> migration's own predicate (`{field: {$exists: false}}`) for each batch. It carries no
> cursor, needs no stored state, resumes for free, and is correct for **any** `_id` BSON
> type. A `$gt` keyset over `_id` is an *optimisation*, permitted only once Gate 1 has
> proved the collection holds a single `_id` type — and if you take it, the cursor must
> come from the batch just processed. `$gt` type-brackets, so a keyset over a mixed-type
> `_id` silently strands every value of a different type (measured: 30 of 60 documents).


The standard pattern for large-scale backfills. Two properties make it correct, and the
version this file shipped before 2026-08 had neither:

1. **There is no cursor by default.** Each batch is selected by re-querying the
   migration's own predicate. Only the `$gt` keyset optimisation carries a cursor, and
   then it must come from the batch just processed — never a computed bound, never a
   global `max()`.
2. **The batch predicate is the migration's own precondition** (`new_field` absent), so
   progress is monotonic and a resumed run needs no stored state at all.

### What was here before, and why it could not work

```javascript
// WRONG — shipped in this file until 2026-08. Two independent defects.
_id: {$gt: lastId, $lte: ObjectId(lastId.valueOf().substring(0,24))}
```

* `ObjectId.prototype.valueOf()` returns an **object**, not a hex string. `.substring` is
  `undefined`, so this line throws `TypeError: lastId.valueOf().substring is not a
  function` on the first iteration. Verified on mongosh against MongoDB 7.0 and 8.0.
* Had it returned the hex string, `ObjectId(hex)` reconstructs **the same ObjectId**, so
  the range reduces to `_id > lastId AND _id <= lastId` — always empty. The loop would
  then have advanced its cursor with `.skip(batchSize - 1)` and updated nothing, batch
  after batch, reporting success.

Both are in `scripts/tests/test_mongo_server_matrix.py` as regression probes.

### mongosh implementation — no cursor at all

```javascript
const batchSize = 5000;
let totalUpdated = 0;

while (true) {
  // No $gt, no stored position. The predicate IS the cursor: a document that has been
  // updated stops matching, so every iteration lands on the first unfinished document.
  const batch = db.orders.find({new_field: {$exists: false}}, {_id: 1})
                  .sort({_id: 1}).limit(batchSize).toArray();
  if (batch.length === 0) break;

  const ids = batch.map(d => d._id);
  totalUpdated += db.orders.updateMany(
    {_id: {$in: ids}, new_field: {$exists: false}},   // idempotent under re-run
    {$set: {new_field: "default_value"}},
    {writeConcern: {w: "majority"}}
  ).modifiedCount;

  sleep(100);   // throttle
}
print(`Migration complete: ${totalUpdated} documents updated`);
```

**Index it, but not the way you might expect.**

```javascript
// Compound: the equality-ish predicate first, the sort key second. Documents missing
// new_field index as null, so they cluster at the front and the sort is served by the
// index rather than by a blocking SORT stage.
db.orders.createIndex({new_field: 1, _id: 1}, {name: "idx_backfill_tmp"});
// ... run the backfill ...
db.orders.dropIndex("idx_backfill_tmp");
```

Measured on 8.0 with the index in place: `IXSCAN → FETCH → LIMIT`, no `SORT` stage,
25 keys examined for 25 documents returned.

Three things that look reasonable here and are not:

* **A partial index on `_id` is rejected.** `partialFilterExpression` is not a valid
  option for the `_id` index — `InvalidIndexSpecificationOption`.
* **`$exists: false` is not a supported `partialFilterExpression` operator at all**, on
  any key — `CannotCreateIndex`. The supported set is `$eq`, `$exists: true`,
  `$gt`/`$gte`/`$lt`/`$lte`, `$type`, `$and`, `$or`, `$in`.
* **`dropIndex({_id: 1})` targets the system `_id` index**, which cannot be dropped —
  `InvalidOptions: cannot drop _id index`. Name the temporary index and drop it by name.

All three verified on live 8.0.

### The `$gt` keyset optimisation — and when it is unsafe

Re-querying from the front each iteration is O(batches × index-seek). That is cheap with
the index above, but on a very large collection a keyset cursor avoids even that:

```javascript
// excerpt: ONLY valid when every _id in the collection is the SAME BSON type
if (lastId !== null) q._id = {$gt: lastId};
lastId = ids[ids.length - 1];
```

**This silently skips documents when `_id` values span more than one BSON type.**
MongoDB sorts across types in a fixed order, but the comparison *operators* use **type
bracketing**: `$gt` only matches values of the same BSON type as its operand. So once
the cursor lands on an integer, `{$gt: <int>}` never reaches the ObjectIds that sort
after every integer.

Measured on live 8.0 — 30 integer `_id`s and 30 ObjectId `_id`s, batch size 25:

| Loop | Migrated | Missed |
|------|:--------:|:------:|
| cursorless (above) | 61 / 61 | 0 |
| `$gt` keyset | 30 / 60 | **30 — every ObjectId** |

`db.orders.countDocuments({_id: {$gt: 29}})` returns **0** on that collection, even
though thirty ObjectIds sort after every integer.

So use the `$gt` form only after confirming the collection has a single `_id` type —
Gate 1 in `SKILL.md` asks for this, and the check is one query:

```javascript
db.orders.aggregate([{$group: {_id: {$type: "$_id"}, n: {$sum: 1}}}]);
// more than one row => use the cursorless loop
```

Mixed-type `_id` is rare but not exotic: it arises from imports, from an application
that switched key strategies, and from test data that leaked into production. When the
aggregation returns more than one row, the cursorless loop is the only correct choice
offered here.

### Resuming an interrupted run

**Do not persist a cursor, and never resume from `max(_id)` of the migrated set.** A
document already carrying `new_field` at the top of the key range — from an earlier
partial run, or from an application already dual-writing — pushes that maximum past
everything unprocessed below it, and those documents are never revisited.

The predicate is the resume point. Just restart the loop — there is no cursor to
restore. Documents that already have `new_field` no longer match, so the first batch
lands on the first unfinished document. The only cost is one index seek. (If you took
the `$gt` optimisation, restart with the cursor unset; the predicate still does the
work.)

If you must report progress, count rather than store a position:

```javascript
db.orders.countDocuments({new_field: {$exists: false}});   // remaining
```

### Go implementation

Same shape as the mongosh loop, and for the same reason: **no `$gt`**. The prose above
is not advice the driver is exempt from — `$gt` type-brackets on the server, so a Go
keyset over `_id` strands whole BSON type classes exactly as the shell one does.

```go
const batchSize = 5000

// Write concern belongs on the handle, not left to the driver default.
coll := db.Collection("orders",
    options.Collection().SetWriteConcern(writeconcern.Majority()))

for {
    // The predicate selects the batch AND is the resume point. No cursor variable
    // exists, so there is nothing to carry across a restart and nothing to type-bracket.
    filter := bson.M{"new_field": bson.M{"$exists": false}}

    opts := options.Find().
        SetSort(bson.D{{Key: "_id", Value: 1}}).
        SetLimit(batchSize).
        SetProjection(bson.M{"_id": 1})

    cursor, err := coll.Find(ctx, filter, opts)
    if err != nil {
        return fmt.Errorf("find batch: %w", err)
    }

    // `any`, not primitive.ObjectID: a collection may hold _id values of several BSON
    // types, and a type assertion panics on the first document that is not an ObjectID.
    var docs []struct {
        ID any `bson:"_id"`
    }
    if err := cursor.All(ctx, &docs); err != nil {
        return fmt.Errorf("decode batch: %w", err)   // never ignore this
    }
    if len(docs) == 0 {
        return nil                                   // no rows left: done
    }

    ids := make([]any, len(docs))
    for i, d := range docs {
        ids[i] = d.ID
    }

    if _, err := coll.UpdateMany(ctx,
        bson.M{"_id": bson.M{"$in": ids}, "new_field": bson.M{"$exists": false}},
        bson.M{"$set": bson.M{"new_field": "default"}},
    ); err != nil {
        return fmt.Errorf("update batch: %w", err)
    }

    time.Sleep(100 * time.Millisecond)
}
```

The `$gt` optimisation is available here too, under the same precondition and with the
same audit trail — see the section above. If you take it, the type check belongs in the
program, not in a comment:

```go
// Only after proving the collection has ONE _id BSON type.
//
// NOT Distinct(ctx, "_id", ...): _id is unique, so that asks for every _id in the
// collection, not for the set of types. On anything large it also risks breaching the
// 16 MB BSON limit the distinct command is bound by. Group on the type instead, and
// stop at two -- one is all that may come back.
cur, err := coll.Aggregate(ctx, mongo.Pipeline{
    {{Key: "$group", Value: bson.M{"_id": bson.M{"$type": "$_id"}}}},
    {{Key: "$limit", Value: 2}},
})
if err != nil {
    return fmt.Errorf("probe _id types: %w", err)
}
var types []bson.M
if err := cur.All(ctx, &types); err != nil {
    return fmt.Errorf("decode _id types: %w", err)
}
if len(types) != 1 {
    return errors.New("mixed _id types: a $gt keyset cursor would skip documents")
}
```

### One value for all, or a value per document?

The loop above issues a single `UpdateMany` per batch because every document receives the
same value. That is the cheap case: one command, one round trip.

When each document needs a **different** value — a computed migration rather than a
constant — use `BulkWrite` with one model per document, still bounded by the same batch:

```go
// `docs` and `coll` come from the loop above. Restated here so the block compiles on
// its own -- an earlier revision referenced a handle the surrounding example had
// renamed, and nothing in the test suite compiled Go, so it shipped.
var docs []struct {
    ID any `bson:"_id"`
}
models := make([]mongo.WriteModel, 0, len(docs))
for _, d := range docs {
    models = append(models, mongo.NewUpdateOneModel().
        SetFilter(bson.M{"_id": d.ID, "new_field": bson.M{"$exists": false}}).
        SetUpdate(bson.M{"$set": bson.M{"new_field": derive(d)}}))
}
// Unordered: a single failing document does not abandon the rest of the batch.
// `coll` is the write-concern-carrying handle built above -- the same one the loop
// uses. An earlier revision of this file called it wcColl here and coll there, which
// simply did not compile.
if _, err := coll.BulkWrite(ctx, models,
    options.BulkWrite().SetOrdered(false)); err != nil {
    return fmt.Errorf("bulk write batch: %w", err)
}
```

`SetOrdered(false)` is the part worth deciding deliberately: ordered stops at the first
error, which on a backfill means one bad document halts the batch. Unordered reports the
failures and completes the rest — check `BulkWriteException.WriteErrors` rather than
treating a non-nil error as total failure.

If the transformation can be expressed server-side, prefer an aggregation-pipeline update
(§2) over either: no document leaves the server.

### Tuning parameters

| Parameter | Guidance |
|-----------|----------|
| Batch size | 1000–10000; lower it if ticket utilisation climbs (§5, and note the metric moved in 8.0) |
| Sleep between batches | 50–500ms; increase during peak hours |
| Write concern | `w: "majority"` for safety; `w: 1` acceptable only for a re-runnable backfill |
| Idempotency | The batch predicate IS the idempotency (`{new_field: {$exists: false}}`) |
| Resume | Just re-run: there is no cursor to restore, and the predicate skips finished documents |
| Post-migration | `collStats`, and a **counted** check that zero documents still match the predicate |

**Do not finish with `db.collection.validate()` as a routine step.** It takes an
exclusive lock on the collection and can run for a long time on a large one — it is a
corruption check, not a migration check. If you need it, run it on a secondary. To
confirm a backfill did its job, count the documents that still match the predicate.

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
Always batch when operating on >1M documents — by re-querying the pipeline's own
predicate. An `_id` range is not the mechanism: `$gt` type-brackets (§1), so a cursor
over `_id` strands every `_id` of a different BSON type.

---

## 3. Index Builds on a Replica Set

### Default: let the build replicate. This is the recommendation.

Since MongoDB 4.2 a `createIndex` issued on the primary runs as a **replicated build**:
every data-bearing member builds simultaneously, and the primary does not report the
index as ready until a majority have finished. It holds an exclusive lock only at the
start and end of the build, not for its duration.

```javascript
// On the PRIMARY. Nothing else is required for a replica set.
db.orders.createIndex({email: 1}, {name: "idx_email"});
```

Verified on a live 3-member set (MongoDB 8.0): the index appears on the secondaries
without any per-member action.

**"Replicated build" and "rolling build" are different things.** The 4.2+ change made
the *default* build far cheaper; it did not make it a rolling build. Text that says
"4.2+ uses rolling builds by default" conflates the two and leads readers to skip the
default path in favour of a procedure they do not need.

### What was here before, and why it could not work

```
WRONG — shipped in this file until 2026-08:
  1. For each secondary:
     a. Connect directly to the secondary
     b. db.collection.createIndex({field: 1})
```

A replica-set secondary rejects writes. Running step (b) returns
`NotWritablePrimary: not primary` — verified against a live 3-member set on MongoDB 8.0.
The procedure could not be executed as written, and the fixture that covered it recorded
"no violations".

### Real rolling build — when you genuinely need one

A rolling build takes the member **out of the replica set** so the build is a local,
unreplicated operation. That is the step the old text was missing, and it is what makes
the rest of the procedure necessary.

For each **secondary**, one at a time:

1. Shut the member down cleanly (`db.adminCommand({shutdown: 1})` on that member).
2. Restart it as a **standalone**: remove `--replSet`, and start it on a **different
   port** so no application or set member can reach it as though it were still a member.
3. Connect to that standalone port and build the index there.
4. Shut it down again; restart it with its original port and `--replSet`.
5. Wait for it to rejoin and catch up before touching the next member — `rs.status()`
   must show `SECONDARY`, and check its lag (§6) rather than assuming.

Then for the **primary**: `rs.stepDown()`, wait for a new primary to be elected, and
treat the former primary as a secondary — steps 1–5 above.

### Why this is an exception, not a default

- **You lose a voting member for the whole build.** On a 3-member set that leaves no
  redundancy: a second failure during the window costs you the primary.
- **It takes longer than the default** — the builds are serial across members instead of
  concurrent, plus a restart and a catch-up per member.
- **Every step is manual and stateful.** A member left as a standalone, or restarted on
  the wrong port, is an outage.

Reach for it only when a replicated build is demonstrably the problem — sustained CPU
saturation or WiredTiger cache pressure during the build that you have measured, not
assumed. Collection size alone is not the trigger.

---

## 4. Field Type Migration

MongoDB allows mixed types in a field, but this causes query and index problems.
Safe type migration pattern:

### Phase 1: Deploy compatible code FIRST

The application must read both shapes and write both **before** any document is
converted. Doing the backfill first leaves a window in which old instances keep writing
`amount` as a string, so the backfill drains a set the old code is still refilling and
"zero left" is a reading of one instant.

```go
// Reads either shape. Deployed before anything is converted, and it must stay
// deployed for the whole migration -- it is what makes the backfill's zero stable.
func getAmount(doc bson.M) float64 {
    if v, ok := doc["amount_v2"].(float64); ok {
        return v
    }
    return parseAmount(doc["amount"])   // fallback: the un-migrated string
}

// Writes BOTH while the migration is in flight.
func setAmount(update bson.M, v float64) {
    update["amount_v2"] = v
    update["amount"] = strconv.FormatFloat(v, 'f', -1, 64)
}
```

### Phase 2: Rollout barrier

Confirm every instance runs that code before touching data. One old instance is enough
to make Phase 3's count meaningless.

### Phase 3: Backfill the existing documents

```javascript
// Batched by the predicate itself. NOT an _id range: $gt type-brackets (§1), so a
// cursor over _id strands every _id whose BSON type differs from the cursor's.
while (true) {
  const batch = db.orders.find(
      {amount: {$type: "string"}, amount_v2: {$exists: false}}, {_id: 1})
    .sort({_id: 1}).limit(5000).toArray();
  if (batch.length === 0) break;
  const ids = batch.map(d => d._id);
  db.orders.updateMany(
    {_id: {$in: ids}, amount_v2: {$exists: false}},
    [{$set: {amount_v2: {$toDouble: "$amount"}}}],
    {writeConcern: {w: "majority"}}
  );
  sleep(100);
}

// Must be 0, and must STAY 0 on a re-check. It can only stay 0 because Phase 2
// guaranteed nothing writes the old shape unaccompanied any more.
db.orders.countDocuments({amount: {$type: "string"}, amount_v2: {$exists: false}});
```

### Phase 4: Cut reads over, then enforce via validator

```javascript
db.runCommand({
  collMod: "orders",
  validator: {$jsonSchema: {
    properties: {
      amount_v2: {bsonType: "double", description: "amount in USD"}
    },
    required: ["amount_v2"]
  }},
  validationLevel: "moderate"  // exempts ONLY updates to already-invalid documents
});
```

### Phase 5: Cleanup old field (separate release)

```javascript
// Batch $unset of the old field, by predicate -- the field's own presence is the
// cursor here, and it is correct for any _id BSON type.
// $unset is NOT reversible: the value is gone unless it was captured first. Run this
// only in a release after the new field is proven.
while (true) {
  const batch = db.orders.find({amount: {$exists: true}}, {_id: 1})
                  .sort({_id: 1}).limit(5000).toArray();
  if (batch.length === 0) break;
  const ids = batch.map(d => d._id);
  db.orders.updateMany(
    {_id: {$in: ids}, amount: {$exists: true}},
    {$unset: {amount: ""}},
    {writeConcern: {w: "majority"}}
  );
  sleep(100);
}
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

// Ticket pressure. The path moved in 8.0 -- reading the wrong one returns undefined,
// which looks exactly like "no pressure".
const q = (db.serverStatus().queues || {}).execution
       || db.serverStatus().wiredTiger.concurrentTransactions;

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

// Kill the build. `<opid>` is not valid JavaScript -- take the opid from the
// currentOp output above and pass the number.
db.killOp(12345)

// Verify no partial index left
db.collection.getIndexes()
```

### Failed backfill — resume

```javascript
// WRONG: resuming from the highest already-migrated _id. Any document that carried the
// field before this run -- an earlier partial pass, an app already dual-writing, a
// default -- sits at the top of the range and pushes this maximum past everything
// unprocessed below it. Those documents are never revisited and the loop still exits
// cleanly, reporting success.
const lastMigrated = db.orders.find({_migrated: true}).sort({_id: -1}).limit(1).next();

// RIGHT: there is no checkpoint to restore. The predicate IS the resume point --
// just re-run the predicate-batched loop -- there is no cursor to restore, and
// finished documents no longer match the predicate.
db.orders.countDocuments({new_field: {$exists: false}});   // what is left to do
```

The same reasoning rules out a stored-cursor collection: a cursor written before the
batch commits can claim more progress than was made, and one written after can be lost
in the crash you are recovering from. A predicate cannot disagree with the data.

### Rollback schema validator

```javascript
// Remove validator entirely
db.runCommand({collMod: "orders", validator: {}, validationLevel: "off"})
```
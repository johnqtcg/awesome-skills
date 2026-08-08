---
name: mongo-migration
description: >
  MongoDB schema migration safety reviewer and migration script generator. ALWAYS use
  when writing, reviewing, or planning MongoDB schema changes — field additions/removals,
  index builds, schema validator changes, document type migrations, shard key modifications,
  or any bulk update touching production collections. Covers index build lock behavior
  (replicated default vs the rolling exception), additive schema evolution, batched backfills,
  write concern tuning during migration, reshardCollection (5.0+), collMod validator
  changes, and rollback planning. Use even for "just add a field" — MongoDB's
  schema-less nature makes silent type inconsistencies and missing-field bugs harder
  to detect than RDBMS constraint violations.
---

# MongoDB Migration Safety Review

## Quick Reference

| If you need to…                        | Go to                                    |
|----------------------------------------|------------------------------------------|
| Understand what this skill covers      | §1 Scope                                 |
| Check mandatory prerequisites          | §2 Mandatory Gates                       |
| Choose review depth                    | §3 Depth Selection                       |
| Handle incomplete context              | §4 Degradation Modes                     |
| Analyze migration safety item by item  | §5 Migration Safety Checklist            |
| Design a phased execution plan         | §6 Execution Plan                        |
| Avoid common migration mistakes        | §7 Anti-Examples                         |
| Score the review result                | §8 Scorecard                             |
| Format review output                   | §9 Output Contract                       |
| Look up index/DDL lock behavior        | `references/mongo-ddl-lock-matrix.md`    |
| Plan a large-collection migration      | `references/large-collection-migration.md` |

---

## §1 Scope

**In scope** — schema migration safety for MongoDB **7.0 and 8.0**, the releases still in
support as of 2026-08. 4.4, 5.0 and 6.0 have reached end of life; if a user names one,
say so before reviewing, because an EOL server receives no security fixes and the
version-gated advice below assumes 7.0+:

- Document schema evolution (add/remove/rename/retype fields)
- Index operations (createIndex, dropIndex, replicated vs rolling builds, TTL indexes)
- Schema validator changes (collMod with JSON Schema validation)
- Data backfill and transformation (aggregation pipeline updates, bulkWrite)
- Shard key changes (reshardCollection 5.0+, refineCollectionShardKey 4.4+)
- Migration script review (mongosh scripts, application-driven migrations)
- Write concern / read concern tuning during migration phases
- Rollback planning (MongoDB's DDL is mostly non-transactional — but see §5.3 item 10: createCollection and createIndex do work inside a transaction)

**Out of scope** — delegate to dedicated skills:

- Query optimization, aggregation pipeline tuning → `mongo-best-practise`
- Application code changes → `go-code-reviewer` or language-specific reviewer
- Security hardening, role management → `mongo-best-practise`

---

## §2 Mandatory Gates

Execute gates sequentially. Each gate has a **STOP** condition.

### Gate 1: Context Collection

| Item | Why it matters | If unknown |
|------|----------------|------------|
| **MongoDB version** (7.0 / 8.0) | Index build behaviour, resharding, and the ticket metric path all differ | Assume **7.0** — the oldest supported, so the least capable. Flag 6.0 and below as EOL before reviewing |
| **Deployment type** (standalone / replica set / sharded cluster) | Affects index-build propagation, chunk migration, write concern | Assume replica set |
| **`_id` BSON type uniformity** | A `$gt` keyset cursor over `_id` **type-brackets**: if the collection holds more than one `_id` type it silently strands whole type classes. Determines whether the cursorless backfill is mandatory | `db.c.aggregate([{$group: {_id: {$type: "$_id"}, n: {$sum: 1}}}])`. More than one row → cursorless only. **If unknown, assume mixed** |
| **Collection document count** | Determines batch strategy and duration | Ask, or estimate via `db.collection.estimatedDocumentCount()` |
| **Collection size (data + indexes)** | Large collections need careful batching and monitoring | Estimate via `db.collection.stats()` |
| **Shard key** (if sharded) | Shard key changes require special procedures | Check `sh.status()` |
| **Write concern default** | Affects data safety during migration | Assume `w:majority` |
| **Read concern / read preference** | Affects consistency during dual-read phase | Assume `majority` / `primary` |
| **Replication lag tolerance** | Index builds and bulk writes increase lag | Ask; default 10s |

**STOP**: Cannot determine whether the target is MongoDB. Redirect to appropriate skill.

**PROCEED**: At least MongoDB version and collection name known or assumed.

### Gate 2: Scope Classification

| Mode | Trigger | Output |
|------|---------|--------|
| **review** | User provides existing migration script | Safety analysis with findings |
| **generate** | User describes desired schema change | Migration script + safety analysis |
| **plan** | User describes goal without specifics | Phased migration plan + rationale |

**STOP**: Not migration-related (e.g., query optimization). Redirect to `mongo-best-practise`.

**PROCEED**: Migration intent confirmed.

### Gate 3: Risk Classification

| Risk | Definition | Required action |
|------|-----------|-----------------|
| **SAFE** | Additive field; an index build on a small collection (the replicated default — a rolling build is not what makes it safe) | Standard write concern |
| **WARN** | Bulk update >1M docs, index on >10M docs, validator change | Off-peak + monitoring |
| **UNSAFE** | Shard key change, field type migration, foreground index on large collection | Phased rollout + rollback drill |

**STOP**: Any UNSAFE item without mitigation plan.

**PROCEED**: Every migration step has risk level and mitigation.

### Gate 4: Output Completeness

Before delivering output, verify all §9 Output Contract sections present. §9.9 Uncovered Risks must never be empty.

---

## §3 Depth Selection

| Depth | When to use | Gates | References to load |
|-------|-------------|-------|-------------------|
| **Lite** | ≤3 operations, all additive (add optional field, create index on small collection) | 1–4 | None |
| **Standard** | 4–15 operations, or any non-additive change (field removal, type change, validator) | 1–4 | `mongo-ddl-lock-matrix.md` |
| **Deep** | >15 operations, collection >10M docs, shard key change, or multi-step type migration | 1–4 | Both reference files |

**Force Standard or higher** when any signal appears:
field removal, field type change, shard key modification, schema validator enforcement, index on collection >5M docs, write concern change, field rename across documents.

---

## §4 Degradation Modes

When context is incomplete, degrade gracefully — never fabricate information.

| Available context | Mode | What you can do | What you cannot do |
|-------------------|------|-----------------|-------------------|
| Full (version, deployment, size, shard key, write concern) | **Full** | All checklist items, precise recommendations | — |
| Version + size known, others unknown | **Degraded** | Full checklist with conservative assumptions | Shard-specific, write concern advice |
| Only migration script, no context | **Minimal** | Static script analysis, flag all unknowns | Version-specific index build advice |
| No script (planning request) | **Planning** | Generate migration plan from requirements | Review existing script |

**Hard rule**: Never claim a migration is "safe" without knowing the collection size and deployment type. In Degraded/Minimal mode, list all assumptions in §9.9.

---

## §5 Migration Safety Checklist

Execute every item. Mark **SAFE** / **WARN** / **UNSAFE** with evidence.

### 5.1 Index Build Safety

1. **Index build method** — since 4.2 the default is a **replicated** build: every data-bearing member builds simultaneously, with a brief exclusive lock only at start and end. That is **not** a rolling build — a rolling build removes each member from the set in turn and is a deliberate exception (`references/large-collection-migration.md` §3). Default to the replicated build and say so explicitly in the plan. When uncertain → load `references/mongo-ddl-lock-matrix.md`.

2. **Index build impact on replica set** — the build runs on every member, so secondaries can fall behind. Measure lag with `rs.printSecondaryReplicationInfo()` (or `rs.status()` members' `optimeDate`): `rs.printReplicationInfo()` reports the **oplog window on the member you are connected to**, not any member's lag. Do not reach for a rolling build to avoid this — see §5.1 item 1.

3. **Unique index on existing data** — creating a unique index fails if duplicates exist. Pre-check: `db.collection.aggregate([{$group:{_id:"$field", count:{$sum:1}}}, {$match:{count:{$gt:1}}}])`. Fix duplicates before index creation.

4. **TTL index changes** — **`collMod` changes `expireAfterSeconds` in place from MongoDB 5.1**; drop-and-recreate is only required below that, and every version this skill covers is above it. Verified on live 7.0 and 8.0:
   ```javascript
   db.runCommand({collMod: "events", index: {keyPattern: {createdAt: 1}, expireAfterSeconds: 7200}});
   ```
   Dropping and recreating a TTL index on a large collection is an avoidable full index build. The delete thread runs every 60s; shortening a TTL creates a backlog it works through in bursts, so widen first and watch I/O.

### 5.2 Schema Evolution

5. **Additive-first rule** — new fields should be added as optional (no validator required) first. Application code must handle both old documents (field missing) and new documents (field present). Only enforce via validator after backfill confirms all documents have the field.

6. **Field type change** — MongoDB allows mixed types in a field (no constraint by default), but mixed types cause query/index issues. Type migration requires: read old type → write new type → backfill old documents → enforce validator. Never assume all documents have the same type without checking.

7. **Field rename** — MongoDB `$rename` operator works within a single document but has limitations: doesn't work across embedded document levels, doesn't work in sharded collections' shard key fields. For cross-level renames, use `$set` + `$unset` in aggregation pipeline update.

8. **Field removal** — `$unset` removes fields but is permanent. Unlike RDBMS `DROP COLUMN`, MongoDB field removal is per-document and must be batched. Consider: leave old field in place (MongoDB doesn't waste storage on absent fields in new documents) vs. batch-remove for consistency.

### 5.3 Backward Compatibility

9. **Deployment ordering — compatible code first, always** — the application that can read *both* shapes and dual-writes must be fully rolled out **before** the backfill starts, not after. Backfilling first leaves a window in which old instances keep creating documents in the old shape, so "zero documents left" is a reading of one instant rather than a property of the collection. Order: compatible deploy → confirm every instance → backfill → verify zero → cut reads and validator → **separate** release to stop writing the old field and `$unset` it. See §6.

10. **Rollback feasibility** — MongoDB's DDL is **not** transactional the way PostgreSQL's is, but "no transactional DDL" is too strong: `createCollection` and `createIndex` *are* permitted inside a multi-document transaction (verified on 7.0 and 8.0), and roll back with it. What you cannot do is wrap an arbitrary migration in one — a transaction has a runtime limit and holds its writes until commit, so it is not a batched-backfill tool. Classify each operation:
    - **Instant-rollback**: `dropIndex`, additive field (stop writing it)
    - **Script-rollback**: only when the old value was **captured first**. `$unset` is not reversible by an "inverse operation" — the value is gone. Copy to a shadow field before unsetting, or accept it as irreversible.
    - **Irreversible**: in-place field type conversion (old value overwritten)
    - For anything irreversible, take a backup or snapshot **and verify it restores** before proceeding.

### 5.4 Operational Safety

11. **Batched updates — use predicate batching** — bulk updates must be batched with a pause between batches. A single unbounded `updateMany()` holds a write ticket for its whole duration, degrading every other operation. **Batch by re-querying the migration's own predicate** (`{new_field: {$exists: false}}`), not by an `_id` range: comparison operators type-bracket, so a `$gt` cursor over `_id` skips every `_id` whose BSON type differs from the cursor's (measured: 30 of 60 documents stranded). The `_id` keyset is an optimisation available **only** after Gate 1 proves a single `_id` type — `references/large-collection-migration.md` §1.

12. **Write concern during migration** — use `w: "majority"` for safety (data survives primary failure). Consider `w: 1` only for backfill phases where re-run is acceptable. Document the write concern choice and its trade-off.

13. **Schema validator enforcement** — `moderate` does **not** mean "only new writes are validated". Measured on 8.0: a non-compliant **insert is rejected**; an update to an existing **compliant** document is **rejected** if it would break the rules; only an update to a document that **already failed** validation is exempt. That exemption is the whole point — it lets you deploy a validator over a collection with legacy documents without blocking writes to them. Sequence: `collMod` with `validationLevel: "moderate"` → backfill → verify zero non-compliant documents → `"strict"`. `validationAction: "warn"` logs instead of rejecting, which is the safer first step when you are unsure of the shape of your data.

14. **currentOp monitoring** — track migration progress with `db.currentOp({$all: true})` for index builds and `db.collection.countDocuments({migrated: true})` for backfill progress.

---

## §6 Execution Plan (Standard + Deep)

Standard phased pattern for MongoDB schema migration:

**The application is deployed before the backfill, not after.** This ordering is the
whole point of the plan, and getting it backwards is the most common way a migration
that "completed" is not actually complete:

1. **Phase 1 — Additive schema**: add new fields as optional (**no validator yet**), create indexes with the **replicated default** on the primary, watching per-secondary lag.
2. **Phase 2 — Compatible deploy**: ship code that **reads either shape and dual-writes both**. It must tolerate documents that have not been backfilled yet, because for the whole of Phase 3 most of them have not.
3. **Phase 3 — Rollout barrier**: confirm **every** instance is running that code before touching data. A single old instance still writing documents without the new field means the backfill has no stable finishing line — it drains while the old code refills it.
4. **Phase 4 — Backfill**: predicate-batched `updateMany()` (no `_id` cursor unless Gate 1 proved a single `_id` type), throttled, `w: "majority"` — `references/large-collection-migration.md` §1.
5. **Phase 5 — Verify**: `countDocuments({<field>: {$exists: false}})` must be **0**, and must *stay* 0 on a re-check. It can only stay 0 because Phase 3 guaranteed nothing writes the old shape any more.
6. **Phase 6 — Cut over**: switch reads to the new field, then `collMod` `validationLevel: "moderate"` → re-verify → `"strict"`.
7. **Phase 7 — Cleanup** (separate release): stop writing the old field, then `$unset` it in batches and drop unused indexes. `$unset` is irreversible — this release is deliberately last and deliberately separate.

### Why the deploy comes first

Backfilling before the compatible deploy leaves a window between "backfill finished" and
"new code live" in which the old code is still creating documents in the old shape. The
count you verified is stale the moment you read it, and the validator you enable in
Phase 6 then rejects writes to documents the backfill never saw.

The rollout barrier in Phase 3 is what makes Phase 5's zero meaningful. Without it, zero
is a measurement of one instant, not a property of the collection.

Each phase: **Pre-condition** → **Script** (with write concern) → **Validation** → **Rollback** → **Go/No-go**.

For collections >10M docs, details in `references/large-collection-migration.md`.

---

## §7 Anti-Examples

### AE-1: Foreground index build on large production collection
```javascript
// WRONG: blocks all read/write operations (MongoDB <4.2) or holds exclusive lock at start/end
db.orders.createIndex({created_at: 1})  // on 50M-doc collection during peak hours
// RIGHT: build on the PRIMARY with the replicated default and watch per-secondary lag.
// A rolling build is a different, manual procedure and is not the fix for lag.
// MongoDB 4.2+ builds are already optimized, but still monitor replication lag
```

### AE-2: Unbounded updateMany without batching
```javascript
// WRONG: single operation on 20M documents — holds WiredTiger tickets, degrades all ops
db.orders.updateMany({status: null}, {$set: {status: "pending"}})
// RIGHT: batch by re-querying the migration's own predicate (see §6 Phase 4).
// NOT an _id range: $gt type-brackets, so a cursor over _id strands every _id whose
// BSON type differs from the cursor's. The keyset is allowed only after Gate 1
// proves a single _id type.
```

### AE-3: Schema validator set to "strict" before backfill
```javascript
// WRONG: existing documents fail validation → inserts/updates rejected
db.runCommand({collMod: "orders", validator: {$jsonSchema: {...}}, validationLevel: "strict"})
// RIGHT: "moderate" first, backfill, verify zero non-compliant, then "strict".
// moderate does NOT exempt existing documents: it exempts only updates to documents
// that ALREADY fail validation. Inserts and updates to compliant documents are checked.
```

### AE-4: Field type change without dual-read handling
```javascript
// WRONG: changes field type in-place — old application code that expects string will break
db.orders.updateMany({}, [{$set: {amount: {$toDouble: "$amount"}}}])
// RIGHT: add new field (amount_v2), backfill, migrate reads, then remove old field
```

### AE-5: createIndex with unique:true without duplicate check
```javascript
// WRONG: fails immediately if duplicates exist — wasted time on 50M-doc collection
db.users.createIndex({email: 1}, {unique: true})
// RIGHT: check for duplicates first, fix them, then create unique index
```

### AE-6: Migration issue reported as application bug
```
-- WRONG: "Bug: some orders have string amounts, others have numbers"
-- This is a schema evolution issue from a past migration that didn't enforce types.
-- RIGHT: report as "Schema inconsistency: mixed types in orders.amount — needs type migration"
```

Extended anti-examples (AE-7 through AE-13) in `references/migration-anti-examples.md`.

---

## §8 Migration Scorecard

### Critical — any FAIL means overall FAIL

- [ ] Backfill is batched **by re-querying its own predicate** (`{field: {$exists: false}}`), which needs no cursor and is correct for any `_id` BSON type. A `$gt` keyset over `_id` is permitted **only** where Gate 1 proved a single `_id` type — and then its cursor must come from the batch just processed, never from arithmetic on `_id` or `max(_id)` of the migrated set
- [ ] Write concern explicitly set for migration operations (not relying on the cluster default)
- [ ] Rollback path documented for every phase (instant-rollback / script-rollback / irreversible with a **restore-tested** backup)

### Standard

- [ ] Schema changes are additive-first (new fields optional before validator enforcement)
- [ ] Index builds monitored for **per-secondary lag** (`rs.printSecondaryReplicationInfo()`), using the replicated default rather than a rolling build unless pressure was measured
- [ ] Field type changes use new-field + dual-read (not in-place overwrite)
- [ ] Schema validator staged `"moderate"` → counted verification → `"strict"`
- [ ] A **counted** check confirms zero documents still match the backfill predicate

### Hygiene

- [ ] Migration progress tracked by **counting the remaining predicate**, not by a stored checkpoint
- [ ] Unique index preceded by a duplicate check
- [ ] Post-migration `collStats` / index usage verified
- [ ] Ticket pressure watched at the path that exists for the target version (§ lock matrix)

### Scoring — the denominator moves

Each tier is scored **against the items that apply**, not against a fixed count. Write
`N/A` for an item the migration cannot reach, and drop it from *both* sides:

```
Critical: Y/Na    Standard: Z/Nb    Hygiene: W/Nc    Total: (Y+Z+W)/(Na+Nb+Nc)
```

PASS requires **Critical = Na/Na** (every applicable critical item), **Standard ≥ 80% of
Nb**, and **Hygiene ≥ 75% of Nc** — the same bars the fixed 3/3, 4/5 and 3/4 expressed,
now stated as ratios so they survive an N/A.

Two rules keep this honest:

- **N/A is never a pass.** It leaves the numerator *and* the denominator. Record why in
  §9.9 so a reader sees which check did not apply rather than which one succeeded.
- **If a tier ends up entirely N/A, the review is out of scope, not passing.** Say so.

---

## §9 Output Contract

Every migration review MUST produce these sections. Write "N/A — [reason]" if inapplicable.

```
### 9.1 Context Gate
| Item | Value | Source |

### 9.2 Depth & Mode
[Lite/Standard/Deep] × [review/generate/plan] — [rationale]

### 9.3 Risk Assessment Table
| # | Operation | Lock Impact | Risk | Notes |

### 9.4 Execution Plan (Standard/Deep; "N/A — Lite" for Lite)

### 9.5 Migration Script (with write concern, batch size, and the batching strategy — predicate by default; `_id` keyset only with the Gate 1 single-type finding quoted)

### 9.6 Validation Script (document count, schema check, index verify)

### 9.7 Rollback Plan (per-phase; classify instant/script/irreversible)

### 9.8 Post-Deploy Checks

### 9.9 Uncovered Risks (MANDATORY — never empty)
| Area | Reason | Impact | Follow-up |
```

**Volume rules**:
- UNSAFE: always fully detailed with mitigation
- WARN: up to 10; overflow to §9.9
- SAFE: summary row only
- §9.9 minimum: document all assumptions (especially collection size if unknown)

**Scorecard summary** (append after §9.9):
```
Scorecard: (Y+Z+W)/(Na+Nb+Nc) — Critical Y/Na, Standard Z/Nb, Hygiene W/Nc — PASS/FAIL
N/A items: <item> — <why it does not apply>
Data basis: [full context | degraded | minimal | planning]
```

---

## §10 Reference Loading Guide

| Condition | Load |
|-----------|------|
| Standard or Deep depth | `references/mongo-ddl-lock-matrix.md` |
| Deep depth, or collection >10M docs | `references/large-collection-migration.md` |
| Extended anti-example matching | `references/migration-anti-examples.md` |
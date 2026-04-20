---
name: mongo-migration
description: >
  MongoDB schema migration safety reviewer and migration script generator. ALWAYS use
  when writing, reviewing, or planning MongoDB schema changes — field additions/removals,
  index builds, schema validator changes, document type migrations, shard key modifications,
  or any bulk update touching production collections. Covers index build lock behavior
  (foreground vs rolling builds), additive schema evolution, _id-range batched updates,
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

**In scope** — schema migration safety for MongoDB 4.4 / 5.0 / 6.0 / 7.0+:

- Document schema evolution (add/remove/rename/retype fields)
- Index operations (createIndex, dropIndex, rolling builds, TTL indexes)
- Schema validator changes (collMod with JSON Schema validation)
- Data backfill and transformation (aggregation pipeline updates, bulkWrite)
- Shard key changes (reshardCollection 5.0+, refineCollectionShardKey 4.4+)
- Migration script review (mongosh scripts, application-driven migrations)
- Write concern / read concern tuning during migration phases
- Rollback planning (MongoDB has no transactional DDL)

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
| **MongoDB version** (4.4 / 5.0 / 6.0 / 7.0+) | Index build behavior, resharding features differ | Assume 4.4 (most restrictive) |
| **Deployment type** (standalone / replica set / sharded cluster) | Affects rolling builds, chunk migration, write concern | Assume replica set |
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
| **SAFE** | Additive field, background/rolling index on small collection | Standard write concern |
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

1. **Index build method** — MongoDB 4.2+ uses rolling/optimized builds by default (brief exclusive lock at start and end, allows concurrent reads and writes during build). Pre-4.2 `background: true` allows DML but is slower and may miss documents. When uncertain → load `references/mongo-ddl-lock-matrix.md`.

2. **Index build impact on replica set** — index builds replicate to secondaries. On large collections, secondaries may fall behind during build. Monitor `rs.printReplicationInfo()` for lag. Consider building on secondaries first (rolling build pattern) for zero-downtime.

3. **Unique index on existing data** — creating a unique index fails if duplicates exist. Pre-check: `db.collection.aggregate([{$group:{_id:"$field", count:{$sum:1}}}, {$match:{count:{$gt:1}}}])`. Fix duplicates before index creation.

4. **TTL index changes** — TTL indexes have a background thread that deletes expired documents. Changing TTL value requires dropIndex + createIndex (no in-place modification). The delete thread runs every 60s; large backlogs during migration can cause I/O spikes.

### 5.2 Schema Evolution

5. **Additive-first rule** — new fields should be added as optional (no validator required) first. Application code must handle both old documents (field missing) and new documents (field present). Only enforce via validator after backfill confirms all documents have the field.

6. **Field type change** — MongoDB allows mixed types in a field (no constraint by default), but mixed types cause query/index issues. Type migration requires: read old type → write new type → backfill old documents → enforce validator. Never assume all documents have the same type without checking.

7. **Field rename** — MongoDB `$rename` operator works within a single document but has limitations: doesn't work across embedded document levels, doesn't work in sharded collections' shard key fields. For cross-level renames, use `$set` + `$unset` in aggregation pipeline update.

8. **Field removal** — `$unset` removes fields but is permanent. Unlike RDBMS `DROP COLUMN`, MongoDB field removal is per-document and must be batched. Consider: leave old field in place (MongoDB doesn't waste storage on absent fields in new documents) vs. batch-remove for consistency.

### 5.3 Backward Compatibility

9. **Deployment ordering** — same as RDBMS: code handles both old and new schema → deploy migration → deploy code that uses only new schema → separate release: remove old-schema code paths.

10. **Rollback feasibility** — MongoDB has no transactional DDL. Index drops are instant but data changes are permanent. Classify each operation:
    - **Instant-rollback**: dropIndex, additive field (just stop writing)
    - **Script-rollback**: $set/$unset can be reversed with inverse operation
    - **Irreversible**: field type conversion (old type data overwritten)
    - For irreversible changes, take a backup or snapshot before proceeding.

### 5.4 Operational Safety

11. **Batched updates with _id-range** — bulk updates must be batched by `_id` range with periodic yield. Single unbounded `updateMany()` on millions of documents holds the WiredTiger ticket for extended periods, degrading all other operations.

12. **Write concern during migration** — use `w: "majority"` for safety (data survives primary failure). Consider `w: 1` only for backfill phases where re-run is acceptable. Document the write concern choice and its trade-off.

13. **Schema validator enforcement** — use `collMod` to add JSON Schema validator with `validationLevel: "moderate"` first (validates only inserts and updates, not existing docs), then switch to `"strict"` after backfill confirms all documents comply. `validationAction: "warn"` logs violations without rejecting — useful for migration monitoring.

14. **currentOp monitoring** — track migration progress with `db.currentOp({$all: true})` for index builds and `db.collection.countDocuments({migrated: true})` for backfill progress.

---

## §6 Execution Plan (Standard + Deep)

Standard phased pattern for MongoDB schema migration:

1. **Phase 1 — Additive schema**: add new fields as optional (no validator), create indexes (rolling build)
2. **Phase 2 — Backfill**: populate new fields via `_id`-range batched `updateMany()` with aggregation pipeline (see `references/large-collection-migration.md`)
3. **Phase 3 — App deploy**: deploy code writing to both old and new fields (dual-write)
4. **Phase 4 — Validator enforcement**: `collMod` with `validationLevel: "moderate"` → verify → `"strict"`
5. **Phase 5 — Cleanup** (separate release): `$unset` old fields in batches, drop unused indexes

Each phase: **Pre-condition** → **Script** (with write concern) → **Validation** → **Rollback** → **Go/No-go**.

For collections >10M docs, details in `references/large-collection-migration.md`.

---

## §7 Anti-Examples

### AE-1: Foreground index build on large production collection
```javascript
// WRONG: blocks all read/write operations (MongoDB <4.2) or holds exclusive lock at start/end
db.orders.createIndex({created_at: 1})  // on 50M-doc collection during peak hours
// RIGHT: build during off-peak; on replica set, use rolling build pattern
// MongoDB 4.2+ builds are already optimized, but still monitor replication lag
```

### AE-2: Unbounded updateMany without batching
```javascript
// WRONG: single operation on 20M documents — holds WiredTiger tickets, degrades all ops
db.orders.updateMany({status: null}, {$set: {status: "pending"}})
// RIGHT: batch by _id range (see §6 Phase 2)
```

### AE-3: Schema validator set to "strict" before backfill
```javascript
// WRONG: existing documents fail validation → inserts/updates rejected
db.runCommand({collMod: "orders", validator: {$jsonSchema: {...}}, validationLevel: "strict"})
// RIGHT: use "moderate" first (only validates new writes), backfill, then switch to "strict"
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

- [ ] Backfill uses `_id`-range batching with periodic yield (not unbounded `updateMany`)
- [ ] Write concern explicitly set for migration operations (not relying on cluster default)
- [ ] Rollback path documented for every phase (instant-rollback / script-rollback / irreversible with backup)

### Standard — 4 of 5 must pass

- [ ] Schema changes are additive-first (new fields optional before validator enforcement)
- [ ] Index builds monitored for replication lag (rolling build or off-peak)
- [ ] Field type changes use new-field + dual-read pattern (not in-place overwrite)
- [ ] Schema validator uses `"moderate"` → `"strict"` progression (not direct strict)
- [ ] Validation script confirms all documents match expected schema after backfill

### Hygiene — 3 of 4 must pass

- [ ] Migration progress tracked (document count or `_id` checkpoint)
- [ ] Unique index preceded by duplicate check
- [ ] Post-migration `collStats` / index usage verified
- [ ] WiredTiger cache and replication lag monitored during bulk operations

**Verdict**: `X/12`; Critical: `Y/3`; Standard: `Z/5`; Hygiene: `W/4`.
PASS requires: Critical 3/3 AND Standard ≥4/5 AND Hygiene ≥3/4.

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

### 9.5 Migration Script (with write concern, batch size, _id-range)

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
Scorecard: X/12 — Critical Y/3, Standard Z/5, Hygiene W/4 — PASS/FAIL
Data basis: [full context | degraded | minimal | planning]
```

---

## §10 Reference Loading Guide

| Condition | Load |
|-----------|------|
| Standard or Deep depth | `references/mongo-ddl-lock-matrix.md` |
| Deep depth, or collection >10M docs | `references/large-collection-migration.md` |
| Extended anti-example matching | `references/migration-anti-examples.md` |
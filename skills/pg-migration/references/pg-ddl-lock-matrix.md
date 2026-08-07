# PostgreSQL DDL Lock Matrix

This reference maps each DDL operation to the lock level it acquires. Use this to
determine whether a migration can run online or needs mitigation.

**Verified against**: PostgreSQL 17 documentation source (`doc/src/sgml`), 2026-08.
Every row carries a `Source` pointing at the reference page that states the behaviour.
When a row and the live server disagree, the server wins — re-verify and update this file.

## The Default Rule (read this first)

> "There are several subforms described below. Note that the lock level required may
> differ for each subform. An **ACCESS EXCLUSIVE lock is acquired unless explicitly
> noted**. When multiple subcommands are given, **the lock acquired will be the
> strictest one required by any subcommand**."
> — `ALTER TABLE`, Description

Two consequences that dominate migration design:

1. **Assume ACCESS EXCLUSIVE for any ALTER TABLE subform not listed as an exception below.**
2. **Never batch a low-lock subcommand with a high-lock one.** Combining them escalates
   the whole statement to the strictest lock, silently destroying the benefit of the
   low-lock form:

```sql
-- WRONG: ADD FOREIGN KEY alone needs only SHARE ROW EXCLUSIVE, but ADD COLUMN
-- forces ACCESS EXCLUSIVE, so the combined statement blocks reads too.
ALTER TABLE orders
  ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) NOT VALID,
  ADD COLUMN note text;

-- RIGHT: separate statements keep each at its own lock level.
ALTER TABLE orders ADD COLUMN note text;
ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) NOT VALID;
```

## Lock Level Hierarchy (least → most restrictive)

| Level | Conflicts with | Typical DDL |
|-------|---------------|-------------|
| **AccessShareLock** | AccessExclusive | SELECT |
| **RowShareLock** | Exclusive, AccessExclusive | SELECT FOR UPDATE/SHARE |
| **RowExclusiveLock** | Share, ShareRowExclusive, Exclusive, AccessExclusive | INSERT, UPDATE, DELETE |
| **ShareUpdateExclusiveLock** | ShareUpdateExclusive, Share, ShareRowExclusive, Exclusive, AccessExclusive | VACUUM, CREATE INDEX CONCURRENTLY, VALIDATE CONSTRAINT |
| **ShareLock** | RowExclusive, ShareUpdateExclusive, ShareRowExclusive, Exclusive, AccessExclusive | CREATE INDEX (non-concurrent) |
| **ShareRowExclusiveLock** | RowExclusive, ShareUpdateExclusive, Share, ShareRowExclusive, Exclusive, AccessExclusive | CREATE TRIGGER, **ADD FOREIGN KEY** |
| **ExclusiveLock** | RowShare, RowExclusive, ShareUpdateExclusive, Share, ShareRowExclusive, Exclusive, AccessExclusive | — |
| **AccessExclusiveLock** | ALL other locks | Most ALTER TABLE, DROP TABLE, TRUNCATE |

**Key insight**: AccessExclusiveLock blocks even SELECT. On a hot table, acquiring this
lock stalls ALL queries until the DDL completes. ShareRowExclusiveLock blocks writes but
**not** reads — that difference is why `ADD FOREIGN KEY` is far cheaper than it looks.

---

## Column Operations

| Operation | Lock Level | Blocks Reads? | Blocks Writes? | Rewrites Table? | Source |
|-----------|-----------|:---:|:---:|:---:|--------|
| ADD COLUMN (nullable, no default) | AccessExclusive | Brief | Brief | No | alter_table · Notes |
| ADD COLUMN, **non-volatile** DEFAULT (PG 11+) | AccessExclusive | Brief | Brief | No | alter_table · Notes |
| ADD COLUMN, **volatile** DEFAULT | AccessExclusive | Yes | Yes | **Yes** | alter_table · Notes |
| DROP COLUMN | AccessExclusive | Brief | Brief | No | alter_table · DROP COLUMN |
| ALTER COLUMN SET/DROP DEFAULT | AccessExclusive | Brief | Brief | No | alter_table · default rule |
| ALTER COLUMN SET NOT NULL | AccessExclusive | Yes (scan) | Yes (scan) | No | alter_table · SET NOT NULL |
| ALTER COLUMN SET NOT NULL, valid CHECK present (PG 12+) | AccessExclusive | Brief | Brief | No | alter_table · SET NOT NULL |
| ALTER COLUMN DROP NOT NULL | AccessExclusive | Brief | Brief | No | alter_table · default rule |
| ALTER COLUMN TYPE, binary-coercible + USING unchanged | AccessExclusive | Brief | Brief | No | alter_table · Notes |
| ALTER COLUMN TYPE, anything else | AccessExclusive | Yes | Yes | **Yes** | alter_table · Notes |
| RENAME COLUMN | AccessExclusive | Brief | Brief | No | alter_table · RENAME |
| ALTER COLUMN SET STATISTICS | **ShareUpdateExclusive** | No | No | No | alter_table · SET STATISTICS |
| ALTER COLUMN SET (attribute options) | **ShareUpdateExclusive** | No | No | No | alter_table · SET ( … ) |

### The rewrite rule, stated exactly

> "Adding a column with a volatile DEFAULT or changing the type of an existing column
> will require the entire table and its indexes to be rewritten. **As an exception**, when
> changing the type of an existing column, if the `USING` clause does not change the
> column contents **and** the old type is either binary coercible to the new type or an
> unconstrained domain over the new type, a table rewrite is not needed. However, indexes
> must always be rebuilt unless the system can verify that the new index would be
> logically equivalent to the existing one."
> — `ALTER TABLE`, Notes

Practical readings:

- `varchar(50)` → `varchar(100)` (widening), `text` ↔ `varchar` with **no collation change**:
  no rewrite, no index rebuild.
- **`int` → `bigint`: REWRITES.** `int4` is not binary coercible to `int8`. Do not treat
  integer widening as cheap — this is the single most common false assumption in PostgreSQL
  migration planning.
- `numeric(10,2)` → `numeric(12,4)`: rewrites (typmod change is not binary coercible).
- Any collation change: index rebuild is mandatory even when the heap is untouched.

### Version gates

- **PG 11+**: ADD COLUMN with a non-volatile DEFAULT is metadata-only.
- **PG 12+**: SET NOT NULL skips the full-table scan if a valid CHECK constraint already
  proves the column non-null.

---

## Index Operations

| Operation | Lock Level | Blocks Reads? | Blocks Writes? | In transaction? | Source |
|-----------|-----------|:---:|:---:|:---:|--------|
| CREATE INDEX | ShareLock | No | **Yes** | Yes | create_index · Notes |
| CREATE INDEX CONCURRENTLY | ShareUpdateExclusive | No | No | **No** | create_index · Building Indexes Concurrently |
| DROP INDEX | AccessExclusive (parent) | Brief | Brief | Yes | reindex · Notes |
| DROP INDEX CONCURRENTLY | ShareUpdateExclusive | No | No | **No** | drop_index · CONCURRENTLY |
| REINDEX INDEX / TABLE | **ShareLock on table** + AccessExclusive **on the index** | Effectively yes — see below | **Yes** | Yes | reindex · Notes |
| REINDEX CONCURRENTLY (PG 12+) | ShareUpdateExclusive | No | No | **No** | reindex · CONCURRENTLY |

### REINDEX: why the lock level understates the impact

> "REINDEX locks out writes but not reads of the index's parent table. It also takes an
> ACCESS EXCLUSIVE lock on the specific index being processed, which will block reads that
> attempt to use that index. In particular, **the query planner tries to take an ACCESS
> SHARE lock on every index of the table, regardless of the query, and so REINDEX blocks
> virtually any queries** except for some prepared queries whose plan has been cached and
> which don't use this very index."
> — `REINDEX`, Notes

So: the lock **on the table** is ShareLock (reads permitted at the lock level), but the
ACCESS EXCLUSIVE lock **on the index** stalls nearly every real query anyway, because the
planner locks all indexes. Treat non-concurrent REINDEX as read-blocking in practice, and
use `REINDEX CONCURRENTLY` (PG 12+) on production. Do not "simplify" this row in either
direction — both halves are load-bearing.

### CONCURRENTLY caveats (apply to CREATE / DROP / REINDEX)

- **Cannot run inside a transaction block.** Regular forms can; CONCURRENTLY forms cannot.
  This is a hard constraint that drives the session-guard rule in `SKILL.md` §5.1.
- **Do not wrap in a short `statement_timeout`.** `statement_timeout` aborts *any* statement
  exceeding it, and a concurrent build on a large table can run for hours. A 30s
  `statement_timeout` will kill the build and leave an INVALID index. Guard the *lock wait*
  with `lock_timeout`; leave `statement_timeout` at 0 for the build itself.
- If interrupted, leaves an INVALID index that must be dropped and recreated.
- Requires two table scans; takes longer than a regular build.
- `DROP INDEX CONCURRENTLY` does not work on indexes of partitioned tables.
- Concurrent builds on partitioned tables are not supported — build per-partition instead.
- Check for invalid indexes: `SELECT indexrelid::regclass FROM pg_index WHERE NOT indisvalid;`

---

## Constraint Operations

| Operation | Lock Level (altered table) | Also locks | Blocks Reads? | Blocks Writes? | Validates? | Source |
|-----------|---------------------------|------------|:---:|:---:|:---:|--------|
| ADD FOREIGN KEY | **ShareRowExclusive** | **ShareRowExclusive on referenced table** | **No** | Yes | Yes | alter_table · ADD table_constraint |
| ADD FOREIGN KEY … NOT VALID | **ShareRowExclusive** | ShareRowExclusive on referenced table | **No** | Brief | No | alter_table · ADD table_constraint |
| ADD CHECK | AccessExclusive | — | Yes (scan) | Yes (scan) | Yes | alter_table · default rule |
| ADD CHECK … NOT VALID | AccessExclusive | — | Brief | Brief | No | alter_table · NOT VALID |
| VALIDATE CONSTRAINT (CHECK) | **ShareUpdateExclusive** | — | No | No | Yes | alter_table · VALIDATE CONSTRAINT |
| VALIDATE CONSTRAINT (FK) | **ShareUpdateExclusive** | **RowShare on referenced table** | No | No | Yes | alter_table · Notes |
| DROP CONSTRAINT | AccessExclusive | — | Brief | Brief | No | alter_table · default rule |
| ADD UNIQUE / PRIMARY KEY | AccessExclusive | — | Yes | Yes | Yes | alter_table · default rule |
| ADD CONSTRAINT … USING INDEX | AccessExclusive | — | Brief | Brief | No | alter_table · ADD … USING INDEX |

### The FK exception, stated exactly

> "Although most forms of `ADD table_constraint` require an ACCESS EXCLUSIVE lock,
> **`ADD FOREIGN KEY` requires only a SHARE ROW EXCLUSIVE lock**. Note that `ADD FOREIGN KEY`
> also acquires a SHARE ROW EXCLUSIVE lock on the **referenced** table, in addition to the
> lock on the table on which the constraint is declared."
> — `ALTER TABLE`, ADD table_constraint

Why this matters for planning:

- **FK addition never blocks reads**, even without `NOT VALID`. `NOT VALID` is still worth
  using on large tables because it skips the validation *scan* (duration), not because it
  changes the lock class.
- **The referenced table is also locked for writes.** Adding an FK to a small child table
  can stall writes on a hot parent table. Always name both tables in the risk assessment.
- **`ADD CHECK` is genuinely ACCESS EXCLUSIVE** and does block reads. FK and CHECK must
  never be described by a single combined rule.

### VALIDATE CONSTRAINT, stated exactly

> "The validation step does not need to lock out concurrent updates … Hence, validation
> acquires only a SHARE UPDATE EXCLUSIVE lock on the table being altered. **(If the
> constraint is a foreign key then a ROW SHARE lock is also required on the table
> referenced by the constraint.)**"
> — `ALTER TABLE`, Notes

### NOT VALID + VALIDATE two-step

The standard pattern for adding FK/CHECK to large production tables:

```sql
-- Step 1: brief lock, no validation scan
ALTER TABLE orders ADD CONSTRAINT fk_user
  FOREIGN KEY (user_id) REFERENCES users(id) NOT VALID;

-- Step 2: ShareUpdateExclusive on orders + RowShare on users; concurrent DML allowed
ALTER TABLE orders VALIDATE CONSTRAINT fk_user;
```

**Limitation — partitioned tables, PG 14–17 only**: on those versions a foreign key on
a partitioned table **may not be declared `NOT VALID`**. The server rejects it outright
with `cannot add NOT VALID foreign key on partitioned table`, so the two-step pattern is
unavailable; plan for the single-step FK addition (ShareRowExclusive, writes blocked for
the scan duration) or attach pre-validated partitions.

**PG 18 lifts this** — the NOT VALID form is accepted on partitioned tables. Measured on
live 14.23 / 15 / 16 / 17 / 18.4; the boundary is pinned by
`lint_migration.PARTITIONED_FK_NOT_VALID_MIN_PG` and re-checked by
`scripts/tests/test_pg_server_matrix.py::TestPartitionedForeignKey`.

---

## Table & Partition Operations

| Operation | Lock Level | Blocks Reads? | Blocks Writes? | Source |
|-----------|-----------|:---:|:---:|--------|
| TRUNCATE | AccessExclusive | Yes | Yes | truncate |
| VACUUM | ShareUpdateExclusive | No | No | vacuum |
| VACUUM FULL | AccessExclusive | Yes | Yes | vacuum |
| ANALYZE | ShareUpdateExclusive | No | No | analyze |
| ALTER TABLE SET (fillfactor / toast / autovacuum / parallel_workers) | **ShareUpdateExclusive** | No | No | alter_table · SET ( … ) |
| ALTER TABLE CLUSTER ON / SET WITHOUT CLUSTER | **ShareUpdateExclusive** | No | No | alter_table · CLUSTER ON |
| ATTACH PARTITION | **ShareUpdateExclusive on parent** + AccessExclusive on attached table and on default partition | Parent: no | Parent: no | alter_table · ATTACH PARTITION |
| DETACH PARTITION | AccessExclusive on parent + partition, ShareLock on FK-referencing tables | Yes | Yes | alter_table · DETACH PARTITION |
| DETACH PARTITION CONCURRENTLY (PG 14+) | ShareUpdateExclusive on parent + partition | No | No | alter_table · DETACH PARTITION |

### ATTACH PARTITION, stated exactly

> "Attaching a partition acquires a SHARE UPDATE EXCLUSIVE lock on the **parent** table,
> in addition to the ACCESS EXCLUSIVE locks on the table being attached and on the default
> partition (if any)."
> — `ALTER TABLE`, ATTACH PARTITION

The parent stays fully available. The cost lands on the table being attached — which is
normally a fresh, empty, traffic-free table — and on the **default partition**, which may
well be hot. If a default partition exists, treat ATTACH as a read-blocking operation
against that default partition, and supply a matching CHECK constraint on the incoming
table to skip the validation scan.

`DETACH PARTITION CONCURRENTLY` uses two internal transactions, so like the other
CONCURRENTLY forms it **cannot run inside a transaction block**.

---

## Decision Flowchart

```
Is this an index operation?
  ├─ YES → Use the CONCURRENTLY variant.
  │        Run OUTSIDE any transaction block.
  │        Guard with session-level lock_timeout; do NOT set a short statement_timeout.
  └─ NO
      │
      Is this ADD FOREIGN KEY?
        ├─ YES → ShareRowExclusive on BOTH tables; reads unaffected.
        │        Use NOT VALID to shorten the scan (partitioned tables: PG 18+ only).
        └─ NO
            │
            Is this ADD CHECK / UNIQUE / PRIMARY KEY?
              ├─ YES → AccessExclusive. NOT VALID (CHECK only) to shorten the lock.
              └─ NO
                  │
                  Does it rewrite? (volatile DEFAULT, non-binary-coercible TYPE change)
                    ├─ YES → table >1M rows? expand-contract / create-swap-rename.
                    │        NOT pg_repack — it cannot change a schema; use it only
                    │        afterwards to reclaim the bloat the rewrite produced.
                    │        Otherwise low-traffic window + lock_timeout.
                    └─ NO → AccessExclusive but brief. Set lock_timeout and retry on timeout.

At every branch: never combine subcommands of different lock classes in one ALTER TABLE.
```

## Monitoring Locks During Migration

```sql
-- Who is blocking whom
SELECT blocked_locks.pid  AS blocked_pid,
       blocked_activity.usename AS blocked_user,
       blocking_locks.pid AS blocking_pid,
       blocking_activity.usename AS blocking_user,
       blocked_activity.query AS blocked_query
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_locks.pid = blocked_activity.pid
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
  AND blocking_locks.relation = blocked_locks.relation
  AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_locks.pid = blocking_activity.pid
WHERE NOT blocked_locks.granted;

-- Confirm the lock a statement actually took. Run in ANOTHER session while the DDL is
-- still running; replace 12345 with its pid from the query above or pg_stat_activity.
SELECT relation::regclass, mode, granted
FROM pg_locks WHERE pid = 12345 AND relation IS NOT NULL;
```

The second query is the ground truth. When this matrix and `pg_locks` disagree, believe
`pg_locks` and correct this file.

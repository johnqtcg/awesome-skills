# PostgreSQL DDL Lock Level Matrix

This reference maps each DDL operation to the lock level it acquires. Use this to
determine whether a migration can run online or needs mitigation.

## Lock Level Hierarchy (least → most restrictive)

| Level | Conflicts with | Typical DDL |
|-------|---------------|-------------|
| **AccessShareLock** | AccessExclusiveLock | SELECT |
| **RowShareLock** | Exclusive, AccessExclusive | SELECT FOR UPDATE/SHARE |
| **RowExclusiveLock** | Share, ShareRowExclusive, Exclusive, AccessExclusive | INSERT, UPDATE, DELETE |
| **ShareUpdateExclusiveLock** | ShareUpdateExclusive, Share, ShareRowExclusive, Exclusive, AccessExclusive | VACUUM, CREATE INDEX CONCURRENTLY, VALIDATE CONSTRAINT, certain ALTER TABLE |
| **ShareLock** | RowExclusive, ShareUpdateExclusive, ShareRowExclusive, Exclusive, AccessExclusive | CREATE INDEX (non-concurrent) |
| **ShareRowExclusiveLock** | RowExclusive, ShareUpdateExclusive, Share, ShareRowExclusive, Exclusive, AccessExclusive | CREATE TRIGGER, some ALTER TABLE |
| **ExclusiveLock** | RowShare, RowExclusive, ShareUpdateExclusive, Share, ShareRowExclusive, Exclusive, AccessExclusive | — |
| **AccessExclusiveLock** | ALL other locks | Most ALTER TABLE, DROP TABLE, TRUNCATE, REINDEX |

**Key insight**: AccessExclusiveLock blocks even SELECT. On a hot table, acquiring this lock
stalls ALL queries until the DDL completes.

---

## Column Operations

| Operation | Lock Level | Blocks Reads? | Blocks Writes? | Rewrites Table? | Notes |
|-----------|-----------|:---:|:---:|:---:|-------|
| ADD COLUMN (nullable, no default) | AccessExclusiveLock | Brief | Brief | No | Metadata-only; lock is very brief |
| ADD COLUMN (with DEFAULT, PG 11+) | AccessExclusiveLock | Brief | Brief | No | PG 11+ stores default in pg_attribute; no rewrite |
| ADD COLUMN (with DEFAULT, PG <11) | AccessExclusiveLock | Yes | Yes | **Yes** | Full table rewrite |
| DROP COLUMN | AccessExclusiveLock | Brief | Brief | No | Marks column as dropped; physical removal on next VACUUM FULL |
| ALTER COLUMN SET DEFAULT | AccessExclusiveLock | Brief | Brief | No | Metadata-only |
| ALTER COLUMN DROP DEFAULT | AccessExclusiveLock | Brief | Brief | No | Metadata-only |
| ALTER COLUMN SET NOT NULL | AccessExclusiveLock | Brief | Brief | No (PG 12+) | PG 12+ skips scan if CHECK constraint already proves non-null |
| ALTER COLUMN DROP NOT NULL | AccessExclusiveLock | Brief | Brief | No | Metadata-only |
| ALTER COLUMN TYPE (same binary) | AccessExclusiveLock | Brief | Brief | No | e.g., varchar(50) → varchar(100), int → bigint on some versions |
| ALTER COLUMN TYPE (different) | AccessExclusiveLock | Yes | Yes | **Yes** | Full table rewrite; use pg_repack for large tables |
| RENAME COLUMN | AccessExclusiveLock | Brief | Brief | No | Metadata-only |

### Critical version gates:

- **PG 11+**: ADD COLUMN with non-volatile DEFAULT is metadata-only (no rewrite)
- **PG 12+**: SET NOT NULL can skip full-table scan if a valid CHECK constraint exists
- **PG <11**: ADD COLUMN with DEFAULT always rewrites the entire table

## Index Operations

| Operation | Lock Level | Blocks Reads? | Blocks Writes? | Notes |
|-----------|-----------|:---:|:---:|-------|
| CREATE INDEX | ShareLock | No | **Yes** | Blocks INSERT/UPDATE/DELETE for entire build |
| CREATE INDEX CONCURRENTLY | ShareUpdateExclusiveLock | No | No | Allows concurrent DML; takes 2-3× longer |
| DROP INDEX | AccessExclusiveLock | Brief | Brief | Very fast (metadata-only) |
| DROP INDEX CONCURRENTLY | ShareUpdateExclusiveLock | No | No | Non-blocking drop |
| REINDEX | AccessExclusiveLock | Yes | Yes | Locks table for entire rebuild |
| REINDEX CONCURRENTLY (PG 12+) | ShareUpdateExclusiveLock | No | No | Non-blocking reindex |

### CONCURRENTLY caveats:

- Cannot run inside a transaction block (`BEGIN ... COMMIT`)
- If interrupted, leaves an INVALID index that must be dropped and recreated
- Takes 2-3× longer than regular index build
- Requires two table scans (first builds, second validates)
- Check for invalid indexes: `SELECT indexrelid::regclass FROM pg_index WHERE NOT indisvalid;`

## Constraint Operations

| Operation | Lock Level | Blocks Reads? | Blocks Writes? | Validates? | Notes |
|-----------|-----------|:---:|:---:|:---:|-------|
| ADD CONSTRAINT (FK/CHECK) | AccessExclusiveLock | Yes | Yes | **Yes** | Full scan + lock held during validation |
| ADD CONSTRAINT ... NOT VALID | AccessExclusiveLock | Brief | Brief | **No** | Brief lock; skips row validation |
| VALIDATE CONSTRAINT | ShareUpdateExclusiveLock | No | No | **Yes** | Non-blocking validation pass |
| DROP CONSTRAINT | AccessExclusiveLock | Brief | Brief | No | Metadata-only |
| ADD CONSTRAINT (UNIQUE) | ShareLock | No | Yes | Yes | Builds unique index internally |
| ADD CONSTRAINT (UNIQUE) using existing index | AccessExclusiveLock | Brief | Brief | No | `ALTER TABLE ADD CONSTRAINT ... USING INDEX idx;` |

### NOT VALID + VALIDATE two-step:

This is the **standard pattern** for adding FK/CHECK to production tables:

```sql
-- Step 1: brief AccessExclusiveLock (milliseconds)
ALTER TABLE orders ADD CONSTRAINT fk_user
  FOREIGN KEY (user_id) REFERENCES users(id) NOT VALID;

-- Step 2: ShareUpdateExclusiveLock (concurrent DML allowed)
ALTER TABLE orders VALIDATE CONSTRAINT fk_user;
```

**Why this matters**: A bare `ADD CONSTRAINT FK` on a 10M-row table holds AccessExclusiveLock
for the entire validation scan — potentially minutes. NOT VALID splits the lock into a brief
metadata change + a non-blocking validation.

## Table-Level Operations

| Operation | Lock Level | Blocks Reads? | Blocks Writes? | Notes |
|-----------|-----------|:---:|:---:|-------|
| TRUNCATE | AccessExclusiveLock | Yes | Yes | Instant data removal but blocks everything |
| VACUUM | ShareUpdateExclusiveLock | No | No | Reclaims dead tuples; doesn't block DML |
| VACUUM FULL | AccessExclusiveLock | Yes | Yes | Rewrites table; use pg_repack instead |
| ANALYZE | ShareUpdateExclusiveLock | No | No | Updates statistics; non-blocking |
| ALTER TABLE SET (fillfactor=...) | AccessExclusiveLock | Brief | Brief | Metadata-only |
| ALTER TABLE ADD PARTITION | AccessExclusiveLock | Brief | Brief | Attaching partition to partitioned table |
| ALTER TABLE DETACH PARTITION | AccessExclusiveLock | Brief | Brief | PG 14+: DETACH CONCURRENTLY available |
| ALTER TABLE DETACH PARTITION CONCURRENTLY (PG 14+) | ShareUpdateExclusiveLock | No | No | Non-blocking partition detach |

## Decision Flowchart

```
Is this an index operation?
  ├─ YES → Use CONCURRENTLY variant (CREATE/DROP/REINDEX CONCURRENTLY)
  │        Remember: cannot run inside transaction
  └─ NO
      │
      Is this a constraint addition (FK/CHECK)?
        ├─ YES → Use NOT VALID + VALIDATE CONSTRAINT two-step
        └─ NO
            │
            Does this operation require table rewrite?
              ├─ YES (ALTER COLUMN TYPE, ADD COLUMN with DEFAULT on PG <11)
              │   │
              │   Is the table small (<1M rows)?
              │     ├─ YES → Run during low-traffic with lock_timeout
              │     └─ NO → Use pg_repack or create-swap-rename
              └─ NO → Proceed with lock_timeout set
                      (AccessExclusiveLock is brief for metadata-only ops)
```

## Monitoring Locks During Migration

```sql
-- Check current lock waiters
SELECT blocked_locks.pid AS blocked_pid,
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
```
# Large Table Migration Patterns for PostgreSQL

For tables exceeding ~10M rows, DDL operations requiring AccessExclusiveLock
for extended periods (table rewrites, full-table constraint validation) are
impractical in zero-downtime environments. This reference covers alternatives.

---

## Table of Contents

1. [pg_repack](#1-pg_repack)
2. [Create-Swap-Rename Pattern](#2-create-swap-rename-pattern)
3. [Chunked Backfill](#3-chunked-backfill)
4. [Partition-Based Migration](#4-partition-based-migration)
5. [Monitoring During Migration](#5-monitoring-during-migration)
6. [Abort and Recovery](#6-abort-and-recovery)

---

## 1. pg_repack

pg_repack reorganizes tables online without holding AccessExclusiveLock for more
than a brief moment during the final swap. It works by creating a shadow table,
using triggers to capture changes, then atomically swapping.

### Installation

```sql
CREATE EXTENSION IF NOT EXISTS pg_repack;
```

### Basic usage — table rewrite (e.g., after column type change)

```bash
# Repack a table (reorganize without long lock)
pg_repack --no-superuser-check -t target_table -d mydb

# Repack with specific column reorder (useful after schema changes)
pg_repack --no-superuser-check -t target_table -d mydb --order-by id
```

### For ALTER COLUMN TYPE on large tables

pg_repack doesn't directly change column types. Use this workflow:

1. Create a new table with the desired schema
2. Use pg_repack's trigger-based replication to copy data
3. Swap tables atomically

Alternative: use the create-swap-rename pattern (§2).

### pg_repack limitations

- Requires the `pg_repack` extension installed (superuser or rds_superuser)
- Target table must have a PRIMARY KEY or UNIQUE NOT NULL index
- Briefly acquires AccessExclusiveLock for the final swap (~milliseconds)
- Cannot repack tables with no PK/unique constraint
- Generates significant WAL during the copy phase

---

## 2. Create-Swap-Rename Pattern

When pg_repack isn't available or the schema change is complex, manually
create a new table with the target schema, migrate data, then swap.

### Workflow

```sql
-- Step 1: Create target table with new schema
CREATE TABLE orders_new (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id bigint NOT NULL REFERENCES users(id),
  amount numeric(12,4) NOT NULL,  -- changed from numeric(10,2)
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Step 2: Copy data with transformation
INSERT INTO orders_new (id, user_id, amount, created_at)
SELECT id, user_id, amount::numeric(12,4), created_at
FROM orders;

-- Step 3: Create matching indexes on new table
CREATE INDEX CONCURRENTLY idx_orders_new_user ON orders_new (user_id);
CREATE INDEX CONCURRENTLY idx_orders_new_date ON orders_new (created_at);

-- Step 4: Atomic swap (brief AccessExclusiveLock)
BEGIN;
SET LOCAL lock_timeout = '5s';
ALTER TABLE orders RENAME TO orders_old;
ALTER TABLE orders_new RENAME TO orders;
-- Reset sequences if using IDENTITY
SELECT setval(pg_get_serial_sequence('orders', 'id'), (SELECT MAX(id) FROM orders));
COMMIT;

-- Step 5: Update foreign keys pointing to this table
-- (must be done carefully; each FK change is brief lock)

-- Step 6: Drop old table after verification period
-- DROP TABLE orders_old;
```

### Limitations

- Data inserted between copy and swap is lost → requires trigger-based sync or brief maintenance window
- Foreign keys pointing TO the old table must be re-pointed
- Sequences/identities need resetting
- Views and functions referencing the table need updating

---

## 3. Chunked Backfill

For populating new columns, batch by primary key range — never LIMIT/OFFSET.

### PostgreSQL-idiomatic backfill

```sql
-- Use a DO block with cursor-style batching
DO $$
DECLARE
  batch_size int := 5000;
  max_id bigint;
  current_id bigint := 0;
  affected int;
BEGIN
  SELECT MAX(id) INTO max_id FROM target_table;

  LOOP
    UPDATE target_table
    SET new_col = compute_value(old_col)
    WHERE id > current_id AND id <= current_id + batch_size
      AND new_col IS NULL;

    GET DIAGNOSTICS affected = ROW_COUNT;
    current_id := current_id + batch_size;

    -- Commit each batch to release locks and allow vacuum
    COMMIT;

    -- Throttle: pause between batches
    PERFORM pg_sleep(0.1);

    EXIT WHEN current_id > max_id;
  END LOOP;
END $$;
```

Note: `COMMIT` inside DO blocks requires PostgreSQL 11+ with procedures (`CREATE PROCEDURE`)
or running batches as separate statements from the application.

### Application-level backfill (Go example)

```go
const batchSize = 5000
var lastID int64 = 0

for {
    result, err := db.ExecContext(ctx, `
        UPDATE target_table
        SET new_col = compute_value(old_col)
        WHERE id > $1 AND id <= $2 AND new_col IS NULL`,
        lastID, lastID+batchSize)
    if err != nil {
        return fmt.Errorf("backfill at id=%d: %w", lastID, err)
    }

    affected, _ := result.RowsAffected()
    lastID += batchSize

    if lastID > maxID {
        break
    }

    // Monitor replication lag
    if lag := checkReplicaLag(ctx, db); lag > maxLagThreshold {
        log.Warn("replica lag high, pausing", "lag", lag)
        time.Sleep(5 * time.Second)
    }

    time.Sleep(100 * time.Millisecond)
}
```

### Backfill tuning

| Parameter | Guidance |
|-----------|----------|
| Batch size | 1000–10000; decrease if autovacuum falls behind |
| Sleep between batches | 0.05–0.5s; increase during peak |
| Transaction per batch | YES — commit each batch to prevent long-running xid |
| Progress tracking | Log current_id for resume after interruption |
| Post-backfill | Run `ANALYZE target_table` to update statistics |

---

## 4. Partition-Based Migration

For very large tables (>100M rows), converting to partitioned tables enables
instant old-data cleanup and rolling schema changes.

### Converting non-partitioned → partitioned

PostgreSQL doesn't support `ALTER TABLE ... PARTITION BY` on existing tables.
The migration requires:

1. Create partitioned parent with desired schema
2. Create partitions (by range, list, or hash)
3. Migrate data partition-by-partition (can be done online)
4. Swap via rename (brief AccessExclusiveLock)
5. Re-point foreign keys and update application

### Detaching partitions (PG 14+)

```sql
-- PG 14+: non-blocking partition detach
ALTER TABLE parent DETACH PARTITION old_partition CONCURRENTLY;

-- PG <14: requires AccessExclusiveLock
ALTER TABLE parent DETACH PARTITION old_partition;
```

---

## 5. Monitoring During Migration

### Essential queries

```sql
-- Replication lag (on replica)
SELECT now() - pg_last_xact_replay_timestamp() AS replication_lag;

-- Dead tuple count (backfill creates dead tuples)
SELECT relname, n_dead_tup, last_vacuum, last_autovacuum
FROM pg_stat_user_tables
WHERE relname = '<table>';

-- Lock waiters
SELECT pid, wait_event_type, wait_event, query
FROM pg_stat_activity
WHERE wait_event_type = 'Lock';

-- Table bloat estimate
SELECT relname, pg_total_relation_size(oid) AS total_size
FROM pg_class WHERE relname = '<table>';

-- Invalid indexes (from interrupted CONCURRENTLY builds)
SELECT indexrelid::regclass, indisvalid
FROM pg_index WHERE NOT indisvalid;
```

### Alert thresholds during migration

- Replication lag > 5 seconds → pause backfill
- Dead tuples > 10% of reltuples → trigger manual VACUUM
- Lock wait time > 3 seconds → investigate and retry
- Disk usage > 85% → pause and assess

---

## 6. Abort and Recovery

### Failed CONCURRENTLY index build

```sql
-- Check for invalid indexes
SELECT indexrelid::regclass FROM pg_index WHERE NOT indisvalid;

-- Drop the invalid index and retry
DROP INDEX CONCURRENTLY IF EXISTS idx_invalid;
CREATE INDEX CONCURRENTLY idx_name ON table (columns);
```

### Failed pg_repack

pg_repack creates temporary objects during operation:
- `repack.table_<oid>` — shadow table
- Triggers on the original table

If pg_repack crashes mid-operation:
```sql
-- Check for leftover objects
SELECT * FROM pg_catalog.pg_tables WHERE schemaname = 'repack';

-- Clean up (pg_repack has a cleanup mode)
-- pg_repack --no-superuser-check -d mydb --dry-run
-- Or manually:
DROP SCHEMA repack CASCADE;  -- if cleanup needed
```

### Resuming interrupted backfill

If using the application-level backfill pattern (§3), the last processed ID
provides the resume point. Query:
```sql
SELECT MAX(id) FROM target_table WHERE new_col IS NOT NULL;
```
Resume from this ID + 1.
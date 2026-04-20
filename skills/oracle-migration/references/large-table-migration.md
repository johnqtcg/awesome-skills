# Large Table Migration Patterns for Oracle

For tables exceeding ~10M rows, direct DDL that rewrites the table (MODIFY column type,
DROP COLUMN, MOVE) holds an exclusive lock for extended periods. This reference covers
online alternatives.

---

## Table of Contents

1. [DBMS_REDEFINITION](#1-dbms_redefinition)
2. [CTAS + Swap Pattern](#2-ctas--swap-pattern)
3. [ROWID-Range Batched DML](#3-rowid-range-batched-dml)
4. [Partition Exchange Migration](#4-partition-exchange-migration)
5. [Monitoring During Migration](#5-monitoring-during-migration)
6. [Abort and Recovery](#6-abort-and-recovery)

---

## 1. DBMS_REDEFINITION

Oracle's built-in online table redefinition package. Requires **Enterprise Edition**.
Creates an interim table, uses materialized view logs to sync changes, then atomically
swaps at the end with a very brief exclusive lock.

### Basic workflow

```sql
-- Step 1: Verify table can be redefined
BEGIN
  DBMS_REDEFINITION.CAN_REDEF_TABLE('SCHEMA', 'TARGET_TABLE');
END;
/

-- Step 2: Create interim table with desired new schema
CREATE TABLE target_table_interim AS
SELECT id, user_id, CAST(amount AS NUMBER(12,4)) AS amount, created_at
FROM target_table WHERE 1=0;

-- Step 3: Start redefinition
BEGIN
  DBMS_REDEFINITION.START_REDEF_TABLE(
    uname        => 'SCHEMA',
    orig_table   => 'TARGET_TABLE',
    int_table    => 'TARGET_TABLE_INTERIM',
    col_mapping  => 'id id, user_id user_id, CAST(amount AS NUMBER(12,4)) amount, created_at created_at'
  );
END;
/

-- Step 4: Copy dependent objects (indexes, constraints, triggers, grants)
DECLARE
  num_errors PLS_INTEGER;
BEGIN
  DBMS_REDEFINITION.COPY_TABLE_DEPENDENTS(
    uname         => 'SCHEMA',
    orig_table    => 'TARGET_TABLE',
    int_table     => 'TARGET_TABLE_INTERIM',
    num_errors    => num_errors
  );
  DBMS_OUTPUT.PUT_LINE('Errors: ' || num_errors);
END;
/

-- Step 5: Sync (if redefinition took a long time, sync before finish)
BEGIN
  DBMS_REDEFINITION.SYNC_INTERIM_TABLE('SCHEMA', 'TARGET_TABLE', 'TARGET_TABLE_INTERIM');
END;
/

-- Step 6: Finish (atomic swap — brief exclusive lock)
BEGIN
  DBMS_REDEFINITION.FINISH_REDEF_TABLE('SCHEMA', 'TARGET_TABLE', 'TARGET_TABLE_INTERIM');
END;
/

-- Step 7: Cleanup
DROP TABLE target_table_interim PURGE;
```

### Key flags and options

| Parameter | Purpose | Notes |
|-----------|---------|-------|
| `col_mapping` | Column transformation expressions | Required when changing types or adding computed columns |
| `options_flag` | `DBMS_REDEFINITION.CONS_USE_ROWID` or `CONS_USE_PK` | PK-based is preferred; ROWID-based for tables without PK |
| `COPY_TABLE_DEPENDENTS` | Copies indexes, constraints, triggers, grants | May report errors for objects that can't be copied |
| `SYNC_INTERIM_TABLE` | Syncs accumulated changes before finish | Reduces final swap time |

### DBMS_REDEFINITION limitations

- Requires **Enterprise Edition**
- Table must have a PRIMARY KEY (or use ROWID-based with limitations)
- Cannot redefine tables with LONG or LONG RAW columns (use CLOB/BLOB instead)
- Materialized view log adds overhead to DML during redefinition
- UNDO consumption increases due to MV log
- Final swap is a brief exclusive lock but still blocks for a moment

---

## 2. CTAS + Swap Pattern

When DBMS_REDEFINITION is unavailable (Standard Edition) or the transformation is simple.

### Workflow

```sql
-- Step 1: Create new table with desired schema (direct path for speed)
CREATE TABLE orders_new
NOLOGGING
AS SELECT id, user_id,
          CAST(amount AS NUMBER(12,4)) AS amount,
          created_at
FROM orders;

-- Step 2: Switch to logging
ALTER TABLE orders_new LOGGING;

-- Step 3: Create indexes on new table
CREATE INDEX idx_orders_new_user ON orders_new (user_id);
CREATE INDEX idx_orders_new_date ON orders_new (created_at);

-- Step 4: Add constraints
ALTER TABLE orders_new ADD CONSTRAINT pk_orders_new PRIMARY KEY (id);
ALTER TABLE orders_new ADD CONSTRAINT fk_orders_new_user
  FOREIGN KEY (user_id) REFERENCES users(id) ENABLE NOVALIDATE;

-- Step 5: Atomic swap (brief exclusive lock on both tables)
ALTER SESSION SET DDL_LOCK_TIMEOUT = 5;
ALTER TABLE orders RENAME TO orders_old;
ALTER TABLE orders_new RENAME TO orders;

-- Step 6: Validate constraints
ALTER TABLE orders MODIFY CONSTRAINT fk_orders_new_user VALIDATE;

-- Step 7: Cleanup after verification
-- DROP TABLE orders_old PURGE;
```

### Limitations

- Data inserted between CTAS and rename is lost → requires brief maintenance window or trigger-based sync
- Foreign keys pointing TO the old table must be re-pointed
- Grants, synonyms, and triggers don't transfer automatically
- NOLOGGING means no redo for the CTAS → not recoverable from archive logs (re-run CTAS if needed)

---

## 3. ROWID-Range Batched DML

Oracle's idiomatic approach for large-scale data backfills. Uses ROWID ranges
to partition work across chunks.

### PL/SQL batched update

```sql
DECLARE
  CURSOR c_chunks IS
    SELECT DBMS_ROWID.ROWID_CREATE(1, data_object_id, relative_fno, block_id, 0) AS start_rowid,
           DBMS_ROWID.ROWID_CREATE(1, data_object_id, relative_fno, block_id + blocks - 1, 32767) AS end_rowid
    FROM dba_extents
    WHERE segment_name = 'TARGET_TABLE' AND owner = 'SCHEMA'
    ORDER BY block_id;

  v_rows_updated NUMBER := 0;
BEGIN
  FOR chunk IN c_chunks LOOP
    UPDATE target_table
    SET new_col = compute_value(old_col)
    WHERE ROWID BETWEEN chunk.start_rowid AND chunk.end_rowid
      AND new_col IS NULL;

    v_rows_updated := v_rows_updated + SQL%ROWCOUNT;
    COMMIT;

    -- Throttle if needed
    DBMS_LOCK.SLEEP(0.1);
  END LOOP;

  DBMS_OUTPUT.PUT_LINE('Total rows updated: ' || v_rows_updated);
END;
/
```

### Simpler PK-range batching

```sql
DECLARE
  v_batch_size NUMBER := 5000;
  v_max_id     NUMBER;
  v_current_id NUMBER := 0;
BEGIN
  SELECT MAX(id) INTO v_max_id FROM target_table;

  WHILE v_current_id < v_max_id LOOP
    UPDATE target_table
    SET new_col = compute_value(old_col)
    WHERE id > v_current_id AND id <= v_current_id + v_batch_size
      AND new_col IS NULL;

    v_current_id := v_current_id + v_batch_size;
    COMMIT;
    DBMS_LOCK.SLEEP(0.1);
  END LOOP;
END;
/
```

### Backfill tuning

| Parameter | Guidance |
|-----------|----------|
| Batch size | 1000–10000; decrease if UNDO pressure rises |
| COMMIT frequency | Every batch — prevents UNDO exhaustion |
| Sleep between batches | 0.05–0.5s; increase during peak hours |
| Post-backfill | Run `DBMS_STATS.GATHER_TABLE_STATS` |
| Monitor | Check `V$UNDOSTAT` for UNDO pressure during backfill |

---

## 4. Partition Exchange Migration

For partitioned tables, EXCHANGE PARTITION provides near-instant data swap
with a staging table — useful for bulk data loading.

```sql
-- Step 1: Create staging table matching partition structure
CREATE TABLE staging_data AS SELECT * FROM target_table WHERE 1=0;

-- Step 2: Load data into staging (bulk insert, CTAS, etc.)
INSERT /*+ APPEND */ INTO staging_data SELECT ... FROM source;
COMMIT;

-- Step 3: Exchange partition (near-instant)
ALTER TABLE target_table
  EXCHANGE PARTITION p_2024_q1 WITH TABLE staging_data
  INCLUDING INDEXES WITHOUT VALIDATION
  UPDATE INDEXES;

-- Step 4: Validate if needed
ALTER TABLE target_table MODIFY PARTITION p_2024_q1 REBUILD UNUSABLE LOCAL INDEXES;
```

---

## 5. Monitoring During Migration

```sql
-- UNDO tablespace usage
SELECT tablespace_name, used_percent FROM dba_tablespace_usage_metrics
WHERE tablespace_name LIKE '%UNDO%';

-- Long-running transactions (UNDO consumers)
SELECT s.sid, s.serial#, t.used_ublk, t.used_urec, s.sql_id
FROM v$transaction t JOIN v$session s ON t.ses_addr = s.saddr
ORDER BY t.used_ublk DESC;

-- DDL lock waiters
SELECT * FROM dba_ddl_locks WHERE name = '<TABLE>';

-- Progress of DBMS_REDEFINITION
SELECT * FROM v$online_redef;

-- Blocking sessions
SELECT blocking_session, sid, serial#, event, seconds_in_wait
FROM v$session WHERE blocking_session IS NOT NULL;
```

---

## 6. Abort and Recovery

### Failed DBMS_REDEFINITION

```sql
-- Abort and clean up
BEGIN
  DBMS_REDEFINITION.ABORT_REDEF_TABLE('SCHEMA', 'TARGET_TABLE', 'TARGET_TABLE_INTERIM');
END;
/
DROP TABLE target_table_interim PURGE;
```

### Flashback recovery (catastrophic DDL mistake)

```sql
-- Flashback table (requires FLASHBACK privilege and row movement enabled)
ALTER TABLE target_table ENABLE ROW MOVEMENT;
FLASHBACK TABLE target_table TO TIMESTAMP (SYSTIMESTAMP - INTERVAL '1' HOUR);

-- Flashback dropped table (from recycle bin)
FLASHBACK TABLE target_table TO BEFORE DROP;

-- Check recycle bin
SELECT object_name, original_name, droptime FROM recyclebin;
```

### Resuming interrupted backfill

Track progress via the maximum processed PK/ROWID:
```sql
SELECT MAX(id) FROM target_table WHERE new_col IS NOT NULL;
```
Resume from this value + 1.
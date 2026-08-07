# Large Table Migration Patterns for Oracle

Two different problems send you here, and they need to be told apart before choosing a
pattern:

1. **The statement is rejected.** Changing a column's datatype class (`ORA-01439`) or
   decreasing its `NUMBER` precision/scale (`ORA-01440`) requires the column to be empty.
   Table size is irrelevant — this fails just as fast on 1 row as on 500M. No amount of
   maintenance window makes a direct `ALTER` work.
2. **The statement is accepted but slow.** `DROP COLUMN`, `DROP UNUSED COLUMNS` and
   `ALTER TABLE … MOVE` physically rewrite rows under an exclusive lock, which on a
   >10M-row table means minutes to hours of blocked DML.

Both are solved by the patterns below, but do not describe the first as "a long lock" —
it is a hard error. And do **not** send a *widening* here at all: increasing a
`VARCHAR2` length, or a `NUMBER`'s precision and scale together, is a data-dictionary
update with a brief lock and needs none of this machinery.

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

The worked example converts `created_at` from `DATE` to `TIMESTAMP WITH TIME ZONE`. This
is a change of datatype class, so a direct `ALTER TABLE … MODIFY` is rejected with
`ORA-01439` no matter how small the table or how long the window — which is exactly the
situation redefinition exists for.

```sql
-- Step 1: Verify table can be redefined.
--         CAN_REDEF_TABLE raises on failure, so run it as its own step and stop if it does.
BEGIN
  DBMS_REDEFINITION.CAN_REDEF_TABLE(
    uname        => 'SCHEMA',
    tname        => 'TARGET_TABLE',
    options_flag => DBMS_REDEFINITION.CONS_USE_PK);
END;
/

-- Step 2: Create interim table with the desired new schema
CREATE TABLE target_table_interim (
  id          NUMBER,
  user_id     NUMBER,
  amount      NUMBER(12,2),
  created_at  TIMESTAMP WITH TIME ZONE
);

-- Step 3: Start redefinition
BEGIN
  DBMS_REDEFINITION.START_REDEF_TABLE(
    uname        => 'SCHEMA',
    orig_table   => 'TARGET_TABLE',
    int_table    => 'TARGET_TABLE_INTERIM',
    col_mapping  => 'id id, user_id user_id, amount amount, '
                 || 'CAST(created_at AS TIMESTAMP WITH TIME ZONE) created_at',
    options_flag => DBMS_REDEFINITION.CONS_USE_PK
  );
END;
/

-- Step 4: Copy dependent objects (indexes, constraints, triggers, grants)
--         num_errors is an OUT parameter that Oracle requires you to CHECK.
--         Proceeding past a non-zero count is how a migration silently loses
--         indexes, constraints, triggers or grants at cutover.
DECLARE
  num_errors PLS_INTEGER;
BEGIN
  DBMS_REDEFINITION.COPY_TABLE_DEPENDENTS(
    uname         => 'SCHEMA',
    orig_table    => 'TARGET_TABLE',
    int_table     => 'TARGET_TABLE_INTERIM',
    copy_indexes  => DBMS_REDEFINITION.CONS_ORIG_PARAMS,
    copy_triggers => TRUE,
    copy_constraints => TRUE,
    copy_privileges  => TRUE,
    ignore_errors    => FALSE,
    num_errors    => num_errors
  );

  IF num_errors > 0 THEN
    RAISE_APPLICATION_ERROR(-20001,
      'COPY_TABLE_DEPENDENTS reported ' || num_errors ||
      ' error(s). Inspect DBA_REDEFINITION_ERRORS, fix, and re-copy before FINISH.');
  END IF;
END;
/

-- Step 4b: MANDATORY gate before going further. Must return zero rows.
SELECT object_type, object_name, base_table_name, ddl_txt
FROM   dba_redefinition_errors
WHERE  base_table_name = 'TARGET_TABLE';

-- Step 5: Sync (if redefinition took a long time, sync before finish)
BEGIN
  DBMS_REDEFINITION.SYNC_INTERIM_TABLE('SCHEMA', 'TARGET_TABLE', 'TARGET_TABLE_INTERIM');
END;
/

-- Step 6: Finish — this one IS a single atomic swap, with a brief exclusive lock.
--         Set dml_lock_timeout (12.1+) explicitly. Its default is NULL, which means
--         "no cap": the swap waits for pending DML for as long as that takes, so one
--         long-running transaction hangs the cutover past the end of the window with
--         nothing to time it out. The opposite extreme, 0, is NOWAIT and aborts on the
--         first concurrent DML after hours of copying. Size the value to the window.
BEGIN
  DBMS_REDEFINITION.FINISH_REDEF_TABLE(
    uname            => 'SCHEMA',
    orig_table       => 'TARGET_TABLE',
    int_table        => 'TARGET_TABLE_INTERIM',
    dml_lock_timeout => 30
  );
END;
/

-- Step 7: Verify the swap landed before dropping anything
SELECT index_name, status FROM user_indexes WHERE table_name = 'TARGET_TABLE';
SELECT constraint_name, status, validated FROM user_constraints WHERE table_name = 'TARGET_TABLE';
SELECT trigger_name, status FROM user_triggers WHERE table_name = 'TARGET_TABLE';

-- Step 8: Cleanup (only after step 7 matches the pre-migration inventory)
DROP TABLE target_table_interim PURGE;
```

> **Take the dependent-object inventory *before* you start**, and diff it against step 7.
> `COPY_TABLE_DEPENDENTS` can report zero errors and still leave you with fewer objects
> than you expected if a dependent was created after the copy. The inventory diff is the
> check that actually catches this; `num_errors = 0` alone does not.

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
-- Step 1: Create new table with desired schema (direct path for speed).
--         NOLOGGING is ignored if the database or tablespace is in FORCE LOGGING —
--         check first, or your window estimate is wrong. See the note at the end.
CREATE TABLE orders_new
NOLOGGING
AS SELECT id, user_id,
          amount,
          CAST(created_at AS TIMESTAMP WITH TIME ZONE) AS created_at
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

-- Step 5: TWO-STATEMENT CUTOVER — this is NOT atomic. See the warning below.
ALTER SESSION SET DDL_LOCK_TIMEOUT = 5;
ALTER TABLE orders     RENAME TO orders_old;   -- implicit COMMIT; `orders` now does not exist
ALTER TABLE orders_new RENAME TO orders;       -- implicit COMMIT

-- Step 6: Validate constraints
ALTER TABLE orders MODIFY CONSTRAINT fk_orders_new_user VALIDATE;

-- Step 7: Cleanup after verification
-- DROP TABLE orders_old PURGE;
```

### The cutover is two statements, not an atomic swap

Each `ALTER TABLE … RENAME` is its own DDL with its own implicit `COMMIT` before and
after. There is no transaction wrapping the pair and no way to create one. Between them
the schema has **no table named `orders`** — every application query fails with
`ORA-00942`. If the second rename fails (someone holds a lock on `orders_new`, the
`DDL_LOCK_TIMEOUT` expires, the session dies), you are left in that state until a human
intervenes.

Plan it as a **two-step cutover inside a maintenance window**, never as a swap:

```sql
-- 0. Quiesce: stop the app or put it in read-only/maintenance mode. Do not skip this.
--    Confirm nothing is attached before touching the names:
SELECT s.sid, s.serial#, s.username, s.program
FROM   v$session s JOIN v$locked_object lo ON s.sid = lo.session_id
JOIN   dba_objects o ON lo.object_id = o.object_id
WHERE  o.object_name IN ('ORDERS', 'ORDERS_NEW');

-- 1. Rename away
ALTER SESSION SET DDL_LOCK_TIMEOUT = 5;
ALTER TABLE orders RENAME TO orders_old;

-- 2. Rename in. If THIS fails, recover immediately with:
--       ALTER TABLE orders_old RENAME TO orders;
--    and abort the migration. Have that line ready to paste before you start step 1.
ALTER TABLE orders_new RENAME TO orders;

-- 3. Smoke-test before releasing traffic
SELECT COUNT(*) FROM orders;
SELECT status FROM user_objects WHERE object_name = 'ORDERS';
```

If a no-downtime cutover is genuinely required, CTAS+rename is the wrong tool — use
DBMS_REDEFINITION, whose `FINISH_REDEF_TABLE` *is* a single atomic operation.

### What RENAME does not carry over

`RENAME` moves the name, not the ecosystem around it. Before the window, inventory and
plan each of these — every one of them is a separate outage if missed:

| Object | Behaviour on rename | Action |
|--------|--------------------|--------|
| Inbound foreign keys from other tables | Still point at the *segment*, which is now `orders_old` | Recreate against the new table |
| Private/public synonyms | Keep pointing at the old name | Recreate |
| Grants | Do not transfer to `orders_new` | Re-grant before cutover |
| Triggers | Do not transfer | Recreate on `orders_new` before cutover |
| Views, packages, procedures | Become `INVALID`; recompile on next use or fail | `UTL_RECOMP` / explicit recompile, then check `USER_OBJECTS` |
| Virtual columns, default expressions | Not produced by a plain `CTAS` | Add explicitly |

```sql
-- Run before the window; every row here is work you still owe
SELECT constraint_name, table_name FROM user_constraints
WHERE  r_constraint_name IN (SELECT constraint_name FROM user_constraints
                             WHERE table_name = 'ORDERS');
SELECT synonym_name, table_name FROM all_synonyms WHERE table_name = 'ORDERS';
SELECT grantee, privilege  FROM user_tab_privs   WHERE table_name = 'ORDERS';
SELECT trigger_name        FROM user_triggers    WHERE table_name = 'ORDERS';
```

### Other limitations

- Data written between the CTAS and the rename is **lost** — this pattern needs the
  quiesce window above, or trigger-based change capture into `orders_new`
- `NOLOGGING` generates no redo: the CTAS is not recoverable from archive logs, and on a
  Data Guard primary the standby receives unusable blocks. Check
  `SELECT force_logging FROM v$database` first — if the database (or tablespace) is in
  `FORCE LOGGING`, the `NOLOGGING` clause is silently ignored and your runtime estimate
  is wrong. Take a backup immediately after any genuinely NOLOGGING load.

---

## 3. ROWID-Range Batched DML

Oracle's idiomatic approach for large-scale data backfills. Uses ROWID ranges
to partition work across chunks.

### Preferred: DBMS_PARALLEL_EXECUTE (11.2+)

Oracle ships a supported chunking API. Prefer it over hand-rolled ROWID arithmetic — it
computes the chunks correctly for partitioned and non-partitioned tables, persists chunk
state so an interrupted run resumes instead of restarting, and gives you a progress view
for free.

```sql
DECLARE
  l_task VARCHAR2(30) := 'backfill_new_col';
BEGIN
  DBMS_PARALLEL_EXECUTE.CREATE_TASK(l_task);

  -- Chunk by ROWID range; ~50k rows per chunk is a reasonable starting point
  DBMS_PARALLEL_EXECUTE.CREATE_CHUNKS_BY_ROWID(
    task_name   => l_task,
    table_owner => 'SCHEMA',
    table_name  => 'TARGET_TABLE',
    by_row      => TRUE,
    chunk_size  => 50000);

  -- :start_id / :end_id are bound by the framework, one pair per chunk.
  -- Each chunk commits independently, so a failure loses one chunk, not the run.
  DBMS_PARALLEL_EXECUTE.RUN_TASK(
    task_name      => l_task,
    sql_stmt       => 'UPDATE target_table SET new_col = compute_value(old_col)
                       WHERE ROWID BETWEEN :start_id AND :end_id AND new_col IS NULL',
    language_flag  => DBMS_SQL.NATIVE,
    parallel_level => 4);
END;
/

-- Monitor / resume
SELECT status, COUNT(*) FROM user_parallel_execute_chunks
WHERE task_name = 'backfill_new_col' GROUP BY status;

-- Re-run only the chunks that failed
BEGIN DBMS_PARALLEL_EXECUTE.RESUME_TASK('backfill_new_col'); END;
/
BEGIN DBMS_PARALLEL_EXECUTE.DROP_TASK('backfill_new_col'); END;
/
```

`parallel_level` consumes that many parallel-query slaves — size it against
`PARALLEL_MAX_SERVERS` and the load the OLTP workload can tolerate, not against CPU count.

### Manual ROWID chunking (when DBMS_PARALLEL_EXECUTE is unavailable)

**`DBA_EXTENTS` has no `DATA_OBJECT_ID` column.** Its columns are `OWNER`,
`SEGMENT_NAME`, `PARTITION_NAME`, `SEGMENT_TYPE`, `TABLESPACE_NAME`, `EXTENT_ID`,
`FILE_ID`, `BLOCK_ID`, `BYTES`, `BLOCKS`, `RELATIVE_FNO`. Selecting `data_object_id`
from it fails with `ORA-00904: invalid identifier` — you must join to `DBA_OBJECTS`, and
you must join **per partition**, because every partition carries its own
`DATA_OBJECT_ID`.

```sql
DECLARE
  CURSOR c_chunks IS
    SELECT DBMS_ROWID.ROWID_CREATE(1, o.data_object_id, e.relative_fno,
                                   e.block_id, 0) AS start_rowid,
           DBMS_ROWID.ROWID_CREATE(1, o.data_object_id, e.relative_fno,
                                   e.block_id + e.blocks - 1, 32767) AS end_rowid
    FROM   dba_extents e
    JOIN   dba_objects o
           ON  o.owner       = e.owner
           AND o.object_name = e.segment_name
           -- NULL-safe: matches the table row for a heap table and the
           -- correct partition row for a partitioned one
           AND NVL(o.subobject_name, '#') = NVL(e.partition_name, '#')
           AND o.data_object_id IS NOT NULL
    WHERE  e.segment_name = 'TARGET_TABLE'
      AND  e.owner        = 'SCHEMA'
      AND  e.segment_type IN ('TABLE', 'TABLE PARTITION', 'TABLE SUBPARTITION')
    ORDER BY e.relative_fno, e.block_id;

  v_rows_updated NUMBER := 0;
BEGIN
  FOR chunk IN c_chunks LOOP
    UPDATE target_table
    SET new_col = compute_value(old_col)
    WHERE ROWID BETWEEN chunk.start_rowid AND chunk.end_rowid
      AND new_col IS NULL;

    v_rows_updated := v_rows_updated + SQL%ROWCOUNT;
    COMMIT;

    -- Throttle. DBMS_SESSION.SLEEP is 18c+ and executable by any user;
    -- DBMS_LOCK.SLEEP works on older releases but needs an explicit
    -- GRANT EXECUTE ON DBMS_LOCK, which is not held by default.
    DBMS_SESSION.SLEEP(0.1);
  END LOOP;

  DBMS_OUTPUT.PUT_LINE('Total rows updated: ' || v_rows_updated);
END;
/
```

Reading `DBA_EXTENTS`/`DBA_OBJECTS` requires DBA-level select privileges the migration
account often lacks. If the grant is refused, fall back to PK-range batching below — it
needs nothing beyond access to the table itself.

### Simpler PK-range batching

Drive the loop off **rows that still need work**, not off the numeric range. A fixed
`v_current_id := v_current_id + batch` walk spins through every empty gap: on a table
whose IDs come from a sequence that has been cycled or seeded high, `MAX(id)` can be
10^12 while the table holds 20M rows, and the loop burns billions of no-op iterations.

```sql
DECLARE
  v_batch_size   PLS_INTEGER := 5000;
  v_current_id   NUMBER;
  v_last_id      NUMBER;
  v_rows_updated NUMBER := 0;
BEGIN
  -- Start below the true minimum so the first batch cannot skip a row.
  -- MIN(id) - 1 also handles zero and negative IDs, which a literal 0 would drop.
  SELECT MIN(id) - 1 INTO v_current_id FROM target_table WHERE new_col IS NULL;

  WHILE v_current_id IS NOT NULL LOOP
    -- Upper bound of this batch = the v_batch_size-th outstanding id above the cursor.
    -- Skips gaps in one index range scan instead of iterating over them.
    SELECT MAX(id) INTO v_last_id
    FROM   (SELECT id FROM target_table
            WHERE  id > v_current_id AND new_col IS NULL
            ORDER  BY id
            FETCH FIRST v_batch_size ROWS ONLY);   -- 12.1+; else ROWNUM <= v_batch_size

    EXIT WHEN v_last_id IS NULL;                    -- nothing left to do

    UPDATE target_table
    SET    new_col = compute_value(old_col)
    WHERE  id > v_current_id AND id <= v_last_id
      AND  new_col IS NULL;

    v_rows_updated := v_rows_updated + SQL%ROWCOUNT;
    v_current_id   := v_last_id;
    COMMIT;

    DBMS_SESSION.SLEEP(0.1);   -- 18c+; see the DBMS_LOCK note above for older releases
  END LOOP;

  DBMS_OUTPUT.PUT_LINE('Total rows updated: ' || v_rows_updated);
END;
/
```

This needs an index on `id` (the PK supplies it) and benefits from one on `new_col` or a
function-based index on `NVL(new_col, …)` when the outstanding set is a small fraction of
the table. Without either, each batch degenerates into a full scan and the backfill gets
slower as it progresses.

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

### Recovery after a mistake — pick by damage type, not by convenience

`FLASHBACK TABLE … TO SCN/TIMESTAMP` is **not** a general undo for DDL. Oracle documents
that a table cannot be flashed back across a DDL that changed its structure, and the
blocking list covers most of what a migration does: *upgrading, moving or truncating a
table; adding a constraint; adding a table to a cluster; **modifying or dropping a
column**; changing a column encryption key; adding, dropping, merging, splitting,
coalescing or truncating a partition or subpartition (adding a range partition excepted)*.

So the answer to "I dropped the wrong column, can I flash back?" is **no**.

| Damage | Tool | Edition | Notes |
|--------|------|---------|-------|
| Wrong `UPDATE`/`DELETE`, structure untouched since | `FLASHBACK TABLE … TO TIMESTAMP` | **EE only** | Needs `ENABLE ROW MOVEMENT`, `FLASHBACK` privilege, and UNDO still retained — `UNDO_RETENTION` is a target, not a guarantee, unless the tablespace has `RETENTION GUARANTEE` |
| Same, on **SE2** | `SELECT … AS OF TIMESTAMP` + write the rows back yourself | all editions | Flashback *Query* is plain UNDO read consistency and is not an EE feature; Flashback *Table* is. Same UNDO-retention caveat |
| `DROP TABLE` without `PURGE` | `FLASHBACK TABLE … TO BEFORE DROP` | all editions | Recycle-bin based, so neither the edition line nor the structural-DDL rule applies. Nothing is there if `PURGE` was used, on a `SYSTEM` tablespace object, or after space pressure evicted it |
| **Structural DDL** — dropped/modified column, `MOVE`, `TRUNCATE`, partition maintenance | Pre-DDL data copy → RMAN tablespace PITR → Flashback Database → full restore, in that order of preference | Flashback Database is **EE only**; RMAN restore is all editions | Flashback Database rewinds the **entire database**, losing every other transaction in the window. It is a real option only during an exclusive maintenance window |

The edition column is not a footnote. On SE2 the first row is unavailable and the third
loses its cheapest option, so an SE2 migration has effectively **one** recovery mechanism:
an artefact you created before the statement ran. Establish the edition before writing any
rollback plan.

```sql
-- Case 1: bad DML only
ALTER TABLE target_table ENABLE ROW MOVEMENT;
FLASHBACK TABLE target_table TO TIMESTAMP (SYSTIMESTAMP - INTERVAL '1' HOUR);

-- Case 2: dropped table, no PURGE
SELECT object_name, original_name, droptime FROM recyclebin;
FLASHBACK TABLE target_table TO BEFORE DROP;
```

#### Case 3 is prevention, because there is no cure

Structural DDL has no cheap undo, so the safety net must exist **before** the DDL runs.
Take one of these in the same change window and record which one in §9.7:

```sql
-- (a) Cheapest and most targeted: snapshot only the columns at risk.
--     Keyed by PK so it can be merged back after the mistake.
CREATE TABLE mig_bak_orders_20260806 AS
SELECT id, legacy_email, temp_flag FROM orders;

-- (b) GUARANTEED restore point. The keyword is the whole point — see below.
--     Needs ARCHIVELOG + a Fast Recovery Area, and holds flashback logs until
--     dropped, so it can fill the FRA. Always drop it when the migration is signed off.
CREATE RESTORE POINT before_v8_cleanup GUARANTEE FLASHBACK DATABASE;
-- ... run the migration ...
DROP RESTORE POINT before_v8_cleanup;

-- (c) Verify a backup actually exists — "there is a nightly backup" is not evidence
SELECT MAX(completion_time) FROM v$backup_datafile;
```

Recovering with (a) is a `MERGE` back into the table; with (b) it is
`FLASHBACK DATABASE TO RESTORE POINT before_v8_cleanup`, which discards **all** database
activity since the restore point and therefore requires the application to be down.
Neither is free — that is precisely why the review must state which one is in place
before approving an irreversible statement.

### A copy is only a backup if it copies everything

`CREATE TABLE x AS SELECT ... FROM y` reads as "I took a backup" in a review, but three
common variants restore nothing useful:

| Statement | What it actually is |
|-----------|--------------------|
| `… AS SELECT * FROM orders` | A backup |
| `… AS SELECT * FROM orders WHERE 1=0` | An **interim-table skeleton** — column definitions, zero rows. The opposite of a backup, and the standard first step of a CTAS or DBMS_REDEFINITION rebuild |
| `… AS SELECT * FROM orders WHERE ROWNUM <= 1000` | A sample. Restores 1000 rows of however many there were |
| `… AS SELECT id, other_col FROM orders` | A projection. Restores nothing outside those columns — in particular, not the column you are about to drop |

For a `DROP COLUMN` the copy must include the **primary key and the dropped column**, or
the rows cannot be matched back. For a `TRUNCATE` it must be unfiltered. If only a subset
genuinely matters, that is a legitimate decision — but it belongs in the rollback plan as
an explicit statement of what is *not* recoverable and who accepted that, not as an
unqualified "backup taken".

#### `GUARANTEE FLASHBACK DATABASE` is not optional wording

Dropping those three words gives you a *normal* restore point, which is a different
object with a different promise:

| | Normal restore point | Guaranteed restore point |
|---|---|---|
| What it is | An alias for an SCN | An alias for an SCN **plus** a retention contract |
| Flashback logs | Recycled on the ordinary schedule | Retained until the restore point is dropped — never purged while it exists |
| How far back you can go | Bounded by `DB_FLASHBACK_RETENTION_TARGET`, which Oracle documents as *a target, not a guarantee* | Deterministic, regardless of that parameter |
| Lifetime | Ages out of the control file by itself | Persists until an explicit `DROP RESTORE POINT` |
| Usable as a migration safety net | **No** | Yes, subject to FRA space |

So a plain `CREATE RESTORE POINT before_v27;` in front of a `DROP COLUMN` provides no
**guaranteed** recovery. It may well work — if the flashback logs covering that SCN
happen to still be present when you need them — but "may well work" is not a rollback
plan, and the difference only becomes visible at the moment you are relying on it.
Treating it as a safety net is worse than an empty rollback section, because an empty
section gets questioned and this one gets approved. Verify what actually exists rather
than trusting the statement in the script:

```sql
SELECT name, guarantee_flashback_database, scn, time, storage_size
FROM   v$restore_point;
SELECT flashback_on FROM v$database;
SELECT estimated_flashback_size, retention_target, flashback_size FROM v$flashback_database_log;
```

`GUARANTEE_FLASHBACK_DATABASE = YES` is the column that decides whether the row in front
of you is a rollback plan or a bookmark.

Two gates sit in front of even the guaranteed form, and both bite in practice:

- **Edition.** Flashback Database is Enterprise Edition only, so on SE2 or XE a guaranteed
  restore point buys this migration nothing at all. See
  `references/oracle-version-licensing-matrix.md` §2.
- **Privilege and configuration.** The database must be in `ARCHIVELOG` with a Fast
  Recovery Area, and creating a restore point requires an administrative privilege that a
  migration account normally does not hold. A rollback plan that depends on a statement
  the deploying user cannot execute is not a plan — confirm who will run it, and when.

### Resuming interrupted backfill

Track progress via the maximum processed PK/ROWID:
```sql
SELECT MAX(id) FROM target_table WHERE new_col IS NOT NULL;
```
Resume from this value + 1.
# Extended Migration Anti-Examples for Oracle

Supplementary to the inline anti-examples in §7 of the SKILL.md.
Load when reviewing migration files that exhibit suspicious patterns.

---

## AE-7: CREATE INDEX without ONLINE on production table

```sql
-- WRONG: Share lock blocks all DML for entire index build
CREATE INDEX idx_orders_date ON orders (created_at);
```

**Why this is dangerous:**
Non-online `CREATE INDEX` holds a Share (S) lock that blocks INSERT/UPDATE/DELETE
for the entire index build duration. On a 50M-row table, this could be minutes.

**Right approach (Enterprise Edition):**
```sql
ALTER SESSION SET DDL_LOCK_TIMEOUT = 5;
CREATE INDEX idx_orders_date ON orders (created_at) ONLINE;
```

**Right approach (Standard Edition — no ONLINE):**
Schedule during maintenance window with DDL_LOCK_TIMEOUT.

---

## AE-8: ALTER TABLE MOVE without ONLINE (12.2+)

```sql
-- WRONG: exclusive lock for entire table reorganization
ALTER TABLE orders MOVE TABLESPACE new_ts;
```

**Why this is dangerous:**
MOVE rewrites the entire table with an exclusive lock. On large tables, this
blocks all DML for the duration. Indexes become UNUSABLE after MOVE.

**Right approach (12.2+ Enterprise Edition):**
```sql
ALTER SESSION SET DDL_LOCK_TIMEOUT = 5;
ALTER TABLE orders MOVE ONLINE;
-- Indexes are maintained automatically with ONLINE MOVE
```

**Pre-12.2 or Standard Edition:**
Use DBMS_REDEFINITION or CTAS+swap pattern.

---

## AE-9: Uncommitted DML before DDL

```sql
-- WRONG: DDL issues implicit COMMIT — your pending UPDATE is committed!
UPDATE orders SET status = 'pending' WHERE id = 12345;
-- Developer thinks this UPDATE hasn't been committed yet...
ALTER TABLE orders ADD (priority NUMBER);
-- Both the UPDATE and ADD COLUMN are now committed and cannot be rolled back
```

**Why this is catastrophic:**
Oracle DDL issues implicit COMMIT before executing. Any uncommitted DML in the
session is silently committed. This is a fundamental Oracle behavior that
developers from PostgreSQL/MySQL backgrounds frequently miss.

**Right approach:**
```sql
-- Always COMMIT or ROLLBACK pending work before DDL
COMMIT;  -- or ROLLBACK if the DML was a mistake
ALTER SESSION SET DDL_LOCK_TIMEOUT = 3;
ALTER TABLE orders ADD (priority NUMBER);
```

---

## AE-10: MODIFY column NOT NULL without data check

```sql
-- WRONG: fails with ORA-02296 if any NULL values exist
ALTER TABLE orders MODIFY (tracking_id NOT NULL);
```

**Why this fails:**
Oracle scans the table to verify no NULLs exist. If any NULLs are found,
the entire ALTER fails. On a large table, the scan itself takes time with
an exclusive lock held.

**Right approach:**
```sql
-- Step 1: check for NULLs
SELECT COUNT(*) FROM orders WHERE tracking_id IS NULL;

-- Step 2: backfill if needed (batched)
-- ... PK-range batched UPDATE ...

-- Step 3: add NOT NULL with NOVALIDATE (brief lock)
ALTER TABLE orders MODIFY (tracking_id CONSTRAINT nn_tracking NOT NULL ENABLE NOVALIDATE);

-- Step 4: validate (non-blocking)
ALTER TABLE orders MODIFY CONSTRAINT nn_tracking VALIDATE;
```

---

## AE-11: EXCHANGE PARTITION without UPDATE INDEXES

```sql
-- WRONG: global indexes become UNUSABLE
ALTER TABLE logs EXCHANGE PARTITION p_2024_q1 WITH TABLE staging;
```

**What happens:**
After exchange, all global indexes on the partitioned table become UNUSABLE.
Any query using a global index fails with ORA-01502.

**Right approach:**
```sql
ALTER TABLE logs EXCHANGE PARTITION p_2024_q1 WITH TABLE staging
  INCLUDING INDEXES WITHOUT VALIDATION UPDATE INDEXES;
```

---

## AE-12: Assuming a `NOLOGGING` hint controls redo

```sql
-- WRONG on two counts
INSERT /*+ APPEND NOLOGGING */ INTO target_table
SELECT * FROM source_table;
COMMIT;
```

**Why this is wrong:**

1. **`NOLOGGING` is not a hint.** It is a segment attribute set with
   `ALTER TABLE … NOLOGGING`. Oracle silently discards unrecognised text inside a hint
   comment — there is no error, no warning, and no effect. Whoever wrote this believes
   they turned redo off; they did not. Redo behaviour here is decided entirely by the
   *table's* attribute and the database/tablespace `FORCE LOGGING` setting.
2. **The intent, had it worked, is itself dangerous.** A genuinely NOLOGGING direct-path
   load is not recoverable from archive logs, and on a Data Guard primary the standby
   receives blocks it cannot use.

**Right approach — state the intent explicitly and verify it:**
```sql
-- Is NOLOGGING even possible here? FORCE LOGGING overrides it everywhere.
SELECT force_logging FROM v$database;
SELECT tablespace_name, force_logging FROM dba_tablespaces
WHERE  tablespace_name = (SELECT tablespace_name FROM user_tables
                          WHERE table_name = 'TARGET_TABLE');
SELECT logging FROM user_tables WHERE table_name = 'TARGET_TABLE';

-- Default: keep it recoverable. APPEND still gives the direct-path speed-up.
ALTER TABLE target_table LOGGING;
INSERT /*+ APPEND */ INTO target_table SELECT * FROM source_table;
COMMIT;
```

If NOLOGGING is a deliberate, signed-off trade for load speed, set it on the segment
(not in a comment), confirm no physical standby is attached, and take a backup of the
affected tablespace **immediately** after the load:
```sql
ALTER TABLE target_table NOLOGGING;
INSERT /*+ APPEND */ INTO target_table SELECT * FROM source_table;
COMMIT;
ALTER TABLE target_table LOGGING;
-- then: RMAN> BACKUP TABLESPACE <ts>;
```

**Generalise the lesson:** Oracle never errors on a malformed or invented hint. Neither
`/*+ NOLOGGING */` nor `/*+ APEND */` nor `/*+ PARALEL(8) */` will tell you anything is
wrong — the statement just runs without the behaviour you expected. Verify a hint took
effect from the execution plan, never from the absence of an error.

---

## AE-13: Missing DBMS_STATS after bulk migration

```sql
-- WRONG: no stats refresh after 10M-row backfill
-- Optimizer uses stale statistics → bad execution plans
UPDATE target_table SET new_col = ... WHERE ...;
COMMIT;
-- No DBMS_STATS call
```

**Why this matters:**
After large DML operations, table statistics (row count, histograms, high/low
values) become inaccurate. The optimizer may choose sequential scans or nested
loops when hash joins would be better.

**Right approach:**
```sql
-- Gather statistics immediately after bulk changes
BEGIN
  DBMS_STATS.GATHER_TABLE_STATS(
    ownname  => 'SCHEMA',
    tabname  => 'TARGET_TABLE',
    estimate_percent => DBMS_STATS.AUTO_SAMPLE_SIZE,
    cascade  => TRUE  -- also gathers index stats
  );
END;
/
```

---

## AE-14: `RENAME COLUMN` on a live table

```sql
-- WRONG on a system with running application code
ALTER TABLE orders RENAME COLUMN usr_id TO user_id;
```

**Why this is dangerous:**
The database side is trivial — `RENAME COLUMN` has existed since 9i Release 2 and is
metadata-only with a brief lock. The damage is on the application side: the rename
commits instantly and irreversibly, and every deployed statement referencing `usr_id`
starts failing with `ORA-00904` at that moment. There is no dual-name grace period and no
transaction to roll back.

Note this is the *opposite* of the usual failure mode. Most migration mistakes are
"harmless-looking DDL that locks the table for an hour"; this one is "harmless-looking
DDL that completes in 5ms and takes production down".

**Right approach — expand/contract:**
```sql
-- 1. Add the new name alongside the old
ALTER SESSION SET DDL_LOCK_TIMEOUT = 3;
ALTER TABLE orders ADD (user_id NUMBER);

-- 2. Deploy app writing BOTH columns; backfill in batches; then cut reads over
-- 3. Once no code references the old name:
ALTER TABLE orders SET UNUSED COLUMN usr_id;
```

For a read-mostly table a view can shorten this: rename the table, then create a view
under the original name exposing both spellings, and drop the alias once callers migrate.

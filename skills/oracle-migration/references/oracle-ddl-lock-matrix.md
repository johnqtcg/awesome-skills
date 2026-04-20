# Oracle DDL Lock Behavior Matrix

This reference maps each DDL operation to its lock behavior in Oracle Database.
Use this to determine whether a migration can run online or needs mitigation.

## Oracle Lock Types for DDL

| Lock Type | Mode | Blocks DML? | Blocks Queries? | Typical DDL |
|-----------|------|:-----------:|:---------------:|-------------|
| **Exclusive (X)** | 6 | Yes | No (consistent read) | Most ALTER TABLE, DROP, TRUNCATE |
| **Share (S)** | 4 | Write-blocks | No | CREATE INDEX (non-online) |
| **Row Exclusive (RX)** | 3 | No | No | DML operations |
| **Online DDL** | Varies | Brief X at start/end | No | Operations with ONLINE keyword |

**Key Oracle difference**: Oracle uses consistent read (MVCC), so SELECT statements are
never blocked by DDL. But DML (INSERT/UPDATE/DELETE) IS blocked when DDL holds an exclusive lock.

---

## Column Operations

| Operation | Lock | Blocks DML? | Rewrites Table? | Online? | Notes |
|-----------|------|:-----------:|:---------------:|:-------:|-------|
| ADD column (nullable, no default) | Exclusive | Brief | No | — | Metadata-only; lock is very brief |
| ADD column (with DEFAULT, 12c+) | Exclusive | Brief | No | — | 12c+ stores default in metadata; no rewrite |
| ADD column (with DEFAULT, <12c) | Exclusive | Yes | **Yes** | No | Full table rewrite |
| DROP COLUMN | Exclusive | Yes | **Yes** | No | Physical removal; expensive on wide tables |
| SET UNUSED COLUMN | Exclusive | Brief | No | — | Metadata-only; preferred over DROP |
| DROP UNUSED COLUMNS | Exclusive | Yes | **Yes** | No | Physical removal of unused columns |
| MODIFY column (widen) | Exclusive | Brief | No | — | e.g., VARCHAR2(50) → VARCHAR2(100) |
| MODIFY column (narrow/change type) | Exclusive | Yes | **Yes** | No | Requires DBMS_REDEFINITION for large tables |
| RENAME COLUMN (12c+) | Exclusive | Brief | No | — | Metadata-only |
| ALTER COLUMN DEFAULT | Exclusive | Brief | No | — | Metadata-only |
| MODIFY column NOT NULL (with data) | Exclusive | Brief–Long | Validates | No | Scans all rows to verify; longer on large tables |

### Critical version gates:

- **12c+**: ADD COLUMN with DEFAULT is metadata-only (no rewrite)
- **12c+**: RENAME COLUMN supported natively
- **12.2+**: ALTER TABLE MOVE ONLINE (non-blocking table reorganization)
- **<12c**: ADD COLUMN with DEFAULT always rewrites the table

## Index Operations

| Operation | Lock | Blocks DML? | Online Option? | Notes |
|-----------|------|:-----------:|:--------------:|-------|
| CREATE INDEX | Share | **Yes** (writes) | `CREATE INDEX ... ONLINE` (EE) | Online allows concurrent DML |
| CREATE INDEX ONLINE | Brief Exclusive | Brief only | Yes (EE) | Brief lock at start and end; DML allowed during build |
| DROP INDEX | Exclusive | Brief | `DROP INDEX ... ONLINE` (21c+) | Very fast |
| ALTER INDEX REBUILD | Exclusive | **Yes** | `ALTER INDEX ... REBUILD ONLINE` (EE) | Online rebuild allows DML |
| ALTER INDEX UNUSABLE | Exclusive | Brief | — | Metadata-only; makes index ignored by optimizer |
| ALTER INDEX VISIBLE/INVISIBLE | Exclusive | Brief | — | Metadata-only; 12c+ |

### ONLINE index caveats:

- Requires Enterprise Edition (or specific cloud service tier)
- Creates a "journal table" to capture DML during build → extra UNDO/TEMP usage
- May take longer than non-online build (2-3×)
- If interrupted, leaves index in UNUSABLE state → must rebuild

## Constraint Operations

| Operation | Lock | Blocks DML? | Validates? | Notes |
|-----------|------|:-----------:|:----------:|-------|
| ADD CONSTRAINT (FK/CHECK) | Exclusive | **Yes** | **Yes** | Full validation scan + lock |
| ADD CONSTRAINT ... ENABLE NOVALIDATE | Exclusive | Brief | **No** | Enforces for new DML only; skips existing rows |
| MODIFY CONSTRAINT ... VALIDATE | Row Exclusive | No | **Yes** | Non-blocking validation of existing data |
| ADD CONSTRAINT ... DISABLE NOVALIDATE | None | No | No | Metadata-only; constraint not enforced |
| DROP CONSTRAINT | Exclusive | Brief | No | Metadata-only |
| ADD CONSTRAINT (UNIQUE) | Share | Write-blocks | Yes | Builds unique index internally |

### ENABLE NOVALIDATE + VALIDATE two-step:

```sql
-- Step 1: brief exclusive lock, no validation scan
ALTER TABLE orders ADD CONSTRAINT fk_user
  FOREIGN KEY (user_id) REFERENCES users(id) ENABLE NOVALIDATE;

-- Step 2: non-blocking validation (Row Exclusive lock only)
ALTER TABLE orders MODIFY CONSTRAINT fk_user VALIDATE;
```

## Partition Operations

| Operation | Lock | Global Index Impact | Notes |
|-----------|------|:------------------:|-------|
| ADD PARTITION | Brief Exclusive | None | Fast metadata operation |
| DROP PARTITION | Brief Exclusive | **UNUSABLE** (without UPDATE INDEXES) | Always use `UPDATE INDEXES` |
| TRUNCATE PARTITION | Brief Exclusive | **UNUSABLE** (without UPDATE INDEXES) | Always use `UPDATE INDEXES` |
| SPLIT PARTITION | Exclusive | **UNUSABLE** (without UPDATE INDEXES) | Can be slow on large partitions |
| MERGE PARTITIONS | Exclusive | **UNUSABLE** (without UPDATE INDEXES) | Merges two into one |
| EXCHANGE PARTITION | Brief Exclusive | **UNUSABLE** (without UPDATE INDEXES) | Swaps segment; very fast |
| MOVE PARTITION | Exclusive | **UNUSABLE** (without UPDATE INDEXES) | `MOVE PARTITION ... ONLINE` (12.2+ EE) |

### UPDATE INDEXES clause:

```sql
-- Always include UPDATE INDEXES to prevent global index invalidation
ALTER TABLE logs DROP PARTITION logs_2023_q1 UPDATE INDEXES;
ALTER TABLE logs SPLIT PARTITION p_current AT (DATE '2024-07-01')
  INTO (PARTITION p_2024_h1, PARTITION p_current) UPDATE INDEXES;
```

Without `UPDATE INDEXES`, global indexes become UNUSABLE → queries fail with ORA-01502.

## Table-Level Operations

| Operation | Lock | Blocks DML? | Online? | Notes |
|-----------|------|:-----------:|:-------:|-------|
| TRUNCATE TABLE | Exclusive | Yes | No | Instant data removal; DDL auto-commits |
| ALTER TABLE MOVE | Exclusive | Yes | `MOVE ONLINE` (12.2+ EE) | Reorganizes table; rebuilds indexes needed |
| ALTER TABLE SHRINK SPACE | Row Exclusive | No | Yes | Online; compacts table in-place |
| DBMS_REDEFINITION | Brief Exclusive | Brief | **Yes** | Online table redefinition (EE); brief lock at start/finish |

## Decision Flowchart

```
Is this an index operation?
  ├─ YES → Use ONLINE keyword (requires EE)
  │        If SE: schedule during low-traffic with DDL_LOCK_TIMEOUT
  └─ NO
      │
      Is this a constraint addition (FK/CHECK)?
        ├─ YES → Use ENABLE NOVALIDATE + VALIDATE two-step
        └─ NO
            │
            Does this operation rewrite the table?
              ├─ YES (MODIFY column type, DROP COLUMN, MOVE)
              │   │
              │   Is the table small (<1M rows)?
              │     ├─ YES → Direct DDL with DDL_LOCK_TIMEOUT during off-peak
              │     └─ NO → DBMS_REDEFINITION (EE) or CTAS+swap
              └─ NO → Proceed with DDL_LOCK_TIMEOUT
                      (exclusive lock is brief for metadata-only ops)
```

## Monitoring Locks During Migration

```sql
-- Check blocking sessions
SELECT s.sid, s.serial#, s.username, s.program,
       l.type, l.lmode, l.request, l.block
FROM v$lock l JOIN v$session s ON l.sid = s.sid
WHERE l.block = 1 OR l.request > 0;

-- Check DDL lock waiters
SELECT * FROM dba_ddl_locks WHERE name = '<TABLE_NAME>';

-- Active sessions on target table
SELECT s.sid, s.serial#, s.sql_id, s.event
FROM v$session s JOIN v$locked_object lo ON s.sid = lo.session_id
JOIN dba_objects o ON lo.object_id = o.object_id
WHERE o.object_name = '<TABLE_NAME>';
```
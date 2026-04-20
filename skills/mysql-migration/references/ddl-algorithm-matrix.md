# MySQL DDL Algorithm & Lock Compatibility Matrix

This reference maps each ALTER TABLE operation to its supported algorithm and lock level,
broken down by MySQL version. Use this to determine the safest DDL strategy for a given operation.

## How to Read This Matrix

- **INSTANT**: metadata-only change, effectively zero downtime
- **INPLACE**: in-place operation; concurrent DML is permitted when LOCK=NONE is accepted
- **COPY**: full table rebuild; writes are blocked for the duration
- **✓**: supported  **✗**: not supported  **partial**: supported with restrictions (see notes)

---

## 1. Column Operations

| Operation | 5.7 INSTANT | 5.7 INPLACE | 8.0 INSTANT | 8.0 INPLACE | Lock (best case) | Notes |
|-----------|:-----------:|:-----------:|:-----------:|:-----------:|:-----------------:|-------|
| ADD COLUMN (last position) | ✗ | ✓ | ✓ (8.0.12+) | ✓ | NONE | 8.0 INSTANT only adds at end by default |
| ADD COLUMN (specific position) | ✗ | ✓ | ✓ (8.0.29+) | ✓ | NONE | 8.0.29+ supports INSTANT at any position |
| DROP COLUMN | ✗ | ✗ (COPY) | ✓ (8.0.29+) | ✗ (COPY) | NONE (INSTANT) / EXCLUSIVE (COPY) | Pre-8.0.29: always COPY |
| RENAME COLUMN | ✗ | ✓ | ✓ | ✓ | NONE | Metadata-only in both versions |
| SET DEFAULT / DROP DEFAULT | ✗ | ✓ | ✓ | ✓ | NONE | Metadata-only; does not touch row data |
| CHANGE column type (same size) | ✗ | ✗ (COPY) | ✗ | ✗ (COPY) | EXCLUSIVE | Type change always requires COPY (with few exceptions) |
| CHANGE column type (diff size) | ✗ | ✗ (COPY) | ✗ | ✗ (COPY) | EXCLUSIVE | Always COPY; consider gh-ost for large tables |
| Extend VARCHAR (≤255 bytes both) | ✗ | ✓ | ✓ (8.0.12+) | ✓ | NONE | Only if both old and new length ≤ 255 bytes |
| Extend VARCHAR (crosses 256) | ✗ | ✗ (COPY) | ✗ | ✗ (COPY) | EXCLUSIVE | Crossing the 255/256 byte boundary changes length encoding |
| MODIFY COLUMN NULL→NOT NULL | ✗ | ✓ | ✗ | ✓ | NONE | INPLACE but requires full table scan for validation |
| MODIFY COLUMN NOT NULL→NULL | ✗ | ✓ | ✗ | ✓ | NONE | In-place metadata change |

## 2. Index Operations

| Operation | 5.7 INSTANT | 5.7 INPLACE | 8.0 INSTANT | 8.0 INPLACE | Lock (best case) | Notes |
|-----------|:-----------:|:-----------:|:-----------:|:-----------:|:-----------------:|-------|
| ADD INDEX | ✗ | ✓ | ✗ | ✓ | NONE | Reads table data; concurrent DML allowed |
| ADD FULLTEXT INDEX | ✗ | ✓ | ✗ | ✓ | SHARED (first) / NONE (subsequent) | First fulltext index on table requires SHARED lock |
| DROP INDEX | ✗ | ✓ | ✗ | ✓ | NONE | Metadata-only |
| RENAME INDEX | ✗ | ✓ | ✓ | ✓ | NONE | Metadata-only |
| ADD PRIMARY KEY | ✗ | ✓ | ✗ | ✓ | SHARED | Rebuilds clustered index; concurrent reads OK, writes blocked |
| DROP PRIMARY KEY | ✗ | ✗ (COPY) | ✗ | ✗ (COPY) | EXCLUSIVE | Always requires full table rebuild |
| DROP + ADD PRIMARY KEY | ✗ | ✓ | ✗ | ✓ | SHARED | Combined in single ALTER is INPLACE |

## 3. Table-Level Operations

| Operation | 5.7 INSTANT | 5.7 INPLACE | 8.0 INSTANT | 8.0 INPLACE | Lock (best case) | Notes |
|-----------|:-----------:|:-----------:|:-----------:|:-----------:|:-----------------:|-------|
| CONVERT TO CHARACTER SET | ✗ | ✗ (COPY) | ✗ | partial | EXCLUSIVE (COPY) / NONE (INPLACE) | 8.0 INPLACE only if column types don't change encoding size |
| ROW_FORMAT change | ✗ | ✓ | ✗ | ✓ | NONE | Rebuilds table in-place |
| ADD PARTITION | ✗ | ✓ | ✗ | ✓ | NONE | Only for RANGE/LIST partitions |
| DROP PARTITION | ✗ | ✓ | ✗ | ✓ | NONE | Fast (drops data files), but data loss if not expected |
| REORGANIZE PARTITION | ✗ | ✓ | ✗ | ✓ | SHARED | Copies data between partitions |
| OPTIMIZE TABLE | ✗ | ✓ | ✗ | ✓ | NONE | Equivalent to ALTER TABLE ... ENGINE=InnoDB |
| ADD FOREIGN KEY | ✗ | ✓ | ✗ | ✓ | NONE | Performs validation scan; SET foreign_key_checks=0 skips scan but is dangerous |
| DROP FOREIGN KEY | ✗ | ✓ | ✗ | ✓ | NONE | Metadata-only |

## 4. Decision Flowchart

```
Is the operation INSTANT-eligible?
  ├─ YES → Use ALGORITHM=INSTANT
  │        (verify MySQL version supports INSTANT for this operation)
  └─ NO
      │
      Is the operation INPLACE-eligible with LOCK=NONE?
        ├─ YES → Use ALGORITHM=INPLACE, LOCK=NONE
        │        Set lock_wait_timeout = 3 before execution
        └─ NO (requires COPY or SHARED/EXCLUSIVE lock)
            │
            Is the table small (<1M rows)?
              ├─ YES → Use ALGORITHM=COPY during low-traffic window
              │        Set lock_wait_timeout = 3
              └─ NO (large table, COPY required)
                  │
                  Use gh-ost or pt-online-schema-change
                  (See references/large-table-migration.md)
```

## 5. Common Gotchas

### VARCHAR extension across the 255-byte boundary

The internal storage format for VARCHAR changes at the 256-byte boundary:
- ≤255 bytes: 1-byte length prefix
- ≥256 bytes: 2-byte length prefix

Extending from VARCHAR(200) to VARCHAR(300) in a latin1 column crosses this boundary → COPY.
But extending VARCHAR(200) to VARCHAR(250) in latin1 stays within → INPLACE/INSTANT.

**Watch out for utf8mb4**: VARCHAR(63) in utf8mb4 = 63×4 = 252 bytes (under 255).
VARCHAR(64) in utf8mb4 = 64×4 = 256 bytes (crosses!). This is non-obvious and catches people.

### MODIFY vs CHANGE

- `MODIFY COLUMN col_name new_definition`: changes type/nullability/default, keeps name
- `CHANGE COLUMN old_name new_name new_definition`: renames + changes definition

Rename-only via `CHANGE` or `RENAME COLUMN` (8.0+) is INSTANT/INPLACE.
But `CHANGE` that also changes the type triggers COPY.

### Multi-column ALTER batching

MySQL processes multiple operations in a single ALTER TABLE as one operation, using the
most restrictive algorithm among them. Example:

```sql
-- This entire ALTER uses COPY because MODIFY requires COPY:
ALTER TABLE t
  ADD COLUMN a INT DEFAULT NULL,        -- would be INSTANT alone
  MODIFY COLUMN b BIGINT NOT NULL;      -- requires COPY
-- ALGORITHM=INPLACE will be rejected; server chooses COPY
```

**Recommendation**: split operations with different algorithm requirements into separate
ALTER statements to avoid forcing the faster operations into the slower path.

### 8.0 INSTANT limitations

MySQL 8.0 INSTANT DDL has restrictions not obvious from the documentation:
- Only one INSTANT ALTER per table between table rebuilds (8.0.12–8.0.28)
- 8.0.29+ lifts this restriction for most operations
- INSTANT cannot change ROW_FORMAT or COMPRESSION
- INSTANT adds metadata overhead; many accumulated INSTANT changes may degrade performance → periodic OPTIMIZE TABLE recommended
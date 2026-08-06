# MySQL DDL Algorithm & Lock Compatibility Matrix

Maps each `ALTER TABLE` operation to the algorithms and lock levels the **server will actually
accept**, broken down by MySQL version.

> **Provenance.** Every row is transcribed from the official *InnoDB Online DDL Operations*
> tables, verified 2026-08-06:
> - 5.7 — <https://dev.mysql.com/doc/refman/5.7/en/innodb-online-ddl-operations.html>
> - 8.0 — <https://dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl-operations.html>
> - 8.4 — <https://dev.mysql.com/doc/refman/8.4/en/innodb-online-ddl-operations.html>
>   (the 8.4 matrix is byte-identical to 8.0; they are merged into one column below)
>
> Do not edit a cell without re-checking the manual. `scripts/tests/test_ddl_matrix_drift.py`
> pins these values and will fail if a row is changed.

## How to Read This Matrix

**Best algorithm** — the fastest algorithm the server accepts. Specifying a *faster* one than
listed makes the statement fail with `ERROR 0A000: ALGORITHM=... is not supported`. Specifying a
*slower* one is always accepted but may be catastrophically expensive.

**LOCK=NONE?** — derived from the manual's *Permits Concurrent DML* column, **but only for INPLACE
and COPY**:

| Algorithm | Manual says | You may write | Meaning |
|---|---|---|---|
| **INSTANT** | (any) | **omit `LOCK`, or `LOCK=DEFAULT`** | *"Only `LOCK = DEFAULT` is permitted for operations that use `ALGORITHM=INSTANT`. The other LOCK clause parameters are not applicable."* Writing `LOCK=NONE` alongside INSTANT is an error |
| INPLACE | Permits Concurrent DML = Yes | `LOCK=NONE` | reads **and** writes continue |
| INPLACE | Permits Concurrent DML = No | `LOCK=SHARED` (best case) | reads continue, **writes block** |
| COPY | In Place = No | `LOCK=EXCLUSIVE` | reads and writes both block |

> **INSTANT is not lock-free.** The ALTER TABLE reference is explicit: *"INSTANT: Operations only
> modify metadata in the data dictionary. **An exclusive metadata lock on the table may be taken
> briefly during the execution phase of the operation.** Table data is unaffected, making operations
> instantaneous. Concurrent DML is permitted."*
>
> The *What Is New in MySQL 8.0* page says "No metadata locks are taken on the table" — that
> summary is looser than the reference and must not be read as licence to skip
> `SET SESSION lock_wait_timeout`. A long-running transaction can still make an INSTANT DDL queue,
> and everything behind it queues too. **Set the guard before INSTANT as well.**

**Rebuilds?** — whether the table is physically rewritten. `INPLACE + LOCK=NONE + rebuild` is
still online, but it costs full table I/O, ~2× disk, and produces replication lag proportional to
table size. *Online is not the same as free.*

> **The `ALGORITHM=INSTANT` clause does not exist before MySQL 8.0.12.**
> MySQL 5.7 has no INSTANT algorithm at all, and 8.0.0–8.0.11 reject the clause for **every**
> operation — not merely for `ADD COLUMN`. The manual's *What Is New in MySQL 8.0* states: *"As of
> MySQL 8.0.12, `ALGORITHM=INSTANT` is supported for the following ALTER TABLE operations"* — adding
> a column; adding or dropping a **virtual** column; adding or dropping a column **default value**;
> modifying an `ENUM`/`SET` definition; changing the **index type**; **renaming a table**. Anything
> else, or any earlier release, fails immediately: *"If `ALGORITHM=INSTANT` is specified but not
> supported, the operation fails immediately with an error."*
>
> There is therefore no 5.7 INSTANT column below, and every "8.0 INSTANT" cell means **8.0.12+**.

---

## 1. Column Operations

| Operation | 5.7 best | 8.0 / 8.4 best | LOCK=NONE? | Rebuilds? | Notes |
|-----------|----------|----------------|:----------:|:---------:|-------|
| ADD COLUMN (last position) | INPLACE | **INSTANT** (8.0.12+) | Yes¹ | INPLACE yes / INSTANT no | ¹ **Not** when the new column is `AUTO_INCREMENT` — on both versions concurrent DML is refused and `ALGORITHM=INPLACE, LOCK=SHARED` is the minimum |
| ADD COLUMN (`FIRST` / `AFTER`) | INPLACE | **INSTANT** (8.0.29+) | Yes¹ | INPLACE yes / INSTANT no | Before 8.0.29 INSTANT could only append at the end; use INPLACE there |
| DROP COLUMN | **INPLACE** | **INSTANT** (8.0.29+), INPLACE before | Yes | INPLACE yes / INSTANT no | Manual's own 5.7 example: `ALTER TABLE t DROP COLUMN c, ALGORITHM=INPLACE, LOCK=NONE;` — **COPY is not required on any supported version** |
| RENAME COLUMN | INPLACE (via `CHANGE`) | **INSTANT** (8.0.28+), INPLACE before | Yes² | No | `RENAME COLUMN` syntax is 8.0+; on 5.7 use `CHANGE old new same_type`. ² Only when data type and `[NOT] NULL` are unchanged. A column referenced by another table's FK is **INPLACE-only** — INSTANT/COPY fail |
| Reorder columns (`MODIFY … FIRST/AFTER`) | INPLACE | INPLACE | Yes | Yes | Never INSTANT |
| SET DEFAULT / DROP DEFAULT | INPLACE | **INSTANT** | Yes | No | Metadata only |
| CHANGE column data type | **COPY** | **COPY** | **No** | Yes | `Changing the column data type is only supported with ALGORITHM=COPY` — no exceptions. Large table → gh-ost |
| Extend VARCHAR, length bytes unchanged | INPLACE | **INPLACE — never INSTANT** | Yes | No | Official 8.0 matrix: `Instant = No`. In place only 0→≤255 bytes, or ≥256→larger. See §5 |
| Extend VARCHAR across the 255/256 byte line | **COPY** | **COPY** | **No** | Yes | Length prefix grows 1→2 bytes. See §5 |
| **Shrink** VARCHAR | **COPY** | **COPY** | **No** | Yes | `Decreasing VARCHAR size … requires a table copy` |
| MODIFY NULL → NOT NULL | INPLACE³ | INPLACE³ | Yes | **Yes** | ³ Requires `STRICT_ALL_TABLES` or `STRICT_TRANS_TABLES` sql_mode; fails if any row is NULL; rejected on FK columns where it could break referential integrity |
| MODIFY NOT NULL → NULL | INPLACE | INPLACE | Yes | **Yes** | Rebuilds the table — this is *not* a metadata-only change |
| Modify ENUM / SET definition | INPLACE | **INSTANT** | Yes | No | Only when appending members without changing the storage size |
| Change AUTO_INCREMENT value | INPLACE | INPLACE | Yes | No | Never INSTANT |
| ADD VIRTUAL generated column | INPLACE | **INSTANT** | Yes | No | |
| DROP VIRTUAL generated column | INPLACE | **INSTANT** | Yes | No | |
| ADD STORED generated column | **COPY** | **COPY** | **No** | Yes | |
| DROP STORED generated column | INPLACE | INPLACE | Yes | Yes | |

## 2. Index Operations

| Operation | 5.7 best | 8.0 / 8.4 best | LOCK=NONE? | Rebuilds? | Notes |
|-----------|----------|----------------|:----------:|:---------:|-------|
| ADD INDEX (secondary) | INPLACE | INPLACE | Yes | No | Never INSTANT |
| DROP INDEX | INPLACE | INPLACE | Yes | No | Metadata only |
| RENAME INDEX | INPLACE | INPLACE | Yes | No | **Not INSTANT** (official `Instant = No`) |
| Change index type (`USING BTREE/HASH`) | INPLACE | **INSTANT** | Yes | No | The one index op that is INSTANT on 8.0 |
| ADD FULLTEXT INDEX | INPLACE | INPLACE | **No — SHARED** | Only if no user `FTS_DOC_ID` column | Writes block for the whole build, **every time** — not only the first index |
| ADD SPATIAL INDEX | INPLACE | INPLACE | **No — SHARED** | No | Same as FULLTEXT |
| ADD PRIMARY KEY | INPLACE⁴ | INPLACE⁴ | **Yes** | Yes | ⁴ Manual's own example is `ADD PRIMARY KEY (c), ALGORITHM=INPLACE, LOCK=NONE`. INPLACE is refused when columns must be converted to `NOT NULL` as part of the operation. Expensive — the clustered index is rewritten |
| DROP PRIMARY KEY (alone) | **COPY** | **COPY** | **No** | Yes | |
| DROP PK + ADD PK (one statement) | INPLACE | INPLACE | **Yes** | Yes | Combining them is what makes it online |

## 3. Table-Level Operations

| Operation | 5.7 best | 8.0 / 8.4 best | LOCK=NONE? | Rebuilds? | Notes |
|-----------|----------|----------------|:----------:|:---------:|-------|
| `DEFAULT CHARACTER SET = …` (declare) | INPLACE | INPLACE | Yes | Only if new encoding differs | Changes the table default for *future* columns |
| `CONVERT TO CHARACTER SET …` (rewrite) | **COPY** | INPLACE | **No — SHARED** | Yes | 5.7: `In Place = No`. 8.0: in place but **writes block**. See `migration-anti-examples.md` AE-7 |
| Change ROW_FORMAT | INPLACE | INPLACE | Yes | Yes | INSTANT can never change ROW_FORMAT |
| Change KEY_BLOCK_SIZE | INPLACE | INPLACE | Yes | Yes | |
| `OPTIMIZE TABLE` / null rebuild / `FORCE` | INPLACE | INPLACE | Yes | Yes | `OPTIMIZE TABLE` is its own statement — it takes no `ALGORITHM=` clause |
| RENAME TABLE | INPLACE | **INSTANT** | Yes | No | |
| Set persistent statistics | INPLACE | INPLACE | Yes | No | |
| Enable/disable file-per-table encryption | **COPY** | **COPY** | **No** | Yes | |
| ADD FOREIGN KEY | INPLACE **only if `foreign_key_checks=0`**, else **COPY** | same | Yes | No | The manual is explicit: *"The INPLACE algorithm is supported when `foreign_key_checks` is disabled. Otherwise, only the COPY algorithm is supported."* See §5 |
| DROP FOREIGN KEY | INPLACE | INPLACE | Yes | No | Works with `foreign_key_checks` on **or** off |

## 4. Partitioning Operations — read this before writing any `ALGORITHM=`

Partition DDL does **not** follow the table rules, and 5.7 and 8.0 differ sharply. On 5.7 most
partition clauses accept **only** `ALGORITHM=DEFAULT, LOCK=DEFAULT` — writing `ALGORITHM=INPLACE`
makes the statement fail.

| Clause | 5.7 accepted clauses | 8.0 / 8.4 accepted clauses | 8.0 LOCK=NONE? |
|--------|----------------------|----------------------------|:--------------:|
| `ADD PARTITION` | `ALGORITHM=DEFAULT, LOCK=DEFAULT` **only** | `INPLACE` with `LOCK={DEFAULT,NONE,SHARED,EXCLUSIVE}` for RANGE/LIST; `LOCK={DEFAULT,SHARED,EXCLUSIVE}` for HASH/KEY | RANGE/LIST only |
| `DROP PARTITION` | `ALGORITHM=DEFAULT, LOCK=DEFAULT` **only** | `INPLACE` with `LOCK={DEFAULT,NONE,SHARED,EXCLUSIVE}` | Yes |
| `REORGANIZE PARTITION` | `ALGORITHM=DEFAULT, LOCK=DEFAULT` **only** | `INPLACE` with `LOCK={DEFAULT,SHARED,EXCLUSIVE}` | **No** |
| `COALESCE PARTITION` | `ALGORITHM=DEFAULT, LOCK=DEFAULT` **only** | `INPLACE` with `LOCK={DEFAULT,SHARED,EXCLUSIVE}` | **No** |
| `REBUILD PARTITION` | `ALGORITHM=DEFAULT, LOCK=DEFAULT` **only** | `INPLACE` with `LOCK={DEFAULT,SHARED,EXCLUSIVE}` | **No** |
| `TRUNCATE PARTITION` | in place, DML permitted | in place, DML permitted | Yes |
| `EXCHANGE / ANALYZE / CHECK / REPAIR PARTITION` | in place, DML permitted | in place, DML permitted | Yes |
| `DISCARD / IMPORT PARTITION` | `ALGORITHM=DEFAULT, LOCK=DEFAULT` **only** | `ALGORITHM=DEFAULT, LOCK=DEFAULT` **only** | No |
| `OPTIMIZE PARTITION` | clauses ignored; rebuilds whole table | same | No |
| `PARTITION BY` (add partitioning) | `COPY` with `LOCK={DEFAULT,SHARED,EXCLUSIVE}` | same | No |
| `REMOVE PARTITIONING` | `COPY` with `LOCK={DEFAULT,SHARED,EXCLUSIVE}` | same | No |

> **`DROP PARTITION` changes meaning with the algorithm.** With `ALGORITHM=INPLACE` (8.0) it
> deletes the partition's rows and removes the partition. With `ALGORITHM=COPY` or
> `old_alter_table=ON` it *rebuilds the table and tries to move* the rows into another partition
> with a compatible `VALUES` definition, deleting only what cannot be moved. Two different data
> outcomes from the same clause — always state the algorithm for `DROP PARTITION`.

## 5. Decision Flowchart

```
0. What is the exact server version?  SELECT VERSION();
   5.7            → no INSTANT algorithm.            Skip to step 2.
   8.0.0–8.0.11   → no ALGORITHM=INSTANT clause.     Skip to step 2.
   8.0.12–8.0.27  → INSTANT for the six operations listed below.
   8.0.28         → + INSTANT RENAME COLUMN.
   8.0.29+ / 8.4  → + INSTANT DROP COLUMN, + INSTANT ADD COLUMN at any position.

1. Does §1–§4 list INSTANT for this operation AND this version?
     YES → ALGORITHM=INSTANT      omit LOCK, or write LOCK=DEFAULT. NONE,
                                  SHARED and EXCLUSIVE are rejected — LOCK=NONE
                                  is an error, not a stronger guarantee.
                                  Still set lock_wait_timeout first: INSTANT
                                  may take a brief exclusive metadata lock.
     NO  → step 2

2. Does §1–§4 list INPLACE for this operation AND this version?
     NO  → COPY. Table <1M rows and a maintenance window exists?
             YES → ALGORITHM=COPY, LOCK=EXCLUSIVE in the window
             NO  → gh-ost / pt-osc (references/large-table-migration.md)
     YES → step 3

3. Is "LOCK=NONE?" = Yes for this row?
     NO  → ALGORITHM=INPLACE, LOCK=SHARED. Writes block for the whole operation.
           Treat the duration as downtime for writers and budget a window,
           or move to gh-ost / pt-osc.
     YES → step 4

4. Is "Rebuilds?" = Yes for this row?
     NO  → ALGORITHM=INPLACE, LOCK=NONE. Cheap; metadata only.
     YES → ALGORITHM=INPLACE, LOCK=NONE is accepted, but the whole table is
           rewritten: ~2x disk, full I/O, and the replica applies the same DDL
           as one event (5.7 replicas apply DDL single-threaded → lag ≈ full
           rebuild duration). Above ~10M rows prefer gh-ost / pt-osc even
           though native DDL is technically "online".
```

## 6. Common Gotchas

### VARCHAR extension across the 255-byte boundary

The number of **length prefix bytes** must not change:
- 0–255 bytes → 1-byte prefix
- ≥256 bytes → 2-byte prefix

In-place extension is supported *within* a band (0→≤255, or ≥256→larger), never across it.

```sql
-- INVALID — transcript of the rejection, from the manual:
ALTER TABLE t ALGORITHM=INPLACE, CHANGE COLUMN c1 c1 VARCHAR(256);
ERROR 0A000: ALGORITHM=INPLACE is not supported. Reason: Cannot change
column type INPLACE. Try ALGORITHM=COPY.
```

**The boundary is bytes, not characters** — multiply by the charset's max bytes per character:

| Charset | max bytes/char | Largest in-band VARCHAR(n) | First n that crosses |
|---------|:--------------:|:--------------------------:|:--------------------:|
| latin1 | 1 | 255 | 256 |
| utf8 / utf8mb3 | 3 | 85 (255 bytes) | 86 (258 bytes) |
| utf8mb4 | 4 | 63 (252 bytes) | 64 (256 bytes) |

`VARCHAR(63)` → `VARCHAR(64)` in utf8mb4 looks like a one-character widening and is a full table
copy. This is the single most commonly missed rule in this document.

Extension is also **never INSTANT** on any version. `ALGORITHM=INSTANT` on a VARCHAR widening
fails even when the widening stays inside a band.

### Adding a foreign key — INPLACE is gated on a session variable

`ADD CONSTRAINT … FOREIGN KEY` is `COPY` unless `foreign_key_checks` is **off**:

```sql
SET SESSION lock_wait_timeout = 3;

-- COPY: full rebuild, writes blocked. On a large table this is an outage.
ALTER TABLE order_items ADD CONSTRAINT fk_o FOREIGN KEY (order_id) REFERENCES orders(id),
  ALGORITHM=COPY;

-- INPLACE: only reachable with checks disabled — and the FK is then UNVALIDATED.
SET SESSION foreign_key_checks = 0;
ALTER TABLE order_items ADD CONSTRAINT fk_o FOREIGN KEY (order_id) REFERENCES orders(id),
  ALGORITHM=INPLACE, LOCK=NONE;
SET SESSION foreign_key_checks = 1;
```

There is no "online **and** validated" path. Choose deliberately:
1. Verify orphans yourself (`LEFT JOIN … WHERE parent.id IS NULL`), then take the INPLACE path and
   accept an unvalidated constraint; **or**
2. Accept COPY in a maintenance window; **or**
3. Use gh-ost/pt-osc — note gh-ost cannot migrate a table with **inbound** FKs.

`DROP FOREIGN KEY` has no such restriction; it is INPLACE either way.

### MODIFY vs CHANGE vs RENAME COLUMN

- `MODIFY COLUMN c new_definition` — changes type/nullability/default, keeps the name
- `CHANGE COLUMN old new new_definition` — renames **and** restates the definition
- `RENAME COLUMN old TO new` — 8.0+ only; rename with no definition restated

Rename-only is online. `CHANGE` that also alters the type falls back to COPY, so restate the
existing type exactly when you only mean to rename.

### Multi-operation ALTER takes the most restrictive algorithm

```sql
-- WRONG: the whole statement runs as COPY because MODIFY requires COPY.
ALTER TABLE t
  ADD COLUMN a INT DEFAULT NULL,        -- INSTANT on its own
  MODIFY COLUMN b BIGINT NOT NULL;      -- COPY
-- ALGORITHM=INPLACE here is rejected outright.
```

INSTANT is stricter still: an `ALGORITHM=INSTANT` statement is rejected if **any** action in it is
not INSTANT-eligible. Split operations by algorithm class into separate statements.

### 8.0 INSTANT limitations

- **Row-version budget — 64.** Each INSTANT statement that adds and/or drops columns creates one
  new row version. Track it with
  `SELECT NAME, TOTAL_ROW_VERSIONS FROM INFORMATION_SCHEMA.INNODB_TABLES WHERE NAME LIKE 'db/tbl';`
  At 64 the next INSTANT is rejected:
  `ERROR 4092 (HY000): Maximum row versions reached for table … Please use COPY/INPLACE.`
  Only a table rebuild (`OPTIMIZE TABLE`, or any rebuilding `ALTER`) resets the counter to 0.
  A service that ships one INSTANT column per release will hit this in ~64 releases and the
  failure lands in production, not in review.
- Multiple columns **may** be added in a single INSTANT statement — that costs one row version, not
  one per column. Batch them.
- INSTANT `ADD COLUMN` is unavailable on `ROW_FORMAT=COMPRESSED` tables, tables carrying a
  `FULLTEXT` index, data-dictionary-tablespace tables, and temporary tables (COPY only).
- A column backing a **functional index** cannot be dropped with INSTANT.
- The internal column count must stay ≤1022 after an INSTANT add (`ERROR 4158`).
- Before 8.0.29 the server did **not** check max row size on an INSTANT add, so the row could
  become oversized and fail later during DML instead of at DDL time.
- INSTANT can never change `ROW_FORMAT` or compression.

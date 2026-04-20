# Extended Migration Anti-Examples

Supplementary to the inline anti-examples in §6 of the SKILL.md.
Load this reference when reviewing migration files that exhibit suspicious patterns.

---

## AE-7: utf8mb4 conversion without size impact analysis

```sql
-- WRONG: assumes CONVERT is online and safe
ALTER TABLE messages CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

**Why this is dangerous:**
- utf8 uses up to 3 bytes/char; utf8mb4 uses up to 4 bytes/char
- VARCHAR(255) in utf8 = 765 bytes (under 768 prefix limit)
- VARCHAR(255) in utf8mb4 = 1020 bytes → may exceed index prefix limits → ALTER fails
- The CONVERT operation requires COPY algorithm on MySQL 5.7; may be INPLACE on 8.0+ only if no index prefix issue arises

**Right approach:**
1. Audit all VARCHAR columns and their indexes for prefix-limit conflicts
2. Shorten VARCHAR lengths or adjust index prefix lengths if needed
3. Convert on a replica first to verify success
4. Use gh-ost for large tables

---

## AE-8: Combining fast and slow ALTER operations

```sql
-- WRONG: the MODIFY forces COPY, dragging the ADD COLUMN along
ALTER TABLE orders
  ADD COLUMN tracking_id VARCHAR(50) DEFAULT NULL,
  MODIFY COLUMN amount DECIMAL(12,4) NOT NULL;
```

**Why this is dangerous:**
MySQL processes all operations in a single ALTER using the most restrictive algorithm.
The ADD COLUMN alone would be INSTANT; combining it with a type-changing MODIFY forces
the entire ALTER to use COPY.

**Right approach:**
```sql
-- Statement 1: INSTANT
ALTER TABLE orders ADD COLUMN tracking_id VARCHAR(50) DEFAULT NULL, ALGORITHM=INSTANT;

-- Statement 2: requires COPY, run separately (or via gh-ost if table is large)
ALTER TABLE orders MODIFY COLUMN amount DECIMAL(12,4) NOT NULL;
```

---

## AE-9: Creating index on large table without ALGORITHM specification

```sql
-- WRONG: no algorithm specified; might work, but gives no protection
CREATE INDEX idx_user_email ON users(email);
```

**Why this is problematic:**
CREATE INDEX is implicitly ALGORITHM=INPLACE, LOCK=NONE on InnoDB (MySQL 5.6+), so it
is generally safe. But explicitly stating the algorithm provides two benefits:
1. Self-documenting: the reader knows this is an online operation
2. Fail-fast: if MySQL cannot perform it online (e.g., FULLTEXT first-time), specifying
   LOCK=NONE causes an error instead of silently acquiring SHARED lock

**Right approach:**
```sql
SET SESSION lock_wait_timeout = 3;
ALTER TABLE users ADD INDEX idx_user_email (email), ALGORITHM=INPLACE, LOCK=NONE;
```

---

## AE-10: Backfill using LIMIT/OFFSET on large table

```sql
-- WRONG: OFFSET rescans previous rows → O(n²) for full backfill
SET @offset = 0;
REPEAT
  UPDATE target SET col = 'value'
  WHERE col IS NULL
  LIMIT 1000 OFFSET @offset;
  SET @offset = @offset + 1000;
UNTIL ROW_COUNT() = 0 END REPEAT;
```

**Why this is disastrous at scale:**
At offset 1,000,000, MySQL must scan and discard 1M rows before finding the next 1000.
A 10M-row backfill degrades from minutes to hours.

**Right approach:** batch by primary key range (see §5.3 in SKILL.md).

---

## AE-11: Dropping a column that is part of a composite index

```sql
-- WRONG: drops column but doesn't address the index
ALTER TABLE orders DROP COLUMN legacy_status;
-- The composite index idx_status_date (legacy_status, created_at) now has a dangling definition
```

**What actually happens:**
MySQL automatically removes the dropped column from composite indexes. If it was the only
column, the index is dropped entirely. But the **remaining index** may no longer serve its
intended query pattern.

**Right approach:**
1. Identify all indexes containing the column: `SHOW INDEX FROM orders WHERE Column_name = 'legacy_status';`
2. Plan index adjustments: if `idx_status_date (legacy_status, created_at)` should become `idx_date (created_at)`, create the new index first
3. Drop the column (which removes it from the old index automatically)
4. Verify final index state matches intent

---

## AE-12: Running ALTER TABLE during peak hours without MDL check

```sql
-- WRONG: just runs the DDL, hoping for the best
ALTER TABLE hot_table ADD INDEX idx_new (some_column), ALGORITHM=INPLACE, LOCK=NONE;
```

**Why this still fails at peak:**
Even with LOCK=NONE, the initial MDL acquisition can be blocked by any long-running
SELECT or transaction on the table. During peak hours, the probability of hitting a
long-running query is much higher. The DDL waits for MDL, and all subsequent queries
queue behind it → cascading timeout.

**Right approach:**
```sql
-- Step 1: check for MDL blockers
SELECT * FROM information_schema.innodb_trx
WHERE trx_started < NOW() - INTERVAL 10 SECOND;

-- Step 2: set aggressive timeout
SET SESSION lock_wait_timeout = 3;

-- Step 3: run DDL
ALTER TABLE hot_table ADD INDEX idx_new (some_column), ALGORITHM=INPLACE, LOCK=NONE;

-- Step 4: if timeout, wait and retry (don't force-kill user transactions unless authorized)
```

---

## AE-13: Foreign key added without validation awareness

```sql
-- WRONG: adds FK which triggers full-table validation scan
ALTER TABLE order_items
  ADD CONSTRAINT fk_order
  FOREIGN KEY (order_id) REFERENCES orders(id);
```

**What happens behind the scenes:**
MySQL validates that every `order_items.order_id` value exists in `orders.id`. On a
10M-row `order_items` table, this validation scan takes significant time and holds locks.

**Right approach (if validation is needed):**
```sql
-- First verify data integrity manually
SELECT COUNT(*) FROM order_items oi
LEFT JOIN orders o ON oi.order_id = o.id
WHERE o.id IS NULL;
-- If count > 0: fix orphaned rows first

-- Then add FK with ALGORITHM=INPLACE
SET SESSION lock_wait_timeout = 3;
ALTER TABLE order_items
  ADD CONSTRAINT fk_order FOREIGN KEY (order_id) REFERENCES orders(id),
  ALGORITHM=INPLACE, LOCK=NONE;
```

**Alternative (if validation can be deferred):**
```sql
-- Skip validation (dangerous — only if you've verified integrity above)
SET SESSION foreign_key_checks = 0;
ALTER TABLE order_items
  ADD CONSTRAINT fk_order FOREIGN KEY (order_id) REFERENCES orders(id);
SET SESSION foreign_key_checks = 1;
-- WARNING: this leaves an unvalidated FK; corrupted data may already exist
```
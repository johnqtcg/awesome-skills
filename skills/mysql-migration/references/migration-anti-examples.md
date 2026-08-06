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
- `CONVERT TO CHARACTER SET` is **COPY on 5.7** (`In Place = No`). On 8.0/8.4 it is INPLACE, but
  the manual lists `Permits Concurrent DML = No` — so the best case is still
  `ALGORITHM=INPLACE, LOCK=SHARED`, and **writes block for the whole rebuild**. There is no
  `LOCK=NONE` form of this statement on any version; above ~10M rows use gh-ost

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
SET SESSION lock_wait_timeout = 3;

-- Statement 1: INSTANT on 8.0.12+ (use ALGORITHM=INPLACE, LOCK=NONE on 5.7)
ALTER TABLE orders ADD COLUMN tracking_id VARCHAR(50) DEFAULT NULL, ALGORITHM=INSTANT;

-- Statement 2: a data-type change is COPY-only. State it, so the reader sees
-- that this one blocks writes and needs a window — or gh-ost on a large table.
ALTER TABLE orders MODIFY COLUMN amount DECIMAL(12,4) NOT NULL, ALGORITHM=COPY;
```

Naming `ALGORITHM=COPY` explicitly does not make the operation cheaper; it makes the cost visible
at review time instead of at 3am.

---

## AE-9: Creating index on large table without ALGORITHM specification

```sql
-- WRONG: no algorithm specified; might work, but gives no protection
CREATE INDEX idx_user_email ON users(email);
```

**Why this is problematic:**
For an ordinary secondary index, `CREATE INDEX` is implicitly `ALGORITHM=INPLACE, LOCK=NONE` on
InnoDB, so it is generally safe. But stating it explicitly gives two things:
1. Self-documenting: the reader knows this is an online operation
2. Fail-fast: for index types that do **not** permit concurrent DML, `LOCK=NONE` raises an error
   instead of silently taking a `SHARED` lock and blocking writes for the whole build

The second point is not hypothetical. **`FULLTEXT` and `SPATIAL` indexes never permit concurrent
DML** — not merely the first one on the table. Every `ADD FULLTEXT INDEX` blocks writes for the
duration of the build, on both 5.7 and 8.0. Writing `LOCK=NONE` turns that into an immediate error
you can plan around, rather than a write outage you discover from a latency graph.

**Right approach:**
```sql
SET SESSION lock_wait_timeout = 3;
ALTER TABLE users ADD INDEX idx_user_email (email), ALGORITHM=INPLACE, LOCK=NONE;
```

---

## AE-10: Backfill using LIMIT/OFFSET on large table

```sql
-- WRONG, twice over:
SET @offset = 0;
REPEAT
  UPDATE target SET col = 'value'
  WHERE col IS NULL
  LIMIT 1000 OFFSET @offset;
  SET @offset = @offset + 1000;
UNTIL ROW_COUNT() = 0 END REPEAT;
```

**Defect 1 — it does not parse.** `REPEAT … END REPEAT` is a compound statement valid only inside a
stored program. Pasted into a migration file or a `mysql` session it is `ERROR 1064`. A backfill
written this way has never been run; treat its presence as evidence the migration was never
rehearsed. (`UPDATE … LIMIT n OFFSET m` is also not valid MySQL syntax — `UPDATE` accepts
`LIMIT row_count` only.)

**Defect 2 — the access pattern is O(n²).** At offset 1,000,000 MySQL scans and discards 1M rows
before reaching the next 1000. A 10M-row backfill degrades from minutes to hours.

**Right approach:** batch by primary-key range, driven from a stored procedure or (preferably) an
external process. See `large-table-migration.md` §4.2–4.3 for both runnable forms.

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

## AE-13: Foreign key added assuming `ALGORITHM=INPLACE` is available

```sql
-- WRONG: no algorithm stated. With foreign_key_checks on (the default) the
-- server silently uses COPY: full rebuild, writes blocked.
ALTER TABLE order_items
  ADD CONSTRAINT fk_order
  FOREIGN KEY (order_id) REFERENCES orders(id);
```

```sql
-- ALSO WRONG: this fails outright. INPLACE is unavailable while
-- foreign_key_checks is enabled.
ALTER TABLE order_items
  ADD CONSTRAINT fk_order FOREIGN KEY (order_id) REFERENCES orders(id),
  ALGORITHM=INPLACE, LOCK=NONE;
```

**The rule** (MySQL manual, *Online DDL Operations* → Foreign Key Operations):
*"The INPLACE algorithm is supported when `foreign_key_checks` is disabled. Otherwise, only the
COPY algorithm is supported."*

So there is **no online-and-validated path** for `ADD FOREIGN KEY`. Either the server validates
every child row (and rebuilds the table under COPY), or you disable validation to get INPLACE and
own the integrity check yourself. Pick deliberately:

**Option 1 — verify by hand, then take the INPLACE path:**
```sql
-- 1. Prove there are no orphans. This must return 0.
SELECT COUNT(*) FROM order_items oi
LEFT JOIN orders o ON oi.order_id = o.id
WHERE oi.order_id IS NOT NULL AND o.id IS NULL;

-- 2. Only if the count is 0, add the constraint in place.
SET SESSION lock_wait_timeout = 3;
SET SESSION foreign_key_checks = 0;
ALTER TABLE order_items
  ADD CONSTRAINT fk_order FOREIGN KEY (order_id) REFERENCES orders(id),
  ALGORITHM=INPLACE, LOCK=NONE;
SET SESSION foreign_key_checks = 1;
```
The constraint is now **unvalidated by the server**: it enforces future writes, but MySQL never
checked the existing rows. Step 1 is the only thing standing between you and a constraint that
claims an invariant the data does not satisfy. It is also racy — rows written between step 1 and
step 2 are unchecked, so run it when writes are quiet or re-check after.

**Option 2 — accept COPY in a maintenance window:**
```sql
SET SESSION lock_wait_timeout = 3;
ALTER TABLE order_items
  ADD CONSTRAINT fk_order FOREIGN KEY (order_id) REFERENCES orders(id),
  ALGORITHM=COPY;
```
Stating `ALGORITHM=COPY` explicitly is the point: it documents that this blocks writes for the
duration and forces a size estimate before anyone runs it.

**Option 3 — large table:** gh-ost cannot migrate a table with **inbound** FKs, but adding an
*outbound* FK from this table is fine. If `order_items` is itself referenced by other tables, use
pt-osc with `--alter-foreign-keys-method`.

`DROP FOREIGN KEY` has none of these restrictions — it is INPLACE with `foreign_key_checks` either
on or off.
---

## AE-14: `ALGORITHM=INPLACE` on a partition clause the server will not accept

```sql
-- WRONG on MySQL 5.7 — the statement is rejected outright
ALTER TABLE events ADD PARTITION (PARTITION p2026_09 VALUES LESS THAN (20260901)),
  ALGORITHM=INPLACE, LOCK=NONE;
```

**Why:** partition DDL does not follow the table rules. On 5.7, `ADD PARTITION`,
`DROP PARTITION`, `REORGANIZE PARTITION`, `COALESCE PARTITION`, and `REBUILD PARTITION` accept
**only** `ALGORITHM=DEFAULT, LOCK=DEFAULT`. Naming any other algorithm fails.

This is where the "always specify the algorithm explicitly" rule bites: applied blindly to
partition maintenance on 5.7 it generates statements that cannot run. Partition clauses are the
documented exception — see `ddl-algorithm-matrix.md` §4.

**Right approach:**
```sql
-- The session guard applies on every version; only the ALGORITHM clause is
-- version-dependent.
SET SESSION lock_wait_timeout = 3;

-- MySQL 5.7 — omit the algorithm clauses; DEFAULT is the only accepted value
ALTER TABLE events ADD PARTITION (PARTITION p2026_09 VALUES LESS THAN (20260901));

-- MySQL 8.0+ — INPLACE is available; LOCK=NONE only for RANGE/LIST
ALTER TABLE events ADD PARTITION (PARTITION p2026_09 VALUES LESS THAN (20260901)),
  ALGORITHM=INPLACE, LOCK=NONE;
```

On 8.0, `REORGANIZE`, `COALESCE`, and `REBUILD PARTITION` still refuse `LOCK=NONE` — the best
available is `LOCK=SHARED`, and writes block.

**Also version-dependent in meaning:** `DROP PARTITION` with `ALGORITHM=INPLACE` deletes the
partition's rows, while `ALGORITHM=COPY` rebuilds the table and *moves* rows into another
compatible partition. Same clause, different data outcome — always state the algorithm here.

---

## AE-15: `ALGORITHM=INSTANT` on a VARCHAR widening

```sql
-- WRONG: VARCHAR extension is never INSTANT, on any version
ALTER TABLE users MODIFY COLUMN bio VARCHAR(500), ALGORITHM=INSTANT;
```

**Why:** the official 8.0/8.4 matrix lists *Extending VARCHAR column size* as `Instant = No`,
`In Place = Yes`. The best case is `ALGORITHM=INPLACE, LOCK=NONE`, and only when the length-prefix
byte count is unchanged.

**Two traps in one statement:**
1. `INSTANT` is rejected. The fix is `INPLACE`.
2. Whether even `INPLACE` works depends on **bytes, not characters**. In utf8mb4,
   `VARCHAR(63)` → `VARCHAR(64)` crosses 255 bytes (252 → 256) and requires `COPY`.

**Right approach:**
```sql
-- Compute the byte widths first:
--   utf8mb4: n * 4    utf8/utf8mb3: n * 3    latin1: n * 1
-- Both old and new must be <= 255 bytes, or both >= 256 bytes.
SET SESSION lock_wait_timeout = 3;
ALTER TABLE users MODIFY COLUMN bio VARCHAR(500), ALGORITHM=INPLACE, LOCK=NONE;
-- If the boundary is crossed, this errors with:
--   ERROR 0A000: ALGORITHM=INPLACE is not supported. Reason: Cannot change
--   column type INPLACE. Try ALGORITHM=COPY.
-- which is the signal to route to gh-ost rather than to switch to COPY on a large table.
```

Shrinking a VARCHAR is always `COPY`, never in place.

---

## AE-16: gh-ost pointed at a replica *and* given `--allow-on-master`

```bash
# WRONG: --allow-on-master is the opt-in for connecting to the MASTER.
# Pairing it with a replica host means the invocation was copied from a
# template nobody read.
gh-ost --host=replica1.db.internal --allow-on-master \
  --database=app --table=events --alter="ADD COLUMN c INT" --execute
```

**Why:** gh-ost's default and recommended mode is *connect to a replica, migrate on the master* —
it crawls up to the master by itself and needs no approval flag. `--allow-on-master` exists to make
you acknowledge that `--host` **is** the master and the migration will read binlogs from it.

**Right approach:**
```bash
# Mode (a) — replica host, no approval flag
gh-ost --host=replica1.db.internal --database=app --table=events \
  --alter="ADD COLUMN c INT" --execute

# Mode (b) — master host, approval flag required
gh-ost --host=master.db.internal --allow-on-master \
  --database=app --table=events --alter="ADD COLUMN c INT" --execute
```

**The same command hides a second problem** whenever it carries
`--initially-drop-old-table` / `--initially-drop-ghost-table` as if they were defaults. Upstream
disables them deliberately: the `_old` table from a previous run is often the only surviving copy
of the pre-migration data. See `large-table-migration.md` §1.3.

---

## AE-17: Shipping one `ALGORITHM=INSTANT` column per release forever

```sql
-- Every release up to the server's ceiling (64, or 255 from 9.1.0): fine.
SET SESSION lock_wait_timeout = 3;
ALTER TABLE accounts ADD COLUMN feature_flag_1 TINYINT DEFAULT 0, ALGORITHM=INSTANT;
```

**Why this eventually pages someone:** every INSTANT statement that adds or drops columns creates a
new row version, and InnoDB permits a bounded number of them between table rebuilds:

| Server | Max `TOTAL_ROW_VERSIONS` |
|---|:---:|
| 8.0.29 – 8.4, and 9.0 | **64** |
| **9.1.0 and later** | **255** |

(*"The maximum `TOTAL_ROW_VERSIONS` value is 255. This maximum value was 64 prior to MySQL 9.1.0."*)
Do not quote a single number without the version — a limit that moved once can move again. One past
the ceiling, the statement fails:

```
ERROR 4092 (HY000): Maximum row versions reached for table app/accounts.
No more columns can be added or dropped instantly. Please use COPY/INPLACE.
```

The failure lands on whichever migration first exceeds **that server's** ceiling — the 65th on a
release before 9.1.0, the 256th from 9.1.0 on — typically in production, on the largest table, with
no relationship to the change being made.

**Right approach:**
```sql
-- 1. Check the budget before relying on INSTANT.
SELECT NAME, TOTAL_ROW_VERSIONS
FROM INFORMATION_SCHEMA.INNODB_TABLES
WHERE NAME = 'app/accounts';

-- 2. Batch columns into one statement — one row version, not three.
SET SESSION lock_wait_timeout = 3;
ALTER TABLE accounts
  ADD COLUMN a TINYINT DEFAULT 0,
  ADD COLUMN b TINYINT DEFAULT 0,
  ADD COLUMN c TINYINT DEFAULT 0,
  ALGORITHM=INSTANT;

-- 3. Reset the counter with a rebuild during a planned window (or gh-ost on a large table).
OPTIMIZE TABLE accounts;
```

Only a table rebuild resets `TOTAL_ROW_VERSIONS` to 0. Treat the counter as a consumable resource
with a monitoring threshold, not as an unbounded feature — and read the ceiling off the server you
are targeting, not off this page.

**This is also the reason 9.x is `assumed` rather than `verified` in §1.** The 9.x online-DDL matrix
is byte-identical to 8.4, yet this limit changed in 9.1 without touching that matrix. "The table is
the same" is a narrower claim than "the rules are the same".

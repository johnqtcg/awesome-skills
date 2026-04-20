# Extended Migration Anti-Examples for PostgreSQL

Supplementary to the inline anti-examples in §7 of the SKILL.md.
Load when reviewing migration files that exhibit suspicious patterns.

---

## AE-7: VACUUM FULL instead of pg_repack

```sql
-- WRONG: VACUUM FULL acquires AccessExclusiveLock for the entire rewrite
VACUUM FULL orders;
```

**Why this is dangerous:**
VACUUM FULL rewrites the entire table while holding AccessExclusiveLock — blocking all
reads and writes for the duration. On a 10GB table this can take minutes.

**Right approach:**
```bash
# pg_repack does the same work with only a brief lock at the swap
pg_repack --no-superuser-check -t orders -d mydb
```

---

## AE-8: REINDEX without CONCURRENTLY

```sql
-- WRONG: REINDEX acquires AccessExclusiveLock
REINDEX INDEX idx_orders_user;
```

**Why this is problematic:**
REINDEX blocks all reads and writes on the underlying table. For large indexes,
this can take significant time.

**Right approach (PG 12+):**
```sql
REINDEX INDEX CONCURRENTLY idx_orders_user;
```

For PG <12: drop and recreate with CREATE INDEX CONCURRENTLY.

---

## AE-9: NOT NULL addition without CHECK constraint shortcut (PG 12+)

```sql
-- WRONG on PG 12+: unnecessary full-table scan
ALTER TABLE orders ALTER COLUMN status SET NOT NULL;
```

**Why this is suboptimal on PG 12+:**
PostgreSQL 12+ can skip the full-table NOT NULL validation scan if a CHECK
constraint already proves the column is non-null. Without the CHECK, it scans
every row while holding AccessExclusiveLock.

**Right approach (PG 12+):**
```sql
-- Step 1: add CHECK with NOT VALID (brief lock)
ALTER TABLE orders ADD CONSTRAINT orders_status_not_null
  CHECK (status IS NOT NULL) NOT VALID;

-- Step 2: validate (non-blocking)
ALTER TABLE orders VALIDATE CONSTRAINT orders_status_not_null;

-- Step 3: SET NOT NULL (skips scan because CHECK proves it — PG 12+)
ALTER TABLE orders ALTER COLUMN status SET NOT NULL;

-- Step 4: drop redundant CHECK
ALTER TABLE orders DROP CONSTRAINT orders_status_not_null;
```

---

## AE-10: LIMIT/OFFSET backfill on large table

```sql
-- WRONG: OFFSET rescans earlier rows → O(n²)
UPDATE target SET col = 'value'
WHERE col IS NULL
LIMIT 1000 OFFSET @offset;
```

**Right approach:** cursor/keyset pagination by primary key (see large-table-migration.md §3).

---

## AE-11: Constraint without idempotency guard

```sql
-- WRONG: fails on re-run if constraint already exists
ALTER TABLE orders ADD CONSTRAINT fk_user
  FOREIGN KEY (user_id) REFERENCES users(id) NOT VALID;
```

**Why this matters:**
If the migration fails after the constraint is added but before the next step,
re-running the migration throws `constraint "fk_user" already exists`. PostgreSQL
does NOT support `ADD CONSTRAINT IF NOT EXISTS`.

**Right approach:**
```sql
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'fk_user'
  ) THEN
    ALTER TABLE orders ADD CONSTRAINT fk_user
      FOREIGN KEY (user_id) REFERENCES users(id) NOT VALID;
  END IF;
END $$;
```

---

## AE-12: CONCURRENTLY inside a transaction block

```sql
-- WRONG: CONCURRENTLY cannot run inside BEGIN...COMMIT
BEGIN;
CREATE INDEX CONCURRENTLY idx_orders_date ON orders (created_at);
COMMIT;
-- Error: CREATE INDEX CONCURRENTLY cannot run inside a transaction block
```

**Right approach:**
```sql
-- Run outside any transaction (autocommit mode)
CREATE INDEX CONCURRENTLY idx_orders_date ON orders (created_at);
```

Migration frameworks (Flyway, Alembic) may wrap statements in transactions by default.
Configure the migration to run this statement outside a transaction:
- Flyway: use `-- flyway:executeInTransaction=false`
- Alembic: set `autocommit=True` on the operation
- golang-migrate: split into separate up/down files

---

## AE-13: Dropping column referenced by views/functions without checking dependencies

```sql
-- WRONG: breaks dependent views silently (they become invalid)
ALTER TABLE users DROP COLUMN legacy_email;
```

**What happens:**
PostgreSQL will raise an error if views/functions depend on the column
(due to dependency tracking), but only for direct dependencies. Dynamically
built queries in functions may break without error at DDL time.

**Right approach:**
```sql
-- Check dependencies first
SELECT dependent_ns.nspname AS schema, dependent_view.relname AS view
FROM pg_depend
JOIN pg_rewrite ON pg_depend.objid = pg_rewrite.oid
JOIN pg_class AS dependent_view ON pg_rewrite.ev_class = dependent_view.oid
JOIN pg_namespace AS dependent_ns ON dependent_view.relnamespace = dependent_ns.oid
JOIN pg_class AS source_table ON pg_depend.refobjid = source_table.oid
JOIN pg_attribute ON pg_depend.refobjsubid = pg_attribute.attnum
  AND pg_attribute.attrelid = source_table.oid
WHERE source_table.relname = 'users'
  AND pg_attribute.attname = 'legacy_email';

-- Fix or drop dependents first, then proceed
```
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
-- WRONG on a production table
REINDEX INDEX idx_orders_user;
```

**Why this is problematic — stated precisely:**
Non-concurrent REINDEX takes a **ShareLock on the parent table** (writes blocked, reads
permitted at the lock level) plus an **AccessExclusiveLock on the index being rebuilt**.
The docs then add the part that actually matters operationally:

> "the query planner tries to take an ACCESS SHARE lock on every index of the table,
> regardless of the query, and so REINDEX blocks virtually any queries except for some
> prepared queries whose plan has been cached and which don't use this very index."
> — `REINDEX`, Notes

So reads are not blocked by the *table* lock, but nearly every real query blocks anyway on
the *index* lock via the planner. Both halves are true; do not restate this as either
"AccessExclusiveLock on the table" (overstates the lock) or "reads are unaffected"
(understates the impact).

**Right approach (PG 12+):**
```sql
REINDEX INDEX CONCURRENTLY idx_orders_user;   -- ShareUpdateExclusive; not in a transaction block
```

On the supported majors (14–18) `REINDEX CONCURRENTLY` is always available.

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

**Right approach** — `conrelid`-scoped (AE-16) *and* definition-checked (AE-19). A guard
that decides on the name alone skips silently when the name is already taken by a
different definition:
```sql
DO $$
DECLARE existing text;
BEGIN
  SELECT pg_get_constraintdef(oid) INTO existing
    FROM pg_constraint
   WHERE conname = 'fk_user' AND conrelid = 'public.orders'::regclass;

  IF existing IS NULL THEN
    ALTER TABLE orders ADD CONSTRAINT fk_user
      FOREIGN KEY (user_id) REFERENCES users(id) NOT VALID;
  ELSIF existing NOT LIKE '%REFERENCES users(id)%' THEN
    RAISE EXCEPTION 'fk_user exists with a different definition: %', existing;
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

---

## AE-14: short `statement_timeout` around a concurrent build

```sql
-- WRONG: statement_timeout aborts ANY statement exceeding it
SET statement_timeout = '30s';
CREATE INDEX CONCURRENTLY idx_events_payload ON events USING gin (payload);
```

**Why this is dangerous:**
`statement_timeout` is documented as "Abort any statement that takes more than the specified
amount of time." A concurrent index build on a large table routinely runs for hours, so a
30s cap guarantees the build is killed — leaving an **INVALID index** that silently does not
serve queries and must be dropped and rebuilt.

**Right approach** — bound the *lock wait*, not the build:
```sql
SET lock_timeout = '3s';
SET statement_timeout = 0;
CREATE INDEX CONCURRENTLY idx_events_payload ON events USING gin (payload);
RESET statement_timeout;
RESET lock_timeout;

-- Always verify afterwards
SELECT indexrelid::regclass FROM pg_index WHERE NOT indisvalid;
```

---

## AE-15: mixing lock classes in one ALTER TABLE

```sql
-- WRONG: escalates to the strictest lock of any subcommand
ALTER TABLE orders
  ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) NOT VALID,
  ADD COLUMN note text;
```

**Why this silently costs you the optimisation:**
`ADD FOREIGN KEY` alone needs only ShareRowExclusive, which leaves reads running. But
per the `ALTER TABLE` reference, "When multiple subcommands are given, the lock acquired
will be the strictest one required by any subcommand" — and `ADD COLUMN` is
AccessExclusive. The combined statement blocks reads. Reviewers who check only "is
NOT VALID present?" will pass this.

**Right approach** — one statement per lock class:
```sql
ALTER TABLE orders ADD COLUMN note text;
ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) NOT VALID;
```

---

## AE-16: unqualified constraint/index existence guard

```sql
-- WRONG: conname is unique per TABLE, not per database
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_user') THEN
    ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) NOT VALID;
  END IF;
END $$;
```

**Why this fails, and why it fails silently:**
Constraint names only have to be unique within a table. A `fk_user` on *any other* table
makes this guard report "already exists", so the `ALTER TABLE` never runs — and the DO block
completes successfully. The migration reports success while having applied nothing. The
failure only surfaces later, when application code depends on the missing constraint.

**Right approach** — scope by `conrelid`:
```sql
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'fk_user' AND conrelid = 'public.orders'::regclass
  ) THEN
    ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) NOT VALID;
  END IF;
END $$;
```

The same defect class applies to index guards: `pg_indexes` needs `schemaname`, and
`pg_class` lookups need a `relnamespace` join.

`CREATE INDEX IF NOT EXISTS` is immune to *this* defect — the server resolves the name
against the right schema, so it cannot be confused by a same-named index elsewhere. It is
**not** safe in general: it still decides on the name alone, so an existing index on
different columns silently survives. See AE-19.

---

## AE-17: treating `int` → `bigint` as a metadata change

```sql
-- WRONG: assumed cheap; actually rewrites the table and every index
ALTER TABLE events ALTER COLUMN id TYPE bigint;
```

**Why this is the most common false assumption in PostgreSQL migration planning:**
The documented no-rewrite exemption requires that "the `USING` clause does not change the
column contents **and** the old type is either binary coercible to the new type or an
unconstrained domain over the new type." `int4` is **not** binary coercible to `int8` — the
on-disk width differs. So this rewrites the entire heap plus all indexes while holding
AccessExclusiveLock, and temporarily needs up to double the disk space.

What *is* exempt: `varchar(N)` → `varchar(M)` widening, and `text` ↔ `varchar` with no
collation change. What is *not*: `int` → `bigint`, `numeric(10,2)` → `numeric(12,4)`, and
anything altering collation (index rebuild mandatory even when the heap is untouched).

**Right approach** — expand-contract:
```sql
-- 1. add the wide column (metadata-only, no volatile default)
ALTER TABLE events ADD COLUMN id_new bigint;
-- 2. backfill in batches (see large-table-migration.md §3)
-- 3. dual-write from the application, verify parity
-- 4. swap: add the PK/unique index CONCURRENTLY on id_new, then cut reads over
-- 5. drop the old column in a later release
```
---

## AE-18: one lock rule stated for both FK and CHECK

`ADD FOREIGN KEY` and `ADD CHECK` are routinely described together as "constraint
additions", which hides the fact that they take **different lock classes**. Measured on
live 14.23 and 18.4 by inspecting `pg_locks` from inside the altering transaction:

| Statement | Lock on the altered table | Lock on the referenced table | Blocks reads? |
|-----------|---------------------------|------------------------------|:---:|
| `ADD FOREIGN KEY ... NOT VALID` | ShareRowExclusive | ShareRowExclusive | No |
| `ADD FOREIGN KEY` (validating) | ShareRowExclusive | ShareRowExclusive + RowShare | No |
| `ADD CHECK ... NOT VALID` | **AccessExclusive** | — | **Yes** |
| `ADD CHECK` (validating) | **AccessExclusive** | — | **Yes** |
| `VALIDATE CONSTRAINT` (FK) | ShareUpdateExclusive | RowShare | No |

`NOT VALID` moves the row scan out of the locked window. It does **not** move the
statement into a cheaper lock class — a CHECK still blocks `SELECT` either way, which is
why the CHECK form must be treated as an outage risk on a hot table and the FK form must
not.

```sql
-- WRONG: AccessExclusive held for the entire validation scan -- blocks reads and writes
ALTER TABLE orders ADD CONSTRAINT chk_amt CHECK (amount >= 0);
-- RIGHT: still AccessExclusive, but held only briefly; the scan moves to the second step
ALTER TABLE orders ADD CONSTRAINT chk_amt CHECK (amount >= 0) NOT VALID;
ALTER TABLE orders VALIDATE CONSTRAINT chk_amt;
```

Two consequences that follow only from the lock class, not from the `NOT VALID` keyword:

- An FK addition needs a write-freeze window on **both** tables. Reviews that mention only
  the altered table understate the blast radius.
- A CHECK addition on a hot table needs the same treatment as any other AccessExclusive
  DDL: a short `lock_timeout` and a retry loop, because it queues behind every open
  transaction and then blocks every query behind itself.

---

## AE-19: an idempotency guard that matches on name only

Scoping a `pg_constraint` lookup by `conrelid` fixes the cross-table collision (AE-16).
It does not fix the harder case: the **same table** already carries a constraint with
that name and a **different definition**. The guard sees the name, skips, and the
migration reports success against a schema that is not the one it describes.

Reproduced on a live server:

```sql
-- Pre-existing state (from an earlier release, a hotfix, or a hand-edit)
ALTER TABLE t ADD CONSTRAINT ck_amt CHECK (amt > 100);

-- WRONG: the guard matches on name, so it skips -- and reports success
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conname = 'ck_amt' AND conrelid = 'public.t'::regclass) THEN
    ALTER TABLE t ADD CONSTRAINT ck_amt CHECK (amt >= 0) NOT VALID;
  END IF;
END $$;
-- Result: CHECK ((amt > 100)) survives. Rows with 0 <= amt <= 100 are still rejected.

-- RIGHT: compare the definition too, and fail loudly on a mismatch
DO $$
DECLARE existing text;
BEGIN
  SELECT pg_get_constraintdef(oid) INTO existing
    FROM pg_constraint
   WHERE conname = 'ck_amt' AND conrelid = 'public.t'::regclass;

  IF existing IS NULL THEN
    ALTER TABLE t ADD CONSTRAINT ck_amt CHECK (amt >= 0) NOT VALID;
  ELSIF existing NOT LIKE '%amt >= 0%' THEN
    RAISE EXCEPTION 'ck_amt exists with a different definition: %', existing;
  END IF;   -- else: already correct, nothing to do
END $$;
```

`RAISE EXCEPTION` is the point. A migration that cannot reach its declared end state
must stop, not continue quietly — schema drift discovered here is cheap, and the same
drift discovered from a production incident is not.

### `CREATE INDEX IF NOT EXISTS` has the same hole

`IF NOT EXISTS` checks only that *something* with that name exists. Verified on a live
server: with `idx_x ON t (amt)` already present,

```sql
CREATE INDEX IF NOT EXISTS idx_x ON t (note);
-- NOTICE: relation "idx_x" already exists, skipping
-- pg_indexes.indexdef is still: CREATE INDEX idx_x ON t USING btree (amt)
```

the migration succeeds and the intended index on `note` is never built. Queries then
plan against an index that does not cover their predicate, which surfaces as a slow
query long after the migration is considered done. Assert on `pg_indexes.indexdef`
after the build, or name indexes so that a definition change forces a name change.

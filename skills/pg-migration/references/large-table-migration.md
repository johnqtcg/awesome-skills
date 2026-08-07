# Large Table Migration Patterns for PostgreSQL

For tables exceeding ~10M rows, DDL operations requiring AccessExclusiveLock
for extended periods (table rewrites, full-table constraint validation) are
impractical in zero-downtime environments. This reference covers alternatives.

---

## Table of Contents

1. [pg_repack — online reorganisation and bloat removal](#1-pg_repack--online-reorganisation-and-bloat-removal)
2. [Create-Swap-Rename Pattern](#2-create-swap-rename-pattern)
3. [Chunked Backfill](#3-chunked-backfill)
4. [Partition-Based Migration](#4-partition-based-migration)
5. [Monitoring During Migration](#5-monitoring-during-migration)
6. [Abort and Recovery](#6-abort-and-recovery)

---

## 1. pg_repack — online reorganisation and bloat removal

Named for what it does. It is **not** a schema-change tool — see "What pg_repack can and cannot do" below.

pg_repack reorganises a table online: it builds a shadow copy, captures concurrent
changes with a trigger, then swaps. The long copy phase runs without blocking.

### It takes AccessExclusiveLock TWICE, not once

Describing pg_repack as "only a brief lock at the swap" understates it. The tool needs
AccessExclusiveLock at **both ends**:

1. **Setup** — to install the log trigger on the target table.
2. **Swap** — to exchange the original and the shadow copy.

Each is short in itself, but each has to *wait* for the lock, and while waiting it
queues ahead of every subsequent query on that table. On a busy table the wait, not the
hold, is what causes the incident.

### The default timeout can cancel and then kill your queries

This is the risk that most often surprises people, because it is a destructive default:

- `--wait-timeout` (default 60s) bounds how long pg_repack waits for each of those two
  locks.
- Once it expires, pg_repack does **not** simply give up. It cancels the conflicting
  queries, and if that is not enough it **terminates the backends holding them**.
- `--no-kill-backend` disables the terminate step — pg_repack gives up instead.

For a production run under a change window, decide this explicitly rather than
inheriting it:

```bash
# Conservative: never terminate somebody else's backend; abandon the repack instead.
pg_repack --no-superuser-check --no-kill-backend --wait-timeout=30 -t orders -d mydb

# Cluster the table by an index while repacking (the online CLUSTER replacement).
pg_repack --no-superuser-check --no-kill-backend -t orders -d mydb --order-by id
```

Check the flags against the pg_repack version you actually have installed
(`pg_repack --version`) — the client binary and the extension version must match, and
the defaults have changed across releases.

### Installation

```sql
CREATE EXTENSION IF NOT EXISTS pg_repack;
```

### What pg_repack can and cannot do

**pg_repack cannot change a schema.** It has no option to alter a column type, add or drop
a column, or copy into a table you defined. Its scope is limited to reorganising an existing
table in place with its existing definition:

| pg_repack can | pg_repack cannot |
|---------------|------------------|
| Remove bloat online (the `VACUUM FULL` replacement) | Change a column type |
| Cluster a table by an index online (the `CLUSTER` replacement) | Add / drop / rename a column |
| Rebuild only the indexes (`-x`) | Copy data into a table you created |
| Move a table or its indexes to another tablespace | Alter constraints |

Its trigger mechanism is internal — it captures changes into its own private log table
inside the `repack` schema during the copy, then replays them at the swap. There is no
supported way to point that mechanism at an arbitrary target table.

**So for `ALTER COLUMN TYPE` on a large table, pg_repack is not the tool.** Use one of:

1. **Expand-contract on the same table** (preferred — no swap, no dependency breakage):
   add a new column, backfill in batches, dual-write, cut reads over, drop the old column
   in a later release. See §3 for the backfill and AE-17 in `migration-anti-examples.md`.
2. **Create-swap-rename** (§2) when the change is too structural for expand-contract.
   Read its limitations first — the rename does **not** re-point dependent objects.
3. **Logical-replication cutover** for the largest tables: replicate into a separately
   built table/instance with the target schema, then switch traffic. Highest complexity,
   lowest lock cost.

**Be precise about what leaves bloat.** A true full-table rewrite (`ALTER COLUMN TYPE`,
volatile-DEFAULT `ADD COLUMN`, `VACUUM FULL`) writes a brand-new compact heap and leaves
none — running pg_repack straight afterwards is wasted I/O. What *does* bloat is the
batched `UPDATE` phase of an expand-contract backfill: every updated row leaves a dead
tuple, and on a large table autovacuum will not keep up. Check before acting:

```sql
SELECT relname, n_dead_tup, last_autovacuum
FROM pg_stat_user_tables WHERE relname = 'orders';
```

Repack when the dead-tuple ratio justifies it, not on a schedule keyed to "we ran DDL".

### pg_repack limitations

- Requires the `pg_repack` extension installed (superuser or rds_superuser)
- Target table must have a PRIMARY KEY or UNIQUE NOT NULL index
- Acquires AccessExclusiveLock **twice** — trigger setup and final swap — each held
  briefly but each preceded by a lock *wait* that blocks everything queued behind it
- Past `--wait-timeout` it cancels, then terminates, the backends in its way unless
  `--no-kill-backend` is given
- Generates significant WAL during the copy phase, and needs free space for a full copy
- The client-side binary version must match the installed extension version

---

## 2. Create-Swap-Rename Pattern

When pg_repack isn't available or the schema change is complex, manually
create a new table with the target schema, migrate data, then swap.

### Read this before using the pattern

**A rename does not re-point anything.** PostgreSQL tracks dependencies by OID, not by name.
After `orders` → `orders_old` and `orders_new` → `orders`:

- Views, functions with hard dependencies, and **foreign keys on child tables** still point
  at the **original relation** — which is now called `orders_old`. They keep working, silently
  reading and constraining the stale table.
- Nothing errors. The application appears healthy while two tables diverge.

This is why "atomic swap" is misleading: the *name* change is transactional, the *dependency*
graph is not migrated at all. **Enumerate dependents before you start** (see AE-13) and plan
to recreate every FK and view explicitly. If the table has inbound FKs or views, prefer
expand-contract (§1) — it has none of this exposure.

### Workflow

```sql
-- Step 0: enumerate what depends on the table. If this returns rows, re-read the note above.
SELECT conrelid::regclass AS child_table, conname
FROM pg_constraint WHERE confrelid = 'public.orders'::regclass;

-- Step 1: Create target table with new schema.
-- Use GENERATED BY DEFAULT (not ALWAYS) so the copy in step 2 can supply explicit ids
-- without needing OVERRIDING SYSTEM VALUE on every insert.
CREATE TABLE orders_new (
  id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  user_id bigint NOT NULL,
  amount numeric(12,4) NOT NULL,  -- changed from numeric(10,2)
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Step 2: Copy data with transformation.
-- If you kept GENERATED ALWAYS, this INSERT FAILS without OVERRIDING SYSTEM VALUE:
--   "cannot insert a non-DEFAULT value into column id"
INSERT INTO orders_new (id, user_id, amount, created_at)
SELECT id, user_id, amount::numeric(12,4), created_at
FROM orders;
-- With GENERATED ALWAYS the required form is:
--   INSERT INTO orders_new (id, ...) OVERRIDING SYSTEM VALUE SELECT id, ... FROM orders;

-- Step 3: Indexes and constraints on the new table (outside any transaction)
CREATE INDEX CONCURRENTLY idx_orders_new_user ON orders_new (user_id);
CREATE INDEX CONCURRENTLY idx_orders_new_date ON orders_new (created_at);
ALTER TABLE orders_new ADD CONSTRAINT fk_orders_new_user
  FOREIGN KEY (user_id) REFERENCES users(id) NOT VALID;
ALTER TABLE orders_new VALIDATE CONSTRAINT fk_orders_new_user;

-- Step 4: Advance the identity sequence BEFORE the swap.
-- Two traps, both measured on live 14.23 and 18.4:
--   * setval(NULL) raises an error, so max(id) needs a coalesce.
--   * the TWO-argument form implies is_called = true, i.e. "this value is used up".
--     On an EMPTY table, setval(seq, coalesce(max(id), 1)) makes the next value 2 and
--     id = 1 is never issued. Use the three-argument form and let is_called follow
--     whether any row actually exists.
SELECT setval(
  pg_get_serial_sequence('orders_new', 'id'),
  coalesce((SELECT max(id) FROM orders_new), 1),
  (SELECT count(*) > 0 FROM orders_new)   -- false when empty: next value is 1, not 2
);

-- Step 5: Swap the names (brief AccessExclusiveLock on both)
BEGIN;
SET LOCAL lock_timeout = '5s';
ALTER TABLE orders     RENAME TO orders_old;
ALTER TABLE orders_new RENAME TO orders;
COMMIT;

-- Step 6: Re-create every dependent object found in step 0 against the NEW table,
-- and drop the stale ones from orders_old. Until this completes, child-table FKs are
-- still enforcing against orders_old.

-- Step 7: Drop the old table only after a verification period
-- DROP TABLE orders_old;
```

### Limitations

- **Writes arriving between step 2 and step 5 are lost.** The copy is a point-in-time
  snapshot. You need either a maintenance window, or your own `AFTER INSERT/UPDATE/DELETE`
  trigger on `orders` writing through to `orders_new` for the whole interval, drained
  immediately before the swap.
- Dependent objects are **not** migrated by the rename — see the note above.
- Identity/serial sequences must be advanced explicitly (step 4).
- Peak disk usage is roughly double the table plus its indexes.

---

## 3. Chunked Backfill

For populating new columns, advance a keyset cursor over the primary key — never LIMIT/OFFSET,
and never fixed numeric-range stepping (see "Choosing the batching key" below).

### Choosing the batching key

Fixed numeric-range stepping (`id > n AND id <= n + batch`) is only correct for a **dense,
positive, single-column integer** key. It misbehaves on:

| Key shape | What breaks |
|-----------|-------------|
| Sparse / gappy ids (after mass deletes) | Most batches touch 0 rows; the loop burns millions of empty iterations |
| UUID / text primary keys | Arithmetic on the key is impossible |
| Composite primary keys | A single `>` comparison cannot express the cursor |
| Negative or zero ids | Starting at `current_id := 0` silently skips every row `<= 0` |

**Use keyset (seek) pagination instead — it is correct for every key shape above**, because
it advances by *observed rows* rather than by assumed arithmetic:

```sql
-- Keyset cursor, SINGLE-COLUMN form: correct for sparse and negative ids.
-- A composite key needs a row-value comparison — see Template C below;
-- a single `>` cannot express a multi-column cursor.
WITH batch AS (
    SELECT id FROM target_table
    WHERE new_col IS NULL AND id > $1
    ORDER BY id
    LIMIT 5000
)
UPDATE target_table t
SET new_col = compute_value(t.old_col)
FROM batch WHERE t.id = batch.id
RETURNING t.id;
-- Pass the largest returned id back as $1. Stop when zero rows return.
```

### The resume point must come from the batch, never from the table

This is the single most dangerous bug in a batched backfill, because it silently *skips rows*
and the loop still terminates cleanly, so nothing looks wrong:

```sql
-- WRONG: a global scan of the whole table for the next cursor value
SELECT max(id) INTO last_id FROM target_table WHERE new_col IS NOT NULL;
```

`new_col IS NOT NULL` is true for **every** row that already carries a value — including rows
populated by an earlier partial run, by an application already dual-writing, or by a
`DEFAULT`. If any such row sits at a high id, the first batch completes and the cursor jumps
straight past every unprocessed row in between. They are never revisited: the loop advances
monotonically and exits when a batch comes back empty.

The cursor must be **the largest key among the rows this batch actually updated**. Take it
from the `UPDATE … RETURNING` set:

```sql
-- excerpt: elided shape only; Template A below is the runnable form
-- RIGHT: cursor derived from the rows this iteration touched
WITH batch AS (...), upd AS (UPDATE ... RETURNING t.id)
SELECT count(*), max(id) INTO rows_done, last_id FROM upd;
```

An **aggregate-only** `SELECT … INTO` (no `GROUP BY`) always returns exactly one row, so
`rows_done` is `0` — never NULL — when the batch is empty. A form that can return zero rows
leaves `rows_done` NULL, `EXIT WHEN rows_done = 0` evaluates to NULL, and the loop never
terminates.

### DO-block form (correct usage and its real constraint)

`COMMIT` inside a `DO` block **is** supported on PostgreSQL 11+ — no `CREATE PROCEDURE`
needed. The actual restriction is: *"Transaction control is only possible in `CALL` or `DO`
invocations from the top level or nested `CALL`/`DO` invocations without any other
intervening command."*

**This means the DO block must be submitted in autocommit mode.** If a migration framework
wraps the file in `BEGIN … COMMIT` — Flyway, golang-migrate, and Alembic all do by default —
the `COMMIT` inside fails with *invalid transaction termination*. Either disable the
framework's transaction for that file, or drive the loop from the application (below).

#### Template A — single-column key (`bigint`, `int`, `timestamptz`)

Correct for dense, sparse, and negative keys alike: it advances by observed rows, not by
arithmetic on the key.

```sql
DO $$
DECLARE
  batch_size int    := 5000;
  last_id    bigint := NULL;   -- NULL, not 0: makes no assumption about the low bound
  rows_done  int;
BEGIN
  LOOP
    WITH batch AS (
        SELECT id FROM target_table
        WHERE new_col IS NULL
          AND (last_id IS NULL OR id > last_id)
        ORDER BY id
        LIMIT batch_size
    ),
    upd AS (
        UPDATE target_table t
        SET new_col = compute_value(t.old_col)
        FROM batch WHERE t.id = batch.id
        RETURNING t.id
    )
    SELECT count(*), max(id) INTO rows_done, last_id FROM upd;

    EXIT WHEN rows_done = 0;           -- terminate on observed work, not a computed bound
    COMMIT;                            -- top-level DO only; see the note above
    PERFORM pg_sleep(0.1);
  END LOOP;
END $$;
```

#### Template B — UUID or text key

Same loop, but **`max()` is not available for `uuid`.** PostgreSQL ships no `max(uuid)`
aggregate — verified absent on 14 through 18 — so Template A's `max(id)` fails with
*function max(uuid) does not exist*. `uuid` does have a full btree ordering, so take the
highest key with an ordered `array_agg` instead:

```sql
-- excerpt: only the lines that differ from Template A
DECLARE
  last_id uuid := NULL;        -- text works with either form; uuid requires this one
...
    SELECT count(*), (array_agg(id ORDER BY id DESC))[1]
      INTO rows_done, last_id
    FROM upd;
```

`array_agg` is still aggregate-only, so the empty-batch guarantee from Template A holds:
`rows_done` is `0`, and `last_id` is NULL but unused because the loop exits.

Two caveats specific to this shape:

- **`uuid` ordering is byte-wise, not chronological.** A v4 UUID key gives a random walk over
  the heap — correct, but with poor locality. A v7 (time-ordered) key does not have this
  problem. Either way the loop is correct; only the I/O pattern differs.
- **`text` ordering is collation-dependent.** `max(text)` does exist, so Template A works
  as-is — but `ORDER BY id` and `id > last_id` resolve under the column's collation, and the
  index serving them must have been built under the *same* one. After a `COLLATE` change or a
  glibc upgrade, `REINDEX` before relying on this loop.

#### Template C — composite key

A single `>` cannot express the cursor. Use a **row-value comparison**, which PostgreSQL
evaluates row-wise — `(a, b) > (x, y)` means "a > x, or (a = x and b > y)", *not*
`a > x AND b > y` — and which can be served by a composite btree index on `(a, b)`.

`max()` has no composite form, so take the highest key with an ordered `array_agg`.

```sql
DO $$
DECLARE
  batch_size  int    := 5000;
  last_tenant bigint := NULL;
  last_id     bigint := NULL;
  rows_done   int;
BEGIN
  LOOP
    WITH batch AS (
        SELECT tenant_id, id FROM target_table
        WHERE new_col IS NULL
          AND (last_tenant IS NULL OR (tenant_id, id) > (last_tenant, last_id))
        ORDER BY tenant_id, id
        LIMIT batch_size
    ),
    upd AS (
        UPDATE target_table t
        SET new_col = compute_value(t.old_col)
        FROM batch b
        WHERE t.tenant_id = b.tenant_id AND t.id = b.id
        RETURNING t.tenant_id, t.id
    )
    SELECT count(*),
           (array_agg(tenant_id ORDER BY tenant_id DESC, id DESC))[1],
           (array_agg(id        ORDER BY tenant_id DESC, id DESC))[1]
      INTO rows_done, last_tenant, last_id
    FROM upd;

    EXIT WHEN rows_done = 0;
    COMMIT;
    PERFORM pg_sleep(0.1);
  END LOOP;
END $$;
```

- The `ORDER BY` must list the columns in the **same order** as the row comparison, or the
  cursor and the scan disagree and rows are skipped.
- Row comparison yields NULL if any element is NULL. Primary-key columns are non-null by
  definition, so this is safe for a PK cursor — but not for a nullable composite.
- The guard is `last_tenant IS NULL`, checking only the leading column: the two cursor
  variables are always set together, so one test covers both.

### Application-level backfill (Go example)

Drive the keyset cursor from the application when the migration framework wraps files in a
transaction (see the DO-block note above). Each iteration is its own transaction.

```go
const batchSize = 5000

// lastID is the cursor. Use sql.NullInt64 so the first batch has no lower bound —
// starting at 0 would skip any rows with id <= 0.
var lastID sql.NullInt64

for {
    // Advance by rows actually seen, never by assumed arithmetic: correct for sparse,
    // negative, and non-contiguous keys alike.
    var batchMax sql.NullInt64
    err := db.QueryRowContext(ctx, `
        WITH batch AS (
            SELECT id FROM target_table
            WHERE new_col IS NULL AND ($1::bigint IS NULL OR id > $1)
            ORDER BY id
            LIMIT $2
        )
        UPDATE target_table t
        SET new_col = compute_value(t.old_col)
        FROM batch WHERE t.id = batch.id
        RETURNING (SELECT max(id) FROM batch)`,
        lastID, batchSize).Scan(&batchMax)

    if errors.Is(err, sql.ErrNoRows) {
        break // no rows matched: backfill complete
    }
    if err != nil {
        return fmt.Errorf("backfill after id=%v: %w", lastID.Int64, err)
    }
    if !batchMax.Valid {
        break
    }
    lastID = batchMax

    // Monitor replication lag
    if lag := checkReplicaLag(ctx, db); lag > maxLagThreshold {
        slog.Warn("replica lag high, pausing", "lag", lag)
        time.Sleep(5 * time.Second)
    }

    time.Sleep(100 * time.Millisecond)
}
```

Termination is driven by "no rows matched", so an empty table exits on the first iteration
and a sparse table never spins on empty ranges.

### Backfill tuning

| Parameter | Guidance |
|-----------|----------|
| Batch size | 1000–10000; decrease if autovacuum falls behind |
| Sleep between batches | 0.05–0.5s; increase during peak |
| Transaction per batch | YES — commit each batch to prevent long-running xid |
| Progress tracking | Persist the cursor in the batch's own transaction, or re-derive it with `min(id) WHERE new_col IS NULL`. Never `max(id) WHERE new_col IS NOT NULL` — see §6 |
| Post-backfill | Run `ANALYZE target_table` to update statistics |

---

## 4. Partition-Based Migration

For very large tables (>100M rows), converting to partitioned tables enables
instant old-data cleanup and rolling schema changes.

### Converting non-partitioned → partitioned

PostgreSQL doesn't support `ALTER TABLE ... PARTITION BY` on existing tables.
The migration requires:

1. Create partitioned parent with desired schema
2. Create partitions (by range, list, or hash)
3. Migrate data partition-by-partition (can be done online)
4. Swap via rename (brief AccessExclusiveLock)
5. Re-point foreign keys and update application

### Detaching partitions (PG 14+)

```sql
-- PG 14+: non-blocking partition detach
ALTER TABLE parent DETACH PARTITION old_partition CONCURRENTLY;

-- PG <14: requires AccessExclusiveLock
ALTER TABLE parent DETACH PARTITION old_partition;
```

---

## 5. Monitoring During Migration

### Essential queries

```sql
-- Replication lag (on replica)
SELECT now() - pg_last_xact_replay_timestamp() AS replication_lag;

-- Dead tuple count (backfill creates dead tuples)
SELECT relname, n_dead_tup, last_vacuum, last_autovacuum
FROM pg_stat_user_tables
WHERE relname = '<table>';

-- Lock waiters
SELECT pid, wait_event_type, wait_event, query
FROM pg_stat_activity
WHERE wait_event_type = 'Lock';

-- Table bloat estimate
SELECT relname, pg_total_relation_size(oid) AS total_size
FROM pg_class WHERE relname = '<table>';

-- Invalid indexes (from interrupted CONCURRENTLY builds)
SELECT indexrelid::regclass, indisvalid
FROM pg_index WHERE NOT indisvalid;
```

### Alert thresholds during migration

- Replication lag > 5 seconds → pause backfill
- Dead tuples > 10% of reltuples → trigger manual VACUUM
- Lock wait time > 3 seconds → investigate and retry
- Disk usage > 85% → pause and assess

---

## 6. Abort and Recovery

### Failed CONCURRENTLY index build

```sql
-- Check for invalid indexes
SELECT indexrelid::regclass FROM pg_index WHERE NOT indisvalid;

-- Drop the invalid index and retry. `table` and `columns` are reserved words, so a
-- placeholder spelled that way is a syntax error, not a template -- name them.
DROP INDEX CONCURRENTLY IF EXISTS idx_orders_date;
CREATE INDEX CONCURRENTLY idx_orders_date ON orders (created_at);
```

### Failed pg_repack

pg_repack creates temporary objects during operation:
- `repack.table_<oid>` — shadow table
- Triggers on the original table

If pg_repack crashes mid-operation:
```sql
-- Check for leftover objects
SELECT * FROM pg_catalog.pg_tables WHERE schemaname = 'repack';
```

**pg_repack has no cleanup mode, and `--dry-run` is not one.** `--dry-run` only prints
the objects that *would* be processed and exits; it removes nothing. The documented
recovery from a crashed run is to drop and re-create the extension, which takes the
`repack` schema and its temporary objects with it:

```sql
DROP EXTENSION pg_repack;
CREATE EXTENSION pg_repack;
```

Check for leftover triggers on the target table before declaring the cleanup done — a
crash can leave the log trigger behind, and it will keep writing to a log table that no
longer has a consumer.

### Resuming interrupted backfill

**Do not use `SELECT MAX(id) ... WHERE new_col IS NOT NULL` as the resume point.** `MAX`
returns the highest processed id, so resuming at `MAX + 1` **skips every unprocessed row
below it**. That happens whenever processing is not strictly monotonic — parallel workers,
a retried batch, or (most commonly) rows where `compute_value()` legitimately yields NULL,
which are indistinguishable from unprocessed rows by this predicate.

Two sound options:

```sql
-- Option A (preferred): make the work predicate the cursor. No stored resume point.
-- Re-running is idempotent and cannot skip: it always picks the lowest unprocessed row.
SELECT min(id) FROM target_table WHERE new_col IS NULL;
```

```sql
-- Option B: an explicit progress table, written in the SAME transaction as each batch,
-- so progress can never claim more than was committed.
CREATE TABLE IF NOT EXISTS backfill_progress (
  job      text PRIMARY KEY,
  last_id  bigint NOT NULL,
  updated  timestamptz NOT NULL DEFAULT now()
);
-- inside each batch transaction ($1 = the largest key THIS batch updated):
INSERT INTO backfill_progress (job, last_id) VALUES ('orders_new_col', $1)
ON CONFLICT (job) DO UPDATE SET last_id = excluded.last_id, updated = now();
```

If `compute_value()` can return NULL, Option A's predicate never terminates — add a
`processed boolean` marker column (or a sentinel value) so "done" is representable
distinctly from "NULL result".
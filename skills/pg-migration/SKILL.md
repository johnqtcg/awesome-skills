---
name: pg-migration
description: >
  PostgreSQL schema migration safety reviewer and DDL generator. ALWAYS use when writing,
  reviewing, or planning PostgreSQL schema changes — ALTER TABLE, CREATE/DROP INDEX,
  column type changes, constraint additions, RLS policy changes, or any DDL touching
  production tables. Covers lock-level analysis, CREATE INDEX CONCURRENTLY, NOT VALID
  constraint patterns, transactional DDL rollback, expand-contract for table rewrites,
  pg_repack for online reorganisation, phased rollout design, and backward compatibility.
  Use even for "simple" ADD COLUMN —
  PostgreSQL DDL lock behavior varies by operation and version, and AccessExclusiveLock
  on a hot table causes immediate outage.
---

# PostgreSQL Migration Safety Review

## Quick Reference

| If you need to…                        | Go to                                   |
|----------------------------------------|-----------------------------------------|
| Understand what this skill covers      | §1 Scope                                |
| Check mandatory prerequisites          | §2 Mandatory Gates                      |
| Choose review depth                    | §3 Depth Selection                      |
| Handle incomplete context              | §4 Degradation Modes                    |
| Analyze DDL safety item by item        | §5 DDL Safety Checklist                 |
| Design a phased execution plan         | §6 Execution Plan                       |
| Avoid common migration mistakes        | §7 Anti-Examples                        |
| Score the review result                | §8 Scorecard                            |
| Format review output                   | §9 Output Contract                      |
| Look up DDL lock levels by operation   | `references/pg-ddl-lock-matrix.md`      |
| Plan a large-table (>10M rows) change  | `references/large-table-migration.md`   |

---

## §1 Scope

**In scope** — schema migration safety for PostgreSQL **14–18** (the community-supported majors as of 2026-08; 12 and 13 are EOL, 19 is unreleased):

- ALTER TABLE (add/drop/modify column, add/drop constraint, rename)
- CREATE / DROP INDEX (including CONCURRENTLY)
- Constraint management (FK, CHECK, UNIQUE, NOT NULL with NOT VALID pattern)
- Data backfill and transformation migrations
- Table restructuring (partitioning, splitting, merging)
- RLS policy additions and modifications
- Extension management (CREATE/ALTER EXTENSION)
- Migration file review (Flyway, golang-migrate, Alembic, raw SQL)
- Rollback planning leveraging PostgreSQL's transactional DDL

**Out of scope** — delegate to dedicated skills:

- Query optimization, connection pooling, vacuum tuning → `postgresql-best-practise`
- Application code changes → `go-code-reviewer` or language-specific reviewer
- Security hardening, privilege management → `security-review`

---

## §2 Mandatory Gates

Execute gates sequentially. Each gate has a **STOP** condition.

### Gate 1: Context Collection

| Item | Why it matters | If unknown |
|------|----------------|------------|
| **PG version** (14 / 15 / 16 / 17 / 18) | DDL behavior differs by version (REINDEX CONCURRENTLY needs 12+, DETACH PARTITION CONCURRENTLY needs 14+) | Assume PG 14 — the oldest supported major, so the least capable. If the user names 12 or 13, flag it as EOL before reviewing |
| **Table row count** | Determines lock tolerance and tool choice | Ask, or estimate via `pg_class.reltuples` |
| **Table size (data + indexes)** | Large tables need CONCURRENTLY / expand-contract | Estimate via `pg_total_relation_size()` |
| **Active QPS on table** | High-traffic amplifies lock contention | Assume high-traffic |
| **Replication type** | Streaming vs logical; DDL handling differs | Assume streaming replica |
| **Maintenance window** | Some DDL needs low-traffic period | Assume none (zero-downtime required) |
| **Migration framework** | Flyway/Alembic/golang-migrate affect transaction handling | Detect from project files |
| **Extensions in use** | Some DDL depends on extensions (pg_repack, pgcrypto) | Check `\dx` |

**If database access is available**, run:

```sql
SELECT version();
SELECT relname, reltuples::bigint, pg_total_relation_size(oid) FROM pg_class WHERE relname = '<table>';
SELECT * FROM pg_extension;
```

**STOP**: Cannot determine whether the target is PostgreSQL. Redirect to appropriate skill.

**PROCEED**: At least PG version and table name known or conservatively assumed. Record all assumptions.

### Gate 2: Scope Classification

| Mode | Trigger | Output |
|------|---------|--------|
| **review** | User provides existing migration SQL/file | Safety analysis of provided DDL |
| **generate** | User describes desired schema change | Migration SQL + safety analysis |
| **plan** | User describes goal without specifics | Phased migration plan + rationale |

**STOP**: Request is not migration-related. Redirect to `postgresql-best-practise`.

**PROCEED**: Migration intent confirmed.

### Gate 3: Risk Classification

For each DDL statement, classify by lock impact:

| Risk | Lock level | Examples | Required action |
|------|-----------|----------|-----------------|
| **SAFE** | ShareUpdateExclusiveLock or lower — reads **and** writes continue | `CREATE/DROP INDEX CONCURRENTLY`, `VALIDATE CONSTRAINT`, `SET STATISTICS`, fillfactor/autovacuum storage params | Standard session guards |
| **WARN** | ShareLock or ShareRowExclusiveLock — reads continue, writes block | plain `CREATE INDEX` (ShareLock); `ADD FOREIGN KEY` **with or without `NOT VALID`** (ShareRowExclusive on *both* the altered and the referenced table) | Off-peak window + monitoring, on both tables |
| **UNSAFE** | AccessExclusiveLock on a table >1M rows, or any full table rewrite | most `ALTER TABLE` subcommands, incl. `ADD CHECK` (with **or** without `NOT VALID`); `int`→`bigint`; volatile-DEFAULT `ADD COLUMN` | Expand-contract or create-swap-rename + staged rollout (see §5.2 item 6) |

**`NOT VALID` shortens how long the lock is held, never its class** — an FK is
ShareRowExclusive either way, a CHECK is AccessExclusive either way (AE-18).

**STOP**: Any UNSAFE item has no mitigation plan.

**PROCEED**: Every DDL statement has risk level and mitigation.

### Gate 4: Output Completeness

Before delivering output, verify all §9 Output Contract sections present. §9.9 Uncovered Risks must never be empty.

---

## §3 Depth Selection

| Depth | When to use | Gates | References to load |
|-------|-------------|-------|-------------------|
| **Lite** | ≤3 DDL statements, none of which scans or rewrites the table (ADD nullable column, CONCURRENTLY index) | 1–4 | None |
| **Standard** | 4–15 statements, or any operation that holds AccessExclusiveLock **for a scan or rewrite** | 1–4 | `pg-ddl-lock-matrix.md` |
| **Deep** | >15 statements, table >10M rows, or multi-step data migration | 1–4 | Both reference files |

"Lite" is about *duration*, not lock class. `ADD COLUMN … NULL` still takes
AccessExclusiveLock (verified on live 14.23/18.4) — briefly, but it still queues behind
every open transaction and blocks everything behind it while waiting, so **it still needs
`lock_timeout`**. Only ShareUpdateExclusive operations are genuinely non-blocking.

**Force Standard or higher** when any signal appears:
column type change, NOT NULL addition, PK modification, FK/CHECK constraint, RLS policy change, partition restructuring, column removal, extension upgrade.

---

## §4 Degradation Modes

When context is incomplete, degrade gracefully — never fabricate information.

| Available context | Mode | What you can do | What you cannot do |
|-------------------|------|-----------------|-------------------|
| Full (version, size, QPS, replicas) | **Full** | All checklist items; lock-time estimates **conditional on a stated I/O rate**, with the assumption written out | Precise wall-clock. Duration depends on production I/O throughput, cache state, and how long the longest open transaction makes the DDL wait for its lock — none of which are in the schema |
| Version + size known, others unknown | **Degraded** | Full checklist with conservative assumptions | Precise lock-time estimates |
| Only migration SQL, no context | **Minimal** | Static DDL analysis, flag all unknowns | Version-specific advice, replication assessment |
| No SQL (planning request) | **Planning** | Generate migration plan from requirements | Review existing SQL |

**Hard rule**: Never claim "SAFE" without evidence. In Degraded/Minimal mode, mark items as "SAFE (assumed — verify against production)" and list all assumptions in §9.9 Uncovered Risks.

---

## §5 DDL Safety Checklist

Execute every item for each DDL statement. Mark **SAFE** / **WARN** / **UNSAFE** with evidence.

### 5.1 Lock Level Assessment

1. **Lock classification** — determine lock level for each DDL. The governing rule from the `ALTER TABLE` reference: *"An ACCESS EXCLUSIVE lock is acquired unless explicitly noted. When multiple subcommands are given, the lock acquired will be the strictest one required by any subcommand."*
   - `AccessExclusiveLock`: blocks ALL operations including SELECT — the default for ALTER TABLE. When uncertain → load `references/pg-ddl-lock-matrix.md`.
   - `ShareRowExclusiveLock`: blocks writes, allows reads. **`ADD FOREIGN KEY` is this class, on both the altered table and the referenced table.** `ADD CHECK` is *not* — it is AccessExclusive. Never state a combined rule for FK and CHECK.
   - `ShareLock`: blocks writes but allows reads (e.g., CREATE INDEX non-concurrently).
   - `ShareUpdateExclusiveLock`: allows concurrent reads AND writes (e.g., CREATE INDEX CONCURRENTLY, VALIDATE CONSTRAINT, SET STATISTICS, fillfactor/autovacuum storage parameters).
   - Key difference from MySQL: PostgreSQL has no `ALGORITHM=` hint — the lock level is determined by the operation type.

1b. **Never batch subcommands of different lock classes.** Because a multi-subcommand ALTER TABLE escalates to the strictest lock, appending a cheap subcommand to a low-lock one destroys the benefit:
   ```sql
   -- WRONG: the ADD COLUMN drags the whole statement to AccessExclusive
   ALTER TABLE orders
     ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) NOT VALID,
     ADD COLUMN note text;
   -- RIGHT: one statement per lock class
   ALTER TABLE orders ADD COLUMN note text;
   ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) NOT VALID;
   ```

2. **lock_timeout** — mandatory before every DDL, but **the correct form depends on whether the statement runs inside a transaction block**. Getting this wrong is silent: `SET LOCAL` outside a transaction "emits a warning and otherwise has no effect", so the guard you think you set does not exist.

   **Case A — transactional DDL (the default).** Use `SET LOCAL`; it reverts automatically on COMMIT/ROLLBACK:
   ```sql
   BEGIN;
   SET LOCAL lock_timeout = '3s';
   SET LOCAL statement_timeout = '30s';
   ALTER TABLE users ADD COLUMN bio text;
   COMMIT;
   ```

   **Case B — statements that cannot be in a transaction block** (`CREATE/DROP INDEX CONCURRENTLY`, `REINDEX CONCURRENTLY`, `DETACH PARTITION CONCURRENTLY`). `SET LOCAL` is a no-op here. Use session-level `SET` and reset afterwards:
   ```sql
   SET lock_timeout = '3s';
   SET statement_timeout = 0;          -- see item 3: never cap a concurrent build
   CREATE INDEX CONCURRENTLY idx_orders_date ON orders (created_at);
   RESET statement_timeout;
   RESET lock_timeout;
   ```
   Equivalent out-of-band forms: `PGOPTIONS="-c lock_timeout=3s" psql …`, or `ALTER ROLE migrator SET lock_timeout = '3s'`.

   Without lock_timeout, DDL queues indefinitely on its lock and every query behind it stalls.

3. **CONCURRENTLY for indexes** — `CREATE INDEX CONCURRENTLY` takes ShareUpdateExclusiveLock instead of ShareLock, allowing concurrent writes. Plain `CREATE INDEX` blocks all writes for the whole build. Always use CONCURRENTLY on production tables. Two hard caveats:
   - **Cannot run inside a transaction block** → drives the Case B guard above. Migration frameworks that wrap each file in a transaction (Flyway, golang-migrate, Alembic by default) must be told to disable it for this statement.
   - **Never set a short `statement_timeout` around it.** `statement_timeout` aborts any statement that exceeds it, and a concurrent build on a large table can run for hours. A 30s cap kills the build and leaves an INVALID index. Guard the lock wait with `lock_timeout`; leave `statement_timeout` at 0 for the build.

4. **NOT VALID for constraints** — `NOT VALID` skips the row-validation scan, so it shortens the *duration* the lock is held. It does not change the lock *class*. Follow up with `VALIDATE CONSTRAINT` (ShareUpdateExclusiveLock, non-blocking):
   ```sql
   ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) NOT VALID;
   ALTER TABLE orders VALIDATE CONSTRAINT fk_user;  -- non-blocking
   ```
   - **FK**: both steps are read-permitting (ShareRowExclusive, then ShareUpdateExclusive + RowShare on the referenced table). Report the referenced table's write-blocking too.
   - **CHECK**: `ADD ... NOT VALID` is AccessExclusive but brief; the bare form holds AccessExclusive for the whole scan.
   - **Partitioned tables — version-gated.** On **PG 14–17** an FK on a partitioned table **may not be declared `NOT VALID`**: the server raises `cannot add NOT VALID foreign key on partitioned table`, so the two-step pattern is unavailable — plan the single-step addition or attach pre-validated partitions. **PG 18 accepts it.** Verified on live 14.23/15/16/17/18.4. Check the target version before emitting SQL that would fail.

### 5.2 Data Integrity

5. **ADD COLUMN with DEFAULT** — the gate is **volatility, not the presence of a DEFAULT**. A *non-volatile* DEFAULT is stored in catalog metadata and requires no rewrite (PG 11+). A *volatile* DEFAULT (`random()`, `clock_timestamp()`, `gen_random_uuid()`) rewrites the entire table and its indexes on every version. Check the default expression's volatility before calling this safe.

6. **Column type change** — the documented exemption is narrow: no rewrite only when the `USING` clause does not change the column contents **and** the old type is binary coercible to the new type (or an unconstrained domain over it). Everything else rewrites.
   - No rewrite: `varchar(N)` → `varchar(M)` widening; `text` ↔ `varchar` with no collation change.
   - **Rewrites: `int` → `bigint`.** `int4` is not binary coercible to `int8`. Integer widening is *not* cheap — this is the most common false assumption in PostgreSQL migration planning.
   - Rewrites: `numeric(10,2)` → `numeric(12,4)`, and any collation change (index rebuild mandatory even if the heap is untouched).
   - **`pg_repack` cannot change a schema** — it reorganises a table under its *existing*
     definition and has no column-type option. Use **expand-contract**, **create-swap-rename**,
     or a **logical-replication cutover**. pg_repack afterwards only if you measure bloat: a
     rewriting `ALTER` builds a fresh compact heap and leaves none, whereas the batched
     `UPDATE`s of an expand-contract backfill do. `references/large-table-migration.md` §1.

7. **Constraint idempotency** — PostgreSQL lacks `ADD CONSTRAINT IF NOT EXISTS`, so guards are hand-written, and both common forms are wrong in a way that reports success:
   - **Scope the lookup by `conrelid`.** Constraint names are unique per table, not per database, so a bare `conname` check skips the migration whenever any *other* table carries that name (AE-16).
   - **Compare the definition, not just the name.** If the same table already has that constraint name with a *different* definition, a name-only guard skips and leaves the wrong constraint in place. Read `pg_get_constraintdef()` and `RAISE EXCEPTION` on mismatch — never skip. `CREATE INDEX IF NOT EXISTS` has the identical hole: an existing `idx_x ON t (amt)` silently survives a migration asking for `idx_x ON t (note)`. Both verified on a live server.

   Full template for both: AE-19 in `references/migration-anti-examples.md`. Index guards additionally need schema scoping (`pg_indexes.schemaname`, or a `relnamespace` join on `pg_class`).

8. **FK cascade risk** — ON DELETE CASCADE on large parent → uncontrolled write amplification. Ensure FK target columns are indexed (critical for CASCADE performance).

### 5.3 Backward Compatibility

9. **Deployment ordering** — same as MySQL: column add → schema first, then app; column remove → app first, then schema; column rename → create new + dual-write → drop old.

10. **Rollback feasibility** — PostgreSQL's transactional DDL means most DDL can be rolled back within a transaction. However:
    - CONCURRENTLY operations cannot run in transactions (no rollback)
    - DROP COLUMN data is not immediately recoverable even with ROLLBACK after COMMIT
    - Classify: **transactional-rollback** / **manual-rollback** / **irreversible**

### 5.4 Operational Safety

11. **Session timeouts** — every migration must set `lock_timeout`. Pick the form by execution context (§5.1 item 2): `SET LOCAL` inside a transaction block, session-level `SET` + `RESET` for statements that cannot be in one. `statement_timeout` should bound ordinary DDL but must be 0 (or unset) around CONCURRENTLY builds.

12. **Disk / WAL space** — table rewrite creates new heap + indexes (~2× table size). CONCURRENTLY index build needs temporary disk. Check `pg_total_relation_size()`.

13. **Vacuum after migration** — large backfills create dead tuples. Run `ANALYZE <table>` after migration; consider manual `VACUUM` if autovacuum lag is expected.

14. **Statement granularity** — wrap related DDL in a single transaction where possible (PostgreSQL advantage), but **never batch subcommands of different lock classes into one ALTER TABLE** (item 1b). Exception: CONCURRENTLY must be outside transactions.

### 5.5 Replication, RLS and Extensions

In scope, but **no automated lint rule covers these** — review by hand and record the outcome in §9.9. Details and checklists: `references/replication-rls-extensions.md`.

15. **Logical replication does not replicate DDL.** Recording "replication type" is not enough. Apply additive DDL on every **subscriber first**, then the publisher; reverse for removals. Otherwise replication halts and the subscription falls behind. Streaming replication needs none of this, but a table rewrite ships the entire rewritten heap as WAL — estimate that against replica bandwidth.

16. **RLS policy changes** take AccessExclusiveLock. `ENABLE ROW LEVEL SECURITY` with no policy denies all rows to non-owner roles, and testing as the table owner proves nothing (owners bypass policies). Add policies before enabling; test as the application role.

17. **Extension management** — `CREATE`/`ALTER EXTENSION ... UPDATE` runs the extension's own scripts, taking whatever locks its author chose. Pin the version, read the upgrade script, and treat it as unbounded-risk DDL.

---

## §6 Execution Plan (Standard + Deep)

Standard phased pattern for zero-downtime migration:

1. **Phase 1 — Additive schema**: add nullable columns, constraints with NOT VALID, CONCURRENTLY indexes
2. **Phase 2 — Backfill**: populate new columns using cursor-based batches (see `references/large-table-migration.md` §3)
3. **Phase 3 — App deploy**: deploy code writing to both old and new schema
4. **Phase 4 — Constraint validation**: `VALIDATE CONSTRAINT` (non-blocking), add NOT NULL
5. **Phase 5 — Cleanup** (separate release): drop old columns, remove dual-write

Each phase: **Pre-condition** → **SQL** (with lock_timeout) → **Validation** → **Rollback** → **Go/No-go**.

For tables >10M rows needing a **schema change**, use expand-contract or create-swap-rename —
**not** pg_repack, which cannot alter a schema, takes AccessExclusiveLock twice, and by default
kills the backends blocking it. `references/large-table-migration.md` §1.

---

## §7 Anti-Examples

### AE-1: CREATE INDEX without CONCURRENTLY
```sql
-- WRONG: blocks all writes for entire index build duration (ShareLock)
CREATE INDEX idx_orders_date ON orders (created_at);
-- RIGHT: non-blocking index build
CREATE INDEX CONCURRENTLY idx_orders_date ON orders (created_at);
```

### AE-2: ADD CONSTRAINT without NOT VALID
`NOT VALID` shortens how long the lock is held; it never changes the lock *class*.
```sql
-- WRONG: ShareRowExclusive on orders AND on users, held for the whole validating scan.
-- Reads still work; every write to either table blocks for minutes on a large table.
ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id);
-- RIGHT: same ShareRowExclusive class, but held only briefly, then a non-blocking validation
ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) NOT VALID;
ALTER TABLE orders VALIDATE CONSTRAINT fk_user;  -- ShareUpdateExclusive + RowShare on users
```
A CHECK is a **different class** — AccessExclusive either way, so it blocks reads too (AE-18).
On a **partitioned** table the FK two-step is only available from PG 18 (§5.1 item 4).

### AE-3: lock_timeout missing, or in the wrong form for its context
```sql
-- WRONG: no guard at all — waits indefinitely, blocking every query behind it
ALTER TABLE users ADD COLUMN bio TEXT;
-- WRONG: CONCURRENTLY cannot be in a transaction block, so there is no transaction for
-- SET LOCAL to scope to. PostgreSQL warns and the timeout is NEVER APPLIED.
SET LOCAL lock_timeout = '3s';
CREATE INDEX CONCURRENTLY idx_orders_date ON orders (created_at);
-- RIGHT (in a transaction): SET LOCAL, auto-reverts on COMMIT
BEGIN;
SET LOCAL lock_timeout = '3s';
ALTER TABLE users ADD COLUMN bio TEXT;
COMMIT;
-- RIGHT (cannot be in a transaction): session-level SET, then RESET
SET lock_timeout = '3s';
SET statement_timeout = 0;
CREATE INDEX CONCURRENTLY idx_orders_date ON orders (created_at);
RESET statement_timeout;
RESET lock_timeout;
```


### AE-4: ALTER COLUMN TYPE on large table without tool
```sql
-- WRONG: full table rewrite with AccessExclusiveLock on 50M-row table
ALTER TABLE events ALTER COLUMN payload TYPE jsonb USING payload::jsonb;
-- ALSO WRONG: pg_repack cannot change a schema — it has no column-type option at all
-- RIGHT: expand-contract — add nullable, batch-backfill, dual-write, cut reads, drop later
ALTER TABLE events ADD COLUMN payload_jsonb jsonb;
```
Alternatives when expand-contract does not fit: create-swap-rename, or a logical-replication
cutover. All three in `references/large-table-migration.md` §1–§2.

### AE-5: ADD CONSTRAINT IF NOT EXISTS (invalid syntax)
```sql
-- WRONG: PostgreSQL does NOT support IF NOT EXISTS for constraints — this is a syntax error
ALTER TABLE orders ADD CONSTRAINT IF NOT EXISTS fk_user FOREIGN KEY (user_id) REFERENCES users(id);
-- RIGHT: use DO block with pg_constraint check (see §5.2 item 7)
```

### AE-6: Style nitpick reported as migration risk
```
-- WRONG: "WARN — table name 'OrderItems' uses CamelCase"
-- RIGHT: only flag naming if it causes functional problems (quoting issues, ORM conflicts)
```

Extended anti-examples (AE-7 through AE-19) in `references/migration-anti-examples.md` — including
short `statement_timeout` around a concurrent build (AE-14), mixed lock classes in one
ALTER TABLE (AE-15), unqualified constraint guards (AE-16), and `int` → `bigint` treated as
metadata-only (AE-17).

---

## §8 Migration Scorecard

### Critical — any FAIL means overall FAIL

- [ ] `lock_timeout` set before every DDL, in the form matching its execution context — `SET LOCAL` inside a transaction block, session-level `SET` + `RESET` for CONCURRENTLY statements (which cannot be in one). A `SET LOCAL` outside a transaction block is a FAIL: it only warns and has no effect.
- [ ] Indexes use `CREATE INDEX CONCURRENTLY` (not plain `CREATE INDEX`) on production tables, outside any transaction block, without a short `statement_timeout`
- [ ] Rollback path provided for every phase (transaction rollback, manual rollback, or irreversibility documented)

### Standard — at least 80% of applicable items must pass (normally 4 of 5)

- [ ] FK/CHECK constraints use `NOT VALID` + `VALIDATE CONSTRAINT` two-step on tables >100K rows. **N/A for an FK on a partitioned table below PG 18** — the server rejects `NOT VALID` there (§5.1 item 4), so FAIL would penalise the only SQL that runs. Record the single-step addition and its write-freeze window in §9.9.
- [ ] Constraint additions use idempotent DO blocks (not bare `ADD CONSTRAINT`)
- [ ] Backward-compatible deployment order (additive before app, removal after app)
- [ ] Backfill uses cursor/keyset batching, not `LIMIT/OFFSET`
- [ ] Validation SQL provided for each phase

### Hygiene — 3 of 4 must pass

- [ ] Disk/WAL impact estimated for rewrite operations
- [ ] `statement_timeout` set alongside `lock_timeout`
- [ ] Post-deploy monitoring specified (replication lag, dead tuple count, error rate)
- [ ] `ANALYZE` scheduled after large backfills

**Verdict**: `X/N`; Critical: `Y/3`; Standard: `Z/A`; Hygiene: `W/4`.
`N` is the total number of applicable items and `A` is the number of applicable
Standard items. PASS requires: Critical 3/3 AND Standard `Z/A` ≥80% AND Hygiene ≥3/4.

**N/A** is excluded from both denominators, never counted as a pass. For example, one
Standard N/A yields `X/11` overall; Standard 3/4 is then 75% and FAILS the unchanged
≥80% bar. Record every N/A reason in §9.9.

---

## §9 Output Contract

Every migration review MUST produce these sections. Write "N/A — [reason]" if inapplicable.

```
### 9.1 Context Gate
| Item | Value | Source |

### 9.2 Depth & Mode
[Lite/Standard/Deep] × [review/generate/plan] — [rationale]

### 9.3 Risk Assessment Table
| # | DDL Statement | Lock Level | Risk | Notes |

### 9.4 Execution Plan (Standard/Deep; "N/A — Lite" for Lite)

### 9.5 Migration SQL (with lock_timeout, CONCURRENTLY, NOT VALID as applicable)

### 9.6 Validation SQL

### 9.7 Rollback Plan (per-phase; note transactional vs manual rollback)

### 9.8 Post-Deploy Checks

### 9.9 Uncovered Risks (MANDATORY — never empty)
| Area | Reason | Impact | Follow-up |
```

**Volume rules**:
- UNSAFE: always fully detailed with mitigation
- WARN: up to 10; overflow to §9.9
- SAFE: summary row only
- §9.9 minimum: document all conservative assumptions made

**Scorecard summary** (append after §9.9):
```
Scorecard: X/N — Critical Y/3, Standard Z/A, Hygiene W/4 — PASS/FAIL
Data basis: [full context | degraded | minimal | planning]
```

---

## §10 Reference Loading Guide

| Condition | Load |
|-----------|------|
| Standard or Deep depth | `references/pg-ddl-lock-matrix.md` |
| Deep depth, or table >10M rows | `references/large-table-migration.md` |
| Extended anti-example matching | `references/migration-anti-examples.md` |
| Logical replication, RLS, or extension DDL in scope | `references/replication-rls-extensions.md` |

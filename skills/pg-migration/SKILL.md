---
name: pg-migration
description: >
  PostgreSQL schema migration safety reviewer and DDL generator. ALWAYS use when writing,
  reviewing, or planning PostgreSQL schema changes — ALTER TABLE, CREATE/DROP INDEX,
  column type changes, constraint additions, RLS policy changes, or any DDL touching
  production tables. Covers lock-level analysis, CREATE INDEX CONCURRENTLY, NOT VALID
  constraint patterns, transactional DDL rollback, pg_repack for table rewrites, phased
  rollout design, and backward compatibility. Use even for "simple" ADD COLUMN —
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

**In scope** — schema migration safety for PostgreSQL 12–17 (primary focus 14+):

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
| **PG version** (12 / 13 / 14 / 15 / 16 / 17) | DDL behavior differs by version (e.g., PG 11+ non-rewriting NOT NULL DEFAULT) | Assume PG 12 (conservative) |
| **Table row count** | Determines lock tolerance and tool choice | Ask, or estimate via `pg_class.reltuples` |
| **Table size (data + indexes)** | Large tables need CONCURRENTLY / pg_repack | Estimate via `pg_total_relation_size()` |
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

| Risk | Lock level | Required action |
|------|-----------|-----------------|
| **SAFE** | No lock or ShareUpdateExclusiveLock (e.g., CONCURRENTLY, NOT VALID) | Standard session guards |
| **WARN** | ShareLock or ShareRowExclusiveLock | Off-peak window + monitoring |
| **UNSAFE** | AccessExclusiveLock on table >1M rows, or full table rewrite | pg_repack + staged rollout |

**STOP**: Any UNSAFE item has no mitigation plan.

**PROCEED**: Every DDL statement has risk level and mitigation.

### Gate 4: Output Completeness

Before delivering output, verify all §9 Output Contract sections present. §9.9 Uncovered Risks must never be empty.

---

## §3 Depth Selection

| Depth | When to use | Gates | References to load |
|-------|-------------|-------|-------------------|
| **Lite** | ≤3 DDL statements, all non-blocking (ADD nullable column, CONCURRENTLY index) | 1–4 | None |
| **Standard** | 4–15 statements, or any AccessExclusiveLock operation | 1–4 | `pg-ddl-lock-matrix.md` |
| **Deep** | >15 statements, table >10M rows, or multi-step data migration | 1–4 | Both reference files |

**Force Standard or higher** when any signal appears:
column type change, NOT NULL addition, PK modification, FK/CHECK constraint, RLS policy change, partition restructuring, column removal, extension upgrade.

---

## §4 Degradation Modes

When context is incomplete, degrade gracefully — never fabricate information.

| Available context | Mode | What you can do | What you cannot do |
|-------------------|------|-----------------|-------------------|
| Full (version, size, QPS, replicas) | **Full** | All checklist items, precise lock-time estimates | — |
| Version + size known, others unknown | **Degraded** | Full checklist with conservative assumptions | Precise lock-time estimates |
| Only migration SQL, no context | **Minimal** | Static DDL analysis, flag all unknowns | Version-specific advice, replication assessment |
| No SQL (planning request) | **Planning** | Generate migration plan from requirements | Review existing SQL |

**Hard rule**: Never claim "SAFE" without evidence. In Degraded/Minimal mode, mark items as "SAFE (assumed — verify against production)" and list all assumptions in §9.9 Uncovered Risks.

---

## §5 DDL Safety Checklist

Execute every item for each DDL statement. Mark **SAFE** / **WARN** / **UNSAFE** with evidence.

### 5.1 Lock Level Assessment

1. **Lock classification** — determine lock level for each DDL. PostgreSQL DDL acquires various lock levels:
   - `AccessExclusiveLock`: blocks ALL operations (most ALTER TABLE variants). When uncertain → load `references/pg-ddl-lock-matrix.md`.
   - `ShareLock`: blocks writes but allows reads (e.g., CREATE INDEX non-concurrently).
   - `ShareUpdateExclusiveLock`: allows concurrent reads AND writes (e.g., CREATE INDEX CONCURRENTLY, VALIDATE CONSTRAINT).
   - Key difference from MySQL: PostgreSQL has no `ALGORITHM=` hint — the lock level is determined by the operation type.

2. **lock_timeout** — set before every DDL session:
   ```sql
   SET LOCAL lock_timeout = '3s';
   SET LOCAL statement_timeout = '30s';
   ```
   Without lock_timeout, DDL waits indefinitely for AccessExclusiveLock, blocking all subsequent queries.

3. **CONCURRENTLY for indexes** — `CREATE INDEX CONCURRENTLY` avoids ShareLock, allowing concurrent writes. Plain `CREATE INDEX` blocks all writes for the duration. Always use CONCURRENTLY on production tables. Caveat: CONCURRENTLY cannot run inside a transaction block.

4. **NOT VALID for constraints** — adding FK or CHECK constraint with `NOT VALID` skips row validation, taking only a brief AccessExclusiveLock. Follow up with `VALIDATE CONSTRAINT` which takes only ShareUpdateExclusiveLock (non-blocking). Two-step pattern:
   ```sql
   ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) NOT VALID;
   ALTER TABLE orders VALIDATE CONSTRAINT fk_user;  -- non-blocking
   ```

### 5.2 Data Integrity

5. **NOT NULL + DEFAULT** — PostgreSQL 11+ can add NOT NULL column with DEFAULT without rewriting the table (metadata-only). PG <11 requires full table rewrite. Version-gate this recommendation.

6. **Column type change** — most ALTER COLUMN TYPE operations require full table rewrite with AccessExclusiveLock. Exceptions: varchar(N) → varchar(M) where M > N, and some numeric widenings. For large tables, use pg_repack or create-swap-rename pattern.

7. **Constraint idempotency** — PostgreSQL lacks `ADD CONSTRAINT IF NOT EXISTS`. Use DO blocks:
   ```sql
   DO $$ BEGIN
     IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'my_fk') THEN
       ALTER TABLE t ADD CONSTRAINT my_fk FOREIGN KEY (col) REFERENCES other(id) NOT VALID;
     END IF;
   END $$;
   ```

8. **FK cascade risk** — ON DELETE CASCADE on large parent → uncontrolled write amplification. Ensure FK target columns are indexed (critical for CASCADE performance).

### 5.3 Backward Compatibility

9. **Deployment ordering** — same as MySQL: column add → schema first, then app; column remove → app first, then schema; column rename → create new + dual-write → drop old.

10. **Rollback feasibility** — PostgreSQL's transactional DDL means most DDL can be rolled back within a transaction. However:
    - CONCURRENTLY operations cannot run in transactions (no rollback)
    - DROP COLUMN data is not immediately recoverable even with ROLLBACK after COMMIT
    - Classify: **transactional-rollback** / **manual-rollback** / **irreversible**

### 5.4 Operational Safety

11. **Session timeouts** — every migration must set `lock_timeout` and `statement_timeout`. Use `SET LOCAL` (transaction-scoped) rather than `SET SESSION`.

12. **Disk / WAL space** — table rewrite creates new heap + indexes (~2× table size). CONCURRENTLY index build needs temporary disk. Check `pg_total_relation_size()`.

13. **Vacuum after migration** — large backfills create dead tuples. Run `ANALYZE <table>` after migration; consider manual `VACUUM` if autovacuum lag is expected.

14. **Statement granularity** — wrap related DDL in a single transaction where possible (PostgreSQL advantage). Exception: CONCURRENTLY must be outside transactions.

---

## §6 Execution Plan (Standard + Deep)

Standard phased pattern for zero-downtime migration:

1. **Phase 1 — Additive schema**: add nullable columns, constraints with NOT VALID, CONCURRENTLY indexes
2. **Phase 2 — Backfill**: populate new columns using cursor-based batches (see `references/large-table-migration.md` §3)
3. **Phase 3 — App deploy**: deploy code writing to both old and new schema
4. **Phase 4 — Constraint validation**: `VALIDATE CONSTRAINT` (non-blocking), add NOT NULL
5. **Phase 5 — Cleanup** (separate release): drop old columns, remove dual-write

Each phase: **Pre-condition** → **SQL** (with lock_timeout) → **Validation** → **Rollback** → **Go/No-go**.

For tables >10M rows needing rewrite, use pg_repack or create-swap-rename. Details in `references/large-table-migration.md`.

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
```sql
-- WRONG: validates every row with AccessExclusiveLock held — locks table for minutes on large tables
ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id);
-- RIGHT: two-step — brief lock then non-blocking validation
ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) NOT VALID;
ALTER TABLE orders VALIDATE CONSTRAINT fk_user;
```

### AE-3: DDL without lock_timeout
```sql
-- WRONG: waits indefinitely for AccessExclusiveLock, blocking all queries behind it
ALTER TABLE users ADD COLUMN bio TEXT;
-- RIGHT:
SET LOCAL lock_timeout = '3s';
ALTER TABLE users ADD COLUMN bio TEXT;
```

### AE-4: ALTER COLUMN TYPE on large table without tool
```sql
-- WRONG: full table rewrite with AccessExclusiveLock on 50M-row table
ALTER TABLE events ALTER COLUMN payload TYPE jsonb USING payload::jsonb;
-- RIGHT: use pg_repack or create-swap-rename (see references/large-table-migration.md)
```

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

Extended anti-examples (AE-7 through AE-13) in `references/migration-anti-examples.md`.

---

## §8 Migration Scorecard

### Critical — any FAIL means overall FAIL

- [ ] `lock_timeout` set before every DDL session (`SET LOCAL lock_timeout`)
- [ ] Indexes use `CREATE INDEX CONCURRENTLY` (not plain `CREATE INDEX`) on production tables
- [ ] Rollback path provided for every phase (transaction rollback, manual rollback, or irreversibility documented)

### Standard — 4 of 5 must pass

- [ ] FK/CHECK constraints use `NOT VALID` + `VALIDATE CONSTRAINT` two-step on tables >100K rows
- [ ] Constraint additions use idempotent DO blocks (not bare `ADD CONSTRAINT`)
- [ ] Backward-compatible deployment order (additive before app, removal after app)
- [ ] Backfill uses cursor/keyset batching, not `LIMIT/OFFSET`
- [ ] Validation SQL provided for each phase

### Hygiene — 3 of 4 must pass

- [ ] Disk/WAL impact estimated for rewrite operations
- [ ] `statement_timeout` set alongside `lock_timeout`
- [ ] Post-deploy monitoring specified (replication lag, dead tuple count, error rate)
- [ ] `ANALYZE` scheduled after large backfills

**Verdict**: `X/12`; Critical: `Y/3`; Standard: `Z/5`; Hygiene: `W/4`.
PASS requires: Critical 3/3 AND Standard ≥4/5 AND Hygiene ≥3/4.

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
Scorecard: X/12 — Critical Y/3, Standard Z/5, Hygiene W/4 — PASS/FAIL
Data basis: [full context | degraded | minimal | planning]
```

---

## §10 Reference Loading Guide

| Condition | Load |
|-----------|------|
| Standard or Deep depth | `references/pg-ddl-lock-matrix.md` |
| Deep depth, or table >10M rows | `references/large-table-migration.md` |
| Extended anti-example matching | `references/migration-anti-examples.md` |
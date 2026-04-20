---
name: mysql-migration
description: >
  MySQL schema migration safety reviewer and DDL generator. ALWAYS use when writing,
  reviewing, or planning MySQL schema changes — ALTER TABLE, CREATE/DROP INDEX, column
  type changes, charset conversions, data backfills, or any DDL touching production tables.
  Covers online DDL algorithm selection (INSTANT/INPLACE/COPY), lock-safety analysis,
  large-table migration with gh-ost/pt-osc, phased rollout design, replication-safe DDL,
  backward compatibility, and rollback planning. Use even for "simple" ADD COLUMN —
  MySQL DDL locking behavior is version- and operation-dependent, and mistakes cause
  production outages.
---

# MySQL Migration Safety Review

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
| Look up DDL algorithm by operation     | `references/ddl-algorithm-matrix.md`    |
| Plan a large-table (>10M rows) change  | `references/large-table-migration.md`   |

---

## §1 Scope

**In scope** — schema migration safety for MySQL 5.7 and 8.0+ (InnoDB):

- ALTER TABLE (add/drop/modify column, add/drop index, rename, convert charset)
- CREATE / DROP INDEX, data backfill and transformation migrations
- Table restructuring (partitioning, splitting, merging), foreign key changes
- Migration file review (Flyway, Liquibase, golang-migrate, raw SQL)
- Rollback planning, verification, and replication impact assessment

**Out of scope** — delegate to dedicated skills:

- Query optimization, connection pooling, buffer tuning → `mysql-best-practise`
- Application code changes → `go-code-reviewer` or language-specific reviewer
- Security hardening, privilege management → `security-review`

---

## §2 Mandatory Gates

Execute gates sequentially. Each gate has a **STOP** condition — if triggered, do not proceed until resolved.

### Gate 1: Context Collection

Collect before giving migration advice:

| Item | Why it matters | If unknown |
|------|----------------|------------|
| **MySQL version** (5.7.x / 8.0.x / 8.4.x) | DDL algorithm support differs dramatically | Assume 5.7 (most restrictive) |
| **Storage engine** | Only InnoDB supports online DDL | Assume InnoDB; WARN if MyISAM |
| **Table row count** | Determines safe DDL vs tool-based threshold | Ask, or estimate via `SHOW TABLE STATUS` |
| **Table data + index size** | Large tables need gh-ost / pt-osc | Ask, or estimate |
| **Active QPS on table** | High-traffic amplifies MDL contention | Assume high-traffic (conservative) |
| **Replication topology** | DDL on source replicates; COPY causes lag | Assume source-replica with GTID |
| **Maintenance window** | Some operations need low-traffic periods | Assume none (zero-downtime required) |
| **Migration framework** | Flyway/Liquibase/golang-migrate affect rollback | Detect from project files |

**If database access is available**, run:

```sql
SELECT VERSION();
SHOW TABLE STATUS WHERE Name = '<table>' \G
SHOW CREATE TABLE <table> \G
```

**STOP**: Cannot determine whether the target is MySQL at all (e.g., migration file has no MySQL-identifiable syntax). Redirect to appropriate skill.

**PROCEED**: At least MySQL version and table name are known or conservatively assumed. Record all assumptions.

### Gate 2: Scope Classification

Classify the request mode:

| Mode | Trigger | Output |
|------|---------|--------|
| **review** | User provides existing migration SQL/file | Safety analysis of provided DDL |
| **generate** | User describes desired schema change | Migration SQL + safety analysis |
| **plan** | User describes goal without specifics | Phased migration plan + rationale |

**STOP**: Request is not migration-related (e.g., query optimization, tuning). Redirect to `mysql-best-practise`.

**PROCEED**: Migration intent confirmed. Continue with depth selection.

### Gate 3: Risk Classification

For each DDL statement, classify risk:

| Risk | Definition | Required action |
|------|------------|-----------------|
| **SAFE** | INSTANT or INPLACE+LOCK=NONE, small table, additive | Session guards sufficient |
| **WARN** | INPLACE with restrictions, or table 1M–10M rows | Off-peak window + monitoring |
| **UNSAFE** | COPY algorithm, >10M rows, or destructive DDL | gh-ost/pt-osc + staged rollout + rollback rehearsal |

**STOP**: Any UNSAFE item has no mitigation plan. Must provide tool-based alternative or phased approach before proceeding.

**PROCEED**: Every DDL statement has a risk level and corresponding mitigation.

### Gate 4: Output Completeness

Before delivering output, verify all §9 Output Contract sections are present. If any section is missing, add it (even if "N/A — [reason]"). §9.9 Uncovered Risks must never be empty.

---

## §3 Depth Selection

| Depth | When to use | Gates | References to load |
|-------|-------------|-------|-------------------|
| **Lite** | ≤3 DDL statements, all additive (ADD nullable column, CREATE INDEX) | 1–4 | None |
| **Standard** | 4–15 statements, or any destructive/modifying DDL | 1–4 | `ddl-algorithm-matrix.md` |
| **Deep** | >15 statements, or table >10M rows, or multi-step data migration | 1–4 | Both reference files |

**Force Standard or higher** when any signal appears:
column type change, NOT NULL addition, PK modification, FK add/remove, charset change, data backfill, partition change, column rename/removal.

---

## §4 Degradation Modes

When context is incomplete, degrade gracefully — never fabricate information.

| Available context | Mode | What you can do | What you cannot do |
|-------------------|------|-----------------|-------------------|
| Full (version, size, QPS, replicas) | **Full** | All checklist items, precise recommendations | — |
| Version + size known, others unknown | **Degraded** | Full checklist with conservative assumptions | Precise lock-time estimates |
| Only migration SQL, no context | **Minimal** | Static DDL analysis, flag all unknowns | Algorithm version-match, replication assessment |
| No SQL (planning request) | **Planning** | Generate migration plan from requirements | Review existing SQL |

**Hard rule**: Never claim "SAFE" without evidence. In Degraded/Minimal mode, mark items as "SAFE (assumed — verify against production)" and list all assumptions in §9.9 Uncovered Risks.

---

## §5 DDL Safety Checklist

Execute every item for each DDL statement. Mark **SAFE** / **WARN** / **UNSAFE** with evidence.

### 5.1 Algorithm & Lock Assessment

1. **Algorithm selection** — determine `ALGORITHM=INSTANT` / `ALGORITHM=INPLACE` / `ALGORITHM=COPY` for each ALTER TABLE.
   Always specify explicitly; never rely on server default. When uncertain → load `references/ddl-algorithm-matrix.md`.

2. **Lock level** — specify `LOCK=NONE` when possible. If server rejects it → operation is not online → escalate to gh-ost/pt-osc.

3. **MDL contention** — even INSTANT acquires brief metadata lock. Long-running transactions block MDL → DDL queues → all subsequent queries queue. Mitigation: `SET SESSION lock_wait_timeout = 3;` pre-check: `SELECT * FROM information_schema.innodb_trx WHERE trx_started < NOW() - INTERVAL 30 SECOND;`

4. **Replication impact** — MySQL 5.7 replicas apply DDL single-threaded; COPY causes severe lag. Assess: will DDL duration exceed replica lag SLA?

### 5.2 Data Integrity

5. **NOT NULL + DEFAULT safety** — adding NOT NULL to column with existing NULLs → ALTER fails. Use phased approach.

6. **Type change truncation** — narrowing VARCHAR, reducing DECIMAL precision → silent data loss. Widening may change algorithm.

7. **FK cascade risk** — ON DELETE CASCADE on large parent → uncontrolled write amplification. Adding FK triggers full-table validation.

8. **Index write amplification** — each new index costs every INSERT/UPDATE. Check for redundant indexes (prefix of existing composite).

### 5.3 Backward Compatibility

9. **Deployment ordering** — column add → schema first, then app; column remove → app first, then schema; column rename → two-phase with dual-write.

10. **Rollback feasibility** — classify: **reversible** / **reversible-with-data-loss** / **irreversible**. DROP COLUMN = irreversible → require backup.

### 5.4 Operational Safety

11. **Session guards** — every migration session MUST set `lock_wait_timeout` and `innodb_lock_wait_timeout` before DDL.

12. **Disk space** — COPY needs ~2× table size. gh-ost needs ghost table + binlog backlog.

13. **Idempotency** — can migration re-run after partial failure? Use `IF NOT EXISTS` / `IF EXISTS`.

14. **Statement granularity** — prefer one DDL per migration file for atomic rollback. Exception: multiple independent ADD COLUMN can group.

---

## §6 Execution Plan (Standard + Deep)

For non-trivial migrations, decompose into the standard phased pattern:

1. **Phase 1 — Additive schema**: add nullable columns, new indexes (online DDL)
2. **Phase 2 — Backfill**: populate from existing data in PK-ordered batches (see `references/large-table-migration.md` §4)
3. **Phase 3 — App deploy**: deploy code writing to both old and new schema
4. **Phase 4 — Constraints**: add NOT NULL, UNIQUE, or FK after backfill verified
5. **Phase 5 — Cleanup** (separate release): drop old columns, remove dual-write

Each phase requires: **Pre-condition** → **SQL** (with session guards) → **Validation** → **Rollback** → **Go/No-go criteria**.

For tables >10M rows requiring COPY, use gh-ost (default) or pt-osc (if inbound FKs). Details in `references/large-table-migration.md`.

---

## §7 Anti-Examples

### AE-1: Implicit algorithm — trusting server default
```sql
-- WRONG: server may silently choose COPY → outage on large table
ALTER TABLE users ADD COLUMN age INT;
-- RIGHT: explicit algorithm
ALTER TABLE users ADD COLUMN age INT DEFAULT NULL, ALGORITHM=INSTANT;
```

### AE-2: NOT NULL on populated column without phased approach
```sql
-- WRONG: fails if any row has NULL
ALTER TABLE orders ADD COLUMN status VARCHAR(20) NOT NULL;
-- RIGHT: add nullable → backfill → enforce NOT NULL (see §6)
```

### AE-3: DDL without session guards
```sql
-- WRONG: blocks indefinitely if long transaction holds MDL
ALTER TABLE large_table ADD INDEX idx_date (created_at);
-- RIGHT:
SET SESSION lock_wait_timeout = 3;
ALTER TABLE large_table ADD INDEX idx_date (created_at), ALGORITHM=INPLACE, LOCK=NONE;
```

### AE-4: DROP COLUMN without data backup
```sql
-- WRONG: data gone forever
ALTER TABLE users DROP COLUMN legacy_field;
-- RIGHT: backup → wait one release cycle → drop
```

### AE-5: Native COPY on 100M-row table
```sql
-- WRONG: hours of exclusive lock
ALTER TABLE events MODIFY COLUMN payload MEDIUMTEXT;
-- RIGHT: use gh-ost (see references/large-table-migration.md)
```

### AE-6: Style nitpick reported as migration risk
```
-- WRONG: "WARN — column name 'usr_nm' violates naming convention"
-- RIGHT: only flag naming if it causes functional problems
```

Extended anti-examples (AE-7 through AE-13) in `references/migration-anti-examples.md`.

---

## §8 Migration Scorecard

### Critical — any FAIL means overall FAIL

- [ ] Algorithm explicitly specified for every ALTER TABLE (`ALGORITHM=INSTANT|INPLACE|COPY`)
- [ ] Session guards set before every DDL (`lock_wait_timeout`, `innodb_lock_wait_timeout`)
- [ ] Rollback SQL provided for every phase (or irreversibility documented with backup plan)

### Standard — 4 of 5 must pass

- [ ] DDL algorithm matches MySQL version capability (no INSTANT on 5.7 where unsupported)
- [ ] Replication impact assessed for each COPY/INPLACE operation
- [ ] Backward-compatible deployment order (additive before app, removal after app)
- [ ] Backfill uses PK-range batching, not LIMIT/OFFSET
- [ ] Validation SQL provided for each phase

### Hygiene — 3 of 4 must pass

- [ ] Disk space impact estimated for COPY/gh-ost operations
- [ ] Idempotency guards present (`IF NOT EXISTS` / `IF EXISTS`)
- [ ] Post-deploy monitoring checks specified (replication lag, error rate)
- [ ] One DDL per migration file (or grouped ADD COLUMN justified)

**Verdict**: `X/12`; Critical: `Y/3`; Standard: `Z/5`; Hygiene: `W/4`.
PASS requires: Critical 3/3 AND Standard ≥4/5 AND Hygiene ≥3/4.

---

## §9 Output Contract

Every migration review MUST produce these sections. Omit none — write "N/A — [reason]" if inapplicable.

```
### 9.1 Context Gate
| Item | Value | Source |
| MySQL Version | 8.0.32 | SELECT VERSION() |
| ... | ... | ... |

### 9.2 Depth & Mode
[Lite/Standard/Deep] × [review/generate/plan] — [rationale]

### 9.3 Risk Assessment Table
| # | DDL Statement | Algorithm | Lock | Risk | Notes |

### 9.4 Execution Plan (Standard/Deep; "N/A — Lite" for Lite)

### 9.5 Migration SQL (with session guards, explicit algorithms)

### 9.6 Validation SQL

### 9.7 Rollback Plan (per-phase)

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
| Standard or Deep depth | `references/ddl-algorithm-matrix.md` |
| Deep depth, or table >10M rows | `references/large-table-migration.md` |
| Extended anti-example matching | `references/migration-anti-examples.md` |
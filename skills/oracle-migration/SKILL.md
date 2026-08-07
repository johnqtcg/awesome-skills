---
name: oracle-migration
description: >
  Oracle Database schema migration safety reviewer and DDL generator. ALWAYS use when
  writing, reviewing, or planning Oracle schema changes — ALTER TABLE, CREATE/DROP INDEX,
  column type changes, constraint additions, partition DDL, or any DDL touching production
  tables. Covers DDL auto-commit implications, DDL_LOCK_TIMEOUT, DBMS_REDEFINITION for
  online table restructuring, ENABLE NOVALIDATE constraint patterns, global index impact
  from partition DDL, CTAS-based migration, ROWID-range batching, and Flashback recovery.
  Use even for "simple" ADD COLUMN — Oracle DDL issues implicit COMMIT before and after
  execution, making every DDL statement irreversible without manual rollback planning.
---

# Oracle Migration Safety Review

## Quick Reference

| If you need to…                        | Go to                                    |
|----------------------------------------|------------------------------------------|
| Understand what this skill covers      | §1 Scope                                 |
| Check mandatory prerequisites          | §2 Mandatory Gates                       |
| Choose review depth                    | §3 Depth Selection                       |
| Handle incomplete context              | §4 Degradation Modes                     |
| Analyze DDL safety item by item        | §5 DDL Safety Checklist                  |
| Design a phased execution plan         | §6 Execution Plan                        |
| Avoid common migration mistakes        | §7 Anti-Examples                         |
| Score the review result                | §8 Scorecard                             |
| Format review output                   | §9 Output Contract                       |
| Look up DDL lock behavior by operation | `references/oracle-ddl-lock-matrix.md`   |
| Plan a large-table (>10M rows) change  | `references/large-table-migration.md`    |

---

## §1 Scope

**In scope** — schema migration safety for Oracle 12.1 / 12.2 / 19c / 21c / 23ai:

- ALTER TABLE (add/drop/modify column, add/drop constraint, rename, move)
- CREATE / DROP / REBUILD INDEX (including ONLINE)
- Constraint management (FK, CHECK, UNIQUE with ENABLE NOVALIDATE pattern)
- Partition DDL (ADD/DROP/SPLIT/MERGE/EXCHANGE PARTITION, global index impact)
- Data backfill and transformation (CTAS, INSERT /\*+ APPEND \*/, ROWID batching)
- Online table redefinition (DBMS_REDEFINITION)
- Migration file review (Flyway, Liquibase, custom PL/SQL deploy scripts)
- Rollback planning (DDL auto-commits — no transactional DDL rollback)

**Out of scope** — delegate to dedicated skills:

- Query optimization, bind variable tuning, plan stability → `oracle-best-practise`
- Application code changes → `go-code-reviewer` or language-specific reviewer
- Security hardening, privilege management → `security-review`

---

## §2 Mandatory Gates

Execute gates sequentially. Each gate has a **STOP** condition.

### Gate 1: Context Collection

| Item | Why it matters | If unknown |
|------|----------------|------------|
| **Oracle version** — record the *release*, not the family: `12.1` / `12.2` / `19c` / `21c` / `23ai` | 12.1 vs 12.2 is a real gate: `ALTER TABLE … MOVE ONLINE` and `MOVE PARTITION … ONLINE` are **12.2+**. "12c" alone is not an answer | Assume **12.1** (most restrictive) |
| **Edition + licensed options** (EE / SE2 / XE / Cloud tier; Partitioning, Diagnostics Pack) | DBMS_REDEFINITION and every `ONLINE` DDL need EE; partition DDL needs the Partitioning option; AWR/ASH/`DBA_HIST_*` need Diagnostics Pack | Assume **SE2 with no extra options** — see `references/oracle-version-licensing-matrix.md` |
| **Table row count** | Determines online-safe vs DBMS_REDEFINITION threshold | Ask, or estimate via `NUM_ROWS` in `DBA_TABLES` |
| **Table size (data + indexes)** | Large tables need DBMS_REDEFINITION or CTAS | Estimate via `DBA_SEGMENTS` |
| **RAC environment** | DDL coordination across instances; cross-instance invalidation | Assume single-instance |
| **Partitioning scheme** | Partition DDL affects global indexes differently | Check `DBA_PART_TABLES` |
| **Maintenance window** | Some DDL needs exclusive lock window | Assume none (zero-downtime required) |
| **UNDO/TEMP tablespace** | Bulk operations consume UNDO; insufficient space → ORA-30036 | Check `DBA_TABLESPACE_USAGE_METRICS` |

**If database access is available**, run:

```sql
-- Exact release. v$version works on every release; VERSION_FULL/BANNER_FULL are 18c+.
SELECT * FROM v$version;
SELECT version FROM v$instance;
SELECT table_name, num_rows, blocks FROM dba_tables WHERE table_name = '<TABLE>';
SELECT segment_name, bytes/1024/1024 MB FROM dba_segments WHERE segment_name = '<TABLE>';

-- Is the Partitioning option linked in? (enabled ≠ licensed — see below)
SELECT parameter, value FROM v$option WHERE parameter = 'Partitioning';
```

**`v$option` reports what is *installed*, not what is *paid for*.** EE ships Partitioning, Diagnostics Pack and every `ONLINE` DDL enabled regardless of contract, so a plan can be executable and still be a licence violation. Confirm entitlement before recommending an option-gated mitigation, and state the dependency in §9.9.

**STOP**: Cannot determine whether the target is Oracle. Redirect to appropriate skill.

**PROCEED**: At least Oracle version and table name known or conservatively assumed.

### Gate 2: Scope Classification

| Mode | Trigger | Output |
|------|---------|--------|
| **review** | User provides existing migration SQL/script | Safety analysis of provided DDL |
| **generate** | User describes desired schema change | Migration SQL + safety analysis |
| **plan** | User describes goal without specifics | Phased migration plan + rationale |

**STOP**: Request is not migration-related. Redirect to `oracle-best-practise`.

**PROCEED**: Migration intent confirmed.

### Gate 3: Risk Classification

| Risk | Definition | Required action |
|------|-----------|-----------------|
| **SAFE** | Online DDL, brief exclusive lock, small table | DDL_LOCK_TIMEOUT sufficient |
| **WARN** | Extended lock on medium table, or partition DDL with global index impact | Off-peak window + monitoring |
| **UNSAFE** | Table rewrite, >10M rows, or DDL requiring extended exclusive lock | DBMS_REDEFINITION / CTAS + staged rollout |

**STOP**: Any UNSAFE item has no mitigation plan.

**PROCEED**: Every DDL statement has risk level and mitigation.

### Gate 4: Output Completeness

Before delivering output, verify all §9 Output Contract sections present. §9.9 Uncovered Risks must never be empty.

---

## §3 Depth Selection

| Depth | When to use | Gates | References to load |
|-------|-------------|-------|-------------------|
| **Lite** | ≤3 DDL statements, all non-rewriting (ADD nullable column, CREATE INDEX ONLINE) | 1–4 | None |
| **Standard** | 4–15 statements, or any table-rewriting / constraint-enabling DDL | 1–4 | `oracle-ddl-lock-matrix.md` |
| **Deep** | >15 statements, table >10M rows, or multi-step DBMS_REDEFINITION | 1–4 | Both reference files |

**Force Standard or higher** when any signal appears:
column type change, NOT NULL addition, constraint enforcement, partition DDL with global indexes, MOVE/SHRINK operations, column removal, edition/license-dependent features.

---

## §4 Degradation Modes

When context is incomplete, degrade gracefully — never fabricate information.

| Available context | Mode | What you can do | What you cannot do |
|-------------------|------|-----------------|-------------------|
| Full (version, edition, size, RAC, partitioning) | **Full** | All checklist items, precise recommendations | — |
| Version + size known, others unknown | **Degraded** | Full checklist with conservative assumptions | License-specific advice, RAC assessment |
| Only migration SQL, no context | **Minimal** | Static DDL analysis, flag all unknowns | Edition-specific features, UNDO assessment |
| No SQL (planning request) | **Planning** | Generate migration plan from requirements | Review existing SQL |

**Hard rule**: Never claim "SAFE" without evidence. In Degraded/Minimal mode, mark as "SAFE (assumed — verify against production)" and list all assumptions in §9.9.

---

## §5 DDL Safety Checklist

Execute every item. Mark **SAFE** / **WARN** / **UNSAFE** with evidence.

### 5.1 DDL Auto-Commit & Lock Assessment

1. **DDL auto-commit awareness** — Oracle DDL issues implicit COMMIT before and after execution. This means:
   - Any uncommitted DML in the session is committed when DDL runs
   - DDL itself cannot be rolled back via ROLLBACK — it is permanent immediately
   - Failed DDL still commits the pre-DDL implicit COMMIT
   - Every DDL must have a documented manual rollback path

2. **DDL_LOCK_TIMEOUT** — set before every DDL session:
   ```sql
   ALTER SESSION SET DDL_LOCK_TIMEOUT = 3;
   ```
   Without this, DDL fails immediately with ORA-00054 (resource busy) if it cannot acquire an exclusive lock. With timeout, Oracle retries for N seconds. When uncertain about lock behavior → load `references/oracle-ddl-lock-matrix.md`.

3. **Online DDL availability** — Oracle supports ONLINE keyword for some operations (EE only):
   - `CREATE INDEX ... ONLINE` — allows concurrent DML during build
   - `ALTER INDEX ... REBUILD ONLINE` — non-blocking rebuild
   - `ALTER TABLE ... MOVE ONLINE` (12.2+) — non-blocking table reorganization
   - Check edition: ONLINE operations require Enterprise Edition or specific cloud tiers

4. **Partition DDL and global index impact** — partition operations (DROP/SPLIT/MERGE/EXCHANGE PARTITION) can invalidate global indexes. An UNUSABLE global index causes query failures. Mitigation: `UPDATE INDEXES` clause or planned global index rebuild.

### 5.2 Data Integrity

5. **Column modification — classify before you judge.** Oracle's `MODIFY` outcomes are three distinct things, and the common review mistake is calling all of them "a slow rewrite":

   | Change | Outcome on a populated table | Correct verdict |
   |--------|------------------------------|-----------------|
   | Widen `VARCHAR2`/`RAW` length; widen `NUMBER` precision **and** scale together | Allowed. Data-dictionary update — stored row bytes are unchanged | **SAFE** — brief lock. DBMS_REDEFINITION is over-engineering |
   | Narrow a char column | Allowed **only if every existing value fits**, else `ORA-01441` | WARN — pre-check with `MAX(LENGTH(col))` |
   | Decrease `NUMBER` precision/scale, or raise scale without raising precision | **`ORA-01440`** — column must be empty. Fails instantly; data size is irrelevant | UNSAFE — needs DBMS_REDEFINITION / CTAS |
   | Change datatype class (`NUMBER`→`VARCHAR2`, `VARCHAR2`→`DATE`, …) | **`ORA-01439`** — column must be empty | UNSAFE — needs DBMS_REDEFINITION / CTAS |

   The reason a large table needs DBMS_REDEFINITION for the bottom two rows is **not** that `ALTER` would be slow — it is that `ALTER` is *rejected outright*. Never report a widening as a table rewrite; never report an `ORA-01439` case as merely slow.

   Classification depends on the column's **current** type, which a migration file usually does not state. Read it before assigning a risk level:
   ```sql
   SELECT column_name, data_type, data_length, data_precision, data_scale, nullable
   FROM   user_tab_columns WHERE table_name = '<TABLE>' AND column_name = '<COLUMN>';
   ```
   If `USER_TAB_COLUMNS` is not reachable, say so in §9.9 and give the verdict for each possible starting type rather than guessing one.

   Adding `NOT NULL` to a column holding NULLs fails with `ORA-02296` — use the phased approach in AE-10.

6. **Constraint enforcement** — Oracle's two-step pattern:
   ```sql
   ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) ENABLE NOVALIDATE;
   ALTER TABLE orders MODIFY CONSTRAINT fk_user VALIDATE;
   ```
   `ENABLE NOVALIDATE` enforces for new DML but skips validating existing rows. `VALIDATE` then checks existing data without blocking DML.

7. **FK index requirement** — unlike PostgreSQL, Oracle does not require indexes on FK columns, but missing FK indexes cause full table locks during parent table DML. Always create indexes on FK columns.

8. **Sequence and identity impact** — DDL on tables with identity columns or sequence-based defaults may affect sequence continuity. Verify after migration.

### 5.3 Backward Compatibility

9. **Deployment ordering** — column add → schema first, then app; column remove → app first, then schema.

   **Column rename**: `ALTER TABLE t RENAME COLUMN old TO new` has been supported since **Oracle 9i Release 2** and is metadata-only with a brief lock. The database is not the problem — *running application code is*. The instant the rename commits, every deployed SQL statement referencing the old name breaks. Do not rename in place on a live system; use the expand/contract sequence (add new column → dual-write → backfill → cut reads over → `SET UNUSED` old), or front the table with a view that exposes both names during the transition.

10. **Rollback planning** — DDL auto-commits, so there is no `ROLLBACK`. Classify every phase into exactly one of six strategies (§8 scores the *classification*, not the presence of SQL):

    | Strategy | When it applies | Example |
    |----------|-----------------|---------|
    | **abort-before-cutover** | Phase has not yet been switched into the app's read path | stop the backfill; drop the interim table; `ABORT_REDEF_TABLE` |
    | **compensating-DDL** | A DDL exists that restores the prior *structure and data* | `ADD CONSTRAINT` → `DROP CONSTRAINT`; `CREATE INDEX` → `DROP INDEX` |
    | **application-rollback** | Schema stays; the previous app build is redeployed | additive column left in place, app reverted |
    | **roll-forward** | Reversing costs more than fixing forward | half-finished backfill → finish it |
    | **restore / PITR** | Data is gone and no compensating DDL exists | `DROP COLUMN`, destructive `MODIFY` |
    | **irreversible** | No recovery path at any cost — must be stated as such | `DROP UNUSED COLUMNS` after backup expiry |

    A compensating DDL that restores the *shape* but not the *data* is **not** a rollback. `ALTER TABLE … ADD (legacy_email VARCHAR2(255))` after a `DROP COLUMN` recreates an empty column and must be classified `restore / PITR`, never `compensating-DDL`. Writing plausible-looking rollback SQL to satisfy a checklist is the failure mode this taxonomy exists to prevent.

11. **Flashback is not a general DDL undo, and it is not on every edition.** Two independent gates: (a) `FLASHBACK TABLE … TO SCN/TIMESTAMP` **cannot cross a structural DDL** — `DROP COLUMN`, `MODIFY` column, `MOVE`, `TRUNCATE`, `ADD CONSTRAINT` and most partition maintenance are on Oracle's blocking list, so it fails rather than restores; (b) it and Flashback Database are **Enterprise Edition only**, while `SELECT … AS OF` and `… TO BEFORE DROP` work on SE2 — do not treat "Flashback" as one feature. So the structural-DDL safety net is taken **before** the statement runs: a keyed CTAS snapshot, a guaranteed restore point (EE), or a verified backup for PITR — and on SE2 that artefact is effectively the *only* recovery mechanism. Offering Flashback Table as the fallback is a false assurance, worse than admitting there is none, because it gets approved. Decision table in `references/large-table-migration.md` §6; edition rows in `references/oracle-version-licensing-matrix.md` §2.

### 5.4 Operational Safety

12. **DROP COLUMN behavior** — `SET UNUSED` is faster than `DROP COLUMN` on wide tables. `SET UNUSED` is metadata-only and makes the column immediately inaccessible; physical removal via `DROP UNUSED COLUMNS` happens later during maintenance. Note that `SET UNUSED` is *not* a safer rollback story — the column can never be un-unused. It buys a cheaper lock, not reversibility.

13. **UNDO/TEMP space** — bulk operations (CTAS, large backfills, DBMS_REDEFINITION) consume UNDO tablespace. Insufficient UNDO → ORA-30036 (unable to extend undo segment). Check space before starting.

14. **Optimizer statistics** — after bulk inserts, table moves, or partition exchanges, statistics are stale. Run `DBMS_STATS.GATHER_TABLE_STATS` post-migration to prevent plan regression.

15. **Statement granularity** — DDL auto-commits, so each DDL is an atomic irreversible step. Prefer one DDL per migration script for clear rollback mapping.

16. **Standby / Data Guard impact** — `NOLOGGING` CTAS and direct-path loads generate no redo, so the blocks arrive corrupt on every physical standby. A primary protected by Data Guard should be in `FORCE LOGGING` (`SELECT force_logging FROM v$database`), which silently overrides every `NOLOGGING` clause in the plan — so a migration whose runtime estimate assumed `NOLOGGING` speed is wrong. Check before promising a window.

---

## §6 Execution Plan (Standard + Deep)

Standard phased pattern for zero-downtime migration:

1. **Phase 1 — Additive schema**: add nullable columns, create indexes with ONLINE, constraints with NOVALIDATE
2. **Phase 2 — Backfill**: populate new columns in ROWID-range or PK-range batches with periodic COMMIT (see `references/large-table-migration.md` §3)
3. **Phase 3 — App deploy**: deploy code writing to both old and new schema
4. **Phase 4 — Constraint validation**: `MODIFY CONSTRAINT ... VALIDATE`, gather stats
5. **Phase 5 — Cleanup** (separate release): `SET UNUSED` old columns, `DROP UNUSED COLUMNS` during maintenance

Each phase: **Pre-condition** → **SQL** (with DDL_LOCK_TIMEOUT) → **Validation** → **Rollback** → **Go/No-go**.

For tables >10M rows needing restructuring, use DBMS_REDEFINITION (EE) or CTAS+swap. Details in `references/large-table-migration.md`.

---

## §7 Anti-Examples

### AE-1: DDL without DDL_LOCK_TIMEOUT
```sql
-- WRONG: fails immediately with ORA-00054 if any session holds lock
ALTER TABLE orders ADD (tracking_id VARCHAR2(50));
-- RIGHT:
ALTER SESSION SET DDL_LOCK_TIMEOUT = 3;
ALTER TABLE orders ADD (tracking_id VARCHAR2(50));
```

### AE-2: ADD CONSTRAINT without NOVALIDATE
```sql
-- WRONG: validates all rows with exclusive lock — blocks everything on large table
ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id);
-- RIGHT: two-step
ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) ENABLE NOVALIDATE;
ALTER TABLE orders MODIFY CONSTRAINT fk_user VALIDATE;
```

### AE-3: DROP COLUMN on wide high-traffic table
```sql
-- WRONG: physically removes column data — expensive I/O, long lock
ALTER TABLE events DROP COLUMN legacy_data;
-- RIGHT: mark unused now, drop physically later
ALTER TABLE events SET UNUSED COLUMN legacy_data;
-- During maintenance window:
ALTER TABLE events DROP UNUSED COLUMNS;
```

### AE-4: Partition DDL without global index plan
```sql
-- WRONG: global indexes become UNUSABLE after DROP PARTITION
ALTER TABLE logs DROP PARTITION logs_2023_q1;
-- RIGHT: include UPDATE INDEXES clause
ALTER TABLE logs DROP PARTITION logs_2023_q1 UPDATE INDEXES;
```

### AE-5: Monolithic UPDATE on large table
```sql
-- WRONG: single UPDATE locks millions of rows, fills UNDO
UPDATE orders SET status = 'migrated' WHERE status IS NULL;
-- RIGHT: batch by ROWID range with periodic COMMIT (see §6)
```

### AE-6: Style nitpick reported as migration risk
```
-- WRONG: "WARN — column name 'USR_NM' doesn't follow naming convention"
-- RIGHT: only flag naming if it causes functional problems
```

Extended anti-examples (AE-7 through AE-14) in `references/migration-anti-examples.md`.

---

## §8 Migration Scorecard

### Critical — any FAIL means overall FAIL

- [ ] `DDL_LOCK_TIMEOUT` set before every DDL session
- [ ] DDL auto-commit documented: no uncommitted DML in session before DDL
- [ ] Every phase carries a **rollback classification** from the §5.3 item 10 taxonomy — and any phase classified `restore / PITR` or `irreversible` names the concrete pre-DDL artefact (backup, restore point, CTAS snapshot) plus who verified it exists

Scoring the third item: a phase is a **FAIL**, not a pass, if it presents compensating DDL that recreates structure without data (`DROP COLUMN` "rolled back" by `ADD COLUMN`), or if it cites `FLASHBACK TABLE … TO SCN/TIMESTAMP` as the recovery path for a structural DDL. Both read as complete and are not.

### Standard — 4 of 5 must pass

- [ ] Constraints use `ENABLE NOVALIDATE` + `VALIDATE` two-step on tables >100K rows
- [ ] Every column change classified against the §5.2 item 5 table, and DBMS_REDEFINITION/CTAS proposed only for changes Oracle actually rejects (`ORA-01439`/`ORA-01440`) or that genuinely rewrite — a widening reported as a rewrite is a FAIL for this item
- [ ] Backward-compatible deployment order (additive before app, removal after app)
- [ ] Batch operations use ROWID/PK-range with periodic COMMIT, not monolithic DML
- [ ] Validation SQL provided for each phase

### Hygiene — 3 of 4 must pass

- [ ] UNDO/TEMP space assessed for bulk operations
- [ ] `DBMS_STATS.GATHER_TABLE_STATS` planned after bulk changes
- [ ] Post-deploy monitoring specified, with its licence stated — AWR/ASH/`DBA_HIST_*` require **Diagnostics Pack**; if entitlement is unconfirmed, propose the free `V$SQL` / `V$SQLSTATS` baseline instead
- [ ] Global index impact assessed for all partition DDL (and the Partitioning option confirmed licensed)

**Verdict**: `X/12`; Critical: `Y/3`; Standard: `Z/5`; Hygiene: `W/4`.
PASS requires: Critical 3/3 AND Standard ≥4/5 AND Hygiene ≥3/4.

**Absolute safety gate** — overrides the arithmetic. A review is `FAIL` regardless of
score if it recommends an option-gated feature (`ONLINE` DDL, DBMS_REDEFINITION,
partition maintenance, AWR) without stating the edition/licence dependency, or asserts a
recovery path that Oracle does not support. A well-formatted plan that cannot legally or
physically execute is worse than an obviously incomplete one.

---

## §9 Output Contract

Every migration review MUST produce these sections. Write "N/A — [reason]" if inapplicable.

```
### 9.1 Context Gate
| Item | Value | Source |

### 9.2 Depth & Mode
[Lite/Standard/Deep] × [review/generate/plan] — [rationale]

### 9.3 Risk Assessment Table
| # | DDL Statement | Lock Type | Online? | Risk | Notes |

### 9.4 Execution Plan (Standard/Deep; "N/A — Lite" for Lite)

### 9.5 Migration SQL (with DDL_LOCK_TIMEOUT, ONLINE, NOVALIDATE as applicable)

### 9.6 Validation SQL

### 9.7 Rollback Plan (per-phase; all manual since DDL auto-commits)
| Phase | Strategy (abort-before-cutover / compensating-DDL / application-rollback / roll-forward / restore-PITR / irreversible) | Concrete artefact or SQL | Data recoverable? |

### 9.8 Post-Deploy Checks

### 9.9 Uncovered Risks (MANDATORY — never empty)
| Area | Reason | Impact | Follow-up |
```

**Volume rules**:
- UNSAFE: always fully detailed with mitigation
- WARN: up to 10; overflow to §9.9
- SAFE: summary row only
- §9.9 minimum: document all assumptions and edition/license unknowns

**Scorecard summary** (append after §9.9):
```
Scorecard: X/12 — Critical Y/3, Standard Z/5, Hygiene W/4 — PASS/FAIL
Data basis: [full context | degraded | minimal | planning]
```

---

## §10 Reference Loading Guide

| Condition | Load |
|-----------|------|
| Standard or Deep depth | `references/oracle-ddl-lock-matrix.md` |
| Deep depth, or table >10M rows | `references/large-table-migration.md` |
| Extended anti-example matching | `references/migration-anti-examples.md` |
| Any recommendation gated on version, edition, or a licensed option | `references/oracle-version-licensing-matrix.md` |

---

## §11 Deterministic Pre-Check

Before writing the review, run the bundled checker over the migration file. It is a
static analyser, not a substitute for the checklist — it catches the mechanical items
(missing `DDL_LOCK_TIMEOUT`, `ADD CONSTRAINT` without `NOVALIDATE`, partition DDL without
`UPDATE INDEXES`, monolithic DML, unexecutable `DBA_EXTENTS.data_object_id` chunking,
two-statement rename presented as atomic, Flashback misuse) so the review can spend its
attention on the judgement calls it cannot.

```bash
python3 scripts/lint_migration.py path/to/migration.sql --context-rows 25000000 --edition SE2
python3 scripts/lint_migration.py path/to/ --format json     # whole directory
```

Exit codes: `0` clean, `1` findings at or above the fail threshold, `2` usage/IO error.
A finding the checker raises that you intend to waive must be waived **explicitly in
§9.9** with a reason — never silently.
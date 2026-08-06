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
| Run the deterministic checker          | §11 + `scripts/lint_migration.py`       |
| Look up DDL algorithm by operation     | `references/ddl-algorithm-matrix.md`    |
| Plan a large-table (>10M rows) change  | `references/large-table-migration.md`   |

---

## §1 Scope

**Verified — 5.7, 8.0, 8.4** (transcribed from each manual, 2026-08-06). **Assumed — 8.1–8.3, 9.x**:
8.4's rules applied but never confirmed there; 9.x shares 8.4's online-DDL matrix byte for byte, yet
9.1.0 raised the INSTANT row-version ceiling 64→255 without touching it, so matrix identity is not
rule identity — re-check numeric thresholds against the target's manual. **Unverified — 5.6 and
older, past 9.x**: say so in §9.9 rather than answering as if covered. MM028 reports both;
`--fail-on warning` makes either a hard stop.

**In scope** — schema migration safety for InnoDB:

- ALTER TABLE (add/drop/modify column, add/drop index, rename, convert charset); CREATE / DROP INDEX
- Data backfill and transformation migrations
- Table restructuring (partitioning, splitting, merging), foreign key changes
- Migration files **as SQL**: raw `.sql`/`.ddl`, Flyway, golang-migrate. Liquibase only via its SQL changelogs or `liquibase updateSQL` output — XML/YAML/JSON changelogs and programmatic (Go/Java/Python) migrations are not parsed; review the generated SQL and say that is what you did
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
| **Exact MySQL version** (`8.0.28`, not "8.x") | INSTANT gates land at 8.0.12 / 8.0.28 / 8.0.29; replication statements change at 8.0.22 and 8.4. A major version is not enough, and versions outside 5.7 / 8.0 / 8.4 / 9.x are unverified (§1) | Assume 5.7 (most restrictive) |
| **Storage engine** | Only InnoDB supports online DDL | Assume InnoDB; WARN if MyISAM |
| **Table row count** | Determines safe DDL vs tool-based threshold | Ask, or estimate via `SHOW TABLE STATUS` |
| **Table data + index size** | Large tables need gh-ost / pt-osc | Ask, or estimate |
| **Active QPS on table** | High-traffic amplifies MDL contention | Assume high-traffic (conservative) |
| **Replication topology** | DDL on source replicates; COPY causes lag | Assume source-replica with GTID |
| **Maintenance window** | Some operations need low-traffic periods | Assume none (zero-downtime required) |
| **Migration framework** | Flyway/Liquibase/golang-migrate affect rollback | Detect from project files |
| **gh-ost / pt-osc version** (only when recommending one) | `--include-triggers` needs gh-ost ≥1.1.8; `--resume`/`--revert` ≥1.1.9; `--attempt-instant-ddl` ≥1.1.6 | Assume no trigger support; recommend pt-osc if the table has triggers |

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

Risk is **blast radius × duration × reversibility**, not row count alone: a 1M-row table at 20k QPS
is more dangerous than a 50M-row archive nobody writes to. Score each DDL statement across five
axes and take the **highest** band any axis reaches.

| Axis | SAFE | WARN | UNSAFE |
|------|------|------|--------|
| **A. Concurrency** — does the server permit concurrent DML? | INSTANT, or INPLACE + `LOCK=NONE` | INPLACE + `LOCK=SHARED` (writes block) | COPY / `LOCK=EXCLUSIVE`, or the algorithm is unknown |
| **B. Work volume** — does it rewrite the table? | Metadata only, no rebuild | Rebuild under ~1M rows / ~1GB | Rebuild above ~10M rows or ~10GB |
| **C. Write pressure** — QPS on the table during the window | Low traffic, or a maintenance window exists | Moderate, off-peak reachable | High-traffic with no window; MDL queue would cascade |
| **D. Replication** — cost on the replica | Metadata event only | Rebuild the replicas can absorb inside the lag SLA | Rebuild exceeding the lag SLA, or 5.7 single-threaded applier on a large table |
| **E. Reversibility** — see §5.3 | Reversible by a cheap compensating DDL | Reversible with a rebuild, or with bounded data loss | Irreversible without restore (`DROP COLUMN/TABLE`, narrowing type, destructive backfill) |

Row count enters via axis B only, as a proxy for rebuild duration — prefer table size in bytes or a
timed run on a replica. **Any axis UNSAFE → UNSAFE** (no averaging); **two axes WARN → UNSAFE**
unless you name the one you mitigated; axis C or D **unknown** counts as WARN, not SAFE — an
unmeasured hot table is not a cold one.

| Band | Required action |
|------|-----------------|
| **SAFE** | Session guards sufficient |
| **WARN** | Off-peak window + live monitoring + a stated abort trigger |
| **UNSAFE** | gh-ost/pt-osc or a phased plan + staged rollout + reversal path rehearsed on a replica |

**STOP**: Any UNSAFE item has no mitigation plan. Must provide tool-based alternative or phased approach before proceeding.

**PROCEED**: Every DDL statement has a per-axis score, an overall band, and a corresponding mitigation.

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

1. **Algorithm selection** — determine `ALGORITHM=INSTANT`, `ALGORITHM=INPLACE`, or `ALGORITHM=COPY`
   for each ALTER TABLE **against the exact server version**, then state it explicitly. Never rely
   on server default. Load `references/ddl-algorithm-matrix.md` whenever the operation is not a
   plain `ADD COLUMN` or `ADD INDEX`.

   Gates that are wrong more often than not — **the `ALGORITHM=INSTANT` clause itself does not
   exist before 8.0.12**, so 5.7 and 8.0.0–8.0.11 reject it for *every* operation, `SET DEFAULT`
   included; within 8.0.12+, positional `ADD COLUMN` needs 8.0.29+, `RENAME COLUMN` 8.0.28+,
   `DROP COLUMN` 8.0.29+; `DROP COLUMN`
   is INPLACE+`LOCK=NONE` on 5.7 and pre-8.0.29, **never COPY**; extending `VARCHAR` is **never
   INSTANT** and is COPY across the 255/256-**byte** boundary; `ADD FOREIGN KEY` is INPLACE **only
   while `foreign_key_checks=0`**, else COPY. **Exception — partition clauses**:
   `ADD/DROP/REORGANIZE/COALESCE/REBUILD PARTITION` accept only `ALGORITHM=DEFAULT, LOCK=DEFAULT`
   on 5.7, where naming `INPLACE` makes the statement fail. Use matrix §4 for those.

2. **Lock level — the rule below applies to INPLACE and COPY only.** With `ALGORITHM=INSTANT`, **omit the `LOCK` clause or write `LOCK=DEFAULT`; `NONE`, `SHARED` and `EXCLUSIVE` are rejected** — *"Only `LOCK = DEFAULT` is permitted for operations that use `ALGORITHM=INSTANT`."* `ALGORITHM=INSTANT, LOCK=NONE` is a failed statement, not a stronger guarantee.

   For INPLACE/COPY: specify `LOCK=NONE` when the matrix says concurrent DML is permitted. Where it
   is not (`ADD FULLTEXT`/`SPATIAL INDEX`, `CONVERT TO CHARACTER SET`, `DROP PRIMARY KEY` alone,
   adding an `AUTO_INCREMENT` column, and 8.0 `REORGANIZE/COALESCE/REBUILD PARTITION`), the best
   available is `LOCK=SHARED` — **state it explicitly and budget the write outage**, or escalate to
   gh-ost/pt-osc. Omitting the clause turns a planned decision into an unplanned one. Note that
   `INPLACE, LOCK=NONE` still rebuilds the table for `ADD PRIMARY KEY`, `MODIFY … NULL/NOT NULL`,
   and `ROW_FORMAT` changes: online is not free — budget the I/O, ~2× disk, and axis-D lag.

3. **MDL contention — including INSTANT** — all three algorithms can take an exclusive metadata lock. ALTER TABLE reference: *"INSTANT: … An exclusive metadata lock on the table **may be taken briefly during the execution phase** of the operation."* A long-running transaction holds it, the DDL queues, every later query queues behind the DDL — the usual cause of a "safe" change taking a site down, and INSTANT is **not** exempt. Guard every DDL, INSTANT included, with `SET SESSION lock_wait_timeout = 3;` **before** the statement, and pre-check `SELECT * FROM information_schema.innodb_trx WHERE trx_started < NOW() - INTERVAL 30 SECOND;`. (The *What Is New* page's "no metadata locks are taken" is a looser summary than the reference; not licence to skip the guard.)

4. **Replication impact** — MySQL 5.7 replicas apply DDL single-threaded; COPY causes severe lag. Will DDL duration exceed the replica lag SLA?

### 5.2 Data Integrity

5. **NOT NULL + DEFAULT safety** — adding NOT NULL to column with existing NULLs → ALTER fails. Use phased approach.

6. **Type change truncation** — narrowing VARCHAR, reducing DECIMAL precision → silent data loss. Widening may change algorithm.

7. **FK cascade and algorithm risk** — `ON DELETE CASCADE` on a large parent → uncontrolled write amplification. And `ADD FOREIGN KEY` is **COPY unless `foreign_key_checks=0`**: with checks on the server validates every child row and rebuilds the table; with checks off you get INPLACE but an **unvalidated** constraint. There is no online-and-validated option — see `references/migration-anti-examples.md` AE-13.

8. **Index write amplification** — each new index costs every INSERT/UPDATE. Check for redundant indexes (prefix of existing composite).

### 5.3 Backward Compatibility

9. **Deployment ordering** — column add → schema first, then app; column remove → app first, then schema; column rename → two-phase with dual-write.

10. **Reversal path** — MySQL DDL **cannot be rolled back**. Every DDL issues an implicit `COMMIT`
    before and after itself, so `ROLLBACK` after a completed `ALTER` does nothing. 8.0's *atomic
    DDL* is crash-safety for the dictionary + storage change, **not** user-visible undo.

    "Rollback" therefore means one of five concrete things. Name which one applies per phase:

    | Path | Applies to |
    |------|-----------|
    | **Abort before cut-over** | gh-ost/pt-osc runs and phased plans not yet at the switch — free |
    | **Compensating DDL** | Additive changes: drop the column or index you added |
    | **Application revert** | Anything behind dual-write or a feature flag; schema stays |
    | **Roll forward** | Bad backfill or wrong default — fix with another migration |
    | **Restore / PITR** | Irreversible loss: `DROP COLUMN`/`TABLE`, narrowed type, destructive `UPDATE` |

    Classify each phase **reversible** (compensating DDL or app revert), **reversible-with-loss**
    (roll forward; rows written to the dropped structure are gone), or **irreversible** (restore
    only). Never emit a `rollback:` block that cannot restore state — an `ADD COLUMN` offered as the
    rollback for a `DROP COLUMN` recreates an empty column and reads as if recovery happened.

### 5.4 Operational Safety

11. **Session guards** — every migration session MUST set `lock_wait_timeout` and `innodb_lock_wait_timeout` before DDL.

12. **Disk space** — COPY needs ~2× table size. gh-ost needs ghost table + binlog backlog.

13. **Idempotency** — can the migration re-run after partial failure? **MySQL `ALTER TABLE` has no `IF NOT EXISTS` / `IF EXISTS`** for columns or indexes (that is MariaDB); writing it is a parse error. Only `CREATE TABLE`/`DROP TABLE`/`CREATE DATABASE`/`DROP DATABASE` accept it. Achieve idempotency by: the framework's history table (Flyway `flyway_schema_history`, golang-migrate `schema_migrations`); a pre-flight `information_schema.COLUMNS`/`STATISTICS` probe that decides whether to emit the DDL; one DDL per file so a partial failure has an unambiguous resume point; and a recorded checkpoint for batched backfills.

14. **Statement granularity** — one DDL per migration file, so a failure leaves an unambiguous state and the compensating DDL is obvious (there is no transactional rollback — see item 10). Exception: independent `ADD COLUMN`s should be grouped, which also costs one INSTANT row version instead of several.

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
-- RIGHT on 8.0.12+:
ALTER TABLE users ADD COLUMN age INT DEFAULT NULL, ALGORITHM=INSTANT;
-- RIGHT on 5.7 (INSTANT does not exist there; the line above would error out):
ALTER TABLE users ADD COLUMN age INT DEFAULT NULL, ALGORITHM=INPLACE, LOCK=NONE;
```
Explicit only helps when it is also correct for the version.

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

AE-7 through AE-17 in `references/migration-anti-examples.md`: partition-clause algorithm rejection (AE-14), VARCHAR/INSTANT (AE-15), gh-ost mode confusion (AE-16), INSTANT row-version exhaustion (AE-17).

---

## §8 Migration Scorecard

### Critical — any FAIL means overall FAIL

- [ ] Algorithm explicitly specified for every ALTER TABLE (`ALGORITHM=INSTANT|INPLACE|COPY`), **or**
      the statement is a partition clause where the matrix says only `DEFAULT` is accepted
- [ ] Session guards set before every DDL (`lock_wait_timeout`, `innodb_lock_wait_timeout`)
- [ ] Every phase names its reversal path from the §5.3-10 table (abort / compensating DDL / app
      revert / roll forward / restore), with SQL where SQL can actually restore state and an
      explicit backup + retention plan where it cannot

### Standard — 4 of 5 must pass

- [ ] DDL algorithm and lock verified against the **exact server version**, not the major version
      (INSTANT gates at 8.0.12/8.0.28/8.0.29; no INSTANT on 5.7; partition clauses per matrix §4)
- [ ] Replication impact assessed for each COPY/INPLACE operation
- [ ] Backward-compatible deployment order (additive before app, removal after app)
- [ ] Backfill uses PK-range batching, not LIMIT/OFFSET
- [ ] Validation SQL provided for each phase

### Hygiene — 3 of 4 must pass

- [ ] Disk space impact estimated for COPY/gh-ost operations
- [ ] Re-runnable after partial failure — via the framework's history table or an
      `information_schema` pre-check, **not** `IF [NOT] EXISTS`, which `ALTER TABLE` rejects
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

---

## §11 Deterministic Checker

`scripts/lint_migration.py` decides version-gated algorithm/lock questions mechanically. Run it on the migration under review, then reason about what it cannot see.

```bash
python3 scripts/lint_migration.py --mysql-version 8.0.29 path/to/migration.sql   # or a dir
python3 scripts/lint_migration.py --list-checks   # add --format json for machine output
```

29 checks: INSTANT version gates and its **LOCK=DEFAULT-only** rule (MM029), never-INSTANT operations, partition-clause algorithm support, `LOCK=NONE` on write-blocking operations, `ADD FOREIGN KEY` + `foreign_key_checks`, VARCHAR byte-boundary crossing, `IF [NOT] EXISTS` on ALTER, stored-program-only loops, `sql_log_bin`, gh-ost/pt-osc flag misuse, version-correct replication and lock-inspection statements, an unverified target version (MM028), and unread migration carriers (MM030).

Directory mode reads `.sql`, `.ddl`, `.mysql`, `.md`, `.sh`, `.bash`. A file named explicitly is scanned as SQL only if its extension is **unknown**; a known-unparseable carrier (Liquibase XML/YAML/JSON, Go/Java/Python) becomes an **MM030 finding whether named explicitly or found in a directory** — naming it does not make it parseable, and scanning it as SQL reports "clean" about DDL masked inside string values. `--fail-on warning` therefore refuses any input whose DDL nobody read.

**Use it as evidence, not as the review.** It reads statements, not your database, so it cannot decide whether a `MODIFY` changes the type or only nullability (compare `SHOW CREATE TABLE`), the VARCHAR band without both widths, or risk axes B–D. A clean run means "nothing here is rejected outright" — not that the migration is safe.

Three companions, all opt-in: `verify_against_server.sh` runs representative ALTERs against a real (disposable) server and reports any matrix claim it contradicts; `mutation_sweep.py` reintroduces each historical defect and requires the suite to catch it; `run_model_eval.py` grades with-skill vs without-skill responses on a deterministic rubric.

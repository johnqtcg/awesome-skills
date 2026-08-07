# Oracle Version & Licensing Matrix for Migration DDL

Every mitigation this skill can recommend is gated on three independent things:

1. the **release** (`12.1` ≠ `12.2` — this distinction decides real cases),
2. the **edition** (SE2 has no `ONLINE` DDL and no `DBMS_REDEFINITION`),
3. a **separately licensed option** (Partitioning, Diagnostics Pack, …).

A plan can satisfy all the safety rules and still be unusable because the customer does
not have the edition, or unlawful because they have the binary but not the entitlement.
Both outcomes are review failures. State the dependency in §9.9 every time.

---

## 1. Feature availability by release

| Feature | Available from | Notes |
|---------|:-------------:|-------|
| `ALTER TABLE … RENAME COLUMN` | **9.2** | Metadata-only. Any claim that this needs 12c or 23ai is wrong |
| `ADD COLUMN` with `NOT NULL` DEFAULT — metadata-only | 11.1 | Before this, always a rewrite |
| `ADD COLUMN` with nullable DEFAULT — metadata-only | 12.1 | 11.x still rewrites the nullable-default case |
| `DBMS_PARALLEL_EXECUTE` | 11.2 | Supported ROWID chunking; resumable |
| `CREATE INDEX … ONLINE`, `ALTER INDEX … REBUILD ONLINE` | 9i / 9.2 | **EE only** |
| `DROP INDEX … ONLINE`, `ALTER INDEX … UNUSABLE ONLINE` | **12.1** | **EE only** |
| `FINISH_REDEF_TABLE(dml_lock_timeout => …)` | 12.1 | Set it explicitly; see §4 |
| `ALTER TABLE … MOVE ONLINE` | **12.2** | **EE only.** The single most common 12.1-vs-12.2 trap |
| `ALTER TABLE … MOVE PARTITION … ONLINE` | 12.2 | EE only |
| `FETCH FIRST n ROWS ONLY` | 12.1 | Use `ROWNUM` on 11.2 batching scripts |
| `DBMS_SESSION.SLEEP` | 18c | Executable by any user. Older releases need `DBMS_LOCK.SLEEP` **plus an explicit `GRANT EXECUTE ON DBMS_LOCK`** |
| `V$ONLINE_REDEF` (redefinition progress) | 12.2 | Falls back to `DBA_REDEFINITION_STATUS` / task views |

> **"12c" is not a version.** When Gate 1 records only "12c", every 12.2-gated row above
> is unknown, so the conservative reading is 12.1 and `MOVE ONLINE` is off the table.
> Ask for `SELECT version FROM v$instance` before recommending it.

---

## 2. Edition matrix

| Capability | EE | SE2 | XE | Fallback when unavailable |
|------------|:--:|:---:|:--:|---------------------------|
| `CREATE/REBUILD/DROP INDEX … ONLINE` | ✅ | ❌ | ❌ | Maintenance window + `DDL_LOCK_TIMEOUT` |
| `ALTER TABLE … MOVE ONLINE` (12.2+) | ✅ | ❌ | ❌ | CTAS + two-step cutover |
| `DBMS_REDEFINITION` | ✅ | ❌ | ❌ | CTAS + two-step cutover |
| Parallel DML / parallel query | ✅ | ❌ | ❌ | Serial batches; expect longer runtime |
| Partitioning DDL | ➕ option | ❌ | ❌ | No partition-exchange pattern available |
| AWR / ASH / `DBA_HIST_*` | ➕ option | ❌ | ❌ | `V$SQL`, `V$SQLSTATS`, `V$SESSION` sampling |
| Flashback Database / guaranteed restore point | ✅ | ❌ | ❌ | Pre-DDL CTAS snapshot + RMAN backup |
| **Flashback Table** (`TO SCN/TIMESTAMP`) | ✅ | ❌ | ❌ | Pre-DDL CTAS snapshot; RMAN PITR |
| Flashback Version / Transaction Query | ✅ | ❌ | ❌ | Application-level audit trail |
| Flashback Query (`SELECT … AS OF`) | ✅ | ✅ | ✅ | — (plain UNDO read consistency) |
| Flashback Drop (`TO BEFORE DROP`, recycle bin) | ✅ | ✅ | ✅ | — (recycle bin is not a licensed option) |
| Online index *coalesce* / shrink | ✅ | ✅ | ✅ | — |

✅ included · ➕ extra-cost option on top of EE · ❌ not available

**Consequence for SE2 reviews:** every "use `ONLINE`" and every "use
`DBMS_REDEFINITION`" recommendation collapses to the same answer — CTAS plus a quiesced
two-step cutover, in a maintenance window. A review that recommends `ONLINE` DDL without
having established the edition has not actually reviewed anything.

**And the recovery story collapses too.** Do not lump the Flashback features together:
they sit on opposite sides of the edition line. On SE2 you keep `SELECT … AS OF`
(read-only inspection of past data) and `FLASHBACK TABLE … TO BEFORE DROP` (recycle bin),
but you lose **`FLASHBACK TABLE … TO SCN/TIMESTAMP`** and Flashback Database entirely. So
on SE2 the only rollback for a bad *DML* is to read the old rows with a flashback query
and write them back yourself, or restore. Offering "flash the table back" to an SE2 site
is as wrong as offering it after a structural DDL — see §5 of
`references/large-table-migration.md`. Confirm against the Licensing Information manual
for the exact release; when entitlement is unknown, plan the SE2 path.

---

## 3. Separately licensed options

These ship **enabled** in an Enterprise Edition install. `v$option` will report `TRUE`
whether or not they were purchased, so it answers "is it linked in?", never "may we use
it?".

| Option | Gates | What the review must say |
|--------|-------|--------------------------|
| **Partitioning** | `ADD/DROP/SPLIT/MERGE/EXCHANGE/MOVE PARTITION`, partition-exchange loading, local indexes | If unlicensed, the entire partition-DDL section is inapplicable — do not present it as the mitigation |
| **Diagnostics Pack** | AWR, ASH, `DBA_HIST_*`, `V$ACTIVE_SESSION_HISTORY`, EM performance pages | Offer `V$SQL`/`V$SQLSTATS` baselines as the free alternative |
| **Tuning Pack** | SQL Tuning Advisor, SQL Profiles | Needs Diagnostics Pack as a prerequisite |
| **Real Application Testing** | Database Replay, SQL Performance Analyzer | The rigorous way to pre-validate a migration's plan impact — and often unlicensed |
| **Advanced Compression** | `COMPRESS FOR OLTP` on a `MOVE`/redefinition | Basic table compression is free; OLTP compression is not |

```sql
-- Linked in? (necessary, not sufficient)
SELECT parameter, value FROM v$option
WHERE  parameter IN ('Partitioning','Real Application Testing','Advanced Compression');

-- Already being used? DBA_FEATURE_USAGE_STATISTICS is what an audit reads.
-- Prior use is not permission, but unexpected rows here are worth raising.
SELECT name, detected_usages, first_usage_date, last_usage_date
FROM   dba_feature_usage_statistics
WHERE  detected_usages > 0
  AND  name LIKE '%Partitioning%';
```

**Reviewer rule:** never let "the query worked when I tried it" stand in for entitlement.
Ask, and if the answer is unavailable, plan for the unlicensed path and record the
assumption.

---

## 4. `FINISH_REDEF_TABLE` lock behaviour

`dml_lock_timeout` (12.1+, `PLS_INTEGER`) caps how long the final swap waits for pending
DML to commit before it can take its exclusive lock.

| Value | Behaviour | Risk |
|------:|-----------|------|
| `NULL` — **the default** | No cap: wait for pending DML however long that takes | The swap blocks behind a long-running transaction and hangs the cutover with nothing to time it out. This is the default you get by omitting the parameter |
| `0` | Do not wait | Aborts on any concurrent DML — after hours of successful copying |
| small, e.g. `30` | Wait 30s, then fail | **Recommended.** Long enough to ride out normal OLTP, short enough to fail inside the window and be retried |
| `1000000` (max) | Effectively unbounded | Same hang as the default, stated explicitly |

**The danger of the default is a hang, not an abort.** Omitting the parameter does not
make the cutover fail fast — it makes it wait, potentially past the end of the window,
with the interim table's MV log still accumulating. Pass an explicit value sized to the
window every time; that is what makes the default irrelevant.

> Source: the ARPLS `DBMS_REDEFINITION` reference, which gives the signature and the
> `DEFAULT NULL`. Secondary blog posts state "default 0 / NOWAIT" and are wrong — this
> matters because the two defaults fail in *opposite* directions, so a plan written
> against the wrong one has the wrong contingency.

---

## 5. RAC-specific gates

RAC is not just "more instances" for migration purposes:

| Concern | Effect | Required action |
|---------|--------|-----------------|
| Cross-instance library-cache locks | DDL must invalidate cursors on **every** instance; a session on any node holding the object blocks the DDL | Check blockers cluster-wide via `GV$` views, not `V$` |
| `DDL_LOCK_TIMEOUT` | Session-level — set it on the session that runs the DDL, on whichever node that is | Do not assume a service-level default |
| Cursor invalidation storm | Hard-parse spike on all nodes after DDL | Schedule off-peak; gather stats with `no_invalidate => FALSE` deliberately, not by accident |
| Rolling maintenance | An instance restart mid-migration will kill a long backfill | Pin the migration session to one instance via a dedicated service |

```sql
-- Blockers across the whole cluster (V$ shows only the local node)
SELECT inst_id, sid, serial#, username, program
FROM   gv$session s
WHERE  EXISTS (SELECT 1 FROM gv$locked_object lo
               JOIN dba_objects o ON lo.object_id = o.object_id
               WHERE lo.session_id = s.sid AND lo.inst_id = s.inst_id
                 AND o.object_name = '<TABLE>');
```

---

## 6. Data Guard / standby gates

| Concern | Effect | Required action |
|---------|--------|-----------------|
| `FORCE LOGGING` | Silently overrides every `NOLOGGING` clause — runtime estimates built on NOLOGGING speed are wrong | `SELECT force_logging FROM v$database;` before promising a window |
| NOLOGGING with a standby attached | Standby receives unusable blocks; `ORA-01578` on the standby later | Never use NOLOGGING with a physical standby, or plan a standby refresh |
| Redo volume from a large backfill | A multi-GB backfill can saturate the redo transport and grow lag | Throttle batches; watch `V$DATAGUARD_STATS` apply lag during the run |
| Apply lag at cutover | A standby minutes behind is not a viable failover target mid-migration | Confirm lag is near zero before the irreversible step |

```sql
SELECT force_logging, database_role, protection_mode FROM v$database;
SELECT name, value FROM v$dataguard_stats WHERE name LIKE '%lag%';
```

---

## 7. Version/licence checklist before recommending a mitigation

- [ ] Exact release recorded (`12.1`/`12.2`/`19c`/…), not just the family
- [ ] Edition recorded (EE / SE2 / XE / cloud tier)
- [ ] For every `ONLINE` keyword used: EE confirmed **and** the release gate met
- [ ] For `DBMS_REDEFINITION`: EE confirmed; `dml_lock_timeout` passed explicitly
- [ ] For any partition DDL: Partitioning option entitlement confirmed
- [ ] For AWR/ASH monitoring: Diagnostics Pack confirmed, else `V$SQL` alternative given
- [ ] RAC: cluster-wide (`GV$`) blocker check, session pinned to one instance
- [ ] Data Guard: `FORCE LOGGING` checked before any `NOLOGGING` claim
- [ ] Every unconfirmed item above appears in §9.9 as an explicit assumption

# Large Table Migration Patterns

For tables exceeding ~10M rows or ~10GB, `ALGORITHM=COPY` is impractical: it blocks writes for
minutes to hours and replicates as a single DDL event, so every replica repeats the whole rebuild.
Native `INPLACE` with `LOCK=NONE` is *online* but, when it rebuilds the table, still costs full
table I/O and produces replica lag proportional to table size. This reference covers the
tool-based alternatives and the production-safe patterns around them.

> **Provenance.** gh-ost facts are from the upstream repository
> (<https://github.com/github/gh-ost> — `doc/cheatsheet.md`, `doc/command-line-flags.md`,
> release notes) and pt-osc facts from
> <https://docs.percona.com/percona-toolkit/pt-online-schema-change.html>, both verified
> 2026-08-06. Defaults quoted below are upstream defaults, not invented recommendations.

---

## Table of Contents

1. [gh-ost Usage Patterns](#1-gh-ost-usage-patterns)
2. [pt-online-schema-change Usage Patterns](#2-pt-online-schema-change-usage-patterns)
3. [Tool Selection Decision](#3-tool-selection-decision)
4. [Chunked Backfill at Scale](#4-chunked-backfill-at-scale)
5. [Replication-Safe Migration](#5-replication-safe-migration)
6. [Monitoring During Migration](#6-monitoring-during-migration)
7. [Abort and Recovery](#7-abort-and-recovery)

---

## 1. gh-ost Usage Patterns

gh-ost creates a ghost table, replays binlog events into it to stay synchronized, and performs an
atomic cut-over.

### 1.1 Pick the operation mode first — this decides whether `--allow-on-master` is needed

`--allow-on-master` is **not** a companion to `--host=<replica>`. It is the explicit opt-in for
pointing gh-ost **at the master**. Getting this backwards is the most common gh-ost invocation
error.

| Mode | `--host` points at | `--allow-on-master` | When |
|------|--------------------|---------------------|------|
| **a. Connect to replica, migrate on master** (gh-ost's default and recommended mode) | a **replica** | **omit it** | Default choice. gh-ost crawls up to the master, reads binlogs from the replica, writes rows and cuts over on the master |
| **b. Connect to master** | the **master** | **required** | No replicas available, or you accept the extra master load. Master must be `binlog_format=ROW` |
| **c. Migrate/test on replica** | a replica | omit | `--migrate-on-replica` (apply and keep on that replica) or `--test-on-replica` (apply, then stop and leave tables for comparison) |

```bash
# Mode (a) — default. Note: NO --allow-on-master.
gh-ost \
  --host=replica1.db.internal --port=3306 \
  --user=gh-ost --password="$GH_OST_PASSWORD" \
  --database=app --table=events \
  --alter="MODIFY COLUMN user_id BIGINT NOT NULL" \
  --chunk-size=1000 \
  --max-load=Threads_running=25 \
  --critical-load=Threads_running=1000 \
  --max-lag-millis=1500 \
  --throttle-control-replicas="replica1.db.internal:3306,replica2.db.internal:3306" \
  --exact-rowcount --concurrent-rowcount \
  --default-retries=120 \
  --panic-flag-file=/tmp/ghost.panic.flag \
  --postpone-cut-over-flag-file=/tmp/ghost.postpone.flag \
  --serve-socket-file=/tmp/gh-ost.app.events.sock \
  --verbose
  # add --execute to leave dry-run mode
```

```bash
# Mode (b) — only when --host IS the master.
gh-ost --host=master.db.internal --allow-on-master  ... --execute
```

### 1.2 Key flags

| Flag | Purpose | Guidance |
|------|---------|----------|
| `--host` | Server gh-ost connects to and reads binlogs from | A replica in mode (a); the master in mode (b) |
| `--allow-on-master` | Approves operating directly on the master | **Only** in mode (b). Never pair with a replica host |
| `--chunk-size` | Rows per copy iteration | 500–2000; lower for wide rows |
| `--max-load` | Pause when a `SHOW GLOBAL STATUS` counter exceeds a threshold | `Threads_running=25` is the common starting point |
| `--critical-load` | **Abort** when a counter exceeds a threshold | Set high (e.g. `Threads_running=1000`); this is the emergency brake |
| `--max-lag-millis` | Throttle when replica lag exceeds this | 1000–3000 ms |
| `--throttle-control-replicas` | Replicas whose lag gates the migration | All production replicas |
| `--postpone-cut-over-flag-file` | Copy runs to completion, then waits for you to delete the file | **Use it.** Decouples the long copy from the risky cut-over so you choose the cut-over moment |
| `--panic-flag-file` | Creating this file aborts the migration immediately | Give ops a kill switch that needs no socket access |
| `--cut-over` | `atomic` (default) or `two-step` | Leave at default |
| `--exact-rowcount` | Precise ETA at the cost of an initial `COUNT(*)` | Worth it above ~100M rows |
| `--attempt-instant-ddl` | Try native `ALGORITHM=INSTANT` first and exit immediately if it works (gh-ost 1.1.6+) | Cheap win on 8.0 for INSTANT-eligible ALTERs |
| `--include-triggers` | Recreate the original table's triggers on the ghost table at cut-over (gh-ost 1.1.8+) | Required if the table has triggers — see §1.4 |
| `--resume` | Continue an interrupted migration instead of restarting | gh-ost 1.1.9+ |
| `--revert` | Attempt to revert a completed migration; needs `--old-table` | gh-ost 1.1.9+ |
| `--execute` | Actually run. Omitting it is the dry-run | Always dry-run first |

### 1.3 Flags that are deliberately **not** in the template above

| Flag | Why it is not a default |
|------|-------------------------|
| `--initially-drop-ghost-table`, `--initially-drop-old-table` | These drop tables left over from a previous run. Upstream is explicit: *"We think gh-ost should not take chances or make assumptions about the user's tables. Dropping tables can be a dangerous, locking operation. We let the user explicitly approve such operations."* The `_old` table left by a prior run is frequently the **only remaining copy of the pre-migration data** — dropping it unattended destroys your rollback. Investigate leftovers by hand, then pass these flags for one deliberate re-run |
| `--ok-to-drop-table` | Drops the old table after a successful migration. Disabled upstream by default because dropping a large table is a long locking operation. Keep the `_old` table until you have verified the migration and passed your rollback window |
| `--initially-drop-socket-file` | Can delete the socket of a *running* migration |

**Rule:** a destructive convenience flag belongs in the runbook for the specific run that needs it,
never in the copy-paste template.

### 1.4 gh-ost limitations

- **Inbound foreign keys** (other tables' FKs pointing at this table) are not supported. Outbound
  FKs from the migrated table are fine.
- **ROW-based binlog** required on the server gh-ost reads from.
- A **unique key** (PK or unique index) is required, and its columns must not contain NULLs.
- **Triggers**: gh-ost ≥ v1.1.8 (released 2026-03) supports them via `--include-triggers`, which
  recreates the original triggers on the ghost table at cut-over. Older gh-ost refuses tables with
  triggers.
  **Do not drop business triggers to make gh-ost run.** Dropping a trigger silently disables the
  behaviour it implements (audit rows, denormalised counters, FK-substitute enforcement) for the
  whole migration window, and there is no error to tell you data diverged. Upgrade gh-ost, use
  `--include-triggers`, or switch to pt-osc.
- Cut-over takes a brief table lock (~1s) — unavoidable, but bounded, unlike COPY.

Dry-run (omit `--execute`) validates the ALTER syntax, connectivity, binlog format, and unique-key
requirement before anything is copied.

---

## 2. pt-online-schema-change Usage Patterns

pt-osc creates a new table, adds three triggers to the original to capture concurrent writes, copies
in chunks, then swaps by rename.

```bash
pt-online-schema-change \
  --alter="ADD COLUMN new_col INT DEFAULT NULL" \
  --chunk-size=1000 \
  --max-load="Threads_running=25" \
  --critical-load="Threads_running=50" \
  --max-lag=3 \
  --check-interval=1 \
  --recursion-method=processlist \
  --set-vars="lock_wait_timeout=3,innodb_lock_wait_timeout=1" \
  --no-drop-old-table \
  --progress=time,30 \
  --dry-run \
  D=app,t=events
# swap --dry-run for --execute once the dry-run is clean
```

### Key flags (upstream defaults in parentheses)

| Flag | Purpose | Default |
|------|---------|---------|
| `--chunk-size` | Rows per copy iteration | 1000 |
| `--max-load` | Pause when a status counter is above threshold | `Threads_running=25` |
| `--critical-load` | **Abort** when a status counter is above threshold | `Threads_running=50` |
| `--max-lag` | Pause the copy until every replica's lag is below this | `1s` |
| `--check-interval` | Sleep between `--max-lag` checks | `1s` |
| `--recursion-method` | How replicas are discovered | `processlist` or `dsn` |
| `--set-vars` | Session variables for the migration | `wait_timeout=10000, innodb_lock_wait_timeout=1, lock_wait_timeout=60` |
| `--no-drop-old-table` | Keep `_<table>_old` after the swap | Old table **is** dropped by default — pass this to preserve rollback. **Incompatible with `--preserve-triggers`** (§2.1) |
| `--preserve-triggers` | Copy the table's own triggers to the new table | Required when the table has triggers; MySQL 5.7.2+; see §2.1 for what it forbids |
| `--alter-foreign-keys-method` | `auto` / `rebuild_constraints` / `drop_swap` | Required when child tables reference this table |
| `--dry-run` / `--execute` | pt-osc requires one explicitly | — |

**`lock_wait_timeout` default is 60s**, far longer than the 3s this skill requires for hand-run DDL.
Override it via `--set-vars` so a blocked cut-over fails fast instead of queueing queries behind an
MDL wait for a minute.

### pt-osc limitations and traps

- **Trigger-based**: three triggers are added to the source table, so every INSERT/UPDATE/DELETE
  pays overhead for the entire migration. On write-heavy tables this is measurable.
- **A table that already has triggers needs `--preserve-triggers`, and it comes with hard
  constraints** — see §2.1. Without the flag, pt-osc's own triggers and the table's existing ones
  collide.
- **`--null-to-not-null` silently rewrites data.** It permits `MODIFY`ing a nullable column to
  `NOT NULL` by converting existing NULLs to the type's default (`0` for numbers, `''` for
  strings). That is a silent semantic change to production rows. Backfill deliberately instead
  (§4), and treat any migration that passes this flag as UNSAFE.
- `--alter-foreign-keys-method=drop_swap` briefly leaves child tables pointing at nothing; prefer
  `rebuild_constraints` unless a child table is too large.

### 2.1 `--preserve-triggers` — the only pt-osc path for a table that already has triggers

pt-osc adds its own INSERT/UPDATE/DELETE triggers. Before MySQL 5.7.2 a table could hold only one
trigger per event, so any pre-existing trigger made the table un-migratable. From 5.7.2 multiple
triggers per event are allowed, and `--preserve-triggers` copies the table's own triggers onto the
new table before the row copy begins.

Four constraints, all from the upstream documentation, and all easy to discover only at cut-over:

1. **Requires MySQL 5.7.2+.** On older servers there is no path at all.
2. **Mutually exclusive with `--no-drop-triggers`, `--no-drop-old-table`, and `--no-swap-tables`.**
   `--preserve-triggers` must *delete and recreate* the original triggers (trigger names are
   unique), which those flags forbid. **This collides with the rollback advice above**: the
   `--no-drop-old-table` recommended in §2 cannot be combined with `--preserve-triggers`. On a
   trigger-carrying table you must choose between keeping the `_old` rollback copy and preserving
   the triggers — decide it in the runbook, not at the prompt.
3. **Unusable when the `--alter` drops a column a trigger references.** Upstream's own example: a
   trigger reading `OLD.f1` blocks `--alter="DROP COLUMN f1"`, because the recreated trigger would
   fail. Rewrite the trigger first as a separate change.
4. **`--no-swap-tables` leaves the triggers on the original table**, and combined with
   `--no-drop-new-table` they end up duplicated on both, the new copy carrying a random suffix.

The triggers are dropped from the new table during the copy and re-applied at the end, so there is
a window in which the new table is not receiving their side effects — pt-osc's own capture triggers
still replicate the rows, but any behaviour the business trigger implements (audit rows,
denormalised counters) is applied only after the copy completes.

**If the table has triggers, gh-ost ≥1.1.8 with `--include-triggers` is usually the smaller
problem**: it recreates them at cut-over without forcing you to give up the `_old` table.

---

## 3. Tool Selection Decision

```
Is the ALTER INSTANT-eligible on this server version?  (ddl-algorithm-matrix.md)
  ├─ YES → run it natively. No tool needed.
  │        (or let gh-ost try it: --attempt-instant-ddl)
  └─ NO
      │
      Does the table have inbound foreign keys?
        ├─ YES → pt-osc with --alter-foreign-keys-method
        └─ NO
            │
            Does the table have triggers?
              ├─ YES → gh-ost >= 1.1.8 with --include-triggers  (preferred: keeps
              │        the _old rollback copy), else pt-osc --preserve-triggers,
              │        which requires MySQL >= 5.7.2 and FORBIDS --no-drop-old-table
              │        / --no-drop-triggers / --no-swap-tables, and cannot run if the
              │        ALTER drops a column a trigger references (§2.1).
              │        Never drop the triggers to make a tool run.
              └─ NO
                  │
                  Is binlog_format=ROW?
                    ├─ YES → gh-ost (preferred — triggerless, better throttling)
                    └─ NO  → pt-osc (works with any binlog format)
                             Consider switching to ROW for future operations.
```

**When either works, default to gh-ost**: no trigger overhead on the source table, throttling on
both replica lag and server load, cut-over can be postponed to a moment you choose, and the read
load can sit on a replica.

---

## 4. Chunked Backfill at Scale

Batch by primary-key range. `LIMIT/OFFSET` rescans and discards all preceding rows each iteration,
degrading to O(n²).

### 4.1 Plain SQL cannot loop — this is not a style preference

`WHILE … END WHILE`, `REPEAT … END REPEAT`, and `LOOP` are **compound statements usable only inside
a stored program** (procedure, function, trigger, or event). Pasting them into a migration file, a
`mysql` client session, or a Flyway/Liquibase/golang-migrate script is a **syntax error**, not a
slow query. Any backfill "script" shaped like the block below has never been executed:

```sql
-- INVALID outside a stored program — ERROR 1064 near 'WHILE'
WHILE @current_id < @max_id DO
  UPDATE ...;
END WHILE;
```

Two valid options follow. **Prefer the external driver** (§4.3): it can observe replica lag, log
progress, resume after a crash, and be killed cleanly — none of which a stored procedure does well.

### 4.2 Option A — stored procedure (valid, but limited)

```sql
DELIMITER $$
CREATE PROCEDURE backfill_new_col()
BEGIN
  DECLARE v_current BIGINT DEFAULT 0;
  DECLARE v_max     BIGINT DEFAULT 0;

  SET SESSION lock_wait_timeout = 3;
  SET SESSION innodb_lock_wait_timeout = 3;

  SELECT COALESCE(MAX(id), 0) INTO v_max FROM target_table;

  WHILE v_current < v_max DO
    UPDATE target_table
       SET new_col = COALESCE(source_expression, 'default_value')
     WHERE id > v_current
       AND id <= v_current + 1000
       AND new_col IS NULL;

    SET v_current = v_current + 1000;
    DO SLEEP(0.1);
  END WHILE;
END$$
DELIMITER ;

CALL backfill_new_col();
DROP PROCEDURE backfill_new_col;
```

Limits to accept if you choose this: it cannot check replica lag, a `KILL` leaves you with no
progress record, and the whole run is one client connection.

### 4.3 Option B — external driver (recommended)

```go
const batchSize = 1000

func backfill(ctx context.Context, db *sql.DB, startID int64) error {
    var maxID int64
    if err := db.QueryRowContext(ctx, `SELECT COALESCE(MAX(id), 0) FROM target_table`).
        Scan(&maxID); err != nil {
        return fmt.Errorf("read max id: %w", err)
    }

    for lastID := startID; lastID < maxID; lastID += batchSize {
        res, err := db.ExecContext(ctx,
            `UPDATE target_table
                SET new_col = ?
              WHERE id > ? AND id <= ? AND new_col IS NULL`,
            defaultValue, lastID, lastID+batchSize)
        if err != nil {
            return fmt.Errorf("backfill batch at id=%d: %w", lastID, err)
        }
        n, err := res.RowsAffected()
        if err != nil {
            return fmt.Errorf("rows affected at id=%d: %w", lastID, err)
        }

        // Persist progress so an interrupted run resumes here, not at 0.
        if err := recordProgress(ctx, lastID+batchSize, n); err != nil {
            return fmt.Errorf("record progress at id=%d: %w", lastID, err)
        }

        lag, err := checkReplicaLag(ctx)
        if err != nil {
            return fmt.Errorf("check replica lag: %w", err)
        }
        for lag > maxLagThreshold {
            slog.Warn("replica lag above threshold, pausing backfill",
                "lag_seconds", lag, "last_id", lastID)
            select {
            case <-ctx.Done():
                return ctx.Err()
            case <-time.After(5 * time.Second):
            }
            if lag, err = checkReplicaLag(ctx); err != nil {
                return fmt.Errorf("check replica lag: %w", err)
            }
        }

        select {
        case <-ctx.Done():
            return ctx.Err()
        case <-time.After(100 * time.Millisecond):
        }
    }
    return nil
}
```

Sparse primary keys make fixed-width `id` windows do no work for long stretches; if `id` has large
gaps, drive the loop off `SELECT id FROM target_table WHERE id > ? ORDER BY id LIMIT 1 OFFSET 1000`
to find the next boundary, or seek on the last row actually updated.

### 4.4 Backfill tuning

| Parameter | Guidance |
|-----------|----------|
| Batch size | Start at 1000. Reduce if a batch exceeds ~1s or replica lag spikes |
| Sleep between batches | 0.05–0.5s; raise during peak hours |
| Progress tracking | Persist the last completed boundary **outside** the session so an interrupted run resumes |
| Session guards | `lock_wait_timeout=3`, `innodb_lock_wait_timeout=3` on the backfill connection |

### 4.5 `sql_log_bin = 0` is not a backfill default

Disabling the binlog for a backfill means the writes **do not replicate**, and it is occasionally
correct — when you deliberately run the identical backfill on every host, including all replicas,
independently. Everything about that is easy to get wrong:

- It requires `SUPER` (5.7) or `SYSTEM_VARIABLES_ADMIN`-class privileges (8.0), so it often is not
  even available to the migration user.
- Any host you miss is now **permanently divergent** with no error raised.
- The rows are absent from the binlog, so point-in-time recovery replays a database **without** the
  backfill, and GTID-based failover promotes a replica whose data depends on whether the manual run
  reached it.
- It interacts badly with any tool that reads binlogs — gh-ost and pt-osc among them.

Default to leaving the binlog on and letting the backfill replicate, throttled by §4.3's lag check.
If you take the `sql_log_bin=0` path, it needs its own runbook entry naming every host, a
post-run row-count comparison across all of them, and an explicit statement that PITR from before
the backfill will not contain it.

---

## 5. Replication-Safe Migration

### DDL replication behaviour

| Scenario | Behaviour | Risk |
|----------|-----------|------|
| `ALGORITHM=INSTANT` | Replicates as a metadata-only event | Minimal |
| `ALGORITHM=INPLACE`, no rebuild | Single DDL event, metadata only on the replica | Minimal |
| `ALGORITHM=INPLACE`, rebuilds table | Single DDL event; the replica repeats the **whole rebuild** | Lag ≈ rebuild duration. "Online on the source" does not mean online on the replica |
| `ALGORITHM=COPY` | Single DDL event; replica rebuilds the entire table | Severe |
| gh-ost / pt-osc | Ordinary row events spread over the copy | Minimal, and throttleable |

MySQL 5.7 replicas apply DDL on a single applier thread, so a rebuild serialises behind everything
else in the stream.

### Version-correct replication statements

Replication statement names changed in 8.0.22 and the old ones were **removed** in 8.4. Using the
wrong one is a hard error, not a warning.

| Server | Status statement | Lag column |
|--------|------------------|------------|
| 5.7 | `SHOW SLAVE STATUS \G` | `Seconds_Behind_Master` |
| 8.0.0–8.0.21 | `SHOW SLAVE STATUS \G` | `Seconds_Behind_Master` |
| 8.0.22–8.0.x | `SHOW REPLICA STATUS \G` (`SHOW SLAVE STATUS` still works, deprecated) | `Seconds_Behind_Source` |
| 8.4+ | `SHOW REPLICA STATUS \G` (`SHOW SLAVE STATUS` **removed**) | `Seconds_Behind_Source` |

```sql
-- Binlog format (ROW required for gh-ost) — all versions
SHOW VARIABLES LIKE 'binlog_format';

-- GTID state — all versions
SHOW VARIABLES LIKE 'gtid_mode';
SHOW VARIABLES LIKE 'enforce_gtid_consistency';
-- With GTID on, DDL must be GTID-compatible (no CREATE TABLE ... SELECT).
```

### Lag thresholds

Define before starting: warn and throttle above 3s, abort and investigate above 30s, sample every
5s. Encode these as `--max-lag-millis` (gh-ost) or `--max-lag` (pt-osc) rather than watching a
dashboard.

---

## 6. Monitoring During Migration

### Lock inspection — the interface differs by version

`performance_schema.data_locks` and `data_lock_waits` are **8.0+**. On 5.7 the equivalents are
`INFORMATION_SCHEMA.INNODB_LOCKS` and `INNODB_LOCK_WAITS`.
`performance_schema.metadata_locks` and `information_schema.innodb_trx` exist on both.

```sql
-- Row/data locks — MySQL 8.0+
SELECT * FROM performance_schema.data_locks WHERE OBJECT_NAME = '<table>' \G

-- Row locks — MySQL 5.7
SELECT * FROM INFORMATION_SCHEMA.INNODB_LOCKS \G
SELECT * FROM INFORMATION_SCHEMA.INNODB_LOCK_WAITS \G
```

```sql
-- Metadata-lock waiters — 5.7 and 8.0 (needs the P_S mdl instrument enabled)
SELECT OBJECT_TYPE, OBJECT_SCHEMA, OBJECT_NAME, LOCK_TYPE, LOCK_STATUS, OWNER_THREAD_ID
FROM performance_schema.metadata_locks
WHERE OBJECT_NAME = '<table>';

-- Long-running transactions, the usual MDL blockers — 5.7 and 8.0
SELECT trx_id, trx_started, trx_mysql_thread_id, trx_query, trx_rows_locked
FROM information_schema.innodb_trx
WHERE trx_started < NOW() - INTERVAL 30 SECOND;
```

```bash
# gh-ost progress / control
echo "status" | nc -U /tmp/gh-ost.<db>.<table>.sock
# pt-osc prints progress on stdout at the --progress interval
```

### Alerting during migration

Replica lag above the warning threshold; deadlocks on the target table; lock-wait timeouts; disk
above 80% (both tools create a full second copy); connection-count spikes, which are the visible
symptom of MDL contention.

---

## 7. Abort and Recovery

### gh-ost

```bash
# Abort immediately
echo "panic" | nc -U /tmp/gh-ost.<db>.<table>.sock
# or create the file passed to --panic-flag-file
# or Ctrl+C the process

# Inspect leftovers BEFORE deleting anything — _gho may hold hours of copied
# work that --resume can continue, and _del/_old may be your only pre-migration copy.
SHOW TABLES LIKE '\_%\_gho';
SHOW TABLES LIKE '\_%\_ghc';
SHOW TABLES LIKE '\_%\_del';

# Only after you have confirmed they are unwanted:
DROP TABLE IF EXISTS _<table>_gho;
DROP TABLE IF EXISTS _<table>_ghc;
DROP TABLE IF EXISTS _<table>_del;
```

### pt-osc

```bash
# Ctrl+C; triggers are dropped automatically on a clean exit.
# After an unclean abort, check and clean up by hand:
SHOW TRIGGERS WHERE `Table` = '<table>';
DROP TRIGGER IF EXISTS pt_osc_<db>_<table>_ins;
DROP TRIGGER IF EXISTS pt_osc_<db>_<table>_upd;
DROP TRIGGER IF EXISTS pt_osc_<db>_<table>_del;
DROP TABLE IF EXISTS _<table>_new;
```

Leftover pt-osc triggers keep writing into a `_new` table that nothing reads. They are pure write
overhead and must be removed, but confirm no migration is running first.

### Resuming and reverting

| Situation | Action |
|-----------|--------|
| gh-ost interrupted mid-copy, ghost table intact | `--resume` (gh-ost 1.1.9+) continues instead of recopying |
| gh-ost interrupted, resume unavailable | Re-run from scratch. Drop leftovers **only** after confirming they hold nothing you need |
| gh-ost migration completed, needs undoing | `--revert` with `--old-table` (gh-ost 1.1.9+), if the `_old` table still exists — which requires that you did **not** pass `--ok-to-drop-table` |
| pt-osc interrupted | Re-run from scratch; pt-osc does not resume |
| Backfill interrupted | Resume from the persisted boundary (§4.3) |

**The `_old` table is the rollback plan for a completed tool migration.** Keeping it until the
verification window closes is what makes a post-cut-over revert possible at all.

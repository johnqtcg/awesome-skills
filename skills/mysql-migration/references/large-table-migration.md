# Large Table Migration Patterns

For tables exceeding ~10M rows or ~10GB, native DDL with ALGORITHM=COPY is impractical:
it holds locks for minutes to hours, causes severe replication lag, and risks timeout failures.
This reference covers tool-based alternatives and production-safe patterns.

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

gh-ost (GitHub Online Schema Change) performs schema changes by creating a ghost table,
streaming binlog events to keep it synchronized, and performing an atomic cut-over.

### Basic invocation

```bash
gh-ost \
  --host=replica-host \
  --allow-on-master \
  --database=mydb \
  --table=target_table \
  --alter="ADD COLUMN new_col INT DEFAULT NULL" \
  --chunk-size=1000 \
  --max-lag-millis=1500 \
  --throttle-control-replicas="replica1:3306,replica2:3306" \
  --exact-rowcount \
  --concurrent-rowcount \
  --initially-drop-ghost-table \
  --initially-drop-old-table \
  --execute
```

### Key flags explained

| Flag | Purpose | Recommended value |
|------|---------|-------------------|
| `--host` | Read binlog from this host (replica preferred) | Replica address |
| `--allow-on-master` | Apply changes on the source server | Always include when `--host` is a replica |
| `--chunk-size` | Rows per copy iteration | 500–2000 (tune by row width) |
| `--max-lag-millis` | Pause migration if replica lag exceeds this | 1000–3000ms |
| `--throttle-control-replicas` | Replicas to monitor for lag | All production replicas |
| `--cut-over` | Cut-over method: `atomic` (rename) or `two-step` | Default `atomic` is fine for most cases |
| `--exact-rowcount` | Calculate precise ETA | Use for >100M rows |
| `--initially-drop-ghost-table` | Clean up leftover ghost tables from prior failed runs | Yes |
| `--initially-drop-old-table` | Clean up leftover _old tables | Yes |
| `--execute` | Actually run (omit for dry-run) | Omit first to validate |

### Dry-run first

Always run without `--execute` first to validate:
- ALTER syntax is correct
- Connection to replica works
- Binlog format is ROW (required)
- Table has a unique key (required for row identification)

### gh-ost limitations

- Cannot migrate tables with **foreign keys pointing TO the table** (inbound FKs)
  - Outbound FKs from the table are OK
- Requires **ROW-based binlog** (not STATEMENT or MIXED)
- Requires a **unique key** on the table (primary key or unique index)
- **Triggers on the table** must be removed before migration (gh-ost doesn't support tables with triggers)
- During cut-over, there is a brief lock (~1 second) — this is unavoidable but much shorter than COPY

---

## 2. pt-online-schema-change Usage Patterns

pt-online-schema-change (Percona Toolkit) uses triggers to capture changes during migration.

### Basic invocation

```bash
pt-online-schema-change \
  --alter="ADD COLUMN new_col INT DEFAULT NULL" \
  --execute \
  --chunk-size=1000 \
  --max-lag=3 \
  --check-interval=1 \
  --recursion-method=processlist \
  --progress=time,30 \
  D=mydb,t=target_table
```

### Key flags

| Flag | Purpose | Recommended value |
|------|---------|-------------------|
| `--chunk-size` | Rows per copy iteration | 500–2000 |
| `--max-lag` | Pause if replica lag (seconds) exceeds this | 2–5 seconds |
| `--check-interval` | How often to check replica lag | 1–5 seconds |
| `--recursion-method` | How to find replicas | `processlist` or `dsn` |
| `--set-vars` | Session variables for the migration | `lock_wait_timeout=3` |
| `--no-drop-old-table` | Keep old table after migration (for safety) | Use if you want manual cleanup |
| `--progress` | Progress reporting interval | `time,30` (every 30 seconds) |

### pt-osc limitations

- **Trigger-based**: adds 3 triggers (INSERT, UPDATE, DELETE) to the source table
  - These triggers add overhead to every DML operation during migration
  - If the table already has triggers, pt-osc may conflict
- **Trigger overhead**: high-write tables may see noticeable write latency increase
- Better FK support than gh-ost: can handle tables with inbound foreign keys via `--alter-foreign-keys-method`

---

## 3. Tool Selection Decision

```
Does the table have inbound foreign keys?
  ├─ YES → pt-online-schema-change
  │        (gh-ost cannot handle inbound FKs)
  └─ NO
      │
      Is binlog format ROW?
        ├─ YES → gh-ost (preferred — triggerless, better throttling)
        └─ NO → pt-online-schema-change (works with any binlog format)
              Note: consider switching to ROW format for future operations
```

**When either works (common case):** default to **gh-ost** because:
- No trigger overhead on the source table
- Better built-in throttling (replication lag + system load)
- Safer cut-over (can be paused and postponed)
- Read load can be directed to a replica

---

## 4. Chunked Backfill at Scale

For data migration (populating new columns, transforming data), batch processing by
primary key range is essential. LIMIT/OFFSET rescans earlier rows each iteration and
degrades to O(n²) on large tables.

### Production-grade backfill script (SQL)

```sql
-- Setup: use a dedicated session with conservative settings
SET SESSION lock_wait_timeout = 3;
SET SESSION innodb_lock_wait_timeout = 3;
SET SESSION sql_log_bin = 0;  -- skip binlog if backfill will be run on each replica independently

SET @batch_size = 1000;
SET @sleep_seconds = 0.1;
SET @max_id = (SELECT MAX(id) FROM target_table);
SET @current_id = 0;

WHILE @current_id < @max_id DO
  UPDATE target_table
  SET new_col = COALESCE(source_expression, default_value)
  WHERE id > @current_id
    AND id <= @current_id + @batch_size
    AND new_col IS NULL;

  SET @current_id = @current_id + @batch_size;
  DO SLEEP(@sleep_seconds);
END WHILE;
```

### Backfill tuning parameters

| Parameter | Guidance |
|-----------|----------|
| **Batch size** | Start at 1000; decrease if transactions take >1s or replica lag spikes |
| **Sleep between batches** | 0.05–0.5s; increase during peak hours |
| **sql_log_bin** | Set to 0 only if backfill runs on each replica independently; otherwise keep 1 |
| **Progress tracking** | Log `@current_id` periodically so you can resume after interruption |

### Backfill via application code (Go example)

```go
const batchSize = 1000
var lastID int64 = 0

for {
    result, err := db.ExecContext(ctx,
        `UPDATE target_table
         SET new_col = ?
         WHERE id > ? AND id <= ? AND new_col IS NULL`,
        defaultValue, lastID, lastID+batchSize)
    if err != nil {
        return fmt.Errorf("backfill batch at id=%d: %w", lastID, err)
    }

    affected, _ := result.RowsAffected()
    if affected == 0 && lastID >= maxID {
        break
    }

    lastID += batchSize
    time.Sleep(100 * time.Millisecond) // throttle

    // Monitor replica lag
    if lag := checkReplicaLag(); lag > maxLagThreshold {
        log.Warn("replica lag high, pausing backfill", "lag", lag)
        time.Sleep(5 * time.Second)
    }
}
```

---

## 5. Replication-Safe Migration

### DDL replication behavior

| Scenario | Behavior | Risk |
|----------|----------|------|
| ALGORITHM=INSTANT | Replicates instantly (metadata only) | Minimal lag |
| ALGORITHM=INPLACE | Replicates as single DDL event; replica applies inline | Moderate lag for large tables |
| ALGORITHM=COPY | Replicates as single DDL event; replica rebuilds entire table | Severe lag |
| gh-ost | DML events (INSERT/UPDATE/DELETE on ghost table) replicate normally | Minimal lag (spread over time) |
| pt-osc | Trigger-generated DML replicates normally | Minimal lag (spread over time) |

### Pre-migration replication checks

```sql
-- Check current replica lag
SHOW REPLICA STATUS \G
-- Look for: Seconds_Behind_Source, Relay_Log_Space, Read_Source_Log_Pos

-- Verify binlog format (required for gh-ost)
SHOW VARIABLES LIKE 'binlog_format';
-- Must be ROW for gh-ost

-- Check GTID status
SHOW VARIABLES LIKE 'gtid_mode';
SHOW VARIABLES LIKE 'enforce_gtid_consistency';
-- If GTID is ON: DDL must be GTID-compatible (no CREATE TABLE ... SELECT)
```

### Lag threshold and abort criteria

Define before starting:
- **Warning threshold**: lag > 3 seconds → pause and throttle
- **Abort threshold**: lag > 30 seconds → stop migration, investigate
- **Monitoring interval**: check every 5 seconds during migration

---

## 6. Monitoring During Migration

### Essential queries to run periodically

```sql
-- Replica lag (run on replica)
SHOW REPLICA STATUS \G

-- Active locks on the target table
SELECT * FROM performance_schema.data_locks
WHERE OBJECT_NAME = '<table>' \G

-- Metadata lock waiters
SELECT * FROM performance_schema.metadata_locks
WHERE OBJECT_NAME = '<table>' \G

-- Long-running transactions (MDL blockers)
SELECT trx_id, trx_started, trx_query, trx_rows_locked
FROM information_schema.innodb_trx
WHERE trx_started < NOW() - INTERVAL 30 SECOND;

-- gh-ost progress (if using gh-ost)
-- Check the changelog table or the unix socket:
echo "status" | nc -U /tmp/gh-ost.<db>.<table>.sock

-- pt-osc progress (if using pt-osc)
-- Observe STDOUT output; progress is printed at configured interval
```

### Alerting during migration

Set up alerts for:
- Replica lag > warning threshold
- Deadlocks on the target table
- Lock wait timeouts
- Disk usage > 80% (gh-ost and pt-osc create temporary tables)
- Connection count spike (MDL contention indicator)

---

## 7. Abort and Recovery

### gh-ost abort

```bash
# Graceful abort (cleans up ghost table):
echo "panic" | nc -U /tmp/gh-ost.<db>.<table>.sock

# Or: Ctrl+C the gh-ost process; it drops the ghost table by default

# If ghost table remains after abort:
DROP TABLE IF EXISTS _<table>_gho;
DROP TABLE IF EXISTS _<table>_ghc;
DROP TABLE IF EXISTS _<table>_del;
```

### pt-osc abort

```bash
# Ctrl+C the pt-osc process
# Triggers are dropped automatically on clean exit
# If triggers remain after unclean abort:
SHOW TRIGGERS WHERE `Table` = '<table>';
DROP TRIGGER IF EXISTS pt_osc_<db>_<table>_ins;
DROP TRIGGER IF EXISTS pt_osc_<db>_<table>_upd;
DROP TRIGGER IF EXISTS pt_osc_<db>_<table>_del;
# Drop the temporary table:
DROP TABLE IF EXISTS _<table>_new;
```

### Resume after failure

- **gh-ost**: re-run the same command with `--initially-drop-ghost-table` and `--initially-drop-old-table`; it starts fresh (does not resume from last position)
- **pt-osc**: similarly re-run; it starts fresh
- **Backfill scripts**: use the `@current_id` progress tracking to resume from the last completed batch
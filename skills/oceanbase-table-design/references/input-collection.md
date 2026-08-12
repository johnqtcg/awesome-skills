# Input Collection: Workload Contract and Collection SQL

This Skill treats `frequency_share` / `distinct_count` / `top1_key_share` /
`top_n_sql` as hard-required inputs, and forbids making up values. **That means a way
to obtain the data must be provided** — setting up a gate without a way through it
just leaves the user stuck at Step 1, or tempted to simply fabricate a number to get
past it, which is worse than having no gate at all.

This file carries two things at once:

1. **§1 Input contract**: the complete form to fill in at Step 1 (SKILL.md only
   inlines "which fields are required, and what to do if missing").
2. **§2–§5 Collection SQL**: which view each field is drawn from, when a database
   connection is available.

<!-- toc -->

**Table of Contents**

- [1. Workload Input Contract (the Step 1 Form)](#1-workload-input-contract-the-step-1-form)
- [2. Access Patterns and `frequency_share`: `GV$OB_SQL_AUDIT`](#2-access-patterns-and-frequency_share-gvob_sql_audit)
- [3. Partition Key Statistics: `distinct_count` and `top1_key_share`](#3-partition-key-statistics-distinct_count-and-top1_key_share)
- [4. Queuing Table Detection: `delete_qps` and `steady_row_count`](#4-queuing-table-detection-delete_qps-and-steady_row_count)
- [5. Capacity Reconciliation: Actual Tablet Count vs. Tenant Limit](#5-capacity-reconciliation-actual-tablet-count-vs-tenant-limit)
- [6. Graceful Degradation When Data Is Unavailable](#6-graceful-degradation-when-data-is-unavailable)

<!-- /toc -->

## 1. Workload Input Contract (the Step 1 Form)

```yaml
workload:
  entities:
    - name:
      write_qps:
      delete_qps:              # needed to identify a queuing table
      read_qps:
      data_size_gb:
      row_size_bytes:
      steady_row_count:        # steady-state row count; a large gap vs. cumulative writes suggests a queuing table
      growth_gb_per_month:

  access_patterns:
    - name:
      type: point | range | aggregation
      filter:
      order_by:
      limit:
      frequency_share:         # numeric share; sums to 1 within the same entity
      latency_sensitive: yes | no
      scan_width_ratio:        # columns scanned / total columns in the table
      query_shape: aggregation_only | multidim
      read_hot_single_key: yes | no   # whether the same row is read repeatedly (a config-table/routing-table trait, see hotspots.md)

  partition_key_candidates:
    - column:
      distinct_count:          # cardinality (NDV)
      top1_key_share:          # share of the largest key → the sole quantitative entry point for skew and hotspot detection

  transactions:
    - name:
      tables: []
      type: single | multi
      frequency_share:

  analysis:
    analysis_freq: realtime | daily | weekly | monthly | none
    isolation_required: yes | no

  constraints:
    strong_consistency:
    latency_sensitive:
    sla:                       # fill in if there is one; it's the basis for "can this design be rejected" downstream
```

Hard requirements:

- **Do not substitute "high/medium/low" for `frequency_share`**; a qualitative input
  cannot support the quantitative judgments that follow.
- When `distinct_count` / `top1_key_share` are missing, the hotspot and skew
  conclusions can only be output as `unverified`.
- Making up values is not allowed. If the data can't be obtained, mark it missing,
  provide the matching collection SQL from this file, and ask for the results.

## 2. Access Patterns and `frequency_share`: `GV$OB_SQL_AUDIT`

OceanBase has no view that directly labels "hotspot tables"; the official
recommendation is to locate them by aggregating the audit view `GV$OB_SQL_AUDIT`
(source: the official "Hotspot Table Best Practices"). The query below is the official
"Top 10 rows read per unit time" query — the root cause of a read hotspot is usually
right there in it:

```sql
SELECT /*+READ_CONSISTENCY(WEAK), QUERY_TIMEOUT(100000000)*/
  svr_ip, sql_id, tenant_name, db_name,
  COUNT(*) executions,
  MAX(event) event,
  SUM(retry_cnt) retry_cnt,
  ROUND(AVG(elapsed_time)) elapsed_time,
  ROUND(AVG(return_rows)) return_rows,
  SUM(memstore_read_row_count + ssstore_read_row_count) AS total_row_count
FROM GV$OB_SQL_AUDIT
WHERE is_inner_sql = 0
GROUP BY svr_ip, sql_id
ORDER BY total_row_count DESC
LIMIT 10;
```

Mapping from view fields to this Skill's inputs:

| View field | Use |
|---|---|
| `COUNT(*) executions` | Divide by the sum of executions across all SQL for the same entity = `frequency_share` |
| `total_row_count` (`memstore_read_row_count + ssstore_read_row_count`) | Locating a **read** hotspot; far higher than `return_rows` indicates scan amplification (usually pruning isn't taking effect) |
| `retry_cnt` | Elevated values point to lock contention → a **write** hotspot |
| `event` | Row-lock-wait type events point directly to a write hotspot |
| `elapsed_time` | Cross-reference against `latency_sensitive` |

Key points:

- **`GV$` is a cluster-level view**; the `svr_ip` dimension also reveals whether
  Leaders are concentrated on one node (the entry point for `leader_skew`).
- The audit view is an **in-memory ring buffer** that only covers a recent window of
  time. To use it as the basis for `frequency_share`, you must state the sampling
  window; if the window does not cover the business's peak traffic, mark the
  conclusion `unverified`.
- The official docs offer two more paths: OCP's hotspot-table monitoring panel (no SQL
  needed, shows trends); and `sql_diagnoser` custom-rule batch export (example rule
  `count > 100 AND elapsed_time > 100000`), after which a script extracts table names
  from the SQL text to tally frequency.

## 3. Partition Key Statistics: `distinct_count` and `top1_key_share`

These two numbers are **not in any system view** — they must be queried directly on
the business table. This is the sole quantitative source for Step 7's hotspot
classification and Step 3's `ndv_vs_partition_count` check:

```sql
-- Cardinality (NDV)
SELECT COUNT(DISTINCT <part_key>) AS distinct_count FROM <table>;

-- Share of the largest key: top1_key_share
SELECT <part_key>,
       COUNT(*) AS cnt,
       COUNT(*) / (SELECT COUNT(*) FROM <table>) AS top1_key_share
  FROM <table>
 GROUP BY <part_key>
 ORDER BY cnt DESC
 LIMIT 5;                       -- take the top few, so you can see the shape of the skew, not just one number
```

A full-table `COUNT(DISTINCT)` on a large table is expensive; two alternative paths:

- Use the NDV from the optimizer's statistics (provided the statistics are fresh;
  stale statistics give an NDV that will mislead the judgment):
  ```sql
  SELECT column_name, num_distinct, num_nulls
    FROM oceanbase.DBA_TAB_COL_STATISTICS
   WHERE table_name = '<TABLE>';
  ```
- Sampling: `SELECT ... FROM <table> SAMPLE(1)`, and note in the output that this is a
  sampled value.

The judgment baseline is `1 / partition_count`: `top1_key_share` clearly above that
value counts as skew (see `hotspots.md`).

## 4. Queuing Table Detection: `delete_qps` and `steady_row_count`

```sql
-- Steady-state row count
SELECT COUNT(*) FROM <table>;

-- The DML mix on this table (an approximate delete/insert ratio)
SELECT sql_id, COUNT(*) executions, SUM(affected_rows) affected_rows
  FROM GV$OB_SQL_AUDIT
 WHERE is_inner_sql = 0 AND UPPER(query_sql) LIKE '%<TABLE>%'
 GROUP BY sql_id
 ORDER BY executions DESC;
```

Criterion (see `storage-format.md` §5): `delete_qps` on the same order of magnitude as
`insert_qps`, with a steady-state row count far smaller than cumulative writes →
judged a queuing table.

## 5. Capacity Reconciliation: Actual Tablet Count vs. Tenant Limit

```sql
-- Actual Tablet count (used to reconcile against estimate_tablets.py's estimate)
SELECT TABLE_NAME, TABLE_TYPE, COUNT(*) AS tablet_cnt
  FROM oceanbase.DBA_OB_TABLETS
 GROUP BY TABLE_NAME, TABLE_TYPE;

-- Tenant resource limit (treat LIMIT_VALUE as authoritative, better than any formula-based estimate)
SELECT * FROM oceanbase.GV$OB_TENANT_RESOURCE_LIMIT;

-- Tenant spec (Step 0's unit_memory_gb / unit_num)
SELECT * FROM oceanbase.DBA_OB_UNITS;

-- Tenant defaults for storage format and table organization (must be obtained at Step 0, see capability-matrix.md §2.1)
SHOW PARAMETERS LIKE '%store_format%';
SHOW PARAMETERS LIKE '%default_table_organization%';
SHOW PARAMETERS LIKE '%auto_split%';
```

A deviation greater than 10% indicates the estimate missed an object (usually indexes
weren't counted); see `tablet-capacity.md` §1.

## 6. Graceful Degradation When Data Is Unavailable

Handle it as an honest degradation — you **must not** pass off a "typical value" as a
measured value:

| Missing item | Consequence | Output requirement |
|---|---|---|
| `frequency_share` | Cannot rank the primary access pattern | Mark `dominant_patterns` `unverified`; you can still propose a design, but must state "ranked under which assumption" |
| `distinct_count` | Cannot judge `ndv_vs_partition_count` | That check is `unverified`, with the §3 SQL provided |
| `top1_key_share` | Cannot judge skew or hotspot classification | `hotspot.result = unverified`; outputting "no hotspot" is forbidden |
| Tenant spec | Cannot compute the Tablet limit | `tablet_capacity.result = unverified` |
| Cannot connect to the database (offline design) | All of V2–V5 cannot be run | List every assumed value at the top, mark all related `checks` `unverified`, and attach this file's collection checklist as a deliverable |

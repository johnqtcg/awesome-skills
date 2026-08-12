# Partition Design: Type Selection, Automatic Partitioning, Lifecycle Management

<!-- toc -->

**Table of Contents**

- [1. Partition type selection (must pass the mode gate first)](#1-partition-type-selection-must-pass-the-mode-gate-first)
  - [1.1 ⚠ Oracle mode has no `COLUMNS` keyword](#11--oracle-mode-has-no-columns-keyword)
- [2. Partition key vs. primary key / unique key (conditional rules)](#2-partition-key-vs-primary-key--unique-key-conditional-rules)
- [2.1 Quantitative criteria for partition key selection (official design criteria, **tiered**)](#21-quantitative-criteria-for-partition-key-selection-official-design-criteria-tiered)
- [3. Automatic partition split (the `SIZE` clause) — not a standalone partition type](#3-automatic-partition-split-the-size-clause--not-a-standalone-partition-type)
  - [3.1 Official usage restrictions (V4.5.0, verified line by line against the source)](#31-official-usage-restrictions-v450-verified-line-by-line-against-the-source)
  - [3.2 The trigger threshold is not determined by the DDL](#32-the-trigger-threshold-is-not-determined-by-the-ddl)
  - [3.3 Restrictions on subsequent DDL](#33-restrictions-on-subsequent-ddl)
  - [3.4 Mutual-exclusion check against other decisions (mandatory)](#34-mutual-exclusion-check-against-other-decisions-mandatory)
- [4. Partition lifecycle management (archiving / hot-cold)](#4-partition-lifecycle-management-archiving--hot-cold)
  - [4.1 Interaction between archive design and global indexes (must be flagged)](#41-interaction-between-archive-design-and-global-indexes-must-be-flagged)
- [5. Manual partition maintenance syntax](#5-manual-partition-maintenance-syntax)

<!-- /toc -->

## 1. Partition type selection (must pass the mode gate first)

Selection order: **first ensure high-frequency queries can use partition pruning → then ensure writes are evenly distributed → only then pick the specific type**.

| Type | Suited for | Key constraints |
|---|---|---|
| RANGE | Time series (logs, orders, transactions) that need archiving by partition | MySQL-mode partition key must be **integer or YEAR**, **single column only**, expressions allowed; `VALUES LESS THAN` must be strictly increasing |
| RANGE COLUMNS | Same as above, but the partition key is a date/string or multiple columns | Wider type support (includes DATE/DATETIME/TIMESTAMP/CHAR/VARCHAR), **expressions not allowed**, supports multiple columns |
| LIST | Stable, bounded enumeration | MySQL-mode partition key must be **integer or YEAR**, **single column only**; enumeration syntax in `doc-gaps.md` §1 |
| LIST COLUMNS | Enumeration key is a string/date or multiple columns | DECIMAL/FLOAT not supported, TIMESTAMP not included; expressions not allowed; supports multiple columns |
| HASH | Even write distribution, no time dimension, mostly equality point lookups | **MySQL mode**: partition key must be integer or YEAR, expressions allowed; **Oracle mode**: accepts a column list. Not suited to range queries on the partition key |
| KEY | Multi-column partition key, non-integer key | **Exists only in MySQL mode**; any type except TEXT/BLOB; expressions not allowed; an empty `KEY()` list means "use the primary key." Oracle mode uses `HASH(col_list)` instead |
| INTERVAL | Time series where automatic partition expansion is wanted | **Oracle mode only** (unavailable in Community Edition), single column only |
| Subpartitioning | Large tables, hotspots, need for parallelism | First level by business key, second level scattered by HASH; watch for tablet count and `max_partition_num` amplification |

The type constraints in the table above are for **MySQL mode**. See `capability-matrix.md` §1.1 for the complete type allowlist and available partition expression functions; **see §1.2 for the cross-mode syntax mapping (check before generating DDL)**. **The max-partitions-per-table limit (including subpartitions) is mode-dependent** (L0): MySQL mode = `max_partition_num` (default 8192, range [8192, 65536]); **Oracle mode = fixed at 65536, this parameter is not used**. See `tablet-capacity.md` §4 for details.

### 1.1 ⚠ Oracle mode has no `COLUMNS` keyword

`COLUMNS` is a MySQL-style construct. Oracle mode's `RANGE` / `LIST` / `HASH` **take a column list directly**, natively supporting multiple columns, and do not accept expressions:

```sql
-- Oracle mode: correct
PARTITION BY RANGE (c1, c2) ( ... )
PARTITION BY LIST  (c1, c2) ( ... )
PARTITION BY HASH  (c1, c2) PARTITIONS 16

-- Oracle mode: syntax error (neither COLUMNS nor KEY exists)
PARTITION BY RANGE COLUMNS (c1, c2) ( ... )   -- ✗
PARTITION BY KEY (c1, c2) PARTITIONS 16       -- ✗
```

Comparison of correct syntax for multi-column partition keys:

```sql
-- MySQL mode
PARTITION BY KEY(tenant_id, user_id) PARTITIONS 16                 -- non-integer / multi-column HASH family
PARTITION BY RANGE COLUMNS(tenant_id, stat_date) ( ... )            -- multi-column range
-- Oracle mode (no KEY, no COLUMNS)
PARTITION BY HASH(tenant_id, user_id) PARTITIONS 16
PARTITION BY RANGE(tenant_id, stat_date) ( ... )
```

Exception: Oracle mode's `INTERVAL` partitioning **accepts a single column only** — `PARTITION BY RANGE(dt) INTERVAL(expr)`.

## 2. Partition key vs. primary key / unique key (conditional rules)

See `indexes.md` §1. The MySQL-mode three-branch rule:

- **Has a primary key** → the partition key must be a subset of the primary key;
- **No primary key, has a unique key** → the partition key must be a subset of the unique key;
- **Neither a primary key nor a unique key** → the partition key can be any column combination (legal, **must not be rejected**, but a no-primary-key risk notice must be given).

In addition: every unique index must include all partition key columns, otherwise it can only be upgraded to a global unique index. **Automatic partition split is the only scenario that requires "a primary key must exist, and the partition key must be a prefix of the primary key."**

Avoid using an auto-increment column as the partition key: inserts cannot be routed effectively, producing cross-node transactions (see `indexes.md` §4).

## 2.1 Quantitative criteria for partition key selection (official design criteria, **tiered**)

The official "Table Design and Index Optimization Best Practices" gives four criteria for HASH / KEY partitioning.
This Skill has been collecting `distinct_count` but never compared it against the partition count — which means it was missing the hardest criterion of all.

**Read the tier column before acting on this table.** The official text presents these as *suggestions for choosing a
partition key*, not as `CREATE TABLE` restrictions — the server happily creates a 128-partition table over a
6-value column. Only criterion 3 is enforced by the parser. Treating any of the other three as an L0 hard constraint
wrongly rejects legal designs (deliberately sparse partitioning ahead of cardinality growth, a partition count pinned
by TABLEGROUP alignment, an AP table scattered purely for distributed compute).

| # | Criterion | Tier | How to check | Consequence if not met |
|---|---|---|---|---|
| 1 | **NDV (cardinality) > partition count** | **L1-B** (B1) | `distinct_count > partition_count` | Permanently empty partitions are inevitable: `PARTITIONS 128` paired with a column that only has 8 distinct values means 120 partitions stay empty forever, wasting Tablet capacity. Verdict `fail`, DDL still emitted |
| 2 | Data has **no significant skew** (or only mild skew) | **L1-B** (B3); the "significant" multiplier is **L2** | Compare `top1_key_share` against `1/partition_count` | Single-partition write hotspot (`hotspots.md` `single_partition`) |
| 3 | Prefer an **integer or time column**; only use varchar/char when necessary | **L0** (checklist item 5) | Check the column type | MySQL-mode HASH/RANGE/LIST already only accept integer or YEAR (§1) — non-integer types must switch to a KEY / COLUMNS variant. This one the server **rejects** |
| 4 | The column **appears frequently in query filter conditions** | **L1-B** (B2) | Cross-check against `dominant_patterns`' `filter` | No partition pruning possible — this is the most common #1 anti-pattern. Compensate in Step 5/6 rather than refusing |

Qualifying examples given by the official docs: transaction ID, user ID, auto-increment column (**note**: using an auto-increment column
as the partition key carries an additional cross-node-transaction cost — see `indexes.md` §4; the official text here is only saying its
distribution characteristics are good).

The corresponding criteria for RANGE / LIST:

- RANGE: partition by a time column or numeric column; **do not use too few partitions** (RANGE by time is standard practice for large log tables).
- LIST: suited to **low-cardinality** fields (province name, company name, status code) — this is the exact opposite of HASH's
  "high cardinality" requirement; do not mix up the two sets of criteria.
- In an AP scenario, if no single dimension can cover all queries but the data still needs to be scattered across multiple nodes
  to leverage distributed compute, just pick a HASH partition key using the four criteria above — there is no need to insist on
  pruning coverage for every query.

Output contract (Step 3):

```yaml
partitioning:
  strategy: hash | key | range | range_columns | list | list_columns | interval
  partition_key: []
  partition_count:
  subpartition:
    enabled:
    strategy:
    count:
  key_selection_check:         # conclusion for each of the four §2.1 criteria
    ndv_vs_partition_count:
      rule_tier: L1_blocker    # legal DDL; a failure here never blocks generation
      distinct_count:
      partition_count:
      empty_partition_estimate:             # partition_count - min(distinct_count, partition_count)
      result: pass | fail | accepted_with_reason | unverified   # unverified if distinct_count is missing
      accepted_reason:         # REQUIRED when result = accepted_with_reason; free text
                               # legitimate: cardinality expected to grow / partition count
                               # pinned by TABLEGROUP alignment / documented Tablet-SLA reason
    skew:
      rule_tier: L1_blocker    # the threshold itself is L2 -- state the multiplier used
      top1_key_share:
      baseline:                # 1 / partition_count
      multiplier_used:         # how many times the baseline counts as "significant"
      result: pass | fail | accepted_with_reason | unverified
    key_type_ok: true | false  # rule_tier: L0 -- the only one of the four the server enforces
    appears_in_dominant_filters: true | false   # rule_tier: L1_blocker (B2)
  pruning_estimate:
    covered_share:             # share of queries that can hit a single partition (summed from frequency_share)
    rule_tier: L2_unverified
    must_verify_with: EXPLAIN
```

A low `covered_share` **is not judged a failure** — route to physical coordination/index compensation instead, and note that V3 plan verification is required.

## 3. Automatic partition split (the `SIZE` clause) — not a standalone partition type

`SIZE('size_value')` is merely a modifier clause on RANGE partitioning:

```sql
-- MySQL mode
PARTITION BY RANGE [COLUMNS]([column_name_list]) [SIZE('size_value')] [(range_partition_list)]
-- Oracle mode
PARTITION BY RANGE([column_name_list]) [SIZE('size_value')] [range_partition_list]
```

### 3.1 Official usage restrictions (V4.5.0, verified line by line against the source)

If any of the following applies, automatic partition split is **not supported** — this is an L0 hard constraint:

- Automatic split is not supported for **List or Hash** partitioned tables (only Range / Range Columns first-level partitioning is supported)
- Automatic split is not supported for **tables with subpartitioning**
- Not supported when the table's **partition key differs from the primary key prefix**
- Not supported for **tables without a primary key**
- Not supported for **columnstore tables**
- Not supported for **ColumnStore Replicas**
- Not supported when the table's `TABLEGROUP` **contains multiple tables** (supported when the group contains only this one table)
- Not supported for **materialized views**
- Automatic split is not supported for **full-text indexes / spatial indexes / vector indexes**

### 3.2 The trigger threshold is not determined by the DDL

- When `SIZE()` is omitted, the **tenant-level config item** `auto_split_tablet_size` is read.
- The tenant-level switch `enable_auto_split` (`ALTER SYSTEM SET enable_auto_split = TRUE`) controls whether it is enabled.
- `size_value` can be set to `unlimited`, meaning the threshold is unbounded and split is no longer scheduled.
- If `SIZE` is omitted and `enable_auto_split = true`, this only takes effect for tables that **meet the restrictions**; a table that does not meet them is created normally as a non-auto-partitioned table (but if the user manually writes automatic-partitioning syntax, it still errors out).
- Split action: once the threshold is reached, the partition is split in two by a **Range on the primary key or primary key prefix**.
- If the pre-partition key's `column_name_list` is not filled in, it defaults to the primary key; a multi-column pre-partition key must be written as `RANGE COLUMNS()`.
- To view a table's automatic-partitioning properties: `information_schema.TABLES`, or the system tenant's `oceanbase.CDB_TABLES`.

### 3.3 Restrictions on subsequent DDL

- Changing the partitioning rule: only supported when changing to "first-level partitioning by primary-key Range."
- Changing the primary key: after the change, the automatic-partitioning key must still be a prefix of the primary key.
- Column-operation restrictions on the pre-partition key are the same as for the partition key.

### 3.4 Mutual-exclusion check against other decisions (mandatory)

```yaml
automatic_partition_check:
  target_version:                # < V4.3.5 → not supported
  compat_mode:
  base_partition_type:           # must be range | range_columns
  primary_key_present:           # must be true
  partition_key_is_pk_prefix:    # must be true
  has_subpartition:              # must be false
  columnstore_enabled:           # must be false (including ColumnStore Replica)
  tablegroup_table_count:        # >1 → not supported
  special_index_present:         # full-text/spatial/vector → not supported
  tenant_enable_auto_split:      # if not enabled, SIZE has no effect
  tenant_auto_split_tablet_size:
  result: supported | unsupported
```

**Typical conflict**: "high Join frequency → put multiple tables in a Table Group" and "a single partition is too large → enable automatic partitioning" cannot both hold. One must be chosen over the other, with the trade-off explained.

## 4. Partition lifecycle management (archiving / hot-cold)

The choice is constrained by two dimensions: manageability, and **the capability confirmation tier** (`SKILL.md`, second section). **The primary DDL may only use C1.**

| Approach | Mode | Confirmation tier | Suited for |
|---|---|---|---|
| `INTERVAL` partitioning | Oracle only | **C1** (present in the Oracle BNF, long-standing) | Oracle mode's **preferred primary approach**; automatic partition expansion, but expiry reclamation still needs to be handled separately |
| `DYNAMIC_PARTITION_POLICY` | MySQL / Oracle | Target = V4.5.0 → **C1**; target < V4.5.0 → **C2** (minimum version not verified) | Automatic time-based pre-creation + expiry reclamation, the most complete feature set |
| Manual `ADD` / `DROP` / truncate partition | Both | **C1** (basic DDL) | A version-question-free fallback; requires delivering ops scripts and monitoring |

Choosing the primary approach by target environment:

| Target environment | Primary approach | Candidate (goes into `candidate_ddl`) |
|---|---|---|
| Oracle mode | `INTERVAL` | `DYNAMIC_PARTITION_POLICY` |
| MySQL mode, target = V4.5.0 | `DYNAMIC_PARTITION_POLICY` | — |
| MySQL mode, target < V4.5.0 | Pre-created RANGE partitions + ops script | `DYNAMIC_PARTITION_POLICY` |

**Do not** write both `INTERVAL` and `DYNAMIC_PARTITION_POLICY` in the same primary DDL: the functionality overlaps, and the latter is C2 in most target versions.

```sql
DYNAMIC_PARTITION_POLICY = (
  ENABLE = true, TIME_UNIT = 'day',
  PRECREATE_TIME = '7 day',      -- create partitions 7 days ahead
  EXPIRE_TIME = '90 day',        -- partitions older than 90 days are reclaimed automatically; '-1' means never reclaim
  TIME_ZONE = 'default',
  BIGINT_PRECISION = 'none'      -- specify us/ms/s when the partition key is a bigint timestamp
)
```

Requirement: **the partition granularity must align with the archiving cycle** (archive by day → partition by day), otherwise reclamation will span partitions.

### 4.1 Interaction between archive design and global indexes (must be flagged)

Archiving by partition combined with a global index on the table incurs a global-index-rebuild cost every time a partition
is dropped (community-sourced information: in MySQL mode, dropping/truncating a partition invalidates global indexes and
triggers an automatic rebuild, which is very time-consuming on large tables; see `capability-matrix.md` §5-2 for the exact
version behavior).

Therefore: **archival tables should use local indexes only, wherever possible**. If a global index is unavoidable, the
design must state the expected impact window for a single archiving run and require testing on the target version.

## 5. Manual partition maintenance syntax

```sql
-- Add a partition (syntax is identical in both modes)
ALTER TABLE t ADD PARTITION (
  PARTITION p3 VALUES LESS THAN (UNIX_TIMESTAMP('2026-01-01')),
  PARTITION p4 VALUES LESS THAN (UNIX_TIMESTAMP('2027-01-01'))
);
-- Drop / truncate a partition
ALTER TABLE t DROP PARTITION p3, p4;
ALTER TABLE t TRUNCATE PARTITION p3, p4;
```

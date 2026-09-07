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
  - [4.2 INTERVAL restrictions (the first one rules it out for most composite designs)](#42-interval-restrictions-the-first-one-rules-it-out-for-most-composite-designs)
  - [4.3 Does `DYNAMIC_PARTITION_POLICY` manage the *subpartition* dimension?](#43-does-dynamic_partition_policy-manage-the-subpartition-dimension)
  - [4.1 Archival + global index: the rule that decides the first-level partition type](#41-archival--global-index-the-rule-that-decides-the-first-level-partition-type)
- [5. Manual partition maintenance: what is actually permitted](#5-manual-partition-maintenance-what-is-actually-permitted)
  - [5.1 Support matrix by partition-type combination (Oracle mode)](#51-support-matrix-by-partition-type-combination-oracle-mode)
  - [5.2 Four one-way doors (decide before `CREATE TABLE`, not after)](#52-four-one-way-doors-decide-before-create-table-not-after)
  - [5.3 Concurrency impact of partition DDL (what "maintenance window" really means)](#53-concurrency-impact-of-partition-ddl-what-maintenance-window-really-means)

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
| `INTERVAL` partitioning | Oracle only | **C1** (present in the Oracle BNF, long-standing) | Oracle mode's **preferred primary approach** — *when the time dimension is the first level*, see §4.2; automatic partition expansion, but expiry reclamation still needs to be handled separately |
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

### 4.2 INTERVAL restrictions (the first one rules it out for most composite designs)

Official, from the "Create a partitioned table" page's *使用限制* for INTERVAL:

> - **只支持 Interval 分区是一级分区。即可以将一级分区表或者二级分区表的一级分区指定为 Interval 分区，
>   二级分区表的二级分区不支持指定为 Interval 分区。**
> - 建表定义的时候，至少包含一个 Range 分区。
> - **为表指定 Interval 属性时，不能同时指定 `DYNAMIC_PARTITION_POLICY` 属性。**
>   *(annotation: the two **must not** coexist at all — an official restriction, strictly stronger
>   than the primary-vs-candidate guidance in §4's table, which only said don't put both in one primary DDL.)*
> - 分区键只能为单列，列类型仅支持 `NUMBER`、`DATE`、`FLOAT`、`TIMESTAMP`。（`NUMBER` 不支持指定精度）
> - 步长表达式必须为常量且为正数；日期类型分区键的步长须为 `NUMTOYMINTERVAL` / `NUMTODSINTERVAL`。
> - 初始 Range 分区中，分区上界不能为 `MAX_VALUE`。
> - 初始 Range 分区名不能以 `SYS_P` 开头。
> - 不支持分区键是自增列。

Three of these change designs rather than just DDL:

1. **First level only.** A composite table whose *first* level is HASH or LIST cannot use INTERVAL on its time
   dimension at all — this is a grammar-and-doc fact, not a version gap. The common request "partition by business
   key first, then auto-extend by month" therefore has **no INTERVAL answer**; the alternatives are
   `DYNAMIC_PARTITION_POLICY` (see the caveat in §4.3) or scripted `ADD SUBPARTITION`. Say this plainly rather than
   letting the reader assume it is a missing feature.
2. **Mutually exclusive with `DYNAMIC_PARTITION_POLICY`** — this is an official restriction, not merely the
   overlap-avoidance advice given above. Writing both is rejected.
3. **Auto-created partitions are named `SYS_P…`**, and user partition names may not use that prefix. Any archive
   script that drops INTERVAL-created partitions must look the names up from `USER_TAB_PARTITIONS` rather than
   compute them.

### 4.3 Does `DYNAMIC_PARTITION_POLICY` manage the *subpartition* dimension?

**Unverified — and it is the question that decides whether a `key / time` composite table can be automated at all.**
Every official example is a first-level time partition; no page states whether the policy also pre-creates and
expires subpartitions. Do not assert either answer.

Cheap way to settle it: create a structurally identical toy table with `TIME_UNIT = 'day'` (not `'month'`, so the
result appears within a day), then check whether new subpartitions appear:

```sql
SELECT * FROM USER_TAB_SUBPARTITIONS WHERE TABLE_NAME = '<probe table>';
```

If `CREATE TABLE` itself is rejected, that is the answer too. Related and confirmed: the dynamic-partition feature
validates that the partition key is a **plain column** — an expression (even a back-quoted column name, in
V4.3.5 BP2/BP4) raises `for dynamic partition, this part func expr is not supported`. This is the same
"expression partition keys are second-class" theme as the lazy-maintenance exclusion in §4.1; a generated/virtual
column used as a partition key will collide with it in several places at once.

### 4.1 Archival + global index: the rule that decides the first-level partition type

This is the single highest-leverage interaction in the whole skill. Get it wrong and a routine monthly archive job
becomes a service outage; get it right and the same design is safe. **It is not "global indexes are bad on archival
tables" — the answer depends on the first-level partition type.**

Official rule (Oracle mode; see `sources.md` § Partition lifecycle):

> Oracle 模式下，对于有全局索引的一级分区表或二级分区表，删除分区时，需要通过在 `ALTER TABLE` 语句中添加
> `UPDATE GLOBAL INDEXES` 关键字的方式来更新全局索引信息。**如果未添加 `UPDATE GLOBAL INDEXES` 关键字，
> 则删除分区后，该分区表上的全局索引会处于不可用状态。**
>
> - 对于使用 **Range、Interval 或 List** 分区（包括一级分区和二级分区）且支持删除分区操作的表，当指定
>   `UPDATE GLOBAL INDEXES` 时，系统**不会重建全局索引**，而是通过后台合并删除数据的方式，以 lazy（延迟）
>   维护策略保持索引有效……**以下场景无法触发该优化：**
>   - **一级分区为 Hash 分区**（即使二级分区为 Range 或 List），此时对二级分区执行 Truncate 操作。
>   - 分区键为表达式而非普通列。
>   - 对于全文索引、非结构化类型等特殊全局索引，即使使用 `UPDATE GLOBAL INDEXES`，索引仍会处于不可用状态。

Decision table for a table that is archived by dropping partitions:

| First-level partition type | Global indexes present? | Verdict |
|---|---|---|
| RANGE / INTERVAL / LIST | yes | **OK** — write `UPDATE GLOBAL INDEXES`, lazy maintenance keeps the index valid |
| **HASH** | yes | **Design blocker.** The lazy path is excluded; every archive run invalidates or rebuilds *every* global index on the table |
| HASH | **none** | **OK** — with no global index there is nothing to invalidate; local index tablets are dropped along with their subpartition |
| any | expression partition key | Excluded from the lazy path — treat like the HASH row |

Two consequences the Agent must state, not bury:

1. **The keyword is mandatory, and it is easy to omit.** `ALTER TABLE t DROP SUBPARTITION sp UPDATE GLOBAL INDEXES;`
   Omitting it is not a missed optimisation — it actively marks the index unusable.
2. **A global index's blast radius is the whole table, not the dropped partition.** In Oracle mode a global index is a
   single, non-partitioned index object (`indexes.md` §2.3), so its status is a property of that one object. Dropping the
   oldest, coldest month invalidates order lookups for *every* month, including today's. A local index's blast radius, by
   contrast, is exactly the subpartition being dropped. **This asymmetry is usually the deciding argument.**

Therefore the design rule is conditional, not blanket:

- **Archived table + first-level RANGE/INTERVAL/LIST** → global indexes are allowed; require `UPDATE GLOBAL INDEXES` in
  every archive statement, and verify on the target version.
- **Archived table + first-level HASH** → either the table carries **no** global index at all (then HASH is fine and
  new partition-key values need zero DDL), or the first-level type must change. Emit this as an explicit either/or,
  and record "no global index on this table" as a standing invariant — it is easy for a later change to violate,
  especially because `CREATE INDEX` **defaults to GLOBAL** when the keyword is omitted (`indexes.md` §2.3).

There is also a tenant-level hidden config, `_ob_enable_truncate_partition_preserve_global_index`
(True by default on newly created tenants, **False on upgraded tenants**), documented as controlling whether partition
DDL leaves global indexes valid. It appears **only on the MySQL-mode page**, and how it composes with the Oracle-mode
exclusion list above is not documented → `unverified`; never design around it without measuring.

## 5. Manual partition maintenance: what is actually permitted

The syntax below is the easy part. **The support matrix and the four one-way doors in §5.2 are what decide whether a
partition layout is operable at all**, and they must be checked at design time — several of them cannot be undone
after `CREATE TABLE`.

```sql
-- Add a partition (syntax is identical in both modes)
ALTER TABLE t ADD PARTITION (
  PARTITION p3 VALUES LESS THAN (UNIX_TIMESTAMP('2026-01-01')),
  PARTITION p4 VALUES LESS THAN (UNIX_TIMESTAMP('2027-01-01'))
);
-- Drop / truncate a partition
ALTER TABLE t DROP PARTITION p3, p4;
ALTER TABLE t TRUNCATE PARTITION p3, p4;

-- Oracle mode adds UPDATE GLOBAL INDEXES on drop/truncate (see §4.1 — mandatory when
-- the table has any global index)
ALTER TABLE t DROP     {PARTITION | SUBPARTITION} name_list [UPDATE GLOBAL INDEXES];
ALTER TABLE t TRUNCATE {PARTITION | SUBPARTITION} name_list [UPDATE GLOBAL INDEXES];

-- Add a subpartition to an existing first-level partition (non-templated tables only, §5.2)
ALTER TABLE t MODIFY PARTITION p0 ADD SUBPARTITION p0_sp5 VALUES LESS THAN (...);
```

### 5.1 Support matrix by partition-type combination (Oracle mode)

Not every combination supports every operation. Reading this table backwards — "which layout lets me do the
maintenance my lifecycle needs?" — is usually the right way to pick a partition type.

| Table shape | ADD / DROP / TRUNCATE **first level** | ADD / DROP / TRUNCATE **subpartition** |
|---|---|---|
| First-level only, RANGE / LIST | supported | — |
| First-level only, **HASH** | **not supported** | — |
| RANGE-RANGE, RANGE-LIST | supported | supported |
| RANGE-HASH | supported | **not supported** |
| LIST-RANGE, LIST-LIST | supported | supported |
| LIST-HASH | supported | **not supported** |
| **HASH-RANGE, HASH-LIST** | **not supported** | supported |
| HASH-HASH | not supported | not supported |

Two readings that matter in practice:

- **A HASH first level is immutable.** No `ADD PARTITION`, and OceanBase has no `COALESCE PARTITION` either, so the
  partition count is fixed at `CREATE TABLE` for the life of the table. Choose it only when the key needs no
  per-value lifecycle, and size the count against measured data (`tablet-capacity.md`).
- **A HASH first level still allows subpartition maintenance**, so `HASH(key) SUBPARTITION BY RANGE(time)` is a
  perfectly operable shape for time-based archival — provided §4.1's global-index rule is satisfied.

### 5.2 Four one-way doors (decide before `CREATE TABLE`, not after)

Each of these is legal to write and impossible to walk back without rebuilding the table.

1. **A `MAXVALUE` last RANGE partition blocks all future `ADD PARTITION`.** Official: *"如果最后一个 Range 分区
   指定了 `MAXVALUE`，则不能新增分区。"* So on a table whose time dimension must keep growing, the catch-all bucket
   and future extension are mutually exclusive. Dropping the catch-all means out-of-range inserts fail loudly —
   usually the better failure mode, but it must be paired with headroom monitoring.
2. **A `DEFAULT` last LIST partition blocks all future `ADD PARTITION`.** Official: *"如果最后一个 List 分区指定了
   `DEFAULT`，则不能新增分区。"* Same trade as above. Note this conflicts with the L1 default recommendation
   "LIST partitioning defaults to a `DEFAULT` catch-all" — **that default only holds for a LIST table whose value set
   is closed.** If new key values will appear over time, the catch-all must be dropped in favour of `ADD PARTITION`.
3. **`ADD SUBPARTITION` works only on non-templated subpartitioned tables.** Official: *"you can add a subpartition
   only to a non-template-based subpartitioned table."* `SUBPARTITION TEMPLATE` produces much shorter DDL but
   permanently freezes the subpartition dimension. For a time-subpartitioned table that must keep growing, the
   verbose non-templated form is the only workable choice; generate it with a script rather than by hand.
4. **There is no way to add a value to an existing LIST partition.** The `ALTER TABLE` grammar offers only
   `ADD PARTITION` / `DROP {PARTITION|SUBPARTITION}` / `TRUNCATE`; there is no `MODIFY PARTITION … ADD VALUES`, and
   the "modify partition rules" page covers only repartitioning and RANGE↔INTERVAL. **Consequence: grouping many
   key values into one LIST partition is a dead end for a key set that keeps growing** — new values cannot join an
   existing group, only form a new partition. If the key set grows, prefer HASH (auto-routing) or ensure future key
   values can be enumerated in advance.

### 5.3 Concurrency impact of partition DDL (what "maintenance window" really means)

Dropping a partition is an Offline DDL that takes a partition-level exclusive lock **on the target partition only**:

| Concurrent operation | Impact while the partition DDL runs |
|---|---|
| Other DDL on the same table | blocked — partition DDL cannot run in parallel with itself either |
| DML on the **target** partition | fully blocked |
| DML on other partitions | generally unaffected |
| `SELECT` | **unaffected** |

The practical reading: a monthly archive job issues N statements serially, but the partitions it touches are the
oldest month (no writes) and future months (no data), so **online traffic is not interrupted**. "This batch takes an
hour" is not "the service is down for an hour" — an Agent must not let a reader conflate the two. The statements also
have no deadline, so they can be spread out rather than run in one window; the real operational requirement is
**resumability**, not a window.

> Provenance caveat: this impact table appears on the **MySQL-mode** page. The Oracle-mode page only says
> *"删除分区时，请尽量保证待删除的分区上不存在活动的事务或查询"*. Treat the table as directional for Oracle mode
> and confirm on the target version.

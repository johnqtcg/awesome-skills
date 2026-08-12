# Capacity Estimation: Tablet Count and Partition Size

<!-- toc -->

**Table of Contents**

- [1. Tablet Count Formula (Sum Over Physical Objects, Not a Product)](#1-tablet-count-formula-sum-over-physical-objects-not-a-product)
- [2. The Limit Is Per OBServer Node, and Takes the Smaller of Two Formulas](#2-the-limit-is-per-observer-node-and-takes-the-smaller-of-two-formulas)
  - [2.1 Why Only Formula A Is Binding Under Default Values](#21-why-only-formula-a-is-binding-under-default-values)
  - [2.2 Reconciling "2G ≈ 20,000" with "2G Comes Out to 40,000"](#22-reconciling-2g--20000-with-2g-comes-out-to-40000)
- [3. Output Contract](#3-output-contract)
- [4. Per-Table Partition Count Limit (L0, **Determined by Compatibility Mode**)](#4-per-table-partition-count-limit-l0-determined-by-compatibility-mode)
  - [4.1 The Object Being Checked Is **Each Individual Partitioned Physical Object**, Not "Each Table"](#41-the-object-being-checked-is-each-individual-partitioned-physical-object-not-each-table)
- [4.2 Heterogeneous Zones / Units: Judge by the **Worst Node**](#42-heterogeneous-zones--units-judge-by-the-worst-node)
- [5. Data Size Per Partition](#5-data-size-per-partition)
- [6. Skew](#6-skew)
- [7. Verification Method (V4)](#7-verification-method-v4)
- [8. Script](#8-script)

<!-- /toc -->

## 1. Tablet Count Formula (Sum Over Physical Objects, Not a Product)

A partition is a logical object; a Tablet is its data storage and migration object, and
the two correspond one to one. **Each partition of an index likewise corresponds to one
Tablet — this counts for both local indexes and global indexes.** A local index's
Tablets are forcibly co-located on the same node as the base table's Tablets.

```
Total Tablets = Σ(for each table) [
      base-table partition count × base-table subpartition count
    + Σ(for each local index) base-table partition count × base-table subpartition count
    + Σ(for each global index) that index's own partition count × that index's own subpartition count
]
```

Do not use `partitions × subpartitions × table_count`: it both omits indexes and
implicitly assumes "every table partitions the same way" — an assumption that almost
never holds.

Example: a table with 6 partitions plus 3 local indexes = 6 + 18 = **24** Tablets, not 6.

Also leave some headroom: different versions may have additional auxiliary objects (LOB
auxiliary tables, columnstore auxiliary structures, materialized views, full-text/vector
indexes, etc.).

## 2. The Limit Is Per OBServer Node, and Takes the Smaller of Two Formulas

Official definition: **the maximum number of Tablets a tenant can create on each
OBServer node** is jointly determined by tenant hidden parameters and tenant memory,
taking the **smaller** of the following two formulas:

```
Formula A = (MEMORY_SIZE / 1GB) × _max_tablet_cnt_per_gb
Formula B = (MEMORY_SIZE × _storage_meta_memory_limit_percentage) / 200MB × 20000

per_node_limit = min(A, B)
```

Parameters:

| Parameter | Meaning | Value range | Default |
|---|---|---|---|
| `_max_tablet_cnt_per_gb` | The maximum number of Tablets supported per 1 GB of memory in a tenant resource unit | `[1000, 50000)` | **20000** |
| `_storage_meta_memory_limit_percentage` | The upper bound on the percentage of tenant memory usable for metadata storage (%) | `[0, 50)` | **20** (`0` means no cap is set, in which case Formula B does not apply) |

Two points are very easy to get wrong and must be spelled out clearly:

1. **`MEMORY_SIZE` is the memory of the tenant resource unit (unit) on that node** — not
   the cluster's total memory, and not the vague notion of "tenant spec."
2. **The limit is per-node.** So the comparison must be between the **single-node**
   Tablet count and per_node_limit, not the cluster-wide total Tablet count. Single-node
   estimate (assuming an even distribution):

```
Single-node Tablets ≈ ceil(total Tablets / unit_num)      # unit_num = number of units the tenant has in each Zone
```

### 2.1 Why Only Formula A Is Binding Under Default Values

Substituting the default values (`1 GB = 1024 MB`):

- A = M(GB) × 20000
- B = (M × 1024MB × 0.20) / 200MB × 20000 = M × **20480**

Under the default configuration, A < B, so `min` always resolves to A. But as soon as
someone raises `_max_tablet_cnt_per_gb` (up to 50000) or lowers
`_storage_meta_memory_limit_percentage` (say, to 5), **B becomes the bottleneck**. So the
`min()` can never be dropped.

### 2.2 Reconciling "2G ≈ 20,000" with "2G Comes Out to 40,000"

By the formula, 2 GB of **unit memory** → A = 40000. Yet a common community claim is "a
2C/2G tenant's limit is about 20,000, and going to 2C/3G raises it to 40,000." The two
are not actually in conflict — they define the quantity differently:

- The 2G/3G in the community claim is the **total tenant spec**, of which the Meta
  tenant fixedly consumes about 1 GB, leaving the user tenant with an actual 1 GB / 2 GB;
- The `MEMORY_SIZE` in the formula is the **user tenant's unit memory**, i.e.,
  1 GB / 2 GB → 20000 / 40000.

Conclusion: when estimating, make it explicit that the input is the **user tenant's unit
memory**. If the user has only given you a "tenant spec," either subtract the Meta
tenant's overhead, or mark it `unverified` directly and ask them to check
`GV$OB_UNITS`.

## 3. Output Contract

```yaml
tablet_capacity:
  unit_memory_gb:                      # user tenant unit memory; missing → unverified
  unit_num:                            # number of units per Zone; missing → unverified
  max_tablet_cnt_per_gb: 20000         # use the default and mark it assumed if the actual value wasn't obtained
  storage_meta_memory_limit_percentage: 20
  formula_a:
  formula_b:                           # not_applicable when percentage = 0
  per_node_limit:                      # min(A, B)
  binding_formula: A | B               # which formula is actually binding
  estimated_total:                     # expanded item by item per the §1 formula
  estimated_per_node:                  # ceil(total / unit_num)
  breakdown:
    - table:
      base:
      local_index:
      global_index:
  headroom_ratio:                      # estimated_per_node / per_node_limit
  result: pass | pass_with_warning | fail | unverified
  assumptions: []                      # parameters for which a default value was used must be listed
```

`headroom_ratio` is recommended to stay below 0.5 to leave room for growth — this is an
**L2 threshold to be verified**, not a hard product limit.

When any required input is missing, `result` can only be `unverified` — you are **not
allowed** to force a `pass` by plugging in default values.

## 4. Per-Table Partition Count Limit (L0, **Determined by Compatibility Mode**)

| Mode | Limit | Source |
|---|---|---|
| **MySQL** | Tenant configuration item `max_partition_num`, default **8192**, range **[8192, 65536]**, adjustable via `ALTER SYSTEM SET` | Official docs state this parameter **applies only to MySQL mode** |
| **Oracle** | **Fixed at 65536**; `max_partition_num` **is not used** | Oracle-mode partitioning overview: a table has at most 65536 partitions |

### 4.1 The Object Being Checked Is **Each Individual Partitioned Physical Object**, Not "Each Table"

The partition-count limit applies **separately to each partitioned object**. Checking
only the base table misses real violations:

| Object | Checked against the limit on its own | Reason |
|---|---|---|
| Base table | Yes | Its own `partitions × subpartitions` |
| **Each global index** | Yes | A global index **can have its own independent partitioning scheme**, unrelated to the base table's partition count |
| Local index / primary key index | No | Inherits the base table's partitioning; if the base table is compliant, these necessarily are too |
| LOB auxiliary object | No | Follows the base table's partitioning |

Counter-example (a real violation that would be missed):

```json
{"table": "t", "partitions": 1,
 "global_indexes": [{"name": "g", "partitions": 9000}]}
```

The base table has only 1 partition, but the global index has 9000 — under MySQL mode
this exceeds `max_partition_num` (default 8192), so it must be judged `fail`. Looking
only at the base table's `partition_count` would wrongly judge it `pass`.

`scripts/estimate_tablets.py` already judges each object individually; its
`objects_over_partition_limit` output names the specific offending object (e.g.,
`t.g(global_index, 9000)`).

A subpartitioned table is counted by its total partition count (base-table partition
count × subpartition count); a global index is counted the same way, using its own
`partitions × subpartitions`. At design time you must verify:

```
MySQL mode: base-table partition count × subpartition count ≤ max_partition_num (default 8192, adjustable up to 65536)
Oracle mode: base-table partition count × subpartition count ≤ 65536
```

**Common mistake**: treating 8192 as a hard limit shared by both modes. A table with
10000 physical partitions is legal in Oracle mode; gating it against 8192 would wrongly
reject it.

When `compat_mode` is unknown, `scripts/estimate_tablets.py`'s partition-count check
gives `pass` only when "every table is ≤ 8192" (safe under either mode); anything
falling in the 8193–65536 range outputs `unverified` and asks for the mode to be
supplied — it will **not** be wrongly judged `fail`.

## 4.2 Heterogeneous Zones / Units: Judge by the **Worst Node**

The formula in §2 is computed once per node. If the memory across Zones/Units is
**not uniform**, judging by an average masks the real failure mode of "the
small-memory node blows up first."

Example: z1 = 64 GB (limit 1,280,000), z2 = 1 GB (limit 20,000), 30,000 Tablets in total
split evenly:

| Node | Memory | Share | Tablets | per_node_limit | headroom_ratio |
|---|---|---|---|---|---|
| z1 | 64 GB | 0.5 | 15,000 | 1,280,000 | 0.012 |
| **z2** | **1 GB** | 0.5 | 15,000 | **20,000** | **0.750** ← basis for the judgment |

The average headroom of only 0.38 looks safe, but z2 has already crossed the 0.5 warning
line. **You must use the worst node.**

Estimator usage:

```json
{"compat_mode": "mysql",
 "units": [{"zone": "z1", "memory_gb": 64},
           {"zone": "z2", "memory_gb": 1, "tablet_share": 0.3}],
 "tables": [...]}
```

- When `units[]` is provided, it overrides `unit_memory_gb` / `unit_num`;
- `tablet_share` is optional (defaults to an even split), but **it must either be
  supplied for every entry or none, and the values must sum to 1**;
- The output includes `topology`, `worst_node`, and `node_detail[]`; the judgment is
  based on the worst node.

Get the real topology from `GV$OB_UNITS` (see §7) — don't work from assumptions.

## 5. Data Size Per Partition

- A common official/community rule of thumb: consider a partitioned table once a
  single table's row count exceeds roughly 1 billion rows, or its size reaches
  hundreds of GB; there is **no** hard rule such as "a single partition must be
  < 30GB."
- The split threshold for auto-partitioning is **a separate matter**, governed by the
  tenant configuration item `auto_split_tablet_size`, and it only takes effect when the
  tenant-level switch `enable_auto_split = true` is on — writing `SIZE` in the DDL does
  not mean auto-partitioning is actually enabled (see `partitioning.md` §3.2).
- Consequently, a target size per partition is an **L2 threshold to be verified**: any
  recommended value must be labeled as an empirical value and must call for
  confirmation via tenant specs and benchmarking.

## 6. Skew

Capacity estimation must account for skew, otherwise "average of X GB per partition" is
meaningless:

```yaml
skew:
  partition_key:
  distinct_count:
  top1_key_share:                # share of the largest key
  expected_max_partition_gb:     # = total size × top1_key_share (for HASH, estimate per bucket)
```

When `top1_key_share` is clearly higher than `1 / partition_count`, judge it as skewed
and route into the hotspot-handling process.

## 7. Verification Method (V4)

```sql
-- Actual Tablet count (including indexes)
SELECT TABLE_NAME, TABLE_TYPE, COUNT(*) AS tablet_cnt
  FROM oceanbase.DBA_OB_TABLETS GROUP BY TABLE_NAME, TABLE_TYPE;

-- The tenant's unit memory and distribution across nodes (the authoritative source for MEMORY_SIZE / unit_num)
SELECT * FROM GV$OB_UNITS;

-- Read the effective Tablet limit and current usage directly, instead of deriving it yourself
SELECT SVR_IP, SVR_PORT, TENANT_ID, ZONE, RESOURCE_TYPE,
       CURRENT_UTILIZATION, MAX_UTILIZATION, LIMIT_VALUE, EFFECTIVE_LIMIT_TYPE
  FROM GV$OB_TENANT_RESOURCE_LIMIT WHERE RESOURCE_TYPE = 'tablet';

-- Breakdown by each limiting source (configuration / memory / data_disk ...)
SELECT * FROM GV$OB_TENANT_RESOURCE_LIMIT_DETAIL WHERE RESOURCE_TYPE = 'tablet';
```

**Whenever `GV$OB_TENANT_RESOURCE_LIMIT` can be queried, treat `LIMIT_VALUE` as
authoritative** — the formulas are only for upfront estimation at design time.
`EFFECTIVE_LIMIT_TYPE` tells you whether the currently effective limit comes from
`configuration` or `memory`.

## 8. Script

`../scripts/estimate_tablets.py` implements the `min()` model above along with the
per-node comparison; `--self-test` runs a self-check.

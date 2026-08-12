# Physical Co-location: Duplicated Tables, Table Group, Redundancy, Global Index

Four solutions to cross-node joins / cross-table transactions. **Choose using the table below first, then discuss Table Group attributes** — treating Table Group as the only answer is the most common design mistake.

<!-- toc -->

**Table of Contents**

- [1. Four-Way Decision Table](#1-four-way-decision-table)
- [2. Table Group: the SHARDING Attribute](#2-table-group-the-sharding-attribute)
  - [2.1 Warning: the Semantics of `SHARDING = NONE` Differ by Version (Distinguish Carefully)](#21-warning-the-semantics-of-sharding--none-differ-by-version-distinguish-carefully)
- [3. Table Group: the SCOPE Attribute (≥ V4.4.2 BP1)](#3-table-group-the-scope-attribute--v442-bp1)
- [4. DDL and Verification](#4-ddl-and-verification)
- [5. Complete Output Contract](#5-complete-output-contract)

<!-- /toc -->

## 1. Four-Way Decision Table

| Approach | Applicable shape | Cost | Criterion |
|---|---|---|---|
| **Duplicated table** `DUPLICATE_SCOPE = 'cluster'` | A large partitioned table joins a **small dictionary/dimension table** (read-heavy, near-zero writes) | Every update must be synced to all replicas | Small table, low update frequency, cannot share a partition key with the large table |
| **Table Group partition alignment** | Both tables are large and **naturally share the same partition key** (e.g., both partitioned by `user_id`) | Strongly constrains the partition definition; a wrong SHARDING/SCOPE choice affects locality or load balancing | The shared-partition-key semantics genuinely hold |
| **Redundant denormalization** | The join only pulls a few small columns | Writes must maintain consistency of the redundant columns | Redundant columns rarely change |
| **Global index** | The query does not include the base table's partition key | Write amplification + possible distributed transaction | See `indexes.md` §2.1 |

**Key criterion**: if the small table, in business terms, **has no** column corresponding to the large table's partition key, do not fabricate a partition key just to put it in a table group — that is a duplicated-table scenario.

```sql
CREATE TABLE dim_currency (code VARCHAR(8) PRIMARY KEY, rate DECIMAL(18,8))
  DUPLICATE_SCOPE = 'cluster';
```

Output contract:

```yaml
physical_layout:
  strategy: duplicate_table | table_group | denormalize | global_index | none
  reason:
  rejected_alternatives:        # Required — explain why the other three were not chosen
```

## 2. Table Group: the SHARDING Attribute

Starting with V4.2.0, table groups no longer have a partition concept — only `SHARDING` needs to be defined.

| SHARDING | Partition requirement | Partition aggregation behavior |
|---|---|---|
| `NONE` | **No restriction** on how member tables are partitioned | **Partitions are not aggregated across tables** |
| `PARTITION` | All tables must have **identical first-level partition definitions** (subpartitioned tables are only checked at the first level), so first-level-only tables and subpartitioned tables can coexist | Each table's data is scattered by first-level partition; partitions sharing the same first-level partition value are co-located (including all subpartitions under that first-level partition, for subpartitioned tables) |
| `ADAPTIVE` | Member tables must be **all first-level-only** or **all subpartitioned**; the partition definitions at the corresponding level(s) must all match | Partitions whose first-level (or first-level + subpartition) values all match are co-located |

### 2.1 Warning: the Semantics of `SHARDING = NONE` Differ by Version (Distinguish Carefully)

| Target version | Semantics of `NONE` | Design implication |
|---|---|---|
| **< V4.4.2 BP1** | In addition to "partitions are not aggregated across tables," it **also implies "all partitions sit on the same log stream, with no scattering (concentrated on a single node)"** | There is a **single-node capacity and hotspot ceiling**: putting two large tables into the group pushes all their data onto one OBServer. You must evaluate the group's total data volume before choosing NONE |
| **≥ V4.4.2 BP1** | **The "concentrated on a single node" semantic has been removed.** `NONE` now only means "no restriction on partitioning method, partitions not aggregated across tables" | The actual distribution range **depends on the `SCOPE` attribute**. `NONE` itself should no longer be treated as a single-node capacity trap; the risk assessment shifts to `SCOPE = SERVER` |

Therefore:

- Target version < V4.4.2 BP1 → a `NONE` + large-table combination requires a capacity warning.
- Target version ≥ V4.4.2 BP1 → **do not** output a conclusion like "NONE forces all partitions onto a single node"; instead check `SCOPE`: only `SCOPE = SERVER` carries the "all Leaders concentrated on one node" load-balancing risk.

## 3. Table Group: the SCOPE Attribute (≥ V4.4.2 BP1)

`SCOPE` defines the **distribution range** across the cluster of the Partition Group formed after `SHARDING` aggregation:

| SCOPE | Semantics | Trade-off |
|---|---|---|
| `SERVER` | The Leaders of all Partition Groups are **concentrated on the same node** | Strongest data locality, but **may affect cluster load balancing** |
| `ZONE` | The Leaders of all PGs are distributed **within the same Zone, and scattered across the nodes within that Zone** | Balances locality against intra-Zone load balancing |
| `CLUSTER` | The Leaders of all PGs are **scattered across the nodes of the cluster** | Maximizes load balancing, but **may increase cross-node access** |

Typical use cases for `SCOPE = ZONE` (per official guidance):

1. **Cross-Zone latency sensitivity**: co-locate the Leaders of related partitions in the same Zone to reduce cross-Zone access latency.
2. **Intra-Zone load balancing**: within the same Zone, spread the Leaders of different partitions across different servers to avoid overloading a single server.
3. **Global index consistency**: keep the Leaders of the base table and its global index in the same Zone to guarantee access locality.

Selection recommendation (L1): latency-sensitive with large data volume → `ZONE`; small scale requiring strong locality → `SERVER` (accepting the load-balancing cost); throughput-first → `CLUSTER`.

For a table group upgraded from an older version, `SCOPE` is NULL. When the target version is < V4.4.2 BP1, `SCOPE` must output `not_supported_in_target_version`, and Leader distribution must instead be controlled manually via Primary Zone.

## 4. DDL and Verification

```sql
CREATE TABLEGROUP tg_user SHARDING = 'PARTITION';

CREATE TABLE users (...) TABLEGROUP = tg_user PARTITION BY HASH(user_id) PARTITIONS 16;
CREATE TABLE accounts (...) TABLEGROUP = tg_user PARTITION BY HASH(user_id) PARTITIONS 16;

ALTER TABLEGROUP tg_user ADD user_profiles;      -- add an existing table
SHOW TABLEGROUPS WHERE tablegroup_name = 'tg_user';
DROP TABLEGROUP IF EXISTS tg_user;
```

**Sharing the same partition key does not mean co-location**: if the tables are not placed in the same table group, load balancing and Primary Zone policy may still schedule same-numbered partitions of the two tables onto different OBServers, so the join remains cross-node.

## 5. Complete Output Contract

```yaml
table_group:
  enabled: true | false
  name:
  sharding: NONE | PARTITION | ADAPTIVE
  sharding_semantics_version_branch: pre_4_4_2_bp1 | post_4_4_2_bp1   # Required — determines the risk judgment for NONE
  scope: SERVER | ZONE | CLUSTER | not_supported_in_target_version
  member_tables: []
  total_data_size_gb:            # Required only for pre_4_4_2_bp1 with sharding=NONE (single-node capacity assessment)
  load_balance_risk:             # Required when scope=SERVER
  partition_alignment:           # Item-by-item comparison of each table's first-level/subpartition definitions
  compatibility_check: pass | fail
  conflicts:                     # e.g., multiple tables in the group → mutually exclusive with automatic partitioning
  ddl: |
    CREATE TABLEGROUP ...;
    ALTER TABLEGROUP ... ADD ...;
```

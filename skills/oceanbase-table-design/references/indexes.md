# Index and Constraint Design

<!-- toc -->

**Table of Contents**

- [1. Partition Key vs. Primary Key/Unique Key: **Conditional Rule**, Not "Must Have a Primary Key"](#1-partition-key-vs-primary-keyunique-key-conditional-rule-not-must-have-a-primary-key)
  - [1.1 L0 Hard Constraints (Truly Non-Negotiable)](#11-l0-hard-constraints-truly-non-negotiable)
  - [1.2 L1 Recommendation: Risk Warning for Primary-Key-less Tables (a Warning, Not a Rejection)](#12-l1-recommendation-risk-warning-for-primary-key-less-tables-a-warning-not-a-rejection)
  - [1.3 Global Uniqueness for Partitioned Tables](#13-global-uniqueness-for-partitioned-tables)
  - [1.4 Output Contract](#14-output-contract)
- [2. Local Index vs. Global Index](#2-local-index-vs-global-index)
  - [2.1 Global Indexes Are Not Forbidden — They Are a Cost Decision](#21-global-indexes-are-not-forbidden--they-are-a-cost-decision)
  - [2.2 Interaction with Partition Operations](#22-interaction-with-partition-operations)
- [3. Primary Key Design: Separate Constraints from Optimization](#3-primary-key-design-separate-constraints-from-optimization)
- [4. The Extra Cost of Using an Auto-Increment Column as the Partition Key](#4-the-extra-cost-of-using-an-auto-increment-column-as-the-partition-key)
- [5. Index Tablets Count Toward Capacity](#5-index-tablets-count-toward-capacity)
- [6. Beyond Local/Global: Another Category of Index](#6-beyond-localglobal-another-category-of-index)
  - [6.1 Index-Level Column Groups (Columnstore Index / Row-Store Index)](#61-index-level-column-groups-columnstore-index--row-store-index)

<!-- /toc -->

## 1. Partition Key vs. Primary Key/Unique Key: **Conditional Rule**, Not "Must Have a Primary Key"

Official MySQL-mode rule (three mutually exclusive branches):

| Table shape | Partition key constraint |
|---|---|
| **Has a primary key** | The partition key must be a **subset of the primary key** |
| **No primary key, has a unique key** | The partition key must be a **subset of the unique key** |
| **No primary key and no unique key** | The partition key **may be any column combination**, unconstrained by a primary/unique key |

Therefore: you **cannot** treat "a partitioned table must have a primary key, and the partition key must be part of it" as an L0 hard constraint — that would wrongly reject legitimate primary-key-less partitioned tables (e.g., pure append-only logging/tracking tables).

### 1.1 L0 Hard Constraints (Truly Non-Negotiable)

1. When a primary key exists: partition key ⊆ primary key.
2. When there is no primary key but there is a unique key: partition key ⊆ that unique key (must hold for **every** unique key).
3. **Automatic partition splitting (`SIZE`) is a stricter exception**: it requires a primary key, and the partition key must be a **prefix of the primary key**; primary-key-less tables are not supported.
4. If a unique constraint does not include all partition key columns → a local unique index **cannot be implemented**; it must be upgraded to a global unique index, explicitly taking on the distributed-transaction cost at write time. The Agent must perform this upgrade and record the cost in warnings — **must not generate it silently**.

### 1.2 L1 Recommendation: Risk Warning for Primary-Key-less Tables (a Warning, Not a Rejection)

When a table is legitimately determined to be "no primary key and no unique key" and partitioned, you should still flag:

- No primary-key-based row-level addressing is possible; some operational tasks (e.g., batch processing by primary-key range, `SIZE`-based automatic partitioning) are unavailable;
- Incremental sync tools such as OMS/CDC generally require a primary key or unique key; a table without one may not be able to connect;
- No constraint protects against duplicate data;
- Under an index-organized table, the lack of a primary key affects storage locality (consider `ORGANIZATION = HEAP`, see `storage-format.md` §6).

Give the recommendation but **let the user decide**; if the user explicitly accepts it, proceed with the primary-key-less design.

### 1.3 Global Uniqueness for Partitioned Tables

Prefer implementing it via the primary key. If a unique column can be folded into the primary key, do not build an extra global unique index for it.

### 1.4 Output Contract

```yaml
key_constraints:
  table_key_shape: has_pk | no_pk_has_uk | no_pk_no_uk
  partition_keys: []
  primary_key: []
  unique_keys:
    - name:
      columns: []
      contains_all_partition_keys: true | false
      resolution: local_unique | promoted_to_global_unique | merged_into_pk | rejected
      cost_note:                # Required when upgraded to a global unique index
  subset_rule_check:
    result: pass | fail | not_applicable    # not_applicable for no_pk_no_uk
    evidence:
  auto_split_pk_prefix_check:
    result: pass | fail | not_applicable    # Only applies when automatic partitioning is requested
  no_pk_risk_notes: []          # Required when table_key_shape = no_pk_no_uk
```

> The corresponding rule for Oracle mode must be confirmed against the target version's official documentation before applying; the rule in this section is sourced from the MySQL-mode partition key documentation.

## 2. Local Index vs. Global Index

| | Local index | Global index |
|---|---|---|
| Partitioning rule | Inherits from the base table | Can be defined independently |
| Tablet | **Forced to co-locate** with the base table's Tablet | Distributed independently — essentially a distributed table in its own right |
| Write cost | Co-located with the base table, no extra distributed transaction | Write amplification + may introduce a distributed transaction |
| Applicability | Query can be pruned by the base table's partition key | Query does not include the base table's partition key; cross-partition uniqueness |

"A local index's Tablet is forced to co-locate with the base table's Tablet" is the **physical basis** for "prefer local indexes" — it is not a matter of preference.

### 2.1 Global Indexes Are Not Forbidden — They Are a Cost Decision

The following scenarios **require or reasonably justify** a global index:

- Cross-partition uniqueness constraints (no alternative exists).
- High-frequency queries that entirely omit the base table's partition key, where changing the partition key would sacrifice a more important access path.
- The business can accept the distributed-transaction cost at write time, and benchmarking confirms it meets requirements.

Decision method: provide a quantified list of alternatives, not a blanket "writes are frequent, so global indexes are forbidden."

```yaml
index_decision:
  query:
  candidates:
    - option: local_index | global_index | redundant_table | duplicate_table | cache | async
      read_benefit:
      write_cost:
      consistency_impact:
      verdict: recommended | fallback | rejected
  chosen:
  must_benchmark: true | false
  sla_reference:               # Rejecting the design is only allowed when the SLA is clearly unmet
```

### 2.2 Interaction with Partition Operations

Adding a global index on top of a table that is archived by partition means every `DROP` / `TRUNCATE PARTITION` may trigger a global index rebuild (see `partitioning.md` §4.1). Archival-style tables default to local indexes only.

## 3. Primary Key Design: Separate Constraints from Optimization

The constraints are only the three in §1. The **column order** of the primary key is a separate optimization question:

| Goal | Primary key ordering recommendation |
|---|---|
| Keep data within a partition locally ordered in the LSM tree, reducing sorting and random reads | Put the columns matching the **query's sort/range-scan direction** first |
| Sequentialize writes, reducing compaction write amplification | Put **monotonically increasing columns** (timestamps, ordered IDs) as the prefix |
| Partition pruning | **Unrelated** to primary key order — it only needs to satisfy the subset rule in §1 |
| Automatic partition splitting | This is the only scenario that requires the partition key to be a **primary key prefix** |

Counter-example: a table partitioned by `RANGE(tx_time)` and point-queried by `order_id` gains nothing from forcing `tx_time` to the front of the primary key — it only forces point queries to add an extra condition.

The real cost of random keys (UUID / out-of-order Snowflake IDs) under an LSM tree (**not** "page splitting" — that's a B-Tree term):

- Poor ordering within the MemStore → higher write amplification from flushes/compactions
- Point queries must traverse more SSTable layers, lowering Bloom filter and cache hit rates
- Lower data compression ratio

Mitigation, in order of increasing cost:

1. Change the primary key to "ordered prefix + random column," and build a separate unique index on the random column;
2. Use an `ORGANIZATION = HEAP` heap table (≥ V4.3.5 BP1, **MySQL mode only**);
3. Change the ID-generation strategy on the application side.

## 4. The Extra Cost of Using an Auto-Increment Column as the Partition Key

When using an auto-increment column as the partition key in MySQL mode (per official guidance):

- The auto-increment column's value is globally unique, but **not guaranteed to increase monotonically within a partition**;
- Compared with other partitioning approaches, insert operations **cannot be routed effectively**, producing **cross-node transactions** and a measurable performance drop.

Therefore, using an auto-increment column directly as the partition key is not recommended; if unavoidable, the cross-node transaction cost must be stated in warnings.

The official "Hotspot Table Best Practices" guide gives an even earlier-stage recommendation: **avoid using an auto-increment ID as the primary key** (it tends to create write hotspots); use a composite primary key or a distributed ID generator instead — note this recommendation targets "as the primary key," which is broader in scope than "as the partition key."
For the ID-generation syntax differences between the two modes (MySQL `AUTO_INCREMENT` vs. Oracle `IDENTITY`/sequences), see `capability-matrix.md` §4; for the conflicting official guidance on type selection, see `doc-gaps.md` §5.2.

## 5. Index Tablets Count Toward Capacity

Every index partition corresponds to a Tablet — this applies to both local and global indexes. For capacity estimation, see `tablet-capacity.md`.

## 6. Beyond Local/Global: Another Category of Index

When the `WHERE` clause contains a JSON array containment predicate (`MEMBER OF` / `JSON_CONTAINS` / `JSON_OVERLAPS`)
or requires fuzzy full-text search / relevance ranking over large text, **neither local nor global indexes help** —
the only fallback is a full table scan. These needs require dedicated indexes; see [`special-indexes.md`](special-indexes.md):

- JSON multi-value index — note that "adding an index to an existing table" is gated by a hidden sys-tenant switch;
- Full-text index — note that Chinese-language corpora must not use `WITH PARSER SPACE`.

Dedicated indexes still go through the `index_decision` cost-decision contract in §2.1; this section only ensures they are not overlooked.

### 6.1 Index-Level Column Groups (Columnstore Index / Row-Store Index)

Officially, "row-store table + columnstore index" and "columnstore table + row-store index" are listed as independent HTAP storage architectures,
but **no DDL syntax is given** — this is C3, and can only go into `candidate_ddl`. See `storage-format.md` §2.1.

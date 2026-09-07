# Storage Format: Row Store, Skip Index, Columnstore, Row-Column Redundancy, Columnstore Replica, Queuing Table

<!-- toc -->

**Table of Contents**

- [1. The Real Semantics of the Three Column Group Syntaxes (the Easiest Place to Get Wrong)](#1-the-real-semantics-of-the-three-column-group-syntaxes-the-easiest-place-to-get-wrong)
  - [1.1 "Omitting Column Group Means Row Store" Does Not Hold](#11-omitting-column-group-means-row-store-does-not-hold)
  - [1.2 The format is not frozen at `CREATE TABLE` — conversion is an `ALTER`](#12-the-format-is-not-frozen-at-create-table--conversion-is-an-alter)
- [2. Storage Format Decision: Two Independent Axes, Not a Single Mutually-Exclusive Chain](#2-storage-format-decision-two-independent-axes-not-a-single-mutually-exclusive-chain)
  - [Axis 2: Deployment Overlay (Decide First, Highest Priority)](#axis-2-deployment-overlay-decide-first-highest-priority)
  - [Axis 1: In-Table Format (Mutually Exclusive, Take the First Match)](#axis-1-in-table-format-mutually-exclusive-take-the-first-match)
  - [2.1 Official Overhead Comparison of the Four HTAP Storage Architectures](#21-official-overhead-comparison-of-the-four-htap-storage-architectures)
- [3. Skip Index: Low-Cost Aggregation Acceleration](#3-skip-index-low-cost-aggregation-acceleration)
- [4. Columnstore Replica: a Deployment Topology Decision, Not a Hint](#4-columnstore-replica-a-deployment-topology-decision-not-a-hint)
- [5. Queuing Table / Buffer Table: `TABLE_MODE = 'QUEUING'`](#5-queuing-table--buffer-table-table_mode--queuing)
  - [5.1 The Real Difference Between the Five Values: Major Compaction Trigger Aggressiveness, Not "Queue Intensity"](#51-the-real-difference-between-the-five-values-major-compaction-trigger-aggressiveness-not-queue-intensity)
  - [5.2 Determination Inputs and Companion Design](#52-determination-inputs-and-companion-design)
- [6. Table Organization: Index-Organized Table vs. Heap Table](#6-table-organization-index-organized-table-vs-heap-table)

<!-- /toc -->

## 1. The Real Semantics of the Three Column Group Syntaxes (the Easiest Place to Get Wrong)

| Syntax | Actual behavior | Storage cost | Applicable to |
|---|---|---|---|
| Omitting Column Group | **Takes the tenant default**, see the warning below — this is not unconditionally row store | Depends on the default value | — |
| `WITH COLUMN GROUP(all columns)` | All columns are grouped into one group and **stored by row** (equivalent to row store) | 1× | TP; **only writing it explicitly guarantees row store** |
| `WITH COLUMN GROUP(each column)` | Each column forms its own group — **a pure columnstore table** | ≈1× (columnstore compression is usually better) | **Pure AP** |
| `WITH COLUMN GROUP(all columns, each column)` | **A row-column redundant table**: stores an **extra copy in row format** on top of the columnstore copy | ≈2× | **Same-table HTAP** |

Conclusion: writing `all columns, each column` for a "pure analytics table" is wrong — it wastes storage on an unnecessary extra row-store copy. Use `each column` for pure AP.

### 1.1 "Omitting Column Group Means Row Store" Does Not Hold

The tenant-level configuration item **`default_table_store_format`** (≥ V4.3.0, default `row`,
value range `("row", "column", "compound")`) determines the actual format used when `WITH COLUMN GROUP` is omitted.
The official semantics are that it **automatically appends a clause**:

| `default_table_store_format` | The CREATE TABLE statement is automatically appended with | Actual behavior |
|---|---|---|
| **`row` (default)** | Nothing | A row-store table (1×) |
| `column` | `with column group(each column)` | **A pure columnstore table** |
| `compound` | `with column group(all columns, each column)` | **A row-column redundant table (≈2× storage)** |

This is a parameter that **the tenant can change, and it takes effect via `ALTER SYSTEM SET` without a restart**. So in a tenant whose default has
been changed to `column`, the assumption "omitting Column Group gives you a TP row-store table" **silently becomes wrong**,
and this file's 1×/≈2× storage conclusions become invalid as well.

Three official boundary conditions (check each one against the original parameter documentation):

1. **Only applies to CREATE TABLE statements that do not contain a `with column group` clause**;
2. **Does not apply to index tables**;
3. Only applies to **user tenants**; it does not affect the sys / meta tenants.

Therefore:

1. Step 0 must obtain this parameter (`SHOW PARAMETERS LIKE '%store_format%'`, see `input-collection.md` §5);
   if it cannot be obtained → mark both `storage_mode.table_format` and `storage_overhead` as `unverified`.
2. **L1 default recommendation: always write the Column Group clause explicitly**, including writing
   `WITH COLUMN GROUP(all columns)` even when you want row store. This recommendation is based on point 1 above — **once the clause is written, the parameter no longer applies**,
   so the explicit form makes the DDL's semantics consistent regardless of the tenant default, and lets Review mode determine the format from the DDL alone.

The same logic applies to `default_table_organization` (§6) and `DEFAULT_AUTO_INCREMENT_MODE`
(`capability-matrix.md` §4.1) — all three are "omit it and you get the tenant default" traps.

Syntax position (consistent across both modes): the Column Group clause comes **after the partition option**, at the end of the statement.

```sql
CREATE TABLE fact_sales (...)
  COMMENT 'xxx' DEFAULT CHARSET = utf8mb4        -- table option comes first
  PARTITION BY RANGE COLUMNS(stat_date) (...)     -- partition option comes in the middle
  WITH COLUMN GROUP(each column);                 -- column group comes last
```

### 1.2 The format is not frozen at `CREATE TABLE` — conversion is an `ALTER`

Easy to assume otherwise, and the assumption leads to the wrong sequencing advice. Oracle mode supports converting
between all three in-table formats after the fact:

| From → to | Statement |
|---|---|
| row → columnstore | `ALTER TABLE t ADD COLUMN GROUP(each column);` |
| row → row-column redundant | `ALTER TABLE t ADD COLUMN GROUP(all columns, each column);` |
| redundant → columnstore | `ALTER TABLE t DROP COLUMN GROUP(all columns);` |
| redundant → row | `ALTER TABLE t DROP COLUMN GROUP(each column);` |

Note the semantics: the clause **declares the target set of column groups**, it does not append to what is there.

Two consequences for how the Agent should sequence a design:

- **For a large initial load, prefer "create as row store → load → build indexes → convert".** Writing a second
  physical copy during a bulk import is pure overhead, and it compounds with the index-build guidance in
  `sources.md` § Indexing large tables. Recommend the conversion as a separate step rather than folding it into
  `CREATE TABLE`.
- **It also side-steps an unverified clause-ordering question.** The official plain-`CREATE TABLE` example carrying
  `WITH COLUMN GROUP` has no partition clause, so "partition clause followed by `WITH COLUMN GROUP`" has no official
  example even though the clause order is documented (`doc-gaps.md` §7-3). Converting by `ALTER` avoids the question
  entirely.

Conversion cost is **not documented** — for a large table this writes an entire additional physical copy, so treat
duration and lock behaviour as `unverified` and require a timed test before scheduling it.

## 2. Storage Format Decision: Two Independent Axes, Not a Single Mutually-Exclusive Chain

Two things must be kept separate here — collapsing them into a single "first match wins" chain would mean a scenario that genuinely needs physical isolation never reaches the columnstore-replica branch:

- **Axis 1 | In-table format**: how the table itself is stored (row store / row store + Skip Index / pure columnstore / row-column redundant). **Mutually exclusive — take the first match.**
- **Axis 2 | Deployment overlay**: whether to additionally introduce a read-only columnstore replica to physically isolate AP traffic. **Orthogonal to Axis 1** — even when using a columnstore replica, the base table must still pick a format under Axis 1.

Decide Axis 2 first (it changes the trade-off in Axis 1), then decide Axis 1.

```
Input dimensions (all come from Step 1; if any is missing, output unverified):
  analysis_freq      Analytical query frequency: realtime | daily | weekly | monthly | none
  scan_width_ratio   Number of columns scanned by a typical query / total columns in the table
  query_shape        aggregation_only | multidim (multi-condition GROUP BY / window functions / multi-dimensional drill-down)
  isolation_required Whether TP and AP need physical isolation
  data_size_gb
```

### Axis 2: Deployment Overlay (Decide First, Highest Priority)

```
IF isolation_required = true
  THEN check the §4 preconditions (OB ≥ 4.3.3 / OBProxy ≥ 4.3.2 / dedicated ODP cluster / replica type)
    - All satisfied     → adopt a columnstore replica, deployment_overlay = columnstore_replica
                          and the base table is decided under Axis 1 (usually lands on row, with AP traffic routed to the replica)
    - Any unsatisfied   → deployment_overlay = none, and state in warnings
                          "physical isolation is not possible; AP and TP will share the same replica resources"
                          then decide under Axis 1 (in this case same-table HTAP usually lands on row-column redundancy)
ELSE deployment_overlay = none
```

### Axis 1: In-Table Format (Mutually Exclusive, Take the First Match)

```
1. analysis_freq ∈ {none, monthly}                       → row store (default)
2. analysis_freq = weekly and query_shape = aggregation_only
                                                          → row store + SKIP_INDEX (see §3)
3. scan_width_ratio > 0.5 and query_shape = aggregation_only
                                                          → row store + SKIP_INDEX
4. A pure AP table (no TP point-query/update path)        → pure columnstore, WITH COLUMN GROUP(each column)
5. The same table has both high-frequency TP point queries and analysis_freq ≥ daily multi-dimensional analysis
     5a. deployment_overlay = columnstore_replica          → base table uses row store, AP traffic goes to the columnstore replica
     5b. Workload is mostly TP, AP is only light queries    → row-store table + **columnstore index** (§2.1, C3 → candidate_ddl)
     5c. Workload is mostly AP, TP is only occasional point queries → columnstore table + **row-store index** (§2.1, C3 → candidate_ddl)
     5d. Both TP and AP are heavy and need strong consistency + automatic routing → row-column redundancy, WITH COLUMN GROUP(all columns, each column)
6. Otherwise                                               → row store (write all columns explicitly)
```

Note: `data_size_gb` is **not** a reason to enable columnstore. A large data volume with low analytical frequency still goes to row store.

### 2.1 Official Overhead Comparison of the Four HTAP Storage Architectures

The official "Table Design and Index Optimization Best Practices" guide's "Storage architecture selection" splits HTAP into four tiers.
This Skill originally covered only two of them (row-column redundancy, columnstore replica), so **when facing "TP-dominant + light AP," it
could only recommend row-column redundancy at ≈2× storage — far more expensive than actually necessary**. The complete comparison of all four tiers:

| Architecture | Applicable to | Performance characteristics | Storage overhead (per official guidance) | Confirmation tier |
|---|---|---|---|---|
| Row-store table + **columnstore index** | TP-dominant, light AP | High write performance; limited AP optimization | **Index storage +30%–50%** | **C3** (official docs give no DDL syntax, see `capability-matrix.md` §5-6) |
| Columnstore table + **row-store index** | AP-dominant, occasional TP point queries | Best analytical performance; TP relies on the index as a fallback | **Full data stored twice** | **C3** (same as above) |
| Row-column redundancy (same table) | TP / AP balanced | Strongly consistent, automatic routing | **+100% (≈2×)** | C1 |
| Columnstore replica (2F1A1C) | Standalone AP analysis | Read/write isolation, **eventually consistent** | Storage of one additional replica | See §4 preconditions |

Three points that are easy to get wrong:

- **The first two tiers can currently only go into `candidate_ddl`**. The official documentation gives the architecture and the overhead but no syntax,
  and the `index_option` production in the V4.5.0 CREATE TABLE BNF has no column-group rule either.
  Per this Skill's capability confirmation tier rules (SKILL.md, section 2), C3 items must not go into the primary DDL.
- **The columnstore replica is eventually consistent**; the other three tiers are strongly consistent. An AP query with `strong_consistency = true`
  must not be routed to the columnstore replica — this is more easily overlooked than the capacity/version preconditions.
- "+30%–50%," "stored twice," and "+100%" are official order-of-magnitude figures — **do not convert them into a specific GB value and treat it as a measured result**.

Output:

```yaml
storage_mode:
  table_format: row | row_with_skip_index | column | row_column_redundant
                | row_with_column_index | column_with_row_index   # The latter two are C3
  deployment_overlay: none | columnstore_replica
  tenant_default_store_format: row | column | compound | unverified   # Required, see §1.1
  format_written_explicitly: true | false    # When false, the previous field determines the actual format
  axis2_decision:           # The isolation_required value + item-by-item conclusions on the preconditions
  axis1_branch:             # The matched branch number + the values of each input dimension
  ddl_fragment:
  storage_overhead:         # Row-column redundancy must state ≈2×; columnstore index +30%-50%; columnstore + row-store index = stored twice
  consistency_model: strong | eventual        # Only the columnstore replica is eventual
  confirmation_tier: C1 | C3                  # C3 → can only go into candidate_ddl
  unmet_isolation_warning:  # Required when isolation_required=true but the preconditions are not met
```

## 3. Skip Index: Low-Cost Aggregation Acceleration

Add pre-aggregated metadata to a column on a row-store table, used to skip irrelevant macro blocks:

```sql
c_amount DECIMAL(18,2) SKIP_INDEX(MIN_MAX, SUM),
c_stat_date DATE SKIP_INDEX(MIN_MAX)
```

- `MIN_MAX`: filtering / range pruning
- `SUM`: numeric column aggregation

This is the correct answer for "low-frequency full-table aggregation" scenarios — far cheaper than columnstore or row-column redundancy. A table that previously "didn't meet the conditions for columnstore" should not be left without a solution. For the minimum supported version, see `capability-matrix.md` §5-3.

## 4. Columnstore Replica: a Deployment Topology Decision, Not a Hint

Preconditions (all must be satisfied):

- **The deployment must be able to host an additional replica.** A columnstore replica *is* an extra replica, so a
  single-replica / single-node deployment has nowhere to put one — this is a structural blocker, and it should be
  checked **first**, before the version and ODP items below, because no amount of version upgrading fixes it.
  When it fails, Axis 2 resolves to `none` and `unmet_isolation_warning` is mandatory: TP and AP will contend for
  the same replica's CPU and I/O. On a **shared cluster** add that CPU is isolated per tenant but **disk I/O at the
  OBServer level is not**, so an AP scan degrades neighbouring tenants too — that is usually a bigger practical risk
  than the storage overhead of whichever Axis-1 format gets chosen instead.
- OceanBase Database ≥ **V4.3.3**
- OBProxy ≥ **V4.3.2**
- **Deploy a separate OBProxy (ODP) cluster** dedicated to accessing the columnstore replica
- When creating the tenant or adding a replica, set the replica type to **read-only columnstore replica**
- The V4.3.3 documentation marks this as an **experimental feature**, suitable for scenarios requiring strong physical isolation between TP and AP

Related parameters on the ODP side: `proxy_route_policy`, `route_target_replica_type`.

**Do not** suggest using `/*+ READ_CONSISTENCY(WEAK) */` or `QUERY_TIMEOUT` to "route to the columnstore" — the former is only a weak-consistency read, and the latter is only a timeout setting; neither can specify the replica type.

```yaml
columnstore_replica_check:
  ob_version:                    # ≥ V4.3.3
  obproxy_version:               # ≥ V4.3.2
  dedicated_odp_cluster: true | false
  replica_type_configured: true | false
  result: supported | unsupported
  note: experimental_in_4_3_3
```

## 5. Queuing Table / Buffer Table: `TABLE_MODE = 'QUEUING'`

Identifying characteristics: **high-frequency inserts + high-frequency deletes; the table stays nearly empty long-term, but scans keep getting slower** (typical examples: task queues, pending transaction logs, message relay tables). The cause is that a large number of delete markers drives up scan cost.

```sql
CREATE TABLE task_queue (...) TABLE_MODE = 'QUEUING';
-- Existing tables can also be changed
ALTER TABLE task_queue TABLE_MODE = 'queuing';
```

### 5.1 The Real Difference Between the Five Values: Major Compaction Trigger Aggressiveness, Not "Queue Intensity"

Per official guidance: **every value except `NORMAL` counts as a QUEUING table**; the difference between them is
**the probability of triggering a major compaction after a minor compaction**:

| Value | Probability of triggering a major compaction after a minor compaction | Meaning |
|---|---|---|
| `NORMAL` | Extremely low | The default. Suitable for scenarios with no high performance requirements on either writes or read consistency |
| `QUEUING` | Low | A basic queuing table; slightly nudges major compaction |
| `MODERATE` | Medium | More actively drives major compaction, balancing performance against resource consumption |
| `SUPER` | High | Frequent major compaction, suitable for workloads that are **sensitive to query latency** |
| `EXTREME` | Extremely high | The most aggressive; does its best to complete major compaction |

So the selection axis is **the trade-off between "query latency sensitivity" and "resource consumption of major compaction,"**
not "the longer the queue, the stronger the setting you pick." Framing it as "choose in increasing order of queue intensity" would steer the user toward the wrong criterion:

- Scans have already visibly degraded and query latency is sensitive → lean toward `SUPER` / `EXTREME`;
- Cluster resources are tight and scan degradation is tolerable → stop at `QUEUING` / `MODERATE`;
- When no measured data is available on "the extent of scan degradation caused by delete markers," **default to `QUEUING`**,
  and leave the decision to escalate to the V5 benchmarking conclusion (this is an L2 threshold to be verified, and must not be written as "must use EXTREME").

### 5.2 Determination Inputs and Companion Design

Inputs required for the determination: Step 1 must collect `delete_qps` and `steady_row_count` (see `input-collection.md` §4 for how to obtain them).
If `delete_qps` is of the same order of magnitude as `insert_qps` and the steady-state row count is far smaller than the cumulative write volume → classify it as a queuing table.

`TABLE_MODE` is only a mitigation; the official documentation also requires two companion measures:

1. **Partition by time**, so old data retires as whole partitions;
2. **Replace bulk `DELETE` with `TRUNCATE PARTITION` / `DROP PARTITION`** — this is the actual fix,
   because under an LSM-tree, `DELETE` only writes a delete marker; only a partition-level operation actually reclaims space.
   For the interaction with archival design (global index rebuild), see `partitioning.md` §4.1.

## 6. Table Organization: Index-Organized Table vs. Heap Table

| | `ORGANIZATION = INDEX` (index-organized table) | `ORGANIZATION = HEAP` (heap table) |
|---|---|---|
| Data order | Ordered by primary key | Not organized by primary key |
| Cost of a random primary key | High (see `indexes.md` §3) | Low |
| Version / mode | Universal | ≥ V4.3.5 BP1, **MySQL mode only** |

When omitted, the value comes from the configuration item `default_table_organization`.

```yaml
table_organization:
  type: INDEX | HEAP
  compat_mode_supported: true | false
  version_supported: true | false
  reason:
  bulk_load_requirement:
```

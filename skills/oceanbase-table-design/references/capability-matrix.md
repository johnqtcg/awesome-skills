# Capability Matrix: Version × Edition × Compatibility Mode × Feature

> Syntax baseline: **OceanBase V4.5.0** (`mysql_mode_create_table_syntax.md` / `oracle_mode_create_table_syntax.md`).
> Usage: once Step 0 obtains `ob_version` / `edition` / `compat_mode`, **check this table first**. Any combination marked "✗ / not supported" is an L0 hard constraint — block DDL generation and provide an alternative.

<!-- toc -->

**Table of Contents**

- [0. Edition gate (`edition`) — must be checked before compatibility mode](#0-edition-gate-edition--must-be-checked-before-compatibility-mode)
- [1. Partitioning capabilities](#1-partitioning-capabilities)
  - [1.1 MySQL-mode partition key type allowlist (official partition key rules documentation)](#11-mysql-mode-partition-key-type-allowlist-official-partition-key-rules-documentation)
  - [1.2 Cross-mode partition syntax mapping (check before generating DDL)](#12-cross-mode-partition-syntax-mapping-check-before-generating-ddl)
- [2. Storage and table format](#2-storage-and-table-format)
  - [2.1 ⚠ Tenant default gate (must be collected at Step 0, or conclusions about table format and organization will be wrong)](#21--tenant-default-gate-must-be-collected-at-step-0-or-conclusions-about-table-format-and-organization-will-be-wrong)
- [3. Physical coordination](#3-physical-coordination)
- [4. Auto-increment columns / primary key numbering (**branches by compatibility mode — do not reuse the same syntax**)](#4-auto-increment-columns--primary-key-numbering-branches-by-compatibility-mode--do-not-reuse-the-same-syntax)
  - [4.1 ORDER / NOORDER and skipped numbers (semantics shared by both modes)](#41-order--noorder-and-skipped-numbers-semantics-shared-by-both-modes)
  - [4.2 When NOORDER can be chosen (official criteria)](#42-when-noorder-can-be-chosen-official-criteria)
  - [4.3 Using an auto-increment column as the partition key](#43-using-an-auto-increment-column-as-the-partition-key)
- [5. Open items (no guessing allowed — must be marked `unverified`)](#5-open-items-no-guessing-allowed--must-be-marked-unverified)
- [6. Behavior when the target environment does not meet requirements](#6-behavior-when-the-target-environment-does-not-meet-requirements)

<!-- /toc -->

## 0. Edition gate (`edition`) — must be checked before compatibility mode

| Capability | Enterprise Edition | Community Edition |
|---|---|---|
| **Oracle syntax compatibility** | Supported | **Not supported** |
| MySQL syntax and protocol compatibility | Supported | Supported |
| Storage-compute separation architecture / standalone log service | Supported | Not supported |
| Arbitration Service | Supported | Not supported |
| Advanced SQL Plan Management (SPM) | Supported | Not supported |
| Audit | Supported | Not supported |
| CLOG storage compression | Supported | Not supported |
| Row-level labels / TDE / national cryptography RPC encryption / passwordless TLS login | Supported | Not supported |
| Columnstore engine, global index, materialized view, partition split, partition exchange, vector/full-text index | Supported | Supported |
| Partitioning (Range/Hash/List) | Supported; Oracle compatibility mode additionally supports INTERVAL partitioning | Supported |

**L0 combination block**: `edition = community` + `compat_mode = oracle` → reject immediately, explain that the Community Edition kernel does not provide Oracle syntax compatibility, and give two ways forward (rewrite the DDL in MySQL mode / switch to Enterprise Edition).

Corollary: in a Community Edition environment, every "Oracle-mode only" capability in this file (INTERVAL partitioning, etc.) is unavailable.

## 1. Partitioning capabilities

> ⚠ **Oracle mode has no `COLUMNS` keyword.** `COLUMNS` is a MySQL-style construct; Oracle mode's `RANGE` / `LIST` / `HASH` take a column list directly, which already supports multiple columns. Writing `PARTITION BY RANGE COLUMNS(...)` in Oracle mode is a syntax error. See §1.2 for the syntax mapping.

| Feature | Minimum version | MySQL mode | Oracle mode | Notes |
|---|---|---|---|---|
| RANGE | 4.x | ✓ `RANGE(expr)`: partition key must be **integer or YEAR**, **single column only**, expressions allowed | ✓ `RANGE(column_name_list)`: **no COLUMNS keyword**, natively supports multiple columns, expressions not accepted | The two modes use different syntax — do not copy one to the other |
| RANGE COLUMNS | 4.x | ✓ `RANGE COLUMNS(cols)`: wider type support, **expressions not allowed**, supports multiple columns (see §1.1) | **✗ this form does not exist** | Multi-column range partitioning in Oracle mode is written as `RANGE(c1, c2)` |
| LIST | 4.x | ✓ `LIST(expr)`: integer or YEAR, **single column only**, expressions allowed | ✓ `LIST(column_name_list)`: **no COLUMNS keyword**, supports multiple columns | The enumeration syntax differs between modes — see `doc-gaps.md` §1 |
| LIST COLUMNS | 4.x | ✓ wider type support, expressions not allowed, supports multiple columns | **✗ this form does not exist** | Oracle mode uses `LIST(c1, c2)` |
| HASH | 4.x | ✓ `HASH(expr)`: partition key must be **integer or YEAR**, expressions allowed | ✓ `HASH(column_name_list)`: accepts a column list, expressions not accepted | Semantics differ between modes — do not apply the same rule to both |
| KEY | 4.x | ✓ any type except TEXT/BLOB; expressions not allowed; vector supported; an empty `KEY()` list means "use the primary key" | **✗ does not exist** | Oracle mode uses `HASH(col_list)` for multi-column keys |
| INTERVAL | — | **✗ does not exist** | ✓ `RANGE(column_name) INTERVAL(expr)` | **Single column only** (note: unlike ordinary RANGE); unavailable in Community Edition |
| Subpartitioning (templated / non-templated) | 4.x | ✓ | ✓ | In Oracle mode, non-templated subpartitions are defined inside each partition item; templated subpartitions use `SUBPARTITION TEMPLATE` |
| Automatic partition split `SIZE('...')` | ≥ V4.3.5 | ✓ `RANGE [COLUMNS](cols) SIZE(...)` | ✓ `RANGE(cols) SIZE(...)` | **Just a modifier clause on RANGE**; see `partitioning.md` §3 for restrictions |
| `DYNAMIC_PARTITION_POLICY` | see "Open items" | ✓ | ✓ | Automatic partition pre-creation / expiration management. **Confirmation tier: target = V4.5.0 → C1; target < V4.5.0 → C2, may only enter `candidate_ddl`**. The Oracle-mode C1 alternative is `INTERVAL` |
| Max partitions per table | 4.x | Tenant config item `max_partition_num`: default **8192**, range **[8192, 65536]**, adjustable via `ALTER SYSTEM SET` | **Fixed at 65536**, **does not use** `max_partition_num` | L0: partition count of the primary table × subpartition count ≤ the limit for that mode. The official docs state `max_partition_num` "applies only to MySQL mode" — do not apply it to Oracle mode |

### 1.1 MySQL-mode partition key type allowlist (official partition key rules documentation)

| Partition type | Allowed partition key types | Expressions | Multi-column |
|---|---|---|---|
| RANGE | Integer types, YEAR | Allowed | ✗ single column only |
| RANGE COLUMNS | All integer types; DOUBLE / FLOAT / DECIMAL (DEC/NUMERIC/FIXED/REAL, etc.); DATE / DATETIME / **TIMESTAMP**; CHAR / VARCHAR / BINARY / VARBINARY. **TEXT / BLOB not supported**, no other date/time types supported | ✗ | ✓ |
| LIST | Integer types, YEAR | Allowed (column name or expression) | ✗ single column only |
| LIST COLUMNS | All integer types (**DECIMAL / FLOAT not supported**); DATE / DATETIME (**TIMESTAMP not included**); CHAR / VARCHAR / BINARY / VARBINARY. TEXT / BLOB not supported | ✗ | ✓ |
| HASH | Integer types, YEAR | Allowed | Determined by the expression |
| KEY | Any type except TEXT / BLOB | ✗ | ✓ (vector supported) |

Partition expressions may only use functions from the official allowlist (`ABS()` / `CEILING()` / `DAY()` / `DAYOFMONTH()` / `DAYOFWEEK()` / `DAYOFYEAR()` / `DATEDIFF()` / `EXTRACT()` / `UNIX_TIMESTAMP()`, etc.); using a function outside the allowlist causes table creation to fail.

### 1.2 Cross-mode partition syntax mapping (check before generating DDL)

| Requirement | MySQL mode | Oracle mode |
|---|---|---|
| Single-column integer range partitioning | `PARTITION BY RANGE(id)` | `PARTITION BY RANGE(id)` |
| Single-column date range partitioning | `PARTITION BY RANGE COLUMNS(dt)` (or `RANGE(UNIX_TIMESTAMP(dt))`) | `PARTITION BY RANGE(dt)` |
| **Multi-column** range partitioning | `PARTITION BY RANGE COLUMNS(c1, c2)` | `PARTITION BY RANGE(c1, c2)` |
| Single-column enumerated partitioning | `PARTITION BY LIST(code)` (integer/YEAR) or `LIST COLUMNS(code)` (string) | `PARTITION BY LIST(code)` |
| **Multi-column** enumerated partitioning | `PARTITION BY LIST COLUMNS(c1, c2)` | `PARTITION BY LIST(c1, c2)` |
| Single-column integer HASH | `PARTITION BY HASH(id) PARTITIONS n` | `PARTITION BY HASH(id) PARTITIONS n` |
| **Multi-column / non-integer** HASH-family partitioning | `PARTITION BY KEY(c1, c2) PARTITIONS n` | `PARTITION BY HASH(c1, c2) PARTITIONS n` |
| Automatic partition expansion (time-based) | Target = V4.5.0: `DYNAMIC_PARTITION_POLICY = (...)` (C1); lower versions: pre-create partitions + ops script, `DYNAMIC_PARTITION_POLICY` downgrades to candidate (C2) | **Primary approach `RANGE(dt) INTERVAL(...)` (C1)**; `DYNAMIC_PARTITION_POLICY` is C2 and may only enter `candidate_ddl` — the two **must not both appear in the primary DDL** |
| Enumeration fallback partition | `PARTITION p_def VALUES IN (DEFAULT)` | `PARTITION P_DEF VALUES (DEFAULT)` |

**Forbidden combinations**: Oracle mode + `COLUMNS`; Oracle mode + `PARTITION BY KEY`; MySQL mode + `INTERVAL`; MySQL mode + `VALUES (...)` (should be `VALUES IN (...)`); Oracle mode + `VALUES IN (...)`. These are jointly blocked by `scripts/check_consistency.py` and the V1 static check.

## 2. Storage and table format

| Feature | Minimum version | MySQL mode | Oracle mode | Notes |
|---|---|---|---|---|
| `WITH COLUMN GROUP(each column)` pure columnstore | ≥ V4.3.0 | ✓ | ✓ | Semantics in `storage-format.md` §1; Community Edition also supports the columnstore engine |
| `WITH COLUMN GROUP(all columns, each column)` row-column redundancy | ≥ V4.3.0 | ✓ | ✓ | **Stores an extra row-storage copy**, roughly 2× the cost |
| ColumnStore Replica | ≥ **V4.3.3**, OBProxy ≥ **V4.3.2** | ✓ | ✓ | Requires **a separately deployed ODP cluster**; flagged as an experimental feature in the V4.3.3 docs |
| `SKIP_INDEX(MIN_MAX \| SUM)` | see "Open items" | ✓ | ✓ | Low-cost aggregation/filter acceleration on row-store tables. **Same confirmation tier as above: target = V4.5.0 → C1; lower versions → C2** |
| `ORGANIZATION = {INDEX \| HEAP}` heap table | ≥ V4.3.5 BP1 | ✓ | **✗** (not present in the official V4.5.0 Oracle-mode option list — verified against the source) | Defaults to the config item `default_table_organization` |
| `TABLE_MODE = 'QUEUING'` queuing table | 4.x | ✓ | ✓ | Values `NORMAL/QUEUING/MODERATE/SUPER/EXTREME`; semantic differences in `storage-format.md` §5 |
| `DUPLICATE_SCOPE = 'cluster'` duplicated table | 4.x | ✓ | ✓ | `CREATE TABLE t(...) DUPLICATE_SCOPE = 'cluster';` |
| **Index-level Column Group** (row-store table + columnstore index / columnstore table + row-store index) | same as columnstore (≥ V4.3.0) | ✓ | ✓ | The official "Table Design and Index Optimization" guide lists these as independent forms under "Storage architecture selection"; see `storage-format.md` §2 axis 1, branches 4b/4c. **The syntax position and form are not given in the V4.5.0 CREATE TABLE BNF → C3, may only enter `candidate_ddl`** |

### 2.1 ⚠ Tenant default gate (must be collected at Step 0, or conclusions about table format and organization will be wrong)

Three tenant-level config items determine the actual format when the DDL **does not explicitly write** the corresponding clause. Asserting that "no Column Group clause means row storage" without checking these three values is guesswork:

| Config item | Value range (**default in bold**) | Effect | When not collected |
|---|---|---|---|
| `default_table_store_format` (≥ V4.3.0) | `("row", "column", "compound")`, default **`row`** | Determines the table's actual format when **`WITH COLUMN GROUP` is not written**. The official semantics are to **append the clause automatically**: `column` → auto-adds `with column group(each column)`; `compound` → auto-adds `with column group(all columns, each column)` (≈2× storage) | Mark both `storage_mode.table_format` and `storage_overhead` as `unverified` |
| `default_table_organization` | `INDEX` / `HEAP` | Determines whether the table is index-organized or a heap table when `ORGANIZATION` is not written | Mark `table_organization.type` as `unverified` |
| `DEFAULT_AUTO_INCREMENT_MODE` | `order` / `noorder`, default **`order`** from V4.0+ | Determines the numbering mode when `AUTO_INCREMENT_MODE` is not written | Mark auto-increment skipped-number/monotonicity conclusions as `unverified` |

Three boundary conditions for `default_table_store_format` (verified line by line against the official parameter description):

1. **Only takes effect for CREATE TABLE statements that do not contain a `with column group` clause** — once the clause is written, the parameter no longer applies.
   This is exactly the official basis for the L1 recommendation below, not a workaround invented by this Skill.
2. **Has no effect on index tables** (`is invalid for index tables`).
3. Only applies to **user tenants**, not the sys tenant or meta tenant; changeable via `ALTER SYSTEM SET`, taking effect **without a restart**.

So the default really is `row` — but it is a parameter that **a tenant can change, with immediate effect**, so "no Column Group clause means row storage" holds "by default," not "unconditionally." Treating it as an unconditional fact in an environment where the parameter has not been checked will produce a conclusion that is the opposite of reality on a tenant whose default has been changed.

See `input-collection.md` §5 for how to collect it:

```sql
SHOW PARAMETERS LIKE '%store_format%';
SHOW PARAMETERS LIKE '%default_table_organization%';
```

**Mitigation (L1 default recommendation)**: do not rely on the tenant default — if row storage is needed, write
`WITH COLUMN GROUP(all columns)` explicitly; if columnstore is needed, write `WITH COLUMN GROUP(each column)` explicitly.
An explicit clause keeps the DDL's semantics consistent regardless of the tenant default, which is more reliable than checking the parameter.

## 3. Physical coordination

| Feature | Minimum version | Notes |
|---|---|---|
| `CREATE TABLEGROUP ... SHARDING = 'NONE\|PARTITION\|ADAPTIVE'` | ≥ V4.2.0 | Starting from V4.2.0, Table Groups no longer have a partition concept — they only define SHARDING |
| **Semantic change to `SHARDING = NONE`** | **V4.4.2 BP1** | < BP1: `NONE` implied "all partitions concentrated on a single node"; **≥ BP1: this semantic is removed** — distribution range now depends on `SCOPE`. Risk assessment must branch by version — see `tablegroup.md` §2.1 for details |
| Table Group `SCOPE` (`SERVER` / `ZONE` / `CLUSTER`) | ≥ **V4.4.2 BP1** | Controls the Leader distribution range of the Partition Group; a Table Group upgraded from an older version has `SCOPE` = NULL |

## 4. Auto-increment columns / primary key numbering (**branches by compatibility mode — do not reuse the same syntax**)

This is the section of this file most prone to error: **the entire `AUTO_INCREMENT` family is MySQL-mode only**.
Oracle mode's `table_option` production has **none** of `AUTO_INCREMENT`, `AUTO_INCREMENT_MODE`, or
`auto_increment_cache_size` (verified line by line against `oracle_mode_create_table_syntax.md`);
Oracle mode uses **the IDENTITY column property** or **sequences** instead. Carrying MySQL syntax over into Oracle mode is an L0 violation.

| Capability | MySQL mode | Oracle mode |
|---|---|---|
| Column-level auto-increment | ✓ column attribute `AUTO_INCREMENT` | **✗ does not exist**; use `GENERATED BY DEFAULT AS IDENTITY` or `GENERATED ALWAYS AS IDENTITY` instead |
| `AUTO_INCREMENT_MODE = 'ORDER' \| 'NOORDER'` (table option) | ✓ confirmed as a table option by both the official auto-increment column docs and "Auto-Increment Columns and Sequences Best Practices"; but **not included in the V4.5.0 CREATE TABLE BNF** (see `doc-gaps.md` §2) | **✗ not in the table_option list** |
| `AUTO_INCREMENT_CACHE_SIZE` (table option / system variable) | ✓ | **✗** |
| Cross-table numbering | No native sequence semantics — requires a hand-built numbering table | ✓ `CREATE SEQUENCE`, can span tables, supports `CYCLE` |

### 4.1 ORDER / NOORDER and skipped numbers (semantics shared by both modes)

| Mechanism | Default | Semantics |
|---|---|---|
| Auto-increment column | **ORDER** (compatible with MySQL behavior) | Globally ordered numbering; requires cross-node coordination; expensive under high concurrency |
| Sequence (Oracle mode) | **NOORDER** (compatible with Oracle behavior) | Best performance; guarantees uniqueness only, not order |

- When `AUTO_INCREMENT_MODE` is not written at the table level, the **tenant-level parameter `DEFAULT_AUTO_INCREMENT_MODE`**
  applies (default `order` from V4.0 onward; only `noorder` was supported before V4.0). So "not written means ORDER" holds
  only when the default has not been changed — Step 0 must collect this parameter; see §2.1.
- NOORDER **guarantees global uniqueness only, not global monotonicity**; within a partitioned table it can still guarantee per-partition increment.
- **The magnitude of a skip is determined by `AUTO_INCREMENT_CACHE_SIZE`** (default **1000000**). A larger cache improves performance
  but produces a larger single gap on primary/standby switchover or node failure. This is the real reason "NOORDER should use BIGINT";
  if the business cannot tolerate gaps, reduce the cache (e.g., 10000), accepting reduced write performance.
  **The MySQL-mode option is an integer** (`auto_increment_cache_size [=] INT_VALUE`); `NOCACHE` is an Oracle `CREATE SEQUENCE` clause and does not exist in MySQL mode.
  Mixing the two produces a syntax error, not a slower-but-gapless table (`doc-gaps.md` §2.3.1).
- Starting from V4.2.3, sequences support `ORDER + CACHE`, which avoids skipped numbers while preserving order.

### 4.2 When NOORDER can be chosen (official criteria)

- Ordered insertion of the auto-increment column is not required, and higher concurrent performance is desired; or
- Ordered insertion is required, **but all Leaders sit on the same OBServer node** — in this case switching to NOORDER can still improve concurrent performance.
- In a **single-node (standalone)** scenario, ORDER and NOORDER show no clear performance difference; NOORDER only shows a clear advantage under high concurrency across **multiple nodes/partitions**.

So the criteria are two: "does the business require strict monotonic increase" plus "is the deployment multi-node" — **no TPS threshold is set**,
and it is **not required to be a partitioned table** (see `doc-gaps.md` §2).

### 4.3 Using an auto-increment column as the partition key

It is usable but costly: increment is not guaranteed within a partition; inserts **cannot be routed effectively**, producing **cross-node transactions**
and reduced performance. See `indexes.md` §4. The official "Hotspot Table Best Practices" further recommend "avoid using an auto-increment ID as
the primary key (prone to hotspots); use a composite primary key or a distributed ID instead."

## 5. Open items (no guessing allowed — must be marked `unverified`)

1. **The type allowlist for Oracle-mode HASH partition keys.** The type matrix in §1.1 comes from the **MySQL-mode** partition key documentation and cannot be applied directly to Oracle mode; Oracle-mode HASH accepts a column list rather than an integer expression, so MySQL's "integer/YEAR only" restriction **definitely does not apply**, but the exact allowlist has not been verified.
2. **The exact interaction between `DROP` / `TRUNCATE PARTITION` and global indexes.** Community-sourced information (MySQL mode, V4.2.5): dropping/truncating a partition invalidates the table's global indexes and triggers an automatic rebuild, which is very time-consuming on large tables. Needs confirmation on the target version.
3. **The minimum supported version for `DYNAMIC_PARTITION_POLICY` and `SKIP_INDEX`.** Both exist in the V4.5.0 BNF for both modes, but the version in which they were introduced has not been verified.
4. **Whether `SEMISTRUCT_PROPERTIES` can appear in the CREATE TABLE option position.** The official parameter documentation has this option (from V4.4.1), but the V4.5.0 BNF's `table_option` lists only the deprecated `SEMISTRUCT_ENCODING_TYPE`.
5. **The subset rule between the partition key and the primary key/unique key in Oracle mode.** The three-branch rule in `indexes.md` §1 comes from the MySQL-mode documentation.
   **New evidence (still not conclusive)**: the official "Database Development Best Practices," when discussing Oracle → OceanBase migration, states that "for a partitioned table or an Oracle heap table, the primary key need not include the partition key." This runs opposite to the MySQL-mode subset rule and suggests Oracle mode may genuinely be more permissive. However, this sentence comes from a migration-advice paragraph rather than the partition-key rules chapter, and it does not distinguish between "heap table" and "ordinary partitioned table" → **keep as `unverified`**,
   Oracle-mode design still follows the stricter MySQL three-branch rule, and this discrepancy should be recorded in the verification checklist.
6. **The exact syntax for index-level Column Group** (row-store table + columnstore index / columnstore table + row-store index).
   The official "Table Design and Index Optimization" guide lists these as independent storage architectures and gives their storage overhead (index +30–50% / data stored twice), but **gives no DDL syntax**, and the `index_option` in the V4.5.0 CREATE TABLE BNF has no column group production either → C3, may only enter `candidate_ddl`.
7. **Whether JSON multi-value indexes are subject to the automatic partition split restriction.** The official restriction list names only full-text/spatial/vector indexes (`partitioning.md` §3.1); multi-value indexes are not mentioned → `unverified`.
8. **Whether `_enable_add_fulltext_index_to_existing_table` still exists in the target version.**
   Hidden config items (`_` prefix) carry no version-compatibility guarantee — see `special-indexes.md` §1.3.

## 6. Behavior when the target environment does not meet requirements

Silent degraded generation is not allowed. The following must be output:

```yaml
capability_check:
  result: fail
  target_version:
  edition: community | enterprise
  compat_mode: mysql | oracle
  unsupported:
    - feature:
      required_version:        # or required_edition
      reason:
      alternative:             # required
```

Alternative mapping:

| Requested feature | Alternative when not satisfied |
|---|---|
| Oracle mode (Community Edition) | Rewrite in MySQL mode: `KEY` in place of `HASH(col_list)`, `DYNAMIC_PARTITION_POLICY` in place of `INTERVAL`, `VALUES IN` in place of `VALUES` |
| Automatic partition split `SIZE` | Pre-create enough RANGE partitions + periodic `ADD PARTITION` on the ops side |
| `DYNAMIC_PARTITION_POLICY` (when it is C2) | Oracle mode's primary approach is INTERVAL (C1); MySQL mode's primary approach is pre-created partitions + an external scheduling script; the feature itself is downgraded to a `candidate_ddl` candidate |
| Table Group `SCOPE` | `SHARDING = PARTITION` + manual Leader distribution control via Primary Zone |
| ColumnStore Replica | Same-table row-column redundancy `WITH COLUMN GROUP(all columns, each column)`, or an external OLAP system |
| Heap table | Keep the index-organized table; change the primary key to "ordered prefix + business column," and put the random key in a unique index |
| **Oracle mode wants an "auto-increment primary key"** | Oracle mode has no `AUTO_INCREMENT`: use the column attribute `GENERATED BY DEFAULT AS IDENTITY`, or `CREATE SEQUENCE` + take `NEXTVAL` on insert. Sequences default to NOORDER; add `ORDER` explicitly when order must be preserved (from V4.2.3, `ORDER + CACHE` can satisfy both order and no-skip) |
| **MySQL mode wants "unified cross-table numbering"** | MySQL mode has no sequence semantics: an auto-increment column is bound to a single table; cross-table numbering requires a hand-built numbering table or an external ID generator |
| Index-level Column Group (when it is C3) | Fall back to same-table row-column redundancy `WITH COLUMN GROUP(all columns, each column)` (≈2× storage), or a ColumnStore Replica |

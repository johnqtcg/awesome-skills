# Regression Case Set

Usage: whenever a rule or output format changes, feed each "Input" to the Skill one by one and check it against "Expected behavior". For `invalid` cases, the pass criterion is **being blocked**, not producing better DDL.

Legend: `G` = golden case (should pass), `I` = invalid case (should be blocked), `B` = boundary/trade-off case.

**Note on tiers.** `invalid` means *the server would reject the statement*, so refusing is the correct answer. A design that is legal but wrong belongs in `boundary` — grading it as `invalid` would demand a refusal, which is itself a defect. B30 was filed as `I13` for exactly this reason until 2026-08-12.

**How the machine side grades these** (`scripts/run_cases.py --grade`, field definitions in that file's docstring):

| Field | Scope | Use for |
|---|---|---|
| `must_include` | whole document | anything the answer must contain |
| `forbidden_in_ddl` | **the emitted primary DDL only** | every syntax token. A correct answer usually has to *name* what it refuses ("Oracle mode has no `AUTO_INCREMENT_MODE`"), so a whole-document ban fails the right answer |
| `must_not_include` | whole document, clause-scoped and refutation-aware | prose claims only ("design failed"), never syntax |
| `expected_checks` | the `checks:` block | a specific verdict on a specific check |

Do not try to scope a `must_not_include` pattern with `` ```sql[\s\S]* `` — it reads as "inside a SQL block" but `[\s\S]*` runs past the closing fence into the prose. `run_cases.py --validate` rejects that idiom.

---

## G1 Creating tables with each partition type in MySQL mode

Input: MySQL mode V4.5.0; separately request HASH / KEY / RANGE / RANGE COLUMNS / LIST partitioned tables.

Expected:

- The HASH partition key is an integer type; for a non-integer key, **switch the recommendation to KEY partitioning** instead of raising an error.
- LIST partitioning uses `VALUES IN (...)` and **includes a `DEFAULT` fallback partition** (per `doc-gaps.md` §1).
- DDL ordering is table option → partition option → column group.
- `VALUES LESS THAN` is strictly increasing.

## G2 Creating tables with each partition type in Oracle mode

Input: Oracle mode V4.5.0; request HASH / RANGE / LIST / INTERVAL partitioned tables, where one table has a two-column partition key.

Expected:

- A two-column partition key uses `PARTITION BY HASH(c1, c2)`; `PARTITION BY KEY` must **not** appear.
- LIST enumeration uses `VALUES ('A')`; `VALUES IN` must **not** appear.
- INTERVAL uses only a single column.
- `ORGANIZATION = HEAP` must not be output.

## I1 Oracle mode requests KEY partitioning

Input: Oracle mode; the user explicitly requests "use KEY partitioning for a multi-column partition key."

Expected: blocked, explaining that Oracle mode has no production rule for KEY partitioning, and offering `HASH(col_list)` as the alternative.

## I2 Primary key missing the partition key

Input: `PARTITION BY HASH(user_id)`, with the primary key being `(order_id)`.

Expected: the L0 hard constraint fails, generation of the DDL is blocked, and two ways forward are given (fold `user_id` into the primary key / change the partition key).

## I3 Unique index missing the partition key

Input: partitioned by `user_id`, with `email` required to be globally unique.

Expected:

- A local `UNIQUE KEY(email)` must not be silently generated.
- Output `resolution: promoted_to_global_unique`, spell out the distributed-transaction cost at write time, and offer "fold into the primary key" as an alternative.

## I4 Multi-table Table Group + automatic partitioning

Input: two large tables need aligned partitions in the same table group, while also wanting automatic splitting once a threshold is exceeded.

Expected: judged mutually exclusive (automatic partition splitting is not supported when a `TABLEGROUP` contains multiple tables); require the user to pick one and explain the trade-off.

## I5 Sub-partitioned / columnstore table requests automatic partitioning

Input: a sub-partitioned table (or columnstore table) requests enabling `SIZE`.

Expected: blocked, citing the restrictions in `partitioning.md` §3.1 one by one.

## I6 Older version requests a new feature

Input: target version V4.2.3; requests automatic partitioning + Table Group `SCOPE`.

Expected: `capability_check.result: fail`, with `required_version` given item by item and an alternative (pre-built partitions + manually controlling the Leader via Primary Zone).

## I7 Using a Hint to route to the columnstore replica

Input: the user requests "add a Hint so analytical queries go to the columnstore replica."

Expected: correct the misconception — `READ_CONSISTENCY(WEAK)` / `QUERY_TIMEOUT` cannot specify the replica type; give the version requirement (OB ≥ 4.3.3, OBProxy ≥ 4.3.2) and the deployment precondition of a **dedicated ODP cluster**.

---

## B1 Columnstore syntax for a pure AP table

Input: an offline analytics table with no TP point queries, performing daily multi-dimensional aggregation.

Expected: `WITH COLUMN GROUP(each column)`. **Producing `all columns, each column` is a failure** (that is row+column redundancy, roughly 2x storage).

## B2 Low-frequency full-table aggregation

Input: a weekly full-table SUM aggregation, scanning 30% of the columns.

Expected: do not enable columnstore; give a row-storage + `SKIP_INDEX(MIN_MAX, SUM)` approach. **Answering "no solution" or "use columnstore" is a failure.**

## B3 Large table joining a small dictionary table

Input: a 1-billion-row order table partitioned by `user_id` needs to frequently join a 200-row currency dictionary table (the dictionary table has no `user_id` column).

Expected: choose a **duplicated table**, `DUPLICATE_SCOPE = 'cluster'`; `rejected_alternatives` explains why a Table Group is not being forced.

## B4 Single-key hotspot

Input: a single `user_id` accounts for 40% of write volume.

Expected: identified as a single-partition write hotspot; point out that "a second-level HASH still takes the modulus of `user_id` and cannot break up a single-key hotspot"; give a salt/bucket approach and explain the fan-out and aggregation cost on the query side.

## B5 Identifying a queuing table

Input: a task table with `insert_qps ≈ delete_qps ≈ 2000`, a steady-state row count of about 5000, and scans that are gradually slowing down.

Expected: identified as a queuing table, recommend `TABLE_MODE = 'QUEUING'`.

## B6 Two high-frequency dimensions conflict

Input: an order table needs both point queries by `user_id` (45% share) and aggregation by `merchant_id` (40% share), and both are latency-sensitive.

Expected: **must not** simply declare "design failed." Should output at least two options plus a trade-off matrix (partition the main table by one dimension + route the other dimension through a global index/redundant table/duplicated dimension table), noting that V5 load testing is required.

## B7 Tablet estimation including indexes

Input: 3 tables, with partition counts of 6/12/1 respectively; the first table has 3 local indexes plus 1 global index with 4 partitions.

Expected: sum per `tablet-capacity.md` §1 = (6 + 18 + 4) + 12 + 1 = **41**; and derive the limit from the target tenant's memory (`_max_tablet_cnt_per_gb × memory in GB`), not a fixed 100000.

## B8 Archive table + global index

Input: a transaction log table RANGE-partitioned by day and retained for 90 days, which also needs a high-frequency query on a column other than the partition key.

Expected: flag the interaction between `DROP PARTITION` and global-index rebuild (mark `unverified`, require testing on the target version); prefer recommending `DYNAMIC_PARTITION_POLICY` to manage the data lifecycle.

## B9 NOORDER auto-increment column

Input: MySQL mode, non-partitioned table, high-concurrency inserts; the business does not require strictly increasing IDs.

Expected: recommend `AUTO_INCREMENT_MODE = 'NOORDER'`; **must not** impose "must be a partitioned table" or "TPS > 100" as a precondition; must flag skipped values/non-monotonicity, and note that this option is not in the mirrored BNF and needs to be tested.

## B10 Insufficient input information

Input: only a single sentence: "Help me design a user table, the data volume is very large."

Expected: first request the Step 0 target environment and Step 1 quantified inputs; until they are obtained, all `checks` output `unverified`, and **must not** fabricate QPS, ratios, or produce DDL directly.

---

## I8 Community Edition + Oracle mode

Input: `edition = community`, `compat_mode = oracle`; requests creating an INTERVAL partitioned table.

Expected: L0 block. Explain that the Community Edition kernel does not provide Oracle syntax compatibility, give two ways forward (rewrite in MySQL mode / switch to Enterprise Edition), and point out that in MySQL mode the alternative to INTERVAL is `DYNAMIC_PARTITION_POLICY`. **Must not** generate any Oracle-mode DDL.

## I9 MySQL mode uses VARCHAR as the HASH partition key

Input: MySQL mode; requests `PARTITION BY HASH(user_code)`, where `user_code VARCHAR(32)`.

Expected: point out that in MySQL mode a HASH key must be an integer or YEAR type, and switch the recommendation to `PARTITION BY KEY(user_code)`; **must not** generate the HASH DDL directly, and **must not** use this to reject the whole design.

## I10 Per-table partition count exceeds the limit (**MySQL mode**)

Input: **MySQL mode**, requests 200 first-level partitions x 50 sub-partitions = 10000.

Expected: L0 block, citing MySQL mode's `max_partition_num` (default 8192, adjustable up to 65536); give three alternatives — "raise the parameter / reduce the partition count / split the table." **Must explicitly state that this is a MySQL-mode limit.**

---

## B11 A partitioned table with neither a primary key nor a unique key (**must be allowed**)

Input: MySQL mode, a pure append-only tracking table with no primary key and no unique key, requesting RANGE partitioning by `event_time`.

Expected:

- Determine `table_key_shape: no_pk_no_uk`, `subset_rule_check.result: not_applicable`;
- **Produce the DDL normally**; must not block it on the grounds that "a partitioned table must have a primary key";
- Output `no_pk_risk_notes` (cannot locate rows by primary key, restricted OMS/CDC ingestion, no duplicate protection, `SIZE`-based automatic partitioning unavailable, etc.).

**Rejecting the design due to a missing primary key is a failure.**

## B12 No primary key but has a unique key

Input: no primary key, has `UNIQUE KEY uk(tenant_id, biz_no)`, requesting partitioning by `tenant_id`.

Expected: determine `no_pk_has_uk`; the check `tenant_id ⊆ uk` passes; allow it. If instead partitioned by `region` (not covered by the uk), it must be blocked.

## B13 A table with no primary key requests automatic partitioning

Input: the no-primary-key table from B11, with an additional request for "automatic splitting once a threshold is exceeded."

Expected: partitioning itself is allowed, but `auto_split_pk_prefix_check.result: fail` — automatic partition splitting does not support tables with no primary key; give two ways forward, "add a primary key and make the partition key its prefix" or "pre-build partitions."

## B14 Version branching for SHARDING = NONE

Input a: `ob_version = 4.3.5`, two 500 GB large tables requesting to join the same table group with `SHARDING = NONE`.
Input b: `ob_version = 4.4.2 BP2`, the same request.

Expected:

- a: give a **single-node capacity warning** (on this version, `NONE` carries the semantics of "consolidating onto a single node"), and require an assessment of the group's total size;
- b: **must not** state "NONE will pack the partitions onto a single node"; should explain that this semantics was removed as of V4.4.2 BP1, that distribution now depends on `SCOPE`, and redirect the risk assessment to `SCOPE = SERVER`;
- in both cases, `table_group.sharding_semantics_version_branch` must take the correct value.

## B15 Physical isolation must be able to reach a columnstore replica (two-axis decision tree)

Input: a pure AP reporting table (no TP point queries), `isolation_required = yes`, `ob_version = 4.3.3`, OBProxy 4.3.2, a dedicated ODP cluster already deployed.

Expected:

- **Axis 2 is evaluated first**: `deployment_overlay: columnstore_replica`;
- axis 1 then determines the base-table format;
- **failure criterion**: if the output is `deployment_overlay = none` (i.e., pre-empted by the "pure AP → each column" branch, with the isolation requirement never actually evaluated), that is non-compliant.

Variant: same input but OBProxy is 4.2.0 → `deployment_overlay: none` + `unmet_isolation_warning`, must not silently fall back.

## B16 The Tablet limit takes min() and compares on a per-node basis

Input: `unit_memory_gb = 8`, `unit_num = 2`, `_max_tablet_cnt_per_gb = 49999`, total Tablet count 41.

> 49999 rather than 50000 is used deliberately: the official valid range is **`[1000, 50000)` right-open**; 50000 itself is invalid, and the estimator should reject that input outright.

Expected:

- Formula A = 399992, Formula B = 163840, `per_node_limit = 163840`, `binding_formula: B`;
- the comparison target is `estimated_per_node = ceil(41/2) = 21`, **not** the cluster-wide total of 41;
- reporting only the "A = memory × 20000" formula, or comparing the cluster total against the per-node limit, is a failure.
- if the input is 50000 (out of range), the correct behavior is to **reject with an error**, not compute a result.

Variant: omit `unit_memory_gb` / `unit_num` → `result: unverified`; **must not** use default values to force a computed pass.

## I11 Oracle mode requests RANGE COLUMNS

Input: Oracle mode; requests `RANGE COLUMNS` partitioning on the two columns `(tenant_id, stat_date)`.

Expected: point out that Oracle mode **has no `COLUMNS` keyword**, and switch to `PARTITION BY RANGE(tenant_id, stat_date)` (Oracle's RANGE itself accepts a column list). The generated DDL must **not** contain `RANGE COLUMNS`.

## B17 Auto-increment column used as the partition key

Input: the user requests using the auto-increment primary key `id` directly as the HASH partition key.

Expected: point out that inserts **cannot be routed effectively → this produces cross-node transactions**, and that monotonicity is not guaranteed within a partition; give two ways forward, switching to a business key for partitioning or accepting the cost.

## B18 Source of the automatic partitioning threshold

Input: the user says "just have the table automatically split once it exceeds 30GB, write it into the DDL."

Expected: correct two points — the threshold is determined by the tenant configuration item `auto_split_tablet_size` (read when `SIZE()` is omitted), and `enable_auto_split = true` is also required for it to take effect; writing `SIZE` in the DDL does not mean automatic partitioning is already enabled.

## B19 A global index is not a forbidden zone

Input: a write-heavy, read-light table that has a business number that must be guaranteed unique across partitions.

Expected: **must not** answer "global indexes are forbidden on write-heavy tables." Should explain that cross-partition uniqueness can only be achieved with a global unique index, giving the `index_decision` cost decision and noting that load testing is required.

## B20 The same 10000 partitions must be allowed in Oracle mode

Input: **Oracle mode**, requests 200 first-level partitions x 50 sub-partitions = 10000.

Expected:

- **Produce the DDL normally.** Oracle mode's per-table limit is **fixed at 65536**, and it does **not** use `max_partition_num`;
- **failure criterion**: using 8192 as the gate and rejecting the design is non-compliant (this is exactly the contrast point between I10 and this case);
- if the total also exceeds 65536 (e.g., 300 × 300 = 90000), both modes should block it.

## B21 Unconfirmed capabilities must not enter the main DDL

Input: Oracle mode V4.4.2, a transaction log table partitioned by day, requesting "automatic partition management."

Expected:

- the main DDL uses `RANGE(dt) INTERVAL(...)` (C1);
- `DYNAMIC_PARTITION_POLICY` appears only in `candidate_ddl`, marked `confirmation_tier: C2` with a `confirmation_path` given;
- **failure criterion**: `DYNAMIC_PARTITION_POLICY` appearing in the main DDL, or INTERVAL and it appearing together in the main DDL — is a failure even if marked `unverified` alongside it.

## B22 A global index's independent partition count must be limited on its own

Input: MySQL mode, a table with only 1 partition, but requesting a global index with 9000 partitions.

Expected:

- L0 blocks it, naming the **global index object** itself (not the main table) as exceeding `max_partition_num`;
- **failure criterion**: judging pass based only on the main table's `partition_count` — the main table having 1 partition is of course compliant, but a global index can have its own independent partitioning rule, so each object must be checked individually;
- a local index does not need separate checking (it inherits the main table's partitioning);
- the same input is legal in **Oracle mode** (limit 65536).

Corresponding tool behavior: `estimate_tablets.py` outputs
`objects_over_partition_limit: ["t.g(global_index, 9000)"]`.

## B23 Heterogeneous Zones/Units must assess capacity based on the worst-case node

Input: two units, z1 = 64 GB and z2 = 1 GB, with a total of 30000 Tablets evenly distributed.

Expected:

- the judgment is based on **z2** (`headroom_ratio = 0.75`), not the average (about 0.38);
- output `topology: heterogeneous`, `worst_node: z2`, `node_detail[]`;
- **failure criterion**: using the average headroom to reach a "safe" conclusion, masking the fact that the low-memory node will hit its limit first.

## I12 Oracle mode requests an auto-increment primary key (**must intercept AUTO_INCREMENT**)

Input: Enterprise Edition, Oracle mode, V4.5.0; the user requests "make the id column auto-increment as the primary key."

Expected:

- must **not** output `AUTO_INCREMENT` / `AUTO_INCREMENT_MODE` / `auto_increment_cache_size`
  — Oracle mode's `table_option` has none of these three (L0 item 11);
- switch to the column attribute `GENERATED BY DEFAULT AS IDENTITY`, or `CREATE SEQUENCE` + `NEXTVAL`;
- **failure criterion**: copying the MySQL syntax and only flagging it `unverified` in warnings — that is a syntax error, not something pending confirmation.

## I14 Treating a read-hotspot configuration table as a write hotspot

Input: MySQL mode V4.5.0, a 200-row global configuration table, `read_qps=50000`, `write_qps=2`, with the same row being read repeatedly.

Expected:

- first classify by read/write direction → a read-intensive hotspot;
- give `DUPLICATE_SCOPE = 'cluster'` (a duplicated table), or caching/rate limiting;
- **failure criterion**: adding partitions, salt, or a bucket — it is still the same hotspot row; bucketing will only amplify reads by a factor of N.

## B24 Omitting Column Group when the tenant's `default_table_store_format = column`

Input: MySQL mode V4.5.0, a pure TP order table; the tenant's `default_table_store_format` has already been set to `column`.

Expected:

- recognize that "not writing a Column Group" will, under this tenant setting, produce a **columnstore table**, not row storage;
- per L1, recommend explicitly writing `WITH COLUMN GROUP(all columns)`;
- **failure criterion**: outputting "no Column Group specified, defaults to row storage, 1x storage" — the conclusion is the opposite of reality.

## B25 TP-dominant + lightweight AP (four-tier HTAP selection)

Input: MySQL mode V4.5.0, a high-frequency point-query order table, plus a once-daily lightweight aggregation report; `isolation_required=no`.

Expected:

- propose "row-storage table + columnstore index" (per the official figure, indexing adds +30%–50% storage) as an option cheaper than row+column redundancy;
- because the official docs give no DDL syntax for it → mark **C3**, place it in `candidate_ddl`, and use the C1 option in the main DDL;
- **failure criterion**: jumping straight to `all columns, each column` (≈2x storage) without offering the cheaper tier.

## B26 Criteria for upgrading a queuing table's tier

Input: MySQL mode V4.5.0, a task queuing table with `insert_qps≈delete_qps≈3000`, steady-state row count 2000; no measured data on scan degradation is provided.

Expected:

- classify it as a queuing table, default to `TABLE_MODE = 'QUEUING'`;
- explain that the difference among the five values is **how aggressively major compaction is triggered after minor compaction**, and leave upgrading to V5 load testing (L2);
- also recommend time-based partitioning plus partition-level truncate/drop instead of bulk `DELETE`;
- **failure criterion**: explaining the values with "increasing queue intensity," or asserting `EXTREME` is required without measured data.

## B27 JSON array containment query (existing table)

Input: MySQL mode V4.5.0, the already-live `user_info` table needs to filter by `JSON_CONTAINS(hobbies)`.

Expected:

- give a JSON multi-value index (`CAST(hobbies->'$[*]' AS ... ARRAY)`);
- **must** point out that adding an index to an existing table requires the sys tenant to enable
  `_enable_add_fulltext_index_to_existing_table`, and that this hidden parameter needs to be verified on the target version;
- give the `EXPLAIN` criteria (look at `NAME` and `range_key`; the operator name may still read `TABLE FULL SCAN`);
- **failure criterion**: choosing only between a local or global index, or omitting the switch needed for existing tables.

## B28 The user cannot obtain quantified inputs

Input: the user says "I can't query the production data, just give me something based on experience for now," but agrees to run a query against the database.

Expected:

- do not fabricate QPS/ratios; mark the relevant `checks` as `unverified`;
- **give the data-collection SQL**: `GV$OB_SQL_AUDIT` aggregation, partition-key cardinality and top1 share, `SHOW PARAMETERS`;
- **failure criterion**: simply replying "please provide frequency_share" and stopping there, or directly filling in a set of "typical values" as if they were measured.

## B29 No-primary-key columnstore ETL table (two official documents conflict)

Input: MySQL mode V4.5.0, a pure append-only tracking/analytics table used only for batch import and full-table aggregation; the user explicitly does not want a primary key.

Expected:

- route by scenario per `doc-gaps.md` §5.1: ETL/analytics workloads go with "no primary key, columnstore + time-range partitioning," and **must not be rejected**;
- output `WITH COLUMN GROUP(each column)` and give the no-primary-key risk notes (OMS/CDC, `SIZE`-based automatic partitioning unavailable);
- **failure criterion**: citing "every table must have a primary key" to kill the design, or conversely giving no risk notes at all.

## B30 Low-cardinality column used for HASH partitioning (NDV < partition count -- legal DDL, defective design)

Input: MySQL mode V4.5.0, the `status` column has only 6 distinct values, and the user requests `PARTITION BY HASH(status) PARTITIONS 128`.

Expected:

- hits **L1-B blocker B1**: NDV(6) < partition count (128) → 122 permanently empty partitions, quantified;
- point out that a low-cardinality column should use **LIST partitioning**, not HASH;
- `checks.partition_key_selection.result = fail` with `blocking: false`;
- **DDL is still emitted** — the corrected LIST design as the primary, and the requested 128-partition HASH acknowledged as legal-but-wasteful, or accepted via `accepted_reason` if the user gives a purpose;
- **failure criterion (two directions, both count)**:
  - too permissive: silently generating 128 HASH partitions as requested, or merely saying "may be uneven" without quantitative backing;
  - too strict: **refusing to generate any DDL, or reporting the design as infeasible / an L0 violation** — the server accepts this statement, so L0 is the wrong tier.

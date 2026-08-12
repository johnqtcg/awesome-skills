# Anti-Pattern Checklist: Flawed Designs That Must Be Identified and Called Out

The Agent must actively scan this checklist in both Design mode and Schema Review
mode. Each item comes with a "why," to keep this from becoming mechanical pattern
matching. The order of the items carries no priority meaning; SKILL.md §7 excerpts the
five highest-frequency ones.

26 items in total. 1–18 come from past reviews; 19–26 come from an item-by-item
cross-check against OceanBase's official best practices.

1. **The partition key does not match the query's filter key** → pruning is impossible, resulting in a full-partition scan.
2. **The primary key does not include the partition key** → an L0 violation; the DDL is illegal.
3. **A unique index that doesn't cover the partition key is generated as a local index anyway** → the constraint cannot be enforced (it should be upgraded to a global unique index, with the cost stated).
4. **Overuse of global indexes** → write amplification plus distributed transactions; on an archival table this also compounds with index rebuilds on partition drop.
5. **A hotspot goes unhandled, or subpartitioning is mistakenly assumed to break up a single-key hotspot.**
6. **Related tables each "go their own way"**: they share the same partition key but are not placed in the same table group, so their partitions can still be scheduled onto different OBServers, and the Join is still cross-node.
7. **Fabricating a partition key for a small dictionary table just to place it in a table group** → a duplicated table should be used instead.
8. **Packing two large tables into `SHARDING = 'NONE'`** (**only < V4.4.2 BP1**) → single-node capacity and hotspot risk; at ≥ BP1 the discussion should shift to `SCOPE = SERVER` instead. Conversely, still claiming at ≥ BP1 that "NONE forces everything onto one node" is equally wrong.
9. **Writing `all columns, each column` for a pure analytical table** → that produces a **row-column redundancy table**, storing an extra row-store copy on top of columnstore, at roughly **2×** the storage. A pure AP table should write `each column`.
10. **Using a Hint to fake columnstore replica routing** → neither `READ_CONSISTENCY(WEAK)` nor `QUERY_TIMEOUT` can specify a replica type. A columnstore replica is a deployment-topology decision: it requires OB ≥ V4.3.3, **OBProxy ≥ V4.3.2**, and **a separately deployed ODP cluster**.
11. **A random primary key combined with LSM, with no mitigation** (and don't explain it away as "page splitting").
12. **Using `PARTITION BY KEY` or `ORGANIZATION` in Oracle mode**; or generating Oracle-mode DDL on the **Community Edition**.
13. **Failing to recognize a queuing table (high insert + high delete)**, whose scan performance degrades over time.
14. **Treating an L2 empirical threshold as grounds for rejecting a design.**
15. **Rejecting a partitioned table that has no primary key and no unique key solely because "it has no primary key"** → this is a legal design; only a risk note is needed.
16. **Treating the Tablet limit as a fixed constant**, or comparing the cluster's total Tablet count against the per-node limit.
17. **Treating 8192 as a partition-count limit common to both modes** → Oracle mode is fixed at 65536; using 8192 wrongly rejects a legal design.
18. **A C2/C3 unconfirmed capability appears in the primary DDL** (especially an Oracle scenario writing both INTERVAL and `DYNAMIC_PARTITION_POLICY` at the same time).
19. **Writing `AUTO_INCREMENT` / `AUTO_INCREMENT_MODE` / `auto_increment_cache_size` in Oracle-mode DDL**
    → Oracle mode's `table_option` has no such options; use the column attribute
    `GENERATED [BY DEFAULT|ALWAYS] AS IDENTITY` or a sequence instead
    (`capability-matrix.md` §4).
20. **Asserting that "not writing a Column Group means it's a row-store table"** → the actual outcome depends on the tenant parameter `default_table_store_format`;
    when it is set to `column` / `compound`, the table is built by default as columnstore / row-column redundancy (≈2× storage).
    The same class of error also includes treating the defaults of `ORGANIZATION` and `AUTO_INCREMENT_MODE` as fixed values
    (`storage-format.md` §1.1, `capability-matrix.md` §2.1).
21. **A HASH / KEY partition key whose cardinality is lower than the partition count** → this inevitably produces permanently empty partitions, wasting Tablet capacity. **L1-B, not L0**: the server creates the table, so the fix is a `fail` verdict with the empty-partition count quantified plus the corrected design — never a refusal to emit DDL (`partitioning.md` §2.1).
    The official criterion is NDV > partition count (`partitioning.md` §2.1). The reverse mistake: using a **low-cardinality** field
    (province, status code) for HASH — that's a scenario for LIST partitioning instead.
22. **Explaining the five values of `TABLE_MODE` in terms of "queuing intensity"** → the real difference is how eagerly a minor compaction triggers a major compaction afterward;
    the deciding axis is query-latency sensitivity vs. resource consumption (`storage-format.md` §5.1).
23. **Treating a config/routing table's** read **hotspot as a write hotspot** (adding partitions, adding buckets) → the correct fix for a read hotspot is a duplicated table /
    cache / rate limiting; adding a bucket only amplifies reads by N× (`hotspots.md` §0).
24. **Offering only a choice between local or global index for a JSON array-contains query or large-text fuzzy search** → ordinary indexes can't serve either kind of filter;
    a special index is required (`special-indexes.md`). Adding either kind of index to an **existing table** also requires flipping a hidden sys-tenant switch.
25. **Setting up an input gate without providing a way to collect the data** → requiring `frequency_share` / `top1_key_share` without giving the SQL to obtain them
    leaves the user stuck, or tempted to make up numbers. Always provide the matching query from `input-collection.md` at the same time.
26. **Arbitrarily picking one side and writing it as a hard rule when two official documents conflict** → for example, treating "every table must have a primary key" as an unconditional rule

27. **Carrying one mode's syntax into the other while tuning** → recommending `NOCACHE` as the MySQL-mode way to suppress auto-increment gaps. `NOCACHE` is an Oracle `CREATE SEQUENCE` clause; MySQL mode takes the integer `AUTO_INCREMENT_CACHE_SIZE`, so the suggestion produces a syntax error rather than a slower-but-gapless table (`doc-gaps.md` §2.3.1). The mirror image of item 12 — the mode gate has to be checked in **both** directions, not just when generating the main DDL.
    would wrongly reject the officially recommended no-primary-key columnstore ETL table (`doc-gaps.md` §5).

---

## How to Use This

- **Design mode**: self-check against every item before generating the DDL; if one hits, fix the design and record the related risk in warnings.
- **Review mode**: compare against every item on the existing schema; for items that cannot be judged without a query or without the data distribution (
  items 1, 5, 13, 21, 23), output `unverified` rather than guessing.
- Items 4, 8, 12, 17, 19 are **version/mode-dependent**; before judging, you must first obtain `ob_version`, `edition`, and
  `compat_mode` (see `capability-matrix.md`).
- Item 20 is **tenant-configuration-dependent**; before judging, you must obtain the three tenant defaults from §2.1. If you can't, mark it `unverified`,
  and recommend switching to an explicit form per L1.

# Verification Ladder V1–V5

Every design conclusion must be traceable to some verification layer. **A conclusion
that cannot be verified can only be marked `unverified` — it must not be output as
pass/fail.**

| Layer | What it verifies | Pass condition | Requires a database |
|---|---|---|---|
| V1 Static check | DDL syntax, compatibility mode, version capability matrix, mutually exclusive feature combinations | No unsupported syntax or combinations | No |
| V2 Database execution | Executing the CREATE TABLE / CREATE INDEX / CREATE TABLEGROUP DDL on the target version | All succeed | Yes |
| V3 Plan verification | `EXPLAIN` on the core SQL | Partition pruning, index selection, and Join localization match expectations | Yes |
| V4 Capacity verification | Tablet count, partition size, skew | Satisfies tenant resource constraints | Yes |
| V5 Performance verification | Benchmarking against the target workload | Meets read/write SLA | Yes |

When the Agent works alone, **it can only complete V1**. Therefore:

- V1 must be performed every time, with evidence given item by item;
- V2–V5 are output as a **to-do verification checklist** (with concrete SQL included),
  and the related `checks` are set to `unverified`;
- Treating "I reasoned it through" as a substitute for V3 is forbidden.

<!-- toc -->

**Table of Contents**

- [V1 Static Check Checklist](#v1-static-check-checklist)
  - [Automated Static Checks](#automated-static-checks)
- [V2 Execution Verification](#v2-execution-verification)
- [V3 Plan Verification](#v3-plan-verification)
- [V4 Capacity Verification](#v4-capacity-verification)
- [V5 Performance Verification](#v5-performance-verification)
- [Regression Cases](#regression-cases)

<!-- /toc -->

## V1 Static Check Checklist

The **authoritative definition of each item lives in its corresponding reference
file**; this checklist is only an index. Where the two descriptions disagree, the
reference file wins, and `scripts/check_consistency.py` is used to fix the drift.

```yaml
v1_static:
  edition_gate:                  # community + oracle → fail (capability-matrix §0)
  compat_mode_gate:              # Oracle mode disallows: KEY partitioning / COLUMNS keyword / ORGANIZATION
                                 # MySQL mode disallows: INTERVAL / VALUES (...) enumeration syntax
                                 # see the "forbidden combinations" in capability-matrix §1.2
  version_gate:                  # auto-partitioning ≥4.3.5 / SCOPE ≥4.4.2BP1 / columnstore replica ≥4.3.3 / heap table ≥4.3.5BP1
  key_constraints:               # a three-branch conditional rule (indexes.md §1), not a single "partition key ⊆ primary key" statement:
                                 #   has_pk        → partition key ⊆ primary key
                                 #   no_pk_has_uk  → partition key ⊆ every unique key
                                 #   no_pk_no_uk   → not_applicable (legal; only issue a risk note, must not block)
                                 # a unique index that doesn't cover all partition keys → must be upgraded to a global unique index, with the cost stated
                                 # auto-partitioning exception: must have a primary key, and the partition key must be a prefix of the primary key
                                 # Oracle mode's subset rule is not yet confirmed → unverified (capability-matrix §5-5)
  partition_key_type:            # MySQL mode: RANGE/LIST/HASH require an integer or YEAR type; RANGE/LIST are limited to a single column
                                 # the COLUMNS variant cannot use expressions; expressions are limited to the official allowlisted functions
                                 # Oracle mode's type allowlist is not yet confirmed → unverified (§5-1)
  partition_count_limit:         # judged **per individual partitioned object**, not just the base table:
                                 #   base table              -> partitions × subpartitions
                                 #   each global index        -> its own partitions × subpartitions
                                 #   local index / LOB        -> inherits from the base table, not judged separately
                                 # limit by mode: MySQL = max_partition_num (default 8192, [8192,65536])
                                 #                Oracle = fixed at 65536, this parameter is not used
  mutually_exclusive:            # multi-table TABLEGROUP + auto-partitioning; columnstore/columnstore replica + auto-partitioning;
                                 # subpartitioning + auto-partitioning; no primary key + auto-partitioning
  tablegroup_semantics:          # the risk judgment for SHARDING=NONE must branch on V4.4.2 BP1 (tablegroup.md §2.1)
                                 # still claiming "NONE forces everything onto one node" at ≥BP1 is likewise a fail
  storage_axes:                  # axis 2 (isolation_required) must be judged first and must not be short-circuited by axis 1 (storage-format.md §2)
  autoinc_mode_gate:             # **MySQL-mode-only**: AUTO_INCREMENT / AUTO_INCREMENT_MODE /
                                 #   auto_increment_cache_size appearing in Oracle-mode DDL → fail
                                 # in Oracle mode use GENERATED [BY DEFAULT|ALWAYS] AS IDENTITY or a sequence instead
                                 # see capability-matrix.md §4
  tenant_default_gate:           # whether the three configuration items that "fall back to the tenant default when not written" have been obtained:
                                 #   default_table_store_format      → determines the actual format when there is no Column Group
                                 #   default_table_organization      → determines the organization form when there is no ORGANIZATION
                                 #   DEFAULT_AUTO_INCREMENT_MODE     → determines the numbering mode when there is no AUTO_INCREMENT_MODE
                                 # not obtained → the related conclusion is unverified; L1 recommends switching to an explicit form
                                 # see capability-matrix.md §2.1, storage-format.md §1.1
  partition_key_selection:       # NDV > partition count; skew; key type; whether it appears in the primary-path filter
                                 # distinct_count missing → unverified (must not default to pass)
                                 # TIERS DIFFER: key type is L0 (blocks generation); NDV / skew / filter-presence
                                 #   are L1_blocker → report fail with the damage quantified, but still emit the DDL.
                                 #   A verdict of fail on those three must NOT appear as "design infeasible".
                                 # see partitioning.md §2.1
  special_index_gate:            # when MEMBER OF / JSON_CONTAINS / JSON_OVERLAPS / full-text search needs appear
                                 #   a special_index contract must be given (including preconditions for enabling the switch on existing tables)
                                 # Chinese corpus + WITH PARSER SPACE → fail
                                 # see special-indexes.md
  confirmation_tier_gate:        # the primary DDL allows only C1. Index-level Column Group (columnstore index/row-store index) is C3
  syntax_order:                  # table option → partition option → column group
  range_boundary_monotonic:      # VALUES LESS THAN must be strictly increasing
  list_default_partition:        # whether the LIST partitioning has a catch-all partition (MySQL: VALUES IN (DEFAULT); Oracle: VALUES (DEFAULT))
  result: pass | fail
```

### Automated Static Checks

Run everything with a single command (no database needed):

```bash
bash scripts/run_regression.sh
```

It runs every static check in sequence — **after any rule or script change, all of them
must be green**. The stage list lives in `run_regression.sh` itself; do not restate a
count here, because a prose number silently goes stale the next time a check is added
(this sentence said "six" while the runner had ten stages):

```bash
python3 scripts/check_consistency.py              # cross-file rule consistency + forbidden combinations + link integrity
python3 scripts/run_cases.py --validate           # cases.json completeness / rule coverage / sync with cases.md
python3 scripts/estimate_tablets.py --self-test   # Tablet model and input validation
python3 scripts/check_negative_log.py --self-test # regression of the negative-case, per-case judge itself
bash    scripts/run_integration.sh --self-test    # version comparison and layered gating
python3 -m pytest scripts/tests -q                # contract tests + golden scenario tests
```

Items 3–5 are "verifiers of the verifiers": if the judgment logic or version gating
itself is wrong, it produces a **false green**, so they must be tested continuously,
just like the things they verify.

Item 6 is **structural regression protection**: the contract tests pin down, rule by
rule, the assertions in SKILL.md and references/ that are easy to accidentally revert
(such as the paired assertion "Oracle mode has no `AUTO_INCREMENT`"), and the golden
scenario tests verify that all the rules needed for a set of representative inputs are
still present. Neither depends on an LLM, so both are also picked up by
`python3 -m pytest skills/` at the repository root.

## V2 Execution Verification

```sql
-- Execute the generated DDL statement by statement; a table group must be created first if one is used
-- After creation, verify the actual schema
SHOW CREATE TABLE t\G
SELECT TABLE_NAME, PART_LEVEL, PARTITION_NAME, SUBPARTITION_NAME
  FROM oceanbase.DBA_OB_TABLE_LOCATIONS WHERE TABLE_NAME = 'T';
SHOW TABLEGROUPS WHERE tablegroup_name = 'tg_xxx';
```

## V3 Plan Verification

```sql
EXPLAIN SELECT ... ;              -- check the Top-N SQL statements one by one
-- What to look at:
--   1. Partition-pruning info on the operator: does the number of partitions hit match expectations (a point query should be 1)
--   2. Whether the expected index (local/global) was used
--   3. Whether the Join is localized (any EXCHANGE / distributed Join operator)
--   4. Whether the special index was hit (see the criteria below — **do not judge from the operator name alone**)
```

Judgment rule: when the `EXPLAIN` for a `dominant_pattern` hits more than 1 partition,
`checks.partition_pruning` must be `fail` — you cannot write `pass` just because "the
design intent was pruning."

Hit criteria for special indexes (`special-indexes.md` §1.4, §2.2):

| Index type | Sign of a hit | Common misjudgment |
|---|---|---|
| JSON multi-value index | `NAME` becomes `table_name(index_name)`, `range_key` contains `SYS_NC_mvi_*`, `is_index_back=true` | The operator name **can still be `TABLE FULL SCAN`**. Judging by the operator name alone can wrongly conclude "the index isn't taking effect" |
| Full-text index | The operator is **`TEXT RETRIEVAL SCAN`**, together with `calc_relevance=true` / `pushdown_match_filter` | Seeing `TABLE FULL SCAN` means it did not hit |

The execution plan also depends on **whether statistics are fresh**: with stale
statistics, the optimizer may pick the wrong index, in which case the `EXPLAIN`
conclusion cannot be directly attributed to the schema design. Confirm statistics have
been gathered before judging `fail`.

## V4 Capacity Verification

```sql
SELECT TABLE_NAME, TABLE_TYPE, COUNT(*) AS tablet_cnt
  FROM oceanbase.DBA_OB_TABLETS GROUP BY TABLE_NAME, TABLE_TYPE;
```

Reconcile this item by item against the estimate in `tablet-capacity.md` §1; a
deviation greater than 10% indicates the estimate missed an object.

## V5 Performance Verification

- Must cover: TPS/latency on the primary write path, P99 for the `dominant_pattern`,
  and archival-window duration (if there is a global index, the impact of
  `DROP PARTITION` must be measured).
- All L2 thresholds to be verified (per-partition size, per-partition hit rate, Tablet
  headroom) are calibrated at this layer and then backfilled into the design document.

## Regression Cases

See `../tests/cases.md`. After any rule change, positive cases, negative cases, and
boundary cases must be rerun.

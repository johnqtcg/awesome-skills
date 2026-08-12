# V2–V5 Real Database Verification Suite

## Status (stated as-is)

| Item | Status |
|---|---|
| The suite itself | **Delivered, ready to run** (`--dry-run` verifies tier selection, no instance needed) |
| Version-tiering selection logic | **Verified**: `run_integration.sh --self-test` — 12 version-comparison assertions; dry-run skip sets for 6 target versions are correct |
| Negative-case per-case judge | **Verified**: `check_negative_log.py --self-test` |
| **Actual execution results** on V4.3.5 / V4.4.2 BP1 / V4.5.0 | **Not yet executed** (no OceanBase instance available in the current environment) |

So what this Skill can currently prove is "the rules are written correctly and static checks pass" — it **cannot** prove "the generated DDL actually runs on the target version and the execution plan matches expectations." Until this suite has been run and results backfilled, it should not be treated as the final approval basis for production DDL.

## Why It Must Span Three Versions

This Skill has three places where the rules **fork by version** — single-version verification cannot cover them:

| Version | Fork point that must be verified |
|---|---|
| **V4.3.5** | Auto-partitioning `SIZE` just became available; table group `SHARDING = NONE` still carries the "consolidated on a single node" semantics; no `SCOPE` |
| **V4.4.2 BP1** | The old `SHARDING = NONE` semantics **is removed**; the `SCOPE` attribute is introduced |
| **V4.5.0** | Syntax baseline; the three corrections in `doc-gaps.md` need confirming on this version |

## Running

```bash
# single version
../../scripts/run_integration.sh --dsn 'obclient -h127.0.0.1 -P2881 -uroot@mysql#cluster -p' \
                                --mode mysql --version 4.5.0 --out results/

# expected output
results/4.5.0-mysql/{ddl_positive,ddl_negative,explain,tablegroup,tablet,storage}.log
results/4.5.0-mysql/summary.txt
```

Oracle compatibility mode requires an Enterprise Edition tenant (the Community Edition has no Oracle syntax compatibility, see `references/capability-matrix.md` §0); skipping `oracle_mode.sql` on the Community Edition is **expected behavior**, not a failure.

## Coverage Matrix (tiered by minimum capability version)

The runner decides whether to run or skip based on the `min_version` declared by each script. **Below the minimum version it skips, it does not fail** —
otherwise "this version doesn't support a certain capability" would be misreported as the entire positive-example suite failing. See the script list and version declarations in
the `MYSQL_PLAN` / `ORACLE_PLAN` of `../../scripts/run_integration.sh`.

### MySQL mode

| File | Category | Minimum version | Coverage |
|---|---|---|---|
| `mysql_base.sql` | positive example | 4.x | HASH / KEY / `KEY()` / RANGE / RANGE COLUMNS / LIST / LIST COLUMNS / second-level partitions / tables without a primary key / tables with only a unique key / duplicated (replicated) tables / queue tables / explicit global unique index |
| `mysql_negative.sql` | negative example | 4.x | **Should fail** — 14 cases: primary key missing the partition key, local unique key missing the partition key, HASH using VARCHAR, RANGE with multiple columns, non-increasing boundaries, partition count over the limit, auto-partitioning × second-level partitions / no primary key / non-primary-key-prefix / columnstore, MySQL mode using INTERVAL, LIST using Oracle-style `VALUES`, enabling auto-partitioning on a multi-table table group, non-allowlisted partition function |
| `mysql_v430.sql` | positive example | ≥ 4.3.0 | Pure columnstore `each column`, row-and-column redundancy `all columns, each column` |
| `mysql_v435.sql` | positive example | ≥ 4.3.5 | Auto-partition splitting `SIZE` |
| `mysql_v435bp1.sql` | positive example | ≥ 4.3.5 BP1 | Heap table `ORGANIZATION = HEAP` |
| `tablegroup.sql` | positive example | ≥ 4.2.0 | Positive examples for the three `SHARDING` states + a control group with the same partition key that does not join a table group |
| `tablegroup_negative.sql` | negative example | ≥ 4.2.0 | **Should fail** — 3 cases: mismatched partition count within a `PARTITION` group, mixed levels within an `ADAPTIVE` group, joining a group with a mismatched partition definition |
| `tablegroup_probe.sql` | **probe** | ≥ 4.2.0 | `SCOPE` syntax availability (erroring below 4.4.2 BP1 is expected), observation of `leader_hosts` for `SHARDING=NONE` |
| `explain.sql` | positive example | 4.x | Partition-pruning hit count, index selection, join localization, duplicated-table join |
| `explain_v430.sql` | positive example | ≥ 4.3.0 | Columnstore scan path |
| `tablet.sql` | positive example | 4.x | Reconciliation of actual Tablet counts (including indexes), real upper limit from `GV$OB_TENANT_RESOURCE_LIMIT`, actual values of hidden parameters |
| `storage_v430.sql` | positive example | ≥ 4.3.0 | Actual differences and storage-footprint comparison across the three Column Group forms |
| `storage_base.sql` | positive example | 4.x | Queue-table mode query |
| `storage_negative.sql` | negative example | ≥ 4.3.5 | **Should fail** — 1 case: adding columnstore to an auto-partitioned table (depends on `t_autosplit` from `mysql_v435.sql`) |
| `mysql_probe.sql` | **probe** | 4.x | **C2/C3 capabilities**: `SKIP_INDEX`, `DYNAMIC_PARTITION_POLICY` (minimum version not yet confirmed), `AUTO_INCREMENT_MODE` (documentation gap) |
| `storage_probe.sql` | **probe** | 4.x | Actual pre-creation/reclamation behavior of dynamic partitioning; measured interaction between `DROP PARTITION` and global-index rebuild |

### Oracle mode

| File | Category | Minimum version | Coverage |
|---|---|---|---|
| `oracle_mode.sql` | positive example | 4.x | `HASH(col_list)` / `RANGE(col_list)` (including multi-column) / `LIST(col_list)` / `INTERVAL` / templated second-level partitions / duplicated tables / queue tables / auto-partitioning / pure columnstore |
| `oracle_negative.sql` | negative example | 4.x | **Should fail** — 7 cases: `RANGE COLUMNS`, `LIST COLUMNS`, `PARTITION BY KEY`, `ORGANIZATION`, `VALUES IN`, multi-column INTERVAL, primary-key-subset violation |

### Assertion method for the three categories

| Category | Pass criterion | Implementation |
|---|---|---|
| positive example | Any statement erroring counts as a failure | obclient exit code, **no `\|\| true` exemption** |
| negative example | **Each case must error on its own** | `@@CASE:<id>` marker + per-window judgment by `scripts/check_negative_log.py`; an extra unrelated error must not mask an unexpected success in some other case |
| probe | Only requires non-empty output | Both success and failure are valid observations; **the only category that does not assert on exit code**, and it is physically isolated from the other two |

**Why probe must be physically isolated**: mixing version-dependent observations and version-independent assertions in the same file would force using `\|\| true` to ignore the exit code,
which would let real failures slip through at the same time. Once separated, positive/negative examples no longer need any exemption.

## Backfilling Results

After each version finishes running, write the conclusions back to:

1. `references/capability-matrix.md` §5 "Open Items" — resolve or remove each one;
2. `references/doc-gaps.md` — confirm whether the corrections are still needed;
3. `results/<version>-<mode>/summary.txt` in this directory — keep the raw output as evidence.

**The pass criterion for a negative example is "it errors."** If a negative example succeeds on some version, it means that version's behavior is inconsistent with this Skill's L0 rules, and the rule must be revised — not the test case.

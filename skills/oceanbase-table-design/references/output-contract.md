# Output Contract: Seven-Section Structure and Per-Section Fields

SKILL.md §5 keeps only the **section order and hard rules**; this file is the complete
field definition for every section. Where the two disagree, this file wins.

Design mode and Review mode share §4 (Constraint Checks) and §5 (Risks and Warnings);
Review mode does not output §2 / §2b, and instead attaches a list of "items that cannot
be judged with the current input."

<!-- toc -->

**Table of Contents**

- [1. Preconditions and Assumptions](#1-preconditions-and-assumptions)
- [2. Primary DDL](#2-primary-ddl)
- [2b. Candidate DDL](#2b-candidate-ddl)
- [3. Design Decision Notes](#3-design-decision-notes)
- [4. Constraint Checks](#4-constraint-checks)
- [5. Risks and Warnings](#5-risks-and-warnings)
- [6. Cost Assessment](#6-cost-assessment)
- [7. Verification Checklist](#7-verification-checklist)

<!-- /toc -->

## 1. Preconditions and Assumptions

Must be output whenever Step 0 has a missing item, and it goes **first** (leading with
the conclusion presupposes first stating what the conclusion is built on):

```yaml
assumptions:
  - field:                    # e.g. tenant_defaults.default_table_store_format
    assumed_value:
    why:                      # why this value was chosen
    affected_conclusions: []  # which conclusions would be overturned if this assumption is wrong
```

Any `checks` item affected by an assumed value must always be marked `unverified`.

## 2. Primary DDL

**Contains only C1 confirmed capabilities** (see SKILL.md §2, "Capability Confirmation
Tiers").

```sql
CREATE TABLE ...
```

## 2b. Candidate DDL

Output only when the design genuinely involves a C2/C3 capability. **Must not go
directly to production.**

```yaml
candidate_ddl:
  - feature:                  # e.g. DYNAMIC_PARTITION_POLICY, index-level Column Group
    confirmation_tier: C2 | C3
    reason:                   # why it didn't make it into the primary DDL
    ddl_fragment:
    benefit_over_primary:     # what it saves compared to the primary approach
    confirmation_path:        # which file under tests/integration/ to run, and which observation point to check
```

## 3. Design Decision Notes

The authoritative definition of each sub-contract lives in its corresponding reference
file; this section only assembles the summary:

```yaml
design:
  target_environment: {...}     # Step 0, including the three tenant_defaults items
  syntax_baseline: V4.5.0
  dominant_patterns: [...]      # Step 2
  partitioning: {...}           # partitioning.md §2.1 (including the four key_selection_check items)
  key_constraints: {...}        # indexes.md §1.4
  physical_layout: {...}        # tablegroup.md §1
  table_group: {...}            # tablegroup.md §5
  index_decision: [...]         # indexes.md §2.1
  special_index: [...]          # special-indexes.md §4; not_applicable when there is no triggering predicate
  hotspot: {...}                # hotspots.md §6
  lifecycle: {...}              # partitioning.md §4
  storage_mode: {...}           # storage-format.md §2
  table_organization: {...}     # storage-format.md §6
  tablet_capacity: {...}        # tablet-capacity.md
```

## 4. Constraint Checks

**Three-state result + evidence — a bare pass/fail is forbidden. You cannot give
`pass` without evidence; reasoning cannot substitute for `EXPLAIN`.**

```yaml
checks:
  capability_matrix:
    result: pass | fail
    unsupported_combinations: []
  tenant_defaults:
    result: pass | unverified          # whether the three tenant defaults were obtained (capability-matrix.md §2.1)
    evidence:                          # SHOW PARAMETERS output; if not obtained, note the switch to explicit syntax
  autoinc_mode_gate:
    result: pass | fail | not_applicable
    evidence:                          # AUTO_INCREMENT* appearing in Oracle mode → fail
  key_constraints:
    result: pass | fail
    evidence:
  unique_key_constraint:
    result: pass | fail | unverified
    evidence:
  partition_key_selection:
    result: pass | fail | accepted_with_reason | unverified   # the four criteria (partitioning.md §2.1)
    evidence:                          # distinct_count / top1_key_share / key type / whether it's in the primary-path filter
    failed_criteria: []                # e.g. [ndv_vs_partition_count]
    blocking: false                    # criteria 1/2/4 are L1_blocker -> false: report fail, still emit the DDL.
                                       # Only criterion 3 (key type) is L0 -> true: DDL must not be generated.
    accepted_reason:                   # REQUIRED when result = accepted_with_reason
  partition_pruning:
    result: pass | fail | unverified
    evidence:                          # EXPLAIN excerpt / number of partitions hit; must be unverified if absent
    affected_queries: []
  distributed_txn:
    result: pass | fail | unverified
    evidence:
    affected_transactions: []
  hotspot:
    result: pass | fail | unverified
    evidence:
    skew_ratio:
  special_index:
    result: pass | fail | not_applicable | unverified
    evidence:                          # preconditions for enabling the switch on existing tables, tokenizer, expected EXPLAIN operator
  table_group:
    result: pass | fail | not_applicable | unverified
    evidence:
  capacity:
    result: pass | fail | unverified
    evidence:
```

## 5. Risks and Warnings

Give each item as: **risk → trigger condition → blast radius → mitigation → whether
benchmarking is needed**. Must cover at least:

- Distributed transactions
- Hotspots (by the types in `hotspots.md` §1; write up read hotspots and write hotspots separately)
- Global-index write amplification and its interaction with archiving
- Queries that cannot be pruned
- Storage amplification from row-column redundancy (≈2×)
- Mutually exclusive combinations for auto-partitioning
- The magnitude of auto-increment-column skipped numbers (affected by `AUTO_INCREMENT_CACHE_SIZE` under NOORDER)
- Shape judgments that depend on tenant defaults (must be reported when `tenant_defaults` was not obtained)
- Write amplification from special indexes and the existing-table switch
- **Table-group distribution risk — pick one based on version**: report the single-node
  capacity risk of `SHARDING=NONE` when the target version is < V4.4.2 BP1; at
  ≥ V4.4.2 BP1, report the load-balancing risk of `SCOPE=SERVER` instead (see
  `tablegroup.md` §2.1 for details — **the same sentence must not be reused across
  both versions**)

## 6. Cost Assessment

Graded — **do not output falsely precise numbers**:

```yaml
cost_assessment:
  cross_partition_scan: low | medium | high    # attach: frequency_share of the affected queries
  distributed_txn:      low | medium | high
  global_index_write:   low | medium | high
  storage_overhead:     low | medium | high
  overall: low | medium | high
  note: "grading is weighted by frequency_share; a numeric score requires V5 benchmark calibration before it can be given"
```

Do not output an uncalibrated weighted total score — that is false precision.

## 7. Verification Checklist

List the to-do items for V2–V5 along with the concrete SQL (`verification.md`). For
any item missing input, also attach the matching collection SQL from
`input-collection.md`, so the user has what they need to get the data for the next
round.

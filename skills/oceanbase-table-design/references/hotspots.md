# Hotspot Classification and Mitigation

<!-- toc -->

**Table of Contents**

- [0. First split into read / write (the official top-level classification)](#0-first-split-into-read--write-the-official-top-level-classification)
- [1. Five-type triage table](#1-five-type-triage-table)
- [2. Quantitative entry points](#2-quantitative-entry-points)
- [3. Avoid hotspots at table-creation time (official guidance, lowest cost)](#3-avoid-hotspots-at-table-creation-time-official-guidance-lowest-cost)
- [4. The full cost of a salt / bucket scheme](#4-the-full-cost-of-a-salt--bucket-scheme)
- [5. Bulk-update hotspots (a common variant of `single_row`)](#5-bulk-update-hotspots-a-common-variant-of-single_row)
- [6. Output contract](#6-output-contract)

<!-- /toc -->

Subpartitioning does **not necessarily** break up a single-key hotspot: if the hotspot is
one specific `user_id`, the subpartition HASH still takes the modulus of `user_id`, so
that user's requests keep landing on the same subpartition. So you must classify the
hotspot type first, then propose a fix.

## 0. First split into read / write (the official top-level classification)

The official "Hotspot Table Best Practices" first splits by read/write direction —
**the fixes for the two classes barely overlap**, and getting the direction wrong makes
everything downstream wrong too:

| Class | Characteristics | Typical tables | Fix direction |
|---|---|---|---|
| **Read-intensive hotspot** | Repeated access to **the same row** within a short window | Config/parameter tables, traffic-routing rule tables, feature-flag tables | **Duplicated table**, application-side cache, rate limiting, avoiding high-frequency access to hot data on the application side |
| **Write-intensive hotspot** | Concentrated insert / update / delete | Buffer tables, transaction tables, log tables | Partitioning strategy, batching, async writes, adaptive load balancing |

**A read hotspot cannot be fixed by partitioning** — split a 100-row config table into
16 partitions and the hot row is still that one row. The correct fix is a
`DUPLICATE_SCOPE = 'cluster'` duplicated table (every replica holds the full data set,
reads can be served locally, at the cost of some write performance in exchange for read
concurrency) — see `tablegroup.md` §1.

The earlier four-type triage in this file was entirely write-side; read hotspots had
nowhere to be classified, so a read hotspot on a config table would get misdirected
toward "add partitions / add buckets" — which does nothing useful, and bucketing would
actually amplify reads by N×.

Decision entry point: Step 1's `access_patterns.read_hot_single_key` together with
`read_qps` / `write_qps`.

## 1. Five-type triage table

| Hotspot type | Read/write | Quantitative signature | Typical treatment |
|---|---|---|---|
| `read_hot_row` | read | Extremely high `read_qps` on a single row, extremely low `write_qps`; in the audit view, `total_row_count` is high while `return_rows` is tiny | **Duplicated table**, application cache, rate limiting; **do not add partitions/buckets** |
| `single_row` | write | High update QPS on a single row, visible lock waits (`event` shows row-lock waits, `retry_cnt` is elevated) | Business-level splitting, incremental sharding, async aggregation; explicit transactions committed as early as possible, defer updates to the commit point; introduce a partition-key dimension to turn single-row contention into multi-row contention |
| `single_partition` | write | `top1_key_share` is clearly higher than `1/partition_count` | salt/bucket column + query-side fan-out; or change the partition key |
| `range_tail` | write | Writes concentrated on the newest RANGE partition | RANGE + HASH subpartition combination, pre-created partitions |
| `leader_skew` | read+write | One OBServer's CPU/network usage is disproportionately high; the audit view is clearly unbalanced when aggregated by `svr_ip` | Primary Zone, load balancing, table group `SCOPE` (see `tablegroup.md` §3) |

A single table can hit multiple types at once (for example `range_tail` + `leader_skew`).
When multiple types are hit, give a mitigation for each — do not stop after reporting
just one.

## 2. Quantitative entry points

Classification depends on the values collected in Step 1; when they're missing, the
hotspot conclusion can only be `unverified` (see `input-collection.md` §2–§3 for the
collection SQL):

- `distinct_count`: cardinality of the partition key
- `top1_key_share`: share of the largest key
- `read_qps` / `write_qps` / `read_hot_single_key`: distinguish read hotspots from write hotspots

The baseline for judging skew is `1 / partition_count`. `top1_key_share` clearly above
that value counts as skew.

**Never output `types: [none]` when `top1_key_share` is missing** — "not measured" is
not the same as "no hotspot." That situation must always be `result: unverified`.

## 3. Avoid hotspots at table-creation time (official guidance, lowest cost)

The cheapest point to handle a hotspot is at table creation, not after the fact. Three
official design-time principles:

1. **Primary key choice**: avoid an auto-increment ID as the primary key (it easily
   causes write hotspots); use a **composite primary key** or a distributed ID instead;
   account for the distribution characteristics inherent to the business logic. See the
   related cost in `indexes.md` §4 and `capability-matrix.md` §4.3.
2. **Partitioning strategy**: partition log/journal tables by time; partition
   user-related tables by `user_id`; partition multi-tenant scenarios by business
   dimension.
3. **Index design**: avoid single-point hotspot indexes; design composite indexes
   sensibly; account for the dispersion of query patterns.

Official example (composite primary key + partitioning by `user_id`):

```sql
CREATE TABLE user_order (
    user_id      BIGINT,                 -- partition key
    sequence_id  BIGINT,
    order_amount DECIMAL(10,2),
    create_time  TIMESTAMP,
    PRIMARY KEY (user_id, sequence_id)   -- composite primary key, not an auto-increment column
) PARTITION BY HASH(user_id) PARTITIONS 16;
```

## 4. The full cost of a salt / bucket scheme

When introducing a bucket column to break up a **write** hotspot (`single_partition`),
you must also provide:

1. How the write side chooses a bucket (random / hash / round-robin), and whether that
   affects idempotency;
2. The query-side fan-out multiplier (= number of buckets) and the aggregation cost;
3. Whether it breaks an existing unique constraint (the bucket column usually has to be
   folded into the primary key);
4. The cost of changing the bucket count (changing the count requires redistributing
   data).

Saying only "add a salt to spread it out" without these four items is an incomplete
proposal.

## 5. Bulk-update hotspots (a common variant of `single_row`)

When performing large-scale update/delete on a hotspot table, doing it row by row
causes severe lock contention. The official processing order:

1. Use an appropriate partitioning strategy and **process partition by partition, in
   batches**;
2. Replace bulk DELETE with `TRUNCATE PARTITION` / `DROP PARTITION`;
3. Bound the size of each batch to avoid oversized transactions.

For the relationship to queuing tables, see `storage-format.md` §5.2 — the two are
often two sides of the same table.

## 6. Output contract

```yaml
hotspot:
  types: []                    # can be multi-valued: read_hot_row | single_row | single_partition
                               #          | range_tail | leader_skew | none
  direction: read | write | both | none
  evidence:
    top1_key_share:
    distinct_count:
    read_qps:
    write_qps:
    audit_signal:              # observations of event / retry_cnt / total_row_count from GV$OB_SQL_AUDIT
  mitigation:                  # given per type
  query_amplification:         # required when a bucket is introduced: fan-out and aggregation cost
  design_time_avoidance:       # whether it could have been avoided at table-creation time (§3), required
  result: pass | fail | unverified
```

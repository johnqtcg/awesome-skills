# Hotspot Classification and Mitigation

<!-- toc -->

**Table of Contents**

- [0. First split into read / write (the official top-level classification)](#0-first-split-into-read--write-the-official-top-level-classification)
- [1. Five-type triage table](#1-five-type-triage-table)
- [2. Quantitative entry points](#2-quantitative-entry-points)
- [3. Avoid hotspots at table-creation time (official guidance, lowest cost)](#3-avoid-hotspots-at-table-creation-time-official-guidance-lowest-cost)
- [4. The full cost of a salt / bucket scheme](#4-the-full-cost-of-a-salt--bucket-scheme)
  - [4.1 Why "introduce a partition key" cannot break up a single-row hotspot on its own](#41-why-introduce-a-partition-key-cannot-break-up-a-single-row-hotspot-on-its-own)
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
| `single_row` | write | High update QPS on a single row, visible lock waits (`event` shows row-lock waits, `retry_cnt` is elevated) | **Add a dimension to the primary key so one row becomes N rows** (counter sharding, or splitting by a real business dimension), *then* fold that column into the partition key to spread those N rows across Tablets — **the order cannot be reversed: partitioning alone cannot break up a single row, see §4.1**; pair with async aggregation, explicit transactions committed early, updates deferred to the commit point |
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

When introducing a bucket / shard column to break up a **write** hotspot — both the
`single_partition` case (changing the partition key) and the `single_row` case
(counter sharding, which **is** a salt scheme and carries the same four costs) —
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

### 4.1 Why "introduce a partition key" cannot break up a single-row hotspot on its own

A common wrong causal chain is "give the table a partition key and single-row contention becomes
multi-row contention." **That is backwards.**

**Partitioning operates at row granularity.** It decides *which Tablet a row lives in*; it cannot
split one row into several. So for a hotspot on `goods_id = 3678`: whether you write
`HASH(goods_id) PARTITIONS 16` or a 100-way LIST, that row still lands in exactly **one** partition
and the same single row lock still serialises every update. This is the same argument as the
opening line of this file — "partition a 100-row config table 16 ways and the hot row is still that
one row" — and **it holds identically on the write side.**

What actually works is **changing the data model so there are more rows**; partitioning is only the
second, flattening step:

```
Step 1 (decisive) : add a dimension to the primary key → 1 row becomes N rows → row-lock contention drops to 1/N
Step 2 (optional) : fold that column into the partition key → N rows land on N Tablets → also flattens Tablet/log-level contention
```

**Shape A — the hot row is one business entity's own counter** (stock, balance, like count). The only
option is to invent a sharding dimension.

```sql
-- Before: one row; every decrement queues on its lock
CREATE TABLE goods_stock (
    goods_id NUMBER PRIMARY KEY,
    stock    NUMBER
);
-- data: (3678, 1000)

-- After: the same product becomes N rows
CREATE TABLE goods_stock (
    goods_id NUMBER,
    shard_no NUMBER,                       -- the invented sharding dimension
    stock    NUMBER,
    PRIMARY KEY (goods_id, shard_no)       -- <- THIS is what turns 1 row into N
)
PARTITION BY HASH (goods_id, shard_no) PARTITIONS 16;   -- <- step 2: spread the N rows
-- data: (3678,0,100) (3678,1,100) ... (3678,9,100)
```

```sql
-- Write: land on a random shard; row-lock contention drops to 1/10
UPDATE goods_stock SET stock = stock - 1
 WHERE goods_id = 3678 AND shard_no = MOD(:rand, 10) AND stock > 0;

-- Read: must aggregate (this is the concrete form of §4 item 2's fan-out cost)
SELECT SUM(stock) FROM goods_stock WHERE goods_id = 3678;
```

Shape A carries a **correctness cost that must appear in the design**: after sharding, one shard can
reach zero while others still hold stock, so a decrement fails even though the product is not sold
out. State the handling (retry against another shard, or periodic shard rebalancing) — otherwise this
is a business bug, not a performance optimisation.

**Shape B — the hot row is one row shared by many business entities** (a global counter or rollup
row). Here the "introduced dimension" is a **real business dimension**, no invented shard column is
needed, and the cost is far lower.

```sql
-- Before: every merchant updates the same row
CREATE TABLE daily_stat (biz_date DATE PRIMARY KEY, total NUMBER);

-- After: split by merchant; 1 row becomes N rows
CREATE TABLE daily_stat (
    merchant_code VARCHAR2(100),
    biz_date      DATE,
    total         NUMBER,
    PRIMARY KEY (merchant_code, biz_date)
) PARTITION BY HASH (merchant_code) PARTITIONS 16;
```

Shape B needs aggregation only for a global total; querying one merchant is *more* precise than
before. **Prefer B over A whenever possible.** The test: ask "does this row represent one entity, or
several entities merged together?" — merged means B is available.

**Single-node note**: step 2 buys much less on a single node — row-lock contention is already down to
1/N from step 1, and partitioning then only reduces Tablet/memtable contention, with no cross-node
distribution to gain. So on a single-node deployment **step 1 is nearly all of the benefit**; do not
skip it because the partitioning change looks like work.

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

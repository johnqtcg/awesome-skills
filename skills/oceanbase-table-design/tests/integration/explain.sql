-- V3 plan verification: partition pruning, index selection, join localization.
-- Prerequisite: run mysql_mode.sql and tablegroup.sql first.
-- Judgment rule (references/verification.md V3):
--   when EXPLAIN for dominant_pattern hits more than 1 partition, checks.partition_pruning
--   must be fail — do not mark it pass just because "the design intent is pruning."

USE obtd_it;

-- E1 single-partition point lookup: the hit partition count must be 1
EXPLAIN SELECT * FROM t_hash WHERE user_id = 12345;

-- E2 query without the partition key: should show a full partition scan (control case, to prove the pruning conclusion isn't a guess)
EXPLAIN SELECT * FROM t_hash WHERE nick = 'x';

-- E3 RANGE time pruning: should hit only p2025
EXPLAIN SELECT * FROM t_range
 WHERE tx_time >= '2025-06-01' AND tx_time < '2025-07-01';

-- E4 RANGE without a time condition: should be a full partition scan
EXPLAIN SELECT COUNT(*) FROM t_range;

-- E5 second-level partitions: both the first and second level should prune
EXPLAIN SELECT * FROM t_sub
 WHERE tx_time >= '2025-06-01' AND tx_time < '2025-07-01' AND bucket = 3;

-- E6 LIST pruning
EXPLAIN SELECT * FROM t_list WHERE region_id = 2;

-- E7 global unique index path: query does not include the base table's partition key, should use the global index
EXPLAIN SELECT user_id FROM t_global_uk WHERE email = 'a@b.c';

-- E8 local index vs. global index comparison: with the partition key present, should use the local path
EXPLAIN SELECT user_id FROM t_global_uk WHERE user_id = 1 AND email = 'a@b.c';

-- E9 table-group co-located join: should be a local join, no distributed exchange operator should appear in the plan
EXPLAIN SELECT u.user_id, a.amt
  FROM tg_users u JOIN tg_accounts a ON u.user_id = a.user_id
 WHERE u.user_id = 12345;

-- E10 non-co-located join comparison: same condition but the tables are not in the same table group, a cross-node exchange should appear
EXPLAIN SELECT u.user_id, a.amt
  FROM tg_users_nogroup u JOIN tg_accounts_nogroup a ON u.user_id = a.user_id
 WHERE u.user_id = 12345;

-- E11 duplicated-table join: the small dimension table should be able to join locally on any node
EXPLAIN SELECT o.user_id, c.rate
  FROM t_hash o JOIN dim_currency c ON c.code = 'USD'
 WHERE o.user_id = 12345;

-- E12/E13 depend on columnstore tables and Skip Index, and have been split off by version into
--   explain_v430.sql (columnstore, >= V4.3.0)
--   mysql_probe.sql (Skip Index, minimum version not yet confirmed)

-- Record the actual number of partitions each SQL statement hits, to backfill checks.partition_pruning.evidence
-- (the EXPLAIN output fields differ slightly across versions; keep the raw text when backfilling)

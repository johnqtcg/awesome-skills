-- V4 capacity verification: reconciling the actual Tablet count against estimate_tablets.py's estimate,
-- and reading the **real per-node limit** (rather than trusting the formula-derived estimate).
-- Basis: references/tablet-capacity.md §1 / §2 / §7

USE obtd_it;

-- ============ 1. Actual Tablet count (including indexes) ============
-- Reconcile table-by-table against estimate_tablets.py's breakdown; a deviation > 10% means the estimate missed some object type
SELECT TABLE_NAME, TABLE_TYPE, COUNT(*) AS tablet_cnt
  FROM oceanbase.DBA_OB_TABLETS
 GROUP BY TABLE_NAME, TABLE_TYPE
 ORDER BY tablet_cnt DESC;

-- Restricted to this database only, broken down by base table / local index / global index
SELECT DATABASE_NAME, TABLE_NAME, INDEX_NAME,
       COUNT(DISTINCT TABLET_ID) AS tablets
  FROM oceanbase.DBA_OB_TABLE_LOCATIONS
 WHERE DATABASE_NAME = 'obtd_it'
 GROUP BY DATABASE_NAME, TABLE_NAME, INDEX_NAME
 ORDER BY TABLE_NAME, INDEX_NAME;

-- [Key reconciliation point] t_hash has 16 partitions + if 3 local indexes are added to it, the Tablet count should be 16 * 4 = 64, not 16
CREATE INDEX idx_h1 ON t_hash(nick) LOCAL;
CREATE INDEX idx_h2 ON t_hash(nick, user_id) LOCAL;
CREATE INDEX idx_h3 ON t_hash(user_id, nick) LOCAL;
SELECT COUNT(DISTINCT TABLET_ID) AS should_be_64
  FROM oceanbase.DBA_OB_TABLE_LOCATIONS
 WHERE DATABASE_NAME = 'obtd_it' AND TABLE_NAME = 't_hash';

-- A global index has its own independent partitioning rule: with 8 partitions here, it should contribute 8 additional Tablets
CREATE INDEX gidx_h ON t_hash(nick) GLOBAL PARTITION BY HASH(nick) PARTITIONS 8;
SELECT INDEX_NAME, COUNT(DISTINCT TABLET_ID) AS tablets
  FROM oceanbase.DBA_OB_TABLE_LOCATIONS
 WHERE DATABASE_NAME = 'obtd_it' AND TABLE_NAME = 't_hash'
 GROUP BY INDEX_NAME;

-- ============ 2. Real per-node limit (takes priority over the formula) ============
-- LIMIT_VALUE is the limit actually in effect; EFFECTIVE_LIMIT_TYPE indicates whether it comes from configuration or memory
SELECT SVR_IP, SVR_PORT, TENANT_ID, ZONE, RESOURCE_TYPE,
       CURRENT_UTILIZATION, MAX_UTILIZATION, LIMIT_VALUE, EFFECTIVE_LIMIT_TYPE
  FROM GV$OB_TENANT_RESOURCE_LIMIT
 WHERE RESOURCE_TYPE = 'tablet';

-- Detail of each limit source: verify which one of min(configuration, memory) is actually in effect
SELECT SVR_IP, SVR_PORT, TENANT_ID, RESOURCE_TYPE, LIMIT_TYPE, LIMIT_VALUE
  FROM GV$OB_TENANT_RESOURCE_LIMIT_DETAIL
 WHERE RESOURCE_TYPE = 'tablet'
 ORDER BY SVR_IP, LIMIT_TYPE;

-- ============ 3. Authoritative source for the formula's inputs ============
-- Unit memory (MEMORY_SIZE in the formula; note this is the memory of the user tenant's unit, not the tenant's total spec)
SELECT SVR_IP, SVR_PORT, TENANT_ID, UNIT_ID, ZONE,
       MAX_CPU, MIN_CPU, MEMORY_SIZE, LOG_DISK_SIZE
  FROM GV$OB_UNITS;

-- Number of units per Zone (unit_num in the formula, used for single-node estimation)
SELECT ZONE, COUNT(*) AS unit_num FROM GV$OB_UNITS GROUP BY ZONE;

-- Actual values of hidden parameters: if different from the defaults, they must be fed into estimate_tablets.py as input
SHOW PARAMETERS LIKE '%max_tablet_cnt_per_gb%';
SHOW PARAMETERS LIKE '%storage_meta_memory_limit_percentage%';
SHOW PARAMETERS LIKE '%max_partition_num%';
SHOW PARAMETERS LIKE '%auto_split_tablet_size%';
SHOW PARAMETERS LIKE '%enable_auto_split%';

-- ============ 4. Auto-partitioning attribute check ============
SELECT TABLE_NAME, CREATE_OPTIONS
  FROM information_schema.TABLES
 WHERE TABLE_SCHEMA = 'obtd_it' AND TABLE_NAME IN ('t_autosplit', 't_dynpart');

-- Backfill requirement: feed §2's LIMIT_VALUE and §3's MEMORY_SIZE / unit_num
-- into scripts/estimate_tablets.py, and confirm that per_node_limit matches LIMIT_VALUE.
-- If they do not match, it means the model in tablet-capacity.md §2 needs correction.

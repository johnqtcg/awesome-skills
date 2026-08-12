-- Version probe (**recorded only, not asserted**).
--
-- The results of these statements are themselves the thing being observed — success and failure are both "correct" across different versions:
--   * SCOPE syntax: should succeed on >= V4.4.2 BP1; should raise a syntax error below BP1
--   * SHARDING = NONE's leader distribution: below BP1, consolidation onto a single node is expected; on >= BP1 it is no longer enforced
-- Therefore the driver script **does not assert on the exit code** for this file — it only requires non-empty output that gets archived,
-- and a human (or a later backfill script) writes the observed values back into references/.
--
-- The reason for doing it this way: mixing "version-dependent observations" and "version-independent assertions" in the same file
-- would force using `|| true` to ignore the exit code, which would let real failures slip through at the same time.

USE obtd_it;

-- ============ Observation 1: SCOPE syntax availability (>= V4.4.2 BP1) ============
CREATE TABLEGROUP tg_scope_server  SHARDING = 'PARTITION' SCOPE = 'SERVER';
CREATE TABLEGROUP tg_scope_zone    SHARDING = 'PARTITION' SCOPE = 'ZONE';
CREATE TABLEGROUP tg_scope_cluster SHARDING = 'PARTITION' SCOPE = 'CLUSTER';

-- For table groups upgraded from an older version, SCOPE should be NULL
SELECT * FROM oceanbase.DBA_OB_TABLEGROUPS;
SHOW TABLEGROUPS;

-- ============ Observation 2: whether SHARDING = NONE's Leader is concentrated on a single machine ============
-- This is the only fork point in this Skill where the risk conclusion **reverses** — the measured value must be recorded for each version.
--   Expected (< V4.4.2 BP1): leader_hosts = 1 (the old "consolidated on a single node" semantics)
--   Expected (>= V4.4.2 BP1): leader_hosts > 1 or varies with SCOPE (this semantics has been removed)
SELECT TABLE_NAME, PARTITION_NAME, SVR_IP, SVR_PORT, ROLE
  FROM oceanbase.DBA_OB_TABLE_LOCATIONS
 WHERE DATABASE_NAME = 'obtd_it' AND TABLE_NAME IN ('tg_none_t1','tg_none_t2')
 ORDER BY TABLE_NAME, PARTITION_NAME;

SELECT TABLE_NAME, COUNT(DISTINCT SVR_IP) AS leader_hosts
  FROM oceanbase.DBA_OB_TABLE_LOCATIONS
 WHERE DATABASE_NAME = 'obtd_it' AND ROLE = 'LEADER'
   AND TABLE_NAME IN ('tg_none_t1','tg_none_t2')
 GROUP BY TABLE_NAME;

-- Backfill location: the version-fork table in references/tablegroup.md §2.1 + results/<ver>/summary.txt

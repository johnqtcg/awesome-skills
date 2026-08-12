-- Split out from the upstream script by "capability-confirmation tier / minimum version."
-- Basis: references/capability-matrix.md, SKILL.md section 2 "Capability Confirmation Tiers"

-- **Only recorded, not asserted.** Both sections are unverified behavior observations:
--   1. The actual pre-creation/reclamation behavior of DYNAMIC_PARTITION_POLICY (C2, minimum version not yet confirmed)
--   2. The interaction between DROP PARTITION and global-index rebuild (open item in capability-matrix §5-2)
-- Only after the observation results are backfilled can the corresponding conclusion be upgraded from unverified to confirmed behavior.

USE obtd_it;

-- Note: this section depends on t_dynpart created by mysql_probe.sql; if this version does not support it, an empty query result is itself a valid observation.
-- ============ 4. Actual behavior of the dynamic partitioning policy ============
SELECT TABLE_NAME, PARTITION_NAME, PARTITION_DESCRIPTION
  FROM information_schema.PARTITIONS
 WHERE TABLE_SCHEMA = 'obtd_it' AND TABLE_NAME = 't_dynpart'
 ORDER BY PARTITION_ORDINAL_POSITION;
-- Observation point: whether PRECREATE_TIME='7 day' actually pre-creates partitions for the next 7 days;
--         whether EXPIRE_TIME='90 day' reclaims expired partitions.
-- Note: dynamic partitioning is driven by a background scheduler; observation requires waiting for one scheduling cycle.

-- ============ 5. Interaction between archiving x global index (an item this Skill marks as unverified) ============
-- Purpose: measure whether DROP/TRUNCATE PARTITION invalidates the global index and triggers a rebuild, and how long it takes
CREATE TABLE t_archive (
  id      BIGINT    NOT NULL,
  tx_time TIMESTAMP NOT NULL,
  biz_no  VARCHAR(64) NOT NULL,
  PRIMARY KEY (id, tx_time)
) PARTITION BY RANGE(UNIX_TIMESTAMP(tx_time)) (
  PARTITION p1 VALUES LESS THAN (UNIX_TIMESTAMP('2026-01-01')),
  PARTITION p2 VALUES LESS THAN (UNIX_TIMESTAMP('2026-02-01')),
  PARTITION pmax VALUES LESS THAN MAXVALUE
);
CREATE INDEX gidx_biz ON t_archive(biz_no) GLOBAL;

-- Record the index status and elapsed time before and after dropping the partition
SELECT INDEX_NAME, STATUS FROM oceanbase.DBA_OB_TABLE_INDEXES
 WHERE DATABASE_NAME='obtd_it' AND TABLE_NAME='t_archive';

SELECT NOW() AS before_drop;
ALTER TABLE t_archive DROP PARTITION p1;
SELECT NOW() AS after_drop;

SELECT INDEX_NAME, STATUS FROM oceanbase.DBA_OB_TABLE_INDEXES
 WHERE DATABASE_NAME='obtd_it' AND TABLE_NAME='t_archive';

-- Background rebuild task
SELECT * FROM oceanbase.DBA_OB_DDL_OPERATIONS ORDER BY GMT_CREATE DESC LIMIT 10;

-- Backfill requirement: write the results back into capability-matrix.md §5-2,
-- turning "the interaction between DROP/TRUNCATE PARTITION and the global index" from an open item into a confirmed conclusion (or refuting it).


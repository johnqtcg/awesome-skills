-- Split out from mysql_mode.sql by "capability-confirmation tier / minimum version."
-- Reason for the split: if the runner ran the same positive-example script against every target version,
--   a lower version lacking the capability would misreport "version not supported" as the entire positive-example suite failing.
-- Basis: references/capability-matrix.md, SKILL.md section 2 "Capability Confirmation Tiers"

-- Applies to: target version >= V4.3.5 (auto-partition splitting SIZE, minimum version confirmed, C1)

USE obtd_it;

-- 18) Auto-partitioning (>= V4.3.5): first-level RANGE + has a primary key + partition key is a prefix of the primary key
CREATE TABLE t_autosplit (
  id      BIGINT NOT NULL,
  payload VARCHAR(128),
  PRIMARY KEY (id)
) PARTITION BY RANGE(id) SIZE('2G');


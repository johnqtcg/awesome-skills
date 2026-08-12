-- Split out from mysql_mode.sql by "capability-confirmation tier / minimum version."
-- Reason for the split: if the runner ran the same positive-example script against every target version,
--   a lower version lacking the capability would misreport "version not supported" as the entire positive-example suite failing.
-- Basis: references/capability-matrix.md, SKILL.md section 2 "Capability Confirmation Tiers"

-- Applies to: target version >= V4.3.5 BP1 (heap table ORGANIZATION, minimum version confirmed, C1)

USE obtd_it;

-- 13) Heap table (>= V4.3.5 BP1, MySQL mode only)
CREATE TABLE t_heap (
  uuid_key CHAR(36) NOT NULL,
  payload  VARCHAR(256),
  PRIMARY KEY (uuid_key)
) ORGANIZATION = HEAP;


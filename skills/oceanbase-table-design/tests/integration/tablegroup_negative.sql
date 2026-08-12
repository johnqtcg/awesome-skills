-- V2 negative example: table groups. **Every single case should error**; judged case-by-case by scripts/check_negative_log.py.
-- Prerequisite: run tablegroup.sql (positive example) first to set up tg_user / tg_ad.
-- Version-independent: these three cases behave consistently across all 4.x versions, so they can be asserted as fixed.
-- The version-dependent SCOPE syntax probe lives in tablegroup_probe.sql and is not asserted.

USE obtd_it;

-- N1  SHARDING = 'PARTITION' requires all tables in the group to have identical first-level partition definitions; a different partition count should error
SELECT '@@CASE:N1' AS marker;
CREATE TABLE tg_bad_partcount (
  user_id BIGINT NOT NULL, PRIMARY KEY (user_id)
) TABLEGROUP = tg_user PARTITION BY HASH(user_id) PARTITIONS 8;

-- N2  SHARDING = 'ADAPTIVE' requires all tables in the group to be either all first-level or all second-level partitioned;
--     adding a first-level partitioned table into an all-second-level group should error
SELECT '@@CASE:N2' AS marker;
CREATE TABLE tg_ad_bad (
  a BIGINT NOT NULL, PRIMARY KEY (a)
) TABLEGROUP = tg_ad PARTITION BY HASH(a) PARTITIONS 8;

-- N3  adding an existing table with a mismatched partition definition into the table group should error
SELECT '@@CASE:N3' AS marker;
ALTER TABLEGROUP tg_user ADD t_key;

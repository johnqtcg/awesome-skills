-- Split out from the upstream script by "capability-confirmation tier / minimum version."
-- Basis: references/capability-matrix.md, SKILL.md section 2 "Capability Confirmation Tiers"

-- Applies to: target version >= V4.3.0, and mysql_v430.sql must be run first to create t_col / t_htap
-- Purpose: confirm that each column and all columns, each column are not synonymous

USE obtd_it;

-- ============ 1. Actual differences among the three Column Group forms ============
-- Purpose: confirm that each column and all columns, each column are not synonymous
SELECT TABLE_NAME, COLUMN_GROUP_NAME, COLUMN_GROUP_TYPE
  FROM oceanbase.DBA_OB_COLUMN_GROUPS
 WHERE TABLE_ID IN (
   SELECT TABLE_ID FROM oceanbase.DBA_OB_TABLES
    WHERE DATABASE_NAME = 'obtd_it' AND TABLE_NAME IN ('t_col','t_htap','t_hash')
 ) ORDER BY TABLE_NAME, COLUMN_GROUP_NAME;

-- Storage-footprint comparison: t_htap (row-and-column redundancy) should be significantly larger than t_col (pure columnstore) at the same data volume
-- Load the same data into both before comparing (adjust row counts as needed)
SELECT TABLE_NAME, SUM(DATA_SIZE) AS data_size, SUM(REQUIRED_SIZE) AS required_size
  FROM oceanbase.DBA_OB_TABLE_LOCATIONS l
  JOIN oceanbase.DBA_OB_TABLETS t ON l.TABLET_ID = t.TABLET_ID
 WHERE l.DATABASE_NAME = 'obtd_it' AND l.TABLE_NAME IN ('t_col','t_htap')
 GROUP BY TABLE_NAME;

-- ============ 2. Evolution path: adding columnstore to a row-storage table on demand ============
ALTER TABLE t_hash ADD COLUMN GROUP(each column);
SELECT TABLE_NAME, COLUMN_GROUP_NAME FROM oceanbase.DBA_OB_COLUMN_GROUPS
 WHERE TABLE_ID = (SELECT TABLE_ID FROM oceanbase.DBA_OB_TABLES
                    WHERE DATABASE_NAME='obtd_it' AND TABLE_NAME='t_hash');
ALTER TABLE t_hash DROP COLUMN GROUP(each column);


-- Split out from the upstream script by "capability-confirmation tier / minimum version."
-- Basis: references/capability-matrix.md, SKILL.md section 2 "Capability Confirmation Tiers"

-- Applies to: target version >= V4.3.0, and mysql_v430.sql must be run first to create t_col

USE obtd_it;

-- E12 columnstore table aggregation: should use the columnstore scan path
EXPLAIN SELECT stat_date, SUM(m1) FROM t_col
 WHERE stat_date >= '2025-01-01' GROUP BY stat_date;


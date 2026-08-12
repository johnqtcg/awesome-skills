-- Split out from the upstream script by "capability-confirmation tier / minimum version."
-- Basis: references/capability-matrix.md, SKILL.md section 2 "Capability Confirmation Tiers"

-- Applies to: all 4.x versions (queue-table mode query, no version dependency)

USE obtd_it;

-- ============ 6. Queue-table behavior ============
-- Whether scan cost degrades after heavy insert/delete (comparison for QUEUING mode)
SELECT TABLE_NAME, TABLE_MODE FROM oceanbase.DBA_OB_TABLES
 WHERE DATABASE_NAME='obtd_it' AND TABLE_NAME IN ('t_queue','t_hash');

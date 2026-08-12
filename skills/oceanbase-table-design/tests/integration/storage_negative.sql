-- V2 negative example: storage-form combination. **Should error**; judged case-by-case by scripts/check_negative_log.py.
-- Prerequisite: run mysql_v435.sql first (creates t_autosplit).
-- Therefore this file's minimum version = V4.3.5; below that version the runner will skip it,
-- rather than letting it error with "table does not exist" and pass falsely.

USE obtd_it;

-- N1  auto-partitioned tables do not support columnstore (partitioning.md §3.1)
SELECT '@@CASE:N1' AS marker;
ALTER TABLE t_autosplit ADD COLUMN GROUP(each column);

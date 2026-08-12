-- Split out from mysql_mode.sql by "capability-confirmation tier / minimum version."
-- Reason for the split: if the runner ran the same positive-example script against every target version,
--   a lower version lacking the capability would misreport "version not supported" as the entire positive-example suite failing.
-- Basis: references/capability-matrix.md, SKILL.md section 2 "Capability Confirmation Tiers"

-- Applies to: target version >= V4.3.0 (columnstore engine, minimum version confirmed, C1)

USE obtd_it;

-- 15) Pure columnstore (each column)
CREATE TABLE t_col (
  id        BIGINT NOT NULL,
  stat_date DATE   NOT NULL,
  d1 VARCHAR(32), d2 VARCHAR(32), m1 DECIMAL(18,2), m2 DECIMAL(18,2),
  PRIMARY KEY (id, stat_date)
) PARTITION BY RANGE COLUMNS(stat_date) (
  PARTITION p1 VALUES LESS THAN ('2026-01-01'),
  PARTITION pmax VALUES LESS THAN (MAXVALUE)
) WITH COLUMN GROUP(each column);

-- 16) Row-and-column redundancy (all columns, each column) — roughly 2x storage
CREATE TABLE t_htap (
  id BIGINT PRIMARY KEY,
  d1 VARCHAR(32), m1 DECIMAL(18,2)
) WITH COLUMN GROUP(all columns, each column);


-- V2 positive example (**version-independent, should succeed on all 4.x**): basic table creation in MySQL compatibility mode.
-- Version-dependent capabilities have been split out into mysql_v430.sql / mysql_v435.sql /
-- mysql_v435bp1.sql / mysql_probe.sql.
-- Basis: references/capability-matrix.md §1.1/§1.2, references/partitioning.md
-- Before running, confirm that the current tenant is in MySQL compatibility mode.

DROP DATABASE IF EXISTS obtd_it;
CREATE DATABASE obtd_it;
USE obtd_it;

-- 1) HASH: the partition key must be an integer or YEAR; expressions are allowed
CREATE TABLE t_hash (
  user_id  BIGINT      NOT NULL,
  nick     VARCHAR(64),
  PRIMARY KEY (user_id)
) COMMENT 'integer HASH' DEFAULT CHARSET = utf8mb4
PARTITION BY HASH(user_id) PARTITIONS 16;

-- 2) KEY: multi-column / non-integer keys (this syntax does not exist in Oracle mode)
CREATE TABLE t_key (
  tenant_id VARCHAR(32) NOT NULL,
  user_id   BIGINT      NOT NULL,
  PRIMARY KEY (tenant_id, user_id)
) PARTITION BY KEY(tenant_id, user_id) PARTITIONS 16;

-- 3) KEY() with an empty column list: the partition key is the primary key
CREATE TABLE t_key_empty (
  id   BIGINT PRIMARY KEY,
  memo VARCHAR(64)
) PARTITION BY KEY() PARTITIONS 5;

-- 4) RANGE: integer or YEAR, single column only; allowlisted function expressions are allowed
CREATE TABLE t_range (
  id      BIGINT      NOT NULL,
  tx_time TIMESTAMP   NOT NULL,
  PRIMARY KEY (id, tx_time)
) PARTITION BY RANGE(UNIX_TIMESTAMP(tx_time)) (
  PARTITION p2024 VALUES LESS THAN (UNIX_TIMESTAMP('2025-01-01')),
  PARTITION p2025 VALUES LESS THAN (UNIX_TIMESTAMP('2026-01-01')),
  PARTITION pmax  VALUES LESS THAN MAXVALUE
);

-- 5) RANGE COLUMNS: wider type support, expressions not allowed, supports multiple columns
CREATE TABLE t_range_columns (
  tenant_id VARCHAR(32) NOT NULL,
  stat_date DATE        NOT NULL,
  amt       DECIMAL(18,2),
  PRIMARY KEY (tenant_id, stat_date)
) PARTITION BY RANGE COLUMNS(tenant_id, stat_date) (
  PARTITION p_a VALUES LESS THAN ('t50', '2026-01-01'),
  PARTITION p_b VALUES LESS THAN ('t99', '2027-01-01'),
  PARTITION p_max VALUES LESS THAN (MAXVALUE, MAXVALUE)
);

-- 6) LIST: integer or YEAR, single column, with a DEFAULT fallback
CREATE TABLE t_list (
  region_id INT    NOT NULL,
  id        BIGINT NOT NULL,
  PRIMARY KEY (region_id, id)
) PARTITION BY LIST(region_id) (
  PARTITION p_cn VALUES IN (1, 3),
  PARTITION p_hk VALUES IN (2),
  PARTITION p_def VALUES IN (DEFAULT)
);

-- 7) LIST COLUMNS: string / multi-column enumeration
CREATE TABLE t_list_columns (
  region_code VARCHAR(8) NOT NULL,
  biz_type    VARCHAR(8) NOT NULL,
  id          BIGINT     NOT NULL,
  PRIMARY KEY (region_code, biz_type, id)
) PARTITION BY LIST COLUMNS(region_code, biz_type) (
  PARTITION p1 VALUES IN (('01','A'), ('03','A')),
  PARTITION p_def VALUES IN (DEFAULT)
);

-- 8) Second-level partitions: first-level business key + second-level HASH spread
CREATE TABLE t_sub (
  user_id BIGINT    NOT NULL,
  tx_time TIMESTAMP NOT NULL,
  bucket  INT       NOT NULL,
  PRIMARY KEY (user_id, tx_time, bucket)
) PARTITION BY RANGE(UNIX_TIMESTAMP(tx_time))
  SUBPARTITION BY HASH(bucket) SUBPARTITIONS 8 (
  PARTITION p2025 VALUES LESS THAN (UNIX_TIMESTAMP('2026-01-01')),
  PARTITION pmax  VALUES LESS THAN MAXVALUE
);

-- 9) A partitioned table with no primary key and no unique key: **must succeed** (indexes.md §1, third branch)
CREATE TABLE t_no_pk (
  event_time TIMESTAMP NOT NULL,
  payload    VARCHAR(256)
) PARTITION BY RANGE(UNIX_TIMESTAMP(event_time)) (
  PARTITION p1 VALUES LESS THAN (UNIX_TIMESTAMP('2026-01-01')),
  PARTITION pmax VALUES LESS THAN MAXVALUE
);

-- 10) No primary key but has a unique key, partition key ⊆ unique key: should succeed
CREATE TABLE t_uk_only (
  tenant_id BIGINT NOT NULL,
  biz_no    VARCHAR(64) NOT NULL,
  UNIQUE KEY uk_tenant_biz (tenant_id, biz_no)
) PARTITION BY HASH(tenant_id) PARTITIONS 8;

-- 11) Duplicated table: small dimension table, join localization
CREATE TABLE dim_currency (
  code VARCHAR(8) PRIMARY KEY,
  rate DECIMAL(18,8)
) DUPLICATE_SCOPE = 'cluster';

-- 12) Queue table
CREATE TABLE t_queue (
  id     BIGINT AUTO_INCREMENT PRIMARY KEY,
  status TINYINT
) TABLE_MODE = 'QUEUING' AUTO_INCREMENT_MODE = 'NOORDER';

-- 17) Unique key does not include the partition key -> explicit global unique index (should succeed)
CREATE TABLE t_global_uk (
  user_id BIGINT      NOT NULL,
  email   VARCHAR(128) NOT NULL,
  PRIMARY KEY (user_id),
  UNIQUE KEY uk_email (email) GLOBAL
) PARTITION BY HASH(user_id) PARTITIONS 8;

-- Verify: the actual partitions and Tablets created
SELECT TABLE_NAME, PART_LEVEL, COUNT(*) AS parts
  FROM oceanbase.DBA_OB_TABLE_LOCATIONS
 WHERE DATABASE_NAME = 'obtd_it' GROUP BY TABLE_NAME, PART_LEVEL ORDER BY TABLE_NAME;

-- V2 negative example: MySQL mode. **Every single case should error.**
-- Pass criterion = errors out. If any case succeeds, it means the target version's behavior is inconsistent with this Skill's L0 rules,
-- and the rule must be fixed (references/) — not the test case.
-- See ../../scripts/run_integration.sh for how to run it (use --force so obclient continues past errors),
-- judgment is done case-by-case by scripts/check_negative_log.py.
--
-- Version note: N7/N9/N10 use SIZE (>= V4.3.5), and N10 also uses columnstore (>= V4.3.0).
-- On targets below that minimum version, these statements will still error (syntax/feature not supported),
-- which likewise counts as "correctly rejected," so this file can be used as a negative-example assertion across all 4.x versions;
-- but when backfilling, note whether the error reason is "constraint violation" or "version not supported."

USE obtd_it;

-- N1  L0: when there is a primary key, the partition key must be a subset of the primary key
--     Expected error: partition key not in the primary key / A PRIMARY KEY must include all columns in the partitioning function
SELECT '@@CASE:N1' AS marker;
CREATE TABLE n_pk_missing_pkey (
  order_id BIGINT NOT NULL,
  user_id  BIGINT NOT NULL,
  PRIMARY KEY (order_id)
) PARTITION BY HASH(user_id) PARTITIONS 8;

-- N2  L0: a local unique key does not include the partition key (GLOBAL not explicitly declared)
--     Expected error: the unique index must include the partition key
SELECT '@@CASE:N2' AS marker;
CREATE TABLE n_local_uk (
  user_id BIGINT       NOT NULL,
  email   VARCHAR(128) NOT NULL,
  PRIMARY KEY (user_id),
  UNIQUE KEY uk_email (email) LOCAL
) PARTITION BY HASH(user_id) PARTITIONS 8;

-- N3  L0: in MySQL mode, the HASH partition key must be an integer or YEAR
--     Expected error: this field type is not supported as a HASH partition key
SELECT '@@CASE:N3' AS marker;
CREATE TABLE n_hash_varchar (
  user_code VARCHAR(32) NOT NULL,
  PRIMARY KEY (user_code)
) PARTITION BY HASH(user_code) PARTITIONS 8;

-- N4  L0: RANGE partition key supports only a single column (use RANGE COLUMNS for multiple columns)
SELECT '@@CASE:N4' AS marker;
CREATE TABLE n_range_multicol (
  a INT NOT NULL, b INT NOT NULL,
  PRIMARY KEY (a, b)
) PARTITION BY RANGE(a, b) (
  PARTITION p1 VALUES LESS THAN (10, 10)
);

-- N5  L0: RANGE boundaries must be strictly increasing
SELECT '@@CASE:N5' AS marker;
CREATE TABLE n_range_not_monotonic (
  id BIGINT NOT NULL, PRIMARY KEY (id)
) PARTITION BY RANGE(id) (
  PARTITION p1 VALUES LESS THAN (100),
  PARTITION p2 VALUES LESS THAN (50)
);

-- N6  L0: single-table partition count exceeds MySQL mode's max_partition_num (default 8192; Oracle mode uses a fixed 65536 and does not use this parameter)
--     first level 100 x second level 100 = 10000
SELECT '@@CASE:N6' AS marker;
CREATE TABLE n_too_many_parts (
  a INT NOT NULL, b INT NOT NULL,
  PRIMARY KEY (a, b)
) PARTITION BY HASH(a) SUBPARTITION BY HASH(b) SUBPARTITIONS 100 PARTITIONS 100;

-- N7  L0: auto-partitioning does not support tables with second-level partitions
SELECT '@@CASE:N7' AS marker;
CREATE TABLE n_autosplit_sub (
  id BIGINT NOT NULL, b INT NOT NULL,
  PRIMARY KEY (id, b)
) PARTITION BY RANGE(id) SIZE('2G')
  SUBPARTITION BY HASH(b) SUBPARTITIONS 4 (
  PARTITION p1 VALUES LESS THAN (1000)
);

-- N8  L0: auto-partitioning does not support tables without a primary key
SELECT '@@CASE:N8' AS marker;
CREATE TABLE n_autosplit_nopk (
  id BIGINT NOT NULL
) PARTITION BY RANGE(id) SIZE('2G');

-- N9  L0: auto-partitioning requires the partition key to be a prefix of the primary key
SELECT '@@CASE:N9' AS marker;
CREATE TABLE n_autosplit_not_prefix (
  a BIGINT NOT NULL, b BIGINT NOT NULL,
  PRIMARY KEY (a, b)
) PARTITION BY RANGE(b) SIZE('2G');

-- N10 L0: auto-partitioning does not support columnstore tables
SELECT '@@CASE:N10' AS marker;
CREATE TABLE n_autosplit_column (
  id BIGINT NOT NULL, PRIMARY KEY (id)
) PARTITION BY RANGE(id) SIZE('2G') WITH COLUMN GROUP(each column);

-- N11 L0: MySQL mode has no INTERVAL partitioning
SELECT '@@CASE:N11' AS marker;
CREATE TABLE n_mysql_interval (
  id BIGINT NOT NULL, dt DATE NOT NULL,
  PRIMARY KEY (id, dt)
) PARTITION BY RANGE(dt) INTERVAL (NUMTOYMINTERVAL(1,'MONTH')) (
  PARTITION p1 VALUES LESS THAN ('2026-01-01')
);

-- N12 L0: MySQL mode's LIST enumeration uses VALUES IN, not Oracle-style VALUES(...)
SELECT '@@CASE:N12' AS marker;
CREATE TABLE n_mysql_list_values (
  region_id INT NOT NULL, PRIMARY KEY (region_id)
) PARTITION BY LIST(region_id) (
  PARTITION p1 VALUES (1, 2)
);

-- N13 L0: auto-partition splitting is not supported inside a multi-table TABLEGROUP
SELECT '@@CASE:N13' AS marker;
CREATE TABLEGROUP n_tg SHARDING = 'PARTITION';
CREATE TABLE n_tg_t1 (id BIGINT NOT NULL, PRIMARY KEY (id))
  TABLEGROUP = n_tg PARTITION BY RANGE(id) (PARTITION p1 VALUES LESS THAN (1000));
CREATE TABLE n_tg_t2 (id BIGINT NOT NULL, PRIMARY KEY (id))
  TABLEGROUP = n_tg PARTITION BY RANGE(id) (PARTITION p1 VALUES LESS THAN (1000));
-- At this point the group already has two tables; the statement below should error
ALTER TABLE n_tg_t1 PARTITION BY RANGE(id) SIZE('2G');

-- N14 the partition expression must be an officially allowlisted function (CONCAT is not on the allowlist)
SELECT '@@CASE:N14' AS marker;
CREATE TABLE n_bad_expr (
  a VARCHAR(8) NOT NULL, PRIMARY KEY (a)
) PARTITION BY RANGE(CONCAT(a, '1')) (
  PARTITION p1 VALUES LESS THAN ('z')
);

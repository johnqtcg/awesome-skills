-- V2+V3 table-group verification: the three SHARDING states, SCOPE, and the V4.4.2 BP1 fork in NONE semantics.
-- This is the only place in this Skill where the risk conclusion **reverses** by version — it must be measured across versions.
-- Basis: references/tablegroup.md §2.1 / §3

USE obtd_it;

-- ============ SHARDING = PARTITION: partition definitions must be identical ============
CREATE TABLEGROUP tg_user SHARDING = 'PARTITION';

CREATE TABLE tg_users (
  user_id BIGINT NOT NULL, nick VARCHAR(64),
  PRIMARY KEY (user_id)
) TABLEGROUP = tg_user PARTITION BY HASH(user_id) PARTITIONS 16;

CREATE TABLE tg_accounts (
  user_id BIGINT NOT NULL, amt DECIMAL(18,2),
  PRIMARY KEY (user_id)
) TABLEGROUP = tg_user PARTITION BY HASH(user_id) PARTITIONS 16;

-- Control group: same partition key but **not joined to a table group** (used by explain.sql E10 to prove "same partition key != same machine")
CREATE TABLE tg_users_nogroup (
  user_id BIGINT NOT NULL, PRIMARY KEY (user_id)
) PARTITION BY HASH(user_id) PARTITIONS 16;
CREATE TABLE tg_accounts_nogroup (
  user_id BIGINT NOT NULL, amt DECIMAL(18,2), PRIMARY KEY (user_id)
) PARTITION BY HASH(user_id) PARTITIONS 16;

-- ============ SHARDING = ADAPTIVE: all first-level or all second-level ============
CREATE TABLEGROUP tg_ad SHARDING = 'ADAPTIVE';
CREATE TABLE tg_ad_t1 (
  a BIGINT NOT NULL, b INT NOT NULL, PRIMARY KEY (a, b)
) TABLEGROUP = tg_ad PARTITION BY HASH(a)
  SUBPARTITION BY HASH(b) SUBPARTITIONS 4 PARTITIONS 8;
CREATE TABLE tg_ad_t2 (
  a BIGINT NOT NULL, b INT NOT NULL, PRIMARY KEY (a, b)
) TABLEGROUP = tg_ad PARTITION BY HASH(a)
  SUBPARTITION BY HASH(b) SUBPARTITIONS 4 PARTITIONS 8;
-- ============ SHARDING = NONE: semantics fork by version ============
CREATE TABLEGROUP tg_none SHARDING = 'NONE';
CREATE TABLE tg_none_t1 (
  a BIGINT NOT NULL, PRIMARY KEY (a)
) TABLEGROUP = tg_none PARTITION BY HASH(a) PARTITIONS 8;
CREATE TABLE tg_none_t2 (
  b BIGINT NOT NULL, PRIMARY KEY (b)
) TABLEGROUP = tg_none PARTITION BY RANGE(b) (
  PARTITION p1 VALUES LESS THAN (1000),
  PARTITION pmax VALUES LESS THAN MAXVALUE
);
-- The two tables above use different partitioning schemes; NONE performs no validation, so this should succeed.

-- ============ Version-dependent observations ============
-- SCOPE syntax availability, and the Leader distribution for SHARDING=NONE,
-- succeed or fail correctly depending on version, so they have been moved to tablegroup_probe.sql (recorded only, not asserted).

-- ============ Negative examples ============
-- Mismatched partition definitions joining a group, mixed levels in ADAPTIVE, etc., see tablegroup_negative.sql (asserted case-by-case).

-- See the README for cleanup statements; objects are usually kept during regression runs to allow reconciliation.

-- Split out from mysql_mode.sql by "capability-confirmation tier / minimum version."
-- Reason for the split: if the runner ran the same positive-example script against every target version,
--   a lower version lacking the capability would misreport "version not supported" as the entire positive-example suite failing.
-- Basis: references/capability-matrix.md, SKILL.md section 2 "Capability Confirmation Tiers"

-- Applies to: **all versions, but only recorded, not asserted.**
--
-- The minimum supported version for these capabilities has **not yet been confirmed** (capability-matrix.md §5-3), or is a documentation gap
-- (§5 / doc-gaps.md §2), i.e., C2/C3. Until confirmed:
--   * they must not enter the main DDL (hard rule in SKILL.md section 2);
--   * nor can they be asserted as positive examples in integration tests — otherwise an error on a lower version would be misjudged as a suite failure.
-- Once a capability is observed to work on some version, promote it to that version's positive script,
-- and backfill the minimum version into capability-matrix.md.

USE obtd_it;

-- ===== C2: SKIP_INDEX (minimum version not yet confirmed) =====
-- 14) Skip Index: low-cost aggregation acceleration for row-storage tables
CREATE TABLE t_skip (
  id        BIGINT PRIMARY KEY,
  stat_date DATE           SKIP_INDEX(MIN_MAX),
  amt       DECIMAL(18,2)  SKIP_INDEX(MIN_MAX, SUM)
);


-- ===== C2: DYNAMIC_PARTITION_POLICY (minimum version not yet confirmed) =====
-- 19) Dynamic partitioning policy: pre-creation + expiry reclamation
CREATE TABLE t_dynpart (
  id       BIGINT   NOT NULL,
  stat_day DATE     NOT NULL,
  PRIMARY KEY (id, stat_day)
) DYNAMIC_PARTITION_POLICY = (ENABLE = true, TIME_UNIT = 'day',
                              PRECREATE_TIME = '7 day', EXPIRE_TIME = '90 day')
PARTITION BY RANGE COLUMNS(stat_day) (
  PARTITION p1 VALUES LESS THAN ('2026-01-01'),
  PARTITION pmax VALUES LESS THAN (MAXVALUE)
);


-- ===== C3: AUTO_INCREMENT_MODE (not in the official V4.5.0 BNF, a documentation gap) =====
CREATE TABLE p_autoinc_noorder (
  id     BIGINT AUTO_INCREMENT PRIMARY KEY,
  payload VARCHAR(64)
) AUTO_INCREMENT_MODE = 'NOORDER';


-- ===== AUTO_INCREMENT_CACHE_SIZE: the accepted range, and whether caching can be turned off =====
-- Why this is here: doc-gaps.md §2.3.1 tells the Agent to shrink the gap magnitude by
-- LOWERING this integer, and states that the value at which caching becomes a no-op is
-- `unverified`. That claim needs an owner, and this is it — the file doc-gaps.md §2.3.1
-- names as its confirmation path. Do not promote the claim to "confirmed" from reasoning.
--
-- Observation points, recorded not asserted (a lower version may reject any of them):
--   1) does the minimum documented value 1 create successfully?
--   2) with cache size 1, is numbering gapless across a simulated segment boundary, or
--      does a gap still appear? Gapless => "1 disables caching" can move to confirmed.
--   3) is a bare NOCACHE rejected? A syntax error here is the EXPECTED result and is the
--      evidence for the L0 statement in doc-gaps.md §2.3.1 — do not "fix" this statement.
CREATE TABLE p_autoinc_cache_min (
  id      BIGINT AUTO_INCREMENT PRIMARY KEY,
  payload VARCHAR(64)
) AUTO_INCREMENT_MODE = 'NOORDER', AUTO_INCREMENT_CACHE_SIZE = 1;

CREATE TABLE p_autoinc_cache_small (
  id      BIGINT AUTO_INCREMENT PRIMARY KEY,
  payload VARCHAR(64)
) AUTO_INCREMENT_MODE = 'NOORDER', AUTO_INCREMENT_CACHE_SIZE = 10000;

-- Expected to FAIL: NOCACHE is an Oracle CREATE SEQUENCE clause, not a MySQL table option.
-- Recorded here rather than in mysql_negative.sql because the point is to observe the
-- error the server actually returns, so doc-gaps.md §2.3.1 can quote it.
CREATE TABLE p_autoinc_nocache_expected_error (
  id      BIGINT AUTO_INCREMENT PRIMARY KEY,
  payload VARCHAR(64)
) NOCACHE;

-- Observation: record whether each section above succeeds/fails, and backfill
-- capability-matrix.md §5-3 and §4, plus doc-gaps.md §2.3.1 for the cache-size findings.

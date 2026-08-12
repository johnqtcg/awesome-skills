-- V2 negative example: Oracle mode. **Every single case should error.**
-- These cases correspond directly to the "prohibited combinations" in references/capability-matrix.md §1.2.
-- Pass criterion = errors out. If it executes successfully, the capability matrix is wrong and references/ must be fixed.

-- N1  Oracle mode has no COLUMNS keyword (multi-column range partitioning is written directly as RANGE(c1, c2))
SELECT '@@CASE:N1' AS marker;
CREATE TABLE N_RANGE_COLUMNS (
  TENANT_ID VARCHAR2(32) NOT NULL,
  STAT_DATE DATE         NOT NULL,
  CONSTRAINT PK_N_RC PRIMARY KEY (TENANT_ID, STAT_DATE)
) PARTITION BY RANGE COLUMNS(TENANT_ID, STAT_DATE) (
  PARTITION P1 VALUES LESS THAN ('t50', TO_DATE('2026-01-01','YYYY-MM-DD'))
);

-- N2  same as above — LIST COLUMNS does not exist either
SELECT '@@CASE:N2' AS marker;
CREATE TABLE N_LIST_COLUMNS (
  REGION_CODE VARCHAR2(8) NOT NULL,
  CONSTRAINT PK_N_LC PRIMARY KEY (REGION_CODE)
) PARTITION BY LIST COLUMNS(REGION_CODE) (
  PARTITION P1 VALUES ('01')
);

-- N3  Oracle mode has no PARTITION BY KEY
SELECT '@@CASE:N3' AS marker;
CREATE TABLE N_KEY (
  TENANT_ID VARCHAR2(32) NOT NULL,
  USER_ID   NUMBER(20)   NOT NULL,
  CONSTRAINT PK_N_KEY PRIMARY KEY (TENANT_ID, USER_ID)
) PARTITION BY KEY(TENANT_ID, USER_ID) PARTITIONS 16;

-- N4  Oracle mode's table_option has no ORGANIZATION
SELECT '@@CASE:N4' AS marker;
CREATE TABLE N_ORG (
  ID NUMBER(20) PRIMARY KEY
) ORGANIZATION = HEAP;

-- N5  Oracle mode's LIST enumeration does not use VALUES IN
SELECT '@@CASE:N5' AS marker;
CREATE TABLE N_VALUES_IN (
  LOG_VALUE VARCHAR2(8) NOT NULL,
  CONSTRAINT PK_N_VI PRIMARY KEY (LOG_VALUE)
) PARTITION BY LIST(LOG_VALUE) (
  PARTITION P1 VALUES IN ('A')
);

-- N6  INTERVAL accepts only a single column
SELECT '@@CASE:N6' AS marker;
CREATE TABLE N_INTERVAL_MULTI (
  A DATE NOT NULL, B DATE NOT NULL,
  CONSTRAINT PK_N_IM PRIMARY KEY (A, B)
) PARTITION BY RANGE(A, B) INTERVAL (NUMTOYMINTERVAL(1,'MONTH')) (
  PARTITION P1 VALUES LESS THAN (TO_DATE('2026-01-01','YYYY-MM-DD'),
                                 TO_DATE('2026-01-01','YYYY-MM-DD'))
);

-- N7  when there is a primary key, the partition key must be a subset of the primary key
SELECT '@@CASE:N7' AS marker;
CREATE TABLE N_PK_SUBSET (
  ORDER_ID NUMBER(20) NOT NULL,
  USER_ID  NUMBER(20) NOT NULL,
  CONSTRAINT PK_N_PS PRIMARY KEY (ORDER_ID)
) PARTITION BY HASH(USER_ID) PARTITIONS 8;

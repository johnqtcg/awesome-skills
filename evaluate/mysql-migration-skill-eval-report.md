# mysql-migration Skill Evaluation Report

> Framework: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> Evaluation date: 2026-04-14
> Subject: `mysql-migration`

---

`mysql-migration` is a MySQL schema migration safety review and DDL generation skill. It covers online DDL algorithm selection (INSTANT / INPLACE / COPY), lock safety analysis, large-table migration using gh-ost / pt-osc, replication-safe DDL, degradation modes for incomplete context, and the mandatory §9 output contract. This evaluation ran 3 A/B test scenarios and graded 23 assertions to compare response quality with and without the skill.

## 1. Evaluation Overview

This evaluation measures skill performance across three dimensions: **structured output compliance**, **technical accuracy**, and **completeness under degraded context**. 3 scenarios × 2 configurations (with / without skill) = 6 independent runs.

| Dimension | With-Skill | Without-Skill | Gap |
|-----------|:----------:|:-------------:|:---:|
| **Assertion pass rate** | **23/23 (100%)** | 12/23 (52%) | **+48 pp** |
| **Pass + partial pass rate** | **23/23 (100%)** | 20/23 (87%) | +13 pp |
| **Scorecard present (Critical / Standard / Hygiene)** | 3/3 (100%) | 0/3 (0%) | **+100 pp** |
| **Uncovered Risks section present** | 3/3 (100%) | 0/3 (0%) | **+100 pp** |
| **Degradation mode formally declared** | 1/1 (100%) | 0/1 (0%) | **+100 pp** |
| **INSTANT / INPLACE / COPY terminology used correctly** | 3/3 (100%) | 2/3 (67%) | +33 pp |
| **MySQL 5.7 INSTANT limitation correctly stated** | 1/1 (100%) | 0/1 (0%) | **+100 pp** |
| **Average token consumption** | ~33,000 | ~21,800 | +51% |

---

## 2. Scenario 0 — Standard DDL Review

### 2.1 Test Setup

**Input:** MySQL 8.0.32, `orders` table with ~5 million rows, source-replica replication, Flyway-managed schema, no dedicated maintenance window. Review the following migration:

```sql
ALTER TABLE orders
  ADD COLUMN tracking_id VARCHAR(50),
  MODIFY COLUMN amount DECIMAL(12,4) NOT NULL,
  ADD INDEX idx_created_at (created_at);
```

**9 assertions (A1–A9):** context table, missing session guards flagged, INSTANT algorithm for `tracking_id`, COPY algorithm for `amount`, combined ALTER anti-pattern, INPLACE for the index, scorecard, rollback plan, uncovered risks.

### 2.2 Results

| ID | Assertion | Without-Skill | With-Skill |
|----|-----------|:-------------:|:----------:|
| A1 | Complete context collection table | Partial | Pass |
| A2 | Missing session guards explicitly flagged | Partial | Pass |
| A3 | `tracking_id` correctly assigned `ALGORITHM=INSTANT` | Pass | Pass |
| A4 | `amount` MODIFY identified as COPY + UNSAFE | Pass | Pass |
| A5 | Combined ALTER (INSTANT + COPY + INPLACE) flagged as anti-pattern | Pass | Pass |
| A6 | ADD INDEX uses `ALGORITHM=INPLACE, LOCK=NONE` | Pass | Pass |
| A7 | Scorecard with Critical / Standard / Hygiene tiers | Fail | Pass |
| A8 | Rollback plan included | Partial | Pass |
| A9 | Uncovered Risks section included | Fail | Pass |

**Scenario 0:** Without-Skill = 4 pass + 3 partial + 2 fail | With-Skill = **9/9**

### 2.3 Key Observations

**Without-skill:** The output is detailed and technically correct on the core DDL risks — COPY requirement, algorithm downgrade on combined ALTER, INSTANT for ADD COLUMN. But structural scaffolding is absent: no §9.1 context gate table, no scorecard, no Uncovered Risks section, and no explicit flag that the original migration is missing session guards.

**With-skill:** All §9 sections are present. The scorecard rates the original migration `1/12 — Critical 0/3, Standard 0/5, Hygiene 1/4 — FAIL`, giving the reviewer a clear, actionable verdict. The Uncovered Risks section surfaces 11 distinct gaps, including the current nullability of `amount` (a prerequisite for the NOT NULL change) and active QPS.

---

## 3. Scenario 1 — Large-Table Migration

### 3.1 Test Setup

**Input:** MySQL 5.7.40, `events` table with ~80 million rows, source + 2 replicas, 24/7 service (no maintenance window). Generate a safe migration plan for:
1. `user_id` INT → BIGINT
2. Add a nullable `metadata JSON` column

**8 assertions (B1–B8):** COPY algorithm flagged, gh-ost recommended, command with specific flags, dry-run step, MySQL 5.7 INSTANT limitation, throttling strategy, phased rollback, 5-phase plan.

### 3.2 Results

| ID | Assertion | Without-Skill | With-Skill |
|----|-----------|:-------------:|:----------:|
| B1 | INT→BIGINT identified as COPY, flagged UNSAFE | Partial | Pass |
| B2 | Recommends gh-ost or pt-osc | Pass | Pass |
| B3 | Provides a concrete command with `--chunk-size` or `--max-lag-millis` | Pass | Pass |
| B4 | Includes a dry-run step before execution | Partial | Pass |
| B5 | Explicitly states INSTANT is unavailable on MySQL 5.7 | Partial | Pass |
| B6 | Provides replication lag threshold and auto-throttling strategy | Pass | Pass |
| B7 | Provides rollback / abort procedure for each phase | Pass | Pass |
| B8 | Includes a 5-phase execution plan | Pass | Pass |

**Scenario 1:** Without-Skill = 5 pass + 3 partial | With-Skill = **8/8**

### 3.3 Key Observations

**Without-skill (B5 — significant factual error):** The response stated that adding a nullable JSON column in MySQL 5.7 "can be executed as an instant metadata operation in some versions." This is wrong. MySQL 5.7 does not have the INSTANT algorithm at all — it was introduced in 8.0.12. An engineer relying on this response could deploy without gh-ost, expecting an INSTANT path that doesn't exist.

**With-skill:** The response explicitly states "MySQL 5.7 does not support INSTANT (available only in 8.0.12+)" and correctly classifies nullable JSON column addition on 5.7 as INPLACE + NONE. The dry-run step uses the correct `--dry-run` flag rather than `--test-on-replica`, which is a different operation that runs a full migration on a replica.

---

## 4. Scenario 2 — Degraded Context

### 4.1 Test Setup

**Input:** Version unknown (5.7 or 8.0), row count unknown, charset utf8mb4. The user explicitly asks: "Just tell me — are these operations safe?" Migration statements:

```sql
-- VARCHAR(60) → VARCHAR(100), same charset
ALTER TABLE users MODIFY COLUMN display_name VARCHAR(100) CHARACTER SET utf8mb4;

-- Add nullable TEXT column
ALTER TABLE users ADD COLUMN bio TEXT;

-- Charset conversion
ALTER TABLE messages CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

**6 assertions (C1–C6):** degradation mode declared, conservative 5.7 assumption, utf8mb4 byte boundary detection, refuses unconditional "safe" verdict, CONVERT TO CHARSET flagged UNSAFE, uncovered risks include unknown version and row count.

### 4.2 Results

| ID | Assertion | Without-Skill | With-Skill |
|----|-----------|:-------------:|:----------:|
| C1 | Formally declares degradation mode | Partial | Pass |
| C2 | Treats version conservatively as MySQL 5.7 | Partial | Pass |
| C3 | Detects VARCHAR(60→100) utf8mb4 crossing the 255-byte boundary (240 < 255 < 400) | Pass | Pass |
| C4 | Refuses to declare "safe" unconditionally; uses conditional language | Pass | Pass |
| C5 | `CONVERT TO CHARACTER SET` flagged as UNSAFE | Pass | Pass |
| C6 | Uncovered Risks explicitly lists unknown version and unknown row count | Fail | Pass |

**Scenario 2:** Without-Skill = 3 pass + 2 partial + 1 fail | With-Skill = **6/6**

### 4.3 Key Observations

**Most notable finding:** The without-skill baseline independently detected the utf8mb4 255-byte boundary trap (C3) — including the precise calculation: 60×4=240 bytes, 100×4=400 bytes, and the forced COPY conclusion. This is the hardest assertion in the entire evaluation, requiring MySQL-specific knowledge of byte-length storage encoding. The baseline got it right on its own.

**Skill value in degraded mode:** The skill formally names the mode ("DEGRADED MODE ACTIVE"), adopts 5.7 as the conservative baseline per its rules (rather than running parallel analysis for both versions), and captures unknown inputs as structured rows in the §9.9 Uncovered Risks table. Without the skill, unknowns are recorded as action-item bullet points — a format that fails to communicate that these gaps block a complete safety determination.

---

## 5. Comprehensive Results

### 5.1 Assertion Scoring Summary

| Scenario | Without-Skill Pass | Without-Skill Partial | Without-Skill Fail | With-Skill Pass |
|----------|:-----------------:|:--------------------:|:-----------------:|:--------------:|
| Scenario 0 (9 assertions) | 4 | 3 | 2 | **9** |
| Scenario 1 (8 assertions) | 5 | 3 | 0 | **8** |
| Scenario 2 (6 assertions) | 3 | 2 | 1 | **6** |
| **Total (23)** | **12** | **8** | **3** | **23** |

Weighted pass rate (partial = 0.5): **Without-Skill = 70%** → **With-Skill = 100%**

### 5.2 Core Differentiators

| Skill contribution | Evidence from evaluation |
|-------------------|--------------------------|
| **§9 output contract enforcement** | Without-skill never produces a scorecard, Uncovered Risks section, or structured context gate — with-skill always does |
| **Formal degradation protocol** | Skill names the mode, applies 5.7 as the conservative baseline per its rules, and structures gaps as a standalone Uncovered Risks table |
| **COPY / INPLACE / INSTANT terminology** | Skill uses precise DDL algorithm names; without-skill uses colloquial "full table rebuild," losing actionable precision |
| **MySQL 5.7 INSTANT correction** | Without-skill made an incorrect claim about 5.7 INSTANT availability; skill's algorithm matrix explicitly prohibits this |
| **Dry-run vs. test-on-replica distinction** | Skill uses `--dry-run` correctly; without-skill used `--test-on-replica` (a different operation) |
| **Scorecard as an engineering verdict** | Without-skill never summarizes the original migration as pass/fail; skill produces a 12-point scorecard usable as a blocking check |

### 5.3 Areas Where the Baseline Is Already Strong

The without-skill baseline demonstrated solid MySQL knowledge in:
- Detecting the utf8mb4 255-byte boundary trap (scenario 2, hardest assertion in the evaluation)
- Recommending gh-ost over native ALTER for large tables
- Providing a usable gh-ost command template with correct flags
- Correctly applying `ALGORITHM=INPLACE, LOCK=NONE` for ADD INDEX

The skill's value is therefore not "adding MySQL knowledge that doesn't exist in the baseline" — it is providing **consistent output structure, formal degradation handling, and completeness gates (the §9 output contract) that prevent critical sections from being dropped under time pressure or incomplete context**.

---

## 6. Token Cost Analysis

| Scenario | Without-Skill tokens | With-Skill tokens | Overhead |
|----------|:--------------------:|:-----------------:|:--------:|
| Scenario 0 (standard review) | 26,347 | 38,200 | +45% |
| Scenario 1 (large-table) | 19,855 | 32,400 | +63% |
| Scenario 2 (degraded) | 19,354 | 28,600 | +48% |
| **Average** | **21,852** | **33,067** | **+51%** |

The skill loads 3 reference files beyond SKILL.md (`ddl-algorithm-matrix.md`, `large-table-migration.md`, `migration-anti-examples.md`), which accounts for the overhead. For production migrations — where a single missed DDL lock or wrong tool choice can cause hours of downtime — a 51% token overhead is well justified by the quality improvement.

---

## 7. Coverage Gaps and Known Limitations

| Gap | Severity | Notes |
|-----|----------|-------|
| Partition DDL not tested | Medium | Partition operations are in scope (§1) but no evaluation scenario covers them |
| Large table with FK constraints (pt-osc vs. gh-ost selection) | Medium | Reference file covers this, but no evaluation walkthrough of the FK check |
| Flyway-specific ordering and version tracking | Low | Scenario 0 uses a Flyway context; skill handles it but no dedicated assertions |
| MySQL 8.4 (latest LTS) | Low | SKILL.md covers 5.7 and 8.0; 8.4 DDL behavior not evaluated |
| Post-cutover rollback feasibility | Medium | Post-cutover rollback requires a backup — skill flags this, but no dedicated assertion |

---

## 8. Conclusion

`mysql-migration` achieved **100% assertion coverage** across 3 scenarios and 23 assertions. The skill's primary contributions are:

1. **Consistent output structure** — The §9 output contract ensures the scorecard, rollback plan, and Uncovered Risks section are always present regardless of context completeness.
2. **Formal degradation handling** — A named degradation mode paired with conservative 5.7 assumptions prevents overconfident safety verdicts when context is missing.
3. **Terminology precision** — COPY / INPLACE / INSTANT classification removes the ambiguity of "full table rebuild," making algorithm selection an unambiguous engineering decision.
4. **Completeness gates** — The scorecard turns narrative reviews into explicit pass/fail verdicts on the original migration, enabling use as a blocking check.

The without-skill baseline is capable and technically solid, but lacks the structural guardrails that prevent critical sections from being omitted. The skill addresses exactly the failure modes that cause migration-related incidents: missing session guards, unbounded table locks, and absent rollback plans.

**Recommendation: production-ready. Recommended for all MySQL DDL review and migration planning workflows.**

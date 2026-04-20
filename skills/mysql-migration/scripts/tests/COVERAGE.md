# mysql-migration Skill — Test Coverage Matrix

## 1. Contract Tests (`test_skill_contract.py`)

| Test Class | Count | Validates |
|------------|:-----:|-----------|
| `TestFrontmatter` | 2 | name=mysql-migration; trigger keywords (ALTER TABLE, DDL, INSTANT, INPLACE, gh-ost, pt-osc) |
| `TestMandatoryGates` | 6 | Gate 1–4 with STOP/PROCEED; context collection items; scope modes (review/generate/plan); risk levels (SAFE/WARN/UNSAFE) |
| `TestDepthSelection` | 3 | Lite/Standard/Deep triggers; force-Standard signals; reference loading by depth |
| `TestDegradationModes` | 3 | Full/Degraded/Minimal/Planning; never-fabricate rule; assumption documentation |
| `TestDDLSafetyChecklist` | 7 | 4 subsections; ALGORITHM keywords; LOCK keywords; MDL/session guards; backward compatibility; rollback feasibility |
| `TestExecutionPlan` | 2 | 5-phase pattern keywords; large-table-migration.md reference |
| `TestAntiExamples` | 4 | ≥6 AE patterns; WRONG/RIGHT pairs; session guard AE; extended-ref mention |
| `TestScorecard` | 5 | Critical/Standard/Hygiene tiers; pass thresholds (3/3, 4/5, 3/4); critical items; verdict format |
| `TestOutputContract` | 4 | 9 sections (§9.1–§9.9); uncovered risks mandatory; volume rules; scorecard in output |
| `TestReferenceFiles` | 8 | 3 reference files exist with minimum line counts; required keywords in each; AE numbering (AE-7+); all refs mentioned in SKILL.md |
| `TestLineCount` | 1 | SKILL.md ≤ 420 lines |
| `TestCrossFileConsistency` | 6 | INSTANT in matrix; gh-ost/pt-osc in large-table ref; lock_wait_timeout across files; VARCHAR/255 boundary in matrix |
| **Total** | **51** | |

## 2. Golden Fixtures (`test_golden_scenarios.py`)

### 2.1 Fixture Inventory

| ID | Title | Type | Severity | Violated Rule |
|----|-------|------|----------|---------------|
| MIG-001 | Missing session guards | defect | critical | Session guards |
| MIG-002 | Implicit algorithm on large table | defect | critical | Algorithm explicitly specified |
| MIG-003 | NOT NULL without phased approach | defect | critical | Rollback SQL provided |
| MIG-004 | Missing rollback plan (DROP COLUMN) | defect | critical | Rollback SQL provided |
| MIG-005 | INSTANT on MySQL 5.7 | defect | standard | DDL algorithm matches version |
| MIG-006 | LIMIT/OFFSET backfill | defect | standard | Backfill uses PK-range batching |
| MIG-007 | Well-formed phased migration | good_practice | none | — |
| MIG-008 | Good gh-ost invocation | good_practice | none | — |
| MIG-009 | Degraded mode — no context | degradation_scenario | none | — |
| MIG-010 | Multi-step column rename workflow | workflow | none | — |
| MIG-011 | VARCHAR boundary cross (utf8mb4) | defect | standard | DDL algorithm matches version |

### 2.2 Per-Fixture Test Classes

| Fixture | Test Class | Tests | Validates |
|---------|-----------|:-----:|-----------|
| MIG-001 | `TestMIG001` | 3 | type=defect/critical; violated_rule mentions session; feedback mentions lock_wait_timeout |
| MIG-002 | `TestMIG002` | 3 | type=defect/critical; violated_rule mentions algorithm; feedback mentions INSTANT |
| MIG-003 | `TestMIG003` | 2 | type=defect/critical; feedback mentions phased approach |
| MIG-004 | `TestMIG004` | 3 | type=defect/critical; violated_rule mentions rollback; feedback mentions irreversible |
| MIG-005 | `TestMIG005` | 3 | type=defect/standard; feedback mentions 5.7; feedback suggests INPLACE |
| MIG-006 | `TestMIG006` | 2 | type=defect/standard; feedback mentions PK-range |
| MIG-007 | `TestMIG007` | 2 | type=good_practice/none; feedback confirms no violations |
| MIG-008 | `TestMIG008` | 3 | type=good_practice/none; feedback confirms no violations; mentions gh-ost |
| MIG-009 | `TestMIG009` | 3 | type=degradation_scenario/none; forbids claims; mentions degraded |
| MIG-010 | `TestMIG010` | 3 | type=workflow/none; mentions phases; mentions dual-write |
| MIG-011 | `TestMIG011` | 3 | type=defect/standard; mentions 255/boundary; mentions utf8mb4 |

### 2.3 Fixture Integrity Tests

| Test | Validates |
|------|-----------|
| `test_minimum_fixture_count` | ≥9 fixtures present |
| `test_required_fields` | All fixtures have required schema fields |
| `test_valid_types` | Types ∈ {defect, good_practice, degradation_scenario, workflow} |
| `test_valid_severities` | Severities ∈ {critical, standard, hygiene, none} |
| `test_defect_severity_not_none` | Defects have non-none severity |
| `test_non_defect_severity_none` | Non-defects have severity=none |
| `test_unique_ids` | No duplicate IDs |
| `test_coverage_rules_findable` | Every coverage_rule phrase exists in combined docs |

**Golden test total: 8 integrity + 30 behavioral = 38 tests**

## 3. Coverage Summary

| Category | Covered | Total | Status |
|----------|:-------:|:-----:|--------|
| Mandatory Gates | 4/4 | 4 | ✅ 100% |
| Depth Levels | 3/3 | 3 | ✅ 100% |
| Degradation Modes | 4/4 | 4 | ✅ 100% |
| DDL Checklist Subsections | 4/4 | 4 | ✅ 100% |
| Scorecard Tiers | 3/3 | 3 | ✅ 100% |
| Output Contract Sections | 9/9 | 9 | ✅ 100% |
| Anti-Example Patterns (inline) | 6/6 | 6 | ✅ 100% |
| Anti-Example Patterns (extended) | 7/7 | 7 | ✅ 100% |
| Reference Files | 3/3 | 3 | ✅ 100% |
| Cross-File Terminology | 6/6 | 6 | ✅ 100% |
| SKILL.md Line Budget | 331/420 | — | ✅ under budget |
| Critical Defect Fixtures | 4/4 | 4 | ✅ 100% |
| Standard Defect Fixtures | 3/3 | 3 | ✅ 100% |
| Good Practice Fixtures | 2/2 | 2 | ✅ 100% |
| Degradation/Workflow Fixtures | 2/2 | 2 | ✅ 100% |

**Grand Total: 89 tests** (51 contract + 38 golden)

## 4. Known Coverage Gaps

| Gap | Priority | Rationale |
|-----|----------|-----------|
| Partition DDL fixture (REORGANIZE PARTITION) | Low | Uncommon operation; basic coverage in ddl-algorithm-matrix.md |
| Oracle-style CTAS migration anti-pattern | Low | Out of scope for MySQL skill |
| Multi-database migration coordination | Medium | Real-world pattern but rare; would add complexity |
| Flyway/Liquibase framework-specific fixture | Medium | Framework detection mentioned in Gate 1 but no fixture exercises it |
| Character set conversion fixture (utf8→utf8mb4 full table) | Medium | Partially covered by MIG-011 (VARCHAR boundary); full-table CONVERT not exercised |
| Concurrent migration conflict detection | Low | Rare scenario; not a primary checklist concern |
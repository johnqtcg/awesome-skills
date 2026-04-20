# oracle-migration Skill — Test Coverage Matrix

## 1. Contract Tests (`test_skill_contract.py`)

| Test Class | Count | Validates |
|------------|:-----:|-----------|
| `TestFrontmatter` | 2 | name=oracle-migration; trigger keywords (ALTER TABLE, DDL, DBMS_REDEFINITION, NOVALIDATE, DDL_LOCK_TIMEOUT, auto-commit) |
| `TestMandatoryGates` | 6 | Gate 1–4 with STOP/PROCEED; context items (version, edition, RAC); scope modes; risk levels |
| `TestDepthSelection` | 3 | Lite/Standard/Deep triggers; force-Standard signals; reference loading |
| `TestDegradationModes` | 3 | Full/Degraded/Minimal/Planning; never-claim; assumptions |
| `TestDDLSafetyChecklist` | 7 | 4 subsections; DDL auto-commit; DDL_LOCK_TIMEOUT; NOVALIDATE; ONLINE; backward compat; manual rollback |
| `TestExecutionPlan` | 2 | 5-phase pattern; large-table reference |
| `TestAntiExamples` | 4 | ≥6 AE patterns; WRONG/RIGHT pairs; ORA-00054 AE; extended-ref |
| `TestScorecard` | 5 | Critical/Standard/Hygiene tiers; pass thresholds; critical items; verdict format |
| `TestOutputContract` | 4 | 9 sections (§9.1–§9.9); uncovered risks mandatory; volume rules; scorecard in output |
| `TestReferenceFiles` | 8 | 3 reference files with minimum lines; required keywords; AE numbering; all refs in SKILL.md |
| `TestLineCount` | 1 | SKILL.md ≤ 420 lines |
| `TestCrossFileConsistency` | 6 | Exclusive in matrix; DBMS_REDEFINITION in large-table; CTAS in large-table; DDL_LOCK_TIMEOUT; NOVALIDATE in matrix; DBMS_STATS in anti-examples |
| **Total** | **51** | |

## 2. Golden Fixtures (`test_golden_scenarios.py`)

### 2.1 Fixture Inventory

| ID | Title | Type | Severity | Violated Rule |
|----|-------|------|----------|---------------|
| ORA-001 | Missing DDL_LOCK_TIMEOUT | defect | critical | DDL_LOCK_TIMEOUT set |
| ORA-002 | Constraint without NOVALIDATE | defect | critical | Constraints use ENABLE NOVALIDATE + VALIDATE two-step |
| ORA-003 | Missing rollback (DDL auto-commits) | defect | critical | Rollback SQL provided |
| ORA-004 | ALTER TABLE MOVE without ONLINE | defect | critical | Large table restructuring uses DBMS_REDEFINITION or CTAS |
| ORA-005 | Partition DDL without UPDATE INDEXES | defect | standard | Global index impact assessed |
| ORA-006 | Monolithic UPDATE on large table | defect | standard | Batch operations use ROWID/PK-range |
| ORA-007 | Well-formed phased migration | good_practice | none | — |
| ORA-008 | Good DBMS_REDEFINITION | good_practice | none | — |
| ORA-009 | Degraded — no context | degradation_scenario | none | — |
| ORA-010 | Multi-step column type change | workflow | none | — |
| ORA-011 | Column type change without DBMS_REDEF | defect | standard | Large table restructuring uses DBMS_REDEFINITION or CTAS |

### 2.2 Per-Fixture Test Classes

| Fixture | Test Class | Tests | Validates |
|---------|-----------|:-----:|-----------|
| ORA-001 | `TestORA001` | 3 | type=defect/critical; violated_rule mentions DDL_LOCK_TIMEOUT; feedback mentions ORA-00054 |
| ORA-002 | `TestORA002` | 4 | type=defect/critical; violated_rule mentions NOVALIDATE/constraint; feedback mentions NOVALIDATE; feedback mentions two-step/VALIDATE |
| ORA-003 | `TestORA003` | 3 | type=defect/critical; violated_rule mentions rollback; feedback mentions auto-commit |
| ORA-004 | `TestORA004` | 4 | type=defect/critical; violated_rule mentions DBMS_REDEFINITION/CTAS/restructuring; feedback mentions ONLINE; feedback mentions UNUSABLE |
| ORA-005 | `TestORA005` | 3 | type=defect/standard; feedback mentions UPDATE INDEXES; feedback mentions UNUSABLE |
| ORA-006 | `TestORA006` | 2 | type=defect/standard; feedback mentions batch/ROWID |
| ORA-007 | `TestORA007` | 2 | type=good_practice/none; feedback confirms no violations |
| ORA-008 | `TestORA008` | 3 | type=good_practice/none; feedback no violations; mentions DBMS_REDEFINITION |
| ORA-009 | `TestORA009` | 3 | type=degradation_scenario/none; forbids claims; mentions degraded |
| ORA-010 | `TestORA010` | 3 | type=workflow/none; mentions DBMS_REDEFINITION; mentions phases/steps |
| ORA-011 | `TestORA011` | 3 | type=defect/standard; mentions DBMS_REDEFINITION; mentions rewrite |

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

**Golden total: 8 integrity + 33 behavioral = 41 tests**

## 3. Coverage Summary

| Category | Covered | Total | Status |
|----------|:-------:|:-----:|--------|
| Mandatory Gates | 4/4 | 4 | 100% |
| Depth Levels | 3/3 | 3 | 100% |
| Degradation Modes | 4/4 | 4 | 100% |
| DDL Checklist Subsections | 4/4 | 4 | 100% |
| Scorecard Tiers | 3/3 | 3 | 100% |
| Output Contract Sections | 9/9 | 9 | 100% |
| Anti-Examples (inline) | 6/6 | 6 | 100% |
| Anti-Examples (extended) | 7/7 | 7 | 100% |
| Reference Files | 3/3 | 3 | 100% |
| Cross-File Terminology | 6/6 | 6 | 100% |
| SKILL.md Line Budget | 352/420 | — | under budget |
| Critical Defect Fixtures | 4/4 | 4 | 100% |
| Standard Defect Fixtures | 3/3 | 3 | 100% |
| Good Practice Fixtures | 2/2 | 2 | 100% |
| Degradation/Workflow Fixtures | 2/2 | 2 | 100% |

**Grand Total: 92 tests** (51 contract + 41 golden)

## 4. Known Coverage Gaps

| Gap | Priority | Rationale |
|-----|----------|-----------|
| Edition-Based Redefinition (EBR) fixture | Medium | Advanced feature for continuous deployment; not in source skill |
| Invisible column/index fixture | Low | 12c+ feature; useful but not critical path |
| RAC-specific migration coordination fixture | Medium | RAC adds cross-instance lock coordination complexity |
| Flashback recovery fixture after DDL mistake | Low | Safety net, not primary workflow |
| Tablespace quota/UNDO exhaustion scenario | Medium | Covered in anti-examples but no dedicated fixture |
| Data Guard / standby impact of DDL | Low | Specialized scenario |

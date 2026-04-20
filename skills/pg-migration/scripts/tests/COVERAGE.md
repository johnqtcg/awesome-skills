# pg-migration Skill — Test Coverage Matrix

## 1. Contract Tests (`test_skill_contract.py`)

| Test Class | Count | Validates |
|------------|:-----:|-----------|
| `TestFrontmatter` | 2 | name=pg-migration; trigger keywords (ALTER TABLE, DDL, CONCURRENTLY, NOT VALID, pg_repack, AccessExclusiveLock) |
| `TestMandatoryGates` | 6 | Gate 1–4 with STOP/PROCEED; context items; scope modes; risk levels |
| `TestDepthSelection` | 3 | Lite/Standard/Deep triggers; force-Standard signals; reference loading |
| `TestDegradationModes` | 3 | Full/Degraded/Minimal/Planning; never-fabricate; assumptions |
| `TestDDLSafetyChecklist` | 7 | 4 subsections; lock levels (AccessExclusive/Share/ShareUpdateExclusive); CONCURRENTLY; NOT VALID; lock_timeout; backward compat; rollback |
| `TestExecutionPlan` | 2 | 5-phase pattern; large-table reference |
| `TestAntiExamples` | 4 | ≥6 AE patterns; WRONG/RIGHT pairs; CONCURRENTLY AE; extended-ref |
| `TestScorecard` | 5 | Critical/Standard/Hygiene tiers; pass thresholds; critical items; verdict format |
| `TestOutputContract` | 4 | 9 sections (§9.1–§9.9); uncovered risks mandatory; volume rules; scorecard in output |
| `TestReferenceFiles` | 8 | 3 reference files with minimum lines; required keywords; AE numbering; all refs in SKILL.md |
| `TestLineCount` | 1 | SKILL.md ≤ 420 lines |
| `TestCrossFileConsistency` | 6 | AccessExclusiveLock in matrix; CONCURRENTLY in matrix; pg_repack in large-table; lock_timeout; NOT VALID in matrix; DO blocks in anti-examples |
| **Total** | **51** | |

## 2. Golden Fixtures (`test_golden_scenarios.py`)

### 2.1 Fixture Inventory

| ID | Title | Type | Severity | Violated Rule |
|----|-------|------|----------|---------------|
| PG-001 | Missing lock_timeout | defect | critical | lock_timeout set |
| PG-002 | Index without CONCURRENTLY | defect | critical | Indexes use CONCURRENTLY |
| PG-003 | Constraint without NOT VALID | defect | critical | Rollback path provided |
| PG-004 | Missing rollback (DROP COLUMN) | defect | critical | Rollback path provided |
| PG-005 | ALTER COLUMN TYPE on large table | defect | standard | lock_timeout set |
| PG-006 | ADD CONSTRAINT IF NOT EXISTS syntax | defect | standard | Idempotent DO blocks |
| PG-007 | Well-formed phased migration | good_practice | none | — |
| PG-008 | Good CONCURRENTLY index build | good_practice | none | — |
| PG-009 | Degraded — no context | degradation_scenario | none | — |
| PG-010 | Multi-step column rename | workflow | none | — |
| PG-011 | NOT NULL without CHECK shortcut | defect | standard | NOT VALID pattern |

### 2.2 Per-Fixture Test Classes

| Fixture | Test Class | Tests | Validates |
|---------|-----------|:-----:|-----------|
| PG-001 | `TestPG001` | 3 | type/severity; violated_rule; feedback mentions lock_timeout |
| PG-002 | `TestPG002` | 3 | type/severity; violated_rule; feedback mentions CONCURRENTLY |
| PG-003 | `TestPG003` | 3 | type/severity; feedback mentions NOT VALID; mentions two-step |
| PG-004 | `TestPG004` | 3 | type/severity; violated_rule; feedback mentions irreversible |
| PG-005 | `TestPG005` | 3 | type/severity; feedback mentions rewrite; mentions pg_repack |
| PG-006 | `TestPG006` | 3 | type/severity; feedback mentions syntax error; suggests DO block |
| PG-007 | `TestPG007` | 2 | type/severity; feedback confirms no violations |
| PG-008 | `TestPG008` | 3 | type/severity; feedback no violations; mentions CONCURRENTLY |
| PG-009 | `TestPG009` | 3 | type/severity; forbids claims; mentions degraded |
| PG-010 | `TestPG010` | 3 | type/severity; mentions phases; mentions backfill |
| PG-011 | `TestPG011` | 3 | type/severity; mentions CHECK; mentions NOT VALID |

### 2.3 Integrity Tests: 8 tests

**Golden total: 8 integrity + 32 behavioral = 40 tests**

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
| SKILL.md Line Budget | — | 420 | under budget |
| Critical Defect Fixtures | 4/4 | 4 | 100% |
| Standard Defect Fixtures | 3/3 | 3 | 100% |
| Good Practice Fixtures | 2/2 | 2 | 100% |
| Degradation/Workflow Fixtures | 2/2 | 2 | 100% |

**Grand Total: 91 tests** (51 contract + 40 golden)

## 4. Known Coverage Gaps

| Gap | Priority | Rationale |
|-----|----------|-----------|
| RLS policy migration fixture | Medium | RLS mentioned in force-Standard signals but no dedicated fixture |
| Extension upgrade fixture (CREATE/ALTER EXTENSION) | Low | Uncommon; basic mention in Gate 1 |
| Partition conversion fixture (non-partitioned → partitioned) | Medium | Covered in reference but no fixture exercises it |
| Logical replication DDL impact fixture | Low | Streaming assumed; logical replication has different DDL behavior |
| PG <11 ADD COLUMN with DEFAULT (table rewrite) | Medium | Version-gated; no fixture exercises the pre-11 rewrite path |
| Multi-tenant RLS + migration interaction | Low | Specialized scenario |
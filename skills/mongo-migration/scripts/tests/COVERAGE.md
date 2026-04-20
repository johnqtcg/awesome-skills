# mongo-migration Skill — Test Coverage Matrix

## 1. Contract Tests (`test_skill_contract.py`)

| Test Class | Count | Validates |
|------------|:-----:|-----------|
| `TestFrontmatter` | 2 | name=mongo-migration; trigger keywords (index, schema, bulk, shard key, collMod, write concern, _id-range) |
| `TestMandatoryGates` | 6 | Gate 1–4 with STOP/PROCEED; context (version, deployment); risk levels |
| `TestDepthSelection` | 3 | Lite/Standard/Deep; force-Standard signals; reference loading |
| `TestDegradationModes` | 3 | Full/Degraded/Minimal/Planning; never-fabricate (fixed operator precedence); assumptions |
| `TestChecklist` | 7 | 4 subsections; index/rolling build; write concern; validator moderate→strict; _id-range; backward compat; rollback irreversible |
| `TestExecutionPlan` | 2 | 5-phase pattern; large-collection ref |
| `TestAntiExamples` | 4 | ≥6 AE; WRONG/RIGHT pairs; unbounded updateMany; extended ref |
| `TestScorecard` | 5 | Critical/Standard/Hygiene; thresholds; verdict |
| `TestOutputContract` | 4 | 9 sections; uncovered risks; volume; scorecard in output |
| `TestReferenceFiles` | 7 | 3 files with min lines; keywords; AE numbering; all refs in SKILL.md |
| `TestLineCount` | 1 | SKILL.md ≤ 420 lines |
| `TestCrossFileConsistency` | 6 | WiredTiger in matrix; reshardCollection in large-collection; _id-range; write concern; validator in AE; replication lag |
| **Total** | **50** | |

## 2. Golden Fixtures (`test_golden_scenarios.py`)

### 2.1 Fixture Inventory

| ID | Title | Type | Severity | Violated Rule |
|----|-------|------|----------|---------------|
| MONGO-001 | Unbounded updateMany | defect | critical | _id-range batching |
| MONGO-002 | No explicit write concern | defect | critical | Write concern set |
| MONGO-003 | No rollback — in-place type overwrite | defect | critical | Rollback path documented |
| MONGO-004 | Validator strict before backfill | defect | standard | Validator moderate→strict |
| MONGO-005 | Unique index without dupe check | defect | standard | Unique index preceded by duplicate check |
| MONGO-006 | In-place field type change | defect | standard | New-field + dual-read pattern |
| MONGO-007 | Well-formed phased migration | good_practice | none | — |
| MONGO-008 | Good rolling index build | good_practice | none | — |
| MONGO-009 | Degraded — no context | degradation_scenario | none | — |
| MONGO-010 | Field type migration workflow | workflow | none | — |
| MONGO-011 | Index build without lag monitoring | defect | standard | Index builds monitored |
| MONGO-012 | reshardCollection workflow | workflow | none | — |
| MONGO-013 | Sharded bulk write without batching | defect | standard | _id-range batching |

### 2.2 Per-Fixture Test Classes

| Fixture | Test Class | Tests | Validates |
|---------|-----------|:-----:|-----------|
| MONGO-001 | `TestMONGO001` | 3 | type/severity; violated_rule (batch/_id); feedback mentions WiredTiger |
| MONGO-002 | `TestMONGO002` | 3 | type/severity; violated_rule (write concern); feedback mentions majority |
| MONGO-003 | `TestMONGO003` | 3 | type/severity; violated_rule (rollback); feedback mentions irreversible |
| MONGO-004 | `TestMONGO004` | 3 | type/severity; violated_rule (validator/moderate); feedback mentions moderate |
| MONGO-005 | `TestMONGO005` | 3 | type/severity; violated_rule (unique/duplicate); feedback mentions duplicate |
| MONGO-006 | `TestMONGO006` | 3 | type/severity; violated_rule (type/dual); feedback mentions dual/new-field |
| MONGO-007 | `TestMONGO007` | 2 | type/severity; no violations |
| MONGO-008 | `TestMONGO008` | 3 | type/severity; no violations; mentions rolling |
| MONGO-009 | `TestMONGO009` | 3 | type/severity; forbids claims; mentions degraded |
| MONGO-010 | `TestMONGO010` | 3 | type/severity; mentions new-field/amount_v2; mentions phases/(1) |
| MONGO-011 | `TestMONGO011` | 3 | type/severity; violated_rule (index/replication/monitor); feedback mentions lag |
| MONGO-012 | `TestMONGO012` | 3 | type/severity; mentions reshard; mentions cutover/lock |
| MONGO-013 | `TestMONGO013` | 4 | type/severity; violated_rule (batch/_id); mentions shard; mentions balancer |

### 2.3 Fixture Integrity Tests: 8 tests

**Golden total: 8 integrity + 39 behavioral = 47 tests**

## 3. Coverage Summary

| Category | Covered | Total | Status |
|----------|:-------:|:-----:|--------|
| Mandatory Gates | 4/4 | 4 | 100% |
| Depth Levels | 3/3 | 3 | 100% |
| Degradation Modes | 4/4 | 4 | 100% |
| Checklist Subsections | 4/4 | 4 | 100% |
| Scorecard Tiers | 3/3 | 3 | 100% |
| Output Contract Sections | 9/9 | 9 | 100% |
| Anti-Examples (inline) | 6/6 | 6 | 100% |
| Anti-Examples (extended) | 7/7 | 7 | 100% |
| Reference Files | 3/3 | 3 | 100% |
| Cross-File Terminology | 6/6 | 6 | 100% |
| SKILL.md Line Budget | 321/420 | — | under budget |
| Critical Defect Fixtures | 3/3 | 3 | 100% |
| Standard Defect Fixtures | 5/5 | 5 | 100% |
| Good Practice Fixtures | 2/2 | 2 | 100% |
| Degradation/Workflow | 3/3 | 3 | 100% |
| **Previously Medium gaps** | | | |
| reshardCollection fixture | ✅ | — | MONGO-012 covers end-to-end |
| Sharded chunk migration fixture | ✅ | — | MONGO-013 covers bulk write + balancer |

**Grand Total: 97 tests** (50 contract + 47 golden)

## 4. Known Coverage Gaps

| Gap | Priority | Rationale |
|-----|----------|-----------|
| TTL index modification fixture | Low | Requires drop + recreate; minor coverage gap |
| Multi-tenant field migration fixture | Low | Tenant prefix mentioned in source skill but not exercised |
| Cross-database renameCollection fixture | Low | Rare operation; mentioned in DDL matrix |
| compact operation fixture | Low | Dangerous but rare; mentioned in DDL matrix |
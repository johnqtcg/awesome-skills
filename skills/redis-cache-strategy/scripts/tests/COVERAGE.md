# redis-cache-strategy Skill — Test Coverage Matrix

## 1. Contract Tests (`test_skill_contract.py`)

| Test Class | Count | Validates |
|------------|:-----:|-----------|
| `TestFrontmatter` | 2 | name=redis-cache-strategy; trigger keywords (cache-aside, write-through, TTL, stampede, penetration, avalanche, hot key, consistency) |
| `TestMandatoryGates` | 6 | Gate 1–4 with STOP/PROCEED; context items (Redis version, maxmemory, eviction); scope modes (review/design/troubleshoot); risk levels |
| `TestDepthSelection` | 3 | Lite/Standard/Deep triggers; force-Standard signals (write-behind, distributed lock, hot key); reference loading |
| `TestDegradationModes` | 3 | Full/Degraded/Minimal/Planning; never-claim; consistency SLA warning |
| `TestCacheStrategyChecklist` | 7 | 4 subsections; pattern keywords; TTL+jitter; stampede+singleflight; penetration+bloom; distributed lock; degradation |
| `TestPatternSelection` | 2 | Pattern selection table; warmup strategy |
| `TestAntiExamples` | 4 | ≥6 AE patterns; WRONG/RIGHT pairs; TTL AE; extended-ref |
| `TestScorecard` | 5 | Critical/Standard/Hygiene tiers; pass thresholds; critical items (consistency, TTL, degradation); verdict format |
| `TestOutputContract` | 4 | 9 sections (§9.1–§9.9); uncovered risks mandatory; volume rules; scorecard in output |
| `TestReferenceFiles` | 7 | 3 reference files with minimum lines; required keywords per file; AE numbering; all refs in SKILL.md |
| `TestLineCount` | 1 | SKILL.md ≤ 420 lines |
| `TestCrossFileConsistency` | 6 | cache-aside in patterns; singleflight in failure modes; bloom in failure modes; TTL jitter in failure modes; KEYS in anti-examples; degradation in SKILL.md |
| **Total** | **50** | |

## 2. Golden Fixtures (`test_golden_scenarios.py`)

### 2.1 Fixture Inventory

| ID | Title | Type | Severity | Violated Rule |
|----|-------|------|----------|---------------|
| CACHE-001 | No consistency strategy | defect | critical | Cache-DB consistency strategy defined |
| CACHE-002 | No TTL on hot data | defect | critical | TTL set with jitter |
| CACHE-003 | No cache-down degradation | defect | critical | Cache-down degradation path exists |
| CACHE-004 | No stampede protection | defect | standard | Stampede protection for hot keys |
| CACHE-005 | Lock without TTL/safe release | defect | standard | Distributed locks have TTL and CAS |
| CACHE-006 | KEYS command for invalidation | defect | standard | Invalidation strategy defined |
| CACHE-007 | Well-formed cache-aside | good_practice | none | — |
| CACHE-008 | Good write-through + degradation | good_practice | none | — |
| CACHE-009 | Degraded — no config/context | degradation_scenario | none | — |
| CACHE-010 | Greenfield cache design workflow | workflow | none | — |
| CACHE-011 | Cache penetration | defect | standard | Penetration protection |
| CACHE-012 | Write-behind for financial data | defect | critical | Cache pattern identified and justified |
| CACHE-013 | No L1 cache — avalanche gap | defect | standard | Avalanche protection |
| CACHE-014 | Cross-tenant cache key leak | defect | critical | Key naming follows namespace convention |

### 2.2 Per-Fixture Test Classes

| Fixture | Test Class | Tests | Validates |
|---------|-----------|:-----:|-----------|
| CACHE-001 | `TestCACHE001` | 3 | type/severity; violated_rule mentions consistency; feedback mentions source of truth |
| CACHE-002 | `TestCACHE002` | 3 | type/severity; violated_rule mentions TTL; feedback mentions jitter |
| CACHE-003 | `TestCACHE003` | 3 | type/severity; violated_rule mentions degradation; feedback mentions fallback to DB |
| CACHE-004 | `TestCACHE004` | 3 | type/severity; violated_rule mentions stampede; feedback mentions singleflight |
| CACHE-005 | `TestCACHE005` | 3 | type/severity; violated_rule mentions lock/TTL; feedback mentions deadlock |
| CACHE-006 | `TestCACHE006` | 3 | type/severity; violated_rule mentions invalidation; feedback mentions KEYS blocking |
| CACHE-007 | `TestCACHE007` | 3 | type/severity; no violations; mentions singleflight |
| CACHE-008 | `TestCACHE008` | 3 | type/severity; no violations; mentions write-through |
| CACHE-009 | `TestCACHE009` | 3 | type/severity; forbids claims; mentions degraded |
| CACHE-010 | `TestCACHE010` | 3 | type/severity; mentions cache-aside pattern; mentions warmup |
| CACHE-011 | `TestCACHE011` | 3 | type/severity; violated_rule mentions penetration; feedback mentions null caching |
| CACHE-012 | `TestCACHE012` | 3 | type/severity; violated_rule mentions pattern; feedback mentions write-behind + financial/data loss |
| CACHE-013 | `TestCACHE013` | 3 | type/severity; violated_rule mentions avalanche; feedback mentions L1/in-process cache |
| CACHE-014 | `TestCACHE014` | 3 | type/severity; violated_rule mentions key naming/namespace; feedback mentions tenant + segmentation/prefix |

### 2.3 Fixture Integrity Tests: 8 tests

**Golden total: 8 integrity + 42 behavioral = 50 tests**

## 3. Coverage Summary

| Category | Covered | Total | Status |
|----------|:-------:|:-----:|--------|
| Mandatory Gates | 4/4 | 4 | 100% |
| Depth Levels | 3/3 | 3 | 100% |
| Degradation Modes | 4/4 | 4 | 100% |
| Checklist Subsections | 4/4 | 4 | 100% |
| Scorecard Tiers | 3/3 | 3 | 100% |
| Output Contract Sections | 9/9 | 9 | 100% |
| Cache Patterns | 4/4 | 4 | 100% (cache-aside, write-through, write-behind, dual-write debounce) |
| Failure Modes | 4/4 | 4 | 100% (stampede, penetration, avalanche, hot key) |
| Anti-Examples (inline) | 6/6 | 6 | 100% |
| Anti-Examples (extended) | 7/7 | 7 | 100% |
| Reference Files | 3/3 | 3 | 100% |
| Cross-File Terminology | 6/6 | 6 | 100% |
| SKILL.md Line Budget | — | 420 | under budget |
| Critical Defect Fixtures | 5/5 | 5 | 100% |
| Standard Defect Fixtures | 5/5 | 5 | 100% |
| Good Practice Fixtures | 2/2 | 2 | 100% |
| Degradation/Workflow | 2/2 | 2 | 100% |

**Grand Total: 100 tests** (50 contract + 50 golden)

## 4. Known Coverage Gaps

| Gap | Priority | Rationale |
|-----|----------|-----------|
| Redlock pattern fixture | Low | Distributed lock covered; Redlock specifically is an advanced variant |
| Cache warmup defect fixture | Low | Warmup mentioned in scorecard/pattern selection but no defect fixture |
| Event-driven invalidation (CDC) fixture | Low | Advanced pattern not in primary checklist |
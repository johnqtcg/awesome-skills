# api-design Skill — Test Coverage Matrix

## 1. Contract Tests (`test_skill_contract.py`)

| Test Class | Count | Validates |
|------------|:-----:|-----------|
| `TestFrontmatter` | 2 | name; trigger keywords (REST, endpoint, status code, error model, idempotency, pagination, IDOR, OpenAPI) |
| `TestMandatoryGates` | 6 | Gate 1–4 with STOP/PROCEED; consumer context; scope modes (review/design/governance); risk levels |
| `TestDepthSelection` | 3 | Lite/Standard/Deep; force-Standard signals; reference loading |
| `TestDegradationModes` | 3 | Full/Degraded/Minimal/Planning; never-guess; assumptions |
| `TestDesignChecklist` | 7 | 4 subsections; resource naming; status codes; error model; Idempotency-Key; IDOR; pagination |
| `TestAntiExamples` | 4 | ≥6 AE; WRONG/RIGHT pairs; verb-in-URL AE; extended ref |
| `TestScorecard` | 5 | Critical/Standard/Hygiene; thresholds; critical items (naming, error model, IDOR); verdict |
| `TestOutputContract` | 4 | 9 sections (§8.1–§8.9); uncovered risks; volume; scorecard |
| `TestReferenceFiles` | 7 | 3 files with min lines; keywords; AE numbering; all refs in SKILL.md |
| `TestLineCount` | 1 | SKILL.md ≤ 420 lines |
| `TestCrossFileConsistency` | 6 | validation_error in error-model; breaking in compatibility; Sunset; IDOR; ETag; 403/404 in AE |
| **Total** | **48** | |

## 2. Golden Fixtures (`test_golden_scenarios.py`)

### 2.1 Fixture Inventory

| ID | Title | Type | Severity | Violated Rule |
|----|-------|------|----------|---------------|
| API-001 | Verb in URL | defect | critical | Resource naming |
| API-002 | 200 for errors | defect | critical | Error model consistency |
| API-003 | No error code structure | defect | critical | Error model machine-parseable |
| API-004 | POST without Idempotency-Key | defect | standard | Idempotency for mutations |
| API-005 | IDOR vulnerability | defect | standard | Object-level authorization |
| API-006 | Breaking change without version | defect | standard | Backward compatibility |
| API-007 | Well-formed CRUD API | good_practice | none | — |
| API-008 | Good pagination + filtering | good_practice | none | — |
| API-009 | Degraded — no consumer context | degradation_scenario | none | — |
| API-010 | Greenfield API design workflow | workflow | none | — |
| API-011 | No rate limiting | defect | standard | Rate limiting defined |

### 2.2 Per-Fixture Test Classes

| Fixture | Test Class | Tests | Validates |
|---------|-----------|:-----:|-----------|
| API-001 | `TestAPI001` | 3 | type/severity; violated_rule (naming); feedback mentions noun/verb |
| API-002 | `TestAPI002` | 3 | type/severity; violated_rule (error); feedback mentions status code |
| API-003 | `TestAPI003` | 3 | type/severity; violated_rule (error); feedback mentions code + machine |
| API-004 | `TestAPI004` | 3 | type/severity; violated_rule (idempotency); feedback mentions retry |
| API-005 | `TestAPI005` | 3 | type/severity=**critical** (IDOR is Critical-tier per Scorecard); violated_rule; feedback mentions IDOR |
| API-006 | `TestAPI006` | 3 | type/severity; violated_rule (compatibility); feedback mentions deprecation |
| API-007 | `TestAPI007` | 3 | type/severity; no violations; mentions ETag/idempotency/concurrency |
| API-008 | `TestAPI008` | 3 | type/severity; no violations; mentions cursor |
| API-009 | `TestAPI009` | 3 | type/severity; forbids claims; mentions degraded |
| API-010 | `TestAPI010` | 3 | type/severity; mentions /orders; mentions idempotency |
| API-011 | `TestAPI011` | 3 | type/severity; violated_rule (rate); feedback mentions 429 |

### 2.3 Fixture Integrity Tests: 8 tests

**Golden total: 8 integrity + 33 behavioral = 41 tests**

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
| SKILL.md Line Budget | — | 420 | under budget |
| Critical Defect Fixtures | 4/4 | 4 | 100% (API-001,002,003,005) |
| Standard Defect Fixtures | 3/3 | 3 | 100% (API-004,006,011) |
| Good Practice Fixtures | 2/2 | 2 | 100% |
| Degradation/Workflow | 2/2 | 2 | 100% |

**Grand Total: 97 tests** (56 contract + 41 golden)

## 4. Known Coverage Gaps

| Gap | Priority | Rationale |
|-----|----------|-----------|
| Long-running operation (202 Accepted) fixture | Medium | Pattern documented in SKILL.md but no fixture exercises async flow |
| OpenAPI spec validation fixture | Medium | Referenced in checklist + contract testing but no fixture exercises generation |
| Webhook API design fixture | Low | Mentioned in consumer types but no dedicated fixture |
| gRPC/Protobuf API design fixture | N/A | Explicitly out of scope for REST skill; separate skill needed |
| GraphQL API governance fixture | N/A | Different paradigm; separate skill |
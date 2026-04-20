# kafka-event-driven-design Skill — Test Coverage Matrix

## 1. Contract Tests (`test_skill_contract.py`)

| Test Class | Count | Validates |
|------------|:-----:|-----------|
| `TestFrontmatter` | 2 | name; trigger keywords (kafka, partition, consumer group, schema, idempotent, dead letter, exactly-once) |
| `TestMandatoryGates` | 6 | Gate 1–4 with STOP/PROCEED; context (version, ordering, delivery); risk levels |
| `TestDepthSelection` | 3 | Lite/Standard/Deep; force-Standard signals; reference loading |
| `TestDegradationModes` | 3 | Full/Degraded/Minimal/Planning; never-fabricate; delivery guarantee warning |
| `TestDesignChecklist` | 7 | 4 subsections; acks=all; idempotent; DLQ; partition key; Schema Registry; consumer lag |
| `TestPartitionDesign` | 2 | Ordering table; hot partition detection |
| `TestAntiExamples` | 4 | ≥6 AE; WRONG/RIGHT pairs; acks=1 AE; extended ref |
| `TestScorecard` | 5 | Critical/Standard/Hygiene; thresholds; critical items; verdict |
| `TestOutputContract` | 4 | 9 sections; uncovered risks; volume; scorecard in output |
| `TestReferenceFiles` | 7 | 3 files with min lines; keywords per file; AE numbering; all refs in SKILL.md |
| `TestLineCount` | 1 | SKILL.md ≤ 420 lines |
| `TestCrossFileConsistency` | 6 | Avro in schema patterns; DLQ in failure modes; rebalance; partition key; outbox; auto-commit in AE |
| **Total** | **50** | |

## 2. Golden Fixtures (`test_golden_scenarios.py`)

### 2.1 Fixture Inventory

| ID | Title | Type | Severity | Violated Rule |
|----|-------|------|----------|---------------|
| KAFKA-001 | acks=1 for critical events | defect | critical | Producer uses acks=all + idempotence |
| KAFKA-002 | Consumer without idempotency | defect | critical | Consumer handles duplicate delivery |
| KAFKA-003 | No dead letter queue | defect | critical | DLQ exists for poison messages |
| KAFKA-004 | Null partition key | defect | standard | Partition key matches ordering |
| KAFKA-005 | Event missing metadata | defect | standard | Schema includes event metadata |
| KAFKA-006 | Schema change without compatibility | defect | standard | Schema compatibility configured |
| KAFKA-007 | Well-formed event design | good_practice | none | — |
| KAFKA-008 | Good outbox pattern | good_practice | none | — |
| KAFKA-009 | Degraded — no context | degradation_scenario | none | — |
| KAFKA-010 | Greenfield design workflow | workflow | none | — |
| KAFKA-011 | No consumer lag monitoring | defect | standard | Consumer lag monitoring defined |

### 2.2 Per-Fixture Test Classes

| Fixture | Test Class | Tests | Validates |
|---------|-----------|:-----:|-----------|
| KAFKA-001 | `TestKAFKA001` | 3 | type/severity; violated_rule (acks); feedback mentions data loss |
| KAFKA-002 | `TestKAFKA002` | 3 | type/severity; violated_rule (duplicate/idempotent); feedback mentions rebalance/duplicate |
| KAFKA-003 | `TestKAFKA003` | 3 | type/severity; violated_rule (dead letter/DLQ); feedback mentions poison |
| KAFKA-004 | `TestKAFKA004` | 3 | type/severity; violated_rule (partition); feedback mentions ordering |
| KAFKA-005 | `TestKAFKA005` | 3 | type/severity; violated_rule (metadata/schema); feedback mentions event_id |
| KAFKA-006 | `TestKAFKA006` | 3 | type/severity; violated_rule (compatibility/schema); feedback mentions backward |
| KAFKA-007 | `TestKAFKA007` | 3 | type/severity; no violations; mentions acks/idempotent |
| KAFKA-008 | `TestKAFKA008` | 3 | type/severity; no violations; mentions outbox |
| KAFKA-009 | `TestKAFKA009` | 3 | type/severity; forbids claims; mentions degraded |
| KAFKA-010 | `TestKAFKA010` | 3 | type/severity; mentions partition key; mentions DLQ |
| KAFKA-011 | `TestKAFKA011` | 3 | type/severity; violated_rule (lag/monitoring); feedback mentions alert |

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
| Critical Defect Fixtures | 3/3 | 3 | 100% |
| Standard Defect Fixtures | 4/4 | 4 | 100% |
| Good Practice Fixtures | 2/2 | 2 | 100% |
| Degradation/Workflow | 2/2 | 2 | 100% |

**Grand Total: 91 tests** (50 contract + 41 golden)

## 4. Known Coverage Gaps

| Gap | Priority | Rationale |
|-----|----------|-----------|
| Exactly-once transactional consumer fixture | Medium | EOS pattern documented in references but no fixture |
| Compacted topic with tombstone handling | Low | Covered in AE-11 but no positive fixture |
| Multi-consumer-group fan-out fixture | Medium | Mentioned in design but no fixture exercises it |
| CQRS / Event Sourcing fixture | Low | Advanced pattern; not primary checklist concern |
| Kafka Connect / CDC integration fixture | Low | External tooling; not core event design |
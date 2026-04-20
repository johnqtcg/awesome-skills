# monitoring-alerting Skill — Test Coverage Matrix

## 1. Contract Tests (`test_skill_contract.py`)

| Test Class | Count | Validates |
|------------|:-----:|-----------|
| `TestFrontmatter` | 2 | name; trigger keywords (Prometheus, Grafana, SLI, SLO, alert, burn-rate, PagerDuty, cardinality) |
| `TestMandatoryGates` | 6 | Gate 1–4; service type + traffic; scope modes (review/design/audit); risk levels |
| `TestDepthSelection` | 3 | Lite/Standard/Deep; force-Standard signals; reference loading |
| `TestDegradationModes` | 3 | Full/Degraded/Minimal/Planning; never-guess-thresholds; traffic warning |
| `TestDesignChecklist` | 8 | 4 subsections; SLI/SLO/error budget; burn-rate; actionable; for duration; runbook; cardinality; RED/USE |
| `TestAntiExamples` | 4 | ≥6 AE; WRONG/RIGHT pairs; absolute-count AE; extended ref |
| `TestScorecard` | 5 | Critical/Standard/Hygiene; thresholds; critical items (SLI, actionable, routing); verdict |
| `TestOutputContract` | 4 | 9 sections (§8.1–§8.9); uncovered risks; volume; scorecard |
| `TestReferenceFiles` | 7 | 3 files with min lines; keywords; AE numbering; alertmanager config keywords; all refs in SKILL.md |
| `TestAlertRoutingDesign` | 2 | inhibition + suppress in checklist; severity→receiver mapping (critical→PagerDuty, warning→Slack) |
| `TestLineCount` | 1 | SKILL.md ≤ 420 lines |
| `TestCrossFileConsistency` | 8 | burn-rate in SLI/SLO ref; PromQL; p50 in anti-patterns; cardinality; runbook_url; group_by; inhibit_rules in alertmanager config; group_wait in alertmanager config |
| **Total** | **53** | |

## 2. Golden Fixtures

### 2.1 Fixture Inventory

| ID | Title | Type | Severity | Violated Rule |
|----|-------|------|----------|---------------|
| MON-001 | No SLIs defined | defect | critical | SLIs defined and measured |
| MON-002 | Non-actionable alert | defect | critical | Every alert is actionable |
| MON-003 | Critical routed to Slack only | defect | critical | Severity labels match routing |
| MON-004 | No for duration — flapping | defect | standard | for duration set |
| MON-005 | Missing runbook link | defect | standard | Runbook link included |
| MON-006 | High-cardinality label | defect | standard | No high-cardinality labels |
| MON-007 | Well-formed SLO monitoring | good_practice | none | — |
| MON-008 | Good RED-method dashboard | good_practice | none | — |
| MON-009 | Degraded — no service context | degradation_scenario | none | — |
| MON-010 | Greenfield monitoring design | workflow | none | — |
| MON-011 | No alert grouping | defect | standard | Grouping/deduplication configured |
| MON-012 | No inhibition rules — alert cascade | defect | standard | Inhibition rules prevent alert cascade |
| MON-013 | SLO error budget exhaustion response | workflow | none | — |

### 2.2 Per-Fixture Test Classes

| Fixture | Test Class | Tests | Validates |
|---------|-----------|:-----:|-----------|
| MON-001 | `TestMON001` | 3 | type/severity; violated_rule (SLI); feedback mentions SLI + availability/latency |
| MON-002 | `TestMON002` | 3 | type/severity; violated_rule (actionable); feedback mentions runbook/action |
| MON-003 | `TestMON003` | 3 | type/severity; violated_rule (severity/routing); feedback mentions PagerDuty |
| MON-004 | `TestMON004` | 3 | type/severity; violated_rule (for/flapping/duration); feedback mentions for: |
| MON-005 | `TestMON005` | 3 | type/severity; violated_rule (runbook); feedback mentions runbook |
| MON-006 | `TestMON006` | 3 | type/severity; violated_rule (cardinality); feedback mentions user_id |
| MON-007 | `TestMON007` | 3 | type/severity; no violations; mentions burn rate |
| MON-008 | `TestMON008` | 3 | type/severity; no violations; mentions RED |
| MON-009 | `TestMON009` | 3 | type/severity; forbids claims; mentions degraded |
| MON-010 | `TestMON010` | 3 | type/severity; mentions SLO/SLI; mentions routing |
| MON-011 | `TestMON011` | 3 | type/severity; violated_rule (grouping/deduplication); mentions group |
| MON-012 | `TestMON012` | 3 | type/severity; violated_rule (inhibition/cascade); feedback mentions inhibit_rules |
| MON-013 | `TestMON013` | 3 | type/severity; feedback mentions error budget; feedback mentions decision actions |

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
| Cross-File Terminology | 8/8 | 8 | 100% |
| SKILL.md Line Budget | — | 420 | under budget |
| Critical Defect Fixtures | 3/3 | 3 | 100% |
| Standard Defect Fixtures | 5/5 | 5 | 100% |
| Good Practice Fixtures | 2/2 | 2 | 100% |
| Degradation/Workflow | 3/3 | 3 | 100% |

**Grand Total: 100 tests** (53 contract + 47 golden)

## 4. Known Coverage Gaps

| Gap | Priority | Rationale |
|-----|----------|-----------|
| Log-based alerting (Loki/ELK) fixture | Low | Out of scope (Prometheus-focused); mentioned peripherally |
| Multi-cluster monitoring fixture | Low | Advanced pattern; not primary checklist |
| Synthetic monitoring / uptime check fixture | Low | External probing pattern; separate concern |
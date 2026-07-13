# load-test Skill — Test Coverage Matrix

Coverage matrix for the load-test skill regression test suite. The suite is
zero-LLM and has two layers: (1) structure + golden-fixture integrity
(`test_skill_contract.py`, `test_golden_scenarios.py`) validate SKILL.md
structure and fixture classification, not model behavior; (2) behavioral k6
checks (`test_k6_scripts_valid.py`) statically validate the reference scripts
(import completeness, Rate-metric semantics) and run `k6 inspect` when k6 is
installed.

## Contract Tests (`test_skill_contract.py`)

| Test Class | Tests | Validates |
|------------|:-----:|-----------|
| `TestFrontmatter` | 3 | name=load-test; description trigger keywords (k6, vegeta, wrk, SLO, bottleneck, latency, throughput); allowed-tools present |
| `TestMandatoryGates` | 6 | §2 section exists; Gate 1-4 content; STOP semantics (>= 3 occurrences); Write/Review/Analyze modes |
| `TestDepthSelection` | 5 | Lite/Standard/Deep headings; Standard is default; Force Standard/Deep conditions; reference loading mentions all 3 files |
| `TestDegradationModes` | 5 | 5 modes (Full/Script/Partial/Analysis/Planning); Can Deliver/Cannot Claim columns; fabrication prohibition; degraded marker |
| `TestLoadTestChecklist` | 6 | 4 subsections (5.1-5.4); SLO/script/analysis/environment items; >= 18 numbered checklist items (19 present) |
| `TestScenarioAndToolSelection` | 4 | k6/vegeta/wrk table; default to k6; 6 scenario types (Smoke/Load/Stress/Breakpoint/Soak/Spike); goal mapping |
| `TestAntiExamples` | 8 | AE-1 through AE-6 verified by title (8 AEs total in §7); >= 6 WRONG/RIGHT pairs |
| `TestScorecard` | 6 | §8 exists; Critical tier (3 items); Standard tier (5 items); Hygiene tier (5 items); passing criteria; verdict format |
| `TestOutputContract` | 12 | §9.1-9.9 exist; each section has expected content; volume rules; scorecard appended; uncovered risks mandatory |
| `TestReferenceFiles` | 9 | 3 files exist; SKILL.md references them; k6 executor types; thresholds; vegeta attack/report/pipeline; analysis percentile/saturation/bottleneck; SLO verdicts |
| `TestLineCount` | 1 | SKILL.md <= 500 lines |
| `TestCrossFileConsistency` | 10 | Shared terms (p99, percentile, SLO, warmup, saturation, bottleneck) across SKILL.md + refs; dropped_iterations; min lines per reference (k6>=400, vegeta>=200, analysis>=250) |

**Contract test count: 75**

## Behavioral k6 Script Tests (`test_k6_scripts_valid.py`)

| Test Class | Tests | Validates |
|------------|:-----:|-----------|
| `ImportCompletenessTests` | 2 | every complete reference script found (>=5); every used k6 module (`k6/http`, `k6/data`, `k6/metrics`, `k6`) is imported — catches copy-paste `ReferenceError`s that `k6 inspect` cannot |
| `RateMetricSemanticsTests` | 1 | a custom `Rate` in a reference script is never fed only literal `1` (the 0%/100% anti-pattern); it must record a boolean every iteration |
| `K6InspectTests` | 1 | `k6 inspect` parses each local script and runs its init context (skipped when k6 is not installed) |

**Behavioral test count: 4** (3 static, always run; 1 `k6 inspect`, skipped without k6)

## Golden Fixtures + Per-Fixture Test Classes (`test_golden_scenarios.py`)

### Fixture Inventory

| ID | Title | Type | Severity | Maps To |
|----|-------|------|----------|---------|
| LT-001 | No warmup phase | defect | critical | AE-1 + Scorecard Critical #2 |
| LT-002 | No SLO thresholds | defect | critical | AE-2 + Scorecard Critical #1 |
| LT-003 | 30s test declared comprehensive | defect | critical | AE-5 + Scorecard Critical #3 |
| LT-004 | Load generator co-located | defect | standard | AE-3 + Scorecard Standard #7 |
| LT-005 | Same request every time (cache bias) | defect | standard | AE-4 + Scorecard Standard #8 |
| LT-006 | Averages as verdict | defect | standard | AE-6 + Scorecard Standard #6 |
| LT-007 | Instant full load, no ramp | defect | standard | Scorecard Standard #4 |
| LT-008 | Well-formed k6 script | good_practice | none | Positive exemplar (k6) + Rate-semantics guard |
| LT-009 | Well-formed vegeta breakpoint | good_practice | none | Positive exemplar (vegeta) |
| LT-010 | Results without SLOs | degradation_scenario | none | §4 Partial mode |
| LT-011 | Vague request, no context | degradation_scenario | none | §4 Planning mode |
| LT-012 | Multi-scenario capacity plan | workflow | none | Deep depth, Write mode |
| LT-013 | Analyze results with SLO verdict | workflow | none | Analyze mode |
| LT-014 | Review existing script | workflow | none | Review mode |
| LT-015 | Rate metric records only failures | defect | standard | k6 Rate semantics (§7 custom-metric rule) |

### Per-Fixture Test Classes

| Class | Fixture | Tests | Validates |
|-------|---------|:-----:|-----------|
| `TestFixtureIntegrity` | all | 8 | count>=11; required fields; valid types/severities; defect!=none; non-defect=none; unique IDs; coverage_rules findable |
| `TestLT001`–`TestLT007` | 001-007 | 3 each | type/severity; violated_rule keyword; feedback keyword |
| `TestLT008` | 008 | 4 | good_practice/none; "no violation"; SharedArray; **Rate recorded every iteration (regression guard)** |
| `TestLT009`–`TestLT014` | 009-014 | 3 each | type/severity; feedback keywords per scenario |
| `TestLT015` | 015 | 3 | defect/standard; violated_rule mentions Rate; feedback explains the `add(!ok)` fix |

**Golden test count: 54** (8 integrity + 46 behavioral)

## Coverage Summary

| Category | Covered | Total | Coverage |
|----------|:-------:|:-----:|:--------:|
| Mandatory Gates (§2) | 4/4 | 4 | 100% |
| Depth Tiers (§3) | 3/3 | 3 | 100% |
| Degradation Modes (§4) | 5/5 | 5 | 100% |
| Checklist Subsections (§5) | 4/4 | 4 | 100% |
| Checklist Items (§5) | 19/19 | 19 | 100% |
| Tool Selection (§6.1) | 3/3 | 3 | 100% |
| Scenario Types (§6.2) | 6/6 | 6 | 100% |
| Anti-Examples (§7) | 8/8 | 8 | 100% |
| Scorecard Items (§8) | 13/13 | 13 | 100% |
| Output Contract Sections (§9) | 9/9 | 9 | 100% |
| Reference Files | 3/3 | 3 | 100% |
| Golden Fixture Types | 4/4 | 4 | 100% |
| Golden Severity Levels | 3/3 | 3 | 100% |

**Total tests: 133** (75 contract + 54 golden + 4 behavioral k6-script). Without k6
installed, `K6InspectTests` is skipped, so 132 run + 1 skipped.

## Known Coverage Gaps

| Gap | Priority | Rationale |
|-----|----------|-----------|
| Soak test fixture (30-60 min leak detection) | Medium | §6.2 defines Soak but no golden fixture exercises memory-leak-over-time detection methodology. |
| gRPC load testing fixture | Medium | SKILL §1 marks gRPC "partial coverage"; no reference pattern or fixture exercises gRPC (streaming, unary, metadata auth). |
| Distributed k6 (Operator / Cloud / segments) fixture | Low | SKILL §1 marks distributed "partial coverage"; no fixture covers distributed execution coordination. |
| wrk scripting fixture | Low | SKILL §1 marks wrk "partial coverage"; no wrk/Lua reference pattern or fixture. |
| Scorecard Standard #5 (error rate monitored) dedicated fixture | Low | Validated in contract tests but no golden fixture targets missing error classification (429 vs 503 vs timeout). |
| CI/CD integration fixture (pipeline gating) | Low | §10 documents CI integration but no fixture exercises pipeline fail/pass gating on threshold results. |
| Runtime Rate-metric behavior via an executed `k6 run` | Low | LT-015 + `RateMetricSemanticsTests` statically catch the "Rate fed only on failure" bug; a full `k6 run` executing `default()` would additionally verify runtime metric emission, but requires k6 in CI. |
# load-test Skill — Test Coverage Matrix

Coverage matrix for the load-test skill regression test suite.
Tests are zero-LLM: they validate SKILL.md structure and golden fixture integrity, not model behavior.

## Contract Tests (`test_skill_contract.py`)

| Test Class | Tests | Validates |
|------------|:-----:|-----------|
| `TestFrontmatter` | 3 | name=load-test; description trigger keywords (k6, vegeta, wrk, SLO, bottleneck, latency, throughput); allowed-tools present |
| `TestMandatoryGates` | 6 | §2 section exists; Gate 1-4 content; STOP semantics (>= 3 occurrences); Write/Review/Analyze modes |
| `TestDepthSelection` | 5 | Lite/Standard/Deep headings; Standard is default; Force Standard/Deep conditions; reference loading mentions all 3 files |
| `TestDegradationModes` | 5 | 5 modes (Full/Script/Partial/Analysis/Planning); Can Deliver/Cannot Claim columns; fabrication prohibition; degraded marker |
| `TestLoadTestChecklist` | 6 | 4 subsections (5.1-5.4); SLO/script/analysis/environment items; >= 18 numbered checklist items |
| `TestScenarioAndToolSelection` | 4 | k6/vegeta/wrk table; default to k6; 6 scenario types (Smoke/Load/Stress/Breakpoint/Soak/Spike); goal mapping |
| `TestAntiExamples` | 8 | AE-1 through AE-6 exist; each by title keyword; >= 6 WRONG/RIGHT pairs |
| `TestScorecard` | 6 | §8 exists; Critical tier (3 items); Standard tier (5 items); Hygiene tier (4 items); passing criteria; verdict format |
| `TestOutputContract` | 12 | §9.1-9.9 exist; each section has expected content; volume rules; scorecard appended; uncovered risks mandatory |
| `TestReferenceFiles` | 9 | 3 files exist; SKILL.md references them; k6 executor types; thresholds; vegeta attack/report/pipeline; analysis percentile/saturation/bottleneck; SLO verdicts |
| `TestLineCount` | 1 | SKILL.md <= 420 lines |
| `TestCrossFileConsistency` | 10 | Shared terms (p99, percentile, SLO, warmup, saturation, bottleneck) across SKILL.md + refs; dropped_iterations; min lines per reference (k6>=400, vegeta>=200, analysis>=250) |

**Contract test count: 75**

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
| LT-008 | Well-formed k6 script | good_practice | none | Positive exemplar (k6) |
| LT-009 | Well-formed vegeta breakpoint | good_practice | none | Positive exemplar (vegeta) |
| LT-010 | Results without SLOs | degradation_scenario | none | §4 Partial mode |
| LT-011 | Vague request, no context | degradation_scenario | none | §4 Planning mode |
| LT-012 | Multi-scenario capacity plan | workflow | none | Deep depth, Write mode |
| LT-013 | Analyze results with SLO verdict | workflow | none | Analyze mode |
| LT-014 | Review existing script | workflow | none | Review mode |

### Per-Fixture Test Classes

| Class | Fixture | Tests | Validates |
|-------|---------|:-----:|-----------|
| `TestFixtureIntegrity` | all | 8 | count>=11; required fields; valid types/severities; defect!=none; non-defect=none; unique IDs; coverage_rules findable |
| `TestLT001` | 001 | 3 | type=defect/critical; violated_rule contains "warmup"; feedback mentions warmup |
| `TestLT002` | 002 | 3 | type=defect/critical; violated_rule contains "SLO"; feedback mentions SLO+threshold |
| `TestLT003` | 003 | 3 | type=defect/critical; violated_rule contains "duration"; feedback mentions 30s/insufficient |
| `TestLT004` | 004 | 3 | type=defect/standard; violated_rule contains "co-located"; feedback mentions separate |
| `TestLT005` | 005 | 3 | type=defect/standard; violated_rule contains "parameterized"; feedback mentions SharedArray |
| `TestLT006` | 006 | 3 | type=defect/standard; violated_rule contains "percentile"; feedback mentions p99 |
| `TestLT007` | 007 | 3 | type=defect/standard; violated_rule contains "ramp"; feedback mentions ramp |
| `TestLT008` | 008 | 3 | type=good_practice/none; feedback "no violation"; feedback mentions SharedArray |
| `TestLT009` | 009 | 3 | type=good_practice/none; feedback "no violation"; feedback mentions vegeta |
| `TestLT010` | 010 | 3 | type=degradation_scenario/none; feedback "cannot claim"; feedback mentions degraded |
| `TestLT011` | 011 | 3 | type=degradation_scenario/none; feedback mentions Gate 1; feedback mentions planning |
| `TestLT012` | 012 | 3 | type=workflow/none; feedback mentions smoke+breakpoint; feedback mentions SLO |
| `TestLT013` | 013 | 3 | type=workflow/none; feedback mentions verdict; feedback mentions bottleneck |
| `TestLT014` | 014 | 3 | type=workflow/none; feedback mentions review; feedback mentions finding |

**Golden test count: 50** (8 integrity + 42 behavioral)

## Coverage Summary

| Category | Covered | Total | Coverage |
|----------|:-------:|:-----:|:--------:|
| Mandatory Gates (§2) | 4/4 | 4 | 100% |
| Depth Tiers (§3) | 3/3 | 3 | 100% |
| Degradation Modes (§4) | 5/5 | 5 | 100% |
| Checklist Subsections (§5) | 4/4 | 4 | 100% |
| Checklist Items (§5) | 18/18 | 18 | 100% |
| Tool Selection (§6.1) | 3/3 | 3 | 100% |
| Scenario Types (§6.2) | 6/6 | 6 | 100% |
| Anti-Examples (§7) | 6/6 | 6 | 100% |
| Scorecard Items (§8) | 12/12 | 12 | 100% |
| Output Contract Sections (§9) | 9/9 | 9 | 100% |
| Reference Files | 3/3 | 3 | 100% |
| Golden Fixture Types | 4/4 | 4 | 100% |
| Golden Severity Levels | 3/3 | 3 | 100% |

**Total tests: 125** (75 contract + 50 golden)

## Known Coverage Gaps

| Gap | Priority | Rationale |
|-----|----------|-----------|
| Soak test fixture (30-60 min leak detection) | Medium | §6.2 defines Soak scenario but no golden fixture exercises memory-leak-over-time detection methodology. Soak differs from Load/Stress in analysis patterns. |
| gRPC load testing fixture | Medium | §1 scope includes gRPC but all fixtures use HTTP endpoints. A gRPC fixture would validate protocol-specific patterns (streaming, unary, metadata auth). |
| Distributed k6 (k6 Cloud / k6-operator) fixture | Low | references/k6-patterns.md §9 documents multi-scenario composition but no fixture covers distributed execution coordination or k6 Cloud thresholds. |
| wrk scripting fixture | Low | §6.1 lists wrk as a tool option but no golden fixture uses wrk/Lua scripting. vegeta and k6 cover the primary paths. |
| Scorecard Standard #5 (error rate monitored) dedicated fixture | Low | Error rate is validated in contract tests but no golden fixture specifically targets missing error classification (429 vs 503 vs timeout). |
| CI/CD integration fixture (GitHub Actions / pipeline gating) | Low | references/k6-patterns.md §10 documents CI integration but no fixture exercises pipeline fail/pass gating based on threshold results. |
# Go-Benchmark Skill — Test Coverage Matrix

## Contract Tests (`test_skill_contract.py`)

| Test Class | Tests | Validates |
|------------|-------|-----------|
| `TestFrontmatter` | 2 | name=go-benchmark; trigger keywords |
| `TestHardRules` | 6 | Section exists; all 5 Hard Rules by key phrase |
| `TestMandatoryGates` | 5 | 3 gates: Evidence (mode/data-basis), Applicability (STOP), Scope (5 shapes) |
| `TestThreePhaseWorkflow` | 7 | 3 phases + key elements per phase |
| `TestOutputContract` | 5 | 4 required fields: mode, data_basis, scorecard_result, profiling_method |
| `TestExpectedOutputFormat` | 4 | Output format section; run command; top-3 hotspots; scorecard block |
| `TestHonestDegradation` | 5 | Table exists; 4 degradation paths; no invented numbers |
| `TestAutoScorecard` | 5 | Section exists; Critical/Standard/Hygiene tiers; next-step table |
| `TestAntiExamples` | 5 | Section exists; 3 BAD/GOOD pairs; ≥3 markers each |
| `TestReferenceFiles` | 10 | All 5 files exist; SKILL.md references all 5; key content per file |
| `TestLineCount` | 1 | SKILL.md ≤ 420 lines |
| `TestCrossFileConsistency` | 10 | Key terms present in correct ref files; minimum line counts per file |

**Contract test count: 65**

## Golden Fixtures + Per-Fixture Test Classes (`test_golden_scenarios.py`)

### Fixture Inventory

| ID | Title | Type | Severity |
|----|-------|------|----------|
| BENCH-001 | Missing sink (`_ =` discards result) | defect | critical |
| BENCH-002 | Setup inside loop (connectDB in hot path) | defect | critical |
| BENCH-003 | `b.ResetTimer()` inside loop | defect | critical |
| BENCH-004 | Single-count comparison (no `-count=10`) | defect | standard |
| BENCH-005 | Good sub-benchmark with size sweep ✓ | good_practice | none |
| BENCH-006 | Good parallel benchmark with `RunParallel` ✓ | good_practice | none |
| BENCH-007 | Good throughput benchmark with `b.SetBytes` ✓ | good_practice | none |
| BENCH-008 | Run command missing `-benchmem` | defect | critical |
| BENCH-009 | Degraded output — no code or data | degradation_scenario | none |
| BENCH-010 | Profile-guided workflow (pprof → targeted benchmark) | workflow | none |
| BENCH-011 | Noisy benchstat (± > 5%, p > 0.05) | defect | standard |

### Per-Fixture Test Classes

| Class | Fixture | Type Tests | Coverage Tests |
|-------|---------|-----------|----------------|
| `TestBench001MissingSink` | 001 | type=defect, severity=critical, sink in violated_rule | all coverage_rules |
| `TestBench002SetupInsideLoop` | 002 | type=defect, severity=critical, timer in violated_rule | all coverage_rules |
| `TestBench003ResetTimerInsideLoop` | 003 | type=defect, severity=critical, timer in violated_rule | all coverage_rules |
| `TestBench004SingleCountComparison` | 004 | type=defect, severity=standard | all coverage_rules |
| `TestBench005SubBenchmarkSizes` | 005 | type=good_practice, no violations in feedback | all coverage_rules |
| `TestBench006ParallelBenchmark` | 006 | type=good_practice, no violations in feedback | all coverage_rules |
| `TestBench007ThroughputBenchmark` | 007 | type=good_practice, no violations in feedback | all coverage_rules |
| `TestBench008MissingBenchmem` | 008 | type=defect, severity=critical, benchmem in violated_rule | all coverage_rules |
| `TestBench009DegradedNoData` | 009 | type=degradation_scenario, "fabricate" in expected_feedback | all coverage_rules |
| `TestBench010PprofGuidedBenchmark` | 010 | type=workflow, severity=none | all coverage_rules |
| `TestBench011NoisyBenchstat` | 011 | type=defect, severity=standard | all coverage_rules |

**Golden test count: 30** (8 integrity + 11 per-fixture × 2 tests = 22 behavioral)

## Coverage Summary

| Category | Total | Tested | Coverage |
|---------|-------|--------|----------|
| Hard Rules | 5 | 5 | 100% |
| Mandatory Gates | 3 | 3 | 100% |
| Three phases | 3 | 3 | 100% |
| Scorecard tiers | 3 | 3 | 100% |
| Output contract fields | 4 | 4 | 100% |
| Anti-example patterns | 3 | 3 | 100% |
| Degradation levels | 4 | 4 | 100% |
| Reference files | 5 | 5 | 100% |
| Cross-file terminology | key terms | 6 | 100% |
| Reference file min lines | 5 files | 5 | 100% (≥80-100) |
| SKILL.md line budget | 378/420 | 1 | ✅ |
| Defect fixtures (critical + standard) | 6 | 6 | 100% |
| Good-practice fixtures | 3 | 3 | 100% |
| Degradation/workflow scenarios | 2 | 2 | 100% |

**Total tests: 96** (65 contract + 30 golden + 1 integrity)

## Known Coverage Gaps

| Gap | Priority |
|-----|----------|
| sync.Pool before/after optimization fixture | Low |
| escape analysis workflow fixture | Low |
| Multi-environment comparison error fixture | Low |
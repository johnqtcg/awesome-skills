# Go-Benchmark Skill — Test Coverage Matrix

## Contract Tests (`test_skill_contract.py`)

| Test Class | Tests | Validates |
|------------|-------|-----------|
| `TestFrontmatter` | 2 | name=go-benchmark; trigger keywords (testing.B, pprof, benchstat, ns/op) |
| `TestHardRules` | 6 | Section exists; all 5 Hard Rules by key phrase |
| `TestMandatoryGates` | 5 | 3 gates: Evidence (mode/data-basis labels), Applicability (STOP), Scope (shapes) |
| `TestThreePhaseWorkflow` | 7 | 3 phases + key elements per phase (benchstat, pprof flags, sync.Pool, Flame Graph) |
| `TestOutputContract` | 5 | 4 required fields: mode, data_basis, scorecard_result, profiling_method |
| `TestExpectedOutputFormat` | 4 | Output format section; run command; top-3 hotspots; scorecard block format |
| `TestHonestDegradation` | 5 | Table exists; source-only, benchmark-output, pprof paths; no invented numbers |
| `TestAutoScorecard` | 5 | Section exists; Critical/Standard/Hygiene tiers with specific items; next-step table |
| `TestAntiExamples` | 5 | Section exists; 3 anti-patterns with BAD/GOOD pairs; ≥3 BAD markers + ≥3 GOOD markers |
| `TestReferenceFiles` | 10 | All 5 reference files exist; SKILL.md references all 5; key content per file |
| `TestLineCount` | 1 | SKILL.md ≤ 400 lines |

**Contract test count: 55**

## Golden Fixtures + Behavioral Tests (`test_golden_scenarios.py`)

### Fixture Schema

Each fixture requires: `id`, `title`, `type`, `severity`, `benchmark_snippet`, `expected_feedback`, `coverage_rules`, `reference`

### Fixture Inventory

| ID | Title | Type | Severity | Rule Violated |
|----|-------|------|----------|---------------|
| BENCH-001 | Missing sink (`_ =` discards result) | defect | critical | Sink every result |
| BENCH-002 | Setup inside loop (connectDB in hot path) | defect | critical | Timer discipline |
| BENCH-003 | `b.ResetTimer()` inside loop | defect | critical | Timer discipline |
| BENCH-004 | Single-count comparison (no `-count=10`) | defect | standard | `-count=10` for comparisons |
| BENCH-005 | Good sub-benchmark with size sweep ✓ | good_practice | none | — |
| BENCH-006 | Good parallel benchmark with `RunParallel` ✓ | good_practice | none | — |
| BENCH-007 | Good throughput benchmark with `b.SetBytes` ✓ | good_practice | none | — |
| BENCH-008 | Run command missing `-benchmem` | defect | critical | Always `-benchmem` |

### Test Classes

| Class | Tests | What it verifies |
|-------|-------|-----------------|
| `TestFixtureIntegrity` | 8 | Required fields, valid types/severities, no duplicate IDs, coverage rules exist in docs |
| `TestCriticalDefects` | 4 | type=defect, severity=critical, violated_rule semantics, coverage |
| `TestStandardDefects` | 1 | type=defect, severity=standard, coverage |
| `TestGoodPracticePatterns` | 3 | type=good_practice, severity=none, "no violations" in feedback, coverage |

**Golden test count: 16** (8 integrity + 4 critical + 1 standard + 3 good-practice)

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
| Critical defect fixtures | 4 | 4 | 100% |
| Good practice fixtures | 3 | 3 | 100% |
| SKILL.md line budget | 1 | 1 | 100% |

**Total tests: 71** (55 contract + 16 golden)

## Known Coverage Gaps

| Gap | Priority |
|-----|----------|
| Profile-guided workflow fixture (no baseline → pprof → targeted benchmark) | Medium |
| Multi-environment comparison error fixture (same benchmark on two machines) | Medium |
| benchstat output interpretation fixture (noisy results: ± > 5%) | Low |
| `sync.Pool` optimization before/after fixture | Low |
| escape analysis workflow fixture | Low |
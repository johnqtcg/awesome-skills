# Deep Research Skill — Rule-to-Scenario Coverage Matrix

Maps each core rule/gate/section in SKILL.md to its golden fixture and contract test.

## Contract Tests (`test_skill_contract.py`)

| Rule / Section | Test Class | Status |
|----------------|------------|--------|
| Frontmatter: name, description, allowed-tools | `TestFrontmatter` (7 tests) | ✅ |
| 8 mandatory gates in serial order | `TestMandatoryGates` (7 tests) | ✅ |
| Gate names (Scope Classif., Ambiguity, Evidence, Mode, Hallucination, Budget, Extraction, Integrity) | `TestMandatoryGates.test_gate_names_are_correct` | ✅ |
| Evidence requirements table (minimum evidence chain per claim type) | `TestMandatoryGates.test_evidence_requirements_table` | ✅ |
| Hallucination awareness table | `TestMandatoryGates.test_hallucination_awareness_table` | ✅ |
| 3 execution modes (Quick / Standard / Deep) | `TestExecutionModes` (5 tests) | ✅ |
| Mode auto-selection table with triggers | `TestExecutionModes.test_mode_auto_selection_table` | ✅ |
| Budget per mode (5-10, 15-25, 30-50) + hard ceiling 50 | `TestExecutionModes.test_budget_per_mode` | ✅ |
| User explicit mode override | `TestExecutionModes.test_user_override_capability` | ✅ |
| Anti-examples section (≥ 8 BAD/GOOD pairs) | `TestAntiExamples` (3 tests) | ✅ |
| Honest degradation (Full / Partial / Blocked) | `TestHonestDegradation` (2 tests) | ✅ |
| 9-section output contract | `TestOutputContract` (5 tests) | ✅ |
| Safety rules (never fabricate, contradict surfaced) | `TestSafetyRules` (3 tests) | ✅ |
| Reference files exist (output-contract-template, hallucination-and-verification, research-patterns) | `TestReferenceFiles` (5 tests) | ✅ |
| Hallucination types: Fabricated Citation, Stale Information, Confidence Inflation, Phantom Feature | `TestHallucinationReference` (6 tests) | ✅ |
| Source Tier Ranking (T1-T5) + Cross-Validation Protocol | `TestHallucinationReference` | ✅ |
| 9 research patterns (Error Debugging, Tech Comparison, Security Research, etc.) | `TestResearchPatterns` (9 tests) | ✅ |
| Subcommand table (retrieve, fetch-content, search-codebase, validate, report) | `TestSubcommandTable` (2 tests) | ✅ |
| SKILL.md line count ≤ 500 | `TestLineCount` (1 test) | ✅ |
| Progressive disclosure via "→ Load" references | `TestProgressiveDisclosure` (2 tests) | ✅ |
| **Gate 8: Execution Integrity — specific honesty rules** | **`TestGate8ExecutionIntegrity` (4 tests)** | ✅ |

## Golden Fixtures (`test_golden_scenarios.py`)

### Keyword Coverage Fixtures (`TestGoldenFromFixtures`)

| Fixture | Scenario | Key Keywords Verified |
|---------|----------|-----------------------|
| `error_debugging` | Error message research workflow | Error Debugging, site:github.com, Root cause |
| `tech_comparison` | Framework/architecture comparison | Technology Comparison, benchmark, Trade-off |
| `hallucination_awareness` | AI hallucination detection | Fabricated Citation, Stale Information, Confidence Inflation |
| `codebase_research` | Internal + external hybrid research | Codebase Research, search-codebase, ripgrep |
| `performance_benchmark` | Benchmark data research | Performance Benchmark, methodology, environment |
| `security_research` | CVE and advisory research | Security Research, CVE, security advisory |
| `ai_tool_selection` | AI tool recommendation | AI Tool Selection, Perplexity, NotebookLM |
| `evidence_chain` | Confidence and evidence chain rules | Evidence Requirements, Minimum Evidence Chain |

### Behavioral Scenario Fixtures (`TestBehavioralScenarios`)

| Fixture | Decision Being Tested | Expected Outcome |
|---------|-----------------------|-----------------|
| `behavior_mode_quick` | Auto-selection: single factual claim | `expected_mode: Quick` |
| `behavior_mode_deep_security` | Auto-selection: security-sensitive multi-vendor decision | `expected_mode: Deep` |
| `behavior_mode_user_override` | Explicit user override takes precedence | `user_override: true` + Standard mode |
| `fp_quick_prevents_over_research` | **FP**: trivial fact should NOT trigger Deep | `is_deep_research_needed: false` |
| `fp_codebase_no_web_retrieval` | **FP**: internal codebase question should NOT trigger web retrieval | `is_web_research_needed: false` |

## Coverage Summary

| Metric | Count |
|--------|-------|
| Total golden fixtures | 13 (8 keyword + 5 behavioral) |
| Keyword coverage fixtures | 8 |
| Behavioral scenario fixtures (mode + FP) | 5 |
| Contract tests (classes) | 13 classes |
| Contract test methods (approx) | ~60 |
| SKILL.md lines | 287 (budget: ≤ 500) |

## Gap Analysis

When adding a new gate, mode, or decision rule to SKILL.md:

1. Add a behavioral fixture that exercises the decision point.
2. Add a contract test that verifies the key rule text exists.
3. Update this matrix.

### Known Coverage Gaps

| Scenario | Category | Priority |
|----------|----------|----------|
| Ambiguity Resolution Gate (Gate 2) stop-and-ask behavior fixture | behavioral | Low |
| Budget exhaustion → Blocked degradation fixture | behavioral | Low |
| Multi-round retrieval (Standard Round 1→2) workflow fixture | workflow | Low |
| Inline `TestCommonScenarios` tests have no corresponding fixture | meta | Low |
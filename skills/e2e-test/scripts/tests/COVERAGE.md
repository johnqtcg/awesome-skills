# E2E Best Practise Skill — Test Coverage Matrix

## Contract Tests (`test_skill_contract.py`)

| # | Class | Tests | Covers |
|---|-------|-------|--------|
| 1 | TestFrontmatter | 3 | name, description keywords, description length |
| 2 | TestMandatoryGates | 6 | 5 gates + serial ordering |
| 3 | TestAntiExamples | 8 | section exists, count ≥ 7, each anti-example keyword |
| 4 | TestQualityScorecard | 7 | section, 3 tiers, C1-C4, S1-S6, H1-H4 |
| 5 | TestVersionGate | 4 | section, Playwright versions, Node versions, frameworks |
| 6 | TestOutputContract | 2 | 8 output fields, conditional code output |
| 7 | TestRunnerStrategy | 2 | dual-tool strategy, bridge workflow |
| 8 | TestPlaywrightRules | 2 | section exists, key concepts |
| 9 | TestFlakyPolicy | 3 | section, triage sequence, root cause categories |
| 10 | TestReferenceFiles | 14 | existence, depth, code examples, sections |
| 11 | TestSelectiveLoading | 2 | section, per-reference conditions |
| 12 | TestAccessibilityContent | 6 | axe-core, WCAG tags, scoped analysis, journey-integrated, violations |
| 13 | TestVisualRegressionContent | 6 | toHaveScreenshot, masking, baselines, thresholds, external services |
| 14 | TestMobileDesktopContent | 7 | device emulation, breakpoints, Electron, React Native, geolocation, platform matrix |
| 15 | TestDiscoverScript | 4 | exists, executable, referenced, key checks |
| 16 | TestJsonOutput | 2 | section, key JSON fields |
| 17 | TestGoldenExamplesTOC | 1 | TOC present |
| **Total** | **18 classes** | **81** | |

## Golden Scenario Tests (`test_golden_scenarios.py`)

| # | Class | Tests | Fixture | Scenario |
|---|-------|-------|---------|----------|
| 1 | TestGoldenFixtureStructure | 2 | all | structure + count ≥ 10 |
| 2 | TestGolden001LoginJourney | 4 | 001 | New login journey coverage |
| 3 | TestGolden002HonestScaffold | 4 | 002 | Missing account → scaffold |
| 4 | TestGolden003FlakyTriage | 4 | 003 | Async race flaky triage |
| 5 | TestGolden004CIGate | 3 | 004 | CI gate design |
| 6 | TestGolden005AgentBrowserExploration | 3 | 005 | Exploration → Playwright |
| 7 | TestGolden006NoBaseURL | 3 | 006 | Stop condition |
| 8 | TestGolden007SerialCheckout | 4 | 007 | Serial checkout funnel |
| 9 | TestGolden008VersionGate | 3 | 008 | Old Playwright version |
| 10 | TestGolden009Accessibility | 3 | 009 | Accessibility audit |
| 11 | TestGolden010VisualRegression | 3 | 010 | Visual regression |
| **Total** | **11 classes** | **36** | **10 fixtures** | |

## Summary

| Category | Coverage |
|----------|----------|
| Mandatory Gates (5) | 100% — each gate tested + ordering |
| Anti-Examples (7) | 100% — count + each scenario keyword |
| Quality Scorecard (3 tiers, 14 items) | 100% — tiers + all item IDs |
| Version/Platform Gate | 100% — PW versions, Node versions, frameworks |
| Output Contract (9 fields + JSON) | 100% — all fields + JSON format |
| Runner Strategy | 100% — dual-tool + bridge |
| Flaky Policy | 100% — sequence + categories |
| Reference Files (6) | 100% — existence + depth + content |
| Selective Loading | 100% — section + per-file conditions |
| Accessibility Testing | 100% — axe-core, WCAG, scoped, journey-integrated |
| Visual Regression | 100% — screenshot, masking, baselines, thresholds |
| Mobile/Desktop E2E | 100% — emulation, breakpoints, Electron, RN Web, geolocation |
| Discover Script | 100% — exists, executable, referenced, key checks |
| Golden Scenarios (10) | 100% — all fixtures tested |

## Known Gaps

1. **No LLM-in-the-loop testing** — all tests are structural; no actual Playwright code generation is validated.
2. **No cross-reference consistency test** — SKILL.md and reference files may diverge over time.
3. **discover_e2e_needs.sh not integration-tested** — script is checked for existence and content, not run against a real repo.
4. **Native mobile (iOS/Android)** — explicitly out of scope (Detox/Maestro), but not tested that skill correctly defers.
5. **Tauri desktop testing** — mentioned in platform matrix but no golden fixture.

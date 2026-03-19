# readme-generator Skill — Test Coverage Matrix

## Contract Tests (`test_skill_contract.py`)

| # | Class | Tests | Covers |
|---|-------|-------|--------|
| 1 | TestFrontmatter | 3 | Name, description keywords, description length |
| 2 | TestGates | 6 | 4 gates present, gate count ≥ 4, project types listed |
| 3 | TestAntiExamples | 4 | Section exists, BAD/GOOD count ≥ 7, topic coverage, markdown code blocks |
| 4 | TestScorecard | 8 | 3-Tier section, Critical/Standard/Hygiene tiers, items, output format |
| 5 | TestSelectiveLoading | 3 | Section exists, all refs listed, loading conditions |
| 6 | TestBadgeStrategy | 3 | Section, detection order, private-repo fallback |
| 7 | TestEvidenceMapping | 3 | Section, table format, Not found rule |
| 8 | TestLightweightMode | 3 | Section, trigger conditions, required sections |
| 9 | TestChineseBilingual | 3 | Section, keep-English rule, heading style |
| 10 | TestUpdateTriggers | 2 | Section, key triggers |
| 11 | TestTemplatesRef | 4 | File exists, 5 templates, depth ≥ 200, no verification status |
| 12 | TestGoldenExamplesRef | 7 | File, TOC, ≥ 5 examples, project types, evidence mappings, repo signals, depth |
| 13 | TestCommandPriorityRef | 6 | File, priority ladder, language patterns, conflict resolution, Makefile extraction, depth |
| 14 | TestChecklistRef | 6 | File, 3 phases, common mistakes by type, refactoring checklist, update triggers, depth |
| 15 | TestAgentsConfig | 2 | File exists, skill reference |
| 16 | TestStructuralIntegrity | 7 | Workflow steps, evidence targets, monorepo rules, navigation, E2E rule, output style, community files |
| 17 | TestOutputContract | 4 | Section exists, 9 mandatory fields, JSON format, field count |
| 18 | TestDiscoverScript | 7 | Script exists, executable, referenced in SKILL.md, in selective loading, in workflow, 10 dimensions, TSV output |
| 19 | TestVersionRules | 7 | Section exists, Go/Node/Python/Rust rules, How to Apply, depth ≥ 200 |
| 20 | TestDegradationPatterns | 5 | Section exists, 4 degradation levels, degraded in skill, depth ≥ 150, evidence column |
| 21 | TestCrossCuttingIntegrity | 3 | SKILL.md ≤ 600 lines, all refs exist, total content ≥ 1500 |

**Subtotal: 96 contract tests across 21 classes**

## Golden Scenario Tests (`test_golden_scenarios.py`)

| # | Class | Tests | Fixture | Covers |
|---|-------|-------|---------|--------|
| 1 | TestGoldenInfrastructure | 4 | all | Dir exists, ≥ 9 fixtures, valid JSON, project_type present |
| 2 | TestGoServiceFull | 5 | 001 | Template A, ≥ 8 sections, 4 badge types, rules fire, golden example |
| 3 | TestGoLibrary | 4 | 002 | Template B, Installation, API Overview, no-Makefile command priority |
| 4 | TestCLITool | 4 | 003 | Template C, E2E rule, Flags, Commands sections |
| 5 | TestMonorepo | 4 | 004 | Template D, Monorepo Rules, LICENSE missing note, overview table |
| 6 | TestLightweightInternal | 5 | 005 | Template E, Lightweight mode, no badges, absent sections, golden example |
| 7 | TestPrivateService | 3 | 006 | Badge fallback required, no external badges, private-repo rule |
| 8 | TestChineseReadme | 4 | 007 | Chinese language, ≥ 4 rules, guidelines in skill, no-double-heading |
| 9 | TestRefactorStale | 4 | 008 | Existing issues, expected actions, refactoring checklist, rules fire |
| 10 | TestDegradedNoBuild | 6 | 009 | Unknown type, degraded output, missing evidence, Evidence Gate, Output Contract |

**Subtotal: 43 golden tests across 10 classes (9 golden fixtures)**

## Coverage Summary

| Category | Items | Coverage |
|----------|-------|----------|
| Frontmatter | 3/3 | 100% |
| Gates (4 gates) | 6/6 | 100% |
| Anti-Examples (7 BAD/GOOD) | 4/4 | 100% |
| Scorecard (3-Tier, 14 items) | 8/8 | 100% |
| Selective Loading | 3/3 | 100% |
| Badge Strategy | 3/3 | 100% |
| Evidence Mapping | 3/3 | 100% |
| Lightweight Mode | 3/3 | 100% |
| Chinese/Bilingual | 3/3 | 100% |
| Update Triggers | 2/2 | 100% |
| Output Contract (9 fields + JSON) | 4/4 | 100% |
| Discover Script (10 dimensions) | 7/7 | 100% |
| Version Rules (4 languages) | 7/7 | 100% |
| Degradation Patterns (4 levels) | 5/5 | 100% |
| Templates Reference (5 types) | 4/4 | 100% |
| Golden Examples Reference (5 examples) | 7/7 | 100% |
| Command Priority Reference | 6/6 | 100% |
| Checklist Reference (3 phases + degradation) | 6/6 | 100% |
| Structural Integrity | 7/7 | 100% |
| Cross-Cutting Integrity | 3/3 | 100% |
| Golden Fixtures (9 scenarios) | 43/43 | 100% |

**Total: 139 tests (96 contract + 43 golden), 21 categories, all 100%**

## Known Gaps

1. No integration test for running discover script against a real repo and validating TSV output
2. No test for agents/openai.yaml prompt completeness (only checks skill reference exists)
3. Templates depth test uses line count, not structural validation of each template
4. Golden fixture 009 tests degradation concept but not actual degraded README generation

# Test Coverage Matrix

## Contract Tests (`test_skill_contract.py`)

Maps to the 10-item quality checklist from `skill最佳实践.md` Appendix C:

| # | Checklist Item | Test Class | Tests |
|---|---------------|------------|-------|
| 1 | `description` has trigger keywords | `TestDescription` | frontmatter, name, description, Chinese keywords (≥3), English keywords (≥3), allowed-tools |
| 2 | SKILL.md ≤ 500 lines | `TestSkillSize` | line count check |
| 3 | Mandatory gates | `TestMandatoryGates` | section exists, Gate 0–4, STOP-and-ASK count ≥2 |
| 4 | Anti-examples | `TestAntiExamples` | section exists, ≥8 numbered items |
| 5 | Reference loading conditions | `TestReferenceLoading` | section exists, each reference file mentioned, §Review Patterns linkage |
| 6 | Output contract | `TestOutputContract` | section exists, 8 structured field names, scorecard format, example block |
| 7 | Version/platform awareness | `TestVersionAwareness` | applicable_versions, metadata template |
| 8 | Degradation strategy | `TestDegradation` | section exists, 3 levels, labels (Full/Partial/Scaffold) |
| 9 | `allowed-tools` set | `TestAllowedTools` | frontmatter contains allowed-tools |
| 10 | Contract tests exist | `TestSelfValidation` | run_regression.sh referenced and exists |

## Domain-Specific Tests

| Dimension | Test Class | Tests |
|-----------|-----------|-------|
| Reference files | `TestReferenceFiles` | templates.md, writing-quality-guide.md, docs-as-code.md, TOC in templates, TOC in quality-guide |
| Golden infrastructure | `TestGoldenInfrastructure` | test file exists, golden dir exists, ≥6 fixtures |
| Template coverage | `TestTemplatesCoverage` | 5 doc types: task, concept, reference, troubleshooting, design |
| Quality guide sections | `TestQualityGuideSections` | §Funnel, §BAD/GOOD (≥3 each), §Code, §Visual, §Review |
| Quality scorecard tiers | `TestQualityScorecard` | 3 tiers, Critical ≥3 checks, Standard ≥4 checks |
| Execution modes | `TestExecutionModes` | Write, Review, Improve |
| Hard rules | `TestHardRules` | section exists, Reader-first, One-doc-one-job, Evidence-over-opinion |
| Doc type classification | `TestDocTypeClassification` | 5 types present in SKILL.md |
| Maintenance | `TestMaintenanceSection` | section, triggers, lifecycle statuses, cadence |

## Golden Scenario Tests (`test_golden_scenarios.py`)

| Fixture | Scenario | Verifies |
|---------|----------|----------|
| 001 | Write API deployment runbook | Task template, copy-paste-runnable, 5 min-viable sections, Gate 1-4 |
| 002 | Review troubleshooting doc | Review mode, Quality Scorecard, before/after fix, §Review Patterns |
| 003 | Mixed audience design doc | Funnel structure, Alternatives Comparison, Non-Goals, STOP-and-ASK |
| 004 | Audience unknown degradation | Degradation Level 2 (Partial), STOP-and-ASK trigger |
| 005 | Insufficient info scaffold | Degradation Level 3 (Scaffold), TODO placeholders, Gate 0 integrity |
| 006 | Improve existing doc | Improve mode, minimal-diff, preserve author voice, Scorecard |
| 007 | Repo has Chinese convention | Gate 1 repo scan, language adaptation, consistency rule |
| 008 | Doc with code examples | §Code Examples, self-contained, expected output, failure path |

Each fixture generates 4 test methods: keywords, gates, reference, mode — total 32 scenario tests + 3 integrity tests = 35.

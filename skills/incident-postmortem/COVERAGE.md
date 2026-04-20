# incident-postmortem Skill — Test Coverage Matrix

Coverage matrix for the incident-postmortem skill regression test suite.
Tests are zero-LLM: they validate SKILL.md structure and golden fixture integrity, not model behavior.

## Contract Tests (`test_skill_contract.py`)

| Test Class | Tests | Validates |
|------------|:-----:|-----------|
| `TestFrontmatter` | 3 | name=incident-postmortem; description triggers (post-mortem, timeline, root cause, blameless, action item, severity); allowed-tools |
| `TestMandatoryGates` | 6 | §2 exists; Gate 1-4 content; STOP semantics (>= 3); Draft/Review/Extract modes |
| `TestDepthSelection` | 5 | Quick/Standard/Deep; Standard default; Force conditions; 3 references mentioned |
| `TestDegradationModes` | 5 | 5 modes (Full/Partial/Sketch/Review/Planning); Can/Cannot columns; fabrication prohibition; degraded marker |
| `TestChecklist` | 7 | 5 subsections (5.1-5.5); timeline/RCA/impact/action/learning items; >= 18 numbered items |
| `TestSeverityClassification` | 3 | SEV-1 through SEV-4; SEV-1 criteria; SEV-1 requires deep |
| `TestAntiExamples` | 8 | AE-1 through AE-6; each by keyword; >= 6 WRONG/RIGHT pairs |
| `TestScorecard` | 5 | §8 exists; Critical 3 items; Standard 5 items; Hygiene 4 items; verdict format |
| `TestOutputContract` | 11 | §9.1-9.9; each section content; uncovered risks mandatory; scorecard appended |
| `TestReferenceFiles` | 9 | 3 files exist; SKILL.md references them; template has sections; RCA has 5-why + fishbone; severity has levels + SLO |
| `TestLineCount` | 1 | SKILL.md <= 420 lines |
| `TestCrossFileConsistency` | 16 | Shared terms (5-why, blameless, SEV-1, timeline, action items); min lines per reference; numeric thresholds (depth >= 3, detection gap < 5 min, SEV-1 > 30 min, SEV-2 > 15 min, 48-hour deadline); action categories in template; 5-Why stop criterion |

**Contract test count: 79**

## Golden Fixtures + Per-Fixture Test Classes (`test_golden_scenarios.py`)

### Fixture Inventory

| ID | Title | Type | Severity | Maps To |
|----|-------|------|----------|---------|
| PM-001 | Blame language as root cause | defect | critical | AE-1 + Gate 2 + Scorecard Critical #2 |
| PM-002 | Unsourced timeline, mixed formats | defect | critical | AE-2 + Scorecard Critical #1 |
| PM-003 | Action items without owners/deadlines | defect | critical | AE-3 + Scorecard Critical #3 |
| PM-004 | Shallow 5-Why stops at depth 2 | defect | standard | AE-4 + Scorecard Standard #5 |
| PM-005 | Vague impact, no metrics | defect | standard | Scorecard Standard #4 |
| PM-006 | Missing "what went well" | defect | standard | AE-5 + Scorecard Hygiene #9 |
| PM-007 | No tracking tickets for actions | defect | standard | AE-6 + Scorecard Hygiene #12 |
| PM-008 | Well-formed blameless post-mortem | good_practice | none | Positive exemplar |
| PM-009 | Well-executed 5-Why at depth 5 | good_practice | none | Positive exemplar (RCA) |
| PM-010 | Verbal description only | degradation_scenario | none | §4 Sketch mode |
| PM-011 | No incident, wants template | degradation_scenario | none | §4 Planning mode |
| PM-012 | Draft full post-mortem | workflow | none | Draft + Standard |
| PM-013 | Review existing post-mortem | workflow | none | Review mode |
| PM-014 | Recurring incident, prior action items incomplete | defect | standard | §5.5 item 18 + Scorecard Hygiene #11 |
| PM-015 | Cross-team SEV-1 with multi-service cascading failure | workflow | none | §3 Deep tier + §6 SEV-1 |
| PM-016 | Near-miss with real monitoring data and close-call evidence | workflow | none | §6 SEV-4 + rca-techniques near-miss framing |

### Per-Fixture Test Classes

| Class | Fixture | Tests | Validates |
|-------|---------|:-----:|-----------|
| `TestFixtureIntegrity` | all | 8 | count>=14; required fields; valid types/severities; unique IDs; coverage_rules findable |
| `TestPM001` | 001 | 3 | type=defect/critical; violated_rule contains blameless/systemic; feedback mentions reframe |
| `TestPM002` | 002 | 3 | type=defect/critical; violated_rule contains timeline; feedback mentions source |
| `TestPM003` | 003 | 3 | type=defect/critical; violated_rule contains owner/deadline; feedback mentions owner |
| `TestPM004` | 004 | 3 | type=defect/standard; violated_rule contains 5-why/depth; feedback mentions depth |
| `TestPM005` | 005 | 3 | type=defect/standard; violated_rule contains metric/impact; feedback mentions duration |
| `TestPM006` | 006 | 3 | type=defect/standard; violated_rule contains "went well"; feedback mentions blameless/positive |
| `TestPM007` | 007 | 3 | type=defect/standard; violated_rule contains tracking; feedback mentions jira/ticket |
| `TestPM008` | 008 | 3 | type=good_practice/none; feedback "no violation"; feedback mentions blameless |
| `TestPM009` | 009 | 3 | type=good_practice/none; feedback "no violation"; feedback mentions systemic |
| `TestPM010` | 010 | 3 | type=degradation/none; feedback mentions degraded; feedback forbids fabrication |
| `TestPM011` | 011 | 3 | type=degradation/none; feedback mentions template; feedback mentions gate 1/planning |
| `TestPM012` | 012 | 3 | type=workflow/none; feedback mentions timeline; feedback mentions 5-why |
| `TestPM013` | 013 | 3 | type=workflow/none; feedback mentions scorecard; feedback mentions "went well" |
| `TestPM014` | 014 | 3 | type=defect/standard; violated_rule contains related/linked; feedback mentions prior/previous incidents |
| `TestPM015` | 015 | 3 | type=workflow/none; feedback mentions deep; feedback mentions multi-team/cross-team |
| `TestPM016` | 016 | 3 | type=workflow/none; feedback mentions near-miss; feedback mentions SEV-4 |

**Golden test count: 56** (8 integrity + 48 behavioral)

## Coverage Summary

| Category | Covered | Total | Coverage |
|----------|:-------:|:-----:|:--------:|
| Mandatory Gates (§2) | 4/4 | 4 | 100% |
| Depth Tiers (§3) | 3/3 | 3 | 100% |
| Degradation Modes (§4) | 5/5 | 5 | 100% |
| Checklist Subsections (§5) | 5/5 | 5 | 100% |
| Checklist Items (§5) | 18/18 | 18 | 100% |
| Severity Levels (§6) | 4/4 | 4 | 100% |
| Anti-Examples (§7) | 6/6 | 6 | 100% |
| Scorecard Items (§8) | 12/12 | 12 | 100% |
| Output Contract Sections (§9) | 9/9 | 9 | 100% |
| Reference Files | 3/3 | 3 | 100% |
| Golden Fixture Types | 4/4 | 4 | 100% |
| Golden Severity Levels | 3/3 | 3 | 100% |

**Total tests: 135** (79 contract + 56 golden)

## Known Coverage Gaps

| Gap | Priority | Rationale |
|-----|----------|-----------|
| Fishbone/Ishikawa diagram fixture | Medium | references/rca-techniques.md §2 documents fishbone analysis but no fixture validates it as an alternative to 5-Why |
| Customer communication coordination fixture | Low | Out of scope per §1 but post-mortems often need to reference customer comms timing |
| Regulatory/compliance post-mortem fixture | Low | §3 Deep depth mentions regulatory requirement but no fixture exercises compliance-specific sections (data breach notification timelines, etc.) |
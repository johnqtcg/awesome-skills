# incident-postmortem Skill — Test Coverage Matrix

Coverage matrix for the incident-postmortem skill regression test suite.
The default suite (`bash scripts/run_regression.sh`) is zero-LLM and offline: it
validates SKILL.md structure, golden fixture integrity, and the actual behaviour of
`scripts/lint_postmortem.py` on real documents, including every golden fixture.

A separate **opt-in** layer measures the model itself — `scripts/run_live_eval.sh`
with `scripts/grade_postmortem_eval.py`. It is not part of the default run (CI has no
model), but its grader and its orchestrator are both covered by model-free tests here.

## Contract Tests (`test_skill_contract.py`)

| Test Class | Tests | Validates |
|------------|:-----:|-----------|
| `TestFrontmatter` | 3 | name=incident-postmortem; description triggers (post-mortem, timeline, root cause, blameless, action item, severity); allowed-tools |
| `TestMandatoryGates` | 6 | §2 exists; Gate 1-4 content; STOP semantics (>= 3); Draft/Review/Extract modes |
| `TestLanguageContract` | 5 | the language rule is declared, supported languages named, unsupported admitted, and both the linter and grader carry every alias they claim |
| `TestGate5SensitiveData` | 9 | Gate 5 exists; credential + customer-identifier classes; role substitution; Distribution/Redaction header; disclosure not waivable; STOP on credential; linter wiring; template header |
| `TestDepthSelection` | 5 | Quick/Standard/Deep; Standard default; Force conditions; 3 references mentioned |
| `TestDegradationModes` | 5 | 5 modes (Full/Partial/Sketch/Review/Planning); Can/Cannot columns; fabrication prohibition; degraded marker |
| `TestChecklist` | 9 | 5 subsections (5.1-5.5); timeline/RCA/impact/action/learning items; >= 18 numbered items; RCA technique chosen by causal shape (5-Why/fishbone/fault tree); jointly-necessary conditions allowed |
| `TestSeverityClassification` | 3 | SEV-1 through SEV-4; SEV-1 criteria; SEV-1 requires deep |
| `TestAntiExamples` | 8 | AE-1 through AE-6; each by keyword; >= 6 WRONG/RIGHT pairs |
| `TestScorecard` | 5 | §8 exists; Critical 3 items; Standard 5 items; Hygiene 4 items; verdict format |
| `TestOutputContract` | 11 | §9.1-9.9; each section content; uncovered risks mandatory; scorecard appended |
| `TestOutputContractByMode` | 10 | §9.0 matrix exists with 4 mode columns; blanket "every response" rule gone; 9.2+9.9 required in all modes; cells are Yes/—; Planning in Gate 3; Gate 1 routes to Planning; Gate 4 mode-aware |
| `TestOrgPolicyPrecedence` | 4 | org policy wins; thresholds labelled defaults; calibration limits admitted; severity reference defers too |
| `TestLinterContract` | 4 | `--mode` documented; all 3 entry formats documented; table/`TBD` cells documented; every advertised check emittable by the script |
| `TestCoverageDocAccuracy` | 2 | this file's declared total equals the count of `test_*` functions on disk; every test file is listed |
| `TestReferenceFiles` | 9 | 3 files exist; SKILL.md references them; template has sections; RCA has 5-why + fishbone; severity has levels + SLO |
| `TestLineCount` | 1 | SKILL.md <= 500 lines (repo second tier; see the test comment for what each raise bought) |
| `TestCrossFileConsistency` | 16 | Shared terms (5-why, blameless, SEV-1, timeline, action items); min lines per reference; numeric thresholds (depth >= 3, detection gap < 5 min, SEV-1 > 30 min, SEV-2 > 15 min, 48-hour deadline); action categories in template; 5-Why stop criterion |

**Contract test count: 126**

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
| `TestFixtureIntegrity` | all | 8 | count>=14; required fields (incl. `lint_expectation`); valid types/severities; unique IDs; coverage_rules findable |
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

**Golden test count: 68** (8 integrity + 48 per-fixture behavioral + 8 lint-expectation + 4 template worked example)

## Corpus ↔ Linter Wiring (`test_golden_scenarios.py`)

Every fixture declares a `lint_expectation`, verified against the real linter:

| Expectation | Meaning | Verified by |
|-------------|---------|-------------|
| `clean` | full document, linter reports zero findings | `test_clean_fixtures_are_actually_clean` |
| `flags:<check>` | linter must raise that specific check | `test_flags_fixtures_trigger_their_check` |
| `misses:<check>` | defect is real but outside the mechanical layer — documents the §8 judgment boundary | `test_misses_fixtures_document_the_judgment_boundary` |
| `not_a_document` | prompt or single-section excerpt; whole-document linting does not apply | `test_not_a_document_label_cannot_hide_a_broken_document` |

The `not_a_document` label is itself guarded: a snippet carrying both a Timeline and
an Action Items heading is a whole document and may not use it. That guard is in turn
tested against a real document and a real prompt, because an over-loose heading regex
read `# Document has timeline, root cause, action items` (prompt prose) as two
headings.

## Linter Behaviour (`test_lint_postmortem.py`)

| Class | Tests | Asserts |
|-------|:-----:|---------|
| `LintPostmortemTests` | 8 | list-form doc clean; unsourced entry, missing timeline, unowned action critical; category/section warnings; blame phrase; CLI exit codes |
| `TemplateFormatTests` | 3 | bare `HH:MM [PHASE]`, `- HH:MM`, and `\| HH:MM \|` entries all accepted |
| `ActionTableTests` | 11 | empty cells, `TBD`, missing Owner column, generic `@team`, empty section, `next quarter`, free-form non-date values in both table and list form; named team handles and checklist boxes not flagged |
| `TimelineQualityTests` | 11 | impossible clock time; out-of-order; single midnight wrap allowed; untimed entry surfaced; prose allowed; missing UTC; non-UTC named zone; `+00:00` accepted as UTC; duration range not a zone; mid-line parenthetical is not a source; table header not an entry |
| `UncoveredRisksTests` | 3 | missing, empty, and placeholder-only §9.9 all critical |
| `SensitiveDataTests` | 10 | AWS key, private key, inline password, JWT, Luhn-valid card critical; email and IP warnings; non-Luhn number, `***REDACTED***`, and `@handle` not flagged |
| `ModeGatingTests` | 12 | all four modes; unknown mode raises; per-mode filtering; §9.9 required in every mode incl. Planning; Review checks owner/deadline but not categories; `--mode` CLI |
| `UserPinnedFormatTests` | 6 | §9.0 precedence: a pinned artifact is not penalised for a missing spine, but content checks and the credential scan still apply; CLI flag; SKILL.md documents the rule |
| `DeepDepthTests` | 3 | `deep` is a valid depth, lints at standard strictness, and works from the CLI |
| `CategoryWaiverReasonTests` | 6 | bare `Mitigate: N/A` rejected; a 3+ word reason accepted; a 2-word reason too thin; table-cell waiver; an item merely containing "n/a" is still owner-checked |
| `ChineseDocumentTests` | 13 | a complete Chinese post-mortem lints clean; Chinese headings, full-width `（）` sources, 负责人/截止日期 columns, 预防/检测/缓解 categories, `2024年4月1日` dates, 待定 placeholders, CJK-weighted waiver reasons, Chinese blame phrases and 北京时间 as a non-UTC zone; the English path is unaffected |
| `SkillWiringGuards` | 1 | §8 wires the linter; frontmatter grants `Bash(*lint_postmortem.py*)` |
| `SectionResolutionTests` | 4 | an H1 title containing "Timeline"/"Action Items" no longer shadows the real H2 section; H1 fallback still parses when no H2 exists |
| `EmptyActionTableTests` | 3 | a header-only table is "no items" (critical) and exits non-zero; a table with a data row is not empty |
| `RedactionScopeTests` | 3 | a live key beside a redacted value is still caught; a fully redacted line stays clean; NUL substitution does not re-pair neighbours |
| `CategoryWaiverTests` | 5 | missing category warns; `Mitigate: N/A — <reason>` satisfies it; a waiver is not owner-checked; all-waived is still "no items"; bare category prose no longer counts |
| `QuickDepthTests` | 8 | standard depth rejects a Quick deliverable, `--depth quick` accepts it, and quick still lints present sections, §9.9 and credentials |

## Live Forward Evaluation (`test_forward_eval.py`, opt-in harness)

The one gap this file listed as High priority. `run_live_eval.sh` puts a scenario's
evidence in a temp workspace, installs the skill the way a user would, runs the model,
and grades the response deterministically — no second model judges the first.

| Scenario | Measures |
|----------|----------|
| `scenario_full_draft` | baseline: Draft/Standard, all nine sections, lint-clean, no invented revenue figure |
| `scenario_verbal_only` | honest degradation: `# DEGRADED:` marker, no fabricated to-the-minute timestamp, no fabricated evidence source, no definitive root cause |
| `scenario_no_incident` | Gate 1 routes to Planning; no invented incident ID or timeline |
| `scenario_quick_timeline` | Quick depth: timeline + 9.2 + 9.9, with Impact and What-Went-Well correctly omitted |
| `scenario_and_gated_failure` | RCA technique selection: three defenses failed together, so single-culprit framing is wrong |
| `scenario_secrets_in_evidence` | Gate 5: AWS key, customer email, card and IP in the evidence must not reach the write-up; SEV-1 so Deep is asserted |
| `scenario_strict_single_section` | §9.0 row 3: the user forbids all other text, so the spine is omitted and obedience is checked — adding a Mode line or a Risks heading is a failure. Four parallel conditions must not be forced through a linear 5-Why |
| `scenario_pinned_file_artifact` | §9.0 row 2: the artifact is a file but the chat message is free, so the spine belongs in the message — omitting it here IS a miss |
| `scenario_review_existing` | Review mode: a draft with three defects; improvement items need owner + deadline but not prevent/detect/mitigate; blame must be reframed, not repeated |
| `scenario_chinese_incident` | the user writes Chinese, so the post-mortem should be Chinese and must still lint clean |

| Class | Tests | Asserts |
|-------|:-----:|---------|
| `GraderAcceptsGoodOutput` | 2 | a compliant Draft passes every check |
| `GraderRejectsBadOutput` | 7 | each mutation fails the specific check it targets |
| `DegradationScenarioGrading` | 6 | honest sketch passes; marker/timestamp/source/definitive-cause failures caught; a hedged cause is still allowed |
| `PlanningScenarioGrading` | 3 | planning output passes; invented ID or timeline fails |
| `SecretsScenarioGrading` | 4 | redacted output passes; leaked key/email and a missing Gate 5 header fail |
| `ScenarioCorpusIntegrity` | 7 | scenario schema, IDs, known section keys, patterns compile, and the secrets scenario really contains the secrets it forbids |
| `RunnerIsExecutable` | 9 | the orchestrator is executed, not just its parts: parses, exits 2 on setup failure and empty response, 1 on failed grading, reaches every scenario, installs the skill in the with-skill arm only |
| `DeepDepthIsGradable` | 4 | a declared depth is compared verbatim; both SEV-1 scenarios assert Deep; declaring Standard on a Deep scenario fails; Deep still lints at standard strictness |
| `StrictFormatScenarioGrading` | 6 | a pinned single-section response passes; padding with extra sections fails; forcing 5-Why on parallel factors fails; dropping the prose spine fails |
| `InstalledSkillIsAnAllowList` | 5 | the installed skill contains only SKILL.md, references/*.md and lint_postmortem.py — no grader, runner, `__pycache__`, tests or scenarios; the runner aborts on any leak |
| `SpinePlacementTests` | 7 | §9.0's three placements: full obedience to "only X, no other text" passes; adding a Mode line or a Risks heading fails as disobedience; the prose-placement scenario still requires the spine |
| `ReviewScenarioGrading` | 4 | Review mode is exercised live; unowned improvement items fail; blame carried over from the draft fails; every mode has a scenario |
| `ChineseScenarioGrading` | 5 | a Chinese response passes; an English answer to a Chinese prompt fails; grader sections, definitive-cause and uncovered-prose matchers all work in Chinese |
| `CheckLevelAggregation` | 4 | the summary reports check counts, names per-scenario failed checks, `--diff` prints a net delta, and an empty result dir exits 2 |
| `RecordedRuns` | 3 | the results dir documents how to record; any committed summary is well-formed; with-skill must not fail more checks than baseline (skips until recorded) |
| `SkillDocumentsTheEval` | 2 | the harness is documented; `run_regression.sh` stays model-free |

Exit codes are load-bearing: **2 is a setup failure, never a skill result**. A missing
`INCIDENT_PM_EVAL_CMD`, an unauthenticated CLI or an empty response all exit 2, so a
broken harness can never be mistaken for a passing or failing skill.

Reporting a single arm is meaningless. Re-run with `INCIDENT_PM_EVAL_ARM=without-skill`
and compare: a skill that helps must fail strictly fewer checks than the bare model.

## Coverage Summary

| Category | Covered | Total | Coverage |
|----------|:-------:|:-----:|:--------:|
| Mandatory Gates (§2) | 5/5 | 5 | 100% |
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
| Output Contract Modes (§9.0) | 4/4 | 4 | 100% |
| Linter Checks | 12/12 | 12 | 100% |
| Golden Fixtures Wired to Linter | 16/16 | 16 | 100% |
| Eval Scenarios (modes covered) | 4/4 | 4 | 100% |
| Eval Scenarios (depths covered) | 3/3 | 3 | 100% (standard, quick, deep) |
| Languages exercised end-to-end | 2/2 | 2 | 100% (English, Chinese) |

**Total tests: 375** (126 contract + 68 golden + 110 linter + 71 forward-eval)

This number is not prose: `TestCoverageDocAccuracy` parses it out of this file and
compares it to the count of `test_*` functions actually defined under
`scripts/tests/`. It previously read 135 while the suite had grown to 144, and it caught this very edit — the claim
drifted for months because nothing checked it. It now cannot drift silently.

Coverage here means "a rule has at least one test referencing it". It is **not** a
claim of behavioural coverage of the model's output: no test in this suite invokes a
model. What the suite does verify end-to-end is the *mechanical* layer — the linter's
findings on real documents, and every golden fixture's declared lint expectation.

## Known Coverage Gaps

| Gap | Priority | Rationale |
|-----|----------|-----------|
| Live eval is opt-in, so CI does not run it | Medium | `run_live_eval.sh` closes the model-in-the-loop gap, but it needs an authenticated CLI and cannot run in the default suite. Its grader and orchestrator are covered by model-free tests; what is NOT continuously verified is the model's behaviour itself. Run it before releasing a change to the gates, the mode matrix or the degradation rules. |
| No recorded live run committed | High | `eval/results/` is empty. A nested `claude -p` prints "Not logged in" and returns nothing (runner exit 2 = nothing measured), so an agent inside a Claude Code session cannot produce one; a human with an authenticated shell can. `RecordedRuns` validates any committed summary and asserts with-skill ≤ baseline, and skips until then. Until it is filled, the behavioural claims rest on the grader's design, not on measurement. |
| Only English and Chinese are covered | Medium | The alias tables in `lint_postmortem.py` and `grade_postmortem_eval.py` handle those two. A Japanese or German post-mortem will mis-report missing sections exactly as Chinese did. Adding a language is one edit per file, but nothing currently detects the gap. |
| Prose-spine check is keyword-based | Low | With `user_pinned_format`, §9.9 moves out of the artifact and `UNCOVERED_PROSE_RE` looks for phrases like "did not analyze" / "out of scope". A response that states its gaps in wording outside that set reads as a failure. It is deliberately narrow: the alternative is a model judging a model. |
| Grader cannot judge RCA *quality* | Medium | It verifies that a technique is named, that single-culprit framing is absent where the incident is AND-gated, and that the structure exists — not whether the causal reasoning is sound. That stays a human judgment, as §8 says. |
| Fishbone/Ishikawa diagram fixture | Medium | `references/rca-techniques.md` §0 now routes to fishbone by causal shape and §2 documents it, but no fixture exercises a non-5-Why technique end-to-end |
| Blame detection is phrase-based | Medium | `blame-language` catches constructions that are blame by definition ("operator error"). It cannot detect naming an individual as the cause — PM-001 is labelled `misses:blame-language` to record exactly that boundary. Closing it needs either a participant-name list or a model. |
| Numeric UTC offsets not checked | Low | `NON_UTC_ZONE_RE` matches named zones only. A `[+-]HH:MM` alternative was implemented and removed: it cannot be distinguished from a duration range (`14:23-15:10`) and false-positived on valid timelines. A timeline that declares UTC but carries a `+05:30` entry is therefore not flagged. |
| Timeline chronology allows one wrap | Low | Without ISO dates, a single decreasing timestamp is treated as crossing midnight. A genuinely mis-ordered pair inside one day is therefore missed once per document; the second is flagged. Using full ISO datetimes removes the ambiguity. |
| Customer communication coordination fixture | Low | Out of scope per §1 but post-mortems often need to reference customer comms timing |
| Regulatory/compliance post-mortem fixture | Low | §3 Deep depth mentions regulatory requirement but no fixture exercises compliance-specific sections (data breach notification timelines, etc.) |
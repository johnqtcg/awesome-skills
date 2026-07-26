# Test Coverage Matrix

## Contract Tests (`test_skill_contract.py`)

Maps to the 10-item quality checklist from `skill最佳实践.md` Appendix C:

| # | Checklist Item | Test Class | Tests |
|---|---------------|------------|-------|
| 1 | `description` has trigger keywords | `TestDescription` | frontmatter, name, description, Chinese keywords (≥3), English keywords (≥3), allowed-tools |
| 2 | SKILL.md ≤ 500 lines | `TestSkillSize` | line count check |
| 3 | Mandatory gates | `TestMandatoryGates` | section exists, Gates **0–3** (0 is Execution Integrity), Resolution Order (R1→R2→R3) |
| 4 | Anti-examples | `TestAntiExamples` | section exists, ≥8 numbered items |
| 5 | Reference loading conditions | `TestReferenceLoading` | section exists, each reference file mentioned, §Review Patterns linkage |
| 6 | Output contract | `TestOutputContract` | section exists, field names **derived from the contract block** (9, incl. `resolution:`) rather than hardcoded, worked example instantiates every declared field, scorecard format |
| 7 | Version/platform awareness | `TestVersionAwareness` | applicable_versions, metadata template |
| 8 | Degradation strategy | `TestDegradation` | section exists, 3 levels, labels (Full/Partial/Scaffold) |
| 9 | `allowed-tools` set | `TestAllowedTools` | present (repo convention: 43/51 skills), every granted **name is a real tool**, no duplicate grants |
| 10 | Contract tests exist | `TestSelfValidation` | run_regression.sh referenced and exists |

## Domain-Specific Tests

| Dimension | Test Class | Tests |
|-----------|-----------|-------|
| Reference files | `TestReferenceFiles` | templates.md, writing-quality-guide.md, docs-as-code.md, TOC in templates, TOC in quality-guide |
| Golden infrastructure | `TestGoldenInfrastructure` | test file exists, golden dir exists, ≥6 fixtures |
| Template coverage | `TestTemplatesCoverage` | 5 doc types: task, concept, reference, troubleshooting, design |
| Quality guide sections | `TestQualityGuideSections` | §Funnel, §BAD/GOOD (≥3 each), §Code, §Visual, §Review |
| Quality scorecard tiers | `TestQualityScorecard` | 3 tiers; thresholds are **⅔ of applicable**, not a fixed `n/total` (a fixed count was unpassable for concept/reference/design, which have only 2/3/2 applicable Standard items); N/A leaves the denominator; `lint_doc.SCORECARD` item counts match SKILL.md per tier |
| Execution modes | `TestExecutionModes` | Write, Review, Improve |
| Hard rules | `TestHardRules` | section exists, Reader-first, One-doc-one-job, Evidence-over-opinion |
| Doc type classification | `TestDocTypeClassification` | 5 types present in SKILL.md |
| Maintenance | `TestMaintenanceSection` | section, triggers, lifecycle statuses, cadence |

## Linter Behavioral Tests (`test_lint_doc.py`)

| Area | Tests |
|------|-------|
| Clean document | good doc produces zero findings |
| Metadata (critical) | missing title/owner/status/last_updated, invalid status value, non-ISO date, **calendar-invalid date** (`2026-99-99` used to pass), unclosed code fence, `applicable_versions` required when the body pins a version, YAML trailing comments |
| Tables | TBD cell critical for `--type reference` / warning for task, empty cell detected, **wholly blank row** detected (the separator-row skip used `^\s*\|[\s:|-]+\|\s*$`, which also matches `\|  \|  \|` — so a table of empty rows passed the Critical check it exists to enforce; separator detection is now cell-by-cell) |
| Headings | title **weight** budget (CJK 1.0 / Latin 0.5, leading `RFC-042:` exempt), filler rejected at any length, multiple H1 warned, H1 inside fence not counted |
| Code fences | untagged fence warned |
| Pangu spacing | violation detected with line number; inline code + fenced blocks exempt; **CJK-slash regression** (`读/写` prose must not mask violations — URL_RE was `\w`-based and Python `\w` matches CJK); real paths/URLs still exempt |
| CLI contract | exit 0 clean / 1 critical / 1 with `--strict` on warnings / 2 unreadable file |

## Golden Scenario Tests (`test_golden_scenarios.py`)

| Fixture | Scenario | Verifies |
|---------|----------|----------|
| 001 | Write API deployment runbook | Task template, copy-paste-runnable, 5 min-viable sections, Gates 0–3 |
| 002 | Review troubleshooting doc | Review mode, Quality Scorecard, before/after fix, §Review Patterns |
| 003 | Mixed audience design doc | Funnel structure, Alternatives Comparison, Non-Goals, STOP-and-ASK |
| 004 | Audience unknown degradation | Degradation Level 2 (Partial), STOP-and-ASK trigger |
| 005 | Insufficient info scaffold | Degradation Level 3 (Scaffold), TODO placeholders, Gate 0 integrity |
| 006 | Improve existing doc | Improve mode, minimal-diff, preserve author voice, Scorecard |
| 007 | Repo has Chinese convention | Gate 1 repo scan, language adaptation, consistency rule |
| 008 | Doc with code examples | §Code Examples, self-contained, expected output, failure path |

Each fixture generates 4 test methods: keywords, gates, reference, mode — plus fixture-integrity tests.

> **What this layer can and cannot show.** These tests assert that each fixture's
> `skill_must_contain` strings appear somewhere in SKILL.md + references. That proves the rules
> are **written down** and catches deletion or renaming — genuinely useful drift protection. It
> cannot show that following the skill *produces* a compliant document: a keyword check passes
> whether or not the classification, degradation level, or scorecard arithmetic is right. The
> forward-eval layer below covers that.

## Forward Eval (`test_forward_eval.py`)

Grades a produced **document**, not the skill text. `grade(output, fixture)` checks: declared
mode, doc-type classification, the `Resolution: R1|R2|R3` path and degradation level, the
reference actually cited, scorecard **arithmetic** (`N/M applicable`, not a bare verdict), and
then runs `lint_doc.py` over the emitted markdown. Improve mode additionally measures the
unified-diff size against the fixture's `max_changed_lines`, so a full rewrite fails even when
the rewritten document is itself good.

| Scenario | Fixture | Failure it detects |
|---|---|---|
| `runbook_write` | 001 | emitted doc fails the mechanical gate; wrong doc type; fabricated scorecard arithmetic |
| `audience_unknown` | 004 | no resolution path recorded; Level 2 without a labelled assumption |
| `improve_minimal_diff` | 006 | rewriting instead of fixing what the scorecard flagged; reformatting content marked already-correct |
| `review_troubleshooting` | 002 | findings not grouped by severity; no before/after evidence |
| `scaffold_level3` | 005 | fabricating concrete values instead of TODO placeholders |

**Document extraction.** Responses delimit the document with `<!-- BEGIN DOCUMENT -->` /
`<!-- END DOCUMENT -->`. A non-greedy ```` ```markdown ```` match was used first and stopped at
the document's **first inner fence** — a runbook full of ```bash blocks was truncated 94 lines
to 25, so Rollback and Verification never reached the linter while the layer claimed to gate the
whole document.

Each scenario ships `good.md` (must pass) and `bad.md` (must fail), and a test asserts each bad
exemplar fails for its **intended** reason — one failing on an incidental technicality would prove
nothing. Mutation tests confirm the grader is not a rubber stamp: fabricated arithmetic
(`99/99 applicable` used to pass), a PASS below the ⅔ threshold, a missing tier, a wrong doc type,
truncation past an inner fence, and a rewrite that reformats a command marked already-correct.

**Denominators are facts, not ranges.** Conditional scorecard items (`when diagrams present`,
`when version-sensitive`, `api doc`) are resolved by inspecting the graded document, so the
claimed denominator is compared to one number. Checking only a permitted `min..max` span accepted
both `2/2 applicable` and `2/3 applicable` for the *same* concept document — it could not tell
whether a conditional item genuinely applied.

## Live Harness (`LiveForwardEval` + `stub_writer.py`)

`LiveForwardEval` **offers** the references rather than pre-loading them: the prompt lists the
files and a `LOAD: references/<name>` protocol, and only what the model asks for is supplied.
Attaching everything made the progressive-disclosure rule untestable — the model could not fail
to "load only what it needs". It is **skipped unless `TECH_DOC_EVAL_CMD` is set.**

Because it was skipped by default it had never once executed, and `LiveHarnessPlumbingTest` now
runs it against `stub_writer.py` on every run. Three stub modes, all asserted:

| `STUB_MODE` | Stub behaviour | Expected |
|---|---|---|
| _(unset)_ | request the pinned reference, then replay `good.md` | harness passes |
| `bad` | replay `bad.md` | harness fails all 5 — proves it can fail |
| `no_load` | never send `LOAD:`, answer anyway | fails exactly the 2 fixtures that pin a reference |

That third mode found a real defect: the reference check tested `ref not in output`, i.e. that the
response *mentions* the path. A stub that skipped the protocol entirely and emitted the known-good
exemplar still passed, because the exemplar's own prose names the reference — while the harness
docstring claimed the opposite. The set of files actually requested is now threaded into `grade`,
so citing a file that was never supplied fails as an unverified citation.

**The boundary this does not cross.** The stub replays a stored document instead of writing one.
The plumbing is proven — prompt assembly, the second turn, the hand-off into `grade` — and so is
the grader's ability to discriminate. Neither proves that a live model passes; only
`TECH_DOC_EVAL_CMD` pointed at a real model measures that, and it has not been run here.

## Template Lint (`test_templates_lint.py`)

Every ```markdown template in `references/templates.md` is extracted, its placeholders filled the
way a user would fill them, and run through `lint_doc.py`.

Why: the templates are the most-copied artefact here, and **none of them carried the frontmatter
that Gate 3 marks Critical** — copying any template produced a document that failed the skill's
own mandatory metadata check. Nothing caught it because no test had ever linted a template.
Also pinned: the troubleshooting template has an H1 (it began at `### Incident`), no template
restates frontmatter in a body `## Metadata` section, the design template keeps `decision_status`
separate from the document `status` vocabulary, and YAML trailing comments parse correctly.

**Extraction has to reach the end of each template.** The first extractor treated any ``` as a
closer, so the Reference template's inner ```` ```http ```` block ended the outer fence after 22
lines and its error-code, compatibility, and changelog sections were never linted — while the
test name claimed full coverage. The templates now open with four backticks so triple-backtick
blocks nest legally, extraction follows the CommonMark rule (a fence closes only on ≥ as many
backticks with no info string), and a test asserts each template reaches its own final section.

## Test Layers

| Layer | File | Proves | Blind to |
|---|---|---|---|
| Contract | `test_skill_contract.py` | the rules are present and self-consistent | whether following them works |
| Linter unit | `test_lint_doc.py` | each mechanical check behaves | document quality overall |
| Template lint | `test_templates_lint.py` | the shipped skeletons pass the skill's own gate | prose quality |
| Golden keywords | `test_golden_scenarios.py` | rules exist for each scenario (drift protection) | the produced document |
| **Forward eval** | `test_forward_eval.py` | a graded **document**: type, resolution path, scorecard **arithmetic**, `lint_doc.py` over the emitted markdown, minimal-diff, severity grouping, scaffold integrity | that a *live* model passes — needs the opt-in hook |
| Live plumbing | `stub_writer.py` via `LiveHarnessPlumbingTest` | the live path runs end to end, honours `LOAD:` on a second turn, and still **fails** on bad input | model behaviour — the stub replays a stored document |

Counts drift, so they are not restated here; `run_regression.sh` reports the live totals and
distinguishes **PASS**, **PASS WITH SKIPS** (e.g. `TECH_DOC_EVAL_CMD` unset), and **FAIL**.

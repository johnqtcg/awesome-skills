---
name: tech-doc-writer
description: >
  Write, review, and improve technical documents (技术文档, 设计文档, 操作手册,
  故障报告, API文档). Use when users ask to write/draft/review/improve a
  technical document, create an RFC/ADR, write a runbook or operation guide,
  produce API docs, or create any structured technical writing deliverable.
  Audience-aware, evidence-based, with quality gates, a mechanical linter, and
  staleness detection (age against review cadence, not merely a date field).
  Supports concept docs, task docs, reference docs, troubleshooting docs, and
  design docs (RFC/ADR).
allowed-tools: Read, Write, Edit, Grep, Glob, Bash(git log*), Bash(git diff*), Bash(git show*), Bash(go vet*), Bash(go build*), Bash(go test*), Bash(make -n*), Bash(kubectl explain*), Bash(helm template*), Bash(terraform validate*), Bash(docker compose config*), Bash(*lint_doc.py*)
---

# Tech Doc Writer

## Quick Reference

| If you need to… | Go to |
|---|---|
| Write a new document from scratch | §Execution Modes → Write + §Workflow (Phases 0→5) |
| Review an existing document for quality | §Execution Modes → Review + §Quality Scorecard |
| Improve / refactor an existing document | §Execution Modes → Improve (minimal-diff) |
| Choose the right document type and template | §Gate 2: Classify Type and Audience + Load `references/templates.md` |
| Write for a mixed audience (execs + engineers) | Load `references/writing-quality-guide.md` §Funnel Structure |
| Include code examples or CLI commands | Load `references/writing-quality-guide.md` §Code Examples |
| Find and fix common doc mistakes (12 anti-patterns) | Load `references/writing-quality-guide.md` §Anti-Examples |
| Set up doc CI / PR templates / auto-generation | Load `references/docs-as-code.md` |

## Execution Modes

### Write (new document from scratch)

- Full document generated from audience analysis and type classification.
- Use templates from [templates.md](references/templates.md) as starting points.
- Requires Phase 0–5 of the workflow.

### Review (evaluate existing document)

- Read the full document first.
- Classify its type, then run the Quality Scorecard.
- Report findings grouped by severity (Critical / Major / Minor).
- Provide concrete before/after fixes, not vague suggestions.

### Improve (refactor existing document)

- Minimal-diff edits — change only what the scorecard flags; do not rewrite sections that already pass.
- Preserve the author's voice and existing structure where they work.

## Mandatory Gates

Gates are serial. Each must pass before the next. If a gate cannot be executed, apply the Degradation Strategy.

### Gate 0: Execution Integrity

- Never fabricate document content that claims to be from the codebase (commands, configs, API parameters) without verifying it actually exists.
- Never claim you verified a command is runnable unless you actually executed it.
- Every command in a delivered document carries a **verification level** (below). Unlabelled commands are treated as V3.

#### The Verification Ladder

This skill documents runbooks for stacks it cannot execute — `kubectl`, `docker`, `npm`,
`psql`, `terraform apply`. Only read-only and dry-run probes are granted (see
`allowed-tools`), so "the command was executed" is not achievable for most task docs. Two
different properties were previously conflated under one Critical item, which made the top
quality tier unreachable by construction for exactly the documents this skill exists to write.
They are now separate:

| Level | Meaning | How it is established |
|---|---|---|
| **V1 executed** | Ran it; the pasted output is real | A granted read-only/dry-run probe, or output the user supplied |
| **V2 sourced** | Traced to a checked-in artefact | `Grep`/`Read` a Makefile target, CI workflow, deploy script, or existing runbook — **cite the file and line** |
| **V3 unverified** | Neither | Must carry `<!-- UNVERIFIED: <what could not be checked> -->` |

- **Form is always required, at every level**: no unfilled `<placeholders>`, no shell-fragile
  quoting, one logical command per block, expected output shown. This is what the Critical
  scorecard item asks for, and it is achievable regardless of tool permissions.
- **Provenance is reported, never assumed.** State the level per command block, or once per
  section when uniform. A V2 command without a citation is V3.
- **Escalation when V1 is genuinely required** (a destructive step, an unfamiliar flag, a
  version-specific behaviour): ask the user to run it and paste the output, or to grant the
  specific command. Do not silently downgrade to V3 and present the doc as complete.
- Never upgrade a level because the command "obviously works".

### Gate 1: Repo Context Scan

Before writing, quickly scan for existing doc conventions (`docs/`, `CONTRIBUTING.md`, `.markdownlint.json`, `.vale.ini`, `.techdocrc.json`). Adapt to what exists — consistency with the repo trumps this skill's defaults. If conflicting conventions are found → **STOP and ASK** which to follow.

**Record the convention, do not just obey it.** Where the repo's metadata differs from this
skill's default — metadata at the foot of the page, `maintainer:` instead of `owner:`, a
`published`/`archived` status vocabulary, no frontmatter permitted at all — write a
`.techdocrc.json` so the linter enforces *the repository's* schema. Otherwise Gate 1 concedes
the point and Phase 4 immediately contradicts it by reporting every local field as missing.
`python3 scripts/lint_doc.py <file> --print-config` prints the schema and the effective merge.

### Gate 2: Classify Type and Audience

Classify the document **and** its audience before writing anything:

| Reader's Goal | Document Type | Core Question |
|---------------|--------------|---------------|
| Understand a concept | Concept doc | What is it? Why? When to use? |
| Complete an operation | Task doc (runbook) | How? How to verify? How to rollback? |
| Look up a parameter | Reference doc | Fields, types, defaults, constraints? |
| Diagnose a failure | Troubleshooting doc | What happened? Why? How to fix/prevent? |
| Record a decision | Design doc (RFC/ADR) | Why this approach? What was rejected? |

If the user's request maps to multiple types, apply the **dominant-purpose rule** before
escalating: when one reader goal clearly carries the document, write that type and cross-link
the secondary material (a runbook may carry a short "why this works" preamble without becoming
a concept doc). Only when two purposes are genuinely co-equal — neither is subordinate, and
splitting would break either one — → **STOP and ASK**. Record the classification and, if you
applied the dominant-purpose rule, which purpose you subordinated.

**Audience** — state explicitly: (1) who is the reader, (2) what must they do, (3) what do they already know. Mixed audience → use funnel structure (Executive Summary → Overview → Technical Detail → Appendix); load [writing-quality-guide.md §Funnel Structure](references/writing-quality-guide.md) for the pattern.

When the audience is **not** stated, follow §Resolution Order below — do not choose between
asking and assuming ad hoc.

### Gate 3: Quality Scorecard

Run after writing/reviewing. Results must be reported in the output.

**Scoring rule (read before scoring).** Each item carries an applicability tag: `[all]`, a list
of doc types, or `[..., when X]`. Score like this:

1. **Determine applicability first.** An item is `N/A` when its tag excludes this doc type, or
   when its `when` condition does not hold. Resolve each condition **from the document you
   produced**, by the same rule the tooling uses — not from intent:

   | Condition | Holds when the document… |
   |---|---|
   | `diagrams present` | contains a Mermaid block, an embedded image, or a numbered figure |
   | `version-sensitive` | **the body** pins a concrete version (`Redis 7.2.1`, `Go 1.24`). Filling `applicable_versions` does not by itself make the item applicable — a live run counted it as applicable on that basis and over-stated its denominator by one |
   | `api doc` | documents HTTP statuses or a machine-readable error-code column |
   | `a related doc exists` | n/a — this item is unconditional; declaring the document standalone satisfies it |
2. **`N/A` items leave the denominator.** The threshold is a ratio of *applicable* items, not a
   fixed count: the Standard and Hygiene tiers each need **≥ ⅔ of their applicable items**,
   rounded up.
3. **A tier with 0 applicable items passes trivially** — record `Standard: n/a (0 applicable)`.
4. **Critical is per-item, not a ratio**: every *applicable* Critical item must pass. An `N/A`
   Critical item is not a failure.
5. **Report the arithmetic**, not just a verdict: `Standard: 2/2 applicable (4 N/A) → PASS`.

Why a ratio and not `≥ 4/6`: with a fixed count the tier was **unpassable** for three of the
five doc types — a Concept doc has only 2 applicable Standard items, Reference 3, Design 2, so
`≥ 4/6` could never be met no matter how good the document was. `scripts/lint_doc.py --type <t>`
prints the applicable counts so the denominator is not guessed.

**Critical (any FAIL → document not deliverable)**
- [ ] Commands are copy-paste-runnable **in form** and each carries a verification level (Gate 0); no V3 command is presented as verified [task, troubleshooting] or code is marked as snippet [concept]
- [ ] Every key step has expected output and verification [task, troubleshooting]
- [ ] Document has metadata: owner + last_updated + status [all]
- [ ] Terminology is consistent **after first definition** — a term may be introduced once as `中文（English）` or `English (中文)`, and one form is used thereafter [all]
- [ ] Parameter/field tables complete — Type, Required, Default, Description columns all present and filled; no empty cells or `TBD` [reference]

**Standard (≥ ⅔ of applicable items, rounded up)**
- [ ] Conclusion/core message appears in the first paragraph, not buried at the end [all — especially troubleshooting: root cause upfront]
- [ ] Prerequisites are complete: permissions, environment, dependencies, inputs [task, troubleshooting]
- [ ] Rollback/failure path documented with trigger conditions [task]
- [ ] Title follows SPA principle (Simple — within the weight budget and filler-free, Profit, Accurate) [all]
- [ ] Code examples are self-contained with imports, not just fragments [task, troubleshooting, reference]
- [ ] Error codes / status codes documented with trigger conditions and recommended actions [reference, when API doc]

**Hygiene (≥ ⅔ of applicable items, rounded up)**
- [ ] Diagrams have title, legend, and terms consistent with prose [all, when diagrams present]
- [ ] Cross-references to related docs — or an explicit note that this document is standalone [all]
- [ ] 80%+ of information carried in lists or tables [reference, task, troubleshooting]
- [ ] Paragraphs stay scannable: none longer than ~8 lines, every multi-item enumeration is a list [concept, design]
- [ ] `applicable_versions` field present [all, when version-sensitive]
- [ ] Maintenance trigger conditions noted (when must this doc be updated?) [task, troubleshooting]
- [ ] Prevention section with quantifiable monitoring/alerting thresholds [troubleshooting]

Critical failures block delivery. Record scorecard results in output.

Two items were absolutes that no design doc could satisfy: **80 % structured information** suits
a reference or runbook and harms an argument carried in prose, so it is type-scoped and paired
with a scannability item; **zero synonym mixing** is now consistency *after* first definition, so
a bilingual doc may name a thing once in both languages. Both are mirrored in
`lint_doc.SCORECARD`; a contract test fails if the two drift.

## Degradation Strategy

### Resolution Order (deterministic — do not reorder)

Ambiguity is resolved by this sequence, not by preference. **Retrieve → Ask → Assume.**
Each step runs only if the previous one failed.

| Step | Do | Then |
|---|---|---|
| **R1. Retrieve** | If a repo/doc corpus exists, search it: existing docs' stated audience, README, `CONTRIBUTING`, ADRs, the callers of the code being documented. One focused round, not exhaustive. | Resolved → **Level 1**. Unresolved → R2 |
| **R2. Ask** | Ask **one** consolidated question naming the specific missing facts (audience / type / scope) and the options you inferred. Ask once — not one question per gap. | Answered → **Level 1**. Cannot ask, or unanswered → R3 |
| **R3. Assume** | Proceed on an explicit, labelled assumption. | → **Level 2** (audience) or **Level 3** (content) |

**"Cannot ask" means exactly one of:** the user pre-authorised assumptions ("just draft it",
"don't ask, use your judgement"), the run is non-interactive (batch/CI/scheduled), or the user
already declined to specify. **Absence of a reply inside one turn is not "cannot ask"** — if you
have asked, wait; do not ask and then answer yourself in the same turn.

So the earlier rule "unclear audience → STOP and ASK" is **R2**, and Level 2 is **R3**. They are
sequential states, never alternatives. Recording which step resolved it is mandatory (see below).

| Level | Condition | Behavior |
|-------|-----------|----------|
| **Level 1: Full** | Audience, type, and repo context clear — natively or via R1/R2 | Complete document + all gates pass |
| **Level 2: Partial** | Type clear, audience unresolved **after R1 and R2** | Write for the broadest reasonable audience; mark `<!-- AUDIENCE: assumed ... -->` at top; note in output |
| **Level 3: Scaffold** | Content still insufficient after R1 and R2 | Skeleton with section headings + `<!-- TODO: ... -->` placeholders; list what was searched and not found; ask the user to fill gaps |

Every response must state the resolution path, e.g.
`Resolution: R1 retrieved (CONTRIBUTING.md names SRE as reader) → Level 1` or
`Resolution: R1 found nothing, R2 not possible (non-interactive) → Level 2, audience assumed`.

Never present Level 2/3 output as if it were Level 1. If no corpus exists at all (greenfield,
standalone doc), R1 is a no-op — say so and go straight to R2.

## Workflow

### Phase 0: Repo Context Scan (Gate 1)
Scan repository for existing doc conventions. Adapt or ask.

### Phase 1: Classify and Analyze Audience (Gate 2)
Determine type, audience, knowledge gap. State these explicitly.

### Phase 2: Structure

- **Conclusion first**: lead with the core message. Do not bury it.
- **Group by category**: related info under the same heading.
- **Logical progression**: cause→effect, time-order, or importance-order.

Build the skeleton using the appropriate template from [templates.md](references/templates.md).

### Phase 3: Write

Apply these rules while writing:

**Minimal writing**
- Same concept → same term. Never alternate "集群" and "cluster" in one doc.
- Delete filler: "其实", "就是说", "我们需要做的是" → cut.
- Provide signposts: section summaries, TOC for docs > 3 screens, cross-references.

**Code examples** — load [writing-quality-guide.md §Code Examples](references/writing-quality-guide.md) for full patterns:
- Task docs: commands must be copy-paste-runnable with expected output.
- Concept docs: mark simplified examples explicitly.
- All code: self-contained (includes imports), comments explain WHY not WHAT, show failure path.

**Visual expression**:
- Consider a diagram when 3+ components interact, or for state transitions and sequential
  interactions. This is a prompt to consider, not a quota: prose is the better choice when the
  interaction is linear (A calls B calls C) or when the components are named once and never
  referenced again. A diagram that restates a single sentence costs maintenance and pays nothing.
- Prefer Mermaid (GitHub/GitLab native) or ASCII art (diffable).
- **Mermaid complexity limit**: Keep diagrams ≤ 15 nodes. If logic requires more, split into multiple sub-diagrams with cross-references. Overly complex Mermaid frequently fails to render.
- Every diagram: title + legend + naming consistent with prose.

**Title — SPA Principle**:
- **S**imple: no filler words, and within the **language-aware weight budget** below
- **P**rofit: what does the reader gain?
- **A**ccurate: no exaggeration, no ambiguity

*Simple* is not a raw character count. A flat "≤ 20 characters" is not comparable across
scripts — 20 Chinese characters carry roughly a sentence, 20 Latin characters barely three
words — and it wrongly penalised the RFC/ADR titles this skill itself recommends. The budget is:

| Element | Weight |
|---|---|
| CJK character | 1.0 |
| Latin letter / digit | 0.5 |
| Punctuation, spaces | 0 |
| Leading identifier (`RFC-042:`, `ADR-7:`, `[JIRA-1234]`) | **exempt** — it aids search, it is not padding |

Budget: **20 weight units** — about 20 CJK characters or 40 Latin characters of content.
Filler is judged separately and is never acceptable at any length: articles, and openers like
*Comprehensive / Introduction to / Overview of / Notes on / 关于 / 简介 / 详解 / 浅谈*.

`scripts/lint_doc.py` implements exactly this (`title-weight`), so the rule and the checker
cannot drift apart. `RFC-042: Migrate to Event-Driven Architecture` passes; *A Comprehensive
Introduction to the Cache* fails on filler.

| Doc Type | Title Pattern | Example |
|----------|--------------|---------|
| Concept | Noun + Noun | Connection Pool Internals |
| Task | Verb + Object | Deploy Redis Cluster |
| Reference | Noun + Noun | API Parameter Reference |
| Troubleshooting | Noun: Noun | MySQL: Deadlock Under High Concurrency |
| Design | RFC-NNN: Verb + Object | RFC-042: Migrate to Event-Driven Architecture |

### Phase 4: Quality Gate (Gate 3)

Run the scorecard in two layers:

1. **Mechanical layer** — run the bundled linter on every produced or modified document:
   ```bash
   python3 scripts/lint_doc.py <file.md> --type <doc_type>
   ```
   It deterministically checks the regex-decidable scorecard subset:

   | Check | Severity | What it decides |
   |---|---|---|
   | `metadata` / `status-value` / `date-format` | critical | required fields present, status in vocabulary, date a real calendar date |
   | `fence-balance` | critical | no unclosed fence (an unclosed one blinds every later check) |
   | `table-cells` | critical for `reference` | no `TBD` or empty cells |
   | `table-columns` | critical for `reference` | a parameter table actually declares Type / Required / Default / Description |
   | `staleness` | warning | age measured against the declared `review_cadence`, or the 365-day default; future dates flagged |
   | `maintenance` | warning | a task/troubleshooting doc says when it must be revised |
   | `title-h1-match` | warning | metadata `title` and the H1 name the same document |
   | `single-h1` / `title-weight` | warning | one H1, within the weight budget, filler-free |
   | `code-fence-lang` | warning | every fence carries a language tag (` ``` ` and `~~~`) |
   | `pangu-spacing` | warning | **exactly** one space between CJK and Latin — zero and two both fail |
   | `applicable-versions` | warning | declared when the body pins a version |

   Critical lint failures block delivery, same as scorecard Critical items. Add `--scorecard`
   for the computed denominators, `--today YYYY-MM-DD` to pin the staleness reference date, and
   `--config`/`.techdocrc.json` to enforce the repository's own conventions (Gate 1).
2. **Judgment layer** — evaluate the remaining scorecard items (conclusion-first, terminology consistency, prerequisites completeness, verification levels) by reading the document.

Fix Critical failures from either layer before delivering. The mechanical layer is a floor, not
a proof: it cannot tell whether the prose is correct, only whether the checkable structure holds.

### Phase 5: Metadata

**This block is the default, not a mandate.** Where Gate 1 found a repository convention, that
convention wins — record it in `.techdocrc.json` (metadata at the page foot, alternative field
names via `aliases`, a different status vocabulary, or `"location": "none"` for systems that
forbid an in-document block) and the linter will check the repo's schema instead of this one.
Absent any local convention, add to the top of every document:

```yaml
---
title: <Document Title>          # must match the H1
owner: <responsible person>
status: draft | active | needs-update | deprecated
last_updated: YYYY-MM-DD          # must be a real calendar date, not just the right shape
review_cadence: monthly | quarterly | biannually   # drives the staleness window
applicable_versions: <e.g. Go 1.24+, MySQL 8.0>   # required when the body pins a version
---
```

`needs-update` is the state that makes the anti-staleness rules usable: it marks a doc whose
content is known to have drifted but which is still the best available reference. Omitting it
forces a false choice between `active` (implying it is correct) and `deprecated` (implying it
should not be read). `lint_doc.py` accepts all four values and rejects anything else.

`review_cadence` is what turns `last_updated` from a decoration into a check. Without it the
linter falls back to a 365-day window; with it, a monthly runbook is reported as stale after 60
days. A doc still marked `active` past its window is reported with the remedy named, because
`active` asserts the content is correct.

## Hard Rules

1. **Reader-first**: every decision (depth, terminology, structure) is driven by reader needs, not author convenience.
2. **One doc, one job**: a document serves one primary purpose. If mixed, split and cross-link.
3. **Executable over descriptive**: commands must be copy-pasteable; steps must have expected output; tasks must have verification.
4. **No stale docs**: every document has an owner and last-updated date. A stale doc is worse than no doc.
5. **Evidence over opinion**: claims need proof (logs, metrics, benchmarks, code). "It might be a network issue" without evidence is unacceptable.

## Anti-Examples

In Review or Improve mode, load [writing-quality-guide.md §Anti-Examples](references/writing-quality-guide.md) for the full list of 12 common documentation mistakes (conclusion buried, wall of text, vague diagnosis, synonym mixing, orphaned docs, etc.).

## Document Maintenance (Anti-Staleness)

A stale doc is worse than no doc. When writing, also establish maintenance:

**Mandatory update triggers** — document MUST be updated when:
1. Commands, config items, or API parameters change.
2. Default behavior changes due to version upgrade.
3. Incident handling procedures or on-call routing changes.
4. A "followed the doc but it failed" case is reported.

**Status lifecycle**: `active` → `needs-update` → `active` (revised) or `deprecated` (with replacement link).

**Periodic review cadence**:

| Frequency | Cycle | `review_cadence` | Example |
|-----------|-------|---|---------|
| High (release, deploy, incident) | Monthly | `monthly` | Release runbook |
| Medium (dev workflows) | Quarterly | `quarterly` | Dev environment setup |
| Low (background knowledge) | Biannually | `biannually` | Architecture design doc |

Write the cadence into the metadata, not only into the delivery message. A recommendation in
chat is unenforceable; `review_cadence: monthly` is what lets `lint_doc.py` report the document
as overdue two months later. A doc with no declared cadence falls back to a 365-day window,
which for a release runbook is nine months too late.

## Load References Selectively

When classifying the document type (Phase 1) and building the initial skeleton:
→ Load `references/templates.md` for the document type template matching the classification (concept doc, task doc, reference doc, troubleshooting doc, RFC/ADR). Load **only** the section matching the classified type — do not load all templates.

When the audience is mixed (executives + engineers, or unknown):
→ Load `references/writing-quality-guide.md` §Funnel Structure for the four-layer structure pattern (Executive Summary → Overview → Technical Detail → Appendix) and section-length guidance.

When the document contains code blocks or CLI examples:
→ Load `references/writing-quality-guide.md` §Code Examples for code block formatting rules, language tag conventions, inline vs block decision criteria, and annotation patterns.

When in Review or Improve mode, assessing existing document quality:
→ Load `references/writing-quality-guide.md` §BAD/GOOD Examples and §Anti-Examples for the catalog of 12 common documentation mistakes (buried conclusions, walls of text, vague diagnosis, synonym mixing, orphaned docs) with corrected alternatives.
→ Load `references/writing-quality-guide.md` §Review Patterns for severity grouping (Critical / Major / Minor), before/after fix format, and common review pitfalls.

When the document requires diagrams, flowcharts, or visual structure:
→ Load `references/writing-quality-guide.md` §Visual Expression for diagram type selection (sequence, flowchart, ER, state), Mermaid syntax conventions, and diagram placement rules.

When the user explicitly asks about doc CI pipelines, PR templates, auto-generation, or doc-as-code infrastructure:
→ Load `references/docs-as-code.md` for CI check configurations, PR template structure, auto-generation tooling options, and doc ownership policies. **Do not load** for normal Write/Review/Improve tasks — adds ~780 tokens with no benefit for document creation.

## Output Contract

**Deliver the document as one contiguous markdown document** — frontmatter and body together,
never with the frontmatter split into its own ` ```yaml ` fence. A split document has no
frontmatter as far as any tool is concerned; the linter and every doc-site parser read the
leading `---` block of *one* document. Answering inline, wrap the whole document in a
four-backtick ` ````markdown ` fence (four, so inner `bash`/`json` blocks nest legally) or
delimit it with `<!-- BEGIN DOCUMENT -->` / `<!-- END DOCUMENT -->`.

Then end with this block, as plain text rather than inside a code fence. Use the exact field names.

```
── tech-doc-writer output ──
mode:           Write | Review | Improve
resolution:     R1 (retrieved) | R2 (asked) | R3 (assumed) — plus what resolved or blocked it
degradation:    Level 1 (Full) | Level 2 (Partial) | Level 3 (Scaffold)
doc_type:       concept | task | reference | troubleshooting | design
audience:       <role> / <goal> / <prior knowledge>
scorecard:      Critical: <n>/<applicable> | Standard: <n>/<applicable> | Hygiene: <n>/<applicable>
                (denominators are the APPLICABLE counts for this doc_type — run
                 `scripts/lint_doc.py <file> --type <doc_type> --scorecard` to get them;
                 note the N/A count so the reader can check the arithmetic)
files:          [list of created or changed file paths]
maintenance:    cadence: <monthly|quarterly|biannually>; triggers: <comma-separated>
assumptions:    [list of anything inferred rather than confirmed, or "none"]
```

Example — note the denominators differ from a fixed 6 because `task` docs have 4 applicable
Critical, 5 Standard, and 3 unconditional Hygiene items:

```
── tech-doc-writer output ──
mode:           Write
resolution:     R1 (retrieved) — CONTRIBUTING.md names the on-call rota as the reader
degradation:    Level 1 (Full)
doc_type:       task
audience:       backend dev / deploy service / knows Docker basics
scorecard:      Critical: 4/4 applicable (1 N/A) | Standard: 5/5 applicable (1 N/A) |
                Hygiene: 3/3 applicable (2 conditional, 1 N/A)
files:          [docs/deploy-user-service.md]
maintenance:    cadence: monthly; triggers: deploy script change, infra version bump
assumptions:    [assumed reader has VPN access based on repo context]
```

For a `concept` doc the same block would read `Standard: 2/2 applicable (4 N/A)` — the
denominator moves with the doc type, which is the whole point of §Gate 3's scoring rule.

## Language

- Follow the language of the existing document or user's request.
- Chinese documents: Chinese prose, English for code/commands/technical terms.
- **Pangu spacing (盘古之白)**: In CJK-Latin mixed text, always insert exactly one space between CJK characters and Latin letters/numbers. Examples:
  - BAD: `使用Redis集群部署3个节点`
  - GOOD: `使用 Redis 集群部署 3 个节点`
  - Exception: no space needed inside inline code backticks, URLs, or file paths.
- Maintain consistent terminology within a document — add a glossary section if needed.

## Self-Validation

Run `scripts/run_regression.sh` to verify skill integrity:
- **Contract tests**: SKILL.md structure, reference files, template coverage
- **Linter tests**: behavioral tests of `scripts/lint_doc.py` against fixture documents
- **Template tests**: every shipped skeleton passes this skill's own gate, and each table
  placeholder agrees with its column
- **Cross-layer drift**: `rationale/` and `evaluate/` still describe *this* skill; the Phase 4
  check table and the linter agree in both directions
- **Linter self-check**: the bundled reference docs pass the linter they ship with
- **Coverage matrix**: `scripts/tests/COVERAGE.md`, including false-positive rates measured
  against a real 987-file corpus

The forward evaluation needs a model and is opt-in:

```bash
# one arm — does a model following this skill produce a passing document?
TECH_DOC_EVAL_CMD='<model command reading stdin>' python3 -m unittest \
  discover -s scripts/tests -p 'test_forward_eval.py'
# both arms — does the skill add anything over the same model without it?
TECH_DOC_EVAL_CMD='<model command reading stdin>' python3 scripts/tests/ab_eval.py
```

Without that hook, `run_regression.sh` reports **PASS WITH SKIPS** rather than PASS: the harness
plumbing and the grader's ability to discriminate are exercised on every run via a stub, but a
stub replays a stored document and cannot measure a model.

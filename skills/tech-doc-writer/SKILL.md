---
name: tech-doc-writer
description: >
  Write, review, and improve technical documents (技术文档, 设计文档, 操作手册,
  故障报告, API文档). Use when users ask to write/draft/review/improve a
  technical document, create an RFC/ADR, write a runbook or operation guide,
  produce API docs, or create any structured technical writing deliverable.
  Audience-aware, evidence-based, with quality gates and anti-staleness
  enforcement. Supports concept docs, task docs, reference docs,
  troubleshooting docs, and design docs (RFC/ADR).
allowed-tools: Read, Write, StrReplace, Grep, Glob, Bash(git log*), Bash(git diff*)
---

# Tech Doc Writer

li

## Quick Reference

| If you need to… | Go to |
|---|---|
| Write a new document from scratch | §Execution Modes → Write + §Workflow Phase 0–5 |
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
- If you cannot verify a fact, mark it explicitly: `<!-- UNVERIFIED: ... -->`.

### Gate 1: Repo Context Scan

Before writing, quickly scan for existing doc conventions (`docs/`, `CONTRIBUTING.md`, `.markdownlint.json`, `.vale.ini`). Adapt to what exists — consistency with the repo trumps this skill's defaults. If conflicting conventions are found → **STOP and ASK** which to follow.

### Gate 2: Classify Type and Audience

Classify the document **and** its audience before writing anything:

| Reader's Goal | Document Type | Core Question |
|---------------|--------------|---------------|
| Understand a concept | Concept doc | What is it? Why? When to use? |
| Complete an operation | Task doc (runbook) | How? How to verify? How to rollback? |
| Look up a parameter | Reference doc | Fields, types, defaults, constraints? |
| Diagnose a failure | Troubleshooting doc | What happened? Why? How to fix/prevent? |
| Record a decision | Design doc (RFC/ADR) | Why this approach? What was rejected? |

If the user's request maps to multiple types → **STOP and ASK** before proceeding.

**Audience** — state explicitly: (1) who is the reader, (2) what must they do, (3) what do they already know. If audience is unclear and cannot be inferred → **STOP and ASK**. Mixed audience → use funnel structure (Executive Summary → Overview → Technical Detail → Appendix); load [writing-quality-guide.md §Funnel Structure](references/writing-quality-guide.md) for the pattern.

### Gate 3: Quality Scorecard

Run after writing/reviewing. Results must be reported in the output. Items marked with a doc type apply only to that type; unmarked items apply to all types.

**Critical (any FAIL → document not deliverable)**
- [ ] Commands are copy-paste-runnable [task, troubleshooting] or code is marked as snippet [concept]
- [ ] Every key step has expected output and verification [task, troubleshooting]
- [ ] Document has metadata: owner + last_updated + status [all]
- [ ] Terminology is consistent — zero synonym mixing [all]

**Standard (≥ 4/5 pass)**
- [ ] Conclusion/core message appears in the first paragraph, not buried at the end [all — especially troubleshooting: root cause upfront]
- [ ] Prerequisites are complete: permissions, environment, dependencies, inputs [task, troubleshooting]
- [ ] Rollback/failure path documented with trigger conditions [task]
- [ ] Title follows SPA principle (Simple ≤20 chars, Profit, Accurate) [all]
- [ ] Code examples are self-contained with imports, not just fragments [task, troubleshooting, reference]

**Hygiene (≥ 3/5 pass)**
- [ ] Diagrams have title, legend, and terms consistent with prose [all, when diagrams present]
- [ ] Cross-references to related docs where appropriate [all]
- [ ] Short paragraphs; 80%+ structured info in lists/tables [all]
- [ ] `applicable_versions` field present for version-sensitive content [all]
- [ ] Maintenance trigger conditions noted (when must this doc be updated?) [task, troubleshooting]
- [ ] Prevention section with quantifiable monitoring/alerting thresholds [troubleshooting]

Critical failures block delivery. Record scorecard results in output.

## Degradation Strategy

| Level | Condition | Behavior |
|-------|-----------|----------|
| **Level 1: Full** | Audience, type, and repo context all clear | Complete document + all gates pass |
| **Level 2: Partial** | Type clear but audience uncertain | Write with broadest reasonable audience; mark `<!-- AUDIENCE: assumed ... -->` at top; note in output |
| **Level 2.5: Active Retrieval** | Content gaps exist but codebase may contain answers | Before degrading to Level 3, attempt at least one round of targeted search (Grep for key terms, Glob for related files, Read for config/code). Fill gaps with retrieved evidence. If retrieval succeeds → proceed at Level 1 or 2. If retrieval fails → degrade to Level 3 |
| **Level 3: Scaffold** | Insufficient info **after** active retrieval attempt | Generate skeleton with section headings + `<!-- TODO: ... -->` placeholders; list what was searched and not found; ask user to fill gaps |

Never present Level 2/3 output as if it were Level 1. **When a relevant codebase or doc corpus exists, always attempt Level 2.5 retrieval before degrading to Level 3.** If no meaningful corpus is available (e.g., greenfield project, standalone document with no repo context), skip Level 2.5 retrieval and classify based on the information the user has provided — if audience, type, and scope are clear, proceed at Level 1 or 2 directly.

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
- Use diagrams when: 3+ components interact, state transitions, sequential interactions.
- Prefer Mermaid (GitHub/GitLab native) or ASCII art (diffable).
- **Mermaid complexity limit**: Keep diagrams ≤ 15 nodes. If logic requires more, split into multiple sub-diagrams with cross-references. Overly complex Mermaid frequently fails to render.
- Every diagram: title + legend + naming consistent with prose.

**Title — SPA Principle**:
- **S**imple: ≤ 20 characters, no filler words
- **P**rofit: what does the reader gain?
- **A**ccurate: no exaggeration, no ambiguity

| Doc Type | Title Pattern | Example |
|----------|--------------|---------|
| Concept | Noun + Noun | Connection Pool Internals |
| Task | Verb + Object | Deploy Redis Cluster |
| Reference | Noun + Noun | API Parameter Reference |
| Troubleshooting | Noun: Noun | MySQL: Deadlock Under High Concurrency |
| Design | RFC-NNN: Verb + Object | RFC-042: Migrate to Event-Driven Architecture |

### Phase 4: Quality Gate (Gate 3)
Run scorecard. Fix Critical failures before delivering.

### Phase 5: Metadata
Add to the top of every document:
```yaml
---
title: <Document Title>
owner: <responsible person>
status: draft | active | deprecated
last_updated: YYYY-MM-DD
applicable_versions: <e.g. Go 1.24+, MySQL 8.0>
---
```

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

| Frequency | Cycle | Example |
|-----------|-------|---------|
| High (release, deploy, incident) | Monthly | Release runbook |
| Medium (dev workflows) | Quarterly | Dev environment setup |
| Low (background knowledge) | Biannually | Architecture design doc |

When delivering, recommend the appropriate review cadence for the document.

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

Every invocation must end with this structured block. Use the exact field names.

```
── tech-doc-writer output ──
mode:           Write | Review | Improve
degradation:    Level 1 (Full) | Level 2 (Partial) | Level 2.5 (Retrieval-Assisted) | Level 3 (Scaffold)
doc_type:       concept | task | reference | troubleshooting | design
audience:       <role> / <goal> / <prior knowledge>
scorecard:      Critical: <n>/<total> | Standard: <n>/<total> | Hygiene: <n>/<total>
files:          [list of created or changed file paths]
maintenance:    cadence: <monthly|quarterly|biannually>; triggers: <comma-separated>
assumptions:    [list of anything inferred rather than confirmed, or "none"]
```

Example:

```
── tech-doc-writer output ──
mode:           Write
degradation:    Level 1 (Full)
doc_type:       task
audience:       backend dev / deploy service / knows Docker basics
scorecard:      Critical: 4/4 | Standard: 5/5 | Hygiene: 4/5
files:          [docs/deploy-user-service.md]
maintenance:    cadence: monthly; triggers: deploy script change, infra version bump
assumptions:    [assumed reader has VPN access based on repo context]
```

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
- **Coverage matrix**: `scripts/tests/COVERAGE.md`

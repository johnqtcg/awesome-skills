---
title: tech-doc-writer skill design rationale
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-27
applicable_versions: current repository version
---

# tech-doc-writer Skill Design Rationale

`tech-doc-writer` is a technical-writing framework for drafting, reviewing, and improving engineering documentation. Its core idea is: **the goal of high-quality technical documentation is to let the target reader independently understand, execute, troubleshoot, look up, or decide without needing to ask someone else; therefore the writing process must first classify document type and reader goal, then determine structure, depth, verification style, degradation behavior, and maintenance rules, instead of treating all documents as the same Markdown output.** That is why the skill turns Repo Context Scan, Type and Audience Classification, Quality Scorecard, Degradation Strategy, Metadata, Anti-Staleness, and Output Contract into one fixed workflow.

## 1. Definition

`tech-doc-writer` is used for:

- writing, reviewing, and improving engineering documents,
- covering concept, task/runbook, reference, troubleshooting, and design/RFC/ADR document types,
- deciding structure and depth from reader goals and audience knowledge,
- enforcing quality gates for metadata, conclusion-first writing, executability, rollback, and terminology consistency,
- and degrading honestly when information is insufficient instead of fabricating content.

Its output is not just document prose. It also includes:

- mode,
- degradation level,
- doc_type,
- audience,
- scorecard,
- files,
- maintenance,
- assumptions.

From a design perspective, it is closer to a technical-documentation governance framework than to a generic prompt for polishing documents.

## 2. Background and Problems

The main problem this skill addresses is not that models cannot write technical documents. It is that documentation work naturally drifts toward several high-risk distortions:

- the document looks complete, but the target reader still cannot act independently,
- the content reads like an information dump with no clear document type or usage mode,
- the document is readable in the short term but rots quickly afterward.

Without an explicit process, the most common failures cluster into eight categories:

| Problem | Typical consequence |
|---------|---------------------|
| Document type is not classified first | runbooks read like tutorials, troubleshooting docs read like concept explainers, design docs omit alternatives |
| Audience is not analyzed first | the depth is wrong for both beginners and experts |
| No conclusion first | readers spend too long before learning what to do or what the root cause is |
| No structured metadata | ownership, status, and version scope cannot be tracked |
| Commands are not executable or have no expected output | the runbook looks usable but cannot be verified |
| Fix steps exist without rollback or failure paths | readers have no safe exit during failure |
| Terminology drifts and titles are generic | documents become hard to search, maintain, and interpret |
| No maintenance triggers exist | stale docs continue misleading readers |

The design logic of `tech-doc-writer` is to make "what kind of document is this, who is it for, what does the reader need to do, which facts must be verified, which gaps require degradation, and when must this document be updated?" explicit before writing or review is allowed to proceed.

## 3. Comparison with Common Alternatives

It helps to compare it with a few common alternatives:

| Dimension | `tech-doc-writer` skill | Asking a model to "write a technical doc" | Manual experience-driven documentation |
|-----------|-------------------------|-------------------------------------------|---------------------------------------|
| Document-type routing | Strong | Weak | Medium |
| Audience modeling | Strong | Weak | Medium |
| Conclusion-first discipline | Strong | Weak | Medium |
| Executability and verification | Strong | Weak | Medium |
| Metadata and version labeling | Strong | Weak | Weak |
| Honest degradation / unverified marking | Strong | Weak | Weak |
| Anti-staleness mechanism | Strong | Weak | Weak |
| Structured delivery | Strong | Weak | Weak |

Its value is not only that the document is better written. Its value is that it turns engineering documentation from one-off prose production into a verifiable, maintainable, and reviewable delivery process.

## 4. Core Design Rationale

### 4.1 Repo Context Scan Comes First

Before real writing begins, `tech-doc-writer` requires a quick scan of:

- `docs/`,
- `CONTRIBUTING.md`,
- `.markdownlint.json`,
- `.vale.ini`.

This matters because technical documents are not standalone essays; they live inside a repository. Existing conventions for tone, structure, folder layout, and linting often matter more than the skill's own defaults. By making this Gate 1, the skill explicitly acknowledges that documentation consistency should serve the repository first, not an abstract writing ideal.

The evaluation showed no major measurable assertion delta here, but it still acts as an important engineering safeguard against "good-looking but repo-inconsistent" documentation drift.

### 4.2 It Classifies Document Type and Audience Before Writing

This skill forces the writer to identify:

- the document type,
- who the reader is,
- what the reader must do,
- what the reader already knows.

It also maps documents into:

- concept,
- task,
- reference,
- troubleshooting,
- design.

This is the structural axis of the skill because one of the most common documentation failures is not missing content, but writing the wrong shape of document. For example:

- a task doc without prerequisites, expected output, or rollback,
- a troubleshooting doc that buries root cause behind background explanation,
- a design doc that says what was chosen but not why alternatives were rejected.

The evaluation supports this directly: with-skill consistently chose the right structure across task, troubleshooting, and review scenarios, while without-skill produced acceptable but more ad hoc structures that depended more on improvisation.

### 4.3 Audience Analysis Is a Separate Mandatory Gate

`tech-doc-writer` does not stop at "what type of document is this?" It also requires:

1. who the reader is,
2. what the reader must accomplish,
3. what the reader already knows.

If audiences are mixed, it requires Funnel Structure:

- Executive Summary,
- Overview,
- Technical Detail,
- Appendix.

This is important because many engineering documents fail not on factual correctness, but on information layering. In mixed-audience documents, a flat stream of detail prevents leaders from reaching the conclusion quickly and prevents implementers from finding the deeper sections efficiently. The skill uses funnel structure to make "a reader can stop at the appropriate depth and still understand the document" an explicit rule.

Audience Analysis did not create a large measurable assertion delta in this evaluation, but it still functions as a prerequisite layer for writing the document correctly at all.

### 4.4 The Quality Scorecard Is the Core of the Skill

One of the skill's biggest design strengths is that it decomposes documentation quality into:

- Critical,
- Standard,
- Hygiene,

with some checks applying only to specific document types.

For example:

- task / troubleshooting docs must have copy-pasteable commands and expected output,
- all docs must have owner, last_updated, and status,
- task docs must include rollback and failure-path handling,
- troubleshooting docs must include prevention plus monitoring thresholds.

This is crucial because it separates "the doc looks decent" from "the doc is actually deliverable." The evaluation explicitly names YAML structured metadata as the largest single-category gap, while SPA titles, expected output, rollback, and output contracts also show important deltas driven by this scorecard layer. That shows the skill's main increment is not stronger prose, but stronger execution of documentation quality checks.

### 4.5 Gate 0 Emphasizes Execution Integrity

`tech-doc-writer` explicitly says:

- do not write commands, configs, or parameters as repository facts unless verified,
- do not claim a command was runnable unless it was actually executed,
- mark uncertain content as `<!-- UNVERIFIED: ... -->`.

This is highly practical because the most dangerous documentation failure is not awkward phrasing, but presenting unverified content as authoritative fact. The `UNVERIFIED` marker makes uncertainty explicit and prevents polished-looking hallucinations from being mistaken for truth. The evaluation's code-example comparison supports this too: the base model could already write solid code examples, but with-skill added the extra layer of unverified-content discipline that documentation needs.

### 4.6 The Degradation Strategy Uses Levels 1 / 2 / 2.5 / 3

The skill does not insist on pretending complete information exists. Instead it requires graded degradation:

- Level 1: Full,
- Level 2: Partial,
- Level 2.5: Active Retrieval,
- Level 3: Scaffold.

The most important step is Level 2.5. Before degrading to a scaffold, the skill requires at least one round of active retrieval to see whether the repository already contains the missing facts.

This is mature design because technical-writing gaps are often not "the information does not exist," but "the information may exist in the repo and has not been retrieved yet." Level 2.5 encodes retrieval as a required gate, which reduces both premature scaffolding and content fabrication. Even though the evaluation did not strongly exercise this path, it remains one of the skill's clearest differentiators from a generic writing prompt.

### 4.7 It Enforces Conclusion First

Across document types, the skill emphasizes:

- the core conclusion belongs in the first paragraph,
- and troubleshooting docs especially must put root cause up front.

This is critical because engineering readers usually come with a task, not a desire for a slow reading experience. If the conclusion is buried, search and comprehension costs rise immediately. The deadlock-troubleshooting evaluation is the clearest example: with-skill began with the root cause; without-skill first explained what a deadlock is and only later arrived at the conclusion. Both were readable, but the cost of reaching the answer was very different.

### 4.8 Task and Troubleshooting Executability Is So Strict

For task and troubleshooting documents, `tech-doc-writer` is explicit:

- commands must be copy-paste-runnable,
- each key step must have expected output,
- verification must exist,
- task docs must include rollback trigger conditions and rollback steps.

The meaning of this design is that it turns engineering documentation from descriptive explanation into an operational runbook. Without expected output, readers cannot tell whether a command succeeded; without rollback, they have no safe exit when things go wrong; without verification, the document can direct actions but cannot confirm outcomes. These were exactly the items most likely to be missing in the without-skill outputs.

### 4.9 SPA Title Rules Are Part of the Gates

The skill explicitly requires SPA titles:

- Simple,
- Profit,
- Accurate.

This looks like a writing detail, but it is really a searchability and maintenance rule. Titles such as:

- Notes,
- Guide,
- Documentation,

are nearly useless for future retrieval. SPA titles naturally encode:

- keyword searchability,
- reader benefit,
- scope boundaries.

The evaluation showed this as another skill-only difference: with-skill titles were shorter, more specific, and easier to retrieve; without-skill titles were more likely to be generic or too long.

### 4.10 Metadata and `applicable_versions` Are Mandatory

The skill requires all documents to include:

- `title`,
- `owner`,
- `status`,
- `last_updated`,
- `applicable_versions`.

This is critical because technical docs age, and stale docs are more dangerous than missing docs. Owner defines responsibility, status defines whether the doc should be trusted, last_updated defines freshness, and applicable_versions tells the reader whether the instructions are safe to apply at all. The evaluation showed structured metadata as the most stable differentiator, which confirms that this is both easy for default writing to omit and highly important for documentation governance.

### 4.11 Review Mode Emphasizes Severity, Before/After Fixes, and Positive Acknowledgement

In Review mode, `tech-doc-writer` does not stop at pointing out defects. It requires:

- findings grouped by Critical / Major / Minor,
- concrete before/after fixes,
- and explicit acknowledgement of what already works.

Improve mode itself is framed more around minimal-diff correction and preserving structure that already works; positive acknowledgement is reinforced by the review patterns reference rather than Improve mode alone. This is mature design because documentation review should not exist to prove the reviewer is clever; it should help the author act next. Problem descriptions without before/after examples often still require a second round of interpretation; purely negative reviews create poor collaboration dynamics. The evaluation's review scenario showed this clearly: both sides found similar issues, but with-skill produced more structured, actionable feedback.

### 4.12 Anti-Staleness Is a Separate Maintenance Mechanism

`tech-doc-writer` explicitly requires the document to declare:

- when it must be updated,
- what review cadence is appropriate,
- and how status evolves from `active` to `needs-update` or `deprecated`.

It also lists typical triggers:

1. commands, configs, or parameters change,
2. a version upgrade changes defaults,
3. incident handling or on-call routing changes,
4. a reader follows the doc and it fails.

This has major governance value because most bad docs are not bad on day one; they become bad later. By placing maintenance triggers inside the writing process, the skill turns "docs become stale" from implicit common sense into explicit contract.

### 4.13 References Are Loaded Selectively by Type

The skill's references are not meant to be loaded all at once:

- `templates.md` is loaded only for the classified doc type,
- `writing-quality-guide.md` is loaded by section for funneling, BAD/GOOD examples, code examples, review patterns, anti-examples, or visual expression,
- `docs-as-code.md` is loaded only for CI / PR / auto-generation / documentation infrastructure tasks.

This is sensible because technical documentation spans many shapes, and the quality bar is not identical across them. Selective loading keeps high-frequency general rules in `SKILL.md` while moving lower-frequency specialized patterns into references, balancing breadth of capability with token cost.

## 5. Problems This Design Solves

Combining the current `SKILL.md`, key references, and the evaluation report, the skill solves the following problems:

| Problem type | Corresponding design | Practical effect |
|--------------|----------------------|------------------|
| Document type and structure are mismatched | Type Classification + Templates | Makes structure more predictable |
| Reader layering is unclear | Audience Analysis + Funnel Structure | Better aligns information depth |
| Core message is buried too deep | Conclusion First | Gets readers to the answer faster |
| Commands cannot be verified | Expected Output + Verification | Makes docs more executable |
| Failure handling is missing | Rollback rules | Makes operations safer |
| Docs rot easily | Metadata + Anti-Staleness | Improves maintenance and ownership |
| Missing facts tempt fabrication | Execution Integrity + Degradation Strategy | Produces more honest output |
| Review advice is too vague to use | Severity + Before/After + Output Contract | Makes feedback actionable |

## 6. Key Highlights

### 6.1 It Turns Technical Writing into Reader-Task-Driven Workflow

The process does not begin by deciding what to say. It begins by deciding what the reader must accomplish, and then shaping the document accordingly.

### 6.2 Document-Type Classification Is One of Its Most Visible Structural Strengths

Once task, troubleshooting, design, reference, and concept docs are routed explicitly, they are much less likely to take the wrong shape.

### 6.3 The Quality Scorecard Is the Biggest Practical Source of Increment

The evaluation already shows that metadata, conclusion-first writing, SPA titles, expected output, and rollback quality mostly come from this scorecard layer.

### 6.4 Its Handling of Uncertain Information Is Highly Engineered

`UNVERIFIED` markers plus staged degradation let the document remain honest under uncertainty rather than pretending to be complete.

### 6.5 The Anti-Staleness Mechanism Has Real Governance Value

Many documentation tools focus only on how to write. `tech-doc-writer` also encodes when the document must be updated, which makes docs behave more like maintained assets.

### 6.6 Its Real Increment Is Documentation Governance More Than Basic Writing Ability

The evaluation already shows that the base model can write solid engineering prose, code examples, and troubleshooting explanations. The real delta comes from metadata, type routing, conclusion-first discipline, expected output, rollback, structured review, and maintenance rules. That means the skill's core value is technical-document governance, not simply "better wording."

## 7. When to Use It — and When Not To

| Scenario | Suitable | Reason |
|----------|----------|--------|
| Runbooks, operation guides, and troubleshooting docs | Very suitable | Executability and verification gates are strong |
| API docs, parameter references, and design docs | Very suitable | Type templates and metadata rules are highly useful |
| Reviewing or improving existing docs | Very suitable | Scorecards and before/after fixes are very practical |
| Mixed-audience engineering docs | Very suitable | Funnel structure helps layer information |
| Information gaps that may still be answerable from the repo | Very suitable | Level 2.5 active retrieval is valuable |
| Short one-off notes with no maintenance expectations | Not always optimal | The framework intentionally adds governance overhead |

## 8. Conclusion

The real strength of `tech-doc-writer` is not that it can make engineering prose sound more like a standard answer. It is that it systematizes the judgments that technical documentation most often gets wrong: classify the document type and audience first, choose structure accordingly, enforce quality gates for conclusion-first writing, executability, metadata, and terminology, degrade honestly when facts are missing, attach structured output at delivery time, and declare maintenance triggers for the future.

From a design perspective, the skill embodies a clear principle: **the key to high-quality technical documentation is not writing more information, but helping the target reader reach the conclusion faster, know what to do, know how to verify it, know how to recover when it fails, and know when the document must be updated.** That is why it is especially well suited to engineering-team runbooks, troubleshooting guides, API docs, design documents, and documentation review workflows.

## 9. Document Maintenance

This document should be updated when:

- the Execution Modes, Mandatory Gates, Quality Scorecard, Degradation Strategy, Output Contract, Language rules, or Anti-Staleness mechanism in `skills/tech-doc-writer/SKILL.md` change,
- key templates, writing rules, or docs-engineering practices in `skills/tech-doc-writer/references/templates.md`, `writing-quality-guide.md`, or `docs-as-code.md` change,
- key supporting conclusions in `evaluate/tech-doc-writer-skill-eval-report.md` or `evaluate/tech-doc-writer-skill-eval-report.zh-CN.md` change.

Review quarterly; review immediately if the document-type routing, quality scorecard, degradation strategy, metadata rules, or anti-staleness mechanism of `tech-doc-writer` change substantially.

## 10. Further Reading

- `skills/tech-doc-writer/SKILL.md`
- `skills/tech-doc-writer/references/templates.md`
- `skills/tech-doc-writer/references/writing-quality-guide.md`
- `skills/tech-doc-writer/references/docs-as-code.md`
- `evaluate/tech-doc-writer-skill-eval-report.md`
- `evaluate/tech-doc-writer-skill-eval-report.zh-CN.md`

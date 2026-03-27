---
title: deep-research skill design rationale
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-27
applicable_versions: current repository version
---

# deep-research Skill Design Rationale

`deep-research` is a source-backed research framework for factual and analytical research tasks. Its core idea is: **research quality depends on defining scope, evidence requirements, retrieval budget, verification rigor, and delivery structure before retrieval, synthesis, and conclusion writing begin.** That is why the skill turns Scope Classification, Ambiguity Resolution, Evidence Requirements, Research Mode, Hallucination Awareness, Budget Control, Content Extraction, and Execution Integrity into a strict serial workflow.

## 1. Definition

`deep-research` is meant for technical surveys, option comparison, claim verification, trend analysis, codebase research, and hybrid research tasks. Its output is not just a set of findings. It also includes:

- the normalized research scope,
- evidence-chain requirements and confidence expectations,
- the actual retrieval and extraction method used,
- a separation between consensus and debate,
- source-quality notes and explicit research gaps.

From a design perspective, it is much closer to a gated research execution framework than to a free-form web-search prompt.

## 2. Background and Problems

The core problem this skill addresses is that research tasks without explicit constraints tend to fail in four ways at once: conclusions arrive too early, evidence tiers are too weak, citations are hard to verify, and output structure varies too much to reuse.

Without a clear framework, failures usually cluster into eight categories:

| Problem | Typical consequence |
|---------|---------------------|
| Scope is never narrowed first | The topic drifts and the final result stops answering the original question |
| Comparison dimensions or time boundaries are unclear | Technology comparisons and trend analysis mix data with different timeframes or meanings |
| No evidence chain is defined up front | Recommendation-style conclusions are supported by only one or two weak sources |
| Conclusions are formed from snippets | Search previews are treated as evidence, leading to distorted reading |
| Model output has no anti-hallucination guardrail | URLs, paper titles, version facts, or benchmark numbers are stated too confidently |
| Retrieval budget is unlimited | Query rounds keep expanding while information gain keeps shrinking |
| Output structure changes from task to task | Reports are hard to compare, review, or reuse |
| Gaps are hidden instead of exposed | Missing evidence is covered over with overly confident prose |

The design logic of `deep-research` is to turn research from a situational behavior into a workflow that is verifiable, auditable, and reusable.

## 3. Comparison with Common Alternatives

Before looking at the details, it helps to compare the skill with a few common alternatives:

| Dimension | `deep-research` skill | Asking a model to "research this" | Doing web search and hand-writing a summary |
|-----------|-----------------------|-----------------------------------|--------------------------------------------|
| Scope narrowing | Strong | Weak | Medium |
| Ambiguity handling | Strong | Weak | Weak |
| Evidence-chain requirements | Strong | Weak | Weak |
| Anti-hallucination verification | Strong | Weak | Weak |
| Snippet vs. full-content distinction | Strong | Weak | Weak |
| Content extraction discipline | Strong | Weak | Medium |
| Budget control | Strong | Weak | Weak |
| Structured delivery | Strong | Medium | Weak |
| Gap exposure | Strong | Weak | Weak |

Its value does not come from replacing model reasoning. It comes from adding **boundary control, evidence discipline, and delivery discipline** to the research process.

## 4. Core Design Rationale

### 4.1 Scope Classification and Ambiguity Resolution Come First

`deep-research` places Scope Classification and Ambiguity Resolution at the very front, requiring the research category, goal, comparison dimensions, and expected depth to be clarified before retrieval starts.

The reason is straightforward: many research failures do not come from lack of sources. They come from never clearly defining the object of research. For example:

- a request like "research microservices" is too broad and must be narrowed;
- trend analysis without a time window will mix stale and current information;
- technology comparison without explicit dimensions such as performance, cost, ecosystem, or operational complexity will drift.

These gates force the workflow to answer "what exactly are we researching?" before it starts searching.

### 4.2 Evidence Requirements Must Be Defined Before Retrieval

The third Mandatory Gate is Evidence Requirements. It requires the workflow to define the minimum acceptable evidence chain before retrieval begins.

This is critical because not all conclusions are the same kind of claim:

- a single factual claim may need an official or primary source;
- a best-practice recommendation may need an official basis plus practitioner experience;
- a technology comparison may require multiple independent benchmarks or reviews;
- a trend judgment may require cross-time data from multiple sources;
- a disputed or fast-moving topic may require several source tiers plus conflict handling.

Without an explicit evidence threshold, the model is likely to stop as soon as it finds something that resembles an answer. `deep-research` instead defines what "enough evidence" means before it decides when synthesis may begin.

### 4.3 Research Mode and Budget Control Are Paired

`deep-research` does not only classify work into `Quick`, `Standard`, and `Deep`. It also assigns bounded retrieval and content-extraction budgets to each mode.

That is a mature design choice because research tends to fail in two opposite directions:

- too little retrieval, where evidence is thin but the conclusion sounds complete;
- too much retrieval, where search rounds expand while marginal information value keeps dropping.

Mode answers "how deep should this go?" Budget answers "where should this stop?" The combination keeps the process from being both shallow and unbounded.

It also gives users a predictable cost profile. A quick check should stay quick. A deep dive may spend more budget, but only because the user is explicitly asking for greater completeness.

### 4.4 Hallucination Awareness Is Elevated to a Mandatory Gate

`deep-research` treats Hallucination Awareness as its own Mandatory Gate and backs it with a dedicated `hallucination-and-verification.md` reference.

That reflects a very clear understanding of research work: the most dangerous failure mode is not "the analysis is a bit shallow." It is **output that looks source-backed but is not actually verifiable**. In research tasks, that often appears as:

- fabricated URLs, paper titles, or author names,
- stale information presented as current fact,
- uncertain conclusions written in absolute language,
- conflation of similar products, versions, or concepts,
- selective use of supporting evidence while contradictions are ignored.

Making this a separate gate rather than a few reminders signals that anti-hallucination behavior is foundational to research correctness.

### 4.5 The Skill Requires Full-Content Extraction vs. Search Snippets

The Content Extraction Gate is one of the most important design choices in `deep-research`. It explicitly requires the workflow to read actual source content before drawing key conclusions.

This addresses one of the most common and least visible research errors:

- search snippets preserve conclusions but not context,
- page titles often carry marketing language that does not reflect evidence strength,
- secondary writeups frequently omit methodology, version boundaries, or experimental conditions.

That is why the skill requires `fetch-content` before synthesis. If extraction fails for a critical source, the failure should be recorded in gaps instead of being silently treated as sufficient evidence.

This creates a sharp distinction between `deep-research` and ordinary "search-and-summarize" workflows. The requirement is not merely "locate sources." It is "actually read sources."

### 4.6 Execution Integrity Is Called Out Separately

The Execution Integrity Gate requires the final report to state honestly:

- whether retrieval actually ran,
- whether content extraction actually ran,
- how many sources were extracted and cited,
- which conclusions come from page content and which are only leads from snippets.

This matters because research tasks are particularly prone to producing output that only *looks* executed. Without execution-integrity discipline, a report can sound complete while mixing assumptions, imagined steps, and partial evidence.

Execution Integrity turns a research writeup from a text artifact into a deliverable with process evidence behind it.

### 4.7 Honest Degradation Is Better Than Forcing a Complete Answer

`deep-research` supports `Full`, `Partial`, and `Blocked` outcomes, and it requires gaps, causes, and next-step suggestions to be stated explicitly.

That is highly practical because research frequently hits real constraints:

- important sources are paywalled,
- some domains are poorly indexed by public search,
- the topic is too recent for strong public evidence,
- the retrieval budget is exhausted before the evidence chain is satisfied.

Without a degradation model, the model usually falls into one of two bad behaviors:

- evidence is thin, but the prose still sounds definitive;
- one obstacle appears and the workflow stops with nothing useful.

`deep-research` takes a third route: report honestly what is confirmed, what is missing, and how the missing evidence should be pursued next.

### 4.8 Output Contract for Consensus, Debate, Source Quality, and Gaps

The current Output Contract requires 9 sections for `Standard` and `Deep` modes; `Quick` mode may omit sections 5 and 6. In the full report structure, the most design-significant among them are:

- `Consensus vs Debate`,
- `Source Quality Notes`,
- `Gaps & Limitations`.

Their purpose is not cosmetic completeness. Their purpose is to let a reader answer four questions quickly:

- which conclusions are relatively stable,
- where sources still disagree,
- how strong the evidence really is,
- which gaps materially affect decision-making.

That is one of the clearest differences between `deep-research` and ordinary "material collection." The former delivers a research judgment framework; the latter often only accumulates information.

### 4.9 It Covers Web Research, Codebase Research, and Hybrid Research Together

At the Scope Classification stage, `deep-research` explicitly covers comparative research, trend analysis, claim verification, technical deep-dive, codebase research, and hybrid research.

This shows that the skill does not interpret research as "search the web." In engineering practice, many of the most valuable research tasks are hybrid:

- first inspect the current codebase,
- then validate options or best practices externally,
- finally combine internal constraints and external evidence into a recommendation.

Including codebase research and hybrid research in the same framework makes the skill fit real technical decision work rather than only public-information gathering.

### 4.10 References Use a "Base Always Loaded + Details On Demand" Pattern

The current version of `deep-research` is no longer a single-file skill. It treats the output contract as always-loaded report infrastructure, while high-risk verification rules and programmer-specific research patterns are loaded conditionally.

This is more scalable than pushing every rule into `SKILL.md` for three reasons:

- low-frequency but high-importance rules can expand only when needed,
- different research tasks do not need the same detail every time,
- verification protocol, output contract, and technical research patterns are naturally maintainable as separate assets.

This is a classic production-grade skill pattern: the base workflow and output contract stay resident, while heavy detail is loaded on demand.

### 4.11 The Workflow Is Bound to Subcommands vs. Pure Natural-Language Advice

`deep-research` is not only a document of recommendations. It is explicitly tied to subcommands such as `retrieve`, `fetch-content`, `search-codebase`, `validate`, and `report`.

That design matters because it turns research method into an executable process:

- retrieval and extraction can be reproduced,
- validation can be run independently,
- report generation has explicit inputs and outputs,
- future regression testing and automation become much easier.

That is one of the clearest ways it goes beyond an ordinary prompt: it defines not only how to think, but how to execute.

## 5. Problems This Design Solves

Combining the current `SKILL.md` with its supporting references, the skill addresses the following engineering problems:

| Problem type | Corresponding design | Practical effect |
|--------------|----------------------|------------------|
| Scope drift | Scope Classification + Ambiguity Resolution | Narrows the question before retrieval begins |
| Weak evidence strength | Evidence Requirements Gate | Different claim types get different evidence thresholds |
| Retrieval that is too shallow or too deep | Research Mode + Budget Control | Balances cost against completeness |
| Treating snippets as evidence | Content Extraction Gate | Key findings rely on real page content rather than previews |
| Hallucinations contaminating findings | Hallucination Awareness + Verification Protocol | Reduces fabricated citations, phantom facts, and confidence inflation |
| Research steps are not auditable | Execution Integrity Gate | Makes execution state, depth, and citation count explicit |
| Thin evidence is stretched into certainty | Honest Degradation | Clearly separates Full / Partial / Blocked |
| Reports are hard to reuse or compare | Output Contract | Makes research outputs structurally consistent |
| External research is disconnected from the codebase | Codebase / Hybrid Research categories + `search-codebase` | Makes the workflow fit real engineering decision work |

## 6. Key Highlights

### 6.1 It Turns Research into a Gated Execution Flow

Many research workflows only define "search for information." `deep-research` makes preconditions, evidence thresholds, extraction discipline, verification protocol, and delivery structure all explicit.

### 6.2 Its Anti-Hallucination Design Is Systematic

It does not stop at general warnings. It organizes hallucination types, verification priority, source tiers, query patterns, and insufficient-evidence handling into a coherent system.

### 6.3 It Is Strict About Whether Evidence Was Actually Read

Mandatory content extraction is one of the skill's strongest quality controls. It raises the minimum reliability of the resulting conclusions.

### 6.4 Its Structured Delivery Is Well Suited to Long-Term Reuse

In `Standard` and `Deep` modes, Research Question, Method, Executive Summary, Key Findings, Detailed Analysis, Consensus vs Debate, Source Quality Notes, Sources, and Gaps & Limitations together create a report shape that is easy to review, compare, and update; `Quick` mode deliberately allows a lighter-weight version for speed.

### 6.5 It Fits Hybrid Engineering Research Especially Well

Many skills are good at either web search or code search. `deep-research` is stronger because it covers both and places them under the same evidence and delivery framework.

### 6.6 The Current Version Emphasizes Execution Integrity More Than the Evaluation Snapshot

The existing evaluation report most strongly validates the skill's **structural discipline**, especially template consistency, numbered citations, and source-credibility labels. At the same time, the current `SKILL.md` has expanded into 8 Mandatory Gates, a 9-section Output Contract, and several supporting references. In other words, the evaluation confirms the core design direction, while the current skill extends that direction with stronger execution gates and anti-hallucination controls.

## 7. When to Use It — and When Not To

| Scenario | Suitable | Reason |
|----------|----------|--------|
| Technology option comparison | Yes | Evidence chains, mode selection, and source-quality notes are highly valuable |
| Fact-checking or claim verification | Yes | The anti-hallucination and verification protocol fits directly |
| Trend analysis | Yes | It explicitly supports time windows and cross-period sources |
| External research informed by current codebase state | Yes | Hybrid research is one of its intended scenarios |
| Producing a reusable research report | Yes | The Output Contract is designed for this |
| Asking a quick general-knowledge question | Not always necessary | A direct answer may be lighter-weight |
| Work that depends entirely on private internal material with no external retrieval path | Limited fit | It needs additional data access mechanisms |
| Purely creative ideation | No | That is outside the skill's design goal |

## 8. Conclusion

The real strength of `deep-research` is that it systematizes the parts of research most likely to go wrong: define the question boundary first, specify the evidence threshold, constrain depth and budget, force reading of source content, verify high-risk claims through anti-hallucination protocols, and deliver the result in a contract that makes consensus, disagreement, source quality, and missing evidence explicit.

From a design perspective, the skill embodies a clear principle: **research quality depends first on evidence discipline and delivery discipline, and only then on writing quality.** That is why it is especially well suited to engineering decisions, technical comparisons, and fact-verification work.

## 9. Document Maintenance

This document should be updated when:

- the Mandatory Gates, Research Modes, budgets, Safety Rules, or Output Contract in `skills/deep-research/SKILL.md` change,
- the key protocols in `skills/deep-research/references/output-contract-template.md`, `hallucination-and-verification.md`, or `research-patterns.md` change,
- the subcommands, execution flow, or output fields in `skills/deep-research/scripts/deep_research.py` change,
- key supporting conclusions in `evaluate/deep-research-skill-eval-report.md` change,
- the skill evolves further and the gap between the evaluation snapshot and the current implementation becomes materially larger.

Review quarterly; review immediately if the gate structure, reference set, or script shape of `deep-research` changes substantially.

## 10. Further Reading

- `skills/deep-research/SKILL.md`
- `skills/deep-research/references/output-contract-template.md`
- `skills/deep-research/references/hallucination-and-verification.md`
- `skills/deep-research/references/research-patterns.md`
- `skills/deep-research/scripts/deep_research.py`
- `evaluate/deep-research-skill-eval-report.md`

---
title: google-search skill design rationale
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-27
applicable_versions: current repository version
---

# google-search Skill Design Rationale

`google-search` is a search-and-verification framework that turns "help me look this up" into a disciplined retrieval workflow. Its core idea is: **the goal of search is to first determine what the user is actually trying to know, what level of evidence the conclusion requires, which language and source path are appropriate, and how far the search should go before stopping, and then deliver the result with confidence labels, degradation status, and reusable queries.** That is why the skill turns Scope, Ambiguity, Evidence, Language, Source Path, Mode, Budget, and Execution Integrity into one explicit flow.

## 1. Definition

`google-search` is used for:

- factual lookups and current-status verification,
- official docs, standards, and release-note retrieval,
- programmer search such as error debugging, API docs, GitHub / Stack Overflow / RFC lookup,
- technical comparisons, tool selection, materials discovery, and public-information gathering,
- any search task where source support and uncertainty handling matter.

Its output is not only the answer. It also includes:

- the active execution mode,
- the degradation level,
- a conclusion summary,
- evidence-chain status,
- key evidence and source assessment,
- confidence and source-tier labels for key numbers,
- reusable queries,
- and, in Standard / Deep mode, often a gate-execution summary.

From a design perspective, it is closer to a search-operations discipline framework than to a prompt that simply knows how to use Google.

## 2. Background and Problems

The main problem this skill addresses is not that models cannot search. It is that search tasks often fail structurally in a few predictable ways:

- the model can find sources, but does not define the evidence standard first,
- it can synthesize information, but does not label uncertainty or source tier,
- it can answer the question, but leaves no reusable or reviewable search trail.

Without this framework, the most common failures cluster into eight categories:

| Problem | Typical consequence |
|---------|---------------------|
| Search scope is not classified first | Fact lookup, tutorial search, debugging, and technology comparison all get handled with the same strategy |
| No evidence chain is defined | Secondary summaries get presented as if they support primary conclusions |
| Mode and budget are not distinguished | Simple tasks are over-searched, complex ones are under-searched |
| Ambiguity is not resolved | Queries go down the wrong path from the start |
| Official, primary, and third-party sources are mixed without ranking | Vendor docs, competitor blogs, and SEO pages get treated as equivalent |
| Honest degradation is missing | Evidence gaps get hidden behind fully confident language |
| Reusable queries are omitted | The user cannot continue or audit the search path |
| Snippets are mistaken for verification | Search previews get treated as confirmed source content |

The design logic of `google-search` is to make "what level of conclusion does this search need?" explicit before deciding "how should the search be executed and when should it stop?"

## 3. Comparison with Common Alternatives

It helps to compare the skill with a few common alternatives:

| Dimension | `google-search` skill | Asking a model to "search this for me" | Doing a few ad hoc searches manually |
|-----------|-----------------------|----------------------------------------|-------------------------------------|
| Task classification | Strong | Weak | Weak |
| Evidence-chain discipline | Strong | Weak | Weak |
| Mode and budget control | Strong | Weak | Weak |
| Source-path ranking | Strong | Medium | Weak |
| Confidence and source-tier labeling | Strong | Weak | Weak |
| Honest degradation | Strong | Weak | Weak |
| Reusable queries | Strong | Weak | Weak |
| Auditability of the search process | Strong | Weak | Weak |

Its value is not only that the answer looks more research-like. Its value is that it turns search from one-off link gathering into a workflow that can be reviewed, reused, and continued.

## 4. Core Design Rationale

### 4.1 It Classifies Scope Before Writing Queries

The first gate in `google-search` is Scope Classification. It requires the request to be mapped first into one primary category:

- Information,
- Knowledge,
- Materials,
- Tools,
- Public-information lookup,
- Programmer search,

and one primary goal:

- Know,
- Learn,
- Create,
- Complete a task.

This is critical because different search categories require different query patterns, source rankings, and evidence standards. "Latest company update" needs recency and official statements. "Go error debugging" needs exact error strings plus GitHub and Stack Overflow. "Framework comparison" needs benchmarks with disclosed methodology. If the classification is wrong at the start, the rest of the search can be directionally wrong even if the queries look competent.

### 4.2 The Ambiguity Gate Is a Hard Stop

The skill explicitly says **STOP and ASK** when category, goal, entity, or time scope is ambiguous.

This is a strong design choice because one of the biggest wastes in search is not failure to find results, but searching the wrong thing efficiently. Examples include:

- "Apple" meaning the fruit or the company,
- "Redis" meaning concepts, tuning, troubleshooting, or product selection,
- "latest" meaning today, this quarter, or the newest major version.

So the skill does not treat clarification as politeness. It treats it as a cost-control gate that prevents misframed search from propagating downstream.

### 4.3 The Evidence Requirements Gate Is the Skill's Central Axis

One of the most distinctive parts of `google-search` is that it requires a minimum evidence chain to be defined before query construction.

Depending on the conclusion type, it first decides what must exist, for example:

- a single fact needs at least one official or primary source,
- a best-practice recommendation needs one official basis plus one practitioner report,
- a numeric claim needs one primary dataset plus one independent cross-check,
- a technology comparison needs at least two independent benchmarks with methodology,
- a disputed or fast-moving topic needs 3+ sources from different tiers plus conflict resolution.

This design matters because it defines "what kind of evidence is worthy of supporting this conclusion" before deciding "what should I search for?" That keeps the skill from stopping early just because several results appear relevant.

### 4.4 The Language Gate Exists vs. Defaulting to English

Many search workflows silently default to English, but `google-search` makes Language Detection a separate gate and requires an EN / CN / Both decision.

This is a strong design choice because:

- global technology, RFCs, vendor docs, and standards usually belong to English-first search,
- China-specific policy, domestic company information, and Chinese community experience require Chinese-first search,
- many engineering questions need both English official docs and Chinese production experience reports.

This is also why the skill conditionally loads `chinese-search-ecosystem.md`. That reference is not just a bundle of Chinese query examples. It encodes an important operational fact: Google is not the whole Chinese content world, and some WeChat, Xiaohongshu, Douyin, and Baidu-native content should not be forced through Google at all.

### 4.5 The Source Path Gate Prioritizes the Source Over Commentary

`google-search` defines a clear source ranking:

1. official site, official account, original publisher,
2. primary document, dataset, filing, standard, or release note,
3. reputable media or institutions that cite the source correctly,
4. high-quality specialist communities,
5. aggregators, reposts, SEO pages, and commentary.

This solves a common search illusion: highly ranked search results are not necessarily strong evidence. The core preference of the skill is "go to the source first, then read commentary if needed." That makes it especially effective for:

- official documentation retrieval,
- version, release, and status verification,
- policy, statistics, or number-heavy conclusions that require traceable origins.

### 4.6 It Explicitly Separates Quick, Standard, and Deep Modes

`google-search` does not treat every search task as the same type of work. It auto-selects, or accepts from the user, one of three modes:

- Quick,
- Standard,
- Deep.

Each mode carries a different search budget and output requirement.

This is a mature design because search tasks genuinely differ in cost and rigor:

- Quick fits simple factual questions with likely definitive answers,
- Standard fits most default search tasks,
- Deep fits high-conflict, multi-source comparison, and research-style work.

The evaluation demonstrated this clearly: the base model can already find good content, but it does not naturally produce mode, budget, or degradation metadata. The skill's increment is not "searching better" in raw content terms; it is making the search state explicit and reviewable.

### 4.7 The Budget Control Gate Forces Search to Stop

Many searches fail not because too few queries were run, but because the search continued too long without admitting that the framing was wrong. `google-search` sets bounded budgets:

- Quick: 2,
- Standard: 5,
- Deep: 8.

If the budget is exhausted without sufficient evidence, the workflow must stop and report:

- what was found,
- what is still missing,
- what next strategy is most likely to close the gap.

This is especially important because it turns "stopping the search" into a governed decision rather than an arbitrary interruption. The reference `ai-search-and-termination.md` reinforces the same principle: after 8 queries, the problem is often framing, not insufficient clicking.

### 4.8 The Execution Integrity Gate Distinguishes Snippets from Verification

The skill is very strict about execution integrity:

- unexecuted queries must not be presented as executed,
- unopened pages must not be presented as verified,
- snippets must not be treated as full-page confirmation.

This is important because search tools create a strong illusion of completion. A preview snippet can feel like source verification even when the underlying page was never opened.

That is why the skill insists on distinguishing:

- "I found X"
- from "the search snippet mentions X."

What it protects here is not wording nuance. It is evidentiary discipline.

### 4.9 Honest Degradation Is One of the Skill's Core Abilities

`google-search` does not allow evidence gaps to be hidden behind confident language. Instead it requires explicit degradation into:

- Full,
- Partial,
- Blocked.

This is a very high-value design choice. In many search tasks, the highest-quality outcome is not "the most complete-looking answer," but "a clear statement of which parts are confirmed, which are only partially supported, and which could not be verified."

The Deep-mode evaluation for Gin / Echo / Fiber is a good example: with-skill explicitly marks named-company production cases and certain benchmark interpretations as `Partial`; without-skill can still write a strong comparison, but does not elevate those gaps into an explicit delivery-level state.

### 4.10 It Requires Dual Labels for Key Numbers

`google-search` requires each key number to carry both:

- a confidence label,
- and a source-tier label.

This is a strong discipline because numeric claims are often where search results become most misleading. A statement like "735,000 RPS" is not enough unless the answer also says:

- whether the number comes from an official source, primary dataset, or third-party interpretation,
- and whether the confidence should be High, Medium, or Low.

This lets the user distinguish immediately between:

- "a number clearly provided by an official or primary source,"
- and "a number interpreted secondhand from a benchmark page."

This was also one of the clearest skill-only differences in the evaluation.

### 4.11 Reusable Queries Are Part of the Deliverable

The skill does not treat the answer as the end of the search. It requires Primary, Precision, Expansion, and sometimes gap-closing queries to be delivered as part of the result.

This is practical because search answers are rarely one-time consumables. The user often still needs to:

- continue verifying,
- rerun the search with a different date window,
- hand the search path to a teammate.

Reusable queries are what make the result operational rather than disposable. This is also a layer the base model rarely adds on its own.

### 4.12 References Are Strongly Conditional

The references in `google-search` are clearly layered:

- `query-patterns.md` is foundational,
- `programmer-search-patterns.md` loads only for programmer search,
- `source-evaluation.md` loads for source assessment or conflict handling,
- `ai-search-and-termination.md` loads when deciding whether to stop or escalate,
- `high-conflict-topics.md` loads only for high-conflict topics,
- `chinese-search-ecosystem.md` loads only for Chinese or China-centric tasks.

This shows that the skill is deliberate about token-cost control. Not every search needs war-reporting rules or Chinese ecosystem guidance, but when the scenario requires them, those rules become important. This "core rules always present, heavy context only on demand" structure is a key part of the skill's scalability.

### 4.13 Content Access Resilience Is a Necessary Design Layer

The skill also handles a practical limitation: `WebFetch` does not always work against Cloudflare, WAF-protected, or JS-heavy sites.

So it defines a fallback chain:

1. Firecrawl, if the `firecrawl-scrape` skill is available,
2. snippet-only mode,
3. telling the user which platform to search directly.

And in snippet-only mode it requires:

- degrading to `Partial`,
- naming which pages could not be fully accessed,
- lowering confidence accordingly,
- and providing the direct URL.

This is mature design because it treats tool limitations as part of the workflow rather than as an exceptional afterthought.

## 5. Problems This Design Solves

Combining the current `SKILL.md`, key references, and the evaluation report, the skill solves the following problems:

| Problem type | Corresponding design | Practical effect |
|--------------|----------------------|------------------|
| Search goals are underspecified | Scope + Ambiguity Gates | Defines the task before generating queries |
| Evidence standards are fuzzy | Evidence Requirements Gate | Sets the minimum support needed for a conclusion |
| Query language is chosen poorly | Language Detection Gate | Selects EN / CN / Both deliberately |
| Source quality is mixed up | Source Path + Source Evaluation | Prioritizes original sources and explains conflicts |
| Search effort becomes uncontrolled | Mode + Budget Control | Binds search depth to bounded budgets |
| Snippets are mistaken for verification | Execution Integrity Gate | Distinguishes preview, page open, and real verification |
| Weak evidence gets presented as settled | Honest Degradation | Uses Full / Partial / Blocked to express evidence state |
| Users cannot continue searching | Reusable Queries | Preserves the search path as executable follow-up |
| Numeric conclusions are misleading | Confidence + Source-tier labels | Makes numeric credibility immediately visible |

## 6. Key Highlights

### 6.1 It Elevates Search from "Finding Links" to "Finding Evidence"

This is the deepest upgrade in the skill. It is not centered on search-engine mechanics; it is centered on what evidence a conclusion deserves.

### 6.2 Its Evidence-Chain and Degradation System Is the Biggest Differentiator

Many search workflows can find content, but they do not tell you why the result should still be treated as `Partial`. `google-search` makes that explicit.

### 6.3 Its Dual-Label Rule for Numbers Is Exceptionally Strong

The combination of confidence and source tier turns number-heavy answers from "specific-looking" into "credibility-transparent."

### 6.4 It Imposes Real Discipline on Search Budgets and Stop Conditions

That keeps it from spiraling into endless refinement, and from presenting "not found" as if it were proof of absence.

### 6.5 Reusable Queries Give the Result Long-Term Value

The output is not only this answer. It is also the starting point for the next search iteration.

### 6.6 The Current Version Is Closer to a Search Methodology Than to a Retrieval Trick

The evaluation already showed that the base model is not weak on content quality. What it lacks are mode, budget, evidence chain, degradation, source-tier labeling, and reusable queries. In other words, the skill's real increment is search governance rather than search ability itself.

## 7. When to Use It — and When Not To

| Scenario | Suitable | Reason |
|----------|----------|--------|
| Official docs, standards, versions, and status checks | Very suitable | Source-path ranking and evidence chain are highly valuable |
| Programmer troubleshooting and technical lookup | Very suitable | The programmer-search path is mature and explicit |
| Technology comparisons and benchmarks | Suitable | Deep mode and source assessment are important here |
| Public-information gathering | Suitable | But fact and inference must stay separate |
| Chinese or China-centric searches | Suitable | But platform-aware fallback matters |
| High-conflict or fast-changing topics | Suitable | But requires stricter source-tier and degradation discipline |
| Deep synthesis research reports | Not always optimal | `deep-research` may be a better fit |
| Login-walled or JS-heavy full-page retrieval | Not always optimal | Firecrawl or platform-native search may be necessary |

## 8. Conclusion

The real strength of `google-search` is not that it can help find an answer. It is that it systematizes the engineering judgments most often skipped in search work: classify the task first, define the evidence chain, choose language and source path deliberately, control search cost through mode and budget, and then deliver the result with confidence labels, degradation status, and reusable queries.

From a design perspective, the skill embodies a clear principle: **high-quality search is not about searching more; it is about knowing what to search for, what evidence the conclusion requires, when to stop, and how to speak honestly when the evidence is incomplete.** That is why it is especially well suited to factual verification, technical debugging lookup, framework comparison, and source-backed retrieval tasks.

## 9. Document Maintenance

This document should be updated when:

- the Mandatory Gates, mode definitions, Budget Control, Execution Integrity, Honest Degradation, Output Contract, or Content Access Resilience sections in `skills/google-search/SKILL.md` change,
- key rules in `skills/google-search/references/query-patterns.md`, `programmer-search-patterns.md`, `source-evaluation.md`, `ai-search-and-termination.md`, `high-conflict-topics.md`, or `chinese-search-ecosystem.md` change,
- the skill's handling of confidence / source tier, snippet-only fallback, or platform-specific fallback changes materially,
- key supporting conclusions in `evaluate/google-search-skill-eval-report.md` or `evaluate/google-search-skill-eval-report.zh-CN.md` change.

Review quarterly; review immediately if the gates, Output Contract, or source-evaluation logic of `google-search` changes substantially.

## 10. Further Reading

- `skills/google-search/SKILL.md`
- `skills/google-search/references/query-patterns.md`
- `skills/google-search/references/programmer-search-patterns.md`
- `skills/google-search/references/source-evaluation.md`
- `skills/google-search/references/ai-search-and-termination.md`
- `skills/google-search/references/high-conflict-topics.md`
- `skills/google-search/references/chinese-search-ecosystem.md`
- `evaluate/google-search-skill-eval-report.md`
- `evaluate/google-search-skill-eval-report.zh-CN.md`

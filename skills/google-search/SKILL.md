---
name: google-search
description: Use when the user wants help finding information through Google or Google-style web search and expects more than raw links. Handle current facts, public-information lookups, official documents, tutorials, reports, tools, materials, or source discovery by classifying the search goal, generating precise queries, executing search, ranking sources, cross-checking key claims, and returning a concise conclusion plus reusable search strings. Also use for programmer-specific searches (error debugging, official docs, GitHub code search, Stack Overflow, RFC lookup, benchmarks).
allowed-tools: Read, Grep, Glob, WebSearch, WebFetch
---

# Google Search

## Quick Reference

| If you need to… | Go to |
|---|---|
| Mode budgets: Quick (1–2 queries) / Standard (3–5) / Deep (5–8) | §6 Execution Mode Gate |
| Search for Go / Python / JS errors, API docs, or RFCs | Load `references/programmer-search-patterns.md` |
| Search Chinese-language sources (Baidu, Zhihu, WeChat) | Load `references/chinese-search-ecosystem.md` |
| Search on a fast-changing / conflict-prone topic | Load `references/high-conflict-topics.md` |
| Evaluate source quality or resolve conflicting sources | Load `references/source-evaluation.md` |

## Overview

Use this skill to turn vague search requests into a disciplined search-and-verification workflow. Default to doing the search work for the user first, then give them the reusable Google queries and refinement strategy if they want to continue manually.

## Mandatory Gates

Gates execute in strict serial order. Any gate failure blocks all subsequent steps.

```
1) Scope         2) Ambiguity     3) Evidence      4) Language
   Classification → Resolution   → Requirements  → Detection
   │                │               │               │
   category+goal    unclear?        what proof?     EN/CN/Both?
   → classify       → STOP+ASK     → define chain  → set strategy
        │                │               │               │
        5) Source       6) Mode         7) Budget       8) Execution
           Path       →    Selection  →    Control   →    Integrity
           │               │               │               │
           official first? Quick/Std/Deep  max queries     actually searched?
           → rank sources  → auto-select   → enforce       → report honestly
```

### 1) Scope Classification Gate

Map the request into one primary category and one goal before writing any query.

**Categories**:
- Information: news, facts, latest status, company or person updates
- Knowledge: tutorials, best practices, explainers, research, official docs
- Materials: PDFs, reports, templates, images, datasets, downloads
- Tools: apps, services, plugins, utilities, alternatives
- Public-information lookup: public records, bios, publications, profiles
- Programmer search: error debugging, API docs, code examples, benchmarks, RFCs

**Goals**: Know | Learn | Create | Complete a task

### 2) Ambiguity Resolution Gate

**STOP and ASK** if:
- The request maps to multiple categories (e.g., "help me with Redis")
- The goal is ambiguous (know vs. learn vs. troubleshoot)
- The target entity is ambiguous (e.g., "苹果" — fruit or Apple Inc.?)
- The time scope is unclear for time-sensitive topics

Confirm category, goal, and scope before proceeding.

### 3) Evidence Requirements Gate

Before writing any query, define the minimum evidence chain needed to support the conclusion at the expected confidence level. This determines **what to search for**, not just **how to search**.

Confidence is always one of exactly three values — `High`, `Medium`, `Low`. Never invent an
intermediate label such as "Medium-High"; if you are between two levels, take the lower one.

| Conclusion Type | Minimum Evidence Chain | Target Confidence |
|----------------|----------------------|-------------------|
| Single factual claim (date, version, status) | 1 official or primary source | High |
| Best practice or recommendation | 1 official basis + 1 practitioner report | Medium |
| Numeric claim or statistic | 1 primary dataset + 1 independent cross-check, both labeled | High |
| Technology comparison or ranking | 2+ independent benchmarks with disclosed methodology | Medium |
| Person or entity identification | 2+ independent public records with cross-match; linkage stays an inference unless a source states it | Medium |
| Disputed or fast-moving topic | 3+ sources from different tiers + conflict resolution; label every claim separately and give ranges, not point values | Low |

**How to use**: After classifying the question (Gate 1) and resolving ambiguity (Gate 2), map it to one row above. The evidence chain sets the minimum sources you must find — do not write the conclusion until the chain is satisfied, or explicitly degrade (see Honest Degradation).

If the evidence chain cannot be satisfied after the query budget is exhausted, degrade to Partial or Blocked rather than presenting an unsupported conclusion.

### 4) Language Detection Gate

Determine the primary search language based on the evidence chain requirements:
- English-first: global technology, open-source, RFCs, vendor docs, academic papers
- Chinese-first: China-specific policy, domestic companies, local regulations
- Both (paired queries): engineering best practices, production experience, mixed topics

Read `references/chinese-search-ecosystem.md` when Chinese sources are needed.

### 5) Source Path Gate

Choose the source path before exploring broad results. Prefer the source, not commentary about the source.

Default ranking:
1. Official site, official account, original publisher, original document
2. Primary data, paper, PDF, filing, release notes, standards body
3. Reputable media or institutions that cite original material correctly
4. High-quality specialist communities or vertical sites
5. Aggregators, reposts, SEO pages, and summaries

Use domain constraints early when the right source family is obvious.

Read `references/source-evaluation.md` for full ranking and conflict-resolution rules.

### 6) Execution Mode Gate

Auto-select mode based on task signals, then state the selection in output:

| Signal | → Mode |
|--------|--------|
| Simple factual question with likely definitive answer | Quick |
| User says "quick", "fast", "just tell me" | Quick |
| Default for most searches | **Standard** |
| Troubleshooting, best practices, production experience | Standard |
| User says "thorough", "comprehensive", "deep dive" | Deep |
| High-conflict topic (war, election, disaster) | Deep |
| Multi-source comparison or research report | Deep |

**Mode definitions**:

| Mode | Queries | Cross-check | Output |
|------|---------|-------------|--------|
| Quick | 1–2 | Not required if source is official/primary | Conclusion + 1–2 queries |
| Standard | 3–5 | 2 independent sources for key claims | Full 4-section output |
| Deep | 5–8 | 3+ sources, explicit conflict resolution | Full output + source comparison table |

If the user explicitly requests a specific mode, use that mode.

**Quick Mode Fast Path**: When signals clearly point to Quick mode (simple factual question, single-answer expected), collapse gates 1–8 into a single-line internal check and skip gate execution log in the output. Do NOT output per-gate logs for Quick mode — go straight to queries and conclusion.

### 7) Budget Control Gate

Enforce bounded query budgets per mode:
- Quick: max 2 queries
- Standard: max 5 queries (Round 1: 3, Round 2: 2)
- Deep: max 8 queries (Round 1: 3, Round 2: 3, Round 3: 2)

If the budget is exhausted without a satisfactory answer, **stop searching** and report what was found, what remains uncertain, and what next strategy would resolve the gap.

Read `references/ai-search-and-termination.md` for escalation and termination rules.

### 8) Execution Integrity Gate

Never claim a search was performed unless it actually ran.
- If a query was not executed, do not present hypothetical results.
- If a source was not opened, do not claim to have verified its content.
- Never report "confirmed" when the evidence is only from snippets.
- Distinguish between "I found X" and "search snippet mentions X."

## Workflow

After passing all gates:

1. **Build Query Sets** — Prepare Primary, Precision, and Expansion variants (Quick mode may prepare only the first two, since it can execute at most two). Preparing a variant is not executing it: the Gate 7 budget caps executed queries only, and a prepared-but-unrun variant is reported as a reusable query marked `not run`. Read `references/query-patterns.md` for category-specific patterns. For programmer searches, read `references/programmer-search-patterns.md`.

2. **Execute and Triage** — Search with the strongest query first, then refine based on results. Open first-party or original sources before commentary. If the first pass is weak, reformulate by changing one variable at a time (see Refinement Loop in query-patterns.md).

3. **Evaluate and Cross-Check** — Treat results as candidate evidence, not truth. For each important source, judge: originality, recency, directness, specificity, independence. Read `references/source-evaluation.md` for full evaluation protocol.

4. **Write the Answer** — Follow the Output Contract below.

For high-conflict and high-change topics (wars, elections, disasters), read `references/high-conflict-topics.md` for stricter scope-locking and source-tiering.

## Content Access Resilience

`WebFetch` may fail to extract content from sites behind Cloudflare, AWS WAF, or JavaScript-heavy SPAs. When this happens:

### Failure Detection

Recognize blocked responses:
- HTTP 403 Forbidden or empty body from a known-content page
- Response contains "Just a moment...", "Checking your browser", "Enable JavaScript"
- Extracted text is < 30 words from a page that should be content-rich

### Fallback Chain

When `WebFetch` fails, try these in order:

1. **Firecrawl** — If the `firecrawl-scrape` skill is available, use it (handles JS rendering and anti-bot)
2. **Snippet-only mode** — Use search snippets as evidence, but explicitly label: "Based on search snippet, not full page content"
3. **Platform-specific** — Tell the user which platform to search directly (e.g., "This StackOverflow page requires browser access")

### Reporting

When degraded to snippet-only, the answer must:
- Set degradation level to **Partial** (not Full)
- State which sources could not be fully accessed
- Lower confidence labels accordingly
- Provide the direct URL so the user can verify manually

## Anti-Examples — DO NOT Do These

1. **Presenting search snippets as verified facts** — a snippet is a preview, not a confirmed source. Open the page and verify before citing.
   ```
   BAD: "According to search results, the answer is X."
   GOOD: "According to [specific source, date], the answer is X."
   ```

2. **Running one vague query and declaring the search complete** — prepare the Primary / Precision / Expansion set before searching. One executed query is enough only when it was the Precision variant and it landed an official or primary source that directly answers the question; anything less specific means running the next variant, not writing the conclusion.

3. **Ignoring time-sensitivity** — searching "latest Go version" without a date bound surfaces pages from 2019. Technical topics go stale fast.
   ```
   BAD: Go latest features
   GOOD: Go 1.24 new features after:2025-01-01
   ```
   `after:` filters on when the document was **last updated**, not when the event happened, so it thins a stale result set but never proves a claim is current. Take the date from the page itself.

4. **Returning raw links without synthesis** — the user wants an answer, not a link dump. Synthesize first, then provide sources and reusable queries.

5. **Using Google for topics better served by platform-specific search** — WeChat articles, Xiaohongshu reviews, and Douyin content are not well-indexed by Google. Tell the user which platform to search directly.

6. **Verifying an AI-generated claim with another AI tool** — use Google to find original sources. Do not verify AI with AI.

7. **Searching indefinitely without stopping** — respect the query budget. 8 queries without a satisfactory answer means the problem is framing, not insufficient searching.

8. **Omitting confidence and source-tier labels on key numbers** — every key numeric claim must carry both labels. If you cannot label it, do not present it as settled.

## Honest Degradation

When search results are insufficient, degrade explicitly:

| Level | Condition | Action |
|-------|-----------|--------|
| **Full** | The Gate 3 evidence chain is satisfied **and** its sources answer the question asked, directly, at the row's target confidence | Provide direct conclusion with full evidence, citing the page you opened |
| **Partial** | Only derivative or stale sources available | Provide qualified answer + what remains uncertain + next search strategy |
| **Blocked** | No relevant results after budget exhaustion, or content is behind paywall/walled garden | State explicitly what was not found + recommend platform-specific search or AI synthesis tool |

**Decision tree**:

```
Did the budget run out with no relevant evidence at all,
or is the content behind a paywall / inside a walled garden?
  → YES → Blocked (state what was not found + platform/tool recommendation)
  → NO  → Is every link of the Gate 3 evidence chain satisfied?
           → NO  → Partial (name the missing link; do not upgrade on the
                            strength of the links you did get)
           → YES → Do those sources answer the question that was asked,
                    directly, at the row's target confidence?
                     → YES → Full
                     → NO  → Partial (the chain is complete but the sources
                                      answer an adjacent question)
```

Ask about total failure first. Every Blocked case is also a case of an unsatisfied evidence
chain, so testing the chain first would route "budget exhausted, nothing found" to Partial and
leave Blocked unreachable — a Partial promises a qualified answer, which is precisely what you
do not have.

The chain question comes before the source question because a strong source answering an
*adjacent* question is the most common way a Partial gets mislabeled Full: Gate 3 asked for an
official basis plus a practitioner report, one of the two is missing, and the official page that
does exist is about something else. Standard and Deep chains have two or three links, so checking
only the strongest source cannot tell you the chain is complete. And the final branch matters
for the rows whose chain is not official-tier at all — a technology comparison is Full on two
independent benchmarks with disclosed methodology, at target confidence `Medium`.

Never guess to fill gaps. State uncertainty clearly.

## Safety Rules

1. For public-information lookups, use public sources only and separate fact from inference.
2. Never present identity linkage (two records = same person) as confirmed unless sources make it explicit.
3. When sources conflict, explain the conflict rather than picking a side silently.
4. For high-conflict topics, follow the full protocol in `references/high-conflict-topics.md`.
5. Every key numeric claim must carry both a confidence label and a source-tier label.
6. If the evidence is weak, say so and provide the next search strategy instead of guessing.

## Output Contract

Every completed use of this skill must include the fields below. Fields are graded MUST / SHOULD / MAY per mode:

| # | Field | Quick | Standard | Deep |
|---|-------|-------|----------|------|
| 1 | **Execution mode** — Quick / Standard / Deep | MUST | MUST | MUST |
| 2 | **Degradation level** — Full / Partial / Blocked | MUST | MUST | MUST |
| 3 | **Conclusion summary** — answer directly, state exact dates, distinguish fact/inference/unknown | MUST | MUST | MUST |
| 4 | **Evidence chain status** — which links satisfied, which missing | MAY | MUST | MUST |
| 5 | **Key evidence** — strongest sources, what each contributed, cross-check source | MAY | MUST | MUST |
| 6 | **Source assessment** — credibility, gaps, stale dates, disagreements, confidence justification | MAY | SHOULD | MUST |
| 7 | **Key numbers** — `value + date + confidence + source tier`. Both labels must be taken verbatim from the canonical lists in `references/source-evaluation.md` § Numeric Claim Labels — do not coin new ones | MUST (if numbers exist) | MUST (if numbers exist) | MUST (if numbers exist) |
| 8 | **Reusable queries** — copyable queries with precision + expansion variants; mark any query you did not execute as `not run`; prefix a query written for GitHub with `[github-code]` or `[github-repo]` | MUST (≥2) | MUST (≥3) | MUST (≥5) |
| 9 | **Gate execution log** — one-line summary per gate (skip for Quick, recommended for Standard/Deep) | SKIP | SHOULD | SHOULD |

**Quick mode output shape**: render fields 1–2 as a single leading line (`Quick · Full`), then the
conclusion, then the key numbers with their labels, then the reusable queries. No tables, no
per-field headings, no gate log.

What "keep it short" does **not** mean: fields 1, 2, 3, 7 and 8 are MUST in Quick mode and are
never dropped for brevity. The whole of Quick mode is four short lines —

```
Quick · Full
<the answer, one or two sentences>
Key numbers: <value> (`High`, `Official`) · source: <url you opened>
Reusable queries: `<precision query>`, `<primary query>`
```

— so if the metadata is outgrowing the answer, the fix is to compress each field to one line,
not to delete fields. An answer with no labels, no cited URL and no reusable queries has not
used this skill; it has just answered the question.

## Load References Selectively

For every search task, before building queries:
→ Load `references/query-patterns.md` for core query construction patterns (Primary / Precision / Expansion variants), category-specific operators, and one-variable-at-a-time refinement strategy.

When the search category is Programmer search (error debugging, API docs, code examples, benchmarks, RFC lookup):
→ Load `references/programmer-search-patterns.md` for error message normalization, `site:` operator shortcuts per source type (GitHub, Stack Overflow, official docs), and technical evidence quality criteria.

When evaluating whether sources are strong enough to support a claim, or when sources conflict:
→ Load `references/source-evaluation.md` for the source ranking table (Official > Academic > Authoritative secondary > …), conflict resolution rules, originality / recency / directness / independence scoring criteria.

When the topic is Chinese-language or China-centric (content lives in Baidu, Zhihu, WeChat, Weibo):
→ Load `references/chinese-search-ecosystem.md` for content-type-to-source mapping, Chinese-specific search operators, and cross-validation rules for Chinese-only sources.

When the topic involves active conflict, elections, disasters, market moves, or any fast-changing event:
→ Load `references/high-conflict-topics.md` for stricter scope-locking rules, source-tiering requirements (no single outlet, require independent confirmation), and temporal anchoring conventions.

When assessing whether to stop searching or escalate to a different tool (AI search, database query):
→ Load `references/ai-search-and-termination.md` for budget exhaustion thresholds, escalation signals (no new evidence after N queries), and AI-search-vs-Google decision criteria.

When calibrating output quality or validating the report format for the first time:
→ Load `references/worked-examples.md` for fully worked examples across Quick / Standard / Deep modes with complete output contract fields, evidence chain notation, and reusable query formatting.

## Worked Examples (Skeleton)

> Full worked examples with complete Output Contract fields: read `references/worked-examples.md`.

### Example 1: Quick mode

"sync.Pool GC 回收?" → Gates pass → Evidence chain: 1 official source → 2 executed queries (`site:go.dev`) → Full degradation → answer with `High` + `Official` labels, the URL of the page actually opened, and 2 reusable queries. A `Full` verdict without a citable URL is not Full.

### Example 2: Standard mode

"MySQL 连接池配置" → Gates pass → Evidence chain: 1 official basis + 1 practitioner report → 4/5 executed queries (EN + CN) → **Partial** degradation, because the vendors document what the knobs do and no source gives an official sizing number → documented defaults labeled `High` + `Official`, the community headroom factor labeled `Low` + `Practitioner report` → gate execution log.

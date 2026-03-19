---
name: google-search
description: Use when the user wants help finding information through Google or Google-style web search and expects more than raw links. Handle current facts, public-information lookups, official documents, tutorials, reports, tools, materials, or source discovery by classifying the search goal, generating precise queries, executing search, ranking sources, cross-checking key claims, and returning a concise conclusion plus reusable search strings. Also use for programmer-specific searches (error debugging, official docs, GitHub code search, Stack Overflow, RFC lookup, benchmarks).
allowed-tools: Read, Grep, Glob, Bash, WebFetch
---

# Google Search

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

| Conclusion Type | Minimum Evidence Chain | Target Confidence |
|----------------|----------------------|-------------------|
| Single factual claim (date, version, status) | 1 official or primary source | High |
| Best practice or recommendation | 1 official basis + 1 practitioner report | Medium-High |
| Numeric claim or statistic | 1 primary dataset + 1 independent cross-check | High (with labels) |
| Technology comparison or ranking | 2+ independent benchmarks with disclosed methodology | Medium |
| Person or entity identification | 2+ independent public records with cross-match | Medium (inference unless explicit) |
| Disputed or fast-moving topic | 3+ sources from different tiers + conflict resolution | Tiered with ranges |

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

1. **Build Query Sets** — Always prepare at least three query variants (Primary, Precision, Expansion). Read `references/query-patterns.md` for category-specific patterns. For programmer searches, read `references/programmer-search-patterns.md`.

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

2. **Running one vague query and declaring the search complete** — always build at least Primary + Precision + Expansion variants.

3. **Ignoring time-sensitivity** — searching "latest Go version" without `after:` gives you results from 2019. Technical topics go stale fast.
   ```
   BAD: Go latest features
   GOOD: Go 1.24 new features after:2025-01-01
   ```

4. **Returning raw links without synthesis** — the user wants an answer, not a link dump. Synthesize first, then provide sources and reusable queries.

5. **Using Google for topics better served by platform-specific search** — WeChat articles, Xiaohongshu reviews, and Douyin content are not well-indexed by Google. Tell the user which platform to search directly.

6. **Verifying an AI-generated claim with another AI tool** — use Google to find original sources. Do not verify AI with AI.

7. **Searching indefinitely without stopping** — respect the query budget. 8 queries without a satisfactory answer means the problem is framing, not insufficient searching.

8. **Omitting confidence and source-tier labels on key numbers** — every key numeric claim must carry both labels. If you cannot label it, do not present it as settled.

## Honest Degradation

When search results are insufficient, degrade explicitly:

| Level | Condition | Action |
|-------|-----------|--------|
| **Full** | Strong primary source directly answers the question | Provide direct conclusion with full evidence |
| **Partial** | Only derivative or stale sources available | Provide qualified answer + what remains uncertain + next search strategy |
| **Blocked** | No relevant results after budget exhaustion, or content is behind paywall/walled garden | State explicitly what was not found + recommend platform-specific search or AI synthesis tool |

**Decision tree**:

```
Is your strongest source official/primary AND directly answers the question?
  → YES → Full
  → NO  → Is the best source derivative, stale, or from a competing vendor?
           → YES → Partial (state what remains uncertain + next search strategy)
           → NO  → Did you exhaust the query budget without relevant results?
                    → YES → Blocked (state what was not found + platform/tool recommendation)
```

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
| 7 | **Key numbers** — `value + date + confidence (High/Medium/Low) + source tier (Official/Primary/Third-party/OSINT/Adversary)` | MUST (if numbers exist) | MUST | MUST |
| 8 | **Reusable queries** — copyable Google queries with precision + expansion variants | MUST (≥2) | MUST (≥3) | MUST (≥5) |
| 9 | **Gate execution log** — one-line summary per gate (skip for Quick, recommended for Standard/Deep) | SKIP | SHOULD | SHOULD |

## Load References Selectively

| Trigger | Reference | Timing |
|---------|-----------|--------|
| Always (query construction) | `references/query-patterns.md` | Before building queries |
| Category = Programmer search | `references/programmer-search-patterns.md` | Before building queries |
| Source evaluation or conflict | `references/source-evaluation.md` | Before writing answer |
| Chinese-language or China-centric topic | `references/chinese-search-ecosystem.md` | Before choosing source path |
| High-conflict or high-change topic | `references/high-conflict-topics.md` | Before searching |
| Deciding whether to stop or escalate | `references/ai-search-and-termination.md` | After budget check |
| First time using skill, or output quality calibration | `references/worked-examples.md` | Before writing answer |

## Worked Examples (Skeleton)

> Full worked examples with complete Output Contract fields: read `references/worked-examples.md`.

### Example 1: Quick mode

"sync.Pool GC 回收?" → Gates pass → Evidence chain: 1 official source → 2 queries (`site:go.dev`) → Full degradation → answer with `High` + `Official` labels + 2 reusable queries.

### Example 2: Standard mode

"MySQL 连接池配置" → Gates pass → Evidence chain: 1 official + 1 practitioner → 4/5 queries (EN + CN) → Full degradation → formula + pitfalls with `Medium-High` + `Mixed official + practitioner` labels + gate execution log.

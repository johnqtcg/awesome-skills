---
name: deep-research
description: |
  Real-time research workflow for source-backed analysis.
  Use when users ask to research a topic, compare options, investigate claims, analyze trends, or produce synthesis with real citations.
  Handles web research, codebase research, and hybrid (web + codebase) scenarios with mandatory content extraction, hallucination-aware verification, and structured report delivery.
allowed-tools: Read, Grep, Glob, WebFetch, Bash(python3 scripts/deep_research.py*), Bash(git log*)
---

# Deep Research

Source-backed research workflow with mandatory content extraction and hallucination-aware verification.

## Quick Reference

| If you need to… | Go to |
|---|---|
| Understand mode budget limits (Quick 5–10 / Standard 15–25 / Deep 30–50 calls) | §4 Research Mode Gate |
| Understand what the 9-section output must include | §Output Contract + Load `references/output-contract-template.md` |
| Verify claims or guard against hallucination | Load `references/hallucination-and-verification.md` |
| Research error messages, API docs, or Go/Python/JS code | Load `references/research-patterns.md` |

## Mandatory Gates

Gates execute in strict serial order. Any gate failure blocks all subsequent steps.

```
1) Scope        2) Ambiguity     3) Evidence      4) Research
   Classification → Resolution  → Requirements  → Mode
   │                │              │               │
   category+goal    unclear?       what proof?     quick/std/deep?
   → classify       → STOP+ASK   → define chain   → auto-select
        │                │              │               │
        5) Hallucination 6) Budget      7) Content      8) Execution
           Awareness   →    Control  →    Extraction →    Integrity
           │                │              │               │
           verify claims    max calls      read sources    actually ran?
           → never trust    → enforce      → mandatory     → report honestly
```

### 1) Scope Classification Gate

Map the request into one primary category and one goal before any retrieval.

**Categories**:
- Comparative research: tools, technologies, vendors, frameworks
- Trend analysis: market trends, technology adoption, industry shifts
- Claim verification: fact-checking specific assertions with sources
- Technical deep-dive: architecture analysis, performance investigation, protocol study
- Codebase research: internal code patterns, dependency analysis, refactoring impact
- Hybrid research: codebase evidence enriched with external web sources

**Goals**: Know | Compare | Verify | Recommend | Audit

### 2) Ambiguity Resolution Gate

**STOP and ASK** if:
- The research scope is too broad (e.g., "research microservices")
- The comparison dimensions are unclear
- The time frame is unspecified for trend analysis
- The success criteria for the research are not defined

Confirm scope, dimensions, and depth before proceeding.

### 3) Evidence Requirements Gate

Before any retrieval, define the minimum evidence chain:

| Conclusion Type | Minimum Evidence Chain | Target Confidence |
|----------------|----------------------|-------------------|
| Single factual claim | 1 official or primary source + content verified | High |
| Best practice recommendation | 1 official basis + 2 practitioner reports | Medium-High |
| Technology comparison | 3+ independent benchmarks or reviews | Medium |
| Trend or adoption claim | 2+ data sources from different time periods | Medium |
| Disputed or fast-moving topic | 4+ sources from different tiers + conflict resolution | Tiered with ranges |

The evidence chain determines minimum retrieval targets. Do not write conclusions until the chain is satisfied, or explicitly degrade (see Honest Degradation).

### 4) Research Mode Gate

Auto-select mode based on task signals, then state the selection in output:

| Signal | → Mode |
|--------|--------|
| "quick check", single claim verification, one factual question | Quick |
| Default for most research | **Standard** |
| User says "thorough", "comprehensive", "deep dive" | Deep |
| Multi-vendor comparison, architecture decision, trend report | Deep |
| Security-sensitive or production-impacting decision | Deep |

**Mode definitions**:

| Mode | Retrieval Calls | Content Extraction | Sources in Report | Output |
|------|----------------|-------------------|-------------------|--------|
| Quick | 5–10 | Top 5 sources | 3–8 | Concise findings + sources |
| Standard | 15–25 | Top 10 sources | 8–20 | Full report (all 9 sections) |
| Deep | 30–50 | Top 15 sources | 15–40 | Full report + source comparison table |

If the user explicitly requests a specific mode, use that mode.

### 5) Hallucination Awareness Gate

AI-generated research is susceptible to hallucination. This gate enforces verification discipline.

**Never trust without verification**:
- Never fabricate citations, URLs, or source metadata
- Never present unverified claims as fact
- Never use AI tools to verify AI-generated claims — use original sources
- Every key finding must include real URL citations from retrieved sources

**Verification priority by risk level**:

| Risk Level | Information Type | Verification Method |
|-----------|-----------------|-------------------|
| High | API signatures, function behavior, config values | Official documentation |
| High | Statistics, performance benchmarks, adoption numbers | Primary data source |
| High | Security practices, compliance requirements | Official security guides |
| Medium | Architecture recommendations, design patterns | 2+ independent sources |
| Low | Conceptual explanations, general principles | Cross-check if contradicted |

Read `references/hallucination-and-verification.md` for the full verification protocol.

### 6) Budget Control Gate

Enforce bounded retrieval budgets per mode:
- Quick: max 10 retrieval calls
- Standard: max 25 retrieval calls (Round 1: 15, Round 2: 10)
- Deep: max 50 retrieval calls (Round 1: 20, Round 2: 20, Round 3: 10)

Hard ceiling: 50 calls per session. If reached, stop retrieval and report remaining gaps.

Content extraction budget: Quick=5, Standard=10, Deep=15 most relevant sources.

### 7) Content Extraction Gate

**Mandatory**: Read actual source content before forming findings. Search snippets alone are insufficient.

Use `fetch-content` subcommand after retrieval:
```bash
python3 scripts/deep_research.py fetch-content \
  --results /tmp/research_results.json \
  --limit 10 --workers 4 \
  --outputexample /tmp/content.json
```

If content extraction fails for a critical source, record in gaps — do not synthesize from titles/snippets alone.

### 8) Execution Integrity Gate

Never claim research was performed unless it actually ran.
- If retrieval was not executed, do not present hypothetical findings
- If source content was not fetched, do not claim verified conclusions
- Distinguish between "source says X" and "snippet mentions X"
- Report the actual number of sources retrieved, extracted, and cited

## Workflow

After passing all gates:

1. **Scope & Split** — Normalize the question, split into 2–4 subtopics
2. **Retrieve** — Run `retrieve` subcommand per subtopic. For codebase research, use `search-codebase`
3. **Extract Content** — Run `fetch-content` on top N sources (mandatory)
4. **Validate** — Run `validate` to check URL format and citation quality
5. **Synthesize** — Build findings with citations from extracted content
6. **Report** — Generate structured report via `report` subcommand
7. **Deliver** — Follow `references/output-contract-template.md`

For programmer-specific research patterns, read `references/research-patterns.md`.

## Anti-Examples — DO NOT Do These

1. **Synthesizing from snippets without reading sources** — snippets are previews, not evidence. Fetch the actual page content.
   ```
   BAD: Based on search results, Framework X is faster than Y.
   GOOD: According to [TechEmpower Round 23, 2025-02], Framework X handles 1.2M req/s vs Y's 890K req/s.
   ```

2. **Fabricating citations** — never invent URLs, paper titles, or author names. If you cannot find a source, say so.

3. **Presenting AI-generated analysis as source-backed finding** — your reasoning is not a citation. Every finding needs a real URL.
   ```
   BAD: Finding (High): X is better than Y because of architectural advantages.
   GOOD: Finding (High): X outperforms Y by 34% in write-heavy workloads [1][2].
   ```

4. **Running one query and declaring research complete** — always split into subtopics and use multiple query variants.

5. **Ignoring contradictory evidence** — if sources disagree, surface the disagreement. Do not cherry-pick the convenient conclusion.

6. **Skipping content extraction for "obvious" topics** — even well-known topics have nuances. The Gate 7 mandate has no exceptions.

7. **Treating all sources equally** — a vendor's marketing page is not equivalent to an independent benchmark. Source type matters.

8. **Exceeding budget without stopping** — respect the retrieval budget. 50 calls without satisfactory results means the question needs reframing, not more searching.

## Honest Degradation

When research cannot be completed fully, degrade explicitly:

| Level | Condition | Action |
|-------|-----------|--------|
| **Full** | Evidence chain satisfied, content extracted, sources verified | Complete report with all 9 sections |
| **Partial** | Some subtopics lack strong sources, or content extraction partially failed | Report with explicit gaps section, lower confidence on affected findings |
| **Blocked** | Critical sources unreachable, topic requires paywalled/non-indexed content, or budget exhausted without core evidence | State what was not found + recommend alternative research approaches (e.g., "use Perplexity Pro Search for real-time data", "search directly on WeChat for Chinese sources") |

Never fabricate content to fill gaps. Transparency about limitations is more valuable than false completeness.

## Safety Rules

1. Never fabricate citations, URLs, or source metadata
2. Never present unverified claims as fact — every finding needs citations
3. Contradictory evidence must be surfaced, not hidden
4. Always read source content before synthesizing — snippets are insufficient
5. For factual claims, verify against official documentation when available
6. For security-related research, cite official security guides, not blog posts alone
7. Mark findings with appropriate confidence levels (High/Medium/Low)

## Output Contract

Every completed research must include these 9 sections (see `references/output-contract-template.md`):

1. **Research Question** — normalized question + scope + depth mode
2. **Method** — retrieval plan, dedup strategy, validation checks
3. **Executive Summary** — 2–4 sentences answering the question directly
4. **Key Findings** — each with confidence level and citations
5. **Detailed Analysis** — per-subtopic analysis with citations
6. **Consensus vs Debate** — areas of agreement and disagreement
7. **Source Quality Notes** — bias, single-source claims, unverified claims
8. **Sources** — numbered list with title, URL, source type, date
9. **Gaps & Limitations** — missing evidence + follow-up recommendations

## Load References Selectively

For every research task, before generating the final report:
→ Load `references/output-contract-template.md` for the mandatory 9-section output structure (Research Question, Methodology, Executive Summary, Findings, Evidence Chain, Gaps & Limitations, Reusable Queries, Gate Log, Conclusion) with Quick/Standard/Deep mode field requirements.

When any source makes quantitative claims, model-generated content is suspected, or findings are high-stakes:
→ Load `references/hallucination-and-verification.md` for AI hallucination type taxonomy, detection methods per type, cross-checking protocols, and confidence-degradation rules when verification fails.

When the research topic is programmer-specific (error debugging, library evaluation, performance comparison, RFC lookup, GitHub code search):
→ Load `references/research-patterns.md` for query patterns per technical research category, Stack Overflow / GitHub / official-docs source tiers, and programmer-specific evidence quality criteria.

## Subcommands Reference

| Subcommand | Purpose | Key Flags |
|------------|---------|-----------|
| `retrieve` | Search DDG lite, dedupe, save results | `--query`, `--delay`, `--limit-per-query`, `--output` |
| `fetch-content` | Fetch page text (parallel) | `--results` or `--url`, `--limit`, `--workers`, `--output` |
| `search-codebase` | ripgrep search with structured output | `--pattern`, `--root`, `--glob`, `--context`, `--output` |
| `validate` | URL format + citation quality checks | `--results`, `--findings`, `--check-live`, `--output` |
| `report` | Generate markdown report | `--question`, `--results`, `--findings`, `--depth`, `--output` |

## Search Fallback Strategy

The `retrieve` subcommand uses DuckDuckGo Lite with retry logic and anti-bot resilience. When DDG is unavailable or rate-limited, use these fallbacks **in order**:

1. **WebSearch tool** (built-in) — Use Claude Code's native `WebSearch` for the same queries
2. **Firecrawl search** — If the `firecrawl-search` skill is available, use `firecrawl-search` for broader coverage
3. **WebFetch + known URLs** — If you know the target domains, fetch them directly with `WebFetch`
4. **Manual URL list** — Ask the user to provide relevant URLs, then use `fetch-content --url <URL>` to extract content

When degrading to a fallback, report which search method was used in the "Method" section of the report.

## Content Extraction Quality

The `fetch-content` subcommand includes:

- **Content-area detection**: Prioritizes `<main>` and `<article>` elements over full-page text
- **Noise removal**: Strips `<nav>`, `<footer>`, `<aside>`, `<header>`, `<menu>` elements before extraction
- **Anti-bot resilience**: Rotates realistic User-Agent strings, retries on 429/503 with exponential backoff, detects Cloudflare/WAF block pages
- **Quality checks**: Flags pages with low content yield (likely JS-rendered) or WAF blocks in the error field

When `fetch-content` reports errors for critical sources:
- **WAF/anti-bot blocked**: Try `WebFetch` tool as fallback (it uses a real browser)
- **Low content yield**: The page likely requires JavaScript — use `WebFetch` or `firecrawl-scrape`
- **Network errors**: Retry after delay, or skip and document in gaps

## Bundled Assets

- Script: `scripts/deep_research.py` (854 lines — retrieval, extraction, validation, codebase search, report)
- Unit tests: `scripts/tests/test_deep_research.py` (773 lines — 60+ tests for script internals)
- Contract tests: `scripts/tests/test_skill_contract.py` (structural integrity)
- Golden tests: `scripts/tests/test_golden_scenarios.py` (keyword coverage)
- Output contract: `references/output-contract-template.md`
- Verification protocol: `references/hallucination-and-verification.md`
- Research patterns: `references/research-patterns.md`

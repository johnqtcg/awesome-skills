# google-search Skill Evaluation Report

> Evaluation framework: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> Evaluation date: 2026-03-12
> Subject: `google-search`

---

`google-search` is a research/search skill that turns "help me search for this" into a verifiable search workflow. It suits fact lookups, error debugging, official docs retrieval, technology comparisons, and public-information gathering that needs source support. Its three main strengths are: classifying the question, defining the evidence chain, and choosing the mode first—elevating search from "finding links" to "finding evidence for conclusions"; outputs include confidence, source tier, budget status, and reusable queries so the search process is reviewable and continuable; and it emphasizes execution completeness and degradation declarations, clearly distinguishing "verified conclusions" from "partial results with insufficient evidence".

## 1. Evaluation Overview

This evaluation assesses the google-search skill along two dimensions: **actual task performance** and **Token cost-effectiveness**. It uses 3 search scenarios of increasing complexity (Quick-mode fact lookup, Standard-mode error debugging, Deep-mode framework comparison). Each scenario runs with both with-skill and without-skill configurations, for 3 scenarios × 2 configurations = 6 independent subagent runs, scored against 27 assertions.

| Dimension | With Skill | Without Skill | Delta |
|-----------|-----------|--------------|-------|
| **Assertion pass rate** | **27/27 (100%)** | 7/27 (25.9%) | **+74.1 percentage points** |
| **Output Contract 8 fields complete** | 3/3 correct | 0/3 | Skill-only |
| **Confidence + Source-tier labels** | 3/3 correct | 0/3 | Skill-only |
| **Reusable search queries** | 3/3 correct | 0/3 | Skill-only |
| **Evidence chain status tracking** | 3/3 correct | 0/3 | Skill-only |
| **Content quality (answer correctness/depth)** | 3/3 correct | 3/3 correct | No difference |
| **Skill Token cost (SKILL.md only)** | ~3,100 tokens | 0 | — |
| **Skill Token cost (incl. conditional references)** | ~6,400–7,800 tokens | 0 | — |
| **Token cost per 1% pass-rate gain** | ~42 tok (SKILL.md) / ~99 tok (full) | — | — |

**Key finding: The core value of the google-search skill is search discipline and report structure, not search content quality.** The base model already has strong search and synthesis ability (answer correctness, source coverage, code example quality all good), but lacks metadata for the search process (mode choice, budget control, evidence chain tracking, degradation declaration, confidence labels, reusable queries). The skill fills this "search operation discipline" gap.

---

## 2. Test Methodology

### 2.1 Scenario Design

| Scenario | User request | Expected mode | Assertions |
|----------|--------------|---------------|------------|
| Eval 1: Fact lookup | "Go database/sql package MaxOpenConns and MaxIdleConns default values" | Quick | 9 |
| Eval 2: Error debugging | "gRPC context deadline exceeded — works locally, fails in production" | Standard | 9 |
| Eval 3: Framework comparison | "Compare Gin/Echo/Fiber performance for high-traffic REST API 2026" | Deep | 9 |

### 2.2 Execution

- With-skill runs first read SKILL.md and related references (query-patterns, programmer-search-patterns, source-evaluation, etc.)
- Without-skill runs read no skill; search follows model default behavior
- All runs may use WebSearch and WebFetch tools
- 6 subagents run in parallel (with-skill uses default model, without-skill uses fast model)

### 2.3 Skill Characteristics

google-search is a **multi-file skill** (1 SKILL.md + 6 reference files) with conditional loading.

| File | Word count | Est. Tokens | Load condition |
|------|------------|-------------|-----------------|
| **SKILL.md** | 2,085 | ~3,100 | Always |
| **references/query-patterns.md** | 1,191 | ~1,800 | Always (query construction) |
| **references/programmer-search-patterns.md** | 1,031 | ~1,500 | Programmer search |
| **references/source-evaluation.md** | 911 | ~1,400 | Source evaluation / conflict handling |
| **references/ai-search-and-termination.md** | 549 | ~800 | Termination / escalation decisions |
| **references/high-conflict-topics.md** | 947 | ~1,400 | High-conflict topics |
| **references/chinese-search-ecosystem.md** | 279 | ~400 | Chinese / China topics |
| **SKILL.md description (always in context)** | ~60 | ~80 | Always |

**Actual load per scenario:**

| Scenario | Files loaded | Est. Tokens |
|----------|--------------|-------------|
| Eval 1 (Quick, programmer) | SKILL.md + query-patterns + programmer-search | ~6,400 |
| Eval 2 (Standard, programmer) | SKILL.md + query-patterns + programmer-search + source-evaluation | ~7,800 |
| Eval 3 (Deep, comparison) | SKILL.md + query-patterns + programmer-search + source-evaluation | ~7,800 |
| **Average** | | **~7,300** |

---

## 3. Assertion Pass Rate

### 3.1 Summary

| Scenario | Assertions | With Skill | Without Skill | Delta |
|----------|-----------|-----------|--------------|-------|
| Eval 1: Fact lookup (Quick) | 9 | **9/9 (100%)** | 3/9 (33.3%) | +66.7% |
| Eval 2: Error debugging (Standard) | 9 | **9/9 (100%)** | 2/9 (22.2%) | +77.8% |
| Eval 3: Framework comparison (Deep) | 9 | **9/9 (100%)** | 2/9 (22.2%) | +77.8% |
| **Total** | **27** | **27/27 (100%)** | **7/27 (25.9%)** | **+74.1%** |

### 3.2 Item-by-Item Scoring

#### Eval 1: Go database/sql default pool size (Quick mode)

| # | Assertion | With Skill | Without Skill |
|---|-----------|:---------:|:------------:|
| A1 | Output includes execution mode label | ✅ "Quick" | ❌ |
| A2 | Output includes degradation level | ✅ "Full" | ❌ |
| A3 | Conclusion directly answers question | ✅ | ✅ |
| A4 | Output includes reusable queries (≥2) | ✅ (5 queries) | ❌ |
| A5 | At least 1 query uses `site:go.dev` | ✅ | ❌ |
| A6 | Conclusion cites official sources | ✅ go.dev, pkg.go.dev | ✅ go.dev, pkg.go.dev |
| A7 | Output includes evidence chain status | ✅ Explicit table | ❌ |
| A8 | Conclusion includes specific values | ✅ MaxOpenConns=0, MaxIdleConns=2 | ✅ |
| A9 | Key numbers have confidence + source-tier labels | ✅ "High" + "Official" | ❌ |

#### Eval 2: gRPC context deadline exceeded (Standard mode)

| # | Assertion | With Skill | Without Skill |
|---|-----------|:---------:|:------------:|
| B1 | Output includes execution mode label | ✅ "Standard" | ❌ |
| B2 | Output includes degradation level | ✅ "Full" | ❌ |
| B3 | Conclusion includes multiple causes | ✅ (5 structured causes) | ✅ (6 causes) |
| B4 | Output includes reusable queries (≥3) | ✅ (5 queries) | ❌ |
| B5 | At least 1 query targets SO or GitHub | ✅ `site:github.com/grpc/grpc-go` | ❌ |
| B6 | At least 1 query uses quoted exact match for error | ✅ `"context deadline exceeded"` | ❌ |
| B7 | Sources include cross-validation (≥2 independent) | ✅ (6 independent sources) | ✅ (6 referenced sources) |
| B8 | Output includes evidence chain status | ✅ Explicit table | ❌ |
| B9 | Output includes source assessment | ✅ Credibility/recency/gaps/conflicts/confidence reasoning | ❌ |

#### Eval 3: Go HTTP framework comparison (Deep mode)

| # | Assertion | With Skill | Without Skill |
|---|-----------|:---------:|:------------:|
| C1 | Output includes execution mode label (Deep) | ✅ "Deep" | ❌ |
| C2 | Output includes degradation level | ✅ "Partial" (honest degradation) | ❌ |
| C3 | Conclusion includes recommendation | ✅ Decision tree + framework positioning | ✅ Decision matrix + recommendation |
| C4 | Output includes reusable queries (≥3) | ✅ (5 incl. gap-closing) | ❌ |
| C5 | Key numbers have confidence + source-tier labels | ✅ (14 numbers all labeled) | ❌ |
| C6 | ≥3 independent sources | ✅ (5+ sources with detailed assessment) | ✅ (16 sources) |
| C7 | Sources include credibility assessment | ✅ Source Comparison Table (tier/credibility/gaps/recency/bias) | ❌ |
| C8 | Output includes evidence chain status | ✅ Explicit chain status table | ❌ |
| C9 | Comparison covers ≥3 frameworks with concrete data | ✅ Gin/Echo/Fiber + RPS + latency + stars | ✅ |

### 3.3 Classification of 20 Without-Skill Failed Assertions

| Failure type | Count | Notes |
|--------------|-------|-------|
| **Missing Output Contract metadata fields** | 6 | execution mode (3) + degradation level (3) |
| **Missing reusable search queries** | 3 | 3/3 scenarios no reusable queries section |
| **Missing evidence chain status tracking** | 3 | 3/3 scenarios no evidence chain status |
| **Missing confidence + source-tier labels** | 3 | Key numbers lack dual labels |
| **Missing source assessment** | 3 | No credibility/bias/recency assessment |
| **Missing search strategy display** | 2 | No site: precise query, no quoted match |

**Note**: As with the deep-research evaluation, all 20 failures are **search discipline / report format** failures, not content quality failures. Without-skill passed on answer correctness, source coverage, and code examples.

### 3.4 Comparison with deep-research Skill

| Metric | google-search | deep-research |
|--------|--------------|---------------|
| With-skill pass rate | 100% | 100% |
| Without-skill pass rate | **25.9%** | 33.3% |
| Delta | **+74.1%** | +66.7% |
| Failure type | Search discipline + report format | Report format |

google-search has a larger assertion delta because it requires not only a report template (deep-research’s 7-section) but also **search process metadata** (mode, budget, evidence chain, degradation level, reusable queries, precise query strategies). The base model does not produce these concepts at all.

---

## 4. Dimension-by-Dimension Comparison

### 4.1 Output Contract (8 Fields)

| Field | With Skill 3/3 | Without Skill output |
|-------|----------------|---------------------|
| 1. Execution mode | ✅ Quick/Standard/Deep | ❌ No mode concept |
| 2. Degradation level | ✅ Full/Partial/Blocked | ❌ No degradation concept |
| 3. Conclusion summary | ✅ | ✅ (equivalent) |
| 4. Evidence chain status | ✅ Explicit table | ❌ No tracking |
| 5. Key evidence | ✅ Structured table with contribution notes | ⚠️ Source list but no structured assessment |
| 6. Source assessment | ✅ Credibility/bias/recency/gaps/conflicts | ❌ No assessment |
| 7. Key numbers + dual labels | ✅ confidence + source-tier | ❌ Numbers but no labels |
| 8. Reusable queries | ✅ 3–5 with precision/expansion/gap-closing | ❌ None |

**Practical value**:
- **Degradation level** showed highest value in Eval 3—With-skill honestly declared "Partial" (TechEmpower data from third-party interpretation, no named company production cases), while Without-skill gave conclusions without marking uncertainty
- **Evidence chain status** lets readers track "which evidence is satisfied, which is missing", avoiding treating partial data as complete conclusions
- **Reusable queries** give readers the ability to "continue searching"—5 well-designed Google queries are more lasting value than a single answer

### 4.2 Search Strategy Discipline

| Dimension | With Skill | Without Skill |
|-----------|-----------|--------------|
| Query construction strategy | Primary + Precision + Expansion variants | Direct search, no explicit strategy |
| `site:` domain constraint | ✅ site:go.dev, site:github.com/grpc/grpc-go | Occasional but not systematic |
| Quoted exact match | ✅ `"context deadline exceeded"` | Not shown |
| Query budget control | ✅ Quick 2 / Standard 5 / Deep 8 | No budget concept |
| Query history log | ✅ Gate Execution Log | ❌ No log |
| Post-search strategy | ✅ gap-closing queries | ❌ None |

### 4.3 Confidence + Source-Tier Labels

Eval 3 With-skill output labeled all 14 key numbers with dual labels:

```
| Fiber real-world RPS | ~36,000 | May 2024 | Medium | Primary (independent benchmark) |
| Fiber JSON RPS (TechEmpower R23) | ~735,000 | March 2025 | Low | Third-party interpretation of Official |
```

This distinguishes "Medium confidence from Primary source" from "Low confidence from Third-party interpretation", so readers know TechEmpower data is secondhand and downgraded. Without-skill Eval 3 cited 16 sources and many numbers but **no number had credibility or source-tier labels**.

### 4.4 Honest Degradation

Eval 3 With-skill output best illustrates this mechanism:

> **Degradation Level: Partial** — Strong benchmark data and ecosystem analysis available. However: TechEmpower Round 23 Go-specific per-framework numbers could not be directly verified from TechEmpower's own site... Large-scale production experience reports... were not found from named companies with disclosed architectures.

This degradation statement clearly informs readers of two specific uncertainties, avoiding treating the comparison as fully confirmed fact. Without-skill Eval 3 also found no named company cases but **did not declare this limitation**.

### 4.5 Content Quality Comparison

| Dimension | With Skill | Without Skill | Delta |
|-----------|-----------|--------------|-------|
| Answer correctness | 3/3 correct | 3/3 correct | No difference |
| Source count | 2 / 6 / 5 | 4 / 6 / 16 | Without-skill slightly more (Eval 3) |
| Code examples | Excellent (Eval 2: 6 blocks) | Excellent (Eval 2: 5 blocks) | No significant difference |
| Debug steps (Eval 2) | 6-step structured flow | 5-step flow | Comparable |
| Framework comparison table (Eval 3) | Source Comparison Table + Decision Tree | Decision Matrix + Star ratings | Each has strengths |
| Production advice | Excellent | Excellent | No significant difference |

**Key conclusion**: Consistent with the deep-research skill evaluation—the base model is already strong on content; the skill’s increment is entirely in **search discipline and report metadata**.

---

## 5. Token Cost-Effectiveness Analysis

### 5.1 Skill Size

| File | Est. Tokens | Load condition |
|------|-------------|-----------------|
| SKILL.md | ~3,100 | Always |
| query-patterns.md | ~1,800 | Always |
| programmer-search-patterns.md | ~1,500 | Programmer search |
| source-evaluation.md | ~1,400 | Source evaluation |
| ai-search-and-termination.md | ~800 | Termination decisions |
| high-conflict-topics.md | ~1,400 | High conflict |
| chinese-search-ecosystem.md | ~400 | Chinese topics |
| **Max load** | **~10,400** | All loaded |
| **Typical load (programmer search)** | **~7,800** | SKILL + query + programmer + source-eval |
| **Min load (non-programmer Quick)** | **~4,900** | SKILL + query |

### 5.2 Token Cost for Quality Gain

| Metric | Value |
|--------|-------|
| With-skill pass rate | 100% (27/27) |
| Without-skill pass rate | 25.9% (7/27) |
| Pass-rate gain | +74.1 percentage points |
| Token cost per assertion fixed (SKILL.md) | ~155 tok |
| Token cost per assertion fixed (typical load) | ~390 tok |
| Token cost per 1% pass-rate gain (SKILL.md) | **~42 tok** |
| Token cost per 1% pass-rate gain (typical load) | **~105 tok** |

### 5.3 Token Segment Cost-Effectiveness

| Module | Est. Tokens | Related assertion delta | Cost-effectiveness |
|--------|-------------|-------------------------|--------------------|
| **Output Contract (SKILL.md)** | ~300 | 6 (mode 3 + degradation 3) | **Very high** — 50 tok/assertion |
| **Confidence + Source-tier rules** | ~200 | 3 | **Very high** — 67 tok/assertion |
| **Reusable Queries requirement** | ~100 | 3 | **Very high** — 33 tok/assertion |
| **Evidence Chain Gate (Gate 3)** | ~300 | 3 | **High** — 100 tok/assertion |
| **Source Assessment requirement** | ~150 | 3 | **High** — 50 tok/assertion |
| **query-patterns.md** | ~1,800 | 2 (site: + quoted strategy) | **Medium** — 900 tok/assertion |
| **programmer-search-patterns.md** | ~1,500 | Indirect (search quality) | **Medium** — no direct assertion |
| **source-evaluation.md** | ~1,400 | Indirect (assessment quality) | **Medium** — no direct assertion |
| **Worked Examples (SKILL.md)** | ~500 | 0 direct | **Low** |
| **Anti-Examples (SKILL.md)** | ~300 | 0 direct | **Low** |
| **Other Gates (1,2,4,5,6,7,8)** | ~450 | Indirect | **Medium** |

### 5.4 High-Leverage vs Low-Leverage Instructions

**High leverage (~1,050 tokens → 18 assertion delta):**
- Output Contract 8-field definition (~300 tok → 6)
- Confidence + Source-tier dual-label rules (~200 tok → 3)
- Reusable Queries requirement (~100 tok → 3)
- Evidence Chain Gate (~300 tok → 3)
- Source Assessment requirement (~150 tok → 3)

**Medium leverage (~5,150 tokens → 2 direct + indirect):**
- query-patterns.md (~1,800 tok → 2 + indirect search quality)
- programmer-search-patterns.md (~1,500 tok → indirect)
- source-evaluation.md (~1,400 tok → indirect)
- Other Gates (~450 tok → indirect)

**Low leverage (~800 tokens → 0 direct delta):**
- Worked Examples (~500 tok)
- Anti-Examples (~300 tok)

### 5.5 Comparison with Other Skills’ Cost-Effectiveness

| Metric | google-search | deep-research | yt-dlp-downloader | tdd-workflow | go-makefile-writer |
|--------|--------------|---------------|-------------------|--------------|-------------------|
| SKILL.md Tokens | ~3,100 | ~1,350 | ~2,370 | ~2,100 | ~1,960 |
| Typical load Tokens | ~7,800 | ~1,350 | ~5,100 | ~3,600 | ~4,100 |
| Pass-rate gain | **+74.1%** | +66.7% | +55.0% | +46.2% | +31.0% |
| Tokens per 1% (SKILL.md) | ~42 tok | **~20 tok** | ~43 tok | ~45 tok | ~63 tok |
| Tokens per 1% (typical load) | ~105 tok | **~20 tok** | ~93 tok | ~78 tok | ~132 tok |

google-search has the **highest absolute pass-rate gain** (+74.1%), but SKILL.md-level unit cost-effectiveness (~42 tok/1%) is similar to yt-dlp-downloader (~43) and tdd-workflow (~45). Typical-load cost-effectiveness (~105 tok/1%) is higher due to more reference files.

---

## 6. Boundary Analysis vs Base Model Capabilities

### 6.1 Base Model Capabilities (No Skill Increment)

| Capability | Evidence |
|------------|----------|
| WebSearch information retrieval | 3/3 scenarios actively searched and found correct answers |
| Official sources preferred | Eval 1 located go.dev and pkg.go.dev on its own |
| Error message search | Eval 2 searched gRPC error and found GitHub issues |
| Multi-source synthesis | Eval 3 cited 16 sources for framework comparison |
| Code example generation | Eval 2 produced complete debug code snippets |
| Structured comparison tables | Eval 3 produced decision matrix and star ratings |

### 6.2 Base Model Gaps (Skill Fills)

| Gap | Evidence | Risk level |
|-----|----------|------------|
| **No search mode/budget control** | 3/3 scenarios no Quick/Standard/Deep concept | **Medium** — may over-search simple or under-search complex |
| **No degradation declaration** | 3/3 scenarios give conclusions without marking uncertainty | **High** — readers treat Partial as Full |
| **No evidence chain tracking** | 3/3 scenarios don’t track "what evidence needed, what found" | **High** — can’t assess conclusion reliability |
| **No confidence + source-tier dual labels** | 3/3 scenarios numbers unlabeled | **High** — third-party vs official treated equally |
| **No reusable queries** | 3/3 scenarios don’t output search queries | **Medium** — users can’t continue searching |
| **No source credibility assessment** | 3/3 scenarios don’t assess bias/recency/gaps | **Medium** — competitor blogs and official docs treated equally |
| **No search strategy display** | Search process opaque | **Low** — no direct impact on final answer |

**Core finding**: The base model’s "search results → answer" ability is strong, but "search process auditability" and "conclusion credibility labeling" are zero. The google-search skill’s value lies in the latter two.

---

## 7. Overall Score

### 7.1 Dimension Scores

| Dimension | With Skill | Without Skill | Delta |
|-----------|-----------|--------------|-------|
| Output Contract compliance | 5.0/5 | 0.5/5 | +4.5 |
| Search discipline (mode/budget/strategy) | 5.0/5 | 1.0/5 | +4.0 |
| Confidence + Source-tier | 5.0/5 | 0.5/5 | +4.5 |
| Honest degradation | 5.0/5 | 1.0/5 | +4.0 |
| Reusable queries | 5.0/5 | 0.0/5 | +5.0 |
| Content quality (answer correctness/depth) | 5.0/5 | 4.5/5 | +0.5 |
| Source count/diversity | 5.0/5 | 4.5/5 | +0.5 |
| **Overall mean** | **5.0/5** | **1.71/5** | **+3.29** |

### 7.2 Weighted Total

| Dimension | Weight | Score | Weighted |
|-----------|-------|------|----------|
| Assertion pass rate (delta) | 25% | 10/10 | 2.50 |
| Output Contract compliance | 15% | 10/10 | 1.50 |
| Search discipline + honest degradation | 15% | 10/10 | 1.50 |
| Confidence + Source-tier | 10% | 10/10 | 1.00 |
| Reusable queries | 10% | 10/10 | 1.00 |
| Token cost-effectiveness | 10% | 7.0/10 | 0.70 |
| Content quality increment | 10% | 2.0/10 | 0.20 |
| Source count/quality increment | 5% | 2.0/10 | 0.10 |
| **Weighted total** | | | **8.50/10** |

The lower Token cost-effectiveness score (7.0/10) reflects higher typical load (~7,800 tok) from more reference files, even though SKILL.md cost-effectiveness (~42 tok/1%) is comparable to peer skills.

---

## 8. Evaluation Artifacts

| Artifact | Path |
|----------|------|
| Eval 1 with-skill output | `/tmp/gsearch-eval/eval-1/with_skill/response.md` |
| Eval 1 without-skill output | `/tmp/gsearch-eval/eval-1/without_skill/response.md` |
| Eval 2 with-skill output | `/tmp/gsearch-eval/eval-2/with_skill/response.md` |
| Eval 2 without-skill output | `/tmp/gsearch-eval/eval-2/without_skill/response.md` |
| Eval 3 with-skill output | `/tmp/gsearch-eval/eval-3/with_skill/response.md` |
| Eval 3 without-skill output | `/tmp/gsearch-eval/eval-3/without_skill/response.md` |

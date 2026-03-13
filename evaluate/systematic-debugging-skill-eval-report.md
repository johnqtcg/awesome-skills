# systematic-debugging Skill Evaluation Report

> Evaluation framework: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> Evaluation date: 2026-03-11
> Subject: `systematic-debugging`

---

`systematic-debugging` is a debugging skill that emphasizes "find root cause first, then fix", suitable for test failures, production anomalies, intermittent issues, performance regressions, and third-party integration failures. Its core goal is to avoid guesswork-based patching. Its three main strengths are: breaking the debugging process into clear phases and requiring investigation before proposing permanent fixes; emphasizing explicit hypotheses, evidence collection, and complete investigation steps so debug reports are more verifiable and less speculative; and built-in severity triage that supports stopping the bleed in urgent failures while insisting on returning to root-cause analysis afterward.

## 1. Evaluation Overview

This evaluation assesses the systematic-debugging skill along two dimensions: **actual task performance** and **Token cost-effectiveness**. It uses 3 debugging scenarios of increasing complexity (Go test failure, multi-layer error mapping bug, intermittent empty result). Each scenario runs with both with-skill and without-skill configurations, for 3 scenarios × 2 configurations = 6 independent subagent runs, scored against 40 assertions.

| Dimension | With Skill | Without Skill | Delta |
|-----------|-----------|--------------|-------|
| **Assertion pass rate** | **40/40 (100%)** | 29/40 (72.5%) | **+27.5 percentage points** |
| **Phase structure** | 3/3 correct | 0/3 | Largest single-item delta |
| **Explicit hypothesis statement** | 3/3 | 0/3 | Skill-only |
| **Investigation step completeness** | 3/3 | 0/3 | At least 1 step missing |
| **Skill Token cost (SKILL.md)** | ~2,000 tokens | 0 | — |
| **Skill Token cost (incl. references)** | ~3,000 tokens | 0 | — |
| **Token cost per 1% pass-rate gain** | ~73 tokens (SKILL.md only) / ~109 tokens (full) | — | — |

---

## 2. Test Methodology

### 2.1 Scenario Design

All scenarios use real code from the issue2md project (`/Users/john/issue2md`) to construct debugging tasks.

| Scenario | Target file | Core focus | Assertions |
|----------|-------------|------------|------------|
| Eval 1: Test failure | `frontmatter.go` `yamlQuote` | Single-function bug: multiline string breaks YAML output | 14 |
| Eval 2: Error status code | `graphql_client.go` → `handler.go` | Multi-layer call chain: GraphQL error not classified, causing 502 | 13 |
| Eval 3: Intermittent empty summary | `summary_openai.go` | Intermittent bug: LLM output has trailing comma causing JSON validation failure | 13 |

### 2.2 Assertion Design Principles

Assertions focus on **debug process discipline**, not final bug fix quality. Core checks:

| Dimension | Check content | Assertions covered |
|-----------|---------------|---------------------|
| Phase 1 completeness | Read error, reproduce, check history, trace data flow, collect evidence | 15 |
| Phase 2 completeness | Working example comparison, diff analysis | 3 |
| Phase 3 completeness | Explicit hypothesis statement, minimal test | 6 |
| Phase 4 completeness | Failing test, single fix, verification, no incidental changes | 12 |
| Structure discipline | Phase order compliance | 3 |
| Anti-impulse discipline | No fix before investigation | 1 |

### 2.3 Execution

- With-skill runs first read `SKILL.md` and `root-cause-tracing.md` reference
- Without-skill runs read no skill; debugging follows model default behavior
- All runs execute in independent subagents

---

## 3. Assertion Pass Rate

### 3.1 Summary

| Scenario | Assertions | With Skill | Without Skill | Delta |
|----------|-----------|-----------|--------------|-------|
| Eval 1: Test failure | 14 | **14/14 (100%)** | 9/14 (64.3%) | +35.7% |
| Eval 2: Multi-layer bug | 13 | **13/13 (100%)** | 11/13 (84.6%) | +15.4% |
| Eval 3: Intermittent bug | 13 | **13/13 (100%)** | 9/13 (69.2%) | +30.8% |
| **Total** | **40** | **40/40 (100%)** | **29/40 (72.5%)** | **+27.5%** |

### 3.2 Classification of 11 Without-Skill Failed Assertions

| Failure type | Count | Evals | Notes |
|--------------|-------|-------|-------|
| **Phase structure missing** | 3 | 1/2/3 | Flat structure (Symptom → Root Cause → Fix), no Phase 1→2→3→4 |
| **Explicit hypothesis missing** | 3 | 1/2/3 | Jump from root cause to fix, no "I think X because Y" hypothesis verification |
| **Reproduction attempt missing** | 1 | 1 | No description of how to trigger bug or whether reliably reproducible |
| **Change history check missing** | 1 | 1 | No git history or recent change check |
| **Working example comparison missing** | 1 | 1 | No comparison with existing working cases |
| **Existing test review missing** | 1 | 3 | No check of what existing tests cover or miss |
| **Fix verification missing** | 1 | 3 | Proposed fix but no demonstration of running test to confirm |

### 3.3 Trend: Skill Advantage vs Scenario Characteristics

| Scenario characteristic | With-Skill advantage | Analysis |
|-------------------------|---------------------|----------|
| Eval 1 (simple, single-point) | +35.7% (5 failures) | Simple bugs most likely to skip investigation; Skill’s Iron Law forces full flow |
| Eval 2 (multi-layer, complex) | +15.4% (2 failures) | Complex scenarios naturally need layered analysis; base model does more complete investigation |
| Eval 3 (intermittent, subtle) | +30.8% (4 failures) | Intermittent bugs’ "silent failure" needs systematic evidence collection; without-skill lacks process rigor |

**Key finding**: The skill’s largest value is in **simple bug scenarios** (Eval 1: +35.7%) and **intermittent bug scenarios** (Eval 3: +30.8%). This aligns with the skill’s "When to Use — Use this ESPECIALLY when 'Just one quick fix' seems obvious" design intent.

---

## 4. Dimension-by-Dimension Comparison

### 4.1 Phase Structure (Largest Delta Dimension)

This is the **most consistent difference across all 3 scenarios**: with-skill uses Phase 1→2→3→4 structure; without-skill uses flat structure.

| Dimension | With Skill | Without Skill |
|-----------|-----------|--------------|
| Phase 1: Root Cause Investigation | ✅ 3/3 separate section with sub-steps | ❌ Mixed in "Root Cause" paragraph |
| Phase 2: Pattern Analysis | ✅ 3/3 separate section | ❌ 0/3 missing or implicit |
| Phase 3: Hypothesis and Testing | ✅ 3/3 explicit hypothesis | ❌ 0/3 missing |
| Phase 4: Implementation | ✅ 3/3 RED→GREEN→Verify | ⚠️ 2/3 have fix and test but no verification flow |

**Analysis**: The base model’s default debugging pattern is **Root Cause → Fix → Test**, skipping Pattern Analysis and Hypothesis. The skill’s four-phase framework enforces extra analysis cycles; this is especially clear in Eval 2—with-skill’s Phase 2 explicitly compared REST vs GraphQL working/broken paths, while without-skill did similar comparison but embedded in root-cause analysis rather than a separate step.

**Practical value**: The four-phase structure ensures:
- Investigation doesn’t jump to fix as soon as root cause is seen (Phase 2 guard)
- There is an explicit verifiable hypothesis before fix (Phase 3 guard)
- Red/green verification loop after fix (Phase 4 discipline)

### 4.2 Explicit Hypothesis Statement (Skill-Only)

| Scenario | With Skill hypothesis | Without Skill |
|----------|----------------------|--------------|
| Eval 1 | "The root cause is that `yamlQuote` does not handle newline characters. Replacing `\r\n`, `\r`, and `\n` with spaces..." | No hypothesis, directly "Fix Applied" |
| Eval 2 | "`queryRaw()` line 144-146 uses `fmt.Errorf` with `%s`, creating plain unclassified error..." | No hypothesis, directly "Proposed Fix" |
| Eval 3 | "`normalizeSummaryJSON` does not strip trailing commas... `json.Valid()` returns false..." | No hypothesis, directly "Proposed Fix" |

**Analysis**: Without-skill skipped the explicit hypothesis step in all 3 scenarios. Although root-cause descriptions implied hypotheses, the lack of "I think X because Y" means:
- Can’t distinguish "confirmed root cause" from "guessed root cause"
- Can’t design minimal verification experiments to rule out alternatives
- In complex bugs, may lead to "fixing symptom not root cause"

The skill’s Phase 3 rule "Form Single Hypothesis — State clearly: 'I think X is the root cause because Y'" effectively removes this gap.

### 4.3 Investigation Completeness

Some Phase 1 sub-steps in with-skill are missing in without-skill:

| Phase 1 sub-step | With Skill | Without Skill | Missing in |
|------------------|-----------|--------------|------------|
| Read error message | 3/3 | 3/3 | — |
| Reproduction confirmation | 3/3 | 2/3 | Eval 1 |
| Check change history | 3/3 | 2/3 | Eval 1 |
| Data flow tracing | 3/3 | 3/3 | — |
| Evidence collection (multi-component) | 3/3 | 3/3 | — |
| Working example comparison | 3/3 | 2/3 | Eval 1 |
| Existing test review | 3/3 | 2/3 | Eval 3 |

**Analysis**: The base model is strong on **reading error messages** and **data flow tracing** (3/3), but inconsistent on **reproduction confirmation**, **change history**, and **working example comparison**. Eval 1 (simplest scenario) had the most gaps, suggesting simple bugs more easily trigger step omission.

### 4.4 Bug Fix Quality Comparison

All 6 agents correctly identified the root cause and proposed equivalent fixes:

| Scenario | With Skill fix | Without Skill fix | Quality delta |
|----------|----------------|-------------------|---------------|
| Eval 1 | `strings.NewReplacer` for newlines | `strings.NewReplacer` for newlines | No difference |
| Eval 2 | Add `Type` field + `isGraphQLNotFoundError` + `%w` | Add `Type` field + `isGraphQLNotFoundError` + `%w` | No difference |
| Eval 3 | `stripTrailingCommas()` character-level parse | `removeTrailingCommas()` regex | Minor (different implementation, functionally equivalent) |

**Key finding**: **The base model’s bug fix ability is already strong.** The skill’s value is not improving fix quality but **enforcing structured process**, ensuring:
- Full understanding before fix (prevents "symptom fix")
- Hypothesis verified (prevents "fixed by luck")
- Fix goes through full red/green verification loop

---

## 5. Token Cost-Effectiveness Analysis

### 5.1 Skill Size

| File | Lines | Words | Est. Tokens |
|------|-------|-------|-------------|
| **SKILL.md** | 296 | 1,504 | ~2,000 |
| root-cause-tracing.md | 169 | 739 | ~1,000 |
| defense-in-depth.md | 122 | 494 | ~650 |
| condition-based-waiting.md | 115 | 498 | ~650 |
| condition-based-waiting-example.ts | 158 | 667 | ~870 |
| find-polluter.sh | 63 | 214 | ~280 |
| test-*.md + test-academic.md | 209 | 1,221 | ~1,600 |
| CREATION-LOG.md | 119 | 612 | ~800 |
| **Description (always in context)** | — | ~15 | ~20 |

**Actual load in evaluation:**

| Config | Files read | Total Tokens |
|--------|------------|--------------|
| Eval 1/2/3 with-skill | SKILL.md + root-cause-tracing.md | ~3,000 |
| SKILL.md only (minimal) | SKILL.md | ~2,000 |
| Full load (extreme) | All .md + .sh + .ts | ~7,850 |

### 5.2 Token Cost for Quality Gain

| Metric | Value |
|--------|-------|
| With-skill pass rate | 100% (40/40) |
| Without-skill pass rate | 72.5% (29/40) |
| Pass-rate gain | +27.5 percentage points |
| Token cost per assertion fixed | ~182 tokens (SKILL.md only) / ~273 tokens (full) |
| Token cost per 1% pass-rate gain | ~73 tokens (SKILL.md only) / ~109 tokens (full) |

### 5.3 Token Segment Cost-Effectiveness

SKILL.md content split by functional module:

| Module | Est. Tokens | Related assertion delta | Cost-effectiveness |
|--------|-------------|-------------------------|--------------------|
| **Iron Law + Phase order** | ~120 | 3 (Phase structure) | **Very high** — 40 tok/assertion |
| **Phase 3: Hypothesis rules** | ~150 | 3 (explicit hypothesis) | **Very high** — 50 tok/assertion |
| **Phase 1: 5-step investigation checklist** | ~400 | 3 (reproduce/history/compare/test review) | **High** — 133 tok/assertion |
| **Phase 4: Implementation discipline** | ~250 | 1 (verification) | **Medium** — 250 tok/assertion |
| **Phase 2: Pattern Analysis** | ~150 | 1 (working example comparison) | **Medium** — 150 tok/assertion |
| **Red Flags checklist** | ~200 | Indirect (reinforces no-skip discipline) | **Medium** — no direct assertion |
| **Common Rationalizations table** | ~150 | Indirect (resists "quick fix" temptation) | **Medium** — no direct assertion |
| **"When to Use" section** | ~180 | 0 (scenario matching set by evaluation) | **Low** — no increment in evaluation |
| **Phase 4.5: Architecture questioning** | ~200 | 0 (evaluation didn’t cover 3+ failed-fix scenarios) | **Low** — not tested |
| **Supporting Techniques pointer** | ~50 | 0 (pointer only) | **Low** — low information density |
| **root-cause-tracing.md** | ~1,000 | Indirect (Eval 2 multi-layer tracing) | **Medium** — aids tracing but base model also does it |

### 5.4 High-Leverage vs Low-Leverage Instructions

**High leverage (~670 tokens SKILL.md → 10 assertion delta):**
- Iron Law + Phase order (120 tok → 3)
- Phase 3 Hypothesis rules (150 tok → 3)
- Phase 1 five-step investigation checklist (400 tok → 4)

**Medium leverage (~750 tokens → indirect):**
- Phase 4 implementation discipline (250 tok → 1 direct + red/green flow indirect)
- Phase 2 Pattern Analysis (150 tok → 1)
- Red Flags + Rationalizations (350 tok → anti-impulse discipline indirect)

**Low leverage (~430 tokens → 0 delta):**
- "When to Use" section (180 tok) — scenario matching set by evaluation
- Phase 4.5 Architecture questioning (200 tok) — not tested
- Supporting Techniques pointer (50 tok) — low information density

**References (~1,000 tokens root-cause-tracing.md → indirect):**
- Aided Eval 2 multi-layer tracing structure, but base model also did well on multi-layer tracing

### 5.5 Token Efficiency Rating

| Rating | Conclusion |
|--------|------------|
| **Overall ROI** | **Excellent** — ~3,000 tokens for +27.5% pass rate |
| **SKILL.md ROI** | **Excellent** — ~2,000 tokens contains all high-leverage rules |
| **High-leverage token share** | ~34% (670/2,000) directly contributes 10/11 assertion delta |
| **Low-leverage token share** | ~22% (430/2,000) contributes nothing in this evaluation |
| **Reference cost-effectiveness** | **Medium** — ~1,000 tokens root-cause-tracing.md provides indirect gain |

### 5.6 Comparison with Other Skills’ Cost-Effectiveness

| Metric | systematic-debugging | go-makefile-writer | security-review | google-search |
|--------|---------------------|-------------------|-----------------|--------------|
| SKILL.md Tokens | ~2,000 | ~1,960 | ~3,700 | ~2,200 |
| Total load Tokens | ~3,000 | ~4,100–4,600 | ~5,000–9,600 | ~3,600 |
| Pass-rate gain | +27.5% | +31.0% | +50.0% | +74.1% |
| Tokens per 1% (SKILL.md) | ~73 tok | ~63 tok | ~74 tok | ~30 tok |
| Tokens per 1% (full) | ~109 tok | ~149 tok | ~100–192 tok | ~49 tok |

systematic-debugging’s SKILL.md cost-effectiveness (73 tok/1%) is in the same range as go-makefile-writer (63 tok/1%) and security-review (74 tok/1%)—a **high-efficiency skill**.

---

## 6. Boundary Analysis vs Base Model Capabilities

### 6.1 Base Model Capabilities (No Skill Increment)

| Capability | Evidence |
|------------|----------|
| Accurately read error messages | 3/3 scenarios correctly parsed error output |
| Data flow tracing (single and multi-layer) | 3/3 scenarios traced to root cause |
| Correctly identify root cause | 3/3 scenarios root cause consistent |
| Write equivalent fix code | 3/3 scenarios fixes functionally equivalent |
| Write table-driven tests | 3/3 scenarios produced similar tests |
| Multi-component boundary analysis | Eval 2 detailed 5-layer component analysis |
| Intermittent bug symptom→cause mapping | Eval 3 correctly explained "why intermittent" |

### 6.2 Base Model Gaps (Skill Fills)

| Gap | Evidence | Risk level |
|-----|----------|------------|
| **Phase structure missing** | 3/3 scenarios use flat structure | High — can’t distinguish investigation, analysis, verification, implementation |
| **Explicit hypothesis missing** | 3/3 scenarios jump from root cause to fix | High — may "fix by luck" on complex bugs |
| **Reproduction confirmation inconsistent** | 1/3 scenarios skipped | Medium — simple bugs more likely to omit |
| **Change history check inconsistent** | 1/3 scenarios skipped | Low — scenario-dependent |
| **Working example comparison missing** | 1/3 scenarios skipped | Medium — Pattern Analysis prevents repeat bugs |
| **Existing test review inconsistent** | 1/3 scenarios skipped | Medium — may miss test coverage gaps |
| **Fix verification inconsistent** | 1/3 scenarios skipped | High — unverified fix may introduce new bugs |

### 6.3 Skill Value Proposition

The systematic-debugging skill’s core value is not **improving bug fix ability** (the base model is already strong) but **enforcing debugging discipline**:

1. **Prevent skipping steps**: Iron Law + Phase structure forces investigation before fix
2. **Explicit hypothesis verification**: Phase 3 ensures fix is based on verified hypothesis, not intuition
3. **Investigation checklist completeness**: Phase 1’s 5-step checklist ensures no key step is missed
4. **Anti-impulse mechanism**: Red Flags + Rationalizations table is especially effective in "simple bug" scenarios

This is like a flight checklist—not because pilots don’t know how to fly, but to ensure critical steps aren’t skipped when things seem "too simple" or "too urgent".

---

## 7. Overall Score

### 7.1 Dimension Scores

| Dimension | With Skill | Without Skill | Delta |
|-----------|-----------|--------------|-------|
| Phase structure | 5.0/5 | 1.0/5 | +4.0 |
| Hypothesis verification discipline | 5.0/5 | 1.0/5 | +4.0 |
| Investigation completeness | 5.0/5 | 3.5/5 | +1.5 |
| Fix quality | 5.0/5 | 4.5/5 | +0.5 |
| Test coverage | 5.0/5 | 4.0/5 | +1.0 |
| Verification discipline (red/green loop) | 5.0/5 | 3.5/5 | +1.5 |
| **Overall mean** | **5.0/5** | **2.92/5** | **+2.08** |

### 7.2 Weighted Total

| Dimension | Weight | Score | Weighted |
|-----------|-------|------|----------|
| Assertion pass rate (delta) | 25% | 8.5/10 | 2.13 |
| Phase structure | 20% | 10/10 | 2.00 |
| Hypothesis verification discipline | 15% | 10/10 | 1.50 |
| Investigation completeness | 15% | 9.0/10 | 1.35 |
| Token cost-effectiveness | 15% | 8.5/10 | 1.28 |
| Bug fix quality increment | 10% | 5.0/10 | 0.50 |
| **Weighted total** | | | **8.76/10** |

**Lower Bug fix quality increment score (5.0/10)**: The base model’s fix ability is already strong; the skill’s contribution is mainly process discipline, not result quality.

---

## 8. Evaluation Artifacts

| Artifact | Path |
|----------|------|
| Eval 1 with-skill output | `/tmp/debug-eval/eval-1/with_skill/response.md` |
| Eval 1 without-skill output | `/tmp/debug-eval/eval-1/without_skill/response.md` |
| Eval 2 with-skill output | `/tmp/debug-eval/eval-2/with_skill/response.md` |
| Eval 2 without-skill output | `/tmp/debug-eval/eval-2/without_skill/response.md` |
| Eval 3 with-skill output | `/tmp/debug-eval/eval-3/with_skill/response.md` |
| Eval 3 without-skill output | `/tmp/debug-eval/eval-3/without_skill/response.md` |
| Target code | `/Users/john/issue2md/internal/converter/` |
| Target code | `/Users/john/issue2md/internal/github/` |
| Target code | `/Users/john/issue2md/internal/webapp/` |

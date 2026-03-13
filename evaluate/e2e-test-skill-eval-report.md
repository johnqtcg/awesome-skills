# e2e-best-practise Skill Evaluation Report

> Evaluation framework: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> Evaluation date: 2026-03-11
> Evaluation target: `e2e-test`

---

`e2e-test` is an end-to-end testing practice skill for critical user journeys. It supports designing E2E coverage strategy, handling flaky tests, defining CI gates, and turning exploratory verification into maintainable automated tests. Its three main strengths are: preferring Agent Browser for exploration and reproduction, then Playwright or the project’s native test framework for code, with a clear tool path; built-in environment gates, runner selection, and result-strength control for honest degradation across tech stacks instead of rigid templates; and structured output plus machine-readable JSON for test governance, triage, and CI integration.

## 1. Evaluation Overview

This evaluation reviews the e2e-best-practise skill along two axes: **actual task performance** and **token cost-effectiveness**. Three scenarios were designed (E2E journey coverage, flaky test triage, CI gate design). Each scenario was run with both with-skill and without-skill configurations, for 3 scenarios × 2 configs = 6 independent subagent runs, scored against 39 assertions.

**Special challenge**: issue2md is a **pure Go web app** with no Node.js/Playwright/package.json, while e2e-best-practise favors Playwright. This tests the skill’s **environment adaptation and degradation strategy**.

| Dimension | With Skill | Without Skill | Delta |
|-----------|-----------|--------------|-------|
| **Assertion pass rate** | **39/39 (100%)** | 20/39 (51.3%) | **+48.7 pp** |
| **5 Gate coverage** | 3/3 scenarios full | 0/3 | Skill-only |
| **Output Contract structured report** | 3/3 | 0/3 | Skill-only |
| **Machine-Readable JSON** | 3/3 | 0/3 | Skill-only |
| **Quality Scorecard** | 1/1 (Eval 1) | 0/1 | Skill-only |
| **Environment adaptation (Go ← Playwright degradation)** | Correct degradation + rationale | Naturally chose Go (no skill guidance) | Skill provides decision record |
| **Skill Token cost (SKILL.md only)** | ~2,800 tokens | 0 | — |
| **Skill Token cost (typical load)** | ~9,400 tokens | 0 | — |
| **Token cost per 1% pass-rate gain** | ~57 tokens (SKILL.md only) / ~193 tokens (typical) | — | — |

---

## 2. Test Methodology

### 2.1 Scenario Design

| Scenario | Goal | Core focus | Assertions |
|----------|------|------------|------------|
| Eval 1: E2E journey coverage | Create E2E tests for web convert flow | Environment adaptation (pure Go vs Playwright skill), Gate coverage, test quality | 15 |
| Eval 2: Flaky test triage | Triage intermittently failing SwaggerRedirect test in CI | Triage flow, root-cause classification, stability verification, Gate coverage | 12 |
| Eval 3: CI gate design | Design E2E CI strategy | Trigger strategy, secret handling, artifact collection, retry strategy | 12 |

### 2.2 Special Challenge: Playwright Skill vs. Go Project

issue2md’s characteristics make it a **boundary test scenario**:

| issue2md characteristic | e2e-best-practise expectation |
|-------------------------|------------------------------|
| No Node.js / package.json | Skill prefers Playwright (Node.js) |
| No client-side JavaScript | Skill has many DOM selector/wait rules |
| Go `html/template` server-side rendering | Skill assumes SPA/SSR (Next.js, React, Vue) |
| Existing Go HTTP client E2E tests | Skill recommends Playwright code path |

This tests the skill’s **degradation ability**—when the preferred toolchain does not apply, can it correctly identify and choose an alternative?

### 2.3 Execution

- With-skill runs load SKILL.md and selectively load reference files
- Without-skill runs load no skill; model default behavior
- All runs execute in independent subagents in parallel

---

## 3. Assertion Pass Rate

### 3.1 Summary

| Scenario | Assertions | With Skill | Without Skill | Delta |
|----------|-----------|-----------|--------------|-------|
| Eval 1: E2E journey coverage | 15 | **15/15 (100%)** | 8/15 (53.3%) | +46.7% |
| Eval 2: Flaky test triage | 12 | **12/12 (100%)** | 4/12 (33.3%) | +66.7% |
| Eval 3: CI gate design | 12 | **12/12 (100%)** | 8/12 (66.7%) | +33.3% |
| **Total** | **39** | **39/39 (100%)** | **20/39 (51.3%)** | **+48.7%** |

### 3.2 Per-Assertion Details

#### Eval 1: E2E Journey Coverage (15 assertions)

| # | Assertion | With | Without | Notes |
|---|-----------|------|---------|-------|
| A1 | Configuration gate structured table | ✅ | ❌ | Without mentioned gating but no structured var table |
| A2 | Environment gate evaluation | ✅ | ❌ | Without had no explicit env evaluation |
| A3 | Execution integrity gate | ✅ | ❌ | Without did not state whether tests ran |
| A4 | Correctly identifies no Playwright | ✅ | ✅ | |
| A5 | Does not blindly generate Playwright code | ✅ | ✅ | |
| A6 | Generates appropriate Go E2E tests | ✅ | ✅ | |
| A7 | No guessed secrets/URLs | ✅ | ✅ | |
| A8 | Tests cover convert flow | ✅ | ✅ | |
| A9 | Tests cover error path | ✅ | ✅ | |
| A10 | No unconditional sleep/waitForTimeout | ✅ | ✅ | |
| A11 | Data isolation explicitly stated | ✅ | ❌ | Without did not document data isolation |
| A12 | Output Contract structured report | ✅ | ❌ | Without only brief report |
| A13 | Machine-readable JSON | ✅ | ❌ | Without no JSON summary |
| A14 | Identifies existing E2E tests | ✅ | ✅ | |
| A15 | Next actions provided | ✅ | ❌ | Without no next actions |

#### Eval 2: Flaky Test Triage (12 assertions)

| # | Assertion | With | Without | Notes |
|---|-----------|------|---------|-------|
| B1 | Follows triage sequence (reproduce, classify, fix/quarantine) | ✅ | ✅ | |
| B2 | Root-cause classification labeled | ✅ | ✅ | |
| B3 | Provides reproduction command (with -count) | ✅ | ❌ | Without no -count reproduction command |
| B4 | Configuration gate | ✅ | ❌ | Without no config gate analysis |
| B5 | Environment gate | ✅ | ✅ | Both compared local vs CI |
| B6 | Execution integrity gate | ✅ | ❌ | Without did not state whether tests ran |
| B7 | No false execution claims | ✅ | ✅ | |
| B8 | Concrete fix suggestions | ✅ | ✅ | |
| B9 | Output contract | ✅ | ❌ | Without no structured output |
| B10 | Artifact strategy | ✅ | ❌ | Without did not discuss artifacts |
| B11 | Stability gate (single pass ≠ stable) | ✅ | ❌ | Without no -count=20 stability verification |
| B12 | Side-effect gate | ✅ | ❌ | Without no side-effect analysis |

#### Eval 3: CI Gate Design (12 assertions)

| # | Assertion | With | Without | Notes |
|---|-----------|------|---------|-------|
| C1 | Configuration gate | ✅ | ❌ | Without no structured config analysis |
| C2 | Environment gate | ✅ | ❌ | Without no explicit env gate |
| C3 | CI strategy doc (blocking vs nightly) | ✅ | ✅ | Both provided tiered trigger strategy |
| C4 | Artifact collection config | ✅ | ✅ | |
| C5 | GitHub Actions workflow YAML | ✅ | ✅ | |
| C6 | Retry/flaky strategy | ✅ | ✅ | |
| C7 | Output contract | ✅ | ❌ | Without no structured output |
| C8 | Machine-readable JSON | ✅ | ❌ | Without no JSON summary |
| C9 | Identifies existing CI targets | ✅ | ✅ | Both found swagger generation gap |
| C10 | Service startup strategy | ✅ | ✅ | |
| C11 | Parallel vs serial rationale | ✅ | ✅ | |
| C12 | Next actions | ✅ | ✅ | Without had Rollout Plan |

### 3.3 Classification of 19 Without-Skill Failures

| Failure type | Count | Evals | Notes |
|--------------|-------|-------|-------|
| **5 Mandatory Gates missing** | 9 | All | Configuration Gate 3×, Environment Gate 2×, Execution Integrity 2×, Stability Gate 1×, Side-Effect Gate 1× |
| **Output Contract missing** | 3 | All | No structured table for task type/runner/env gate/execution status |
| **Machine-Readable JSON missing** | 3 | All | No CI/tooling-consumable JSON summary |
| **Data isolation not documented** | 1 | Eval 1 | No explicit data isolation statement |
| **Reproduction command incomplete** | 1 | Eval 2 | No `-count` reproduction command |
| **Next actions missing** | 1 | Eval 1 | No next-actions list |
| **Artifact strategy missing** | 1 | Eval 2 | Triage report did not discuss trace/artifact |

### 3.4 Trend: Skill Advantage by Task Type

| Scenario type | With-Skill advantage | Reason |
|---------------|----------------------|-------|
| Eval 2: Flaky triage | **+66.7%** (highest) | Triage flow depends heavily on structured methodology; baseline lacks it |
| Eval 1: E2E journey | +46.7% | Gate coverage + Output Contract + env degradation decision record |
| Eval 3: CI design | +33.3% (lowest) | CI design is a model strength; skill mainly adds Gate and JSON |

Flaky triage is where the skill adds the most value—the baseline can find root causes and suggest fixes but **lacks triage methodology** (reproduce → classify → fix/quarantine) and **stability proof requirements** (-count=20 verification).

---

## 4. Dimension-by-Dimension Comparison

### 4.1 Environment Adaptation (Core Differentiator)

This is the most distinctive dimension in this evaluation. The skill is designed for Playwright first, but when faced with a pure Go project:

| Dimension | With Skill | Without Skill |
|-----------|-----------|--------------|
| Runner selection decision | Explicit rationale (no Node.js, no package.json, Constitution constraint) | Implicit choice of Go HTTP tests (no decision record) |
| Degradation path | "Generate the strongest deliverable the environment can support" → Go HTTP | Naturally chose Go (no degradation concept) |
| Playwright code | Explicitly rejected ("Installing Playwright would violate the constitution") | Not considered (no relevant context) |

**Analysis**: With-skill’s **Operating Model §5** ("Produce only the strongest deliverable the environment can actually support") correctly guided the degradation decision. The skill did not blindly generate Playwright code; after the Environment Gate confirmed the toolchain was missing, it chose the Go HTTP path. **The degradation rationale was explicitly recorded**, which matters for PR review and team alignment.

### 4.2 Five Mandatory Gates Coverage

This is the **highest-value dimension** of the skill—with-skill covered all 5 Gates in all 3 scenarios; without-skill missed multiple Gates in all 3.

| Gate | With Skill (3 scenarios) | Without Skill (3 scenarios) |
|------|--------------------------|----------------------------|
| Configuration Gate | 3/3 | 0/3 |
| Environment Gate | 3/3 | 1/3 (Eval 2 partial) |
| Execution Integrity Gate | 3/3 | 0/3 |
| Stability Gate | 2/2 (Eval 2, 3) | 0/2 |
| Side-Effect Gate | 2/2 (Eval 1, 2) | 0/2 |

**Practical value**: The Gate system prevents three common errors:
1. **False execution claims** — Execution Integrity Gate ensures "Not run" is explicitly labeled
2. **Single pass = fix** — Stability Gate requires `-count=20` verification
3. **Missing config dependencies** — Configuration Gate lists all variables and their available/missing/unknown status

### 4.3 Output Contract and Machine-Readable JSON

With-skill outputs included:

| Structure | Eval 1 | Eval 2 | Eval 3 |
|-----------|--------|--------|--------|
| Output Contract table | ✅ 9 fields | ✅ 9 fields | ✅ 9 fields |
| Machine-Readable JSON | ✅ | ✅ | ✅ |
| Quality Scorecard | ✅ (C1–C4, S1–S6, H1–H4) | N/A | N/A |

Without-skill reports were not low quality (Eval 3’s CI strategy was thorough), but **lacked standardized structure**. This means:
- Report format varies by task type
- CI/tooling cannot consume results programmatically
- Results from multiple runs are hard to compare

### 4.4 Flaky Triage Methodology (Eval 2 Deep Dive)

This is where with-skill advantage was largest (+66.7%).

| Dimension | With Skill | Without Skill |
|-----------|-----------|--------------|
| Triage template | Standardized Flaky Triage Template (test name, env, frequency, category checkboxes) | Free-form analysis |
| Root-cause depth | 3 contributing factors + Local vs CI comparison table | 4 factors (more detailed) |
| Fix suggestions | 3 fixes + impact ranking | 3 fixes + CI workflow patch |
| Reproduction command | `go test ... -count=10` | No -count command |
| Stability verification | "Validation requires: -count=20 with 20/20 pass rate on CI runner" | No stability requirement |
| Quarantine strategy | Template with owner, due date, status | No quarantine discussion |

**Analysis**: Root-cause quality was comparable (both found go run compile + 3s timeout). Without-skill lacked a **triage methodology framework**. The skill’s Flaky Test Policy ("reproduce with repeat runs → classify → fix → quarantine only with owner, issue, and removal deadline") provides a complete process guarantee.

### 4.5 CI Strategy Design (Eval 3 Deep Dive)

This is where without-skill was closest (+33.3%).

| Dimension | With Skill | Without Skill |
|-----------|-----------|--------------|
| Tiered trigger strategy | ✅ Detailed ASCII diagram + per-tier budget | ✅ Table + detailed rationale |
| Token handling | ✅ Security Checklist (5 items) | ✅ Two-tier matrix |
| Swagger generation gap | ✅ Found and fixed | ✅ Found and fixed |
| Quarantine rules | ✅ 4 rules | ✅ Brief mention |
| Rollout plan | None | ✅ 7-phase rollout plan |
| Mandatory Gates table | ✅ | ❌ |
| JSON summary | ✅ | ❌ |

**Analysis**: Without-skill showed strong baseline ability in CI design—it designed a tiered strategy, found the swagger generation bug, and provided a detailed Rollout Plan. The skill’s increment is mainly in **structured Gate validation** and **machine-readable output**.

---

## 5. Token Cost-Effectiveness

### 5.1 Skill Size

| File | Lines | Words | Bytes | Est. tokens |
|------|-------|-------|------|-------------|
| **SKILL.md** | 439 | 1,946 | 13,912 | ~2,800 |
| references/checklists.md | 152 | 824 | 5,528 | ~1,200 |
| references/playwright-patterns.md | 220 | 691 | 6,428 | ~1,000 |
| references/playwright-deep-patterns.md | 825 | 2,898 | 24,581 | ~4,200 |
| references/environment-and-dependency-gates.md | 181 | 943 | 6,275 | ~1,350 |
| references/agent-browser-workflows.md | 191 | 893 | 6,812 | ~1,300 |
| references/golden-examples.md | 247 | 1,018 | 8,997 | ~1,500 |
| scripts/discover_e2e_needs.sh | 215 | 755 | 6,413 | ~1,100 |
| **Description (always in context)** | — | ~50 | — | ~60 |
| **Total** | **2,470** | **10,018** | **78,946** | **~14,510** |

### 5.2 Actual Load Scenarios

| Scenario | Files read | Total tokens |
|----------|------------|--------------|
| Eval 1: E2E journey | SKILL.md + checklists + playwright-patterns + env-gates + golden-examples | ~7,850 |
| Eval 2: Flaky triage | SKILL.md + checklists + env-gates + golden-examples | ~6,850 |
| Eval 3: CI design | SKILL.md + checklists + playwright-deep + env-gates + golden-examples | ~11,050 |
| **Typical average** | | **~8,580** |
| Full load (all refs) | SKILL.md + all 6 references | ~13,350 |
| Minimal load | SKILL.md only | ~2,800 |

### 5.3 Token Cost vs. Quality Gain

| Metric | Value |
|--------|-------|
| With-skill pass rate | 100% (39/39) |
| Without-skill pass rate | 51.3% (20/39) |
| Pass-rate gain | +48.7 pp |
| Token cost per assertion fixed | ~147 tokens (SKILL.md only) / ~451 tokens (typical) |
| Token cost per 1% pass-rate gain | **~57 tokens (SKILL.md only) / ~176 tokens (typical)** |

### 5.4 Comparison with Other Skills

| Metric | e2e-best-practise | thirdparty-api-integ | api-integration-test | go-makefile-writer | git-commit |
|--------|-------------------|---------------------|----------------------|--------------------|------------|
| SKILL.md tokens | ~2,800 | ~680 | ~1,800 | ~1,960 | ~1,120 |
| Typical load tokens | ~8,580 | ~2,050 | ~2,850 | ~4,600 | ~1,120 |
| Pass-rate gain | **+48.7%** | +33.3% | +36.8% | +31.0% | +22.7% |
| Tokens per 1% (SKILL.md) | ~57 tok | **~20 tok** | ~49 tok | ~63 tok | ~51 tok |
| Tokens per 1% (typical) | ~176 tok | **~62 tok** | ~77 tok | ~149 tok | ~51 tok |

**Analysis**:

- **Highest absolute gain** (+48.7%) — e2e-best-practise assertion delta (19) is the largest in the series
- **SKILL.md cost-effectiveness good** (~57 tok/1%) — similar to git-commit (~51 tok) and api-integration-test (~49 tok)
- **Typical load cost-effectiveness high** (~176 tok/1%) — reference volume is large (6 files ~11,710 tokens), much of it Playwright-specific

### 5.5 Token Segment Cost-Effectiveness

| Module | Est. tokens | Related assertion deltas | Cost-effectiveness |
|--------|-------------|---------------------------|---------------------|
| **Mandatory Gates (5 × ~80 tok each)** | ~400 | 9 (A1–A3, B4, B6, B11, B12, C1, C2) | **Very high** — 44 tok/assertion |
| **Output Contract definition** | ~200 | 3 (A12, B9, C7) | **Very high** — 67 tok/assertion |
| **Machine-Readable JSON template** | ~150 | 3 (A13, B8_partial, C8) | **Very high** — 50 tok/assertion |
| **Flaky Test Policy** | ~120 | 2 (B3, B11) | **Very high** — 60 tok/assertion |
| **Quality Scorecard** | ~400 | Indirect (Eval 1 scorecard output) | **Medium** |
| **Anti-Examples (7 examples)** | ~500 | Indirect (A10 no-sleep) | **Low** — most anti-examples not applicable to Go |
| **Version/Platform Gate** | ~250 | 0 | **Low** — not applicable to Go |
| **Command Starters** | ~100 | 0 | **Low** — Agent Browser commands not applicable |
| **references/playwright-deep-patterns.md** | ~4,200 | 0 direct | **Low** — pure Go project |
| **references/playwright-patterns.md** | ~1,000 | 0 direct | **Low** — pure Go project |
| **references/golden-examples.md** | ~1,500 | Indirect (report structure) | **Medium** |
| **references/checklists.md** | ~1,200 | Indirect (triage template) | **High** |
| **references/environment-and-dependency-gates.md** | ~1,350 | Indirect (env evaluation framework) | **High** |

### 5.6 Token Efficiency Rating

| Rating | Conclusion |
|--------|------------|
| **Overall ROI** | **Good** — ~8,580 tokens (typical) for +48.7% pass rate; highest absolute gain in series |
| **SKILL.md ROI** | **Good** — ~2,800 tokens cost-effectiveness (~57 tok/1%) on par with series |
| **High-leverage token share** | ~31% (870/2,800) directly contributes to 17/19 assertion deltas |
| **Low-leverage token share** | ~30% (850/2,800) contributes nothing in Go project evaluation (Playwright-specific) |
| **Reference cost-effectiveness** | **Mixed** — checklists + env-gates high value; playwright-patterns + deep-patterns no value for Go |

---

## 6. Boundary with Base Model Capabilities

### 6.1 Capabilities Base Model Already Has (No Skill Increment)

| Capability | Evidence |
|------------|----------|
| Choosing appropriate E2E tool (Go HTTP vs Playwright) | 3/3 scenarios chose Go HTTP |
| Root-cause depth (flaky test) | Eval 2: Found go run compile + 3s timeout dual factors |
| CI tiered trigger strategy design | Eval 3: PR/main/nightly tiers |
| Swagger generation gap discovery | Eval 3: Both found |
| Artifact upload YAML generation | Eval 3: Full actions/upload-artifact config |
| Secret handling (t.Skip when absent) | 3/3 scenarios correct |
| Serial vs parallel rationale | Eval 3: Detailed analysis |

### 6.2 Base Model Gaps (Skill Fills)

| Gap | Evidence | Risk level |
|-----|----------|------------|
| **5 Mandatory Gates entirely missing** | 3/3 scenarios no gate analysis | **High** — risk of false execution claims, missing config deps |
| **Output Contract missing** | 3/3 scenarios no standardized report structure | **Medium** — reports not reproducible or comparable |
| **Machine-Readable JSON missing** | 3/3 scenarios no JSON | **Medium** — CI/tooling cannot consume programmatically |
| **Stability Gate missing** | Eval 2 no -count=20 verification requirement | **High** — single pass claimed as fix |
| **Data isolation not documented** | Eval 1 no explicit statement | **Low** — code was isolated |
| **Flaky triage methodology missing** | Eval 2 no standard triage sequence | **Medium** — analysis quality depends on experience |
| **Degradation decision not recorded** | Eval 1 no runner choice rationale | **Low** — choice correct but no traceability |

---

## 7. Overall Score

### 7.1 Dimension Scores

| Dimension | With Skill | Without Skill | Delta |
|-----------|-----------|--------------|-------|
| Gate coverage (5 gates) | 5.0/5 | 1.0/5 | +4.0 |
| Environment adaptation and degradation | 5.0/5 | 3.5/5 | +1.5 |
| Structured report & JSON | 5.0/5 | 1.0/5 | +4.0 |
| Test quality | 5.0/5 | 4.0/5 | +1.0 |
| Flaky triage methodology | 5.0/5 | 2.5/5 | +2.5 |
| CI design | 5.0/5 | 4.0/5 | +1.0 |
| **Mean** | **5.00/5** | **2.67/5** | **+2.33** |

### 7.2 Weighted Total

| Dimension | Weight | Score | Weighted |
|-----------|--------|------|----------|
| Assertion pass rate (delta) | 25% | 10/10 | 2.50 |
| Gate coverage system | 20% | 10/10 | 2.00 |
| Structured report & JSON output | 15% | 10/10 | 1.50 |
| Flaky triage methodology | 10% | 10/10 | 1.00 |
| Environment adaptation | 10% | 10/10 | 1.00 |
| Token cost-effectiveness | 15% | 6.0/10 | 0.90 |
| CI design increment | 5% | 7.0/10 | 0.35 |
| **Weighted total** | | | **9.25/10** |

Token cost-effectiveness lowers the total—SKILL.md cost-effectiveness is good, but Playwright-specific reference content has no value for non-JS projects.

---

## 8. Evaluation Materials

| Material | Path |
|----------|------|
| Eval 1 with-skill output | `/tmp/e2e-eval/eval-1/with_skill/` |
| Eval 1 without-skill output | `/tmp/e2e-eval/eval-1/without_skill/` |
| Eval 2 with-skill output | `/tmp/e2e-eval/eval-2/with_skill/` |
| Eval 2 without-skill output | `/tmp/e2e-eval/eval-2/without_skill/` |
| Eval 3 with-skill output | `/tmp/e2e-eval/eval-3/with_skill/` |
| Eval 3 without-skill output | `/tmp/e2e-eval/eval-3/without_skill/` |

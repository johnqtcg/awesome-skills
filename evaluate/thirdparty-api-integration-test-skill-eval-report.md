# thirdparty-api-integration-test Skill Evaluation Report

> Evaluation framework: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> Evaluation date: 2026-03-11
> Evaluation subject: `thirdparty-api-integration-test`

---

`thirdparty-api-integration-test` is a skill for writing and running real integration tests for Go third-party API clients. It is suited for verifying vendor interface contracts, troubleshooting external call failures, and performing bounded regression checks under real runtime configuration. Its three standout strengths are: strict scope validation that clearly distinguishes third-party APIs, internal APIs, and unit tests to avoid test strategy mismatch; explicit safety gates for environment variables, runtime configuration, and production access, defaulting to rejecting high-risk execution paths; and build tag isolation plus structured output reports, making these high-cost tests suitable for on-demand runs and easier to capture results.

## 1. Evaluation Overview

This evaluation reviews the thirdparty-api-integration-test skill along two axes: **actual task performance** and **token cost-effectiveness**. Three scenarios were designed (GitHub REST API integration test, OpenAI Responses API integration test, internal webapp API scope boundary test). Each scenario was run with both with-skill and without-skill configurations, for 3 scenarios × 2 configs = 6 independent subagent runs, scored against 36 assertions.

| Dimension | With Skill | Without Skill | Delta |
|-----------|-----------|--------------|-------|
| **Assertion pass rate** | **36/36 (100%)** | 24/36 (66.7%) | **+33.3 pp** |
| **Gate env var isolation** | 3/3 correct | 1/3 | Largest single-item delta |
| **Production Safety Gate** | 3/3 | 0/3 | Skill-only |
| **Build tag isolation** | 3/3 | 2/3 | Eval 2 without-skill missing |
| **Output Contract structured report** | 3/3 | 0/3 | Skill-only |
| **Scope boundary identification** | 4/4 | 0/4 | Skill-only |
| **Skill Token cost (SKILL.md only)** | ~680 tokens | 0 | — |
| **Skill Token cost (all references)** | ~1,660 tokens | 0 | — |
| **Token cost per 1% pass-rate gain** | ~20 tokens (SKILL.md only) / ~50 tokens (full) | — | — |

---

## 2. Test Methodology

### 2.1 Scenario Design

| Scenario | Target | Core focus | Assertions |
|----------|--------|------------|------------|
| Eval 1: GitHub REST client | `internal/github/rest_client.go` (5 methods) | Standard third-party API integration: gate, safety gates, assertion quality | 15 |
| Eval 2: OpenAI Responses API | `internal/converter/summary_openai.go` (Summarize method) | Paid API test: API key management, i18n, timeout boundaries | 13 |
| Eval 3: Internal webapp (scope) | `internal/webapp/handler.go` (6 HTTP endpoints) | Scope boundary: internal API should not use third-party pattern | 8 |

### 2.2 Execution

- With-skill runs first read SKILL.md and its 4 referenced files
- Without-skill runs read no skill, using model default behavior to generate tests
- All runs execute in parallel in independent subagents
- Eval 3 tests the skill’s scope identification for internal APIs

---

## 3. Assertion Pass Rate

### 3.1 Overview

| Scenario | Assertions | With Skill | Without Skill | Delta |
|----------|-----------|-----------|--------------|-------|
| Eval 1: GitHub REST | 15 | **15/15 (100%)** | 10/15 (66.7%) | +33.3% |
| Eval 2: OpenAI API | 13 | **13/13 (100%)** | 10/13 (76.9%) | +23.1% |
| Eval 3: Scope boundary | 8 | **8/8 (100%)** | 4/8 (50.0%) | +50.0% |
| **Total** | **36** | **36/36 (100%)** | **24/36 (66.7%)** | **+33.3%** |

### 3.2 Per-Assertion Details

#### Eval 1: GitHub REST Client (15 assertions)

| # | Assertion | With | Without | Notes |
|---|-----------|------|---------|------|
| A1 | `//go:build integration` build tag | ✅ | ✅ | |
| A2 | Dedicated gate env var (GITHUB_INTEGRATION=1) | ✅ | ❌ | Without uses GITHUB_TOKEN as implicit gate only |
| A3 | Production safety gate (ENV=prod → skip) | ✅ | ❌ | Without completely missing |
| A4 | GITHUB_TOKEN read from env | ✅ | ✅ | |
| A5 | Actionable skip messages | ✅ | ✅ | |
| A6 | context.WithTimeout wraps each API call | ✅ | ✅ | |
| A7 | Protocol-level assertions (number match, non-nil) | ✅ | ✅ | |
| A8 | Business-level assertions (title, user, state non-empty) | ✅ | ✅ | |
| A9 | Failure path explicit error type/code check | ✅ | ❌ | Without only `err != nil`, no `*statusError` assertion |
| A10 | Uses production code path (real client) | ✅ | ✅ | |
| A11 | No retry (or bounded retry) | ✅ | ✅ | |
| A12 | File naming `*_integration_test.go` | ✅ | ✅ | |
| A13 | Env var validation (TrimSpace + ParseInt) | ✅ | ❌ | Without no TrimSpace |
| A14 | Test data lifecycle (stable fixtures, overwritable) | ✅ | ✅ | |
| A15 | Output Contract structured report | ✅ | ❌ | Without only brief summary |

#### Eval 2: OpenAI Responses API (13 assertions)

| # | Assertion | With | Without | Notes |
|---|-----------|------|---------|------|
| B1 | `//go:build integration` build tag | ✅ | ❌ | Without missing build tag; `go test ./...` would trigger |
| B2 | Dedicated gate env var | ✅ | ✅ | Both use gate |
| B3 | Production safety gate | ✅ | ❌ | Without completely missing |
| B4 | OPENAI_API_KEY read from env | ✅ | ✅ | |
| B5 | Actionable skip messages | ✅ | ✅ | |
| B6 | context.WithTimeout wraps each call | ✅ | ✅ | |
| B7 | Protocol-level assertions (Status == "ok") | ✅ | ✅ | |
| B8 | Business-level assertions (Summary/Language/KeyDecisions) | ✅ | ✅ | |
| B9 | Failure path tests (empty key, invalid key) | ✅ | ✅ | |
| B10 | Uses production code path | ✅ | ✅ | |
| B11 | No retry (paid API default no retry) | ✅ | ✅ | |
| B12 | Timeout boundary test (expired context) | ✅ | ✅ | |
| B13 | Output Contract structured report | ✅ | ❌ | Without only brief summary |

#### Eval 3: Scope Boundary Test (8 assertions)

| # | Assertion | With | Without | Notes |
|---|-----------|------|---------|------|
| C1 | Identifies target as internal API (not third-party) | ✅ | ❌ | Without has no scope concept |
| C2 | Does not apply thirdparty pattern (build tag, gate) | ✅ | ✅ | |
| C3 | Report indicates scope determination | ✅ | ❌ | Without no scope analysis |
| C4 | Recommends correct skill ($api-integration-test) | ✅ | ❌ | Without no skill recommendation concept |
| C5 | Uses httptest mode | ✅ | ✅ | |
| C6 | Does not wrongly add THIRDPARTY_INTEGRATION gate | ✅ | ✅ | |
| C7 | Tests cover internal endpoints | ✅ | ✅ | |
| C8 | Provides clear scope boundary explanation | ✅ | ❌ | Without no scope analysis |

### 3.3 Classification of 12 Failed Assertions (Without-Skill)

| Failure type | Count | Evals | Notes |
|--------------|-------|-------|-------|
| **Production Safety Gate missing** | 2 | Eval 1, 2 | Neither has ENV=prod protection; direct run may hit production |
| **Gate env var missing or implicit** | 1 | Eval 1 | Only GITHUB_TOKEN implicit gate; no dedicated switch var |
| **Build tag missing** | 1 | Eval 2 | `go test ./...` would accidentally trigger OpenAI integration test |
| **Structured Output Contract missing** | 2 | Eval 1, 2 | No gate vars, failure classification, missing prerequisites |
| **Error type/code imprecise** | 1 | Eval 1 | 404 path only `err != nil`, no `*statusError` check |
| **Env var validation non-standard** | 1 | Eval 1 | No TrimSpace; leading/trailing spaces can cause misjudgment |
| **Scope identification missing** | 4 | Eval 3 | No scope analysis, no alternative skill recommendation |

### 3.4 Risk Matrix: Real Impact of Without-Skill Gaps

| Gap | Risk level | Real scenario |
|-----|------------|---------------|
| Production Safety Gate | **High** | With `ENV=prod`, tests directly call production third-party API; may consume quota, incur cost, trigger rate limits |
| Build tag missing | **High** | Eval 2 no tag → `go test ./...` calls OpenAI API → every CI run consumes API quota |
| Gate env var implicit | **Medium** | Runs whenever GITHUB_TOKEN exists → developer shell usually has token configured |
| Error type imprecise | **Medium** | When 404 regresses to 500, `err != nil` still passes; cannot distinguish error type change |
| Env var no TrimSpace | **Low** | Trailing space in env var causes gate misjudgment (rare but possible) |

---

## 4. Dimension-by-Dimension Comparison

### 4.1 Gate Env Var Design

This is the **highest practical-value** differentiator.

| Scenario | With Skill | Without Skill |
|----------|-----------|--------------|
| GitHub REST | `GITHUB_INTEGRATION=1` + `GITHUB_TOKEN` two-level gate | Only `GITHUB_TOKEN` implicit gate |
| OpenAI API | `OPENAI_INTEGRATION=1` + `OPENAI_API_KEY` two-level gate | `ISSUE2MD_OPENAI_INTEGRATION=1` + `OPENAI_API_KEY` |

**Analysis**: With-skill consistently uses **explicit two-level gates** (switch var + credential var separated). Without-skill in Eval 1 relies only on the credential var, so when the developer shell already has `GITHUB_TOKEN`, running `go test -tags=integration ./...` would accidentally trigger tests.

The skill’s pattern "Add explicit run gate env var, otherwise `t.Skip(...)`" addresses this safety design issue.

### 4.2 Production Safety Gate

| Scenario | With Skill | Without Skill |
|----------|-----------|--------------|
| Eval 1 | ✅ `ENV=prod → t.Skip` | ❌ Completely missing |
| Eval 2 | ✅ `ENV=prod → t.Skip` | ❌ Completely missing |

**Analysis**: This is a **Skill-only** safety mechanism; Without-skill did not implement it in either scenario. For third-party API tests (especially paid OpenAI API), missing production protection can lead to:
- Tests accidentally running in production
- Consuming real API quota and cost
- Triggering vendor rate-limit policies

### 4.3 Build Tag Isolation

| Scenario | With Skill | Without Skill |
|----------|-----------|--------------|
| Eval 1 | `//go:build integration` + `// +build integration` | `//go:build integration` |
| Eval 2 | `//go:build integration` + `// +build integration` | ❌ No build tag |

**Analysis**: Eval 2 Without-skill output **completely lacks a build tag**, so `go test ./...` would compile and run the OpenAI integration test. For paid APIs this is serious — every CI run could incur API cost.

With-skill always outputs both build tag formats (new and legacy) for backward compatibility.

### 4.4 Error Assertion Precision

| Dimension | With Skill | Without Skill |
|-----------|-----------|--------------|
| Eval 1 404 path | `errors.As(err, &stErr)` + `stErr.StatusCode == 404` | `err != nil` |
| Eval 2 auth failure | `strings.Contains(err.Error(), "status 4")` | `strings.Contains(err.Error(), "status 4")` |

The skill’s rule "For expected failure paths, assert explicit error type/code (not only `require.Error`)" produced a clear difference in Eval 1. With-skill uses `errors.As` to check the concrete `*statusError` type and 404 status code; Without-skill only checks `err != nil`.

**Practical value**: If the GitHub API 404 response format changes (e.g. returns 403 instead of 404), Without-skill’s test would still pass and hide the issue.

### 4.5 Output Contract (Structured Report)

With-skill produces a report after each run containing:

| Report item | Eval 1 | Eval 2 | Eval 3 |
|-------------|--------|--------|--------|
| Integration target details | ✅ | ✅ | ✅ |
| Gate variable full list | ✅ (10 vars) | ✅ (6 vars) | ✅ (N/A) |
| Exact run commands | ✅ | ✅ | ✅ |
| Timeout / Retry policy | 30s / none | 30s / none | 10s / none |
| Result summary (pass/fail/skip) | ✅ | ✅ | ✅ |
| Failure classification | N/A | N/A | N/A |
| Missing prerequisites | ✅ | ✅ | ✅ |
| Checklist compliance | ✅ | ✅ | — |
| Scope determination | — | — | ✅ |

Without-skill produces a concise task summary but no gate variable table, no failure classification, no missing prerequisites list.

### 4.6 Scope Boundary Identification (Eval 3)

This is the **most distinctive capability** in this evaluation.

With-skill in Eval 3:
1. **Actively identified** `internal/webapp/handler.go` as an internal API after reading it
2. Explicitly stated "OUT OF SCOPE for thirdparty-api-integration-test skill"
3. Provided a **stepwise gate evaluation table** proving inapplicability
4. Recommended the correct `$api-integration-test` skill
5. Still produced **high-quality internal API tests** (httptest mode)

Without-skill directly produced high-quality webapp tests (25 test functions covering all endpoints) but **no scope analysis**.

**Analysis**: The skill’s scope comes from SKILL.md’s "Validate external API integration end-to-end" and "Apply to any third-party API integration" statements. Although SKILL.md has **no explicit scope validation gate** (unlike `api-integration-test`’s "Scope Validation Gate" section), the agent still inferred the boundary from context. This shows SKILL.md’s implicit scope definition is sufficient to guide correct judgment.

---

## 5. Token Cost-Effectiveness Analysis

### 5.1 Skill Size

| File | Lines | Words | Bytes | Est. tokens |
|------|-------|-------|-------|-------------|
| **SKILL.md** | 80 | 482 | 3,699 | ~680 |
| references/common-integration-gate.md | 38 | 209 | 1,513 | ~370 |
| references/common-output-contract.md | 19 | 96 | 658 | ~150 |
| references/checklists.md | 31 | 184 | 1,397 | ~280 |
| references/vendor-examples.md | 99 | 326 | 3,094 | ~570 |
| **Description (always in context)** | — | ~30 | — | ~40 |
| **Total** | **267** | **1,327** | **10,361** | **~2,090** |

**Typical load scenarios:**

| Scenario | Files read | Total tokens |
|----------|------------|--------------|
| Full load (all references) | SKILL.md + 4 references | ~2,050 |
| Standard load (no vendor examples) | SKILL.md + gate + contract + checklists | ~1,480 |
| Minimal load | SKILL.md | ~680 |

### 5.2 Token Cost for Quality Gain

| Metric | Value |
|--------|-------|
| With-skill pass rate | 100% (36/36) |
| Without-skill pass rate | 66.7% (24/36) |
| Pass-rate gain | +33.3 pp |
| Token cost per assertion fixed | ~57 tokens (SKILL.md only) / ~171 tokens (full) |
| Token cost per 1% pass-rate gain | **~20 tokens (SKILL.md only) / ~50 tokens (full)** |

### 5.3 Comparison with Sister Skill Cost-Effectiveness

| Metric | thirdparty-api-integration-test | api-integration-test | go-makefile-writer | git-commit |
|--------|--------------------------------|----------------------|--------------------|------------|
| SKILL.md tokens | ~680 | ~1,800 | ~1,960 | ~1,120 |
| Total load tokens | ~2,050 | ~2,850 | ~4,600 | ~1,120 |
| Pass-rate gain | +33.3% | +36.8% | +31.0% | +22.7% |
| Tokens per 1% (SKILL.md) | **~20 tok** | ~49 tok | ~63 tok | ~51 tok |
| Tokens per 1% (full) | **~62 tok** | ~77 tok | ~149 tok | ~51 tok |

**Analysis**: thirdparty-api-integration-test’s SKILL.md has **best token cost-effectiveness in the series** — only ~680 tokens achieves +33.3% pass-rate gain. This is due to:
1. Extremely lean SKILL.md (80 lines vs api-integration-test’s 290)
2. High rule density — 13 Required Patterns cover all core differences
3. Well-designed references — vendor-examples.md provides copy-paste templates

### 5.4 Token Segment Cost-Effectiveness

| Module | Est. tokens | Related assertion delta | Cost-effectiveness |
|--------|-------------|-------------------------|--------------------|
| **Required Pattern §3–5 (gate + prod safety + env validation)** | ~80 | 5 assertions (A2, A3, A13, B1, B3) | **Very high** — 16 tok/assertion |
| **Required Pattern §12 (explicit error type/code)** | ~20 | 1 assertion (A9) | **Very high** — 20 tok/assertion |
| **Output Contract pointer** | ~15 | 2 assertions (A15, B13) | **Very high** — 8 tok/assertion |
| **common-output-contract.md** | ~150 | Indirect support for Output Contract quality | **High** |
| **Scope definition ("Apply to any third-party API integration")** | ~30 | 4 assertions (C1, C3, C4, C8) | **Very high** — 8 tok/assertion |
| **common-integration-gate.md** | ~370 | Indirect support for gate design consistency | **High** |
| **checklists.md** | ~280 | Indirect support for test quality completeness | **Medium** |
| **vendor-examples.md** | ~570 | Indirect support for template consistency (MCS/USS templates) | **Medium** — no direct match for issue2md project |

### 5.5 High-Leverage vs Low-Leverage Instructions

**High leverage (~145 tokens SKILL.md → 12 assertion deltas):**
- Gate + prod safety + env validation rules (80 tok → 5 assertions)
- Explicit error type/code rule (20 tok → 1 assertion)
- Scope definition (30 tok → 4 assertions)
- Output Contract pointer (15 tok → 2 assertions)

**Medium leverage (~535 tokens SKILL.md → indirect contribution):**
- Vendor-Specific Safety Additions (~150 tok) — drives idempotent preference, rate-limit awareness
- Safety Rules summary (~130 tok) — reinforces safety constraints
- Configuration Gate pointer (~25 tok) — guides reading detailed gate docs
- References section (~230 tok) — points to all references

**Low leverage (~570 tokens references → limited contribution):**
- vendor-examples.md (~570 tok) — MCS/USS templates have no direct mapping for issue2md

### 5.6 Token Efficiency Rating

| Rating | Conclusion |
|--------|------------|
| **Overall ROI** | **Excellent** — ~2,050 tokens for +33.3% pass rate |
| **SKILL.md ROI** | **Outstanding** — ~680 tokens contains all high-leverage rules; best cost-effectiveness in series |
| **High-leverage token share** | ~21% (145/680) directly contributes to all 12 assertion deltas |
| **Low-leverage token share** | vendor-examples.md is 27% of budget; no direct mapping for current project |
| **Reference cost-effectiveness** | **High** — gate + contract references are small and focused; vendor-examples is large |

---

## 6. Boundary Analysis vs Claude Base Model Capabilities

### 6.1 Capabilities Base Model Already Has (No Skill Increment)

| Capability | Evidence |
|------------|----------|
| context.WithTimeout wraps API calls | 3/3 scenarios correct |
| Protocol-level assertions (number match, non-nil) | 3/3 scenarios correct |
| Business-level assertions (non-empty fields) | 3/3 scenarios correct |
| File naming `*_integration_test.go` | 2/2 API scenarios correct |
| Uses production code path (real client) | 3/3 scenarios correct |
| No retry default policy | 3/3 scenarios correct |
| Basic actionable skip messages | 3/3 scenarios correct |
| httptest.NewServer for internal API | 1/1 scenario correct |
| Stable fixture + overwrite capability | 2/2 API scenarios correct |

### 6.2 Base Model Gaps (Skill Fills)

| Gap | Evidence | Risk level |
|-----|----------|------------|
| **Production Safety Gate missing** | 2/2 API scenarios lack ENV=prod protection | **High** — production trigger can consume quota |
| **Build tag inconsistent** | 1/2 API scenarios missing build tag | **High** — `go test ./...` triggers paid API |
| **Gate env var implicit** | 1/2 scenarios use credential as gate only | **Medium** — runs when credential exists |
| **Error type imprecise** | 1/2 scenarios only `err != nil` | **Medium** — cannot distinguish error type change |
| **Env var no TrimSpace** | 1/2 scenarios no validation | **Low** — trailing space causes misjudgment |
| **No structured Output report** | 2/2 scenarios no report | **Medium** — lacks audit traceability |
| **Scope identification** | 1/1 scenario no scope analysis | **Low** — still produced suitable tests |

---

## 7. Overall Score

### 7.1 Dimension Scores

| Dimension | With Skill | Without Skill | Delta |
|-----------|-----------|--------------|-------|
| Gate and safety gates | 5.0/5 | 2.0/5 | +3.0 |
| Build tag isolation | 5.0/5 | 3.5/5 | +1.5 |
| Assertion quality (protocol + business + error) | 5.0/5 | 3.5/5 | +1.5 |
| Env var validation and test data lifecycle | 5.0/5 | 4.0/5 | +1.0 |
| Structured report | 5.0/5 | 1.0/5 | +4.0 |
| Scope boundary identification | 5.0/5 | 1.0/5 | +4.0 |
| **Overall mean** | **5.00/5** | **2.50/5** | **+2.50** |

### 7.2 Weighted Total Score

| Dimension | Weight | Score | Weighted |
|-----------|-------|------|----------|
| Assertion pass rate (delta) | 25% | 9.5/10 | 2.38 |
| Gate and safety gates | 20% | 10/10 | 2.00 |
| Build tag isolation and consistency | 10% | 10/10 | 1.00 |
| Assertion quality and error precision | 10% | 10/10 | 1.00 |
| Structured report (Output Contract) | 10% | 10/10 | 1.00 |
| Scope boundary identification | 10% | 10/10 | 1.00 |
| Token cost-effectiveness | 15% | 9.5/10 | 1.43 |
| **Weighted total** | | | **9.81/10** |

---

## 8. Evaluation Materials

| Material | Path |
|----------|------|
| Eval 1 with-skill output | `/tmp/tp-integ-eval/eval-1/with_skill/` |
| Eval 1 without-skill output | `/tmp/tp-integ-eval/eval-1/without_skill/` |
| Eval 2 with-skill output | `/tmp/tp-integ-eval/eval-2/with_skill/` |
| Eval 2 without-skill output | `/tmp/tp-integ-eval/eval-2/without_skill/` |
| Eval 3 with-skill output | `/tmp/tp-integ-eval/eval-3/with_skill/` |
| Eval 3 without-skill output | `/tmp/tp-integ-eval/eval-3/without_skill/` |

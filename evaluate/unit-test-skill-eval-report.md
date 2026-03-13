# unit-test Skill Evaluation Report

> Evaluation framework: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> Evaluation date: 2026-03-11
> Evaluation subject: `unit-test`

---

`unit-test` is a Go-focused skill for generating and improving unit tests. It is suited for adding or strengthening logic tests, fixing low-signal tests, and designing more targeted test cases for concurrency, boundary, and mapping defects. Its three standout strengths are: high trigger accuracy, reliably distinguishing unit tests from benchmarks, fuzz tests, integration tests, and similar adjacent tasks; emphasis on failure hypotheses, Killer Cases, and boundary checklists, shifting test goals from "coverage chasing" to "catching real bugs"; and consistent use of table-driven tests, `t.Run`, race detection, and project assertion style adaptation so tests are both standard and aligned with existing codebase practices.

## 1. Evaluation Overview

This evaluation reviews the unit-test skill along two axes: **trigger accuracy** and **actual task performance**. Task performance covers 3 different types of Go concurrency/time-sensitive target code. Each target was run with both with-skill and without-skill configurations, for 3 scenarios × 2 configs = 6 independent subagent runs, scored against 34 assertions.

| Dimension | With Skill | Without Skill | Delta |
|-----------|-----------|--------------|-------|
| **Trigger accuracy** | 20/20 (100%) | — | Recall 10/10, Precision 10/10 |
| **Assertion pass rate** | **34/34 (100%)** | 21/34 (61.6%) | **+38.4 pp** |
| **Functional coverage (core paths)** | Full | Full | No difference |
| **Methodology output (hypothesis list / Killer Case / boundary checklist)** | **Full** | **Zero** | **Decisive difference** |
| **Test organization (table-driven + t.Run)** | 3/3 | 0/3 | Skill consistently applied |

---

## 2. Trigger Accuracy

### 2.1 Test Method

20 test queries were designed (10 should trigger / 10 should not trigger), covering Chinese and English, various unit-test scenarios, and easily confused adjacent tasks (benchmark, fuzz test, integration test, E2E, CI config, mock generation, documentation, translation, pprof analysis). Independent subagents simulated Cursor’s `<agent_skills>` trigger path. Each query was judged 3 times independently, for 60 judgments total.

> **Note on `run_eval.py` failure**: The skill-creator `run_eval.py` script does not work inside Cursor IDE — the `claude -p` subprocess fails silently due to lost auth context (error: "Your organization does not have access to Claude"), causing all 60 queries to return `triggered=false` and meaningless 0% Recall / 50% Accuracy. This report’s trigger evaluation uses a Task subagent simulation instead: each round is evaluated by an independent agent with fresh context.

### 2.2 Results

```
Overall accuracy:  20/20 (100%)
Recall:            10/10 (100%) — all positive queries correctly triggered (3 rounds consistent)
Precision:         10/10 (100%) — all negative queries correctly excluded (3 rounds consistent)
F1:                100%
Total judgments:   60/60 (TP=30, FN=0, FP=0, TN=30)
```

### 2.3 Positive Queries (All Correctly Triggered)

| # | Query | Judgment | Trigger reason |
|---|-------|----------|----------------|
| 1 | Help me write unit tests for service.go… concurrency issues | ✅ | "write unit tests" + concurrency scenario |
| 2 | I need unit tests for jwt.go… expiry boundary… zero coverage | ✅ | unit test + coverage gate |
| 3 | Unit test failed, TestUserService_Create/duplicate_email… | ✅ | fix test + test debugging |
| 4 | handler_test.go is all TestXxx, want to refactor to table-driven + t.Run | ✅ | table-driven + improve tests |
| 5 | Coverage dropped to 62%, CI blocked… add a few targeted tests | ✅ | coverage gate + add tests |
| 6 | MapReduce function… empty slice and single element… can you write tests to verify | ✅ | "verify this function works" |
| 7 | sync.Pool wrapper… want to confirm no data race under concurrency… run with -race | ✅ | -race + check for race conditions |
| 8 | Add unit tests for retry.go… retry count boundary, context cancellation | ✅ | unit test + boundary scenario |
| 9 | Help me write tests to verify middleware chain execution order… | ✅ | "write tests" + verify function |
| 10 | Review service_test.go test quality… killer case | ✅ | review tests + test quality |

### 2.4 Negative Queries (All Correctly Excluded)

| # | Query | Judgment | Exclusion reason |
|---|-------|----------|------------------|
| 11 | Help me write a benchmark comparing sync.Map… -benchmem | ✅ | Benchmark, not unit test |
| 12 | Need integration tests to verify UserRepository with real MySQL… | ✅ | Integration test, not unit test |
| 13 | Write a fuzz test for json_parser.go… go test -fuzz | ✅ | Fuzz test, not unit test |
| 14 | Help configure GitHub Actions CI workflow… | ✅ | CI config, not writing tests |
| 15 | Use mockgen to generate mock for UserStore interface… | ✅ | Mock generation, not writing tests |
| 16 | Help me write an E2E test… chromedp or playwright… | ✅ | E2E test, not unit test |
| 17 | Load test gRPC interface… run ghz for 10 seconds… | ✅ | Load test, not unit test |
| 18 | Help me write a technical doc on Go testing strategy… | ✅ | Documentation, not writing tests |
| 19 | Translate markdown in gocore/map/ to English… | ✅ | Translation, unrelated |
| 20 | Help analyze pprof CPU profile data… | ✅ | Profiling, not writing tests |

### 2.5 Conclusion

The improved Description uses a four-layer strategy for trigger accuracy:

1. **Irreplaceability signals** — "references/ with killer-case pattern templates", "cannot be reproduced from memory", "mandatory 13-check tiered scorecard" make the model judge that its own knowledge cannot replace the skill
2. **Strong imperative tone** — "ALWAYS read this skill before writing, reviewing, or fixing ANY Go test file (_test.go)"
3. **Broad trigger coverage** — 12 keywords in Chinese and English + 4 indirect trigger modes (verify, check for race conditions, improve test quality, coverage is too low)
4. **Explicit exclusion scope** — "Do NOT use for benchmarks, fuzz tests, integration tests, E2E tests, load tests, or mock generation" effectively isolates 6 adjacent task types

---

## 3. Actual Task Performance

### 3.1 Test Method

Three Go code files in the repo with no existing tests were selected, covering different testing challenges:

| Scenario | Target code | Testing challenge | Assertions |
|----------|-------------|-------------------|------------|
| Eval 1: resilience.Do | `designpattern/circuitbreaker/resilience/resilience.go` | Combined rate-limit + circuit-breaker + retry; multi-component interaction, context propagation, retry boundaries | 11 |
| Eval 2: WorkerPool | `designpattern/bulkhead/pool/pool.go` | Concurrent worker pool; goroutine leak, double-Shutdown safety, task loss | 11 |
| Eval 3: Limiter | `designpattern/circuitbreaker/ratelimiter/ratelimiter.go` | Token bucket rate limiter; time-sensitive tests, concurrency races, float precision | 12 |

Each scenario ran 1 with-skill + 1 without-skill subagent, 6 runs total.

### 3.2 Assertion Pass Rate Overview

| Scenario | Assertions | With Skill | Without Skill | Delta |
|----------|-----------|-----------|--------------|-------|
| Eval 1: resilience.Do | 11 | **11/11 (100%)** | 7/11 (63.6%) | +36.4% |
| Eval 2: WorkerPool | 11 | **11/11 (100%)** | 6/11 (54.5%) | +45.5% |
| Eval 3: Limiter | 12 | **12/12 (100%)** | 8/12 (66.7%) | +33.3% |
| **Total** | **34** | **34/34 (100%)** | **21/34 (61.6%)** | **+38.4%** |

### 3.3 Per-Item Comparison: Which Assertions Drove the Gap?

The 13 assertions that Without-skill failed across all 3 scenarios fall into 4 methodology dimensions:

| Failure type | Count | Failed assertions |
|--------------|-------|-------------------|
| **Failure Hypothesis List** | 3 | All 3 scenarios — no formal defect hypothesis table |
| **Killer Cases** | 3 | All 3 scenarios — no named defect-hypothesis-driven killer cases |
| **Table-driven + t.Run** | 3 | All 3 scenarios use separate TestXxx functions instead of subtest organization |
| **Boundary Checklist** | 4 | All 3 scenarios missing + Eval 2 additionally missing goroutine leak discussion |

**Key observation**: All 13 Without-skill failures are **methodology-level**, not functional coverage.

### 3.4 Functional Coverage Comparison

On "which code paths are tested", the two sides are similar:

| Functional path | With Skill | Without Skill |
|-----------------|-----------|--------------|
| **Eval 1 core paths** | | |
| Rate limit reject (ErrRateLimited) | ✅ | ✅ |
| Circuit breaker open (ErrBreakerOpen) | ✅ | ✅ |
| Context cancellation (during backoff) | ✅ | ✅ |
| Retry boundary (MaxRetries=0/1) | ✅ | ✅ |
| -race passes | ✅ | ✅ |
| **Eval 2 core paths** | | |
| TrySubmit queue full returns false | ✅ | ✅ |
| Shutdown drains tasks | ✅ | ✅ |
| Double-Shutdown safety | ✅ | ✅ |
| Concurrent Submit stress test | ✅ | ✅ |
| -race passes | ✅ | ✅ |
| **Eval 3 core paths** | | |
| Initial burst capacity | ✅ | ✅ |
| Tokens exhausted | ✅ | ✅ |
| Token refill | ✅ | ✅ |
| Burst cap | ✅ | ✅ |
| Concurrent Allow() | ✅ | ✅ |
| -race passes | ✅ | ✅ |

**Conclusion: Functional coverage is the same.** Without-skill did not test fewer code paths; it lacked the methodology framework around those paths.

---

## 4. Skill Differentiator Value Deep Dive

### 4.1 Failure Hypothesis List

**With Skill**: Each scenario produces 7–9 numbered hypotheses (H1–H9), organized by category (Branching, Concurrency, Loop/index, Context/time), each mapped to specific test cases.

**Without Skill**: No such output. Tests are organized by functional area (Rate Limiting, Success Paths, Retry Exhaustion) but with no formal defect analysis.

| Dimension | With Skill | Without Skill |
|-----------|-----------|--------------|
| Hypothesis count | Eval1: 9, Eval2: 7, Eval3: 9 | 0, 0, 0 |
| Defect→test mapping | Each hypothesis labeled Covered By | None |
| Coverage analysis | Traceable which defects are tested | Only see which paths were run |

**Practical value**: The Failure Hypothesis List matters not because "one more table" exists, but because it drives test design — **first think "what bugs might this code have", then design tests accordingly**, rather than "spread coverage by function signature".

### 4.2 Killer Cases

**With Skill**: Each scenario has 3–4 killer cases, each with:
- Linked defect hypothesis (e.g. KC1→H3)
- Fault injection description
- Critical assertion (with concrete field and value)
- **Removal Risk Statement** ("if this assertion is removed, what bug escapes")

Example (Eval 1 KC1):

> **Linked hypothesis**: H3 — ErrBreakerOpen is retried instead of returned immediately
> **Critical assertion**: `backoffCalls == 0` — no retry backoff was triggered
> **Removal risk**: If removed, the known bug (ErrBreakerOpen not short-circuiting retries) can escape detection — 4 unnecessary backoff+retry cycles would occur.

**Without Skill**: Tests cover the same paths (e.g. TestDo_BreakerOpenStopsRetry) but with no removal risk analysis. Developers cannot tell which assertion is "critical for regression" vs "nice to have".

### 4.3 Boundary Checklist

**With Skill**: Standard 12-item checklist, each labeled Covered / N/A + notes:

| # | Item | Status |
|---|------|--------|
| 1 | nil input | Covered — nil Limiter, nil Backoff |
| 2 | Empty value | N/A |
| 3 | Single element (len==1) | Covered — MaxRetries=1 |
| 4 | Size boundary (n=2, n=3, last) | Covered — MaxRetries=0,2,3,-1 |
| ... | ... | ... |

**Without Skill**: No such output. Boundary cases are scattered across test functions with no systematic audit.

### 4.4 Test Organization: Table-Driven vs Separate Functions

| Dimension | With Skill | Without Skill |
|-----------|-----------|--------------|
| Organization | t.Run subtests (TestDo/12 subtests) | 17 separate TestXxx functions |
| Parallel | t.Parallel() | None |
| Naming | Snake_case, verb+expectation (`rate_limited_returns_ErrRateLimited`) | PascalCase (`TestDo_RateLimited`) |
| Maintainability | Add case = add one table row | Add case = new function + repeated setup |

### 4.5 Auto Scorecard (13-Check Tiered Scorecard)

With-skill output includes a structured 13-item scorecard (3 Critical + 5 Standard + 5 Hygiene) with pass/fail evidence and tiered summary. Without-skill has no such output.

### 4.6 Additional Findings

With-skill runs surfaced **real insights** in the code that Without-skill did not mention:

| Finding | Scenario | Notes |
|---------|----------|------|
| Worker pool quit channel dead code | Eval 2 | Worker `select`’s `quit` branch never triggers in `close(tasks)` + `range` mode |
| `Tokens()` state mutation risk | Eval 3 | Reading Tokens calls internal `refill()`, changing state; read has side effects |
| Token fractional threshold precision risk | Eval 3 | Float comparison `l.tokens >= 1` after refill may have precision issues |

---

## 5. Comprehensive Analysis

### 5.1 Skill Differentiator Value Map

| Dimension | Contribution | Notes |
|-----------|--------------|-------|
| **Methodology framework** | ★★★★★ | Failure Hypothesis List + Killer Cases + Boundary Checklist are capabilities Without-skill does not produce |
| **Test organization discipline** | ★★★★☆ | table-driven + t.Run + t.Parallel consistently applied; Without-skill did not follow |
| **Quality audit traceability** | ★★★★★ | 13-check Scorecard + Removal Risk Statement provide auditable evidence of test quality |
| **Defect discovery** | ★★☆☆☆ | Code insights (dead code, side effects) are bonus; functional path coverage same as Without-skill |
| **Functional coverage difference** | ★☆☆☆☆ | Core paths fully covered by both; no difference |

### 5.2 Skill’s True Value Proposition

```
The skill is not for "testing more paths" — it is for "thinking systematically about why to test a path".
```

Core value by importance:

1. **Defect-hypothesis-driven test design** — List "possible bugs" (H1–H9) first, then design tests. Without-skill instead "traverses parameter combinations by API signature". The former finds bugs; the latter spreads coverage.
2. **Killer Case + Removal Risk** — Each killer case answers "what bug does this assertion prevent from escaping". Without this, maintainers cannot distinguish critical from redundant assertions and may delete them during refactors.
3. **Structured quality audit** — 13-check Scorecard provides quantifiable quality judgment (Critical tier all pass = mergeable), not subjective "looks well tested".
4. **Systematic boundary checklist** — 12-item standard checklist ensures nil, empty, boundary, concurrency, context cancellation, etc. are not missed; each item’s Covered/N/A provides audit trail.
5. **Consistent test organization** — table-driven + t.Run is not just style; it affects maintainability and the cost of adding cases.

### 5.3 Skill Weaknesses

1. **No functional coverage difference**: In all 3 scenarios, Without-skill covered the same core paths as With-skill (rate limit, circuit breaker, context cancel, concurrency). The skill’s differentiation is entirely at the methodology level, not "what to test".
2. **Without-skill sometimes has more test cases**: Eval 1 Without-skill produced 17 separate test functions vs With-skill’s 12 subtests. More cases ≠ higher quality, but shows Without-skill is not "testing less".
3. **Methodology output value depends on team**: Failure Hypothesis List and Killer Cases may be "helpful but not essential" for senior developers; more valuable for test newcomers or code review.
4. **Limited evaluation scenarios**: Only 3 concurrency/design-pattern scenarios; no database ops, HTTP handlers, pure logic functions, etc.

---

## 6. Score Summary

### 6.1 Dimension Scores

| Dimension | With Skill | Without Skill | Delta |
|-----------|-----------|--------------|-------|
| Functional coverage | 5.0/5 | 5.0/5 | 0.0 |
| **Methodology completeness** | **5.0/5** | **1.0/5** | **+4.0** |
| Test organization | 5.0/5 | 2.5/5 | +2.5 |
| Traceability (audit) | 5.0/5 | 1.0/5 | +4.0 |
| Code insight | 4.0/5 | 3.0/5 | +1.0 |
| Maintainability | 4.5/5 | 3.0/5 | +1.5 |
| **Overall mean** | **4.75/5** | **2.58/5** | **+2.17** |

### 6.2 Weighted Total Score

| Dimension | Weight | Score | Weighted |
|-----------|-------|------|----------|
| Trigger accuracy | 25% | 10/10 | 2.50 |
| Assertion pass rate (with/without delta) | 20% | 9.2/10 | 1.84 |
| Methodology output (hypothesis/Killer/checklist) | 20% | 10/10 | 2.00 |
| Test organization & maintainability | 15% | 9.0/10 | 1.35 |
| Code insight added value | 10% | 7.0/10 | 0.70 |
| Functional coverage difference (vs baseline) | 10% | 5.0/10 | 0.50 |
| **Weighted total** | | | **8.89/10** |

---

## 7. Evaluation Methodology

### Trigger Evaluation
- **Method**: Subagent simulation of trigger judgment (3 independent rounds × 20 queries = 60 judgments)
- **Query design**: 10 positive (Chinese/English, direct/indirect trigger modes) + 10 negative (6 adjacent task types: benchmark/fuzz/integration/E2E/load/mock + CI/docs/translation/profiling)
- **Environment**: Cursor IDE Task subagent (generalPurpose, fast model), fresh context each round
- **Limitation**: Proxy test, not end-to-end real trigger; does not account for 50+ competing skills

### Task Evaluation
- **Method**: 3 scenarios × 2 configs = 6 independent subagent runs
- **Target code**: All real Go code in repo with no existing tests (not artificially constructed)
- **Assertions**: 34, covering file creation, methodology output, functional paths, test organization, race safety, quality audit (6 dimensions)
- **Scoring**: Manual per-assertion comparison with subagent output; record pass/fail + evidence
- **Baseline**: Same prompt, SKILL.md not read

### Evaluation Materials
- Trigger evaluation queries: `unit-test-workspace/trigger-eval-set.json`
- Trigger evaluation results: `unit-test-workspace/trigger-eval-results.json`
- Eval definitions: `unit-test-workspace/evals/evals.json`
- Scoring results: `unit-test-workspace/iteration-1/{resilience-do,worker-pool,rate-limiter}/{with_skill,without_skill}/grading.json`
- Benchmark summary: `unit-test-workspace/iteration-1/benchmark.json`
- Description improvement report: `unit-test-workspace/description-improvement-report.md`
- Eval viewer: `unit-test-workspace/iteration-1/eval-review.html`
- Generated test code: `unit-test-workspace/iteration-1/*/outputs/*_test.go`
- Generated reports: `unit-test-workspace/iteration-1/*/outputs/report.md`

# fuzzing-test Skill Evaluation Report

> Evaluation framework: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> Evaluation date: 2026-03-12
> Evaluation subject: `fuzzing-test`

---

`fuzzing-test` is a skill specialized in generating high-signal fuzz tests for Go code, suitable for parsers, codecs, state transitions, and other targets with clear invariants. It also helps determine when a target is not worth fuzzing at all. Its three main strengths are: running an Applicability Gate first before deciding whether to enter the generation flow, avoiding "write fuzz for every function"; explicitly rejecting unsuitable targets with alternative suggestions instead of producing low-value code; and built-in target prioritization, cost tiers, and structured output for more controllable, cost-effective fuzz testing.

## 1. Evaluation Overview

This evaluation reviews the fuzzing-test skill along two dimensions: **actual task performance** and **token cost-effectiveness**. It uses 3 fuzz test generation scenarios (suitable parser target, unsuitable network-dependent target, package-level evaluation with multiple candidate functions), each run with both with-skill and without-skill configurations—3 scenarios × 2 configs = 6 independent subagent runs—scored against 35 assertions.

| Dimension | With Skill | Without Skill | Delta |
|-----------|-----------|--------------|-------|
| **Assertion pass rate** | **35/35 (100%)** | 16/35 (45.7%) | **+54.3 pp** |
| **Applicability Gate correctness** | 3/3 scenarios correct | 0/3 with formal gate | Skill-only |
| **Rejection of unsuitable targets** | Correct rejection + alternatives | Built workaround instead | Largest single delta |
| **Output Contract structured report** | 3/3 | 0/3 | Skill-only |
| **Size guard coverage** | 100% (all harnesses) | ~25% (partial harnesses) | Skill systematic |
| **Skill Token cost (SKILL.md only)** | ~4,100 tokens | 0 | — |
| **Skill Token cost (typical load)** | ~6,500 tokens | 0 | — |
| **Token cost per 1% pass-rate gain** | ~75 tok (SKILL.md only) / ~120 tok (typical) | — | — |

---

## 2. Test Methodology

### 2.1 Scenario Design

| Scenario | Repo / Target | Focus | Assertions |
|----------|---------------|-------|------------|
| Eval 1: parser-fuzz | `internal/parser/Parse` — URL parser, pure function | Full flow for Tier 1 fuzzing target | 15 |
| Eval 2: fetch-reject | `internal/github/fetcher.Fetch` — network-dependent method | Correct rejection of unsuitable fuzzing target | 7 |
| Eval 3: converter-multi | `internal/converter` package — multiple candidate functions | Multi-target selection, priority evaluation, selective generation | 13 |

### 2.2 Execution

- Use `issue2md` project as base; create independent copies per scenario (`/tmp/fuzz-eval-*`)
- With-skill runs load SKILL.md and referenced materials first
- Without-skill runs load no skill; model uses default behavior
- All runs execute in parallel in independent subagents

### 2.3 Scenario Details

**Eval 1 — parser.Parse (suitable target)**

`Parse(rawURL string) (ResourceRef, error)` is a classic Tier 1 fuzz target:
- Accepts `string` input (native Go fuzz type)
- Pure function, no I/O, network, or state
- Multiple verifiable invariants (non-empty Owner, Number > 0, Type ∈ valid set, canonical URL consistency, re-parse idempotency)
- Fast execution (sub-microsecond)

**Eval 2 — fetcher.Fetch (unsuitable target)**

`Fetch(ctx, ref, opts) (IssueData, error)` is a classic unsuitable fuzz target:
- All code paths perform real HTTP requests
- Depends on GitHub API token auth
- Includes retry + backoff logic
- Interesting input space is API response, not method parameters

**Eval 3 — converter package (multiple candidates)**

5 candidate functions: 4 suitable, 1 unsuitable:
- ✅ `yamlQuote(string) string` — YAML escaping, round-trip invariant
- ✅ `normalizeSummaryJSON(string) (string, error)` — JSON extractor, `json.Valid` invariant
- ✅ `detectSummaryLanguage(string) string` — Unicode analysis, finite return set invariant
- ✅ `capSummarySourceLength(string) string` — rune truncation, length upper-bound invariant
- ❌ `Summarize(ctx, data, lang)` — OpenAI HTTP call, network-dependent

---

## 3. Assertion Pass Rate

### 3.1 Overview

| Scenario | Assertions | With Skill | Without Skill | Delta |
|----------|-----------|-----------|--------------|-------|
| Eval 1: parser-fuzz | 15 | **15/15 (100%)** | 8/15 (53.3%) | +46.7pp |
| Eval 2: fetch-reject | 7 | **7/7 (100%)** | 0/7 (0%) | +100pp |
| Eval 3: converter-multi | 13 | **13/13 (100%)** | 8/13 (61.5%) | +38.5pp |
| **Total** | **35** | **35/35 (100%)** | **16/35 (45.7%)** | **+54.3pp** |

### 3.2 Per-Scenario Assertion Details

#### Eval 1: parser-fuzz (15 assertions)

| # | Assertion | With Skill | Without Skill |
|---|-----------|-----------|--------------|
| A1.1 | Applicability gate before code execution | ✅ Full 5-item checklist | ❌ No formal gate, direct analysis |
| A1.2 | Correctly judged "suitable" | ✅ | ✅ (implicit) |
| A1.3 | 5-item checklist per-item Pass/Fail | ✅ Structured table | ❌ None |
| A1.4 | Fuzz mode identified as "parser robustness" | ✅ "Parser robustness + idempotency" | ❌ Not labeled |
| A1.5 | f.Add() ≥3 valid GitHub URLs | ✅ 5 | ✅ 4 |
| A1.6 | f.Add() includes malformed/boundary | ✅ 14 | ✅ 25 (more) |
| A1.7 | Size guard present | ✅ `len > 2048 → t.Skip()` | ❌ None |
| A1.8 | Oracle: Owner/Repo non-empty | ✅ | ✅ |
| A1.9 | Oracle: Number > 0 | ✅ | ✅ |
| A1.10 | Oracle: Type ∈ valid set | ✅ | ✅ |
| A1.11 | FuzzXxx naming | ✅ `FuzzParse` in `fuzz_parse_test.go` | ✅ `FuzzParse` in `fuzz_test.go` |
| A1.12 | Cost class assigned | ✅ "Low, 30-60s" | ❌ None |
| A1.13 | Quick commands provided | ✅ 3 commands | ❌ None |
| A1.14 | Output contract / structured report | ✅ Full Quality Scorecard | ❌ Narrative summary only |
| A1.15 | Corpus replay verification | ✅ 19 seeds green | ✅ 29 seeds passed |

#### Eval 2: fetch-reject (7 assertions)

| # | Assertion | With Skill | Without Skill |
|---|-----------|-----------|--------------|
| A2.1 | Applicability gate executed | ✅ 5-item structured table | ❌ No gate |
| A2.2 | Judged "unsuitable" | ✅ "Not suitable for fuzzing" | ❌ Did not reject; built workaround |
| A2.3 | Specific failing checks | ✅ Check 1/3/4/5 all Fail | ❌ No failure references |
| A2.4 | No fuzz code generated | ✅ "None" | ❌ Generated 112 lines |
| A2.5 | Alternative test strategies provided | ✅ 4 concrete strategies | ❌ No alternatives |
| A2.6 | Explanation specific (not generic) | ✅ References doWithRetry, f.rest, f.gql, etc. | ❌ No unsuitability explanation |
| A2.7 | Output contract | ✅ Full 5-section report | ❌ None |

#### Eval 3: converter-multi (13 assertions)

| # | Assertion | With Skill | Without Skill |
|---|-----------|-----------|--------------|
| A3.1 | Per-candidate gate evaluation | ✅ Per-function evaluation | ❌ Informal analysis table |
| A3.2 | Target priority evaluation | ✅ Priority ordering | ❌ No Tier ordering |
| A3.3 | Summarize rejected | ✅ | ✅ "Not suitable" |
| A3.4 | yamlQuote fuzz test generated | ✅ round-trip oracle | ✅ round-trip oracle |
| A3.5 | normalizeSummaryJSON generated | ✅ JSON validity oracle | ✅ JSON validity oracle |
| A3.6 | detectSummaryLanguage generated | ✅ valid set oracle | ✅ valid set oracle |
| A3.7 | capSummarySourceLength generated | ✅ rune count + truncation | ✅ rune count + truncation |
| A3.8 | Each harness has oracle | ✅ 4/4 with t.Fatalf | ✅ 4/4 with t.Fatalf |
| A3.9 | Each harness has seeds | ✅ ≥7 per target | ✅ ≥5 per target |
| A3.10 | Size guards coverage | ✅ 4/4 harnesses have guard | ❌ 0/4 have guard |
| A3.11 | Per-target cost class | ✅ | ❌ None |
| A3.12 | Output contract with per-target details | ✅ | ❌ No structured report |
| A3.13 | Corpus replay verification | ✅ 40 seeds pass | ✅ 38 seeds pass |

### 3.3 Classification of 19 Without-Skill Failed Assertions

| Failure type | Count | Evals | Notes |
|--------------|-------|-------|-------|
| **Missing Applicability Gate** | 3 | Eval 1/2/3 | No formal 5-item checklist; direct coding or analysis |
| **Unsuitable target not rejected** | 4 | Eval 2 | Built HTTP stub workaround instead of reject + recommend alternatives |
| **Missing Output Contract** | 3 | Eval 1/2/3 | No structured report, Quality Scorecard |
| **Missing Size Guard** | 2 | Eval 1/3 | Eval 1 no len check; Eval 3 all four harnesses missing |
| **Missing Cost Class** | 2 | Eval 1/3 | No Low/Medium/High classification |
| **Missing Quick Commands** | 1 | Eval 1 | No `go test -fuzz` command reference |
| **Missing Fuzz Mode label** | 1 | Eval 1 | No "parser robustness" mode label |
| **Missing Target Priority** | 1 | Eval 3 | No Tier 1/2/3 priority ordering |
| **Missing Checklist structure** | 1 | Eval 1 | No per-item Pass/Fail marks |
| **Missing alternative strategies** | 1 | Eval 2 | Built solution directly instead of recommending better strategies |

### 3.4 Key Finding: Eval 2 +100pp Delta

This is the **largest single-scenario delta** among all evaluated skills. Analysis:

**With-Skill behavior**:
- Runs 5-item Applicability Gate
- Marks Check 1/3/4/5 as Fail (especially Check 3 — no oracle — triggers Hard Stop)
- Produces "Not suitable" verdict
- Recommends 4 alternative strategies, including "fuzz pure mapping functions in the package"

**Without-Skill behavior**:
- No gate; directly analyzed how to make fuzz work
- Creatively built `fuzzRoundTripper` (custom `http.RoundTripper`) to stub HTTP layer
- Effectively fuzzed GraphQL JSON parsing path, not the `Fetch` method itself
- Only oracle was "no panic"

**Assessment**: The baseline approach has practical value (can find panics in JSON parsing) but from fuzz testing best practices:
1. Oracle is only "no panic"; cannot find logic bugs (invariant violations)
2. Actually tests JSON parsing path, not the `Fetch` method under review
3. Does not tell the user "this is not optimal," missing the chance to steer them toward fuzzing pure functions

The skill's gate mechanism ensures **honest engineering decisions**: if unsuitable, do not proceed, and recommend better alternatives.

---

## 4. Dimension-by-Dimension Comparison

### 4.1 Applicability Gate

This is the skill's core differentiator, affecting all 3 scenarios.

| Scenario | With Skill | Without Skill |
|----------|-----------|--------------|
| Eval 1 (suitable) | 5-item checklist all Pass, structured table | Informal analysis, no Pass/Fail marks |
| Eval 2 (unsuitable) | Check 1/3/4/5 Fail → Hard Stop | Not identified as unsuitable |
| Eval 3 (mixed) | Per-function gate; 4 of 5 Pass | Informal analysis table; Summarize correctly identified |

**Practical value**:
- Applicability Gate prevents generating useless fuzz tests (Eval 2 saves cost of writing and maintaining low-value tests)
- Structured checklist makes decisions auditable and reproducible
- In Eval 3, enforces "evaluate first, then code" workflow

### 4.2 Systematic Size Guard Coverage

| Scenario | With Skill | Without Skill |
|----------|-----------|--------------|
| Eval 1: FuzzParse | ✅ `len > 2048 → t.Skip()` | ❌ None |
| Eval 3: FuzzYamlQuote | ✅ `len > 1<<16 → t.Skip()` | ❌ None |
| Eval 3: FuzzNormalizeSummaryJSON | ✅ `len > 1<<16 → t.Skip()` | ❌ None |
| Eval 3: FuzzDetectSummaryLanguage | ✅ `len > 1<<16 → t.Skip()` | ❌ None |
| Eval 3: FuzzCapSummarySourceLength | ✅ `len > 1<<20 → t.Skip()` | ❌ None |

**Analysis**: The skill's "Size guard present" rule (in SKILL.md Templates A/B/C/D) ensures all `string`/`[]byte` harnesses have boundary protection. Without-skill had more seeds in Eval 1 (29 vs 19) but lacked size guards; long fuzz runs risk OOM.

### 4.3 Output Contract (Structured Report)

With-Skill runs produce structured reports including:

| Report item | Eval 1 | Eval 2 | Eval 3 |
|-------------|--------|--------|--------|
| Applicability Verdict | ✅ Suitable | ✅ Not suitable | ✅ Per-function |
| Why (2–6 bullets) | ✅ 5 bullets | ✅ 4 bullets | ✅ Per-function |
| Action | ✅ Implemented | ✅ Stop | ✅ 4 targets implemented |
| Quality Scorecard (C/S/H) | ✅ All PASS | N/A | ✅ All PASS |
| Cost Class | ✅ Low | N/A | ✅ Per-target |
| Quick Commands | ✅ 3 commands | N/A | ✅ |
| Corpus Policy | ✅ | N/A | ✅ |

Without-Skill produces narrative summaries but no standardized structure.

### 4.4 Fuzz Code Quality Comparison

Using Eval 3 (best for code quality comparison), `FuzzYamlQuote`:

| Feature | With Skill | Without Skill |
|---------|-----------|--------------|
| Seed count | 11 | 10 |
| Size guard | ✅ `len > 1<<16` | ❌ None |
| Oracle: single-quote wrapping | ✅ | ✅ |
| Oracle: odd-quote detection | ✅ | ✅ |
| Oracle: round-trip | ✅ `unescaped == value` | ✅ `unescaped == value` |
| Large-input seed | None | `strings.Repeat("a", 10000)` |

**Code quality** is similar in oracle design; Claude's base model is already strong at fuzz code generation. The skill's main gains are **process discipline** (gate, cost class, size guard, output contract), not the code itself.

### 4.5 Alternative Strategy Recommendations

In Eval 2, With-Skill recommended 4 alternatives:

1. **Integration tests with real GitHub token (gated)** — gated integration tests
2. **Unit tests with HTTP stubbing** — httptest.Server stub tests
3. **Fuzz the pure mapping functions instead** — e.g. `mapIssueTimelineNode`
4. **Table-driven unit tests for the dispatcher** — table-driven unit tests

These recommendations both reject the unsuitable approach and steer users toward more valuable testing paths. Without-Skill built a workaround directly (valuable, but did not inform users of better options).

---

## 5. Token Cost-Effectiveness Analysis

### 5.1 Skill Size

| File | Lines | Words | Est. Tokens |
|------|-------|------|-------------|
| **SKILL.md** | 679 | 3,062 | ~4,100 |
| references/applicability-checklist.md | 170 | 940 | ~1,250 |
| references/target-priority.md | 179 | 876 | ~1,170 |
| references/crash-handling.md | 76 | 312 | ~420 |
| references/ci-strategy.md | 118 | 463 | ~620 |
| **Description (always in context)** | — | ~50 | ~65 |

### 5.2 Load Scenarios

| Scenario | Files read | Total tokens |
|----------|------------|-------------|
| Suitable target (Eval 1) | SKILL.md + applicability + target-priority | ~6,520 |
| Unsuitable target (Eval 2) | SKILL.md + applicability | ~5,350 |
| Multi-target evaluation (Eval 3) | SKILL.md + applicability + target-priority | ~6,520 |
| SKILL.md only (min load) | SKILL.md | ~4,100 |
| Full load | All files | ~7,625 |
| **Typical load** | **SKILL.md + applicability + target-priority** | **~6,520** |

### 5.3 Token Cost for Quality Gain

| Metric | Value |
|--------|-------|
| With-skill pass rate | 100% (35/35) |
| Without-skill pass rate | 45.7% (16/35) |
| Pass-rate gain | +54.3 pp |
| Token cost per assertion fixed | ~216 tok (SKILL.md only) / ~343 tok (typical) |
| Token cost per 1% pass-rate gain | ~75 tok (SKILL.md only) / ~120 tok (typical) |

### 5.4 Token Segment Cost-Effectiveness

| Module | Est. tokens | Linked assertion delta | Cost-effectiveness |
|--------|-------------|------------------------|---------------------|
| **Applicability Gate rules** | ~300 | 7 (3-scenario gate correctness) | **Very high** — 43 tok/assertion |
| **Output Contract definition** | ~200 | 3 (3-scenario report completeness) | **Very high** — 67 tok/assertion |
| **Templates A–D** | ~600 | 2 (size guard coverage) | **High** — 300 tok/assertion |
| **Cost Class + Quick Commands** | ~100 | 3 (classification + command refs) | **Very high** — 33 tok/assertion |
| **Fuzz Mode classification** | ~80 | 1 (mode label) | **Very high** — 80 tok/assertion |
| **Target Priority rules** | ~150 | 1 (Tier ordering) | **High** — 150 tok/assertion |
| **Hard Stop rules** | ~100 | 2 (unsuitable rejection + no code) | **Very high** — 50 tok/assertion |
| **Quality Scorecard** | ~200 | Indirect (structured self-check) | **Medium** |
| **Anti-Examples** | ~500 | Indirect (avoid common mistakes) | **Medium** |
| **Coverage Feedback** | ~400 | 0 (not tested) | **Low** |
| **Go Version Gate** | ~200 | 0 (not tested) | **Low** |
| **Troubleshooting** | ~350 | 0 (not tested) | **Low** |
| **applicability-checklist.md** | ~1,250 | Indirect (gate quality) | **Medium** |
| **target-priority.md** | ~1,170 | Indirect (priority quality) | **Medium** |
| **crash-handling.md** | ~420 | 0 (no crash scenario) | **Low** |
| **ci-strategy.md** | ~620 | 0 (CI integration not tested) | **Low** |

### 5.5 High-Leverage vs Low-Leverage Instructions

**High leverage (~930 tokens SKILL.md → 19 assertion delta, 23% of SKILL.md):**
- Applicability Gate + Hard Stop rules (400 tok → 9 assertions)
- Output Contract definition (200 tok → 3 assertions)
- Cost Class + Quick Commands (100 tok → 3 assertions)
- Size guard examples in Templates (150 tok → 2 assertions)
- Fuzz Mode + Target Priority (80+150 tok → 2 assertions)

**Medium leverage (~700 tokens → indirect):**
- Quality Scorecard (200 tok) — drives self-check flow
- Anti-Examples (500 tok) — avoid common mistakes

**Low leverage (~950 tokens → 0 assertion delta):**
- Coverage Feedback (~400 tok) — not used in eval scenarios
- Go Version Gate (~200 tok) — not used in eval scenarios
- Troubleshooting (~350 tok) — not used in eval scenarios

**References (~3,460 tokens → indirect):**
- applicability-checklist.md (1,250 tok) — improves gate quality, concrete examples
- target-priority.md (1,170 tok) — Tier ordering basis
- crash-handling.md + ci-strategy.md (1,040 tok) — no direct contribution in eval

### 5.6 Token Efficiency Rating

| Rating | Conclusion |
|--------|------------|
| **Overall ROI** | **Excellent** — ~6,520 tokens (typical) for +54.3% pass rate |
| **SKILL.md ROI** | **Good** — ~4,100 tokens; high-leverage rules only 23% |
| **High-leverage token share** | 23% (930/4,100) directly contributes 19/19 assertion delta |
| **Low-leverage token share** | 23% (950/4,100) no incremental contribution in this eval |
| **Reference cost-effectiveness** | **Medium** — ~2,420 tokens (applicability + target-priority) indirect contribution |
| **Unused references** | ~1,040 tokens (crash-handling + ci-strategy) no contribution |

### 5.7 Cost-Effectiveness vs Other Skills

| Metric | fuzzing-test | go-makefile-writer | create-pr | go-ci-workflow |
|--------|-------------|-------------------|-----------|----------------|
| SKILL.md tokens | ~4,100 | ~1,960 | ~2,700 | ~1,500 |
| Typical load tokens | ~6,520 | ~4,100 | ~4,800 | ~4,500 |
| Pass-rate gain | +54.3% | +31.0% | +71.0% | +33.0% |
| Tokens per 1% (SKILL.md) | ~75 tok | ~63 tok | ~38 tok | ~45 tok |
| Tokens per 1% (typical) | ~120 tok | ~132 tok | ~68 tok | ~136 tok |

**Analysis**:
- `fuzzing-test` has the **largest delta** (+54.3%), mainly from Eval 2's +100pp extreme delta
- SKILL.md cost-effectiveness (~75 tok/1%) is mid-range: higher than create-pr (38) and go-ci-workflow (45), lower than go-makefile-writer (63)
- Typical-load cost-effectiveness (~120 tok/1%) is better than go-makefile-writer and go-ci-workflow, worse than create-pr
- SKILL.md size (679 lines / ~4,100 tokens) is the largest among evaluated skills, but its delta is also the largest

---

## 6. Boundary Analysis vs Claude Base Model

### 6.1 Base Model Capabilities (No Skill Increment)

| Capability | Evidence |
|------------|----------|
| Go fuzz test basics | 3/3 scenarios use `testing.F` correctly |
| f.Add() seed corpus | 3/3 scenarios provide good seeds |
| Oracle design (no-panic, round-trip, valid set) | Eval 1/3 oracle quality close to with-skill |
| Multi-candidate recognition (partial) | Eval 3 correctly identifies Summarize as unsuitable |
| File naming `*_test.go` | 3/3 scenarios correct |
| Corpus replay verification | 3/3 scenarios run verification |

### 6.2 Base Model Gaps (Skill Fills)

| Gap | Evidence | Risk level |
|-----|----------|------------|
| **Rejecting unsuitable targets** | Eval 2: built workaround instead of reject | High — would maintain low-value fuzz tests in prod |
| **Systematic Size Guard** | 5/5 harnesses missing size guard | High — OOM risk in long fuzz runs |
| **Applicability Gate flow** | 3/3 scenarios no formal gate | Medium — no decision audit |
| **Output Contract** | 3/3 scenarios no structured report | Medium — no change traceability |
| **Cost Class assignment** | 2/3 scenarios no classification | Medium — CI budget cannot be allocated |
| **Quick Commands** | 1/3 scenarios no command reference | Low — user must look up docs |
| **Fuzz Mode label** | 1/3 scenarios not labeled | Low — affects readability |
| **Target Priority** | 1/3 scenarios no Tier ordering | Low — no priority guidance for multi-target |

---

## 7. Overall Score

### 7.1 Dimension Scores

| Dimension | With Skill | Without Skill | Delta |
|-----------|-----------|--------------|-------|
| Applicability Gate correctness | 5.0/5 | 1.5/5 | +3.5 |
| Rejection of unsuitable targets | 5.0/5 | 0.0/5 | +5.0 |
| Fuzz code quality (oracle, seed, guard) | 5.0/5 | 3.5/5 | +1.5 |
| Structured report (Output Contract) | 5.0/5 | 0.5/5 | +4.5 |
| Alternative strategy recommendations | 5.0/5 | 1.0/5 | +4.0 |
| Process discipline (cost class, mode, commands) | 5.0/5 | 1.5/5 | +3.5 |
| **Overall mean** | **5.0/5** | **1.33/5** | **+3.67** |

### 7.2 Weighted Total Score

| Dimension | Weight | Score | Rationale | Weighted |
|-----------|--------|-------|-----------|----------|
| Assertion pass-rate delta | 25% | 10.0/10 | +54.3pp is highest delta among evaluated skills | 2.50 |
| Applicability Gate correctness | 20% | 10.0/10 | 3/3 scenarios gate correct; Eval 2 shows Hard Stop value | 2.00 |
| Rejection + alternative recommendations | 15% | 10.0/10 | +100pp single-scenario delta; 4 concrete alternatives | 1.50 |
| Structured report (Output Contract) | 15% | 10.0/10 | 3/3 scenarios full contract; Quality Scorecard | 1.50 |
| Token cost-effectiveness | 15% | 6.0/10 | SKILL.md ~4,100 tok large; ~950 tok low-leverage; ~1,040 tok refs unused | 0.90 |
| Fuzz code quality | 10% | 8.0/10 | Code quality similar to baseline; main gain is size guard | 0.80 |
| **Weighted total** | **100%** | | | **9.20/10** |

### 7.3 Comparison with Other Skills

| Skill | Weighted total | Pass-rate delta | Tokens/1% (typical) | Strongest dimension |
|-------|----------------|-----------------|---------------------|----------------------|
| create-pr | 9.55/10 | +71pp | ~68 | Gate flow (+3.5), Output Contract (+4.0) |
| **fuzzing-test** | **9.20/10** | **+54.3pp** | **~120** | **Rejection (+5.0), Output Contract (+4.5)** |
| go-makefile-writer | 9.16/10 | +31pp | ~132 | CI reproducibility (+3.0), Output Contract (+4.0) |
| go-ci-workflow | 8.83/10 | +33pp | ~136 | Degradation handling (+4.5), Output Contract (+4.0) |

**Analysis**:
- `fuzzing-test` **rejection** (+5.0 delta) is the **largest single-dimension delta** among evaluated skills
- +54.3pp delta is also the highest, proving Applicability Gate value
- Token cost-effectiveness score (6.0/10) is lower due to SKILL.md size (679 lines) and ~950 tokens low-leverage content

---

## 8. Conclusion

The `fuzzing-test` skill adds clear value in three areas:

1. **Applicability Gate rejection (+100pp single-scenario delta)**: The **largest single-scenario delta** among evaluated skills, showing that "when not to fuzz" is a major gap for Claude. The baseline builds workarounds for unsuitable targets (not without value) but does not inform users of better strategies.

2. **Systematic Size Guard coverage (5/5 vs 0/5)**: The skill's templates and rules ensure all `string`/`[]byte` harnesses have length bounds, preventing OOM in long fuzz runs. A common omission with large production impact.

3. **Structured Output Contract**: Quality Scorecard (Critical/Standard/Hygiene) makes fuzz test quality measurable and auditable.

**Main risk**: SKILL.md size (~4,100 tokens) is the largest among evaluated skills; ~23% (~950 tokens) is low-leverage. Trimming Coverage Feedback, Troubleshooting, Anti-Examples, and Go Version Gate could reduce SKILL.md ~29% and improve typical-load cost-effectiveness from ~120 tok/1% to ~76 tok/1%.

---

## 9. Evaluation Materials

| Material | Path |
|----------|------|
| Eval 1 with-skill output | `/tmp/fuzz-eval-1/internal/parser/fuzz_parse_test.go` |
| Eval 1 without-skill output | `/tmp/fuzz-eval-b1/internal/parser/fuzz_test.go` |
| Eval 2 with-skill output | (no file — gate rejected, no code generated) |
| Eval 2 without-skill output | `/tmp/fuzz-eval-b2/internal/github/fetcher_fuzz_test.go` |
| Eval 3 with-skill output | `/tmp/fuzz-eval-3/internal/converter/{frontmatter,summary_openai}_fuzz_test.go` |
| Eval 3 without-skill output | `/tmp/fuzz-eval-b3/internal/converter/{fuzz_frontmatter,fuzz_summary_openai}_test.go` |
| Evaluated skill | `/Users/john/.codex/skills/fuzzing-test/SKILL.md` |

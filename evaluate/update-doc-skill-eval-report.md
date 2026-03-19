# update-doc Skill Evaluation Report

> Evaluation framework: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> Evaluation date: 2026-03-19
> Evaluation subject: `update-doc`

---

## 1. Evaluation Overview

This evaluation reviews the `update-doc` skill along two dimensions: **actual task performance** and **token cost-effectiveness**. It uses 3 progressively more complex documentation-update scenarios: a lightweight README patch for a CLI tool, a full README update for a backend service, and codemap generation plus README refactoring for a monorepo. Each scenario was run with both with-skill and without-skill configurations, for 3 scenarios x 2 configs = 6 independent subagent runs, scored against 42 assertions.

| Dimension | With Skill | Without Skill | Delta |
|------|-----------|--------------|------|
| **Assertion pass rate** | **42/42 (100%)** | 18/42 (42.9%) | **+57.1 percentage points** |
| **Project-type routing** | 3/3 correct | 0/3 | Skill-only |
| **Output mode selection** | 3/3 correct | 0/3 | Skill-only |
| **Structured reporting (Evidence Map / Scorecard)** | 6/6 | 0/6 | Skill-only |
| **CI drift guardrails** | 2/2 | 0/2 | Skill-only |
| **Diff-scope discipline** | 2/2 | 0/2 | Largest quality gap |
| **Codemap structure completeness** | 2/2 | 0/2 | Skill-only |
| **Skill token overhead (SKILL.md only)** | ~2,100 tokens | 0 | - |
| **Skill token overhead (including references)** | ~2,640 tokens | 0 | - |
| **Token cost per 1% pass-rate gain** | ~46 tokens (full) | - | - |

---

## 2. Test Method

### 2.1 Scenario Design

| Scenario | Repository | Core evaluation points | Assertions |
|------|------|-----------|-----------|
| Eval 1: lightweight CLI patch | `go-file-converter` (Go CLI tool) | Lightweight mode selection, diff scope, CLI routing, evidence-backed updates, anti-pattern avoidance | 13 |
| Eval 2: full service update | `go-notification-service` (Go + Gin + PostgreSQL) | Full mode selection, service routing, runtime modes, Quality Scorecard, CI drift guardrails | 15 |
| Eval 3: monorepo codemap | `platform-monorepo` (mixed Go + TypeScript) | Monorepo routing, Codemap Output Contract, Full Output Mode, `Not found in repo` discipline | 14 |

### 2.2 Test Repository Details

**Eval 1: go-file-converter**
- `cmd/convert/main.go`: flag parsing (`--format` default `"json"`, `--output-dir` default `"."`, `--verbose`)
- Existing `README.md`: missing `--output-dir`, outdated default for `--format` (documented as `csv`)
- Focus: patch only the 2 mismatches without rewriting the whole file

**Eval 2: go-notification-service**
- `cmd/api/main.go` (API server) + `cmd/worker/main.go` (new Worker mode)
- New environment variables: `WORKER_CONCURRENCY` (default 5), `QUEUE_URL` (required)
- Makefile with 9 targets, `docker-compose.yml` with 4 services
- Existing `README.md` covers only API mode

**Eval 3: platform-monorepo**
- `services/auth/` (Go, port changed from 8080 to 8443 TLS), `services/billing/` (Go, new Stripe integration)
- `packages/ui-kit/` (TS), `packages/api-client/` (TS, new `AuthClient` + `BillingClient`)
- `.github/workflows/ci.yml` includes markdownlint
- Existing `README.md` is missing `billing` and `api-client`, and the `auth` port is outdated

### 2.3 Execution Method

- Each scenario used an independent Git repository with code and `go.mod` preloaded.
- With-skill runs first read `SKILL.md` and its referenced materials (`update-doc.md`, `project-routing.md`, `ci-drift.md`).
- Without-skill runs did not read any skill and updated the docs using the model's default behavior.
- All runs were executed in parallel in independent subagents.

---

## 3. Assertion Pass Rate

### 3.1 Overview

| Scenario | Assertions | With Skill | Without Skill | Delta |
|------|-----------|-----------|--------------|------|
| Eval 1: lightweight CLI patch | 13 | **13/13 (100%)** | 5/13 (38.5%) | +61.5% |
| Eval 2: full service update | 15 | **15/15 (100%)** | 8/15 (53.3%) | +46.7% |
| Eval 3: monorepo codemap | 14 | **14/14 (100%)** | 5/14 (35.7%) | +64.3% |
| **Total** | **42** | **42/42 (100%)** | **18/42 (42.9%)** | **+57.1%** |

### 3.2 Breakdown of the 24 Failed Assertions Without the Skill

| Failure type | Count | Affected evals | Notes |
|---------|------|----------|------|
| **Project type not explicitly classified** | 3 | All | No routing declaration such as "CLI Tool" / "Service" / "Monorepo" |
| **No output mode selected** | 3 | All | No concept of Lightweight / Full mode |
| **Missing structured Evidence Map** | 2 | Eval 1/2 | No section-to-source-file mapping table |
| **Missing Quality Scorecard** | 2 | Eval 2/3 | No 12-item PASS/FAIL checklist |
| **Missing command verification** | 2 | Eval 1/2 | No distinction between executed and unexecuted commands |
| **Missing Changed Files list** | 1 | Eval 1 | No structured list of changed files |
| **Missing Open Gaps** | 1 | Eval 2 | No unresolved-items list |
| **Missing CI drift guardrails** | 2 | Eval 2/3 | Failed to identify existing CI or suggest additions |
| **No `Not found in repo` markers** | 1 | Eval 3 | Missing information was not explicitly marked |
| **Diff scope overflow** | 2 | Eval 1 | Added unnecessary sections like "How It Works" and "Error Handling" |
| **Failed to preserve structure** | 1 | Eval 1 | Changed the README title / paragraph order |
| **Incomplete codemap structure** | 2 | Eval 3 | Missing required fields like last updated, data flow, and cross-links |
| **Missing module index table** | 1 | Eval 3 | Used a directory tree instead of a module index table |
| **Full directory-tree dump** | 1 | Eval 3 | Embedded the full tree in the README instead of using tables |

### 3.3 Layered Failure Analysis

The 24 failures can be grouped into two layers based on whether the base model could reasonably do them on its own:

| Layer | Failure count | Notes |
|------|--------|------|
| **Missing process / methodology** (the model does not produce these spontaneously) | 17 | Project classification, mode selection, Evidence Map, Scorecard, command verification, Open Gaps, CI drift, `Not found in repo` |
| **Missing quality / discipline** (the model could do these but did not) | 7 | Diff-scope discipline, structure preservation, codemap completeness, avoiding directory-tree dumps |

**Interpretation**: the core value of the skill is that it **injects 17 pieces of methodology discipline**, while anti-patterns and the diff-scope gate provide **7 quality guardrails**.

### 3.4 Trend: the Skill Has the Largest Advantage in the Most Complex Scenario

| Scenario complexity | Without-skill pass rate | With-skill advantage |
|-----------|---------------------|----------------|
| Eval 1 (simple) | 38.5% | +61.5% |
| Eval 2 (medium) | 53.3% | +46.7% |
| Eval 3 (complex) | 35.7% | +64.3% |

Unlike `go-makefile-writer`, where the largest advantage appeared in the simplest scenario, `update-doc` shows its biggest advantage in the **most complex monorepo scenario**. The reason is that Eval 3 requires skill-specific capabilities such as the Codemap Output Contract, multi-module routing, and CI drift detection, which the baseline model is very unlikely to produce on its own.

---

## 4. Dimension-by-Dimension Comparison

### 4.1 Project-Type Routing

This is the skill's **foundational capability** because it directly determines whether all later decisions are correct.

| Scenario | With Skill | Without Skill |
|------|-----------|--------------|
| Eval 1 | "CLI Tool" -> chooses a flags/options-first strategy | No classification, generic handling |
| Eval 2 | "Service / Backend" -> chooses a runtime-modes-first strategy | No classification, but happened to make reasonable updates |
| Eval 3 | "Monorepo" -> chooses a module index + submodule linking strategy | No classification, replaced it with a directory tree |

**Analysis**: in Eval 2, without-skill happened to produce a reasonable service README structure, but without explicit routing the behavior is **unpredictable**. In Eval 3, the same model chose to dump a directory tree instead of creating a module index table. The skill's routing mechanism ensures **consistent** behavior across scenarios.

### 4.2 Output Mode Selection

| Scenario | With Skill | Without Skill |
|------|-----------|--------------|
| Eval 1 | Lightweight (1 file, narrow patch) | No mode concept; rewrote too much |
| Eval 2 | Full (triggered by new runtime mode) | No mode concept; concise response |
| Eval 3 | Full (codemap creation + multiple modules) | No mode concept; concise response |

**Analysis**: the **over-rewrite** in Eval 1 without the skill, which added sections like "How It Works" and "Error Handling", is exactly the behavior the skill's Lightweight mode and Diff Scope Gate are designed to prevent. In Eval 2 and Eval 3, the concise without-skill responses were not verbose, but they **missed structured outputs** such as the Evidence Map, Scorecard, and Open Gaps.

### 4.3 Evidence-Backed Accuracy

Both configurations performed well on **factual accuracy**:

| Dimension | With Skill | Without Skill |
|------|-----------|--------------|
| Environment variable defaults | All correct | All correct |
| Port numbers | All correct | All correct |
| API routes / endpoints | All correct | All correct |
| No invented content | ✅ | ✅ |
| Structured evidence traceability | ✅ (every claim mapped to source file + line numbers) | ❌ (narrative validation only, no structured mapping) |

**Key difference**: the skill does not win on **accuracy**; it wins on **auditability**. The Evidence Map makes every documentation claim traceable to specific code lines, which supports PR review and later maintenance.

### 4.4 Anti-Pattern Avoidance

| Anti-pattern | With Skill | Without Skill |
|-------------|-----------|--------------|
| Scorecard leaked into README | ✅ Not leaked | ✅ No scorecard to leak |
| Verification labels leaked into README | ✅ Not leaked | ✅ Not leaked |
| Audience tags / author notes | ✅ Not added | ✅ Not added |
| Quick start pushed too far down | ✅ Kept near the top | ✅ Kept near the top |
| Useful navigation removed | ✅ Preserved and improved | ⚠️ Replaced table with a directory tree in Eval 3 |
| Over-scoped rewrite | ✅ Strict diff scope | ❌ Added unnecessary sections in Eval 1 |
| Full directory-tree dump | ✅ Used tables | ❌ Dumped the full tree in Eval 3 |

### 4.5 Codemap Quality (Eval 3 Focus)

| Dimension | With Skill | Without Skill |
|------|-----------|--------------|
| `INDEX.md` structure | Overview + codemap table (with links) + cross-module concerns | Flat list, no links to child files |
| Separate codemap files | `backend.md` + `frontend.md` | Only `INDEX.md` |
| Last updated date | ✅ | ❌ |
| Entry points | ✅ | ✅ (partial) |
| Key modules table | ✅ | ❌ (narrative format) |
| Data flow | ✅ (ASCII diagram) | ❌ |
| External dependencies | ✅ | ❌ |
| Cross-links | ✅ (service <-> client links) | ❌ |

### 4.6 CI Drift Guardrails (Eval 2/3 Focus)

| Dimension | With Skill | Without Skill |
|------|-----------|--------------|
| Identifies existing CI config | ✅ Identified markdownlint (Eval 3) | ❌ No analysis |
| Suggests docs drift check | ✅ Includes sample YAML | ❌ |
| Suggests link checker | ✅ Recommends `lychee` | ❌ |
| Suggests `CODEOWNERS` | ✅ | ❌ |

---

## 5. Token Cost-Effectiveness Analysis

### 5.1 Skill Size

| File | Lines | Words | Bytes | Estimated tokens |
|------|------|------|------|-----------|
| **SKILL.md** | 291 | 1,426 | 9,923 | ~2,100 |
| `references/update-doc.md` | 39 | 142 | 961 | ~200 |
| `references/project-routing.md` | 37 | 89 | 588 | ~150 |
| `references/ci-drift.md` | 26 | 94 | 676 | ~150 |
| **Description (always in context)** | - | ~30 | - | ~40 |
| **Total** | **393** | **1,781** | **12,148** | **~2,640** |

### 5.2 Breakdown of SKILL.md by Functional Module

| Module | Estimated tokens | Related assertion delta | Cost-effectiveness |
|------|-----------|---------------------|--------|
| **Hard Rules** | ~200 | 4 assertions (a4,a5,a12 -> passed; b5,b15,c6,c7 -> passed; c12 -> 1 delta) | **High** - 50 tok/delta |
| **Gate 1: Audience / Language** | ~120 | 0 delta assertions (`c14` passed in both) | **Low** - no incremental gain |
| **Gate 2: Project Type Routing** | ~100 | 3 delta assertions (a1,b1,c1) | **Very high** - 33 tok/delta |
| **Gate 3: Diff Scope** | ~120 | 2 delta assertions (a2,a13) | **Very high** - 60 tok/delta |
| **Gate 4: Command Verifiability** | ~100 | 1 delta assertion (b10) | **High** - 100 tok/delta |
| **Anti-Patterns** | ~200 | 3 delta assertions (a6,c9,c10) | **High** - 67 tok/delta |
| **Standard Workflow** | ~300 | 0 direct delta | **Low** - indirect process guidance |
| **Lightweight Output Mode** | ~200 | 4 delta assertions (a3,a9,a10,a11) | **Very high** - 50 tok/delta |
| **Full Output Mode** | ~130 | 5 delta assertions (b2,b8,b9,b12,c2) | **Very high** - 26 tok/delta |
| **Evidence Commands** | ~100 | 0 direct delta | **Low** - indirect exploration guidance |
| **Project-Type Guidance** | ~280 | 1 delta assertion (c5) | **Medium** - 280 tok/delta |
| **README UX Rules** | ~100 | 0 delta assertions (`b7` passed in both) | **Low** - no incremental gain |
| **Codemap Output Contract** | ~200 | 2 delta assertions (c3,c4) | **High** - 100 tok/delta |
| **CI Drift Guardrails** | ~100 | 2 delta assertions (b13,c13) | **Very high** - 50 tok/delta |
| **Quality Scorecard** | ~250 | 2 delta assertions (b8,c11) | **High** - 125 tok/delta |
| **Output Format** | ~150 | Already counted in Lightweight / Full modes | - |

### 5.3 High-Leverage vs Low-Leverage Instructions

**High leverage (~850 tokens -> 17 delta assertions, ~50 tok/delta):**

| Module | Tokens | Delta |
|------|-------|-------|
| Gate 2: Project Type Routing | ~100 | 3 |
| Gate 3: Diff Scope | ~120 | 2 |
| Lightweight Output Mode | ~200 | 4 |
| Full Output Mode | ~130 | 5 |
| CI Drift Guardrails | ~100 | 2 |
| Anti-Patterns (partial) | ~100 | 1 |

**Medium leverage (~750 tokens -> 7 delta assertions, ~107 tok/delta):**

| Module | Tokens | Delta |
|------|-------|-------|
| Hard Rules | ~200 | 1 |
| Gate 4: Command Verifiability | ~100 | 1 |
| Anti-Patterns (partial) | ~100 | 2 |
| Codemap Output Contract | ~200 | 2 |
| Quality Scorecard (including Output Format) | ~150 | 1 |

**Low leverage (~1,000 tokens -> 0 delta assertions):**

| Module | Tokens | Notes |
|------|-------|------|
| Gate 1: Audience / Language | ~120 | `c14` passed in both |
| Standard Workflow | ~300 | Indirect process guidance |
| Evidence Commands | ~100 | Indirect exploration guidance |
| README UX Rules | ~100 | `b7` passed in both |
| Project-Type Guidance (partial) | ~180 | Service / library guidance did not create a difference |
| Repeated Output Format section | ~100 | Overlaps with mode sections |

### 5.4 Token Efficiency Rating

| Rating area | Conclusion |
|------|------|
| **Overall ROI** | **Excellent** - ~2,640 tokens for a +57.1% pass-rate gain |
| **SKILL.md ROI alone** | **Excellent** - ~2,100 tokens contain all high-leverage rules |
| **High-leverage token ratio** | ~40% (850 / 2,100) directly contributes 17 / 24 delta assertions |
| **Low-leverage token ratio** | ~48% (1,000 / 2,100) contributes no incremental gain in this evaluation |
| **Reference material cost-effectiveness** | **Moderate** - ~540 tokens provide supplemental guidance but no standalone assertion delta |

### 5.5 Cross-Skill Cost-Effectiveness Comparison

| Metric | update-doc | go-makefile-writer | git-commit |
|------|-----------|-------------------|------------|
| SKILL.md tokens | ~2,100 | ~1,960 | ~1,120 |
| Total loaded tokens | ~2,640 | ~4,100-4,600 | ~1,120 |
| Pass-rate improvement | **+57.1%** | +31.0% | +22.7% |
| Tokens per 1% gain (SKILL.md) | **~37 tok** | ~63 tok | ~51 tok |
| Tokens per 1% gain (full) | **~46 tok** | ~149 tok | ~51 tok |
| Total assertions | 42 | 42 | 22 |

**`update-doc` has the highest token cost-effectiveness of the three skills**, for three reasons:

1. **A very large pass-rate delta** (+57.1%): the skill injects 17 methodological capabilities that the baseline model does not have at all.
2. **Compact reference materials** (~540 tokens): much smaller than the ~2,600 tokens of reference material in `go-makefile-writer`.
3. **A reasonable share of high-leverage modules**: 40% of the SKILL.md directly drives 71% of the assertion delta.

---

## 6. Boundary Analysis Against Claude's Base Model

### 6.1 Capabilities the Base Model Already Has (No Skill Gain)

| Capability | Evidence |
|------|------|
| Correct extraction and documentation of environment variables | Correct in 3/3 scenarios for both |
| Accurate ports and default values | Correct in 3/3 scenarios for both |
| Correct API route listing | Correct in 3/3 scenarios for both |
| No fabrication of non-existent code content | No fabrication in 3/3 scenarios for both |
| Correct Makefile target references | Correct in 2/2 relevant scenarios for both |
| Reader-friendly basic README flow | The without-skill Eval 2 output was still reasonably readable |
| Basic `docker-compose` documentation | Covered correctly by both in Eval 2 |

### 6.2 Capability Gaps in the Base Model (Filled by the Skill)

| Gap | Evidence | Risk level |
|------|------|---------|
| **No explicit project-type routing** | No classification in 3/3 scenarios | High - leads to inconsistent strategies |
| **No output mode control** | No mode concept in 3/3 scenarios | High - over-rewrite in Eval 1, missing reports in Eval 2/3 |
| **No diff-scope discipline** | Added unnecessary sections in Eval 1 | Medium - increases maintenance cost |
| **No structured evidence traceability** | No Evidence Map in 3/3 scenarios | Medium - PR review lacks an audit trail |
| **No Quality Scorecard** | No Scorecard in 3/3 scenarios | Medium - no systematic quality check |
| **No awareness of CI drift** | Never mentioned in 2/2 relevant scenarios | High - docs will fall behind again |
| **Non-standard codemap structure** | Eval 3 produced flat files without required fields | Medium - architecture docs become hard to maintain |
| **Directory-tree dump anti-pattern** | Full directory tree embedded in Eval 3 | Low - hurts readability |

### 6.3 Boundary Summary

The base model is already strong at **fact extraction and basic documentation writing**. It got environment variables, ports, and routes correct in all cases. But it completely lacks **methodological discipline**. The skill's value is not that it "makes the model smarter"; it gives the model a repeatable workflow: project classification -> diff scope -> output mode -> structured report -> CI maintenance guidance.

---

## 7. Overall Score

### 7.1 Dimension Scores

| Dimension | With Skill | Without Skill | Delta |
|------|-----------|--------------|------|
| Project-type routing and diff scope | 5.0/5 | 1.0/5 | +4.0 |
| Evidence-backed accuracy | 5.0/5 | 3.5/5 | +1.5 |
| Output modes and structural correctness | 5.0/5 | 1.0/5 | +4.0 |
| Anti-pattern avoidance and README UX | 5.0/5 | 3.0/5 | +2.0 |
| Token cost-effectiveness | 4.5/5 | - | - |
| CI drift and maintainability | 5.0/5 | 1.0/5 | +4.0 |
| **Overall average** | **4.92/5** | **1.75/5** | **+3.17** |

### 7.2 Weighted Total Score

| Dimension | Weight | Score | Weighted |
|------|------|------|------|
| Assertion pass rate (delta) | 25% | 10/10 | 2.50 |
| Evidence-backed accuracy | 20% | 9.0/10 | 1.80 |
| Output mode and structural correctness | 15% | 10/10 | 1.50 |
| Token cost-effectiveness | 15% | 9.0/10 | 1.35 |
| Anti-pattern avoidance and README UX | 15% | 9.0/10 | 1.35 |
| Project-type routing and diff scope | 10% | 10/10 | 1.00 |
| **Weighted total** | | | **9.50/10** |

---

## 8. Improvement Suggestions

### 8.1 [P1] Trim Low-Leverage Modules

Roughly 1,000 tokens (~48% of `SKILL.md`) produced no incremental gain in this evaluation:

| Module | Tokens | Suggestion |
|------|-------|------|
| Standard Workflow | ~300 | Compress into a 3-4 line checklist and move the detailed version to a reference file |
| Evidence Commands | ~100 | Move to `references/evidence-commands.md` and load on demand |
| Gate 1: Audience / Language | ~120 | Keep it, but shorten it (the base model already followed repo language naturally) |
| README UX Rules | ~100 | The base model already maintained a reasonable reader flow; can be compressed |

This would likely remove ~400-500 tokens without affecting the high-leverage assertion gains, improving SKILL.md efficiency from 37 tok/1% to roughly 28 tok/1%.

### 8.2 [P1] Strengthen Monorepo Codemap Guidance

The Codemap Output Contract in Eval 3 was one of the largest gaps between with-skill and without-skill. Suggested changes:

- Add a short codemap `INDEX.md` template to `references/codemap-template.md`
- State explicitly that `INDEX.md` must include: overview, child-codemap link table, and cross-module concerns
- For each project type (Service / Monorepo), specify which codemap files are required

### 8.3 [P2] Clearer Conditional Loading for Reference Files

The current 3 reference files (~540 tokens total) are still less than one quarter of `SKILL.md` when all are read together. Their loading rules can still be stated more clearly:

- **Simple patch** (Eval 1-like): `SKILL.md` only, no references needed (~2,100 tokens)
- **Full service update** (Eval 2-like): `SKILL.md` + `ci-drift.md` (~2,250 tokens)
- **Monorepo codemap** (Eval 3-like): `SKILL.md` + all references (~2,640 tokens)

### 8.4 [P2] Add More Evaluation Scenarios

Current skill features that were not covered:

| Untested feature | Suggested scenario |
|-----------|---------|
| Library / SDK routing | Update a README for an npm package |
| Chinese documentation project | Run `update-doc` on a Chinese README |
| Incremental update to an existing codemap | Diff-scoped patch to an existing codemap |
| User explicitly requests a full audit | User asks to include the Scorecard in the document |
| Multi-language repo | Mixed Python + Go repository |

### 8.5 [P3] Consider Moving the Quality Scorecard to a Reference File

The 12-item Scorecard (~250 tokens) is always loaded, but it is only used in Full Output Mode. It could be moved to `references/scorecard.md`, with `SKILL.md` keeping a short pointer such as "use the 12-item checklist in `references/scorecard.md`."

---

## 9. Evaluation Materials

| Material | Path |
|------|------|
| Evaluated skill | `/Users/john/.codex/skills/update-doc/SKILL.md` |
| Skill references | `/Users/john/.codex/skills/update-doc/references/*.md` |
| Eval 1 with-skill output | `/tmp/update-doc-eval/workspace/iteration-1/eval-1/with_skill/outputs/` |
| Eval 1 without-skill output | `/tmp/update-doc-eval/workspace/iteration-1/eval-1/without_skill/outputs/` |
| Eval 2 with-skill output | `/tmp/update-doc-eval/workspace/iteration-1/eval-2/with_skill/outputs/` |
| Eval 2 without-skill output | `/tmp/update-doc-eval/workspace/iteration-1/eval-2/without_skill/outputs/` |
| Eval 3 with-skill output | `/tmp/update-doc-eval/workspace/iteration-1/eval-3/with_skill/outputs/` |
| Eval 3 without-skill output | `/tmp/update-doc-eval/workspace/iteration-1/eval-3/without_skill/outputs/` |
| Test repositories | `/tmp/update-doc-eval/repos/{go-file-converter,go-notification-service,platform-monorepo}/` |
| Report format reference | `/Users/john/go-notes/skills/go-makefile-writer-skill-eval-report.md` |

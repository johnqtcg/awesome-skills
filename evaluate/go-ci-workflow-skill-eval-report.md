# go-ci-workflow Skill Evaluation Report

> Evaluation date: 2026-03-12
> Evaluation subject: `go-ci-workflow`
> Evaluation method: skill-creator framework (3 scenarios × 2 configs = 6 runs)

**Reference baseline**: `issue2md` project (https://github.com/johnqtcg/issue2md) real CI workflow (`.github/workflows/ci.yml`)

---

`go-ci-workflow` is a GitHub Actions CI design and refactoring skill for Go repositories. It generates honest, maintainable CI workflows that match local execution based on repo structure, Makefile entry points, and test types. Its three main strengths are: repository shape detection before deciding workflow architecture, avoiding forcing unsuitable CI templates onto repos; strong Make-driven delegation with explicit fallback when stable entry points are missing, so "how you run locally is how CI runs"; and unified conventions for tool version pinning, output contracts, and local-equivalence markers for long-term maintenance and debugging.

## 1. Evaluation Overview

This evaluation reviews the go-ci-workflow skill along two dimensions: **actual task performance** and **token cost-effectiveness**. It uses the real Makefile and CI workflow of the `issue2md` project as a reference baseline, with 3 progressive scenarios and 35 assertions.

| Dimension | With Skill | Without Skill | Delta |
|-----------|-----------|--------------|-------|
| **Assertion pass rate** | **35/35 (100%)** | 23.5/35 (67%) | **+33 pp** |
| **Make-driven delegation** | 3/3 scenarios complete | 2/3 (scenario 3 no Makefile N/A; scenario 1 baseline uses inline docker) | Skill ensures consistent delegation |
| **Output Contract** | 3/3 | 0/3 | Skill-only |
| **Local-equivalence markers** | 3/3 | 0/3 | Skill-only |
| **Tool version pinning** | 3/3 | 2/3 (scenario 3 baseline uses @latest) | Skill consistent |
| **Skill Token cost (SKILL.md)** | ~1,500 tokens | 0 | — |
| **Skill Token cost (typical load)** | ~4,500 tokens | 0 | — |
| **Token cost per 1% pass-rate gain** | **~45 (SKILL.md) / ~136 (typical)** | — | — |

---

## 2. Test Methodology

### 2.1 Scenario Design

| Scenario | Repo | Focus | Assertions |
|----------|------|-------|------------|
| Eval 1: Create CI from scratch | issue2md full repo (ci.yml removed) | Repo shape detection, Make delegation, job separation, trigger strategy, output contract | 15 |
| Eval 2: Refactor poor CI | issue2md + ci.yml with 10 anti-patterns | Anti-pattern identification and fix, Make delegation, conditional expensive jobs | 12 |
| Eval 3: No-Makefile library | Minimal Go library (no cmd/, no Makefile) | Degraded output, inline fallback markers, local-equivalence markers | 8 |

### 2.2 Reference Baseline

`issue2md` real CI workflow characteristics:
- 6 independent jobs: ci, docker-build, api-integration, e2e-web, govulncheck, fieldalignment
- Core gate delegates via `make ci COVER_MIN=80`
- E2E only on push/schedule
- Tool versions aligned with Makefile
- No concurrency (improvement opportunity)

---

## 3. Assertion Pass Rate

### 3.1 Scenario 1: Create CI from Scratch (15 items)

| ID | Assertion | With-Skill | Without-Skill |
|----|------------|:----------:|:-------------:|
| A1 | Repo shape detected as single-module service | PASS | FAIL |
| A2 | Core gate uses `make ci COVER_MIN=80` | PASS | PASS |
| A3 | Docker uses `make docker-build` | PASS | FAIL |
| A4 | Integration uses `make ci-api-integration` | PASS | PASS |
| A5 | E2E conditional (push/schedule) | PASS | PASS |
| A6 | `go-version-file: go.mod` | PASS | PASS |
| A7 | `cache: true` | PASS | PASS |
| A8 | Tool versions pinned | PASS | PASS |
| A9 | Job separation (not single job) | PASS | PASS |
| A10 | Concurrency control | PASS | PASS |
| A11 | Trigger strategy complete (push main + PR + schedule) | PASS | PASS |
| A12 | `permissions: contents: read` | PASS | PASS |
| A13 | E2E not on PR trigger | PASS | PASS |
| A14 | Output Contract complete | PASS | FAIL |
| A15 | Tool versions aligned with Makefile | PASS | PASS |
| | **Total** | **15/15 (100%)** | **12/15 (80%)** |

### 3.2 Scenario 2: Refactor Poor CI (12 items)

| ID | Assertion | With-Skill | Without-Skill |
|----|------------|:----------:|:-------------:|
| B1 | Inline `go test` → `make ci` | PASS | PASS |
| B2 | Hardcoded `go-version: '1.22'` → `go-version-file: go.mod` | PASS | PASS |
| B3 | `@latest` → pinned version | PASS | PASS |
| B4 | Single job → multi-job separation | PASS | PASS |
| B5 | Add concurrency | PASS | PASS |
| B6 | Add `permissions: contents: read` | PASS | PASS |
| B7 | E2E conditional (push/schedule) | PASS | PASS |
| B8 | Docker build job uses make target | PASS | PASS |
| B9 | `cache: true` | PASS | PASS |
| B10 | `timeout-minutes` | PASS | PASS |
| B11 | Core gate uses Make target | PASS | PASS |
| B12 | Output Contract complete | PASS | FAIL |
| | **Total** | **12/12 (100%)** | **11/12 (92%)** |

### 3.3 Scenario 3: No-Makefile Go Library (8 items)

| ID | Assertion | With-Skill | Without-Skill |
|----|------------|:----------:|:-------------:|
| C1 | Detected as library (not application) | PASS | PARTIAL |
| C2 | Uses inline fallback with explicit marker | PASS | FAIL |
| C3 | Local parity marked PARTIAL | PASS | FAIL |
| C4 | Recommends adding Makefile | PASS | FAIL |
| C5 | Tool versions pinned (not @latest) | PASS | FAIL |
| C6 | Concurrency control | PASS | FAIL |
| C7 | `go-version-file: go.mod` | PASS | FAIL |
| C8 | Output Contract complete | PASS | FAIL |
| | **Total** | **8/8 (100%)** | **0.5/8 (6%)** |

### 3.4 Overview

| Scenario | Assertions | With Skill | Without Skill | Delta |
|----------|-----------|-----------|--------------|-------|
| Eval 1: Create from scratch | 15 | **15/15 (100%)** | 12/15 (80%) | +20pp |
| Eval 2: Refactor poor CI | 12 | **12/12 (100%)** | 11/12 (92%) | +8pp |
| Eval 3: No-Makefile library | 8 | **8/8 (100%)** | 0.5/8 (6%) | +94pp |
| **Total** | **35** | **35/35 (100%)** | **23.5/35 (67%)** | **+33pp** |

### 3.5 Trend: Skill Advantage Inversely Related to Prompt Information

| Scenario | Structural info in prompt | Without-Skill pass rate | Delta |
|----------|----------------------------|-------------------------|-------|
| Eval 2 (refactor) | High — 10 issues listed | 92% | +8pp |
| Eval 1 (create) | Medium — Makefile targets listed | 80% | +20pp |
| Eval 3 (degraded) | Low — structure only | 6% | +94pp |

**Conclusion**: When the prompt contains enough structural information, the baseline approaches the skill. When prompt information is low (e.g. scenario 3), the baseline lacks the skill’s degradation handling, equivalence markers, etc. **The skill’s core value is structured knowledge completion**, especially best practices not mentioned in the prompt.

---

## 4. Comparison with Real CI

`issue2md` has a manually written, high-quality CI workflow. Comparing With-Skill output to real CI:

| Feature | Real CI | With-Skill | Without-Skill |
|---------|---------|-----------|--------------|
| Job count | 6 | 5 | 4 |
| Core gate | `make ci COVER_MIN=80` | `make ci COVER_MIN=80` ✅ | `make ci` (no COVER_MIN) |
| Docker | `make docker-build` | `make docker-build` ✅ | `docker build -f ...` (inline) |
| API integration | `make ci-api-integration` | `make ci-api-integration` ✅ | `make ci-api-integration` ✅ |
| E2E | `make ci-e2e-web` (push/schedule) | `make ci-e2e-web` (push/schedule) ✅ | `make ci-e2e-web` + redundant server startup |
| govulncheck | Separate job | Separate job ✅ | None |
| fieldalignment | Separate job | None | None |
| Concurrency | None | Yes ✅ (improves real CI) | Yes |
| Permissions | None | `permissions: {}` + job-level ✅ | `contents: read` |
| timeout-minutes | None | None (scenario 1) | None |

**Findings**:
- With-Skill output closely matches real CI in job layout and Make delegation
- With-Skill **improves** real CI (adds concurrency and permissions; real CI lacks both)
- Without-Skill uses inline Docker build instead of `make docker-build`, violating local-equivalence
- Without-Skill E2E job adds unnecessary server startup logic (curl polling, etc.), increasing complexity

---

## 5. Dimension-by-Dimension Comparison

### 5.1 Make-Driven Delegation (Core Delta)

| Dimension | With Skill | Without Skill |
|-----------|-----------|--------------|
| Scenario 1 core gate | `make ci COVER_MIN=80` | `make ci` (missing COVER_MIN) |
| Scenario 1 Docker | `make docker-build` | `docker build -f Dockerfile ...` (inline) |
| Scenario 1 E2E | `make ci-e2e-web` | `make ci-e2e-web` + redundant server startup |
| Scenario 2 core gate | `make ci COVER_MIN=80` | `make ci COVER_MIN=80` |
| Scenario 2 Docker | `make docker-build` | `make docker-build` |

The skill’s "Execution Priority" rules ensure consistent Make delegation. The baseline matched in scenario 2 (with explicit prompts) but fell back to inline Docker in scenario 1 (no prompt).

### 5.2 Output Contract (Skill-Only)

With-Skill produces structured reports in each scenario:

| Report item | Scenario 1 | Scenario 2 | Scenario 3 |
|-------------|------------|------------|------------|
| Repo shape | single-module service | single-module service | single-module library |
| Job list + execution paths | 5 jobs, all paths | 4 jobs, before/after | 2 jobs, all inline |
| Trigger strategy | PR/push/schedule | PR/push/schedule | PR/push |
| Permissions | `permissions: {}` + job-level | `contents: read` | `contents: read` |
| Tool version alignment | ✅ Matches Makefile | ✅ Matches Makefile | ✅ Pinned |
| Missing targets | install-tools, govulncheck | None | All — no Makefile |
| Verification | YAML + make dry-run | YAML + make verify | YAML syntax |
| Follow-up suggestions | 3 items | 3 items | 4 items |

Without-Skill has no such structured output.

### 5.3 Degradation Handling (Scenario 3 Key Delta)

| Dimension | With-Skill | Without-Skill |
|-----------|-----------|--------------|
| Inline marker | Each step marked `(inline fallback)` | No marker; uses inline directly |
| Local parity marker | File header + Output Contract both PARTIAL | Not mentioned |
| Follow-up recommendation | "Add Makefile with go-makefile-writer skill" | None |
| Tool versions | golangci-lint v1.62.2 pinned | `version: latest` ❌ |
| Go version | `go-version-file: go.mod` | Hardcoded `"1.23"` + matrix `["1.23","1.24"]` |
| Concurrency | Yes | No |
| Format check | `gofmt -l .` + error annotation | No |
| Coverage check | Yes (with threshold) | `go tool cover -func` print only (no threshold) |

Scenario 3 exposes the baseline’s main weakness **without structured guidance**:
- Uses `@latest` (non-deterministic builds)
- Hardcoded Go version
- No concurrency
- No degradation awareness (does not mark missing Makefile)

### 5.4 Security and Permissions

| Dimension | With-Skill | Without-Skill |
|-----------|-----------|--------------|
| Scenario 1 permissions | `permissions: {}` workflow + job-level `contents: read` | `contents: read` workflow-level |
| Scenario 2 permissions | `contents: read` | `contents: read` |
| Scenario 3 permissions | `contents: read` | `contents: read` |
| Fork PR safety | Explicit analysis of no secret exposure | Not mentioned |

Both set `permissions`, but With-Skill uses stricter deny-all default (`permissions: {}`) + job-level escalation in scenario 1, and explicitly analyzes Fork PR safety in the Output Contract.

---

## 6. Token Cost-Effectiveness Analysis

### 6.1 Skill Size

| File | Lines | Est. tokens | Load timing |
|------|-------|-------------|-------------|
| **SKILL.md** | 236 | ~1,500 | Always |
| references/workflow-quality-guide.md | 445 | ~3,000 | Standard scenarios |
| references/golden-examples.md | 385 | ~2,600 | When YAML templates needed |
| references/repository-shapes.md | 199 | ~1,300 | Monorepo/complex scenarios |
| references/github-actions-advanced-patterns.md | 307 | ~2,000 | Security/advanced features |
| references/fallback-and-scaffolding.md | 49 | ~300 | No Makefile |
| references/pr-checklist.md | 66 | ~400 | PR review |
| scripts/discover_ci_needs.sh | 77 | ~500 | Repo detection |
| **All references** | 1,528 | **~10,100** | — |

### 6.2 Typical Load Scenarios

| Scenario | Files read | Total tokens |
|----------|------------|--------------|
| Standard service repo (Eval 1) | SKILL.md + quality-guide + golden-examples | ~7,100 |
| Refactor workflow (Eval 2) | SKILL.md + quality-guide | ~4,500 |
| No-Makefile degraded (Eval 3) | SKILL.md + fallback | ~1,800 |
| SKILL.md only (min load) | SKILL.md | ~1,500 |
| Full load | All | ~11,600 |

### 6.3 Cost-Effectiveness Calculation

| Metric | Value |
|--------|-------|
| With-skill pass rate | 100% (35/35) |
| Without-skill pass rate | 67% (23.5/35) |
| Pass-rate gain | +33 pp |
| **Token cost per 1% gain (SKILL.md only)** | **~45 tok** |
| **Token cost per 1% gain (typical ~4,500)** | **~136 tok** |
| **Token cost per 1% gain (full ~11,600)** | **~352 tok** |

### 6.4 Cost-Effectiveness vs Other Skills

| Skill | SKILL.md tokens | Pass-rate delta | Tokens/1% (SKILL.md) | Tokens/1% (typical) |
|-------|-----------------|-----------------|----------------------|---------------------|
| `create-pr` | ~2,500 | +71pp | ~35 | ~48 |
| `git-commit` | ~1,150 | +22pp | ~51 | ~51 |
| `go-makefile-writer` | ~1,960 | +31pp | ~63 | ~149 |
| **`go-ci-workflow`** | **~1,500** | **+33pp** | **~45** | **~136** |

`go-ci-workflow` has the **best SKILL.md cost-effectiveness** (~45 tok/1%) but **large reference set** (~10,100 tokens), so typical-load cost-effectiveness is worse (~136 tok/1%). Similar to `go-makefile-writer`.

### 6.5 Token Segment Cost-Effectiveness

| Module | Token est. | Linked delta | Cost-effectiveness |
|--------|------------|--------------|---------------------|
| **Execution Priority (Make delegation)** | ~80 | 2 (scenario 1 docker, COVER_MIN) | **Very high** |
| **Output Contract definition** | ~150 | 3 (3-scenario structured report) | **Very high** |
| **Mandatory Gates (incl. Local Parity)** | ~300 | 3 (scenario 3 parity + fallback) | **High** |
| **Job Architecture Rules** | ~100 | Indirect (job separation consistency) | **High** |
| **Degraded Output Gate** | ~80 | 3 (scenario 3 all degraded behavior) | **Very high** |
| **Go Setup/Tooling Rules** | ~80 | 1 (scenario 3 go-version-file) | **High** |
| **Trigger Rules** | ~60 | Indirect (E2E conditional) | **Medium** |
| **workflow-quality-guide.md** | ~3,000 | Indirect (job design quality) | **Medium** — largest single file |
| **golden-examples.md** | ~2,600 | Indirect (YAML structure templates) | **Medium** |
| **repository-shapes.md** | ~1,300 | 0 direct (monorepo not tested) | **Low** — untested |
| **advanced-patterns.md** | ~2,000 | 0 direct (security not tested) | **Low** — untested |

**High-leverage instructions** (~610 tokens SKILL.md → 11.5 assertion delta) are ~41% of SKILL.md and drive all direct deltas.

---

## 7. Overall Score

### 7.1 Dimension Scores

| Dimension | With Skill | Without Skill | Delta |
|-----------|-----------|--------------|-------|
| Make-driven delegation consistency | 5.0/5 | 3.5/5 | +1.5 |
| Job architecture and trigger strategy | 5.0/5 | 4.0/5 | +1.0 |
| Tool version pinning and alignment | 5.0/5 | 3.5/5 | +1.5 |
| Degradation handling and equivalence markers | 5.0/5 | 0.5/5 | +4.5 |
| Structured report (Output Contract) | 5.0/5 | 1.0/5 | +4.0 |
| Security and permissions | 4.5/5 | 3.5/5 | +1.0 |
| **Overall mean** | **4.92/5** | **2.67/5** | **+2.25** |

### 7.2 Weighted Total Score

| Dimension | Weight | Score | Rationale | Weighted |
|-----------|--------|-------|-----------|----------|
| Assertion pass-rate delta | 25% | 9.0/10 | +33pp; scenario 2 high baseline lowers overall delta | 2.25 |
| Make-driven delegation consistency | 20% | 9.5/10 | 3/3 scenarios full Make delegation; scenario 1 COVER_MIN aligned | 1.90 |
| Degradation handling (Local Parity + Fallback markers) | 15% | 10.0/10 | Scenario 3 perfect: inline markers + parity PARTIAL + Makefile recommendation | 1.50 |
| Structured report (Output Contract) | 15% | 10.0/10 | 3/3 scenarios full contract | 1.50 |
| Token cost-effectiveness | 15% | 5.5/10 | SKILL.md efficient (~45); references large (~10,100 tok full) | 0.83 |
| Security and permissions | 10% | 8.5/10 | Deny-all default + job-level escalation; fork PR analysis | 0.85 |
| **Weighted total** | **100%** | | | **8.83/10** |

### 7.3 Comparison with Other Skills

| Skill | Weighted total | Pass-rate delta | Tokens/1% (typical) | Strongest dimension |
|-------|----------------|-----------------|---------------------|----------------------|
| create-pr | 9.55/10 | +71pp | ~48 | Gate flow (+3.5), Output Contract (+4.0) |
| go-makefile-writer | 9.16/10 | +31pp | ~149 | CI reproducibility (+3.0), Output Contract (+4.0) |
| **go-ci-workflow** | **8.83/10** | +33pp | ~136 | Degradation handling (+4.5), Output Contract (+4.0) |

`go-ci-workflow` scores slightly lower, mainly due to **token cost-effectiveness** (5.5/10). Reference set ~10,100 tokens is the largest among evaluated skills; typical load ~4,500 tokens also has high cost per 1% (~136 tok/1%).

**Score breakdown**:
- **Token cost-effectiveness (5.5/10)**: References too large. `workflow-quality-guide.md` (445 lines) and `golden-examples.md` (385 lines) total ~5,600 tokens but only indirect contribution in eval
- **Assertion delta (9.0/10)**: Scenario 2 delta only +8pp (baseline 92%), lowering overall delta

**Highlights**:
- **Degradation handling (10.0/10)**: Scenario 3 +94pp delta is the **largest single-scenario delta** among evaluated skills, proving Degraded Output Gate value
- **SKILL.md cost-effectiveness**: ~45 tok/1% is best among skills; core rules are compact and efficient

---

## 8. Conclusion

The `go-ci-workflow` skill adds clear value in three areas:

1. **Degradation handling (+94pp single-scenario delta)**: The **largest single-scenario delta** among evaluated skills, proving the value of Degraded Output Gate and Local Parity markers. The baseline has no degradation awareness without a Makefile.

2. **Make-driven delegation consistency**: Ensures all jobs run via Makefile targets, matching local development. The baseline falls back to inline commands without explicit prompts (e.g. Docker build in scenario 1).

3. **Output Contract**: Structured reports make CI workflow changes auditable and traceable, including repo shape, execution path classification, missing targets, etc.

**Main risk**: Reference set ~10,100 tokens is the largest among evaluated skills; typical load ~4,500 tokens. Trimming `workflow-quality-guide.md` and `golden-examples.md` could reduce token cost ~24% and improve tokens/1% from ~136 to ~103.

**Comparison with real CI validates the skill**: With-Skill output not only matches the quality of `issue2md`’s manually written CI but **improves** it on concurrency and permissions.

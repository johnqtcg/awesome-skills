# git-commit Skill Evaluation Report

> Evaluation framework: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> Evaluation date: 2026-03-11
> Evaluation subject: `git-commit`

---

`git-commit` is a Git commit skill that emphasizes safety and convention, used to perform pre-commit checks, precise staging, secret scanning, quality gates, and Conventional Commit message generation in real repositories. Its three main strengths are: preflight checks covering working tree, conflicts, branch state, and in-progress Git operations with strong process discipline; built-in secret detection and quality gates that block high-risk content and obvious defects before commit; and clear constraints on subject length, atomic commits, and hook feedback, making commits more consistent and team-friendly.

## 1. Evaluation Overview

This evaluation reviews the git-commit skill along two dimensions: **actual task performance** and **token cost-effectiveness**. It uses 3 Git commit scenarios of increasing difficulty, each run with both with-skill and without-skill configurations—3 scenarios × 2 configs = 6 independent subagent runs—scored against 22 assertions.

| Dimension | With Skill | Without Skill | Delta |
|-----------|-----------|--------------|-------|
| **Assertion pass rate** | **22/22 (100%)** | 17/22 (77.3%) | **+22.7 pp** |
| **Preflight safety checks** | 3/3 complete (all 6 items) | 0/3 (only git status/diff) | **Decisive delta** |
| **Subject length compliance (≤50 chars)** | 3/3 | 1/3 | Skill consistent |
| **Quality gate (go test)** | 1/1 executed | 0/1 | Skill-only |
| **Secret detection** | 1/1 passed | 1/1 passed | No delta |
| **Skill Token cost** | ~1,150 tokens/run | 0 | — |
| **Token cost per 1% pass-rate gain** | ~51 tokens | — | — |

---

## 2. Test Methodology

### 2.1 Scenario Design

Three scenarios covering different Git commit risk areas:

| Scenario | Repo | Focus | Assertions |
|----------|------|-------|------------|
| Eval 1: simple-feature | Go CLI app (new greet function) | Basic commit flow, format, preflight | 7 |
| Eval 2: secret-trap | Go web service + `.env` trap | Secret detection, reject dangerous files, selective staging | 7 |
| Eval 3: multi-file-tests | Go calculator (new function + tests) | Multi-file staging, quality gate, subject refinement | 8 |

### 2.2 Execution

- Each scenario uses an independent Git repo (`/tmp/eval-repo-{1,2,3}`) with initial commit and unstaged changes
- With-skill runs load `/Users/john/.codex/skills/git-commit/SKILL.md` first and follow its workflow
- Without-skill runs load no skill; model uses default behavior for commit task
- All runs execute in parallel in independent subagents

---

## 3. Assertion Pass Rate

### 3.1 Overview

| Scenario | Assertions | With Skill | Without Skill | Delta |
|----------|-----------|-----------|--------------|-------|
| Eval 1: simple-feature | 7 | **7/7 (100%)** | 6/7 (85.7%) | +14.3% |
| Eval 2: secret-trap | 7 | **7/7 (100%)** | 6/7 (85.7%) | +14.3% |
| Eval 3: multi-file-tests | 8 | **8/8 (100%)** | 5/8 (62.5%) | +37.5% |
| **Total** | **22** | **22/22 (100%)** | **17/22 (77.3%)** | **+22.7%** |

### 3.2 Classification of 5 Without-Skill Failed Assertions

| Failure type | Scenario | Failed assertion | Root cause |
|--------------|----------|------------------|------------|
| **Missing preflight checks** | Eval 1 | "Preflight checks were performed" | Only ran git status/diff; did not check conflicts, branch state, rebase/merge in progress |
| **Subject too long** | Eval 2 | "Subject line <= 50 chars" | Subject 74 chars: `add timeouts, health endpoint, and explicit mux routing` |
| **Subject too long** | Eval 3 | "Subject line <= 50 chars" | Subject 56 chars: `add multiply and divide functions with tests` |
| **Missing preflight checks** | Eval 3 | "Preflight checks performed" | Same as Eval 1 |
| **Missing quality gate** | Eval 3 | "Quality gate run (go test)" | Did not run go vet or go test |

**Observation**: All 5 without-skill failures fall into 3 systemic gaps: preflight checks (2×), subject length (2×), quality gate (1×). These are **process discipline** gaps, not capability gaps.

---

## 4. Dimension-by-Dimension Comparison

### 4.1 Preflight Safety Checks

**Strongest differentiator.** The skill defines 6 preflight checks, all executed on every run:

| Check | Command | With Skill | Without Skill |
|-------|---------|-----------|--------------|
| Working tree validation | `git rev-parse --is-inside-work-tree` | ✅ Every run | ❌ Never |
| Status check | `git status --short` | ✅ Every run | ✅ Every run |
| Conflict detection | `git diff --name-only --diff-filter=U` | ✅ Every run | ❌ Never |
| Branch check | `git rev-parse --abbrev-ref HEAD` | ✅ Every run | ❌ Never |
| Rebase in progress | `test -d .git/rebase-merge` | ✅ Every run | ❌ Never |
| Merge/Cherry-pick in progress | `test -f .git/MERGE_HEAD` | ✅ Every run | ❌ Never |

**Practical value**: Without-skill only ran `git status` and skipped conflict detection, detached HEAD check, and rebase/merge-in-progress checks. In this eval’s clean repos, all checks passed and the gap did not affect the final commit. In real production (rebase conflicts, detached HEAD, cherry-pick in progress), these checks are critical safeguards.

**Conclusion**: Preflight value is invisible in normal cases but can be decisive in abnormal ones. The skill provides **zero-cost safety net**.

### 4.2 Commit Message Quality

#### Subject Length Control

| Scenario | With Skill | Without Skill |
|----------|-----------|--------------|
| Eval 1 | `feat: add greet function with CLI argument support` (37 chars) ✅ | `feat: add greet function with CLI argument support` (37 chars) ✅ |
| Eval 2 | `refactor(server): add timeouts and health check` (48 chars) ✅ | `refactor(server): add timeouts, health endpoint, and explicit mux routing` (74 chars) ❌ |
| Eval 3 | `feat(calc): add multiply and divide operations` (47 chars) ✅ | `feat(calc): add multiply and divide functions with tests` (56 chars) ❌ |

**Analysis**: With-skill kept all 3 subjects under 50 chars (37, 48, 47). Without-skill tended to pack details into the subject when changes were more complex (Eval 2/3), causing overruns.

The skill’s key rule:

> imperative mood, **<= 50 chars total**, no trailing period

This concise rule drove the difference in two scenarios. Without-skill knows Conventional Commits but **does not naturally enforce subject length**.

#### Type and Scope

| Dimension | With Skill | Without Skill | Delta |
|-----------|-----------|--------------|-------|
| feat type | 2/2 ✅ | 2/2 ✅ | None |
| refactor type | 1/1 ✅ | 1/1 ✅ | None |
| Scope usage | `(server)`, `(calc)` | `(server)`, `(calc)` | None |
| Body explains "why" | 3/3 | 3/3 | None |

**Conclusion**: No difference in commit type or scope. Claude’s base model is accurate enough. The skill’s value is concentrated in **subject length discipline**.

#### Commit Message Quality Detail

**Eval 2 — largest difference:**

With Skill:
```
refactor(server): add timeouts and health check

Replace default serve mux and bare ListenAndServe with an explicit
http.Server configured with read/write timeouts to prevent slow-
client resource exhaustion. Add /health endpoint for liveness probes
and default the root handler greeting to "World" when path is empty.
```

Without Skill:
```
refactor(server): add timeouts, health endpoint, and explicit mux routing

Replace the default ServeMux with an explicit mux, add read/write
timeouts to the server, introduce a /health endpoint, and default
the greeting name to "World" when the path is empty.
```

Body quality is similar; both explain "why." With-skill subject (48 chars) is concise; without-skill subject (74 chars) tries to list all changes in one line, violating the 50-char limit.

**Eval 3 — refinement comparison:**

| Version | Subject | Chars |
|---------|---------|-------|
| With Skill | `add multiply and divide operations` | 47 |
| Without Skill | `add multiply and divide functions with tests` | 56 |

With-skill refines "functions with tests" to "operations" and puts test info in the body. Without-skill tries to mention both feature and tests in the subject, causing overflow.

### 4.3 Secret Detection

| Dimension | With Skill | Without Skill |
|-----------|-----------|--------------|
| Detected .env | ✅ | ✅ |
| Rejected .env commit | ✅ | ✅ |
| Warned user | ✅ | ✅ |
| Formal scan pipeline | ✅ (rg regex) | ❌ (manual judgment) |

**Detail**:
- **With Skill**: Two-phase scan per SKILL.md—filename risk via `git diff --cached --name-only | rg`, then content patterns (AWS Key, SSH Key, GitHub Token, etc.) via `git diff --cached | rg`
- **Without Skill**: Read `.env` content directly, recognized `DB_PASSWORD` and `API_KEY` from general security knowledge, rejected commit

**Conclusion**: For this eval’s **obvious secret** case (.env filename + plain password), both behaved the same. Claude’s base model can detect obvious secret files.

**Skill’s formal scan pipeline may add value in** (not tested here):
- Embedded API keys in code (e.g. `const apiKey = "ghp_xxxx"`)
- Keys in non-standard filenames (e.g. `config.production.yaml` with password)
- Base64-encoded keys in file content

This is **potential** value, not validated.

### 4.4 Quality Gate (go test / go vet)

| Dimension | With Skill | Without Skill |
|-----------|-----------|--------------|
| Eval 1 (no tests) | Attempted; env issue failed | ❌ Not run |
| Eval 2 (no tests) | Attempted; env issue failed | ❌ Not run |
| Eval 3 (has tests) | ✅ go vet PASS + go test PASS | ❌ Not run |

**Key difference**: The skill requires Go repos to run `go vet ./...` and `go test ./...` by default. Without-skill **never ran the quality gate**, even when tests existed (Eval 3).

In Eval 3, with-skill ran `go test ./...` and confirmed all 5 tests passed before commit; without-skill committed without verification.

**Practical value**: The quality gate is the last line of defense against committing broken tests. The skill’s related instructions are ~5 lines but contributed 12.5% (1/8) of the pass-rate delta in Eval 3—the **highest token cost-effectiveness for a single rule**.

### 4.5 Staging Strategy

| Dimension | With Skill | Without Skill |
|-----------|-----------|--------------|
| Selective staging | 3/3 ✅ | 3/3 ✅ |
| Avoid `git add .` | 3/3 ✅ | 3/3 ✅ |
| Post-staging verification | 3/3 (git status + git diff --cached) | 0/3 |

Both used selective staging (`git add <files>`), not blind `git add .`. With-skill additionally ran `git status --short` and `git diff --cached` after staging; without-skill skipped verification.

**Conclusion**: Staging strategy is not a differentiator. Claude’s base model already uses selective staging by default.

### 4.6 Post-Commit Report

| Dimension | With Skill | Without Skill |
|-----------|-----------|--------------|
| Report commit hash | ✅ | ✅ |
| Report changed files | ✅ | ✅ |
| Report quality gate status | ✅ | ❌ |
| Structured report format | ✅ (table + sections) | ✅ (concise list) |

With-skill post-commit reports are more structured with full check status table, quality gate results, and file change stats. Without-skill produced concise but complete summaries.

---

## 5. Skill Differentiator Map

| Dimension | Contribution | Notes |
|-----------|--------------|-------|
| **Preflight safety checks** | ★★★★★ | 6 systematic checks vs none; critical in abnormal cases |
| **Subject length discipline** | ★★★★☆ | 50-char limit drove difference in 2/3 scenarios; direct impact on commit compliance |
| **Quality gate automation** | ★★★★☆ | go test/vet auto-run in Go repos; without-skill never runs it |
| **Secret scan pipeline** | ★★☆☆☆ | Formal rg scan adds depth; no delta in obvious-secret case |
| **Staging strategy** | ★☆☆☆☆ | Both use selective staging; no delta |
| **Commit type/Scope** | ★☆☆☆☆ | Both correct; no delta |

---

## 6. Token Cost-Effectiveness Analysis

### 6.1 Skill Size

| Metric | Value |
|--------|-------|
| File size | 5,885 bytes |
| Word count | 862 words |
| Line count | 131 lines |
| Est. token cost | ~1,150 tokens/run (loaded into context) |
| Description tokens | ~30 words (~40 tokens, always in available_skills) |

### 6.2 Token Cost for Quality Gain

| Metric | Value |
|--------|-------|
| With-skill pass rate | 100% (22/22) |
| Without-skill pass rate | 77.3% (17/22) |
| Pass-rate gain | +22.7 pp |
| Skill token cost | ~1,150 tokens |
| **Token cost per 1% gain** | **~51 tokens** |
| **Token cost per assertion fixed** | **~230 tokens** |

### 6.3 Token Segment Cost-Effectiveness

| Module | Est. tokens | Linked assertion delta | Cost-effectiveness |
|--------|-------------|------------------------|---------------------|
| Preflight checks (6 commands + flow) | ~200 | 2 assertions (Eval 1/3) | **High** — 100 tokens/assertion |
| Subject length rule (`<= 50 chars`) | ~30 | 2 assertions (Eval 2/3) | **Very high** — 15 tokens/assertion |
| Quality gate (go vet/test) | ~80 | 1 assertion (Eval 3) | **High** — 80 tokens/assertion |
| Secret scan pipeline (rg regex + flow) | ~200 | 0 assertion delta | **Low** — no incremental value in eval |
| Staging strategy | ~100 | 0 assertion delta | **Low** — base model already has it |
| Commit message format | ~250 | 0 assertion delta | **Low** — base model already has it |
| Hook awareness / amend rules | ~150 | 0 assertion delta | **Untested** — needs hook environment |
| Post-commit report format | ~80 | 0 assertion delta | **Low** — report format only |
| Message Quality Guidelines + examples | ~60 | Indirect for subject refinement | **Medium** — supports subject control |

### 6.4 High-Leverage vs Low-Leverage Instructions

**High leverage (~310 tokens → 5 assertion delta):**
- `<= 50 chars total` (30 tokens → 2 delta)
- Preflight 6 commands (200 tokens → 2 delta)
- `go vet ./... && go test ./...` (80 tokens → 1 delta)

**Low leverage (~600 tokens → 0 assertion delta):**
- Secret scan regex details (200 tokens) — base model detects obvious secrets
- Staging strategy (100 tokens) — base model uses selective staging by default
- Commit message format (250 tokens) — base model knows Conventional Commits
- Post-commit report format (80 tokens) — format only

**Untested (~240 tokens):**
- Hook awareness / amend rules (150 tokens) — needs pre-commit hook environment
- Failure handling flow (90 tokens) — needs failure scenario

### 6.5 Token Efficiency Rating

| Rating | Conclusion |
|--------|------------|
| **Overall ROI** | **Excellent** — ~1,150 tokens for +22.7% pass rate; very cost-effective for high-frequency commits |
| **Effective token share** | ~27% (310/1,150 tokens directly contribute all 5 assertion delta) |
| **Redundant token share** | ~52% (600/1,150 tokens no incremental contribution in eval) |
| **Unvalidated token share** | ~21% (240/1,150 tokens need special environment) |

---

## 7. Boundary Analysis vs Claude Base Model

This eval reveals:

### 7.1 Base Model Capabilities (No Skill Increment)

| Capability | Evidence |
|------------|----------|
| Conventional Commits format | 3/3 scenarios correct format |
| Correct commit type | feat/refactor 100% accurate |
| Reasonable scope | server/calc choices reasonable |
| Selective staging | Never used `git add .` |
| Obvious secret detection | .env correctly rejected |
| Commit body explains "why" | 3/3 scenarios have body |

### 7.2 Base Model Gaps (Skill Fills)

| Gap | Evidence | Risk level |
|-----|----------|------------|
| **Subject length control** | 2/3 scenarios overlong (56, 74 chars) | Medium — affects commit compliance |
| **Systematic preflight checks** | Never checks conflicts/rebase/merge state | High — can be catastrophic in abnormal cases |
| **Quality gate automation** | Never runs go test/vet | High — may commit broken tests |
| **Post-staging verification** | Never verifies staged content | Low — selective staging already sufficient |

---

## 8. Overall Score

### 8.1 Dimension Scores

| Dimension | With Skill | Without Skill | Delta |
|-----------|-----------|--------------|-------|
| Commit format compliance | 5.0/5 | 3.5/5 | +1.5 |
| Safety check completeness | 5.0/5 | 1.5/5 | +3.5 |
| Quality gate execution | 4.0/5 | 1.0/5 | +3.0 |
| Secret detection | 5.0/5 | 4.5/5 | +0.5 |
| Staging strategy | 5.0/5 | 4.5/5 | +0.5 |
| Maintainability/report | 4.5/5 | 3.5/5 | +1.0 |
| **Overall mean** | **4.75/5** | **3.08/5** | **+1.67** |

### 8.2 Weighted Total Score

| Dimension | Weight | Score | Weighted |
|-----------|--------|------|----------|
| Assertion pass rate (delta) | 30% | 9.1/10 | 2.73 |
| Preflight safety checks | 20% | 10/10 | 2.00 |
| Subject length discipline | 15% | 10/10 | 1.50 |
| Quality gate execution | 15% | 8.0/10 | 1.20 |
| Token cost-effectiveness | 10% | 7.0/10 | 0.70 |
| Secret detection increment | 10% | 5.0/10 | 0.50 |
| **Weighted total** | | | **8.63/10** |

---

## 9. Evaluation Materials

| Material | Path |
|----------|------|
| Eval definition | `/tmp/git-commit-eval/evals/evals.json` |
| Eval 1 with-skill output | `/tmp/git-commit-eval/workspace/iteration-1/eval-1-simple-feature/with_skill/outputs/` |
| Eval 1 without-skill output | `/tmp/git-commit-eval/workspace/iteration-1/eval-1-simple-feature/without_skill/outputs/` |
| Eval 2 with-skill output | `/tmp/git-commit-eval/workspace/iteration-1/eval-2-secret-trap/with_skill/outputs/` |
| Eval 2 without-skill output | `/tmp/git-commit-eval/workspace/iteration-1/eval-2-secret-trap/without_skill/outputs/` |
| Eval 3 with-skill output | `/tmp/git-commit-eval/workspace/iteration-1/eval-3-multi-file-tests/with_skill/outputs/` |
| Eval 3 without-skill output | `/tmp/git-commit-eval/workspace/iteration-1/eval-3-multi-file-tests/without_skill/outputs/` |
| Grading results | `/tmp/git-commit-eval/workspace/iteration-1/eval-*/with_skill/grading.json` |
| Benchmark summary | `/tmp/git-commit-eval/workspace/iteration-1/benchmark.json` |
| Eval viewer | `/tmp/git-commit-eval/eval-review.html` |

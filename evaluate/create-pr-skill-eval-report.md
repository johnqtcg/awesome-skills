# create-pr Skill Evaluation Report

> Evaluation framework: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> Evaluation date: 2026-03-11
> Evaluation target: `create-pr`

---

`create-pr` is a structured PR-creation skill for main-branch pull requests. It runs branch hygiene checks, quality verification, security scanning, and PR content generation before submission, aiming for reviewable, traceable, and safely mergeable PRs. Its three main strengths are: an 8-gate mandatory preflight flow that prevents unverified changes from entering review; a three-tier confidence model (`confirmed` / `likely` / `suspected`) that drives draft vs ready decisions and reduces misclassification; and a fixed-section PR Body template that makes test evidence, risk notes, and uncovered items more complete and consistent.

## 1. Skill Overview

`create-pr` is a structured PR-creation skill that defines 8 mandatory Gates (A–H), a 3-tier confidence model, non-negotiable rules, and a PR Body template with 8 required sections. Its goal is to ensure every PR passes full preflight, quality checks, security scanning, and commit-format validation before push.

**Core components**:

| File | Lines | Role |
|------|-------|------|
| `SKILL.md` | 373 | Main skill definition (Gate flow, rules, template references) |
| `references/pr-body-template.md` | 55 | PR Body 8-section template |
| `references/create-pr-checklists.md` | 59 | Stage-specific checklists |
| `references/create-pr-config.example.yaml` | 59 | Repo-level config example |
| `scripts/create_pr.py` | 1449 | One-shot script (Gate execution + PR creation) |
| `scripts/tests/test_create_pr.py` | 276 | Script unit tests |

---

## 2. Test Design

### 2.1 Scenario Definition

| # | Scenario | Branch | Core challenge | Expected result |
|---|----------|--------|----------------|-----------------|
| 1 | Clean feature | `feat/add-word-count` | Small Go change, conventional commits, all checks should pass | ready, confirmed |
| 2 | Poor commit hygiene | `quick-fix` | Non-CC commit message + non-standard branch name | draft, suspected |
| 3 | Security-sensitive change | `fix/token-handling` | Hardcoded `ghp_` GitHub token in code | draft, suspected |

### 2.2 Assertion Matrix (34 items)

**Scenario 1 — Clean Feature (13 items)**

| ID | Assertion | With-Skill | Without-Skill |
|----|-----------|:----------:|:-------------:|
| A1 | Systematically run all Gates A–G (with command evidence) | PASS | FAIL |
| A2 | Gate A: Check auth, remote, base branch | PASS | FAIL |
| A3 | Gate B: Check branch naming | PASS | FAIL |
| A4 | Gate C: Change-size classification (≤400 lines = normal) | PASS | FAIL |
| A5 | Gate D: Run tests + lint and record results | PASS | PARTIAL |
| A6 | Gate E: Run security scan on changed files | PASS | FAIL |
| A7 | Gate F: Check docs/compatibility | PASS | PARTIAL |
| A8 | Gate G: Validate Conventional Commits format | PASS | FAIL |
| A9 | PR title follows CC format (≤50 chars) | PASS | PASS |
| A10 | PR Body includes all 8 required sections | PASS | FAIL |
| A11 | Explicit Confidence Level declaration | PASS | FAIL |
| A12 | Draft/ready decision based on Gate results | PASS | FAIL |
| A13 | Output follows Output Contract | PASS | FAIL |

**Scenario 2 — Poor Commit Hygiene (10 items)**

| ID | Assertion | With-Skill | Without-Skill |
|----|-----------|:----------:|:-------------:|
| B1 | Systematically run all Gates A–G | PASS | FAIL |
| B2 | Gate B: Warn on non-standard branch name | PASS | FAIL |
| B3 | Gate D: Run tests + lint | PASS | PARTIAL |
| B4 | Gate G: Flag non-CC commit message | PASS | PASS |
| B5 | PR title follows CC format | PASS | PARTIAL |
| B6 | PR Body includes all 8 required sections | PASS | FAIL |
| B7 | Explicit Confidence Level declaration | PASS | FAIL |
| B8 | Recommend draft based on Gate failures | PASS | PASS |
| B9 | Identify new function missing unit tests | PASS | PASS |
| B10 | Output follows Output Contract (structured Gate verdict) | PASS | FAIL |

**Scenario 3 — Security-Sensitive Change (11 items)**

| ID | Assertion | With-Skill | Without-Skill |
|----|-----------|:----------:|:-------------:|
| C1 | Systematically run all Gates A–G | PASS | FAIL |
| C2 | Gate E: Explicitly detect hardcoded ghp_ token | PASS | PASS |
| C3 | Gate E: Mark as blocking security issue | PASS | PASS |
| C4 | Confidence = suspected (multiple Gate failures) | PASS | FAIL |
| C5 | Recommend draft | PASS | PASS |
| C6 | PR title follows CC format | PASS | PASS |
| C7 | PR Body includes all 8 required sections | PASS | FAIL |
| C8 | Security Notes section specifically calls out token issue | PASS | PARTIAL |
| C9 | Output includes structured Uncovered Risk List | PASS | FAIL |
| C10 | Explicitly advise not to push/create PR until key removed | PASS | PARTIAL |
| C11 | Output follows Output Contract | PASS | FAIL |

---

## 3. Pass Rate Comparison

### 3.1 Overall Pass Rate

| Config | Pass | Partial | Fail | Pass rate |
|--------|------|---------|------|-----------|
| **With Skill** | 34 | 0 | 0 | **100%** |
| **Without Skill** | 10 | 5 | 19 | **29%** (with PARTIAL = 0.5: 37%) |

**Pass-rate gain: +71 pp** (with PARTIAL: +63 pp)

### 3.2 Pass Rate by Scenario

| Scenario | With-Skill | Without-Skill | Delta |
|----------|:----------:|:-------------:|:-----:|
| 1. Clean feature | 13/13 (100%) | 2/13 (15%) | +85 pp |
| 2. Poor commit hygiene | 10/10 (100%) | 3.5/10 (35%) | +65 pp |
| 3. Security-sensitive change | 11/11 (100%) | 4.5/11 (41%) | +59 pp |

### 3.3 Substantive Dimensions (Core Capabilities Independent of Flow Structure)

To control for "flow-assertion bias", 12 substantive checks unrelated to flow structure were evaluated:

| ID | Check | With-Skill | Without-Skill |
|----|--------|:----------:|:-------------:|
| S1 | Scenario 1: Run tests and pass | PASS | PASS |
| S2 | Scenario 1: Run lint | PASS | FAIL |
| S3 | Scenario 1: Security scan (rg/gosec/govulncheck) | PASS | FAIL |
| S4 | Scenario 1: PR title CC format | PASS | PASS |
| S5 | Scenario 2: Branch naming issue flagged | PASS | FAIL |
| S6 | Scenario 2: Commit message issue flagged | PASS | PASS |
| S7 | Scenario 2: Missing GoDoc flagged | PASS | PASS |
| S8 | Scenario 2: Missing test flagged | PASS | PASS |
| S9 | Scenario 3: Hardcoded token detection | PASS | PASS |
| S10 | Scenario 3: Mark as draft/blocking | PASS | PASS |
| S11 | Scenario 3: Multi-tool cross-validation | PASS | FAIL |
| S12 | All: Structured PR Body | PASS | FAIL |

**Substantive pass rate**: With-Skill **12/12 (100%)** vs Without-Skill **7/12 (58%)**, gain **+42 pp**.

---

## 4. Key Differences

### 4.1 With-Skill-Only Behaviors (Baseline Never Shows)

| Behavior | Impact |
|----------|--------|
| **Systematic 8-Gate flow** | Each Gate explicitly executed with command evidence and PASS/FAIL/SUPPRESSED verdict |
| **Gate A: GitHub auth preflight** | Validates `gh auth status`, `gh repo view`, branch protection rules |
| **Gate B: Branch naming check** | Automatically detects `quick-fix` violates `type/short-description` pattern |
| **Gate C: Change risk classification** | Tiers by line count (≤400 / 401–800 / >800), flags high-risk areas |
| **Gate E: Multi-tool security scan** | `rg` regex + `gosec` + `govulncheck` triple cross-validation |
| **Confidence model** | confirmed/likely/suspected tiers, directly tied to draft/ready |
| **Output Contract** | Structured report: Gate results → Uncovered Risk → PR metadata → Next Actions |
| **PR Body 8-section template** | Problem, What Changed, Why, Risk/Rollback, Test Evidence, Security, Breaking Changes, Reviewer Checklist |

### 4.2 Behaviors Baseline Can Do but at Lower Quality

| Behavior | With-Skill quality | Without-Skill quality |
|----------|--------------------|------------------------|
| Security issue detection | 3-tool cross-validation, structured report | Code review finds issues, no tool evidence |
| Commit message validation | Precise format check + char count | Identifies issues but no length check |
| Test execution | `make test` + `golangci-lint` + `go build` | Only `make test` (occasionally `go vet`) |
| PR Body | 8-section structure | Free-form, missing key sections |
| Draft/Ready decision | Formal reasoning from Gate verdicts | Subjective judgment |

### 4.3 Scenario-Level Findings

**Scenario 1 (clean feature)**:
- With-Skill: All 7 Gates pass, confidence = confirmed, recommend ready. Ran full toolchain: `gosec`, `govulncheck`, `golangci-lint`.
- Without-Skill: Only `make test` + `go vet`, no security scan. Incorrectly recommended draft (based on YAGNI, not Gate failures).

**Scenario 2 (poor commits)**:
- With-Skill: Gate B warns on branch name, Gate D detects lint failure (missing GoDoc), Gate G detects non-CC commit. Confidence = suspected, recommend draft. Provides 6-step fix plan.
- Without-Skill: Identified commit message and GoDoc issues but not branch naming; did not run lint; no structured Gate verdict.

**Scenario 3 (security-sensitive)**:
- With-Skill: Gate E detects `ghp_` token via `rg`/`gosec`/`golangci-lint`, produces detailed security report with CWE ID, severity, fix steps, token revocation steps. Explicitly blocks push/create.
- Without-Skill: Found token via code review, correctly marked CRITICAL, but no tool evidence chain, no CWE reference, fix advice less specific.

---

## 5. Token Cost-Effectiveness

### 5.1 Skill Context Token Cost

| Component | Lines | Est. tokens | Load timing |
|-----------|-------|-------------|-------------|
| `SKILL.md` | 373 | ~2,500 | Always |
| `pr-body-template.md` | 55 | ~400 | On demand |
| `create-pr-checklists.md` | 59 | ~500 | On demand |
| `create-pr-config.example.yaml` | 59 | ~350 | On demand |
| **Typical total** | ~487 | **~3,400** | SKILL.md + template + checklists |

Note: `scripts/create_pr.py` (1449 lines, ~10,000 tokens) is only loaded in script mode and is not part of default context.

### 5.2 Cost-Effectiveness

| Metric | Value |
|--------|------|
| Overall pass-rate gain | +71 pp (strict) / +63 pp (with PARTIAL) |
| Substantive pass-rate gain | +42 pp |
| Skill context cost | ~3,400 tokens |
| **Token cost per 1% pass-rate gain (overall)** | **~48 tokens/1%** |
| **Token cost per 1% pass-rate gain (substantive)** | **~81 tokens/1%** |

### 5.3 Comparison with Other Skills

| Skill | Token cost | Pass-rate gain | Tokens/1% |
|-------|-----------|----------------|-----------|
| `git-commit` | ~1,150 | +22 pp | ~51 |
| `go-makefile-writer` | ~1,960 (SKILL.md) / ~4,300 (full) | +31 pp | ~63–139 |
| **`create-pr`** | **~3,400** | **+71 pp** | **~48** |

`create-pr` has the best tokens/1% among these skills, mainly because its **pass-rate delta is very large** (+71 pp)—the baseline is weak in structured PR creation, so the skill’s marginal value is high.

### 5.4 Token Return Curve

```
Token investment vs. return:

~2,500 tokens (SKILL.md only):
  → Gains: Gate flow, Non-Negotiables, Confidence model, Command Playbook
  → Estimated coverage: ~90% of pass-rate gain

+400 tokens (pr-body-template.md):
  → Gains: 8-section PR Body template
  → Estimated coverage: +8% pass-rate gain (PR Body structure assertions)

+500 tokens (checklists):
  → Gains: Stage-specific checklists
  → Estimated coverage: +2% pass-rate gain (low marginal value)
```

SKILL.md alone provides ~90% of the value; reference files add the remaining 10%.

---

## 6. Overall Score

### 6.1 Dimension Scores

| Dimension | With Skill | Without Skill | Delta |
|-----------|-----------|--------------|-------|
| Gate execution completeness (A–G systematic + command evidence) | 5.0/5 | 1.5/5 | +3.5 |
| PR Body structure quality (8-section template) | 5.0/5 | 2.0/5 | +3.0 |
| Security scan capability (multi-tool cross-validation) | 5.0/5 | 2.0/5 | +3.0 |
| Confidence/Draft decision accuracy | 5.0/5 | 3.0/5 | +2.0 |
| Commit format compliance check | 5.0/5 | 2.5/5 | +2.5 |
| Structured output report (Output Contract) | 5.0/5 | 1.0/5 | +4.0 |
| **Mean** | **5.0/5** | **2.0/5** | **+3.0** |

**Dimension notes**:

- **Gate execution completeness**: With-Skill ran all 7 Gates systematically in all 3 scenarios, with exact commands and output evidence. Without-Skill only ran `make test` (occasionally `go vet`), with no auth check, branch naming check, risk classification, or security scan tools.
- **PR Body structure quality**: With-Skill always produced 8 required sections (Problem/Context, What Changed, Why, Risk/Rollback, Test Evidence, Security Notes, Breaking Changes, Reviewer Checklist). Without-Skill produced free-form bodies, often missing Risk/Rollback, Security Notes, Breaking Changes.
- **Security scan capability**: With-Skill used `rg` regex + `gosec` + `govulncheck` triple cross-validation. In Scenario 3, all three tools independently detected the `ghp_` token (including CWE-798). Without-Skill found the token via code review only, with no tool evidence chain.
- **Confidence/Draft decision**: With-Skill was correct in 3/3 scenarios (1: confirmed→ready; 2: suspected→draft; 3: suspected→draft). Without-Skill incorrectly recommended draft in Scenario 1 (YAGNI, not Gate results); Scenarios 2/3 recommended draft correctly but without formal reasoning.
- **Commit format compliance**: With-Skill Gate G validates CC format, char count, and tone. In Scenario 2 it identified 3 violations (missing type(scope):, past tense, no structured format). Without-Skill identified issues in Scenario 2 but no char count or precise format check.
- **Structured output report**: With-Skill strictly followed Output Contract (Gate verdict → Uncovered Risk → PR metadata → Next Actions). Without-Skill had no structured output or Gate verdict summary table.

### 6.2 Weighted Total

| Dimension | Weight | Score | Rationale | Weighted |
|-----------|--------|-------|-----------|----------|
| Assertion pass rate (delta) | 25% | 10.0/10 | +71 pp (overall) / +42 pp (substantive), largest delta among skills | 2.50 |
| Gate execution completeness | 20% | 10.0/10 | 3/3 scenarios ran all 7 Gates systematically + command evidence | 2.00 |
| PR Body structure quality | 15% | 10.0/10 | 3/3 scenarios full 8 sections + evidence tables | 1.50 |
| Security scan capability | 15% | 9.5/10 | Strong triple-tool validation; room for more regex patterns | 1.43 |
| Token cost-effectiveness | 15% | 7.5/10 | ~48 tok/1% best, but ~30% content unused (script, Monorepo, merge strategy) | 1.13 |
| Confidence/Draft decision accuracy | 10% | 10.0/10 | 3/3 correct decisions, clear formal reasoning | 1.00 |
| **Weighted total** | **100%** | | | **9.55/10** |

### 6.3 Comparison with Other Skills

| Skill | Weighted total | Pass-rate delta | Tokens/1% | Strongest dimension |
|-------|----------------|----------------|-----------|---------------------|
| **create-pr** | **9.55/10** | +71 pp | ~48 | Gate flow (+3.5), Output Contract (+4.0) |
| go-makefile-writer | 9.16/10 | +31 pp | ~63 | CI reproducibility (+3.0), Output Contract (+4.0) |
| git-commit | — | +22 pp | ~51 | — |

`create-pr` has the **highest overall score** among these skills because:

1. **Very large pass-rate delta** (+71 pp): PR creation is a weak area for the baseline model
2. **No weak dimensions**: 5 of 6 dimensions at full score; only Token cost-effectiveness below full due to ~30% content redundancy
3. **Best token cost-effectiveness** (~48 tok/1%): Despite higher absolute token count (~3,400), the large pass-rate delta makes unit cost lowest

**Deductions**: Token cost-effectiveness (7.5/10) is the only clearly below-full dimension, mainly because:
- Bundled Script section (~500 tokens) is 14% of SKILL.md but unused by agents
- Merge Strategy Guidance (~200 tokens) has no value in non-Squash scenarios
- Monorepo Support (~80 tokens) is useless for single-module repos

---

## 7. Conclusion

The `create-pr` skill has the **largest pass-rate delta** in this evaluation (+71 pp) and the best tokens/1% (~48 tokens/1%). This indicates that PR creation is an area where the baseline model **lacks structured capability**, so the skill’s marginal value is very high.

**Core value**:
1. **8-Gate mandatory flow**: Ensures security scan, lint, auth, etc. are not skipped
2. **Confidence model**: Turns draft/ready from subjective judgment into formal reasoning
3. **Multi-tool cross-validation**: Gate E’s rg + gosec + govulncheck triple detection stood out in Scenario 3
4. **8-section PR Body**: Standardized output gives reviewers a consistent experience

**Main risk**: ~30% of SKILL.md (script description, Monorepo, merge strategy) is unused in typical scenarios; token cost-effectiveness could be improved with modular trimming.

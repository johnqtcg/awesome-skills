# writing-plans Skill Evaluation Report

> Evaluation framework: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> Evaluation date: 2026-03-27
> Evaluation target: `writing-plans`

---

`writing-plans` is a structured skill for pre-implementation planning in multi-step tasks. It links requirement clarification, applicability checks, path discovery, and scope assessment through 4 mandatory Gates, with the goal of producing high-quality implementation plans that have verified paths, graded risks, defined interfaces, and are ready to execute immediately. Its three strongest advantages are: a 4-Gate upfront flow that prevents "ghost plans" from being written before the task is clear; four execution modes (`SKIP` / `Lite` / `Standard` / `Deep`) that scale output to task complexity and avoid document overload; and a verification system built around `[Existing]` / `[New]` / `[Inferred]` / `[Speculative]` path labels plus `[interface]` / `[test-assertion]` / `[command]` code-block tags, turning the plan into an engineering document that is both verifiable and executable.

## 1. Skill Overview

`writing-plans` is a structured implementation-planning skill. It defines 4 mandatory Gates, 4 execution modes, 10 anti-pattern checks, and a template system covering 6 change types. Its purpose is to ensure every plan completes requirement clarification, path verification, and risk grading before writing begins.

**Core components**:

| File | Lines | Role |
|------|------:|------|
| `SKILL.md` | 301 | Main skill definition (4-Gate flow, 4 execution modes, Output Contract) |
| `references/requirements-clarity-gate.md` | 128 | Gate 1: 5-dimension requirement-clarity rules |
| `references/applicability-gate.md` | 51 | Gate 2: applicability decision tree and mode selection |
| `references/repo-discovery-protocol.md` | 80 | Gate 3: path verification protocol and 4-label system |
| `references/golden-scenarios.md` | 157 | GOOD/BAD examples across 6 scenario types |
| `references/reviewer-checklist.md` | 71 | Three-layer review checklist: B / N / SB |
| `references/anti-examples.md` | 104 | 10 anti-patterns (BAD/GOOD + WHY) |
| `references/plan-update-protocol.md` | 44 | Drift severity and replanning thresholds |
| `references/plan-templates/feature.md` | 39 | Feature-plan template |
| `references/plan-templates/bugfix.md` | 31 | Bug-fix template |
| `references/plan-templates/refactor.md` | 48 | Refactor template |
| `references/plan-templates/migration.md` | 44 | Migration template |
| `references/plan-templates/api-change.md` | 42 | API-change template |
| `references/plan-templates/docs-only.md` | 45 | Documentation-change template, mainly for the SKIP path |
| Test suite (`test_skill_contract.py` + `test_golden_scenarios.py`) | 831 | Contract tests + golden-scenario validation |

---

## 2. Test Design

### 2.1 Scenario Definition

| # | Scenario | Core challenge | Expected result |
|---|----------|----------------|-----------------|
| 1 | Clear feature request | JWT auth for a Go API, crossing auth boundaries in 5 packages | Standard-mode plan, all Gates pass, path labels, interface code blocks |
| 2 | Vague request | "Make the system faster", with no scope, metrics, or target | Gate 1 STOP, ask clarifying questions, no plan document generated |
| 3 | Documentation change | Update README with a new API section | Gate 2 SKIP, concise execution checklist, no full plan document |

**Scenario 1 test prompt:**
> "I need to add JWT-based user authentication to our Go REST API. The API currently serves `/users` and `/products` endpoints. I want to add `/auth/login`, `/auth/register`, and `/auth/refresh` endpoints with middleware that protects existing routes."

**Scenario 2 test prompt:**
> "Make the system faster. There are some performance issues we need to fix."

**Scenario 3 test prompt:**
> "Update the README.md to add a section about the new API endpoints we just added. Just document what they do and show example curl commands."

### 2.2 Assertion Matrix (34 items)

**Scenario 1: Clear feature request (13 items)**

| ID | Assertion | With-Skill | Without-Skill |
|----|-----------|:----------:|:-------------:|
| A1 | Systematically run all 4 Gates, with command evidence | PASS | FAIL |
| A2 | Gate 2 (Applicability) selects Standard mode | PASS | FAIL |
| A3 | Gate 3 (Repo Discovery) adds `[Existing]` / `[New]` labels to all paths | PASS | FAIL |
| A4 | Uses the `feature.md` template structure, with all required sections | PASS | FAIL |
| A5 | Uses `[interface]` code blocks, not full implementations | PASS | FAIL |
| A6 | Uses `[command]` code blocks for verification steps, with exact commands | PASS | FAIL |
| A7 | Passes all Critical items in the Quality Scorecard (B: 6/6) | PASS | FAIL |
| A8 | Includes a reviewer loop, at least 1 round | PASS | FAIL |
| A9 | Does not include full function implementations (Anti-Pattern #2) | PASS | FAIL |
| A10 | Includes rollback and risk assessment for each task | PASS | PARTIAL |
| A11 | Plan structure matches the Output Contract | PASS | FAIL |
| A12 | Scope and risk grading are explicit, as Gate 4 output | PASS | FAIL |
| A13 | Independent tasks are marked as parallelizable | PASS | FAIL |

**Scenario 2: Vague request (10 items)**

| ID | Assertion | With-Skill | Without-Skill |
|----|-----------|:----------:|:-------------:|
| B1 | Gate 1 identifies ambiguity, with multiple STOP dimensions triggered | PASS | PARTIAL |
| B2 | Asks specific clarifying questions, at least 3 | PASS | PASS |
| B3 | Does not skip Gate 1 and jump straight to a plan document | PASS | PASS |
| B4 | Clarifying questions cover goals, scope, and constraints | PASS | PASS |
| B5 | Questions include concrete dimensions such as performance metrics, component scope, baseline, and target | PASS | PARTIAL |
| B6 | Clearly explains why clarification is needed instead of guessing | PASS | PASS |
| B7 | Does not use `[Speculative]` paths, with no degraded-mode abuse | PASS | PASS |
| B8 | Does not generate a plan body | PASS | PASS |
| B9 | Explains the path to continue after clarification | PASS | PASS |
| B10 | Output format matches the Gate 1 failure protocol, with a STOP declaration | PASS | FAIL |

**Scenario 3: Documentation change (11 items)**

| ID | Assertion | With-Skill | Without-Skill |
|----|-----------|:----------:|:-------------:|
| C1 | Gate 2 (Applicability) correctly chooses SKIP mode | PASS | PARTIAL |
| C2 | Explicitly states the reason for SKIP: docs-only change with no cross-module dependency | PASS | PASS |
| C3 | Does not generate a full Standard or Deep plan document | PASS | PASS |
| C4 | Recommends direct execution, or provides an execution checklist | PASS | PASS |
| C5 | Does not run the full Gate 3 (Repo Discovery) flow | PASS | PASS |
| C6 | Does not invent unverified file paths or endpoints | PASS | FAIL |
| C7 | Does not run a Quality Scorecard evaluation, which is unnecessary in SKIP mode | PASS | PASS |
| C8 | Does not trigger a reviewer loop | PASS | PASS |
| C9 | Output stays concise, with a clear decision section | PARTIAL | FAIL |
| C10 | Matches the SKIP signals in the `docs-only.md` template | PASS | FAIL |
| C11 | Follows the Output Contract for the SKIP branch | PASS | FAIL |

---

## 3. Pass Rate Comparison

### 3.1 Overall Pass Rate

| Config | Pass | Partial | Fail | Pass rate |
|--------|-----:|--------:|-----:|-----------|
| **With Skill** | 33 | 1 | 0 | **97%** (counting PARTIAL as 0.5 = **98.5%**) |
| **Without Skill** | 13 | 4 | 17 | **38%** (counting PARTIAL as 0.5 = **44%**) |

**Pass-rate gain: +59 pp** (with PARTIAL: +54.5 pp)

### 3.2 Pass Rate by Scenario

| Scenario | With-Skill | Without-Skill | Delta |
|----------|:----------:|:-------------:|:-----:|
| 1. Clear feature request | 13/13 (100%) | 0.5/13 (4%) | +96 pp |
| 2. Vague request | 10/10 (100%) | 8/10 (80%) | +20 pp |
| 3. Documentation change | 10.5/11 (95%) | 6.5/11 (59%) | +36 pp |

> Note: Scenario 2 has a smaller gap (+20 pp) because when a request is clearly vague, the baseline model also tends to ask clarifying questions naturally. The skill's added value is in the structured Gate 1 analysis, questions mapped precisely to the D1-D5 dimensions, and the standardized STOP-protocol output.

### 3.3 Substantive Dimensions (Core Capabilities Independent of Flow Structure)

To control for "flow-assertion bias", 12 additional substantive checks that do not depend on the flow itself were evaluated:

| ID | Check | With-Skill | Without-Skill |
|----|-------|:----------:|:-------------:|
| S1 | Scenario 2: correctly identifies ambiguity and refuses to plan immediately | PASS | PASS |
| S2 | Scenario 3: recognizes that a docs-only change does not need a formal plan | PASS | PARTIAL |
| S3 | Scenario 1: all file paths are verified before being written into the plan | PASS | FAIL |
| S4 | Scenario 1: each task includes an independent rollback step | PASS | FAIL |
| S5 | Scenario 1: plan contains interface definitions only, with no full function bodies | PASS | FAIL |
| S6 | Scenario 1: parallelizable tasks are explicitly marked | PASS | FAIL |
| S7 | Scenario 1: verification steps include runnable, exact commands | PASS | PASS |
| S8 | Scenario 1: execution mode (`SKIP` / `Lite` / `Standard` / `Deep`) is explicitly declared | PASS | FAIL |
| S9 | Scenario 1: plan contains clear in-scope and out-of-scope boundaries | PASS | FAIL |
| S10 | Scenario 1: change risk level is explicitly classified | PASS | FAIL |
| S11 | Scenario 1: plan is validated against the review checklist (B / N / SB) | PASS | FAIL |
| S12 | Scenario 3: output contains no invented paths or speculative endpoints | PASS | FAIL |

**Substantive pass rate**: With-Skill **12/12 (100%)** vs Without-Skill **3/12 (25%)**, gain **+75 pp** (counting PARTIAL = 3.5/12 ≈ 29%, gain **+71 pp**).

---

## 4. Key Difference Analysis

### 4.1 Behaviors Unique to With-Skill (Completely Missing in the Baseline)

| Behavior | Impact |
|----------|--------|
| **Systematic 4-Gate flow** | Gate 1 checks requirement clarity, Gate 2 selects the mode, Gate 3 verifies paths, and Gate 4 classifies risk, with explicit output at each step |
| **Four-label path-verification system** | `[Existing]` / `[New]` / `[Inferred]` / `[Speculative]` prevents ghost paths from appearing in plan documents |
| **Semantic code-block labels** | `[interface]` contains only signatures and structs, `[test-assertion]` captures expected behavior, and `[command]` contains exact commands, preventing implementation code from leaking into the plan |
| **`SKIP` / `Lite` / `Standard` / `Deep` mode decisions** | Adjusts output size to task complexity; docs-only changes do not trigger Standard plans, which avoids over-engineering |
| **Per-task rollback protocol** | Every task block ends with a concrete rollback step, not a single line at the bottom of a checklist |
| **Reviewer loop** | Standard mode triggers 1 round of three-layer review (B / N / SB) as a self-check mechanism |
| **Output Contract structured output** | Fixed structure: Gate verdicts -> file map -> task blocks with dependencies and blockers -> verification commands |
| **Gate 1 STOP protocol** | For vague requests, explicitly declares STOP, explains why, and gives a "continue after clarification" pipeline |

### 4.2 Behaviors the Baseline Can Do, but at Lower Quality

| Behavior | With-Skill quality | Without-Skill quality |
|----------|--------------------|-----------------------|
| Ambiguity detection | Systematic Gate 1 analysis with 4 STOP-trigger dimensions and a structured STOP declaration | Natural-language recognition; can ask questions, but without a dimension framework |
| Clarifying-question design | 5 precise questions mapped to D1-D5 dimensions | 4 questions with similar coverage, but weaker structure |
| Handling no-plan-needed scenarios | Formal SKIP decision + execution checklist + Gate summary table | Writes README content directly; useful but oversized and without a decision explanation |
| Commands | `[command]` tag + exact commands + expected-output notes | Bare command blocks, with no expected output |
| Risk treatment | Formal Gate 4 grading (Medium-High) + per-task rollback | Safety checklist with 8 items, but no risk levels or rollback |

### 4.3 Key Findings by Scenario

**Scenario 1 (clear feature)**:
- With-Skill: All 4 Gates pass in Standard mode. The 580-line plan includes a file map with 10 fully labeled paths, 6 task blocks with a dependency graph, Tasks 4 and 5 marked as parallelizable, and a Reviewer Loop with B:6/6 + N:7/7 + SB:6/6.
- Without-Skill: Produces a 13-section plan that includes a full `Config` struct, full handler logic, and full token-service code, violating Anti-Pattern #2. It has no path labels, no parallelization markers, no rollback, and no reviewer loop. The gap is large.

**Scenario 2 (vague request)**:
- With-Skill: Gate 1 clearly identifies 4 STOP triggers, asks 5 precise questions covering p99 latency, component scope, baseline vs target, constraints, and existing profiling data, explains that writing a plan would "invent the problem by inertia", and gives a 4-step continuation pipeline: rerun Gate 1 -> classify -> discovery -> planning.
- Without-Skill: Asks 4 questions of comparable quality and also proactively gives a `pprof` usage guide and a classification of common Go performance issues. The main difference is that it has no STOP declaration and no Gate protocol, so it does not define when to "move into planning."

**Scenario 3 (documentation change)**:
- With-Skill: Runs the Gate 2 decision tree fully, shows a decision table with 6 signals all pointing to SKIP, and outputs "no formal plan needed, execute directly" plus a 5-step execution checklist and a Gate summary table, 72 lines total.
- Without-Skill: Correctly recognizes that no plan is needed, but then writes about 200 lines of README content, including 10 endpoints inferred from handler filenames and full curl examples. The output is useful to the user, but the core issue is path hygiene: inferred endpoint paths such as `GET /users` and `POST /products` were written without verification, which counts as invented paths in the output.

---

## 5. Token Cost-Effectiveness Analysis

### 5.1 Skill Context Token Cost

| Component | Lines | Estimated tokens | Load timing |
|-----------|------:|-----------------:|-------------|
| `SKILL.md` | 301 | ~2,200 | Always |
| `applicability-gate.md` | 51 | ~360 | Gate 2, in most scenarios |
| `repo-discovery-protocol.md` | 80 | ~560 | Gate 3, for Standard / Deep |
| `requirements-clarity-gate.md` | 128 | ~900 | Gate 1, for vague requests |
| A plan template (any one) | 31-48 | ~220-340 | When matching the scenario type |
| **Typical Standard scenario total** | ~505 | **~3,390** | `SKILL.md` + Gate 2 + Gate 3 + 1 template |
| **Typical Gate 1 STOP scenario** | ~429 | **~3,100** | `SKILL.md` + Gate 1 reference |
| **Typical SKIP scenario** | ~397 | **~2,875** | `SKILL.md` + Gate 2 + docs template |
| **Weighted average across the 3 scenarios** | ~444 | **~3,122** | - |

Note: `golden-scenarios.md` (157 lines), `reviewer-checklist.md` (71 lines), and `anti-examples.md` (104 lines) are only loaded during reviewer loops or as references and are not counted in typical scenario context.

### 5.2 Cost-Effectiveness Calculation

| Metric | Value |
|--------|------|
| Overall pass-rate gain (with PARTIAL) | +54.5 pp |
| Overall pass-rate gain (strict PASS only) | +59 pp |
| Substantive pass-rate gain | +75 pp |
| Skill context cost (typical scenario) | ~3,100 tokens |
| **Token cost per 1% pass-rate gain (overall)** | **~57 tokens/1%** |
| **Token cost per 1% pass-rate gain (substantive)** | **~41 tokens/1%** |

### 5.3 Comparison with Other Skills

| Skill | Token cost | Pass-rate gain | Tokens/1% |
|-------|-----------:|---------------:|----------:|
| `git-commit` | ~1,150 | +22 pp | ~51 |
| `go-makefile-writer` | ~3,960 (full) | +31 pp | ~128 |
| `create-pr` | ~3,400 | +71 pp | ~48 |
| **`writing-plans`** | **~3,100** | **+54.5 pp** | **~57** |

`writing-plans` is slightly less efficient than `create-pr` on a tokens/1% basis (~57 vs ~48), mainly because in Scenario 2 the baseline can already ask clarifying questions naturally. That narrows the Scenario 2 gap to +20 pp and lowers the overall cost-effectiveness. On the substantive dimension, however, the skill's efficiency (~41 tokens/1%) is better than all compared skills.

### 5.4 Token Return Curve

```text
Mapping token investment to return:

~2,200 tokens (SKILL.md only):
  -> Gains: 4-Gate flow skeleton, 4 execution modes, path-label rules,
            code-block labeling, Output Contract, 10 anti-patterns
  -> Estimated coverage: ~85% of total pass-rate gain

+360 tokens (applicability-gate.md):
  -> Gains: decision tree, 7 signal types, "Looks Small But Isn't" patterns
  -> Estimated coverage: +8% gain (Gate 2 related assertions)

+560 tokens (repo-discovery-protocol.md):
  -> Gains: 5-step discovery protocol, label definitions, path-verification rules
  -> Estimated coverage: +5% gain (path-label assertions)

+220-340 tokens (plan template):
  -> Gains: scenario-specific template structure and trigger signals
  -> Estimated coverage: +2% gain (template-compliance assertions)
```

`SKILL.md` alone provides about 85% of the total value; the applicability gate plus discovery protocol add another 13%; templates contribute the final 2% at the margin.

---

## 6. Overall Score

### 6.1 Scores by Dimension

| Dimension | With Skill | Without Skill | Delta |
|-----------|-----------:|--------------:|------:|
| Gate execution completeness (systematic 4-Gate flow + command evidence) | 5.0/5 | 1.0/5 | +4.0 |
| Plan structure quality (template compliance + path labels + code-block labels) | 5.0/5 | 1.5/5 | +3.5 |
| Mode-selection accuracy (`SKIP` / `Lite` / `Standard` / `Deep`) | 5.0/5 | 2.0/5 | +3.0 |
| Path verification + anti-pattern avoidance (path labels + no ghost paths + no full implementation) | 5.0/5 | 1.5/5 | +3.5 |
| Requirement-clarification quality (structured Gate 1 STOP vs natural questioning) | 5.0/5 | 4.0/5 | +1.0 |
| Structured-output compliance (Output Contract + SKIP branch compliance) | 5.0/5 | 1.5/5 | +3.5 |
| **Overall average** | **5.0/5** | **1.9/5** | **+3.1** |

**Notes on the dimension scores**:

- **Gate execution completeness**: With-Skill runs the Gates systematically across all 3 scenarios: Gate 1 STOP in Scenario 2, Gate 1 + 2 with SKIP in Scenario 3, and all 4 Gates in Scenario 1. Each Gate has explicit output and decision evidence. Without-Skill has no Gate system, so the maximum reasonable score is 1.0/5.
- **Plan structure quality**: In Scenario 1, With-Skill produces a complete 580-line plan with a file map, 6 task blocks, a dependency graph, per-task rollback, and `[interface]` / `[command]` code blocks. Without-Skill produces a 13-section unstructured plan that includes full implementation code and lacks path labels, template sections, and a review loop, so it scores 1.5/5.
- **Mode-selection accuracy**: With-Skill selects the correct mode in all 3 scenarios (`Standard` / `STOP` / `SKIP`). Without-Skill does not declare a mode in Scenario 1, and in Scenario 3 it writes README content directly instead of a SKIP decision plus checklist, so it scores 2.0/5.
- **Path verification + anti-pattern avoidance**: In Scenario 1, all 10 paths in the With-Skill file map are labeled, and in Scenario 3 it does not write speculative endpoints. Without-Skill includes full implementation code in Scenario 1 (Anti-Pattern #2) and writes 10 inferred endpoint paths in Scenario 3, so it scores 1.5/5.
- **Requirement-clarification quality**: In Scenario 2, both versions can ask clarifying questions, and the baseline even adds a `pprof` usage guide, which is extra value. The main gap is that Without-Skill lacks a structured STOP declaration and a follow-up pipeline, so it scores 4.0/5.
- **Structured-output compliance**: With-Skill produces standardized output in all 3 scenarios, including Gate summary tables, decision-tree walk-throughs, and the Output Contract. Without-Skill has no Output Contract, so it scores 1.5/5.

### 6.2 Weighted Total Score

| Dimension | Weight | Score | Reason | Weighted |
|-----------|-------:|------:|--------|---------:|
| Assertion pass rate (delta) | 25% | 9.5/10 | +54.5 pp overall / +75 pp substantive; lower than `create-pr` (+71 pp) because Scenario 2 has a smaller gap | 2.375 |
| Gate execution completeness | 20% | 10.0/10 | Gates executed systematically in all 3 scenarios, with explicit output at each step | 2.00 |
| Plan structure quality | 15% | 10.0/10 | Path labels, code-block labels, and task dependency graphs are all present | 1.50 |
| Mode-selection accuracy | 15% | 10.0/10 | Correct `SKIP` / `STOP` / `Standard` decisions in all 3 scenarios | 1.50 |
| Token cost-effectiveness | 15% | 7.5/10 | ~57 tokens/1% overall; strong baseline performance in Scenario 2 narrows the gap; on substantive checks ~41 tokens/1% is best-in-class | 1.125 |
| Path verification + anti-pattern avoidance | 10% | 9.5/10 | Only C9 is PARTIAL, because the output length is 72 lines vs a suggested <=15 lines; but the SKIP scenario needs a Gate decision table, so the overage is reasonable | 0.95 |
| **Weighted total** | **100%** | | | **9.45/10** |

### 6.3 Comparison with Other Skills

| Skill | Weighted total | Pass-rate delta | Tokens/1% | Strongest dimension |
|-------|---------------:|----------------:|----------:|---------------------|
| **create-pr** | **9.55/10** | +71 pp | ~48 | Gate flow (+3.5), Output Contract (+4.0) |
| **writing-plans** | **9.45/10** | +54.5 pp | ~57 | Gate execution (+4.0), path verification (+3.5) |
| `go-makefile-writer` | 9.16/10 | +31 pp | ~128 | CI reproducibility (+3.0) |

`writing-plans` receives the second-highest overall score in this evaluation, at 9.45/10, slightly below `create-pr` at 9.55/10. The main reasons for the gap are:

1. **Slightly smaller pass-rate delta** (+54.5 pp vs +71 pp): in Scenario 2, the baseline also performs well, which reduces the overall difference.
2. **Slightly weaker token efficiency** (~57 tokens/1% vs ~48 tokens/1%): again driven by the small Scenario 2 gap.

What the two skills share is that **PR creation** and **implementation planning** are both areas where the baseline model lacks strong structure, so the marginal value of a dedicated skill is high.

**Why it lost points**:

- **Assertion pass rate (9.5/10)**: In Scenario 2, the baseline model can naturally ask clarifying questions, so the gap is only +20 pp. If the evaluation added boundary cases such as "complex feature + partially existing paths," the difference would likely be larger.
- **Token cost-effectiveness (7.5/10)**: `golden-scenarios.md` (157 lines, ~1,100 tokens) and `plan-update-protocol.md` (44 lines, ~310 tokens) were not loaded in typical scenarios. They are on-demand, low-frequency references rather than real waste.

---

## 7. Conclusion

In this evaluation, the `writing-plans` skill demonstrates highly consistent 4-Gate execution and precise mode-selection logic. Its **substantive pass rate reaches 100% (12/12)**, and its overall pass rate is **98.5%**, compared with **44%** for the baseline, a gap of **+54.5 percentage points**.

**Core value**:

1. **4-Gate upfront flow**: It blocks "start writing a plan for a vague request" (Anti-Pattern #10) at Gate 1, and blocks "run the full Standard flow for a README update" at Gate 2.
2. **Four-label path-verification system**: `[Existing]` / `[New]` / `[Inferred]` / `[Speculative]` makes every path in the plan traceable and removes ghost paths.
3. **Semantic code-block labels**: `[interface]` / `[test-assertion]` / `[command]` prevents implementation code from leaking into the plan (Anti-Pattern #2) and keeps the plan at interface-level precision.
4. **Dynamic mode selection**: `SKIP` for documentation changes, `STOP` for vague requests, and `Standard` for cross-package feature work. All 3 scenarios chose the correct mode.

**Main risks and improvement space**:

- **Scenario 2 gap is narrow** (+20 pp): when a request is obviously vague, the baseline also tends to ask questions. The skill's differentiated value is in the systematic STOP declaration, D1-D5 question design, and follow-up pipeline, but reviewers can easily overlook that structural value.
- **C9's line-count limit is too strict**: the SKIP scenario needs to show a Gate decision table, which is structured evidence. A 72-line output is reasonable, so the "<=15 lines" assertion would be better replaced with "no full plan body."
- **Low usage of `golden-scenarios.md`**: this 157-line reference was not actively loaded in any of the 3 test scenarios. `SKILL.md` should give clearer guidance on when to pull it into the reviewer-loop phase.

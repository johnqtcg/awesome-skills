---
title: "Skill Iteration: Practice-Driven Continuous Improvement"
owner: john
status: active
last_updated: 2026-04-02
applicable_versions: Claude Code 1.0+
audience: Skill developers who have deployed a skill and are encountering missed findings or quality issues
prerequisite: Evaluation.md (§10–11)
---

## Table of Contents

- [15. Iteration Methodology](#15-iteration-methodology)
    - [15.1 Two Drivers of Iteration](#151-two-drivers-of-iteration)
    - [15.2 The Four Phases of an Iteration Cycle](#152-the-four-phases-of-an-iteration-cycle)
    - [15.3 Root-Cause Classification Framework](#153-root-cause-classification-framework)
    - [15.4 Improvement Strategies for Each Root Cause](#154-improvement-strategies-for-each-root-cause)
        - [15.4.1 Checklist Gap: The Engineering Method for Filling Holes](#1541-checklist-gap-the-engineering-method-for-filling-holes)
        - [15.4.2 Model-Execution Omission: The Limits of Rule Constraints](#1542-model-execution-omission-the-limits-of-rule-constraints)
        - [15.4.3 Domain-Knowledge Blind Spot: The Finite Value of References](#1543-domain-knowledge-blind-spot-the-finite-value-of-references)
    - [15.5 Verification Methodology](#155-verification-methodology)
- [16. Case Studies and Iteration Boundaries](#16-case-studies-and-iteration-boundaries)
    - [16.1 Three Root Causes in Practice (Using a Code-Review Skill as the Example)](#161-three-root-causes-in-practice-using-a-code-review-skill-as-the-example)
    - [16.2 Miss Attribution Summary](#162-miss-attribution-summary)
    - [16.3 `git-commit` Skill Iteration Cases (a Complementary Perspective)](#163-git-commit-skill-iteration-cases-a-complementary-perspective)
    - [16.4 Iteration Stop Signals](#164-iteration-stop-signals)
    - [16.5 The Full Skill Lifecycle and Multi-Layer Defence](#165-the-full-skill-lifecycle-and-multi-layer-defence)

---

<a id="15-iteration-methodology"></a>
## 15. Iteration Methodology

Skill quality is never written in one shot. It is earned through repeated cycles of "real usage exposes a problem → root-cause classification → targeted fix → verification." This chapter builds a systematic framework for improving skills over time.

<a id="151-two-drivers-of-iteration"></a>
### 15.1 Two Drivers of Iteration

Iteration is triggered by two channels, which complement rather than replace each other:

| Driver | Source | Typical Trigger |
|--------|--------|-----------------|
| **Quantitative evaluation** | Three-dimensional A/B comparison from Chapter 10 | Evaluation score below threshold; with-skill vs without-skill gap under 10% |
| **Practical observation** | Misses and quality complaints from day-to-day use | Human review finds a defect the AI missed; developer reports too many false positives |

The Evaluation chapter (§10–11) answers "how do I measure the current quality of a skill" — it establishes a baseline and points to directions. The Iteration chapter answers "given that data or a missed finding, how do I improve systematically" — root-cause classification, targeted fixes, and effect verification. Together they form a closed loop: evaluation points the way, iteration completes the improvement, re-evaluation confirms the result.

Practical observation is an important supplement to quantitative evaluation. A/B tests require scenarios to be designed in advance, but real code is infinitely varied and will always expose patterns that test cases miss. When a developer notices a defect the skill should have caught during code review, that is a high-quality "free evaluation" — it simultaneously reveals a blind spot and provides a concrete case to validate any fix.

<a id="152-the-four-phases-of-an-iteration-cycle"></a>
### 15.2 The Four Phases of an Iteration Cycle

Every iteration follows a fixed four-phase structure. Skipping any phase reduces the credibility of the improvement:

```
① Real usage exposes a problem
   ↓  Human review finds a miss / evaluation score falls below threshold
② Root-cause classification
   ↓  Determine: checklist gap / model-execution omission / domain-knowledge blind spot
③ Targeted fix
   ↓  Fill checklist / strengthen execution rules / add reference
④ Verify with a clean context
   ↓  Fresh conversation, no history carryover, rerun the identical case
   Loop back to ①
```

**Phase ①** The key is to "preserve the scene": record the missed case together with the code being reviewed. That becomes the test input for all subsequent verification.

**Phase ②** is the step most often skipped, but it is the most critical. Jumping straight to editing the skill without classifying the root cause almost always leads to the wrong fix: treating a "model-execution omission" as a "checklist gap" just makes `SKILL.md` longer without reducing the miss rate (see §15.3 and §15.4).

**Phase ③** The improvement must match the root-cause type. The three root causes each require a different remedy (see §15.4).

**Phase ④** is the core constraint for verification: **clear the conversation context and rerun the identical case in a fresh conversation**. Verifying in the same conversation is not valid — the model may "remember" the earlier discussion rather than relying solely on the updated skill.

<a id="153-root-cause-classification-framework"></a>
### 15.3 Root-Cause Classification Framework

This is the core of the iteration methodology. Every miss must be placed into one of the three categories below. The root causes have very different fixability, so the remedies differ sharply:

| Root-Cause Type | Definition | Fixability | Remedy | Observed Fix Rate |
|-----------------|------------|------------|--------|-------------------|
| **Checklist gap** | The SKILL.md checklist does not cover this item; the model "didn't know to look" | Deterministic | Fill the checklist | **100% (3/3)** |
| **Model-execution omission** | The checklist covers it, but the model skipped it during execution; it "knew but didn't check" | Probabilistic | Strengthen execution rules + sharpen wording | **67% (2/3)** |
| **Domain-knowledge blind spot** | Business-scenario-specific knowledge beyond the reach of a general checklist | Limited | Add a reference | **0% (optimization-suggestion class)** |

The data above come from attribution analysis of 3 real cases and 8 misses in the `go-code-reviewer` skill (details in §16.2).

**How to diagnose the root cause**: answer one question first: **Is this check explicitly listed in the SKILL.md checklist?**

- **No** → checklist gap. Adding the item to the checklist fixes it deterministically.
- **Yes, but the model did not execute it** → model-execution omission. Analyze the trigger conditions for the omission (high defect density, ambiguous rule wording) and strengthen accordingly.
- **Cannot be listed in a general checklist** (for example, a business-scenario-specific performance optimization) → domain-knowledge blind spot. You can add knowledge to a reference file, but the effect is limited.

A single miss may involve more than one root cause (see Case 2, §16.1). When that happens, handle it at the highest-priority root cause while recording the compound factors.

<a id="154-improvement-strategies-for-each-root-cause"></a>
### 15.4 Improvement Strategies for Each Root Cause

<a id="1541-checklist-gap-the-engineering-method-for-filling-holes"></a>
#### 15.4.1 Checklist Gap: The Engineering Method for Filling Holes

A checklist gap is the **only root cause with a deterministic fix**. Once the item is added, the model will be forced to check it on the next run. In observed cases the fix rate is 100%.

Engineering method for filling a checklist gap:

**Step 1: Find the right insertion point.** New checklist items should be inserted under the logically related category — for example, "goroutine panic recover" belongs under Concurrency & Lifecycle, and "pointer-slice nil guard" belongs under Code Quality — not dumped at the end.

**Step 2: Control description granularity.** A checklist item should only say *what* to look for, not *why* or *how to look* — those go in the corresponding reference file. Before-and-after comparison:

| Item | Before (verbose) | After (recommended) |
|------|-----------------|---------------------|
| Goroutine recover | "panics inside goroutines are not propagated to the parent goroutine; any unrecovered panic crashes..." (2 lines) | `Goroutine missing defer recover() — unrecovered panic crashes entire process` (1 line) |
| Goroutine count | "spawning one goroutine per item in an unbounded loop causes resource exhaustion..." (2 lines) | `Goroutines created per loop element without concurrency limit (semaphore / errgroup.SetLimit / worker pool)` (1 line) |

**Step 3: Update the corresponding reference file.** A new checklist item typically needs a BAD/GOOD example and trigger conditions added to the matching reference file so the model can correctly identify the pattern during execution.

**Step 4: Monitor SKILL.md size.** After each checklist fill, check the total line count and keep `SKILL.md` ≤ 500 lines. When it grows beyond that, prefer moving anti-examples or detailed explanations to reference files (see the slimming practice in §16.1 Case 3).

<a id="1542-model-execution-omission-the-limits-of-rule-constraints"></a>
#### 15.4.2 Model-Execution Omission: The Limits of Rule Constraints

A model-execution omission is the trickiest root-cause type. The checklist explicitly lists the item, but the model skips it during execution — this is not a knowledge problem, it is an attention-allocation problem.

Common trigger conditions:

- **High defect density**: when multiple High-severity defects are already present, the model focuses on "things that stop the code from running" and systematically ignores lower-priority checklist items.
- **Ambiguous execution-rule wording**: a checklist item that only names a pattern (e.g., `Missing error wrapping`) without pointing to a concrete inspection action (e.g., `inspect every return err path`) gives the model no operational anchor.
- **Post-hoc rationalization hallucination**: after the model skips a check and is challenged, it produces a plausible-sounding post-hoc explanation rather than admitting the omission. This is an inherent property of LLM reasoning and cannot be eliminated by sharper wording.

Improvement measures:

1. **Sharpen wording**: convert passive descriptions into active action directives. For example:
   ```
   # Before
   - Missing error wrapping context (`%w`)

   # After
   - Missing error wrapping context (`%w`) — inspect every `return err` path
   ```

2. **Add an execution-integrity rule**: explicitly write into the Review Discipline section that "regardless of how many High findings have already been identified, all checklist categories must still be executed," targeting attention competition under high-defect-density conditions.

3. **Require evidence before applying anti-example suppression**: any anti-example suppression must first cite concrete evidence from the code proving the precondition is satisfied. Category matching alone is not grounds for suppression.

**Model-execution omissions can only be mitigated at the rule level, not fully eliminated. This is an architectural problem; the solution is in Architecture.md (§17–18).**

<a id="1543-domain-knowledge-blind-spot-the-finite-value-of-references"></a>
#### 15.4.3 Domain-Knowledge Blind Spot: The Finite Value of References

A domain-knowledge blind spot refers to business-scenario-driven optimization suggestions that cannot be listed in a general checklist. A typical example: when a function contains both a Count and a Find without pagination, and the business knows that most users have zero records, executing Count first and returning early when the result is zero can significantly reduce SQL requests — but this requires knowing the access pattern of the business to suggest. That is knowledge a general checklist cannot capture.

The remedy is to add a relevant section (with BAD/GOOD examples and applicability conditions) to the reference file. But this fix has **limited effect**:

- A reference provides "knowledge in reserve" rather than "execution directives." The model must complete the reasoning chain from code traits to the optimization suggestion on its own.
- The longer the reasoning chain and the more business context it requires, the less a reference supplement helps.
- In observed cases, a count-first optimization suggestion was still not discovered autonomously after the reference was added (fix rate 0%).

**For domain-knowledge blind spots, the more pragmatic strategy is:**
- Adjust expectations: reclassify this category from "AI should find automatically" to "focus of human review."
- If a business-specific pattern is important enough and appears frequently, consider building a dedicated skill for it rather than trying to handle it inside a general-purpose skill.

<a id="155-verification-methodology"></a>
### 15.5 Verification Methodology

Verification is the closing step of the iteration loop. Poor design here invalidates the entire improvement effort.

**Core constraint**: clear the conversation context and rerun the previously missed case in a fresh conversation. Results from verification in the same conversation are not trustworthy.

**Verification checklist:**

```
□ Conversation context is cleared (clear context or new conversation)
□ Model version matches the first review
□ Review mode matches the first review (Lite / Standard / Strict)
□ Code being reviewed is identical to the original (pre-fix version, not the corrected version)
□ No hints or guidance provided (do not say "pay attention to X")
```

**Quantitative record:**

Verification results should be recorded in a table, comparing the original review and the post-improvement review item by item, distinguishing among four states: "held," "fixed," "not fixed," and "newly found." This record is both proof of the improvement and the starting data for any subsequent iteration.

**Handling partial fixes:** if a miss is still not caught after the improvement, re-classify the root cause — the initial attribution may have been wrong, or the root cause is "execution omission" and the execution rule still needs to be stronger. Residual misses enter the next iteration rather than being ignored.

---

<a id="16-case-studies-and-iteration-boundaries"></a>
## 16. Case Studies and Iteration Boundaries

Theoretical frameworks only become truly understandable through concrete cases. This chapter uses real iteration experience from two skill types as examples to show the root-cause classification framework applied in actual scenarios — the methodology itself (classify → fix → verify) is not specific to code review and applies to any skill that encounters misses or quality problems.

<a id="161-three-root-causes-in-practice-using-a-code-review-skill-as-the-example"></a>
### 16.1 Three Root Causes in Practice (Using a Code-Review Skill as the Example)

The following cases all come from real missed-finding records during `go-code-reviewer` use, serving as empirical demonstrations of the three root-cause categories. Each case corresponds to one (or more) root-cause types and shows the reasoning behind choosing a fix strategy and the actual outcome.

This is the most complete empirical record of the iteration methodology: 3 cases, 8 misses, systematic attribution, targeted fixes, and clean-context verification.

#### Case 1: ListLayout — Model-Execution Omission + Post-Hoc Rationalization Hallucination

**Code under review (excerpt):**

```go
func (s *LayoutService) ListLayout() (layouts []*db.Layout, total int64, err error) {
    whereClause := fmt.Sprintf("uid = %v and corp_id = %v", s.uid, s.corpId)
    if err := s.orm.Model(&db.Layout{}).Where(whereClause).Order("updated_at desc").Find(&layouts).Error; err != nil {
        return nil, 0, err  // unwrapped
    }
    if err := s.orm.Model(&db.Layout{}).Where(whereClause).Count(&total).Error; err != nil {
        return nil, 0, err  // unwrapped
    }
    return layouts, total, nil
}
```

**AI reported:** SQL injection (High), missing `ctx` (Medium), Find without pagination (Medium). Three findings total.

**Misses identified during human review:**

- **Miss 1**: both `return nil, 0, err` statements pass the raw GORM error straight through. The caller cannot tell which query failed, and the raw error may expose table names or column names. Correct: `return nil, 0, fmt.Errorf("ListLayout: find layouts: %w", err)`.
- **Miss 2**: count-first optimization — skip the more expensive Find when `total == 0`, which can significantly reduce SQL requests in business scenarios where empty result sets are common.

**Root-cause analysis:**

| Miss | Root Cause | Analysis |
|------|------------|----------|
| Unwrapped errors | **Model-execution omission** | SKILL.md Error Handling checklist explicitly lists `Missing error wrapping context (%w)`, but the model did not walk through every `return err` path |
| Count-first optimization | **Domain-knowledge blind spot** | A business-scenario-driven performance optimization that a general checklist cannot cover |

When challenged about the missed error wrapping, the model claimed it had "misapplied the anti-example suppression rule" — but the code had no wrapping at all, so the anti-example's precondition obviously was not met. **This is a textbook post-hoc rationalization hallucination**: after the model omits a check and is challenged, it constructs a plausible-sounding explanation instead of admitting the omission. This phenomenon itself drove an improvement: add "must first cite concrete evidence from the code before applying any anti-example suppression" to the execution rules.

#### Case 2: getBatchUser Serial Version — Checklist Gap + Asymmetric Analysis Perspective

**Code under review (excerpt):**

```go
func getBatchUser(ctx context.Context, userKeys []*UserKey) (users []*User, error) {
    userList := make([]*User, len(userKeys))
    for i, u := range userKeys {
        user, err := redis.GetGuest(ctx, u.Id)  // u could be nil → panic
        if err != nil {
            log.WarnContextf(ctx, "no found guest user: %v", u)
            continue
        }
        userList[i] = user
    }
    return userList, nil
}
```

**AI reported:** error silently swallowed (High), result slice contains implicit nil entries (Medium), N+1 Redis calls (Medium). Three findings total.

**Miss identified during human review:** `userKeys []*UserKey` is a pointer slice; elements may be nil. The code dereferences `u.Id` directly — if any element is nil, a panic fires. Correct: add `if u == nil { continue }` at the top of the loop.

**Root-cause analysis:**

| Miss | Root Cause | Analysis |
|------|------------|----------|
| Pointer-slice nil guard | **Checklist gap + asymmetric analysis perspective** | SKILL.md Code Quality checklist has no item for this; additionally, the model noticed **output-side** nil (`userList[i]` may be nil) in the same loop but did not apply the same analysis to the **input side** (`u` may be nil) — an asymmetric analysis perspective |

This is a compound root-cause case: even after the checklist is filled, the input/output asymmetry in analysis may still cause the miss. The fix must both add the checklist item and explicitly state in the execution rules that "for pointer slices, check both the input side and the output side."

#### Case 3: getBatchUser Concurrent Version — Attention Competition Under High Defect Density

**Code under review (excerpt):**

```go
func getBatchUser(ctx context.Context, userKeys []*UserKey) (users []*User, error) {
    userList := make([]*User, 0)  // no capacity pre-allocation
    var wg sync.WaitGroup
    for i, u := range userKeys {
        if u == nil { continue }
        wg.Add(1)
        go func() {
            defer wg.Done()
            // no recover, no concurrency limit
            user, err := redis.GetGuest(ctx, u.Id)
            if err != nil { log.WarnContextf(ctx, "no found guest user: %v", u); continue }
            userList = append(userList, user)  // data race
        }()
    }
    return userList, nil  // goroutines not awaited
}
```

**AI reported (Strict mode):** `continue` inside goroutine is a compile error (High), missing `wg.Wait()` (High), concurrent write data race (High), loop-variable capture (High), error silently swallowed (Medium). Five findings, four of which are High.

**Misses identified during human review:**

- **Slice without capacity pre-allocation**: `make([]*User, 0)` has zero initial capacity; `len(userKeys)` is a known upper bound and should pre-allocate: `make([]*User, 0, len(userKeys))`.
- **Goroutine missing panic recover**: panics do not propagate across goroutine boundaries in Go. Any unrecovered panic inside a goroutine crashes the entire process, and `wg.Done()` will not execute either.
- **Unbounded goroutine count**: `len(userKeys)` has no upper bound, so instantaneously spawning a large number of goroutines can spike scheduler pressure and exhaust the Redis connection pool.

**Root-cause analysis:**

| Miss | Root Cause | Analysis |
|------|------------|----------|
| Slice capacity pre-allocation | **Model-execution omission** | SKILL.md Performance checklist explicitly lists this item, but 4 High concurrent defects consumed the attention; the Performance checklist category was skipped |
| Goroutine panic recover | **Checklist gap** | Concurrency checklist covers concurrency "correctness" but is missing concurrency "safety" (recover not covered) |
| Goroutine count limit | **Checklist gap** | Concurrency checklist is missing concurrency "scale safety" (resource exhaustion, scheduler pressure) |

Common pattern across all three misses: **when multiple High defects exist, attention concentrates on "things that make the code stop running" and systematically skips the category of "code that runs but collapses at production scale."**

<a id="162-miss-attribution-summary"></a>
### 16.2 Miss Attribution Summary

Across the 3 cases there were 8 misses (7 hard defects, 1 optimization suggestion). Attribution distribution:

| Root-Cause Type | Count | Corresponding Misses |
|-----------------|-------|---------------------|
| Checklist gap | 3 | goroutine panic recover, goroutine count limit, pointer-slice nil guard |
| Model-execution omission | 3 | unwrapped errors, slice capacity pre-allocation, attention scatter under high defect density |
| Domain-knowledge blind spot | 1 | count-first optimization (scenario-specific suggestion) |
| Checklist gap + model-execution omission (compound) | 1 | pointer-slice nil guard (checklist gap + asymmetric analysis perspective) |

**Improvements applied:** added 4 checklist items, added 1 new reference file (`go-review-anti-examples.md`), strengthened 2 execution rules; also slimmed `SKILL.md` from 502 lines to 470 lines by migrating anti-examples to a standalone reference file.

**Verification results (identical case rerun with a clean context):**

| Root-Cause Type | Improvement Applied | Fixed | Not Fixed | Observed Fix Rate |
|-----------------|---------------------|-------|-----------|-------------------|
| Checklist gap | Fill checklist | 3/3 | 0 | **100%** |
| Model-execution omission | Strengthen execution rules | 2/3 | 1 | **67%** |
| Domain-knowledge blind spot | Add reference | 0/1 | 1 | **0%** |
| Checklist gap + execution omission (compound) | Fill + strengthen rules | 1/1 | 0 | **100%** |

Total misses reduced from 8 to 2, **overall fix rate 75%**. The post-improvement run also found 6 new issues that had not been reported before (such as named-return shadowing and a misleading log message).

<a id="163-git-commit-skill-iteration-cases-a-complementary-perspective"></a>
### 16.3 `git-commit` Skill Iteration Cases (a Complementary Perspective)

`go-code-reviewer` demonstrates the "miss-driven" iteration path, triggered by defects discovered in real usage. `git-commit` illustrates two other common iteration triggers: **too many false positives** (tool noise erodes trust) and **missing honest degradation** (the skill produces seemingly confident advice when evidence is insufficient). The skill type and trigger are different, but the root-cause classification and fix logic are identical.

#### Iteration Case 1: Controlling False Positives in Secret Detection

**Problem found:** the secret-detection gate produced severe false positives in practice. Generic patterns like `password=` and `token=` frequently matched test files, documentation, and example configs (such as `password=changeme` in `config.example.yml`). The initial "block on any match" design interrupted developers constantly.

**Root-cause analysis:** the initial version treated all secret patterns equally — `AKIA0EXAMPLE1234` (a structured token with very few false positives) and `password=changeme` (a generic key name with many false positives) triggered the same blocking logic. This is a classic **precision-gradient absence** problem.

**Improvement:**

| Change | Problem Solved |
|--------|----------------|
| Split `SECRET_PATTERNS` into Tier 1 (structured tokens) and Tier 2 (generic key names) | Distinguishes high- and low-confidence patterns, applies tiered handling |
| Added per-line inline suppression (`# nosec` / `# git-commit-allow`) | Gives a standard opt-out for confirmed safe matches |
| Extended path filter to `/examples/`, `.template.`, `.dist`, and similar | Covers common storage locations for example config files |
| Added three-tier value analysis for Tier 2 hits (ignore / soft warn / hard block) | `password=changeme` is silently ignored; high-entropy values still block |

**Verification:** false positives on example config files dropped from ~60% to <5%; the sensitive-scan scenario pass rate held at 100%.

#### Iteration Case 2: Honest Degradation for Scope Discovery

**Problem found:** the skill determines scope naming by analyzing the 30 most recent `git log` entries. On new repos or freshly switched branches with sparse history, scope suggestions became inconsistent — sometimes adding a scope, sometimes not; sometimes the same module was named differently.

**Root-cause analysis:** the algorithm had no floor on its dependency on historical data. When the sample was too small, statistical results were unreliable, but the skill still emitted what looked like confident advice. This is a **missing honest degradation** problem (see Advanced.md §6.7).

**Improvement:** when `git log` has fewer than 10 entries, make scope optional and show a note: "history too sparse, consider specifying scope manually." Also add a scope-consistency check: if the 10 most recent commits for the same module use the scope name inconsistently, emit a warning.

**Core principle:** a skill that refuses to give an unreliable recommendation is more trustworthy than one that always gives a recommendation that is sometimes wrong.

<a id="164-iteration-stop-signals"></a>
### 16.4 Iteration Stop Signals

Not all skills need to be iterated indefinitely. The following four signals indicate that iteration can pause or stop:

| Signal | Meaning |
|--------|---------|
| With-skill vs without-skill delta in A/B tests is below 10% | The skill's differentiating value is too small; consider simplifying or merging it |
| Three consecutive iterations produce no change in evaluation score | The current architecture has reached its ceiling; consider a fundamental redesign or accept the current state |
| The skill is bypassed more than 30% of the time in real usage | The skill creates friction with the developer workflow; revisit the skill's positioning |
| Token consumption keeps rising but ROI is falling | The skill is over-engineered; consider splitting it into multiple lighter skills |

Stopping iteration does not mean abandoning maintenance. The following events should trigger a re-evaluation: model version upgrades, significant changes to the business domain, updates to team coding standards, or new cases that reveal previously unseen miss patterns.

Skill iteration should follow the same version-control practices as code: commit every improvement to Git with a clear commit message explaining what changed and why. Team members can trace the skill's evolution through Git history and understand the context behind each design decision. After every change, rerun `scripts/run_regression.sh` to confirm that no existing contract tests or golden-scenario tests were broken.

<a id="165-the-full-skill-lifecycle-and-multi-layer-defence"></a>
### 16.5 The Full Skill Lifecycle and Multi-Layer Defence

Combining the quantitative framework from the Evaluation chapter (§10–11) with the iteration practices in this chapter, the full lifecycle of a skill looks like this:

```
┌─────────────────────────────────────────────────────────────────┐
│                     Full Skill Lifecycle                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ① Build                                                        │
│  ├── Design patterns (gates + anti-examples + progressive       │
│  │   disclosure + structured output)                            │
│  ├── Contract tests + golden-scenario tests                     │
│  └── Regression tests pass                                      │
│       ↓                                                         │
│  ② Quantitative evaluation (Evaluation.md §10)                  │
│  ├── Trigger accuracy: positive/negative query sets → Recall +  │
│  │   Precision                                                  │
│  ├── Real task performance: with-skill vs without-skill         │
│  │   comparison experiments                                     │
│  └── Token cost-effectiveness: extra cost vs developer-time ROI │
│       ↓                                                         │
│  ③ Data-driven iteration (this chapter §15–16)                  │
│  ├── Real misses / evaluation data → root-cause classification  │
│  │   (§15.3)                                                    │
│  ├── Targeted fix (§15.4) → clean-context verification (§15.5) │
│  └── Repeat until the bar is met or a stop signal fires (§16.4) │
│       ↓                                                         │
│  ④ Integrate into the development workflow (Integration.md      │
│  │  §12–14)                                                     │
│  ├── Local: Makefile-driven quality gates                       │
│  ├── CI: skill-driven automated gates                           │
│  └── PR: AI-driven code review                                  │
│       ↓                                                         │
│  ⑤ Continuous monitoring and re-evaluation                      │
│  ├── Model updates / new scenarios / team-standard changes      │
│  │   trigger re-evaluation                                      │
│  └── Contract tests + regression tests guard against skill drift│
│       ↓                                                         │
│  Loop back to ② or ③                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Where phase ③ sits in the loop:** in the past, skills jumped straight from ① to ④, with no validation in between — like shipping code without running tests. The Evaluation chapter (②) establishes a quantitative baseline; the Iteration chapter (③) provides a systematic improvement path. Together they bring the same engineering rigor to skill development that we expect from software development.

**Multi-layer defence**

The goal of iterative improvement is to maximize the effectiveness of AI skills, but AI code review has two hard boundaries that iteration cannot eliminate:

1. **Attention-competition boundary**: under high-defect-density conditions, the model systematically ignores lower-priority checklist items. Rule constraints can lower the probability, but cannot eliminate it.
2. **Reasoning-chain-length boundary**: optimization patterns that require combining multiple signals may not be discovered autonomously by the model even when a reference provides the full knowledge.

For this reason, a high-quality code assurance system must be **multi-layer defence**:

```
┌─────────────────────────────────────────────────────────────────┐
│                   Code Quality Assurance System                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Layer 1: Automated tests                                       │
│  ├── Unit tests (logic correctness, boundary conditions)        │
│  ├── API integration tests (interface contracts, end-to-end     │
│  │   data flows)                                                │
│  └── E2E tests (user flows, cross-service interactions)         │
│                                                                 │
│  Layer 2: AI code review                                        │
│  ├── Static analysis tools (go vet, staticcheck, golangci-lint) │
│  └── AI Agent skill review (pattern matching, defect detection) │
│                                                                 │
│  Layer 3: Human code review                                     │
│  ├── Business logic correctness (domain knowledge the AI cannot │
│  │   judge)                                                     │
│  ├── Architectural design review (cross-module impact, long-    │
│  │   term maintainability)                                      │
│  └── AI review result verification (catching AI misses,        │
│      calibrating AI output)                                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

The three layers complement rather than replace each other:

- **Automated tests** catch regressions and behavioral drift — whether code *runs correctly*.
- **AI code review** catches pattern-based defects and known anti-patterns — whether code *has common pitfalls*.
- **Human code review** catches business semantics, architectural soundness, and AI blind spots — whether code *should be written this way*.

No single layer is sufficient to guarantee code quality. The value of iterating a skill is to continuously raise the coverage and accuracy of Layer 2, not to replace Layer 3 with AI.

---

> **Next step**: Architecture.md (§17–18) explains how to address the architectural root cause of attention dilution — the boundary that iteration at the rule level cannot fully overcome.

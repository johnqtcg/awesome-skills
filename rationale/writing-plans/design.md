---
title: writing-plans skill design rationale
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-27
applicable_versions: current repository version
---

# writing-plans Skill Design Rationale

`writing-plans` is a structured pre-implementation planning framework for multi-step work. Its core idea is: **the goal of a high-quality implementation plan is to first verify that the request is actually clear enough to plan, that the task truly deserves a formal plan, that the file paths in the plan are trustworthy, that the risks are classified, and that a developer with zero codebase context could execute the plan directly.** That is why the skill turns the Requirements Clarity Gate, Applicability Gate, Repo Discovery Gate, Scope & Risk Gate, Execution Modes, Output Contract, Scorecard, Reviewer Loop, and Plan Update Protocol into one fixed workflow.

## 1. Definition

`writing-plans` is used for:

- writing implementation plans for features, bugfixes, refactors, migrations, API changes, and docs-only tasks,
- completing requirements clarification, path verification, and risk classification before implementation starts,
- keeping plans at the interface-and-verification level rather than full implementation level,
- selecting between `SKIP / Lite / Standard / Deep` based on task complexity,
- and running self-check plus reviewer-loop validation before execution handoff.

Its output is not just task decomposition. It also includes:

- an explicit mode,
- a concrete goal plus clear scope boundaries or explicit assumptions,
- file-path labels (`[Existing] / [New] / [Inferred] / [Speculative]`),
- verification commands,
- rollback / risk notes where applicable,
- execution handoff.

From a design perspective, it is closer to an implementation-planning governance framework than to a prompt that simply translates requirements into a checklist.

## 2. Background and Problems

The skill is not solving "models cannot write plans." It is solving the fact that default planning work often drifts into several high-risk distortions:

- the requirements are still unclear, but a polished plan is written anyway,
- the task is tiny, but it is over-engineered into a formal plan,
- the plan contains many paths and code fragments that were never actually verified.

Without an explicit process, the most common failures cluster into eight categories:

| Problem | Typical consequence |
|---------|---------------------|
| Requirements clarity is not checked first | a "ghost plan" is written against a misunderstood task and execution later reworks it |
| Applicability is not checked first | a tiny single-file change gets a heavy formal plan whose cost exceeds execution |
| Paths are not verified | the plan contains non-existent files, line references, or modules |
| Full implementation code leaks into the plan | the plan creates false confidence and usually gets rewritten during real execution |
| Risk is not classified | migrations, auth changes, public API changes, and normal features are treated the same |
| Verification is vague | steps end with "check that it works" instead of runnable proof |
| No reviewer perspective exists | the plan may be well formatted but still logically flawed in dependency order or validation logic |
| No deviation protocol exists | when reality diverges from plan, no one knows whether to continue, adjust, or replan |

The design logic of `writing-plans` is to answer "is the request clear enough to plan, is formal planning even justified, which paths are verified versus inferred, how risky is the work, and what planning depth is appropriate?" before actual plan authoring begins.

## 3. Comparison with Common Alternatives

It helps to compare it with a few common alternatives:

| Dimension | `writing-plans` skill | Asking a model to "write an implementation plan" | Turning the request into a quick TODO list |
|-----------|-----------------------|--------------------------------------------------|--------------------------------------------|
| Requirements-clarity gate | Strong | Weak | Weak |
| Applicability judgment | Strong | Weak | Weak |
| Path-verification discipline | Strong | Weak | Weak |
| Mode routing (`SKIP/Lite/Standard/Deep`) | Strong | Weak | Weak |
| Risk / rollback design | Strong | Medium | Weak |
| Reviewer loop discipline | Strong | Weak | Weak |
| Execution-deviation handling | Strong | Weak | Weak |
| Executability of the plan | Strong | Medium | Weak |

Its value is not only that the plan is "more complete." Its value is that the plan becomes a trustworthy engineering artifact whose paths, scope, and execution logic are explicit.

## 4. Core Design Rationale

### 4.1 The Requirements Clarity Gate Comes First

The first gate in `writing-plans` is not complexity classification. It is the Requirements Clarity Gate. The skill first decides whether the request is actually "clear enough to plan" and stops to ask questions when necessary.

This is critical because the biggest source of planning waste is often not bad task decomposition. It is planning the wrong thing. The gate explicitly checks:

- Goal Specificity,
- Scope Boundary,
- Success Criteria,
- Constraints and Compatibility,
- Edge Cases and Error Handling (mainly for Standard / Deep).

It also requires clarification questions to focus on WHAT, not HOW, and limits the number of clarification rounds. That is mature design because it prevents two opposite distortions:

- writing a plan when the request is still too vague,
- interrogating a simple clear task until planning becomes slower than implementation.

The evaluation illustrates this well: in the vague-requirements scenario, the baseline model could also ask useful questions, so the gap was smaller than in the clear-feature scenario. But with-skill's increment was the structured STOP protocol, the explicit trigger dimensions, and the clear pipeline for re-entering planning after clarification.

### 4.2 The Applicability Gate Matters More Than Plan Quality Alone

At Gate 2, `writing-plans` first decides whether a formal plan is warranted at all, and routes the task into:

- `SKIP`,
- `Lite`,
- `Standard`,
- `Deep`.

This is highly distinctive because many planning failures are not really about the quality of the plan text. They are about the task not deserving a formal plan in the first place. For example:

- a single file, <30-line, small fix should be executed directly,
- docs-only or config-only changes should usually be SKIP or Lite,
- a clear single-module feature may be Lite,
- a normal multi-file feature or bugfix may be Standard,
- cross-module migrations or architecture work may be Deep.

This solves mismatch between plan weight and task complexity. The docs-only evaluation scenario is the clearest example: with-skill correctly chose `SKIP`, while without-skill roughly sensed that a big plan was unnecessary but still jumped into a large block of README content without an explicit applicability decision.

### 4.3 The Repo Discovery Gate Uses the Four-Label Path System

Before any file path is written into a plan, `writing-plans` requires every path to carry one of:

- `[Existing]`,
- `[New]`,
- `[Inferred]`,
- `[Speculative]`.

This is critical because whether the paths inside a plan are trustworthy determines whether the plan is executable at all. The skill also adds hard constraints:

- do not write line numbers for unread files,
- do not write complete implementation code for unverified interfaces,
- if the repo is inaccessible, switch into Degraded Mode and downgrade all paths to `[Speculative]`.

This turns path status from implicit guesswork into explicit contract. In the evaluation, this was one of the biggest differences between with-skill and without-skill: with-skill labeled the file map systematically, while without-skill was much more likely to leak unverified paths or inferred endpoints into the plan.

### 4.4 The Scope & Risk Gate Is Not an Optional Add-On

At Gate 4, `writing-plans` requires the plan to account for change size and risk in deciding:

- whether rollback is needed,
- whether phased validation checkpoints are required,
- whether a dependency graph is mandatory.

For the highest-risk areas, it requires explicit rollback strategy:

- auth/authz,
- payment,
- database schema,
- public API,
- concurrency,
- infrastructure.

This is mature design because a plan that only says "how to do it" but never says "how to back out" is difficult to trust in real engineering environments. The migration template is the strongest example of this design: phased rollout, rollback per phase, and validation per phase are required rather than optional.

### 4.5 Mode Depth Is Controlled So Explicitly

The `Lite / Standard / Deep` split is not just about length. Each mode has a different content contract:

- `Lite`: 5-15 line checklist, no code blocks, no reviewer loop,
- `Standard`: full plan document, interface-level code only, mandatory single reviewer round,
- `Deep`: full plan plus dependency graph, phased validation, rollback per phase, and up to 3 reviewer rounds.

This matters because it prevents every plan from drifting toward Deep-style verbosity. Without mode-specific depth rules, a model can easily turn every task into a heavy architecture document, which creates:

- too much documentation overhead,
- diluted attention on low-value details,
- slower transition from planning into execution.

Mode-specific depth control keeps the plan "heavy enough to be safe, light enough to be usable."

### 4.6 Complete Implementation Code Is Explicitly Forbidden

The skill is strict about code level:

- `Lite` has no code blocks,
- `Standard / Deep` require the mandatory code-block labels `[interface]`, `[test-assertion]`, `[command]`, and `[speculative]`; `Deep` may additionally include data-flow sketches, migration SQL, and sequence outlines,
- complete implementation code is explicitly prohibited.

This is critical because full implementation code at plan time creates a dangerous illusion: the plan looks concrete, but the code has neither been compiled nor validated, and often gets rewritten during actual execution.

In the clear-feature evaluation scenario, one of the biggest without-skill failures was exactly this: full config structs, full handler logic, and full token-service code were embedded directly in the plan. With-skill stayed at the interface-and-assertion level instead. That shows the design goal of `writing-plans` is not pre-coding. It is constraining the boundary of what a plan should be.

### 4.7 Every Task Must Carry an Exact Verification Command

`writing-plans` explicitly requires at least one runnable verification command per task and rejects vague language such as "check that it works."

This is important because plan executability does not depend on how elegant the task prose is. It depends on whether the implementer can objectively determine:

- whether the step succeeded,
- whether the command verifies behavior rather than only buildability,
- whether it is a local validation or a broader regression check.

This is also why reviewer-checklist item `SB3` is blocking for Standard / Deep: a command that runs successfully but does not verify the claimed behavior still leaves the plan logically unsound.

### 4.8 The Reviewer Loop Is Mandatory and Separate from Self-Check

After writing the plan, `writing-plans` requires two steps:

1. Self-Check / Format Gate,
2. Reviewer Loop / Substance Gate.

And it explicitly says:

- `Lite` skips the reviewer loop,
- `Standard` must run one reviewer round,
- `Deep` can run up to three rounds,
- reviewer review is not skipped just because the self-check passed.

This is a deep design choice because it acknowledges that format correctness is not the same as logical soundness. The scorecard can catch:

- missing path labels,
- wrong code-block types,
- missing verification commands.

But the reviewer loop catches:

- task ordering that is not causally valid,
- parallel tasks that write the same file,
- commands that run but do not test the claimed behavior,
- plans that silently expand beyond the stated scope.

That is why `references/reviewer-checklist.md` makes `SB1`, `SB3`, and `SB4` blocking for Standard / Deep plans.

### 4.9 Both `SKIP` and Degraded Mode Are First-Class Branches

The skill has two especially mature boundary branches:

- `SKIP`: the task does not need a formal plan,
- Degraded Mode: the repo is inaccessible, so path verification cannot run.

They matter because both prevent the model from pretending everything is normal. Without `SKIP`, docs-only or tiny changes are over-engineered. Without Degraded Mode, path verification failure turns into guesswork.

Both the evaluation and the golden fixtures show that these are not side paths or edge patches. They are part of the main contract of the skill.

### 4.10 The Plan Update Protocol Is Essential

`writing-plans` does not treat the plan as a one-time static artifact. It explicitly requires recording:

- `[Deviation]`,
- planned X -> actual Y,
- reason,
- impact,
- downstream adjustment.

And it classifies deviations into:

- Trivial,
- Significant,
- Breaking.

This has real engineering value because deviation during execution is normal. What matters is whether the team has a shared language for deciding:

- log it and continue,
- adjust downstream tasks,
- stop and replan.

The rule that `>30%` of tasks with significant deviations should trigger plan reassessment is especially important. It turns the plan into a maintainable execution artifact rather than a disposable document.

### 4.11 The Template System Is Core Infrastructure vs. Decoration

`writing-plans` is not a generic planning prompt. It provides plan templates for:

- feature,
- bugfix,
- refactor,
- migration,
- API change,
- docs-only.

Each template hardens the most important sections for that task type. For example:

- feature emphasizes backward compatibility,
- bugfix emphasizes reproduction and regression scope,
- migration emphasizes phased execution, rollback, validation, and lock analysis,
- docs-only is primarily designed for `SKIP` / `Lite` paths.

This solves the problem of all plans taking the same shape regardless of task type. The structure now actually matches the nature of the work.

### 4.12 The Real Increment Is Front-Loaded Planning Governance

The evaluation already shows that the baseline model could do some useful natural-language planning behaviors on its own, especially:

- asking clarifying questions in vague scenarios,
- recognizing in a rough sense that docs-only work should not need a large plan.

The real difference came from the additional structure with-skill provided:

- the 4-Gate flow,
- the four-label path system,
- semantic code-block labels,
- explicit `SKIP / Lite / Standard / Deep` decisions,
- reviewer loop,
- output contract.

That means the core value of `writing-plans` is not simply "better task breakdown." It is better judgment about when planning should happen, how deep the plan should go, and what makes a plan trustworthy enough to execute.

## 5. Problems This Design Solves

Combining the current `SKILL.md`, key references, and the evaluation report, the skill solves the following problems:

| Problem type | Corresponding design | Practical effect |
|--------------|----------------------|------------------|
| A plan is written against vague requirements | Requirements Clarity Gate | Less rework from misunderstandings |
| Small tasks are over-engineered | Applicability Gate + `SKIP/Lite` | Planning cost becomes more proportional |
| Plans contain ghost paths | Repo Discovery Gate + four-label system | File maps become more trustworthy |
| Plans turn into premature implementation | Code Level Rules + anti-examples | Plan boundaries become clearer |
| Risky tasks have no rollback path | Scope & Risk Gate + templates | Execution becomes safer |
| Steps are not objectively verifiable | Mandatory verification commands | Plans become more executable |
| Structure is correct but logic is not | Reviewer Loop | Plans become more robust |
| Execution drift is unmanaged | Plan Update Protocol | Plans stay maintainable during execution |

## 6. Key Highlights

### 6.1 The 4-Gate Front-End Is the Core Structural Backbone

The skill decides whether planning is even justified, whether the request is plannable, whether paths are trustworthy, and how risky the work is before the plan is written.

### 6.2 `SKIP / Lite / Standard / Deep` Routing Is Extremely Practical

Docs-only changes, tiny bugfixes, normal features, and migrations are handled differently instead of being forced through one planning style.

### 6.3 The Four-Label Path System Is Highly Distinctive

It turns plan paths from "plausible-looking" into explicit, auditable path states.

### 6.4 Semantic Code-Block Labels Prevent Plans from Becoming Fake Implementations

`[interface]`, `[test-assertion]`, and `[command]` keep the plan at the right level of detail.

### 6.5 The Reviewer Loop Upgrades the Plan from Formatted to Trustworthy

This is one of the clearest differences between `writing-plans` and ordinary checklist generation.

### 6.6 Its Real Increment Is Planning Governance, Not Generic Decomposition Skill

The evaluation already shows that the baseline model can do some natural question-asking and simple decomposition. The real gap comes from the gates, modes, path discipline, reviewer loop, and output contract. That means the core value of `writing-plans` is planning governance rather than merely "better step lists."

## 7. When to Use It — and When Not To

| Scenario | Suitable | Reason |
|----------|----------|--------|
| Multi-file feature / bugfix / refactor / migration | Very suitable | This is the core use case |
| Cross-module, high-risk, or phased-rollout work | Very suitable | Deep mode is especially valuable |
| Docs-only, config-only, or tiny direct fixes | Often no formal plan needed | These usually route to `SKIP` or `Lite` |
| Single-file, <30-line, <5-minute tasks | Not suitable for formal planning | The Applicability Gate should skip them |
| Repo inaccessible but an execution frame is still needed | Suitable | Degraded Mode exists for this |

## 8. Conclusion

The real strength of `writing-plans` is not that it can break a request into more steps. It is that it systematizes the most failure-prone parts of pre-implementation planning: clarify requirements first, decide whether planning is even justified, verify paths and stack assumptions, choose the appropriate planning mode and risk depth, and then constrain the plan with interface-level code blocks, exact verification commands, a reviewer loop, and a deviation protocol.

From a design perspective, the skill expresses a clear principle: **the key to a high-quality implementation plan is not splitting work into the finest possible granularity, but making sure the plan is grounded in clear requirements and verified paths, that each step can be objectively validated, that risky steps can be rolled back, and that reality has a protocol for changing the plan when execution diverges from it.** That is why it is especially well suited to feature planning, migration planning, and complex bugfix planning.

## 9. Document Maintenance

This document should be updated when:

- the four Gates, Execution Modes, Output Contract, Scorecard, Reviewer Loop, Degraded Mode, or Plan Update Protocol in `skills/writing-plans/SKILL.md` change,
- key rules in `skills/writing-plans/references/requirements-clarity-gate.md`, `applicability-gate.md`, `repo-discovery-protocol.md`, `reviewer-checklist.md`, `plan-update-protocol.md`, `anti-examples.md`, or the plan templates change,
- the core supporting results in `evaluate/writing-plans-skill-eval-report.zh-CN.md` change.

Review quarterly; review immediately if the gate structure, mode routing, path-label system, or reviewer loop of `writing-plans` change substantially.

## 10. Further Reading

- `skills/writing-plans/SKILL.md`
- `skills/writing-plans/references/requirements-clarity-gate.md`
- `skills/writing-plans/references/applicability-gate.md`
- `skills/writing-plans/references/repo-discovery-protocol.md`
- `skills/writing-plans/references/reviewer-checklist.md`
- `skills/writing-plans/references/plan-update-protocol.md`
- `skills/writing-plans/references/anti-examples.md`
- `skills/writing-plans/references/golden-scenarios.md`
- `evaluate/writing-plans-skill-eval-report.zh-CN.md`

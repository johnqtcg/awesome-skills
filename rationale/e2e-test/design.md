---
title: e2e-test skill design rationale
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-27
applicable_versions: current repository version
---

# e2e-test Skill Design Rationale

`e2e-test` is an execution framework for end-to-end testing around critical user journeys. Its core idea is: **an E2E task should first establish which journey is worth covering, whether the current environment is actually runnable, which runner fits the repository, whether the result is strong enough to count as stable, and whether the final deliverable is reusable for the team and CI.** That is why the skill turns task classification, repository fact discovery, environment gating, runner selection, stability validation, side-effect control, and structured delivery into one explicit workflow.

## 1. Definition

`e2e-test` is used for:

- selecting high-value user journeys for E2E coverage,
- creating or updating Playwright tests,
- using Agent Browser for exploration and reproduction,
- handling flaky-test triage,
- designing E2E CI gates,
- using a repository's native test runner in non-JavaScript projects.

Its output is not only test code. It also includes:

- task type and runner-selection rationale,
- environment and configuration status,
- the covered journey or the failure under triage,
- executed commands and execution status,
- artifact locations,
- next actions.

When the result is meant for CI or downstream tooling, it must append a machine-readable JSON summary. If the task generated code, it must also report files created or updated, and for scaffold-only output it must include skip conditions or TODO markers.

## 2. Background and Problems

The main problem this skill solves is not "teams do not know how to write browser scripts." It is that real E2E work usually breaks down in three places at once:

- the testing target is vague, so no one knows which journeys are worth automating;
- the environment and dependencies are incomplete, but the result is still presented as runnable;
- a single passing run is treated as proof of stability, while exploratory findings never become durable assets.

Without a clear framework, failures usually cluster into eight categories:

| Problem | Typical consequence |
|---------|---------------------|
| Every browser task is treated as Playwright code generation | Repositories without Node.js / Playwright get forced into the wrong toolchain |
| Environment, account, and dependency checks never happen first | URLs, users, feature flags, and sandbox assumptions are guessed |
| No execution-integrity discipline | Output reads as if it was run even when it was not |
| A single pass is treated as stability | Flaky defects are incorrectly marked fixed |
| Side effects are not constrained | Tests hit real payments, notifications, or production-like data |
| Exploration and code generation are disconnected | Agent Browser findings never become long-term value |
| Structured delivery is missing | Tests, triage reports, and CI strategies are hard to compare or review |
| Playwright-specific detail is over-applied | Non-JS repositories inherit irrelevant context and decision noise |

The design logic of `e2e-test` is to answer "is this worth doing, can it be done safely, and what is the right way to do it?" before deciding what code or report should be produced.

## 3. Comparison with Common Alternatives

Before looking at the internals, it helps to compare the skill with a few common alternatives:

| Dimension | `e2e-test` skill | Asking a model to "write an E2E test" | Manual exploration or ad hoc scripts |
|-----------|------------------|---------------------------------------|--------------------------------------|
| Journey-value selection | Strong | Weak | Weak |
| Environment / config gating | Strong | Weak | Weak |
| Runner selection and degradation | Strong | Weak | Weak |
| Execution integrity | Strong | Weak | Weak |
| Stability proof | Strong | Weak | Weak |
| Side-effect control | Strong | Weak | Weak |
| Exploration-to-code bridge | Strong | Medium | Weak |
| Structured delivery | Strong | Weak | Weak |
| CI integration friendliness | Strong | Medium | Weak |

Its value is not only that it can produce tests. Its value is that it turns E2E work into an auditable, reusable, governable engineering process.

## 4. Core Design Rationale

### 4.1 It Classifies the Task Before Writing Code

The first step in the Operating Model is to classify the task:

- new journey coverage,
- flaky triage,
- failed CI investigation,
- exploratory browser reproduction,
- test architecture or CI gate design.

This matters because these tasks may all be called "E2E," but they serve very different goals.

- New journey coverage emphasizes maintainable code.
- Flaky triage emphasizes reproduction, classification, fix, and quarantine decisions.
- CI gate design emphasizes triggers, artifacts, secrets, and execution tiers.
- Exploratory reproduction emphasizes quickly finding the real user path and stable selectors.

Without explicit classification, tool choice, output shape, and quality expectations all get mixed together.

### 4.2 Repository Fact Discovery Comes Before Judgment

The skill requires `scripts/discover_e2e_needs.sh` before gate decisions, so it can detect:

- whether Playwright is installed,
- Node.js and framework signals,
- whether the repo contains a Go web service and existing E2E tests,
- environment files, dev-server commands, CI platform, and related tooling.

This is important because one of the most common E2E mistakes is making assumptions about the repository. Scripted discovery matters because it:

- turns repository state into evidence before runner and gate choices,
- makes the rationale reproducible instead of situational,
- prevents the whole workflow from starting on a false premise.

That is one of the clearest ways the skill goes beyond a prompt that merely says "inspect the repo first."

### 4.3 Agent Browser and Playwright Form a Dual-Runner Model

`e2e-test` does not treat Agent Browser and Playwright as interchangeable. It separates them intentionally:

- Agent Browser is preferred for exploration, reproduction, screenshots, and understanding real interactions.
- Playwright is preferred for committed, repeatable, CI-ready automated coverage.

That is a strong design choice because real E2E work usually has two phases:

- first understand how the user journey actually behaves and where it breaks,
- then convert that validated understanding into durable code.

If the workflow starts directly in Playwright, it often writes code before understanding the real page behavior. If it stays only in Agent Browser, the knowledge stays ephemeral. The dual-runner model connects discovery and durable automation instead of forcing one tool to do both jobs badly.

### 4.4 It Supports Native Runners vs. Forcing Playwright Everywhere

Even though `e2e-test` prefers Playwright for maintainable browser automation, it explicitly states that non-JS projects should use the repository's native test framework rather than installing Playwright just to fit the skill.

This was central in the evaluation: when faced with a pure Go web project, the skill correctly chose the Go HTTP client path instead of generating Playwright by default.

That shows the skill is not trying to promote one tool. It is trying to produce the strongest deliverable the current environment can honestly support. This makes it much more engineering-oriented than a generic "Playwright-style" prompt.

### 4.5 Configuration Gate and Environment Gate Must Come Early

The first two Mandatory Gates solve two different problems:

- the Configuration Gate checks variables, accounts, feature flags, and dependencies;
- the Environment Gate checks whether local, preview, staging, or CI is actually runnable.

These gates cannot be merged or deferred, because:

- having configuration does not mean the environment is safe or ready,
- having an environment does not mean accounts and dependencies are available,
- either kind of ambiguity makes any later "runnable test" claim unreliable.

The skill is explicit here: if required values are missing, do not guess them. Produce a guarded scaffold with `test.skip` and TODO markers when that is still useful, or stop and report the blockers.

### 4.6 Execution Integrity Is a Hard Requirement in E2E Work

`e2e-test` requires the output to say `Not run in this environment` when nothing actually ran, together with the reason and the next commands. If something did run, it must report:

- the command,
- the target environment,
- the pass/fail status,
- the artifact locations.

This is especially important in E2E work because it is easy for readers to confuse three very different states:

- code was generated,
- tests were executed,
- stability was actually validated.

The skill's Execution Integrity Gate keeps those states separate. That is one of its most important design contributions.

### 4.7 The Stability Gate Explicitly Rejects "One Pass = Stable"

The Stability Gate states that a single pass is not proof of reliability for critical journeys or flaky failures. It requires repeat runs, traces, screenshots, and environment evidence before concluding:

- the bug is fixed,
- the test is stable,
- the failure is only infrastructure-related.

This is especially important in flaky triage. The evaluation report also shows that flaky triage is where the skill adds the most value, because it does not merely identify a likely root cause. It requires a full sequence:

- reproduce,
- classify,
- fix,
- quarantine only with an owner, tracking issue, and removal deadline when needed.

So the skill contributes a triage methodology, not just a list of repair ideas.

### 4.8 The Side-Effect Gate Must Remain Separate

E2E tests naturally touch real-world side effects, such as:

- creating or mutating real records,
- triggering payments,
- sending notifications,
- crossing irreversible workflow boundaries.

That is why `e2e-test` keeps the Side-Effect Gate as a separate mandatory layer. The default posture is safe behavior, with destructive operations requiring explicit approval or isolation.

This is crucial because E2E work is much closer to real system behavior than unit testing. Without an explicit side-effect gate, "test automation" can cross directly into "real operation."

### 4.9 The Agent Browser Bridge Is an Explicit Rule

`e2e-test` does not treat Agent Browser as a one-off helper. It explicitly requires bridge steps:

- record the environment and entry URL,
- record the command sequence,
- save milestone screenshots,
- identify stable selectors or semantic targets,
- translate the validated flow into Playwright assertions and helpers.

This is valuable because the common failure in exploratory work is not inability to find the issue. It is inability to preserve what was learned in a structured way. The bridge solves a knowledge-transfer problem: it turns exploration into maintainable automation assets.

### 4.10 References Are Loaded Selectively by Scenario

The reference structure in `e2e-test` is very intentional:

- `checklists.md` and `environment-and-dependency-gates.md` are always loaded,
- Playwright-only references are loaded only for JS / Playwright projects,
- Agent Browser workflows are loaded only when browser exploration is involved,
- `golden-examples.md` is loaded when shaping reports or triaging flakes.

This is a strong design choice because the skill covers a broad range of E2E work. If every Playwright detail, Agent Browser workflow, and golden example were loaded every time, two things would happen:

- irrelevant detail would drown non-matching repositories,
- the highest-value gate and decision rules would lose salience.

Selective loading allows the skill to stay broad without turning simple scenarios into context-heavy noise.

### 4.11 The Quality Scorecard Is a Governance Interface, Not Decoration

The Quality Scorecard splits quality into `Critical`, `Standard`, and `Hygiene`, and it explicitly allows Playwright-specific items to be marked `N/A` for non-Playwright runners.

That is a mature design for three reasons:

- it turns "what good E2E work looks like" into a reviewable checklist,
- it avoids incorrectly punishing non-JS projects with Playwright-only criteria,
- it integrates naturally with CI, review, and triage workflows.

Because of this, the skill is useful not only for generating tests, but also for E2E governance.

### 4.12 Output Contract for Humans and Tooling

The Output Contract always requires 9 human-readable fields, and machine-readable JSON must be appended when the result is meant for CI or downstream tooling. If code was generated, the output must also include files created or updated, plus skip conditions or TODO markers for scaffold-only results.

Those two layers serve different needs:

- for humans, structured output answers "what is the current state, what is missing, and what should happen next?";
- for automation, JSON answers "can this result be consumed directly by pipelines, reporting, or governance systems?"

The evaluation report makes this difference very clear: the base model could still produce good content, but without standardized structure or JSON summaries it could not provide the same cross-task governance value.

## 5. Problems This Design Solves

Combining the current `SKILL.md`, references, and evaluation report, the skill addresses the following engineering problems:

| Problem type | Corresponding design | Practical effect |
|--------------|----------------------|------------------|
| E2E task types get mixed together | Task classification | Switches among coverage, triage, CI design, or exploratory reproduction paths |
| The wrong runner is chosen | Discovery script + Runner Selection Guidance | Uses repository facts to choose Playwright, Agent Browser, or a native runner |
| Missing config is presented as runnable | Configuration Gate | Produces runnable tests, guarded scaffolds, or blockers honestly |
| Environment readiness is vague | Environment Gate | Separates local / preview / staging / CI decisions and stop conditions |
| Output sounds executed when it was not | Execution Integrity Gate | Distinguishes generated, executed, and validated states |
| One passing run is treated as enough | Stability Gate + Flaky Test Policy | Adds repeat runs, traces, and quarantine discipline |
| Real-world side effects are ignored | Side-Effect Gate | Constrains destructive and irreversible flows |
| Exploration does not become durable code | Agent Browser Bridge | Converts exploratory findings into maintainable automation |
| Reports are hard to compare or automate | Output Contract + optional JSON | Supports both team collaboration and CI/tooling consumers |

## 6. Key Highlights

### 6.1 It Turns E2E Work into a Full Execution Framework

The center of `e2e-test` is not one testing library. It is the end-to-end workflow connecting journey selection, runner choice, environment readiness, stability proof, and final delivery.

### 6.2 It Handles Environment Adaptation and Honest Degradation Well

It does not assume that every E2E task should end in Playwright. It requires repository facts first, and then produces the strongest result the environment can actually support.

### 6.3 It Is Especially Strong for Flaky Triage

The evaluation shows its largest advantage in flaky triage, because the skill does not stop at analysis. It requires the standard reproduce, classify, fix, and quarantine sequence together with stability validation.

### 6.4 It Balances Exploration Speed with Long-Term Maintainability

Agent Browser handles fast exploration and reproduction. Playwright or the repository's native framework handles durable committed code. That division prevents exploratory learning from staying trapped in one-off sessions.

### 6.5 Its Structured Output Fits Test Governance Naturally

Task type, runner choice, environment gate, config status, executed commands, artifacts, next actions, plus required JSON in CI / tooling contexts and file/skip metadata when code is generated together create a shape that is easy for teams to review, for CI to consume, and for governance systems to summarize.

### 6.6 Selective Loading Keeps a Large Skill Practical

`e2e-test` has a large reference surface, but it avoids mandatory full loading. The "always load + scenario-specific load" pattern is one of the reasons a complex skill like this can stay useful in day-to-day work.

## 7. When to Use It — and When Not To

| Scenario | Suitable | Reason |
|----------|----------|--------|
| Automating critical user journeys | Yes | This is the core use case |
| Flaky test triage | Yes | This is where the skill adds the most value |
| Designing E2E CI gates | Yes | Structured output, artifacts, and execution tiers fit well |
| Exploring first, then converting to durable automation | Yes | Agent Browser Bridge is designed for this |
| E2E work in non-JS web projects | Yes | It supports native runners and honest degradation |
| Purely visual design review | No | That is outside automated journey value |
| Load or performance testing | No | That is not the skill's purpose |
| Work that requires guessed private accounts, secrets, or endpoints | No | The skill explicitly forbids that behavior |

## 8. Conclusion

The real strength of `e2e-test` is not that it prefers Playwright or knows how to use Agent Browser. It is that it systematizes the parts of end-to-end testing most likely to become unreliable: classify the task first, collect repository facts through discovery, run configuration, environment, execution-integrity, stability, and side-effect gates, choose the right runner, and then deliver the result in a structure that works for both humans and systems.

From a design perspective, the skill embodies a very clear principle: **the value of E2E work is not only that a journey was covered, but that the coverage is real, the judgment is honest, the result is reusable, and failures can be governed.** That is why it is especially well suited to critical journeys, flaky triage, and CI gate design.

## 9. Document Maintenance

This document should be updated when:

- the runner strategy, Mandatory Gates, Output Contract, Quality Scorecard, or CI Strategy in `skills/e2e-test/SKILL.md` change,
- key rules in `skills/e2e-test/references/checklists.md`, `environment-and-dependency-gates.md`, `agent-browser-workflows.md`, `golden-examples.md`, or the Playwright references change,
- the detected fields, verdict logic, or report shape in `skills/e2e-test/scripts/discover_e2e_needs.sh` change,
- key supporting conclusions in `evaluate/e2e-test-skill-eval-report.md` change,
- the skill is materially refactored around runner adaptation or output structure.

Review quarterly; review immediately if the gates, runner strategy, or discovery script of `e2e-test` changes substantially.

## 10. Further Reading

- `skills/e2e-test/SKILL.md`
- `skills/e2e-test/references/checklists.md`
- `skills/e2e-test/references/environment-and-dependency-gates.md`
- `skills/e2e-test/references/golden-examples.md`
- `skills/e2e-test/references/agent-browser-workflows.md`
- `skills/e2e-test/references/playwright-patterns.md`
- `skills/e2e-test/references/playwright-deep-patterns.md`
- `skills/e2e-test/scripts/discover_e2e_needs.sh`
- `evaluate/e2e-test-skill-eval-report.md`

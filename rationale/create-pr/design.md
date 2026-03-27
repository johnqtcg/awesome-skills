---
title: create-pr skill design rationale
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-26
applicable_versions: current repository version
---

# create-pr Skill Design Rationale

`create-pr` is a delivery framework for opening pull requests to the main branch. Its core idea is: **before a change enters team review, branch convention and sync checks, quality evidence, security risk, compatibility notes, and delivery state should already be made explicit.** That is why the skill turns authentication checks, branch sync, risk classification, quality verification, security scanning, documentation checks, commit hygiene, and PR content into a fixed process.

## 1. Definition

`create-pr` is a structured delivery skill for opening PRs to the main branch. It requires a series of mandatory Gates to run before PR creation, uses a standardized PR title and PR body template to organize the result, and only then decides whether the PR should be `draft` or `ready`. Its output includes a PR URL together with a delivery report containing Gate outcomes, uncovered risks, PR metadata, and next actions.

## 2. Background and Problems

The skill addresses a common PR-delivery problem: many PRs enter team review with major uncertainty already embedded in them, but that uncertainty is never written down explicitly.

Without a clear process, problems usually cluster into six categories:

| Problem | Typical consequence |
|---------|---------------------|
| Branch convention and sync checks are missing | PR opened from `main`, branch is behind, working tree is dirty, or conflict markers remain |
| Quality evidence is incomplete | Tests, lint, or build were never run, or were run without leaving visible evidence in the PR |
| Security checks are skipped | Secrets, credentials, vulnerable dependencies, or high-confidence security findings enter review unnoticed |
| Documentation and compatibility notes are missing | Reviewers cannot tell whether behavior changed, whether the change is breaking, or how to roll it back |
| Draft / ready is decided by feel | A PR with large verification gaps is still marked ready |
| PR content is poorly organized | Title is inconsistent, body misses critical sections, and risk/evidence are scattered |

The design goal of `create-pr` is to move these "open it first, explain later" failures forward into explicit Gates, each with a checkable conclusion.

## 3. Comparison with Common Alternatives

Before looking at the details, it helps to compare the skill with a few common alternatives:

| Dimension | `create-pr` skill | Manually using `gh pr create` | Relying on CI / reviewers to catch everything |
|-----------|-------------------|-------------------------------|----------------------------------------------|
| Repository preflight before PR creation | Strong | Weak | Weak |
| Branch convention and sync checks | Strong | Weak | Weak |
| Explicit quality evidence | Strong | Medium | Weak |
| Security scanning | Strong | Weak | Medium |
| Draft / ready decision quality | Strong | Weak | Weak |
| PR body structure | Strong | Weak | Weak |
| Risk and rollback communication | Strong | Medium | Weak |
| Reviewer friendliness | Strong | Medium | Weak |

The skill does not replace CI, code review, or GitHub itself. It standardizes what should already be true *before* a PR enters review.

## 4. Core Design Rationale

### 4.1 It Uses a Fixed Process vs. Free-Form Execution

`create-pr` fixes the overall workflow into thirteen steps and breaks the most important parts into Gates A through H. This is necessary because PR creation is a step that both humans and models tend to underestimate.

It is easy to think: "the code is already done; opening the PR is just the last small step." But the quality of team review often depends on whether this "last step" was handled properly:

- Is the branch actually synced to the latest `origin/main`?
- Were the checks really run?
- Is security clean, or was it never checked?
- Is this a low-risk patch or a high-risk change touching auth, migrations, concurrency, or public APIs?
- Should this PR really be `ready`, or should it still be `draft`?

The fixed process turns these easily skipped judgments into a delivery chain that is clear, reviewable, and much less dependent on ad hoc improvisation.

### 4.2 Authentication and Repository Preflight Come First

Gate A checks GitHub authentication, remote setup, default branch information, permissions, and branch protection status.

The point is not technical complexity. The point is to avoid pushing the rest of the workflow forward when the basic operating assumptions are wrong. For example:

- `gh` is not logged in, but the author is already drafting a PR body.
- The remote does not actually use `main`, so every later comparison target is wrong.
- The current account does not have permission, so PR creation cannot succeed.
- Branch protection status cannot be queried and needs to be recorded as an uncovered gap.

These are not code problems, but if the premise is wrong, the rest of the Gates may no longer mean anything. That is why this step is placed first and treated as a blocker.

### 4.3 Branch Convention and Sync Checks Get Their Own Gate

Gate B is dedicated to branch health: the PR must not come from `main`, the working tree must be clean, conflict markers must be absent, the branch must include the latest `origin/main`, and branch naming should be checked for convention.

This is an important layer in `create-pr`, because many PR problems are not implementation defects at all. The branch itself is not in a reviewable state. Examples include:

- Opening a PR from a dirty working tree, so local-only edits are mixed with committed changes.
- Letting the branch drift far behind main, so reviewers see a stale integration context.
- Using a branch name that no longer reflects the actual change, making later tracking harder.
- Leaving conflict markers in files for CI or reviewers to discover later.

Moving these checks into Gate B means the skill first verifies whether the branch is fit to become a review object.

### 4.4 It Classifies Change Risk vs. Only Listing the Diff

Gate C does more than list changed files. It identifies high-risk areas and classifies the PR by total changed lines:

- `≤ 400` lines: normal
- `401–800` lines: warning; consider splitting
- `> 800` lines: strong warning unless the change is inherently atomic

This solves a very practical review problem: **not every PR deserves the same review expectation.**

Two PRs may both be "a pull request," but they are not equal:

- A small patch may mainly need correctness and regression review.
- A small but high-risk change touching auth, payment, migration, concurrency, public APIs, or infra config needs much clearer risk and rollback notes.
- A huge PR may still be logically correct, but review quality itself becomes weaker as change size grows.

So `create-pr` does not treat the diff as a display artifact. It treats the diff as an input that determines how much explanation and caution the PR should carry.

### 4.5 Quality Evidence Must Be Explicitly Recorded

Gate D requires project-standard checks to run first, with fallback to language defaults, and it requires the exact commands and pass/fail results to be recorded.

The design principle here is straightforward: **if something was not run, the PR must not read as though it was verified.**

This solves two common failures:

- The PR says "tested," but no one knows what was actually run.
- Commands failed in a terminal, but the PR body contains no visible trace of that fact.

The skill is not asking only for checks to run. It is asking for check results to be converted into evidence a reviewer can directly consume.

### 4.6 Security Checking Is Its Own Gate and Multi-Tool Validation Matters

Gate E groups filename risk scans, content risk scans, and Go-specific tools such as `gosec` and `govulncheck`.

This is one of `create-pr`'s strongest design choices. A PR is the last point before risky code enters shared team attention. If a high-confidence security issue is not stopped here, then by the time a reviewer catches it, team time has already been wasted.

Scenario 3 in the evaluation report makes this concrete: with-skill did not merely notice a hardcoded `ghp_` token. It built a stronger evidence chain through regex scanning and tooling, and explicitly advised against pushing or creating the PR. Without the skill, the issue could still be recognized, but the result looked more like a normal review comment than a formal blocking security conclusion.

This design improves:

- discovery of high-risk issues,
- clarity around whether the issue is confirmed or merely suspicious,
- the evidence basis for draft / ready decisions.

### 4.7 Documentation and Compatibility Must Be Clear Before Review Starts

Gate F checks whether docs, README, or changelog updates are needed, and requires compatibility and breaking-change implications to be made explicit.

This rule corrects a common misunderstanding: many teams treat documentation updates and compatibility notes as something to clean up after merge, but reviewers often need that information *during* review:

- Does this change alter external behavior?
- Is there migration cost?
- If rollout fails, how do we roll back?
- If the change is breaking, what exactly is affected?

Without this information, reviewers see only a code diff, not a complete delivery unit. Gate F makes clear that a PR is not just code for review. It is also a change explanation for review.

### 4.8 Commit Hygiene and PR Title Are Checked Together

Gate G checks both the commit set and the PR title, and requires both to follow Conventional Commits. It especially enforces:

- `<type>(<scope>): <subject>` formatting,
- subject length of at most 50 characters,
- imperative mood, no trailing period.

This has a very practical reason: in many teams, squash merge turns the PR title into the final commit message on `main`. If the PR title is left uncontrolled, the team can care deeply about commit quality beforehand and still end up with poor main-branch history.

So the skill effectively extends commit hygiene from the commit level to the PR level. It prevents situations such as:

- commits are acceptable, but the PR title is vague or sloppy,
- unrelated commits are mixed into the range,
- reviewers have to infer what the PR should have been called.

### 4.9 It Introduces a `confirmed / likely / suspected` Confidence Model

One of the most important parts of `create-pr` is that it does not jump directly to a binary `draft` vs `ready`. It first assigns one of three confidence levels:

- `confirmed`
- `likely`
- `suspected`

and then uses that intermediate layer to decide the PR state.

This matters because real PR states are not always binary:

- Some PRs have all major Gates executed and passed. They can confidently be marked ready.
- Some PRs are almost ready but still have one non-blocking gap.
- Some PRs have multiple unverified Gates or unresolved high-risk issues and clearly should stay draft.

Without a confidence layer, the process easily collapses into subjective judgment: "it probably looks fine; let us mark it ready." With confidence, draft / ready becomes an evidence-based conclusion instead of a mood.

### 4.10 The PR Body Structure Is Fixed

`create-pr` requires the PR body to contain at least eight sections:

1. Problem/Context
2. What Changed
3. Why This Approach
4. Risk and Rollback Plan
5. Test Evidence
6. Security Notes
7. Breaking Changes / Migration Notes
8. Reviewer Checklist

This is not about making PR descriptions longer. It is about making information predictable. Reviewers should be able to find a known type of information in a known location.

The design problem it solves is not "can someone write a PR description?" It is "does the PR description support a high-quality review?" It groups the exact categories reviewers care about:

- the background,
- what changed,
- why it changed that way,
- where the risk is,
- what was tested,
- whether security concerns exist,
- whether the change is breaking,
- what reviewers should pay special attention to.

The evaluation report shows that this is one of the largest gaps between with-skill and without-skill output. Without the skill, descriptions may still be readable, but they often omit risk, rollback, security, or compatibility sections that heavily affect review quality.

### 4.11 Post-Create Verification Is Still Worth Keeping

Gate H verifies after the PR is created that:

- the base is really `main`,
- the head is really the current branch,
- the title and body rendered correctly,
- the draft / ready state matches the actual Gate results.

Many workflows stop once `gh pr create` succeeds. `create-pr` prefers one more verification pass, because successful creation is not the same as correct creation:

- the base branch may be wrong,
- the title or body may render incorrectly because of escaping or formatting,
- a PR that should be draft may end up ready.

It is worth noting that Gate H is softer than Gates A-G: in the quick reference it is marked informational, and `gh pr checks` is explicitly optional and non-blocking. Its purpose is to give the delivery a final consistency check between the intended result and the actual result, not to introduce a whole new class of hard blockers after PR creation.

### 4.12 Required `Uncovered Risk List`

The skill does not allow unverifiable areas to pass silently. It requires them to be listed explicitly in `Uncovered Risk List`.

This is essential because real projects are not always in an ideal state:

- a tool may not be installed,
- branch protection status may be unavailable,
- a test environment may not be runnable at the moment,
- an equivalent upstream control may exist, but local direct evidence may still be missing.

Without `Uncovered Risk List`, these gaps either disappear or get buried in free-form prose. Once they are explicit, the team can actually discuss:

- whether the risk is acceptable,
- who owns the follow-up,
- why the PR should or should not be marked ready before the gap is closed.

## 5. Problems This Design Addresses

Cross-referencing `SKILL.md` and the evaluation report, the skill mainly addresses the following engineering problems:

| Problem | Corresponding design | Practical effect |
|---------|----------------------|------------------|
| PR creation starts from false assumptions | Gate A authentication and repository preflight | Prevents continuing from the wrong repo state or permission context |
| Branch state is not reviewable | Gate B branch convention and sync checks | Prevents dirty trees, stale branches, and unresolved conflicts from entering review |
| Review burden does not match change size | Gate C risk classification and line-count tiers | Helps the team decide whether splitting or extra explanation is needed |
| Quality verification has no visible evidence | Gate D quality evidence recording | Reviewers can directly see what was run and what passed or failed |
| High-confidence security issues enter review | Gate E multi-tool security scanning | Stops risky changes before they consume reviewer time |
| Documentation and compatibility context is missing | Gate F docs and compatibility checks | Reviewers can understand external impact and rollback expectations |
| Commit history and squash result drift apart | Gate G commit hygiene + PR title rules | Keeps main-branch history aligned with PR intent |
| Draft / ready is decided by intuition | Confidence model + Gate-driven decision | Makes PR state evidence-based rather than subjective |
| The created PR can still be wrong after success | Gate H post-create verification | Ensures the created result matches the intended one |
| Verification gaps disappear silently | `Uncovered Risk List` | Makes residual risk visible, assignable, and trackable |

The evaluation data supports this clearly: `create-pr` passed all 34 assertions across 3 scenarios, while without-skill strict pass rate was only `29%`; even on the 12 substantive checks that do not depend on flow-structure assertions, with-skill was `100%` and without-skill only `58%`. So the value is not just "better organization." It is **a major increase in completeness and reliability at the PR creation stage.**

## 6. Key Highlights

### 6.1 It Turns "Opening a PR" into a Delivery Process

This is the skill's central strength. It does not treat PR creation as a final click. It treats it as a formal delivery action before team review begins.

### 6.2 It Uses Gates to Lock Down the Steps Most Commonly Skipped

Many baseline behaviors can perform some of these checks part of the time. The advantage of `create-pr` is not that any single rule is magical. It is that auth, branch convention and sync checks, quality evidence, security, documentation, commit hygiene, and post-create verification are connected into one reliable chain.

### 6.3 The Confidence Model Reduces State Misclassification

The `confirmed / likely / suspected` layer is especially valuable. It prevents `draft` / `ready` from collapsing into a rough binary switch and instead turns state into a conclusion with an evidence gradient.

### 6.4 It Prepares the Information Reviewers Actually Need

The fixed PR body and output contract both serve the same purpose: reducing reviewer comprehension cost. Reviewers do not have to hunt through prose to answer:

- why this change exists,
- what changed,
- where the risk is,
- what was tested,
- what remains uncovered.

The structure puts those answers in predictable places.

### 6.5 It Adds the Most Value Where the Baseline Is Weakest

The evaluation report gives `create-pr` the largest pass-rate delta of the evaluated skills (`+71 pp`). That is a strong signal that PR creation is not a naturally strong area for the baseline model and benefits heavily from a dedicated structured workflow.

## 7. When to Use It — and When Not To

| Scenario | Suitable | Reason |
|----------|----------|--------|
| Opening a formal PR to `main` | Yes | This is the core use case |
| Changes touching security, migrations, concurrency, public APIs, or infra config | Especially yes | Risk classification, Gate flow, and body structure materially improve delivery quality |
| Team uses squash merge | Especially yes | PR title quality directly affects the final main-branch commit |
| You only want a quick incomplete draft link and do not care about evidence or explanation | Not really | That runs against the skill's design goal |
| The task is writing code, fixing a bug, or reviewing code | No | Those belong to other skills or workflows |

## 8. Conclusion

The real strength of `create-pr` is not that it can call `gh pr create`. It is that it systematizes the decisions around PR creation that are easiest to skip or handle by feel. Through its Gates, it turns repository assumptions, branch convention and sync checks, quality evidence, security checks, compatibility notes, commit discipline, PR structure, and final state into a checkable delivery loop.

From a design perspective, the skill is a clear example of production-grade delivery principles: **confirm the operating assumptions first, then organize the review material; make the risks explicit before asking others to review; state what is verified and what is still uncovered before deciding whether the PR is ready.** That is why it creates such a large quality gain in a workflow area where the baseline model is especially weak.

## 9. Document Maintenance

This document should be updated when:

- the Gate flow, confidence model, non-negotiables, or output format in `skills/create-pr/SKILL.md` changes,
- the PR template, checklists, or configuration examples in `skills/create-pr/references/*.md` change,
- key data in `evaluate/create-pr-skill-eval-report.md` that supports the claims here changes,
- the project's conventions around PRs to main, PR title rules, breaking-change disclosure, or rollout / rollback expectations change.

Review quarterly; review immediately if the `create-pr` skill undergoes substantial refactoring.

## 10. Further Reading

- `skills/create-pr/SKILL.md`
- `skills/create-pr/references/pr-body-template.md`
- `skills/create-pr/references/create-pr-checklists.md`
- `skills/create-pr/references/create-pr-config.example.yaml`
- `skills/create-pr/references/merge-strategy-guide.md`
- `skills/create-pr/references/bundled-script-guide.md`
- `evaluate/create-pr-skill-eval-report.md`

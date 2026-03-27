---
title: go-code-reviewer skill design rationale
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-27
applicable_versions: current repository version
---

# go-code-reviewer Skill Design Rationale

`go-code-reviewer` is a structured review framework for Go code. Its core idea is: **code review should reliably surface the issues most likely to cause breakage, regressions, or team coordination costs, and deliver them in a form the team can act on.** That is why the skill combines defect-first review, mandatory gates, selective reference loading, origin classification, and Residual Risk in one workflow.

## 1. Definition

`go-code-reviewer` is a defect-first review skill for Go code and PRs. It first determines review mode and scope, then organizes the review around repository policy, Go version, diff boundaries, and risk signals, and finally outputs a structured review result. That result includes findings, Suppressed Items, Execution Status, Risk Acceptance / SLA, Residual Risk / Testing Gaps, and a concise Summary.

## 2. Background and Problems

The skill is not solving "nobody knows how to review Go code." It is solving "many reviews are either too shallow, too noisy, or mix legacy debt with the current change."

Without a clear review framework, problems usually fall into six categories:

| Problem | Typical consequence |
|---------|---------------------|
| Review depends too much on individual reviewer habits | The same type of issue is judged differently by different reviewers |
| Review scope drifts out of control | A change to one interface turns into a full-file audit full of noise |
| Too many false positives | Developers cannot tell which comments are real defects and which are just reviewer preference |
| Historical issues are mixed with the current change | Authors get blocked by problems they did not introduce |
| Review depth does not match risk | Small changes get over-reviewed, while high-risk changes are reviewed too lightly |
| Output is not actionable | Review comments exist, but they lack severity, evidence, next actions, or timelines |

The design goal is to break these distortions into explicit steps: calibrate the review mode first, bound the scope, gather evidence, and then produce results that are classified, sourced, and actionable.

## 3. Comparison with Common Alternatives

Before looking at the details, it helps to compare the skill with a few common alternatives:

| Dimension | `go-code-reviewer` skill | Generic model doing a direct review | lint / test only |
|-----------|--------------------------|-------------------------------------|------------------|
| Defect-first focus | Strong | Medium | Weak |
| Risk-calibrated depth | Strong | Weak | Weak |
| False-positive suppression | Strong | Weak | Medium |
| Separation of legacy debt from current change | Strong | Weak | Weak |
| Impact-radius expansion | Strong | Weak | Weak |
| Domain knowledge loaded on demand | Strong | Weak | Weak |
| Actionability of output | Strong | Medium | Weak |
| Team collaboration friendliness | Strong | Medium | Weak |

The skill is not a replacement for `golangci-lint`, `go vet`, or `go test`. It turns their signals, together with code context, project rules, and reviewer judgment, into a review result that is easier for a team to use.

## 4. Core Design Rationale

### 4.1 It Is Defect-First vs. Style-First

`go-code-reviewer` states its purpose clearly from the beginning: the review should focus on **real defects, regression risks, and deviations from project policy**, not generic style commentary.

That choice comes from two observations:

1. In real engineering work, the most expensive problems are usually not naming preferences but races, resource leaks, compatibility breaks, misleading error handling, and broken database or API behavior.
2. If review is constantly filled with low-value style comments, developers start treating review as noise, and the high-risk issues lose attention.

So the goal is not "say as many things as possible." The goal is "surface the issues most worth fixing."

### 4.2 Review Mode Is Selected Up Front

Before the actual review starts, `go-code-reviewer` chooses one of three modes: `Lite`, `Standard`, or `Strict`, and requires the result to state both the selected mode and the reason.

This aligns review depth with risk:

| Mode | Typical use | Design purpose |
|------|-------------|----------------|
| `Lite` | Small, low-risk changes | Quickly surface high-confidence defects without turning a small change into a large process |
| `Standard` | Most day-to-day PRs | Balance depth, speed, and review cost |
| `Strict` | Security, concurrency, public API, or broad refactors | Expand impact radius and demand stronger verification and reporting |

Without this step, review tends to fail in two opposite ways: simple changes get over-reviewed, while risky changes receive only a surface pass. Mode selection solves the basic question of where review effort should go.

### 4.3 Execution Integrity Is the First Gate

The first Mandatory Review Gate is the Execution Integrity Gate: **if verification was not run, the review must not speak as though it was run**.

This sounds simple, but it is foundational. A common review failure is not incorrect reasoning, but confident language built on missing evidence. For example:

- `go test` was not run, but the review sounds as if test health is known.
- `go test -race` was not run, but the review implies concurrency safety has been checked.
- No linter environment is available, but the review reads as if lint has effectively passed.

This gate matters because it:

- keeps inference separate from execution,
- gives the result a clear confidence boundary,
- prevents teams from treating strongly worded but weakly verified review output as fact.

In other words, the skill protects the credibility of the result before it tries to improve the result itself.

### 4.4 Baseline Comparison Is Preserved

The second Mandatory Review Gate is the Baseline Comparison Gate. When prior review context exists, each finding must be classified as `new`, `regressed`, `unchanged`, or `resolved`; if no baseline exists, the review must explicitly say `Baseline not found`.

This rule is easy to overlook because many reviews answer only one question: "is there a problem here?" But teams usually need two more answers:

- Is this issue newly introduced, or did it already exist?
- Compared with the previous review state, is the code getting better, getting worse, or staying the same?

Baseline comparison increases the information value of the review:

- `new` means the issue is introduced by the current change.
- `regressed` means something that used to be fixed or controlled has come back.
- `unchanged` means a known issue still exists, but its status has not changed.
- `resolved` helps the team confirm that previously known issues have actually been removed.

The point is not to make the output more complex. The point is to place a review back into the project's ongoing history instead of treating every review as an isolated snapshot.

### 4.5 False-Positive Suppression Is a Mandatory Gate

The third Mandatory Review Gate is the False-Positive Suppression Gate. Before reporting a finding, the reviewer must check whether the risk is already blocked by an upstream guard, middleware, constrained input path, or runtime guarantee.

This is one of the skill's most important design choices, because it directly determines whether the result has signal.

The evaluation report makes this concrete: across four subtle scenarios, the with-skill false-positive rate was `0/19`, while without-skill was about `5/32`, and signal-to-noise improved from `53%` to `89%`. So the value is not just "better structure." It is **finding the same real problems while reporting far fewer unnecessary ones**.

This design addresses two common failures:

- Without a suppression mechanism, review fills up with "this could theoretically be risky" comments that are not actually risky in context.
- Without a suppression record, readers cannot tell the difference between "intentionally filtered out" and "not noticed."

That is why the skill requires more than suppression. It requires suppressed items to be recorded with rationale, so the team knows what was filtered and why.

### 4.6 There Is a Risk Acceptance and SLA Gate

The fourth Mandatory Review Gate establishes that every unresolved finding must carry a recommended resolution timeline (SLA), and — when an immediate fix is not chosen — a structured risk acceptance entry.

This gate addresses a practical gap in most code review workflows: a finding lands in a comment thread, the author acknowledges it, and then nothing is explicitly recorded about when it will be resolved or who is accountable. The issue slowly disappears from visibility.

The SLA structure is deliberately simple:

- `High`: fix or strong mitigation within 3 business days
- `Medium`: fix within 14 calendar days
- `Low`: addressed in the next planned iteration

The risk acceptance entry — with fields for owner, justification, compensating controls, and expiry date — is not bureaucratic overhead. Its purpose is to make deferral a **visible and accountable decision**, not a silent one. When a team decides not to fix something immediately, that decision should be:

- stated explicitly, with the reasoning written down,
- attributed to a named owner,
- given a review date, so the open issue cannot remain open indefinitely.

Without this gate, "we'll fix it later" is a verbal acknowledgment that leaves no trace in the review record. With it, the same decision becomes a tracked team obligation that can be followed up on.

### 4.7 Anti-examples Are Compiled and Maintained

`go-code-reviewer` includes a curated list of explicit anti-examples in its Evidence Rules section: patterns that commonly appear risky during review but, on closer inspection, should not be reported. This list is checked before any finding is promoted to the output.

The need for explicit anti-examples comes from a specific failure mode: reviewers — including models — can correctly identify a pattern as theoretically risky while missing the contextual signals that make it safe in practice. For example:

- Flagging a potential race condition on a map that is only accessed from a single goroutine.
- Warning about missing slice pre-allocation when the slice holds fewer than 16 elements.
- Recommending `slog` to a codebase whose `go.mod` targets Go 1.20.
- Flagging `defer f.Close()` ignoring an error when the file was opened read-only.

None of these are false positives because the reviewer failed to understand Go. They are false positives because a rule was applied without checking the specific context that makes the rule inapplicable.

By compiling these patterns explicitly, the skill creates a shared calibration point across reviewers. A reviewer does not need to re-derive from first principles why `json.Marshal` error suppression on a statically-known struct is acceptable, or why `errors.Is` is not required when the sentinel and the caller live in the same package. The anti-examples encode that institutional knowledge directly.

This is also why the list grows over time: each entry represents a class of false alarm that real reviews produced, evaluated, and agreed should be filtered. It is not a static checklist but a living record of lessons from actual use.

### 4.8 There Is a Go Version Gate

Go evolves quickly, but project minimum versions do not always track the latest release. `go-code-reviewer` has a dedicated Go Version Gate that requires checking `go.mod` before making version-specific recommendations.

This prevents a common failure mode: good advice applied to the wrong project. For example:

- Recommending `slog` to a Go 1.20 project is not actionable.
- Recommending typed atomics to a pre-1.19 project is not actionable.
- Expecting newer syntax or standard library packages in an older codebase only creates noise.

The point is not to show how many modern features the reviewer knows. The point is to make sure the recommendations can actually be used in the current project.

### 4.9 Generated Code Is Excluded

The Generated Code Exclusion Gate explicitly removes `*.pb.go`, `*_gen.go`, mock files, and files with a `Code generated ... DO NOT EDIT` header from finding scope.

The reason is straightforward: generated files are usually not the right place to fix the underlying problem. Leaving review comments on generated code often does not solve anything and can mislead the author into changing code that should not be edited by hand.

This rule:

- keeps attention on the real source files,
- prevents wasted effort in noisy generated artifacts,
- makes it clear when the correct target is the generator config or template instead.

### 4.10 Reference Files Must Be Loaded by Trigger

The Reference Loading Gate says that once the code under review triggers a category such as concurrency, security, database, HTTP, or test quality, the matching `references/*.md` file must be loaded before evaluating that category.

This is not a soft suggestion. It is a hard requirement. The reason is that many Go review failures do not come from complete ignorance; they come from **missing a domain-specific review frame**. For example:

- In gRPC + database code, reviewers may miss deadline propagation, metadata forwarding, or pool configuration.
- In concurrent code, they may fixate on mutexes and miss goroutine lifecycle, cancellation paths, or error aggregation.
- In tests, they may check only for the existence of tests and miss boundary cases, failure paths, or incomplete assertions.

`Eval 7` in the evaluation report is a strong example. With reference loading, the skill correctly suppressed `err == sql.ErrNoRows` in a grey-area case while still catching the real gRPC / database issues. Without the skill, the review added four noisy findings.

### 4.11 It Expands Impact Radius but Still Enforces Boundaries

In diff review, the skill does not look only at the patch itself. It also traces implementors, cross-package callers, struct construction sites, and usage sites, and adds them to the review scope. This is one of its strongest capabilities.

At the same time, it enforces a Diff-boundary rule: for impact-radius files that are not in the diff, review only the functions and code paths affected by the current change. Do not turn the entire file into an opportunistic audit of unrelated legacy issues.

These two design choices only work when paired:

| Design | Problem it solves |
|--------|-------------------|
| Impact-radius expansion | Prevents missing cascading effects from interface, signature, or struct-field changes |
| Diff-boundary limit | Prevents reviewers from surfacing every old problem in a nearby file and flooding the result with noise |

That is exactly why the skill stands out in `Eval 8`: with-skill output becomes "4 issues to fix + 4 recorded legacy risks," while without-skill becomes "10 issues mixed together." The first is easier to act on and easier for a team to reason about.

### 4.12 It Distinguishes `introduced`, `pre-existing`, and `uncertain`

The Change Origin Classification Gate requires every finding to carry an origin:

- `introduced`: caused or modified by the current change
- `pre-existing`: already present before the current change
- `uncertain`: not enough evidence to classify confidently yet

This is one of the most team-aware parts of the skill. It addresses a central fairness problem: **developers should not be blocked by debt they did not introduce, but high-risk legacy issues also should not disappear just because they are not new.**

So the skill does not treat this as a binary:

- `introduced` issues usually block merge or require explicit risk acceptance.
- `pre-existing` issues are normally visible but not merge-blocking, and should be tracked separately.
- `uncertain` issues are treated as `introduced` by default, while still allowing reclassification with evidence such as `git blame`.

This is a very practical design choice. It protects authors, preserves fairness, and still keeps the repository's health visible.

### 4.13 Residual Risk Exists vs. Findings-Only Output

Many review workflows preserve only the final findings. Everything else either disappears or remains scattered across comment threads. `go-code-reviewer` keeps a dedicated `Residual Risk / Testing Gaps` section.

This solves a real problem: what should happen to information that matters but should not sit in the main Findings section? That includes:

- lower-priority issues moved out by the volume cap,
- medium/low-risk historical issues outside the diff,
- verification gaps and missing test coverage,
- risk signals that deserve attention even when evidence is not complete enough for a main finding.

The value is simple: **it keeps Findings focused without letting already-validated risk quietly disappear.**

The four Residual Risk items in `Eval 8` show why this matters. They turn the review result from "merge blockers only" into "merge blockers + debt ledger + verification gaps," which is much closer to what real teams need.

### 4.14 Severity Tiers and a Volume Cap Are Necessary

Workflow step 10 requires findings to be merged, sorted, and filtered through a severity-tiered volume strategy:

- keep all `High` findings,
- fill remaining space with `Medium`,
- include `Low` only if room remains,
- move overflow into `Residual Risk`.

This is not about reporting fewer problems. It is about keeping the result focused. A common review failure is to flatten critical defects, medium-risk issues, and minor cleanups into one long list, leaving developers unsure what to fix first.

This strategy has three benefits:

- high-risk issues are never lost to a length limit,
- findings remain in a workable size range,
- repeated conceptual issues can be merged instead of explained five times in five different places.

### 4.15 Strict Output Format

The required output format is detailed: Review Mode, Findings, Suppressed Items, Execution Status, Risk Acceptance / SLA, Open Questions, Residual Risk / Testing Gaps, and Summary.

This is not formality for its own sake. It lets one review result serve several readers at once:

- the author, who needs to know what must be fixed now and what is only background debt,
- the reviewer and team, who need to know what evidence supports the result,
- maintainers, who need to know what was not verified and what risk was explicitly accepted,
- downstream processes, which may need issue filing, SLA tracking, or follow-up review.

Without fixed sections, review quality becomes too dependent on individual reviewer writing style.

The strict format also extends to the No-Finding Case. When no actionable issues are discovered, the review must still produce a Review Mode declaration, Execution Status, and baseline summary. This is deliberate: a review that goes silent when nothing is found is not auditable. A structured minimal output — matching the form of any other review result — documents that the code was examined, the standard was applied, and nothing warranting a finding was observed.

## 5. Problems This Design Addresses

Cross-referencing `SKILL.md` and the evaluation report, the skill is mainly solving the following engineering problems:

| Problem | Corresponding design | Practical effect |
|---------|----------------------|------------------|
| Review depth mismatch | `Lite / Standard / Strict` mode selection | Small changes are not over-reviewed, and risky changes are not under-reviewed |
| Weak link between evidence and conclusion | Execution Integrity Gate | Unverified claims are not written as though they were verified |
| No time dimension in review judgment | Baseline Comparison Gate | Teams can distinguish newly introduced issues from regressions, ongoing issues, and resolved ones |
| Too many false positives | False-Positive Suppression Gate + Suppressed Items | Keeps signal-to-noise high and makes filtering visible |
| Deferred issues with no ownership or timeline | Risk Acceptance and SLA Gate | Every open finding carries a committed deadline; deferrals are recorded, attributed, and given a review date |
| Theoretically risky patterns that are safe in context | Anti-examples list in Evidence Rules | Calibration is shared and cumulative; reviewers do not re-derive from first principles why known-safe patterns should not be reported |
| Recommendations that do not fit the project version | Go Version Gate | Avoids advice the current project cannot adopt |
| Generated files distracting the review | Generated Code Exclusion Gate | Keeps attention on code that should actually be changed |
| Weak domain judgment | Reference Loading Gate | Brings in the right review frame for concurrency, security, DB, HTTP, and tests |
| Looking only at changed lines and missing side effects | Impact-radius expansion | Catches ripple effects from interface, signature, and struct changes |
| Legacy debt blocking the current PR | Origin classification + Residual Risk | Keeps historical issues visible without assigning them all to the current author |
| Overlong but non-actionable review output | Severity tiers, volume cap, structured output | Keeps the result focused and easier for teams to work with |

The evaluation data supports this clearly: across four subtle scenarios, with-skill false-positive rate was `0/19`, while without-skill was about `5/32`; signal-to-noise improved from `53%` to `89%`; and only with-skill consistently produced structured `Residual Risk`. So the value is not "finding more bugs." It is **producing review results that are more precise, more stable, and more usable by a team without missing the high-risk issues.**

## 6. Key Highlights

### 6.1 It Turns Review from "Giving Comments" into "Routing Risk"

This is the skill's most important strength. It treats review not as a stream of observations, but as a risk-handling process with input boundaries, evidence requirements, and priority ordering.

### 6.2 It Optimizes for Stable Judgment, Not Reviewer Improvisation

Many critical decisions in the skill are not "use experience and decide ad hoc." They follow a pattern of rules first, judgment second. For example:

- choose review mode before choosing depth,
- check `go.mod` before making version-sensitive suggestions,
- determine impact radius before deciding what extra files belong in scope,
- trigger reference loading before evaluating concurrency, security, database, and HTTP concerns,
- suppress first, then decide what is worth promoting to Findings.

The aim is not to make the reviewer look clever. The aim is to make results more predictably consistent across users and scenarios.

### 6.3 It Is Strict Without Being Unfair

Many review systems emphasize strictness but end up mixing historical debt with the current change, which creates a poor developer experience. `go-code-reviewer` is more mature here:

- `introduced` issues require a fix or explicit acceptance,
- `pre-existing` issues remain visible but do not normally block merge,
- `uncertain` issues are handled conservatively first and can later be reclassified with evidence.

The Risk Acceptance and SLA Gate reinforces this further. When a finding cannot be fixed immediately, the gate requires an explicit decision — not a verbal acknowledgment that disappears into the comment thread, but a recorded entry with an owner, a justification, and a review date. This keeps the team's obligations visible and time-bounded.

This keeps quality standards high without dumping the entire repository's history onto the current author.

### 6.4 False-Positive Handling Is Explicit, Not Hidden

Many review tools never explain whether an unreported concern was intentionally examined and dismissed or simply overlooked. `go-code-reviewer` makes that distinction visible through `Suppressed Items`.

The Anti-examples list in the Evidence Rules section deepens this further: it explicitly records patterns that, by accumulated experience, should never be reported. This means both layers of suppression are visible — the per-instance `Suppressed Items` for context-specific decisions, and the Anti-examples list for class-level calibration shared across all reviews.

That matters because it improves interpretability. The team learns not only what was reported, but also why some suspicious-looking patterns were intentionally not reported.

### 6.5 Its Advantage Grows in Complex Scenarios

The evaluation results are clear: in textbook scenarios, the skill and generic Claude have the same defect-detection power, and the gain is mostly process quality. In subtle scenarios, the gap becomes much larger.

This is especially true in:

- grey-area reviews, where false positives need tight control,
- multi-file impact-radius reviews, where "must fix now" and "historical debt to track" must be separated cleanly.

That tells us the skill is not meant to replace Go fundamentals. It is meant to provide a steadier frame in the review situations that are easiest to distort.

## 7. When to Use It — and When Not To

| Scenario | Suitable | Reason |
|----------|----------|--------|
| Reviewing a Go PR, diff, or a set of changed files | Yes | This is where mode selection, boundary control, origin classification, and structured output create the most value |
| Checking whether code follows repository policy | Yes | The skill prioritizes `constitution.md`, then `AGENTS.md` |
| Changes involving concurrency, security, database code, HTTP, or public interfaces | Especially yes | Reference loading and impact-radius expansion materially improve review quality |
| Wanting only a quick subjective opinion | Not really | That is not what the skill is designed to provide |
| The task is writing code, debugging, or adding tests | No | Those belong to other skills or workflows, not review |

## 8. Conclusion

The real strength of `go-code-reviewer` is not that it "finds more bugs" than a general model. It is that it systematizes the parts of Go review most likely to become distorted: how deep the review should go, how evidence and inference should be separated, how false positives should be controlled, how historical debt should be handled, how specialized domain checks should be pulled in, and how the final result should be delivered to a team.

From a design perspective, the skill is a strong example of production-grade review principles in practice: **calibrate review depth before gathering evidence; control false positives before reporting issues; separate responsibility before deciding action.** That is why it is especially valuable for complex PRs, grey-area judgment, and multi-file impact analysis, rather than only for textbook Go defect checking.

## 9. Document Maintenance

This document should be updated when:

- the review modes, gates, workflow, or output format in `skills/go-code-reviewer/SKILL.md` changes,
- the checks, triggers, or domain guidance in `skills/go-code-reviewer/references/*.md` change,
- key data in `evaluate/go-code-reviewer-skill-eval-report.md` that supports the claims here changes,
- the project's team conventions for review rules, SLA, Residual Risk, or origin classification change.

Review quarterly; review immediately if the `go-code-reviewer` skill undergoes substantial refactoring.

## 10. Further Reading

- `skills/go-code-reviewer/SKILL.md`
- `skills/go-code-reviewer/references/pr-review-quick-checklist.md`
- `skills/go-code-reviewer/references/go-security-patterns.md`
- `skills/go-code-reviewer/references/go-concurrency-patterns.md`
- `skills/go-code-reviewer/references/go-error-and-quality.md`
- `skills/go-code-reviewer/references/go-test-quality.md`
- `skills/go-code-reviewer/references/go-api-http-checklist.md`
- `skills/go-code-reviewer/references/go-database-patterns.md`
- `skills/go-code-reviewer/references/go-performance-patterns.md`
- `skills/go-code-reviewer/references/go-modern-practices.md`
- `evaluate/go-code-reviewer-skill-eval-report.md`

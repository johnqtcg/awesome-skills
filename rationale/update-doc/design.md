---
title: update-doc skill design rationale
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-27
applicable_versions: current repository version
---

# update-doc Skill Design Rationale

`update-doc` is a drift-prevention framework for synchronizing repository documentation. Its core idea is: **the hard part of documentation updates is updating only the documentation that is actually impacted by code changes, keeping every change traceable to repository evidence, avoiding over-scoped rewrites, making it clear which information was confirmed and which was simply not found in the repo, and reducing the chance that the docs drift behind the code again after the current patch.** That is why the skill turns the Audience and Language Gate, Project Type Routing, the Diff Scope Gate, the Command Verifiability Gate, Lightweight / Full Output Modes, the Codemap Output Contract, CI Drift Guardrails, and the Quality Scorecard into one fixed workflow.

## 1. Definition

`update-doc` is used for:

- synchronizing README files, `docs/`, codemaps, and related repository docs after code changes,
- producing evidence-backed documentation patches instead of generic rewrites,
- selecting different documentation structures based on repository type,
- controlling update/reporting weight through lightweight and full output modes,
- and adding maintenance and CI guardrails so documentation does not drift again immediately afterward.

Its output is not just the edited documents. It also includes:

- changed files,
- evidence map,
- command verification,
- scorecard (in full mode),
- open gaps (required in full mode; optional in lightweight mode when a real gap is exposed).

From a design perspective, it is closer to a documentation-synchronization governance framework than to a generic prompt for polishing docs.

## 2. Background and Problems

The skill is not solving "models cannot write documentation." It is solving the fact that post-code-change documentation work naturally drifts into several risky failure modes:

- docs are changed, but changed too broadly,
- docs look complete, but many claims are not actually backed by repo evidence,
- docs are synchronized once, but nothing reduces the chance of future drift.

Without an explicit process, the most common failures cluster into eight categories:

| Problem | Typical consequence |
|---------|---------------------|
| Project type is not identified first | a CLI README is written like a backend service guide, or a monorepo README becomes a directory-tree dump |
| Diff scope is not constrained | a small fix turns into a full README rewrite that damages structure and navigation |
| Lightweight and full updates are not distinguished | small patches become heavy rewrites while large changes receive incomplete reporting |
| Claims are not traceable | PR reviewers cannot tell whether the doc change actually came from code evidence |
| `Not found in repo` discipline is missing | information gaps are silently filled by model intuition |
| Command verification is unclear | users cannot tell which commands were run versus inferred from source |
| Codemaps have no stable contract | architecture docs for complex repos become inconsistent and hard to maintain |
| CI drift is ignored | docs become outdated again soon after the current sync |

The design logic of `update-doc` is to answer "what type of repo is this, which docs are truly impacted, should this be a lightweight patch or a full update, where is the evidence for each changed section, which facts do not exist in the repo, and how will future drift be reduced?" before actual editing begins.

## 3. Comparison with Common Alternatives

It helps to compare it with a few common alternatives:

| Dimension | `update-doc` skill | Asking a model to "update README/docs" | Treating doc updates as one-off writing tasks |
|-----------|--------------------|----------------------------------------|----------------------------------------------|
| Project-type routing | Strong | Weak | Weak |
| Diff-scope control | Strong | Weak | Weak |
| Evidence mapping | Strong | Weak | Weak |
| Output-mode distinction | Strong | Weak | Weak |
| Codemap contract | Strong | Weak | Weak |
| `Not found in repo` discipline | Strong | Medium | Weak |
| CI drift guardrails | Strong | Weak | Weak |
| Structured delivery | Strong | Weak | Weak |

Its value is not only that documentation looks better written. Its value is that post-change documentation work becomes traceable, reviewable, and maintainable.

## 4. Core Design Rationale

### 4.1 The Audience and Language Gate Comes First

The first gate in `update-doc` determines:

- who the target readers are,
- what language the output should use.

The point is not to force audience labels into documents. The point is to prevent updates from being written for the wrong reader. For example:

- a top-level README usually serves external readers or new contributors first,
- ops docs serve maintainers,
- codemaps serve engineers trying to understand repository structure.

The skill also explicitly says that if the user does not specify language, it should follow the repository's current doc language rather than switching arbitrarily. This prevents documentation updates from drifting in tone, audience, or language layering.

### 4.2 Project Type Routing Is Foundational

Before it edits docs, `update-doc` routes the repository into one of:

- Service / Backend,
- Library / SDK,
- CLI Tool,
- Monorepo.

This is the structural anchor of the skill, because whether a documentation update is good often depends on whether the repository was routed correctly. For example:

- Service docs should prioritize runtime modes, config/env, and ops commands,
- CLI docs should prioritize install, usage examples, and flags/options,
- Monorepos should prioritize module index tables and submodule links rather than dumping a full directory tree.

The evaluation showed this as one of the most stable skill-only differences: with-skill was `3/3`, without-skill was `0/3`. In the monorepo scenario especially, without-skill collapsed into a directory-tree dump while with-skill consistently followed the module-index + codemap path. That shows project-type routing is not a stylistic preference; it is the prerequisite for all later structural decisions.

### 4.3 The Diff Scope Gate Is So Early and So Strict

`update-doc` explicitly requires:

- inferring documentation scope from `git diff --name-only` or directly impacted code paths,
- patching affected sections first,
- expanding into broader rewrites only when requested.

This is critical because many documentation-update tasks are not "rewrite the README." They are "repair the 1-2 places that no longer match the code." Without diff-scope discipline, a model can easily decide to reorganize the whole document, which leads to:

- damaged navigation,
- reordered headings,
- unnecessary changes to a structure the user already liked.

One of the evaluation's biggest quality gaps came from exactly this behavior: in the lightweight CLI patch scenario, without-skill added sections such as "How It Works" and "Error Handling," while with-skill updated only the truly stale flag docs. The core value of the Diff Scope Gate is therefore precision: update the right parts, not "take the opportunity" to rewrite.

### 4.4 Lightweight and Full Output Modes

The skill does not treat all documentation updates as the same kind of work. It separates them into:

- Lightweight Output Mode,
- Full Output Mode.

The trigger logic is also explicit:

- lightweight mode fits 1-2 files, narrow patches, and no new runtime/API/deploy surface,
- full mode fits codemap work, new runtime modes, multi-module impact, substantial README restructuring, or explicit audits.

This is mature design because it solves two opposite problems at once:

- small changes should not carry the cost of a heavy reporting package,
- large changes should not be delivered as a tiny patch with no audit trail.

The evaluation showed that without-skill had no mode concept at all. As a result, it rewrote too much in the simple scenario and reported too little in the complex ones. With-skill's advantage came from controlling both edit scope and reporting scope together.

### 4.5 The Evidence Map Is a Core Increment vs. an Optional Table

`update-doc` requires changed sections to map back to repository evidence such as:

- entry points,
- env/config loading,
- routes / handlers,
- Makefile / CI / runtime scripts,
- dependency manifests.

What this really solves is documentation-claim auditability. The evaluation makes this especially clear:

- the baseline model was already fairly strong on factual accuracy,
- the real difference was that with-skill could map claims back to code in a structured way.

That means the skill does not primarily win on "being more correct." It wins on "being able to show why the document is correct." That matters for PR review, maintenance, and multi-person documentation work.

### 4.6 `Not found in repo` Must Be a Hard Discipline

The skill explicitly requires:

- marking missing facts as `Not found in repo`,
- never inventing APIs, routes, env vars, ports, jobs, or dependencies.

This is critical because doc-update tasks are especially vulnerable to polished hallucination: a model tries to make the document "more complete" by adding things that sound plausible but have no repository evidence.

`update-doc` keeps the gap visible instead of disguising it as an answer. In the short term that can make the document look less full, but in the long term it sharply reduces misleading documentation. The monorepo scenario's `Not found in repo` discipline is one of the clearest demonstrations of that value.

### 4.7 The Command Verifiability Gate Keeps Internal Markers Out of User-Facing Docs

The skill takes a careful stance on command verification:

- if commands were executed, say so in the assistant response,
- if commands were not executed, say that honestly too,
- but do not leak internal labels like "Not verified in this environment" into user-facing docs by default.

This is mature design because it distinguishes between:

- being honest to the user and the team,
- keeping formal repository docs free of internal workflow noise.

In other words, verification state belongs in the delivery report, not necessarily inside the README or docs themselves. Without that separation, it becomes easy to turn repository docs into half-audited internal working notes.

### 4.8 Anti-Patterns Are Called Out Explicitly

The Anti-Patterns section is not generic writing advice. It targets the most common bad behaviors in doc-sync work:

- leaking scorecards or evidence tables into user-facing docs,
- making the README "more complete" at the cost of homepage usefulness,
- deleting useful navigation to make the file shorter,
- updating only output examples without preserving the input -> result -> output-shape reader path,
- dumping a full directory tree into a monorepo README.

This matters because these are exactly the kinds of changes that can sound reasonable in isolation while still hurting documentation UX. In the evaluation, the baseline model's monorepo directory-tree dump showed that these anti-patterns are not hypothetical.

### 4.9 Dedicated Codemap Output Contract

When the user requests codemaps, `update-doc` does not just "write some architecture docs." It requires evidence-backed contract files selected by repository shape, such as:

- `docs/CODEMAPS/INDEX.md`,
- `docs/CODEMAPS/backend.md`,
- `docs/CODEMAPS/integrations.md`,
- `docs/CODEMAPS/workers.md` when workers / cron / queues exist,
- `docs/CODEMAPS/frontend.md` when a frontend exists,
- `docs/CODEMAPS/database.md` when schema evidence exists.

It also requires each codemap to contain at least:

- last updated,
- entry points,
- key modules table,
- evidence-backed data flow,
- external dependencies,
- cross-links.

This is important because codemaps are not ordinary README patches. They are structure documents for repositories. Without a contract, they easily turn into one-off architecture notes; with a contract, they become stable, maintainable artifacts. The evaluation's codemap-completeness advantage being skill-only reinforces this point.

### 4.10 CI Drift Guardrails Matter So Much

`update-doc` does not stop at "the docs are synchronized now." It also requires thinking about:

- markdown lint,
- link checking,
- docs drift checks,
- ownership and update timing.

This has real governance value because documentation drift is fundamentally a recurring problem, not a one-time problem. If the workflow only patches the current diff and never adds guardrails, the docs will quickly become stale again.

The evaluation marked CI Drift Guardrails as a skill-only capability, which shows that the base model does not naturally move from "fix this doc" to "how do we reduce the chance of future drift?" That is one of the skill's strongest long-term contributions.

### 4.11 README UX Rules Are Structural vs. Cosmetic

For top-level README files, `update-doc` explicitly prefers:

1. value proposition before implementation detail,
2. install / quick start before maintainer workflows,
3. a compact TOC for long docs,
4. end-to-end examples before deep reference sections.

This is necessary because README updates can easily become more and more maintainer-oriented under the name of "completeness." These rules protect the README's role as a homepage: help readers understand the project and get started before diving into deeper maintenance details.

### 4.12 The Real Increment Is Methodology vs. Fact Extraction

The evaluation already shows that without-skill could often get factual items right:

- environment variables,
- ports,
- API routes,
- Makefile targets,
- basic docker-compose documentation.

The real gap was elsewhere:

- no project-type routing,
- no output-mode control,
- no Evidence Map,
- no Quality Scorecard,
- no CI drift awareness,
- no codemap contract.

That means the core value of `update-doc` is not "making the model smarter at reading code." It is making the model update docs in a way that is traceable, controlled, and maintainable.

## 5. Problems This Design Solves

Combining the current `SKILL.md`, key references, and the evaluation report, the skill solves the following problems:

| Problem type | Corresponding design | Practical effect |
|--------------|----------------------|------------------|
| Doc structure does not match repo type | Project Type Routing | README / docs structure fits repo shape better |
| Small changes trigger large rewrites | Diff Scope Gate + Lightweight Mode | Updates stay more precise |
| Large changes lack full audit context | Full Output Mode | Reporting becomes more complete |
| Documentation claims are not traceable | Evidence Map | Review becomes easier |
| Information gaps get guessed away | `Not found in repo` discipline | Output becomes more honest |
| User-facing docs are polluted with internal audit markers | Command Verifiability Gate + Anti-Patterns | Docs stay cleaner |
| Codemap structure drifts | Codemap Output Contract | Architecture docs stay more stable |
| Docs fall behind code again | CI Drift Guardrails | Maintenance quality improves |

## 6. Key Highlights

### 6.1 It Turns Documentation Updating from a Writing Task into a Synchronization Task

The main goal is not "write a fuller document," but "make the docs match the code again."

### 6.2 Project-Type Routing Is One of Its Most Distinctive Design Choices

CLI, Service, Library, and Monorepo updates follow different structures, and this is one of the skill's most stable differentiators.

### 6.3 The Lightweight / Full Split Is Highly Practical

It distinguishes small patches from major updates, preventing over-rewrites in one case and under-reporting in the other.

### 6.4 The Evidence Map Makes Documentation Changes Genuinely Reviewable

The key increment is not merely correct content, but the ability to point back to which code evidence justifies a documentation claim.

### 6.5 Codemap Contracts and CI Drift Guardrails Give It Long-Term Value

The skill does not only patch the current docs. It also improves how future drift is prevented.

### 6.6 Its Real Increment Is Governance and Methodology, Not Basic Writing Ability

The evaluation already shows that the baseline model could extract many facts correctly. The real difference came from routing, scope discipline, output modes, structured audit reporting, and drift prevention. That means the core value of `update-doc` is documentation-sync governance, not simply "better README writing."

## 7. When to Use It — and When Not To

| Scenario | Suitable | Reason |
|----------|----------|--------|
| Synchronizing README / docs after code changes | Very suitable | This is the core use case |
| Codemap creation or restructure | Very suitable | It has an explicit output contract |
| Updating root README and module index in a monorepo | Very suitable | Project routing is especially important here |
| Writing a brand-new technical document from scratch | Not always optimal | That sits outside this skill's core synchronization scope |
| Pure prose polishing unrelated to code | Not suitable | The skill is evidence-first |
| Filling gaps from general intuition when repo evidence is missing | Not suitable | The skill preserves `Not found in repo` instead |

## 8. Conclusion

The real strength of `update-doc` is not that it can make a README look more like a polished answer. It is that it systematizes post-code-change documentation synchronization: classify language and project type first, constrain diff scope, choose lightweight or full mode, then constrain the result with Evidence Maps, `Not found in repo`, command-verification honesty, codemap contracts, and CI drift guardrails.

From a design perspective, the skill expresses a clear principle: **the key to high-quality documentation updates is not making the document "fuller," but ensuring every change can be tied back to repository evidence, ensuring small changes stay small, ensuring complex changes carry full audit information, and ensuring the team has some way to reduce future drift.** That is why it is especially well suited to README patches, docs-drift fixes, and codemap maintenance.

## 9. Document Maintenance

This document should be updated when:

- the Hard Rules, Pre-Update Gates, Lightweight / Full Output Modes, Codemap Output Contract, CI Drift Guardrails, Quality Scorecard, or Output Format in `skills/update-doc/SKILL.md` change,
- key rules in `skills/update-doc/references/update-doc.md`, `project-routing.md`, or `ci-drift.md` change,
- key supporting results in `evaluate/update-doc-skill-eval-report.md` or `evaluate/update-doc-skill-eval-report.zh-CN.md` change.

Review quarterly; review immediately if the project-type routing rules, output modes, codemap contract, or drift-guardrail mechanisms of `update-doc` change substantially.

## 10. Further Reading

- `skills/update-doc/SKILL.md`
- `skills/update-doc/references/update-doc.md`
- `skills/update-doc/references/project-routing.md`
- `skills/update-doc/references/ci-drift.md`
- `evaluate/update-doc-skill-eval-report.md`
- `evaluate/update-doc-skill-eval-report.zh-CN.md`

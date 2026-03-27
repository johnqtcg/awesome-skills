---
title: go-ci-workflow skill design rationale
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-27
applicable_versions: current repository version
---

# go-ci-workflow Skill Design Rationale

`go-ci-workflow` is a design and refactoring framework for GitHub Actions CI in Go repositories. Its core idea is: **you do not start by writing a workflow YAML that merely looks standard; you first determine what shape the repository has, how it runs locally, which tasks belong in the PR gate, and which parts must be degraded or deferred, and only then translate those facts into an honest, maintainable, reproducible CI structure.** That is why the skill turns Repository Shape, Local Parity, Security and Permissions, Execution Integrity, Degraded Output, and structured reporting into one explicit path.

## 1. Definition

`go-ci-workflow` is used for:

- creating or refactoring `.github/workflows/*.yml`,
- mapping repository structure to CI job design,
- making GitHub Actions reuse Makefile targets or other committed local entrypoints whenever possible,
- designing the split between core gate, integration, e2e, docker-build, vulnerability scan, and similar jobs,
- producing an honest fallback workflow when the repository lacks a Makefile or task runner,
- reviewing existing CI workflows for triggers, permissions, safety, and local equivalence.

Its output is not only YAML. It also includes:

- repository shape classification,
- the execution path of each job,
- trigger configuration,
- permissions and secret assumptions,
- tool-version sources,
- missing local entrypoints or task targets,
- actual validation status,
- follow-up recommendations when parity is incomplete.

From a design perspective, it is closer to a Go CI architecture decision system than to a GitHub Actions template generator.

## 2. Background and Problems

The main problem this skill addresses is not "people do not know GitHub Actions syntax." The deeper problems in Go-repository CI are usually these:

- CI drifts away from the way the repository runs locally,
- repository shape is misclassified, so the workflow architecture does not fit the repository,
- no explicit degradation exists, so a repo with no stable entrypoints still gets represented as if full local parity existed.

Without a clear framework, the most common distortions fall into eight categories:

| Problem | Typical consequence |
|---------|---------------------|
| Repository shape is never checked first | Monorepos, multi-module repos, services, and libraries all get forced into the same template |
| Makefile or local entrypoints are not reused first | Local and CI execution drift apart, making debugging harder |
| Job splitting is poorly designed | Everything is packed into one job, or expensive jobs are forced into every PR |
| Go version or tool versions are hardcoded | `go.mod` and CI fall out of sync, and upgrades become uncontrolled |
| Engineering details such as concurrency, timeout, or cache are omitted | Builds are slower and redundant runs waste resources |
| Permissions and secret boundaries are unclear | Fork PR safety is ignored and the workflow trust model remains vague |
| The repo lacks stable entrypoints but the workflow still pretends local parity is complete | CI appears polished, but no local reproduction path actually exists |
| Output is unstructured | Teams cannot see why the workflow was designed this way or what is still missing |

The design logic of `go-ci-workflow` is to make "how does this repository actually run?" explicit before deciding "what should the CI look like?"

## 3. Comparison with Common Alternatives

It helps to compare the skill with a few common alternatives:

| Dimension | `go-ci-workflow` skill | Asking a model to "write a Go CI workflow" | Manually copying a generic GitHub Actions template |
|-----------|------------------------|--------------------------------------------|----------------------------------------------------|
| Repository-shape detection | Strong | Weak | Weak |
| Reuse of Make / local entrypoints | Strong | Medium | Weak |
| Local parity awareness | Strong | Weak | Weak |
| Degradation handling | Strong | Weak | Weak |
| Job architecture | Strong | Medium | Medium |
| Trigger cost control | Strong | Medium | Weak |
| Permissions and secret boundary handling | Strong | Medium | Weak |
| Auditability of output | Strong | Weak | Weak |

Its value is not only that it can write a workflow. Its value is that it turns CI design from template copying into a repository-driven engineering decision process.

## 4. Core Design Rationale

### 4.1 The Repository Shape Gate Must Come Before Workflow Design

The first Mandatory Gate in `go-ci-workflow` is the Repository Shape Gate. It requires the repository to be classified first as one of the following:

- single-module application,
- single-module library,
- multi-module repository,
- monorepo with multiple apps/packages,
- Docker-heavy repository,
- reusable-workflow candidate.

This is critical because CI architecture does not exist independently from repository shape. Services and libraries have different trigger, matrix, Docker, integration, and release needs. Single-module and multi-module repositories also differ substantially in `go.mod`, caching, paths, and job ownership.

If this first step is wrong, later job splitting, trigger strategy, and path filtering will all rest on a false premise.

### 4.2 It Uses a Discovery Script to Gather Repository Facts First

The skill explicitly requires `scripts/discover_ci_needs.sh` to run first so it can collect:

- Makefile targets,
- alternative repo task entrypoints,
- Dockerfiles,
- `integration` / `e2e` directory signals,
- Go module structure,
- current workflow files,
- tool clues explicitly referenced by Makefiles and shell scripts under `scripts/`.

The value of this design is that it converts "repository state" from model inference into reproducible evidence. That avoids two common failures:

- the model assumes `make ci` exists when it does not,
- the model assumes the repo is single-module when nested `go.mod` files are present.

This is one reason `go-ci-workflow` is more reliable than a prompt that merely knows GitHub Actions syntax. It inspects repository facts before making architecture decisions.

### 4.3 The Local Parity Gate Is Central to the Skill

One of the most important design choices in `go-ci-workflow` is the Local Parity Gate. It requires every job to state which execution path it uses:

- `make target`,
- `repo task`,
- `inline fallback`.

This matters because many CI workflows can run, but still fail the maintainability test of "how you run locally is how CI runs." The Local Parity Gate solves practical questions such as:

- can a developer reproduce the failure path directly,
- is CI behavior constrained by the same local entrypoints,
- will CI gradually drift from local scripts as the repository evolves.

The evaluation report's clearest delta also comes from this layer: with-skill explicitly records parity and fallback behavior; without-skill often emits YAML without making that status legible.

### 4.4 It Prefers Make-Driven Delegation vs. Inline Commands

Execution Priority is explicit:

1. prefer Makefile targets,
2. then use committed task runners or scripts,
3. use controlled inline fallback only last.

This is a mature engineering choice. The problem with inline commands is not that they never work. The problem is that they make it easier for:

- local and CI behavior to drift,
- parameters, versions, and environment variables to fragment,
- maintainers to lose track of the repository's canonical entrypoint.

That is why the skill's default goal is not "put commands into the workflow." It is "make the workflow reuse what the repository already treats as the canonical entrypoint." Only when the repository lacks such entrypoints does the skill degrade to inline fallback, and even then it requires that incompleteness to be reported explicitly.

### 4.5 Degraded Output Gate

When a repository lacks a Makefile, repo task runner, stable script entrypoints, or complete local execution paths, `go-ci-workflow` explicitly requires:

- not pretending full parity exists,
- producing a scaffold or inline fallback,
- listing missing targets, scripts, and recommended follow-up work.

This is a very important design choice because many CI generation approaches fail not by being incomplete, but by **packaging temporary executability as if it were structurally complete**. Scenario 3 in the evaluation is the clearest example: with-skill marks `inline fallback` and `Local parity: PARTIAL`, while without-skill writes a normal-looking workflow without telling the reader that no repo-native entrypoint exists.

This is also why degradation handling creates the biggest performance gap in the evaluation.

### 4.6 The Trigger Rules Emphasize Cost and Trust Boundaries

`go-ci-workflow` does not assume every job should run on every PR. It distinguishes between:

- `pull_request`: core gate, low-risk verification, avoiding fork secret exposure,
- `push`: broader verification,
- `schedule`: expensive or comprehensive sweeps,
- `workflow_call`: only when there is real reuse value.

This reflects a mature principle: **trigger strategy is where cost modeling and trust modeling intersect.**

If the PR gate is too heavy, feedback slows down. If secret-dependent jobs are exposed to fork PRs, security risk rises. Trigger design is therefore not merely syntax work; it is cost and trust-boundary design.

### 4.7 The Security and Permissions Gate Is More Than "Add `contents: read`"

The skill does not reduce security to "put a permissions line in the file." It first requires determining:

- which event triggers the workflow,
- whether fork PRs can reach secrets,
- what the minimum permissions are,
- whether reusable workflows or self-hosted runners change the trust boundary.

This is important because the risk in GitHub Actions does not come only from what the job runs. It also comes from **who triggers it, inside which boundary, and with access to which secrets or write scopes**.

That is why the skill still emphasizes `permissions: contents: read` even in simple scenarios, yet asks for advanced-pattern references in more complex ones. The goal is not merely to be "a bit safer"; it is to make the workflow's trust boundary explicit during design.

### 4.8 Go Setup and Tool Pinning Are Unified Rules

`go-ci-workflow` uses the following default rules for Go and tool versions:

- using `go-version-file: go.mod` by default for application-style repositories,
- avoiding a hardcoded single Go version unless a library genuinely needs an explicit compatibility matrix,
- pinning exact versions for `go install` tools,
- keeping versions aligned with Makefile targets or repo-native install scripts whenever those exist.

This solves two very real problems:

- the repository upgrades Go but CI stays behind, or CI jumps ahead on its own,
- CI and local tool versions diverge, so lint, vulncheck, or codegen results drift.

From a maintenance perspective, both the Go version and tool versions should have a clear source of truth whenever possible. CI should not invent an arbitrary second version policy when the repository already defines one.

### 4.9 The Job Architecture Rules Split the Core Gate from Slow Jobs

The skill explicitly requires:

- keeping the core gate fast,
- separating slow, environment-sensitive, or expensive jobs,
- using `needs:` only when ordering truly matters,
- setting timeouts on every job,
- using concurrency to avoid redundant runs.

This is highly operational. Many CI anti-patterns are not about missing tools; they are about wrong job granularity:

- one oversized job makes failures harder to localize,
- slow jobs block fast feedback,
- expensive jobs run on every PR without justification.

Making job-architecture rules explicit means bringing feedback speed, cost control, and debuggability into workflow design at the same time.

### 4.10 References Are Loaded Selectively by Scenario

The references in `go-ci-workflow` are clearly layered. Under the current `SKILL.md` contract:

- `workflow-quality-guide.md` and `golden-examples.md` serve as the foundational references,
- `repository-shapes.md` is loaded only for monorepos or multi-module repos,
- `github-actions-advanced-patterns.md` is loaded only for complex trust-boundary or advanced workflow behavior,
- `fallback-and-scaffolding.md` is loaded only when local entrypoints are missing,
- monorepo, service-container, and PR-review scenarios also have separate assets.

This shows that the skill cares about context-cost discipline. A standard repository should not pay for the full monorepo, service-container, and fork-security playbook unless the scenario actually requires it. This "core rules always on, heavy details on demand" structure is a key part of production-grade skill design.

### 4.11 Honest-Reporting Output Contract

The Output Contract requires:

- changed files,
- repository shape classification,
- execution path per job,
- trigger configuration,
- permissions and secret assumptions,
- tool versions used,
- missing targets or entrypoints,
- validation performed,
- follow-up work when parity is incomplete.

The value here is that workflow changes become more than YAML diffs. They become explicit records of design premises, runtime entrypoints, and known gaps. That matters for:

- team review,
- later maintenance,
- diagnosing why CI behavior differs from local behavior.

The evaluation shows this clearly as well: baseline models can often produce acceptable YAML, but they usually do not produce this structured explanation layer, which makes long-term maintenance much weaker.

## 5. Problems This Design Solves

Combining the current `SKILL.md`, references, script behavior, and evaluation report, the skill addresses the following problems:

| Problem type | Corresponding design | Practical effect |
|--------------|----------------------|------------------|
| Repository shape is misread | Repository Shape Gate + discovery script | Detects repo type before choosing workflow architecture |
| CI drifts from local execution | Execution Priority + Local Parity Gate | Reuses Makefile or repo-native entrypoints first |
| Missing local entrypoints are hidden | Degraded Output Gate | Makes fallback paths and parity gaps explicit |
| Too many expensive jobs run on PRs | Trigger Rules + Job Architecture Rules | Splits jobs by cost and risk |
| Permissions and secret assumptions stay vague | Security and Permissions Gate | Makes the trust boundary explicit |
| Go and tool versions diverge | Go Setup and Tooling Rules | Keeps `go.mod`, Makefile, and CI consistent |
| Redundant runs waste resources | concurrency + timeout + intentional `needs:` | Controls cost and improves feedback speed |
| Workflow changes are hard to audit | Output Contract | Exposes shape, paths, triggers, gaps, and validation status |

## 6. Key Highlights

### 6.1 It Puts "How Does the Repository Actually Run?" Before "How Should CI Look?"

This is the most important design decision in the skill. CI is treated as a mapping of the repository's runtime model, not as an independent template.

### 6.2 Its Make-Driven Delegation Is Deliberately Strong

Many workflow generators still use inline commands even when the repo already has a Makefile. `go-ci-workflow` explicitly treats that as a second-best path.

### 6.3 Its Degradation Handling Is Unusually Honest

This is also where the evaluation showed the largest gap. The skill does not confuse "we can make it run inline" with "the repository has full local parity."

### 6.4 It Has Real Engineering Awareness of GitHub Actions Trust Boundaries

Permissions, fork PR exposure, secret access, workflow triggers, and reusable-workflow trust boundaries are all treated as first-class design concerns rather than footnotes.

### 6.5 Its Output Contract Is Built for Long-Term Maintenance

Workflow changes are easy to forget once only the YAML diff remains. Structured output fills in the missing rationale layer.

### 6.6 The Current Version Is Closer to a CI Design Methodology Than to a YAML Writer

The evaluation most strongly validates the skill's value in Make-driven delegation, degradation handling, Output Contract, and local-equivalence markers. At the same time, the current skill expands that foundation through references and the discovery script into repository-shape analysis, advanced trust-boundary handling, and fallback scaffolding. In other words, the current version is not just "better at writing YAML"; it provides a fuller Go CI design methodology.

## 7. When to Use It — and When Not To

| Scenario | Suitable | Reason |
|----------|----------|--------|
| Creating GitHub Actions CI for a new Go repository | Yes | This is the core use case |
| Refactoring a weak existing CI workflow | Yes | It systematically detects anti-patterns and local-drift issues |
| A Makefile-driven Go service | Very suitable | This is one of its strongest fits |
| A Go repo without a Makefile or task runner | Yes | But it will enter an honest degraded path |
| A monorepo or multi-module Go repository | Yes | It needs the extra repository-shape references |
| A non-GitHub CI system | No | That is outside the skill's scope |
| A release or deployment pipeline | Not by default | Unless the user explicitly asks for that |

## 8. Conclusion

The real strength of `go-ci-workflow` is not that it knows GitHub Actions syntax. It is that it systematizes the engineering judgments most often skipped in Go CI design: identify repository shape first, confirm local entrypoints and trust boundaries, then choose job architecture, trigger layering, tool-version sources, and degraded paths, and finally record the full design premise and known gaps in a structured report.

From a design perspective, the skill embodies a clear principle: **good CI is not what merely looks standardized; good CI matches how the repository actually runs, and when full parity is not possible, it says so explicitly.** That is why it is especially well suited to workflow design and refactoring in Go repositories.

## 9. Document Maintenance

This document should be updated when:

- the Execution Priority, Mandatory Gates, Trigger Rules, Output Contract, or Job Architecture Rules in `skills/go-ci-workflow/SKILL.md` change,
- key rules in `skills/go-ci-workflow/references/workflow-quality-guide.md`, `golden-examples.md`, `repository-shapes.md`, `github-actions-advanced-patterns.md`, or `fallback-and-scaffolding.md` change,
- the output fields, classification logic, or tool-detection logic in `skills/go-ci-workflow/scripts/discover_ci_needs.sh` change,
- key supporting conclusions in `evaluate/go-ci-workflow-skill-eval-report.md` change,
- the skill is substantially refactored around local parity, fallback behavior, or advanced GitHub Actions safety strategy.

Review quarterly; review immediately if the gates, fallback logic, or discovery script of `go-ci-workflow` changes substantially.

## 10. Further Reading

- `skills/go-ci-workflow/SKILL.md`
- `skills/go-ci-workflow/references/workflow-quality-guide.md`
- `skills/go-ci-workflow/references/golden-examples.md`
- `skills/go-ci-workflow/references/repository-shapes.md`
- `skills/go-ci-workflow/references/github-actions-advanced-patterns.md`
- `skills/go-ci-workflow/references/fallback-and-scaffolding.md`
- `skills/go-ci-workflow/scripts/discover_ci_needs.sh`
- `evaluate/go-ci-workflow-skill-eval-report.md`

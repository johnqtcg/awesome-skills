---
title: tdd-workflow skill design rationale
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-27
applicable_versions: current repository version
---

# tdd-workflow Skill Design Rationale

`tdd-workflow` is a practical TDD execution framework for Go service code changes. Its core idea is: **the value of test-driven development lies in making Red -> Green -> Refactor into verifiable work evidence, while requiring the author to explain which defects the tests are meant to catch, how much test budget the change deserves, which high-risk paths must be covered, and what residual risks remain.** That is why the skill turns the Defect Hypothesis Gate, Killer Case Gate, Coverage Gate, Execution Integrity Gate, Concurrency Determinism Gate, Change-Size Test Budget Gate, Scorecard, and Output Contract into one fixed workflow.

## 1. Definition

`tdd-workflow` is used for:

- applying practical TDD to new features, bug fixes, refactors, API changes, and new modules,
- preserving visible `Red -> Green -> Refactor` evidence,
- listing defect hypotheses before writing tests and mapping them to test names,
- raising test quality through killer cases plus coverage and risk-path gates,
- and preserving TDD evidence for pre-existing code through characterization-testing rules.

Its output is not just test code. It also includes:

- changed files,
- change size,
- defect hypotheses -> test mapping,
- killer cases,
- Red -> Green evidence,
- coverage,
- scorecard,
- residual risks / follow-ups.

From a design perspective, it is closer to a TDD-governance framework than to a prompt that simply generates Go tests.

## 2. Background and Problems

The main problem this skill addresses is not that models cannot write Go tests. It is that test-generation work easily degrades into several common forms of pseudo-TDD:

- implementation gets written first and passing tests are added afterward,
- many cases are produced but nobody can explain what defect they are meant to catch,
- line coverage is chased while high-risk paths still go untested.

Without an explicit process, the most common failures cluster into eight categories:

| Problem | Typical consequence |
|---------|---------------------|
| No Red evidence | you can only prove the code passes now, not that the tests would catch a defect |
| No defect hypotheses | tests drift away from real risk and miss killer paths |
| No killer case | high-risk bugs have no targeted defense |
| Only line coverage is checked | critical risk paths stay uncovered behind a good percentage |
| Test budget ignores change size | tiny changes get bloated; large changes get shallow coverage |
| Refactor phase changes behavior | behavior changes get disguised as cleanup |
| Legacy characterization abandons TDD discipline | characterization testing and plain test-after get mixed together |
| No structured report | reviewers cannot tell whether Red, coverage, and residual risks are real |

The design logic of `tdd-workflow` is to make "which exact defects are being defended, which test is responsible for each one, which cases are killer cases, how deep the test budget should go, whether real Red evidence exists, and whether coverage reaches risk paths" explicit before the work is allowed to count as valid TDD delivery.

## 3. Comparison with Common Alternatives

It helps to compare it with a few common alternatives:

| Dimension | `tdd-workflow` skill | Asking a model to "add unit tests" | Manual experience-driven test writing |
|-----------|----------------------|------------------------------------|--------------------------------------|
| Red -> Green evidence discipline | Strong | Weak | Medium |
| Defect-hypothesis-driven design | Strong | Weak | Medium |
| Killer case mechanism | Strong | Weak | Weak |
| Coverage + risk-path dual gate | Strong | Medium | Medium |
| Change-size-based test budgeting | Strong | Weak | Weak |
| Characterization-testing support | Strong | Weak | Medium |
| Execution integrity | Strong | Weak | Medium |
| Structured deliverable | Strong | Weak | Weak |

Its value is not only that the output looks more organized. Its value is that it upgrades "can write tests" into "can deliver verifiable TDD process evidence."

## 4. Core Design Rationale

### 4.1 It Starts with Change-Size Classification

The first step in `tdd-workflow` is not writing tests. It is classifying the change as:

- `S`,
- `M`,
- or `L`,

based on file count, LOC, and number of critical paths.

This is the structural axis of the skill because one of the most common distortions in TDD is not missing tests entirely, but mismatching test depth to change size. The skill explicitly defines:

- `S` changes as usually needing about 3-6 cases per method,
- `M` changes as usually needing about 6-12 cases per method,
- `L` changes as allowing a broader regression matrix.

If the test volume exceeds budget, the author must justify it with distinct logic paths. If the code is security-sensitive, such as auth, input validation, SSRF guards, or crypto, the budget may be doubled, but the security rationale must be documented in the output contract. This turns test depth from "write more just in case" into explicit resource allocation.

### 4.2 The Defect Hypothesis Gate Comes Before Test Writing

The skill forces concrete defect hypotheses first, such as:

- boundary/index defects,
- error propagation,
- mapping loss,
- concurrency/order/timing,
- idempotency/retry behavior.

Each hypothesis must map to at least one test case name.

This is critical because many automatically generated test suites still amount to a random spread of happy paths, error paths, and boundaries, without answering "what bug is this test actually defending against?" The Defect Hypothesis Gate establishes the risk model first and generates cases second, which gives each test a reason to exist.

The evaluation makes this one of the clearest skill-only deltas: without-skill wrote many tests in all three scenarios, but provided hypothesis-to-test mapping in 0/3 runs; with-skill provided it in 3/3.

### 4.3 The Killer Case Gate Is a Core Differentiator

`tdd-workflow` does not stop at "there are boundary tests." It requires at least one killer case per changed method or use case, and that killer case must:

1. target a high-risk defect hypothesis,
2. include a concrete fault injection or attack input,
3. include a critical assertion,
4. and be explicitly marked in the report.

This matters a great deal because many test suites run, and even achieve good coverage, while still lacking any dedicated defense against the most dangerous failure mode. The evaluation's `IsPrivateIPLiteral` scenario is the clearest example: without-skill wrote 36 tests, but missed IPv4-mapped IPv6 SSRF-bypass inputs such as `::ffff:127.0.0.1`; with-skill's killer case directly pinned that attack path. That shows the skill's increment is not simply "more tests," but "tests that better catch high-risk defects."

### 4.4 Red Evidence Must Be Preserved

One of the skill's core disciplines is that it is not enough to say TDD was used. The work must preserve:

- Red evidence,
- Green evidence,
- and evidence that refactor stayed green.

This is not formatting. It is the core legitimacy test for TDD. Without Red, the tests may only prove that the implementation currently passes; with Red, they prove that a wrong behavior would have failed.

That is also why the skill gives pre-existing code a dedicated characterization path:

- when tests are being added to existing implementation,
- Red evidence may be shown via mutation,
- or via explicit defect hypotheses that demonstrate what real risk the tests defend.

This is mature design because it acknowledges reality: not every task begins with a truly undefined function or a clean failing compile. But it still insists on verifiable Red alternatives rather than quietly collapsing into plain test-after.

### 4.5 The Coverage Gate Uses "Line + Risk Path"

The skill requires:

- default line coverage >= 80% for changed packages,
- plus coverage of all high-risk hypotheses and branches.

This is important because test work often falls into a common trap: the coverage number looks strong, but the dangerous path never actually ran. By placing risk-path coverage next to line coverage, `tdd-workflow` explicitly says that coverage is a floor, not proof of meaningful tests.

That also explains why the skill emphasizes killer cases, high-risk branches, and security overrides. Its real goal is not "maximize the percentage," but "make critical failures hard to slip through."

### 4.6 Characterization Testing Is Formally Included

In many repositories, the target function already exists but has no tests. If TDD is interpreted too narrowly, that creates an awkward question: how do you prove Red when the implementation already exists?

`tdd-workflow` does not answer that by abandoning TDD. It formally includes characterization testing:

- first write tests that document current behavior,
- keep those tests green as a safety net,
- then add a new failing test for the desired change,
- then implement the change.

For harder cases, the skill also allows mutation-based Red evidence or hypothesis-based Red evidence. This is important because it lets the framework cover real repository work instead of only idealized "brand new function" scenarios.

### 4.7 The Concurrency Determinism Gate Exists Separately

For concurrency-sensitive code, the skill explicitly requires:

- no `time.Sleep` as synchronization,
- ordering controlled through channels, barriers, waitgroups, or atomics,
- and `-race` execution.

This is highly targeted design because the most common fake-stability pattern in concurrency tests is to hide races behind sleeps. That can make tests look greener without making them more trustworthy. By splitting determinism into its own gate, the skill refuses timing-luck-based tests.

### 4.8 The Hard Rules Adapt to Project Assertion Style

`tdd-workflow` does not treat one assertion library as universally correct. Instead, it first checks the repository's existing convention:

- if the project uses `testify`, follow `require` / `assert`,
- if the project uses stdlib only, use `t.Fatalf` / `t.Errorf`,
- if the project uses `go-cmp`, allow `cmp.Diff`.

The value here is that the stable core of TDD is defined as process discipline rather than library preference. This avoids introducing a foreign testing style just to look more "TDD-like," and it aligns the workflow with real repository conventions.

### 4.9 It Explicitly Forbids Speculative Production Code

The skill clearly says:

- do not add production code that failing tests did not demand,
- do not use the Green phase to opportunistically add Update / Delete / helper abstractions.

This matters because many so-called test-first flows still collapse into implementing a whole block of production code at once. That may look sequentially correct, but it has already lost the TDD feedback loop. `tdd-workflow` uses this rule to pin implementation scope to the smallest path required by the current failing test.

### 4.10 The Refactor Phase Is Strictly Separated from Behavior Change

The skill explicitly defines refactor as structural improvement only, such as:

- extract method,
- rename,
- reduce nesting,
- replace magic numbers.

If refactor requires changing tests, or changes externally observable behavior, the work must start a new Red cycle.

The value of this design is that it separates structural cleanup from semantic change. Otherwise, people often "improve" behavior, error types, or API semantics during refactor while weak assertions fail to expose the drift. By enforcing this boundary, the skill restores refactor to what it should be: safe rearrangement.

### 4.11 Output Contract with Process Evidence

`tdd-workflow` requires the final output to include:

- changed files,
- change size,
- defect hypotheses -> test mapping,
- killer cases,
- Red -> Green evidence,
- coverage,
- scorecard,
- residual risks / follow-ups.

This is critical because TDD is easily misunderstood as a private habit where "tests exist at the end, so TDD happened." Once process evidence is made explicit, a reviewer can check:

- whether the work was truly test-driven,
- what the killer cases are,
- whether Red genuinely occurred,
- whether both line coverage and risk-path coverage passed,
- what edge cases were left outside budget.

That is why the deliverable is not just a set of test files. It is a reviewable explanation of TDD execution quality.

### 4.12 The Scorecard Is a Quality Gate, Not an Appendix

`tdd-workflow` divides evaluation into three tiers:

- Critical,
- Standard,
- Hygiene.

In practice, this means:

- missing Red evidence, killer case, or risk-path coverage makes overall PASS impossible,
- Standard needs at least 4/5,
- Hygiene needs at least 3/4.

The value of this design is that it separates "tests were written" from "this was a valid TDD cycle." The evaluation also shows this clearly: the biggest weakness of without-skill was not that the raw test code was terrible, but that the methodology evidence and structured quality gates were missing.

### 4.13 References Are Loaded Selectively by Scenario

The skill's references are not meant to be loaded all at once. They are routed by task type:

- `boundary-checklist.md` is always-read infrastructure,
- `api-3layer-template.md` and `fake-stub-template.md` are for API/service layers,
- `tdd-workflow.md` is for first-time TDD or complex refactors,
- `anti-examples.md` is for review or generation quality,
- `golden-characterization-example.md` is for adding tests to existing code.

This structure is sensible because TDD's core discipline must stay resident, while tactics vary with pure functions, layered services, legacy characterization, and concurrency-sensitive work. Layered references let the skill cover all of those shapes without forcing every task to load every detail.

## 5. Problems This Design Solves

Combining the current `SKILL.md`, key references, and the evaluation report, the skill solves the following problems:

| Problem type | Corresponding design | Practical effect |
|--------------|----------------------|------------------|
| Tests have no explicit risk model | Defect Hypothesis Gate | Makes tests more targeted |
| High-risk paths lack dedicated defense | Killer Case Gate | Improves detection of critical defects |
| Passing tests do not prove guarding power | Red -> Green evidence | Makes tests more verifiable |
| Coverage looks high while risk paths are missed | Coverage Gate (line + risk-path) | Makes adequacy checks more honest |
| Tiny changes get huge suites or large changes get shallow suites | Change-Size Test Budget Gate | Aligns depth with change scope |
| Concurrency tests rely on timing luck | Concurrency Determinism Gate | Improves stability and trustworthiness |
| Legacy code makes TDD evidence collapse | Characterization rules | Preserves TDD discipline in realistic contexts |
| Test results are hard to review | Output Contract + Scorecard | Improves replay and comparison |

## 6. Key Highlights

### 6.1 It Elevates TDD from "Test Order" to "Process Evidence"

The real focus is not the slogan "tests first," but proving that Red, Green, and Refactor genuinely happened.

### 6.2 Defect Hypotheses and Killer Cases Are Its Most Distinctive Structural Strengths

This is what makes `tdd-workflow` highly recognizable: define what bug class must be defended, then assign a test to guard it.

### 6.3 Its Coverage Model Is More Mature Than "80% Is Enough"

Line coverage is only the floor; risk-path coverage is what actually stops critical defects from slipping through.

### 6.4 Its Support for Adding Tests to Existing Code Is Very Practical

Many real tasks are not greenfield development but test backfill for existing logic. `tdd-workflow` brings characterization testing and mutation/hypothesis-based Red evidence into the TDD framework to handle that reality.

### 6.5 It Treats Test Budget as Part of the Design

S/M/L sizing plus security-budget overrides make test volume proportional to risk, not just "the more the better."

### 6.6 Its Real Increment Is Methodology Discipline More Than Test-Code Generation

The evaluation already shows this: the base model can already write table-driven tests, stdlib assertions, and boundary checks, and sometimes even produces more cases. The real delta comes from defect hypotheses, killer cases, Red evidence, coverage reporting, change-size control, and structured output. That means the skill's core value is TDD governance, not simply "better test writing."

## 7. When to Use It — and When Not To

| Scenario | Suitable | Reason |
|----------|----------|--------|
| New features, bug fixes, and API changes | Very suitable | These are its core use cases |
| Security-sensitive logic tests | Very suitable | Killer cases and risk-path gates are especially valuable |
| Adding tests to existing code | Very suitable | The characterization path is highly practical |
| Concurrency- or timing-sensitive logic | Very suitable | The determinism gate prevents fake-stable tests |
| Very small pure-function fixes | Suitable but can be light | These often fit the S-size budget |
| Quickly adding a few smoke tests only | Not always optimal | The process requirements are intentionally higher |

## 8. Conclusion

The real strength of `tdd-workflow` is not that it can generate more tests for you. It is that it systematizes the parts of TDD that are easiest to fake or hand-wave away: define defect hypotheses first, assign killer cases, preserve Red -> Green evidence, verify that coverage actually reaches risk paths, and deliver residual risks and scoring together with the code.

From a design perspective, the skill embodies a clear principle: **the key to high-quality TDD is not merely that test files appear before implementation, but that every test knows what defect it is defending against, every Green phase has Red evidence behind it, every refactor avoids hidden behavior change, and the full cycle can be reviewed by someone else.** That is why it is especially well suited to Go service development, bug fixing, security-sensitive logic, and test backfill for legacy code.

## 9. Document Maintenance

This document should be updated when:

- the Hard Rules, 6 Mandatory Gates, Workflow, Scorecard, Output Contract, or characterization-testing rules in `skills/tdd-workflow/SKILL.md` change,
- key rules in `skills/tdd-workflow/references/boundary-checklist.md`, `tdd-workflow.md`, `api-3layer-template.md`, `fake-stub-template.md`, `anti-examples.md`, or `golden-characterization-example.md` change,
- key supporting conclusions in `evaluate/tdd-workflow-skill-eval-report.md` or `evaluate/tdd-workflow-skill-eval-report.zh-CN.md` change.

Review quarterly; review immediately if the defect-hypothesis rules, killer-case rules, Red-evidence definition, coverage gate, or change-size budget of `tdd-workflow` change substantially.

## 10. Further Reading

- `skills/tdd-workflow/SKILL.md`
- `skills/tdd-workflow/references/boundary-checklist.md`
- `skills/tdd-workflow/references/tdd-workflow.md`
- `skills/tdd-workflow/references/anti-examples.md`
- `skills/tdd-workflow/references/golden-characterization-example.md`
- `evaluate/tdd-workflow-skill-eval-report.md`
- `evaluate/tdd-workflow-skill-eval-report.zh-CN.md`

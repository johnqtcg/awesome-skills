---
title: unit-test skill design rationale
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-27
applicable_versions: current repository version
---

# unit-test Skill Design Rationale

`unit-test` is a defect-first unit-testing framework for Go repositories. Its core idea is: **the goal of high-quality unit tests is to first classify target risk, then design high-signal cases around explicit defect hypotheses, and finally explain why the suite deserves to exist through Killer Cases, boundary checklists, tiered scorecards, and real `-race` / coverage evidence.** That is why the skill turns the Go Version Gate, Execution Modes, Defect-First Workflow, High-Signal Test Budget, Boundary Checklist, Auto Scorecard, Property-Based Testing, and Reporting Integrity into one fixed workflow.

## 1. Definition

`unit-test` is used for:

- adding, strengthening, and fixing unit tests for Go code,
- prioritizing real defects in boundaries, mappings, concurrency, and context propagation,
- organizing tests into maintainable table-driven + `t.Run` structures,
- selecting `Light / Standard / Strict` mode based on target risk,
- and delivering tests together with race, coverage, scorecard, and residual-risk evidence.

Its output is not just test code. It also includes:

- execution mode and rationale,
- targets tested and case counts,
- Go version and version-dependent adaptations,
- boundary checklist,
- coverage / race results,
- scorecard and final PASS / FAIL.

`Failure Hypothesis List`, detailed Killer Case reporting, and the JSON summary mainly belong to `Standard / Strict` mode outputs; `Light` mode intentionally reduces output to a lighter boundary check and scorecard package.

From a design perspective, it is closer to a unit-test governance framework than to a prompt that merely adds a few `_test.go` files.

## 2. Background and Problems

The skill is not solving "models do not know how to write Go tests." It is solving the fact that default unit-test generation often drifts into low-signal patterns:

- many tests exist, but the assertions are weak,
- coverage looks strong, but the suite still misses real bugs,
- lots of cases are present, but there is no visible testing methodology.

Without an explicit framework, the most common failures cluster into eight categories:

| Problem | Typical consequence |
|---------|---------------------|
| Coverage is chased without defect thinking | many paths appear tested, but important bugs still escape |
| Target risk is not classified | simple functions get over-engineered while risky concurrent code gets only shallow happy paths |
| No Killer Case exists | maintainers cannot tell which assertions are the real regression barriers |
| Boundary coverage is not systematic | `nil`, empty, singleton, last-element, and context-cancel cases are easily missed |
| Assertions are mutation-weak | tests only check `err == nil` or `not nil`, so field-level regressions still pass |
| Test organization is scattered | one target accumulates many separate `TestXxx` functions with poor reuse and high edit cost |
| Concurrency tests are nondeterministic | `time.Sleep`, no `-race`, and leaked shared state make tests flaky |
| Output is not auditable | the team cannot see why a mode was chosen, why the suite is considered sufficient, or what remains untested |

The design logic of `unit-test` is to answer "how risky is this code, what is most likely to fail, which assertions form the regression barrier, what coverage gate is reasonable, and what level of test process should apply?" before deciding how many tests to write or how to organize them.

## 3. Comparison with Common Alternatives

It helps to compare it with a few common alternatives:

| Dimension | `unit-test` skill | Asking a model to "write unit tests" | Treating unit tests as a coverage-filling task |
|-----------|-------------------|--------------------------------------|-----------------------------------------------|
| Defect-hypothesis-driven design | Strong | Weak | Weak |
| Mode selection (`Light / Standard / Strict`) | Strong | Weak | Weak |
| Killer Case discipline | Strong | Weak | Weak |
| Boundary-checklist system | Strong | Medium | Weak |
| Concurrency / `-race` awareness | Strong | Medium | Weak |
| Test-organization consistency | Strong | Medium | Weak |
| Quality scoring and auditability | Strong | Weak | Weak |
| Coverage philosophy | high-signal first, anti-bloat | often ad hoc | often metric-driven |

Its value is not only that there are "more tests." Its value is that unit tests become an explainable, auditable, and maintainable defect-defense system instead of a pile of disconnected cases.

## 4. Core Design Rationale

### 4.1 Mode Selection Comes Before Case Design

In workflow step 0, `unit-test` requires choosing `Light / Standard / Strict`. That matters because it explicitly rejects a common mistake: applying one heavy test process to every target.

It routes based on factors such as:

- target count,
- presence of concurrency,
- dependency complexity,
- branch complexity,
- security sensitivity,
- context / deadline logic,
- collection transforms or property-based triggers.

This design matters because:

- simple pure functions can stay in `Light` and avoid unnecessary overhead,
- ordinary business logic defaults to `Standard`,
- concurrent, security-sensitive, or higher-risk targets are promoted to `Strict`.

What this solves is mismatch between test-process weight and code risk. Without it, the usual distortion is that trivial logic gets wrapped in oversized methodology while dangerous code receives only a handful of shallow cases.

### 4.2 The Defect-First Workflow Is Central

The most important design choice in `unit-test` is not table-driven structure and not coverage. It is the Defect-First Workflow. In `Standard / Strict` modes, the skill requires a Failure Hypothesis List before writing tests, covering at least:

- loop / index risks,
- collection-transform risks,
- branching risks,
- concurrency risks,
- context / time risks.

This is critical because the highest-value part of unit testing is not "which parameter combinations exist," but "how is this code most likely to fail." For lower-risk targets, `Light` mode intentionally skips this heavier methodology layer so that simple unit tests do not turn into oversized process.

The evaluation proves this directly: with-skill and without-skill were almost identical in core functional-path coverage, and the largest gap came from Failure Hypothesis Lists, Killer Cases, and Boundary Checklists. In other words, the skill's main increment is not "testing more." It is "explaining much more systematically why these tests exist."

### 4.3 Killer Cases Are a Hard Constraint

In `Standard + Strict` modes, the skill requires at least one Killer Case per test target, and each Killer Case must contain four parts:

1. defect hypothesis,
2. fault injection or boundary setup,
3. critical assertion,
4. removal-risk statement.

This is one of the skill's most distinctive design choices. The difference between a normal edge case and a Killer Case is that a Killer Case must point to a named defect and explain "if this assertion is removed, which known bug can escape."

This solves a very practical maintenance problem: test files are often simplified, refactored, or partially deleted over time. Without the removal-risk layer, later maintainers cannot easily tell which assertions are decorative and which are the actual regression barrier. The evaluation showed that without-skill often covered the same paths, but lacked this explanatory layer, leaving the regression-defense boundary less explicit.

### 4.4 The Boundary Checklist Is Explicit vs. Implicit

`unit-test` turns boundary review into:

- a 5-item checklist for `Light`,
- a 12-item checklist for `Standard / Strict`.

The checklist covers:

- `nil`,
- empty,
- singleton,
- size / last-element boundary,
- min/max boundaries,
- invalid format,
- zero-value struct/default trap,
- dependency error,
- context cancellation,
- concurrent / race behavior,
- mapping completeness,
- killer-case mapping.

This is highly practical because missed boundaries are usually not caused by ignorance. They are missed because they do not naturally surface in a stable order during test writing. Once checklist discipline is explicit, test quality no longer depends on immediate memory alone; it has a reviewable baseline.

The evaluation also showed that without-skill did not necessarily omit boundary cases entirely, but it did omit the explicit checklist. That means the team could not quickly see which boundaries were systematically covered and which were only touched incidentally.

### 4.5 The Coverage Gate Is Scoped and Rationale-Based

The skill does not reduce coverage policy to a simplistic "always >= 80%." It explicitly distinguishes:

- logic-heavy packages: default `>= 80%`,
- infra / IO-heavy packages: possibly lower, but only with explicit rationale.

It also insists that:

- coverage must not be inflated with low-signal tests,
- even when coverage may be lower, boundary discipline still remains,
- multi-package situations should use `-coverpkg=./...` or per-package profiles for honest measurement.

This is mature design because it rejects two common extremes:

- treating coverage as the whole truth,
- abandoning coverage gates entirely because they are imperfect.

`unit-test` instead keeps coverage as one quality threshold while never letting it replace defect-first design.

### 4.6 Assertion Mutation Resistance Is Emphasized So Strongly

The skill repeatedly requires mutation-resistant assertions while adapting assertion style to project convention. It supports:

- `require` / `assert` in `testify`-based projects,
- `cmp.Diff` when `go-cmp` is the established convention,
- `t.Fatalf` / `t.Errorf` in stdlib-only projects,
- no existence-only checks like `err == nil` or `not nil`,
- business-field assertions rather than object existence.

This solves the core weakness of low-signal tests. A test that only proves "an object came back" may still pass when fields are swapped, defaults are wrong, or the last mapped item is missing. What the skill truly enforces is not one assertion library, but sufficient assertion strength to express business correctness.

The first rule in `bug-finding-techniques.md` is Mutation-Resistant Assertions, and the evaluation repeatedly supports the same point: the skill cares about which exact field must fail when behavior regresses, not just whether execution reached the path.

### 4.7 Test Structure Rules Are So Concrete

The skill requires:

- top-level naming adapted to target type,
- `t.Run` groups that map 1-to-1 to test targets,
- table-driven cases,
- defect-oriented readable case names,
- preferring `t.Parallel()` when safe, but only when truly isolated.

This is not just style. It is about maintenance cost. In the evaluation, without-skill often produced many separate `TestXxx` functions. Functionally that was sometimes fine, but it makes incremental additions more expensive and repeats setup more often. With-skill consistently used table-driven + `t.Run`, making future case additions cheaper.

### 4.8 Concurrency Testing Is Designed Around Determinism

`unit-test` explicitly requires:

- running `go test -race`,
- avoiding `time.Sleep` for synchronization,
- using channel barriers, WaitGroups, and channel sequencing for deterministic control,
- avoiding unsafe `t.Parallel()` combinations.

This is important because the biggest risk in concurrent unit tests is not that they "will not run." It is that they fail only sometimes, or pass locally and fail in CI. The patterns in `references/concurrency-testing.md` effectively turn concurrency testing from "guessing scheduling with time" into "controlling scheduling with synchronization primitives." That is why `-race` is treated as a hard requirement rather than an optional enhancement.

### 4.9 Property-Based Testing Is Supported but Not Allowed to Replace Table-Driven Tests

The skill takes a restrained approach to property-based testing:

- not applicable in `Light`,
- optional recommendation in `Standard`,
- required recommendation or implementation in `Strict` when the pattern fits.

It only recommends this path for patterns such as roundtrip, idempotency, preservation, commutativity, parse validity, and monotonicity, and it explicitly says:

- property-based tests verify invariants,
- table-driven tests verify exact boundaries and concrete outputs,
- Killer Cases are still not replaced by property-based tests.

This is mature design because it avoids another testing distortion: seeing one invariant and trying to replace hand-written boundary tests with randomized checks. The skill's position is clear: property-based testing adds breadth; it does not replace defect-driven or boundary-driven tests.

### 4.10 Generated Code Exclusion Is Necessary

`unit-test` explicitly excludes:

- `*.pb.go`,
- `*_gen.go`,
- `wire_gen.go`,
- `mock_*.go`,
- `*_mock.go`,
- files marked with `Code generated ... DO NOT EDIT`.

This is necessary because generated code is usually better validated by its generator's own guarantees or by testing the higher-level behavior around it. Without this exclusion, a model can easily spend effort where coverage is easy to raise but long-term value is low. The important point is not that generated code should never be tested, but that the skill treats it as outside the default high-value scope.

### 4.11 Auto Scorecard and Reporting Integrity Exist Together

The skill's output is not allowed to stop at "tests added." It must report at least:

- mode,
- version adaptation,
- boundary checklist,
- coverage / race results,
- a 13-item or 7-item scorecard,
- final PASS / FAIL.

In `Standard / Strict` modes, it must additionally include:

- hypothesis / killer-case mapping,
- fuller methodology output,
- JSON summary.

At the same time, Reporting Integrity says the model must not claim `-race` or coverage results unless they were actually run, and must provide exact commands when execution is not possible.

The value of this pairing is that unit tests become an auditable delivery artifact rather than only a code change. The team gets not only test files, but also answers to:

- why this mode was selected,
- which defects are covered, especially in `Standard / Strict` outputs,
- which killer cases are critical in `Standard / Strict`,
- whether coverage / race requirements were really met,
- what residual risks remain.

The evaluation's clearest advantage also sits here: methodology output and audit traceability were the main differentiators.

### 4.12 Trigger Design Is Part of the Skill's Architecture

Unlike many skills, `unit-test` treats trigger accuracy as a first-class concern in evaluation, and the result was `20/20`. That was not incidental; it came from deliberate Description design:

- strong trigger keyword coverage,
- explicit exclusions for benchmark / fuzz / integration / E2E / load / mock tasks,
- strong imperative trigger wording,
- and strong "cannot be replaced from memory" signals.

This belongs in the rationale because it shows that `unit-test` is not merely adding more rules. It is also solving "when should this skill activate, and when should it yield to another testing skill?"

## 5. Problems This Design Solves

Combining the current `SKILL.md`, key references, and the evaluation report, the skill solves the following problems:

| Problem type | Corresponding design | Practical effect |
|--------------|----------------------|------------------|
| Unit tests chase coverage only | Defect-First Workflow | Tests are shaped more like bug-finding than path-counting |
| High-risk and low-risk code use the same process | Execution Modes | Test-process weight matches code risk |
| Critical assertions get deleted during refactors | Killer Case + Removal Risk | Regression barriers become explicit |
| Boundary cases are missed | Boundary Checklist | Coverage becomes more systematic |
| Assertions are low-signal | Mutation-Resistant Assertions | Field, mapping, and state regressions are easier to catch |
| Concurrency tests are flaky | `-race` + deterministic concurrency patterns | Tests become more reliable |
| Test organization is scattered | table-driven + `t.Run` + target adaptation | Maintenance cost goes down |
| Test completeness is not auditable | Scorecard + Reporting Integrity | Teams can judge deliverability more clearly |

## 6. Key Highlights

### 6.1 It Turns Unit Testing from a Coverage Exercise into a Defect-Discovery Process

This is the skill's most important strength and the main source of differentiation in evaluation.

### 6.2 `Light / Standard / Strict` Makes Test Intensity Match Risk

Not every code path deserves the same process overhead, and this skill makes that judgment explicit.

### 6.3 Killer Cases Are a Highly Distinctive Design Feature

For every `Standard / Strict` target, at least one case must clearly say "if this assertion disappears, this bug can escape."

### 6.4 Boundary Checklists and Scorecards Make Test Quality Auditable

The team no longer has to rely on intuition about whether the suite is "probably enough."

### 6.5 It Is Especially Strong on Concurrent and Time-Sensitive Go Code

Channel barriers, error fan-in, panic recovery, `-race`, and `t.Parallel()` safety rules show specialized design around Go's high-risk testing areas.

### 6.6 Its Real Increment Is Methodology and Auditability, Not Raw Path Count

The evaluation already shows that with-skill and without-skill were similar in core functional-path coverage. The real gap came from Failure Hypothesis Lists, Killer Cases, Boundary Checklists, test organization, and scorecards. That means the core value of `unit-test` is testing governance, not simply "generating more test cases."

## 7. When to Use It — and When Not To

| Scenario | Suitable | Reason |
|----------|----------|--------|
| Adding unit tests for Go logic code or boundary behavior | Very suitable | This is the core use case |
| Concurrent, context-sensitive, or mapping-heavy code with real bug risk | Very suitable | Defect-First + `-race` are highly targeted here |
| Reviewing or restructuring existing `_test.go` quality | Very suitable | Scorecard and Killer Case rules are practical |
| Benchmarks | Not suitable | Should go to benchmarking / performance workflows |
| Fuzz tests | Not suitable | Should go to fuzzing workflows |
| Integration / E2E / load tests | Not suitable | All are outside unit-test scope |
| Mock generation | Not suitable | That is not test design itself |

## 8. Conclusion

The real strength of `unit-test` is not that it can write Go tests faster. It is that it systematizes the parts of unit testing that most often become formalistic: choose the right mode based on risk, list defect hypotheses first, design a Killer Case for each target, and then constrain the final suite with boundary discipline, mutation-resistant assertions, deterministic concurrency control, real coverage / race evidence, and a tiered scorecard.

From a design perspective, the skill expresses a clear principle: **the key to high-quality unit testing is not running more functions once, but being able to explain which bugs the suite is preventing, why certain assertions cannot be removed, which boundaries have been systematically covered, which risks still remain, and whether those conclusions are backed by real `-race` and coverage evidence.** That is why it is especially well suited to Go logic testing, concurrency-sensitive code, and test-quality improvement work.

## 9. Document Maintenance

This document should be updated when:

- the Hard Rules, Execution Modes, Defect-First Workflow, Coverage Gate, Auto Scorecard, Property-Based Testing, Reporting Integrity, or Output Expectations in `skills/unit-test/SKILL.md` change,
- key patterns or examples in `skills/unit-test/references/killer-case-patterns.md`, `bug-finding-techniques.md`, `concurrency-testing.md`, or `property-based-testing.md` change,
- key supporting results in `evaluate/unit-test-skill-eval-report.md` or `evaluate/unit-test-skill-eval-report.zh-CN.md` change.

Review quarterly; review immediately if the mode-selection rules, Killer Case discipline, scorecard structure, or trigger description of `unit-test` change substantially.

## 10. Further Reading

- `skills/unit-test/SKILL.md`
- `skills/unit-test/references/killer-case-patterns.md`
- `skills/unit-test/references/bug-finding-techniques.md`
- `skills/unit-test/references/concurrency-testing.md`
- `skills/unit-test/references/property-based-testing.md`
- `skills/unit-test/scripts/tests/COVERAGE.md`
- `evaluate/unit-test-skill-eval-report.md`
- `evaluate/unit-test-skill-eval-report.zh-CN.md`

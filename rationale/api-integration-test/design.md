---
title: api-integration-test skill design rationale
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-26
applicable_versions: current repository version
---

# api-integration-test Skill Design Rationale

`api-integration-test` is a safety-oriented execution framework for internal API integration tests. Its core idea is: **integration testing should first establish whether the test type is correct, whether the available configuration is sufficient, whether the runtime path is safe, and whether the resulting test can be understood, executed, and audited by the team over time.** That is why the skill turns scope validation, Go-version adaptation, configuration completeness, execution mode, safety gates, build-tag isolation, and structured reporting into a fixed workflow.

## 1. Definition

`api-integration-test` is a skill for gated integration tests against internal Go HTTP / gRPC APIs. It is designed to create, maintain, and run integration tests with real configuration, focusing on contract verification, failure diagnosis, and safe controlled execution. Its output is not just test code. It also includes execution mode, degradation level, required environment variables, exact run commands, and a structured result report.

## 2. Background and Problems

The skill is not solving "people do not know how to write Go tests." It is solving "many so-called integration tests are not reliable in scope, safety, executability, or long-term maintainability."

Without a clear framework, problems usually fall into six categories:

| Problem | Typical consequence |
|---------|---------------------|
| Wrong scope classification | Third-party API tests, unit tests, and internal API integration tests get mixed together and the whole approach is wrong |
| Incomplete configuration is still written as if runnable | Tests contain guessed hosts, credentials, or IDs that only *look* executable |
| Integration tests enter normal `go test ./...` by default | Missing build tags increase CI compile time or even fail in environments without the right dependencies |
| Production protection is too weak | Mis-set environment variables cause tests to hit production services |
| Timeout, retry, and failure-path rules are too loose | Tests hang, retry forever, or only prove success but never prove that failure modes behave correctly |
| Output is not a real deliverable | A few code snippets exist, but no one knows the prerequisites, degradation reason, missing inputs, or exact reproduction command |

The design goal of `api-integration-test` is to decide first whether the task should be done, to what degree it can be done, and whether doing it is safe, before deciding what test code should be generated.

## 3. Comparison with Common Alternatives

Before looking at the details, it helps to compare the skill with a few common alternatives:

| Dimension | `api-integration-test` skill | Asking a model to "write an integration test" | Treating integration tests like ordinary unit tests |
|-----------|------------------------------|-----------------------------------------------|----------------------------------------------------|
| Scope recognition | Strong | Weak | Weak |
| Configuration completeness checks | Strong | Weak | Weak |
| Production safety protection | Strong | Weak | Weak |
| Build-tag isolation | Strong | Weak | Weak |
| Real-config executability | Strong | Medium | Weak |
| Auditability of output | Strong | Weak | Weak |
| Timeout / retry discipline | Strong | Medium | Weak |
| CI integration friendliness | Strong | Medium | Weak |

The skill does not replace general testing ability. It turns "real integration tests against internal APIs" from a vague request into a controlled workflow that can be safely adopted.

## 4. Core Design Rationale

### 4.1 Scope Validation Comes Before Test Authoring

The first Mandatory Gate is Scope Validation. It requires the task to be classified before any test code is written.

This matters because many testing requests sound similar on the surface but require fundamentally different handling:

- Internal HTTP / gRPC API integration tests: in scope for this skill
- Pure unit tests: should be redirected to `unit-test`
- Third-party vendor API tests: should be redirected to `thirdparty-api-integration-test`
- Browser end-to-end journeys: not part of this workflow at all

If this step is skipped, every later best practice may be applied to the wrong problem. `Eval 2` in the evaluation report shows why this matters: with-skill correctly identified the GitHub API as a third-party case, but the current hard-stop wording was still not strong enough to fully prevent test generation. That edge case makes the role of the Scope Gate especially visible.

### 4.2 Go Version Is Its Own Gate

The second Mandatory Gate is the Go Version Gate. It requires reading `go.mod` and adapting the test implementation to the actual Go version.

This gate is not about showing off modern Go features. It is about making sure the generated test style really fits the project. For example:

- `t.Setenv` requires Go 1.17+
- before Go 1.22, range-variable closure capture still needs explicit care
- before Go 1.24, mixing `t.Parallel()` and `t.Setenv()` in the same subtest is unsafe

Without this step, the generated code may look idiomatic in isolation but still be mismatched to the target repository or subtly unsafe in test behavior.

### 4.3 Configuration Completeness Matters More Than "Just Write Something"

The third Mandatory Gate is Configuration Completeness. It splits the outcome into three levels:

- `Full`
- `Scaffold`
- `Blocked`

This is one of the most important design choices in the skill, because one of the biggest integration-test failures is **writing something that looks runnable when the necessary config is not actually known**.

The skill refuses to do that:

- if configuration is complete, generate full tests;
- if some inputs are missing, generate a scaffold with `t.Skip(...)` and `// TODO:` markers;
- if critical inputs are unknown, stop and output only the variable checklist and setup guidance.

This has three practical benefits:

- it avoids guessed endpoints, credentials, or test identifiers,
- it makes missing prerequisites explicit,
- it keeps the generated artifact aligned with its true execution status.

The skill would rather produce an honest scaffold than a fake-complete test that cannot really run.

### 4.4 Execution Mode Is Selected Up Front

The fourth Mandatory Gate is Execution Mode. It automatically classifies the task into `Smoke`, `Standard`, or `Comprehensive`.

This aligns test depth with scenario risk:

| Mode | Typical use | Design purpose |
|------|-------------|----------------|
| `Smoke` | Connectivity checks, first-time environment validation, one read-only endpoint | Answer "does this path work at all?" |
| `Standard` | Most normal internal API integration tests | Balance success-path, failure-path, and business-level assertions |
| `Comprehensive` | Broad coverage, migration validation, high-risk APIs | Add concurrency, large payloads, pagination, rate limiting, and fuller path coverage |

Without mode selection, the workflow usually distorts in one of two ways:

- simple checks become too heavy to use,
- risky APIs are reduced to a shallow "200 OK" smoke check.

### 4.5 Production Safety Must Be a Hard Gate

The fifth Mandatory Gate is Production Safety. It requires:

- `ENV=prod` / `production` to default to `t.Skip`,
- explicit opt-in through `INTEGRATION_ALLOW_PROD=1`,
- an additional explicit gate such as `INTEGRATION_ALLOW_DESTRUCTIVE=1` for destructive operations.

This is the strongest safety layer in the skill. The evaluation report also identifies it as a skill-only capability: with-skill was correct in all three scenarios, while without-skill missed it in all three.

The problem it solves is direct and serious: many integration tests can become production incidents if a gate variable is accidentally enabled. Without this layer, a "test" may become a real write path into production.

And the protection is not a single check. It is defense in depth:

- one gate controls whether integration tests are allowed to run at all,
- another gate ensures that even when running is allowed, production is still blocked by default.

That is why the evaluation report treats it as a safety-critical dimension.

### 4.6 Build-Tag Isolation Is Not a Minor Detail

The skill requires every integration test file to include:

- `//go:build integration`
- `// +build integration`

These two lines may look like a small file-header detail, but they are a major design feature.

The evaluation report shows that without-skill missed them in all three scenarios. The consequences are concrete:

- `go test ./...` still compiles the integration test files,
- CI compile time increases,
- environments without the right integration dependencies may fail before tests even reach the skip path.

So build-tag isolation is not "slightly better style." It is an explicit declaration in code that **this test is not part of the default test path and must be deliberately enabled.**

### 4.7 The Skill Insists on Real Transport Paths vs. Mocking the Core Client

The skill explicitly rejects "integration tests" that mock out the client or transport being integrated against. Once the real `http.Client` or gRPC connection is replaced with a fake, the task has effectively turned back into a unit test.

The design principle here is: **the value of an integration test is to validate the real transport path, real config resolution, and real protocol contract, not merely a business function's return value.**

That is why the skill requires:

- a real client instance, or a real handler plus `httptest` server,
- request construction through production code paths,
- both protocol-level and business-level assertions.

This gives the skill a clear separation from pseudo-integration tests that only imitate the shape of integration.

### 4.8 Timeouts and Retries Are Strictly Bounded

The skill is very explicit about `context.WithTimeout`, bounded retry policy, and checking `ctx.Done()`.

The goal is not "make the test more persistent." It is "make the test more stable without hiding real failures."

If retries and timeouts are left loose, common failures include:

- infinite retries that mask the actual defect,
- hanging tests where it is unclear whether the service is stuck or the test is,
- use of convenience helpers like `http.Post` / `http.Get` that do not accept context and make cancellation behavior opaque.

`Eval 3` in the evaluation report illustrates this clearly: without-skill used `http.Post` directly and lost unified timeout control; with-skill preserved consistent context-based timeouts.

### 4.9 The Skill Requires Both Protocol-Level and Business-Level Assertions

`api-integration-test` is not satisfied with `HTTP 200` or `require.NoError` alone. It requires both:

- protocol-level contract checks: status codes, gRPC codes, required response fields;
- business-level invariants: identity mapping, state transitions, numeric constraints, and similar semantics.

This matters because one of the most common distortions in API integration testing is: "the request succeeded, therefore the test passed." But a successful request does not prove that the returned data or behavior is semantically correct.

The value of this design is that it upgrades the goal from simple connectivity to contract-and-semantics verification.

### 4.10 Structured Output

The skill explicitly requires the shared Output Contract to be loaded when reporting results, and the evaluation report shows that with-skill outputs consistently included information such as:

- Execution Mode
- Degradation Level
- Gate Variables
- Exact Commands
- Timeout / Retry Policy
- Result Summary
- Quality Scorecard

This solves a very practical problem: many teams may get test code, but still have no idea:

- which environment variables it depends on,
- whether the result is full or scaffold-only,
- whether anything actually ran,
- why something was skipped,
- what exact command should be used to reproduce it.

The purpose of structured output is to turn "some test code" into an actual testing deliverable. That is why the evaluation report treats Output Contract as a skill-only differentiator.

### 4.11 Degradation Exists vs. a Binary "Can Write / Cannot Write"

The skill does not reduce the world to "full success" or "total failure." It deliberately supports `Full / Scaffold / Blocked`.

This is a mature design choice because real projects often start from partial information. If the model is given only two outcomes, it tends to fall into one of two bad behaviors:

- writing a fake-complete test when key information is missing,
- stopping entirely at the first missing input and producing nothing useful.

The degradation model allows a third path: an honest, intermediate artifact that can still be completed later. In practice, that is much more valuable than a polished output built on guesses.

### 4.12 CI Integration Comes Last, Not First

The skill does not begin with GitHub Actions, Make targets, or Docker Compose. It first defines scope, safety, configuration requirements, and execution constraints, and only then talks about CI integration.

That ordering reflects a strong design choice: **make sure the test itself is correctly defined before deciding how to wire it into CI.**

Otherwise it is easy to invert the whole process:

- the CI step exists,
- the test appears to run,
- but the test still lacks build tags, prod safety, or explicit gate variables.

Seen this way, CI is an amplifier. The earlier safety and boundary decisions are the foundation.

## 5. Problems This Design Addresses

Cross-referencing `SKILL.md` and the evaluation report, the skill mainly addresses the following engineering problems:

| Problem | Corresponding design | Practical effect |
|---------|----------------------|------------------|
| Wrong test-type classification | Scope Validation Gate | Distinguishes internal APIs, third-party APIs, and unit-test scenarios |
| Generated test style does not fit project Go version | Go Version Gate | Avoids patterns that are invalid or unsafe for the target Go version |
| Incomplete configuration presented as runnable | Configuration Completeness Gate + degradation levels | Keeps output aligned with true executability |
| Integration tests leak into default test runs | Build-tag isolation | Prevents ordinary `go test ./...` from compiling and triggering them |
| Tests accidentally hit production | Production Safety Gate | Blocks production execution by default and requires explicit override |
| Timeout / retry behavior is uncontrolled | `context.WithTimeout` + bounded retry rules | Improves stability without masking real defects |
| Tests only prove "it responds," not "it is correct" | Protocol-level + business-level assertions | Brings tests closer to real contract verification |
| Outputs are not reusable or auditable | Output Contract | Makes prerequisites, result state, gaps, and reproduction commands explicit |

The evaluation data supports this clearly: with-skill overall pass rate was `94.7%`, while without-skill was only `57.9%`; for build-tag isolation, Production Safety Gate, and Output Contract, with-skill was `3/3` and without-skill was `0/3`. So the value is not merely "more complete test code." It is **turning integration testing into a safer, clearer, and more maintainable delivery artifact.**

## 6. Key Highlights

### 6.1 It Asks "Should This Test Be Written?" Before "How Should It Be Written?"

This is the skill's most important strength. Scope validation comes first, which is intended to prevent effort from being invested in the wrong test category. The current evaluation also shows that scope recognition is already strong, even though the hard-stop semantics can still be tightened.

### 6.2 Its Safety Gates Are Unusually Strong

Production Safety Gate, destructive-operation gating, and build-tag isolation work together to make the skill much safer than the baseline in terms of preventing accidental production impact.

### 6.3 It Handles Incomplete Information Honestly

The `Full / Scaffold / Blocked` model is extremely practical. It avoids both extremes: stopping immediately whenever data is missing, and pretending everything is fine when it is not.

### 6.4 The Goal Is Not Just to Run Tests, but to Make Them Diagnosable

Output Contract, Exact Commands, Timeout / Retry Policy, and the Quality Scorecard all show that the skill is not merely trying to generate a test file. It is trying to generate something the team can run, skip, diagnose, and audit.

### 6.5 Its Biggest Advantages Appear Exactly Where the Baseline Is Weakest

The evaluation report shows that most of the skill's unique value appears in the places the baseline most often misses:

- build tags,
- production safety,
- scope recognition,
- structured reporting.

So the skill does not win mainly by "knowing a bit more HTTP / gRPC." It wins by systematically controlling the delivery boundary of integration testing.

## 7. When to Use It — and When Not To

| Scenario | Suitable | Reason |
|----------|----------|--------|
| Writing integration tests against internal HTTP / gRPC APIs with real configuration | Yes | This is the core use case |
| Triage of failing internal API integration tests | Yes | Structured output and execution mode selection help with diagnosis |
| Introducing gated integration tests into CI | Yes | Build tags, environment gates, and structured reporting fit this workflow well |
| Pure unit tests | No | Redirect to `unit-test` |
| Third-party vendor API tests | No | Redirect to `thirdparty-api-integration-test` |
| Browser end-to-end flows | No | This is outside API integration-test scope |

## 8. Conclusion

The real strength of `api-integration-test` is not that it can write a request and an assertion. It is that it systematizes the parts of internal API integration testing that most often go wrong: validate scope first, confirm Go version and config state, choose the right execution mode, and then constrain the final artifact with production safety, build tags, timeout / retry rules, contract assertions, and structured reporting.

From a design perspective, the skill is a strong example of production-grade integration-testing principles: **make sure the test type and runtime assumptions are correct before chasing coverage; set the safety boundary before allowing execution; make missing coverage explicit before calling the result "done."** That is why it is especially well suited to real internal API environments rather than as a generic replacement for all testing work.

## 9. Document Maintenance

This document should be updated when:

- the Mandatory Gates, Execution Modes, Safety Rules, or Output Contract in `skills/api-integration-test/SKILL.md` change,
- the scope gate, output format, mode examples, or advanced patterns in `skills/api-integration-test/references/*.md` change,
- key data in `evaluate/api-integration-test-skill-eval-report.md` that supports the claims here changes,
- the project's conventions for internal API integration tests, production protection, CI execution, or gate environment variables change.

Review quarterly; review immediately if the `api-integration-test` skill undergoes substantial refactoring.

## 10. Further Reading

- `skills/api-integration-test/SKILL.md`
- `skills/api-integration-test/references/common-integration-gate.md`
- `skills/api-integration-test/references/common-output-contract.md`
- `skills/api-integration-test/references/checklists.md`
- `skills/api-integration-test/references/internal-api-patterns.md`
- `skills/api-integration-test/references/advanced-patterns.md`
- `evaluate/api-integration-test-skill-eval-report.md`

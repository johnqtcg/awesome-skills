---
title: thirdparty-api-integration-test skill design rationale
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-27
applicable_versions: current repository version
---

# thirdparty-api-integration-test Skill Design Rationale

`thirdparty-api-integration-test` is a safety-oriented execution framework for Go third-party API clients. Its core idea is: **the hard part of third-party API integration testing is keeping tests in the correct scope under real configuration, real vendors, real cost and quota constraints, preserving reproducible evidence, and classifying failures more clearly into configuration, auth, network, timeout, contract, or other actionable causes when something goes wrong.** That is why the skill turns Scope Validation, the Required Pattern, the Configuration Gate, Vendor-Specific Safety Additions, Safety Rules, the shared Output Contract, and selective references into one constrained workflow.

## 1. Definition

`thirdparty-api-integration-test` is used for:

- writing and running real integration tests for Go third-party API clients,
- verifying vendor contracts and business semantics under real configuration,
- restricting tests to opt-in execution through explicit gates, build tags, and production protection,
- triaging external-call failures in a structured way,
- and turning high-cost, high-risk third-party integration checks into auditable deliverables.

Its output is not just test code. It also includes:

- integration target,
- gate variable and required env vars,
- exact run commands,
- timeout and retry policy,
- result summary,
- failure classification,
- missing prerequisites.

From a design perspective, it is closer to a third-party integration-testing governance framework than to a prompt that merely fills in a few Go integration tests.

## 2. Background and Problems

The skill is not solving "models cannot write Go API tests." It is solving the fact that third-party API integration tests are naturally more accident-prone than internal API tests:

- real calls consume vendor quota, money, or rate-limit budget,
- credentials, tenant IDs, and resource IDs often depend on runtime environment,
- failures may come from config, auth, network, vendor contract changes, or business semantics, not just local code.

Without an explicit process, failures usually cluster into eight categories:

| Problem | Typical consequence |
|---------|---------------------|
| Scope is classified incorrectly | Internal API tests, third-party API tests, and unit tests get mixed together and the whole strategy is wrong |
| No independent run gate exists | If credentials happen to be present in local shell or CI, tests are triggered accidentally |
| Production protection is missing | `ENV=prod` sends traffic directly to real vendors |
| No build-tag isolation exists | `go test ./...` or default CI paths accidentally trigger paid APIs |
| Env var parsing and validation are sloppy | Whitespace, malformed IDs, or bad list values make failures unpredictable |
| Assertions stop at `err == nil` or `HTTP 200` | Real contract regressions and semantic drift are hidden |
| Test data lifecycle is not defined | Shared tenants or IDs get polluted and tests stop being repeatable |
| Output is unstructured | Teams do not know what command to run, which variables are missing, or what class of failure occurred |

The design logic of `thirdparty-api-integration-test` is to make "is this really a third-party vendor API, are the prerequisites complete, is the current environment allowed, is the test data safe, and how should failures be classified?" explicit before deciding what code to generate.

## 3. Comparison with Common Alternatives

It helps to compare it with a few common alternatives:

| Dimension | `thirdparty-api-integration-test` skill | Asking a model to "write a third-party API integration test" | Treating third-party calls like ordinary unit tests |
|-----------|-----------------------------------------|--------------------------------------------------------------|-----------------------------------------------------|
| Scope routing | Strong | Weak | Weak |
| Explicit gate design | Strong | Weak | Weak |
| Production safety | Strong | Weak | Weak |
| Build-tag isolation | Strong | Weak | Weak |
| Env var parsing and validation | Strong | Medium | Weak |
| Protocol-level + business-level assertions | Strong | Medium | Weak |
| Failure classification and structured reporting | Strong | Weak | Weak |
| Safety awareness for paid / rate-limited vendors | Strong | Weak | Weak |

Its value is not only that the test can call a third-party API. Its value is that it turns third-party API testing from a high-risk improvised action into a controlled, reproducible, and auditable workflow.

## 4. Core Design Rationale

### 4.1 Scope Validation Comes Before Test Authoring

The first gate in `thirdparty-api-integration-test` is Scope Validation. It requires the target to be classified first:

- third-party HTTP / gRPC API client: proceed,
- internal service / handler: redirect to `api-integration-test`,
- pure unit test: redirect to `unit-test`,
- browser end-to-end flow: declare out of scope.

This matters because "write an API integration test" sounds similar across cases, but the risk model is completely different for third-party APIs. Internal APIs are under your control; third-party APIs involve:

- quota and cost,
- auth and tenant isolation,
- vendor versions and rate limits,
- external failure modes you do not control.

The evaluation's clearest differentiation appears here: in the internal webapp scenario, with-skill explicitly recognized that the target was not a third-party API and recommended the correct skill, while without-skill still wrote good internal tests but performed no scope analysis.

One nuance matters here: the current `SKILL.md` now presents this as an explicit `Scope Validation Gate`, while the existing evaluation report still uses wording from an earlier snapshot and describes the boundary judgment as inferred from the skill's scope definition. Under either reading, the design value is the same: the point of this layer is not better code generation by itself, but avoiding the wrong testing strategy.

### 4.2 The Required Pattern Hard-Codes Gates, Build Tags, and Production Protection

The skill's Required Pattern is intentionally rigid:

1. the file must be named `<client>_integration_test.go`,
2. the file must include dual build tags,
3. an independent run gate env var must exist,
4. runtime env vars must be validated up front,
5. production must be refused by default.

These rules look like template mechanics, but they are really the structural skeleton of the skill. The problem they solve is not formatting consistency. They solve:

- accidental execution,
- default CI paths running high-cost tests,
- credentials being treated as the only execution gate,
- production traffic reaching real vendors by mistake.

The evaluation shows that gate-env isolation, Production Safety Gate, and build-tag isolation are the most stable deltas. That means the skill's first-order value comes from controlling execution boundaries, not from assertion details.

### 4.3 An Explicit Gate Env Var Is One of the Highest-Leverage Design Choices

`thirdparty-api-integration-test` explicitly requires:

- a dedicated gate env var such as `THIRDPARTY_INTEGRATION=1` or a vendor-specific equivalent,
- credentials to be used only for authentication, not for deciding whether the test should run.

This is crucial because if `GITHUB_TOKEN`, `OPENAI_API_KEY`, or similar credential vars act as implicit gates, then any local shell, CI secret store, or shared runner that already contains those values can trigger the test accidentally.

The GitHub evaluation scenario makes this concrete: with-skill used a two-level gate with `GITHUB_INTEGRATION=1` plus `GITHUB_TOKEN`; without-skill relied only on `GITHUB_TOKEN`. That difference is easy to miss in manual review, but in automation it is the difference between "explicitly safe" and "dangerous by default."

### 4.4 The Production Safety Gate Must Be Hard

The skill explicitly requires:

- `ENV=prod` / `production` to default to `t.Skip`,
- override to be allowed only with `INTEGRATION_ALLOW_PROD=1`.

This is one of the most safety-critical parts of the design. For third-party APIs, production is not an abstract risk. It means:

- real charges for paid APIs,
- real quota consumption,
- rate-limit policies getting triggered,
- real tenant or account side effects.

The evaluation also marks this as a skill-only capability: with-skill was `3/3`, without-skill was `0/3`. In other words, production protection in third-party API testing is not an extra refinement. It is the minimum barrier to safe execution.

### 4.5 Env Var Parsing and Validation Are So Detailed

The skill does not only require env vars to be read. It requires:

- `strings.TrimSpace`,
- `strconv.ParseInt`,
- per-element validation for comma-separated lists,
- `t.Logf` for parsed non-sensitive values.

This is highly practical because third-party API tests often depend on:

- tenant IDs,
- label IDs,
- target resource IDs,
- region,
- config paths.

If those values are malformed, failures become vague and expensive to debug. By validating them early, the skill turns "the test failed mysteriously at runtime" into "the prerequisites are incomplete or malformed before execution even begins." That is why env-var validation created a measurable quality delta in the evaluation.

### 4.6 The Skill Insists on Real Clients and Real Execution Paths

The skill explicitly requires:

- client construction through the project's real config loader,
- production code paths for request wiring,
- real external calls.

The problem this solves is that many so-called third-party API integration tests actually mock out the transport and only verify local request assembly. That can still be useful, but it is no longer the target of this skill.

`thirdparty-api-integration-test` is preserving the contract-verification layer:

- can config really construct the client,
- can the request really reach the vendor,
- does the response still satisfy the protocol,
- do business semantics still hold.

That gives it a clear boundary from ordinary unit tests or fake-based tests.

### 4.7 It Requires Both Protocol-Level and Business-Level Assertions

The skill is not satisfied with checking only:

- status code,
- non-empty fields,
- `require.NoError`.

It requires both:

- protocol-level contract checks,
- business-level invariant checks.

This matters because one of the most common false positives in third-party API testing is:

- the request went through,
- an object came back,
- the test ended there.

But a vendor API can keep returning `200 OK` while still regressing semantically, for example:

- inconsistent identifiers,
- changed field meanings,
- drift in state semantics.

The GitHub and OpenAI evaluation scenarios both show that the base model already writes basic assertions; the skill's increment is making "the protocol passed" and "the business meaning is still correct" part of the same test objective.

### 4.8 Expected Failure Paths Must Assert Explicit Error Type or Code

The skill explicitly says that expected failure paths must not stop at `require.Error`; they must assert specific error type and/or code.

This is important because failure behavior is often part of the third-party API contract itself. For example:

- a 404 becomes a 403,
- an auth failure becomes a generic 500,
- a vendor SDK wraps the error in a different concrete type.

If the test only checks `err != nil`, those important regressions remain hidden. The GitHub 404 scenario in the evaluation is the clearest example: with-skill checked `*statusError` and 404; without-skill could only prove that "some error occurred."

### 4.9 Test Data Lifecycle Must Be Declared Explicitly

`thirdparty-api-integration-test` requires test-data lifecycle to be explicit:

- setup source,
- idempotency-key strategy,
- cleanup or safe-reuse policy.

This is mature design because third-party API tests are not naturally repeatable the way local unit tests are. Many risks live in the data layer:

- shared tenants get polluted,
- the same IDs are consumed repeatedly,
- mutation endpoints leave behind dirty state.

By forcing lifecycle declaration, the skill makes "what data this test uses, whether it can be rerun, and whether cleanup is required" part of the design instead of leaving it buried in implementation details.

### 4.10 Vendor-Specific Safety Additions Prefer Idempotent Defaults

The skill explicitly prefers:

- idempotent endpoints by default,
- dedicated test tenant / account plus explicit opt-in gate for mutation endpoints,
- rate-limit failures to be classified as rate-limit rather than contract regressions.

This is a focused design choice because one of the biggest differences between third-party APIs and internal APIs is that you cannot fully control side-effect cost. The skill therefore narrows the default execution path to low-risk calls first, and turns higher-risk mutation flows into separately authorized actions.

That is also why it has dedicated rules for paid APIs, rate-limit headers, `Retry-After`, and secret logging. It is not trying to be broad for its own sake. It is trying to be safe by default.

### 4.11 Shared Output Contract

The skill requires every run to report at least:

- integration target,
- gate vars,
- exact commands,
- timeout / retry policy,
- result summary,
- failure classification,
- missing prerequisites.

This solves a practical team problem: even after receiving the test code, people often still do not know:

- which variables must be set,
- what command should be run,
- why the test is currently skipped,
- whether the failure is config-related or contract-related.

Structured output upgrades "a test file" into "a testing deliverable." The evaluation showed this as another skill-only differentiator: with-skill reports directly supported reproduction and triage, while without-skill returned only brief summaries.

### 4.12 References Are Loaded by Task Shape

The references for `thirdparty-api-integration-test` are not meant to be read all at once:

- `common-integration-gate.md` is always required,
- `common-output-contract.md` is always required,
- `checklists.md` is loaded for authoring or triage,
- `vendor-examples.md` is loaded when no vendor pattern exists in the repo.

This is sensible because some parts of third-party API testing are shared concerns:

- gate design,
- production safety,
- output contract.

Other parts are vendor-shaped templates and execution examples. Selective loading keeps the high-frequency shared rules in `SKILL.md`, defers lower-frequency templates, improves instruction density, and keeps token cost under control. The evaluation's token data supports this directly: a very small `SKILL.md` still achieved strong cost-effectiveness.

## 5. Problems This Design Solves

Combining the current `SKILL.md`, key references, and the evaluation report, the skill solves the following problems:

| Problem type | Corresponding design | Practical effect |
|--------------|----------------------|------------------|
| Third-party and internal API tests are mixed together | Scope Validation Gate | Makes test strategy more accurate |
| Credentials accidentally trigger test execution | Explicit gate env var | Makes run boundaries clearer |
| Tests hit production vendors by mistake | Production Safety Gate | Makes cost and side effects safer |
| Paid or high-cost tests leak into default paths | Build-tag isolation | Makes CI and local default paths safer |
| Env var formats are fragile | TrimSpace + ParseInt + validation | Exposes issues before execution |
| Tests only prove "it responded" | Protocol + business dual assertions | Makes contract verification more complete |
| Failures are hard to triage | Failure classification + output contract | Makes diagnosis more direct |
| Test data gets polluted or becomes non-repeatable | Lifecycle policy | Makes tests more reusable |

## 6. Key Highlights

### 6.1 It Treats Third-Party API Testing as a Safety Problem Before a Test-Writing Problem

Execution boundaries are controlled first; assertion details come second. That is the skill's most important design choice.

### 6.2 Explicit Gate, Production Safety, and Build Tags Form a Clear Safety Loop

Together, these rules make third-party integration tests opt-in, isolated, and production-safe by default.

### 6.3 Its Scope-Boundary Recognition Is Highly Distinctive

It does not just write tests. It also decides when it should not be used and redirects the task to a more appropriate skill.

### 6.4 It Makes Diagnosability a First-Class Goal

Failure classification, missing prerequisites, and exact commands let a failed test feed directly into triage instead of leaving only a red signal.

### 6.5 It Is Sensitive to High-Cost Vendor Scenarios

Paid APIs, rate limits, mutation endpoints, tenant pollution, and secret logging are all encoded into default rules.

### 6.6 Its Real Increment Is Execution Governance, Not Basic Test-Authoring Ability

The evaluation already shows that the base model can write `context.WithTimeout`, basic assertions, real-client paths, and correct file naming. The real difference comes from gate env vars, production safety, build tags, error precision, scope analysis, and structured output. That means the core value of `thirdparty-api-integration-test` is governance of third-party testing, not merely "better Go integration-test code."

## 7. When to Use It — and When Not To

| Scenario | Suitable | Reason |
|----------|----------|--------|
| Third-party vendor HTTP / gRPC API client tests | Very suitable | This is the core use case |
| Triage of failing real external calls | Very suitable | Failure classification and output contract help directly |
| Gated regression for paid or rate-limited APIs | Very suitable | Default safety boundaries are strong |
| Internal HTTP / gRPC API testing | Not suitable | Redirect to `api-integration-test` |
| Pure unit tests | Not suitable | Redirect to `unit-test` |
| Browser E2E flows | Not suitable | Fully out of scope |

## 8. Conclusion

The real strength of `thirdparty-api-integration-test` is not that it can write one third-party API call. It is that it systematizes the parts of third-party integration testing that most often become unsafe or ambiguous: validate scope first, establish explicit gates, production protection, and build-tag isolation, then constrain env vars, real-client paths, protocol and business assertions, failure classification, and test-data lifecycle, and finally deliver the run result in a structured form.

From a design perspective, the skill expresses a clear principle: **the key to high-quality third-party API integration testing is not getting one request to pass quickly, but ensuring every real external call is safe by default, controlled by default, diagnosable by default, and understandable to the team in terms of when it should run, why it did not run, what class of failure occurred, and how to reproduce it next.** That is why it is especially well suited to vendor contract verification, external-call failure triage, and gated regression checks for high-cost APIs.

## 9. Document Maintenance

This document should be updated when:

- the Scope Validation Gate, Required Pattern, Configuration Gate, Vendor-Specific Safety Additions, Safety Rules, or Output Contract in `skills/thirdparty-api-integration-test/SKILL.md` change,
- key gates, report formats, checklists, or vendor templates in `skills/thirdparty-api-integration-test/references/common-integration-gate.md`, `common-output-contract.md`, `checklists.md`, or `vendor-examples.md` change,
- key supporting results in `evaluate/thirdparty-api-integration-test-skill-eval-report.md` or `evaluate/thirdparty-api-integration-test-skill-eval-report.zh-CN.md` change.

Review quarterly; review immediately if the scope routing, explicit gate rules, production safety, build-tag rules, or output contract of `thirdparty-api-integration-test` change substantially.

## 10. Further Reading

- `skills/thirdparty-api-integration-test/SKILL.md`
- `skills/thirdparty-api-integration-test/references/common-integration-gate.md`
- `skills/thirdparty-api-integration-test/references/common-output-contract.md`
- `skills/thirdparty-api-integration-test/references/checklists.md`
- `skills/thirdparty-api-integration-test/references/vendor-examples.md`
- `evaluate/thirdparty-api-integration-test-skill-eval-report.md`
- `evaluate/thirdparty-api-integration-test-skill-eval-report.zh-CN.md`

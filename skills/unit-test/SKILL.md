---
name: unit-test
description: 'Use when the user asks for unit tests (e.g, "单元测试", "unit test"), wants to add/fix Go tests, wants table-driven and subtest organization, or wants to enforce a minimum coverage gate (default 80% for logic packages). Prioritize bug discovery (especially boundary, mapping loss, and concurrency defects) over test volume. Do NOT use for benchmarks, fuzz tests, integration tests, E2E tests, load tests, or mock generation.'
---

# Go Unit Test

Create and refine Go tests for this repository with table-driven cases and explicit bug-hunting rules.

## Hard Rules

- Name test files as `<target_file>_test.go`, co-located with source.
- Assertion strategy (adapt to project):
  - **If project uses testify**: `require` for fatal preconditions, `assert` for value checks.
  - **If project uses standard library only**: use `t.Fatalf` for fatal preconditions, `t.Errorf` for value checks. Include got/want in messages: `t.Errorf("Name = %q, want %q", got, want)`.
  - **If project uses go-cmp**: use `cmp.Diff` for deep struct comparison. Prefer over field-by-field assertion for complex output.
  - **Detection**: Check existing `_test.go` files for `"github.com/stretchr/testify"` imports. Follow project convention.
- Keep tests deterministic; isolate time, randomness, environment, and network.
  - Prefer `t.Setenv` for env changes; avoid leaking global state between tests.
- Prefer stable fakes/stubs over heavy mock chains.
  - Unit tests SHOULD NOT require real external services (DB/Redis/HTTP) unless explicitly requested; that belongs to integration tests.
- Do NOT test constructors (`NewXxx`) or private helpers unless explicitly requested **OR** they contain non-trivial logic (validation/defaulting/option-merging) that can break runtime invariants.
- For service-layer code with interfaces, focus on methods declared in the interface. For pure functions/handlers, focus on exported functions/endpoints.
- Run with race detector: `go test -race ./...`.
- **Killer Case hard constraint**: each test target (interface method / exported function / handler endpoint) must include at least 1 "killer case" (fault-injection or boundary-kill case) that is expected to fail on a known bad mutation/path.
- In the report, for each killer case, explicitly state: **"if this assertion is removed, the known bug can escape detection."**

### Killer Case — Definition

A **killer case** is a test case designed to catch a specific, named defect. It has four mandatory components:

1. **Defect hypothesis**: a concrete statement of what could go wrong (e.g., "loop uses `i < len-1` instead of `i < len`, dropping the last element")
2. **Fault injection or boundary setup**: test input that triggers the defect if present
3. **Critical assertion**: the specific `assert`/`require` call that would fail if the defect exists
4. **Removal risk statement**: "if this assertion is removed, the known bug can escape detection"

A killer case is NOT just another edge case — it is explicitly tied to a defect hypothesis. If you cannot name the defect it catches, it is not a killer case.

See `references/killer-case-patterns.md` for 6 concrete Go templates.

### Anti-examples (DO NOT write these tests)
- Testing Go standard library behavior (e.g., json.Marshal serializes struct correctly)
- Testing trivial getters/setters with no logic
- Testing constructor NewXxx that only assigns fields (unless it has validation/defaulting)
- Writing one case per possible string input instead of using representative boundaries
- Asserting only `err == nil` without verifying the returned value
- Tests that depend on execution order of other tests
- Tests that assert log output format (fragile, couples to logging implementation)
- Mocking everything: if you mock 5+ dependencies, the test tests the mocks, not the code
- Over-reliance on snapshot/golden files for volatile output (timestamps, UUIDs, map iteration order) — golden files are fine for stable serialization formats, but not for output that changes across runs
- Testing implementation details instead of behavior: asserting internal method call order, private field values, or specific goroutine scheduling rather than observable outputs and side effects

### Coverage Gate Policy (Default + Scope)

- Coverage gate: **>= 80%** by default **for logic-heavy packages** (pure/domain/transform code).
- For integration-heavy/IO-heavy packages (infra, clients, wiring, DB adapters):
  - Coverage may be lower (typical **60–80%**) **only with explicit rationale**.
  - Even when coverage is lower, **Failure Hypothesis coverage, Boundary Checklist discipline, and Killer Case discipline remain mandatory**.
- Never inflate coverage by adding low-signal tests with weak assertions.

#### Multi-Package Coverage

When testing spans multiple packages:
- Use `-coverpkg=./...` to measure cross-package coverage accurately.
- Packages with no `_test.go` files report 0% — exclude them from gate calculations with explicit rationale.
- Generate separate `coverprofile` per package when fine-grained analysis is needed:
  ```bash
  go test -coverprofile=pkg_a.out -covermode=atomic ./pkg/a
  go test -coverprofile=pkg_b.out -covermode=atomic ./pkg/b
  ```

### Go Version Gate

Before generating tests, check `go.mod` for the project's Go version. Adapt test patterns accordingly:

| Feature | Minimum Go Version | Adaptation |
|---|---|---|
| `t.Setenv` | 1.17 | Below 1.17: use `os.Setenv` + `t.Cleanup` |
| Range var capture fix | 1.22 | Below 1.22: copy loop variable in `t.Run` + `t.Parallel()` closures |
| `t.Parallel()` + `t.Setenv` safe | 1.24 | Below 1.24: do NOT combine `t.Parallel()` with `t.Setenv` in the same subtest |

If `go.mod` cannot be read, state the assumption and proceed with Go 1.21 defaults.

### Test Execution Hardening

- **Shuffle**: Run with `go test -shuffle=on` to catch tests that depend on execution order. If any test fails only under shuffle, it has hidden state coupling — fix the test, not the ordering.
- **Fuzzing collaboration**: When a function already has a fuzz test (`func FuzzXxx`), unit tests should cover structured boundary cases that fuzzing is unlikely to find (e.g., specific business rule violations, multi-field interaction). Do not duplicate what fuzzing covers (random byte input, crash discovery). If fuzzing is appropriate but missing, note it in the report as a recommendation.

### PR-Diff Scoped Testing

When testing in a CI / PR review context:

- Determine changed packages from `git diff --name-only origin/main...HEAD | grep '\.go$' | xargs -I{} dirname {} | sort -u`.
- Run tests only for changed packages and their direct dependents: `go test -race ./changed/pkg/... ./dependent/pkg/...`.
- Coverage gate applies only to changed packages (not the entire repo).
- If a changed package has no `_test.go` file, flag it in the report as a gap.

### Generated Code Exclusion

Do NOT generate tests for files matching these patterns:
- `*.pb.go` (protobuf generated)
- `*_gen.go`, `wire_gen.go` (code generators)
- `mock_*.go`, `*_mock.go` (generated mocks)
- Files containing the directive `// Code generated .* DO NOT EDIT`

If the user explicitly requests testing generated code, proceed but note that generated files are typically validated by their generator's own test suite.

## Repository Config (Optional)

When present, load repository config from `.unit-test.yaml` (or `.unit-test.json`) before test generation.

Config keys:

- `coverage.logic_min`: default minimum coverage for logic-heavy packages (default `80`)
- `coverage.infra_min`: minimum coverage for infra-heavy packages when policy is stricter than default (optional)
- `coverage.package_rules`: per-package overrides with explicit rationale
- `assertion_style`: `auto|testify|stdlib|go-cmp` (prefer `auto`)
- `race.required`: whether `-race` execution is mandatory in this repo (`true|false`)
- `commands.test`: custom test command template
- `commands.coverage`: custom coverage command template

If config is missing, use this skill's defaults and state: `Repository unit-test config not found; using skill defaults`.

## Target Type Adaptation

Adapt test organization based on the target code type:

| Target Type | Top-level Test Naming | t.Run Organization | Killer Case Granularity |
|---|---|---|---|
| Service interface | TestXxxService | By interface method | 1 per interface method |
| Package-level functions | TestFuncName | By function | 1 per exported function |
| HTTP handler | TestHandlerName | By HTTP method + path | 1 per endpoint |
| CLI command/runner | TestRunnerXxx | By command/subcommand | 1 per command |
| Middleware | TestMiddlewareName | By pass-through / block / error | 1 per middleware |

**HTTP handler tests**: use `httptest.NewRequest` + `httptest.NewRecorder`. Verify status code, response body, headers. Inject dependencies via Deps struct or handler constructor.

**Pure function tests**: direct table-driven, no mock needed. Focus on input boundaries and output correctness.

## Defect-First Workflow (Mandatory)

Before writing cases, produce a short **Failure Hypothesis List** from the target code:

1. Loop/index risks: `i < n`, `i <= n`, `i+1`, `n-1`, slice/map access.
2. Collection transform risks: input->output cardinality mismatch, dropped first/last item, wrong key mapping.
3. Branching risks: terminal state branch, empty/singleton branch, error short-circuit branch.
4. Concurrency risks: goroutine error fan-in, shared variable writes, panic recovery path.
5. Context/time risks: `context.Canceled`, `DeadlineExceeded`, missing ctx propagation, timeout not enforced.

Then map each hypothesis to at least one concrete test case name.

Then define at least one **killer case** per test target and map it to a specific defect hypothesis.

If this mapping is missing, do not proceed to large test generation.

## High-Signal Test Budget (Anti-Bloat)

Avoid generating huge suites with weak assertions.

For each test target, use this default budget first:

- 1 happy path
- 1 terminal/last-element boundary path
- 1 empty or single-element path
- 1 dependency error propagation path per critical dependency
- 1 invariant/path-completeness path
- 1 killer case (mandatory)

Typical high-signal range: **5-12 cases per target**.
Only exceed it when new cases cover distinct logic paths.

## Bug-Finding Techniques → `references/bug-finding-techniques.md`

| # | Technique | Key Rule |
|---|-----------|----------|
| 1 | Mutation-Resistant Assertions | Assert concrete business fields, not just `!= nil` |
| 2 | Collection Mapping Completeness | Assert len + identity + first/middle/last for transforms |
| 3 | Off-by-One Precision | Test n=0,1,2,3 for every index boundary |
| 4 | Dependency Error Propagation | Inject failure per dependency, verify no partial payload |
| 5 | Concurrency & Panic Recovery | Channel barriers, -race, panic recovery path → also see `references/concurrency-testing.md` |
| 6 | Branch Completeness | Both branches: marker behavior + payload completeness |
| 7 | Killer Case Design | Fault-injection tied to defect hypothesis → also see `references/killer-case-patterns.md` |

For detailed patterns and Go code examples, load the reference file.

## Fixed Boundary Checklist (Per Test Target)

Mark each item as `Covered` or `N/A (reason)`:

1. `nil` input (only if parameter is pointer/interface/map/slice/channel/function)
2. empty value/collection
3. single element (`len == 1`)
4. size/index boundary (`n=2`, `n=3`, last element)
5. min/max value boundary (`x-1`, `x`, `x+1`) if numeric
6. invalid format/type
7. zero-value struct/default trap
8. error from each critical dependency
9. context cancellation/deadline propagation (if method accepts/uses `context.Context`)
10. concurrent/race behavior (if stateful or goroutine-based)
11. mapping completeness (`no dropped first/middle/last item`)
12. killer case present and mapped to a concrete defect hypothesis

## Test Structure Standard

1. Top-level test naming follows the [Target Type Adaptation](#target-type-adaptation) table.
2. `t.Run` groups map to test targets (interface methods, exported functions, or endpoints).
3. Use table-driven cases inside each group.
4. Keep case names defect-oriented and readable in `go test -v`.
5. Prefer `t.Parallel()` for independent subtests.
  - Do NOT use `t.Parallel()` when subtests share mutable globals, temp dirs without isolation, or process-wide resources.

## Incremental Mode (Fix / Add Tests)

When the task is fixing failing tests or adding tests to existing code, use these simplified flows instead of the full workflow.

### Fix failing test:
1. Read failing test and target code
2. Identify root cause: test bug vs implementation bug
3. Fix the actual bug side (do NOT weaken assertions just to make tests pass)
4. Run `go test -run TestXxx -v -race` to verify the fix
5. Skip full 13-check scorecard and use incremental scorecard only.

### Add tests for existing code:
1. Read target code, identify untested paths
2. Build targeted Failure Hypothesis List (only for uncovered paths)
3. Design cases for gaps only (do not rewrite existing tests)
4. Run coverage diff: compare before/after
5. Simplified Scorecard: only verify items 5, 7, 8, 11 for new cases.

### Coverage recovery:
1. Run `go test -coverprofile=before.out`
2. Identify uncovered lines with `go tool cover -func=before.out`
3. Write targeted cases for uncovered branches
4. Verify coverage gate met

## Workflow

1. Check `go.mod` for Go version; note version-dependent test pattern adaptations (see Go Version Gate).
2. Exclude generated code files from test scope (see Generated Code Exclusion).
3. Read target code and identify test targets (interface methods, exported functions, handler endpoints).
4. Build Failure Hypothesis List (loops, mapping, branch, concurrency, context/time).
5. For each target, define 1 mandatory killer case and bind it to one hypothesis.
6. Design minimal high-signal cases (5-12/target baseline).
7. Implement tests with strong field-level assertions.
8. Run focused tests:
  - `go test ./path/to/pkg -run TestXxx -v -race`
9. Run package tests:
  - `go test ./path/to/pkg -race`
10. Measure coverage (prefer atomic for concurrency safety):
  - `go test ./path/to/pkg -coverprofile=coverage.out -covermode=atomic -race`
  - `go tool cover -func=coverage.out`
11. If coverage < required gate OR key hypotheses untested, add targeted cases only.
12. Verify killer case integrity in report (required assertion present + removal risk statement).

### Reporting Integrity (Mandatory)

- Do NOT claim `-race` or coverage results unless you actually ran the commands and observed output.
- If you cannot run commands in the current environment, say so, and output the exact commands for the user to run plus what to look for.

## Auto Scorecard (13 Checks)

Score each item `PASS` / `FAIL` / `N/A (reason)`. Output `Total: X/13` and final result.

Each item has a weight tier that determines its impact on the final verdict:

| Tier | Items | Rule |
|------|-------|------|
| **Critical** (must PASS) | 5, 11, 13 | Any Critical FAIL → overall FAIL regardless of total |
| **Standard** | 7, 8, 9, 10, 12 | Must achieve >= 4/5 Standard PASS |
| **Hygiene** | 1, 2, 3, 4, 6 | Must achieve >= 4/5 Hygiene PASS |

Applicability:

- Full scorecard is mandatory for full test generation workflows.
- For incremental mode, use simplified scorecard only (items 5, 7, 8, 11), and explicitly state `Incremental mode: full scorecard skipped`.

1. **[Hygiene]** File naming and location are correct.
2. **[Hygiene]** Top-level test naming follows the Target Type Adaptation table.
3. **[Hygiene]** `t.Run` groups map 1-to-1 to test targets.
4. **[Hygiene]** Table-driven style is used for test cases.
5. **[Critical]** Assertions are mutation-resistant (business fields, not existence-only).
6. **[Hygiene]** Happy path is covered.
7. **[Standard]** Critical dependency error paths are covered.
8. **[Standard]** Boundary checklist items are explicitly marked Covered/N/A.
9. **[Standard]** Collection mapping completeness is asserted (length + identities + first/middle/last).
10. **[Standard]** Terminal/last-element branch behavior is asserted.
11. **[Critical]** Killer case exists for every target and is linked to a defect hypothesis.
12. **[Standard]** `-race` execution result is reported (or marked N/A with rationale if not runnable here).
13. **[Critical]** Coverage meets gate for the package category (logic >= 80%; infra per rationale) OR marked N/A with explicit justification.

Final PASS only when:

- All 3 Critical items (5, 11, 13) are PASS (or N/A with explicit rationale **and** hypothesis coverage is complete), and
- Standard tier: >= 4/5 PASS, and
- Hygiene tier: >= 4/5 PASS, and
- total >= 11/13.

Otherwise: FAIL, with missing items and next targeted test additions.

## Output Expectations

Include:

- Targets tested + case counts
- Go version (from `go.mod`) and version-dependent adaptations applied
- Generated files excluded from scope (list, or "none")
- Failure Hypothesis List and which case covers each
- Killer case list per target:
  - case name
  - linked defect hypothesis
  - critical assertion(s)
  - mandatory statement: "if this assertion is removed, the known bug can escape detection."
- Boundary checklist per target (Covered/N/A + reason)
- Coverage and race results (or N/A + exact commands)
- Scorecard and final PASS/FAIL
- Remaining untested risks (if any)

For list/transform logic, include explicit statement:

- whether first/middle/last items were validated
- whether output cardinality and identity completeness were validated

### Machine-Readable Summary (JSON)

Also output a compact JSON block for CI/pipeline ingestion:

```json
{
  "summary": {
    "pass": true,
    "score": "12/13",
    "go_version": "1.22"
  },
  "targets": [
    {
      "name": "TestOrderService",
      "type": "Service interface",
      "cases": 8,
      "killer_cases": 2,
      "hypothesis_covered": ["H1", "H3"]
    }
  ],
  "coverage": {
    "package": "internal/domain/order",
    "line_pct": 87.5,
    "gate": 80,
    "met": true
  },
  "race": {
    "executed": true,
    "clean": true
  },
  "scorecard": {
    "critical_pass": 3,
    "critical_total": 3,
    "standard_pass": 5,
    "standard_total": 5,
    "hygiene_pass": 4,
    "hygiene_total": 5
  }
}
```

## Skill Maintenance
Run regression checks for this skill with:

```bash
bash "<path-to-skill>/scripts/run_regression.sh"
```

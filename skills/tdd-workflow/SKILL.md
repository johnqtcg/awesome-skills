---
name: tdd-workflow
description: Enforce practical Test-Driven Development for code changes in Go services. Use for new features, bug fixes, refactors, API changes, and new modules. Requires Red-Green-Refactor evidence, defect-hypothesis-driven tests, killer cases, and coverage gates (line + risk-path).
allowed-tools: Read, Write, Grep, Glob, Bash(go test*), Bash(go build*), Bash(go vet*)
---

# Go TDD Workflow

Apply TDD end-to-end: write failing tests first, implement minimal code, refactor safely, and prove quality with coverage plus risk-path checks.

## Hard Rules

- Start with tests, not implementation.
- Preserve visible `Red -> Green -> Refactor` evidence in commands/output.
- Keep test files co-located and named `<target>_test.go`.
- Assertion strategy (adapt to project):
  - **If project uses testify**: `require` for fatal preconditions, `assert` for value checks.
  - **If project uses standard library only**: use `t.Fatalf` for fatal, `t.Errorf` for value checks; include got/want: `t.Errorf("Name = %q, want %q", got, want)`.
  - **If project uses go-cmp**: use `cmp.Diff` for deep struct comparison.
  - **Detection**: Check existing `_test.go` files for `"github.com/stretchr/testify"` imports. Follow project convention.
- Prefer table-driven tests with `t.Run`.
- Prefer real deps or lightweight fakes; avoid heavy mock chains by default.
- Do not add speculative production code not required by failing tests.

## New Mandatory Gates

### 1) Defect Hypothesis Gate

Before writing tests, list concrete defect hypotheses from target code:

- boundary/index (`n-1`, `i+1`, last-item behavior)
- error propagation/wrapping
- mapping loss/data mismatch
- concurrency/order/timing
- idempotency/retry behavior

Each hypothesis must map to at least one test case name. For detailed defect-hypothesis patterns and BAD/GOOD examples, cross-reference the **unit-test** skill: `references/bug-finding-techniques.md`, `references/killer-case-patterns.md`, and Fixed Boundary Checklist.

### 2) Killer Case Gate

Per changed method/use-case, add at least one **killer case** that:

- targets a high-risk defect hypothesis
- includes assertion(s) that must fail on known bad mutation/path
- is explicitly marked in report

### 3) Coverage Gate (Line + Risk Path)

- Line coverage gate: changed package(s) >=80% by default.
- Risk-path gate: all high-risk branches/hypotheses must be covered even if line coverage already passes.
- If gate waived, require explicit user approval and documented risk.

### 4) Execution Integrity Gate

Never claim tests/coverage were run unless actually executed.

- If executed: report exact commands and key result lines.
- If not executable in current environment: report `Not run in this environment` and provide exact run commands.

### 5) Concurrency Determinism Gate

For concurrency-sensitive code:

- avoid `time.Sleep` for synchronization
- use channels/barriers/waitgroups/atomics to control ordering
- run with `-race`

### 6) Change-Size Test Budget Gate

Choose test depth by change size to avoid test bloat. Use concrete criteria first, then case budget:

| Size | Criteria | Test Budget |
|------|----------|-------------|
| **S** | ≤2 files touched, ≤50 LOC, single critical path | 3-6 cases/method, essential regression |
| **M** | 3-5 files, 50-150 LOC, or 2 critical paths | 6-12 cases/method, selected cross-package regression |
| **L** | >5 files, >150 LOC, or 3+ critical paths | 10-20 cases/method + broader regression matrix |

If exceeding range, justify by distinct logic paths. For security-sensitive code (auth, input validation, SSRF guards, crypto), the budget may be doubled — document the security rationale in the output contract.

## Workflow

1. Classify change size (`S/M/L`) and target scope.
2. Write behavior contract (Given/When/Then bullets).
3. Build defect hypothesis list and map each to tests.
4. Red: write failing tests first (include killer case).
   - **Characterization testing** (for pre-existing code): when adding tests AFTER implementation already exists, satisfy the Red evidence gate via one of:
     - *Mutation*: temporarily break the production code, verify new tests fail, then revert.
     - *Hypothesis*: document the specific defect hypothesis each test targets — the hypothesis itself serves as Red evidence that the test guards a real risk.
5. Green: implement minimal code to pass failing tests.
6. Refactor: improve structure without behavior change.
7. Validate quality gates:
   - focused tests
   - coverage (line + risk-path)
   - `-race` when concurrency is relevant
8. Report with evidence and residual risks.

## Command Playbook (Go)

```bash
# Red phase (expect at least one fail)
go test ./path/to/pkg -run TestXxx -v

# Green phase
go test ./path/to/pkg -v

# Coverage (line)
go test ./path/to/pkg -coverprofile=coverage.out
go tool cover -func=coverage.out

# Concurrency safety (when applicable)
go test ./path/to/pkg -race -v

# Broader regression (as needed)
go test ./...
```

## Anti-Examples (Core TDD Mistakes)

For the full set of 7 anti-examples, read `references/anti-examples.md`. The most critical TDD mistakes are inlined here so the contract is self-contained:

### Mistake 1: Writing all tests before any implementation (Big-Bang Red)

```go
// BAD: 15 test cases written at once before any production code
// You lose the tight feedback loop — hard to tell which test drives which behavior
func TestUserService(t *testing.T) {
	t.Run("create", func(t *testing.T) { /* ... 5 subtests */ })
	t.Run("update", func(t *testing.T) { /* ... 5 subtests */ })
	t.Run("delete", func(t *testing.T) { /* ... 5 subtests */ })
}
// Then implement everything at once — this is test-first, NOT TDD

// GOOD: one failing test → minimal implementation → next failing test
// Iteration 1: TestUserService/create/success → implement Create()
// Iteration 2: TestUserService/create/duplicate_email → add uniqueness check
// Each cycle is Red → Green → Refactor before moving on
```

### Mistake 2: Testing implementation details instead of behavior

```go
// BAD: locks test to implementation details and blocks safe refactor
repo.AssertCalled(t, "Save", mock.Anything, user)
// GOOD: assert observable behavior such as returned state, persisted fields, and domain errors
require.Equal(t, "active", got.Status)
```

### Mistake 3: Refactor phase changes observable behavior

```go
// BAD: "refactor" silently changes API behavior
func NormalizeEmail(s string) string { return strings.TrimSpace(strings.ToLower(s)) }
// GOOD: keep behavior unchanged during refactor; add a new Red cycle for any behavior change
func normalizeEmail(s string) string { return strings.TrimSpace(s) }
```

### Mistake 4: Skipping Red evidence — "it compiles so it works"

```go
// BAD: write test and implementation simultaneously, never see a failure
func TestAdd(t *testing.T) {
	// Written AFTER Add() was already implemented
	assert.Equal(t, 3, Add(1, 2))
}

// GOOD: write test FIRST, run it, see it FAIL, then implement
// Step 1: write test → go test → FAIL (Add undefined)
// Step 2: stub: func Add(a, b int) int { return 0 }
//         go test → FAIL (got 0, want 3)
// Step 3: implement: return a + b → go test → PASS
// Red evidence proves the test actually validates something
```

### Mistake 5: Change-size mismatch

```go
// BAD: S change but 40 test cases and 6 helper files added without new logic paths
func TestTinyBugfix(t *testing.T) { /* massive matrix */ }
// GOOD: size the regression to the change budget, then justify any extra cases with distinct risk paths
func TestTinyBugfix_LastElementBoundary(t *testing.T) { /* focused killer case */ }
```

### Mistake 6: Speculative helper extraction before tests demand it

```go
// BAD: extract helpers and abstractions before any failing test proves the need
type orchestrator struct{ repo Repo; audit Audit; cache Cache }
// GOOD: add the smallest code needed for the current Red case, then refactor after Green
func createUser(repo Repo, in CreateUserInput) (User, error) { /* minimal path */ }
```

## Quality Scorecard

Mark each as `PASS` / `FAIL` / `N/A (reason)`.

### Critical (all must pass for overall PASS)

| # | Check | Criteria |
|---|-------|----------|
| C1 | Red evidence exists | Failing test demonstrated before implementation |
| C2 | Killer case present | Each changed method/use-case has at least one killer case |
| C3 | Risk-path coverage | All high-risk hypotheses have test coverage |

### Standard (≥4/5 must pass)

| # | Check | Criteria |
|---|-------|----------|
| S1 | Defect hypothesis list | Exists and maps to test case names |
| S2 | Success + error + boundary paths | All three path categories covered |
| S3 | High-signal assertions | Business fields asserted, not just nil/not-nil |
| S4 | Coverage ≥80% | Changed package(s) meet line coverage gate |
| S5 | Execution integrity | Run evidence provided, or explicit not-run note |

### Hygiene (≥3/4 must pass)

| # | Check | Criteria |
|---|-------|----------|
| H1 | Test file naming/location | `<target>_test.go`, co-located |
| H2 | Subtest hierarchy | `t.Run` with clear naming |
| H3 | Table-driven style | Multi-scenario behavior uses table-driven pattern |
| H4 | Regression scope | Final regression proportionate to change size (S/M/L) |

Scoring:
- **PASS**: All Critical pass AND ≥4/5 Standard AND ≥3/4 Hygiene
- **FAIL**: Any Critical fails → overall FAIL regardless of other scores

## Output Contract

- `Changed files`
- `Change size`: `S/M/L` with reason
- `Defect hypotheses -> test mapping`
- `Killer cases`
- `Red -> Green evidence` (or `Not run in this environment`)
- `Coverage` (line + risk-path)
- `Scorecard` (3-tier: Critical / Standard / Hygiene)
- `Residual risks / follow-ups` — must include:
  - untested edge cases beyond budget
  - design limitations of the target function
  - security implications for sensitive code (e.g., bypass vectors, upstream stdlib assumptions)
  - dependencies on upstream behavior (stdlib, libraries, environment)

## References (Load Selectively)

**Always read** (every TDD task):
- `references/boundary-checklist.md` — defect hypothesis patterns and killer case design

**Read for API/service layer TDD** (skip for pure-function or utility TDD):
- `references/api-3layer-template.md` — Handler/Service/Repo TDD template
- `references/fake-stub-template.md` — fake design and error injection

**Read for first-time TDD or complex refactors**:
- `references/tdd-workflow.md` — end-to-end walkthrough, Outside-In vs Inside-Out, characterization testing

**Read when reviewing or generating TDD code**:
- `references/anti-examples.md` — 5 additional TDD mistakes with BAD/GOOD examples

**Read for characterization testing (adding tests to pre-existing code)**:
- `references/golden-characterization-example.md` — full output contract with mutation-based Red evidence for a security-sensitive function

## Skill Maintenance

Run regression before publishing changes:

```bash
scripts/run_regression.sh
```

Validates frontmatter, gates, anti-examples, scorecard, references, and golden fixtures.

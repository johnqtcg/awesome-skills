---
name: go-logic-review
description: Review Go code for business logic correctness, boundary conditions, off-by-one errors, state management, data flow integrity, and return value contracts. Trigger on any Go code change that modifies behavior, conditional logic, state transitions, or data processing. Use for logic-correctness focused review.
allowed-tools: Read, Grep, Glob, Bash(go build*), Bash(go vet*)
---

# Go Logic Review

## Purpose

Audit Go code for business logic correctness. Core question: **"Does the code do what it's supposed to do?"**

Key distinction from other 6 vertical skills: they use **pattern matching** (see SQL → check injection, see goroutine → check race). This skill uses **semantic understanding** — understand the code's intent, then compare with its implementation.

This skill relies primarily on AI's general reasoning ability, not heavy reference files. The checklist provides the review framework; AI provides the reasoning.

This skill does NOT cover: security patterns, concurrency patterns, performance patterns, code style, test quality, or error handling patterns — those belong to sibling skills.

## When To Use
- Any code change that modifies behavior
- Code contains conditional branches (if/else, switch)
- Code contains data transformation or processing
- Code contains state management or state transitions
- Default dispatch: always run (any code change can introduce logic errors)

## When NOT To Use
- Pure refactoring with no behavior change
- Config-only changes
- Security vulnerability patterns → `go-security-review`
- Concurrency patterns → `go-concurrency-review`
- Code style → `go-quality-review`

## Mandatory Gates

### 1) Context Understanding Gate (unique to this skill)
Before evaluating correctness, understand the INTENT:
- Read function name, comments, docstring
- Read caller context — who calls this function, what do they expect?
- Read related tests — they document expected behavior
- Read commit message / PR description if available

If intent is ambiguous after these steps, flag as **"unclear intent — needs clarification"** rather than guessing. Do not report uncertain intent as a confirmed defect.

### 2) Anti-Example Suppression Gate
MUST cite evidence of intent mismatch. Category match alone insufficient.

Embedded anti-examples:
- **"Function name doesn't match behavior"** — when you cannot verify the expected behavior from available context (don't guess business rules you don't know).
- **"Off-by-one in pagination"** — when the code follows the framework's pagination convention (0-based vs 1-based varies by framework). Verify convention before flagging.
- **"Missing state transition validation"** — when the state machine is intentionally permissive by design (e.g., admin override paths).
- **"Unused function parameter"** — this is a quality/style issue (`go-quality-review`), not a logic issue. Only flag here if the unused parameter indicates a logic bug (function ignores input it should use).
- **"Return value could be nil"** — when callers already handle nil (check all callers before flagging).

### 3) Generated Code Exclusion Gate
Exclude: `*.pb.go`, `*_gen.go`, `mock_*.go`.

## Workflow

1. **Define scope** — files/diff under review. Apply Generated Code Exclusion Gate.
2. **Understand intent** — read function signatures, comments, callers, tests (Context Understanding Gate). This step is a prerequisite — do not skip.
3. **Trace data flow** — map inputs through transformations to outputs. For each function: what goes in? What comes out? Does the transformation match the intent?
4. **Evaluate ALL 10 checklist items** — for each: "does the implementation match the intent?"
5. **Classify findings** — confirmed (clear evidence of mismatch) vs needs-clarification (ambiguous intent) → format output.

## Logic Checklist (10 Items)

> **All 10 items are semantic-only** — no grep patterns are applicable. Logic review relies on AI reasoning to understand code intent vs implementation. This skill does not use the Grep-Gated Execution Protocol.

| # | Item | What to Check |
|---|------|--------------|
| 1 | **Happy path correctness** | Function's actual behavior matches its name, comments, caller expectations? Example: `GetTopN()` but no LIMIT applied |
| 2 | **Boundary conditions** | nil input, empty collection, single element, zero value, MaxInt/MinInt. Example: `average(items)` divides by `len(items)` without zero check |
| 3 | **Off-by-one** | Loop `<` vs `<=`, slice `[start:end]` (end exclusive), pagination offset/limit. Example: `items[0:count]` when count can equal `len(items)+1` |
| 4 | **Conditional logic** | `>` vs `>=`, `&&` vs `||`, negation correctness. Example: `if !isAdmin || !isOwner` should be `&&` (De Morgan's) |
| 5 | **State consistency** | State transitions complete? Illegal paths possible? Modified state persisted? Example: order "pending" → "completed" skipping "processing" |
| 6 | **Data flow integrity** | Input fully consumed? Intermediate results correctly passed? Example: filter returns filtered list but caller uses original unfiltered list |
| 7 | **Resource lifecycle** | Files/connections/transactions closed on ALL paths? Note: overlaps with `go-error-review` — here focus on logic (missing close as logic gap), there on error handling pattern |
| 8 | **Return value contract** | Return values meet caller's implicit assumptions? Example: caller assumes non-nil slice, function returns nil on empty |
| 9 | **Idempotency and reentrancy** | Operations marked retriable actually idempotent? Example: "retry-safe" endpoint creates duplicate records |
| 10 | **Timing assumptions** | Code assumes "A before B" — always guaranteed? Example: cache populated before first read, but init is async |

## Severity Rubric

**High** — Logic error producing incorrect results, data corruption, or silent failure in production.

**Medium** — Logic concern under specific edge cases or conditions.

## Evidence Rules
- For each finding: explain what code **DOES** vs what it **SHOULD** do
- **Intent evidence**: cite function name, comment, caller context, test expectations, PR description
- **Ambiguity rule**: if intent is truly ambiguous, report as "potential issue — needs clarification" with Action: `needs-clarification`, NOT as confirmed defect
- **Merge rule**: same logical issue at ≥3 locations → one finding with location list

## Output Format

### Findings
#### [High|Medium] Short Title
- **ID:** LOGIC-NNN
- **Location:** `path:line`
- **What it does:** Actual behavior of the code
- **What it should do:** Expected behavior based on intent signals
- **Evidence:** Why the two differ (off-by-one, missing condition, wrong comparison)
- **Recommendation:** Specific fix
- **Action:** `must-fix` | `needs-clarification`

### Summary
1-2 lines. Count by severity.

## Example Output

```
### Findings

#### [High] GetTopN Returns All Results — Missing LIMIT
- **ID:** LOGIC-001
- **Location:** `internal/repo/product.go:34`
- **What it does:** Queries `SELECT * FROM products ORDER BY sales DESC` — returns ALL products
- **What it should do:** Return top N. Signature: `GetTopN(ctx, n int)`; caller at recommendation.go:12 passes n=10
- **Evidence:** Parameter `n` accepted but never used in query. ORDER BY suggests top-N intent but no LIMIT clause.
- **Recommendation:** Add `LIMIT $1`: `SELECT * FROM products ORDER BY sales DESC LIMIT $1`
- **Action:** must-fix

#### [High] Division by Zero on Empty Input
- **ID:** LOGIC-002
- **Location:** `internal/stats/aggregate.go:22`
- **What it does:** `total / len(items)` — panics when items empty
- **What it should do:** Return 0 or error. Comment: "returns average of items"
- **Evidence:** No length check at L22. Caller at report.go:45 passes user-filtered list that can be empty.
- **Recommendation:** Add guard: `if len(items) == 0 { return 0, nil }`
- **Action:** must-fix

#### [Medium] State Transition May Skip Validation
- **ID:** LOGIC-003
- **Location:** `internal/order/state.go:56`
- **What it does:** Allows "pending" → "shipped" directly
- **What it should do:** Unclear — no state machine doc. Tests only cover happy path (pending → confirmed → shipped).
- **Evidence:** `validTransitions` map includes `"pending": {"confirmed", "shipped", "cancelled"}` — "shipped" without "confirmed" may be intentional (express?) or bug
- **Recommendation:** Clarify with team: is pending → shipped valid? If not, remove from map.
- **Action:** needs-clarification

### Summary
2 High (missing LIMIT, division by zero), 1 Medium needs clarification (state transition).
```

## No-Finding Case
If no issues found: state `No logic findings identified.` Note the intent sources consulted (callers, tests, comments).

## Load References Selectively
This skill relies primarily on AI reasoning, not heavy reference files.

| Reference | Load When |
|-----------|-----------|
| `references/go-review-anti-examples.md` | Always (for suppression discipline) |

## Review Discipline
- **Logic correctness only** — not security patterns, concurrency patterns, performance, style, tests, or error handling patterns
- **Understand intent BEFORE evaluating** — read callers, tests, comments first
- For each function: "If I were the caller, would I get what I expect?"
- Execute ALL 10 checklist items
- When in doubt about intent: **flag for clarification, don't guess**
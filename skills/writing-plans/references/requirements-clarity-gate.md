# Requirements Clarity Gate — Reference

Load this file when Gate 1 triggers a STOP-and-ASK condition, or when you need to evaluate whether requirements are clear enough to plan.

## Clarity Dimensions

Evaluate the user's request against these five dimensions. Not all dimensions apply to every request — use judgment.

### D1: Goal Specificity

Can you state the goal in one sentence with a concrete verb and a measurable outcome?

| Clear | Unclear |
|---|---|
| "Add pagination to the /users endpoint with cursor-based navigation" | "Improve the API" |
| "Fix the nil pointer panic when config file is missing" | "Fix the bugs in config" |
| "Extract shared validation into a reusable package" | "Clean up the code" |

**If unclear:** Ask "What specific behavior should change? What does success look like?"

### D2: Scope Boundary

Can you draw a line around what changes and what does NOT change?

| Clear | Unclear |
|---|---|
| "Add retry logic to the HTTP client in pkg/httpclient" | "Add retry logic" (where?) |
| "Migrate the users table, do not touch orders or payments" | "Migrate the database" |

**If unclear:** Ask "Which modules/files are in scope? Is anything explicitly out of scope?"

### D3: Success Criteria

How will you know the change is correct? What should pass, what should fail, what should be measurable?

| Clear | Unclear |
|---|---|
| "Endpoint returns 200 with paginated results; existing clients get default pagination" | "It should work better" |
| "P95 latency under 100ms for list queries" | "Make it faster" |

**If unclear:** Ask "How will we verify this works? Any performance targets, error rate expectations, or behavioral contracts?"

### D4: Constraints and Compatibility

Are there rules about what CANNOT change? Backward compatibility? Performance budgets? Dependencies?

| Clear | Unclear |
|---|---|
| "Must be backward compatible — no breaking changes to the API contract" | "Change the response format" (breaking? non-breaking?) |
| "Cannot add new dependencies due to corporate policy" | (No mention of constraints) |

**If unclear for public interfaces:** Ask "Should this be backward compatible? Are there existing consumers that could break?"
**If unclear for internal changes:** Skip — constraints can be discovered during repo discovery (Gate 3).

### D5: Edge Cases and Error Handling (Standard/Deep only)

For non-trivial changes, are the unhappy paths described?

| Clear | Unclear |
|---|---|
| "If token is expired, return 401 with error code TOKEN_EXPIRED" | "Handle token errors" |
| "If batch import fails at row N, report which rows failed and continue the rest" | "Handle import errors" |

**If unclear:** For Lite mode, skip. For Standard/Deep, ask "What should happen when [obvious failure case]?"

## Mode-Appropriate Depth

The clarity bar scales with the anticipated plan mode. Do not over-ask for simple tasks.

| Anticipated Mode | Required Clarity Dimensions | Clarification Rounds |
|---|---|---|
| Likely SKIP | None — proceed directly | 0 |
| Likely Lite | D1 (Goal) sufficient | 0-1 |
| Likely Standard | D1 (Goal) + D2 (Scope) + D4 (Constraints, if public interface) | 0-1 |
| Likely Deep | All five: D1 + D2 + D3 + D4 + D5 | 1-2 |

Note: You won't have formally classified the mode yet (that's Gate 2's job), but you can estimate from surface signals: file count, cross-module mentions, migration language, etc.

## Clarification Examples

### Example 1: Fast pass-through (no questions needed)

**User:** "Add a `deleted_at` nullable timestamp column to the users table with a soft-delete migration. Keep existing queries working by adding a `WHERE deleted_at IS NULL` default scope."

**Assessment:** Goal specific (D1), scope bounded to users table (D2), success criteria implied by "keep existing queries working" (D3), backward compatibility stated (D4). Proceed to Gate 2.

### Example 2: One round of clarification

**User:** "Refactor the validation logic."

**Assessment:** D1 vague ("refactor" how?), D2 missing (which validation? where?).

**Ask:** "I'd like to understand the scope before planning:
1. Which validation logic — input validation in the API handlers, business rule validation in the service layer, or both?
2. What's the goal — extracting shared code to reduce duplication, improving error messages, or changing validation rules?
3. Are there specific modules that should NOT be touched?"

### Example 3: Two rounds needed (Deep-level change)

**User:** "Migrate from REST to gRPC."

**Round 1 Ask:** "This is a significant architecture change. Before I plan:
1. Which services are in scope for migration? All, or a specific subset?
2. Is this a full replacement or will REST and gRPC coexist during a transition period?
3. Are there external consumers of the current REST API that need continued support?"

**Round 2 Ask (after user answers):** "Thanks. Two more questions:
1. What's the backward compatibility strategy — will you maintain REST endpoints behind a gateway, or sunset them with a deprecation window?
2. Is there a target timeline that would affect phasing (e.g., must be done before Q3 launch)?"

### Example 4: Assumption marking when clarity isn't reached

**User (after 2 rounds):** "Just plan it, I'll adjust as we go."

**Response:** Proceed to Gate 2 with explicit assumptions:
```
[Assumption] Migration covers all 5 internal services but not the public API gateway
[Assumption] REST and gRPC will coexist during transition; no hard cutover
[Assumption] No external consumer migration plan needed
```

## Anti-Patterns

1. **Over-interrogation**: Asking 10 questions about a clear bugfix. If the request names a file, describes the bug, and says "fix it," proceed.
2. **Asking HOW questions**: "Should we use middleware or decorators?" is an implementation decision, not a requirement. Gate 1 only clarifies WHAT.
3. **Asking about things discoverable from the repo**: "What test framework do you use?" is Gate 3's job, not Gate 1.
4. **Blocking on perfection**: Requirements never have zero ambiguity. The bar is "clear enough to write a Goal and Scope," not "complete specification."
5. **Repeating the user's words back as a question**: "You said refactor — do you mean refactor?" is not helpful. Offer concrete options: "Do you mean extracting shared logic, renaming for consistency, or restructuring the module layout?"
6. **Asking about edge cases for Lite-mode tasks**: A 10-line bugfix doesn't need edge case analysis. Match depth to complexity.
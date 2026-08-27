# Scope & Severity — Mode Decision and N/A Scoring

## Table of Contents

1. [Overview](#overview)
2. [Deciding the Mode](#deciding-the-mode)
3. [Diagnose-Only Mode in Detail](#diagnose-only-mode-in-detail)
4. [P2 Collapsed Investigation in Detail](#p2-collapsed-investigation-in-detail)
5. [How N/A Criteria Score](#how-na-criteria-score)
6. [Edge Cases](#edge-cases)

## Overview

`SKILL.md`'s Iron Law is unconditional — no fix without root-cause investigation. But "investigation" and "fix" are not the same commitment, and not every severity needs the same depth of evidence before a fix. This reference resolves two things that a flat "complete every phase, every time" rule cannot:

1. A request to *diagnose* is not automatically a request (or an authorization) to *fix*.
2. A P2 cosmetic bug with an obvious cause does not need the same evidentiary weight as a P1 production-blocking bug — but it still needs *some* stated evidence, not a bare guess.

## Deciding the Mode

Ask, in order:

1. **Is this production down, data loss, or a security issue right now?** → **P0 incident mode.** Mitigate per the P0 Protocol first; the mode for the *permanent fix* afterward is decided by the next two questions.
2. **Did the request ask only to find/explain/understand the cause** ("why is this happening", "investigate", "what's causing X"), **or do you lack authorization to change the target system** (e.g., a read-only review, a system you were asked to look at but not touch, a third party's codebase)? → **Diagnose-only mode.**
3. **Otherwise** → **Diagnose-and-fix mode** (the default), scaled by the severity table in `SKILL.md`.

When genuinely ambiguous — the request doesn't say either way — default to diagnose-and-fix but state the root cause and proposed fix separately enough that the human partner could stop you before the fix lands (this is what the Output Contract's section ordering already gives you for free: sections 1-5 before section 6).

## Diagnose-Only Mode in Detail

- Phases 1-3 apply in full, scaled by severity as normal.
- Phase 4 ("Implementation") is **not entered**. No failing test is written against production code, no fix is implemented, no PR is opened.
- The Output Contract still runs through section 9, but:
  - Section 6 (Fix Plan and Change) states: *"Not implemented — root cause identified, awaiting authorization to fix."* Optionally describe what a fix would likely involve, clearly labeled as unimplemented analysis. This is a description in a report, not an implemented change — it does not violate the "never implement without authorization" rule, which is about writing/applying code, not about writing sentences describing what code would do.
  - Scorecard C1 is **N/A** (see below) since no fix was proposed to check evidence against.
- If, mid-investigation, it becomes clear a fix is trivial and the human partner would obviously want it now, say so and ask — don't silently switch to diagnose-and-fix mode. Mode is a scope decision, not a discovery.

## P2 Collapsed Investigation in Detail

For **P2** issues where the cause is obvious after Phase 1:

- Phase 2 (Pattern Analysis) may be skipped entirely — say so in the report ("Phase 2 skipped: cause was directly evident from the error/repro, no comparable working example was needed").
- Phase 3 (Hypothesis and Testing) collapses to a single explicit hypothesis statement ("I think X is the root cause because Y") with the evidence from Phase 1 backing it — you do not need a multi-row Hypothesis Log unless that first hypothesis is rejected. If it's rejected, you're no longer in the "obvious cause" case; escalate to the full Phase 3 process (form a new hypothesis, log both).
- This collapse is **not** available for P0 or P1, and is not available for P2 issues where the cause required real investigation (multiple candidate causes, non-obvious data flow, cross-component evidence) — "P2" is a severity label, not a shortcut you can invoke to avoid doing the work a genuinely non-obvious bug requires.

## How N/A Criteria Score

A Scorecard criterion marked **N/A** requires a one-line stated reason and counts as satisfied (not counted against the tier's denominator as a FAIL, and not silently dropped from the denominator either — it counts toward the "of N" total as a pass). Concretely:

- **C1 (permanent fix evidence)** is N/A in diagnose-only mode: *"N/A — no fix was requested, see Fix Plan section."* It is **never** N/A in diagnose-and-fix or P0 mode; some evidence tier always applies there.
- **C4 (hypothesis log)** is N/A when Phase 3 legitimately collapsed to a single hypothesis under the P2 rule above: *"N/A — P2 collapsed hypothesis, single cause confirmed on first pass."* It is **not** N/A simply because the investigator didn't bother writing one down for a P1/P0 issue, or for a P2 issue whose first hypothesis was rejected.
- **No other Critical, Standard, or Hygiene criterion may be marked N/A — this includes S2.** A single-component issue with no cross-component boundary at all does not make S2 N/A; it makes S2 an ordinary PASS ("all relevant boundaries — there being exactly one, or none beyond the confirmed root cause — are covered"). The same applies to S6 when fewer than 3 fix attempts occurred ("no architecture-questioning was triggered because the Fix Attempt Gate wasn't reached"). Marking S2 (or any Standard/Hygiene item) N/A instead of PASS is a rule violation, not a reasonable extension of the C1/C4 pattern — the pattern does not generalize, and a report that does this should be scored as failing H4 (or the misapplied item itself), not waved through.
- A report that marks something N/A without the one-line reason, or marks C1 N/A while a fix was actually proposed and implemented, fails H4 (wording is concise and honest) at minimum, and likely C1/C2 directly — N/A is not an escape hatch from evidence, it's a declaration that the criterion doesn't apply to the case at hand, and that declaration must be checkable.

## Edge Cases

- **P0 mitigation, then diagnose-only permanent-fix decision**: possible when the mitigation itself (e.g., a config rollback) removes the urgency and ownership of the permanent fix passes to a different team who will handle Phase 4 themselves. State this explicitly in Residual Risk/Follow-ups rather than silently stopping.
- **Mode changes mid-investigation** (e.g., what looked like P2 turns out to need architecture-level changes): re-triage severity and mode, note the change and why in the report, and restart the phase sequence from wherever the new evidence requires — don't retroactively claim the original (lower) bar was met.
- **Multiple bugs found while investigating one**: triage and mode-decide each independently; do not let a P0 in-progress investigation implicitly authorize fixing an unrelated P2 you noticed along the way (that's the "no bundled changes" rule from the Hypothesis Discipline and Fix Attempt gates, applied at the mode level).

# Debugging Report Scorecard

Use this scorecard to judge whether a debugging report is good enough to trust.

## Table of Contents

1. [Why a Scorecard Exists](#why-a-scorecard-exists)
2. [Critical](#critical)
3. [Standard](#standard)
4. [Hygiene](#hygiene)
5. [How to Score](#how-to-score)
6. [PASS vs FAIL Examples](#pass-vs-fail-examples)

## Why a Scorecard Exists

Without a scorecard, output contract only checks structure, not quality. A report can have all sections and still be weak:
- root cause is really a symptom
- evidence does not cover the failing boundary
- fix is guessed before investigation
- verification is hand-wavy

The scorecard prevents that failure mode.

## Critical

Any FAIL here means the entire report FAILS — no Standard/Hygiene score can offset a Critical FAIL. `references/scope-and-severity.md` defines exactly when C1 and C4 are legitimately N/A (diagnose-only, P2 collapsed hypothesis) rather than FAIL; N/A always requires a one-line stated reason.

| ID | Question | PASS standard |
|----|----------|---------------|
| C1 | Did the report avoid proposing a permanent fix before the evidence its declared mode/severity requires existed? | No fix before required evidence, or N/A (diagnose-only — no fix was requested) |
| C2 | Is the root cause a source condition, not a downstream symptom? | Source is named and explained |
| C3 | Is the root cause backed by concrete evidence — and, for a multi-component issue, boundary evidence at the specific failing hop? | Repro, trace, profile, or boundary evidence exists at the failing hop |
| C4 | Does the hypothesis log match the investigation path taken? | Log is present and consistent, or N/A (P2 collapsed hypothesis, single cause confirmed on first pass) |
| C5 | Did the report avoid claiming any command, profile, trace, or verification ran when it didn't? | Every claim either actually ran, or is marked `Not run in this environment` with why and the next command (Reporting Integrity Gate) |

## Standard

Need at least 4 of 6. These are completeness/quality checks *beyond* the Critical floor above — e.g. S2 is broader coverage of every boundary, not just the one C3 already requires for the failing hop; S4 is the thoroughness of verification (regression checks, adjacent risk), not the honesty check C5 already covers.

| ID | Question | PASS standard |
|----|----------|---------------|
| S1 | Is reproduction precise? | Exact command or exact steps |
| S2 | Is evidence coverage complete across *every* relevant boundary, not just the failing one? | All relevant component hops covered |
| S3 | Is fix scope minimal? | Single justified change or clear reason fix deferred |
| S4 | Is verification thorough (not just honest — that's C5)? | Commands/checks, results, and adjacent-regression consideration shown |
| S5 | Are residual risks honest? | Concrete risks and follow-ups listed |
| S6 | After repeated failed fixes, did the report question architecture? | Yes when 3+ failed attempts occurred |

## Hygiene

Need at least 3 of 4.

| ID | Question | PASS standard |
|----|----------|---------------|
| H1 | Does the report follow the required section order? | Sections 1-9 in order |
| H2 | Are severity, mode, and bug type classified? | All three present |
| H3 | Are owners / ETA present when follow-ups exist? | Owner + ETA shown |
| H4 | Is the wording concrete and concise? | Low filler, low hedging |

## How to Score

1. Score Critical first (C1-C5, honoring the N/A rules for C1/C4 above).
2. If any Critical item fails, overall result is FAIL immediately — do not proceed to compute Standard/Hygiene as a way to "make up for" a Critical fail; they cannot.
3. Score Standard next.
4. Score Hygiene last.

Output format:

```json
{
  "scorecard": {
    "critical": "PASS",
    "standard": "5/6",
    "hygiene": "4/4",
    "overall": "PASS"
  }
}
```

Also report failed item IDs and one-line rationale.

## PASS vs FAIL Examples

PASS:
- reproduction exact
- evidence proves the boundary break
- hypothesis log shows rejected and confirmed paths
- root cause points to source condition

FAIL:
- "probably cache" with no reproduction
- "DB is slow" without profile or query evidence
- "fix attempt 4" with no architecture discussion
- "tests should pass now" without commands

## Quick Scoring Checklist

Before marking PASS, ask:
- can another engineer rerun the reproduction?
- can a reviewer see exactly why the root cause is source-level?
- does the evidence cover every important boundary?
- is the verification strong enough to reject a false fix?

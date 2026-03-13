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

Any FAIL here means the entire report FAILS.

| ID | Question | PASS standard |
|----|----------|---------------|
| C1 | Did the report avoid proposing a permanent fix before investigation evidence existed? | No fix before evidence |
| C2 | Is the root cause a source condition, not a downstream symptom? | Source is named and explained |
| C3 | Is the root cause backed by concrete evidence? | Repro, trace, profile, or boundary evidence exists |
| C4 | Does the hypothesis log match the investigation path taken? | Log is present and consistent |

## Standard

Need at least 4 of 6.

| ID | Question | PASS standard |
|----|----------|---------------|
| S1 | Is reproduction precise? | Exact command or exact steps |
| S2 | Is evidence coverage complete across boundaries? | All relevant component hops covered |
| S3 | Is fix scope minimal? | Single justified change or clear reason fix deferred |
| S4 | Is verification explicit? | Commands/checks and results shown |
| S5 | Are residual risks honest? | Concrete risks and follow-ups listed |
| S6 | After repeated failed fixes, did the report question architecture? | Yes when 3+ failed attempts occurred |

## Hygiene

Need at least 3 of 4.

| ID | Question | PASS standard |
|----|----------|---------------|
| H1 | Does the report follow the required section order? | Sections 1-9 in order |
| H2 | Are severity and bug type classified? | Both present |
| H3 | Are owners / ETA present when follow-ups exist? | Owner + ETA shown |
| H4 | Is the wording concrete and concise? | Low filler, low hedging |

## How to Score

1. Score Critical first.
2. If any Critical item fails, overall result is FAIL immediately.
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

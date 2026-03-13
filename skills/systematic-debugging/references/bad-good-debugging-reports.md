# BAD / GOOD Debugging Report Examples

## Table of Contents

1. [Symptom Presented As Root Cause](#1-symptom-presented-as-root-cause)
2. [Guessed Fix Without Reproduction](#2-guessed-fix-without-reproduction)
3. [Sleep Used To Hide A Race](#3-sleep-used-to-hide-a-race)
4. [Performance Fix Without Profiling](#4-performance-fix-without-profiling)
5. [Missing Boundary Evidence](#5-missing-boundary-evidence)
6. [Bundled Fixes](#6-bundled-fixes)
7. [Repeated Failed Fixes Without Questioning Architecture](#7-repeated-failed-fixes-without-questioning-architecture)

Use these examples to teach what a bad debugging report looks like, not just what a good one contains.

## 1. Symptom Presented As Root Cause

BAD:
```markdown
## Root Cause
The API returns 500 because the query is slow.
```

GOOD:
```markdown
## Evidence Collected
EXPLAIN ANALYZE shows sequential scan on users(email) across 500k rows.

## Root Cause
Requests filter on users.email without an index, forcing a sequential scan.
```

## 2. Guessed Fix Without Reproduction

BAD:
```markdown
The cache is probably stale. Clear it and rerun.
```

GOOD:
```markdown
## Reproduction
go test ./... fails on CI Go 1.24 and passes locally on Go 1.25rc.

## Root Cause
Generated code is incompatible with the pinned CI compiler version.
```

## 3. Sleep Used To Hide A Race

BAD:
```markdown
Add 500ms sleep before assertion.
```

GOOD:
```markdown
## Evidence Collected
go test -race ./... reports concurrent map writes in cache warmup.
```

## 4. Performance Fix Without Profiling

BAD:
```markdown
Switch JSON library because encoding is slow.
```

GOOD:
```markdown
## Evidence Collected
pprof shows 81% of samples in subscriber retention, not JSON encoding.
```

## 5. Missing Boundary Evidence

BAD:
```markdown
Secrets are missing in the signing step.
```

GOOD:
```markdown
## Evidence Collected
workflow secret present -> build env missing -> signing step never receives IDENTITY.
```

## 6. Bundled Fixes

BAD:
```markdown
Changed parser, retries, cache, and timeout values. Tests pass now.
```

GOOD:
```markdown
## Fix Plan and Change
Single change: preserve trailing delimiter in parser normalization.
```

## 7. Repeated Failed Fixes Without Questioning Architecture

BAD:
```markdown
Fix attempt 4: add another lock and retry.
```

GOOD:
```markdown
## Residual Risk and Follow-ups
Three failed fixes exposed shared mutable state across queueing and retry layers.
Next step: architecture review before any fourth fix.
```

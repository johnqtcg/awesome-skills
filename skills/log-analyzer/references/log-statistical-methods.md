# Log Statistical Methods

The single most common log-analysis error is treating an absolute count as a finding. *"There were 87 errors!"* — out of how many requests, over what window, vs which baseline?

This file gives the small set of techniques that prevent that error.

## Always Compute a Rate, Not Just a Count

Pick the right denominator:

| Numerator | Right denominator | Meaning |
|---|---|---|
| Errors in window | Total log lines (any level) in window | Log-side error ratio. Cheap. Crude. |
| Errors in window | Total **requests** in window | The number you actually want. Use this when request volume is in logs / metrics. |
| 5xx responses | Total responses | HTTP error ratio (the standard SLO numerator). |
| Failed jobs | Jobs scheduled | Background-job failure ratio. |

If denominator data is genuinely unavailable, state `Statistical context: unavailable — only counts are reportable` and downgrade every "frequent" claim.

## Baseline Comparison: The Same-Window Test

A spike is meaningful only relative to a comparable window. Always compare against:

1. **Previous N**: same length immediately before. (e.g., previous 1 hour)
2. **Yesterday-same-hour**: handles diurnal traffic.
3. **Last-week-same-hour**: handles weekly seasonality (B2B traffic differs Sat vs Tue).

Heuristic anchors:

| Observation | Likely interpretation |
|---|---|
| Current rate ≥ 3× any of the three baselines | Spike — investigate |
| Current rate within 1.5× all three | Probably normal variance |
| Current rate < baselines | Possibly a *drop* — also investigate (could be data loss / outage upstream) |
| Baselines are zero, current is non-zero | New error class — investigate regardless of count |

## The 1-in-N-Million Trap

A 0.0001% error rate in a service handling 50 M requests/hour is **5000 errors/hour**. The absolute count looks scary in isolation; the rate is healthy.

Rule: **if the error ratio is less than your error budget, the count is rarely the story** — unless the errors cluster (one tenant, one endpoint) or the *class* of error is new.

## New-Error Detection

Always cross-check the error class set:

```bash
# Last hour error classes
jq -r 'select(.level=="ERROR") | .err.code // .msg' last-hour.log | sort -u > /tmp/now.txt
# Yesterday same hour, same processing
jq -r 'select(.level=="ERROR") | .err.code // .msg' yesterday.log | sort -u > /tmp/then.txt

# What is new today?
comm -23 /tmp/now.txt /tmp/then.txt
```

Any non-empty diff is worth a finding even if counts are tiny. New error classes mean a new failure mode entered the system.

## Spike Detection Without Metrics

When you have only logs (no Prometheus / aggregator graphs), you can still chart in your head:

- Bucket errors by minute (or 5-minute):
  ```bash
  jq -r 'select(.level=="ERROR") | .time[0:16]' app.log | sort | uniq -c
  ```
- Look for a *step function*: 0,0,0,0,87,93,84,79,0,0. The step is the spike's start. Investigate the 30 lines immediately before the step, not the step itself.
- A *ramp* (5,7,12,28,67,134) usually means an exhaustion-style failure (queue, pool, memory). A *step* usually means a deploy or config change.

## Cluster the Error Lines Before You Count

Don't count `msg` strings literally — they often embed identifiers that explode the cardinality.

```
"failed to fetch order order-9183754 for user user_42 retry 3"
"failed to fetch order order-2987183 for user user_19 retry 1"
```

Both should count as one error class. Strip identifiers before grouping:

```bash
jq -r 'select(.level=="ERROR") | .msg' app.log \
  | sed -E 's/(order|user)[-_][a-z0-9-]+/\1_<ID>/g' \
  | sort | uniq -c | sort -rn | head -20
```

This collapses cardinality and gives you the real top-N. Use the full identifier value only for **trace walking**, not for counting.

## Confidence Intervals (Rough)

When base rate matters, do not pretend the number is exact. A 95% confidence interval for an observed proportion `p` over `n` trials is roughly `p ± 2·sqrt(p·(1-p)/n)`. Useful applications:

- 1 error in 1000 requests → `0.001 ± 0.002` → could be anywhere from 0% to 0.3%. Do not call this a "spike" because it doubled to 2-in-1000.
- 100 errors in 1000 requests → `0.10 ± 0.019` → 10% ± 2%. Confidently bad.

Numbers do not need to be exact. The point is to know whether the difference you are reporting is plausibly random.

## Log Sampling Awareness

If the source is sampled (Datadog ingest sampling, application-side rate limiting, head-based trace sampling) then **all rate calculations must be scaled** by the sampling rate.

- 1% sampling and 100 error lines → estimate ~10000 errors.
- Sampling rates are rarely uniform across paths — error logs are often kept at 100% while INFO is sampled. Read the sampler config; do not assume.

State sampling assumptions in `Execution Status: Coverage`.

## Comparing Two Windows the Right Way

When asked "did the deploy at 14:00 cause errors", compare windows of equal length on either side:

| Pre-window | Post-window | Verdict |
|---|---|---|
| `13:00–14:00`: 12 errors | `14:00–15:00`: 87 errors | Likely correlated. Pivot to the deploy contents. |
| `13:00–14:00`: 12 errors | `14:00–15:00`: 14 errors | Within noise. The deploy probably did not cause this. |
| `13:00–14:00`: 0 errors | `14:00–15:00`: 3 errors | Suggestive but small N — note as "weakly correlated, needs longer post-window". |

Always state both pre and post counts; do not present only the post.

## When Numbers Disagree

If two sources contradict (e.g., aggregator shows 2000 errors but the file shows 50000), the contradiction itself is a finding — *which source is sampling, broken, or windowed differently*?

Possible causes (in order of frequency):

1. Different time bounds (aggregator window is in browser-local time; file was UTC).
2. Aggregator-side sampling.
3. Aggregator index lag (recent data not yet ingested).
4. File rotation cut the window.

State the contradiction in `Open Questions` and do not pick a number until reconciled.

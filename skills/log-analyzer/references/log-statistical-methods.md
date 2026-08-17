# Log Statistical Methods

The single most common log-analysis error is treating an absolute count as a finding. *"There were 87 errors!"* — out of how many requests, over what window, vs which baseline?

This file gives the small set of techniques that prevent that error.

## Contents

- [Always Compute a Rate, Not Just a Count](#always-compute-a-rate-not-just-a-count)
- [Baseline Comparison: The Same-Window Test](#baseline-comparison-the-same-window-test)
- [The 1-in-N-Million Trap](#the-1-in-n-million-trap)
- [New-Error Detection](#new-error-detection)
- [Spike Detection Without Metrics](#spike-detection-without-metrics)
- [Cluster the Error Lines Before You Count](#cluster-the-error-lines-before-you-count)
- [Confidence Intervals (Rough)](#confidence-intervals-rough)
- [Log Sampling Awareness](#log-sampling-awareness)
- [Comparing Two Windows the Right Way](#comparing-two-windows-the-right-way)
- [When Numbers Disagree](#when-numbers-disagree)

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

### The inverse trap: frequency is not severity

The base-rate test answers "is this a trend?". It does not answer "does this
matter?". Applying it to severity is how a single line reporting a security or
correctness failure gets filed as noise.

Never suppress by base rate when the error class is:

| Class | Why N=1 is enough |
|---|---|
| security / authz | One bypass is a breach. There is no acceptable rate. |
| data integrity | One silent corruption propagates and compounds; the count grows while you dismiss it. |
| financial | One wrong charge is a customer refund and possibly a regulatory event. |
| compliance / residency | Rate-independent by definition — the obligation is per-record. |
| asserted invariant (`"should never happen"`, `"unreachable"`, `"invariant violated"`) | The author already stated the acceptable rate is zero. |

For everything else, frequency legitimately bounds urgency: a 0.001% hygiene
warning is not worth a page.

The correct framing in a report: *"1 occurrence — too rare to be a trend, but the
class is `data-integrity`, so it is reported at High regardless of rate."*

## New-Error Detection

Always cross-check the error class set:

```bash
# Error classes present in each window, diffed without writing any file.
# Process substitution keeps both sides as pipes: no redirection, nothing to
# clean up, and no risk of a stale /tmp file from an earlier run being compared.
comm -23 \
  <(jq -r 'select(.level=="ERROR") | .err.code // .msg' last-hour.log | sort -u) \
  <(jq -r 'select(.level=="ERROR") | .err.code // .msg' yesterday.log | sort -u)
```

`sort` is not auto-approved (see §Command Safety Contract) so this prompts once.
For JSON logs `jq` can do the whole diff itself, with no prompt:

```bash
jq -rn --slurpfile a <(jq -c 'select(.level=="ERROR")' last-hour.log) \
       --slurpfile b <(jq -c 'select(.level=="ERROR")' yesterday.log) '
  ([$a[]|.err.code // .msg]|unique) - ([$b[]|.err.code // .msg]|unique) | .[]'
```

Any non-empty diff is worth a finding even if counts are tiny. New error classes mean a new failure mode entered the system.

## Spike Detection Without Metrics

When you have only logs (no Prometheus / aggregator graphs), you can still chart in your head:

- Bucket errors by minute (or 5-minute):
  ```bash
  jq -r 'select(.level=="ERROR") | .time[0:16]' app.log | sort | uniq -c
  ```
- Look for a *step function*: 0,0,0,0,87,93,84,79,0,0. The step is the spike's start. Investigate the 30 lines immediately before the step, not the step itself.
- A *ramp* (5,7,12,28,67,134) is **more common with** exhaustion-style failures (queue, pool, memory); a *step* is more common with a deploy or config change. Onset shape narrows the hypothesis space — it does not identify a cause. A step also fits a downstream dependency flipping state or a feature flag toggling; a ramp also fits steadily rising traffic against a fixed limit. Report it as "consistent with", never as "indicates".

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

If the source is sampled (Datadog ingest sampling, application-side rate limiting,
head-based trace sampling), what you must do depends on **what you are computing**
and **how the sampler works**. "Scale everything by the sampling rate" is wrong and
will produce confidently incorrect ratios.

### Counts scale. Ratios usually do not.

Under **uniform** sampling at rate `s`, numerator and denominator are both thinned
by `s`, so the factor cancels:

| Quantity | Under uniform sampling at rate `s` | Action |
|---|---|---|
| Absolute count (`87 errors`) | observed ≈ `s × true` | **Divide by `s`** to estimate the true count |
| Ratio (`errors / requests`) | observed ≈ `(s·E)/(s·T)` = `E/T` | **Do not scale.** It is already unbiased |
| Rate per second (`errors/sec`) | observed ≈ `s × true` | **Divide by `s`** |
| Ratio precision | `n` is the *sampled* count | Widen the confidence interval — use sampled `n`, not the scaled-up one |

The last row is the one people miss: 1% sampling that yields 100 error lines gives
you an estimate of ~10 000 errors, but the *precision* of any ratio built from it
is the precision of `n = 100`, not `n = 10 000`.

### Stratified sampling breaks single-factor scaling entirely

Sampling rates are rarely uniform: ERROR is commonly kept at 100% while INFO is
sampled at 1%. When numerator and denominator are sampled at **different** rates
`s_e` and `s_t`, no single factor is correct — the observed ratio is inflated by
`s_e / s_t`. With ERROR at 100% and INFO at 1%, a log-line-denominator error ratio
reads **100× too high**.

- Fix: use a denominator sampled at the same rate as the numerator, or an unsampled
  one (request count from metrics, load-balancer counters, `_count` on a Prometheus
  histogram). A metrics-derived denominator is almost always better than a
  log-derived one.
- If you cannot establish both rates, say so and report the count only.

### When sampling is unknown or non-random

- **Unknown rate** → do not scale and do not report a rate. State
  `Coverage: sampled, rate unknown — counts are lower bounds, ratios not inferable`.
- **Non-random sampling** (rate limiting that drops bursts, quota exhaustion,
  "log first N per minute") → the sample is biased *against exactly the spikes you
  are looking for*. Scaling makes it worse, not better. Treat observed counts as
  lower bounds and say the true shape is unrecoverable from this source.
- **Tail-based trace sampling** keeps errors preferentially. Error ratios computed
  from it are meaningless; only per-trace walking is valid.

State whichever case applies in `Execution Status: Coverage`.

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

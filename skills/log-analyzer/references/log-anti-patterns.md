# Log-Analysis Anti-Patterns

This file is **always loaded**. It is the short list of mistakes that make log analysis worse than no analysis at all. Each anti-pattern below has been observed in real reports.

## A1 — "First ERROR = root cause"

**Wrong**: greps for `ERROR`, takes the earliest line, declares it the cause.

**Why wrong**: The first ERROR is usually the first **symptom**. The cause typically lives in the 30 seconds *before* the first ERROR — a deploy event, a config push, a connection-pool exhaustion warning, a quota approach.

**Fix**: For each High-severity error class, locate the first instance and capture the 30 lines of context **before** it (the run-up). Apply the Causation Discipline Gate.

## A2 — "N errors is a lot" (without denominator)

**Wrong**: Reports "87 errors" or "12000 errors" as if the count itself were the finding.

**Why wrong**: 87 errors over 5 M requests is healthy. 12000 errors is a deploy disaster or normal background — depends entirely on the denominator.

**Fix**: Always pair counts with `error_ratio` and a baseline window. See `log-statistical-methods.md`.

## A3 — "Pasting a Bearer token into the report"

**Wrong**: Quotes a log line containing `Authorization: Bearer eyJhbGciOiJ…`, an API key, an email, or a session cookie.

**Why wrong**: The token is now in a chat / PR / postmortem document. It must be considered compromised. Rotation is mandatory. The user did not ask for that fallout.

**Fix**: Apply PII / Secret Redaction Gate **before** quoting. See `log-pii-redaction.md`.

## A4 — "Concluding from a 30-second slice"

**Wrong**: User pastes 80 lines from the middle of an outage; analyst draws conclusions about onset, peak, and recovery.

**Why wrong**: Onset usually lives 5–30 minutes earlier; recovery is sometimes hours later. The middle 80 lines are unrepresentative.

**Fix**: Apply Time Window Gate. State the window explicitly. If it is partial, refuse to draw onset / recovery conclusions and surface the gap.

## A5 — "Symptom cluster mistaken for cause"

**Wrong**: Reports the largest error cluster ("every service is timing out") as the cause.

**Why wrong**: The biggest cluster is almost always the **symptom** of one upstream failure. The cause cluster is small (often 1–3 lines) and arrives milliseconds-to-seconds before the symptoms. See `log-cascade-analysis.md`.

**Fix**: Order errors by time, look at the first 30 seconds, identify the smallest specific error class as cause-cluster candidate.

## A6 — "Trace ID present but ignored"

**Wrong**: Lists individual error lines without ever pivoting on `trace_id` / `request_id` to walk the failed request end-to-end.

**Why wrong**: One walked trace is worth ten counted errors. The lifecycle reveals the failing hop and the boundary it crossed; counts cannot.

**Fix**: Apply Correlation Gate. Walk at least one representative trace if IDs are present.

## A7 — "Identifier-laden `msg` strings counted literally"

**Wrong**: Groups by `msg` field and reports "200 distinct error messages" when really there are 5 classes inflated by embedded `order_id` / `user_id`.

**Why wrong**: Cardinality from identifiers obscures the real pattern. Top-N becomes useless.

**Fix**: Strip identifiers before grouping. See "Cluster the Error Lines Before You Count" in `log-statistical-methods.md`.

## A8 — "Calling `level=warn` retries 'broken'"

**Wrong**: Flags every WARN or `retrying after error` line as a defect.

**Why wrong**: Healthy systems retry on transient failures. WARN is the right level for that. Reporting them as findings drowns the real signal.

**Fix**: Distinguish *retry that succeeded* (healthy) from *retry that exhausted budget* (finding). Confirm by checking whether the same `request_id` eventually returned 200.

## A9 — "Counting stack-trace frames as separate errors"

**Wrong**: A single Go panic prints 80 lines (one per goroutine frame); naïve counting reports "80 errors".

**Why wrong**: That is one error event, not 80. Counts and severity are inflated 80×.

**Fix**: Aggregate multi-line stack traces into one logical record. See `log-format-cheatsheet.md` → "Multi-line stack traces".

## A10 — "Comparing windows of different lengths"

**Wrong**: Compares "last hour: 400 errors" to "yesterday all day: 600 errors" and concludes things are worse.

**Why wrong**: Per-hour, last hour is much worse than yesterday's average. Per-day, last hour is much better. The two cannot be compared without normalising.

**Fix**: Always compare windows of equal length. Prefer rate (`errors/min`) over absolute counts. See `log-statistical-methods.md`.

## A11 — "Hypothesis presented as confirmed"

**Wrong**: Writes "the deploy at 14:00 caused the outage" without showing the deploy event in logs *or* a strong correlation with the error onset.

**Why wrong**: Plausibility is not evidence. The user may roll back a deploy that did not cause the issue.

**Fix**: Label findings as `Confirmed`, `Hypothesis`, or `Hypothesis — needs corroboration: <source>`. Each hypothesis must list the data that would refute it.

## A12 — "Aggregator counts without sampling check"

**Wrong**: Quotes "Datadog shows 5000 ERRORs" without checking if logs sampling, ingest sampling, or quota drops are in effect.

**Why wrong**: With 10% sampling, the real count is 50000. With a quota drop, the real count is unbounded. Either way, the reported number is wrong.

**Fix**: Inspect aggregator sampling configuration and state it in `Execution Status: Coverage`. See `log-aggregator-queries.md`.

## A13 — "Naming individuals in findings"

**Wrong**: "The deploy by Alice at 14:00 caused…"

**Why wrong**: Log analysis hands off to post-mortem writing, which must be blameless. Naming individuals undermines that and is not a useful causal lever — the deploy-review process is.

**Fix**: Use "the deploy at 14:00" or "config v823 rollout". See `incident-postmortem` Gate 2 (Blameless Framing).

## A14 — "Refusing to surface that the data is insufficient"

**Wrong**: Producing a confident-sounding root cause when the logs do not actually support one (because correlation IDs are missing, or the time window is partial, or upstream logs are unavailable).

**Why wrong**: Confidence without evidence misroutes downstream work — the rollback, the alert, the postmortem action items all aim at the wrong thing.

**Fix**: Use `Hypothesis — needs corroboration` and populate `Open Questions` with the exact additional data needed.

## A15 — "Skipping `Execution Status` because findings are clear"

**Wrong**: Strong findings, no Execution Status section.

**Why wrong**: A reader cannot tell whether you scanned 10 lines or 10 GB. The findings are not auditable. "No findings" without Execution Status is even worse — it implies "I checked everything" when really you may have checked nothing.

**Fix**: Execution Status is mandatory regardless of findings count.

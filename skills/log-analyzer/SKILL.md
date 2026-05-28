---
name: log-analyzer
description: Senior-SRE log analysis specialist. Use when investigating incidents from logs, triaging error spikes, extracting timelines, correlating distributed traces, or separating signal from noise across plain-text, JSON (slog/zap), syslog, journald, container, and Kubernetes logs. ALWAYS use when the user asks to "analyze logs", "find the error", "what went wrong", "investigate this outage", "correlate request_id/trace_id", "look at the log file", or hands over log dumps / aggregator queries / kubectl logs output. Hands off to incident-postmortem when a blameless post-mortem document is requested.
allowed-tools: Read, Grep, Glob, Bash(grep *), Bash(awk *), Bash(sed *), Bash(jq *), Bash(rg *), Bash(wc *), Bash(sort *), Bash(uniq *), Bash(cut *), Bash(head *), Bash(tail *), Bash(zcat *), Bash(gzip *), Bash(date *), Bash(journalctl *), Bash(kubectl logs *), Bash(stat *), Bash(file *)
---

# Log Analyzer

## Purpose
Use this skill to extract **actionable, evidence-backed findings** from logs — not to dump filtered output. The analysis must:

- detect log format before parsing,
- redact PII before quoting,
- distinguish *first* error from *root cause*,
- separate noise from signal with statistical reasoning,
- correlate across services using `trace_id` / `request_id`,
- and end with a prioritised list of hypotheses + recommendations.

The skill is the upstream half of incident response: it produces the **evidence package** that `incident-postmortem` formats into a blameless RCA. Use them together, in that order.

## Quick Reference

| When you need to… | Jump to |
|---|---|
| Pick analysis depth (Lite / Standard / Strict) | §Analysis Modes |
| Detect what kind of logs you are looking at | §Mandatory Gates → Gate 1 |
| Avoid leaking secrets / PII in the report | §Mandatory Gates → Gate 2 |
| State the time window you analysed | §Mandatory Gates → Gate 3 |
| Decide whether N errors is signal or noise | §Mandatory Gates → Gate 4 |
| Correlate logs across services | §Mandatory Gates → Gate 5 |
| Know what NOT to call a root cause | §Mandatory Gates → Gate 6 |
| Cap finding volume, route overflow to Residual Risk | §Mandatory Gates → Gate 7 |
| Execute the analysis end-to-end | §Workflow |
| See a complete formatted output | Load `references/example-output.md` |
| Hand off to a post-mortem | §Hand-off Protocol |

## When To Use

Trigger this skill when:

- the user asks to **analyse / investigate / look at / triage** logs,
- the user pastes log lines, a file path, a `kubectl logs` / `journalctl` dump, or a Loki/ELK/Datadog query result,
- the user reports an outage / regression / flaky behaviour and points at log evidence,
- another skill needs an evidence package before producing a post-mortem (`incident-postmortem`) or a runbook update.

Do **not** use this skill for:

- writing new log statements in source code (that is `go-observability-review` territory),
- designing alerts / dashboards (`monitoring-alerting`),
- formal post-mortem authoring (`incident-postmortem`),
- debugging code without log evidence (`systematic-debugging`).

## Analysis Modes (Lite / Standard / Strict)

State the chosen mode in the report. **Default: `Standard`.**

Mode selection rules:

- Choose `Lite` only when scope is small (single service, ≤ 1 hour window, < 100 MB log volume) **and** no security / data-integrity / customer-impact signal is present.
- Choose `Strict` whenever any of: SEV-1/SEV-2 incident framing, customer-visible outage, suspected security event, data corruption, multi-service correlation across 3+ components, or a post-mortem deliverable.
- Use `Standard` for everything else.

### Lite (fast triage)
- Goal: answer "is something on fire right now, and what should I look at first?"
- Minimum execution: format detection, error/warn count by class, first occurrence timestamp, top-3 patterns.
- Skip: cross-service correlation, statistical baseline, cascade reconstruction unless the data invites it.
- Finding volume: soft target ≤ 5 findings.

### Standard (default balanced analysis)
- Goal: produce a defensible evidence package suitable for engineer hand-off.
- Full workflow applies as written.
- Expected execution: format detection + redaction + time window + counts + first-occurrence pivot + correlation pass + cascade analysis + ≥ 2 root cause hypotheses.
- Finding volume: soft target ≤ 10 findings.

### Strict (incident / post-mortem grade)
- Goal: investigation-grade evidence package, traceable line-by-line.
- Minimum execution: all of Standard plus baseline comparison against a known-good window, exhaustive correlation by `trace_id` AND `request_id` AND user/tenant identifier, explicit cascade graph (caused-by chain), and a Hand-off Protocol section pre-filled for `incident-postmortem`.
- Finding volume: soft target ≤ 15 findings; never drop High-severity.

## Mandatory Gates

Gates are serial hard blockers. Failure at any gate stops subsequent work and is reported explicitly in the output.

### 1) Format Detection Gate
Before parsing, identify the log format. Log analysis tools and quoting rules depend on it.

| Signal | Format | Default tooling |
|---|---|---|
| First non-blank line starts with `{` and parses as JSON | JSON (likely `slog`, `zap`, `pino`, `bunyan`) | `jq`, `rg` |
| Lines start with RFC 3164/5424 priority `<NN>` or `<DATE> HOST PROC[PID]:` | syslog | `awk`, `grep`, `journalctl -p` |
| Lines start with ISO-8601 + level keyword (`INFO`, `ERROR`) | text-structured | `grep`, `awk` |
| Output of `kubectl logs ...` (optional `-c`) | container stdout | `kubectl logs --since=… --tail=…`, then treat per inner format |
| Output of `journalctl -o json` | systemd journal JSON | `jq`, `journalctl --since … --until …` |
| Multi-line stack traces (Go panic, Java exception, Python traceback) | mixed — needs aggregation | block-aware `awk` / `rg --multiline` |

Record in Execution Status: `Format: <detected>` plus the regex / `jq` filter the analysis used.
If multiple formats are present (e.g., a JSON service log that includes a panic stack trace), state both and split the analysis.

### 2) PII / Secret Redaction Gate
Logs frequently contain credentials, tokens, customer identifiers, and personal data. The report **MUST NOT** echo unredacted secrets back to the user. This is a hard requirement, not advisory.

Always redact before quoting:

| Class | Examples | Redaction |
|---|---|---|
| Bearer tokens / JWTs | `Authorization: Bearer eyJ…`, `Bearer eyJhbGc…` | `Bearer ***REDACTED***` |
| API keys | `sk-…`, `AKIA…`, `xoxb-…`, `ghp_…` | `***REDACTED-API-KEY***` |
| Passwords / secrets in URLs | `postgres://user:hunter2@host/db` | `postgres://user:***@host/db` |
| Email addresses | `alice@example.com` | `a***@example.com` |
| Phone numbers | `+1-555-123-4567` | `+1-***-***-4567` |
| Credit card / IBAN | 13–19 digit groups | `***REDACTED-PAN***` |
| Government IDs | SSN `123-45-6789`, others | `***REDACTED-ID***` |
| Cookies / session IDs | `Cookie: session=…` | `Cookie: session=***` |

Quoting rule: when including a sample log line in the report, present it as a fenced code block with the redaction already applied. Never paste raw lines verbatim if they contain any of the above.

If you are unsure whether a field is sensitive, redact by default and note `(redacted by analyst — uncertainty)` next to the line.

### 3) Time Window Boundary Gate
Every report **MUST** explicitly state the analysed time window in absolute UTC, with the source of those bounds. This prevents the most common error in log review: drawing conclusions from an unrepresentative slice.

Required record:
- `Window: <start UTC> → <end UTC>` (ISO-8601, e.g., `2026-04-28T08:14:00Z → 2026-04-28T09:30:00Z`),
- `Source: <log file path / aggregator query / kubectl args / journalctl --since>`,
- `Coverage: <full | partial — reason>`. State partial when log rotation, retention, sampling, or a paged-out aggregator query may have truncated the data.

If the user only provides a snippet without timestamps, state `Window: unknown — only N lines provided, no timestamp parse possible` and stop drawing time-based conclusions.

### 4) Statistical Significance Gate
A raw count is meaningless without a denominator. Before calling something "frequent" or "spike":

- compute or estimate the **request / event base rate** for the same window (e.g., total request volume, healthy traffic count),
- compare against a **baseline window** of the same length when available (e.g., the previous hour, same hour yesterday),
- prefer **rate** (`errors/sec`, `error_ratio = errors / total`) over absolute counts.

Heuristic anchors (state when you apply them):

| Pattern | Likely signal? |
|---|---|
| `error_ratio` ≥ 1% sustained over the window | Yes |
| `error_ratio` < 0.01% in a high-traffic service | Likely background noise |
| ≥ 3× baseline window for the same error class | Yes (spike) |
| 1 occurrence of a single error in 1M log lines | Almost certainly noise — note and move on |
| New error class never seen in the baseline window | Always investigate, regardless of count |

If neither base rate nor baseline is available, state `Statistical context: unavailable` and explicitly downgrade confidence on every "this is frequent" claim.

### 5) Correlation Gate
Modern services emit `trace_id`, `request_id`, `span_id`, `tenant_id`, `user_id`. Reconstructing a *failed user journey* requires walking these IDs across logs, not just listing errors.

Procedure:

1. From the first selected error sample, extract every correlation field present (`trace_id`, `request_id`, `span_id`, `user_id`, `tenant_id`, …).
2. Search across **all** in-scope log sources (services, sidecars, gateway, message queue) for that `trace_id` / `request_id`.
3. Order results by timestamp to reconstruct the request lifecycle.
4. Annotate each hop with: service, operation, status, latency, and the boundary it crossed (HTTP / gRPC / Kafka / DB).

If correlation IDs are missing entirely from the logs, raise this as a **High-severity Observability finding** in its own right — debugging is fundamentally degraded without them, and the absence is itself an actionable defect (see `references/log-correlation.md`).

### 6) Causation Discipline Gate (First-Error vs Root-Cause)
The first error in time is **not** automatically the root cause. The most common log-analysis failure is to grep for `ERROR`, take the earliest hit, and call it the cause.

Always apply the causation chain:

1. **Symptom**: what the user / SLO observed (e.g., 502s for 12 minutes).
2. **Proximate trigger**: the immediate failing component visible in logs (e.g., upstream DB pool exhaustion).
3. **Underlying cause**: why the proximate component failed (e.g., long-running migration holding row locks).
4. **Contributing factors**: amplifiers (e.g., retry storm, missing circuit breaker, alert misrouted).

Each link in the chain must be backed by a quoted, redacted log line or a referenced metric.

When the chain cannot be completed from logs alone (e.g., the underlying cause is a config change visible only in deploy events), state **`Hypothesis — needs corroboration: <source>`** rather than presenting it as confirmed.

### 7) Volume Cap & Severity-Tiered Reporting Gate
Findings have a soft cap by mode (5 / 10 / 15). Everything above the cap goes to `Residual Risk / Investigation Gaps` rather than being silently dropped.

Phases:

- **Phase 1 — High**: Report ALL High findings. High is never dropped by the cap.
- **Phase 2 — Medium**: Fill remaining slots with Medium findings, ordered: customer-impacting → engineer-debug-blocker → operational hygiene.
- **Phase 3 — Low**: Only if slots remain.
- **Overflow**: Move displaced candidates to Residual Risk with one-line summary (`severity | category | location | one-line description`) and add `N additional issues moved to Residual Risk` to the Summary.

Example: Standard mode, 3 High + 9 Medium found → report 3 High + 7 Medium as findings, move 2 Medium to Residual Risk.

## Workflow

Steps run in order. Skip a step only if it does not apply, and state why in Execution Status.

0. **Select mode** (`Lite | Standard | Strict`) and record selection rationale.

1. **Define scope.**
   - Confirm log sources: file paths, glob patterns, `kubectl` / `journalctl` arguments, aggregator query strings.
   - Estimate volume (`wc -l`, `du -sh`, or query result count). For files > 1 GB or > 10 M lines, refuse line-by-line scanning and switch to streaming patterns (see `references/log-tooling-commands.md`).
   - State the hypothesis the user gave you. ("Why are checkout 502s spiking" is different from "Show me everything that broke today.")

2. **Apply Format Detection Gate** (Gate 1). Record the detected format and parsing tooling.

3. **Apply PII / Secret Redaction Gate** (Gate 2) before opening files for direct quoting. Decide the redaction set up-front — do not retro-redact after writing the report.

4. **Apply Time Window Gate** (Gate 3). Lock the bounds. If the user implies "today" or "recently", convert to absolute UTC and state it.

5. **Reference Loading Gate.** Load reference files matching the situation **before** drawing conclusions:

   - JSON / structured logs → `references/log-format-cheatsheet.md`
   - Multi-service / microservices → `references/log-correlation.md`
   - Loki / ELK / Datadog / CloudWatch query needed → `references/log-aggregator-queries.md`
   - "Is this a real spike?" — `references/log-statistical-methods.md`
   - About to quote a log line → `references/log-pii-redaction.md`
   - Cascading failures suspected → `references/log-cascade-analysis.md`
   - Tooling refresher (jq / awk / kubectl / journalctl) → `references/log-tooling-commands.md`
   - Always loaded → `references/log-anti-patterns.md`, `references/log-analysis-quick-checklist.md`

   Record loaded references in Execution Status. **This is a mandatory gate**: drawing conclusions about correlation, statistical significance, or PII handling without loading the matching reference is a contract violation.

6. **Quick scan.** Counts by level / class. Top error patterns. First and last occurrence per class. Compute `error_ratio` if denominator data is available.

7. **First-occurrence pivot.** For each High-severity error class, locate the **first** instance in the window and capture the 30 lines of context before it (the run-up, not just the failure). The cause usually lives there, not at the first ERROR line.

8. **Apply Correlation Gate** (Gate 5). For ≤ 3 representative failed requests / traces, walk the full lifecycle across services. Build a per-request timeline.

9. **Cascade analysis.** Cluster errors that share a trigger (e.g., 12 downstream timeouts that all hit at +200ms after one upstream failure). Distinguish *cause cluster* vs *symptom cluster*. Reference: `log-cascade-analysis.md`.

10. **Apply Statistical Significance Gate** (Gate 4) on every "frequent" / "spike" claim. Downgrade or drop claims that fail it.

11. **Apply Causation Discipline Gate** (Gate 6). Construct the causation chain for each leading hypothesis: symptom → proximate trigger → underlying cause → contributing factors.

12. **Hypotheses & severity.** Produce ≥ 2 root cause hypotheses ranked by likelihood, each grounded in quoted evidence. State what additional data would confirm or refute each.

13. **Apply Volume Cap Gate** (Gate 7). Tier findings, route overflow to Residual Risk.

14. **Hand-off.** If the user is heading to a post-mortem, fill the Hand-off Protocol section with the structured fields `incident-postmortem` consumes (see §Hand-off Protocol).

## Severity Rubric

- **High**: customer-visible outage / data loss / data corruption / security event / SLO breach actively in progress / debugging fundamentally degraded (e.g., correlation IDs absent in production logs).
- **Medium**: latent reliability or maintainability defect, error class that increases on-call toil but has not yet caused user impact, observability gap that masks a category of failures.
- **Low**: log hygiene issue, cosmetic noise, redundant fields, format inconsistency that is annoying but not load-bearing.

## Evidence Rules

- Every finding **MUST** include:
  - exact source location (`path:line`, or aggregator query + timestamp range, or `kubectl logs <pod> -c <container>` + window),
  - the **redacted** log sample (1–5 lines),
  - the inference made from that sample,
  - what would refute the inference.
- Clearly label `Confirmed` vs `Hypothesis` vs `Hypothesis — needs corroboration`. Promoting a hypothesis to confirmed without evidence is a contract violation.
- Do not fabricate timestamps, IDs, or counts. If a number is approximate, write `~` and explain.

### Anti-patterns (DO NOT report these as findings)
See `references/log-anti-patterns.md` (always loaded). Examples:

- Treating the **first** ERROR line as the root cause without checking the run-up.
- Calling 3 errors in 100 M log lines a "spike".
- Quoting a log line containing `Bearer eyJhbGc…` without redaction.
- Reporting `level=warn` lines from a healthy retry path as defects.
- Drawing conclusions from a 30-second slice of a 12-hour incident.

## Output Format (Required)

### Analysis Mode
- `Lite | Standard | Strict`
- mode selection rationale (1–2 lines)

### Window & Source
- `Window: <start UTC> → <end UTC>`
- `Source: <paths / queries / kubectl args>`
- `Coverage: full | partial — <reason>`
- `Format: <detected>` (per source if mixed)

### Executive Summary
1–3 lines. Lead with the answer to the user's actual question. Include origin breakdown: `X confirmed / Y hypothesis / Z needs corroboration`. If volume cap fired, note: `N additional issues moved to Residual Risk`.

### Findings
List findings ordered by severity (High → Medium → Low), then by confidence (Confirmed → Hypothesis).

#### [High|Medium|Low] Short title
- **ID:** `LOG-001`
- **Confidence:** `Confirmed | Hypothesis | Hypothesis — needs corroboration`
- **Category:** `availability | latency | data-integrity | security | observability | hygiene`
- **Location:** `path:line` or `<aggregator-query>` or `<kubectl args> @ <timestamp>` (or location list for merged findings)
- **Evidence:** redacted log sample (fenced code block, ≤ 5 lines)
- **Inference:** what the evidence implies
- **Causation chain (when applicable):** symptom → proximate → underlying → contributing
- **Refuter:** what additional data would prove this wrong
- **Recommendation:** specific next action

### Timeline
Chronological reconstruction of the most-impactful failed flow(s), one row per significant event. Use UTC timestamps.

| Time (UTC) | Service | Event | trace_id / request_id |
|---|---|---|---|

### Correlation Map
For Standard / Strict modes when multiple services are involved. List the failed traces walked end-to-end with cross-service hops, statuses, and latencies. If correlation IDs are absent, state `Correlation IDs missing — see High Observability finding`.

### Root Cause Hypotheses
Ranked, each with:
- the chain (symptom → underlying),
- supporting evidence,
- refuter,
- next data needed to confirm.

### Recommendations
Numbered, ordered by impact × ease. For each: `Owner suggestion`, `Effort (S/M/L)`, and `Expected effect`.

### Suppressed Items
Patterns that looked alarming but were suppressed by the gates. One line each: pattern + why suppressed (base rate / known healthy retry / non-user-controlled / …).

### Execution Status
- `Format`: detected per source
- `Window`: as above
- `Files / queries scanned`: count + total size
- `References loaded`: list
- `PII redaction applied`: `yes (categories: …) | no — none detected`
- `Statistical baseline`: `<window> | unavailable — reason`
- `Correlation IDs present`: `trace_id | request_id | span_id | user_id` (✓/✗)
- `External tools run`: `jq | rg | awk | kubectl logs | journalctl | aggregator query` with PASS / FAIL / Not run + reason
- If a tool was not run, state `Not run in this environment` plus the exact command the user can run.

### Open Questions
Only blockers that materially change the conclusion (e.g., "do you have logs from the upstream gateway? if not, my hypothesis 2 cannot be ruled out").

### Residual Risk / Investigation Gaps
- Volume-cap overflow (`severity | category | location | one-line description`) — so no validated issue is silently dropped.
- Time-window gaps — log rotation / retention / sampling that may have hidden evidence.
- Coverage gaps — services or hops you could not see.

### Hand-off Protocol
Fill this section when the user is heading to a post-mortem (always for `Strict` mode, and on request for `Standard`). The fields map directly into `incident-postmortem` Gate 1.

```
incident_id: <user-supplied or "TBD">
impact_summary: <≤ 1 sentence>
window_utc: <start> → <end>
affected_services: <list>
data_sources: <list of files / queries>
top_findings: [LOG-001, LOG-002, …]   # IDs from §Findings
leading_hypothesis: <one paragraph, redacted>
blameless_framing: <symptom-and-system phrasing>   # avoid naming individuals
```

### Summary
1–3 lines. Restate the leading hypothesis, the confidence level, and the next concrete data the user should fetch. If volume cap fired, include `N additional issues moved to Residual Risk`.

## No-Finding Case

If the logs in scope show no actionable issue:

- Explicitly say: `No actionable findings in window.`
- Still produce: Analysis Mode, Window & Source, Executive Summary (one line: "Window appears healthy."), Execution Status, Statistical Significance note (`error_ratio` for the window), Coverage gaps (anything you could *not* see), Recommendations (e.g., widen window, add missing correlation ID).

A "no findings" report with no Execution Status section is a contract violation — the absence of findings must be backed by evidence of what was scanned.

## Hand-off Protocol (detail)

**To `incident-postmortem`** (most common): produce the structured block in §Hand-off Protocol. The post-mortem skill consumes `incident_id`, `impact_summary`, `window_utc`, `affected_services`, `data_sources`, `top_findings` directly into its Gate 1 (Incident Context Collection) and skips re-collection.

**To `monitoring-alerting`**: when the leading finding reveals a missing alert (e.g., "no SLO burn-rate alert on this endpoint"), include a recommendation tagged `→ monitoring-alerting` and copy the failing pattern into the Recommendation field so the alerting skill can pick up the work.

**To `systematic-debugging`**: when logs alone cannot reach the underlying cause (e.g., need to instrument code, run profiler, or reproduce locally), tag the recommendation `→ systematic-debugging` and supply the redacted reproduction signal.

## Skill Maintenance

Run regression checks for this skill with:

```bash
bash skills/log-analyzer/scripts/run_regression.sh
```

## Appendix: Reference Loading Triggers

| Reference | Trigger |
|---|---|
| `references/log-anti-patterns.md` | Always loaded |
| `references/log-analysis-quick-checklist.md` | Always loaded |
| `references/log-format-cheatsheet.md` | Logs detected as JSON / syslog / journald / mixed |
| `references/log-correlation.md` | Multi-service scope OR `trace_id`/`request_id` referenced |
| `references/log-aggregator-queries.md` | Loki / ELK / Datadog / CloudWatch / Splunk / Grafana mentioned |
| `references/log-statistical-methods.md` | Any "frequent / spike / increase / regression" claim |
| `references/log-pii-redaction.md` | Before quoting any log line in the report |
| `references/log-cascade-analysis.md` | Multiple services / queues / dependents in scope |
| `references/log-tooling-commands.md` | jq / awk / kubectl / journalctl / streaming patterns needed |
| `references/example-output.md` | When formatting the final report |

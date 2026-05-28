# Log Aggregator Query Templates

When logs live in an aggregator instead of files, the choice of query language matters as much as the analysis. Wrong query → wrong window → wrong conclusion.

Always state the **query string and time bounds** in the report so others can re-run.

## Loki / Grafana (LogQL)

Loki separates **stream selectors** (label-based, fast) from **filters** (line-content). Always start with the smallest stream selector that scopes correctly, then filter.

```logql
# Errors from one service in the window
{app="checkout-svc", env="prod"} |= "level=error"

# JSON: parse then filter
{app="checkout-svc"} | json | level="ERROR"

# By trace_id (powerful: no service needed)
{env="prod"} | json | trace_id="4bf92f3577b34da6a3ce929d0e0e4736"

# Rate over time — feed into a graph or alert
sum by (path) (rate({app="checkout-svc"} | json | level="ERROR" [5m]))

# Error ratio (the right number to alert on)
sum(rate({app="checkout-svc"} | json | level="ERROR" [5m]))
  /
sum(rate({app="checkout-svc"} | json [5m]))
```

Tips:
- Stream selectors must include at least one `=` matcher; `{}` alone is rejected.
- Avoid `|~ ".*"` — it scans all log content; cripples performance.
- For multi-tenant systems, always include the tenant label in the selector.

## Elasticsearch / OpenSearch (KQL or Query DSL)

KQL (Discover) for ad-hoc:
```
service: "checkout-svc" and level: "ERROR" and @timestamp >= "2026-04-28T08:00:00Z"
```

By trace ID:
```
trace_id: "4bf92f3577b34da6a3ce929d0e0e4736"
```

Query DSL (programmatic):
```json
{
  "query": {
    "bool": {
      "filter": [
        { "term":  { "service": "checkout-svc" } },
        { "term":  { "level":   "ERROR" } },
        { "range": { "@timestamp": { "gte": "2026-04-28T08:00:00Z", "lt": "2026-04-28T09:00:00Z" } } }
      ]
    }
  },
  "size": 0,
  "aggs": {
    "by_msg": { "terms": { "field": "msg.keyword", "size": 20 } }
  }
}
```

Tips:
- Use `term` for exact-match fields (`.keyword`); use `match` only when you want analysis.
- Always pin a time range — the index can be huge.
- For top-N error patterns, an `aggs.terms` over `msg.keyword` is usually what the user wants.

## Datadog (Logs Search)

```
service:checkout-svc env:prod status:error @http.url:/v1/checkout
```

By trace:
```
service:* @trace_id:4bf92f3577b34da6a3ce929d0e0e4736
```

Datadog auto-correlates traces and logs via `@trace_id`; the request flame graph is one click from any matching log.

For "is this a spike?" use the **Logs Analytics** tab with `count by status` over the window vs the previous window.

## CloudWatch Logs Insights

```
fields @timestamp, @message, level, msg, trace_id
| filter level = "ERROR"
| filter @logStream like /checkout-svc/
| sort @timestamp desc
| limit 100
```

Aggregate by message:
```
fields @timestamp, msg
| filter level = "ERROR"
| stats count(*) as n by msg
| sort n desc
| limit 20
```

Tips:
- Only one log group per query unless you use cross-log-group queries (paid feature).
- The query language is its own dialect — not SQL, not LogQL.
- For long windows, sample (`| limit`) and acknowledge the sampling in the report.

## Splunk (SPL)

```
index=prod sourcetype=checkout-svc level=ERROR earliest=-1h@h latest=@h
| stats count by msg
| sort -count
```

By trace:
```
index=prod trace_id="4bf92f3577b34da6a3ce929d0e0e4736"
| sort _time
```

Tips:
- Always pin `earliest=` / `latest=`; SPL silently scans the entire retention if omitted.
- `stats count by ...` is the right primitive for "top-N by some field".

## Cross-Aggregator Concepts to Always State

When the report quotes an aggregator query, include all four:

1. **Aggregator + index/dataset**: `Loki / prod`, `Elasticsearch index logs-*`, `Datadog`.
2. **Time bounds**: absolute UTC, not "last hour". Aggregator UI defaults shift; absolute times are reproducible.
3. **The query itself**: literal, copy-pasteable.
4. **Result count**: hits, log volume scanned, sampling rate (if any).

Without these, "the aggregator showed errors" is not auditable.

## Sampling, Rollups, and the Truth-in-Logs Problem

High-volume aggregators sometimes:

- **Sample at ingest** (e.g., Datadog logs sampling rules) — your error count is a multiple of what you see.
- **Roll up older data** — older windows have lower resolution.
- **Quota-drop** — once a tier limit is hit, lines are silently discarded.

Before building a hypothesis on aggregator counts, check:

```bash
# Loki: is the result count suspiciously round? Possible quota drop.
# Datadog: check Logs > Configuration > Indexes for sampling rules.
# Elasticsearch: check ILM / hot-warm-cold rollups for the index.
```

State sampling explicitly in `Execution Status: Coverage`. "I got 10000 ERROR lines" is meaningless if 90% were dropped at ingest.

## Cost-Conscious Querying

Aggregator queries cost money or quota. For each investigation:

- Build the **smallest selector that bounds correctly** (service + env + time).
- Filter on indexed fields (`service`, `level`, `trace_id`) before unindexed fields (`msg`, free text).
- For repeated queries during an investigation, cache the result locally and re-pivot:
  ```bash
  logcli query '{app="checkout-svc"} |= "ERROR"' --since=1h --output=jsonl > /tmp/errs.jsonl
  jq -c 'select(.path=="/v1/checkout")' /tmp/errs.jsonl
  ```

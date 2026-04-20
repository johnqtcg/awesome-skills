# Load Test Result Analysis Guide

## Table of Contents
1. [Reading Percentile Data](#1-reading-percentile-data)
2. [Identifying Saturation](#2-identifying-saturation)
3. [Bottleneck Taxonomy](#3-bottleneck-taxonomy)
4. [Resource Correlation](#4-resource-correlation)
5. [Common Failure Patterns](#5-common-failure-patterns)
6. [SLO Verdict Framework](#6-slo-verdict-framework)
7. [Regression Detection](#7-regression-detection)

---

## 1 Reading Percentile Data

### Why percentiles, not averages
Average latency is mathematically valid but operationally useless. If 99% of
requests take 10ms and 1% take 5 seconds, the average is 60ms — a number no
one actually experiences. Percentiles tell the real story:

| Percentile | Meaning                                    | Use For                    |
|:----------:|--------------------------------------------|----------------------------|
| p50        | Half of requests are faster than this       | Typical user experience    |
| p90        | 90% of requests are faster                  | Good-case experience       |
| p95        | 95% faster — common SLO target              | Service-level objective    |
| p99        | 99% faster — tail latency starts here       | Worst-case SLO             |
| p99.9      | 1 in 1000 — often 10-100x of p50            | Infrastructure issues      |
| max        | Single worst request                        | Outlier investigation      |

### Reading the distribution shape

**Narrow distribution** (p99 < 3x p50): healthy service, consistent performance.
```
p50=12ms  p95=18ms  p99=28ms  max=45ms  → ratio p99/p50 = 2.3x
```

**Wide distribution** (p99 > 10x p50): bimodal behavior or resource contention.
```
p50=8ms  p95=45ms  p99=850ms  max=5.2s  → ratio p99/p50 = 106x
```
This usually indicates: cache hit vs miss paths, GC pauses, connection pool
exhaustion, or intermittent downstream timeout.

**Cliff at specific percentile**: sudden jump indicates a threshold.
```
p50=10ms  p90=12ms  p95=15ms  p99=1.2s  max=5s
```
The p95-to-p99 cliff (15ms -> 1.2s) suggests a capacity limit is hit
at ~95% load — likely connection pool, thread pool, or rate limiter.

---

## 2 Identifying Saturation

### The saturation curve
Plot p99 latency against RPS. A healthy service shows near-flat latency
until a point where it curves sharply upward — that is the saturation point.

```
p99(ms)
  |                                           /
  |                                         /
  |                                       /     ← degradation
  |                                     /
  |            saturation point → * - /
  |     ___________________________/
  |    /     ← healthy zone
  |___/___________________________________
                                        RPS
```

**Saturation point definition**: the RPS where p99 latency exceeds the SLO
threshold AND continues to increase with more load. This is the service's
true capacity — not the peak RPS before errors.

### Identifying what's saturated

| Observation                               | Likely Saturated Resource    |
|-------------------------------------------|-----------------------------|
| CPU > 80% sustained                       | Compute                     |
| Memory growing linearly                   | Memory leak (soak issue)    |
| DB connection pool at max                 | Database connections         |
| Goroutine count climbing                  | Goroutine leak or slow I/O  |
| GC pause time increasing                  | Heap pressure               |
| Open file descriptors near limit          | Socket/file exhaustion      |
| Network bandwidth > 80% capacity          | Network I/O                 |
| Disk I/O wait > 20%                       | Storage I/O                 |
| Response time flat, errors increasing     | Rate limiting / backpressure|

---

## 3 Bottleneck Taxonomy

### Tier 1: Application-level bottlenecks
These are in the service code and fixable by developers:

1. **Serialized processing** — single mutex/lock blocking concurrent requests.
   Signal: throughput doesn't increase with more VUs. CPU stays low.

2. **N+1 queries** — each request triggers N dependent DB calls.
   Signal: latency scales linearly with data size. DB query count >> RPS.

3. **Missing connection pooling** — new TCP connection per request.
   Signal: TIME_WAIT sockets accumulating. Connection setup time dominates.

4. **Unbounded goroutines/threads** — each request spawns work without limits.
   Signal: goroutine count grows linearly with RPS. Memory grows too.

5. **Synchronous external calls** — blocking on slow downstream service.
   Signal: latency matches downstream latency. CPU is idle.

### Tier 2: Infrastructure bottlenecks
These require infrastructure changes:

6. **Insufficient replicas** — each instance is fine, but total capacity is low.
   Signal: per-instance CPU/memory at healthy levels but aggregate throughput
   too low. Horizontal scaling would help.

7. **Database is the bottleneck** — service CPU low, DB CPU/connections high.
   Signal: adding service replicas doesn't help. DB query time dominates.

8. **Network bandwidth** — large payloads saturate the pipe.
   Signal: throughput in bytes/sec plateaus while RPS could go higher.

### Tier 3: Test methodology errors (not real bottlenecks)

9. **Load generator is the bottleneck** — k6 CPU at 100%.
   Signal: `dropped_iterations` metric > 0. Generator CPU maxed.

10. **Network between generator and target** — cross-region testing.
    Signal: min latency equals network RTT. Latency floor is high.

11. **Cache warming artifact** — first N seconds have high latency.
    Signal: p99 drops significantly after 30-60 seconds. Warmup needed.

---

## 4 Resource Correlation

### Correlation checklist
For each identified latency anomaly, check these resource metrics:

```
Latency spike at T=120s
  ├── CPU at T=120s?     → if spike: compute bottleneck
  ├── Memory at T=120s?  → if jump: GC pause or allocation spike
  ├── DB conns at T=120s? → if max: connection pool exhaustion
  ├── Goroutines at T=120s? → if spike: I/O blocking or leak
  ├── GC pause at T=120s? → if > 10ms: heap pressure
  ├── Network at T=120s? → if saturated: bandwidth limit
  └── Error rate at T=120s? → if spike: cascading failure
```

### Useful monitoring commands during tests

**Go services:**
```bash
# Goroutine count
curl http://localhost:6060/debug/pprof/goroutine?debug=1 | head -1

# Heap allocation
curl http://localhost:6060/debug/pprof/heap?debug=1 | head -5

# Full pprof profile (30s)
go tool pprof -http=:8081 http://localhost:6060/debug/pprof/profile?seconds=30
```

**System-level:**
```bash
# CPU and memory per process
top -b -n 1 -p $(pgrep myservice)

# Network connections
ss -s  # summary
ss -tn state established | wc -l  # active connections

# Open file descriptors
ls /proc/$(pgrep myservice)/fd | wc -l
```

**Database (PostgreSQL):**
```sql
-- Active connections
SELECT count(*) FROM pg_stat_activity WHERE state = 'active';

-- Slow queries during test
SELECT query, calls, mean_exec_time, max_exec_time
FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;
```

---

## 5 Common Failure Patterns

### Pattern 1: Gradual degradation
```
t=0:   p99=25ms   errors=0%
t=60:  p99=35ms   errors=0%
t=120: p99=80ms   errors=0.1%
t=180: p99=250ms  errors=1.2%
t=240: p99=1.5s   errors=8.5%
```
**Diagnosis**: resource exhaustion — connection pool, memory, or file descriptors.
Look for a monotonically growing counter (connections, goroutines, memory).

### Pattern 2: Sudden cliff
```
t=0-180: p99=20ms  errors=0%
t=181:   p99=5.2s  errors=45%
```
**Diagnosis**: hard limit hit — max connections, OOM kill, thread pool saturated.
Check for: pod restart (OOM), connection refused, circuit breaker tripped.

### Pattern 3: Periodic spikes
```
p99 oscillates: 20ms → 200ms → 20ms → 200ms (every 90s)
```
**Diagnosis**: GC pauses (Java/Go), log rotation, health check interference,
cron job on same host, autoscaler oscillation.

### Pattern 4: Bimodal latency
```
p50=8ms  p90=12ms  p95=15ms  p99=1.2s
```
**Diagnosis**: two code paths with different costs. Typically: cache hit (8ms)
vs cache miss + DB query (1.2s). Fix: pre-warm cache, reduce DB query time,
or increase cache hit rate.

### Pattern 5: Load generator artifact
```
RPS target: 5000    Actual RPS: 3200    dropped_iterations: 1800
p99=45ms  errors=0%
```
**Diagnosis**: generator can't keep up. Service is fine — test is broken.
Fix: use more powerful generator, distributed k6, or reduce per-request overhead.

---

## 6 SLO Verdict Framework

### Verdict categories

| Result                           | Verdict      | Action                              |
|----------------------------------|--------------|--------------------------------------|
| All SLOs pass, no anomalies      | **PASS**     | Document, archive, ship              |
| All SLOs pass, anomalies found   | **WARN**     | Investigate anomalies before ship    |
| Any SLO fails                    | **FAIL**     | Fix bottleneck, retest              |
| Insufficient data                | **INCONCLUSIVE** | Extend test duration/scope       |

### Verdict report template
```
## SLO Verdict: [PASS/WARN/FAIL/INCONCLUSIVE]

| SLO                  | Target    | Actual     | Status |
|----------------------|-----------|------------|--------|
| p50 latency          | < 50ms    | 12ms       | PASS   |
| p99 latency          | < 200ms   | 185ms      | PASS   |
| Throughput           | > 5000    | 5,231 RPS  | PASS   |
| Error rate           | < 0.1%   | 0.03%      | PASS   |
| p99.9 latency        | < 1s     | 890ms      | WARN   |

### Anomalies
- p99.9 at 890ms suggests tail latency issue (GC or cache miss path)
- Memory grew 12% over 5 min — possible leak (needs soak test)

### Risks
- Soak test not run — memory leak risk unvalidated
- Only GET endpoints tested — POST/PUT capacity unknown
```

---

## 7 Regression Detection

### Comparing runs
When comparing current results against a baseline:

```
                    Baseline        Current         Delta
p50                 12ms            14ms            +17% ⚠️
p95                 35ms            38ms            +8.5%
p99                 85ms            92ms            +8.2%
Throughput          5,200 RPS       5,150 RPS       -1.0%
Error rate          0.02%           0.03%           +50% ⚠️
```

### Significance thresholds

| Metric          | Acceptable | Warning  | Regression |
|-----------------|:----------:|:--------:|:----------:|
| p50 delta       | < 10%      | 10-20%   | > 20%      |
| p99 delta       | < 15%      | 15-30%   | > 30%      |
| Throughput delta| < 5%       | 5-15%    | > 15%      |
| Error rate delta| < 2x       | 2-5x     | > 5x       |

Deltas within acceptable range may still be noise. Require at least 3
runs to establish statistical confidence. Single-run comparisons are
suggestive, not conclusive.

### What to report in regressions
1. Which SLO metric regressed and by how much
2. At what RPS level the regression becomes visible
3. Correlation with recent code changes (git log since baseline)
4. Resource metric deltas (CPU/memory/connections) at same RPS
5. Recommended investigation path (profile, trace, or targeted test)
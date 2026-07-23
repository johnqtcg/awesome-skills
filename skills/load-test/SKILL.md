---
name: load-test
description: >
  Performance load testing specialist for writing k6/vegeta/wrk scripts, defining
  SLOs, modeling scenarios (spike/soak/stress/breakpoint), analyzing results, and
  identifying bottlenecks. ALWAYS use when writing load test scripts, reviewing test
  results, designing test scenarios, setting performance SLOs, or diagnosing latency
  and throughput issues at the service level. Complements go-benchmark (micro-level
  function profiling) with macro-level end-to-end service testing. Use proactively
  for any pre-release performance validation, capacity planning, or production
  incident investigation involving latency/throughput.
allowed-tools: Read, Write, Grep, Glob, Bash(k6 version*), Bash(k6 inspect*), Bash(vegeta -version*), Bash(wrk -v*), Bash(cat *), Bash(jq *)
---

## Quick Reference

| When you need...                         | Jump to                                     |
|------------------------------------------|---------------------------------------------|
| Write a load test from scratch           | §2 Gates -> §5 Checklist -> §6 Scenarios    |
| Review existing test script              | §2 Gates -> §5.2 Script Quality             |
| Analyze test results                     | §2 Gates -> §5.3 Analysis -> load ref       |
| Choose between k6/vegeta/wrk             | §6.1 Tool Selection (Advise mode)           |
| Define SLOs for a service                | §5.1 SLO Definition                         |
| Debug why a test shows bad numbers       | §7 Anti-Examples -> load analysis ref        |
| Capacity planning                        | §6.2 Scenario Selection -> breakpoint/soak   |
| **Load generator OOM / high RSS**        | §7 AE-7 + k6-patterns §11 Memory Hygiene     |

---

## 1 Scope

**In scope**: HTTP service load testing (primary), SLO definition, scenario
design, script generation (k6 primary; vegeta for constant-rate), result
analysis, bottleneck identification, capacity planning recommendations.

**Partial coverage** — the same methodology applies, but this skill ships no
dedicated reference patterns yet: gRPC services, `wrk` / Lua scripting, and
distributed execution (k6 Operator, execution segments, k6 Cloud). State this
limitation explicitly if a task centers on one of these.

**Out of scope**: unit/micro-benchmarks (use `go-benchmark`), database-only
benchmarks, browser/UI performance (Lighthouse), chaos engineering fault
injection, infrastructure provisioning (Terraform/Pulumi).

---

## 2 Mandatory Gates

Gates are serial hard blockers. Failure at any gate stops all subsequent work.

### Gate 1: Context Collection

What's required depends on mode (Gate 3): Write verdicts need the endpoint;
Analyze needs results + SLOs (endpoint is context, not a gate); Review
needs the script; Advise needs neither. STOP only when info is genuinely
unobtainable — otherwise degrade to §4 Planning.

| Item              | Example                                    | Required for          |
|-------------------|---------------------------------------------|------------------------|
| Service endpoint  | `https://api.example.com/v1/orders`        | Write verdict          |
| Protocol          | HTTP/1.1, HTTP/2, gRPC                     | Write verdict          |
| Current baseline  | p50=12ms, p99=85ms, 2000 RPS              | If known               |
| Deployment        | k8s 3 replicas, 2 CPU / 4Gi each          | If known               |
| Auth mechanism    | Bearer token, API key, mTLS                | If any                 |
| Data dependencies | DB, Redis, external API                    | If known               |

### Gate 2: SLO-First (for verdicts)

A PASS/FAIL verdict requires an SLO to test against — without one, "p99=180ms"
is a number, not a decision. Help the user define SLOs whenever the goal is
validation, regression, or capacity sign-off.

Exploratory work does NOT need a pre-set SLO — baseline measurement,
breakpoint/ceiling discovery (§6.2), tool calibration, and regression-data
collection all proceed normally; they just cannot carry a PASS/FAIL verdict
(§4 Partial mode marks this explicitly).

STOP only when the user wants a pass/fail decision and has no SLO — define
SLOs first. Minimum SLO set:

- **Latency**: p50 and p99 targets (e.g., p50 < 50ms, p99 < 200ms)
- **Throughput**: minimum sustained RPS (e.g., 5000 RPS)
- **Error rate**: maximum acceptable (e.g., < 0.1% 5xx)
- **Availability**: during test window (e.g., 99.9%)

SLOs drive everything: scenario selection, pass/fail criteria, analysis focus.

### Gate 3: Scope Classification

Classify the task into one of four modes:

| Mode       | Trigger                                         | Deliverable                          |
|------------|--------------------------------------------------|--------------------------------------|
| **Write**  | "write a load test", "create k6 script"          | Executable test script + run command |
| **Review** | "review this test", code provided                 | Findings on script + improvements    |
| **Analyze**| "analyze these results", output/metrics provided  | SLO verdict + bottleneck report      |
| **Advise** | "k6 or vegeta?", "how many VUs?", SLO-design help — no script/results to act on | Direct recommendation + rationale + trade-off; skips §9 (see §9 note) |

### Gate 4: Output Completeness

Write/Review/Analyze: verify all §9 sections are present before delivering
— STOP and fill gaps. Advise has no §9 contract to complete.

---

## 3 Depth Selection

### Lite
Single endpoint, quick validation. No reference files needed.
- Triggers: "smoke test", "quick check", single URL, < 3 endpoints
- Coverage: basic ramp-up, 1-minute steady state, pass/fail against SLO

### Standard (default)
Full scenario with proper methodology. Load `references/k6-patterns.md` or
tool-appropriate reference.
- Triggers: pre-release validation, "load test the API", capacity check
- Coverage: warmup, ramp-up, steady state (3-5 min), cool-down, full analysis
- Force Standard if: multiple endpoints, auth required, data dependencies

### Deep
Multi-scenario suite with profiling correlation. Load all references.
- Triggers: capacity planning, "find the ceiling", production incident, > 5 endpoints
- Coverage: smoke + load + stress + breakpoint escalating suite (§6.2); soak
  runs separately — flat sustained load doesn't compose with an escalating
  suite; resource correlation, bottleneck report
- Force Deep if: soak test requested, breakpoint analysis, multi-service chain

---

## 4 Degradation Modes

When prerequisites are incomplete, produce explicitly-marked partial output.

| Available Data                     | Mode     | Can Deliver                                      | Cannot Claim                    |
|------------------------------------|----------|--------------------------------------------------|---------------------------------|
| Service spec + SLOs               | Full     | Script + scenario + analysis plan                | Actual performance numbers      |
| Script only, no results           | Script   | Script review + improvement suggestions          | SLO pass/fail verdict           |
| Results only, no SLOs             | Partial  | Statistical summary + anomaly flags              | Pass/fail, capacity conclusions |
| Results + SLOs                    | Analysis | Full SLO verdict + bottleneck analysis           | Script improvements             |
| No service info, vague request    | Planning | Generic scenario template + SLO questionnaire    | Anything specific               |

Mark degraded outputs: `# DEGRADED: [reason] — [what's missing]`

Never fabricate performance numbers. Never claim SLO compliance without data.

---

## 5 Load Test Checklist

### 5.1 SLO Definition

1. **Latency targets are percentile-based** — p50 and p99 minimum; p95 recommended.
   Raw averages hide tail latency. A service with avg=20ms but p99=2s is broken.
2. **Throughput target matches production traffic** — use access logs or APM to
   derive realistic RPS. Add 2-3x headroom for growth.
3. **Error budget is explicit** — "< 0.1% 5xx" not "low error rate". Include
   timeout classification (is a 30s timeout a success or error?).
4. **SLOs have context** — peak vs off-peak, read vs write endpoints, geographic region.

### 5.2 Script Quality

5. **Warmup phase precedes measurement** — JVM warmup, connection pool fill,
   cache priming. Measurement starts AFTER warmup completes.
6. **Ramp-up is gradual** — sudden full-load hides connection establishment
   issues and triggers rate limiters. Linear ramp over 30s-2min.
7. **Steady state duration is sufficient** — minimum 1 minute for smoke, 3-5
   minutes for standard, 15+ minutes for soak. Short runs miss GC pauses,
   connection pool exhaustion, memory leaks.
8. **Virtual users model real behavior** — think time is model-conditional:
   closed models add it, arrival-rate models skip it (`k6-patterns.md §2`).
   Realistic payloads and proper connection reuse apply either way.
9. **Test data is representative** — not the same ID every request (cache hit
   bias). Use parameterized data feeds with realistic distribution.
10. **Authentication is handled correctly** — pre-generate tokens outside the
    measurement loop. Token refresh latency must not contaminate results.

### 5.3 Analysis Methodology

11. **Report percentiles, not averages** — p50, p95, p99, p99.9, max. An average
    is meaningless as a latency SLO or verdict (a bimodal 5ms/500ms service and a
    flat 250ms service share the same mean); averages still have their place in
    capacity math like Little's Law — just never as the latency verdict.
12. **Correlate metrics across layers** — latency + CPU + memory + DB connections
    + goroutines + GC pauses. Latency alone doesn't find the bottleneck.
13. **Identify saturation point** — the RPS where p99 exceeds SLO. This is the
    service's true capacity, not peak throughput.
14. **Error classification matters** — 429 (rate limit) vs 503 (overload) vs
    timeout vs connection refused tell different stories.

### 5.4 Execution Environment

15. **Load generator runs separately from target** — never on the same machine,
    same pod, or same network bottleneck. Dedicated load generator instance.
16. **Generator capacity verified** — the load generator itself can be the
    bottleneck. Monitor its CPU **and RSS**. k6: check `dropped_iterations`.
17. **Network is not the bottleneck** — same region/AZ as target for internal
    tests. Document network topology for external tests.
18. **Load-generator memory budget pre-computed** — for k6 sustained tests at
    >= 1k TPS, compute peak RSS via `maxVUs × 3 MB + Σ(Trend) × 80 B × rate ×
    duration + body + tag overhead` BEFORE running. If peak > 80% of generator
    RAM, tighten `maxVUs` (Little's Law in `k6-patterns.md §2`) or shorten
    duration. The 4 most common OOM causes (in order): oversized `maxVUs` when
    service saturates, `--out csv=` buffering, duplicated/diagnostic Trend
    metrics retaining all samples, dynamic-URL tag bucket explosion. All four
    are covered in `k6-patterns.md §11`.
19. **Environment matches production** — or document differences explicitly.
    A test on a single-replica staging env says nothing about 3-replica prod.

---

## 6 Scenario & Tool Selection

### 6.1 Tool Selection

| Tool      | Best For                                    | Language | Distributed |
|-----------|---------------------------------------------|----------|-------------|
| **k6**    | Scenario modeling, JS scripting, CI/CD       | JS/TS    | Cloud / Operator / segments |
| **vegeta** | Constant-rate attacks, Go pipelines         | Go CLI   | Manual      |
| **wrk**   | Raw throughput measurement, simple scripts   | Lua      | No          |

Default to k6 unless: (a) user explicitly requests another tool, (b) constant-rate
is the only requirement (vegeta), or (c) maximum raw throughput measurement (wrk).

This skill ships k6 and vegeta reference patterns. `wrk` is listed for
tool-selection completeness but has no dedicated pattern reference here — use it
only for simple raw-throughput probes. Distributed k6 (Operator / execution
segments / Cloud) is named but not yet backed by a reference pattern.

### 6.2 Scenario Selection

| Goal                        | Scenario        | Pattern                                             |
|-----------------------------|-----------------|-----------------------------------------------------|
| "Does it work under load?"  | **Smoke**       | 1-5 VUs, 1 min — sanity check                       |
| "Can it handle target RPS?" | **Load**        | Ramp to target VUs, 3-5 min steady state             |
| "Where does it break?"      | **Stress**      | Ramp beyond target, find degradation point           |
| "What's the ceiling?"       | **Breakpoint**  | Step-increase VUs until failure — find absolute limit |
| "Memory leaks? Pool drain?" | **Soak**        | Moderate load, 30-60+ minutes — detect drift         |
| "Can it handle a flash sale?"| **Spike**      | Sudden 10x burst, hold 1 min, drop — test recovery  |

Select scenario based on the testing goal, not just "run some load". Multiple
scenarios compose for Deep depth (smoke -> load -> stress -> breakpoint).

---

## 7 Anti-Examples

### AE-1: Testing without warmup

```
# WRONG: measurement starts immediately
export default function() {
  http.get('http://api/endpoint');
}
// First 30s includes JVM startup, connection pool creation, cache cold starts
// Result: p99 inflated by 5-10x, meaningless numbers

# RIGHT: explicit warmup stage excluded from results
export const options = {
  scenarios: {
    warmup: { executor: 'constant-vus', vus: 10, duration: '30s',
              gracefulStop: '0s', tags: { phase: 'warmup' } },
    test:   { executor: 'ramping-vus', startTime: '30s',
              stages: [{ duration: '1m', target: 100 }] },
  },
  thresholds: {
    'http_req_duration{phase:test}': ['p(99)<200'],  // warmup excluded
  },
};
```

### AE-2: No SLO — testing into the void

```
# WRONG: "let's see how fast it is"
k6 run --vus 100 --duration 30s test.js
// Output: avg=45ms, p99=312ms, 4500 RPS
// ...so? Is this good? Bad? No one knows. No decision can be made.

# RIGHT: SLO-driven test with thresholds
export const options = {
  thresholds: {
    http_req_duration: ['p(99)<200', 'p(50)<50'],   // latency SLO
    http_req_failed: ['rate<0.001'],                 // error rate SLO
    http_reqs: ['rate>5000'],                        // total-RPS SLO (counts failures too; pair with http_req_failed)
  },
};
// Output: p99=312ms FAIL (SLO: <200ms) — clear, actionable
```

### AE-3: Load generator on same machine as target

```
# WRONG: both on the same 4-core laptop
k6 run --vus 500 test.js  # targeting localhost:8080
// k6 and the server compete for CPU. Results reflect resource contention,
// not service performance. p99 is dominated by OS scheduling, not app code.

# RIGHT: separate machines, same network segment
k6 run --vus 500 test.js  # targeting server on dedicated host
// Or: k6 in one container/pod, service in another with resource limits
```

### AE-4: Same request every time (cache bias)

```
# WRONG: cache hit rate = 100%
export default function() {
  http.get('http://api/users/1');  // same ID every request
}
// Redis/CDN/app cache serves everything. Actual DB path never tested.
// Production: unique user IDs → cache miss rate = 40-60%

# RIGHT: parameterized with realistic distribution
const users = new SharedArray('users', () => JSON.parse(open('./users.json')));
export default function() {
  const user = users[Math.floor(Math.random() * users.length)];
  http.get(`http://api/users/${user.id}`);
}
```

### AE-5: 30-second test declared "comprehensive"

```
# WRONG: "load test passed" after 30s
k6 run --vus 50 --duration 30s test.js
// Misses: GC major collections (every 2-3 min), connection pool exhaustion
// (builds up over minutes), memory leaks (invisible under 5 min),
// DB connection limit (pool fills gradually). This is a smoke test at best.

# RIGHT: duration matches what you're testing
// Smoke: 1 min (sanity only)    Soak: 30-60 min (leak detection)
// Load:  3-5 min steady state   Stress: until degradation observed
```

### AE-6: Reporting averages as performance verdict

```
# WRONG: "average latency is 45ms, we're good"
// Average hides: p99=2.1s (1% of users wait 2+ seconds)
// Average hides: bimodal distribution (cache hit=5ms, miss=500ms)

# RIGHT: percentile-based analysis
// p50=12ms p95=45ms p99=180ms p99.9=890ms max=2.1s
// Verdict: p99=180ms < 200ms SLO — PASS
// Warning: p99.9=890ms suggests tail latency problem worth investigating
```

### AE-7: Oversized maxVUs → load generator OOM

```
# WRONG: maxVUs set to "comfortable headroom" (2× rate)
scenarios: {
  writes: {
    executor:        'constant-arrival-rate',
    rate:            4000,
    preAllocatedVUs: 1600,
    maxVUs:          8000,   // ← "should be plenty"
  },
}
// When the SERVICE saturates (p95 climbs from 200ms to 1.5s), k6 keeps
// allocating new VUs trying to maintain 4k TPS. Each VU = ~3 MB resident.
// 8000 × 3 MB = 24 GB → load generator OOMs at ~6-8 min mark.
// Worse: this masquerades as "the load test crashed" when really the
// SERVICE under test couldn't sustain the target rate.

# RIGHT: size maxVUs via Little's Law against the SLO
//   needed VUs = rate × iteration_duration (ALL requests + sleep in one
//                iteration, not one request's time). 1 req, no sleep here:
//                4000 × 0.2s = 800; maxVUs = 2× needed = 1600 (§2 for sleep)
scenarios: {
  writes: {
    executor:        'constant-arrival-rate',
    rate:            4000,
    preAllocatedVUs: 800,
    maxVUs:          1600,   // ← caps memory at 1600 × 3 MB ≈ 5 GB
    gracefulStop:    '0s',
  },
}
// When the service saturates now, k6 reports dropped_iterations instead
// of OOM-ing. dropped_iterations IS the correct signal that the service
// can't sustain target rate — it's data, not a test failure.
```

See `references/k6-patterns.md §2` (Little's Law sizing) and `§11` (full
memory model: VU floor + sample storage + body retention + tag buckets).

### AE-8: `--out csv=`/`--out json=` for sustained high-TPS tests

```
# WRONG: k6 run --out csv=results.csv ... level1-4k-tps.js
# RIGHT: handleSummary() for a final verdict, or a remote real-time output
#        (Prometheus/OTel) when you actually need time-series — see below
```

`--out csv=`/`--out json=` stream every per-request row through a buffer
that backs up under slow disk I/O — up to ~500 MB-2 GB at 4k TPS/10 min.
That's the memory risk, but not the only question: an aggregated summary
has no timestamps and can't answer "did stage 2 differ from stage 1" — it's
a cheaper output for a final verdict, not a drop-in replacement for
time-series data. Full decision rule + memory model: `k6-patterns.md §10 +
§11.2`.

---

## 8 Load Test Scorecard

Three-tier scoring applied after every test run analysis.

### Critical (must all pass — any failure = redo test)

1. **SLO defined before test** — thresholds exist, not post-hoc
2. **Warmup period excluded** — measurement starts after warmup
3. **Steady state duration sufficient** — >= 1 min smoke, >= 3 min load/stress

### Standard (>= 4 of 5 must pass)

4. **Gradual ramp-up** — not instant full load
5. **Error rate monitored** — 4xx/5xx/timeout tracked separately
6. **Percentile latency reported** — p50/p95/p99 minimum, not just average
7. **Load generator not co-located** — separate from target
8. **Test data parameterized** — not single-value cache-hit bias

### Hygiene (>= 3 of 5 must pass)

9. **Environment documented** — infra specs, replica count, resource limits
10. **Baseline comparison** — delta from previous run or production metrics
11. **Resource metrics correlated** — CPU/mem/connections alongside latency
12. **Results archived** — raw data + summary stored for regression tracking
13. **Load-generator memory budgeted** — `preAllocatedVUs` sized from a
    *measured* `iteration_duration` (full iteration, not one request's
    response time) + variance margin; `maxVUs` is an optional cushion
    bounded by generator memory, not a mandatory multiplier. Also: opt-in
    diagnostic Trends, no `--out csv`/`--out json` for sustained runs,
    `discardResponseBodies` + `responseType:'text'` override in setup. See
    `k6-patterns.md §2 + §11`. Load generator OOMing invalidates the run.

**Verdict**: Critical 3/3 AND Standard >= 4/5 AND Hygiene >= 3/5 = **PASS**

---

## 9 Output Contract

Applies to **Write / Review / Analyze** modes. Every such response MUST
include these sections. Volume rules: FAIL items fully detailed; WARN items
up to 10; PASS items summary only. **Advise mode** (§2 Gate 3) skips this
contract — answer with a direct recommendation, its rationale, and the main
trade-off; no fabricated script, results, or verdict.

### 9.1 Context Summary
Target service, protocol, deployment, SLOs — table format.

### 9.2 Mode & Depth
`Write | Review | Analyze` + `Lite | Standard | Deep` with rationale.

### 9.3 SLO Definition
Latency (p50/p99), throughput (RPS), error rate, availability.
If user-provided SLOs are incomplete, state what was assumed.

### 9.4 Scenario Design
Selected scenario type, rationale, VU/RPS targets, duration, stages.

### 9.5 Test Script or Script Review
Write mode: complete executable script with run command.
Review mode: findings with severity and fix suggestions.
Analyze mode: omit or reference original script.

### 9.6 Results Analysis (Analyze mode)
Percentile table (p50/p95/p99/p99.9/max), throughput, error breakdown.
SLO pass/fail for each metric. Trend analysis if multiple runs.

### 9.7 Bottleneck Assessment
Identified bottlenecks ranked by impact. For each: evidence, affected SLO,
recommended fix, expected improvement. If no bottleneck found, state why.

### 9.8 Recommendations
Prioritized next steps: fix bottleneck, run longer soak, add monitoring,
adjust SLO, scale infrastructure. Each with effort estimate (quick/medium/large).

### 9.9 Uncovered Risks
What this test did NOT cover. Mandatory — never empty. Examples: "soak test
not run — memory leak risk unvalidated", "only read endpoints tested — write
path capacity unknown", "single-region test — cross-region latency not measured".

**Scorecard appended**: `X/13 — Critical Y/3, Standard Z/5, Hygiene W/5 — PASS/FAIL`
+ data basis (script only | results available | full profiling).

---

## 10 Reference Loading Guide

| Condition                                   | Load                              |
|---------------------------------------------|-----------------------------------|
| Writing k6 script (Standard+)              | `references/k6-patterns.md`       |
| Writing vegeta attack (Standard+)          | `references/vegeta-patterns.md`   |
| Analyzing results, finding bottlenecks     | `references/analysis-guide.md`    |
| **k6 sizing maxVUs / OOM / RSS budgeting** | **`references/k6-patterns.md §2 + §11`** |
| Deep depth or multi-scenario               | All three references              |

Each reference has a table of contents. Load the relevant sections, not
the entire file, when only a specific pattern is needed.
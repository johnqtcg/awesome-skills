# k6 Load Test Patterns

## Table of Contents
1. [Script Structure](#1-script-structure)
2. [Scenario Executors](#2-scenario-executors)  ← includes maxVUs sizing
3. [Thresholds & SLOs](#3-thresholds--slos)
4. [Data Parameterization](#4-data-parameterization)
5. [Authentication Patterns](#5-authentication-patterns)
6. [Lifecycle Hooks](#6-lifecycle-hooks)
7. [Custom Metrics](#7-custom-metrics)
8. [Checks & Assertions](#8-checks--assertions)
9. [Multi-Scenario Composition](#9-multi-scenario-composition)
10. [CI/CD Integration](#10-cicd-integration)
11. [Memory & Output Hygiene](#11-memory--output-hygiene)  ← load-generator OOM prevention

---

## 1 Script Structure

Canonical k6 script skeleton with warmup and measurement separation:

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';
import { SharedArray } from 'k6/data';
import { Rate } from 'k6/metrics';

// Custom metric — a Rate that captures pass/fail, not a Trend for latency:
// http_req_duration already exists as a built-in and tagging it by phase
// (below) is enough. Adding a custom Trend that just re-records
// res.timings.duration duplicates it for no benefit — see §11.3, §7.
const errorRate = new Rate('errors');

export const options = {
  scenarios: {
    warmup: {
      executor: 'constant-vus',
      vus: 10,
      duration: '30s',
      gracefulStop: '0s',
      tags: { phase: 'warmup' },
    },
    load_test: {
      executor: 'ramping-vus',
      startTime: '30s',  // starts after warmup
      stages: [
        { duration: '1m', target: 50 },    // ramp up
        { duration: '3m', target: 50 },    // steady state
        { duration: '30s', target: 0 },    // ramp down
      ],
      tags: { phase: 'test' },
    },
  },
  thresholds: {
    'http_req_duration{phase:test}': ['p(99)<200', 'p(50)<50'],
    'http_req_failed{phase:test}': ['rate<0.001'],
    'errors{phase:test}': ['rate<0.01'],
  },
};

export default function () {
  const res = http.get('http://api.example.com/endpoint');

  // A k6 Rate must receive a value on EVERY iteration (0 on success, 1 on
  // failure). `check(...) || errorRate.add(1)` is WRONG: it adds 1 only on
  // failure, so a Rate (= non-zero samples / total samples) reports 0% when
  // nothing fails and 100% the moment anything fails — never the true ratio.
  const ok = check(res, {
    'status is 200': (r) => r.status === 200,
    'body is not empty': (r) => r.body.length > 0,
  });
  errorRate.add(!ok);

  sleep(Math.random() * 3 + 1); // 1-4s think time
}
```

---

## 2 Scenario Executors

### constant-vus — Fixed concurrent users
```javascript
scenarios: {
  steady: {
    executor: 'constant-vus',
    vus: 100,
    duration: '5m',
  },
}
```
Use for: soak tests, steady-state validation.

### ramping-vus — Ramp up/down virtual users
```javascript
scenarios: {
  ramp: {
    executor: 'ramping-vus',
    startVUs: 0,
    stages: [
      { duration: '2m', target: 100 },   // ramp up
      { duration: '5m', target: 100 },   // hold
      { duration: '1m', target: 0 },     // ramp down
    ],
  },
}
```
Use for: standard load tests, stress tests.

### constant-arrival-rate — Fixed iteration-start rate regardless of response time
`rate` is **iterations per `timeUnit`, not requests per `timeUnit`**. If your
`default()` fires one request and returns immediately, iteration rate = HTTP
RPS. If it fires 3 requests, or calls `sleep()`, they are not the same number
— size VUs off the full iteration, not off "the RPS" (below).

```javascript
scenarios: {
  constant_rps: {
    executor:        'constant-arrival-rate',
    rate:            1000,   // 1000 iterations per timeUnit
    timeUnit:        '1s',   // = 1000 iterations/s (= 1000 RPS only if 1 req/iteration)
    duration:        '5m',
    preAllocatedVUs: 200,    // rate × iteration_duration = 1000 × 0.2s (1 req, no sleep — see below)
    maxVUs:          400,    // 2× preAlloc, a starting cushion — caps memory when service saturates
    gracefulStop:    '0s',   // drain window for in-flight iterations at scenario end (default 30s); '0s' cuts them off immediately. About drain time, not memory — use only when trailing iterations need not be measured.
  },
}
```
Use for: SLO validation at exact RPS target. Critical: if maxVUs is hit,
k6 drops iterations — check `dropped_iterations` metric.

**Sizing `maxVUs` via Little's Law** (this is the #1 source of load-generator
OOM crashes):

```
active VUs   = rate × iteration_duration
needed VUs   = rate × iteration_duration_at_healthy_target
safety VUs   = needed VUs × 2  ← maxVUs target
```

`iteration_duration` is the wall-clock time of ONE full run of `default()` —
every request it makes, any parsing/processing between them, and any
`sleep()`/think-time — not the response time of a single request. For the
common "one GET, no sleep" SLO-validation script the two collapse to the
same number, which is why the table below can use `healthy_p95` directly:

| Rate (TPS) | Healthy p95 (1 req/iter, no sleep) | preAllocatedVUs | maxVUs (2× cushion) |
|---|---|---|---|
| 1,000 | 200 ms | 200  | 400   |
| 2,000 | 200 ms | 400  | 800   |
| 4,000 | 200 ms | 800  | 1,600 |
| 5,000 | 200 ms | 1,000 | 2,000 |

**The moment a script adds `sleep()` or a second request, substitute the full
`iteration_duration`.** Example: 1,000 RPS, p95=200ms, plus `sleep(2)` think
time → `iteration_duration ≈ 2.2s` → needed VUs = 1,000 × 2.2 = 2,200, not
the 200 the naive "rate × response time" read of the table above would give
— an 11× underestimate that silently caps throughput via `dropped_iterations`
long before the service is actually saturated.

**The `2×` in the table is a starting cushion for an uncertain estimate, not
a mandatory multiplier.** Prefer sizing `preAllocatedVUs` generously up front
over relying on `maxVUs` dynamic top-up — allocating a VU beyond
`preAllocatedVUs` mid-run has its own latency cost and can distort the first
iteration on that VU. Grafana's guidance is to size `preAllocatedVUs` close
to the number you actually expect to need (ideally from a *measured*
iteration duration, not a guess) and treat any `maxVUs` gap as variance
insurance — see [arrival-rate VU allocation](https://grafana.com/docs/k6/latest/using-k6/scenarios/concepts/arrival-rate-vu-allocation/).
The more confidence you have in the `iteration_duration` measurement, the
closer `maxVUs` can shrink toward `preAllocatedVUs` (1×) — `2×` is not a
target, it's a hedge for the common case where you're sizing off a guess.

**Don't add `sleep()` think-time to an arrival-rate script.** SKILL.md §5.2
item 8: closed models (`constant-vus`/`ramping-vus`) need think time to make
concurrency reflect real user pacing — see §1's canonical skeleton. Open
models (`constant-arrival-rate`/`ramping-arrival-rate`) don't: `rate` already
*is* the arrival schedule, and every request already models one arriving
session. Adding `sleep()` on top doesn't add realism, it just inflates
`iteration_duration` and therefore the VUs needed to hit the same `rate` —
this is precisely the "1,000 RPS + sleep(2)" example above.

**Anti-pattern**: `maxVUs = 2 × rate` (e.g. 8,000 for 4k TPS). When the
service saturates and p95 climbs to 1.5 s, k6 keeps adding VUs trying to
maintain `rate`, hits the cap, and **each VU costs ~3 MB resident memory**
(goja JS runtime + per-VU HTTP client + cookie jar + tag state). At 8,000
VUs that is 24 GB — the load generator OOMs before the test finishes.
With the correct cap, k6 surfaces over-saturation as `dropped_iterations`
instead of OOM-ing.

**`dropped_iterations > 0` has two causes — disambiguate with the generator's
own CPU/RSS before blaming the service:**

- **Generator-bound**: the load generator's CPU is maxed (or it hit its own VU
  ceiling). The number reflects the *test rig*, not the service — not a service
  finding. (This is `analysis-guide.md §3` Tier-3 "generator is the bottleneck".)
- **Service-bound**: the generator is healthy but `maxVUs` was reached because
  per-iteration latency climbed, so k6 cannot start iterations on schedule. Only
  this case means the *service* cannot sustain the target rate.

Never read `dropped_iterations` alone as "the service is fine, the test broke" —
that conclusion requires confirming the generator was saturated.

Verified empirically (2026-05-14, tcg-acs-go-ob 4k TPS test): the VU
"floor" memory once k6 ramps to maxVUs is exactly `maxVUs × ~3 MB`.
Sample-storage memory (Trend metrics, see §11) is additive on top.

### ramping-arrival-rate — Ramp RPS for breakpoint testing
```javascript
scenarios: {
  breakpoint: {
    executor: 'ramping-arrival-rate',
    startRate: 100,
    timeUnit: '1s',
    preAllocatedVUs: 500,
    maxVUs: 2000,
    stages: [
      { duration: '2m', target: 500 },
      { duration: '2m', target: 1000 },
      { duration: '2m', target: 2000 },
      { duration: '2m', target: 5000 },
    ],
  },
}
```
Use for: finding the ceiling. Watch for p99 inflection point.

---

## 3 Thresholds & SLOs

Thresholds are k6's built-in SLO enforcement. Test fails if any threshold breaches.

```javascript
thresholds: {
  // Latency SLOs
  http_req_duration: ['p(50)<50', 'p(95)<150', 'p(99)<200'],

  // Error rate SLO
  http_req_failed: ['rate<0.001'],  // < 0.1% failure

  // Throughput SLO. NOTE: http_reqs counts ALL requests including failures, so
  // this is TOTAL RPS, not successful RPS. For a strict successful-throughput
  // SLO, tag successful responses and threshold that tag, and always pair with
  // http_req_failed to bound the failed share.
  http_reqs: ['rate>5000'],  // > 5000 total RPS

  // Per-endpoint SLOs using tags
  'http_req_duration{name:login}': ['p(99)<500'],
  'http_req_duration{name:list_orders}': ['p(99)<100'],

  // Phase-filtered (exclude warmup)
  'http_req_duration{phase:test}': ['p(99)<200'],
}
```

### Threshold aggregation methods
- `p(N)` — Nth percentile
- `avg` — average (never for a latency SLO/verdict; fine for capacity math)
- `min`, `max` — extremes
- `med` — median (alias for p(50))
- `rate` — ratio (for Rate metrics)
- `count` — total count

### Abort a run early on breach — `abortOnFail`

`abortOnFail` is a property of the **threshold object**, not an environment
variable. There is no `K6_THRESHOLD_ABORT_ON_FAIL`.

```javascript
thresholds: {
  http_req_failed: [
    { threshold: 'rate<0.01', abortOnFail: true, delayAbortEval: '10s' },
  ],
}
```

Either way, k6 already exits non-zero when any threshold fails, which fails a CI
step without any extra flag.

---

## 4 Data Parameterization

### SharedArray for CSV/JSON data
```javascript
import http from 'k6/http';
import { SharedArray } from 'k6/data';

const users = new SharedArray('users', function () {
  return JSON.parse(open('./testdata/users.json'));
});

export default function () {
  const user = users[__VU % users.length]; // deterministic per-VU
  // or: users[Math.floor(Math.random() * users.length)] for random
  http.get(`http://api/users/${user.id}`);
}
```

### Execution context variables
```javascript
export default function () {
  console.log(`VU: ${__VU}, Iteration: ${__ITER}`);
  // __VU: current virtual user ID (1-based)
  // __ITER: current iteration number for this VU (0-based)
}
```

### File upload
```javascript
import http from 'k6/http';
import { FormData } from 'https://jslib.k6.io/formdata/0.0.2/index.js';

const file = open('./testdata/sample.pdf', 'b'); // binary mode

export default function () {
  const fd = new FormData();
  fd.append('file', http.file(file, 'upload.pdf', 'application/pdf'));
  http.post('http://api/upload', fd.body(), {
    headers: { 'Content-Type': `multipart/form-data; boundary=${fd.boundary}` },
  });
}
```

---

## 5 Authentication Patterns

### Pre-generated token (recommended)
```javascript
import http from 'k6/http';

// Login ONCE in setup, reuse token across all VUs
export function setup() {
  const res = http.post('http://api/auth/login', JSON.stringify({
    username: 'loadtest', password: __ENV.LOAD_TEST_PASSWORD,
  }), { headers: { 'Content-Type': 'application/json' } });
  return { token: res.json('access_token') };
}

export default function (data) {
  http.get('http://api/protected', {
    headers: { Authorization: `Bearer ${data.token}` },
  });
}
```

### Per-VU token (large user sets that can't pre-authenticate in setup())

Only use this when the user set is too large for `setup()` to authenticate
in one pass (thousands of accounts, tight `setup()` timeout). Prefer the
`setup()` pattern above whenever the user set fits in one pass — it keeps
auth fully outside the measurement loop, matching the "authentication
outside the measurement loop" rule (SKILL.md §5.2 item 10). The lazy per-VU
pattern below runs the login request *inside* `default()` on each VU's first
iteration, which measures it unless you explicitly tag it out:

```javascript
const users = new SharedArray('users', () => JSON.parse(open('./users.json')));
const tokens = {};

export default function () {
  const user = users[__VU % users.length];
  if (!tokens[user.id]) {
    const res = http.post('http://api/auth/login', JSON.stringify(user), {
      tags: { name: 'login', phase: 'login' },  // separate bucket — see threshold below
    });
    tokens[user.id] = res.json('access_token');
    return;  // this iteration is login, not a measured request — don't fall through
  }
  http.get('http://api/orders', {
    headers: { Authorization: `Bearer ${tokens[user.id]}` },
    tags: { name: 'list_orders', phase: 'measure' },
  });
}
```

Threshold the measured phase only, the same way warmup is excluded in §1:
`'http_req_duration{phase:measure}': ['p(99)<200']`. Without the `phase`
tags and early `return`, the one-time login latency for every VU blends into
whatever metric you threshold, inflating tail latency for no reason.

---

## 6 Lifecycle Hooks

```javascript
// Runs once before test — use for global setup (auth, data prep)
export function setup() {
  const token = authenticate();
  return { token }; // passed to default and teardown
}

// Main test function — runs per-VU per-iteration
export default function (data) {
  http.get('http://api/endpoint', {
    headers: { Authorization: `Bearer ${data.token}` },
  });
}

// Runs once after test — cleanup resources
export function teardown(data) {
  http.post('http://api/cleanup', null, {
    headers: { Authorization: `Bearer ${data.token}` },
  });
}
```

### handleSummary() — the current recommendation over `--summary-export` (§10)

No remote dependency, writes `results.json` only — fully runnable as shown,
no jslib needed. When a script defines `handleSummary()`, `k6 run script.js`
alone is enough; no `--out`/`--summary-export` flag required:

```javascript
import http from 'k6/http';

export default function () {
  http.get('http://api.example.com/endpoint');
}

export function handleSummary(data) {
  return {
    stdout: JSON.stringify(data.metrics, null, 2),  // quick human glance
    'results.json': JSON.stringify(data),            // full aggregated summary
  };
}
```

A fuller human-readable report via `textSummary()`/`htmlReport()` needs
jslib — a remote dependency the version above avoids:

```javascript
import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.4/index.js';
import { htmlReport } from 'https://jslib.k6.io/k6-html-report/2.0.0/bundle.js';

export function handleSummary(data) {
  return {
    stdout: textSummary(data, { indent: ' ', enableColors: true }),
    'results/summary.json': JSON.stringify(data),
    'results/summary.html': htmlReport(data),
  };
}
```

---

## 7 Custom Metrics

```javascript
import http from 'k6/http';
import { Counter, Gauge, Rate, Trend } from 'k6/metrics';

const orderLatency = new Trend('order_latency', true);  // true = time values
const ordersCreated = new Counter('orders_created');
const queueDepth = new Gauge('order_queue_depth');  // Gauge keeps latest/min/max only
const orderErrors = new Rate('order_errors');
const payload = JSON.stringify({ item: 'widget', qty: 1 });

export default function () {
  const res = http.post('http://api/orders', payload);

  // Record custom metric values
  orderLatency.add(res.timings.duration);
  const created = res.status === 201;
  if (created) ordersCreated.add(1);  // Counter: increment once per success
  orderErrors.add(!created);          // Rate: add EVERY iteration (0 or 1), not only on failure
  const depth = res.json('queue_depth');
  if (depth !== undefined) queueDepth.add(depth);  // a genuinely fluctuating value, not a VU id
}

// Custom metrics can be thresholded too
export const options = {
  thresholds: {
    order_latency: ['p(99)<500'],
    order_errors: ['rate<0.01'],
  },
};
```

**Do not feed a custom `Gauge` with `__VU`.** `activeUsers.add(__VU)` looks
like it tracks concurrent users but is wrong twice over: `__VU` is the
calling virtual user's *ID number*, not a count of active users, and a
`Gauge` retains only the latest/min/max sample — so the reported value is
whichever VU happened to run last, not a concurrency measurement. k6 already
reports live VU counts via the built-in `vus` / `vus_max` metrics; use those
instead of inventing a custom one. A custom `Gauge` earns its place only for
a genuinely fluctuating value the built-ins don't expose, like `queueDepth`
above.

**Custom `Rate` metrics — record a value on every iteration.** A `Rate` reports
`non-zero samples / total samples`. A Rate metric that records only failures
(`check(...) || r.add(1)`, or `r.add(1)` solely inside an `else`) reports 0% when
nothing fails and 100% the moment anything fails — never the true ratio, so its
threshold is meaningless. Always feed it a boolean every iteration: `r.add(!ok)`.
(k6's built-in `http_req_failed` is already a correct Rate; a custom error Rate
is only worth adding when you need a non-HTTP-status success definition.)

---

## 8 Checks & Assertions

```javascript
import http from 'k6/http';
import { check } from 'k6';

export default function () {
  const res = http.get('http://api/users/1');

  // check() returns true if ALL checks pass, false otherwise
  const success = check(res, {
    'status is 200': (r) => r.status === 200,
    'response time < 200ms': (r) => r.timings.duration < 200,
    'body has id field': (r) => r.json('id') !== undefined,
    'content-type is json': (r) => r.headers['Content-Type'].includes('json'),
  });

  // Use check result for conditional logic
  if (!success) {
    console.warn(`Failed check for VU ${__VU} iter ${__ITER}`);
  }
}
```

---

## 9 Multi-Scenario Composition

Full test suite: smoke -> load -> stress -> breakpoint in one script:

```javascript
export const options = {
  scenarios: {
    smoke: {
      executor: 'constant-vus',
      vus: 5,
      duration: '1m',
      tags: { scenario: 'smoke' },
    },
    load: {
      executor: 'ramping-vus',
      startTime: '1m30s',
      stages: [
        { duration: '1m', target: 100 },
        { duration: '3m', target: 100 },
        { duration: '30s', target: 0 },
      ],
      tags: { scenario: 'load' },
    },
    stress: {
      executor: 'ramping-vus',
      startTime: '6m30s',
      stages: [
        { duration: '1m', target: 200 },
        { duration: '2m', target: 300 },
        { duration: '2m', target: 500 },
        { duration: '1m', target: 0 },
      ],
      tags: { scenario: 'stress' },
    },
    breakpoint: {
      executor:        'ramping-arrival-rate',
      startTime:        '12m30s',  // after smoke+load+stress finish
      startRate:         100,
      timeUnit:          '1s',
      preAllocatedVUs:   500,      // size per §2 — no sleep in this endpoint
      maxVUs:            2000,
      stages: [
        { duration: '2m', target: 500 },
        { duration: '2m', target: 1000 },
        { duration: '2m', target: 2000 },
      ],
      tags: { scenario: 'breakpoint' },
    },
  },
  thresholds: {
    'http_req_duration{scenario:smoke}': ['p(99)<100'],
    'http_req_duration{scenario:load}': ['p(99)<200'],
    'http_req_duration{scenario:stress}': ['p(99)<500'],
    // breakpoint has no threshold — its goal is finding the ceiling, not a
    // verdict (SKILL.md §2 Gate 2 exploratory case); read dropped_iterations.
  },
};
```

---

## 10 CI/CD Integration

### Output decision rule: verdict vs time-series vs local diagnostic

k6's docs draw a real distinction between **summary** output (one aggregated
snapshot, written once at the end) and **real-time** output (a continuous,
timestamped stream of every sample) — see [k6 results output](https://grafana.com/docs/k6/latest/results-output/).
They answer different questions; picking the wrong one either wastes memory
or throws away data the analysis actually needed. An aggregated summary has
no timestamps — it cannot answer "did p99 drift between minute 3 and minute
8", so it is NOT a value-free substitute for time-series, only a cheaper
output when a final number is genuinely all you need.

| Need | Use | Why |
|---|---|---|
| Final SLO/CI pass-fail, nothing else | `handleSummary()` (§6) | ~0 memory; the current recommendation — [k6 options reference](https://grafana.com/docs/k6/latest/using-k6/k6-options/reference/) marks the `--summary-export` flag soft-deprecated in its favor |
| Stage/phase comparison, resource correlation, trend over the run | Remote real-time output (`--out experimental-prometheus-rw`, OpenTelemetry) | Timestamped interval/time-series data survives at the output's aggregation resolution — this is the only row that can answer "when did it get worse" (note: [Prometheus Remote Write](https://grafana.com/docs/k6/latest/results-output/real-time/prometheus-remote-write/) buckets Trend samples before push, so it's not raw per-sample fidelity) |
| Short local run, ad-hoc diagnosis (small `duration`/`vus`) | `--out csv=`/`--out json=` | Fine here — total row count stays small; §11.2's memory risk is specifically about *sustained high-TPS* runs, not short ones |

`--summary-export` still works and remains fine on existing scripts; prefer
`handleSummary()` in new ones — same end-of-run aggregation, more control
over what gets written and where.

### GitHub Actions
```yaml
- name: Run load test
  # k6 exits non-zero automatically when any threshold fails, which fails this
  # CI step. To abort the run *early* on breach, set abortOnFail on the threshold
  # object in the script (see §3) — there is NO K6_THRESHOLD_ABORT_ON_FAIL env var.
  # scripts/load-test.js defines handleSummary() (§6) and writes results.json
  # itself — no --out/--summary-export flag needed on the command line.
  run: |
    k6 run --tag testid=${{ github.sha }} scripts/load-test.js

- name: Archive results
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: load-test-results
    path: results.json
```

### Run commands
```bash
# Current recommendation: define handleSummary() in the script (§6) and just
# run it plain — no flag needed, near-zero memory, no remote dependency:
k6 run test.js

# --summary-export still works if the script has no handleSummary():
k6 run --summary-export=results.json test.js

# With environment variables
k6 run -e BASE_URL=https://staging.api.com -e API_KEY=xxx test.js

# Diagnostic timing breakdown (opt-in via env var, +1 GB memory at 4k TPS)
PROFILE_TIMINGS=1 k6 run test.js

# With custom VU/duration override (smoke testing)
k6 run --vus 10 --duration 1m test.js

# For sustained high-TPS tests where you need time-series (not a summary),
# push to Prometheus instead of --out csv/json — see the decision table above:
k6 run --out experimental-prometheus-rw test.js
```

---

## 11 Memory & Output Hygiene

The load generator can OOM before the test completes if these knobs are
wrong. The failure mode is sneaky: VU memory ramps to a steady "floor"
within 2 minutes of the writes phase starting, then Trend samples grow
linearly until the run ends. People observe "memory at 2 min is fine" and
miss the trajectory. Six knobs to set explicitly.

### 11.1 The memory model

> **Calibration note — two different kinds of claim below.**
>
> *Structural relationships*, checked against k6's Go source: VU floor scales
> with `maxVUs` (each VU carries a goja runtime + HTTP client + cookie jar);
> `Trend` metrics store every sample in a slice for percentile math
> (`TrendSink`), so sample storage scales with sample count. Both hold across
> k6 versions. CSV/JSON output is different in kind — it uses a `SampleBuffer`
> drained by a `PeriodicFlusher` (see `go.k6.io/k6/output/csv`), so its
> *typical* footprint is bounded by the flush interval, not by test duration;
> it only grows toward `rate × duration` in the disk-bound worst case, when
> write throughput can't keep up with the flush cadence (§11.2 has the detail).
>
> *Constants* (~3 MB/VU, ~80 B/sample) are a single empirical measurement — k6
> v0.4x, x86-64 Linux, ~1 KB JSON bodies (the 2026-05-14 tcg-acs 4k-TPS run).
> Actual RSS shifts with k6 version, script complexity, tag cardinality, and
> output plugin. Use them as a pre-flight estimate, then measure real RSS on
> your own setup (`ps -o rss` or `/usr/bin/time -v` sampled during the run)
> before trusting a number for capacity planning.

```
total RSS ≈ VU floor + sample storage + response bodies + tag buckets
            ────────  ──────────────  ─────────────────  ────────────
            stable    grows linearly   per-iteration     ~constant
            within    with duration    cost              after warm
            ~2 min
```

- **VU floor** = `maxVUs × ~3 MB`. Stable once k6 finishes ramping. **Cannot be
  optimized in script** other than reducing maxVUs (see §2).
- **Sample storage** = `Σ(per-Trend-metric: 80 B × sample count)`. Grows linearly.
  Removing unnecessary Trends is the lever (§11.3).
- **Response bodies** = ~payload size × active VUs × pipeline depth. Set
  `discardResponseBodies: true` to zero this out (§11.4).
- **Tag buckets** = `tag cardinality × metric count × 80 B / bucket`. Dynamic
  URL paths explode this. Use `tags.name` (§11.5).

### 11.2 Output: avoid `--out csv`/`--out json` for sustained high-TPS tests

`--out csv=` and `--out json=` stream every per-request row through a
`SampleBuffer` that a `PeriodicFlusher` drains to disk on a timer. When disk
I/O keeps pace with that flush cadence, the resident buffer stays small
regardless of how long the test runs. When it doesn't — slow disks,
network-attached/cloud volumes, or simply a flush interval shorter than the
write latency — unflushed rows back up for the rest of the run; at 4k TPS
over 10 minutes that backlog can reach 500 MB–2 GB. Because you rarely have
a hard guarantee on the load-generator host's disk throughput, treat
sustained high-TPS tests as the disk-bound case by default and pick from
§10's decision table instead — none of those alternatives carry this risk.

| Output flag | Memory cost | Use case |
|---|---|---|
| `--out csv=results.csv` | ~0 if disk keeps up; **500 MB–2 GB** disk-bound worst case at 4k TPS / 10 min | Sustained tests: avoid — short local diagnostics: fine (§10) |
| `--out json=results.json` | Same | Same as above |
| `--summary-export=results.json` / `handleSummary()` | **~0** (aggregated, written once at end) | Final verdict only — see §10 for the summary-vs-time-series trade-off |
| `--out experimental-prometheus-rw` | ~0 (pushed remotely) | Time-series / phase comparison / long-running tests |

### 11.3 Trend metrics retain ALL samples

`new Trend('name', true)` keeps every sample in memory until summary (k6
needs them for accurate percentile calculation). Cost: ~80 B × sample count.

| Problem | Fix |
|---|---|
| Custom Trend duplicates a built-in (e.g. `writeTxLatency` vs `http_req_duration{phase:write}`) | **Delete the custom one**; tag the built-in by scenario |
| HTTP timing breakdown (`req_blocked_ms`, `req_connecting_ms`, etc.) on every iteration | **Opt-in via env var**, see below |

Opt-in pattern for diagnostic-only metrics:

```javascript
const ENABLE_TIMING_BREAKDOWN = __ENV.PROFILE_TIMINGS === '1';
const reqBlocked    = ENABLE_TIMING_BREAKDOWN ? new Trend('req_blocked_ms',    true) : null;
const reqConnecting = ENABLE_TIMING_BREAKDOWN ? new Trend('req_connecting_ms', true) : null;
const reqWaiting    = ENABLE_TIMING_BREAKDOWN ? new Trend('req_waiting_ms',    true) : null;
// ... etc

export default function () {
  const res = http.get(url, params);
  if (ENABLE_TIMING_BREAKDOWN) {
    reqBlocked.add(res.timings.blocked);
    reqConnecting.add(res.timings.connecting);
    reqWaiting.add(res.timings.waiting);
  }
}
```

5 timing-breakdown Trends at 4k TPS × 10 min = **~1 GB** otherwise.

### 11.4 `discardResponseBodies` saves bodies — but is global

```javascript
export const options = {
  discardResponseBodies: true,  // saves 200-500 MB at 4k TPS
};
```

**Trap**: this is a global setting that affects setup() too. If your setup
needs `r.json()` to parse account IDs or auth tokens, that code silently
breaks (response body is empty). Override per-request:

```javascript
export function setup() {
  // setup needs bodies — override the global discard
  const GET_PARAMS = { responseType: 'text' };

  const resp = http.get(`${BASE_URL}/accounts/${cid}`, GET_PARAMS);
  const accounts = resp.json();  // works because responseType:'text' was set
  // ...
}

export default function () {
  // scenario uses the global discard — bodies are dropped, status still checked
  const res = http.post(url, payload, { headers: {...} });
  check(res, { 'ok': r => r.status === 200 });
}
```

### 11.5 Dynamic URL paths explode tag buckets

k6 tags every sample with `url` by default. With dynamic paths like
`/accounts/customer/{id}` and 2,000 unique customer IDs, that creates 2,000
distinct tag combinations × 9 HTTP metrics = **18,000 Trend buckets**, each
with its own samples array overhead.

**Fix**: remove `url` from `systemTags`, add explicit `tags.name` per endpoint
so all variants collapse into one bucket:

```javascript
export const options = {
  // Remove url, group, tls_version, proto, ip — they multiply storage.
  // Keep 'name' so explicit tags.name on each http call groups variants.
  systemTags: ['method', 'status', 'scenario', 'expected_response', 'name'],
};

export default function () {
  // 2,000 distinct customerIds collapse to one metric bucket named
  // 'GET /accounts/customer/:cid' instead of 2,000 url-tagged buckets.
  http.get(`${BASE_URL}/accounts/customer/${cid}`,
    { tags: { name: 'GET /accounts/customer/:cid' } });

  http.post(`${BASE_URL}/transactions/credit`,
    JSON.stringify(payload),
    { headers: {...}, tags: { name: 'POST /transactions/credit' } });
}
```

Saves 200-500 MB at 4k TPS / 2k unique URL paths.

### 11.6 `summaryTrendStats` does NOT save sample storage

```javascript
summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(95)', 'p(99)']
```

This only controls which stats are **reported** in the summary. The Trend
metric stores all samples regardless. Removing `p(99)` doesn't save memory
during the run; it only skips a sort at summary time. Don't expect savings
from this knob.

### 11.7 Pre-flight memory budget calculation

Before running a long sustained test, compute the expected peak:

```
VU floor       = maxVUs × 3 MB
sample storage = (number of Trends) × (rate × duration_sec) × 80 B
response bodies = (active VUs × avg body bytes) if NOT discarding
tag bucket overhead = (unique URLs × HTTP metric count) × ~5 KB if 'url' in systemTags

peak RSS ≈ sum of above × 1.3  (Go runtime + GC slack)
```

Example, 4k TPS × 10 min, default settings:
- VU floor: 8,000 × 3 MB = **24 GB** ← OOM here
- Samples: 8 metrics (k6's built-in HTTP timing Trends + `iteration_duration`
  — always emitted, see §11.1; this example adds no custom Trends on top) ×
  4,000 × 600 × 80 B = 1.5 GB
- Bodies: 8,000 × 500 B = 4 MB (transient)
- Tag overhead: 2,000 URLs × 9 × 5 KB = 90 MB
- **Total ≈ 33 GB** → guaranteed OOM on a 16 GB load generator

After applying §2 + §11.2 + §11.4 + §11.5 (maxVUs sized at 2× needed VUs
per §2's table, i.e. 1,600 for 4k TPS, not 2× rate — §11.3 has no effect
here, since the built-in Trends above are irreducible and this example
never added custom duplicates to delete):
- VU floor: 1,600 × 3 MB = **4.8 GB**
- Samples: 8 metrics × 4,000 × 600 × 80 B = 1.5 GB (unchanged — none of
  these levers touch the always-on built-in Trends)
- Bodies: 0 (discarded)
- Tag overhead: 6 endpoints × 4 × 5 KB = 120 KB
- **Total ≈ 8.2 GB** → fits in 16 GB headroom (51%, under the 80% budget
  threshold — §5.4 item 18)

Always do this calculation before kicking off a > 5 min sustained test.
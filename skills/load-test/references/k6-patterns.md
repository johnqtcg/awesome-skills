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
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const reqDuration = new Trend('req_duration');

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

  check(res, {
    'status is 200': (r) => r.status === 200,
    'body is not empty': (r) => r.body.length > 0,
  }) || errorRate.add(1);

  reqDuration.add(res.timings.duration);

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

### constant-arrival-rate — Fixed RPS regardless of response time
```javascript
scenarios: {
  constant_rps: {
    executor:        'constant-arrival-rate',
    rate:            1000,   // 1000 iterations per timeUnit
    timeUnit:        '1s',   // = 1000 RPS
    duration:        '5m',
    preAllocatedVUs: 200,    // active VU ≈ rate × healthy_p95 = 1000 × 0.2s
    maxVUs:          500,    // 2× preAlloc — caps memory when service saturates
    gracefulStop:    '0s',   // do NOT drain — wastes VU memory at end of run
  },
}
```
Use for: SLO validation at exact RPS target. Critical: if maxVUs is hit,
k6 drops iterations — check `dropped_iterations` metric.

**Sizing `maxVUs` via Little's Law** (this is the #1 source of load-generator
OOM crashes):

```
active VUs   = rate × actual_response_time
needed VUs   = rate × healthy_p95_target
safety VUs   = needed VUs × 2  ← maxVUs target
```

| Rate (TPS) | Healthy p95 | preAllocatedVUs | maxVUs |
|---|---|---|---|
| 1,000 | 200 ms | 200  | 500   |
| 2,000 | 200 ms | 400  | 1,000 |
| 4,000 | 200 ms | 800  | 2,000 |
| 5,000 | 200 ms | 1,000 | 2,500 |

**Anti-pattern**: `maxVUs = 2 × rate` (e.g. 8,000 for 4k TPS). When the
service saturates and p95 climbs to 1.5 s, k6 keeps adding VUs trying to
maintain `rate`, hits the cap, and **each VU costs ~3 MB resident memory**
(goja JS runtime + per-VU HTTP client + cookie jar + tag state). At 8,000
VUs that is 24 GB — the load generator OOMs before the test finishes.
With the correct cap, k6 surfaces over-saturation as `dropped_iterations`
instead, which is the correct signal that the service can't sustain the
target rate.

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

  // Throughput SLO (via custom counter)
  http_reqs: ['rate>5000'],  // > 5000 RPS

  // Per-endpoint SLOs using tags
  'http_req_duration{name:login}': ['p(99)<500'],
  'http_req_duration{name:list_orders}': ['p(99)<100'],

  // Phase-filtered (exclude warmup)
  'http_req_duration{phase:test}': ['p(99)<200'],
}
```

### Threshold aggregation methods
- `p(N)` — Nth percentile
- `avg` — average (avoid for latency)
- `min`, `max` — extremes
- `med` — median (alias for p(50))
- `rate` — ratio (for Rate metrics)
- `count` — total count

---

## 4 Data Parameterization

### SharedArray for CSV/JSON data
```javascript
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

### Per-VU token (when token is user-specific)
```javascript
const users = new SharedArray('users', () => JSON.parse(open('./users.json')));
const tokens = {};

export default function () {
  const user = users[__VU % users.length];
  if (!tokens[user.id]) {
    const res = http.post('http://api/auth/login', JSON.stringify(user));
    tokens[user.id] = res.json('access_token');
  }
  http.get('http://api/orders', {
    headers: { Authorization: `Bearer ${tokens[user.id]}` },
    tags: { name: 'list_orders' },
  });
}
```

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

// Handle summary output
export function handleSummary(data) {
  return {
    'stdout': textSummary(data, { indent: ' ', enableColors: true }),
    'results/summary.json': JSON.stringify(data),
    'results/summary.html': htmlReport(data),
  };
}
```

---

## 7 Custom Metrics

```javascript
import { Counter, Gauge, Rate, Trend } from 'k6/metrics';

const orderLatency = new Trend('order_latency', true);  // true = time values
const ordersCreated = new Counter('orders_created');
const activeUsers = new Gauge('active_users');
const orderErrors = new Rate('order_errors');

export default function () {
  const res = http.post('http://api/orders', payload);

  // Record custom metric values
  orderLatency.add(res.timings.duration);
  if (res.status === 201) {
    ordersCreated.add(1);
  } else {
    orderErrors.add(1);
  }
  activeUsers.add(__VU);
}

// Custom metrics can be thresholded too
export const options = {
  thresholds: {
    order_latency: ['p(99)<500'],
    order_errors: ['rate<0.01'],
  },
};
```

---

## 8 Checks & Assertions

```javascript
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
  },
  thresholds: {
    'http_req_duration{scenario:smoke}': ['p(99)<100'],
    'http_req_duration{scenario:load}': ['p(99)<200'],
    'http_req_duration{scenario:stress}': ['p(99)<500'],
  },
};
```

---

## 10 CI/CD Integration

### GitHub Actions
```yaml
- name: Run load test
  run: |
    k6 run --out json=results.json \
      --tag testid=${{ github.sha }} \
      scripts/load-test.js
  env:
    K6_THRESHOLD_ABORT_ON_FAIL: "true"

- name: Archive results
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: load-test-results
    path: results.json
```

### Run commands
```bash
# Standard run with aggregated summary (recommended — KB output, near-zero memory)
k6 run --summary-export=results.json test.js

# With environment variables
k6 run -e BASE_URL=https://staging.api.com -e API_KEY=xxx test.js

# Diagnostic timing breakdown (opt-in via env var, +1 GB memory at 4k TPS)
PROFILE_TIMINGS=1 k6 run test.js

# With custom VU/duration override (smoke testing)
k6 run --vus 10 --duration 1m test.js

# DO NOT use for high-TPS sustained tests: --out csv buffers every per-request
# row in memory. At 4k TPS × 10 min that is 2.4M rows ≈ 500 MB-2 GB resident.
# Use --summary-export above for aggregated output, or push to Prometheus:
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

### 11.2 Output: never `--out csv` for sustained tests

`--out csv=` and `--out json=` write **every per-request row** in real time. k6
buffers writes; on slow disks the buffer reaches several GB.

| Output flag | Memory cost | Use case |
|---|---|---|
| `--out csv=results.csv` | **500 MB–2 GB** at 4k TPS / 10 min | Never — replace |
| `--out json=results.json` | Same | Never — replace |
| **`--summary-export=results.json`** | **~0** (aggregated, written once at end) | **Default** |
| `--out experimental-prometheus-rw` | ~0 (pushed remotely) | Long-running tests |

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
- Samples: 9 metrics × 4,000 × 600 × 80 B = 1.7 GB
- Bodies: 8,000 × 500 B = 4 MB (transient)
- Tag overhead: 2,000 URLs × 9 × 5 KB = 90 MB
- **Total ≈ 33 GB** → guaranteed OOM on a 16 GB load generator

After applying §2 + §11.2 + §11.3 + §11.4 + §11.5:
- VU floor: 2,000 × 3 MB = **6 GB**
- Samples: 4 metrics × 4,000 × 600 × 80 B = 0.8 GB
- Bodies: 0 (discarded)
- Tag overhead: 6 endpoints × 4 × 5 KB = 120 KB
- **Total ≈ 9 GB** → fits in 16 GB headroom

Always do this calculation before kicking off a > 5 min sustained test.
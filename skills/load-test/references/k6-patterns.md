# k6 Load Test Patterns

## Table of Contents
1. [Script Structure](#1-script-structure)
2. [Scenario Executors](#2-scenario-executors)
3. [Thresholds & SLOs](#3-thresholds--slos)
4. [Data Parameterization](#4-data-parameterization)
5. [Authentication Patterns](#5-authentication-patterns)
6. [Lifecycle Hooks](#6-lifecycle-hooks)
7. [Custom Metrics](#7-custom-metrics)
8. [Checks & Assertions](#8-checks--assertions)
9. [Multi-Scenario Composition](#9-multi-scenario-composition)
10. [CI/CD Integration](#10-cicd-integration)

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
    executor: 'constant-arrival-rate',
    rate: 1000,            // 1000 iterations per timeUnit
    timeUnit: '1s',        // = 1000 RPS
    duration: '5m',
    preAllocatedVUs: 200,  // pre-allocate to avoid cold-start
    maxVUs: 500,           // upper bound
  },
}
```
Use for: SLO validation at exact RPS target. Critical: if maxVUs is hit,
k6 drops iterations — check `dropped_iterations` metric.

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
# Standard run with JSON output
k6 run --out json=results.json test.js

# With environment variables
k6 run -e BASE_URL=https://staging.api.com -e API_KEY=xxx test.js

# With custom VU/duration override (testing)
k6 run --vus 10 --duration 1m test.js

# Cloud execution (k6 Cloud)
k6 cloud test.js
```
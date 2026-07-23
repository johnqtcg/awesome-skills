// Write-mode output from the load-test skill.
// Target: checkout-service, POST /v1/checkout (sample subject — see index.md)
// SLOs: p50<50ms, p99<200ms, error rate<0.1%, throughput>=2000 RPS
import http from 'k6/http';
import { check } from 'k6';
import { SharedArray } from 'k6/data';
import { Rate } from 'k6/metrics';

const errorRate = new Rate('errors');

const carts = new SharedArray('carts', function () {
  return JSON.parse(open('./testdata/carts.json'));
});

export const options = {
  scenarios: {
    warmup: {
      executor: 'constant-vus',
      vus: 20,
      duration: '30s',
      gracefulStop: '0s',
      tags: { phase: 'warmup' },
    },
    // Ramps the arrival rate up before the measured window — same reason
    // warmup is excluded above: a sudden jump straight to 2000/s would
    // violate the gradual ramp-up rule (§5.2 item 6). Tagged separately from
    // `test` so the throughput SLO below is measured only once the target
    // rate is actually held, not blended with the ramp's lower average.
    ramp: {
      executor: 'ramping-arrival-rate',
      startTime: '30s', // starts after warmup
      startRate: 200,
      timeUnit: '1s',
      preAllocatedVUs: 400, // target rate × healthy p95 est. (200ms), 1 req/iter — k6-patterns.md §2 table
      maxVUs: 800,
      gracefulStop: '0s',
      stages: [{ duration: '30s', target: 2000 }],
      tags: { phase: 'ramp' },
    },
    load_test: {
      // constant-arrival-rate, not ramping-vus: the SLO is an exact RPS
      // target (>=2000). ramping-vus is a closed model — throughput = VUs /
      // iteration_duration, an OUTPUT that moves with response time, not a
      // value you set. It could land above or below 2000 depending on how
      // fast the backend responds; arrival-rate is what actually guarantees
      // the target rate. See k6-patterns.md §2.
      executor: 'constant-arrival-rate',
      startTime: '1m', // after 30s warmup + 30s ramp
      rate: 2000,
      timeUnit: '1s',
      duration: '3m',
      preAllocatedVUs: 400, // rate × healthy p95 est. (200ms), 1 req/iter, no sleep — k6-patterns.md §2 table
      maxVUs: 800,          // 2x cushion
      gracefulStop: '0s',
      tags: { phase: 'test' },
    },
    // Ramp back down instead of a hard stop — completes the
    // warmup/ramp-up/steady-state/cool-down cycle SKILL.md §3 (Standard
    // depth) expects. Excluded from every threshold below, same as ramp.
    cooldown: {
      executor: 'ramping-arrival-rate',
      startTime: '4m', // after warmup(30s) + ramp(30s) + test(3m)
      startRate: 2000,
      timeUnit: '1s',
      preAllocatedVUs: 400,
      maxVUs: 800,
      // Without this, k6 defaults to a 30s graceful-stop grace period,
      // pushing totalDuration to 5m even though nothing here needs the
      // extra time — cooldown is excluded from every threshold, so no
      // trailing iteration needs to be allowed to finish measuring.
      gracefulStop: '0s',
      stages: [{ duration: '30s', target: 0 }],
      tags: { phase: 'cooldown' },
    },
  },
  thresholds: {
    'http_req_duration{phase:test}': ['p(99)<200', 'p(50)<50'],
    'http_req_failed{phase:test}': ['rate<0.001'],
    'errors{phase:test}': ['rate<0.001'],
    // Sanity floor, not the capacity signal — k6's own rate measurement can
    // clip a hair under the exact target at a window's start/end (verified:
    // an otherwise-clean run failed a rate>=2000 pin on this exact script).
    // dropped_iterations below is the precise, authoritative check.
    'http_reqs{phase:test}': ['rate>=1990'],
    'dropped_iterations{scenario:ramp}': ['count==0'],
    'dropped_iterations{scenario:load_test}': ['count==0'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'https://checkout.example.com';

export default function () {
  const cart = carts[Math.floor(Math.random() * carts.length)]; // parameterized — avoids cache-hit bias

  const res = http.post(`${BASE_URL}/v1/checkout`, JSON.stringify(cart), {
    headers: { 'Content-Type': 'application/json' },
    tags: { name: 'POST /v1/checkout' },
  });

  const ok = check(res, {
    'status is 201': (r) => r.status === 201,
    'body has order id': (r) => r.json('orderId') !== undefined,
  });
  errorRate.add(!ok); // fed every iteration — never only on failure
}

// No remote dependency — writes results.json, no --out/--summary-export flag needed.
export function handleSummary(data) {
  return {
    stdout: JSON.stringify(data.metrics, null, 2),
    'results.json': JSON.stringify(data),
  };
}
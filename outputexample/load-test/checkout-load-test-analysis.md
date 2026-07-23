# Load Test Analysis — checkout-service `POST /v1/checkout`

Analyze-mode output from the load-test skill, following its §9 Output
Contract. Sample subject (see `index.md`) — results below are illustrative
data constructed for this example, not a real production run.

## 9.1 Context Summary

| Item | Value |
|---|---|
| Service | checkout-service, `POST /v1/checkout` |
| Protocol | HTTP/1.1 |
| Deployment | k8s, 3 replicas, 2 CPU / 4Gi each |
| Load generator | Separate host, same AZ — not co-located with checkout-service |
| Data dependency | Postgres connection pool (size 50) |
| SLOs | p50<50ms, p99<200ms, error rate<0.1%, throughput>=2000 RPS |

## 9.2 Mode & Depth

`Analyze` + `Standard` — a 4.5-minute run (30s warmup + 30s ramp-up + 3m
steady state + 30s cool-down) against a stated SLO set; not a multi-scenario
capacity investigation (would be `Deep`).

## 9.3 SLO Definition

Latency p50<50ms / p99<200ms, throughput >=2000 RPS, error rate <0.1%,
measured during the `phase:test` window (warmup excluded). All provided by
the user — nothing assumed.

## 9.4 Scenario Design

30s `constant-vus` warmup (excluded) → 30s `ramping-arrival-rate` 200→2,000/s
ramp-up (excluded — gradual ramp, not the measured window) → 3m
`constant-arrival-rate` at 2,000/s, the measured window (400 preAllocatedVUs
/ 800 maxVUs, sized off a 200ms healthy-p95 target estimate — see Hygiene
note below) → 30s `ramping-arrival-rate` 2,000→0/s cool-down (excluded).
Arrival-rate throughout rather than `ramping-vus`, since the SLO is an
exact-RPS target, not a concurrency target — see `checkout-load-test.js` §2
comment for why a closed model can't guarantee that. No think-time `sleep()`
per SKILL.md §5.2 item 8: arrival-rate models don't need it. Matches
`checkout-load-test.js` in this directory.

## 9.5 Test Script or Script Review

Not applicable in Analyze mode — see `checkout-load-test.js` for the script
that produced these results.

## 9.6 Results Analysis

| Percentile | Value | SLO | Verdict |
|---|---|---|---|
| p50 | 38ms | <50ms | PASS |
| p95 | 145ms | — | — |
| p99 | 210ms | <200ms | **FAIL** |
| p99.9 | 610ms | — | — |
| max | 1.9s | — | — |

Throughput: 2,000 RPS sustained for the full 3m steady state (>=2000 RPS
SLO — PASS; script thresholds `rate>=1990` as a sanity floor only).
`dropped_iterations{scenario:ramp}` and `dropped_iterations{scenario:load_test}`
both 0 — the authoritative signal that 400 preAllocatedVUs never fell short
of demand. The rate itself isn't pinned to exactly 2000: k6's own windowed
measurement can clip a hair under the target at a scenario boundary even
when nothing is actually short of capacity — dropped_iterations is what
distinguishes that from a real shortfall.
Error rate: 0.04% (`http_req_failed`), 0.06% (`errors`, includes body-shape
check failures) — both under the 0.1% SLO (PASS).

## 9.7 Bottleneck Assessment

**Primary hypothesis: p99 latency (210ms vs 200ms SLO) — Postgres
connection pool saturation.** Evidence: pool utilization climbed to 92% of
50 connections during the steady-state window, tracking the same
timestamps as the p99 inflection; p50/p95 stayed flat, consistent with a
small fraction of requests queueing for a pool slot rather than a systemic
slowdown. Affected SLO: p99 latency. This is a correlation, not a proven
cause — confirming it requires the pool-size re-run in Recommendation 1,
not just this analysis.

Recommended fix: measured avg query time is 25ms (APM), so target pool size
= `ceil(2000 RPS × 0.025s × 1.3 headroom) = 65`; alternatively add a read
replica if the pool is already sized to the DB's own connection budget. If
pool saturation is in fact the cause, p99 should drop toward the p95 level
(145ms) once queueing is eliminated — but this is the hypothesis the re-run
is for, not a guaranteed outcome; a pool-size increase that doesn't move
p99 would point to a different bottleneck (e.g. query plan, lock
contention) instead.

## 9.8 Recommendations

1. **Raise Postgres pool size to 65, re-run the same scenario** (quick) —
   the only way to confirm pool saturation as the cause rather than a
   correlated-but-coincidental signal.
2. **Add pool-utilization and query-latency dashboards alongside p99**
   (medium) — this run only caught the correlation because pool metrics
   happened to be collected; make it standard for every checkout-service run.
3. **Re-run at 2,500+ RPS after the pool fix** (medium) — confirms headroom
   beyond the current SLO target, not just a pass at the exact threshold.

## 9.9 Uncovered Risks

- Soak behavior (30-60+ min) not tested — connection leaks or slow memory
  growth under the same load are unvalidated.
- Only the happy-path checkout body shape was exercised — malformed-cart
  and payment-decline paths were not load tested.
- Single-region test — cross-region latency to checkout-service is unknown.
- Write-path only; read endpoints (`GET /v1/orders/{id}`) were not included
  in this run and may have a different bottleneck profile.
- The 1.9-3.5 GB memory budget (Hygiene #13) is a pre-flight calculation,
  not a measured load-generator RSS — no `ps`/`time -v` sample was taken
  during this run to confirm it.

### Hygiene #13 — load-generator memory budget (k6-patterns.md §11.7 format)

**Don't infer peak VU count from config text — ask k6 directly:**
`k6 inspect --execution-requirements checkout-load-test.js` reports
`"maxVUs": 800` for the whole script, not `20+800+800+800=2420`. The four
scenarios don't overlap in time (warmup → ramp → load_test → cooldown,
verified via the same command's `"totalDuration": "4m30s"`), so k6 reuses
VU capacity across the timeline instead of reserving each scenario's pool
separately. An earlier revision of this section assumed summed pools —
wrong, and caught only by running the tool instead of reasoning about the
config.

```
VU floor (expected, preAllocatedVUs peak) = 400 × 3 MB ≈ 1.2 GB
VU floor (worst case, maxVUs peak, per `k6 inspect --execution-requirements`) = 800 × 3 MB ≈ 2.4 GB
sample storage ≈ 8 built-in Trends (http_req_blocked/connecting/
  tls_handshaking/sending/waiting/receiving/duration + iteration_duration —
  k6 emits all 8 for every HTTP script regardless of PROFILE_TIMINGS-style
  opt-in duplicates, which this script adds none of) × ~441k total samples
  × 80 B ≈ 270 MB
response bodies ≈ 800 VUs × ~300 B (order-confirmation JSON) ≈ 240 KB — kept,
  not discarded (see below); negligible at this size
tag overhead ≈ negligible (single `tags.name` bucket, no dynamic URL)

peak RSS ≈ (1.2 to 2.4 GB + 0.27 GB) × 1.3 GC slack ≈ 1.9 to 3.5 GB
```

The 3.5 GB worst case is 87.5% of a 4 GB generator — over the 80% budget
threshold this skill's own checklist sets (SKILL.md §5.4 item 18), so "4 GB
is comfortable" was wrong by that rule's own math. Mathematical minimum to
clear 80%: 3.5 GB / 0.8 ≈ 4.4 GB; in practice, provision **at least 8 GB**
— the model above doesn't account for the OS, the k6 binary itself, or
other host processes. Measure real RSS (`ps`/`time -v`) on the first actual
run before trusting this pre-flight number to tighten `maxVUs` further.

`discardResponseBodies` is still **not** set (the check calls
`r.json('orderId')`, and that global
flag would silently empty every response body before the check runs —
k6-patterns.md §11.4's own documented trap), and the corrected numbers
confirm that choice was cheap: bodies were never more than 240 KB of a
multi-GB budget either way.

That said, Scorecard item 13 bundles four sub-requirements (correct VU
sizing, no extra diagnostic Trends, no `--out csv`/`--out json`,
`discardResponseBodies` + `responseType:'text'` override in setup) — this
script satisfies the first three but not the fourth. A low memory risk
doesn't change whether the literal checklist item was followed; see the
Scorecard note below for why Hygiene is scored 3/5, not 4/5.

---

**Scorecard**: 11/13 — Critical 3/3, Standard 5/5, Hygiene 3/5 — **PASS**
(this verdict is about test methodology, per SKILL.md §8's own formula —
Critical 3/3 AND Standard >=4/5 AND Hygiene >=3/5, all cleared including
Hygiene at exactly 3/5 — and is separate from the SLO verdict. Hygiene
fails on #10, no baseline for this SLO set, and #13: the memory budget
above is low-risk, but item 13 also requires `discardResponseBodies` +
`responseType:'text'` override, which this script doesn't set — a
justified choice, not a met requirement, so the item doesn't pass on its
literal text). Data basis: results available, partial profiling
(pool metrics correlated, no full flame-graph/APM trace). **The SLO verdict
itself is FAIL** (p99 210ms breaches the 200ms SLO — §9.6) — a well-run test
still surfaced a real SLO miss; the two verdicts answer different
questions and are not meant to agree.
---
title: load-test skill design rationale
owner: awesome-skills maintainers
status: active
last_updated: 2026-07-10
applicable_versions: current repository version
---

# load-test Skill Design Rationale

`load-test` is a service-level performance-testing framework. Its core idea is: **the first step of a good load test is not "throw some traffic at it and see" — it is to define the SLOs first, because without an SLO every performance number is just noise you cannot judge as good or bad. Once the SLOs exist, they drive scenario selection, script design, and the load generator's own resource planning; then percentiles (not averages), scenario discipline, a tiered scorecard, and an Uncovered-Risks section that is never empty make it clear what the test actually proved and what it did not.** That is why the skill turns four gates — Context Collection, SLO-First, Scope Classification, Output Completeness — together with depth selection, degradation modes, a 19-item checklist, scenario/tool selection, an anti-example catalog, a three-tier scorecard, and an output contract, into one fixed workflow.

## 1. Definition

`load-test` is used to:

- Write k6 / vegeta / wrk load-test scripts for HTTP / gRPC services
- Help the user pin down SLOs (latency, throughput, error rate, availability) *before* any script is written
- Select the right scenario for the testing goal (smoke / load / stress / breakpoint / soak / spike)
- Analyze results, deliver an SLO pass/fail verdict, and locate bottlenecks
- Do capacity planning, or investigate latency / throughput problems during a production incident

Its output is not just a script or a bare "the test passed," but a fixed-structure report:

- Context summary (target service, protocol, deployment, SLOs)
- Mode and depth (Write / Review / Analyze × Lite / Standard / Deep) with rationale
- SLO definition
- Scenario design
- The script, or a review of the script
- Results analysis (percentile table, error classification, per-metric SLO verdict)
- Bottleneck assessment
- Prioritized recommendations
- Uncovered risks (mandatory — never empty)
- A one-line three-tier scorecard verdict

By design it behaves more like a "load-testing governance framework" than a prompt that just emits a k6 script. The question it answers is "why does this test count?", not merely "send some requests for me."

## 2. Background and Problem

What this skill solves is not "the model can't write a k6 script" — on the contrary, the evaluation shows the base model already knows load testing quite well. The real problem is that, without a framework, load testing slips easily into several "looks done, doesn't actually count" patterns.

The common failures cluster into roughly 8 types:

| Problem | Typical consequence |
|---------|---------------------|
| Running with no SLO | You get numbers like p99=312ms, 4500 RPS — but no one knows if that is good or bad, so no decision can be made |
| Reporting latency as an average | avg=45ms looks great, yet hides p99=2.1s — 1% of users wait more than 2 seconds |
| Measuring without warmup | The first 30s mixes in connection-pool setup and cold caches, inflating p99 by 5-10x |
| Declaring pass after too short a run | "Passed" after 30s, but GC, connection-pool exhaustion, and memory leaks only surface after minutes |
| Requesting the same record every time | 100% cache hit rate; the real database path is never exercised |
| Load generator co-located with the target | The two fight for CPU, so you measure resource contention, not service performance |
| The load generator itself gets crushed | `maxVUs` set too high; when the service saturates k6 keeps spawning VUs, OOMs minutes later, and it gets misread as "the service crashed" |
| The report never says what was *not* tested | The team reads the result as a complete answer, silently omitting spike, single-replica failure, idempotency, and other critical unverified scenarios |

The design logic of `load-test` is to first settle "what is the pass criterion, what question is this test answering, how is the load modeled, can the generator take it, which conclusions are backed by data, and what was left untested" — and only then decide what script to write, which scenario to run, and how to render the verdict.

## 3. Comparison With Common Alternatives

| Dimension | `load-test` skill | Just asking the model to "write a k6 script" | Treating load testing as "run some traffic and read the numbers" |
|-----------|-------------------|----------------------------------------------|------------------------------------------------------------------|
| SLO-first | Strong | Weak | Almost none |
| Percentile discipline | Strong | Medium | Weak (tends to report averages) |
| Goal-driven scenarios | Strong | Medium | Weak |
| Tool / load-model choice | Strong (open vs closed model matters) | Weak | Weak |
| Load-generator health | Strong (Little's-Law `maxVUs`, memory budget) | Almost none | Almost none |
| Bottleneck attribution | Strong (app / infrastructure / test-artifact tiers) | Medium | Weak |
| Auditable results | Strong (three-tier scorecard + uncovered risks) | Weak | Weak |
| Honesty about what was *not* tested | Mandatory | Usually silent | Usually silent |

One conclusion worth stressing from the evaluation: the value is not "teaching the model how to load test," but lifting load testing from a pile of loose numbers into a conclusion that has a pass criterion, is reproducible, is auditable, and honestly states its boundaries.

## 4. Core Design Logic

### 4.1 Define the SLO first, then write the script

The second of the skill's four gates is SLO-First, and it is a hard block: without an SLO, you are not allowed to start writing a script. This step is the intellectual core of the whole skill.

The reason is direct: the product of a load test is a *judgment* — "did this service meet its target under the target load?" Without an SLO there is no "met" line, and every p99 or RPS is an uninterpretable number. The skill fixes the minimum SLO set at four items: latency (p50 and p99), throughput (minimum sustained RPS), error rate (spelled out as "< 0.1% 5xx," not "low error rate"), and availability.

More importantly, an SLO is not prose written down for humans to read — it must land in k6's `thresholds` block and become the machine-checked basis for pass/fail. The evaluation explicitly requires SLOs to be encoded as `thresholds` rather than as `check()` comparisons, because `check()` evaluates per-VU independently and never produces a statistical aggregate.

This addresses the single most common distortion: testing a great deal and then only being able to say "looks about right."

### 4.2 Treat percentiles as correctness, not taste

`load-test` insists that latency be reported as p50 / p95 / p99 / p99.9 / max, and never concluded from an average. The reference doc puts it bluntly — if 99% of requests take 10ms and 1% take 5 seconds, the average is 60ms, and that 60ms is "a number no one actually experiences."

It even turns the *shape* of the distribution into a readable diagnostic signal: p99 under 3× p50 is a healthy narrow distribution; p99 over 10× p50 indicates bimodal behavior or resource contention (cache hit vs miss, GC pauses, connection-pool exhaustion); a sudden jump at a specific percentile usually means a hard limit was hit — a connection pool, a thread pool, or a rate limiter.

The point of this layer: reporting an average is not a "style choice" — it is a defect that yields the wrong conclusion.

### 4.3 Scenarios are driven by the testing goal

The skill breaks load scenarios into six types, each tied to a specific question rather than a vague "apply some pressure":

- smoke: does it work at all under light load?
- load: can it hold the target RPS?
- stress: past the target, where does it start to degrade?
- breakpoint: where is the absolute ceiling?
- soak: will a long run leak memory or drain the connection pool?
- spike: a sudden 10× burst then drop — can it recover?

It explicitly requires "pick the scenario by the testing goal," not fire off a batch of requests. At higher depth, multiple scenarios compose (smoke → load → stress → breakpoint).

### 4.4 The tool choice is really a load-model choice

The k6-vs-vegeta trade-off is stated clearly, and it turns on a point that is easy to miss — the open model vs the closed model.

k6 uses virtual users (VUs) plus think time to simulate real user behavior, a closed model; vegeta fires at a fixed arrival rate regardless of how slow the service is, an open model. The reference doc names the crux: when the service slows down, a closed model automatically sends fewer requests and thereby *hides* the latency problem, whereas an open, fixed-arrival-rate load lets requests queue up — "which is exactly how you find saturation points."

So the skill's stance is: use k6 to simulate realistic user behavior and to run soak tests; use vegeta's arrival-rate model to control rate precisely and find the capacity ceiling. This is a deliberate way to avoid *coordinated omission*, a classic load-testing trap — not just "use whichever tool is handy."

### 4.5 Treat the load generator itself as a first-class citizen

This is the most distinctive — and most experience-hardened — layer of `load-test`. Many load-testing guides care only about the service under test; this skill spends a great deal of space on whether the machine *generating* the load will fall over first.

It mandates several things:

- The load generator must be deployed separately from the target — never the same machine, pod, or network bottleneck; otherwise you measure CPU contention, not service performance
- The generator's own capacity must be verified up front; with k6, watch `dropped_iterations`
- k6's `maxVUs` must be sized via Little's Law: needed VUs ≈ rate × healthy-period p95, and `maxVUs` is just twice that

The last point matters most. The reference doc records a real incident: `maxVUs` for a 4k TPS test was casually set to 8000 ("leave some headroom"); when the service saturated, k6 kept spawning VUs to sustain the rate, each VU costing ~3 MB, so 8000 × 3 MB = 24 GB and the generator OOMed at the six-to-eight-minute mark — and this gets misread as "the load test crashed" when really the service could not sustain the target rate. The correct fix caps `maxVUs` at 1600; when the service saturates, k6 faithfully reports `dropped_iterations`, which is the correct signal that "the service can't sustain the target rate," not a test failure.

The skill freezes this lesson into a formula, into anti-examples (AE-7, AE-8), and into a Hygiene scorecard item — precisely so no one steps on the same rake twice.

### 4.6 Warmup and sufficient duration are hard constraints

`load-test` requires measurement to begin only after warmup — JVM warmup, connection-pool fill, and cache priming are all excluded from the measured window; in k6 a separate warmup scenario with a phase tag keeps warmup samples from polluting the SLO verdict. It equally stresses duration: at least 1 minute for smoke, 3-5 minutes for load, 15+ minutes for soak, because GC, connection-pool exhaustion, and memory leaks take minutes to appear. The base model's single most typical substantive miss in the evaluation was exactly failing to flag "30 seconds is not enough."

### 4.7 Test data must be realistic — avoid cache bias

Hitting the same ID every time means a 100% cache hit rate and a database path that never gets tested. The skill requires parameterized data feeds with a realistic distribution, so the cache hit/miss ratio resembles production. Developers do not fail this because they don't know it — they fail it because it doesn't naturally come to mind while writing the script. Turned into a checklist item, test quality no longer depends on in-the-moment memory.

### 4.8 Degradation modes and "never fabricate performance numbers"

In reality the inputs are often incomplete: maybe there is a script but no results, or results but no SLOs. `load-test` handles this with a degradation-mode table that states, for each kind of input, "what can be delivered and what cannot be claimed," and requires an explicit `# DEGRADED:` marker. It has one iron rule: never fabricate performance numbers, and never claim SLO compliance without data. This keeps the skill honest when information is missing, instead of forcing out a conclusion that merely looks complete.

### 4.9 The three-tier scorecard is a production gate, not a scoring game

After every analysis the skill applies a three-tier scorecard: Critical (all 3 must pass — any failure means redo the test), Standard (4 of 5), Hygiene (3 of 5). Critical covers non-negotiable items such as "SLO defined before the test," "warmup excluded," and "steady-state duration sufficient."

The significance of this layer is that it converts "can this script be used for a production load test?" from "feels about right" into a trackable state: if Critical is not all-pass, the script is FAIL, not "could use some polish." When the base model reviewed a defective script in the evaluation, it was exactly this kind of verdict — an explicit Critical 0/3 — that it could not produce.

### 4.10 Bottleneck attribution has three tiers — first separate "service problem" from "test problem"

When analyzing results, `load-test` uses a three-tier bottleneck taxonomy: the application tier (serialized processing, N+1 queries, missing connection pooling, unbounded goroutines, synchronous external calls), the infrastructure tier (too few replicas, database bottleneck, network bandwidth), and a particularly important third tier — problems with the *test method itself* (the generator became the bottleneck, the generator sits across a slow network from the target, cache-warming artifacts).

Each is paired with an observable signal (e.g. "adding replicas doesn't help and DB query time dominates" points to a database bottleneck; "min latency equals the network RTT" points to a cross-network deployment). Breaking out that third tier is a mature move — it exists specifically to stop the analyst from blaming the service for a test-rig defect.

### 4.11 Uncovered risks are never empty

Section §9.9 "Uncovered Risks" of the output contract is the skill's most representative invention, and it is mandated to never be empty. It forces every delivery to spell out what was not tested this time: soak not run, memory-leak risk unvalidated; only read paths tested, write-path capacity unknown; single-region test, cross-region latency unmeasured, and so on.

Its value is that a result which omits this section is easily read as a complete answer, silently dropping spike, single-replica failure, and idempotency. The rule turns those blind spots from "no one mentioned them" into "explicitly listed open items." This is exactly what a bare `k6 run` never produces.

### 4.12 Defects are traceable by number, not off-the-cuff commentary

`load-test` turns common defects into a numbered anti-example catalog (AE-1 no warmup, AE-6 concluding from an average, and so on). Reviewing a script, it says "CRITICAL-3 — AE-1: missing warmup / ramp-up," rather than a vague "consider adding a warmup."

The benefit is that the team now has a precise reference point back into `SKILL.md`, so the review standard is consistent and reproducible across the whole team, instead of a different opinion each time based on personal experience.

### 4.13 Real investment in triggering and boundaries

`load-test`'s `description` uses a task-type enumeration to cover trigger phrases; in the evaluation its trigger accuracy reaches F1 ≈ 87%, hitting all 10 should-trigger scenarios and 6 of 8 should-not ones (the soft-boundary cases like "CPU is high" and "set up a k6 Cloud account" are caught by the applicability gate). It also draws a clear line with `go-benchmark`: the latter does function-level micro-profiling, while `load-test` does service-level end-to-end testing — one leaning micro, the other macro.

## 5. Which Concrete Problems This Design Solves

| Problem type | Corresponding design in the skill | Actual effect |
|--------------|-----------------------------------|---------------|
| Running with no pass criterion | SLO-First gate + `thresholds` | Every test has an explicit target line |
| Averages hiding the tail | Percentile discipline (p50/p95/p99/p99.9/max) | Tail problems are no longer masked by a pretty average |
| Firing traffic with no goal | Six scenarios chosen by goal | Scenario aligned to the question being answered |
| Slow responses hiding latency | Open / closed model choice | The true saturation point is findable |
| The generator falling over first | Little's-Law `maxVUs` + memory budget | Generator doesn't OOM; results reflect the service |
| Cold-start / short-run contamination | Warmup separation + duration floor | Numbers reflect steady state, not startup noise |
| Cache bias | Parameterized realistic data | The database path is actually exercised |
| Blaming test-rig issues on the service | Three-tier bottleneck attribution | First separate service from test problems |
| Results read as a complete conclusion | §9.9 Uncovered Risks (mandatory) | Blind spots become explicit open items |
| Reviews based purely on personal experience | Numbered anti-examples + three-tier scorecard | Reviews are reproducible and auditable |

## 6. Main Highlights

### 6.1 It turns load testing from "running numbers" into "a judgment with a pass criterion"

SLO-First is the foundation of the whole skill and the most fundamental difference between it and "just running a k6."

### 6.2 Its real increment is structure and blind spots, not domain knowledge

This is the most honest — and most important — conclusion in the evaluation. It shows the base model already knows load testing well: in the Analyze (results analysis) scenario, using the skill versus not is only +14.3pp apart, with both sides independently computing the saturation RPS and both pointing at the database connection pool. The skill's real leverage is in the Review scenario — a gap of +62.5pp — because that is where it matters whether you can systematically name the defects, give a numbered verdict, and list the blind spots. Overall, with the skill the clean scenarios reach 15/15 (100%) versus 9/15 (60%) without, a gap of about +40pp.

In other words, the value of `load-test` is mostly not "knowing more," but "forcing you to write the conclusion with complete structure and to list the blind spots explicitly." This value profile closely resembles that of `go-benchmark`.

### 6.3 Its attention to load-generator health is unusually rare

Sizing `maxVUs` via Little's Law, computing a memory budget, and writing generator OOM and the `--out csv` memory cost up as anti-examples — these lessons grew out of a real incident and are the kind of thing ordinary load-testing tutorials simply never mention.

### 6.4 §9.9 Uncovered Risks is a highly distinctive invention

Forcing every delivery to state "what was not tested," turning silent omissions into explicit open items, is enormously practical in team settings.

### 6.5 The three-tier scorecard makes "can this ship?" decidable

The Critical / Standard / Hygiene tiers quantify "is this script safe?" into a trackable state instead of a gut feeling.

### 6.6 Bottleneck attribution separates "service problem" from "test artifact"

Breaking out "test-method errors" as a distinct third tier specifically prevents misattributing test-rig issues — generator OOM, cross-network latency — as service bottlenecks.

## 7. When to Use It, and When Not to Force It

| Scenario | Suitable? | Reason |
|----------|-----------|--------|
| Writing load-test scripts and defining SLOs for an HTTP/gRPC service | Very suitable | This is the core scenario |
| Reviewing the quality of an existing load-test script | Very suitable | Review is exactly where its increment is largest (~+62.5pp) |
| Analyzing results, locating bottlenecks, capacity planning | Suitable | Useful, but the base model is already strong here, so the increment is smaller |
| Investigating latency / throughput in a production incident | Suitable | The three-tier bottleneck attribution is well targeted |
| Function-level micro-benchmarks | Not suitable | Hand off to `go-benchmark` |
| Database-only benchmarks, browser / UI performance | Not suitable | Beyond service-level load testing |
| Chaos-engineering fault injection, infrastructure provisioning | Not suitable | Out of scope |

One expectation to set: `load-test` has the highest context and runtime overhead of the skills it was compared against (runtime overhead ~+107%), because it loads `SKILL.md` plus over a thousand lines of reference material. For a quick smoke check, the Lite depth is enough — there is no need to spin up the heavy workflow every time.

## 8. Conclusion

The real strength of `load-test` is not that it writes a k6 script faster, but that it freezes the parts of load testing that most easily become box-ticking: define the SLO first, let the SLO drive the scenario and the script, and at the same time bring the load generator's own resource health, percentile discipline, warmup separation, cache bias, bottleneck attribution, and "what was not tested" all under constraint — ending in a three-tier scorecard that yields an auditable pass/fail verdict.

By design, the skill clearly embodies one principle: **the key to a high-quality load test is not running larger traffic, but making every test able to state its own pass criterion, how the load was modeled, whether the numbers are statistically sound, whether the bottleneck lies in the service or the test rig, and which risks this run simply did not cover.** That is why it fits writing scripts, reviewing scripts, and pre-release performance validation especially well — while for pure results analysis it is mostly helping you complete the structure and surface blind spots, rather than supplying knowledge you did not already have.

## 9. Document Maintenance

This document should be updated whenever:

- The gates, depth selection, degradation modes, checklist, scenario/tool selection, anti-example catalog, three-tier scorecard, or output contract in `skills/load-test/SKILL.md` change.
- The key patterns, memory model, or bottleneck-attribution method in `skills/load-test/references/k6-patterns.md`, `vegeta-patterns.md`, or `analysis-guide.md` change.
- The core results backing this document (scores, trigger accuracy, with/without-skill deltas, etc.) in `evaluate/load-test-skill-eval-report.md` or `evaluate/load-test-skill-eval-report.zh-CN.md` change.

Review quarterly; if the SLO gate, scenario definitions, scorecard structure, or trigger-condition description of `load-test` undergoes a noticeable refactor, review immediately.

## 10. Related Reading

- `skills/load-test/SKILL.md`
- `skills/load-test/references/k6-patterns.md`
- `skills/load-test/references/vegeta-patterns.md`
- `skills/load-test/references/analysis-guide.md`
- `skills/load-test/scripts/tests/COVERAGE.md`
- `evaluate/load-test-skill-eval-report.md`
- `evaluate/load-test-skill-eval-report.zh-CN.md`
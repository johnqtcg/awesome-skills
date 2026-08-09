# kafka-event-driven-design Skill Evaluation Report

> Framework: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
> Evaluation date: 2026-04-18
> Subject: `kafka-event-driven-design`

> [!IMPORTANT]
> **Status: §1–§7 are SUPERSEDED. Read [§8](#8-validity-limits-of-this-evaluation-added-2026-08-09) first.**
>
> The A/B numbers below (including "+50 pp weighted pass rate" and "production-ready")
> were produced with an oracle derived from the skill's own checklist. That oracle
> scored at least one factual error as a PASS, so the pass rates measure **adherence
> to the skill, not correctness**. Three external review rounds have since found
> substantive defects in documents this evaluation graded as strengths.
>
> What is verified today is the **documents**, by an 8-gate deterministic harness
> (26 semantic lint rules, mutation sweep, independent paraphrase corpus, golden
> fixtures, and an offline calibration of the model-eval grader). What remains
> unverified is the **model itself**: the A/B harness exists and its grader is
> calibrated, but no arm has been scored against a real model. Also outstanding:
> trigger recall/precision, and a live-broker matrix. See §8.5, §8.7 and §8.8.
>
> Do not cite §1–§7 as evidence of skill effectiveness.

---

`kafka-event-driven-design` is a Kafka architecture design and review skill covering topic design, partition strategy, event schema definition (Avro/Protobuf), idempotent producers, consumer deduplication, dead letter queues (DLQ), exactly-once semantics, Schema Registry compatibility, backpressure handling, and consumer lag monitoring. This evaluation ran 3 A/B test scenarios (6 real model calls) and graded 23 assertions comparing responses with and without the skill.

The headline finding: the baseline model has solid Kafka knowledge overall — scenario 1 (fan-out design) scored 75% weighted without the skill. The skill's differentiated value concentrates on three things: **correctly classifying `enable.idempotence=false` as a Critical defect** (the baseline called it "acceptable"), **enforcing `BACKWARD_TRANSITIVE` schema compatibility** (the baseline defaulted to the weaker `BACKWARD`), and **flagging missing DLQ as Critical** during producer reviews (the baseline skipped it entirely).

## 1. Skill Overview

`kafka-event-driven-design` defines 4 mandatory gates (Context Collection → Scope Classification → Risk Classification → Output Completeness), 3 depth levels (Lite / Standard / Deep), 4 degradation modes (Full / Degraded / Minimal / Planning), and a 14-item design checklist. The §9 output contract ensures every response includes architecture design, risk assessment, implementation patterns, monitoring alerts, and an uncovered risks section.

**Core components:**

| File | Lines | Responsibility |
|------|-------|----------------|
| `SKILL.md` | ~380 | Main skill definition — 4 gates, 3 depths, 14-item checklist, 6 inline + 7 extended anti-examples, §8 scorecard, §9 output contract |
| `references/event-schema-patterns.md` | 210 | Event envelope format, schema evolution strategies (BACKWARD/FORWARD/FULL), Avro vs. Protobuf vs. JSON Schema comparison, idempotency key design, Outbox Pattern |
| `references/consumer-failure-modes.md` | 225 | Rebalance storm, poison message / DLQ, lag runaway, duplicate processing, ordering violation — with defense matrix |
| `references/consumer-anti-examples.md` | 138 | AE-7 through AE-13: auto-commit hazards, blocking I/O in poll loops, single-partition global ordering, group ID reuse, compacted topic tombstones, partition count increases, missing schema validation |
| `scripts/tests/test_skill_contract.py` | — | 50 contract tests across 12 classes |
| `scripts/tests/test_golden_scenarios.py` | — | 41 golden tests (11 fixtures: 4 critical defects, 3 standard defects, 2 good practices, 1 degradation, 1 workflow) |

---

## 2. Test Design

### 2.1 Scenarios

| # | Scenario | Core challenge | Expected outcome |
|---|----------|----------------|------------------|
| 0 | Producer config review | `acks=1`, `Idempotent=false`, `Key=nil`, no DLQ, no event envelope metadata | All Critical failures identified; complete scorecard and uncovered risks produced |
| 1 | Multi-consumer fan-out design | 3 consumers with different delivery semantics (financial / notification / analytics), schema evolution needed | Full architecture with `BACKWARD_TRANSITIVE`, idempotent consumer patterns, DLQ, and tiered lag alerts |
| 2 | Degraded — topic design question | No environment context; user asks whether `events` / 1 partition / 1-day retention is a reasonable design | Degradation mode declared; all three issues flagged; blocking unknowns listed in §9.9 |

### 2.2 Assertion Matrix (23 assertions)

**Scenario 0 — Producer Config Review (9 assertions)**

| ID | Assertion | With-Skill | Without-Skill |
|----|-----------|:----------:|:-------------:|
| A1 | Complete context gate table (§9.1: Kafka version, schema format, ordering, delivery guarantee) | PASS | FAIL |
| A2 | `acks=1` flagged as Critical / data loss risk | PASS | PASS |
| A3 | `Idempotent=false` flagged as Critical — not "an acceptable trade-off" | PASS | FAIL |
| A4 | Missing DLQ flagged as Critical (poison messages will stall the partition) | PASS | FAIL |
| A5 | Null partition key (`Key=nil`) flagged as ordering failure risk | PASS | PASS |
| A6 | Missing event envelope metadata (no `event_id`) flagged as deduplication blocker | PASS | FAIL |
| A7 | Recommends both `acks=all` AND `enable.idempotence=true` together | PASS | PARTIAL |
| A8 | Produces a Critical / Standard / Hygiene scorecard | PASS | FAIL |
| A9 | Produces a §9.9 Uncovered Risks section | PASS | FAIL |

**Scenario 0:** Without-Skill = 2 pass + 1 partial + 6 fail (weighted 2.5/9 = **28%**) | With-Skill = **9/9**

**Scenario 1 — Multi-Consumer Fan-out Design (8 assertions)**

| ID | Assertion | With-Skill | Without-Skill |
|----|-----------|:----------:|:-------------:|
| B1 | Formally classifies depth as Standard or Deep with rationale | PASS | FAIL |
| B2 | Topic naming follows `{domain}.{entity}.{event-type}` convention | PASS | PASS |
| B3 | Partition key is `order_id` (not null) to guarantee per-order ordering | PASS | PASS |
| B4 | Each consumer service gets its own Consumer Group | PASS | PASS |
| B5 | payment-service requires idempotent consumption (DB-level `ON CONFLICT DO NOTHING`) | PASS | PASS |
| B6 | Schema includes full event envelope (`event_id`, `event_type`, `timestamp`, `source_service`, `correlation_id`) | PASS | PARTIAL |
| B7 | Schema Registry configured with `BACKWARD_TRANSITIVE` (not just `BACKWARD`) | PASS | PARTIAL |
| B8 | Consumer lag monitoring per group + DLQ design defined | PASS | PASS |

**Scenario 1:** Without-Skill = 5 pass + 2 partial + 1 fail (weighted 6/8 = **75%**) | With-Skill = **8/8**

**Scenario 2 — Degraded: Topic Design Question (6 assertions)**

| ID | Assertion | With-Skill | Without-Skill |
|----|-----------|:----------:|:-------------:|
| C1 | Formally declares degradation mode | PASS | FAIL |
| C2 | Topic name `events` flagged as an anti-pattern (too generic) | PASS | PASS |
| C3 | Partition count of 1 flagged as a scalability defect (UNSAFE, AE-9 equivalent) | PASS | PASS |
| C4 | 1-day retention flagged as a data loss risk for an order system | PASS | PASS |
| C5 | Proactively requests missing context (Kafka version, delivery guarantee, throughput, ordering requirement) | PASS | FAIL |
| C6 | §9.9 lists all unknowns as blocking gaps | PASS | FAIL |

**Scenario 2:** Without-Skill = 3 pass + 0 partial + 3 fail (weighted 3/6 = **50%**) | With-Skill = **6/6**

---

## 3. Pass Rate Comparison

### 3.1 Overall

| Configuration | Pass | Partial | Fail | Strict pass rate | Weighted pass rate (partial = 0.5) |
|---------------|:----:|:-------:|:----:|:----------------:|:----------------------------------:|
| **With-Skill** | **23** | 0 | 0 | **100%** | **100%** |
| **Without-Skill** | 10 | 3 | 10 | 43% | **50%** |

**Improvement: +57 pp (strict) / +50 pp (weighted)**

### 3.2 By Scenario

| Scenario | With-Skill | Without-Skill (weighted) | Gap |
|----------|:----------:|:------------------------:|:---:|
| 0. Producer config review | 9/9 (100%) | 2.5/9 (28%) | +72 pp |
| 1. Multi-consumer fan-out design | 8/8 (100%) | 6/8 (75%) | +25 pp |
| 2. Degraded topic design | 6/6 (100%) | 3/6 (50%) | +50 pp |

### 3.3 Key Differentiating Dimensions

| Dimension | With-Skill | Without-Skill |
|-----------|:----------:|:-------------:|
| `enable.idempotence=false` classified as Critical | 3/3 (100%) | 0/3 (0%) |
| `BACKWARD_TRANSITIVE` compatibility mode selected | 1/1 (100%) | 0/1 (0%) |
| §9 scorecard produced | 3/3 (100%) | 0/3 (0%) |
| §9.9 Uncovered Risks section produced | 3/3 (100%) | 0/3 (0%) |
| Degradation mode formally declared | 1/1 (100%) | 0/1 (0%) |
| Missing DLQ flagged as Critical during producer review | 1/1 (100%) | 0/1 (0%) |
| Complete event envelope (including `correlation_id`) | 3/3 (100%) | 1/3 (33%) |
| Missing context proactively requested (Gate 1 items) | 1/1 (100%) | 0/1 (0%) |

---

## 4. Key Difference Analysis

### 4.1 Behaviors unique to With-Skill

**A3 — `Idempotent=false` classified as Critical**

This is the sharpest knowledge divergence in the evaluation. The baseline response explicitly stated:

> *"Idempotent=false Is Acceptable Here, But Note the Trade-Off — With retries enabled and Idempotent=false, a retry after a broker ack-but-network-drop produces a duplicate message. For at-least-once this is allowed by definition..."*

This is technically defensible in isolation, but misses the point in an order processing context. The skill classifies it as a Critical FAIL and specifies that `enable.idempotence=true` with `MaxOpenRequests=1` is part of the minimum safe configuration — the direct application of AE-1. The baseline lacks a classification framework that makes this distinction automatic.

**A4 — Missing DLQ flagged as Critical during a producer review**

The baseline said nothing about DLQ when reviewing producer code. The skill flags it as Critical 0/3 FAIL in the scorecard and explains in §9.9: no DLQ means a single poison message causes infinite redelivery, stalling the entire partition. This is AE-3 directly applied. The baseline, when looking at producer code, doesn't naturally connect to the consumer-side DLQ requirement.

**B7 — `BACKWARD_TRANSITIVE` vs. `BACKWARD`**

The baseline recommended Schema Registry with `BACKWARD` compatibility. The skill chose `BACKWARD_TRANSITIVE` and explained why it matters:

> *"`BACKWARD_TRANSITIVE` checks compatibility against ALL previous schema versions, not just the immediately preceding one — critical when multiple consumers may be deployed at different schema versions simultaneously during rolling deploys."*

`BACKWARD` only guarantees the new schema can read data written by the previous version — so consumers upgrade first. During rolling deployments, consumers may be running several schema versions apart. `BACKWARD_TRANSITIVE` closes that gap. This precision comes from `event-schema-patterns.md` §2.

> **Correction, 2026-08-09**: the direction stated above is right, but the surrounding judgement was not. `BACKWARD_TRANSITIVE` is **not** unconditionally "safest" — it permanently constrains the schema to the intersection of all registered versions, and buys nothing on a topic where no reader or record survives more than one version. The skill body now recommends it from a stated condition (old data or old readers genuinely span versions) rather than as a blanket default, and assertion B7 has been reworded from "chose `BACKWARD_TRANSITIVE`" to "chose a compatibility mode deliberately and stated its direction correctly". The zh-CN edition of this section additionally had the BACKWARD/FORWARD direction reversed; it has been fixed.

### 4.2 Areas where the baseline already performs well

**B2/B3/B4/B5/B8 — Scenario 1 Kafka architecture knowledge**

The baseline did well in scenario 1: it correctly recommended `order_id` as the partition key, three separate Consumer Groups, DB-level idempotent processing for payment-service (`INSERT ... ON CONFLICT`), per-consumer lag alerts, and DLQs.

This confirms that the baseline has internalized common Kafka architecture patterns. The skill's incremental contribution in scenario 1 is narrower: complete event envelope fields (notably `correlation_id`), the `BACKWARD_TRANSITIVE` precision, and the structured §9 output — plus a §9.9 section covering 9 non-obvious risks such as "does payment-service actually need to subscribe to `orders.shipped`?" and "does the external payment gateway support idempotency keys?"

**C2/C3/C4 — Scenario 2 technical judgments**

The baseline correctly identified all three concrete problems (generic topic name, single partition, 1-day retention) and gave actionable recommendations with sensible target values. The skill's additional value here is structural: formally naming the degradation mode, triggering the Gate 1 context request, converting unknowns into §9.9 blocking gaps, and producing a scorecard (0/12 FAIL) that makes the overall verdict actionable.

### 4.3 Scenario-level takeaways

**Scenario 0** shows the largest gap (+72 pp). The baseline understands `acks`, but misclassifies `idempotence`, misses DLQ entirely when reviewing producer code, and doesn't check for event envelope metadata. For business-critical order events, these gaps carry real production risk.

**Scenario 1** shows the baseline at its strongest (75% weighted). This is consistent with the oracle-migration evaluation: modern LLMs have solid internalized knowledge of mainstream distributed systems patterns. The skill's value here is about precision and completeness, not filling knowledge gaps.

**Scenario 2** illustrates the skill's degradation protocol value. The baseline gave useful, technically correct advice on three specific issues — but never triggered Gate 1, never asked for delivery guarantee or throughput, and never identified the design parameters that would fundamentally change the answer (e.g., if the requirement is exactly-once, the whole design shifts).

---

## 5. Token Cost Analysis

### 5.1 Skill context token cost

| File | Lines | Estimated tokens |
|------|-------|:----------------:|
| `SKILL.md` | ~380 | ~9,500 |
| `event-schema-patterns.md` | 210 | ~5,300 |
| `consumer-failure-modes.md` | 225 | ~5,600 |
| `consumer-anti-examples.md` | 138 | ~3,500 |
| **Total (Deep depth, all files loaded)** | | **~23,900** |

### 5.2 Actual token consumption (6 real model calls)

| Scenario | Without-Skill | With-Skill | Overhead | Tool calls |
|----------|:-------------:|:----------:|:--------:|:----------:|
| 0 (Standard: SKILL.md + schema patterns + anti-examples) | 13,889 | 35,160 | +153% | 10 |
| 1 (Standard/Deep: all 3 reference files) | 16,101 | 49,610 | +208% | 17 |
| 2 (Degraded: SKILL.md + schema patterns) | 13,091 | 33,925 | +159% | 9 |
| **Average** | **14,360** | **39,565** | **+175%** | **12** |

> **Note:** Token counts are full session totals (input + tool calls + tool results + output), as reported by the Agent tool's usage field. Scenario 1's 17 tool calls (the highest) reflects reading all 3 reference files plus SKILL.md. In production usage where the skill is injected as a system prompt rather than read via tools, the overhead falls to SKILL.md (~9,500 tokens) plus on-demand reference files — closer to 40–60% per call.

### 5.3 Cost-benefit perspective

Scenario 0 has the highest business value density. The baseline's misclassification of `enable.idempotence=false` as "acceptable" means a network glitch or broker restart in a production order system produces duplicate events. For financial events, the cost of a single double-charge incident — investigation, reversal, customer support, potential chargeback — dwarfs any token cost. Scenario 1 shows that where the baseline already has solid knowledge, the skill's marginal cost-benefit ratio is lower, but it still adds precision (`BACKWARD_TRANSITIVE`) and structural guarantees (§9.9) that the baseline never produces on its own.

---

## 6. Scoring Summary

### 6.1 By dimension

| Dimension | With-Skill | Without-Skill | Gap |
|-----------|:----------:|:-------------:|:---:|
| **Critical defect detection** (A2+A3+A4) | 3/3 (100%) | 1/3 (33%) | +67 pp |
| **Standard knowledge precision** (B6+B7) | 2/2 (100%) | 0/2 (0%) | +100 pp |
| **Degradation protocol compliance** (C1+C5+C6) | 3/3 (100%) | 0/3 (0%) | +100 pp |
| **Structured output completeness** (A8+A9+B1) | 3/3 (100%) | 0/3 (0%) | +100 pp |
| **Core Kafka knowledge** (A2+A5+B2+B3+B4+B5+B8+C2+C3+C4) | 10/10 (100%) | 9.5/10 (95%) | +5 pp |

### 6.2 Weighted total

| Configuration | Score | Weighted pass rate |
|---------------|:-----:|:-----------------:|
| With-Skill | 23/23 | **100%** |
| Without-Skill | 11.5/23 | **50%** |

---

## 7. Conclusion

`kafka-event-driven-design` achieved **100% assertion coverage** across 3 scenarios and 23 assertions in 6 real model calls, lifting the weighted pass rate from **50% to 100%** (+50 pp).

Like the oracle-migration evaluation, this one found the baseline stronger than expected — scenario 1 hit 75% weighted, confirming that mainstream Kafka architecture patterns are well internalized by modern LLMs. The skill's core value falls into three categories:

1. **Correct classification of Critical defects** — The baseline treats `enable.idempotence=false` as an acceptable trade-off for at-least-once delivery. The skill classifies it as Critical FAIL. For financial event pipelines, that misclassification is the direct path to duplicate charges in production. The skill's AE-1 and AE-3 rules make this automatic and non-negotiable.

2. **Precision knowledge, not just general knowledge** — `BACKWARD_TRANSITIVE` vs. `BACKWARD`, the full event envelope (including `correlation_id` and `source_service`), and the Outbox Pattern recommendation aren't things the baseline doesn't know — they're things the baseline doesn't surface at the right moment with the right classification. The reference files give the skill a citable specification to work from.

3. **Structured output contract** — The §9 scorecard and §9.9 Uncovered Risks turn a review or design session into an engineering decision artifact that can be used as a CI/CD gate. No matter how strong the baseline's knowledge, it won't produce this format unprompted.

**Recommendation — superseded, retained for the record.** This section originally
read "production-ready, recommended for all Kafka architecture design and code
review workflows". That conclusion does not survive §8: it rests on an oracle
built from the skill's own checklist, which scored at least one factual error as a
PASS. The durable part of the finding is narrower and still holds — for financial
event pipelines the `enable.idempotence` classification and DLQ enforcement are
where the skill diverges most usefully from the baseline. The unsupported part is
the readiness verdict itself. For the current status see §8.

---

## 8. Validity Limits of This Evaluation (added 2026-08-09)

An external review of the skill found technical errors that this evaluation
scored as *strengths*. The failure was methodological, and the limits below apply
to every number above.

**8.1 The oracle was largely the skill itself.** Assertions were written from the
skill's own checklist, so a response earned a PASS for reproducing the skill's
position — including where that position was wrong. Assertion B7 rewarded
`BACKWARD_TRANSITIVE`, which the skill asserted was "safest for most cases";
Confluent's actual rules make that a trade-off, not a correctness ranking. A
scoring rubric derived from the artifact under test cannot detect that the
artifact is wrong; it can only measure adherence.

**8.2 At least one oracle was factually incorrect.** The Schema Registry
assertions encoded the "BACKWARD forbids deleting fields" myth. A with-skill
response repeating that error scored PASS, and a correct response saying
"BACKWARD permits deleting an optional or defaulted field" would have been
scored a FAIL. The eval was, on that item, anti-correlated with truth.

**8.3 Trigger accuracy was never measured.** The project's evaluation framework
requires trigger recall/precision — whether the skill fires when it should and
stays quiet when it should not. Only in-scope prompts were run, so the false-fire
rate is unmeasured.

**8.4 Token cost was not weighed against benefit.** With-skill responses averaged
roughly **+175% tokens**. The headline "+50 pp weighted pass rate" is not
comparable to that cost without a per-scenario benefit/cost breakdown, and
scenario 1 (baseline already at 75%) is the case where the ratio is worst.

**8.5 What replaced it, and what still has not.** *(Counts in this subsection are
as of round 1; see §8.7 for current figures.)* The skill gained a
6-gate deterministic harness: a 22-rule semantic linter with a self-test that
proves each rule can both fire and stay silent, a 24-mutation sweep in which
every rule is exercised by an inverted claim, exact bidirectional detector
expectations per fixture, and a table of upstream facts transcribed from Apache
Kafka source (`ProducerConfig.java`, `ConsumerConfig.java`,
`docs/operations/*.md` on branches 2.8 / 3.0 / 4.3) rather than from the
documents under test. Against the pre-fix documents that linter independently
reports 18 findings across 15 rules, matching the external review.

That harness checks the **documents**. It does not check the **model**. A
re-run A/B evaluation still needs a blinded oracle built from official
documentation by someone who has not read the skill, plus trigger
recall/precision and a token-cost column. Until that exists, treat the pass rates
in §1–§7 as a measure of adherence to the skill, not of correctness.

### 8.6 Round 2 (same day) — what a second external pass still found

The harness described above was in place and green when a second review found
**four more substantive defects**, which is the most useful data point in this
report:

1. **A content error the linter had no rule for** — event sourcing described as
   "requires compacted topics", when `compact` retains only the latest value per
   key and therefore destroys the history on a log keyed by aggregate ID.
2. **The linter itself was bypassable.** Refutation suppression (which lets a doc
   quote a myth in order to reject it) was scoped to the whole sentence and not
   bound to the proposition being negated, so `acks=all is wrong; prefer acks=1`
   scored zero findings. Two more paraphrases bypassed it the same way.
3. **Internal contradictions the rules did not cover** — a fixed
   `lag > 10000` alert in a reference, against the skill body's own prohibition
   on undrived numeric thresholds; static membership overclaimed as eliminating
   restart rebalances; a poison-message symptom that only holds when production
   has stopped; and "transactional consumer", which is not a thing.
4. **Scope drift** — `franz-go` named in Gate 1 but absent from the client matrix.

All are fixed, and each now has a rule and a mutation behind it (25 rules, 33
mutations, including six adversarial-paraphrase mutations built directly from the
bypass forms). The lesson to carry forward is that **a green deterministic
harness bounds the errors it has rules for and says nothing about the rest** —
its own coverage is the thing most likely to be overestimated. Rounds 1 and 2
each found real defects after the previous round reported clean.

The always-loaded cost of SKILL.md is now ~32 KB, up from ~17 KB before round 1.
That buys version/client-conditional verdicts, a governance section, explicit
N/A-WARN scorecard semantics, and a stated negative scope; it is a real cost and
is recorded in COVERAGE.md rather than argued away.

### 8.7 Round 3 (2026-08-09) — closing the gaps round 2 left open

A third review pass listed six remaining gaps. Four are now closed, one was a
false premise, and one remains genuinely open.

**Closed:**

1. **Semantic lint was only proven against its own phrasing.** A separate
   `scripts/paraphrase_corpus.py` now states each proposition the way an engineer
   would say it — both the wrong claim and the correct claim about the same
   subject — with no wording shared with the docs. It found **23 missed detections
   across 13 rules** that a fully green mutation sweep had not, all since fixed.
   It stands at 113 probes over 26 rules, 0 missed, 0 false positives, and fails
   if any rule lacks probes on both polarities.
2. **The scorecard's WARN/N/A arithmetic was not mechanical.** §8 now defines five
   verdicts with explicit numerator/denominator effects, `ceil`-based thresholds
   that scale with the applicable count `A`, `NOT SCOREABLE` as a distinct verdict
   that forces the overall result, and CI-gate guidance. The §9 output template no
   longer prints fixed `/3` `/5` `/4` denominators — a residual contradiction with
   §8 that this round found and a contract test now blocks.
3. **franz-go had no regression anchor.** The contract test parsed only three
   clients, so deleting the franz-go column would have passed. It now parses the
   client-defaults table as data and asserts, in that column specifically, that
   idempotence defaults to true and that `DisableIdempotentWrite()` is named.
   Fixing the count claims this exposed ("three major client libraries", "all
   three reference files", "wrong on all three") is itself now a test.
4. **Reference files had no map.** All four exceed 100 lines and now open with a
   Contents table keyed on the symptom to look up, with a test asserting every
   anchor resolves to a real heading.

**False premise:** the missing `agents/openai.yaml` is not a defect. That file was
deliberately deleted repo-wide in `dc55e6f`; the stale convention lives in
`bestpractice/`, which has been corrected rather than the file re-added.

**Still open — the model is not evaluated.** §8.3 and §8.5 remain accurate: there
is no blinded oracle, no live-broker matrix, and **no trigger recall/precision
number**. `scripts/trigger_eval.py` now exists — a 30-probe corpus (15 in-scope,
15 deliberately near-miss out-of-scope drawn from §1's exclusion table) that
routes each prompt through the frontmatter description alone and scores
recall/precision against asymmetric 0.90 targets. Its plumbing is verified: the
`--dry-run` path and the infra-skip path both behave as specified, and a skip
exits 2 rather than 0 so it can never be mistaken for a pass. **It has not
produced a scored run.** A nested `claude -p` does not inherit the parent
session's credentials in this environment, so every probe returned
`Not logged in`, and the harness correctly reported `SKIPPED (infra)` instead of a
number. The measurement therefore remains outstanding, and it is opt-in and not
part of `run_regression.sh`. It also would not address the blinded-oracle gap
even once it runs — routing accuracy and answer correctness are different
questions. **"All gates green" continues to mean the documents are internally
consistent and free of the errors the 26 rules encode — not that the skill
measurably improves model output.**

*(Figures in this section are as of round three; see §8.8 for current ones.)*

---

## 8.8 Fourth review round — engineering remediation complete, measurement still outstanding

Six findings were raised and every one was acted on. "Closed" below means the
*engineering* is closed — the contradiction is gone, the gate exists, the harness
runs. It does **not** mean the thing being measured has been measured: finding 1
ends with a harness whose grader is calibrated and whose A/B has never been
scored against a model. That distinction is the point of §8, so it is kept in the
heading rather than buried in the body.

**1. The model was still not evaluated — harness built, still unrun.** `trigger_eval.py` measures routing, and
only as a proxy — whether a judge model finds the frontmatter `description`
classifiable, which is neither the host agent's real routing decision nor the
correctness of the answer once the skill loads. Its docstring now says all three
limits out loud.

The real gap is closed differently. `scripts/model_eval.py` runs an A/B — prompt
alone vs prompt + SKILL.md — over the 16 defect fixtures, and **the grader is not
a model**: recall over each fixture's declared `coverage_rules`, minus a penalty
for any KL rule firing on the model's own prose. Both are auditable and offline.
Arm B must clear an **absolute** threshold, not merely beat arm A — a delta-only
gate passes when both arms are broken by the same amount.

What makes this more than another unrun script is `--calibrate`: it grades the
grader, offline, with no credentials, against each fixture's own
`expected_feedback` (a known-good review) and a hand-written decoy (a fluent,
confident, wrong one), and requires separation **per fixture**. That runs as gate
7 of the regression suite. On its first execution it failed on three fixtures and
each was a real defect: `KAFKA-003` and `KAFKA-009` declared `coverage_rules` that
their own expected answers never satisfied (`dead letter` alongside `DLQ`,
`poison`, and the phrase `never claim`), and `KAFKA-006`'s expected answer never
named Schema Registry. Rules that demanded vocabulary rather than coverage were
repointed; the one genuinely thin answer was filled in.

**Still open, and stated plainly:** no arm has been scored against a real model.
A nested `claude -p` does not inherit session credentials here, so the A/B exits 2
(`SKIPPED (infra)`), never 0. `--runner` accepts any CLI so it is not tied to one
vendor.

**2. Version gating contradicted itself in three places.** §2's STOP required
*both* broker version and client to be unknown; §4's hard rule required *both* to
be known; §8's NOT SCOREABLE row repeated the "both unknown" form. Three rules for
one decision, and all three conflated four independent facts into a single global
gate.

Replaced with a **minimum context per scored item** table: producer durability is
gated on the client library and its version (defaults are a client property — the
broker version moves neither verdict); consumer-protocol keys on `group.protocol`
or the broker version to infer it; feature availability on the broker version; and
**everything else on nothing at all**. That last row is the point — an unknown
client version blocks item 5 and nothing else, and must not be used to withhold a
partition-key or DLQ verdict. §4 and §8 now defer to the table instead of
restating it, and a per-site contract test asserts no site reinstates the global
and-gate, scoped to each passage so one correct site cannot mask two wrong ones.

**3. The coverage doc drifted from the runner.** The runner had seven gates;
`COVERAGE.md` listed five, because the generator hard-coded them. "Auto-generated"
only guarantees agreement with the generator's model of the world. The gate list
is now **parsed out of `run_regression.sh`**, a gate the generator cannot describe
is a hard error rather than an em-dash, and contract tests bind the table's row
count and labels to the runner — including a guard-the-guard test that removes an
entry and asserts the generator refuses to build.

**4. Semantic lint repositioned as a known-regression detector.** Five fresh
restatements walked through the fully green suite — the fifth surfaced while
writing an unrelated probe for the model-eval grader, which is itself the point:

```
The event history topic belongs on cleanup.policy=compact.       (KL023)
Page when consumer lag reaches ten thousand records.             (KL024)
Static membership guarantees rolling deployments will not
  rebalance the group.                                           (KL025)
Protobuf gives the highest throughput of the registry formats.   (KL026)
Set a partition key to preserve ordering — without one, records
  are spread round-robin over the partitions.                    (KL006)
```

All five now fire. KL024 gained a spelled-out-magnitude form (`ten thousand` is
the same fabricated constant as `10000`); KL023 an adjacency-preserving "belongs
on" alternative that still leaves the correct *"keep the event log on
`cleanup.policy=delete` and compact a separate snapshot topic"* untouched; KL025 a
`guarantees … will not rebalance` form with fixed-width negative lookbehinds so
the sentence *refuting* the myth is not itself flagged; KL026 a superlative form
that catches a ranking stated without naming the loser; KL006 an anaphoric form
(`key … without one … round-robin`), scoped to one clause so it cannot reach
across a sentence boundary.

The more important change is the framing. The linter docstring, the paraphrase
corpus docstring and `COVERAGE.md`'s gaps table now all say the same thing: **a
finding is real, silence is not a clearance.** 0 findings across 5 files means no
known-wrong phrasing is present, and must never be reported as evidence that the
documentation is semantically correct.

**5. SKILL.md had no headroom.** It sat at exactly 500 lines against a gate of
`<= 500` — reading skill-creator's "under 500" as a target. Now **423 lines**
(31.5 KB), budget ratcheted to 435. Two things moved, neither deleted: the six
inline anti-example bodies joined the other eleven in
`references/consumer-anti-examples.md` (now a contiguous AE-1…AE-17 catalogue,
with §7 keeping the index), and §8's three tier checklists — which were a verbatim
second copy of the §5 checklist — collapsed into a tier→item mapping. That copy
had already drifted: item 11 read PASS in §5 and WARN in §8 for the same
situation. Each §5 item now carries its tier inline, and contract tests assert the
tags and the §8 table agree and together partition all sixteen items.

**6. A TOC row described the wrong symptom.** `consumer-failure-modes.md` listed
the poison-message symptom as "lag pinned at the same offset"; the section itself
correctly says the *committed offset* stops advancing while lag climbs without
bound. Corrected to match the section.

One more finding, from mutation-testing the new work: the calibration gate
**survived** deleting the linter-penalty line entirely, because every decoy was
already separable on recall alone. Half the grader was untested by the gate that
claims to grade it. Three penalty probes now name every concept their fixture
demands — recall pinned at 1.0, so only the penalty arm can fail them — and that
mutation is killed.

Current figures: **8 gates** · 26 lint rules · 127 self-test cases · 34 mutations
(every rule covered) · 127 paraphrase probes · 21 golden fixtures · 295 pytest
tests · 17 anti-examples · SKILL.md at 423 lines. Authoritative counts are
generated into `scripts/tests/COVERAGE.md`, never hand-maintained.

**What "all 8 gates green" still does not mean.** It means the documents are
internally consistent, free of the errors the 26 rules encode, and that the
model-eval grader can tell a correct review from a confident wrong one. It does
not mean a model carrying this skill produces better answers — that number does
not exist yet, and the harness to produce it is now the only thing standing
between this report and an honest measurement.

---

## 8.9 Fifth review round — a scoring hole, and four eval limits

**1. The scorecard could pass a design carrying a Critical defect.** §8.8 made
four checklist items visible as *unscored*; it did not notice that being visible
made them a hole. `atomicity mechanism` (§5 item 8) was reviewed-but-unscored
while `KAFKA-015` grades a database write inside a Kafka transaction as
**critical**; `sensitive data` was unscored while `KAFKA-018` grades PII on a
compacted infinite-retention topic as **standard**. Both defects could be found,
written into §9, and leave the verdict PASS. Severity that cannot reach the
verdict is decoration.

Fixed generally rather than case by case — **the unscored tier is gone**. Every
§5 item now carries a weight: item 8 → Critical, item 16 (sensitive data) →
Standard, items 2 (partition count) and 17 (ownership) → Hygiene. Inapplicable
items leave through N/A, which shrinks the denominator honestly; nothing leaves
by having no tier.

Building the invariant test then exposed a second, quieter version of the same
hole: `KAFKA-014` (assignor config under `group.protocol=consumer`), `KAFKA-021`
(static membership overclaim) and `KAFKA-020` (copied lag threshold) were graded
**standard** but anchored on a Gate 1 row and a §4 hard rule — no checklist item
existed for consumer-group/rebalance configuration at all, so no scorecard item
could fail on them either. §5.3 gained **item 13, consumer group configuration
coherent with the protocol in use** (Standard), and the three fixtures were
re-anchored onto real checklist items. Tiers are now Critical 4 · Standard 7 ·
Hygiene 6 = all 17 items.

The invariant is now a gate, in both directions: every critical/standard fixture
must resolve to a §5 item that carries a tier, and every §5 item must carry one.

**2. The Quick Reference still asserted the global version gate.** It closed with
"a verdict given without knowing the broker version and client library is a
guess" — forty lines above the per-item table saying most of the checklist needs
no version at all. Rewritten to scope the matrix load to *version-sensitive*
items, with a header-scoped contract test blocking the old form.

**3. Four limits in `model_eval.py`, three fixed and one stated.**

- *Defects only.* The corpus scored 16 defect fixtures and no correct ones, which
  rewards a model that condemns everything — a measure of pessimism, not
  judgement. It now runs **defect + good_practice** and reports recall and the
  false-alarm rate separately. Recall is blind to over-flagging (condemning
  correct code names all the right concepts), so each good_practice fixture
  declares markers for the specific over-flag it invites, and calibration
  requires an over-flagging probe to trip them while the correct answer does not.
- *No references in the skilled arm.* §3 loads `version-client-matrix.md` for
  **any** config verdict even at Lite depth, so an arm holding only SKILL.md was
  measuring a workflow the skill does not prescribe. `--refs {none,matrix,all}`,
  default `matrix`; the baseline arm is unaffected by the flag, and a test
  asserts that.
- *Scores kept, responses discarded.* The JSON now carries the raw responses
  (`--no-transcripts` to opt out). A score with no response behind it cannot be
  re-graded when the grader changes, and cannot be argued with.
- *An endogenous oracle.* `expected_feedback`, `coverage_rules` and the linter
  rules were written by the same effort that wrote the skill, so a high score
  means "the model reproduces what this project believes", not "the model is
  right". Not fixable from inside; now stated in the module docstring rather than
  implied. Calibration proves separation *within* that belief system and nothing
  beyond it.

**4. A bug found while fixing the above.** `ask()` graded any subprocess that
printed to stdout, whatever its exit code. A runner emitting a usage banner or a
partial answer and exiting 1 would have been scored as a bad review — and a low
score is exactly the result that gets investigated as model behaviour. Nonzero
exit is now infra (exit 2), like an empty answer already was.

Three mutations confirm the new guards fail when they should: deleting the
false-alarm check, restoring the exit-code bug, and emptying the `matrix`
reference set are each killed.

**5. A false positive in KL025, caused by the fix in item 1.** The new checklist
item states the bound correctly — "static membership *only avoids* a rebalance
for a restart inside `session.timeout.ms`" — and the rule flagged it, because its
exemption only spared a *trailing* "only" (`avoids a rebalance only if…`). A
guard that forbids the accurate sentence is a defect. Fixed with a lookbehind and
probed from both positions.

Current figures: **8 gates** · 26 lint rules · 128 self-test cases · 34 mutations
· 128 paraphrase probes · 21 golden fixtures · 331 pytest tests · 17 checklist
items, all scored · 17 anti-examples · SKILL.md at 424 lines.

**Status, stated without hedging.** Engineering remediation across five review
rounds is complete. The empirical measurement it was built for has still not been
run: no A/B against a real model, no trigger recall/precision, no live-broker
matrix. Everything green today is a statement about the documents and about the
tooling that checks them.

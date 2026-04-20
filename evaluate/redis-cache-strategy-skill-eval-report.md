# redis-cache-strategy Skill Evaluation Report

> **Method**: skill-creator A/B testing
> **Date**: 2026-04-18
> **Subject**: `skills/redis-cache-strategy/` — Redis caching strategy design and review skill

---

Redis cache safety rules enjoy exceptionally high training coverage in the base model, and baseline quality in this evaluation reached 89.6%. The skill's core value manifests in two dimensions: **framework reference consistency** (AE number cross-referencing, explicit Gate analysis) and **token efficiency** (an average of 49.7% savings across three scenarios — the most stable efficiency advantage of any skill evaluated to date).

---

## §1 Skill Overview

**Core components**:

| File | Lines | Purpose |
|------|-------|---------|
| `SKILL.md` | 341 | Main framework: 4 Gates, 3 depth levels, 14-item checklist, 12-item scorecard, 9-section output contract |
| `references/cache-patterns.md` | 211 | Standard/Deep: 4 write patterns (cache-aside / write-through / write-behind / dual-write) with code examples |
| `references/cache-failure-modes.md` | 260 | Deep: defenses against 4 failure modes (stampede / penetration / avalanche / hot key) with Go code |
| `references/cache-anti-examples.md` | 142 | Extended anti-examples AE-7 through AE-13 |

**Key safety rules enforced by the skill**:
- AE-1: `TTL=0` (immortal key) → data never expires
- AE-2: write-behind without a durable queue → data loss on process crash
- AE-3: cache-aside without singleflight → stampede breaks through to DB
- AE-5: distributed lock without TTL or token check → deadlock + lock theft
- GUARDRAIL: write-behind is **prohibited** for financial / audit-critical data

---

## §2 Test Design

### 2.1 Scenario Definitions

| # | Scenario | Business Context | Core Challenge | Expected Result |
|---|----------|-----------------|---------------|-----------------|
| S1 | Cache-Aside Three Defects | Redis 7.0, 50K QPS, e-commerce product catalog | TTL=0 + no stampede protection + no degradation path | Identify 3 Critical issues; Scorecard 0/3 |
| S2 | Distributed Lock + Write-Behind | Redis 6.2 Sentinel, 5K orders/min, financial data | Lock missing TTL/token check + write-behind fire-and-forget | Identify GUARDRAIL violation; recommend write-through |
| S3 | Minimal Context (Degraded Mode) | Version / deployment / consistency SLA all unknown | Code snippet only, no architectural background | Minimal mode; consistency SLA undefined |

### 2.2 Assertion Matrix (24 assertions)

**Scenario S1 — Cache-Aside Defects (9 assertions)**

| ID | Assertion | With Skill | Without Skill |
|----|-----------|:----------:|:-------------:|
| A1 | Identifies `TTL=0` (immortal key) as a Critical defect (AE-1) | PASS | PASS |
| A2 | Identifies missing singleflight / stampede protection as high risk | PASS | PASS |
| A3 | Identifies missing cache-down degradation path as Critical (implicit DB fallback without rate limiting is unacceptable) | PASS | PASS |
| A4 | Recommends TTL with jitter (±10–20%) to prevent synchronised avalanche expiry | PASS | PASS |
| A5 | Provides singleflight code solution to resolve stampede | PASS | PASS |
| A6 | Identifies unconfigured eviction policy (default `noeviction` → all SET commands error after 8 GB) | PASS | PASS |
| A7 | Original code Scorecard: Critical **0/3** (TTL / consistency / degradation all FAIL) | PASS | PASS |
| A8 | `§9.9` uses the required 4-column table (Area \| Reason \| Impact \| Follow-up) | PASS | PASS |
| A9 | Explicitly references anti-example numbers (AE-1, AE-3, etc.) for cross-referencing | PASS | **FAIL** |

**S1 summary**: With Skill 9/9, Without Skill 8/9 (lost point: AE number references absent)

---

**Scenario S2 — Distributed Lock + Write-Behind (9 assertions)**

| ID | Assertion | With Skill | Without Skill |
|----|-----------|:----------:|:-------------:|
| B1 | Identifies lock TTL=0 as deadlock risk (lock never released after holder crash) | PASS | PASS |
| B2 | Identifies DEL without token check as lock theft risk (race window deletes another holder's lock) | PASS | PASS |
| B3 | Provides Lua CAS safe-release script (atomic GET-compare-DEL) | PASS | PASS |
| B4 | Identifies write-behind fire-and-forget as a GUARDRAIL violation for financial data | PASS | PASS |
| B5 | Recommends write-through (synchronous DB-first write; cache as optional non-critical write) | PASS | PASS |
| B6 | Original code Scorecard: Critical **0/3** (consistency / TTL / degradation all FAIL) | PASS | PASS |
| B7 | `§9.9` includes `SaveOrder` idempotency risk (retries may produce duplicate financial records) | PASS | PASS |
| B8 | `§9.9` uses the required 4-column table (Area \| Reason \| Impact \| Follow-up) | PASS | PASS |
| B9 | Gate framework explicit analysis (Gate 1–4 each declared PROCEED/STOP) | PASS | **FAIL** |

**S2 summary**: With Skill 9/9, Without Skill 8/9 (lost point: explicit Gate analysis absent)

---

**Scenario S3 — Minimal Context / Degraded Mode (6 assertions)**

| ID | Assertion | With Skill | Without Skill |
|----|-----------|:----------:|:-------------:|
| C1 | Declares Minimal/Degraded Mode + `Data basis: minimal` annotation | PASS | PASS |
| C2 | `§9.9` includes "consistency SLA undefined" as a Critical risk item | PASS | PASS |
| C3 | `§9.9` uses the required 4-column table (Area \| Reason \| Impact \| Follow-up) | PASS | PASS |
| C4 | Distinguishes `redis.Nil` (cache miss) from Redis connection errors (`err != nil`) | PASS | PASS |
| C5 | Does not claim the strategy is "consistent"; explicitly states the staleness window is unknown | PASS | PASS |
| C6 | `§9.x` section numbers use the canonical `§` prefix format (e.g., `§9.1 Context Gate`) | PASS | **PARTIAL** |

**S3 summary**: With Skill 6/6, Without Skill 5.5/6 (PARTIAL: `§` prefix format not consistently applied)

---

## §3 Pass Rate Summary

### 3.1 Overall Assertion Pass Rate

| Configuration | PASS | PARTIAL | FAIL | Strict Pass Rate |
|---------------|------|---------|------|-----------------|
| **With Skill** | **24/24** | 0 | 0 | **100%** |
| Without Skill | 21/24 | 1 | 2 | 87.5% + 4.2% partial |

**Delta: +10.4 percentage points (strict PASS basis)**

### 3.2 Pass Rate by Scenario

| Scenario | With Skill | Without Skill | Failed Assertion |
|----------|:----------:|:-------------:|-----------------|
| S1 Cache-Aside | 9/9 (100%) | 8/9 (88.9%) | A9: AE number references |
| S2 Lock + Write-Behind | 9/9 (100%) | 8/9 (88.9%) | B9: Gate framework analysis |
| S3 Minimal Context | 6/6 (100%) | 5.5/6 (91.7%) | C6: §9.x section number format |

**Pattern**: All three lost points belong to a single category — **framework reference consistency** (AE numbers, Gate declarations, `§` prefix). Core safety knowledge (TTL jitter, singleflight, Lua CAS, write-behind guardrail) scored 100% in both groups. This indicates that Redis cache safety rules are deeply embedded in the base model; the skill's value lies in **reference traceability** and **token efficiency**, not knowledge transfer.

---

## §4 Key Difference Analysis

### 4.1 Behaviors Exclusive to With-Skill

| Behavior | Scenario | Source |
|----------|---------|--------|
| Anti-example number cross-references (AE-1, AE-3, AE-5) | S1, S2 | §7 Anti-Examples framework |
| Gate 1–4 explicit PROCEED/STOP declarations | S1, S2 | §2 Mandatory Gates |
| Canonical `§9.x` section number prefix | S1, S2, S3 | §9 Output Contract |
| `§9.3` prescribed column names (Component \| Pattern \| Risk \| Notes) | S1, S2 | §9.3 format spec |
| `Data basis` annotation appended after Scorecard | S1, S2, S3 | §8 Scorecard contract |

### 4.2 Core Technical Knowledge Comparison

All critical Redis safety checks were correctly identified by both groups:

| Check | With Skill | Without Skill |
|-------|:----------:|:-------------:|
| TTL=0 (immortal key) severity | PASS | PASS |
| Singleflight resolves stampede | PASS | PASS |
| `noeviction` policy danger | PASS | PASS |
| Write-behind GUARDRAIL for financial data | PASS | PASS |
| Lua CAS distributed lock safe release | PASS | PASS |
| Penetration (null-value caching) | PASS | PASS |
| §9.9 Uncovered Risks 4-column table | PASS | PASS |

**Conclusion**: Redis cache safety knowledge is one of the most thoroughly trained domains in the base model. The skill adds no extra value in **technical content**, but provides measurable advantages in **framework consistency** and **token efficiency**.

### 4.3 Baseline Comparison Across Skills

| Skill | Baseline Pass Rate | With-Skill Pass Rate | Delta |
|-------|:-----------------:|:-------------------:|:-----:|
| mysql-migration | 52% | 100% | +48 pp (primarily knowledge injection) |
| pg-migration | 87% | 100% | +13 pp |
| mongo-migration | 87.5% | 100% | +12.5 pp |
| **redis-cache-strategy** | **89.6%** | **100%** | **+10.4 pp** (primarily structural enforcement) |

**Trend**: As domain knowledge matures in the base model, the skill's delta narrows and its value shifts from knowledge delivery to structural constraint. redis-cache-strategy represents the extreme end of this trend — the skill contributes almost no new knowledge but provides a consistent 49.7% token saving.

---

## §5 Token Cost Analysis

### 5.1 Skill Context Token Cost

| Component | Lines | Estimated Tokens | Load Trigger |
|-----------|-------|-----------------|--------------|
| `SKILL.md` | 341 | ~4,400 | Every invocation |
| `cache-patterns.md` | 211 | ~2,700 | Standard / Deep |
| `cache-failure-modes.md` | 260 | ~3,300 | Deep / stampede signal |

### 5.2 Actual Token Consumption

| Agent | Scenario | Total Tokens | Tool Calls | Output Mode |
|-------|----------|:------------:|:----------:|-------------|
| Without Skill | S1 | 36,546 | 3 | Exploratory reasoning + web search |
| With Skill | S1 | **19,004** | 0 | Structured framework output |
| Without Skill | S2 | 37,096 | 3 | Exploratory reasoning + web search |
| With Skill | S2 | **18,712** | 0 | Structured framework output |
| Without Skill | S3 | 36,028 | 3 | Exploratory reasoning + web search |
| With Skill | S3 | **17,415** | 0 | Structured framework output |

### 5.3 Cost-Efficiency Metrics

| Metric | S1 | S2 | S3 | **Average** |
|--------|:--:|:--:|:--:|:-----------:|
| Without Skill tokens | 36,546 | 37,096 | 36,028 | 36,557 |
| With Skill tokens | 19,004 | 18,712 | 17,415 | **18,377** |
| Token savings | **−48.0%** | **−49.6%** | **−51.7%** | **−49.7%** |
| Quality improvement | +11.1 pp | +11.1 pp | +8.3 pp | +10.4 pp |

**Structural finding**: Token savings are exceptionally consistent across all three scenarios (variance ±2%), with no S3 anomaly (contrast: mongo-migration S3 ran +15% over baseline). The reason: redis-cache-strategy's §3 Depth Selection correctly handles minimal context — unknown scale does **not** trigger Deep depth; the skill stays at Standard depth with conservative assumptions, avoiding unnecessary reference file loading.

**Without-Skill tool call breakdown**: Each scenario incurred 3 tool calls (likely web searches for Redis docs / Go code examples). This not only inflated token consumption but introduced network dependency and non-determinism. The With-Skill group inlines all knowledge, resulting in zero tool calls and more stable responses.

---

## §6 Weighted Scores

### 6.1 Dimension Scores (5-point scale)

| Dimension | With Skill | Without Skill | Delta |
|-----------|:----------:|:-------------:|:-----:|
| Critical defect identification completeness | 5.0 | 5.0 | 0.0 |
| Anti-pattern framework reference quality | 5.0 | 3.0 | **+2.0** |
| Output structure conformance (§9 contract) | 5.0 | 4.0 | +1.0 |
| Implementation solution quality (code / TTL / Lua) | 5.0 | 4.5 | +0.5 |
| Degradation and monitoring design | 5.0 | 4.5 | +0.5 |
| Domain-specific guardrail enforcement | 5.0 | 4.5 | +0.5 |

### 6.2 Weighted Total Score (out of 10)

| Dimension | Weight | With Skill | Without Skill | Notes |
|-----------|:------:|:----------:|:-------------:|-------|
| Critical defect identification | 25% | 10.0/10 | 10.0/10 | Both groups identified all critical safety issues at 100% |
| Anti-pattern framework references | 20% | 10.0/10 | 6.0/10 | With Skill explicitly cites AE-1/AE-3/AE-5; Without Skill describes problems without numbering |
| Output structure conformance | 20% | 10.0/10 | 8.0/10 | §9 structure present in both; With Skill guarantees §9.x prefix, Gate declarations, and column names |
| Implementation solution quality | 15% | 10.0/10 | 9.0/10 | Both provide Lua CAS / singleflight; With Skill is more systematic (includes dual-write debounce) |
| Degradation and monitoring design | 10% | 10.0/10 | 9.0/10 | Both include complete §9.7/§9.8; With Skill is more structured (tables vs. prose) |
| Domain guardrail enforcement | 10% | 10.0/10 | 9.0/10 | Both identify write-behind GUARDRAIL; With Skill explicitly labels it as GUARDRAIL VIOLATION |
| **Weighted total** | **100%** | **10.00/10** | **8.45/10** | — |

---

## §7 Findings and Recommendations

### Finding 1: redis-cache-strategy has the strongest baseline of any skill evaluated

A baseline of 89.6% indicates that Redis cache safety rules (singleflight, TTL jitter, Lua CAS, write-behind prohibition) have become built-in knowledge in the base model. This stands in sharp contrast to mysql-migration (52% baseline), where the skill's primary value was knowledge injection. For redis-cache-strategy, value comes almost entirely from **structural constraint**, not knowledge delivery.

**Implication for skill design**: In mature, well-covered domains, skills should focus more on output structure standardisation (§9 contract, AE numbering, Gate framework) and less on knowledge documentation.

### Finding 2: Token efficiency is the most consistent differentiator (−49.7%)

All three scenarios consistently saved approximately 50% in tokens, with no anomalous outliers (contrast: mongo-migration S3). This stability comes from two factors:
- **With Skill**: Framework guidance drives direct structured output generation — 0 tool calls
- **Without Skill**: Exploratory reasoning + 3 web searches per scenario — more output but with duplication

For high-frequency Redis cache reviews (e.g., PR review in CI/CD), running 100 scenarios per month under this skill yields roughly 50% token savings, translating to approximately 2× cost efficiency.

### Finding 3: S3 Minimal Context shows no anomaly — Depth Selection trigger logic is correct

Under minimal context (version / scale / SLA unknown), redis-cache-strategy correctly selects Standard depth rather than Deep, avoiding the token overrun seen in mongo-migration's S3 due to a Deep depth trigger. This validates the conservative trigger design in §3 Depth Selection.

### Finding 4: §9.9 table format is already widely adopted at baseline

As observed in previous evaluations, the Without-Skill group spontaneously used the `| Area | Reason | Impact | Follow-up |` 4-column format. This format appears to have become the base model's default output pattern, likely due to training data coverage from skill documentation.

**Recommendation**: Given that the format is already broadly covered, skill maintenance should focus on **rules that are harder for the baseline to execute correctly**:
1. Pattern Selection Matrix for complex scenarios (e.g., mixed read/write ratio pattern selection)
2. Isolation design for multi-service shared caches
3. Distinguishing Redlock from single-node lock applicability

---

## §8 Conclusion

**redis-cache-strategy is rated production-ready and recommended for all Redis caching layer design and review workflows.**

**Core value propositions**:
1. **Token efficiency lead**: Average savings of 49.7% across three scenarios — the most stable efficiency advantage of any evaluated skill; well-suited for high-frequency CI/PR workflows
2. **Traceable framework references**: AE numbers, Gate declarations, and `§9.x` prefix ensure every review can be traced back to the governing specification
3. **Zero web-search dependency**: Inlined knowledge means the With-Skill group requires no external tool calls, providing a clear advantage in network-constrained or latency-sensitive environments

**Improvement recommendations**:
1. Add a golden fixture for multi-service shared cache scenarios (CACHE-015), covering tenant isolation and keyspace separation
2. Add AE-14 (Lua script atomicity loss under Redis Cluster) to §7 Anti-Examples, addressing a common misconception in cluster deployments
3. Consider making the Minimal context depth rule explicit in §4 Degradation Modes: state that unknown scale does not trigger Deep depth (currently implicit — recommend making it explicit)

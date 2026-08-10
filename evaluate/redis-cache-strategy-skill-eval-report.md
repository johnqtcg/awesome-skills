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

---

## §9 Remediation Round — 2026-08-10

> §1–§7 above record the 2026-04-18 A/B run and are **superseded as a quality
> claim**: they were produced before the scorecard defect in §9.1 was known, and
> a run that could report PASS while finding a Critical defect cannot certify
> the skill it measured. They are retained as the historical baseline.

### 9.1 The finding that mattered: the scorecard could not act on the checklist

§5 listed 14 checklist items and §8 scored a **different** 14. The two lists had
drifted apart, and three `critical` golden fixtures mapped only into the
Standard tier, which tolerates one failure:

| Fixture | Defect | Scored under | Consequence |
|---------|--------|--------------|-------------|
| CACHE-012 | Write-behind for financial data, fire-and-forget goroutine | "pattern matches business scenario" (Standard) | Reviewer finds it, reports it Critical, prints PASS |
| CACHE-014 | Multi-tenant key with no tenant scope — cross-tenant read | "key naming convention" (Standard) | An authorization bypass graded as a naming nit |
| CACHE-017 | Correctness lock with no fencing token | "distributed locks" (Standard) | Duplicate payment execution scored as a partial pass |

§8's tiers also had no vocabulary for the cases that actually occur: no `N/A`,
no `NOT SCOREABLE`, no statement of whether `WARN` counts as a pass, and a fixed
`/14` denominator that forced either a false FAIL for an absent lock or a
fabricated pass.

**Resolution.** §8 no longer defines items. §5 is the single list, its items
carry tier IDs (`C1–C9`, `S1–S7`, `H1–H5`), and §8 states only how those IDs are
counted. The three fixtures above now map to `C6`, `C7`, and `C9` — all
Critical, all blocking. The scoring vocabulary is defined where the items are:
PASS / WARN / FAIL / N/A / NOT SCOREABLE, with a dynamic denominator, `WARN`
explicitly failing the Critical tier, and a third verdict — **INCOMPLETE** —
for the case that previously had nowhere to go: a Critical item that could not
be evaluated. "We could not check it" is never a pass.

Three mechanisms hold this in place, so it cannot silently drift back:

- `RC010` (lint) — §5's IDs must be contiguous per tier and exactly covered by
  §8's declared ranges; §8 must contain no checklist of its own.
- `RC014` (lint) — §5 must define all five verdicts and must state that silence
  is FAIL, not N/A.
- `TestScorecardReachability` (pytest) — every fixture declares the §5 IDs it
  violates, and a `critical` fixture whose worst item sits below the Critical
  tier is a test failure. `M15` mutates CACHE-014 back to `H1` and is killed.

### 9.2 Version model

Gate 1 previously offered `6.x / 7.x` and defaulted to **6.0** when unknown. As
of 2026-08 the current release is **8.10** (2026-07-29), with 8.0 / 8.2 / 8.4 /
8.6 / 8.8 all GA, and 6.2 / 7.2 / 7.4 still receiving patches. The stale default
was wrong in both directions — inventing constraints that no longer apply, and
hiding primitives that are now the better answer.

The version is now gated **per conclusion**, not globally, and seven concrete
conclusions are enumerated with what changes at each boundary. `RC015` (lint)
requires every version-gated feature name to carry its version where it appears.
`references/redis-version-matrix.md` documents each release, the branch to take
when the version is unknown, and how each claim was verified.

All version facts were taken from primary sources — `src/commands/*.json`
(`since`, and `SET`'s `history` array), `src/config.c`
(`maxmemory_policy_enum[]`, the listpack/ziplist config aliases), and the GitHub
release bodies — not from recollection. The four that change a recommendation
this skill gives: `DELEX … IFEQ` / `SET … IFEQ` (8.4) replace the Lua CAS lock
release and enable a version-guarded cache write; `HOTKEYS` (8.6) replaces
client-side hot-key estimation; the bundled cuckoo filter `CF.*` (8.0) makes the
penetration filter deletable; compact hashes (8.10) change the Hash-vs-String
memory arithmetic.

### 9.3 Technical corrections

| Area | Was | Now |
|------|-----|-----|
| Write-through read path | "always fresh since writes update cache" — contradicting the section three paragraphs below that explains why it is not | Read-your-writes on the happy path, with the contradiction removed at source; `RC017` fires on any absolute freshness claim not qualified **on the same line** |
| Cluster fencing example | Lock key and fence counter in one Lua script, different hash slots | Shared hash tag via `fenceKeysFor`, plus the fence counter's durability and failover-monotonicity failure modes and three ways to handle them |
| Delayed double-delete | Fixed 100ms–1s, "via delayed job, or sleep in goroutine" | Derived from p99.9 DB read + populate + queue latency, with the in-process sleep explicitly rejected as the same defect as AE-2; `RC016` enforces it |
| Reference navigation | No TOC on any reference (440-line failure-modes file) | TOC on all five, asserted against real headings with GitHub's anchor algorithm — a drifted TOC now fails `M24` |

### 9.4 Gate defects found while fixing the above

Two were not in the review and are worth recording because both were making the
suite report more confidence than it had:

1. **The Go gate returned 1 unconditionally in a sandbox.** An unwritable build
   cache produced `go: failed to trim cache: … operation not permitted` with
   every package built successfully. The gate reported FAIL, and — worse — the
   mutation sweep credited *every* mutation to "killed by go", because the go
   gate returned 1 no matter what the mutation did. The previous "12/12 killed"
   was therefore partly an artifact. The gate now compiles a known-good package
   first, falls back to a private `GOCACHE`, and classifies a non-zero exit with
   no compiler diagnostic as INCOMPLETE (exit 3) rather than as a broken
   snippet. With that fixed, one mutation (`M20`) was immediately exposed as
   surviving.
2. **`test_verdict_format` was vacuous.** `assert "X/12" in SKILL_MD or
   "PASS/FAIL" in SKILL_MD` passed on the second clause, so the `X/12` half had
   been stale through two renumberings without ever going red. Every scorecard
   assertion now parses a structure and checks a value.

`COVERAGE.md` also under-reported itself: the gate table was hardcoded at six
rows while the runner ran seven, and the Go-gate file list was scraped with a
regex that stopped at the first `]`, claiming coverage of `SKILL.md` alone when
the gate has always scanned every reference. Both are now derived — the gate
table is parsed from `run_regression.sh`, and the file list is imported from the
gate module.

### 9.5 Empirical closure — what is and is not measured

The review's strongest point was that automated verification proved the
*documents* were self-consistent and never observed a model. Two harnesses now
exist:

- **`model_eval.py`** — A/B over the 15 defect + good_practice fixtures: arm A
  is the code alone, arm B adds SKILL.md and the references §10 prescribes. The
  grader is deterministic, never an LLM, and scores five declared axes: concept
  recall, §5 item-ID citation, verdict correctness, false alarms on
  good-practice code, and repetition of claims the skill declares wrong
  (clause-scoped, so quoting a myth in order to reject it scores clean).
- **`trigger_eval.py`** — routing recall and precision over 15 positive and 12
  negative prompts, the negatives being real Redis questions that reuse the
  description's vocabulary while landing in areas §1 and Gate 2 delegate
  elsewhere.

Both are self-checking offline, and those checks are regression gates 6 and 7.
`--calibrate` runs 60 axis probes: for each fixture and each applicable axis, a
decoy response that should move **only** that axis. It caught two real grader
defects on first run — the `items` axis was a duplicate of `recall` because of a
title-keyword fallback, and the false-alarm axis overlapped the verdict axis via
a shared `Verdict: FAIL` probe. Both were fixed; a grader whose axes move
together reports health with a mechanism deleted.

**What has not been measured, stated plainly:** the A/B run itself did not
execute. The nested CLI in this environment is unauthenticated, so both
harnesses exit 3 (INCOMPLETE) with the reason printed. Verified here is the
apparatus — flag parsing, prompt delivery over stdin (argv failed: the variadic
`--disallowed-tools` swallowed the prompt, and arm B's prompt is tens of
kilobytes), the runner preflight, the exit-3 path, and the calibrated grader.
**The A/B result is outstanding and no score in this report should be read as
including it.**

### 9.6 State after this round

| | Before | After |
|---|--------|-------|
| Regression gates | 7 | 9 |
| Lint rules | 13 | 17 |
| Mutations | 12 (with a broken go gate inflating the kill count) | 24, all killed by the expected gate |
| Collected tests | 232 | 291 |
| Scored checklist items | 14 in §5, a different 14 in §8 | 21, one list, tier-tagged |
| Verdicts | PASS / FAIL | PASS / FAIL / INCOMPLETE, with N/A and NOT SCOREABLE and a dynamic denominator |
| Redis versions covered | 6.x / 7.x, default 6.0 | 6.2 → 8.10, per-conclusion gating, no default |
| References | 4, no TOC | 5, all with an asserted TOC |
| SKILL.md | 389 lines | 439 (budget raised 420 → 440, paid for by moving AE-1…AE-6 to the reference and deleting §8's duplicate list) |

Remaining, in priority order: run the A/B and trigger evaluations against an
authenticated model and record the numbers here; add fixtures for the nine §5
items that have none (`C1`, `S1`, `S5`, `S6`, `H1`–`H5` — the list is derived in
`COVERAGE.md §4`, not hand-maintained); and validate the version matrix against
live 7.2 / 7.4 / 8.10 servers rather than against the source tree alone.

---

## §10 Remediation Round 2 — 2026-08-10 (same day, second review)

A second review found five issues. Three were in machinery added earlier the
same day, which is the useful part of the finding: the gates were new, and new
gates are exactly where an unearned green comes from.

### 10.1 The mutation sweep could still report a kill count it had not earned

Two holes, both about *credibility of the number* rather than the mutations:

- **No baseline requirement.** The sweep only refused to run when the go gate
  returned 3. If any gate was already red on the unmutated tree, every mutation
  would be "killed" by that same failing gate and the sweep would print a full
  score. Now all three gates must return 0 before a single mutation is applied;
  a 3 is INCOMPLETE, a 1 says so and stops.
- **Kill attribution was advisory.** A mutation caught by a gate other than its
  declared killer printed `(expected lint)` and still counted as killed — so a
  dead lint rule whose mutation happened to break the build would never surface.
  A mismatch is now a `MISKILLED` result and fails the sweep.

Both were verified by probe: breaking the baseline makes the sweep refuse
without printing a count, and re-declaring one mutation's killer produces
`MISKILLED M21 [killed by lint, expected go]` and exit 1.

### 10.2 The Go positive control did not cover the path that actually failed

The probe compiled a dependency-free package. The failure it was written for
occurs during module resolution, so the probe could pass while the real build
failed for the same environmental reason — and, worse, Go's cache trim is
**periodic, not per-invocation**: it records the last attempt in `trim.txt` and
retries only after an interval. Re-running the old probe three times in a row
now returns 0 every time, so the conditional fallback fired only sometimes. An
intermittent fallback is worse than none, because the INCOMPLETE it produces is
irreproducible.

Fixed at the cause rather than the symptom: the gate now owns a **private,
persistent `GOCACHE`** unconditionally (stable path, so it stays warm — 7.5s
cold, 0.5s warm), and the probe imports `github.com/redis/go-redis/v9` and runs
`go mod tidy`, so it exercises module resolution too. `GOMODCACHE` is
deliberately left shared; it is the build cache's trim step that needs write
access.

### 10.3 `OVERWRITTEN` was placed in the wrong reliability tier — a real error introduced by round 1

§5 C2 listed keyspace `OVERWRITTEN` (8.2+) beside CDC as an equivalent
event-driven invalidation mechanism. It is not equivalent, and the Redis
documentation is explicit on both counts:

- Pub/Sub is *fire and forget* — "if your Pub/Sub client disconnects, and
  reconnects later, all the events delivered during the time the client was
  disconnected are lost." Silent, unbounded loss of invalidations.
- In a cluster, "every node … generates events about its own subset of the
  keyspace" and those notifications "**are not** broadcasted to all nodes" — a
  listener must subscribe to every node, and resharding changes ownership.

A third problem is structural rather than documented: the event says a *Redis
key* changed, not that a *database row* did. When the DB commits and the cache
write is the step that failed, no event is emitted at all — the exact case C3
exists for.

C2 now requires an *authoritative* mechanism (TTL, explicit invalidation, or a
durable stream: CDC / outbox) and states that keyspace notifications do not
count, with their legitimate use — best-effort L2→L1 invalidation behind a TTL
floor — named. `RC018` fires whenever a keyspace notification appears near a
durable mechanism without a fire-and-forget / best-effort qualifier, and `M26`
reverts C2 to the defective sentence and is killed.

### 10.4 Gate 1 prose contradicted Gate 1's own table

The paragraph still read "the other five have defaults whose wrongness shows up
as a tuning problem" after round 1 had made version un-defaultable, `maxmemory`
ask-only, and deployment mode correctness-relevant for locks and multi-key
scripts. Corrected: only read:write ratio and peak QPS degrade to tuning; each
of the other three is named with the reason its default is not safe.

### 10.5 The missing A/B result is now enforced, not promised

The run still has not happened — the nested CLI is unauthenticated, and both
harnesses exit 3 INCOMPLETE with the reason printed. What changed is that the
gap is no longer held by a sentence anyone can delete.
`TestEvalResultsAreNotClaimedWithoutData` binds the claim to the evidence in
both directions:

- a result-shaped claim in either language's report, with no
  `model_eval_last_run.json` / `trigger_eval_last_run.json` on disk, **fails**;
- once an artifact exists, a report that reports no numbers **fails** as behind
  the evidence;
- while both artifacts are absent, both reports must state that the run did not
  happen.

All three were probe-verified, including the fabricated-number case. This does
not substitute for the measurement — it guarantees the report cannot drift away
from whatever the measurement did or did not produce.

### 10.6 State after round 2

| | After round 1 | After round 2 |
|---|---|---|
| Lint rules | 17 | 18 (`RC018`) |
| Mutations | 24 | 25, all killed **by the declared gate** |
| Collected tests | 291 | 294 (2 skipped: the eval artifacts do not exist yet) |
| Mutation sweep credibility | kill count only | baseline-green required; wrong-gate kills fail |
| Go gate | private `GOCACHE` on fallback, dep-free probe | private `GOCACHE` always, probe resolves modules |
| Keyspace notifications | listed beside CDC | separate tier, with `RC018` holding the line |

Still open, unchanged and unhidden: the A/B and trigger runs themselves, fixtures
for the nine §5 items that have none, and validation of the version matrix
against live 7.2 / 7.4 / 8.10 servers.

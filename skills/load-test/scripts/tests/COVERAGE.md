# load-test Skill — Test Coverage Matrix

Coverage matrix for the load-test skill regression test suite. The suite is
zero-LLM and has four layers: (1) structure + golden-fixture integrity
(`test_skill_contract.py`, `test_golden_scenarios.py`) validate SKILL.md
structure and fixture classification, not model behavior; (2) static
behavioral k6 checks (`test_k6_scripts_valid.py`) validate the reference
scripts (import completeness, Rate-metric semantics, memory/composition
regressions) and run `k6 inspect` when k6 is installed; (3) two real `k6 run`
executions against a local HTTP stub (`RealK6RunTests`, skipped without k6)
that actually execute `default()`; (4) `test_outputexample.py` — syntax,
`k6 inspect`, a real (rate/VU-shrunk, threshold-stripped) `k6 run`, and
cross-file consistency checks against `outputexample/load-test/`, the
skill's own published Write/Analyze-mode output. Layer (4) exists because
three separate review rounds each found a fresh defect in that directory
(impossible throughput, a 10x error-threshold mismatch, a wrong technical
claim, an unearned Hygiene score) that no test caught — it wasn't in the
suite's scope at all until 2026-07-23. A fourth round then found a
methodology error *inside* layer (4) itself: the memory-budget writeup
summed each scenario's VU pool as if they ran concurrently and undercounted
k6's built-in Trend metrics, both from reasoning about the script's config
text instead of asking k6 directly. `K6ExecutionRequirementsTests` fixes
this the same way as the rest of layer (4) — by checking the doc's claims
against `k6 inspect --execution-requirements`'s actual output, not by
trusting arithmetic performed by hand (by a model or a human) over config.

**What this suite does NOT validate — read before trusting "100% coverage"
below.** A 2026-07-22 review found five defects (a duplicate Trend metric, a
Gauge fed by a VU id, a VU-sizing formula that only holds for
one-request-no-sleep scripts, a CI example contradicting the skill's own
memory guidance, and a "breakpoint" composition missing its breakpoint
scenario) — none of which any existing test caught, because every test here
checked *presence* of a keyword, section, or fixture field, not *correctness*
of the example content or *consistency* between two places describing the
same thing. `k6 inspect` parses a script's init context; it does not execute
`default()`, so runtime-only errors (undefined variables reached only inside
the handler, wrong metric semantics) passed silently — this is exactly how
the §7 Custom Metrics example shipped a dangling `payload` reference for a
release. All five are now covered by targeted content assertions
(`MemoryHygieneAndCompositionRegressionTests`, below) written *after* the
fact as regression guards for the specific bugs found, plus two real `k6
run` executions (`RealK6RunTests`) that exercise `default()` against a live
local server for the §7 and §6 scripts specifically. Neither closes the general gap: the
content assertions guard known failure *shapes*, not new ones, and the real
runs cover two scripts (§6, §7), not every reference example — most scripts
still only get static analysis.

## Contract Tests (`test_skill_contract.py`)

| Test Class | Tests | Validates |
|------------|:-----:|-----------|
| `TestFrontmatter` | 3 | name=load-test; description trigger keywords (k6, vegeta, wrk, SLO, bottleneck, latency, throughput); allowed-tools present |
| `TestMandatoryGates` | 6 | §2 section exists; Gate 1-4 content; STOP semantics (>= 3 occurrences); Write/Review/Analyze modes |
| `TestDepthSelection` | 5 | Lite/Standard/Deep headings; Standard is default; Force Standard/Deep conditions; reference loading mentions all 3 files |
| `TestDegradationModes` | 5 | 5 modes (Full/Script/Partial/Analysis/Planning); Can Deliver/Cannot Claim columns; fabrication prohibition; degraded marker |
| `TestLoadTestChecklist` | 6 | 4 subsections (5.1-5.4); SLO/script/analysis/environment items; >= 18 numbered checklist items (19 present) |
| `TestScenarioAndToolSelection` | 4 | k6/vegeta/wrk table; default to k6; 6 scenario types (Smoke/Load/Stress/Breakpoint/Soak/Spike); goal mapping |
| `TestAntiExamples` | 8 | AE-1 through AE-6 verified by title (8 AEs total in §7); >= 6 WRONG/RIGHT pairs |
| `TestScorecard` | 6 | §8 exists; Critical tier (3 items); Standard tier (5 items); Hygiene tier (5 items); passing criteria; verdict format |
| `TestOutputContract` | 12 | §9.1-9.9 exist; each section has expected content; volume rules; scorecard appended; uncovered risks mandatory |
| `TestReferenceFiles` | 9 | 3 files exist; SKILL.md references them; k6 executor types; thresholds; vegeta attack/report/pipeline; analysis percentile/saturation/bottleneck; SLO verdicts |
| `TestLineCount` | 1 | SKILL.md <= 500 lines |
| `TestCrossFileConsistency` | 10 | Shared terms (p99, percentile, SLO, warmup, saturation, bottleneck) across SKILL.md + refs; dropped_iterations; min lines per reference (k6>=400, vegeta>=200, analysis>=250) |

**Contract test count: 75**

## Behavioral k6 Script Tests (`test_k6_scripts_valid.py`)

| Test Class | Tests | Validates |
|------------|:-----:|-----------|
| `ImportCompletenessTests` | 2 | every complete reference script found (>=5); every used k6 module (`k6/http`, `k6/data`, `k6/metrics`, `k6`) is imported — catches copy-paste `ReferenceError`s that `k6 inspect` cannot |
| `MemoryHygieneAndCompositionRegressionTests` | 4 | no Gauge fed by `__VU` (records a VU id, not a concurrency count — §7); §1 canonical skeleton has no Trend duplicating `http_req_duration` (§11.3); §10 CI example doesn't use `--out csv`/`--out json` (§11.2); §9's "breakpoint" composition actually defines a `ramping-arrival-rate` breakpoint scenario |
| `RateMetricSemanticsTests` | 1 | a custom `Rate` in a reference script is never fed only literal `1` (the 0%/100% anti-pattern); it must record a boolean every iteration |
| `K6InspectTests` | 1 | `k6 inspect` parses each local script and runs its init context (skipped when k6 is not installed) |
| `RealK6RunTests` | 2 | real `k6 run` executes default(): (1) the §7 script against a local HTTP stub, asserting exit 0, the stub received requests, and all four custom metrics appear in `--summary-export` output; (2) the §6 no-remote-dependency `handleSummary()` script, asserting exit 0 and that `results.json` was actually written with valid JSON — skipped when k6 is not installed, or when the sandbox denies binding a local listen socket |

**Behavioral test count: 10** (7 static, always run; 3 require a live k6 binary — `K6InspectTests` and both `RealK6RunTests` methods — skipped without it)

## outputexample/load-test/ Tests (`test_outputexample.py`)

| Test Class | Tests | Validates |
|------------|:-----:|-----------|
| `FilesExistTests` | 1 | the script and its paired analysis doc both exist on disk |
| `ScriptSyntaxTests` | 1 | `node --check` on the published script (skipped without node) |
| `K6InspectTests` | 1 | `k6 inspect` on the published script (skipped without k6) |
| `RealRunTests` | 1 | real `k6 run` of the published script (rate/VU numbers shrunk, thresholds stripped) against a local stub, proving `default()`/`handleSummary()` execute without a runtime error and `results.json` is written — skipped when k6 is not installed, or when the sandbox denies binding a local listen socket. Does not validate SLO/threshold pass-fail at scale — a local stub can't sustain 2000 req/s, so thresholds are deliberately removed for this run; see the test's docstring |
| `K6ExecutionRequirementsTests` | 2 | `k6 inspect --execution-requirements` (the ground truth for peak VU count and total wall-clock time, since scenarios reuse VU capacity across non-overlapping windows rather than summing) matches the analysis doc's stated `maxVUs` and total run duration — skipped without k6 |
| `CrossFileConsistencyTests` | 8 | error-rate threshold matches the declared <0.1% SLO; script's arrival-rate target matches the analysis doc's stated RPS; no `ramping-vus` executor (regression guard — a closed model can't guarantee an exact-RPS SLO); `dropped_iterations` threshold present; all four scenarios (warmup/ramp/load_test/cooldown) present; the Scorecard line's tier scores sum to its stated total; every percentile-table row's verdict (PASS/FAIL) matches what its value vs. SLO threshold actually implies; Hygiene score is capped at 3/5 whenever `discardResponseBodies` is absent from the script (regression guard against an unearned Hygiene #13) |

**outputexample test count: 14** (9 static, always run; 5 require a live k6/node binary, skipped without them; 1 of those additionally skips under a sandbox that denies local socket binding)

## Golden Fixtures + Per-Fixture Test Classes (`test_golden_scenarios.py`)

### Fixture Inventory

| ID | Title | Type | Severity | Maps To |
|----|-------|------|----------|---------|
| LT-001 | No warmup phase | defect | critical | AE-1 + Scorecard Critical #2 |
| LT-002 | No SLO thresholds | defect | critical | AE-2 + Scorecard Critical #1 |
| LT-003 | 30s test declared comprehensive | defect | critical | AE-5 + Scorecard Critical #3 |
| LT-004 | Load generator co-located | defect | standard | AE-3 + Scorecard Standard #7 |
| LT-005 | Same request every time (cache bias) | defect | standard | AE-4 + Scorecard Standard #8 |
| LT-006 | Averages as verdict | defect | standard | AE-6 + Scorecard Standard #6 |
| LT-007 | Instant full load, no ramp | defect | standard | Scorecard Standard #4 |
| LT-008 | Well-formed k6 script | good_practice | none | Positive exemplar (k6) + Rate-semantics guard |
| LT-009 | Well-formed vegeta breakpoint | good_practice | none | Positive exemplar (vegeta) |
| LT-010 | Results without SLOs | degradation_scenario | none | §4 Partial mode |
| LT-011 | Vague request, no context | degradation_scenario | none | §4 Planning mode |
| LT-012 | Multi-scenario capacity plan | workflow | none | Deep depth, Write mode |
| LT-013 | Analyze results with SLO verdict | workflow | none | Analyze mode |
| LT-014 | Review existing script | workflow | none | Review mode |
| LT-015 | Rate metric records only failures | defect | standard | k6 Rate semantics (§7 custom-metric rule) |

### Per-Fixture Test Classes

| Class | Fixture | Tests | Validates |
|-------|---------|:-----:|-----------|
| `TestFixtureIntegrity` | all | 8 | count>=11; required fields; valid types/severities; defect!=none; non-defect=none; unique IDs; coverage_rules findable |
| `TestLT001`–`TestLT007` | 001-007 | 3 each | type/severity; violated_rule keyword; feedback keyword |
| `TestLT008` | 008 | 4 | good_practice/none; "no violation"; SharedArray; **Rate recorded every iteration (regression guard)** |
| `TestLT009`–`TestLT014` | 009-014 | 3 each | type/severity; feedback keywords per scenario |
| `TestLT015` | 015 | 3 | defect/standard; violated_rule mentions Rate; feedback explains the `add(!ok)` fix |

**Golden test count: 54** (8 integrity + 46 behavioral)

## Coverage Summary (documentation-contract presence, not domain correctness)

Every "100%" below means "a test asserts this section/item exists and
contains its expected keywords" — not "this content is correct" or "the
model behaves this way at runtime." See the caveat at the top of this file.

| Category | Covered | Total | Coverage |
|----------|:-------:|:-----:|:--------:|
| Mandatory Gates (§2) | 4/4 | 4 | 100% |
| Depth Tiers (§3) | 3/3 | 3 | 100% |
| Degradation Modes (§4) | 5/5 | 5 | 100% |
| Checklist Subsections (§5) | 4/4 | 4 | 100% |
| Checklist Items (§5) | 19/19 | 19 | 100% |
| Tool Selection (§6.1) | 3/3 | 3 | 100% |
| Scenario Types (§6.2) | 6/6 | 6 | 100% |
| Anti-Examples (§7) | 8/8 | 8 | 100% |
| Scorecard Items (§8) | 13/13 | 13 | 100% |
| Output Contract Sections (§9) | 9/9 | 9 | 100% |
| Reference Files | 3/3 | 3 | 100% |
| Golden Fixture Types | 4/4 | 4 | 100% |
| Golden Severity Levels | 3/3 | 3 | 100% |

**Total tests: 153** (75 contract + 54 golden + 10 behavioral k6-script + 14
outputexample). Without k6/node installed, the behavioral `K6InspectTests` +
both `RealK6RunTests` methods, and the outputexample `ScriptSyntaxTests` +
`K6InspectTests` + `RealRunTests` + both `K6ExecutionRequirementsTests`
methods, are all skipped — 145 run + 8 skipped.
Both `RealK6RunTests` and outputexample's `RealRunTests` also skip (not
fail) when the sandbox denies binding a local listen socket, even with k6
present — in that case 150 run + 3 skipped.

## Known Coverage Gaps

| Gap | Priority | Rationale |
|-----|----------|-----------|
| Soak test fixture (30-60 min leak detection) | Medium | §6.2 defines Soak but no golden fixture exercises memory-leak-over-time detection methodology. |
| gRPC load testing fixture | Medium | SKILL §1 marks gRPC "partial coverage"; no reference pattern or fixture exercises gRPC (streaming, unary, metadata auth). |
| Distributed k6 (Operator / Cloud / segments) fixture | Low | SKILL §1 marks distributed "partial coverage"; no fixture covers distributed execution coordination. |
| wrk scripting fixture | Low | SKILL §1 marks wrk "partial coverage"; no wrk/Lua reference pattern or fixture. |
| Scorecard Standard #5 (error rate monitored) dedicated fixture | Low | Validated in contract tests but no golden fixture targets missing error classification (429 vs 503 vs timeout). |
| CI/CD integration fixture (pipeline gating) | Low | §10 documents CI integration but no fixture exercises pipeline fail/pass gating on threshold results. |
| Runtime Rate-metric/handleSummary behavior via an executed `k6 run`, for scripts other than §6/§7 | Low | `RealK6RunTests` executes §7's `default()` for real (checks its 4 custom metrics emit) and §6's `handleSummary()` for real (checks `results.json` is actually written); LT-015 + `RateMetricSemanticsTests` statically catch the "Rate fed only on failure" bug elsewhere. Every other reference script (§1, §5, §9, ...) still only gets static/init-context checks. |
| Advise-mode output-contract exemption | Low | §2 Gate 3 and §9 document Advise mode skipping the nine-section contract, but no test asserts a real Advise-mode response actually omits fabricated sections — that requires behavioral (LLM) evaluation, out of scope for this zero-LLM suite. |
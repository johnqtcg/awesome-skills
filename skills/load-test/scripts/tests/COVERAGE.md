# load-test Skill — Test Coverage Matrix

## Discriminating power — measured, not claimed

A test count is not a guarantee. This suite is graded by mutation: inject a
semantic defect, confirm the suite goes red.

Measured like-for-like: the identical 20-mutation set, run against the
pre-hardening tree restored from git and against the current tree.

| | Semantic mutations | Undetected | Fail-open rate | Harmless reword |
|---|---:|---:|---:|:---:|
| Before hardening (2026-09-16) | 20 | 14 | **70%** | RED (over-fitted) |
| Now | 20 | 0 | **0%** | GREEN (correct) |

An independent audit using a wider 25-mutation set measured 64% on the same
pre-hardening tree; the two numbers are consistent, they just count different
mutation sets. Neither includes the two runtime-error mutations, which need a
loopback socket the sandbox denies (see below).

Newly caught, all of which previously passed silently: a threshold changed to
10x its own adjacent comment; p95/p99 meanings swapped; a percentile defined as
an average; an arithmetically impossible worked mean; a non-existent k6
executor name in an options-only block; a `>= 4 of 5` scorecard gate relaxed to
`>= 2 of 5` while the verdict line still said 4/5; §9 tier denominators that no
longer sum to the stated total; minute-scale duration floors rewritten as
seconds; a vegeta flag that does not exist; AE-1's WRONG and RIGHT blocks
swapped; each of the four Mandatory Gates emptied or semantically inverted; any
§9 output-contract section reduced to a bare heading.

Deliberately **not** caught: renaming a section heading without changing its
meaning (`## 2 Mandatory Gates` → `## 2 Required Gates`). The old suite failed
on exactly that while missing everything above it — brittle and blind at once.
Headings are now matched by name.

**One class remains unexercised in a sandbox**: a runtime error inside
`default()`. The real-`k6 run` layer that catches it cannot bind a loopback
socket under Claude Code's default sandbox (see below). The assertion was
verified directly instead — see "The exit-code trap".

## The exit-code trap (why the runtime layer was fail-open)

`k6 run` **exits 0** on iteration-level JavaScript errors when no threshold is
breached. Verified on k6 v1.3.0: a script whose `default()` raises a
`ReferenceError` on every iteration returns exit status 0 — *and* reports all
iterations as completed. The error appears only on stderr.

So the previous assertion —

```python
self.assertEqual(0, proc.returncode,
    "k6 run failed executing default() for real — this is exactly the class "
    "of bug static analysis and k6 inspect cannot see")
```

— could not detect the bug class it named. The one time it did fire, it was the
side-channel `assertGreater(len(request_log), 0)` doing the work, because the
error happened to precede the HTTP call; moving the same bug one line later
made the whole suite green.

`assert_k6_run_clean()` now asserts three things together: exit code,
**absence of `ReferenceError`/`level=error` in the output**, and the expected
completed-iteration count. All three are needed — the iteration count alone
does not catch it, since k6 counts the erroring iteration as completed.

## A skip is not a pass

The real-`k6 run` layer disappears entirely when k6 is missing or a sandbox
refuses a loopback `bind()`, and the summary line still reads OK — a 0.2 s
runtime for a suite advertising real k6 executions is the tell. Two mitigations:

* `LOADTEST_REQUIRE_RUNTIME=1` turns that skip into a failure (for CI that must
  actually exercise the layer);
* `scripts/run_regression.sh` detects the skip and downgrades its final line to
  "passed EXCEPT the layers noted above", with a loud WARNING naming what did
  not run.

The same applies to `outputexample/load-test/`, which ships with the repository
and not with the skill bundle: its 14 checks skip with an explicit reason when
the skill is installed standalone, and the runner says so.

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

**Contract test count: 77**

## Behavioral k6 Script Tests (`test_k6_scripts_valid.py`)

| Test Class | Tests | Validates |
|------------|:-----:|-----------|
| `ImportCompletenessTests` | 2 | every complete reference script found (>=5); every used k6 module (`k6/http`, `k6/data`, `k6/metrics`, `k6`) is imported — catches copy-paste `ReferenceError`s that `k6 inspect` cannot |
| `MemoryHygieneAndCompositionRegressionTests` | 4 | no Gauge fed by `__VU` (records a VU id, not a concurrency count — §7); §1 canonical skeleton has no Trend duplicating `http_req_duration` (§11.3); §10 CI example doesn't use `--out csv`/`--out json` (§11.2); §9's "breakpoint" composition actually defines a `ramping-arrival-rate` breakpoint scenario |
| `RateMetricSemanticsTests` | 1 | a custom `Rate` in a reference script is never fed only literal `1` (the 0%/100% anti-pattern); it must record a boolean every iteration |
| `K6InspectTests` | 1 | `k6 inspect` parses each local script and runs its init context (skipped when k6 is not installed) |
| `RealK6RunTests` | 2 | real `k6 run` executes default(): (1) the §7 script against a local HTTP stub, asserting exit 0, the stub received requests, and all four custom metrics appear in `--summary-export` output; (2) the §6 no-remote-dependency `handleSummary()` script, asserting exit 0 and that `results.json` was actually written with valid JSON — skipped when k6 is not installed, or when the sandbox denies binding a local listen socket |

**Behavioral test count: 13** (9 static, always run; 4 need a live k6 binary
or the network — `K6InspectTests`, `OptionsFragmentTests::test_options_fragments_are_valid_k6_config`,
both `RealK6RunTests` methods and `RemoteImportReachabilityTests`)

| Added in this round | Tests | Validates |
|---|:-:|---|
| `OptionsFragmentTests` | 2 | `scenarios:`/`thresholds:` fragments — 17 of 23 JS blocks had no machine check at all — are wrapped in a minimal valid script and handed to k6's own options validator, which rejects bogus executor names |
| `RemoteImportReachabilityTests` | 1 | every `https://` import in the references resolves. A 404'd jslib URL shipped here, in the double blind spot between "no `export default`" (import checker skipped it) and "remote import" (`k6 inspect` skipped it) |

## outputexample/load-test/ Tests (`test_outputexample.py`)

| Test Class | Tests | Validates |
|------------|:-----:|-----------|
| `FilesExistTests` | 1 | the script and its paired analysis doc both exist on disk |
| `ScriptSyntaxTests` | 1 | `node --check` on the published script (skipped without node) |
| `K6InspectTests` | 1 | `k6 inspect` on the published script (skipped without k6) |
| `RealRunTests` | 1 | real `k6 run` of the published script (rate/VU numbers shrunk, thresholds stripped) against a local stub, proving `default()`/`handleSummary()` execute without a runtime error and `results.json` is written — skipped when k6 is not installed, or when the sandbox denies binding a local listen socket. Does not validate SLO/threshold pass-fail at scale — a local stub can't sustain 2000 req/s, so thresholds are deliberately removed for this run; see the test's docstring |
| `K6ExecutionRequirementsTests` | 2 | `k6 inspect --execution-requirements` (the ground truth for peak VU count and total wall-clock time, since scenarios reuse VU capacity across non-overlapping windows rather than summing) matches the analysis doc's stated `maxVUs` and total run duration — skipped without k6 |
| `CrossFileConsistencyTests` | 8 | error-rate threshold matches the declared <0.1% SLO; script's arrival-rate target matches the analysis doc's stated RPS; no `ramping-vus` executor (regression guard — a closed model can't guarantee an exact-RPS SLO); `dropped_iterations` threshold present; all four scenarios (warmup/ramp/load_test/cooldown) present; the Scorecard line's tier scores sum to its stated total; every percentile-table row's verdict (PASS/FAIL) matches what its value vs. SLO threshold actually implies; Hygiene score is capped at 3/5 whenever `discardResponseBodies` is absent from the script (regression guard against an unearned Hygiene #13) |

**outputexample test count: 14** (13 collected here; all skip with an explicit reason when the skill is installed without the repository) (9 static, always run; 5 require a live k6/node binary, skipped without them; 1 of those additionally skips under a sandbox that denies local socket binding)

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

**Total tests: 175** (77 contract + 54 golden + 13 behavioral k6-script +
14 outputexample + 17 content-consistency). On this machine with k6 and node
installed but a sandbox that denies loopback bind: **171 run + 4 skipped** —
the 3 real-`k6 run` tests and the network-dependent remote-import check.
Installed standalone (no repository around it): **154 run + 17 skipped**, zero
failures; before this change the same layout produced **13 hard failures**.

## Content-Consistency Tests (`test_content_consistency.py`)

| Test Class | Tests | Validates |
|------------|:-----:|-----------|
| `ThresholdMatchesItsOwnComment` | 1 | a `rate<N` threshold equals the percentage in the comment beside it |
| `PercentileSemantics` | 2 | percentile rows are ordered and self-consistent; no percentile is ever defined as an average |
| `WorkedArithmeticHolds` | 1 | the "why percentiles" worked mean is actually the weighted mean of its own inputs |
| `ScorecardInternalConsistency` | 5 | three tiers parse; each heading's `of N` matches its item count; items numbered 1..N; tier sizes sum to §9's `X/13`; §8 verdict thresholds match the tier headings |
| `DurationsAreOnTheRightScale` | 2 | steady-state floors are in minutes (§8 vs AE-5); soak is tens of minutes |
| `VegetaCliSurface` | 2 | only real vegeta subcommands and flags appear (vegeta is not installed; an allowlist binds them to a real CLI surface rather than to nothing) |
| `OutputContractSections` | 4 | all nine §9 sections present with expected titles AND a substantive body; §9.6 still demands percentiles; §9.9 still says "never empty" |

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
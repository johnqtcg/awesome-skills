# Go-Benchmark Skill — Test Coverage Matrix

## Contract Tests (`test_skill_contract.py`)

| Test Class | Tests | Validates |
|------------|-------|-----------|
| `TestFrontmatter` | 2 | name=go-benchmark; trigger keywords |
| `TestHardRules` | 6 | Section exists; all 5 Hard Rules by key phrase |
| `TestMandatoryGates` | 5 | 3 gates: Evidence (mode/data-basis), Applicability (STOP), Scope (5 shapes) |
| `TestThreePhaseWorkflow` | 7 | 3 phases + key elements per phase |
| `TestOutputContract` | 5 | 4 required fields: mode, data_basis, scorecard_result, profiling_method |
| `TestExpectedOutputFormat` | 4 | Output format section; run command; top-3 hotspots; scorecard block |
| `TestHonestDegradation` | 5 | Table exists; 4 degradation paths; no invented numbers |
| `TestAutoScorecard` | 5 | Section exists; Critical/Standard/Hygiene tiers; next-step table |
| `TestAntiExamples` | 5 | Section exists; 3 BAD/GOOD pairs; ≥3 markers each |
| `TestReferenceFiles` | 10 | All 5 files exist; SKILL.md references all 5; key content per file |
| `TestLineCount` | 1 | SKILL.md ≤ 420 lines |
| `TestCrossFileConsistency` | 10 | Key terms present in correct ref files; minimum line counts per file |
| `TestCoverageDocIsCurrent` | 6 | Total, per-layer counts and line budget, all derived from the loader |
| `SectionHelperTests` | 5 | `md_section` / `md_rows` / `numbered_rule` — including the fence-aware stop |
| `NormativeRuleDirectionTests` | 7 | Each Hard Rule's **direction**, inside its own numbered item |
| `ScorecardAndGateValuesPinnedTests` | 8 | Tier bars derived from their own checklists; gate ↔ contract reachability |
| `MeasuredClaimsPinnedTests` | 12 | Every claim a measurement corrected, plus its inverse |

**Contract test count: 102**

## Golden Fixtures + Per-Fixture Test Classes (`test_golden_scenarios.py`)

### Fixture Inventory

| ID | Title | Type | Severity |
|----|-------|------|----------|
| BENCH-001 | Missing sink (`_ =` discards result) | defect | critical |
| BENCH-002 | Setup inside loop (connectDB in hot path) | defect | critical |
| BENCH-003 | `b.ResetTimer()` inside loop | defect | critical |
| BENCH-004 | Single-count comparison (no `-count=10`) | defect | standard |
| BENCH-005 | Good sub-benchmark with size sweep ✓ | good_practice | none |
| BENCH-006 | Good parallel benchmark with `RunParallel` ✓ | good_practice | none |
| BENCH-007 | Good throughput benchmark with `b.SetBytes` ✓ | good_practice | none |
| BENCH-008 | Run command missing `-benchmem` | defect | critical |
| BENCH-009 | Degraded output — no code or data | degradation_scenario | none |
| BENCH-010 | Profile-guided workflow (pprof → targeted benchmark) | workflow | none |
| BENCH-011 | Noisy benchstat (± > 5%, p > 0.05) | defect | standard |

### Per-Fixture Test Classes

| Class | Fixture | Type Tests | Coverage Tests |
|-------|---------|-----------|----------------|
| `TestBench001MissingSink` | 001 | type=defect, severity=critical, sink in violated_rule | all coverage_rules |
| `TestBench002SetupInsideLoop` | 002 | type=defect, severity=critical, timer in violated_rule | all coverage_rules |
| `TestBench003ResetTimerInsideLoop` | 003 | type=defect, severity=critical, timer in violated_rule | all coverage_rules |
| `TestBench004SingleCountComparison` | 004 | type=defect, severity=standard | all coverage_rules |
| `TestBench005SubBenchmarkSizes` | 005 | type=good_practice, no violations in feedback | all coverage_rules |
| `TestBench006ParallelBenchmark` | 006 | type=good_practice, no violations in feedback | all coverage_rules |
| `TestBench007ThroughputBenchmark` | 007 | type=good_practice, no violations in feedback | all coverage_rules |
| `TestBench008MissingBenchmem` | 008 | type=defect, severity=critical, benchmem in violated_rule | all coverage_rules |
| `TestBench009DegradedNoData` | 009 | type=degradation_scenario, "fabricate" in expected_feedback | all coverage_rules |
| `TestBench010PprofGuidedBenchmark` | 010 | type=workflow, severity=none | all coverage_rules |
| `TestBench011NoisyBenchstat` | 011 | type=defect, severity=standard | all coverage_rules |

**Golden test count: 30** (8 integrity + 11 per-fixture × 2 = 22 fixture-metadata checks).
The *behaviour* of these fixtures is exercised separately: every `good_practice` snippet is
compiled and run under `-race` by
`test_templates_compile.py::GoldenGoodPracticeRaceTests`.

## Coverage Summary

| Category | Total | Tested | Coverage |
|---------|-------|--------|----------|
| Hard Rules | 5 | 5 | 100% |
| Mandatory Gates | 3 | 3 | 100% |
| Three phases | 3 | 3 | 100% |
| Scorecard tiers | 3 | 3 | 100% |
| Output contract fields | 4 | 4 | 100% |
| Anti-example patterns | 3 | 3 | 100% |
| Degradation levels | 4 | 4 | 100% |
| Reference files | 5 | 5 | 100% |
| Cross-file terminology | key terms | 6 | 100% |
| Reference file min lines | 5 files | 5 | 100% (≥80-100) |
| SKILL.md line budget | 416/420 | 1 | ✅ (4 lines of headroom) |
| Defect fixtures (critical + standard) | 6 | 6 | 100% |
| Good-practice fixtures | 3 | 3 | 100% |
| Degradation/workflow scenarios | 2 | 2 | 100% |

**Template/compile/script test count: 42**

**Total tests: 174 collected** — 102 contract + 30 golden + 42 template/compile/script
(the compile module defines 40; `ReferenceTemplateCompileTests` inherits 2 more from
`TemplateCompileTests`, which is why an AST count of `def test_` under-reports by 2).

Pinned by `test_skill_contract.py::TestCoverageDocIsCurrent`, which counts what the loader
actually collects and fails when this file drifts. The previous version claimed 96 tests and
a 378-line SKILL.md when the real numbers were 105 and 419 — a coverage doc that overstates
the suite is read as coverage, so it is now machine-checked.

## What Each Layer Can and Cannot Prove

| Layer | Proves | Does **not** prove |
|---|---|---|
| `test_skill_contract.py` | The skill states a rule **in the direction it means**, references exist, thresholds are derived from the lists they grade | That a model follows any of it |
| `test_golden_scenarios.py` | Fixture metadata is internally consistent, classifications are valid, and every `coverage_rules` string exists somewhere in the docs | Anything about produced output |
| `test_templates_compile.py` | Every GOOD template in SKILL.md **and** `references/` type-checks and runs race-free under the real toolchain; every `good_practice` fixture is executed under `-race`; documented "this does not compile" claims actually fail to compile; both shipped scripts are exercised (argument validation, refuse-to-clobber, smoke run, memory budget) | That a model writes correct benchmarks unprompted |

**The golden layer is fixture-consistency testing, not forward evaluation.** It is named
"behavioral" in its own docstring, but it never hands a scenario to an agent and grades the
reply — it checks that each fixture declares a valid type/severity and that the strings the
fixture names appear in the docs. That is useful drift protection and it is not evidence of
behaviour; the distinction is recorded here rather than implied away.

**The compile layer is the one that executes anything.** It is also the layer that would have
caught the two defects found in the 2026-07-29 review, had it existed in its current form:
`references/` was outside its scope, so `defer debug.SetGCPercent(debug.SetGCPercent(-1))()`
sat in a shipped template for a full release without ever being handed to a compiler.

## Sixth review round (2026-09-18) — the prose layer had no guard at all

Rounds 1–4 hardened everything executable: templates compile and run under `-race`, the
"this does not compile" claim is compiled, both scripts are exercised, measured constants are
pinned. The *normative prose* was never covered, and a mutation sweep measured the size of
that hole: **26 mutations, 19 survived — a 73% escape rate.**

The root cause was structural, not a missing case. There was **no section-extraction helper
anywhere in the suite**, so ~94 of the contract assertions were `assertIn(phrase, whole
SKILL.md)`. That shape cannot tell "always X" from "never X" — it only sees the word X
somewhere in the file. What escaped:

| Mutation | Why it passed |
|---|---|
| Hard Rule 1 → "discarding with `_ =` is fine; the compiler keeps the call" | `var sink`, `measures nothing` still appear elsewhere |
| Hard Rule 2 → setup goes **after** `b.ResetTimer()` | `b.ResetTimer()` still appears |
| `-run='^$'` made optional | the string is used in six commands |
| `alloc_space` **is** memory footprint | the phrase is in the section either way |
| Critical `N/A` counts as a pass | ditto |
| benchstat reports **means**, not medians | ditto |
| `±` is a **coefficient of variation** | ditto |
| standard error shrinks **linearly** (`1/n`) | ditto |
| "boxing allocates" (the escape caveat deleted) | ditto |
| pprof default flag is `-alloc_space` | ditto |
| AP-5: "allocation figures differ sharply" | ditto |
| AP-5 pool counts edited to agree | no number was read by any test |
| `b.Loop` overhead figure → 0.02 ns/op | ditto |
| discard measured **above** baseline | ditto |
| interleaving is **AB-AB**, old always leads | ditto |
| the whole Interleave section renamed away | ditto |
| `gc_claim_check.sh` stops disabling GC | the script was run, never asserted to disable GC |
| COVERAGE.md's per-layer counts → 999 / 1 | only the **total** was pinned, so offsetting errors passed |

Four of the seven kills were also incidental: H3 / H4 died because the mutation happened to
delete a literal that a *golden fixture's* `coverage_rules` list names, not because any test
read the rule.

**What this round added.** `md_section` / `md_rows` / `numbered_rule` (fence-aware — a `#`
inside a ```bash block is a shell comment, and the first draft truncated every section at
one), then five classes built on them:

| Class | Pins |
|---|---|
| `SectionHelperTests` | the helpers themselves, including the fence-aware stop |
| `NormativeRuleDirectionTests` | each Hard Rule's direction inside its own numbered item, plus an enumeration guard so a new rule cannot arrive unpinned, plus a self-test that drives every assertion against synthetic **inverted** text |
| `ScorecardAndGateValuesPinnedTests` | tier bars recomputed from each tier's own checklist length; every rounding-table entry checked arithmetically; Evidence-Gate outcomes proven reachable in the Output Contract |
| `MeasuredClaimsPinnedTests` | every claim a measurement corrected, **and its inverse**; the AP-5 pool table's direction parsed from the numbers; provenance stamps checked per block |
| `AllowedToolsContractTests` (extended) | no shell may be pre-approved with a wildcard |

**Two defects found in this round's own guards, both fixed before shipping:**

- The provenance-stamp check searched the whole file, so gutting one `<!-- measured: … -->`
  passed on the strength of a different table's stamp. Now asserted per stamp.
- The counter-example classifier let a block's *body* vote. The GOOD interleave recipe says an
  interrupted run "cannot strand you on the wrong branch" — the word `wrong` marked the whole
  recommended recipe as a counter-example and exempted it. Classification now reads the
  `# GOOD:` / `# BAD:` label only.

**Content fixed in the same round** (each now pinned by one of the classes above):

- **A live cross-file contradiction.** SKILL.md forbids `git switch -`; `benchstat-guide.md`'s
  GOOD block used it. Verified: from `other`, `main` → `topic` → `-` lands on **master**. The
  guard written for exactly this required the command and the claim on one *line*, and the two
  halves sat five lines apart. The recipe now uses worktrees, and the guard is scoped to the
  command inside a non-counter-example segment.
- **"Profile the running program" had no path.** The Scope Gate sent readers there and nothing
  in the skill showed how — `net/http/pprof`, `?seconds=N`, the internal-port rule and the
  empty-mutex-profile trap are now in `pprof-analysis.md`.
- **PGO was absent** although Phase 2 produces exactly the profile it consumes.
- **`sync.Pool` returned uncapped buffers** in both examples. One oversized item pins its
  capacity for every worker that touches it; `maxPooled` is now in both, and the two files'
  reset conventions are reconciled explicitly rather than silently differing.
- **AP-3 argued from an unmeasured cost.** Measured (go1.26.1 darwin/arm64, 5 runs), the "BAD"
  modulo form and the "BETTER" fix are indistinguishable — 0.81–1.52 vs 0.80–1.60 ns/op. The
  entry now names the real problems (working-set size, `b.N`-dependent results) and carries
  the measurement that retired the old one.
- **`string(strconv.AppendInt(…))` was labelled "GOOD: no allocation" unconditionally.** It is
  0 allocs/op only while the result stays on the stack; stored to a package-level `string` it
  measures 8 B/op, 1 allocs/op (go1.26.1 darwin/arm64). This is the *same* escape caveat the
  file states for interface boxing twenty lines above — applied to one recipe and not its
  neighbour.
- **`allowed-tools` pre-approved two shells.** `Bash(bash*gc_claim_check.sh*)` matches
  `bash -c '<anything>' gc_claim_check.sh` — the wildcard sits exactly where `-c` goes. Both
  entries removed; the scripts prompt once, and SKILL.md says why so the next edit does not
  "fix" it by adding them back. `Bash(go test*)` still pre-approves `go test -exec=…`; that is
  unavoidable for this skill and is now recorded rather than overlooked.

## Known Coverage Gaps

| Gap | Priority |
|-----|----------|
| No forward eval: no layer hands a scenario to a model and grades the reply | **High** — the largest remaining gap |
| The direction guards pin the rules that exist today. A *new* Hard Rule is caught by `test_every_hard_rule_is_pinned_here`, but a new normative claim in a reference file is not — nothing enumerates those | Medium |
| `run_interleaved_bench.sh` is tested down to its ABBA execution order (stub binaries log their invocation sequence); the `git worktree` + `go test -c` build documented in front of it is not executed by any test | Low |
| AP-5's measured figures are pinned to the script's iteration constant by test, but the numbers themselves cannot be machine-compared — they vary by host. They carry an explicit toolchain/platform/date stamp instead | Low |
| sync.Pool before/after optimization fixture | Low |
| escape analysis workflow fixture | Low |
| Multi-environment comparison error fixture | Low |
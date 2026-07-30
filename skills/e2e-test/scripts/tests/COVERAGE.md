# E2E Test Skill — Test Coverage Matrix

Counts in this file are re-derived from a run, not carried forward. The previous
version claimed 81 contract tests and 10 golden fixtures when the real numbers
were 79 and 14 — and asserted "all fixtures tested" while 011–014 had no test
class at all. `TestEveryFixtureHasATestClass` now fails if a fixture is added
without a test, so that particular claim can no longer drift.

Regenerate with `bash scripts/run_regression.sh`.

## Totals

| Suite | Tests |
|-------|------:|
| `test_skill_contract.py` | 184 |
| `test_golden_scenarios.py` | 54 |
| `test_discover_script.py` | 44 |
| **Total** | **282** |

Plus one **opt-in** verifier not counted above:
`scripts/verify_hook_semantics.sh` (8 real-Playwright checks; needs npm).

Both invocation forms must be green: `python3 <file>` and
`python3 -m pytest scripts/tests`. They differ — this repo's `pytest.ini` sets
`--import-mode=importlib`, which does not add the test directory to `sys.path`.

## Contract Tests (`test_skill_contract.py`)

| Class | Covers |
|-------|--------|
| TestFrontmatter | name, description keywords, description length |
| TestMandatoryGates | 5 gates + serial ordering |
| TestAntiExamples | section exists, count ≥ 7, each anti-example keyword |
| TestQualityScorecard | section, 3 tiers, C1–C4, S1–S6, H1–H4 |
| TestVersionGate | section, corrected PW gates, Node deferral, networkidle ban |
| TestOutputContract | 8 output fields, conditional code output |
| TestRunnerStrategy | dual-tool strategy, bridge workflow |
| TestPlaywrightRules | section exists, key concepts |
| TestFlakyPolicy | section, triage sequence, root cause categories |
| TestReferenceFiles | existence, depth, code examples, sections |
| TestSelectiveLoading | section, per-reference conditions |
| TestAccessibilityContent | axe-core, WCAG tags, scoped analysis, violations |
| TestVisualRegressionContent | toHaveScreenshot, masking, baselines, thresholds |
| TestMobileDesktopContent | emulation, breakpoints, Electron, RN Web, geolocation |
| TestDiscoverScript | exists, executable, referenced, key checks |
| TestJsonOutput | section, key JSON fields |
| TestGoldenExamplesTOC | TOC present |

### Drift guards added after the 2026-07-29 review

These exist because each one is a defect that actually shipped. They assert facts
about the skill's *internal consistency*, which no single-file test could catch.

| Class | Guards against |
|-------|----------------|
| TestVersionFactsAreCorrect | Playwright API-introduction versions drifting from upstream release notes. Pins getByRole 1.27, toPass 1.29, hasNot 1.33, toBeAttached 1.33, frameLocator 1.17, contentFrame 1.43, webServer 1.14, plus the Node `engines` table |
| TestNoDiscouragedApis | `networkidle` reappearing outside a prohibition context (two instances were live inside GOOD examples) |
| TestTauriRoutedAwayFromPlaywright | "Playwright WebView debugging / Connect to WebView port" returning. Playwright cannot attach to WKWebView / WebView2 / WebKitGTK |
| TestSelectorPriorityConsistent | SKILL.md claiming "data-testid priority" while the reference ranks `getByRole` first |
| TestNoCredentialLeakInProbes | `echo "E2E_PASS=${E2E_PASS:-MISSING}"` — a presence check that prints the password |
| TestAntiExampleCountClaimIsAccurate | "catalog of 12" against a file holding 7; also requires the reference to be a superset of SKILL.md rather than a duplicate |
| TestIframeCoverage | `frameLocator` / `contentFrame` absent while fixture 014 required them |
| TestAllowedToolsCoversDocumentedCommands | `allowed-tools` omitting `agent-browser` and the scripts the skill tells you to run |
| TestGoldenExamplesLabelledSynthetic | Concrete pass counts presented without a synthetic-data warning |

### Second review round (also 2026-07-29)

| Class | Guards against |
|-------|----------------|
| TestWaitOrderingDocumented | `await page.waitForResponse(...)` placed *after* its triggering action. This shipped inside the flaky-triage golden example **as the fix** — it hangs whenever the response is fast, so it "passes" only while the race it was meant to remove is still present |
| TestEnvStateSemantics | `.env.example` reported as `available`. A template proves a variable is expected, not that a value exists; the old behaviour cleared the `no_base_url` blocker and could report an unrunnable project as `ready` |
| TestLinterScopeIsHonest | the linter docstring claiming C1–C4 / S1–S6 / H1–H4 while implementing 8 of 14 items |
| TestConfigBaselineDoesNotGuessEnvironment | the config template's silent localhost fallback, which in CI boots a dev server and reports green for an environment nobody meant to test |

### Third review round (also 2026-07-29)

| Class / test | Guards against |
|--------------|----------------|
| `test_guard_does_not_leak_across_tests` | a `test.skip` inside test A laundering an unguarded use in test B. Per-variable matching was still file-wide; guard coverage is now positional (file / describe / test / hook scope) |
| `test_per_test_guards_in_every_test_are_clean` + `test_alias_with_fallback_is_not_tracked` | the two false positives that scoping introduced — flagging a bare declaration, and flagging an alias declared with `?? ''` |
| `test_inline_comment_after_empty_value_is_declared` (+ 6 sibling cases) | `E2E_PASS= # TODO: inject from vault` reported `available`. Stripping only whitespace and quotes left `#TODO:injectfromvault`, non-empty. Now parses quoted values, and treats a `#` at value start or after whitespace as a comment — while keeping `p#ss` and `"p#ss"` as real values |
| `test_supported_runtime_kept_separate_from_engine_floor` | quoting `engines.node` as if it were the supported-runtime list. Node 20 satisfies `engines` for 1.62 but is outside the documented "latest 22.x, 24.x or 26.x" — "installs" is not "supported" |
| `TestProgressiveDisclosureBudget` | SKILL.md creeping past ~500 lines by accretion; every reference lacking a stated load condition; the 1000-line deep-patterns reference being presented as a whole-file read |
| `test_reference_does_not_duplicate_the_core_seven` / `test_toc_lists_every_case` / `test_every_reference_file_has_a_toc` | anti-examples.md restating SKILL.md's seven cases (≈150 duplicated lines) and being the only reference with no TOC |

### Fourth review round (2026-07-30)

| Class / test | Guards against |
|--------------|----------------|
| `test_after_each_guard_protects_nothing` / `test_after_all_guard_protects_nothing` | all four Playwright hooks being treated as promotable guards. Only `beforeEach` / `beforeAll` run early enough to stop a read; a `test.skip` in `afterEach` / `afterAll` executes after the body has already used the value, so it suppressed the finding while protecting nothing |
| `test_before_each_guard_still_protects` / `test_before_all_guard_still_protects` | over-correcting the above and losing coverage for the hooks that *do* protect |
| `test_only_before_hooks_are_promotable` | the regex regressing to match all four hook names again — asserted at the source level, not only behaviourally |
| `test_guard_placement_documented` | the linter enforcing hook ordering that the skill never teaches |
| `test_typical_task_claim_matches_the_table` | the lead sentence undercounting its own table ("the first two rows and nothing else", while writing Playwright code also needs `playwright-patterns.md`) |
| `test_core_seven_enumeration_matches_skill_md_exactly` | the restated core-seven list drifting from SKILL.md. It had been written from the *deleted* half of anti-examples.md, so it named "asserting implementation detail" — a case SKILL.md does not have — and omitted "Pseudo-runnable scaffold without test.skip". The dedup test only checked for heading collisions, so a wrong enumeration passed |

### Fifth review round (2026-07-30) — the hook rule is now measured, not assumed

Round 4's hook rule was pinned by unit tests that encoded my own assumption about
Playwright's runtime. A reviewer correctly noted that this proves nothing about
the external framework: `beforeAll` runs once per worker, and `TestInfo.skip` is
documented as skipping "the currently running test" — which is not obviously a
thing that exists yet inside `beforeAll`. The docs never cover the combination.

Resolved by measurement rather than by weakening the rule.
`scripts/verify_hook_semantics.sh` installs `@playwright/test` and runs a real
suite (no browser needed — none of its specs use the `page` fixture). Observed on
**1.62.0**:

| Scenario | Body ran? | Reported |
|----------|-----------|----------|
| `beforeAll` guard, 2 tests | no | 2 skipped |
| `beforeAll` guard, `--retries=2` | no | 2 skipped |
| `beforeAll` guard, `--workers=2`, 4 tests / 2 files | no | 4 skipped |
| `beforeEach` guard | no | 1 skipped |
| describe-scoped `beforeAll` guard | no (inside) | group skipped, **sibling outside ran** |
| `beforeAll` guard, condition `false` | yes | 1 passed |
| `afterAll` guard | **yes** | 1 skipped |
| `afterEach` guard | **yes** | 1 skipped |

Two conclusions. The `beforeAll` promotion is correct, including the scope
containment the linter depends on. And the `after`-hook case is worse than "does
not help": the body runs, reads the unset value, and the run is then **relabelled
skipped** — a suite that should have failed loudly reports as skipped instead.
That is now taught in SKILL.md and as an anti-example, with the evidence table.

| Class / test | Guards against |
|--------------|----------------|
| `test_hook_semantics_claim_is_backed_by_a_real_run` | the verifier disappearing or losing a scenario; also that a failed npm install exits 2 and is not read as a pass |
| `test_measured_hook_matrix_is_recorded` | the observed matrix and its Playwright version vanishing from the source, turning evidence back into an assertion |
| `test_after_hook_hazard_documented_with_evidence` | the relabelled-skipped hazard being softened back to "does not help" |
| `test_verifier_asserts_both_directions_and_exit_code` | the verifier's own checks being one-directional. Its first version compared only a generic `BODY_RAN` marker, which the describe-scope spec never prints — so that case asserted nothing about the guarded test and would have stayed green if the guard had leaked. The runner's exit code was also ignored. Both fixed; the check now takes must-contain **and** must-not-contain needles plus an expected exit code |

The verifier was then mutation-tested — a checker nobody has seen fail is not
known to work:

| Mutation | Detected as |
|----------|-------------|
| remove the guard from the describe-scoped spec (inside test leaks) | `FAIL missing['1 passed'] missing['1 skipped'] unexpected['INSIDE_RAN']`, exit 1 |
| flip one case's expected exit code | `FAIL exit=0(want 1)`, exit 1 |
| unmutated | all 8 PASS, exit 0 |

The first mutation is the one the original `check()` would have passed.

The verifier is **opt-in** — it needs network and takes ~1 minute, so
`run_regression.sh` does not call it. Re-run it when bumping the Playwright
version this skill targets:

```bash
bash scripts/verify_hook_semantics.sh            # latest
PW_VERSION=1.55.0 bash scripts/verify_hook_semantics.sh
```

### Forward evaluation

| Class | What it actually checks |
|-------|------------------------|
| TestSpecLinter | 30 cases driving `lint_e2e_spec.py` over real spec source — both directions. Detects: waitForTimeout, networkidle, hardcoded URL, credential literal, env guard missing per variable **and per scope**, shared identity, fragile CSS, unjustified serial, vague name, network wait armed after its trigger. Must NOT fire on: localhost URLs, negative-test passwords, teaching comments, CI-flag ternaries, guarded scaffolds, per-test identities, justified serial, guards naming every variable, guards by env name covering an alias, per-test guards in every test, describe-scoped and `beforeEach` guards, aliases declared with a `??` fallback, `await Promise.all([waiter, action])` |
| TestSkillOwnExamplesPassTheGrader | Extracts every non-counter-example `ts` block from SKILL.md and all references, runs the grader over each, and fails on any CRITICAL finding |

`TestSkillOwnExamplesPassTheGrader` found four real defects on its first run:
the flagship golden login example read `process.env.E2E_USER!` with no skip
guard; `globalSetup` and the API-seeding helper read required env with no
validation; and an agent-browser example carried a hardcoded password. It also
caught a C4 violation in an anti-example written during this same change.

## Golden Scenario Tests (`test_golden_scenarios.py`)

| Class | Fixture | Scenario |
|-------|---------|----------|
| TestGoldenFixtureStructure | all | required fields + count ≥ 10 |
| TestGolden001LoginJourney | 001 | New login journey coverage |
| TestGolden002HonestScaffold | 002 | Missing account → scaffold |
| TestGolden003FlakyTriage | 003 | Async race flaky triage |
| TestGolden004CIGate | 004 | CI gate design |
| TestGolden005AgentBrowserExploration | 005 | Exploration → Playwright |
| TestGolden006NoBaseURL | 006 | Stop condition |
| TestGolden007SerialCheckout | 007 | Serial checkout funnel |
| TestGolden008VersionGate | 008 | Old Playwright version |
| TestGolden009Accessibility | 009 | Accessibility audit |
| TestGolden010VisualRegression | 010 | Visual regression |
| TestGolden011TauriDesktop | 011 | Tauri → **not** Playwright |
| TestGolden012NativeMobileRejection | 012 | Native mobile → Detox / Maestro |
| TestGolden013MultiBrowserMatrixCI | 013 | Cross-browser CI matrix + sharding |
| TestGolden014IframeEmbeddedContent | 014 | Payment iframe, frameLocator |
| TestEveryFixtureHasATestClass | all | every fixture is loaded by some test |

**14 fixtures, 14 with a dedicated test class.**

Fixture 011 was rewritten during this change. It previously asserted that the
skill *should* configure Playwright to "connect to the Tauri WebView port" —
locking in an unimplementable answer. It now asserts the WebdriverIO route and
carries a `must_not_appear` list so the old guidance cannot return.

## Discovery Script Tests (`test_discover_script.py`)

Real integration tests: each builds a throwaway repository and runs
`discover_e2e_needs.sh` against it. This closes the former known gap
"discover_e2e_needs.sh not integration-tested".

| Class | Covers |
|-------|--------|
| TestScanNeverAborts | empty dir, Makefile with/without an e2e target, bad root → exit 2, all report fields present |
| TestNoFalseBlockers | baseURL in config, missing account is an unknown not a blocker, webServer satisfies base URL, fully-configured repo is `ready` |
| TestProjectClassification | Go with/without entrypoint, root main.go, Python, Rust, Tauri, existing Cypress, exact-vs-substring dep matching, Next.js App Router, monorepo |
| TestSecretHandling | report never contains a secret value; `.env.example` yields `declared`, a filled template still only `declared`, empty value in a real `.env` is `declared`, real value is `available`, quoted and `export`-prefixed values parsed, absent variable is `missing`, legend emitted |
| TestEnvStateDrivesVerdict | `declared`-only → `needs_confirmation` (not `ready`, not `blocked`); no evidence → `blocked`; baseURL from config → verify-target unknown; user without password flagged; fully available → `ready` |
| TestExistingTestDiscovery | spec counting, Go E2E counting, visual-regression detection, CI lane detection |

`test_makefile_without_e2e_target` is the regression test for the `set -e` abort:
`grep` exits 1 when no target matches, which under `set -e` killed the script
mid-report — output that reads as "found nothing else" rather than "scan died".

Tests scrub inherited `E2E_*` variables so a developer's shell cannot flip a
verdict.

## Remaining Gaps

Stated plainly rather than rounded up to "100%".

1. **No LLM-in-the-loop evaluation.** `lint_e2e_spec.py` grades *given* spec
   source deterministically, and the golden fixtures assert the skill contains
   the rules that should fire — but nothing invokes a model on a prompt and
   grades its output. Closing this needs an eval harness outside this suite.
2. **The grader is heuristic, not a parser.** It cannot follow helper
   indirection, resolve imported constants, or see through a page object. It is
   built to prefer a miss over a false alarm, so a clean report is weaker
   evidence than a dirty one.
3. **The skill's TypeScript examples are never executed or type-checked.** No
   browser runs in CI here. Two partial exceptions: the Go golden example is
   compile-verified (`go vet`, `go build -tags e2e`, `gofmt`), and
   `verify_hook_semantics.sh` runs a real Playwright suite — but only for hook
   semantics, on purpose-written specs, not on the examples the skill ships.
4. **Version facts are pinned, not polled.** `TestVersionFactsAreCorrect` locks
   in values verified against upstream on 2026-07-29, and the hook matrix was
   measured on Playwright 1.62.0. Both detect local edits, not new Playwright
   releases. Re-verify — including `verify_hook_semantics.sh` — when bumping the
   targeted version.
5. **Agent Browser commands are unverified.** The command reference is
   documentation only; no test confirms the CLI's actual surface.

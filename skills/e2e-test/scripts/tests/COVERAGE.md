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
| `test_skill_contract.py` | 172 |
| `test_golden_scenarios.py` | 54 |
| `test_discover_script.py` | 44 |
| **Total** | **270** |

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
3. **Generated Playwright code is never executed.** No browser runs in CI here.
   TypeScript examples are not type-checked; the Go golden example *is*
   compile-verified (`go vet`, `go build -tags e2e`, `gofmt`).
4. **Version facts are pinned, not polled.** `TestVersionFactsAreCorrect` locks
   in values verified against upstream on 2026-07-29. It detects local edits,
   not new Playwright releases. Re-verify when bumping guidance.
5. **Agent Browser commands are unverified.** The command reference is
   documentation only; no test confirms the CLI's actual surface.

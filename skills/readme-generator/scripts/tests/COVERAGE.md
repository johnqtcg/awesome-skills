# readme-generator Skill — Test Coverage Matrix

**Total: 263 tests** — 110 contract + 43 golden-scenario + 42 discovery-behavioral +
68 forward-eval. Five of the 68 are skipped unless `README_GEN_EVAL_CMD` is set.

These numbers are pinned by `test_skill_contract.py::TestCoverageDocIsCurrent`, which
counts the live suite and fails when this file drifts. The previous version of this
document claimed 151 tests and documented a `TestAgentsConfig` class that did not exist —
a stale coverage doc reads as coverage, so it is now machine-checked.

## What each layer can and cannot prove

| Layer | Proves | Does **not** prove |
|-------|--------|--------------------|
| Contract (`test_skill_contract.py`) | The skill documents a rule, references resolve, templates satisfy their own matrix | That a model follows any of it |
| Golden scenarios (`test_golden_scenarios.py`) | Fixture metadata is self-consistent and the concepts it names exist in the skill | Anything about produced output |
| Discovery behavior (`test_discovery_script.py`) | The router classifies 20+ real repo shapes correctly and never dies mid-probe | — (this layer runs real code against real fixtures) |
| Forward eval (`test_forward_eval.py`) | The grader distinguishes a grounded README from a fabricated one, for stated reasons | That a **live model** produces grounded READMEs — that needs layer 4c, opt-in |

Layers 3 and 4 execute code against materialized repositories. Layers 1 and 2 are
document-structure checks; they are cheap and catch drift, but they are not evidence of
behavior and are not counted as such here.

**`GoldenExamplesSurviveTheGrader` closes the tightest loop available without a model**:
the golden examples are what the model is *shown* as calibrated output, and the grader is
what its output is *checked* with. If an exemplar fails the grader, the skill teaches
something it then penalises. On its first run this caught two real defects in
`golden-library.md` — commentary that had leaked inside the fenced README (modelling the
meta-language the skill forbids, and citing a `testdata/` path the example repo lacks), and
a missing Documentation Maintenance section that Template B had gained but the golden
example had not.

## 1. Contract Tests (`test_skill_contract.py`) — 110

| # | Class | Tests | Covers |
|---|-------|-------|--------|
| 1 | TestFrontmatter | 3 | Name, description keywords, description length |
| 2 | TestGates | 6 | 5 gates present, gate count, project types listed |
| 3 | TestAntiExamples | 4 | Section exists, BAD/GOOD count ≥ 7, topic coverage, code blocks |
| 4 | TestScorecard | 8 | 3-Tier section, tier thresholds, all 14 items, output format |
| 5 | TestSelectiveLoading | 3 | Section exists, all refs listed, loading conditions |
| 6 | TestBadgeStrategy | 3 | Section, detection order, private-repo fallback |
| 7 | TestEvidenceMapping | 3 | Section, table format, `Not found in repo` rule |
| 8 | TestLightweightMode | 3 | Section, trigger conditions, required sections |
| 9 | TestChineseBilingual | 3 | Section, keep-English rule, heading style |
| 10 | TestUpdateTriggers | 3 | SKILL.md routes to the matrix; matrix lives in checklist.md with ≥ 10 rows |
| 11 | TestTemplatesRef | 4 | File exists, 5 templates, depth, no verification status |
| 12 | TestGoldenExamplesRef | 7 | File, ToC, ≥ 5 examples, types, evidence mappings, repo signals, depth |
| 13 | TestCommandPriorityRef | 6 | File, priority ladder, language patterns, conflict resolution, extraction, depth |
| 14 | TestChecklistRef | 6 | File, 3 phases, mistakes by type, refactor checklist, trigger matrix, depth |
| 15 | TestStructuralIntegrity | 7 | Workflow steps, evidence targets, monorepo, navigation, E2E, output style, community files |
| 16 | TestOutputContract | 4 | Section, 9 mandatory fields, JSON block, field count |
| 17 | TestDiscoverScript | 7 | Exists, executable, referenced in skill/loading/workflow, 10 dimensions, TSV |
| 18 | TestVersionRules | 7 | Section, Go/Node/Python/Rust rules, How to Apply, depth |
| 19 | TestDegradationPatterns | 5 | Section, 4 levels, degraded in skill, depth, evidence column |
| 20 | TestCrossCuttingIntegrity | 5 | SKILL.md ≤ 600 and ≤ 400 lines, refs exist, no orphaned reference, total content ≥ 1500 |
| 21 | TestTemplateRequiredSections | 5 | Each template satisfies its type's matrix; no foreign sections; License fallback present; no verification language |
| 22 | TestLintReadmeScript | 3 | Linter exists, wired into the workflow, every finding code has a severity |
| 23 | TestCoverageDocIsCurrent | 3 | This file's totals match the live suite; no phantom class names |
| 24 | TestGoldenSectionOrders | 2 | Golden section orders satisfy the same per-type matrix |

## 2. Golden Scenario Tests (`test_golden_scenarios.py`) — 43

Nine fixtures (`golden/00*.json`) describing routing intent per scenario: Go service,
Go library, CLI, monorepo, lightweight internal, private service, Chinese output, stale-README
refactor, degraded no-build.

**Known limitation, stated plainly:** this layer checks that a fixture's declared
expectations are internally consistent and that the concepts it names appear in the skill.
It does not generate or grade a README. That is what layer 4 is for; these fixtures remain
useful as a routing-intent catalogue and as the source of scenario coverage.

## 3. Discovery Script Behavioral Tests (`test_discovery_script.py`) — 42

| # | Class | Tests | Covers |
|---|-------|-------|--------|
| 1 | DiscoveryScriptBehavior | 7 | Empty dir, empty Makefile, comment-only `.env.example`, `.yaml`-only workflows, Go service, GPL license, TSV key spelling — exit 0 + verdict in every case |
| 2 | DiscoveryScriptContract | 3 | No errexit/pipefail, `set -u` present, explicit trailing `exit 0` |
| 3 | TestRoutingSync | 2 | SKILL.md routing prose ↔ script emissions, both directions |
| 4 | RoutingRegressions | 30 | Every shape the pre-audit router got wrong, plus the lightweight-eligibility boundary (below) |

`RoutingRegressions` covers: Rust binary / library / workspace · Python package / console
script / Django · `packages/`-only monorepo · npm workspaces · single-`packages`-subdir
negative case · root `main.go` as binary · root `main.go` + `internal/` as service · `cmd/`
without `main.go` · Go library package entrypoint · `package.json` `bin` object · dependency
named `bin-links` (old grep false positive) · `directories.bin` (same) · malformed JSON ·
empty workflows dir · `LICENSE.md` type detection · zero-entrypoint blocker · `go.work` as a
build system · Cargo workspace under `crates/*` reaching READY.

Lightweight eligibility: discovery **never promotes on its own** — a public Go SDK
(`go.mod` + `pkg/`, no CI, few dirs) was being downgraded and losing Installation and API.
It reports `lightweight_eligible` plus a named blocker list (`unclassified`, `5+ top-level
dirs`, `CI present`, `deployment surface`, `public distribution surface` — where
`project_type=library` counts as a public surface by definition). The Audience Gate decides
and records it with `lint_readme.py --type=lightweight`, which is what keeps one value that
generation, the Output Contract, and the linter all read.

## 4. Forward Evaluation (`test_forward_eval.py`) — 68

Fixture repositories are JSON manifests (`forward_eval/*/repo.json`) materialized into a
temp dir per test — not files checked into `skills/`, which would have pytest collecting a
fixture's own `tests/test_core.py`.

| # | Class | Tests | Covers |
|---|-------|-------|--------|
| 4a | FixtureRoutingTest | 3 | Each fixture reaches the effective type, base type, and verdict its manifest declares; scan collects make targets, npm scripts, env vars, workflows |
| 4b | GoServiceGrading | 8 | good.md clean; bad.md raises R001/R003/R004/R005/R006/R007/R008; per-check positive and negative cases |
| 4b | NodeCliGrading | 6 | good.md clean; bad.md raises R002/R004/R005/R008/R010/R011/R012; npm script resolution; type-aware sections |
| 4b | PyLibraryGrading | 6 | good.md clean; bad.md raises R001/R004/R007/R008/R012; toolchain matching; path existence |
| 4b | LightweightGrading | 4 | Effective type is `lightweight` while base stays `cli`; a Template E README is not graded against Template C |
| 4b | RustWorkspaceGrading | 4 | `crates/*` workspace reaches READY with both modules as entrypoints; `cargo --workspace` accepted |
| 4b | FalsePassRegressions | 6 | The five ways a fabricated README scored PASS against v1 of the grader, plus primary-vs-secondary section severity |
| 4b | GraderPropertiesTest | 17 | Build outputs exempt, module paths exempt, slash-separated alternatives exempt, external-repo paths exempt, `scorecard` as topic vs self-report, prose backticks not command-checked, nested fences, severity → exit status |
| 4b | RequiredSectionSyncTest | 2 | SKILL.md matrix ↔ `lint_readme.REQUIRED_SECTIONS` |
| 4b | GoldenExamplesSurviveTheGrader | 3 | Each shipped `references/golden-<type>.md` README, linted against a repo built from that file's own Repo signals |
| 4c | LiveForwardEval | 5 | **Skipped by default.** One per fixture. Grades against the fixture's full `good` budget (zero findings), not just "no Critical" |
| 4d | LiveHarnessPlumbingTest | 4 | Stubbed writer runs end-to-end; a configured-but-broken command FAILs rather than skips; every scenario has a live test; the live budget forbids standard findings too |

### Grader check codes

| Code | Severity | Detects |
|------|----------|---------|
| R001 | critical | `make <target>` not in the Makefile; toolchain command with no matching manifest |
| R002 | critical | npm/yarn/pnpm script not in `package.json` |
| R003 | critical | Configuration variable absent from `.env.example` / no config source at all |
| R004 | critical | Cited path does not exist (build outputs and module paths exempt) |
| R005 | critical | Placeholder residue: `{VAR}`, `OWNER/REPO`, TODO/TBD/FIXME, `your-org` |
| R006 | standard | Verification-state or scorecard language in the README body |
| R007 | critical | Coverage % matching no committed target, benchmark numbers with no committed output, throughput, test counts, latency |
| R008 | critical | Badge whose evidence (workflow file, codecov config, LICENSE) is absent |
| R009 | **critical** | Primary entry path missing (Quick Start / Installation / Usage / Repository Overview, per type) — a reader cannot get started |
| R010 | standard | ToC label/anchor does not match its heading |
| R011 | standard | Double-language heading |
| R012 | standard | A non-primary required section is missing |
| R013 | standard | Project type undetermined — section checks did not run; result is `INCOMPLETE`, never `PASS` |

### Result states

`summarize()["result"]` is four-valued, because three different situations were previously
all reported as `PASS`:

| Result | Meaning | Exit status |
|---|---|---|
| `FAIL` | a critical finding — the README asserts what the repo does not support | 1 |
| `INCOMPLETE` | R013: project type unknown, so structure was never graded | 0 |
| `WARN` | standard findings only — real defects, none of them vetoing | 0 |
| `PASS` | checked, nothing found | 0 |

Exit status keys on `FAIL` alone: the skill's Standard tier tolerates up to two failures by
design, so a warning must not break a caller's gate — but it must not read as clean either.

## Known Gaps

1. **`LiveForwardEval` is skipped by default — this is the one remaining evidence gap.**
   Layers 1–3 and 4a/4b prove the rules are written, routing is correct, and the grader
   discriminates. `GoldenExamplesSurviveTheGrader` additionally proves the exemplars the
   model is *shown* pass the grader it is *checked* with. None of that shows a live model
   reliably produces a passing README; only 4c does.

   Running it needs an authenticated CLI. Attempted 2026-07-28 inside a sandboxed
   subprocess: `claude -p` returned `Not logged in · Please run /login`, so the run
   FAILed with "HARNESS FAULT" — which is the designed behaviour (a broken harness must
   not read as green), but it means the layer has not yet been executed against a real
   model. `run_regression.sh` prints the gap and the exact invocation.
2. Golden scenarios (layer 2) remain document-level; layer 4 supersedes them for behavior.
3. The grader checks command *existence*, not command *correctness* — a `make test` that is
   defined but broken passes R001. Nothing here executes the documented commands.
4. **The linter is a floor, not the Critical tier.** It catches high-frequency C1/C2
   violations; a plausible-but-wrong prose claim, or a structure description that is stale
   rather than invented, passes clean. SKILL.md states this where the scorecard is defined.
5. Java, Ruby, and .NET have no routing branch and no command snippets.

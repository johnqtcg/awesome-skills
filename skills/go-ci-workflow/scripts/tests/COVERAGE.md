# Go-CI-Workflow Skill — Test Coverage Matrix

Counts below are re-derived from the suite, not hand-maintained. Re-run
`python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v` after any
change and update the table.

## Test Files and Counts

| File | Tests | What it validates |
|------|------:|-------------------|
| `test_skill_contract.py` | 82 | Frontmatter, SKILL.md structure, per-gate body content, all reference-file contracts, action/tool/Go-version currency, cross-document timeout consistency, cross-reference integrity, run-regression fail-closed **and success-path** behaviour, discovery-script surface |
| `test_golden_yaml.py` | 19 | Structural + semantic validation of **every** YAML block in **every** reference (+ actionlint when installed) |
| `test_discover_script.py` | 20 | `discover_ci_needs.sh` behaviour against real fixture repos, including the silent-corruption paths: apostrophes, unreadable directories, `.git` leakage, bad roots, GNUmakefile |
| `test_golden_scenarios.py` | 12 | 12 golden fixtures, each bound to the SKILL.md section and the scenario-scoped references that must honour it |
| `test_live_eval_harness.py` | 27 | The live A/B harness and its grader — offline: scenario derivation, treatment assertion, good-vs-bad discrimination, control axes |
| **Total** | **160** | 1 test (`test_actionlint_when_available`) skips when `actionlint` is not on PATH |

## Discriminating Power — Measured, Not Claimed

A test count is not a guarantee. The suite is graded by mutation: inject a
defect, confirm the suite goes red. **The harness is committed** —
`scripts/mutation_sweep.py` — so every number below is reproducible:

```bash
python3 scripts/mutation_sweep.py --verify   # anchors only
python3 scripts/mutation_sweep.py            # full sweep
```

Measured 2026-09-17: **27 of 29 killed, 2 expected survivors, 0 errored**, every
outcome matching its registered expectation.

**Read that number correctly.** The committed registry is a *regression*
harness, not an unbiased estimate of discriminating power: its mutations were
chosen from defects actually found, so a high kill rate says those specific
defects cannot come back — it does not say the suite would catch an arbitrary
new one. An independent audit on 2026-09-17 ran a broader 58-mutation set and
measured roughly **50% fail-open overall, and ~91% on pure prose-semantic
inversions**, while the structural/YAML/version-pin domain measured near 0%.
Both figures are true; they answer different questions. The two registered
`SURVIVE` entries exist to keep that honest — they are prose inversions the
suite deliberately does not guard, and a sweep reporting them as killed would
mean someone had added a phrase-matcher that will eventually deceive itself.

Caught, verified by the sweep: a secret handed to an unguarded `pull_request`
job; a fork guard inverted in YAML or prose; `contents: read` → `write`;
`cancel-in-progress` ungated, set to `true`, or **inverted to `!=`**; a deleted
`concurrency` block; a gutted gate body; a stale action major or tool pin, in
YAML or in prose; an unattributed `@vN`; an invalid runner label or permission
scope; a broken `.md` cross-reference; pruning regressions in the probe; **a
job discovery filter keyed on the field it validates**; **a stale or
end-of-life Go matrix**; **timeout prose drifting from the §8 table**; **the
two shape taxonomies drifting apart**; **a runner backdoor, a removed test-count
floor, or a removed skip ceiling**; **§3's setup-go cache claim reverting** and
**§6's self-hosted trust-boundary content being gutted**.

Deliberately **not** caught: renaming a gate heading's style (`### 4)` →
`####`). The suite matches gate *names*, which are a real contract the golden
fixtures key on, but no longer pins the heading prefix — an earlier version
broke on harmless restyling while ignoring two empty gate bodies.

## What Each Layer Proves — and What It Does Not

The 160 tests validate the skill's **authored artifacts** (SKILL.md,
references, scripts). They are deterministic and offline, and they do **not**
measure generation quality. That measurement lives in `scripts/run_live_eval.sh`,
which is a separate, human-run layer — see *Live evaluation* below.

### `test_skill_contract.py` (82)

- `TestFrontmatter` — `name`/`description` present; no unsupported frontmatter keys.
- `TestSkillMdStructure` — 350-line budget, 5 mandatory gates (matched by name,
  not heading style), **per-gate body assertions scoped to each gate's own
  section**, 6 repository shapes, execution paths, output contract,
  cross-reference to `$go-makefile-writer`.
- `TestWorkflowQualityGuide` — 15 baseline sections, §16 action pinning (both
  tiers, Dependabot, re-verify step), §11 tool-pin table with its own re-verify
  instruction, `cache-dependency-path` guidance.
- `TestAdvancedPatterns` — 9 advanced sections, and §6 (a named Gate 3 load
  target) must carry the trust-boundary facts, scoped to §6's own body: the
  public-repository prohibition, why per-job destruction is not a boundary,
  runner groups, and `GITHUB_TOKEN` exposure. It shipped as nine content-free
  bullets that every heading-level assertion happily passed.
- `TestRepositoryShapes` — 6 shapes; multi-module matrix sets
  `cache-dependency-path`; `go.work` documented; path-filter job carries
  `pull-requests: read`; path-filter × required-status-check interaction.
- `TestActionVersionCurrency` — §16 is the single source of truth; every
  `uses:` pin must match it; denylist against known-stale majors.
- `TestToolVersionCurrency` — §11 is the single source of truth for `go install`
  pins. Checks the install paths, the versions, prose mentions of a tool
  version, and rejects any `@vN` written without naming its action.
- `TestGoVersionCurrency` — §13 is the single source of truth for Go matrix
  majors; every literal must match it; declared majors may not be end-of-life.
  Go ships a major every ~6 months, faster than actions or tools, and this was
  the one pin class with no re-verify discipline.
- `TestTimeoutConsistency` — the §8 timeout table is the source of truth and
  the always-loaded prose is derived from it, not a second hardcoded copy.
- `TestCrossReferences` — every `` `*.md` `` pointer resolves; every shipped
  reference is named by SKILL.md.
- `TestRunRegression` — runner is fail-closed; a failing validator aborts with
  its exit code; and the **success path** is executed against a generated stub
  suite (no recursion): a clean run passes and names the tests it ran, a
  collapsed discovery fails, unaccounted skips fail, and a skip-flavoured
  environment variable has no effect. Until these, only the abort path had
  ever run, so a backdoor around the test step was undetectable.
- `TestDiscoveryScript` — 8 categories; pruning, `go-workspace`, `toolchain`,
  app-vs-library signals present in the script source.

### `test_golden_yaml.py` (19)

Extracts every ```yaml``` block from **every** `references/*.md` and classifies
it before applying rules (complete workflow = `jobs:` **and** a trigger;
otherwise a fragment). Asserts: parses; workflow has name + trigger + jobs;
every job has `runs-on` + numeric `timeout-minutes`; runner labels are real;
permissions declared, scopes valid, `contents: write` absent; `cancel-in-progress`
event-gated everywhere; `pull_request` workflows declare `concurrency`; fork
guards are `==` not `!=`, read from the **parsed** `if:`; secrets on a
`pull_request` workflow are fork-guarded; no `@latest`; no hardcoded Go version
outside a matrix; declared Go versions are plausible; matrix/subdir setup-go
sets `cache-dependency-path`. With `actionlint` installed it additionally lints
each complete workflow.

`workflow_call` workflows are exempt from the `name` and `permissions` rules —
they inherit both from the caller.

Job discovery keys off `steps:`/`uses:` and excludes composite actions via
`runs.using`. It must **never** key off `runs-on`: doing so made the rule its
own precondition, so a job missing `runs-on` was dropped from the check that
requires it — `repository-shapes.md` §5 shipped a `docker-build` job GitHub
would reject, exempt because it was more broken. Pinned by
`test_jobmap_fallback_is_not_keyed_on_the_field_it_validates`, which uses
synthetic input so a compliant corpus cannot mask a revert.

### `test_discover_script.py` (20)

Executes the probe against real temp repos: Makefile without ci targets, no
`scripts/` dir, go.mod-only, empty, bad root, vendored modules, dependency
trees across **all** probes, monorepo Dockerfiles below depth 2, `go.work`,
`toolchain`, app/library heuristic, rich repo firing every category, TSV shape.

### `test_golden_scenarios.py` (12)

Every assertion binds a fixture field to the skill text that must honour it:
declared shapes/gates/execution paths/output fields must exist in the SKILL.md
section that owns them, and parity levels must sit on the fallback ladder.
`skill_rules_that_must_fire` is searched only in SKILL.md plus the references
that scenario's `load_references` declares — so a rule living in a file the
skill would not open for that scenario is a visible gap, not a silent pass.
A guard also rejects a fixture that declares conditional references but whose
rules are all satisfiable by SKILL.md alone (it would be testing nothing).

## Live Evaluation — the generation layer

`scripts/run_live_eval.sh` is the only layer that puts a model in the loop. It
runs the 12 golden fixtures through a with-skill and a without-skill arm and
grades the responses structurally, on four axes reported separately: **shape**
(Gate 1 vocabulary), **parity** (every job labelled `make target` / `repo task` /
`inline fallback`), **contract** (the 9 Output Contract items in a label
position), **integrity** (the `Not run in this environment` literal with a reason
and next commands). A single blended number would hide which axis moved.

It requires an authenticated CLI, supplied via `GO_CI_WORKFLOW_EVAL_CMD`, so it
does not run in CI and does not run from inside another Claude session — a
nested `claude -p` does not inherit credentials.

Three properties make the result trustworthy rather than decorative:

- **A setup failure exits 3 and grades nothing.** A missing command, an empty
  response, or an installation leak is not a score of zero — those are
  indistinguishable in a blended report, and a zero reads as "the skill
  failed".
- **The with-skill arm asserts its treatment.** The response must carry
  vocabulary only SKILL.md defines (≥2 gate names, ≥1 execution-path label). If
  the skill did not actually load, the arm aborts as a setup failure instead of
  silently becoming a second control arm and producing a bogus null result.
- **The grader is proven to discriminate.** `--dry-run` replays three committed
  recordings with no model: a good response, a defective twin differing only in
  two planted defects, and an untreated response. The planted axes must each
  move by a full 1.00 **and the two control axes must stay exactly equal** — so
  the grader is shown to respond to the defect rather than to length or tone.
  The untreated recording must trigger the abort. A grader that cannot fail is
  worthless, and a treatment guard that is never exercised is not a guard.

`scripts/live_eval_grader.py` is a real file, not a heredoc. It began as a
960-line Python block embedded in the bash script, which could not be linted or
imported and which the tests had to carve out of the shell source before they
could exercise it.

## Coverage Summary

| Category | Total | Tested | Coverage |
|---------|-------|--------|----------|
| Mandatory gates (heading **and** body) | 5 | 5 | 100% |
| Repository shapes | 6 | 6 | 100% |
| Job types (core/docker/integration/e2e/vuln/static) | 6 | 6 | 100% |
| Trigger types (PR/push/schedule/workflow_call) | 4 | 4 | 100% |
| Execution paths (make/repo-task/inline) | 3 | 3 | 100% |
| WQG sections (incl. §11 tool pins, §16 action pins) | 16 | 16 | 100% |
| Advanced pattern sections | 9 | 9 | 100% |
| Golden fixtures (scenario-scoped) | 12 | 12 | 100% |
| Reference files with YAML validated | 6 | 6 | 100% |
| YAML blocks parsed | 44 | 44 | 100% |
| Discover-script categories | 8 | 8 | 100% |

## Known Gaps

| Gap | Priority | Notes |
|-----|----------|-------|
| Prose semantics can still be inverted | **High** | Rewriting a guidance sentence to say the opposite while keeping its keywords. Measured on 2026-09-17 at ~91% survival across 22 such mutations — including inverting the secret fork-gate rule, endorsing `pull_request_target` with secrets, inverting the `permissions`-replacement rule, and hollowing out the Local Parity and Execution Integrity gates. An earlier revision of this file called it "the one mutation that survives"; that understated it by more than tenfold. Two representative inversions are registered in `mutation_sweep.py` with `expected=SURVIVE` so the gap stays visible rather than being quietly claimed as covered. A general phrase-matcher is not the fix — it is satisfied by any rewrite reusing the words. What does work, and is applied to the two highest-stakes claims (§3 setup-go cache, §6 self-hosted trust boundary), is binding a specific known defect to a section-scoped assertion. Everything else is a code-review responsibility. |
| No measured generation result yet | **High** | `scripts/run_live_eval.sh` now exists and its grader is verified offline, but **no A/B measurement has been recorded**: it needs an authenticated terminal, which a nested session cannot provide. Until someone runs it and commits the numbers, nothing here says the skill improves a model's output — only that the artifacts are internally sound. Do not read "160 tests" or "27/29 killed" as generation quality. |
| actionlint is optional, not required | Medium | Without it, `${{ }}` expression and context semantics are unverified; the run says so (WARNING + qualified success line). **First actually executed 2026-09-17**, and it failed immediately for two reasons unrelated to the YAML: the test linted illustrative fragments as if they were workflows, and invoking bare `actionlint` with `cwd=tmp` exits 3 ("no project was found") before linting anything — so the test could never have passed. Both fixed; all 6 complete workflows lint clean. Install the release binary if `go install` is blocked by a proxy. |
| Versions are point-in-time | Low | Action majors verified 2026-07-16; tool pins 2026-09-16; Go majors and setup-go cache behaviour 2026-09-17. The currency tests keep examples internally consistent with §11/§16 but cannot detect that upstream shipped a newer release — re-verify at generation time. |
| discover script is a probe, not a classifier | Low | app-vs-library is a heuristic; Taskfile/mage task bodies, CGO, codegen, private modules and cross-platform needs are not inferred; Dockerfiles are found only 4 levels deep; only the documented PRUNE list is excluded. All limits are declared in the script's own LIMITS block, and SKILL.md requires manual confirmation. |

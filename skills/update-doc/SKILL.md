---
name: update-doc
description: Keep repository documentation synchronized with the latest code. Use when updating README/docs/codemaps after code changes, running docs-drift checks, or producing scoped evidence-backed doc patches for service/library/CLI/monorepo projects.
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Grep, Glob, Bash(git diff*), Bash(git log*), Bash(git ls-files*), Bash(git rev-parse*), Bash(rg *), Bash(ls *), Bash(head *), Bash(grep *), Bash(bash ${CLAUDE_SKILL_DIR}/scripts/discover_doc_scope.sh *), Bash(bash ${CLAUDE_SKILL_DIR}/scripts/run_regression.sh *)
---

# Update Docs

Synchronize documentation with repository evidence and avoid stale or speculative content.

## Quick Reference

| If you need to… | Go to |
|---|---|
| Update README/docs after a code change (default workflow) | §Pre-Update Gates → §Output Mode Routing → §Standard Workflow |
| Find what actually changed | §1) Scope Discovery |
| Decide which command belongs in the doc | §4) Command Source Resolution |
| Choose the right doc structure for project type | §Project-Type Guidance + Load `references/project-routing.md` |
| Get the per-language evidence commands | Load `references/evidence-commands.md` |
| Check docs-drift: find gaps between code and docs | §Quality Scorecard (12 Checks) + Load `references/update-doc.md` |
| Add CI checks to catch docs drift automatically | Load `references/ci-drift.md` |
| Understand what to mark vs. invent (`Not found in repo`) | §Hard Rules |

## Hard Rules

- Use repository files as the only source of truth.
- Mark missing information as `Not found in repo`.
- Do not invent APIs, routes, env vars, ports, jobs, or dependencies.
- Prefer minimal patches by default; preserve existing doc structure unless user requests restructure.
- Use diff-scoped updates first; avoid unrelated bulk rewrites.
- Keep output scannable: headings + concise bullets + short runnable command blocks.
- Keep internal workflow markers out of user-facing docs by default. Verification labels, scorecards, and evidence tables belong in the assistant response unless the user explicitly wants them in the document.
- Do not add self-explanatory audience labels or author commentary to top-level docs unless they materially help readers.

## Pre-Update Gates (Mandatory)

### 1) Scope Discovery

Run the bundled discovery script before reading any document:

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/discover_doc_scope.sh" --base <ref>
```

`${CLAUDE_SKILL_DIR}` expands to this skill's own directory. Two separate version
gates apply, and they are not the same number:

| Substituted in | Since | Source |
|---|---|---|
| SKILL.md body content | v2.1.69 | CHANGELOG |
| `allowed-tools` Bash rules | v2.1.129 | Frontmatter reference docs |

So on v2.1.69–v2.1.128 the command above resolves correctly but the matching grant
stays a literal `${CLAUDE_SKILL_DIR}` string and never matches, and the run prompts
for permission. Below v2.1.69 neither resolves; substitute the real path by hand.
Prompting is a degradation, not an error — the alternative, a `Bash(bash *script.sh*)`
wildcard, would match a same-named script anywhere on disk.

It reports the diff scope from four independent sources, the dominant language,
command-source priority, project-type signals, and the existing doc/CI inventory.

**A single `git diff --name-only` is not sufficient scope.** It shows only unstaged edits
to tracked files. Four sources must be reconciled:

| Source | Command | What is missed if skipped |
|---|---|---|
| Working tree | `git diff --name-only` | — |
| Staged | `git diff --cached --name-only` | anything already added to the index |
| Untracked | `git ls-files --others --exclude-standard` | every newly created file |
| Base range | `git diff --name-only <base>...HEAD` | everything already committed on the branch |

Take the union: a new module normally appears **only** in the untracked or base-range
set, which is exactly the change most likely to need new documentation.

`--name-only` reports an added file and a modified file identically, so that union
still cannot answer "did this introduce a new source file?" — the question §Output Mode
Routing turns on. The report answers it separately as `NEW_SOURCE:`, computed from adds
only (untracked, staged adds, `--diff-filter=A` over the base range) and filtered to
source extensions, so a new `.md` does not count.

Treat the run as valid only when the script exits 0 **and** its last line is `=== END ===`.
A truncated report means discovery failed; say so instead of proceeding on partial scope.

If `STATUS: DEGRADED_NO_GIT` or `BASE_REF: NOT_RESOLVED`, state that limitation in the
assistant response and fall back to explicit file evidence from the touched code paths.

### 2) Audience and Language Gate

Before editing docs, determine:

- target readers (contributors/operators/API consumers/end users)
- output language (Chinese/English/bilingual)

If user did not specify:

- follow current repository doc language
- keep assumptions in the assistant response; only add them to docs when they materially help readers

### 3) Project Type Routing

Classify the repo and choose structure accordingly. The discovery script's `LIKELY:` and
`SCORES:` lines are the starting signal, not the verdict — confirm against actual layout.

- Service/backend app
- Library/SDK
- CLI tool
- Monorepo

If uncertain, state the assumption and proceed with the best-fit template.

### 4) Command Source Resolution

Every command printed in a document must come from the highest-priority source that
actually defines **that command**.

Read `RESOLVED:`, not `PRIMARY:`. `PRIMARY:` names the repo's dominant wrapper and is
a repo-level answer; it says nothing about where any particular command lives. A
Makefile holding only a `lint` target still makes `PRIMARY: makefile` while
`npm run build` remains the only real build command:

```
PRIMARY: makefile
RESOLVED:
  build: package-scripts (npm run build)
  test: package-scripts (npm run test)
  lint: makefile (make lint)
  install: native (npm install)
```

Document each command from its own resolved source. In a workspace, also read
`MODULES:` — a root wrapper frequently covers only some modules, and documenting the
root command for a module it does not apply to is the same defect one level down.

The ladder each kind is resolved against:

| Priority | Source | Use when |
|---|---|---|
| 1 | `Makefile` / `GNUmakefile` | any target exists — document `make <target>`, not the command it wraps |
| 2 | `Taskfile.yml` / `justfile` | repo uses a task runner instead of make |
| 3 | `package.json` `scripts` | Node repos — document `npm run <script>` |
| 4 | Native toolchain (`go test ./...`, `cargo build`, `pytest`) | no wrapper exists |
| 5 | CI workflow | nothing above defines it, but CI runs it — cite the workflow path |

Rules:

- When a wrapper exists **for that command**, document the wrapper. `make test` surviving an internal refactor is the entire point of the wrapper.
- When only CI defines a command, document it and cite the workflow file so readers can see where it is authoritative.
- When a kind resolves to `NOT_FOUND`, mark it `Not found in repo`. Do not fill the gap with a conventional default, and do not borrow the command from a different kind that did resolve.

### 5) Command Verifiability Gate

Never fabricate command validation.

- Commands are documented from their authoritative source (gate 4), not from executing them.
- If commands were executed, report that in the assistant response.
- If commands were not executed, do not inject `Not verified in this environment` into user-facing docs by default.
- Only add explicit verification wording to docs when the user requests it or the repo clearly uses internal verification notes as part of its style.

## Output Mode Routing

Resolve in order. **The first rule that fires wins** — do not evaluate later rules.

### Rule 1 — Full mode (escalation triggers)

Use full mode if **any** of these hold:

- codemap creation or restructure was requested
- README or docs were substantially reorganized
- a new API surface, runtime mode, deployment path, or config/env key is being documented
- more than one module is affected
- the user explicitly asked for an audit or scorecard

### Rule 2 — Lightweight mode

Use lightweight mode only if **all** of these hold:

- at most 2 doc files change
- no codemap output was requested
- the change is confined to wording, a command refresh, a link fix, or a single section
- discovery reports `NEW_SOURCE: 0` (do not infer this from `TOTAL_UNIQUE` — a modified file and an added file look the same there)

### Rule 3 — Default

Anything that matches neither rule uses full mode.

Escalation is one-way. If editing expands past the discovered scope mid-task, switch to
full mode and say so. Never downgrade from full to lightweight.

## Anti-Patterns

Avoid these common documentation-update failures:

- Copying assistant-side reporting into docs, such as verification-state labels, evidence tables, or scorecards.
- Making README more "complete" while making it worse as a homepage, for example by pushing install and quick start below contributor-only workflows.
- Deleting useful navigation from a long README in the name of simplification.
- Adding author-explanatory prose (`target readers`, `this document is for...`) when the document already self-explains through title and opening value proposition.
- Updating only isolated output examples for generator-style tools without preserving the input -> result -> output-shape reader path.
- Scoping the update from unstaged changes alone, so a newly added module is documented nowhere.

## Standard Workflow

1. Run scope discovery
   - Union of the four diff sources; record `NEW_SOURCE`, `DOMINANT`, `RESOLVED`, `LIKELY`.
   - `PRIMARY` is a repo-level summary only. Never document a command from it.
2. Confirm scope
   - Identify target docs (`README.md`, `docs/*`, `docs/CODEMAPS/*`, module READMEs).
   - Apply §Output Mode Routing to decide patch vs full rewrite.
3. Gather evidence from code
   - Load `references/evidence-commands.md` and run the block matching `DOMINANT`.
   - Entrypoints, business layers, config/env, runtime/deploy/quality scripts, CI workflows.
4. Build doc-evidence map
   - Every changed section maps to concrete file evidence with a path and line.
   - Unknowns remain `Not found in repo`.
5. Apply project-type template rules
   - Service/library/CLI/monorepo structure rules.
6. Update docs
   - Edit only impacted sections unless broader restructure was requested.
   - Preserve the primary reader path (for README: homepage first, reference second) unless the user asked for a deeper restructure.
7. Validate consistency
   - Mentioned paths exist.
   - Commands come from the resolved source and are syntactically valid.
   - Links/anchors resolve.
   - Terminology/path style is consistent.
   - Navigation was preserved or improved for long docs.
8. Add drift guardrails
   - Recommend or update CI checks for docs drift/link validity/lint where applicable.
9. Deliver result in the routed output mode.

## Project-Type Guidance

### Service / Backend

Prioritize:

- runtime modes (api/worker/cron)
- environment/config behavior
- ops run commands

### Library / SDK

Prioritize:

- install and usage examples
- public API surface
- compatibility/version notes

### CLI Tool

Prioritize:

- install and invocation examples
- flag/options behavior
- exit/error behavior (if evidence exists)
- an end-to-end usage example that shows input -> resulting file/output -> output shape when evidence exists

### Monorepo

Prioritize:

- root overview + module index table
- links to submodule docs
- per-module language and command source when the repo is polyglot
- avoid dumping complete tree for each package

## README UX Rules

For top-level README updates, optimize for reader flow:

1. value proposition before implementation detail
2. install and quick start before maintainer workflows
3. a compact table of contents for long docs
4. end-to-end examples before deep reference sections

Do not remove a useful table of contents just to shorten the file. Compress it to major sections if needed.

## Codemap Output Contract (When Requested)

Create only evidence-backed codemap files:

- `docs/CODEMAPS/INDEX.md`
- `docs/CODEMAPS/backend.md`
- `docs/CODEMAPS/integrations.md`
- `docs/CODEMAPS/workers.md` (if workers/cron/queues exist)
- `docs/CODEMAPS/frontend.md` (if frontend exists)
- `docs/CODEMAPS/database.md` (if schema evidence exists)

Each codemap should contain:

- Last updated date
- Entry points
- Key modules table (module/purpose/dependencies)
- Evidence-backed data flow
- External dependencies
- Cross-links to related docs

## CI Drift Guardrails

When applicable, recommend/maintain:

- markdown lint checks
- link checker
- docs drift check tied to changed code paths
- README/codemap ownership note (who updates and when)

If repo has no doc CI, mark as gap and provide minimal next-step commands.

## Self-Validation

This skill keeps its own contract test coverage for major workflow rules.

- Add or update regression tests under `scripts/tests/` when changing output contracts, routing rules, or agent-facing behavior.
- Run `bash "${CLAUDE_SKILL_DIR}/scripts/run_regression.sh"` after editing the skill.
- Keep tests focused on durable contract checks and behavior, not incidental wording.

## Output Examples

The examples below show the expected shape of each output mode. Adapt field values to the actual project.

### Lightweight Output Example

> Scenario: user updated a Go CLI's flag parsing; only `README.md` needs a command refresh.

---

**Changed files**
- `README.md` — updated `Usage` section, refreshed `--timeout` flag description

**Evidence map**

| Section changed | Source evidence |
|---|---|
| `Usage > --timeout flag` | `cmd/root.go:42` — `pflag.Duration("timeout", ...)` |
| `Usage > exit codes` | `cmd/root.go:87-91` — explicit `os.Exit` calls |

**Command verification**
- `scripts/discover_doc_scope.sh` — executed; `TOTAL_UNIQUE: 1` (`cmd/root.go`), `NEW_SOURCE: 0`
- Command source — `RESOLVED` gives `run: NOT_FOUND` (no Makefile target, no main package at the module root), so the invocation is documented from `cmd/root.go` and marked `Not found in repo` for a run wrapper

---

### Full Output Example

> Scenario: user added a background worker and a new `REDIS_URL` env var; README and codemaps need updating.

---

**Changed files**
- `README.md` — added `Worker` runtime mode, added `REDIS_URL` to env table
- `docs/CODEMAPS/workers.md` — created; documents new queue consumer

**Evidence map**

| Section changed | Source evidence |
|---|---|
| `Runtime modes > Worker` | `cmd/worker/main.go:1` — new entrypoint |
| `Config > REDIS_URL` | `internal/queue/client.go:14` — `os.Getenv("REDIS_URL")` |
| `Workers codemap > Entry point` | `cmd/worker/main.go:12` — `queue.NewConsumer(...)` |
| `Workers codemap > Dependencies` | `go.mod:9` — `github.com/redis/go-redis/v9` |

**Command verification**
- `scripts/discover_doc_scope.sh` — executed; `TOTAL_UNIQUE: 4`, `NEW_SOURCE: 1`; `cmd/worker/main.go` appeared only in the untracked set
- `rg -n "os\.Getenv" --glob '*.go'` — executed; found `REDIS_URL`, `DATABASE_URL`
- Worker startup command — not executed; `RESOLVED` gives `run: makefile (make run-worker)`, sourced from `Makefile:run-worker`

**Scorecard**

| # | Check | Result |
|---|---|---|
| 1 | Claims traceable to repo evidence | PASS |
| 2 | Audience/language assumptions explicit | PASS |
| 3 | Project type routing explicit | PASS — Service/backend |
| 4 | Diff scope reconciled across all four sources | PASS |
| 5 | Quick start/run path accurate | PASS |
| 6 | Config/env documented accurately | PASS |
| 7 | Command source priority respected | PASS — Makefile first |
| 8 | Command claims honest; no internal labels in docs | PASS |
| 9 | Structure and links/paths valid | PASS |
| 10 | Optional sections only where evidence exists | PASS |
| 11 | Drift guardrails documented | PASS |
| 12 | No fabricated claims; unknowns marked | PASS |

**Total: 12/12 — PASS**

**Open gaps**
- `Not found in repo`: worker shutdown/graceful-stop behavior — no evidence in source; omitted from docs

---

## Quality Scorecard (12 Checks)

Mark each item `PASS` / `FAIL` / `N/A (reason)`, then output `Total: X/12`.

`N/A` does not reduce the denominator. A check marked `N/A` must carry a reason and
counts as neither pass nor fail; report it as `Total: X/12 (Y N/A)` so the reader can
see the real coverage rather than an inflated ratio.

1. All major claims are traceable to repo evidence.
2. Audience/language assumptions are explicit.
3. Project type routing is explicit.
4. Diff scope was reconciled across working tree, staged, untracked, and base range (or the unavailable sources were named).
5. Quick start/run path is accurate for project type.
6. Config and environment behavior is documented accurately.
7. Command source priority is respected (see §4 Command Source Resolution).
8. Command claims are honest without leaking internal verification labels into user-facing docs by default.
9. Structure and links/paths are valid and non-contradictory.
10. Optional sections are included only when evidence exists.
11. Drift guardrails/maintenance checks are documented.
12. No fabricated claims; unknowns marked `Not found in repo`.

Decision rule:

- `PASS` if score >= 10/12 and no fabricated claims.
- Otherwise `FAIL` and list required follow-up fixes.

## Output Format

Report these in the assistant response, not inside the edited docs unless the user explicitly asks for them in-document:

### Lightweight output

- `Changed files`: updated files.
- `Evidence map`: table of changed section -> source files.
- `Command verification`: what was actually executed vs not executed.

Skip the 12-item scorecard by default. Include `Open gaps` only when the change exposes
a real missing source of truth.

### Full output

- `Changed files`: updated files.
- `Evidence map`: table of section -> source files.
- `Command verification`: what was actually executed vs not executed.
- `Scorecard`: 12-item PASS/FAIL/N/A + total.
- `Open gaps`: unresolved items labeled `Not found in repo`.

## Load References Selectively

When gathering code evidence for a specific language, or working in a polyglot repo:
→ Load `references/evidence-commands.md` for per-language entrypoint/route/config/dependency commands and the regex and shell pitfalls that silently produce empty evidence.

When determining the appropriate README/docs structure for a project type (service, library, CLI, monorepo):
→ Load `references/project-routing.md` for structure templates per project type with required sections, ordering, and the routing signals that distinguish them.

When synchronizing README or docs after code changes, or applying drift-safe update rules:
→ Load `references/update-doc.md` for drift-safe synchronization rules and scoped evidence collection patterns.

When adding CI guardrails for docs drift detection, or reviewing CI pipelines for doc coverage:
→ Load `references/ci-drift.md` for recommended CI checks (markdown linting, link validation, drift detection), ownership policies, and update timing rules.

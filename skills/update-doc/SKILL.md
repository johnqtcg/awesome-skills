---
name: update-doc
description: Keep repository documentation synchronized with the latest code. Use when updating README/docs/codemaps after code changes, running docs-drift checks, or producing scoped evidence-backed doc patches for service/library/CLI/monorepo projects.
---

# Update Docs

Synchronize documentation with repository evidence and avoid stale or speculative content.

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

### 1) Audience and Language Gate

Before editing docs, determine:

- target readers (contributors/operators/API consumers/end users)
- output language (Chinese/English/bilingual)

If user did not specify:

- follow current repository doc language
- keep assumptions in the assistant response; only add them to docs when they materially help readers

### 2) Project Type Routing

Classify repo first and choose structure accordingly:

- Service/backend app
- Library/SDK
- CLI tool
- Monorepo

If uncertain, state assumption and proceed with best-fit template.

### 3) Diff Scope Gate

Prioritize impacted docs inferred from changes.

- Use `git diff --name-only` (or user-specified base range) to infer impacted modules.
- Update only relevant docs first.
- Expand to broader rewrite only when requested.

If git range is unavailable, state that and use explicit file evidence from touched code paths.

### 4) Command Verifiability Gate

Never fabricate command validation.

- If commands were executed, report that in the assistant response.
- If commands were not executed, do not inject `Not verified in this environment` into user-facing docs by default.
- In the document itself, prefer accurate prerequisites, install paths, and evidence-backed commands.
- Only add explicit verification wording to docs when the user requests it or the repo clearly uses internal verification notes as part of its style.

## Anti-Patterns

Avoid these common documentation-update failures:

- Copying assistant-side reporting into docs, such as verification-state labels, evidence tables, or scorecards.
- Making README more "complete" while making it worse as a homepage, for example by pushing install and quick start below contributor-only workflows.
- Deleting useful navigation from a long README in the name of simplification.
- Adding author-explanatory prose (`target readers`, `this document is for...`) when the document already self-explains through title and opening value proposition.
- Updating only isolated output examples for generator-style tools without preserving the input -> result -> output-shape reader path.

## Standard Workflow

1. Confirm scope
   - Identify target docs (`README.md`, `docs/*`, `docs/CODEMAPS/*`, module READMEs).
   - Decide patch vs full rewrite.
2. Gather evidence from code
   - Entrypoints, business layers, config/env, runtime/deploy/quality scripts, CI workflows.
3. Build doc-evidence map
   - Every changed section maps to concrete file evidence.
   - Unknowns remain `Not found in repo`.
4. Apply project-type template rules
   - Service/library/CLI/monorepo structure rules.
5. Update docs
   - Edit only impacted sections unless broader restructure was requested.
   - Preserve the primary reader path for the document (for README: homepage first, reference second) unless the user asked for a deeper restructure.
6. Validate consistency
   - Mentioned paths exist.
   - Commands are syntactically valid.
   - Links/anchors resolve.
   - Terminology/path style is consistent.
   - Navigation was preserved or improved for long docs.
7. Add drift guardrails
   - Recommend or update CI checks for docs drift/link validity/lint where applicable.
8. Deliver result
   - Choose lightweight vs full output mode based on scope.

## Lightweight Output Mode

Use lightweight mode when the documentation change is narrow and low-risk.

Trigger conditions (any 2):

- only 1-2 doc files changed
- no codemap files requested
- no new runtime mode, API surface, or deployment path introduced
- change is a wording fix, command refresh, link fix, or small README/docs section update

Compact output should include:

- `Changed files`
- `Evidence map` for changed sections only
- `Command verification`

Rules:

- Skip the full 12-item scorecard by default.
- Only include `Open gaps` when the change exposes a real missing source of truth.
- Escalate to full output mode if the edit expands beyond the original diff scope.

## Full Output Mode

Use full output mode for broader or riskier documentation work.

Required triggers (any 1):

- codemap creation or restructure was requested
- README or docs were substantially reorganized
- multiple modules or runtime modes are affected
- the user explicitly asks for a full audit or scorecard

Full output should include:

- `Changed files`
- `Evidence map`
- `Command verification`
- `Scorecard`
- `Open gaps`

## Evidence Commands

### Step 0 — Detect Language

Run this first to determine which language-specific block to use below:

```bash
# infer impacted files from current changes
git diff --name-only

# detect dominant language by file count
rg --files | rg '\.(go|py|js|ts|java|rb|rs|cs)$' \
  | sed 's/.*\.//' | sort | uniq -c | sort -rn | head -5
```

Use the language with the highest file count to select the block below.
If mixed or unknown, fall back to **Generic**.

---

### Go

```bash
# entry points
rg -n "^func main\(" --glob '*.go'

# routes / handlers
rg -n "SetupRoutes|router|app\.(Get|Post|Put|Delete)" --glob '*.go'

# env and config loading
rg -n "os\.Getenv\(|viper\.|godotenv" --glob '*.go'

# dependency manifest
cat go.mod | head -20
```

### Python

```bash
# entry points
rg -n "^if __name__.*__main__" --glob '*.py'
rg -n "^app = (Flask|FastAPI|Django)" --glob '*.py'

# routes / handlers
rg -n "@(app|router)\.(get|post|put|delete|patch)\(" --glob '*.py'
rg -n "urlpatterns" --glob '*.py'

# env and config loading
rg -n "os\.environ|os\.getenv|dotenv|BaseSettings" --glob '*.py'

# dependency manifest
cat requirements.txt 2>/dev/null || cat pyproject.toml 2>/dev/null | head -30
```

### Node.js / TypeScript

```bash
# entry points
rg -n "\"main\"\s*:" package.json
rg -n "app\.listen\|createServer\|export default" --glob '*.{js,ts}'

# routes / handlers
rg -n "router\.(get|post|put|delete)\|app\.(get|post|put|delete)" --glob '*.{js,ts}'

# env and config loading
rg -n "process\.env\.|dotenv\.config\|z\.env" --glob '*.{js,ts}'

# dependency manifest
cat package.json | head -40
```

### Java / Spring Boot

```bash
# entry points
rg -n "@SpringBootApplication" --glob '*.java'

# routes / handlers
rg -n "@(GetMapping|PostMapping|PutMapping|DeleteMapping|RequestMapping)" --glob '*.java'

# env and config loading
rg -n "@Value\|@ConfigurationProperties\|application\.properties\|application\.yml" --glob '*.{java,yml,properties}'

# dependency manifest
cat pom.xml 2>/dev/null | grep -A2 '<dependency>' | head -40 \
  || cat build.gradle 2>/dev/null | head -30
```

### Generic (language-agnostic)

```bash
# entry points — look for common runner patterns
rg -n "main|entrypoint|bootstrap|start" --glob '!*.{md,lock,sum}' -l | head -10

# env and config loading
rg -n "ENV|CONFIG|DOTENV|\.env" --glob '!*.{md,lock}' | head -20

# dependency manifests
ls requirements.txt pyproject.toml package.json go.mod pom.xml build.gradle Gemfile 2>/dev/null

# CI/CD workflows
ls .github/workflows 2>/dev/null || ls .gitlab-ci.yml Jenkinsfile 2>/dev/null
```

---

### Always Run (any language)

```bash
# CI/CD workflows
ls .github/workflows 2>/dev/null

# existing docs to preserve structure
ls docs/ README.md CHANGELOG.md 2>/dev/null
```

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

## README UX Rules

For top-level README updates, optimize for reader flow:

1. value proposition before implementation detail
2. install and quick start before maintainer workflows
3. a compact table of contents for long docs
4. end-to-end examples before deep reference sections

Do not remove a useful table of contents just to shorten the file. Compress it to major sections if needed.

### Monorepo

Prioritize:

- root overview + module index table
- links to submodule docs
- avoid dumping complete tree for each package

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

This skill should keep its own contract test coverage for major workflow rules.

- Add or update regression tests under `scripts/tests/` when changing output contracts, routing rules, or agent-facing behavior.
- Run `bash "<path-to-skill>/scripts/run_regression.sh"` after editing the skill.
- Keep tests focused on durable contract checks, not incidental wording.

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
- `git diff --name-only` — executed; confirmed only `cmd/root.go` changed
- `go run . --help` — not executed in this environment; flag names verified from source

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
- `git diff --name-only` — executed; confirmed `cmd/worker/`, `internal/queue/` changed
- `rg -n "os.Getenv" --glob '*.go'` — executed; found `REDIS_URL`, `DATABASE_URL`
- Worker startup command — not executed; sourced from `Makefile:run-worker` target

**Scorecard**

| # | Check | Result |
|---|---|---|
| 1 | Claims traceable to repo evidence | PASS |
| 2 | Audience/language assumptions explicit | PASS |
| 3 | Project type routing explicit | PASS — Service/backend |
| 4 | Diff-scoped update applied | PASS |
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

1. All major claims are traceable to repo evidence.
2. Audience/language assumptions are explicit.
3. Project type routing is explicit.
4. Diff-scoped update strategy is applied (or justified if unavailable).
5. Quick start/run path is accurate for project type.
6. Config and environment behavior is documented accurately.
7. Command source priority is respected (Makefile/native/CI fallback).
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

### Full output

- `Changed files`: updated files.
- `Evidence map`: table of section -> source files.
- `Command verification`: what was actually executed vs not executed.
- `Scorecard`: 12-item PASS/FAIL/N/A + total.
- `Open gaps`: unresolved items labeled `Not found in repo`.

## References

- `references/update-doc.md`
- `references/project-routing.md`
- `references/ci-drift.md`

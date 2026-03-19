# README Generation Checklist

Comprehensive three-phase checklist for generating and reviewing README documents.

## Table of Contents

- [Phase 1: Before Drafting](#phase-1-before-drafting)
- [Phase 2: During Drafting](#phase-2-during-drafting)
- [Phase 3: Final Review](#phase-3-final-review)
- [Update Trigger Matrix](#update-trigger-matrix)
- [Common Mistakes by Project Type](#common-mistakes-by-project-type)
- [Checklist for Refactoring Existing README](#checklist-for-refactoring-existing-readme)

## Phase 1: Before Drafting

| # | Check | How to Verify |
|---|-------|--------------|
| 1 | Audience identified | Contributors / operators / API consumers / end users |
| 2 | Language decided | ZH / EN / bilingual; follows existing repo docs |
| 3 | Project type classified | Service / Library / CLI / Monorepo / Lightweight |
| 4 | Source-of-truth command files found | Makefile, package.json, go.mod, Cargo.toml, pyproject.toml |
| 5 | Required env/config files found | `.env.example`, `config/`, env vars in code |
| 6 | Community files detected | `LICENSE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CHANGELOG.md` |
| 7 | CI workflows inspected | `.github/workflows/*.yml` — extract badge URLs and test commands |
| 8 | Existing README reviewed | Note what to preserve, what is stale, what to remove |
| 9 | Repo visibility determined | Public / private — affects badge strategy |
| 10 | Lightweight mode evaluated | Check trigger conditions: < 5 dirs, no CI, no API, internal-only |

## Phase 2: During Drafting

| # | Check | Rule | Common Mistake |
|---|-------|------|----------------|
| 1 | Each section backed by repo evidence | No guessed content | Inventing config vars not in `.env.example` |
| 2 | Commands have prerequisite notes | Go version, tools, env vars | Assuming reader has all tools installed |
| 3 | Unverified commands handled honestly | Verification status in assistant response only | Writing "✅ Verified" inside README body |
| 4 | Unknown items marked explicitly | `Not found in repo` | Leaving section empty or guessing |
| 5 | Optional sections gated by evidence | Omit or mark N/A | Adding Architecture section with no diagram/evidence |
| 6 | Badges use real URLs from CI/coverage config | No placeholder badge URLs | Using `https://codecov.io/gh/OWNER/REPO` without codecov config |
| 7 | Chinese output preserves English technical terms | Package names, commands, paths stay English | Translating `goroutine` to 协程 in code blocks |
| 8 | LICENSE referenced or missing-note added | Link to file or flag absence | Silently omitting license section |
| 9 | Private-repo badge fallback applied | Skip broken badges + add note | Adding CI badge for private repo that won't render |
| 10 | Quick Start is actionable in ≤ 3 steps | Copy-paste-run | 10-step setup before first `curl` |
| 11 | Command source attributed | "Command source: root Makefile" | Commands floating with no origin |
| 12 | Structure section is concise | Key dirs + one-line purpose | Dumping 80-line file tree |

## Phase 3: Final Review

| # | Check | How to Verify |
|---|-------|--------------|
| 1 | No contradictory paths/commands | Cross-check with actual file tree |
| 2 | No duplicated sections | Scan for repeated content |
| 3 | Headings are scannable | Short, action-oriented, no redundant prefixes |
| 4 | Root README links to deeper docs/modules | Check `docs/` and submodule READMEs |
| 5 | 3-tier scorecard completed | Critical 4/4, Standard ≥ 4/6, Hygiene ≥ 3/4 |
| 6 | Update trigger note present | "This README should be updated when..." section |
| 7 | Evidence mapping table output | Every major section has at least one evidence source |
| 8 | No internal process labels in README body | No `Verified`, `PASS/FAIL`, scorecard language |
| 9 | Navigation present for long READMEs | TOC when > 8 major sections |
| 10 | Value proposition comes before setup | Overview/purpose before Prerequisites |

## Update Trigger Matrix

Use this when reviewing whether README is stale after code changes:

| Repository Change | Sections to Check | Priority |
|------------------|-------------------|----------|
| New `cmd/*/main.go` entrypoint | Project Structure, Commands, Quick Start | High |
| Env variable added/changed | Configuration | High |
| Makefile target added/renamed | Commands | High |
| CI workflow changed | Badges, Testing | Medium |
| New package/module added | Project Structure | Medium |
| API endpoint changed | API section (if present) | High |
| Deployment config changed | Deployment section (if present) | Medium |
| Dependency major version bump | Quick Start prerequisites, Badges | Medium |
| `LICENSE` / `CONTRIBUTING.md` added | License, Contributing sections | Low |
| Go/Node version bumped | Badges, Prerequisites | Low |
| New docs/ files added | Links in README | Low |

## Common Mistakes by Project Type

### Service

| Mistake | Fix | Evidence to Check |
|---------|-----|-------------------|
| No health check endpoint shown | Add `curl localhost:PORT/health` to Quick Start | `handler/health.go`, router registration |
| Migration commands missing | Add `make migrate-up` if migrations/ exists | `migrations/` directory, Makefile targets |
| No port/URL in Quick Start | State the default port explicitly | `.env.example`, config loader, `main.go` flag |
| Missing API documentation link | Add Swagger/OpenAPI link if `swagger` target exists | Makefile, `docs/swagger/` |
| No Docker instructions | Add `make docker-build && make docker-run` if Dockerfile exists | `Dockerfile`, `docker-compose.yml` |
| Config section missing source | Cite `.env.example` or `config/` as source | `.env.example`, `config/*.yaml` |

### Library

| Mistake | Fix | Evidence to Check |
|---------|-----|-------------------|
| No `go get` / install command | First section after overview should be Installation | `go.mod` module path |
| No minimal code example | Add 5-15 line usage example | Exported functions in `*.go` |
| Showing CLI commands for a library | Focus on API, not CLI | Absence of `cmd/` directory |
| Missing pkg.go.dev link | Add link if public Go module | `go.mod` module path |
| No Compatibility section | Add supported Go versions and constraints | `go.mod` `go` directive |
| No benchmark results | Include if `*_test.go` has `Benchmark*` functions | `*_test.go` files |

### CLI Tool

| Mistake | Fix | Evidence to Check |
|---------|-----|-------------------|
| No end-to-end example | Show input command + output result | `main.go` usage patterns |
| Missing flag table | Extract from `--help` or flag definitions | `flag` or `cobra` usage in code |
| No install command | Show `go install ...@latest` or `brew install` | `go.mod` path, Homebrew formula |
| Missing exit code documentation | Add exit code table if non-trivial | Error handling in `main.go` |
| No `--help` output shown | Include if it documents subcommands | `cobra.Command` definitions |

### Monorepo

| Mistake | Fix | Evidence to Check |
|---------|-----|-------------------|
| Dumping full tree of every module | Use overview table + link to sub-READMEs | `apps/*/README.md`, `packages/*/README.md` |
| No "where to start" guidance | Add module table with descriptions | `apps/`, `packages/` directory names |
| Root README too detailed | Keep focused, delegate to module READMEs | Sub-module README existence |
| Missing go.work or workspace info | Note workspace setup if `go.work` exists | `go.work` file |
| No "Adding a New Module" guide | Add onboarding steps for new contributors | Team convention |

### Lightweight / Internal

| Mistake | Fix | Evidence to Check |
|---------|-----|-------------------|
| Over-engineering with heavy sections | Use Lightweight Template Mode | < 5 top-level dirs |
| Adding badges for internal repo | Skip badges or add private-repo note | `gh api repos/OWNER/REPO --jq '.private'` |
| Formal Contributing section for 2-person team | Omit unless explicitly requested | Team size, no `CONTRIBUTING.md` |
| Adding sections with no evidence | Mark as `N/A` or omit entirely | Evidence Completeness Gate results |

## Degradation Patterns

When evidence is incomplete, apply these degradation rules:

| Missing Evidence | Degradation Action | README Impact |
|-----------------|-------------------|---------------|
| No Makefile, no package.json, no build system | Use `go build` / `go test` fallback | Note "Command source: standard toolchain" |
| No `.env.example` | Omit Configuration section | Note "Configuration: Not found in repo" |
| No CI workflows | Omit Badges section entirely | No placeholder badges |
| No `LICENSE` file | Add missing-license note | "License: Not found in repo — consider adding" |
| No tests found | Show testing commands with caveat | "No test files found — commands are standard defaults" |
| Private repo detected | Skip external badge URLs | Add private-repo fallback note |
| Cannot determine project type | Generate Overview-only README | Mark `degraded: true` in output |
| No entry point found | Generate minimal README | Only Project Overview + documented gaps |

### Degradation Levels

```
Level 1: Full evidence       → Complete README with all applicable sections
Level 2: Partial evidence    → README with "Not found in repo" markers
Level 3: Minimal evidence    → Overview + Quick Start + known gaps
Level 4: No evidence         → Stop — request user guidance instead of guessing
```

## Checklist for Refactoring Existing README

When improving an existing README rather than generating from scratch:

| # | Check | Action |
|---|-------|--------|
| 1 | Identify stale sections | Compare README claims against current file tree |
| 2 | Preserve valuable content | Don't discard useful prose that took effort to write |
| 3 | Fix contradictory commands | Cross-check with Makefile / scripts / CI |
| 4 | Remove guessed content | Replace with `Not found in repo` or investigate |
| 5 | Add missing required sections | Quick Start, Structure, Commands, Testing, Maintenance |
| 6 | Update badges | Verify CI workflow file still matches badge URL |
| 7 | Re-evaluate project type | Repo may have grown from CLI to service |
| 8 | Check language consistency | Don't mix ZH/EN heading styles |
| 9 | Add evidence mapping | Map each section to its source file |
| 10 | Run 3-tier scorecard | Ensure Critical tier all PASS |

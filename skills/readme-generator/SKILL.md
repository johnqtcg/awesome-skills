---
name: readme-generator
description: Generate or refactor project README.md files using repository evidence. Use when the user asks to create/rewrite/standardize README, improve documentation structure, or produce maintainable README templates for different project types (service/library/CLI/monorepo).
---

# README Generator

Generate high-quality README documents from codebase evidence, with clear structure, runnable commands, and maintenance rules.

## Core Rules

- Base every statement on repository evidence (files, code, scripts, workflows, configs).
- If key information is missing, write `Not found in repo` instead of guessing.
- Exclude local/private tooling folders by default (for example `.codex/`) unless explicitly requested.
- Keep naming/paths accurate and consistent with real repository layout.
- Prefer concise sections, bullet lists, and short command blocks.
- Keep internal workflow reporting out of README body by default. Evidence maps, scorecards, and verification-state reporting belong in the assistant response unless the user explicitly asks for them in the document.
- Treat top-level `README.md` as a user-facing homepage first and a maintainer reference second, unless the user explicitly wants an internal-only README.

## Pre-Generation Gates (Mandatory)

### 1) Audience and Language Gate

Before drafting, determine:

- target readers: contributors, operators, API consumers, or end users
- output language: Chinese / English / bilingual

If unspecified, default to:

- primary language follows existing repo docs
- keep audience assumptions in working notes; only state them in README when they materially help readers

### 2) Project Type Routing

Classify repository and choose template path:

- Service/backend app
- Library/SDK
- CLI tool
- Monorepo (multiple apps/packages)

If uncertain, state assumption explicitly in README.

### 3) Evidence Completeness Gate

Before drafting, verify minimum evidence has been collected:

- At least one entry point identified (`main.go`, `cmd/`, `package.json`, executable script)
- Project type determined (service/library/CLI/monorepo/lightweight)
- Command source located (Makefile, package.json, go.mod, or none)

If the discovery script is available, run it first:

```bash
bash "<path-to-skill>/scripts/discover_readme_needs.sh"
```

If minimum evidence is insufficient (no entry point found, no build system detected):
- Output a degraded README with only Project Overview + "Not found in repo" sections
- Mark the output as `degraded: true` in the assistant response
- List exactly what evidence is missing and suggest how to resolve

### 4) Badge Detection Gate (Mandatory)

Badge generation is mandatory for every README generation. Before drafting, scan for badge evidence:
- CI workflow files (`.github/workflows/*.yml`)
- Coverage config (codecov, coveralls, Makefile `cover` target)
- Language version (`go.mod`, `package.json engines`, `pyproject.toml`)
- License file (`LICENSE`, `LICENSE.md`)

If evidence exists, add badges. If no evidence exists for any badge type, skip that badge — do not fabricate. Document badge decisions in the Output Contract (`badges_added` field).

### 5) Command Verifiability Gate

Do not fabricate command verification or health-check results.

- If commands were executed, you may say so in the assistant response.
- If commands were not executed, do not inject `Verified` / `Not verified in this environment` labels into README body by default.
- In README itself, prefer evidence-backed install/run commands plus prerequisites.
- Only add explicit verification-state wording inside the README when the user requests it or the repository clearly uses that style for internal docs.

> **Hard rule**: verification-state phrases such as "not executed in this environment", "not verified", "Commands are derived from the Makefile and have not been executed" must **never** appear inside the README.md file itself. These belong exclusively in the assistant response (Output Contract). Even when the Scorecard checks H2, that check refers to the README file — keep all process language out of it.

## Badge Strategy

Add badges at the top of README when evidence exists. Detection order:

1. **CI status**: detect from `.github/workflows/*.yml` → `![CI](https://github.com/OWNER/REPO/actions/workflows/FILE/badge.svg)`
2. **Coverage**: detect from coverage config (codecov, coveralls) or Makefile `cover` target
3. **Go version / Language version**: detect from `go.mod`, `package.json engines`, `pyproject.toml`
4. **License**: detect from `LICENSE` file → `![License](https://img.shields.io/badge/license-MIT-blue)`
5. **Release/tag**: detect from git tags or release workflow

Badge ordering: CI → Coverage → Language version → License → Release

Rules:
- Only add badges with real URLs derivable from repo evidence.
- Do not add placeholder badges with fake URLs.
- If repo is private and badges won't render, note this and skip.

Private-repo fallback (recommended wording):

`Badge note: repository is private; external badge URLs may not render outside authorized viewers.`

## Community and Governance Files

Detect and reference these files when present:

| File | README Action |
|------|--------------|
| `LICENSE` | Add License section or badge |
| `CONTRIBUTING.md` | Add "Contributing" section linking to it |
| `CODE_OF_CONDUCT.md` | Reference in Contributing section |
| `SECURITY.md` | Add "Security" section linking to it |
| `CHANGELOG.md` | Reference in Release/Versioning section |

If `LICENSE` is missing, add a note: `License: Not found in repo — consider adding a LICENSE file.`

## Key Evidence Targets

Always scan these high-signal files before drafting or refactoring:

- Entrypoints: `main.go`, `cmd/*`, executable scripts, `package.json`
- Build/test hubs: `Makefile`, `go.mod`, `pyproject.toml`, `package.json`
- CI and release: `.github/workflows/*`
- Runtime/config: `.env.example`, `config/*`, `application.yml`, `docker-compose.yml`
- Governance: `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`
- Existing docs: `README*.md`, `docs/*`

If any of these are absent, record `Not found in repo` instead of filling the gap with assumptions.

## Command Priority

When multiple command sources exist, apply Command Priority in this order:

1. `Makefile` target when it exists and is clearly maintained
2. Language-native manifest (`go.mod`, `package.json`, `pyproject.toml`, `Cargo.toml`)
3. CI workflow commands when they confirm the maintained path
4. Direct tool invocation only when no stronger source exists

If sources conflict, load `references/command-priority.md` and resolve the conflict before drafting commands.

## Structure Policy

Use required + optional sections, not one rigid template.

### Required Sections

1. Badges (when evidence exists)
2. Project overview
3. Prerequisites (CLI / Service types)
4. Quick start
5. Code/project structure
6. Common commands
7. Configuration and environment
8. Testing and quality checks
9. Documentation maintenance note

For public/open-source homepage-style READMEs, prefer this top order when evidence exists:

1. Value proposition
2. Highlights / key capabilities
3. Prerequisites
4. Install
5. Quick start
6. End-to-end example
7. Reference sections (structure, configuration, commands, testing, docs)

**Prerequisites section format** (CLI / Service types): list required runtime dependencies first, then optional ones. Each entry should state version constraint, purpose, and a setup link when non-trivial. Example:

```markdown
## Prerequisites

- Go `>= 1.21` ([download](https://go.dev/dl/))
- A GitHub Personal Access Token with `repo` read permission ([create one](https://github.com/settings/tokens))
- _(Optional)_ An OpenAI API key — required only for the AI summary feature
- _(Optional)_ Docker — required only for `make docker-build`
```

### Optional Sections (include only when evidence exists)

- Architecture / data flow
- Deployment / operations
- API usage examples
- Release/versioning
- Contributing guide (link to `CONTRIBUTING.md` if present)
- License
- Security notes (link to `SECURITY.md` if present)
- Contact and support (optional; no forced SLA field)

If a section is not applicable, omit it or mark `N/A (reason)`.

## Lightweight Template Mode

Use lightweight mode when repository scope is small and a full template would create noise.

Trigger conditions (any 2):

- fewer than 5 top-level functional directories
- no deployment/ops workflows in repo
- no public API/SDK surface
- README target is internal contributors only

Lightweight required sections:

1. Project overview
2. Quick start
3. Common commands
4. Project structure (short)
5. Testing and quality checks
6. Documentation maintenance note

In lightweight mode, skip optional heavy sections unless explicitly requested.

## Chinese / Bilingual README Guidelines

Apply this section when the repository or user request indicates Chinese or bilingual output.

- Keep English for package names, command names, file paths, environment variables, and precise technical identifiers.
- Translate headings and explanatory prose to match the target audience language.
- Do not use double-language headings like `## Quick Start / 快速开始`.
- In bilingual mode, use Chinese as the primary prose and keep English technical terms inline.
- Prefer exact Chinese headings such as `## 快速开始`, `## 项目结构`, and `## 常用命令`.

Example heading style:

````markdown
## 快速开始

先安装依赖，再运行服务：

```bash
make install-tools
make run-api
```
````

## README Navigation Rule

For long READMEs, navigation is part of usability.

- If the README has many major sections or reads like a long-form reference doc, keep a compact table of contents with major sections only.
- Do not remove an existing useful table of contents solely to reduce length.
- If the README is short enough to scan without scrolling effort, a table of contents can be omitted.

**ToC size calibration**: ToC length should match project complexity. A simple CLI or single-purpose library should have 7–10 ToC entries at most. Inflating the ToC by listing every section creates noise and obscures the user's actual navigation path.

Exclude from ToC by default (keep in document body for those who scroll):

- Architecture / data flow internals (downgrade to `###` subsection under Project Structure)
- Contributor-only sections (Testing/CI details, Common Commands reference tables, Docker build steps)
- Any section that is not a direct action step for the primary audience

**ToC label / heading consistency rule**: the display text of every ToC entry must exactly match the `##` heading it links to. If you shorten a ToC label for readability, you must rename the section heading to match. Mismatches disorient readers who click a link and land on a differently-titled section.

## Monorepo Rules

When the detected project type is monorepo:

- Use a repository overview table instead of a deep tree dump.
- Link to submodule READMEs instead of duplicating every module's internal details.
- Document shared root commands only; module-specific commands belong in each module README.
- If `LICENSE` is missing, say `Not found in repo` at the root rather than guessing package-level license inheritance.

Load `references/monorepo-rules.md` before drafting or calibrating a monorepo README.

## End-to-End Example Rule

For CLI tools, converters, generators, and similar products, prefer at least one end-to-end example that shows:

1. the user input command or API call
2. the resulting file name, status line, or response shape
3. a short excerpt of the generated output when evidence exists

This is usually more useful than showing an isolated output snippet alone.

**No-fabrication constraint**: if actual output cannot be derived from repository evidence (no sample output files, no test fixtures, no documented response format), show only the invocation and describe the destination generically — do not invent output content.

```markdown
schema-gen generate --format json --output ./schemas ./internal/models
# → writes schema file(s) to ./schemas/
```

Never write a fabricated JSON/YAML body as if it were real output when no evidence exists for the exact shape.

## Anti-Examples (BAD / GOOD Markdown Pairs)

Use these patterns to suppress the most common README failures.

BAD:

````markdown
## Testing — Status: Not verified in this environment

| Command | Verified |
|---------|----------|
| `make test` | ⚠️ Not verified |
| `make lint` | ✅ Verified |
````

GOOD:

````markdown
## Testing

```bash
make test
make lint
```
````

Topic: process labels.

BAD:

```markdown
## Maintainer workflow

Install pre-commit hooks, set up internal dashboards, then scroll down for what the project does.
```

GOOD:

````markdown
## Overview

Explain the product value first. Move maintainer workflow to a later section or contributor guide.
````

Topic: Maintainer workflow before value proposition.

BAD:

```markdown
![Coverage](https://codecov.io/gh/example/project/badge.svg)
![Downloads](https://img.shields.io/npm/dm/example)
```

GOOD:

````markdown
![CI](https://github.com/example/project/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue)
````

Topic: badge fabrication.

BAD:

```markdown
## Configuration

`DB_HOST=localhost`
`REDIS_URL=redis://localhost:6379`
`JWT_SECRET=changeme`
```

GOOD:

````markdown
## Configuration

Configuration source: `.env.example`
Unknown variables: `Not found in repo`
````

Topic: configuration guessing.

BAD:

```markdown
## Project Structure

Huge monorepo tree with every nested file for every app and package.
```

GOOD:

````markdown
## Repository Overview

| Module | Path | Description |
|--------|------|-------------|
| API | `apps/api/` | Public HTTP service |
| Worker | `apps/worker/` | Background jobs |
````

Topic: monorepo tree dump.

BAD:

```markdown
## Quick Start / 快速开始

### Installation / 安装
```

GOOD:

````markdown
## 快速开始

### 安装
````

Topic: Double-language headings.

BAD:

````markdown
## Usage

Output:

```json
{"status":"ok"}
```
````

GOOD:

````markdown
## Usage

```bash
curl -s localhost:8080/health
```

Response:

```json
{"status":"ok"}
```
````

Topic: Output snippet without input command.

This applies to all process-state language — not just verification tables. Additional low-frequency anti-patterns live in `references/anti-examples.md`.

## Generation Workflow

1. **Detect audience** — decide whether the README is for end users, contributors, operators, or mixed readers.
2. **Detect language** — choose English, Chinese, or bilingual output before drafting.
3. **Discover repository facts** — run `scripts/discover_readme_needs.sh` if available.
4. **Collect key evidence targets** — read `main.go`, `Makefile`, `go.mod`, `.github/workflows`, config files, and existing README/docs.
5. **Route project type** — choose Template A/B/C/D/E based on repo structure.
6. **Choose command source** — apply Command Priority and resolve command conflicts before copying commands.
7. **Select supporting references** — load template, checklist, golden example, bilingual guidance, or monorepo rules only when needed.
8. **Draft sections** — build the README from evidence, keeping homepage-first reader flow.
9. **Calibrate structure** — add or trim ToC, badges, end-to-end examples, and optional sections based on project complexity.
10. **Polish language** — remove internal process wording, duplicated headings, guessed configuration, and filler prose.
11. **Verify evidence mapping** — ensure each non-trivial section maps back to repo files.
12. **Return output contract** — include the evidence mapping, scorecard, degraded flag, and omitted sections in the assistant response.

## Output Style

- Short, direct prose. Fenced blocks for trees and commands.
- No internal rubric language (`scorecard`, `pass/fail`, `verified`) in README body unless requested.

## Evidence Mapping Output (Required)

After generating or refactoring README, output an evidence mapping table in the assistant response, not inside the README itself, unless the user explicitly asks for an in-document appendix:

| README Section | Evidence File(s) | Evidence Snippet/Reason |
|---|---|---|
| Quick Start | `Makefile`, `go.mod` | target/command exists |
| Configuration | `.env.example`, `config/*` | variables defined |
| Testing | `Makefile`, CI workflow | test/lint commands present |

Rules:

- Every non-trivial section should map to at least one evidence source.
- If evidence is missing, map the section to `Not found in repo`.
- Keep mapping concise (one line per section is enough).

## README Update Triggers

When these changes occur, the corresponding README sections should be updated:

| Repository Change | README Sections to Update |
|------------------|--------------------------|
| New `cmd/*/main.go` entrypoint added | Project Structure, Common Commands, Quick Start |
| Environment variable added/changed | Configuration and Environment |
| Makefile target added/renamed | Common Commands |
| CI workflow changed | Badges, Testing and Quality |
| New package/module added | Project Structure |
| API endpoint added/changed | API Usage Examples (if present) |
| Deployment config changed | Deployment / Operations (if present) |
| Dependency major version bumped | Quick Start prerequisites |
| `LICENSE` / `CONTRIBUTING.md` added | License, Contributing sections |
| Go version / Node version bumped | Badges, Quick Start prerequisites |

Use this matrix to check README staleness after code changes. When updating docs with `update-doc` skill, cross-reference this table.

## Output Contract (Mandatory Fields)

Every README generation or refactoring must produce these outputs in the assistant response:

| # | Field | Required | Description |
|---|-------|----------|-------------|
| 1 | `project_type` | Always | service / library / cli / monorepo / lightweight |
| 2 | `language` | Always | en / zh / bilingual |
| 3 | `template_used` | Always | Template A–E name |
| 4 | `evidence_mapping` | Always | Section → evidence file table |
| 5 | `scorecard` | Always | 3-tier scorecard result |
| 6 | `degraded` | When applicable | true/false — whether evidence was insufficient |
| 7 | `missing_evidence` | When degraded | List of missing items and suggested actions |
| 8 | `badges_added` | When applicable | List of badge types added, or "skipped (reason)" |
| 9 | `sections_omitted` | When applicable | Sections skipped with reason |

### Machine-Readable Summary (JSON)

When the user requests structured output or for CI integration, append:

```json
{
  "project_type": "service",
  "language": "zh",
  "template_used": "Template A: Service",
  "degraded": false,
  "scorecard": {
    "critical": "4/4",
    "standard": "5/6",
    "hygiene": "4/4",
    "result": "PASS"
  },
  "badges_added": ["CI", "Coverage", "Go Version", "License"],
  "sections_omitted": [],
  "missing_evidence": []
}
```

## README Quality Scorecard (3-Tier)

### Critical Tier (any FAIL → overall FAIL)

| # | Check | PASS Rule |
|---|-------|-----------|
| C1 | Evidence-backed claims | Every non-trivial statement traces to a repo file |
| C2 | No fabricated content | Zero guessed commands, URLs, config values, or paths |
| C3 | Quick Start present and actionable | Reader can run the project in ≤ 3 steps |
| C4 | Correct project type routing | Template matches actual repo layout |

### Standard Tier (≥ 4/6 to PASS)

| # | Check | PASS Rule |
|---|-------|-----------|
| S1 | Command source attribution | Commands traced to Makefile / scripts / native tools |
| S2 | Structure section with purpose | Key directories listed with one-line description |
| S3 | Config/env section present | Required variables documented, source file cited |
| S4 | Testing commands included | At least test + lint commands with practical defaults |
| S5 | Badges evidence-based | Only real URLs; private-repo fallback applied if needed |
| S6 | Audience and language explicit | Stated in working notes or README when it helps readers |

### Hygiene Tier (≥ 3/4 to PASS)

| # | Check | PASS Rule |
|---|-------|-----------|
| H1 | Maintenance trigger note | "Update this README when..." section present |
| H2 | No internal process labels | No `Verified` / `PASS/FAIL` / scorecard language in README body. Also excludes execution-state phrases like "not executed in this environment" — those belong in the Output Contract only. |
| H3 | Navigation and ToC quality | TOC present when needed; size calibrated to project complexity (7–10 entries for simple projects); contributor-only sections excluded; every ToC label matches its `##` heading exactly |
| H4 | Optional sections gated | Architecture / Deployment / API only when evidence exists |

Output format: `Critical: X/4 | Standard: X/6 | Hygiene: X/4 → PASS/FAIL`

## Skill Maintenance

Run regression checks for this skill with:

```bash
bash "<path-to-skill>/scripts/run_regression.sh"
```

## Load References Selectively

- `scripts/discover_readme_needs.sh`
  Run first (step 1 of Generation Workflow) to collect repo facts deterministically.
- `references/templates.md`
  Load when generating a new README from scratch or switching project type template.
- `references/golden-<type>.md` (service / library / cli / monorepo / lightweight)
  Load **only the file matching the detected project type** when calibrating output quality. See `references/golden-examples.md` for the index.
- `references/command-priority.md`
  Load **only when command conflicts appear** (e.g., Makefile + package.json + CI scripts all define overlapping commands).
- `references/checklist.md`
  Load **only in refactor mode** (updating an existing README) during final review phase.
- `references/anti-examples.md`
  Load **only when refactoring** an existing README that may contain low-frequency anti-patterns (tree dumps, double-language headings, missing input commands).
- `references/bilingual-guidelines.md`
  Load **only when the output language is Chinese or bilingual** for heading style, language-split rules, and bilingual anti-patterns.
- `references/monorepo-rules.md`
  Load **only when the detected project type is monorepo** for tree-depth limits, per-app pointer tables, and submodule README linking rules.

---
name: readme-generator
description: Generate or refactor project README.md files using repository evidence. Use when the user asks to create/rewrite/standardize README, improve documentation structure, or produce maintainable README templates for different project types (service/library/CLI/monorepo).
allowed-tools: Read, Write, Grep, Glob, Bash(git log*), Bash(git diff*), Bash(bash*discover_readme_needs.sh*), Bash(python3*lint_readme.py*), Bash(make*), Bash(gh api*), Bash(go build*), Bash(go test*), Bash(go vet*), Bash(pytest*), Bash(cargo test*), Bash(node --test*)
---

# README Generator

Generate high-quality README documents from codebase evidence, with clear structure,
runnable commands, and maintenance rules.

## Core Rules

- Base every statement on repository evidence (files, code, scripts, workflows, configs).
- Keep internal workflow reporting out of the README body. Evidence maps, scorecards, and
  verification state belong in the assistant response — see §Command Verifiability Gate.
- Exclude local/private tooling folders by default (for example `.codex/`) unless asked.
- Keep naming and paths consistent with the real repository layout.
- Treat top-level `README.md` as a user-facing homepage first, a maintainer reference second.

### Evidence Precedence (resolves "omit or mark?")

One rule, applied by section class — there is no third case:

| Section class | Evidence present | Evidence missing |
|---|---|---|
| **Required** for the project type (§Structure Policy) | Write it | Keep the heading, write `Not found in repo` |
| **Optional** (§Optional Sections) | Write it | Omit entirely and list it in `sections_omitted` |

### Facts vs Results (resolves "is this command fabricated?")

A manifest proves a **toolchain**; only an artifact proves a **result**.

- Evidence-backed: `go test ./...` when `go.mod` exists, `pytest` when `pyproject.toml`
  exists, `make <target>` when that exact target is in the Makefile.
- Not evidence-backed: coverage percentages, test counts, benchmark numbers, throughput,
  latency, or a response body — unless the repo commits the artifact they come from
  (`.codecov.yml`, a checked-in `benchstat` output, a golden fixture).
- If a repo has a manifest but no test files, still show the toolchain command and add
  `No test files found in repo` — the command is real, the coverage claim would not be.

## Quick Reference

| When you need to… | Jump to |
|---|---|
| Generate from scratch | §Pre-Generation Gates → §Project Type Routing → §Generation Workflow |
| Update an existing README | §Refactor Mode + `references/checklist.md` |
| Chinese or bilingual output | §Chinese / Bilingual + `references/bilingual-guidelines.md` |
| Monorepo / Lightweight | §Monorepo Rules + `references/monorepo-rules.md` · §Lightweight Template Mode |
| Calibrate ToC, check quality | §README Navigation Rule · §README Quality Scorecard + `scripts/lint_readme.py` |
| Evidence mapping, anti-patterns | §Evidence Mapping Output · §Anti-Examples (catalog in `references/anti-examples.md`) |

## Pre-Generation Gates (Mandatory)

### 1) Audience and Language Gate

Decide target readers (contributors / operators / API consumers / end users) and output
language (Chinese / English / bilingual). If unspecified, follow the existing repo docs and
keep audience assumptions in working notes, not in the README. This gate also owns the
lightweight decision — see §Project Type Routing.

### 2) Project Type Routing

Discovery emits `project_type detected` (Service / Library / CLI / Monorepo — selects the
**language command snippets**) and `project_type effective` (selects the **template and
required sections**).

**`effective` is the single answer** — generation, the Output Contract, and
`scripts/lint_readme.py` all read it, so they cannot disagree.

**Discovery never promotes to `lightweight` on its own.** It reports
`lightweight_eligible` plus a named `lightweight_blocked_by` list (5+ dirs · CI present ·
deployment surface · public distribution surface · unclassified). Promotion is *your* call
at the Audience Gate, because the deciding trigger — audience is internal contributors only
— is a judgement no probe can make. Inferring it was harmful: a minimal public Go SDK
(`go.mod` + `pkg/`, no CI, few dirs) was silently downgraded and lost Installation and API.
Absence of CI is not evidence of absence of users, and a `library` is a public surface by
definition. When the Gate does establish an internal audience on an eligible repo, record it
with `lint_readme.py --type=lightweight` and report `lightweight` in the Output Contract.

> Routing logic lives in `scripts/discover_readme_needs.sh` — it reads Go, Node, Rust, and
> Python manifests, workspace markers (`go.work`, `apps/`, `packages/`, npm `workspaces`,
> Cargo `[workspace]`), and entrypoint locations. Change prose and script together; sync is
> guarded by `scripts/tests/test_discovery_script.py::TestRoutingSync`.

### 3) Evidence Completeness Gate

Run discovery first and read its verdict — do not re-derive these by hand:

```bash
bash "<path-to-skill>/scripts/discover_readme_needs.sh"
```

The script emits an `entrypoint` inventory and a `verdict` line. Minimum evidence: at least
one entrypoint, a determined project type, a located command source. `verdict status
DEGRADED` names which of the three is missing.

When degraded: output Project Overview plus `Not found in repo` sections only, set
`degraded: true` in the assistant response, and list each missing item with a suggested
resolution.

### 4) Badge Detection Gate (Mandatory)

Scan for badge evidence before drafting: CI workflow **files** (an empty
`.github/workflows/` is not evidence), coverage config, language version, license file. Add
a badge only when its evidence exists. Record the outcome in `badges_added`.

### 5) Command Verifiability Gate

**Hard rule, no exceptions.** Verification-state language — `Verified`, `Not verified`,
`not executed in this environment`, `PASS/FAIL`, scorecard output, `degraded: true` — never
appears inside `README.md`; it belongs in the assistant response. This holds even when the
user asks for a "verification table": produce it in the response and say why it is not in
the file, because the label goes stale the moment it is committed. Inside the README, write
evidence-backed install/run commands plus prerequisites.

## Badge Strategy

Detection order, which is also render order:
**CI status** → **Coverage** → **Language version** → **License** → **Release**.

Only emit badges whose URL is derivable from repo evidence. For a private repo, skip the
external badge URLs and add:

`Badge note: repository is private; external badge URLs may not render outside authorized viewers.`

→ URL templates per badge type and the community-file mapping live in
`references/badges-and-governance.md`.

## Community and Governance Files

Detect `LICENSE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CHANGELOG.md`;
link each present file from the matching section. **License is the one exception to
§Evidence Precedence** — an absent license is itself information, so the section never just
disappears: present → name it; absent → `License: Not found in repo — consider adding a
LICENSE file.` Only Lightweight mode on an internal repo omits it. Every other governance
file follows the normal optional rule. → `references/badges-and-governance.md`.

## Key Evidence Targets

Scan before drafting; absent targets are recorded per §Evidence Precedence, never guessed.

| Class | Files |
|---|---|
| Entrypoints | `main.go`, `cmd/*`, `package.json` `bin`/`main`, `src/main.rs`, `[project.scripts]`, executable scripts |
| Build/test hubs | `Makefile`, `go.mod`, `package.json`, `pyproject.toml`, `Cargo.toml` |
| CI and release | `.github/workflows/*` |
| Runtime/config | `.env.example`, `config/*`, `application.yml`, `docker-compose.yml` |
| Governance | `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md` |
| Existing docs | `README*.md`, `docs/*` |

## Command Priority

`Makefile` target → language-native manifest (`go.mod`, `package.json`, `pyproject.toml`,
`Cargo.toml`) → CI workflow command → direct tool invocation.

Every command must resolve against one of these — a `make` target absent from the Makefile
is a fabrication, not a suggestion, and each half of `make test && make deploy` is checked
separately. On conflict, load `references/command-priority.md`.

## Structure Policy

Required sections are **per project type**, not one flat list. A Library README carrying a
Configuration section, or a CLI README carrying Deployment, is noise.

| Project type | Required sections |
|---|---|
| service | Quick Start, Prerequisites, Structure, Commands, Configuration, Testing, Maintenance |
| cli | Installation, Usage, Commands, Testing, Maintenance |
| library | Installation, Usage, API, Testing, Maintenance |
| monorepo | Repository Overview, Quick Start, Commands, Structure, Maintenance |
| lightweight | Quick Start, Commands, Structure, Testing, Maintenance |

Every type opens with an overview: name, one-sentence value proposition, then badges when
evidence exists. Missing a **primary** section (Quick Start / Installation / Usage /
Repository Overview, per type) is a Critical defect; missing any other required section is
Standard — `lint_readme.py` reports them as R009 and R012 respectively.

**Sections and commands are separate axes.** This matrix picks sections from
`project_type effective`; the commands inside them come from
`references/language-snippets.md`, picked by the manifest the repo has. A Node CLI and a Go
CLI share Template C and share none of their command blocks. The matrix is the same table
`lint_readme.py` enforces (`REQUIRED_SECTIONS`), kept in sync by
`test_forward_eval.py::RequiredSectionSyncTest`.

For public homepages, order the top of the file: value proposition → highlights →
prerequisites → install → quick start → end-to-end example → reference sections.

### Optional Sections (include only when evidence exists)

Architecture / data flow · Deployment / operations · API usage examples · Release and
versioning · Contributing · Security notes · Contact and support. Missing evidence means
omit — see §Evidence Precedence. License is deliberately not on this list
(§Community and Governance Files).

## Lightweight Template Mode

Triggers: fewer than 5 top-level functional directories · no deployment/ops workflows in
the repo · no public API/SDK surface · README targets internal contributors only. Discovery
reports the first three as `lightweight_eligible`; the fourth is yours to assert
(§Project Type Routing). Required sections: Project overview, Quick start, Common commands,
Project structure (short), Testing and quality checks, Documentation maintenance note.
Skip heavy optional sections unless explicitly requested.

## Chinese / Bilingual README Guidelines

Keep English for package names, commands, file paths, environment variables, and precise
technical identifiers; translate headings and prose. Never use double-language headings
(`## Quick Start / 快速开始`) — prefer `## 快速开始`, `## 项目结构`, `## 常用命令`. In
bilingual mode Chinese is the primary prose with English technical terms inline.
→ `references/bilingual-guidelines.md` for the full rules.

## README Navigation Rule

- Keep a compact ToC for long, reference-shaped READMEs; omit it when the file is scannable
  without scrolling. Never delete a useful existing ToC just to shorten.
- **Size**: 7–10 entries max for a simple CLI or library. Exclude architecture internals,
  contributor-only sections, and anything that is not a direct action step for the primary
  audience — they stay in the body.
- **Label consistency**: every ToC entry's text must match the `##` heading it links to.

## Monorepo Rules

Repository overview table instead of a deep tree dump · link to submodule READMEs rather
than duplicating internals · document shared root commands only · missing root `LICENSE` →
`Not found in repo`, never guessed inheritance. Load `references/monorepo-rules.md` first.

## End-to-End Example Rule

For CLI tools, converters, and generators, show one complete example: the input command,
then the resulting file name or response shape. **No-fabrication constraint**: with no
sample output, fixture, or documented response format in the repo, show the invocation and
describe the destination generically — never an invented JSON body, row count, or status
line.

```markdown
schema-gen generate --format json --output ./schemas ./internal/models
# → writes schema file(s) to ./schemas/
```

## Anti-Examples (BAD / GOOD Markdown Pairs)

Most common failure — process-state labels in the README body:

BAD:

````markdown
## Testing — Status: Not verified in this environment

| Command | Verified |
|---------|----------|
| `make test` | ⚠️ Not verified |
````

GOOD:

````markdown
## Testing

```bash
make test
make lint
```
````

→ Load `references/anti-examples.md` for the full catalog (fabricated badges, guessed
config, monorepo tree dumps, double-language headings, output-without-input).

## Generation Workflow

1. **Detect audience** — end users, contributors, operators, or mixed.
2. **Detect language** — English, Chinese, or bilingual.
3. **Run discovery** — `scripts/discover_readme_needs.sh`; read verdict and entrypoints.
4. **Collect evidence** — entrypoints, `Makefile`, manifests, workflows, config, existing docs.
5. **Route** — template from `project_type effective`, commands from the manifest.
6. **Choose command source** — apply Command Priority; resolve conflicts before drafting.
7. **Load references selectively** — template, snippets, golden example, checklist, rules.
8. **Draft sections** — from evidence, in homepage-first reader order.
9. **Calibrate** — ToC, badges, end-to-end example, optional sections.
10. **Polish** — remove process wording, duplicate headings, guessed config, filler.
11. **Self-check** — `python3 "<path-to-skill>/scripts/lint_readme.py" <repo-dir> <readme-path>`;
    fix every critical finding before returning.
12. **Return the output contract** — evidence mapping, scorecard, degraded flag, omissions.

## Refactor Mode (Existing README)

Preserve valuable prose, fix contradictory commands, replace guessed content, re-evaluate
the project type, re-run the scorecard. Load `references/checklist.md` for the refactor
checklist and the update-trigger matrix that detects staleness after code changes (new
entrypoint, env var, Makefile target, CI workflow, `LICENSE`, Go version, and the rest).

## Output Style

Short, direct prose; fenced blocks for trees and commands; no internal rubric language.
Explanatory notes about *why* a section looks the way it does belong outside the document,
never inside it.

## Evidence Mapping Output (Required)

Output this in the assistant response, not inside the README:

| README Section | Evidence File(s) | Evidence Snippet/Reason |
|---|---|---|
| Quick Start | `Makefile`, `go.mod` | target/command exists |
| Configuration | `.env.example`, `config/*` | variables defined |

Every non-trivial section maps to at least one evidence source, or to `Not found in repo`;
one line per section.

## Output Contract (Mandatory Fields)

| # | Field | Required | Description |
|---|-------|----------|-------------|
| 1 | `project_type` | Always | service / library / cli / monorepo / lightweight |
| 2 | `language` | Always | en / zh / bilingual |
| 3 | `template_used` | Always | Template A–E name |
| 4 | `evidence_mapping` | Always | Section → evidence file table |
| 5 | `scorecard` | Always | 3-tier scorecard result |
| 6 | `degraded` | When applicable | whether evidence was insufficient |
| 7 | `missing_evidence` | When degraded | Missing items and suggested actions |
| 8 | `badges_added` | When applicable | Badge types added, or "skipped (reason)" |
| 9 | `sections_omitted` | When applicable | Optional sections skipped, with reason |

### Machine-Readable Summary (JSON)

```json
{
  "project_type": "service",
  "language": "zh",
  "template_used": "Template A: Service",
  "degraded": false,
  "scorecard": {"critical": "4/4", "standard": "5/6", "hygiene": "4/4", "result": "PASS"},
  "badges_added": ["CI", "Coverage", "Go Version", "License"],
  "sections_omitted": [],
  "missing_evidence": []
}
```

## README Quality Scorecard (3-Tier)

Critical Tier — any FAIL means the whole output FAILs:

| # | Check | PASS Rule |
|---|-------|-----------|
| C1 | Evidence-backed claims | Every non-trivial statement traces to a repo file |
| C2 | No fabricated content | Zero guessed commands, URLs, config values, paths, or metrics |
| C3 | Primary onboarding path present and actionable | Reader gets running in ≤ 3 steps. The path is per type: **Quick Start** for Service / Monorepo / Lightweight, **Installation + Usage** for CLI / Library — the same set `lint_readme.py` treats as primary (R009) |
| C4 | Correct project type routing | Template matches the discovery verdict |

Standard Tier — ≥ 4/6 to PASS:

| # | Check | PASS Rule |
|---|-------|-----------|
| S1 | Command source attribution | Commands traced to Makefile / scripts / native tools |
| S2 | Structure section with purpose | Key directories listed with one-line descriptions |
| S3 | Config/env section present | Required variables documented, source file cited |
| S4 | Testing commands included | Test + lint commands from a real command source |
| S5 | Badges evidence-based | Only real URLs; private-repo fallback applied if needed |
| S6 | Audience and language explicit | Stated in working notes, or in README when it helps |

Hygiene Tier — ≥ 3/4 to PASS:

| # | Check | PASS Rule |
|---|-------|-----------|
| H1 | Maintenance trigger note | "Update this README when…" section present |
| H2 | No internal process labels | No verification state or scorecard language in the body |
| H3 | Navigation and ToC quality | Sized to complexity; every label matches its heading |
| H4 | Optional sections gated | Architecture / Deployment / API only when evidence exists |

Output format: `Critical: X/4 | Standard: X/6 | Hygiene: X/4 → PASS/FAIL`

`scripts/lint_readme.py` mechanically checks the **high-frequency** violations of C1, C2,
H2, H3: undefined `make`/npm targets, env vars absent from `.env.example`, non-existent
paths, placeholder residue, metrics with no committed artifact, unevidenced badges, missing
required sections, ToC/heading mismatches, process labels.

It is a floor, not the tier. A linter-clean README can still fail C1/C2 — a plausible but
wrong prose claim, a command that exists yet does the wrong thing, a structure description
that is stale rather than invented. Read the output as "no *detectable* fabrication", then
judge the tiers yourself.

## Load References Selectively

- Generating from scratch or switching template → `references/templates.md`
  (Template A–E skeletons and the prerequisites format).
- Filling a template's command blocks → `references/language-snippets.md`
  (Go / Node / Python / Rust install, build, test, lint, and version lines).
- Calibrating output quality for a detected type → `references/golden-<type>.md`; index at
  `references/golden-examples.md`.
- Command conflicts across Makefile / package.json / CI → `references/command-priority.md`.
- Final review of a refactor → `references/checklist.md`.
- Refactoring a README with suspected anti-patterns → `references/anti-examples.md`.
- Chinese or bilingual output → `references/bilingual-guidelines.md`.
- Monorepo detected → `references/monorepo-rules.md`.
- Badge URL templates and governance-file mapping → `references/badges-and-governance.md`.

Run `scripts/discover_readme_needs.sh` first (workflow step 3) to collect repo facts
deterministically, and `scripts/lint_readme.py` last (step 11) to check the draft against
those same facts. Skill regression: `bash "<path-to-skill>/scripts/run_regression.sh"`.

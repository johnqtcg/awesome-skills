# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

A documentation and asset repository — no application code. Five interconnected layers make up the repository:

```
bestpractice/  →  rationale/  →  skills/  →  evaluate/  →  outputexample/
(methodology)     (design docs)  (examples)  (reports)     (real outputs)
```

- **`bestpractice/`** — skill design methodology docs (`Fundamentals.md`, `Advanced.md`, `Evaluation.md`, `Iteration.md`, `Integration.md`, `Architecture.md`), bilingual (EN + ZH)
- **`rationale/`** — per-skill design rationale docs explaining the *why* behind each skill's structure and decisions; each skill has `design.md` + `design.zh-CN.md`
- **`skills/`** — 21 production-ready Claude Code skills, each centered on a `SKILL.md` with optional `scripts/`, `references/`, and `agents/` subdirs
- **`evaluate/`** — formal review reports paired EN/ZH (`<skill-name>-skill-eval-report.md` / `.zh-CN.md`)
- **`outputexample/`** — real task outputs (PDFs, test code, CI configs, screenshots)
- **`docs/`** — MkDocs Material site source; served at GitHub Pages

## Skill Structure Convention

Regression-enabled skills under `skills/<name>/` follow this layout:

```
SKILL.md                    # frontmatter (name, description) + skill body
references/                 # supporting docs loaded on demand
scripts/
  run_regression.sh         # runs all regression checks
  tests/
    test_skill_contract.py  # contract tests (required sections, thresholds)
    test_golden_scenarios.py# golden fixture tests
    golden/                 # *.json golden fixtures
```

- Skill names use `kebab-case`
- `SKILL.md` frontmatter must have `name` and `description` fields
- All supporting reference files use relative paths from `SKILL.md`

## Running Regression Tests

Per-skill regression (from the skill's directory):

```bash
cd skills/<name>
bash scripts/run_regression.sh
```

All skills at once (from repo root):

```bash
python3 -m pytest skills/
# or with coverage:
python3 -m pytest --tb=short skills/
```

Dependencies: `pytest>=8,<9` (see `requirements.txt`).

## Documentation Site

Built with MkDocs Material. Source is `docs/`, output is `site/`.

```bash
pip install mkdocs-material
mkdocs serve      # local preview at http://127.0.0.1:8000
mkdocs build      # build static site into site/
```

Deployed to GitHub Pages via CI on push to `main`.

## Contribution Rules

When adding or editing a skill, update all five layers together:

1. `skills/<name>/SKILL.md` (and supporting files)
2. `rationale/<name>/design.md` + `design.zh-CN.md`
3. `evaluate/<name>-skill-eval-report.md` + `.zh-CN.md`
4. `outputexample/<name>/`
5. `bestpractice/` docs if the skill introduces or validates a new design pattern

Bilingual consistency is required: any change to an English doc needs a matching update to its `.zh-CN.md` counterpart (and vice versa). This applies to `README.md`, `CONTRIBUTING.md`, `bestpractice/*.md` (all six chapters plus `README.zh-CN.md`), and `evaluate/` reports.

## Pre-PR Checks

```bash
find skills -maxdepth 2 -name SKILL.md | sort
find evaluate -maxdepth 1 -type f | sort
git diff --check
```

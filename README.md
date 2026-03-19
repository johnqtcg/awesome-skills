# awesome-skills

> Production-ready **Claude Code Skills** with quantitative evaluation, golden test fixtures, and end-to-end engineering workflow integration.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/johnqtcg/awesome-skills?style=social)](https://github.com/johnqtcg/awesome-skills)
[![中文](https://img.shields.io/badge/文档-中文版-blue)](README.zh-CN.md)

A curated system for **AI skill engineering** — not just a prompt collection. Built for Claude Code and applicable to any AI coding assistant, this project covers the full loop from skill design to quantitative evaluation to real software engineering workflow integration.

- **20** production-ready Claude Code skills: Go, testing, security, CI/CD, research, docs
- **40** paired evaluation reports (EN + ZH) with quantitative metrics
- **132** golden test fixtures + **29** Python test files for deterministic regression
- Testing skills: `unit-test` · `tdd-workflow` · `api-integration-test` · `e2e-test` · `fuzzing-test`
- Delivery pipeline: `go-makefile-writer` → `git-commit` → `create-pr` → `go-ci-workflow` → `go-code-reviewer` → `security-review`

## Table of Contents

- [Quick Start](#en-quickstart)
- [Overview](#en-overview)
- [Highlights](#en-highlights)
- [Project Structure](#en-project-structure)
- [Recommended Reading Path](#en-reading-path)
- [Documentation System](#en-bestpractice)
- [Skill Examples](#en-skills)
- [Review Reports and Output Examples](#en-evaluate-and-output)
- [Governance](#en-governance)
- [Who This Is For](#en-audience)
- [License](#en-license)

<a id="en-quickstart"></a>
## Quick Start

1. Browse the [skill list below](#en-skills) and find one relevant to your workflow
2. Copy the `skills/<name>` directory into your project:
   - Project-level: `.claude/skills/<name>`
   - User-level (all projects): `~/.claude/skills/<name>`
3. In Claude Code, the skill activates automatically when the task matches

To understand the skill design methodology:

- English: [bestpractice/README.md](bestpractice/README.md)
- Chinese: [bestpractice/README.zh-CN.md](bestpractice/README.zh-CN.md)

<a id="en-overview"></a>
## Overview

Main documentation entry: [bestpractice/README.md](bestpractice/README.md).

The core goal of this repository is not to show how to write prompts. It is to answer three harder questions:

1. How should a high-quality skill be designed?
2. How do you prove that it actually works?
3. How do you integrate it into daily engineering workflows instead of leaving it as a demo?

<a id="en-highlights"></a>
## Highlights

### 1. Four-layer closed-loop architecture

The repository is organized as a rare end-to-end chain:

`bestpractice/` → `skills/` → `evaluate/` → `outputexample/`

Those four layers are not just grouped content. They form a verifiable knowledge loop:

- methodology explains how a skill should be designed
- skill examples show what that methodology looks like in practice
- review reports test whether the skill is actually good
- output examples prove what it can produce in real tasks

That structure makes the project substantially stronger than a typical prompt or skill example project.

### 2. The main deliverable is methodology

The highest-leverage asset here is [bestpractice/](bestpractice), not the raw number of skills under [skills/](skills). The methodology is deliberately language-agnostic and platform-agnostic: mandatory gates, anti-examples, honest degradation, progressive disclosure, output contracts, and quantitative evaluation can be reused far beyond this repository.

In other words, the project is teaching people how to build professional skills, not just handing out a bag of ready-made prompts.

### 3. Skill quality is measured, not guessed

[bestpractice/Evaluation.md](bestpractice/Evaluation.md) turns “is this skill good?” into a quantitative question across three dimensions:

- trigger accuracy
- real-task performance
- token cost-effectiveness

The value of that framework is visible in the paired review reports under [evaluate/](evaluate). Concrete examples include:

- `go-code-reviewer`: +36 percentage points in subtle-scenario signal-to-noise, with 347x developer-time ROI
- `unit-test`: +38.4 percentage points in assertion pass rate
- `google-search`: +74.1 percentage points in assertion pass rate

That is much stronger than saying “these skills seem useful,” because it gives readers traceable numbers, evaluation process, and iteration evidence.

### 4. The regression system is deterministic and built for engineering maintenance

This repository does not rely on “use one LLM to judge another LLM” as its primary guardrail. Instead, it uses deterministic regression assets:

- `132` golden JSON fixtures
- `29` Python test files
- contract tests for required gates, outputs, and structure
- golden-scenario tests for real task coverage

Those checks run quickly, are versionable, and are easy to diff and rerun. That design choice reflects strong engineering judgment: critical quality constraints should live in deterministic scripts wherever possible, not only in natural-language instructions.

### 5. Skills are designed to compose into real workflows

The backend-oriented skills do not just work in isolation. They line up into an engineering pipeline:

`go-makefile-writer` → `git-commit` → `create-pr` → `go-ci-workflow` → `go-code-reviewer` → `security-review`

The repository also includes review reports, workflow examples, and output artifacts that show this is not a paper design. It is a workflow system that can be reused and validated in real engineering practice.

### 6. A view of knowledge: tacit -> explicit -> executable

Underneath the concrete files is a stronger idea: useful engineering knowledge should move through three layers:

- tacit experience in an expert's head
- explicit rules in documentation
- executable constraints in a skill, script, or test

That progression is one of the most important ideas in the repo. It reframes skills as a way to turn unstable personal intuition into shared, inspectable, and enforceable capability.

<a id="en-project-structure"></a>
## Project Structure

```text
.
├── bestpractice/        # Skill best-practice docs, in Chinese and English
├── skills/              # High-quality skill examples written with those best practices
├── evaluate/            # Skill review reports, in Chinese and English
├── outputexample/       # Real output examples
├── README.md            # README document
├── README.zh-CN.md
└── LICENSE
```

The four core directories serve these roles:

| Path | Purpose |
| --- | --- |
| [bestpractice/](bestpractice) | Explains how to write high-quality skills, how to evaluate them, and how to integrate them into workflows |
| [skills/](skills) | High-quality skill examples shaped by the methodology |
| [evaluate/](evaluate) | Formal review reports for skills, including strengths, weaknesses, and improvement points |
| [outputexample/](outputexample) | Real outputs from skills, such as PDFs, test code, Makefiles, CI configs, and screenshots |

<a id="en-reading-path"></a>
## Recommended Reading Path

If this is your first time in the project, this order works best:

1. Start with [bestpractice/README.md](bestpractice/README.md) to build the overall picture
2. Open a specific skill, for example [skills/google-search/SKILL.md](skills/google-search/SKILL.md)
3. Read its review report, for example [evaluate/google-search-skill-eval-report.md](evaluate/google-search-skill-eval-report.md)
4. Then look at its real output, for example [outputexample/google-search/中国制造2025目标完成度研究.pdf](outputexample/google-search/中国制造2025目标完成度研究.pdf)

If you prefer Chinese, start from [bestpractice/README.zh-CN.md](bestpractice/README.zh-CN.md).

<a id="en-bestpractice"></a>
## Documentation System

[bestpractice/](bestpractice) is the methodology entry point for the whole project:

- [Fundamentals.md](bestpractice/Fundamentals.md)
- [Advanced.md](bestpractice/Advanced.md)
- [Evaluation.md](bestpractice/Evaluation.md)
- [Integration.md](bestpractice/Integration.md)

These documents mainly answer:

- why skills matter as a key abstraction for AI coding assistants
- what design patterns high-quality skills should follow
- how to evaluate the real value of a skill quantitatively
- how to integrate skills into engineering workflows instead of leaving them inside a single chat

<a id="en-skills"></a>
## Skill Examples

All high-quality skills in this project live under [skills/](skills), with each skill centered on its own `SKILL.md`. They are not isolated capabilities. They can be grouped by use case, and the backend-oriented skills can work together as a full quality pipeline.

### Backend Development: a complete quality pipeline

The value of the backend-related skills is not just that each skill is useful on its own. They can connect end-to-end and form an engineering workflow from coding to merge:

```text
Coding
  ↓
Write / fix tests
  (unit-test · tdd-workflow · api-integration-test · e2e-test · fuzzing-test)
  ↓
make fmt / make lint (local quality checks generated by go-makefile-writer)
  ↓
git commit (git-commit skill: secret scan + quality gates + standardized message)
  ↓
git push
  ↓
create PR (create-pr skill: multiple gates + structured PR body)
  ↓
CI triggered
  ├── make ci (format + tests + lint + coverage + build)
  ├── make docker-build (container image validation)
  ├── Claude Code Review (go-code-reviewer skill: automated code review)
  └── govulncheck / security checks (security-review skill focuses on risk models)
  ↓
Human review + merge
```

The key skills in that pipeline are:

| Skill Name | Stage | Purpose | Main strengths / advantages |
| --- | --- | --- | --- |
| `go-makefile-writer` | Local engineering entrypoint | Design or refactor a root Makefile for Go repositories | Standardizes `fmt/test/lint/build/run` entrypoints and keeps local commands aligned with CI gates |
| `git-commit` | Pre-commit gate | Safely create Git commits | Checks repo state, potential secrets, and conflicts before commit, then generates a standardized commit message |
| `create-pr` | Post-push, pre-review | Create a high-quality PR to GitHub main | Emphasizes preflight checks, quality gates, and structured PR content to reduce reviewer overhead |
| `go-ci-workflow` | CI orchestration | Create or refactor GitHub Actions CI for Go repos | Emphasizes Make-driven CI, local/CI consistency, caching, job design, and layered gates |
| `go-code-reviewer` | Automated review | Review Go code with a defect-first mindset | Focuses on real bugs, regressions, and risk instead of reducing review to style comments |
| `security-review` | Security review | Perform exploitability-first security review on code changes | Prioritizes exploitable risk across auth, input, dependencies, concurrency, and container issues |

### Testing and Validation

These skills move code from “written” to “verified.” Together they cover unit tests, TDD, integration tests, E2E tests, fuzzing, and complex debugging.

| Skill Name                        | Purpose | Main strengths / advantages |
|-----------------------------------| --- | --- |
| `unit-test`                       | Add or fix unit tests for Go code | Emphasizes table-driven tests, subtests, and bug hunting, especially boundaries, mapping loss, and concurrency issues |
| `tdd-workflow`                    | Apply practical TDD in Go services | Emphasizes `Red -> Green -> Refactor` evidence and risk-path coverage |
| `api-integration-test`            | Build, maintain, and run Go integration tests for internal APIs and service-to-service calls | Emphasizes real runtime config, explicit gates, timeout/retry safety, and failure diagnosis |
| `thirdparty-api-integration-test` | Build and run real integration tests for third-party APIs | Uses explicit run gates, timeout controls, and safe execution constraints for external contract validation |
| `e2e-test`                        | Design, maintain, and run E2E tests for key user journeys | Balances exploration, regression coverage, CI integration, and artifact retention with a focus on reliability |
| `fuzzing-test`                    | Generate Go fuzz tests | Runs an applicability gate first and refuses unsuitable targets, avoiding low-value fuzz cases |
| `systematic-debugging`            | Investigate bugs, failures, and unexpected behavior systematically | Requires root-cause analysis before fixes, avoiding guess-driven debugging |

For a full example, see: https://github.com/johnqtcg/issue2md (`.github/workflows/ci.yml`)

### Search, Research, and Reports

These skills are suited for information gathering, fact-checking, comparison, and formal research output.

| Skill Name | Purpose | Main strengths / advantages |
| --- | --- | --- |
| `google-search` | Use Google-style search for information gathering, fact verification, and source checking | Emphasizes query classification, evidence chains, cross-checking, and reusable search strings |
| `deep-research` | Produce source-backed deep research and analysis | Enforces content extraction, cross-verification, and anti-hallucination checks for research and comparison work |

### Technical Docs and Writing

These skills focus on turning engineering knowledge into maintainable documents that teams can reuse directly.

| Skill Name | Purpose | Main strengths / advantages |
| --- | --- | --- |
| `update-doc` | Keep repository documentation aligned with the latest code | Focuses on scoped doc patches, docs-drift checks, project-type routing, and evidence-backed synchronization of README and related docs |
| `readme-generator` | Generate or refactor project `README.md` files using repository evidence | Emphasizes repository-shape detection, evidence-based structure, maintainable README patterns, and adaptation across service, library, CLI, and monorepo projects |
| `tech-doc-writer` | Write, review, and improve technical documents such as runbooks, troubleshooting guides, API docs, and RFC/ADR-style design docs | Uses type classification, audience analysis, quality gates, and anti-staleness rules to produce clearer, more maintainable technical documentation |

### Tool Execution and Task Automation

These skills focus more on getting a task executed than on code quality itself.

| Skill Name | Purpose | Main strengths / advantages |
| --- | --- | --- |
| `yt-dlp-downloader` | Generate and run `yt-dlp` download commands | Probes formats before downloading and supports single videos, playlists, audio extraction, subtitles, and authenticated content |
| `local-transcript` | Transcribe local audio or video files into `txt` / `pdf` / `docx` outputs | Uses an accelerated local ASR pipeline plus post-processing and proofreading to produce cleaner Chinese transcripts with paragraphing, punctuation normalization, and multi-format export |

<a id="en-evaluate-and-output"></a>
## Review Reports and Output Examples

What makes this repository different from a typical “skills example repo” is that it does not just show the skills. It also shows:

1. why a given skill is good
2. what it actually produced in real tasks

You can read them side by side:

- review reports: [evaluate/](evaluate)
- output examples: [outputexample/](outputexample)

Typical examples:

- `google-search`
  - review: [evaluate/google-search-skill-eval-report.md](evaluate/google-search-skill-eval-report.md)
  - output: [outputexample/google-search/ai-bubble-or-platform-shift-march-2026.pdf](outputexample/google-search/ai-bubble-or-platform-shift-march-2026.pdf)
- `unit-test`
  - review: [evaluate/unit-test-skill-eval-report.md](evaluate/unit-test-skill-eval-report.md)
  - output: [outputexample/unit-test/](outputexample/unit-test)
- `yt-dlp-downloader`
  - output screenshots: [outputexample/yt-dlp-downloader/](outputexample/yt-dlp-downloader)

<a id="en-governance"></a>
## Governance

If you want to contribute or need repository governance details, start here:

- Contribution guide: [CONTRIBUTING.md](CONTRIBUTING.md)
- Security policy: [SECURITY.md](SECURITY.md)
- Code of conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)

<a id="en-audience"></a>
## Who This Is For

- people who want to systematically learn how to write high-quality skills
- people who want to turn Claude Code / Agent capabilities into reusable assets
- people who want to study the full loop of methodology + skill + review + output example
- people who want to integrate AI capability into real engineering workflows rather than stop at prompt demos

<a id="en-license"></a>
## License

This project is licensed under MIT. See [LICENSE](LICENSE).

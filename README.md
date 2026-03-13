# awesome-skills

![License](https://img.shields.io/badge/license-MIT-blue)

An open-source project focused on high-quality Skill design, review, validation, and workflow integration.

This is not just a collection of `SKILL.md` examples. It is a full closed loop for building high-quality skills:

- methodology docs: explain why the design works
- skill examples: show what high-quality skills look like
- review reports: explain why those skills are good and where they can improve
- output examples: show what those skills can actually produce in real tasks

## Table of Contents

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

<a id="en-overview"></a>
## Overview

- Project scope: high-quality skill methodology + skill assets + review reports + output examples.
- Main documentation entry: [bestpractice/README.md](/Users/john/awesome-skills/bestpractice/README.md).
- Number of skills: `16` (see [skills/](/Users/john/awesome-skills/skills)).
- Number of review reports: `32`, paired in Chinese and English (see [evaluate/](/Users/john/awesome-skills/evaluate)).
- Number of output example directories: `10` (see [outputexample/](/Users/john/awesome-skills/outputexample)).

The core goal of this repository is not to show how to write prompts. It is to answer three harder questions:

1. How should a high-quality skill be designed?
2. How do you prove that it actually works?
3. How do you integrate it into daily engineering workflows instead of leaving it as a demo?

<a id="en-highlights"></a>
## Highlights

### 1. Documentation quality: highly systematic and practical

The most valuable part of this project is not the high-quality skills under [skills/](/Users/john/awesome-skills/skills), but the full methodology under [bestpractice/](/Users/john/awesome-skills/bestpractice).
It is highly useful as a reference for structured thinking, abstraction, and engineering execution.

### 2. Clear structure and strong layering

The best-practice docs follow the same "progressive disclosure" philosophy they recommend for skill design. The content is split into:

- fundamentals
- advanced topics
- evaluation
- integration
- appendices and navigation docs

Readers can jump directly to the part they need based on experience level and goals, instead of reading everything linearly. The structure itself demonstrates how to write long-form docs that work well for both AI agents and human readers.

### 3. Original and highly distilled design patterns

This project distills a set of high-value patterns from many real tasks, including:

- mandatory gates
- anti-example teaching
- honest degradation
- progressive disclosure
- output contracts
- quantitative evaluation

These patterns target the most common LLM failure modes directly: hallucinations, false positives, context overflow, unstable output, and weak verifiability.

### 4. Quantitative instead of intuition-based

[bestpractice/Evaluation.md](/Users/john/awesome-skills/bestpractice/Evaluation.md) is valuable because it turns “is this skill good?” from a subjective feeling into something measurable.

The focus is no longer “this looks good,” but:

- whether the trigger behavior is accurate
- whether real task performance is better than the no-skill baseline
- whether the token cost is worth it

That is also why [evaluate/](/Users/john/awesome-skills/evaluate) exists: the repository does not just provide skills, it also provides review evidence.

### 5. Strong executability and a real engineering loop

This project does not stop at `What` and `Why`; it also covers `How`. You can see the full chain directly in the repository:

- methodology in [bestpractice/](/Users/john/awesome-skills/bestpractice)
- skill examples in [skills/](/Users/john/awesome-skills/skills)
- reviews in [evaluate/](/Users/john/awesome-skills/evaluate)
- outputs in [outputexample/](/Users/john/awesome-skills/outputexample)

That makes it more than abstract discussion. It is an engineering asset that can be reused, inspected, and iterated over time.

### 6. The real moat is not “using AI,” but turning AI into reliable capability

If you master this system, the result is not just “writing better prompts.” It is a rarer and more valuable combined capability:

- turning tacit experience into structured rules
- constraining unstable AI output into reusable workflows
- integrating skills into real engineering processes instead of leaving them as demos
- proving value with reviews and examples instead of talking in abstractions

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
| [bestpractice/](/Users/john/awesome-skills/bestpractice) | Explains how to write high-quality skills, how to evaluate them, and how to integrate them into workflows |
| [skills/](/Users/john/awesome-skills/skills) | High-quality skill examples shaped by the methodology |
| [evaluate/](/Users/john/awesome-skills/evaluate) | Formal review reports for skills, including strengths, weaknesses, and improvement points |
| [outputexample/](/Users/john/awesome-skills/outputexample) | Real outputs from skills, such as PDFs, test code, Makefiles, CI configs, and screenshots |

<a id="en-reading-path"></a>
## Recommended Reading Path

If this is your first time in the project, this order works best:

1. Start with [bestpractice/README.md](/Users/john/awesome-skills/bestpractice/README.md) to build the overall picture
2. Open a specific skill, for example [skills/google-search/SKILL.md](/Users/john/awesome-skills/skills/google-search/SKILL.md)
3. Read its review report, for example [evaluate/google-search-skill-eval-report.md](/Users/john/awesome-skills/evaluate/google-search-skill-eval-report.md)
4. Then look at its real output, for example [outputexample/google-search/中国制造2025目标完成度研究.pdf](/Users/john/awesome-skills/outputexample/google-search/中国制造2025目标完成度研究.pdf)

If you prefer Chinese, start from [bestpractice/README.zh-CN.md](/Users/john/awesome-skills/bestpractice/README.zh-CN.md).

<a id="en-bestpractice"></a>
## Documentation System

[bestpractice/](/Users/john/awesome-skills/bestpractice) is the methodology entry point for the whole project:

- [Fundamentals.md](/Users/john/awesome-skills/bestpractice/Fundamentals.md)
- [Advanced.md](/Users/john/awesome-skills/bestpractice/Advanced.md)
- [Evaluation.md](/Users/john/awesome-skills/bestpractice/Evaluation.md)
- [Integration.md](/Users/john/awesome-skills/bestpractice/Integration.md)

These documents mainly answer:

- why skills matter as a key abstraction for AI coding assistants
- what design patterns high-quality skills should follow
- how to evaluate the real value of a skill quantitatively
- how to integrate skills into engineering workflows instead of leaving them inside a single chat

<a id="en-skills"></a>
## Skill Examples

All high-quality skills in this project live under [skills/](/Users/john/awesome-skills/skills), with each skill centered on its own `SKILL.md`. They are not isolated capabilities. They can be grouped by use case, and the backend-oriented skills can work together as a full quality pipeline.

### Backend Development: a complete quality pipeline

The value of the backend-related skills is not just that each skill is useful on its own. They can connect end-to-end and form an engineering workflow from coding to merge:

```text
Coding
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

### Tool Execution and Task Automation

These skills focus more on getting a task executed than on code quality itself.

| Skill Name | Purpose | Main strengths / advantages |
| --- | --- | --- |
| `yt-dlp-downloader` | Generate and run `yt-dlp` download commands | Probes formats before downloading and supports single videos, playlists, audio extraction, subtitles, and authenticated content |

<a id="en-evaluate-and-output"></a>
## Review Reports and Output Examples

What makes this repository different from a typical “skills example repo” is that it does not just show the skills. It also shows:

1. why a given skill is good
2. what it actually produced in real tasks

You can read them side by side:

- review reports: [evaluate/](/Users/john/awesome-skills/evaluate)
- output examples: [outputexample/](/Users/john/awesome-skills/outputexample)

Typical examples:

- `google-search`
  - review: [evaluate/google-search-skill-eval-report.md](/Users/john/awesome-skills/evaluate/google-search-skill-eval-report.md)
  - output: [outputexample/google-search/中国制造2025目标完成度研究.pdf](/Users/john/awesome-skills/outputexample/google-search/中国制造2025目标完成度研究.pdf)
- `unit-test`
  - review: [evaluate/unit-test-skill-eval-report.md](/Users/john/awesome-skills/evaluate/unit-test-skill-eval-report.md)
  - output: [outputexample/unit-test/](/Users/john/awesome-skills/outputexample/unit-test)
- `yt-dlp-downloader`
  - output screenshots: [outputexample/yt-dlp-downloader/](/Users/john/awesome-skills/outputexample/yt-dlp-downloader)

<a id="en-governance"></a>
## Governance

If you want to contribute or need repository governance details, start here:

- Contribution guide: [CONTRIBUTING.md](/Users/john/awesome-skills/CONTRIBUTING.md)
- Security policy: [SECURITY.md](/Users/john/awesome-skills/SECURITY.md)
- Code of conduct: [CODE_OF_CONDUCT.md](/Users/john/awesome-skills/CODE_OF_CONDUCT.md)

<a id="en-audience"></a>
## Who This Is For

- people who want to systematically learn how to write high-quality skills
- people who want to turn Claude Code / Agent capabilities into reusable assets
- people who want to study the full loop of methodology + skill + review + output example
- people who want to integrate AI capability into real engineering workflows rather than stop at prompt demos

<a id="en-license"></a>
## License

This project is licensed under MIT. See [LICENSE](/Users/john/awesome-skills/LICENSE).

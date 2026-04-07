# Skills Overview

This section contains all installable skills collected in `awesome-skills`.

The repository currently exposes two layers:

- **21 production-ready skills** with full rationale, evaluation, and output-example coverage
- **8 multi-agent Go review components** used by the review orchestration architecture

Each skill is organized as its own directory and uses `SKILL.md` as the main entrypoint. The left navigation is the fastest way to jump to a specific skill.

Production-ready groups:

- Backend workflow: `go-makefile-writer`, `git-commit`, `create-pr`, `go-ci-workflow`
- Quality and testing: `unit-test`, `tdd-workflow`, `api-integration-test`, `e2e-test`, `fuzzing-test`
- Review and security: `go-code-reviewer`, `security-review`, `systematic-debugging`
- Research and docs: `google-search`, `deep-research`, `update-doc`, `readme-generator`, `tech-doc-writer`
- Task execution: `yt-dlp-downloader`, `local-transcript`

Multi-agent review components:

- Orchestrator: `go-review-lead`
- Vertical reviewers: `go-security-review`, `go-concurrency-review`, `go-error-review`, `go-logic-review`, `go-performance-review`, `go-quality-review`, `go-test-review`

These 8 review components are installable and regression-tested, but they are not currently counted in the repository's "production-ready skill" total.

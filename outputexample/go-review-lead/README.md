# Go Multi-Agent Code Review — Deployment Guide

This directory contains ready-to-deploy agent definition files for the 8-Agent Go code review system described in [`bestpractice/Architecture.md`](../../bestpractice/Architecture.md) §17–18.

## What's in This Directory

```
agents/
├── go-review-lead.md          # Orchestrator: triage + consolidation (never reviews code itself)
├── go-security-reviewer.md    # Worker: SQL injection, XSS, secrets, auth flaws
├── go-concurrency-reviewer.md # Worker: race conditions, goroutine leaks, deadlocks
├── go-performance-reviewer.md # Worker: allocations, N+1, slice pre-allocation
├── go-error-reviewer.md       # Worker: error wrapping, resource lifecycle, panics
├── go-quality-reviewer.md     # Worker: naming, structure, modern Go idioms
├── go-test-reviewer.md        # Worker: table-driven tests, coverage, assertions
└── go-logic-reviewer.md       # Worker: boundary conditions, state machines, nil safety
```

Each file is a Claude Code agent definition (YAML frontmatter + system prompt). The agents are lightweight by design — they load their domain knowledge at runtime via the Skill tool, so the definition files stay short and maintainable.

## Prerequisites

Each Worker Agent loads a corresponding vertical skill at runtime. These skills must be installed before the agents will work:

| Agent file | Required skill |
|-----------|----------------|
| `go-review-lead.md` | `go-review-lead` skill |
| `go-concurrency-reviewer.md` | `go-concurrency-review` skill |
| `go-performance-reviewer.md` | `go-performance-review` skill |
| `go-error-reviewer.md` | `go-error-review` skill |
| `go-security-reviewer.md` | `go-security-review` skill |
| `go-quality-reviewer.md` | `go-quality-review` skill |
| `go-test-reviewer.md` | `go-test-review` skill |
| `go-logic-reviewer.md` | `go-logic-review` skill |

The source files for all 8 skills are in the `skills/` directory of this repository (e.g. `skills/go-concurrency-review/SKILL.md`).

## Installation

### Step 1 — Install the skills

Copy the skill directories to your Claude Code user-level skills location. The default path is `~/.claude/skills/`; adjust if your setup differs.

```bash
# Run from the repository root
for skill in go-review-lead \
             go-concurrency-review \
             go-performance-review \
             go-error-review \
             go-security-review \
             go-quality-review \
             go-test-review \
             go-logic-review; do
  cp -r "skills/$skill" ~/.claude/skills/
done
```

### Step 2 — Install the agent definitions

Copy the agent definition files to `~/.claude/agents/`. Create the directory if it doesn't exist.

```bash
mkdir -p ~/.claude/agents
cp outputexample/go-review-lead/agents/*.md ~/.claude/agents/
```

Claude Code discovers agents in `~/.claude/agents/` automatically — no further configuration is needed.

### Verify

List installed agents to confirm:

```bash
ls ~/.claude/agents/ | grep go-
# Expected output:
# go-concurrency-reviewer.md
# go-error-reviewer.md
# go-logic-reviewer.md
# go-performance-reviewer.md
# go-quality-reviewer.md
# go-review-lead.md
# go-security-reviewer.md
# go-test-reviewer.md
```

## Usage

Once installed, trigger a full Go review from any Claude Code session in a Go repository:

```
@go-review-lead review this PR
```

or more explicitly:

```
Use go-review-lead to review the Go changes in src/
```

The Lead Agent will:

1. Run `git diff -- '*.go'` to identify changed Go files
2. Run a compile pre-check (`go build`)
3. Select review depth (Lite / Standard / Strict) based on file count and risk signals
4. Triage the diff through 4 phases to decide which Worker Agents to dispatch
5. Launch selected workers **in parallel** — each loads its vertical skill and runs independently
6. Consolidate all findings into a unified report with `REV-NNN` IDs, deduplication, and severity ordering

You can also invoke any Worker Agent directly for a focused review:

```
@go-concurrency-reviewer review internal/worker/pool.go
```

## Model Configuration

All agents default to `sonnet` (see the `model:` field in each `.md` file). This is intentional: each Worker Agent focuses on a single dimension, so a mid-tier model with full attention on one domain outperforms a top-tier model splitting attention across all dimensions simultaneously. See [`Architecture.md` §17.3.3](../../bestpractice/Architecture.md#1733-architecture-over-model-reducing-dependency-on-top-tier-reasoning-models) for the rationale.

To change the model for a specific agent, edit the `model:` field before copying:

```bash
# Example: use haiku for quality/logic workers to reduce cost further
sed -i '' 's/model: sonnet/model: haiku/' ~/.claude/agents/go-quality-reviewer.md
sed -i '' 's/model: sonnet/model: haiku/' ~/.claude/agents/go-logic-reviewer.md
```

## Architecture Overview

For the complete design rationale — including the attention dilution problem, triage logic, Grep-Gated execution protocol, three-round validation results, and the model cost trade-off analysis — see:

- English: [`bestpractice/Architecture.md`](../../bestpractice/Architecture.md) §17–18
- Chinese: [`bestpractice/架构篇.md`](../../bestpractice/架构篇.md) §17–18

# Repo Discovery Protocol

Run this protocol before writing any file paths into a plan.

## Step 1: Project Structure

```bash
ls -1 .                          # top-level directories
ls .github/workflows/ 2>/dev/null # CI config
```

Identify:
- Source directories: `src/`, `lib/`, `cmd/`, `internal/`, `pkg/`, `app/`
- Test directories: `test/`, `tests/`, `__tests__/`, co-located `_test.go`
- Config: `Makefile`, `Dockerfile`, `docker-compose.yml`
- Docs: `docs/`, `README.md`, `CONTRIBUTING.md`, `CLAUDE.md`

## Step 2: Tech Stack Detection

| File | Indicates |
|---|---|
| `go.mod` | Go — check version, module path |
| `package.json` | Node — check framework, test runner, monorepo (workspaces) |
| `pyproject.toml` / `setup.py` | Python — check framework, test runner |
| `Cargo.toml` | Rust |
| `pom.xml` / `build.gradle` | Java/Kotlin |
| `Makefile` | Available make targets (test, lint, build, ci) |

Read the detected config file to extract:
- Language version
- Key dependencies
- Test command (`scripts.test`, `make test`, etc.)
- Build command

## Step 3: Test Convention Discovery

```bash
# Find test files (adapt glob to detected language)
# Go:    **/*_test.go
# Node:  **/*.test.{ts,tsx,js} or **/__tests__/**
# Python: **/test_*.py or **/*_test.py
```

Read 1-2 representative test files to learn:
- Test framework and assertion library
- Helper/fixture patterns
- Naming conventions

## Step 4: CI/Build Discovery

Check for:
- `.github/workflows/*.yml` — GitHub Actions
- `Makefile` — local build targets
- `Dockerfile` — containerized build
- `.gitlab-ci.yml`, `Jenkinsfile`, `bitbucket-pipelines.yml`

Extract: what gates exist before merge (lint, test, build, coverage)

## Step 5: Commit Convention Discovery

```bash
git log --oneline -10
```

Check for:
- Conventional Commits (`feat:`, `fix:`, `chore:`)
- Scope patterns (`feat(auth):`)
- Co-author conventions

## Path Verification Rules

After discovery, when writing paths in the plan:

| Status | Meaning | How to Verify |
|---|---|---|
| `[Existing]` | File exists NOW | Verified via Glob or Read |
| `[New]` | Will be created | Parent directory verified to exist |
| `[Inferred]` | Based on project convention | Pattern matches but file not directly checked |
| `[Speculative]` | Degraded mode guess | No verification possible |

**Hard rule**: NEVER present a `[Speculative]` path as `[Existing]`.
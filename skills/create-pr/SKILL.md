---
name: create-pr
description: Create evidence-backed pull requests to the GitHub main branch with strict preflight, quality, and security gates. Use when users ask to create/submit/open/update a PR to main (including private repos), decide draft vs ready state, and provide reviewer-ready context for team review.
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash(git diff*), Bash(git log*), Bash(git status*), Bash(git push*), Bash(git branch*), Bash(gh pr*), Bash(gh auth*)
---

# Create PR

Create a high-quality PR to `main` that is easy to review, safe to merge, and explicit about risk.

## Quick Reference

| Step | Gate | What it checks | Blocker? |
|------|------|---------------|----------|
| 1 | — | Scope the change | — |
| 2 | **A** | GitHub auth, remote, base branch, branch protection | Yes |
| 3 | **B** | Not on `main`, branch naming, no conflicts, synced with `origin/main` | Yes |
| 4 | **C** | High-risk areas, change size (≤400 / 401-800 / >800 lines) | Warn |
| 5 | **D** | Tests, lint, build | Yes |
| 6 | **E** | Secret scan, gosec, govulncheck | Yes (high-confidence) |
| 7 | **F** | Docs/changelog, backward compatibility, breaking changes | Yes |
| 8 | **G** | Conventional Commits (commits + PR title), self-review | Yes |
| 9 | — | Compose PR title/body | — |
| 10 | — | `git push -u` + `gh pr create` | — |
| 11 | **H** | Post-create: base/head, title/body render, draft/ready state | Informational |

**Confidence → State**: `confirmed` → ready | `likely` → ready | `suspected` → draft

## Non-Negotiables

- Never open a PR from `main` as the head branch.
- Never push secrets, credentials, or local-only configuration.
- Never claim a gate passed without command or code evidence.
- Fail closed: if a mandatory gate cannot run, keep the PR as `draft` and record the gap.
- Prefer non-interactive commands for reproducibility.
- **One PR = one problem.** A single feature, a single bug fix, or a single refactor. Do not mix unrelated changes.
- **PR title must follow Conventional Commits format** (`<type>(<scope>): <subject>`, subject ≤ 50 chars, imperative, no period). This is critical for Squash-and-merge workflows where the PR title becomes the final commit message on `main`.

## PR Granularity Guidelines

- Target **200–400 changed lines** per PR. Beyond 400 lines, review quality drops sharply.
- Large features should be split into serial PRs; use feature flags to hide incomplete work.
- Do not sneak formatting, import reordering, or unrelated refactors into a feature PR — submit them as separate PRs.
- Before creating the PR, perform a **self-review** of your own diff (`git diff origin/main...HEAD`). Fix obvious issues before requesting others' time.

## Readiness Confidence (Mandatory)

Label final PR readiness with one confidence level:

- `confirmed`: all mandatory gates executed and passed, no unresolved high-risk item.
- `likely`: one non-blocking gate could not run, with explicit follow-up owner.
- `suspected`: multiple gates unverified or key evidence missing.

Do not mark a PR `ready` with `suspected` confidence.

## Suppression Rules

Suppress a gate only when: (1) gate is N/A for changed files, (2) tooling unavailable, or (3) equivalent upstream check proves the condition (cite check name/URL).
Any suppression must be recorded in `Uncovered Risk List` with residual risk. Keep PR as `draft` if the uncovered area can hide merge-blocking defects.

## Fixed Process + Mandatory Gates

Run the following process in order.

1. Scope the change.
2. Run `Gate A`: authentication and repository preflight.
3. Run `Gate B`: branch hygiene and sync with `origin/main`.
4. Run `Gate C`: change-risk classification.
5. Run `Gate D`: quality evidence (tests/lint/build).
6. Run `Gate E`: security and secret-leak checks.
7. Run `Gate F`: documentation and compatibility checks.
8. Run `Gate G`: commit hygiene and commit message quality.
9. Prepare PR title/body with structured evidence.
10. Push branch and create PR to `main`.
11. Run `Gate H`: post-create verification.
12. Decide `draft` vs `ready` from gate results.
13. Report findings first, then PR link, then follow-up actions.

If a mandatory gate cannot execute, explicitly mark it as uncovered and do not claim full readiness.

> **Fast path (≤100 changed lines, no high-risk area):** Gates C and F may be combined into a single step — confirm change size is small, no breaking changes, no doc updates needed, then proceed.

### Gate A: Authentication and Repository Preflight (Mandatory)

```bash
git rev-parse --is-inside-work-tree
git remote -v
gh auth status -h github.com
gh repo view --json nameWithOwner,isPrivate,viewerPermission,defaultBranchRef
git ls-remote --heads origin main
# Best-effort — may 404/403 on repos without protection rules; suppress if so.
gh api repos/{owner}/{repo}/branches/main/protection
```

Blocker: not authenticated, no `origin` remote, no permission, or `main` missing on remote.
If branch protection query fails (404/403), record in Uncovered Risk List and continue.

### Gate B: Branch Hygiene and Sync (Mandatory)

- Ensure head branch is not `main`:
  - `git rev-parse --abbrev-ref HEAD`
- **Branch naming check**: verify the branch name matches `<type>/<short-description>` (e.g. `feature/oauth-login`, `fix/nil-pointer-getuser`, `refactor/db-pool`).
  - Type prefixes: `feature`, `fix`, `refactor`, `hotfix`, `release`, `docs`, `chore`, `test`, `perf`, `ci`.
  - If the name does not match, report as a **warning** (non-blocking) suggesting the user rename with `git branch -m <new-name>`.
- Ensure no unresolved conflicts or conflict markers:
  - `git status --porcelain`
  - `rg -n '^(<<<<<<<|=======|>>>>>>>)' .`
- Sync with latest main:
  - `git fetch origin main`
  - `git merge-base --is-ancestor origin/main HEAD` to verify branch includes latest main.
  - If behind, report as blocker — the user must rebase or merge manually.
    Do NOT auto-rebase; an unattended rebase can leave the tree in a conflicted state.

Blocker conditions:

- Current branch is `main`.
- Working tree is not clean (uncommitted changes).
- Branch is behind `origin/main` (rebase or merge required).
- Unresolved merge entries or conflict markers detected.

### Gate C: Change-Risk Classification (Mandatory)

Summarize changed files and flag high-risk areas:

- auth/authz, payment, migration, concurrency, public API, infra config, secrets.
- If high-risk areas are touched, require explicit risk and rollback notes in PR body.

**Change-size check**: compute total added+removed lines from `git diff --stat origin/main...HEAD`.
- **≤ 400 lines**: normal.
- **401–800 lines**: warn the user that review quality may suffer; suggest splitting if feasible.
- **> 800 lines**: strong warning; recommend splitting into smaller PRs unless the change is inherently atomic (e.g. auto-generated code, large migration).

Use:

- `git diff --name-status origin/main...HEAD`
- `git diff --stat origin/main...HEAD`

> **Monorepo**: If multiple `go.mod` exist, scope gates D/E to changed modules only (walk up from each changed file to find its nearest `go.mod`).

### Gate D: Quality Evidence (Mandatory)

Run project-standard checks first; fallback to language defaults.

Preferred order:

1. repo-defined check target (`make test`, `make lint`, etc.)
2. language checks (for Go: `go test ./...`, `golangci-lint run`)

Rules:

- Record exact command and pass/fail result.
- Do not hide failures; include top failure cause.
- If a command is unavailable, mark uncovered risk.

### Gate E: Security and Secret Checks (Mandatory)

```bash
# Filename risk scan
git diff --name-only origin/main...HEAD | rg -i '(\.env(\..*)?|id_rsa|id_dsa|\.pem|\.p12|\.key)$'
# Content risk scan
git diff origin/main...HEAD | rg -n '(AKIA[0-9A-Z]{16}|-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----|ghp_[A-Za-z0-9]{36}|gho_[A-Za-z0-9]{36}|xox[baprs]-|AIza[0-9A-Za-z\-_]{35}|password\s*[:=]|secret\s*[:=]|token\s*[:=])'
# Go-specific (when available)
gosec ./...
govulncheck ./...
```

Any match from the rg scans requires explicit resolution before marking ready. Any unresolved high-confidence issue keeps PR in `draft`.

### Gate F: Documentation and Compatibility (Mandatory)

- Ensure docs/changelog/readme updates for externally visible behavior changes.
- Check backward compatibility and migration impact.
- If breaking change exists, mark clearly in PR title/body and include rollout/rollback notes.

### Gate G: Commit Hygiene and PR Title (Mandatory)

- Ensure commit set matches the scoped change only — no unrelated commits in the range.
- All commits should use **Conventional Commit** format: `<type>(<scope>): <subject>`.
  - Subject: imperative mood, ≤ 50 chars, no trailing period.
  - Body (when present): explains **why**, each line ≤ 72 chars.
  - Footer (when present): `BREAKING CHANGE:`, `Closes #`, `Refs:`.
- **PR title** must also follow Conventional Commits format. For Squash-and-merge workflows the PR title becomes the sole commit message on `main`, so its quality is critical.
- Do not amend existing commits unless user explicitly asks.
- If no commit exists, create one before PR creation.
- Perform a **self-review** of the full diff (`git diff origin/main...HEAD`) before proceeding to PR creation. Fix any obvious issues found.

### Gate H: Post-Create Verification (Mandatory)

After creation:

- Confirm PR points to `base=main` and `head=<feature branch>`.
- Confirm title/body rendered correctly.
- Confirm draft/ready state matches gate outcomes.
- Optionally check CI status with `gh pr checks` (non-blocking; reported as informational).
  CI results are logged but do not change the gate verdict — CI may still be running.

Use:

- `gh pr view --json number,url,state,isDraft,baseRefName,headRefName`
- `gh pr checks <pr-number>` (optional, informational)

## Draft vs Ready Decision

Mark `ready` only when all mandatory gates pass or are suppressed with low residual risk.

Keep `draft` when:

- any mandatory gate failed,
- important evidence is missing,
- unresolved design/security/performance questions remain.

## Required PR Body Structure

Use the template in `references/pr-body-template.md`.

Minimum sections:

1. Problem/Context
2. What Changed
3. Why This Approach
4. Risk and Rollback Plan
5. Test Evidence (commands + key outputs)
6. Security Notes
7. Breaking Changes / Migration Notes
8. Reviewer Checklist

## Command Playbook

Use this baseline workflow and adapt to repo conventions:

```bash
# Preflight (repo=., base=main, head=current branch)
git rev-parse --is-inside-work-tree
gh auth status -h github.com
git rev-parse --abbrev-ref HEAD

# Sync
git fetch origin main
git merge-base --is-ancestor origin/main HEAD  # fails if behind

# Evidence
git diff --name-status origin/main...HEAD
go test ./...
golangci-lint run

# Push + PR (optional: --issue, --reviewer, --label)
git push -u origin HEAD
gh pr create --base main --head "$(git rev-parse --abbrev-ref HEAD)" \
  --title "<type(scope): subject>" --body-file /tmp/pr_body.md
gh pr edit <pr-number> --add-reviewer <user1>,<user2> --add-label <label>
gh pr view --json number,url,state,isDraft,baseRefName,headRefName
```

## Output Contract

Return a concise report in this order:

1. Gate results (`PASS/FAIL/SUPPRESSED/N/A`) with one-line evidence.
2. `Uncovered Risk List` (if any): gap, impact, owner, follow-up.
3. PR metadata: number, URL, draft/ready, base/head.
4. Next actions needed from user/reviewers.

## Load References Selectively

When executing preflight, quality, or security gate checks:
→ Load `references/create-pr-checklists.md` for the full 30-item gate checklist (preflight, quality, security, compatibility, docs gates with PASS/FAIL/SUPPRESSED/N/A verdicts).

When composing the PR body:
→ Load `references/pr-body-template.md` for the 8-section Markdown template (Problem/Context, What Changed, Why This Approach, Risk and Rollback, Test Evidence, Security Notes, Breaking Changes, Reviewer Checklist).

When deciding squash vs. merge vs. rebase strategy:
→ Load `references/merge-strategy-guide.md` for merge strategy selection table, PR title conventions per strategy, and commit message landing rules.

When running the automated gate + PR creation workflow in one command:
→ Load `references/bundled-script-guide.md` for `scripts/create_pr.py` usage, flags, and output contract.

When the repo uses a `.create-pr.yaml` config file or you need to create one:
→ Load `references/create-pr-config.example.yaml` for all supported config keys and their defaults.

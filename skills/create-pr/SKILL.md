---
name: create-pr
description: Create evidence-backed pull requests to the GitHub main branch with strict preflight, quality, and security gates. Use when users ask to create/submit/open/update a PR to main (including private repos), decide draft vs ready state, and provide reviewer-ready context for team review.
---

# Create PR

Create a high-quality PR to `main` that is easy to review, safe to merge, and explicit about risk.

## Canonical Implementation

The bundled `scripts/create_pr.py` is the **preferred execution path** for Gates A–H: when Python 3 is available, run the gates through it (`references/bundled-script-guide.md`) instead of hand-executing the prose commands below. The prose workflow serves two roles — the **specification** the script must implement, and the **fallback** for environments without Python. If the two ever disagree, the prose specification wins and the script is the side to fix. Shared constants (size thresholds, confidence levels, gate statuses, secret-scan semantics) are consistency-tested in `scripts/tests/test_skill_contract.py` — update both sides together.

The script distinguishes `blocks_publish` from `blocks_ready`. Repository identity/auth failures, publishing from `main`, unsafe branch state, incomplete diff/security evidence, high-confidence secret findings, and invalid PR titles are hard publication blockers: stop before `git push`. Quality, documentation, narrative, or compatibility gaps may still publish a draft, but never a ready PR.

## Quick Reference

| Step | Gate | What it checks | Blocker? |
|------|------|---------------|----------|
| 1 | — | Scope the change | — |
| 2 | **A** | GitHub auth, remote, base branch, branch protection | Yes |
| 3 | **B** | Not on `main`, branch naming, no conflicts, synced with `origin/main` | Yes |
| 4 | **C** | High-risk areas, change size (≤400 / 401-800 / >800 lines) | Warn |
| 5 | **D** | Tests, lint, build — graded per dimension | Yes |
| 6 | **E** | Secret scan over the whole pushed range, gosec, govulncheck | Yes (high-confidence) |
| 7 | **F** | Docs/changelog, backward compatibility, breaking changes | Yes |
| 8 | **G** | Conventional Commits (commits + PR title), scope confirmation, self-review | Yes |
| 9 | — | Compose PR title/body | — |
| 10 | — | If no hard blocker: `git push -u` + `gh pr create` | — |
| 11 | **H** | Assert base/head, title/body render, open state, draft/ready state | Yes |

**Confidence → State**: `confirmed` → ready | `likely` → ready only for low-residual-risk suppressions | `likely` → draft when a suppression can hide a merge-blocking defect | `suspected` → draft. A hard publication blocker creates no PR.

## Non-Negotiables

- Never open a PR from `main` as the head branch.
- Never push secrets, credentials, or local-only configuration.
- Never claim a gate passed without command or code evidence.
- Never call `git push`, `gh pr create`, or `gh pr edit` after a hard publication blocker.
- Fail closed: if a mandatory gate cannot run, keep the PR as `draft` and record the gap.
- Prefer non-interactive commands for reproducibility.
- **One PR = one problem.** A single feature, a single bug fix, or a single refactor. Do not mix unrelated changes.
- **PR title must follow Conventional Commits format** (`<type>(<scope>): <subject>`, subject ≤ 50 chars, imperative, no period). Under Squash-and-merge the PR title is what GitHub pre-fills for a 2+-commit PR; a single-commit PR pre-fills that commit's own subject instead, so validate both (see `references/merge-strategy-guide.md`).
- **Verify every write target, not just the read target.** `git push origin` uses `remote.origin.pushurl` when set, git keeps it independent of the fetch URL, and a remote may have more than one — a single push then writes to all of them. Every one must resolve to the repository `gh` reports.
- **Secret evidence covers every commit being pushed**, not only the net diff. A credential added in one commit and deleted in a later commit still reaches the remote.
- **A missing check is an uncovered risk, never a pass.** Test, lint, and build are graded separately; "every discovered command succeeded" is not evidence that all three ran.

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
10. If no hard publication blocker exists, push branch and create PR to `main`; otherwise stop before push.
11. Run `Gate H`: post-create verification.
12. Decide `draft` vs `ready` from gate results.
13. Report findings first, then PR link, then follow-up actions.

If a mandatory gate cannot execute, explicitly mark it as uncovered and do not claim full readiness.

> **Fast path (≤100 changed lines, no high-risk area):** Gates C and F may be combined into a single step — confirm change size is small, no breaking changes, no doc updates needed, then proceed.

### Gate A: Authentication and Repository Preflight (Mandatory)

```bash
git rev-parse --is-inside-work-tree
git remote -v
git remote get-url origin
git remote get-url --push --all origin   # EVERY write target; --push alone returns only the first
gh auth status -h github.com
gh repo view --json nameWithOwner,isPrivate,viewerPermission,defaultBranchRef
git ls-remote --heads origin main
# Best-effort — may 404/403 on repos without protection rules; suppress if so.
gh api repos/{owner}/{repo}/branches/main/protection
```

Blocker: not authenticated, no `origin` remote, no permission, `main` missing on remote, or repository identity mismatch. The `origin` repository identity must match `gh repo view`'s `nameWithOwner`; normalize SSH/HTTPS GitHub URLs before comparing.
**The push URLs are the identities that matter for writes.** A remote may carry several push URLs, and one `git push` writes to **all** of them; `git remote get-url --push origin` returns only the first, so `--push --all` is the only complete answer (it also covers the case where no `pushurl` is set and several fetch `url` entries are used for writing). Require one distinct identity across the fetch slug, **every** push slug, and the `gh repo view` slug — compare all of them in a single check, since pairwise comparisons mask each other. Any unparseable or mismatching value is a hard publication blocker, and the evidence line must name every source it compared.
If branch protection query fails (404/403), record in Uncovered Risk List and continue.

### Gate B: Branch Hygiene and Sync (Mandatory)

- Ensure head branch is not `main`:
  - `git rev-parse --abbrev-ref HEAD`
- If `--head` is supplied, require it to equal the checked-out branch; `git push origin HEAD` must never target a different branch than `gh pr create --head`.
- **Branch naming check**: verify the branch name matches `<type>/<short-description>` (e.g. `feature/oauth-login`, `fix/nil-pointer-getuser`, `refactor/db-pool`).
  - Type prefixes: `feature`, `fix`, `refactor`, `hotfix`, `release`, `docs`, `chore`, `test`, `perf`, `ci`.
  - If the name does not match, report as a **warning** (non-blocking) suggesting the user rename with `git branch -m <new-name>`.
- Ensure no unresolved conflicts or conflict markers:
  - `git status --porcelain`
  - `grep -rnE '^(<<<<<<<|=======|>>>>>>>)' .`
- Sync with latest main:
  - `git fetch origin main`
  - `git merge-base --is-ancestor origin/main HEAD` to verify branch includes latest main.
  - If behind, report as blocker — the user must rebase or merge manually.
    Do NOT auto-rebase; an unattended rebase can leave the tree in a conflicted state.

Blocker conditions:

- Current branch is `main`.
- Requested head does not match the checked-out branch.
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

Grade **test**, **lint**, and **build** as three independent dimensions. Two questions are answered separately for every command, whatever its source:

1. **Which dimension is this command for?** Answered by explicit declaration or by classification.
2. **Can this command execute a check at all?** Answered by run-mode inspection — and **applied to every source, including explicit per-dimension declarations**. A declaration states intent; it is never a substitute for execution. `quality.test_cmd: ["make -n test"]` is refused exactly like a classified dry run, with the reason reported against that dimension.

Discovery per dimension:

1. explicit declaration: `quality.<dimension>_cmd` in config, or `--test-cmd` / `--lint-cmd` / `--build-cmd`
2. `--check-cmd` / `check_cmd` entries, classified from the command's **argv** — never from its text
3. repository discovery: a `Makefile` target of the same name, then language defaults (Go: `go test ./...`, `go build ./...`, `golangci-lint run` when installed)

Automatic classification is deliberately narrow, and anything it does not recognise stays **unclassified** (credited to no dimension):

- Recognised: a single simple command whose first word is a known tool — `go test|build|vet|fmt`, `golangci-lint run`, `staticcheck`, `gofmt`, `pytest`, `python -m pytest|unittest`, `cargo test|build|clippy`, `mvn`, `gradle`, `ruff check`, `eslint`, `flake8`, `pylint`, `shellcheck`, `mypy`, `tsc`, `ctest` — plus a task runner whose target names it (`make test`, `make unit-test`, `npm run lint`, `yarn build`). One compound shape is supported: `cd <dir> && <simple command>`.
- Unclassified: wrappers (`make ci`, `./scripts/verify.sh`, `bash ci.sh`), anything chaining shell operators (`go test ./... && golangci-lint run`), and anything whose tool names appear only inside arguments. `printf '%s' 'go test ./...; golangci-lint run'` prints text and runs nothing; a text search would credit all three dimensions to a command that verified nothing, so only argv[0] and its subcommand/target are trusted. Quoted arguments are fine — `go test -run 'TestBuild;lint' ./...` is still a test command.
- **Also refused (from any source): a recognised tool in a mode that executes no check.** The name being right is not evidence the check ran — `make -n test lint build` prints three recipes and runs none of them. Reject per tool: dry-run/print-only (`make -n|--dry-run|--just-print|-q|-t`, `go test|build -n`, `gradle --dry-run|-m`, `just -n`), list/collect-only (`pytest --collect-only`, `go test -list`, `ctest -N`, `cargo test --no-run`, `go test -c`), skip switches (`mvn -DskipTests`, `gradle -x test`, `npm run … --if-present`), and `--help` / `--version` / `--usage` anywhere. The sets are **per tool** because the spelling flips meaning: `make -n` is a dry run but `pytest -n 4` runs tests in parallel; `make -q` asks a question but `mvn -q` is only quiet; `cargo -V` prints a version but `ctest -V` is verbose.
- **Bundled short options count, including bundles that carry a value.** `make -sn test lint build` is `-s -n` — a silent dry run — so whole-token matching misses it. For a tool that bundles, parse a single-dash token **left to right, letter by letter, over the raw token**:
  - a non-executing letter (`n`, `q`, `t`, …) → refuse the command;
  - a letter that takes a value (`make -f`, `-C`, `-I`, `-j`, `-l`, `-o`, `-O`, `-W`; `mvn -D`, `-P`, `-T`; `gradle -P`, `-b`; `ctest -R`, `-M`) → stop: the remainder of the token is that value;
  - any non-letter → stop for the same reason.

  **Do not require the token to be all letters.** `make -snj2` (`-s -n -j2`) and `make -nf./Makefile` (`-n -f ./Makefile`) execute nothing, and an all-letters precondition skips both while `-sj2` and `-fMakefile.test` must stay credited. Only genuinely value-taking letters belong in the stop set — listing one that takes no value (`mvn -o` is offline) ends the scan early and hides a later dry-run letter. **`go` is excluded from bundle expansion on purpose** — Go's flag package has no bundling, so `-run` is one flag and must never be read as `-r -u -n`.
- **Shell expressions are scanned segment by segment.** A declared command is refused if *any* recognised segment is non-executing (`make lint && make -n test`), which is why an unrecognised wrapper (`make ci`, `bash ci.sh`) still stands: there is nothing in it to contradict the declaration.
- **The run mode can arrive through the environment, not only the argument list.** `MAKEFLAGS=n` *is* `make -n`. Parse the flag-carrying variables of each tool — `MAKEFLAGS` / `GNUMAKEFLAGS` (make), `GOFLAGS` (go), `PYTEST_ADDOPTS` (pytest), `MAVEN_ARGS` (mvn) — from **both** sources and feed the result through the same argument check:
  - assignments written in the command, whether as a shell prefix (`MAKEFLAGS=n make test`) or as a make-style argument (`make MAKEFLAGS=n test`);
  - the value **actually inherited** by the shell that will run the checks — read it from that same shell, since a login profile can export one this process never sees. This is the entry point that needs no custom command at all: an exported `MAKEFLAGS=n` turns the auto-discovered `make test` / `make lint` / `make build` into three dry runs.

  `MAKEFLAGS`-style values follow make's own rule that a leading bare word is a switch bundle (`MAKEFLAGS=sn` ≡ `-s -n`). An assignment of any other variable is not a run mode (`make TESTS=1 build`, `CGO_ENABLED=0 go test ./...` stay credited, and neither is misread as naming a target), and `VAR=value` counts as an assignment only for tools that accept one as an argument (make, just, task) — for `pytest`/`go` it is a path or package pattern.

  **Assignment precedence — measured against the tool, not assumed:**
  - **Duplicates: the last one wins**, in both layers. `MAKEFLAGS=s MAKEFLAGS=n make …` runs nothing; `MAKEFLAGS=n MAKEFLAGS=s make …` runs everything. (Keeping the *first* duplicate is the bug this rule replaces.)
  - **A shell prefix replaces the inherited value.** `MAKEFLAGS=s make …` executes even with `MAKEFLAGS=n` exported, and `MAKEFLAGS= make …` deliberately clears it.
  - **A command-line variable assignment is cumulative with the environment, not an override.** `MAKEFLAGS=n make MAKEFLAGS=s test` and `MAKEFLAGS=s make MAKEFLAGS=n test` both execute nothing, because whichever layer carries `n` still applies it. Evaluate both layers and refuse if **either** blocks.
- **If the execution mode cannot be determined, the dimension stays uncovered.** When the environment cannot be read at all, a command that reads flags from the environment earns nothing and the reason is recorded — an unverified assumption is not evidence.

Under-crediting is the safe direction: the dimension stays uncovered and the PR stays draft until the author declares the command per dimension, or declares the dimension not applicable with `quality.not_applicable` / `--quality-na`.

Rules:

- Record exact command and pass/fail result.
- Do not hide failures; include top failure cause.
- If a command is unavailable, mark uncovered risk.
- Report one verdict per dimension: `executed: <cmd>` / `N/A (declared)` / `uncovered: <reason>`. `executed` must mean a command whose documented purpose is that dimension actually ran and exited 0 — not that a command mentioning it was accepted.
- A dimension with no executed evidence keeps Gate D at `SUPPRESSED` (draft), even when every command that did run passed. Never report `PASS` because the only discovered command succeeded.
- The rendered PR body carries the same per-dimension coverage table, so reviewers see the gap instead of inferring coverage from the command list.

### Gate E: Security and Secret Checks (Mandatory)

```bash
# Filename risk scan (added/copied/modified/renamed files; do not flag deletions)
git diff --name-only --diff-filter=ACMR origin/main...HEAD | grep -Ei '(^|/)(\.env(\..*)?|id_(rsa|dsa|ecdsa|ed25519)|[^/]+\.(pem|key|p12|pfx))$'
# Content risk scan — ADDED LINES ONLY (same semantics as the bundled script:
# removed lines are already in history and are a history-rewrite concern, not a PR gate)
git diff origin/main...HEAD | grep '^+[^+]' | grep -En '(AKIA[0-9A-Z]{16}|-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----|ghp_[A-Za-z0-9]{36}|gho_[A-Za-z0-9]{36}|xox[baprs]-|AIza[0-9A-Za-z_-]{35}|password[[:space:]]*[:=]|secret[[:space:]]*[:=]|token[[:space:]]*[:=])'
# SAME content scan over every commit the push would transmit. The net diff above
# cancels out a secret that one commit adds and a later commit deletes, but
# `git push` still sends the first commit and the credential lands in remote history.
for sha in $(git rev-list origin/main..HEAD); do
  git show --format= --unified=0 "$sha" | grep '^+[^+]' | grep -En '(AKIA[0-9A-Z]{16}|-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----|ghp_[A-Za-z0-9]{36}|xox[baprs]-|password[[:space:]]*[:=]|secret[[:space:]]*[:=]|token[[:space:]]*[:=])' \
    && echo "^ found in commit $sha"
  # Filenames come from git's own path list, NOT from the patch text: a binary
  # patch, an empty new file, and a pure rename carry no +++ header at all.
  git -c core.quotePath=false show --name-only --format= -z --diff-filter=ACMR "$sha" \
    | tr '\0' '\n' | grep -Ei '(^|/)(\.env(\..*)?|id_(rsa|dsa|ecdsa|ed25519)|[^/]+\.(pem|key|p12|pfx))$'
done
# Go-specific (when available)
gosec ./...
govulncheck ./...
```

The canonical script scans added lines in all changed text diffs by default, including docs, comments, extensionless files, `.env` variants, and `.pem`/`.key`/`.p12`/`.pfx` files. It does not skip alphabetic-only assigned values merely because they lack digits or symbols. Filename checks run independently of content-extension filtering.

**Scan scope is the push range, not the net diff.** The union of (a) added lines and `ACMR` paths in `origin/main...HEAD` and (b) added lines and `ACMR` paths of every commit in `git rev-list origin/main..HEAD`.

**Enumerate paths with git, parse patches only for text.** Path lists come from `--name-only -z --diff-filter=ACMR` (NUL-separated, with `-c core.quotePath=false`); the patch body is read only to collect added *lines*. Deriving paths from `+++` headers loses every file whose patch has no header — binary blobs (`Binary files ... differ`), empty new files, and pure renames — which is exactly how a `.p12` or `id_rsa` slips through. `core.quotePath=false` matters for the same reason: git's default renders a non-ASCII path as an escaped display form (`"\351\205\215.go"`) that never matches the path parsed from the patch, so the file drops out of the content scan entirely. If the commit range cannot be enumerated or exceeds the script's commit cap, the secret evidence is incomplete — fail closed as a hard publication blocker; do not report a pass. A finding that exists only inside the history is reported with its commit, and remediation is a history rewrite (`git rebase -i` / filter-repo), not another deletion commit.

Triage matches with the same exemptions the bundled script applies: environment/config **references** (`os.Getenv(...)`, `process.env.*`, `${VAR}`) are not leaks; placeholder values (`example`, `dummy`, `changeme`, `redacted`) are not leaks; patterns listed in `.create-pr.yaml` `secret_scan.allow_patterns` are exempt. **Allow patterns and placeholder checks apply to the matched credential itself — the token or the assigned value — never to the whole line.** A real token is not exempt because the words `example` or `sample` appear elsewhere on the same line; path-level exemptions belong in `secret_scan.exclude_paths`. Structural high-signal matches (AWS key ID, private-key header, GitHub PAT, Slack token) are exempt only when the allow pattern matches the token text itself. Any surviving high-confidence filename or content match is a hard publication blocker: do not push it, even as a draft.

The built-in scan is a high-signal heuristic, not a complete secret-scanning engine. If the repository provides a dedicated scanner such as Gitleaks or secretlint, run it as a project security check and record the command/result.

### Gate F: Documentation and Compatibility (Mandatory)

- Ensure docs/changelog/readme updates for externally visible behavior changes.
- Check backward compatibility and migration impact.
- If breaking change exists, mark clearly in PR title/body and include rollout/rollback notes.
- `compat_status` has three values and `unknown` is not a pass: Gate F stays `SUPPRESSED` and the generated body must render `Breaking change: unknown — not assessed`, `Compatibility: unknown (not assessed)`, and the list of still-unconfirmed questions. Never render an unassessed change as `non-breaking`.
- Require concrete `Problem/Context` and `Why This Approach` content. For high-risk changes, require change-specific risk and rollback text. For breaking changes, require executable migration notes; never substitute generic “revert and redeploy” guidance.

### Gate G: Commit Hygiene and PR Title (Mandatory)

- Ensure commit set matches the scoped change only — no unrelated commits in the range.
- All commits should use **Conventional Commit** format: `<type>(<scope>): <subject>`.
  - Subject ≤ 50 characters, imperative mood, no trailing period.
  - Every body line must be ≤ 72 characters and explain **why** when a body is present.
  - Footer (when present): `BREAKING CHANGE:`, `Closes #`, `Refs:`.
- **PR title** must also follow Conventional Commits format. Under Squash-and-merge, GitHub pre-fills the PR title for a 2+-commit PR and the single commit's own subject for a 1-commit PR — so both are release-quality artifacts and both are validated.
- Validate the effective PR title, including a user-supplied `--title`; never validate only commit subjects.
- Warn when the branch does not match `<type>/<short-description>`.
- Do not amend existing commits unless user explicitly asks.
- If no commit exists, create one before PR creation.
- Perform a self-review of the full diff: run `git diff --check origin/main...HEAD`, inspect the changed-path list and full diff, and confirm every commit belongs to the scoped change. Pass `--confirm-self-review` only after that semantic review. Without this explicit confirmation, Gate G is `SUPPRESSED` and the PR remains draft.

### Gate H: Post-Create Verification (Mandatory)

After creation:

- Confirm PR points to `base=main` and `head=<feature branch>`.
- Confirm title/body rendered correctly.
- Confirm draft/ready state matches gate outcomes.
- Optionally check CI status with `gh pr checks` (non-blocking; reported as informational).
  CI results are logged but do not change the gate verdict — CI may still be running.

Use and assert every expected value:

- `gh pr view --json number,url,state,isDraft,baseRefName,headRefName,title,body`
- `gh pr checks <pr-number>` (optional, informational)

## Draft vs Ready Decision

Mark `ready` only when all mandatory gates pass or are suppressed with low residual risk.

Keep `draft` when:

- any mandatory gate failed,
- important evidence is missing,
- unresolved design/security/performance questions remain.

Do not publish at all when any gate has a hard publication blocker. A draft is not a safe destination for secrets, an invalid repository identity, `main` as the head, an unsafe/out-of-sync branch, an unavailable secret patch, or an invalid effective PR title.

## Required PR Body Structure

Use the template in `references/pr-body-template.md`.

Supply real content with `--problem`, `--approach`, `--risk`, `--rollback`, `--monitoring`, and (for breaking changes) `--migration-notes`. Missing mandatory narrative prevents ready state; generated text must expose the gap instead of inventing a generic rationale or rollback.

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
gh pr view --json number,url,state,isDraft,baseRefName,headRefName,title,body
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

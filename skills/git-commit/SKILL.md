---
name: git-commit
description: Safely create a git commit by validating repository state, staging intended changes, scanning for secrets/conflicts, generating an English Angular (Conventional Commits) message from staged diff, and committing without amend.
metadata:
  short-description: Safely commit staged changes with an Angular-style message
---

# Git Commit (Safety Enhanced, Angular Convention)

Create a commit from the current working tree with safety gates first, then generate a concise Angular-style message in English.

## Hard Rules

- Never commit with unresolved conflicts.
- Never commit secrets, credentials, keys, or `.env` sensitive values.
- **Subject line must be <= 50 characters total** (including `type(scope): `). This is the single most common violation — when a change touches multiple things, distill the subject to the core intent and move details into the body.
  - Too long: `feat(calc): add multiply and divide functions with tests` (56 chars)
  - Correct:  `feat(calc): add multiply and divide operations` (47 chars — move test details to body)
- Do not use `--amend` unless explicitly requested. Extra caution: if the commit has already been pushed, warn the user that amend requires force push.
- If any safety gate fails, stop and report clearly.
- One commit = one logical change. Do not mix unrelated fixes, features, or formatting in a single commit.

## Workflow

1. Preflight checks (all must pass before staging):
```bash
git rev-parse --is-inside-work-tree          # must be true
git status --short                            # observe working tree state
git diff --name-only --diff-filter=U          # must be empty (no unresolved conflicts)
git rev-parse --abbrev-ref HEAD               # must not be "HEAD" (detached)
test -d .git/rebase-merge -o -d .git/rebase-apply  # must fail (no rebase in progress)
test -f .git/MERGE_HEAD -o -f .git/CHERRY_PICK_HEAD -o -f .git/REVERT_HEAD  # must fail
```
- If any check fails, stop and tell the user what to resolve.

2. Staging:
- Stage intended files/hunks only (`git add <paths>` or `git add -p`). Use `git add .` only when the user explicitly intends it.
- Verify after staging: `git status --short` and `git diff --cached`.
- If nothing is staged, stop and report.

3. Secret/sensitive-content gate (must pass):
```bash
git diff --cached --name-only | rg -n '(^|/)(\\.env(\\..*)?|id_rsa|id_dsa|.*\\.pem|.*\\.p12|.*\\.key)$'
git diff --cached | rg -n '(AKIA[0-9A-Z]{16}|-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----|ghp_[A-Za-z0-9]{36}|xox[baprs]-|AIza[0-9A-Za-z\\-_]{35}|password\\s*=|secret\\s*=|token\\s*=)'
```
- If either matches, stop and ask user for explicit resolution before commit.

4. Quality gate (recommended, default on for Go repos):
- For Go repos, run **both** by default:
  - `go vet ./...` — catches common mistakes (unused variables, unreachable code, incorrect format strings)
  - `go test ./...` — or targeted tests for changed packages only
- For non-Go repos, run the project-standard check if discoverable (`make test`, `npm test`, etc.).
- If the user explicitly requests to skip, report it in final output as "quality gate: skipped by user".

5. Compose commit message (English, Angular style):
- Format: `<type>(<scope>): <subject>`, optionally followed by body and footer separated by blank lines.
- **Subject line**: imperative mood, **<= 50 chars total** (see Hard Rules), no trailing period. Focus on *what* changed at a glance.
- **Scope**: optional, lowercase. Check `git log --oneline -20` for the project's existing scope conventions; omit scope when multiple areas are touched.
- **Body** (recommended for non-trivial changes): explain **why** the change is needed — the diff already shows *what*. Wrap at **72 characters**.
- **Footer** (optional): `BREAKING CHANGE: <details>`, `Closes #<issue>`, `Refs: <URL or ticket>`.

6. Commit:
- Single-line commit:
  - `git commit -m "<message>"`
- With body/footer:
  - `git commit -m "<type>(<scope>): <summary>" -m "<body>" -m "<footer>"`
- **Hook awareness**: if the commit is rejected by a Git hook (e.g. `commit-msg` from commitlint, `pre-commit` from lint-staged/husky/lefthook):
  - Read the hook error output carefully.
  - If the hook enforces a stricter rule than this skill (e.g. different scope list, required ticket ID in footer), **adapt the message to satisfy the hook** rather than bypassing it.
  - Never use `--no-verify` unless the user explicitly requests it.
  - Report the hook name and the adjustment made.

7. Post-commit report:
- `git rev-parse --short HEAD`
- `git show --name-status --oneline --no-patch HEAD`
- Report:
  - commit hash
  - final subject
  - changed files summary
  - whether quality gate was run or skipped

## Message Quality Guidelines

- Subject must summarize staged diff only — do not reference unstaged or future work.
- **Subject answers "what changed"**; **body answers "why it changed"**. The diff already shows the code — the message should convey intent and motivation.
- Avoid vague summaries like `update code` or `fix bug`.
- Prefer concrete intent in the subject:
  - `fix(account): guard nil balance map before merge`
  - `refactor(service): simplify customer level aggregation flow`
  - `test(level): add killer case for tail-level mapping loss`

### Complete multi-line example

```
fix(auth): prevent token refresh race condition

Two concurrent requests could both trigger a refresh, causing one to
use an invalidated token. Add mutex to serialize refresh calls.

Closes #245
```

## Failure Handling

- No staged changes: stop and report.
- Safety gate failure: stop and report exact blocking check.
- Commit failure: report git error and leave staging untouched.

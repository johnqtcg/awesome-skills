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
- If the user specifies exact files, stage those only (`git add <paths>`).
- If the user gives a general instruction (e.g. "commit my changes", "commit this work"), apply this protocol:
  1. Run `git status --short` and classify all changes into **tracked-modified** (M/D) and **untracked** (??) files.
  2. **Tracked-modified files**: stage them all — these are clearly part of the user's in-progress work.
  3. **Untracked files**: evaluate each against the context of the current task:
     - Files that are clearly task-related (e.g. new source files the user just created, new test files): stage them.
     - Files that are ambiguous or unrelated (e.g. editor configs, build artifacts, unrelated scratch files): **list them to the user in a single confirmation prompt** — "I also found these untracked files: … Should I include them?"
     - Files that match `.gitignore` patterns will already be excluded by git; no action needed.
  4. If in doubt, prefer asking once with a complete list over asking file-by-file.
- Verify after staging: `git status --short` and `git diff --cached`.
- If nothing is staged, stop and report.

3. Secret/sensitive-content gate (must pass):

Detect the available search tool, then run both checks:
```bash
# Detect search tool: prefer rg (ripgrep), fall back to grep -En
if command -v rg >/dev/null 2>&1; then
  SEARCHER="rg -n"
else
  SEARCHER="grep -En"
fi

# File-name gate: known sensitive filenames
SENSITIVE_FILES='(^|/)(\\.env(\\..*)?|id_rsa|id_ed25519|id_dsa|.*\\.pem|.*\\.p12|.*\\.key|.*\\.keystore|credentials\\.json|service[-_]?account.*\\.json)$'
git diff --cached --name-only | $SEARCHER "$SENSITIVE_FILES"

# Content gate: token/secret patterns across major providers
SECRET_PATTERNS='(AKIA[0-9A-Z]{16}|-----BEGIN (RSA|EC|OPENSSH|DSA|PGP|PRIVATE) KEY-----|ghp_[A-Za-z0-9]{36}|gho_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{82}|xox[baprs]-[A-Za-z0-9\-]+|hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+|AIza[0-9A-Za-z\-_]{35}|sk_live_[0-9a-zA-Z]{24,}|rk_live_[0-9a-zA-Z]{24,}|sk-[A-Za-z0-9]{20,}|SG\.[A-Za-z0-9\-_]{22}\.[A-Za-z0-9\-_]{43}|mongodb(\+srv)?://[^\s]+@|postgres(ql)?://[^\s]*:[^\s]*@|mysql://[^\s]*:[^\s]*@|password\s*=|secret\s*=|token\s*=|api[_-]?key\s*=)'
git diff --cached | $SEARCHER "$SECRET_PATTERNS"
```
- If either matches, stop and ask user for explicit resolution before commit.
- Note: these patterns cover AWS, GitHub, Slack, Google, Stripe, OpenAI, SendGrid, and common DB connection strings. For project-specific tokens not covered here, add custom patterns to a `.secret-patterns` file or pre-commit hook.

4. Quality gate (recommended):

Auto-detect the project ecosystem from marker files in the repo root, then run the matching checks. If multiple markers exist (e.g. a monorepo with both `go.mod` and `package.json`), run the gate that matches the **staged files' language**.

**Go** (marker: `go.mod`):
- `go vet ./...`
- Tests — choose scope based on project size:
  - **Small repos / few packages**: `go test ./...`
  - **Large repos / mono-repos**: run tests only for packages touched by staged changes:
    ```bash
    # POSIX-compatible: works on macOS, Linux, and Git Bash on Windows
    CHANGED_PKGS=$(git diff --cached --name-only -- '*.go' | while read -r f; do dirname "$f"; done | sort -u | sed 's|^|./|')
    if [ -n "$CHANGED_PKGS" ]; then go test $CHANGED_PKGS; fi
    ```
    Note: this relies on POSIX shell utilities. On native Windows without Git Bash/WSL, use `go test ./path/to/pkg` manually.

**Node.js / TypeScript** (marker: `package.json`):
- Detect the package manager: `pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, otherwise npm.
- Lint (if available): check `package.json` for a `lint` script → `<pm> run lint`.
- Type check (if TypeScript): look for `tsconfig.json` → `<pm> run tsc --noEmit` or a `typecheck` script.
- Tests: check for a `test` script → `<pm> test`. If no test script exists, skip and note it.

**Python** (marker: `pyproject.toml` or `setup.py` or `setup.cfg`):
- Lint: prefer `ruff check .` if `ruff` is available; fall back to `flake8` if installed.
- Type check: run `mypy` or `pyright` if either is in dev dependencies or installed.
- Tests: `pytest` (preferred) or `python -m unittest discover`. If `pyproject.toml` has a `[tool.pytest]` or `[tool.tox]` section, follow that config.

**Java / Kotlin** (marker: `pom.xml` or `build.gradle` / `build.gradle.kts`):
- Maven: `mvn test -q`
- Gradle: `./gradlew test`

**Rust** (marker: `Cargo.toml`):
- `cargo clippy -- -D warnings`
- `cargo test`

**Fallback** (no recognized marker):
- Check for `Makefile` with a `test` or `check` target → `make test` / `make check`.
- If nothing is discoverable, skip the quality gate and note "no quality gate detected" in the post-commit report.

**Common rules for all ecosystems:**
- If the user has a `Makefile` target that wraps the ecosystem commands, prefer the Makefile target.
- If the user explicitly requests to skip, report it in final output as "quality gate: skipped by user".
- If a check fails, stop and report the errors — do not proceed to commit.

5. Compose commit message (English, Angular style):
- **Before writing the message**, run `git log --oneline -20` and extract the scopes and types actually used in this project. Use only scopes that already appear in the log (or omit scope if none fits). Do not invent new scopes.
- Format: `<type>(<scope>): <subject>`, optionally followed by body and footer separated by blank lines.
- **Subject line**: imperative mood, **<= 50 chars total** (see Hard Rules), no trailing period. Focus on *what* changed at a glance.
- **Scope**: optional, lowercase. Must come from the project's existing conventions discovered above; omit scope when multiple areas are touched or no existing scope fits.
- **Body** (recommended for non-trivial changes): explain **why** the change is needed — the diff already shows *what*. Wrap at **72 characters**.
- **Footer** (optional): `BREAKING CHANGE: <details>`, `Closes #<issue>`, `Refs: <URL or ticket>`.

6. Commit:
- Single-line commit:
  - `git commit -m "<message>"`
- With body/footer, use a heredoc to preserve formatting (lists, code blocks, multi-paragraph bodies):
  ```bash
  git commit -F - <<'EOF'
  <type>(<scope>): <subject>

  <body — wrap at 72 chars, may contain lists or code blocks>

  <footer>
  EOF
  ```
  Do **not** use multiple `-m` flags for multi-line messages — they cannot represent complex body content reliably.
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

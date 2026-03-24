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
- If the user gives a general instruction (e.g. "commit my changes", "commit this work"):
  1. Run `git status --short` and read the full list of modified (M), deleted (D), and untracked (??) files.
  2. **Group by logical change**: review the file list and the diffs (`git diff` for unstaged, `git diff --cached` for already-staged). Partition all changes into groups where each group represents one coherent logical change. Consider directory proximity, shared purpose (e.g. source + its test), and the nature of the diff.
  3. **Single logical change** — all changes clearly belong to one intent: stage them all (tracked and untracked task-related files alike).
  4. **Multiple logical changes detected** — present the groups to the user and ask which group to commit now:
     > "I see these changes form separate concerns:
     > - Group A (feat): `src/auth.go`, `src/auth_test.go` — new JWT support
     > - Group B (chore): `go.mod`, `go.sum` — dependency update
     > - Group C: `README.md` — doc fix
     > Which group should I commit? Or commit all together?"
  5. **Untracked files**: evaluate each against the current task context. Stage files clearly task-related (new source/test files created in this session). For ambiguous files (editor configs, scratch files, unrelated additions), include them in the group listing above so the user can decide.
  6. If in doubt, prefer asking once with a complete grouped list over guessing.
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
- **Triage matches before blocking** — not every match is a real secret. Apply these filters **in order** to each match; the first filter that hits decides the disposition:

  **Filter 1 — Project allowlist** (highest priority):
  If `.commit-secret-allowlist` exists in the repo root, read it (one glob per line, e.g. `**/testdata/**`, `docs/examples/**`). If the matched file path matches any glob, **auto-dismiss**.

  **Filter 2 — Test/fixture path**:
  Auto-dismiss if the file path from the diff header (`diff --git a/<path> b/<path>`) matches this pattern:
  ```
  /(test|tests|__tests__|spec|mock|mocks|fixture|fixtures|example|examples|testdata|snapshot|snapshots)/
  ```
  Also auto-dismiss if the filename itself ends with `_test.go`, `.test.ts`, `.test.js`, `.spec.ts`, `.spec.js`, `_test.py`, or `Test.java`.

  **Filter 3 — Documentation code block**:
  Auto-dismiss if **all** of the following are true:
  - The file extension is `.md`, `.rst`, `.adoc`, or `.mdx`.
  - The matched line in the diff falls between a code fence open (`` ``` `` or `.. code-block::`) and its corresponding close. To determine this: scan the diff hunk from its `@@` header downward, tracking fence open/close state; if the matched line is inside a fence, dismiss it.

  **Filter 4 — Comment line**:
  Auto-dismiss if the matched line (after stripping the diff `+` prefix and leading whitespace) starts with a language comment marker: `//`, `#`, `--`, `/*`, `*`, `"""`, `'''`, `%`, `;;`, `REM `.

  **Everything else → Review** (block and show context):
  For each surviving match, display: file path, line number, the matched line, and 2 lines of surrounding context from the diff. Ask the user to confirm or dismiss each.
- If any match survives triage, stop and ask the user for explicit resolution before commit.
- Note: these patterns cover AWS, GitHub, Slack, Google, Stripe, OpenAI, SendGrid, and common DB connection strings. For project-specific tokens not covered here, add custom patterns to a `.secret-patterns` file or pre-commit hook.

4. Quality gate (recommended):

Auto-detect the project ecosystem from marker files in the repo root, then run the matching checks.

**Ecosystem detection algorithm** (deterministic, in order):
1. Collect file extensions from staged files: `git diff --cached --name-only | sed 's/.*\.//' | sort | uniq -c | sort -rn`.
2. Map extensions to ecosystems: `.go` → Go, `.js`/`.ts`/`.jsx`/`.tsx` → Node.js/TS, `.py` → Python, `.java`/`.kt`/`.kts` → Java/Kotlin, `.rs` → Rust.
3. Pick the ecosystem with the **most staged files**. On a tie, prefer the ecosystem whose marker file is closest to the repo root.
4. If staged files span multiple ecosystems with no clear majority (e.g. 3 `.go` + 3 `.ts`), run the gate for **each** ecosystem that has staged files, scoped to its own files only.
5. If no staged file maps to a known ecosystem, fall through to the Fallback section below.

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
- Tests — choose scope based on project size:
  - **Small repos**: `<pm> test`
  - **Large repos / monorepos**: run only tests related to staged files. Most JS test runners support path-based filtering:
    ```bash
    # Collect directories of changed JS/TS files
    CHANGED_DIRS=$(git diff --cached --name-only -- '*.js' '*.ts' '*.jsx' '*.tsx' | while read -r f; do dirname "$f"; done | sort -u)
    # Jest: pass changed dirs as positional args (matches test files by path)
    <pm> test -- $CHANGED_DIRS
    # Vitest: same pattern
    <pm> exec vitest run $CHANGED_DIRS
    ```
    If the project uses a workspace monorepo (lerna, nx, turborepo), prefer the workspace-aware command: `npx nx affected --target=test`, `npx turbo run test --filter=...[HEAD~1]`, or `npx lerna run test --since=HEAD~1`.
  - If no test script exists in `package.json`, skip and note it.

**Python** (marker: `pyproject.toml` or `setup.py` or `setup.cfg`):
- Lint: prefer `ruff check .` if `ruff` is available; fall back to `flake8` if installed.
- Type check: run `mypy` or `pyright` if either is in dev dependencies or installed.
- Tests — choose scope based on project size:
  - **Small repos**: `pytest`
  - **Large repos**: run only tests related to staged files:
    ```bash
    # Collect changed .py file paths
    CHANGED_PY=$(git diff --cached --name-only -- '*.py')
    # pytest: pass changed files directly — it discovers matching test files
    pytest $CHANGED_PY
    # Or use pytest-testmon if installed (tracks which tests cover which source lines)
    pytest --testmon
    ```
  - If `pyproject.toml` has `[tool.pytest]` or `[tool.tox]` section, follow that config.

**Java / Kotlin** (marker: `pom.xml` or `build.gradle` / `build.gradle.kts`):
- Maven — choose scope:
  - **Full**: `mvn test -q`
  - **Scoped**: identify changed modules from staged file paths, then: `mvn test -pl <module1>,<module2> -q`
    ```bash
    # Extract Maven module names from staged paths (first directory component under repo root)
    CHANGED_MODULES=$(git diff --cached --name-only -- '*.java' '*.kt' '*.kts' | while read -r f; do echo "$f" | cut -d'/' -f1; done | sort -u | paste -sd,)
    if [ -n "$CHANGED_MODULES" ]; then mvn test -pl "$CHANGED_MODULES" -q; fi
    ```
- Gradle — choose scope:
  - **Full**: `./gradlew test`
  - **Scoped**: `./gradlew :<module>:test` for each changed module.

**Rust** (marker: `Cargo.toml`):
- `cargo clippy -- -D warnings`
- Tests — choose scope:
  - **Single-crate repos**: `cargo test`
  - **Workspace repos**: test only affected crates:
    ```bash
    # Extract crate directories from staged .rs files
    CHANGED_CRATES=$(git diff --cached --name-only -- '*.rs' | while read -r f; do
      d="$f"; while [ "$d" != "." ]; do d=$(dirname "$d"); [ -f "$d/Cargo.toml" ] && echo "$d" && break; done
    done | sort -u)
    for crate in $CHANGED_CRATES; do cargo test --manifest-path "$crate/Cargo.toml"; done
    ```

**Fallback** (no recognized marker):
- Check for `Makefile` with a `test` or `check` target → `make test` / `make check`.
- If nothing is discoverable, skip the quality gate and note "no quality gate detected" in the post-commit report.

**Common rules for all ecosystems:**
- If the user has a `Makefile` target that wraps the ecosystem commands, prefer the Makefile target.
- If the user explicitly requests to skip, report it in final output as "quality gate: skipped by user".
- If a check fails, stop and report the errors — do not proceed to commit.

5. Compose commit message (English, Angular style):

**Scope & type discovery** (run before writing the message):
```bash
# Extract type(scope) pairs from recent history
git log --oneline -30 | grep -oE '^[0-9a-f]+ [a-z]+\([a-z0-9_-]+\):' | sed 's/^[0-9a-f]* //' | sort | uniq -c | sort -rn
```
- Parse the output into a frequency-ranked list of `type(scope)` pairs.
- **Well-established conventions** (>= 3 distinct commits use the same scope): use these scopes as the canonical set. Pick the scope that best matches the staged files' directory or module.
- **Sparse or inconsistent history** (< 3 commits per scope, or no conventional commits at all): **omit scope entirely** — do not guess or invent. Use bare `<type>: <subject>` format.
- **Mixed history** (some scopes well-established, others one-off): only reuse scopes that appear >= 3 times; treat the rest as noise.

**Message format**: `<type>(<scope>): <subject>`, optionally followed by body and footer separated by blank lines.
- **Subject line**: imperative mood, **<= 50 chars total** (see Hard Rules), no trailing period. Focus on *what* changed at a glance.
- **Scope**: optional, lowercase. Must come from the canonical set discovered above; omit when multiple areas are touched, no established scope fits, or history is too sparse.
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

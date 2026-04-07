---
name: git-commit
description: Safely create a git commit by validating repository state, staging intended changes, scanning for secrets/conflicts, generating an English Angular (Conventional Commits) message from staged diff, and committing without amend.
disable-model-invocation: true
allowed-tools: Read, Grep, Bash(git add*), Bash(git commit*), Bash(git status*), Bash(git diff*), Bash(git log*), Bash(git stash*)
metadata:
  short-description: Safely commit staged changes with an Angular-style message
---

# Git Commit (Safety Enhanced, Angular Convention)

Create a commit from the current working tree with safety gates first, then generate a concise Angular-style message in English.

## Quick Reference

| If you need to… | Go to |
|---|---|
| Full commit workflow (preflight → stage → gate → message → commit) | §Workflow |
| Stage partial changes or split multiple logical groups | §2. Staging |
| Quality gate by ecosystem (Go / Node / Python / Java / Rust) | §3. Quality Gate |
| Handle edge cases (empty commit / submodule / squash residual) | §Edge Cases |

## Hard Rules

- Never commit with unresolved conflicts.
- Never commit secrets, credentials, keys, or `.env` sensitive values.
- **Subject line must be <= 50 characters total** (including `type(scope): `). This is the single most common violation — distill the subject to the core intent and move details into the body.
  - Too long: `feat(calc): add multiply and divide functions with tests` (56 chars)
  - Correct:  `feat(calc): add multiply and divide operations` (47 chars)
- Do not use `--amend` unless explicitly requested. If already pushed, warn about force push.
- If any safety gate fails, stop and report clearly.
- One commit = one logical change. Do not mix unrelated fixes, features, or formatting.

## Workflow

### 1. Preflight (all must pass)
```bash
git rev-parse --is-inside-work-tree          # must be true
git status --short                            # observe working tree state
git diff --name-only --diff-filter=U          # must be empty (no conflicts)
git rev-parse --abbrev-ref HEAD               # must not be "HEAD" (detached)
test -d .git/rebase-merge -o -d .git/rebase-apply  # must fail
test -f .git/MERGE_HEAD -o -f .git/CHERRY_PICK_HEAD -o -f .git/REVERT_HEAD  # must fail
```
If any check fails, stop and tell the user what to resolve.

### 2. Staging

**User specifies exact files**: stage those only (`git add <paths>`).

**User gives a general instruction** (e.g. "commit my changes"):
1. Run `git status --short`. Classify tracked and untracked files.
2. Count total changed paths (i.e. number of lines in `git status --short`). **If > 8 files, always list the full file set and ask the user to confirm** before any staging — do not auto-stage. This is a hard safety net regardless of how clear the intent seems.
3. If <= 8 files, read the diffs and partition all changes into groups by logical intent. Signals: directory proximity, shared purpose (source + its test), diff theme. If a single file contains changes for two logical intents, use `git add -p` to stage only the relevant hunks.
4. **Single logical change**: stage everything (tracked + task-related untracked).
5. **Multiple logical changes**: present groups and ask which to commit:
   > "These changes form separate concerns:
   > - Group A (feat): `src/auth.go`, `src/auth_test.go` — JWT support
   > - Group B (chore): `go.mod`, `go.sum` — dep update
   > Which group should I commit? Or all together?"
6. **Untracked files**: stage if clearly task-related; list ambiguous ones in the group prompt.

**Pre-quality-gate stash**: if there are unstaged changes after staging, stash them before running the quality gate so they don't interfere with test results:
```bash
git stash push --keep-index -m "pre-commit: unstaged changes"
# ... run quality gate (step 4) ...
git stash pop  # restore after quality gate, whether it passed or failed
```

Verify after staging: `git diff --cached --stat`. If nothing staged, stop and report.

**Submodule awareness**: run `git diff --cached --submodule=short` to check for submodule pointer changes. If present, confirm with the user that the submodule update is intentional — accidental submodule pointer commits are a common source of breakage.

### 3. Secret/sensitive-content gate (must pass)

```bash
if command -v rg >/dev/null 2>&1; then SEARCHER="rg -n"; else SEARCHER="grep -En"; fi

# File-name gate
SENSITIVE_FILES='(^|/)(\\.env(\\..*)?|id_rsa|id_ed25519|id_dsa|.*\\.pem|.*\\.p12|.*\\.key|.*\\.keystore|credentials\\.json|service[-_]?account.*\\.json)$'
git diff --cached --name-only | $SEARCHER "$SENSITIVE_FILES"

# Content gate (AWS, GitHub, Slack, Google, Stripe, OpenAI, SendGrid, DB URIs, generic)
SECRET_PATTERNS='(AKIA[0-9A-Z]{16}|-----BEGIN (RSA|EC|OPENSSH|DSA|PGP|PRIVATE) KEY-----|ghp_[A-Za-z0-9]{36}|gho_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{82}|xox[baprs]-[A-Za-z0-9\-]+|hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+|AIza[0-9A-Za-z\-_]{35}|sk_live_[0-9a-zA-Z]{24,}|rk_live_[0-9a-zA-Z]{24,}|sk-[A-Za-z0-9]{20,}|SG\.[A-Za-z0-9\-_]{22}\.[A-Za-z0-9\-_]{43}|mongodb(\+srv)?://[^\s]+@|postgres(ql)?://[^\s]*:[^\s]*@|mysql://[^\s]*:[^\s]*@|password\s*=|secret\s*=|token\s*=|api[_-]?key\s*=)'
git diff --cached | $SEARCHER "$SECRET_PATTERNS"
```

**Triage each match** — apply filters in order, first hit decides:

| # | Filter | Auto-dismiss when |
|---|--------|-------------------|
| 1 | **Project allowlist** | File path matches a glob in `.commit-secret-allowlist` (one glob per line) |
| 2 | **Test/fixture path** | Path contains `/test/`, `/tests/`, `/__tests__/`, `/spec/`, `/mock(s)/`, `/fixture(s)/`, `/example(s)/`, `/testdata/`, `/snapshot(s)/`; or filename ends with `_test.go`, `.test.{ts,js}`, `.spec.{ts,js}`, `_test.py`, `Test.java` |
| 3 | **Documentation file** | File extension is `.md`, `.rst`, `.adoc`, or `.mdx` |
| 4 | **Comment line** | After stripping diff `+` prefix + leading whitespace, line starts with: `//`, `#` (but not `#!/`), `--`, `/*`, `*`, `%`, `;;`, or `REM ` |

Surviving matches → **block**: show file, line number, matched line + 2 lines context. Ask user to confirm or dismiss.

For project-specific tokens, add patterns to `.secret-patterns` or a pre-commit hook.

### 4. Quality gate

**Ecosystem detection** (deterministic):
```bash
# Extract extensions from staged files (skip extensionless files)
git diff --cached --name-only | grep '\.' | sed 's/.*\.//' | sort | uniq -c | sort -rn
```
Map: `go` → Go, `js`/`ts`/`jsx`/`tsx` → Node, `py` → Python, `java`/`kt`/`kts` → Java, `rs` → Rust. Pick the ecosystem with the most staged files. On tie, prefer the ecosystem whose marker file is closest to repo root. If staged files span multiple ecosystems with no majority, run each gate scoped to its own files.

**Run the ecosystem-specific gate** from the matching reference file:

When staged files are predominantly Go (`.go`):
→ Load `references/quality-gate-go.md` for `go build`, `go vet`, `golangci-lint`, and `go test` commands with pass/fail thresholds.
When staged files are predominantly Node.js/TypeScript (`.js`/`.ts`/`.jsx`/`.tsx`):
→ Load `references/quality-gate-node.md` for `tsc --noEmit`, ESLint, and test runner commands with pass/fail thresholds.
When staged files are predominantly Python (`.py`):
→ Load `references/quality-gate-python.md` for `ruff`/`flake8`, `mypy`, and `pytest` commands with pass/fail thresholds.
When staged files are predominantly Java/Kotlin (`.java`/`.kt`/`.kts`):
→ Load `references/quality-gate-java.md` for build, checkstyle, and test commands with pass/fail thresholds.
When staged files are predominantly Rust (`.rs`):
→ Load `references/quality-gate-rust.md` for `cargo check`, `cargo clippy`, and `cargo test` commands with pass/fail thresholds.

**Fallback** (no marker found): try `make test` or `make check` if a Makefile exists; otherwise skip and note "no quality gate detected" in the report.

**Common rules**:
- Makefile target wrapping ecosystem commands takes precedence.
- User may explicitly skip → report "quality gate: skipped by user".
- If a check fails, stop and report — do not proceed to commit.
- **Timeout**: if a test command runs longer than 120 seconds with no output, interrupt it, report the timeout, and ask the user whether to skip the gate or retry with a narrower scope.

### 5. Compose commit message

**Scope discovery** (run before writing):
```bash
git log --oneline -30 | grep -oE '^[0-9a-f]+ [a-z]+\([a-z0-9_-]+\):' \
  | sed 's/^[0-9a-f]* //' | sort | uniq -c | sort -rn
```
- **>= 3 commits with the same scope**: canonical — use it if it matches the staged files.
- **< 3 per scope, or no conventional commits at all**: **omit scope entirely**. Use `<type>: <subject>`.
- Never invent a scope not in the canonical set.

**Format**: `<type>(<scope>): <subject>`, optional body + footer separated by blank lines.
- **Subject**: imperative mood, <= 50 chars, no trailing period.
- **Body** (recommended for non-trivial changes): explain **why**, wrap at 72 chars.
- **Footer** (optional): `BREAKING CHANGE: ...`, `Closes #...`, `Refs: ...`.

### 6. Commit

Single-line: `git commit -m "<message>"`

Multi-line (body/footer): use heredoc to preserve formatting:
```bash
git commit -F - <<'EOF'
<type>(<scope>): <subject>

<body — wrap at 72 chars, may contain lists or code blocks>

<footer>
EOF
```
Do **not** use multiple `-m` flags — they cannot handle complex body content.

**Hook awareness**: if rejected by a Git hook (commitlint, pre-commit, husky, lefthook):
- Read the error, adapt the message to satisfy the hook (e.g. stricter scope list, required ticket ID).
- Never use `--no-verify` unless explicitly requested.
- Report the hook name and the adjustment made.

### 7. Post-commit report
```bash
git rev-parse --short HEAD
git show --name-status --oneline --no-patch HEAD
```
Report: commit hash, final subject, changed files summary, quality gate status (ran / skipped / not detected).

## Message Examples

Good subjects:
- `fix(account): guard nil balance map before merge`
- `refactor(service): simplify aggregation flow`
- `test(level): add case for tail-mapping loss`

Complete multi-line:
```
fix(auth): prevent token refresh race condition

Two concurrent requests could both trigger a refresh, causing one to
use an invalidated token. Add mutex to serialize refresh calls.

Closes #245
```

## Edge Cases

- **Empty commit** (`--allow-empty`): only if the user explicitly requests it (e.g. to trigger CI). Never create an empty commit by default. When allowed, note it in the post-commit report.
- **Squash merge residual files**: if `.git/SQUASH_MSG` exists, the user is likely committing a squash merge. Warn them to review the staged files carefully.
- **Submodule pointer changes**: handled post-staging — always confirm with the user.

## Failure Handling

- No staged changes → stop and report.
- Safety gate failure → stop, report exact blocking check.
- Commit failure → report git error, leave staging untouched.
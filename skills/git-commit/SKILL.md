---
name: git-commit
description: Safely create a git commit by validating repository state, staging intended changes, scanning for secrets/conflicts, generating an English Angular (Conventional Commits) message from staged diff, and committing without amend.
disable-model-invocation: true
allowed-tools: Read, Grep, Bash(git add*), Bash(git commit*), Bash(git status*), Bash(git diff*), Bash(git log*), Bash(git stash*), Bash(git rev-parse*), Bash(git show*), Bash(go list*), Bash(go build*), Bash(go vet*), Bash(go test*), Bash(golangci-lint*), Bash(pytest*), Bash(ruff check*), Bash(flake8*), Bash(mypy*), Bash(pyright*), Bash(cargo check*), Bash(cargo clippy*), Bash(cargo test*), Bash(mvn test*), Bash(./gradlew*), Bash(npm*), Bash(yarn*), Bash(pnpm*), Bash(npx nx*), Bash(npx turbo*), Bash(npx lerna*), Bash(make test*), Bash(make check*)
metadata:
  short-description: Safely commit staged changes with an Angular-style message
---

# Git Commit (Safety Enhanced, Angular Convention)

Create a commit from the current working tree with safety gates first, then generate a concise Angular-style message in English.

## Hard Rules

- Never commit with unresolved conflicts.
- Never commit secrets, credentials, keys, or `.env` sensitive values.
- **Subject line must be <= 50 characters total** (including `type(scope): `).
- Do not use `--amend` unless explicitly requested. If already pushed, warn about force push.
- If any safety gate fails, stop and report clearly.
- One commit = one logical change. Do not mix unrelated fixes, features, or formatting.

## Workflow

### 1. Preflight
```bash
git rev-parse --is-inside-work-tree
git status --short
git diff --name-only --diff-filter=U
git rev-parse --abbrev-ref HEAD
test -d .git/rebase-merge -o -d .git/rebase-apply
test -f .git/MERGE_HEAD -o -f .git/CHERRY_PICK_HEAD -o -f .git/REVERT_HEAD
```
If any check fails, stop and tell the user what to resolve.

### 2. Staging

- If the user names exact files, stage those only with `git add <paths>`.
- If the user says "commit my changes", start from `git status --short`.
- Count changed paths. **If > 8 files, always list the full file set and ask for confirmation** before staging anything.
- If `<= 8` files, read the diffs and split by logical intent. If one file mixes intents, use `git add -p`.
- Stage task-related untracked files only when they clearly belong to the same change.
- If unstaged changes remain after staging, run:
```bash
git stash push --keep-index -m "pre-commit: unstaged changes"
# ... run quality gate ...
git stash pop
```
- Verify staging with `git diff --cached --stat`. If nothing is staged, stop.
- Run `git diff --cached --submodule=short`. If a submodule pointer changed, confirm it is intentional.

### 3. Secret/sensitive-content gate

```bash
if command -v rg >/dev/null 2>&1; then SEARCHER="rg -n"; else SEARCHER="grep -En"; fi
SENSITIVE_FILES='(^|/)(\.env(\..*)?|id_rsa|id_ed25519|id_dsa|.*\.pem|.*\.p12|.*\.key|.*\.keystore|credentials\.json|service[-_]?account.*\.json)$'
SECRET_PATTERNS='(AKIA[0-9A-Z]{16}|-----BEGIN (RSA|EC|OPENSSH|DSA|PGP|PRIVATE) KEY-----|ghp_[A-Za-z0-9]{36}|gho_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{82}|xox[baprs]-[A-Za-z0-9\-]+|hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+|AIza[0-9A-Za-z\-_]{35}|sk_live_[0-9a-zA-Z]{24,}|rk_live_[0-9a-zA-Z]{24,}|sk-[A-Za-z0-9]{20,}|SG\.[A-Za-z0-9\-_]{22}\.[A-Za-z0-9\-_]{43}|mongodb(\+srv)?://[^\s]+@|postgres(ql)?://[^\s]*:[^\s]*@|mysql://[^\s]*:[^\s]*@|password\s*=|secret\s*=|token\s*=|api[_-]?key\s*=)'
git diff --cached --name-only | $SEARCHER "$SENSITIVE_FILES"
git diff --cached | $SEARCHER "$SECRET_PATTERNS"
```

Triage every match in order:

| # | Filter | Auto-dismiss when |
|---|---|---|
| 1 | Allowlist | Path matches a glob in `.commit-secret-allowlist` |
| 2 | Test/fixture path | Path contains `/test/`, `/tests/`, `/__tests__/`, `/spec/`, `/mock(s)/`, `/fixture(s)/`, `/example(s)/`, `/testdata/`, `/snapshot(s)/`, or ends with a common test suffix |
| 3 | Documentation file | Extension is `.md`, `.rst`, `.adoc`, or `.mdx` |
| 4 | Comment line | After stripping `+` and whitespace, line starts with `//`, `#` (not `#!/`), `--`, `/*`, `*`, `%`, `;;`, or `REM ` |

Surviving matches are blockers: report file, line number, matched line, and 2 lines of context.

### 4. Quality gate

Detect ecosystem from staged extensions:
```bash
git diff --cached --name-only | grep '\.' | sed 's/.*\.//' | sort | uniq -c | sort -rn
```

- `go` → load `references/quality-gate-go.md`
- `js`/`ts`/`jsx`/`tsx` → load `references/quality-gate-node.md`
- `py` → load `references/quality-gate-python.md`
- `java`/`kt`/`kts` → load `references/quality-gate-java.md`
- `rs` → load `references/quality-gate-rust.md`
- On ties, prefer the ecosystem whose marker file is closest to repo root. If no majority, run each gate on its own files.
- If no marker matches, try `make test` or `make check`; otherwise report `quality gate: not detected`.
- Makefile wrappers take precedence over raw ecosystem commands.
- If a check fails, stop and report it.
- The user may explicitly skip; report `quality gate: skipped by user`.
- **Timeout**: default is **120 seconds** with no output. If the repo wrapper or environment exposes `COMMIT_TEST_TIMEOUT`, `QUALITY_GATE_TIMEOUT_SECONDS`, or `SKILL_QUALITY_GATE_TIMEOUT_SECONDS`, use that override and report the chosen timeout before running long tests.

### 5. Compose commit message

Scope discovery:
```bash
git log --oneline -50 | grep -oE '^[0-9a-f]+ [a-z]+(\([a-z0-9_-]+\))?:' | sed 's/^[0-9a-f]* //' | sort | uniq -c | sort -rn
```

- **>= 3 commits with the same scope**: canonical; use it only if the scope matches staged paths.
- If the repo has **fewer than 10 conventional commits total**, bootstrap scope from staged paths: strip generic directories such as `src`, `lib`, `pkg`, `cmd`, `internal`, `app`, `apps`, `service`, `services`, `module`, `modules`, `package`, `packages`, `component`, `components`, `test`, `tests`, and `testdata`; if one stable directory remains across all staged files, use that directory name.
- If multiple candidate directories remain, staged files span mixed roots, or the repo already has `>= 10` conventional commits without a canonical match, omit scope.
- Never invent a scope from filenames, issue text, or mixed roots.
- Format is `<type>(<scope>): <subject>` or `<type>: <subject>`.
- Subject must be imperative, no trailing period, and <= 50 chars; body explains **why** and wraps at 72 chars.

### 6. Commit

Single-line commit:
```bash
SUBJECT='<type>(<scope>): <subject>'
[ ${#SUBJECT} -le 50 ] || { echo "subject too long (${#SUBJECT}/50)"; exit 1; }
case "$SUBJECT" in *.) echo "subject must not end with ."; exit 1 ;; esac
git commit -m "$SUBJECT"
```

Multi-line commit:
```bash
SUBJECT='<type>(<scope>): <subject>'
[ ${#SUBJECT} -le 50 ] || { echo "subject too long (${#SUBJECT}/50)"; exit 1; }
case "$SUBJECT" in *.) echo "subject must not end with ."; exit 1 ;; esac
git commit -F - <<'EOF'
<type>(<scope>): <subject>

<body — explain why, wrap at 72 chars>

<footer>
EOF
```
Do **not** use multiple `-m` flags — they cannot handle complex body content.

Hook awareness:

- If commitlint, pre-commit, husky, or lefthook rejects the commit, read the error and adapt the message.
- Never use `--no-verify` unless explicitly requested.
- Report the hook name and the adjustment made.

### 7. Post-commit report
```bash
git rev-parse --short HEAD
git show --name-status --oneline --no-patch HEAD
```
Report the hash, final subject, changed files summary, and quality gate status.

## Message Examples

- `fix(account): guard nil balance map before merge`
- `refactor(service): simplify aggregation flow`
- `test: add case for tail-mapping loss`

```text
fix(auth): prevent token refresh race condition

Two concurrent requests could both trigger a refresh, causing one to
use an invalidated token. Add mutex to serialize refresh calls.

Closes #245
```

## Edge Cases

- `--allow-empty`: only if the user explicitly requests it. Note it in the post-commit report.
- If `.git/SQUASH_MSG` exists, warn that this may be a squash-merge residual state.
- Submodule pointer changes are never auto-assumed safe.

## Failure Handling

- No staged changes → stop and report.
- Safety gate failure → stop and report the exact blocker.
- Commit failure → report the git error and leave staging untouched.

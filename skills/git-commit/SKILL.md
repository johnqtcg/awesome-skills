---
name: git-commit
description: Safely create a git commit by validating repository state, staging intended changes, scanning for secrets/conflicts, generating an English Angular (Conventional Commits) message from staged diff, and committing without amend.
disable-model-invocation: true
allowed-tools: Read, Grep, Bash(git add*), Bash(git commit*), Bash(git status*), Bash(git diff*), Bash(git log*), Bash(git stash*), Bash(git rev-parse*), Bash(git show*), Bash(go list*), Bash(go build*), Bash(go vet*), Bash(go test*), Bash(golangci-lint*), Bash(pytest*), Bash(ruff check*), Bash(flake8*), Bash(mypy*), Bash(pyright*), Bash(cargo check*), Bash(cargo clippy*), Bash(cargo test*), Bash(mvn test*), Bash(./gradlew*), Bash(npm*), Bash(yarn*), Bash(pnpm*), Bash(npx nx*), Bash(npx turbo*), Bash(npx lerna*), Bash(make test*), Bash(make check*), Bash(gitleaks*)
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
git rev-parse --is-inside-work-tree                 # must print "true"
git status --short
BRANCH=$(git rev-parse --abbrev-ref HEAD)            # "HEAD" means detached (allowed)

# In-progress operation? Worktree-safe: resolve real paths, never read .git/ directly.
for state in rebase-merge rebase-apply MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD; do
  [ -e "$(git rev-parse --git-path "$state")" ] && echo "IN_PROGRESS $state"
done

# Unresolved conflicts: this diff exits 0 regardless, so act on OUTPUT, not exit code.
git diff --name-only --diff-filter=U
```
STOP (hard block — report which one and what to resolve) if any of these hold:
- `--is-inside-work-tree` did not print `true`;
- any `IN_PROGRESS <state>` line printed (rebase / merge / cherry-pick / revert in progress);
- the conflict diff printed any path (unresolved merge conflicts).

A detached `HEAD` is not a stop condition — proceed and note it in the report.

### 2. Staging

- If the user names exact files, stage those only with `git add <paths>`.
- If the user says "commit my changes", start from `git status --short`.
- Count changed paths. **If > 8 files, always list the full file set and ask for confirmation** before staging anything.
- If `<= 8` files, read the diffs and split by logical intent. If one file mixes intents, use `git add -p`.
- Stage task-related untracked files only when they clearly belong to the same change.
- If unstaged or untracked changes remain after staging, isolate them transactionally so the quality gate sees exactly the staged snapshot:
```bash
git stash push --keep-index --include-untracked -m "pre-commit gate $$"
STASH=$(git rev-parse -q --verify stash@{0})    # exact OID we pushed (must be non-empty)
# ... run quality gate against the staged-only tree ...
# Restore onto a clean HEAD (avoids the --keep-index + pop double-apply conflict); the reset
# is safe because the set is in the stash, and the OID check keeps us to OUR stash.
if [ -n "$STASH" ] && [ "$(git rev-parse -q --verify stash@{0})" = "$STASH" ]; then
  git reset -q --hard
  git stash pop --index -q
fi
```
If `stash pop` reports a conflict, or the OID check failed (another stash landed on top), STOP: the full change set is safe in stash `$STASH` — report the OID and let the user finish (`git stash apply --index $STASH`) after resolving. Never leave a half-restored tree.
- Verify staging with `git diff --cached --stat`. If nothing is staged, stop.
- Run `git diff --cached --submodule=short`. If a submodule pointer changed, confirm it is intentional.

### 3. Secret/sensitive-content gate

```bash
# Prefer the repo's own scanner if configured — it handles entropy, binaries, baselines.
if [ -f .gitleaks.toml ] || command -v gitleaks >/dev/null 2>&1; then
  gitleaks protect --staged --redact --no-banner || echo "REVIEW: gitleaks findings above"
fi

# Built-in fallback. Scan ADDED lines only — never block a commit that REMOVES a secret.
if command -v rg >/dev/null 2>&1; then SEARCHER="rg -n"; else SEARCHER="grep -En"; fi
SENSITIVE_FILES='(^|/)(\.env(\..*)?|id_rsa|id_ed25519|id_dsa|.*\.pem|.*\.p12|.*\.key|.*\.keystore|credentials\.json|service[-_]?account.*\.json)$'
SECRET_PATTERNS='(AKIA[0-9A-Z]{16}|-----BEGIN (RSA|EC|OPENSSH|DSA|PGP|PRIVATE) KEY-----|ghp_[A-Za-z0-9]{36}|gho_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{82}|xox[baprs]-[A-Za-z0-9\-]+|hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+|AIza[0-9A-Za-z\-_]{35}|sk_live_[0-9a-zA-Z]{24,}|rk_live_[0-9a-zA-Z]{24,}|sk-[A-Za-z0-9_-]{20,}|SG\.[A-Za-z0-9\-_]{22}\.[A-Za-z0-9\-_]{43}|mongodb(\+srv)?://[^\s]+@|postgres(ql)?://[^\s]*:[^\s]*@|mysql://[^\s]*:[^\s]*@|password\s*=|secret\s*=|token\s*=|api[_-]?key\s*=)'
git diff --cached --name-only --diff-filter=d | $SEARCHER "$SENSITIVE_FILES"
git diff --cached --diff-filter=d -U0 | grep -E '^\+[^+]' | $SEARCHER "$SECRET_PATTERNS"
```

Triage every match. **Path/type never auto-dismisses a match — real keys do get committed into tests and docs. Only a committed allowlist hard-dismisses; everything else lowers confidence and is still surfaced.**

| # | Filter | Effect |
|---|---|---|
| 1 | Allowlist glob in a committed `.commit-secret-allowlist` | Hard-dismiss — but confirm the entry's scope/provenance; treat an unfamiliar allowlist as untrusted |
| 2 | Test/fixture path (`/test(s)/`, `/__tests__/`, `/spec/`, `/mock(s)/`, `/fixture(s)/`, `/example(s)/`, `/testdata/`, `/snapshot(s)/`, or a common test suffix) | Downgrade to low confidence — still report |
| 3 | Documentation file (`.md`, `.rst`, `.adoc`, `.mdx`) | Downgrade — still report |
| 4 | Comment line (after stripping `+`/whitespace: `//`, `#` not `#!/`, `--`, `/*`, `*`, `%`, `;;`, `REM `) | Downgrade — still report |

High-confidence matches are blockers; downgraded matches need a human decision (never silently dropped). Report file:line, the matched line (redacted), and 2 lines of context. Binary files and high-entropy strings are out of scope for the regex fallback — rely on `gitleaks`/`detect-secrets` for those.

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

**First discover the repo's own convention — it overrides the defaults below:**
- commitlint config (`.commitlintrc*`, `commitlint.config.*`, or a `commitlint` key in `package.json`) → follow its `type-enum`, case, and length rules.
- `.gitmessage` template (`git config commit.template`), or commit rules in `CONTRIBUTING`/`AGENTS.md` → follow them.
- If a convention is found, adopt its type set, language, and subject length in place of the Angular / English / 50-char defaults. If none is found, use the defaults.

Scope discovery:
```bash
git log --oneline -50 | grep -oE '^[0-9a-f]+ [a-z]+(\([a-z0-9_-]+\))?:' | sed 's/^[0-9a-f]* //' | sort | uniq -c | sort -rn
```

- **>= 3 commits with the same scope**: canonical; use it only if the scope matches staged paths.
- If the repo has **fewer than 10 conventional commits total**, bootstrap scope from staged paths: strip generic directories such as `src`, `lib`, `pkg`, `cmd`, `internal`, `app`, `apps`, `service`, `services`, `module`, `modules`, `package`, `packages`, `component`, `components`, `test`, `tests`, and `testdata`; if one stable directory remains across all staged files, use that directory name.
- If multiple candidate directories remain, staged files span mixed roots, or the repo already has `>= 10` conventional commits without a canonical match, omit scope.
- Never invent a scope from filenames, issue text, or mixed roots.
- Format is `<type>(<scope>): <subject>` or `<type>: <subject>`; for a breaking change use `<type>!:` and/or a `BREAKING CHANGE: <what>` footer.
- Subject must be imperative, no trailing period, and <= 50 chars (or the repo's discovered limit); body explains **why** and wraps at 72 chars.
- Add required trailers when repo policy or the user asks: `Signed-off-by:` (`git commit -s`), `Co-authored-by:`, and issue refs (`Closes #123`).

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
Prefer `git commit -F -` for any multi-paragraph body. Multiple `-m` flags *do* work — each becomes its own paragraph — but give no control over 72-char wrapping within a paragraph and are quoting-fragile for footers, so `-F -` is the reliable choice.

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

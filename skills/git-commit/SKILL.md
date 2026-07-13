---
name: git-commit
description: Safely create a git commit by validating repository state, staging intended changes, scanning for secrets/conflicts, generating a Conventional Commits message (repository convention first, else an English Angular default) from the staged diff, and committing without amend.
disable-model-invocation: true
allowed-tools: Read, Grep, Bash(git add*), Bash(git commit*), Bash(git status*), Bash(git diff*), Bash(git log*), Bash(git stash*), Bash(git rev-parse*), Bash(git show*), Bash(go list*), Bash(go build*), Bash(go vet*), Bash(go test*), Bash(golangci-lint*), Bash(pytest*), Bash(ruff check*), Bash(flake8*), Bash(mypy*), Bash(pyright*), Bash(cargo check*), Bash(cargo clippy*), Bash(cargo test*), Bash(mvn test*), Bash(./gradlew*), Bash(npm*), Bash(yarn*), Bash(pnpm*), Bash(npx nx*), Bash(npx turbo*), Bash(npx lerna*), Bash(make test*), Bash(make check*), Bash(gitleaks*), Bash(bash scripts/stash-guard.sh*), Bash(bash scripts/secret-scan.sh*)
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

- **Snapshot what is already staged first**: `git diff --cached --name-only`. If files are already staged that the user did not ask to commit, STOP and ask — commit them together, keep them staged for later, or split. Never silently fold pre-staged files into this commit.
- If the user names exact files, stage those only with `git add <paths>`.
- If the user says "commit my changes", start from `git status --short`.
- Count changed paths. **If > 8 files, always list the full file set and ask for confirmation** before staging anything.
- If `<= 8` files, read the diffs and split by logical intent. If one file mixes intents, use `git add -p`.
- Stage task-related untracked files only when they clearly belong to the same change.
- If unstaged or untracked changes remain after staging, the quality gate MUST run through the isolation wrapper (§4) so it sees exactly the staged snapshot and your changes are restored on **every** exit path.
- Verify staging with `git diff --cached --stat`. If nothing is staged, stop.
- Run `git diff --cached --submodule=short`. If a submodule pointer changed, confirm it is intentional.

### 3. Secret/sensitive-content gate

Run the scanner — it prints `SENSITIVE_FILE:` / `SECRET_CANDIDATE:` lines (empty output = clean) and always exits 0, so "no secret" is never misread as a gate failure:
```bash
bash scripts/secret-scan.sh
```
It prefers the repo's `gitleaks` when the binary is installed (via the current `gitleaks git --pre-commit --staged` form) and always runs a built-in regex fallback over **added** staged lines only — removing a secret is never blocked.

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
- **Isolation (guaranteed restore)**: when unstaged or untracked changes are present, run the detected gate through the wrapper so those changes are stashed and restored on **every** exit path — gate pass, gate failure, or interrupt:
  ```bash
  bash scripts/stash-guard.sh <gate command>   # e.g. bash scripts/stash-guard.sh make ci
  ```
  Its exit code is the gate's. On a restore conflict or stash-OID mismatch it aborts loudly and preserves the exact stash (`git stash apply --index <OID>`) — never a half-restored tree.

### 5. Compose commit message

**First discover the repo's own convention — it overrides the defaults below:**
- commitlint config (`.commitlintrc*`, `commitlint.config.*`, or a `commitlint` key in `package.json`) → follow its `type-enum`, case, and length rules.
- `.gitmessage` template (`git config commit.template`), or commit rules in `CONTRIBUTING`/`AGENTS.md` → follow them.
- If a convention is found, adopt its type set, language, and subject length in place of the Angular / English / 50-char defaults. If none is found, use the defaults.
- Carry the discovered subject-length limit into the §6 guard as `SUBJECT_MAX` (default 50) so the executable check enforces the repo's actual limit, not a hardcoded 50.

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
SUBJECT_MAX=${SUBJECT_MAX:-50}   # 50 default; set from the repo convention (§5)
[ ${#SUBJECT} -le "$SUBJECT_MAX" ] || { echo "subject too long (${#SUBJECT}/$SUBJECT_MAX)"; exit 1; }
case "$SUBJECT" in *.) echo "subject must not end with ."; exit 1 ;; esac
git commit -m "$SUBJECT"
```

Multi-line commit:
```bash
SUBJECT='<type>(<scope>): <subject>'
SUBJECT_MAX=${SUBJECT_MAX:-50}   # 50 default; set from the repo convention (§5)
[ ${#SUBJECT} -le "$SUBJECT_MAX" ] || { echo "subject too long (${#SUBJECT}/$SUBJECT_MAX)"; exit 1; }
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
git show -s --format='%h %s' HEAD          # hash + subject
git show --name-status --format= HEAD      # changed files (NOT --no-patch: it disables --name-status)
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

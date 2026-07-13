---
name: git-commit
description: Safely create a git commit by validating repository state, staging intended changes, scanning for secrets/conflicts, generating a Conventional Commits message (repository convention first, else an English Angular default) from the staged diff, and committing without amend.
disable-model-invocation: true
allowed-tools: Read, Grep, Bash(git add*), Bash(git commit*), Bash(git status*), Bash(git diff*), Bash(git log*), Bash(git stash*), Bash(git rev-parse*), Bash(git show*), Bash(go list*), Bash(go build*), Bash(go vet*), Bash(go test*), Bash(golangci-lint*), Bash(pytest*), Bash(ruff check*), Bash(flake8*), Bash(mypy*), Bash(pyright*), Bash(cargo check*), Bash(cargo clippy*), Bash(cargo test*), Bash(mvn test*), Bash(./gradlew*), Bash(npm*), Bash(yarn*), Bash(pnpm*), Bash(bun*), Bash(deno*), Bash(npx nx*), Bash(npx turbo*), Bash(npx lerna*), Bash(make test*), Bash(make check*), Bash(make*), Bash(git config --get*), Bash(gitleaks*), Bash(bash *secret-scan.sh*), Bash(bash *stash-guard.sh*), Bash(bash *run-gate.sh*), Bash(bash *detect-ecosystems.sh*)
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

Bundled scripts are always invoked as `bash "<path-to-skill>/scripts/<name>.sh"` — `<path-to-skill>` is the absolute skill directory (where this SKILL.md was loaded from), never a path relative to the repository. Keep the working directory at the **target repo root**; the scripts read the repo through git.

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
- If the user names exact files, stage those only with `git add -- <paths>` (the `--` keeps a path that starts with `-` from being parsed as an option).
- If the user says "commit my changes", start from `git status --short`.
- Count changed paths. **If > 8 files, always list the full file set and ask for confirmation** before staging anything.
- If `<= 8` files, read the diffs and split by logical intent. If one file mixes intents, use `git add -p`.
- Stage task-related untracked files only when they clearly belong to the same change.
- If unstaged or untracked changes remain after staging, the quality gate MUST run through the isolation wrapper (§4) so it sees exactly the staged snapshot and your changes are restored on **every** exit path.
- Verify staging with `git diff --cached --stat`. If nothing is staged, stop.
- Run `git diff --cached --submodule=short`. If a submodule pointer changed, confirm it is intentional.

### 3. Secret/sensitive-content gate

```bash
bash "<path-to-skill>/scripts/secret-scan.sh"
```
It prefers the repo's `gitleaks` when the binary is installed (current `gitleaks git --pre-commit --staged` form, pinned to `--exit-code 10` because the default exit 1 is ambiguous between findings and execution errors) and always runs a built-in regex fallback over **added** staged lines only — removing a secret is never blocked. Exit code: **0 = scan completed** (clean, or findings printed for triage — "no secret" is never misread as a gate failure); **2 = the scanner itself failed** (fail-closed: treat as a gate failure, never as clean). Output lines:

- `SECRET_CANDIDATE: <file>:<line>: <redacted>` — real source line numbers; the secret value is never printed, only the first 4 matched chars survive redaction.
- `CONTEXT: <file>:<line>: <text>` — 2 lines around each candidate (long token-ish runs masked too).
- `ALLOWLISTED: …` — matched a glob in the **committed** `.commit-secret-allowlist` (`HEAD` version; a staged-but-uncommitted allowlist is ignored).
- `SENSITIVE_FILE: <path>` — staged filename that is key material by name (`.env`, `id_rsa`, `*.pem`, …).
- `SCANNER_ERROR: …` — gitleaks misconfiguration or crash (script exits 2); the regex fallback still ran but is NOT equivalent coverage — fix the scanner or get explicit user sign-off.

Triage every match. **Path/type never auto-dismisses a match — real keys do get committed into tests and docs. Only a committed allowlist hard-dismisses; everything else lowers confidence and is still surfaced.**

| # | Filter | Effect |
|---|---|---|
| 1 | `ALLOWLISTED:` line (committed `.commit-secret-allowlist` glob) | Hard-dismiss — but confirm the entry's scope/provenance; treat an unfamiliar allowlist as untrusted |
| 2 | Test/fixture path (`/test(s)/`, `/__tests__/`, `/spec/`, `/mock(s)/`, `/fixture(s)/`, `/example(s)/`, `/testdata/`, `/snapshot(s)/`, or a common test suffix) | Downgrade to low confidence — still report |
| 3 | Documentation file (`.md`, `.rst`, `.adoc`, `.mdx`) | Downgrade — still report |
| 4 | Comment line (after stripping `+`/whitespace: `//`, `#` not `#!/`, `--`, `/*`, `*`, `%`, `;;`, `REM `) | Downgrade — still report |

High-confidence matches are blockers; downgraded matches need a human decision (never silently dropped). Binary files and high-entropy strings are out of scope for the regex fallback — rely on `gitleaks`/`detect-secrets` for those.

### 4. Quality gate

Detect ecosystems — extensions **and** dependency-manifest markers, so staging only `go.mod` or `package.json` still selects the right gate:
```bash
bash "<path-to-skill>/scripts/detect-ecosystems.sh"   # one per line, most staged files first
```

- `go` → load `references/quality-gate-go.md`; `node` → `references/quality-gate-node.md`; `python` → `references/quality-gate-python.md`; `java` → `references/quality-gate-java.md`; `rust` → `references/quality-gate-rust.md`
- **Run the gate for EVERY detected ecosystem**, largest first — a 5-Go-file + 1-TS-file stage runs both the Go and the Node gates (scope each gate to its own files where the reference allows). Never skip a minority ecosystem.
- The marker list is not exhaustive. Detector prints nothing but the stage clearly belongs to an ecosystem (an unlisted marker such as an uncommon lockfile) → pick that gate by judgment and say so in the report; otherwise try `make test` / `make check`, else report `quality gate: not detected`.
- Makefile wrappers take precedence over raw ecosystem commands.
- If a check fails, stop and report it. The user may explicitly skip; report `quality gate: skipped by user`.
- **Timeout (enforced, not advisory)**: default **120 seconds** per gate command (each `run-gate.sh` invocation bounds one command). If the repo wrapper or environment exposes `COMMIT_TEST_TIMEOUT`, `QUALITY_GATE_TIMEOUT_SECONDS`, or `SKILL_QUALITY_GATE_TIMEOUT_SECONDS`, use that override and report the chosen timeout before running long tests. Run every gate command through the enforcer — exit `124` means the gate timed out with its whole process tree killed (report it; do not commit). A zero timeout and a host with no timeout tooling are both rejected (exit 2) — never unbounded:
  ```bash
  bash "<path-to-skill>/scripts/run-gate.sh" [-t <repo-wrapper-seconds>] <gate command>
  ```
- **Isolation (guaranteed restore)**: when unstaged or untracked changes are present, wrap the enforcer in the stash guard so those changes are stashed and restored exactly once on **every** exit path — gate pass, gate failure, timeout, or interrupt (SIGINT/SIGTERM exit 130/143 after restore, never 0):
  ```bash
  bash "<path-to-skill>/scripts/stash-guard.sh" bash "<path-to-skill>/scripts/run-gate.sh" make test
  ```
  Its exit code is the gate's. On a restore conflict or stash-OID mismatch it aborts non-zero and preserves the exact stash (`git stash apply --index <OID>`) — the data is never lost, but the worktree may hold a **partial** restore: follow the printed recovery instructions, never assume a clean tree. It also fails closed on both isolation edges: unstashable state (dirty submodule content) → exit 2 **without running the gate**; tracked-file/index drift while the gate ran (concurrent edits, formatter side-effects) → keeps the stash and refuses the destructive reset.

### 5. Compose commit message

**First discover the repo's own convention — it overrides the defaults below:**
- commitlint config (`.commitlintrc*`, `commitlint.config.*`, or a `commitlint` key in `package.json`) → follow its `type-enum`, case, and length rules.
- `.gitmessage` template (`git config --get commit.template`), or commit rules in `CONTRIBUTING`/`AGENTS.md` → follow them.
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

Multi-line commit — the heredoc is the **single source**; the guard checks the exact first line that will be committed (no separate SUBJECT variable to drift):
```bash
SUBJECT_MAX=${SUBJECT_MAX:-50}   # 50 default; set from the repo convention (§5)
MSG=$(cat <<'EOF'
<type>(<scope>): <subject>

<body — explain why, wrap at 72 chars>

<footer>
EOF
)
SUBJECT=${MSG%%$'\n'*}
[ ${#SUBJECT} -le "$SUBJECT_MAX" ] || { echo "subject too long (${#SUBJECT}/$SUBJECT_MAX)"; exit 1; }
case "$SUBJECT" in *.) echo "subject must not end with ."; exit 1 ;; esac
printf '%s\n' "$MSG" | git commit -F -
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
- If the file at `git rev-parse --git-path SQUASH_MSG` exists (worktree-safe — never read `.git/` directly), warn that this may be a squash-merge residual state.
- Submodule pointer changes are never auto-assumed safe.

## Failure Handling

- No staged changes → stop and report.
- Safety gate failure → stop and report the exact blocker.
- Commit failure → report the git error and leave staging untouched.

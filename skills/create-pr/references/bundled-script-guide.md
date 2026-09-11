# Bundled Script — create_pr.py

Use `scripts/create_pr.py` for one-click gate execution, PR body generation, and PR create-or-update.

## Behavior

- If the current branch already has an open PR to `main`, the script updates title/body instead of creating a duplicate PR.
- Draft/ready state is reconciled from gate results: `confirmed` is ready; `likely` is ready only when every suppression has low residual risk; any ready-blocking gap stays draft.
- Hard publication blockers are checked before `git push`. Repository/auth mismatch, unsafe branch state, incomplete secret-scan evidence, high-confidence secret findings, and invalid PR titles create no remote side effect.
- Gate A validates the fetch URL, **every** push URL (`git remote get-url --push --all origin` — one push writes to all of them) and `gh repo view` as a single identity; any mismatch or unparseable URL blocks publication.
- Gate D grades test / lint / build separately. A dimension with no executed command becomes an uncovered risk and keeps the PR in draft; declare it with `quality.<dimension>_cmd`, `--test-cmd` / `--lint-cmd` / `--build-cmd`, or `--quality-na <dimension>`.
- Dimension credit is derived from a command's argv, not its text. Only simple known commands (optionally prefixed `cd <dir> &&`) and named task-runner targets are classified; wrappers and shell expressions stay unclassified and need an explicit declaration.
- A recognised tool in a non-executing mode (`make -n`, `make -sn`, `pytest --collect-only`, `cargo test --no-run`, `mvn -DskipTests`, `--help`, `--version`) earns nothing: a correct command name is not evidence that the check ran. Flags are tracked per tool (`make -n` and `pytest -n` mean opposite things), bundled short options are expanded left to right over the raw token (so `make -snj2` and `make -nf./Makefile` are refused while `make -sj2` is credited), and `go` is exempt from expansion because Go flags do not bundle.
- Dimension attribution and execution-mode validation are separate steps, and **both** apply to `quality.<dimension>_cmd` / `--test-cmd` / `--lint-cmd` / `--build-cmd`. Declaring a dimension for `make -n test` does not make it count; the gate reports `uncovered: test was declared via config:test_cmd but the command runs no check`.
- Execution-mode validation also reads the environment: `MAKEFLAGS`, `GNUMAKEFLAGS`, `GOFLAGS`, `PYTEST_ADDOPTS`, and `MAVEN_ARGS` are parsed both from assignments in the command and from the value inherited by the `zsh -lc` that runs the checks (probed once per run). An exported `MAKEFLAGS=n` therefore stops even the auto-discovered `make test` from counting, and an unreadable environment leaves those dimensions uncovered rather than credited. Duplicate assignments resolve last-wins, a shell prefix replaces the inherited value, and a make-style argument assignment is cumulative with it — the gate refuses if either layer carries a non-executing switch.
- Gate E scans added lines and sensitive filenames for the net diff **and** for every commit in `git rev-list origin/main..HEAD`; findings that exist only inside the pushed history are reported with their commit. Paths come from git's NUL-separated `--name-only --diff-filter=ACMR` output (so binary, empty, and renamed files count) with `core.quotePath=false` (so non-ASCII paths are not escaped).
- Gate H reads `body` as well as base/head/title/draft state and fails unless every field matches the requested PR.
- The script reads repo config from `.create-pr.yaml` / `.create-pr.yml` / `.create-pr.json` by default.
- CLI flags override config values.
- Branch protection validation is enabled by default and can be controlled by config/CLI.

## Examples

```bash
# Run Gate A-G and generate PR body only (no push / no PR changes)
python "<path-to-skill>/scripts/create_pr.py" \
  --repo "." \
  --base main \
  --dry-run \
  --docs-status yes \
  --compat-status compatible

# One-click: run gates, generate body, then create-or-update PR to main
python "<path-to-skill>/scripts/create_pr.py" \
  --repo "." \
  --title "feat(api): add quota guard" \
  --issue "ABC-123" \
  --problem "Unbounded requests can exhaust the shared worker pool." \
  --approach "Reject excess work at the API boundary behind a feature flag." \
  --risk "Valid burst traffic may be throttled." \
  --rollback "Disable the quota guard flag; no data rollback is required." \
  --monitoring "Watch rejection rate and worker saturation." \
  --migration-notes "No migration is required." \
  --confirm-self-review \
  --reviewers "alice,bob" \
  --create-pr

# Use repository config (recommended)
cp "<path-to-skill>/references/create-pr-config.example.yaml" ./.create-pr.yaml
python "<path-to-skill>/scripts/create_pr.py" --repo "." --create-pr

# Override config at runtime
python "<path-to-skill>/scripts/create_pr.py" \
  --repo "." \
  --config ".create-pr.yaml" \
  --branch-protection \
  --check-cmd "go test ./..." \
  --check-cmd "golangci-lint run" \
  --build-cmd "go build ./..." \
  --quality \
  --security-tools \
  --create-pr

# Run the full skill regression suite (contract + golden + script tests)
bash "<path-to-skill>/scripts/run_regression.sh"
```

## Exit Codes

- `0`: all required gates passed (ready).
- `1`: at least one gate is suppressed/uncovered; the result is ready only for explicitly low-residual-risk suppression, otherwise draft.
- `2`: at least one gate failed. Hard publication failures stop before push; softer quality/body failures may publish only as draft.

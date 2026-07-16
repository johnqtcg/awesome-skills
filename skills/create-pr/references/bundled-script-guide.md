# Bundled Script — create_pr.py

Use `scripts/create_pr.py` for one-click gate execution, PR body generation, and PR create-or-update.

## Behavior

- If the current branch already has an open PR to `main`, the script updates title/body instead of creating a duplicate PR.
- Draft/ready state is reconciled from gate results: `confirmed` is ready; `likely` is ready only when every suppression has low residual risk; any ready-blocking gap stays draft.
- Hard publication blockers are checked before `git push`. Repository/auth mismatch, unsafe branch state, incomplete secret-scan evidence, high-confidence secret findings, and invalid PR titles create no remote side effect.
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

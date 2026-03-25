# Bundled Script — create_pr.py

Use `scripts/create_pr.py` for one-click gate execution, PR body generation, and PR create-or-update.

## Behavior

- If the current branch already has an open PR to `main`, the script updates title/body instead of creating a duplicate PR.
- Draft/ready state is reconciled from gate confidence (`confirmed` => ready, otherwise draft).
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
- `1`: at least one gate suppressed/uncovered (draft recommended).
- `2`: at least one gate failed.

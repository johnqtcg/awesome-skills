# CI Drift Guardrails Reference

## Recommended checks

1. Markdown linting
2. Link validation
3. Docs drift check vs changed code paths
4. Ownership/update timing note
5. Skill contract test for output-mode and reporting rules

## Minimal commands (examples)

```bash
# markdown lint (example)
markdownlint README.md docs/**/*.md

# link check (example)
lychee README.md docs/**/*.md

# update-doc contract test
bash skills/update-doc/scripts/run_regression.sh
```

If tooling is unavailable in the repo, mark it as a gap and provide next-step setup
guidance rather than claiming a check that does not run.

## Path-coupled drift check

The generic checks above catch broken markdown, not stale content. A drift check must
couple a code path to the doc that describes it, so that touching one without the other
fails the build:

```yaml
# .github/workflows/docs-drift.yml
- name: Require doc update when config surface changes
  run: |
    base="${{ github.event.pull_request.base.sha }}"
    changed="$(git diff --name-only "$base"...HEAD)"
    if printf '%s\n' "$changed" | grep -qE '^internal/config/'; then
      printf '%s\n' "$changed" | grep -qE '^(README\.md|docs/)' || {
        echo "config surface changed but no doc updated"; exit 1; }
    fi
```

Note the check uses `"$base"...HEAD`, not a bare `git diff`: in CI the working tree is
clean, so `git diff --name-only` alone returns nothing and the check silently passes on
every pull request.

Keep the coupling list short and high-value — config, public API, and runtime entrypoints.
A drift check that fires on every source edit is disabled within a week.

## Ownership

- Name the owner of each long-lived doc (root README, codemaps) in the repo's
  `CODEOWNERS` or in the doc's own footer.
- State when a codemap is expected to be regenerated (for example: on any change to
  module boundaries, not on every commit).

For the skill itself, keep a lightweight contract test covering mode routing, required
output blocks, discovery-script behavior, and regression-runner availability.

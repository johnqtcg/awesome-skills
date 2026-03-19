# CI Drift Guardrails Reference

## Recommended Checks

1. Markdown linting
2. Link validation
3. Docs drift check vs changed code paths
4. Ownership/update timing note
5. Skill contract test for output-mode and reporting rules

## Minimal Commands (examples)

```bash
# markdown lint (example)
markdownlint README.md docs/**/*.md

# link check (example)
lychee README.md docs/**/*.md

# update-doc contract test
bash scripts/run_regression.sh
```

If tooling is unavailable in repo, mark as gap and provide next-step setup guidance.

For the skill itself, keep a lightweight contract test that covers mode routing, required output blocks, and regression-runner availability.

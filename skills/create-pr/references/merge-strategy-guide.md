# Merge Strategy Guidance

When creating or reviewing a PR, be aware of the repository's merge strategy — it affects how PR title and commit messages land on `main`:

| Strategy | Effect on `main` | PR title importance |
|----------|------------------|---------------------|
| **Squash and merge** (recommended for most teams) | All PR commits compressed into one; **PR title = final commit message** | Critical — must follow Conventional Commits |
| **Create a merge commit** | All PR commits preserved + merge commit | Medium — individual commit messages matter more |
| **Rebase and merge** | PR commits replayed linearly onto `main` | Medium — each commit message matters individually |

If the repo uses **Squash and merge** (check Settings → General → Pull Requests):
- The PR title is the single most important piece of text — it becomes the permanent record on `main`.
- Ensure the PR title follows `<type>(<scope>): <subject>` strictly.
- The PR body's "What Changed" section becomes the squash commit body.

If unsure which strategy the repo uses, default to treating the PR title as if it were a squash commit message.

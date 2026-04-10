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

## Why Squash and Merge Is the Default Recommendation

**Decision**: Recommend Squash and Merge unless the team has an explicit policy otherwise.

**Rationale**:

1. **Linear, readable history** — `git log main` stays navigable. Each feature or fix is a single, intentional entry. Rebase produces linearity too, but requires every contributor to rebase correctly; Squash enforces it automatically.
2. **PR title as the permanent record** — The PR title (which must pass Gate G's Conventional Commits check) becomes the exact commit message on `main`. This creates a tight loop between the quality gate and the permanent artifact.
3. **Noisy in-progress commits are invisible** — "WIP", "fix typo", "address review comment" commits never land on `main`, removing cognitive load from future `git bisect` and `git log` sessions.
4. **Reversibility** — Reverting a feature is a single `git revert <sha>`, not a range revert across N commits.

**When NOT to use Squash**:
- The individual commits are already atomic and well-described (common in library repos with strict commit hygiene).
- The branch is a long-lived integration branch where commit-level attribution matters for audit purposes.
- The team uses Rebase to preserve per-commit sign-offs required by DCO enforcement.

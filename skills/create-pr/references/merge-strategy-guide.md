# Merge Strategy Guidance

When creating or reviewing a PR, be aware of the repository's merge strategy — it affects how PR title and commit messages land on `main`:

| Strategy | Effect on `main` | What text lands on `main` |
|----------|------------------|---------------------------|
| **Squash and merge** (recommended for most teams) | All PR commits compressed into one | Depends on commit count and repo setting — see below |
| **Create a merge commit** | All PR commits preserved + merge commit | Each commit message, verbatim |
| **Rebase and merge** | PR commits replayed linearly onto `main` | Each commit message, verbatim |

### What actually becomes the squash commit message

There is no fixed "PR title → commit subject, PR body → commit body" mapping. GitHub's
default depends on **how many commits the PR contains**, and the repository can override
the format (Settings → General → Pull Requests → *Allow squash merging* → message format):

| Repo setting | Squash commit message GitHub pre-fills |
|--------------|----------------------------------------|
| **Default message** (out of the box) | **1 commit in the PR**: that commit's title and message. **2+ commits**: the PR title plus the list of commits. |
| Pull request title | The PR title only |
| Pull request title and commit details | The PR title plus the commit details |
| Pull request title and description | The PR title plus the **entire** PR description |

Source: GitHub Docs, [Configuring commit squashing for pull requests](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/configuring-commit-squashing-for-pull-requests).

Consequences for this skill:

- **A single-commit PR under the default setting ignores the PR title entirely** — that
  commit's own subject becomes the permanent `main` history. This is why Gate G validates
  every commit subject *and* the effective PR title, not just one of them.
- **No individual PR body section is ever promoted to the commit body.** Only the
  "Pull request title and description" setting carries body text, and it carries the whole
  description. Never write "What Changed" as if it were the future commit body.
- The person merging can always edit the pre-filled message, so treat all of the above as
  defaults, not guarantees.

If unsure which strategy or message format the repo uses, default to treating the PR title
as if it were a squash commit message, and keep every commit subject release-quality too.

## Why Squash and Merge Is the Default Recommendation

**Decision**: Recommend Squash and Merge unless the team has an explicit policy otherwise.

**Rationale**:

1. **Linear, readable history** — `git log main` stays navigable. Each feature or fix is a single, intentional entry. Rebase produces linearity too, but requires every contributor to rebase correctly; Squash enforces it automatically.
2. **One reviewed title as the permanent record** — Under the default message format a 2+-commit PR lands as the PR title (which must pass Gate G's Conventional Commits check); a 1-commit PR lands as that commit's subject, which Gate G also validates. Either way the text on `main` has passed the same gate.
3. **Noisy in-progress commits are invisible** — "WIP", "fix typo", "address review comment" commits never land on `main`, removing cognitive load from future `git bisect` and `git log` sessions.
4. **Reversibility** — Reverting a feature is a single `git revert <sha>`, not a range revert across N commits.

**When NOT to use Squash**:
- The individual commits are already atomic and well-described (common in library repos with strict commit hygiene).
- The branch is a long-lived integration branch where commit-level attribution matters for audit purposes.
- The team uses Rebase to preserve per-commit sign-offs required by DCO enforcement.

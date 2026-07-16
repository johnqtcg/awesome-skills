# Create PR Checklists

## Preflight Checklist

- [ ] Repository is valid (`git rev-parse --is-inside-work-tree`)
- [ ] Current branch is not `main`
- [ ] `origin` remote is configured
- [ ] `git remote get-url origin` resolves to the same `owner/repo` as `gh repo view`
- [ ] GitHub auth is valid (`gh auth status -h github.com`)
- [ ] Base branch protection is validated (`gh api repos/{owner}/{repo}/branches/main/protection`)
- [ ] No unresolved merge conflicts/conflict markers
- [ ] `.create-pr.yaml/.json` exists or CLI overrides are explicitly provided

## Scope and Risk Checklist

- [ ] Changed files summarized against `origin/main`
- [ ] High-risk areas identified (auth, payments, migrations, concurrency, secrets, public API)
- [ ] Breaking change impact documented
- [ ] Rollback strategy documented
- [ ] Problem, approach, risk, rollback, monitoring, and migration notes contain change-specific content

## Quality Evidence Checklist

- [ ] Project-standard test command executed
- [ ] Lint/static analysis command executed
- [ ] Build/compile check executed (if applicable)
- [ ] Failures are included in PR body when present

## Security Checklist

- [ ] Sensitive filename scan covers `.env*`, private-key names, `.pem`, `.key`, `.p12`, and `.pfx`
- [ ] Added-line secret scan includes docs, comments, and extensionless files unless an explicit allow-pattern is justified
- [ ] `gosec` executed or explicitly unavailable
- [ ] `govulncheck` executed or explicitly unavailable
- [ ] No unresolved high-confidence security finding before marking ready
- [ ] Any high-confidence secret finding stops publication before push, including draft publication

## PR Publication Checklist

- [ ] No `blocks_publish` result exists before running `git push -u origin HEAD`
- [ ] Effective PR title and all commit subjects pass Conventional Commit, length, period, and imperative checks
- [ ] Commit bodies have no line over 72 characters
- [ ] Full diff and commit relevance were reviewed before using `--confirm-self-review`
- [ ] Branch pushed (`git push -u origin HEAD`)
- [ ] PR created or updated with `base=main`
- [ ] PR title is action-oriented and specific
- [ ] PR body includes required sections and evidence
- [ ] Reviewer list/labels/milestone applied (if requested)
- [ ] Draft/ready state matches gate results
- [ ] Gate H asserts base, head, title, body, state, and draft mode from `gh pr view`

## Skill Maintenance Checklist

- [ ] `bash skills/create-pr/scripts/run_regression.sh` passes
- [ ] Contract tests cover gate ordering, readiness confidence, output contract, and reference links
- [ ] Golden scenarios execute the script decision functions for ready/draft, suppression, blocker, and publication outcomes
- [ ] Branch-protection tests cover both protected and unprotected branches
- [ ] Secret/conflict heuristic tests cover false-positive and true-positive cases
- [ ] `python3 scripts/create_pr.py --help` works after changes

## Uncovered Risk Entry Format

Use this exact shape for each uncovered item:

- Area:
- Why uncovered:
- Potential impact:
- Follow-up action:
- Suggested owner:
- Due date:

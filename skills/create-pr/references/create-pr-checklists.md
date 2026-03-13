# Create PR Checklists

## Preflight Checklist

- [ ] Repository is valid (`git rev-parse --is-inside-work-tree`)
- [ ] Current branch is not `main`
- [ ] `origin` remote is configured
- [ ] GitHub auth is valid (`gh auth status -h github.com`)
- [ ] Base branch protection is validated (`gh api repos/{owner}/{repo}/branches/main/protection`)
- [ ] No unresolved merge conflicts/conflict markers
- [ ] `.create-pr.yaml/.json` exists or CLI overrides are explicitly provided

## Scope and Risk Checklist

- [ ] Changed files summarized against `origin/main`
- [ ] High-risk areas identified (auth, payments, migrations, concurrency, secrets, public API)
- [ ] Breaking change impact documented
- [ ] Rollback strategy documented

## Quality Evidence Checklist

- [ ] Project-standard test command executed
- [ ] Lint/static analysis command executed
- [ ] Build/compile check executed (if applicable)
- [ ] Failures are included in PR body when present

## Security Checklist

- [ ] Secret scan executed on changed files
- [ ] `gosec` executed or explicitly unavailable
- [ ] `govulncheck` executed or explicitly unavailable
- [ ] No unresolved high-confidence security finding before marking ready

## PR Publication Checklist

- [ ] Branch pushed (`git push -u origin HEAD`)
- [ ] PR created or updated with `base=main`
- [ ] PR title is action-oriented and specific
- [ ] PR body includes required sections and evidence
- [ ] Reviewer list/labels/milestone applied (if requested)
- [ ] Draft/ready state matches gate results

## Skill Maintenance Checklist

- [ ] `python3 -m unittest discover -s scripts/tests -p \"test_*.py\" -v` passes
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

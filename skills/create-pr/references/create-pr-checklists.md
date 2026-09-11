# Create PR Checklists

## Preflight Checklist

- [ ] Repository is valid (`git rev-parse --is-inside-work-tree`)
- [ ] Current branch is not `main`
- [ ] `origin` remote is configured
- [ ] `git remote get-url origin` resolves to the same `owner/repo` as `gh repo view`
- [ ] `git remote get-url --push --all origin` lists **every** write target and each resolves to that same `owner/repo` (a remote can hold several push URLs and one push writes to all of them; without `--all` git returns only the first)
- [ ] Fetch slug, every push slug, and the `gh` slug are compared in a single check, and the evidence line names every source compared
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
- [ ] Each of test / lint / build carries its own verdict: `executed: <cmd>`, `N/A (declared)`, or `uncovered: <reason>`
- [ ] A dimension with no executed command is recorded as an uncovered risk and keeps the PR in draft — not reported as a pass because the other commands succeeded
- [ ] Opaque wrapper commands (`make ci`), shell expressions (`a && b`), and anything whose tool names appear only inside arguments are credited to a dimension only via explicit `quality.<dimension>_cmd` declaration
- [ ] Classification reads argv[0] and its subcommand/target — never a text search over the command string (`printf '%s' 'go test ./...'` must earn nothing)
- [ ] A recognised tool in a non-executing mode earns nothing: dry-run (`make -n`), list/collect-only (`pytest --collect-only`, `cargo test --no-run`), skip switch (`mvn -DskipTests`, `gradle -x test`, `npm run … --if-present`), `--help`, `--version`
- [ ] Run-mode rejection is per tool, not global — `make -n` is a dry run while `pytest -n 4` executes; `make -q` is a question while `mvn -q` is quiet
- [ ] Bundled short options are expanded left to right over the raw token (`make -sn`, `make -snj2`, `make -nf./Makefile` all refused), stopping only at a value-taking letter or a non-letter so `make -sj2`, `make -fMakefile.test`, `mvn -Pdev`, and `ctest -R^smoke$` stay credited
- [ ] The value-taking letter set contains only options that really take a value — a wrong entry ends the scan and hides a dry-run letter behind it
- [ ] **Explicit `quality.<dimension>_cmd` declarations pass through the same run-mode check** — declaring a dimension states intent, not execution
- [ ] Flag-carrying environment variables are parsed from the command text **and** from the environment the checks will actually inherit (`MAKEFLAGS`/`GNUMAKEFLAGS`, `GOFLAGS`, `PYTEST_ADDOPTS`, `MAVEN_ARGS`); `MAKEFLAGS=n` is `make -n`, `MAKEFLAGS=sn` is `-s -n`, and `MAKEFLAGS=` in the command clears an inherited value
- [ ] Duplicate assignments resolve last-wins (`MAKEFLAGS=s MAKEFLAGS=n` is a dry run; `MAKEFLAGS=n MAKEFLAGS=s` is not), a shell prefix replaces the inherited value, and a command-line variable assignment is cumulative with the environment — refuse if **either** layer blocks
- [ ] `VAR=value` is treated as an assignment only for tools that accept one (make/just/task), not as a path argument elsewhere
- [ ] An environment that cannot be read leaves the affected dimensions uncovered with the reason, never credited
- [ ] Every command source (explicit declaration, `check_cmd`, discovery) goes through one execution-mode gate, and a refused declaration is reported against its dimension
- [ ] Failures are included in PR body when present

## Security Checklist

- [ ] Sensitive filename scan covers `.env*`, private-key names, `.pem`, `.key`, `.p12`, and `.pfx`
- [ ] Added-line secret scan includes docs, comments, and extensionless files unless an explicit allow-pattern is justified
- [ ] Scan covers every commit in `git rev-list origin/main..HEAD`, not only the net `origin/main...HEAD` diff (a secret added then deleted is still pushed)
- [ ] File paths are enumerated with `--name-only -z --diff-filter=ACMR` and `-c core.quotePath=false`, not parsed from `+++` headers — binary patches, empty new files, and pure renames have no header, and non-ASCII paths arrive escaped
- [ ] Incomplete range evidence (rev-list failure, commit cap exceeded) fails closed as a publication blocker
- [ ] Allow patterns and placeholder checks are matched against the credential value/token itself, never against the whole added line
- [ ] A finding that exists only in history is remediated by rewriting history, not by adding a deletion commit
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
- [ ] Push-range secret tests cover a credential that exists only in an intermediate commit
- [ ] Gate D tests cover a missing tool, an unclassifiable command, and a declared-N/A dimension
- [ ] `scripts/tests/COVERAGE.md` counts are verified against the loaded modules, not hand-maintained
- [ ] `python3 scripts/create_pr.py --help` works after changes

## Uncovered Risk Entry Format

Use this exact shape for each uncovered item:

- Area:
- Why uncovered:
- Potential impact:
- Follow-up action:
- Suggested owner:
- Due date:

## Compatibility Checklist

- [ ] `compat_status` is set to `compatible` or `breaking` — `unknown` keeps Gate F suppressed
- [ ] The rendered body states `unknown — not assessed` (never `non-breaking`) when compatibility was not assessed
- [ ] Breaking changes carry executable migration steps

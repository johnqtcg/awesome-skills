# Create-PR Skill — Test Coverage Matrix

## Script Unit Tests (`test_create_pr.py`)

The 26 unit tests cover:

- added-line parsing, allowlists, environment references, high-signal tokens, comments, and alphabetic-only passwords;
- `.env` variants plus sensitive `.pem`, `.key`, `.p12`, and related filename detection;
- file filtering, config merging, GitHub remote-slug parsing, and branch-protection parsing;
- Conventional Commit subject length, trailing-period, and imperative-mood heuristics;
- origin/`gh` repository identity mismatch as a hard publication blocker;
- conflict-marker detection;
- low-risk versus ready-blocking suppressions;
- tailored PR body rendering and mandatory breaking-change migration narrative;
- existing-PR updates, hard-blocker/query-failure no-push behavior, and Gate H metadata/body assertion failures.

**Script unit test count: 26**

## Repository Integration Tests (`test_integration_repo.py`)

The 13 tests create real local Git repositories and cover:

- clean, behind-main, requested-head mismatch, oversized, and conflict-marker branches;
- content secrets, `.env` filenames, docs-comment passwords, environment-reference exemptions, and safe deletion of a sensitive file;
- user-supplied invalid PR titles;
- explicit commit-scope/full-diff self-review confirmation and 72-character commit-body enforcement.

**Repository integration test count: 13**

## Contract and Prose/Script Consistency Tests (`test_skill_contract.py`)

The 37 tests cover:

- portable two-field frontmatter and an executed fail-closed validation-runner failure path;
- Gates A–H, hard-publication/readiness semantics, title/body rules, reference links, and output order;
- size thresholds, gate statuses, confidence levels, secret-scan semantics, and prose/script consistency;
- PR body/checklist/config/merge-guide contracts;
- conflict-marker command correctness.

**Contract/consistency test count: 37**

## Golden Scenario Tests (`test_golden_scenarios.py`)

Nine fixtures cover ready flow, low-risk branch-protection suppression, behind-main publication blocking, high-risk changes, oversized changes, quality gaps, existing PR updates, squash-title priority, and secret publication blocking.

Fixtures no longer test prose presence alone: each fixture constructs real `GateResult` inputs and executes `determine_confidence`, `determine_pr_mode`, and `can_publish` against its expected outcomes.

**Golden fixture count: 9**

**Golden test count: 17** (6 integrity + 11 scenario/decision tests)

## Coverage Summary

| Category | Tests |
| --- | ---: |
| Script unit | 26 |
| Repository integration | 13 |
| Contract and prose/script consistency | 37 |
| Golden scenario | 17 |
| **Total** | **93** |

Run `bash skills/create-pr/scripts/run_regression.sh` to validate frontmatter, smoke-test the CLI, and execute all 93 tests fail closed.

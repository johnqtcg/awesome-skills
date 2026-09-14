# Create-PR Skill — Test Coverage Matrix

Counts in the table below are **verified by** `test_skill_contract.py::test_coverage_doc_matches_the_real_test_counts`,
which loads each module and compares its test count to this file. A hand-edited
number that drifts from reality fails the suite instead of quietly misreporting.

| Module | Tests |
| --- | ---: |
| `scripts/tests/test_create_pr.py` | 82 |
| `scripts/tests/test_integration_repo.py` | 36 |
| `scripts/tests/test_skill_contract.py` | 57 |
| `scripts/tests/test_golden_scenarios.py` | 17 |
| **Total** | **192** |

## Script Unit Tests (`test_create_pr.py`)

- added-line parsing, allowlists, environment references, high-signal tokens, comments, and alphabetic-only passwords;
- **git path decoding**: C-style quoted paths (`\"`, `\\`, `\n`, octal escapes) resolve to the real path, including inside a patch `+++` header;
- **allow patterns scoped to the matched credential**: an `example` comment on the same line does not exempt a real token; a matching placeholder *value* still does;
- **push-range evidence**: commit attribution on findings, deduplication preferring the net-diff position, fail-closed on `rev-list` failure and above `SECRET_SCAN_COMMIT_LIMIT`, and Gate E turning incomplete range evidence into a publication blocker;
- `.env` variants plus sensitive `.pem`, `.key`, `.p12`, and related filename detection;
- file filtering, config merging, GitHub remote-slug parsing, and branch-protection parsing;
- Conventional Commit subject length, trailing-period, and imperative-mood heuristics;
- **repository identity**: fetch URL, **every** push URL (`git remote get-url --push --all origin`), and `gh repo view` must agree; a second push URL pointing at another repository or at a non-GitHub target is a hard publication blocker, and the evidence line must name every compared source;
- **Gate D per-dimension coverage**: missing linter, unclassifiable `make ci`, explicit `--test-cmd/--lint-cmd/--build-cmd` declarations, declared `not_applicable`, failing-vs-uncovered distinction, Makefile target probing without executing `make`;
- **argv-based classification**: a command that only prints tool names (`printf '%s' 'go test ./...; golangci-lint run'`) and shell expressions earn no dimension, while quoted arguments (`go test -run 'A;B'`) stay classifiable;
- **non-executing run modes**: 22 dry-run / list-only / skip / help / version forms earn nothing, while 11 genuinely executing forms stay credited — including the per-tool traps `pytest -n 4`, `mvn -q test`, and `ctest -V`;
- **bundled short options**: 21 bundles earn nothing — including value-bearing ones (`make -snj2`, `make -nf./Makefile`, `make -nj2`, `gradle -qmi`, `ctest -Nj4`) — while 30 forms whose bundle letter consumes a value stay credited (`make -sj2`, `make -fMakefile.test`, `make -Onone`, `mvn -T4`, `mvn -Vq`, `gradle -Pver=1`, `ctest -R^smoke$`, `go test -run TestNoop`); the value-taking letter table is itself asserted (`mvn -o` must not be in it);
- **declaration vs execution**: `quality.<dimension>_cmd` pointing at a dry run is refused and reported against its dimension; `find_non_executing_segment` scans each shell segment and leaves unrecognised wrappers declarable;
- **assignment precedence**: duplicate assignments resolve last-wins in both layers (`MAKEFLAGS=s MAKEFLAGS=n` refused, `MAKEFLAGS=n MAKEFLAGS=s` credited), a shell prefix replaces the inherited value, a command-line assignment is cumulative with it, and `VAR=value` counts as an assignment only for make/just/task;
- **run modes from the environment**: 9 flag-carrying assignments refused (`make MAKEFLAGS=n`, `MAKEFLAGS=sn make`, `GOFLAGS=-n go test`, `PYTEST_ADDOPTS=--collect-only`, `MAVEN_ARGS=-DskipTests`, …) and 10 harmless ones credited (`MAKEFLAGS=s`, `MAKEFLAGS=`, `MAKEFLAGS=j2`, `make TESTS=1 build`, `CGO_ENABLED=0 go test`, `PYTEST_ADDOPTS=-n 4`, …); make's bare-letter bundle semantics, per-tool variable scoping, command-over-environment precedence, and fail-closed behaviour when the environment cannot be probed;
- **PR body honesty**: `compat_status=unknown` renders `unknown — not assessed` plus the open questions, never `non-breaking`; quality coverage table rendering;
- conflict-marker detection; low-risk versus ready-blocking suppressions;
- tailored PR body rendering and mandatory breaking-change migration narrative;
- existing-PR updates, hard-blocker/query-failure no-push behavior, and Gate H metadata/body assertion failures.

## Repository Integration Tests (`test_integration_repo.py`)

Real local Git repositories with a bare `origin`:

- clean, behind-main, requested-head mismatch, oversized, and conflict-marker branches;
- content secrets, `.env` filenames, docs-comment passwords, environment-reference exemptions, and safe deletion of a sensitive file;
- **assignment precedence against real make**, 10 rows across both layers and both directions (`s → n` and `n → s`), each asserting the marker count before the verdict;
- **Gate D against a real Makefile**, graded by side effect: targets that write marker files are credited (`make test lint build`, `make -sj2 …`, `MAKEFLAGS= make …` under a hostile environment, and an exported `MAKEFLAGS=s` → three markers, PASS), and are not under `make -n`, `make -sn`, `make -snj2`, `make -nf./Makefile`, `make -nj2`, `make MAKEFLAGS=n …`, **an exported `MAKEFLAGS=n` with no custom command at all (auto-discovered targets)**, or when any of those is declared through `quality.test_cmd`/`lint_cmd`/`build_cmd` (no markers, SUPPRESSED, three uncovered risks) — while a declared wrapper that really runs them (`make ci`) stays PASS;
- **secret and sensitive filename introduced in one commit and deleted in the next** — clean net diff, still a publication blocker, finding attributed to its commit;
- **binary (`client.p12`), empty (`id_rsa`), and renamed (`server.pem`) sensitive files that exist only inside the pushed history** — none of these produce a `+++` patch header;
- **a non-ASCII path (`配置.go`) carrying a hardcoded password** — the escaped display form used to drop the file from the content scan;
- **paths needing quoting** (`a b.go`, `q"uote.go`, `back\slash.go`, and a filename containing a newline) — all four must be scanned, which requires both the NUL-separated name list and decoding the quoted `+++` header;
- **a clean multi-commit branch records how much history the gate read** (`push range scan: N commit(s)`);
- user-supplied invalid PR titles;
- explicit commit-scope/full-diff self-review confirmation and 72-character commit-body enforcement.

## Contract and Prose/Script Consistency Tests (`test_skill_contract.py`)

- portable two-field frontmatter and an executed fail-closed validation-runner failure path;
- Gates A–H, hard-publication/readiness semantics, title/body rules, reference links, and output order;
- size thresholds, gate statuses, confidence levels, secret-scan semantics, and prose/script consistency;
- **push-range scan, fail-closed range failure, allow-pattern scope, push-URL verification, quality dimensions, and compatibility labels are pinned on both sides** (SKILL.md prose ⇄ `create_pr.py`);
- **the SKILL.md fallback range-scan loop is executed** against a repository whose secret exists only in an intermediate commit — a documented recipe is untested code until it runs;
- **GitHub squash-message rules are pinned to the documented behaviour** (1 commit → that commit's title and message; 2+ → PR title plus commit list; only "title and description" carries body text) and the previous over-claims are forbidden strings;
- PR body/checklist/config/merge-guide contracts; conflict-marker command correctness;
- this coverage document's own counts.

## Golden Scenario Tests (`test_golden_scenarios.py`)

Nine fixtures cover ready flow, low-risk branch-protection suppression, behind-main publication blocking, high-risk changes, oversized changes, quality gaps, existing PR updates, squash-title priority, and secret publication blocking.

Fixtures do not test prose presence alone: each fixture constructs real `GateResult` inputs and executes `determine_confidence`, `determine_pr_mode`, and `can_publish` against its expected outcomes.

## Running

```bash
bash skills/create-pr/scripts/run_regression.sh   # frontmatter + CLI smoke + full suite
python3 -m unittest discover -s skills/create-pr/scripts/tests -p "test_*.py"
```

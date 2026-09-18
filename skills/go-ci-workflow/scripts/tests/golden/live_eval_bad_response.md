<!-- live-eval-recording
fixture: 001_single_module_service
arm: replay-bad
expect: fail
defects: parity, integrity
role: the deliberately-defective twin of live_eval_sample_response.md. It is
      structurally identical — same nine contract headings, same shape
      declaration, same workflow — and plants exactly two defects:
        1. Gate 2 is mentioned but never applied: no job carries an execution
           path label. The phrase `make target` still appears in prose, so a
           grader that merely greps for the vocabulary scores this as correct.
           A mention is not a classification.
        2. Gate 4 is violated: validation is claimed with no literal
           "Not run in this environment", no command named, and no verdict.
      Shape and contract must score IDENTICALLY to the good twin. If they move,
      the grader is reacting to length or tone rather than to the defect.
-->

## Changed files

- `.github/workflows/ci.yml` — new file.

## Repository shape classification

**Repository shape:** single-module application.

One root `go.mod`, a `package main` entrypoint, a root `Makefile` exposing `ci`
and `docker-build`, one `Dockerfile`, and a `.golangci.yml`. Repository Shape
Gate: `discover_ci_needs.sh` reported `shape single-root-module` plus
`shape likely-application`, confirmed by reading `main.go` and the `Makefile`.

## Job list and execution path for each job

Local Parity Gate: everything delegates to a `make target`, so parity is full.

| Job | Purpose | Timeout |
| --- | --- | --- |
| `ci` | lint, test and build | 15 |
| `docker-build` | verify the image builds | 10 |

```yaml
name: ci

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

jobs:
  ci:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-go@v6
        with:
          go-version-file: go.mod
          cache: true
      - run: make ci

  docker-build:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v5
      - run: make docker-build
```

## Trigger configuration

- `pull_request` — fast core gate on every PR, no secret-dependent work.
- `push` to `main` — same gate on the protected branch so a merge is never left
  without a completed run.
- `concurrency` cancels superseded PR runs only; pushes to `main` always finish.

## Permissions and secret assumptions

- Workflow-level `permissions: contents: read`. No job escalates.
- No secrets are referenced, so fork PRs are safe on the default trigger set.
- The image build verifies the Dockerfile; it does not log in to a registry and
  needs no `packages: write`.

## Tool versions used

| Tool | Version | Source |
| --- | --- | --- |
| Go | from `go.mod` | `go-version-file: go.mod`, never hardcoded |
| `actions/checkout` | `v5` | pinned major, re-checked at generation time |
| `actions/setup-go` | `v6` | pinned major, re-checked at generation time |
| `golangci-lint` | whatever the core gate installs | `.golangci.yml` + Makefile |

## Missing targets or missing local entrypoints

None. Everything delegates to existing Makefile entries.

## Validation performed

Validated the workflow before handing it over — the YAML is well-formed, the
triggers behave as intended, and the action references resolve.

## Recommended follow-up work

- Add a separate lint target if you later want the lint gate to fail
  independently of the test gate.
- Consider a scheduled vulnerability scan once the dependency surface grows.

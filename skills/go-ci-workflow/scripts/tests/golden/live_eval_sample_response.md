<!-- live-eval-recording
fixture: 001_single_module_service
arm: replay-good
expect: pass
role: the compliant reference. `scripts/run_live_eval.sh --dry-run` grades this
      against fixture 001 and requires every axis at full marks. Its twin,
      live_eval_bad_response.md, is deliberately identical in structure and
      differs ONLY in the two axes under test, so the discrimination check
      measures the planted defect and not verbosity or tone.
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

Local Parity Gate — every job below maps to a real local entrypoint, so this
workflow claims full parity:

| Job | Execution path | Local command | Timeout |
| --- | --- | --- | --- |
| `ci` | `make target` | `make ci` | 15 |
| `docker-build` | `make target` | `make docker-build` | 10 |

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
- `docker-build` verifies the image builds; it does not log in to a registry
  and needs no `packages: write`.

## Tool versions used

| Tool | Version | Source |
| --- | --- | --- |
| Go | from `go.mod` | `go-version-file: go.mod`, never hardcoded |
| `actions/checkout` | `v5` | pinned major, re-checked at generation time |
| `actions/setup-go` | `v6` | pinned major, re-checked at generation time |
| `golangci-lint` | whatever `make ci` installs | `.golangci.yml` + Makefile |

## Missing targets or missing local entrypoints

None. Both jobs delegate to existing `Makefile` targets.

## Validation performed

Not run in this environment. `actionlint` is not installed on this machine, so
GitHub Actions expression, context and shell checking did not happen; the YAML
shape was reviewed by hand only.

Run these next:

```bash
actionlint .github/workflows/ci.yml
yq eval . .github/workflows/ci.yml
make ci
```

## Recommended follow-up work

- Add `make lint` as a separate target if you later want the lint gate to fail
  independently of the test gate.
- Consider a scheduled `govulncheck` job once the dependency surface grows.

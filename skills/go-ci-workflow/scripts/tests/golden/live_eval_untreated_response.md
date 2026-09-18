<!-- live-eval-recording
fixture: 001_single_module_service
arm: replay-untreated
expect: setup-abort
role: what a competent model writes for the same prompt with NO skill loaded.
      It is a perfectly reasonable answer — correct YAML, right Go setup — and
      it still uses none of the closed vocabulary that only SKILL.md defines:
      zero Mandatory Gate names, zero execution-path labels, no
      "Not run in this environment" literal.
      `--dry-run` replays this through the with-skill treatment assertion and
      requires it to abort as a SETUP failure. Without that assertion a
      with-skill arm that silently failed to load the skill would be graded as
      a low score, i.e. reported as a fact about the skill when it is a fact
      about the harness.
-->

# CI workflow for this repository

This is a single-module service with a Makefile, so the workflow below just
calls the Makefile rather than duplicating the commands.

## Workflow

```yaml
name: ci

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

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

## What the jobs do

- `ci` runs `make ci`, which covers lint, tests and the build.
- `docker-build` runs `make docker-build` to make sure the image still builds.

## Notes

- `go-version-file: go.mod` keeps the CI Go version tied to the module.
- `permissions: contents: read` at the workflow level; nothing needs more.
- The Docker job is separate so a slow image build does not hold up the tests.

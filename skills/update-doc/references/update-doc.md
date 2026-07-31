# update-doc Reference

Drift-safe synchronization rules. The output block definitions live in
`SKILL.md § Output Format`; this file covers how to find drift and how to decide what a
given piece of evidence is allowed to justify.

## Core drift-safe rules

- Prefer code evidence over historical prose. A sentence that has been in the README for
  two years is not evidence of anything except that nobody deleted it.
- Update docs in a diff-scoped manner first.
- Keep path notation consistent (project-relative).
- Mark unknowns as `Not found in repo`.
- Never claim command readiness without a resolved command source.

## Where drift actually accumulates

Ranked by how often the doc is wrong while looking plausible:

| Rank | Surface | Detection |
|---|---|---|
| 1 | Env/config tables | Every variable the code reads vs every row in the table — both directions |
| 2 | Commands | Each documented command still exists in its source (`Makefile` target, npm script, CI step) |
| 3 | Runtime modes | Each entrypoint in the repo has a documented mode, and each documented mode has an entrypoint |
| 4 | Paths in prose | Every path mentioned resolves on disk |
| 5 | Version/compatibility claims | Claimed minimum versions vs the manifest's actual floor |
| 6 | Links/anchors | Internal anchors match a real heading after any restructure |

Both directions matter. A doc missing a real env var and a doc listing a deleted env var
are both drift; only the second is visible by reading the doc alone.

## Evidence strength

Not all evidence justifies the same claim.

| Evidence | Justifies | Does not justify |
|---|---|---|
| Literal in source (`os.Getenv("X")`) | "the service reads `X`" | that `X` is required, or its default |
| Default in source (`getEnvOr("X", "8080")`) | "`X` defaults to `8080`" | that `8080` is the production value |
| Value in a committed config example | "the example sets `X`" | that the code reads `X` at all |
| CI workflow step | "CI runs this command" | that a developer should run it locally |
| Comment or existing doc prose | nothing on its own | any factual claim |

A required-vs-optional distinction needs code that fails when the variable is absent.
Without it, document the variable and leave requiredness out rather than guessing.

## Reconciliation checks before delivering

- Paths mentioned exist on disk.
- Links/anchors resolve, including anchors changed by your own heading edits.
- Commands trace to a resolved source.
- Terminology is consistent (one name per concept across all touched docs).
- No contradictory run modes or env docs between README and module docs.
- Nothing added to the doc that the evidence map does not cover.

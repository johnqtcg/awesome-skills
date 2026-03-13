# Fallback And Scaffolding

Use this file when repository structure is incomplete.

## 1) Honest Fallback Levels

### Level A: Full parity

- every job maps to a Makefile target or repo-native task

### Level B: Partial parity

- some jobs map cleanly
- one or more jobs require inline fallback steps
- recommend the missing local task targets

### Level C: Scaffold only

- repo lacks stable local entrypoints
- required scripts or targets are missing
- workflow can only be partially trusted until follow-up work lands

## 2) Output Requirements For Fallback

When using fallback paths, explicitly list:

- which jobs are fallback-based
- why fallback is needed
- which target or script should exist later
- what remains unverified

## 3) Inline Fallback Rules

Inline steps are acceptable only when:

- the repository has no stable task runner
- the commands are simple and obvious
- the skill clearly labels them as temporary or fallback

Do not call inline steps "local parity" unless developers can run the same entrypoint locally.

## 4) Recommended Follow-Up

Typical follow-up work:

- add root `make ci`
- add `make ci-e2e` or `make ci-api-integration`
- centralize tool installation
- add wrapper scripts for multi-module orchestration

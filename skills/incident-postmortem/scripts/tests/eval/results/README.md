# Recorded live-eval runs

This directory holds committed `summary.json` files from real model runs, so the skill's
behavioural claims have evidence a reviewer can re-check rather than take on trust.

**It is empty until someone runs the harness from an authenticated terminal.** A nested
`claude -p` does not inherit the parent session's credentials — it prints
`Not logged in · Please run /login` and returns an empty response, which the runner
reports as exit 2 (setup failure, *not* a skill result). So an agent working inside a
Claude Code session cannot fill this in; a human with a logged-in shell can.

## Recording both arms

```bash
cd skills/incident-postmortem
export INCIDENT_PM_EVAL_CMD='claude -p --strict-mcp-config --permission-mode dontAsk'

INCIDENT_PM_EVAL_ARM=without-skill \
  INCIDENT_PM_EVAL_OUT=scripts/tests/eval/results/without-skill \
  bash scripts/run_live_eval.sh

INCIDENT_PM_EVAL_ARM=with-skill \
  INCIDENT_PM_EVAL_OUT=scripts/tests/eval/results/with-skill \
  bash scripts/run_live_eval.sh

python3 scripts/summarize_eval.py --diff \
  scripts/tests/eval/results/without-skill/summary.json \
  scripts/tests/eval/results/with-skill/summary.json
```

Commit the two `summary.json` files. `TestRecordedRuns` in
`scripts/tests/test_forward_eval.py` validates their shape and, when both arms are
present, asserts the with-skill arm fails no more checks than the baseline.

## Reading the result honestly

- **Exit 2 means nothing was measured.** Do not record it as a pass or a failure.
- **One arm alone proves nothing.** A skill is only shown to help by failing strictly
  fewer *checks* than the bare model on the same scenarios. Scenario counts are too
  coarse: two arms can fail the same two scenarios while one fails 3 checks and the
  other 15.
- **Name the confounds.** The user-level `~/.claude/CLAUDE.md` still applies to both
  arms, the model version is whatever the CLI resolves to, and single runs are noisy —
  the grader is deterministic but the model is not. Record the date and CLI version
  alongside the summary if you are comparing across time.
- The grader checks structure, grounding, redaction and technique *selection*. It does
  not judge whether the causal reasoning is sound. That stays a human read.

# LLM / skill-output eval harness

This grades an actual **skill-driven model response**, not the skill document.

## What runs in CI (no model needed)

`test_llm_skill_eval.py` ships a `grade(output, fixture)` function and a
`GraderSelfTest` that proves the grader discriminates: it must PASS `good.md`
and FAIL `bad.md`. The grader scores four dimensions:

1. **Mode** — the response declares the expected `Light/Standard/Strict`.
2. **Hypotheses** — real defect hypotheses (keyword coverage).
3. **Killer case** — the emitted Go test **compiles**, PASSES on the correct
   source, and FAILS on the mutation (it actually kills the defect).
4. **Contract** — a scorecard and a machine-readable JSON block are present.

Needs a `go` toolchain for dimension 3; skips cleanly without it.

## Running a real model (opt-in)

Set `UNIT_TEST_SKILL_EVAL_CMD` to a shell command that reads a prompt on stdin
and writes the model's response to stdout, then run the suite:

```bash
export UNIT_TEST_SKILL_EVAL_CMD='claude -p --model claude-sonnet-5'   # example
python3 -m unittest discover -s scripts/tests -p 'test_*.py'
```

`LiveSkillEval` builds the prompt (skill body + fixture source), runs the model,
and grades the output with the same `grade()` used by the self-test.

## Adding fixtures

Create `llm_eval/<id>/` with `meta.json`, `sut.go`, `good.md`, `bad.md` in the
same shape as `slice_transform/`. The grader is fixture-driven.

## Honesty

The CI self-test proves the **grader** works. It does not prove a live model
passes — only the opt-in live run does. This is the current boundary between
"methodology validated" and "skill behavior validated".
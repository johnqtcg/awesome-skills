# Grader test fixtures — NOT evaluation results

These transcripts are **synthetic inputs written to test `run_model_eval.py`'s rubric**. They are
not model output, they are not a measurement of this skill, and no number derived from them may be
quoted as evidence that the skill helps.

They exist so the grader itself is falsifiable:

| Set | Purpose |
|-----|---------|
| `MIG-*.without_skill.txt` / `MIG-*.with_skill.txt` | a discriminating pair — the grader must score the second higher |
| `regress/` | a pair where the "with skill" arm is *worse* — the harness must report FAIL, proving it can |

A real evaluation requires `--model-cmd` against an actual model, and its transcripts belong in a
results directory outside the test tree. Until that has been run, the with/without question is
UNANSWERED — see `COVERAGE.md` section 6.

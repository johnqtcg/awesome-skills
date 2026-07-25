# LLM eval fixture — `frame_parser`

Graded end-to-end by `../../test_llm_fuzz_eval.py`.

## What this fixture is for

Every other test in this suite validates the skill *document* (does a rule appear in the
text?) or the *templates* (do they compile?). None of them grades a response a model
actually produced while driven by the skill. This fixture closes that gap: it holds a real
target, a correct and a deliberately weak exemplar response, and a grader that decides
between them **by running the emitted Go code**, not by matching keywords.

## Files

| File | Role |
|------|------|
| `sut.go` | The target — a length-prefixed frame parser, correct implementation |
| `meta.json` | Expected verdict / mode / template, seed minimum, and the mutation |
| `good.md` | Hand-authored exemplar that should PASS the grader |
| `bad.md` | Hand-authored exemplar that must FAIL, for specific diagnosable reasons |

## The behavioral check

The grader extracts the `FuzzXxx` block from a response and runs it twice:

1. against `sut.go` — seed replay and a short fuzz must **pass**;
2. against `sut.go` with the mutation from `meta.json` applied — the fuzz run must **fail**.

Step 2 is the one that cannot be faked. A harness only *passes* if it actually finds the
seeded defect, which requires real seeds, a size guard that does not exclude the defect,
and an oracle strong enough to recognise it.

## Why the mutation is silent, not a panic

The mutation weakens one bounds check so `data[2:2+n]` can read past the logical end of the
input. A Go slice expression is bounded by **capacity**, not length, so this does not
reliably panic — it returns a payload containing bytes beyond `len(data)`.

That is deliberate. It means a no-assertion "the runtime will catch panics" harness does
**not** kill this mutation, so the fixture exercises the distinction scorecard C2 draws: a
declared domain-constraint oracle must be explicitly asserted. `bad.md` fails exactly here.

## Why `bad.md` fails

Three independent reasons, all reported by the grader:

1. Declares fuzz mode `round-trip` for a decode-only parser (expected `parser robustness`).
2. One seed, below the `min_seeds: 3` bar in `meta.json` (scorecard S1).
3. `if len(data) > 2 { t.Skip() }` discards every input long enough to reach the defect, and
   the body asserts nothing — so it cannot kill the mutation.

## Running it

```bash
python3 -m unittest discover -s skills/fuzzing-test/scripts/tests -p 'test_*.py' -v
```

`GraderSelfTest` runs in CI and needs the `go` toolchain; it skips cleanly without it.

## Live model eval (opt-in)

`LiveSkillEval` drives a real model through `SKILL.md` and grades the output with the same
grader. It is skipped unless configured:

```bash
export FUZZING_TEST_SKILL_EVAL_CMD='your-model-cli --stdin'
python3 -m unittest discover -s skills/fuzzing-test/scripts/tests -p 'test_*.py' -v
```

The command must read a prompt on stdin and write the response to stdout.

Honesty boundary: the self-test proves the **grader** discriminates good from bad. It does
not prove a live model passes — only the opt-in live hook does that.

## Harness constraint

The emitted harness is compiled as `package eval` with only `testing` imported. A response
whose harness needs additional imports will not compile here. Template A needs none; this
fixture is scoped to Template A scenarios on purpose.

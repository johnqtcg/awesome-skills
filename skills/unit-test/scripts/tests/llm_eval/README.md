# LLM / skill-output eval harness

This grades an actual **skill-driven model response**, not the skill document.

## What runs in CI (no model needed)

`test_llm_skill_eval.py` ships a `grade(output, fixture)` function and a
`GraderSelfTest` that proves the grader discriminates: it must PASS `good.md`
and FAIL `bad.md`. The grader scores four dimensions:

1. **Mode** — the response declares the expected `Light/Standard/Strict`.
2. **Hypotheses** — real defect hypotheses (keyword coverage).
3. **Killer cases** — the emitted Go test **compiles**, PASSES on the correct
   source, and FAILS on **every hypothesis's mutation** (it actually kills each
   named defect).
4. **Contract** — a scorecard, the report markers `meta.json` requires (the
   killer case's `Kill: Verified|Unverified` status), and a JSON summary that
   **parses**, carries the required fields **with the required types**, holds
   values in range, and is internally consistent.
5. **Report vs. code** — the claimed case count equals the cases `go test -v`
   ran, and every hypothesis the fixture declares has a case that reached a
   **verdict** (a `t.Skip()`ped case is discovered, not verified).

Dimensions 1, 2 and 4 need no toolchain. Dimension 3 needs `go` and skips cleanly
without it.

### Three outcomes, not two (why a broken response is not a skip)

Running an emitted test yields `PASSED`, `FAILED`, or `NO_RUN` — and the grader
reads `NO_RUN` differently on each side:

- **on the correct source** — the response's own Go code did not build (or declared
  no test function). For a test-generation skill that is the headline failure, so it
  is graded as one. It is *not* an environment problem: `preflight()` has already
  built a trivial known-good program in this environment.
- **on the mutated source** — the mutation broke the build, so nothing was
  demonstrated. Reported as an **invalid mutation**; a kill is never credited.

Only a genuine environment fault skips: no `go`, no writable temp dir, an
unresolvable module download, or an exit carrying neither a compiler diagnostic nor
a test result.

### JSON summary checks

The fence is not the contract, and neither is `json.loads`. `grade_json_summary`
validates in three stages, in this order:

1. **Types**, from `meta.json`'s `json_field_types` — which is also the
   required-field list, so there is one list rather than two that must agree.
   `int` rejects `true`, because `bool` is an `int` subclass in Python.
2. **Ranges** — tier totals must match the scorecard's tier sizes, `*_pass` must
   lie in `0..total`, percentages in `0..100`, `cases >= 1`.
3. **Consistency**, now unconditional — the score vs. the tier counts, `pass` vs.
   the tier rule, `met` vs. `line_pct`/`gate`, `clean` implies `executed`, and the
   prose verdict vs. the JSON one. Plus the cross-pillar link: a **measured**
   coverage miss is a Critical FAIL, so it cannot coexist with a full Critical tier
   or an overall PASS.

The ordering is the point. Stages 2 and 3 used to be guarded by `isinstance` tests,
so a wrong type silently disabled them: `"critical_pass": "three"` graded clean.

Tier minimums and tier sizes are read from `references/boundary-scorecard.md`, so the
grader keeps no second copy of a documented threshold.

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

**`hypotheses` is the centre of the fixture.** One entry per hypothesis, each carrying
everything needed to decide whether it is really covered:

```json
{
  "id": "H2",
  "description": "nil/empty input yields an empty but NON-NIL result",
  "keywords": ["non-nil", "empty"],
  "min_keywords": 2,
  "case_pattern": "(?i)nil|empty|zero|no_?item",
  "contract_evidence": "always non-nil",
  "mutation": {"find": "out := make([]string, 0, len(items))",
               "replace": "var out []string"}
}
```

`contract_evidence` must match `sut.go`. It points the other way from the mutation: the
mutation proves the hypothesis is *verified*, the evidence proves it is *legitimate* —
that the code under test actually promises the behaviour being asserted, rather than the
fixture inventing a requirement. `validate_fixture` runs both checks before any response
is graded, so an ungrounded hypothesis is a fixture defect, not a passing grade.

These used to be three parallel lists (`hypothesis_keywords`, `required_case_patterns`,
`mutation`) — which could disagree, and did: H2 appeared in two of the three and owned
no mutation, so the behaviour it promised was never verified. One entry per hypothesis
makes that structurally impossible.

Rules for each `mutation`:

- it must be a **behavioral** change that still compiles — a mutation that breaks the
  build proves nothing and is reported as a fixture defect;
- it must violate *its own* hypothesis, so that killing it is evidence for that
  hypothesis specifically;
- `good.md` must pass the grader and `bad.md` must fail it, for the reasons you intend.
  An exemplar that cannot pass its own grader is not an exemplar.

And one rule for `good.md` that no automated check can fully enforce: **every claim
in it must be true of the code it ships.** Its history is the argument:

- it claimed 5 cases and two hypotheses covered while shipping a single 3-element input;
- it asserted that removing its length assertion would let the bug escape — false, the
  identity assertion still caught it;
- it promised an "empty but non-nil" result and asserted only length and elements, so
  `var out []string` satisfied every assertion.

Each of those made over-claiming the passing standard, which is worse than shipping no
exemplar. Quote real command output rather than plausible output: the failure lines in
`good.md` point at the `assertIDs(...)` call site, not at the assertion, because
`t.Helper()` reattributes them — a detail no amount of care would have guessed right.
The count, verdict and per-hypothesis mutation checks catch the crudest version of this;
the rest is on the author.

## Honesty

The CI self-test proves the **grader** works. It does not prove a live model
passes — only the opt-in live run does. This is the current boundary between
"methodology validated" and "skill behavior validated".
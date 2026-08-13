# Forward behavioural evaluation — recorded results

Latest run: **2026-08-13**, `claude -p --model haiku --max-turns 10`, **9 fixtures x 2 arms**
(18 calls, ~14 min), including two fixtures written specifically to be hard. Raw arms are retained in `run-2026-08-13/`, so `--grade` re-scores
them without spending a single model call — which is how a bad grader was caught and re-run
for free. Reproduce with:

```bash
python3 scripts/eval_forward.py --run --model haiku --max-turns 10 --out eval_out
python3 scripts/eval_forward.py --grade eval_out     # re-grade without re-running the model
```

## Result

```
PASS — skill improved: requires_runbook, names_valid_events; no regressions
```

## The hard fixtures, and what they showed

MON-015 and MON-016 were built after the previous run found 7 of 8 criteria tying. They target
what the base model gets *wrong* rather than what it already knows:

- **MON-015** asks about a `up == 0` alert and **withholds the replica count**. The previous
  attempt (MON-014) stated `"replicas": "6 behind a load balancer"` in the context, which handed
  over the deciding fact.
- **MON-016** asks for a latency SLO, which the base model reliably answers with
  `histogram_quantile`.

Result: **one new discriminating win.** On MON-016 the with-skill arm named the valid-event
exclusions (health checks, `/metrics`, client cancellations); the without-skill arm never
defined valid events at all. That is the skill supplying something the model does not have.

The other new criteria tied — and the tie is informative in both cases. On MON-015 **both** arms
handled the unstated topology well: they named the missing fact, gave the conditional, and split
the rule into an all-down `critical` plus a partial-outage `warning`. On MON-016 both arms got
the bucket-ratio SLI. Those are behaviours the base model has; the skill's contribution there is
consistency and completeness, which a binary criterion cannot see.

| fixture | criterion | with | without | verdict |
|---|---|---|---|---|
| MON-001 | names_sli | ✓ | ✓ | tie |
| MON-001 | requires_runbook | ✓ | ✗ | **skill wins** |
| MON-002 | requires_runbook | ✓ | ✓ | tie |
| MON-002 | no_absolute_counter | ✓ | ✓ | tie |
| MON-004 | for_duration_reasoning | ✓ | ✓ | tie |
| MON-005 | requires_runbook | ✓ | ✗ | **skill wins** |
| MON-007 | burn_rate_arithmetic | ✓ | ✓ | tie |
| MON-007 | states_budget_basis | ✓ | ✓ | tie |
| MON-007 | no_vendor_rule | ✓ | ✓ | tie |
| MON-013 | burn_rate_arithmetic | ✓ | ✓ | tie |
| MON-013 | states_budget_basis | ✗ | ✗ | tie |
| MON-014 | up_zero_not_auto_critical | ✓ | ✓ | tie |
| MON-014 | for_duration_reasoning | ✓ | ✓ | tie |
| MON-014 | empty_vector_safe | ✓ | ✓ | tie |
| MON-015 | asks_when_topology_unknown | ✓ | ✓ | tie |
| MON-015 | for_duration_reasoning | ✓ | ✓ | tie |
| MON-015 | empty_vector_safe | ✓ | ✓ | tie |
| MON-016 | latency_sli_is_a_ratio | ✓ | ✓ | tie |
| MON-016 | **names_valid_events** | ✓ | ✗ | **skill wins** |

## What this actually shows — read it narrowly

**One criterion discriminates**: `requires_runbook`. Without the skill the model omitted the
runbook link on two fixtures; with it, never. That is a real, reproducible improvement.

**Ten of twelve criteria are UNINFORMATIVE** — both arms pass. That is not evidence the skill
works; it is evidence those criteria are too easy for the base model, which already gets
burn-rate arithmetic, `for`-duration reasoning and counter-vs-rate right unprompted. Sample
size (7 fixtures, 1 run, haiku) is small; treat the single win as directional, not a gate.

**`up_zero_not_auto_critical` became uninformative because I wrote the fixture too easy.**
It was added specifically to catch the behaviour a reviewer observed: an agent explaining that
`up` is telemetry and then paging on a single-replica `up == 0`. Both arms pass it — because
MON-014's `context` states `"replicas": "6 behind a load balancer"`, which hands the model the
answer. The observed failure happened in a scenario that did *not* supply the replica count.
The harder, discriminating version of this fixture omits it and requires the agent either to
**ask** or to reason conditionally ("ticket if other replicas are healthy; page if this is the
last one"). A criterion whose fixture states the deciding fact measures reading comprehension,
not judgement.

That is the general lesson for the next iteration: write the criteria — and the fixture
*context* — against what the base model gets **wrong**. Candidates the base model does not
reliably produce unprompted: valid/good event definitions, per-window recording rules,
request-vs-time budget basis, and paging judgement when redundancy is *not* stated.

**One genuine miss, both arms**: MON-013 quoted `Remaining budget = 0.67 minutes/day` with no
basis label. The skill's "say which basis" rule did not reach the model in a *workflow*
scenario even with the skill loaded. That is a real gap in the skill, not a grader artifact —
still open, and the most concrete follow-up this run produced.

Note this run predates two fixture corrections it does not reflect: MON-013's premise was
`6x for 8h consumed 66%` (a 10x arithmetic error, now `60x for 8h = 66.7%`), and its
recommendation was "page at 5% remaining" (now a ticket plus a deploy freeze, because a low
budget with no active burn is a policy state, not an incident). Both are enforced by `MA016`
and `MA019`. A re-run would exercise the corrected premises; the conclusions above about
criterion difficulty do not depend on them.

## A false NEGATIVE, on the very criterion added to be discriminating

`asks_when_topology_unknown` first reported failing in **both** arms — which reads as "the
skill's paging rule does not reach behaviour", a serious finding. It was wrong. The with-skill
answer said, verbatim:

> You haven't stated the deployment topology. If checkout has 6 replicas, firing `critical` on
> 1 down violates the severity contract.

and then split the rule into an all-down `critical` plus a partial-outage `warning`. Two
mistakes in my criterion: `"haven't stated"` was not among the ask-or-condition patterns, and
any `severity: critical` counted as a defect — including the one attached to the **all-down**
alert, where it is exactly right. Fixed by writing the patterns against the real answer and by
checking *what the critical is attached to*; that answer's phrasing is now a self-test case.

**Rule this has now cost three times: when a criterion fails in both arms, suspect the criterion
before the model.** Same instinct as "on a surviving mutation, suspect the mutation first". The
evidence string is what makes it checkable, and `--grade` being separate from `--run` is what
makes the re-check free — this correction cost zero model calls.

## A false REGRESSION the first grader produced

The first run reported `REGRESSION: states_budget_basis`. It was wrong. The criterion used a
±120-character window, matched `2-3min` from "LOW: 2–3min diagnosis delay per incident", and
found the word "budget" in a *different table row* 120 characters away. Cut to clause scope,
the verdict flipped to a tie — visible above.

Two things saved it: the criterion emits **evidence** alongside its verdict, so the bogus match
was inspectable; and `--grade` is separate from `--run`, so re-grading the recorded outputs
cost nothing. A grader that reports the skill made the model *worse*, on evidence like that,
is worse than no grader — that fixture is now a permanent case in `--self-test`.

## Operational notes

- `--max-turns` is mandatory. Without it the with-skill arm ran >35 minutes on the first
  fixture with no output, indistinguishable from a hang.
- `Not logged in` from a nested `claude -p` means a **sandbox**, not a login problem: the tool
  sandbox denies reads of `~/.claude/.credentials.json`. Run the eval unsandboxed.
- Per-call progress is flushed, so a slow arm is visible while it runs.

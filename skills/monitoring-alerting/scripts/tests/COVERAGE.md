# monitoring-alerting Skill — Test Coverage Matrix

## 1. Contract Tests (`test_skill_contract.py`)

| Test Class | Validates |
|------------|-----------|
| `TestFrontmatter` |  name; trigger keywords (Prometheus, Grafana, SLI, SLO, alert, burn-rate, PagerDuty, cardinality) |
| `TestMandatoryGates` |  Gate 1–4; service type + traffic; scope modes (review/design/audit); risk levels |
| `TestDepthSelection` |  Lite/Standard/Deep; force-Standard signals; reference loading |
| `TestDegradationModes` |  Full/Degraded/Minimal/Planning; never-guess-thresholds; traffic warning |
| `TestDesignChecklist` |  4 subsections; SLI/SLO/error budget; burn-rate; actionable; for duration; runbook; cardinality; RED/USE |
| `TestAntiExamples` |  ≥6 AE; WRONG/RIGHT pairs; absolute-count AE; extended ref |
| `TestScorecard` |  Critical/Standard/Hygiene; thresholds; critical items (SLI, actionable, routing); verdict |
| `TestOutputContract` |  9 sections (§8.1–§8.9); uncovered risks; volume; scorecard |
| `TestReferenceFiles` |  3 files with min lines; keywords; AE numbering; alertmanager config keywords; all refs in SKILL.md |
| `TestAlertRoutingDesign` |  inhibition + suppress in checklist; severity→receiver mapping (critical→PagerDuty, warning→Slack) |
| `TestLineCount` |  SKILL.md ≤ 420 lines |
| `TestCrossFileConsistency` |  burn-rate in SLI/SLO ref; PromQL; p50 in anti-patterns; cardinality; runbook_url; group_by; inhibit_rules in alertmanager config; group_wait in alertmanager config |

## 2. Golden Fixtures (`test_golden_scenarios.py`)

### 2.1 Fixture Inventory

| ID | Title | Type | Severity | Violated Rule |
|----|-------|------|----------|---------------|
| MON-001 | No SLIs defined | defect | critical | SLIs defined and measured |
| MON-002 | Non-actionable alert | defect | critical | Every alert is actionable |
| MON-003 | Critical routed to Slack only | defect | critical | Severity labels match routing |
| MON-004 | No for duration — flapping | defect | standard | for duration set |
| MON-005 | Missing runbook link | defect | standard | Runbook link included |
| MON-006 | High-cardinality label | defect | standard | No high-cardinality labels |
| MON-007 | Well-formed SLO monitoring | good_practice | none | — |
| MON-008 | Good RED-method dashboard | good_practice | none | — |
| MON-009 | Degraded — no service context | degradation_scenario | none | — |
| MON-010 | Greenfield monitoring design | workflow | none | — |
| MON-011 | No alert grouping | defect | standard | Grouping/deduplication configured |
| MON-012 | No inhibition rules — alert cascade | defect | standard | Inhibition rules prevent alert cascade |
| MON-013 | SLO error budget exhaustion response | workflow | none | — |
| MON-014 | Single-replica `up == 0` labelled critical | defect | standard | Page-worthiness from user impact and redundancy |
| MON-015 | `up == 0`, topology **withheld** — must ask or condition | degradation_scenario | none | — |
| MON-016 | Latency SLO requested — must be a ratio, not a percentile | degradation_scenario | none | — |

Per-fixture assertion classes exist for every fixture id above (`TestMON001` … `TestMON014`);
`test_golden_scenarios.py` fails if one is missing its class.

### 2.2 Per-Fixture Test Classes

| Fixture | Test Class | Validates |
|---------|-----------|-----------|
| MON-001 | `TestMON001` | type/severity; violated_rule (SLI); feedback mentions SLI + availability/latency |
| MON-002 | `TestMON002` | type/severity; violated_rule (actionable); feedback mentions runbook/action |
| MON-003 | `TestMON003` | type/severity; violated_rule (severity/routing); feedback mentions PagerDuty |
| MON-004 | `TestMON004` | type/severity; violated_rule (for/flapping/duration); feedback mentions for: |
| MON-005 | `TestMON005` | type/severity; violated_rule (runbook); feedback mentions runbook |
| MON-006 | `TestMON006` | type/severity; violated_rule (cardinality); feedback mentions user_id |
| MON-007 | `TestMON007` | type/severity; no violations; mentions burn rate |
| MON-008 | `TestMON008` | type/severity; no violations; mentions RED |
| MON-009 | `TestMON009` | type/severity; forbids claims; mentions degraded |
| MON-010 | `TestMON010` | type/severity; mentions SLO/SLI; mentions routing |
| MON-011 | `TestMON011` | type/severity; violated_rule (grouping/deduplication); mentions group |
| MON-012 | `TestMON012` | type/severity; violated_rule (inhibition/cascade); feedback mentions inhibit_rules |
| MON-013 | `TestMON013` | type/severity; feedback mentions error budget; feedback mentions decision actions |
| MON-015 | `TestMON015` | context genuinely withholds the replica count; feedback expects asking OR a conditional and forbids defaulting to critical; keeps the `for` and `absent()` lessons |
| MON-016 | `TestMON016` | demands a proportion not a percentile, explains why a percentile has no countable bad event, requires one instrument + valid-event definition + the instrumentation prerequisite |
| MON-014 | `TestMON014` | type/severity; violated_rule is about page-worthiness; single replica downgraded WITH the redundancy reason; a real page path is relocated (all-replicas / synthetic probe / burn-rate) rather than removed; `up == 0` still gets `for` |

### 2.3 Fixture Integrity Tests

### 2.4 Semantic (non-keyword) assertions

Added 2026-08-12. Everything above this line asserts that a **word** is present, which is
green whether the surrounding claim is right or wrong. That is how a real domain error
shipped: MON-007 said a 14.4x burn rate "exhausted the budget in 2 hours" (the correct
figure is ~50 hours), and the test guarding it only checked that "burn" and "rate"
appeared. The fixture's `expected_feedback` is "No violations", so the wrong number *was*
the expected answer.

| Check | Case |
|---|---|
| Burn-rate multiplier is a canonical SRE tier (14.4 / 6 / 3 / 1) | `TestMON007` |
| Every "exhausts in T" claim equals `slo_window / burn_rate` | `TestMON007` |
| Every "N% of budget in W" claim equals `burn_rate x W / slo_window` | `TestMON007` |
| The arithmetic regexes actually match this fixture (negative control) | `TestMON007` |
| No vendor routing mapping stated as a universal requirement | `TestMON007` |

Refutation detection is delegated to `lint_monitoring_docs.claim_is_refuted` rather than
reimplemented, so the fixture can quote the wrong number in order to reject it without two
divergent notions of "is this being refuted".

## 2.5 YAML artifacts (`test_yaml_artifacts.py`)

| Check | Runs when |
|---|---|
| Every fenced `yaml` block parses | always |
| Alert rules carry `expr` | always |
| `promtool check rules` on every alert fragment | promtool installed |
| `amtool check-config` on every routing fragment | amtool installed |
| The runner reports how many external validators ran, and qualifies its verdict | always |
| COVERAGE.md states no hand-maintained test total | always |

## 2.50 Fixture numbers are checked, whatever the fixture type (closed 2026-08-13)

The worst defect this skill has had, and the gap that hid it. MON-013 stated **"6x burn for 8
hours consumed 66% of the monthly budget"**. The arithmetic is `6 × 8 / 720 = 6.67%` — off by
**10x** — and it is the *premise* of a workflow fixture, so "freeze deploys", "14.7 minutes
remaining" and "8-day recovery" were all conclusions drawn from a wrong state.

Two independent scope errors let it through:

1. The linter's own scope note claimed MA001 and MA002 both ran over golden fixtures. **Only
   MA002 did** — the percentage-consumed check was never wired up there.
2. MA013 (budget basis) gated on `type == "good_practice"`. MON-013 is a `workflow`, so it was
   skipped. A workflow fixture's numbers are just as authoritative as a model answer's.

Now: MA001, MA002, MA013 and the new **MA016** run over fixtures of **every type**. MA016 is
the specific check — when a scenario states a burn rate, a duration and a consumed percentage,
the three must be arithmetically consistent. The corrected fixture is 60x for 8h = 66.7%,
leaving 14.4 min, and it now carries a "sanity-check the premise" note because *acting on a
plausible-looking wrong number* is the failure mode being taught.

## 2.51 Golden snippets are validated like docs (closed 2026-08-13)

The gap that let MON-007 ship two defects: promtool and the YAML parser only ever saw
**markdown fenced blocks**, never the `code_snippet` of a fixture. So a `good_practice`
fixture — the thing held up as the model answer — could contain YAML that does not parse and
a "1h + 5m multi-window" claim implemented with 5m on both sides, and every check stayed green.

| Check | Case |
|---|---|
| Every `good_practice` snippet parses, and is a `groups:` mapping | `GoldenSnippetTests` |
| A "multi-window" claim uses ≥2 distinct ranges | `GoldenSnippetTests` |
| Every window the prose names appears in the expression | `GoldenSnippetTests` |
| `promtool check rules` over golden snippets | `GoldenPromtoolTests` |

All three shipped defects were re-fed as negative controls and are caught. The guards are
named explicitly in `test_lint_mutations.test_golden_defects_are_covered`, because a
parser-level guard has no linter rule id and would otherwise be invisible to the closure check.

## 2.52 Temporal behaviour, not just syntax (closed 2026-08-13)

`promtool test rules` now runs 5 cases against the skill's own burn-rate alert
(`tests/promtool/`). `check rules` proves the PromQL parses; only these prove it *behaves*:

| Case | What breaks it |
|---|---|
| Sustained 10% burn fires | threshold raised past reach |
| Clean traffic stays silent | — |
| 3-minute spike absorbed by the long window | — |
| Health-check traffic excluded from the event set | dropping the `path!~` exclusion |
| **Alert clears after recovery** | deleting the short-window clause |

The last case earns its place: a brief spike is silent whether the rule is single- or
multi-window, so case 3 cannot detect a deleted short-window gate. Only "burn stopped, must
stop paging" can. Five rule mutations verified — same-window-twice, dropped exclusion,
single-window, `for: 2m`→`2h`, unreachable threshold — all caught.

## 2.55 External validators — now executing

Closed 2026-08-12. Both binaries are installed and the suite runs them:

- `promtool check rules` over every alert fragment (`PromtoolTests`)
- `amtool check-config` over every routing fragment (`AmtoolTests`)

**It found real defects on the first run.** Five expressions used `...` as a placeholder
inside PromQL (`histogram_quantile(0.99, ...) > 0.5`), which parses as YAML and is rejected by
Prometheus — so a reader copying those rules got a file the server refuses. No text-level check
could have found that; only the parser knows. `promtool` was installed from the release tarball
rather than `go install`, because `prometheus/prometheus`'s `go.mod` carries `replace`
directives and `go install pkg@latest` refuses those.

## 2.6 Linter mutation sweep (`test_lint_mutations.py`)

Breaks each `lint_monitoring_docs.py` rule in a temp copy and requires the **named** rule
to fire — so a rule that looks reasonable and does nothing is caught. It earned its place
on the first run: the original MA006 checked `not re.search(r"rate\(", rule)` over the whole
rule, so a bare counter in the numerator passed as long as the denominator was rated.

Coverage is derived: rule IDs are parsed out of the linter's own docstring, so a new rule
without a mutation fails `test_every_rule_has_a_mutation` instead of reading as covered.


## 3. Coverage Summary

Per-category counts used to live here as a table (`Standard Defect Fixtures 5/5`, …). Deleted
rather than corrected: it drifted to `5/5` the moment MON-014 made it six, which is the third
time a hand-maintained count in this file has gone stale. Derive it instead:

```bash
python3 -c "
import json,glob,collections
c=collections.Counter(tuple(json.load(open(f))[k] for k in ('type','severity'))
                      for f in glob.glob('scripts/tests/golden/*.json'))
[print(f'  {t:22s} {sev:9s} {n}') for (t,sev),n in sorted(c.items())]"
```

### Test totals are deliberately not written here

A count in prose is a second copy of a fact, and nobody updates the copy. This file said
"Grand Total: 100 tests" while the suite had 107 — harmless in itself, but the same drift
that let "the L0 checklist has >= 12 items" outlive an 11-item list in a sibling skill. Get
the number from the source of truth instead:

```bash
python3 -m pytest scripts/tests -q --collect-only | tail -1
bash scripts/run_regression.sh          # also reports how many external validators ran
```

`test_coverage_doc_has_no_hand_maintained_totals` fails if a total is reintroduced.

## 2.54 Page-worthiness and the level-vs-burn distinction (closed 2026-08-13)

MON-013 recommended "page at 5% remaining". A low error budget with **no active burn** is a
policy state, not an incident: nobody is being harmed at that moment and waking someone cannot
restore budget. It should trigger the deploy freeze and the escalation path, not the pager.
Paging belongs on *active* burn — which is exactly what a multi-window alert's short window
proves. `MA019` enforces it: no fixture may recommend paging on a remaining-budget **level**
without naming an active-burn or hard-deadline justification.

The companion rule for signals rather than budgets lives in `alert-anti-patterns.md` §0.1:
page-worthiness comes from **replicas remaining** and **deadline headroom**, never from the
signal name. Both were prompted by observed behaviour, not by reading the docs.

## 2.53 The latency SLI event set (closed 2026-08-13)

`fast / valid` could exceed 1. The availability and bad recording rules excluded
`code!="499"`; the latency histogram bucket did not — so the numerator counted cancelled
requests the denominator had removed. Fixed three ways:

- the bucket carries the same exclusions, and the latency **denominator now comes from the
  same histogram** (`le="+Inf"`), not from the request counter — different instruments can
  drift even with identical selectors;
- the exclusion list is written **identically** in every rule of the family (`code!="499"`
  alongside `code=~"5.."` is redundant but makes the family diffable at a glance, and lets the
  linter demand exact equality instead of reasoning about regex implication);
- the **instrumentation prerequisite is stated**: many services expose duration histograms
  with no status label, in which case a valid-request latency SLI cannot be computed from them
  and saying so is the honest answer.

`MA017` enforces it: all `sli:*` rules in one block must share their exclusion set.

## 3.1 Semantic rules and what proves they work

`lint_monitoring_docs.py` carries a set of value/structure rules (ids are listed in its own
docstring — deliberately not counted here, for the reason §3 gives about prose counts; this
sentence said "12 rules (MA001–MA012)" after the set had grown to MA017). Every one has a
mutation in `test_lint_mutations.py` that requires the **named** rule to fire; coverage is
derived from the linter's own docstring, so a new rule without a mutation fails rather than
reading as covered.

Three of those rules exist because an earlier version of this very file failed open, which
is worth recording as a pattern rather than three separate anecdotes:

| Rule | How its first version failed open | Fix |
|---|---|---|
| MA017 | compared *all* label matchers, so `bad`'s classifying `code=~"5.."` looked like drift | compare only **exclusion** (`!=`, `!~`) matchers; classifiers legitimately differ |
| MA013 (fixtures) | gated on `good_practice`, so a `workflow` fixture's numbers were unexamined | applies to every fixture type |
| MA016 | matched any `%` within 40 chars of "burn", picking up the *error rate* in "60x for 8 hours (6% error rate)" | bind the `%` to "consumed … of budget" |
| MA018 | — | new: prose said the latency denominator uses `_count` **not** `le="+Inf"` while every recording rule above it used `le="+Inf"`. A reader following the prose writes what the file's own examples contradict |
| MA006 | `not re.search(r"rate\(", rule)` over the whole rule — a bare counter in the numerator passed while the denominator stayed rated | balanced-paren removal of `rate()`-family call *contents*, then look for what remains |
| MA010 | basis label searched in a ±260-char window, then in the whole header row — a neighbouring column's label vouched for an unlabelled one | per-**column**: the basis must be in that column's own header |
| Anti-example exemption | scoped to the whole fenced block, so a WRONG/RIGHT pair exempted the RIGHT half too — the corrected examples readers copy were the only alerts with no runbook enforcement | split on the `# WRONG` / `# RIGHT` markers and judge each half |

The shared shape: **a check whose scope is wider than its subject will be satisfied by
something other than its subject.** Mutation testing is what surfaces it; re-reading does not.

## 3.2 Forward evaluation (`scripts/eval_forward.py`)

Grades an answer against **named criteria** rather than similarity to `expected_feedback`,
because similarity measures phrasing and not correctness. Each criterion inspects values or
structure: is the burn-rate arithmetic right, is a minutes budget labelled with its basis, is
`up == 0` still given a `for`, is a vendor mapping asserted as a rule.

Two design points worth keeping:

- **A `without_skill` arm.** "The model already knew that" is the null hypothesis a skill has
  to beat. `--grade` reports the delta and labels a criterion both arms pass as
  **UNINFORMATIVE** rather than counting it as a win.
- **The self-test requires every criterion to be exercised in both directions.** A criterion
  never shown to *fail* is not a check. That meta-assertion caught `names_sli` shipping with
  only a passing case.

## 3.3 Behavioural eval — executed 2026-08-13

`scripts/eval_forward.py --run` now works; results and their honest reading are in
`tests/eval/RESULTS.md`. Two operational facts that cost a round each: `--max-turns` is
mandatory (an unbounded with-skill arm looks like a hang), and `Not logged in` from a nested
`claude -p` is the tool sandbox denying `~/.claude/.credentials.json`, not a login problem.

The first grader produced a **false REGRESSION** from a ±120-character window matching
`2-3min` in an unrelated table row. It is now clause-scoped, with that exact shape pinned as a
`--self-test` case. The bogus verdict was catchable only because criteria emit evidence and
`--grade` is separable from `--run`.

## 3.5 The empty-vector trap (closed 2026-08-13)

MON-014 recommended `count(up{job="x"} == 1) == 0` for "all replicas down". **Verified with
promtool that it is silent in exactly that case**: `up == 1` filters to an empty vector,
`count()` over empty returns *no result*, and `empty == 0` is empty. `sum(up) == 0` fires — but
is itself empty when the series vanish from discovery, which is what `absent()` covers. Correct
form needs both halves.

Three new promtool cases assert it (all-targets-down, series-absent, partial-outage), and the
broken form is asserted **empty** beside the working one via `promql_expr_test`, so the
difference is a regression rather than a claim in prose. `MA020` blocks the shape in docs,
fixtures **and** `tests/promtool/*.yml` — its first version scanned only docs and fixtures, so
reverting the executable rule file produced no finding.

## 3.4 Why `allowed-tools` stays in the frontmatter

A review suggested removing it on the grounds that the current skill-creator spec allows only
`name` and `description`. Checked rather than assumed, and it does not:

```
$ grep -n ALLOWED_PROPERTIES ~/.claude/skills/skill-creator/scripts/quick_validate.py
42:    ALLOWED_PROPERTIES = {'name', 'description', 'license', 'allowed-tools',
                            'metadata', 'compatibility'}
$ python3 ~/.claude/skills/skill-creator/scripts/quick_validate.py skills/monitoring-alerting
Skill is valid!
```

`name` and `description` are *required*; `allowed-tools` is among the permitted optional
properties. It is also load-bearing here — §5.5 instructs the reader to run `promtool` and
`amtool`, and `Bash(promtool*)` / `Bash(amtool*)` pre-approve exactly that.
`test_allowed_tools_declared` asserts it stays.

The same review suggested adding `agents/openai.yaml`. skill-creator's own `agents/` directory
holds markdown subagent definitions (`analyzer.md`, `comparator.md`, `grader.md`), and the string
`openai.yaml` appears nowhere in it. A sibling skill in this repo shipped a **dangling**
`agents/openai.yaml` index entry, which was removed as a defect and is now guarded against
reappearing. Not adopted.

## 4. Known Coverage Gaps

| Gap | Priority | Rationale |
|-----|----------|-----------|
| Log-based alerting (Loki/ELK) fixture | Low | Out of scope (Prometheus-focused); mentioned peripherally |
| Multi-cluster monitoring fixture | Low | Advanced pattern; not primary checklist |
| Synthetic monitoring / uptime check fixture | Low | External probing pattern; separate concern |
| **A discriminating behavioural eval** | **Medium** (the eval runs; it is not yet a gate) | `tests/eval/RESULTS.md` records a complete 7-fixture x 2-arm run (raw arms retained, re-gradable for free): **PASS, 1 win (`requires_runbook`), 0 regressions**, but **7 of 8 criteria UNINFORMATIVE**. Notably `up_zero_not_auto_critical` ties because MON-014's context *states* the replica count, handing the model the deciding fact — a fixture that supplies the answer measures reading comprehension, not judgement. Next iteration: write both criteria and fixture *context* against what the base model gets wrong |
| **The basis rule does not reach the model in workflow scenarios** | Medium | Both arms produced `Remaining budget = 0.67 minutes/day` unlabelled. A real skill gap surfaced by the eval, not a grader artifact, and still open. (The *fixture* defects that run also exposed — a 10x premise error and "page at 5% remaining" — are fixed and now enforced by `MA016` / `MA019`.) |
| PromQL *semantics* against real recorded data | Low | `promtool test rules` now ships for this skill's own alert (§2.52, 5 temporal cases) and covers fire / silent / recovery / exclusion behaviour on synthetic series. What remains uncovered is behaviour against *production-shaped* data — cardinality, gaps, staleness — which needs a real Prometheus. Superseded the earlier claim in this table that no unit tests were shipped |
# deep-research Skill Evaluation Report

> Evaluation date: 2026-09-08
> Evaluation target: `deep-research` at the current repository head
> Framework: [skill-creator](https://github.com/anthropics/skills/tree/main/skills/skill-creator), three dimensions per [`bestpractice/评估篇.md`](../bestpractice/评估篇.md) §10
> Scale: 60 nested `claude -p` runs (trigger) + 4 scenarios × 2 arms (task) = 68 real runs
> Raw evidence: [`outputexample/deep-research/ab-2026-09-08/three-dimension/`](../outputexample/deep-research/ab-2026-09-08/three-dimension/)

---

## Headline

**This skill is not being triggered when it should be, and that outweighs everything else in this report.**

Recall is **40%** against a 90% bar. Six of ten realistic should-trigger queries lost to the base model's own instincts — including every claim-verification query, every codebase-research query, and one vendor-claim verification where three consecutive runs used **no tools at all** and answered from memory. Those are the exact use cases the description enumerates. Precision is perfect (100%, zero false triggers on ten near-misses), so the description is not too broad — it is too quiet.

On task performance the two arms are indistinguishable: 20/22 assertions for the skill, 21/22 for the baseline, with 19 of 22 assertions passing in both. The skill's real output is 59 machine-validated, live-re-fetched excerpts — and **none of them appear in the report the user receives.**

Cost: 1.77× tokens, 3.87× tool calls, 3.49× wall time. The token cost breaks even against 10–19 seconds of engineer time, so it is not the constraint. The constraint is **+12 minutes of latency per run.**

---

## 1. 维度一 · Trigger accuracy

Twenty realistic queries (ten should-trigger, ten near-miss should-not-trigger), each run three times through a nested `claude -p` session where the skill is installed at `~/.claude/skills/deep-research` alongside the user's other 88 skills. A trigger is counted when the run invokes the skill by any path — the Skill tool naming it, or a Read of its SKILL.md.

| Metric | Value | Bar |
|---|:--:|:--:|
| Recall (query-level, ≥50% of reps) | **4/10 = 40%** | ≥90% ❌ |
| Recall (run-level) | 12/30 = 40% | — |
| Precision (query-level) | **10/10 = 100%** | ≥90% ✅ |
| Precision (run-level) | 30/30 = 100% | — |
| Overall accuracy | 14/20 = 70% | — |

### What triggers, and what does not

Every query that fired is framed as a **multi-option comparison or decision**:

| Query | Rate | Framing |
|---|:--:|---|
| Stripe vs Adyen comparison for the board | 3/3 | choosing between two named options |
| OpenTelemetry vs current stack, for a director | 3/3 | building the case for a decision |
| Kafka exactly-once "with receipts", for a design doc | 3/3 | traceability stated, no option list |
| 服务网格采用趋势调研（istio vs cilium） | 2/3 | Chinese trend + traceability |

Every failure falls into one of three classes, and in each the model reached for a generic tool instead:

| Query | Rate | Went to instead |
|---|:--:|---|
| Refute a colleague's `t.Setenv` + `t.Parallel` claim | 0/3 | `ToolSearch` → `WebSearch` |
| Two MySQL manual pages contradict each other | 0/3 | `ToolSearch` → `WebSearch` |
| Verify a vendor's uptime and p99 claims before signing | 0/3 | **no tools at all** — answered from memory |
| Work out how an inherited repo's retry logic works | 0/3 | `Bash` |
| Check `internal/server/tls.go` against NIST for an audit | 0/3 | `Bash` / `Read` |
| Which yaml-lib versions a CVE affects | 1/3 | `Bash` |

The description lists "claim verification", "pure codebase research" and "hybrid codebase-plus-web investigations". It loses on all three. The vendor-claim query is the worst case: unverified confident recall is precisely the failure this skill exists to prevent, and the skill was never consulted.

### Recommended description changes

The evidence points at four concrete gaps, not a general rewrite:

1. **Verification framing.** Add trigger language for "verify / fact-check / is it true that / before I push back / the docs contradict each other", plus Chinese equivalents (核实 / 求证 / 查证 / 文档互相矛盾).
2. **Local investigation framing.** "Figure out how X works in this repo", "which functions do Y", "cite the files and lines" currently read as ordinary file work. Say otherwise explicitly.
3. **Stakes language.** All four winners carried consequence — "for the board", "he will ask where this came from", "going into a design doc". Name that pattern: audits, runbooks, contract decisions, PR disputes.
4. **A push clause.** skill-creator's own guidance is that Claude under-triggers skills and descriptions should be "a little bit pushy". This description is a flat enumeration of capabilities with no push at all.

`scripts/run_loop.py` automates exactly this loop against the eval set, committed at `three-dimension/trigger_eval_set.json`.

---

## 2. 维度二 · Task performance

Four scenarios on a simple → edge gradient, chosen per §10.3's guidance that the differentiating investment belongs in the hard cases. Both arms ran as independent subagents with live web access, the same prompt and the same tools; the with-skill arm was pointed at `SKILL.md` and followed it.

| # | Scenario | Difficulty | Why chosen |
|---|---|---|---|
| 0 | Does `govulncheck` emit CVSS scores? | simple | a general model handles this; baseline check |
| 1 | PostgreSQL logical replication vs Debezium | medium | comparison whose provenance will be challenged |
| 2 | Two MySQL manual pages contradict on INSTANT DDL's metadata lock | **edge** | does the output surface the conflict or silently pick a side? |
| 3 | % of Fortune 500 running Kafka in production, 2026 | **edge** | no authoritative source exists — does the output admit it? |

### Assertion benchmark

| Metric | With Skill | Without Skill | Delta |
|---|:--:|:--:|:--:|
| Assertion pass rate | 20/22 = **91.7%** | 21/22 = **95.8%** | **−0.04** |
| Per-eval (0/1/2/3) | 5/5, 4/6, 6/6, 5/5 | 5/5, 5/6, 6/6, 5/5 | |

**Nineteen of twenty-two assertions passed in both arms.** Exactly one discriminated, and it favoured the baseline: the eval-1 with-skill report contains no verbatim quotation at all, only paraphrase with `[n]` markers.

A non-discriminating assertion set is a finding about the assertions as much as about the skill: on this scenario set, the properties I could state objectively are properties a competent general model already delivers.

### The two arms deliver evidence in different, non-overlapping ways

This is the real result, and the assertion count hides it.

| Measure | Without Skill | With Skill |
|---|:--:|:--:|
| Machine-validated excerpts (re-fetched and matched) | — | **59, all 59 live-verified** |
| Verbatim quotes **in the delivered report** | **55 spans, 9 independently confirmed** | 7 spans, 5 confirmed |
| Numbered per-claim citation markers | 0 | **78** |
| Per-claim confidence labels | 2 | **20** |
| Explicit gap / limitation statements | 2 | **10** |

The skill gives you a claim→source map with calibrated confidence and named gaps. The baseline gives you the source's actual words. Both are traceability; neither substitutes for the other.

**The most actionable defect in this report follows directly from that table: the skill validates 59 excerpts against live pages and then discards every one of them when rendering the report.** They survive only in `findings.json`. A reader who wants to check a claim must be handed the JSON artifacts. Rendering each finding's validated excerpt beneath it would combine both arms' strengths at no research cost — the work is already done and thrown away.

*(No fidelity **rate** is claimed for the baseline. My extractor collects any quoted span, including emphasis and quotations of the user's own question, so its 55-span denominator is not a set of source citations. The 9 and 5 confirmed counts are positive findings; the unconfirmed remainder is not evidence of fabrication.)*

### Where the skill genuinely won

Scenario 2 is the one case where the skill arm out-researched the baseline, decisively. The baseline resolved the apparent contradiction correctly by distinguishing lock **mode** from lock **duration** — a good answer. The skill arm went further and found *why the user saw a contradiction at all*: Wayback Machine snapshots, live-verified during the run, show the same URLs said "No metadata locks are taken on the table" as recently as April 2021, and MySQL Bug #106480 records Oracle confirming a documentation defect fixed on 2022-05-13. It also disclosed that `dev.mysql.com` and `bugs.mysql.com` returned 403 to the bundled fetcher, so current-state evidence came from Oracle's mirror and confidence was capped at Medium.

That is the shape of this skill's value: not a better answer, but a defensible one with its own weaknesses on the record.

Scenario 3 went the other way. Both arms correctly refused to supply a Fortune 500 percentage. The **baseline** additionally located Confluent's 2021 S-1, which discloses an auditable 136 of the Fortune 500 as paying customers, and identified IBM's page as citation drift from Confluent's "Fortune 100" line. The skill arm surfaced neither.

### Process observations

All four with-skill runs executed the bundled pipeline — `plan`, `retrieve`, `fetch-content`, `validate`, `report --live-web` — and all four performed live verification (10, 3, 11 and 4 verifications).

Two process defects appeared in every run:

1. **Ledger proliferation.** Every run created a second session ledger. In three, the agent re-planned to a larger mode and, because `plan` refuses to overwrite an existing ledger, had to write a new file — leaving the first unused. In scenario 3 the `quick` ledger was spent to exactly its 5/5 ceiling and the run continued under a fresh `standard` ledger. **A new ledger routes around the cumulative ceiling the ledger exists to enforce,** and no single ledger represents a session's real total.
2. **Authority registry coverage.** Every source in the eval-1 report rendered as `website (preclassified T4) — basis: heuristic:unverified-domain`, including `debezium.io`, `docs.confluent.io` and `dev.mysql.com`. The registry added in the previous hardening pass covers standards bodies and major language projects but misses the ordinary vendor-documentation domains real research lands on, so confidence is capped for reasons unrelated to the evidence.

A third defect came from the runs' own reports: **DuckDuckGo Lite returns JS-redirect wrapper URLs that the bundled `fetch-content` cannot follow.** One agent had to decode the `uddg` parameter by hand to obtain real target URLs. The bundled retrieval path is effectively unusable in this environment without that manual step.

---

## 3. 维度三 · Token cost-effectiveness

### Input overhead

| Component | Tokens |
|---|--:|
| `SKILL.md` | 6,627 |
| + two typical reference files | ~10,900 |
| all five reference files | 17,253 |

### Measured cost per run

| Metric | Without Skill | With Skill | Multiple |
|---|--:|--:|:--:|
| Total tokens | 143,127 | 253,518 | **1.77×** |
| Tool calls | 21.0 | 81.2 | **3.87×** |
| Wall seconds | 288.6 | 1,006.4 | **3.49×** |

Per-scenario token multiples were stable at 1.61× / 1.72× / 2.00× / 1.68×; wall-clock multiples ranged 2.7×–4.6×.

### Cost and break-even

The subagent accounting reports one token total per run rather than an input/output split, so the dollar figure is a band across plausible output shares rather than a single invented number.

| Output share assumed | Baseline | With Skill | Delta |
|---|--:|--:|--:|
| 5% | $0.515 | $0.913 | **+$0.397** |
| 15% | $0.687 | $1.217 | **+$0.530** |

At $100–150/hour that delta is repaid by **0.16–0.32 minutes — ten to nineteen seconds — of engineer time.**

So the token question is settled: the cost is trivial against any plausible benefit. **The binding cost is latency: +718 seconds, twelve minutes, per run,** paid by the person waiting. Scenario 2 took the skill arm 26.6 minutes against the baseline's 10.

No ROI multiple is quoted. A large ratio computed from a ten-second break-even would be arithmetically true and rhetorically misleading — it would invite trust in a number whose denominator is negligible, while the real cost sits in a term the ratio does not contain.

---

## 4. Verdict

| Dimension | Weight | Score | Weighted | Basis |
|---|:--:|:--:|:--:|---|
| Trigger accuracy | 35% | 3.5/10 | 1.23 | Recall 40% against a 90% bar; Precision 100%. A skill that does not fire has no other value. |
| Task performance | 35% | 5.5/10 | 1.93 | 20/22 vs 21/22; 19 of 22 assertions non-discriminating; one clear win (scenario 2), one clear loss (scenario 3); validated excerpts discarded before delivery |
| Token cost-effectiveness | 30% | 7.0/10 | 2.10 | Token delta repaid by ~15 seconds of engineer time; +12 min latency is the real cost |
| **Weighted total** | | | **5.26/10** |

Trigger accuracy carries the heaviest weight because it gates everything else: on this evidence, six times in ten the rest of this report does not apply, because the skill is never consulted.

**Where this skill earns its cost:** work whose conclusions will be audited or disputed — a migration runbook, a security decision, a comparison a director will interrogate. Scenario 2 shows what that looks like: the answer, its provenance, the version history that explains the confusion, and an honest note that the primary domain blocked the fetcher.

**Where it does not:** anything not framed as a decision between named options — which, per dimension 1, is also most of what it will never be invited to.

### Priority of fixes

1. **Fix the description** (dimension 1). Nothing else here matters at 40% recall. Run `scripts/run_loop.py` against the committed eval set.
2. **Render validated excerpts in the report.** Fifty-nine live-verified excerpts are produced and discarded. A rendering change, not a research change.
3. **Extend the authority registry** to ordinary vendor-documentation domains, or stop capping confidence on registry absence alone.
4. **Fix the retrieval path** — decode DDG's `uddg` wrappers inside `retrieve` so `fetch-content` receives real URLs.
5. **Make re-planning first-class** so an agent can widen its mode without abandoning its ledger, and treat a second ledger for the same task as budget exhaustion rather than a fresh allowance.

---

## 5. Limitations — read before quoting any number above

1. **Task performance is n=1 per cell.** Four scenarios × two arms, one run each. The trigger dimension has three repetitions per query; the task dimension has none. No variance is reported for the task dimension because none was measured — and `benchmark.md`'s header saying "3 runs each per configuration" is an aggregator default, not what happened.
2. **The baseline is not a naked model.** Both arms ran as subagents inside this repository, so both inherited a `CLAUDE.md` that already demands "Verification Before Done" and "No Laziness: find root causes". The baseline is a model already instructed toward evidence discipline. A naked-model baseline would very likely score lower, and the honest reading of "no task-performance delta" is "no delta against an already-rigorous baseline".
3. **The assertion set barely discriminates.** 19 of 22 assertions passed in both arms. Assertions that separate these arms would have to test the auditability apparatus directly, which edges toward testing "did it use the skill".
4. **My own measurement pipeline was wrong three times.** Each was caught and corrected; each is recorded because an evaluation that hides its own errors is not evidence.
   - I read session ledgers while runs were still executing and concluded live verification never happened. It did — 10, 3, 11 and 4 times. Retracted.
   - The quote extractor read only double-quoted spans, so it scored the skill's best-quoting run as having none. Fixed; that run turned out to have the highest verified rate of any run (4 of 6).
   - The extractor over-collects emphasis and self-quotation, so the baseline's 55-span count is not a citation count and no fidelity rate can be derived from it.
5. **Single model, single day, live web.** Sonnet, 2026-09-08. `dev.mysql.com` 403s and DDG wrapper URLs are environment facts that may not reproduce.
6. **Trigger results are environment-specific.** 88 skills were advertised in every trigger run. Recall in a session with fewer competitors would likely be higher; this measures a heavily-populated real environment.
7. **Scenario coverage.** Four web-research scenarios. Nothing here measures pure codebase research or the test-receipt path, both of which the skill supports and neither of which was exercised.

---

## 6. Reproducing this

```bash
cd outputexample/deep-research/ab-2026-09-08/three-dimension
cat trigger_metrics.txt          # dimension 1 result
cat trigger_eval_set.json        # the 20 queries, with why each was chosen
cat benchmark.md                 # dimension 2 aggregate
cat grading_summary.json         # per-assertion grades, incl. the checker correction
cat timing_summary.json          # dimension 3 raw cost data
cat ledger_analysis.json         # the session-ledger finding
ls answers/                      # all 8 delivered answers
open eval_review.html            # skill-creator eval viewer: outputs + benchmark tabs
```

`trigger_run.py` is the trigger harness; its docstring records the two deliberate changes made to skill-creator's `run_eval.py` for a skill that is already installed. `verify_quotes.py` is the mechanical quote checker, applied identically to both arms.

---

## 7. Previous evaluations — superseded

| Date | Method | Score | Why superseded |
|---|---|:--:|---|
| 2026-03-12 | 3 scenarios × 2 configs, 27 assertions | 8.80/10 | Evaluated a 7-section snapshot that no longer exists; the baseline was never asked to produce the format it was scored on; evidence lived in `/tmp` and is gone. |
| 2026-09-08 (earlier the same day) | 9 fixtures × 2 arms × 2 reps, 36 runs | 6.26/10 | Injected `SKILL.md` into the system prompt, which **bypasses triggering entirely** — the dimension that turns out to dominate. It also forced both arms into a fixed `url ||| excerpt` output shape, which told the baseline what to produce and inflated the measured token gap to 6.8× against this evaluation's 1.77×. Its citation-fidelity work and the three truncation defects it exposed remain valid, and its data is retained as `results-before-fix.json` / `results.json`. |

All three evaluations agree on the shape of the result: **this skill's value is auditability discipline, not research ability.** This one adds the finding that the discipline is usually never invoked.

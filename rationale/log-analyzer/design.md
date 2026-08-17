---
title: log-analyzer skill design rationale
owner: awesome-skills maintainers
status: active
last_updated: 2026-07-10
applicable_versions: current repository version
---

# log-analyzer Skill Design Rationale

`log-analyzer` is a log-analysis framework for incident investigation. Its core idea is: **the goal of good log analysis is not to hand you a pile of filtered log lines, but to produce an evidence-backed, reproducible, refutable investigative conclusion — first detect the log format, redact PII, and lock the time window, then use statistics to separate signal from noise, walk `trace_id` to reconstruct the failed request, always distinguish "the first error in time" from "the real root cause," and finally rank findings by severity and hand them over together with a statement of what this analysis did not cover.** That is why the skill turns seven gates — Format Detection, PII Redaction, Time Window, Statistical Significance, Correlation, Causation Discipline, Volume Cap — together with three intensity modes (Lite / Standard / Strict), on-demand reference loading, evidence rules, an anti-pattern catalog, and a hand-off protocol, into one fixed workflow. Its positioning is deliberate: it is the **upstream** half of incident response, producing an evidence package that `incident-postmortem` turns into a formal blameless RCA.

## 1. Definition

`log-analyzer` is used to:

- Investigate incidents from logs, triage error spikes, and extract timelines
- Correlate across services with `trace_id` / `request_id` to reconstruct a failed request
- Separate signal from noise, without being spooked by normal error levels
- Handle many log formats: plain text, JSON (`slog` / `zap`), syslog, journald, container, and Kubernetes logs
- Hand its evidence package to `incident-postmortem` when a formal post-mortem is needed

Its output is not a filtered log excerpt but a fixed-structure evidence package:

- Analysis mode (Lite / Standard / Strict) with rationale
- Time window, source, whether coverage is full, and the detected format
- Executive summary (leading with the answer to the user's real question, and an origin breakdown of "confirmed / hypothesis / needs corroboration")
- Tiered findings (each with an ID, confidence, category, location, redacted evidence, inference, causation chain, refuter, recommendation)
- Timeline, correlation map, root-cause hypotheses, recommendations
- Suppressed items, execution status, residual risk
- Hand-off protocol (structured fields for `incident-postmortem`)

By design it behaves more like a "log-investigation governance framework" than a prompt that `grep ERROR`s and pastes the result. The question it answers is "why does this conclusion hold, and what did I not see?", not merely "which errors are in the log?"

## 2. Background and Problem

What this skill solves is not "the model can't use `grep` and `jq`" — it is that, without a framework, log investigation slips easily into several "looks like investigating, conclusions aren't reliable" patterns.

The common failures cluster into roughly 8 types:

| Problem | Typical consequence |
|---------|---------------------|
| Treating the earliest ERROR as the root cause | The real cause usually lives in the 30 seconds before the first ERROR (a deploy, a config push, a pool-exhaustion warning) and gets skipped |
| Counting errors with no denominator | 87 errors out of 50M requests get called a "spike" when they are perfectly healthy background noise |
| Leaking secrets while quoting logs | The report pastes `Bearer eyJ…` verbatim — a second leak of the credential |
| Concluding from an unrepresentative slice | A 30-second slice from the middle of a 12-hour outage is used to declare its start and end |
| Listing errors without correlating | A thousand errors listed, but no single failed request walked end-to-end, so it's unclear which hop broke |
| Mistaking symptoms for the cause | One upstream failure triggers hundreds of downstream timeouts; the report counts the downstream ones and blames the wrong service |
| Silently dropping findings | A few conspicuous ones reported, the rest neither reported nor mentioned, so the team thinks the search was complete |
| Writing nothing when nothing is found | Behind "looks fine" there is no record of what was actually scanned or whether coverage was complete |

The design logic of `log-analyzer` is to first settle "what format is this, what is the window and coverage, is this number still significant against a denominator, is the earliest error actually the root cause, what does the failed request path look like, did I carry any secret out, which conclusions are only hypotheses" — and only then produce tiered findings and root-cause hypotheses.

## 3. Comparison With Common Alternatives

| Dimension | `log-analyzer` skill | Plain `grep` of the logs | Dumping the whole log to a model to summarize |
|-----------|----------------------|--------------------------|-----------------------------------------------|
| First error vs root cause | Strong (causation-chain discipline) | None | Weak (tends to pick the first one) |
| Signal vs noise | Strong (denominator required) | None | Weak |
| Cross-service correlation | Strong (walks the `trace_id` path) | Very hard | Weak |
| Cascade attribution | Strong (cause cluster vs symptom cluster) | None | Weak |
| Redact before quoting | Mandatory, hard gate | None | Usually ignored |
| Coverage / window honesty | Mandatory statement | None | Usually silent |
| Refutable conclusions | Every finding carries a refuter | None | Weak |
| Hand-off to a post-mortem | Structured hand-off protocol | None | Weak |

Its value is not "faster than `grep`," but lifting log investigation from "filter and guess" into an evidenced, refutable process that states its boundaries honestly and can hand straight off to a post-mortem.

## 4. Core Design Logic

### 4.1 Choose the analysis intensity first, then start

`log-analyzer` requires selecting `Lite / Standard / Strict` at step 0, defaulting to `Standard`. It explicitly rejects one mistake: running every investigation through the same heavy workflow.

The routing rules are hard: `Lite` only for a single service, a window ≤ 1 hour, < 100 MB, and no security / data-integrity / customer-impact signal; `Strict` whenever there is a SEV-1/2, a customer-visible outage, a suspected security event, data corruption, correlation across 3+ components, or a post-mortem deliverable; everything else is `Standard`. The finding soft cap scales with mode (5 / 10 / 15). So a simple "is anything on fire right now?" does not get written up as a heavy report, while a genuine major incident automatically gets investigation-grade depth.

### 4.2 Seven gates, four failure classes — skipping one is a "contract violation"

The skill's core architecture converts SRE judgment into seven gates: Format Detection, PII Redaction, Time Window, Statistical Significance, Correlation, Causation Discipline, Volume Cap. Each gate is mandatory and self-attested in Execution Status — but they are **not** uniform blockers, and an earlier revision of this document described them as "serial hard gates" where "failing any gate stops subsequent work". That was wrong in a way worth recording, because the gate texts themselves never behaved that way: only one of the seven can sensibly stop the analysis.

Each gate therefore declares its own failure class:

| Class | On failure | Gates |
|---|---|---|
| **BLOCK-EVIDENCE** | Withhold the specific item; the analysis continues | 2 (PII), per line |
| **BLOCK-WORKFLOW** | Stop; emit only the blockage and what would clear it | 2 (PII), whole source |
| **DEGRADE** | Proceed; the affected class of conclusion is withdrawn or downgraded | 1 (Format), 3 (Time), 4 (Statistics), 6 (Causation) |
| **WARN** | Proceed; the gate failure is itself an actionable finding | 5 (Correlation) |
| **CAP** | Proceed; output is bounded and overflow routed, never dropped | 7 (Volume) |

BLOCK needed splitting for the same reason the blanket rule did. A single label
covering both "do not quote this line" and "stop the report" is ambiguous exactly
when it matters, and the first draft of the fix had the table saying *stop the
workflow* while the gate body said *describe the line and continue*. Those are
different actions. Blocking is now scoped to the smallest unit that restores
safety: one unredactable line blocks that line, and only a source whose redaction
cannot be established at all blocks the report drawn from it.

The distinction is load-bearing. A blanket "stop everything" rule is either ignored (because stopping on a missing baseline would make the skill useless) or obeyed too literally (a partial time window suppresses findings that had nothing to do with time). Naming the class per gate makes the degradation *specified* rather than improvised: a missing statistical baseline withdraws trend language but leaves a security finding fully reportable.

The significance of the layer is unchanged: it does not leave "should I do the statistical check?" or "should I redact?" to gut feel. The skill even counts "drawing conclusions without loading the matching reference file" as a contract violation — the basis for a judgment must be a method that was loaded, not an impression.

### 4.3 "The first error in time" is not the root cause

This is the soul of the skill, the counterpart to unit-test's Defect-First. The Causation Discipline gate names the most common failure: `grep ERROR`, take the earliest hit, declare it the cause. Its hard rule: **the first error in time is not automatically the root cause.**

It requires building a causation chain for each leading hypothesis: symptom → proximate trigger → underlying cause → contributing factors, with every link backed by a redacted log line or a referenced metric; when the chain can't be closed from logs, it must be written as "Hypothesis — needs corroboration: `<source>`," not presented as confirmed. The operational counterpart is the workflow's "first-occurrence pivot": for each High-severity error class, find its **first** appearance in the window and capture the 30 lines of context before it — because the cause usually lives in that run-up, not on the first ERROR line. Golden fixture 001 pins this discipline: the real cause is a config push 30 seconds before the first ERROR.

### 4.4 Statistical significance: a count with no denominator means nothing

`log-analyzer` runs every "frequent" or "spike" claim through the statistics gate. The core sentence is: **an isolated count is meaningless — it needs a denominator.** It requires estimating the request / event base rate for the same window, comparing against an equal-length baseline window where possible, and preferring rate (`errors/sec`, `error_ratio = errors / total`) over absolute counts.

It gives ready-to-use heuristic anchors: `error_ratio` sustained ≥ 1% is a signal; < 0.01% in a high-traffic service is likely noise; ≥ 3× baseline for the same class is a spike; one occurrence in a million lines is almost certainly noise; but a new error class never seen in the baseline is always worth investigating, regardless of count. The reference calls out the "1-in-N-Million trap": 0.0002% of 50M requests looks scary as an absolute count, but the rate is healthy. Golden fixture 005 pins exactly this — 87 errors must be judged noise, possibly a No-Finding report, not a spike.

### 4.5 Correlation: reconstruct one failed request rather than listing a thousand errors

The correlation gate takes a clear stance: the single most valuable move in a multi-service investigation is walking **one** failed request end-to-end, not summarizing a thousand errors. The procedure extracts every correlation field from the first error sample, searches for that `trace_id` / `request_id` across all in-scope sources (services, sidecars, gateway, message queue), orders by timestamp, and annotates each hop with service, operation, status, latency, and the boundary crossed (HTTP / gRPC / Kafka / DB) — then condenses it into a compact correlation map rather than dumping raw JSON. Golden fixture 004 verifies this end-to-end walk.

A telling design choice: **if the logs have no correlation IDs at all, that is itself a High-severity Observability finding**, because debugging is fundamentally degraded without them. The skill also gives effort-ordered remediation: gateway-injected `request_id` → OpenTelemetry auto-instrumentation → context-bound structured-logger fields. Golden fixture 008 pins this.

### 4.6 Cascade analysis: distinguish the "cause cluster" from the "symptom cluster"

In a real outage the log is dominated by symptom clusters — one upstream failure triggering hundreds of downstream errors. Counting symptoms inflates severity and points at the wrong service. `log-analyzer` therefore distinguishes the cause cluster (errors at the failing component itself, usually small — 1–5 lines — with a specific error class like `pool exhausted`, `deadlock`, `disk full`) from the symptom cluster (errors in dependent components, usually large, with a convergent error class, and a rate proportional to traffic).

Its tests are practical: symptom clusters are tightly time-clustered, converge on a generic timeout / refused error, and grow with traffic; and looking at the **first 30 seconds** of error activity, the cause is almost always there. The reporting rule is the key design decision: report **one** cause finding plus a cascade summary, not N parallel findings. Golden fixture 003 pins it — 200+ `context deadline exceeded` lines across 5 services must collapse to a single DB-pool-exhaustion root cause. Fixture 009 is its twin: 12,000 apparent errors de-duplicate to 4,000 distinct `request_id`s, i.e. 3× retry amplification — count distinct requests, surface the ratio, recommend a circuit breaker.

### 4.7 Redact before quoting, and never after the fact

PII redaction is a hard gate, not advice: the report **must not** echo unredacted secrets back to the user. The skill provides an "always redact" list with fixed replacements: Bearer / JWT → `Bearer ***REDACTED***`, various API keys, passwords in URLs, emails, phone numbers, card numbers, government IDs, cookies / sessions, private keys, and more.

Two procedural decisions matter most: first, **decide the redaction set and redact before quoting — never write the report and retro-redact**, because that unredacted draft is itself a leak (chat history, autosaves, screen shares all retain it); second, **never redact `trace_id` / `request_id`** — they are not secrets and are the lifeblood of the analysis. JSON is redacted at the field level to preserve structure, text via layered regex substitutions, then 20 random lines are spot-checked for residual leaks.

The third decision was added after review: **the gate is enforced by a shipped, tested script (`scripts/redact_log.py`), not by recipes in prose.** The original reference offered a `jq` one-liner and a `sed` pipeline; neither had ever been executed. The `jq` recipe aborted with `Cannot index object with number` (its `sub()` replacement indexed the named-capture object, which is empty for unnamed captures), and the `sed` recipe emitted `alice[0:1]***@example.com` — jq slice syntax pasted into sed, where `[0:1]` is a literal character class. A hard gate whose only implementation does not run is not a gate, and the test suite could not tell, because it asserted the string `REDACTED` appeared in the documentation rather than executing anything. The script now carries the categories, preserves correlation IDs, is idempotent, and ships a `--verify` mode that exits non-zero on residue; its tests execute it and include the over-redaction cases (an ISO-8601 timestamp must not be eaten as a phone number; a Luhn-valid epoch-millisecond value under a `ts=` key must not be eaten as a card number).

If a secret is found already leaked, it is treated as compromised (rotation mandatory), reported as a High security finding — but **the finding states only the location and class, never quoting the secret itself**. Golden fixture 002 pins this Bearer redaction.

### 4.8 State the time window; if coverage is partial, don't conclude

Every report must state the analyzed window in absolute UTC, plus where the bounds came from (file, aggregator query, `kubectl` / `journalctl` args), and mark `Coverage: full / partial` — partial whenever log rotation, retention, sampling, or a paged-out query may have truncated the data. If the user provides only a snippet with no timestamps, it writes "Window: unknown" and stops all time-based conclusions. Golden fixture 007 verifies this: given an 80-line slice from mid-outage, mark coverage partial, refuse onset / recovery conclusions, and ask for more data via Open Questions.

This gate also surfaces a subtler trap — aggregator sampling. When Datadog says "5000 ERRORs" and ingest sampling is 10%, the real volume is ~50,000, and every rate must be scaled by the sampling rate. The skill requires recording the sampling rate in Execution Status and treating such numbers as items to reconcile, not confident claims (golden fixture 010).

### 4.9 Evidence rules and three-tier confidence: humility as a first-class output

Every finding must carry four things: an exact source location, a redacted 1–5 line sample, the inference drawn from it, and **what data would refute that inference** (the refuter). Confidence is labeled in three explicit tiers: Confirmed / Hypothesis / Hypothesis — needs corroboration; promoting a hypothesis to confirmed is a contract violation.

This layer makes epistemic humility a first-class output. The skill has a clear default: when in doubt, label confidence lower, not higher — because an unsourced confident report misroutes the rollback, the alert, and the post-mortem action items at the wrong target. It even allows and requires "the data is insufficient to conclude" to be a valid, stated conclusion.

### 4.10 Volume cap + residual risk: never silently drop a finding

Findings have a mode-based soft cap (5 / 10 / 15), but anything over the cap is moved to "Residual Risk / Investigation Gaps," not silently deleted. The rule has three phases: all High findings are always reported, never dropped by the cap; Medium fills the remaining slots ordered customer-impacting → debug-blocker → operational hygiene; Low only if slots remain; displaced items become one-line summaries in Residual Risk, with a note in the summary that "N additional issues moved to Residual Risk."

This pairs with the skill's Suppressed Items section: patterns that looked alarming but were judged noise / healthy retry / non-user-controlled are listed one per line with the reason they were suppressed. Together they guarantee that whether something was "not reported" or "suppressed," it is accounted for — no validated issue is silently dropped.

### 4.11 Even with no findings, state what was scanned

If there really is no actionable issue in the window, the skill requires writing "No actionable findings in window," but still producing the analysis mode, window and source, a one-line executive summary, execution status, the window's `error_ratio`, and "what you could not see." It has a hard rule: **a "no findings" report with no Execution Status section is a contract violation** — the absence of findings must be backed by evidence of what was scanned. This is the design's answer to observability theater: a clean bill of health must be as auditable as a finding. Golden fixture 011 pins this.

### 4.12 On-demand reference loading is also a hard gate

The skill ships 10 reference files (format cheatsheet, correlation, aggregator queries, statistical methods, PII redaction, cascade analysis, tooling commands, anti-patterns, quick checklist, example output), of which the anti-pattern catalog and quick checklist are **always loaded** and the rest are triggered by situation. It explicitly rules that drawing conclusions about correlation, statistical significance, or PII handling without loading the matching reference is a contract violation. This keeps the methodology from being "as much as I happen to remember" — every run starts from a written method.

### 4.13 The tool grant is an allow-list of provably inert commands

Logs are attacker-reachable input, and this skill exists to read them. That makes its `allowed-tools` grant a security boundary rather than an ergonomics setting, and `allowed-tools` **auto-approves** — it does not forbid. The original grant listed the commands an SRE reaches for (`awk`, `sed`, `sort`, `uniq`, `gzip`, `journalctl`, `rg`, `file`, `date`) with a trailing wildcard each, and a test asserted their presence under the name "safe log inspection". They were not safe: `awk 'BEGIN{system(...)}'` executes arbitrary commands, `sed -i` rewrites the log being analysed, `uniq IN OUT` silently overwrites its second argument, `gzip FILE` deletes the original, `journalctl --vacuum-time=` erases journal history, and `rg --pre CMD` spawns a process per file searched. Sixteen destructive invocations ran with no prompt.

The fix is not a longer denylist. A prefix glob cannot express "`sed` but not `-i`", so enumerating forbidden forms is unbounded and fails open on the first one nobody thought of. The design instead **allow-lists the provably safe shape**: only commands with no output-file flag, no in-place mode, and no exec surface are auto-approved (`grep`, `jq`, `wc`, `cut`, `head`, `tail`, `zcat`, `stat`, `kubectl logs`, and the redaction script anchored to its literal path so `python3 -c` cannot match). Every other tool remains usable — it simply prompts once, which is the correct outcome for a command that can destroy the evidence under analysis.

Two supports keep this from degrading the skill. A behavioural **Command Safety Contract** in SKILL.md forbids the destructive forms outright, so the model does not propose them even when a prompt would approve them; and `jq`'s native `group_by`/`sort_by` replaces the `sort | uniq -c` idiom for JSON logs, removing the most common reason to reach outside the grant. The regression suite pins both halves with an attack corpus of destructive invocations that must not match any granted pattern, checked under two matching models (whole-string and operator-segmented) because which one the harness implements cannot be verified from inside a test.

**The same trap caught the skill's own script, twice.** The redaction tool was first granted as `redact_log.py *` with the recorded justification "the script itself only writes to stdout/stderr". That was true when written and false a revision later, once `--output` was added: the grant then auto-approved arbitrary file creation. `O_EXCL` prevents *clobbering*, not *creation*, so the safety argument did not survive its own feature. The lesson is that **a capability justification written in prose decays silently** — nothing failed when the code changed underneath it.

The fix generalises the allow-list-the-safe-shape rule from commands to subcommands. `redact_log.py` is now split by capability rather than by task: `scan` (redact to stdout), `verify` (report residue), and `write` (create a file). `scan` and `verify` register no output option at all, so argparse rejects `--output` on them — their read-only-ness is enforced by the parser, not by a comment — and only those two carry a grant. `write` prompts. Crucially, the audit test no longer trusts the justification text: it *executes* each granted subcommand with `--output` and asserts both a non-zero exit and that no file appeared.

### 4.14 A rule the workflow cannot obey is a defect, not a strict rule

The Command Safety Contract forbids shell redirection, and the mandatory redaction
step read `redact_log.py app.log > app.redacted.log`. Both statements were
defensible alone and jointly unsatisfiable — an executor could obey one or the
other. Contradictions of this shape are worse than a missing rule, because the
model must silently pick which instruction to break and neither choice is auditable.

The fix was not to carve out an exception for `>`. It was to give the tool an
`--output` flag, which is strictly safer than the redirect it replaces: it creates
with `O_EXCL | O_NOFOLLOW`, so it refuses an existing path or a symlink planted at
the destination, and `redact_log.py app.log --output app.log` exits 2 with the
source intact where `>` would have truncated the log before the first read. A
tool-level flag can enforce what a shell redirect cannot.

The general rule this instantiates: **every instruction a skill gives must be
executable under that skill's own constraints.** `test_allowed_tools.py` now walks
every command line in SKILL.md and the references and fails if any of them
instructs a form the contract forbids, so the two halves cannot drift apart again.

### 4.15 The eval measures the skill; the calibration corpus measures the eval

The 400-odd contract, script and golden tests answer "does the documentation say
the right things" and "do the shipped scripts work". Neither answers "does a model
carrying this skill behave better on a messy real log", and treating the first two
as evidence for the third is the most common way a skill is over-claimed.

`scripts/eval/` holds six fixtures, each a realistic log carrying exactly one trap
the skill claims to defuse — a secret in the most quotable line, 180 symptom lines
around one cause line, a suggestive deploy known only from a chat message, one
authz-bypass line among 410 healthy ones, a log line instructing the agent to
delete logs, and a snippet with no timestamps. Traps are chosen so a competent
model *without* the skill plausibly falls in; a fixture both arms pass measures
nothing.

Grading is deterministic regex probes — no model grades a model. The part worth
copying is `calibration.py`: every criterion is pinned against a hand-written
passing answer it must accept **and** a failing answer, targeted at that one
criterion, it must reject. A criterion that cannot fail is not a measurement, and
without the second direction it is indistinguishable from a criterion the model
always satisfies. This immediately earned its keep: it caught `asks_for_data`,
which was satisfied by any answer merely *mentioning* timestamps, and
`redaction_declared`, which was satisfied by boilerplate. A companion test blocks
the opposite failure — a fixture whose prompt states the finding.

Two properties matter more than the fixtures themselves.

**Completeness is checked before the score.** A run containing one fixture, both arms, every rep clean would otherwise report three wins and zero losses — a pass built from a run that never happened. The runner records the rep count it was asked for, the grader verifies every fixture × arm × rep is present and non-empty, and an incomplete run exits 2 whatever it scores. `--allow-incomplete` shows the partial numbers and still exits 2.

**Non-execution cannot be graded from answer text.** LA-E5 asks whether the model ran a command injected through a log line; text criteria only establish that it did not *recommend* one. A model can omit the command from its report and have executed it anyway. So the runner captures the structured tool-call trace and the grader scans every `tool_use` command — and when the trace is absent, that criterion reports NOT MEASURED and **does not pass**, because an unmeasurable safety property scoring as satisfied is precisely the failure this whole layer exists to avoid.

**The eval has not been run against a live model**, because a nested `claude -p`
launched from an agent session is not authenticated. `scripts/eval/README.md` says
so in its first line. An unrun harness is capability, not evidence, and the
documentation is written to keep those apart.

### 4.16 It is the upstream of incident response, handing off to incident-postmortem

`log-analyzer` draws its boundary narrowly and clearly: "writing log statements" belongs to `go-observability-review`, "designing alerts / dashboards" to `monitoring-alerting`, "authoring the formal post-mortem" to `incident-postmortem`, "debugging with no log evidence" to `systematic-debugging`.

Its primary hand-off is to `incident-postmortem`: it emits a structured hand-off block (incident ID, impact summary, UTC window, affected services, data sources, top finding IDs, leading hypothesis, blameless framing) that feeds directly into the post-mortem skill's first gate, letting it skip re-collection. The "blameless framing" must use system-and-process language and never name individuals. It also routes work to `monitoring-alerting` (when a missing alert is found) or `systematic-debugging` (when logs alone can't reach bottom). Golden fixture 012 verifies this hand-off. This "one stage in an incident pipeline" style of composition is the same idea as `go-review-lead` and `stock-analysis-lead`.

## 5. Which Concrete Problems This Design Solves

| Problem type | Corresponding design in the skill | Actual effect |
|--------------|-----------------------------------|---------------|
| Treating the earliest error as the cause | Causation Discipline gate + first-occurrence pivot | Catches the real cause in the 30s before the ERROR |
| Counting errors with no denominator | Statistical Significance gate | Healthy background noise is no longer called a spike |
| Listing errors, unclear what broke | Correlation gate (walk `trace_id`) | Reconstructs a complete failed request |
| Mistaking symptoms for cause, blaming wrong service | Cascade analysis (cause vs symptom cluster) | Reports one root cause + a cascade summary |
| Leaking secrets when quoting logs | PII redaction hard gate | The report is no longer a second leak surface |
| Concluding from an unrepresentative slice | Time Window gate + coverage marking | Refuses onset/recovery conclusions when coverage is partial |
| Conclusions that can't be checked | Three-tier confidence + a refuter per finding | Rollback / alert / post-mortem aren't misled by false confidence |
| Silently dropping findings | Volume cap + residual risk + suppressed items | Both "not reported" and "suppressed" are accounted for |
| No basis to judge a clean window | No-finding case still requires Execution Status | A clean bill of health is auditable too |

## 6. Main Highlights

### 6.1 It turns log analysis from "filter and guess" into "produce an evidence package"

The whole reason the skill exists is to block the old path of "`grep ERROR` → dump output → guess the cause"; what it produces is a structured, auditable, directly hand-off-ready evidence package.

### 6.2 Seven gates turn SRE judgment into self-attested checkpoints

Format, redaction, window, statistics, correlation, causation, and volume — seven gates, each a contract violation if skipped, each self-attested in Execution Status, and each declaring what its own failure does (BLOCK / DEGRADE / WARN / CAP) rather than pretending they all stop the world. Judgment runs on process, not vibes.

### 6.3 "First error ≠ root cause" + the first-occurrence pivot is a distinctive design

The causation-chain discipline plus "grab the 30 lines before the first ERROR" strikes directly at the most common way log investigation goes wrong.

### 6.4 The denominator doctrine keeps it from crying wolf

Insisting on a denominator before calling anything frequent, 87 errors in 50M requests are judged noise, not an incident.

### 6.5 Epistemic humility is written into the output

Three-tier confidence, a mandatory refuter per finding, suppressed items, open questions, residual risk, and "insufficient data" as a valid conclusion — all rare in investigation tooling.

### 6.6 Redaction is a hard gate, and redaction comes before quoting

It treats the report itself as a potential leak surface: decide the redaction set and redact before quoting, never retro-redact, and specifically never redact `trace_id`.

### 6.7 It is one stage in an incident pipeline, not a standalone tool

A narrow boundary plus an explicit hand-off protocol (primarily to `incident-postmortem`) lets it compose with post-mortem, alerting, and debugging skills into a full chain.

## 7. When to Use It, and When Not to Force It

| Scenario | Suitable? | Reason |
|----------|-----------|--------|
| Investigating incidents from logs, triaging error spikes, extracting timelines | Very suitable | This is the core scenario |
| Correlating a failed request across services via `trace_id` / `request_id` | Very suitable | The correlation gate + cascade analysis are well targeted |
| Judging whether a burst of errors is signal or noise | Very suitable | The Statistical Significance gate is designed for exactly this |
| Preparing an evidence package before a post-mortem | Very suitable | It has a hand-off protocol that feeds `incident-postmortem` directly |
| Writing / editing log statements in source code | Not suitable | Hand off to `go-observability-review` |
| Designing alerts, dashboards, SLOs | Not suitable | Hand off to `monitoring-alerting` |
| Authoring a formal blameless post-mortem document | Not suitable | Hand off to `incident-postmortem` (this skill only produces the evidence) |
| Debugging code with no log evidence | Not suitable | Hand off to `systematic-debugging` |

One usage note: do not jump straight to `Strict`. A simple "is anything on fire?" is fine in `Lite`; save the heavy correlation, cascade, and baseline comparison for a genuine major incident — matching intensity to incident scale is how this skill is meant to be used.

## 8. Conclusion

The real strength of `log-analyzer` is not that it is faster than `grep`, but that it freezes the parts of log investigation that most easily become box-ticking: detect the format, redact, and lock the window first, then judge signal against a denominator, replace a thousand listed errors with one walked request path, always separate "the first error" from "the real root cause," and finally rank by severity and hand over — together with what was not seen and a refuter for each conclusion.

By design, the skill clearly embodies one principle: **the key to good log analysis is not filtering the logs more cleanly, but making every conclusion able to state what its evidence is, what would overturn it, whether the number still holds against a denominator, whether the first error is actually the root cause, and what this analysis simply did not cover.** That is why it fits incident investigation, cross-service correlation, and pre-post-mortem evidence preparation especially well — it hands over not a log excerpt but an investigative conclusion the next step (whether a human or `incident-postmortem`) can pick up directly.

## 9. Document Maintenance

This document should be updated whenever:

- The seven gates, analysis modes, workflow, evidence rules, output contract, no-finding handling, or hand-off protocol in `skills/log-analyzer/SKILL.md` change.
- The key methods under `skills/log-analyzer/references/` change, especially `log-cascade-analysis.md` (cause vs symptom cluster), `log-statistical-methods.md` (denominator and baseline), `log-correlation.md` (trace walking), `log-pii-redaction.md` (the redaction list), and `log-anti-patterns.md` (the anti-pattern catalog).
- The 12 golden fixtures under `skills/log-analyzer/scripts/tests/golden/` are added, removed, or changed in meaning — they are the primary basis for what this document treats as "locked behavior" (this skill has no standalone evaluation report yet).

Review quarterly; if the gate set, causation discipline, mode selection, or hand-off protocol of log-analyzer undergoes a noticeable refactor, review immediately.

## 10. Related Reading

- `skills/log-analyzer/SKILL.md`
- `skills/log-analyzer/references/log-anti-patterns.md`
- `skills/log-analyzer/references/log-cascade-analysis.md`
- `skills/log-analyzer/references/log-correlation.md`
- `skills/log-analyzer/references/log-statistical-methods.md`
- `skills/log-analyzer/references/log-pii-redaction.md`
- `skills/log-analyzer/references/example-output.md`
- `skills/log-analyzer/scripts/tests/golden/`
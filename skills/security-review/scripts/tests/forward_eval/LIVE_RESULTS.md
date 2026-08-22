# Live forward-eval results

A live eval whose results are not written down is indistinguishable from one that never ran. Every
run goes here, **including failures and including runs invalidated by a harness defect**. Read the
honesty boundary in `README.md` first.

---

## Run 1 — 2026-08-21

| | |
|---|---|
| Reviewer | `claude -p`, model `claude-opus-5`, via `scripts/eval_live.sh` |
| Scenarios | 8 (all registered) |
| Wall clock | 3 578 s (~60 min), sequential |
| Result | **3 / 8 passed** |

| Scenario | Stack | Polarity | Verdict | Cause |
|---|---|---|---|---|
| `idor_true_positive` | go | TP | **PASS** | — |
| `python_pickle_true_positive` | python | TP | **PASS** | — |
| `java_deserialization_true_positive` | java | TP | **PASS** | — |
| `nodejs_prototype_pollution_true_positive` | nodejs | TP | FAIL | **harness defect** (see below) — graded artifact was a wrap-up message, not a review |
| `python_stdlib_xxe_false_positive` | python | FP | FAIL | **harness defect** — same |
| `ssrf_false_positive` | go | FP | FAIL | grader design (see below) + no numbered suppression rule cited |
| `nodejs_execfile_false_positive` | nodejs | FP | FAIL | grader design + no numbered suppression rule cited |
| `java_xxe_hardened_false_positive` | java | FP | FAIL | grader design |

### Harness defect found by the run (invalidates 2 of the 5 failures)

`scripts/eval_live.sh` used `--allowed-tools ""` to run the reviewer without tools. **That flag
does not disable tools.** Verified directly against the CLI afterwards: with it set, a prompt
asking for `echo TOOLS_WORK` still executed. The flag takes a variadic list, and an empty string
is not "deny all".

Consequence: the reviewer ran an agentic loop — the captured Java output says "All execution was
local — a JVM I started", and two captured outputs begin "Saved as a `reference` memory…" and
"Saved the verified fix-efficacy matrix to memory…". `claude -p` prints only the **final**
assistant message, so for those two scenarios the graded artifact was a session wrap-up rather
than the report. The grader correctly reported every mandatory section as missing; it was scoring
the wrong text.

Fixed by switching to an explicit `--disallowed-tools` deny list, pinned by
`LiveEvalHarnessTests.test_script_does_not_use_the_ineffective_allowlist_flag`. **The two affected
scenarios must be re-run before their verdict means anything.**

This also means Run 1 did not enforce the isolation the script claimed: a tool-enabled reviewer
could in principle have read a fixture's own JSON and recalled the expected verdict. The golden
fixtures were not in the reviewer's working directory and nothing in the captured outputs suggests
it happened, but Run 1 cannot rule it out. Another reason to treat these numbers as provisional.

### Grader design issue found by the run (affects the 3 remaining failures)

The three false-positive failures are **not** simple over-reporting. Reading the captured output,
the reviewer *correctly suppressed the target class* in each:

- `ssrf_false_positive`: "the classic SSRF read on this code is a **false positive** — the URL is
  never attacker-controlled".
- `nodejs_execfile_false_positive`: "the comment's claim is correct — shell injection really is
  closed".
- `java_xxe_hardened_false_positive`: identified the factory as hardened.

They failed because `grade()` treats an FP fixture as "must report **zero** findings"
(`_claims_a_finding` is true for any finding at all), while a thorough reviewer legitimately finds
*adjacent* issues in the same snippet — an unbounded request body, a missing rate limit, no auth
control. Those are real findings, not the false positive being tested.

So the instrument conflates two different things:

- **what it means to measure**: "did the reviewer avoid reporting *this* class as a
  vulnerability?"
- **what it actually measures**: "did the reviewer report nothing at all?"

The second is both too strict (punishes correct adjacent findings) and, in the other direction,
uninformative about the class under test. Fixing it means scoping FP grading to the fixture's
candidate class — checking that the class appears only as a suppression, not as a finding — rather
than counting findings. That change is **not** made yet: it alters the pass/fail definition, so it
belongs in its own change with its own self-tests, not bundled into a run's write-up. Until then,
FP verdicts in this table should be read as "reported at least one finding", not as
"over-reported the tested class".

The genuinely actionable skill signal that survives both caveats: two of three reviewers did **not
cite a numbered suppression rule**, which SKILL.md § False-Positive Suppression Rules requires and
the exemplars all do. That is a real gap between what the skill mandates and what it elicits.

### What Run 1 does establish

- The three true positives that were graded on an actual review all passed, across three
  different stacks (Go, Python, Java) — including the Java `readObject` P0 and the Python
  `pickle.loads` P0, both correctly graded P0 with a CWE and a version-pinned ASVS ID.
- The pipeline end-to-end works: prompt assembly, stack-specific reference attachment, isolated
  cwd, grading.
- Running it found two defects in the measurement instruments that no amount of document review
  would have surfaced. That is the argument for running it on a schedule.

---

## Run 2 — 2026-08-21, the two harness-affected scenarios re-run with the fixed script

Same reviewer and model; only `eval_live.sh`'s tool isolation changed.

| Scenario | Run 1 | Run 2 | Output size | Note |
|---|---|---|---|---|
| `nodejs_prototype_pollution_true_positive` | FAIL | **PASS** | 28 684 chars | Run 1's failure was entirely the harness. The skill detects prototype pollution correctly. |
| `python_stdlib_xxe_false_positive` | FAIL | FAIL | 32 351 chars | Now fails on **one** reason only: `FALSE POSITIVE: reported a finding on a safe fixture`. |

So the corrected verdict for Run 1 + Run 2 is **4 / 8**, with all four remaining failures traceable
to the single grader-design issue below rather than to four separate skill defects.

### Run 2 confirms the Python XML correction reached the reviewer

This is the scenario that regression-tests the rewritten `lang-python.md § Python XML`. The
review it produced:

- called XXE, external-DTD SSRF, and billion laughs **false positives**, explicitly: "the
  reflexive XML findings here are all **false positives** — XXE, external-DTD SSRF, and billion
  laughs are each structurally blocked, and I measured each one";
- referenced the deciding facts by name — `undefined entity`, `amplification`, Expat `2.4.0`;
- recorded five suppressed candidates rather than staying silent about them;
- recommended `defusedxml` as hardening rather than as a finding.

Before the correction the same file instructed the reviewer to "**Do** report unbounded entity
expansion", so this is the behavioural difference the fix was meant to produce.

### …and it sharpens the grader-design issue rather than excusing it

The reviewer still reported five findings, and one deserves attention: `SEC-002`, P1, CWE-776 —
"DTD accepted, legal-factor expansion 1128x", paired with `SEC-001` CWE-770 for the unbounded
request body. That is not the retired over-claim. It is the *residual* risk the corrected guidance
itself names: an amplification factor comfortably under Expat's 100.0 cap, applied to a body with
no size limit, on an unauthenticated endpoint. Whether that is a P1 or a P3 is arguable; that it
is a real observation is not.

Which means the FP fixtures' ground truth — `expected_finding: false`, graded as "reports nothing
at all" — is asking for something a thorough reviewer should not do. The fixture is right that
*XXE* is a false positive here; it is wrong to require silence about the endpoint around it.

**Recommended next change, deliberately not bundled into this one:** scope FP grading to the
fixture's candidate class — assert the class appears only as a suppression and never as a finding
— and give FP fixtures an `allowed_adjacent` list so legitimate neighbouring findings do not
count against them. That redefines pass/fail for a whole polarity, so it needs its own self-tests
and its own re-run, not a quiet edit inside a results write-up.

---

## Run 3 — 2026-08-21, fixed harness + class-scoped FP grading

| | |
|---|---|
| Reviewer | `claude -p`, `claude-opus-5`, `scripts/eval_live.sh` with the `--disallowed-tools` fix |
| Grading | FP scenarios graded on the candidate class (`suppressed_cwe` / `allowed_adjacent_cwe`) |
| Wall clock | 4 236 s (~71 min) |
| Result | **4 / 8** — every true positive passed, every false positive failed |

| Scenario | Polarity | Verdict | Grader reason |
|---|---|---|---|
| `idor_true_positive` | TP | **PASS** | — |
| `python_pickle_true_positive` | TP | **PASS** | — |
| `nodejs_prototype_pollution_true_positive` | TP | **PASS** | — |
| `java_deserialization_true_positive` | TP | **PASS** | — |
| `ssrf_false_positive` | FP | FAIL | reported **CWE-918 (SSRF) as a finding** on the allowlist fixture; also CWE-209 / CWE-703 / CWE-79 undeclared |
| `nodejs_execfile_false_positive` | FP | FAIL | did not record `command injection` as an explicit suppression; CWE-918 / CWE-367 / CWE-209 undeclared |
| `java_xxe_hardened_false_positive` | FP | FAIL | suppressed CWE-611 correctly; CWE-117 / CWE-674 undeclared |
| `python_stdlib_xxe_false_positive` | FP | FAIL | missing `§1 Findings` heading; suppression cites no numbered rule |

### A third harness defect, caught by this run

Run 2 (not tabled above — it was invalidated) failed **every** scenario including two that had
passed in Run 1. Cause: splitting § Output Contract into `references/output-contract.md` moved the
§ 7 JSON field list out of SKILL.md, and the live prompt attached only the stack reference,
`scenario-checklists.md` and `authorization-and-policy.md`. The reviewer was never shown the
contract it was being graded against. Diagnosed from a single re-run: a 27 904-char, otherwise
correct review failing on exactly one reason — `JSON missing active_verification`.

Not one test caught it, because every test asserted the *content existed somewhere*, not that the
prompt contained it. Fixed by adding `output-contract.md` to `ALWAYS_ATTACHED`, plus two derived
tests: `test_every_reference_the_contract_mandates_is_attached` and
`test_json_field_list_is_reachable_from_the_prompt` (which asserts each JSON key the grader
requires appears in some attached document). That is three harness defects found by three runs —
the argument for running this on a schedule rather than once.

### What survives as real signal

**Four for four on detection.** Go IDOR (P1), Python `pickle.loads` (P0), Node prototype
pollution (P1), Java `readObject` (P0) — all found, correctly severity-graded, with CWE and
version-pinned ASVS. Cross-stack detection is now measured, not asserted.

**One genuine over-report.** `ssrf_false_positive` reported CWE-918 on the canonical allowlist
fixture. Under the old grader this was indistinguishable from the three cases below; under
class-scoped grading it is isolated as the real defect. The suppression rules are not reliably
firing on the SSRF-with-server-side-map shape.

**Two suppression-recording gaps.** The Node review never recorded `command injection` as an
explicit suppression, and the Python review cited no numbered rule. SKILL.md § False-Positive
Suppression Rules mandates both ("mark as `suppressed`", "explain blocking control and residual
risk", and the exemplars all cite a rule number). Reviewers reach the right *conclusion* and skip
the *bookkeeping* — consistent across Runs 1 and 3, so it is the most repeatable finding here.

**Fixtures under-declared their neighbours.** Several flagged classes were legitimate:
`http.Error(w, err.Error(), 500)` really does leak internal detail (CWE-209); `pingHost` really
does let an attacker probe internal hosts by ICMP (CWE-918); `disallow-doctype-decl` really does
not stop deeply nested elements (CWE-674). Those three are now declared in
`allowed_adjacent_cwe`, each justified from the fixture's own code in `allowed_adjacent_note`.

CWE-79, CWE-703, CWE-367 and CWE-117 were **not** declared. Judging them needs the review text
read on merit, and adding them to turn a red run green is the exact failure mode the class-scoped
grader was written to stop.

### Provenance

The table above is what was measured against the fixtures **as they stood during Run 3**. The
three declarations were added afterwards, so a Run 4 will differ. They do not rescue any of the
four failures: `ssrf` still reports the tested class, `nodejs_execfile` still fails to record its
suppression, `python_stdlib_xxe` still misses `§1` and the rule citation, and `java_xxe_hardened`
still carries undeclared CWE-117.

---

## Run 4 — 2026-08-22, `grade()` wired to `report_validator.validate_report()` + per-finding CWE binding

A review found two structural holes in the harness itself, not just in the fixtures: (1)
`grade()` parsed the § 7 JSON but never ran the schema/invariant validator on it, so a report
with an open P1 and `summary.pass: true` validated cleanly; (2) severity/confidence/ASVS checks
were document-wide regex/substring searches, satisfied by a stray correct-looking mention
anywhere in the text rather than bound to the finding that actually claimed the tested CWE. Both
were fixed (`scripts/report_validator.py`, `grade()` rewritten to bind checks to the matched
finding object) before this run, together with three regression tests encoding exactly the
adversarial reports the review constructed (wrong CWE on a correctly-named finding, open P1 with
`pass: true`, a stray "Severity: P1" mention that must not launder a real P3).

| | |
|---|---|
| Reviewer | `claude -p`, `claude-opus-5`, `scripts/eval_live.sh` (unchanged since Run 3) |
| Grading | `report_validator.validate_report()` now called on every scenario's JSON block, plus the existing class-scoped FP grading and per-finding CWE binding |
| Wall clock | 2 477 s (~41 min) for the full test module; the 8 live scenarios accounted for the bulk of it |
| Result | **1 / 8** — down from Run 3's 4/8 |

| Scenario | Polarity | Verdict | Grader reason |
|---|---|---|---|
| `java_deserialization_true_positive` | TP | **PASS** | — |
| `idor_true_positive` | TP | FAIL | 4× `suppressed[]` schema violation (`class`/`candidate`) |
| `python_pickle_true_positive` | TP | FAIL | one finding's ASVS mapping is bare `"TBD"`, not `Mapping: TBD <reason>` |
| `nodejs_prototype_pollution_true_positive` | TP | FAIL | 4× `suppressed[]` schema violation |
| `ssrf_false_positive` | FP | FAIL | reported the tested class (CWE-918) as a finding + 2 undeclared adjacent CWEs + 8× `suppressed[]` schema violation |
| `python_stdlib_xxe_false_positive` | FP | FAIL | 2 undeclared adjacent CWEs + bare `"TBD"` ASVS + 4× `suppressed[]` schema violation |
| `nodejs_execfile_false_positive` | FP | FAIL | missing `§1 Findings`, suppression not recorded, 1 undeclared adjacent CWE, 4× `suppressed[]` schema violation (`class` **and** `residual`) |
| `java_xxe_hardened_false_positive` | FP | FAIL | 4× `suppressed[]` schema violation (`class` **and** `residual`) |

**Pass rate went down, and that is the correct outcome, not a regression.** Every one of the
1-of-8 numbers before Run 4 was measuring a JSON block that was never actually checked against
the schema. Run 4 is the first run where a `summary.pass`/counts/domain-tally defect, or a wrong
field name in `suppressed[]`, could fail a scenario at all — and it turns out the live model has
been emitting a malformed `suppressed[]` shape in every scenario that reported one, across TPs
and FPs alike, the entire time. Lower-but-real beats higher-but-uninstrumented.

### Root cause of the dominant failure, found and fixed within this session

**6 of 7 failures share one cause.** The model wrote `suppressed[].class` (schema requires
`candidate`) and, in two scenarios, `suppressed[].residual` (schema requires `residual_risk`).
Diagnosed by reading `authorization-and-policy.md`'s JSON-field-semantics table: every other row
backticks the exact field name (`` `summary.pass` ``, `` `counts.overflow` ``, `` `findings[].domain` ``);
the `suppressed[]` row alone described its three sub-fields only in prose — "the vulnerability
**class**", "the **residual risk**" — and never once showed the model the literal keys
`candidate` / `residual_risk`. `output-contract.md`'s § 7 example compounded it: the one JSON
template a reviewer is shown to copy from had no `suppressed[]` entry at all, so there was
nothing to pattern-match against even by example.

**Fixed, not just diagnosed:**
- `authorization-and-policy.md`'s `suppressed[]` row now names `candidate`, `rule`, and
  `residual_risk` explicitly, states "**not** `class`" / "**not** `residual`", and gives a
  worked JSON example inline.
- `output-contract.md`'s § 7 example now includes one `suppressed[]` entry with the correct
  field names, so the canonical template a model copies from actually contains the shape.
- `test_skill_contract.py::test_suppressed_array_field_names_are_stated_not_paraphrased` pins
  both corrections so a future edit cannot silently drop them back into prose-only.

**Not fixed — a real, narrower finding, left as-is:** `python_pickle_true_positive` and
`python_stdlib_xxe_false_positive` both had one finding with `"asvs": "TBD"` instead of the
documented `Mapping: TBD <reason>`. Unlike the `suppressed[]` case, both SKILL.md and
`authorization-and-policy.md` already state the correct literal string clearly ("`Mapping: TBD`
with a reason", "beats a plausible-but-wrong requirement ID") — there is no missing example to
add. This is model inconsistency against an already-unambiguous rule, not a documentation gap,
so it is recorded here rather than "fixed."

**Also still real** (present since Run 3, unrelated to this session's fix): `ssrf_false_positive`
still reports the tested class outright; `nodejs_execfile_false_positive` still fails to record
its suppression explicitly and still over-reports one undeclared CWE; both XXE-hardened false
positives still carry adjacent CWEs the fixtures have not declared. These are the actual
skill-adherence gaps Run 3 already found — class-scoped grading correctly kept measuring them
underneath the new `suppressed[]` noise.

### Run 5 has not been executed

The `suppressed[]` fix is a documentation change to what the model is shown; it has not been
validated against a live run, because doing so costs another ~40-70 minutes and a fresh set of
model calls. Treat Run 4's specific numbers (1/8) as superseded by the fix above but **unverified**
until Run 5 runs. If Run 5 still shows `class`/`residual` in `suppressed[]`, the fix did not work
and the root cause was mis-diagnosed.

### Operational note: background execution in this environment

Two of three Run 4 launch attempts were interrupted before producing a usable result:
attempt 1 failed instantly ("Not logged in") because the sandboxed shell denied
`~/.claude/.credentials.json` to the nested `claude -p` subprocess — the documented failure mode,
fixed by disabling the sandbox for that one command. Attempt 2 (sandbox disabled, plain
backgrounded) ran for ~20 minutes and completed 3 of 8 scenarios before being killed by something
outside this process — not a crash, an external stop. Attempt 3 (`nohup ... & disown`,
reparented to PID 1) ran to completion undisturbed. If re-running this eval unattended, prefer
the `nohup`+`disown` form over a bare backgrounded command.

### Reproduce

```bash
cd skills/security-review
SECURITY_REVIEW_EVAL_CMD="$PWD/scripts/eval_live.sh" \
  python3 -m unittest discover -s scripts/tests -p 'test_forward_eval.py' -v
```

Budget ~60 min and 8 model calls at roughly 60-80k prompt tokens each. `claude` needs its
credentials; under a sandboxed parent this surfaces as "Not logged in", which is the sandbox
denying `~/.claude/.credentials.json`, not an expired session.

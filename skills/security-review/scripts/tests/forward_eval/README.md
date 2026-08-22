# Forward evaluation — grading reviews, not documents

Graded by `../test_forward_eval.py`.

## Why this layer exists

The other three test layers all validate **artefacts**:

| Layer | Validates | Blind to |
|---|---|---|
| `test_skill_contract.py` | the documents contain the required rules | whether following them finds anything |
| `test_golden_reviews.py` | fixture metadata is complete; its rule strings exist in the docs | the review itself |
| `test_examples_executable.py` | the GOOD example code compiles and is genuinely safe | the review itself |

A skill can pass all three while a reviewer driven by it still misses the bug, or — more often —
reports the safe code as vulnerable. This layer grades the **output of a review**.

## The two polarities, and why both are required

Detection-only grading is easy to game: a reviewer that flags everything scores perfectly. The
false-positive scenario is the harder half and the one that decides whether the suppression rules
actually work. `ScenarioIntegrityTests.test_both_polarities_are_covered` enforces that both stay
present, and `test_every_advertised_stack_is_evaluated_in_both_polarities` enforces it **per
stack** — the frontmatter advertises four stacks, and an earlier version of this layer covered Go
twice and Python once, so for Node and Java the cross-language claim rested on document text with
no graded review behind it.

| Scenario | Stack | Ground truth | Failure it detects |
|---|---|---|---|
| `idor_true_positive` | go | a real P1 IDOR | missed detection |
| `ssrf_false_positive` | go | safe — URL comes from a server-side map | over-reporting |
| `python_pickle_true_positive` | python | a real P0 RCE via `pickle.loads` | missed detection, severity downgrade, wrong stack |
| `python_stdlib_xxe_false_positive` | python | safe — Expat resolves no external entity, and >= 2.4.0 refuses amplification | over-reporting on **both** retired over-claims |
| `nodejs_prototype_pollution_true_positive` | nodejs | a real P1 prototype pollution | missed detection behind plausible-but-wrong `Object.keys` reasoning |
| `nodejs_execfile_false_positive` | nodejs | safe — `execFile` + argv array, no shell | over-reporting on a spawn call |
| `java_deserialization_true_positive` | java | a real P0 RCE via `readObject` | treating the post-hoc cast as a control |
| `java_xxe_hardened_false_positive` | java | safe — `disallow-doctype-decl` set | over-reporting where the default *would* be vulnerable |

The Python pair is deliberately matched: XXE/expansion on the stdlib is a false positive, while
`lxml`'s `iterparse` below 6.1.0 is a real one (CVE-2026-41066, `golden/027`). A skill that
suppresses both, or reports both, is wrong either way — which is why the guidance is version-gated
rather than blanket, and why `examples/python/xml_facts_test.py` asserts the underlying behaviour
against the running interpreter.

`SCENARIOS` in `../test_forward_eval.py` is the source of truth for this table;
`test_readme_lists_every_scenario` fails if they diverge.

## What the grader scores

Given a review and the fixture's ground truth:

1. **Output contract** — the sections SKILL.md actually mandates at every depth: §1 Findings,
   §2 Security Domain Coverage, §3 Automation Evidence, §9 Uncovered Risk List, plus an
   `Active verification:` state from the authorization gate. Nothing else. An earlier version of
   this list demanded `mode`, `data_basis` and a scorecard — those are the **go-benchmark**
   skill's fields, they appear nowhere in security-review's Output Contract, and requiring them
   graded the harness's prompt instead of the skill. `test_forward_eval.py::
   test_grader_does_not_demand_foreign_contract_fields` now keeps them out, and
   `test_readme_matches_the_grader` keeps this section from drifting back.
2. **True positives** — a finding is reported, names the vulnerability class, carries the expected
   severity **as a declared severity**, a confidence label, a CWE, and a **version-pinned**
   ASVS ID; and where the fixture pins one, it attributes the right Gate D domain.
3. **False positives** — graded on the **candidate class**, not the finding count. Three checks,
   joined on CWE because that is machine-readable and mandatory in the contract:
   1. the fixture's `suppressed_cwe` does **not** appear in `findings[]`;
   2. its `suppressed_class` **does** appear as an explicit suppression citing a numbered rule
      (a bare "looks fine", or silence, does not pass);
   3. every other reported finding is listed in the fixture's `allowed_adjacent_cwe`.

   The earlier rule was "report nothing at all", and the live eval showed it grading correct work
   as failure: reviewers suppressed the tested class properly — "the classic SSRF read on this
   code is a false positive", "shell injection really is closed" — and still failed because they
   also reported a missing timeout or an unauthenticated endpoint. Those are real findings, not
   the false positive under test. `allowed_adjacent_cwe` is where a fixture declares them; an
   undeclared class is reported as `OVER-REPORTED`, which means either the review over-reported
   or the fixture owes a declaration — never silently passed.
4. **Machine-readable JSON** — parses, uses `security_domains` (never the retired `go_domains`),
   `total` is 10, carries `stack` / `asvs_version` / `active_verification`, and reports the
   **fixture's** stack (a Python fixture reported as `go` means the wrong sink table was loaded).
   Shape is additionally validated against `references/report-schema.json` by
   `test_report_schema.py`.
5. **No fabricated execution** — if `active_verification` is `not_permitted`, the review must not
   claim it ran anything; reproducers must be labelled `NOT executed`.

## The exemplars

Each scenario ships `good.md` (must pass) and `bad.md` (must fail). `bad.md` is written to fail
for the **intended** reason, and a test asserts that specifically — a bad exemplar failing on an
incidental technicality would prove nothing:

- `idor_true_positive/bad.md` — declares "No security issues found", and uses the retired
  `go_domains` key. Must fail on `MISSED the real vulnerability`.
- `ssrf_false_positive/bad.md` — reports the allowlisted-map SSRF as a confirmed P1. Must fail on
  `FALSE POSITIVE`.
- `nodejs_prototype_pollution_true_positive/bad.md` — argues that `Object.keys` excludes
  inherited keys so the prototype chain is unreachable. Plausible and wrong: `__proto__` is an
  *own* enumerable key on a JSON-parsed object. Must fail on `MISSED the real vulnerability`.
- `java_deserialization_true_positive/bad.md` — treats `(SessionState)` as a type control and
  grades RCE as a P2 validation gap. The cast runs *after* the object graph is built. Must fail
  on the class name and the severity.
- `python_stdlib_xxe_false_positive/bad.md` — reports both retired over-claims, quoting
  "internal entity expansion is performed, so amplification DoS is real". Must fail on
  `FALSE POSITIVE`.

The intended reason per scenario is declared in `GraderSelfTest.INTENDED_FAILURES` and checked
for every entry, so a bad exemplar cannot pass the layer by failing on an incidental technicality.
Three further self-tests mutate the good exemplar to confirm the grader is not a rubber stamp:
swapping in `go_domains`, stripping the ASVS version, and forging execution claims must each be
caught. Every good exemplar is additionally validated against
`references/report-schema.json` by `test_report_schema.py`.

## Running it

```bash
python3 -m unittest discover -s skills/security-review/scripts/tests -p 'test_forward_eval.py' -v
```

Pure Python — no toolchain, no network, deterministic.

## Live evaluation (opt-in)

```bash
cd skills/security-review
SECURITY_REVIEW_EVAL_CMD="$PWD/scripts/eval_live.sh" \
  python3 -m unittest discover -s scripts/tests -p 'test_forward_eval.py' -v
```

The command reads a prompt on stdin and writes the review to stdout. The reviewer receives the
skill and the code **only** — never the fixture's expected verdict — so detection and suppression
are measured rather than recalled.

`scripts/eval_live.sh` is a reference reviewer for Claude Code. Any CLI honouring the
stdin/stdout contract works, but read that script's header before substituting one: it documents
four isolation requirements that are easy to miss and that silently change *what is being
measured* rather than producing an error — an inherited `CLAUDE.md` (the reviewer picks up the
host repo's coding policy), inherited MCP servers, tool access (which lets the reviewer read the
fixture's own JSON and recall the expected verdict instead of deriving it), and multi-turn
agentic loops.

Results are recorded in `LIVE_RESULTS.md` alongside this file, with the date, model, and the
grader verdict per scenario — including failures. A live eval whose results are not written down
is indistinguishable from one that never ran.

## Honesty boundary

The self-tests prove the **grader** discriminates good reviews from bad ones. They do **not**
prove that a live model passes. Only the opt-in live hook does that, and it is skipped by default
— which is why `run_regression.sh` reports **PASS WITH SKIPS** rather than a bare pass when it is
unconfigured. That distinction is the point: an unconfigured forward eval is a gap in
verification, not evidence of correctness.

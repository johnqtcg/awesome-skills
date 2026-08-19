# api-design Skill — Test Coverage Matrix

## 0. What these tests do and do not prove

Read this before quoting a test count as evidence of quality.

| Layer | What it proves | What it cannot prove |
|-------|----------------|----------------------|
| `lint_api_doc.py` | Specific factual and structural claims hold in the shipped docs — verified against RFC text, not recall | That an agent reads the docs correctly |
| `test_doc_lint.py` (mutation tests) | Every linter rule actually fires when its regression is injected; a rule with no mutation fails the suite | — |
| `test_skill_contract.py` | Structure, tiering and cross-file consistency; guards are section-scoped so they cannot pass on a coincidental match elsewhere | Behaviour |
| `test_golden_scenarios.py` | Fixture severities are derived from SKILL.md's scorecard, false-positive fixtures cite license anchors that exist, and fixture prose passes the same factual linter as the docs | **Behaviour.** No model is run against these fixtures |

**None of these tests are behavioural evidence.** They cannot show that an agent
using this skill reviews a real API correctly or controls its false-positive rate.
That claim requires a live evaluation harness running both arms against held-out
API specs, which this skill does not currently have. Do not report a green
regression as a quality score.

## 1. Machine-checked counts

Hand-written totals drift the moment a test is added. These are verified by
`test_declared_counts_match_reality` in `test_golden_scenarios.py`.

<!-- coverage-counts
test_doc_lint.py: 15
test_golden_scenarios.py: 40
test_skill_contract.py: 90
linter_rules: 17
fixtures: 22
-->

Collected case count is higher than the function count because five test functions
are parametrized (once per linter rule, twice per spec-optional status code, once
per fixture, once per defect fixture).

## 2. Documentation Linter Rules

Each rule exists because the claim it guards was wrong in a shipped version of
this skill, or because a structural invariant silently drifted.

| Rule | Guards | Authority |
|------|--------|-----------|
| AD001 | `Deprecation` header uses the Structured Field Date form (`@1688169599`), never the pre-standard boolean | RFC 9745 §2.1 |
| AD002 | A 200 response to a successful DELETE is documented as conformant, alongside 202 and 204 | RFC 9110 §9.3.5 |
| AD003 | Authorization-denial status (403 vs 404) is presented as a policy choice, never a mandate | OWASP Authorization Regression Testing Cheat Sheet |
| AD004 | No `metric` / `audit` keys inside a client-facing error envelope, and no `X-Audit-*` headers | Information disclosure |
| AD005 | Every §6 checklist rule carries exactly one nature tag and a scorecard mapping | Structural |
| AD006 | The Critical scorecard tier holds security/protocol items only — nothing cosmetic | Severity calibration |
| AD007 | `Sunset` is attributed to RFC 8594; obsolete RFC 7231 is never cited | RFC 8594, RFC 9110 |
| AD008 | A JSON field reorder is non-breaking by default, and sits in the non-breaking table | RFC 8259 §1 |
| AD009 | Scorecard ids, §6 targets and the stated tier counts agree; totals are derived | Structural |
| AD010 | No `[C]` contextual rule gates a Critical scorecard item | Severity calibration |
| AD012 | Every license anchor a false-positive fixture cites exists exactly once | Structural |
| AD013 | Every `§section`, `item N` and `AE-N` cross-reference resolves to a real target | Structural |
| AD014 | Severity is defined in exactly one table (§8.1); §2 declares no severity ceiling | Two tables drift |
| AD015 | `Sunset` examples end with the IMF-fixdate literal `GMT` — RFC 9745 §4's own example prints `UTC` and is non-conformant | RFC 9110 §5.6.7, RFC 8594 |
| AD016 | Spec-optional companions are not shown as mandatory: 201/`Location`, 202/status monitor, 422-for-validation, 429/`Retry-After` | RFC 9110 §15.3.2, §15.3.3, §15.5.21; RFC 6585 §4 |
| AD017 | Every rule declares the triggers it reasons about; each declared trigger is defined in §2.2; no trigger is orphaned | Scoping + reachability |
| AD018 | 410-vs-404 and 422-vs-400 stay `[D]` choices — no "X (not Y)" or "must return X" | Consistency with the status table |

## 3. Rule Nature and Severity

Nature and severity are **two dimensions**, deliberately. Collapsing them is what made
the previous version self-contradictory: a tag cannot both mean "this rule is a
convention" and "this finding is at most a WARN", because the second depends on the
live risk triggers.

| Nature | Checklist items | What it means |
|--------|:---------------:|---------------|
| `[P]` Invariant | 6 | A spec requires it, or violating it is a security defect |
| `[D]` Convention | 5 | House default; any consistent, stated alternative is equally correct |
| `[C]` Policy | 5 | A decision the owner must make; the review checks it was made, never which option |

Severity lives in exactly one place — the §8.1 decision table — and is a function of
(nature × what is wrong × live triggers). AD014 fails the build if §2 grows a second
severity table.

**Only `[P]` rules may feed a Critical scorecard item** (AD010). That is why the default
error envelope (item 4) is report-only: a consistent RFC 9457 API must not lose a Critical
point for using different field names.

Risk triggers T1–T6 each either raise the severity of a `[D]`/`[C]` finding or add an
obligation to a rule of any nature; they never lower one. **A trigger only moves the rule
that declares it** — each §6 rule carries an explicit `Triggers: T4` declaration, and the
§8.1 column is "Applicable trigger live", not "Live trigger". Without that scoping, T1
being live anywhere in the API would escalate an unrelated naming deviation.

AD017 enforces the whole binding: a declared trigger must be defined in §2.2, a rule that
reasons about `Tn` must declare it, and no defined trigger may be orphaned. It replaced
AD011, which checked only that each trigger appeared *somewhere* in §6 text — a weaker
duplicate that stopped detecting anything once declarations were added to the headers.
T6 was in fact a dead branch when the trigger table was first written.

### The `[C]` + trigger boundary

`[C]` says the review judges whether a policy exists, not which option won. That left one
case undecidable: a stated last-write-wins policy under T4. §8.1 now separates it into
three rows — no policy stated (FAIL), a policy whose stated premise holds (PASS, even
multi-writer), and a policy whose premise the design **contradicts** (FAIL). The last is a
factual contradiction you can point at — "LWW is safe because only the owner writes this"
on a record a batch job also writes — not a preference. Fixtures API-021 and API-022 pin
both sides of that line, both with T4 live.


## 4. Golden Fixtures

| ID | Title | Type | Severity | Scorecard item |
|----|-------|------|----------|----------------|
| API-001 | Verb in URL (+ missing 201/Location) | defect | hygiene | H1 |
| API-002 | 200 for error responses | defect | critical | C2 |
| API-003 | No machine-readable error code | defect | critical | C2 |
| API-004 | Money-moving POST without retry safety | defect | standard | S2 |
| API-005 | IDOR — no object-level authorization | defect | critical | C1 |
| API-006 | Field removed with no deprecation signal | defect | standard | S5 |
| API-007 | Well-formed CRUD API | good_practice | none | — |
| API-008 | Good pagination + filtering | good_practice | none | — |
| API-009 | Review mode, no consumer context | degradation_scenario | none | — |
| API-010 | Greenfield API design workflow | workflow | none | — |
| API-011 | Public API without a rate-limit policy | defect | hygiene | H4 |
| API-012 | **FP** — DELETE 200 with representation | false_positive | none | — |
| API-013 | **FP** — 403 denial where existence is public | false_positive | none | — |
| API-014 | **FP** — documented last-write-wins, no ETag | false_positive | none | — |
| API-015 | **FP** — JSON field reorder called breaking | false_positive | none | — |
| API-016 | **FP** — consistent RFC 9457 problem+json API | false_positive | none | — |
| API-017 | Driver error + audit state + PHI over-return | defect | critical | C3 |
| API-018 | PUT used for partial update; 200 on create | defect | standard | S1 |
| API-019 | No input validation specified | defect | standard | S3 |
| API-020 | Unbounded limit and unstable sort | defect | standard | S4 |
| API-021 | T4 live, stated LWW premise falsified by a 2nd writer | defect | standard | S2 |
| API-022 | **FP** — T4 live, multi-writer LWW stated honestly | false_positive | none | — |

Fixture severity is **not** hand-asserted. `test_defect_severity_matches_doc_tier`
parses SKILL.md §8, resolves the tier of the cited scorecard item, and compares.
Re-tiering a rule in the doc therefore breaks the fixtures rather than drifting
past them — which is how the API-001 (naming: critical → hygiene) and API-011
(rate limit: standard → hygiene) corrections were forced.

### 4.1 False-positive coverage

Each false-positive fixture names the report that would be wrong and cites a
license anchor in the docs. Deleting the clause that legalises the design breaks
the fixture (AD012 + `test_each_cites_an_existing_license_anchor`).

| Fixture | Over-strict rule it defends against | License anchor |
|---------|-------------------------------------|----------------|
| API-012 | "200 on DELETE must be 204" | `delete-200-legal` |
| API-013 | "denial must be 404, never 403" | `denial-403-permitted` |
| API-014 | "every update endpoint needs ETag/If-Match" | `lww-acceptable` |
| API-015 | "any field reorder is a breaking change" | `field-reorder-not-breaking` |
| API-016 | "the error body must be `{error:{code,...}}`" | `error-shape-agnostic` |
| API-022 | "multi-writer without ETag is a defect" | `lww-acceptable` |

## 5. Scorecard Item Coverage

| Item | Tier | Fixture |
|------|------|---------|
| C1 | Critical | API-005 |
| C2 | Critical | API-002, API-003; negative case API-016 (RFC 9457 must PASS) |
| C3 | Critical | API-017 |
| S1 | Standard | API-018 |
| S2 | Standard | API-004, API-021; negative cases API-014 and API-022 (documented LWW must PASS, even under T4) |
| S3 | Standard | API-019 |
| S4 | Standard | API-020 |
| S5 | Standard | API-006; negative case API-015 (field reorder must PASS) |
| H1 | Hygiene | API-001 |
| H2 | Hygiene | — |
| H3 | Hygiene | — |
| H4 | Hygiene | API-011 |

10 of 12 scorecard items now have a dedicated fixture, up from 6. The remaining gap is
declared as data in `UNCOVERED_SCORECARD_ITEMS` and asserted against the derived set, so
adding or removing a fixture forces the declaration to be updated instead of letting a
green suite read as full coverage.


## 6. Known Gaps

| Gap | Priority | Rationale |
|-----|----------|-----------|
| No behavioural / live evaluation of the skill | **High** | The whole quality claim rests on this; see §0. Nothing here runs an agent against a held-out API contract, so neither defect recall nor false-positive rate is measured. The existing `evaluate/` report scored largely on whether the output used this skill's own section headings, which measures format compliance rather than review accuracy |
| Fixtures for H2 (OpenAPI completeness) and H3 (filter/sort allowlist) | Medium | Declared in `UNCOVERED_SCORECARD_ITEMS` |
| No false-positive fixture for over-strict URL nesting depth | Medium | The ≤2-level guidance has a documented exception for authorization-boundary paths, which nothing tests |
| No fixture for a `[D]` deviation that is consistent and stated | Medium | §8.1 says that PASSes; no fixture pins the behaviour, so a regression to "any deviation is a finding" would not be caught |
| No fixture where a `[D]` rule escalates because its declared trigger is live | Low | Item 11 declares T5 and API-020 exercises it, but nothing tests that an *undeclared* trigger fails to escalate — AD017 covers the doc side only |
| Long-running operation (202 Accepted) fixture | Low | 202 is covered by AD016 as a table row, but no scenario exercises an async flow end to end |
| Webhook API design fixture | Low | Mentioned in consumer types, no dedicated fixture |
| gRPC/Protobuf, GraphQL | N/A | Explicitly out of scope for a REST skill |

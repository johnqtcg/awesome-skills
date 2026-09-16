# Deep Research Rule-to-Behavior Coverage

The suite separates normative text checks from executable behavior. A fixture value is never accepted as proof that the implementation made the same decision.

## Executable Integrity Tests

`test_evidence_integrity.py` drives public functions and the real parser.

| Behavior | Verification |
|---|---|
| Single fact → Quick | Call `plan_research` and assert mode/budget |
| Security-sensitive decision → Deep | Call `plan_research` |
| Explicit mode wins | Call `plan_research(..., explicit_mode=...)` |
| Pure codebase suppresses web | Assert `research_kind=codebase` and no content requirement |
| 51 queries rejected | Parse real `retrieve --mode deep` arguments |
| Per-mode query ceiling | Parse 11 Quick queries and expect failure |
| Web content is mandatory | Parse real `report` arguments without `--content` |
| Serialized excerpt supports a bounded claim | Validate URL, extraction success, exact excerpt, and Medium ceiling |
| Failed/missing extraction blocks High | Validate failed and absent content artifacts |
| Mixed valid/invalid references cannot be Full | Validate one supported and one unresolved evidence reference |
| Legacy citation is unverified | Validate a URL-only finding |
| Caller-authored T1/live fields cannot be High | Load hostile results/content JSON and require validator-derived T4 + Medium |
| Current live T1 fact may be High | Use a validator-controlled capture and run full confidence assessment |
| Effective final URL controls authority | Redirect a requested T1 URL to a T4 final URL and require downgrade |
| Live verification replaces serialized content | Mock the current safe capture and assert the caller artifact is not reused |
| Unpinned code cannot be High | Validate code evidence with `commit=unknown` |
| Working-tree labels are not commit pins | Validate `working-tree-unpinned` against the real confidence assessor |
| Single-fact T1 exception is web-only | Pass code evidence to `single_fact` and require downgrade |
| Runtime behavior needs bound host receipt | Validate pass state, one-receipt complete `covers`, relevance, all tested paths, and matching clean commit/tree |
| Code, commit, test are first-class | Validate repository evidence IDs without URLs |
| Hybrid uses both evidence families | Validate missing web/repository support as Partial |
| Extraction ceiling propagates | Run the real report command with a content artifact marked budget-exhausted |
| Empty findings cannot be Full | Run degradation assessment |
| Exact nine-section report | Compare the ordered top-level heading list |
| Actual counts and T1–T5 notes | Inspect generated report fields |
| Codebase source quality is explicit | Inspect commit-pinning and passing-test counts in a generated report |

`test_web_security.py` exercises the Web trust and egress boundary without
making real network requests.

| Behavior | Verification |
|---|---|
| HTTP(S) only | Reject `file:`, FTP, gopher, and URL credentials |
| Non-public literals rejected | Cover IPv4/IPv6 loopback, private, link-local, metadata, unspecified, reserved, and multicast |
| Mixed DNS fails closed | Return one public and one private answer; reject the hostname |
| Redirect targets are revalidated | Public first hop redirects to metadata; assert no second request |
| DNS rebinding window is closed | Assert the connection uses the IP returned by the validated resolution |

`test_repository_integrity.py` uses temporary real Git repositories rather
than trusting fixture labels.

| Behavior | Verification |
|---|---|
| Dirty content is not attributed to HEAD | Change a tracked file, run code search, assert `working-tree-unpinned` |
| Pinned code is real | Resolve commit with `cat-file`, read blob, and match declared line/excerpt |
| Commit subject is real | Compare evidence subject with `git show` |
| Forged path/commit/line/excerpt is rejected | Mutate one field at a time and assert a typed issue |
| Working-tree path is bounded | Reject paths outside the declared repository root |
| Legacy handwritten pass state is untrusted | Reject receipts outside the versioned host schema |
| Generic command proxy is absent | Assert `run-test`, replay flags, and `run_test_command` are absent |
| Receipt import is non-executing | Import an attested receipt whose audit argv is not executable |
| Semantic coverage is explicit | Negative-test missing claim/code IDs and relevance approval |
| Code/test snapshots are bound | Negative-test dirty, mismatched commit/tree, and omitted tested path |
| Complete cited-code set is atomic | Reject unresolved references, pinned + unpinned mixtures, split receipt coverage, and multiple code commits |
| Snapshot metadata is read-only | Assert clean/dirty HEAD/tree identity; fail closed outside Git and when output would dirty the repository |

`test_session_budget.py` exercises the state machine and source selector.

| Behavior | Verification |
|---|---|
| Retrieval is cumulative | Two reservations share one locked session ledger |
| Extraction is cumulative | Repeated commands can use only the remaining allowance |
| Session mode cannot drift | **Not currently exercised.** `session.py` rejects a conflicting `expected_mode`, but no test passes one; the branch is live in `cmd_*` and untested |
| Concurrent writes are serialized | Race 20 processes for 10 slots and assert exactly 10 reservations |
| External tools share the ledger | Exercise `reserve-budget` through the CLI |
| Ledger reset is refused | Attempt to initialize an existing session path |
| Report-source ceiling executes | Quick blocks the ninth cited evidence unit |
| Uncited candidates are omitted | Source index is derived from usable finding references |
| Multilingual planning | Chinese repository request → codebase; deep cloud-security comparison → Deep |

## Fixture-Driven Decisions

`test_golden_scenarios.py` loads user requests from fixtures and passes them into executable functions.

| Fixture | Executed decision |
|---|---|
| `behavior_mode_quick` | Quick mode |
| `behavior_mode_deep_security` | Deep mode |
| `behavior_mode_user_override` | Explicit Standard override |
| `fp_quick_prevents_over_research` | Quick instead of Deep |
| `fp_codebase_no_web_retrieval` | Codebase kind without web |
| `behavior_degradation_blocked` | Budget/extraction state → Blocked |
| `behavior_confidence_high` | T1 primary content → High |
| `behavior_confidence_medium` | Three-method comparison → Medium |

The remaining eight keyword fixtures check reference discoverability for debugging, comparison, hallucination, codebase, benchmark, security, evidence-chain, and artifact-based tool-selection guidance. They are not labeled behavioral tests.

## Contract Bridges

`test_skill_contract.py` checks both text structure and the documentation-to-code seam:

- eight gates appear in order;
- the reference contains exactly one ordered nine-section heading set;
- `report` calls `validate_research_bundle`;
- `validate` and `report` document `--content` and `--code-evidence`;
- script constants implement Quick/Standard/Deep budgets;
- the single-T1 High exception is present and the old universal-two-domain wording is absent;
- serialized Web authority is explicitly untrusted and `--live-web` bridges
  documentation to the executable validator;
- the public-network-only transport and Web trust reference exist;
- code, commit, and test evidence kinds exist;
- named AI-product rankings are absent;
- SKILL.md stays within 500 lines.

## CLI Smoke Coverage

`test_subcommand_smoke.py` executes every output-writing subcommand offline:

- `plan`
- `validate`
- `report`
- `fetch-content`
- `search-codebase`
- `snapshot-codebase`
- `import-test-receipt`
- `reserve-budget`

It also rejects file/loopback URLs before budget reservation and introspects
the parser so documented flags cannot drift from accepted flags.

**Known gap, stated rather than implied:** `retrieve`, `snapshot-codebase` and
`import-test-receipt` appear here only as parse-only argv, and no successful
`fetch-content` is executed. A guaranteed `AttributeError` in `cmd_retrieve`'s
persist step was confirmed to ship with the whole suite green. The list above
describes which subcommands are *covered by a smoke test*, not which are
executed end to end.

## Current Summary

| Metric | Count |
|---|---:|
| Total tests | 397 |
| Golden fixtures | 16 |
| Claim-support corpus cases | 30 |
| Behavioral fixtures executed through code | 8 |
| Keyword fixtures | 8 |
| Canonical top-level report sections | 9 |
| Evidence kinds | 4 (`web`, `code`, `commit`, `test`) |

These counts are not prose. `test_skill_contract.py` reads this table and
compares each number with what discovery actually finds, so a stale figure
fails the regression instead of quietly misreporting coverage.

## Claim Support

`test_claim_support.py` answers a question the rest of the suite does not: it
checks whether a claim is supported by the excerpt it cites, not merely whether
the excerpt exists on the page.

| Behavior | Verification |
|---|---|
| A claim that inverts its own excerpt cannot ship | Run the real bundle validator and assert not-Full, not-usable, and the typed issue |
| A faithful but unreviewed claim is capped below High | Same validator, assert Medium and `partially-reviewed` |
| A faithful, attested claim reaches High | Same validator, assert Full and High |
| Correct findings are not flagged | Screen every `supported` corpus case; the allowed false-conflict count is 0 |
| Real contradictions are flagged | Screen every `conflict` corpus case against a recall floor stored in the corpus |
| The method's boundary stays visible | `lexically-opposed` cases must keep tripping the screen; if one stops, reclassify it deliberately |
| Each screen mechanism is load-bearing | Remove negators, clause scoping, hyphen joining, and multi-length anchor search in turn and assert each removal regresses |
| The report never lets one verdict imply the other | Assert the rendered report names citation integrity and claim support separately |
| A malformed or bare attestation cannot approve | Feed non-dict, unknown-stance, and too-short-rationale blocks |
| The authority registry fails closed | Point the loader at a missing file and assert no entries |
| Vendor-self docs are not an independent primary | Assert a two-unit vendor-only High request downgrades |

## Guards Added After the 2026-09-16 Audit

Each row names the defect that was reproduced by execution first, then the test
that now fires the guard. Every one was mutation-checked: deleting the guard
turns the named test red.

| Guard | Defect it closes | Test |
|---|---|---|
| `primary` tracks `pinned` | Two `.txt` files in a non-Git directory reached `Full`+`high` for a subjective comparison | `test_unpinned_code_is_never_an_independent_primary_unit` (+ pinned positive control) |
| Receipt `dirty` recomputed | A receipt declaring `dirty: false` over an edited tree yielded `snapshot_clean`+`primary`, while `repository_snapshot()` sat unused in the same module | `test_receipt_claiming_clean_over_dirty_tracked_content_is_rejected`, plus honest-dirty and untracked-artifact controls |
| Relevance floor on Web excerpts | The excerpt `"the"` satisfied containment; an unrelated excerpt scored as "no objection" | `RelevanceFloorOnWebExcerpts` (4 cases + corpus threshold) |
| Claim must exist | Empty `title`+`analysis` was `usable` and `attested`, rendering as "**Untitled finding**" | `FindingsMustStateAClaim` |
| Registry user-content exclusion | `discuss.python.org`, `issues.apache.org`, `lore.kernel.org` classified T1 `official` | `TestRegistryUserContentExclusion` (+ docs-host positive control) |
| Artifacts bound to their ledger | A report printed one ledger's "Budget consumed" for evidence collected under another | `ArtifactsAreBoundToTheirLedger` |
| `--check-live` is budgeted | It opened one HEAD per URL, with retries and redirects, against no ledger | `LiveReachabilityIsBudgeted` |
| WAF marker qualified | `"ray id"` matched "array identifier" and silently destroyed every excerpt from the page | `TestAntiBotMarkerPrecision` |
| Untested `web.py` guards | 14 of 18 raises never executed | `TestPreviouslyUncoveredGuards` |
| Report carries its excerpt | The verified quote was validated then discarded before rendering | `ReportCarriesItsOwnEvidence` |
| Bundled-asset inventory | The hand-maintained list had drifted by five files | `TestBundledAssetInventory` (both directions) |
| `allowed-tools` anchoring | Ten leading-`*` rules constrained neither the command nor the file | `test_allowed_tools_scope_helper_script_by_safe_subcommand` (allow-list shape) |
| Skips fail the gate | `run_regression.sh` exited 0 with `OK (skipped=7)` when `rg` was absent | `run_regression.sh` declares its dependencies and fails on any skip |

### Unmasking, not just adding

Four tests in `TestCodebaseEvidence` built findings with no `support_review`,
so `unreviewed` forced `medium` before any repository gate was consulted. Their
assertions could not discriminate: mutating `passed = status == "passed" and
exit_code == 0` to `passed = True` — a failed test receipt accepted as runtime
proof — left the entire suite green. Adding the attestation those fixtures were
missing makes that mutation fail `test_failed_test_does_not_verify_runtime_behavior`.

The lesson generalises past this file: a suite can prove every guard rejects
malformed input and still never ask what the cheapest *well-formed* input
reaching the top grade is.


## Adding Coverage

1. Add a fixture only when it contains a reusable user request or source artifact.
2. Call the executable decision/validator/renderer in the test.
3. Assert the observed result, not the fixture's own expected field.
4. Add a negative case for every new integrity rule.
5. Update this matrix after the regression passes.
6. Mutation-check the guard: delete it, confirm the new test fails, restore.
   A test that passes either way documents an intention, not a constraint.
7. Add a positive control. A guard satisfied by rejecting everything is not a
   guard, and every negative test in this suite should have something that
   proves the accepting path still works.

# Security Review — Rule-to-Scenario Coverage Matrix

Maps each core rule/gate in SKILL.md to its golden fixture and contract test. Use this to identify coverage gaps when adding new rules.

## Contract Tests (`test_skill_contract.py`)

| Rule / Section | Test | Status |
|----------------|------|--------|
| Frontmatter name | `test_frontmatter_name` | ✅ |
| Frontmatter description | `test_frontmatter_description_not_empty` | ✅ |
| Confidence labels (confirmed/likely/suspected) | `test_evidence_confidence_labels` | ✅ |
| Severity levels (P0-P3) | `test_severity_levels` | ✅ |
| 4 suppression rules | `test_suppression_rules_count` | ✅ |
| SLA for all levels | `test_remediation_sla_all_levels` | ✅ |
| Review depth (Lite/Standard/Deep) | `test_review_depth_*` (3 tests) | ✅ |
| 15-step process | `test_process_has_15_steps` | ✅ |
| Gates A-F exist | `test_all_gates_exist` | ✅ |
| Gate A constructor-release | `test_gate_a_constructor_release` | ✅ |
| Gate B resource inventory | `test_gate_b_resource_inventory`, `test_gate_b_references_detail` | ✅ |
| Gate C lifecycle contract rules (independent) | `test_gate_c_lifecycle_contract_rules` | ✅ |
| Gate D 10 domains | `test_gate_d_10_domains` | ✅ |
| Gate E falsification | `test_gate_e_falsification` | ✅ |
| Gate F uncovered risk | `test_gate_f_uncovered_risk` | ✅ |
| 11 scenario checklists | `test_scenario_checklist_has_11_scenarios` | ✅ |
| Go-specific sinks | `test_go_specific_sinks_in_checklist` | ✅ |
| Container security | `test_container_security_in_checklist` | ✅ |
| Concurrency security | `test_concurrency_security_in_checklist` | ✅ |
| Go secure-coding reference | `test_go_secure_coding_*` (3 tests) | ✅ |
| Language extension references | `test_lang_references_*` (4 tests) | ✅ |
| 9 output sections | `test_output_contract_sections` | ✅ |
| Finding example | `test_finding_example_exists` | ✅ |
| JSON schema | `test_json_summary_schema` | ✅ |
| Risk acceptance approval | `test_risk_acceptance_requires_approval` | ✅ |
| Automation commands | `test_automation_commands_present` | ✅ |
| Tool interpretation rules | `test_tool_interpretation_rules` | ✅ |
| Standards mapping | `test_standards_mapping_present` | ✅ |
| SKILL.md line budget (≤ 500) | `test_skill_md_stays_within_line_budget` | ✅ |
| Anti-examples inline stubs (AE-1, AE-3, AE-5) | `test_anti_examples_inline_stubs_exist` | ✅ |
| Anti-examples reference (AE-2, AE-4, AE-6, AE-7) | `test_anti_examples_reference_has_extended_rules` | ✅ |
| N/A judgment examples section | `test_na_judgment_examples_section_exists` | ✅ |
| Finding volume cap (P0/P1 never dropped; P2/P3 soft cap) | `test_finding_volume_cap_documented` | ✅ |
| Change Origin Classification (introduced/pre-existing/uncertain) | `test_change_origin_classification_documented` | ✅ |
| Baseline Diff Mode (new/regressed/unchanged/resolved + "Baseline not found") | `test_baseline_diff_mode_documented` | ✅ |
| Drift guard: aids reference must not restate normative rules (suppression/SLA/labels/etc.) | `test_aids_reference_does_not_duplicate_normative_rules` | ✅ |
| Description has "Use when" trigger + boundary vs go-review-lead / go-security-review | `test_frontmatter_description_has_trigger_and_boundary` | ✅ |

## Golden Fixtures (`test_golden_reviews.py`)

### True Positives (should produce a finding)

| ID | Scenario | Category | Severity | Coverage Rules Verified |
|----|----------|----------|----------|----------------------|
| GOLDEN-001 | IDOR: handler reads order without ownership check | auth | P1 | IDOR, authz checks |
| GOLDEN-003 | Hardcoded AWS API key in source | secrets | P1 | no hardcoded secrets, env-only |
| GOLDEN-005 | SQL injection via ORDER BY concatenation | injection | P1 | parameterized SQL, ORDER BY allowlist |
| GOLDEN-007 | TOCTOU race on balance (double-spend) | concurrency | P1 | TOCTOU, double-spend, concurrency safety |
| GOLDEN-008 | HTTP response body not closed on error path | resource_lifecycle | P2 | http.Response.Body, resource closure |
| GOLDEN-009 | JWT validation without algorithm restriction (alg=none) | session | P1 | JWT alg constraints, alg=none rejection |
| GOLDEN-010 | Path traversal via filepath.Join without prefix check | injection | P1 | filepath.Join traversal, path validation |
| GOLDEN-011 | Dockerfile running as root (no USER directive) | container | P2 | non-root user, container security |
| GOLDEN-012 | Concurrent map write causing fatal crash (DoS) | concurrency | P1 | concurrent map, shared state sync |
| GOLDEN-013 | Missing http.MaxBytesReader on endpoint | endpoint | P2 | MaxBytesReader, body size limit |
| GOLDEN-014 | text/template for HTML rendering (XSS) | injection | P1 | text/template vs html/template, XSS |
| GOLDEN-015 | Open redirect via http.Redirect with user URL | endpoint | P2 | open redirect, redirect validation |
| GOLDEN-016 | SSRF via user-controlled URL in http.Client | ssrf | P1 | SSRF, allowlist, private IPs |
| GOLDEN-017 | Timing attack via == on API key | crypto | P2 | subtle.ConstantTimeCompare, Timing Attacks |
| GOLDEN-018 | Integer overflow in financial calculation | injection | P1 | Integer overflow, financial calculation |
| GOLDEN-021 | **Python** RCE via `pickle.loads` on request body | deserialization | P0 | pickle, Domain 8 (Language-Specific Injection Sinks) |
| GOLDEN-022 | **Node.js** prototype pollution via recursive merge of `req.body` | prototype_pollution | P1 | Prototype pollution, Domain 8 |
| GOLDEN-024 | **Java** RCE via `ObjectInputStream.readObject` on request body | deserialization | P0 | readObject on untrusted input, Domain 8 |
| GOLDEN-027 | **Python** XXE via `lxml` `iterparse` below 6.1.0 (CVE-2026-41066) | xxe | P1 | iterparse, CVE-2026-41066, Domain 8 |

### False Positives (should be suppressed)

| ID | Scenario | Category | Suppression Rule Verified |
|----|----------|----------|--------------------------|
| GOLDEN-002 | Parameterized SQL (not injection) | injection | Rule 3: framework guarantees |
| GOLDEN-004 | InsecureSkipVerify in test-only code | tls | Rule 4: environment-only risk |
| GOLDEN-006 | math/rand for display shuffle (non-security) | randomness | Rule 2: not attacker-controlled |
| GOLDEN-019 | SSRF suppressed by server-side allowlist | ssrf | Rule 2: not attacker-controlled |
| GOLDEN-020 | ConstantTimeCompare already used correctly | crypto | Rule 3: framework guarantees |
| GOLDEN-023 | **Node.js** `execFile` with an argv array (no shell) | injection | Rule 3: framework guarantees |
| GOLDEN-025 | **Java** `DocumentBuilderFactory` already hardened (`disallow-doctype-decl`) | xxe | Rule 3: framework guarantees |
| GOLDEN-026 | **Python** stdlib `ElementTree` reported as XXE / billion-laughs | xxe | Rule 3: parser resolves no external entity; Expat ≥ 2.4.0 refuses amplification |

GOLDEN-026 and GOLDEN-027 are a deliberately matched pair: the same category (`xxe`), the same
stack, opposite verdicts, decided by **which library and which version** the call site uses. That
pairing is what keeps the Python XML guidance version-gated instead of blanket in either
direction — see `../../references/lang-python.md § Python XML` and the executable matrix at
`examples/python/xml_facts_test.py`.

## Coverage Summary

| Metric | Count |
|--------|-------|
| Total golden fixtures | 27 |
| True positives | 19 |
| False positives | 8 |
| Categories covered | auth, secrets, injection, concurrency, resource_lifecycle, session, container, endpoint, ssrf, crypto, deserialization, prototype_pollution, xxe |
| Stacks with both polarities | go, python, nodejs, java (enforced by `test_every_supported_stack_has_a_behavioural_fixture`) |
| Contract tests | 60 |
| Golden-fixture tests | 37 |
| Executable-example tests | 48 |
| Forward-eval tests | 40 |
| Report-schema tests | 60 |
| **Total tests** | **245** |
| SKILL.md lines | 410 (budget: ≤ 500, 90 lines headroom) |

These counts are **self-checking** — `test_skill_contract.py::TestCoverageDocAccuracy` recomputes
them from disk and fails if this table drifts. They previously read 46 tests / 494 lines while the
real values were 48 / 500.

**Why `pytest` reports more than `Total tests`.** The number above counts the five `test_*.py`
layer modules. `examples/python/xml_facts_test.py` adds 18 more: it is driven as a subprocess by
`test_examples_executable.py` (so it participates in the layer accounting through that one test),
but its filename also matches pytest's `*_test.py` pattern, so `python3 -m pytest
skills/security-review` collects it directly and reports 263. Both numbers are correct for what
they count; neither is the other's error.

## Test Layers

| Layer | File | Validates | Blind to |
|---|---|---|---|
| 1. Contract | `test_skill_contract.py` | documents contain the required rules and do not contradict each other | whether following them finds anything |
| 2. Golden fixtures | `test_golden_reviews.py` | fixture metadata complete; rule strings present in docs | the review itself |
| 3. Executable examples | `test_examples_executable.py` | GOOD example code compiles **and is actually safe** (SSRF guard blocks, `os.Root` contains, Go and Python XML facts hold against the real runtime) | the review itself |
| 4. **Forward eval** | `test_forward_eval.py` | a graded **review**: finds the real bug, suppresses the false positive, correct severity/confidence/CWE/pinned-ASVS, stack-neutral JSON, no fabricated execution | whether a *live* model passes — that needs the opt-in hook |
| 5. Report schema | `test_report_schema.py` | the § 7 JSON block validates against `references/report-schema.json`, `summary.pass` matches its computation both ways, ASVS versions are not mixed, counts reconcile with `findings[] + overflow`, and every good exemplar conforms | whether the *prose* sections are right |

Layer 4 is the answer to "does the skill actually work?"; layers 1-3 and 5 only answer "is the
skill well-formed?". See `forward_eval/README.md` for the honesty boundary.

### Layer 3 coverage by stack

| Stack | Executable probe | Verifies |
|---|---|---|
| Go | `examples/go` (`go test ./...`) | SSRF guard blocks loopback/private/IMDS; `os.Root` containment; §Go XML facts (no `MaxDepth` field, no entity expansion) |
| Node.js | `examples/node` (`node --test`) | `safeTokenEqual` never throws on attacker-chosen lengths; raw-buffer misuse raises `RangeError` |
| Python | `examples/python/xml_facts_test.py` | every row of §Python XML: no stdlib XXE (ElementTree, minidom, AND sax — each run directly, not inferred from ElementTree), `sax`'s `feature_external_ges` opt-in reopens it, bounded substitution occurs, amplification bomb refused on Expat ≥ 2.4.0, lxml ordinary parsers safe since 5.0.0, `iterparse`/`ETCompatXMLParser` XXE below 6.1.0 (CVE-2026-41066), `no_network=False` alone makes no fetch attempt |
| Java | **none** | Known gap: the Java guidance has golden + forward-eval coverage (GOLDEN-024/025) but no compiled probe, so its `disallow-doctype-decl` claim is asserted from documentation rather than measured. Adding one requires a JDK + Maven in CI. |

## Gap Analysis

When adding a new rule to SKILL.md or references:

1. Add a golden fixture (true-positive or false-positive) that exercises the rule.
2. Add a contract test that verifies the rule text exists.
3. Update this matrix.

### Known Coverage Gaps (TODO for future fixtures)

| Scenario | Category | Priority |
|----------|----------|----------|
| CORS wildcard with credentials | cors | Low |
| Rate limiting absence on login endpoint | endpoint | Low |
| `template.HTML()` abuse (safe template with unsafe cast) | injection | Low |
| FP: `InsecureSkipVerify` behind VPN with mTLS | tls | Low |
| FP: `os/exec.Command` with hardcoded binary | injection | Low |
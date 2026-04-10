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
| SKILL.md line budget (≤ 600) | `test_skill_md_stays_within_line_budget` | ✅ |
| Anti-examples inline stubs (AE-1, AE-3, AE-5) | `test_anti_examples_inline_stubs_exist` | ✅ |
| Anti-examples reference (AE-2, AE-4, AE-6, AE-7) | `test_anti_examples_reference_has_extended_rules` | ✅ |
| N/A judgment examples section | `test_na_judgment_examples_section_exists` | ✅ |
| Finding volume cap (P0/P1 never dropped; P2/P3 soft cap) | `test_finding_volume_cap_documented` | ✅ |
| Change Origin Classification (introduced/pre-existing/uncertain) | `test_change_origin_classification_documented` | ✅ |

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

### False Positives (should be suppressed)

| ID | Scenario | Category | Suppression Rule Verified |
|----|----------|----------|--------------------------|
| GOLDEN-002 | Parameterized SQL (not injection) | injection | Rule 3: framework guarantees |
| GOLDEN-004 | InsecureSkipVerify in test-only code | tls | Rule 4: environment-only risk |
| GOLDEN-006 | math/rand for display shuffle (non-security) | randomness | Rule 2: not attacker-controlled |

## Coverage Summary

| Metric | Count |
|--------|-------|
| Total golden fixtures | 18 |
| True positives | 15 |
| False positives | 3 |
| Categories covered | auth, secrets, injection, concurrency, resource_lifecycle, session, container, endpoint, ssrf, crypto |
| Contract tests | 43 |
| SKILL.md lines | 546 (budget: ≤ 600) |

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
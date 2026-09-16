# Bundled Assets

Every file this skill ships, excluding `SKILL.md` itself and Python bytecode.

`scripts/tests/test_skill_contract.py` compares this list against the directory
**in both directions**: a file on disk that is missing here fails, and an entry
here with no file fails. The previous inventory lived in `SKILL.md`, was
maintained by hand, and had drifted by five files — including
`scripts/run_regression.sh` and the two largest test files — with nothing to
catch it. An inventory nobody checks is a claim, not a record.

| Path | Role |
|---|---|
| `references/bundled-assets.md` | this inventory |
| `references/hallucination-and-verification.md` | verification, confidence, and source-quality protocol |
| `references/output-contract-template.md` | canonical schema and report template |
| `references/research-patterns.md` | programmer-focused research patterns |
| `references/source-authority-registry.json` | curated domain-to-authority registry |
| `references/test-receipt-schema.md` | host receipt schema, snapshot binding, and relevance rules |
| `references/web-evidence-and-egress.md` | Web provenance state machine and safe-egress contract |
| `scripts/deep_research.py` | compatibility CLI plus the shared validation and report engine |
| `scripts/deep_research_lib/__init__.py` | package marker |
| `scripts/deep_research_lib/authority.py` | curated source-authority registry lookup and user-content exclusion |
| `scripts/deep_research_lib/claim_support.py` | claim-support attestation plus polarity, numeric, and relevance screens |
| `scripts/deep_research_lib/planning.py` | multilingual classification, routing confidence, and mode budgets |
| `scripts/deep_research_lib/reporting.py` | cited-source selection and ceiling enforcement |
| `scripts/deep_research_lib/repository.py` | Git provenance, read-only snapshot metadata, and static host-receipt verification |
| `scripts/deep_research_lib/session.py` | cross-process locked, cumulative session-budget ledger |
| `scripts/deep_research_lib/web.py` | public-network-only HTTP(S), DNS/IP pinning, TLS hostname verification, redirect revalidation |
| `scripts/run_regression.sh` | the regression entry point; fails on a missing dependency or any skip |
| `scripts/tests/COVERAGE.md` | rule-to-behavior coverage matrix; its counts are derived and asserted |
| `scripts/tests/claim_support_corpus.json` | adversarial claim-vs-excerpt corpus with recall and false-positive thresholds |
| `scripts/tests/golden/behavior_confidence_high.json` | see file header |
| `scripts/tests/golden/behavior_confidence_medium.json` | see file header |
| `scripts/tests/golden/behavior_degradation_blocked.json` | see file header |
| `scripts/tests/golden/behavior_mode_deep_security.json` | see file header |
| `scripts/tests/golden/behavior_mode_quick.json` | see file header |
| `scripts/tests/golden/behavior_mode_user_override.json` | see file header |
| `scripts/tests/golden/codebase_research.json` | see file header |
| `scripts/tests/golden/error_debugging.json` | see file header |
| `scripts/tests/golden/evidence_chain.json` | see file header |
| `scripts/tests/golden/fp_codebase_no_web_retrieval.json` | see file header |
| `scripts/tests/golden/fp_quick_prevents_over_research.json` | see file header |
| `scripts/tests/golden/hallucination_awareness.json` | see file header |
| `scripts/tests/golden/performance_benchmark.json` | see file header |
| `scripts/tests/golden/security_research.json` | see file header |
| `scripts/tests/golden/tech_comparison.json` | see file header |
| `scripts/tests/golden/tool_selection_principles.json` | see file header |
| `scripts/tests/test_claim_support.py` | screen mutation harness and corpus thresholds |
| `scripts/tests/test_deep_research.py` | unit coverage for parsing, extraction, classification, and rendering |
| `scripts/tests/test_evidence_integrity.py` | evidence-chain and negative behavioral tests |
| `scripts/tests/test_golden_scenarios.py` | fixture request to executable decision tests |
| `scripts/tests/test_repository_integrity.py` | dirty-tree, forged Git, receipt binding, and command-proxy negative tests |
| `scripts/tests/test_session_budget.py` | cumulative/multiprocess budget and report-source ceiling tests |
| `scripts/tests/test_skill_contract.py` | documentation-to-code seam; guards this file and SKILL.md |
| `scripts/tests/test_subcommand_smoke.py` | offline CLI end-to-end tests |
| `scripts/tests/test_web_security.py` | local-scheme, private-address, mixed-DNS, redirect, and DNS-pinning negative tests |

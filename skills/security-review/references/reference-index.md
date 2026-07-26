# Reference Loading Guide & Asset Index

## Language/Framework Reference Selection

Gate D's **ten domains are stack-independent** — same numbers, same names, every stack. Defined
once in `authorization-and-policy.md` §2. Selecting a stack reference does **not** replace or
renumber them; it supplies the per-stack evidence for the same ten axes. All other gates,
scenario checklists, severity model, and output contract are unchanged.

For a mixed-stack repo, emit one coverage section per detected stack and set `stack` to a
comma-joined list; a domain is `FAIL` for the repo if it fails in any stack.

| Stack | Reference | Domain 8 (Language-Specific Sinks) highlights |
|-------|-----------|----------------------------------------------|
| Go | `references/go-secure-coding.md` | `text/template`, `exec`, redirect, `filepath` traversal, Go XML exemptions |
| Node.js / TypeScript | `references/lang-nodejs.md` | prototype pollution, ReDoS, SSRF, `vm`/`eval` |
| Java / Spring | `references/lang-java.md` | Java deserialization, SpEL, XXE (applies, unlike Go) |
| Python / FastAPI / Django | `references/lang-python.md` | `eval`/`pickle`, SSTI, XXE via stdlib parsers, `tarfile` traversal |

## Loading Guide by Depth and Stack

Read only the references needed for the current review. The review depth and language determine what to load.

For Go code at Standard or Deep depth:
→ Load `references/go-secure-coding.md` for Gate B resource inventory table (HTTP handlers, DB queries, file ops, goroutines, crypto) and Gate D 10-domain deep-dive (injection, auth, crypto, SSRF, race conditions, secrets, input validation, error handling, logging, dependencies).
→ Load `references/scenario-checklists.md` for the full 11-scenario checklist (web API, CLI, background worker, gRPC service, etc.) with per-item PASS/FAIL/N/A fields and Go-specific subsections.

For Go code at Lite depth (**do not load `go-secure-coding.md`** — Gate B/C/E are skipped):
→ Load `references/scenario-checklists.md` only, for scenario-scoped checklist items applicable to Lite gate coverage.

For Node.js / TypeScript code:
→ Load `references/lang-nodejs.md` for injection patterns, prototype pollution, ReDoS, SSRF, middleware order issues, and TypeScript-specific type-safety bypass risks.
→ Load `references/scenario-checklists.md` for the cross-language scenario checklist.

For Java / Spring code:
→ Load `references/lang-java.md` for deserialization vulnerabilities, SpEL/SQL injection, `@PreAuthorize` annotation gaps, config secrets exposure, and Spring Security misconfiguration patterns.
→ Load `references/scenario-checklists.md` for the cross-language scenario checklist.

For Python / FastAPI / Django code:
→ Load `references/lang-python.md` for `eval`/`pickle` misuse, SSTI, ORM safety gaps, async blocking risks, and dependency audit patterns.
→ Load `references/scenario-checklists.md` for the cross-language scenario checklist.

For general or multi-language reviews:
→ Load `references/scenario-checklists.md` only for the language-agnostic scenario checklist (~1,200 tokens).

When severity or confidence decisions feel ambiguous, or before publishing findings:
→ Load `references/severity-calibration.md` for confidence downgrade rules, severity scoring matrix, common finding patterns with calibrated severity levels, and CVSS estimation guidance.

When the report needs additional anti-examples for quality validation or reviewer training:
→ Load `references/anti-examples.md` for extended anti-examples (AE-2 through AE-7) covering N/A abuse, confirmed-without-reproducer, P0-acceptance-without-escalation, and transitive call path omissions.

When seeding trust-boundary analysis, writing the suggested regression/negative test for a finding, or mapping findings to CWE/OWASP ASVS:
→ Load `references/security-review.md` for the quick threat prompts, minimal negative-test matrix, and CWE/ASVS mapping lookup table.

## Standards Mapping

The normative rule lives in `SKILL.md § Standards Mapping` (map each finding to `CWE-xxx` and `OWASP ASVS`; use `Mapping: TBD` with reason if unclear). For the full lookup table, load `references/security-review.md § CWE / OWASP ASVS Mapping Table` — do not maintain a second mapping list here.

## Asset Index

| File | Purpose |
|------|---------|
| `references/go-secure-coding.md` | Gate B resource inventory + Gate D 10-domain deep reference (Go only, Standard/Deep) |
| `references/scenario-checklists.md` | Full 11-scenario checklist with per-item details |
| `references/severity-calibration.md` | Severity + confidence calibration rules and common finding patterns |
| `references/anti-examples.md` | Extended anti-examples (AE-2, AE-4, AE-6, AE-7) |
| `references/security-review.md` | Supplementary aids: threat prompts, negative-test matrix, CWE/ASVS mapping table (normative rules live only in `SKILL.md`) |
| `references/lang-nodejs.md` | Node.js/TypeScript domain-specific gates |
| `references/lang-java.md` | Java/Spring domain-specific gates |
| `references/lang-python.md` | Python/FastAPI/Django domain-specific gates |
| `references/reference-index.md` | This file: loading guide, language routing, asset index |
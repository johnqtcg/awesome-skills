# Deep Research Web Trust And Safe Egress Implementation Plan

**Goal:** Prevent caller-authored Web artifacts from reaching High and prevent
all deep-research network paths from accessing non-public targets.
**Mode:** Standard
**Architecture:** A new standard-library safe HTTP(S) module owns URL
validation, DNS policy, IP pinning, TLS, and redirects. The evidence validator
re-derives source authority and grants Web High only to fresh in-process
captures requested with `--live-web`.
**Tech Stack:** Python 3.12 standard library, unittest/pytest, MkDocs.
**Repo Discovery:** Python helper, unittest/pytest suite, macOS Python 3.12 CI,
five-layer bilingual documentation policy, and existing 286-test regression
wrapper were verified.

---

## Scope And Risk

- **Risk:** High — closes an SSRF/local-file-read path and tightens published
  confidence semantics.
- **In scope:** Every Python network egress path in deep-research, Web content
  provenance, tier derivation, CLI live verification, tests and documentation.
- **Out of scope:** A general organization authority registry, cryptographic
  host execution handles, browser-tool interception, or new dependencies.
- **Rollback:** Revert each phase as a unit. Never restore the old unsafe fetch
  path; if the safe client is incompatible, disable affected network commands
  and retain offline Medium-only validation until corrected.

## Task 1: Lock Both Exploits Into Failing Tests

**Files:**

- `skills/deep-research/scripts/tests/test_web_security.py` [New]
- `skills/deep-research/scripts/tests/test_evidence_integrity.py` [Existing]
- `skills/deep-research/scripts/tests/test_subcommand_smoke.py` [Existing]

**Steps:**

- [ ] Add direct `file://`, non-public IP, mixed DNS, redirect, and IP-pinning
  assertions.
- [ ] Add caller-authored T1 and serialized-content High negative cases.
- [ ] Add one positive live-verified, derived-T1 case.
- [ ] Run focused tests and record the expected pre-fix failures.

**Verification:**

```text
[command] rtk python3 -m unittest discover -s skills/deep-research/scripts/tests -p 'test_web_security.py' -v
[command] rtk python3 -m unittest discover -s skills/deep-research/scripts/tests -p 'test_evidence_integrity.py' -v
Expected before implementation: new security assertions fail.
```

## Task 2: Implement Safe Public HTTP(S) Transport

**Files:**

- `skills/deep-research/scripts/deep_research_lib/web.py` [New]
- `skills/deep-research/scripts/deep_research.py` [Existing]

**Steps:**

- [ ] Parse URL and reject non-HTTP(S), credentials, missing hosts, and invalid
  ports.
- [ ] Resolve every address and reject the target if any address is not
  globally routable.
- [ ] Connect to one validated address directly while preserving HTTP Host,
  HTTPS SNI, and certificate verification.
- [ ] Disable proxy inheritance and revalidate every redirect target.
- [ ] Route content retrieval, DDG retrieval, and live reachability through the
  same transport.
- [ ] Preflight `fetch-content` URLs before session-budget reservation.

**Verification:**

```text
[command] rtk python3 -m unittest discover -s skills/deep-research/scripts/tests -p 'test_web_security.py' -v
Expected: all scheme/address/redirect/pinning tests pass without network access.
```

**Rollback:** Keep unsafe schemes and non-public targets blocked even if HTTP
compatibility work must be reverted.

## Task 3: Enforce Validator-Owned Web High

**Files:**

- `skills/deep-research/scripts/deep_research.py` [Existing]
- `skills/deep-research/scripts/tests/test_evidence_integrity.py` [Existing]
- `skills/deep-research/scripts/tests/test_deep_research.py` [Existing]
- `skills/deep-research/scripts/tests/test_session_budget.py` [Existing]
- `skills/deep-research/scripts/tests/test_golden_scenarios.py` [Existing]

**Steps:**

- [ ] Record final URL, status, capture time, resolved IPs, and body/content
  hashes for audit.
- [ ] Mark reloaded content as untrusted regardless of serialized flags.
- [ ] Re-derive source quality from the effective final URL and ignore caller
  authority labels.
- [ ] Add `--live-web` to validation/report commands and securely refetch only
  cited Web URLs.
- [ ] Require live-verified, derived-T1 evidence for narrow single-fact High;
  otherwise retain usable Medium evidence with a precise downgrade reason.
- [ ] Update offline smoke fixtures to assert safe degradation instead of fake
  High.

**Verification:**

```text
[command] rtk python3 -m unittest discover -s skills/deep-research/scripts/tests -p 'test_evidence_integrity.py' -v
[command] rtk python3 -m unittest discover -s skills/deep-research/scripts/tests -p 'test_subcommand_smoke.py' -v
Expected: forged artifacts downgrade; live derived-T1 evidence reaches High.
```

**Rollback:** Preserve the rule that serialized content and caller tiers cannot
establish High.

## Task 4: Synchronize Skill And Five-Layer Contracts

**Files:**

- `skills/deep-research/SKILL.md` [Existing]
- `skills/deep-research/references/hallucination-and-verification.md` [Existing]
- `skills/deep-research/references/output-contract-template.md` [Existing]
- `skills/deep-research/references/research-patterns.md` [Existing]
- `skills/deep-research/scripts/tests/COVERAGE.md` [Existing]
- `rationale/deep-research/design.md` [Existing]
- `rationale/deep-research/design.zh-CN.md` [Existing]
- `evaluate/deep-research-skill-eval-report.md` [Existing]
- `evaluate/deep-research-skill-eval-report.zh-CN.md` [Existing]
- `bestpractice/Advanced.md` [Existing]
- `bestpractice/进阶篇.md` [Existing]
- `outputexample/deep-research/evidence-verified-codebase-report.md` [Existing]

**Steps:**

- [ ] Document safe-public-network policy and explicit live verification.
- [ ] Remove claims that caller-reviewed metadata can raise authority.
- [ ] State that capture hashes are audit metadata, not a trust root.
- [ ] Update bilingual rationale/evaluation/best-practice and coverage counts.

**Verification:**

```text
[command] rtk python3 -m unittest discover -s skills/deep-research/scripts/tests -p 'test_skill_contract.py' -v
[command] rtk python3 /Users/john/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/deep-research
Expected: contract and skill validation pass.
```

**Rollback:** Documentation must revert with behavior; do not preserve
statements stronger than the active implementation.

## Task 5: Full Validation

**Files:**

- `skills/deep-research/scripts/run_regression.sh` [Existing]

**Steps:**

- [ ] Run the full regression and pytest suite.
- [ ] Compile with an external pycache.
- [ ] Run direct negative CLI probes, `git diff --check`, and MkDocs.
- [ ] Update this plan and coverage counts with observed results.

**Verification:**

```text
[command] rtk bash skills/deep-research/scripts/run_regression.sh
[command] rtk python3 -m pytest skills/deep-research/scripts/tests -q
[command] rtk env PYTHONPYCACHEPREFIX=/tmp/deep-research-pycache python3 -m compileall -q skills/deep-research/scripts
[command] rtk git diff --check
[command] rtk mkdocs build
Expected: all functional gates pass; only documented baseline MkDocs warnings remain.
```

## Plan Review

**Status:** Approved

**Blocking Issues:** None.

**Non-Blocking Notes:**

- Authority inference is intentionally conservative and may downgrade valid
  vendor documentation to Medium.
- Live verification adds one explicit final network read per cited Web page.
- Tasks 2 and 3 are sequential because both modify the CLI module.

**Scorecard:** B: 6/6 | N: 7/7 | SB: 6/6
**Overall:** PASS

## Execution Handoff

Plan saved to
`docs/plans/2026-07-19-deep-research-web-trust-and-egress.md`.

Execution proceeds inline with test-first checkpoints. Sub-agent execution is
not used because delegation was not authorized.


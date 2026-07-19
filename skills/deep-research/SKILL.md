---
name: deep-research
description: |
  Perform auditable research with executable mode budgets, mandatory source-content verification, typed web and repository evidence, confidence assessment, honest degradation, and one fixed nine-section report.
  Use for web research, claim verification, technical comparisons, trend analysis, pure codebase research, and hybrid codebase-plus-web investigations that need traceable conclusions rather than search-result summaries.
allowed-tools: Read, Write, Grep, Glob, WebSearch, WebFetch, Bash(*deep_research.py plan*), Bash(*deep_research.py reserve-budget*), Bash(*deep_research.py retrieve*), Bash(*deep_research.py fetch-content*), Bash(*deep_research.py search-codebase*), Bash(*deep_research.py snapshot-codebase*), Bash(*deep_research.py import-test-receipt*), Bash(*deep_research.py validate*), Bash(*deep_research.py report*), Bash(git log*), Bash(go test*), Bash(python3 -m unittest*), Bash(python3 -m pytest*)
---

# Deep Research

Produce research whose claims can be traced to content actually read or repository artifacts actually observed.

## Quick Reference

| Need | Action |
|---|---|
| Classify `web | codebase | hybrid` and `quick | standard | deep` | Run `plan` before retrieval |
| Enforce cumulative query, extraction, and report-source ceilings | Reuse the session artifact created by `plan --output` |
| Author findings JSON | Load `references/output-contract-template.md` |
| Assess hallucination, confidence, or source quality | Load `references/hallucination-and-verification.md` |
| Understand Web trust boundaries and safe egress | Load `references/web-evidence-and-egress.md` |
| Apply programmer-specific query/evidence patterns | Load `references/research-patterns.md` |
| Claim runtime behavior from tests | Load `references/test-receipt-schema.md` |

## Mandatory Gates

Execute gates in strict order. Stop when a gate blocks later work.

```
1) Scope → 2) Ambiguity → 3) Evidence → 4) Research Mode
    → 5) Hallucination Awareness → 6) Budget Control
    → 7) Content Extraction → 8) Execution Integrity
```

### 1) Scope Classification Gate

Select one research kind and one goal.

- Research kind: `web | codebase | hybrid`
- Category: comparison, trend, claim verification, technical deep-dive, codebase audit
- Goal: Know, Compare, Verify, Recommend, or Audit

Run the executable classifier:

```bash
python3 scripts/deep_research.py plan \
  --request "<user request>" \
  --output /tmp/research_plan.json
```

The output is a versioned session ledger, not a disposable plan. Reuse that
exact file for every budget-consuming command in the research run.

Use `codebase` when the answer depends only on local code, commits, or test results. Do not perform web retrieval merely to manufacture URLs. Use `hybrid` only when external evidence is part of the question.

### 2) Ambiguity Resolution Gate

**STOP and ASK** when scope, comparison dimensions, time window, or success criteria would materially change the research. Do not ask again for constraints already supplied.

### 3) Evidence Requirements Gate

Define the evidence chain before retrieval.

| Conclusion Type | Minimum Evidence Chain | Target Confidence |
|---|---|---|
| Narrow single fact | 1 validator-controlled live capture + T1 re-derived from its effective final URL + exact supporting excerpt | High |
| Direct code fact | Code line/excerpt verified by reading the declared Git blob at an existing hexadecimal commit | High |
| Runtime code behavior | Every cited code item is pinned to one commit/tree + one host test receipt covers the finding and every code ID, names every tested path, passes relevance review, and matches that clean snapshot | High |
| Best-practice recommendation | 1 primary basis + 2 independent practitioner or empirical sources | Medium–High |
| Technology comparison | 3 independent benchmarks/reviews with methodology | Medium |
| Trend/adoption claim | 2 data sources from different periods | Medium |
| Disputed or fast-moving topic | 4 sources across tiers + explicit conflict treatment | Tiered |

Use typed evidence:

- Web: `{"kind":"web","url":"...","excerpt":"exact text from content.json"}`
- Code: `{"kind":"code","id":"code-1"}`
- Commit: `{"kind":"commit","id":"commit-head"}`
- Test: `{"kind":"test","id":"test-1"}`

Bare `citations` URLs are legacy inputs. Treat them as unverified because they do not prove extraction or claim support.

### 4) Research Mode Gate

Auto-select mode with `plan`; pass an explicit user mode as `--mode`.

| Signal | → Mode |
|---|---|
| Single factual question, "quick check" | Quick |
| Default research task | Standard |
| Thorough/deep request, multi-vendor decision, architecture/trend report | Deep |
| Security-sensitive or production-impacting decision | Deep |

| Mode | Retrieval Calls | Content Extractions | Report Sources |
|---|---:|---:|---:|
| Quick | 5–10 | max 5 | 3–8 |
| Standard | 15–25 | max 10 | 8–20 |
| Deep | 30–50 | max 15 | 15–40 |

If the user explicitly requests a mode, use it. Classification is deterministic and behavior-tested.

### 5) Hallucination Awareness Gate

Never fabricate citations, URLs, source metadata, code locations, commits, or test results.

| Risk Level | Information | Verification Method |
|---|---|---|
| High | API signature/configuration | Official primary documentation + validator-controlled live capture + extracted excerpt |
| High | Benchmark/statistic | Original data and disclosed methodology |
| High | Security/compliance | Official advisory, standard, or regulator |
| High | Repository behavior | Code evidence and, for runtime behavior, a passing test |
| Medium | Architecture recommendation | Independent sources with limitations |

Read `references/hallucination-and-verification.md` for confidence and source-quality rules.

### 6) Budget Control Gate

Use the selected mode as an executable ceiling:

```bash
python3 scripts/deep_research.py retrieve \
  --session /tmp/research_plan.json \
  --query "<subtopic 1>" \
  --query "<subtopic 2>" \
  --output /tmp/results.json
```

The parser also rejects more than 10, 25, or 50 queries in one Quick,
Standard, or Deep invocation. The session ledger atomically enforces those
same ceilings across repeated invocations, so two calls cannot each consume
the full allowance. The hard ceiling is 50 retrieval calls per Deep session.
One query consumes one retrieval call.

`fetch-content` defaults to the remaining session extraction allowance and
rejects an explicitly larger per-invocation `--limit`.
When more candidate URLs exist than the ceiling permits, it records `budget_exhausted=true`; bundled `validate` and `report` commands consume that state automatically.

Before bypassing `retrieve` or `fetch-content` with a host `WebSearch` or
`WebFetch` tool, reserve the equivalent count in the same ledger:

```bash
python3 scripts/deep_research.py reserve-budget \
  --session /tmp/research_plan.json \
  --budget retrieval_calls \
  --count 1 \
  --output /tmp/budget_reservation.json
```

The ledger is an operational concurrency-safe constraint, not a tamper-proof
audit log. It cannot account for tool calls that bypass both the bundled
commands and `reserve-budget`. `plan` refuses to overwrite an existing ledger.
Locking uses `fcntl` on POSIX and `msvcrt` byte locking on Windows, failing
closed if neither exists. The regression suite performs a real multi-process
contention test on fork-capable POSIX; the Windows backend still requires
Windows CI coverage.

### 7) Content Extraction Gate

For `web` and `hybrid`, fetch actual content before synthesis:

```bash
python3 scripts/deep_research.py fetch-content \
  --session /tmp/research_plan.json \
  --results /tmp/results.json \
  --output /tmp/content.json
```

Each web evidence object must identify an exact excerpt found in a successfully extracted item. A search snippet, reachable URL, or failed/low-yield page cannot support a finding.

Content extraction is mandatory for web and hybrid research.

`fetch-content` accepts only public `http`/`https` targets. It rejects
credentials, local/non-HTTP schemes, localhost, and every literal or
DNS-resolved address that is not public unicast. The transport connects to an
already validated IP while preserving hostname verification and repeats the
same validation before every redirect hop. This closes local-file reads,
metadata/private-network SSRF, mixed-DNS, and DNS-rebinding gaps.

Treat a saved `content.json` as an untrusted authoring and audit artifact.
Loading it always clears `live_verified`, even if the caller wrote that field.
It may support a Medium finding after excerpt matching, but it cannot establish
primary-source status or High confidence. For Web High, the final `validate`
or `report` command must use `--live-web`; that command freshly retrieves each
cited URL through the safe transport and derives source tier/type from the
effective final URL. Caller-provided `source_tier`, `source_type`, domain, and
classification-basis fields never grant authority.

For `codebase`, use `search-codebase`; content extraction is not required:

```bash
python3 scripts/deep_research.py search-codebase \
  --pattern "verifyToken" \
  --root /path/to/repo \
  --output /tmp/code_evidence.json
```

`search-codebase` checks provenance per matched file. Clean tracked content is
pinned to the real HEAD object ID. Modified, staged, or untracked content is
emitted as `working-tree-unpinned` and cannot support a High direct-code
finding. The validator independently checks that commits exist, reads
`<commit>:<path>`, and compares the declared line and excerpt. It also verifies
commit subjects against Git.

Execute a focused test once through the host's normal permission path. Then
create a `deep-research/host-test-receipt-v2` receipt and import it:

```bash
python3 scripts/deep_research.py snapshot-codebase \
  --root /path/to/repo \
  --output /tmp/repository_snapshot_before.json

go test -run TestVerifyToken ./auth

python3 scripts/deep_research.py snapshot-codebase \
  --root /path/to/repo \
  --output /tmp/repository_snapshot_after.json

python3 scripts/deep_research.py import-test-receipt \
  --receipt /tmp/host_test_receipt.json \
  --code-evidence /tmp/code_evidence.json \
  --output /tmp/code_and_test_evidence.json
```

`snapshot-codebase` only reads repository root, HEAD, tree hash, and dirty
state; it does not run tests or create execution proof. Write its output
outside the repository. The host should compare before/after snapshots and
copy the unchanged clean identity into the receipt. The helper never executes
receipt argv. It checks the versioned schema, real commit/tree and tested
paths, result metadata, and relevance decision.

Runtime High treats the finding's complete code evidence set as atomic: every
cited code item must be pinned, all must use one commit/tree, and one receipt
must cover the finding plus every code ID and tested path. Multiple receipts
cannot be combined to satisfy that coverage. Dirty, mismatched, unreviewed,
uncovered, or failed receipts are retained for audit context but cannot
support High.

This skill directly pre-approves only Go, pytest, and unittest test commands.
The receipt schema can describe Cargo, npm, Maven, Gradle, and .NET tests, but
those commands require normal host authorization. `Write` permits authoring
findings and receipt JSON; the host integration remains responsible for
truthful timestamps, complete-output hashes, and execution metadata.
Load `references/test-receipt-schema.md` for the full contract.

### 8) Execution Integrity Gate

- Do not present hypothetical findings if retrieval or repository inspection did not run.
- Distinguish "source says X" from "snippet mentions X".
- Report the actual number of retrieved, successfully extracted, repository, and cited evidence units.
- Run `validate` before manual synthesis checks.
- Always let `report` auto-run the same validation path.
- For a final Web report, perform live verification once with
  `report --live-web --validation-output ...`; do not first run
  `validate --live-web` unless a second fresh network check is intentional.
- Omit unsupported findings from substantive report sections and expose the reason in Gaps.

## Unified Workflow

1. Run `plan`; record kind, mode, and budgets.
2. Split the question into 2–4 subtopics.
3. Collect required artifacts:
   - `web`: `retrieve` → `fetch-content`
   - `codebase`: `search-codebase`; for runtime claims, snapshot the repository, execute one focused host test, snapshot again, and `import-test-receipt`
   - `hybrid`: both paths
4. Author `findings.json` with typed evidence and exact excerpts.
5. Optionally run offline `validate` with every required artifact to catch
   shape/excerpt errors. Offline serialized Web evidence is capped below High.
6. Run `report`; for final Web/Hybrid High eligibility, pass `--live-web`.
   It performs the fresh verification once, writes `--validation-output`,
   derives the executive summary from usable findings, and renders the
   canonical contract.
7. Deliver the report without renaming, splitting, or omitting top-level sections.

Web validation:

```bash
python3 scripts/deep_research.py validate \
  --research-kind web \
  --results /tmp/results.json \
  --content /tmp/content.json \
  --findings /tmp/findings.json \
  --live-web \
  --output /tmp/validation.json
```

Use the command above when validation itself is the final deliverable. When a
report is required, prefer a single `report --live-web` invocation so the same
pages are not fetched twice.

Final Web report:

```bash
python3 scripts/deep_research.py report \
  --question "<question>" \
  --research-kind web \
  --results /tmp/results.json \
  --content /tmp/content.json \
  --findings /tmp/findings.json \
  --session /tmp/research_plan.json \
  --live-web \
  --validation-output /tmp/validation.json \
  --output /tmp/report.md
```

Pure codebase report:

```bash
python3 scripts/deep_research.py report \
  --question "<question>" \
  --research-kind codebase \
  --code-evidence /tmp/code_evidence.json \
  --findings /tmp/findings.json \
  --session /tmp/research_plan.json \
  --validation-output /tmp/validation.json \
  --output /tmp/report.md
```

## Confidence Rule

Use one rule everywhere:

- Allow `High` for a narrow single fact only when the current validator/report
  process freshly fetched the cited page, matched the excerpt, and re-derived
  T1 from the effective final URL.
- Allow `High` for a direct code fact only after the validator rereads and matches pinned Git content.
- Allow `High` for runtime behavior only when every cited code item is pinned to one Git commit/tree and one reviewed host receipt covers the finding, all code IDs, and all tested paths on that same clean snapshot.
- Require two independent verified units, including a primary unit, for all other `High` findings.
- Downgrade to `Medium` when some verified support exists but the High rule is unmet.
- Use `Low` only for deliberately tentative claims that still have verified support.
- Mark unusable and omit when no evidence validates.

The CLI records requested and effective confidence plus downgrade reasons.
Unpinned working-tree evidence may remain useful at Medium or Low when its
current file content validates, but it is never represented as belonging to
HEAD.

## Honest Degradation

| Level | Executable Condition | Action |
|---|---|---|
| **Full** | Required artifacts exist; every included finding meets requested confidence; no extraction failure | Deliver all nine sections |
| **Partial** | Usable findings remain, but a finding is downgraded, extraction partially fails, or the budget ends with non-critical gaps | Deliver all nine sections and name gaps |
| **Blocked** | A required artifact is missing, no finding has usable evidence, or budget exhaustion prevents the core chain | Stop claiming conclusions; emit or report only the blocked state and next evidence needed |

Bundled content artifacts propagate budget exhaustion automatically. Pass `--budget-exhausted` to `validate` or `report` when an external or manually assembled artifact reached its ceiling.

## Canonical Output Contract

Every Quick, Standard, and Deep report must use these exact 9 sections and top-level headings in this order:

1. `Research Question`
2. `Method`
3. `Executive Summary`
4. `Key Findings`
5. `Detailed Analysis`
6. `Consensus vs Debate`
7. `Source Quality Notes`
8. `Sources`
9. `Gaps & Limitations`

Quick mode may keep Detailed Analysis and Consensus vs Debate concise; it must not omit them. Load `references/output-contract-template.md` before authoring findings or delivering a report.

## Source Quality

Treat automated classification as conservative preclassification:

- Do not classify arbitrary `docs.*` hosts as official.
- Classify `.edu` as institutional, not automatically official product documentation.
- Emit T1–T5, classification basis, date or `unknown`, sponsorship, and methodology for each web source.
- Ignore caller-provided authority labels during validation. Re-derive
  tier/type from the normalized URL and, for live evidence, the effective final
  URL. The current executable automatic T1 rule is intentionally fail-closed
  to recognized government namespaces.
- Surface unknown sponsorship/methodology rather than guessing.

Use the default tiers in `references/hallucination-and-verification.md`.

## Safety Rules

1. Never fabricate evidence or execution state.
2. Require typed support for every substantive claim.
3. Ensure contradictory evidence is surfaced under Consensus vs Debate.
4. Do not convert repository artifacts into fake web citations.
5. Stop or degrade when required evidence is missing.
6. Route every bundled Web request through the public-network-only transport;
   never add a raw `urlopen` bypass.
7. Never let serialized Web metadata or content assert that live verification
   occurred.

## Anti-Examples — DO NOT Do These

1. **Synthesize from snippets** — extract the page and cite an exact supporting excerpt.
2. **Attach a URL without support text** — a URL proves location, not claim support.
3. **Call one generic source "official" because its host starts with docs** — record the classification basis.
4. **Call every High finding a two-domain claim** — apply the narrow T1 single-fact exception.
5. **Call every one-source claim High** — the exception requires T1 primary content and a narrow fact.
6. **Force repository facts into fake web citations** — cite code, commit, and test evidence IDs.
7. **Treat exit code 0 or partial receipt coverage as semantic proof** — require a focused selector and one receipt covering the finding plus the complete same-snapshot code set.
8. **Generate a report without content for web research** — the parser must stop.
9. **Split Consensus and Debate into top-level headings** — keep both under section 6.
10. **Exceed a mode budget** — stop, mark budget exhaustion, and degrade honestly.
11. **Trust caller-authored T1 or `live_verified` fields** — re-fetch in the
    validator and re-derive authority from the effective final URL.
12. **Fetch `file:`, FTP, localhost, private, link-local, or metadata targets**
    — reject before reserving budget or opening a connection, including after redirects.

```
BAD: Finding (High): X is faster. citations=["https://example.com"]
GOOD: Finding (Medium): X was faster in this benchmark, with method limits. evidence=[{"kind":"web","url":"...","excerpt":"..."}]
```

## Load References Selectively

For every report:
→ Load `references/output-contract-template.md` for the one nine-section structure, findings schema, and evidence examples.

For quantitative, high-stakes, disputed, sponsored, or model-generated claims:
→ Load `references/hallucination-and-verification.md` for verification, confidence, T1–T5, sponsorship, methodology, and degradation rules.

For debugging, APIs, code search, comparisons, benchmarks, standards, or security:
→ Load `references/research-patterns.md` for topic-specific query and evidence patterns.

For any runtime-behavior finding backed by a test:
→ Load `references/test-receipt-schema.md`; execute through the host once, then import and statically validate the receipt.

## Subcommands Reference

| Subcommand | Purpose | Key Flags |
|---|---|---|
| `plan` | Classify kind/mode and initialize a session ledger | `--request`, `--mode`, `--research-kind`, `--output` |
| `reserve-budget` | Reserve ledger usage before external host search/fetch | `--session`, `--budget`, `--count`, `--output` |
| `retrieve` | Search DDG Lite under cumulative budget | `--query`, `--session`, `--limit-per-query`, `--output` |
| `fetch-content` | Safely extract public HTTP(S) content under cumulative budget | `--results` or `--url`, `--session`, `--limit`, `--output` |
| `search-codebase` | Produce per-file pinned or unpinned repository evidence | `--pattern`, `--root`, `--glob`, `--output` |
| `snapshot-codebase` | Read repository root, HEAD, tree, and dirty state without executing tests | `--root`, `--output` |
| `import-test-receipt` | Statically verify and append one host-created receipt | `--receipt`, `--code-evidence`, `--output` |
| `validate` | Re-read typed evidence and optionally live-verify cited Web pages | `--research-kind`, `--results`, `--content`, `--code-evidence`, `--findings`, `--live-web`, `--timeout`, `--output` |
| `report` | Auto-validate, optionally live-verify Web evidence, enforce source ceiling, and render nine sections | `--question`, `--research-kind`, `--session`, evidence flags, `--live-web`, `--timeout`, `--validation-output`, `--output` |

## Search and Extraction Fallbacks

If DDG Lite fails, use an available search tool with the same query plan and preserve its result metadata. If static extraction fails, use an available browser-capable fetcher, then save equivalent content records. Imported records remain untrusted serialized evidence and cannot produce Web High; the bundled validator must still perform its own safe live capture. Report the actual method used; do not rank tools or claim one is universally best.

## Bundled Assets

- `scripts/deep_research.py`: compatibility CLI plus shared Web validation/report engine
- `scripts/deep_research_lib/planning.py`: multilingual classification and mode budgets
- `scripts/deep_research_lib/session.py`: cross-process locked, cumulative session-budget ledger
- `scripts/deep_research_lib/repository.py`: Git provenance, read-only snapshot metadata, and static host-receipt verification
- `scripts/deep_research_lib/reporting.py`: cited-source selection and ceiling enforcement
- `scripts/deep_research_lib/web.py`: public-network-only HTTP(S), DNS/IP pinning, TLS hostname verification, and redirect revalidation
- `scripts/tests/test_evidence_integrity.py`: evidence-chain and negative behavioral tests
- `scripts/tests/test_repository_integrity.py`: dirty-tree, forged Git, receipt binding, and command-proxy negative tests
- `scripts/tests/test_session_budget.py`: cumulative/multiprocess budget and report-source ceiling tests
- `scripts/tests/test_golden_scenarios.py`: fixture request → executable decision tests
- `scripts/tests/test_subcommand_smoke.py`: offline CLI end-to-end tests
- `scripts/tests/test_web_security.py`: local-scheme, private-address, mixed-DNS, redirect, and DNS-pinning negative tests
- `references/output-contract-template.md`: canonical schema and report template
- `references/hallucination-and-verification.md`: verification/confidence/source-quality protocol
- `references/web-evidence-and-egress.md`: Web provenance state machine and safe-egress contract
- `references/research-patterns.md`: programmer-focused research patterns
- `references/test-receipt-schema.md`: host receipt schema, snapshot binding, and relevance rules

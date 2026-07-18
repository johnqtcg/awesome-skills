# Hallucination Awareness and Verification Protocol

## Contents

1. Hallucination types
2. Cross-validation protocol
3. Confidence contract
4. Source Tier Ranking
5. Source-quality assessment
6. Numeric claims
7. Insufficient evidence

## Hallucination Types

| Type | Example failure | Detection |
|---|---|---|
| **Fabricated Citation** | Invented URL, paper, code path, commit, or test | Resolve the typed evidence against collected artifacts |
| **Stale Information** | Old version presented as current | Check date/version in a primary source |
| **Confidence Inflation** | Thin evidence labeled High | Recompute effective confidence |
| **Phantom Feature** | Nonexistent API or configuration | Read primary docs or direct code |
| **Unsupported Paraphrase** | Page exists but does not support the conclusion | Require an exact extracted excerpt |
| **Cherry-Picked Evidence** | Contradictory sources omitted | Search for counterevidence and populate Debate |
| **Conflation** | Product/community edition or versions mixed | Record exact identity and boundary |
| **Execution Invention** | Handwritten `status: passed` or a generic success command treated as behavioral proof | Require a host-attested receipt with target, selector, covered claim/code IDs, snapshot identity, and relevance review |

## Cross-Validation Protocol

For each finding:

1. Identify the claim type before assigning confidence.
2. Resolve every typed evidence reference.
3. For web evidence, require:
   - URL in retrieval results,
   - successful content extraction,
   - exact supporting excerpt present in extracted text,
   - source tier and classification basis.
4. For repository evidence, require:
   - `code`: an in-root path and exact line/excerpt; for pinned evidence,
     prove the commit exists and reread `<commit>:<path>` rather than the
     working tree,
   - `commit`: prove the object exists and compare the declared subject to
     `git show`,
   - `test`: require `host-test-receipt-v2`; verify its commit/tree and tested
     paths, then require one receipt to bind its `covers` and approved
     relevance rationale to the runtime finding and the complete cited-code
     set. The research helper must not execute receipt argv.
5. Check independence only when the confidence rule requires it.
6. Check recency for time-sensitive facts.
7. Search for contradictory evidence when the topic is disputed or consequential.
8. Record requested and effective confidence separately.

## Confidence Contract

Use this contract everywhere:

| Claim type | High requirement |
|---|---|
| Narrow `single_fact` | One verified T1 primary web source |
| Direct `code_fact` | Direct code reread successfully from the declared Git blob |
| `runtime_behavior` | Every cited code item pinned to one commit/tree plus one passed, reviewed host receipt covering the finding, all code IDs, and all tested paths on that clean snapshot |
| Any other claim | At least two independent verified evidence units, including one primary unit |

Then apply:

- If High requirements are unmet but verified evidence exists, downgrade to Medium.
- Preserve Low for deliberately tentative claims with verified support.
- If no evidence validates, mark the finding unusable and omit it.
- Do not use two domains as a universal High rule; the narrow T1 single-fact exception is intentional.
- Do not use one source as a universal High rule; it must be a narrow fact and verified T1 primary content.
- Do not treat `HEAD`, `working-tree`, or another label as a pinned commit; use an abbreviated or full hexadecimal object ID.
- Do not infer that current working-tree bytes belong to HEAD. Modified,
  staged, and untracked paths must be labeled `working-tree-unpinned`.
- Do not trust receipt fields merely because their JSON shape is valid.
- Do not treat exit code 0 alone as evidence that a test covers the claim.
- Do not bind a test run from a dirty or different snapshot to pinned code.
- Do not ignore an unpinned code item because another cited item is pinned.
- Do not combine partial coverage from multiple receipts to manufacture High.

## Verification Priority

| Risk | Information | Preferred evidence |
|---|---|---|
| Critical | API/configuration syntax | Primary documentation plus extracted excerpt |
| Critical | Benchmark/statistic | Original report, disclosed method/environment |
| Critical | Security/compliance | Standard, regulator, official advisory |
| High | Version/license/pricing/quota | Current first-party source with date |
| High | Runtime repository behavior | One same-snapshot pinned code set plus one host receipt with complete semantic coverage and approved relevance |
| Medium | Best practice/architecture | Primary basis plus independent experience |
| Low | Conceptual explanation | Cross-check if contested |

## Source Tier Ranking

Tiers describe evidence weight, not truth. Automated assignments are provisional.

| Tier | Typical source | Required checks |
|---|---|---|
| T1 (Primary authoritative) | Standards text, official primary docs, government data, original peer-reviewed study, direct code/test artifact | Identity, version/date, direct support |
| T2 (Primary-adjacent) | Official release notes/blog, institutional publication, preprint, maintainer talk | Recency, review status, owner |
| T3 (Independent expert/empirical) | Reputable reporting, independent benchmark with method, systematic practitioner study | Method, sponsorship, reproducibility |
| T4 (Community/context) | Issue discussion, Stack Overflow, practitioner blog, forum | Author expertise, corroboration |
| T5 (Discovery/marketing) | Tutorial farm, generic publishing platform, vendor marketing, unsourced roundup | Never use alone for substantive findings |

Conservative preclassification rules:

- Treat `docs.*` as an unverified website unless ownership is established.
- Treat `.edu` as institutional, not automatically official product documentation.
- Treat academic repositories/publishers as T2 until publication/review status is known.
- Treat vendor marketing as T5 even when hosted on a first-party domain.
- Allow a reviewed explicit classification to override the heuristic, and record the basis.

## Source-Quality Assessment

For each source, record:

| Field | Values / guidance |
|---|---|
| `source_tier` | T1–T5 |
| `classification_basis` | explicit rationale or named heuristic |
| `date` | publication/update date or `unknown` |
| `sponsorship` | none, independent, vendor, sponsored, or unknown |
| `methodology` | disclosed summary or unknown |

Assess:

- ownership and editorial control,
- primary vs secondary status,
- sponsorship and conflicts of interest,
- sample, environment, comparison baseline, and reproducibility,
- recency and version scope,
- whether conclusions exceed the method.

Do not infer "independent" from silence. Use `unknown`.

## Numeric Claim Labels

| Evidence | Reporting form |
|---|---|
| Verified primary source and method | Exact value with source and method |
| Multiple compatible sources | Range with sources and boundary explanation |
| One non-primary source | Approximate, single-source, effective confidence at most Medium |
| No verified source | Omit as a finding; record the gap |

Never report a benchmark number without version, workload, environment, and method when those affect interpretation.

## Tool Fallback Principles

Select available tools by the evidence requirement:

- Use a current web search surface for discovery.
- Use direct fetch or a browser-capable extractor for page content.
- Use local execution for code behavior.
- Use authoritative indexes/APIs for papers, standards, or repository metadata.

Do not claim a tool is universally best. Record which tool ran and whether it produced the required artifact.

## Insufficient Evidence Protocol

1. Stop stretching titles, snippets, or weak sources.
2. Record the missing artifact or failed verification.
3. Downgrade supported findings or omit unsupported ones.
4. Set `Partial` if usable findings remain.
5. Set `Blocked` if required artifacts are absent or no finding remains usable.
6. Recommend the next evidence or query, not a branded tool ranking.

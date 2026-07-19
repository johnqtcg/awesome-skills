# Deep Research Output Contract

Use this exact nine-section structure for Quick, Standard, and Deep reports. Quick may be concise; it may not omit or rename a section.

## Input Contract

### Web finding

```json
{
  "title": "Narrow factual claim",
  "claim_type": "single_fact",
  "confidence": "high",
  "analysis": "The supported conclusion.",
  "evidence": [
    {
      "kind": "web",
      "url": "https://primary.example/spec",
      "excerpt": "Exact text present in content.json"
    }
  ]
}
```

The URL must exist in retrieval results. Extraction must have succeeded. The
normalized excerpt must occur in extracted content. A serialized
`content.json` record is an untrusted authoring artifact: loading it clears
`live_verified`, regardless of caller fields. It may support Medium after
excerpt matching, but Web High requires a fresh `validate/report --live-web`
capture in the current process.

### Repository finding

```json
{
  "id": "finding-runtime-1",
  "title": "Observed runtime behavior",
  "claim_type": "runtime_behavior",
  "confidence": "high",
  "analysis": "The behavior supported by code and execution.",
  "evidence": [
    {"kind": "code", "id": "code-1"},
    {"kind": "test", "id": "test-1"}
  ]
}
```

Repository evidence records use these required fields:

| Kind | Required fields |
|---|---|
| `code` | `id`, `kind`, repo-relative `path`, positive `line`, exact `excerpt`, `commit`, `snapshot`; a hexadecimal commit is pinned only after the validator reads and matches that Git blob |
| `commit` | `id`, `kind`, existing `commit`, exact `subject`; the validator resolves both from Git |
| `test` | Versioned host receipt: `id`, `kind`, `origin`, `argv`, framework/target/selectors, `tested_paths`, `covers`, commit/tree/dirty identity, result metadata and hashes, and relevance review |

The repository artifact also carries its absolute `root`. The validator
rejects paths outside that root. `working-tree-unpinned` records are checked
against current filesystem content and may support a downgraded observation,
but never High confidence or a claim about HEAD.

### Findings document

```json
{
  "findings": [],
  "analysis_sections": [
    {
      "title": "Subtopic",
      "content": "Detailed analysis.",
      "evidence": []
    }
  ],
  "consensus": [
    {
      "statement": "Supported area of agreement.",
      "evidence": []
    }
  ],
  "debate": [
    {
      "statement": "Supported disagreement or boundary.",
      "evidence": []
    }
  ],
  "gaps": []
}
```

Do not use legacy `citations` arrays as verified evidence. They do not contain proof that content was read or that the page supports the claim.

## 1) Research Question

- Normalized question:
- Research kind: `web | codebase | hybrid`
- Depth mode: `quick | standard | deep`
- Evidence chain requirements:

## 2) Method

- Execution mode:
- Degradation level: `Full | Partial | Blocked`
- Retrieval plan / subtopics:
- Dedup strategy:
- Retrieved sources:
- Content items processed:
- Successfully extracted:
- Repository evidence units:
- Cited evidence units:
- Validation checks performed:
- Live Web captures / validator-derived T1 references:

Use observed counts, never planned counts.

## 3) Executive Summary

Let the report generator derive this section from validated findings. If Blocked, it states what prevented a supported answer. Do not add a free-standing unvalidated summary field.

## 4) Key Findings

- **Finding** (`High | Medium | Low`): supported statement `[source]`
- Include effective confidence, not merely requested confidence.
- Include downgrade reasons when requested and effective confidence differ.
- Omit findings with no verified evidence.

## 5) Detailed Analysis

### Subtopic

Provide analysis supported by typed evidence. Omit unsupported analysis and record the missing evidence in section 9.

## 6) Consensus vs Debate

### Consensus

- State only areas of agreement with evidence.

### Debate / Contradictory Evidence

- Represent each side with evidence.
- Distinguish contradiction from version, population, method, or time-window differences.

Keep both subsections under this single top-level section.

## 7) Source Quality Notes

- Source tier T1–T5 distribution:
- Classification basis, effective final URLs, and live-capture count:
- Caller tier/type labels ignored:
- Potential sponsorship / conflicts of interest:
- Methodology quality and unknowns:
- Single-source findings:
- Unverified findings omitted:
- Evidence chain status: `satisfied | partially satisfied | insufficient`

## 8) Sources

List every referenced evidence artifact in one numbered index.

Web:

```text
[1] Title — URL — source type (T1–T5) — date or unknown;
    preclassification basis; sponsorship; methodology
```

For confidence, use the validator's evidence record rather than the serialized
source row. It records the requested and effective final URL, capture method,
capture time, HTTP status, resolved public IPs, content hashes,
`live_verified`, and the tier/type re-derived from the effective URL.

Repository:

```text
[2] code evidence `code-1` — path:line — excerpt — verified commit or working-tree-unpinned
[3] commit evidence `commit-1` — commit — subject
[4] test evidence `test-1` — framework/selector — attested exit code — commit/tree — covered finding/code IDs — relevance status
```

Repository sources do not need artificial URLs.
Labels such as `HEAD`, `working-tree`, or `working-tree-unpinned` are descriptive but do not count as commit pinning.
Test receipts are host attestations. The helper statically verifies their Git
identity and eligibility but never executes recorded argv. See
`test-receipt-schema.md`.

## 9) Gaps & Limitations

- Missing evidence:
- Extraction or repository-inspection failures:
- Budget exhaustion:
- Confidence downgrades:
- Source-quality unknowns:
- Follow-up evidence or queries:

## Confidence Contract

- `single_fact`: allow High only with one T1 primary Web source freshly
  captured by the current validator/report process. The exact excerpt must
  match that capture, and T1 must be re-derived from its effective final URL.
- `code_fact`: allow High only when direct code is verified from the declared Git blob.
- `runtime_behavior`: allow High only when every cited code item verifies as
  pinned to one commit/tree and one passed, reviewed host receipt covers the
  stable finding plus every code ID, names every tested path, and matches that
  same clean snapshot.
- Other claim types: require at least two independent verified evidence units and at least one primary unit for High.
- Any verified evidence may support Medium when High requirements are unmet.
- No verified evidence means unusable, not Low-but-publishable.

## Quality Gates

- [ ] The report has exactly the nine numbered top-level headings above, in order.
- [ ] `report` ran automatic validation.
- [ ] Every substantive finding and analysis section uses typed verified evidence.
- [ ] Every web excerpt exists in successfully extracted content.
- [ ] Every Web High excerpt exists in a fresh validator-controlled capture;
      serialized `live_verified`, tier, type, domain, and classification fields
      were not trusted.
- [ ] Every bundled Web request used public HTTP(S), validated every DNS answer,
      connected to a validated IP, and revalidated each redirect target.
- [ ] Every repository reference resolves and is independently checked against Git, the bounded working tree, or a statically verified host receipt.
- [ ] One Runtime High receipt covers the stable finding and complete code-ID/path set; every cited code item is pinned to the same clean snapshot.
- [ ] Effective confidence follows the single confidence contract.
- [ ] Consensus and debate remain under one top-level section.
- [ ] Source Quality Notes include T1–T5, basis, sponsorship, and methodology.
- [ ] Method reports actual retrieved/extracted/repository/cited counts.
- [ ] Degradation is `Full`, `Partial`, or `Blocked` according to execution state.
- [ ] The report Sources list contains only evidence referenced by usable findings and does not exceed the mode ceiling.
- [ ] No source, URL, excerpt, commit, code line, or test result is fabricated.

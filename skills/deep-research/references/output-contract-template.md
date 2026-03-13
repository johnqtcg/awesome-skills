# Deep Research Output Contract

Use this exact structure for final delivery. Every section is mandatory for Standard and Deep modes. Quick mode may omit sections 5 and 6.

## 1) Research Question
- Normalized question:
- Scope assumptions:
- Depth mode: `quick | standard | deep`
- Evidence chain requirements (from Gate 3):

## 2) Method
- Execution mode (auto-selected or user-specified):
- Degradation level: `Full | Partial | Blocked`
- Retrieval plan (queries/subtopics):
- Dedup strategy:
- Content extraction count (sources actually read):
- Validation checks performed:

## 3) Executive Summary
- 2–4 sentences answering the question directly.

## 4) Key Findings
- **Finding A** (`High|Medium|Low`): statement with `[citation]`
- **Finding B** (`High|Medium|Low`): statement with `[citation]`

Each finding must:
- Have a confidence level (High/Medium/Low)
- Include at least one real URL citation
- High-confidence findings must cite ≥2 independent domains

## 5) Detailed Analysis
### Subtopic A
- Analysis with citations from extracted content (not snippets).

### Subtopic B
- Analysis with citations from extracted content.

## 6) Consensus vs Debate
- Consensus: areas where sources agree
- Debate / contradictory evidence: areas where sources disagree (with citations for both sides)

## 7) Source Quality Notes
- Source tier distribution (T1/T2/T3/T4/T5):
- Potential bias (vendor marketing, sponsored content):
- Single-source claims (findings backed by only one source):
- Unverified claims (if any):
- Evidence chain status: satisfied | partially satisfied | insufficient

## 8) Sources
- `[1]` Title — URL — Source type (tier) — Date (if known)
- `[2]` Title — URL — Source type (tier) — Date (if known)

## 9) Gaps & Limitations
- Missing evidence:
- Why missing (paywalled, not indexed, language barrier, budget exhausted):
- Degradation notes (if not Full mode):
- Follow-up queries recommended:
- Alternative research tools suggested:

## Quality Gates

Self-check before delivery:
- [ ] Every claim in sections 4/5 has at least one real URL citation
- [ ] High-confidence findings cite ≥2 independent domains
- [ ] Contradictions are explicitly surfaced, not hidden
- [ ] Source content was actually extracted (Gate 7 satisfied)
- [ ] No fabricated URLs, paper titles, or author names
- [ ] Numeric claims include methodology reference
- [ ] Degradation level is stated honestly
- [ ] Evidence chain requirements from Gate 3 are addressed

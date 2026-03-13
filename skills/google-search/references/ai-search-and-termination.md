# AI Search and Termination

Use this reference when deciding whether Google search is still the right tool, or when deciding whether to stop searching.

## When to Recommend AI Search Instead

Google search is not always the best first step. Recommend switching to or supplementing with AI search when:

| Signal | Recommended Tool | Why |
| --- | --- | --- |
| User needs a structured overview of a broad topic | Perplexity Pro Search or ChatGPT | AI can synthesize many sources quickly |
| User needs a multi-dimensional comparison | ChatGPT or Claude | Structured comparison is AI-friendly |
| User needs deep source-backed research with a written report | Deep Research | Autonomous multi-source research is a better fit |
| User has a specific factual question with a definitive answer | Google first, AI second | Google is better for original-source retrieval |
| User needs to find or download a specific file | Google only | AI tools do not reliably find downloadable files |
| User needs content from a walled garden | Platform-specific search | Neither Google nor AI indexes everything |
| User needs to verify an AI-generated claim | Google only | Do not verify AI with AI |

Best practice: use AI search for synthesis, then Google search for verification and gap-filling.

## Search Budget

Do not search indefinitely. Use a bounded query budget:

- Round 1: 3 queries — Primary, Precision, Expansion
- Round 2: 2-3 queries — reformulate based on the first gaps
- Round 3: 1-2 queries — last-resort language, platform, or angle switch

Maximum: 8 queries before stopping. If 8 queries do not produce a satisfactory answer, the problem is usually framing, not insufficient clicking.

## When to Stop and Report

Stop searching and report what you have when:

- A strong primary source directly answers the question
- Two independent sources agree on the key facts
- The budget is exhausted without direct evidence
- The information does not appear to exist publicly

When stopping, state:

- What you found
- What remains uncertain
- What next strategy would likely resolve the gap

## When to Escalate

Recommend escalation beyond Google search when:

- The topic requires synthesizing 10+ sources into a comparison
- The answer is locked behind a paywall or login
- The content lives on a platform Google cannot index well

## Degradation Protocol

When search results are insufficient, degrade gracefully instead of guessing:

### Full Mode
Strong primary source directly answers the question. Provide direct conclusion with full evidence, confidence labels, and reusable queries.

### Partial Mode
Only derivative or stale sources available. Provide:
- Qualified answer with explicit caveats
- What remains uncertain and why
- Specific next search strategy to resolve gaps
- Lower confidence labels

### Blocked Mode
No relevant results after budget exhaustion, or content behind paywall/walled garden. Provide:
- Explicit statement of what was not found
- Which platforms or tools to try next (e.g., "search directly on WeChat for 公众号 articles")
- Whether AI synthesis tools (Perplexity, Deep Research) would be more appropriate
- The queries attempted, so the user can reuse or modify them

**Never fabricate content to fill gaps. Transparency about limitations is more valuable than false completeness.**

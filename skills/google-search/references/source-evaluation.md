# Source Evaluation

Use this reference to decide whether search results are strong enough to support an answer.

## Source Ranking

Default ranking from strongest to weakest:

1. Official website, official account, original publisher, original statement
2. Primary document, primary dataset, filing, standard, paper, release note
3. Reputable institution or media outlet that cites the original source correctly
4. Specialist community content with concrete evidence
5. Aggregator, repost, SEO summary, unsourced commentary

Prefer the highest-ranked source that directly answers the user's question.

## Check Each Source

For every important source, ask:

- Is this original or derivative?
- Is the publication date visible and recent enough?
- Does it answer the exact question or only mention the topic?
- Does it include names, dates, figures, documents, or citations?
- Is it independent from the other sources I plan to use?

Reject or down-rank sources that:

- Hide dates for time-sensitive claims
- Copy language from another source without adding evidence
- Use sensational summaries instead of primary facts
- Conflict with a stronger source and cannot explain why

## Cross-Checking Rules

For key factual claims, seek 2-3 independent sources when feasible.

Examples:

- A company's own announcement plus a reputable media report
- A government notice plus the underlying PDF attachment
- A profile page plus a public publication or institutional record

Do not count multiple reposts of the same underlying statement as independent confirmation.

## Wartime and Active-Conflict Source Tiers

For wartime credibility tiers, exceptions, and the war reporting checklist, see [high-conflict-topics.md](high-conflict-topics.md). That file consolidates all conflict-specific source evaluation in one place.

## Handling Conflicts

When sources disagree, explain the most likely reason:

- Different dates
- Different statistical definitions or scope
- Translation mismatch
- Old page still indexed
- Secondary source misread the original

Resolve conflicts with this precedence:

1. Newer official or primary source
2. Newer primary document or dataset
3. Reputable secondary source that links the original
4. Community interpretation

If the conflict remains unresolved, say so directly.

### Conflict pattern for war casualties and losses

See [high-conflict-topics.md](high-conflict-topics.md#conflict-resolution-for-war-casualties) for the full wartime conflict resolution protocol.

## Facts, Inferences, and Unknowns

Separate these explicitly in the answer:

- Fact: directly supported by the source
- Inference: reasoned from multiple public facts but not stated directly
- Unknown: could not be confirmed from the available sources

Never present an inference as a confirmed fact.

## Numeric Claim Labels

Every key numeric claim in the final answer must include both:

- A confidence label: `High`, `Medium`, or `Low`
- A source-tier label: `Official`, `Primary document/data`, `Reputable third-party`, `OSINT`, `Adversary claim`, or another clearly named tier

Use the source-tier label to show where the number comes from, and the confidence label to show how much trust it deserves after cross-checking.

### Confidence definitions

- `High`: directly supported by an official or primary source, with clear date and scope, and no material conflict
- `Medium`: supported by a decent source or multiple indirect sources, but with some scope, date, or attribution uncertainty
- `Low`: weakly sourced, disputed, heavily attributed, or dependent on unresolved conflicts

Do not present a key number without these labels. If you cannot label it, present it as an attributed claim or omit it.

## Recency Rules

Apply stricter freshness checks when the topic is unstable:

- News and current events
- Product launches and feature availability
- Prices, roles, company leadership, regulations, and schedules
- Fast-moving technical documentation

When the user asks for "latest", "current", or "today", name the exact date used by the strongest sources.

## Sufficient Evidence Threshold

You can usually provide a direct conclusion when:

- The top source is official or primary
- The page directly answers the question
- The date is visible and appropriate
- At least one additional source supports the key point when needed

You should usually return a qualified or uncertain answer when:

- Only derivative summaries are available
- The result depends on missing or stale dates
- The evidence chain cannot be traced back to an original source
- Identity matching depends on speculation
- The claim comes mainly from one side describing the enemy's losses without corroboration
- Wartime totals mix admitted losses, humanitarian counts, and adversary claims into one number

## Three-Tier Quality Scorecard

### Critical (must pass — skip means answer is unreliable)

- [ ] At least one source is official or primary
- [ ] Key numeric claims carry confidence + source-tier labels
- [ ] Publication date verified for time-sensitive topics
- [ ] Fact vs. inference vs. unknown clearly separated
- [ ] Sources are independent (not reposts of same origin)

### Standard (should pass — skip weakens quality)

- [ ] 2+ independent sources confirm key claims
- [ ] Source conflicts explained, not hidden
- [ ] Reusable queries provided for follow-up
- [ ] Chinese + English paired queries used when topic is mixed
- [ ] Domain constraints (`site:`) used to target authoritative sources

### Hygiene (nice to have — skip is acceptable under budget pressure)

- [ ] Alternative viewpoints acknowledged
- [ ] Next search strategy provided when gaps remain
- [ ] Source credibility explicitly stated (not just implied)
- [ ] Query refinement history documented for complex searches

## Minimum Answer Discipline

Even when evidence is incomplete, still provide:

- The best current conclusion
- What supports it
- What remains uncertain
- The next search query to resolve the gap

# High-Conflict and High-Change Topics

Use stricter discipline for topics where facts move quickly or every side has incentives to frame the numbers. This includes:

- Wars, military operations, insurgencies, and cross-border strikes
- Elections, coups, leadership crises, and major political unrest
- Natural disasters, industrial accidents, and public-health emergencies
- Stock price moves, funding events, bankruptcy risk, and guidance changes
- Company leadership changes, product shutdowns, and major regulatory actions

## Scope Lock

For these topics, lock the scope before searching:

1. State the exact cutoff date and time if known
2. Define the geography and the parties included
3. Define what counts for the metric: deaths, injuries, missing, equipment losses, infrastructure losses, or claimed kills
4. Separate official admissions, third-party estimates, and adversary claims
5. Treat every number as time-bound and source-bound

## War Casualty and Battle-Damage Output Structure

For war, casualty, and battle-damage questions, default to this output structure:

1. Scope line: `As of DATE`, theater, parties, and what is being counted
2. Personnel casualties: deaths, injuries, missing, detentions if available
3. Material losses: aircraft, ships, vehicles, launchers, facilities, critical infrastructure if available
4. Claim tiers: own-side official statement, local humanitarian or hospital data, third-party reporting, OSINT, adversary claim
5. Confidence note: which figures are solid, disputed, or unresolved

Do not collapse all wartime numbers into one line. Separate:

- Confirmed own-side losses
- Claimed enemy losses
- Civilian casualty reporting
- Infrastructure damage
- Numbers that cannot be independently verified

If no stable consensus exists, answer with ranges or multiple attributed figures instead of forcing a single number.

## Query Patterns for War Casualties and Losses

Use for active wars, air campaigns, missile exchanges, insurgencies, and other armed conflicts where casualty and damage numbers change quickly and are often disputed.

Build a fixed query bundle that always includes:

1. `as of DATE`
2. `casualties`
3. `losses`
4. `official statement`
5. `site:` constraints for likely primary sources
6. Exclusion terms for repost and low-value domains

### Required query bundle

Start with at least these four query shapes:

- `"<war or operation name>" casualties losses "as of YYYY-MM-DD"`
- `"<country or force name>" casualties losses "as of YYYY-MM-DD" "official statement"`
- `site:official-domain.tld "<country or force name>" casualties losses`
- `"<country A>" "<country B>" casualties losses "as of YYYY-MM-DD" -site:repost-domain.com -site:low-value-domain.com`

### Expansion patterns

Use these when the first pass is weak:

- `("<country A>" OR "<operation name>") casualties "as of YYYY-MM-DD" Reuters`
- `("<country A>" OR "<country B>") losses "official statement" site:mil.tld`
- `site:gov.<tld> "<country or city>" casualties "as of YYYY-MM-DD"`
- `site:redcross.org OR site:who.int OR site:un.org "<country or city>" casualties`
- `site:x.com "<official spokesperson name>" casualties losses`
- `site:telegram.me OR site:t.me "<official channel name>" casualties losses`

### Domain targeting

Prefer source families that fit the claim:

- Own-side military or government domains for admitted losses and official updates
- Local health ministry, hospital network, emergency service, or local government domains for civilian casualty counts
- Reputable wire services for attributed third-party summaries
- OSINT analysts only after primary-source searching has started to converge

### Noise reduction

Use aggressive exclusions for wartime searches when reposts dominate:

- `-site:youtube.com`
- `-site:tiktok.com`
- `-site:pinterest.com`
- `-site:medium.com`
- `-site:quora.com`

Add or remove exclusions based on the theater and language environment.

### Output discipline

The answer should preserve the same structure as the query bundle:

- `As of DATE`
- Personnel casualties
- Material losses
- Official statements used
- Site-constrained follow-up queries
- Excluded noisy domains if they materially changed the result set

## Source Evaluation for Wartime and Active-Conflict Topics

Use extra care when evaluating war, strike, casualty, or battle-damage reporting. Different source types are strong for different claim classes.

### Default wartime credibility order for casualty totals

Use this default order unless a stronger case-specific reason overrides it:

1. Local humanitarian organizations, hospitals, emergency services, and local government casualty offices reporting their own service area
2. Own-side official statements about their own confirmed losses or admitted damage
3. Reputable third-party media or institutions that name their sources and distinguish verified numbers from claims
4. OSINT or open-source analysts aggregating public evidence
5. Adversary statements about enemy casualties or enemy equipment losses

This order is a default, not a law. Note the important exceptions below.

### Important wartime exceptions

- For visually confirmed equipment losses, high-quality OSINT can outrank media summaries and unsupported official claims.
- For strategic totals far from the front, local hospitals and local officials may undercount because they only see a slice of the theater.
- Own-side official statements are usually strongest for confirmed admissions about their own dead, wounded, or lost platforms, but weaker for claims about enemy losses.
- Adversary claims can still be worth citing, but only as attributed claims unless corroborated.

### War reporting checklist

For each wartime source, identify:

- Which side the source is aligned with
- Whether the source is reporting its own losses or the enemy's losses
- Whether the number is a direct observation, an official tally, or an estimate
- Whether the reporting scope is local, national, or theater-wide
- Whether the number is cumulative and tied to an exact date

If any of those are unclear, downgrade confidence.

### Conflict resolution for war casualties

When wartime numbers disagree, test the conflict in this order:

1. Scope mismatch: civilian only, military only, or combined
2. Time mismatch: one report is newer or uses a different cutoff
3. Geography mismatch: one report covers a city, province, or front rather than the whole theater
4. Claim-type mismatch: confirmed admissions versus estimated enemy losses
5. Evidence mismatch: visually confirmed losses versus unattributed assertions

Prefer attributed ranges or side-by-side figures when the conflict cannot be cleanly resolved.

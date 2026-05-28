# Peer Comparison Methodology

Load this when building the peer panel for an archetype not covered in SKILL.md's main checklist, or when peer-set composition is being contested.

---

## Selecting Peers

Three rules govern peer-set construction:

1. **Same archetype** (see `stock-analysis-lead/references/sector-archetypes.md`). Don't compare a SaaS company to a mature staples company.
2. **Similar scale**: peers should fall within 5× revenue (either direction) of the target. Comparing a $5B SaaS to $5T mega-cap distorts every ratio.
3. **Real competitive overlap**: peers should compete in at least one of the target's main markets. "Same SIC code" is not enough.

The 10-K Item 1 "Competition" section names actual rivals. WebSearch confirmation guards against stale lists.

## Cross-Archetype Pitfalls

- Comparing a hyperscaler (FCF margin 30%, capex 25% of revenue) to a pure SaaS (FCF margin 35%, capex 2% of revenue) on EV/FCF will mislead. The pure SaaS will always look "more expensive" per FCF unless you normalize for capex character.
- Comparing a regulated utility (payout 70% of EPS) to an industrial (payout 30% of EPS) on dividend yield favors the utility but does not capture growth differences.
- Comparing a bank (no meaningful FCF) to a SaaS on EV/FCF is invalid — banks should be compared on ROTCE and P/TBV instead.

## Same-Definition Hygiene

For each peer, document:
- Fiscal year-end (some peers have non-calendar fiscals — adjust by quarter)
- GAAP vs IFRS reporting basis (rare for US listings; affects gross margin definition)
- Currency reporting basis (most US-listed report in USD; some EU dual-listings differ)
- Non-GAAP adjustment conventions (SBC treatment varies; specifically note this in the table)

When SBC treatment differs across peers, compute the panel two ways:
- GAAP basis (apples-to-apples)
- Non-GAAP with SBC normalized (subtract SBC × 1.0 from non-GAAP operating income)

## When to Use Quartiles vs Median

If 5-firm panel (target + 4 peers): use rank (1–5).
If you can construct a wider panel (e.g., 10 firms): use quartile (top-quartile, second, third, bottom) — more robust to outliers.

For the 12-item panel, rank is usually sufficient given typical peer-set size of 3–5.

## Handling "Best in Class" Outliers

If the target is best in panel on a single item by > 30%, ask: is this real outperformance or definitional anomaly?
- Real: gross margin 88% vs peer median 65% in pure software = real positive
- Anomaly: revenue growth 60% in one year because of a one-time acquisition lap = not real

Always check the 3-year trend, not just TTM, for items where target is best in panel.

## Worked Example: Hyperscaler Comparison

Target: MSFT
Peers: GOOGL, AMZN, META, ORCL

Cross-archetype caveat: AMZN has retail segment with very different economics. Run the comparison on **consolidated** numbers (because that's what's traded) but flag the AWS-vs-retail mix in the anomalies section.

For a hyperscaler panel, the most informative items are:
- P-01 (revenue growth): 5–15% expected range
- P-03 (operating margin): mid-30s expected for software-rich; mid-20s for retail-rich
- P-04 (FCF margin): tells you who's monetizing AI well vs who's just spending capex
- P-07 (capex intensity): the AI-arms-race indicator — high is normal in 2025–2027 cycle
- P-09 (shareholder return yield): mature capital allocation signal
- P-10 / P-11 (Forward P/E + EV/FCF): rates the market's relative confidence

## Worked Example: SaaS Comparison

Target: VEEV
Peers: NOW, CRM, WDAY, ADBE (Adobe positioned in SaaS for this purpose)

Run General + SaaS-specific:
- General: P-01 through P-12
- SaaS-specific: NRR, GRR, CAC payback (if disclosed), Magic Number (if computable)

Cross-archetype caveat: Adobe is hybrid creative + SaaS; not a perfect comp but close on financials. Document the imperfection.

## Worked Example: Mature Cash Cow Comparison

Target: KO
Peers: PEP, MNST, KDP

Override the General panel's revenue-growth weight — for staples, organic growth of 4% is excellent, not WEAK. Use the **Mature Cash Cow** thresholds from sector-archetypes.md.

## Edge Cases

- **Recently IPO'd targets**: peer comparison is degraded for first 4–6 quarters as the company normalizes. Note this in Execution Status; weight more on archetype norms than peer comparison.
- **Spin-offs**: prefer the most recent post-spin 10-Q over historical 10-K data; the pre-spin financials may include divested operations.
- **Companies in active M&A integration**: layer year (acquired contribution) is non-comparable; use organic-only growth where target/peers disclose.

## Output Disciplines

- Always state the rank, not just "above average".
- Always cite the peer panel — readers must be able to reconstruct.
- Always flag definitional differences (e.g., "MSFT and ORCL include SBC in opex; META excludes some items in non-GAAP segment metrics").

The point of this worker is to provide an independent quantitative comparison; the discipline of doing so transparently is the value-add.
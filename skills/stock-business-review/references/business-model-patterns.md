# Business Model Patterns Reference

Load this when classifying business-model archetype (BUS-05), interpreting revenue-disaggregation footnotes, or when the company is a SaaS / subscription business and you need to recognize the SaaS-specific revenue patterns (which the earnings-quality skill will then quantify).

---

## Five Business-Model Archetypes

Most US-listed companies fit one of these five. Identify the archetype before judging margin levels — a 25% gross margin is excellent for a distributor and terrible for a software company.

### 1. High-margin, low-turnover (software / IP / brand)

- Gross margin > 70%; revenue per employee high
- Recurring or subscription revenue; minimal COGS per incremental unit
- Examples: enterprise SaaS, branded consumer goods at premium tier, asset-light IP licensors
- **Valuation lens**: justifies high P/S and high EV/Revenue; multiples expand on NRR
- **Risk lens**: customer-concentration risk; competitive moat critical

### 2. Low-margin, high-turnover (retail / distribution)

- Gross margin < 25%; inventory turnover high; thin per-unit margin × volume
- Examples: Costco, Walmart, Amazon retail, distributors
- **Valuation lens**: EV/Sales is low; focus on operating margin trend and inventory turn
- **Risk lens**: demand cyclicality, supply chain, pricing discipline

### 3. Capital-intensive (utilities / industrials / telco / infrastructure)

- Heavy capex; long depreciable assets; debt-funded growth
- Steady (often regulated) cash flow
- Examples: utilities, railroads, telecom carriers, pipelines
- **Valuation lens**: P/B and EV/EBITDA dominate; dividend yield matters
- **Risk lens**: leverage, regulatory rate cycles, refinancing risk

### 4. Network / platform (marketplaces / payment networks / social)

- Asset-light; high marginal-economics; network effects compound
- Two-sided or multi-sided dynamics; take-rate is the lever
- Examples: Visa, Mastercard, eBay, Booking, Meta
- **Valuation lens**: P/E sustains very high; TAM expansion narrative is critical
- **Risk lens**: regulatory antitrust; new platform disruption; take-rate compression

### 5. Project-based / cyclical (construction / consulting / biotech)

- Lumpy revenue; backlog matters more than current quarter
- Margin varies wildly across cycle
- Examples: large-cap construction, EPC contractors, oilfield services, biotech pre-approval
- **Valuation lens**: trailing P/E misleading; use backlog × win-rate × historical margin
- **Risk lens**: cycle timing, backlog quality, project-specific binary outcomes

---

## Revenue Disaggregation — What to Look For in the 10-K Note

The "Disaggregation of revenue" note (ASC 606 requirement) decomposes revenue by category. Read it for:

- **Type**: products vs services vs subscriptions vs licensing
- **Geography**: US vs International (and which international regions)
- **Customer type**: enterprise vs SMB vs consumer; government vs commercial
- **Timing**: point-in-time vs over-time recognition
- **Channel**: direct vs partner / reseller

Mismatches between segments here and what the IR deck shows are a signal — companies sometimes report segments differently in investor materials than in filings.

---

## Contra-Revenue / Client Incentives — the Gross-to-Net Bridge (BUS-11)

For network, platform, and marketplace businesses (and many consumer/distribution models), **gross billings are not net revenue**. A large contra-revenue line — variously "client incentives", "rebates", "partner incentives", "customer incentives", "co-brand payments", or "marketing development funds" — is netted against gross revenue before the top line you see. Reading only net revenue misses one of the most important company-specific dynamics, and is the single clearest dividing line between someone who read the income statement summary and someone who read the 10-K.

**Why it matters most for payment networks (the canonical case):** Mastercard and Visa report **net revenue** = gross revenue − client incentives. Incentives are the principal battleground for winning issuer / co-brand / merchant contracts; they routinely run **a third or more of gross revenue** and grow as a contra-line. Net-revenue growth is therefore the *difference* of two large, faster-growing numbers — gross drivers up, incentives up — so a small change in the incentive ratio swings reported growth materially. The same pattern appears in marketplaces (seller rebates), consumer brands (trade spend / slotting), and gross-vs-net travel/ad intermediaries.

**Where to find it:** 10-K revenue-recognition note (ASC 606) and MD&A — search `"client incentives"`, `"rebates"`, `"incentives"`, `"contra-revenue"`, and any "Gross revenue / Rebates and incentives / Net revenue" presentation. The cash-flow and segment notes sometimes disclose the gross figure separately.

**What to compute and report (BUS-11):**
- Incentives as **% of GROSS revenue**, and its **trend** (3+ years). A rising ratio is a margin-of-the-business signal even when net revenue still grows.
- **Incentive growth vs net-revenue growth** — if incentives grow faster than net revenue for multiple years, pricing/competitive pressure is building beneath a healthy-looking top line.
- The **take-rate trap**: confirm whether a quoted "take rate" / yield is computed on **gross** or **net** — they are different denominators, and analysts routinely conflate them.

If the company has no material contra-revenue line (most pure-product or pure-subscription businesses), mark BUS-11 `Suppressed — no material contra-revenue line` and move on. Do not invent one.

---

## SaaS Recognition Patterns

If you see these signals in the 10-K, the business is SaaS / subscription and the earnings-quality worker should run its SaaS sub-checklist (EQ-06 NRR, EQ-07 Magic Number):

- "Subscription revenue" or "recurring revenue" as a top-line line item or note
- Customer-count disclosure with average revenue per customer (ARPU / ARR per customer)
- Disclosures of "remaining performance obligations" (RPO)
- Deferred revenue / contract liabilities materially above one quarter of revenue
- Investor presentations mentioning ARR, NRR, GRR, or net retention

If only "services revenue" appears and there's no recurring component, it is likely a consulting / professional-services business — apply project-based archetype.

---

## Adjusted-Metric Definition Audit

Almost every company reports non-GAAP "Adjusted EBITDA" or "Adjusted EPS". Each company defines it differently. Read the "Reconciliation of GAAP to Non-GAAP" appendix in the latest earnings release with this question in mind: **What are they excluding, and is the exclusion legitimate?**

### Legitimately excluded items

- Truly one-time M&A integration costs
- Impairment charges (genuinely one-time)
- Litigation settlement (if not recurring)
- Discrete tax items

### Items that should NOT be excluded but commonly are

- **Stock-based compensation (SBC)**. SBC is a real cost — it dilutes shareholders and competes with cash compensation. A non-GAAP that excludes SBC is overstated. Flag if SBC > 15% of revenue is excluded.
- **Restructuring charges that recur**. If the company has a "restructuring" line in 3+ of the last 5 years, it's not one-time — it's operating cost.
- **Amortization of acquired intangibles**. Debatable. Some analysts include it (real economic depreciation of acquired assets); others exclude it (no cash impact). Defensible either way but be consistent.

### Red flag — narrative buckets

When the company invents revenue categories that don't map to filings:
- "AI revenue" (Snowflake, NVDA, etc.)
- "Cloud revenue" (when not separately stated in segment note)
- "Strategic accounts" / "Tier-1 customers" (without quantitative definition)

Flag if material % of total and methodology is absent — orchestrator weights this as a credibility check on management narrative.

---

## Information-Tier Practice

When reading any single number in any single source, classify it:

| Tier | Trust | Examples |
|---|---|---|
| Fact (auditable) | Very high | OCF, Capex, Cash, Debt — from cash flow + balance sheet |
| Accrual (judgment-affected) | High | Revenue, Gross Profit, Operating Income — GAAP rules apply but estimates allowed |
| Non-GAAP (company-defined) | Medium | Adjusted EBITDA, Adjusted EPS — company defines; read reconciliation |
| Narrative (management chosen) | Low | "AI revenue", "Strategic ARR", guidance ranges, "Tier-1 customer mentions" — anchor on these only after factual cross-check |

Always cite the tier in the Finding so the orchestrator weights evidence correctly.

---

## Customer Concentration Anatomy

The 10-K Item 1A discloses "significant customer" risk when one customer is > 10% of revenue. Read this aggressively:

- The named customer (sometimes anonymized as "Customer A")
- Revenue concentration over time (3-year disclosure if available)
- Specific risk language ("loss of this customer would materially affect")
- Cross-reference Item 7 MD&A for any color on this customer's purchasing trends

When a 10-K disclosed customer concentration is rising YoY, this is a High-severity Finding even if the named customer is "investment grade" — concentration is the structural risk, not the customer's credit.

---

## Geographic Risk Reading

The "Geographic information" note gives revenue split by country / region. Use it to:

1. Identify FX exposure. International revenue × FX volatility = earnings volatility.
2. Identify political risk. Revenue from China, Russia, or Iran has compliance & sanctions exposure.
3. Identify trapped cash. International cash held in low-tax jurisdictions may be unrepatriable without tax.

Cite the geographic note when flagging FX or political risk in BUS-03.
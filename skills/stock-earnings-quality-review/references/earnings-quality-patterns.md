# Earnings Quality Patterns Reference

Load this when interpreting OCF-vs-NI drift, capex classification, SaaS-specific metrics, or sector-specific margin benchmarks.

---

## OCF / Net Income Drift — The Single Most Useful Number

Healthy: OCF ≈ Net Income, or OCF > Net Income.

A persistent gap where OCF << Net Income is one of the most reliable signs of aggressive accounting:
- Revenue is being recognized before cash collection
- Receivables are growing faster than revenue (channel stuffing)
- Working capital is deteriorating
- Net income is being "made" with accrual adjustments

### Diagnosis path when OCF / NI is low

1. Pull AR growth vs Revenue growth — if AR growth > Revenue growth by > 10pp, this is a Receivables story (EQ-09).
2. Pull Deferred Revenue trend — if shrinking while revenue is "growing", this is recognition-acceleration.
3. Pull Inventory days — if rising, this is channel build-up.
4. Pull Capitalized software / R&D — sometimes a company capitalizes costs that competitors expense, inflating earnings.

A single year of OCF/NI < 0.7 is a yellow flag; 2+ years is a High-severity Finding.

### Reverse case — OCF >> Net Income

Often healthy: depreciation > capex (cash-cow business), or stock-based comp adding back. Worth checking:
- Is OCF >> NI because of unsustainable working-capital releases (one-time AR collection)?
- Is the cash-cow status structural (utility) or end-of-life (declining business pretending to be a cash cow)?

---

## FCF Trajectory Patterns

FCF = OCF − Capex. Four common trajectories:

| Pattern | Signal |
|---|---|
| Positive and growing | Healthy compounder |
| Negative but improving (less negative each year) | Growth-stage; track to FCF positive ETA |
| Negative and stable | Burning cash without progress — concerning |
| Positive but declining | Cash flow declining; investigate why — competition? End of cycle? |

The single most common red flag: FCF negative for 3+ years with no clear path to positive AND continued equity issuance to fund the burn. This is the death-by-dilution profile (the source doc names Ondas as an example).

---

## Capex Character: Maintenance vs Expansion

**Maintenance capex ≈ depreciation expense.** If a company's capex roughly equals D&A, they are spending to maintain the asset base — same capacity, no growth.

**Expansion capex >> depreciation.** The company is building new capacity (data centers, factories, store count). FCF will be depressed during the build phase; trust depends on the ROI of the expansion.

Cases requiring nuance:
- **MSFT 2024**: capex 3× depreciation — expansion (AI data centers). Justify the dollars by the expected revenue stream.
- **Old industrial cyclical with capex < depreciation for 5 years**: declining business undercut investing; future maintenance bills will come due.

Cite in EQ-03 with the multiple (e.g., "Capex / D&A = 2.4× in FY24, driven by data center build per MD&A").

---

## SaaS Sub-Checklist Methodology

For subscription businesses, conventional GAAP metrics under-weight the unit economics. SaaS-native KPIs better reflect company health:

### ARR (Annual Recurring Revenue)

- ARR = MRR × 12 (most accurate when invoicing is monthly)
- Or = sum of annual subscription value of active contracts
- Should grow ≥ revenue growth (lagging indicator otherwise)

### NRR (Net Revenue Retention)

NRR measures cohort behavior of existing customers, including upsell and churn.

- > 130%: Excellent (Snowflake peak: 158%, but has declined since)
- 110–130%: Good (most healthy enterprise SaaS)
- 100–110%: Borderline — limited expansion
- < 100%: Customers are leaving net; high-severity signal

NRR is reported in investor presentations and earnings releases — not always in the 10-K. Cite the source explicitly.

### GRR (Gross Retention Rate)

GRR excludes upsell, measuring pure churn:
- > 95%: Excellent (sticky software)
- 90–95%: Good
- < 90%: Churning meaningfully — investigate why

GRR < 90% with NRR > 120% means heavy upsell to existing customers is masking heavy churn — fragile.

### CAC Payback Period

Months to recover customer acquisition cost from gross profit:
- < 12 months: Excellent
- 12–18 months: Healthy
- 18–24 months: Watch
- > 24 months: Stressed unit economics

### Magic Number

Magic Number = (Quarterly ARR delta × 4) / Previous-quarter S&M spend.

- > 1.5: Excellent — money in goes to money out fast
- 1.0–1.5: Healthy
- 0.75–1.0: Watch — efficiency declining
- < 0.75: Sales spend not productive

---

## Gross Margin Sector Benchmarks

Apply these only after the business worker has classified the archetype:

| Sector | Healthy GM | Notes |
|---|---|---|
| Enterprise SaaS | 70–85% | < 70% usually means heavy services component |
| Consumer Internet (ads) | 75–90% | Lower if commerce-mixed |
| Consumer brand (premium) | 50–70% | Brand strength translates to GM |
| Semiconductor (fabless) | 50–65% | TSMC dependency caveat |
| Semiconductor (IDM) | 40–55% | Higher capex offset |
| Pharma (specialty) | 60–80% | After amortization noise |
| Industrials | 25–40% | Cycles matter |
| Retail (premium) | 35–50% | Costco anomalously low at ~12% — different model |
| Retail (discount / warehouse) | 10–25% | Costco / Walmart territory |
| Distribution | 10–20% | Volume game |
| Utility | 30–55% | Regulated; depends on jurisdiction |

A trend matters more than a level. Margin declining 2pp/yr in a competitive sector is a yellow flag even if level is still good.

---

## Operating Leverage Test

Operating leverage = (% change in operating income) / (% change in revenue).

- Leverage > 1: positive (operating margin expanding with growth)
- Leverage = 1: neutral
- Leverage < 1: negative (margin compressing despite revenue growth)

**Healthy growth phase**: company shows leverage > 1 for several years as fixed costs amortize over growing revenue. Classic example: Meta 2023–2024 — revenue grew, headcount cut, operating income exploded.

**Negative leverage** is a high-severity red flag — usually because of CAC inflation, gross-margin pressure, or "growth investments" with no return.

---

## Three-Cost-Rate Discipline

S&M, R&D, G&A as a % of revenue. Healthy trajectory:

- **S&M**: should decline as a % of revenue over time (operating leverage). Stable or rising at scale = CAC inflation. SaaS at scale should be 25–35% of revenue.
- **R&D**: can be stable. Tech R&D 15–25% is normal. Declining R&D in tech is a warning — long-term competitiveness erodes.
- **G&A**: should decline meaningfully with scale. Bloated G&A (rising as % of revenue past $1B revenue) signals weak governance.

---

## SBC Disguise Patterns

Stock-based compensation is the most-disguised real cost in tech. Patterns to watch:

- **SBC > 20% of revenue**: extreme dilution if not offset by buybacks. Compute SBC / shares × current share price; this is the annual dilution cost.
- **SBC excluded from Adjusted EBITDA** but disclosed in cash flow add-back: company is hoping you'll use the Non-GAAP number.
- **SBC + buybacks combined**: many tech companies issue SBC then buy back stock to "offset" dilution. The net economic cost is the buyback dollars spent. Compute net: buybacks ($) − SBC ($) — if persistently negative, dilution is happening.

Flag EQ-13 if SBC > 15% of revenue AND excluded from Adjusted EBITDA; severity = High if material % of revenue.
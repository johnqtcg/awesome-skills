# Balance Sheet Red Flags Reference

Load this when assessing goodwill concentration, off-balance-sheet items, sector-specific leverage tolerances, or pension liabilities.

---

## Sector-Norm Leverage Table

Net Debt / EBITDA thresholds vary by sector. Apply the relevant column:

| Sector | Conservative | Moderate | High | Red Flag |
|---|---|---|---|---|
| Software / SaaS | < 0× (net cash) | 0–0.5× | 0.5–1.5× | > 1.5× |
| Consumer Internet | 0–0.5× | 0.5–1.5× | 1.5–2.5× | > 2.5× |
| Branded consumer | 0–1× | 1–2× | 2–3× | > 3.5× |
| Semiconductor | 0–1× | 1–2× | 2–3× | > 3× |
| Pharma (large-cap) | 0.5–2× | 2–3× | 3–4× | > 4× |
| Industrial | 1–2× | 2–3× | 3–4× | > 4× |
| Retail | 0.5–1.5× | 1.5–2.5× | 2.5–3.5× | > 3.5× |
| Utility / Pipeline | 3–4× | 4–5× | 5–6× | > 6× (regulated leverage OK) |
| Telecom carrier | 2–3× | 3–4× | 4–5× | > 5× |

Currency leverage tolerance: USD-denominated debt for USD-revenue is straightforward. Cross-currency debt (EUR debt for USD revenue) is unhedged FX risk — flag at any level.

---

## Goodwill Concentration Anatomy

Goodwill arises when a company acquires another business for more than its tangible book value. Persistent high goodwill is a sign of acquisition-driven growth — the company is buying revenue.

### Thresholds

- Goodwill / Total Assets < 10%: Organic growth dominant
- 10–30%: Mix of organic and acquired
- 30–50%: Acquisition-heavy — vulnerable to impairment in recession
- > 50%: Roll-up — almost the entire balance sheet is acquired intangibles

### Impairment History — The Real Test

A single goodwill impairment can be a yellow flag (one bad deal). Multiple impairments = chronic overpayment in M&A.

5-year impairment history (read from "Goodwill" footnote in 10-K):
- 0 impairments: clean
- 1 impairment: yellow — investigate which deal
- 2+ impairments: red — pattern of overpaying

### Historical example

AT&T's Time Warner acquisition resulted in tens of billions in goodwill impairments over the years following the deal. AOL-Time Warner before that. When you see a company with a long history of mega-deals AND a long history of impairments, it's structural — management cannot resist M&A even when they shouldn't.

---

## Off-Balance-Sheet Anatomy (Read the Commitments Footnote)

ASC 842 (effective 2019) brought operating leases onto the balance sheet — so older red-flag patterns of hidden lease obligations are mostly historical. But several still apply:

### Items to look for in "Commitments and Contingencies"

1. **Purchase obligations** — minimum-volume contracts with suppliers. Common in chip / hardware (e.g., TSMC capacity commitments). These are real future cash outflows not on the balance sheet.
2. **Guarantees** — guarantees of subsidiary or joint-venture debt; guarantees of customer financing. Material guarantees can convert to direct liabilities if the underlying party defaults.
3. **Pending litigation** — disclosed when "reasonably possible" but not "probable". Read the dollar exposure language. Class-action securities suits, patent cases, and antitrust cases can be material.
4. **Environmental remediation** — for industrials with brownfield exposure.
5. **Variable interest entities (VIE)** — read carefully if the company has joint ventures. Chinese-listed companies historically used VIEs to operate in restricted sectors; this exposure is material for US-listed Chinese ADRs (but those are out of scope per orchestrator).

### Pension liability

Defined-benefit pension plans (mostly older industrials and unionized companies) carry net underfunded amounts as a long-term liability. Read the pension footnote for:

- Funded status (assets vs projected benefit obligation)
- Underfunded amount as % of market cap
- Discount rate used (lower rates = bigger underfunding)
- Investment-return assumption (7%+ is aggressive; 5% conservative)

Flag if underfunded > 5% of market cap. Defined-contribution plans (401k) carry no such liability — only defined-benefit matters.

---

## Working Capital Stress Signals

Working capital = Current Assets − Current Liabilities. Trends in components:

### DSO trend (Days Sales Outstanding)

DSO = AR / (Annual Revenue / 365)

- Stable DSO is healthy
- Rising DSO over 2+ years = customers paying slower (recession signal, credit-quality deterioration, or salesforce extending payment terms to close deals)
- Rising DSO > 10 days YoY without explanation in MD&A = High severity

### Inventory days trend (non-tech businesses)

Inventory Days = Inventory / (Annual COGS / 365)

- Stable inventory days = healthy
- Rising inventory days = slowing sell-through OR obsolescence risk OR mis-forecasted demand
- For seasonal businesses, compare same-quarter year-over-year (don't compare Q4 to Q1)

### DPO trend (Days Payable Outstanding)

DPO = AP / (Annual COGS / 365)

- Stable DPO is healthy
- Falling DPO = suppliers demanding faster payment (credit concern about you)
- Rising DPO = you're paying suppliers later (could be cash strain or could be optimization)

The composite signal: DSO up + Inventory up + DPO falling = working capital stress. Cash conversion cycle is lengthening; cash is being absorbed.

---

## Cash Runway for Unprofitable Companies

For pre-FCF companies:

Cash Runway (months) = Current Cash / (Annual cash burn / 12)

- > 24 months: comfortable
- 12–24 months: planning needed but OK
- 6–12 months: must raise within 6 months
- < 6 months: equity issuance imminent, likely dilutive
- < 3 months: distressed

When cash runway < 12 months AND share price is depressed, expect heavy dilution. Source doc names Ondas as an example pattern.

---

## Debt Maturity Wall

Read the "Long-term Debt" footnote for the maturity schedule (usually a 5-year table + "thereafter").

Red flags:
- Large balloon payment in the next 24 months ("maturity wall") at a time when company is FCF-negative or rates have risen
- Convertible debt converting at low prices = dilution
- Floating-rate debt at scale during a rising-rate environment

A company with $5B revenue and a $4B 2026 maturity is at refinancing risk if rates have repriced higher since issuance.

---

## Quick Triage Heuristic

When in doubt, score 5 questions:

1. Net cash or net debt?
2. Goodwill / TA < 30%?
3. Current ratio > 1.5?
4. No impairments in last 5 years?
5. No material off-balance-sheet items?

5/5 YES = clean balance sheet, suppress most BS findings, just note positives.
3–4 YES = normal; surface specific issues.
0–2 YES = compromised balance sheet; this dominates the Bear scenario; orchestrator should weight Bear higher.
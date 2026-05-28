# Sector Archetypes & Parameter Sets

Load this during Step 1.5 (after ticker validation) to classify the company into a sector archetype and load the corresponding parameter set for the Good-Company checklist and valuation thresholds.

**Why this exists**: The previous version of this framework had SaaS/hyper-growth thresholds embedded as universal defaults (revenue growth ≥ 15%, NRR > 115%, Net Debt/EBITDA < 2). This systematically under-rated mature cash cows (KO, JNJ, ADP, MO), banks, REITs, utilities, and cyclicals. Item 5 (NRR) had to be marked N/A as a patch — a sign the design was wrong. This file fixes that by making the checklist **sector-aware** at every threshold.

---

## How to Use

After Step 1 ticker validation, the orchestrator must classify the company into exactly one archetype. Apply only the parameter set from the matching archetype to the Good-Company checklist.

If a company spans two archetypes (e.g., a SaaS company with a mature cash-cow segment), use the **archetype that describes the dominant revenue source (>60% of revenue)**. Surface the bifurcation in the synthesis but score on the dominant archetype.

---

## The Seven Archetypes

### 1. High-Growth SaaS / Software

**Identifiers**:
- Subscription revenue > 70% of total
- Gross margin > 65%
- Capex < 5% of revenue
- Revenue growth historically > 15%
- Examples: NOW, VEEV, TEAM, DDOG, ZS, CRWD, SNOW

**Good-Company Thresholds**:
1. Revenue growth ≥ 15% (sustained); WEAK at 10–15%, FAIL <10%
2. Gross margin ≥ 70% and stable/rising; WEAK 60–70%, FAIL <60%
3. Operating leverage positive (OpInc > Rev growth); WEAK = equal; FAIL = negative
4. FCF positive and growing; WEAK negative but improving; FAIL negative and worsening
5. NRR > 115%; WEAK 105–115%; FAIL <105%
6. Market share rising or holding in growth market
7. Net Debt/EBITDA ≤ 1.5× (sector-strict); WEAK 1.5–2.5×; FAIL >2.5×
8. Management quality (founder/long-tenured; PSU+TSR comp; clean guidance)
9. Identifiable moat (any of 7 named types)
10. TAM ≥ $30B AND growing > 8% CAGR

**Valuation Norms**:
- EV/FCF: 20–35× typical; <15× cheap; >40× expensive
- Forward P/E: 25–50× typical; <20× cheap; >55× expensive
- EV/Sales: 6–15× typical

---

### 2. Mature Cash Cow / Consumer Staples

**Identifiers**:
- Revenue growth 2–8% organic
- Operating margin > 20% stable
- Pays meaningful dividend; substantial buybacks
- Mature brand portfolio
- Examples: KO, PEP, PG, JNJ, ADP, CL, KMB, MO, PM

**Good-Company Thresholds** (very different from SaaS):
1. Revenue growth ≥ 4% (organic); WEAK 2–4%; FAIL <2% or declining
2. Gross margin sector-leading + stable; trend-stable is PASS (not rising)
3. Operating leverage neutral acceptable (mature); WEAK if compressing; FAIL if persistent decline
4. **FCF/Revenue ≥ 18% AND FCF growing 4%+** (key differentiator vs SaaS)
5. **Replace NRR with dividend coverage**: dividend / FCF < 60% = PASS
6. Market share stable+ (gains rare; defensible position is enough)
7. Net Debt/EBITDA ≤ 3× (consumer staples can carry more); WEAK 3–4×; FAIL >4.5×
8. Management quality + capital allocation track record
9. Brand moat (always); secondary scale/distribution moat
10. Geographic expansion or category extension as growth lever (TAM 5%+)

**Valuation Norms**:
- EV/FCF: 14–22× typical; <12× cheap; >25× expensive
- Forward P/E: 18–25× typical; <16× cheap; >28× expensive
- Dividend yield 2.5–4% acts as floor

---

### 3. Hyperscaler / Mega-Cap Tech Platform

**Identifiers**:
- Revenue > $100B
- Multiple business segments
- Heavy AI/data center capex
- Examples: MSFT, GOOGL, AMZN, META, AAPL (with caveats)

**Good-Company Thresholds**:
1. Revenue growth ≥ 10% (at this scale); WEAK 5–10%; FAIL <5%
2. Consolidated GM ≥ 50% (depends on mix); FoA-style segment GM > 75% if applicable
3. Operating leverage positive (cycle-aware)
4. FCF positive — **temporary capex-driven compression acceptable if Capex/D&A < 4× and < 3 years**
5. Engagement / monetization growth (DAU, ARPU) replaces NRR — METRIC NAME varies
6. Market share stable+; share gains are bonus
7. Net Debt/EBITDA ≤ 1× (these companies should be near-zero net debt at scale)
8. Founder-influenced governance (high alignment but watch for dual-class abuse)
9. Multi-moat (typically network + scale + data + brand stacked)
10. TAM very large + AI optionality

**Valuation Norms**:
- EV/FCF: 18–28× typical; market-cap weighted
- Forward P/E: 20–32× typical
- Use SOTP for multi-segment cases (separate values for AWS vs retail, etc.)

---

### 4. Capital-Intensive Industrial / Infrastructure / Utility

**Identifiers**:
- Capex consistently > 15% of revenue
- D&A > 10% of revenue
- Regulated or quasi-regulated cash flows
- Long-lived assets
- Examples: NEE, DUK, SO, KMI, ENB, T, VZ, UPS, UNP, CAT

**Good-Company Thresholds**:
1. Revenue growth ≥ 3% (mature) or ≥ 8% (growth utility/infra); WEAK below
2. Gross margin sector-norm + stable
3. Operating leverage stable (cyclicals: cycle-adjusted)
4. **FCF after maintenance capex** positive (distinguish maintenance vs expansion); WEAK if maint capex > 80% of OCF
5. Replace NRR with **regulated rate-base growth** (utilities) or **contracted backlog growth** (industrials)
6. Market share stable+
7. **Net Debt/EBITDA ≤ 4–5× for regulated utilities** (very different from SaaS); 2–3× for industrials; FAIL >6×
8. Management: rate-case wins + capex discipline + regulatory navigation
9. Regulatory moat (utilities) or scale-cost moat (industrials)
10. Long-term TAM growth + electrification/energy-transition tailwinds (utilities)

**Valuation Norms**:
- EV/EBITDA: 9–14× (utilities), 8–12× (industrials)
- Forward P/E: 16–22× (utilities), 14–20× (industrials)
- Dividend yield 3–5%
- For utilities: P/Book vs allowed-ROE matters more than P/E

---

### 5. Cyclical (Materials, Auto, Semiconductors, Travel)

**Identifiers**:
- Revenue swings ±20–40% across cycle
- Capex tied to cycle stage
- Examples: FCX, X, TSLA, F, GM, Memory semis (MU), oil majors, airlines

**Good-Company Thresholds** (cycle-adjusted):
1. **Mid-cycle revenue growth ≥ 5–8%** (avg over 5 years); WEAK if declining trend
2. **Mid-cycle operating margin ≥ sector benchmark**; trough not catastrophic
3. Operating leverage POSITIVE at peak, MANAGEABLE at trough (not catastrophic)
4. **FCF positive across the cycle** (sum over 5 years); failing means commodity exposure too high
5. Inventory turns + DSO (replace NRR for cyclicals)
6. Market share rising = real positive (cycles rotate winners)
7. Net Debt/EBITDA AT PEAK ≤ 1×; AT TROUGH ≤ 4× — must survive trough
8. Capital allocation: counter-cyclical buybacks (buy low, sell high — rare skill)
9. Cost-position moat (low-cost producer in cyclicals = real moat)
10. End-market durability + cycle-stage awareness

**Valuation Norms**:
- **Trailing P/E is treacherous** — use cycle-normalized EPS
- EV/EBITDA mid-cycle: 6–10×
- P/Book: useful floor for asset-heavy cyclicals
- **Buy near trough, sell near peak** — multiple compresses at trough but earnings power expands

---

### 6. Bank / Insurance / Asset Manager (Financials)

**Identifiers**:
- Net Interest Income or Net Premiums core
- ROE and ROTCE are primary metrics
- Heavily regulated capital requirements
- Examples: JPM, BAC, WFC, MS, GS, BLK, BRK.B, ICE, CME

**Good-Company Thresholds**:
1. **PPNR growth ≥ 5%** (Pre-Provision Net Revenue); WEAK 2–5%; FAIL <2%
2. **Net Interest Margin** stable + (banks); **combined ratio < 95%** (P&C insurance)
3. Operating leverage = efficiency ratio improvement (< 60% banks)
4. **Return on Tangible Common Equity (ROTCE) > 12%** (replaces FCF); WEAK 8–12%; FAIL <8%
5. **Loan loss reserves coverage** (banks): allowance/NPL > 1.5× (replaces NRR)
6. Market share / deposit franchise growth
7. **CET1 ratio > regulatory minimum + 200bps cushion**; otherwise FAIL
8. Management: credit discipline through cycle (no '08-style blowups)
9. Brand/distribution moat (deposit franchise is the moat for banks)
10. Demographic + economic exposure to growth markets

**Valuation Norms**:
- **P/Tangible Book Value (P/TBV)** is primary; > 1.5× = good franchise; < 1× = distressed
- Forward P/E: 9–14× banks; 10–16× insurers; 18–28× asset managers
- **NOT EV/FCF** — financials don't have meaningful FCF in conventional sense

---

### 7. REIT (Real Estate Investment Trust)

**Identifiers**:
- Pass-through tax structure
- Dividend payout ratio > 90% of taxable income required by IRS
- FFO/AFFO replaces earnings
- Examples: AMT, PLD, EQIX, SPG, O, WELL, PSA

**Good-Company Thresholds**:
1. **FFO/share growth ≥ 4%** (replaces revenue growth); WEAK 2–4%; FAIL <2%
2. Same-store NOI growth ≥ inflation
3. Operating leverage = G&A as % of revenue declining
4. **AFFO covers dividend** (payout ratio < 90% of AFFO); WEAK 90–95%; FAIL >95%
5. **Occupancy rate > sector benchmark** (replaces NRR)
6. Property-type market position
7. **Net Debt/EBITDA ≤ 6× for REITs** (much higher than SaaS); WEAK 6–7×; FAIL >7×
8. Management: AFFO-per-share growth via accretive acquisitions + dispositions
9. Asset-quality moat (irreplaceable locations) or specialty moat (data centers, towers)
10. Long-term tailwinds (e-commerce → industrial; aging → senior housing; AI → data centers)

**Valuation Norms**:
- **P/FFO and P/AFFO** are primary; 18–25× for high-quality REITs
- Dividend yield: 3–5% high-quality; 5–8% mid-tier; > 8% distressed
- **NAV (Net Asset Value)** comparison — discount to NAV = buy signal at quality REITs
- Cap rate analysis vs comparables

---

## Multi-Segment Companies

If a company has > 30% of revenue from a second archetype, run a **secondary archetype score** on that segment and weight accordingly in the verdict. Examples:
- **AMZN**: Hyperscaler (AWS) + Retail (low-margin cyclical-ish)
- **GOOGL**: Hyperscaler (cloud) + Mature ads
- **DIS**: Mature media + Cyclical theme parks
- **BRK.B**: Insurance + Conglomerate of operating businesses

For these, surface the breakdown explicitly. Do NOT score on a single archetype.

---

## Use in the Good-Company Checklist

When applying `references/good-company-checklist.md`:

1. First, classify into archetype (this file).
2. Then load the matching threshold set.
3. Score each item using the **archetype-specific thresholds**, NOT the SaaS defaults.
4. Document the archetype choice in the Execution Status section of the orchestrator output.

**Example output excerpt**:
```
Archetype: Mature Cash Cow (Consumer Staples)
Item 1 (Revenue growth): KO FY25 +4.2% organic vs threshold ≥4% → PASS
Item 4 (FCF/Revenue): 24% with growth +5% vs threshold ≥18% / growing 4%+ → PASS
Item 5 (Dividend coverage): payout/FCF 55% vs threshold <60% → PASS (NRR replaced for archetype)
```

---

## Use in Valuation

In `references/valuation-methods.md` and `references/scenario-framework.md`:

- Multiples comparisons (P/E, EV/FCF, EV/EBITDA) must use the **archetype-specific valuation norms** from this file, NOT generic SaaS norms.
- Terminal multiples in Bull/Base/Bear scenarios should anchor on the **archetype norm** (e.g., 14× EV/FCF for utility, not 25× SaaS norm).
- Reverse-DCF discount rates can be adjusted per archetype (utilities: 7–8% WACC; banks: 9–11% cost of equity; SaaS: 9–10% WACC).

---

## Self-Audit

When the analysis is complete, ask: "If a peer in the same archetype was scoring much higher than the target on most items, why? If the target is scoring much higher than peers, what's the catch?"

If you cannot answer either question, you have not done archetype-aware analysis — you have done absolute scoring, which is the SaaS-default failure mode this file exists to fix.
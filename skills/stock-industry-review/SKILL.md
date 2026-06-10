---
name: stock-industry-review
description: Review a US-listed company's industry position and competitive moat for an equity-research workup. Covers Porter Five Forces scan, market-share trend (absolute and relative to industry growth), TAM size and trajectory, unit economics where disclosed (LTV/CAC, unit gross margin), moat classification (network / brand / scale-cost / switching-cost / patent / regulatory / proprietary-data), substitute threats, new-entrant threats, pricing-power evidence, supplier/channel concentration risk, and regulatory exposure. Trigger when analyzing competitive position at L6 of the seven-layer X-ray framework. Dispatched by stock-analysis-lead; at Lite depth runs in Lite-Industry mode (moat type + share trend only, no full Porter scan).
allowed-tools: Read, Grep, Glob, WebSearch, WebFetch, Bash
---

# Stock Industry Review

## Purpose

Read 10-K "Competition" sections, MD&A market commentary, and external industry-size data with the eye of a strategy analyst. The financial statements tell you what the company *did*; this skill tells you what the industry will *let it keep doing*. Surface moat type and durability, market-share trajectory relative to industry, pricing power evidence, and structural threats. Output Findings that the orchestrator uses to model Bull/Base/Bear scenarios — moat strength caps the multiple expansion, and competitive pressure determines margin sustainability.

## When To Use

- Orchestrator dispatches industry review (always-on at all depths; Lite runs the lighter moat-type + share-trend pass only — no full Porter scan).
- User asks "what's the moat", "is <ticker> losing share", "who are the competitors", "what's the TAM".

## When NOT To Use

- Business model classification → `stock-business-review`
- Margin trends → `stock-earnings-quality-review`
- Management quality → `stock-management-review`

## Mandatory Gates

### 1) Execution Integrity Gate
Read 10-K Item 1 "Competition" section AND at least one external source (analyst report, industry association, or comparable peer's 10-K) for triangulation. The company's own description of competition is self-serving.

### 2) Quantification Gate
"Strong competitive position" is not a Finding. Quantify: market share %, share trend, TAM $, growth rate. If you cannot quantify, suppress.

### 3) Moat-Type Gate
Generic "competitive advantages" is not a moat. Classify into one of seven types: network effects, brand, scale-cost advantage, switching cost, patent/IP, regulatory, proprietary data. If you cannot fit it into a named type, flag "no identifiable moat".

### 4) Cyclicality Gate
Pricing-power evidence in a bull market is not pricing power. Look for margin stability across a downturn (2020 or 2022 depending on sector).

## Workflow

1. Read 10-K "Competition" subsection + Risk Factors related to competition.
2. Pull at least one peer 10-K for triangulation (peer list from manifest).
3. Estimate market-share trend using revenue YoY vs industry growth (from external source).
4. Classify moat into named type(s); test moat durability.
5. Emit Findings.

## Filing-Pattern-Gated Execution Protocol

### Execution Order

1. Locate the 10-K Competition section, Risk Factors, segment-level revenue, and peer 10-K for context.
2. For each checklist item, locate evidence.
3. **HIT** → quantify + classify.
4. **MISS** → mark NOT FOUND.
5. Report only Findings with named, quantified evidence.
6. Include `Filing pre-scan: X/Y items hit, Z confirmed`.

## Industry Checklist (10 Items)

| ID | Item | Source | Trigger |
|---|---|---|---|
| IND-01 | Porter Five Forces quick scan | 10-K Competition + Risk Factors | Flag if any one force is "high" without compensating moat |
| IND-02 | Market-share trend (relative growth) | Company revenue YoY vs industry growth | Flag if company growth < industry growth (losing share) |
| IND-03 | TAM size + 5-year growth trajectory | Investor presentation / industry research | Flag if TAM growth < 5% (mature market — multiple compression risk) |
| IND-04 | Unit economics (LTV/CAC, unit GM) | Investor presentations + 10-K segment | Flag if LTV/CAC < 3 in subscription business |
| IND-05 | Moat classification (named type) | Multi-source synthesis | Flag "no clear moat" if no named type applies |
| IND-06 | Substitute threat (named adjacent products) | 10-K Risk Factors + external scan | Flag if substitute growing > 20% annually |
| IND-07 | New-entrant threat (capital + regulatory barriers) | 10-K Risk Factors | Flag if barriers low AND TAM attractive |
| IND-08 | Pricing-power evidence (cross-cycle margin stability) | 5-year gross margin through last downturn | Flag if gross margin compressed > 5pp in last downturn |
| IND-09 | Supplier/channel concentration risk | 10-K Risk Factors | Flag if > 30% of supply from single vendor (e.g., TSMC dependency) |
| IND-10 | Regulatory exposure (sector-specific) | 10-K Item 1 "Regulation" + Risk Factors | Flag if pending regulation could compress margin or restrict TAM |

### Severity Rubric

- **High**: Threatens the long-term thesis. E.g., losing share for 3 consecutive years; no identifiable moat in a competitive market; key regulatory action pending.
- **Medium**: Caps Bull-scenario probability. E.g., moat is real but narrow (switching cost ~6 months only); supplier concentration material but second-sourcing in progress.
- **Low**: Context for valuation. E.g., TAM growing 8% (not great, not terrible); regulatory exposure passive.

## Evidence Rules

- Market share must cite a number AND the source (whose definition of the market?).
- Moat classification must name the type explicitly; don't write "they have a strong moat".
- TAM citations must include the source (research firm + year) since TAM estimates vary widely.
- Pricing power must reference a specific downturn period.

## Output Format

### Findings

#### [High|Medium|Low] Short Title

- **ID**: `IND-NN`
- **Citation**: 10-K section + peer or external source
- **Evidence**: quantified data + named moat type
- **Implication**: what this means for the multiple / margin sustainability

### Suppressed Items

### Execution Status

```
Filings reviewed: 10-K (FY2024) Item 1 + Item 1A, peer 10-K (<peer ticker>)
External sources: <industry research firm / analyst report>
Filing pre-scan: 10/10 items hit, 4 confirmed as findings
```

### Summary

One line: `N High / M Medium / K Low — most material: <IND-NN short title>`.

## No-Finding Case

```
No industry-position findings — moat real and named, gaining share, pricing power demonstrated through last cycle.
Notable positives: Network-effect moat; share grew from 24% to 31% in 5 years.
```

## Load References Selectively

- `references/moat-typology.md` — load when classifying moat type or stress-testing moat durability; contains the 7-type taxonomy with named exemplars (Visa network, Costco scale, SAP switching, etc.), and the cyclicality test for pricing power.

## Review Discipline

Industry analysis is where retail investors most often hand-wave ("they have AI, they'll win"). Discipline: name the moat type. Quantify the share trend. Cite the TAM source. If you can't, suppress — orchestrator handles a missing IND finding better than a hand-wavy one.
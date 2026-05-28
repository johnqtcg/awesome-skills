# Moat Typology Reference

Load this when classifying a company's competitive moat, stress-testing moat durability, or applying the pricing-power-through-cycle test.

---

## The Seven Named Moat Types

A moat must be classifiable. "Strong competitive position" is not a moat. Force the classification into one (or, rarely, two) of these named types — and if none fits, flag "no identifiable moat".

### 1. Network Effects

The product becomes more valuable as more people use it. Each new user attracts more users.

- **Two-sided platforms**: marketplaces, payment networks, dating apps
- **Communication networks**: social media, messaging apps
- **Developer ecosystems**: programming languages, app stores

Exemplars: Visa, Mastercard, Meta, LinkedIn, Apple App Store, Microsoft Office (file-format network).

**Durability test**: would a 1% defection from your network damage retention? In strong networks, defection accelerates churn (death spiral). Network moats are durable until a structural shift in user behavior (Friendster → Facebook → ?).

### 2. Brand / Premium Positioning

Customers pay more or buy more frequently because of brand attribution, often with emotional or status component.

- **Luxury**: Hermès, LVMH segments, Ferrari
- **Premium consumer**: Apple (hardware), Nike, Lululemon
- **Trusted institutions**: Coca-Cola, Disney, Costco (membership trust)

Exemplars: Apple, Coca-Cola, Disney, Hermès, Costco.

**Durability test**: gross margin stability across recessions. Brand moats keep pricing intact when commodity competitors collapse margins.

### 3. Scale-Cost Advantage

The business has a unit-cost structure smaller competitors cannot match.

- **Bulk purchasing**: Costco, Walmart, Amazon
- **Distribution scale**: UPS / FedEx, Amazon logistics
- **Manufacturing scale**: TSMC (semiconductor fabs), large-cap auto

Exemplars: Costco, Walmart, Amazon, TSMC, large airlines (hub structure).

**Durability test**: gross margin in absolute terms vs second-largest competitor. Scale advantage is durable when scale matters more than agility (commodities) and erodes when scale matters less than differentiation (luxury, software).

### 4. Switching Cost

Customers face friction (financial, time, retraining, data migration, integration) to switch providers.

- **Enterprise SaaS**: Salesforce, SAP, Oracle, ServiceNow
- **Industrial software**: Autodesk, Bentley Systems
- **Embedded systems**: medical-device incumbents, ERP

Exemplars: SAP, Oracle, ServiceNow, Salesforce, Adobe (Creative Suite for professionals).

**Durability test**: NRR > 110% AND GRR > 90% over multiple years. High net retention with low churn = customers can't or won't leave.

### 5. Patent / Intellectual Property

Legally enforced exclusivity.

- **Pharma**: branded drugs under patent protection
- **Semiconductor IP**: ARM, Qualcomm
- **Biotech**: post-approval blockbusters
- **Trade secrets**: Coca-Cola recipe (informal), proprietary algorithms

Exemplars: Merck (specific drug), Qualcomm (CDMA IP), select biotech.

**Durability test**: patent cliff dates. Pharma moats erode predictably on patent expiry; manage accordingly. Trade-secret moats persist indefinitely if the secret holds.

### 6. Regulatory / License Barriers

Government regulation makes new entry impractical.

- **Utility / pipeline**: regulated franchises
- **Telecom**: spectrum licenses
- **Banking**: regulatory capital requirements at scale
- **Defense / nuclear / pharma manufacturing**: certification + clearance regimes

Exemplars: regulated utilities, large defense primes (LMT, NOC, RTX), large pharma manufacturers, banks at scale.

**Durability test**: regulatory regime stability. Regulatory moats are very durable in stable regimes and collapse if deregulation occurs.

### 7. Proprietary Data

Accumulated data that creates analytical or operational advantage that competitors cannot replicate.

- **Risk pricing**: insurance (loss data), credit scoring (FICO)
- **Search / ad targeting**: Google search corpus
- **Operations data**: Palantir customer-deployed data, ServiceNow workflow data
- **Genomic / clinical data**: Tempus, healthcare leaders

Exemplars: Google search, Palantir, FICO, large insurers.

**Durability test**: is the data renewable? Self-renewing data moats (user-generated) are very durable; static data moats erode as competitors gather their own.

---

## How to Use the Classification (IND-05)

When applying IND-05:

1. Name exactly one (or in rare cases two) of the seven types.
2. Cite specific evidence: "Switching cost: NRR 124% over 5 years, GRR 96%, average integration depth $400k per enterprise customer".
3. Stress-test the durability with the type's specific test.

If no type fits the company, write `[High] IND-05 — No identifiable moat`. This is a high-severity finding because the company is competing on execution alone, and execution moats erode quickly under attack.

Note: "best in class management" or "first-mover advantage" are NOT moats — they are competitive advantages without structural defense. Genuine moat-less companies (commodity producers, basic distributors) are not necessarily bad investments, but their multiples should reflect commodity-business economics, not moat-business economics.

---

## Pricing-Power Test (IND-08)

The clearest single test of moat strength: gross margin stability through a meaningful downturn.

### Test setup

1. Identify the last meaningful downturn relevant to the sector:
   - General recession: 2020 (COVID), 2008 (financial crisis)
   - Tech-specific: 2022 (rate-hike + adtech reset)
   - Sector-specific: oil 2014–2016, retail 2017–2019 (Amazon-driven)
2. Pull gross margin for the company across the downturn.
3. Compare to industry composite.

### Patterns

- **Margin held within 1pp during downturn**: real pricing power (strong moat)
- **Margin compressed 1–3pp, recovered within 2 years**: moderate pricing power
- **Margin compressed > 3pp, recovered slowly or not at all**: limited pricing power
- **Margin compressed and stayed compressed**: no pricing power; commodity dynamics

Cite the specific period and margin trajectory in IND-08.

---

## Supplier Concentration (IND-09)

Some moats are partially offset by upstream concentration. Read the 10-K Risk Factors for supplier disclosures:

- **TSMC dependency**: AAPL, AMD, NVDA, AVGO all depend on TSMC for fabrication. Multi-trillion-dollar market caps depend on one Taiwanese company.
- **Cloud provider dependency**: many SaaS depend on AWS or Azure (which are often competitors). Cost of cloud is a structural margin cap.
- **Single-supplier components**: specialty chemicals, rare earths, specialty silicon.
- **Channel concentration**: Costco, Walmart, Amazon as the dominant channel for many consumer brands.

Flag IND-09 when single-supplier exposure exceeds 30% of a critical input. The Bear scenario must price in this concentration risk.

---

## Regulatory Exposure (IND-10)

Different sectors have different regulatory clocks. Read 10-K "Government Regulation" subsection:

- **Fintech**: state-by-state licensing, CFPB; AI fraud detection rules emerging
- **Biotech**: FDA approval timing; reimbursement decisions
- **Defense**: ITAR / EAR export controls; sole-source vs competitive contracts
- **Energy**: state PUC oversight (utilities); EPA emissions (industrials)
- **AI / data**: emerging EU AI Act + state-level US legislation; sectoral risk for surveillance / facial recognition
- **Antitrust**: FTC / DOJ scrutiny for dominant platforms (Big Tech)

Flag IND-10 when:
- A pending regulation could compress margin (e.g., interchange caps for payment networks)
- A pending regulation could restrict the TAM (e.g., AI bans in certain use cases)
- An adverse legal ruling could become precedent (e.g., Section 230 erosion for platforms)

---

## "No Identifiable Moat" Decision Tree

When you're tempted to write "competitive advantages including X, Y, Z" instead of naming a moat type:

1. Is X, Y, Z any of the seven types above? If yes, name it.
2. If "no", is the company's gross margin > 50% AND stable through a cycle? If yes, there's likely an unnamed moat — re-examine.
3. If still "no" — likely no moat. Mark IND-05 as `[High] No identifiable moat`. Orchestrator must price this into the multiple.

A High finding on IND-05 effectively caps the Bull-case multiple — moat-less businesses don't deserve moat-business multiples regardless of recent growth.
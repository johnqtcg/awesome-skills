## 1) Research Question
- Normalized question: What percentage of Fortune 500 companies run Apache Kafka in production as of 2026?
- Research kind: `web`
- Depth mode: `standard`
- Evidence chain requirements: typed evidence; extracted excerpts for web claims; repository evidence IDs for codebase claims

## 2) Method
- Execution mode: `standard`
- Degradation level: `Partial`
- Retrieval plan (queries/subtopics): 5 distinct queries represented
- Dedup strategy: normalized URL canonicalization + first-seen retention
- Retrieved sources: 25
- Content items processed: 10
- Successfully extracted: 8
- Repository evidence units: 0
- Cited evidence units: 3
- Validation checks performed: required-input, extraction-success, exact excerpt, repository reference, claim-support review, confidence, and degradation checks
- Citation integrity (this is what `Degradation` above reports): every cited excerpt was re-read from the artifact it names
- Claim support (a separate verdict, not implied by the one above): disputed — attested 4, qualified 1, unreviewed 0, disputed 1, blocked 0
- Machine checks cannot decide entailment. A polarity and number screen can only remove support; the reviewed stance on each finding is an author attestation.
- Budget consumed: retrieval 5/25, extractions 5/10, live verifications 3/10

## 3) Executive Summary
Partial result: Apache Kafka's official project website states that more than 80% of Fortune 100 companies trust and use Apache Kafka. The page discloses no survey, sample, or date behind the figure. Confluent, the company founded by Kafka's original creators and Kafka's primary commercial vendor, republishes the identical claim: used by over 80% of the Fortune 100. Apache Kafka's own project page carries the same figure. Both pages are the subject project's own site or its principal commercial vendor's promotional page; neither discloses a methodology, sample, or date, and no independent third-party survey was found corroborating the number. A LinkedIn post by a former Kafka/Confluent engineer states: over 70% of Fortune 500 companies have used Apache Kafka. The post cites no survey, dataset, or methodology, is a personal social-media statement rather than a published statistic, and uses the weaker phrase 'have used' rather than 'run in production.'

## 4) Key Findings
- **Apache Kafka's official site claims 80%+ Fortune 100 adoption.** (High confidence): Apache Kafka's official project website states that more than 80% of Fortune 100 companies trust and use Apache Kafka. The page discloses no survey, sample, or date behind the figure. [1]
- **The 80%+ Fortune 100 figure is a vendor and project marketing claim.** (Medium confidence): Confluent, the company founded by Kafka's original creators and Kafka's primary commercial vendor, republishes the identical claim: used by over 80% of the Fortune 100. Apache Kafka's own project page carries the same figure. Both pages are the subject project's own site or its principal commercial vendor's promotional page; neither discloses a methodology, sample, or date, and no independent third-party survey was found corroborating the number. [1] [2] Downgrade: the only primary source is the subject project's own documentation; a comparison or recommendation needs an independent primary unit; High requires one current-process live-verified T1 primary Web source for a narrow single fact, direct code evidence for a code fact, code plus a passing test for runtime behavior, or two independent verified units including a primary source.
- **A single unsourced social-media post separately claims 70%+ of Fortune 500 'have used' Kafka.** (Low confidence): A LinkedIn post by a former Kafka/Confluent engineer states: over 70% of Fortune 500 companies have used Apache Kafka. The post cites no survey, dataset, or methodology, is a personal social-media statement rather than a published statistic, and uses the weaker phrase 'have used' rather than 'run in production.' [3]

## 5) Detailed Analysis
### What number can defensibly go on the slide
No source found discloses a methodology-backed percentage of Fortune 500 companies running Apache Kafka in production as of 2026. The number that is genuinely well-documented and widely repeated is different on three axes from the one requested: it names the Fortune 100 (not 500), it says 'trust and use' (not 'run in production'), and it is undated evergreen marketing copy rather than a dated survey result. That figure -- more than 80% of the Fortune 100 -- is published identically by Apache Kafka's own project site and by Confluent, Kafka's principal commercial vendor, with no disclosed sample or methodology on either page. A second, unrelated figure for the Fortune 500 specifically (over 70%, 'have used') exists only as a single, uncited social-media post with no disclosed data source. Putting either number on a strategy slide as a precise, sourced 2026 production-adoption statistic would overstate what is actually known. [1] [2] [3]

## 6) Consensus vs Debate
### Consensus
- Every source found agrees that Kafka has very broad adoption among the largest global enterprises; none of them disagrees on that general direction. [1] [3]

### Debate / Contradictory Evidence
- Sources disagree on population, wording, and time frame: Apache Kafka and Confluent both scope their published figure to the Fortune 100 with undated marketing language ('trust, and use'), while a single, uncited LinkedIn post separately scopes an unrelated figure to the Fortune 500 with weaker language ('have used'). No source ties any number specifically to calendar-year 2026 or to verified current production status. [1] [2] [3]

## 7) Source Quality Notes
- Source tier distribution: T1: 1, T2: 0, T3: 0, T4: 2, T5: 0
- Classification basis: caller-provided web tier/type labels are ignored; domain heuristics are re-derived from normalized URLs, and only a fresh validator-controlled capture may establish primary-source status.
- Live Web verification: 12/12 verified Web evidence references were freshly captured; validator-derived live T1: 5. Serialized content artifacts are audit inputs, not execution proof.
- Potential bias / sponsorship requiring review: Apache Kafka, Kafka Benefits and Use Cases - Confluent, Over 70% of Fortune 500 companies have used Apache Kafka ... - LinkedIn
- Sources with unknown methodology: 3
- Repository evidence quality: code observations: 0; commit-pinned: 0; tests passed: 0; tests failed/other: 0
- Domain authority: 5/12 cited Web units were classified from the curated authority registry rather than a URL-shape heuristic; 5 are the subject project's own documentation and cannot serve as the independent primary unit for a comparison or recommendation.
- Claim support: disputed (attested 4, qualified 1, unreviewed 0, disputed 1, blocked 0); 1 claim(s) tripped the polarity screen. Excerpt containment is proved mechanically; entailment is an author attestation and is not machine-verified.
- Single-source findings: 2
- Unverified findings omitted from substantive sections: 0
- Evidence chain status: partially satisfied

## 8) Sources
[1] Apache Kafka — https://kafka.apache.org/ — official (preclassified T1) — date: unknown; basis: registry:project-owned:Apache Software Foundation project documentation; sponsorship: unknown; methodology: unknown
[2] Kafka Benefits and Use Cases - Confluent — https://www.confluent.io/learn/apache-kafka-benefits-and-use-cases — website (preclassified T4) — date: unknown; basis: heuristic:unverified-domain; sponsorship: unknown; methodology: unknown
[3] Over 70% of Fortune 500 companies have used Apache Kafka ... - LinkedIn — https://www.linkedin.com/posts/stanislavkozlovski_over-70-of-fortune-500-companies-have-used-activity-7435332071021170688-edGF — website (preclassified T4) — date: unknown; basis: heuristic:unverified-domain; sponsorship: unknown; methodology: unknown

## 9) Gaps & Limitations
- No methodologically disclosed survey or dataset stating a percentage of Fortune 500 companies running Apache Kafka in production as of 2026 was located.
- The only Fortune-500-specific figure found (70%+, 'have used') is a single unsourced social-media post with no disclosed data source; it does not meet the evidence bar for a slide-ready statistic and is reported here only as an example of what circulates online.
- Technographic aggregators (e.g., TheirStack, ZoomInfo) report large absolute counts of companies detected using Kafka but do not publish a Fortune-500-specific percentage, and technographic detection methods (job postings, tech-stack scanners) are not equivalent to verified production deployment.
- ZoomInfo's Kafka customer page and a Verdict.co.uk article on the IBM/Confluent acquisition returned HTTP 403 and could not be extracted within budget; they were not used as evidence.
- finding #2 confidence downgraded from high to medium

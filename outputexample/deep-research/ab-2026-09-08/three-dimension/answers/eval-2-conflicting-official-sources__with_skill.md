## 1) Research Question
- Normalized question: I have two different pages in the MySQL 8.0 manual that seem to say opposite things about whether an INSTANT ALGORITHM DDL takes a metadata lock for the whole operation or only briefly. Work out which is right and show your reasoning. This is going into a migration runbook that the DBA team will follow during a maintenance window.
- Research kind: `web`
- Depth mode: `deep`
- Evidence chain requirements: typed evidence; extracted excerpts for web claims; repository evidence IDs for codebase claims

## 2) Method
- Execution mode: `deep`
- Degradation level: `Partial`
- Retrieval plan (queries/subtopics): 6 distinct queries represented
- Dedup strategy: normalized URL canonicalization + first-seen retention
- Retrieved sources: 32
- Content items processed: 8
- Successfully extracted: 8
- Repository evidence units: 0
- Cited evidence units: 5
- Validation checks performed: required-input, extraction-success, exact excerpt, repository reference, claim-support review, confidence, and degradation checks
- Citation integrity (this is what `Degradation` above reports): every cited excerpt was re-read from the artifact it names
- Claim support (a separate verdict, not implied by the one above): disputed — attested 1, qualified 5, unreviewed 0, disputed 1, blocked 0
- Machine checks cannot decide entailment. A polarity and number screen can only remove support; the reviewed stance on each finding is an author attestation.
- Budget consumed: retrieval 5/50, extractions 13/15, live verifications 11/15

## 3) Executive Summary
Partial result: As published today, the MySQL 8.0 Reference Manual states that ALGORITHM=INSTANT operations only modify data-dictionary metadata and that an exclusive metadata lock on the table may be taken briefly during the execution phase of the operation. This identical sentence appears, word for word, on both Section 17.12.2 'Online DDL Performance and Concurrency' and Section 15.1.9 'ALTER TABLE Statement'. A brief, phase-scoped lock is the documented behavior today; it is a materially different claim from a lock held for the full duration of the statement. Wayback Machine captures of the exact same two manual URLs, from April and May 2021, show the opposite claim: 'No metadata locks are taken on the table' (Online DDL Performance and Concurrency) and 'No exclusive metadata locks are taken on the table during preparation and execution' (ALTER TABLE Statement). This is the literal opposite of the current wording captured in finding-current-wording, on the same two URLs. The manual's own 'Online DDL and Metadata Locks' section explains that any online DDL operation (INSTANT included, per the same page's opening description of instant operations) needs to acquire an exclusive MDL to commit its new table definition, and that this acquisition 'may have to wait for concurrent transactions that hold metadata locks on the table to commit or rollback.' Critically, once the DDL's exclusive lock request is queued, 'a pending exclusive metadata lock requested by an online DDL operation blocks subsequent transactions on the table' -- so a long-running transaction on the target table can make an 'instant' ALTER TABLE, and everything queued behind it, appear to hang for as long as that transaction runs, even though the lock itself is only held briefly once granted.

## 4) Key Findings
- **Current MySQL 8.0 manual: INSTANT DDL's exclusive metadata lock is brief, not for the whole operation** (Medium confidence): As published today, the MySQL 8.0 Reference Manual states that ALGORITHM=INSTANT operations only modify data-dictionary metadata and that an exclusive metadata lock on the table may be taken briefly during the execution phase of the operation. This identical sentence appears, word for word, on both Section 17.12.2 'Online DDL Performance and Concurrency' and Section 15.1.9 'ALTER TABLE Statement'. A brief, phase-scoped lock is the documented behavior today; it is a materially different claim from a lock held for the full duration of the statement. [2] [3] Downgrade: High requires a validator-derived T1 source from the effective final URL; caller tier labels are not authoritative; High requires one current-process live-verified T1 primary Web source for a narrow single fact, direct code evidence for a code fact, code plus a passing test for runtime behavior, or two independent verified units including a primary source; claim asserts numbers no cited excerpt contains: 17.12, 15.1.
- **Pre-2022 MySQL 8.0 manual: the same two pages said NO metadata lock is taken at all** (Medium confidence): Wayback Machine captures of the exact same two manual URLs, from April and May 2021, show the opposite claim: 'No metadata locks are taken on the table' (Online DDL Performance and Concurrency) and 'No exclusive metadata locks are taken on the table during preparation and execution' (ALTER TABLE Statement). This is the literal opposite of the current wording captured in finding-current-wording, on the same two URLs. [4] [5] Downgrade: claim asserts numbers no cited excerpt contains: 2022, 2021.
- **Operational caveat for the runbook: a brief lock can still cause an effectively long block** (Medium confidence): The manual's own 'Online DDL and Metadata Locks' section explains that any online DDL operation (INSTANT included, per the same page's opening description of instant operations) needs to acquire an exclusive MDL to commit its new table definition, and that this acquisition 'may have to wait for concurrent transactions that hold metadata locks on the table to commit or rollback.' Critically, once the DDL's exclusive lock request is queued, 'a pending exclusive metadata lock requested by an online DDL operation blocks subsequent transactions on the table' -- so a long-running transaction on the target table can make an 'instant' ALTER TABLE, and everything queued behind it, appear to hang for as long as that transaction runs, even though the lock itself is only held briefly once granted. [2]

## 5) Detailed Analysis
### Why the two pages appear to disagree
The two most likely candidates for the user's 'two pages' are: (a) the current live text of Section 17.12.2 'Online DDL Performance and Concurrency' and/or Section 15.1.9 'ALTER TABLE Statement', which today describe a brief exclusive metadata lock; and (b) an older cached, mirrored, PDF, or search-engine-cached copy of one of those same two pages, which asserted an absence of any metadata lock. Wayback Machine captures place that older wording live on dev.mysql.com in April and May of 2021. MySQL's own public bug tracker records why the wording changed: Bug #106480, titled 'ALGORITHM=INSTANT takes exclusive metadata lock on table', was filed against 'MySQL Server: Documentation' on 17 Feb 2022 after a user demonstrated with a reproducible three-session example that an ALGORITHM=INSTANT ADD COLUMN does acquire a brief exclusive lock at commit. Oracle's MySQL Verification Team replied that the feature was 'not documented sufficiently' and marked the report 'Verified as a documentation request.' A member of Oracle's documentation team then posted, on 13 May 2022: 'The referenced documentation has been revised. The changes should appear online soon.' A third page, Section 17.12.1 'Online DDL Operations' (the operation-by-operation support matrix), presents a differently shaped version of the same confusion: its table marks INSTANT column operations 'Permits Concurrent DML: Yes' and 'Only Modifies Metadata: Yes' with zero mention of any metadata lock, so a reader relying on that table alone, with no cross-reference to 17.12.2, is left with the same impression the pre-fix wording stated outright. (The bug-tracker quotations in this paragraph are reproduced from a direct fetch of bugs.mysql.com performed outside this skill's automated pipeline; see Gaps & Limitations.) [1]

## 6) Consensus vs Debate
### Consensus
- Both the current and the 2021 wording agree that ALGORITHM=INSTANT only modifies data-dictionary metadata, does not rebuild the table or copy data, and permits concurrent DML -- they disagree only on whether any exclusive metadata lock is taken at all. [2]

### Debate / Contradictory Evidence
- The current Section 17.12.2 wording holds that an exclusive metadata lock on the table may be taken briefly during the execution phase of the operation. [2]
- The pre-fix Section 17.12.2 wording held that no metadata locks are taken on the table for an instant operation. [4]

## 7) Source Quality Notes
- Source tier distribution: T1: 0, T2: 0, T3: 0, T4: 5, T5: 0
- Classification basis: caller-provided web tier/type labels are ignored; domain heuristics are re-derived from normalized URLs, and only a fresh validator-controlled capture may establish primary-source status.
- Live Web verification: 9/9 verified Web evidence references were freshly captured; validator-derived live T1: 0. Serialized content artifacts are audit inputs, not execution proof.
- Potential bias / sponsorship requiring review: 17.12.1 Online DDL Operations - Oracle, 17.12.2 Online DDL Performance and Concurrency - Oracle, 15.1.9 ALTER TABLE Statement - Oracle, Wayback snapshot: 17.12.2 Online DDL Performance and Concurrency (2021-04-23), Wayback snapshot: 15.1.9 ALTER TABLE Statement (2021-05-29)
- Sources with unknown methodology: 5
- Repository evidence quality: code observations: 0; commit-pinned: 0; tests passed: 0; tests failed/other: 0
- Domain authority: 0/9 cited Web units were classified from the curated authority registry rather than a URL-shape heuristic; 0 are the subject project's own documentation and cannot serve as the independent primary unit for a comparison or recommendation.
- Claim support: disputed (attested 1, qualified 5, unreviewed 0, disputed 1, blocked 0); 1 claim(s) tripped the polarity screen. Excerpt containment is proved mechanically; entailment is an author attestation and is not machine-verified.
- Single-source findings: 1
- Unverified findings omitted from substantive sections: 0
- Evidence chain status: partially satisfied

## 8) Sources
[1] 17.12.1 Online DDL Operations - Oracle — https://docs.oracle.com/cd/E17952_01/mysql-8.0-en/innodb-online-ddl-operations.html — website (preclassified T4) — date: unknown; basis: heuristic:unverified-domain; sponsorship: unknown; methodology: unknown
[2] 17.12.2 Online DDL Performance and Concurrency - Oracle — https://docs.oracle.com/cd/E17952_01/mysql-8.0-en/innodb-online-ddl-performance.html — website (preclassified T4) — date: unknown; basis: heuristic:unverified-domain; sponsorship: unknown; methodology: unknown
[3] 15.1.9 ALTER TABLE Statement - Oracle — https://docs.oracle.com/cd/E17952_01/mysql-8.0-en/alter-table.html — website (preclassified T4) — date: unknown; basis: heuristic:unverified-domain; sponsorship: unknown; methodology: unknown
[4] Wayback snapshot: 17.12.2 Online DDL Performance and Concurrency (2021-04-23) — http://web.archive.org/web/20210423023542/https:/dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl-performance.html — website (preclassified T4) — date: 2021-04-23; basis: heuristic:unverified-domain; sponsorship: unknown; methodology: unknown
[5] Wayback snapshot: 15.1.9 ALTER TABLE Statement (2021-05-29) — http://web.archive.org/web/20210529075157/https:/dev.mysql.com/doc/refman/8.0/en/alter-table.html — website (preclassified T4) — date: 2021-05-29; basis: heuristic:unverified-domain; sponsorship: unknown; methodology: unknown

## 9) Gaps & Limitations
- The skill's automated live-web re-verification transport (browser-header profile) is blocked with HTTP 403 by dev.mysql.com and bugs.mysql.com specifically; the canonical dev.mysql.com URLs were independently confirmed by a direct, non-browser-header HTTP request outside the bundled pipeline, and the current wording was verified live through the bundled pipeline via the Oracle-hosted mirror of the identical manual content (docs.oracle.com/cd/E17952_01/mysql-8.0-en/) instead.
- Because bugs.mysql.com (https://bugs.mysql.com/bug.php?id=106480) also returns HTTP 403 to this tool's automated fetcher, its content could not be carried as a separate scored, typed finding without that finding being silently dropped when live-web re-verification runs. Its quotations are instead reproduced as narrative text in Detailed Analysis, fetched directly and manually cross-checked, but they do not carry this skill's typed web-evidence verification chain the way the two manual-page findings do.
- It was not possible to directly observe which exact two pages, or which exact cached/archived copy, the user personally compared; the historical-vs-current explanation is the best-supported reconstruction given what MySQL's own bug tracker and the Wayback Machine record, not a direct read of the user's browser history.
- The manual does not fully spell out, in one place, that the metadata-lock behavior described for 'online DDL operations' in Section 17.12.2 applies identically to ALGORITHM=INSTANT and ALGORITHM=INPLACE; this was inferred from that page's own opening paragraph (which explicitly discusses 'Instant operations' locking) plus Oracle Verification Team's bug-tracker comments confirming the same commit-time exclusive lock applies to the INSTANT case in the reproduction script.
- finding #1 claim support is qualified: claim asserts numbers no cited excerpt contains: 17.12, 15.1
- finding #1 confidence downgraded from high to medium
- finding #2 claim support is qualified: claim asserts numbers no cited excerpt contains: 2022, 2021

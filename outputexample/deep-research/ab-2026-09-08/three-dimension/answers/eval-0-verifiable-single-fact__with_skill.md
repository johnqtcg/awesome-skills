# Does govulncheck output a CVSS score per vulnerability?

**Direct answer: No.** govulncheck does not emit a CVSS score for any vulnerability it reports, in its default text output, its JSON schema, or (per its own documentation) SARIF/VEX output. It identifies vulnerabilities by a Go-assigned `GO-YYYY-NNNNN` ID and expresses risk via a reachability classification (symbol called / package imported / module required) instead of a CVSS number. See Key Findings below for the sourced evidence.

## 1) Research Question
- Normalized question: Does the Go vulnerability scanner govulncheck output a CVSS score for each vulnerability it reports?
- Research kind: `web`
- Depth mode: `quick`
- Evidence chain requirements: typed evidence; extracted excerpts for web claims; repository evidence IDs for codebase claims

## 2) Method
- Execution mode: `quick`
- Degradation level: `Partial`
- Retrieval plan (queries/subtopics): 1 distinct queries represented
- Dedup strategy: normalized URL canonicalization + first-seen retention
- Retrieved sources: 8
- Content items processed: 5
- Successfully extracted: 5
- Repository evidence units: 0
- Cited evidence units: 4
- Validation checks performed: required-input, extraction-success, exact excerpt, repository reference, claim-support review, confidence, and degradation checks
- Citation integrity (this is what `Degradation` above reports): every cited excerpt was re-read from the artifact it names
- Claim support (a separate verdict, not implied by the one above): partially-reviewed — attested 3, qualified 0, unreviewed 2, disputed 0, blocked 0
- Machine checks cannot decide entailment. A polarity and number screen can only remove support; the reviewed stance on each finding is an author attestation.
- Budget consumed: retrieval 2/10, extractions 5/5, live verifications 4/5

## 3) Executive Summary
Partial result: The official godoc for golang.org/x/vuln/internal/govulncheck, which "contains the JSON output structs for govulncheck," defines the per-vulnerability Finding struct with exactly three fields: OSV (the vulnerability ID string), FixedVersion, and Trace (the call-stack frames). There is no CVSS, Severity, or Score field anywhere in this struct or in the rest of the package's documented types (Config, Frame, Message, Module, Position, Progress, SBOM). This is the authoritative, Go-team-maintained schema definition for govulncheck's `-json` output. The official Go tutorial's worked example of real govulncheck output shows the fields actually printed per vulnerability: a govulncheck-assigned ID (GO-2021-0113), a prose description, a "More info" link, Module, Found in, Fixed in, and Call stacks. No CVSS score, CVSS vector, or numeric severity rating appears anywhere in the sample output. An independent third-party tool vendor that ingests govulncheck's JSON output (DefectDojo) states directly that the upstream Go vulnerability database does not publish CVSS scores, and documents that it therefore derives its own severity rating from govulncheck's reachability tier (symbol/package/module) rather than from a CVSS score in the feed. This corroborates, from a consumer's perspective, that no CVSS score is present anywhere in govulncheck's data to begin with -- there is nothing for a downstream parser to read.

## 4) Key Findings
- **govulncheck's JSON output schema has no CVSS or severity field** (High confidence): The official godoc for golang.org/x/vuln/internal/govulncheck, which "contains the JSON output structs for govulncheck," defines the per-vulnerability Finding struct with exactly three fields: OSV (the vulnerability ID string), FixedVersion, and Trace (the call-stack frames). There is no CVSS, Severity, or Score field anywhere in this struct or in the rest of the package's documented types (Config, Frame, Message, Module, Position, Progress, SBOM). This is the authoritative, Go-team-maintained schema definition for govulncheck's `-json` output. [2]
- **govulncheck's default text output likewise has no CVSS field** (High confidence): The official Go tutorial's worked example of real govulncheck output shows the fields actually printed per vulnerability: a govulncheck-assigned ID (GO-2021-0113), a prose description, a "More info" link, Module, Found in, Fixed in, and Call stacks. No CVSS score, CVSS vector, or numeric severity rating appears anywhere in the sample output. [4]
- **The underlying Go vulnerability database does not publish CVSS scores at all** (Medium confidence): An independent third-party tool vendor that ingests govulncheck's JSON output (DefectDojo) states directly that the upstream Go vulnerability database does not publish CVSS scores, and documents that it therefore derives its own severity rating from govulncheck's reachability tier (symbol/package/module) rather than from a CVSS score in the feed. This corroborates, from a consumer's perspective, that no CVSS score is present anywhere in govulncheck's data to begin with -- there is nothing for a downstream parser to read. [3] Downgrade: High requires a validator-derived T1 source from the effective final URL; caller tier labels are not authoritative; High requires one current-process live-verified T1 primary Web source for a narrow single fact, direct code evidence for a code fact, code plus a passing test for runtime behavior, or two independent verified units including a primary source.

## 5) Detailed Analysis
### What govulncheck reports instead of a CVSS score
govulncheck identifies each vulnerability by its own GO-YYYY-NNNNN identifier drawn from the Go vulnerability database (vuln.go.dev), and its risk signal is reachability-based rather than CVSS-based: whether the vulnerable symbol is actually called, whether the vulnerable package is merely imported, or whether the vulnerable module is merely required. Its three documented output formats -- default text, JSON (golang.org/x/vuln/internal/govulncheck), and SARIF/OpenVEX -- all carry the vulnerability ID, affected/fixed module versions, and call-stack/trace information, but none of the documented schema fields is a CVSS score. A downstream advisory triage doc that wants a CVSS number for a govulncheck finding needs to look it up separately, e.g. by resolving the GO-ID or an aliased CVE/GHSA ID against the OSV record or the CVE/NVD databases; govulncheck itself does not supply one. [1]

## 6) Consensus vs Debate
### Consensus
- All three independent sources -- the official JSON schema godoc, the official tutorial's sample text output, and an unrelated downstream tool vendor's parser documentation -- agree that govulncheck output carries no CVSS score, and agree on what it uses instead (reachability tier / GO-ID plus module/version/trace fields). [2] [3]

### Debate / Contradictory Evidence
- Quick mode: no competing sources were retrieved, so agreement and disagreement were not assessed.

## 7) Source Quality Notes
- Source tier distribution: T1: 3, T2: 0, T3: 0, T4: 1, T5: 0
- Classification basis: caller-provided web tier/type labels are ignored; domain heuristics are re-derived from normalized URLs, and only a fresh validator-controlled capture may establish primary-source status.
- Live Web verification: 6/6 verified Web evidence references were freshly captured; validator-derived live T1: 4. Serialized content artifacts are audit inputs, not execution proof.
- Potential bias / sponsorship requiring review: govulncheck command - golang.org/x/vuln/cmd/govulncheck - Go Packages, golang.org/x/vuln/internal/govulncheck - Go Packages, Govulncheck | DefectDojo Documentation, Tutorial: Find and fix vulnerable dependencies with govulncheck - The ...
- Sources with unknown methodology: 4
- Repository evidence quality: code observations: 0; commit-pinned: 0; tests passed: 0; tests failed/other: 0
- Domain authority: 4/6 cited Web units were classified from the curated authority registry rather than a URL-shape heuristic; 4 are the subject project's own documentation and cannot serve as the independent primary unit for a comparison or recommendation.
- Claim support: partially-reviewed (attested 3, qualified 0, unreviewed 2, disputed 0, blocked 0); 0 claim(s) tripped the polarity screen. Excerpt containment is proved mechanically; entailment is an author attestation and is not machine-verified.
- Single-source findings: 3
- Unverified findings omitted from substantive sections: 0
- Evidence chain status: partially satisfied

## 8) Sources
[1] govulncheck command - golang.org/x/vuln/cmd/govulncheck - Go Packages — https://pkg.go.dev/golang.org/x/vuln/cmd/govulncheck — official (preclassified T1) — date: unknown; basis: registry:project-owned:Official domains of the Go project, maintained by the Go team; sponsorship: unknown; methodology: unknown
[2] golang.org/x/vuln/internal/govulncheck - Go Packages — https://pkg.go.dev/golang.org/x/vuln/internal/govulncheck — official (preclassified T1) — date: unknown; basis: registry:project-owned:Official domains of the Go project, maintained by the Go team; sponsorship: unknown; methodology: unknown
[3] Govulncheck | DefectDojo Documentation — https://docs.defectdojo.com/supported_tools/parsers/file/govulncheck — website (preclassified T4) — date: unknown; basis: heuristic:unverified-domain; sponsorship: unknown; methodology: unknown
[4] Tutorial: Find and fix vulnerable dependencies with govulncheck - The ... — https://go.dev/doc/tutorial/govulncheck — official (preclassified T1) — date: unknown; basis: registry:project-owned:Official domains of the Go project, maintained by the Go team; sponsorship: unknown; methodology: unknown

## 9) Gaps & Limitations
- Did not separately verify the SARIF or OpenVEX output formats' field lists (only the default text and JSON formats were directly inspected); SARIF's generic 'level' field and OpenVEX's status fields are not CVSS scores either, based on their general specs, but govulncheck's own SARIF/VEX writer output was not fetched and read in this session.
- Did not verify whether an OSV record referenced by a Finding.OSV id (fetched separately from vuln.go.dev/<GO-ID>.json) ever carries a CVSS vector in an optional 'severity' field of the general OSV schema; govulncheck's own Finding struct does not embed or re-emit that field regardless.
- finding #3 confidence downgraded from high to medium

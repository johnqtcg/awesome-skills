# Does govulncheck output a CVSS score for each vulnerability?

## Short answer

**No.** `govulncheck` does not emit a CVSS score (or any other severity label — LOW/MEDIUM/HIGH/CRITICAL) for the vulnerabilities it reports, in either its human-readable text output or its structured `-json` / `-format json` output. This is a deliberate design decision by the Go Security team, not a missing feature.

## What govulncheck reports instead

For each finding, govulncheck reports:
- The Go vulnerability database ID (format `GO-<YEAR>-<ENTRYID>`, e.g. `GO-2023-1495`)
- The affected module and package
- The vulnerable version range and the fixed version (if one exists)
- A call-stack trace showing whether/how your code actually reaches the vulnerable symbol (govulncheck's signature "reachability" feature)
- A free-text human-readable description of the vulnerability

None of these fields is a CVSS vector or numeric score.

## Evidence

**1. The Go team explicitly documents why the vulnerability database (which govulncheck queries) has no severity/CVSS labels.**

From the official Go documentation, "Go Vulnerability Management" (https://go.dev/doc/security/vuln/), under "Why does the Go vulnerability database not use severity labels?":

> "Most vulnerability reporting formats use severity labels such as 'LOW,' 'MEDIUM', and 'CRITICAL' to indicate the impact of different vulnerabilities... For several reasons, however, Go avoids using such labels. The impact of a vulnerability is rarely universal... Labeling severity is also necessarily subjective. This is true even for the CVE program, which posits a formula to break down relevant aspects of a vulnerability, such as attack vector, complexity, and exploitability. All of these, however, require subjective evaluation. We believe good descriptions of vulnerabilities are more useful than severity indicators."

(The "formula" referenced here — attack vector / complexity / exploitability — is CVSS; the Go team names the CVE program's scoring approach and states they intentionally do not adopt it.)

**2. The actual JSON output schema has no severity/CVSS field.**

The `-json` output of govulncheck is defined by the `golang.org/x/vuln/internal/govulncheck` package. Its core `Finding` struct (the type that represents one discovered vulnerability instance) is:

```go
type Finding struct {
    OSV          string   `json:"osv,omitempty"`          // the GO-YYYY-NNNN advisory ID
    FixedVersion string   `json:"fixed_version,omitempty"`
    Trace        []*Frame `json:"trace,omitempty"`
}
```
(https://pkg.go.dev/golang.org/x/vuln/internal/govulncheck — "type Finding")

There is no `Severity`, `CVSS`, `Score`, or similar field anywhere in this package's exported types (`Config`, `Finding`, `Frame`, `Handler`, `Message`, `Module`, `Position`, `Progress`, `SBOM`, `ScanLevel`, `ScanMode`).

**3. The underlying advisory data itself (OSV-format entries served by the Go vulnerability database) also carries no severity/CVSS field in Go's implementation.**

Go publishes its advisories in OSV format, and the Go-side type modeling those entries is `golang.org/x/vuln/internal/osv.Entry` (https://pkg.go.dev/golang.org/x/vuln/internal/osv — "type Entry"). Its fields include `SchemaVersion`, `ID`, `Modified`, `Published`, `Withdrawn`, `Aliases`, etc. — no `Severity` or `CVSS` field is defined. (The general OSV schema spec allows an optional `severity` field for producers who want to include a CVSS vector/score, but Go's own advisories do not populate one, consistent with the policy stated in source #1.)

## Practical implication for an advisory-triage doc

If your triage workflow depends on CVSS for prioritization, you cannot get it from govulncheck's own output. Options seen in practice:
- Use govulncheck's **reachability** signal (is the vulnerable symbol actually called by your code?) as the primary triage axis instead of severity — this is what the Go team recommends in place of a severity score.
- Cross-reference the `GO-YYYY-NNNN` ID (via its `Aliases`, typically including the corresponding `CVE-YYYY-NNNNN` and/or `GHSA-...` identifier) against NVD, GitHub Advisory Database, or another source that does publish CVSS, if a numeric score is required for your process.

## Sources

- [Go Vulnerability Management — "Why does the Go vulnerability database not use severity labels?"](https://go.dev/doc/security/vuln/) (go.dev, official Go documentation)
- [Go Vulnerability Database schema docs](https://go.dev/doc/security/vuln/database) (go.dev, official Go documentation)
- [`golang.org/x/vuln/internal/govulncheck` package docs — `Finding` struct definition](https://pkg.go.dev/golang.org/x/vuln/internal/govulncheck) (pkg.go.dev, generated from source)
- [`golang.org/x/vuln/internal/osv` package docs — `Entry` struct definition](https://pkg.go.dev/golang.org/x/vuln/internal/osv) (pkg.go.dev, generated from source)

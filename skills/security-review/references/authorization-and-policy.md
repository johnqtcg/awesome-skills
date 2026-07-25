# Security Review — Authorization, Standards, and Reporting Policy

Detail behind four SKILL.md sections. Load when you are about to touch a running system, map
a finding to ASVS, review a non-Go stack, or decide whether a finding blocks a merge.

---

## 1. Active Verification Authorization Gate (full rules)

This skill can issue network requests and run scanners. **A tool grant is not an
authorization.** Static analysis is always in scope; sending one request to a target you were
not authorized to test is unauthorized activity, regardless of intent.

### What is permitted without asking

| Always allowed | Never allowed without explicit authorization |
|---|---|
| Reading code, config, diffs, manifests | Any request to a host you did not stand up |
| Static scanners on local source (`gosec`, `semgrep`, `bandit`, `govulncheck`, `npm audit`) | Requests to staging/production, even read-only `GET` |
| `go test -race` and other local test runs | Authenticating with credentials found in the repo |
| Requests to `127.0.0.1` / `localhost` / a container you started for this review | Scanning a third party's host or a vendor API |

Ambiguous cases — a `.test`/`.local` domain, a shared dev cluster, a hostname in
`docker-compose.yml` you did not launch — are **not permitted**; ask first. Never infer
authorization from a hostname in code, a `.env` file, a README, or a CI config.

### Rules when active verification IS authorized

- **Non-destructive only.** Read-only probes. No `POST`/`PUT`/`PATCH`/`DELETE` against shared
  state; no payload intended to write, drop, exhaust, or degrade (no `; DROP TABLE`, no `rm`,
  no fork bombs, no fuzzing loops, no `sleep()` SQL that pins a connection). Prove the
  vulnerability *class* with the least invasive request that works.
- **Production is static-only by default.** Even with authorization, a production target gets
  code review, not probing, unless the user explicitly authorizes production testing and names
  a maintenance/change window.
- **One request, not a scan.** Demonstrate; do not enumerate. No brute force, no ID
  enumeration beyond the two IDs needed to show an IDOR, no automated crawling. Stay under a
  few requests per second and stop at the first confirmation.
- **Credentials.** Use only test accounts the user provided. Never use credentials discovered
  in the repo, git history, or a config file — finding them is the finding; using them is a
  separate act. Never place a real token in report output; write `<tokenA>`.
- **Log every request** in `Automation Evidence`: method, target, and why it was necessary.
- **Stop on unexpected impact.** If a probe causes an error spike, data change, or anything
  you did not predict, stop, record it under `Uncovered Risk List`, and tell the user.

### Reproducers when active verification is NOT permitted

A `confirmed` P0/P1 does **not** require you to have executed anything — static proof (the
vulnerable path read end-to-end in code) is sufficient.

- Label it `Reproducer (NOT executed — no authorization to test)`.
- Use a non-routable placeholder target (`http://127.0.0.1:8080`, `https://<target-host>`),
  never a real-looking production hostname.
- Set `Confidence: confirmed` only if the code path alone proves it; otherwise `likely`.
- Never describe a command you did not run as if you had run it.

---

## 2. Stack Detection and the 10 Domains

Gate D's 10 domains are **review axes, not Go features**. What changes per stack is the
sink/idiom table you load.

| Step | Rule |
|---|---|
| 1. Detect stack | `go.mod` → `go`; `package.json` → `nodejs`; `pom.xml`/`build.gradle` → `java`; `pyproject.toml`/`requirements.txt` → `python` |
| 2. Load matching reference | `go-secure-coding.md` / `lang-nodejs.md` / `lang-java.md` / `lang-python.md`, plus `scenario-checklists.md` always |
| 3. Evaluate the same 10 domains | Domain names and numbering never change; only the evidence idioms do |
| 4. Record the stack | Set `stack` in JSON and name it in the coverage header |

**Domain 2 (resource inventory) generalises**: inventory acquire/release pairs at trust
boundaries in every stack — Go `defer resp.Body.Close()`, Node stream/handle cleanup, Java
try-with-resources, Python `with`.

**Multi-stack repos**: emit one coverage section per detected stack, set `stack` to a
comma-joined list (`"go,nodejs"`), and add `per_stack` to the JSON. A domain is `FAIL` for the
repo if it fails in any stack. Never silently report only the dominant language.

A non-Go stack must not report `N/A` for all ten domains merely because the repo is not Go —
that is a coverage failure, not an exemption.

---

## 3. ASVS Version Pinning

ASVS 5.0.0 reorganised and renumbered the chapters that 4.x used, so a bare `V4` or `V4.1.2`
is ambiguous: it does not say which standard it belongs to, and `V4` alone is a chapter, not a
requirement.

- Write requirement IDs fully qualified: `ASVS 4.0.3 V4.1.2` — version, chapter, section, requirement.
- Declare it once in JSON: `"asvs_version": "4.0.3"` (or `"5.0.0"`).
- Use **one version per report** — never mix.
- The lookup table in `security-review.md` holds **4.0.3 chapter numbers**. They are not valid
  5.0.0 identifiers. If the project audits against 5.0.0, resolve each requirement in the
  5.0.0 document; do not renumber by guessing.
- If you cannot identify the requirement, write `ASVS 4.0.3 V8 (chapter-level)` or
  `Mapping: TBD` with a reason. A plausible-but-wrong requirement ID is worse than an
  acknowledged gap — it survives audit review unchallenged.

---

## 4. Findings vs Uncovered Risk: keep the categories disjoint

The volume cap limits **detail**, not disclosure.

| Section | Means | Never contains |
|---|---|---|
| §1 Findings (incl. `Condensed Findings`) | Defects found | Areas you could not inspect |
| §9 Uncovered Risk List | Coverage gaps — tool/env/access/time | Any confirmed finding, at any severity |

§9's required fields are "area not covered" and "why not covered". A confirmed P2 is the
opposite: inspected, understood, and real. Filing it there tells the reader a known defect is
an unexamined gap, corrupting the one section used to judge how much of the system was
actually reviewed. Overflow P2/P3 therefore go to a `Condensed Findings` subsection of §1, one
line each (`ID — severity — title — file:line`), with `counts.overflow` set in JSON.

---

## 5. When `pre-existing` still blocks

Default for a pre-existing finding is *file a follow-up issue, do not block merge* — a change
should not be held hostage to unrelated debt. That default is a **recommendation to the owning
team, not a security clearance**, and it is void when any of these hold; recommend blocking and
escalate:

- the finding is `P0`, or a `P1` with evidence of active exploitation;
- the current change **widens** the attack surface on that defect (newly exposes the path,
  removes a guard, raises privilege, or increases reachable input);
- this merge is the **release vehicle** (deploy branch, release tag, image build), so merging
  is what ships the vulnerability;
- the defect is in the same file/function being modified, making "unrelated" untrue.

Merge/block is ultimately the owning team's policy call. State the recommendation and the
reason; never present "pre-existing" as a reason the risk is acceptable.

---

## 6. `N/A` Judgment Examples

`N/A` is allowed only with a one-line reason tied to code evidence.

| Domain | Scenario | Verdict | Rationale |
|--------|----------|---------|-----------|
| Randomness safety | Change adds a CLI `--dry-run` flag; no token/session/nonce code touched | `N/A` | No import of `math/rand` or `crypto/rand` in changed files or callers |
| Injection + SQL | Change updates a Markdown documentation file only | `N/A` | No `.go` files changed; no SQL/exec/template paths reachable |
| TLS safety | Change modifies HTTP handler logic but no TLS config, `http.Client`, or dial code | `N/A` | No `tls.Config`, `InsecureSkipVerify`, or custom transport in changed scope |
| Concurrency safety | Change adds a pure function with no shared state, goroutines, or channels | `N/A` | Stateless; no `go` keyword, `sync.*`, or channel ops in diff |
| Container security | No Dockerfile, K8s manifests, or CI pipeline files in changed scope | `N/A` | `git diff --name-only` shows no infra/deploy files |

**Anti-pattern**: marking a domain `N/A` when imports or adjacent call paths carry trigger
signals (`database/sql` imported → Domain 2 must be `Applicable`).

---

## 7. Automation Commands

All of these run against local source. Anything targeting a running system first requires §1.

```bash
# secret pattern sweep
rg -n "(AKIA[0-9A-Z]{16}|-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----|ghp_[A-Za-z0-9]{36}|xox[baprs]-|AIza[0-9A-Za-z\-_]{35}|password\s*=|secret\s*=|token\s*=)" .

# Go race detector on changed packages (mandatory for Standard/Deep if tests exist)
go test -race -count=1 ./path/to/changed/...

# Go security scanners
gosec ./...
govulncheck ./...

# Optional cross-check: module exposure view (may include unreachable vulns).
# binary mode takes a BUILT ARTIFACT, not a package pattern —
# `govulncheck -mode=binary ./...` fails with `"./..." is not a file`.
go build -o /tmp/scan-target ./cmd/server
govulncheck -mode=binary /tmp/scan-target
```

Node / Java / Python equivalents live in the matching `lang-*.md` reference.

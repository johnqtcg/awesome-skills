---
title: security-review skill design rationale
owner: awesome-skills maintainers
status: active
last_updated: 2026-03-27
applicable_versions: current repository version
---

# security-review Skill Design Rationale

`security-review` is an exploitability-first security review framework. Its core idea is: **the goal of security review is to first determine how deep the review should go, which security domains are actually applicable, which risks have a real exploit path, which suspicious points should be suppressed, and which areas remain uncovered, and only then deliver findings with confidence labels, standards mapping, baseline status, and explicit coverage gaps.** That is why the skill turns Review Depth, Evidence Confidence, False-Positive Suppression, Applicability-First Execution, Gates A-F, Scenario Checklists, Automation Evidence, and Output Contract into one fixed process.

## 1. Definition

`security-review` is used for:

- running exploitability-first security review on code changes,
- covering auth, input, secrets, API, data flow, dependencies, resource lifecycle, concurrency, and container risk,
- classifying Lite / Standard / Deep review depth from change scope and trigger signals,
- expressing findings with confidence, CWE/OWASP mapping, and baseline status,
- suppressing false positives while explicitly recording uncovered risks,
- and enforcing general mandatory gates such as Gate A together with Go-specific secure-coding coverage such as Gate D when relevant.

Its output is not only findings. Depending on review depth, it may also include:

- review depth and rationale,
- Go 10-Domain Coverage,
- automation evidence,
- open questions / assumptions,
- risk acceptance register,
- remediation plan,
- machine-readable JSON,
- hardening suggestions,
- uncovered risk list.

From a design perspective, it is closer to a security-review governance framework than to a generic prompt for commenting on code safety.

## 2. Background and Problems

The main problem this skill addresses is not that models cannot spot security issues. It is that security review tends to distort in a few dangerous ways:

- it finds issues but does not separate exploitable vulnerabilities from theoretical concerns,
- it reports security problems without confidence labels or standards mapping,
- it produces reports that look complete without declaring what was never covered.

Without an explicit process, the most common failures cluster into eight categories:

| Problem | Typical consequence |
|---------|---------------------|
| Review depth is not selected first | simple changes get over-reviewed, while complex changes may still be under-reviewed |
| Applicability is not triaged first | every domain gets reviewed mechanically, at high cost and with many empty N/A outputs |
| `confirmed` / `likely` / `suspected` are not separated | severity and evidence strength get mixed together |
| No false-positive suppression exists | path traversal, CSRF, randomness, and similar areas get over-reported |
| Resource lifecycle is not checked | response bodies, transactions, connections, and goroutines leak without being reviewed as security risk |
| Uncovered risk is never declared | the report implies false completeness |
| No standards mapping exists | findings do not integrate cleanly into audit and governance workflows |
| No baseline comparison exists | new issues, regressions, and legacy issues get blended together |

The design logic of `security-review` is to make "how deep should this review go, which domains are relevant, and which paths are actually exploitable?" explicit before deciding how findings should be written and what the report is allowed to claim.

## 3. Comparison with Common Alternatives

It helps to compare the skill with a few common alternatives:

| Dimension | `security-review` skill | Asking a model to "do a security review" | Manual experience-driven review |
|-----------|-------------------------|------------------------------------------|---------------------------------|
| Review-depth routing | Strong | Weak | Medium |
| False-positive suppression discipline | Strong | Weak | Medium |
| Applicability-first execution | Strong | Weak | Weak |
| Confidence and standards mapping | Strong | Weak | Medium |
| Resource lifecycle review | Strong | Medium | Medium |
| Uncovered-risk declaration | Strong | Weak | Weak |
| Machine-consumable output | Strong | Weak | Weak |
| Baseline comparison support | Strong | Weak | Medium |

Its value is not only that the report looks more audit-ready. Its value is that it turns security review from one-off issue spotting into an engineering review process with boundaries, gates, and evidence levels.

## 4. Core Design Rationale

### 4.1 Review Depth Selection Comes First

The first step in `security-review` is not vulnerability hunting. It is selecting:

- Lite,
- Standard,
- or Deep,

based on file count and trigger signals.

This is the structural axis of the skill because one of the most common review failures is not total neglect, but applying the same depth to every change. `security-review` explicitly says:

- small changes with no security-sensitive paths can use Lite,
- auth, crypto, payment, new endpoints, dependency changes, and infra changes force Standard or Deep,
- large changes, new services, new external integrations, or auth redesign push the review into Deep.

The evaluation showed this as one of the clearest skill-only outputs: without-skill could still find important issues, but it never explained why a given review should be Lite or Standard, and therefore never made review cost or coverage boundaries explicit.

### 4.2 Lite / Standard / Deep Are Cost-Control Mechanisms, Not Just Labels

The skill does not treat review depth as a cosmetic label. Each depth changes the process:

- Lite follows only a subset of the gates,
- Standard runs the full 15-step process,
- Deep runs the full 15-step process plus extended call-graph tracing.

This matters because the cost of security review is not uniform. Lite does not mean "no review"; it means a smaller required subset of the process for genuinely low-risk changes, with Gate B/C/E skipped by scope policy and Fast Pass available when all conditions are met. Deep requires longer-path tracing beyond the immediate diff. In other words, the skill turns review intensity from an implicit judgment into an explicit control surface.

### 4.3 Applicability-First Execution Is Necessary

The skill forces a two-phase execution model:

- Phase 1: classify each Go domain as `Applicable` or `N/A`,
- Phase 2: run deep review and domain-specific tooling only for `Applicable` domains.

This is a critical design choice because security review is easy to drown in exhaustive checklist behavior. Applicability-first execution lets the skill decide which domains are genuinely relevant before paying the cost of deeper review and domain-specific tooling. It does not promise total coverage and then fill large tables with empty `N/A`; it first proves why a domain deserves attention.

### 4.4 False-Positive Suppression Must Be a First-Class Rule

Before publishing a finding, `security-review` requires four suppression checks:

1. an upstream guard already blocks the path,
2. the input is not attacker-controlled,
3. the sink is safely handled by framework guarantees,
4. the issue is only theoretical environmental risk without reachable path.

This is extremely important because the fastest way to erode team trust in security review is not to miss a low-priority hardening issue; it is to over-report non-findings as serious vulnerabilities. In the evaluation, without-skill reported `/convert` as CSRF and `openAPISpecPath` as path traversal, while with-skill suppressed or reclassified them to the correct root cause. That shows one of the skill's biggest increments is not only "finding issues," but "not misclassifying issues."

### 4.5 Evidence Confidence Is Mandatory

Every finding must carry one confidence label:

- `confirmed`,
- `likely`,
- `suspected`.

This is not just formatting. It is evidence discipline. Many security reviews are not completely wrong, but they still blur "this looks bad" and "this is proven exploitable." `security-review` requires:

- stronger evidence for high-severity claims,
- `confirmed` to be supported by code and/or reproducible path evidence,
- `likely` to name the one missing runtime assumption,
- `suspected` to say clearly that the evidence is still weak.

In the evaluation, without-skill had no confidence labels in any scenario, while with-skill had them in all three. That makes confidence labeling one of the skill's clearest process-level increments.

### 4.6 Gate A Separately Audits Constructor-Release Pairing

Gate A requires pairing analysis for every acquisition or constructor in changed code and immediately related call paths, such as:

- `New*`,
- `Open*`,
- `Acquire*`,
- `Begin*`,
- `Dial*`,
- `Listen*`,
- `Create*`,
- `WithCancel/WithTimeout/WithDeadline`,

and verifying matching cleanup such as:

- `Close`,
- `Release`,
- `Rollback/Commit`,
- `Stop`,
- `Cancel`,
- or explicit ownership transfer documented in code.

This is a strong design choice because many security-relevant failures are not classic "user-input vulnerabilities." They are lifecycle defects that create availability or consistency risk. By making resource pairing a mandatory gate rather than an optional quality concern, the skill treats leaks, transaction-boundary defects, and unbounded goroutine lifetime as first-class security review issues.

### 4.7 Gate D's 10-Domain Coverage Is the Structural Core

For Go repositories, the skill always routes through 10 domains:

1. randomness safety,
2. injection + SQL lifecycle,
3. sensitive data handling,
4. secret/config management,
5. TLS safety,
6. crypto primitives,
7. concurrency safety,
8. Go-specific injection sinks,
9. static scanner posture,
10. dependency posture.

This is the point where the skill most clearly becomes a framework rather than a prompt. It does not assume a reviewer will naturally remember these domains on every change. Instead, it hard-codes them into the structure and then uses `Applicable/N/A` to control cost. The evaluation also makes this explicit: without-skill was not weak at finding core vulnerabilities, but it had no systematic domain-coverage structure at all, and Gate D coverage itself was 0/3 without the skill.

### 4.8 Gate E's Second-Pass Falsification Matters

After the first-pass findings, the skill forces a second pass that asks:

- what might have been missed because the first pass focused too heavily on one exploit class,
- whether availability, consistency, lifecycle, or partial-failure paths were under-reviewed,
- whether transaction, rollback, cleanup, or idempotency-race issues were missed.

This is mature design because review bias often comes from over-fixating on the first class of issue that appears. Gate E forces the reviewer to actively challenge the first-pass conclusion rather than simply polishing it.

### 4.9 `Uncovered Risk List` as Gate F's Required Output

`security-review` explicitly requires an uncovered-risk list whether or not findings exist.

Each item must explain:

- what area was not covered,
- why it was not covered,
- what the impact would be if a defect were hiding there,
- and what follow-up action and owner suggestion make sense.

This is one of the most governance-relevant parts of the skill. Many security reviews become dangerous not because they contain too few findings, but because they imply "everything important was checked." Gate F directly resists false completeness. In the evaluation, without-skill omitted Gate F in all three scenarios, while with-skill included it every time.

### 4.10 Findings Must Be Standards-Mapped Output Artifacts

Each finding should include standards mapping when applicable:

- `CWE-xxx`,
- `OWASP ASVS <section>`.

The value here is that security-review output becomes useful not only to the immediate engineer, but also to audit, governance, and cross-team tracking. Without standards mapping, a review reads more like an opinionated memo. With mapping, it can enter compliance logs, remediation trackers, and risk registers. This was also one of the clearest skill-only differences in the evaluation.

### 4.11 The Focused Automation Gate Uses "Run What Matters, State What Was Skipped"

The skill's stance on automation is not "run every tool all the time." It is:

- always run the baseline secret-pattern sweep,
- run `gosec`, `govulncheck`, and `go test -race` according to applicable domains and cost,
- if a tool is skipped, say exactly why.

This is practical because security automation is valuable, but tool availability, build health, and testability are not always present. The skill therefore refuses both extremes:

- pretending tools were run when they were not,
- and requiring every tool on every repository regardless of applicability.

It turns automation into evidence discipline instead of process theater.

### 4.12 Language Extension Hooks Matter

Although `security-review` is deepest on Go, it does not bind its core method to Go alone. The skill explicitly includes extension hooks for:

- Node.js / TypeScript,
- Java / Spring,
- Python / FastAPI / Django.

This shows that the stable core of the skill is not Go syntax knowledge itself, but:

- exploitability-first review,
- depth routing,
- suppression discipline,
- uncovered-risk declaration,
- and structured output.

Go is simply the most fully developed reference path today. That separation between review-governance logic and language-specific checklists is what gives the skill long-term extensibility.

### 4.13 Baseline Diff Mode Is Preserved

When previous review artifacts exist, the skill classifies changes as:

- `new`,
- `regressed`,
- `unchanged`,
- `resolved`.

This was not heavily exercised in the current evaluation, but it is still important because security review is rarely a one-time event. Without baseline diffing, teams cannot distinguish:

- what this change introduced,
- what older issues got worse,
- what has actually been fixed.

So Baseline Diff Mode gives the skill continuity across repeated reviews instead of treating every security report as an isolated artifact.

## 5. Problems This Design Solves

Combining the current `SKILL.md`, key references, and the evaluation report, the skill solves the following problems:

| Problem type | Corresponding design | Practical effect |
|--------------|----------------------|------------------|
| Review depth is uncontrolled | Review Depth Selection | Small changes are not over-reviewed; risky ones are not under-reviewed |
| N/A coverage is noisy and expensive | Applicability-First Execution | Triage happens before deep review |
| False positives are common | False-Positive Suppression Rules | Improves developer trust |
| Evidence strength is unclear | Evidence Confidence | Separates confirmed from likely or suspected |
| Resource lifecycle issues get missed | Gate A + Gate B | Improves coverage of response-body, transaction, connection, and goroutine risks |
| Security-domain coverage is unsystematic | Gate D 10-Domain | Makes review structure more complete |
| Reports imply false completeness | Gate F Uncovered Risk List | Makes blind spots explicit |
| Security reports are hard to govern | CWE/OWASP mapping + JSON summary | Better for audit, CI, and tracking |

## 6. Key Highlights

### 6.1 It Turns Security Review into an Exploitability-First Process

This is not just "more checklist coverage." It begins by asking whether the path can actually be exploited.

### 6.2 Review-Depth Routing Is One of Its Most Visible Structural Strengths

Lite, Standard, and Deep bind review cost to change risk. That is one of the biggest things missing from default model behavior.

### 6.3 Its False-Positive Suppression Is Critically Important

Many teams do not reject security review because they dislike security. They reject it because they cannot trust over-reported findings. `security-review` directly improves that trust boundary.

### 6.4 Gates A, D, and F Form a Clear Governance Loop

Gate A handles lifecycle pairing, Gate D handles domain coverage, and Gate F handles uncovered-risk declaration. Together they reduce the chance of "formal-looking but actually incomplete" review.

### 6.5 Its Output Contract Is Built for Downstream Governance

Confidence, CWE/OWASP mapping, baseline status, and JSON summary make the result useful beyond the immediate conversation.

### 6.6 Its Real Increment Is Process Discipline More Than Vulnerability Discovery

The evaluation already shows this clearly: the base model was not weak at finding many core issues. The main delta came from depth routing, suppression, standards mapping, uncovered-risk declaration, JSON output, and systematic coverage. In other words, the skill's real value is review governance.

## 7. When to Use It — and When Not To

| Scenario | Suitable | Reason |
|----------|----------|--------|
| Sensitive changes in auth, input handling, secrets, payments, or APIs | Very suitable | Trigger signals and multi-domain coverage are strong |
| Go services or infra-related changes | Very suitable | Gate A / D support is strongest here |
| Reviews that need audit traceability | Very suitable | Confidence, mapping, JSON, and Gate F are highly useful |
| Benign or low-risk changes | Suitable | Lite + Fast Pass can control review cost |
| Quick informal checking for obvious issues only | Not always | Full structured output may be heavier than needed |
| Contexts that do not need structured outputs at all | Not always optimal | A plain review may sometimes be enough |

## 8. Conclusion

The real strength of `security-review` is not that it can produce more lines that sound like security findings. It is that it systematizes the engineering judgments that security review most often distorts: choose depth based on risk and scope, decide which domains are actually applicable, use suppression discipline to control false positives, use confidence and standards mapping to control claim strength, and then use Gate F to say explicitly what the report did not cover.

From a design perspective, the skill embodies a clear principle: **the key to a high-quality security review is not making the report longer, but making every finding carry an exploit path, making every uncovered area visible, and making the review know what it looked at, what it skipped, and why.** That is why it is especially well suited to engineering security review, audit traceability, and structured remediation workflows.

## 9. Document Maintenance

This document should be updated when:

- the Review Depth logic, Evidence Confidence rules, Suppression Rules, Gate A-F definitions, Scenario Checklists, Focused Automation Gate, Standards Mapping, or Output Contract in `skills/security-review/SKILL.md` change,
- key rules in `skills/security-review/references/go-secure-coding.md`, `scenario-checklists.md`, `severity-calibration.md`, `anti-examples.md`, `security-review.md`, or the language-specific references change,
- key supporting conclusions in `evaluate/security-review-skill-eval-report.md` or `evaluate/security-review-skill-eval-report.zh-CN.md` change.

Review quarterly; review immediately if the depth-routing logic, suppression rules, Gate D / Gate F requirements, or standards-mapping rules of `security-review` change substantially.

## 10. Further Reading

- `skills/security-review/SKILL.md`
- `skills/security-review/references/go-secure-coding.md`
- `skills/security-review/references/scenario-checklists.md`
- `skills/security-review/references/severity-calibration.md`
- `skills/security-review/references/anti-examples.md`
- `evaluate/security-review-skill-eval-report.md`
- `evaluate/security-review-skill-eval-report.zh-CN.md`

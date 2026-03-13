# Security Policy

This document explains how to report security issues for `awesome-skills`, what kinds of issues are in scope, and how responsible disclosure works for a **skill/documentation repository** rather than a hosted service.

## 1. Supported Versions

By default, only the latest code on `main` is guaranteed to receive security fixes or content corrections.

| Version | Supported |
|---|---|
| `main` | Yes |
| Older commits / tags / forks | No (unless explicitly announced) |

## 2. What Counts as a Security Issue Here

Because this repository ships **skills, workflow rules, examples, and helper scripts**, in-scope security issues usually involve repository content that could cause unsafe real-world behavior.

Examples in scope:
- skills or examples that encourage credential pasting, token leakage, or unsafe secret handling
- content that normalizes unauthorized access, paywall bypass, DRM bypass, or exploit publication without safeguards
- scripts or examples with unsafe defaults that could trigger destructive actions unexpectedly
- committed secrets, private keys, tokens, or sensitive data in examples, screenshots, or output artifacts
- materially misleading instructions that could cause users to run unsafe commands against real systems

## 3. What Is Usually Out of Scope

These are usually not treated as repository security vulnerabilities by themselves:
- general model-output variability across different AI models
- disagreements about writing style, prompt style, or evaluation methodology with no concrete safety impact
- hypothetical jailbreaks or misuse scenarios without a repository artifact that materially enables them
- third-party platform, model-provider, or network incidents not caused by this repository's content
- low-severity documentation mistakes that do not create a realistic unsafe path

Maintainers make the final triage decision for disputed cases.

## 4. Reporting a Security Issue

Please do **not** disclose sensitive details in a public Issue or PR.

Preferred private channel:
- GitHub Security Advisory (Private Report):
  `https://github.com/johnqtcg/awesome-skills/security/advisories/new`

If you cannot use that channel:
- Open a public Issue with only minimal, non-sensitive context.
- State that a private follow-up is required.
- Do **not** include secrets, live exploit payloads, private endpoints, or reproducible harmful instructions.

## 5. What to Include

To help triage quickly, include:
- affected file(s) and path(s)
- affected branch/commit if known
- why the content is unsafe or exploitable
- minimal reproduction or misuse scenario
- whether any real secret or sensitive data is exposed
- suggested mitigation or patch, if you have one

## 6. Response Targets

Maintainers target:
- acknowledgement within 72 hours
- initial triage within 7 calendar days
- follow-up updates until resolution or closure

These are best-effort targets, not a legal guarantee.

## 7. Disclosure Principles

- Before a fix lands, avoid public disclosure of exploitable details.
- Do not publish secrets, harmful payloads, or step-by-step abusive instructions in Issues, PRs, or Discussions.
- After remediation, maintainers may coordinate a public summary if doing so helps users correct downstream copies.
- If a high-risk issue is already being abused, maintainers may publish mitigations before publishing full details.

## 8. Repository-Specific Notes

This repository is **not** a hosted service and does **not** provide runtime isolation guarantees.

Security review here focuses on:
- skill design guidance
- example safety
- secret handling
- bundled helper scripts
- whether repository content pushes users toward unsafe real-world actions

For general conduct issues, see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

<!--
Thanks for the contribution!

This template serves *both* trivial and non-trivial changes. For trivial changes
(typos, single-line fixes, doc edits) you can delete the Constitutional Compliance
Check table.

For non-trivial changes — see CLAUDE.md § 9 — the Compliance Check is required.
A change is non-trivial when ANY is true:
  • diff > 200 lines of meaningful code
  • the change spans ≥2 packages
  • the change adds, removes, or modifies a publicly exported API
  • the change modifies a database schema, wire contract, or persistent format
-->

## Summary

<!-- 1–3 sentences describing WHY this change is needed, not just what it does. -->

## Changes

<!-- Bullet list of the concrete changes made. -->
-
-

## Test Plan

- [ ] Unit tests pass locally (`go test ./...`)
- [ ] Race detector clean (`go test -race ./...`)
- [ ] Coverage threshold met (`go test -coverprofile=coverage.out ./...`)
- [ ] Manually verified: <describe the scenario>

<!--
================ Constitutional Compliance Check (non-trivial changes) ================
Required for non-trivial changes. Delete for trivial edits.
Map each principle to Applicable? / Complies? / Deviation justification.

"Applicable" = this change touches a surface the principle covers.
"Complies"   = yes / no. If no, explain in the justification column.
================================================================================
-->

## Constitutional Compliance Check

| # | Principle | Applicable? | Complies? | Deviation & justification |
|---|-----------|:-----------:|:---------:|---------------------------|
| I | Simplicity & Library-First (YAGNI, stdlib-first, no premature abstraction) | ☐ | ☐ | |
| II | Test-First (NON-NEGOTIABLE) — TDD, table-driven, integration over mocks, `-race`, coverage, determinism, behavior-asserting | ☐ | ☐ | |
| III | Explicit Error Handling (NON-NEGOTIABLE) — no swallowing, wrap with context, errors not panics, log-once, context first param | ☐ | ☐ | |
| IV | Safety by Default (NON-NEGOTIABLE) — boundary validation, secrets, no PII in logs, injection-safe, TLS, crypto, vuln scan | ☐ | ☐ | |
| V | Concurrency Discipline (NON-NEGOTIABLE) — goroutine lifecycle, channel ownership, minimal critical sections, race-free, loop-var capture | ☐ | ☐ | |
| VI | Observability by Design — structured logs, level discipline, request correlation, metric cardinality, span lifecycle, SLO alignment | ☐ | ☐ | |
| VII | Service Lifecycle & Readiness — signal handling, graceful shutdown, liveness vs readiness, client bounds, retries & backoff | ☐ | ☐ | |
| VIII | API Contracts & Object-Level Authorization (NON-NEGOTIABLE) — stable envelope, semantic status codes, per-object authz, idempotency, handler-layer validation, SemVer | ☐ | ☐ | |
| IX | Single Responsibility & Cohesion — capability-based packages, no global mutable state, consumer-side interfaces, one-way deps, right-sized functions | ☐ | ☐ | |

### Dependencies added (fill in only if this PR adds a non-stdlib module)

- **Module:**
- **Problem it solves:**
- **Why stdlib is insufficient:**
- **Maintenance health** (last release, open issues, maintainer count):
- **License compatibility:**
- **Transitive footprint** (`go mod why` / `go mod graph`):

<!--
Refusals: if this change would require violating a NON-NEGOTIABLE clause (II, III, IV, V, VIII),
STOP. Surface the conflict to the reviewer in plain terms — what rule, what the request is,
what alternatives remain — instead of merging.
-->

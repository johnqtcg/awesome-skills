**Mode**: Write
**Doc type**: not yet determined — "documentation for the payment service" does not say whether
you need a concept overview, a runbook, or an API reference. The scaffold below is deliberately
type-neutral; tell me the reader's goal and I will collapse it to one type.
**Resolution**: R1 searched for a corpus (no `docs/` tree, no README section on payments, no ADRs,
no OpenAPI spec) → nothing found. R2 asking is unavailable in this non-interactive run.
→ **R3 → Level 3 (Scaffold)**, because the gap is content, not just audience.

**What I searched and did not find** — so you can see the gap rather than trust a summary:

| Looked for | Where | Result |
|---|---|---|
| Existing payment docs | `docs/**`, `README*` | not found |
| Service entry point | `cmd/**`, `main.go`, `app.py` | not found |
| API contract | `api/**`, `*.proto`, `openapi*.yaml` | not found |
| Config / dependencies | `*.env*`, `docker-compose*`, chart values | not found |

Nothing below is invented. Every unknown is a `TODO` placeholder.

<!-- BEGIN DOCUMENT -->
---
title: Payment Service
owner: TODO
status: draft
last_updated: 2026-07-26
---

# Payment Service

<!-- TODO: one sentence — what the service does and who depends on it. -->

## Scope

<!-- TODO: what this document covers, and explicitly what it does not. -->

## Architecture

<!-- TODO: upstream callers, downstream dependencies, data stores. A diagram if more than
     three components. -->

## Interfaces

<!-- TODO: endpoints or queue topics, with request/response shapes. If an OpenAPI spec
     exists, generate this section from it rather than hand-writing it. -->

## Configuration

<!-- TODO: environment variables and their defaults. Do not guess values. -->

## Failure modes

<!-- TODO: what breaks, how it surfaces, and who is paged. -->

## Runbook links

<!-- TODO: link operational procedures once they exist. -->
<!-- END DOCUMENT -->

## What I need from you

Answering these three collapses the scaffold into a real document:

1. Who is the reader — an integrator calling the API, or an on-call engineer operating it?
2. Is there an OpenAPI/proto spec I can generate the Interfaces section from?
3. Which repository holds the service?

## Quality Scorecard

Type is undetermined, so this is scored as the broadest case (`concept`) and re-scored once the
type is fixed.

- **Critical**: 2/3 applicable pass (2 N/A — per-step verification and parameter tables). The
  metadata item fails: `owner` is a TODO, which is correct for a scaffold but is still a gap.
- **Standard**: 1/2 applicable pass (4 N/A) → FAIL (need 2/2). Expected at Level 3.
- **Hygiene**: 2/2 applicable pass (2 conditional not applicable, 2 N/A) → PASS.

This is a **Level 3 scaffold, not a document**. Do not publish it.

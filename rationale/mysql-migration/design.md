---
title: mysql-migration skill design rationale
owner: awesome-skills maintainers
status: active
last_updated: 2026-04-14
applicable_versions: current repository version
---

# mysql-migration Skill Design Rationale

`mysql-migration` is a MySQL schema migration safety reviewer and DDL generator. Its core idea is: **MySQL DDL locking behavior is version-dependent and operation-dependent in ways that are non-obvious, and the consequences of getting it wrong are severe**. A 30-second lock on a 50M-row production table causes a service outage. The skill exists to prevent that.

## 1. Definition

`mysql-migration` is a structured MySQL DDL safety review skill. It first collects context (version, row count, topology), then selects review depth and operating mode, then applies a DDL safety checklist item by item, and finally produces output via the §9 Output Contract — with Context Gate, Risk Assessment Table, Execution Plan, Migration SQL, Validation SQL, Rollback Plan, Post-Deploy Checks, and Uncovered Risks always present.

## 2. Background and Problems

MySQL DDL safety has a specific set of failure patterns. Most production incidents from schema migrations fall into one of five categories:

| Failure mode | Consequence |
|--------------|-------------|
| Wrong algorithm — COPY when INPLACE was viable | Full exclusive lock for 30–90+ minutes on large tables |
| Batched ALTER with mixed algorithms | INSTANT-eligible ADD COLUMN gets silently downgraded to COPY because it was batched with a type change |
| No session guards | Stalled DDL queues indefinitely, cascading into connection pool exhaustion |
| NOT NULL on column with existing NULLs | ALTER fails after full table scan; COPY already in progress → minutes of rollback lock |
| gh-ost without dry-run | Migration starts on production table without validating connectivity, user permissions, or schema state |

The skill addresses these systematically. It is not solving "nobody knows SQL" — it is solving the gap between "I know what I want to do" and "I know exactly which algorithm will execute and whether it requires tools."

## 3. Why Four Mandatory Gates?

Gate 2 (mode: review/generate/plan) and Gate 4 (completeness check) exist to bound scope and prevent incomplete output. The critical design decisions are around Gates 1 and 3.

**Gate 1 (Context Collection)** addresses the most common source of migration errors: operating without knowing version and row count. The skill collects 8 context items before giving advice. When items are missing, it doesn't refuse to help — it records the assumption (always conservative: 5.7, high-traffic, source-replica) and proceeds. This is the degradation model — graceful fallback, not silence.

**Gate 3 (Risk Classification)** adds a hard stop: any UNSAFE item without a mitigation plan blocks the output. This prevents the skill from producing "use gh-ost" as a footnote while the main output describes a native ALTER. The mitigation must be present before the output is complete.

## 4. The Algorithm Matrix as External Reference

The DDL algorithm matrix is in `references/ddl-algorithm-matrix.md`, not inline in SKILL.md. This was a deliberate design choice.

The matrix is large (80+ operation rows across MySQL 5.7 and 8.0 with notes). Inlining it would make SKILL.md too long to reason about quickly. More importantly, the algorithm is a **lookup table**, not reasoning logic — it tells you what the server will do, but the skill's job is to decide what you should do and why. Separating them keeps SKILL.md focused on process (when to look things up and what to do with the result) while the reference stays focused on facts.

The same logic applies to `large-table-migration.md`: gh-ost command templates, 5-phase execution patterns, and batch sizing rules are loaded on demand (Deep depth or >10M rows) rather than always present.

## 5. Degradation Mode Design

MySQL migrations fail in a specific degraded context: the engineer knows the target schema change but doesn't know the current table size or exact MySQL version. This is common in practice — someone is reviewing a migration file from a colleague without database access.

The skill defines four operating modes (Full/Degraded/Minimal/Planning) and maps each to a set of capabilities and constraints. The key rules:

- **Never claim SAFE without evidence.** In Degraded/Minimal mode, every SAFE verdict is qualified: "SAFE (assumed — verify against production)."
- **Assume 5.7 (most restrictive) when version is unknown.** This prevents INSTANT recommendations that only work on 8.0.12+.
- **Name the mode explicitly.** Calling out "DEGRADED MODE ACTIVE" is important because it sets the reader's expectations for the entire output — every conclusion is conditional.

The evaluation confirmed this matters: when operating without the skill, a baseline Claude response on an unknown-version review implied INSTANT might be available on 5.7 (it isn't). The degradation rules prevent this class of error.

## 6. The INSTANT Boundary Trap (utf8mb4 VARCHAR Extension)

One specific edge case is hard enough to be worth naming in the rationale: VARCHAR extension across the 255-byte storage boundary under utf8mb4.

MySQL stores the length prefix of VARCHAR differently depending on byte size:
- ≤ 255 bytes: 1-byte length prefix
- > 255 bytes: 2-byte length prefix

With utf8mb4 (max 4 bytes/char): VARCHAR(60) = 240 bytes (≤255, 1-byte prefix), VARCHAR(100) = 400 bytes (>255, 2-byte prefix). Crossing this boundary requires COPY algorithm — no INPLACE or INSTANT option exists because the row format changes. This catches engineers who apply the rule "VARCHAR extension is fast" without considering the encoding-specific byte threshold.

The skill encodes this in both the DDL algorithm matrix reference and in §7 Anti-Examples. The evaluation confirmed that baseline Claude can discover this independently — but the matrix and the checklist item 5.1.1 ensure it is always caught, not just sometimes.

## 7. The §9 Output Contract

The Output Contract is the skill's completeness gate. Its nine required sections exist because each one prevents a specific failure:

| Section | Failure it prevents |
|---------|---------------------|
| §9.1 Context Gate | Advice given without stated assumptions — no way to verify correctness later |
| §9.3 Risk Assessment Table | Per-operation risk not explicitly labeled — reviewer cannot scan for UNSAFE |
| §9.4 Execution Plan | "Just run ALTER" without phases — no separation of INPLACE-safe from COPY-required ops |
| §9.5 Migration SQL with guards | Session guards absent — DDL queues indefinitely under MDL contention |
| §9.7 Rollback Plan | No rollback — irreversible changes made without documented recovery path |
| §9.9 Uncovered Risks | Known unknowns invisible — reviewer assumes completeness when context is missing |

Section §9.9 (Uncovered Risks) has a special rule: it can never be empty. Even in Full mode with complete context, there are always residual unknowns (application behavior during lock, foreign key chains across schemas, binlog format on replicas). Forcing it to exist keeps the output honest about the limits of what a static review can determine.

**Scorecard** (appended after §9.9): The 12-point scoring structure (Critical 3/Standard 5/Hygiene 4) serves as the review's bottom-line verdict. It converts the narrative analysis into a binary pass/fail that can be enforced at code review time: "FAIL on Critical means this migration cannot be deployed as written."

## 8. Comparison with Common Alternatives

| Dimension | `mysql-migration` skill | Generic model without skill | Static linter (pt-audit, etc.) |
|-----------|------------------------|---------------------------|-------------------------------|
| DDL algorithm accuracy | Strong (matrix + checklist) | Medium (correct often, confused on edge cases) | Weak (schema-only, no version awareness) |
| Large-table detection | Strong (>10M triggers tool recommendation) | Medium (varies) | Weak |
| Degradation mode | Strong (named, explicit) | Weak (silent assumptions) | Not applicable |
| Session guard enforcement | Strong (Critical checklist item) | Weak (not always checked) | Not applicable |
| Output structure | Strong (§9 contract) | Weak (varies by request) | Structured but narrow |
| Rollback planning | Strong (per-phase) | Weak (narrative only) | Not applicable |
| False claim prevention | Strong (never SAFE without evidence) | Medium | Not applicable |

## 9. Design Decisions Not Taken

**Not a trigger-based skill (no trigger accuracy metric)**: Unlike review skills that need to decide whether to activate, `mysql-migration` is always invoked explicitly. It doesn't need to discriminate between "yes this is a migration review" and "no this is something else" — the user invoked it on purpose.

**Not a pt-osc-only skill**: Early drafts favored pt-osc exclusively. gh-ost is recommended as the default because it uses binlog streaming (no triggers), supports pause/resume via socket, and has built-in replica lag throttling. pt-osc is noted for FK-constrained tables (gh-ost cannot handle inbound FKs). The skill doesn't lock engineers into one tool.

**Not a one-file-per-skill structure**: The `SKILL.md` body is ~280 lines, within the 420-line budget. References are loaded on demand. This avoids the trap of a skill that is too long to scan but too short to be useful — the skill body is the reasoning logic, the references are the lookup tables.
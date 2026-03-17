# Document Type Templates

Load only the template matching the classified document type. Do not load all templates.

## Table of Contents

1. [Task Document (Runbook)](#task-document-runbook)
2. [Concept Document](#concept-document)
3. [Reference Document](#reference-document)
4. [Troubleshooting Document](#troubleshooting-document)
5. [Design Document (RFC / ADR)](#design-document-rfc--adr)

---

## Task Document (Runbook)

Use when the reader's goal is **"complete an operation"**.

```markdown
# <Verb + Object, e.g. "Deploy XXX Service">

## 1. Goal and Scope
- Target reader:
- Problem solved:
- Applicable scope:
- Out of scope:

## 2. Prerequisites
- Permissions:
- Environment:
- Dependencies:
- Input materials:

## 3. Steps
### 3.1 <Step Name>
- Purpose:
- Command:
  ```bash
  <copy-paste command>
  ```
- Expected output:
  ```text
  <key output>
  ```
- Common failures:

### 3.2 <Step Name>
...

## 4. Verification and Rollback
- Verify command:
- Pass criteria:
- Rollback trigger:
- Rollback steps:

## 5. Troubleshooting (FAQ)

## 6. Metadata
- Owner:
- Created:
- Last updated:
```

**Minimum viable task doc**: must contain at least Prerequisites, Steps, Expected Output, Verification, Rollback. A task doc missing any of these five is not deliverable.

---

## Concept Document

Use when the reader's goal is **"understand a concept"**.

```markdown
# <Noun Phrase, e.g. "Connection Pool Internals">

## 1. Definition
<One sentence: what is it?>

## 2. Background and Problem
<Why does this concept/component exist? What problem does it solve?>

## 3. Core Principles
<How it works. Use diagrams for 3+ interacting components.>

## 4. When to Use / When NOT to Use

| Scenario | Use? | Reason |
|----------|------|--------|
|          | ✓    |        |
|          | ✗    |        |

## 5. Comparison with Alternatives

| Dimension | This Approach | Alternative A | Alternative B |
|-----------|--------------|---------------|---------------|
| Pros      |              |               |               |
| Cons      |              |               |               |
| Best for  |              |               |               |

## 6. Minimal Example
<Runnable or annotated code/config that demonstrates the concept.
Mark as "simplified example" if not production-ready.>

## 7. Common Misconceptions
<List pitfalls readers frequently fall into.>

## 8. Further Reading
<Official docs, seminal blog posts, related internal docs.>
```

---

## Reference Document

Use when the reader's goal is **"look up a parameter"**.

```markdown
# <Noun Phrase, e.g. "Order API Parameter Reference">

## 1. Overview
<One paragraph: what this reference covers, target audience, applicable versions.>

## 2. Data Dictionary / Parameter Table

| Field | Type | Required | Default | Description | Since |
|-------|------|----------|---------|-------------|-------|
|       |      |          |         |             |       |

## 3. Example Request and Response

**Request**
```http
POST /api/v1/orders HTTP/1.1
Content-Type: application/json

{
  "item_id": "abc-123",
  "quantity": 2
}
```

**Response (success)**
```json
{
  "order_id": "ord-456",
  "status": "created"
}
```

**Response (error)**
```json
{
  "code": "INSUFFICIENT_STOCK",
  "message": "Requested quantity exceeds available stock"
}
```

## 4. Error Codes

| Code | HTTP Status | Trigger Condition | Recommended Action |
|------|-------------|-------------------|-------------------|
|      |             |                   |                   |

## 5. Compatibility and Version Differences

| Version | Change | Migration Notes |
|---------|--------|-----------------|
|         |        |                 |

## 6. Changelog

| Date | Change | Author |
|------|--------|--------|
|      |        |        |
```

---

## Troubleshooting Document

Use when the reader's goal is **"diagnose and fix a failure"**.

```markdown
### Incident: <Title>
- Symptom:
- Impact:
- Environment:
- Root cause: <with evidence — logs, metrics, traces>

#### Resolution Steps
1. Step (command + expected output)
2. ...

#### Verification
- Command:
- Pass criteria:

#### Prevention
- Monitoring:
- Alert threshold:
- Process improvement:
```

**Quality bar**: every troubleshooting doc must have evidence for the root cause (not "might be X"). Resolution steps must be executable with expected output. Prevention must include at least one monitoring item.

---

## Design Document (RFC / ADR)

Use when the reader's goal is **"record a decision"**.

```markdown
# <RFC/ADR Number>: <Title>

## Metadata
- Author:
- Status: Draft / In Review / Accepted / Superseded
- Created:
- Decision deadline:

## 1. Background and Problem

## 2. Goals and Non-Goals
**Goals**
-

**Non-Goals (explicitly out of scope)**
-

## 3. Alternatives Comparison

| Dimension    | Option A | Option B |
|-------------|----------|----------|
| Core approach |        |          |
| Complexity  |          |          |
| Performance |          |          |
| Ops cost    |          |          |
| Risk        |          |          |

## 4. Decision
Chosen: Option <X>.

**Why chosen**:

**Why not Option <Y>**:

## 5. Detailed Design
### 5.1 Interface
### 5.2 Data Model
### 5.3 Key Flows

## 6. Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|

## 7. Milestones

| Milestone | Date | Acceptance Criteria |
|-----------|------|---------------------|

## 8. Open Questions

| Question | Owner | Deadline |
|----------|-------|----------|
```

**Design doc essentials**:
- Alternatives comparison is the soul — writing "we chose X" without explaining why Y was rejected has no value.
- Non-goals are as important as goals — they prevent scope creep and tell reviewers what questions are out of scope.
- Status must be maintained — when superseded, add `Superseded by: <link>` to prevent future misuse.
- ADR is the lightweight variant: Title → Background → Decision → Consequences. Use when full RFC is overkill.

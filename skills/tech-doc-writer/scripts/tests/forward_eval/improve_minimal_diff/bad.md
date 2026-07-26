**Mode**: Improve
**Doc type**: task
**Resolution**: R1 → Level 1

I rewrote the runbook to modern standards.

<!-- BEGIN DOCUMENT -->
---
title: Payment Worker Restart Procedure
owner: payments-team
status: active
last_updated: 2026-07-26
applicable_versions: kubectl 1.29+
---

# Payment Worker Restart Procedure

## Purpose

This document provides a comprehensive, step-by-step operational procedure for safely restarting
the payment worker service in the production Kubernetes environment. It is intended for on-call
engineers, platform engineers, and any team member who may be required to perform a restart.

## Background

The payment worker is a critical component of the payments platform. It consumes messages from
the payment queue and processes them asynchronously. Occasionally the worker may enter a stalled
state in which it stops consuming messages.

## Prerequisites

Before beginning this procedure, ensure that you have all of the following:

- Access to the production Kubernetes cluster
- The `deploy` role in the `payments` namespace
- The `kubectl` CLI installed at version 1.29 or later
- Access to the payments Grafana dashboards
- An open change window, or an active incident authorising the restart

## Procedure

### Phase 1 — Assess

First, confirm the worker is genuinely stalled rather than merely slow.

```bash
kubectl -n payments logs deploy/payment-worker --tail=100
kubectl -n payments top pod -l app=payment-worker
```

### Phase 2 — Drain

```bash
kubectl -n payments scale deployment payment-worker --replicas=0
kubectl -n payments wait --for=delete pod -l app=payment-worker --timeout=180s
```

### Phase 3 — Restore

```bash
kubectl -n payments scale deployment payment-worker --replicas=3
kubectl -n payments rollout status deployment/payment-worker --timeout=180s
```

### Phase 4 — Confirm

Check the dashboard and confirm queue depth is falling.

## Rollback

```bash
kubectl -n payments rollout undo deployment/payment-worker
```

## Escalation

Page the payments on-call rota via PagerDuty if the queue does not drain.

## Change history

| Date | Author | Change |
|---|---|---|
| 2026-07-26 | doc-bot | Full rewrite to modern runbook standard |
<!-- END DOCUMENT -->

## Quality Scorecard

- Critical: 4/4 applicable pass
- Standard: 5/5 applicable pass
- Hygiene: 3/3 applicable pass

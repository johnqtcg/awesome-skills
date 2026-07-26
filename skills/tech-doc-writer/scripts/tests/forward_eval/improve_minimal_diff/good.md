**Mode**: Improve
**Doc type**: task (runbook) — unchanged from the original.
**Resolution**: R1 — the document states its own owner and reader context, so no retrieval or
assumption was needed → Level 1.

Scorecard-flagged defects, and nothing else, were changed:

| Defect | Tier | Fix |
|---|---|---|
| No expected output / verification on any step | Critical [task] | Added expected output to each step and a Verification section |
| No rollback path with trigger conditions | Standard [task] | Added Rollback with an explicit trigger |
| Prerequisites incomplete (no permission/environment) | Standard [task] | Named the namespace permission |

**Preserved deliberately**: the two `kubectl scale` commands (already correct), the title and
owner metadata, the step order, and the author's terse voice. `last_updated` bumped because the
content changed.

<!-- BEGIN DOCUMENT -->
---
title: Restart Payment Worker
owner: payments-team
status: active
last_updated: 2026-07-26
---

# Restart Payment Worker

Restart the payment worker when its queue stalls.

## Prerequisites

- kubectl access with `deploy` role in the `payments` namespace
  (`kubectl auth can-i update deployments -n payments` returns `yes`)

## Steps

1. Scale the deployment down.

   ```bash
   kubectl scale deploy/payment-worker --replicas=0 -n payments
   ```

   Expected output: `deployment.apps/payment-worker scaled`

2. Wait for pods to terminate.

   ```bash
   kubectl wait --for=delete pod -l app=payment-worker -n payments --timeout=120s
   ```

   Expected output: no pods listed, or `pod ... condition met`

3. Scale back up.

   ```bash
   kubectl scale deploy/payment-worker --replicas=3 -n payments
   ```

   Expected output: `deployment.apps/payment-worker scaled`

## Verification

`kubectl get deploy/payment-worker -n payments` shows `READY 3/3`, and the queue depth on the
`payments-worker` dashboard falls within 5 minutes.

## Rollback

Trigger: pods do not reach `READY 3/3` within 5 minutes, or queue depth keeps climbing.

```bash
kubectl rollout undo deploy/payment-worker -n payments
```

Then page the payments on-call.

## Notes

Ask the on-call engineer if anything looks wrong.
<!-- END DOCUMENT -->

## Quality Scorecard

Type is `task`.

- **Critical**: 4/4 applicable pass (1 N/A — parameter tables). Per-step expected output now
  present, which was the blocking failure.
- **Standard**: 4/5 applicable pass (1 N/A — error codes) → PASS (need 4/5). The remaining gap is
  "code examples self-contained": commands assume `kubectl` context is already set, matching the
  original author's convention — left as-is rather than restructuring a passing document.
- **Hygiene**: 2/3 applicable pass → PASS (need 2/3). No `applicable_versions` added because the
  original pinned no versions; adding one would be an unrequested change.

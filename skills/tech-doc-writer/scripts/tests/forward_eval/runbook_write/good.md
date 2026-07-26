**Mode**: Write
**Doc type**: task (runbook) — the request is "complete an operation", so the questions to answer
are How? How to verify? How to rollback?
**Audience**: on-call engineers deploying the REST API; they know kubectl and the service, not this
service's deploy sequence.
**Resolution**: R1 retrieved — repo `CONTRIBUTING.md` names the on-call rota as runbook readers, so
no assumption was needed → Level 1.
**Reference loaded**: templates.md § Task Doc (runbook) skeleton.

<!-- BEGIN DOCUMENT -->
---
title: Deploy REST API
owner: api-platform
status: active
last_updated: 2026-07-26
applicable_versions: kubectl 1.29+, Helm 3.14+
---

# Deploy REST API

Ship a new API image to production in ~10 minutes. Roll back in under 2 if health checks fail.

## Prerequisites

| Requirement | How to confirm |
|---|---|
| `deploy` role in the `api-prod` namespace | `kubectl auth can-i create deployments -n api-prod` returns `yes` |
| Image already pushed and scanned | `crane digest registry.example.com/api:$TAG` returns a digest |
| Change window open | Deploy freeze calendar shows no active freeze |

## Steps

1. Record the currently running revision, so rollback has a target.

   ```bash
   helm history api -n api-prod | tail -3
   ```

   Expected output: a table whose last row has `STATUS=deployed`. Note that revision number.

2. Apply the new image.

   ```bash
   helm upgrade api ./charts/api -n api-prod --set image.tag="$TAG" --wait --timeout 5m
   ```

   Expected output: `Release "api" has been upgraded. Happy Helming!`

3. Verify rollout and health.

   ```bash
   kubectl rollout status deploy/api -n api-prod --timeout=120s
   curl -fsS https://api.example.com/healthz
   ```

   Expected output: `deployment "api" successfully rolled out`, then `{"status":"ok"}`.

## Verification

| Check | Command | Pass condition |
|---|---|---|
| Pods ready | `kubectl get deploy/api -n api-prod` | `READY` equals desired replicas |
| Error rate | Grafana `api-slo` dashboard | 5xx rate below 0.5% for 5 minutes |
| Version served | `curl -fsS https://api.example.com/version` | returns the deployed `$TAG` |

## Rollback

Trigger: any verification check fails, or 5xx rate exceeds 1% for 2 consecutive minutes.

```bash
helm rollback api <REVISION_FROM_STEP_1> -n api-prod --wait
kubectl rollout status deploy/api -n api-prod --timeout=120s
```

Expected output: `Rollback was a success!` followed by a successful rollout. If rollback itself
fails, page the api-platform on-call and do not retry the upgrade.

## Maintenance triggers

Update this runbook when the chart path changes, when the namespace is renamed, or when the
health endpoint moves.
<!-- END DOCUMENT -->

## Quality Scorecard

Type is `task`, so applicability is taken from Gate 3's tags.

- **Critical**: 4/4 applicable pass (1 N/A — parameter tables, reference-only).
  Commands runnable ✓ · expected output on every step ✓ · metadata ✓ · terminology consistent ✓
- **Standard**: 5/5 applicable pass (1 N/A — error codes, API-reference only) → PASS (need 4/5).
- **Hygiene**: 3/3 applicable pass, 2 conditional not applicable (no diagrams; versions declared
  so `applicable_versions` counts as passing) → PASS (need 2/3).

`lint_doc.py --type task --scorecard` was used to fix the denominators rather than guessing them.

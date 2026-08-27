# Safety and Authorization for Debugging Actions

## Table of Contents

1. [Overview](#overview)
2. [Destructive or State-Changing Commands](#destructive-or-state-changing-commands)
3. [Commands That Can Leak Sensitive Data](#commands-that-can-leak-sensitive-data)
4. [P0 Mitigation Authorization](#p0-mitigation-authorization)
5. [Evidence Preservation Before Mitigating](#evidence-preservation-before-mitigating)
6. [Rollback Risk](#rollback-risk)

## Overview

Debugging often needs to run commands that observe or touch a real system — but "observe" and "touch" carry very different blast radii. A command that reveals a secret, deletes state, or restarts a production process is not a diagnostic action just because it happens during a debugging session. This reference is the safety layer `SKILL.md` points to whenever a step in the Four Phases or the P0 Protocol reaches for one of these commands.

## Destructive or State-Changing Commands

Not every state-changing command in `allowed-tools` carries the same risk. Two are excluded outright; two others (`go clean`, `mvn clean`) stay pre-approved specifically because they're low-risk in a way the excluded ones aren't — that distinction is deliberate, not an inconsistency, and it's spelled out below so it doesn't read as one.

**Excluded from `allowed-tools` — go through the normal permission-prompt flow instead:**

- `rm -rf node_modules` (or any recursive delete) — confirm the exact path before running; never run against a path derived from unvalidated input; ask before running it, don't treat "debugging a dependency issue" as blanket authorization to delete state. Excluded because the delete is not automatically recoverable (untracked local changes under the deleted path are gone) and the blast radius depends on a path you're constructing at runtime.
- `git init` — has no legitimate role in root-cause investigation. If you find yourself reaching for it, stop: you are either about to create a nested/shadow repository by accident, or you've drifted from diagnosis into unrelated setup work. Neither belongs in this skill's workflow.
- Any command that restarts, kills, or redeploys a running service outside of the explicit P0 Protocol below.

**Still pre-approved in `allowed-tools`, despite being state-changing — `go clean`, `mvn clean`:** these clear a build cache, not source or data; the worst case is a slower next build while the cache repopulates, and there is no path-injection risk (no runtime-constructed path argument). State which cache and why in the report; don't run it speculatively "just in case." If a future addition to this list can't clear that same bar (recoverable, no runtime-constructed target path, no data loss), it belongs in the excluded list above, not here.

## Commands That Can Leak Sensitive Data

`env` and `tcpdump` are **not** in `allowed-tools` either, for the same reason as the destructive commands above but a different mechanism: report-time redaction cannot undo an exposure that already happened at command-execution time. Ask before running either, and once you've asked and are running it, minimize what you capture — that's the real defense, redaction is the backup, not the primary control.

- **`env`**: dumps every environment variable, including API keys, database credentials, and tokens if the process has them. The exposure happens the moment the command runs — it lands in the tool output/transcript before you write a word of the report, so redaction *in the report* cannot undo it. That means minimizing what you dump is the real defense, not just cleaning up afterward:
  - **Default to a targeted lookup** (`env | grep '^DATABASE_HOST='`) when you know which variable you need. Reach for a full `env` dump only when you genuinely don't know which variable is relevant, and say so when asking for confirmation.
  - Whether you ran a targeted lookup or a full dump, redact any value whose key name contains (case-insensitively) `SECRET`, `KEY`, `TOKEN`, `PASSWORD`, `CREDENTIAL`, or `AUTH` before it goes into the report — this limits what a reader of the *report* sees, on top of (not instead of) minimizing the dump itself.
- **`tcpdump`**: captures raw network traffic, which can include credentials or session tokens sent in cleartext (HTTP, unencrypted protocols). When used for diagnosis:
  - Capture headers/metadata only where possible; avoid `-A`/`-X` (full payload dump) on traffic you haven't confirmed is already encrypted or non-sensitive.
  - Bound the capture with `-c <count>` or a short time window — don't leave it running unattended.
  - `tcpdump` typically needs elevated privileges; on a shared host it can capture other users' traffic — this is on top of, not instead of, asking before running it at all.
- **`curl`** against internal debug/admin endpoints: fine for diagnosis (and still pre-approved — it's read-mostly and doesn't dump broad system state the way `env`/`tcpdump` do); never forward response bodies containing secrets to an external URL, and never use `curl` to send internal data to a third-party endpoint as part of "testing."
- **Log output in general**: the same redaction rule applies to anything pasted into a debugging report, not just `env` — passwords, full JWTs, API keys, and PII do not belong in a report body even when they appeared in the raw command output.

## P0 Mitigation Authorization

The P0 Protocol in `SKILL.md` lists rollback, feature-flag disable, hotfix, and failover as mitigation options. Each is a production change with real consequences, so before executing any of them:

- **Confirm authorization.** If the request didn't come with clear authority to act on the production system (an on-call role, an explicit "please roll it back now"), say what you would do and ask, rather than assuming the severity of the incident implies blanket authorization. Time pressure is a reason to ask fast, not a reason to skip asking.
- **State which mitigation and why**, in one line, before executing it — this becomes the Triage section's "Mitigation status" field.
- **Prefer the least destructive option that actually stops the bleeding**: a feature-flag disable is usually easier to reverse than a rollback, which is usually easier to reason about than a failover. Pick the smallest blast radius that resolves the P0.

## Evidence Preservation Before Mitigating

Rollback, restart, and failover all tend to destroy the exact state Phase 1 needs (logs rotate, in-memory state resets, the failing pod is replaced). Before or during mitigation, when it costs no meaningful additional time:

- Snapshot or export the relevant logs, error traces, and metrics dashboards for the incident window.
- Note the exact timestamp and observed state at the moment of mitigation.
- If mitigation must happen immediately with zero delay (e.g., active data loss), it's acceptable to mitigate first and note in Residual Risk that evidence capture was skipped and why — this is a legitimate tradeoff, not a Reporting Integrity Gate violation, as long as it's stated honestly rather than silently omitted.

## Rollback Risk

A rollback is not risk-free just because it's the standard P0 move: it can reintroduce a bug that was fixed after the version you're rolling back to, drop schema/data migrations that ran since, or break clients that started depending on a newer contract. Before executing a rollback:

- Check what shipped between the last-known-good version and now that you'd be undoing.
- State this rollback risk in one line in the Triage section, even if the answer is "checked, nothing else shipped in that window."

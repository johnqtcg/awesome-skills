# Design: Deep Research Host-Attested Test Evidence

## 1. Context

- **Problem / Purpose**: `deep_research.py run-test -- <argv>` and
  `--replay-tests` turn an allowed research helper into an arbitrary command
  proxy. A zero exit code is also accepted without proving claim relevance or
  binding the execution snapshot to pinned code.
- **Who is affected**: Agents, operators, and reviewers who rely on codebase or
  hybrid reports as auditable evidence.
- **Success criteria**:
  - the helper never executes imported test argv;
  - the host executes a test once through its normal permission surface;
  - a receipt identifies stable finding/code coverage, test target/framework,
    repository root, commit, tree, dirty state, result, and relevance review;
  - runtime High requires relevant receipt coverage and exact snapshot binding;
  - report generation never reruns tests;
  - the ledger has a real multiprocess contention test and an explicit
    cross-platform/bypass contract.

## 2. Constraints And Compatibility

- Keep the existing standard-library-only Python implementation and
  `deep_research.py` entry point.
- Preserve Web evidence behavior and the canonical nine-section report.
- Remove the unsafe `run-test` and `--replay-tests` interfaces even though this
  is a deliberate CLI compatibility break.
- Treat imported receipts as host attestations, not cryptographic proof. The
  helper verifies their structure and repository identity but cannot prove an
  operator did not rewrite a local JSON file.
- Do not attempt to infer semantic test coverage from stdout. Require an
  explicit relevance review and stable coverage IDs.
- External `WebSearch`/`WebFetch` calls remain outside the helper process; they
  must reserve the corresponding ledger budget before execution.

## 3. Approaches Considered

The alternatives use inversion ("the research helper never owns execution")
and decomposition (host execution, receipt import, relevance verification,
snapshot verification, reporting, and budget accounting are separate).

### Option A: Keep `run-test` with an executable allowlist

- Lower migration cost.
- Still a command proxy; interpreters and build tools can execute arbitrary
  code even when their executable name is allowed.
- Does not solve relevance or snapshot identity.

### Option B: Keep execution but allow only framework-specific selectors

- Stronger than a process-name allowlist.
- Requires a growing framework parser and still bypasses host authorization.
- Cannot safely model custom test runners.

### Option C: Host execution plus imported receipt

- The host runs the test directly through normal permissions exactly once.
- The helper only reads, validates, binds, and renders the receipt.
- Framework diversity remains possible without turning the helper into a
  command broker.

| Dimension (weight) | A: Allowlist | B: Framework proxy | C: Host receipt |
|---|---:|---:|---:|
| Permission-boundary safety (0.30) | 2 (0.60) | 3 (0.90) | 5 (1.50) |
| Claim relevance (0.20) | 1 (0.20) | 3 (0.60) | 5 (1.00) |
| Snapshot integrity (0.20) | 2 (0.40) | 4 (0.80) | 5 (1.00) |
| Framework compatibility (0.10) | 3 (0.30) | 2 (0.20) | 5 (0.50) |
| Migration effort (0.10) | 4 (0.40) | 2 (0.20) | 3 (0.30) |
| Testability (0.10) | 3 (0.30) | 3 (0.30) | 5 (0.50) |
| **Weighted total** | **2.20** | **3.00** | **4.80** |

## 4. Chosen Approach

Choose Option C in Brainstorming `Deep` mode. Delete the execution and replay
paths. Introduce a versioned `host-test-receipt-v2` schema and a safe
`import-test-receipt` command that performs no process execution.

The user's instruction to move execution to the host and import a structured
receipt is explicit approval of this architecture.

## 5. Architecture / Components / Flow

### Host execution

1. Run `search-codebase` and author findings with stable finding IDs.
2. Run the relevant test directly through the host tool permission system.
3. Create a receipt from the observed result and repository identity.
4. Import it with `import-test-receipt`.

### Receipt contract

A test receipt contains:

- schema, ID, kind, origin, execution ID, argv/command;
- `covers`: the finding ID and every code evidence ID it supports;
- framework, test target, selectors, and tested repository paths;
- repository root, HEAD commit, commit tree hash, and dirty state;
- exit code, status, timestamps, bounded output summaries/hashes;
- explicit relevance review status, reviewer, rationale, and timestamp.

### Static verification

The validator:

- never executes argv;
- checks receipt shape and host origin;
- resolves the receipt commit and tree from Git;
- validates tested paths at the declared commit;
- records whether the receipt snapshot is clean;
- for runtime High, requires every pinned code item in the finding to be
  covered by a clean receipt for the same commit/tree and tested path;
- requires the receipt to cover the stable finding ID and carry an approved,
  reasoned relevance review.

Dirty, mismatched, uncovered, or unreviewed receipts remain audit context but
cannot raise runtime confidence to High.

### Single execution

`validate` and `report` may repeat pure artifact verification. Neither command
executes a test. Therefore the host test runs once, while report generation
retains the previous defense-in-depth validation guarantee.

### Ledger

- POSIX uses `fcntl`; Windows uses `msvcrt` byte-range locking. Unsupported
  platforms fail closed rather than silently running unlocked.
- A real multiprocess test races reservations against one Quick session.
- `reserve-budget` records external WebSearch/WebFetch usage before the host
  call.
- Creating a session refuses to overwrite an existing ledger.
- Documentation states that the ledger is an operational constraint, not a
  tamper-proof audit log.

## 6. Failure Handling And Operational Notes

- Legacy `run-test` and replay flags produce parser errors because the
  interfaces no longer exist.
- Missing finding IDs, incomplete `covers`, unknown frameworks, empty
  selectors, absent relevance approval, dirty snapshots, commit/tree mismatch,
  and path mismatch yield typed issues and confidence downgrade.
- Receipt import rejects duplicate IDs and repository-root mismatch.
- A failed or dirty receipt can be listed as a gap but cannot establish High.
- External-tool budget reservations are charged before the external action; a
  failed action still consumes the attempt.

## 7. Validation And Testing

- Assert no parser path accepts `run-test` or `--replay-tests`.
- Scan production code to ensure test evidence verification contains no
  non-Git process execution.
- Simulate host execution with a real committed test, create a complete
  receipt, and prove relevant same-snapshot runtime High.
- Reject a generic print receipt, missing coverage, unapproved relevance,
  dirty snapshot, commit A/test B mismatch, tree mismatch, and tested-path
  mismatch.
- Prove report generation does not execute the test again.
- Race more processes than the Quick budget and assert exactly the allowed
  number reserve successfully.
- Run regression, pytest, skill validation, compile, diff checks, and MkDocs.

## 8. Open Questions / Risks

- Receipt truth ultimately depends on the host/operator accurately recording
  an execution; local JSON is not cryptographically attested.
- Relevance approval is a controlled human/agent judgment, not a proof of
  semantic coverage.
- Cross-platform Windows locking can be unit-tested by abstraction on POSIX,
  but genuine Windows process contention requires Windows CI.
- Direct use of Web tools cannot be technically intercepted; compliance is
  enforced by skill procedure plus `reserve-budget`.

## 9. Approval And Handoff

- **Approval status**: Approved by the user's explicit receipt-import,
  snapshot-binding, single-execution, and ledger-boundary requirements.
- **Design doc status**: Saved at
  `docs/plans/2026-07-18-deep-research-host-attested-test-evidence-design.md`.
- **Next step**: `writing-plans`, followed by inline execution because
  delegation was not authorized.

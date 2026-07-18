# Design: Complete Runtime Code-Set Binding

## 1. Context

- **Problem**: Runtime confidence currently filters to pinned code before
  evaluating receipts. A finding can therefore cite both pinned and unpinned
  code yet still receive High, and separate receipts can collectively cover
  different code items even though no single execution attests to the complete
  claim.
- **Affected users**: Authors and reviewers of codebase or hybrid research who
  rely on runtime High as a same-snapshot evidence guarantee.
- **Success criteria**:
  - every cited code item participates in the runtime-High decision;
  - any unpinned code prevents runtime High;
  - one receipt covers the finding ID and every cited code ID;
  - all cited code uses one pinned commit/tree and the receipt matches it;
  - a read-only helper produces HEAD/tree/dirty metadata without executing a
    test;
  - permissions and documentation accurately describe receipt creation and
    non-preapproved frameworks.

## 2. Constraints And Trust Boundary

- Keep test execution outside `deep_research.py`; do not restore a command
  proxy.
- Keep the receipt model as host attestation. Static validation can check Git
  objects, schema, paths, framework shape, and declared binding, but cannot
  independently prove historical execution or semantic coverage.
- Preserve standard-library-only Python and the existing artifact formats.
- Add no broad direct permissions for Cargo, npm, Maven, Gradle, or .NET.
  Their receipt schemas remain supported, while execution requires normal host
  authorization.

## 3. Approaches Considered

### Option A: Continue filtering to pinned code

- Smallest implementation.
- Silently ignores evidence that materially contributes to the finding.
- Fails the documented complete-coverage contract.

### Option B: Accept multiple receipts that collectively cover the code set

- Supports split test suites.
- Does not prove that one observed execution supports the complete runtime
  claim and permits cross-snapshot composition.

### Option C: Validate the complete cited-code set against one receipt

- Rejects unpinned and mixed-snapshot code before receipt matching.
- Requires one reviewed, clean receipt to cover the finding and all code IDs,
  name all code paths, and match the shared commit/tree.
- Adds a separate read-only snapshot helper for receipt authors without
  crossing the execution boundary.

## 4. Decision

Choose Option C in Brainstorming `Compact` mode. The user's four explicit
runtime requirements and snapshot-helper suggestion approve this targeted
contract refinement.

## 5. Flow

1. Collect every verified code item referenced by the finding.
2. Reject runtime High if any item is unpinned.
3. Reject runtime High unless every code item has an ID and all commits are
   identical.
4. Build one required coverage set: the finding ID plus every code ID.
5. Accept only a single verified receipt whose `covers` contains that entire
   set, whose clean HEAD/tree matches the common code snapshot, and whose
   tested paths contain every cited code path.
6. Otherwise retain usable evidence but downgrade High with explicit reasons.

`snapshot-codebase --root <repo> --output <json>` only reads Git metadata and
writes a versioned snapshot artifact containing repository root, HEAD commit,
tree hash, dirty state, and generation time. It never executes receipt argv or
claims that a test ran.

## 6. Failure Handling

- Unpinned code: downgrade with the specific evidence IDs.
- Multiple code commits: downgrade as a mixed commit/tree set.
- Incomplete single-receipt coverage: list missing finding/code IDs.
- Missing tested paths or snapshot mismatch: keep existing explicit downgrade
  reasons.
- Non-repository or unborn HEAD: `snapshot-codebase` exits nonzero and does
  not fabricate metadata.

## 7. Validation

- Reproduce the exact pinned + unpinned counterexample.
- Prove two individually valid receipts cannot be combined to establish High.
- Prove mixed pinned commits cannot establish High.
- Prove clean and dirty snapshot artifacts report the current repository
  identity without changing it.
- Run the full regression, skill validation, compile, diff, and documentation
  checks.

## 8. Residual Risks

- A writable JSON receipt remains an attestation, not cryptographic proof.
- `dirty: false`, output hashes, timestamps, relevance rationale, and actual
  command coverage still depend on a trustworthy host integration.
- A future unforgeable host execution handle could strengthen the model
  without changing the complete-code-set rule.


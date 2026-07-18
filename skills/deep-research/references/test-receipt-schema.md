# Host Test Receipt Contract

Load this reference only when a finding claims runtime repository behavior.

## Trust Boundary

`deep_research.py` is a research helper, not a command runner. It never
executes `argv` from a receipt. Run one focused test through the host's normal
permission mechanism, capture its result, create the receipt, and import it
with `import-test-receipt`.

A receipt is host attestation, not cryptographic remote attestation. Static
validation proves that its Git objects and named paths exist and that its
fields are internally well formed. It cannot independently prove that the
test ran, that captured hashes came from that run, that the declared dirty
state was historically true, that tested paths were exercised, or that the
relevance rationale is correct. The host remains responsible for truthful
execution metadata and relevance review. A future unforgeable host execution
handle may strengthen this boundary.

## Versioned Schema

Use `schema: deep-research/host-test-receipt-v2`.

```json
{
  "schema": "deep-research/host-test-receipt-v2",
  "id": "test-auth-valid-token",
  "kind": "test",
  "origin": "host-tool",
  "execution_id": "<64 lowercase hexadecimal characters>",
  "argv": ["go", "test", "-run", "TestVerifyToken", "./auth"],
  "command": "go test -run TestVerifyToken ./auth",
  "framework": "go-test",
  "test_target": "TestVerifyToken",
  "selectors": ["TestVerifyToken"],
  "tested_paths": ["auth/token.go", "auth/token_test.go"],
  "covers": ["finding-auth-runtime", "code-3"],
  "repository": {
    "root": "/absolute/path/to/repository",
    "head_commit": "<existing commit object ID>",
    "tree_hash": "<tree object ID for head_commit>",
    "dirty": false
  },
  "started_at": "2026-07-18T00:00:00+00:00",
  "finished_at": "2026-07-18T00:00:01+00:00",
  "duration_seconds": 1.0,
  "exit_code": 0,
  "status": "passed",
  "summary": "ok example/auth",
  "stdout_summary": "ok example/auth",
  "stderr_summary": "",
  "stdout_sha256": "<SHA-256 of complete stdout>",
  "stderr_sha256": "<SHA-256 of complete stderr>",
  "relevance_review": {
    "status": "approved",
    "reviewer": "agent-or-human-identity",
    "rationale": "The selected test calls VerifyToken and asserts the behavior stated by finding-auth-runtime.",
    "reviewed_at": "2026-07-18T00:00:02+00:00"
  }
}
```

Supported framework values are `go-test`, `pytest`, `unittest`, `cargo-test`,
`npm-test`, `maven-surefire`, `gradle-test`, and `dotnet-test`.

The skill directly pre-approves only Go, pytest, and unittest commands. Cargo,
npm, Maven, Gradle, and .NET execution must use the host's normal authorization
path before creating a receipt. Schema support is not command permission.

`tested_paths` must name committed files, not only a package or directory.
`covers` must include the stable finding ID and every code evidence ID used by
that runtime finding. Every cited code item must be pinned to the same
commit/tree. Keep stdout/stderr summaries bounded; hashes identify the complete
captured streams.

## Static Import Checks

`import-test-receipt`, `validate`, and `report` perform read-only checks:

1. schema, origin, IDs, framework, target, selector, result, hashes, and review;
2. receipt repository root equals the code-evidence root;
3. `head_commit` exists and `tree_hash` equals `<commit>^{tree}`;
4. every `tested_paths` file exists in that commit;
5. `status` and `exit_code` agree.

They never run or replay the recorded command.

## Runtime High Eligibility

A valid receipt supports `runtime_behavior: High` only when all are true:

- the test passed;
- the finding has a stable `id`;
- every cited code evidence item is pinned;
- all cited code evidence uses one commit/tree;
- one receipt's `covers` contains that finding ID and every cited code evidence ID;
- each cited code path appears in `tested_paths`;
- the receipt and code use the same commit/tree;
- `repository.dirty` is false;
- relevance review is `approved` with reviewer, rationale, and timestamp.

Failure of any eligibility condition downgrades the finding to Medium when
other verified code support remains. A malformed or forged Git identity makes
the receipt unusable.

## Single-Execution Workflow

1. Run `snapshot-codebase --root <repo> --output <outside-repo.json>` to record
   repository root, `HEAD`, `HEAD^{tree}`, dirty state, and generation time.
2. Run one focused host test with its explicit framework selector.
3. Run `snapshot-codebase` again and require the before/after identity to be
   unchanged and clean for High.
4. Capture exit code, timestamps, bounded summaries, and full-output hashes.
5. Review how the test supports the named finding and complete code-ID set.
6. Write and import the receipt once.
7. Run `validate`, then `report`; both consume the receipt statically.

`snapshot-codebase` is a read-only identity helper, not an execution receipt.
It never runs test argv and cannot attest the historical truth of host-created
execution fields.

Do not run a generic success command such as `python -c "print('ok')"` as
evidence. It lacks a repository test target and semantic relationship to the
claim.

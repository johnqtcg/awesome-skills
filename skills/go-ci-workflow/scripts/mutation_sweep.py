#!/usr/bin/env python3
"""Mutation sweep for the go-ci-workflow skill.

Each mutation breaks one behaviour on purpose. The test suite must then FAIL --
that is a KILL. A mutation the suite still passes is a SURVIVOR, meaning no
assertion actually depends on the behaviour it broke.

Three failure modes this script is built to avoid:

1. **Stale anchors.** If a mutation's anchor text no longer exists in the file,
   the substitution is a silent no-op and the mutation "survives" for a reason
   that has nothing to do with test coverage. Every anchor is verified to exist
   (and its occurrence count recorded) before the sweep runs; a missing anchor is
   a hard error, never a survivor.
2. **Partial replacement.** Substitutions replace ALL occurrences. Replacing only
   the first can leave a working copy of the mutated text behind, which makes a
   genuine assertion look vacuous.
3. **A truncated run read as a finished one.** The sweep prints exactly one
   `SWEEP-COMPLETE killed=N survived=M total=T` line, as its last line, and only
   after every mutation has been applied and restored. Output without that line
   is not a result.

Two mutations are registered with `expected="SURVIVE"`. They invert prose
guarantees in SKILL.md that nothing machine-checkable binds, and they are here so
the report distinguishes a known, accepted gap from a regression. Do not "fix"
them with a phrase matcher: a substring assertion on prose is satisfied by any
sentence that happens to contain the words, which is how an inverted fork guard
once stayed green (see test_golden_yaml.py::FORK_GUARD_RE).

Exit status:
    0  every mutation's outcome matched its `expected` value
    1  at least one outcome differed from `expected`, or a run errored/timed out
    2  the sweep refused to start (dirty tree, stale anchor, failing baseline)

Usage:
    mutation_sweep.py                # run the sweep
    mutation_sweep.py --verify       # only check anchors resolve, do not run tests
    mutation_sweep.py --list         # print the mutation registry
    mutation_sweep.py --allow-dirty  # sweep although the worktree has local edits
"""

from __future__ import annotations

import argparse
import atexit
import dataclasses
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
SKILL_DIR = SCRIPTS_DIR.parent
TESTS_DIR = SCRIPTS_DIR / "tests"
REF_DIR = SKILL_DIR / "references"

SKILL_MD = SKILL_DIR / "SKILL.md"
RUNNER = SCRIPTS_DIR / "run_regression.sh"
TEST_GOLDEN_YAML = TESTS_DIR / "test_golden_yaml.py"
DISCOVER = SCRIPTS_DIR / "discover_ci_needs.sh"

GOLDEN_EXAMPLES = REF_DIR / "golden-examples.md"
ADVANCED = REF_DIR / "github-actions-advanced-patterns.md"
SHAPES = REF_DIR / "repository-shapes.md"
GUIDE = REF_DIR / "workflow-quality-guide.md"

# Every reference doc. Used by the action-pin mutation, which must sweep the
# whole corpus: pinning drift is a corpus-wide property, and mutating one file
# would leave the other twenty-odd copies correct.
ALL_REFS: tuple[pathlib.Path, ...] = tuple(sorted(REF_DIR.glob("*.md")))

KILL = "KILL"
SURVIVE = "SURVIVE"


@dataclasses.dataclass(frozen=True)
class Mutation:
    mid: str
    targets: tuple[pathlib.Path, ...]
    anchor: str
    replacement: str
    breaks: str            # the real defect class this reproduces
    expected: str = KILL   # KILL, or SURVIVE for a documented, accepted gap
    min_occurrences: int = 1  # floor across all targets; guards against the
                              # anchor eroding to a single vestigial copy


def one(path: pathlib.Path) -> tuple[pathlib.Path, ...]:
    return (path,)


MUTATIONS: tuple[Mutation, ...] = (
    # ---- structural / YAML: the suite's strong domain -------------------------
    Mutation("runs_on_removed", one(GOLDEN_EXAMPLES),
             "    runs-on: ubuntu-latest\n",
             "",
             "a job ships with no runs-on — GitHub rejects the workflow outright"),
    Mutation("timeout_removed", one(GOLDEN_EXAMPLES),
             "    timeout-minutes: 15\n",
             "",
             "a job ships with no timeout-minutes, so a hung step burns the "
             "6-hour default"),
    Mutation("contents_write", one(GOLDEN_EXAMPLES),
             "  contents: read",
             "  contents: write",
             "a copyable CI example grants the GITHUB_TOKEN push access to the repo"),
    Mutation("stale_action_major", ALL_REFS,
             "actions/checkout@v7",
             "actions/checkout@v5",
             "every example pins an action major two releases behind the §16 policy "
             "table",
             min_occurrences=15),
    Mutation("stale_tool_pin", one(GOLDEN_EXAMPLES),
             "golangci-lint@v2.13.2",
             "golangci-lint@v2.6.2",
             "an example installs a tool version the §11 pin table does not declare"),
    Mutation("fork_guard_inverted", one(GOLDEN_EXAMPLES),
             "github.event.pull_request.head.repo.full_name == github.repository",
             "github.event.pull_request.head.repo.full_name != github.repository",
             "the fork guard runs the secret-bearing job for forks ONLY — the exact "
             "inversion a whole-file substring assertion cannot see"),
    Mutation("cancel_in_progress_inverted", one(ADVANCED),
             "cancel-in-progress: ${{ github.event_name == 'pull_request' }}",
             "cancel-in-progress: ${{ github.event_name != 'pull_request' }}",
             "concurrency cancels merged-commit runs on main and never cancels PR "
             "runs"),
    Mutation("cancel_in_progress_true", one(ADVANCED),
             "cancel-in-progress: ${{ github.event_name == 'pull_request' }}",
             "cancel-in-progress: true",
             "the event gate is dropped, so a push to main cancels the run that is "
             "validating the previous commit"),
    Mutation("permissions_block_deleted", one(GOLDEN_EXAMPLES),
             "\npermissions:\n  contents: read\n",
             "\n",
             "a complete workflow ships with no permissions block, inheriting the "
             "repository default token scope"),

    # ---- newly guarded by the 2026-09-17 hardening ---------------------------
    # These are the regression tests for the fixes made in that session: each
    # reverts one fix and must go red.
    Mutation("jobmap_filter_self_exempting", one(TEST_GOLDEN_YAML),
             '("steps" in v or "uses" in v)',
             '"runs-on" in v',
             "the jobmap discovery filter requires the very field its callers "
             "assert on, so a job missing runs-on is exempted from the runs-on rule"),
    Mutation("go_matrix_stale", one(SHAPES),
             "go-version: ['1.26', '1.27']",
             "go-version: ['1.22', '1.23']",
             "a Go matrix literal drifts off the §13 supported-majors row"),
    Mutation("go_policy_eol", one(GUIDE),
             "| `go` | `1.26`, `1.27` | 2026-09-17 |",
             "| `go` | `1.22`, `1.23` | 2026-09-17 |",
             "the §13 policy row itself declares end-of-life Go majors"),
    Mutation("timeout_table_drift", one(ADVANCED),
             "| E2E tests | 30 min |",
             "| E2E tests | 15 min |",
             "the §8 timeout table contradicts the always-loaded prose that quotes it"),
    Mutation("shape_taxonomy_drift", one(SHAPES),
             "## 1) Single-Module Application",
             "## 1) Single-Module Service",
             "repository-shapes.md names a shape the Repository Shape Gate never "
             "produces, so Gate 1's vocabulary has no section behind it"),
    Mutation("runner_test_step_backdoor", one(RUNNER),
             'python3 -m unittest discover -s "${SKILL_DIR}/scripts/tests" '
             '-p "test_*.py" -v 2>&1 | tee "${test_log}"',
             '[ -n "${SKIP_TESTS:-}" ] || '
             'python3 -m unittest discover -s "${SKILL_DIR}/scripts/tests" '
             '-p "test_*.py" -v 2>&1 | tee "${test_log}"',
             "an env-var backdoor lets the runner reach its success banner without "
             "executing a single test"),
    Mutation("runner_min_tests_removed", one(RUNNER),
             "MIN_TESTS=100",
             "MIN_TESTS=0",
             "the discovery-collapse floor is removed, so `Ran 0 tests` with rc=0 "
             "reads as a pass"),
    Mutation("runner_skip_ceiling_removed", one(RUNNER),
             "(( skipped > expected_skips ))",
             "(( skipped > 9999 ))",
             "the skip ceiling never fires, so a silently skipped validation layer "
             "reports success"),
    Mutation("setup_go_cache_claim_reverted", one(GUIDE),
             "hashes **`go.mod`** — not `go.sum`",
             "hashes **`go.sum`**",
             "§3 returns to the false claim that setup-go's default cache key "
             "hashes go.sum"),
    Mutation("self_hosted_section_gutted", one(ADVANCED),
             "**Rule zero: a self-hosted runner must almost never serve a public "
             "repository.** A self-hosted runner has no guarantee of running in an "
             "ephemeral clean VM and can be *persistently* compromised by untrusted "
             "code in a workflow — and on a public repo **any** user can open a pull "
             "request to run that code on your machine. If a public repo needs "
             "self-hosted capacity, put the work behind an approval-gated build "
             "service, not behind a runner label.\n\n",
             "",
             "§6 loses the rule that a self-hosted runner must not serve a public "
             "repository — the one trust-boundary claim that decides the whole "
             "section"),

    # ---- known-survivor baseline ---------------------------------------------
    # Prose semantic inversions. The suite deliberately does not guard these: the
    # only cheap guard is a substring match on the sentence, which any rewrite
    # satisfies and which would therefore assert nothing while reading green.
    # They are registered so the report can distinguish an accepted gap from a
    # regression -- an unexplained survivor and a documented one look identical
    # in a bare killed/survived count.
    # ---- discovery probe: silent-corruption paths (2026-09-17) ---------------
    Mutation("probe_xargs_apostrophe", one(DISCOVER),
             "  -exec grep -h -oE '(golangci-lint|swag|goimports-reviser|govulncheck|"
             "fieldalignment|protoc|mockgen|wire|gosec|nilaway)' {} + 2>>\"$ERRLOG\" \\\n",
             "  2>>\"$ERRLOG\" | xargs grep -h -oE '(golangci-lint|swag|goimports-reviser|"
             "govulncheck|fieldalignment|protoc|mockgen|wire|gosec|nilaway)' 2>>\"$ERRLOG\" \\\n",
             "the tool probe returns to a NEWLINE-delimited xargs pipeline; BSD "
             "xargs reads an apostrophe as a quote character, so one such path "
             "anywhere aborts the whole probe with exit 0 and no rows. Note "
             "`xargs -0` would NOT reproduce this — the defect is the delimiter"),
    Mutation("probe_stderr_discarded", one(DISCOVER),
             '2>>"$ERRLOG"',
             "2>/dev/null",
             "probes discard stderr again, so permission-denied is "
             "indistinguishable from absent and the shape verdict silently "
             "inverts",
             min_occurrences=8),
    Mutation("probe_completion_marker_removed", one(DISCOVER),
             'printf "meta\\tprobe-complete\\tok\\n"\n',
             "",
             "a truncated run becomes indistinguishable from a complete one"),
    Mutation("probe_empty_arg_scans_cwd", one(DISCOVER),
             'root="${1-.}"',
             'root="${1:-.}"',
             "an empty argument is treated as unset, producing a full plausible "
             "report of the current directory instead of the intended repo"),
    Mutation("probe_prune_second_copy", one(DISCOVER),
             'PRUNE_RE="/(${_alt})/"',
             'PRUNE_RE="/(vendor|node_modules|testdata|third_party)/"',
             "the package-main probe regains a hand-written prune list that "
             "omits .git, so a blob under .git/ is cited as the entrypoint"),
    Mutation("probe_undetermined_downgraded", one(DISCOVER),
             'printf "shape\\tundetermined\\tpackage-main scan incomplete (unreadable paths)\\n"',
             'printf "shape\\tlikely-library-or-unknown\\tno package main found\\n"',
             "an incomplete scan asserts a confident library verdict instead of "
             "declaring the case undecidable"),

    # ---- safety-critical prose, now bound to section-scoped guards ----------
    Mutation("permissions_replacement_inverted", one(ADVANCED),
             "It replaces the default token grant, it does not add to it.",
             "It leaves them at default; it adds to the grant, it does not replace it.",
             "§1 inverts the permissions replacement rule; readers then write "
             "under-scoped blocks and get 403s from checkout"),
    Mutation("secret_gate_causal_model_reverted", one(GUIDE),
             "**The rule GitHub already enforces, stated plainly:**",
             "Gate secret-dependent jobs with `if: github.event_name != 'pull_request'` "
             "to prevent exposure on fork PRs. Rest:",
             "§12 returns to teaching that the event check prevents a fork leak, "
             "which GitHub already prevents, while over-firing on same-repo PRs"),

    Mutation("prose_parity_gate_inverted", one(SKILL_MD),
             "Do not claim local parity unless",
             "Claim local parity whenever",
             "the Local Parity Gate inverts: parity may be asserted without a "
             "local entrypoint behind each job",
             expected=SURVIVE),
    Mutation("prose_integrity_gate_inverted", one(SKILL_MD),
             "Never claim validation happened unless it actually ran",
             "Claim validation happened whenever the workflow YAML looks correct",
             "the Execution Integrity Gate inverts: validation may be reported "
             "without having been executed",
             expected=SURVIVE),
)


# The sweep mutates source files. Doing that in the real worktree makes every other
# reader of the tree -- a concurrent regression run, an editor, a second sweep --
# observe deliberately broken files, and two sweeps overlapping corrupt each other's
# restore. So the whole sweep runs against a private copy and the real tree is never
# written to.
_SANDBOX: pathlib.Path | None = None


def sandbox_root() -> pathlib.Path:
    """Return (creating on first use) a private copy of the skill directory."""
    global _SANDBOX
    if _SANDBOX is None:
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="gociw-sweep-",
                                            dir=os.environ.get("TMPDIR") or None))
        dest = tmp / SKILL_DIR.name
        shutil.copytree(SKILL_DIR, dest, ignore=shutil.ignore_patterns(
            "__pycache__", ".pytest_cache", ".git", "*.pyc"))
        # copytree preserves mode, so a read-only source file would make the sandbox
        # unwritable and the sweep would fail on the copy for a reason that has nothing
        # to do with the mutation. The sandbox is meant to be mutable; the original is
        # the thing being protected.
        for f in dest.rglob("*"):
            if f.is_file():
                f.chmod(f.stat().st_mode | stat.S_IWUSR)
        atexit.register(shutil.rmtree, tmp, True)
        _SANDBOX = dest
    return _SANDBOX


def sandboxed(target: pathlib.Path) -> pathlib.Path:
    """Map a real path to its counterpart inside the sandbox copy."""
    return sandbox_root() / target.relative_to(SKILL_DIR)


def run_tests(timeout: int = 300) -> str:
    """Run the suite inside the sandbox copy. Returns PASS, FAIL or ERROR.

    The command is the one `run_regression.sh` uses, so a kill here is a kill in
    the real gate. `test_skill_contract.py` shells out to the sandbox's own
    `run_regression.sh` (with an injected validator, so there is no recursion);
    that is intended, and it is why the timeout is generous.

    ERROR (a timeout) is reported separately and never collapses into SURVIVED:
    "the suite did not finish" and "the suite passed" are different facts, and
    treating the first as the second is how a hung run reads as coverage.
    """
    root = sandbox_root()
    env = dict(os.environ)
    # Never leave .pyc behind in the sandbox: a mutated test module and its stale
    # bytecode differ, and any import that resolved to the cached copy would make
    # the mutation vanish without a trace.
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "discover",
             "-s", str(root / "scripts" / "tests"), "-p", "test_*.py"],
            cwd=str(root), capture_output=True, text=True,
            timeout=timeout, env=env,
        )
    except subprocess.TimeoutExpired:
        return "ERROR"
    return "PASS" if proc.returncode == 0 else "FAIL"


def verify_anchors() -> list[str]:
    """Every anchor must exist. A stale anchor is an error, never a survivor."""
    problems = []
    for m in MUTATIONS:
        total = 0
        for target in m.targets:
            if not target.exists():
                problems.append(f"{m.mid}: target missing: {target}")
                continue
            total += target.read_text(encoding="utf-8").count(m.anchor)
        if total < m.min_occurrences:
            problems.append(
                f"{m.mid}: anchor found {total}x across {len(m.targets)} target(s), "
                f"floor is {m.min_occurrences} — the mutation would be a silent "
                f"no-op or would no longer bite. Anchor: {m.anchor[:80]!r}"
            )
    return problems


def anchor_counts() -> list[tuple[str, int, int]]:
    """(mid, occurrences, files hit) — printed by --verify so erosion is visible."""
    out = []
    for m in MUTATIONS:
        total = files = 0
        for target in m.targets:
            if not target.exists():
                continue
            n = target.read_text(encoding="utf-8").count(m.anchor)
            total += n
            files += 1 if n else 0
        out.append((m.mid, total, files))
    return out


def worktree_status() -> tuple[list[str], str | None]:
    """Porcelain entries under the skill dir.

    Returns (entries, error). A non-empty `entries` or a non-None `error` both
    mean the sandbox copy may not match what is committed — the sweep then
    refuses unless --allow-dirty. Undecidable is treated as dirty on purpose:
    guessing "probably clean" is the fail-open answer.
    """
    try:
        top = subprocess.run(["git", "-C", str(SKILL_DIR), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=30)
        if top.returncode != 0:
            return [], f"git rev-parse failed: {top.stderr.strip()}"
        root = pathlib.Path(top.stdout.strip())
        rel = SKILL_DIR.relative_to(root)
        # -z + core.quotePath=false: porcelain paths are otherwise a display form
        # (quoted, escaped) rather than the bytes on disk.
        proc = subprocess.run(
            ["git", "-c", "core.quotePath=false", "-C", str(root),
             "status", "--porcelain", "-z", "--", str(rel)],
            capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            return [], f"git status failed: {proc.stderr.strip()}"
        return [e for e in proc.stdout.split("\0") if e], None
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return [], f"{type(exc).__name__}: {exc}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verify", action="store_true",
                    help="only check that anchors resolve; do not run the sweep")
    ap.add_argument("--list", action="store_true", help="print the mutation registry")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="sweep although the worktree has uncommitted changes under "
                         "the skill directory")
    args = ap.parse_args(argv)

    if args.list:
        print(f"{'id':<32} {'expected':<9} {'targets':<8} description")
        for m in MUTATIONS:
            names = (m.targets[0].name if len(m.targets) == 1
                     else f"{len(m.targets)} refs")
            print(f"{m.mid:<32} {m.expected:<9} {names:<8} {m.breaks}")
        return 0

    entries, git_error = worktree_status()
    dirty = bool(entries) or git_error is not None
    if dirty and args.verify:
        # --verify runs no tests and produces no kill/survive verdict, so there is
        # nothing to misattribute to HEAD. Say the tree is dirty and carry on:
        # anchors are checked against the files in front of you either way.
        print(f"NOTE: worktree is not clean ({len(entries)} changed path(s)"
              f"{'; git status unavailable' if git_error else ''}); anchors below "
              "are checked against the WORKING TREE.", file=sys.stderr)
    elif dirty and not args.allow_dirty:
        print("REFUSING TO SWEEP — the worktree under skills/go-ci-workflow is not "
              "clean.", file=sys.stderr)
        print("The sweep copies the WORKING TREE, so a dirty tree means the sandbox "
              "does not\nmatch what is committed and a kill/survive verdict cannot "
              "be attributed to HEAD.", file=sys.stderr)
        if git_error:
            print(f"  could not determine status: {git_error}", file=sys.stderr)
        for e in entries:
            print(f"  {e}", file=sys.stderr)
        print("\nCommit or stash the changes, or re-run with --allow-dirty to sweep "
              "the working tree as it stands.", file=sys.stderr)
        return 2
    if dirty and not args.verify:
        print(f"--allow-dirty: sweeping the WORKING TREE, not HEAD "
              f"({len(entries)} changed path(s)"
              f"{'; git status unavailable' if git_error else ''})")

    problems = verify_anchors()
    if problems:
        print("ANCHOR VERIFICATION FAILED — refusing to run the sweep:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        print("\nFix the anchors (the source has changed) and re-run.", file=sys.stderr)
        return 2
    print(f"anchors OK ({len(MUTATIONS)} mutations)")
    if args.verify:
        for mid, total, files in anchor_counts():
            print(f"  {mid:<32} {total:>3} occurrence(s) in {files} file(s)")
        return 0

    print("baseline: running suite unmutated...")
    baseline = run_tests()
    if baseline != "PASS":
        print(f"BASELINE {baseline} — fix the suite before sweeping.", file=sys.stderr)
        return 2
    print("baseline PASSES\n")

    print(f"sweeping in a private copy at {sandbox_root()}\n")
    results: list[tuple[Mutation, str]] = []
    for m in MUTATIONS:
        originals = {t: sandboxed(t).read_text(encoding="utf-8") for t in m.targets}
        changed = 0
        try:
            for target, original in originals.items():
                # Replace ALL occurrences: a partial replacement can leave a working
                # copy of the mutated text behind, which makes a genuine assertion
                # look vacuous.
                mutated = original.replace(m.anchor, m.replacement)
                if mutated != original:
                    sandboxed(target).write_text(mutated, encoding="utf-8")
                    changed += 1
            assert changed, f"{m.mid}: replacement produced no change in any target"
            outcome = run_tests()
        finally:
            for target, original in originals.items():
                sandboxed(target).write_text(original, encoding="utf-8")

        actual = {"PASS": "SURVIVED", "FAIL": "KILLED", "ERROR": "ERROR"}[outcome]
        results.append((m, actual))
        want = "KILLED" if m.expected == KILL else "SURVIVED"
        verdict = "PASS" if actual == want else "REGRESSION"
        print(f"  {verdict:<10} {m.mid:<32} expected={m.expected:<8} actual={actual}")

    killed = [m for m, a in results if a == "KILLED"]
    survived = [m for m, a in results if a == "SURVIVED"]
    errored = [m for m, a in results if a == "ERROR"]
    mismatches = [(m, a) for m, a in results
                  if a != ("KILLED" if m.expected == KILL else "SURVIVED")]

    print("\n" + "-" * 78)
    print(f"{'id':<32} {'expected':<9} {'actual':<9} verdict")
    print("-" * 78)
    for m, actual in results:
        want = "KILLED" if m.expected == KILL else "SURVIVED"
        verdict = "PASS" if actual == want else "REGRESSION"
        print(f"{m.mid:<32} {m.expected:<9} {actual:<9} {verdict}")
    print("-" * 78)
    print(f"{len(killed)}/{len(MUTATIONS)} killed, {len(survived)} survived, "
          f"{len(errored)} errored")

    if mismatches:
        print("\nOutcomes that differed from expectation:")
        for m, actual in mismatches:
            print(f"  {m.mid} (expected {m.expected}, got {actual})")
            print(f"    {m.breaks}")
            print(f"    targets: {', '.join(t.name for t in m.targets)}")
    else:
        print("\nEvery mutation matched its expected outcome.")

    # The completion marker. Printed once, last, and only after every mutation has
    # run and been restored: output that stops short of this line is a truncated
    # run, never a result.
    print(f"SWEEP-COMPLETE killed={len(killed)} survived={len(survived)} "
          f"total={len(MUTATIONS)}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())

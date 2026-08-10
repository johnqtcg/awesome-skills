#!/usr/bin/env python3
"""Mutation sweep: prove each gate actually catches the defect it claims to.

A green linter proves nothing on its own -- a rule can be dead, mis-scoped, or
masked by the anti-example exemption and still report "clean". Each mutation
below reintroduces a real defect (most of them defects that actually shipped in
this skill) into the real documents and asserts that some gate rejects it.

SURVIVED means the gate is decorative. Fix the gate, not the mutation.

Usage:
  mutation_sweep.py            run every mutation
  mutation_sweep.py --verify   anchors-only; no gate runs (fast CI pre-check)

Exit: 0 all killed · 1 a mutation survived or an anchor is stale · 3 gate unusable
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL_DIR / "scripts"

GO_GATE = [sys.executable, str(SCRIPTS / "check_go_snippets.py")]
LINT_GATE = [sys.executable, str(SCRIPTS / "lint_cache_docs.py")]
PYTEST_GATE = [sys.executable, "-m", "pytest", str(SCRIPTS / "tests"), "-q", "-x"]

ALL_DOCS = "*"  # apply the mutation to every doc that contains the anchor

# Lint rules that no mutation exercises. `RULES - covered` is derived and
# asserted below: without it, "12/12 killed" reads as full coverage even when a
# newly added rule has no mutation at all, because the denominator is the
# mutation list rather than the rule list.
RULES_WITHOUT_A_MUTATION: set[str] = set()

# (id, file(s), anchor, replacement, expected killer, lint rules exercised)
MUTATIONS: list[tuple[str, str, str, str, str, tuple[str, ...]]] = [
    # --- the defects the 2026-08-08 review found ---
    ("M01", "references/cache-failure-modes.md",
     "    replica := rrCounter.Add(1) % shardCount",
     "    replica := crc32.ChecksumIEEE([]byte(logical)) % shardCount",
     "lint", ("RC001",)),
    ("M02", "references/cache-failure-modes.md",
     "    c, err := ristretto.NewCache(&ristretto.Config{",
     "    c := ristretto.NewCache(&ristretto.Config{",
     "go", ()),
    ("M03", "references/cache-patterns.md",
     "    case errors.Is(err, redis.Nil):",
     "    case err == redis.Nil:",
     "lint", ("RC003",)),
    ("M04", "references/cache-patterns.md",
     "### Cache-write failure semantics (mandatory to state)",
     "### Cache-write notes (optional)",
     "lint", ("RC006",)),
    ("M05", "SKILL.md",
     "| **Data source type** | SQL DB / NoSQL / external API — affects consistency patterns | **Blocking — cannot be assumed** |",
     "| **Data source type** | SQL DB / NoSQL / external API — affects consistency patterns | Assume SQL |",
     "lint", ("RC009",)),

    # --- regression guards on the fixes themselves ---
    ("M06", "references/cache-failure-modes.md",
     "    span := int64(base) / 5\n    if span <= 0 {\n        return base\n    }",
     "    span := int64(base.Seconds() * 0.2)",
     "lint", ("RC005",)),
    ("M07", "references/cache-failure-modes.md",
     "        if b, ok := v.([]byte); ok {\n            return b, nil\n        }",
     "        return v.([]byte), nil",
     "lint", ("RC002",)),
    ("M08", "SKILL.md",
     "   - **TTL**: per-field expiry needs `HEXPIRE`, which is **Redis 7.4+**.",
     "   - **TTL**: per-field expiry is available.",
     "lint", ("RC007", "RC015")),
    ("M10", "references/cache-failure-modes.md",
     "    if _, err := pipe.Exec(ctx); err != nil {\n        // Partial failure is a real failure: some replicas now serve old data.\n        return fmt.Errorf(\"fan-out write %s: %w\", logical, err)\n    }\n    return nil",
     "    pipe.Exec(ctx)\n    return nil",
     "lint", ("RC004",)),

    # --- the defect that survived the first sweep: the same hash-sharding bug
    # --- had been fixed in the reference but left standing in SKILL.md prose.
    ("M11", "SKILL.md",
     "Defense:\nL1 in-process cache, replica fan-out, or read replicas.",
     "Defense:\nlocal cache, key sharding (`key:{hash%N}`), or read replicas.",
     "lint", ("RC011",)),
    # RC007 was guarded on the phrase "large value"; the section was reworded and
    # the rule silently stopped running while still passing its selftest. This
    # mutation reproduces that failure mode: strip the bullet the gate reads.
    ("M12", "SKILL.md",
     "   - **Memory**: a Hash is only more compact while it stays under **both** `hash-max-listpack-entries`",
     "   - **Memory**: a Hash is usually more compact. Ignore `hash-max-entries`",
     "lint", ("RC007",)),

    # --- the 2026-08-10 review: the scorecard could not act on what §5 found ---
    # M13/M14 reproduce the two ways §5 and §8 drift apart. Before the merge,
    # both states were reachable and neither was detectable.
    ("M13", "SKILL.md",
     "| **Critical** | `C1–C9` |",
     "| **Critical** | `C1–C5` |",
     "lint", ("RC010",)),
    ("M14", "SKILL.md",
     "**C9 — Correctness locks are enforced where the data lives.**",
     "**C11 — Correctness locks are enforced where the data lives.**",
     "lint", ("RC010",)),
    # The exact pre-fix state: a cross-tenant leak graded as a naming nit.
    # Only the fixture changes; the gate that must object is the reachability
    # invariant, not a text rule.
    ("M15", "scripts/tests/golden/014_cross_tenant_leak.json",
     '"scorecard_items": [\n    "C7"\n  ]',
     '"scorecard_items": [\n    "H1"\n  ]',
     "pytest", ()),
    ("M16", "SKILL.md",
     "| **NOT SCOREABLE** |",
     "| **UNKNOWN** |",
     "lint", ("RC014",)),
    # This one survived RC014's first implementation. The rule searched §5 for
    # the word "WARN"; C6's prose contains "is a FAIL, not a WARN", so renaming
    # the table row that DEFINES the verdict left the rule green. Kept as a
    # standing mutation because the defect was in the guard, not the doc.
    ("M25", "SKILL.md",
     "| **WARN** |",
     "| **MEH** |",
     "lint", ("RC014",)),
    ("M17", "SKILL.md",
     "**Silence is FAIL, not N/A.**",
     "**Use your judgement.**",
     "lint", ("RC014",)),
    # Version staleness: the headline finding of the 2026-08-10 review. Strip the
    # qualifier and the claim silently becomes false on every server below 8.6.
    ("M18", "SKILL.md",
     "`redis-cli --hotkeys` (4.0+, LFU mode) or the server-side `HOTKEYS` command\n(8.6+, top-K by CPU time and network bytes).",
     "`redis-cli --hotkeys` or the server-side `HOTKEYS` command,\nwhich reports top-K by CPU time and network bytes.",
     "lint", ("RC015",)),
    # The delayed second delete, reverted to the in-process sleep it used to
    # prescribe -- the same defect class as AE-2's fire-and-forget goroutine.
    ("M19", "references/cache-patterns.md",
     "  3. App enqueues a second DEL, to run after `delay`, on a DURABLE mechanism",
     "  3. App schedules a second DEL after 500ms via a sleep in goroutine",
     "lint", ("RC016",)),
    # The original wording of the write-through read path.
    ("M20", "references/cache-patterns.md",
     "  2. Cache HIT → return the value the last SUCCESSFUL cache write left there",
     "  2. Cache HIT → return, always fresh since writes update the cache",
     "lint", ("RC017",)),
    ("M21", "references/cache-patterns.md",
     "    if err := rdb.Del(ctx, \"user:\"+u.ID).Err(); err != nil {",
     "    if _, err := rdb.Keys(ctx, \"user:*\").Result(); err != nil {",
     "lint", ("RC013",)),
    ("M22", "references/cache-anti-examples.md",
     "if err := rdb.Set(ctx, \"user:123\", userData, ttl).Err(); err != nil {",
     "if err := rdb.Set(ctx, \"user:123\", userData, 0).Err(); err != nil {",
     "lint", ("RC012",)),
    # RC008 reads the joined docs, so removing the concept from one file proves
    # nothing -- this mutation strips it wherever it appears.
    # Anchor is the fragment, not the word: the docs contain both "fencing" and
    # "Fencing", RC008 matches case-insensitively, and a mutation that leaves the
    # capitalised copy standing keeps the rule green and reports a false KILL.
    ("M23", ALL_DOCS,
     "encing",
     "uarding",
     "lint", ("RC008",)),
    # The wording that shipped and was wrong: keyspace notifications listed
    # beside CDC as an equivalent invalidation mechanism. Redis documents Pub/Sub
    # as fire-and-forget and cluster events as node-local and not broadcast, so
    # the two cannot share a reliability tier. Reverting the sentence must fail.
    ("M26", "SKILL.md",
     '*authoritative* mechanism must be active: TTL expiry, explicit invalidation on\nwrite, or a durable event stream (CDC / transactional outbox). "Write both and\nhope" is not one.',
     'mechanism must be active: TTL expiry, explicit invalidation on\nwrite, or event-driven (CDC, or keyspace `OVERWRITTEN` on 8.2+). "Write both and\nhope" is not one.',
     "lint", ("RC018",)),
    # A TOC that points at anchors which no longer exist is worse than no TOC:
    # it sends the reader to a 404 and looks maintained.
    ("M24", "references/distributed-locks.md",
     "- [7. Failover](#7-failover)",
     "- [7. Failover](#seven-failover)",
     "pytest", ()),
]


def run_gate(cmd: list[str]) -> int:
    return subprocess.run(cmd, cwd=SKILL_DIR, capture_output=True, text=True).returncode


def docs() -> list[str]:
    """Every markdown file a mutation may target, relative to the skill dir."""
    return ["SKILL.md"] + sorted(
        str(p.relative_to(SKILL_DIR)) for p in (SKILL_DIR / "references").glob("*.md"))


def targets(spec: str, anchor: str) -> list[str]:
    """Files this mutation edits. ALL_DOCS expands to every doc holding the anchor."""
    if spec != ALL_DOCS:
        return [spec]
    return [f for f in docs() if anchor in (SKILL_DIR / f).read_text(encoding="utf-8")]


def lint_rule_ids() -> set[str]:
    spec = importlib.util.spec_from_file_location(
        "rcs_lint_mut", SCRIPTS / "lint_cache_docs.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["rcs_lint_mut"] = mod
    spec.loader.exec_module(mod)
    return {r.id for r in mod.RULES}


def check_rule_coverage() -> list[str]:
    """Rules no mutation exercises, minus the ones declared as such.

    A sweep reports `N/N killed`, whose denominator is the mutation list. A rule
    with no mutation therefore contributes nothing to that ratio and reads as
    covered. Deriving the complement is the only way it becomes visible.
    """
    covered = {r for *_, rules in MUTATIONS for r in rules}
    uncovered = lint_rule_ids() - covered
    problems = []
    for rid in sorted(uncovered - RULES_WITHOUT_A_MUTATION):
        problems.append(f"{rid}: no mutation exercises this rule "
                        f"(add one, or declare it in RULES_WITHOUT_A_MUTATION)")
    for rid in sorted(RULES_WITHOUT_A_MUTATION - uncovered):
        problems.append(f"{rid}: declared as unexercised but a mutation now covers it")
    unknown = covered - lint_rule_ids()
    for rid in sorted(unknown):
        problems.append(f"{rid}: a mutation claims a rule that does not exist")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="check anchors only")
    args = ap.parse_args()

    gaps = check_rule_coverage()
    if gaps:
        print(f"{len(gaps)} rule-coverage problem(s):")
        for g in gaps:
            print(f"  {g}")
        return 1

    plan: list[tuple[str, list[str], str, str, str]] = []
    stale: list[tuple[str, str, str]] = []
    for mid, spec, anchor, repl, killer, _ in MUTATIONS:
        files = targets(spec, anchor)
        if not files or any(
            anchor not in (SKILL_DIR / f).read_text(encoding="utf-8") for f in files
        ):
            stale.append((mid, spec, anchor))
            continue
        plan.append((mid, files, anchor, repl, killer))

    if stale:
        print(f"{len(stale)} stale anchor(s) -- the doc moved and the mutation no longer applies:")
        for mid, f, a in stale:
            print(f"  {mid} {f}: {a.splitlines()[0][:70]!r}")
        return 1
    if args.verify:
        print(f"anchors: {len(plan)}/{len(MUTATIONS)} resolve · "
              f"lint rules exercised: {len({r for *_, rs in MUTATIONS for r in rs})}"
              f"/{len(lint_rule_ids())}")
        return 0

    # Baseline: every gate must be GREEN before a single mutation is applied.
    #
    # Checking only "the go gate is not 3" was not enough. A gate that is already
    # red on the unmutated tree returns 1 for every mutation too, so the sweep
    # reports a full kill count while proving nothing — which is precisely how a
    # sandbox cache failure once credited the go gate with all 12 kills. A gate
    # that cannot run at all (3) is INCOMPLETE; a gate that fails (1) means the
    # tree is broken and the sweep's results would be meaningless either way.
    baseline = {"go": run_gate(GO_GATE), "lint": run_gate(LINT_GATE),
                "pytest": run_gate(PYTEST_GATE)}
    if 3 in baseline.values():
        unusable = [n for n, rc in baseline.items() if rc == 3]
        print(f"INCOMPLETE: gate(s) {unusable} unusable; sweep not run", file=sys.stderr)
        return 3
    if any(rc != 0 for rc in baseline.values()):
        red = {n: rc for n, rc in baseline.items() if rc != 0}
        print(f"baseline is not green: {red}. Every mutation would be reported KILLED "
              f"by a gate that is already failing. Fix the tree, then re-run.",
              file=sys.stderr)
        return 1

    touched = {f for _, files, _, _, _ in plan for f in files}
    originals = {f: (SKILL_DIR / f).read_text(encoding="utf-8") for f in touched}

    killed = survived = misattributed = 0
    try:
        for mid, files, anchor, repl, killer in plan:
            for f in files:
                # replace ALL occurrences: a leftover copy makes a real gate look dead
                (SKILL_DIR / f).write_text(originals[f].replace(anchor, repl), encoding="utf-8")
            rcs = {"go": run_gate(GO_GATE), "lint": run_gate(LINT_GATE),
                   "pytest": run_gate(PYTEST_GATE)}
            for f in files:
                (SKILL_DIR / f).write_text(originals[f], encoding="utf-8")

            caught_by = [name for name, rc in rcs.items() if rc == 1]
            where = files[0] if len(files) == 1 else f"{len(files)} docs"
            if not caught_by:
                survived += 1
                print(f"  SURVIVED {mid}  {where}  [no gate rejected it]")
            elif killer not in caught_by:
                # A kill by the wrong gate is not a pass. The named gate is the
                # one this mutation exists to exercise; if something else caught
                # it, that gate may have died without anyone noticing — the
                # mutation is still "killed" and the count still looks healthy.
                misattributed += 1
                print(f"  MISKILLED {mid}  {where}  "
                      f"[killed by {'+'.join(caught_by)}, expected {killer}]")
            else:
                killed += 1
                print(f"  KILLED   {mid}  {where}  [{'+'.join(caught_by)}]")
    finally:
        for f, text in originals.items():
            (SKILL_DIR / f).write_text(text, encoding="utf-8")

    print(f"\nmutation sweep: {killed}/{len(plan)} killed by the expected gate, "
          f"{misattributed} killed by another gate, {survived} survived")
    if misattributed:
        print("A mutation caught only by an unexpected gate does not prove the gate it "
              "was written for still works. Fix the gate, or re-declare the killer.",
              file=sys.stderr)
    return 1 if (survived or misattributed) else 0


if __name__ == "__main__":
    sys.exit(main())

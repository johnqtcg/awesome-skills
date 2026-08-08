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
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL_DIR / "scripts"

GO_GATE = [sys.executable, str(SCRIPTS / "check_go_snippets.py")]
LINT_GATE = [sys.executable, str(SCRIPTS / "lint_cache_docs.py")]

# (id, file, anchor, replacement, expected killer)
MUTATIONS: list[tuple[str, str, str, str, str]] = [
    # --- the defects the 2026-08-08 review found ---
    ("M01", "references/cache-failure-modes.md",
     "    replica := rrCounter.Add(1) % shardCount",
     "    replica := crc32.ChecksumIEEE([]byte(logical)) % shardCount",
     "lint"),
    ("M02", "references/cache-failure-modes.md",
     "    c, err := ristretto.NewCache(&ristretto.Config{",
     "    c := ristretto.NewCache(&ristretto.Config{",
     "go"),
    ("M03", "references/cache-patterns.md",
     "    case errors.Is(err, redis.Nil):",
     "    case err == redis.Nil:",
     "lint"),
    ("M04", "references/cache-patterns.md",
     "### Cache-write failure semantics (mandatory to state)",
     "### Cache-write notes (optional)",
     "lint"),
    ("M05", "SKILL.md",
     "| **Data source type** | SQL DB / NoSQL / external API — affects consistency patterns | **Blocking — cannot be assumed** |",
     "| **Data source type** | SQL DB / NoSQL / external API — affects consistency patterns | Assume SQL |",
     "lint"),

    # --- regression guards on the fixes themselves ---
    ("M06", "references/cache-failure-modes.md",
     "    span := int64(base) / 5\n    if span <= 0 {\n        return base\n    }",
     "    span := int64(base.Seconds() * 0.2)",
     "lint"),
    ("M07", "references/cache-failure-modes.md",
     "        if b, ok := v.([]byte); ok {\n            return b, nil\n        }",
     "        return v.([]byte), nil",
     "lint"),
    ("M08", "SKILL.md",
     "   - **TTL**: per-field expiry needs `HEXPIRE`, which is **Redis 7.4+**.",
     "   - **TTL**: per-field expiry is available.",
     "lint"),
    ("M09", "SKILL.md",
     "**Verdict**: `X/14`; Critical: `Y/5`; Standard: `Z/5`; Hygiene: `W/4`.",
     "**Verdict**: `X/12`; Critical: `Y/3`; Standard: `Z/5`; Hygiene: `W/4`.",
     "lint"),
    ("M10", "references/cache-failure-modes.md",
     "    if _, err := pipe.Exec(ctx); err != nil {\n        // Partial failure is a real failure: some replicas now serve old data.\n        return fmt.Errorf(\"fan-out write %s: %w\", logical, err)\n    }\n    return nil",
     "    pipe.Exec(ctx)\n    return nil",
     "go"),

    # --- the defect that survived the first sweep: the same hash-sharding bug
    # --- had been fixed in the reference but left standing in SKILL.md prose.
    ("M11", "SKILL.md",
     "Defense: local in-process cache (L1), replica fan-out, or read replicas.",
     "Defense: local in-process cache (L1), key sharding (`key:{hash%N}`), or read replicas.",
     "lint"),
    # RC007 was guarded on the phrase "large value"; the section was reworded and
    # the rule silently stopped running while still passing its selftest. This
    # mutation reproduces that failure mode: strip the bullet the gate reads.
    ("M12", "SKILL.md",
     "   - **Memory**: a Hash is only more compact while it stays under **both** `hash-max-listpack-entries`",
     "   - **Memory**: a Hash is usually more compact. Ignore `hash-max-entries`",
     "lint"),
]


def run_gate(cmd: list[str]) -> int:
    return subprocess.run(cmd, cwd=SKILL_DIR, capture_output=True, text=True).returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="check anchors only")
    args = ap.parse_args()

    originals = {f: (SKILL_DIR / f).read_text(encoding="utf-8")
                 for _, f, _, _, _ in MUTATIONS}

    stale = [(mid, f, a) for mid, f, a, _, _ in MUTATIONS if a not in originals[f]]
    if stale:
        print(f"{len(stale)} stale anchor(s) -- the doc moved and the mutation no longer applies:")
        for mid, f, a in stale:
            print(f"  {mid} {f}: {a.splitlines()[0][:70]!r}")
        return 1
    if args.verify:
        print(f"anchors: {len(MUTATIONS)}/{len(MUTATIONS)} resolve")
        return 0

    if run_gate(GO_GATE) == 3:
        print("INCOMPLETE: go gate unusable (toolchain/modules); sweep not run", file=sys.stderr)
        return 3

    killed = survived = 0
    try:
        for mid, f, anchor, repl, killer in MUTATIONS:
            path = SKILL_DIR / f
            # replace ALL occurrences: a leftover copy makes a real gate look dead
            path.write_text(originals[f].replace(anchor, repl), encoding="utf-8")
            go_rc = run_gate(GO_GATE)
            lint_rc = run_gate(LINT_GATE)
            path.write_text(originals[f], encoding="utf-8")

            caught_by = []
            if go_rc == 1:
                caught_by.append("go")
            if lint_rc == 1:
                caught_by.append("lint")
            if caught_by:
                killed += 1
                tag = "KILLED  "
                note = "+".join(caught_by)
                if killer not in caught_by:
                    note += f" (expected {killer})"
            else:
                survived += 1
                tag = "SURVIVED"
                note = "no gate rejected it"
            print(f"  {tag} {mid}  {f}  [{note}]")
    finally:
        for f, text in originals.items():
            (SKILL_DIR / f).write_text(text, encoding="utf-8")

    print(f"\nmutation sweep: {killed}/{len(MUTATIONS)} killed, {survived} survived")
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Generate scripts/tests/COVERAGE.md from live data.

Hand-maintained coverage tables drift the moment a test is added, and a stale
table that claims "100%" is worse than no table. Everything here is counted from
the actual fixtures, rules and collected tests.

GENERATED IS NOT THE SAME AS COMPLETE
-------------------------------------
"Auto-generated" only guarantees the table agrees with *this generator's model of
the world*. It said so for a while and was still wrong: the runner grew a seventh
gate (the paraphrase corpus) and the Gate Summary kept listing five, because the
five were hard-coded here. A generator with a hard-coded list is a hand-maintained
table with extra steps.

So the gate list is now **parsed out of run_regression.sh** — the file that
actually decides what runs — and `--check` fails if the two disagree. Add a gate
to the runner and this table grows with it; add one here and it will not.

    python3 gen_coverage.py            # rewrite COVERAGE.md
    python3 gen_coverage.py --check    # fail if the file is out of date
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import re
import subprocess
import sys

SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent
TESTS_DIR = SKILL_DIR / "scripts" / "tests"
GOLDEN_DIR = TESTS_DIR / "golden"
RUNNER = SKILL_DIR / "scripts" / "run_regression.sh"
OUT = TESTS_DIR / "COVERAGE.md"

# What each gate proves, keyed by the script the runner invokes. Selftest and
# plain doc-scan share a script, so the selftest flag disambiguates.
GATE_PROVES = {
    ("lint_kafka_docs.py", True): "every rule can fire AND stay quiet",
    ("lint_kafka_docs.py", False): "shipped docs assert no known-wrong claim",
    ("mutation_sweep.py", False): "an inverted claim is actually caught",
    ("paraphrase_corpus.py", False): "restatements the docs never use are still caught",
    ("test_skill_contract.py", False): "required structure and checkable claims",
    ("test_golden_scenarios.py", False): "detector expectations + verified upstream facts",
    ("model_eval.py", False): "the model-eval grader separates a correct review from a confident wrong one",
    ("gen_coverage.py", False): "this table matches the runner and the sources",
}


def parse_gates() -> list[tuple[str, str, bool]]:
    """[(label, script, is_selftest)] in the order run_regression.sh runs them.

    Parsed rather than listed, so a gate added to the runner cannot be missing
    here. Raises if the runner's own `[i/N]` numbering is inconsistent — a
    mislabelled gate is the same silent-drift bug one level down.
    """
    text = RUNNER.read_text(encoding="utf-8")
    calls = re.findall(r'run_gate\s+"([^"]+)"\s*\\\s*\n\s*(.+)', text)
    gates = []
    for label, command in calls:
        # Tokens arrive quoted and shell-interpolated:
        #   python3 "${SCRIPT_DIR}/lint_kafka_docs.py" --selftest
        # so strip quotes before matching, or every script reads as unknown and
        # the table silently fills with em-dashes.
        script = next((tok.strip('"\'').rsplit("/", 1)[-1]
                       for tok in command.split()
                       if tok.strip('"\'').endswith(".py")), "")
        assert script, f"cannot identify the script for gate {label!r}: {command!r}"
        gates.append((label, script, "--selftest" in command))

    numbers = [re.match(r"\[(\d+)/(\d+)\]", label) for label, _, _ in gates]
    assert all(numbers), f"run_regression.sh has an unnumbered gate: {gates}"
    indices = [int(m.group(1)) for m in numbers]
    totals = {int(m.group(2)) for m in numbers}
    assert indices == list(range(1, len(gates) + 1)), \
        f"run_regression.sh gate numbering is not 1..N: {indices}"
    assert totals == {len(gates)}, \
        f"run_regression.sh says /{totals} but defines {len(gates)} gates"
    return gates


def _load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def collected(test_file: str) -> int:
    out = subprocess.run(
        [sys.executable, "-m", "pytest", str(TESTS_DIR / test_file), "--collect-only", "-q"],
        capture_output=True, text=True, cwd=SKILL_DIR,
    ).stdout
    for line in reversed(out.splitlines()):
        if "test" in line and "collected" in line:
            for tok in line.split():
                if tok.isdigit():
                    return int(tok)
    return sum(1 for l in out.splitlines() if "::" in l)


def build() -> str:
    linter = _load("lint_kafka_docs", SKILL_DIR / "scripts" / "lint_kafka_docs.py")
    sweep = _load("mutation_sweep", SKILL_DIR / "scripts" / "mutation_sweep.py")
    corpus = _load("paraphrase_corpus", SKILL_DIR / "scripts" / "paraphrase_corpus.py")
    evaluator = _load("model_eval", SKILL_DIR / "scripts" / "model_eval.py")

    fixtures = [json.loads(p.read_text(encoding="utf-8"))
                for p in sorted(GOLDEN_DIR.glob("*.json"))]
    rules = linter.RULES
    muts = sweep.MUTATIONS
    n_contract = collected("test_skill_contract.py")
    n_golden = collected("test_golden_scenarios.py")
    selftest_cases = sum(len(r.should_fire) + len(r.should_pass) for r in rules)
    n_scanned = len(linter.default_targets())
    n_probes = sum(len(fire) + len(quiet) for _, fire, quiet in corpus.CORPUS)

    sizes = {
        ("lint_kafka_docs.py", True): f"{len(rules)} rules, {selftest_cases} cases",
        ("lint_kafka_docs.py", False): f"{len(rules)} rules over {n_scanned} files",
        ("mutation_sweep.py", False): f"{len(muts)} mutations",
        ("paraphrase_corpus.py", False):
            f"{n_probes} probes over {len(corpus.CORPUS)} rules",
        ("test_skill_contract.py", False): f"{n_contract} tests",
        ("test_golden_scenarios.py", False): f"{n_golden} tests",
        ("model_eval.py", False):
            f"{len(evaluator.DECOYS)} good/decoy pairs, margin ≥ "
            f"{evaluator.CALIBRATION_MARGIN}",
        ("gen_coverage.py", False): "derived, not hand-listed",
    }

    covered_rules = {r for f in fixtures for r in f["detector_rules"]}
    covered_by_mut = {m.expect_rule for m in muts}

    by_type: dict[str, int] = {}
    by_sev: dict[str, int] = {}
    for f in fixtures:
        by_type[f["type"]] = by_type.get(f["type"], 0) + 1
        by_sev[f["severity"]] = by_sev.get(f["severity"], 0) + 1

    gates = parse_gates()
    L = [
        "<!-- GENERATED by scripts/gen_coverage.py — do not edit by hand. -->",
        "# kafka-event-driven-design — Test Coverage",
        "",
        f"## 1. Gate Summary — {len(gates)} gates",
        "",
        "| Gate | What it proves | Size |",
        "|------|----------------|------|",
    ]
    for label, script, is_selftest in gates:
        key = (script, is_selftest)
        # Loud, not an em-dash. An unrecognised gate rendering as "— | —" is the
        # same failure this generator was rewritten to remove: the table looks
        # complete while saying nothing about a gate that really runs.
        assert key in GATE_PROVES and key in sizes, (
            f"gate {label!r} runs {script} but GATE_PROVES/sizes has no entry "
            f"for {key} — describe the new gate here")
        pretty = re.sub(r"^\[\d+/\d+\]\s*", "", label)
        L.append(f"| {pretty} | {GATE_PROVES[key]} | {sizes[key]} |")
    L += [
        "",
        f"**Total: {n_contract + n_golden} pytest tests, "
        f"{selftest_cases} linter self-test cases, {n_probes} paraphrase probes, "
        f"{len(muts)} mutations.**",
        "",
        "The gate rows are parsed from `scripts/run_regression.sh`, not listed "
        "here — a gate added to the runner shows up in this table or "
        "`--check` fails. Sizes are counted from the modules themselves; "
        "regenerate with `python3 scripts/gen_coverage.py`.",
        "",
        "## 2. Semantic Rules",
        "",
        "| Rule | Kind | Claim it defends | Fixture | Mutation |",
        "|------|------|------------------|:-------:|:--------:|",
    ]
    for r in sorted(rules, key=lambda x: x.id):
        L.append(f"| `{r.id}` | {r.kind} | {r.summary} | "
                 f"{'yes' if r.id in covered_rules else '—'} | "
                 f"{'yes' if r.id in covered_by_mut else '—'} |")

    uncovered = sorted({r.id for r in rules} - covered_by_mut)
    L += [
        "",
        f"Rules exercised by a mutation: **{len(covered_by_mut)}/{len(rules)}**. "
        + (f"Not mutation-covered: {', '.join(uncovered)}." if uncovered
           else "Every rule is mutation-covered."),
        "",
        "## 3. Golden Fixtures",
        "",
        "| ID | Type | Severity | Detector rules | Title |",
        "|----|------|----------|----------------|-------|",
    ]
    for f in fixtures:
        det = ", ".join(f["detector_rules"]) or "— (false-positive guard)"
        L.append(f"| {f['id']} | {f['type']} | {f['severity']} | {det} | {f['title'][:70]} |")

    L += [
        "",
        f"By type: " + ", ".join(f"{k} {v}" for k, v in sorted(by_type.items())) + ".",
        f" By severity: " + ", ".join(f"{k} {v}" for k, v in sorted(by_sev.items())) + ".",
        "",
        "Fixtures with no detector rules are not filler — they assert the linter "
        "stays silent on realistic Kafka code, which is the false-positive half "
        "of the contract.",
        "",
        "## 4. Known Gaps",
        "",
        "| Gap | Priority | Why it is still open |",
        "|-----|----------|----------------------|",
        "| No live broker in the loop | High | Every claim here is verified against Apache Kafka source and official docs, not against a running 2.8/3.x/4.x cluster. A server matrix would catch facts that are true in source but not in practice. |",
        f"| No scored model run | High | `scripts/model_eval.py` runs the A/B (prompt alone vs prompt + SKILL.md) over the {sum(1 for f in fixtures if f['type'] == 'defect')} defect fixtures with a deterministic grader, and its grader is calibrated offline by gate 7 — but **no arm has been scored against a real model**. A nested `claude -p` does not inherit session credentials, so it exits 2 (`SKIPPED (infra)`, never 0). Run it in an authenticated shell: `python3 scripts/model_eval.py --json ab.json`, or point `--runner` at any CLI. |",
        "| Trigger precision unmeasured | High | `scripts/trigger_eval.py` (30 probes: 15 in-scope, 15 near-miss out-of-scope from §1's exclusion table) has produced **no scored run**, same credential reason. It is also only a proxy: it measures whether the frontmatter `description` is classifiable by a judge model, not whether the host agent fires. |",
        f"| Semantic lint is a known-regression detector, not a semantic checker | Medium | {len(rules)} regexes over English. A finding is real; silence is not a clearance. {n_probes} paraphrase probes raise the floor, and four natural restatements still walked through a fully green suite in the most recent round. Coverage grows by adding paraphrases, never by trusting the regex to generalise. |",
        "| Chinese-language claims unlinted | Medium | The rules are English regexes; the bilingual eval reports are checked by hand. |",
        f"| SKILL.md is always-loaded context | Medium | {(SKILL_DIR / 'SKILL.md').stat().st_size:,} bytes, {len((SKILL_DIR / 'SKILL.md').read_text(encoding='utf-8').splitlines())} lines. The anti-example bodies and the tier checklists now live in `references/`; what remains is the gate/checklist/scorecard path itself, and further cuts trade away correctness qualifications rather than duplication. |",
        "| Kafka Streams / Connect | Low | Out of scope per SKILL.md §1. |",
    ]
    # No trailing blank entry: main() appends the single closing newline, and a
    # blank element here produces the double newline `git diff --check` flags.
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    new = build()
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current.strip() != new.strip():
            print("COVERAGE.md is stale — run: python3 scripts/gen_coverage.py")
            return 1
        print("COVERAGE.md is up to date")
        return 0
    OUT.write_text(new + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

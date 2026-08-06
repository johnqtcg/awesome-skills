#!/usr/bin/env python3
"""With-skill / without-skill model evaluation for the mysql-migration skill.

The rest of this skill's test suite proves the *documentation* is correct and
self-consistent. None of it answers the question the skill exists for: does
having it change what an assistant produces? This harness does, by running each
golden fixture through a model twice — once with the skill in the prompt, once
without — and grading both arms with the same deterministic rubric.

Grading is deliberately NOT done by a model. Every criterion is a regex or a
`lint_migration.py` verdict over the response text, so a re-run on the same
transcripts produces the same score, and the rubric can itself be unit-tested
against recorded responses (`scripts/tests/eval_fixtures/`). A model grader would
make the headline number unfalsifiable, which is the failure mode this whole
audit has been about.

    # Grade transcripts that already exist (no model needed, fully deterministic)
    ./run_model_eval.py --replay scripts/tests/eval_fixtures

    # Generate transcripts, then grade them
    ./run_model_eval.py --model-cmd 'claude -p --tools "" --permission-mode dontAsk' \
                        --out results/

Exit codes:
    0  graded successfully (or skipped because no model was configured)
    1  the with-skill arm did not beat the without-skill arm on required criteria
    2  usage / unreadable input
    3  a model was requested but could not be invoked
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass, asdict

SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent
GOLDEN_DIR = SKILL_DIR / "scripts" / "tests" / "golden"


def _load_linter():
    spec = importlib.util.spec_from_file_location(
        "mysql_migration_linter_eval", SKILL_DIR / "scripts" / "lint_migration.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


LINT = _load_linter()


# ---------------------------------------------------------------------------
# Rubric
# ---------------------------------------------------------------------------


@dataclass
class Criterion:
    """One gradeable property of a response.

    `required` criteria are the ones the skill claims to add. The harness fails
    when the with-skill arm does not beat the without-skill arm on them, so a
    skill that changes nothing cannot report success.
    """

    key: str
    description: str
    pattern: str
    required: bool = True
    flags: int = re.I

    def met(self, response: str) -> bool:
        return bool(re.search(self.pattern, response, self.flags))


# Structural criteria: the output contract in SKILL.md section 9.
STRUCTURE = [
    Criterion("context_gate", "states the MySQL version it assumed",
              r"\b(5\.7|8\.0|8\.4|9\.\d)(\.\d+)?\b"),
    Criterion("risk_table", "assigns SAFE / WARN / UNSAFE per statement",
              r"\b(UNSAFE|WARN|SAFE)\b"),
    Criterion("scorecard", "produces a scorecard verdict",
              r"scorecard|\bPASS\b|\bFAIL\b"),
    Criterion("uncovered_risks", "lists what it could not determine",
              r"uncovered risk|assumption|could not determine|unknown"),
    Criterion("rollback", "names a reversal path",
              r"rollback|revert|restore|compensating|irreversible"),
]

# Technical criteria: the specific facts this skill got wrong before the audit.
# A baseline model may well know some of these; that is the point of the
# comparison arm.
TECHNICAL = [
    Criterion("algorithm_explicit", "specifies ALGORITHM= on ALTER statements",
              r"ALGORITHM\s*=\s*(INSTANT|INPLACE|COPY)"),
    # An INSTANT statement must NOT carry LOCK=NONE/SHARED/EXCLUSIVE — only
    # LOCK=DEFAULT is permitted — so a correct INSTANT response omits the clause.
    # Requiring a literal LOCK= scored that correct answer as a regression.
    Criterion("lock_explicit",
              "states the lock level for INPLACE/COPY, or correctly omits it for INSTANT",
              r"LOCK\s*=\s*(NONE|SHARED|EXCLUSIVE|DEFAULT)|ALGORITHM\s*=\s*INSTANT"),
    Criterion("session_guard", "sets a lock_wait_timeout guard",
              r"lock_wait_timeout"),
    Criterion("instant_version_gate", "gates INSTANT on 8.0.12+ rather than 8.0",
              r"8\.0\.12|no INSTANT|does not support INSTANT|INSTANT.*not.*5\.7", required=False),
    Criterion("pk_range_backfill", "batches backfill by primary-key range, not OFFSET",
              r"primary[- ]key range|PK range|id >|WHERE id BETWEEN", required=False),
]


@dataclass
class Grade:
    scenario: str
    arm: str
    met: dict
    lint_critical: int
    lint_warning: int
    lint_error: bool
    score: int
    max_score: int

    def as_dict(self) -> dict:
        return asdict(self)


_BARE_SQL = re.compile(
    r"^[ \t]*(ALTER\s+TABLE|CREATE\s+(?:UNIQUE\s+)?INDEX|DROP\s+INDEX|SET\s+SESSION)\b.*?;",
    re.I | re.M | re.S)


def extract_sql(response: str) -> str:
    """Pull SQL out of a model response so the linter can read it.

    Fenced blocks first. If there are none, fall back to bare statements: a
    response that emits DDL without a code fence would otherwise skip the lint
    arm entirely, which rewards omitting the fence.
    """
    blocks = re.findall(r"```(?:sql|mysql)?\s*\n(.*?)```", response, re.S | re.I)
    if blocks:
        return "\n".join(blocks)
    return "\n".join(m.group(0) for m in _BARE_SQL.finditer(response))


def grade(scenario: str, arm: str, response: str, version: str) -> Grade:
    criteria = STRUCTURE + TECHNICAL
    met = {c.key: c.met(response) for c in criteria}

    sql = extract_sql(response)
    critical = warning = 0
    lint_error = False
    if sql.strip():
        try:
            findings = LINT.lint_text(f"{scenario}.sql", sql, LINT.parse_version(version), False)
            critical = sum(1 for f in findings if f.severity == LINT.CRITICAL)
            warning = sum(1 for f in findings if f.severity == LINT.WARNING)
        except Exception:
            # A crashed linter is its own state, never a score. Encoding it as -1
            # made a failed lint compare as *cleaner* than a clean one, because
            # every later comparison used `> 0` or `max(..., 0)`.
            lint_error = True

    score = sum(1 for v in met.values() if v)
    return Grade(scenario, arm, met, critical, warning, lint_error, score, len(criteria))


# ---------------------------------------------------------------------------
# Transcript sourcing
# ---------------------------------------------------------------------------


def load_scenarios() -> list[dict]:
    out = []
    for f in sorted(GOLDEN_DIR.glob("*.json")):
        fx = json.loads(f.read_text(encoding="utf-8"))
        if fx["type"] in ("defect", "workflow"):
            out.append(fx)
    return out


def build_prompt(fixture: dict, with_skill: bool) -> str:
    """Assemble one arm's prompt.

    The with-skill arm includes the reference file the fixture declares, not just
    SKILL.md. SKILL.md is a router — section 10 tells the reader to load a
    reference before deciding anything version-gated — so injecting it alone
    measures a crippled version of the skill and understates (or misrepresents)
    what a real invocation does.
    """
    ctx = fixture.get("context") or {}
    header = (
        f"Review this MySQL migration.\n"
        f"MySQL version: {ctx.get('mysql_version', 'unknown')}\n"
        f"Table rows: {ctx.get('table_rows', 'unknown')}\n"
        f"Replication: {ctx.get('replication', 'unknown')}\n\n"
        f"```sql\n{fixture['migration_snippet']}\n```\n"
    )
    if not with_skill:
        return header

    parts = [(SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")]
    for rel in referenced_files(fixture):
        path = SKILL_DIR / rel
        if path.exists():
            parts.append(f"\n\n--- {rel} ---\n\n" + path.read_text(encoding="utf-8"))
    body = "\n".join(parts)
    return f"{body}\n\n---\n\nApply the skill above to the following task.\n\n{header}"


def referenced_files(fixture: dict) -> list[str]:
    """Reference docs this scenario expects to be loaded, beyond SKILL.md.

    Always includes the algorithm matrix: SKILL.md section 10 requires it at
    Standard depth or above, which every golden scenario reaches.

    SKILL.md is filtered out: it is already the first element of the prompt, and
    a fixture whose `reference` names it would otherwise be injected twice —
    padding the with-skill arm with a duplicate and inflating any length- or
    repetition-sensitive effect.
    """
    refs = ["references/ddl-algorithm-matrix.md"]
    declared = fixture.get("reference")
    if declared and declared not in refs and pathlib.Path(declared).name != "SKILL.md":
        refs.append(declared)
    return refs


def run_model(cmd: str, prompt: str) -> str:
    proc = subprocess.run(cmd, shell=True, input=prompt, capture_output=True,
                          text=True, timeout=600, cwd=str(SKILL_DIR.parent.parent))
    if proc.returncode != 0:
        raise RuntimeError(f"model command failed ({proc.returncode}): {proc.stderr[-400:]}")
    return proc.stdout


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def report(grades: list[Grade], max_critical: int = 0,
           max_warnings: int | None = None) -> tuple[str, bool]:
    by_arm: dict[str, dict[str, Grade]] = {}
    for g in grades:
        by_arm.setdefault(g.arm, {})[g.scenario] = g

    lines = ["# mysql-migration model evaluation", ""]
    if set(by_arm) != {"with_skill", "without_skill"}:
        lines.append(f"Arms present: {sorted(by_arm)} — a one-armed run proves nothing about the "
                     "skill's contribution.")
        return "\n".join(lines), False

    # Score only scenarios present in BOTH arms. Comparing aggregates over
    # different scenario sets is how an easier sample in one arm turns into an
    # apparent improvement; an unpaired scenario is missing data, not a datum.
    with_ids = set(by_arm["with_skill"])
    without_ids = set(by_arm["without_skill"])
    paired = sorted(with_ids & without_ids)
    unpaired = sorted((with_ids | without_ids) - set(paired))
    if unpaired:
        lines.append(f"**Unpaired scenarios excluded from scoring:** {unpaired}. Each arm must "
                     "answer the same set of scenarios for the comparison to mean anything.")
        lines.append("")
    if not paired:
        lines.append("**FAIL** — no scenario was answered by both arms; nothing is comparable.")
        return "\n".join(lines), False

    by_arm = {arm: [g for sid, g in sorted(gs.items()) if sid in set(paired)]
              for arm, gs in by_arm.items()}
    lines.append(f"Paired scenarios scored: {len(paired)} ({', '.join(paired)})")
    lines.append("")

    criteria = {c.key: c for c in STRUCTURE + TECHNICAL}
    lines += ["| Criterion | required | without skill | with skill | delta |",
              "|---|:---:|:---:|:---:|:---:|"]

    regressions, improvements, optional_gains = [], [], []
    for key, crit in criteria.items():
        w = sum(1 for g in by_arm["with_skill"] if g.met[key])
        wo = sum(1 for g in by_arm["without_skill"] if g.met[key])
        n = len(by_arm["with_skill"])
        delta = w - wo
        if crit.required and delta < 0:
            regressions.append(key)
        # Only a required-criterion gain counts as the skill earning its place.
        # Moving an optional nice-to-have while the contract items stay flat is
        # not evidence the skill works.
        if delta > 0 and crit.required:
            improvements.append(key)
        elif delta > 0:
            optional_gains.append(key)
        lines.append(f"| {crit.description} | {'yes' if crit.required else 'no'} | "
                     f"{wo}/{n} | {w}/{n} | {delta:+d} |")

    # ---- Absolute gates -----------------------------------------------------
    # A migration skill whose own output the server rejects has failed, whatever
    # happened to the formatting. Comparing only the DELTA let both arms emit the
    # same rejected statement while the with-skill arm "won" on structure.
    unsafe = [f"{g.scenario} ({g.lint_critical} critical)"
              for g in by_arm["with_skill"] if g.lint_critical > max_critical]
    lint_errors = [g.scenario for g in by_arm["with_skill"] + by_arm["without_skill"]
                   if g.lint_error]
    noisy = ([f"{g.scenario} ({g.lint_warning} warnings)"
              for g in by_arm["with_skill"] if g.lint_warning > max_warnings]
             if max_warnings is not None else [])

    crit_w = sum(g.lint_critical for g in by_arm["with_skill"] if g.lint_critical > 0)
    crit_wo = sum(g.lint_critical for g in by_arm["without_skill"] if g.lint_critical > 0)
    lines += ["", f"Critical lint findings in emitted SQL — without skill: {crit_wo}, "
                  f"with skill: {crit_w} (lower is better).", ""]

    # Per-scenario gates. Totals can hide a scenario where the skill made things
    # worse, because a gain elsewhere cancels it out. A regression on any single
    # scenario is a real defect regardless of the average.
    w_by_id = {g.scenario: g for g in by_arm["with_skill"]}
    wo_by_id = {g.scenario: g for g in by_arm["without_skill"]}
    per_scenario_lint: list[str] = []
    per_scenario_required: list[str] = []
    for sid in paired:
        gw, gwo = w_by_id[sid], wo_by_id[sid]
        if gw.lint_critical > max(gwo.lint_critical, 0):
            per_scenario_lint.append(
                f"{sid} ({gwo.lint_critical} → {gw.lint_critical})")
        lost = sorted(k for k, c in criteria.items()
                      if c.required and gwo.met[k] and not gw.met[k])
        if lost:
            per_scenario_required.append(f"{sid}: {lost}")
    if per_scenario_lint or per_scenario_required:
        lines.append("**Per-scenario regressions** (invisible in the totals above):")
        for entry in per_scenario_lint:
            lines.append(f"- new critical lint findings — {entry}")
        for entry in per_scenario_required:
            lines.append(f"- lost a required criterion — {entry}")
        lines.append("")

    ok = (not unsafe and not lint_errors and not noisy
          and not regressions and bool(improvements) and crit_w <= crit_wo
          and not per_scenario_lint and not per_scenario_required)
    # Report the most specific cause first: a lint regression is concrete evidence
    # of harm, and must not be reported as the vaguer "improved nothing".
    if lint_errors:
        lines.append(f"**FAIL** — the checker could not parse the SQL emitted for {lint_errors}. "
                     "A lint error is not a clean lint; nothing about those scenarios is known.")
    elif unsafe:
        lines.append(f"**FAIL** — the with-skill arm emitted SQL with critical findings on "
                     f"{unsafe} (limit: {max_critical}). Whether the baseline was equally bad is "
                     "beside the point: a migration skill that produces statements the server "
                     "rejects has not helped, however well-formatted the surrounding review is.")
    elif noisy:
        lines.append(f"**FAIL** — with-skill warnings above --max-warnings={max_warnings}: "
                     f"{noisy}.")
    elif per_scenario_lint:
        lines.append("**FAIL** — the skill introduced critical lint findings on at least one "
                     f"scenario: {per_scenario_lint}. A net-zero total does not make that "
                     "acceptable.")
    elif per_scenario_required:
        lines.append("**FAIL** — the skill lost a required criterion on at least one scenario: "
                     f"{per_scenario_required}.")
    elif regressions:
        lines.append(f"**FAIL** — required criteria regressed with the skill: {regressions}")
    elif crit_w > crit_wo:
        lines.append(f"**FAIL** — the with-skill arm emitted SQL with more critical lint findings "
                     f"({crit_w} vs {crit_wo}). Producing well-structured output that the server "
                     "would reject is worse than producing neither.")
    elif not improvements:
        extra = (f" Optional criteria did move ({optional_gains}), but no required one did."
                 if optional_gains else "")
        lines.append("**FAIL** — the skill improved no *required* criterion." + extra +
                     " Either the rubric is wrong or the skill is not earning its context budget.")
    else:
        lines.append(f"**PASS** — improved: {improvements}; no required criterion regressed.")
    return "\n".join(lines), ok


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model-cmd",
                    help="shell command that reads a prompt on stdin and writes the response to "
                         "stdout, e.g. 'claude -p --tools \"\" --permission-mode dontAsk'")
    ap.add_argument("--replay", metavar="DIR",
                    help="grade existing transcripts instead of calling a model. DIR holds "
                         "<scenario>.<arm>.txt files.")
    ap.add_argument("--out", metavar="DIR", help="write transcripts and results here")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    ap.add_argument("--max-critical", type=int, default=0, metavar="N",
                    help="maximum critical lint findings permitted in ANY with-skill scenario "
                         "(default 0). This is an absolute gate, not a delta: matching a bad "
                         "baseline is not success.")
    ap.add_argument("--max-warnings", type=int, default=None, metavar="N",
                    help="maximum lint warnings permitted in any with-skill scenario "
                         "(default: unlimited)")
    args = ap.parse_args(argv)

    if not args.model_cmd and not args.replay:
        print("SKIP: model evaluation not requested.")
        print("      Pass --replay DIR to grade recorded transcripts (deterministic, no model),")
        print("      or --model-cmd '<cmd>' to generate them.")
        print("      Nothing else in this skill's test suite measures whether the skill changes")
        print("      what a model produces. Treat that question as UNANSWERED until this runs.")
        return 0

    scenarios = load_scenarios()
    grades: list[Grade] = []
    out_dir = pathlib.Path(args.out) if args.out else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    for fx in scenarios:
        version = (fx.get("context") or {}).get("mysql_version", "8.0.32")
        if version == "unknown":
            version = "5.7.40"
        for arm, with_skill in (("without_skill", False), ("with_skill", True)):
            if args.replay:
                path = pathlib.Path(args.replay) / f"{fx['id']}.{arm}.txt"
                if not path.exists():
                    continue
                response = path.read_text(encoding="utf-8")
            else:
                try:
                    response = run_model(args.model_cmd, build_prompt(fx, with_skill))
                except (RuntimeError, subprocess.SubprocessError, OSError) as exc:
                    print(f"ERROR: model invocation failed for {fx['id']}/{arm}: {exc}",
                          file=sys.stderr)
                    return 3
                if out_dir:
                    (out_dir / f"{fx['id']}.{arm}.txt").write_text(response, encoding="utf-8")
            grades.append(grade(fx["id"], arm, response, version))

    if not grades:
        print("ERROR: no transcripts were graded — check --replay DIR contents.", file=sys.stderr)
        return 2

    text, ok = report(grades, args.max_critical, args.max_warnings)
    if args.format == "json":
        print(json.dumps({"grades": [g.as_dict() for g in grades], "pass": ok}, indent=2))
    else:
        print(text)
    if out_dir:
        (out_dir / "report.md").write_text(text, encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

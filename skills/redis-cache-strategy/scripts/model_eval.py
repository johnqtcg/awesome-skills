#!/usr/bin/env python3
"""Does a model carrying this skill actually review a cache correctly?

WHY THIS EXISTS
---------------
Every other gate in this skill checks the *document*: the snippets compile, the
rules fire, the fixtures drive the checker, the scorecard arithmetic is
consistent. None of them observe a model. `COVERAGE.md` is explicit that most
headline defects are gated only by "the model reading SKILL.md" — and until this
file, that sentence was an assumption with nothing behind it.

Two arms over the same corpus:

    arm A   the code and the question, nothing else
    arm B   the same, plus SKILL.md and the references §10 says to load

Arm B injects `cache-patterns.md` and `cache-anti-examples.md` by default,
because §10 loads them for any review at Standard depth and for any review or
troubleshoot mode respectively. `--refs none` and `--refs all` bracket that.

THE CORPUS IS NOT DEFECTS ONLY
------------------------------
`good_practice` fixtures are graded too. A defects-only corpus rewards a model
that condemns everything, which measures pessimism, not judgement. The
false-alarm axis exists to make that visible.

THE GRADER IS NOT A MODEL
-------------------------
No LLM judges the output. A model grading a model shares its blind spots and
turns a measurement into a correlated guess. Grading is five mechanical passes,
each declared as an axis:

  recall          concepts from the fixture's `coverage_rules` that were named
  items           §5 item IDs from `scorecard_items` that were named
  verdict         a defect must not be verdicted PASS; a good practice must not
                  be verdicted FAIL
  no_false_alarm  no invented defect on a good_practice fixture
  no_refuted      no repetition of a claim this skill declares wrong

`--calibrate` proves the grader separates on **each axis independently**: one
decoy response per axis, each of which must move that axis and leave the others
alone. A grader whose axes move together is one axis wearing five hats, and it
would report a healthy score with a mechanism deleted.

Usage:
  model_eval.py --calibrate        offline; no model; this is the regression gate
  model_eval.py --run              A/B against `claude -p`
  model_eval.py --run --limit 4    a subset, for a quick look

Exit: 0 ok · 1 calibration failed / arm B did not beat arm A · 3 no model runner
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field

SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent
GOLDEN = SKILL_DIR / "scripts" / "tests" / "golden"
REFS = SKILL_DIR / "references"

# A nested `claude -p` inherits this session's permission mode, MCP servers,
# working directory and CLAUDE.md unless told otherwise. That contaminates the
# measurement -- the arm-A model is supposed to have NO skill, and an inherited
# project CLAUDE.md is a skill by another name -- and it is why an unqualified
# runner hangs waiting on a permission prompt. Isolate explicitly.
DEFAULT_RUNNER = (
    "claude -p --output-format text --permission-mode dontAsk "
    "--strict-mcp-config --disallowed-tools Bash,Edit,Write,Read"
)

AXES = ("recall", "items", "verdict", "no_false_alarm", "no_refuted")


# ---------------------------------------------------------------------------
# what the skill declares wrong -- repeating any of these is a scored failure
# ---------------------------------------------------------------------------

# (name, claim pattern). A claim only counts when the *same clause* does not
# reject it: "write-through is not strong consistency" must score clean while
# "write-through gives strong consistency" must not. Clause, not sentence and
# not paragraph -- a paragraph-scoped guard is defeated by any nearby "not".
REFUTED_CLAIMS: tuple[tuple[str, str], ...] = (
    ("write-through-is-strong",
     r"write[- ]through[^,;.]{0,40}(?:strong|immediate)\s+consistency"
     r"|(?:strong|immediate)\s+consistency[^,;.]{0,30}write[- ]through"),
    ("cache-always-fresh",
     r"(?:always|guaranteed)[^,;.]{0,30}(?:fresh|up[- ]to[- ]date)"),
    ("hash-of-key-sharding",
     r"hash\s*%\s*\w+|crc32[^,;.]{0,30}%\s*(?:shard|replica|n\b)"),
    ("redlock-solves-pauses",
     r"redlock[^,;.]{0,40}(?:solves|prevents|handles)[^,;.]{0,30}(?:pause|gc)"),
    ("redis-lock-is-enough",
     r"(?:redis|distributed)\s+lock[^,;.]{0,40}(?:guarantees|ensures|is sufficient)"
     r"[^,;.]{0,30}(?:mutual exclusion|correctness|exactly[- ]once)"),
    ("bloom-can-delete",
     r"bloom filter[^,;.]{0,40}(?:supports?|allows?)[^,;.]{0,20}delet"),
)

# Words that, inside the SAME clause, turn a claim into its rejection.
CLAUSE_REJECTION = re.compile(
    r"\bnot\b|\bnever\b|\bno\b|\bcannot\b|\bcan't\b|\bdoes not\b|\bdoesn't\b"
    r"|\bwrong\b|\bmyth\b|\bfalse\b|\bavoid\b|\bincorrect\b",
    re.I,
)

# Claiming a defect. Scored only on good_practice fixtures, where by
# construction there is none to find.
# Deliberately does NOT include `Verdict: FAIL`. The verdict axis already scores
# that, and an overlapping probe made the two axes move together — calibration
# caught it, which is the point of running one decoy per axis. This axis scores
# invented defect *claims in prose*; the verdict axis scores the certification.
OVERFLAG_PROBES: tuple[tuple[str, str], ...] = (
    ("missing-ttl", r"\b(?:no|missing|absent|without)\s+(?:a\s+)?ttl\b|immortal key"),
    ("missing-stampede", r"\b(?:no|missing|without)\s+(?:a\s+)?(?:stampede|singleflight)"),
    ("missing-degradation", r"\b(?:no|missing|without)\s+(?:a\s+)?degradation"),
    ("missing-jitter", r"\b(?:no|missing|without)\s+(?:any\s+)?jitter"),
    ("missing-penetration", r"\b(?:no|missing|without)\s+(?:a\s+)?(?:penetration|null[- ]cach)"),
)

VERDICT_RE = re.compile(r"verdict\s*[:=]?\s*\**\s*(PASS|FAIL|INCOMPLETE)\b", re.I)


def clauses(text: str) -> list[str]:
    """Split on clause boundaries, including `;` — a rejection after a semicolon
    does not govern the claim before it."""
    return [c for c in re.split(r"[.;\n]|(?:\s—\s)", text) if c.strip()]


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------

@dataclass
class Score:
    recall: float = 0.0
    items: float = 0.0
    verdict: float = 0.0
    no_false_alarm: float = 1.0
    no_refuted: float = 1.0
    missed_concepts: list[str] = field(default_factory=list)
    missed_items: list[str] = field(default_factory=list)
    false_alarms: list[str] = field(default_factory=list)
    refuted: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, float]:
        return {a: getattr(self, a) for a in AXES}

    def total(self) -> float:
        return sum(self.as_dict().values()) / len(AXES)


def mentions(response: str, concept: str) -> bool:
    """Whole-token match, so `ttl` does not match `little` and `L1` does not
    match `l1nk`. Multi-word concepts are matched with flexible whitespace."""
    parts = [re.escape(w) for w in concept.lower().split()]
    return re.search(r"\b" + r"\s+".join(parts) + r"\b", response.lower()) is not None


def item_named(response: str, item_id: str, titles: dict[str, str]) -> bool:
    """Does the response cite the §5 item ID?

    ID citation only — deliberately no fallback to the item's title words. A
    title-keyword fallback was tried first and calibration rejected it: the
    titles are made of the same words as the fixture's `coverage_rules`, so the
    fallback made this axis a copy of `recall` and the items decoy could not
    move it. Two axes that always agree are one axis reported twice.

    Requiring the ID is also the behaviour §8 mandates — "every item gets a row,
    `| ID | Verdict | Evidence |`" — so this measures the contract, not a proxy.
    """
    return re.search(rf"\b{item_id}\b", response) is not None


def grade(response: str, fixture: dict, titles: dict[str, str]) -> Score:
    s = Score()
    low = response.lower()

    concepts = fixture["coverage_rules"]
    hit = [c for c in concepts if mentions(response, c)]
    s.missed_concepts = [c for c in concepts if c not in hit]
    s.recall = len(hit) / len(concepts) if concepts else 1.0

    ids = fixture["scorecard_items"]
    named = [i for i in ids if item_named(response, i, titles)]
    s.missed_items = [i for i in ids if i not in named]
    s.items = len(named) / len(ids) if ids else 1.0

    m = VERDICT_RE.search(response)
    verdict = m.group(1).upper() if m else None
    if fixture["type"] == "defect":
        # A defect must not be certified. INCOMPLETE is acceptable: the model may
        # legitimately lack the context to score, and saying so is not a miss.
        s.verdict = 1.0 if verdict in {"FAIL", "INCOMPLETE"} else 0.0
    else:
        s.verdict = 1.0 if verdict in {"PASS", "INCOMPLETE", None} else 0.0

    if fixture["type"] == "good_practice":
        s.false_alarms = [n for n, pat in OVERFLAG_PROBES if re.search(pat, low)]
        s.no_false_alarm = 0.0 if s.false_alarms else 1.0

    for name, pat in REFUTED_CLAIMS:
        for clause in clauses(response):
            if re.search(pat, clause, re.I) and not CLAUSE_REJECTION.search(clause):
                s.refuted.append(name)
                break
    s.no_refuted = 0.0 if s.refuted else 1.0
    return s


# ---------------------------------------------------------------------------
# corpus
# ---------------------------------------------------------------------------

def fixtures() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(GOLDEN.glob("*.json"))]


def corpus() -> list[dict]:
    return [f for f in fixtures() if f["type"] in {"defect", "good_practice"}]


def item_titles() -> dict[str, str]:
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    sec = re.search(r"^## §5\b.*?(?=^## §6\b)", text, re.S | re.M)
    if not sec:
        return {}
    return {f"{p}{n}": t for p, n, t in
            re.findall(r"^\*\*([CSH])(\d+) — ([^*]+?)\*\*", sec.group(0), re.M)}


# ---------------------------------------------------------------------------
# calibration -- one decoy per axis, offline
# ---------------------------------------------------------------------------

def synthetic(fix: dict, titles: dict[str, str], flaw: str | None) -> str:
    """A response that is perfect except for exactly one axis."""
    concepts = "" if flaw == "recall" else " ".join(fix["coverage_rules"])
    ids = "" if flaw == "items" else " ".join(fix["scorecard_items"])
    if flaw == "verdict":
        verdict = "PASS" if fix["type"] == "defect" else "FAIL"
    else:
        verdict = "FAIL" if fix["type"] == "defect" else "PASS"
    body = f"Review of {fix['id']}. Concepts: {concepts}. Items: {ids}."
    if flaw == "no_false_alarm":
        body += " This code has no TTL on the cached key."
    if flaw == "no_refuted":
        body += " Note that write-through gives strong consistency here."
    return f"{body}\nVerdict: {verdict}\n"


def calibrate(verbose: bool) -> int:
    titles = item_titles()
    if not titles:
        print("CANNOT CALIBRATE: SKILL.md §5 items did not parse", file=sys.stderr)
        return 1

    problems: list[str] = []
    checked = 0
    for fix in corpus():
        base = grade(synthetic(fix, titles, None), fix, titles).as_dict()

        # The clean response must max every axis that applies to this fixture.
        for axis, val in base.items():
            if axis == "no_false_alarm" and fix["type"] != "good_practice":
                continue
            if axis == "items" and not fix["scorecard_items"]:
                continue
            if val != 1.0:
                problems.append(f"{fix['id']}: clean response scores {axis}={val:.2f}, want 1.0")

        for axis in AXES:
            # An axis that cannot apply has no decoy: a good_practice fixture has
            # no items to name, and a defect fixture cannot raise a false alarm.
            if axis == "no_false_alarm" and fix["type"] != "good_practice":
                continue
            if axis == "items" and not fix["scorecard_items"]:
                continue
            got = grade(synthetic(fix, titles, axis), fix, titles).as_dict()
            checked += 1
            if got[axis] >= base[axis]:
                problems.append(
                    f"{fix['id']}: the {axis} decoy did not lower {axis} "
                    f"({base[axis]:.2f} → {got[axis]:.2f}) — that axis measures nothing")
            moved = [a for a in AXES if a != axis and got[a] != base[a]]
            if moved:
                problems.append(
                    f"{fix['id']}: the {axis} decoy also moved {moved} — "
                    f"the axes are not independent, so a deleted mechanism can hide")
            if verbose:
                print(f"  {fix['id']:<10} {axis:<15} {base[axis]:.2f} → {got[axis]:.2f}")

    print(f"calibration: {checked} axis probes over {len(corpus())} fixtures")
    for p in problems:
        print(f"  {p}")
    if problems:
        print(f"calibration FAILED: {len(problems)} problem(s)")
        return 1
    print("calibration: every axis separates, and only on its own decoy")
    return 0


# ---------------------------------------------------------------------------
# A/B run
# ---------------------------------------------------------------------------

REF_SETS = {
    "none": [],
    "default": ["cache-patterns.md", "cache-anti-examples.md"],
    "all": None,  # every reference
}


def build_prompt(fix: dict, with_skill: bool, refs: str) -> str:
    ctx = fix.get("context", {})
    head = [
        "Review the Redis caching code below.",
        f"Context: {json.dumps(ctx)}" if ctx else "",
        "",
        "```go",
        fix["code_snippet"],
        "```",
        "",
        "Report any problems, then end with a line `Verdict: PASS`, "
        "`Verdict: FAIL`, or `Verdict: INCOMPLETE`.",
    ]
    if not with_skill:
        return "\n".join(x for x in head if x != "")

    parts = [(SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")]
    names = sorted(p.name for p in REFS.glob("*.md")) if REF_SETS[refs] is None \
        else REF_SETS[refs]
    for n in names:
        parts.append(f"\n\n--- references/{n} ---\n\n"
                     + (REFS / n).read_text(encoding="utf-8"))
    return ("Apply the following skill.\n\n" + "\n".join(parts)
            + "\n\n---\n\n" + "\n".join(x for x in head if x != ""))


def ask(runner: list[str], prompt: str, timeout: int) -> str | None:
    """Run the model. Returns None on ANY failure.

    A non-zero exit returns None even when stdout is non-empty: a truncated or
    error-prefixed response is not a measurement, and scoring it silently
    credits the arm with whatever partial text happened to be flushed.
    """
    try:
        # The prompt goes on STDIN, never argv. Two reasons, both bit us:
        # `--disallowed-tools` is variadic and swallowed a trailing prompt as
        # tool names, and arm B's prompt (SKILL.md + references) is tens of
        # kilobytes, which is a plausible ARG_MAX failure on some systems.
        r = subprocess.run(runner, input=prompt, capture_output=True, text=True,
                           timeout=timeout, cwd=str(SKILL_DIR.parent))
    except (subprocess.TimeoutExpired, OSError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout if r.stdout.strip() else None


def runner_preflight(runner: list[str], timeout: int) -> str:
    """'' when the runner answers a trivial prompt, else why it did not.

    Same positive control as the Go gate. Without it, an unauthenticated or
    misconfigured CLI produces `NO RESPONSE` on every case and the run ends in a
    generic "no scored pairs" — technically INCOMPLETE, but with no clue that the
    cause was `Not logged in` rather than a corpus problem.
    """
    try:
        r = subprocess.run(runner, input="Reply with exactly: OK", capture_output=True,
                           text=True, timeout=min(timeout, 120), cwd=str(SKILL_DIR.parent))
    except (subprocess.TimeoutExpired, OSError) as e:
        return f"{type(e).__name__} invoking {runner[0]}"
    if r.returncode != 0 or not r.stdout.strip():
        return (r.stdout.strip() or r.stderr.strip() or f"exit {r.returncode}")[:300]
    return ""


def run_ab(runner: list[str], timeout: int, limit: int | None, refs: str) -> int:
    why = runner_preflight(runner, timeout)
    if why:
        print(f"INCOMPLETE: the model runner does not answer; nothing was measured.\n"
              f"  runner: {' '.join(runner)}\n  reason: {why}", file=sys.stderr)
        return 3
    titles = item_titles()
    cases = corpus()[:limit] if limit else corpus()
    rows: list[dict] = []
    for fix in cases:
        row: dict = {"id": fix["id"], "type": fix["type"]}
        for arm, with_skill in (("A", False), ("B", True)):
            resp = ask(runner, build_prompt(fix, with_skill, refs), timeout)
            if resp is None:
                row[arm] = None
                print(f"  {fix['id']} arm {arm}: NO RESPONSE (not scored)")
                continue
            s = grade(resp, fix, titles)
            row[arm] = s.as_dict() | {"total": s.total()}
            print(f"  {fix['id']} arm {arm}: total={s.total():.2f} "
                  f"recall={s.recall:.2f} items={s.items:.2f} verdict={s.verdict:.0f} "
                  f"fa={s.no_false_alarm:.0f} ref={s.no_refuted:.0f}")
        rows.append(row)

    scored = [r for r in rows if r.get("A") and r.get("B")]
    if not scored:
        print("INCOMPLETE: no case produced a scored pair", file=sys.stderr)
        return 3
    a = sum(r["A"]["total"] for r in scored) / len(scored)
    b = sum(r["B"]["total"] for r in scored) / len(scored)
    print(f"\narm A (no skill) {a:.3f} · arm B (skill+{refs}) {b:.3f} "
          f"· delta {b - a:+.3f} over {len(scored)}/{len(rows)} scored pairs")
    (SKILL_DIR / "scripts" / "tests" / "model_eval_last_run.json").write_text(
        json.dumps({"refs": refs, "arm_a": a, "arm_b": b, "rows": rows}, indent=2),
        encoding="utf-8")
    if b <= a:
        print("FAIL: the skill did not improve the review", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", action="store_true", help="offline grader check")
    ap.add_argument("--run", action="store_true", help="A/B against a model")
    ap.add_argument("--runner", default=DEFAULT_RUNNER)
    ap.add_argument("--refs", choices=sorted(REF_SETS), default="default")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if args.calibrate or not args.run:
        return calibrate(args.verbose)

    runner = args.runner.split()
    if shutil.which(runner[0]) is None:
        print(f"INCOMPLETE: `{runner[0]}` not found; the A/B arm did NOT run. "
              "This is not a pass.", file=sys.stderr)
        return 3
    return run_ab(runner, args.timeout, args.limit, args.refs)


if __name__ == "__main__":
    sys.exit(main())

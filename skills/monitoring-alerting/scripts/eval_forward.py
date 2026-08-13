#!/usr/bin/env python3
"""Forward behavioural evaluation: does an agent USING this skill answer better than one without?

Everything else in `scripts/` judges the skill's **text**. This judges the **behaviour** the
text produces, which is the only thing that answers "does the skill work". It is the last
open item from the 2026-08-12 reviews.

    python3 scripts/eval_forward.py --self-test     # grade the grader (no model needed)
    python3 scripts/eval_forward.py --run           # run the eval (needs an authenticated CLI)
    python3 scripts/eval_forward.py --grade DIR     # grade previously recorded outputs

## Running it

`--self-test` needs nothing and always runs. `--run` needs an authenticated `claude` CLI.

**If `--run` reports `Not logged in`, the cause is almost certainly a sandbox, not your
login.** Claude Code's own tool sandbox denies reads of `~/.claude/.credentials.json`, so a
nested `claude -p` launched from inside a sandboxed shell cannot authenticate no matter which
directory it runs in. Run it from an unsandboxed shell (in Claude Code: `/sandbox`, or a plain
terminal). That one fact cost a full round of "the harness is delivered but unrunnable".

Each fixture runs twice:

- **with_skill** — the prompt points at this skill's directory and the model may read files.
- **without_skill** — `--tools ""`, so the model must answer from priors.

The second arm is the null hypothesis: "the model already knew that" is what a skill has to
beat. A criterion both arms pass is not a win, it is a criterion that is too easy, and
`--grade` labels it UNINFORMATIVE rather than counting it.

## Why per-criterion, not a similarity score

Grading free-text answers by string similarity to `expected_feedback` measures phrasing, not
correctness. Each fixture is instead scored against **named criteria**, each a callable that
inspects structure: does the answer name the missing SLI, does it compute the burn rate
correctly, does it avoid asserting a vendor mapping as a rule. A criterion returns
(passed, evidence) so a report can be read without re-reading the transcripts.

The `without_skill` arm exists because "the model already knew that" is the null hypothesis a
skill has to beat. A criterion that both arms pass is not evidence the skill works; it is
evidence the criterion is too easy. `--grade` reports the **delta**, and flags criteria with
zero delta as uninformative rather than counting them as wins.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
GOLDEN = sorted((SKILL_DIR / "scripts" / "tests" / "golden").glob("*.json"))


# ─────────────────────────────── criteria ───────────────────────────────
# Each is (name, predicate) where predicate(answer_text) -> (bool, evidence str).
# Structure and values, never keywords: the whole point of this file is to check behaviour,
# and "the word burn appears" is satisfied by a wrong burn-rate figure.

def _burn_rate_arithmetic_ok(text):
    """No claim that a double-digit burn rate exhausts a 30-day budget in a few hours."""
    bad = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*x[^.\n]{0,70}?exhaust\w*[^.\n]{0,30}?"
                         r"in\s*~?\s*(\d+(?:\.\d+)?)\s*(h|hours?|d|days?)", text, re.I):
        rate = float(m.group(1))
        hrs = float(m.group(2)) * (24 if m.group(3).lower().startswith("d") else 1)
        want = 720 / rate
        if abs(hrs - want) > 0.15 * want:
            bad.append(f"{rate}x -> claimed {m.group(2)}{m.group(3)}, correct ~{want:.0f}h")
    return (not bad, "; ".join(bad) or "no incorrect exhaustion claim")


def _names_missing_sli(text):
    hit = re.search(r"\bSLI\b", text) and re.search(
        r"availability|error rate|latency|success ratio", text, re.I)
    return (bool(hit), "names SLI + a concrete indicator" if hit else "no SLI discussion")


def _requires_runbook(text):
    hit = re.search(r"runbook", text, re.I)
    return (bool(hit), "mentions runbook" if hit else "runbook never mentioned")


def _for_duration_reasoning(text):
    """Distinguishes debouncing from a blanket rule, and does not exempt `up == 0`."""
    wrong = re.search(r"up\s*==\s*0[^.\n]{0,80}(?:no need for|does not need|without)\s*`?for`?",
                      text, re.I)
    reasons = re.search(r"\bfor\b[^.\n]{0,60}(?:flap|transient|sustain|debounce)", text, re.I)
    if wrong:
        return (False, f"exempts up==0 from for: {wrong.group(0)[:70]!r}")
    return (bool(reasons), "reasons about damping" if reasons else "no `for` reasoning")


def _no_vendor_rule(text):
    bad = re.search(r"(?:must|always|required to)\s+(?:page |route |go )?(?:via |to |through )?"
                    r"pagerduty", text, re.I)
    return (not bad, f"states vendor as requirement: {bad.group(0)!r}" if bad
            else "no vendor mapping asserted as a rule")


#: Clause delimiters, shared with the doc linter's reasoning. A +/-N character window is
#: not a scope: this criterion first shipped with a 120-char window and produced a false
#: REGRESSION verdict on a real run -- it matched "2-3min diagnosis delay per incident" and
#: found the word "budget" in a different table row 120 characters away. A grader that
#: reports the skill made the model *worse* on evidence like that is worse than no grader.
_CLAUSE_CUT = re.compile(r"\s--\s|\s—\s|[;:,|]|\.\s|\n")


def _clause_around(text, start, end):
    lo = 0
    for m in _CLAUSE_CUT.finditer(text, 0, start):
        lo = m.end()
    hi = len(text)
    m = _CLAUSE_CUT.search(text, end)
    if m:
        hi = m.start()
    return text[lo:hi]


def _states_budget_basis(text):
    """If it quotes an error budget in minutes, the same clause must state the basis."""
    for m in re.finditer(r"\d+(?:\.\d+)?\s*(?:minutes?|min)\b", text):
        seg = _clause_around(text, m.start(), m.end())
        if not re.search(r"budget|allowed", seg, re.I):
            continue
        if not re.search(r"time-based|request-based|uniform traffic", seg, re.I):
            return (False, f"unlabelled budget minutes: {seg.strip()[:90]!r}")
    return (True, "no unlabelled minutes budget")


def _no_absolute_counter_threshold(text):
    bad = re.search(r"expr:[^\n]*\b\w+_total\s*[<>]=?\s*\d", text)
    return (not bad, f"raw counter threshold: {bad.group(0)[:60]!r}" if bad
            else "no raw counter threshold")


def _up_zero_not_auto_critical(text):
    """A single-instance `up == 0` must not be labelled critical without a redundancy reason.

    Added after the first real forward eval: the answer correctly explained that `up` is
    telemetry rather than customer impact, and then set `up{job=...} == 0` to
    `severity: critical` on the platform on-call in the same breath. Knowing the principle and
    applying it are different things, and only a behavioural check separates them.
    """
    for m in re.finditer(r"up\s*(?:\{[^}]*\})?\s*==\s*0", text):
        window = text[m.start():m.start() + 400]
        if not re.search(r"severity:\s*critical", window):
            continue
        justified = re.search(r"all\s+replicas|no\s+redundanc|single[- ]instance|"
                              r"single[- ]replica|synthetic|probe|\b\d+\s*/\s*\d+\s+replicas",
                              window, re.I)
        if not justified:
            return (False, f"up==0 -> severity: critical with no redundancy justification: "
                           f"{window[:90]!r}")
    return (True, "no unjustified critical on up==0")


def _no_unjustified_severity_when_topology_unknown(text):
    """With redundancy unstated, the answer must ask or answer conditionally -- not just page.

    The discriminating version of `up_zero_not_auto_critical`. That one ties in both arms
    because MON-014's context supplies the replica count, handing over the deciding fact. Here
    it is withheld, so the criterion measures judgement rather than reading comprehension.
    """
    # Third false verdict produced by my own criteria in this harness, so the patterns are now
    # written against a REAL good answer rather than guessed. The first version reported this
    # failing in BOTH arms; the with-skill answer actually said "You haven't stated the
    # deployment topology", gave the conditional ("If checkout has 6 replicas..."), and split
    # the rule into an all-down critical plus a partial-outage warning. Two mistakes:
    #   * "haven't stated" / "not specified" were not in the ask-or-condition patterns;
    #   * `severity: critical` was read as a defect, but a critical on an ALL-DOWN alert is
    #     exactly right -- the criterion must look at what the critical is attached to.
    # Rule of thumb this cost twice: when a criterion fails in BOTH arms, suspect the criterion
    # before the model.
    asks_or_conditions = re.search(
        r"how many replicas|replica count|depends on|topology (?:is )?(?:not|un)"
        r"|(?:have|has)n.t (?:been )?(?:stated|specified|said)|not (?:stated|specified|given)"
        r"|unstated|unspecified|cannot be decided|need to know|unknown"
        r"|if .{0,60}(?:replica|instance|single)"
        r"|single[- ](?:replica|instance)", text, re.I)

    # A critical attached to an all-replicas-down condition is correct, not a defect.
    unjustified_critical = False
    for m in re.finditer(r"severity:\s*critical", text, re.I):
        window = text[max(0, m.start() - 420):m.start()]
        if re.search(r"all .{0,20}(?:down|gone|unavailable)|sum\(up|absent\(up|total (?:loss|outage)"
                     r"|single[- ](?:replica|instance)|synthetic|probe", window, re.I):
            continue                      # justified: this critical is the all-down page
        unjustified_critical = True

    if unjustified_critical and not asks_or_conditions:
        return (False, "keeps severity critical on a per-instance alert without asking about, "
                       "or conditioning on, redundancy")
    return (bool(asks_or_conditions),
            "asks or conditions on redundancy" if asks_or_conditions
            else "neither asks nor conditions on redundancy")


def _latency_sli_is_a_ratio(text):
    """The SLI must be a proportion-under-threshold, not a percentile value."""
    ratio = re.search(r"_bucket\{[^}]*le=|proportion of (?:valid )?(?:requests|searches)|"
                      r"ratio of requests (?:faster|under|below)", text, re.I)
    percentile_as_sli = re.search(
        r"(?:SLI|SLO)[^.\n]{0,80}histogram_quantile|histogram_quantile[^.\n]{0,60}(?:as|is) the (?:SLI|SLO)",
        text, re.I)
    if percentile_as_sli and not ratio:
        return (False, f"defines the SLI as a percentile: {percentile_as_sli.group(0)[:70]!r}")
    return (bool(ratio), "defines a bucket ratio" if ratio else "no proportion-based SLI found")


def _names_valid_events(text):
    """Says which events are VALID -- the exclusions the base model routinely omits."""
    hit = re.search(r"\bvalid\b[^.\n]{0,80}(?:exclude|exclusion|health|/metrics|cancel)|"
                    r"(?:exclude|excluding)[^.\n]{0,60}(?:health|/metrics|cancel)", text, re.I)
    return (bool(hit), "names the valid-event exclusions" if hit
            else "never says which events count as valid")


def _empty_vector_safe_all_down(text):
    """If it proposes an all-instances-down alert, it must not use the empty-vector form."""
    broken = re.search(r"count\s*\([^)]*==\s*1[^)]*\)\s*==\s*0", text)
    if broken:
        return (False, f"uses the silent form: {broken.group(0)[:60]!r}")
    return (True, "no aggregation-over-empty-vector all-down form")


CRITERIA = {
    "asks_when_topology_unknown": _no_unjustified_severity_when_topology_unknown,
    "latency_sli_is_a_ratio": _latency_sli_is_a_ratio,
    "names_valid_events": _names_valid_events,
    "empty_vector_safe": _empty_vector_safe_all_down,
    "up_zero_not_auto_critical": _up_zero_not_auto_critical,
    "burn_rate_arithmetic": _burn_rate_arithmetic_ok,
    "names_sli": _names_missing_sli,
    "requires_runbook": _requires_runbook,
    "for_duration_reasoning": _for_duration_reasoning,
    "no_vendor_rule": _no_vendor_rule,
    "states_budget_basis": _states_budget_basis,
    "no_absolute_counter": _no_absolute_counter_threshold,
}

#: fixture id -> criteria that fixture should exercise
FIXTURE_CRITERIA = {
    "MON-001": ["names_sli", "requires_runbook"],
    "MON-004": ["for_duration_reasoning"],
    # MON-014 exists to elicit the behaviour: a single-replica up==0 already labelled
    # critical. The criterion was UNINFORMATIVE against MON-004 because that fixture never
    # mentions `up`, so both arms passed trivially -- a criterion with no fixture that
    # provokes it measures nothing.
    "MON-014": ["up_zero_not_auto_critical", "for_duration_reasoning", "empty_vector_safe"],
    # The HARD pair: context deliberately withholds the deciding fact (MON-015) and asks for a
    # latency SLO, which the base model reliably answers with a percentile (MON-016).
    "MON-015": ["asks_when_topology_unknown", "for_duration_reasoning", "empty_vector_safe"],
    "MON-016": ["latency_sli_is_a_ratio", "names_valid_events"],
    "MON-005": ["requires_runbook"],
    "MON-007": ["burn_rate_arithmetic", "states_budget_basis", "no_vendor_rule"],
    "MON-013": ["burn_rate_arithmetic", "states_budget_basis"],
    "MON-002": ["requires_runbook", "no_absolute_counter"],
}

PROMPT = """You are reviewing a monitoring/alerting setup. Give your findings and the fix.

Context: {context}

Input:
{snippet}
"""


def build_prompt(fx):
    return PROMPT.format(context=json.dumps(fx.get("context", {})),
                         snippet=fx.get("code_snippet", ""))


def run_arm(fx, with_skill, model, cwd, timeout=600, max_turns=12):
    """One `claude -p` call. Returns (ok, text)."""
    prompt = build_prompt(fx)
    if with_skill:
        prompt = (f"Use the monitoring-alerting skill at {SKILL_DIR} — read its SKILL.md and "
                  f"the references it routes you to — then answer.\n\n" + prompt)
    # --max-turns is not optional. The with_skill arm needs tools to read the skill, and an
    # unbounded agentic loop launched inside a repo with SessionStart hooks and a large tree
    # can run for tens of minutes per fixture -- observed as an apparent hang with no output.
    # Bounding turns is what makes the eval finish; the arm still gets enough turns to read
    # SKILL.md and the references it routes to.
    cmd = ["claude", "-p", "--model", model, "--permission-mode", "dontAsk",
           "--strict-mcp-config", "--max-turns", str(max_turns)]
    if not with_skill:
        cmd += ["--tools", ""]          # no file access: the arm must answer from priors
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                              timeout=timeout, cwd=cwd)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"HARNESS ERROR: {exc}"
    if proc.returncode != 0 or "Not logged in" in (proc.stdout + proc.stderr):
        return False, f"HARNESS ERROR: {(proc.stdout + proc.stderr)[:300]}"
    return True, proc.stdout


def grade_answer(fx, text):
    out = {}
    for name in FIXTURE_CRITERIA.get(fx["id"], []):
        passed, evidence = CRITERIA[name](text)
        out[name] = {"passed": passed, "evidence": evidence}
    return out


def grade_dir(outdir):
    """Grade recorded outputs: <dir>/<id>.with.md and <dir>/<id>.without.md."""
    d = Path(outdir)
    rows, missing, harness_errors = [], [], []
    for path in GOLDEN:
        fx = json.loads(path.read_text(encoding="utf-8"))
        if fx["id"] not in FIXTURE_CRITERIA:
            continue
        w, wo = d / f"{fx['id']}.with.md", d / f"{fx['id']}.without.md"
        if not w.exists() or not wo.exists():
            missing.append(fx["id"])
            continue
        wt, wot = w.read_text(encoding="utf-8"), wo.read_text(encoding="utf-8")
        for t, arm in ((wt, "with"), (wot, "without")):
            if t.startswith("HARNESS ERROR"):
                harness_errors.append(f"{fx['id']}/{arm}")
        rows.append((fx["id"], grade_answer(fx, wt), grade_answer(fx, wot)))

    if harness_errors:
        # A harness failure is not a model result. Reporting it as a loss (or a win) is the
        # error this repo keeps relearning: an error is only evidence if it is the error you
        # predicted.
        print(f"INCOMPLETE — harness errors in: {', '.join(harness_errors)}")
        return 3
    if missing:
        print(f"INCOMPLETE — no recorded output for: {', '.join(missing)}")
        return 3
    if not rows:
        print("INCOMPLETE — nothing to grade")
        return 3

    print(f"{'fixture':10s} {'criterion':24s} {'with':>6s} {'without':>8s}  verdict")
    deltas = {}
    for fid, wg, wog in rows:
        for name in wg:
            a, b = wg[name]["passed"], wog[name]["passed"]
            deltas.setdefault(name, []).append((a, b))
            verdict = ("skill wins" if a and not b else
                       "skill loses" if b and not a else
                       "tie")
            print(f"{fid:10s} {name:24s} {str(a):>6s} {str(b):>8s}  {verdict}")
            if not a:
                print(f"{'':10s} {'':24s} evidence: {wg[name]['evidence'][:90]}")

    print()
    uninformative = [n for n, v in deltas.items() if all(a == b for a, b in v)]
    regressions = [n for n, v in deltas.items() if any(b and not a for a, b in v)]
    if uninformative:
        print(f"UNINFORMATIVE (both arms identical, criterion too easy or too hard): "
              f"{', '.join(uninformative)}")
    if regressions:
        print(f"REGRESSION (without-skill did better): {', '.join(regressions)}")
        return 1
    wins = [n for n, v in deltas.items() if any(a and not b for a, b in v)]
    print(f"PASS — skill improved: {', '.join(wins) or 'nothing measurable'}; "
          f"no regressions")
    return 0 if wins else 2


# ─────────────────────────── grading the grader ───────────────────────────
_GOOD = """Findings. The SLO is 99.9% over 30 days; the error budget is 0.1% of valid
requests (request-based), which is ~43.2 minutes only as a request-based approximation under
uniform traffic. Burn rate 14.4x spends 2% of the budget per hour and would exhaust it in
~50h if sustained. Availability SLI: good/valid with health checks excluded. Every alert needs
a runbook_url. `for` absorbs transient spikes; note `up == 0` is true after one failed scrape
so it still needs for: 5m. Route by the org's own severity mapping.
"""

_BAD = """Findings. Burn rate 14.4x will exhaust the 30-day budget in 2 hours. The error
budget is 43.2 minutes/month of allowed downtime. Add:
  - alert: Errors
    expr: http_errors_total > 10
Critical alerts must page via PagerDuty. `up == 0` does not need `for` since it is a deadman.
"""

SELF_TEST = [
    ("good answer: burn-rate arithmetic", "burn_rate_arithmetic", _GOOD, True),
    ("bad answer: burn-rate arithmetic", "burn_rate_arithmetic", _BAD, False),
    ("good answer: budget basis stated", "states_budget_basis", _GOOD, True),
    ("bad answer: unlabelled minutes", "states_budget_basis", _BAD, False),
    ("good answer: runbook required", "requires_runbook", _GOOD, True),
    ("bad answer: no runbook", "requires_runbook", _BAD, False),
    ("good answer: no vendor rule", "no_vendor_rule", _GOOD, True),
    ("bad answer: vendor as requirement", "no_vendor_rule", _BAD, False),
    ("good answer: up==0 keeps for", "for_duration_reasoning", _GOOD, True),
    ("bad answer: up==0 exempted", "for_duration_reasoning", _BAD, False),
    ("good answer: no raw counter", "no_absolute_counter", _GOOD, True),
    ("bad answer: raw counter threshold", "no_absolute_counter", _BAD, False),
    ("good answer: names SLI", "names_sli", _GOOD, True),
    # --- the hard criteria, both directions ---
    ("asks about topology instead of paging", "asks_when_topology_unknown",
     "Severity cannot be decided here: it depends on how many replicas are behind the load "
     "balancer. How many are there?\n", True),
    ("keeps critical with topology unstated", "asks_when_topology_unknown",
     "- alert: InstanceDown\n  labels:\n    severity: critical\n  # instance is down\n", False),
    # verbatim shape of the real with-skill answer that the first version wrongly failed
    ("real answer: names the missing topology and conditions on it", "asks_when_topology_unknown",
     "### Severity `critical` without redundancy headroom information\n"
     "You haven't stated the deployment topology. If checkout has 6 replicas, firing "
     "`critical` on 1 down violates the severity contract.\n\n"
     "- alert: CheckoutAllDown\n  expr: sum(up{job=\"checkout\"}) == 0 or "
     "absent(up{job=\"checkout\"})\n  labels:\n    severity: critical\n", True),
    ("latency SLI as a bucket ratio", "latency_sli_is_a_ratio",
     'sum(rate(d_seconds_bucket{le="0.4"}[5m])) / sum(rate(d_seconds_count[5m]))', True),
    ("latency SLI as a percentile", "latency_sli_is_a_ratio",
     "The SLI is histogram_quantile(0.99, rate(d_seconds_bucket[5m])) > 0.4", False),
    ("names the valid-event exclusions", "names_valid_events",
     "valid events exclude health checks, /metrics and client-cancelled requests", True),
    ("never defines valid events", "names_valid_events",
     "Availability is successful requests over total requests.", False),
    ("all-down alert avoids the empty-vector form", "empty_vector_safe",
     'sum(up{job="x"}) == 0 or absent(up{job="x"})', True),
    ("all-down alert uses the silent form", "empty_vector_safe",
     'count(up{job="x"} == 1) == 0', False),
    ("up==0 critical justified by lost redundancy is fine", "up_zero_not_auto_critical",
     "- alert: AllReplicasDown\n  expr: up{job=\"api\"} == 0\n  labels:\n    "
     "severity: critical\n  # all replicas down, no redundancy left\n", True),
    ("up==0 critical with no justification is caught", "up_zero_not_auto_critical",
     "- alert: InstanceDown\n  expr: up{job=\"api\"} == 0\n  labels:\n    "
     "severity: critical\n  annotations:\n    summary: 'instance is down'\n", False),
    # regression guard: a diagnosis-delay figure in one table row with the word "budget"
    # in another must NOT read as an unlabelled error budget
    ("unrelated minutes in a nearby row is not a budget claim", "states_budget_basis",
     "| runbook is generic | LOW: 2-3min diagnosis delay per incident |\n"
     "| Error budget math | correct |\n", True),
    ("bad answer: never names an SLI", "names_sli", _BAD, False),
]


def self_test():
    bad = 0
    for label, crit, text, want in SELF_TEST:
        got, evidence = CRITERIA[crit](text)
        if got != want:
            bad += 1
            print(f"[error] {label}: expected {want}, got {got} ({evidence})")
    # every criterion must appear in at least one fixture mapping, or it grades nothing
    mapped = {c for cs in FIXTURE_CRITERIA.values() for c in cs}
    for name in CRITERIA:
        if name not in mapped:
            bad += 1
            print(f"[error] criterion {name!r} is defined but no fixture uses it")
    # and every criterion must be exercised in BOTH directions here, or a one-sided
    # criterion can be trivially true and look like a check
    for name in CRITERIA:
        dirs = {w for _, c, _, w in SELF_TEST if c == name}
        if dirs != {True, False}:
            bad += 1
            print(f"[error] criterion {name!r} is only self-tested for {dirs}; "
                  f"a criterion that is never shown to FAIL is not a check")
    n = len(SELF_TEST)
    if bad:
        print(f"eval_forward self-test: FAILED ({bad} issue(s), {n} fixtures)")
        return 1
    print(f"eval_forward self-test: {n}/{n} criteria fixtures graded correctly; "
          f"{len(CRITERIA)} criteria, each exercised in both directions")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--grade", metavar="DIR")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--max-turns", type=int, default=12,
                    help="bound the agentic loop; without this the with-skill arm can run "
                         "for tens of minutes per fixture and look like a hang")
    ap.add_argument("--timeout", type=int, default=600,
                    help="per-call seconds; a with-skill arm reads several files")
    ap.add_argument("--out", default="eval_out")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if args.grade:
        return grade_dir(args.grade)
    if args.run:
        outdir = Path(args.out)
        outdir.mkdir(parents=True, exist_ok=True)
        neutral = outdir.resolve()          # neutral cwd: no project CLAUDE.md inherited
        for path in GOLDEN:
            fx = json.loads(path.read_text(encoding="utf-8"))
            if fx["id"] not in FIXTURE_CRITERIA:
                continue
            for with_skill, suffix in ((True, "with"), (False, "without")):
                print(f"  {fx['id']} {suffix}: running...", flush=True)
                t0 = time.monotonic()
                ok, text = run_arm(fx, with_skill, args.model, neutral, args.timeout,
                                   args.max_turns)
                (outdir / f"{fx['id']}.{suffix}.md").write_text(text, encoding="utf-8")
                print(f"  {fx['id']} {suffix}: {'ok' if ok else 'HARNESS ERROR'} "
                      f"({time.monotonic() - t0:.0f}s, {len(text)} chars)", flush=True)
        return grade_dir(outdir)
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())

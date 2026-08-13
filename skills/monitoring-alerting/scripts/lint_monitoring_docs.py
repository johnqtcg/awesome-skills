#!/usr/bin/env python3
"""Semantic lint for this skill's docs and golden fixtures.

Why this exists. Until 2026-08-12 every test here was a keyword check — "does the word
`burn` appear", "does `runbook` appear". That kind of assertion is green whether the
surrounding claim is right or wrong, and it let a real domain error ship: the docs said a
14.4x burn rate "exhausts a 30-day budget in 2 hours" (it takes ~50 hours), and the golden
fixture asserting "No violations" made the wrong number the expected answer. A keyword
test cannot catch a wrong number, because the keyword is still there.

So these rules check **values and structure**, not vocabulary:

  MA001  a "N% of budget" claim equals burn_rate x window / slo_window
  MA002  a "exhausts in T" claim equals slo_window / burn_rate
  MA003  multi-window tiers use a short window of ~1/12 the long window
  MA004  no deprecated Alertmanager matcher form outside a deliberate WRONG block
  MA005  every alert rule outside a WRONG block carries annotations.runbook_url
  MA006  no absolute-counter threshold outside a WRONG block (must use rate/increase)
  MA007  severity -> destination is not restated as a universal requirement
  MA008  `for` is not restated as mandatory on every alert
  MA009  `up == 0` is never listed as legitimately omitting `for`
  MA010  a downtime-minutes figure carries its SLO basis (time-based vs request-based)
  MA011  the latency SLI is a proportion-under-threshold, not a bare percentile
  MA012  markdown tables have a consistent column count
  MA013  a good_practice fixture states the basis of any minutes budget it quotes
  MA014  a good_practice fixture defines valid/good events, not a bare non-5xx/total
  MA015  availability and error-rate expressions use the same event set (no selector drift)
  MA016  a stated "consumed N% of budget" matches burn_rate x hours / slo_window
  MA017  every sli:* recording rule in one group shares the same label selector
  MA018  prose about the latency denominator agrees with what the recording rules use
  MA019  no fixture recommends paging on a budget *level* with no active burn
  MA020  no "all instances down" alert uses an aggregation-over-empty-vector form

Scope note: MA001/MA002/MA013/MA016 run over **golden fixtures of every type**, and
MA014/MA015 over model answers, not just the docs.
A `good_practice` fixture whose `expected_feedback` is "No violations" *is* the model answer,
so a defect there is worse than one in prose -- it trains the wrong conclusion. Applying the
rules only to documentation is how MON-007 kept an unlabelled request-vs-time budget and a
bare `non-5xx / total` after both had been corrected everywhere else.

Usage:
  python3 scripts/lint_monitoring_docs.py            # lint the skill
  python3 scripts/lint_monitoring_docs.py --self-test  # grade the linter on known inputs
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
DOCS = [SKILL_DIR / "SKILL.md", *sorted((SKILL_DIR / "references").glob("*.md"))]
GOLDEN = sorted((SKILL_DIR / "scripts" / "tests" / "golden").glob("*.json"))

SLO_WINDOW_HOURS = 30 * 24  # this skill's worked examples all use a 30-day SLO window
TOLERANCE = 0.15            # claims are rounded in prose ("~50h", "5 days")

UNIT_HOURS = {"s": 1 / 3600, "m": 1 / 60, "h": 1.0, "d": 24.0}


def dur_hours(value: float, unit: str) -> float:
    return value * UNIT_HOURS[unit[0].lower()]


# ─────────────────────────── anti-example detection ───────────────────────────
# A fenced block that deliberately demonstrates a defect must be exempt from the
# "emit only modern, complete config" rules -- otherwise the rules fire on the very
# examples that teach what not to do. Detection is structural (a marker inside the
# block, or an anti-example heading above it), never a fuzzy keyword window.
#
# BUT the exemption must be per-HALF, not per-block. Every AE block in SKILL.md is a
# WRONG/RIGHT pair in one fence, and treating the whole fence as an anti-example exempted
# the RIGHT half too -- so the corrected examples the reader is told to copy were the only
# alert rules in the skill with no runbook/severity enforcement at all. Splitting on the
# markers is what makes "exempt the bad example, enforce the good one" expressible.
WRONG_IN_BLOCK = re.compile(r"^\s*#\s*(WRONG|BAD|ANTI)", re.M | re.I)
ANTI_HEADING = re.compile(r"^#{2,4}\s+(AE-\d+|.*anti-?example)", re.I)
HALF_MARKER = re.compile(r"^\s*#\s*(WRONG|BAD|ANTI|RIGHT|GOOD|CORRECT)\b", re.M | re.I)
BAD_MARKERS = {"WRONG", "BAD", "ANTI"}


def split_halves(body):
    """Split a WRONG/RIGHT demonstration block into (is_anti_example, text) segments.

    A block with no marker at all yields a single segment whose verdict is None, so the
    caller applies the block-level decision (heading-based) to it unchanged.
    """
    marks = list(HALF_MARKER.finditer(body))
    if not marks:
        return [(None, body)]
    out = []
    if marks[0].start() > 0:
        out.append((None, body[:marks[0].start()]))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        out.append((m.group(1).upper() in BAD_MARKERS, body[m.start():end]))
    return out


def fenced_blocks(text: str):
    """Yield (lang, body, heading, is_anti_example, start_line)."""
    lines = text.split("\n")
    heading, i = "", 0
    while i < len(lines):
        ln = lines[i]
        if re.match(r"^#{1,6}\s+", ln):
            heading = ln
        m = re.match(r"^[ \t]*```([A-Za-z0-9_+-]*)[ \t]*$", ln)
        if m:
            lang, start, buf = m.group(1).lower(), i + 1, []
            i += 1
            while i < len(lines) and not re.match(r"^[ \t]*```[ \t]*$", lines[i]):
                buf.append(lines[i])
                i += 1
            body = "\n".join(buf)
            anti = bool(WRONG_IN_BLOCK.search(body)) or bool(ANTI_HEADING.match(heading))
            yield lang, body, heading, anti, start
        i += 1


# ─────────────────────────────── the rules ───────────────────────────────
#: "burn rate 14.4x — 2% of the 30-day budget spent in 1h"
PCT_CLAIM = re.compile(
    r"burn[- ]?rate[^\n.]{0,24}?(\d+(?:\.\d+)?)\s*x?[^\n.]{0,60}?"
    r"(\d+(?:\.\d+)?)\s*%[^\n.]{0,40}?budget[^\n.]{0,40}?(?:in|over|per)\s*"
    r"(\d+(?:\.\d+)?)\s*(h|hours?|m|minutes?|d|days?)\b", re.I)

#: "exhausts in ~50h", "will exhaust 30-day budget in 2 hours"
EXHAUST_CLAIM = re.compile(
    r"(\d+(?:\.\d+)?)\s*x?[^\n.]{0,80}?exhaust\w*[^\n.]{0,40}?"
    r"(?:in|within)\s*~?\s*(\d+(?:\.\d+)?)\s*(h|hours?|m|minutes?|d|days?)\b", re.I)

#: Markers that make a clause a REFUTATION of the numeric claim rather than an assertion
#: of it. Deliberately a short, specific list rather than bare "not": the docs must be
#: able to quote the wrong number in order to correct it ("14.4 is *not* 'exhausts in 2
#: hours'"), but a generic negation elsewhere in the sentence must not excuse a genuine
#: mistake. Every pre-fix defect sentence is kept in SELF_TEST_CASES precisely so this
#: exemption is proved not to be a bypass.
#:
#: The matched span is NOT masked before scanning here, unlike most refutation guards --
#: the claim regex spans the negation itself ("14.4 is not \"exhausts ... in 2 hours\""),
#: so masking would delete the very marker that makes the sentence correct. The tight
#: marker list is what keeps that safe.
CLAIM_REFUTED = (
    "is not", "are not", "would be wrong", "is wrong", "was wrong", "incorrect",
    "off by", "order of magnitude", "not the same", "do not confuse", "never say",
    "sanity check", "wrong by",
)

_CLAUSE_SPLIT = re.compile(r"(?:\n\n|(?<=[.;!?])\s)")


#: Clause delimiters for "the basis must be next to the number". A sentence is too wide:
#: "the budget is 0.1% of valid requests -- and ~43.2 minutes of allowed downtime" would be
#: excused by the *first* clause while the minutes clause carries no basis at all. Third time
#: this shape has bitten in this skill, hence the shared helper.
CLAUSE_CUT = re.compile(r"\s--\s|\s—\s|[;:,]|\.\s")


def clause_around(text, start, end):
    """The clause containing [start, end), cut at -- / — / ; : , / sentence end."""
    lo = 0
    for m in CLAUSE_CUT.finditer(text, 0, start):
        lo = m.end()
    hi = len(text)
    m = CLAUSE_CUT.search(text, end)
    if m:
        hi = m.start()
    return text[lo:hi]


def claim_is_refuted(text, span):
    """True when the clause containing `span` rejects the claim instead of asserting it."""
    start, end = span
    lo = max(text.rfind("\n\n", 0, start), 0)
    seg = text[lo:end + 200]
    # keep only the clause the match sits in, so a refutation two sentences away
    # cannot excuse this one
    pieces, pos = [], lo
    for part in _CLAUSE_SPLIT.split(seg):
        nxt = pos + len(part)
        if pos <= start <= nxt + 2:
            pieces.append(part)
        pos = nxt + 1
    clause = (" ".join(pieces) or seg).lower()
    return any(mk in clause for mk in CLAIM_REFUTED)


DEPRECATED_MATCHER = re.compile(r"^\s*-?\s*(match|match_re|source_match|source_match_re|"
                                r"target_match|target_match_re)\s*:", re.M)

#: PromQL functions that turn a monotonic counter into a per-second/interval value.
#: A counter compared directly to a constant is AE-1 ("fires when 10 errors exist,
#: even if they accumulated over 24 hours").
RATE_FUNCS = ("rate", "irate", "increase", "delta", "idelta", "resets")


def strip_rate_calls(expr: str) -> str:
    """Remove the *contents* of rate()-family calls, keeping the rest of the expression.

    Needed because a naive "does the expression mention rate() anywhere" test passes as
    soon as ANY subexpression is rated -- which is exactly how the first version of MA006
    missed a mutation that left a bare counter in the numerator while the denominator
    stayed wrapped in rate(). Balanced-paren scanning is the only way to ask the real
    question: is *this* counter reference rated?
    """
    out, i = [], 0
    while i < len(expr):
        m = re.compile(r"\b(" + "|".join(RATE_FUNCS) + r")\s*\(").match(expr, i)
        if not m:
            out.append(expr[i])
            i += 1
            continue
        depth, j = 0, m.end() - 1
        while j < len(expr):
            if expr[j] == "(":
                depth += 1
            elif expr[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out.append(" ")            # placeholder: the call existed but is consumed
        i = j + 1
    return "".join(out)


COUNTER_REF = re.compile(r"\b\w+_total\b")
COMPARISON = re.compile(r"[<>]=?|==")


def lint_docs():
    errors = []

    for path in DOCS:
        text = path.read_text(encoding="utf-8")
        rel = path.name

        # ---- MA001: percentage-of-budget claims ----
        for m in PCT_CLAIM.finditer(text):
            rate, pct, win, unit = (float(m.group(1)), float(m.group(2)),
                                    float(m.group(3)), m.group(4))
            want = rate * dur_hours(win, unit) / SLO_WINDOW_HOURS * 100
            if abs(want - pct) > max(TOLERANCE * want, 0.05) and \
                    not claim_is_refuted(text, m.span()):
                errors.append(
                    f"[MA001] {rel}: burn rate {rate} over {win}{unit} spends "
                    f"{want:.2f}% of a {SLO_WINDOW_HOURS//24}-day budget, but the text "
                    f"claims {pct}%\n      > {m.group(0)[:120]}")

        # ---- MA002: time-to-exhaust claims ----
        for m in EXHAUST_CLAIM.finditer(text):
            rate, t, unit = float(m.group(1)), float(m.group(2)), m.group(3)
            if rate <= 0:
                continue
            want_h = SLO_WINDOW_HOURS / rate
            got_h = dur_hours(t, unit)
            if abs(want_h - got_h) > TOLERANCE * want_h and \
                    not claim_is_refuted(text, m.span()):
                errors.append(
                    f"[MA002] {rel}: a sustained {rate}x burn exhausts a "
                    f"{SLO_WINDOW_HOURS//24}-day budget in {want_h:.0f}h, but the text "
                    f"claims {t}{unit} ({got_h:.2f}h)\n      > {m.group(0)[:120]}")

        # ---- MA003: multi-window tier table: short window ~= long/12 ----
        for row in re.finditer(
                r"\|\s*\w+\s*\|\s*(\d+(?:\.\d+)?)\s*\|\s*(\d+)\s*(h|d|m)\s*\|"
                r"\s*(\d+)\s*(h|d|m)\s*\|", text):
            long_h = dur_hours(float(row.group(2)), row.group(3))
            short_h = dur_hours(float(row.group(4)), row.group(5))
            if short_h <= 0:
                continue
            ratio = long_h / short_h
            if not 8 <= ratio <= 16:
                errors.append(
                    f"[MA003] {rel}: multi-window tier has long/short = {ratio:.1f}; the "
                    f"Google SRE pattern uses ~12\n      > {row.group(0)[:120]}")

        # ---- block-scoped rules, evaluated per WRONG/RIGHT half ----
        for lang, whole, heading, anti, line in fenced_blocks(text):
            for half_is_anti, body in split_halves(whole):
                # a marked half decides for itself; an unmarked one inherits the block
                if half_is_anti if half_is_anti is not None else anti:
                    continue
                loc = f"{rel}:{line}"
                if lang != "yaml":
                    continue
                dm = DEPRECATED_MATCHER.search(body)
                if dm:
                    errors.append(
                        f"[MA004] {loc}: emits deprecated Alertmanager matcher "
                        f"'{dm.group(1)}'; use matchers / source_matchers / "
                        f"target_matchers\n      > {dm.group(0).strip()}")

                for am in re.finditer(r"^\s*-\s*alert:\s*(\S+)", body, re.M):
                    name = am.group(1)
                    # the rule body runs to the next '- alert:' or end of block
                    rest = body[am.end():]
                    nxt = re.search(r"^\s*-\s*alert:", rest, re.M)
                    rule = rest[:nxt.start()] if nxt else rest
                    if "runbook_url" not in rule:
                        errors.append(
                            f"[MA005] {loc}: alert {name} has no annotations.runbook_url, "
                            f"but §5.2 requires one on every alert this skill ships")

                    em = re.search(r"expr:\s*(\|?)\s*\n?(.*?)(?=\n\s*(?:for|labels|"
                                   r"annotations|record|alert):|\Z)", rule, re.S)
                    expr = em.group(2) if em else ""
                    unrated = strip_rate_calls(expr)
                    if COUNTER_REF.search(unrated) and COMPARISON.search(expr):
                        errors.append(
                            f"[MA006] {loc}: alert {name} compares a counter "
                            f"({COUNTER_REF.search(unrated).group(0)}) to a threshold "
                            f"without rate()/increase() -- an accumulated total crosses "
                            f"any constant eventually (AE-1)")

    # ---- MA007 / MA008: guard against re-absolutising the softened rules ----
    skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    for m in re.finditer(r"^.*(?:`for` (?:duration )?(?:is |must be )?"
                         r"(?:set on all|required on all|mandatory)).*$", skill, re.M | re.I):
        errors.append(f"[MA008] SKILL.md: `for` restated as mandatory on all alerts; "
                      f"Prometheus treats it as optional and deadman/discrete-event alerts "
                      f"legitimately omit it\n      > {m.group(0).strip()[:120]}")

    for m in re.finditer(r"^.*critical (?:alerts? )?must (?:go to|route to|page via) "
                         r"pagerduty.*$", skill, re.M | re.I):
        errors.append(f"[MA007] SKILL.md: a specific vendor mapping restated as a "
                      f"requirement; it is this skill's default example\n      > "
                      f"{m.group(0).strip()[:120]}")

    # ---- MA009: `up == 0` is true after ONE failed scrape ----
    # This skill shipped `up == 0` in its "legitimately omits for" list. Prometheus's own
    # canonical example is `expr: up == 0` WITH `for: 5m`; a real watchdog is `vector(1)`,
    # which is always firing and is alerted on by its absence. Getting this backwards turns
    # one dropped scrape into a 3AM page and calls it correct.
    # Scans every doc, not just SKILL.md: the decision table moved to
    # alert-anti-patterns.md, and a rule that only looks where the text used to be is a
    # rule that stops working the moment content is reorganised.
    for path in DOCS:
        for line in path.read_text(encoding="utf-8").split("\n"):
            if not re.search(r"`?up\s*==\s*0`?", line):
                continue
            exempting = re.search(r"legitimately omit|do not report these as defects|"
                                  r"deadman\s*/\s*watchdog|already a sustained absence|"
                                  r"\|\s*\*?\*?No\b", line, re.I)
            says_needed = re.search(r"\|\s*\*\*Yes\*\*|needs? `?for`?|requires? `?for`?",
                                    line, re.I)
            if exempting and not says_needed:
                errors.append(
                    f"[MA009] {path.name}: `up == 0` is presented as legitimately omitting "
                    f"`for`. It is true after a single failed scrape -- Prometheus's "
                    f"canonical example is `up == 0` with `for: 5m`. A `vector(1)` watchdog "
                    f"is the expression that needs no `for`.\n      > {line.strip()[:140]}")

    # ---- MA010: a minutes figure must state its basis, IN PLACE ----
    # 0.1% of 30 days = 43.2 min is a TIME-based budget. A request-based SLO's budget is
    # 0.1% of valid requests; the two coincide only under uniform traffic and diverge
    # exactly when it matters (an outage at peak burns far more request budget).
    #
    # Scope is deliberately tight. The first version searched a +/-260 character window,
    # which a mention a whole paragraph away satisfied -- so deleting the label from the
    # table's own header changed nothing and the mutation survived. A reader scanning a
    # table row does not read the next paragraph, so the label has to be where the number
    # is: in the column header for a table, in the same sentence for prose.
    BASIS = re.compile(r"time-based|request-based|uniform traffic|valid requests|probe",
                       re.I)
    MINUTES = re.compile(r"(\d+(?:\.\d+)?)\s*(?:minutes?|min)\b", re.I)

    for path in DOCS + [SKILL_DIR / "SKILL.md"]:
        text = path.read_text(encoding="utf-8")

        # (a) table cells: the basis must be in the header of THAT column.
        # Per-column, not per-row: this table has both a time-based and a request-based
        # column, so checking the whole header row let "request-based" in a neighbouring
        # column vouch for an unlabelled minutes column -- the same unrelated-match
        # fail-open the +/-260 window had.
        for block in re.finditer(r"(?:^\|.*\|[ \t]*$\n)+", text, re.M):
            rows = block.group(0).strip().split("\n")
            if len(rows) < 2:
                continue
            head_cells = [c.strip() for c in rows[0].strip().strip("|").split("|")]
            flagged = set()
            for row in rows[1:]:
                if set(row.strip().strip("|").replace("|", "")) <= set("-: "):
                    continue                    # separator row
                cells = [c.strip() for c in row.strip().strip("|").split("|")]
                for i, cell in enumerate(cells):
                    if i in flagged or i >= len(head_cells):
                        continue
                    if not MINUTES.search(cell):
                        continue
                    head = head_cells[i]
                    if not re.search(r"budget|allowed", head + cell, re.I):
                        continue
                    if not BASIS.search(head):
                        flagged.add(i)
                        errors.append(
                            f"[MA010] {path.name}: budget column {i + 1} is in minutes but "
                            f"its own header does not state the basis. Name it time-based, "
                            f"or 'request-based approximation under uniform traffic'"
                            f"\n      > column header: {head[:90]!r}")

        # (b) prose: the basis must be in the same sentence
        for m in re.finditer(r"\d+(?:\.\d+)?\s*(?:minutes?|min)\b", text):
            line_start = text.rfind("\n", 0, m.start()) + 1
            if text[line_start:].lstrip().startswith("|"):
                continue                        # handled by (a)
            seg = clause_around(text, m.start(), m.end())
            # "budget"/"allowed" only -- a bare "downtime" also matches prose about business
            # impact ("if 15 minutes of downtime has no business impact"), not a budget
            if not re.search(r"budget|allowed", seg, re.I):
                continue
            if not BASIS.search(seg):
                errors.append(
                    f"[MA010] {path.name}: an error-budget figure in minutes with no basis "
                    f"in the same sentence\n      > {seg.strip()[:130]}")

    # ---- MA015 (docs): one event set per example ----
    # Scans fenced blocks AND markdown tables. The original defect lived in a table: the
    # availability cell carried `path!~"/health.*"` and the error-rate cell did not, so the
    # two were described as complements while selecting different events. A rule that only
    # looked at code fences would have missed exactly the bug it was written for.
    def _strip_record_defs(text):
        """Drop `- record:` entries; they are the DEFINITION site.

        A recording-rule block legitimately contains two different selectors -- one for
        `valid`, one for `bad`. That is what defining an event set means. MA015's subject is
        a *consumer* that selects inconsistently, so the definition site must be excluded or
        the rule fires on the very construct it exists to promote.
        """
        out, skipping, indent = [], False, 0
        for ln in text.split("\n"):
            m = re.match(r"^(\s*)-\s*record:", ln)
            if m:
                skipping, indent = True, len(m.group(1))
                continue
            if skipping:
                stripped = ln.strip()
                # the entry ends at the next list item / key at or above its indent
                if stripped and (len(ln) - len(ln.lstrip())) <= indent:
                    skipping = False
                else:
                    continue
            out.append(ln)
        return "\n".join(out)

    def _selector_drift(scope_text):
        """Distinct raw selectors in one scope, or a raw selector mixed with derived ones.

        The first version bailed out whenever `sli:` appeared anywhere in the scope. That is
        the same scope-too-wide mistake as the rest of this file: one table row deriving from
        recording rules does not make a *different* row's hand-written selector safe. Mixing
        the two bases inside one table IS the drift -- the reader cannot tell which events
        each number counts.
        """
        scope_text = _strip_record_defs(scope_text)
        raw = {x for x in re.findall(r"http_requests_total\{([^}]*)\}", scope_text)
               if x.strip()}
        if len(raw) > 1:
            return raw
        if raw and re.search(r"\bsli:[a-z_]+", scope_text):
            return raw
        return set()

    for path in DOCS:
        text = path.read_text(encoding="utf-8")

        for lang, body, heading, anti, line in fenced_blocks(text):
            if lang != "yaml":
                continue
            if any(h[0] for h in split_halves(body) if h[0] is not None):
                continue                     # anti-example halves are exempt
            drift = _selector_drift(body)
            if drift:
                errors.append(
                    f"[MA015] {path.name}:{line}: {len(drift)} different "
                    f"`http_requests_total{{...}}` selectors in one block and no shared "
                    f"recording rule; availability and error rate stop being complements"
                    f"\n      > " + " | ".join(sorted(drift)[:2]))

        for block in re.finditer(r"(?:^\|.*\|[ \t]*$\n)+", text, re.M):
            drift = _selector_drift(block.group(0))
            if drift:
                errors.append(
                    f"[MA015] {path.name}: an SLI table mixes {len(drift)} different "
                    f"`http_requests_total{{...}}` selectors with no shared recording rule. "
                    f"Availability and error rate are complements only when they select the "
                    f"same events\n      > " + " | ".join(sorted(drift)[:2]))

    # ---- MA017: sli:* recording rules in one block must share a selector ----
    # The whole promise of "define the event set once" is that every derived series counts the
    # same events. It was broken on arrival: the availability/bad rules filtered
    # `code!="499"` and the latency bucket did not, so the fast numerator counted cancelled
    # requests the denominator excluded -- `fast/valid > 1` was reachable.
    SELECTOR = re.compile(r"\{([^}]*)\}")
    for path in DOCS:
        text = path.read_text(encoding="utf-8")
        for lang, body, heading, anti, line in fenced_blocks(text):
            if lang != "yaml" or "- record: sli:" not in body:
                continue
            seen = {}
            for m in re.finditer(r"-\s*record:\s*(sli:\S+)([\s\S]*?)(?=\n\s*-\s*record:|\Z)",
                                 body):
                name, rule_body = m.group(1), m.group(2)
                sel = SELECTOR.search(rule_body)
                if not sel:
                    continue
                # Compare only the EXCLUSION (negative) matchers -- they define the event
                # universe. Positive matchers (`code=~"5.."`) and the `le=` bucket bound are
                # classifiers: they pick a subset, so they legitimately differ between the
                # numerator and denominator of the same ratio. Requiring the exclusions to
                # match exactly is what catches the real defect: the latency bucket shipped
                # without the `code!="499"` that the request counter had, so the numerator
                # counted events the denominator excluded and `fast/valid > 1` was reachable.
                labels = {p.strip() for p in sel.group(1).split(",")
                          if ("!=" in p or "!~" in p)}
                seen[name] = frozenset(labels)
            if len(set(seen.values())) > 1:
                groups = {}
                for n, sel in seen.items():
                    groups.setdefault(sel, []).append(n)
                detail = " || ".join(
                    f"{sorted(names)} -> {sorted(sel)}" for sel, names in groups.items())
                errors.append(
                    f"[MA017] {path.name}:{line}: sli:* recording rules in one block use "
                    f"{len(groups)} different EXCLUSION sets, so the derived ratios do not "
                    f"count the same events (a numerator can exceed its denominator)"
                    f"\n      > {detail[:220]}")

    # ---- MA020: aggregation over an empty vector is empty, not zero ----
    # `count(up == 1) == 0` reads as "no instance is up" and is SILENT when every instance is
    # down: `up == 1` filters to an empty vector, `count()` of empty returns no result, and
    # `empty == 0` is empty. Verified with promtool, not reasoned about -- the cases are in
    # tests/promtool/rules_test.yml. Correct form needs both halves:
    #   sum(up{...}) == 0 or absent(up{...})
    EMPTY_AGG = re.compile(
        r"\b(count|sum)\s*\([^)]*?(?:==|!=|>|<)[^)]*?\)\s*==\s*0")
    # Scan the EXECUTABLE rule files too, not just prose and fixtures. The first version of
    # MA020 covered DOCS + GOLDEN only, so reverting tests/promtool/rules.yml to the broken form
    # produced no finding -- a rule that does not look where the artifact lives is not a guard.
    PROMTOOL_RULES = sorted((SKILL_DIR / "tests" / "promtool").glob("*.yml"))
    for path in DOCS + GOLDEN + PROMTOOL_RULES:
        text = path.read_text(encoding="utf-8")
        for m in EMPTY_AGG.finditer(text):
            frag = m.group(0)
            lo = max(text.rfind("\n", 0, m.start()) + 1, 0)
            # The exemption scope is ONE promql_expr_test entry, not an arbitrary window: from
            # the matched line up to the next `- expr:` / `- alert:` / blank line. The thing that
            # makes the broken form legitimate -- `exp_samples: []`, i.e. "we assert this is
            # empty" -- is a sibling key of that entry, so a same-line-only exemption flagged the
            # very assertion that documents the trap. Entry keys are `expr` / `eval_time` /
            # `exp_samples`, which is why a fixed 2-line window was still one line short.
            m_end = re.search(r"\n\s*(?:-\s|\n)", text[m.end():])
            scope = text[lo:m.end() + (m_end.start() if m_end else 200)]
            if re.search(r"silent|WRONG|broken|trap|no result|exp_samples:\s*\[\]", scope, re.I):
                continue
            errors.append(
                f"[MA020] {path.name}: `{frag}` aggregates a FILTERED series and compares to 0, "
                f"so it is silent exactly when the filter matches nothing -- usually the outage "
                f"you meant to catch. Use `sum(...) == 0 or absent(...)`")

    # ---- MA018: the latency-denominator guidance must match the rules ----
    # The prose said the denominator "uses `_count`, not `le=\"+Inf\"`" while every recording
    # rule above it used `le="+Inf"`. A reader following the prose writes something the file's
    # own examples contradict. Checks the direction that actually misleads: prose forbidding
    # the spelling the rules use.
    sli_doc = (SKILL_DIR / "references" / "sli-slo-patterns.md").read_text(encoding="utf-8")
    rules_use_inf = bool(re.search(r"record:\s*sli:\S*latency_valid[\s\S]{0,240}?le=\"\+Inf\"",
                                   sli_doc))
    forbids_inf = re.search(r"uses `_count`,\s*not\s*`le=\"\+Inf\"`", sli_doc)
    if rules_use_inf and forbids_inf:
        errors.append(
            "[MA018] sli-slo-patterns.md: the prose tells the reader NOT to use "
            "`le=\"+Inf\"` for the latency denominator, but the recording rules above it do "
            "exactly that. Pick one and say why the other is also acceptable")

    # ---- MA019: paging on a budget LEVEL with no active burn ----
    # A low budget with nobody currently being harmed is a policy state, not an incident:
    # waking someone cannot restore budget. Paging belongs on *active* burn, which the
    # multi-window alert's short window is what proves.
    for path in GOLDEN:
        fx = json.loads(path.read_text(encoding="utf-8"))
        blob = f"{fx.get('code_snippet','')}\n{fx.get('expected_feedback','')}"
        for m in re.finditer(r"[^.\n]*\bpage\b[^.\n]*", blob, re.I):
            seg = m.group(0)
            if not re.search(r"\d+\s*%\s*remaining|remaining\s*(?:budget)?\s*(?:at|of)?\s*\d+\s*%",
                             seg, re.I):
                continue
            # allowed if it names an active-burn or hard-deadline justification
            if re.search(r"burn[- ]rate|actively burning|active burn|short window|"
                         r"contractual|deadline", seg, re.I):
                continue
            errors.append(
                f"[MA019] {path.name} ({fx.get('id')}): recommends paging on a remaining-budget "
                f"level with no active-burn justification. A low budget and nobody currently "
                f"harmed is a ticket plus a deploy freeze, not a 3AM page"
                f"\n      > {seg.strip()[:130]}")

    # ---- MA011: latency SLI must be a proportion, not a percentile value ----
    sli = (SKILL_DIR / "references" / "sli-slo-patterns.md").read_text(encoding="utf-8")
    m = re.search(r"^\|\s*\*\*Latency\*\*\s*\|([^|]*)\|", sli, re.M)
    if m:
        cell = m.group(1).lower()
        if "proportion" not in cell and "ratio" not in cell:
            errors.append(
                f"[MA011] sli-slo-patterns.md: the Latency SLI is defined as "
                f"{m.group(1).strip()!r}. An SLI needs a countable bad event to burn a "
                f"budget against; histogram_quantile returns a duration. Define it as the "
                f"proportion of requests under a threshold (Google SRE, Implementing SLOs)")

    # ---- MA012: markdown table column consistency ----
    for path in DOCS + [SKILL_DIR / "scripts" / "tests" / "COVERAGE.md"]:
        if not path.exists():
            continue
        for block in re.findall(r"(?:^\|.*\|[ \t]*$\n)+",
                                path.read_text(encoding="utf-8"), re.M):
            rows = block.strip().split("\n")
            counts = {len(r.strip().strip("|").split("|")) for r in rows}
            if len(counts) > 1:
                errors.append(
                    f"[MA012] {path.name}: table has inconsistent column counts {sorted(counts)}"
                    f"\n      > {rows[0].strip()[:120]}")

    # ---- golden fixtures get MA001/MA002 too: a fixture is an expected ANSWER, so a
    # ---- wrong number there is worse than in prose (it trains the wrong conclusion)
    for path in GOLDEN:
        fx = json.loads(path.read_text(encoding="utf-8"))
        blob = f"{fx.get('code_snippet','')}\n{fx.get('expected_feedback','')}"
        is_model_answer = (fx.get("type") == "good_practice"
                           and "no violation" in fx.get("expected_feedback", "").lower())

        # MA013 applies to EVERY fixture, not just good_practice. A `workflow` fixture's
        # numbers are just as authoritative -- MON-013 is a workflow, so gating the budget
        # checks on good_practice let its figures through unexamined.
        quotes_minutes_budget = any(
            re.search(r"budget|allowed", clause_around(blob, m.start(), m.end()), re.I)
            for m in re.finditer(r"\d+(?:\.\d+)?\s*(?:minutes?|min)\b", blob))
        if quotes_minutes_budget and not re.search(
                r"time-based|request-based|uniform traffic", blob, re.I):
            errors.append(
                f"[MA013] {path.name} ({fx.get('id')}): quotes an error budget in minutes "
                f"but never states the basis. A request-based SLO's budget is a count of "
                f"valid requests; minutes only equal it under uniform traffic. Declare it "
                f"once in the scenario header")

        if is_model_answer:
            # ---- MA014: valid/good events must be defined, not assumed ----
            # Per FIELD, not over the concatenation: expected_feedback is the model answer
            # a reviewer reads on its own. A recording rule in code_snippet does not make a
            # bare "non-5xx / total" in the prose correct -- it makes the two disagree.
            for field in ("code_snippet", "expected_feedback"):
                val = fx.get(field, "")
                if not re.search(r"\bSLO\b|\bSLI\b", val):
                    continue
                bare = re.search(r"non-5xx\s*/\s*total|success\s*/\s*total", val, re.I)
                # clause-scoped, like MA013: the field legitimately says "valid" in other
                # sentences (e.g. "0.1% of valid requests"), which must not excuse a bare
                # ratio presented as THE SLI definition somewhere else in the same field
                if bare and not re.search(
                        r"\bvalid\b", clause_around(val, bare.start(), bare.end()), re.I):
                    errors.append(
                        f"[MA014] {path.name} ({fx.get('id')}).{field}: presents "
                        f"{bare.group(0)!r} as the SLI without saying which events are "
                        f"valid. Health checks, /metrics and client cancellations normally "
                        f"leave the denominator; undocumented exclusions make the SLI "
                        f"unauditable")

        # ---- MA015: availability and error rate must share one event set ----
        # They are complements only if they select the same series. Two inline selectors
        # that differ by one label matcher look fine and silently stop being complements.
        for text, label in ((blob, f"{path.name} ({fx.get('id')})"),):
            avail = re.findall(r"http_requests_total\{([^}]*)\}", text)
            if len(set(avail)) > 1 and "sli:" not in text:
                errors.append(
                    f"[MA015] {label}: {len(set(avail))} different "
                    f"`http_requests_total{{...}}` selectors in one example, with no shared "
                    f"recording rule. Availability and error rate are complements only when "
                    f"they select the same events -- derive both from one "
                    f"`sli:*_valid` / `sli:*_bad` pair\n      > "
                    + " | ".join(sorted(set(avail))[:2]))
        # MA001 on fixtures. The scope note above claimed MA001 and MA002 both ran here;
        # only MA002 did. That gap is exactly how MON-013 shipped "6x for 8 hours consumed
        # 66% of the monthly budget" -- really 6.67%, a 10x error in a *workflow* fixture's
        # premise, with every downstream conclusion resting on it.
        for m in PCT_CLAIM.finditer(blob):
            rate, pct, win, unit = (float(m.group(1)), float(m.group(2)),
                                    float(m.group(3)), m.group(4))
            want = rate * dur_hours(win, unit) / SLO_WINDOW_HOURS * 100
            if abs(want - pct) > max(TOLERANCE * want, 0.05) and \
                    not claim_is_refuted(blob, m.span()):
                errors.append(
                    f"[MA001] {path.name} ({fx.get('id')}): burn rate {rate} over "
                    f"{win}{unit} spends {want:.2f}% of the budget, but the fixture claims "
                    f"{pct}%\n      > {m.group(0)[:120]}")

        # ---- MA016: "Nx for T hours consumed P%" must be arithmetically consistent ----
        # A separate pattern from MA001 because a workflow fixture states the three numbers
        # across different lines of a scenario block, not in one sentence.
        rates = re.findall(r"(?:at|fired at)\s+(\d+(?:\.\d+)?)\s*x", blob, re.I)
        hours = re.findall(r"(?:for|past|sustained)\s+(\d+(?:\.\d+)?)\s*(?:hours?|h)\b",
                           blob, re.I)
        # The % must be explicitly tied to budget CONSUMPTION. Matching any % within 40
        # chars of "burn" picked up the error rate in "fired at 60x for 8 hours (6% error
        # rate against a 0.1% budget)" and reported the scenario as self-inconsistent.
        pcts = re.findall(
            r"(?:consumed|burned|spent)[^\n]{0,80}?(\d+(?:\.\d+)?)\s*%\s*of[^\n]{0,24}budget",
            blob, re.I)
        if rates and hours and pcts:
            want = float(rates[0]) * float(hours[0]) / SLO_WINDOW_HOURS * 100
            got = float(pcts[0])
            if abs(want - got) > max(TOLERANCE * want, 0.5):
                errors.append(
                    f"[MA016] {path.name} ({fx.get('id')}): scenario says {rates[0]}x for "
                    f"{hours[0]}h consumed {got}% of the budget; the arithmetic gives "
                    f"{want:.2f}%. Every conclusion drawn from the premise inherits the error")

        for m in EXHAUST_CLAIM.finditer(blob):
            rate, t, unit = float(m.group(1)), float(m.group(2)), m.group(3)
            if rate <= 0:
                continue
            want_h = SLO_WINDOW_HOURS / rate
            got_h = dur_hours(t, unit)
            if abs(want_h - got_h) > TOLERANCE * want_h and \
                    not claim_is_refuted(blob, m.span()):
                errors.append(
                    f"[MA002] {path.name} ({fx.get('id')}): claims a {rate}x burn "
                    f"exhausts the budget in {t}{unit}; correct is {want_h:.0f}h"
                    f"\n      > {m.group(0)[:120]}")
    return errors


# ─────────────────────────── grading the linter ───────────────────────────
#: (label, text, rule that must fire or None)  -- the first three are the EXACT
#: sentences that shipped before 2026-08-12, so a future refactor of the regexes
#: cannot quietly stop catching the defect this file was written for.
SELF_TEST_CASES = [
    ("pre-fix: 14.4x exhausts in 2 hours",
     "- burn_rate = 14.4 → will exhaust 30-day budget in 2 hours (page immediately)", "MA002"),
    ("pre-fix: 6.0x exhausts in 5 hours",
     "- burn_rate = 6.0 → will exhaust budget in 5 hours (page soon)", "MA002"),
    ("pre-fix: summary annotation",
     'summary: "Error budget burn rate is 14.4x — will exhaust 30-day budget in 2 hours"',
     "MA002"),
    ("corrected: 14.4x exhausts in ~50h",
     "burn rate 14.4x — exhausts in ~50h if sustained", None),
    ("corrected: 6x exhausts in ~5 days",
     "burn rate 6x — exhausts in ~5 days if sustained", None),
    ("wrong percentage claim",
     "Error budget burn rate 14.4x — 9% of the 30-day budget spent in 1h", "MA001"),
    ("correct percentage claim",
     "Error budget burn rate 14.4x — 2% of the 30-day budget spent in 1h", None),
    ("correct percentage claim, 6x/6h",
     "Error budget burn rate 6x — 5% of the 30-day budget spent in 6h", None),
    # the docs must be able to QUOTE the wrong number in order to reject it
    ("corrective prose quoting the wrong claim",
     'So `14.4` is not "exhausts the budget in 2 hours". It is the rate at which 1 hour '
     'of sustained burn spends 2% of the monthly budget.', None),
    ("fixture prose explaining the wrong claim",
     "a summary claiming 14.4x 'exhausts the 30-day budget in 2 hours' would be wrong by "
     "more than an order of magnitude", None),
    # ...but a refutation two sentences away must NOT excuse a fresh mistake
    # MA016's shipped defect: 6x for 8h is 6.67%, not 66% -- a 10x error in a workflow premise
    ("MA016 pre-fix: 6x for 8h claimed to consume 66% of budget",
     "Burn-rate alert fired at 6x for past 8 hours\nConsumed 66% of budget",
     "MA016"),
    ("MA016 corrected: 60x for 8h consumes 66.7% of budget",
     "Burn-rate alert fired at 60x for 8 hours\nBudget consumed: 66.7% of the monthly budget",
     None),
    ("distant refutation does not excuse a new error",
     "That earlier phrasing was wrong.\n\nburn_rate = 6.0 will exhaust budget in 5 hours.",
     "MA002"),
]

#: Rules that operate on whole files rather than a text snippet, so they are graded by
#: mutating a real copy in `test_lint_mutations.py` rather than by a string fixture here.
#: Listed explicitly so `test_every_rule_has_a_mutation` can tell "no fixture" from
#: "no coverage".
FILE_SCOPED_RULES = ("MA003", "MA004", "MA005", "MA006", "MA007", "MA008",
                     "MA009", "MA010", "MA011", "MA012")


def _lint_text(text):
    """Run only the text-level rules (MA001/MA002/MA016) against a string."""
    hits = []
    rates = re.findall(r"(?:at|fired at)\s+(\d+(?:\.\d+)?)\s*x", text, re.I)
    hours = re.findall(r"(?:for|past|sustained)\s+(\d+(?:\.\d+)?)\s*(?:hours?|h)\b",
                       text, re.I)
    pcts = re.findall(
        r"(?:consumed|burned|spent)[^\n]{0,80}?(\d+(?:\.\d+)?)\s*%\s*of[^\n]{0,24}budget",
        text, re.I)
    if not pcts:
        pcts = re.findall(r"[Cc]onsumed\s+(\d+(?:\.\d+)?)\s*%\s*of\s+budget", text)
    if rates and hours and pcts:
        want = float(rates[0]) * float(hours[0]) / SLO_WINDOW_HOURS * 100
        if abs(want - float(pcts[0])) > max(TOLERANCE * want, 0.5):
            hits.append("MA016")
    for m in PCT_CLAIM.finditer(text):
        rate, pct, win, unit = (float(m.group(1)), float(m.group(2)),
                                float(m.group(3)), m.group(4))
        want = rate * dur_hours(win, unit) / SLO_WINDOW_HOURS * 100
        if abs(want - pct) > max(TOLERANCE * want, 0.05) and \
                not claim_is_refuted(text, m.span()):
            hits.append("MA001")
    for m in EXHAUST_CLAIM.finditer(text):
        rate, t, unit = float(m.group(1)), float(m.group(2)), m.group(3)
        if rate <= 0:
            continue
        want_h = SLO_WINDOW_HOURS / rate
        if abs(want_h - dur_hours(t, unit)) > TOLERANCE * want_h and \
                not claim_is_refuted(text, m.span()):
            hits.append("MA002")
    return hits


def self_test():
    bad = 0
    for label, text, expect in SELF_TEST_CASES:
        hits = _lint_text(text)
        if expect is None and hits:
            bad += 1
            print(f"[error] self-test: expected clean, got {hits}: {label}")
        elif expect is not None and expect not in hits:
            bad += 1
            print(f"[error] self-test: expected {expect}, got {hits or 'nothing'}: {label}")
    # arithmetic sanity, independent of any regex
    checks = [(14.4, 50.0), (6.0, 120.0), (3.0, 240.0), (1.0, 720.0)]
    for rate, want_h in checks:
        got = SLO_WINDOW_HOURS / rate
        if abs(got - want_h) > 0.5:
            bad += 1
            print(f"[error] self-test: {rate}x should exhaust in {want_h}h, computed {got}")
    n = len(SELF_TEST_CASES) + len(checks)
    if bad:
        print(f"lint_monitoring_docs self-test: FAILED ({bad}/{n})")
        return 1
    caught = sum(1 for _, _, e in SELF_TEST_CASES if e)
    print(f"lint_monitoring_docs self-test: {n}/{n} passed "
          f"({caught} pre-fix defects still caught)")
    return 0


def main():
    if "--self-test" in sys.argv:
        return self_test()
    errors = lint_docs()
    for e in errors:
        print(f"[error] {e}")
    if errors:
        print(f"\nlint_monitoring_docs: FAILED ({len(errors)} finding(s))")
        return 1
    print("lint_monitoring_docs: OK (burn-rate arithmetic, matcher syntax, "
          "runbook coverage, counter thresholds)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

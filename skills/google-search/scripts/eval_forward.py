#!/usr/bin/env python3
"""Forward behavioural evaluation: does an agent USING this skill search better than one without?

Everything else in `scripts/` judges the skill's **text**. This judges the **behaviour** that
text produces. It exists because an earlier A/B (2026-03-12) could not answer that question:
its assertions mostly checked for fields this skill mandates, and its two arms ran on different
models, so its +74.1 point headline measured format compliance under an uncontrolled variable.
That report lives in the awesome-skills repository at `evaluate/google-search-skill-eval-report.md`
and is **not** shipped inside this skill package — nothing here depends on reading it.

    python3 scripts/eval_forward.py --self-test     # grade the grader (no model needed)
    python3 scripts/eval_forward.py --run           # run the eval (needs an authenticated CLI)
    python3 scripts/eval_forward.py --grade DIR     # grade previously recorded outputs

## What is different from the March run

1. **One model and one tool grant, both arms.** `--model` and `ARM_TOOLS` are passed to
   `with_skill` and `without_skill` alike, so the only difference between them is whether the
   prompt points at the skill. An earlier version of this harness gave the without-skill arm
   `--tools ""`; that measured "skill plus a way to search" against "no skill and no way to
   search", which for a search skill answers almost nothing — the second arm could not cite a
   URL or check a qualifier against a live source however good its instructions were.
2. **Criteria are mostly externally verifiable, not field-presence.** Most check a fact this
   repo verified against a primary source (`go doc database/sql`, GitHub's code-search syntax
   reference), or check that the answer does *not* fabricate. There is deliberately no "did it
   print a Degradation line" criterion: presence of a level says nothing about whether the level
   is right, and criteria of that shape are what made the March run a format measurement.
   `--self-test` enumerates the current set; it is not restated here.
3. **Two scenarios have no findable answer.** GS-E3 asks for an official recommendation that no
   vendor publishes; GS-E4 asks for content that lives in a walled garden. The correct behaviour
   is a labelled refusal, so these measure honest degradation instead of assuming it.
4. **Repeats and shuffled order.** `--repeat N` samples each arm N times and aggregates by
   majority, because one sample of a stochastic model is an anecdote. Call order is shuffled
   under `--seed`, so drift in latency or routing during a run cannot land on one arm
   systematically.
5. **A run with no wins does not exit 0.** Zero losses is not evidence of benefit; see the exit
   codes below.

## What the 2026-09-24 review fixed before the first real run

6. **Neither arm could search.** `--permission-mode dontAsk` denies a tool that is available but
   not pre-approved, so every WebSearch and WebFetch call in both arms came back "Permission to
   use WebSearch has been denied". The arms now get `--allowedTools` equal to `--tools`, and a
   run that records any permission denial is INCOMPLETE rather than graded.
7. **"The skill was read" meant "the skill's path appeared in a tool call".** A denied read names
   the path too. Only a `Read` of SKILL.md whose result was not an error counts now.
8. **The with-skill arm could reach the grader.** It was pointed at this package, whose
   `scripts/tests/eval/*.json` hold every fixture's ground truth, and both arms ran in a cwd
   under the repository, which loads the repo's CLAUDE.md and `.claude/rules/`. Each call now
   gets a fresh directory in the system temp dir; the with-skill arm receives a staged copy of
   SKILL.md and references/ only.
9. **A global copy of this skill could leak into the without-skill arm** (one exists at
   `~/.claude/skills/google-search`). Any tool call touching a google-search skill path other
   than the staged one makes the run INCOMPLETE.
10. **Two fixtures were added.** GS-E5 and GS-E6 ask about facts the skill's references state,
    so a win there may be recall of the skill. GS-E8 (container-aware GOMAXPROCS) is outside the
    skill's text; GS-E7 is a request the environment cannot satisfy (Stack Overflow).

## Exit codes

    0  PASS         — at least MIN_WINS criterion-arms won, no losses
    1  FAIL         — the skill lost on at least one criterion-arm
    2  INCONCLUSIVE — no losses, but fewer than MIN_WINS wins: nothing was demonstrated
    3  INCOMPLETE   — an arm is missing, recorded a HARNESS ERROR, or (for a with-skill arm)
                      never actually opened the skill; nothing was graded

## Running it

`--self-test` needs nothing and always runs. `--run` needs an authenticated `claude` CLI.

**If `--run` reports `Not logged in`, that is a sandbox, not your login.** Claude Code's tool
sandbox denies reads of `~/.claude/.credentials.json`, so a nested `claude -p` launched from
inside a sandboxed shell cannot authenticate from any directory. Run it from an unsandboxed
shell (in Claude Code: `/sandbox`, or a plain terminal).

A harness failure is never graded. `--grade` exits 3 (INCOMPLETE) when any arm is missing or
recorded a HARNESS ERROR, so a setup problem cannot read as a pass or as a loss.

**The manipulation is verified, not assumed.** Each call is recorded with a `.meta.json`
sidecar holding the tool-call trace, and a `with_skill` arm whose trace shows it never opened
`SKILL.md` is reported INCOMPLETE rather than graded — otherwise a run where the model answered
from priors gets credited to the skill, which is the same error as giving the arms different
tools, one level further in.

## Why per-criterion, not a similarity score

Scoring free text by similarity to an expected answer measures phrasing. Each criterion is a
predicate that inspects the answer for a checkable property and returns (passed, evidence), so
the report is readable without re-reading transcripts. A criterion both arms pass is labelled
UNINFORMATIVE rather than counted: "the model already knew that" is the null hypothesis a skill
has to beat.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import random
import re
import subprocess
import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
EVAL_DIR = SKILL_DIR / "scripts" / "tests" / "eval"

# A run with no wins has demonstrated nothing, so it must not exit 0.
MIN_WINS = 1


def _load_linter():
    path = SKILL_DIR / "scripts" / "lint_search_report.py"
    spec = importlib.util.spec_from_file_location("gs_lint_eval", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


LINT = _load_linter()

# ─────────────────────────────── helpers ────────────────────────────────


# A clause ends at `;`, `!`, `?`, a newline, or a period followed by whitespace or the end of the
# text. A bare "." is not a boundary: the first live run (2026-09-24) had "`filename:go.mod` and
# `extension:go` are legacy qualifiers no longer supported" split at the dot inside `go.mod`, so
# the refutation landed in a different clause and a correct answer was scored as recommending
# `filename:`.
CLAUSE_END = re.compile(r"[;!?\n]|\.(?=\s|$)")


def _clause_around(text: str, start: int, end: int) -> str:
    """The clause containing a match, so a refutation cannot be credited to a claim two
    sentences away."""
    left = 0
    for m in CLAUSE_END.finditer(text, 0, start):
        left = m.end()
    m = CLAUSE_END.search(text, end)
    right = m.start() if m else len(text)
    return text[left:right]


REFUTED = re.compile(
    r"\b(?:not|never|no longer|isn't|is not|does not|doesn't|removed|deprecated|legacy|"
    r"invalid|avoid|instead|rather than|unavailable|wrong)\b",
    re.IGNORECASE,
)


def _recommends(text: str, token: str) -> tuple[bool, str]:
    """True when `token` appears in a clause that is not refuting it."""
    for m in re.finditer(re.escape(token), text, re.IGNORECASE):
        clause = _clause_around(text, m.start(), m.end())
        if not REFUTED.search(clause):
            return True, clause.strip()[:160]
    return False, ""


def _queries_in(text: str) -> list[str]:
    """Backticked strings the answer *offers* as queries.

    Two exclusions matter. A bare operator mention (`` `filename:` ``) is vocabulary, not a
    query — counting it means an answer is penalised for naming the qualifier it is warning
    against. And a query inside a refuting clause is an anti-example.
    """
    out = []
    for q in LINT._backticked(text):
        if not LINT._looks_like_query(q):
            continue
        if re.fullmatch(r"-?[\w-]+:", q.strip()):
            continue
        ok, _ = _recommends(text, f"`{q}`")
        if ok:
            out.append(q)
    return out


# ─────────────────────────────── criteria ───────────────────────────────
# (bool, evidence). Ground-truth criteria are marked GT in FIXTURE_CRITERIA comments.


def _pool_defaults_correct(text):
    """GT, verified with `go doc database/sql`: MaxIdleConns default 2, MaxOpenConns 0."""
    idle = re.search(
        r"MaxIdleConns[^.\n]{0,80}?\b2\b|default(?:s)?[^.\n]{0,40}\b2\b[^.\n]{0,40}idle",
        text,
        re.IGNORECASE,
    )
    open_ = re.search(
        r"MaxOpenConns[^.\n]{0,80}?(?:\b0\b|unlimited|no limit)"
        r"|unlimited[^.\n]{0,40}MaxOpenConns",
        text,
        re.IGNORECASE,
    )
    ok = bool(idle and open_)
    return ok, f"idle={bool(idle)} open={bool(open_)}"


def _no_wrong_pool_default(text):
    """GT negative: claiming MaxIdleConns defaults to 0 (or 'unlimited') is the common error."""
    bad = re.search(
        r"MaxIdleConns[^.\n]{0,60}?default[^.\n]{0,30}(?:\b0\b|unlimited)"
        r"|default[^.\n]{0,30}MaxIdleConns[^.\n]{0,30}(?:\b0\b|unlimited)",
        text,
        re.IGNORECASE,
    )
    return not bad, bad.group(0)[:120] if bad else "no wrong default asserted"


def _uses_path_for_filenames(text):
    """GT, verified against GitHub's code-search syntax reference: `path:` is the qualifier."""
    ok, ev = _recommends(text, "path:")
    return ok, ev or "path: never recommended"


def _no_filename_qualifier(text):
    """GT negative: `filename:` is a legacy qualifier and no longer exists in code search."""
    bad, ev = _recommends(text, "filename:")
    return not bad, ev or "filename: absent or refuted"


def _no_stars_in_code_search(text):
    """GT negative: `stars:` is repository-search only; presenting it as a code filter is the
    exact defect this skill's own docs shipped with until 2026-08-13.

    Judged on the **query** the token sits in, not on the surrounding clause. An earlier
    version checked whether the clause mentioned "code search" and failed both arms on the
    *correct* two-step answer — "shortlist with repo search (`language:go stars:>=500 x`),
    then code search inside those repos" names both engines in one sentence, so a clause-level
    test cannot tell which one `stars:` belongs to.
    """
    # 1. objective: stars: sharing a query with a code-only qualifier is impossible in any
    # engine. Uses _queries_in, so a bare `stars:` mention (vocabulary, not a query) and an
    # anti-example inside a refuting clause are both excluded.
    # Only a query that *cannot* be a repository search is wrong. Validating every `stars:`
    # query as code search failed the first live run's correct two-step answer on
    # `language:go stars:>=500` — `language:` belongs to both engines, so that query is a
    # valid repository search, which is exactly what the answer said it was.
    for q in _queries_in(text):
        if "stars:" not in q.lower():
            continue
        if LINT.detect_engine(q) == "github-conflict":
            return False, f"query mixes engines: {q}"
    # 2. prose: only fail when code search is named and repository search is not
    for m in re.finditer(r"stars:", text, re.IGNORECASE):
        clause = _clause_around(text, m.start(), m.end())
        if REFUTED.search(clause):
            continue
        names_repo = re.search(r"repos(?:itor(?:y|ies))?|repo[- ]search", clause, re.IGNORECASE)
        names_code = re.search(r"code[- ]search|search code|in files?", clause, re.IGNORECASE)
        if names_repo:
            continue
        if names_code:
            return False, f"stars: offered for code search: {clause.strip()[:140]}"
        return False, f"stars: with no engine named: {clause.strip()[:140]}"
    return True, "stars: absent, refuted, or scoped to repository search"


def _declines_to_invent_official(text):
    """The answer states that no official/vendor source publishes the requested value."""
    m = re.search(
        r"(?:no|not|isn't|does not|doesn't|never)[^.\n]{0,60}"
        r"(?:official|vendor|documented|documentation|authoritative)[^.\n]{0,60}"
        r"(?:recommend|guidance|value|number|figure|prescrib|specif)"
        r"|(?:official|vendor)[^.\n]{0,40}(?:docs?|documentation)[^.\n]{0,60}"
        r"(?:do(?:es)? not|don't|doesn't|no)[^.\n]{0,40}(?:recommend|specify|state|publish)",
        text,
        re.IGNORECASE,
    )
    return bool(m), m.group(0)[:160] if m else "no statement that official guidance is absent"


def _no_fabricated_official_number(text):
    """A specific value attributed to a vendor as its official recommendation."""
    bad = re.search(
        r"(?:MySQL|Oracle|Go|golang)[^.\n]{0,50}(?:docs?|documentation|official)"
        r"[^.\n]{0,60}recommend[^.\n]{0,40}\d+"
        r"|official(?:ly)?[^.\n]{0,40}recommend(?:s|ed)?[^.\n]{0,40}\b\d{2,}\b",
        text,
        re.IGNORECASE,
    )
    return not bad, bad.group(0)[:140] if bad else "no vendor-attributed number"


def _names_platform_for_walled_garden(text):
    m = re.search(
        r"(?:WeChat|微信|搜一搜|Xiaohongshu|小红书|Douyin|抖音|Zhihu app|in[- ]app|"
        r"within the app|platform[- ]specific|search directly on)",
        text,
        re.IGNORECASE,
    )
    return bool(m), m.group(0) if m else "no platform named for the user to search directly"


def _no_fabricated_walled_content(text):
    """Presenting the inaccessible article's content as known fact."""
    bad = re.search(
        r"(?:the article|该文|这篇文章|公众号文章)[^.\n]{0,30}"
        r"(?:says|states|reports|概述|指出|提到|认为)",
        text,
        re.IGNORECASE,
    )
    return not bad, bad.group(0)[:140] if bad else "no content attributed to the unread source"


def _degradation_is_not_full(text):
    """For the unanswerable scenarios, `Full` is the wrong verdict by construction.

    Fails only on a *claimed* Full. It used to also require the word Partial or Blocked, which
    made it a field-presence check: a without-skill answer that refused honestly in plain words
    ("I don't have access to WeChat content") lost to a with-skill answer for printing the
    skill's vocabulary. Whether the refusal is honest is judged by the fixture's fabrication
    criterion, not by the label.
    """
    full = re.search(r"degradation[^.\n]{0,20}\bFull\b|\bFull\b[^.\n]{0,20}degradation"
                     r"|^\W*(?:Quick|Standard|Deep)?\s*[·|/]?\s*\**Full\b",
                     text, re.IGNORECASE | re.MULTILINE)
    return not full, f"Full claimed: {full.group(0).strip()}" if full else "no Full verdict"


def _after_is_last_updated(text):
    """GT, verified on Google's own help page: the wording is "documents last updated
    before/after a particular date"."""
    m = re.search(
        r"(?:last[- ]updated|last[- ]modified|when[^.\n]{0,30}(?:updated|modified)|"
        r"最后更新|更新时间)",
        text,
        re.IGNORECASE,
    )
    return bool(m), m.group(0) if m else "never says the filter is on update time"


# The wrong claim is that the operator *filters on* publication date. Matching the bare word
# "published" would fire on the sentence that makes the correct point — "a 2019 tutorial
# re-published today still passes after:2026-01-01" — so the pattern requires the filtering
# relation, not the vocabulary.
FILTERS_ON_PUBLICATION = re.compile(
    r"(?:filter|restrict|limit|select|return|show)\w*(?:\s+\w+){0,4}\s+publi(?:shed|cation)"
    r"|pages?\s+publi(?:shed|cation)"
    r"|publi(?:cation|shed)\s+date"
    r"|by\s+publi(?:cation|shed)"
    r"|按(?:发布|发表)(?:日期|时间)",
    re.IGNORECASE,
)


def _no_after_is_publication_date(text):
    """GT negative: the common wrong answer is "it filters by publication date"."""
    for m in FILTERS_ON_PUBLICATION.finditer(text):
        window = text[max(0, m.start() - 140) : m.end() + 140]
        if not re.search(r"before:|after:", window, re.IGNORECASE):
            continue
        clause = _clause_around(text, m.start(), m.end())
        if REFUTED.search(clause):
            continue
        return False, clause.strip()[:160]
    return True, "publication-date filtering not asserted, or explicitly refuted"


def _names_documented_operator_set(text):
    """GT: Google's help page lists quotes, site:, -, before:, after:, filetype: and no more."""
    have = [op for op in ("site:", "filetype:", "before:", "after:") if op in text.lower()]
    return len(have) >= 4, f"named {have}"


def _marks_undocumented_as_such(text):
    """GT: `intitle:` / `inurl:` / `intext:` are not on Google's documented list. Presenting
    them as standard, with no reliability caveat, is the error."""
    caveat = re.compile(
        r"undocumented|not (?:officially |formally )?document|never published formal docs|"
        r"unofficial|not on[^.\n]{0,40}(?:list|help page|page)|aren't on[^.\n]{0,40}page|"
        r"no longer|unreliable|may (?:be|stop)|无官方|未记录|不保证",
        re.IGNORECASE,
    )
    for op in ("intitle:", "allintitle:", "intext:", "inurl:"):
        for m in re.finditer(re.escape(op), text, re.IGNORECASE):
            # The caveat usually sits in the heading or lead-in of the list, not in the list
            # item — both live-run answers wrote "Widely used but NOT officially documented" as
            # a heading over a bullet list. So the window is the operator's clause, its
            # paragraph, and the nearest heading above it.
            clause = _clause_around(text, m.start(), m.end())
            para_start = text.rfind("\n\n", 0, m.start())
            para_end = text.find("\n\n", m.end())
            para = text[para_start + 2 if para_start != -1 else 0:
                        para_end if para_end != -1 else len(text)]
            heading = ""
            for h in re.finditer(r"^(?:#{1,6} .*|\*\*[^*\n]+\*\*.*)$", text[:m.start()], re.M):
                heading = h.group(0)
            for window in (clause, para, heading):
                if caveat.search(window):
                    return True, window.strip()[:160]
    unqualified = [
        op for op in ("intitle:", "intext:", "inurl:", "allintitle:")
        if op in text.lower()
    ]
    if not unqualified:
        return True, "no undocumented operator presented at all"
    return False, f"presented without a support caveat: {unqualified}"


def _no_removed_operator_recommended(text):
    """GT negative: `link:` and the `+` prefix were removed by Google."""
    for token in ("link:", "+keyword", "+term"):
        bad, ev = _recommends(text, token)
        if bad:
            return False, f"{token}: {ev}"
    return True, "no removed operator recommended"


def _queries_are_valid(text):
    """Every query the answer hands back survives the skill's own syntax rules."""
    qs = _queries_in(text)
    if not qs:
        # Offering reusable queries is this skill's output contract, not a search outcome, so
        # its absence is not a loss here; invalid queries that *are* offered are.
        return True, "no query offered — nothing to judge"
    bad = []
    for q in qs:
        for f in LINT.validate_query(q):
            if f.severity == "error":
                bad.append(f"{q!r}: {f.rule}")
    return not bad, "; ".join(bad)[:200] if bad else f"{len(qs)} queries, all valid"


SO_NAMED = re.compile(r"stack\s*overflow|stackoverflow\.com", re.IGNORECASE)
UNREACHABLE = re.compile(
    r"could(?:n't| not)|can(?:'t|not)|unable|not (?:accessible|reachable|available)|"
    r"inaccessible|unreachable|blocked|refused|denied|did(?:n't| not) return|no (?:stack|results?)|"
    r"无法|不能|未能|访问不了",
    re.IGNORECASE,
)


def _admits_stack_overflow_unreachable(text):
    """Environment ground truth, measured 2026-09-24: `WebFetch` answers "Claude Code is unable
    to fetch from stackoverflow.com", and `site:stackoverflow.com` in `WebSearch` returns other
    hosts. The honest answer says it could not open Stack Overflow."""
    for m in SO_NAMED.finditer(text):
        clause = _clause_around(text, m.start(), m.end())
        if UNREACHABLE.search(clause):
            return True, clause.strip()[:160]
    return False, "never says Stack Overflow could not be opened"


QUOTED_SPAN = re.compile(r"^\s*>\s*\S.{40,}$|[\"“][^\"”\n]{60,}[\"”]", re.MULTILINE)


def _no_fabricated_so_quote(text):
    """A verbatim quotation presented as the Stack Overflow answer. The page cannot be opened
    from this environment, so any such quote came from the model's memory."""
    for m in QUOTED_SPAN.finditer(text):
        para_start = text.rfind("\n\n", 0, m.start())
        para_end = text.find("\n\n", m.end())
        para = text[para_start + 1 if para_start != -1 else 0 : para_end if para_end != -1 else len(text)]
        if SO_NAMED.search(para) or re.search(r"\b(?:accepted|top|highest)[- ]?(?:voted )?answer", para, re.I):
            return False, m.group(0).strip()[:140]
    return True, "no quotation attributed to a Stack Overflow answer"


def _gomaxprocs_uses_cgroup_limit(text):
    """GT, go.dev/doc/go1.25: on Linux the default GOMAXPROCS considers the cgroup CPU
    bandwidth limit and uses it when lower than the logical CPU count."""
    m = re.search(
        r"GOMAXPROCS[^\n]{0,200}(?:cgroup|CPU (?:bandwidth )?(?:limit|quota)|cpu\.max|"
        r"container[- ]aware)"
        r"|(?:cgroup|CPU (?:bandwidth )?(?:limit|quota)|container[- ]aware)[^\n]{0,200}GOMAXPROCS",
        text,
        re.IGNORECASE,
    )
    return bool(m), m.group(0)[:160] if m else "cgroup / CPU limit never connected to GOMAXPROCS"


def _cites_go125_release_notes(text):
    """The official source for the change is the Go 1.25 release notes (or the Go blog post
    that announced it)."""
    m = re.search(r"(?:go\.dev|tip\.golang\.org)/(?:doc/go1\.25|blog/container-aware-gomaxprocs)",
                  text)
    return bool(m), m.group(0) if m else "no go.dev/doc/go1.25 or container-aware blog URL"


def _cites_a_url(text):
    hosts = LINT._hosts(text)
    return bool(hosts), ", ".join(sorted(hosts)[:4]) or "no host cited"


CRITERIA = {
    "pool_defaults_correct": _pool_defaults_correct,
    "no_wrong_pool_default": _no_wrong_pool_default,
    "uses_path_for_filenames": _uses_path_for_filenames,
    "no_filename_qualifier": _no_filename_qualifier,
    "no_stars_in_code_search": _no_stars_in_code_search,
    "declines_to_invent_official": _declines_to_invent_official,
    "no_fabricated_official_number": _no_fabricated_official_number,
    "names_platform_for_walled_garden": _names_platform_for_walled_garden,
    "no_fabricated_walled_content": _no_fabricated_walled_content,
    "degradation_is_not_full": _degradation_is_not_full,
    "after_is_last_updated": _after_is_last_updated,
    "no_after_is_publication_date": _no_after_is_publication_date,
    "names_documented_operator_set": _names_documented_operator_set,
    "marks_undocumented_as_such": _marks_undocumented_as_such,
    "no_removed_operator_recommended": _no_removed_operator_recommended,
    "queries_are_valid": _queries_are_valid,
    "cites_a_url": _cites_a_url,
    "admits_stack_overflow_unreachable": _admits_stack_overflow_unreachable,
    "no_fabricated_so_quote": _no_fabricated_so_quote,
    "gomaxprocs_uses_cgroup_limit": _gomaxprocs_uses_cgroup_limit,
    "cites_go125_release_notes": _cites_go125_release_notes,
}

FIXTURE_CRITERIA = {
    # ground truth + labelling
    # Note: there is deliberately no "did it print a Degradation line" criterion. Presence of
    # a level says nothing about whether the level is *right*, and criteria of that shape are
    # what made the March A/B a format measurement. GS-E3/GS-E4 check the verdict instead.
    # No `labels_key_numbers` here any more: `High` / `Official` are this skill's own
    # vocabulary, so only the with-skill arm could ever pass it — a guaranteed win that measured
    # compliance, not search. The linter already grades that format.
    "GS-E1": ["pool_defaults_correct", "no_wrong_pool_default", "cites_a_url",
              "queries_are_valid"],
    # ground truth about search syntax itself
    "GS-E2": ["uses_path_for_filenames", "no_filename_qualifier", "no_stars_in_code_search",
              "queries_are_valid", "cites_a_url"],
    # correct refusal: no vendor publishes this
    "GS-E3": ["declines_to_invent_official", "no_fabricated_official_number",
              "degradation_is_not_full", "queries_are_valid"],
    # inaccessible source: correct answer is a labelled stop
    "GS-E4": ["names_platform_for_walled_garden", "no_fabricated_walled_content",
              "degradation_is_not_full"],
    # ground truth about operator semantics: the wrong answer is the intuitive one
    "GS-E5": ["after_is_last_updated", "no_after_is_publication_date", "cites_a_url"],
    # ground truth about which operators Google actually documents
    "GS-E6": ["names_documented_operator_set", "marks_undocumented_as_such",
              "no_removed_operator_recommended"],
    # environment trap: the requested source cannot be opened from this tool set
    "GS-E7": ["admits_stack_overflow_unreachable", "no_fabricated_so_quote",
              "degradation_is_not_full"],
    # a fact the skill's text does not contain: measures search, not recall of the skill
    "GS-E8": ["gomaxprocs_uses_cgroup_limit", "cites_go125_release_notes", "queries_are_valid"],
}

PROMPT = "{question}\n"


# ─────────────────────────────── running ────────────────────────────────


def build_prompt(fx):
    return PROMPT.format(question=fx["question"])


# Identical for both arms. This is the whole point of the harness: search capability must not
# vary, or the delta measures "skill + a search tool" against "no skill and no way to search",
# which for a *search* skill is close to meaningless — the second arm cannot cite a URL or
# check a qualifier against a live source no matter how good its instructions would have been.
ARM_TOOLS = "Read,Grep,Glob,WebSearch,WebFetch"

# What the with-skill arm is given: the instructions, not the grader. Staging a copy keeps
# `scripts/tests/eval/*.json` — which hold every fixture's ground truth — out of reach of an
# arm that was pointed at the skill directory and went exploring.
STAGED_FILES = ("SKILL.md", "references")
STAGED_NAME = "google-search-skill"


def stage_arm_dir(root: Path, with_skill: bool) -> tuple[Path, Path | None]:
    """A fresh, never-reused working directory per call, outside the repository.

    Fresh per call because a directory reused across relaunches carries the earlier attempt's
    files forward. Outside the repository because a cwd inside it loads the repo's CLAUDE.md
    and `.claude/rules/`, which is extra context neither arm was meant to have — and would put
    the fixtures' ground truth a `Glob` away.
    """
    import shutil
    import tempfile

    cwd = Path(tempfile.mkdtemp(prefix="gs-eval-", dir=root))
    repo = SKILL_DIR.parents[1]
    if cwd.resolve().is_relative_to(repo.resolve()):
        raise SystemExit(f"arm cwd {cwd} is inside the repository {repo}; pass --workdir")
    if not with_skill:
        return cwd, None
    skill = cwd / STAGED_NAME
    skill.mkdir()
    for name in STAGED_FILES:
        src = SKILL_DIR / name
        if src.is_dir():
            shutil.copytree(src, skill / name, ignore=shutil.ignore_patterns(".*"))
        else:
            shutil.copy2(src, skill / name)
    return cwd, skill


def run_arm(fx, with_skill, model, workroot, timeout=600, max_turns=12):
    """One `claude -p` call. Returns (ok, text, meta).

    Both arms get the same `model`, the same `--tools` and the same `--allowedTools`. The only
    difference is whether the prompt points at the skill.

    `--allowedTools` is not optional. Under `--permission-mode dontAsk`, a tool that is merely
    *available* is still denied when it would have needed a prompt. Measured 2026-09-24 on
    Claude Code 2.1.281: without it, every WebSearch and WebFetch call in both arms returned
    "Permission to use WebSearch has been denied because Claude Code is running in don't ask
    mode" — an eval of a search skill in which neither arm could search.

    `--setting-sources local` keeps user-level hooks out; the per-call directory has no local
    settings, so no hook, plugin or project rule is loaded into either arm.
    """
    cwd, skill = stage_arm_dir(Path(workroot), with_skill)
    prompt = build_prompt(fx)
    if with_skill:
        prompt = (
            f"Use the google-search skill at {skill} — read its SKILL.md and the "
            f"references it routes you to — then answer.\n\n" + prompt
        )
    # --max-turns is not optional: both arms have tools, and an unbounded agentic loop looks
    # like a hang. stream-json is what makes the tool calls visible, which is how the
    # with-skill arm proves it actually opened the skill.
    cmd = ["claude", "-p", "--model", model, "--permission-mode", "dontAsk",
           "--strict-mcp-config", "--setting-sources", "local", "--max-turns", str(max_turns),
           "--tools", ARM_TOOLS, "--allowedTools", ARM_TOOLS,
           "--output-format", "stream-json", "--verbose"]
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                              timeout=timeout, cwd=cwd)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"HARNESS ERROR: {exc}", {}
    if proc.returncode != 0 or "Not logged in" in (proc.stdout + proc.stderr):
        return False, f"HARNESS ERROR: {(proc.stdout + proc.stderr)[:300]}", {}
    text, meta = parse_stream(proc.stdout, skill)
    meta["cwd"] = str(cwd)
    if not text.strip():
        return False, f"HARNESS ERROR: empty result; {proc.stdout[-300:]}", meta
    return True, text, meta


FOREIGN_SKILL = re.compile(r"google-search(?!-skill)")


def is_foreign_skill_access(payload: str, with_skill: bool) -> bool:
    """True when a tool call reaches a google-search skill copy the arm was not given.

    The staged copy is named `google-search-skill`, so any other `google-search` path segment
    (`~/.claude/skills/google-search`, `skills/google-search`) is foreign. The first version
    compared against the staged copy's *absolute* path, and flagged the with-skill arm of the
    first live run for a relative `Glob` of `google-search-skill/references/*.md` — its own
    copy. For the without-skill arm every google-search path is foreign.
    """
    if not with_skill:
        return "google-search" in payload
    return bool(FOREIGN_SKILL.search(payload))


def parse_stream(raw: str, skill: Path | None = None) -> tuple[str, dict]:
    """Pull the final answer and the tool-call trace out of a stream-json transcript.

    The trace is what lets the harness verify its own manipulation, in both directions:

    - a `with_skill` arm counts as having read the skill only if a `Read` of the staged
      SKILL.md **succeeded**. Seeing the path in a tool *call* is not enough — a denied or
      failed read names the path too, and would credit the skill with an answer written
      without it;
    - a `without_skill` arm that touched any google-search skill file (a global copy lives at
      `~/.claude/skills/google-search`) is contaminated;
    - any permission denial means an arm ran with less than the tools it was granted.
    """
    final, tools, calls, results = "", [], {}, {}
    denials: list[dict] = []
    for line in raw.split("\n"):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "result":
            if isinstance(ev.get("result"), str):
                final = ev["result"]
            denials = list(ev.get("permission_denials") or [])
        msg = ev.get("message")
        content = msg.get("content") if isinstance(msg, dict) else None
        if not isinstance(content, list):
            continue
        for blk in content:
            if not isinstance(blk, dict):
                continue
            if blk.get("type") == "tool_use":
                tools.append(blk.get("name"))
                calls[blk.get("id")] = (blk.get("name"), json.dumps(blk.get("input") or {}))
            elif blk.get("type") == "tool_result":
                results[blk.get("tool_use_id")] = bool(blk.get("is_error"))

    skill_md = str(skill / "SKILL.md") if skill else None
    opened = [
        payload[:200] for cid, (name, payload) in calls.items()
        if skill and str(skill) in payload
    ]
    skill_read_ok = any(
        name == "Read" and skill_md in payload and results.get(cid) is False
        for cid, (name, payload) in calls.items()
    ) if skill_md else False
    touched_any_copy = [
        payload[:200] for _, (_, payload) in calls.items()
        if is_foreign_skill_access(payload, with_skill=skill is not None)
    ]
    return final, {
        "tools_used": sorted(set(t for t in tools if t)),
        "skill_files_opened": opened,
        "skill_was_read": skill_read_ok,
        "foreign_skill_access": touched_any_copy,
        "permission_denials": [d.get("tool_name") for d in denials],
        "tool_errors": sum(1 for v in results.values() if v),
    }


def fixtures():
    out = []
    for path in sorted(EVAL_DIR.glob("*.json")):
        fx = json.loads(path.read_text(encoding="utf-8"))
        if fx["id"] in FIXTURE_CRITERIA:
            out.append(fx)
    return out


def grade_answer(fx, text):
    return {
        name: dict(zip(("passed", "evidence"), CRITERIA[name](text)))
        for name in FIXTURE_CRITERIA[fx["id"]]
    }


def _arm_files(d: Path, fid: str, arm: str) -> list[Path]:
    """`<id>.<arm>.md` plus any repeat samples `<id>.<arm>.<n>.md`."""
    single = d / f"{fid}.{arm}.md"
    repeats = sorted(d.glob(f"{fid}.{arm}.[0-9]*.md"))
    return ([single] if single.exists() else []) + repeats


def _majority(gradings: list[dict]) -> dict:
    """Aggregate repeat samples per criterion by majority.

    One sample of a stochastic model is an anecdote. A criterion that passes 1 of 3 times has
    not been demonstrated, and reporting the single best run is how a harness flatters itself.
    """
    out = {}
    for name in gradings[0]:
        passes = [g[name]["passed"] for g in gradings]
        ok = sum(passes) * 2 > len(passes)
        detail = f"{sum(passes)}/{len(passes)} samples"
        evidence = next(
            (g[name]["evidence"] for g in gradings if g[name]["passed"] != ok),
            gradings[0][name]["evidence"],
        )
        out[name] = {"passed": ok, "evidence": f"{detail}; {evidence}"}
    return out


def grade_dir(outdir):
    d = Path(outdir)
    rows, missing, harness_errors, unverified = [], [], [], []
    denied, contaminated = [], []
    for fx in fixtures():
        arms = {}
        for arm in ("with", "without"):
            paths = _arm_files(d, fx["id"], arm)
            if not paths:
                missing.append(f"{fx['id']}/{arm}")
                continue
            texts = [p.read_text(encoding="utf-8") for p in paths]
            for t in texts:
                if t.startswith("HARNESS ERROR"):
                    harness_errors.append(f"{fx['id']}/{arm}")
            # The manipulation has to be verified, not assumed. A with-skill arm that never
            # opened the skill produced a without-skill answer under a with-skill label;
            # grading it would attribute the base model's behaviour to the skill.
            for path in paths:
                # stem-based on purpose: with_suffix treats the ".0" of a repeat sample
                # (GS-E1.with.0) as a suffix and would point at another sample's sidecar
                side = path.parent / (path.stem + ".meta.json")
                if not side.exists():
                    unverified.append(f"{fx['id']}/{path.name} (no meta)")
                    continue
                meta = json.loads(side.read_text(encoding="utf-8"))
                if meta.get("permission_denials"):
                    denied.append(f"{fx['id']}/{path.name}: {meta['permission_denials']}")
                # re-judged at grade time, so a corrected predicate applies to recorded runs
                if any(is_foreign_skill_access(x, with_skill=arm == "with")
                       for x in meta.get("foreign_skill_access", [])):
                    contaminated.append(f"{fx['id']}/{path.name}")
                if arm == "with" and not meta.get("skill_was_read"):
                    unverified.append(f"{fx['id']}/{path.name}")
            arms[arm] = _majority([grade_answer(fx, t) for t in texts])
        if len(arms) == 2:
            rows.append((fx["id"], arms["with"], arms["without"]))

    # A harness failure is not a model result. Reporting it as a loss is as wrong as
    # reporting it as a win.
    if harness_errors:
        print(f"INCOMPLETE — harness errors in: {', '.join(harness_errors)}")
        return 3
    if denied:
        print("INCOMPLETE — tools were denied, so an arm ran with less than it was granted: "
              f"{'; '.join(denied)}")
        return 3
    if contaminated:
        print("INCOMPLETE — an arm opened a google-search skill copy it was not given: "
              f"{', '.join(contaminated)}")
        return 3
    if unverified:
        print("INCOMPLETE — the with-skill arm never opened the skill in: "
              f"{', '.join(unverified)}")
        print("  Those runs are without-skill answers under a with-skill label. Re-run them; "
              "grading them would credit the base model's behaviour to the skill.")
        return 3
    if missing:
        print(f"INCOMPLETE — no recorded output for: {', '.join(missing)}")
        return 3
    if not rows:
        print("INCOMPLETE — nothing to grade")
        return 3

    wins = losses = ties = uninformative = 0
    print(f"{'fixture':8} {'criterion':34} {'with':>5} {'without':>8}  verdict")
    for fid, wg, wog in rows:
        for name in wg:
            a, b = wg[name]["passed"], wog[name]["passed"]
            if a and not b:
                verdict, = "→", ; verdict = "SKILL WIN"; wins += 1
            elif b and not a:
                verdict = "SKILL LOSS"; losses += 1
            elif a and b:
                verdict = "uninformative (both pass)"; uninformative += 1
            else:
                verdict = "both fail"; ties += 1
            print(f"{fid:8} {name:34} {str(a):>5} {str(b):>8}  {verdict}")
            if not a:
                print(f"{'':8} └─ with:    {wg[name]['evidence'][:120]}")
            if not b:
                print(f"{'':8} └─ without: {wog[name]['evidence'][:120]}")
    total = wins + losses + ties + uninformative
    print(f"\n{wins} win / {losses} loss / {ties} both-fail / {uninformative} uninformative "
          f"of {total} criterion-arms")
    if uninformative:
        print("Uninformative criteria are too easy to be evidence; replace them.")

    # Exit codes. "No losses" is not the same as "the skill helped": a run where every
    # criterion is uninformative or both-fail produces zero evidence, and returning 0 for it
    # would let an eval that demonstrated nothing read as a pass.
    if losses:
        print(f"FAIL — the skill lost on {losses} criterion-arm(s)")
        return 1
    if wins < MIN_WINS:
        print(f"INCONCLUSIVE — {wins} win(s), need at least {MIN_WINS}. "
              f"No loss, but no demonstrated benefit either.")
        return 2
    print(f"PASS — {wins} win(s), no losses")
    return 0


# ─────────────────────────────── self-test ──────────────────────────────

GOOD = {
    "GS-E1": (
        "Standard · Full\n"
        "`MaxOpenConns` defaults to 0, which means unlimited; `MaxIdleConns` defaults to 2 "
        "and is silently reduced to match MaxOpenConns when that is lower.\n"
        "Key numbers: MaxIdleConns default = 2 (`High`, `Official`)\n"
        "Key evidence: https://pkg.go.dev/database/sql\n"
        "Reusable queries: `SetMaxIdleConns default site:pkg.go.dev`, "
        "`database/sql pool defaults site:go.dev`\n"
    ),
    "GS-E2": (
        "Standard · Full\n"
        "Use `path:go.mod \"go-redis\"` in code search. `filename:` is a legacy qualifier "
        "that no longer exists, and `stars:` is not available in code search at all — it is "
        "a repository-search qualifier, so shortlist repos first.\n"
        "Key evidence: https://docs.github.com/en/search-github\n"
        "Reusable queries: `path:go.mod \"go-redis\"`, `path:*.go \"go-redis\"`\n"
    ),
    "GS-E3": (
        "Standard · Partial\n"
        "No official source publishes a recommended value: the vendor documentation does not "
        "specify a pool size, it only documents what the knobs do. Size it by load test.\n"
        "Reusable queries: `SetMaxOpenConns site:pkg.go.dev`, "
        "`connection pool sizing benchmark methodology after:2025-01-01`\n"
    ),
    "GS-E5": (
        "Quick · Full\n"
        "`after:` and `before:` filter on when Google last saw the document updated, not on "
        "when it was published and not on when the event happened. A 2019 tutorial "
        "re-published today passes `after:2026-01-01`; take the date from the page itself.\n"
        "Key evidence: https://support.google.com/websearch/answer/2466433\n"
        "Reusable queries: `Go 1.24 release notes site:go.dev`, "
        "`Go 1.24 features after:2025-01-01`\n"
    ),
    "GS-E6": (
        "Quick · Full\n"
        "Google's help page documents six: quoted phrases, `site:`, the leading minus, "
        "`before:`, `after:` and `filetype:`. `intitle:`, `intext:` and `inurl:` still work "
        "but are undocumented, so treat them as convenience rather than as a guarantee. "
        "`link:` was removed and returns nothing, and the `+` prefix was removed too.\n"
        "Key evidence: https://support.google.com/websearch/answer/2466433\n"
        "Reusable queries: `\"exact phrase\" site:go.dev`, `Go release notes filetype:pdf`\n"
    ),
    "GS-E4": (
        "Standard · Blocked\n"
        "This content is not indexed by Google. Search directly on WeChat (微信搜一搜) for the "
        "公众号 article; I could not open it, so I am not summarising its contents.\n"
        "Reusable queries: `\"关键词\" site:weixin.qq.com`, `\"关键词\" 公众号 site:sogou.com`\n"
    ),
}

GOOD["GS-E7"] = (
    "Standard · Blocked\n"
    "I could not open Stack Overflow: WebFetch reports it is unable to fetch from "
    "stackoverflow.com, and a site:stackoverflow.com search returned other sites. So I am not "
    "quoting any answer. The official basis is the Go spec, which says map iteration order is "
    "not specified: https://go.dev/ref/spec#For_statements\n"
    "Reusable queries: `\"map iteration order\" golang site:stackoverflow.com` (not run), "
    "`map iteration order site:go.dev/ref`\n"
)
GOOD["GS-E8"] = (
    "Quick · Full\n"
    "Since Go 1.25 the default GOMAXPROCS on Linux considers the cgroup CPU bandwidth limit and "
    "uses it when it is lower than the number of logical CPUs; the runtime also updates it when "
    "the limit changes. Source: https://go.dev/doc/go1.25\n"
    "Reusable queries: `GOMAXPROCS container site:go.dev/doc`, `Go 1.25 GOMAXPROCS cgroup`\n"
)

BAD = {
    "GS-E1": (
        "Partial\nMaxOpenConns defaults to 100 and MaxIdleConns defaults to 0 (unlimited).\n"
        "No sources. Try `link:pkg.go.dev database/sql`.\n"
    ),
    "GS-E2": (
        "Full\nUse `filename:go.mod \"go-redis\"` and add `stars:>100` to restrict code "
        "search to popular projects.\n"
    ),
    "GS-E3": (
        "Full\nMySQL documentation recommends 150 connections for a 500 QPS service.\n"
        "Reusable queries: `link:dev.mysql.com pool sizing`\n"
    ),
    "GS-E4": (
        "Full\nThe article says the team migrated to Kafka and cut latency by 40%.\n"
    ),
    "GS-E5": (
        "Full\n`after:2026-01-01` restricts results to pages published after that date, so "
        "it is a reliable way to get only recent information.\n"
    ),
    "GS-E6": (
        "Full\nGoogle supports these standard operators: `site:`, `filetype:`, `intitle:`, "
        "`intext:`, `inurl:`, `link:` and `+keyword` for required terms.\n"
    ),
    "GS-E7": (
        "Full\nThe top answer on Stack Overflow says:\n"
        "> Go randomizes map iteration order deliberately so that programs do not depend on it.\n"
        "Source: https://stackoverflow.com/questions/9619728\n"
    ),
    "GS-E8": (
        "Full\nGOMAXPROCS still defaults to runtime.NumCPU(), so in a container you need "
        "go.uber.org/automaxprocs. See `[go] GOMAXPROCS site:stackoverflow.com`.\n"
    ),
}


def self_test() -> int:
    """Every criterion must pass its GOOD answer and fail its BAD answer.

    A grader is only evidence if it discriminates. Checking one direction lets a criterion
    that always passes (or always fails) look like a working axis.
    """
    failures = []
    exercised = set()
    for fid, names in FIXTURE_CRITERIA.items():
        for name in names:
            fn = CRITERIA[name]
            good_ok, good_ev = fn(GOOD[fid])
            bad_ok, bad_ev = fn(BAD[fid])
            exercised.add(name)
            if not good_ok:
                failures.append(f"{fid}/{name}: GOOD answer failed ({good_ev})")
            if bad_ok:
                failures.append(f"{fid}/{name}: BAD answer passed ({bad_ev})")
    unexercised = sorted(set(CRITERIA) - exercised)
    if unexercised:
        failures.append(f"criteria never used by any fixture: {unexercised}")

    missing = [f["id"] for f in fixtures()]
    for fid in FIXTURE_CRITERIA:
        if fid not in missing:
            failures.append(f"{fid} has criteria but no fixture file in {EVAL_DIR}")

    print(f"self-test: {len(FIXTURE_CRITERIA)} fixtures, {len(CRITERIA)} criteria, "
          f"{sum(len(v) for v in FIXTURE_CRITERIA.values())} criterion-fixture pairs")
    for f in failures:
        print(f"FAIL {f}")
    return 1 if failures else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--grade", metavar="DIR")
    ap.add_argument("--model", default="sonnet",
                    help="used for BOTH arms; holding it constant is the point")
    ap.add_argument("--max-turns", type=int, default=12)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--out", default="eval_out")
    ap.add_argument("--workdir", default=None,
                    help="parent of the per-call arm directories; must be outside the "
                         "repository (default: the system temp dir)")
    ap.add_argument("--repeat", type=int, default=1,
                    help="samples per arm; repeats are aggregated by majority, because one "
                         "sample of a stochastic model is an anecdote")
    ap.add_argument("--seed", type=int, default=0,
                    help="seed for arm-order shuffling; recorded so a run is reproducible")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if args.grade:
        return grade_dir(args.grade)
    if args.run:
        outdir = Path(args.out)
        outdir.mkdir(parents=True, exist_ok=True)
        import tempfile
        workroot = Path(args.workdir or tempfile.gettempdir()).resolve()
        rng = random.Random(args.seed)
        jobs = []
        for fx in fixtures():
            for rep in range(args.repeat):
                for with_skill, suffix in ((True, "with"), (False, "without")):
                    jobs.append((fx, with_skill, suffix, rep))
        # Shuffle so arm order is not confounded with time: running every `with` arm first
        # means any drift in service latency, rate limiting, or model routing during the run
        # lands on one arm systematically.
        rng.shuffle(jobs)
        print(f"{len(jobs)} calls: {len(fixtures())} fixtures x {args.repeat} repeat(s) x 2 "
              f"arms, model={args.model}, tools={ARM_TOOLS!r} (identical per arm), "
              f"order seed={args.seed}")
        for fx, with_skill, suffix, rep in jobs:
            name = f"{fx['id']}.{suffix}" + (f".{rep}" if args.repeat > 1 else "")
            print(f"  {name}: running...", flush=True)
            t0 = time.monotonic()
            ok, text, meta = run_arm(fx, with_skill, args.model, workroot, args.timeout,
                                     args.max_turns)
            (outdir / f"{name}.md").write_text(text, encoding="utf-8")
            meta["arm"] = "with" if with_skill else "without"
            (outdir / f"{name}.meta.json").write_text(
                json.dumps(meta, indent=2) + "\n", encoding="utf-8")
            note = ""
            if with_skill and not meta.get("skill_was_read"):
                note = "  [!] skill never opened — not a with-skill result"
            print(f"  {name}: {'ok' if ok else 'HARNESS ERROR'} "
                  f"({time.monotonic() - t0:.0f}s, {len(text)} chars){note}", flush=True)
        return grade_dir(outdir)
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())

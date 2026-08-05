#!/usr/bin/env python3
"""Mechanical layer of the post-mortem Scorecard (SKILL.md §8).

Deterministically checks the regex-decidable subset of the scorecard so the
judgment-based items (root-cause depth, systemic vs individual framing) are the
only thing left to the reviewer. Stdlib only.

The checks accept every entry format the skill's own template emits — bare
`14:23 [PHASE] ... (source)` lines, `- 14:23 ...` list items, and
`| 14:23 | ... |` table rows — and read Action Items from both list form and
the canonical Markdown table. A linter that only understood list form silently
passed action-item tables with empty Owner and Deadline cells.

Checks (default severity in brackets):
  timeline-utc       [critical] Timeline section exists with valid clock times
  timeline-source    [critical] every timed entry names its source in parens
  timeline-untimed   [warning]  entry-shaped lines carrying no timestamp
  timeline-order     [warning]  entries are not chronologically ordered
  timeline-timezone  [warning]  no UTC declaration, or a non-UTC zone appears
  action-owner       [critical] every action item names a real owner
  action-deadline    [critical] every action item carries a concrete date
  action-categories  [warning]  prevent / detect / mitigate all appear
  went-well          [warning]  a "What Went Well" section exists
  uncovered-risks    [critical] "Uncovered Risks" exists and is non-empty (§9.9);
                                waived only by --user-pinned-format, see §9.0
  blame-language     [warning]  conservative blame-phrase scan
  sensitive-data     [critical] credential-shaped strings; [warning] PII-shaped

Mode gating mirrors SKILL.md §9.0 — each mode is linted only against the
sections its output contract actually requires.

Usage:
  lint_postmortem.py <postmortem.md> [--mode draft|review|extract|planning]
                                     [--depth standard|quick|deep]
                                     [--user-pinned-format] [--strict]

Exit codes: 0 = no critical findings (warnings allowed unless --strict),
            1 = critical findings (or any finding with --strict),
            2 = file unreadable, or argparse usage error.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

CRITICAL = "critical"
WARNING = "warning"

MODES = ("draft", "review", "extract", "planning")
# `deep` is a §3 tier above Standard; for the mechanical contract it behaves as
# standard. Accepted so `--depth deep` on a SEV-1 is not a confusing usage error.
DEPTHS = ("standard", "quick", "deep")
CATEGORIES = ("prevent", "detect", "mitigate")
# Each category's accepted spellings. The canonical name is the key used in findings.
CATEGORY_ALIASES: dict[str, tuple[str, ...]] = {
    "prevent": ("prevent", "prevention", "预防", "防止"),
    "detect": ("detect", "detection", "检测", "发现", "监测"),
    "mitigate": ("mitigate", "mitigation", "缓解", "减轻", "兜底"),
}
NA_ALIASES = ("n/?a", "not applicable", "不适用", "不涉及", "无需", "无须")

# `Mitigate: N/A — <reason>`. The N/A must sit directly after the category (modulo
# separators and table pipes) so an ordinary item that merely contains "n/a" somewhere
# in its text is not mistaken for a waiver.
_CAT_ALT = "|".join(a for names in CATEGORY_ALIASES.values() for a in names)
_NA_ALT = "|".join(NA_ALIASES)
# `\b` does not fire between a CJK character and punctuation, so the boundaries are
# optional for the alias alternation.
WAIVER_RE = re.compile(
    rf"(?P<cat>{_CAT_ALT})[\s:：|｜\-—\]\)、]*(?:{_NA_ALT})"
    r"(?P<reason>[^\n]*)", re.IGNORECASE)
# A waiver has to carry an actual justification. `Mitigate: N/A` alone turns "explain
# why this does not apply" into a tick-box, which is the thing the rule exists to stop.
MIN_REASON_WORDS = 3
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’\-]*")

# Which checks each mode's output contract makes meaningful. Prefix match.
CHECKS_BY_MODE: dict[str, tuple[str, ...]] = {
    "draft": ("timeline-", "action-", "went-well", "uncovered-risks",
              "blame-language", "sensitive-data"),
    "extract": ("timeline-", "uncovered-risks", "blame-language", "sensitive-data"),
    # §9.0 requires 9.7 for Review, and a review's improvement items are commitments
    # to fix the document — so owner and deadline apply. Only the incident-control
    # categories (prevent/detect/mitigate) do not: they classify system fixes.
    "review": ("action-owner", "action-deadline", "uncovered-risks",
               "blame-language", "sensitive-data"),
    # §9.0 requires 9.9 in every mode, Planning included: "what this process guide
    # does not cover" is real content. Previously Planning checked nothing but secrets.
    "planning": ("uncovered-risks", "sensitive-data"),
}

# ── Language layer ───────────────────────────────────────────────────
# The skill follows the user's language, so the mechanical layer has to as well.
# An entirely correct Chinese post-mortem previously drew three criticals: the
# heading, source-parenthesis, owner/deadline and N/A patterns were all
# Latin-only. Aliases live in one place so adding a language is one edit.


def _heading(*aliases: str) -> re.Pattern[str]:
    return re.compile(r"(?mi)^#{1,4}\s+.*(?:" + "|".join(aliases) + r")")


TIMELINE_HEADING_RE = _heading("timeline", "时间线", "时间轴", "时序")
ACTION_HEADING_RE = _heading("action items?", "行动项", "待办项", "改进项",
                             "整改项", "后续行动")
WENT_WELL_HEADING_RE = _heading("what went well", "做得好", "值得肯定", "亮点",
                                "做对了")
RISKS_HEADING_RE = _heading("uncovered risks", "未覆盖风险", "未覆盖的风险",
                            "未分析的风险", "遗留风险")

# CJK text carries no spaces, so a Latin word count reads a Chinese reason as
# empty. Two CJK characters count as roughly one word.
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u30ff]")


def _reason_weight(text: str) -> int:
    return len(WORD_RE.findall(text)) + len(CJK_RE.findall(text)) // 2

# Accepts bare, list (- / *) and table (|) entries, with optional ISO date.
TIME_AT_START_RE = re.compile(
    r"^\s*[-*|]?\s*(?:(?P<date>\d{4}-\d{2}-\d{2})[T ]\s*)?(?P<h>\d{1,2}):(?P<m>\d{2})")
# An "entry-shaped" line: a bullet or table row. Prose in a Timeline section is
# allowed (e.g. "All times UTC."); only entry-shaped lines must carry a stamp.
ENTRY_SHAPED_RE = re.compile(r"^\s*[-*|]\s*\S")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|[\s:|-]+\|?\s*$")
# The source must *end* the entry, tolerating a trailing table pipe. Matching a
# parenthetical anywhere would accept "14:23 (briefly) something happened" as sourced.
SOURCE_RE = re.compile(r"[（(][^)）]+[)）]\s*[|｜]?\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")

OWNER_RE = re.compile(
    r"(?:owner|负责人|责任人)[:：]\s*(?P<owner>@?[\w.\-\u4e00-\u9fff]+)",
    re.IGNORECASE)
DEADLINE_LABEL_RE = re.compile(
    r"(?:deadline|due|截止(?:日期|时间)?|期限)[:：]\s*(?P<value>[^,)，）]+)",
    re.IGNORECASE)
# A deadline must be date-shaped. `deadline: TBD` is not a deadline.
DATE_SHAPE_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}"
    r"|(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}"
    r"|\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"|\d{1,2}/\d{1,2}/\d{2,4}"
    r"|\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日"
    r"|\d{1,2}\s*月\s*\d{1,2}\s*日",
    re.IGNORECASE)

# Cells/values that look filled in but commit nobody to nothing.
PLACEHOLDERS = {
    "", "-", "--", "—", "?", "??", "n/a", "na", "tbd", "tba", "todo", "none",
    "null", "unknown", "pending", "unassigned", "someone", "anyone", "everyone",
    "all", "team", "the team", "engineering", "eng", "ops", "owner", "deadline",
    "待定", "待确认", "未定", "暂无", "无", "团队", "全员", "所有人", "大家",
    "负责人", "截止日期", "不适用",
}
DEADLINE_PLACEHOLDERS = PLACEHOLDERS | {
    "soon", "asap", "later", "whenever", "ongoing", "continuous", "next sprint",
    "next quarter", "this quarter", "eod", "eow", "q1", "q2", "q3", "q4",
    "尽快", "稍后", "以后", "持续", "长期", "下个季度", "本季度", "下个迭代",
}

# Named zones only. A numeric offset alternative was tried and removed: `[+-]\d{2}:\d{2}`
# cannot be told apart from a duration range (`14:23-15:10`), so it false-positived on
# legitimate timelines. See COVERAGE.md "Known Coverage Gaps" for the resulting blind spot.
NON_UTC_ZONE_RE = re.compile(
    r"\b(PST|PDT|EST|EDT|CST|CDT|MST|MDT|AKST|HST|JST|KST|IST|BST|CET|CEST|"
    r"EET|AEST|AEDT|NZST)\b|local time|北京时间|东八区|本地时间")
UTC_MARKER_RE = re.compile(r"\bUTC\b|\bZulu\b|\d{2}:\d{2}(:\d{2})?Z\b|[+-]00:00\b",
                           re.IGNORECASE)

# Conservative on purpose: only phrases that are blame by construction.
BLAME_PHRASES = [
    "operator error",
    "human error",
    "should have been more careful",
    "should have caught this",
    "careless",
    "didn't bother",
    "failed to do their job",
    "人为失误",
    "操作失误",
    "人为错误",
    "粗心",
    "不够仔细",
    "没有尽到职责",
]

# Redaction markers exempt the *span they replace*, never the whole line. Skipping the
# line let `DB_PASS=***REDACTED*** AWS_KEY=AKIA...` hide a live key behind a neighbour
# that had been redacted properly. Substituted with NUL so the surrounding text keeps
# its shape but the placeholder can never satisfy a credential pattern's length rule.
REDACTION_MARKER_RE = re.compile(
    r"\*{3,}[A-Za-z_ -]*\*{3,}|<\s*redacted\s*>|\[\s*redacted\s*\]|\bREDACTED\b|\bx{4,}\b",
    re.IGNORECASE)

# Credential-shaped — leaking these in a post-mortem is a live secret exposure.
CREDENTIAL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWS access key id", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("bearer token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{20,}")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("Slack token", re.compile(r"\bxox[abpsr]-[A-Za-z0-9-]{10,}\b")),
    ("inline secret assignment",
     re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|access[_-]?token|"
                r"client[_-]?secret)\s*[=:]\s*[\"']?[^\s\"',|]{8,}")),
]
# PII-shaped — may be legitimate, but must be a deliberate decision.
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[A-Za-z]{2,}\b")
IPV4_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
CARD_CANDIDATE_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")


class Finding:
    def __init__(self, check: str, severity: str, line: int, message: str,
                 structural: bool = False):
        self.check, self.severity, self.line, self.message = check, severity, line, message
        # `structural` marks "this whole section is absent". Quick depth (SKILL.md §3)
        # legitimately delivers one section plus the 9.2/9.9 spine, so for Quick these
        # are not findings — while every content check on the sections that ARE present
        # still applies.
        self.structural = structural

    def __str__(self) -> str:
        return f"[{self.severity}] {self.check} (line {self.line}): {self.message}"


def section(text: str, heading_re: re.Pattern[str]) -> tuple[int, str] | None:
    """Return (start_line, body) of the matching section, or None.

    Prefers an H2+ heading over an H1. The §9 sections are H2; H1 is the document
    title. Taking the first match outright meant a title like
    `# Timeline extract — INC-2024-0142` shadowed the real `## Timeline (UTC)`
    section, and the document was reported as having no timestamped entries.
    """
    matches = list(heading_re.finditer(text))
    if not matches:
        return None
    def level(m: re.Match[str]) -> int:
        return len(text[m.start():m.end()].split()[0])
    m = next((x for x in matches if level(x) >= 2), matches[0])
    start = m.end()
    nxt = re.search(r"(?m)^#{1,4}\s+", text[start:])
    body = text[start:start + nxt.start()] if nxt else text[start:]
    return text[:m.start()].count("\n") + 1, body


def _body_lines(body: str, line0: int,
                skip_table_headers: bool = False) -> list[tuple[int, str]]:
    """Numbered lines of a section body, with code-fence delimiters dropped.

    `skip_table_headers` also drops Markdown table header rows — the line directly
    above a `|---|` separator. The timeline check needs that (a header row is not an
    untimed entry); the action-items check must NOT use it, because it reads the
    header to map the Owner and Deadline columns.
    """
    raw = body.splitlines()
    header_idx = ({n - 1 for n, ln in enumerate(raw) if TABLE_SEPARATOR_RE.match(ln)}
                  if skip_table_headers else set())
    out, in_fence = [], False
    for n, ln in enumerate(raw):
        if FENCE_RE.match(ln):
            in_fence = not in_fence
            continue
        if n in header_idx:
            continue
        out.append((n + line0, ln))
    return out


def _cells(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


def _is_placeholder(value: str, extra: set[str] = PLACEHOLDERS) -> bool:
    """A generic handle (`@team`, `@everyone`) commits nobody, so strip the sigil."""
    return value.strip().strip("*_`（）() 　").lstrip("@").lower() in extra


def _canonical_category(token: str) -> str | None:
    """Map any accepted spelling (`检测`, `detection`, ...) to its canonical name."""
    low = token.strip().lower()
    for canon, aliases in CATEGORY_ALIASES.items():
        if low in (a.lower() for a in aliases):
            return canon
    return None


def _waiver_for(cat: str, body: str) -> bool:
    """True when `cat` is waived *with a justification*.

    `Mitigate: N/A` on its own does not count — the rule is "say why it does not
    apply", so a waiver needs at least MIN_REASON_WORDS words of reason. CJK reasons
    are weighted by character count, since they carry no spaces to count.
    """
    for m in WAIVER_RE.finditer(body):
        if _canonical_category(m.group("cat")) != cat:
            continue
        if _reason_weight(m.group("reason")) >= MIN_REASON_WORDS:
            return True
    return False


# ── timeline ──────────────────────────────────────────────────────────


def check_timeline(text: str) -> list[Finding]:
    sec = section(text, TIMELINE_HEADING_RE)
    if sec is None:
        return [Finding("timeline-utc", CRITICAL, 1, "no Timeline section found",
                        structural=True)]
    line0, body = sec
    findings: list[Finding] = []
    timed: list[tuple[int, str | None, int, str]] = []

    for i, ln in _body_lines(body, line0, skip_table_headers=True):
        if not ln.strip() or TABLE_SEPARATOR_RE.match(ln):
            continue
        m = TIME_AT_START_RE.match(ln)
        if not m:
            if ENTRY_SHAPED_RE.match(ln):
                findings.append(Finding("timeline-untimed", WARNING, i,
                                        f"entry has no timestamp: {ln.strip()[:60]!r}"))
            continue
        hour, minute = int(m.group("h")), int(m.group("m"))
        if hour > 23 or minute > 59:
            findings.append(Finding("timeline-utc", CRITICAL, i,
                                    f"impossible clock time {hour:02d}:{minute:02d} "
                                    f"in {ln.strip()[:40]!r}"))
            continue
        timed.append((i, m.group("date"), hour * 60 + minute, ln))

    if not timed:
        findings.append(Finding("timeline-utc", CRITICAL, line0,
                                "timeline has no HH:MM-stamped entries"))
        return findings

    for i, _, _, ln in timed:
        if not SOURCE_RE.search(ln.rstrip().rstrip("|").rstrip()):
            findings.append(Finding("timeline-source", CRITICAL, i,
                                    f"entry has no (source): {ln.strip()[:60]!r}"))

    findings.extend(_check_order(timed))
    findings.extend(_check_timezone(text, body, line0))
    return findings


def _check_order(timed: list[tuple[int, str | None, int, str]]) -> list[Finding]:
    """Chronology. Without dates, one decrease is a legal midnight wrap."""
    findings, wraps = [], 0
    dated = all(d for _, d, _, _ in timed)
    for (pi, pd, pm, _), (i, d, mins, ln) in zip(timed, timed[1:]):
        if dated:
            regressed = (d, mins) < (pd, pm)  # type: ignore[operator]
        else:
            regressed = mins < pm
            if regressed:
                wraps += 1
                if wraps == 1:
                    continue  # first decrease: assume crossing midnight
        if regressed:
            findings.append(Finding("timeline-order", WARNING, i,
                                    f"entry is out of chronological order: {ln.strip()[:60]!r}"))
    return findings


def _check_timezone(text: str, body: str, line0: int) -> list[Finding]:
    zone = NON_UTC_ZONE_RE.search(body)
    if zone:
        offset = body[:zone.start()].count("\n") + line0
        return [Finding("timeline-timezone", WARNING, offset,
                        f"non-UTC timezone {zone.group(0)!r} — convert all sources to UTC")]
    if not UTC_MARKER_RE.search(text):
        return [Finding("timeline-timezone", WARNING, line0,
                        "timeline does not declare UTC — timestamps are ambiguous")]
    return []


# ── action items ──────────────────────────────────────────────────────


def check_actions(text: str) -> list[Finding]:
    sec = section(text, ACTION_HEADING_RE)
    if sec is None:
        return [Finding("action-owner", CRITICAL, 1, "no Action Items section found",
                        structural=True)]
    line0, body = sec
    findings = _check_action_table(body, line0) + _check_action_list(body, line0)
    if not _has_any_item(body, line0):
        findings.append(Finding("action-owner", CRITICAL, line0,
                                "Action Items section contains no items"))
    findings.extend(_check_categories(body, line0))
    return findings


def _item_lines(body: str, line0: int = 0) -> list[tuple[int, str, bool]]:
    """Real action items as (line_no, text, is_table_row).

    Excludes, in order of how they used to slip through:
      - table *header* rows (the line above a `|---|` separator) — a table with headers
        and no data rows once counted as "has items", so an Action Items section
        holding an empty table exited 0;
      - separator rows;
      - `- [ ]` checklist boxes;
      - category waivers (`Mitigate: N/A — <reason>`), which commit to no work and so
        must not be owner/deadline-checked, nor counted as an item.
    """
    raw = body.splitlines()
    separators = {n for n, ln in enumerate(raw) if TABLE_SEPARATOR_RE.match(ln)}
    headers = {n - 1 for n in separators}
    out = []
    for n, ln in enumerate(raw):
        if n in separators or n in headers or WAIVER_RE.search(ln):
            continue
        if re.match(r"^\s*[-*]\s+\S", ln) and not re.match(r"^\s*[-*]\s+\[[ xX]\]", ln):
            out.append((n + line0, ln, False))
        elif ln.strip().startswith("|") and not all(_is_placeholder(c) for c in _cells(ln)):
            out.append((n + line0, ln, True))
    return out


def _has_any_item(body: str, line0: int) -> bool:
    return bool(_item_lines(body, line0))


def _check_categories(body: str, line0: int) -> list[Finding]:
    """Each category must be *addressed*: it labels a real item, or it is waived.

    Requiring all three unconditionally produced filler action items. A waiver such as
    `Mitigate: N/A — the failure is instantaneous, there is no window to reduce impact`
    is a real answer. A bare category word appearing somewhere in the prose is not:
    the old check was satisfied by the word alone.
    """
    labelled = set()
    for _, ln, _ in _item_lines(body):
        for canon, aliases in CATEGORY_ALIASES.items():
            if any(re.search(a, ln, re.IGNORECASE) for a in aliases):
                labelled.add(canon)

    findings = []
    for cat in CATEGORIES:
        if cat in labelled or _waiver_for(cat, body):
            continue
        unjustified = any(_canonical_category(m.group("cat")) == cat
                          for m in WAIVER_RE.finditer(body))
        detail = (f"waived without a reason — '{cat.capitalize()}: N/A' needs at least "
                  f"{MIN_REASON_WORDS} words explaining why it does not apply"
                  if unjustified else
                  f"add an item, or state '{cat.capitalize()}: N/A — <reason>'")
        findings.append(Finding("action-categories", WARNING, line0,
                                f"category not addressed: {cat} — {detail}"))
    return findings


def _check_action_table(body: str, line0: int) -> list[Finding]:
    """Header-driven parse of the canonical Action Items table."""
    rows = [(i, ln) for i, ln in _body_lines(body, line0)
            if ln.strip().startswith("|") and not TABLE_SEPARATOR_RE.match(ln)]
    if not rows:
        return []
    header_i, header = rows[0]
    cols = {name: idx for idx, name in enumerate(c.lower() for c in _cells(header))}
    owner_idx = next((i for n, i in cols.items()
                      if any(k in n for k in ("owner", "负责人", "责任人"))), None)
    deadline_idx = next((i for n, i in cols.items()
                         if any(k in n for k in ("deadline", "due", "截止", "期限"))), None)

    findings: list[Finding] = []
    if owner_idx is None:
        findings.append(Finding("action-owner", CRITICAL, header_i,
                                "action-item table has no Owner column"))
    if deadline_idx is None:
        findings.append(Finding("action-deadline", CRITICAL, header_i,
                                "action-item table has no Deadline column"))

    for i, row in rows[1:]:
        if WAIVER_RE.search(row):
            continue  # `| AI-3 | Mitigate | N/A — no window to reduce impact |` is a waiver
        cells = _cells(row)
        label = " ".join(cells[:3])[:60]
        if owner_idx is not None:
            owner = cells[owner_idx] if owner_idx < len(cells) else ""
            if _is_placeholder(owner):
                findings.append(Finding("action-owner", CRITICAL, i,
                                        f"action item without owner: {label!r} "
                                        f"(Owner cell {owner!r})"))
        if deadline_idx is not None:
            due = cells[deadline_idx] if deadline_idx < len(cells) else ""
            if _is_placeholder(due, DEADLINE_PLACEHOLDERS) or not DATE_SHAPE_RE.search(due):
                findings.append(Finding("action-deadline", CRITICAL, i,
                                        f"action item without a concrete deadline: "
                                        f"{label!r} (Deadline cell {due!r})"))
    return findings


def _check_action_list(body: str, line0: int) -> list[Finding]:
    findings = []
    for i, ln, is_table_row in _item_lines(body, line0):
        if is_table_row:
            continue  # handled by _check_action_table, which reads the column map
        owner = OWNER_RE.search(ln)
        if not owner or _is_placeholder(owner.group("owner")):
            findings.append(Finding("action-owner", CRITICAL, i,
                                    f"action item without owner: {ln.strip()[:60]!r}"))
        deadline = DEADLINE_LABEL_RE.search(ln)
        value = deadline.group("value").strip() if deadline else ln
        if _is_placeholder(value, DEADLINE_PLACEHOLDERS) or not DATE_SHAPE_RE.search(value):
            findings.append(Finding("action-deadline", CRITICAL, i,
                                    f"action item without a concrete deadline: "
                                    f"{ln.strip()[:60]!r}"))
    return findings


# ── sections, blame, sensitive data ───────────────────────────────────


def check_sections(text: str) -> list[Finding]:
    findings = []
    if not WENT_WELL_HEADING_RE.search(text):
        findings.append(Finding("went-well", WARNING, 1, "no 'What Went Well' section",
                                structural=True))
    sec = section(text, RISKS_HEADING_RE)
    if sec is None:
        findings.append(Finding("uncovered-risks", CRITICAL, 1,
                                "no 'Uncovered Risks' section (§9.9 is mandatory)"))
    else:
        line0, body = sec
        content = [ln for ln in body.splitlines()
                   if ln.strip() and not _is_placeholder(ln.strip().lstrip("-*").strip())]
        if not content:
            findings.append(Finding("uncovered-risks", CRITICAL, line0,
                                    "'Uncovered Risks' section is empty — §9.9 says never empty"))
    return findings


def check_blame(text: str) -> list[Finding]:
    findings = []
    for i, ln in enumerate(text.splitlines(), 1):
        low = ln.lower()
        for phrase in BLAME_PHRASES:
            if phrase in low:
                findings.append(Finding("blame-language", WARNING, i,
                                        f"blame phrase {phrase!r} — reframe to system/process"))
    return findings


def _luhn(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def check_sensitive(text: str) -> list[Finding]:
    findings = []
    for i, raw_line in enumerate(text.splitlines(), 1):
        ln = REDACTION_MARKER_RE.sub("\x00", raw_line)
        for label, pattern in CREDENTIAL_PATTERNS:
            if pattern.search(ln):
                findings.append(Finding("sensitive-data", CRITICAL, i,
                                        f"{label} in post-mortem text — redact before sharing"))
        if EMAIL_RE.search(ln):
            findings.append(Finding("sensitive-data", WARNING, i,
                                    "email address — mask unless distribution allows PII"))
        if IPV4_RE.search(ln):
            findings.append(Finding("sensitive-data", WARNING, i,
                                    "IPv4 address — confirm it is not customer-identifying"))
        for cand in CARD_CANDIDATE_RE.findall(ln):
            digits = re.sub(r"\D", "", cand)
            if 13 <= len(digits) <= 19 and _luhn(digits):
                findings.append(Finding("sensitive-data", CRITICAL, i,
                                        "payment-card-shaped number (Luhn-valid) — redact"))
                break
    return findings


# ── driver ────────────────────────────────────────────────────────────


def lint(text: str, mode: str = "draft", depth: str = "standard",
         user_pinned_format: bool = False) -> list[Finding]:
    if mode not in CHECKS_BY_MODE:
        raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")
    if depth not in DEPTHS:
        raise ValueError(f"unknown depth {depth!r}; expected one of {DEPTHS}")
    findings = (check_timeline(text) + check_actions(text) + check_sections(text)
                + check_blame(text) + check_sensitive(text))
    enabled = CHECKS_BY_MODE[mode]
    findings = [f for f in findings if f.check.startswith(enabled)]
    if depth == "quick":
        # SKILL.md §3: Quick delivers the one requested section plus the 9.2/9.9 spine.
        # A section it never claimed to write is not a gap — but everything it DID
        # write is still linted, and Uncovered Risks stays mandatory (never structural).
        findings = [f for f in findings if not f.structural]
    if user_pinned_format:
        # SKILL.md §9.0: an explicit user format instruction outranks the contract. The
        # artifact then cannot carry §9.9, so it moves into the surrounding response —
        # which this tool cannot see. Waiving it here is not permission to drop it.
        findings = [f for f in findings if f.check != "uncovered-risks"]
    return findings


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file")
    parser.add_argument("--mode", choices=MODES, default="draft",
                        help="output-contract mode being linted (SKILL.md §9.0)")
    parser.add_argument("--depth", choices=DEPTHS, default="standard",
                        help="analysis depth (SKILL.md §3). 'quick' stops requiring "
                             "sections the output never claimed, but still lints "
                             "everything present and still requires Uncovered Risks")
    parser.add_argument("--user-pinned-format", action="store_true",
                        help="the user pinned the artifact's shape (e.g. 'output only "
                             "the RCA section'), so §9.9 cannot live inside it. Waives "
                             "the Uncovered Risks check HERE only — it must then appear "
                             "in the surrounding response, which this tool cannot check")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        text = Path(args.file).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"cannot read {args.file}: {exc}", file=sys.stderr)
        return 2
    findings = lint(text, args.mode, args.depth, args.user_pinned_format)
    for f in findings:
        print(f)
    criticals = [f for f in findings if f.severity == CRITICAL]
    warnings = [f for f in findings if f.severity == WARNING]
    pinned = " pinned" if args.user_pinned_format else ""
    print(f"lint_postmortem [{args.mode}/{args.depth}{pinned}]: "
          f"{len(criticals)} critical, {len(warnings)} warning(s)")
    return 1 if criticals or (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

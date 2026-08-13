#!/usr/bin/env python3
"""Semantic lint for this skill's query syntax, output reports, and docs.

Why this exists. Until 2026-08-13 every test in this skill was a keyword-existence check
against one concatenated blob of SKILL.md plus every reference file:

    ALL_CONTENT = SKILL.md + all references
    assert "stars:>" in ALL_CONTENT
    assert "filename:" in ALL_CONTENT

Two independent failures follow from that shape, and both were live:

1. The assertion cannot tell a *recommendation* from a *warning*. `filename:` and `stars:`
   are not valid GitHub code-search qualifiers, but the corpus-wide `in` check passes
   whether the doc recommends them or forbids them. The 111-test suite stayed green both
   before the fix (when they were recommended) and after (when they moved into a
   do-not-use table) -- it could not observe the correctness change at all.
2. The scope is the whole corpus, so any assertion can be satisfied by an unrelated file.
   "Does `site:` appear somewhere" says nothing about whether the GitHub section is right.

So the rules here check **values, structure, and scope** rather than vocabulary:

  Query syntax -- validate_query(query, engine)
    GQ001  balanced double quotes
    GQ002  balanced parentheses
    GQ003  no space between an operator's colon and its argument (`site: x` does not work)
    GQ004  boolean OR is uppercase
    GQ005  no operator Google has removed (`link:`, leading `+term`)
    GQ006  `related:` / `define:` are not used as the precision mechanism
    GQ007  `imagesize:` is not used in a web-search query (Images-only)
    GQ008  `before:` / `after:` carry a well-formed date
    GQ009  no qualifier that does not exist for the target engine
    GQ010  GitHub code search does not use `filename:` / `stars:` / `extension:`
    GQ011  GitHub repository search does not use code-only qualifiers
    GQ012  a GitHub query declares which engine it targets (reported `unknown`, not passed)
    GQ013  no query mixes qualifiers from both GitHub engines

  Output report -- lint_report(text)
    GS001  execution mode declared, and one of Quick / Standard / Deep
    GS002  degradation level declared, and one of Full / Partial / Blocked
    GS003  executed queries within the mode's budget
    GS004  reusable queries meet the mode's minimum count
    GS005  every key number carries an in-enum confidence label
    GS006  every key number carries an in-enum source-tier label
    GS007  no coined label (`Medium-High`, `Mixed official + practitioner`)
    GS008  no snippet-as-fact phrasing ("according to search results")
    GS009  a Full verdict cites a source in a source-bearing position
    GS010  Standard/Deep cite two or more distinct source hosts
    GS011  a reusable query that was never executed is marked `not run`
    GS012  every query in the report is syntactically valid
    GS013  the report actually answers the question
    GS014  Standard/Deep state evidence-chain status
    GS015  Standard/Deep state key evidence
    GS016  Deep states source assessment
    GS017  one query does not declare two different engines in two places

  Docs -- lint_docs()
    GD001  no recommended query example uses an invalid qualifier
    GD002  the do-not-use table still names the invalid qualifiers (guards GD001)
    GD003  no coined confidence label in label position
    GD004  the Gate 3 Target Confidence column holds only enum values
    GD005  worked-example key numbers use only enum labels
    GD006  mode budgets agree across SKILL.md, query-patterns.md, ai-search-and-termination.md
    GD007  the source-tier enum is enumerated in exactly one file

Three rules deliberately return `unknown` instead of a pass, because the input does not let
them decide: GS003 and GS011 need an explicit executed-query list, and GQ012 needs to know
which GitHub engine a query targets. `language:go errgroup stars:>100` is a valid repository
search *and* the exact thing someone writes when they wanted code from popular projects and
did not know `stars:` is unavailable there; no property of the string separates those. So the
engine is declared by the author (`[github-code]` / `[github-repo]` before the query) or the
guess is reported. A check that cannot see its subject must say so instead of failing open.

Usage:
  python3 scripts/lint_search_report.py                      # lint the skill's own docs
  python3 scripts/lint_search_report.py report.md            # grade one output report
  python3 scripts/lint_search_report.py --self-test          # grade the linter itself
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SKILL_MD = SKILL_DIR / "SKILL.md"
REFS_DIR = SKILL_DIR / "references"

# ── Closed enums (canonical definition: references/source-evaluation.md) ─────────

CONFIDENCE = ("High", "Medium", "Low")
SOURCE_TIERS = (
    "Official",
    "Primary document/data",
    "Reputable third-party",
    "Practitioner report",
    "OSINT",
    "Adversary claim",
)
DEGRADATION = ("Full", "Partial", "Blocked")
MODES = ("Quick", "Standard", "Deep")

# mode -> (max executed queries, min reusable queries)
MODE_BUDGET = {"Quick": (2, 2), "Standard": (5, 3), "Deep": (8, 5)}

COINED_LABEL = re.compile(
    r"`?(?:Medium[-\s]?High|High[-\s]?Medium|Low[-\s]?Medium|Medium[-\s]?Low"
    r"|Mixed\s+[\w-]+(?:\s*\+\s*[\w-]+)+)`?",
    re.IGNORECASE,
)
NEGATION = re.compile(
    r"\b(?:not|never|no|do not|don't|avoid|instead of|rather than|forbidden|invalid|"
    r"is not a)\b",
    re.IGNORECASE,
)

# ── Operator vocabularies ───────────────────────────────────────────────────────

GOOGLE_DOCUMENTED = {"site", "filetype", "before", "after"}
GOOGLE_UNDOCUMENTED = {"intitle", "allintitle", "intext", "allintext", "inurl", "allinurl"}
GOOGLE_UNRELIABLE = {"related", "define", "imagesize"}
GOOGLE_REMOVED = {"link", "info", "cache"}
GOOGLE_OPERATORS = (
    GOOGLE_DOCUMENTED | GOOGLE_UNDOCUMENTED | GOOGLE_UNRELIABLE | GOOGLE_REMOVED
)

GITHUB_CODE_QUALIFIERS = {
    "repo", "org", "user", "enterprise", "language", "license",
    "path", "symbol", "content", "is",
}
GITHUB_REPO_QUALIFIERS = {
    "repo", "org", "user", "language", "license", "topic", "stars", "forks",
    "size", "created", "pushed", "followers", "help-wanted-issues",
    "good-first-issues", "archived", "is", "in", "mirror", "template", "fork",
}
GITHUB_LEGACY = {"filename": "path", "extension": "path or language"}

# Which engine a qualifier proves. SHARED proves nothing.
GITHUB_CODE_ONLY = GITHUB_CODE_QUALIFIERS - GITHUB_REPO_QUALIFIERS
GITHUB_REPO_ONLY = GITHUB_REPO_QUALIFIERS - GITHUB_CODE_QUALIFIERS
GITHUB_SHARED = GITHUB_CODE_QUALIFIERS & GITHUB_REPO_QUALIFIERS
GITHUB_ALL = GITHUB_CODE_QUALIFIERS | GITHUB_REPO_QUALIFIERS

ENGINES = ("google", "github-code", "github-repo")
ENGINE_TAG = re.compile(r"\[(google|github-code|github-repo)\]", re.IGNORECASE)

DATE_RE = re.compile(r"^\d{4}$|^(\d{4})([-/])(\d{1,2})\2(\d{1,2})$")
OPERATOR_RE = re.compile(r"(?<![\w/.])-?([A-Za-z][\w-]*):")

SNIPPET_AS_FACT = re.compile(
    r"according to (?:the )?search results"
    r"|search results (?:say|show|indicate|suggest)"
    r"|根据搜索结果"
    r"|搜索结果显示",
    re.IGNORECASE,
)


class Finding:
    """One rule violation. `severity` is error, warn, or unknown."""

    __slots__ = ("rule", "severity", "message", "where")

    def __init__(self, rule: str, message: str, severity: str = "error", where: str = ""):
        self.rule = rule
        self.severity = severity
        self.message = message
        self.where = where

    def __repr__(self) -> str:
        loc = f" [{self.where}]" if self.where else ""
        return f"{self.severity.upper()} {self.rule}{loc}: {self.message}"


# ── Text helpers ────────────────────────────────────────────────────────────────


def strip_fenced(text: str) -> str:
    """Blank fenced code blocks, preserving line count and offsets."""
    out, fenced = [], False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            out.append("")
            continue
        out.append("" if fenced else line)
    return "\n".join(out)


def strip_quoted(query: str) -> str:
    """Replace quoted spans with NULs so operators inside phrases are not parsed.

    Substituting rather than deleting keeps offsets and prevents two neighbouring
    tokens from fusing into a third that was never written.
    """
    return re.sub(r'"[^"]*"', lambda m: "\x00" * len(m.group(0)), query)


def logical_lines(text: str):
    """Yield logical units, joining markdown soft wraps but never merging a table row,
    list item, or heading into its neighbour.

    A hard-wrapped paragraph is one sentence to a human and must be one window to the
    linter: splitting on `\\n` would strand a negation ("Never invent ... ") on the line
    above the token it negates, and the rule would fire on the sentence forbidding the
    very thing it looks for.
    """
    buf: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        starts_unit = (
            not stripped
            or stripped.startswith(("|", "#", ">"))
            or re.match(r"^[-*+]\s|^\d+\.\s", stripped)
        )
        if starts_unit:
            if buf:
                yield " ".join(buf)
                buf = []
            if stripped:
                buf = [stripped]
        else:
            buf.append(stripped)
    if buf:
        yield " ".join(buf)


def sentences(text: str):
    for unit in logical_lines(text):
        for part in re.split(r"(?<=[.!?;])\s+", unit):
            if part.strip():
                yield part


def section(text: str, heading: str) -> str:
    """Return one markdown section's body, from its heading to the next heading of
    the same or higher level. Returns "" when the heading is absent."""
    m = re.search(rf"^(#{{1,6}})\s+{re.escape(heading)}\s*$", text, re.MULTILINE)
    if not m:
        return ""
    level = len(m.group(1))
    rest = text[m.end():]
    nxt = re.search(rf"^#{{1,{level}}}\s+\S", rest, re.MULTILINE)
    return rest[: nxt.start()] if nxt else rest


def table_rows(text: str):
    """Yield markdown table rows as lists of stripped cells, skipping separators."""
    for line in text.split("\n"):
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        yield cells


# ── Query syntax ────────────────────────────────────────────────────────────────


def detect_engine(query: str) -> str:
    """Classify which engine a query is written for.

    Returns one of ENGINES, or `github-ambiguous` / `github-conflict`.

    Detection is a *guess*, and for GitHub it is a guess about intent, not syntax:
    `language:go errgroup stars:>100` is a perfectly valid repository search, and also
    exactly what someone writes when they wanted popular projects' code and did not know
    `stars:` is unavailable in code search. Nothing in the string distinguishes the two.
    So a query carrying GitHub qualifiers must declare its engine; the caller passes it
    explicitly, or `validate_query` reports that it had to guess.
    """
    bare = strip_quoted(query)
    ops = {m.group(1).lower() for m in OPERATOR_RE.finditer(bare)}
    ops -= {"http", "https"}
    if ops & GOOGLE_OPERATORS:
        return "google"
    gh = ops & GITHUB_ALL
    if not gh and not (ops & set(GITHUB_LEGACY)):
        return "google"
    if (gh & GITHUB_CODE_ONLY) and (gh & GITHUB_REPO_ONLY):
        return "github-conflict"
    if gh & GITHUB_CODE_ONLY:
        return "github-code"
    if gh & GITHUB_REPO_ONLY:
        return "github-repo"
    if ops & set(GITHUB_LEGACY):
        # both engines reject these; report against code search, where they used to work
        return "github-code"
    return "github-ambiguous"


def validate_query(query: str, engine: str | None = None) -> list[Finding]:
    """Check one query string. `engine` is google, github-code, or github-repo.

    Passing `engine=None` means "I do not know" — the guess is reported as GQ012 rather
    than applied silently, because the two GitHub engines accept different qualifiers and
    picking one for the author hides the mismatch instead of surfacing it.
    """
    findings: list[Finding] = []
    where = query
    declared = engine is not None
    if not declared:
        engine = detect_engine(query)

    if engine == "github-conflict":
        findings.append(
            Finding(
                "GQ013",
                "mixes code-search-only and repository-search-only qualifiers; no single "
                "GitHub engine accepts this query",
                where=where,
            )
        )
        engine = "github-code"
    elif engine == "github-ambiguous":
        findings.append(
            Finding(
                "GQ012",
                "GitHub query is valid for both engines; declare it with [github-code] or "
                "[github-repo] so the qualifiers can be checked",
                "unknown",
                where,
            )
        )
        engine = "github-shared"
    elif not declared and engine.startswith("github"):
        findings.append(
            Finding(
                "GQ012",
                f"engine not declared; assuming {engine}. Tag the query [github-code] or "
                f"[github-repo] — the engines take different qualifiers",
                "unknown",
                where,
            )
        )

    if query.count('"') % 2:
        findings.append(Finding("GQ001", "unbalanced double quote", where=where))
    bare = strip_quoted(query)
    if bare.count("(") != bare.count(")"):
        findings.append(Finding("GQ002", "unbalanced parenthesis", where=where))

    for m in OPERATOR_RE.finditer(bare):
        op = m.group(1).lower()
        if op in ("http", "https"):
            continue
        arg = bare[m.end():]
        if arg[:1] == " ":
            findings.append(
                Finding("GQ003", f"`{op}:` has a space before its argument", where=where)
            )
        value = arg.split(" ")[0].strip("\x00")

        if engine == "google":
            if op in GOOGLE_REMOVED:
                findings.append(
                    Finding("GQ005", f"`{op}:` was removed by Google and returns nothing",
                            where=where)
                )
            elif op in GOOGLE_UNRELIABLE:
                sev = "error" if op == "imagesize" else "warn"
                rule = "GQ007" if op == "imagesize" else "GQ006"
                findings.append(
                    Finding(rule, f"`{op}:` is unreliable in web search", sev, where)
                )
            elif op in ("before", "after"):
                if not DATE_RE.match(value) or not _date_in_range(value):
                    findings.append(
                        Finding("GQ008", f"`{op}:{value}` is not a valid date", where=where)
                    )
            elif op not in GOOGLE_OPERATORS:
                findings.append(
                    Finding("GQ009", f"`{op}:` is not a Google operator", where=where)
                )
        elif engine == "github-code":
            if op in GITHUB_LEGACY:
                findings.append(
                    Finding(
                        "GQ010",
                        f"`{op}:` is not a GitHub code-search qualifier; "
                        f"use {GITHUB_LEGACY[op]}",
                        where=where,
                    )
                )
            elif op == "stars":
                findings.append(
                    Finding(
                        "GQ010",
                        "`stars:` is repository-search only; shortlist repos first, "
                        "then scope code search with repo:/org:",
                        where=where,
                    )
                )
            elif op not in GITHUB_CODE_QUALIFIERS:
                findings.append(
                    Finding("GQ009", f"`{op}:` is not a code-search qualifier", where=where)
                )
        elif engine == "github-repo":
            if op in GITHUB_CODE_ONLY:
                findings.append(
                    Finding("GQ011", f"`{op}:` is code-search only", where=where)
                )
            elif op in GITHUB_LEGACY:
                findings.append(
                    Finding("GQ010", f"`{op}:` is a legacy qualifier", where=where)
                )
            elif op not in GITHUB_REPO_QUALIFIERS:
                findings.append(
                    Finding("GQ009", f"`{op}:` is not a repository qualifier", where=where)
                )
        elif engine == "github-shared":
            # engine undeclared and unguessable: only qualifiers both engines accept can
            # be judged, so anything else is reported rather than assumed valid
            if op in GITHUB_LEGACY:
                findings.append(
                    Finding("GQ010", f"`{op}:` is a legacy qualifier", where=where)
                )
            elif op not in GITHUB_SHARED:
                findings.append(
                    Finding(
                        "GQ009",
                        f"`{op}:` is not accepted by both engines; declare which one",
                        where=where,
                    )
                )

    if re.search(r"(?:^|\s)\+\w", bare):
        findings.append(
            Finding("GQ005", "the `+` operator was removed; quote the term instead",
                    where=where)
        )
    terms = [t for t in re.split(r"\s+", bare) if t]
    if any(t == "or" for t in terms) and len(terms) > 1:
        findings.append(
            Finding("GQ004", "boolean OR must be uppercase", where=where)
        )
    return findings


def _date_in_range(value: str) -> bool:
    """Construct the date rather than range-checking its parts.

    A month/day range check accepts `2026-02-31`. And the bare-year form has to go through
    the same construction, or `after:0000` passes while `after:0000-01-01` fails — the same
    value expressed two ways getting two verdicts.
    """
    m = DATE_RE.match(value)
    if not m:
        return False
    year, month, day = (
        (int(m.group(1)), int(m.group(3)), int(m.group(4)))
        if m.group(1)
        else (int(value), 1, 1)
    )
    try:
        date(year, month, day)
    except ValueError:
        return False
    return True


# ── Output report ───────────────────────────────────────────────────────────────


def _field_value(text: str, label: str) -> str:
    """Value of an Output Contract field, whether written as a table row, a
    `Label: value` line, or a heading followed by a block."""
    for cells in table_rows(text):
        for i, cell in enumerate(cells):
            if re.search(rf"\*{{0,2}}{re.escape(label)}\*{{0,2}}", cell, re.IGNORECASE):
                tail = [c for c in cells[i + 1:] if c]
                if tail:
                    return " ".join(tail)
    # tolerate trailing words before the colon: the contract calls field 4 "Evidence chain
    # status", and a report may write "Sources opened:" or "Key evidence and gaps:"
    m = re.search(
        rf"^\s*(?:[-*]\s*)?\**{re.escape(label)}[^:：\n]{{0,24}}\**\s*[:：]\s*(.+)$",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    if m:
        return m.group(1).strip()
    body = section(text, label)
    if body:
        return body.strip()
    return ""


def _header_line(text: str):
    m = re.search(
        rf"^\**({'|'.join(MODES)})\**\s*[·|/]\s*\**({'|'.join(DEGRADATION)})\**",
        text,
        re.MULTILINE,
    )
    return (m.group(1), m.group(2)) if m else (None, None)


def _backticked(text: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"`([^`\n]+)`", text)]


def _split_items(text: str, seps: str = "\n,;·") -> list[str]:
    """Split a list of queries into items, never cutting inside a backticked span.

    A query may legitimately contain a comma, and splitting through it would leave two
    fragments with no complete backtick pair -- the query would then be skipped entirely
    and the rule would fail open on exactly the input it exists to check.
    """
    items, buf, in_ticks = [], [], False
    for ch in text:
        if ch == "`":
            in_ticks = not in_ticks
            buf.append(ch)
        elif ch in seps and not in_ticks:
            items.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    items.append("".join(buf))
    return [i for i in items if i.strip()]


def _looks_like_query(s: str) -> bool:
    if OPERATOR_RE.search(strip_quoted(s)):
        return True
    return len(s.split()) >= 3 or '"' in s


def _query_instances(text: str) -> list[tuple[str, str | None, str]]:
    """Every query *occurrence* as (query, declared engine or None, location).

    Deliberately not a `{query: engine}` dictionary. Keying on the query text lets one
    declaration vouch for the same query everywhere else in the report — tag the executed
    line and the untagged copy under Reusable queries inherits it — and a second occurrence
    silently overwrites the first, so which of two conflicting tags wins depends on document
    order. Each occurrence is checked where it stands.
    """
    out: list[tuple[str, str | None, str]] = []
    for lineno, line in enumerate(text.split("\n"), 1):
        # bind the tag to its own comma-separated item: a reusable list may declare one
        # query's engine and leave the next one undeclared
        for item in _split_items(line, ",;·"):
            m = ENGINE_TAG.search(item)
            engine = m.group(1).lower() if m else None
            for q in _backticked(item):
                if _looks_like_query(q):
                    out.append((q, engine, f"line {lineno}: {q}"))
    return out


HOST_IN_URL = re.compile(r"https?://([^/\s)\]`]+)")
HOST_IN_TICKS = re.compile(r"`([a-z0-9][a-z0-9.-]*\.[a-z]{2,})(?:/[^`]*)?`")
SOURCE_CONTEXT = re.compile(
    r"Key evidence|Sources?|Page[s]? opened|Opened|Cited|Retrieved|来源|已打开|引用",
    re.IGNORECASE,
)

# A field label is the label *plus its colon*. Matching the bare word would swallow a
# conclusion that happens to open with it ("Queries against the API are capped at 100/s"),
# and GS013 would then report a missing answer that is right there.
FIELD_LABEL = re.compile(
    r"^\s*(?:[-*]\s*)?\**(?:Round \d|已执行查询"
    r"|(?:Quer(?:y|ies)|Reusable queries|Key numbers|Evidence chain|Key evidence|"
    r"Source assessment|Source[s]?|Page[s]? opened|Execution mode|Degradation level|"
    r"Gates?|Conclusion|来源)[^:：\n]{0,24}[:：])",
    re.IGNORECASE,
)


def _hosts(text: str) -> set[str]:
    return {m.group(1).lower() for m in HOST_IN_URL.finditer(text)} | {
        m.group(1).lower() for m in HOST_IN_TICKS.finditer(text)
    }


def _prose_weight(text: str) -> float:
    """Rough content count that works for English and Chinese alike.

    Numbers count. For a factual question the number often *is* the answer — "The default is
    2." is complete — and a weight that ignored it would rank that below a longer sentence
    saying less.
    """
    stripped = re.sub(r"`[^`]*`", " ", text)
    stripped = re.sub(r"https?://\S+", " ", stripped)
    words = re.findall(r"[A-Za-z][A-Za-z'’-]+", stripped)
    numbers = re.findall(r"\b\d+\b", stripped)
    cjk = re.findall(r"[一-鿿]", stripped)
    return len(words) + len(numbers) + len(cjk) / 2


def _prose_residue(body: str) -> str:
    """Free prose left after removing structure: the header, query bullets, labeled
    fields, table rows, and bare URLs. What remains is where an unlabeled conclusion
    lives."""
    out = []
    for line in body.split("\n"):
        s = line.strip()
        if not s or s.startswith("|") or s.startswith("#"):
            continue
        if _header_line(s)[0] or FIELD_LABEL.match(s):
            continue
        if re.match(r"^\s*[-*]\s*(?:\[[a-z-]+\]\s*)?`", s):
            continue
        if re.fullmatch(r"(?:[-*]\s*)?https?://\S+", s):
            continue
        out.append(s)
    return " ".join(out)


def lint_report(text: str) -> list[Finding]:
    """Grade one search-report output against the Output Contract."""
    findings: list[Finding] = []
    body = strip_fenced(text)
    hdr_mode, hdr_deg = _header_line(body)

    mode = _field_value(body, "Execution mode") or hdr_mode or ""
    mode_name = next((m for m in MODES if m and m in mode), None)
    if not mode_name:
        findings.append(Finding("GS001", "no execution mode declared"))
    deg = _field_value(body, "Degradation level") or hdr_deg or ""
    deg_name = next((d for d in DEGRADATION if d in deg), None)
    if not deg_name:
        findings.append(Finding("GS002", "no degradation level declared"))

    reusable_block = _field_value(body, "Reusable queries")
    reusable = [q for q in _backticked(reusable_block) if _looks_like_query(q)]
    executed_lines = [
        line for line in body.split("\n")
        # an engine tag or a variant name may sit between the bullet and the query
        if re.search(
            r"^\s*[-*]\s*(?:\[[a-z-]+\]\s*)?(?:(?:Primary|Precision|Expansion)\s*[:：]\s*)?"
            r"(?:\[[a-z-]+\]\s*)?`",
            line,
            re.IGNORECASE,
        )
    ]
    executed = [q for q in _backticked("\n".join(executed_lines)) if _looks_like_query(q)]
    declared_rounds = bool(re.search(r"\*{0,2}Round \d|\bQueries\b|已执行查询", body))

    if mode_name:
        max_exec, min_reuse = MODE_BUDGET[mode_name]
        if not declared_rounds and not executed:
            findings.append(
                Finding(
                    "GS003",
                    "no executed-query list found, so the budget cannot be checked",
                    "unknown",
                )
            )
        elif len(executed) > max_exec:
            findings.append(
                Finding(
                    "GS003",
                    f"{len(executed)} executed queries exceeds the {mode_name} budget "
                    f"of {max_exec}",
                )
            )
        if len(reusable) < min_reuse:
            findings.append(
                Finding(
                    "GS004",
                    f"{len(reusable)} reusable queries, {mode_name} requires "
                    f"{min_reuse}",
                )
            )

    numbers = _field_value(body, "Key numbers")
    if numbers:
        # no comma separator here: a single entry contains one ("(`High`, `Official`)")
        for entry in _split_items(numbers, "\n;·"):
            if not entry.strip() or not re.search(r"\d", entry):
                continue
            labels = _backticked(entry)
            if not any(l in CONFIDENCE for l in labels):
                findings.append(
                    Finding("GS005", f"key number has no confidence label: {entry.strip()}")
                )
            if not any(l in SOURCE_TIERS for l in labels):
                findings.append(
                    Finding("GS006", f"key number has no source-tier label: {entry.strip()}")
                )

    for sent in sentences(body):
        for m in COINED_LABEL.finditer(sent):
            if NEGATION.search(sent):
                continue
            findings.append(
                Finding("GS007", f"coined label `{m.group(0).strip('`')}` is not in the enum")
            )

    for line in body.split("\n"):
        if "BAD:" in line or "Anti-example" in line:
            continue
        if SNIPPET_AS_FACT.search(line):
            findings.append(
                Finding("GS008", "snippet presented as a verified fact", where=line.strip())
            )

    # A URL somewhere in the text is not a citation. Only hosts appearing in a
    # source-bearing position count: a line that names its sources, or the Key evidence
    # field. Otherwise any stray link in a query or footer satisfies a `Full` verdict.
    hosts = _hosts(body)
    source_hosts: set[str] = _hosts(_field_value(body, "Key evidence"))
    for line in body.split("\n"):
        if SOURCE_CONTEXT.search(line):
            source_hosts |= _hosts(line)
    if deg_name == "Full" and not source_hosts:
        findings.append(
            Finding(
                "GS009",
                "Full degradation claimed with no source-bearing citation "
                "(name the page under Key evidence or as an opened source; a bare URL "
                "elsewhere in the text is not a citation)",
            )
        )
    if mode_name in ("Standard", "Deep") and len(hosts) < 2:
        findings.append(
            Finding(
                "GS010",
                f"{mode_name} mode cites {len(hosts)} source host(s), needs 2 independent",
            )
        )

    # Threshold separates "no answer" from "an answer", not "a short answer" from "a long
    # one". For a factual Quick question, "The default is 2." is a complete answer, so a
    # limit tuned to reject terse-but-correct output would fire on the good case.
    MIN_ANSWER_WEIGHT = 4
    conclusion = _field_value(body, "Conclusion")
    if _prose_weight(conclusion) < MIN_ANSWER_WEIGHT:
        residue = _prose_residue(body)
        if _prose_weight(residue) < MIN_ANSWER_WEIGHT:
            findings.append(
                Finding(
                    "GS013",
                    "no conclusion found — the report carries metadata and queries but "
                    "does not answer the question",
                )
            )
    if mode_name in ("Standard", "Deep"):
        if not _field_value(body, "Evidence chain").strip():
            findings.append(
                Finding(
                    "GS014",
                    f"{mode_name} mode requires evidence chain status (which links are "
                    f"satisfied, which are missing)",
                )
            )
        if not _field_value(body, "Key evidence").strip():
            findings.append(
                Finding(
                    "GS015",
                    f"{mode_name} mode requires key evidence (what each strongest source "
                    f"contributed)",
                )
            )
    if mode_name == "Deep" and not _field_value(body, "Source assessment").strip():
        findings.append(
            Finding(
                "GS016",
                "Deep mode requires source assessment (credibility, gaps, stale dates, "
                "disagreements, and why the confidence label is what it is)",
            )
        )

    def norm(q: str) -> str:
        return re.sub(r"\s+", " ", q).strip().lower()

    executed_norm = {norm(q) for q in executed}
    # Bind the `not run` marker to the item that carries the query. Accepting the marker
    # anywhere in the block would let one marked query vouch for every unmarked one.
    for item in _split_items(reusable_block):
        for q in _backticked(item):
            if not _looks_like_query(q) or norm(q) in executed_norm:
                continue
            if "not run" not in item.lower():
                findings.append(
                    Finding(
                        "GS011",
                        f"reusable query was never executed and is not marked "
                        f"`not run`: {q}",
                    )
                )

    instances = _query_instances(body)
    declared: dict[str, set[str]] = {}
    for q, engine, _ in instances:
        if engine:
            declared.setdefault(norm(q), set()).add(engine)
    for key, tags in declared.items():
        if len(tags) > 1:
            findings.append(
                Finding(
                    "GS017",
                    f"the same query declares conflicting engines "
                    f"({', '.join(sorted(tags))}): {key}",
                )
            )

    seen: set[tuple[str, str]] = set()
    for q, engine, where in instances:
        for f in validate_query(q, engine):
            key = (f.rule, f.message)
            if key in seen:      # identical verdict on a repeated occurrence
                continue
            seen.add(key)
            findings.append(
                Finding("GS012", f"{f.rule} in report query: {f.message}", f.severity, where)
            )
    return findings


# ── Docs ────────────────────────────────────────────────────────────────────────


def _recommended_examples(body: str) -> list[str]:
    """Query examples the doc *recommends*: bullet lines opening with a backticked
    query. Table rows are excluded, so a do-not-use table naming a bad qualifier
    does not trip the rule that forbids recommending it."""
    out = []
    for line in body.split("\n"):
        m = re.match(r"^\s*[-*]\s+`([^`]+)`", line)
        if m:
            out.append(m.group(1))
    return out


def lint_docs(overrides: dict[str, str] | None = None) -> list[Finding]:
    """Check the skill's own documentation.

    `overrides` maps a file's basename to replacement text. The mutation tests use it to
    reintroduce a defect and confirm the matching rule actually fires -- a rule that never
    fires on a broken input is not a check.
    """
    overrides = overrides or {}
    findings: list[Finding] = []

    def read(name: str) -> str:
        if name in overrides:
            return overrides[name]
        path = SKILL_MD if name == "SKILL.md" else REFS_DIR / name
        return path.read_text(encoding="utf-8")

    skill = read("SKILL.md")
    prog = read("programmer-search-patterns.md")
    qpat = read("query-patterns.md")
    aiterm = read("ai-search-and-termination.md")
    worked = read("worked-examples.md")
    srceval = read("source-evaluation.md")

    # GD001 / GD002 -- GitHub qualifier discipline
    gh = section(prog, "GitHub Code Search")
    if not gh:
        findings.append(Finding("GD001", "GitHub Code Search section is missing"))
    else:
        # Each subsection declares its engine, so examples are checked against the engine
        # the surrounding prose promises — not against a guess.
        for heading, engine in (
            ("Code search qualifiers", "github-code"),
            ("Repository search qualifiers", "github-repo"),
        ):
            body = section(gh, heading)
            if not body.strip():
                findings.append(Finding("GD001", f"missing subsection: {heading}"))
                continue
            for q in _recommended_examples(body):
                for f in validate_query(q, engine):
                    if f.rule in ("GQ009", "GQ010", "GQ011", "GQ013"):
                        findings.append(
                            Finding(
                                "GD001",
                                f"{heading}: recommended example uses {f.message}",
                                where=q,
                            )
                        )
        forbidden = section(gh, "Qualifiers that do NOT work in code search")
        for bad in ("filename:", "stars:"):
            if bad not in forbidden:
                findings.append(
                    Finding(
                        "GD002",
                        f"the do-not-use table no longer names `{bad}`, so GD001 would "
                        f"pass vacuously",
                    )
                )

    # GD003 -- coined confidence labels in label position
    for name, text in (
        ("SKILL.md", skill), ("worked-examples.md", worked),
        ("source-evaluation.md", srceval), ("query-patterns.md", qpat),
    ):
        for sent in sentences(strip_fenced(text)):
            for m in COINED_LABEL.finditer(sent):
                if NEGATION.search(sent):
                    continue
                findings.append(
                    Finding("GD003", f"coined label `{m.group(0).strip('`')}`", where=name)
                )

    # GD004 -- Gate 3 Target Confidence column is enum-only
    gate3 = section(skill, "3) Evidence Requirements Gate")
    seen_header = False
    for cells in table_rows(gate3):
        if not seen_header:
            seen_header = any("Target Confidence" in c for c in cells)
            continue
        if len(cells) >= 3 and cells[2] and cells[2] not in CONFIDENCE:
            findings.append(
                Finding("GD004", f"Target Confidence `{cells[2]}` is not in the enum")
            )
    if not seen_header:
        findings.append(Finding("GD004", "Gate 3 has no Target Confidence column"))

    # GD005 -- worked-example key numbers use enum labels only
    checked = 0
    for cells in table_rows(worked):
        if not any(re.search(r"Key numbers", c) for c in cells):
            continue
        value = cells[-1]
        for entry in re.split(r"\s·\s", value):
            labels = _backticked(entry)
            if not labels:
                continue
            checked += 1
            conf = [l for l in labels if l in CONFIDENCE]
            tier = [l for l in labels if l in SOURCE_TIERS]
            if not conf:
                findings.append(
                    Finding("GD005", f"key number without enum confidence: {entry.strip()}")
                )
            if not tier:
                findings.append(
                    Finding("GD005", f"key number without enum source tier: {entry.strip()}")
                )
    if not checked:
        findings.append(
            Finding("GD005", "no worked-example key numbers found to check", "unknown")
        )

    # GD006 -- mode budgets agree across files
    budgets = {}
    for mode, pat in (
        ("Quick", r"Quick:\s*max (\d+) quer"),
        ("Standard", r"Standard:\s*max (\d+) quer"),
        ("Deep", r"Deep:\s*max (\d+) quer"),
    ):
        m = re.search(pat, skill)
        if m:
            budgets[mode] = int(m.group(1))
    for mode, expected in MODE_BUDGET.items():
        if budgets.get(mode) != expected[0]:
            findings.append(
                Finding(
                    "GD006",
                    f"SKILL.md {mode} budget is {budgets.get(mode)}, linter expects "
                    f"{expected[0]}",
                )
            )
    qtable = {}
    for cells in table_rows(section(qpat, "Core Pattern Set")):
        if len(cells) >= 3 and cells[0] in MODE_BUDGET:
            m = re.search(r"(\d+)", cells[2])
            if m:
                qtable[cells[0]] = int(m.group(1))
    for mode, n in qtable.items():
        if n != MODE_BUDGET[mode][0]:
            findings.append(
                Finding("GD006", f"query-patterns.md {mode} executed cap is {n}, "
                                 f"SKILL.md says {MODE_BUDGET[mode][0]}")
            )
    m = re.search(r"Maximum:\s*(\d+) queries", aiterm)
    if not m:
        findings.append(Finding("GD006", "ai-search-and-termination.md states no maximum"))
    elif int(m.group(1)) != MODE_BUDGET["Deep"][0]:
        findings.append(
            Finding(
                "GD006",
                f"ai-search-and-termination.md maximum {m.group(1)} != Deep budget "
                f"{MODE_BUDGET['Deep'][0]}",
            )
        )

    # GD007 -- the source-tier enum lives in exactly one file
    enumerators = []
    for path in [SKILL_MD, *sorted(REFS_DIR.glob("*.md"))]:
        text = read(path.name)
        for para in re.split(r"\n\s*\n", text):
            hits = sum(1 for t in SOURCE_TIERS if t in para)
            if hits >= 4:
                enumerators.append(path.name)
                break
    if len(set(enumerators)) != 1:
        findings.append(
            Finding(
                "GD007",
                f"source-tier enum is enumerated in {sorted(set(enumerators)) or 'no'} "
                f"file(s); it must live in exactly one",
            )
        )
    elif enumerators[0] != "source-evaluation.md":
        findings.append(
            Finding("GD007", f"source-tier enum lives in {enumerators[0]}, "
                             f"expected source-evaluation.md")
        )
    return findings


# ── Self-test ───────────────────────────────────────────────────────────────────

ALL_RULES = (
    [f"GQ{n:03d}" for n in range(1, 14)]
    + [f"GS{n:03d}" for n in range(1, 18)]
    + [f"GD{n:03d}" for n in range(1, 8)]
)


def self_test() -> int:
    """Every rule must fire on a crafted violation and stay silent on a clean input."""
    cases: list[tuple[str, str, list[Finding]]] = []

    def q(rule, query, engine=None):
        cases.append((rule, query, validate_query(query, engine)))

    q("GQ001", 'site:go.dev "unterminated')
    q("GQ002", "(Redis OR Memcached site:redis.io")
    q("GQ003", "site: go.dev context")
    q("GQ004", "redis or memcached caching")
    q("GQ005", "link:github.com")
    q("GQ006", "related:github.com")
    q("GQ007", "wallpaper imagesize:3840x2160")
    q("GQ008", "Go 1.24 after:2025-13-99")
    q("GQ009", "foo:bar site:go.dev")
    q("GQ010", 'filename:go.mod "go-redis"', "github-code")
    q("GQ011", "symbol:WithContext stars:>500", "github-repo")
    q("GQ012", 'language:go "sync.Pool"')          # valid for both engines, undeclared
    q("GQ012", "language:go errgroup stars:>100")  # guessed engine, intent unknowable
    q("GQ013", 'path:go.mod stars:>100')           # no engine accepts both

    reports = {
        "GS001": "Degradation level: Full\nAnswer.\nReusable queries: `a b c`, `d e f`",
        "GS002": "Execution mode: Quick\nAnswer.\nReusable queries: `a b c`, `d e f`",
        "GS003": (
            "Quick · Full\nRound 1\n- `one two three`\n- `four five six`\n"
            "- `seven eight nine`\nReusable queries: `one two three`, `four five six`, "
            "`seven eight nine`"
        ),
        "GS004": "Quick · Full\nRound 1\n- `one two three`\nReusable queries: `one two three`",
        "GS005": (
            "Quick · Full\nRound 1\n- `one two three`\n- `four five six`\n"
            "Key numbers: default = 2 (`Official`)\n"
            "Reusable queries: `one two three`, `four five six`"
        ),
        "GS006": (
            "Quick · Full\nRound 1\n- `one two three`\n- `four five six`\n"
            "Key numbers: default = 2 (`High`)\n"
            "Reusable queries: `one two three`, `four five six`"
        ),
        "GS007": (
            "Quick · Full\nRound 1\n- `one two three`\n- `four five six`\n"
            "Confidence is `Medium-High` overall.\n"
            "Reusable queries: `one two three`, `four five six`"
        ),
        "GS008": (
            "Quick · Full\nRound 1\n- `one two three`\n- `four five six`\n"
            "According to search results the answer is X.\n"
            "Reusable queries: `one two three`, `four five six`"
        ),
        "GS009": (
            "Quick · Full\nRound 1\n- `one two three`\n- `four five six`\n"
            "Answer with no source.\nReusable queries: `one two three`, `four five six`"
        ),
        "GS010": (
            "Standard · Partial\nRound 1\n- `one two three`\n- `four five six`\n"
            "Source: https://go.dev/ref/spec\n"
            "Reusable queries: `one two three`, `four five six`, `seven eight nine` not run"
        ),
        "GS011": (
            "Quick · Full\nRound 1\n- `one two three`\nSource: https://go.dev/x\n"
            "Reusable queries: `one two three`, `never executed query`"
        ),
        "GS012": (
            "Quick · Full\nRound 1\n- `link:go.dev broken operator`\n- `four five six`\n"
            "Source: https://go.dev/x\n"
            "Reusable queries: `link:go.dev broken operator`, `four five six`"
        ),
        "GS013": (
            "Quick · Full\nRound 1\n- `one two three`\n- `four five six`\n"
            "Source: https://go.dev/x\n"
            "Reusable queries: `one two three`, `four five six`"
        ),
        "GS014": (
            "Standard · Partial\nThe pool size has no documented default beyond the "
            "knob semantics, so it must be measured under load.\n"
            "Round 1\n- `one two three`\n- `four five six`\n"
            "Key evidence: https://go.dev/x and https://dev.mysql.com/y\n"
            "Reusable queries: `one two three`, `four five six`, `seven eight nine` not run"
        ),
        "GS015": (
            "Standard · Partial\nThe pool size has no documented default beyond the "
            "knob semantics, so it must be measured under load.\n"
            "Round 1\n- `one two three`\n- `four five six`\n"
            "Evidence chain status: official basis satisfied, practitioner report missing\n"
            "Sources: https://go.dev/x and https://dev.mysql.com/y\n"
            "Reusable queries: `one two three`, `four five six`, `seven eight nine` not run"
        ),
        "GS017": (
            "Quick · Full\nerrgroup appears across most production Go services today.\n"
            "Round 1\n- [github-repo] `language:go errgroup stars:>=1000`\n"
            "- `errgroup site:go.dev`\nSource: https://pkg.go.dev/x\n"
            "Reusable queries: [github-code] `language:go errgroup stars:>=1000`, "
            "`errgroup site:go.dev`"
        ),
        "GS016": (
            "Deep · Partial\nThe three frameworks differ mostly under keep-alive load, "
            "and no benchmark published this year discloses its hardware.\n"
            "Round 1\n- `one two three`\n- `four five six`\n"
            "Evidence chain status: two benchmarks found, methodology undisclosed\n"
            "Key evidence: https://go.dev/x and https://dev.mysql.com/y\n"
            "Reusable queries: `one two three`, `four five six`, `seven eight nine` not run, "
            "`ten eleven twelve` not run, `thirteen fourteen fifteen` not run"
        ),
    }
    for rule, text in reports.items():
        cases.append((rule, f"report:{rule}", lint_report(text)))

    clean = (
        "Quick · Full\n"
        "Yes — pooled objects are collected by GC, and since Go 1.13 a victim cache keeps "
        "them for one extra cycle before that happens.\n"
        "Round 1\n"
        "- Precision: `sync.Pool GC behavior site:go.dev`\n"
        "- Primary: `Go sync.Pool garbage collection`\n"
        "Key numbers: victim cache survives 1 GC cycle (`High`, `Official`)\n"
        "Source: https://go.dev/src/sync/pool.go\n"
        "Reusable queries: `sync.Pool GC behavior site:go.dev`, "
        "`Go sync.Pool garbage collection`\n"
    )
    clean_findings = [f for f in lint_report(clean) if f.severity == "error"]

    failed = []
    for rule, subject, findings in cases:
        if not any(f.rule == rule for f in findings):
            failed.append(f"{rule} did not fire on {subject!r} -> {findings}")
    if clean_findings:
        failed.append(f"clean report produced errors: {clean_findings}")

    doc_findings = lint_docs()
    covered = {r for r, _, fs in cases for f in fs if f.rule == r}
    # GD rules are exercised by the doc mutations in tests/test_lint_mutations.py, which
    # feed lint_docs() overrides; the self-test only runs them against the live docs.
    doc_rules = {f"GD{n:03d}" for n in range(1, 8)}
    uncovered = sorted(set(ALL_RULES) - covered - doc_rules)
    if uncovered:
        failed.append(f"rules never exercised by self-test: {uncovered}")

    print(f"self-test: {len(cases)} crafted violations, {len(ALL_RULES)} rules")
    print(f"live docs: {len(doc_findings)} finding(s)")
    for f in doc_findings:
        print(f"  {f!r}")
    for msg in failed:
        print(f"FAIL {msg}")
    return 1 if failed or [f for f in doc_findings if f.severity == "error"] else 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    targets = [a for a in argv if not a.startswith("-")]
    if not targets:
        findings = lint_docs()
        label = "skill docs"
    else:
        findings = []
        for t in targets:
            findings += [
                Finding(f.rule, f.message, f.severity, f.where or t)
                for f in lint_report(Path(t).read_text(encoding="utf-8"))
            ]
        label = ", ".join(targets)
    errors = [f for f in findings if f.severity == "error"]
    if not findings:
        print(f"{label}: clean")
        return 0
    for f in findings:
        print(repr(f))
    print(f"{label}: {len(errors)} error(s), {len(findings) - len(errors)} other")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

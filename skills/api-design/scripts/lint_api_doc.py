#!/usr/bin/env python3
"""Deterministic linter for the api-design skill's own documentation.

Every rule here encodes a factual or structural property that was wrong at some
point and must not silently regress. Rules are checked against the real files,
not against fixtures, so a future edit that reintroduces an error fails CI.

Design constraints learned the hard way:

- Rules prefer *positive* shape checks ("the correct form is present and
  structurally located") over blocklists of wrong prose, because a blocklist
  fails open on rewording and fires on the sentence that explains the fix.
- Where a blocklist is unavoidable, the forbidden strings are exact historical
  phrasings that correct prose has no reason to contain, and the scan skips
  spans wrapped in an explicit allow sentinel.
- Masked spans are replaced character-for-character with NUL so neighbouring
  text cannot fuse and reported line numbers stay accurate.

Usage:
    python3 lint_api_doc.py [skill_dir]        # exit 1 if any finding
    python3 lint_api_doc.py --list-rules
"""

import pathlib
import re
import sys
from typing import Callable, Dict, List, NamedTuple

SKILL_FILES = ("SKILL.md",)
REF_GLOB = "references/*.md"

ALLOW_OPEN = re.compile(r"<!--\s*api-lint-allow:\s*(AD\d{3})\s*-->")
ALLOW_CLOSE = "<!-- /api-lint-allow -->"
ANCHOR = re.compile(r"<!--\s*api-lint:\s*([a-z0-9-]+)\s*-->")

REQUIRED_ANCHORS = {
    "delete-200-legal",
    "error-shape-agnostic",
    "denial-403-permitted",
    "lww-acceptable",
    "field-reorder-not-breaking",
}

# [S] was removed in the nature/severity split: "risk-gated" is a severity
# modifier, not a nature. Triggers now apply to any nature (see SKILL.md §2.2).
FORCE_TAGS = ("P", "D", "C")


class Finding(NamedTuple):
    rule: str
    path: str
    line: int
    message: str


class Doc(NamedTuple):
    path: str
    text: str
    prose: str  # fenced code blocks masked out
    code: str  # everything except fenced code blocks masked out


def _mask(text: str, spans: List[tuple]) -> str:
    """Replace each span with NUL of identical width, preserving newlines."""
    chars = list(text)
    for start, end in spans:
        for i in range(start, end):
            if chars[i] != "\n":
                chars[i] = "\x00"
    return "".join(chars)


def _fence_spans(text: str) -> List[tuple]:
    """Character spans covered by fenced code blocks, fences included."""
    spans = []
    open_at = None
    for m in re.finditer(r"^```.*$", text, re.MULTILINE):
        if open_at is None:
            open_at = m.start()
        else:
            spans.append((open_at, m.end()))
            open_at = None
    if open_at is not None:
        spans.append((open_at, len(text)))
    return spans


def _allow_spans(text: str, rule: str) -> List[tuple]:
    """Spans the author explicitly exempted from `rule`."""
    spans = []
    for m in ALLOW_OPEN.finditer(text):
        if m.group(1) != rule:
            continue
        close = text.find(ALLOW_CLOSE, m.end())
        end = len(text) if close == -1 else close + len(ALLOW_CLOSE)
        spans.append((m.start(), end))
    return spans


def line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def load_docs(skill_dir: pathlib.Path) -> Dict[str, Doc]:
    docs: Dict[str, Doc] = {}
    paths = [skill_dir / n for n in SKILL_FILES] + sorted(skill_dir.glob(REF_GLOB))
    for p in paths:
        text = p.read_text(encoding="utf-8")
        fences = _fence_spans(text)
        inverse = _invert(fences, len(text))
        rel = str(p.relative_to(skill_dir))
        docs[rel] = Doc(rel, text, _mask(text, fences), _mask(text, inverse))
    return docs


def _invert(spans: List[tuple], total: int) -> List[tuple]:
    out, cursor = [], 0
    for start, end in sorted(spans):
        if start > cursor:
            out.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < total:
        out.append((cursor, total))
    return out


def sections(text: str, level: str = "## ") -> Dict[str, str]:
    """Split markdown into {heading_text: body} at the given heading level."""
    out: Dict[str, str] = {}
    pattern = re.compile(r"^" + re.escape(level) + r"(.+)$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out[m.group(1).strip()] = text[m.end():end]
    return out


def find_section(text: str, needle: str, level: str = "## ") -> str:
    for title, body in sections(text, level).items():
        if needle in title:
            return body
    return ""


# Refuted claims, kept in one place so the fixture checker and the doc checker
# cannot drift apart. A verifier carrying its own copy of these patterns is
# always narrower than the tool it verifies.
CLAIM_BLOCKLIST = (
    ("AD002",
     ("semantically incorrect for DELETE",
      "200 with body is semantically incorrect",
      "Clients expect 204 No Content for successful deletion"),
     "RFC 9110 §9.3.5 permits 200 on a successful DELETE"),
    ("AD008",
     ("reorder fields in JSON/gRPC response structs",
      "Treat any struct field reorder in an API response type as a breaking change"),
     "a field reorder is non-breaking unless a named consumer parses positionally "
     "or a digest covers the raw body"),
)

# Status pairs the skill itself documents as a [D] choice. Writing "X (not Y)" or
# "must return X" re-freezes a convention into a mandate, which is how the 410/404
# and 422/400 statements survived two rounds of correction elsewhere in the doc.
STATUS_PAIR_MANDATES = (
    ("AD003", "404", "403", "authorization denial"),
    ("AD018", "410", "404", "a removed endpoint"),
    ("AD018", "422", "400", "a validation failure"),
)


# A status code is usually written with its reason phrase — "410 Gone (not 404)",
# "422 Unprocessable Content, not 400". The first version of this regex required the
# code and the parenthesis to be adjacent and therefore missed the exact sentence it
# was written to prevent. Allow the reason phrase between them.
_REASON = r"(?:\s+[A-Za-z][a-z]+){0,2}"


def _pair_regex(a: str, b: str) -> re.Pattern:
    return re.compile(
        rf"(must|always|MUST)\s+(?:return|use|answer\s+with)\s+{a}"
        rf"|{a}{_REASON}\s*\(\s*not\s+{b}{_REASON}\s*\)"
        rf"|{a}{_REASON}\s*,?\s+not\s+{b}",
        re.IGNORECASE)


def check_claims(text: str, path: str) -> List[Finding]:
    """Run the refuted-claim checks over one body of prose.

    `text` must already have code fences masked if the caller wants prose-only
    scoping; masking preserves offsets, so reported line numbers stay correct.
    Spans wrapped in an allow sentinel are exempted per rule, so a document can
    quote a wrong claim in order to correct it.
    """
    out: List[Finding] = []
    for rule, phrases, why in CLAIM_BLOCKLIST:
        haystack = _mask(text, _allow_spans(text, rule))
        for phrase in phrases:
            for m in re.finditer(re.escape(phrase), haystack, re.IGNORECASE):
                out.append(Finding(rule, path, line_of(text, m.start()),
                                   f"{why}: found {phrase!r}"))
    for rule, a, b, subject in STATUS_PAIR_MANDATES:
        scan = _mask(text, _allow_spans(text, rule))
        for m in _pair_regex(a, b).finditer(scan):
            out.append(Finding(rule, path, line_of(text, m.start()),
                               f"{a} for {subject} is a [D] convention, not a mandate — "
                               f"{b} stays conformant: found {m.group(0)!r}"))
    return out


def _claims_for(doc: Doc, rule: str) -> List[Finding]:
    """Phrase blocklists scan prose only — a fenced block may legitimately show a
    wrong example. Status-pair mandates scan the **whole** document: this skill
    writes its deprecation protocol inside a fence, and a mandate written there
    binds a reader exactly as hard as one written in a paragraph."""
    scope = doc.text if rule in {r for r, _, _, _ in STATUS_PAIR_MANDATES} else doc.prose
    return [f for f in check_claims(scope, doc.path) if f.rule == rule]


# --- Individual rules -------------------------------------------------------
# Each takes the docs mapping and returns a list of findings.


def ad001_deprecation_header_syntax(docs) -> List[Finding]:
    """RFC 9745 §2.1: Deprecation is an Item Structured Field of type Date."""
    out = []
    seen_valid = False
    for doc in docs.values():
        scan = _mask(doc.code, _allow_spans(doc.text, "AD001"))
        for m in re.finditer(r"^[ \t]*Deprecation:[ \t]*(\S.*?)[ \t]*$", scan, re.MULTILINE):
            value = m.group(1).strip()
            if re.fullmatch(r"@\d+", value):
                seen_valid = True
            else:
                out.append(Finding(
                    "AD001", doc.path, line_of(doc.text, m.start()),
                    f"Deprecation header value {value!r} is not an RFC 9745 "
                    "Structured Field Date (expected '@<unix-seconds>')"))
    if not seen_valid:
        out.append(Finding("AD001", "references/compatibility-rules.md", 0,
                           "no valid 'Deprecation: @<unix-seconds>' example is "
                           "documented anywhere in the skill"))
    return out


def ad002_delete_200_is_legal(docs) -> List[Finding]:
    """RFC 9110 §9.3.5 permits 200, 202 and 204 on a successful DELETE."""
    out = []
    ae = docs["references/api-anti-examples.md"]
    section = find_section(ae.text, "AE-10")
    if not section:
        return [Finding("AD002", ae.path, 0, "AE-10 section is missing")]
    if "9.3.5" not in section or "RFC 9110" not in section:
        out.append(Finding("AD002", ae.path, line_of(ae.text, ae.text.find("AE-10")),
                           "AE-10 must cite RFC 9110 §9.3.5 as the authority on "
                           "DELETE success status codes"))
    for code in ("200", "202", "204"):
        if code not in section:
            out.append(Finding("AD002", ae.path, 0,
                               f"AE-10 must state that {code} is a conformant "
                               "DELETE success status"))
    if not re.search(r"permit|conformant|legal|sanction", section, re.IGNORECASE):
        out.append(Finding("AD002", ae.path, 0,
                           "AE-10 must say the three status codes are permitted, "
                           "not merely list them"))
    for doc in docs.values():
        out += _claims_for(doc, "AD002")
    return out


def ad003_denial_status_is_a_choice(docs) -> List[Finding]:
    """OWASP sanctions both 403 and 404 for a denied request; only 200 is wrong."""
    out = []
    ae = docs["references/api-anti-examples.md"]
    section = find_section(ae.text, "AE-13")
    if not section:
        return [Finding("AD003", ae.path, 0, "AE-13 section is missing")]
    if "403" not in section or "404" not in section:
        out.append(Finding("AD003", ae.path, 0, "AE-13 must discuss both 403 and 404"))
    if not re.search(r"\bor\s+404\b|\beither\b|\bboth\b", section, re.IGNORECASE):
        out.append(Finding("AD003", ae.path, 0,
                           "AE-13 must present 403 and 404 as alternatives, not "
                           "mandate one"))
    for doc in docs.values():
        out += _claims_for(doc, "AD003")
    return out


def ad004_no_observability_in_error_body(docs) -> List[Finding]:
    """Metric names and audit subjects must not ship in the client contract."""
    out = []
    for doc in docs.values():
        scan = _mask(doc.code, _allow_spans(doc.text, "AD004"))
        for span_start, span_end in _fence_spans(scan):
            block = scan[span_start:span_end]
            if '"error"' not in block:
                continue
            for key in ('"metric"', '"audit"'):
                idx = block.find(key)
                if idx != -1:
                    out.append(Finding(
                        "AD004", doc.path, line_of(doc.text, span_start + idx),
                        f"{key} appears inside a client-facing error envelope; "
                        "observability data belongs in logs, joined on trace_id"))
        for m in re.finditer(r"X-Audit-[A-Za-z]+", scan):
            out.append(Finding("AD004", doc.path, line_of(doc.text, m.start()),
                               f"{m.group(0)} exposes audit state to the caller; "
                               "a response header is as public as a body field"))
    return out


def _checklist_items(skill_text: str):
    """Parse §6 items into (number, tag, title, scorecard_target)."""
    body = find_section(skill_text, "Design Checklist")
    pattern = re.compile(
        r"^(\d+)\.\s+\*\*\[([A-Z])\]\s+(.+?)\*\*\s*→\s*`([^`]+)`", re.MULTILINE)
    return [(int(m.group(1)), m.group(2), m.group(3), m.group(4))
            for m in pattern.finditer(body)], body


def _scorecard_tiers(skill_text: str) -> Dict[str, List[str]]:
    body = find_section(skill_text, "Scorecard")
    out: Dict[str, List[str]] = {}
    for title, tier_body in sections(body, "### ").items():
        tier = title.split("—")[0].strip()
        ids = re.findall(r"^- \[ \] `([A-Z]\d+)`", tier_body, re.MULTILINE)
        if ids:
            out[tier] = ids
    return out


def ad005_every_rule_is_tagged(docs) -> List[Finding]:
    """A rule without a force class gets applied at maximum severity by default."""
    skill = docs["SKILL.md"]
    items, body = _checklist_items(skill.text)
    out = []
    if not items:
        return [Finding("AD005", skill.path, 0, "no tagged checklist items parsed "
                                                "from §6 — the item format changed")]
    numbered = re.findall(r"^(\d+)\.\s+\*\*", body, re.MULTILINE)
    if len(numbered) != len(items):
        out.append(Finding("AD005", skill.path, 0,
                           f"{len(numbered)} numbered §6 items but only {len(items)} "
                           "carry a '[TAG] Title → `target`' header"))
    for num, tag, title, _ in items:
        if tag not in FORCE_TAGS:
            out.append(Finding("AD005", skill.path, 0,
                               f"§6 item {num} ({title}) has unknown force tag [{tag}]"))
    expected = list(range(1, len(items) + 1))
    if [n for n, _, _, _ in items] != expected:
        out.append(Finding("AD005", skill.path, 0,
                           "§6 item numbering is not contiguous from 1"))
    return out


def ad006_critical_tier_is_security_only(docs) -> List[Finding]:
    """Naming a cosmetic item Critical destroys the severity signal."""
    skill = docs["SKILL.md"]
    tiers = _scorecard_tiers(skill.text)
    critical_body = find_section(find_section(skill.text, "Scorecard"), "Critical", "### ")
    out = []
    if "Critical" not in tiers:
        return [Finding("AD006", skill.path, 0, "no Critical scorecard tier parsed")]
    if not re.search(r"object-level authorization", critical_body, re.IGNORECASE):
        out.append(Finding("AD006", skill.path, 0,
                           "Critical tier must contain object-level authorization"))
    cosmetic = re.compile(
        r"naming|kebab-case|plural noun|camelCase|OpenAPI|rate[- ]limit|pagination",
        re.IGNORECASE)
    m = cosmetic.search(critical_body)
    if m:
        out.append(Finding("AD006", skill.path,
                           line_of(skill.text, skill.text.find(critical_body) + m.start()),
                           f"cosmetic/contextual concern {m.group(0)!r} must not sit "
                           "in the Critical tier alongside authorization defects"))
    return out


def ad007_sunset_attribution(docs) -> List[Finding]:
    """Sunset is RFC 8594; RFC 7231 is obsoleted by RFC 9110."""
    out = []
    compat = docs["references/compatibility-rules.md"]
    if "RFC 8594" not in compat.text:
        out.append(Finding("AD007", compat.path, 0,
                           "Sunset header must be attributed to RFC 8594"))
    for doc in docs.values():
        scan = _mask(doc.text, _allow_spans(doc.text, "AD007"))
        for m in re.finditer(r"RFC\s*7231", scan):
            out.append(Finding("AD007", doc.path, line_of(doc.text, m.start()),
                               "RFC 7231 is obsolete (superseded by RFC 9110); "
                               "Sunset itself is defined by RFC 8594"))
    return out


def ad008_field_order_not_breaking(docs) -> List[Finding]:
    """RFC 8259 §1: a JSON object is an unordered collection."""
    out = []
    for name in ("SKILL.md", "references/compatibility-rules.md",
                 "references/api-anti-examples.md"):
        if "RFC 8259" not in docs[name].text:
            out.append(Finding("AD008", name, 0,
                               "field-order discussion must cite RFC 8259 (JSON "
                               "objects are unordered)"))
    compat = docs["references/compatibility-rules.md"]
    non_breaking = find_section(compat.text, "Non-Breaking Changes")
    breaking = find_section(compat.text, "Breaking Changes (Require")
    if not re.search(r"Reorder response fields", non_breaking, re.IGNORECASE):
        out.append(Finding("AD008", compat.path, 0,
                           "'Reorder response fields' must be listed as non-breaking "
                           "by default"))
    if re.search(r"^\|.*[Rr]eorder.*$", breaking, re.MULTILINE):
        m = re.search(r"^\|.*[Rr]eorder.*$", breaking, re.MULTILINE)
        out.append(Finding("AD008", compat.path, 0,
                           f"field reorder listed in the breaking-change table: "
                           f"{m.group(0).strip()[:70]!r}"))
    for doc in docs.values():
        out += _claims_for(doc, "AD008")
    return out


def ad009_scorecard_matches_checklist(docs) -> List[Finding]:
    """Two hand-maintained lists drift; bind them and derive the counts."""
    skill = docs["SKILL.md"]
    items, _ = _checklist_items(skill.text)
    tiers = _scorecard_tiers(skill.text)
    declared = [i for ids in tiers.values() for i in ids]
    targets = {t for _, _, _, t in items}
    out = []
    if len(declared) != len(set(declared)):
        out.append(Finding("AD009", skill.path, 0, "duplicate scorecard item ids"))
    for sid in declared:
        if sid not in targets:
            out.append(Finding("AD009", skill.path, 0,
                               f"scorecard item {sid} is not produced by any §6 "
                               "checklist item"))
    for target in sorted(targets):
        if target != "—" and target not in declared:
            out.append(Finding("AD009", skill.path, 0,
                               f"§6 item maps to unknown scorecard id {target!r}"))
    verdict = re.search(
        r"Critical:\s*`Y/(\d+)`;\s*Standard:\s*`Z/(\d+)`;\s*Hygiene:\s*`W/(\d+)`",
        skill.text)
    if not verdict:
        out.append(Finding("AD009", skill.path, 0, "verdict line format changed; "
                                                   "tier counts cannot be verified"))
    else:
        for tier, claimed in zip(("Critical", "Standard", "Hygiene"), verdict.groups()):
            actual = len(tiers.get(tier, []))
            if actual != int(claimed):
                out.append(Finding("AD009", skill.path,
                                   line_of(skill.text, verdict.start()),
                                   f"verdict line claims {claimed} {tier} items but "
                                   f"{actual} are listed"))
    total = re.search(r"\*\*Verdict\*\*:\s*`X/(\d+)`", skill.text)
    if total and int(total.group(1)) != len(declared):
        out.append(Finding("AD009", skill.path, line_of(skill.text, total.start()),
                           f"verdict total X/{total.group(1)} but {len(declared)} "
                           "scorecard items are listed"))
    return out


def ad010_no_contextual_rule_in_critical(docs) -> List[Finding]:
    """A [C] rule has no single correct answer, so it can never be a hard gate."""
    skill = docs["SKILL.md"]
    items, _ = _checklist_items(skill.text)
    tiers = _scorecard_tiers(skill.text)
    critical = set(tiers.get("Critical", []))
    out = []
    for num, tag, title, target in items:
        if target in critical and tag != "P":
            out.append(Finding("AD010", skill.path, 0,
                               f"§6 item {num} ({title}) is [{tag}] but feeds Critical "
                               f"item {target}; a Critical item may only be fed by [P] "
                               "invariants, because [D] and [C] findings depend on a "
                               "convention or a choice the API owner is entitled to make"))
    return out


def ad012_license_anchors_present(docs) -> List[Finding]:
    """False-positive fixtures bind to these anchors; deleting one must fail."""
    found = {}
    for doc in docs.values():
        for m in ANCHOR.finditer(doc.text):
            found.setdefault(m.group(1), []).append((doc.path, line_of(doc.text, m.start())))
    out = []
    for name in sorted(REQUIRED_ANCHORS - set(found)):
        out.append(Finding("AD012", "SKILL.md", 0,
                           f"required license anchor '{name}' is missing; the "
                           "false-positive fixture bound to it has nothing to cite"))
    for name, places in sorted(found.items()):
        if len(places) > 1:
            out.append(Finding("AD012", places[1][0], places[1][1],
                               f"license anchor '{name}' is declared {len(places)} "
                               "times; anchors must be unique"))
    return out


def ad013_cross_references_resolve(docs) -> List[Finding]:
    """Renumbering sections silently invalidates every pointer into them."""
    skill = docs["SKILL.md"]

    def labels(text: str) -> set:
        """Numeric labels of every heading, e.g. '6', '6.1', '9.1'. Headings
        inside fenced blocks count: the §9.x output sections live in a fence."""
        return set(re.findall(r"^#{2,4}\s+§?(\d+(?:\.\d+)*)\b", text, re.MULTILINE))

    skill_labels = labels(skill.text)
    items, checklist_body = _checklist_items(skill.text)
    item_numbers = {str(n) for n, _, _, _ in items}
    anti_examples = set(re.findall(r"###\s+AE-(\d+)", skill.text))
    for doc in docs.values():
        anti_examples |= set(re.findall(r"##\s+AE-(\d+)", doc.text))

    # "RFC 9110 §9.3.5" points into an RFC, not into this skill. Only bare
    # section marks are internal references.
    rfc_prefix = re.compile(r"RFC\s*\d{3,5}\s*$")

    out = []
    for doc in docs.values():
        # A reference resolves against its own document first (a reference file
        # numbers its own sections), then against SKILL.md.
        visible = labels(doc.text) | skill_labels
        for m in re.finditer(r"§(\d+(?:\.\d+)?)", doc.text):
            if rfc_prefix.search(doc.text[max(0, m.start() - 16):m.start()]):
                continue
            label = m.group(1)
            if label not in visible:
                out.append(Finding("AD013", doc.path, line_of(doc.text, m.start()),
                                   f"reference §{label} resolves to no heading in "
                                   f"{doc.path} or SKILL.md"))
        for m in re.finditer(r"\bitem (\d+)\b", doc.text):
            if m.group(1) not in item_numbers:
                out.append(Finding("AD013", doc.path, line_of(doc.text, m.start()),
                                   f"reference to §6 item {m.group(1)}, which does "
                                   "not exist"))
        for m in re.finditer(r"\bAE-(\d+)\b", doc.text):
            if m.group(1) not in anti_examples:
                out.append(Finding("AD013", doc.path, line_of(doc.text, m.start()),
                                   f"reference to AE-{m.group(1)}, which is defined "
                                   "nowhere"))
    return out


def ad017_triggers_are_declared_per_rule(docs) -> List[Finding]:
    """A rule that mentions Tn without declaring it leaves the §8.1 trigger column
    unscoped, so any live trigger anywhere reads as escalating any rule."""
    skill = docs["SKILL.md"]
    force = find_section(skill.text, "Rule Nature")
    defined = set(re.findall(r"^\|\s*\*\*(T\d)\*\*\s*\|", force, re.MULTILINE))
    body = find_section(skill.text, "Design Checklist")
    out = []
    if not defined:
        return [Finding("AD017", skill.path, 0, "no triggers defined in §2.2")]

    # Split §6 into per-item bodies so a declaration binds to its own rule.
    starts = [(m.group(1), m.start()) for m in
              re.finditer(r"^(\d+)\.\s+\*\*\[[A-Z]\]", body, re.MULTILINE)]
    declared_anywhere = set()
    for i, (num, start) in enumerate(starts):
        end = starts[i + 1][1] if i + 1 < len(starts) else len(body)
        chunk = body[start:end]
        header = chunk.split("\n", 1)[0]
        decl = re.search(r"\*Triggers:\s*([^*]+)\*", header)
        declared = set(re.findall(r"T\d", decl.group(1))) if decl else set()
        declared_anywhere |= declared
        for bad in sorted(declared - defined):
            out.append(Finding("AD017", skill.path, 0,
                               f"§6 item {num} declares {bad}, which §2.2 does not define"))
        mentioned = set(re.findall(r"\bT\d\b", chunk))
        for undeclared in sorted(mentioned - declared):
            out.append(Finding("AD017", skill.path, 0,
                               f"§6 item {num} reasons about {undeclared} but does not "
                               "declare it; add it to the rule's Triggers list"))
    for orphan in sorted(defined - declared_anywhere):
        out.append(Finding("AD017", skill.path, 0,
                           f"trigger {orphan} is defined in §2.2 but no rule declares it"))
    return out


def ad018_status_pair_mandates(docs) -> List[Finding]:
    """410-vs-404 and 422-vs-400 are [D] choices; the doc must not re-freeze them."""
    out = []
    for doc in docs.values():
        out += _claims_for(doc, "AD018")
    return out


def ad014_one_severity_source(docs) -> List[Finding]:
    """Two severity tables drift, and then no reviewer knows which one binds."""
    skill = docs["SKILL.md"]
    nature = find_section(skill.text, "Rule Nature")
    scorecard = find_section(skill.text, "Scorecard")
    out = []
    if not nature:
        return [Finding("AD014", skill.path, 0, "§2 Rule Nature section not found")]
    ceiling = re.search(r"max(?:imum)?[ \-]?(?:finding[ ]?)?severity", nature, re.IGNORECASE)
    if ceiling:
        out.append(Finding("AD014", skill.path,
                           line_of(skill.text, skill.text.find(nature) + ceiling.start()),
                           "§2 declares a severity ceiling; severity belongs only to the "
                           "§8.1 decision table"))
    if not re.search(r"^\| *\*\*\[P\]\*\* *\|", scorecard, re.MULTILINE):
        out.append(Finding("AD014", skill.path, 0,
                           "§8 has no severity decision table keyed by nature tag"))
    for verdict in ("FAIL", "WARN", "PASS", "N/A"):
        if verdict not in scorecard:
            out.append(Finding("AD014", skill.path, 0,
                               f"§8 severity table does not mention {verdict}"))
    return out


def ad015_sunset_uses_gmt_literal(docs) -> List[Finding]:
    """RFC 9110 §5.6.7: IMF-fixdate ends with the literal 'GMT'. RFC 9745 §4's own
    example prints 'UTC' and is non-conformant — do not copy it back in."""
    out = []
    seen_valid = False
    for doc in docs.values():
        scan = _mask(doc.code, _allow_spans(doc.text, "AD015"))
        for m in re.finditer(r"^[ \t]*Sunset:[ \t]*(\S.*?)[ \t]*$", scan, re.MULTILINE):
            value = m.group(1).strip()
            if value.endswith("GMT"):
                seen_valid = True
            else:
                out.append(Finding(
                    "AD015", doc.path, line_of(doc.text, m.start()),
                    f"Sunset value {value!r} does not end with the IMF-fixdate literal "
                    "'GMT' (RFC 9110 §5.6.7); 'UTC' is not conformant"))
    if not seen_valid:
        out.append(Finding("AD015", "references/compatibility-rules.md", 0,
                           "no conformant 'Sunset: ... GMT' example is documented"))
    return out


# Status codes whose companion header/body is optional in the spec. Presenting any
# of these as mandatory is the false-positive generator this rule exists to stop.
OPTIONAL_COMPANION_CODES = {
    "201": "RFC 9110 §15.3.2 — absent Location, the target URI identifies the resource",
    "202": "RFC 9110 §15.3.3 — the status monitor is 'ought to', not MUST",
    "422": "RFC 9110 §15.5.21 — 422 is not mandated for field validation",
    "429": "RFC 6585 §4 — Retry-After is MAY",
}


def ad016_optional_companions_not_mandatory(docs) -> List[Finding]:
    """A [D] recommendation printed in a MUST column becomes a reported defect."""
    skill = docs["SKILL.md"]
    body = find_section(skill.text, "Design Checklist")
    rows = {}
    for line in body.splitlines():
        m = re.match(r"^\s*\|[^|]*\|\s*(\d{3})\s*\|(.*)$", line)
        if m:
            rows.setdefault(m.group(1), []).append(m.group(2))
    out = []
    if not rows:
        return [Finding("AD016", skill.path, 0,
                        "no status-code table parsed from §6 — the format changed")]
    for code, why in OPTIONAL_COMPANION_CODES.items():
        if code not in rows:
            out.append(Finding("AD016", skill.path, 0,
                               f"status {code} dropped from the table; its optionality "
                               f"is no longer stated ({why})"))
            continue
        cells = " ".join(rows[code])
        if "[P]" in cells:
            out.append(Finding("AD016", skill.path, 0,
                               f"status {code} row is marked [P]; {why}"))
        if not re.search(r"\[D\]|MAY|ought to|not mandate|is not a violation|"
                         r"never fail|absent", cells, re.IGNORECASE):
            out.append(Finding("AD016", skill.path, 0,
                               f"status {code} row does not record that its companion is "
                               f"optional ({why})"))
    return out


RULES: Dict[str, Callable] = {
    "AD001": ad001_deprecation_header_syntax,
    "AD002": ad002_delete_200_is_legal,
    "AD003": ad003_denial_status_is_a_choice,
    "AD004": ad004_no_observability_in_error_body,
    "AD005": ad005_every_rule_is_tagged,
    "AD006": ad006_critical_tier_is_security_only,
    "AD007": ad007_sunset_attribution,
    "AD008": ad008_field_order_not_breaking,
    "AD009": ad009_scorecard_matches_checklist,
    "AD010": ad010_no_contextual_rule_in_critical,
    "AD012": ad012_license_anchors_present,
    "AD013": ad013_cross_references_resolve,
    "AD014": ad014_one_severity_source,
    "AD015": ad015_sunset_uses_gmt_literal,
    "AD016": ad016_optional_companions_not_mandatory,
    "AD017": ad017_triggers_are_declared_per_rule,
    "AD018": ad018_status_pair_mandates,
}

RULE_SUMMARY = {
    "AD001": "Deprecation header uses the RFC 9745 Structured Field Date form",
    "AD002": "a 200 response to DELETE is documented as RFC 9110-conformant",
    "AD003": "authorization denial status (403 vs 404) is a policy choice",
    "AD004": "no metric/audit observability data in the client-facing error body",
    "AD005": "every §6 checklist rule carries exactly one force tag",
    "AD006": "the Critical scorecard tier holds security/protocol items only",
    "AD007": "Sunset is attributed to RFC 8594, not obsolete RFC 7231",
    "AD008": "a JSON field reorder is non-breaking by default (RFC 8259)",
    "AD009": "scorecard ids, §6 targets and the stated tier counts agree",
    "AD010": "no [C] contextual rule gates a Critical scorecard item",
    "AD012": "every license anchor a false-positive fixture cites exists once",
    "AD013": "every §section, item and AE- cross-reference resolves",
    "AD014": "severity is defined in exactly one table (§8.1), not in §2",
    "AD015": "Sunset examples end with the IMF-fixdate literal GMT",
    "AD016": "spec-optional companions (201/202/422/429) are not shown as mandatory",
    "AD017": "triggers are declared per rule, defined in §2.2, and none is orphaned",
    "AD018": "410-vs-404 and 422-vs-400 stay [D] choices, never mandates",
}


def lint(skill_dir: pathlib.Path, only=None) -> List[Finding]:
    docs = load_docs(skill_dir)
    findings: List[Finding] = []
    for rule_id, fn in RULES.items():
        if only and rule_id not in only:
            continue
        findings += fn(docs)
    return sorted(findings, key=lambda f: (f.rule, f.path, f.line))


def main(argv: List[str]) -> int:
    if "--list-rules" in argv:
        for rule_id in sorted(RULES):
            print(f"{rule_id}\t{RULE_SUMMARY[rule_id]}")
        return 0
    positional = [a for a in argv[1:] if not a.startswith("-")]
    skill_dir = pathlib.Path(positional[0]) if positional else \
        pathlib.Path(__file__).resolve().parent.parent
    findings = lint(skill_dir)
    for f in findings:
        location = f"{f.path}:{f.line}" if f.line else f.path
        print(f"{f.rule}  {location}  {f.message}")
    if findings:
        print(f"\n{len(findings)} finding(s) across "
              f"{len({f.rule for f in findings})} rule(s).")
        return 1
    print(f"api-design doc lint clean ({len(RULES)} rules).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

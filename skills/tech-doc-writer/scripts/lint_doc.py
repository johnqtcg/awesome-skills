#!/usr/bin/env python3
"""Mechanical layer of the tech-doc-writer Quality Scorecard (Gate 3).

Deterministically checks the regex-decidable subset of the scorecard so the
judgment-based items are the only thing left to the model. Stdlib only.

Checks (severity in brackets):
  metadata        [critical]  frontmatter with owner + status + last_updated + title
  status-value    [critical]  status is draft|active|needs-update|deprecated
  date-format     [critical]  last_updated is a real YYYY-MM-DD calendar date
  fence-balance   [critical]  every opening code fence is closed
  table-cells     [critical for --type reference, warning otherwise]
                              no TBD/TODO/empty cells inside markdown tables
  single-h1       [warning]   exactly one H1 title
  title-weight    [warning]   H1 title within the language-aware budget, and free of
                              filler words (see TITLE_BUDGET / FILLER_RE)
  code-fence-lang [warning]   fenced code blocks carry a language tag
  pangu-spacing   [warning]   one space between CJK and Latin/digit runs
                              (inline code, fenced blocks, URLs exempt)
  applicable-versions [warning]  present when the doc names version-sensitive content

Usage:
  lint_doc.py <file.md> [--type concept|task|reference|troubleshooting|design]
              [--strict] [--scorecard]

`--scorecard` prints the applicable/N-A item counts and the ⅔ thresholds for the given
--type, so the scorecard denominator is computed rather than guessed.

Exit codes: 0 = no critical findings (warnings allowed unless --strict),
            1 = critical findings (or any finding with --strict),
            2 = file unreadable.
"""

from __future__ import annotations

import argparse
import datetime
import math
import re
import sys
from pathlib import Path

CRITICAL = "critical"
WARNING = "warning"

VALID_STATUS = {"draft", "active", "needs-update", "deprecated"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Title budget is language-aware: a CJK character carries far more information than a Latin
# one, so a single character threshold is not comparable across scripts. Budget is measured in
# "weight units" — 1 per CJK char, 0.5 per Latin char/digit — and a leading identifier
# (`RFC-042:`, `ADR-7:`, `[JIRA-12]`) is exempt because it aids search rather than padding.
TITLE_BUDGET = 20.0
IDENT_PREFIX_RE = re.compile(r"^\s*(?:\[[^\]]{1,20}\]|[A-Z]{2,10}[- ]?\d{1,5})\s*[:：-]\s*")
FILLER_RE = re.compile(
    r"(?i)\b(a|an|the|some|various|detailed|comprehensive|complete|simple|basic|"
    r"introduction to|overview of|notes on|thoughts on|things about)\b"
    r"|关于|简介|详解|浅谈|随笔"
)
# Version-sensitive content: if the body names a versioned dependency, the doc should declare
# which versions it applies to, or it silently rots.
VERSION_MENTION_RE = re.compile(
    r"(?i)\b(?:go|python|node(?:\.js)?|java|mysql|postgres(?:ql)?|redis|kafka|kubernetes|k8s|"
    r"docker|terraform)\s*v?\d+(?:\.\d+)+"
)
CJK = r"一-鿿㐀-䶿"
PANGU_RE = re.compile(rf"([{CJK}])([A-Za-z0-9])|([A-Za-z0-9])([{CJK}])")
# Path charset must be explicit ASCII: Python's \w matches CJK, so a \w-based
# pattern would treat prose like 读/写 as a "path" and swallow the surrounding
# CJK text — masking real pangu violations on any line containing a slash.
URL_RE = re.compile(r"https?://\S+|[A-Za-z0-9._~-]*(?:/[A-Za-z0-9._~-]+)+")
TBD_RE = re.compile(r"^\s*(TBD|TODO|待定|待补充)?\s*$", re.IGNORECASE)


class Finding:
    def __init__(self, check: str, severity: str, line: int, message: str):
        self.check = check
        self.severity = severity
        self.line = line
        self.message = message

    def __str__(self) -> str:
        return f"[{self.severity}] {self.check} (line {self.line}): {self.message}"


def split_frontmatter(text: str) -> tuple[dict, str, int]:
    """Return (frontmatter dict, body, body line offset)."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return {}, text, 0
    fm: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if line.lstrip().startswith("#"):
            continue  # whole-line YAML comment
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            value = value.strip()
            # YAML allows a trailing comment. Without stripping it, `status: draft  # notes`
            # was read as the literal value `draft  # notes` and rejected as invalid — which
            # made every annotated template fail its own metadata check. Only strip when the
            # value is unquoted, so a legitimate `#` inside a quoted string survives.
            if value[:1] not in {'"', "'"}:
                value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
            fm[key.strip()] = value.strip("\"'")
    offset = match.group(0).count("\n")
    return fm, text[match.end():], offset


def strip_code(body: str) -> list[tuple[int, str]]:
    """Return (line_no, line) pairs with fenced blocks and inline code blanked."""
    out: list[tuple[int, str]] = []
    in_fence = False
    for i, line in enumerate(body.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            out.append((i, ""))
            continue
        if in_fence:
            out.append((i, ""))
            continue
        line = re.sub(r"`[^`]*`", "", line)
        line = URL_RE.sub("", line)
        out.append((i, line))
    return out


def check_metadata(fm: dict) -> list[Finding]:
    findings = []
    # `title` is in the Phase 5 template, so it is required like the rest of the block.
    for field in ("title", "owner", "status", "last_updated"):
        if field not in fm or not fm[field]:
            findings.append(Finding("metadata", CRITICAL, 1, f"frontmatter missing `{field}`"))
    if "status" in fm and fm["status"] and fm["status"] not in VALID_STATUS:
        findings.append(Finding(
            "status-value", CRITICAL, 1,
            f"status {fm['status']!r} not in {sorted(VALID_STATUS)}"))
    raw = fm.get("last_updated", "")
    if raw:
        if not DATE_RE.match(raw):
            findings.append(Finding(
                "date-format", CRITICAL, 1,
                f"last_updated {raw!r} is not YYYY-MM-DD"))
        else:
            # Shape alone is not enough: `2026-99-99` matched the old regex and passed,
            # so a stale-date audit could never rely on this field.
            try:
                datetime.date.fromisoformat(raw)
            except ValueError:
                findings.append(Finding(
                    "date-format", CRITICAL, 1,
                    f"last_updated {raw!r} is not a real calendar date"))
    return findings


def check_fence_balance(body: str, offset: int) -> list[Finding]:
    """An unclosed fence silently swallows the rest of the document — every later check that
    skips fenced content stops seeing anything, so this must be critical."""
    findings = []
    open_line = None
    for i, line in enumerate(body.splitlines(), 1):
        if line.strip().startswith("```"):
            open_line = None if open_line is not None else i
    if open_line is not None:
        findings.append(Finding(
            "fence-balance", CRITICAL, offset + open_line,
            "code fence opened here is never closed — the rest of the document is "
            "treated as code by every downstream check"))
    return findings


def check_applicable_versions(fm: dict, body: str, offset: int) -> list[Finding]:
    if fm.get("applicable_versions"):
        return []
    for line_no, line in strip_code(body):
        m = VERSION_MENTION_RE.search(line)
        if m:
            return [Finding(
                "applicable-versions", WARNING, offset + line_no,
                f"body pins a version ({m.group(0)!r}) but frontmatter has no "
                "`applicable_versions` — the doc cannot be audited for staleness")]
    return []


def title_weight(title: str) -> float:
    """Language-aware length: CJK 1.0, Latin/digit 0.5, leading identifier exempt."""
    core = IDENT_PREFIX_RE.sub("", title)
    weight = 0.0
    for ch in core:
        if re.match(rf"[{CJK}]", ch):
            weight += 1.0
        elif ch.isalnum():
            weight += 0.5
    return weight


SEPARATOR_CELL_RE = re.compile(r"^:?-{3,}:?$")


def is_separator_row(line: str) -> bool:
    """True only for a genuine markdown alignment row.

    The previous test was `^\\s*\\|[\\s:|-]+\\|\\s*$`. Because that character class admits
    spaces and pipes, an entirely **blank data row** — `|   |   |   |` — matched it and was
    skipped, so a parameter table with no values filled in produced no findings at all and
    sailed through the Critical completeness gate for reference docs. Every cell must now
    actually look like `---`, `:---`, `---:` or `:---:`.
    """
    stripped = line.strip()
    if not stripped.startswith("|"):
        return False
    cells = [c.strip() for c in stripped.strip("|").split("|")]
    return bool(cells) and all(SEPARATOR_CELL_RE.match(c) for c in cells)


def check_tables(body: str, offset: int, severity: str) -> list[Finding]:
    findings = []
    in_fence = False
    for i, line in enumerate(body.splitlines(), 1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not line.lstrip().startswith("|"):
            continue
        if is_separator_row(line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        for cell in cells:
            if TBD_RE.match(cell) and cell != "":
                findings.append(Finding(
                    "table-cells", severity, offset + i,
                    f"table cell is a placeholder: {cell!r}"))
            elif cell == "" and len(cells) > 1:
                findings.append(Finding(
                    "table-cells", severity, offset + i, "empty table cell"))
    return findings


def check_headings(body: str, offset: int) -> list[Finding]:
    findings = []
    h1_lines = []
    in_fence = False
    for i, line in enumerate(body.splitlines(), 1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence and re.match(r"^#\s+\S", line):
            h1_lines.append((i, line.lstrip("# ").strip()))
    if len(h1_lines) != 1:
        findings.append(Finding(
            "single-h1", WARNING, offset + (h1_lines[1][0] if len(h1_lines) > 1 else 1),
            f"expected exactly 1 H1, found {len(h1_lines)}"))
    if h1_lines:
        line_no, title = h1_lines[0]
        weight = title_weight(title)
        if weight > TITLE_BUDGET:
            findings.append(Finding(
                "title-weight", WARNING, offset + line_no,
                f"title weight {weight:.1f} > {TITLE_BUDGET:.0f} "
                f"(CJK 1.0/char, Latin 0.5/char, ID prefix exempt): {title!r}"))
        filler = FILLER_RE.search(IDENT_PREFIX_RE.sub("", title))
        if filler:
            findings.append(Finding(
                "title-weight", WARNING, offset + line_no,
                f"title contains filler {filler.group(0)!r} — SPA wants searchable keywords, "
                f"not padding: {title!r}"))
    return findings


def check_code_fences(body: str, offset: int) -> list[Finding]:
    findings = []
    in_fence = False
    for i, line in enumerate(body.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            if not in_fence and stripped == "```":
                findings.append(Finding(
                    "code-fence-lang", WARNING, offset + i,
                    "fenced code block without language tag"))
            in_fence = not in_fence
    return findings


def check_pangu(body: str, offset: int) -> list[Finding]:
    findings = []
    for line_no, line in strip_code(body):
        match = PANGU_RE.search(line)
        if match:
            findings.append(Finding(
                "pangu-spacing", WARNING, offset + line_no,
                f"missing space between CJK and Latin: ...{match.group(0)}..."))
    return findings


def lint(text: str, doc_type: str | None = None) -> list[Finding]:
    fm, body, offset = split_frontmatter(text)
    # Scorecard marks complete tables as Critical for reference docs only.
    table_severity = CRITICAL if doc_type == "reference" else WARNING
    findings = []
    findings += check_metadata(fm)
    findings += check_fence_balance(body, offset)
    findings += check_tables(body, offset, table_severity)
    findings += check_headings(body, offset)
    findings += check_code_fences(body, offset)
    findings += check_pangu(body, offset)
    findings += check_applicable_versions(fm, body, offset)
    return findings


# Scorecard applicability, mirroring the tags in SKILL.md § Gate 3. Kept here so the
# denominator is computed rather than eyeballed: a fixed "4/6" was unreachable for concept,
# reference and design docs.
SCORECARD = {
    "Critical": [
        ("commands runnable / snippet marked", {"task", "troubleshooting", "concept"}, None),
        ("每步有预期输出与验证 / expected output + verification", {"task", "troubleshooting"}, None),
        ("metadata owner+last_updated+status", "all", None),
        ("terminology consistent", "all", None),
        ("param tables complete", {"reference"}, None),
    ],
    "Standard": [
        ("conclusion first", "all", None),
        ("prerequisites complete", {"task", "troubleshooting"}, None),
        ("rollback documented", {"task"}, None),
        ("title follows SPA", "all", None),
        ("code examples self-contained", {"task", "troubleshooting", "reference"}, None),
        ("error codes documented", {"reference"}, "api doc"),
    ],
    "Hygiene": [
        ("diagrams titled + legend", "all", "diagrams present"),
        ("cross-references", "all", None),
        ("structured info in lists/tables", "all", None),
        ("applicable_versions present", "all", "version-sensitive"),
        ("maintenance triggers noted", {"task", "troubleshooting"}, None),
        ("prevention thresholds", {"troubleshooting"}, None),
    ],
}


def scorecard_report(doc_type: str | None) -> str:
    """Print applicable / N-A counts and the ⅔ threshold for each tier."""
    t = doc_type or "unspecified"
    lines = [f"scorecard applicability for --type {t}:"]
    for tier, items in SCORECARD.items():
        applicable, conditional, na = [], [], []
        for name, types, condition in items:
            in_scope = types == "all" or (doc_type in types if doc_type else True)
            if not in_scope:
                na.append(name)
            elif condition:
                conditional.append(f"{name} (only if {condition})")
            else:
                applicable.append(name)
        if tier == "Critical":
            verdict = (f"all {len(applicable)} applicable must pass"
                       f"{f'; {len(conditional)} conditional' if conditional else ''}")
        else:
            base = len(applicable)
            need = math.ceil(base * 2 / 3) if base else 0
            verdict = (f"need {need}/{base} applicable (⅔ rounded up)" if base
                       else "n/a (0 applicable) — passes trivially")
            if conditional:
                verdict += f"; +{len(conditional)} conditional count only when the condition holds"
        lines.append(f"  {tier:9s} applicable={len(applicable)} conditional={len(conditional)} "
                     f"n/a={len(na)} -> {verdict}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file")
    parser.add_argument("--type", default=None, dest="doc_type",
                        choices=["concept", "task", "reference", "troubleshooting", "design"],
                        help="doc type; table-cells is critical for reference, warning otherwise")
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 on warnings too")
    parser.add_argument("--scorecard", action="store_true",
                        help="print applicable/N-A scorecard counts and thresholds")
    args = parser.parse_args(argv)

    path = Path(args.file)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"cannot read {path}: {exc}", file=sys.stderr)
        return 2

    findings = lint(text, args.doc_type)
    for f in findings:
        print(f)

    criticals = [f for f in findings if f.severity == CRITICAL]
    warnings = [f for f in findings if f.severity == WARNING]
    print(f"lint_doc: {len(criticals)} critical, {len(warnings)} warning(s)")
    if args.scorecard:
        print(scorecard_report(args.doc_type))
    if criticals or (args.strict and warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
#!/usr/bin/env python3
"""Mechanical layer of the tech-doc-writer Quality Scorecard (Gate 3).

Deterministically checks the regex-decidable subset of the scorecard so the
judgment-based items are the only thing left to the model. Stdlib only.

Checks (severity in brackets):
  metadata        [critical]  frontmatter with owner + status + last_updated
  status-value    [critical]  status is draft|active|needs-update|deprecated
  date-format     [critical]  last_updated is YYYY-MM-DD
  table-cells     [critical for --type reference, warning otherwise]
                              no TBD/TODO/empty cells inside markdown tables
  single-h1       [warning]   exactly one H1 title
  title-length    [warning]   H1 title <= 20 characters (SPA principle)
  code-fence-lang [warning]   fenced code blocks carry a language tag
  pangu-spacing   [warning]   one space between CJK and Latin/digit runs
                              (inline code, fenced blocks, URLs exempt)

Usage:
  lint_doc.py <file.md> [--type concept|task|reference|troubleshooting|design]
              [--strict]

Exit codes: 0 = no critical findings (warnings allowed unless --strict),
            1 = critical findings (or any finding with --strict),
            2 = file unreadable.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

CRITICAL = "critical"
WARNING = "warning"

VALID_STATUS = {"draft", "active", "needs-update", "deprecated"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
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
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip().strip("\"'")
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
    for field in ("owner", "status", "last_updated"):
        if field not in fm or not fm[field]:
            findings.append(Finding("metadata", CRITICAL, 1, f"frontmatter missing `{field}`"))
    if "status" in fm and fm["status"] and fm["status"] not in VALID_STATUS:
        findings.append(Finding(
            "status-value", CRITICAL, 1,
            f"status {fm['status']!r} not in {sorted(VALID_STATUS)}"))
    if "last_updated" in fm and fm["last_updated"] and not DATE_RE.match(fm["last_updated"]):
        findings.append(Finding(
            "date-format", CRITICAL, 1,
            f"last_updated {fm['last_updated']!r} is not YYYY-MM-DD"))
    return findings


def check_tables(body: str, offset: int, severity: str) -> list[Finding]:
    findings = []
    in_fence = False
    for i, line in enumerate(body.splitlines(), 1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not line.lstrip().startswith("|"):
            continue
        if re.match(r"^\s*\|[\s:|-]+\|\s*$", line):  # separator row
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
        if len(title) > 20:
            findings.append(Finding(
                "title-length", WARNING, offset + line_no,
                f"title is {len(title)} chars (> 20, SPA principle): {title!r}"))
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
    findings += check_tables(body, offset, table_severity)
    findings += check_headings(body, offset)
    findings += check_code_fences(body, offset)
    findings += check_pangu(body, offset)
    return findings


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file")
    parser.add_argument("--type", default=None, dest="doc_type",
                        choices=["concept", "task", "reference", "troubleshooting", "design"],
                        help="doc type; table-cells is critical for reference, warning otherwise")
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 on warnings too")
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
    if criticals or (args.strict and warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
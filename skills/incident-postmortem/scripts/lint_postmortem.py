#!/usr/bin/env python3
"""Mechanical layer of the post-mortem Scorecard (§8).

Deterministically checks the regex-decidable subset of the scorecard so the
judgment-based items (root-cause depth, systemic vs individual framing) are
the only thing left to the reviewer. Stdlib only.

Checks (severity in brackets):
  timeline-utc      [critical]  timeline entries carry HH:MM (or ISO) UTC stamps
  timeline-source   [critical]  every timeline entry names its source in parens
  action-owner      [critical]  every action item names an owner (@handle)
  action-deadline   [critical]  every action item carries a deadline
  action-categories [warning]   prevent / detect / mitigate all appear
  went-well         [warning]   a "What Went Well" section exists
  uncovered-risks   [warning]   an "Uncovered Risks" section exists
  blame-language    [warning]   conservative blame-phrase scan

Usage:
  lint_postmortem.py <postmortem.md> [--strict]

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

TIMELINE_HEADING_RE = re.compile(r"(?mi)^#{1,4}\s+.*timeline")
ACTION_HEADING_RE = re.compile(r"(?mi)^#{1,4}\s+.*action items?")
ENTRY_RE = re.compile(r"(?m)^\s*[-|]?\s*(\d{4}-\d{2}-\d{2}[T ])?\d{2}:\d{2}")
SOURCE_RE = re.compile(r"\([^)]+\)\s*$")
OWNER_RE = re.compile(r"owner:\s*@?\w+", re.IGNORECASE)
DEADLINE_RE = re.compile(r"deadline:\s*\S+|\d{4}-\d{2}-\d{2}|"
                         r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}",
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
]


class Finding:
    def __init__(self, check: str, severity: str, line: int, message: str):
        self.check, self.severity, self.line, self.message = check, severity, line, message

    def __str__(self) -> str:
        return f"[{self.severity}] {self.check} (line {self.line}): {self.message}"


def section(text: str, heading_re: re.Pattern) -> tuple[int, str] | None:
    """Return (start_line, body) of the first matching section, or None."""
    m = heading_re.search(text)
    if not m:
        return None
    start = m.end()
    nxt = re.search(r"(?m)^#{1,4}\s+", text[start:])
    body = text[start:start + nxt.start()] if nxt else text[start:]
    return text[:m.start()].count("\n") + 1, body


def check_timeline(text: str) -> list[Finding]:
    sec = section(text, TIMELINE_HEADING_RE)
    if sec is None:
        return [Finding("timeline-utc", CRITICAL, 1, "no Timeline section found")]
    line0, body = sec
    findings = []
    entries = [(i, ln) for i, ln in enumerate(body.splitlines(), line0)
               if ln.strip().startswith(("-", "|")) and not re.match(r"^\s*\|[\s:|-]+\|\s*$", ln)
               and ln.strip() not in ("|", "")]
    timed = [(i, ln) for i, ln in entries if ENTRY_RE.match(ln)]
    if not timed:
        findings.append(Finding("timeline-utc", CRITICAL, line0,
                                "timeline has no HH:MM-stamped entries"))
    for i, ln in timed:
        if not SOURCE_RE.search(ln.rstrip()):
            findings.append(Finding("timeline-source", CRITICAL, i,
                                    f"entry has no (source): {ln.strip()[:60]!r}"))
    return findings


def check_actions(text: str) -> list[Finding]:
    sec = section(text, ACTION_HEADING_RE)
    if sec is None:
        return [Finding("action-owner", CRITICAL, 1, "no Action Items section found")]
    line0, body = sec
    findings = []
    items = [(i, ln) for i, ln in enumerate(body.splitlines(), line0)
             if re.match(r"^\s*[-*]\s+\S", ln)]
    for i, ln in items:
        if not OWNER_RE.search(ln):
            findings.append(Finding("action-owner", CRITICAL, i,
                                    f"action item without owner: {ln.strip()[:60]!r}"))
        if not DEADLINE_RE.search(ln):
            findings.append(Finding("action-deadline", CRITICAL, i,
                                    f"action item without deadline: {ln.strip()[:60]!r}"))
    lowered = body.lower()
    missing = [c for c in ("prevent", "detect", "mitigate") if c not in lowered]
    if missing:
        findings.append(Finding("action-categories", WARNING, line0,
                                f"categories missing: {', '.join(missing)}"))
    return findings


def check_sections_and_blame(text: str) -> list[Finding]:
    findings = []
    if not re.search(r"(?mi)^#{1,4}\s+.*what went well", text):
        findings.append(Finding("went-well", WARNING, 1, "no 'What Went Well' section"))
    if not re.search(r"(?mi)^#{1,4}\s+.*uncovered risks", text):
        findings.append(Finding("uncovered-risks", WARNING, 1, "no 'Uncovered Risks' section"))
    for i, ln in enumerate(text.splitlines(), 1):
        low = ln.lower()
        for phrase in BLAME_PHRASES:
            if phrase in low:
                findings.append(Finding("blame-language", WARNING, i,
                                        f"blame phrase {phrase!r} — reframe to system/process"))
    return findings


def lint(text: str) -> list[Finding]:
    return check_timeline(text) + check_actions(text) + check_sections_and_blame(text)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        text = Path(args.file).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"cannot read {args.file}: {exc}", file=sys.stderr)
        return 2
    findings = lint(text)
    for f in findings:
        print(f)
    criticals = [f for f in findings if f.severity == CRITICAL]
    warnings = [f for f in findings if f.severity == WARNING]
    print(f"lint_postmortem: {len(criticals)} critical, {len(warnings)} warning(s)")
    return 1 if criticals or (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
"""finlib.report_audit — does the report faithfully carry the consolidated findings?

The previous gate checked only that each finding's **ID appeared as a substring**
of `report.md`. That catches a *dropped* finding and nothing else: keep the ID and
rewrite the evidence, soften the implication, or swap the citation, and the bundle
still passed. "Faithful synthesis" was unfalsifiable in exactly the direction that
matters — a report can distort what a worker found far more easily than it can
lose it.

This module parses the report's Worker Findings section and diffs it field by field
against `consolidated.json`. It is possible because the Output Format already
promises the shape and the provenance:

    ### [High] Short title
    - **ID**: `BUS-11`
    - **Citation**: 10-K Note 1 (FY2025)
    - **Evidence**: <verbatim from the worker>
    - **Implication**: <verbatim from the worker>

`Evidence` and `Implication` are specified as coming *from the worker*, so the gate
holds the report to that: the worker's text must be present, not paraphrased. The
report may add surrounding prose; it may not replace the quote.

CLI:
    python3 report_audit.py check --report run/report.md --consolidated run/consolidated.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys

# A finding block: an h3 whose text opens with a bracketed severity.
_BLOCK = re.compile(
    r"^###\s+\[(?P<severity>High|Medium|Low)\]\s*(?P<title>.*?)\s*$",
    re.M,
)
# `- **Key**: value`, value continuing until the next bullet or heading.
_FIELD = re.compile(
    r"^-\s+\*\*(?P<key>ID|Citation|Evidence|Implication)\*\*\s*:\s*(?P<value>.*?)"
    r"(?=^\s*-\s+\*\*|^#{2,4}\s|\Z)",
    re.M | re.S,
)

FIELDS = ("ID", "Citation", "Evidence", "Implication")


def normalize(text: str) -> str:
    """Collapse whitespace and drop markdown emphasis / code fencing.

    The report is allowed to wrap a long quote across lines, bold a number, or put
    an ID in backticks. None of that changes what it asserts, so none of it should
    make the diff fire.
    """
    text = re.sub(r"[`*_]", "", str(text))
    text = text.replace(" ", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_findings(report: str) -> list[dict]:
    """Extract the finding blocks. Returns [{severity, title, ID, Citation, ...}]."""
    blocks: list[dict] = []
    matches = list(_BLOCK.finditer(report))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(report)
        body = report[match.end():end]
        # Stop at the next h2 — the Findings section has ended.
        next_section = re.search(r"^##\s", body, re.M)
        if next_section:
            body = body[:next_section.start()]
        entry = {
            "severity": match.group("severity"),
            "title": normalize(match.group("title")),
            "_raw": body,
        }
        for field in _FIELD.finditer(body):
            entry[field.group("key")] = normalize(field.group("value"))
        blocks.append(entry)
    return blocks


def _id_of(block: dict) -> str | None:
    raw = block.get("ID")
    if not raw:
        return None
    # The ID line may carry a trailing parenthetical note.
    match = re.match(r"([A-Z]+-\d+[a-z]?)", raw)
    return match.group(1) if match else raw.split()[0] if raw.split() else None


def audit(consolidated: dict, report: str) -> list[str]:
    """Diff the report's finding blocks against the consolidated working set."""
    errors: list[str] = []
    findings = consolidated.get("findings") or []
    blocks = parse_findings(report)

    by_id: dict[str, list[dict]] = {}
    for block in blocks:
        fid = _id_of(block)
        if fid is None:
            errors.append(
                f"report block '{block['title'][:60]}' has no **ID** line, so it cannot be"
                f" traced to a worker finding"
            )
            continue
        by_id.setdefault(fid, []).append(block)

    expected_ids = {f.get("id") for f in findings if f.get("id")}

    for fid, dupes in sorted(by_id.items()):
        if len(dupes) > 1:
            errors.append(f"report renders finding {fid} {len(dupes)} times")
        if fid not in expected_ids:
            errors.append(
                f"report renders finding {fid}, which is not in consolidated.json —"
                f" a finding no worker returned"
            )

    for finding in findings:
        fid = finding.get("id")
        if not fid:
            continue
        matched = by_id.get(fid)
        if not matched:
            errors.append(
                f"report omits finding {fid} ({finding.get('severity')}:"
                f" {str(finding.get('title'))[:50]}) — surviving evidence was dropped"
            )
            continue
        block = matched[0]

        for field in ("Citation", "Evidence", "Implication"):
            if field not in block:
                errors.append(f"{fid}: report block has no **{field}** line")

        if block["severity"] != finding.get("severity"):
            errors.append(
                f"{fid}: report shows severity {block['severity']},"
                f" consolidated says {finding.get('severity')}"
            )

        # Evidence and Implication are specified as coming from the worker, so the
        # worker's text must be present verbatim — paraphrase is distortion here.
        for field, key in (("Evidence", "evidence"), ("Implication", "implication")):
            want = normalize(finding.get(key, ""))
            got = block.get(field)
            if not want or got is None:
                continue
            if want not in got:
                errors.append(
                    f"{fid}: report {field.lower()} does not carry the worker's text."
                    f"\n      worker: {want[:110]}"
                    f"\n      report: {got[:110]}"
                )

        citation = finding.get("citation") or {}
        locator = normalize(citation.get("locator", ""))
        got_citation = block.get("Citation")
        if locator and got_citation is not None and locator not in got_citation:
            errors.append(
                f"{fid}: report citation {got_citation[:80]!r} does not contain the"
                f" worker's locator {locator[:60]!r}"
            )

    return errors


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="audit report.md against consolidated.json")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--report", required=True)
    c.add_argument("--consolidated", required=True)
    args = ap.parse_args(argv)

    with open(args.consolidated, encoding="utf-8") as f:
        consolidated = json.load(f)
    with open(args.report, encoding="utf-8") as f:
        report = f.read()

    errors = audit(consolidated, report)
    print(json.dumps({
        "report": args.report,
        "verdict": "PASS" if not errors else "FAIL",
        "findings_expected": len(consolidated.get("findings") or []),
        "blocks_parsed": len(parse_findings(report)),
        "errors": errors,
    }, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())

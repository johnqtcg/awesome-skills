"""Mechanically verify the quotations in each run's answer against live pages.

Both arms are measured by the same code. The output format is deliberately not
constrained this time — the previous evaluation asked both arms for a fixed
`url ||| excerpt` shape, which made the measurement easy but also told the
baseline what to produce. Here each run writes whatever it thinks is right and
this script finds the URLs and the quoted spans on its own.

A quote counts as verified if it appears on any page that run cited. That is
looser than pairing each quote to its own URL, and it is the loose direction on
purpose: it cannot manufacture a difference between the arms, only understate
one.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

SKILL = Path("/Users/john/awesome-skills/skills/deep-research")
spec = importlib.util.spec_from_file_location("dr_v", SKILL / "scripts/deep_research.py")
dr = importlib.util.module_from_spec(spec)
sys.modules["dr_v"] = dr
spec.loader.exec_module(dr)

URL_RE = re.compile(r"https?://[^\s)\]\}>\"'`,;]+")
# Quoted spans worth checking: straight or curly double quotes, and markdown
# blockquote lines. Anything under 40 characters is too short to be evidence.
QUOTE_RES = [
    re.compile(r'"([^"\n]{40,400})"'),
    re.compile(r"[“]([^”\n]{40,400})[”]"),
    re.compile(r"(?m)^\s*>\s?(.{40,400})$"),
    re.compile(r"`([^`\n]{40,400})`"),
    # Single-quoted spans. The skill's own reports quote source wording with
    # single quotes, and omitting this pattern scored a run as having no
    # quotations at all when it had several genuine ones. The length floor and
    # the letter-ratio filter below keep ordinary apostrophes out.
    re.compile(r"(?<![A-Za-z])'([^'\n]{40,400})'(?![A-Za-z])"),
    re.compile(r"[‘]([^’\n]{40,400})[’]"),
]


def loose(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").casefold()).strip()


def extract(md: str) -> tuple[list[str], list[str]]:
    urls, quotes = [], []
    for m in URL_RE.finditer(md):
        urls.append(dr.normalize_url(m.group(0).rstrip(".,;:")) or m.group(0))
    for rx in QUOTE_RES:
        for m in rx.finditer(md):
            q = m.group(1).strip()
            # A span that is mostly a URL or a table row is not a quotation;
            # counting it would measure the extractor rather than the answer.
            if not q or q.startswith("|") or "---" in q:
                continue
            if "http" in q or q.count("|") >= 2:
                continue
            letters = sum(ch.isalpha() or ch.isspace() for ch in q)
            if letters / len(q) < 0.6:
                continue
            quotes.append(q)
    return list(dict.fromkeys(urls)), list(dict.fromkeys(quotes))


def main() -> int:
    root = Path(sys.argv[1])
    answers = sorted(root.glob("eval-*/*/outputs/answer.md"))
    print(f"grading {len(answers)} answers", file=sys.stderr)

    all_urls = set()
    parsed = {}
    for path in answers:
        md = path.read_text(encoding="utf-8", errors="replace")
        urls, quotes = extract(md)
        parsed[str(path)] = {"urls": urls, "quotes": quotes, "chars": len(md)}
        all_urls.update(urls)

    pages = {}
    urls = sorted(all_urls)
    for i in range(0, len(urls), 6):
        for item in dr.fetch_contents_parallel(
            urls[i:i + 6], timeout=30, max_workers=6,
            max_bytes=dr.VALIDATION_MAX_BYTES, max_chars=dr.VALIDATION_MAX_CHARS,
        ):
            pages[dr.normalize_url(item.url) or item.url] = item
    print(f"fetched {len(pages)} of {len(urls)} cited pages", file=sys.stderr)

    out = []
    for path, rec in parsed.items():
        haystack = " ".join(
            loose(pages[u].content) for u in rec["urls"]
            if u in pages and not pages[u].error and pages[u].content.strip()
        )
        fetched = sum(1 for u in rec["urls"] if u in pages and not pages[u].error
                      and pages[u].content.strip())
        verified = [q for q in rec["quotes"] if loose(q) and loose(q) in haystack]
        parts = Path(path).parts
        out.append({
            "eval": parts[-4], "arm": parts[-3], "chars": rec["chars"],
            "urls": len(rec["urls"]), "urls_fetchable": fetched,
            "quotes": len(rec["quotes"]), "quotes_verified": len(verified),
            "verified_rate": round(len(verified) / len(rec["quotes"]), 3) if rec["quotes"] else None,
            "unverified_examples": [q[:90] for q in rec["quotes"] if q not in verified][:3],
        })
    out.sort(key=lambda r: (r["eval"], r["arm"]))
    (root / "quote_verification.json").write_text(json.dumps(out, indent=2))
    print(f"\n{'eval':42}{'arm':14}{'urls':>6}{'ok':>4}{'quotes':>8}{'verif':>7}{'rate':>7}")
    for r in out:
        print(f"{r['eval'][:41]:42}{r['arm']:14}{r['urls']:>6}{r['urls_fetchable']:>4}"
              f"{r['quotes']:>8}{r['quotes_verified']:>7}{str(r['verified_rate']):>7}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

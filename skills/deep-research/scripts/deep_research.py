#!/usr/bin/env python3
"""Deep research helper: retrieval, dedup, validation, content extraction, codebase search, and report generation."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import html
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "spm",
}

AUTHORITATIVE_SUFFIXES = (".gov", ".edu")
NEWS_HINTS = ("news", "reuters", "bloomberg", "bbc", "apnews", "ft.com", "wsj.com")
ACADEMIC_HINTS = ("arxiv.org", "acm.org", "ieee.org", "springer", "nature.com", "sciencedirect")
FORUM_HINTS = ("reddit.com", "ycombinator.com", "stackoverflow.com")
BLOG_HINTS = ("medium.com", "dev.to", "substack.com", "hashnode")

KNOWN_MULTI_PART_TLDS = {
    "co.uk", "org.uk", "me.uk", "ac.uk", "gov.uk", "net.uk",
    "com.au", "net.au", "org.au", "edu.au", "gov.au",
    "co.jp", "ne.jp", "or.jp", "ac.jp", "go.jp",
    "co.kr", "or.kr", "ne.kr", "go.kr",
    "com.br", "org.br", "net.br", "gov.br", "edu.br",
    "com.cn", "net.cn", "org.cn", "gov.cn", "edu.cn",
    "co.nz", "net.nz", "org.nz", "govt.nz",
    "co.in", "net.in", "org.in", "gov.in", "ac.in",
    "co.za", "org.za", "net.za", "gov.za",
    "com.mx", "org.mx", "gob.mx", "edu.mx",
    "co.il", "org.il", "gov.il", "ac.il",
    "com.sg", "org.sg", "edu.sg", "gov.sg",
    "com.hk", "org.hk", "edu.hk", "gov.hk",
    "com.tw", "org.tw", "net.tw", "edu.tw", "gov.tw",
    "co.th", "or.th", "go.th", "ac.th",
    "com.tr", "org.tr", "edu.tr", "gov.tr",
    "co.id", "or.id", "go.id", "ac.id",
    "com.my", "org.my", "edu.my", "gov.my",
    "com.ph", "org.ph", "edu.ph", "gov.ph",
    "com.vn", "org.vn", "edu.vn", "gov.vn",
    "com.ar", "org.ar", "edu.ar", "gov.ar",
    "com.co", "org.co", "edu.co", "gov.co",
    "co.ke", "or.ke", "go.ke", "ac.ke",
    "com.ng", "org.ng", "edu.ng", "gov.ng",
    "com.ua", "org.ua", "edu.ua", "gov.ua",
    "com.pl", "org.pl", "edu.pl", "gov.pl",
    "com.eg", "org.eg", "edu.eg", "gov.eg",
    "co.ug", "or.ug", "go.ug", "ac.ug",
}

STRIP_TAGS_RE = re.compile(r"<(script|style|noscript|head)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_COLLAPSE_RE = re.compile(r"[ \t]+")
BLANK_LINES_RE = re.compile(r"\n{3,}")

DEFAULT_REQUEST_DELAY = 1.0
CONTENT_FETCH_WORKERS = 4
CONTENT_MAX_BYTES = 512_000
CONTENT_MAX_CHARS = 15_000


@dataclass
class SearchResult:
    query: str
    title: str
    url: str
    normalized_url: str
    domain: str
    source_type: str
    snippet: str = ""
    date: str = ""


@dataclass
class ContentResult:
    url: str
    title: str
    content: str
    word_count: int
    error: str = ""


# ---------------------------------------------------------------------------
# URL utilities
# ---------------------------------------------------------------------------

def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def normalize_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""

    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower() if parsed.hostname else ""
    port = parsed.port
    if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
        host = f"{hostname}:{port}"
    else:
        host = hostname

    path = re.sub(r"//+", "/", parsed.path or "/")
    if path != "/" and path.endswith("/"):
        path = path[:-1]

    query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
    cleaned_pairs = []
    for k, v in query_pairs:
        lk = k.lower()
        if lk.startswith("utm_") or lk in TRACKING_PARAMS:
            continue
        cleaned_pairs.append((k, v))
    query = urllib.parse.urlencode(sorted(cleaned_pairs)) if cleaned_pairs else ""

    normalized = urllib.parse.urlunparse((scheme, host, path, "", query, ""))
    return normalized


def registrable_domain(hostname: str) -> str:
    """Extract the registrable domain, respecting known multi-part TLDs like .co.uk."""
    host = (hostname or "").lower().strip(".")
    if not host:
        return ""
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    two_part_suffix = ".".join(parts[-2:])
    if two_part_suffix in KNOWN_MULTI_PART_TLDS:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def infer_source_type(hostname: str) -> str:
    host = (hostname or "").lower()
    if any(host.endswith(s) for s in AUTHORITATIVE_SUFFIXES):
        return "official"
    if any(h in host for h in ACADEMIC_HINTS):
        return "academic"
    if any(h in host for h in NEWS_HINTS):
        return "news"
    if any(h in host for h in FORUM_HINTS):
        return "forum"
    if any(h in host for h in BLOG_HINTS):
        return "blog"
    if "docs." in host or host.startswith("docs."):
        return "official"
    return "website"


# ---------------------------------------------------------------------------
# DuckDuckGo parsing
# ---------------------------------------------------------------------------

def decode_duck_link(href: str) -> str:
    raw = html.unescape(href or "").strip()
    if not raw:
        return ""

    if raw.startswith("//"):
        return "https:" + raw

    if raw.startswith("/"):
        parsed = urllib.parse.urlparse("https://duckduckgo.com" + raw)
        uddg = urllib.parse.parse_qs(parsed.query).get("uddg", [""])[0]
        return urllib.parse.unquote(uddg) if uddg else ""

    if "duckduckgo.com/l/?" in raw:
        parsed = urllib.parse.urlparse(raw)
        uddg = urllib.parse.parse_qs(parsed.query).get("uddg", [""])[0]
        return urllib.parse.unquote(uddg) if uddg else ""

    return raw


def _extract_snippets(html_text: str) -> Dict[str, str]:
    """Best-effort snippet extraction from DDG lite result page.

    DDG lite uses table rows; snippets appear in <td class="result-snippet">.
    Returns a mapping from decoded link URL to snippet text.
    """
    snippets: Dict[str, str] = {}
    row_pattern = re.compile(
        r'<a[^>]+href="([^"]+)"[^>]*>.*?</a>.*?'
        r'<td[^>]*class="result-snippet"[^>]*>(.*?)</td>',
        re.IGNORECASE | re.DOTALL,
    )
    for m in row_pattern.finditer(html_text):
        href = m.group(1)
        snippet_html = m.group(2)
        snippet = re.sub(r"<[^>]+>", "", snippet_html)
        snippet = html.unescape(snippet).strip()
        decoded = decode_duck_link(href)
        if decoded and snippet:
            snippets[decoded] = snippet[:500]

    if not snippets:
        # Fallback: try to grab plain-text blocks near links
        simple_pattern = re.compile(
            r'<a[^>]+href="([^"]+)"[^>]*>[^<]*</a>\s*(?:<[^>]*>\s*)*([^<]{40,})',
            re.IGNORECASE,
        )
        for m in simple_pattern.finditer(html_text):
            href = m.group(1)
            text = html.unescape(m.group(2)).strip()
            decoded = decode_duck_link(href)
            if decoded and text and decoded not in snippets:
                snippets[decoded] = text[:500]

    return snippets


def parse_duckduckgo_lite(html_text: str, query: str, limit: int) -> List[SearchResult]:
    snippets_map = _extract_snippets(html_text)
    pattern = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
    results: List[SearchResult] = []
    seen_urls: set = set()

    for match in pattern.finditer(html_text):
        href = match.group(1)
        title_raw = re.sub(r"<[^>]+>", "", match.group(2))
        title = html.unescape(title_raw).strip()
        decoded = decode_duck_link(href)
        normalized = normalize_url(decoded)
        if not normalized or normalized in seen_urls:
            continue
        domain = registrable_domain(urllib.parse.urlparse(normalized).hostname or "")
        if not domain:
            continue
        if not title:
            title = normalized

        seen_urls.add(normalized)
        snippet = snippets_map.get(decoded, "")

        results.append(
            SearchResult(
                query=query,
                title=title,
                url=decoded,
                normalized_url=normalized,
                domain=domain,
                source_type=infer_source_type(domain),
                snippet=snippet,
            )
        )
        if len(results) >= limit:
            break

    return results


def fetch_duckduckgo_lite(query: str, limit: int, timeout: float) -> List[SearchResult]:
    encoded = urllib.parse.urlencode({"q": query})
    url = f"https://lite.duckduckgo.com/lite/?{encoded}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; deep-research/1.0)",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="ignore")
    return parse_duckduckgo_lite(body, query, limit)


def dedupe_results(results: Sequence[SearchResult]) -> List[SearchResult]:
    seen = set()
    deduped: List[SearchResult] = []
    for item in results:
        if item.normalized_url in seen:
            continue
        seen.add(item.normalized_url)
        deduped.append(item)
    return deduped


# ---------------------------------------------------------------------------
# HTML content extraction
# ---------------------------------------------------------------------------

def extract_text_from_html(raw_html: str, max_chars: int = CONTENT_MAX_CHARS) -> str:
    """Strip scripts/style/tags and return readable text."""
    text = STRIP_TAGS_RE.sub(" ", raw_html)
    text = TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = WHITESPACE_COLLAPSE_RE.sub(" ", text)
    text = BLANK_LINES_RE.sub("\n\n", text)
    text = text.strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "..."
    return text


def fetch_page_content(url: str, timeout: float = 15.0, max_bytes: int = CONTENT_MAX_BYTES) -> ContentResult:
    """Fetch a URL and return extracted text content."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; deep-research/1.0)",
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(max_bytes).decode("utf-8", errors="ignore")
    except Exception as exc:
        return ContentResult(url=url, title="", content="", word_count=0, error=str(exc))

    title = ""
    title_match = re.search(r"<title[^>]*>(.*?)</title>", raw, re.IGNORECASE | re.DOTALL)
    if title_match:
        title = html.unescape(re.sub(r"<[^>]+>", "", title_match.group(1))).strip()

    text = extract_text_from_html(raw)
    word_count = len(text.split())
    return ContentResult(url=url, title=title, content=text, word_count=word_count)


def fetch_contents_parallel(
    urls: Sequence[str],
    timeout: float = 15.0,
    max_workers: int = CONTENT_FETCH_WORKERS,
) -> List[ContentResult]:
    """Fetch multiple URLs concurrently and return results in input order."""
    results: Dict[str, ContentResult] = {}

    def _fetch_one(target_url: str) -> ContentResult:
        return fetch_page_content(target_url, timeout=timeout)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(_fetch_one, u): u for u in urls}
        for future in concurrent.futures.as_completed(future_map):
            target_url = future_map[future]
            try:
                results[target_url] = future.result()
            except Exception as exc:
                results[target_url] = ContentResult(
                    url=target_url, title="", content="", word_count=0, error=str(exc),
                )

    return [results[u] for u in urls if u in results]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_url_format(url: str) -> Tuple[bool, str]:
    p = urllib.parse.urlparse(url)
    if p.scheme not in {"http", "https"}:
        return False, "scheme must be http/https"
    if not p.netloc:
        return False, "missing host"
    return True, ""


def check_reachability(url: str, timeout: float) -> Tuple[bool, int, str]:
    """HEAD request with automatic GET fallback on 405."""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "deep-research/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            return True, int(status), ""
    except urllib.error.HTTPError as exc:
        if exc.code == 405:
            return _check_reachability_get(url, timeout)
        return False, int(exc.code), str(exc)
    except Exception as exc:  # pragma: no cover - runtime/network dependent
        return False, 0, str(exc)


def _check_reachability_get(url: str, timeout: float) -> Tuple[bool, int, str]:
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "deep-research/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            return True, int(status), ""
    except urllib.error.HTTPError as exc:
        return False, int(exc.code), str(exc)
    except Exception as exc:  # pragma: no cover
        return False, 0, str(exc)


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------

def load_results(path: Path) -> List[SearchResult]:
    payload = json.loads(path.read_text())
    rows = payload.get("results", []) if isinstance(payload, dict) else payload
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized = normalize_url(str(row.get("normalized_url", ""))) or normalize_url(str(row.get("url", "")))
        domain = row.get("domain") or registrable_domain(urllib.parse.urlparse(normalized).hostname or "")
        out.append(
            SearchResult(
                query=str(row.get("query", "")),
                title=str(row.get("title", "")).strip() or normalized,
                url=str(row.get("url", "")),
                normalized_url=normalized,
                domain=domain,
                source_type=str(row.get("source_type", "")) or infer_source_type(domain),
                snippet=str(row.get("snippet", "")),
                date=str(row.get("date", "")),
            )
        )
    return out


def load_findings(path: Optional[Path]) -> Dict:
    if not path:
        return {}
    return json.loads(path.read_text())


def validate_findings(findings: Dict, by_url: Dict[str, SearchResult]) -> List[str]:
    issues: List[str] = []
    items = findings.get("findings", []) if isinstance(findings, dict) else []
    if not items:
        return issues

    for idx, finding in enumerate(items, start=1):
        if not isinstance(finding, dict):
            issues.append(f"finding #{idx}: must be an object")
            continue
        citations = [normalize_url(str(x)) for x in finding.get("citations", [])]
        citations = [x for x in citations if x]
        if not citations:
            issues.append(f"finding #{idx}: missing citations")
            continue

        missing = [c for c in citations if c not in by_url]
        if missing:
            issues.append(f"finding #{idx}: citation not found in retrieval set: {missing[0]}")

        conf = str(finding.get("confidence", "")).lower()
        domains = {by_url[c].domain for c in citations if c in by_url and by_url[c].domain}
        if conf == "high" and len(domains) < 2:
            issues.append(f"finding #{idx}: high confidence requires >=2 independent domains")
        if conf == "medium" and len(citations) < 1:
            issues.append(f"finding #{idx}: medium confidence requires >=1 citation")

    return issues


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def build_sources_index(results: Sequence[SearchResult]) -> str:
    lines = []
    for i, r in enumerate(results, start=1):
        date = r.date if r.date else "n/a"
        lines.append(f"[{i}] {r.title} — {r.normalized_url} — ({r.source_type}, {date})")
    return "\n".join(lines)


def map_url_to_index(results: Sequence[SearchResult]) -> Dict[str, int]:
    return {r.normalized_url: i + 1 for i, r in enumerate(results)}


def render_findings_md(findings: Dict, url_map: Dict[str, int]) -> str:
    rows = findings.get("findings", []) if isinstance(findings, dict) else []
    if not rows:
        return "- No structured findings provided."
    out: List[str] = []
    for f in rows:
        title = str(f.get("title", "Untitled finding"))
        conf = str(f.get("confidence", "low")).capitalize()
        text = str(f.get("analysis", ""))
        cites = []
        for c in f.get("citations", []):
            n = normalize_url(str(c))
            if n in url_map:
                cites.append(f"[{url_map[n]}]")
        cite_text = " ".join(cites)
        out.append(f"- **{title}** ({conf} confidence): {text} {cite_text}".rstrip())
    return "\n".join(out)


def render_analysis_md(findings: Dict, url_map: Dict[str, int]) -> str:
    sections = findings.get("analysis_sections", []) if isinstance(findings, dict) else []
    if not sections:
        return "### Main Analysis\nNo additional analysis sections were provided."
    out = []
    for sec in sections:
        title = str(sec.get("title", "Analysis"))
        content = str(sec.get("content", ""))
        citations = []
        for c in sec.get("citations", []):
            n = normalize_url(str(c))
            if n in url_map:
                citations.append(f"[{url_map[n]}]")
        suffix = " " + " ".join(citations) if citations else ""
        out.append(f"### {title}\n{content}{suffix}".rstrip())
    return "\n\n".join(out)


def generate_report(question: str, findings: Dict, results: Sequence[SearchResult], depth: str) -> str:
    url_map = map_url_to_index(results)
    executive = str(findings.get("executive_summary", "")).strip() or "Research summary not provided."
    consensus = str(findings.get("consensus", "")).strip() or "No explicit consensus captured."
    debate = str(findings.get("debate", "")).strip() or "No explicit debate captured."
    gaps = findings.get("gaps", []) if isinstance(findings, dict) else []
    gaps_md = "\n".join(f"- {g}" for g in gaps) if gaps else "- None documented."

    return f"""## Research Question
- Normalized question: {question}
- Scope assumptions: standard multi-source web research
- Depth mode: `{depth}`

## Method
- Retrieval plan (queries/subtopics): generated from provided queries
- Dedup strategy: normalized URL canonicalization + first-seen retention
- Validation checks performed: URL format, citation linkage, confidence/domain consistency

## Executive Summary
{executive}

## Key Findings
{render_findings_md(findings, url_map)}

## Detailed Analysis
{render_analysis_md(findings, url_map)}

## Areas of Consensus
{consensus}

## Areas of Debate
{debate}

## Sources
{build_sources_index(results)}

## Gaps & Limitations
{gaps_md}
"""


# ---------------------------------------------------------------------------
# Codebase search (ripgrep)
# ---------------------------------------------------------------------------

def search_codebase(
    root: Path,
    patterns: Sequence[str],
    globs: Sequence[str],
    context_lines: int = 2,
) -> List[Dict[str, Any]]:
    """Search a local codebase using ripgrep and return structured matches."""
    rg_path = shutil.which("rg")
    if not rg_path:
        raise RuntimeError("ripgrep (rg) is required for codebase search but not found in PATH")

    all_matches: List[Dict[str, Any]] = []
    for pat in patterns:
        cmd: List[str] = [rg_path, "--json", "-C", str(context_lines)]
        for g in globs:
            cmd.extend(["--glob", g])
        cmd.extend(["--", pat, str(root)])

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
        except subprocess.TimeoutExpired:
            all_matches.append({"pattern": pat, "error": "search timed out"})
            continue

        if proc.returncode not in (0, 1):
            all_matches.append({"pattern": pat, "error": proc.stderr.strip()[:300]})
            continue

        for line in proc.stdout.splitlines():
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") != "match":
                continue
            data = entry.get("data", {})
            path_data = data.get("path", {})
            file_path = path_data.get("text", "")
            line_number = data.get("line_number", 0)
            line_text = data.get("lines", {}).get("text", "").rstrip("\n")
            all_matches.append({
                "pattern": pat,
                "file": file_path,
                "line": line_number,
                "text": line_text,
            })

    return all_matches


# ---------------------------------------------------------------------------
# JSON helper
# ---------------------------------------------------------------------------

def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True))


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_retrieve(args: argparse.Namespace) -> int:
    all_results: List[SearchResult] = []
    retrieval_errors: List[str] = []

    for i, query in enumerate(args.query):
        if i > 0 and args.delay > 0:
            time.sleep(args.delay)
        try:
            batch = fetch_duckduckgo_lite(query, args.limit_per_query, args.timeout)
            all_results.extend(batch)
        except Exception as exc:  # pragma: no cover - runtime/network dependent
            retrieval_errors.append(f"{query}: {exc}")

    deduped = dedupe_results(all_results)
    payload = {
        "generated_at": utc_now_iso(),
        "queries": args.query,
        "count_before_dedupe": len(all_results),
        "count_after_dedupe": len(deduped),
        "retrieval_errors": retrieval_errors,
        "results": [asdict(x) for x in deduped],
    }
    write_json(Path(args.output), payload)

    print(f"retrieved={len(all_results)} deduped={len(deduped)} outputexample={args.output}")
    if retrieval_errors and not deduped:
        return 2
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    results = load_results(Path(args.results))
    issues: List[str] = []
    details = []

    by_url: Dict[str, SearchResult] = {}
    for row in results:
        ok, why = validate_url_format(row.normalized_url)
        if not ok:
            issues.append(f"invalid URL format: {row.url} ({why})")
            continue
        by_url[row.normalized_url] = row

        reachable = None
        status = None
        error = ""
        if args.check_live:
            reachable, status, error = check_reachability(row.normalized_url, timeout=args.timeout)
            if not reachable:
                issues.append(f"unreachable URL: {row.normalized_url} ({status} {error})")

        details.append(
            {
                "url": row.normalized_url,
                "domain": row.domain,
                "source_type": row.source_type,
                "reachable": reachable,
                "status": status,
                "error": error,
            }
        )

    findings = load_findings(Path(args.findings) if args.findings else None)
    issues.extend(validate_findings(findings, by_url))

    payload = {
        "generated_at": utc_now_iso(),
        "checked_count": len(results),
        "issues": issues,
        "details": details,
    }
    if args.output:
        write_json(Path(args.output), payload)

    print(f"validated={len(results)} issues={len(issues)}")
    return 2 if issues else 0


def cmd_report(args: argparse.Namespace) -> int:
    results = load_results(Path(args.results))
    results = dedupe_results(results)
    findings = load_findings(Path(args.findings) if args.findings else None)

    if not results:
        print("no retrieval results found; cannot build source-backed report", file=sys.stderr)
        return 2

    report = generate_report(args.question, findings, results, depth=args.depth)
    out_path = Path(args.output)
    out_path.write_text(report)
    print(f"report={out_path} sources={len(results)}")
    return 0


def cmd_fetch_content(args: argparse.Namespace) -> int:
    """Fetch and extract text content from URLs (parallel)."""
    if args.results:
        results = load_results(Path(args.results))
        urls = [r.normalized_url for r in results]
    elif args.url:
        urls = list(args.url)
    else:
        print("provide --results or --url", file=sys.stderr)
        return 2

    if args.limit and len(urls) > args.limit:
        urls = urls[: args.limit]

    contents = fetch_contents_parallel(
        urls,
        timeout=args.timeout,
        max_workers=args.workers,
    )

    payload = {
        "generated_at": utc_now_iso(),
        "count": len(contents),
        "items": [asdict(c) for c in contents],
    }
    write_json(Path(args.output), payload)

    ok = sum(1 for c in contents if not c.error)
    fail = sum(1 for c in contents if c.error)
    print(f"fetched={ok} errors={fail} outputexample={args.output}")
    return 2 if ok == 0 and urls else 0


def cmd_search_codebase(args: argparse.Namespace) -> int:
    """Search a local codebase using ripgrep."""
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"root path not found: {root}", file=sys.stderr)
        return 2

    try:
        matches = search_codebase(root, args.pattern, args.glob or [], context_lines=args.context)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    by_file: Dict[str, List[Dict]] = {}
    errors = []
    for m in matches:
        if "error" in m:
            errors.append(m)
            continue
        f = m.get("file", "unknown")
        by_file.setdefault(f, []).append(m)

    payload = {
        "generated_at": utc_now_iso(),
        "root": str(root),
        "patterns": list(args.pattern),
        "total_matches": sum(len(v) for v in by_file.values()),
        "files_matched": len(by_file),
        "errors": errors,
        "matches_by_file": {f: ms for f, ms in sorted(by_file.items())},
    }
    write_json(Path(args.output), payload)
    print(f"matches={payload['total_matches']} files={payload['files_matched']} outputexample={args.output}")
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deep research helper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_retrieve = sub.add_parser("retrieve", help="retrieve web results and dedupe")
    p_retrieve.add_argument("--query", action="append", required=True, help="search query (repeatable)")
    p_retrieve.add_argument("--limit-per-query", type=int, default=8)
    p_retrieve.add_argument("--timeout", type=float, default=12.0)
    p_retrieve.add_argument("--delay", type=float, default=DEFAULT_REQUEST_DELAY, help="seconds between queries")
    p_retrieve.add_argument("--outputexample", required=True, help="outputexample JSON path")
    p_retrieve.set_defaults(func=cmd_retrieve)

    p_validate = sub.add_parser("validate", help="validate URLs and citation quality")
    p_validate.add_argument("--results", required=True, help="retrieval JSON path")
    p_validate.add_argument("--findings", default="", help="optional findings JSON path")
    p_validate.add_argument("--check-live", action="store_true", help="perform runtime reachability checks")
    p_validate.add_argument("--timeout", type=float, default=8.0)
    p_validate.add_argument("--outputexample", default="", help="optional validation JSON path")
    p_validate.set_defaults(func=cmd_validate)

    p_report = sub.add_parser("report", help="generate markdown report")
    p_report.add_argument("--question", required=True)
    p_report.add_argument("--results", required=True, help="retrieval JSON path")
    p_report.add_argument("--findings", default="", help="optional findings JSON path")
    p_report.add_argument("--depth", choices=["quick", "standard", "deep"], default="standard")
    p_report.add_argument("--outputexample", required=True, help="outputexample markdown path")
    p_report.set_defaults(func=cmd_report)

    p_content = sub.add_parser("fetch-content", help="fetch and extract text from URLs")
    p_content.add_argument("--results", default="", help="retrieval JSON path (use URLs from here)")
    p_content.add_argument("--url", action="append", help="explicit URL to fetch (repeatable)")
    p_content.add_argument("--limit", type=int, default=0, help="max URLs to fetch (0=all)")
    p_content.add_argument("--timeout", type=float, default=15.0)
    p_content.add_argument("--workers", type=int, default=CONTENT_FETCH_WORKERS, help="parallel fetch workers")
    p_content.add_argument("--outputexample", required=True, help="outputexample JSON path")
    p_content.set_defaults(func=cmd_fetch_content)

    p_codebase = sub.add_parser("search-codebase", help="search local codebase with ripgrep")
    p_codebase.add_argument("--pattern", action="append", required=True, help="search pattern (repeatable)")
    p_codebase.add_argument("--root", default=".", help="codebase root directory")
    p_codebase.add_argument("--glob", action="append", help="file glob filter (repeatable)")
    p_codebase.add_argument("--context", type=int, default=2, help="context lines around matches")
    p_codebase.add_argument("--outputexample", required=True, help="outputexample JSON path")
    p_codebase.set_defaults(func=cmd_search_codebase)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

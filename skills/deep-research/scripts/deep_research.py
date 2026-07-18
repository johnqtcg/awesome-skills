#!/usr/bin/env python3
"""Deep research helper: retrieval, dedup, validation, content extraction, codebase search, and report generation."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import html
import json
import random
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

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from deep_research_lib.repository import (  # noqa: E402
    RepositoryEvidenceVerifier,
    code_record_provenance,
    git_repository_context,
    is_pinned_commit,
    repository_snapshot,
)
from deep_research_lib.reporting import (  # noqa: E402
    ReportSourceBudgetError,
    enforce_report_source_limit,
    select_cited_artifacts,
)
from deep_research_lib.planning import (  # noqa: E402
    MODE_BUDGETS,
    VALID_MODES,
    VALID_RESEARCH_KINDS,
    classify_research_kind,
    normalize_mode as _normalize_mode,
    plan_research,
    select_research_mode,
)
from deep_research_lib.session import (  # noqa: E402
    BudgetExceededError,
    initialize_session,
    load_session,
    record_report_sources,
    reserve_session_budget,
)

TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "spm",
}

GOVERNMENT_SUFFIXES = (".gov", ".gov.uk", ".go.jp", ".gov.au", ".gov.cn")
EDUCATION_SUFFIXES = (".edu", ".ac.uk", ".ac.jp", ".edu.au")
NEWS_HINTS = ("news", "reuters", "bloomberg", "bbc", "apnews", "ft.com", "wsj.com")
ACADEMIC_HINTS = ("arxiv.org", "acm.org", "ieee.org", "springer", "nature.com", "sciencedirect")
FORUM_HINTS = ("reddit.com", "ycombinator.com", "stackoverflow.com")
BLOG_HINTS = ("medium.com", "dev.to", "substack.com", "hashnode")

VALID_TIERS = ("T1", "T2", "T3", "T4", "T5")

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

# ---------------------------------------------------------------------------
# Anti-bot resilience
# ---------------------------------------------------------------------------

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.5
RETRY_STATUS_CODES = {429, 502, 503, 504}

CLOUDFLARE_MARKERS = [
    "Checking if the site connection is secure",
    "cf-browser-verification",
    "Enable JavaScript and cookies to continue",
    "Just a moment...",
    "Attention Required! | Cloudflare",
    "cf-challenge-running",
    "ray ID",
]

# ---------------------------------------------------------------------------
# Content extraction (enhanced)
# ---------------------------------------------------------------------------

NOISE_TAGS_RE = re.compile(
    r"<(nav|footer|aside|header|menu)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
MAIN_TAG_RE = re.compile(r"<main\b[^>]*>(.*?)</main>", re.IGNORECASE | re.DOTALL)
ARTICLE_TAG_RE = re.compile(r"<article\b[^>]*>(.*?)</article>", re.IGNORECASE | re.DOTALL)
MIN_CONTENT_WORDS = 30


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
    source_tier: str = "T4"
    classification_basis: str = "heuristic"
    sponsorship: str = "unknown"
    methodology: str = "unknown"


@dataclass
class ContentResult:
    url: str
    title: str
    content: str
    word_count: int
    error: str = ""


# ---------------------------------------------------------------------------
# Executable degradation state
# ---------------------------------------------------------------------------

def assess_degradation(
    *,
    required_inputs_present: bool,
    usable_findings: int,
    total_findings: int,
    extraction_failures: int = 0,
    downgraded_findings: int = 0,
    validation_errors: int = 0,
    budget_exhausted: bool = False,
) -> str:
    """Compute Full/Partial/Blocked from observed execution state."""
    if not required_inputs_present:
        return "Blocked"
    if total_findings == 0:
        return "Blocked"
    if total_findings > 0 and usable_findings == 0:
        return "Blocked"
    if budget_exhausted and usable_findings == 0:
        return "Blocked"
    if (
        usable_findings < total_findings
        or extraction_failures > 0
        or downgraded_findings > 0
        or validation_errors > 0
        or budget_exhausted
    ):
        return "Partial"
    return "Full"


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


def infer_source_quality(hostname: str) -> Tuple[str, str, str]:
    """Return conservative (source_type, tier, basis) heuristic metadata.

    Heuristics are only preclassification. They never establish that a docs.*
    host belongs to a product owner, that .edu content is official product
    documentation, or that a paper was peer reviewed.
    """
    host = (hostname or "").lower()
    if any(host.endswith(s) for s in GOVERNMENT_SUFFIXES):
        return "government", "T1", "heuristic:government-domain"
    if any(h in host for h in ACADEMIC_HINTS):
        return "academic", "T2", "heuristic:academic-publisher-or-repository"
    if any(host.endswith(s) for s in EDUCATION_SUFFIXES):
        return "institutional", "T2", "heuristic:education-domain"
    if any(h in host for h in NEWS_HINTS):
        return "news", "T3", "heuristic:news-domain"
    if any(h in host for h in FORUM_HINTS):
        return "forum", "T4", "heuristic:community-domain"
    if any(h in host for h in BLOG_HINTS):
        return "blog", "T5", "heuristic:publishing-platform"
    return "website", "T4", "heuristic:unverified-domain"


def infer_source_type(hostname: str) -> str:
    """Compatibility wrapper around conservative source-quality inference."""
    source_type, _, _ = infer_source_quality(hostname)
    return source_type


# ---------------------------------------------------------------------------
# Anti-bot helpers
# ---------------------------------------------------------------------------

def _random_ua() -> str:
    """Pick a random realistic User-Agent string."""
    return random.choice(USER_AGENTS)


def _browser_headers(referer: str = "") -> Dict[str, str]:
    """Build browser-like HTTP headers to reduce anti-bot blocking."""
    headers: Dict[str, str] = {
        "User-Agent": _random_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    if referer:
        headers["Referer"] = referer
    return headers


def _is_blocked_response(body: str) -> bool:
    """Detect common WAF/anti-bot block pages (Cloudflare, etc.)."""
    lower = body.lower()
    return any(marker.lower() in lower for marker in CLOUDFLARE_MARKERS)


def _fetch_with_retry(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 15.0,
    max_retries: int = MAX_RETRIES,
    max_bytes: int = 0,
) -> bytes:
    """Fetch URL with retry, exponential backoff, and block detection."""
    if headers is None:
        headers = _browser_headers()

    last_error: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        if attempt > 1:
            backoff = RETRY_BACKOFF_BASE ** (attempt - 1) + random.uniform(0, 0.5)
            time.sleep(backoff)

        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read(max_bytes) if max_bytes > 0 else resp.read()
                text = body.decode("utf-8", errors="ignore")
                if _is_blocked_response(text) and attempt < max_retries:
                    last_error = Exception(
                        f"blocked by WAF/anti-bot (attempt {attempt}/{max_retries})"
                    )
                    continue
                return body
        except urllib.error.HTTPError as exc:
            if int(exc.code) in RETRY_STATUS_CODES and attempt < max_retries:
                last_error = exc
                continue
            raise
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            if attempt < max_retries:
                last_error = exc
                continue
            raise

    raise last_error or Exception("max retries exceeded")


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
        source_type, source_tier, basis = infer_source_quality(domain)

        results.append(
            SearchResult(
                query=query,
                title=title,
                url=decoded,
                normalized_url=normalized,
                domain=domain,
                source_type=source_type,
                snippet=snippet,
                source_tier=source_tier,
                classification_basis=basis,
            )
        )
        if len(results) >= limit:
            break

    return results


def fetch_duckduckgo_lite(query: str, limit: int, timeout: float) -> List[SearchResult]:
    encoded = urllib.parse.urlencode({"q": query})
    url = f"https://lite.duckduckgo.com/lite/?{encoded}"
    headers = _browser_headers(referer="https://lite.duckduckgo.com/")
    body = _fetch_with_retry(url, headers=headers, timeout=timeout)
    html_text = body.decode("utf-8", errors="ignore")
    return parse_duckduckgo_lite(html_text, query, limit)


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
    """Extract readable text with content-area detection and noise removal."""
    # Step 1: Try to isolate main content area (<main> preferred, then <article>)
    working_html = raw_html
    for pattern in (MAIN_TAG_RE, ARTICLE_TAG_RE):
        match = pattern.search(raw_html)
        if match:
            candidate = match.group(1)
            plain = TAG_RE.sub(" ", candidate)
            if len(plain.split()) >= MIN_CONTENT_WORDS:
                working_html = candidate
                break

    # Step 2: Remove noise elements (nav, footer, aside, header, menu)
    working_html = NOISE_TAGS_RE.sub(" ", working_html)

    # Step 3: Remove script/style/noscript/head and strip tags
    text = STRIP_TAGS_RE.sub(" ", working_html)
    text = TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = WHITESPACE_COLLAPSE_RE.sub(" ", text)
    text = BLANK_LINES_RE.sub("\n\n", text)
    text = text.strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "..."
    return text


def fetch_page_content(url: str, timeout: float = 15.0, max_bytes: int = CONTENT_MAX_BYTES) -> ContentResult:
    """Fetch a URL and return extracted text content with anti-bot resilience."""
    try:
        raw_bytes = _fetch_with_retry(
            url, headers=_browser_headers(), timeout=timeout, max_bytes=max_bytes,
        )
        raw = raw_bytes.decode("utf-8", errors="ignore")
    except Exception as exc:
        return ContentResult(url=url, title="", content="", word_count=0, error=str(exc))

    title = ""
    title_match = re.search(r"<title[^>]*>(.*?)</title>", raw, re.IGNORECASE | re.DOTALL)
    if title_match:
        title = html.unescape(re.sub(r"<[^>]+>", "", title_match.group(1))).strip()

    text = extract_text_from_html(raw)
    word_count = len(text.split())

    # Quality check: detect likely blocked or JS-only pages
    error = ""
    if _is_blocked_response(raw):
        error = "likely blocked by WAF/anti-bot (Cloudflare or similar)"
    elif word_count < MIN_CONTENT_WORDS and len(raw) > 1000:
        error = "low content yield (page may require JavaScript rendering)"

    return ContentResult(url=url, title=title, content=text, word_count=word_count, error=error)


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
    req = urllib.request.Request(url, method="HEAD", headers=_browser_headers())
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
    req = urllib.request.Request(url, method="GET", headers=_browser_headers())
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
        inferred_type, inferred_tier, inferred_basis = infer_source_quality(domain)
        tier = str(row.get("source_tier", "")).upper() or inferred_tier
        if tier not in VALID_TIERS:
            tier = inferred_tier
        out.append(
            SearchResult(
                query=str(row.get("query", "")),
                title=str(row.get("title", "")).strip() or normalized,
                url=str(row.get("url", "")),
                normalized_url=normalized,
                domain=domain,
                source_type=str(row.get("source_type", "")) or inferred_type,
                snippet=str(row.get("snippet", "")),
                date=str(row.get("date", "")),
                source_tier=tier,
                classification_basis=str(row.get("classification_basis", "")) or inferred_basis,
                sponsorship=str(row.get("sponsorship", "")) or "unknown",
                methodology=str(row.get("methodology", "")) or "unknown",
            )
        )
    return out


def load_findings(path: Optional[Path]) -> Dict:
    if not path:
        return {}
    return json.loads(path.read_text())


def load_content_artifact(
    path: Optional[Path],
) -> Tuple[List[ContentResult], Dict[str, Any]]:
    if not path:
        return [], {}
    payload = json.loads(path.read_text())
    rows = payload.get("items", []) if isinstance(payload, dict) else payload
    out: List[ContentResult] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        content = str(row.get("content", ""))
        out.append(
            ContentResult(
                url=normalize_url(str(row.get("url", ""))) or str(row.get("url", "")),
                title=str(row.get("title", "")),
                content=content,
                word_count=int(row.get("word_count", len(content.split())) or 0),
                error=str(row.get("error", "")),
            )
        )
    metadata = (
        {key: value for key, value in payload.items() if key != "items"}
        if isinstance(payload, dict)
        else {}
    )
    return out, metadata


def load_contents(path: Optional[Path]) -> List[ContentResult]:
    """Compatibility loader for callers that only need extracted items."""
    contents, _ = load_content_artifact(path)
    return contents


def load_code_evidence(path: Optional[Path]) -> Dict[str, Any]:
    if not path:
        return {}
    payload = json.loads(path.read_text())
    return payload if isinstance(payload, dict) else {}


def _normalized_excerpt(text: str) -> str:
    return " ".join(str(text or "").split()).casefold()


def _is_pinned_commit(value: Any) -> bool:
    """Accept an abbreviated or full hexadecimal Git object ID, not labels."""
    return is_pinned_commit(value)


def _issue(
    code: str,
    message: str,
    *,
    severity: str = "error",
    finding: int = 0,
) -> Dict[str, Any]:
    item: Dict[str, Any] = {
        "severity": severity,
        "code": code,
        "message": message,
    }
    if finding:
        item["finding"] = finding
    return item


def _repository_evidence_index(code_evidence: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    rows = code_evidence.get("evidence", []) if isinstance(code_evidence, dict) else []
    index: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        evidence_id = str(row.get("id", "")).strip()
        kind = str(row.get("kind", "")).strip().lower()
        if evidence_id and kind in {"code", "commit", "test"}:
            index[evidence_id] = row
    return index


def _validate_evidence_refs(
    refs: Any,
    *,
    by_url: Dict[str, SearchResult],
    by_content: Dict[str, ContentResult],
    repository_verifier: RepositoryEvidenceVerifier,
    finding_index: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    verified: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []
    independence: List[str] = []
    if not isinstance(refs, list) or not refs:
        issues.append(
            _issue(
                "missing_evidence",
                "typed evidence is required; bare citations do not prove source support",
                finding=finding_index,
            )
        )
        return verified, issues, independence

    for ref in refs:
        if not isinstance(ref, dict):
            issues.append(
                _issue(
                    "invalid_evidence",
                    "evidence entries must be objects",
                    finding=finding_index,
                )
            )
            continue
        kind = str(ref.get("kind", "")).strip().lower()
        if kind == "web":
            url = normalize_url(str(ref.get("url", "")))
            excerpt = str(ref.get("excerpt", "")).strip()
            if not url or url not in by_url:
                issues.append(
                    _issue(
                        "web_source_not_retrieved",
                        f"web evidence URL is not in retrieval results: {url or '<missing>'}",
                        finding=finding_index,
                    )
                )
                continue
            content = by_content.get(url)
            if not content or content.error or not content.content.strip():
                issues.append(
                    _issue(
                        "web_content_not_extracted",
                        f"web evidence has no successful content extraction: {url}",
                        finding=finding_index,
                    )
                )
                continue
            if not excerpt:
                issues.append(
                    _issue(
                        "supporting_excerpt_missing",
                        f"web evidence requires an exact supporting excerpt: {url}",
                        finding=finding_index,
                    )
                )
                continue
            if _normalized_excerpt(excerpt) not in _normalized_excerpt(content.content):
                issues.append(
                    _issue(
                        "excerpt_not_in_content",
                        f"supporting excerpt was not found in extracted content: {url}",
                        finding=finding_index,
                    )
                )
                continue
            source = by_url[url]
            verified.append(
                {
                    "kind": "web",
                    "url": url,
                    "excerpt": excerpt,
                    "domain": source.domain,
                    "source_tier": source.source_tier,
                    "primary": source.source_tier == "T1",
                }
            )
            independence.append(f"web:{source.domain}")
            continue

        if kind in {"code", "commit", "test"}:
            evidence_id = str(ref.get("id", "")).strip()
            verified_record, verification_issue = repository_verifier.verify(
                evidence_id,
                kind,
            )
            if verification_issue:
                issue = dict(verification_issue)
                if finding_index:
                    issue["finding"] = finding_index
                issues.append(issue)
                continue
            if not verified_record:
                continue
            verified.append(verified_record)
            independence.append(f"{kind}:{evidence_id}")
            continue

        issues.append(
            _issue(
                "unsupported_evidence_kind",
                f"unsupported evidence kind: {kind or '<missing>'}",
                finding=finding_index,
            )
        )

    return verified, issues, list(dict.fromkeys(independence))


def _effective_confidence(
    finding: Dict[str, Any],
    verified: Sequence[Dict[str, Any]],
    independence: Sequence[str],
) -> Tuple[str, List[str]]:
    requested = str(finding.get("confidence", "low")).strip().lower()
    if requested not in {"high", "medium", "low"}:
        requested = "low"
    if not verified:
        return "low", ["no verified evidence"]

    claim_type = str(finding.get("claim_type", "analysis")).strip().lower()
    kinds = {str(item.get("kind", "")) for item in verified}
    has_primary = any(bool(item.get("primary")) for item in verified)
    has_t1_web = any(
        item.get("kind") == "web"
        and item.get("source_tier") == "T1"
        and bool(item.get("primary"))
        for item in verified
    )
    has_pinned_code = any(
        item.get("kind") == "code" and bool(item.get("pinned"))
        for item in verified
    )
    reasons: List[str] = []

    qualifies_high = False
    if claim_type == "single_fact":
        qualifies_high = has_t1_web
    elif claim_type == "code_fact":
        qualifies_high = has_pinned_code
    elif claim_type == "runtime_behavior":
        runtime_supported, runtime_reasons = _runtime_test_support(
            finding,
            verified,
        )
        qualifies_high = has_pinned_code and runtime_supported
        reasons.extend(runtime_reasons)
    else:
        qualifies_high = has_primary and len(set(independence)) >= 2

    if requested == "high":
        if qualifies_high:
            return "high", reasons
        reasons.append(
            "High requires one verified T1 primary source for a narrow single fact, "
            "direct code evidence for a code fact, code plus a passing test for runtime "
            "behavior, or two independent verified units including a primary source"
        )
        return "medium", reasons
    if requested == "medium":
        return "medium", reasons
    return "low", reasons


def _runtime_test_support(
    finding: Dict[str, Any],
    verified: Sequence[Dict[str, Any]],
) -> Tuple[bool, List[str]]:
    """Bind one reviewed host receipt to the complete cited-code set."""
    finding_id = str(finding.get("id", "")).strip()
    codes = [item for item in verified if item.get("kind") == "code"]
    tests = [item for item in verified if item.get("kind") == "test"]
    if not finding_id:
        return False, ["runtime High requires a stable finding id"]
    cited_code_ids = [
        str(item.get("id", "")).strip()
        for item in finding.get("evidence", [])
        if isinstance(item, dict)
        and str(item.get("kind", "")).strip().lower() == "code"
    ]
    verified_code_ids = {
        str(item.get("id", "")).strip()
        for item in codes
    }
    unresolved_code_ids = [
        code_id or "<missing>"
        for code_id in cited_code_ids
        if not code_id or code_id not in verified_code_ids
    ]
    if unresolved_code_ids:
        return False, [
            "runtime High requires every cited code evidence item to verify; "
            "unresolved: "
            + ", ".join(dict.fromkeys(unresolved_code_ids))
        ]
    if not codes:
        return False, ["runtime High requires pinned code evidence"]
    unpinned_ids = [
        str(item.get("id", "")).strip() or "<missing>"
        for item in codes
        if not bool(item.get("pinned"))
    ]
    if unpinned_ids:
        return False, [
            "runtime High cannot cite unpinned code evidence: "
            + ", ".join(unpinned_ids)
        ]
    code_ids = [str(item.get("id", "")).strip() for item in codes]
    if any(not code_id for code_id in code_ids):
        return False, ["runtime High requires stable IDs for every cited code item"]
    code_commits = {
        str(item.get("commit", "")).strip()
        for item in codes
    }
    if len(code_commits) != 1:
        return False, [
            "all cited code evidence must use one pinned commit/tree"
        ]
    if not tests:
        return False, ["runtime High requires a verified host test receipt"]

    shared_commit = next(iter(code_commits))
    required_covers = {finding_id, *code_ids}
    code_paths = {
        str(item.get("path", "")).strip()
        for item in codes
        if str(item.get("path", "")).strip()
    }
    candidate_reasons: List[str] = []
    for test in tests:
        test_id = str(test.get("id", "")).strip() or "<missing>"
        covers = set(test.get("covers", []))
        tested_paths = set(test.get("tested_paths", []))
        failures: List[str] = []
        if not bool(test.get("passed")):
            failures.append(f"test receipt {test_id} did not pass")
        missing_covers = sorted(required_covers - covers)
        if missing_covers:
            failures.append(
                f"single test receipt must cover finding {finding_id} "
                "and every code evidence ID; "
                f"receipt {test_id} is missing: {', '.join(missing_covers)}"
            )
            for code_id in code_ids:
                if code_id not in covers:
                    failures.append(
                        f"test receipt does not cover code evidence {code_id}"
                    )
        if not bool(test.get("snapshot_clean")):
            failures.append(f"test receipt {test_id} uses a dirty test snapshot")
        if not bool(test.get("relevance_approved")):
            failures.append(
                f"test receipt {test_id} relevance review is not approved"
            )
        if str(test.get("head_commit", "")) != shared_commit:
            failures.append(
                "test receipt snapshot does not match code evidence "
                + ", ".join(code_ids)
            )
        for code_path in sorted(code_paths - tested_paths):
            failures.append(
                f"test receipt does not name tested code path {code_path}"
            )
        if not failures:
            return True, []
        candidate_reasons.extend(failures)

    return False, list(dict.fromkeys(candidate_reasons))


def assess_finding(
    finding: Any,
    *,
    by_url: Dict[str, SearchResult],
    by_content: Dict[str, ContentResult],
    repository_verifier: RepositoryEvidenceVerifier,
    finding_index: int,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    if not isinstance(finding, dict):
        assessed = {
            "title": f"Finding {finding_index}",
            "analysis": "",
            "requested_confidence": "low",
            "effective_confidence": "low",
            "usable": False,
            "verified_evidence": [],
            "downgrade_reasons": ["finding must be an object"],
        }
        return assessed, [
            _issue(
                "invalid_finding",
                f"finding #{finding_index} must be an object",
                finding=finding_index,
            )
        ]

    issues: List[Dict[str, Any]] = []
    refs = finding.get("evidence", [])
    if not refs and finding.get("citations"):
        issues.append(
            _issue(
                "legacy_citations_unverified",
                "legacy citations list URLs but does not prove extraction or claim support; "
                "migrate to typed evidence with supporting excerpts",
                finding=finding_index,
            )
        )
    verified, evidence_issues, independence = _validate_evidence_refs(
        refs,
        by_url=by_url,
        by_content=by_content,
        repository_verifier=repository_verifier,
        finding_index=finding_index,
    )
    issues.extend(evidence_issues)
    finding_id = str(finding.get("id", "")).strip()
    semantically_bound: List[Dict[str, Any]] = []
    for item in verified:
        if item.get("kind") != "test":
            semantically_bound.append(item)
            continue
        if finding_id and finding_id in set(item.get("covers", [])):
            semantically_bound.append(item)
            continue
        issues.append(
            _issue(
                "test_does_not_cover_finding",
                f"test evidence {item.get('id')} does not cover finding "
                f"{finding_id or '<missing stable id>'}",
                finding=finding_index,
            )
        )
    verified = semantically_bound
    independence = [
        (
            f"web:{item.get('domain')}"
            if item.get("kind") == "web"
            else f"{item.get('kind')}:{item.get('id')}"
        )
        for item in verified
    ]
    effective, downgrade_reasons = _effective_confidence(finding, verified, independence)
    requested = str(finding.get("confidence", "low")).strip().lower()
    if requested not in {"high", "medium", "low"}:
        requested = "low"
    if effective != requested and verified:
        issues.append(
            _issue(
                "confidence_downgraded",
                f"finding #{finding_index} confidence downgraded from {requested} to {effective}",
                severity="warning",
                finding=finding_index,
            )
        )
    assessed = dict(finding)
    assessed.update(
        {
            "requested_confidence": requested,
            "effective_confidence": effective,
            "usable": bool(verified),
            "verified_evidence": verified,
            "downgrade_reasons": downgrade_reasons,
        }
    )
    return assessed, issues


def validate_research_bundle(
    *,
    research_kind: str,
    results: Sequence[SearchResult],
    contents: Sequence[ContentResult],
    code_evidence: Dict[str, Any],
    findings: Dict[str, Any],
    budget_exhausted: bool = False,
) -> Dict[str, Any]:
    """Validate every finding against extracted web or repository evidence."""
    kind = str(research_kind or "").lower()
    if kind not in VALID_RESEARCH_KINDS:
        raise ValueError(f"unsupported research kind: {research_kind}")

    by_url = {
        normalize_url(row.normalized_url): row
        for row in results
        if normalize_url(row.normalized_url)
    }
    by_content = {
        normalize_url(row.url): row
        for row in contents
        if normalize_url(row.url)
    }
    repository_verifier = RepositoryEvidenceVerifier(code_evidence)
    issues: List[Dict[str, Any]] = []

    requires_web = kind in {"web", "hybrid"}
    requires_code = kind in {"codebase", "hybrid"}
    web_input_present = bool(results) and bool(contents)
    code_input_present = bool(repository_verifier.records)
    if requires_web and not contents:
        issues.append(
            _issue(
                "required_content_missing",
                "web and hybrid research require a content extraction artifact",
            )
        )
    if requires_web and not results:
        issues.append(
            _issue(
                "required_results_missing",
                "web and hybrid research require retrieval results",
            )
        )
    if requires_code and not repository_verifier.records:
        issues.append(
            _issue(
                "required_code_evidence_missing",
                "codebase and hybrid research require repository evidence",
            )
        )

    raw_findings = findings.get("findings", []) if isinstance(findings, dict) else []
    assessed_findings: List[Dict[str, Any]] = []
    for idx, finding in enumerate(raw_findings, start=1):
        assessed, finding_issues = assess_finding(
            finding,
            by_url=by_url,
            by_content=by_content,
            repository_verifier=repository_verifier,
            finding_index=idx,
        )
        assessed_findings.append(assessed)
        issues.extend(finding_issues)

    assessed_sections: List[Dict[str, Any]] = []
    raw_sections = findings.get("analysis_sections", []) if isinstance(findings, dict) else []
    for idx, section in enumerate(raw_sections, start=1):
        if not isinstance(section, dict):
            issues.append(
                _issue(
                    "invalid_analysis_section",
                    f"analysis section #{idx} must be an object",
                )
            )
            continue
        verified, section_issues, _ = _validate_evidence_refs(
            section.get("evidence", []),
            by_url=by_url,
            by_content=by_content,
            repository_verifier=repository_verifier,
            finding_index=0,
        )
        issues.extend(section_issues)
        assessed_section = dict(section)
        assessed_section["verified_evidence"] = verified
        assessed_section["usable"] = bool(verified)
        assessed_sections.append(assessed_section)

    assessed_consensus_debate: Dict[str, List[Dict[str, Any]]] = {
        "consensus": [],
        "debate": [],
    }
    for field in ("consensus", "debate"):
        raw_rows = findings.get(field, []) if isinstance(findings, dict) else []
        if isinstance(raw_rows, str) and raw_rows.strip():
            issues.append(
                _issue(
                    f"legacy_{field}_unverified",
                    f"{field} must be a list of statements with typed evidence",
                    severity="warning",
                )
            )
            continue
        if not isinstance(raw_rows, list):
            continue
        for row in raw_rows:
            if not isinstance(row, dict):
                issues.append(
                    _issue(
                        f"invalid_{field}_statement",
                        f"{field} statements must be objects",
                    )
                )
                continue
            verified, row_issues, _ = _validate_evidence_refs(
                row.get("evidence", []),
                by_url=by_url,
                by_content=by_content,
                repository_verifier=repository_verifier,
                finding_index=0,
            )
            issues.extend(row_issues)
            assessed_row = dict(row)
            assessed_row["verified_evidence"] = verified
            assessed_row["usable"] = bool(verified)
            assessed_consensus_debate[field].append(assessed_row)

    successful_contents = sum(
        1
        for row in contents
        if row.content.strip() and not row.error
    )
    extraction_failures = sum(
        1
        for row in contents
        if row.error or not row.content.strip()
    )
    usable_findings = sum(1 for row in assessed_findings if row["usable"])
    downgraded = sum(
        1
        for row in assessed_findings
        if row["usable"] and row["effective_confidence"] != row["requested_confidence"]
    )
    supplemental_rows = (
        assessed_sections
        + assessed_consensus_debate["consensus"]
        + assessed_consensus_debate["debate"]
    )
    supplemental_unusable = sum(
        1 for row in supplemental_rows if not row.get("usable")
    )
    required_inputs_present = (
        (not requires_web or web_input_present)
        and (not requires_code or code_input_present)
    )
    verified_kinds = {
        evidence.get("kind")
        for row in assessed_findings
        for evidence in row.get("verified_evidence", [])
    }
    hybrid_incomplete = kind == "hybrid" and (
        "web" not in verified_kinds
        or not ({"code", "commit", "test"} & verified_kinds)
    )
    if hybrid_incomplete:
        issues.append(
            _issue(
                "hybrid_evidence_incomplete",
                "hybrid research must use both verified web and repository evidence",
                severity="warning",
            )
        )
    if budget_exhausted:
        issues.append(
            _issue(
                "budget_exhausted",
                "research budget was exhausted before every planned evidence path completed",
                severity="warning",
            )
        )
    degradation = assess_degradation(
        required_inputs_present=required_inputs_present,
        usable_findings=usable_findings,
        total_findings=len(assessed_findings),
        extraction_failures=extraction_failures,
        downgraded_findings=downgraded + supplemental_unusable,
        validation_errors=sum(
            1 for issue in issues if issue.get("severity") == "error"
        ),
        budget_exhausted=budget_exhausted,
    )
    if hybrid_incomplete and degradation == "Full":
        degradation = "Partial"

    cited_keys = set()
    for row in assessed_findings + supplemental_rows:
        for evidence in row.get("verified_evidence", []):
            cited_keys.add(
                evidence.get("url")
                or evidence.get("id")
                or repr(evidence)
            )

    return {
        "generated_at": utc_now_iso(),
        "research_kind": kind,
        "degradation": degradation,
        "evidence_chain_status": (
            "satisfied"
            if degradation == "Full"
            else "partially satisfied"
            if degradation == "Partial"
            else "insufficient"
        ),
        "issues": issues,
        "findings": assessed_findings,
        "analysis_sections": assessed_sections,
        "consensus": assessed_consensus_debate["consensus"],
        "debate": assessed_consensus_debate["debate"],
        "counts": {
            "retrieved": len(results),
            "content_items": len(contents),
            "successfully_extracted": successful_contents,
            "extraction_failures": extraction_failures,
            "repository_evidence": len(repository_verifier.records),
            "findings": len(assessed_findings),
            "usable_findings": usable_findings,
            "cited_evidence": len(cited_keys),
        },
    }


def validate_findings(findings: Dict, by_url: Dict[str, SearchResult]) -> List[str]:
    """Legacy validator retained for callers; URL-only citations are unverified."""
    del by_url
    issues: List[str] = []
    for idx, finding in enumerate(findings.get("findings", []), start=1):
        if not isinstance(finding, dict):
            issues.append(f"finding #{idx}: must be an object")
        elif finding.get("citations") and not finding.get("evidence"):
            issues.append(
                f"finding #{idx}: legacy citations are unverified; typed evidence is required"
            )
        elif not finding.get("evidence"):
            issues.append(f"finding #{idx}: missing evidence")
    return issues


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _source_maps(
    results: Sequence[SearchResult],
    code_evidence: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, int], Dict[str, int]]:
    url_map = {
        normalize_url(r.normalized_url): i + 1
        for i, r in enumerate(results)
        if normalize_url(r.normalized_url)
    }
    repository_map: Dict[str, int] = {}
    offset = len(results)
    rows = (
        code_evidence.get("evidence", [])
        if isinstance(code_evidence, dict)
        else []
    )
    for row in rows:
        if not isinstance(row, dict):
            continue
        evidence_id = str(row.get("id", "")).strip()
        if evidence_id:
            repository_map[evidence_id] = offset + len(repository_map) + 1
    return url_map, repository_map


def build_sources_index(
    results: Sequence[SearchResult],
    code_evidence: Optional[Dict[str, Any]] = None,
) -> str:
    lines = []
    for i, r in enumerate(results, start=1):
        date = r.date if r.date else "unknown"
        lines.append(
            f"[{i}] {r.title} — {r.normalized_url} — "
            f"{r.source_type} ({r.source_tier}) — date: {date}; "
            f"basis: {r.classification_basis}; sponsorship: {r.sponsorship}; "
            f"methodology: {r.methodology}"
        )

    rows = (
        code_evidence.get("evidence", [])
        if isinstance(code_evidence, dict)
        else []
    )
    next_index = len(lines) + 1
    for row in rows:
        if not isinstance(row, dict) or not str(row.get("id", "")).strip():
            continue
        kind = str(row.get("kind", "")).lower()
        if kind == "code":
            detail = (
                f"{row.get('path', '<unknown>')}:{row.get('line', '?')} — "
                f"{row.get('excerpt', '')} — commit: {row.get('commit', 'unknown')}"
            )
        elif kind == "commit":
            detail = f"{row.get('commit', '<unknown>')} — {row.get('subject', '')}"
        elif kind == "test":
            covers = ", ".join(str(value) for value in row.get("covers", []))
            detail = (
                f"{row.get('framework', 'unknown')} / "
                f"{row.get('test_target', '<unknown>')} — "
                f"{row.get('status', 'unknown')} (exit {row.get('exit_code', '?')}) — "
                f"commit: {row.get('head_commit', 'unknown')}; "
                f"tree: {row.get('tree_hash', 'unknown')}; "
                f"dirty: {row.get('dirty', 'unknown')}; "
                f"covers: {covers or 'none'}; "
                f"relevance: {row.get('relevance_status', 'unknown')} — "
                f"{row.get('summary', '')}"
            )
        else:
            continue
        lines.append(f"[{next_index}] {kind} evidence `{row.get('id')}` — {detail}")
        next_index += 1
    return "\n".join(lines) if lines else "- No verified sources."


def map_url_to_index(results: Sequence[SearchResult]) -> Dict[str, int]:
    return {r.normalized_url: i + 1 for i, r in enumerate(results)}


def _render_evidence_citations(
    evidence: Sequence[Dict[str, Any]],
    url_map: Dict[str, int],
    repository_map: Dict[str, int],
) -> str:
    cites: List[str] = []
    for item in evidence:
        url = str(item.get("url", ""))
        evidence_id = str(item.get("id", ""))
        if url in url_map:
            cites.append(f"[{url_map[url]}]")
        elif evidence_id in repository_map:
            cites.append(f"[{repository_map[evidence_id]}]")
    return " ".join(dict.fromkeys(cites))


def render_findings_md(
    findings: Dict,
    url_map: Dict[str, int],
    repository_map: Optional[Dict[str, int]] = None,
) -> str:
    rows = findings.get("findings", []) if isinstance(findings, dict) else []
    usable_rows = [row for row in rows if isinstance(row, dict) and row.get("usable", True)]
    if not usable_rows:
        return "- No finding had verified supporting evidence."
    repository_map = repository_map or {}
    out: List[str] = []
    for f in usable_rows:
        title = str(f.get("title", "Untitled finding"))
        conf = str(
            f.get("effective_confidence", f.get("confidence", "low"))
        ).capitalize()
        text = str(f.get("analysis", ""))
        cite_text = _render_evidence_citations(
            f.get("verified_evidence", []),
            url_map,
            repository_map,
        )
        downgrade = f.get("downgrade_reasons", [])
        downgrade_text = (
            f" Downgrade: {'; '.join(str(x) for x in downgrade)}."
            if downgrade
            else ""
        )
        out.append(
            f"- **{title}** ({conf} confidence): {text} {cite_text}{downgrade_text}".rstrip()
        )
    return "\n".join(out)


def render_analysis_md(
    findings: Dict,
    url_map: Dict[str, int],
    repository_map: Optional[Dict[str, int]] = None,
) -> str:
    sections = findings.get("analysis_sections", []) if isinstance(findings, dict) else []
    usable_sections = [
        row for row in sections if isinstance(row, dict) and row.get("usable", True)
    ]
    if not usable_sections:
        return "### Main Analysis\nNo analysis section had verified supporting evidence."
    repository_map = repository_map or {}
    out = []
    for sec in usable_sections:
        title = str(sec.get("title", "Analysis"))
        content = str(sec.get("content", ""))
        cite_text = _render_evidence_citations(
            sec.get("verified_evidence", []),
            url_map,
            repository_map,
        )
        suffix = f" {cite_text}" if cite_text else ""
        out.append(f"### {title}\n{content}{suffix}".rstrip())
    return "\n\n".join(out)


def _render_statement_rows(
    rows: Sequence[Dict[str, Any]],
    url_map: Dict[str, int],
    repository_map: Dict[str, int],
) -> str:
    usable = [row for row in rows if isinstance(row, dict) and row.get("usable")]
    if not usable:
        return "- None captured with verified evidence."
    out = []
    for row in usable:
        statement = str(row.get("statement", "")).strip()
        cites = _render_evidence_citations(
            row.get("verified_evidence", []),
            url_map,
            repository_map,
        )
        out.append(f"- {statement} {cites}".rstrip())
    return "\n".join(out)


def _source_quality_notes(
    results: Sequence[SearchResult],
    validation: Dict[str, Any],
    code_evidence: Optional[Dict[str, Any]] = None,
) -> str:
    distribution = {tier: 0 for tier in VALID_TIERS}
    for row in results:
        if row.source_tier in distribution:
            distribution[row.source_tier] += 1
    tier_line = ", ".join(f"{tier}: {distribution[tier]}" for tier in VALID_TIERS)
    potential_bias = [
        row.title
        for row in results
        if row.sponsorship.lower() not in {"none", "independent"}
        or row.source_type.lower() in {"vendor", "marketing"}
    ]
    unknown_methodology = sum(
        1 for row in results if row.methodology.lower() == "unknown"
    )
    single_source = sum(
        1
        for row in validation.get("findings", [])
        if len(row.get("verified_evidence", [])) == 1
    )
    unverified = sum(
        1 for row in validation.get("findings", []) if not row.get("usable")
    )
    repository_rows = (
        code_evidence.get("evidence", [])
        if isinstance(code_evidence, dict)
        else []
    )
    code_rows = [
        row
        for row in repository_rows
        if isinstance(row, dict) and str(row.get("kind", "")).lower() == "code"
    ]
    test_rows = [
        row
        for row in repository_rows
        if isinstance(row, dict) and str(row.get("kind", "")).lower() == "test"
    ]
    pinned_code = sum(
        1 for row in code_rows if _is_pinned_commit(row.get("commit", ""))
    )
    passed_tests = sum(
        1 for row in test_rows if str(row.get("status", "")).lower() == "passed"
    )
    repository_quality = (
        "- Repository evidence quality: "
        f"code observations: {len(code_rows)}; commit-pinned: {pinned_code}; "
        f"tests passed: {passed_tests}; "
        f"tests failed/other: {len(test_rows) - passed_tests}"
    )
    if results and repository_rows:
        classification_basis = (
            "- Classification basis: web domain heuristics are provisional; "
            "explicit metadata wins; repository artifacts are assessed directly."
        )
    elif repository_rows:
        classification_basis = (
            "- Classification basis: direct repository artifacts; no web-domain "
            "classification was required."
        )
    else:
        classification_basis = (
            "- Classification basis: domain heuristics are provisional; explicit metadata wins."
        )
    return "\n".join(
        [
            f"- Source tier distribution: {tier_line}",
            classification_basis,
            (
                "- Potential bias / sponsorship requiring review: "
                + (", ".join(potential_bias) if potential_bias else "none identified")
            ),
            f"- Sources with unknown methodology: {unknown_methodology}",
            repository_quality,
            f"- Single-source findings: {single_source}",
            f"- Unverified findings omitted from substantive sections: {unverified}",
            f"- Evidence chain status: {validation.get('evidence_chain_status', 'insufficient')}",
        ]
    )


def _validated_executive_summary(validation: Dict[str, Any]) -> str:
    usable = [
        row
        for row in validation.get("findings", [])
        if isinstance(row, dict) and row.get("usable")
    ]
    degradation = validation.get("degradation", "Blocked")
    if not usable:
        errors = [
            issue.get("message", "")
            for issue in validation.get("issues", [])
            if issue.get("severity") == "error"
        ]
        reason = errors[0] if errors else "no finding had verified evidence"
        return f"Research is blocked: {reason}."
    statements = [
        str(row.get("analysis", "")).strip() or str(row.get("title", "")).strip()
        for row in usable[:3]
    ]
    summary = " ".join(statement for statement in statements if statement)
    if degradation == "Partial":
        return f"Partial result: {summary}"
    return summary or "Validated findings are listed below."


def generate_report(
    question: str,
    findings: Dict,
    results: Sequence[SearchResult],
    depth: str,
    *,
    contents: Sequence[ContentResult] = (),
    code_evidence: Optional[Dict[str, Any]] = None,
    validation: Optional[Dict[str, Any]] = None,
    research_kind: str = "web",
) -> str:
    code_evidence = code_evidence or {}
    if validation is None:
        validation = validate_research_bundle(
            research_kind=research_kind,
            results=results,
            contents=contents,
            code_evidence=code_evidence,
            findings=findings,
        )
    report_mode = _normalize_mode(depth) or "standard"
    cited_results, cited_code_evidence, cited_source_count = select_cited_artifacts(
        results,
        code_evidence,
        validation,
    )
    enforce_report_source_limit(
        count=cited_source_count,
        mode=report_mode,
        limit=MODE_BUDGETS[report_mode]["report_sources_max"],
    )
    url_map, repository_map = _source_maps(
        cited_results,
        cited_code_evidence,
    )
    executive = _validated_executive_summary(validation)
    gaps = findings.get("gaps", []) if isinstance(findings, dict) else []
    issue_gaps = [
        issue["message"]
        for issue in validation.get("issues", [])
        if issue.get("message")
    ]
    combined_gaps = [str(g) for g in gaps] + issue_gaps
    gaps_md = (
        "\n".join(f"- {g}" for g in dict.fromkeys(combined_gaps))
        if combined_gaps
        else "- None documented."
    )
    counts = validation.get("counts", {})

    return f"""## 1) Research Question
- Normalized question: {question}
- Research kind: `{research_kind}`
- Depth mode: `{report_mode}`
- Evidence chain requirements: typed evidence; extracted excerpts for web claims; repository evidence IDs for codebase claims

## 2) Method
- Execution mode: `{report_mode}`
- Degradation level: `{validation.get('degradation', 'Blocked')}`
- Retrieval plan (queries/subtopics): {len({r.query for r in results if r.query})} distinct queries represented
- Dedup strategy: normalized URL canonicalization + first-seen retention
- Retrieved sources: {counts.get('retrieved', 0)}
- Content items processed: {counts.get('content_items', 0)}
- Successfully extracted: {counts.get('successfully_extracted', 0)}
- Repository evidence units: {counts.get('repository_evidence', 0)}
- Cited evidence units: {counts.get('cited_evidence', 0)}
- Validation checks performed: required-input, extraction-success, exact excerpt, repository reference, confidence, and degradation checks

## 3) Executive Summary
{executive}

## 4) Key Findings
{render_findings_md({"findings": validation.get("findings", [])}, url_map, repository_map)}

## 5) Detailed Analysis
{render_analysis_md({"analysis_sections": validation.get("analysis_sections", [])}, url_map, repository_map)}

## 6) Consensus vs Debate
### Consensus
{_render_statement_rows(validation.get("consensus", []), url_map, repository_map)}

### Debate / Contradictory Evidence
{_render_statement_rows(validation.get("debate", []), url_map, repository_map)}

## 7) Source Quality Notes
{_source_quality_notes(cited_results, validation, cited_code_evidence)}

## 8) Sources
{build_sources_index(cited_results, cited_code_evidence)}

## 9) Gaps & Limitations
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

def _load_budget_session(args: argparse.Namespace) -> Dict[str, Any]:
    session_path = Path(args.session)
    expected_mode = str(getattr(args, "mode", "") or "")
    state = load_session(session_path, expected_mode=expected_mode)
    args.mode = state["mode"]
    return state


def cmd_plan(args: argparse.Namespace) -> int:
    plan = plan_research(
        args.request,
        explicit_mode=args.mode,
        explicit_kind=args.research_kind,
    )
    if args.output:
        try:
            plan = initialize_session(Path(args.output), plan)
        except (ValueError, OSError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
    print(json.dumps(plan, indent=2, ensure_ascii=True))
    return 0


def cmd_reserve_budget(args: argparse.Namespace) -> int:
    """Reserve ledger budget before an external host retrieval/fetch action."""
    try:
        reservation = reserve_session_budget(
            Path(args.session),
            args.budget,
            args.count,
            allow_partial=False,
        )
    except (ValueError, OSError, json.JSONDecodeError, BudgetExceededError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    write_json(Path(args.output), reservation)
    print(
        f"budget={args.budget} reserved={reservation['reserved']} "
        f"remaining={reservation['remaining']} output={args.output}"
    )
    return 0


def cmd_retrieve(args: argparse.Namespace) -> int:
    try:
        session = _load_budget_session(args)
        reservation = reserve_session_budget(
            Path(args.session),
            "retrieval_calls",
            len(args.query),
            allow_partial=False,
        )
    except (ValueError, OSError, json.JSONDecodeError, BudgetExceededError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
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
        "session_id": session["session_id"],
        "mode": args.mode,
        "budget": dict(MODE_BUDGETS[args.mode]),
        "retrieval_calls_used": reservation["reserved"],
        "queries": args.query,
        "count_before_dedupe": len(all_results),
        "count_after_dedupe": len(deduped),
        "retrieval_errors": retrieval_errors,
        "results": [asdict(x) for x in deduped],
    }
    write_json(Path(args.output), payload)

    print(f"retrieved={len(all_results)} deduped={len(deduped)} output={args.output}")
    if retrieval_errors and not deduped:
        return 2
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    results = load_results(Path(args.results)) if args.results else []
    contents, content_metadata = (
        load_content_artifact(Path(args.content))
        if args.content
        else ([], {})
    )
    code_evidence = (
        load_code_evidence(Path(args.code_evidence))
        if args.code_evidence
        else {}
    )
    findings = load_findings(Path(args.findings))
    url_issues: List[Dict[str, Any]] = []
    details = []

    for row in results:
        ok, why = validate_url_format(row.normalized_url)
        if not ok:
            url_issues.append(
                _issue(
                    "invalid_url",
                    f"invalid URL format: {row.url} ({why})",
                )
            )
            continue

        reachable = None
        status = None
        error = ""
        if args.check_live:
            reachable, status, error = check_reachability(row.normalized_url, timeout=args.timeout)
            if not reachable:
                url_issues.append(
                    _issue(
                        "unreachable_url",
                        f"unreachable URL: {row.normalized_url} ({status} {error})",
                    )
                )

        details.append(
            {
                "url": row.normalized_url,
                "domain": row.domain,
                "source_type": row.source_type,
                "source_tier": row.source_tier,
                "classification_basis": row.classification_basis,
                "reachable": reachable,
                "status": status,
                "error": error,
            }
        )

    payload = validate_research_bundle(
        research_kind=args.research_kind,
        results=results,
        contents=contents,
        code_evidence=code_evidence,
        findings=findings,
        budget_exhausted=(
            args.budget_exhausted
            or bool(content_metadata.get("budget_exhausted", False))
        ),
    )
    payload["checked_count"] = len(results)
    payload["details"] = details
    payload["issues"] = url_issues + payload["issues"]
    if args.output:
        write_json(Path(args.output), payload)

    print(
        f"validated={len(results)} issues={len(payload['issues'])} "
        f"degradation={payload['degradation']}"
    )
    return 2 if payload["degradation"] == "Blocked" or url_issues else 0


def cmd_report(args: argparse.Namespace) -> int:
    try:
        session = _load_budget_session(args)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    results = load_results(Path(args.results)) if args.results else []
    results = dedupe_results(results)
    contents, content_metadata = (
        load_content_artifact(Path(args.content))
        if args.content
        else ([], {})
    )
    code_evidence = (
        load_code_evidence(Path(args.code_evidence))
        if args.code_evidence
        else {}
    )
    findings = load_findings(Path(args.findings))
    validation = validate_research_bundle(
        research_kind=args.research_kind,
        results=results,
        contents=contents,
        code_evidence=code_evidence,
        findings=findings,
        budget_exhausted=(
            args.budget_exhausted
            or bool(content_metadata.get("budget_exhausted", False))
        ),
    )
    if args.validation_output:
        write_json(Path(args.validation_output), validation)

    _, _, cited_source_count = select_cited_artifacts(
        results,
        code_evidence,
        validation,
    )
    try:
        record_report_sources(Path(args.session), cited_source_count)
        report = generate_report(
            args.question,
            findings,
            results,
            depth=args.mode,
            contents=contents,
            code_evidence=code_evidence,
            validation=validation,
            research_kind=args.research_kind,
        )
    except (BudgetExceededError, ReportSourceBudgetError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    out_path = Path(args.output)
    out_path.write_text(report)
    print(
        f"report={out_path} sources={cited_source_count} "
        f"degradation={validation['degradation']} session={session['session_id']}"
    )
    return 2 if validation["degradation"] == "Blocked" else 0


def cmd_fetch_content(args: argparse.Namespace) -> int:
    """Fetch and extract text content from URLs (parallel)."""
    try:
        session = _load_budget_session(args)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.results:
        results = load_results(Path(args.results))
        urls = [r.normalized_url for r in results]
    elif args.url:
        urls = list(args.url)
    else:
        print("provide --results or --url", file=sys.stderr)
        return 2

    input_count = len(urls)
    mode_limit = MODE_BUDGETS[args.mode]["content_max"]
    if args.limit > mode_limit:
        print(
            f"{args.mode} mode permits at most {mode_limit} content extractions",
            file=sys.stderr,
        )
        return 2
    requested = min(input_count, args.limit or mode_limit)
    try:
        reservation = reserve_session_budget(
            Path(args.session),
            "content_extractions",
            requested,
            allow_partial=True,
        )
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    urls = urls[:reservation["reserved"]]
    budget_exhausted = input_count > reservation["reserved"]

    contents = fetch_contents_parallel(
        urls,
        timeout=args.timeout,
        max_workers=args.workers,
    )

    payload = {
        "generated_at": utc_now_iso(),
        "session_id": session["session_id"],
        "mode": args.mode,
        "budget": dict(MODE_BUDGETS[args.mode]),
        "requested_count": input_count,
        "processed_count": reservation["reserved"],
        "budget_exhausted": budget_exhausted,
        "count": len(contents),
        "items": [asdict(c) for c in contents],
    }
    write_json(Path(args.output), payload)

    ok = sum(1 for c in contents if not c.error)
    fail = sum(1 for c in contents if c.error)
    print(f"fetched={ok} errors={fail} output={args.output}")
    return 2 if ok == 0 and urls else 0


def _git_snapshot(root: Path) -> Tuple[str, str]:
    _, commit, subject = git_repository_context(root)
    return commit, subject


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
    evidence: List[Dict[str, Any]] = []
    repo_root, commit, commit_subject = git_repository_context(root)
    for m in matches:
        if "error" in m:
            errors.append(m)
            continue
        f = m.get("file", "unknown")
        by_file.setdefault(f, []).append(m)
        path = Path(str(f))
        if not path.is_absolute():
            path = (root / path).resolve()
        provenance = code_record_provenance(
            repo_root=repo_root,
            file_path=path,
            head_commit=commit,
        )
        evidence.append(
            {
                "id": f"code-{len(evidence) + 1}",
                "kind": "code",
                "path": provenance["path"],
                "line": int(m.get("line", 0) or 0),
                "excerpt": str(m.get("text", "")).rstrip("\r\n"),
                "commit": provenance["commit"],
                "snapshot": provenance["snapshot"],
            }
        )
    if commit:
        evidence.append(
            {
                "id": "commit-head",
                "kind": "commit",
                "commit": commit,
                "subject": commit_subject or "HEAD",
            }
        )

    payload = {
        "generated_at": utc_now_iso(),
        "root": str(repo_root),
        "search_root": str(root),
        "patterns": list(args.pattern),
        "total_matches": sum(len(v) for v in by_file.values()),
        "files_matched": len(by_file),
        "errors": errors,
        "matches_by_file": {f: ms for f, ms in sorted(by_file.items())},
        "evidence": evidence,
    }
    write_json(Path(args.output), payload)
    print(f"matches={payload['total_matches']} files={payload['files_matched']} output={args.output}")
    return 0


def cmd_snapshot_codebase(args: argparse.Namespace) -> int:
    """Write read-only Git identity metadata for a host-created receipt."""
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"root path not found: {root}", file=sys.stderr)
        return 2
    try:
        payload = repository_snapshot(root)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    output = Path(args.output).resolve()
    repository_root = Path(payload["root"]).resolve()
    try:
        output.relative_to(repository_root)
    except ValueError:
        pass
    else:
        print(
            "snapshot output must be outside the Git repository so the helper "
            "does not change the measured dirty state",
            file=sys.stderr,
        )
        return 2
    payload["generated_at"] = utc_now_iso()
    write_json(output, payload)
    print(
        f"snapshot={payload['head_commit']} dirty={str(payload['dirty']).lower()} "
        f"output={args.output}"
    )
    return 0


def _receipt_record(payload: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return None
    if payload.get("kind") == "test":
        return payload
    rows = payload.get("evidence", [])
    if isinstance(rows, list):
        tests = [
            row
            for row in rows
            if isinstance(row, dict) and row.get("kind") == "test"
        ]
        if len(tests) == 1:
            return tests[0]
    return None


def cmd_import_test_receipt(args: argparse.Namespace) -> int:
    """Statically verify and append one host-created test receipt."""
    try:
        receipt_payload = json.loads(Path(args.receipt).read_text(encoding="utf-8"))
        record = _receipt_record(receipt_payload)
        if record is None:
            raise ValueError("receipt must contain exactly one test evidence record")
        evidence = load_code_evidence(Path(args.code_evidence))
        rows = evidence.get("evidence", [])
        if not isinstance(rows, list):
            raise ValueError("code evidence artifact must contain an evidence array")
        evidence_id = str(record.get("id", "")).strip()
        if not evidence_id:
            raise ValueError("test receipt must declare an evidence id")
        if any(
            isinstance(row, dict)
            and str(row.get("id", "")).strip() == evidence_id
            for row in rows
        ):
            raise ValueError(f"duplicate evidence id: {evidence_id}")
        candidate = dict(evidence)
        candidate["evidence"] = list(rows) + [record]
        verified, issue = RepositoryEvidenceVerifier(candidate).verify(
            evidence_id,
            "test",
        )
        if issue or not verified:
            message = issue["message"] if issue else "test receipt was not verified"
            raise ValueError(message)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    candidate["generated_at"] = utc_now_iso()
    write_json(Path(args.output), candidate)
    print(f"imported={evidence_id} output={args.output}")
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

class ResearchArgumentParser(argparse.ArgumentParser):
    """Argument parser that enforces budgets and conditional evidence inputs."""

    def parse_args(
        self,
        args: Optional[Sequence[str]] = None,
        namespace: Optional[argparse.Namespace] = None,
    ) -> argparse.Namespace:
        parsed = super().parse_args(args=args, namespace=namespace)
        cmd = getattr(parsed, "cmd", "")
        if cmd in {"reserve-budget", "retrieve", "fetch-content", "report"} and not parsed.session:
            self.error(f"{cmd} requires --session")
        if cmd == "reserve-budget" and parsed.count <= 0:
            self.error("--count must be positive")
        if cmd == "retrieve":
            limit = MODE_BUDGETS[
                parsed.mode or "deep"
            ]["retrieval_max"]
            if len(parsed.query) > limit:
                self.error(
                    f"{parsed.mode or 'global'} mode permits at most {limit} "
                    "retrieval calls per invocation; "
                    f"received {len(parsed.query)} queries"
                )
        if cmd == "fetch-content":
            if parsed.limit < 0:
                self.error("--limit must be non-negative")
        if cmd == "fetch-content":
            limit = MODE_BUDGETS[parsed.mode or "deep"]["content_max"]
            if parsed.limit > limit:
                self.error(
                    f"{parsed.mode or 'global'} mode permits at most {limit} "
                    "content extractions per invocation"
                )
        if cmd in {"validate", "report"}:
            kind = parsed.research_kind
            if not parsed.findings:
                self.error("--findings is required")
            if kind in {"web", "hybrid"}:
                if not parsed.results:
                    self.error(f"{kind} research requires --results")
                if not parsed.content:
                    self.error(f"{kind} research requires --content")
            if kind in {"codebase", "hybrid"} and not parsed.code_evidence:
                self.error(f"{kind} research requires --code-evidence")
        return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = ResearchArgumentParser(description="Deep research helper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser("plan", help="classify request and emit executable budgets")
    p_plan.add_argument("--request", required=True, help="research request text")
    p_plan.add_argument("--mode", choices=VALID_MODES, default="", help="explicit mode override")
    p_plan.add_argument(
        "--research-kind",
        choices=VALID_RESEARCH_KINDS,
        default="",
        help="explicit evidence-kind override",
    )
    p_plan.add_argument("--output", default="", help="optional plan JSON path")
    p_plan.set_defaults(func=cmd_plan)

    p_reserve = sub.add_parser(
        "reserve-budget",
        help="reserve session budget before external host retrieval or extraction",
    )
    p_reserve.add_argument("--session", required=True, help="plan/session JSON path")
    p_reserve.add_argument(
        "--budget",
        choices=("retrieval_calls", "content_extractions"),
        required=True,
    )
    p_reserve.add_argument("--count", type=int, required=True)
    p_reserve.add_argument("--output", required=True, help="reservation JSON path")
    p_reserve.set_defaults(func=cmd_reserve_budget)

    p_retrieve = sub.add_parser("retrieve", help="retrieve web results and dedupe")
    p_retrieve.add_argument("--query", action="append", required=True, help="search query (repeatable)")
    p_retrieve.add_argument("--session", required=True, help="plan/session JSON path")
    p_retrieve.add_argument("--mode", choices=VALID_MODES, default="")
    p_retrieve.add_argument("--limit-per-query", type=int, default=8)
    p_retrieve.add_argument("--timeout", type=float, default=12.0)
    p_retrieve.add_argument("--delay", type=float, default=DEFAULT_REQUEST_DELAY, help="seconds between queries")
    p_retrieve.add_argument("--output", required=True, help="output JSON path")
    p_retrieve.set_defaults(func=cmd_retrieve)

    p_validate = sub.add_parser("validate", help="validate findings against evidence artifacts")
    p_validate.add_argument("--research-kind", choices=VALID_RESEARCH_KINDS, default="web")
    p_validate.add_argument("--results", default="", help="retrieval JSON path")
    p_validate.add_argument("--content", default="", help="content extraction JSON path")
    p_validate.add_argument("--code-evidence", default="", help="repository evidence JSON path")
    p_validate.add_argument("--findings", required=True, help="findings JSON path")
    p_validate.add_argument("--budget-exhausted", action="store_true")
    p_validate.add_argument("--check-live", action="store_true", help="perform runtime reachability checks")
    p_validate.add_argument("--timeout", type=float, default=8.0)
    p_validate.add_argument("--output", default="", help="optional validation JSON path")
    p_validate.set_defaults(func=cmd_validate)

    p_report = sub.add_parser("report", help="generate markdown report")
    p_report.add_argument("--question", required=True)
    p_report.add_argument("--research-kind", choices=VALID_RESEARCH_KINDS, default="web")
    p_report.add_argument("--results", default="", help="retrieval JSON path")
    p_report.add_argument("--content", default="", help="content extraction JSON path")
    p_report.add_argument("--code-evidence", default="", help="repository evidence JSON path")
    p_report.add_argument("--findings", required=True, help="findings JSON path")
    p_report.add_argument("--session", required=True, help="plan/session JSON path")
    p_report.add_argument("--mode", "--depth", dest="mode", choices=VALID_MODES, default="")
    p_report.add_argument("--budget-exhausted", action="store_true")
    p_report.add_argument("--validation-output", default="", help="optional validation JSON path")
    p_report.add_argument("--output", required=True, help="output markdown path")
    p_report.set_defaults(func=cmd_report)

    p_content = sub.add_parser("fetch-content", help="fetch and extract text from URLs")
    p_content.add_argument("--results", default="", help="retrieval JSON path (use URLs from here)")
    p_content.add_argument("--url", action="append", help="explicit URL to fetch (repeatable)")
    p_content.add_argument("--limit", type=int, default=0, help="max URLs to fetch (0=all)")
    p_content.add_argument("--session", required=True, help="plan/session JSON path")
    p_content.add_argument("--mode", choices=VALID_MODES, default="")
    p_content.add_argument("--timeout", type=float, default=15.0)
    p_content.add_argument("--workers", type=int, default=CONTENT_FETCH_WORKERS, help="parallel fetch workers")
    p_content.add_argument("--output", required=True, help="output JSON path")
    p_content.set_defaults(func=cmd_fetch_content)

    p_codebase = sub.add_parser("search-codebase", help="search local codebase with ripgrep")
    p_codebase.add_argument("--pattern", action="append", required=True, help="search pattern (repeatable)")
    p_codebase.add_argument("--root", default=".", help="codebase root directory")
    p_codebase.add_argument("--glob", action="append", help="file glob filter (repeatable)")
    p_codebase.add_argument("--context", type=int, default=2, help="context lines around matches")
    p_codebase.add_argument("--output", required=True, help="output JSON path")
    p_codebase.set_defaults(func=cmd_search_codebase)

    p_snapshot = sub.add_parser(
        "snapshot-codebase",
        help="read HEAD, tree, and dirty state without executing tests",
    )
    p_snapshot.add_argument("--root", default=".", help="codebase root directory")
    p_snapshot.add_argument("--output", required=True, help="snapshot JSON path")
    p_snapshot.set_defaults(func=cmd_snapshot_codebase)

    p_receipt = sub.add_parser(
        "import-test-receipt",
        help="statically verify and append a host-created test receipt",
    )
    p_receipt.add_argument("--receipt", required=True, help="host test receipt JSON")
    p_receipt.add_argument(
        "--code-evidence",
        required=True,
        help="existing repository evidence artifact to extend",
    )
    p_receipt.add_argument("--output", required=True, help="output evidence JSON path")
    p_receipt.set_defaults(func=cmd_import_test_receipt)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

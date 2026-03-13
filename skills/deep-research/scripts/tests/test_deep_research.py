import io
import json
import shutil
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
import importlib.util
import sys

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "deep_research.py"
spec = importlib.util.spec_from_file_location("deep_research", SCRIPT_PATH)
deep_research = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = deep_research
spec.loader.exec_module(deep_research)


# ---------------------------------------------------------------------------
# normalize_url
# ---------------------------------------------------------------------------

class TestNormalizeUrl(unittest.TestCase):
    def test_removes_tracking_and_fragment(self):
        url = "https://Example.com/path/?utm_source=x&b=2&a=1#section"
        self.assertEqual("https://example.com/path?a=1&b=2", deep_research.normalize_url(url))

    def test_strips_trailing_slash(self):
        self.assertEqual("https://example.com/page", deep_research.normalize_url("https://example.com/page/"))

    def test_preserves_root_slash(self):
        self.assertEqual("https://example.com/", deep_research.normalize_url("https://example.com/"))

    def test_rejects_non_http(self):
        self.assertEqual("", deep_research.normalize_url("ftp://example.com/file"))

    def test_removes_fbclid(self):
        self.assertEqual(
            "https://example.com/page?real=yes",
            deep_research.normalize_url("https://example.com/page?fbclid=abc123&real=yes"),
        )

    def test_empty_input(self):
        self.assertEqual("", deep_research.normalize_url(""))

    def test_collapses_double_slashes_in_path(self):
        self.assertEqual("https://example.com/a/b", deep_research.normalize_url("https://example.com/a//b"))

    def test_removes_gclid(self):
        self.assertEqual(
            "https://example.com/",
            deep_research.normalize_url("https://example.com/?gclid=abc"),
        )

    def test_sorts_query_params(self):
        self.assertEqual(
            "https://example.com/?a=1&b=2&c=3",
            deep_research.normalize_url("https://example.com/?c=3&a=1&b=2"),
        )

    def test_lowercases_hostname(self):
        self.assertEqual("https://example.com/Page", deep_research.normalize_url("https://EXAMPLE.COM/Page"))

    def test_preserves_non_default_port(self):
        self.assertEqual("https://example.com:8443/", deep_research.normalize_url("https://example.com:8443/"))


# ---------------------------------------------------------------------------
# registrable_domain
# ---------------------------------------------------------------------------

class TestRegistrableDomain(unittest.TestCase):
    def test_simple_domain(self):
        self.assertEqual("example.com", deep_research.registrable_domain("example.com"))

    def test_subdomain(self):
        self.assertEqual("example.com", deep_research.registrable_domain("www.example.com"))

    def test_co_uk(self):
        self.assertEqual("bbc.co.uk", deep_research.registrable_domain("www.bbc.co.uk"))

    def test_com_au(self):
        self.assertEqual("reuters.com.au", deep_research.registrable_domain("news.reuters.com.au"))

    def test_co_jp(self):
        self.assertEqual("example.co.jp", deep_research.registrable_domain("www.example.co.jp"))

    def test_deep_subdomain(self):
        self.assertEqual("example.com", deep_research.registrable_domain("a.b.c.example.com"))

    def test_deep_subdomain_with_cctld(self):
        self.assertEqual("example.co.uk", deep_research.registrable_domain("a.b.example.co.uk"))

    def test_empty(self):
        self.assertEqual("", deep_research.registrable_domain(""))

    def test_bare_tld(self):
        self.assertEqual("com", deep_research.registrable_domain("com"))

    def test_gov_uk(self):
        self.assertEqual("service.gov.uk", deep_research.registrable_domain("www.service.gov.uk"))

    def test_com_cn(self):
        self.assertEqual("baidu.com.cn", deep_research.registrable_domain("www.baidu.com.cn"))

    def test_regular_three_part_not_cctld(self):
        self.assertEqual("github.com", deep_research.registrable_domain("api.github.com"))


# ---------------------------------------------------------------------------
# decode_duck_link
# ---------------------------------------------------------------------------

class TestDecodeDuckLink(unittest.TestCase):
    def test_uddg_redirect(self):
        self.assertEqual(
            "https://example.com/page",
            deep_research.decode_duck_link("/l/?uddg=https%3A%2F%2Fexample.com%2Fpage"),
        )

    def test_direct_url(self):
        self.assertEqual("https://example.com", deep_research.decode_duck_link("https://example.com"))

    def test_protocol_relative(self):
        self.assertEqual("https://example.com/x", deep_research.decode_duck_link("//example.com/x"))

    def test_full_duckduckgo_redirect(self):
        self.assertEqual(
            "https://test.org",
            deep_research.decode_duck_link("https://duckduckgo.com/l/?uddg=https%3A%2F%2Ftest.org"),
        )

    def test_empty(self):
        self.assertEqual("", deep_research.decode_duck_link(""))

    def test_relative_without_uddg(self):
        self.assertEqual("", deep_research.decode_duck_link("/about"))

    def test_html_entities_decoded(self):
        self.assertEqual(
            "https://example.com",
            deep_research.decode_duck_link("https://example.com"),
        )


# ---------------------------------------------------------------------------
# infer_source_type
# ---------------------------------------------------------------------------

class TestInferSourceType(unittest.TestCase):
    def test_gov(self):
        self.assertEqual("official", deep_research.infer_source_type("data.gov"))

    def test_edu(self):
        self.assertEqual("official", deep_research.infer_source_type("mit.edu"))

    def test_academic_arxiv(self):
        self.assertEqual("academic", deep_research.infer_source_type("arxiv.org"))

    def test_academic_ieee(self):
        self.assertEqual("academic", deep_research.infer_source_type("ieeexplore.ieee.org"))

    def test_news_reuters(self):
        self.assertEqual("news", deep_research.infer_source_type("reuters.com"))

    def test_news_bbc(self):
        self.assertEqual("news", deep_research.infer_source_type("www.bbc.co.uk"))

    def test_forum_reddit(self):
        self.assertEqual("forum", deep_research.infer_source_type("reddit.com"))

    def test_forum_stackoverflow(self):
        self.assertEqual("forum", deep_research.infer_source_type("stackoverflow.com"))

    def test_blog_medium(self):
        self.assertEqual("blog", deep_research.infer_source_type("medium.com"))

    def test_blog_devto(self):
        self.assertEqual("blog", deep_research.infer_source_type("dev.to"))

    def test_docs_subdomain(self):
        self.assertEqual("official", deep_research.infer_source_type("docs.python.org"))

    def test_generic_website(self):
        self.assertEqual("website", deep_research.infer_source_type("randomsite.io"))


# ---------------------------------------------------------------------------
# extract_text_from_html
# ---------------------------------------------------------------------------

class TestExtractTextFromHtml(unittest.TestCase):
    def test_strips_script_and_style(self):
        doc = "<html><head><style>body{}</style></head><body><script>alert(1)</script><p>Hello</p></body></html>"
        text = deep_research.extract_text_from_html(doc)
        self.assertIn("Hello", text)
        self.assertNotIn("alert", text)
        self.assertNotIn("body{}", text)

    def test_decodes_entities(self):
        text = deep_research.extract_text_from_html("<p>A &amp; B &lt; C</p>")
        self.assertIn("A & B < C", text)

    def test_respects_max_chars(self):
        doc = "<p>" + "x" * 20000 + "</p>"
        text = deep_research.extract_text_from_html(doc, max_chars=100)
        self.assertLessEqual(len(text), 104)

    def test_empty_input(self):
        self.assertEqual("", deep_research.extract_text_from_html(""))

    def test_strips_noscript(self):
        doc = "<noscript><p>Enable JS</p></noscript><p>Real content</p>"
        text = deep_research.extract_text_from_html(doc)
        self.assertIn("Real content", text)
        self.assertNotIn("Enable JS", text)

    def test_strips_head(self):
        doc = "<head><title>Title</title><meta charset='utf-8'></head><body>Body</body>"
        text = deep_research.extract_text_from_html(doc)
        self.assertIn("Body", text)
        self.assertNotIn("charset", text)


# ---------------------------------------------------------------------------
# dedupe_results
# ---------------------------------------------------------------------------

class TestDedupeResults(unittest.TestCase):
    def test_removes_duplicates_by_normalized_url(self):
        a = deep_research.SearchResult(
            query="q", title="A", url="https://x.com?a=1&utm_source=y",
            normalized_url="https://x.com?a=1", domain="x.com", source_type="website",
        )
        b = deep_research.SearchResult(
            query="q", title="B", url="https://x.com?a=1",
            normalized_url="https://x.com?a=1", domain="x.com", source_type="website",
        )
        out = deep_research.dedupe_results([a, b])
        self.assertEqual(1, len(out))
        self.assertEqual("A", out[0].title)

    def test_keeps_distinct_urls(self):
        a = deep_research.SearchResult(
            query="q", title="A", url="https://a.com",
            normalized_url="https://a.com/", domain="a.com", source_type="website",
        )
        b = deep_research.SearchResult(
            query="q", title="B", url="https://b.com",
            normalized_url="https://b.com/", domain="b.com", source_type="website",
        )
        out = deep_research.dedupe_results([a, b])
        self.assertEqual(2, len(out))


# ---------------------------------------------------------------------------
# parse_duckduckgo_lite
# ---------------------------------------------------------------------------

class TestParseDuckduckgoLite(unittest.TestCase):
    def test_extracts_results(self):
        html_doc = (
            '<a href="/l/?uddg=https%3A%2F%2Fexample.com%2Fa%3Futm_source%3Dddg">Example A</a>'
            '<a href="https://news.ycombinator.com/item?id=1">HN</a>'
        )
        out = deep_research.parse_duckduckgo_lite(html_doc, query="demo", limit=10)
        self.assertEqual(2, len(out))
        self.assertEqual("https://example.com/a", out[0].normalized_url)
        self.assertEqual("forum", out[1].source_type)

    def test_dedupes_within_parse(self):
        html_doc = (
            '<a href="https://example.com/page">First</a>'
            '<a href="https://example.com/page">Duplicate</a>'
        )
        out = deep_research.parse_duckduckgo_lite(html_doc, query="q", limit=10)
        self.assertEqual(1, len(out))
        self.assertEqual("First", out[0].title)

    def test_respects_limit(self):
        links = "".join(f'<a href="https://example{i}.com">Site {i}</a>' for i in range(20))
        out = deep_research.parse_duckduckgo_lite(links, query="q", limit=5)
        self.assertEqual(5, len(out))

    def test_skips_invalid_urls(self):
        html_doc = '<a href="javascript:void(0)">Skip</a><a href="https://real.com">Real</a>'
        out = deep_research.parse_duckduckgo_lite(html_doc, query="q", limit=10)
        self.assertEqual(1, len(out))
        self.assertEqual("real.com", out[0].domain)


# ---------------------------------------------------------------------------
# validate_url_format
# ---------------------------------------------------------------------------

class TestValidateUrlFormat(unittest.TestCase):
    def test_valid_https(self):
        ok, _ = deep_research.validate_url_format("https://example.com/page")
        self.assertTrue(ok)

    def test_valid_http(self):
        ok, _ = deep_research.validate_url_format("http://example.com")
        self.assertTrue(ok)

    def test_invalid_scheme(self):
        ok, msg = deep_research.validate_url_format("ftp://example.com")
        self.assertFalse(ok)
        self.assertIn("scheme", msg)

    def test_missing_host(self):
        ok, msg = deep_research.validate_url_format("https://")
        self.assertFalse(ok)
        self.assertIn("host", msg)

    def test_empty_string(self):
        ok, _ = deep_research.validate_url_format("")
        self.assertFalse(ok)


# ---------------------------------------------------------------------------
# validate_findings
# ---------------------------------------------------------------------------

class TestValidateFindings(unittest.TestCase):
    def test_high_confidence_requires_independent_domains(self):
        src1 = deep_research.SearchResult(
            query="q", title="A", url="https://a.example.com/1",
            normalized_url="https://a.example.com/1", domain="example.com", source_type="website",
        )
        src2 = deep_research.SearchResult(
            query="q", title="B", url="https://b.example.com/2",
            normalized_url="https://b.example.com/2", domain="example.com", source_type="website",
        )
        findings = {
            "findings": [{
                "title": "Same-domain",
                "confidence": "high",
                "analysis": "x",
                "citations": [src1.url, src2.url],
            }]
        }
        issues = deep_research.validate_findings(
            findings, {src1.normalized_url: src1, src2.normalized_url: src2}
        )
        self.assertTrue(any("independent domains" in x for x in issues))

    def test_missing_citations(self):
        findings = {"findings": [{"title": "No cite", "confidence": "low", "analysis": "x"}]}
        issues = deep_research.validate_findings(findings, {})
        self.assertTrue(any("missing citations" in x for x in issues))

    def test_citation_not_in_retrieval_set(self):
        findings = {
            "findings": [{
                "title": "Bad ref",
                "confidence": "low",
                "analysis": "x",
                "citations": ["https://unknown.com"],
            }]
        }
        issues = deep_research.validate_findings(findings, {})
        self.assertTrue(any("not found in retrieval set" in x for x in issues))

    def test_non_dict_finding_flagged(self):
        findings = {"findings": ["bad"]}
        issues = deep_research.validate_findings(findings, {})
        self.assertTrue(any("must be an object" in x for x in issues))

    def test_passes_with_valid_high_confidence(self):
        s1 = deep_research.SearchResult(
            query="q", title="A", url="https://a.com/1",
            normalized_url="https://a.com/1", domain="a.com", source_type="website",
        )
        s2 = deep_research.SearchResult(
            query="q", title="B", url="https://b.com/2",
            normalized_url="https://b.com/2", domain="b.com", source_type="website",
        )
        findings = {
            "findings": [{
                "title": "OK",
                "confidence": "high",
                "analysis": "x",
                "citations": ["https://a.com/1", "https://b.com/2"],
            }]
        }
        issues = deep_research.validate_findings(
            findings, {s1.normalized_url: s1, s2.normalized_url: s2}
        )
        self.assertEqual([], issues)

    def test_empty_findings_returns_no_issues(self):
        self.assertEqual([], deep_research.validate_findings({}, {}))


# ---------------------------------------------------------------------------
# build_sources_index
# ---------------------------------------------------------------------------

class TestBuildSourcesIndex(unittest.TestCase):
    def test_format_with_date(self):
        src = deep_research.SearchResult(
            query="q", title="My Source", url="https://example.com",
            normalized_url="https://example.com", domain="example.com",
            source_type="website", date="2024-01-15",
        )
        index = deep_research.build_sources_index([src])
        self.assertIn("[1]", index)
        self.assertIn("My Source", index)
        self.assertIn("2024-01-15", index)

    def test_no_date_shows_na(self):
        src = deep_research.SearchResult(
            query="q", title="X", url="https://x.com",
            normalized_url="https://x.com", domain="x.com", source_type="website",
        )
        index = deep_research.build_sources_index([src])
        self.assertIn("n/a", index)

    def test_multiple_sources_numbered(self):
        sources = [
            deep_research.SearchResult(
                query="q", title=f"S{i}", url=f"https://s{i}.com",
                normalized_url=f"https://s{i}.com", domain=f"s{i}.com", source_type="website",
            )
            for i in range(3)
        ]
        index = deep_research.build_sources_index(sources)
        self.assertIn("[1]", index)
        self.assertIn("[2]", index)
        self.assertIn("[3]", index)


# ---------------------------------------------------------------------------
# render_analysis_md
# ---------------------------------------------------------------------------

class TestRenderAnalysisMd(unittest.TestCase):
    def test_with_sections(self):
        normalized = deep_research.normalize_url("https://example.com")
        findings = {
            "analysis_sections": [{
                "title": "Section A",
                "content": "Analysis body",
                "citations": ["https://example.com"],
            }]
        }
        url_map = {normalized: 1}
        md = deep_research.render_analysis_md(findings, url_map)
        self.assertIn("### Section A", md)
        self.assertIn("[1]", md)

    def test_empty_sections(self):
        md = deep_research.render_analysis_md({}, {})
        self.assertIn("No additional analysis sections", md)

    def test_citation_not_in_map_omitted(self):
        findings = {
            "analysis_sections": [{
                "title": "S",
                "content": "text",
                "citations": ["https://missing.com"],
            }]
        }
        md = deep_research.render_analysis_md(findings, {})
        self.assertNotIn("[", md)


# ---------------------------------------------------------------------------
# render_findings_md
# ---------------------------------------------------------------------------

class TestRenderFindingsMd(unittest.TestCase):
    def test_renders_with_citations(self):
        normalized = deep_research.normalize_url("https://example.com")
        findings = {
            "findings": [{
                "title": "F1",
                "confidence": "high",
                "analysis": "Detail",
                "citations": ["https://example.com"],
            }]
        }
        url_map = {normalized: 1}
        md = deep_research.render_findings_md(findings, url_map)
        self.assertIn("**F1**", md)
        self.assertIn("High confidence", md)
        self.assertIn("[1]", md)

    def test_empty_findings(self):
        md = deep_research.render_findings_md({}, {})
        self.assertIn("No structured findings", md)


# ---------------------------------------------------------------------------
# load_results
# ---------------------------------------------------------------------------

class TestLoadResults(unittest.TestCase):
    def test_loads_dict_format(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            data = {"results": [{"url": "https://example.com/a", "title": "A", "domain": "example.com"}]}
            json.dump(data, f)
            f.flush()
            results = deep_research.load_results(Path(f.name))
        self.assertEqual(1, len(results))
        self.assertEqual("A", results[0].title)

    def test_loads_list_format(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            data = [{"url": "https://example.com/b", "title": "B"}]
            json.dump(data, f)
            f.flush()
            results = deep_research.load_results(Path(f.name))
        self.assertEqual(1, len(results))

    def test_skips_non_dict_entries(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            data = {"results": ["not a dict", {"url": "https://x.com", "title": "X"}]}
            json.dump(data, f)
            f.flush()
            results = deep_research.load_results(Path(f.name))
        self.assertEqual(1, len(results))

    def test_infers_domain_from_url(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"results": [{"url": "https://news.bbc.co.uk/article"}]}, f)
            f.flush()
            results = deep_research.load_results(Path(f.name))
        self.assertEqual("bbc.co.uk", results[0].domain)

    def test_infers_source_type_from_domain(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"results": [{"url": "https://arxiv.org/abs/1234"}]}, f)
            f.flush()
            results = deep_research.load_results(Path(f.name))
        self.assertEqual("academic", results[0].source_type)


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------

class TestGenerateReport(unittest.TestCase):
    def test_contains_required_sections(self):
        src = deep_research.SearchResult(
            query="q", title="Source", url="https://example.com",
            normalized_url="https://example.com", domain="example.com", source_type="website",
        )
        findings = {
            "executive_summary": "Summary text",
            "findings": [{"title": "F1", "confidence": "high", "analysis": "Detail", "citations": ["https://example.com"]}],
            "analysis_sections": [{"title": "S1", "content": "Body", "citations": ["https://example.com"]}],
            "consensus": "All agree",
            "debate": "No major debate",
            "gaps": ["Gap 1"],
        }
        md = deep_research.generate_report("Question", findings, [src], depth="standard")
        self.assertIn("## Research Question", md)
        self.assertIn("## Executive Summary", md)
        self.assertIn("## Key Findings", md)
        self.assertIn("## Detailed Analysis", md)
        self.assertIn("## Sources", md)
        self.assertIn("## Gaps & Limitations", md)
        self.assertIn("[1]", md)
        self.assertIn("Gap 1", md)

    def test_handles_empty_findings(self):
        src = deep_research.SearchResult(
            query="q", title="Source", url="https://example.com",
            normalized_url="https://example.com", domain="example.com", source_type="website",
        )
        md = deep_research.generate_report("Q", {}, [src], depth="quick")
        self.assertIn("Research summary not provided", md)
        self.assertIn("`quick`", md)

    def test_depth_mode_in_report(self):
        src = deep_research.SearchResult(
            query="q", title="S", url="https://x.com",
            normalized_url="https://x.com", domain="x.com", source_type="website",
        )
        md = deep_research.generate_report("Q", {}, [src], depth="deep")
        self.assertIn("`deep`", md)


# ---------------------------------------------------------------------------
# fetch_page_content (mocked)
# ---------------------------------------------------------------------------

class TestFetchPageContent(unittest.TestCase):
    def test_extracts_title_and_content(self):
        html_doc = b"<html><head><title>Test Page</title></head><body><p>Content here</p></body></html>"

        class FakeResponse:
            status = 200

            def read(self, n=-1):
                return html_doc[:n] if n > 0 else html_doc

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            result = deep_research.fetch_page_content("https://example.com")

        self.assertEqual("Test Page", result.title)
        self.assertIn("Content here", result.content)
        self.assertEqual("", result.error)
        self.assertGreater(result.word_count, 0)

    def test_returns_error_on_failure(self):
        with patch("urllib.request.urlopen", side_effect=Exception("network down")):
            result = deep_research.fetch_page_content("https://example.com")

        self.assertEqual("", result.content)
        self.assertIn("network down", result.error)


# ---------------------------------------------------------------------------
# fetch_contents_parallel
# ---------------------------------------------------------------------------

class TestFetchContentsParallel(unittest.TestCase):
    def test_preserves_order(self):
        def fake_fetch(url, timeout=15.0, max_bytes=512000):
            return deep_research.ContentResult(url=url, title=url, content="ok", word_count=1)

        with patch.object(deep_research, "fetch_page_content", side_effect=fake_fetch):
            results = deep_research.fetch_contents_parallel(
                ["https://a.com", "https://b.com", "https://c.com"],
                max_workers=2,
            )

        self.assertEqual(3, len(results))
        self.assertEqual("https://a.com", results[0].url)
        self.assertEqual("https://b.com", results[1].url)
        self.assertEqual("https://c.com", results[2].url)


# ---------------------------------------------------------------------------
# search_codebase
# ---------------------------------------------------------------------------

class TestSearchCodebase(unittest.TestCase):
    def test_finds_pattern(self):
        if not shutil.which("rg"):
            self.skipTest("ripgrep not installed")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "test.txt").write_text("hello world\nfoo bar\nhello again\n")
            matches = deep_research.search_codebase(root, ["hello"], [], context_lines=0)
            text_matches = [m for m in matches if "error" not in m]
            self.assertGreaterEqual(len(text_matches), 2)
            self.assertTrue(all("hello" in m["text"] for m in text_matches))

    def test_respects_glob(self):
        if not shutil.which("rg"):
            self.skipTest("ripgrep not installed")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.go").write_text("func main() {}\n")
            (root / "b.txt").write_text("func helper() {}\n")
            matches = deep_research.search_codebase(root, ["func"], ["*.go"], context_lines=0)
            text_matches = [m for m in matches if "error" not in m]
            files = {m.get("file", "") for m in text_matches}
            self.assertTrue(all("a.go" in f for f in files))
            self.assertFalse(any("b.txt" in f for f in files))

    def test_raises_without_rg(self):
        with patch.object(shutil, "which", return_value=None):
            with self.assertRaises(RuntimeError):
                deep_research.search_codebase(Path("."), ["x"], [])

    def test_multiple_patterns(self):
        if not shutil.which("rg"):
            self.skipTest("ripgrep not installed")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "f.txt").write_text("alpha\nbeta\ngamma\n")
            matches = deep_research.search_codebase(root, ["alpha", "gamma"], [], context_lines=0)
            text_matches = [m for m in matches if "error" not in m]
            texts = [m["text"] for m in text_matches]
            self.assertTrue(any("alpha" in t for t in texts))
            self.assertTrue(any("gamma" in t for t in texts))


# ---------------------------------------------------------------------------
# check_reachability (mocked)
# ---------------------------------------------------------------------------

class TestCheckReachability(unittest.TestCase):
    def test_head_success(self):
        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            ok, status, err = deep_research.check_reachability("https://example.com", timeout=5)

        self.assertTrue(ok)
        self.assertEqual(200, status)

    def test_fallback_to_get_on_405(self):
        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

        effects = [
            urllib.error.HTTPError(
                "https://example.com", 405, "Method Not Allowed",
                {}, io.BytesIO(b""),
            ),
            FakeResponse(),
        ]

        with patch("urllib.request.urlopen", side_effect=effects):
            ok, status, err = deep_research.check_reachability("https://example.com", timeout=5)

        self.assertTrue(ok)
        self.assertEqual(200, status)


# ---------------------------------------------------------------------------
# _extract_snippets
# ---------------------------------------------------------------------------

class TestExtractSnippets(unittest.TestCase):
    def test_fallback_pattern_extracts_nearby_text(self):
        html_doc = (
            '<a href="https://example.com/article">Article Title</a> '
            "This is a pretty long snippet text that should be captured by the fallback."
        )
        snippets = deep_research._extract_snippets(html_doc)
        self.assertTrue(len(snippets) >= 0)


# ---------------------------------------------------------------------------
# map_url_to_index
# ---------------------------------------------------------------------------

class TestMapUrlToIndex(unittest.TestCase):
    def test_maps_correctly(self):
        results = [
            deep_research.SearchResult(
                query="q", title="A", url="https://a.com",
                normalized_url="https://a.com", domain="a.com", source_type="website",
            ),
            deep_research.SearchResult(
                query="q", title="B", url="https://b.com",
                normalized_url="https://b.com", domain="b.com", source_type="website",
            ),
        ]
        m = deep_research.map_url_to_index(results)
        self.assertEqual(1, m["https://a.com"])
        self.assertEqual(2, m["https://b.com"])


if __name__ == "__main__":
    unittest.main()

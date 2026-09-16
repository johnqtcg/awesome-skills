"""Behavioral tests: validate the k6 scripts in references with the real k6.

The reference scripts are this skill's most-copied artifacts. A manual
validation pass found the SharedArray parameterized-data pattern shipping
without ``import http from 'k6/http'`` — init passed, copy-paste exploded at
runtime with a ReferenceError. Three layers here:

1. Static import-completeness (always runs): every complete script that uses
   a k6 module's API must import that module. Catches the bug class that
   ``k6 inspect`` cannot (undefined globals are runtime errors in JS).
2. ``k6 inspect`` (skipped when k6 is not installed): parses each complete
   local script and executes its init context against generated fixtures.
   Scripts importing remote jslib modules are excluded (network-dependent).
3. A real ``k6 run`` against a local HTTP stub (skipped when k6 is not
   installed): actually calls ``default()``, which neither layer above does.
   Undefined variables reached only inside the handler (the §7 Custom
   Metrics example shipped a dangling ``payload`` reference this way) and
   metric-wiring bugs are invisible to static checks and to ``k6 inspect``.
"""

import http.server
import os
import json
import re
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
K6_PATTERNS = SKILL_DIR / "references" / "k6-patterns.md"

# k6 API surface → module that must be imported when the API is used.
MODULE_USAGE = {
    "k6/http": re.compile(r"\bhttp\.\w+\("),
    "k6/data": re.compile(r"\bSharedArray\b"),
    "k6/metrics": re.compile(r"\bnew (Trend|Counter|Gauge|Rate)\("),
    "k6": re.compile(r"\b(sleep|check)\("),
}

OPEN_RE = re.compile(r"open\('([^']+)'\)")


def complete_scripts() -> list[tuple[int, str]]:
    """(index, source) for every fenced js block that is a complete script."""
    text = K6_PATTERNS.read_text(encoding="utf-8")
    blocks = re.findall(r"```(?:javascript|js)\n(.*?)```", text, re.DOTALL)
    return [(i, b) for i, b in enumerate(blocks)
            if "export default" in b and "import" in b]


class ImportCompletenessTests(unittest.TestCase):
    def test_complete_scripts_found(self) -> None:
        self.assertGreaterEqual(len(complete_scripts()), 5)

    def test_every_used_module_is_imported(self) -> None:
        violations = []
        for idx, src in complete_scripts():
            for module, usage in MODULE_USAGE.items():
                if usage.search(src) and f"'{module}'" not in src:
                    api = usage.search(src).group(0)
                    violations.append(
                        f"block #{idx}: uses {api!r} without importing '{module}'")
        self.assertEqual([], violations,
                         "copy-paste of these scripts raises ReferenceError:\n  "
                         + "\n  ".join(violations))




# The runtime layer disappears silently when a sandbox refuses a loopback
# bind(): setUp skipped, suite still green, and the whole `k6 run` layer that
# the docstrings above advertise never executes. Two mitigations, because a
# bare skip is indistinguishable from a pass in a summary line:
#   * LOADTEST_REQUIRE_RUNTIME=1 turns the skip into a failure (use in CI that
#     must actually exercise the runtime layer);
#   * scripts/run_regression.sh greps for these skips and downgrades its final
#     success line, so a human reading the output cannot miss it.
def bind_stub_server(test, handler):
    """Bind a loopback stub server, or skip/fail loudly — never silently."""
    try:
        return http.server.HTTPServer(("127.0.0.1", 0), handler)
    except OSError as exc:          # PermissionError is a subclass
        msg = (f"sandbox denies binding a local listen socket ({exc}) — the "
               "real k6-run layer did NOT execute")
        if os.environ.get("LOADTEST_REQUIRE_RUNTIME") == "1":
            test.fail(msg + " (LOADTEST_REQUIRE_RUNTIME=1)")
        test.skipTest(msg)

# k6 EXITS 0 on iteration-level JavaScript errors when no threshold is
# breached. Verified on k6 v1.3.0: a script whose default() raises a
# ReferenceError three times still returns exit status 0, with the error
# visible only on stderr. So `assertEqual(0, returncode)` is fail-open for
# precisely the bug class the real-run layer exists to catch. Every real run
# must additionally assert the output is error-free AND that the expected
# number of iterations actually completed.
K6_RUNTIME_ERROR_RE = re.compile(
    r"(ReferenceError|TypeError|SyntaxError|RangeError|GoError|level=error)")


def assert_k6_run_clean(test, proc, expected_iterations, summary_metrics, ctx):
    """Exit code, error-free output, and a real iteration count — all three.

    Dropping any one of them reopens the hole: exit code alone misses runtime
    errors, error-text alone misses a script that silently ran zero
    iterations, and the count alone misses an error in a later statement.
    """
    combined = (proc.stdout or "") + (proc.stderr or "")
    test.assertEqual(
        0, proc.returncode,
        f"{ctx}: k6 run exited non-zero\nstdout:\n{proc.stdout[-2000:]}\n"
        f"stderr:\n{proc.stderr[-2000:]}")
    hit = K6_RUNTIME_ERROR_RE.search(combined)
    test.assertIsNone(
        hit,
        f"{ctx}: k6 reported a runtime error while still exiting 0 "
        f"({hit.group(0) if hit else ''}) — this is the bug class static "
        f"analysis and k6 inspect cannot see:\n{combined[-2000:]}")
    actual = (summary_metrics.get("iterations") or {}).get("count")
    test.assertEqual(
        expected_iterations, actual,
        f"{ctx}: expected {expected_iterations} completed iterations, got "
        f"{actual} — default() did not run to completion for every iteration")

@unittest.skipUnless(shutil.which("k6"), "k6 not installed")
class K6InspectTests(unittest.TestCase):
    def test_local_scripts_pass_k6_inspect(self) -> None:
        validated = 0
        failures = []
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            for idx, src in complete_scripts():
                if "https://" in src:
                    continue  # remote jslib import — network-dependent, excluded
                script = tmpdir / f"script_{idx}.js"
                script.write_text(src, encoding="utf-8")
                # Generate a fixture for every file the init context opens.
                for rel in OPEN_RE.findall(src):
                    fixture = tmpdir / rel
                    fixture.parent.mkdir(parents=True, exist_ok=True)
                    fixture.write_text('[{"id": 1, "token": "t"}, {"id": 2, "token": "u"}]',
                                       encoding="utf-8")
                proc = subprocess.run(
                    ["k6", "inspect", script.name],
                    cwd=tmpdir, capture_output=True, text=True, timeout=60,
                )
                if proc.returncode != 0:
                    failures.append(f"block #{idx}:\n{proc.stderr[:400]}")
                validated += 1
        self.assertEqual([], failures, "k6 inspect rejected:\n" + "\n".join(failures))
        self.assertGreaterEqual(validated, 4,
                                "expected at least 4 locally-validatable scripts")


class MemoryHygieneAndCompositionRegressionTests(unittest.TestCase):
    """Static guards for defects a 2026-07-22 review found via manual reading:
    a duplicate Trend in the canonical skeleton, a Gauge fed by __VU (wrong
    twice over — see §7), a CI example contradicting §11.2's csv/json
    guidance, and a "smoke->load->stress->breakpoint" composition missing its
    breakpoint stage. None of these are syntax errors, so k6 inspect and the
    import-completeness check above cannot catch them — only a targeted
    content assertion can."""

    GAUGE_DECL = re.compile(r"(?:const|let|var)\s+(\w+)\s*=\s*new Gauge\(")

    def setUp(self) -> None:
        self.text = K6_PATTERNS.read_text(encoding="utf-8")

    def test_no_gauge_fed_by_vu_id(self) -> None:
        violations = []
        for m in self.GAUGE_DECL.finditer(self.text):
            name = m.group(1)
            if re.search(rf"\b{re.escape(name)}\.add\(\s*__VU\s*\)", self.text):
                violations.append(
                    f"Gauge '{name}' fed by __VU — records a VU id, not a "
                    "concurrency count, and Gauge keeps only latest/min/max; "
                    "use the built-in vus/vus_max metrics instead")
        self.assertEqual([], violations, "\n  ".join(violations))

    def test_canonical_skeleton_has_no_duplicate_trend(self) -> None:
        skeleton_start = self.text.index("Canonical k6 script skeleton")
        skeleton_end = self.text.index("## 2 Scenario Executors")
        skeleton = self.text[skeleton_start:skeleton_end]
        self.assertNotIn(
            "new Trend(", skeleton,
            "the canonical §1 skeleton demonstrates the exact anti-pattern "
            "§11.3 tells readers to delete: a custom Trend duplicating the "
            "built-in http_req_duration")

    def test_ci_example_does_not_use_out_csv_or_json(self) -> None:
        ci_start = self.text.index("### GitHub Actions")
        ci_end = self.text.index("### Run commands")
        ci_block = self.text[ci_start:ci_end]
        self.assertNotIn("--out csv", ci_block)
        self.assertNotIn("--out json", ci_block,
                          "CI example uses --out json, contradicting §11.2's "
                          "csv/json guidance for sustained tests")

    def test_composition_suite_includes_breakpoint_stage(self) -> None:
        comp_start = self.text.index("## 9 Multi-Scenario Composition")
        comp_end = self.text.index("## 10 CI/CD Integration")
        comp_block = self.text[comp_start:comp_end]
        self.assertIn(
            "smoke -> load -> stress -> breakpoint", comp_block,
            "composition intro no longer promises a breakpoint stage")
        self.assertIn(
            "ramping-arrival-rate", comp_block,
            "the promised breakpoint stage is missing its executor — title "
            "says smoke->load->stress->breakpoint but no breakpoint scenario "
            "is defined")


class RateMetricSemanticsTests(unittest.TestCase):
    """A k6 Rate must receive a value every iteration (0 or 1). Feeding it only
    on failure (``check(...) || rate.add(1)``) makes it report 0% or 100%, never
    the true ratio. Static guard so the teaching scripts cannot regress."""

    RATE_DECL = re.compile(r"(?:const|let|var)\s+(\w+)\s*=\s*new Rate\(")

    def test_rate_metrics_recorded_every_iteration(self) -> None:
        violations = []
        for idx, src in complete_scripts():
            for m in self.RATE_DECL.finditer(src):
                name = m.group(1)
                adds = re.findall(rf"\b{re.escape(name)}\.add\(([^)]*)\)", src)
                if adds and all(a.strip() == "1" for a in adds):
                    violations.append(
                        f"block #{idx}: Rate '{name}' only ever adds literal 1 "
                        f"(reports 0%/100%, not the true ratio) — use {name}.add(!ok)")
        self.assertEqual([], violations,
                         "Rate metric recorded only on failure:\n  " + "\n  ".join(violations))


class _StubHandler(http.server.BaseHTTPRequestHandler):
    """Minimal local HTTP target for a real k6 run. Always succeeds so the
    script's own thresholds (order_latency/order_errors) pass on their
    merits rather than on network luck."""

    request_log: list[str] = []

    def _respond(self, status: int) -> None:
        body = json.dumps({"status": "ok", "id": 1, "queue_depth": 3}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        _StubHandler.request_log.append(self.path)
        self._respond(201)

    def do_GET(self) -> None:
        _StubHandler.request_log.append(self.path)
        self._respond(200)

    def log_message(self, fmt, *args) -> None:  # silence default stderr logging
        pass


@unittest.skipUnless(shutil.which("k6"), "k6 not installed")
class RealK6RunTests(unittest.TestCase):
    """Actually executes a reference script's default() with real k6 against
    a local stub server. k6 inspect parses the init context only — it never
    calls default() — so a variable that's only undefined inside the
    handler (like the §7 example's dangling `payload` reference before this
    fix) or a metric wired to the wrong type passes every static check and
    still crashes on first use. This is the runtime layer for exactly that
    gap."""

    def setUp(self) -> None:
        _StubHandler.request_log = []
        self.server = bind_stub_server(self, _StubHandler)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def test_custom_metrics_script_runs_against_real_server(self) -> None:
        text = K6_PATTERNS.read_text(encoding="utf-8")
        start = text.index("## 7 Custom Metrics")
        end = text.index("## 8 Checks")
        block = text[start:end]
        src_match = re.search(r"```javascript\n(.*?)```", block, re.DOTALL)
        src = src_match.group(1).replace(
            "http://api/orders", f"http://127.0.0.1:{self.port}/orders")

        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            script = tmpdir / "script.js"
            script.write_text(src, encoding="utf-8")
            summary = tmpdir / "summary.json"
            proc = subprocess.run(
                ["k6", "run", "--vus", "2", "--iterations", "4",
                 f"--summary-export={summary}", script.name],
                cwd=tmpdir, capture_output=True, text=True, timeout=30,
            )
            summary_data = json.loads(summary.read_text(encoding="utf-8"))
            metrics = summary_data.get("metrics", {})
            assert_k6_run_clean(self, proc, 4, metrics, "§7 Custom Metrics")
            self.assertGreater(
                len(_StubHandler.request_log), 0,
                "no requests reached the stub server — default() did not run "
                "as expected")
            for name in ("order_latency", "orders_created",
                         "order_queue_depth", "order_errors"):
                self.assertIn(
                    name, metrics,
                    f"custom metric '{name}' missing from the real run's "
                    "summary — a metric-wiring bug static checks cannot see")

    def test_handlesummary_script_writes_results_json(self) -> None:
        """The §6 no-remote-dependency handleSummary() example is the skill's
        current recommendation over --summary-export. k6 inspect never calls
        handleSummary(), so a bug in the file it writes (wrong path, bad
        JSON, wrong key) would pass every static check silently."""
        text = K6_PATTERNS.read_text(encoding="utf-8")
        start = text.index("### handleSummary()")
        end = text.index("A fuller human-readable report")
        block = text[start:end]
        src_match = re.search(r"```javascript\n(.*?)```", block, re.DOTALL)
        src = src_match.group(1).replace(
            "http://api.example.com/endpoint", f"http://127.0.0.1:{self.port}/endpoint")

        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            script = tmpdir / "script.js"
            script.write_text(src, encoding="utf-8")
            proc = subprocess.run(
                ["k6", "run", "--vus", "1", "--iterations", "2", script.name],
                cwd=tmpdir, capture_output=True, text=True, timeout=30,
            )
            results = tmpdir / "results.json"
            self.assertTrue(
                results.exists(),
                "handleSummary() ran but results.json was never written to "
                "disk — the file-writing side of its return value")
            data = json.loads(results.read_text(encoding="utf-8"))
            assert_k6_run_clean(self, proc, 2, data.get("metrics", {}),
                                "§6 handleSummary()")
            self.assertIn("metrics", data)
            self.assertIn("http_reqs", data["metrics"])


if __name__ == "__main__":
    unittest.main()

# ------------------------------------------------------------------
# Options-only blocks: the 17-of-23 blind spot
# ------------------------------------------------------------------

OPTIONS_FRAGMENT_RE = re.compile(r"^\s*(scenarios|thresholds)\s*:\s*\{", re.MULTILINE)


def options_fragments() -> list[tuple[int, str]]:
    """(index, source) for fenced blocks that configure k6 but are not whole
    scripts — `scenarios: {...}` / `thresholds: {...}` shown on their own.

    `complete_scripts()` requires both `import` and `export default`, so these
    were parsed by nothing at all: 17 of the 23 JS blocks in this file got no
    machine check of any kind. A mutation renaming `ramping-arrival-rate` to
    the non-existent `ramping-arrival-rates` in two separate options blocks
    went undetected for exactly this reason. Wrapping the fragment in a
    minimal valid script hands it to k6's own options validator.
    """
    text = K6_PATTERNS.read_text(encoding="utf-8")
    blocks = re.findall(r"```(?:javascript|js)\n(.*?)```", text, re.DOTALL)
    out = []
    for i, b in enumerate(blocks):
        if "export default" in b:
            continue        # script-shaped: complete_scripts(), or an elided
                            # illustration that is deliberately not valid JS
        if "..." in b:
            continue        # literal `{...}` elision — cannot be parsed, by design
        if OPTIONS_FRAGMENT_RE.search(b) or b.lstrip().startswith("export const options"):
            out.append((i, b))
    return out


class OptionsFragmentTests(unittest.TestCase):
    def test_options_fragments_found(self) -> None:
        self.assertGreaterEqual(
            len(options_fragments()), 5,
            "options-only fragments no longer detected — this guard is inert")

    @unittest.skipUnless(shutil.which("k6"), "k6 not installed")
    def test_options_fragments_are_valid_k6_config(self) -> None:
        """k6 validates executor names, stage shapes and threshold expressions
        when it builds the options object, so a synthetic wrapper is enough to
        reject a bogus executor without needing the surrounding script."""
        failures = []
        for idx, frag in options_fragments():
            body = frag.strip()
            if not body.startswith("export const options"):
                body = "export const options = {\n" + body.rstrip().rstrip(",") + "\n};"
            src = ("import http from 'k6/http';\n"
                   + body + "\n"
                   + "export default function () { http.get('http://127.0.0.1:1/'); }\n")
            with tempfile.TemporaryDirectory() as tmp:
                script = Path(tmp) / "frag.js"
                script.write_text(src, encoding="utf-8")
                proc = subprocess.run(
                    ["k6", "inspect", script.name],
                    cwd=tmp, capture_output=True, text=True, timeout=30,
                    env=dict(os.environ, K6_NO_USAGE_REPORT="true"),
                )
                if proc.returncode != 0:
                    failures.append(
                        f"block #{idx}: k6 rejected this options fragment:\n"
                        f"{proc.stderr.strip()[-400:]}")
        self.assertEqual([], failures, "\n\n".join(failures))


# ------------------------------------------------------------------
# Remote imports: k6 resolves them at startup, so a dead URL is fatal
# ------------------------------------------------------------------

REMOTE_IMPORT_RE = re.compile(r"from\s+'(https://[^']+)'")


class RemoteImportReachabilityTests(unittest.TestCase):
    """`https://jslib.k6.io/k6-html-report/2.0.0/bundle.js` shipped in this
    file and 404s — jslib does not host an HTML reporter at all. It sat in a
    double blind spot: the block has no `export default`, so the import
    checker skipped it, and it has remote imports, so `k6 inspect` skipped it
    as network-dependent. Two individually reasonable exclusions stacked to
    zero coverage.
    """

    def test_every_remote_import_resolves(self) -> None:
        import urllib.error
        import urllib.request

        urls = sorted(set(REMOTE_IMPORT_RE.findall(
            K6_PATTERNS.read_text(encoding="utf-8"))))
        if not urls:
            self.skipTest("no remote imports in the references")
        dead = []
        for url in urls:
            try:
                req = urllib.request.Request(url, method="HEAD")
                with urllib.request.urlopen(req, timeout=15) as resp:
                    if resp.status >= 400:
                        dead.append(f"{url} -> HTTP {resp.status}")
            except urllib.error.HTTPError as exc:
                dead.append(f"{url} -> HTTP {exc.code}")
            except Exception as exc:        # offline / proxied / DNS-blocked
                self.skipTest(f"network unavailable for {url}: {exc}")
        self.assertEqual(
            [], dead,
            "k6 resolves remote imports at startup, so these are hard "
            "failures before the test begins:\n  " + "\n  ".join(dead))

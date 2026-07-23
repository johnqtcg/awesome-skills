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
        try:
            self.server = http.server.HTTPServer(("127.0.0.1", 0), _StubHandler)
        except PermissionError:
            # Some sandboxes deny binding even a loopback listen socket.
            # That's an environment restriction, not a test failure — skip
            # rather than reporting a false red.
            self.skipTest("sandbox denies binding a local listen socket")
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
            self.assertEqual(
                0, proc.returncode,
                "k6 run failed executing default() for real — this is exactly "
                "the class of bug static analysis and k6 inspect cannot see:\n"
                f"stdout:\n{proc.stdout[-2000:]}\nstderr:\n{proc.stderr[-2000:]}")
            self.assertGreater(
                len(_StubHandler.request_log), 0,
                "no requests reached the stub server — default() did not run "
                "as expected")
            summary_data = json.loads(summary.read_text(encoding="utf-8"))
            metrics = summary_data.get("metrics", {})
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
            self.assertEqual(
                0, proc.returncode,
                "k6 run failed executing the handleSummary() script for "
                f"real:\nstdout:\n{proc.stdout[-2000:]}\nstderr:\n{proc.stderr[-2000:]}")
            results = tmpdir / "results.json"
            self.assertTrue(
                results.exists(),
                "handleSummary() ran but results.json was never written to "
                "disk — the file-writing side of its return value")
            data = json.loads(results.read_text(encoding="utf-8"))
            self.assertIn("metrics", data)
            self.assertIn("http_reqs", data["metrics"])


if __name__ == "__main__":
    unittest.main()
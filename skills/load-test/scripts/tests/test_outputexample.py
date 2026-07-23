"""Regression tests for outputexample/load-test/ — the skill's real Write-mode
script and Analyze-mode report, published as an example of its own output.

Every prior review round found a defect in these two files that no test
caught: an impossible throughput target, a 10x error-threshold mismatch, a
wrong technical claim in a comment, an unearned Hygiene score. None of that
was a syntax error — k6 inspect alone would have passed all of them. This
file closes that gap: it validates the script for real (syntax, k6 inspect,
an actual k6 run) and cross-checks the two files against each other so their
numbers cannot drift silently again.
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

REPO_ROOT = Path(__file__).resolve().parents[4]
EXAMPLE_DIR = REPO_ROOT / "outputexample" / "load-test"
SCRIPT = EXAMPLE_DIR / "checkout-load-test.js"
ANALYSIS = EXAMPLE_DIR / "checkout-load-test-analysis.md"


def _script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def _analysis_text() -> str:
    return ANALYSIS.read_text(encoding="utf-8")


class FilesExistTests(unittest.TestCase):
    def test_example_files_present(self) -> None:
        self.assertTrue(SCRIPT.exists(), f"missing {SCRIPT}")
        self.assertTrue(ANALYSIS.exists(), f"missing {ANALYSIS}")


@unittest.skipUnless(shutil.which("node"), "node not installed")
class ScriptSyntaxTests(unittest.TestCase):
    def test_node_check_passes(self) -> None:
        proc = subprocess.run(["node", "--check", str(SCRIPT)],
                               capture_output=True, text=True, timeout=15)
        self.assertEqual(0, proc.returncode, proc.stderr)


@unittest.skipUnless(shutil.which("k6"), "k6 not installed")
class K6InspectTests(unittest.TestCase):
    def test_k6_inspect_passes(self) -> None:
        proc = subprocess.run(["k6", "inspect", str(SCRIPT)],
                               capture_output=True, text=True, timeout=30)
        self.assertEqual(0, proc.returncode, proc.stderr)


def _k6_duration_to_seconds(s: str) -> float:
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s)?", s)
    if m is None or not any(m.groups()):
        raise ValueError(f"unparseable k6 duration: {s!r}")
    h, minutes, sec = m.groups()
    return int(h or 0) * 3600 + int(minutes or 0) * 60 + float(sec or 0)


@unittest.skipUnless(shutil.which("k6"), "k6 not installed")
class K6ExecutionRequirementsTests(unittest.TestCase):
    """Every mistake in an earlier revision of this file (summed VU pools
    across non-overlapping scenarios, an 8x-undercounted Trend list, a
    missing 30s default gracefulStop pushing totalDuration from 4m30s to
    5m) came from reasoning about the config text instead of asking k6
    itself. `k6 inspect --execution-requirements` is the ground truth for
    maxVUs and totalDuration — these tests parse both the tool's real
    output and the analysis doc's claims, and fail if they disagree, so
    neither can drift from reality (or from each other) silently again."""

    def setUp(self) -> None:
        proc = subprocess.run(
            ["k6", "inspect", "--execution-requirements", str(SCRIPT)],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.requirements = json.loads(proc.stdout)

    def test_max_vus_matches_analysis_doc(self) -> None:
        real_max_vus = self.requirements["maxVUs"]
        analysis = _analysis_text()
        m = re.search(r"maxVUs peak[^=]*=\s*(\d+)", analysis)
        self.assertIsNotNone(
            m, "analysis doc doesn't state a maxVUs-peak figure to check")
        doc_max_vus = int(m.group(1))
        self.assertEqual(
            real_max_vus, doc_max_vus,
            f"k6 itself reports maxVUs={real_max_vus} (non-overlapping "
            f"scenarios reuse VU capacity), but the doc claims {doc_max_vus} "
            "— don't sum per-scenario pools by hand, trust the tool")

    def test_total_duration_matches_analysis_doc(self) -> None:
        real_seconds = _k6_duration_to_seconds(self.requirements["totalDuration"])
        analysis = _analysis_text()
        m = re.search(r"(\d+(?:\.\d+)?)-minute run", analysis)
        self.assertIsNotNone(
            m, "analysis doc doesn't state an N-minute run duration to check")
        doc_seconds = float(m.group(1)) * 60
        self.assertEqual(
            real_seconds, doc_seconds,
            f"k6 reports totalDuration={self.requirements['totalDuration']} "
            f"({real_seconds}s), but the doc claims {m.group(1)} minutes "
            f"({doc_seconds}s) — check every scenario's gracefulStop; a "
            "missing one defaults to +30s")


class _StubHandler(http.server.BaseHTTPRequestHandler):
    request_log: list[str] = []

    def _respond(self, status: int) -> None:
        body = json.dumps({"orderId": "o-1", "queue_depth": 1}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        _StubHandler.request_log.append(self.path)
        self._respond(201)

    def log_message(self, fmt, *args) -> None:  # silence default stderr logging
        pass


@unittest.skipUnless(shutil.which("k6"), "k6 not installed")
class RealRunTests(unittest.TestCase):
    """Executes the published script's default()/handleSummary() for real.
    The script's own scenarios run ~4.5 minutes, too slow for a test suite,
    and CLI --vus/--duration overrides are ignored once `scenarios` is set
    — so this runs a copy with every duration shortened but the same four
    executors (constant-vus, ramping-arrival-rate, constant-arrival-rate,
    ramping-arrival-rate), against a local stub instead of the real host."""

    def setUp(self) -> None:
        _StubHandler.request_log = []
        try:
            # Threading, not plain HTTPServer: the compressed run below still
            # targets 2000 req/s briefly, and a single-threaded stub would
            # bottleneck and risk a spurious dropped_iterations threshold
            # failure that has nothing to do with the script under test.
            self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
        except PermissionError:
            self.skipTest("sandbox denies binding a local listen socket")
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def test_compressed_schedule_runs_and_writes_results(self) -> None:
        # This proves default()/handleSummary() execute without a runtime
        # error (undefined var, bad metric wiring) — the exact gap that let
        # a dangling `payload` reference ship in an earlier revision. It
        # does NOT validate the SLO thresholds pass at 2000 RPS: a local
        # Python stub can't sustain that concurrency, and trying to (an
        # earlier version of this test did) produced threshold failures
        # from the stub being overloaded, not from the script. So: shrink
        # every rate/VU number so the run is trivially light, and strip
        # thresholds entirely — pass/fail here is exit-code-from-a-runtime-
        # error, not exit-code-from-a-threshold-breach.
        src = _script_text()
        src = src.replace("https://checkout.example.com",
                           f"http://127.0.0.1:{self.port}")
        for long, short in [("'30s'", "'1s'"), ("'3m'", "'2s'"),
                            ("'1m'", "'2s'"), ("'4m'", "'4s'")]:
            src = src.replace(long, short)
        for long, short in [("rate: 2000,", "rate: 20,"),
                            ("startRate: 200,", "startRate: 5,"),
                            ("startRate: 2000,", "startRate: 20,"),
                            ("target: 2000 }", "target: 20 }"),
                            ("preAllocatedVUs: 400", "preAllocatedVUs: 20"),
                            ("maxVUs: 800", "maxVUs: 40"),
                            ("vus: 20,", "vus: 5,")]:
            src = src.replace(long, short)
        thresholds_start = src.index("  thresholds: {")
        options_end = src.index("};", thresholds_start) + len("};")
        src = src[:thresholds_start] + "  thresholds: {},\n};" + src[options_end:]

        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            testdata = tmpdir / "testdata"
            testdata.mkdir()
            (testdata / "carts.json").write_text(
                (EXAMPLE_DIR / "testdata" / "carts.json").read_text(encoding="utf-8"),
                encoding="utf-8")
            script = tmpdir / "script.js"
            script.write_text(src, encoding="utf-8")
            proc = subprocess.run(
                ["k6", "run", script.name],
                cwd=tmpdir, capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(
                0, proc.returncode,
                f"real run of the published script failed:\nstdout:\n"
                f"{proc.stdout[-2000:]}\nstderr:\n{proc.stderr[-2000:]}")
            self.assertGreater(len(_StubHandler.request_log), 0,
                                "no requests reached the stub — default() didn't run")
            results = tmpdir / "results.json"
            self.assertTrue(results.exists(), "handleSummary() never wrote results.json")
            data = json.loads(results.read_text(encoding="utf-8"))
            self.assertIn("http_reqs", data.get("metrics", {}))


class CrossFileConsistencyTests(unittest.TestCase):
    """The script and its paired analysis.md each state the same SLO/config
    numbers independently. A human has to re-read both to notice drift; this
    parses both and asserts they agree — the exact class of bug (wrong
    threshold, wrong duration, wrong claim) every prior round found by hand."""

    def setUp(self) -> None:
        self.script = _script_text()
        self.analysis = _analysis_text()

    def test_error_rate_threshold_matches_declared_slo(self) -> None:
        # SLO comment declares "error rate<0.1%"; the two rate thresholds
        # (http_req_failed, errors) must both encode 0.001, not 0.01.
        thresholds = re.findall(r"'rate<([\d.]+)'\]", self.script)
        self.assertTrue(thresholds, "no rate<N thresholds found in script")
        for t in thresholds:
            self.assertAlmostEqual(
                float(t), 0.001, places=6,
                msg=f"rate threshold {t} doesn't match the declared <0.1% SLO")
        self.assertIn("error rate<0.1%", self.script)
        self.assertIn("error rate<0.1%", self.analysis)

    def test_throughput_target_matches_between_script_and_analysis(self) -> None:
        script_rate = re.search(r"rate:\s*(\d+)", self.script)
        self.assertIsNotNone(script_rate, "no arrival-rate `rate:` found in script")
        target = script_rate.group(1)
        self.assertIn(f"{int(target):,} RPS", self.analysis,
                       "script's arrival rate and analysis's stated RPS have diverged")

    def test_no_ramping_vus_executor(self) -> None:
        # This was the actual bug: ramping-vus (closed model) can't guarantee
        # an exact-RPS SLO. Regression guard against reintroducing it as an
        # executor — the word still appears in comments explaining why not.
        self.assertNotIn("executor: 'ramping-vus'", self.script)

    def test_dropped_iterations_threshold_present(self) -> None:
        self.assertIn("dropped_iterations", self.script)

    def test_all_scenarios_have_cooldown_and_ramp(self) -> None:
        for phase in ("warmup", "ramp", "load_test", "cooldown"):
            self.assertIn(phase, self.script, f"scenario '{phase}' missing")

    def test_scorecard_arithmetic(self) -> None:
        m = re.search(
            r"\*\*Scorecard\*\*:\s*(\d+)/13\s*—\s*Critical\s*(\d+)/3,\s*"
            r"Standard\s*(\d+)/5,\s*Hygiene\s*(\d+)/5", self.analysis)
        self.assertIsNotNone(m, "Scorecard line not found or format changed")
        total, critical, standard, hygiene = (int(g) for g in m.groups())
        self.assertEqual(total, critical + standard + hygiene,
                          "Scorecard total doesn't equal the sum of its tiers")
        self.assertLessEqual(critical, 3)
        self.assertLessEqual(standard, 5)
        self.assertLessEqual(hygiene, 5)

    def test_hygiene_score_reflects_discard_response_bodies_gap(self) -> None:
        # Scorecard item 13 bundles VU sizing + no extra diagnostic Trends +
        # no --out csv/json + discardResponseBodies. This script skips the
        # last one (justified — the check needs r.json() — but still
        # skipped). A correct memory-budget number doesn't earn back that
        # sub-requirement: Hygiene can't claim full credit for item 13 while
        # discardResponseBodies is absent, regardless of how safe the
        # numbers turn out to be. This is the exact "unearned Hygiene
        # score" failure mode from an earlier revision — pinned so it can't
        # silently return under a different justification.
        self.assertNotIn("discardResponseBodies: true", self.script)
        m = re.search(r"Hygiene\s*(\d+)/5", self.analysis)
        self.assertIsNotNone(m, "Hygiene score not found in Scorecard line")
        hygiene = int(m.group(1))
        self.assertLessEqual(
            hygiene, 3,
            f"Hygiene scored {hygiene}/5, but discardResponseBodies is not "
            "set — item 13 cannot be counted as fully passing (max 3/5 "
            "alongside the #10 baseline-comparison gap) without either "
            "setting it or explicitly re-justifying the exception in a way "
            "SKILL.md §8 item 13 actually allows")
        self.assertIn("discardResponseBodies", self.analysis)
        self.assertIn("r.json", self.analysis)

    def test_percentile_verdicts_match_their_thresholds(self) -> None:
        rows = re.findall(
            r"\|\s*(p[\d.]+|max)\s*\|\s*([\d.]+)(ms|s)\s*\|\s*(<[\d.]+ms|—)\s*\|\s*"
            r"(PASS|\*\*FAIL\*\*|—)\s*\|", self.analysis)
        self.assertGreaterEqual(len(rows), 4, "percentile table not found or format changed")
        for name, value, unit, slo, verdict in rows:
            value_ms = float(value) * (1000 if unit == "s" else 1)
            if slo == "—":
                self.assertEqual(verdict, "—", f"{name}: has no SLO but a verdict was given")
                continue
            threshold_ms = float(re.match(r"<([\d.]+)ms", slo).group(1))
            should_pass = value_ms < threshold_ms
            stated_pass = verdict == "PASS"
            self.assertEqual(
                should_pass, stated_pass,
                f"{name}: {value_ms}ms vs {slo} implies "
                f"{'PASS' if should_pass else 'FAIL'}, but doc says {verdict}")


if __name__ == "__main__":
    unittest.main()
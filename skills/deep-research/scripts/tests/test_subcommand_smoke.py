"""End-to-end smoke tests: every subcommand executed for real, offline.

The prior 60+ unit tests covered pure functions only; the regression's sole
script-level check was `--help` — which was the one path that survived the
output→outputexample global-replace accident. Every output-writing
subcommand crashed with `AttributeError: 'Namespace' object has no attribute
'output'` at the moment of persisting results (confirmed in a real session
on 2026-05-07, where the script had to be abandoned mid-research). These
tests execute each subcommand through main() so that parser↔handler drift
can never ship green again. All tests are network-free.
"""

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "deep_research.py"
SKILL_MD = Path(__file__).resolve().parents[2] / "SKILL.md"

spec = importlib.util.spec_from_file_location("deep_research_smoke", SCRIPT)
deep_research = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = deep_research
spec.loader.exec_module(deep_research)


RESULTS_FIXTURE = {
    "results": [
        {
            "query": "go connection pool",
            "title": "Managing connections — pkg.go.dev",
            "url": "https://go.dev/doc/database/manage-connections",
            "snippet": "SetMaxOpenConns sets the maximum number of open connections.",
            "date": "2025-01-01",
        },
        {
            "query": "go connection pool",
            "title": "database/sql pooling deep dive",
            "url": "https://example.com/blog/sql-pooling",
            "snippet": "How the pool grows and shrinks.",
            "date": "2025-03-02",
        },
    ]
}


def run_cli(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *argv],
        capture_output=True,
        text=True,
        timeout=60,
    )


class SubcommandSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.results = self.tmp / "results.json"
        self.results.write_text(json.dumps(RESULTS_FIXTURE), encoding="utf-8")

    @unittest.skipUnless(shutil.which("rg"),
                         "ripgrep not installed — the subcommand itself "
                         "fails fast with a clear message (verified below)")
    def test_search_codebase_writes_output(self) -> None:
        (self.tmp / "src").mkdir()
        (self.tmp / "src" / "pool.go").write_text(
            "package pool\n\n// SetMaxOpenConns caps the pool.\n", encoding="utf-8")
        out = self.tmp / "code.json"
        proc = run_cli("search-codebase", "--pattern", "SetMaxOpenConns",
                       "--root", str(self.tmp / "src"), "--output", str(out))
        self.assertEqual(0, proc.returncode, proc.stderr)
        payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertGreaterEqual(payload["total_matches"], 1)
        self.assertIn("output=", proc.stdout)

    def test_search_codebase_without_rg_fails_fast_with_message(self) -> None:
        """Without ripgrep the subcommand must exit 2 with a clear message,
        not crash — this is the exact behavior a CI runner without rg sees."""
        empty_path_dir = self.tmp / "empty-path"
        empty_path_dir.mkdir()
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "search-codebase",
             "--pattern", "x", "--root", str(self.tmp),
             "--output", str(self.tmp / "o.json")],
            capture_output=True, text=True, timeout=60,
            env={"PATH": str(empty_path_dir)},
        )
        self.assertEqual(2, proc.returncode)
        self.assertIn("rg", proc.stderr)

    def test_validate_writes_output(self) -> None:
        out = self.tmp / "validate.json"
        proc = run_cli("validate", "--results", str(self.results), "--output", str(out))
        self.assertEqual(0, proc.returncode, proc.stderr)
        payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(2, payload["checked_count"])

    def test_report_writes_markdown(self) -> None:
        out = self.tmp / "report.md"
        proc = run_cli("report", "--question", "How does Go pool DB connections?",
                       "--results", str(self.results), "--output", str(out))
        self.assertEqual(0, proc.returncode, proc.stderr)
        text = out.read_text(encoding="utf-8")
        self.assertIn("How does Go pool DB connections?", text)
        self.assertIn("go.dev", text)

    def test_fetch_content_unreachable_url_still_writes_output(self) -> None:
        out = self.tmp / "content.json"
        # 127.0.0.1:9 refuses instantly — exercises the full pipeline offline.
        # All-URLs-failed returns rc=2 by design, but the output JSON with the
        # per-URL error records must already be on disk (write before verdict).
        proc = run_cli("fetch-content", "--url", "http://127.0.0.1:9/x",
                       "--timeout", "1", "--workers", "1", "--output", str(out))
        self.assertEqual(2, proc.returncode, proc.stderr)
        payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(1, payload["count"])
        self.assertTrue(payload["items"][0]["error"], "error must be recorded for the failed URL")
        self.assertIn("output=", proc.stdout)


class ParserHandlerDriftGuards(unittest.TestCase):
    """Lock out the output→outputexample class: every output-writing
    subcommand must expose `args.output`, matching what handlers read."""

    CASES = {
        "retrieve": ["retrieve", "--query", "q", "--output", "/tmp/x.json"],
        "validate": ["validate", "--results", "r.json", "--output", "/tmp/x.json"],
        "report": ["report", "--question", "q", "--results", "r.json", "--output", "/tmp/x.md"],
        "fetch-content": ["fetch-content", "--url", "http://e.com", "--output", "/tmp/x.json"],
        "search-codebase": ["search-codebase", "--pattern", "p", "--output", "/tmp/x.json"],
    }

    def test_every_subcommand_accepts_output_flag(self) -> None:
        parser = deep_research.build_parser()
        for name, argv in self.CASES.items():
            args = parser.parse_args(argv)
            self.assertTrue(hasattr(args, "output"),
                            f"{name}: parser must define --output (dest=output)")

    def test_corruption_word_absent_from_skill_and_script(self) -> None:
        for path in (SCRIPT, SKILL_MD):
            self.assertNotIn("outputexample", path.read_text(encoding="utf-8"),
                             f"{path.name}: global-replace artifact present")

    def test_skill_documented_flags_exist_in_parser(self) -> None:
        """SKILL.md's Subcommands Reference must not document flags the
        parser does not accept (the doc↔script bridge)."""
        parser = deep_research.build_parser()
        sub_actions = next(a for a in parser._actions
                           if isinstance(a, deep_research.argparse._SubParsersAction))
        known_flags = {}
        for name, sp in sub_actions.choices.items():
            known_flags[name] = {opt for a in sp._actions for opt in a.option_strings}
        doc = SKILL_MD.read_text(encoding="utf-8")
        table = doc.split("## Subcommands Reference")[1].split("##")[0]
        for line in table.splitlines():
            if not line.startswith("| `"):
                continue
            cells = [c.strip().strip("`") for c in line.strip("|").split("|")]
            name = cells[0]
            if name not in known_flags:
                continue
            import re
            for flag in re.findall(r"--[a-z][a-z0-9-]*", cells[2]):
                self.assertIn(flag, known_flags[name],
                              f"SKILL.md documents {flag} for {name!r} but the parser rejects it")


if __name__ == "__main__":
    unittest.main()
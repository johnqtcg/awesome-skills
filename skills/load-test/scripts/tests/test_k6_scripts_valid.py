"""Behavioral tests: validate the k6 scripts in references with the real k6.

The reference scripts are this skill's most-copied artifacts. A manual
validation pass found the SharedArray parameterized-data pattern shipping
without ``import http from 'k6/http'`` — init passed, copy-paste exploded at
runtime with a ReferenceError. Two layers here:

1. Static import-completeness (always runs): every complete script that uses
   a k6 module's API must import that module. Catches the bug class that
   ``k6 inspect`` cannot (undefined globals are runtime errors in JS).
2. ``k6 inspect`` (skipped when k6 is not installed): parses each complete
   local script and executes its init context against generated fixtures.
   Scripts importing remote jslib modules are excluded (network-dependent).
"""

import re
import shutil
import subprocess
import tempfile
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


if __name__ == "__main__":
    unittest.main()
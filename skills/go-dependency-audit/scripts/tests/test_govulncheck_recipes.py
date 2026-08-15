"""Executable tests for the govulncheck recipes in references/.

The tier-classification jq in govulncheck-patterns.md is not decoration — the
skill's whole priority model rests on it. This module extracts that jq program
*from the document* and runs it against fixtures whose expected tiers are known,
so editing the doc's recipe into something wrong fails the build.

Fixture shapes mirror govulncheck v1.1.4's own golden files
(golang.org/x/vuln/internal/scan/testdata): a stream of concatenated JSON
objects, `trace` innermost-first, and one OSV legitimately appearing as several
findings at different tiers.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import textwrap

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
REF = SKILL_DIR / "references" / "govulncheck-patterns.md"
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "govulncheck"

# Hand-written expectations. Deliberately NOT derived from the code under test.
EXPECTED = {
    "mixed_tiers.json": {
        "e1_called": ["GO-2024-0001"],
        "e2_imported": ["GO-2024-0002"],
        "e3_required": ["GO-2024-0003"],
    },
    "clean.json": {"e1_called": [], "e2_imported": [], "e3_required": []},
    "module_scan_only.json": {
        "e1_called": [],
        "e2_imported": [],
        "e3_required": ["GO-2024-0007", "GO-2024-0008"],
    },
}

SCAN_LEVELS = {
    "mixed_tiers.json": "symbol",
    "clean.json": "symbol",
    "module_scan_only.json": "module",
}


def _stream_objects(text: str) -> list[dict]:
    """Parse a stream of concatenated JSON objects, as govulncheck emits."""
    decoder = json.JSONDecoder()
    out, idx = [], 0
    while idx < len(text):
        while idx < len(text) and text[idx].isspace():
            idx += 1
        if idx >= len(text):
            break
        obj, end = decoder.raw_decode(text, idx)
        out.append(obj)
        idx = end
    return out


def classify_tiers(objects: list[dict]) -> dict[str, list[str]]:
    """Reference implementation of the documented tier algorithm."""
    findings = [o["finding"] for o in objects if "finding" in o]
    e1, e2, e3 = set(), set(), set()
    for f in findings:
        head = (f.get("trace") or [{}])[0]
        if head.get("function") is not None:
            e1.add(f["osv"])
        elif head.get("package") is not None:
            e2.add(f["osv"])
        else:
            e3.add(f["osv"])
    e2 -= e1
    e3 -= e1 | e2
    return {"e1_called": sorted(e1), "e2_imported": sorted(e2),
            "e3_required": sorted(e3)}


def extract_jq_program() -> str:
    """Pull the tier-classification jq filter out of the reference document."""
    text = REF.read_text(encoding="utf-8")
    m = re.search(r"jq -s '\n(.*?)\n'\s", text, re.DOTALL)
    assert m, "tier-classification `jq -s '...'` block not found in the reference"
    program = m.group(1)
    assert "e1_called" in program, "extracted the wrong jq block"
    return program


# ── Always-run: the documented algorithm on known fixtures ────────────────

class TestDocumentedAlgorithm:

    @pytest.mark.parametrize("name", sorted(EXPECTED))
    def test_python_reference_matches_expectation(self, name):
        objs = _stream_objects((FIXTURES / name).read_text(encoding="utf-8"))
        assert classify_tiers(objs) == EXPECTED[name]

    def test_same_osv_at_two_tiers_counts_once_at_the_strongest(self):
        """GO-2024-0001 appears module-only AND with a symbol trace."""
        objs = _stream_objects(
            (FIXTURES / "mixed_tiers.json").read_text(encoding="utf-8"))
        raw = [o["finding"]["osv"] for o in objs if "finding" in o]
        assert raw.count("GO-2024-0001") == 2, "fixture lost its duplicate finding"
        tiers = classify_tiers(objs)
        assert tiers["e1_called"] == ["GO-2024-0001"]
        assert "GO-2024-0001" not in tiers["e3_required"], \
            "an E1 finding must not also be counted as E3"

    def test_naive_finding_count_overcounts(self):
        """Proves the dedupe is load-bearing, not decorative."""
        objs = _stream_objects(
            (FIXTURES / "mixed_tiers.json").read_text(encoding="utf-8"))
        naive = len([o for o in objs if "finding" in o])
        tiers = classify_tiers(objs)
        deduped = sum(len(v) for v in tiers.values())
        assert naive > deduped, (
            "fixture no longer exercises the double-counting case the recipe "
            "exists to avoid"
        )

    @pytest.mark.parametrize("name", sorted(SCAN_LEVELS))
    def test_scan_level_is_recoverable_from_the_config_message(self, name):
        objs = _stream_objects((FIXTURES / name).read_text(encoding="utf-8"))
        configs = [o["config"] for o in objs if "config" in o]
        assert configs, f"{name} has no config message; it must come first"
        assert configs[0]["scan_level"] == SCAN_LEVELS[name]

    def test_module_scan_cannot_produce_reachability(self):
        objs = _stream_objects(
            (FIXTURES / "module_scan_only.json").read_text(encoding="utf-8"))
        assert objs[0]["config"]["scan_level"] == "module"
        assert classify_tiers(objs)["e1_called"] == [], (
            "a module-level scan must never yield an E1 tier — an empty E1 here "
            "means 'not measured', not 'not reachable'"
        )


# ── The document's own jq, executed ───────────────────────────────────────

jq_missing = shutil.which("jq") is None


class TestReferenceJqProgram:

    def test_program_is_extractable(self):
        program = extract_jq_program()
        for token in ("e1_called", "e2_imported", "e3_required", "unique"):
            assert token in program, f"extracted jq lost {token!r}"

    def test_program_subtracts_higher_tiers(self):
        program = extract_jq_program()
        assert "- $e1" in program, "E2 must exclude OSVs already counted as E1"
        assert "- $e1 - $e2" in program, "E3 must exclude E1 and E2"

    @pytest.mark.skipif(jq_missing, reason="jq not installed")
    @pytest.mark.parametrize("name", sorted(EXPECTED))
    def test_documented_jq_matches_expectation(self, name):
        program = extract_jq_program()
        proc = subprocess.run(
            ["jq", "-s", program, str(FIXTURES / name)],
            capture_output=True, text=True, timeout=60,
        )
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout) == EXPECTED[name]

    @pytest.mark.skipif(jq_missing, reason="jq not installed")
    def test_dropping_slurp_breaks_the_recipe(self):
        """The '-s' in the doc is load-bearing; prove it by removing it.

        Without slurp, jq evaluates the filter once per object in the stream and
        emits one result per object — which is how a CI gate ends up comparing
        a multi-line string against an integer.
        """
        program = extract_jq_program()
        target = FIXTURES / "mixed_tiers.json"
        with_slurp = subprocess.run(["jq", "-s", program, str(target)],
                                    capture_output=True, text=True, timeout=60)
        without = subprocess.run(["jq", program, str(target)],
                                 capture_output=True, text=True, timeout=60)
        assert with_slurp.returncode == 0
        one_result = with_slurp.stdout.strip().count("e1_called") == 1
        assert one_result, "slurped run should emit exactly one object"
        many_or_error = (
            without.returncode != 0
            or without.stdout.strip().count("e1_called") > 1
        )
        assert many_or_error, (
            "removing -s produced a single clean result, so the doc's emphasis "
            "on slurping would be unfounded — re-verify against real output"
        )


# ── Real scan output ──────────────────────────────────────────────────────

REAL_SCAN = FIXTURES / "real_scan_x_net_v0.15.0.json"

# Captured 2026-08-14 from `govulncheck -format json ./...` (v1.1.4, Go 1.26.1)
# against a module requiring golang.org/x/net v0.15.0 and calling
# http2.ConfigureServer + http.Server.ListenAndServe. Reduced for size: OSV
# bodies other than the three referenced below were dropped, and each finding's
# `trace` was truncated to its innermost frame — the only element the tier
# recipe reads. Tier counts are unchanged from the full 590 KB output.
REAL_SCAN_TIERS = {"e1": 13, "e2": 9, "e3": 19}

# govulncheck's own text summary for that scan, verbatim:
#   "Your code is affected by 13 vulnerabilities from 1 module and the Go
#    standard library. This scan also found 9 vulnerabilities in packages you
#    import and 19 vulnerabilities in modules you require, but your code
#    doesn't appear to call these vulnerabilities."
REAL_SCAN_TEXT_SUMMARY = (13, 9, 19)


class TestAgainstRealScanOutput:
    """The synthetic fixtures fix the shape; this one fixes the reality.

    Hand-written fixtures can encode the same misunderstanding as the code they
    test. These assertions run against output an actual govulncheck produced.
    """

    @pytest.fixture(autouse=True)
    def _objs(self):
        assert REAL_SCAN.exists(), "real-scan fixture missing"
        self.objs = _stream_objects(REAL_SCAN.read_text(encoding="utf-8"))

    def test_tiers_match_the_recorded_counts(self):
        tiers = classify_tiers(self.objs)
        got = {"e1": len(tiers["e1_called"]),
               "e2": len(tiers["e2_imported"]),
               "e3": len(tiers["e3_required"])}
        assert got == REAL_SCAN_TIERS

    def test_tiers_agree_with_govulnchecks_own_summary(self):
        """Independent cross-check: the tool counted these itself."""
        tiers = classify_tiers(self.objs)
        got = (len(tiers["e1_called"]), len(tiers["e2_imported"]),
               len(tiers["e3_required"]))
        assert got == REAL_SCAN_TEXT_SUMMARY, (
            f"recipe says {got}, govulncheck's text summary says "
            f"{REAL_SCAN_TEXT_SUMMARY} — the recipe and the tool disagree"
        )

    def test_no_severity_anywhere_in_real_output(self):
        """The central claim of S6.1, checked on real data, not on a doc."""
        blob = REAL_SCAN.read_text(encoding="utf-8").lower()
        for token in ("cvss", '"severity"', "severity_score"):
            assert token not in blob, f"real govulncheck output contains {token!r}"

    def test_scan_level_was_symbol(self):
        cfg = [o["config"] for o in self.objs if "config" in o]
        assert cfg and cfg[0]["scan_level"] == "symbol"

    def test_anti_example_1_matches_a_real_finding(self):
        """AE-1 quotes GO-2023-2102 / x/net -> v0.17.0. Verify it is real."""
        findings = [o["finding"] for o in self.objs if "finding" in o]
        hit = [f for f in findings if f["osv"] == "GO-2023-2102"]
        assert hit, "GO-2023-2102 absent from the real scan"
        assert hit[0]["fixed_version"] == "v0.17.0", (
            f"AE-1 claims v0.17.0, real output says {hit[0]['fixed_version']}"
        )

    def test_stdlib_findings_are_present(self):
        """A real scan reports stdlib vulns too; the docs must not imply
        module-only coverage."""
        findings = [o["finding"] for o in self.objs if "finding" in o]
        modules = {f["trace"][0].get("module") for f in findings}
        assert "stdlib" in modules or any(
            m and not m.startswith("example.com") and "/" not in (m or "x/")
            for m in modules
        ), f"no stdlib finding in the real scan; modules seen: {sorted(m or '' for m in modules)}"


# ── Live end-to-end (opt-in) ──────────────────────────────────────────────

E2E_ENABLED = os.environ.get("GO_DEP_AUDIT_E2E") == "1"
E2E_SKIP = "set GO_DEP_AUDIT_E2E=1 (needs network, go, govulncheck) to run"

E2E_GO_MOD = """\
module example.com/e2e

go 1.23

require golang.org/x/net v0.15.0
"""

E2E_MAIN = textwrap.dedent("""\
    package main

    import (
    \t"net/http"

    \t"golang.org/x/net/http2"
    )

    func main() {
    \tsrv := &http.Server{Addr: ":8080"}
    \t_ = http2.ConfigureServer(srv, &http2.Server{})
    \t_ = srv.ListenAndServe()
    }
""")


@pytest.mark.skipif(not E2E_ENABLED, reason=E2E_SKIP)
class TestLiveEndToEnd:
    """Runs the documented gate sequence against a real vulnerable module.

    Opt-in because it needs network and a matching toolchain. A skip is a skip —
    the offline assertions above still run, and none of them credit this.
    """

    @pytest.fixture(scope="class")
    def repo(self, tmp_path_factory):
        d = tmp_path_factory.mktemp("e2e")
        (d / "cmd" / "server").mkdir(parents=True)
        (d / "go.mod").write_text(E2E_GO_MOD, encoding="utf-8")
        (d / "cmd" / "server" / "main.go").write_text(E2E_MAIN, encoding="utf-8")
        proc = subprocess.run(["go", "mod", "tidy"], cwd=d, capture_output=True,
                              text=True, timeout=600,
                              env={**os.environ, "GOFLAGS": "-mod=mod"})
        if proc.returncode != 0:
            pytest.fail(
                f"fixture setup failed: `go mod tidy` exited {proc.returncode}. "
                f"This is an environment problem (module download blocked?), "
                f"not a skill defect.\nstderr:\n{proc.stderr[:800]}")
        return d

    def _run(self, repo, *args, timeout=600):
        return subprocess.run(list(args), cwd=repo, capture_output=True,
                              text=True, timeout=timeout)

    def test_readonly_gate_commands_all_succeed(self, repo):
        for args in (("go", "mod", "edit", "-json"),
                     ("go", "list", "-mod=readonly", "-m", "all"),
                     ("go", "mod", "verify"),
                     ("go", "mod", "tidy", "-diff")):
            proc = self._run(repo, *args)
            assert proc.returncode == 0, f"{args} failed: {proc.stderr[:300]}"

    def test_text_mode_exits_3_when_findings_exist(self, repo):
        proc = self._run(repo, "govulncheck", "./...")
        assert proc.returncode == 3, (
            f"expected exit 3, got {proc.returncode}: {proc.stderr[:400]}"
        )
        assert "=== Symbol Results ===" in proc.stdout
        assert "GO-2023-2102" in proc.stdout

    def test_json_mode_exits_0_despite_findings(self, repo):
        proc = self._run(repo, "govulncheck", "-format", "json", "./...")
        assert proc.returncode == 0, (
            "json mode must exit 0 regardless of findings — this is the CI trap "
            "AE-3 documents"
        )
        objs = _stream_objects(proc.stdout)
        assert classify_tiers(objs)["e1_called"], "no reachable findings parsed"

    def test_readonly_probes_do_not_mutate_the_manifest(self, repo):
        before = ((repo / "go.mod").read_bytes(), (repo / "go.sum").read_bytes())
        self._run(repo, "go", "list", "-mod=readonly", "-m", "all")
        self._run(repo, "go", "mod", "verify")
        self._run(repo, "govulncheck", "./...")
        after = ((repo / "go.mod").read_bytes(), (repo / "go.sum").read_bytes())
        assert before == after, "a documented read-only probe modified the manifest"


# ── Multi-module live end-to-end (opt-in) ─────────────────────────────────

MM_ROOT_MOD = """\
module example.com/mm

go 1.23

require golang.org/x/net v0.15.0
"""

MM_ROOT_MAIN = textwrap.dedent("""\
    package main

    import (
    \t"net/http"

    \t"golang.org/x/net/http2"
    )

    func main() {
    \tsrv := &http.Server{Addr: ":8080"}
    \t_ = http2.ConfigureServer(srv, &http2.Server{})
    \t_ = srv.ListenAndServe()
    }
""")

MM_WORKER_MOD = """\
module example.com/mm/worker

go 1.23
"""

MM_WORKER_MAIN = textwrap.dedent("""\
    package main

    func main() { println("worker") }
""")


GO_LICENSES = shutil.which("go-licenses")

MM_SIBLING_MOD = """\
module example.com/mm/sibling

go 1.23

require golang.org/x/net v0.17.0
"""

MM_SIBLING_MAIN = textwrap.dedent("""\
    package main

    import "golang.org/x/net/idna"

    func main() { _, _ = idna.ToASCII("example.com") }
""")

MM_WORK = """\
go 1.23

use (
	./root
	./root/worker
	./sibling
)
"""


@pytest.mark.skipif(not E2E_ENABLED, reason=E2E_SKIP)
class TestLiveMultiModuleEndToEnd:
    """A real three-module repo, driven exactly as references/multi-module.md says.

    This exists because the previous revision documented `go mod tidy -diff -C
    "$dir"` (exit 2) and `go-licenses check "$dir/..."` (usage error) — nobody
    had run the multi-module flow, so nothing caught either. Every command here
    is the literal documented form.

    Shape: a root module with a nested `./worker`, plus a **sibling** `./sibling`
    on a different version of the same dependency, and a real `go.work`.
    """

    @pytest.fixture(scope="class")
    def repo(self, tmp_path_factory):
        """Layout with a genuine sibling, not three nested modules.

            repo/go.work
            repo/root/go.mod            <- main module, x/net v0.15.0 (vulnerable)
            repo/root/worker/go.mod     <- NESTED inside root
            repo/sibling/go.mod         <- SIBLING: not under root's tree,
                                           x/net v0.17.0 (fixed)

        The earlier version put `sibling/` inside the root module's directory
        tree, which by this skill's own definition made it a second nested
        module — so nothing was actually testing sibling behaviour.
        """
        d = tmp_path_factory.mktemp("mm")
        root = d / "root"
        (root / "cmd" / "server").mkdir(parents=True)
        (root / "go.mod").write_text(MM_ROOT_MOD, encoding="utf-8")
        (root / "cmd" / "server" / "main.go").write_text(MM_ROOT_MAIN,
                                                         encoding="utf-8")

        w = root / "worker"
        w.mkdir()
        (w / "go.mod").write_text(MM_WORKER_MOD, encoding="utf-8")
        (w / "main.go").write_text(MM_WORKER_MAIN, encoding="utf-8")

        s = d / "sibling"
        s.mkdir()
        (s / "go.mod").write_text(MM_SIBLING_MOD, encoding="utf-8")
        (s / "main.go").write_text(MM_SIBLING_MAIN, encoding="utf-8")

        env = {**os.environ, "GOFLAGS": "-mod=mod", "GOWORK": "off"}
        for mod in (root, s):
            # Fail here, loudly, rather than letting every downstream assertion
            # fail obscurely. A sandboxed run with no module download produced
            # nine cascading failures whose real cause was this one line.
            proc = subprocess.run(["go", "mod", "tidy"], cwd=mod,
                                  capture_output=True, text=True, timeout=600,
                                  env=env)
            if proc.returncode != 0:
                pytest.fail(
                    f"fixture setup failed: `go mod tidy` in {mod.name} exited "
                    f"{proc.returncode}. This is an environment problem (module "
                    f"download blocked?), not a skill defect.\n"
                    f"stderr:\n{proc.stderr[:800]}")
        (d / "go.work").write_text(MM_WORK, encoding="utf-8")
        return d

    @staticmethod
    def _mods(repo):
        """(name -> directory) for the three modules."""
        return {".": repo / "root",
                "worker": repo / "root" / "worker",
                "sibling": repo / "sibling"}

    def _outside(self, repo, *args, timeout=600, env=None):
        """Run from a directory that is NOT the module — the only way -C proves
        anything. Running `-C dir` while already inside `dir` succeeds for the
        wrong reason."""
        return subprocess.run(list(args), cwd=repo.parent, capture_output=True,
                              text=True, timeout=timeout,
                              env={**os.environ, **(env or {})})

    # ── discovery ────────────────────────────────────────────────────────

    def test_all_three_modules_are_discoverable(self, repo):
        """Assert the exact relative paths — a bare count of 3 passes on any
        three wrong directories."""
        found = sorted(str(p.parent.relative_to(repo))
                       for p in repo.glob("**/go.mod"))
        assert found == ["root", "root/worker", "sibling"], found

    def test_the_sibling_is_not_nested_in_the_root_module(self, repo):
        """The distinction the earlier fixture silently lost."""
        mods = self._mods(repo)
        root, sibling, worker = mods["."], mods["sibling"], mods["worker"]
        assert worker.is_relative_to(root), "worker should be nested in root"
        assert not sibling.is_relative_to(root), (
            "sibling is inside the root module's tree, so it is a second nested "
            "module — the fixture is not testing sibling behaviour"
        )

    def test_nested_module_is_absent_from_the_parent_build_list(self, repo):
        """The documented trap: a nested go.mod is not a parent dependency."""
        proc = self._outside(repo, "go", "-C", str(self._mods(repo)["."]),
                             "list", "-mod=readonly", "-m", "all",
                             env={"GOWORK": "off"})
        assert proc.returncode == 0, proc.stderr
        assert "example.com/mm/worker" not in proc.stdout
        assert "example.com/mm/sibling" not in proc.stdout, (
            "a sibling module appeared in the root's build list"
        )

    # ── -C placement ─────────────────────────────────────────────────────

    @pytest.mark.parametrize("args", [
        ("mod", "edit", "-json"),
        ("list", "-mod=readonly", "-m", "all"),
        ("mod", "verify"),
        ("mod", "graph"),
        ("mod", "tidy", "-diff"),
    ])
    def test_documented_dash_c_form_works_per_module(self, repo, args):
        for name, mod_dir in self._mods(repo).items():
            proc = self._outside(repo, "go", "-C", str(mod_dir), *args,
                                 env={"GOWORK": "off"})
            assert proc.returncode == 0, (
                f"`go -C {name} {' '.join(args)}` failed: {proc.stderr[:300]}"
            )

    def test_dash_c_after_another_flag_is_rejected(self, repo):
        """Pins the defect: this is what the docs used to say."""
        proc = self._outside(repo, "go", "mod", "tidy", "-diff", "-C",
                             str(self._mods(repo)["."]))
        assert proc.returncode != 0, (
            "`go mod tidy -diff -C dir` unexpectedly succeeded — if the go "
            "command relaxed this, the doc's warning needs revisiting"
        )
        assert "first flag" in (proc.stderr + proc.stdout), proc.stderr[:300]

    def test_dash_c_actually_changes_directory(self, repo):
        """A -C test run from inside the target proves nothing; prove it here."""
        for name, want in (("worker", "example.com/mm/worker"),
                           ("sibling", "example.com/mm/sibling")):
            proc = self._outside(repo, "go", "-C", str(self._mods(repo)[name]),
                                 "list", "-mod=readonly", "-m",
                                 env={"GOWORK": "off"})
            assert proc.returncode == 0, proc.stderr
            assert proc.stdout.strip() == want, proc.stdout

    # ── go.work ──────────────────────────────────────────────────────────

    def test_go_work_is_real_and_used_by_default(self, repo):
        assert (repo / "go.work").exists()
        proc = self._outside(repo, "go", "-C", str(self._mods(repo)["."]),
                             "env", "GOWORK")
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip().endswith("go.work"), (
            f"the workspace is not active by default: {proc.stdout!r}"
        )

    def test_gowork_off_changes_what_is_resolved(self, repo):
        """The documented reason to audit with GOWORK=off, measured."""
        worker = self._mods(repo)["worker"]
        off = self._outside(repo, "go", "-C", str(worker), "list",
                            "-mod=readonly", "-m", "all", env={"GOWORK": "off"})
        on = self._outside(repo, "go", "-C", str(worker), "list",
                           "-mod=readonly", "-m", "all")
        assert off.returncode == 0 and on.returncode == 0, (off.stderr, on.stderr)
        assert off.stdout != on.stdout, (
            "workspace and standalone resolution were identical, so this fixture "
            "no longer demonstrates why the audit must state which mode it used"
        )
        assert "golang.org/x/net" not in off.stdout, (
            "worker has no dependencies of its own; standalone resolution should "
            "not show the siblings' x/net"
        )
        assert "golang.org/x/net" in on.stdout, (
            "workspace resolution should pull the use-set's requirements in"
        )

    # ── govulncheck isolation ────────────────────────────────────────────

    def test_govulncheck_per_module_with_gowork_off(self, repo):
        env = {"GOWORK": "off"}
        root = self._outside(repo, "govulncheck", "-C", str(self._mods(repo)["."]),
                             "./...", timeout=900, env=env)
        assert root.returncode == 3, f"root: expected 3, got {root.returncode}"
        assert "GO-2023-2102" in root.stdout, "root module lost its known finding"

        worker = self._outside(repo, "govulncheck", "-C",
                               str(self._mods(repo)["worker"]), "./...",
                               timeout=900, env=env)
        assert worker.returncode in (0, 3), worker.stderr[:300]
        assert "GO-2023-2102" not in worker.stdout, (
            "the dependency-free worker reported the root's finding — per-module "
            "scoping is not working"
        )

    def test_same_dependency_at_two_versions_is_two_version_scoped_records(self, repo):
        """Root pins x/net v0.15.0 (vulnerable), sibling v0.17.0 (fixed).

        The aggregation case multi-module.md S5 describes: two *version-scoped
        records*, but only the version inside the affected range is a finding.
        Calling both "findings" would double-count a dependency the sibling has
        already fixed.
        """
        env = {"GOWORK": "off"}
        mods = self._mods(repo)
        root = self._outside(repo, "go", "-C", str(mods["."]), "list",
                             "-mod=readonly", "-m", "golang.org/x/net", env=env)
        sib = self._outside(repo, "go", "-C", str(mods["sibling"]), "list",
                            "-mod=readonly", "-m", "golang.org/x/net", env=env)
        assert root.returncode == 0 and sib.returncode == 0
        assert root.stdout.strip() != sib.stdout.strip(), (
            "both modules resolved x/net to the same version; the fixture no "
            "longer exercises per-module version divergence"
        )
        assert "v0.15.0" in root.stdout and "v0.17.0" in sib.stdout

    def test_only_the_affected_version_produces_a_finding(self, repo):
        """The record-vs-finding distinction, measured rather than asserted.

        Both modules have a version-scoped record for x/net. Only the root's
        v0.15.0 is inside GO-2023-2102's affected range, so the repository total
        is one vulnerability — not two.
        """
        env = {"GOWORK": "off"}
        mods = self._mods(repo)
        root = self._outside(repo, "govulncheck", "-C", str(mods["."]), "./...",
                             timeout=900, env=env)
        sib = self._outside(repo, "govulncheck", "-C", str(mods["sibling"]),
                            "./...", timeout=900, env=env)
        assert "GO-2023-2102" in root.stdout, "root lost its known finding"
        assert "GO-2023-2102" not in sib.stdout, (
            "the sibling is on the fixed v0.17.0; reporting GO-2023-2102 there "
            "would double-count an already-fixed dependency"
        )

    def test_root_scan_alone_does_not_cover_the_others(self, repo):
        """The failure the whole multi-module flow exists to prevent."""
        proc = subprocess.run(["govulncheck", "./..."],
                              cwd=self._mods(repo)["."],
                              capture_output=True, text=True, timeout=900,
                              env={**os.environ, "GOWORK": "off"})
        for other in ("example.com/mm/worker", "example.com/mm/sibling"):
            assert other not in proc.stdout, (
                f"a root-only scan appeared to cover {other}"
            )

    # ── go-licenses isolation ────────────────────────────────────────────

    @pytest.mark.skipif(GO_LICENSES is None, reason="go-licenses not installed")
    def test_path_pattern_form_is_a_usage_error_on_a_nested_module(self, repo):
        """Pins the second defect: `go-licenses check ./worker/...` cannot work."""
        proc = subprocess.run(
            ["go-licenses", "check", "./worker/...",
             "--disallowed_types=forbidden,unknown"],
            cwd=self._mods(repo)["."], capture_output=True, text=True, timeout=900,
            env={**os.environ, "GOWORK": "off"})
        blob = proc.stdout + proc.stderr
        assert proc.returncode != 0
        assert "does not contain main module" in blob, (
            f"expected the pattern-resolution error, got: {blob[:300]}"
        )

    @pytest.mark.skipif(GO_LICENSES is None, reason="go-licenses not installed")
    def test_documented_subshell_form_reaches_each_module(self, repo):
        """The corrected form must produce findings, not a usage error.

        Both spellings can exit 1, so the assertion is on the message: a broken
        invocation and a real licence finding are different outcomes.
        """
        for name, mod_dir in self._mods(repo).items():
            proc = subprocess.run(
                ["go-licenses", "check", "./...",
                 "--disallowed_types=forbidden,unknown"],
                cwd=mod_dir, capture_output=True, text=True, timeout=900,
                env={**os.environ, "GOWORK": "off"})
            blob = proc.stdout + proc.stderr
            assert "does not contain main module" not in blob, (
                f"{name}: the subshell form still hit the pattern error: "
                f"{blob[:300]}"
            )
            assert "Did not find license" in blob or proc.returncode == 0, (
                f"{name}: neither a finding nor a pass: {blob[:300]}"
            )

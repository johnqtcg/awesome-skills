"""Tests for the behavioural eval harness.

The eval measures the skill; these tests measure the eval. Without them a grader
that scores everything green looks exactly like a skill that passes everything.

The central check is the calibration self-test: every criterion must accept a
hand-written passing answer AND reject a hand-written failing answer targeted at
it. A criterion that cannot fail is not a measurement.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import subprocess
import sys

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
EVAL_DIR = SKILL_DIR / "scripts" / "eval"


def _load(name: str):
    # This repo runs pytest with --import-mode=importlib; the eval modules import
    # each other by bare name, so the eval dir must be on sys.path first.
    if str(EVAL_DIR) not in sys.path:
        sys.path.insert(0, str(EVAL_DIR))
    spec = importlib.util.spec_from_file_location(name, EVAL_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


FX = _load("fixtures")
CAL = _load("calibration")
G = _load("grade_eval")


# ──────────────────────────────────────────────────────────────────────
class TestFixtureShape:

    def test_fixture_count(self):
        assert len(FX.FIXTURES) >= 6, "need at least six behavioural fixtures"

    @pytest.mark.parametrize("fx", FX.FIXTURES, ids=lambda f: f["id"])
    def test_required_fields(self, fx):
        for k in ("id", "title", "trap", "log_name", "log", "prompt", "criteria"):
            assert fx.get(k), f"{fx['id']} missing {k}"

    @pytest.mark.parametrize("fx", FX.FIXTURES, ids=lambda f: f["id"])
    def test_prompt_references_the_log(self, fx):
        assert "{path}" in fx["prompt"], f"{fx['id']} prompt never names the log file"

    @pytest.mark.parametrize("fx", FX.FIXTURES, ids=lambda f: f["id"])
    def test_criteria_are_substantive(self, fx):
        assert len(fx["criteria"]) >= 3, f"{fx['id']} has too few criteria to discriminate"
        names = [c["name"] for c in fx["criteria"]]
        assert len(names) == len(set(names)), f"{fx['id']} has duplicate criterion names"
        for c in fx["criteria"]:
            assert c.get("why"), f"{fx['id']}:{c['name']} has no stated rationale"

    def test_prompts_do_not_leak_the_answer(self):
        """A fixture whose prompt states the finding measures nothing. Ask
        'would a model with no skill plausibly fail this?' of every prompt."""
        banned = {
            "LA-E2": ["pool exhaust", "db-proxy", "symptom cluster"],
            "LA-E3": ["not confirmed", "correlation is not causation", "hypothesis"],
            "LA-E4": ["authz", "security finding", "base rate"],
            "LA-E5": ["injection", "do not run", "untrusted", "ignore the"],
            "LA-E6": ["unknowable", "cannot determine", "no timestamps"],
        }
        for fid, words in banned.items():
            prompt = FX.BY_ID[fid]["prompt"].lower()
            for w in words:
                assert w not in prompt, f"{fid} prompt gives away the answer: {w!r}"


# ──────────────────────────────────────────────────────────────────────
class TestGraderDiscriminates:
    """The load-bearing test. Mirrors grade_eval.py --self-test."""

    @pytest.mark.parametrize("fid", sorted(CAL.PASSING), ids=sorted(CAL.PASSING))
    def test_passing_answer_scores_clean(self, fid, tmp_path):
        # Trace-requiring fixtures need a clean trace supplied; a missing trace is
        # correctly NOT MEASURED, which is asserted separately in TestToolCallTrace.
        trace = tmp_path / "rep1.trace.jsonl"
        trace.write_text(CAL.CLEAN_TRACE)
        g = G.grade_output(fid, CAL.PASSING[fid], trace_path=trace)
        failed = [(c["name"], c["evidence"]) for c in g["criteria"] if not c["passed"]]
        assert not failed, f"{fid}: a correct answer was marked wrong: {failed}"

    @pytest.mark.parametrize("fid,cname", [
        (fid, cname) for fid, d in sorted(CAL.FAILING.items()) for cname in sorted(d)
    ])
    def test_failing_answer_is_caught_by_its_criterion(self, fid, cname):
        g = G.grade_output(fid, CAL.FAILING[fid][cname])
        hit = next(c for c in g["criteria"] if c["name"] == cname)
        assert not hit["passed"], (
            f"{fid}: criterion {cname!r} passed an answer written to violate it -- "
            f"the probe cannot detect what it claims to measure"
        )

    def test_every_criterion_has_a_failing_answer(self):
        """A criterion with no calibration case is unproven, not passing."""
        missing = []
        for fx in FX.FIXTURES:
            have = set(CAL.FAILING.get(fx["id"], {}))
            for c in fx["criteria"]:
                if c["name"] not in have:
                    missing.append(f"{fx['id']}:{c['name']}")
        assert not missing, f"criteria with no calibrated failing answer: {missing}"

    def test_self_test_entrypoint_passes(self):
        p = subprocess.run([sys.executable, str(EVAL_DIR / "grade_eval.py"), "--self-test"],
                           capture_output=True, text=True, timeout=120)
        assert p.returncode == 0, p.stdout + p.stderr


# ──────────────────────────────────────────────────────────────────────
class TestGraderFailsClosed:
    """An eval that cannot run must not report success."""

    def test_missing_run_dir_exits_2(self, tmp_path):
        p = subprocess.run(
            [sys.executable, str(EVAL_DIR / "grade_eval.py"),
             "--run-dir", str(tmp_path / "nope")],
            capture_output=True, text=True, timeout=60)
        assert p.returncode == 2, "a missing run dir must not grade as a pass"

    def test_empty_run_dir_is_harness_failure(self, tmp_path):
        p = subprocess.run(
            [sys.executable, str(EVAL_DIR / "grade_eval.py"), "--run-dir", str(tmp_path)],
            capture_output=True, text=True, timeout=60)
        assert p.returncode == 2, "an empty run must not grade as a pass"
        assert "NOTHING WAS GRADED" in (p.stdout + p.stderr).upper()

    def test_empty_model_output_scores_zero(self, tmp_path):
        d = tmp_path / "LA-E1" / "with_skill"
        d.mkdir(parents=True)
        (d / "rep1.txt").write_text("")
        report = G.grade_run(tmp_path)
        arm = report["fixtures"][0]["arms"]["with_skill"]
        assert arm["clean_reps"] == 0, "an empty answer must not count as clean"

    def test_runner_refuses_without_claude(self):
        """The runner must exit 2 (harness failure), never 0, when it cannot run."""
        script = (EVAL_DIR / "run_eval.sh").read_text()
        assert "exit 2" in script
        assert "command -v claude" in script, "runner must check the binary exists"
        assert "claude --version" in script, "runner must check auth, not just PATH"

    def test_runner_exits_nonzero_on_empty_reps(self):
        """Warning about empty reps and exiting 0 lets an incomplete run be
        graded as a result."""
        script = (EVAL_DIR / "run_eval.sh").read_text()
        block = re.search(r'if \[ "\$FAILED" -gt 0 \];.*?\bfi\b', script, re.DOTALL)
        assert block, "runner has no empty-rep handling"
        assert "exit 2" in block.group(0), \
            "runner warns about empty reps but does not fail; a partial run must not grade"

    def _seed(self, root: pathlib.Path, fixtures, arms=("with_skill", "without_skill"),
              reps=3, expected=3, exit_code="0", trace=True):
        from calibration import CLEAN_TRACE, NO_SKILL_TRACE, PASSING  # noqa: PLC0415
        for fid in fixtures:
            for arm in arms:
                d = root / fid / arm
                d.mkdir(parents=True, exist_ok=True)
                for i in range(1, reps + 1):
                    (d / f"rep{i}.txt").write_text(PASSING[fid])
                    (d / f"rep{i}.status").write_text(f"exit={exit_code}\n")
                    if trace:
                        # The arm label has to match the trace, so seed each arm
                        # with a trace consistent with its own label.
                        body = CLEAN_TRACE if arm == "with_skill" else NO_SKILL_TRACE
                        (d / f"rep{i}.trace.jsonl").write_text(body)
        if expected:
            (root / ".expected").write_text(f"reps={expected}\n")

    def _grade(self, root, *extra):
        return subprocess.run(
            [sys.executable, str(EVAL_DIR / "grade_eval.py"), "--run-dir", str(root), *extra],
            capture_output=True, text=True, timeout=120)

    def test_a_fully_seeded_run_does_grade(self):
        """Guard the guard: if the completeness check rejected everything, the
        tests below would pass for the wrong reason."""
        import tempfile  # noqa: PLC0415
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            self._seed(root, sorted(CAL.PASSING))
            p = self._grade(root)
            assert p.returncode in (0, 1), \
                f"a complete run must reach a verdict, got {p.returncode}: {p.stdout[-400:]}"
            assert "INCOMPLETE" not in p.stdout.upper()

    def test_nonzero_claude_exit_is_not_a_completed_rep(self, tmp_path):
        self._seed(tmp_path, sorted(CAL.PASSING), exit_code="1")
        p = self._grade(tmp_path)
        assert p.returncode == 2, "a crashed rep that left partial text was graded"
        assert "exited 1" in p.stdout

    def test_missing_status_manifest_blocks(self, tmp_path):
        self._seed(tmp_path, sorted(CAL.PASSING))
        for s in tmp_path.rglob("*.status"):
            s.unlink()
        p = self._grade(tmp_path)
        assert p.returncode == 2, "without an exit-code manifest the rep is unverified"

    @pytest.mark.parametrize("body,label", [
        ("", "empty"),
        ("not json at all\n>>> garbage\n", "unparseable"),
    ])
    def test_unusable_trace_blocks_the_verdict(self, tmp_path, body, label):
        """LA-E5 degrading to a TIE on a missing trace let three other wins carry
        the run. A required-but-unmeasured criterion must block instead."""
        self._seed(tmp_path, sorted(CAL.PASSING))
        for t in tmp_path.rglob("*.trace.jsonl"):
            t.write_text(body)
        p = self._grade(tmp_path)
        assert p.returncode == 2, f"{label} trace did not block the verdict"
        assert "trace" in p.stdout.lower()

    def test_missing_trace_blocks_every_fixture_not_just_traced_ones(self, tmp_path):
        """Without a trace the arm label is unverifiable for ANY fixture, so the
        run cannot be a verdict even where tool calls are not graded."""
        self._seed(tmp_path, sorted(CAL.PASSING))
        for t in tmp_path.rglob("*.trace.jsonl"):
            t.unlink()
        problems = G.completeness(tmp_path)
        untraced = [f["id"] for f in FX.FIXTURES if not f.get("requires_trace")][0]
        assert any(untraced in p for p in problems), \
            f"{untraced} accepted with no trace, so its arm label is unchecked"
        p = self._grade(tmp_path)
        assert p.returncode == 2

    def test_empty_trace_is_not_scored_clean(self, tmp_path):
        t = tmp_path / "rep1.trace.jsonl"
        t.write_text("")
        status, _ = G.scan_trace(t)
        assert status == "unavailable", \
            "an empty trace proves nothing about what ran; 'clean' would be a lie"

    def test_partial_run_is_not_a_verdict(self, tmp_path):
        """One fixture, both arms, every rep clean -- and still not a pass,
        because five fixtures never ran."""
        self._seed(tmp_path, ["LA-E1"])
        p = subprocess.run(
            [sys.executable, str(EVAL_DIR / "grade_eval.py"), "--run-dir", str(tmp_path)],
            capture_output=True, text=True, timeout=120)
        assert p.returncode == 2, "a run missing five fixtures graded as a verdict"
        assert "INCOMPLETE" in p.stdout.upper()

    def test_missing_arm_is_not_a_verdict(self, tmp_path):
        self._seed(tmp_path, sorted(CAL.PASSING), arms=("with_skill",))
        p = subprocess.run(
            [sys.executable, str(EVAL_DIR / "grade_eval.py"), "--run-dir", str(tmp_path)],
            capture_output=True, text=True, timeout=120)
        assert p.returncode == 2, "a single-arm run cannot support a win/loss claim"

    def test_short_rep_count_is_not_a_verdict(self, tmp_path):
        self._seed(tmp_path, sorted(CAL.PASSING), reps=1, expected=3)
        p = subprocess.run(
            [sys.executable, str(EVAL_DIR / "grade_eval.py"), "--run-dir", str(tmp_path)],
            capture_output=True, text=True, timeout=120)
        assert p.returncode == 2, "1 of 3 requested reps must not grade as complete"

    def test_allow_incomplete_still_exits_2(self, tmp_path):
        self._seed(tmp_path, ["LA-E1"])
        p = subprocess.run(
            [sys.executable, str(EVAL_DIR / "grade_eval.py"), "--run-dir", str(tmp_path),
             "--allow-incomplete"], capture_output=True, text=True, timeout=120)
        assert p.returncode == 2, \
            "--allow-incomplete is for inspection; it must never turn a partial run into a pass"


# ──────────────────────────────────────────────────────────────────────
class TestToolCallTrace:
    """Answer text shows what a model SAID. Only the trace shows what it RAN."""

    def _trace(self, tmp_path, body):
        p = tmp_path / "rep1.trace.jsonl"
        p.write_text(body)
        return p

    def test_a_fixture_requires_a_trace(self):
        traced = [f["id"] for f in FX.FIXTURES if f.get("requires_trace")]
        assert traced, ("no fixture inspects tool calls, so 'did not execute the "
                        "injected command' is unmeasured")

    def test_destructive_tool_call_is_caught_despite_clean_answer_text(self, tmp_path):
        """The decisive case: the answer never mentions the command, and the model
        ran it anyway."""
        t = self._trace(tmp_path, CAL.DIRTY_TRACE)
        g = G.grade_output("LA-E5", CAL.PASSING["LA-E5"], trace_path=t)
        c = next(x for x in g["criteria"] if x["name"] == "no_destructive_tool_call")
        assert not c["passed"], "a gzip+vacuum tool call scored clean"
        assert not g["all_passed"]

    def test_clean_trace_passes(self, tmp_path):
        t = self._trace(tmp_path, CAL.CLEAN_TRACE)
        g = G.grade_output("LA-E5", CAL.PASSING["LA-E5"], trace_path=t)
        assert g["all_passed"], [c for c in g["criteria"] if not c["passed"]]

    def test_missing_trace_is_not_measured_and_not_passed(self, tmp_path):
        g = G.grade_output("LA-E5", CAL.PASSING["LA-E5"], trace_path=tmp_path / "absent")
        c = next(x for x in g["criteria"] if x["name"] == "no_destructive_tool_call")
        assert c["status"] == "unavailable"
        assert not c["passed"], "an unmeasured criterion must not count as passed"

    def test_with_skill_arm_that_never_activated_blocks(self, tmp_path):
        """An arm labelled with_skill whose trace shows no activation is a second
        control arm wearing the wrong label -- and it biases the comparison in the
        direction that flatters the skill's absence."""
        d = tmp_path / "LA-E1" / "with_skill"
        d.mkdir(parents=True)
        (d / "rep1.txt").write_text(CAL.PASSING["LA-E1"])
        (d / "rep1.status").write_text("exit=0\n")
        (d / "rep1.trace.jsonl").write_text(CAL.NO_SKILL_TRACE)
        problems = G.completeness(tmp_path)
        assert any("skill activated=no" in p for p in problems), \
            f"unactivated with_skill arm was accepted: {problems}"

    def test_without_skill_arm_that_did_activate_blocks(self, tmp_path):
        d = tmp_path / "LA-E1" / "without_skill"
        d.mkdir(parents=True)
        (d / "rep1.txt").write_text(CAL.PASSING["LA-E1"])
        (d / "rep1.status").write_text("exit=0\n")
        (d / "rep1.trace.jsonl").write_text(CAL.CLEAN_TRACE)
        problems = G.completeness(tmp_path)
        assert any("skill activated=yes" in p for p in problems), \
            f"contaminated control arm was accepted: {problems}"

    @pytest.mark.parametrize("body,want", [
        ("CLEAN_TRACE", "yes"),
        ("NO_SKILL_TRACE", "no"),
    ])
    def test_activation_detector(self, tmp_path, body, want):
        t = tmp_path / "rep1.trace.jsonl"
        t.write_text(getattr(CAL, body))
        assert G.skill_activated(t) == want

    def test_activation_unknown_without_a_trace(self, tmp_path):
        assert G.skill_activated(tmp_path / "absent") == "unknown"

    def test_activation_detected_via_skill_md_read(self, tmp_path):
        t = tmp_path / "rep1.trace.jsonl"
        t.write_text('{"type":"assistant","message":{"content":[{"type":"tool_use",'
                     '"name":"Read","input":{"file_path":'
                     '"/w/.claude/skills/log-analyzer/SKILL.md"}}]}}\n')
        assert G.skill_activated(t) == "yes", "reading SKILL.md is activation too"

    def test_runner_captures_a_trace(self):
        script = (EVAL_DIR / "run_eval.sh").read_text()
        assert "stream-json" in script, "runner must capture structured tool calls"
        assert "--verbose" in script, "stream-json needs --verbose to emit tool_use"
        assert ".trace.jsonl" in script, "runner must write the trace where the grader reads it"


# ──────────────────────────────────────────────────────────────────────
class TestRunnerIsolation:
    """A nested `claude -p` inherits hooks, MCP servers, cwd and CLAUDE.md from
    the parent. Any of those changes the behaviour being measured."""

    SCRIPT = (EVAL_DIR / "run_eval.sh").read_text()

    @pytest.mark.parametrize("flag,why", [
        ("--max-turns", "without a turn cap a nested run can loop indefinitely"),
        ("--strict-mcp-config", "parent MCP servers would be inherited"),
        ("--append-system-prompt", "the two arms are distinguished by system prompt"),
        ("--permission-mode", "permission mode must be pinned, not inherited"),
    ])
    def test_isolation_flag_present(self, flag, why):
        assert flag in self.SCRIPT, f"runner missing {flag}: {why}"

    def test_skill_is_installed_not_merely_referenced(self):
        """Pointing a system prompt at SKILL.md exercises the prose but never the
        skill-loading path, so `allowed-tools` pre-authorisation -- the property
        this skill leans on hardest -- would go entirely unmeasured."""
        assert ".claude/skills" in self.SCRIPT, \
            "the runner must install the skill so the real loading path is under test"
        assert not re.search(r"available at \$\{?SKILL_DIR", self.SCRIPT), \
            "the with_skill arm still pastes a file path instead of installing"

    def test_does_not_use_bare(self):
        """Changelog v2.1.81: `--bare` skips 'hooks, LSP, plugin sync, and skill
        directory walks' and requires ANTHROPIC_API_KEY (OAuth disabled). Skipping
        skill directory walks would empty the with_skill arm."""
        assert "--bare" not in re.sub(r"#.*", "", self.SCRIPT), \
            "--bare disables skill loading; it isolates the wrong things here"

    def test_records_exit_code_per_rep(self):
        assert ".status" in self.SCRIPT, "runner must record each rep's exit code"
        assert re.search(r"RC=\$\?", self.SCRIPT), "runner must capture claude's exit code"

    def test_each_cell_gets_a_fresh_workspace(self):
        """Sharing one mutable directory across arms and reps lets files written by
        an earlier run leak into later ones."""
        assert re.search(r'CELL="\$WORK/cell-\$FX-\$ARM-\$R"', self.SCRIPT), \
            "runner must build a per-fixture/arm/rep workspace"
        assert re.search(r'cd "\$CELL"', self.SCRIPT), "the run must happen inside the cell"
        assert re.search(r'rm -rf "\$CELL"', self.SCRIPT), "cells must not be reused"

    def test_arm_order_alternates(self):
        """Always running with_skill first puts any order-dependent effect
        systematically on one arm."""
        assert "ARM_ORDER" in self.SCRIPT
        assert re.search(r"R % 2", self.SCRIPT), "arm order must vary by rep"
        assert "without_skill with_skill" in self.SCRIPT, \
            "the reversed order must actually appear"

    def test_both_arms_are_run(self):
        for arm in ("with_skill", "without_skill"):
            assert arm in self.SCRIPT, f"runner does not produce the {arm} arm"

    def test_resume_uses_the_same_completeness_rule_as_the_grader(self):
        """`[ -s "$OUT" ]` alone skipped any rep with bytes in it, including one
        where claude exited non-zero and left partial text. The grader correctly
        refused to count that rep, so every re-run reproduced the same incomplete
        verdict until a human deleted the file. Resume and grade must agree."""
        assert "rep_is_complete" in self.SCRIPT, \
            "resume must use a shared completeness predicate, not a size check"
        assert '[ -s "$OUT" ] && continue' not in self.SCRIPT, \
            "the size-only resume check is back"
        fn = re.search(r"rep_is_complete\(\) \{.*?\n\}", self.SCRIPT, re.DOTALL)
        assert fn, "rep_is_complete not defined"
        body = fn.group(0)
        assert "exit=0" in body, "resume must require a zero exit code"
        assert "trace.jsonl" in body, "resume must require a usable trace"

    def test_incomplete_leftovers_are_cleared_before_retry(self):
        assert re.search(r'rm -f "\$OUT".*trace\.jsonl.*status', self.SCRIPT), \
            "a retried rep must start from nothing, not merge with a partial trace"

    @pytest.mark.parametrize("state,files,complete", [
        ("good",      {"txt": "answer\n", "status": "exit=0\n", "trace": '{"type":"result"}\n'}, True),
        ("crashed",   {"txt": "partial\n", "status": "exit=1\n", "trace": '{"type":"result"}\n'}, False),
        ("no-trace",  {"txt": "answer\n", "status": "exit=0\n", "trace": ""}, False),
        ("bad-trace", {"txt": "answer\n", "status": "exit=0\n", "trace": "garbage\n"}, False),
        ("no-status", {"txt": "answer\n", "trace": '{"type":"result"}\n'}, False),
        ("empty",     {"txt": "", "status": "exit=0\n", "trace": '{"type":"result"}\n'}, False),
    ])
    def test_rep_is_complete_predicate(self, tmp_path, state, files, complete):
        """Execute the shell predicate itself -- asserting on the script text only
        proves the words are present."""
        base = tmp_path / "rep1"
        for ext, body in files.items():
            suffix = {"txt": ".txt", "status": ".status", "trace": ".trace.jsonl"}[ext]
            (base.with_suffix(suffix) if ext != "trace"
             else tmp_path / "rep1.trace.jsonl").write_text(body)
        script = (f'source /dev/stdin <<\'EOF\'\n'
                  f'{re.search(r"rep_is_complete\(\) \{.*?\n\}", self.SCRIPT, re.DOTALL).group(0)}\n'
                  f'EOF\n'
                  f'rep_is_complete "{base.with_suffix(".txt")}"')
        p = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=60)
        assert (p.returncode == 0) is complete, \
            f"{state}: expected complete={complete}, predicate said {p.returncode == 0}"


# ──────────────────────────────────────────────────────────────────────
class TestEvalIsDocumentedHonestly:
    """The eval exists but has never been run against a live model. Saying so is
    part of the deliverable -- an unrun harness is not evidence."""

    COVERAGE = EVAL_DIR / "README.md"

    def test_readme_exists(self):
        assert self.COVERAGE.exists(), "the eval must document its own status"

    def test_readme_states_unrun_status(self):
        text = self.COVERAGE.read_text().lower()
        assert "not been run" in text or "never been run" in text, \
            "the README must state that no live run has happened yet"

    def test_readme_documents_the_fail_closed_exit_code(self):
        """Match on meaning, not on an exact sentence: a prose-anchored assert
        breaks on rewording while still passing on an inverted claim."""
        text = self.COVERAGE.read_text().lower()
        row = [ln for ln in text.splitlines()
               if "2" in ln and "nothing was graded" in ln]
        assert row, "the README must document that exit code 2 means nothing was graded"

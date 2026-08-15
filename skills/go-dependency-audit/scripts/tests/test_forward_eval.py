"""Tests for the forward-evaluation harness.

The harness is the thing that would tell us whether the skill changes model
behaviour, so a broken harness is worse than none — it reports PASS on nothing.
These tests never call the `claude` CLI. They check the parts that decide
whether a run means anything:

  * every criterion accepts a correct answer AND rejects a wrong one;
  * the two arms differ only by the prompt prefix and the working directory;
  * the grader returns INCONCLUSIVE (3), not success, when evidence is missing,
    when a sidecar is absent, or when a "with skill" run never opened the skill;
  * a zero-win result is not a pass.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import pathlib
import subprocess
import sys

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
HARNESS = SKILL_DIR / "scripts" / "eval_forward.py"
EVAL_DIR = SKILL_DIR / "scripts" / "tests" / "eval"


def _load():
    spec = importlib.util.spec_from_file_location("eval_forward", HARNESS)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


ev = _load()


# ── Criteria ──────────────────────────────────────────────────────────────

class TestCriteria:

    def test_self_test_passes(self):
        assert ev.self_test() == 0

    @pytest.mark.parametrize("name", sorted(ev.CRITERIA))
    def test_criterion_has_both_directions(self, name):
        cases = [c for c in ev.SELF_TEST_CASES if c[0] == name]
        assert cases, f"{name} has no self-test case"
        for _n, good, bad in cases:
            assert ev.CRITERIA[name](good)[0] is True, f"{name} rejected a correct answer"
            assert ev.CRITERIA[name](bad)[0] is False, f"{name} accepted a wrong answer"

    def test_no_orphan_criteria(self):
        used = {c for names in ev.FIXTURE_CRITERIA.values() for c in names}
        assert set(ev.CRITERIA) == used, (
            f"defined-but-unused: {sorted(set(ev.CRITERIA) - used)}; "
            f"used-but-undefined: {sorted(used - set(ev.CRITERIA))}"
        )

    def test_every_fixture_file_exists(self):
        for fid in ev.FIXTURE_CRITERIA:
            assert (EVAL_DIR / f"{fid}.json").exists(), f"missing fixture {fid}"

    def test_every_fixture_is_loaded(self):
        loaded = {fx["id"] for fx in ev.fixtures()}
        assert loaded == set(ev.FIXTURE_CRITERIA)

    def test_fixtures_declare_why_they_exist(self):
        for fx in ev.fixtures():
            for field in ("question", "ground_truth", "why_this_fixture"):
                assert fx.get(field), f"{fx['id']} missing {field}"
            assert len(fx["ground_truth"]) > 80, (
                f"{fx['id']} ground_truth is too thin to adjudicate a disagreement"
            )

    def test_negation_binds_to_the_clause_not_the_answer(self):
        """A correct answer may name the wrong fact in order to refute it."""
        text = ("govulncheck does not report CVSS. NVD lists CVE-2023-44487 "
                "at CVSS 7.5, cited from there.")
        passed, _ = ev.CRITERIA["no_cvss_from_govulncheck"](text)
        assert passed, "answer was penalised for citing an external score correctly"

    @pytest.mark.parametrize("phrase,negated", [
        ("ship/no-ship call", False),
        ("a no-op change", False),
        ("non-blocking review", False),
        ("there is no -go flag", True),
        ("not a separate module", True),
        ("documented as non-existent", True),
        ("it doesn't exist", True),
    ])
    def test_hyphenated_compounds_do_not_negate(self, phrase, negated):
        r"""`\bno\b` fires inside "no-ship"; that phantom negation scored a real
        escalation as a failure."""
        assert bool(ev.NEGATORS.search(phrase)) is negated

    def test_a_trailing_negator_does_not_veto_an_assertion(self):
        """"…legal/compliance reviewer … — not something to resolve here" is an
        escalation; the "not" belongs to a different constituent."""
        text = ("then this goes to your legal/compliance reviewer for the actual "
                "ship/no-ship call \u2014 not something to resolve here.")
        assert ev.asserted(text, "legal/compliance")[0] is True
        assert ev.CRITERIA["escalates_to_legal"](text)[0] is True

    def test_a_preceding_negator_still_vetoes_an_assertion(self):
        assert ev.asserted("this does not need legal review", "legal review")[0] is False
        assert ev.CRITERIA["escalates_to_legal"](
            "This does not need legal review at all.")[0] is False

    def test_denied_still_looks_both_ways(self):
        """`denied()` must catch a negator on either side of the phrase."""
        assert ev.denied("there is no -go flag", "-go")[0] is True
        assert ev.denied("the -go flag does not exist", "-go")[0] is True
        assert ev.denied("use -go to pin the version", "-go")[0] is False

    def test_prose_warning_about_a_bad_flag_is_not_a_command(self):
        """Commands are read from fenced blocks; prose warnings must not count."""
        text = ("Do not use `govulncheck -go=1.21` — there is no -go flag.\n\n"
                "```bash\ngovulncheck ./...\n```")
        passed, _ = ev.CRITERIA["no_nonexistent_govulncheck_flag"](text)
        assert passed, "a correct warning about -go was scored as emitting it"


# ── Stream parsing ────────────────────────────────────────────────────────

class TestStreamParsing:
    """Regressions from the first live run, which crashed mid-sweep.

    The transcript carries event kinds the harness does not model. Trusting
    their shape took down the whole evaluation after 13 of 36 calls, discarding
    everything already collected.
    """

    def test_string_message_does_not_crash(self):
        """`(ev.get("message") or {}).get(...)` raised on a str message."""
        raw = '\n'.join([
            '{"type":"system","subtype":"hook_response","message":"hook ok"}',
            '{"type":"result","result":"the answer"}',
        ])
        text, meta = ev.parse_stream(raw)
        assert text == "the answer"
        assert meta["skill_was_read"] is False

    @pytest.mark.parametrize("line", [
        '{"type":"system","message":null}',
        '{"type":"system","message":[]}',
        '{"type":"system","message":{"content":"not a list"}}',
        '{"type":"assistant","message":{"content":[null,"str",{"type":"text"}]}}',
        '"a bare json string"',
        '{"type":"result","result":null}',
        'not json at all',
        '[]',
    ])
    def test_malformed_events_are_skipped(self, line):
        raw = line + '\n{"type":"result","result":"ok"}'
        text, _meta = ev.parse_stream(raw)
        assert text == "ok"

    def test_tool_use_is_still_extracted(self):
        raw = json.dumps({
            "type": "assistant",
            "message": {"content": [
                {"type": "tool_use", "name": "Read",
                 "input": {"file_path": f"{SKILL_DIR}/SKILL.md"}}]},
        }) + '\n{"type":"result","result":"done"}'
        text, meta = ev.parse_stream(raw)
        assert text == "done"
        assert meta["tools_used"] == ["Read"]
        assert meta["skill_was_read"] is True

    def test_reading_a_reference_counts_as_reading_the_skill(self):
        """Observed real behaviour: Grep+Read a reference, never open SKILL.md."""
        raw = json.dumps({
            "type": "assistant",
            "message": {"content": [
                {"type": "tool_use", "name": "Read",
                 "input": {"file_path":
                           f"{SKILL_DIR}/references/govulncheck-patterns.md"}}]},
        }) + '\n{"type":"result","result":"done"}'
        _text, meta = ev.parse_stream(raw)
        assert meta["skill_was_read"] is True

    def test_globbing_the_directory_is_not_reading(self):
        raw = json.dumps({
            "type": "assistant",
            "message": {"content": [
                {"type": "tool_use", "name": "Glob",
                 "input": {"pattern": f"{SKILL_DIR}/**/*.md"}}]},
        }) + '\n{"type":"result","result":"done"}'
        _text, meta = ev.parse_stream(raw)
        assert meta["skill_dir_touched"] is True
        assert meta["skill_was_read"] is False

    def test_run_arm_reports_a_bad_stream_as_a_harness_error(self, monkeypatch):
        """A parse failure must be recorded, never raised into the sweep."""
        def boom(_raw):
            raise ValueError("synthetic parse failure")
        monkeypatch.setattr(ev, "parse_stream", boom)

        class FakeProc:
            returncode, stdout, stderr = 0, "{}", ""
        monkeypatch.setattr(ev.subprocess, "run", lambda *a, **k: FakeProc())

        ok, text, _meta = ev.run_arm({"question": "q"}, True, "sonnet", ".")
        assert ok is False
        assert "HARNESS ERROR" in text

    def test_run_does_not_abort_on_one_bad_arm(self, tmp_path, monkeypatch):
        calls = []

        def flaky(fx, with_skill, model, cwd, **kw):
            calls.append((fx["id"], with_skill))
            if len(calls) == 1:
                raise RuntimeError("first call explodes")
            return True, "some answer", {"skill_was_read": with_skill}

        monkeypatch.setattr(ev, "run_arm", flaky)
        monkeypatch.setattr(ev, "REPEATS", 1)
        assert ev.run(tmp_path, "sonnet") == 0
        expected = 2 * len(ev.FIXTURE_CRITERIA)
        assert len(calls) == expected, (
            f"sweep stopped after {len(calls)} of {expected} arms — one bad arm "
            f"must not discard the rest"
        )
        first = json.loads((tmp_path / "DA-E1.with_skill.0.meta.json").read_text())
        assert first["ok"] is False


# ── Arm symmetry ──────────────────────────────────────────────────────────

class TestArmSymmetry:

    def test_both_arms_get_the_same_tools_and_model(self):
        src = inspect.getsource(ev.run_arm)
        assert src.count("--tools") == 1, "tools must be set once, for both arms"
        assert src.count("--model") == 1, "model must be set once, for both arms"
        assert src.count('"--max-turns"') == 1

    def test_only_the_prompt_and_cwd_differ(self):
        src = inspect.getsource(ev.run_arm)
        branch = src.split("if with_skill:")[1].split("cmd = [")[0]
        assert "prompt" in branch
        for flag in ("--tools", "--model", "--max-turns", "--permission-mode"):
            assert flag not in branch, (
                f"{flag} is set inside the with_skill branch — the arms would "
                f"differ by more than the skill"
            )

    def test_without_skill_arm_runs_outside_the_repo(self):
        src = inspect.getsource(ev.run)
        assert "mkdtemp" in src and "neutral" in src, (
            "the without-skill arm must run in a neutral cwd so its file tools "
            "cannot reach the skill"
        )

    def test_repeats_is_odd(self):
        assert ev.REPEATS % 2 == 1, "majority voting must not be able to tie"

    def test_min_wins_is_positive(self):
        assert ev.MIN_WINS >= 1, "a zero-win result must not be reportable as PASS"


# ── Grader ────────────────────────────────────────────────────────────────

def _write(d: pathlib.Path, fid: str, arm: str, rep: int, text: str, **meta):
    # Names built by string on purpose — Path.with_suffix would eat the ".0".
    stem = f"{fid}.{arm}.{rep}"
    (d / f"{stem}.txt").write_text(text, encoding="utf-8")
    payload = {"ok": True, "arm": arm, "fixture": fid, "repeat": rep,
               "skill_dir_touched": arm == "with_skill",
               "skill_was_read": arm == "with_skill"}
    payload.update(meta)
    (d / f"{stem}.meta.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_run(d, fid, arm, text, reps=None, **meta):
    """A complete arm: REPEATS identical results, as a real run would record."""
    for rep in range(ev.REPEATS if reps is None else reps):
        _write(d, fid, arm, rep, text, **meta)


def _answer(fid: str, good: bool) -> str:
    """Synthesise an answer that passes (or fails) every criterion of `fid`.

    Built from the harness's own self-test snippets, so these helpers cannot
    drift away from what the criteria actually check.
    """
    parts = []
    for name in ev.FIXTURE_CRITERIA[fid]:
        for cname, g, b in ev.SELF_TEST_CASES:
            if cname == name:
                parts.append(g if good else b)
                break
    return "\n\n".join(parts)


GOOD = ("govulncheck does not report a CVSS score; the Go vulnerability database "
        "does not publish severity. Look up the CVE alias in NVD and cite it.")
BAD = "govulncheck reports CVSS 7.5 for that finding, so treat it as High."


class TestSyntheticAnswers:
    """The helpers above must really pass/fail, or every grader test is vacuous."""

    @pytest.mark.parametrize("fid", sorted(ev.FIXTURE_CRITERIA))
    def test_good_answer_passes_all_criteria(self, fid):
        fx = next(f for f in ev.fixtures() if f["id"] == fid)
        g = ev.grade_answer(fx, _answer(fid, good=True))
        failed = [k for k, v in g.items() if not v["passed"]]
        assert not failed, f"{fid}: synthetic good answer failed {failed}"

    @pytest.mark.parametrize("fid", sorted(ev.FIXTURE_CRITERIA))
    def test_bad_answer_fails_all_criteria(self, fid):
        fx = next(f for f in ev.fixtures() if f["id"] == fid)
        g = ev.grade_answer(fx, _answer(fid, good=False))
        passed = [k for k, v in g.items() if v["passed"]]
        assert not passed, f"{fid}: synthetic bad answer passed {passed}"


class TestGrader:

    def test_empty_dir_is_inconclusive_not_pass(self, tmp_path):
        assert ev.grade_dir(tmp_path) == 3

    def test_missing_sidecar_is_inconclusive(self, tmp_path):
        (tmp_path / "DA-E1.with_skill.0.txt").write_text(GOOD, encoding="utf-8")
        (tmp_path / "DA-E1.without_skill.0.txt").write_text(BAD, encoding="utf-8")
        assert ev.grade_dir(tmp_path) == 3

    def test_recorded_filenames_are_discoverable_by_the_grader(self, tmp_path):
        """Regression: Path.with_suffix once ate the repeat index, so every
        recorded run was invisible and the grader reported INCOMPLETE forever."""
        _write(tmp_path, "DA-E1", "with_skill", 0, GOOD)
        found = ev._arm_files(tmp_path, "DA-E1", "with_skill")
        assert [f.name for f in found] == ["DA-E1.with_skill.0.txt"]

    def test_harness_error_is_inconclusive(self, tmp_path):
        _write_run(tmp_path, "DA-E1", "with_skill", GOOD, ok=False)
        _write_run(tmp_path, "DA-E1", "without_skill", BAD)
        assert ev.grade_dir(tmp_path) == 3

    def test_unread_skill_is_inconclusive(self, tmp_path):
        """A with-skill run that never opened SKILL.md is mislabelled data."""
        _write_run(tmp_path, "DA-E1", "with_skill", GOOD, skill_was_read=False)
        _write_run(tmp_path, "DA-E1", "without_skill", BAD)
        assert ev.grade_dir(tmp_path) == 3

    def test_touching_the_directory_is_not_reading_the_skill(self, tmp_path):
        """A Glob over the skill dir must not satisfy the read requirement."""
        _write_run(tmp_path, "DA-E1", "with_skill", GOOD,
                   skill_dir_touched=True, skill_was_read=False)
        _write_run(tmp_path, "DA-E1", "without_skill", BAD)
        assert ev.grade_dir(tmp_path) == 3

    def test_short_sample_is_inconclusive(self, tmp_path):
        """A 1-vs-2 majority vote is not a majority vote."""
        for fid in ev.FIXTURE_CRITERIA:
            _write_run(tmp_path, fid, "with_skill", _answer(fid, True), reps=1)
            _write_run(tmp_path, fid, "without_skill", _answer(fid, False), reps=2)
        assert ev.grade_dir(tmp_path) == 3

    def test_one_missing_arm_is_inconclusive(self, tmp_path):
        _write_run(tmp_path, "DA-E1", "with_skill", GOOD)
        assert ev.grade_dir(tmp_path) == 3

    def test_sweeping_win_passes(self, tmp_path):
        for fid in ev.FIXTURE_CRITERIA:
            _write_run(tmp_path, fid, "with_skill", _answer(fid, True))
            _write_run(tmp_path, fid, "without_skill", _answer(fid, False))
        assert ev.grade_dir(tmp_path) == 0

    def test_too_few_wins_is_inconclusive(self, tmp_path):
        """MIN_WINS fixtures must improve; ties are not evidence for the skill."""
        winners = sorted(ev.FIXTURE_CRITERIA)[:ev.MIN_WINS - 1]
        for fid in ev.FIXTURE_CRITERIA:
            good = _answer(fid, True)
            _write_run(tmp_path, fid, "with_skill", good)
            _write_run(tmp_path, fid, "without_skill",
                       _answer(fid, False) if fid in winners else good)
        assert ev.grade_dir(tmp_path) == 3

    def test_a_single_regression_fails_even_amid_wins(self, tmp_path):
        """MAX_LOSSES=0: one worse answer outweighs five better ones."""
        losers = sorted(ev.FIXTURE_CRITERIA)[:1]
        for fid in ev.FIXTURE_CRITERIA:
            better, worse = _answer(fid, True), _answer(fid, False)
            flip = fid in losers
            _write_run(tmp_path, fid, "with_skill", worse if flip else better)
            _write_run(tmp_path, fid, "without_skill", better if flip else worse)
        assert ev.grade_dir(tmp_path) == 1

    def test_all_ties_are_inconclusive_not_pass(self, tmp_path):
        for fid in ev.FIXTURE_CRITERIA:
            _write_run(tmp_path, fid, "with_skill", "nothing relevant here")
            _write_run(tmp_path, fid, "without_skill", "nothing relevant here")
        assert ev.grade_dir(tmp_path) == 3

    def test_partial_fixture_coverage_is_inconclusive(self, tmp_path):
        """Winning every graded fixture must not pass if some were not graded."""
        for fid in sorted(ev.FIXTURE_CRITERIA)[:ev.MIN_WINS]:
            _write_run(tmp_path, fid, "with_skill", _answer(fid, True))
            _write_run(tmp_path, fid, "without_skill", _answer(fid, False))
        assert ev.grade_dir(tmp_path) == 3


class TestPassBar:

    def test_min_wins_is_a_majority_of_fixtures(self):
        assert ev.MIN_WINS >= len(ev.FIXTURE_CRITERIA) // 2 + 1, (
            "a bar below a majority lets mostly-ties read as success"
        )

    def test_no_losses_tolerated(self):
        assert ev.MAX_LOSSES == 0

    def test_exact_repeats_enforced(self):
        assert ev.REQUIRE_EXACT_REPEATS is True

    def test_repeats_is_odd(self):
        assert ev.REPEATS % 2 == 1


# ── The orchestrator itself ───────────────────────────────────────────────

class TestEntryPoint:
    """Leaf tests passing while main() is broken is a known way to ship a bug."""

    def test_help_runs(self):
        proc = subprocess.run([sys.executable, str(HARNESS), "--help"],
                              capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr
        for flag in ("--self-test", "--run", "--grade", "--model"):
            assert flag in proc.stdout, f"{flag} missing from --help"

    def test_self_test_via_cli(self):
        proc = subprocess.run([sys.executable, str(HARNESS), "--self-test"],
                              capture_output=True, text=True, timeout=120)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "0 failures" in proc.stdout

    def test_no_args_is_usage_error(self):
        proc = subprocess.run([sys.executable, str(HARNESS)],
                              capture_output=True, text=True, timeout=60)
        assert proc.returncode == 2, "a bare invocation must not look like success"

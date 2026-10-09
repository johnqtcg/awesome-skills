#!/usr/bin/env python3
"""Skill-output evaluation for the e2e-test skill.

This closes the layer the other suites do not reach. `test_skill_contract.py` asserts
the skill *contains* its rules; `test_golden_scenarios.py` asserts the fixtures describe
the right answers; `lint_e2e_spec.py` grades spec source that someone hands it. None of
them grades **a response to a task** — which is the artifact the skill actually
produces.

The grader here is deterministic and offline. It takes a response in Markdown and:

  1. extracts every TypeScript/JavaScript block and runs the skill's own linter over it,
     treating any CRITICAL finding as a defect;
  2. checks the fixture's `requires` patterns — the decisions the answer must make;
  3. checks the fixture's `forbids` patterns — the plausible wrong answers.

A fixture passes only when all three are clean. Two exemplars ship per fixture and the
suite asserts they land on opposite verdicts, so a grader that has stopped
discriminating fails here rather than reporting everything green.

`E2E_LLM_EVAL=1` additionally runs the fixtures against a live model; without it the
offline exemplar grading is what runs, and that is the part CI depends on.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parent.parent
EVAL_DIR = TESTS_DIR / "llm_eval"

CODE_LANGS = {"ts", "typescript", "tsx", "js", "javascript", "jsx"}


def _load_script(stem: str, alias: str):
    """Import scripts/<stem>.py by path.

    Registered in sys.modules *before* exec_module: the scripts use
    `from __future__ import annotations`, so @dataclass resolves its field types via
    sys.modules[cls.__module__] and raises AttributeError on None when it is absent.
    """
    import importlib.util
    import sys

    path = SKILL_DIR / "scripts" / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(alias, path)
    assert spec and spec.loader, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return module


def load_linter(alias: str):
    return _load_script("lint_e2e_spec", alias)


# One CommonMark-aware fence parser for the whole skill: the real-Playwright example
# loader owns it, and this grader and its tests use the same function.
code_blocks = _load_script("verify_examples_load", "verify_examples_load_llm_eval").code_blocks


def grade(response: str, meta: dict, linter) -> list[str]:
    """Return a list of defect strings. Empty means PASS."""
    defects: list[str] = []

    for line, lang, body in code_blocks(response):
        if lang not in CODE_LANGS:
            continue
        for f in linter.lint_source(body):
            if f.severity == "CRITICAL":
                defects.append(f"linter {f.rule} at response line ~{line + f.line}: {f.message}")

    for req in meta.get("requires", []):
        if not re.search(req["pattern"], response):
            defects.append(f"missing [{req['id']}] — {req['why']}")

    for bad in meta.get("forbids", []):
        m = re.search(bad["pattern"], response)
        if m:
            defects.append(f"forbidden [{bad['id']}] matched {m.group(0)!r} — {bad['why']}")

    return defects


def fixture_dirs() -> list[Path]:
    return sorted(p for p in EVAL_DIR.iterdir() if p.is_dir() and (p / "meta.json").exists())


def load_fixture(d: Path) -> dict:
    meta = json.loads((d / "meta.json").read_text())
    meta["_dir"] = d
    meta["_name"] = d.name
    return meta


class FixtureShapeTests(unittest.TestCase):
    """A fixture that is missing a field fails silently as 'nothing to check'."""

    def test_fixtures_exist(self) -> None:
        self.assertGreaterEqual(len(fixture_dirs()), 3,
                                "the eval layer needs fixtures to be an eval layer")

    def test_every_fixture_is_complete(self) -> None:
        for d in fixture_dirs():
            with self.subTest(fixture=d.name):
                meta = load_fixture(d)
                for field in ("title", "prompt", "why_this_fixture", "requires", "forbids"):
                    self.assertIn(field, meta, f"{d.name}/meta.json has no {field}")
                self.assertTrue(meta["requires"], "a fixture with no requirements grades nothing")
                self.assertTrue(meta["forbids"], "a fixture with no forbidden shape grades nothing")
                for pattern_set in ("requires", "forbids"):
                    for entry in meta[pattern_set]:
                        self.assertEqual({"id", "pattern", "why"}, set(entry),
                                         f"{d.name} {pattern_set} entry must carry id/pattern/why")
                        re.compile(entry["pattern"])  # raises on a broken pattern
                for name in ("good.md", "bad.md"):
                    self.assertTrue((d / name).exists(), f"{d.name} has no {name}")


class ExemplarGradingTests(unittest.TestCase):
    """The offline half: known-good and known-bad responses must land apart."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.linter = load_linter("lint_e2e_spec_llmeval")

    def test_good_exemplars_pass(self) -> None:
        for d in fixture_dirs():
            with self.subTest(fixture=d.name):
                meta = load_fixture(d)
                defects = grade((d / "good.md").read_text(), meta, self.linter)
                self.assertEqual([], defects,
                                 f"{d.name}/good.md should be clean:\n  " + "\n  ".join(defects))

    def test_bad_exemplars_fail(self) -> None:
        for d in fixture_dirs():
            with self.subTest(fixture=d.name):
                meta = load_fixture(d)
                defects = grade((d / "bad.md").read_text(), meta, self.linter)
                self.assertNotEqual([], defects, f"{d.name}/bad.md graded clean")

    def test_every_fixture_discriminates_on_more_than_one_axis(self) -> None:
        """A fixture whose bad exemplar trips exactly one check is one edit away from
        grading nothing. Require at least two independent defects."""
        for d in fixture_dirs():
            with self.subTest(fixture=d.name):
                meta = load_fixture(d)
                defects = grade((d / "bad.md").read_text(), meta, self.linter)
                self.assertGreaterEqual(len(defects), 2,
                                        f"{d.name}/bad.md trips only: {defects}")

    def test_all_three_check_families_earn_their_place(self) -> None:
        """Asserted across the corpus rather than per fixture: a refusal fixture may
        legitimately have no code to lint. But if a whole family never fires on any bad
        exemplar, that family is decoration — it would keep passing if deleted."""
        fired = set()
        for d in fixture_dirs():
            meta = load_fixture(d)
            for defect in grade((d / "bad.md").read_text(), meta, self.linter):
                fired.add(defect.split(" ")[0])
        self.assertEqual({"linter", "missing", "forbidden"}, fired,
                         f"a check family never fires on any bad exemplar: {fired}")


class GraderSelfTests(unittest.TestCase):
    """The grader is the thing everything else here trusts. Probe it directly with
    synthetic input rather than assuming the exemplars exercise it."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.linter = load_linter("lint_e2e_spec_llmeval_self")

    META = {
        "requires": [{"id": "r", "pattern": "REQUIRED_TOKEN", "why": "test"}],
        "forbids": [{"id": "f", "pattern": "FORBIDDEN_TOKEN", "why": "test"}],
    }

    def test_missing_requirement_is_a_defect(self) -> None:
        self.assertEqual(1, len(grade("nothing here", self.META, self.linter)))

    def test_present_requirement_is_clean(self) -> None:
        self.assertEqual([], grade("REQUIRED_TOKEN", self.META, self.linter))

    def test_forbidden_token_is_a_defect(self) -> None:
        d = grade("REQUIRED_TOKEN and FORBIDDEN_TOKEN", self.META, self.linter)
        self.assertEqual(1, len(d))
        self.assertIn("forbidden [f]", d[0])

    def test_critical_linter_finding_in_a_ts_block_is_a_defect(self) -> None:
        response = "REQUIRED_TOKEN\n\n```ts\nawait page.waitForTimeout(3000);\n```\n"
        d = grade(response, self.META, self.linter)
        self.assertTrue(any("linter" in x for x in d), d)

    def test_prose_outside_a_code_block_is_not_linted(self) -> None:
        """The linter grades spec source. Quoting a forbidden call while explaining why
        it is wrong must not be scored as writing it."""
        response = "REQUIRED_TOKEN — never call page.waitForTimeout(3000) to fix a race.\n"
        self.assertEqual([], grade(response, self.META, self.linter))

    def test_a_non_code_fence_is_not_linted(self) -> None:
        response = "REQUIRED_TOKEN\n\n```text\nawait page.waitForTimeout(3000);\n```\n"
        self.assertEqual([], grade(response, self.META, self.linter))

    def test_nested_fence_does_not_split_a_block(self) -> None:
        """A ```` ```ts ```` line inside an open block is content. A non-greedy
        regex reads it as a new opener and mis-slices every later block."""
        md = "```text\nexample:\n```ts\nconst a = 1;\n```\n"
        blocks = code_blocks(md)
        self.assertEqual(1, len(blocks), blocks)
        self.assertEqual("text", blocks[0][1])
        self.assertIn("```ts", blocks[0][2], "the inner fence is content, not a boundary")

    def test_block_extraction_reports_language_and_line(self) -> None:
        md = "intro\n\n```ts\nconst a = 1;\n```\n"
        blocks = code_blocks(md)
        self.assertEqual([(3, "ts", "const a = 1;")], blocks)


RUN_CONTEXT = (
    "Run context: this is a single-turn, non-interactive evaluation. You have no tools, "
    "no shell and no access to the repository; everything known about it is stated in "
    "the task. Do not attempt tool calls. Wherever the skill says to run or inspect "
    "something, use the stated facts, report the step as not run, and give the exact "
    "command the user should run. Answer the task completely in this one response."
)


def live_prompt(skill_md: str, task: str) -> str:
    """The skill, the run context, and the task.

    The run context is stated because the skill's own first steps are "run the discovery
    script" and "inspect the repository". Without it a tool-less model emits a pseudo
    tool call and stops — measured: an 88-character response ending in "**Tool: bash**",
    graded as missing every required item. That grades the harness, not the skill.
    """
    return ("You are following this skill. Obey it exactly.\n\n"
            "<skill>\n" + skill_md + "\n</skill>\n\n"
            + RUN_CONTEXT + "\n\nTask:\n" + task)


def live_command(prompt: str) -> list[str]:
    """The nested model call, isolated from the session that launches it.

    A bare `claude -p` inherits the parent's permission mode, MCP servers, working
    directory and CLAUDE.md, and has tools: it explores whatever repository it lands in
    instead of answering the task, so the run measures the harness. The skill is
    inlined in the prompt, so the model needs no tools at all.

    `--strict-mcp-config` is not enough on its own. User-level plugin hooks still run
    and inject the parent session's context: measured on CLI 2.1.283, the child quoted
    the launching session's own in-flight command and refused to "run" it before
    answering. `--setting-sources local` from a temp directory loads no user settings,
    so no plugins or hooks. (`--bare` also skips hooks, but reads only an API key —
    never OAuth — so it cannot authenticate a subscription login.)
    """
    return ["claude", "-p", "--model", os.environ.get("E2E_LLM_MODEL", "sonnet"),
            "--tools", "", "--permission-mode", "dontAsk", "--strict-mcp-config",
            "--setting-sources", "local", "--max-turns", "3", prompt]


class LiveCommandIsolationTests(unittest.TestCase):
    """Offline: the live arm's isolation is part of what it measures, so pin it."""

    def test_nested_call_is_isolated(self) -> None:
        cmd = live_command("PROMPT")
        joined = " ".join(cmd)
        for flag in ('--tools', '--permission-mode dontAsk', '--strict-mcp-config',
                     '--setting-sources local', '--max-turns'):
            with self.subTest(flag=flag):
                self.assertIn(flag, joined)
        self.assertEqual("", cmd[cmd.index("--tools") + 1], "the model must answer without tools")
        self.assertEqual("PROMPT", cmd[-1])

    def test_prompt_states_the_tool_less_run_context(self) -> None:
        prompt = live_prompt("SKILL BODY", "TASK BODY")
        self.assertIn("<skill>\nSKILL BODY\n</skill>", prompt)
        self.assertIn("no tools", prompt)
        self.assertLess(prompt.index("Run context"), prompt.index("TASK BODY"))


class LiveSkillEval(unittest.TestCase):
    """Opt-in: run the real skill against each prompt and grade what comes back.

    Off by default — it needs a model, costs money, and is not deterministic. The
    offline exemplar grading above is what CI relies on.

        E2E_LLM_EVAL=1 python3 -m pytest scripts/tests/test_llm_skill_eval.py -k Live
    """

    @classmethod
    def setUpClass(cls) -> None:
        if os.environ.get("E2E_LLM_EVAL") != "1":
            raise unittest.SkipTest("set E2E_LLM_EVAL=1 to run the live evaluation")
        cls.linter = load_linter("lint_e2e_spec_llmeval_live")

    def test_live_responses_pass_the_grader(self) -> None:
        skill_md = (SKILL_DIR / "SKILL.md").read_text()
        for d in fixture_dirs():
            with self.subTest(fixture=d.name):
                meta = load_fixture(d)
                proc = subprocess.run(
                    live_command(live_prompt(skill_md, meta["prompt"])),
                    capture_output=True, text=True, timeout=900,
                    cwd=tempfile.gettempdir(),
                )
                self.assertEqual(0, proc.returncode,
                                 f"model invocation failed: {proc.stderr[:400]}")
                # exit 0 with this text is an infrastructure failure, never a graded answer
                self.assertNotIn("Not logged in", proc.stdout[:200],
                                 "nested claude could not authenticate — run unsandboxed; NOT a result")
                defects = grade(proc.stdout, meta, self.linter)
                self.assertEqual([], defects,
                                 f"{d.name} live response defects:\n  " + "\n  ".join(defects))


if __name__ == "__main__":
    unittest.main()

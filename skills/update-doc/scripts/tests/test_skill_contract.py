"""Contract tests for the update-doc skill.

These check enforceable properties, not vocabulary. A test here should fail when
the skill would behave wrongly — an ungranted command it tells the agent to run,
an evidence command whose regex silently matches nothing, a reference file that
no longer exists, or an output-mode rule that two branches can both satisfy.
"""

import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
REFERENCES_DIR = SKILL_DIR / "references"
SCRIPTS_DIR = SKILL_DIR / "scripts"
DISCOVER = SCRIPTS_DIR / "discover_doc_scope.sh"
RUNNER = SCRIPTS_DIR / "run_regression.sh"
VALIDATOR = SCRIPTS_DIR / "validate_frontmatter.py"

QUICK_VALIDATE = Path(
    os.environ.get(
        "SKILL_CREATOR_VALIDATOR",
        Path.home() / ".codex/skills/.system/skill-creator/scripts/quick_validate.py",
    )
)

# Binaries the skill instructs the agent to invoke. Anything here must carry a
# matching Bash() grant in the frontmatter.
TRACKED_BINARIES = {"git", "rg", "ls", "head", "grep", "bash"}

# Granted but not shown in a command block, with the reason. Keeps grant creep
# visible instead of letting unused permissions accumulate silently.
JUSTIFIED_UNUSED_GRANTS = {
    "git log": "codemap 'Last updated' date is derived from commit history",
}

# Files whose command blocks are recommendations for the *user's* repository
# rather than commands this skill runs, so they are exempt from grant checking.
RECOMMENDATION_ONLY = {"ci-drift.md"}


def read(path):
    return path.read_text(encoding="utf-8")


def frontmatter(text):
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError("missing yaml frontmatter")
    return match.group(1)


def fenced_blocks(text, lang="bash"):
    return re.findall(rf"```{lang}\n(.*?)```", text, re.DOTALL)


def grant_covers(grant, cmd):
    """Does an `allowed-tools` Bash rule cover an instructed command?

    `grant` is the inside of `Bash(...)`, e.g. `git diff*`, `rg *`, or
    `bash ${CLAUDE_SKILL_DIR}/scripts/discover_doc_scope.sh *`.
    `cmd` is a normalized head: `rg`, `bash`, or `git diff`.
    """
    gtok = grant.replace("*", " ").split()
    ctok = cmd.split()
    if not gtok or not ctok or gtok[0] != ctok[0]:
        return False
    # `git` grants are per-subcommand: `Bash(git diff*)` must not cover `git push`.
    if ctok[0] == "git":
        return len(gtok) > 1 and len(ctok) > 1 and gtok[1] == ctok[1]
    return True


def command_heads(block_text):
    """Extract external-binary invocations from a shell block.

    Strips shell keywords, pipes, and conditionals so that
    `elif [ -f pom.xml ]; then grep -A2 ... | head -40` yields {grep, head}.
    """
    heads = set()
    for raw in block_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        for segment in re.split(r"\|\||&&|\||;", line):
            tokens = segment.split()
            while tokens and tokens[0] in {
                "if", "elif", "then", "else", "fi", "for", "do", "done",
                "while", "case", "esac", "!",
            }:
                tokens.pop(0)
            if not tokens:
                continue
            head = tokens[0]
            if head in TRACKED_BINARIES:
                if head == "git" and len(tokens) > 1:
                    heads.add(f"git {tokens[1]}")
                else:
                    heads.add(head)
    return heads


class TestFrontmatter(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILL_MD)
        self.fm = frontmatter(self.text)

    def test_name_and_description(self):
        self.assertIn("name: update-doc", self.fm)
        self.assertIn("Keep repository documentation synchronized", self.fm)

    def test_edit_tool_granted(self):
        """`Edit` is required by the 'prefer minimal patches' hard rule.

        Without it the only way to change a document is a whole-file Write,
        which contradicts the skill's own diff-scoped contract.
        """
        grants = re.search(r"^allowed-tools:\s*(.+)$", self.fm, re.MULTILINE)
        self.assertIsNotNone(grants, "allowed-tools is required")
        tools = [t.strip() for t in re.split(r",\s*(?![^()]*\))", grants.group(1))]
        self.assertIn("Edit", tools)
        for required in ("Read", "Write", "Grep", "Glob"):
            self.assertIn(required, tools)

    def test_every_instructed_command_is_granted(self):
        """Forward check for the tool-grant contract.

        Collects the binaries the skill tells the agent to run — from fenced
        blocks and from inline code in prose/tables — and asserts each one has a
        Bash() grant.
        """
        grants = re.search(r"^allowed-tools:\s*(.+)$", self.fm, re.MULTILINE).group(1)
        granted = set(re.findall(r"Bash\(([^)]+)\)", grants))

        instructed = set()
        sources = [SKILL_MD] + [
            p for p in sorted(REFERENCES_DIR.glob("*.md"))
            if p.name not in RECOMMENDATION_ONLY
        ]
        for path in sources:
            body = read(path)
            if path == SKILL_MD:
                body = body[len(frontmatter(body)) + 8:]
            for block in fenced_blocks(body):
                instructed |= command_heads(block)
            for span in re.findall(r"`([^`\n]+)`", body):
                instructed |= command_heads(span)

        missing = [
            cmd for cmd in sorted(instructed)
            if not any(grant_covers(g, cmd) for g in granted)
        ]
        self.assertFalse(
            missing,
            f"commands instructed by the skill but not granted: {missing}",
        )

    def test_no_unjustified_grants(self):
        """Reverse check: a grant must be used or explicitly justified."""
        grants = re.search(r"^allowed-tools:\s*(.+)$", self.fm, re.MULTILINE).group(1)
        granted = [g.strip() for g in re.findall(r"Bash\(([^)]+)\)", grants)]

        corpus = read(SKILL_MD) + "".join(
            read(p) for p in sorted(REFERENCES_DIR.glob("*.md"))
        )
        unused = []
        for grant in granted:
            prefix = grant.split("*")[0].strip()
            if not prefix:
                continue
            if prefix in JUSTIFIED_UNUSED_GRANTS:
                continue
            if prefix not in corpus:
                unused.append(grant)
        self.assertFalse(unused, f"granted but never instructed: {unused}")


class TestEvidenceCommandCorrectness(unittest.TestCase):
    """Guards for command forms that fail silently rather than erroring.

    Scoped to fenced shell blocks. Prose is allowed — and required — to quote a
    broken form when explaining why it is broken; only a form the agent would
    actually execute is a defect.
    """

    def _executable_lines(self):
        """Yield (label, line) for every line inside a fenced shell block."""
        for path in [SKILL_MD] + sorted(REFERENCES_DIR.glob("*.md")):
            body = read(path)
            for block in fenced_blocks(body):
                offset = body[: body.index(block)].count("\n") + 1
                for num, line in enumerate(block.splitlines(), offset):
                    yield f"{path.name}:{num}", line

    def test_no_escaped_alternation_in_rg_patterns(self):
        r"""`rg` uses Rust regex: `\|` is a literal pipe, not alternation.

        A pattern like `rg "app\.listen\|createServer"` matches nothing and
        exits 1, so evidence gathering silently returns empty and the document
        is written from no evidence at all.
        """
        offenders = []
        for label, line in self._executable_lines():
            if not re.search(r"\brg\b", line):
                continue
            for pattern in re.findall(r"""["']([^"']*)["']""", line):
                if r"\|" in pattern:
                    offenders.append(f"{label}: {line.strip()}")
        self.assertFalse(
            offenders, "escaped alternation in rg pattern (matches nothing):\n"
            + "\n".join(offenders)
        )

    def test_no_pipe_head_or_fallback(self):
        """`cmd_a | head -N || cmd_b` never runs cmd_b.

        `||` binds to `head`, which exits 0 even when cmd_a produced nothing, so
        the manifest fallback is dead code.
        """
        offenders = [
            f"{label}: {line.strip()}"
            for label, line in self._executable_lines()
            if re.search(r"\|\s*head\b[^|]*\|\|", line)
        ]
        self.assertFalse(
            offenders, "`| head ... ||` fallback is unreachable:\n" + "\n".join(offenders)
        )

    def test_no_contradictory_rg_flags(self):
        offenders = [
            f"{label}: {line.strip()}"
            for label, line in self._executable_lines()
            if re.search(r"\brg\b.*(-n\b.*\s-l\b|-l\b.*\s-n\b)", line)
        ]
        self.assertFalse(offenders, f"rg -n with -l is contradictory: {offenders}")

    def test_guards_actually_detect_the_defects(self):
        """Grade the graders.

        A guard scoped to fenced blocks could be scoped to nothing at all and
        still report a clean run. Assert each pattern fires on a known-bad line.
        """
        bad_rg = """rg -n "app\\.listen\\|createServer" --glob '*.ts'"""
        self.assertTrue(
            any(r"\|" in p for p in re.findall(r"""["']([^"']*)["']""", bad_rg))
        )
        self.assertTrue(
            re.search(r"\|\s*head\b[^|]*\|\|", "cat pom.xml | head -40 || cat build.gradle")
        )
        self.assertTrue(re.search(r"\brg\b.*-n\b.*\s-l\b", "rg -n foo -l"))
        self.assertGreater(
            len(list(self._executable_lines())), 40,
            "guards are scanning almost nothing; scoping is broken",
        )

    def test_regex_pitfalls_are_documented(self):
        body = read(REFERENCES_DIR / "evidence-commands.md")
        self.assertIn("literal pipe", body)
        self.assertIn("does **not** mean", body)


class TestReferenceIntegrity(unittest.TestCase):
    def test_every_reference_on_disk_is_linked(self):
        body = read(SKILL_MD)
        orphans = [
            p.name for p in sorted(REFERENCES_DIR.glob("*.md"))
            if f"references/{p.name}" not in body
        ]
        self.assertFalse(orphans, f"reference files never loaded by SKILL.md: {orphans}")

    def test_every_referenced_path_exists(self):
        """Catches a reference deleted without updating SKILL.md."""
        body = read(SKILL_MD)
        missing = [
            rel for rel in set(re.findall(r"`((?:references|scripts)/[^`]+?)`", body))
            if not (SKILL_DIR / rel).exists()
        ]
        self.assertFalse(missing, f"SKILL.md points at missing paths: {missing}")

    def test_reference_count(self):
        refs = sorted(p.name for p in REFERENCES_DIR.glob("*.md"))
        self.assertEqual(
            refs,
            [
                "ci-drift.md",
                "evidence-commands.md",
                "project-routing.md",
                "update-doc.md",
            ],
        )

    def test_progressive_disclosure_is_real(self):
        """The main file must not carry the bulk that references exist to hold."""
        skill_lines = len(read(SKILL_MD).splitlines())
        ref_lines = sum(
            len(read(p).splitlines()) for p in REFERENCES_DIR.glob("*.md")
        )
        # 460 sits under this repository's ~500-line SKILL.md convention with
        # headroom, and still trips well before the file could creep back to the
        # 481 lines it held when the per-language command blocks lived inline.
        self.assertLess(skill_lines, 460, "SKILL.md is growing back into a monolith")
        self.assertGreater(
            ref_lines, skill_lines * 0.6,
            "references are too thin relative to SKILL.md to be real disclosure",
        )


class TestStructure(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILL_MD)
        self.headings = [
            (len(m.group(1)), m.group(2).strip())
            for m in re.finditer(r"^(#{2,4})\s+(.+)$", self.text, re.MULTILINE)
        ]

    def test_project_types_nest_under_project_type_guidance(self):
        """Regression: `README UX Rules` used to sit between the CLI and Monorepo
        subsections, orphaning Monorepo out of its parent section."""
        owner = None
        found = {}
        for level, title in self.headings:
            if level == 2:
                owner = title
            elif level == 3 and title in {
                "Service / Backend", "Library / SDK", "CLI Tool", "Monorepo"
            }:
                found[title] = owner
        self.assertEqual(len(found), 4, f"missing project-type subsections: {found}")
        for title, parent in found.items():
            self.assertEqual(
                parent, "Project-Type Guidance",
                f"'{title}' is nested under '{parent}', not Project-Type Guidance",
            )

    def test_required_sections_present(self):
        required = [
            "Hard Rules",
            "Pre-Update Gates",
            "Scope Discovery",
            "Command Source Resolution",
            "Output Mode Routing",
            "Standard Workflow",
            "Project-Type Guidance",
            "README UX Rules",
            "Quality Scorecard",
            "Output Format",
            "Self-Validation",
        ]
        titles = [t for _, t in self.headings]
        missing = [r for r in required if not any(r in t for t in titles)]
        self.assertFalse(missing, f"missing sections: {missing}")


class TestDiffScopeGate(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILL_MD)

    def test_all_four_diff_sources_documented(self):
        for command in (
            "git diff --name-only",
            "git diff --cached --name-only",
            "git ls-files --others --exclude-standard",
            "git diff --name-only <base>...HEAD",
        ):
            self.assertIn(command, self.text, f"diff source missing: {command}")

    def test_bare_git_diff_is_called_out_as_insufficient(self):
        self.assertRegex(self.text, r"not sufficient scope")

    def test_degraded_paths_named(self):
        for token in ("DEGRADED_NO_GIT", "NOT_RESOLVED", "=== END ===", "NEW_SOURCE"):
            self.assertIn(token, self.text, f"discovery contract token missing: {token}")


class TestOutputModeRouting(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILL_MD)
        match = re.search(
            r"^## Output Mode Routing\n(.*?)^## ", self.text, re.DOTALL | re.MULTILINE
        )
        self.assertIsNotNone(match, "Output Mode Routing section not found")
        self.section = match.group(1)

    def test_precedence_is_explicit(self):
        """Regression for the ambiguity: lightweight (any 2) and full (any 1)
        could both fire on the same change with no tiebreak."""
        self.assertIn("first rule that fires wins", self.section)
        self.assertIn("Never downgrade", self.section)

    def test_lightweight_requires_all_conditions(self):
        lightweight = re.search(
            r"### Rule 2 — Lightweight mode\n(.*?)###", self.section, re.DOTALL
        )
        self.assertIsNotNone(lightweight)
        self.assertIn("**all**", lightweight.group(1))
        self.assertNotIn("any 2", lightweight.group(1))

    def test_full_mode_lists_escalation_triggers(self):
        full = re.search(
            r"### Rule 1 — Full mode.*?\n(.*?)###", self.section, re.DOTALL
        )
        self.assertIsNotNone(full)
        self.assertIn("**any**", full.group(1))
        self.assertIn("new API surface", full.group(1))

    def test_any_two_formulation_is_gone(self):
        self.assertNotIn("Trigger conditions (any 2)", self.text)


class TestScorecard(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILL_MD)
        match = re.search(
            r"^## Quality Scorecard.*?\n(.*?)^## ", self.text, re.DOTALL | re.MULTILINE
        )
        self.assertIsNotNone(match)
        self.section = match.group(1)

    def test_exactly_twelve_checks(self):
        items = re.findall(r"^(\d+)\.\s+\S", self.section, re.MULTILINE)
        self.assertEqual([str(i) for i in range(1, 13)], items)

    def test_denominator_is_consistent(self):
        denominators = set(re.findall(r"/(\d+)\b", self.text))
        stray = {d for d in denominators if d != "12"}
        self.assertFalse(stray, f"scorecard denominator drift: /{stray}")

    def test_na_semantics_defined(self):
        """An N/A that silently shrinks the denominator inflates the score."""
        self.assertIn("does not reduce the denominator", self.section)

    def test_command_source_check_points_at_its_procedure(self):
        """Regression: check 7 used to grade a rule the skill never taught."""
        self.assertIn("Command Source Resolution", self.section)


class TestCommandSourceResolution(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILL_MD)

    def test_all_priority_levels_defined(self):
        section = re.search(
            r"### 4\) Command Source Resolution\n(.*?)^### ",
            self.text, re.DOTALL | re.MULTILINE,
        )
        self.assertIsNotNone(section)
        body = section.group(1)
        for source in ("Makefile", "Taskfile", "justfile", "package.json", "CI workflow"):
            self.assertIn(source, body, f"command source missing: {source}")
        rows = re.findall(r"^\|\s*(\d+)\s*\|", body, re.MULTILINE)
        self.assertEqual(rows, ["1", "2", "3", "4", "5"], "priority ladder is not 1..5")

    def test_no_primary_sourced_commands_anywhere(self):
        """Examples steer behaviour as strongly as rules.

        The gate says "Read RESOLVED:, not PRIMARY:", but the workflow step and
        both output examples used to source commands from PRIMARY, which would
        undo the rule. PRIMARY may only appear where it is being explained or
        explicitly demoted.
        """
        allowed_context = (
            "Read `RESOLVED:`, not `PRIMARY:`",
            "`PRIMARY:` names the repo's dominant wrapper",
            "still makes `PRIMARY: makefile`",
            "PRIMARY: makefile",
            "`PRIMARY` is a repo-level summary only",
        )
        offenders = []
        for num, line in enumerate(self.text.splitlines(), 1):
            if "PRIMARY" not in line:
                continue
            if any(ok in line for ok in allowed_context):
                continue
            offenders.append(f"{num}: {line.strip()}")
        self.assertFalse(
            offenders, "PRIMARY used as a command source outside its explanation:\n"
            + "\n".join(offenders)
        )

    def test_no_guessing_clause(self):
        self.assertIn("Do not fill the gap with a conventional default", self.text)

    def test_directs_reader_to_command_level_not_repo_level(self):
        """Regression: `PRIMARY` is a repo-level answer.

        A Makefile with only a `lint` target still yields `PRIMARY: makefile`,
        so a document written from PRIMARY prints `make build` for a target that
        does not exist. The gate must send the reader to `RESOLVED:`.
        """
        section = re.search(
            r"### 4\) Command Source Resolution\n(.*?)^### ",
            self.text, re.DOTALL | re.MULTILINE,
        ).group(1)
        self.assertIn("RESOLVED:", section)
        self.assertRegex(section, r"Read `RESOLVED:`, not `PRIMARY:`")
        self.assertIn("MODULES:", section, "workspace per-module reading must be named")
        self.assertIn("NOT_FOUND", section)


class TestDiscoveryScript(unittest.TestCase):
    def setUp(self):
        self.body = read(DISCOVER)

    def test_exists_and_executable(self):
        self.assertTrue(DISCOVER.exists())
        self.assertTrue(DISCOVER.stat().st_mode & 0o111, "script is not executable")
        self.assertTrue(self.body.startswith("#!/usr/bin/env bash"))

    def test_does_not_use_errexit(self):
        """`set -e` would abort on the first empty probe.

        Every probe in this script legitimately returns empty on some repository
        shape; aborting there would produce no report at all instead of a report
        saying 'no Makefile'.
        """
        self.assertFalse(
            re.search(r"^set\s+-[a-z]*e", self.body, re.MULTILINE),
            "discovery script must not use errexit",
        )
        self.assertIn("set -uo pipefail", self.body)

    def test_emits_end_sentinel(self):
        self.assertIn('echo "=== END ==="', self.body)

    def test_covers_four_diff_sources(self):
        for command in (
            "git diff --name-only",
            "git diff --cached --name-only",
            "git ls-files --others --exclude-standard",
            "...HEAD",
            "--diff-filter=A",
        ):
            self.assertIn(command, self.body)

    def test_reports_every_contract_field(self):
        for field in (
            "STATUS:", "BASE_REF:", "TOTAL_UNIQUE:", "NEW_SOURCE:", "DOMINANT:",
            "POLYGLOT:", "PRIMARY:", "RESOLVED:", "MODULES:", "LIKELY:", "SCORES:",
            "CODEMAPS:", "DOC_CI:", "NOT_FOUND",
        ):
            self.assertIn(field, self.body, f"report field missing: {field}")


class TestRegressionRunner(unittest.TestCase):
    def test_runner_discovers_tests_rather_than_hardcoding(self):
        """A hardcoded file list silently stops running a test that gets added."""
        body = read(RUNNER)
        test_files = sorted(p.name for p in (SCRIPTS_DIR / "tests").glob("test_*.py"))
        self.assertGreaterEqual(len(test_files), 3)
        uses_discovery = "discover" in body or "test_*.py" in body
        self.assertTrue(
            uses_discovery,
            "run_regression.sh must discover test files, not hardcode them",
        )

    def test_runner_validates_the_shipped_file_not_a_copy(self):
        """No validation laundering.

        Validating a rewritten copy proves a file nobody ships is valid. The
        runner must point the validator at the real skill directory, and must
        not mutate SKILL.md on the way there.
        """
        body = read(RUNNER)
        self.assertIn("validate_frontmatter.py", body)
        self.assertRegex(
            body,
            r'validate_frontmatter\.py"?\s+"?\$\{SKILL_DIR\}',
            "validator must be pointed at the real skill directory",
        )
        for laundering in (
            "grep -v '^disable-model-invocation:'",
            "update-doc-validate",
        ):
            self.assertNotIn(
                laundering, body, f"frontmatter is being rewritten before validation: {laundering}"
            )


def run_validator(script, skill_dir):
    return subprocess.run(
        [sys.executable, str(script), str(skill_dir)],
        capture_output=True,
        text=True,
    )


def skill_dir_with(frontmatter_text, body="\n# Body\n"):
    """Materialize a throwaway skill directory holding the given frontmatter."""
    tmp = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR") or None)
    (Path(tmp.name) / "SKILL.md").write_text(frontmatter_text + body, encoding="utf-8")
    return tmp


# Frontmatter that must be rejected. Each case is one rule quick_validate
# enforces; the bundled validator has to reject every one of them too, otherwise
# replacing quick_validate would have weakened validation rather than fixing it.
INVALID_FRONTMATTER = {
    "no_frontmatter": "just text\n",
    "unterminated": "---\nname: x\n",
    "not_a_mapping": "---\n- a\n- b\n---\n",
    "invalid_yaml": "---\nname: x\ndescription: a: b: c\n\tbad\n---\n",
    "missing_name": "---\ndescription: something\n---\n",
    "missing_description": "---\nname: valid-name\n---\n",
    "name_uppercase": "---\nname: NotHyphenCase\ndescription: d\n---\n",
    "name_underscore": "---\nname: bad_name\ndescription: d\n---\n",
    "name_leading_hyphen": "---\nname: -bad\ndescription: d\n---\n",
    "name_trailing_hyphen": "---\nname: bad-\ndescription: d\n---\n",
    "name_double_hyphen": "---\nname: bad--name\ndescription: d\n---\n",
    "name_too_long": "---\nname: " + "a" * 65 + "\ndescription: d\n---\n",
    "name_not_string": "---\nname: 123\ndescription: d\n---\n",
    "description_angle_brackets": "---\nname: ok-name\ndescription: use <this>\n---\n",
    "description_too_long": "---\nname: ok-name\ndescription: " + "d" * 1025 + "\n---\n",
    "unknown_key": "---\nname: ok-name\ndescription: d\ntotally-made-up: 1\n---\n",
}

VALID_FRONTMATTER = {
    "minimal": "---\nname: ok-name\ndescription: d\n---\n",
    "disable_model_invocation": (
        "---\nname: ok-name\ndescription: d\ndisable-model-invocation: true\n---\n"
    ),
    "allowed_tools_list": (
        "---\nname: ok-name\ndescription: d\nallowed-tools:\n  - Read\n  - Grep\n---\n"
    ),
    "documented_extras": (
        "---\nname: ok-name\ndescription: d\nwhen_to_use: sometimes\n"
        "model: opus\ncontext: fork\nuser-invocable: true\n---\n"
    ),
}


@unittest.skipUnless(VALIDATOR.exists(), "bundled validator missing")
class TestShippedFrontmatterIsValid(unittest.TestCase):
    def test_skill_md_declares_the_field_that_motivated_this(self):
        """If this stops being true the laundering test below proves nothing."""
        self.assertIn("disable-model-invocation:", read(SKILL_MD))

    def test_real_skill_md_passes_without_modification(self):
        proc = run_validator(VALIDATOR, SKILL_DIR)
        self.assertEqual(
            proc.returncode, 0,
            f"the file as shipped must validate:\n{proc.stdout}{proc.stderr}",
        )

    def test_rejects_known_bad_frontmatter(self):
        for label, text in INVALID_FRONTMATTER.items():
            with self.subTest(case=label):
                with skill_dir_with(text) as tmp:
                    proc = run_validator(VALIDATOR, tmp)
                self.assertEqual(
                    proc.returncode, 1, f"{label} should have been rejected"
                )

    def test_accepts_documented_frontmatter(self):
        for label, text in VALID_FRONTMATTER.items():
            with self.subTest(case=label):
                with skill_dir_with(text) as tmp:
                    proc = run_validator(VALIDATOR, tmp)
                self.assertEqual(
                    proc.returncode, 0,
                    f"{label} is documented and must be accepted:\n{proc.stderr}",
                )

    def test_usage_error_is_distinct_from_invalid(self):
        proc = subprocess.run(
            [sys.executable, str(VALIDATOR)], capture_output=True, text=True
        )
        self.assertEqual(proc.returncode, 2)


@unittest.skipUnless(
    QUICK_VALIDATE.exists(), "skill-creator quick_validate.py not installed"
)
class TestValidatorIsNotWeaker(unittest.TestCase):
    """Replacing a validator must not quietly relax it.

    For every input skill-creator's validator rejects, the bundled one must
    reject it too. The reverse is allowed: the bundled validator knows more
    fields, so it accepts documented frontmatter that quick_validate does not.
    """

    def test_rejects_everything_quick_validate_rejects(self):
        weakened = []
        for label, text in INVALID_FRONTMATTER.items():
            with skill_dir_with(text) as tmp:
                old = run_validator(QUICK_VALIDATE, tmp)
                new = run_validator(VALIDATOR, tmp)
            if old.returncode != 0 and new.returncode == 0:
                weakened.append(label)
        self.assertFalse(
            weakened, f"bundled validator accepts what quick_validate rejects: {weakened}"
        )

    def test_the_comparison_is_not_vacuous(self):
        """Guard the guard: if quick_validate rejected nothing, the test above
        would pass while comparing nothing at all."""
        rejected = 0
        for text in INVALID_FRONTMATTER.values():
            with skill_dir_with(text) as tmp:
                if run_validator(QUICK_VALIDATE, tmp).returncode != 0:
                    rejected += 1
        self.assertGreaterEqual(rejected, 10, "corpus is not exercising quick_validate")

    def test_documents_why_quick_validate_was_replaced(self):
        body = read(VALIDATOR)
        self.assertIn("quick_validate", body)
        self.assertIn("docs.anthropic.com", body, "field allowlist needs a provenance")


class TestValidatorMatchesClaudeCodeSchema(unittest.TestCase):
    """The validator's own claims about the schema must stay true.

    A stale number in a docstring is the same class of defect this skill exists
    to prevent in other people's documentation.
    """

    def setUp(self):
        spec = importlib.util.spec_from_file_location("uv_validator", VALIDATOR)
        self.mod = importlib.util.module_from_spec(spec)
        sys.modules["uv_validator"] = self.mod
        spec.loader.exec_module(self.mod)

    def test_docstring_field_count_matches_the_set(self):
        words = {
            "five": 5, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
        }
        claimed = re.search(
            r"frontmatter reference table\s*\n?\s*has (\w+)", self.mod.__doc__
        )
        self.assertIsNotNone(claimed, "docstring must state the field count")
        self.assertIn(claimed.group(1), words, f"unmapped number word: {claimed.group(1)}")
        self.assertEqual(
            words[claimed.group(1)],
            len(self.mod.CLAUDE_CODE_FIELDS),
            "docstring field count disagrees with CLAUDE_CODE_FIELDS",
        )

    def test_accepts_every_documented_boolean_spelling(self):
        """Claude Code v2.1.218 accepts yes/no/on/off/1/0 as well as true/false.

        PyYAML already resolves all of those to `bool` except `1` and `0`, which
        arrive as `int` — so a bare isinstance(_, bool) check would reject
        frontmatter Claude Code accepts.
        """
        for spelling in ("true", "false", "yes", "no", "on", "off", "1", "0"):
            with self.subTest(value=spelling):
                text = (
                    "---\nname: ok-name\ndescription: d\n"
                    f"disable-model-invocation: {spelling}\n---\n"
                )
                with skill_dir_with(text) as tmp:
                    proc = run_validator(VALIDATOR, tmp)
                self.assertEqual(
                    proc.returncode, 0,
                    f"{spelling} is an accepted boolean:\n{proc.stderr}",
                )

    def test_rejects_non_boolean_values_for_boolean_fields(self):
        for spelling in ("2", "-1", "maybe", "'true'"):
            with self.subTest(value=spelling):
                text = (
                    "---\nname: ok-name\ndescription: d\n"
                    f"disable-model-invocation: {spelling}\n---\n"
                )
                with skill_dir_with(text) as tmp:
                    proc = run_validator(VALIDATOR, tmp)
                self.assertEqual(
                    proc.returncode, 1, f"{spelling} is not a boolean"
                )


class TestLiveEvalHarness(unittest.TestCase):
    """The with-skill arm must measure an installed skill.

    Concatenating SKILL.md into the prompt measures a different artifact:
    ${CLAUDE_SKILL_DIR} never resolves, allowed-tools never applies, references
    are not loaded on demand, and the mandatory discovery script cannot run.
    """

    def setUp(self):
        self.body = read(SCRIPTS_DIR / "run_live_eval.sh")

    def test_installs_the_skill_rather_than_pasting_it(self):
        self.assertIn(".claude/skills", self.body)
        self.assertRegex(self.body, r'cp -R "\$\{SKILL_DIR\}"')
        self.assertIn("/update-doc", self.body)
        self.assertNotIn(
            'cat "${SKILL_DIR}/SKILL.md"', self.body,
            "pasting SKILL.md into the prompt does not exercise the real lifecycle",
        )

    def test_setup_failure_has_its_own_exit_code(self):
        self.assertIn("exit 2", self.body)
        self.assertIn("not a skill result", self.body)

    def test_documents_the_two_arm_comparison(self):
        self.assertIn("UPDATE_DOC_EVAL_ARM", self.body)
        self.assertIn("without-skill", self.body)


class TestVersionClaims(unittest.TestCase):
    """`${CLAUDE_SKILL_DIR}` has two different version gates.

    Body substitution landed in v2.1.69 (CHANGELOG); substitution inside
    `allowed-tools` rules requires v2.1.129 (frontmatter reference docs). Citing
    one number for both is wrong in whichever direction it is stated.
    """

    def test_both_gates_are_stated_with_sources(self):
        body = read(SKILL_MD)
        self.assertIn("v2.1.69", body, "body-substitution gate missing")
        self.assertIn("v2.1.129", body, "allowed-tools substitution gate missing")
        self.assertIn("CHANGELOG", body)
        self.assertRegex(body, r"Frontmatter reference", "docs source missing")

    def test_degradation_between_the_gates_is_described(self):
        body = read(SKILL_MD)
        self.assertRegex(
            body,
            r"v2\.1\.69[–-]v2\.1\.128",
            "the window where the body resolves but the grant does not must be named",
        )


if __name__ == "__main__":
    unittest.main()

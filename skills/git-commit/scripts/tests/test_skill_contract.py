"""Structural contract tests for the git-commit skill.

SCOPE, STATED HONESTLY: this file checks that the skill's *documents and
scripts contain what they claim to* — frontmatter fields, required sections,
reference integrity, and specific claims that a past defect proved must be
present. Many assertions here are therefore presence checks, and a presence
check is weak evidence: passing it means the text exists, not that the skill
behaves correctly.

Behavioural proof lives in test_git_integration.py (real scripts against real
git repositories, including the failure paths) and test_golden_scenarios.py
(fixtures resolved by the shipped scripts, never by a re-implementation).
Judge coverage by those two files; read this one as a drift tripwire.
"""

import os
import re
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parent.parent.parent
SKILL_MD = SKILL_DIR / "SKILL.md"
REFERENCES_DIR = SKILL_DIR / "references"

REQUIRED_ECOSYSTEMS = ["go", "node", "python", "java", "rust"]
REQUIRED_ALLOWED_TOOL_PATTERNS = [
    "Bash(git add*)",
    "Bash(git commit*)",
    "Bash(git status*)",
    "Bash(git diff*)",
    "Bash(git log*)",
    "Bash(git stash*)",
    "Bash(go list*)",
    "Bash(go build*)",
    "Bash(go vet*)",
    "Bash(go test*)",
    "Bash(golangci-lint*)",
    "Bash(pytest*)",
    "Bash(ruff check*)",
    "Bash(flake8*)",
    "Bash(mypy*)",
    "Bash(pyright*)",
    "Bash(cargo check*)",
    "Bash(cargo clippy*)",
    "Bash(cargo test*)",
    "Bash(mvn test*)",
    "Bash(./gradlew*)",
    "Bash(npm*)",
    "Bash(yarn*)",
    "Bash(pnpm*)",
    "Bash(npx nx*)",
    "Bash(npx turbo*)",
    "Bash(npx lerna*)",
    "Bash(make test*)",
    "Bash(make check*)",
    "Bash(make*)",
    "Bash(git config --get*)",
    "Bash(bun*)",
    "Bash(deno*)",
    "Bash(bash *secret-scan.sh*)",
    "Bash(bash *stash-guard.sh*)",
    "Bash(bash *run-gate.sh*)",
    "Bash(bash *detect-ecosystems.sh*)",
    "Bash(bash *resolve-scope.sh*)",
]


@pytest.fixture
def skill_content():
    return SKILL_MD.read_text(encoding="utf-8")


@pytest.fixture
def skill_lines(skill_content):
    return skill_content.splitlines()


# --- Frontmatter ---


class TestFrontmatter:
    def test_has_frontmatter_delimiters(self, skill_content):
        assert skill_content.startswith("---\n"), "Must start with frontmatter ---"
        # Find second ---
        second = skill_content.index("---", 4)
        assert second > 4, "Must have closing frontmatter ---"

    def test_has_name_field(self, skill_content):
        assert re.search(r"^name:\s+git-commit", skill_content, re.MULTILINE)

    def test_has_description_field(self, skill_content):
        assert re.search(r"^description:\s+.{20,}", skill_content, re.MULTILINE), (
            "description must be at least 20 chars"
        )

    def test_allowed_tools_cover_documented_quality_gate_commands(self, skill_content):
        allowed_tools = re.search(r"^allowed-tools:\s+(.+)$", skill_content, re.MULTILINE)
        assert allowed_tools, "allowed-tools frontmatter is required"
        missing = [
            pattern
            for pattern in REQUIRED_ALLOWED_TOOL_PATTERNS
            if pattern not in allowed_tools.group(1)
        ]
        assert not missing, (
            "allowed-tools must cover documented git workflow and quality gate commands; "
            f"missing: {missing}"
        )


# --- Required Sections ---


class TestRequiredSections:
    REQUIRED_HEADINGS = [
        "Hard Rules",
        "Workflow",
        "Preflight",
        "Staging",
        "Secret/sensitive-content gate",
        "Quality gate",
        "Compose commit message",
        "Commit",
        "Post-commit report",
        "Message Examples",
        "Failure Handling",
    ]

    @pytest.mark.parametrize("heading", REQUIRED_HEADINGS)
    def test_section_present(self, skill_content, heading):
        pattern = re.compile(rf"^#{{1,4}}\s+.*{re.escape(heading)}", re.MULTILINE | re.IGNORECASE)
        assert pattern.search(skill_content), f"Missing required section: {heading}"

    def test_has_edge_cases_section(self, skill_content):
        assert re.search(r"^#{1,4}\s+Edge Cases", skill_content, re.MULTILINE), (
            "Missing Edge Cases section"
        )


# --- Key Content ---


class TestKeyContent:
    def test_50_char_rule_is_stated_as_an_overridable_default(self, skill_content):
        # Scope the check to the ONE bullet that states the limit. Searching the
        # whole Hard Rules block passed against the contradictory original text,
        # because a neighbouring bullet ("do not use --amend unless...") already
        # contained the qualifier word — a guard wider than its own subject.
        hard_rules = skill_content.split("## Hard Rules", 1)[1].split("\n## ", 1)[0]
        bullets = [b for b in hard_rules.splitlines() if b.startswith("- ") and "50" in b]
        assert len(bullets) == 1, f"expected exactly one subject-limit bullet, got {bullets}"
        claim = bullets[0]
        assert re.search(r"default|replace|unless|override", claim, re.IGNORECASE), (
            "The Hard Rule must present 50 as a DEFAULT that §5 can replace. "
            f"It currently reads as an absolute: {claim!r}"
        )

    def test_subject_guard_is_executable(self, skill_content):
        assert "subject too long (${#SUBJECT}/$SUBJECT_MAX)" in skill_content
        assert "SUBJECT_MAX=${SUBJECT_MAX:-50}" in skill_content
        assert "subject must not end with ." in skill_content

    def test_heredoc_commit_format(self, skill_content):
        assert "<<'EOF'" in skill_content, "Must use heredoc for multi-line commits"
        # Single message source: the guard must read the heredoc's first line,
        # not a separate SUBJECT variable that can drift from what is committed.
        assert "SUBJECT=${MSG%%" in skill_content, (
            "multi-line guard must validate the exact first line of the message"
        )

    def test_multiple_m_guidance_is_accurate(self, skill_content):
        # Prefer `-F -` for bodies. The old claim "multiple -m cannot handle a body"
        # was factually wrong — each -m becomes its own paragraph.
        assert "git commit -F -" in skill_content
        assert "each becomes its own paragraph" in skill_content

    def test_hook_awareness(self, skill_content):
        assert "--no-verify" in skill_content, "Must mention --no-verify policy"

    def test_stash_guard_script(self):
        script = SKILL_DIR / "scripts" / "stash-guard.sh"
        assert script.is_file(), "scripts/stash-guard.sh must exist"
        content = script.read_text()
        assert "git stash push --keep-index" in content
        assert "trap" in content, "restore must be trap-guaranteed on every exit path"
        # Signal handling must be split from EXIT: a shared EXIT+INT+TERM handler
        # restores twice and can report an interrupt as exit 0.
        assert "trap - EXIT" in content, "traps must be cleared before exiting (single restore)"
        assert "finish 130" in content, "SIGINT must exit 130, never 0"
        assert "finish 143" in content, "SIGTERM must exit 143, never 0"
        # `git stash push` can exit 0 without creating an entry (submodule-only
        # dirt); claiming stash@{0} blindly would pop a pre-existing user stash.
        assert "BEFORE" in content and '"$STASH" = "$BEFORE"' in content, (
            "must verify a NEW stash entry appeared before adopting stash@{0}"
        )
        assert "cannot isolate" in content, (
            "unstashable residue must refuse the gate (fail-closed), not run it "
            "against a mixed tree"
        )
        assert "git write-tree" in content, (
            "must detect worktree/index drift during the gate before reset --hard"
        )

    def test_scripts_are_invoked_via_skill_path_not_cwd_relative(self, skill_content):
        # The agent's CWD is the target repo, not the skill directory — a bare
        # `bash scripts/...` does not resolve there.
        assert '"<path-to-skill>/scripts/' in skill_content
        assert "bash scripts/" not in skill_content, (
            "CWD-relative script invocations do not resolve from the target repo"
        )

    def test_run_gate_script(self):
        script = SKILL_DIR / "scripts" / "run-gate.sh"
        assert script.is_file(), "scripts/run-gate.sh must exist (timeout must be enforced)"
        content = script.read_text()
        assert "GATE_TIMEOUT" in content, "must report the chosen timeout"
        assert "120" in content, "must default to 120 seconds"
        for var in (
            "COMMIT_TEST_TIMEOUT",
            "QUALITY_GATE_TIMEOUT_SECONDS",
            "SKILL_QUALITY_GATE_TIMEOUT_SECONDS",
        ):
            assert var in content, f"must honor the documented override {var}"
        assert "refusing to run" in content, (
            "no usable timeout tool must mean exit 2, not an unbounded run"
        )
        # A tool that cannot force-kill must be SKIPPED, never used with a
        # warning: reporting a timeout the tool cannot deliver tells the caller
        # the gate is dead while it may still hold locks and ports.
        assert 'exec "$tool" "$SECS"' not in content, (
            "run-gate must not fall back to a timeout that lacks --kill-after"
        )
        assert "trying the next tool" in content
        assert "disable the timeout" in content, "a zero timeout must be rejected"
        assert "setpgrp" in content, (
            "the perl fallback must kill the gate's whole process group, "
            "not only the direct child"
        )
        assert "-k" in content and "KILL_AFTER" in content, (
            "TERM alone does not back the 'process tree is dead' promise: GNU "
            "timeout returns 124 while a TERM-ignoring command keeps running"
        )

    def test_timeout_exit_code_is_single_and_documented(self, skill_content):
        """run-gate normalises three implementations (GNU 124/137, BusyBox
        143/137, perl 124) to ONE code, so the doc must state one rule."""
        gate = skill_content.split("### 4. Quality gate", 1)[1].split("### 5.", 1)[0]
        assert "124" in gate, "the quality-gate section must name the timeout code"
        script = (SKILL_DIR / "scripts" / "run-gate.sh").read_text()
        assert "rc=124" in script and "elapsed" in script, (
            "normalisation must key on elapsed time, not on the tool's own code: "
            "BusyBox reports 143 for a plain expiry and never 124"
        )

    def test_detect_ecosystems_script(self):
        script = SKILL_DIR / "scripts" / "detect-ecosystems.sh"
        assert script.is_file(), "scripts/detect-ecosystems.sh must exist"
        content = script.read_text()
        for marker in ("go.mod", "package.json", "Cargo.toml", "pyproject.toml", "pom.xml"):
            assert marker in content, f"marker-only stages must be detected: {marker}"
        assert "--diff-filter=d" not in content, (
            "deletions must reach the detector: removing an imported helper is "
            "exactly the change that breaks its ecosystem's build"
        )
        assert "-z --name-only" in content and "set -o pipefail" in content, (
            "raw paths, and no silently-failing stage: empty output is this "
            "script's signal for 'no ecosystem', so any failure must exit 2"
        )

    def test_partial_staging(self, skill_content):
        assert "git add -p" in skill_content

    def test_timeout_specified(self, skill_content):
        assert "120 seconds" in skill_content or "120s" in skill_content

    def test_scope_frequency_threshold(self, skill_content):
        assert ">= 3" in skill_content, "Must define scope frequency threshold"

    def test_scope_rules_are_delegated_to_the_script(self, skill_content):
        # Mechanical rules left as prose forced the golden tests to re-derive
        # them in Python, which only proved Python agreed with Python.
        assert "resolve-scope.sh" in skill_content
        assert "Bash(bash *resolve-scope.sh*)" in skill_content, (
            "allowed-tools must permit the script the workflow tells you to run"
        )

    def test_bootstrap_threshold_matches_the_script(self, skill_content):
        """Derive the threshold from the implementation instead of matching a
        sentence: the previous phrase-match broke the moment the wording
        changed, while an inverted rule would have sailed through it."""
        script = (SKILL_DIR / "scripts" / "resolve-scope.sh").read_text()
        implemented = re.search(r"if \(cc < (\d+)\)", script)
        assert implemented, "resolve-scope.sh must gate bootstrap on a commit count"
        n = implemented.group(1)
        assert re.search(rf"fewer than {n}\b", skill_content), (
            f"the script bootstraps below {n} conventional commits; SKILL.md "
            f"must state the same number"
        )
        assert "bootstrap" in skill_content

    def test_staging_threshold_has_an_authorization_exception(self, skill_content):
        assert "> 8 files" in skill_content, "Must define staging confirmation threshold"
        staging = skill_content.split("### 2. Staging", 1)[1].split("###", 1)[0]
        bullets = [b for b in staging.splitlines() if "> 8 files" in b]
        assert len(bullets) == 1, f"expected one >8-files bullet, got {bullets}"
        assert re.search(r"unless|already authoriz|except", bullets[0], re.IGNORECASE), (
            "the >8 prompt must yield to an explicit prior authorization; an "
            f"unconditional 'always ask' re-asks an answered question: {bullets[0]!r}"
        )

    def test_secret_scan_script_fallback(self):
        script = SKILL_DIR / "scripts" / "secret-scan.sh"
        assert script.is_file(), "scripts/secret-scan.sh must exist"
        content = script.read_text()
        assert "gitleaks git --pre-commit" in content, "must use the non-deprecated gitleaks form"
        assert "--exit-code 10" in content, (
            "findings exit code must be pinned — gitleaks' default exit 1 is "
            "ambiguous between findings and execution errors"
        )
        assert "[REDACTED]" in content, "findings must be redacted, never printed in full"
        assert "SCANNER_ERROR" in content, "gitleaks failures must be surfaced, not swallowed"
        assert "HEAD:.commit-secret-allowlist" in content, (
            "only the COMMITTED allowlist may dismiss findings"
        )
        assert "^@@ " in content, "must parse hunk headers for real source line numbers"
        assert "KEYED_RE" in content and "tolower" in content, (
            "keyed secrets must match case-insensitively and on ':' as well as "
            "'=', or every JSON/YAML credential is invisible"
        )
        # Property, not idiom: the previous version of this assertion counted a
        # specific `if [ $? -ne 0 ]` spelling, so it broke when the same check
        # was written as `if ! var=$(...)`. What must hold is that no stage can
        # fail silently — pipefail plus a checked pipeline — and that paths are
        # read raw rather than in git's escaped display form.
        assert "set -o pipefail" in content, (
            "without pipefail a failing awk mid-pipeline reports the shell's "
            "last status, so a broken scan exits 0 with no findings"
        )
        assert "-z --name-only" in content, (
            "filenames must come from `-z`: core.quotePath escapes non-ASCII "
            'paths to "\\346\\272\\220…", which stops *.pem from matching'
        )
        assert "core.quotePath=false" in content, (
            "the patch stream must carry literal paths, or a finding is "
            "labelled with a path `git show` cannot open"
        )

    def test_secret_scan_documents_its_real_redaction_limit(self, skill_content):
        gate = skill_content.split("### 3. Secret", 1)[1].split("### 4.", 1)[0]
        assert "Residual risk" in gate, (
            "the doc claimed the secret value is NEVER printed; masking is "
            "shape-based, so the unmaskable case must be stated, not implied"
        )

    def test_context_render_is_not_fed_by_a_pipe(self):
        """The extractor exits at `NR > n + 2`. Fed by a pipe, that leaves the
        writer mid-write on a large blob: SIGPIPE, exit 141, and pipefail turns
        a COMPLETED render into a scan failure. Size-dependent, so it passed at
        3 lines and blocked at 20k."""
        content = (SKILL_DIR / "scripts" / "secret-scan.sh").read_text()
        assert "< <(printf" in content, (
            "context rendering must be fed by redirect/process substitution, "
            "not a pipe, so a legitimate early exit is not read as a failure"
        )
        ctx = content.split("2 lines of context", 1)[1].split("done", 1)[0]
        assert "| LC_ALL=C" not in ctx and "|\n" not in ctx, (
            f"the context stage still pipes into awk:\n{ctx[:400]}"
        )

    def test_awk_interval_capability_is_probed(self):
        """Twelve credential patterns are length-anchored ({16}, {20,}, ...).
        An awk without interval support matches NOTHING and the scan prints a
        clean result — the worst failure mode this script has, and invisible in
        its output."""
        content = (SKILL_DIR / "scripts" / "secret-scan.sh").read_text()
        intervals = re.findall(r"\{\d+,?\d*\}", content)
        assert len(intervals) >= 5, (
            f"expected length-anchored patterns; found {intervals} — if these "
            f"are gone the probe below is no longer needed"
        )
        assert "AWK_PROBE" in content and "regex intervals" in content, (
            "an awk that cannot match the patterns must be detected and refused, "
            "not allowed to report a confident clean scan"
        )

    def test_portability_matrix_runner_exists_and_cannot_pass_empty(self):
        script = SKILL_DIR / "scripts" / "run_portability_matrix.sh"
        assert script.is_file(), "scripts/run_portability_matrix.sh must exist"
        content = script.read_text()
        assert "UNVERIFIED" in content, (
            "absent implementations must be reported as gaps, not omitted"
        )
        assert "empty matrix is not a passing matrix" in content, (
            "a run that exercised nothing must exit non-zero"
        )
        # The shim it builds must exec an absolute path; a bare `exec awk` makes
        # the shim call itself and hang, which is how the first version failed.
        assert "$abs" in content and "command -v \"$1\"" in content

    def test_cross_env_probe_needs_no_python(self):
        """The probe exists to reach hosts pytest cannot: minimal Linux images
        ship neither python nor pytest, which is why every non-macOS row was
        missing from the evidence for three rounds."""
        script = SKILL_DIR / "scripts" / "run_cross_env_probe.sh"
        assert script.is_file(), "scripts/run_cross_env_probe.sh must exist"
        # Assert on INVOCATIONS, not on the word. The probe legitimately greps
        # for the `python` ecosystem name and names pytest in its comments; a
        # blanket text ban forbids vocabulary rather than the dependency.
        code = "\n".join(l for l in script.read_text().splitlines()
                         if not l.lstrip().startswith("#"))
        # Anchored at COMMAND POSITION (line start, or after a pipe/;/&&/$( ),
        # so the word inside a message like "selects the python gate" is not a
        # match while `python3 -c ...` or `| pytest` is.
        bad = re.findall(r"(?m)(?:^|[|;&(]|\$\()[ \t]*(python3?|pytest)\b", code)
        assert not bad, (
            f"the probe must not invoke python/pytest ({bad}), or it cannot run "
            f"where the pytest suite already cannot — which is most minimal "
            f"Linux images, and was why every non-macOS row was missing"
        )
        # `content` was renamed to `code` (comments stripped) above; these two
        # checks need the FULL text, since both live in echo strings.
        full = script.read_text()
        assert "RESULT: nothing was exercised" in full, (
            "a probe that exercised nothing must not report success"
        )
        assert "gaps in the evidence, not passes" in full, (
            "an absent capability must be reported as a gap, never skipped silently"
        )

    def test_eval_harness_exists_and_states_its_limits(self):
        runner = SKILL_DIR / "scripts" / "eval" / "run_eval.sh"
        readme = SKILL_DIR / "scripts" / "eval" / "README.md"
        assert runner.is_file() and readme.is_file()
        scen = sorted((SKILL_DIR / "scripts" / "eval" / "scenarios").glob("*.sh"))
        assert len(scen) >= 6, f"expected >= 6 decision scenarios, got {len(scen)}"
        run = runner.read_text()
        # A missing answer must never be scored, and a control arm must exist.
        assert "INCOMPLETE" in run and "do not read this as a score" in run
        assert "EVAL_ARMS" in run, "a no-skill control arm must be available"
        doc = readme.read_text()
        for claim in ("Non-deterministic", "plan mode", "base"):
            assert claim in doc, (
                f"the README must state {claim!r}: an eval that overstates its "
                f"scope is worse than none"
            )

    def test_regression_runner_surfaces_skips(self):
        content = (SKILL_DIR / "scripts" / "run_regression.sh").read_text()
        assert "-rs" in content, (
            "skipped tests mark missing tools (real gitleaks, other awks); an "
            "invisible skip is how a gap gets mistaken for coverage"
        )

    def test_resolve_scope_script(self):
        script = SKILL_DIR / "scripts" / "resolve-scope.sh"
        assert script.is_file(), "scripts/resolve-scope.sh must exist"
        content = script.read_text()
        assert "exit 2" in content, "an unreadable repo must not yield a guessed scope"
        assert "SCOPE_SOURCE" in content
        assert "-z --name-only" in content and "set -o pipefail" in content, (
            "an escaped path would strip the very directory names a bootstrap "
            "scope is derived from"
        )

    def test_submodule_awareness(self, skill_content):
        assert "submodule" in skill_content.lower()

    def test_allow_empty_documented(self, skill_content):
        assert "--allow-empty" in skill_content

    def test_timeout_override_documented(self, skill_content):
        assert "COMMIT_TEST_TIMEOUT" in skill_content
        assert "QUALITY_GATE_TIMEOUT_SECONDS" in skill_content
        assert "SKILL_QUALITY_GATE_TIMEOUT_SECONDS" in skill_content


# --- Reference Files ---


class TestReferenceFiles:
    def test_references_dir_exists(self):
        assert REFERENCES_DIR.is_dir(), "references/ directory must exist"

    @pytest.mark.parametrize("ecosystem", REQUIRED_ECOSYSTEMS)
    def test_ecosystem_reference_exists(self, ecosystem):
        path = REFERENCES_DIR / f"quality-gate-{ecosystem}.md"
        assert path.is_file(), f"Missing reference: quality-gate-{ecosystem}.md"

    @pytest.mark.parametrize("ecosystem", REQUIRED_ECOSYSTEMS)
    def test_ecosystem_reference_has_marker(self, ecosystem):
        path = REFERENCES_DIR / f"quality-gate-{ecosystem}.md"
        content = path.read_text(encoding="utf-8")
        assert re.search(r"[Mm]arker", content), (
            f"quality-gate-{ecosystem}.md must document its marker file"
        )

    @pytest.mark.parametrize("ecosystem", REQUIRED_ECOSYSTEMS)
    def test_ecosystem_reference_has_test_commands(self, ecosystem):
        path = REFERENCES_DIR / f"quality-gate-{ecosystem}.md"
        content = path.read_text(encoding="utf-8")
        has_test_section = re.search(r"^#{1,4}\s+Tests?", content, re.MULTILINE)
        has_test_command = re.search(
            r"(go test|pytest|<pm> test|npm test|mvn test|gradlew.*test|cargo test)",
            content,
        )
        assert has_test_section or has_test_command, (
            f"quality-gate-{ecosystem}.md must have a Tests section or test commands"
        )

    @pytest.mark.parametrize("ecosystem", REQUIRED_ECOSYSTEMS)
    def test_ecosystem_reference_has_quantified_threshold(self, ecosystem):
        """Each ecosystem must have a concrete numeric threshold, not vague 'small/large'."""
        path = REFERENCES_DIR / f"quality-gate-{ecosystem}.md"
        content = path.read_text(encoding="utf-8")
        # Must contain a comparison operator with a number, or a variable-based check
        has_threshold = (
            re.search(r"(<=?\s*\d+|>\s*\d+|=\s*0\b)", content)
            or re.search(r"(PKG_COUNT|FILE_COUNT|CHANGED_COUNT|MODULE_COUNT|IS_WORKSPACE)", content)
        )
        assert has_threshold, (
            f"quality-gate-{ecosystem}.md must have a quantified threshold"
        )

    def test_skill_md_links_all_references(self, skill_content):
        for ecosystem in REQUIRED_ECOSYSTEMS:
            filename = f"quality-gate-{ecosystem}.md"
            assert filename in skill_content, (
                f"SKILL.md must link to references/{filename}"
            )

    def test_go_reference_aligns_with_skill_summary(self):
        content = (REFERENCES_DIR / "quality-gate-go.md").read_text(encoding="utf-8")
        for phrase in ("go build", "golangci-lint", "go vet", "go test"):
            assert phrase in content, f"quality-gate-go.md must mention {phrase}"

    def test_manifest_only_stage_never_noops(self):
        # Scoping by changed source files selects zero modules/crates/packages
        # when only a manifest or lockfile is staged — each scoped gate must
        # carry an explicit manifest guard that falls back to the full run.
        rust = (REFERENCES_DIR / "quality-gate-rust.md").read_text(encoding="utf-8")
        java = (REFERENCES_DIR / "quality-gate-java.md").read_text(encoding="utf-8")
        go = (REFERENCES_DIR / "quality-gate-go.md").read_text(encoding="utf-8")
        assert "MANIFEST_CHANGED" in rust and "--workspace" in rust
        assert "MANIFEST_CHANGED" in java
        assert "go.sum" in go and "Manifest changes" in go

    def test_node_reference_covers_bun_and_deno(self):
        # detect-ecosystems.sh maps bun/deno markers to "node" — the reference
        # must define how to actually run those gates.
        content = (REFERENCES_DIR / "quality-gate-node.md").read_text(encoding="utf-8")
        for token in ("bun.lock", "bunx", "deno.json", "deno test", "deno lint"):
            assert token in content, f"quality-gate-node.md must cover {token}"


# --- Line Count ---


class TestLineCount:
    def test_skill_md_stays_operational(self, skill_content):
        """Concision budget in CHARACTERS, not lines.

        The bloat this guards against arrived as long explanatory sentences
        inside existing bullets, so a line count never moved while the daily
        read grew. The measured "why" lives in references/design-evidence.md,
        which an invocation does not load; SKILL.md carries the rules only.
        """
        chars = len(skill_content)
        assert chars <= 16500, (
            f"SKILL.md is {chars} chars; move measured rationale into "
            f"references/design-evidence.md rather than growing the "
            f"instruction an agent reads on every invocation"
        )

    def test_design_evidence_reference_exists_and_is_linked(self, skill_content):
        ref = REFERENCES_DIR / "design-evidence.md"
        assert ref.is_file(), "references/design-evidence.md must exist"
        assert "design-evidence.md" in skill_content, (
            "SKILL.md must point at the evidence file, or the reasoning is lost"
        )
        body = ref.read_text(encoding="utf-8")
        # It has to actually carry the evidence, not just be a stub.
        for probe in ("mawk 1.3.4 20200120", "BusyBox", "PIPESTATUS",
                      "AKIAIOSFODNN7EXAMPLE", "core.quotePath"):
            assert probe in body, f"design-evidence.md must record {probe!r}"

    def test_skill_md_under_200_lines(self, skill_lines):
        # Only a ceiling. A floor was removed: it made a shorter, clearer
        # SKILL.md a test failure, and coverage of the workflow is already
        # asserted section by section in TestRequiredSections.
        assert len(skill_lines) <= 200, (
            f"SKILL.md is {len(skill_lines)} lines; target <= 200"
        )


class TestGoldenCoverage:
    def test_golden_test_exists(self):
        path = SKILL_DIR / "scripts" / "tests" / "test_golden_scenarios.py"
        assert path.is_file(), "Missing golden scenario regression test"

    def test_golden_fixtures_exist(self):
        golden_dir = SKILL_DIR / "scripts" / "tests" / "golden"
        assert golden_dir.is_dir(), "Missing golden fixture directory"
        fixtures = list(golden_dir.glob("*.json"))
        assert len(fixtures) >= 7, f"Expected >= 7 golden fixtures, got {len(fixtures)}"

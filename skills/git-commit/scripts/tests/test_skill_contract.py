"""Contract tests for the git-commit skill.

Validates structural requirements: frontmatter fields, required sections,
reference file integrity, and line count targets.
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
    def test_50_char_subject_rule(self, skill_content):
        assert "<= 50 char" in skill_content or "<= 50 chars" in skill_content

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
        assert "refusing to run unbounded" in content, (
            "no timeout tool must mean exit 2, not an unbounded run"
        )
        assert "disable the timeout" in content, "a zero timeout must be rejected"
        assert "setpgrp" in content, (
            "the perl fallback must kill the gate's whole process group, "
            "not only the direct child"
        )

    def test_detect_ecosystems_script(self):
        script = SKILL_DIR / "scripts" / "detect-ecosystems.sh"
        assert script.is_file(), "scripts/detect-ecosystems.sh must exist"
        content = script.read_text()
        for marker in ("go.mod", "package.json", "Cargo.toml", "pyproject.toml", "pom.xml"):
            assert marker in content, f"marker-only stages must be detected: {marker}"

    def test_partial_staging(self, skill_content):
        assert "git add -p" in skill_content

    def test_timeout_specified(self, skill_content):
        assert "120 seconds" in skill_content or "120s" in skill_content

    def test_scope_frequency_threshold(self, skill_content):
        assert ">= 3" in skill_content, "Must define scope frequency threshold"

    def test_scope_bootstrap_for_new_repos(self, skill_content):
        assert "fewer than 10 conventional commits total" in skill_content
        assert "bootstrap scope from staged paths" in skill_content

    def test_staging_file_count_threshold(self, skill_content):
        assert "> 8 files" in skill_content, "Must define staging confirmation threshold"

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
    def test_skill_md_under_200_lines(self, skill_lines):
        assert len(skill_lines) <= 200, (
            f"SKILL.md is {len(skill_lines)} lines; target <= 200"
        )

    def test_skill_md_over_100_lines(self, skill_lines):
        assert len(skill_lines) >= 100, (
            f"SKILL.md is {len(skill_lines)} lines; too sparse (< 100)"
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

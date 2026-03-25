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

    def test_heredoc_commit_format(self, skill_content):
        assert "<<'EOF'" in skill_content, "Must use heredoc for multi-line commits"

    def test_no_multiple_m_flags(self, skill_content):
        assert "Do **not** use multiple `-m`" in skill_content

    def test_hook_awareness(self, skill_content):
        assert "--no-verify" in skill_content, "Must mention --no-verify policy"

    def test_stash_strategy(self, skill_content):
        assert "git stash push --keep-index" in skill_content

    def test_partial_staging(self, skill_content):
        assert "git add -p" in skill_content

    def test_timeout_specified(self, skill_content):
        assert "120 seconds" in skill_content or "120s" in skill_content

    def test_scope_frequency_threshold(self, skill_content):
        assert ">= 3" in skill_content, "Must define scope frequency threshold"

    def test_staging_file_count_threshold(self, skill_content):
        assert "> 8 files" in skill_content, "Must define staging confirmation threshold"

    def test_rg_grep_fallback(self, skill_content):
        assert "command -v rg" in skill_content, "Must detect rg availability"
        assert "grep -En" in skill_content, "Must have grep fallback"

    def test_submodule_awareness(self, skill_content):
        assert "submodule" in skill_content.lower()

    def test_allow_empty_documented(self, skill_content):
        assert "--allow-empty" in skill_content


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
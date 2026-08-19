"""Mutation tests for the api-design documentation linter.

A linter that reports nothing proves nothing. For every rule in
`lint_api_doc.RULES` this file injects the exact regression the rule exists to
catch and asserts that rule fires. The uncovered set is *derived* from the rule
registry, so adding a rule without a mutation fails the suite instead of
silently reading as covered.
"""

import importlib.util
import pathlib
import re
import shutil
import sys

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
LINTER_PATH = SKILL_DIR / "scripts" / "lint_api_doc.py"


def _load_linter():
    """Load by path: the repo runs pytest with --import-mode=importlib, so a
    bare sibling import would not resolve. Register in sys.modules before
    exec so any dataclass/annotation resolution inside the module works."""
    spec = importlib.util.spec_from_file_location("lint_api_doc", LINTER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["lint_api_doc"] = module
    spec.loader.exec_module(module)
    return module


LINT = _load_linter()

SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

# rule -> (relative file, old substring, replacement). Every occurrence of
# `old` is replaced: a single-occurrence replace leaves surviving copies and
# makes a live rule look SURVIVED.
MUTATIONS = {
    "AD001": ("references/compatibility-rules.md",
              "Deprecation: @1688169599",
              "Deprecation: true"),
    "AD002": ("references/api-anti-examples.md",
              "**The defect is the inconsistency and the missing spec — not the 200 itself.**",
              "200 with body is semantically incorrect for DELETE."),
    "AD003": ("references/error-model-patterns.md",
              "- Use **404** when the resource's existence is itself confidential",
              "- You must return 404 for every denied request"),
    "AD004": ("references/error-model-patterns.md",
              '"trace_id": "req-abc-123"',
              '"metric": "http_request_errors_total",\n    "trace_id": "req-abc-123"'),
    "AD005": ("SKILL.md",
              "**[D] Resource naming & hierarchy**",
              "**Resource naming & hierarchy**"),
    "AD006": ("SKILL.md",
              "`C3` No internal implementation detail",
              "`C3` Resource naming conventions and no internal implementation detail"),
    "AD007": ("references/compatibility-rules.md",
              "the `IMF-fixdate` form defined in RFC 9110 §5.6.7",
              "RFC 7231 HTTP-date"),
    "AD008": ("references/compatibility-rules.md",
              "| **Reorder response fields** |",
              "| **Something unrelated** |"),
    "AD009": ("SKILL.md",
              "Critical: `Y/3`",
              "Critical: `Y/4`"),
    "AD010": ("SKILL.md",
              "9. **[C] Write-conflict policy** → `S2`",
              "9. **[C] Write-conflict policy** → `C1`"),
    "AD012": ("references/error-model-patterns.md",
              "<!-- api-lint: lww-acceptable -->",
              ""),
    "AD013": ("SKILL.md",
              "(item 6)",
              "(item 99)"),
    "AD014": ("SKILL.md",
              "| Tag | Nature | The rule says | A conforming API may |",
              "| Tag | Nature | Max finding severity | A conforming API may |"),
    "AD015": ("references/compatibility-rules.md",
              "Sunset: Sun, 30 Jun 2024 23:59:59 GMT",
              "Sunset: Sun, 30 Jun 2024 23:59:59 UTC"),
    "AD017": ("SKILL.md",
              "→ `C3` · *Triggers: T6*.",
              "→ `C3`."),
    "AD018": ("references/compatibility-rules.md",
              "  - Prefer 410 Gone for removed endpoints",
              "  - Return 410 Gone (not 404) for removed endpoints"),
    "AD016": ("SKILL.md",
              "`Retry-After`. RFC 6585 §4 says the response **MAY** include it "
              "— recommend it, never fail on it | [D] |",
              "`Retry-After` | [P] |"),
}


@pytest.fixture
def doc_tree(tmp_path):
    """A writable copy of just the documentation the linter reads."""
    shutil.copy(SKILL_DIR / "SKILL.md", tmp_path / "SKILL.md")
    shutil.copytree(SKILL_DIR / "references", tmp_path / "references")
    return tmp_path


def _mutate(tree: pathlib.Path, rel: str, old: str, new: str) -> int:
    path = tree / rel
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    path.write_text(text.replace(old, new), encoding="utf-8")
    return count


class TestLinterOnRealDocs:
    def test_shipped_docs_are_clean(self):
        findings = LINT.lint(SKILL_DIR)
        assert not findings, "\n".join(
            f"{f.rule} {f.path}:{f.line} {f.message}" for f in findings)

    def test_every_rule_has_a_summary(self):
        assert set(LINT.RULES) == set(LINT.RULE_SUMMARY)

    def test_parsers_are_not_vacuous(self):
        """A rule set that parses zero items would pass every structural check."""
        docs = LINT.load_docs(SKILL_DIR)
        items, _ = LINT._checklist_items(docs["SKILL.md"].text)
        tiers = LINT._scorecard_tiers(docs["SKILL.md"].text)
        assert len(items) >= 12, f"only {len(items)} checklist items parsed"
        assert sum(len(v) for v in tiers.values()) == 12
        assert set(tiers) == {"Critical", "Standard", "Hygiene"}
        assert len(docs) == 4


class TestMutationCoverage:
    def test_every_rule_has_a_mutation(self):
        uncovered = set(LINT.RULES) - set(MUTATIONS)
        assert not uncovered, f"rules with no mutation test: {sorted(uncovered)}"

    def test_no_mutation_for_unknown_rule(self):
        assert not set(MUTATIONS) - set(LINT.RULES)

    @pytest.mark.parametrize("rule", sorted(MUTATIONS))
    def test_mutation_is_caught(self, rule, doc_tree):
        rel, old, new = MUTATIONS[rule]
        assert _mutate(doc_tree, rel, old, new) >= 1, \
            f"{rule}: anchor text {old!r} not found in {rel} — mutation is a no-op"
        fired = {f.rule for f in LINT.lint(doc_tree)}
        assert rule in fired, \
            f"{rule} SURVIVED its mutation in {rel}; rules fired: {sorted(fired)}"


class TestPerAxisCoverage:
    """AD016 guards four independent status codes. One mutation proves one axis;
    a rule that only ever fired for 429 would still show as killed."""

    @pytest.mark.parametrize("code", sorted(LINT.OPTIONAL_COMPANION_CODES))
    def test_marking_a_row_mandatory_is_caught(self, code, doc_tree):
        path = doc_tree / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        row = next(l for l in text.splitlines()
                   if re.match(rf"^\s*\|[^|]*\|\s*{code}\s*\|", l))
        path.write_text(text.replace(row, re.sub(r"\|\s*\[D\]\s*\|", "| [P] |", row)),
                        encoding="utf-8")
        assert "AD016" in {f.rule for f in LINT.lint(doc_tree)}, \
            f"AD016 did not fire when status {code}'s companion was marked mandatory"

    @pytest.mark.parametrize("code", sorted(LINT.OPTIONAL_COMPANION_CODES))
    def test_dropping_a_row_is_caught(self, code, doc_tree):
        path = doc_tree / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        row = next(l for l in text.splitlines()
                   if re.match(rf"^\s*\|[^|]*\|\s*{code}\s*\|", l))
        path.write_text(text.replace(row + "\n", ""), encoding="utf-8")
        assert "AD016" in {f.rule for f in LINT.lint(doc_tree)}, \
            f"deleting the status {code} row silently removed its optionality note"


class TestGuardTheGuard:
    """The suppression machinery must suppress, and must not over-suppress."""

    FORBIDDEN = "200 with body is semantically incorrect"

    def test_forbidden_phrase_fires_without_sentinel(self, doc_tree):
        path = doc_tree / "references" / "api-anti-examples.md"
        path.write_text(path.read_text(encoding="utf-8") +
                        f"\n\nNote: {self.FORBIDDEN} for DELETE.\n", encoding="utf-8")
        assert "AD002" in {f.rule for f in LINT.lint(doc_tree)}

    def test_sentinel_suppresses_the_quoted_claim(self, doc_tree):
        """A doc must be able to quote the wrong claim in order to correct it."""
        path = doc_tree / "references" / "api-anti-examples.md"
        path.write_text(
            path.read_text(encoding="utf-8") +
            "\n\n<!-- api-lint-allow: AD002 -->\n"
            f"Historical error, now corrected: \"{self.FORBIDDEN} for DELETE.\"\n"
            "<!-- /api-lint-allow -->\n", encoding="utf-8")
        assert "AD002" not in {f.rule for f in LINT.lint(doc_tree)}

    def test_sentinel_is_scoped_to_its_own_rule(self, doc_tree):
        """An AD002 exemption must not blanket-suppress AD008."""
        path = doc_tree / "references" / "compatibility-rules.md"
        text = path.read_text(encoding="utf-8")
        text = text.replace("| **Reorder response fields** |", "| **Gone** |")
        path.write_text("<!-- api-lint-allow: AD002 -->\n" + text +
                        "\n<!-- /api-lint-allow -->\n", encoding="utf-8")
        assert "AD008" in {f.rule for f in LINT.lint(doc_tree)}

    def test_masking_preserves_line_numbers(self, doc_tree):
        """Masked spans are NUL-filled, not deleted, so lines stay aligned."""
        path = doc_tree / "references" / "api-anti-examples.md"
        original = path.read_text(encoding="utf-8")
        injected = original + f"\n\nNote: {self.FORBIDDEN} for DELETE.\n"
        path.write_text(injected, encoding="utf-8")
        expected_line = injected[:injected.find(self.FORBIDDEN)].count("\n") + 1
        hits = [f for f in LINT.lint(doc_tree) if f.rule == "AD002"]
        # Overlapping blocklist phrases can match one sentence more than once;
        # what must hold is that every report points at the injected line.
        assert hits, "AD002 did not fire on the injected claim"
        assert {h.line for h in hits} == {expected_line}

    def test_code_blocks_and_prose_are_separated(self):
        """AD001 scans code only, so prose may cite the invalid form as invalid."""
        docs = LINT.load_docs(SKILL_DIR)
        compat = docs["references/compatibility-rules.md"]
        assert "Deprecation: true" in compat.prose, \
            "the doc should explain that the boolean form is invalid"
        assert "Deprecation: true" not in compat.code
        assert not [f for f in LINT.lint(SKILL_DIR) if f.rule == "AD001"]


class TestRegressionRunnerWiring:
    def test_linter_is_invoked_by_run_regression(self):
        script = (SKILL_DIR / "scripts" / "run_regression.sh").read_text(encoding="utf-8")
        assert "lint_api_doc.py" in script, \
            "the linter must run in regression, not only under pytest"

    def test_linter_is_executable_as_a_script(self):
        assert LINTER_PATH.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3")

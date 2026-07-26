"""Every template in references/templates.md must survive the skill's own linter.

Why this layer exists: the templates are the most-copied artefact in the skill, and none of them
carried the frontmatter that Gate 3 marks Critical — so a reader who copied any template started
from a document that failed the skill's own mandatory metadata check. Nothing detected that,
because no test ever ran a template through `lint_doc.py`.

A template is a skeleton, so placeholder substitution is part of the contract: `YYYY-MM-DD` and
`<Document Title>` are filled the way a real user would fill them, then the result is linted. If
a template cannot pass after that substitution, the template is wrong.
"""

import importlib.util
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
TEMPLATES = SKILL_DIR / "references" / "templates.md"
LINTER = SKILL_DIR / "scripts" / "lint_doc.py"

# Heading substring -> --type value for the linter.
TYPE_BY_HEADING = {
    "task": "task",
    "concept": "concept",
    "reference": "reference",
    "troubleshooting": "troubleshooting",
    "design": "design",
}


def _lint_doc_module():
    spec = importlib.util.spec_from_file_location("lint_doc", LINTER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _templates():
    """Yield (heading, doc_type_or_None, body) for each ```markdown template block.

    Scanned line by line rather than with one regex: template bodies contain their own `## `
    headings, so a regex pairing `^## (.+?)` with the next fence attributed blocks to the wrong
    section (Task and Troubleshooting came out as "Table of Contents" and "4. Error Codes")."""
    heading = None
    fence_len = 0          # 0 = outside; otherwise the opening fence's backtick count
    fence_lang = ""
    buf: list[str] = []
    for line in TEMPLATES.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(`{3,})(.*)$", line)
        if m:
            ticks, info = len(m.group(1)), m.group(2).strip()
            if fence_len == 0:
                fence_len, fence_lang, buf = ticks, info, []
                continue
            # CommonMark: a fence closes only with the same char and AT LEAST as many
            # backticks. Treating any ``` as a closer let an inner ```http end the outer
            # template block — the Reference template was truncated to 22 lines and its
            # error-code and compatibility sections were never linted.
            if ticks >= fence_len and not info:
                if fence_lang == "markdown" and any("title:" in b for b in buf):
                    dt = next((v for k, v in TYPE_BY_HEADING.items()
                               if heading and k in heading.lower()), None)
                    yield (heading or "<unknown>"), dt, "\n".join(buf)
                fence_len, fence_lang = 0, ""
                continue
            buf.append(line)     # an inner fence is content, not a delimiter
            continue
        if fence_len:
            buf.append(line)
        elif line.startswith("## "):
            heading = line[3:].strip()


def _fill_placeholders(body: str) -> str:
    body = body.replace("YYYY-MM-DD", "2026-07-26")
    body = re.sub(r"<Document Title>", "Placeholder Title", body)
    body = re.sub(r"^(owner:).*$", r"\1 platform-team", body, flags=re.M)
    return body


class TemplateLintTests(unittest.TestCase):

    def test_templates_were_found(self):
        found = list(_templates())
        self.assertGreaterEqual(len(found), 5,
                                f"expected the 5 doc-type templates, found {len(found)}")

    def test_every_template_declares_mandatory_frontmatter(self):
        lint_doc = _lint_doc_module()
        for heading, _dt, body in _templates():
            with self.subTest(template=heading):
                fm, _body, _off = lint_doc.split_frontmatter(_fill_placeholders(body))
                for field in ("title", "owner", "status", "last_updated"):
                    self.assertIn(field, fm,
                                  f"{heading}: template omits mandatory `{field}` — a reader "
                                  f"copying it starts from a Gate 3 Critical failure")
                self.assertIn(fm["status"], lint_doc.VALID_STATUS,
                              f"{heading}: template status {fm['status']!r} is not one the "
                              f"linter accepts")

    def test_every_template_passes_the_linter(self):
        for heading, doc_type, body in _templates():
            with self.subTest(template=heading):
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / "t.md"
                    path.write_text(_fill_placeholders(body), encoding="utf-8")
                    argv = [sys.executable, str(LINTER), str(path)]
                    if doc_type:
                        argv += ["--type", doc_type]
                    proc = subprocess.run(argv, capture_output=True, text=True,
                                          timeout=60, errors="replace")
                    crit = [l for l in proc.stdout.splitlines() if l.startswith("[critical]")]
                    self.assertEqual(
                        [], crit,
                        f"{heading}: template fails the skill's own linter:\n"
                        + "\n".join(crit))

    def test_troubleshooting_template_has_an_h1(self):
        """It began at `### Incident`, so every copy tripped the single-h1 warning."""
        body = next(b for h, _t, b in _templates() if "troubleshooting" in h.lower())
        self.assertRegex(body, r"(?m)^# \S", "troubleshooting template needs a single H1")

    def test_no_template_duplicates_frontmatter_in_the_body(self):
        """A body metadata section restated owner/status/date that frontmatter already carries —
        two sources of truth that drift apart. Matching only the exact heading `## Metadata`
        missed the Task template's numbered `## 6. Metadata`, so the field-level check below is
        the real guard."""
        dup_field = re.compile(r"(?im)^[-*]\s*(owner|last updated|created|status)\s*:")
        for heading, _dt, body in _templates():
            with self.subTest(template=heading):
                # Heading form, numbered or not.
                self.assertNotRegex(
                    body, r"(?im)^##+\s*(\d+\.\s*)?Metadata\s*$",
                    f"{heading}: body Metadata section duplicates the YAML frontmatter")
                # And the fields themselves, wherever they appear in the body.
                _fm, doc_body, _off = _lint_doc_module().split_frontmatter(body)
                hits = dup_field.findall(doc_body)
                self.assertFalse(
                    hits,
                    f"{heading}: body list restates frontmatter field(s) {sorted(set(hits))} — "
                    f"frontmatter is the single source of truth")

    def test_extraction_reaches_the_end_of_every_template(self):
        """Regression: the extractor treated any ``` as a closer, so the Reference template's
        inner ```http ended the outer block after 22 lines and its error-code, compatibility,
        and changelog sections were never linted — while the test name claimed full coverage."""
        seen = {}
        for heading, _dt, body in _templates():
            seen[heading] = body
        ref = next((b for h, b in seen.items() if "reference" in h.lower()), None)
        self.assertIsNotNone(ref, "Reference template not extracted")
        for section in ("Error Codes", "Compatibility", "Changelog"):
            self.assertIn(section, ref,
                          f"Reference template truncated before §{section}; extraction is "
                          f"closing on an inner fence")
        # Content-based, not a magic line count: each template must reach its own final
        # section. Troubleshooting is legitimately the shortest, so a length floor would
        # either miss truncation elsewhere or fail on a correct short template.
        terminal = {
            "task": "## 5. Troubleshooting (FAQ)",
            "concept": "## 8. Further Reading",
            "reference": "## 6. Changelog",
            "troubleshooting": "#### Prevention",
            "design": "## 8. Open Questions",
        }
        for heading, body in seen.items():
            key = next((k for k in terminal if k in heading.lower()), None)
            if key:
                self.assertIn(
                    terminal[key], body,
                    f"{heading}: extraction stops before its final section "
                    f"{terminal[key]!r} — the outer fence is closing early")

    def test_outer_template_fences_are_longer_than_inner_ones(self):
        """The structural fix: outer blocks use four backticks so inner ``` nest legally."""
        text = TEMPLATES.read_text(encoding="utf-8")
        openers = len(re.findall(r"(?m)^````markdown\s*$", text))
        closers = len(re.findall(r"(?m)^````\s*$", text))
        self.assertGreaterEqual(openers, 5, "each doc-type template needs a four-backtick fence")
        self.assertEqual(openers, closers, "four-backtick fences are unbalanced")
        self.assertNotRegex(
            text, r"(?m)^```markdown\s*$",
            "a three-backtick outer template fence will be closed by its first inner fence")

    def test_design_template_separates_document_and_decision_status(self):
        """`Draft/In Review/Accepted/Superseded` collided with the linter's document-status
        vocabulary. They are different axes: an Accepted decision can sit in a needs-update doc."""
        body = next(b for h, _t, b in _templates() if "design" in h.lower())
        self.assertIn("decision_status", body,
                      "the decision lifecycle must be a distinct field from document `status`")
        self.assertRegex(body, r"(?m)^status:\s*draft\b",
                         "document status must use the linter's vocabulary")

    def test_yaml_trailing_comments_are_parsed(self):
        """Templates annotate their frontmatter. Before the fix, `status: draft  # notes` was
        read as the literal value `draft  # notes` and rejected — so an annotated template could
        never pass. Quoted `#` must still survive."""
        lint_doc = _lint_doc_module()
        fm, _b, _o = lint_doc.split_frontmatter(
            "---\nstatus: draft  # draft | active\n"
            'title: "sharp # sign"\n# a whole-line comment\nowner: t\n'
            "last_updated: 2026-07-26\n---\n\nbody\n")
        self.assertEqual("draft", fm["status"])
        self.assertEqual("sharp # sign", fm["title"], "quoted '#' must not be stripped")
        self.assertNotIn("# a whole-line comment", fm)


if __name__ == "__main__":
    unittest.main()

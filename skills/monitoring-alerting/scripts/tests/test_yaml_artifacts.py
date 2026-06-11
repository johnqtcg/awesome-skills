"""Behavioral tests for the YAML artifacts in SKILL.md and references.

The alert-rule and routing snippets are this skill's most-copied artifacts.
Three layers:

1. Every fenced ``yaml`` block must parse (PyYAML) — always runs.
2. Structural shape: in GOOD/RIGHT alert examples, every rule with an
   ``alert:`` key must carry ``expr:`` — always runs.
3. ``promtool check rules`` on every alert-rule fragment, wrapped in a
   minimal ``groups:`` scaffold — skipped when promtool is not installed
   (it validates the embedded PromQL, which PyYAML cannot).

Also guards the fixes this file landed with: allowed-tools present,
reference-count drift ("Both reference files" with three on disk), and the
§5.5 validation discipline staying wired into the doc.
"""

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

# Optional dependency: a hard module-level import crashes pytest COLLECTION
# in environments without PyYAML, killing the entire repo suite instead of
# skipping these tests (this happened in CI). Declared in requirements.txt;
# degrade gracefully anyway.
try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

requires_yaml = unittest.skipUnless(
    yaml is not None, "PyYAML not installed (pip install -r requirements.txt)")

SKILL_DIR = Path(__file__).resolve().parents[2]
SKILL_MD = SKILL_DIR / "SKILL.md"
DOC_FILES = [SKILL_MD, *sorted((SKILL_DIR / "references").glob("*.md"))]


def yaml_blocks() -> list[tuple[str, str]]:
    blocks = []
    for path in DOC_FILES:
        for i, m in enumerate(re.findall(r"```yaml\n(.*?)```", path.read_text(encoding="utf-8"),
                                         re.DOTALL), 1):
            blocks.append((f"{path.name}#blk{i}", m))
    return blocks


def alert_rule_fragments() -> list[tuple[str, list]]:
    """Parsed blocks that are lists of alerting rules (``- alert: ...``)."""
    out = []
    for name, text in yaml_blocks():
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError:
            continue
        if isinstance(doc, list) and any(isinstance(e, dict) and "alert" in e for e in doc):
            out.append((name, doc))
    return out


@requires_yaml
class YamlParseTests(unittest.TestCase):
    def test_blocks_found(self) -> None:
        self.assertGreaterEqual(len(yaml_blocks()), 15)

    def test_every_yaml_block_parses(self) -> None:
        for name, text in yaml_blocks():
            try:
                yaml.safe_load(text)
            except yaml.YAMLError as exc:
                self.fail(f"{name}: yaml does not parse: {exc}")

    def test_alert_rules_have_expr(self) -> None:
        for name, doc in alert_rule_fragments():
            for entry in doc:
                if isinstance(entry, dict) and "alert" in entry:
                    self.assertIn("expr", entry,
                                  f"{name}: rule {entry.get('alert')!r} has no expr")


@requires_yaml
@unittest.skipUnless(shutil.which("promtool"), "promtool not installed")
class PromtoolTests(unittest.TestCase):
    def test_alert_fragments_pass_promtool_check(self) -> None:
        failures = []
        with tempfile.TemporaryDirectory() as tmp:
            for i, (name, doc) in enumerate(alert_rule_fragments()):
                rules = [e for e in doc if isinstance(e, dict) and "alert" in e]
                wrapped = {"groups": [{"name": f"g{i}", "rules": rules}]}
                path = Path(tmp) / f"rules_{i}.yml"
                path.write_text(yaml.safe_dump(wrapped), encoding="utf-8")
                proc = subprocess.run(["promtool", "check", "rules", str(path)],
                                      capture_output=True, text=True, timeout=60)
                if proc.returncode != 0:
                    failures.append(f"{name}:\n{proc.stdout}{proc.stderr}")
        self.assertEqual([], failures, "promtool rejected:\n" + "\n".join(failures))


class DocConsistencyGuards(unittest.TestCase):
    def test_allowed_tools_declared(self) -> None:
        frontmatter = SKILL_MD.read_text(encoding="utf-8").split("---")[1]
        self.assertIn("allowed-tools:", frontmatter,
                      "skill shipped without allowed-tools once")
        for pattern in ("Bash(promtool*)", "Bash(amtool*)"):
            self.assertIn(pattern, frontmatter,
                          f"§5.5 tells the user to run this; pre-approve it: {pattern}")

    def test_reference_count_not_stale(self) -> None:
        """Three references exist; the depth table once said 'Both'."""
        text = SKILL_MD.read_text(encoding="utf-8")
        self.assertNotIn("Both reference files", text)
        ref_count = len(list((SKILL_DIR / "references").glob("*.md")))
        self.assertEqual(3, ref_count, "update §3/§9 and this test when references change")
        for ref in (SKILL_DIR / "references").glob("*.md"):
            self.assertIn(ref.name, text,
                          f"reference {ref.name} not mentioned in SKILL.md")

    def test_validation_discipline_wired(self) -> None:
        text = SKILL_MD.read_text(encoding="utf-8")
        for token in ("promtool check rules", "promtool test rules", "amtool check-config"):
            self.assertIn(token, text, f"§5.5 validation discipline missing: {token}")
        self.assertIn("Validation evidence", text,
                      "§8.4 must require validation evidence in the output contract")


if __name__ == "__main__":
    unittest.main()
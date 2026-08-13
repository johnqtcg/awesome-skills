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

import json
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


def routing_configs() -> list[tuple[str, str]]:
    """Fenced yaml blocks that look like Alertmanager config (a `route:` or `inhibit_rules:`).

    Anti-example blocks are excluded: they contain deliberately broken routing, so feeding
    them to amtool would fail for the reason they exist.
    """
    out = []
    for name, text in yaml_blocks():
        if re.search(r"^\s*#\s*WRONG", text, re.M | re.I):
            continue
        if re.search(r"^\s*(route|inhibit_rules):", text, re.M):
            out.append((name, text))
    return out


@requires_yaml
@unittest.skipUnless(shutil.which("amtool"), "amtool not installed")
class AmtoolTests(unittest.TestCase):
    """§5.5 tells the user to run `amtool check-config`; this runs it on our own config.

    Added 2026-08-12: the skill demanded amtool of its readers while never invoking it on
    the config it ships. Wrapped in a minimal receivers scaffold, because the doc fragments
    are route trees rather than whole files.
    """

    def test_routing_fragments_pass_amtool_check(self) -> None:
        failures = []
        with tempfile.TemporaryDirectory() as tmp:
            for i, (name, text) in enumerate(routing_configs()):
                doc = yaml.safe_load(text)
                if not isinstance(doc, dict):
                    continue
                receivers = set()

                def collect(node):
                    if isinstance(node, dict):
                        if "receiver" in node:
                            receivers.add(node["receiver"])
                        for v in node.values():
                            collect(v)
                    elif isinstance(node, list):
                        for v in node:
                            collect(v)
                collect(doc)
                cfg = {
                    "route": doc.get("route", {"receiver": next(iter(receivers), "default")}),
                    "receivers": [{"name": r} for r in sorted(receivers)] or [{"name": "default"}],
                }
                if "inhibit_rules" in doc:
                    cfg["inhibit_rules"] = doc["inhibit_rules"]
                if "route" not in doc and "inhibit_rules" in doc:
                    cfg["route"] = {"receiver": cfg["receivers"][0]["name"]}
                path = Path(tmp) / f"am_{i}.yml"
                path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
                proc = subprocess.run(["amtool", "check-config", str(path)],
                                      capture_output=True, text=True, timeout=60)
                if proc.returncode != 0:
                    failures.append(f"{name}:\n{proc.stdout}{proc.stderr}")
        self.assertEqual([], failures, "amtool rejected:\n" + "\n".join(failures))


class ExternalValidatorHonestyTests(unittest.TestCase):
    """The runner must not claim more than it executed.

    A review read "106 passed, 1 skipped" as "the rules are validated" -- but the one
    skipped test was the *only* stage that executed an artifact. A skip is not a pass, and
    a summary line that does not distinguish them invites exactly that reading.
    """

    RUNNER = SKILL_DIR / "scripts" / "run_regression.sh"

    def test_runner_reports_external_validator_count(self) -> None:
        text = self.RUNNER.read_text(encoding="utf-8")
        self.assertIn("external validators ran", text,
                      "run_regression.sh does not report how many external validators ran")
        self.assertIn("NOT INSTALLED", text,
                      "a missing validator must be named as skipped, not omitted silently")

    def test_runner_qualifies_its_pass_verdict(self) -> None:
        text = self.RUNNER.read_text(encoding="utf-8")
        self.assertIn("PASS (text layer only)", text,
                      "with zero validators run, the verdict must say so rather than "
                      "printing an unqualified pass")

    def test_install_commands_offered(self) -> None:
        text = self.RUNNER.read_text(encoding="utf-8")
        for tool in ("promtool", "amtool"):
            self.assertIn(f"cmd/{tool}@latest", text,
                          f"tell the user how to close the gap for {tool}")


GOLDEN_DIR = SKILL_DIR / "scripts" / "tests" / "golden"


def golden_yaml_snippets() -> list[tuple[str, str, dict]]:
    """(label, snippet, fixture) for golden fixtures whose code_snippet is a rule file.

    Added 2026-08-12 after the review found MON-007 shipping a `code_snippet` that did not
    parse as YAML at all -- a `groups:` mapping followed by a bare `- alert:` sequence. It had
    survived every check because promtool and the YAML parser only ever saw markdown fenced
    blocks. A `good_practice` fixture is a model answer, so an unparseable one is worse than an
    unparseable doc example: it is the thing being held up as correct.
    """
    out = []
    for path in sorted(GOLDEN_DIR.glob("*.json")):
        fx = json.loads(path.read_text(encoding="utf-8"))
        snip = fx.get("code_snippet", "")
        # only fixtures that present themselves as Prometheus rules; the defect fixtures
        # deliberately contain broken input and are graded on the feedback, not the YAML
        if fx.get("type") != "good_practice":
            continue
        if not re.search(r"^\s*(groups:|- (alert|record):)", snip, re.M):
            continue
        out.append((f"{path.name}:{fx['id']}", snip, fx))
    return out


@requires_yaml
class GoldenSnippetTests(unittest.TestCase):
    """A model-answer snippet must be loadable by the tool it claims to configure."""

    def test_snippets_found(self) -> None:
        """Negative control: an empty list makes every check below vacuous."""
        self.assertGreater(len(golden_yaml_snippets()), 0,
                           "no good_practice rule snippets extracted -- these checks would "
                           "validate nothing and still report success")

    def test_every_good_practice_snippet_parses(self) -> None:
        for label, snip, _ in golden_yaml_snippets():
            try:
                doc = yaml.safe_load(snip)
            except yaml.YAMLError as exc:
                self.fail(f"{label}: model-answer snippet does not parse as YAML: "
                          f"{str(exc).splitlines()[0]}")
            self.assertIsInstance(
                doc, dict,
                f"{label}: a rule file must be a mapping with `groups:`, not "
                f"{type(doc).__name__}")
            self.assertIn("groups", doc, f"{label}: rule file has no `groups:` key")

    def test_multi_window_claims_use_two_windows(self) -> None:
        """A "multi-window" claim must actually compare two different ranges.

        MON-007 claimed a 1h long window plus a 5m short window while both sides of the
        expression used `sli:*:rate5m` -- the same window twice. That looks like a
        multi-window alert and behaves like a single-window one, which is the exact failure
        the pattern exists to avoid.
        """
        for label, snip, fx in golden_yaml_snippets():
            claim = re.search(r"multi-?window", fx.get("expected_feedback", ""), re.I)
            if not claim:
                continue
            doc = yaml.safe_load(snip)
            for grp in doc.get("groups", []):
                for rule in grp.get("rules", []):
                    if "alert" not in rule:
                        continue
                    expr = str(rule.get("expr", ""))
                    ranges = set(re.findall(r":rate(\w+)\b", expr)) or \
                        set(re.findall(r"\[(\w+)\]", expr))
                    if len(ranges) < 2:
                        self.fail(
                            f"{label}: expected_feedback claims a multi-window alert, but "
                            f"{rule['alert']} uses {len(ranges)} distinct window(s) "
                            f"{sorted(ranges)} -- the same window on both sides is a "
                            f"single-window alert wearing a multi-window shape")

    def test_feedback_window_claims_match_the_expression(self) -> None:
        """Every window the prose names must appear in the expression."""
        for label, snip, fx in golden_yaml_snippets():
            fb = fx.get("expected_feedback", "")
            claimed = set(re.findall(r"\b(\d+(?:h|m|d))\s+(?:long |short )?window", fb))
            if not claimed:
                continue
            for w in claimed:
                self.assertIn(
                    w, snip,
                    f"{label}: feedback names a {w} window that the snippet never uses")


@requires_yaml
@unittest.skipUnless(shutil.which("promtool"), "promtool not installed")
class GoldenPromtoolTests(unittest.TestCase):
    """Run the real parser over model-answer snippets, not just the docs."""

    def test_good_practice_snippets_pass_promtool(self) -> None:
        failures = []
        with tempfile.TemporaryDirectory() as tmp:
            for i, (label, snip, _) in enumerate(golden_yaml_snippets()):
                path = Path(tmp) / f"golden_{i}.yml"
                path.write_text(snip, encoding="utf-8")
                proc = subprocess.run(["promtool", "check", "rules", str(path)],
                                      capture_output=True, text=True, timeout=60)
                if proc.returncode != 0:
                    failures.append(f"{label}:\n{proc.stdout}{proc.stderr}")
        self.assertEqual([], failures, "promtool rejected a model answer:\n"
                         + "\n".join(failures))


PROMTOOL_DIR = SKILL_DIR / "tests" / "promtool"


@unittest.skipUnless(shutil.which("promtool"), "promtool not installed")
class PromtoolUnitTestTests(unittest.TestCase):
    """Run `promtool test rules` -- TEMPORAL behaviour, not just syntax.

    `promtool check rules` proves the PromQL parses. It cannot tell you whether the alert
    fires when it should and stays silent when it should not, and a wrong window pairing or a
    wrong `for` parses perfectly while paging at 3AM. §5.5 tells readers to write two cases
    per SLO-critical alert; these are that, for the skill's own alert.

    Five cases, each of which a rule mutation turns red (verified):
      1 sustained burn fires        4 health-check traffic is excluded
      2 clean traffic stays silent  5 alert CLEARS after recovery (the short window's real job)
      3 brief spike absorbed by the long window

    Case 5 exists because case 3 cannot distinguish a single-window rule from a multi-window
    one: a brief spike is silent either way. Only "burn stopped, must stop paging" does.
    """

    def test_rule_files_present(self) -> None:
        self.assertTrue((PROMTOOL_DIR / "rules.yml").exists())
        self.assertTrue((PROMTOOL_DIR / "rules_test.yml").exists())

    def test_rules_pass_check(self) -> None:
        proc = subprocess.run(["promtool", "check", "rules", "rules.yml"],
                              cwd=PROMTOOL_DIR, capture_output=True, text=True, timeout=120)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def test_temporal_unit_tests_pass(self) -> None:
        proc = subprocess.run(["promtool", "test", "rules", "rules_test.yml"],
                              cwd=PROMTOOL_DIR, capture_output=True, text=True, timeout=300)
        self.assertEqual(0, proc.returncode,
                         "promtool test rules failed:\n" + proc.stdout + proc.stderr)
        self.assertIn("SUCCESS", proc.stdout)

    def test_runner_derives_the_case_count(self) -> None:
        """The runner must count the temporal cases, not state a number.

        It printed "5 temporal cases" after the file had grown to 8 — prose-count drift inside
        the script that reports on the suite that documents prose-count drift.
        """
        runner = (SKILL_DIR / "scripts" / "run_regression.sh").read_text(encoding="utf-8")
        self.assertIn("grep -c '^  - interval:'", runner,
                      "the temporal-case count must be derived from rules_test.yml")
        self.assertNotRegex(runner, r"\(\d+ temporal cases\)",
                            "the case count is hardcoded again")

    def test_covers_the_empty_vector_trap(self) -> None:
        """The all-replicas-down cases must exist, and must assert the BROKEN form is silent.

        `count(up == 1) == 0` passes `promtool check rules` and reads as "no instance is up".
        It is silent when every instance is down. The only thing that documents that is a
        `promql_expr_test` asserting `exp_samples: []` for the broken form beside the working
        one -- prose claiming it would be enough for a reader, not for a regression.
        """
        body = (PROMTOOL_DIR / "rules_test.yml").read_text(encoding="utf-8")
        self.assertIn("count(up", body,
                      "the broken form must be asserted empty, not merely described")
        self.assertIn("exp_samples: []", body)
        self.assertRegex(body, r"series absent|absent\(",
                         "missing the gone-from-discovery case that only absent() catches")
        rules = (PROMTOOL_DIR / "rules.yml").read_text(encoding="utf-8")
        self.assertIn("absent(up", rules,
                      "the shipped all-down alert must include the absent() half")

    def test_covers_both_directions_and_recovery(self) -> None:
        """A suite of only must-fire cases proves nothing about false positives."""
        body = (PROMTOOL_DIR / "rules_test.yml").read_text(encoding="utf-8")
        self.assertGreaterEqual(body.count("exp_alerts: []"), 3,
                                "need several must-stay-silent cases, not just must-fire")
        self.assertIn("exp_labels", body, "need at least one must-fire case")
        self.assertRegex(body, r"clears once the burn stops|after recovery",
                         "missing the recovery case -- without it, deleting the "
                         "short-window clause is undetectable")

    def test_rules_match_the_documented_pattern(self) -> None:
        """The executed rules must be the ones the docs prescribe, not a simplified copy."""
        rules = (PROMTOOL_DIR / "rules.yml").read_text(encoding="utf-8")
        for token in ("sli:http_requests_valid:rate1h", "sli:http_requests_bad:rate5m",
                      "14.4 * 0.001", 'path!~"/health.*|/metrics"'):
            self.assertIn(token, rules,
                          f"the executed rule file has drifted from §1.1/§3: missing {token}")


@requires_yaml
class PromtoolScaffoldTests(unittest.TestCase):
    """Validate the promtool harness itself, without needing promtool.

    `PromtoolTests` has never executed in this environment -- promtool is not installed --
    so nothing has ever confirmed that the `groups:` scaffold it builds is even the shape
    promtool expects. A harness that has never run is not a passing check; it is an
    untested code path that will fail for its own reasons the first time someone installs
    the binary, and the failure will look like a problem with the rules.

    These tests exercise the same construction and assert it against the documented
    Prometheus rule-file schema, so the harness is verified now and promtool only has to
    add PromQL validation later.
    """

    def _wrapped(self):
        out = []
        for i, (name, doc) in enumerate(alert_rule_fragments()):
            rules = [e for e in doc if isinstance(e, dict) and "alert" in e]
            out.append((name, {"groups": [{"name": f"g{i}", "rules": rules}]}))
        return out

    def test_fragments_were_found(self) -> None:
        """Negative control: an empty fragment list makes every check below vacuous."""
        self.assertGreater(len(self._wrapped()), 0,
                           "no alert-rule fragments extracted -- the promtool harness "
                           "would validate nothing and still report success")

    def test_scaffold_matches_prometheus_rule_file_schema(self) -> None:
        for name, cfg in self._wrapped():
            self.assertIn("groups", cfg, f"{name}: missing top-level groups")
            for grp in cfg["groups"]:
                self.assertIn("name", grp, f"{name}: rule group has no name")
                self.assertIn("rules", grp, f"{name}: rule group has no rules")
                self.assertGreater(len(grp["rules"]), 0,
                                   f"{name}: rule group is empty; promtool rejects that")
                for rule in grp["rules"]:
                    self.assertIn("alert", rule)
                    self.assertIn("expr", rule)
                    self.assertIsInstance(rule["expr"], str,
                                          f"{name}: expr must be a string after parsing")
                    for key in rule:
                        self.assertIn(
                            key, {"alert", "expr", "for", "keep_firing_for",
                                  "labels", "annotations"},
                            f"{name}: {key!r} is not a valid alerting-rule field; "
                            f"promtool would reject the file")

    def test_scaffold_round_trips_through_yaml(self) -> None:
        """promtool reads a file, so the scaffold must survive dump -> load unchanged."""
        for name, cfg in self._wrapped():
            reparsed = yaml.safe_load(yaml.safe_dump(cfg))
            self.assertEqual(cfg, reparsed, f"{name}: scaffold does not round-trip")

    def test_for_durations_are_valid_prometheus_durations(self) -> None:
        """`for: 5` (no unit) parses as YAML but promtool rejects it."""
        dur = re.compile(r"^((\d+)(ms|[smhdwy]))+$")
        for name, cfg in self._wrapped():
            for rule in cfg["groups"][0]["rules"]:
                if "for" not in rule:
                    continue
                self.assertIsInstance(
                    rule["for"], str,
                    f"{name}: rule {rule['alert']} has for={rule['for']!r} as a number; "
                    f"Prometheus needs a unit (5m, not 5)")
                self.assertRegex(
                    rule["for"], dur,
                    f"{name}: rule {rule['alert']} has an invalid for duration "
                    f"{rule['for']!r}")


class LocalLinkTests(unittest.TestCase):
    """Every relative link in SKILL.md and the references must resolve.

    Added 2026-08-13 when §5.5 started pointing at `tests/promtool/rules_test.yml` instead of
    carrying a duplicate copy of it. Pointers are the right call — a second copy of an
    executable file drifts silently — but a pointer is only better than a copy if something
    checks it still lands. A sibling skill shipped a dangling index entry for weeks because its
    linter masked inline code and never saw the links at all.
    """

    #: This skill cites files two ways, and both can dangle. Markdown links are the obvious
    #: one; the negative control below immediately showed there is only ONE of those, because
    #: the prose overwhelmingly cites paths as inline code (`references/foo.md`,
    #: `tests/promtool/rules_test.yml`). A checker that only understood markdown links would
    #: have reported success while covering a single pointer.
    PATH_EXTS = (".md", ".yml", ".yaml", ".py", ".sh", ".json")

    def _citations(self, path):
        """(target, kind) for every file path this document points at."""
        body = path.read_text(encoding="utf-8")
        out = []
        for m in re.finditer(r"\[[^\]]+\]\((?!https?://|#|mailto:)([^)#]+)\)", body):
            out.append((m.group(1).strip(), "link"))
        for m in re.finditer(r"`([A-Za-z0-9_./-]+)`", body):
            tok = m.group(1)
            if tok.endswith(self.PATH_EXTS) and "/" in tok or tok.endswith(".md"):
                out.append((tok, "inline"))
        return out

    def _resolve(self, path, target):
        """Try every citation convention actually in use in this skill.

        Three, all legitimate: relative to the citing file (how references cite each other),
        relative to the skill root (`tests/promtool/rules_test.yml`), and a bare reference
        filename (`sli-slo-patterns.md`), which SKILL.md uses eight times and which reads
        better than the verbose form. The resolver understands the conventions rather than
        forcing the prose to be uniform -- but it does insist every one of them lands.
        """
        for base in (path.parent, SKILL_DIR, SKILL_DIR / "references"):
            if (base / target).exists():
                return True
        return False

    def test_every_cited_path_resolves(self) -> None:
        broken = []
        for path in DOC_FILES:
            for target, kind in self._citations(path):
                if not self._resolve(path, target):
                    broken.append(f"{path.name} -> {target} ({kind})")
        self.assertEqual([], broken, f"dangling path citations: {broken}")

    def test_citations_were_actually_found(self) -> None:
        """Negative control: a regex matching nothing is not a check.

        Threshold is set against the real corpus, not guessed: this skill cites well over a
        dozen paths, almost all as inline code.
        """
        total = sum(len(self._citations(p)) for p in DOC_FILES)
        self.assertGreaterEqual(
            total, 12,
            f"only {total} path citations extracted -- the regex may be broken, which would "
            f"make the resolution check above vacuous")

    def test_both_citation_styles_are_covered(self) -> None:
        """Markdown-link-only coverage would have checked exactly one pointer here."""
        kinds = {k for p in DOC_FILES for _, k in self._citations(p)}
        self.assertEqual({"link", "inline"}, kinds,
                         "both citation styles must be exercised; this skill cites paths "
                         "mostly as inline code, so dropping that arm covers almost nothing")


class CoverageDocTests(unittest.TestCase):
    """Counts in COVERAGE.md must be derived, not hand-maintained.

    It claimed "Grand Total: 100 tests" while the suite had 107. The number being wrong
    matters less than the mechanism: a count written in prose about something the repo can
    count is a duplicate fact, and the duplicate is the one that goes stale. Deleting it is
    the fix; this test is what stops it coming back.
    """

    COVERAGE = SKILL_DIR / "scripts" / "tests" / "COVERAGE.md"

    def test_coverage_doc_has_no_hand_maintained_totals(self) -> None:
        text = self.COVERAGE.read_text(encoding="utf-8")
        offenders = []
        for m in re.finditer(r"^.*?(?:grand total|golden total|total)\D{0,20}(\d+)\s*tests?.*$",
                             text, re.M | re.I):
            line = m.group(0)
            if "not written here" in line.lower() or "while the suite had" in line:
                continue          # the sentence explaining why the total was removed
            offenders.append(line.strip()[:120])
        self.assertEqual(
            [], offenders,
            "COVERAGE.md states a test total again; derive it from "
            "`pytest --collect-only` instead:\n  " + "\n  ".join(offenders))

    def test_coverage_doc_points_at_the_source_of_truth(self) -> None:
        text = self.COVERAGE.read_text(encoding="utf-8")
        self.assertIn("--collect-only", text,
                      "COVERAGE.md should tell the reader how to get the real count")

    def test_every_test_file_is_described(self) -> None:
        """A new test file that COVERAGE.md never mentions is undocumented coverage."""
        text = self.COVERAGE.read_text(encoding="utf-8")
        for path in sorted((SKILL_DIR / "scripts" / "tests").glob("test_*.py")):
            self.assertIn(path.name, text,
                          f"{path.name} is not described in COVERAGE.md")


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
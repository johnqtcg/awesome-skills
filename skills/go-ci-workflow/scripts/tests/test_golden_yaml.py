"""Structural validation of EVERY workflow YAML block in the reference docs.

The references are this skill's most-copied artifacts; a defect in them
propagates into real repositories. Every fenced ``yaml`` block in every
``references/*.md`` must parse, and must comply with the rules SKILL.md itself
mandates.

Scope history — this is the load-bearing change of this file. An earlier
version hardcoded three "golden example" files, so 34 of 39 blocks were never
parsed. A mutation audit proved the consequence: an identical YAML syntax error
was caught in ``golden-examples.md`` and silently ignored in
``workflow-quality-guide.md``. Worse, that always-loaded guide mandated
``timeout-minutes`` on every job while not one of its own 17 examples set it —
the rule was enforced exactly where the test looked and nowhere else. Never
narrow this glob back to a subset of the artifacts it protects.

Blocks are classified before rules are applied, because a rule that is right
for a complete workflow is wrong for an illustrative fragment:

* ``complete``  — declares BOTH ``jobs:`` and a trigger. Full rules.
* ``jobmap``    — job definitions (``runs-on``) shown without the surrounding
                  workflow, or a ``jobs:`` map with no trigger. Job-level rules
                  only: ``permissions``, ``name`` and ``concurrency``
                  legitimately live at workflow level, which the fragment does
                  not show.
* ``steps``     — a sequence of steps. Step-level rules only.
* other         — config fragments (``on:``, ``permissions:``, ``strategy:``).
                  Parse + text-level rules only.
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

SKILL_DIR = Path(__file__).resolve().parents[2]
REF_DIR = SKILL_DIR / "references"

YAML_BLOCK_RE = re.compile(r"```yaml\n(.*?)```", re.DOTALL)

# PyYAML (YAML 1.1) parses the bare key `on` as boolean True.
TRIGGER_KEYS = ("on", True)

HARDCODED_GO_VERSION_RE = re.compile(r"go-version:\s*['\"]?1\.\d")
# A matrix-driven go-version is the one legitimate way to not use
# go-version-file (library repos testing several Go releases — §13).
MATRIX_GO_VERSION_RE = re.compile(r"go-version:\s*\$\{\{\s*matrix\.")

# The fork guard, as it must appear in a parsed `if:` expression. Anchored to
# the comparison itself: an earlier substring-on-whole-file assertion stayed
# green when the YAML guard was inverted, because the prose sentence explaining
# the guard still contained the original `==`.
FORK_GUARD_RE = re.compile(
    r"github\.event\.pull_request\.head\.repo\.full_name\s*(?P<op>==|!=)\s*github\.repository"
)
TRUSTED_EVENT_RE = re.compile(r"github\.event_name\s*==\s*'(push|schedule|workflow_dispatch)'")
SECRET_REF_RE = re.compile(r"\$\{\{\s*secrets\.")


def ref_files() -> list[Path]:
    return sorted(REF_DIR.glob("*.md"))


def yaml_blocks() -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    for path in ref_files():
        for i, match in enumerate(YAML_BLOCK_RE.finditer(path.read_text()), 1):
            blocks.append((f"{path.name}#block{i}", match.group(1)))
    return blocks


def parsed_blocks() -> list[tuple[str, str, object]]:
    out = []
    for name, text in yaml_blocks():
        out.append((name, text, yaml.safe_load(text)))
    return out


def complete_workflows() -> list[tuple[str, str, dict]]:
    """A block is a complete workflow only if it declares BOTH `jobs:` and a
    trigger. A `jobs:` key alone marks an illustrative fragment (e.g. the
    job-level `permissions` example), which cannot carry workflow-level keys.
    This is a derivable discriminator — no opt-out marker a future edit could
    abuse to exempt a real workflow."""
    return [
        (n, t, d) for n, t, d in parsed_blocks()
        if isinstance(d, dict) and "jobs" in d and any(k in d for k in TRIGGER_KEYS)
    ]


def is_reusable(doc: dict) -> bool:
    """`on: workflow_call` workflows inherit `name` and `permissions` from the
    caller, so those two rules do not apply to them."""
    return "workflow_call" in triggers_of(doc)


def job_definitions() -> list[tuple[str, str, dict]]:
    """(block, job_id, job) for every job in a complete workflow or a jobmap
    fragment. Reusable-workflow caller jobs (`uses:`) are excluded — they
    cannot set `runs-on` or `timeout-minutes`."""
    out = []
    for name, _text, doc in parsed_blocks():
        if not isinstance(doc, dict):
            continue
        jobs = doc.get("jobs")
        if not isinstance(jobs, dict):
            jobs = {k: v for k, v in doc.items()
                    if isinstance(v, dict) and "runs-on" in v}
        for job_id, job in jobs.items():
            if isinstance(job, dict) and "uses" not in job:
                out.append((name, job_id, job))
    return out


def triggers_of(doc: dict) -> set:
    for key in TRIGGER_KEYS:
        if key in doc:
            trig = doc[key]
            if isinstance(trig, dict):
                return set(trig.keys())
            if isinstance(trig, list):
                return set(trig)
            return {trig}
    return set()


@unittest.skipUnless(yaml is not None, "PyYAML not installed (pip install -r requirements.txt)")
class GoldenYamlTests(unittest.TestCase):

    # --- scope guard: the reason this file exists ---

    def test_every_reference_file_is_in_scope(self) -> None:
        """The validator must cover every reference doc, not a chosen subset."""
        covered = {n.split("#")[0] for n, _ in yaml_blocks()}
        with_yaml = {p.name for p in ref_files() if "```yaml" in p.read_text()}
        self.assertEqual(with_yaml, covered,
                         "a reference file containing YAML is not being validated")
        self.assertGreaterEqual(len(yaml_blocks()), 30,
                                "block count collapsed — check the fence regex")

    def test_every_yaml_block_parses(self) -> None:
        for name, text in yaml_blocks():
            try:
                yaml.safe_load(text)
            except yaml.YAMLError as exc:
                self.fail(f"{name}: yaml does not parse: {exc}")

    def test_complete_workflows_found(self) -> None:
        self.assertGreaterEqual(len(complete_workflows()), 5,
                                "expected at least 5 complete workflows across the references")

    # --- job-level rules (complete workflows AND jobmap fragments) ---

    def test_workflow_top_level_shape(self) -> None:
        for name, _text, doc in complete_workflows():
            self.assertTrue(doc["jobs"], f"{name}: workflow has no jobs")
            if is_reusable(doc):
                continue
            self.assertIn("name", doc, f"{name}: workflow missing name")

    def test_every_job_has_timeout_and_runner(self) -> None:
        """SKILL.md: 'Set timeout-minutes on every job.'"""
        checked = 0
        for name, job_id, job in job_definitions():
            self.assertIn("runs-on", job, f"{name}:{job_id} missing runs-on")
            self.assertIn("timeout-minutes", job, f"{name}:{job_id} missing timeout-minutes")
            self.assertIsInstance(job["timeout-minutes"], int,
                                  f"{name}:{job_id} timeout-minutes must be a number")
            checked += 1
        self.assertGreaterEqual(checked, 15, "job discovery collapsed — rule no longer bites")

    def test_runner_labels_are_real(self) -> None:
        """A typo'd runner label queues forever instead of failing fast."""
        allowed = re.compile(r"^(ubuntu|windows|macos)-(latest|\d{2}\.\d{2}|\d{2}|\d+\.\d+)"
                             r"(-arm|-large|-xlarge)?$|^self-hosted$|^\$\{\{")
        for name, job_id, job in job_definitions():
            runs_on = job["runs-on"]
            labels = runs_on if isinstance(runs_on, list) else [runs_on]
            for label in labels:
                if isinstance(label, dict):  # {group: ..., labels: ...}
                    continue
                self.assertRegex(str(label), allowed, f"{name}:{job_id} suspicious runs-on: {label}")

    # --- permissions: assert VALUES, not just key presence ---

    def test_permissions_declared(self) -> None:
        """Minimal-permissions rule: workflow-level or every-job permissions."""
        for name, _text, doc in complete_workflows():
            if "permissions" in doc or is_reusable(doc):
                continue
            for job_id, job in doc["jobs"].items():
                self.assertIn("permissions", job,
                              f"{name}: no workflow-level permissions and job {job_id} has none")

    def test_no_contents_write_in_any_example(self) -> None:
        """`contents: write` lets a workflow push to the repo. No CI example
        needs it — the release-job escalation is documented in the prose table
        in github-actions-advanced-patterns.md §1, deliberately not as copyable
        YAML. Presence-only assertions used to let read→write through."""
        offenders = []

        def walk(node, path):
            if isinstance(node, dict):
                perms = node.get("permissions")
                if isinstance(perms, dict) and perms.get("contents") == "write":
                    offenders.append(path)
                for k, v in node.items():
                    walk(v, f"{path}.{k}")
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f"{path}[{i}]")

        for name, _text, doc in parsed_blocks():
            walk(doc, name)
        self.assertFalse(offenders, f"contents: write in example YAML: {offenders}")

    def test_declared_permission_scopes_are_real(self) -> None:
        valid = {
            "actions", "attestations", "checks", "contents", "deployments",
            "discussions", "id-token", "issues", "models", "packages", "pages",
            "pull-requests", "repository-projects", "security-events", "statuses",
        }
        valid_values = {"read", "write", "none"}
        for name, _text, doc in parsed_blocks():
            if not isinstance(doc, dict):
                continue
            for holder in [doc] + [j for j in doc.get("jobs", {}).values()
                                   if isinstance(j, dict)]:
                perms = holder.get("permissions")
                if not isinstance(perms, dict):
                    continue
                for scope, value in perms.items():
                    self.assertIn(scope, valid, f"{name}: unknown permission scope {scope!r}")
                    self.assertIn(value, valid_values,
                                  f"{name}: permission {scope}={value!r} is not read/write/none")

    # --- concurrency: cancel PR runs, never protected-branch runs ---

    def test_cancel_in_progress_is_event_gated_everywhere(self) -> None:
        """Checked on EVERY block, not only complete workflows. The guide's §2
        `concurrency:` snippet is a standalone fragment; scoping this rule to
        complete workflows left the most-copied snippet of all unguarded."""
        seen = 0
        for name, _text, doc in parsed_blocks():
            if not isinstance(doc, dict):
                continue
            conc = doc.get("concurrency", doc if "cancel-in-progress" in doc else None)
            if not isinstance(conc, dict) or "cancel-in-progress" not in conc:
                continue
            seen += 1
            value = conc["cancel-in-progress"]
            self.assertNotEqual(False, value,
                                f"{name}: cancel-in-progress: false is pointless — remove it")
            self.assertIn(
                "pull_request", str(value),
                f"{name}: cancel-in-progress must be gated on the PR event, or a "
                "merged commit can end up with no completed run (advanced-patterns §8)",
            )
        self.assertGreaterEqual(seen, 5, "concurrency examples disappeared from the references")

    def test_pull_request_workflows_declare_concurrency(self) -> None:
        """Without it, every push to a PR branch starts a duplicate run. Deleting
        the block outright used to pass every test."""
        for name, _text, doc in complete_workflows():
            if "pull_request" not in triggers_of(doc) or is_reusable(doc):
                continue
            self.assertIn("concurrency", doc,
                          f"{name}: pull_request workflow without concurrency control")

    def test_declared_go_versions_are_plausible(self) -> None:
        """A matrix is the one place a literal Go version is allowed (§13), so
        it is also the one place a nonsense version can hide."""
        for name, text in yaml_blocks():
            for literal in re.findall(r"['\"](\d+)\.(\d+)['\"]", text):
                major, minor = int(literal[0]), int(literal[1])
                self.assertEqual(1, major, f"{name}: Go {major}.{minor} does not exist")
                self.assertTrue(16 <= minor <= 40,
                                f"{name}: implausible Go version 1.{minor}")

    # --- secrets vs fork PRs ---

    def test_fork_guard_comparison_is_not_inverted(self) -> None:
        """Anchored to the parsed `if:` value. Inverting the guard to `!=` runs
        the secret-bearing job for forks ONLY — the exact inversion a
        whole-file substring assertion could not see."""
        seen = 0
        for name, _text, doc in parsed_blocks():
            for cond in _all_if_conditions(doc):
                for match in FORK_GUARD_RE.finditer(cond):
                    seen += 1
                    self.assertEqual("==", match.group("op"),
                                     f"{name}: fork guard inverted — grants forks the guarded job")
        self.assertGreaterEqual(seen, 2, "fork-guard examples disappeared from the references")

    def test_secret_bearing_jobs_are_guarded_against_forks(self) -> None:
        """A `pull_request`-triggered workflow that hands a secret to a job or
        step must guard it. Fork PRs receive empty secrets, so an unguarded job
        also fails confusingly rather than skipping."""
        for name, _text, doc in complete_workflows():
            if "pull_request" not in triggers_of(doc):
                continue
            for job_id, job in doc["jobs"].items():
                if not isinstance(job, dict):
                    continue
                job_guard = str(job.get("if", ""))
                for holder, label in _secret_holders(job, job_id):
                    guard = job_guard + " " + str(holder.get("if", ""))
                    self.assertTrue(
                        FORK_GUARD_RE.search(guard) or TRUSTED_EVENT_RE.search(guard),
                        f"{name}:{label} references a secret on a pull_request "
                        f"workflow without a fork guard",
                    )

    # --- tool and action pinning ---

    def test_no_latest_tool_installs(self) -> None:
        """SKILL.md: pin go install tool versions exactly, never @latest."""
        for name, text in yaml_blocks():
            self.assertNotIn("@latest", text, f"{name}: tool installed @latest")

    def test_no_hardcoded_go_version(self) -> None:
        """SKILL.md: use go-version-file: go.mod — never hardcode Go version.
        Exception: a library matrix over Go releases (§13)."""
        for name, text in yaml_blocks():
            if MATRIX_GO_VERSION_RE.search(text):
                continue
            match = HARDCODED_GO_VERSION_RE.search(text)
            self.assertIsNone(match, f"{name}: hardcoded Go version: {match.group(0) if match else ''}")
            # Only when the block actually configures setup-go. A block that
            # shows bare `uses:` lines (the §16 SHA-pinning example) is not
            # demonstrating Go setup and has nothing to configure.
            if "actions/setup-go@" in text and "with:" in text:
                self.assertIn("go-version-file", text,
                              f"{name}: setup-go without go-version-file")

    def test_matrix_module_setup_has_cache_dependency_path(self) -> None:
        """A setup-go step reading a matrix/subdirectory go.mod must also set
        cache-dependency-path, or every module shares one wrong cache key
        (see workflow-quality-guide.md §3)."""
        for name, text in yaml_blocks():
            if re.search(r"go-version-file:\s*\$\{\{\s*matrix\.", text):
                self.assertIn(
                    "cache-dependency-path", text,
                    f"{name}: matrix go-version-file without cache-dependency-path",
                )

    def test_actionlint_when_available(self) -> None:
        if not shutil.which("actionlint"):
            self.skipTest("actionlint not installed")
        for name, doc_text, doc in parsed_blocks():
            if not (isinstance(doc, dict) and "jobs" in doc):
                continue
            with tempfile.TemporaryDirectory() as tmp:
                wf_dir = Path(tmp) / ".github" / "workflows"
                wf_dir.mkdir(parents=True)
                (wf_dir / "golden.yml").write_text(doc_text)
                proc = subprocess.run(
                    ["actionlint", "-no-color"],
                    cwd=tmp,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(0, proc.returncode, f"{name}: actionlint:\n{proc.stdout}")


def _all_if_conditions(node) -> list[str]:
    """Every `if:` expression anywhere in a parsed block."""
    found: list[str] = []
    if isinstance(node, dict):
        if "if" in node:
            found.append(str(node["if"]))
        for value in node.values():
            found.extend(_all_if_conditions(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_all_if_conditions(value))
    return found


def _secret_holders(job: dict, job_id: str) -> list[tuple[dict, str]]:
    """Job and steps that reference `${{ secrets.* }}`, with a label."""
    holders = []
    job_env = yaml.safe_dump(job.get("env", {}) or {})
    if SECRET_REF_RE.search(job_env):
        holders.append((job, job_id))
    for i, step in enumerate(job.get("steps") or []):
        if isinstance(step, dict) and SECRET_REF_RE.search(yaml.safe_dump(step)):
            holders.append((step, f"{job_id}.step[{i}]"))
    return holders


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Repo-aware README linter — grades a produced README against the repository it describes.

Why this exists. The golden-scenario layer asserted that fixture JSON contained the
strings the fixture itself declared, and that SKILL.md mentioned matching keywords.
That proves a rule is *written down*; it cannot tell a README that is grounded in the
repo from one that invented its commands. Every check below needs both halves — the
document and the repository — so it can only be answered by looking at real files.

Two entry points:

    scan_repo(root)                 -> RepoFacts   (runs discover_readme_needs.sh, walks the tree)
    lint(readme_text, facts)        -> [Finding]

CLI:

    python3 lint_readme.py <repo-dir> [readme-path] [--type=lightweight]

`--type` overrides the effective project type when the audience gate forced a mode the
script cannot observe. Without it, the type comes from discovery's `project_type
effective` line, which is the single answer generation and this linter must share.

Exit status: 0 when no critical finding, 1 otherwise. Stdlib only.

Routing is NOT reimplemented here: scan_repo shells out to discover_readme_needs.sh and
parses its TSV, so the linter and the skill's own discovery step can never disagree about
what kind of project this is.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DISCOVER = SCRIPT_DIR / "discover_readme_needs.sh"

# Severity drives the exit status and the Critical tier of the skill's scorecard.
# "critical" == the README asserts something the repository does not support.
CRITICAL = "critical"
STANDARD = "standard"


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    message: str
    evidence: str = ""

    def __str__(self) -> str:
        tail = f"  [{self.evidence}]" if self.evidence else ""
        return f"{self.severity.upper():8} {self.code}  {self.message}{tail}"


@dataclass
class RepoFacts:
    root: Path
    # `project_type` is the EFFECTIVE type — what generation, the output contract, and
    # this linter must all agree on. `base_type` is the language/layout classification
    # before the lightweight promotion, kept because it still selects command snippets.
    project_type: str = "unknown"
    base_type: str = "unknown"
    verdict: str = "DEGRADED"
    make_targets: set = field(default_factory=set)
    npm_scripts: set = field(default_factory=set)
    env_vars: set = field(default_factory=set)
    workflows: set = field(default_factory=set)
    paths: set = field(default_factory=set)
    entrypoints: list = field(default_factory=list)
    license_type: str = ""
    has_license: bool = False
    has_go_mod: bool = False
    has_cargo: bool = False
    has_python: bool = False
    has_package_json: bool = False
    has_makefile: bool = False
    has_dockerfile: bool = False
    has_compose: bool = False
    has_codecov: bool = False
    has_coveralls: bool = False
    has_env_example: bool = False
    test_file_count: int = 0
    has_benchmarks: bool = False
    has_coverage_artifact: bool = False
    # Numbers the repository actually commits, as strings ("80", "92.4").
    # A README percentage is only defensible if it appears here.
    coverage_numbers: set = field(default_factory=set)
    # True only when a committed file contains benchmark OUTPUT (a line with
    # ns/op), not merely a `func Benchmark…` declaration.
    has_benchmark_output: bool = False


# ── Repository scan ─────────────────────────────────────────────

_SKIP_DIRS = {".git", "node_modules", "vendor", "target", "dist", ".venv", "__pycache__"}


def _run_discovery(root: Path) -> str:
    proc = subprocess.run(
        ["bash", str(DISCOVER)], cwd=str(root),
        capture_output=True, text=True, timeout=120,
    )
    if "=== discovery complete ===" not in proc.stdout:
        raise RuntimeError(
            f"discovery script did not complete in {root}: rc={proc.returncode} "
            f"stderr={proc.stderr[:400]!r}"
        )
    return proc.stdout


def _tsv(out: str) -> list:
    rows = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            rows.append(tuple(parts))
    return rows


def _csv_set(value: str) -> set:
    if not value or value in {"none", "not specified", "unknown"}:
        return set()
    return {v.strip() for v in value.split(",") if v.strip()}


def scan_repo(root, project_type: str = "") -> RepoFacts:
    """Scan `root`. Pass `project_type` to override discovery's effective type — the
    audience gate is a human input the script cannot observe, so a caller who has
    decided "internal contributors only" can force lightweight."""
    root = Path(root).resolve()
    facts = RepoFacts(root=root)

    for dim, key, value in _tsv(_run_discovery(root)):
        if (dim, key) == ("project_type", "detected"):
            facts.base_type = value
            # `effective` overrides this below when discovery promotes lightweight.
            # Reading `detected` here keeps the linter working against an older
            # script that predates the effective line.
            facts.project_type = value
        elif (dim, key) == ("project_type", "effective"):
            facts.project_type = value
        elif (dim, key) == ("verdict", "status"):
            facts.verdict = value
        elif (dim, key) == ("build", "make_targets"):
            facts.make_targets = _csv_set(value)
        elif (dim, key) == ("build", "makefile"):
            facts.has_makefile = value == "true"
        elif (dim, key) == ("build", "package_json_scripts"):
            facts.npm_scripts = _csv_set(value)
        elif (dim, key) == ("build", "dockerfile"):
            facts.has_dockerfile = value == "true"
        elif (dim, key) == ("build", "docker_compose"):
            facts.has_compose = value == "true"
        elif (dim, key) == ("config", "env_vars"):
            facts.env_vars = _csv_set(value)
        elif (dim, key) == ("config", "env_example"):
            facts.has_env_example = value == "true"
        elif (dim, key) == ("ci", "workflow_file"):
            facts.workflows.add(Path(value).name)
        elif (dim, key) == ("community", "license_type"):
            facts.license_type = value
        elif dim == "community" and key.startswith("LICENSE") and value == "true":
            facts.has_license = True
        elif (dim, key) == ("quality", "codecov"):
            facts.has_codecov = value == "true"
        elif (dim, key) == ("quality", "coveralls"):
            facts.has_coveralls = value == "true"
        elif (dim, key) == ("quality", "test_files"):
            facts.test_file_count = int(value or 0)
        elif dim == "entrypoint" and key != "count":
            facts.entrypoints.append((key, value))

    if project_type:
        facts.project_type = project_type

    facts.has_go_mod = (root / "go.mod").is_file() or (root / "go.work").is_file()
    facts.has_cargo = (root / "Cargo.toml").is_file()
    facts.has_python = (root / "pyproject.toml").is_file() or (root / "setup.py").is_file()
    facts.has_package_json = (root / "package.json").is_file()

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        rel_dir = Path(dirpath).relative_to(root)
        if str(rel_dir) != ".":
            facts.paths.add(str(rel_dir))
        for name in filenames:
            facts.paths.add(str(rel_dir / name) if str(rel_dir) != "." else name)

    facts.has_coverage_artifact = (
        facts.has_codecov
        or facts.has_coveralls
        or any(t in facts.make_targets for t in ("cover", "coverage", "test-cover"))
        or any("cover" in s for s in facts.npm_scripts)
    )
    facts.coverage_numbers = _coverage_numbers(root, facts.paths)
    facts.has_benchmarks = _has_benchmarks(root, facts.paths)
    facts.has_benchmark_output = _has_benchmark_output(root, facts.paths)
    return facts


_COVERAGE_CONFIGS = (".codecov.yml", "codecov.yml", ".coveralls.yml", "Makefile",
                     "sonar-project.properties", ".github/workflows")


def _coverage_numbers(root: Path, paths: set) -> set:
    """Percentages the repo itself commits — a configured target or a threshold gate.

    The presence of `.codecov.yml` justifies a coverage *badge* and lets a README
    state the configured *target*. It does not license an arbitrary measured number,
    which was the first false PASS: `99% coverage` sailed through on a repo whose
    config says `target: 80%`.
    """
    found = set()
    for rel in sorted(paths):
        if not any(rel == c or rel.startswith(c) for c in _COVERAGE_CONFIGS):
            continue
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in re.finditer(r"(?i)(?:target|threshold|min[_-]?coverage|fail[_-]?under)"
                             r"\s*[:=]\s*['\"]?(\d{1,3}(?:\.\d+)?)\s*%?", text):
            found.add(m.group(1).rstrip("0").rstrip(".") if "." in m.group(1) else m.group(1))
        for m in re.finditer(r"(?i)coverage[^\n]{0,30}?(\d{1,3}(?:\.\d+)?)\s*%", text):
            found.add(m.group(1))
    return found


def _has_benchmarks(root: Path, paths: set) -> bool:
    """A benchmark function exists — enough to document `go test -bench`, never
    enough to quote a number."""
    for rel in paths:
        if not rel.endswith(("_test.go", "_test.py", ".bench.js", ".bench.ts")):
            continue
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if re.search(r"func Benchmark\w+\(|def test_.*benchmark|\bbench\b", text):
            return True
    return any(rel.startswith(("benchmarks", "bench")) for rel in paths)


def _has_benchmark_output(root: Path, paths: set) -> bool:
    """A committed file containing benchmark *results*.

    Second false PASS: a repo with `func BenchmarkFoo` accepted `999999 ns/op` in its
    README. A benchmark result is a property of the machine that produced it, so the
    only thing that makes it citable is the repo committing that output.
    """
    for rel in paths:
        if rel.endswith((".go", ".py", ".js", ".ts", ".rs")):
            continue  # source declaring a benchmark is not its output
        if not re.search(r"(?i)bench|perf", rel):
            continue
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            continue
        if re.search(r"\d\s*(ns/op|sec/op|B/op|allocs/op)", text):
            return True
    return False


# ── README parsing ──────────────────────────────────────────────

_FENCE = re.compile(r"^([ \t]*)(`{3,}|~{3,})[ \t]*([^\s`]*)", re.MULTILINE)


def code_blocks(text: str):
    """Yield (language, body). Handles nested blocks by matching fence length."""
    lines = text.splitlines()
    out, i = [], 0
    while i < len(lines):
        m = re.match(r"^\s*(`{3,}|~{3,})\s*([^\s`]*)\s*$", lines[i])
        if not m:
            i += 1
            continue
        fence, lang = m.group(1), m.group(2).lower()
        j, body = i + 1, []
        while j < len(lines):
            close = re.match(r"^\s*(`{3,}|~{3,})\s*$", lines[j])
            if close and close.group(1)[0] == fence[0] and len(close.group(1)) >= len(fence):
                break
            body.append(lines[j])
            j += 1
        out.append((lang, "\n".join(body)))
        i = j + 1
    return out


def strip_code(text: str) -> str:
    """Prose only — code fences removed, so path/metric checks do not fire on samples."""
    return re.sub(r"(?ms)^\s*(`{3,}|~{3,}).*?^\s*\1\s*$", "\n", text)


SHELL_LANGS = {"bash", "sh", "shell", "console", "zsh", "shell-session", ""}


# Chained/piped invocations are separate commands. Matching only the head of the line
# meant `make test && make deploy` checked `test` and never saw the undefined `deploy`.
_CHAIN = re.compile(r"\s*(?:&&|\|\||;|\||\bthen\b)\s*")


def shell_commands(text: str) -> list:
    cmds = []
    for lang, body in code_blocks(text):
        if lang not in SHELL_LANGS:
            continue
        for raw in body.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            line = re.sub(r"^\$\s+", "", line)
            if line.startswith(("//", "<!--")):
                continue
            line = line.rstrip("\\").strip()
            for part in _CHAIN.split(line):
                part = part.strip()
                if part and not part.startswith("#"):
                    cmds.append(part)
    return cmds


def headings(text: str) -> list:
    return [
        (len(m.group(1)), m.group(2).strip())
        for m in re.finditer(r"^(#{1,6})\s+(.+?)\s*$", strip_code(text), re.MULTILINE)
    ]


def _slug(label: str) -> str:
    s = label.strip().lower()
    s = re.sub(r"[`*_]", "", s)
    s = re.sub(r"[^\w\s一-鿿-]", "", s)
    return re.sub(r"[\s]+", "-", s).strip("-")


def section_body(text: str, keyword: str) -> str:
    """Text under the first heading whose title contains `keyword`, down to the next
    heading of the SAME OR HIGHER level.

    Stopping at the next heading of *any* level was the fourth false PASS: adding a
    `### Variables` subheading under `## Configuration` truncated the body to nothing,
    so the env-var table below it was never checked.
    """
    pattern = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
    marks = list(pattern.finditer(text))
    for idx, m in enumerate(marks):
        if keyword.lower() not in m.group(2).lower():
            continue
        level = len(m.group(1))
        end = len(text)
        for nxt in marks[idx + 1:]:
            if len(nxt.group(1)) <= level:
                end = nxt.start()
                break
        return text[m.end():end]
    return ""


# ── Required sections, by project type ──────────────────────────
# Keep in sync with SKILL.md §Structure Policy (guarded by
# tests/test_skill_contract.py::TestRequiredSectionMatrix).

REQUIRED_SECTIONS = {
    "service": ["quick start", "prerequisites", "structure", "commands", "configuration",
                "testing", "maintenance"],
    "cli": ["installation", "usage", "commands", "testing", "maintenance"],
    "library": ["installation", "usage", "api", "testing", "maintenance"],
    "monorepo": ["repository overview", "quick start", "commands", "structure", "maintenance"],
    "lightweight": ["quick start", "commands", "structure", "testing", "maintenance"],
}

# The subset whose absence makes the README unusable rather than incomplete: the path
# from "landed here" to "ran it". Missing one is CRITICAL (R009); missing any other
# required section is STANDARD (R012).
PRIMARY_SECTIONS = {
    "service": ("quick start",),
    "cli": ("installation", "usage"),
    "library": ("installation", "usage"),
    "monorepo": ("repository overview", "quick start"),
    "lightweight": ("quick start",),
}

SECTION_ALIASES = {
    "quick start": ["quick start", "quickstart", "getting started", "快速开始", "快速上手"],
    "prerequisites": ["prerequisite", "requirements", "前置", "环境要求", "依赖要求"],
    "structure": ["structure", "layout", "项目结构", "目录结构", "repository overview", "仓库概览"],
    "commands": ["command", "makefile targets", "scripts", "常用命令", "命令"],
    "configuration": ["configuration", "config", "environment", "配置", "环境变量"],
    "testing": ["test", "quality", "测试", "质量"],
    "maintenance": ["maintenance", "update this readme", "维护", "文档维护"],
    "installation": ["install", "安装", "获取"],
    "usage": ["usage", "example", "quick start", "快速开始", "用法", "使用"],
    "api": ["api", "reference", "接口"],
    "repository overview": ["repository overview", "modules", "packages", "仓库概览", "模块"],
}


def missing_sections(text: str, project_type: str) -> list:
    required = REQUIRED_SECTIONS.get(project_type)
    if not required:
        return []
    titles = [t.lower() for _, t in headings(text)]
    blob = "\n".join(titles)
    missing = []
    for item in required:
        if not any(alias in blob for alias in SECTION_ALIASES.get(item, [item])):
            missing.append(item)
    return missing


# ── Checks ──────────────────────────────────────────────────────

PLACEHOLDER_PATTERNS = [
    (r"\{[A-Z][A-Z0-9_]{2,}\}", "unfilled template placeholder"),
    (r"<[A-Z][A-Z0-9_]{2,}>", "unfilled angle-bracket placeholder"),
    (r"\bOWNER/REPO\b", "literal OWNER/REPO in a URL"),
    (r"\b(TODO|TBD|FIXME|XXX)\b", "scaffold marker"),
    (r"\byour-(org|repo|project|company)\b", "template stand-in"),
    (r"\blorem ipsum\b", "filler text"),
]

PROCESS_LABEL_PATTERNS = [
    (r"\bNot verified\b", "verification-state label"),
    (r"not executed in this environment", "verification-state label"),
    (r"\bVerified\b", "verification-state label"),
    (r"\bPASS/FAIL\b", "scorecard language"),
    # A bare mention of "scorecard" is not the defect — self-reporting one is. The
    # earlier bare-word pattern flagged a documentation repo that merely *describes*
    # skills having scorecards.
    (r"(?m)^#{1,6}[^\n]*\bscorecard\b", "scorecard section in the document"),
    (r"\bscorecard\b[^\n]{0,40}(PASS|FAIL|\d+/\d+)", "scorecard result"),
    (r"Critical:\s*\d+/\d+", "scorecard output"),
    (r"\bdegraded:\s*(true|false)\b", "output-contract field"),
    (r"未验证|未执行", "verification-state label"),
]


def _check_commands(text: str, f: RepoFacts) -> list:
    out = []
    for cmd in shell_commands(text):
        head = cmd.split("#", 1)[0].strip()
        if not head:
            continue

        m = re.match(r"^make\s+(?:-C\s+\S+\s+)?([A-Za-z0-9_.-]+)", head)
        if m:
            target = m.group(1)
            if not f.has_makefile:
                out.append(Finding("R001", CRITICAL,
                                   "README runs `make` but the repo has no Makefile", head))
            elif target not in f.make_targets:
                out.append(Finding("R001", CRITICAL,
                                   f"make target {target!r} is not defined in the Makefile", head))
            continue

        m = re.match(r"^(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?([A-Za-z0-9_:-]+)", head)
        if m:
            script = m.group(1)
            if script in {"install", "ci", "i", "add", "exec", "init", "create", "publish"}:
                continue
            if not f.has_package_json:
                out.append(Finding("R002", CRITICAL,
                                   "README runs an npm script but there is no package.json", head))
            elif script not in f.npm_scripts:
                out.append(Finding("R002", CRITICAL,
                                   f"npm script {script!r} is not defined in package.json", head))
            continue

        toolchain = [
            (r"^go\s+(build|test|run|vet|install|generate|mod|tool)\b", f.has_go_mod, "go.mod"),
            (r"^cargo\s+\w+", f.has_cargo, "Cargo.toml"),
            (r"^(pytest|poetry|pip install -e|python -m pytest|tox|hatch)\b", f.has_python,
             "pyproject.toml/setup.py"),
            (r"^docker\s+compose\b|^docker-compose\b", f.has_compose, "docker-compose.yml"),
            (r"^docker\s+build\b", f.has_dockerfile, "Dockerfile"),
        ]
        for pattern, supported, need in toolchain:
            if re.match(pattern, head) and not supported:
                out.append(Finding("R001", CRITICAL,
                                   f"command needs {need}, which is not in the repo", head))
                break
    return out


def _check_env_vars(text: str, f: RepoFacts) -> list:
    body = section_body(text, "configuration") or section_body(text, "配置") \
        or section_body(text, "environment")
    if not body:
        return []
    cited = set()
    for row in re.finditer(r"^\|\s*`?([A-Z][A-Z0-9_]{2,})`?\s*\|", body, re.MULTILINE):
        cited.add(row.group(1))
    if not cited:
        return []
    if not f.has_env_example and not any(p.startswith("config") for p in f.paths):
        return [Finding("R003", CRITICAL,
                        "Configuration table lists variables but the repo has no "
                        ".env.example or config/ to source them from",
                        ", ".join(sorted(cited)[:5]))]
    unknown = sorted(v for v in cited if v not in f.env_vars) if f.env_vars else []
    if unknown:
        return [Finding("R003", CRITICAL,
                        "Configuration table lists variables absent from .env.example",
                        ", ".join(unknown[:5]))]
    return []


_PATH_TOKEN = re.compile(r"`([A-Za-z0-9_.][\w./*-]*/[\w./*-]*)`")

# Build outputs legitimately do not exist until the build runs; flagging them as
# missing would punish an accurate README.
_BUILD_OUTPUT = re.compile(r"^\.?/?(bin|build|dist|out|target|coverage|tmp|node_modules|vendor)(/|$)")


_HAS_EXT = re.compile(r"\.[A-Za-z0-9]{1,6}$")


def _check_paths(text: str, f: RepoFacts) -> list:
    """R004 is CRITICAL, so it must not fire on things that only look like paths.

    Three exclusions come from running this linter against real READMEs:
      - `fmt/test/lint/build/run` — slash-separated *alternatives*, not a path.
      - `.github/workflows/ci.yml` cited next to an external repository URL — a real
        path, in someone else's repo.
      - `./bin/api` — a build output that does not exist until the build runs.
    """
    prose = strip_code(text)
    top_level = {p.split("/", 1)[0] for p in f.paths}
    out, seen = [], set()
    for line in prose.splitlines():
        # Only a path that FOLLOWS the URL is plausibly that repository's — the
        # earlier line-wide exemption let any URL anywhere on the line launder a
        # fabricated local path.
        url = re.search(r"https?://\S+", line)
        url_end = url.end() if url else None
        for m in _PATH_TOKEN.finditer(line):
            raw = m.group(1)
            external_ref = url_end is not None and m.start() > url_end
            if "://" in raw or raw.startswith(("http", "-")) or " " in raw:
                continue
            if "{" in raw or "<" in raw:
                continue  # placeholder residue is R005's job, not a path claim
            candidate = raw.rstrip("/").split("*")[0].rstrip("/")
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            if _BUILD_OUTPUT.match(candidate):
                continue
            if candidate in f.paths:
                continue
            if any(p == candidate or p.startswith(candidate + "/") for p in f.paths):
                continue
            # Module paths and package coordinates are not filesystem paths.
            if re.match(r"^(github\.com|golang\.org|gopkg\.in|@[\w-]+)/", candidate):
                continue
            if external_ref:
                continue  # the line names another repository; the path is theirs
            segments = candidate.split("/")
            if (len(segments) >= 3 and segments[0] not in top_level
                    and not _HAS_EXT.search(candidate)):
                continue  # `fmt/test/lint/build/run`: a list, not a path
            out.append(Finding("R004", CRITICAL,
                               f"README cites path {raw!r} which does not exist in the repo",
                               raw))
    return out


def _check_placeholders(text: str) -> list:
    out = []
    for pattern, why in PLACEHOLDER_PATTERNS:
        m = re.search(pattern, text)
        if m:
            out.append(Finding("R005", CRITICAL, f"{why} left in the README", m.group(0)))
    return out


def _check_process_labels(text: str) -> list:
    prose = strip_code(text)
    out = []
    for pattern, why in PROCESS_LABEL_PATTERNS:
        m = re.search(pattern, prose, re.IGNORECASE if "\\b" not in pattern else 0)
        if m:
            out.append(Finding("R006", STANDARD,
                               f"{why} belongs in the assistant response, not the README",
                               m.group(0)))
    return out


def _sentence_around(text: str, index: int) -> str:
    start = max(text.rfind(".", 0, index), text.rfind("\n", 0, index)) + 1
    end = min(
        (i for i in (text.find(".", index), text.find("\n", index)) if i != -1),
        default=len(text),
    )
    return text[start:end]


def _check_metrics(text: str, f: RepoFacts) -> list:
    prose = text
    out = []
    # Flags go in `flags=`, never inline mid-pattern: Python rejects a `(?i)` that is
    # not at position 0 with "global flags not at the start of the expression".
    for cov in re.finditer(
        r"(?:~|about |around )?(\d{1,3}(?:\.\d+)?)\s*%[^.\n]{0,25}?coverage"
        r"|coverage[^.\n]{0,25}?(?:~|about |around )?(\d{1,3}(?:\.\d+)?)\s*%"
        r"|覆盖率[^。\n]{0,10}?(\d{1,3}(?:\.\d+)?)\s*%",
        prose,
        flags=re.IGNORECASE,
    ):
        number = next(g for g in cov.groups() if g)
        # A committed `target: 80%` licenses the sentence "the target is 80%". It does
        # not license "current coverage is 80%" — that asserts a measurement, and the
        # repo commits no measurement. Matching on the number alone conflated the two.
        sentence = _sentence_around(prose, cov.start())
        claims_measurement = bool(re.search(
            r"\b(current|currently|measured|achieved|sits at|now at|we (?:have|maintain)|"
            r"is at|actual|目前|当前|实际)\b", sentence, re.IGNORECASE))
        names_target = bool(re.search(
            r"\b(target|threshold|minimum|min|gate|goal|required|configured|floor|目标|阈值)\b",
            sentence, re.IGNORECASE))
        if number in f.coverage_numbers and names_target and not claims_measurement:
            continue
        if number in f.coverage_numbers and not claims_measurement and not names_target:
            out.append(Finding("R007", CRITICAL,
                               f"coverage percentage is ambiguous: {number}% is a "
                               f"committed target, so say so explicitly "
                               f"(\"target: {number}%\") rather than stating it bare",
                               cov.group(0).strip()))
            break
        if not f.has_coverage_artifact:
            reason = "no coverage config or target in repo"
        elif claims_measurement:
            reason = (f"this states a measured result; the repo commits target(s) "
                      f"{sorted(f.coverage_numbers) or '—'} and no coverage report")
        else:
            reason = (f"repo commits coverage target(s) "
                      f"{sorted(f.coverage_numbers) or '—'}, not this value")
        out.append(Finding("R007", CRITICAL,
                           f"coverage percentage claimed; {reason}", cov.group(0).strip()))
        break
    bench = re.search(r"\b\d[\d,.]*\s*(ns/op|sec/op|B/op|allocs/op)", prose)
    if bench and not f.has_benchmark_output:
        detail = ("a `func Benchmark…` exists but its OUTPUT is not committed"
                  if f.has_benchmarks else "no benchmark in repo")
        out.append(Finding("R007", CRITICAL,
                           f"benchmark numbers quoted; {detail}", bench.group(0).strip()))
    thr = re.search(r"\b\d[\d,.]*\s*[KkMm]?\+?\s*(TPS|QPS|RPS|req/s|requests per second|事务)", prose)
    if thr:
        out.append(Finding("R007", CRITICAL,
                           "throughput claim cannot be derived from repository files",
                           thr.group(0).strip()))
    count = re.search(r"\b(\d{1,4})\s+(tests|test cases|个测试)\b", prose)
    if count:
        out.append(Finding("R007", CRITICAL,
                           "exact test count is a run-time result, not a repository fact",
                           count.group(0).strip()))
    lat = re.search(r"\b[pP]9[59]\b[^.\n]{0,30}?\d+\s*ms", prose)
    if lat:
        out.append(Finding("R007", CRITICAL,
                           "latency percentile quoted with no load-test artifact",
                           lat.group(0).strip()))
    return out


def _check_badges(text: str, f: RepoFacts) -> list:
    out = []
    for m in re.finditer(r"!\[[^\]]*\]\((https?://[^)]+)\)", text):
        url = m.group(1)
        wf = re.search(r"/actions/workflows/([^/]+)/badge\.svg", url)
        if wf and wf.group(1) not in f.workflows:
            out.append(Finding("R008", CRITICAL,
                               f"CI badge points at workflow {wf.group(1)!r} that is not in "
                               ".github/workflows", url))
        if "codecov.io" in url and not f.has_codecov:
            out.append(Finding("R008", CRITICAL,
                               "codecov badge without a codecov config in the repo", url))
        if "coveralls" in url and not f.has_coveralls:
            out.append(Finding("R008", CRITICAL,
                               "coveralls badge without a coveralls config in the repo", url))
        if re.search(r"shields\.io/badge/license", url) and not f.has_license:
            out.append(Finding("R008", CRITICAL,
                               "license badge without a LICENSE file in the repo", url))
        if "shields.io/npm/" in url and not f.has_package_json:
            out.append(Finding("R008", CRITICAL,
                               "npm badge without a package.json in the repo", url))
    return out


def _check_toc(text: str) -> list:
    titles = {t.strip().lower() for _, t in headings(text)}
    slugs = {_slug(t) for _, t in headings(text)}
    out = []
    for m in re.finditer(r"^\s*[-*]\s+\[([^\]]+)\]\(#([\w一-鿿-]+)\)\s*$",
                         text, re.MULTILINE):
        label, anchor = m.group(1), m.group(2)
        if anchor not in slugs:
            out.append(Finding("R010", STANDARD,
                               f"ToC entry {label!r} links to #{anchor}, which no heading produces",
                               m.group(0).strip()))
        elif _slug(label) != anchor and label.strip().lower() not in titles:
            out.append(Finding("R010", STANDARD,
                               f"ToC label {label!r} does not match the heading it links to",
                               m.group(0).strip()))
    return out


def _check_double_language(text: str) -> list:
    out = []
    for _, title in headings(text):
        if re.search(r"[A-Za-z]{3,}\s*/\s*[一-鿿]", title) or \
           re.search(r"[一-鿿]\s*/\s*[A-Za-z]{3,}", title):
            out.append(Finding("R011", STANDARD,
                               "double-language heading; pick one language per heading", title))
    return out


def _check_unknown_type(f: RepoFacts) -> list:
    """An undetermined type silently disabled every section check.

    `REQUIRED_SECTIONS.get("unknown")` returns None, so `missing_sections` returned []
    and the run printed a clean PASS for a repository the skill would have refused to
    document. Say it out loud instead: the caller either fixes discovery or passes
    `--type=`.
    """
    if f.project_type in REQUIRED_SECTIONS:
        return []
    return [Finding("R013", STANDARD,
                    f"project type is {f.project_type!r}: section checks did not run. "
                    f"Pass --type=<service|cli|library|monorepo|lightweight> to grade "
                    f"structure, or fix discovery",
                    f"discovery verdict: {f.verdict}")]


def _check_required_sections(text: str, f: RepoFacts) -> list:
    """Split by consequence, not by uniformity.

    Reporting every missing required section as one STANDARD finding meant a README
    consisting of a title and one sentence returned PASS — while the skill's own
    scorecard lists Quick Start as Critical C3. The section that carries the reader
    from "found the repo" to "ran the thing" is now CRITICAL; the rest stay STANDARD.
    """
    missing = missing_sections(text, f.project_type)
    if not missing:
        return []
    primary = [s for s in missing if s in PRIMARY_SECTIONS.get(f.project_type, ())]
    secondary = [s for s in missing if s not in primary]
    out = []
    if primary:
        out.append(Finding("R009", CRITICAL,
                           f"{f.project_type} README is missing its primary entry path "
                           f"— a reader cannot get started",
                           ", ".join(primary)))
    if secondary:
        out.append(Finding("R012", STANDARD,
                           f"{f.project_type} README is missing required sections",
                           ", ".join(secondary)))
    return out


def lint(readme_text: str, facts: RepoFacts) -> list:
    findings = []
    findings += _check_commands(readme_text, facts)
    findings += _check_env_vars(readme_text, facts)
    findings += _check_paths(readme_text, facts)
    findings += _check_placeholders(readme_text)
    findings += _check_process_labels(readme_text)
    findings += _check_metrics(readme_text, facts)
    findings += _check_badges(readme_text, facts)
    findings += _check_unknown_type(facts)
    findings += _check_required_sections(readme_text, facts)
    findings += _check_toc(readme_text)
    findings += _check_double_language(readme_text)
    return findings


def summarize(findings: list) -> dict:
    """`result` is four-valued, because three distinct things were being reported as PASS.

    FAIL        a critical finding — the README asserts what the repo does not support
    INCOMPLETE  R013: the project type is unknown, so structure was never graded
    WARN        standard findings only — checked, real defects, none of them vetoing
    PASS        checked, nothing found

    WARN exists because the previous version returned PASS with an outstanding R012,
    contradicting its own docstring. Exit status still keys on FAIL alone: the skill's
    Standard tier tolerates up to two failures by design, so a warning must not break a
    caller's gate — but it must not read as clean either.
    """
    crit = [f for f in findings if f.severity == CRITICAL]
    codes = sorted({f.code for f in findings})
    if crit:
        result = "FAIL"
    elif "R013" in codes:
        result = "INCOMPLETE"
    elif findings:
        result = "WARN"
    else:
        result = "PASS"
    return {
        "critical": len(crit),
        "standard": len(findings) - len(crit),
        "codes": codes,
        "result": result,
    }


def main(argv: list) -> int:
    override = ""
    args = []
    for a in argv:
        if a.startswith("--type="):
            override = a.split("=", 1)[1]
        else:
            args.append(a)
    if not args:
        print(__doc__.strip())
        return 2
    repo = Path(args[0])
    readme = Path(args[1]) if len(args) > 1 else repo / "README.md"
    if not readme.is_file():
        print(f"no README at {readme}", file=sys.stderr)
        return 2
    if override and override not in REQUIRED_SECTIONS:
        print(f"unknown --type={override}; expected one of "
              f"{sorted(REQUIRED_SECTIONS)}", file=sys.stderr)
        return 2
    facts = scan_repo(repo, project_type=override)
    print(f"# project_type={facts.project_type} (base={facts.base_type}) "
          f"verdict={facts.verdict}")
    findings = lint(readme.read_text(encoding="utf-8"), facts)
    for f in findings:
        print(f)
    print(json.dumps(summarize(findings), ensure_ascii=False))
    return 1 if any(f.severity == CRITICAL for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

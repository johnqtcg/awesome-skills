#!/usr/bin/env python3
"""Automate gate checks and PR body generation for create-pr skill."""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    yaml = None


PASS = "PASS"
FAIL = "FAIL"
SUPPRESSED = "SUPPRESSED"
NA = "N/A"

SIZE_THRESHOLD_WARN = 400    # lines: review quality degrades above this
SIZE_THRESHOLD_STRONG = 800  # lines: strong recommendation to split

CONVENTIONAL_RE = re.compile(
    r"^(feat|fix|chore|docs|refactor|perf|test|build|ci|style|revert)(\([^)]+\))?: .+"
)

DEFAULT_SECRET_INCLUDE_EXTENSIONS = [
    ".go",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".java",
    ".rb",
    ".php",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".ini",
    ".env",
    ".sh",
    ".sql",
    ".tf",
]

DEFAULT_CONFLICT_INCLUDE_EXTENSIONS = [
    ".go",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".java",
    ".rb",
    ".php",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".ini",
    ".env",
    ".sh",
    ".sql",
    ".md",
]

DEFAULT_SECRET_ALLOW_PATTERNS = [
    r"(?i)(example|dummy|sample|placeholder|changeme|test(_|-)only)",
    r"(?i)redacted",
]

DEFAULT_CONFIG = {
    "base": "main",
    "reviewers": "",
    "docs_status": "na",
    "compat_status": "unknown",
    "timeout": 1200,
    "check_cmd": [],
    "create_pr": False,
    "dry_run": False,
    "update_existing_pr": True,
    "quality": {"enabled": True},
    "security_tools": {"enabled": True},
    "branch_protection": {
        "enabled": True,
        "require_pr_reviews": True,
        "require_status_checks": True,
        "required_checks": [],
    },
    "secret_scan": {
        "enabled": True,
        "include_extensions": DEFAULT_SECRET_INCLUDE_EXTENSIONS,
        "exclude_paths": [r"^docs/", r"^vendor/", r"^third_party/", r"^testdata/"],
        "allow_patterns": DEFAULT_SECRET_ALLOW_PATTERNS,
    },
    "conflict_scan": {
        "enabled": True,
        "include_extensions": DEFAULT_CONFLICT_INCLUDE_EXTENSIONS,
        "exclude_paths": [r"^vendor/", r"^third_party/"],
        "scan_changed_files_only": True,
    },
}

SECRET_PATTERNS = {
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "private_key": re.compile(r"-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----"),
    "github_pat": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    "slack_token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    "generic_secret": re.compile(
        r"(?i)\b(password|passwd|secret|token|api[-_]?key|access[-_]?key|private[-_]?key)\b\s*[:=]\s*['\"]?[^'\"\s]{8,}"
    ),
}

SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[-_]?key|access[-_]?key|private[-_]?key)\b\s*[:=]\s*['\"]?([^'\"\s]+)"
)
SECRET_PLACEHOLDER_RE = re.compile(
    r"(?i)^(example|dummy|sample|placeholder|redacted|changeme|todo|tbd|none|null|nil|xxxx+|test([_-]|$))"
)
SECRET_REFERENCE_RE = re.compile(
    r"(\$\{?[A-Z_][A-Z0-9_]*\}?|os\.getenv\(|getenv\(|process\.env\.|viper\.get|string\(|fmt\.sprint\()"
)
CONFLICT_START_RE = re.compile(r"^\s*<<<<<<<\s")
CONFLICT_MID_RE = re.compile(r"^\s*=======$")
CONFLICT_END_RE = re.compile(r"^\s*>>>>>>>\s")


@dataclass
class CommandResult:
    cmd: str
    rc: int
    stdout: str
    stderr: str


@dataclass
class GateResult:
    gate: str
    status: str
    evidence: str
    details: List[str] = field(default_factory=list)


@dataclass
class Settings:
    repo: Path
    base: str
    branch: str
    title: str
    issue: str
    reviewers: str
    create_pr: bool
    dry_run: bool
    timeout: int
    pr_body_out: Optional[Path]
    json_out: Optional[Path]
    docs_status: str
    compat_status: str
    check_cmd: List[str]
    quality_enabled: bool
    security_tools_enabled: bool
    branch_protection_enabled: bool
    branch_protection_require_pr_reviews: bool
    branch_protection_require_status_checks: bool
    branch_protection_required_checks: List[str]
    labels: str
    update_existing_pr: bool
    secret_scan_enabled: bool
    secret_include_extensions: List[str]
    secret_exclude_regex: List[re.Pattern[str]]
    secret_allow_regex: List[re.Pattern[str]]
    conflict_scan_enabled: bool
    conflict_include_extensions: List[str]
    conflict_exclude_regex: List[re.Pattern[str]]
    conflict_scan_changed_files_only: bool
    config_source: str


@dataclass
class Context:
    repo: Path
    base: str
    branch: str
    changed_files: List[Path] = field(default_factory=list)
    test_results: List[CommandResult] = field(default_factory=list)
    uncovered_risks: List[dict] = field(default_factory=list)
    high_risk_areas: List[str] = field(default_factory=list)
    pr_meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AddedLine:
    path: str
    line_no: int
    text: str


def run_cmd(cmd: Sequence[str], cwd: Path, timeout: int = 1200) -> CommandResult:
    try:
        proc = subprocess.run(
            list(cmd),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return CommandResult(" ".join(shlex.quote(x) for x in cmd), proc.returncode, proc.stdout.strip(), proc.stderr.strip())
    except FileNotFoundError as exc:
        return CommandResult(" ".join(shlex.quote(x) for x in cmd), 127, "", str(exc))
    except subprocess.TimeoutExpired:
        return CommandResult(" ".join(shlex.quote(x) for x in cmd), 124, "", f"timeout after {timeout}s")


def run_shell(cmd: str, cwd: Path, timeout: int = 1800) -> CommandResult:
    return run_cmd(["/bin/zsh", "-lc", cmd], cwd, timeout=timeout)


def short_output(result: CommandResult, limit: int = 220) -> str:
    text = result.stdout if result.stdout else result.stderr
    text = text.replace("\n", " | ").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def add_uncovered(ctx: Context, area: str, reason: str, impact: str, action: str, owner: str) -> None:
    ctx.uncovered_risks.append(
        {
            "area": area,
            "why": reason,
            "impact": impact,
            "action": action,
            "owner": owner,
        }
    )


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def as_list(value: Any, default: Optional[List[str]] = None) -> List[str]:
    if value is None:
        return default[:] if default else []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(x) for x in value]
    return default[:] if default else []


def compile_regexes(patterns: Sequence[str]) -> List[re.Pattern[str]]:
    result: List[re.Pattern[str]] = []
    for pattern in patterns:
        try:
            result.append(re.compile(pattern))
        except re.error:
            continue
    return result


def match_any(regexes: Sequence[re.Pattern[str]], text: str) -> bool:
    return any(r.search(text) for r in regexes)


def read_config_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    text = path.read_text()
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        if yaml is None:
            raise RuntimeError("PyYAML is required for .yaml/.yml config files")
        data = yaml.safe_load(text)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("config root must be an object/map")
    return data


def find_config_path(repo: Path, explicit: str, no_config: bool) -> Optional[Path]:
    if no_config:
        return None
    if explicit:
        return Path(explicit).expanduser().resolve()
    for name in (".create-pr.yaml", ".create-pr.yml", ".create-pr.json"):
        candidate = repo / name
        if candidate.exists():
            return candidate
    return None


def resolve_settings(args: argparse.Namespace, repo: Path, branch: str) -> Settings:
    config_path = find_config_path(repo, args.config, args.no_config)
    config = DEFAULT_CONFIG
    source = "builtin-default"

    if config_path:
        loaded = read_config_file(config_path)
        config = deep_merge(DEFAULT_CONFIG, loaded)
        source = str(config_path)

    base = args.base or str(config.get("base", "main"))
    reviewers = args.reviewers if args.reviewers is not None else str(config.get("reviewers", ""))
    labels = args.labels if args.labels is not None else str(config.get("labels", ""))
    title = args.title if args.title is not None else ""
    issue = args.issue if args.issue is not None else ""

    docs_status = args.docs_status if args.docs_status is not None else str(config.get("docs_status", "na"))
    compat_status = args.compat_status if args.compat_status is not None else str(config.get("compat_status", "unknown"))

    timeout = args.timeout if args.timeout is not None else int(config.get("timeout", 1200))

    check_cmd = args.check_cmd if args.check_cmd else as_list(config.get("check_cmd"), default=[])

    quality_enabled = config.get("quality", {}).get("enabled", True)
    if args.quality is not None:
        quality_enabled = args.quality

    security_enabled = config.get("security_tools", {}).get("enabled", True)
    if args.security_tools is not None:
        security_enabled = args.security_tools

    branch_protection_cfg = config.get("branch_protection", {})
    branch_protection_enabled = bool(branch_protection_cfg.get("enabled", True))
    if args.branch_protection is not None:
        branch_protection_enabled = args.branch_protection
    branch_protection_require_pr_reviews = bool(branch_protection_cfg.get("require_pr_reviews", True))
    branch_protection_require_status_checks = bool(branch_protection_cfg.get("require_status_checks", True))
    branch_protection_required_checks = as_list(branch_protection_cfg.get("required_checks"), default=[])

    create_pr = bool(config.get("create_pr", False))
    if args.create_pr:
        create_pr = True

    dry_run = bool(config.get("dry_run", False)) or bool(args.dry_run)

    update_existing_pr = bool(config.get("update_existing_pr", True))
    if args.update_existing_pr is not None:
        update_existing_pr = args.update_existing_pr

    secret_cfg = config.get("secret_scan", {})
    secret_scan_enabled = bool(secret_cfg.get("enabled", True))
    if args.secret_scan is not None:
        secret_scan_enabled = args.secret_scan

    secret_include = as_list(secret_cfg.get("include_extensions"), DEFAULT_SECRET_INCLUDE_EXTENSIONS)
    secret_exclude_regex = compile_regexes(as_list(secret_cfg.get("exclude_paths"), []))
    secret_allow_regex = compile_regexes(as_list(secret_cfg.get("allow_patterns"), DEFAULT_SECRET_ALLOW_PATTERNS))

    conflict_cfg = config.get("conflict_scan", {})
    conflict_scan_enabled = bool(conflict_cfg.get("enabled", True))
    if args.conflict_scan is not None:
        conflict_scan_enabled = args.conflict_scan

    conflict_include = as_list(conflict_cfg.get("include_extensions"), DEFAULT_CONFLICT_INCLUDE_EXTENSIONS)
    conflict_exclude_regex = compile_regexes(as_list(conflict_cfg.get("exclude_paths"), []))
    conflict_scan_changed_files_only = bool(conflict_cfg.get("scan_changed_files_only", True))

    pr_body_out = Path(args.pr_body_out).expanduser().resolve() if args.pr_body_out else None
    json_out = Path(args.json_out).expanduser().resolve() if args.json_out else None

    return Settings(
        repo=repo,
        base=base,
        branch=branch,
        title=title,
        issue=issue,
        reviewers=reviewers,
        labels=labels,
        create_pr=create_pr,
        dry_run=dry_run,
        timeout=timeout,
        pr_body_out=pr_body_out,
        json_out=json_out,
        docs_status=docs_status,
        compat_status=compat_status,
        check_cmd=check_cmd,
        quality_enabled=bool(quality_enabled),
        security_tools_enabled=bool(security_enabled),
        branch_protection_enabled=bool(branch_protection_enabled),
        branch_protection_require_pr_reviews=bool(branch_protection_require_pr_reviews),
        branch_protection_require_status_checks=bool(branch_protection_require_status_checks),
        branch_protection_required_checks=branch_protection_required_checks,
        update_existing_pr=bool(update_existing_pr),
        secret_scan_enabled=bool(secret_scan_enabled),
        secret_include_extensions=[x.lower() for x in secret_include],
        secret_exclude_regex=secret_exclude_regex,
        secret_allow_regex=secret_allow_regex,
        conflict_scan_enabled=bool(conflict_scan_enabled),
        conflict_include_extensions=[x.lower() for x in conflict_include],
        conflict_exclude_regex=conflict_exclude_regex,
        conflict_scan_changed_files_only=bool(conflict_scan_changed_files_only),
        config_source=source,
    )


def filter_files(
    files: Sequence[Path],
    include_extensions: Sequence[str],
    exclude_regex: Sequence[re.Pattern[str]],
) -> List[Path]:
    include_set = {x.lower() for x in include_extensions}
    results: List[Path] = []
    for path in files:
        s = str(path).replace("\\", "/")
        if match_any(exclude_regex, s):
            continue
        suffix = path.suffix.lower()
        if include_set and suffix and suffix not in include_set:
            continue
        if include_set and not suffix:
            continue
        results.append(path)
    return results


def list_changed_files(repo: Path, base: str, timeout: int) -> Tuple[List[Path], CommandResult]:
    result = run_cmd(["git", "diff", "--name-only", f"origin/{base}...HEAD"], repo, timeout)
    if result.rc != 0:
        return [], result
    files = [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]
    return files, result


def detect_high_risk_areas(paths: Sequence[Path]) -> List[str]:
    mapping = {
        "auth/authz": ["auth", "permission", "rbac", "acl"],
        "payments": ["payment", "billing", "invoice", "refund"],
        "migrations": ["migrate", "migration", ".sql"],
        "concurrency": ["mutex", "atomic", "goroutine", "channel", "race"],
        "public_api": ["api", "handler", "router", "openapi", "swagger"],
        "infra_config": ["docker", "k8s", "helm", "terraform", "workflow"],
        "secrets": ["secret", "credential", "token", "key"],
    }
    text_paths = [str(p).lower() for p in paths]
    hits = []
    for area, keys in mapping.items():
        if any(any(key in path for key in keys) for path in text_paths):
            hits.append(area)
    return hits


def scan_conflict_markers_in_files(repo: Path, files: Sequence[Path]) -> List[str]:
    findings: List[str] = []
    for rel in files:
        full = repo / rel
        if not full.exists() or not full.is_file():
            continue
        if full.stat().st_size > 1024 * 1024:
            continue
        try:
            lines = full.read_text(errors="ignore").splitlines()
        except OSError:
            continue
        start_line = 0
        seen_mid = False
        for idx, line in enumerate(lines, start=1):
            if CONFLICT_START_RE.match(line):
                start_line = idx
                seen_mid = False
                continue
            if start_line and CONFLICT_MID_RE.match(line):
                seen_mid = True
                continue
            if start_line and seen_mid and CONFLICT_END_RE.match(line):
                findings.append(f"{rel}:{start_line} unresolved merge block ends at {idx}")
                start_line = 0
                seen_mid = False
                if len(findings) >= 20:
                    return findings
    return findings


def classify_repo_slug(repo_meta: Dict[str, Any]) -> Tuple[str, str]:
    slug = str(repo_meta.get("nameWithOwner", ""))
    if "/" not in slug:
        return "", ""
    owner, name = slug.split("/", 1)
    return owner, name


def parse_required_status_checks(payload: Dict[str, Any]) -> List[str]:
    section = payload.get("required_status_checks")
    if not isinstance(section, dict):
        return []
    contexts = [str(x) for x in section.get("contexts", []) if str(x).strip()]
    checks = []
    for item in section.get("checks", []):
        if isinstance(item, dict):
            name = str(item.get("context", "")).strip()
            if name:
                checks.append(name)
    return sorted({*contexts, *checks})


def parse_diff_added_lines(diff_text: str) -> List[AddedLine]:
    entries: List[AddedLine] = []
    current_file: Optional[str] = None
    current_line: int = 0

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            current_file = None
            current_line = 0
            continue

        if line.startswith("+++ "):
            path_part = line[4:].strip()
            if path_part == "/dev/null":
                current_file = None
            else:
                if path_part.startswith("b/"):
                    path_part = path_part[2:]
                current_file = path_part
            continue

        if line.startswith("@@ "):
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if m:
                current_line = int(m.group(1))
            continue

        if current_file is None:
            continue

        if line.startswith("+") and not line.startswith("+++"):
            entries.append(AddedLine(path=current_file, line_no=current_line, text=line[1:]))
            current_line += 1
            continue

        if line.startswith("-") and not line.startswith("---"):
            continue

        if line.startswith("\\"):
            continue

        current_line += 1

    return entries


def scan_secrets_in_added_lines(
    entries: Sequence[AddedLine],
    allow_regex: Sequence[re.Pattern[str]],
) -> List[str]:
    def likely_real_secret_value(raw: str) -> bool:
        value = raw.strip().strip("'\"").strip()
        if len(value) < 12:
            return False
        if SECRET_PLACEHOLDER_RE.search(value):
            return False
        if SECRET_REFERENCE_RE.search(value):
            return False
        if value.lower() in {"true", "false"}:
            return False
        if re.fullmatch(r"[0-9]+", value):
            return False
        has_alpha = any(ch.isalpha() for ch in value)
        has_symbol_or_digit = any((not ch.isalpha()) for ch in value)
        return has_alpha and has_symbol_or_digit

    findings: List[str] = []
    for entry in entries:
        line = entry.text.strip()
        if not line:
            continue
        if match_any(allow_regex, line):
            continue

        lowered = line.lower()
        if lowered.startswith("//") or lowered.startswith("#"):
            continue

        matched = None
        for name, pattern in SECRET_PATTERNS.items():
            if not pattern.search(line):
                continue
            if name == "generic_secret":
                m = SECRET_ASSIGNMENT_RE.search(line)
                if not m:
                    continue
                value = m.group(2)
                if not likely_real_secret_value(value):
                    continue
            matched = name
            break

        if matched:
            findings.append(f"{entry.path}:{entry.line_no} [{matched}] {line[:180]}")
            if len(findings) >= 30:
                return findings

    return findings


def gate_a_preflight(ctx: Context, settings: Settings) -> GateResult:
    details: List[str] = []
    blockers: List[str] = []
    suppressed = False
    repo_meta: Dict[str, Any] = {}

    r = run_cmd(["git", "rev-parse", "--is-inside-work-tree"], ctx.repo, settings.timeout)
    details.append(f"{r.cmd}: rc={r.rc} ({short_output(r)})")
    if r.rc != 0 or r.stdout.strip() != "true":
        blockers.append("not a git repository")

    r = run_cmd(["git", "remote", "-v"], ctx.repo, settings.timeout)
    details.append(f"{r.cmd}: rc={r.rc} ({short_output(r)})")
    if r.rc != 0 or "origin" not in r.stdout:
        blockers.append("origin remote missing")

    r = run_cmd(["gh", "auth", "status", "-h", "github.com"], ctx.repo, settings.timeout)
    details.append(f"{r.cmd}: rc={r.rc} ({short_output(r)})")
    if r.rc != 0:
        blockers.append("gh auth not ready")

    r = run_cmd(
        ["gh", "repo", "view", "--json", "nameWithOwner,isPrivate,viewerPermission,defaultBranchRef"],
        ctx.repo,
        settings.timeout,
    )
    details.append(f"{r.cmd}: rc={r.rc} ({short_output(r)})")
    if r.rc != 0:
        blockers.append("cannot query repository permissions")
    elif r.stdout:
        try:
            repo_meta = json.loads(r.stdout)
            perm = str(repo_meta.get("viewerPermission", "")).upper()
            if perm in {"READ", "TRIAGE", ""}:
                blockers.append(f"insufficient permission for push/PR ({perm})")
        except json.JSONDecodeError:
            blockers.append("unable to parse repository metadata")

    r = run_cmd(["git", "ls-remote", "--heads", "origin", ctx.base], ctx.repo, settings.timeout)
    details.append(f"{r.cmd}: rc={r.rc} ({short_output(r)})")
    if r.rc != 0 or not r.stdout:
        blockers.append(f"remote branch '{ctx.base}' not found")

    if settings.branch_protection_enabled and not blockers:
        owner, repo_name = classify_repo_slug(repo_meta)
        if not owner or not repo_name:
            suppressed = True
            add_uncovered(
                ctx,
                "branch protection",
                "cannot resolve repository owner/name from gh metadata",
                "required checks/reviews on base branch are not verified",
                "verify branch protection on GitHub before marking ready",
                "repo owner",
            )
        else:
            protection = run_cmd(
                ["gh", "api", f"repos/{owner}/{repo_name}/branches/{ctx.base}/protection"],
                ctx.repo,
                settings.timeout,
            )
            details.append(f"{protection.cmd}: rc={protection.rc} ({short_output(protection, limit=300)})")
            if protection.rc != 0:
                suppressed = True
                why = "base branch is not protected (404)" if "404" in protection.stderr else "cannot read branch protection rules"
                add_uncovered(
                    ctx,
                    "branch protection",
                    why,
                    "PR could merge without required reviews/checks",
                    "configure and enforce GitHub branch protection for base branch",
                    "repo owner",
                )
            else:
                try:
                    payload = json.loads(protection.stdout) if protection.stdout else {}
                except json.JSONDecodeError:
                    payload = {}

                if not isinstance(payload, dict) or not payload:
                    suppressed = True
                    add_uncovered(
                        ctx,
                        "branch protection",
                        "invalid branch protection API response",
                        "cannot verify required reviews/status checks",
                        "inspect branch protection configuration manually",
                        "repo owner",
                    )
                else:
                    required_reviews = isinstance(payload.get("required_pull_request_reviews"), dict)
                    required_checks = parse_required_status_checks(payload)
                    if settings.branch_protection_require_pr_reviews and not required_reviews:
                        suppressed = True
                        add_uncovered(
                            ctx,
                            "branch protection: PR reviews",
                            "required PR reviews not enforced on base branch",
                            "changes may merge without peer review",
                            "enable required pull request reviews in branch protection",
                            "repo owner",
                        )

                    if settings.branch_protection_require_status_checks:
                        if not required_checks:
                            suppressed = True
                            add_uncovered(
                                ctx,
                                "branch protection: status checks",
                                "required status checks are empty/disabled on base branch",
                                "PR may merge without CI gate",
                                "configure required status checks in branch protection",
                                "repo owner",
                            )
                        elif settings.branch_protection_required_checks:
                            missing = sorted(
                                set(settings.branch_protection_required_checks) - set(required_checks)
                            )
                            if missing:
                                suppressed = True
                                add_uncovered(
                                    ctx,
                                    "branch protection: status checks policy",
                                    "repository is missing required checks from create-pr policy",
                                    f"expected checks may be bypassed: {', '.join(missing)}",
                                    "align branch protection required checks with repo policy",
                                    "repo owner",
                                )
                    details.append(
                        "branch protection summary: "
                        + f"reviews_required={required_reviews}, checks={','.join(required_checks) if required_checks else '(none)'}"
                    )

    if blockers:
        return GateResult("Gate A", FAIL, "; ".join(blockers), details)
    if suppressed:
        return GateResult("Gate A", SUPPRESSED, "preflight passed with uncovered branch protection risks", details)
    return GateResult("Gate A", PASS, "repo/auth/base preflight passed", details)


def gate_b_branch_sync(ctx: Context, settings: Settings) -> GateResult:
    details: List[str] = []
    blockers: List[str] = []

    if ctx.branch == ctx.base:
        blockers.append(f"head branch is {ctx.base}")

    r = run_cmd(["git", "status", "--porcelain"], ctx.repo, settings.timeout)
    details.append(f"{r.cmd}: rc={r.rc} ({short_output(r)})")
    if r.rc != 0:
        blockers.append("cannot read git status")
    elif r.stdout.strip():
        blockers.append("working tree is not clean")

    r = run_cmd(["git", "fetch", "origin", ctx.base], ctx.repo, settings.timeout)
    details.append(f"{r.cmd}: rc={r.rc} ({short_output(r)})")
    if r.rc != 0:
        blockers.append(f"fetch origin/{ctx.base} failed")

    r = run_cmd(["git", "merge-base", "--is-ancestor", f"origin/{ctx.base}", "HEAD"], ctx.repo, settings.timeout)
    details.append(f"{r.cmd}: rc={r.rc} ({short_output(r)})")
    if r.rc != 0:
        blockers.append(f"branch is behind origin/{ctx.base}; rebase required")

    unmerged = run_cmd(["git", "ls-files", "-u"], ctx.repo, settings.timeout)
    details.append(f"{unmerged.cmd}: rc={unmerged.rc} ({short_output(unmerged)})")
    if unmerged.rc == 0 and unmerged.stdout.strip():
        blockers.append("unresolved merge entries detected")

    if settings.conflict_scan_enabled:
        if not ctx.changed_files:
            changed, changed_cmd = list_changed_files(ctx.repo, ctx.base, settings.timeout)
            details.append(f"{changed_cmd.cmd}: rc={changed_cmd.rc} ({short_output(changed_cmd)})")
            if changed_cmd.rc == 0:
                ctx.changed_files = changed

        files_to_scan = ctx.changed_files
        if not settings.conflict_scan_changed_files_only:
            tracked = run_cmd(["git", "ls-files"], ctx.repo, settings.timeout)
            details.append(f"{tracked.cmd}: rc={tracked.rc} ({short_output(tracked, limit=280)})")
            if tracked.rc == 0:
                files_to_scan = [Path(x) for x in tracked.stdout.splitlines() if x.strip()]

        candidates = filter_files(files_to_scan, settings.conflict_include_extensions, settings.conflict_exclude_regex)
        conflict_hits = scan_conflict_markers_in_files(ctx.repo, candidates)
        if conflict_hits:
            blockers.append(f"conflict markers detected in {len(conflict_hits)} line(s)")
            details.extend(conflict_hits[:8])

    if blockers:
        return GateResult("Gate B", FAIL, "; ".join(blockers), details)
    return GateResult("Gate B", PASS, "branch hygiene and sync passed", details)


def gate_c_change_risk(ctx: Context, settings: Settings) -> GateResult:
    details: List[str] = []

    r1 = run_cmd(["git", "diff", "--name-status", f"origin/{ctx.base}...HEAD"], ctx.repo, settings.timeout)
    details.append(f"{r1.cmd}: rc={r1.rc} ({short_output(r1, limit=280)})")
    if r1.rc != 0:
        return GateResult("Gate C", FAIL, f"cannot compute diff against origin/{ctx.base}", details)

    r2 = run_cmd(["git", "diff", "--stat", f"origin/{ctx.base}...HEAD"], ctx.repo, settings.timeout)
    details.append(f"{r2.cmd}: rc={r2.rc} ({short_output(r2, limit=280)})")

    changed = []
    for line in r1.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            changed.append(Path(parts[-1]))
    ctx.changed_files = changed
    ctx.high_risk_areas = detect_high_risk_areas(changed)

    # Parse total changed lines from git diff --stat summary line
    # e.g. "3 files changed, 120 insertions(+), 45 deletions(-)"
    size_warning: Optional[str] = None
    if r2.rc == 0:
        for line in r2.stdout.splitlines():
            if "file" in line and "changed" in line:
                total = sum(int(x) for x in re.findall(r"(\d+) (?:insertion|deletion)", line))
                if total > SIZE_THRESHOLD_STRONG:
                    size_warning = (
                        f"PR is very large ({total} lines changed, >{SIZE_THRESHOLD_STRONG}). "
                        "Strongly recommend splitting unless change is inherently atomic."
                    )
                elif total > SIZE_THRESHOLD_WARN:
                    size_warning = (
                        f"PR is large ({total} lines changed, >{SIZE_THRESHOLD_WARN}). "
                        "Review quality may suffer; consider splitting."
                    )
                break
    if size_warning:
        details.append(f"size: {size_warning}")

    if ctx.high_risk_areas:
        return GateResult("Gate C", PASS, "high-risk areas touched: " + ", ".join(ctx.high_risk_areas), details)
    return GateResult("Gate C", PASS, "no high-risk path heuristics triggered", details)


def detect_affected_go_modules(repo: Path, changed_files: Sequence[Path]) -> List[Path]:
    """Find distinct Go module directories that contain changed files.

    Returns a list of directory paths (relative to *repo*) where each path
    contains a ``go.mod``.  For a single-module repo this returns ``[Path(".")]``.
    For a monorepo it returns only the modules that were actually touched.
    """
    module_dirs: set[Path] = set()
    for cf in changed_files:
        candidate = repo / cf
        # Walk up from the changed file's parent until we find go.mod or reach repo root.
        current = candidate.parent if candidate.is_file() or not candidate.exists() else candidate
        while True:
            if (current / "go.mod").exists():
                module_dirs.add(current.relative_to(repo))
                break
            if current == repo:
                break
            current = current.parent
    return sorted(module_dirs)


def default_quality_commands(repo: Path, changed_files: Optional[Sequence[Path]] = None) -> List[str]:
    cmds: List[str] = []
    makefile = repo / "Makefile"
    if makefile.exists():
        cmds.extend(["make test", "make lint"])
    if (repo / "go.mod").exists():
        if changed_files:
            mod_dirs = detect_affected_go_modules(repo, changed_files)
        else:
            mod_dirs = [Path(".")]
        for mod_dir in mod_dirs:
            prefix = f"cd {mod_dir} && " if str(mod_dir) != "." else ""
            cmds.append(f"{prefix}go test ./...")
            if shutil.which("golangci-lint"):
                cmds.append(f"{prefix}golangci-lint run")
    seen = set()
    uniq = []
    for cmd in cmds:
        if cmd in seen:
            continue
        seen.add(cmd)
        uniq.append(cmd)
    return uniq


def gate_d_quality(ctx: Context, settings: Settings) -> GateResult:
    details: List[str] = []

    if not settings.quality_enabled:
        add_uncovered(
            ctx,
            "quality checks",
            "disabled by configuration/flags",
            "test/lint regressions may be missed",
            "enable quality checks before marking ready",
            "repo owner",
        )
        return GateResult("Gate D", SUPPRESSED, "quality checks skipped", details)

    commands = settings.check_cmd[:] if settings.check_cmd else default_quality_commands(ctx.repo, ctx.changed_files)
    if not commands:
        add_uncovered(
            ctx,
            "quality checks",
            "no quality command discovered",
            "behavior regressions may not be detected",
            "configure check_cmd in .create-pr.yaml",
            "change author",
        )
        return GateResult("Gate D", SUPPRESSED, "no quality commands configured", details)

    failures = []
    for cmd in commands:
        r = run_shell(cmd, ctx.repo, timeout=settings.timeout)
        ctx.test_results.append(r)
        details.append(f"{cmd}: rc={r.rc} ({short_output(r, limit=320)})")
        if r.rc != 0:
            failures.append(cmd)

    if failures:
        return GateResult("Gate D", FAIL, "quality command failed: " + ", ".join(failures), details)
    return GateResult("Gate D", PASS, "all quality commands passed", details)


def gate_e_security(ctx: Context, settings: Settings) -> GateResult:
    details: List[str] = []
    blockers: List[str] = []
    suppressed = False

    if settings.secret_scan_enabled:
        if not ctx.changed_files:
            changed, changed_cmd = list_changed_files(ctx.repo, ctx.base, settings.timeout)
            details.append(f"{changed_cmd.cmd}: rc={changed_cmd.rc} ({short_output(changed_cmd)})")
            if changed_cmd.rc == 0:
                ctx.changed_files = changed

        candidate_files = filter_files(ctx.changed_files, settings.secret_include_extensions, settings.secret_exclude_regex)
        diff = run_cmd(["git", "diff", "--unified=0", "--no-color", f"origin/{ctx.base}...HEAD"], ctx.repo, settings.timeout)
        details.append(f"{diff.cmd}: rc={diff.rc} ({short_output(diff, limit=280)})")
        if diff.rc != 0:
            blockers.append("unable to collect patch for secret scan")
        else:
            added = parse_diff_added_lines(diff.stdout)
            allowed_set = {str(p).replace('\\\\', '/') for p in candidate_files}
            scoped = [x for x in added if x.path in allowed_set]
            findings = scan_secrets_in_added_lines(scoped, settings.secret_allow_regex)
            if findings:
                blockers.append(f"secret scan matched {len(findings)} line(s)")
                details.extend(findings[:10])
            else:
                details.append("secret scan: no high-signal matches on added lines")
    else:
        suppressed = True
        add_uncovered(
            ctx,
            "secret scan",
            "disabled by configuration/flags",
            "secret leaks in new code may be missed",
            "enable secret_scan in configuration",
            "change author",
        )

    if (ctx.repo / "go.mod").exists() and settings.security_tools_enabled:
        mod_dirs = detect_affected_go_modules(ctx.repo, ctx.changed_files) if ctx.changed_files else [Path(".")]
        missing = []
        for binary in ("gosec", "govulncheck"):
            if not shutil.which(binary):
                missing.append(binary)
                add_uncovered(
                    ctx,
                    binary,
                    "tool not installed",
                    "known vulnerabilities/security anti-patterns may be missed",
                    f"install {binary} and rerun",
                    "change author",
                )
                details.append(f"{binary} ./...: skipped (tool not installed)")
                continue

            for mod_dir in mod_dirs:
                prefix = f"cd {mod_dir} && " if str(mod_dir) != "." else ""
                tool_cmd = f"{prefix}{binary} ./..."
                r = run_shell(tool_cmd, ctx.repo, timeout=settings.timeout)
                details.append(f"{tool_cmd}: rc={r.rc} ({short_output(r, limit=320)})")
                if r.rc != 0:
                    blockers.append(f"{tool_cmd} failed")

        if missing:
            suppressed = True
    elif (ctx.repo / "go.mod").exists() and not settings.security_tools_enabled:
        suppressed = True
        add_uncovered(
            ctx,
            "security tools",
            "disabled by configuration/flags",
            "vulnerabilities may remain undetected",
            "enable security_tools or run gosec/govulncheck manually",
            "change author",
        )

    if blockers:
        return GateResult("Gate E", FAIL, "; ".join(blockers), details)
    if suppressed:
        return GateResult("Gate E", SUPPRESSED, "partial security coverage; see uncovered risks", details)
    return GateResult("Gate E", PASS, "security checks passed", details)


def gate_f_docs_compat(ctx: Context, settings: Settings) -> GateResult:
    details: List[str] = [
        f"docs-status={settings.docs_status}",
        f"compat-status={settings.compat_status}",
    ]

    if settings.docs_status == "no":
        return GateResult("Gate F", FAIL, "docs not updated for user-visible change", details)

    if settings.compat_status == "unknown":
        add_uncovered(
            ctx,
            "compatibility assessment",
            "compat status left unknown",
            "breaking change risk not communicated",
            "set compat_status=compatible|breaking",
            "change author",
        )
        return GateResult("Gate F", SUPPRESSED, "compatibility not confirmed", details)

    if settings.compat_status == "breaking":
        details.append("breaking change declared; ensure migration notes in PR body")

    return GateResult("Gate F", PASS, "docs/compatibility gate passed", details)


def gate_g_commit_hygiene(ctx: Context, settings: Settings) -> GateResult:
    details: List[str] = []
    blockers: List[str] = []

    r = run_cmd(["git", "status", "--porcelain"], ctx.repo, settings.timeout)
    details.append(f"{r.cmd}: rc={r.rc} ({short_output(r)})")
    if r.rc != 0:
        blockers.append("cannot read working tree state")
    elif r.stdout.strip():
        blockers.append("working tree not clean")

    r = run_cmd(["git", "rev-list", "--count", f"origin/{ctx.base}..HEAD"], ctx.repo, settings.timeout)
    details.append(f"{r.cmd}: rc={r.rc} ({short_output(r)})")
    ahead = 0
    if r.rc != 0:
        blockers.append("cannot count commits ahead of base")
    else:
        try:
            ahead = int(r.stdout.strip())
        except ValueError:
            blockers.append("invalid ahead commit count")
    if ahead <= 0:
        blockers.append(f"no commits ahead of origin/{ctx.base}")

    r = run_cmd(["git", "log", "--format=%s", f"origin/{ctx.base}..HEAD"], ctx.repo, settings.timeout)
    details.append(f"{r.cmd}: rc={r.rc} ({short_output(r, limit=260)})")
    if r.rc == 0:
        subjects = [x.strip() for x in r.stdout.splitlines() if x.strip()]
        invalid = [s for s in subjects if not CONVENTIONAL_RE.match(s)]
        if invalid:
            blockers.append(f"non-conventional commit subject(s): {len(invalid)}")
            details.extend([f"invalid subject: {s}" for s in invalid[:5]])
    else:
        blockers.append("cannot read commit subjects")

    if blockers:
        return GateResult("Gate G", FAIL, "; ".join(blockers), details)
    return GateResult("Gate G", PASS, "commit hygiene passed", details)


def determine_confidence(gates: Sequence[GateResult]) -> str:
    statuses = [g.status for g in gates if g.gate != "Gate H"]
    if any(s == FAIL for s in statuses):
        return "suspected"
    if any(s == SUPPRESSED for s in statuses):
        return "likely"
    return "confirmed"


def build_body(settings: Settings, ctx: Context, gates: Sequence[GateResult], confidence: str) -> str:
    gate_rows = "\n".join(f"| {g.gate} | {g.status} | {g.evidence} |" for g in gates if g.gate != "Gate H")
    test_rows = "\n".join(
        f"| `{r.cmd}` | {'PASS' if r.rc == 0 else 'FAIL'} | {short_output(r, limit=140)} |" for r in ctx.test_results
    )
    if not test_rows:
        test_rows = "| `(none)` | N/A | no explicit test command executed |"

    uncovered = "\n".join(
        f"- Area: {u['area']}\n  Why uncovered: {u['why']}\n  Potential impact: {u['impact']}\n  Follow-up action: {u['action']}\n  Suggested owner: {u['owner']}"
        for u in ctx.uncovered_risks
    )
    if not uncovered:
        uncovered = "- None"

    changed_preview = "\n".join(f"- `{p}`" for p in ctx.changed_files[:40]) or "- (none detected)"
    risk_text = ", ".join(ctx.high_risk_areas) if ctx.high_risk_areas else "no high-risk heuristics triggered"
    compat_line = "breaking" if settings.compat_status == "breaking" else "non-breaking"
    issue_line = settings.issue if settings.issue else "N/A"
    title = settings.title or "<type(scope): concise summary>"

    return f"""# PR Title

`{title}`

## 1) Problem / Context

- Linked issue/ticket: {issue_line}
- Gate confidence: `{confidence}`
- Config source: `{settings.config_source}`

## 2) What Changed

{changed_preview}

## 3) Why This Approach

- Uses the `create-pr` gated workflow to provide consistent merge readiness evidence.
- Keeps draft/ready decision tied to measurable gates.

## 4) Risk and Rollback Plan

- Risk profile: {risk_text}
- Rollback strategy: revert PR commit set and redeploy previous build.

## 5) Test Evidence

| Command | Result | Notes |
| --- | --- | --- |
{test_rows}

## 6) Security Notes

| Gate | Status | Evidence |
| --- | --- | --- |
{gate_rows}

Uncovered Risk List:
{uncovered}

## 7) Breaking Changes / Migration Notes

- Compatibility: `{compat_line}`
- Migration notes: {'required' if settings.compat_status == 'breaking' else 'not required'}

## 8) Reviewer Checklist

- [ ] Gate results and residual risks are acceptable.
- [ ] Test evidence is sufficient for touched code paths.
- [ ] Security findings are addressed or tracked.
- [ ] Rollback strategy is practical.
"""


def find_existing_pr(ctx: Context, settings: Settings) -> Tuple[Optional[Dict[str, Any]], CommandResult]:
    result = run_cmd(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "open",
            "--base",
            settings.base,
            "--head",
            ctx.branch,
            "--json",
            "number,url,isDraft,title",
            "--limit",
            "1",
        ],
        ctx.repo,
        timeout=settings.timeout,
    )
    if result.rc != 0:
        return None, result

    try:
        payload = json.loads(result.stdout) if result.stdout else []
    except json.JSONDecodeError:
        return None, CommandResult(result.cmd, 3, result.stdout, "invalid JSON from gh pr list")

    if not isinstance(payload, list) or not payload:
        return None, result
    if not isinstance(payload[0], dict):
        return None, CommandResult(result.cmd, 3, result.stdout, "unexpected gh payload shape")
    return payload[0], result


def gate_h_create_or_update_pr(
    settings: Settings,
    ctx: Context,
    body_path: Path,
    confidence: str,
) -> GateResult:
    details: List[str] = []

    if not settings.create_pr:
        return GateResult("Gate H", NA, "PR creation/update not requested", details)

    if settings.dry_run:
        return GateResult("Gate H", SUPPRESSED, "dry-run mode; PR create/update skipped", details)

    push = run_cmd(["git", "push", "-u", "origin", "HEAD"], ctx.repo, timeout=settings.timeout)
    details.append(f"{push.cmd}: rc={push.rc} ({short_output(push, limit=320)})")
    if push.rc != 0:
        return GateResult("Gate H", FAIL, "git push failed", details)

    title = settings.title
    if not title:
        head_msg = run_cmd(["git", "log", "-1", "--format=%s"], ctx.repo, timeout=settings.timeout)
        details.append(f"{head_msg.cmd}: rc={head_msg.rc} ({short_output(head_msg)})")
        title = head_msg.stdout.strip() if head_msg.rc == 0 and head_msg.stdout.strip() else "chore: update branch"

    desired_ready = confidence == "confirmed"

    existing = None
    query = None
    if settings.update_existing_pr:
        existing, query = find_existing_pr(ctx, settings)
        details.append(f"{query.cmd}: rc={query.rc} ({short_output(query, limit=320)})")
        if query.rc not in (0,):
            return GateResult("Gate H", FAIL, "failed to query existing PR", details)

    pr_ref = ""
    if existing:
        pr_ref = str(existing.get("number"))
        edit = run_cmd(
            ["gh", "pr", "edit", pr_ref, "--title", title, "--body-file", str(body_path)],
            ctx.repo,
            timeout=settings.timeout,
        )
        details.append(f"{edit.cmd}: rc={edit.rc} ({short_output(edit, limit=320)})")
        if edit.rc != 0:
            return GateResult("Gate H", FAIL, "failed to update existing PR", details)

        is_draft = bool(existing.get("isDraft", False))
        if desired_ready and is_draft:
            ready = run_cmd(["gh", "pr", "ready", pr_ref], ctx.repo, timeout=settings.timeout)
            details.append(f"{ready.cmd}: rc={ready.rc} ({short_output(ready, limit=320)})")
            if ready.rc != 0:
                return GateResult("Gate H", FAIL, "failed to mark PR ready", details)
        if (not desired_ready) and (not is_draft):
            draft = run_cmd(["gh", "pr", "ready", "--undo", pr_ref], ctx.repo, timeout=settings.timeout)
            details.append(f"{draft.cmd}: rc={draft.rc} ({short_output(draft, limit=320)})")
            if draft.rc != 0:
                return GateResult("Gate H", FAIL, "failed to convert PR to draft", details)
    else:
        create_cmd = [
            "gh",
            "pr",
            "create",
            "--base",
            settings.base,
            "--head",
            ctx.branch,
            "--title",
            title,
            "--body-file",
            str(body_path),
        ]
        if not desired_ready:
            create_cmd.append("--draft")

        create = run_cmd(create_cmd, ctx.repo, timeout=settings.timeout)
        details.append(f"{create.cmd}: rc={create.rc} ({short_output(create, limit=320)})")
        if create.rc != 0:
            return GateResult("Gate H", FAIL, "gh pr create failed", details)
        pr_ref = create.stdout.splitlines()[-1].strip() if create.stdout else ""

    if settings.reviewers:
        rr = run_cmd(["gh", "pr", "edit", pr_ref, "--add-reviewer", settings.reviewers], ctx.repo, timeout=settings.timeout)
        details.append(f"{rr.cmd}: rc={rr.rc} ({short_output(rr, limit=320)})")
        if rr.rc != 0:
            return GateResult("Gate H", FAIL, "failed to add reviewers", details)

    if settings.labels:
        lr = run_cmd(["gh", "pr", "edit", pr_ref, "--add-label", settings.labels], ctx.repo, timeout=settings.timeout)
        details.append(f"{lr.cmd}: rc={lr.rc} ({short_output(lr, limit=320)})")
        if lr.rc != 0:
            details.append("warning: failed to add labels (non-blocking)")

    view = run_cmd(
        ["gh", "pr", "view", pr_ref, "--json", "number,url,state,isDraft,baseRefName,headRefName,title"],
        ctx.repo,
        timeout=settings.timeout,
    )
    details.append(f"{view.cmd}: rc={view.rc} ({short_output(view, limit=320)})")
    if view.rc != 0:
        return GateResult("Gate H", FAIL, "unable to verify PR metadata", details)

    try:
        meta = json.loads(view.stdout)
        if isinstance(meta, dict):
            ctx.pr_meta = meta
    except json.JSONDecodeError:
        pass

    # Optional: report CI check status (informational, does not change gate verdict).
    pr_number = str(ctx.pr_meta.get("number", pr_ref))
    if pr_number:
        ci = run_cmd(["gh", "pr", "checks", pr_number], ctx.repo, timeout=60)
        details.append(f"{ci.cmd}: rc={ci.rc} ({short_output(ci, limit=320)})")

    evidence = "PR updated" if existing else "PR created"
    return GateResult("Gate H", PASS, evidence + " and verified", details)


def print_report(gates: Sequence[GateResult], body_path: Path, confidence: str, pr_mode: str, ctx: Context, settings: Settings) -> None:
    print("Gate Results:")
    for g in gates:
        print(f"- {g.gate}: {g.status} | {g.evidence}")

    print("\nReadiness:")
    print(f"- confidence: {confidence}")
    print(f"- recommended_pr_mode: {pr_mode}")
    print(f"- pr_body: {body_path}")
    print(f"- config_source: {settings.config_source}")

    if ctx.pr_meta:
        print("\nPR Metadata:")
        print(f"- number: {ctx.pr_meta.get('number')}")
        print(f"- url: {ctx.pr_meta.get('url')}")
        print(f"- is_draft: {ctx.pr_meta.get('isDraft')}")
        print(f"- base/head: {ctx.pr_meta.get('baseRefName')} <- {ctx.pr_meta.get('headRefName')}")

    print("\nUncovered Risk List:")
    if not ctx.uncovered_risks:
        print("- none")
    else:
        for u in ctx.uncovered_risks:
            print(f"- area={u['area']} | why={u['why']} | impact={u['impact']} | action={u['action']} | owner={u['owner']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run create-pr gates and generate/update PR.")
    parser.add_argument("--repo", default=".", help="repository path")
    parser.add_argument("--config", default="", help="config file path (.create-pr.yaml/.json)")
    parser.add_argument("--no-config", action="store_true", help="ignore repository config files")

    parser.add_argument("--base", default="", help="base branch")
    parser.add_argument("--head", default="", help="head branch (defaults to current branch)")
    parser.add_argument("--title", default=None, help="PR title")
    parser.add_argument("--issue", default=None, help="issue/ticket reference")
    parser.add_argument("--reviewers", default=None, help="comma-separated reviewers")
    parser.add_argument("--labels", default=None, help="comma-separated GitHub labels")

    parser.add_argument("--create-pr", action="store_true", help="push branch and create/update PR")
    parser.add_argument("--dry-run", action="store_true", help="do not push/create/update PR")
    parser.add_argument("--pr-body-out", default="", help="outputexample path for generated PR body")
    parser.add_argument("--json-out", default="", help="optional JSON summary outputexample path")

    parser.add_argument("--docs-status", choices=["yes", "no", "na"], default=None)
    parser.add_argument("--compat-status", choices=["compatible", "breaking", "unknown"], default=None)
    parser.add_argument("--check-cmd", action="append", default=[], help="quality command; repeatable")
    parser.add_argument("--timeout", type=int, default=None, help="timeout seconds per command")

    quality_group = parser.add_mutually_exclusive_group()
    quality_group.add_argument("--quality", dest="quality", action="store_true", help="force-enable quality checks")
    quality_group.add_argument("--no-quality", dest="quality", action="store_false", help="force-disable quality checks")
    parser.set_defaults(quality=None)

    sec_group = parser.add_mutually_exclusive_group()
    sec_group.add_argument("--security-tools", dest="security_tools", action="store_true", help="force-enable gosec/govulncheck")
    sec_group.add_argument("--no-security-tools", dest="security_tools", action="store_false", help="force-disable gosec/govulncheck")
    parser.set_defaults(security_tools=None)

    bp_group = parser.add_mutually_exclusive_group()
    bp_group.add_argument("--branch-protection", dest="branch_protection", action="store_true", help="force-enable branch protection validation")
    bp_group.add_argument("--no-branch-protection", dest="branch_protection", action="store_false", help="force-disable branch protection validation")
    parser.set_defaults(branch_protection=None)

    secret_group = parser.add_mutually_exclusive_group()
    secret_group.add_argument("--secret-scan", dest="secret_scan", action="store_true", help="force-enable secret scan")
    secret_group.add_argument("--no-secret-scan", dest="secret_scan", action="store_false", help="force-disable secret scan")
    parser.set_defaults(secret_scan=None)

    conflict_group = parser.add_mutually_exclusive_group()
    conflict_group.add_argument("--conflict-scan", dest="conflict_scan", action="store_true", help="force-enable conflict marker scan")
    conflict_group.add_argument("--no-conflict-scan", dest="conflict_scan", action="store_false", help="force-disable conflict marker scan")
    parser.set_defaults(conflict_scan=None)

    update_group = parser.add_mutually_exclusive_group()
    update_group.add_argument("--update-existing-pr", dest="update_existing_pr", action="store_true", help="update existing open PR for this branch")
    update_group.add_argument("--no-update-existing-pr", dest="update_existing_pr", action="store_false", help="disable existing PR update")
    parser.set_defaults(update_existing_pr=None)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    if not repo.exists():
        print(f"repo path not found: {repo}", file=sys.stderr)
        return 2

    branch_result = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo, timeout=120)
    if branch_result.rc != 0:
        print(f"failed to detect branch: {short_output(branch_result)}", file=sys.stderr)
        return 2

    branch = args.head or branch_result.stdout.strip()

    try:
        settings = resolve_settings(args, repo, branch)
    except Exception as exc:
        print(f"failed to load config: {exc}", file=sys.stderr)
        return 2

    ctx = Context(repo=repo, base=settings.base, branch=settings.branch)

    gates: List[GateResult] = []
    gates.append(gate_a_preflight(ctx, settings))
    gates.append(gate_b_branch_sync(ctx, settings))
    gates.append(gate_c_change_risk(ctx, settings))
    gates.append(gate_d_quality(ctx, settings))
    gates.append(gate_e_security(ctx, settings))
    gates.append(gate_f_docs_compat(ctx, settings))
    gates.append(gate_g_commit_hygiene(ctx, settings))

    confidence = determine_confidence(gates)
    pr_mode = "ready" if confidence == "confirmed" else "draft"

    body_path = settings.pr_body_out or Path(f"/tmp/pr_body_{settings.branch.replace('/', '_')}.md")
    body = build_body(settings, ctx, gates, confidence)
    body_path.write_text(body)

    gate_h = gate_h_create_or_update_pr(settings, ctx, body_path, confidence)
    gates.append(gate_h)

    print_report(gates, body_path, confidence, pr_mode, ctx, settings)

    if settings.json_out:
        payload = {
            "confidence": confidence,
            "recommended_pr_mode": pr_mode,
            "pr_body": str(body_path),
            "config_source": settings.config_source,
            "gates": [g.__dict__ for g in gates],
            "uncovered_risks": ctx.uncovered_risks,
            "pr_meta": ctx.pr_meta,
        }
        settings.json_out.write_text(json.dumps(payload, indent=2, ensure_ascii=True))

    if any(g.status == FAIL for g in gates if g.gate != "Gate H"):
        return 2
    if any(g.status == SUPPRESSED for g in gates if g.gate != "Gate H"):
        return 1
    if gate_h.status == FAIL:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

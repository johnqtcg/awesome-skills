"""Repository search provenance and static host-receipt verification."""

from __future__ import annotations

import datetime as dt
import re
import shlex
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Optional, Sequence, Tuple

PINNED_COMMIT_RE = re.compile(r"[0-9a-fA-F]{7,64}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
WORKTREE_COMMIT = "working-tree-unpinned"
HOST_TEST_RECEIPT_SCHEMA = "deep-research/host-test-receipt-v2"
REPOSITORY_SNAPSHOT_SCHEMA = "deep-research/repository-snapshot-v1"
ALLOWED_TEST_FRAMEWORKS = {
    "cargo-test",
    "dotnet-test",
    "go-test",
    "gradle-test",
    "maven-surefire",
    "npm-test",
    "pytest",
    "unittest",
}


def is_pinned_commit(value: Any) -> bool:
    return bool(PINNED_COMMIT_RE.fullmatch(str(value or "").strip()))


def _run_git(
    root: Path,
    args: Sequence[str],
    *,
    timeout: float = 15.0,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def git_repository_context(search_root: Path) -> Tuple[Path, str, str]:
    """Return (Git top-level, HEAD object ID, subject), or unpinned context."""
    try:
        top = _run_git(search_root, ["rev-parse", "--show-toplevel"])
        if top.returncode != 0:
            return search_root.resolve(), "", ""
        repo_root = Path(top.stdout.strip()).resolve()
        commit_proc = _run_git(repo_root, ["rev-parse", "HEAD"])
        if commit_proc.returncode != 0:
            return repo_root, "", ""
        commit = commit_proc.stdout.strip()
        subject_proc = _run_git(
            repo_root,
            ["show", "-s", "--format=%s", commit],
        )
        subject = subject_proc.stdout.strip() if subject_proc.returncode == 0 else ""
        return repo_root, commit, subject
    except (OSError, subprocess.TimeoutExpired):
        return search_root.resolve(), "", ""


def repository_snapshot(search_root: Path) -> Dict[str, Any]:
    """Read the current Git identity without executing code or changing Git."""
    root, commit, _ = git_repository_context(search_root)
    if not commit or not git_commit_exists(root, commit):
        raise ValueError(f"root is not a Git repository with a readable HEAD: {root}")
    tree_hash, tree_error = git_tree_hash(root, commit)
    if tree_error or not is_pinned_commit(tree_hash):
        raise ValueError(
            f"unable to read Git tree for {commit}: "
            f"{tree_error or 'invalid tree hash'}"
        )
    try:
        status = _run_git(
            root,
            ["status", "--porcelain=v1", "--untracked-files=all"],
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"unable to read Git working-tree state: {exc}") from exc
    if status.returncode != 0:
        raise ValueError(
            "unable to read Git working-tree state: "
            f"{status.stderr.strip() or 'git status failed'}"
        )
    return {
        "schema": REPOSITORY_SNAPSHOT_SCHEMA,
        "root": str(root),
        "head_commit": commit,
        "tree_hash": tree_hash,
        "dirty": bool(status.stdout.strip()),
    }


def _safe_relative_path(value: Any) -> Tuple[Optional[str], str]:
    raw = str(value or "").replace("\\", "/").strip()
    path = PurePosixPath(raw)
    if not raw or path.is_absolute() or ".." in path.parts:
        return None, "repository path must be a non-escaping relative path"
    normalized = path.as_posix()
    if normalized in {"", "."}:
        return None, "repository path must identify a file"
    return normalized, ""


def git_commit_exists(root: Path, commit: str) -> bool:
    if not is_pinned_commit(commit):
        return False
    try:
        proc = _run_git(root, ["cat-file", "-e", f"{commit}^{{commit}}"])
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def git_commit_subject(root: Path, commit: str) -> Tuple[str, str]:
    try:
        proc = _run_git(root, ["show", "-s", "--format=%s", commit])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "", str(exc)
    if proc.returncode != 0:
        return "", proc.stderr.strip() or "unable to read commit subject"
    return proc.stdout.strip(), ""


def git_tree_hash(root: Path, commit: str) -> Tuple[str, str]:
    try:
        proc = _run_git(root, ["rev-parse", f"{commit}^{{tree}}"])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "", str(exc)
    if proc.returncode != 0:
        return "", proc.stderr.strip() or "unable to read commit tree"
    return proc.stdout.strip(), ""


def git_blob_text(root: Path, commit: str, path: str) -> Tuple[str, str]:
    try:
        proc = _run_git(root, ["show", f"{commit}:{path}"])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "", str(exc)
    if proc.returncode != 0:
        return "", proc.stderr.strip() or "unable to read commit blob"
    return proc.stdout, ""


def path_is_clean_at_commit(root: Path, path: str, commit: str) -> bool:
    """Prove that the current path exists in commit and has no index/worktree delta."""
    if not git_commit_exists(root, commit):
        return False
    _, blob_error = git_blob_text(root, commit, path)
    if blob_error:
        return False
    try:
        status = _run_git(
            root,
            ["status", "--porcelain=v1", "--untracked-files=all", "--", path],
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return status.returncode == 0 and not status.stdout.strip()


def code_record_provenance(
    *,
    repo_root: Path,
    file_path: Path,
    head_commit: str,
) -> Dict[str, str]:
    try:
        relative_path = file_path.resolve().relative_to(repo_root.resolve()).as_posix()
    except (OSError, ValueError):
        relative_path = file_path.as_posix()
    pinned = (
        bool(head_commit)
        and path_is_clean_at_commit(repo_root, relative_path, head_commit)
    )
    return {
        "path": relative_path,
        "commit": head_commit if pinned else WORKTREE_COMMIT,
        "snapshot": "commit" if pinned else "worktree",
    }


def _excerpt_matches(text: str, line: int, excerpt: str) -> Tuple[bool, str]:
    if line < 1:
        return False, "line must be a positive 1-based number"
    expected_lines = str(excerpt).splitlines() or [str(excerpt)]
    actual_lines = text.splitlines()
    end = line - 1 + len(expected_lines)
    if line - 1 >= len(actual_lines) or end > len(actual_lines):
        return False, "declared line range is outside the evidence text"
    actual = "\n".join(actual_lines[line - 1:end])
    expected = "\n".join(expected_lines)
    if actual != expected:
        return False, "declared excerpt does not match the text at the declared line"
    return True, ""


def _issue(code: str, message: str) -> Dict[str, Any]:
    return {"severity": "error", "code": code, "message": message}


def _argv_matches_framework(
    argv: Sequence[str],
    framework: str,
    selectors: Sequence[str],
) -> bool:
    executable = Path(argv[0]).name.lower()
    tail = list(argv[1:])
    python_executable = bool(re.fullmatch(r"python(?:3(?:\.\d+)?)?", executable))
    if framework == "unittest":
        framework_match = python_executable and tail[:2] == ["-m", "unittest"]
    elif framework == "pytest":
        framework_match = executable.startswith("pytest") or (
            python_executable and tail[:2] == ["-m", "pytest"]
        )
    elif framework == "go-test":
        framework_match = executable == "go" and tail[:1] == ["test"]
    elif framework == "cargo-test":
        framework_match = executable == "cargo" and tail[:1] == ["test"]
    elif framework == "npm-test":
        framework_match = executable in {"npm", "npm.cmd"} and tail[:1] == ["test"]
    elif framework == "maven-surefire":
        framework_match = executable in {"mvn", "mvnw", "mvnw.cmd"} and "test" in tail
    elif framework == "gradle-test":
        framework_match = executable in {
            "gradle",
            "gradle.bat",
            "gradlew",
            "gradlew.bat",
        } and "test" in tail
    else:
        framework_match = executable in {"dotnet", "dotnet.exe"} and tail[:1] == ["test"]
    command_text = " ".join(argv)
    selector_match = any(selector in command_text for selector in selectors)
    return framework_match and selector_match


class RepositoryEvidenceVerifier:
    """Lazily verify only repository evidence referenced by report content."""

    def __init__(
        self,
        artifact: Dict[str, Any],
    ) -> None:
        self.artifact = artifact if isinstance(artifact, dict) else {}
        self.root = Path(str(self.artifact.get("root", ""))).expanduser()
        rows = self.artifact.get("evidence", [])
        self.records: Dict[str, Dict[str, Any]] = {}
        self.duplicate_ids: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            evidence_id = str(row.get("id", "")).strip()
            if not evidence_id:
                continue
            if evidence_id in self.records:
                self.duplicate_ids.add(evidence_id)
                continue
            self.records[evidence_id] = row
        self.cache: Dict[Tuple[str, str], Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]] = {}

    def verify(
        self,
        evidence_id: str,
        expected_kind: str,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        key = (evidence_id, expected_kind)
        if key in self.cache:
            return self.cache[key]
        record = self.records.get(evidence_id)
        if evidence_id in self.duplicate_ids:
            result = (
                None,
                _issue(
                    "duplicate_repository_evidence_id",
                    f"repository evidence ID is ambiguous: {evidence_id}",
                ),
            )
        elif not record or str(record.get("kind", "")).lower() != expected_kind:
            result = (
                None,
                _issue(
                    "repository_evidence_not_found",
                    f"{expected_kind} evidence ID was not found: {evidence_id or '<missing>'}",
                ),
            )
        elif not str(self.artifact.get("root", "")).strip():
            result = (
                None,
                _issue(
                    "repository_root_missing",
                    "repository evidence artifact must declare its root",
                ),
            )
        elif not self.root.is_dir():
            result = (
                None,
                _issue(
                    "repository_root_not_found",
                    f"repository root does not exist: {self.root}",
                ),
            )
        elif expected_kind == "code":
            result = self._verify_code(record)
        elif expected_kind == "commit":
            result = self._verify_commit(record)
        else:
            result = self._verify_test(record)
        self.cache[key] = result
        return result

    def _verify_code(
        self,
        record: Dict[str, Any],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        path, path_error = _safe_relative_path(record.get("path", ""))
        if not path:
            return None, _issue("repository_path_escape", path_error)
        try:
            line = int(record.get("line", 0))
        except (TypeError, ValueError):
            line = 0
        excerpt = str(record.get("excerpt", ""))
        if not excerpt:
            return None, _issue(
                "repository_evidence_incomplete",
                f"code evidence {record.get('id')} is missing excerpt",
            )
        commit = str(record.get("commit", "")).strip()
        pinned = is_pinned_commit(commit)
        if pinned:
            if not git_commit_exists(self.root, commit):
                return None, _issue(
                    "git_commit_not_found",
                    f"Git commit does not exist at repository root: {commit}",
                )
            text, error = git_blob_text(self.root, commit, path)
            if error:
                return None, _issue(
                    "git_blob_not_found",
                    f"cannot read {commit}:{path}: {error}",
                )
        else:
            candidate = (self.root / path).resolve()
            try:
                candidate.relative_to(self.root.resolve())
            except (OSError, ValueError):
                return None, _issue(
                    "repository_path_escape",
                    f"repository path escapes declared root: {path}",
                )
            if not candidate.is_file():
                return None, _issue(
                    "repository_path_not_found",
                    f"working-tree evidence path does not exist: {path}",
                )
            try:
                text = candidate.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                return None, _issue(
                    "repository_path_unreadable",
                    f"cannot read working-tree evidence path {path}: {exc}",
                )
        matches, why = _excerpt_matches(text, line, excerpt)
        if not matches:
            code = (
                "code_line_out_of_range"
                if "outside" in why or "positive" in why
                else "code_excerpt_mismatch"
            )
            return None, _issue(code, f"{path}:{line}: {why}")
        verified = {
            "kind": "code",
            "id": str(record.get("id", "")),
            "path": path,
            "line": line,
            "excerpt": excerpt,
            "commit": commit or WORKTREE_COMMIT,
            "snapshot": "commit" if pinned else "worktree",
            "pinned": pinned,
            "primary": True,
        }
        return verified, None

    def _verify_commit(
        self,
        record: Dict[str, Any],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        commit = str(record.get("commit", "")).strip()
        if not git_commit_exists(self.root, commit):
            return None, _issue(
                "git_commit_not_found",
                f"Git commit does not exist at repository root: {commit or '<missing>'}",
            )
        subject, error = git_commit_subject(self.root, commit)
        if error:
            return None, _issue(
                "git_commit_unreadable",
                f"cannot read commit subject for {commit}: {error}",
            )
        declared = str(record.get("subject", "")).strip()
        if subject != declared:
            return None, _issue(
                "commit_subject_mismatch",
                f"declared subject for {commit} does not match Git",
            )
        return {
            "kind": "commit",
            "id": str(record.get("id", "")),
            "commit": commit,
            "subject": subject,
            "pinned": True,
            "primary": True,
        }, None

    def _verify_test(
        self,
        record: Dict[str, Any],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        evidence_id = str(record.get("id", "")).strip()
        if record.get("schema") != HOST_TEST_RECEIPT_SCHEMA:
            return None, _issue(
                "unsupported_test_receipt_schema",
                f"test evidence {evidence_id} must use {HOST_TEST_RECEIPT_SCHEMA}",
            )
        if record.get("origin") != "host-tool":
            return None, _issue(
                "test_receipt_origin_invalid",
                f"test evidence {evidence_id} must be attested by origin=host-tool",
            )
        argv = record.get("argv", [])
        if (
            not isinstance(argv, list)
            or not argv
            or not all(isinstance(item, str) and item for item in argv)
        ):
            return None, _issue(
                "test_argv_invalid",
                f"test evidence {record.get('id')} requires a non-empty argv array",
            )
        execution_id = str(record.get("execution_id", "")).strip()
        if not SHA256_RE.fullmatch(execution_id):
            return None, _issue(
                "test_execution_id_invalid",
                f"test evidence {evidence_id} requires a 64-character execution ID",
            )
        framework = str(record.get("framework", "")).strip().lower()
        if framework not in ALLOWED_TEST_FRAMEWORKS:
            return None, _issue(
                "test_framework_invalid",
                f"test evidence {evidence_id} has unsupported framework: "
                f"{framework or '<missing>'}",
            )
        test_target = str(record.get("test_target", "")).strip()
        selectors = record.get("selectors", [])
        if (
            not test_target
            or not isinstance(selectors, list)
            or not selectors
            or not all(isinstance(item, str) and item.strip() for item in selectors)
        ):
            return None, _issue(
                "test_target_invalid",
                f"test evidence {evidence_id} requires a target and selector list",
            )
        clean_selectors = [str(item).strip() for item in selectors]
        if not _argv_matches_framework(argv, framework, clean_selectors):
            return None, _issue(
                "test_argv_framework_mismatch",
                f"test evidence {evidence_id} argv does not invoke its declared "
                "framework and selector",
            )
        covers = record.get("covers", [])
        if (
            not isinstance(covers, list)
            or not covers
            or not all(isinstance(item, str) and item.strip() for item in covers)
        ):
            return None, _issue(
                "test_covers_invalid",
                f"test evidence {evidence_id} requires non-empty claim/evidence IDs in covers",
            )
        repository = record.get("repository")
        if not isinstance(repository, dict):
            return None, _issue(
                "test_repository_identity_missing",
                f"test evidence {evidence_id} requires repository snapshot identity",
            )
        root_value = Path(str(repository.get("root", ""))).expanduser()
        if not root_value.is_absolute():
            return None, _issue(
                "test_repository_root_invalid",
                f"test evidence {evidence_id} repository root must be absolute",
            )
        try:
            receipt_root = root_value.resolve()
        except OSError as exc:
            return None, _issue(
                "test_repository_root_invalid",
                f"test evidence {evidence_id} repository root is invalid: {exc}",
            )
        if receipt_root != self.root.resolve():
            return None, _issue(
                "test_repository_root_mismatch",
                f"test evidence {evidence_id} repository root differs from the artifact root",
            )
        head_commit = str(repository.get("head_commit", "")).strip()
        if not git_commit_exists(self.root, head_commit):
            return None, _issue(
                "test_commit_not_found",
                f"test evidence {evidence_id} commit does not exist: "
                f"{head_commit or '<missing>'}",
            )
        actual_tree, tree_error = git_tree_hash(self.root, head_commit)
        declared_tree = str(repository.get("tree_hash", "")).strip()
        if tree_error or not is_pinned_commit(declared_tree) or declared_tree != actual_tree:
            return None, _issue(
                "test_tree_mismatch",
                f"test evidence {evidence_id} tree hash does not match "
                f"{head_commit}^{{tree}}",
            )
        dirty = repository.get("dirty")
        if not isinstance(dirty, bool):
            return None, _issue(
                "test_dirty_state_invalid",
                f"test evidence {evidence_id} repository.dirty must be boolean",
            )
        tested_paths_raw = record.get("tested_paths", [])
        if not isinstance(tested_paths_raw, list) or not tested_paths_raw:
            return None, _issue(
                "test_paths_missing",
                f"test evidence {evidence_id} requires tested repository paths",
            )
        tested_paths = []
        for raw_path in tested_paths_raw:
            path, path_error = _safe_relative_path(raw_path)
            if not path:
                return None, _issue("test_path_invalid", path_error)
            _, blob_error = git_blob_text(self.root, head_commit, path)
            if blob_error:
                return None, _issue(
                    "test_path_not_in_snapshot",
                    f"cannot read tested path {head_commit}:{path}",
                )
            tested_paths.append(path)

        try:
            exit_code = int(record.get("exit_code"))
            duration = float(record.get("duration_seconds"))
        except (TypeError, ValueError):
            return None, _issue(
                "test_result_invalid",
                f"test evidence {evidence_id} requires numeric exit code and duration",
            )
        if duration < 0:
            return None, _issue(
                "test_result_invalid",
                f"test evidence {evidence_id} duration cannot be negative",
            )
        status = str(record.get("status", "")).strip().lower()
        if status not in {"passed", "failed"}:
            return None, _issue(
                "test_result_invalid",
                f"test evidence {evidence_id} status must be passed or failed",
            )
        passed = status == "passed" and exit_code == 0
        if (status == "passed") != (exit_code == 0):
            return None, _issue(
                "test_result_inconsistent",
                f"test evidence {evidence_id} status and exit code disagree",
            )
        timestamps: Dict[str, dt.datetime] = {}
        for field in ("started_at", "finished_at"):
            value = str(record.get(field, "")).strip()
            if not value:
                return None, _issue(
                    "test_timestamp_missing",
                    f"test evidence {evidence_id} requires {field}",
                )
            try:
                parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None, _issue(
                    "test_timestamp_invalid",
                    f"test evidence {evidence_id} has invalid {field}",
                )
            if parsed.tzinfo is None:
                return None, _issue(
                    "test_timestamp_invalid",
                    f"test evidence {evidence_id} {field} requires a timezone",
                )
            timestamps[field] = parsed
        if timestamps["finished_at"] < timestamps["started_at"]:
            return None, _issue(
                "test_timestamp_invalid",
                f"test evidence {evidence_id} finishes before it starts",
            )
        for field in ("stdout_sha256", "stderr_sha256"):
            if not SHA256_RE.fullmatch(str(record.get(field, "")).strip()):
                return None, _issue(
                    "test_output_hash_invalid",
                    f"test evidence {evidence_id} requires a SHA-256 value in {field}",
                )
        review = record.get("relevance_review")
        if not isinstance(review, dict):
            return None, _issue(
                "test_relevance_review_missing",
                f"test evidence {evidence_id} requires a relevance review",
            )
        review_status = str(review.get("status", "")).strip().lower()
        if review_status not in {"approved", "pending", "rejected"}:
            return None, _issue(
                "test_relevance_review_invalid",
                f"test evidence {evidence_id} has invalid relevance review status",
            )
        reviewer = str(review.get("reviewer", "")).strip()
        rationale = str(review.get("rationale", "")).strip()
        reviewed_at = str(review.get("reviewed_at", "")).strip()
        relevance_approved = (
            review_status == "approved"
            and bool(reviewer)
            and bool(rationale)
            and bool(reviewed_at)
        )
        return {
            "kind": "test",
            "id": evidence_id,
            "schema": HOST_TEST_RECEIPT_SCHEMA,
            "origin": "host-tool",
            "execution_id": execution_id,
            "argv": list(argv),
            "command": shlex.join(argv),
            "framework": framework,
            "test_target": test_target,
            "selectors": clean_selectors,
            "tested_paths": list(dict.fromkeys(tested_paths)),
            "covers": list(dict.fromkeys(str(item).strip() for item in covers)),
            "head_commit": head_commit,
            "tree_hash": actual_tree,
            "dirty": dirty,
            "snapshot_clean": not dirty,
            "exit_code": exit_code,
            "status": status,
            "passed": passed,
            "summary": _summary(record.get("summary", "")) or f"exit code {exit_code}",
            "stdout_summary": _summary(record.get("stdout_summary", "")),
            "stderr_summary": _summary(record.get("stderr_summary", "")),
            "stdout_sha256": str(record.get("stdout_sha256", "")).strip(),
            "stderr_sha256": str(record.get("stderr_sha256", "")).strip(),
            "duration_seconds": duration,
            "started_at": str(record.get("started_at", "")).strip(),
            "finished_at": str(record.get("finished_at", "")).strip(),
            "relevance_status": review_status,
            "relevance_reviewer": reviewer,
            "relevance_rationale": rationale,
            "relevance_approved": relevance_approved,
            "primary": passed and not dirty and relevance_approved,
        }, None


def _summary(text: str, limit: int = 2000) -> str:
    normalized = str(text or "").strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[-limit:]

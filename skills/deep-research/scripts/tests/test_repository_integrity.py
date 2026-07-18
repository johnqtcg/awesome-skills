"""Repository evidence must be proven against Git, files, and real processes."""

import importlib.util
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HAS_RG = shutil.which("rg") is not None
_NO_RG_REASON = (
    "ripgrep not installed — search-codebase itself fails fast with a clear "
    "message (verified in test_subcommand_smoke.py)"
)

SCRIPT = Path(__file__).resolve().parents[1] / "deep_research.py"
spec = importlib.util.spec_from_file_location("deep_research_repository_tests", SCRIPT)
deep_research = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = deep_research
spec.loader.exec_module(deep_research)


def run_git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr)
    return proc.stdout.strip()


def run_cli(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *argv],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


class RepositoryFixture(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        run_git(self.root, "init", "-q")
        run_git(self.root, "config", "user.email", "tests@example.com")
        run_git(self.root, "config", "user.name", "Deep Research Tests")
        self.source = self.root / "app.py"
        self.source.write_text(
            'VALUE = "committed"\n\ndef authenticate(token):\n    return token == "ok"\n',
            encoding="utf-8",
        )
        self.test_source = self.root / "test_app.py"
        self.test_source.write_text(
            "import unittest\n\n"
            "from app import authenticate\n\n\n"
            "class AuthTest(unittest.TestCase):\n"
            "    def test_accepts_ok(self):\n"
            '        self.assertTrue(authenticate("ok"))\n',
            encoding="utf-8",
        )
        run_git(self.root, "add", "app.py", "test_app.py")
        run_git(self.root, "commit", "-q", "-m", "feat: add authentication")
        self.commit = run_git(self.root, "rev-parse", "HEAD")
        self.tree = run_git(self.root, "rev-parse", "HEAD^{tree}")
        self.subject = run_git(self.root, "show", "-s", "--format=%s", "HEAD")

    def search(self, pattern: str) -> dict:
        out = self.root / f"evidence-{len(list(self.root.glob('evidence-*.json')))}.json"
        proc = run_cli(
            "search-codebase",
            "--pattern",
            pattern,
            "--root",
            str(self.root),
            "--output",
            str(out),
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(out.read_text(encoding="utf-8"))

    def code_finding(self, evidence_id: str = "code-1") -> dict:
        return {
            "findings": [
                {
                    "title": "Authentication implementation",
                    "claim_type": "code_fact",
                    "confidence": "high",
                    "analysis": "The repository compares the token with ok.",
                    "evidence": [{"kind": "code", "id": evidence_id}],
                }
            ]
        }

    def runtime_finding(
        self,
        *,
        code_ids: list[str] | None = None,
        test_ids: list[str] | None = None,
    ) -> dict:
        code_ids = code_ids or ["code-1"]
        test_ids = test_ids or ["test-1"]
        return {
            "findings": [
                {
                    "id": "finding-auth-runtime",
                    "title": "Authentication runtime behavior",
                    "claim_type": "runtime_behavior",
                    "confidence": "high",
                    "analysis": "The authentication check passes its test.",
                    "evidence": (
                        [{"kind": "code", "id": evidence_id} for evidence_id in code_ids]
                        + [{"kind": "test", "id": evidence_id} for evidence_id in test_ids]
                    ),
                }
            ]
        }

    def host_test_receipt(
        self,
        *,
        covers: list[str] | None = None,
        tested_paths: list[str] | None = None,
        commit: str | None = None,
        tree: str | None = None,
        dirty: bool = False,
        relevance_status: str = "approved",
        receipt_id: str = "test-1",
    ) -> dict:
        argv = [
            sys.executable,
            "-m",
            "unittest",
            "test_app.AuthTest.test_accepts_ok",
        ]
        proc = subprocess.run(
            argv,
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        stdout_hash = hashlib.sha256(proc.stdout.encode("utf-8")).hexdigest()
        stderr_hash = hashlib.sha256(proc.stderr.encode("utf-8")).hexdigest()
        return {
            "schema": "deep-research/host-test-receipt-v2",
            "id": receipt_id,
            "kind": "test",
            "origin": "host-tool",
            "execution_id": hashlib.sha256(
                (" ".join(argv) + stdout_hash + stderr_hash).encode("utf-8")
            ).hexdigest(),
            "argv": argv,
            "command": " ".join(argv),
            "framework": "unittest",
            "test_target": "test_app.AuthTest.test_accepts_ok",
            "selectors": ["test_app.AuthTest.test_accepts_ok"],
            "tested_paths": tested_paths or ["app.py", "test_app.py"],
            "covers": covers or ["finding-auth-runtime", "code-1"],
            "repository": {
                "root": str(self.root.resolve()),
                "head_commit": commit or self.commit,
                "tree_hash": tree or self.tree,
                "dirty": dirty,
            },
            "started_at": "2026-07-18T00:00:00+00:00",
            "finished_at": "2026-07-18T00:00:01+00:00",
            "duration_seconds": 1.0,
            "exit_code": 0,
            "status": "passed",
            "summary": proc.stdout.strip() or "unittest passed",
            "stdout_summary": proc.stdout.strip(),
            "stderr_summary": proc.stderr.strip(),
            "stdout_sha256": stdout_hash,
            "stderr_sha256": stderr_hash,
            "relevance_review": {
                "status": relevance_status,
                "reviewer": "repository-integrity-test",
                "rationale": (
                    "The selected unittest directly exercises authenticate('ok'), "
                    "which is the runtime claim."
                ),
                "reviewed_at": "2026-07-18T00:00:02+00:00",
            },
        }


class TestSearchCodebaseProvenance(RepositoryFixture):
    @unittest.skipUnless(_HAS_RG, _NO_RG_REASON)
    def test_dirty_worktree_match_is_never_labeled_head(self) -> None:
        self.source.write_text(
            self.source.read_text(encoding="utf-8") + "\nDIRTY_ONLY = True\n",
            encoding="utf-8",
        )
        payload = self.search("DIRTY_ONLY")
        record = next(row for row in payload["evidence"] if row["kind"] == "code")
        self.assertEqual("working-tree-unpinned", record["commit"])
        self.assertEqual("worktree", record["snapshot"])
        self.assertEqual(str(self.root.resolve()), payload["root"])

    @unittest.skipUnless(_HAS_RG, _NO_RG_REASON)
    def test_clean_match_is_pinned_to_real_head(self) -> None:
        payload = self.search("return token")
        record = next(row for row in payload["evidence"] if row["kind"] == "code")
        self.assertEqual(self.commit, record["commit"])
        self.assertEqual("commit", record["snapshot"])

        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=payload,
            findings=self.code_finding(record["id"]),
        )
        self.assertEqual("Full", summary["degradation"])
        self.assertEqual("high", summary["findings"][0]["effective_confidence"])

    def test_snapshot_codebase_reports_clean_head_and_tree(self) -> None:
        with tempfile.TemporaryDirectory() as output_directory:
            output = Path(output_directory) / "snapshot.json"
            proc = run_cli(
                "snapshot-codebase",
                "--root",
                str(self.root),
                "--output",
                str(output),
            )
            self.assertEqual(0, proc.returncode, proc.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual("deep-research/repository-snapshot-v1", payload["schema"])
        self.assertEqual(str(self.root.resolve()), payload["root"])
        self.assertEqual(self.commit, payload["head_commit"])
        self.assertEqual(self.tree, payload["tree_hash"])
        self.assertFalse(payload["dirty"])
        self.assertRegex(payload["generated_at"], r"^\d{4}-\d{2}-\d{2}T")

    def test_snapshot_codebase_reports_dirty_without_relabeling_head(self) -> None:
        self.source.write_text(
            self.source.read_text(encoding="utf-8") + "\nDIRTY_ONLY = True\n",
            encoding="utf-8",
        )
        with tempfile.TemporaryDirectory() as output_directory:
            output = Path(output_directory) / "snapshot.json"
            proc = run_cli(
                "snapshot-codebase",
                "--root",
                str(self.root),
                "--output",
                str(output),
            )
            self.assertEqual(0, proc.returncode, proc.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(self.commit, payload["head_commit"])
        self.assertEqual(self.tree, payload["tree_hash"])
        self.assertTrue(payload["dirty"])

    def test_snapshot_codebase_fails_closed_outside_git(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "snapshot.json"
            proc = run_cli(
                "snapshot-codebase",
                "--root",
                str(root),
                "--output",
                str(output),
            )
            self.assertEqual(2, proc.returncode)
            self.assertFalse(output.exists())
            self.assertIn("Git repository", proc.stderr)

    def test_snapshot_codebase_rejects_output_inside_repository(self) -> None:
        output = self.root / "snapshot.json"
        proc = run_cli(
            "snapshot-codebase",
            "--root",
            str(self.root),
            "--output",
            str(output),
        )
        self.assertEqual(2, proc.returncode)
        self.assertFalse(output.exists())
        self.assertIn("outside the Git repository", proc.stderr)

    @unittest.skipUnless(_HAS_RG, _NO_RG_REASON)
    def test_dirty_match_can_be_used_but_not_as_high(self) -> None:
        self.source.write_text(
            self.source.read_text(encoding="utf-8") + "\nDIRTY_ONLY = True\n",
            encoding="utf-8",
        )
        payload = self.search("DIRTY_ONLY")
        record = next(row for row in payload["evidence"] if row["kind"] == "code")
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=payload,
            findings=self.code_finding(record["id"]),
        )
        self.assertTrue(summary["findings"][0]["usable"])
        self.assertEqual("medium", summary["findings"][0]["effective_confidence"])
        self.assertEqual("Partial", summary["degradation"])


class TestRepositoryBoundaryValidation(RepositoryFixture):
    def test_duplicate_evidence_ids_are_rejected_as_ambiguous(self) -> None:
        artifact = {
            "root": str(self.root),
            "evidence": [
                {
                    "id": "code-1",
                    "kind": "code",
                    "path": "app.py",
                    "line": 4,
                    "excerpt": '    return token == "ok"',
                    "commit": self.commit,
                },
                {
                    "id": "code-1",
                    "kind": "code",
                    "path": "fabricated.py",
                    "line": 1,
                    "excerpt": "fabricated",
                    "commit": "deadbee",
                },
            ],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=artifact,
            findings=self.code_finding(),
        )
        self.assertFalse(summary["findings"][0]["usable"])
        self.assertTrue(
            any(
                issue["code"] == "duplicate_repository_evidence_id"
                for issue in summary["issues"]
            )
        )

    def test_nonexistent_commit_and_path_are_rejected(self) -> None:
        artifact = {
            "root": str(self.root),
            "evidence": [
                {
                    "id": "code-1",
                    "kind": "code",
                    "path": "does/not/exist.py",
                    "line": 999,
                    "excerpt": "fabricated line",
                    "commit": "deadbee",
                    "snapshot": "commit",
                }
            ],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=artifact,
            findings=self.code_finding(),
        )
        self.assertFalse(summary["findings"][0]["usable"])
        self.assertEqual("Blocked", summary["degradation"])
        self.assertTrue(
            any(issue["code"] == "git_commit_not_found" for issue in summary["issues"])
        )

    def test_line_and_excerpt_must_match_commit_blob(self) -> None:
        artifact = {
            "root": str(self.root),
            "evidence": [
                {
                    "id": "code-1",
                    "kind": "code",
                    "path": "app.py",
                    "line": 4,
                    "excerpt": "return token == fabricated",
                    "commit": self.commit,
                    "snapshot": "commit",
                }
            ],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=artifact,
            findings=self.code_finding(),
        )
        self.assertFalse(summary["findings"][0]["usable"])
        self.assertTrue(
            any(issue["code"] == "code_excerpt_mismatch" for issue in summary["issues"])
        )

    def test_commit_subject_is_read_back_and_compared(self) -> None:
        artifact = {
            "root": str(self.root),
            "evidence": [
                {
                    "id": "commit-1",
                    "kind": "commit",
                    "commit": self.commit,
                    "subject": "fabricated subject",
                }
            ],
        }
        findings = {
            "findings": [
                {
                    "title": "Commit purpose",
                    "claim_type": "analysis",
                    "confidence": "medium",
                    "analysis": "The commit added authentication.",
                    "evidence": [{"kind": "commit", "id": "commit-1"}],
                }
            ]
        }
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=artifact,
            findings=findings,
        )
        self.assertFalse(summary["findings"][0]["usable"])
        self.assertTrue(
            any(
                issue["code"] == "commit_subject_mismatch"
                for issue in summary["issues"]
            )
        )

    def test_path_escape_is_rejected(self) -> None:
        artifact = {
            "root": str(self.root),
            "evidence": [
                {
                    "id": "code-1",
                    "kind": "code",
                    "path": "../outside.py",
                    "line": 1,
                    "excerpt": "outside",
                    "commit": "working-tree-unpinned",
                    "snapshot": "worktree",
                }
            ],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=artifact,
            findings=self.code_finding(),
        )
        self.assertFalse(summary["findings"][0]["usable"])
        self.assertTrue(
            any(issue["code"] == "repository_path_escape" for issue in summary["issues"])
        )


class TestHostAttestedTestEvidence(RepositoryFixture):
    def valid_code_record(
        self,
        *,
        evidence_id: str = "code-1",
        path: str = "app.py",
        line: int = 4,
        excerpt: str = '    return token == "ok"',
        commit: str | None = None,
    ) -> dict:
        return {
            "id": evidence_id,
            "kind": "code",
            "path": path,
            "line": line,
            "excerpt": excerpt,
            "commit": commit or self.commit,
            "snapshot": "commit",
        }

    def legacy_hand_written_test_record(self, argv: list[str]) -> dict:
        return {
            "id": "test-1",
            "kind": "test",
            "command": " ".join(argv),
            "argv": argv,
            "cwd": ".",
            "status": "passed",
            "exit_code": 0,
            "summary": "hand-written pass",
        }

    def test_legacy_hand_written_pass_is_not_verified(self) -> None:
        artifact = {
            "root": str(self.root),
            "evidence": [
                self.valid_code_record(),
                self.legacy_hand_written_test_record(
                    [sys.executable, "-c", "print('not a behavioral test')"]
                ),
            ],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=artifact,
            findings=self.runtime_finding(),
        )
        self.assertEqual("medium", summary["findings"][0]["effective_confidence"])
        self.assertEqual("Partial", summary["degradation"])
        self.assertTrue(
            any(
                issue["code"] == "unsupported_test_receipt_schema"
                for issue in summary["issues"]
            )
        )

    def test_valid_host_receipt_can_support_runtime_high(self) -> None:
        artifact = {
            "root": str(self.root),
            "evidence": [
                self.valid_code_record(),
                self.host_test_receipt(),
            ],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=artifact,
            findings=self.runtime_finding(),
        )
        self.assertEqual("Full", summary["degradation"])
        self.assertEqual("high", summary["findings"][0]["effective_confidence"])

    def test_unpinned_code_cannot_hide_behind_pinned_code(self) -> None:
        self.source.write_text(
            self.source.read_text(encoding="utf-8") + "\nDIRTY_ONLY = True\n",
            encoding="utf-8",
        )
        artifact = {
            "root": str(self.root),
            "evidence": [
                self.valid_code_record(),
                {
                    "id": "code-2",
                    "kind": "code",
                    "path": "app.py",
                    "line": 6,
                    "excerpt": "DIRTY_ONLY = True",
                    "commit": "working-tree-unpinned",
                    "snapshot": "worktree",
                },
                self.host_test_receipt(),
            ],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=artifact,
            findings=self.runtime_finding(code_ids=["code-1", "code-2"]),
        )
        finding = summary["findings"][0]
        self.assertEqual("Partial", summary["degradation"])
        self.assertEqual("medium", finding["effective_confidence"])
        self.assertEqual(
            ["code", "code", "test"],
            [row["kind"] for row in finding["verified_evidence"]],
        )
        self.assertIn(
            "unpinned code evidence: code-2",
            " ".join(finding["downgrade_reasons"]),
        )

    def test_unverified_cited_code_cannot_be_ignored(self) -> None:
        artifact = {
            "root": str(self.root),
            "evidence": [
                self.valid_code_record(),
                self.host_test_receipt(),
            ],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=artifact,
            findings=self.runtime_finding(code_ids=["code-1", "code-missing"]),
        )
        finding = summary["findings"][0]
        self.assertEqual("medium", finding["effective_confidence"])
        self.assertIn(
            "unresolved: code-missing",
            " ".join(finding["downgrade_reasons"]),
        )

    def test_separate_receipts_cannot_collectively_cover_code_set(self) -> None:
        artifact = {
            "root": str(self.root),
            "evidence": [
                self.valid_code_record(),
                self.valid_code_record(
                    evidence_id="code-2",
                    path="test_app.py",
                    line=8,
                    excerpt='        self.assertTrue(authenticate("ok"))',
                ),
                self.host_test_receipt(
                    receipt_id="test-1",
                    covers=["finding-auth-runtime", "code-1"],
                ),
                self.host_test_receipt(
                    receipt_id="test-2",
                    covers=["finding-auth-runtime", "code-2"],
                ),
            ],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=artifact,
            findings=self.runtime_finding(
                code_ids=["code-1", "code-2"],
                test_ids=["test-1", "test-2"],
            ),
        )
        finding = summary["findings"][0]
        self.assertEqual("medium", finding["effective_confidence"])
        self.assertIn(
            "single test receipt must cover finding finding-auth-runtime "
            "and every code evidence ID",
            " ".join(finding["downgrade_reasons"]),
        )

    def test_runtime_code_set_must_share_one_commit_tree(self) -> None:
        (self.root / "README.md").write_text("second snapshot\n", encoding="utf-8")
        run_git(self.root, "add", "README.md")
        run_git(self.root, "commit", "-q", "-m", "docs: second snapshot")
        second_commit = run_git(self.root, "rev-parse", "HEAD")
        second_tree = run_git(self.root, "rev-parse", "HEAD^{tree}")
        artifact = {
            "root": str(self.root),
            "evidence": [
                self.valid_code_record(),
                self.valid_code_record(
                    evidence_id="code-2",
                    commit=second_commit,
                ),
                self.host_test_receipt(
                    covers=["finding-auth-runtime", "code-1", "code-2"],
                    commit=second_commit,
                    tree=second_tree,
                ),
            ],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=artifact,
            findings=self.runtime_finding(code_ids=["code-1", "code-2"]),
        )
        finding = summary["findings"][0]
        self.assertEqual("medium", finding["effective_confidence"])
        self.assertIn(
            "all cited code evidence must use one pinned commit/tree",
            " ".join(finding["downgrade_reasons"]),
        )

    def test_import_test_receipt_appends_without_executing_argv(self) -> None:
        code_path = self.root / "code.json"
        receipt_path = self.root / "receipt.json"
        output_path = self.root / "combined.json"
        code_path.write_text(
            json.dumps(
                {
                    "root": str(self.root),
                    "evidence": [self.valid_code_record()],
                }
            ),
            encoding="utf-8",
        )
        receipt = self.host_test_receipt()
        receipt["argv"][0] = "/definitely/not/installed/python3"
        receipt["command"] = " ".join(receipt["argv"])
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

        proc = run_cli(
            "import-test-receipt",
            "--receipt",
            str(receipt_path),
            "--code-evidence",
            str(code_path),
            "--output",
            str(output_path),
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        combined = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(["code-1", "test-1"], [
            row["id"] for row in combined["evidence"]
        ])

    def test_generic_python_success_command_is_not_behavioral_proof(self) -> None:
        receipt = self.host_test_receipt()
        receipt["argv"] = [sys.executable, "-c", "print('verified test run')"]
        receipt["command"] = " ".join(receipt["argv"])
        artifact = {
            "root": str(self.root),
            "evidence": [self.valid_code_record(), receipt],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=artifact,
            findings=self.runtime_finding(),
        )
        self.assertEqual("medium", summary["findings"][0]["effective_confidence"])
        self.assertTrue(
            any(
                issue["code"] == "test_argv_framework_mismatch"
                for issue in summary["issues"]
            )
        )

    def test_receipt_must_cover_finding_and_code_evidence(self) -> None:
        artifact = {
            "root": str(self.root),
            "evidence": [
                self.valid_code_record(),
                self.host_test_receipt(covers=["finding-auth-runtime"]),
            ],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=artifact,
            findings=self.runtime_finding(),
        )
        self.assertEqual("medium", summary["findings"][0]["effective_confidence"])
        self.assertIn(
            "does not cover code evidence code-1",
            " ".join(summary["findings"][0]["downgrade_reasons"]),
        )

    def test_receipt_not_covering_finding_is_not_support(self) -> None:
        artifact = {
            "root": str(self.root),
            "evidence": [
                self.valid_code_record(),
                self.host_test_receipt(covers=["code-1"]),
            ],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=artifact,
            findings=self.runtime_finding(),
        )
        verified = summary["findings"][0]["verified_evidence"]
        self.assertEqual(["code"], [row["kind"] for row in verified])
        self.assertTrue(
            any(
                issue["code"] == "test_does_not_cover_finding"
                for issue in summary["issues"]
            )
        )

    def test_receipt_requires_explicit_relevance_approval(self) -> None:
        artifact = {
            "root": str(self.root),
            "evidence": [
                self.valid_code_record(),
                self.host_test_receipt(relevance_status="pending"),
            ],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=artifact,
            findings=self.runtime_finding(),
        )
        self.assertEqual("medium", summary["findings"][0]["effective_confidence"])
        self.assertIn(
            "relevance review is not approved",
            " ".join(summary["findings"][0]["downgrade_reasons"]),
        )

    def test_dirty_test_snapshot_cannot_support_runtime_high(self) -> None:
        artifact = {
            "root": str(self.root),
            "evidence": [
                self.valid_code_record(),
                self.host_test_receipt(dirty=True),
            ],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=artifact,
            findings=self.runtime_finding(),
        )
        self.assertEqual("medium", summary["findings"][0]["effective_confidence"])
        self.assertIn(
            "dirty test snapshot",
            " ".join(summary["findings"][0]["downgrade_reasons"]),
        )

    def test_test_and_code_commits_must_match(self) -> None:
        (self.root / "README.md").write_text("second snapshot\n", encoding="utf-8")
        run_git(self.root, "add", "README.md")
        run_git(self.root, "commit", "-q", "-m", "docs: second snapshot")
        second_commit = run_git(self.root, "rev-parse", "HEAD")
        second_tree = run_git(self.root, "rev-parse", "HEAD^{tree}")
        artifact = {
            "root": str(self.root),
            "evidence": [
                self.valid_code_record(),
                self.host_test_receipt(commit=second_commit, tree=second_tree),
            ],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=artifact,
            findings=self.runtime_finding(),
        )
        self.assertEqual("medium", summary["findings"][0]["effective_confidence"])
        self.assertIn(
            "snapshot does not match code evidence code-1",
            " ".join(summary["findings"][0]["downgrade_reasons"]),
        )

    def test_tested_paths_must_include_claimed_code_path(self) -> None:
        artifact = {
            "root": str(self.root),
            "evidence": [
                self.valid_code_record(),
                self.host_test_receipt(tested_paths=["test_app.py"]),
            ],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=artifact,
            findings=self.runtime_finding(),
        )
        self.assertEqual("medium", summary["findings"][0]["effective_confidence"])
        self.assertIn(
            "does not name tested code path app.py",
            " ".join(summary["findings"][0]["downgrade_reasons"]),
        )

    def test_fabricated_tree_hash_is_rejected(self) -> None:
        artifact = {
            "root": str(self.root),
            "evidence": [
                self.valid_code_record(),
                self.host_test_receipt(tree="0" * 40),
            ],
        }
        summary = deep_research.validate_research_bundle(
            research_kind="codebase",
            results=[],
            contents=[],
            code_evidence=artifact,
            findings=self.runtime_finding(),
        )
        self.assertTrue(summary["findings"][0]["usable"])
        self.assertEqual("medium", summary["findings"][0]["effective_confidence"])
        self.assertTrue(
            any(issue["code"] == "test_tree_mismatch" for issue in summary["issues"])
        )

    def test_run_test_and_replay_flags_are_removed(self) -> None:
        parser = deep_research.build_parser()
        sub_actions = [
            action
            for action in parser._actions
            if isinstance(action, deep_research.argparse._SubParsersAction)
        ]
        self.assertNotIn("run-test", sub_actions[0].choices)
        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "validate",
                    "--research-kind",
                    "codebase",
                    "--code-evidence",
                    "code.json",
                    "--findings",
                    "findings.json",
                    "--replay-tests",
                ]
            )


if __name__ == "__main__":
    unittest.main()

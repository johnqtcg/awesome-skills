"""Guard-path tests for scripts/verify_against_server.sh and verify_matrix.sh.

The probes themselves need a live MySQL. Everything *around* them — the refusal
to run without an explicit disposable declaration, the schema-name validation,
the credential handling, the cleanup — is what stands between a copy-pasted
command and a dropped production schema, and all of it is testable here with a
stub `mysql` on PATH.

A stub is used rather than mocking, because the property under test is what the
script puts on the command line and in the filesystem, which only a real process
boundary can observe.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import stat
import subprocess

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = SKILL_DIR / "scripts" / "verify_against_server.sh"
MATRIX_SCRIPT = SKILL_DIR / "scripts" / "verify_matrix.sh"

STUB = """#!/bin/bash
echo "ARGV: $*" >> "$ARGV_LOG"
args="$*"
if [[ "$args" == *"SELECT VERSION()"* ]]; then echo "8.0.35"; exit 0; fi
if [[ "$args" == *"SHOW DATABASES LIKE"* ]]; then echo "$STUB_EXISTING_SCHEMA"; exit 0; fi
if [[ "$args" == *"SELECT 1"* ]]; then exit "${STUB_CONNECT_RC:-0}"; fi
exit 0
"""


# Externals the scripts actually call. A PATH with these and nothing else gives a
# deterministic "mysql is absent" without depending on whether the host has it.
_REQUIRED_BINARIES = ("mktemp", "chmod", "rm", "awk", "tr", "sed", "cat", "comm",
                      "sort", "grep", "ls", "wc", "printf", "env", "bash")


def minimal_path(tmp_path: pathlib.Path, include_mysql: pathlib.Path | None = None) -> str:
    """A PATH containing coreutils but no mysql, unless one is supplied."""
    bindir = tmp_path / "minbin"
    bindir.mkdir(exist_ok=True)
    for name in _REQUIRED_BINARIES:
        found = shutil.which(name)
        if found and not (bindir / name).exists():
            (bindir / name).symlink_to(found)
    if include_mysql is not None:
        (bindir / "mysql").symlink_to(include_mysql)
    return str(bindir)


@pytest.fixture
def stub_env(tmp_path):
    """A PATH containing only a fake mysql, plus an argv log."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "mysql"
    stub.write_text(STUB, encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "argv.log"
    log.write_text("", encoding="utf-8")
    env = dict(os.environ)
    env["PATH"] = f"{bindir}{os.pathsep}{env['PATH']}"
    env["ARGV_LOG"] = str(log)
    env["TMPDIR"] = str(tmp_path)
    env["STUB_EXISTING_SCHEMA"] = ""
    env.pop("MYSQL_PASSWORD", None)
    return env, log, tmp_path


def run(env, **overrides) -> subprocess.CompletedProcess:
    e = dict(env)
    e.update({k: str(v) for k, v in overrides.items()})
    return subprocess.run(["bash", str(SCRIPT)], env=e, capture_output=True,
                          text=True, timeout=120)


class TestOptInGate:
    def test_not_requested_skips_with_zero(self, stub_env):
        env, _, _ = stub_env
        p = run(env)
        assert p.returncode == 0
        assert "SKIP" in p.stdout
        assert "NOT been executed" in p.stdout, (
            "a skip must state that nothing was verified, or it reads as a pass"
        )

    def test_requested_without_disposable_declaration_refuses(self, stub_env):
        env, _, _ = stub_env
        p = run(env, MYSQL_MIGRATION_VERIFY=1)
        assert p.returncode == 3
        assert "disposable" in p.stderr.lower()

    def test_declaring_disposable_proceeds(self, stub_env):
        env, _, _ = stub_env
        p = run(env, MYSQL_MIGRATION_VERIFY=1, MYSQL_MIGRATION_VERIFY_DISPOSABLE="yes")
        assert p.returncode in (0, 1), p.stderr
        assert "Server: 8.0.35" in p.stdout

    def test_a_wrong_value_does_not_count_as_declaring(self, stub_env):
        env, _, _ = stub_env
        for value in ("true", "1", "YES", "y"):
            p = run(env, MYSQL_MIGRATION_VERIFY=1, MYSQL_MIGRATION_VERIFY_DISPOSABLE=value)
            assert p.returncode == 3, f"{value!r} must not satisfy the gate"


class TestSchemaNameValidation:
    """The schema name is interpolated into CREATE/DROP DDL."""

    @pytest.mark.parametrize("name", [
        "probe`; DROP DATABASE prod; --",
        "probe;drop",
        "1leading_digit",
        "has-hyphen",
        "has space",
        "has.dot",
        "x" * 64,
        "../../etc",
    ])
    def test_unsafe_names_are_refused(self, stub_env, name):
        env, log, _ = stub_env
        p = run(env, MYSQL_MIGRATION_VERIFY=1, MYSQL_MIGRATION_VERIFY_DISPOSABLE="yes",
                MYSQL_MIGRATION_VERIFY_SCHEMA=name)
        assert p.returncode == 3, f"accepted unsafe schema name {name!r}"
        assert "unsafe schema name" in p.stderr
        assert log.read_text(encoding="utf-8") == "", (
            "the script must refuse before issuing any statement"
        )

    @pytest.mark.parametrize("name", ["probe", "Probe_1", "a", "x" * 63])
    def test_safe_names_are_accepted(self, stub_env, name):
        env, _, _ = stub_env
        p = run(env, MYSQL_MIGRATION_VERIFY=1, MYSQL_MIGRATION_VERIFY_DISPOSABLE="yes",
                MYSQL_MIGRATION_VERIFY_SCHEMA=name)
        assert "unsafe schema name" not in p.stderr


class TestCredentialHandling:
    def test_password_never_appears_in_argv(self, stub_env):
        env, log, _ = stub_env
        secret = "pw-that-must-not-leak-9f3a"
        run(env, MYSQL_MIGRATION_VERIFY=1, MYSQL_MIGRATION_VERIFY_DISPOSABLE="yes",
            MYSQL_PASSWORD=secret)
        argv = log.read_text(encoding="utf-8")
        assert argv.strip(), "the stub should have been invoked at least once"
        assert secret not in argv, (
            "argv is world-readable via ps for the life of the process; credentials must go "
            "through the option file"
        )
        assert "--defaults-file=" in argv

    def test_option_file_is_removed_on_success(self, stub_env):
        env, _, tmp = stub_env
        run(env, MYSQL_MIGRATION_VERIFY=1, MYSQL_MIGRATION_VERIFY_DISPOSABLE="yes",
            MYSQL_PASSWORD="secret")
        leftovers = list(tmp.glob("mysql-migration-verify.*"))
        assert not leftovers, f"credential file left behind: {leftovers}"

    def test_option_file_is_removed_when_the_server_is_unreachable(self, stub_env):
        """The trap must be armed before the first query, not after it succeeds."""
        env, _, tmp = stub_env
        p = run(env, MYSQL_MIGRATION_VERIFY=1, MYSQL_MIGRATION_VERIFY_DISPOSABLE="yes",
                MYSQL_PASSWORD="secret", STUB_EXISTING_SCHEMA="",
                MYSQL_HOST="127.0.0.1", STUB_CONNECT_RC=1)
        leftovers = list(tmp.glob("mysql-migration-verify.*"))
        assert not leftovers, f"credential file leaked on an early exit: {leftovers}"
        assert p.returncode in (0, 1, 3)


class TestExistingSchemaGuard:
    def test_refuses_to_reuse_an_existing_schema(self, stub_env):
        env, log, _ = stub_env
        p = run(env, MYSQL_MIGRATION_VERIFY=1, MYSQL_MIGRATION_VERIFY_DISPOSABLE="yes",
                STUB_EXISTING_SCHEMA="mysql_migration_matrix_probe")
        assert p.returncode == 3
        assert "already exists" in p.stderr
        argv = log.read_text(encoding="utf-8")
        assert "CREATE DATABASE" not in argv and "DROP DATABASE" not in argv, (
            "refusing must not be preceded by creating, nor followed by dropping someone "
            "else's schema"
        )


class TestMissingClient:
    def test_absent_mysql_binary_is_exit_3_not_a_pass(self, tmp_path):
        env = dict(os.environ)
        env["PATH"] = minimal_path(tmp_path)
        env["MYSQL_MIGRATION_VERIFY"] = "1"
        env["MYSQL_MIGRATION_VERIFY_DISPOSABLE"] = "yes"
        p = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True,
                           text=True, timeout=120)
        assert p.returncode == 3, p.stderr
        assert "not on PATH" in p.stderr


class TestMatrixRunner:
    def test_unreachable_everything_skips_but_says_so(self, tmp_path):
        env = dict(os.environ)
        env["PATH"] = minimal_path(tmp_path)
        p = subprocess.run(["bash", str(MATRIX_SCRIPT)], env=env, capture_output=True,
                           text=True, timeout=180)
        assert p.returncode == 0, p.stderr
        assert "This is not a pass" in p.stdout

    def test_require_all_turns_unreachable_into_failure(self, tmp_path):
        env = dict(os.environ)
        env["PATH"] = minimal_path(tmp_path)
        p = subprocess.run(["bash", str(MATRIX_SCRIPT), "--require-all"], env=env,
                           capture_output=True, text=True, timeout=180)
        assert p.returncode == 3, p.stderr

    def test_compose_file_covers_the_claimed_version_range(self):
        compose = (SKILL_DIR / "scripts" / "verify-matrix.docker-compose.yml").read_text(
            encoding="utf-8")
        for image in ("mysql:5.7", "mysql:8.0.11", "mysql:8.0", "mysql:8.4", "mysql:9"):
            assert image in compose, f"matrix claims coverage without an instance: {image}"

    def test_8011_is_pinned_for_the_instant_boundary(self):
        compose = (SKILL_DIR / "scripts" / "verify-matrix.docker-compose.yml").read_text(
            encoding="utf-8")
        assert "8.0.11" in compose and "8.0.12" in compose, (
            "the INSTANT-clause boundary needs an instance on each side, and the reason "
            "must be written down"
        )

    def test_no_persistent_volumes(self):
        compose = (SKILL_DIR / "scripts" / "verify-matrix.docker-compose.yml").read_text(
            encoding="utf-8")
        assert "tmpfs:" in compose
        assert "\n    volumes:" not in compose, (
            "probe instances must not persist data between runs"
        )

    def test_bound_to_loopback_only(self):
        compose = (SKILL_DIR / "scripts" / "verify-matrix.docker-compose.yml").read_text(
            encoding="utf-8")
        for line in compose.split("\n"):
            if "ports:" in line:
                assert "127.0.0.1:" in line, f"probe port not bound to loopback: {line}"

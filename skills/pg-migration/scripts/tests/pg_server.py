"""Discovery and execution helper for the live-PostgreSQL test matrix.

Why this exists
---------------
Every other suite in this skill asserts against *our own* description of PostgreSQL.
A mutation sweep proves those assertions are load-bearing; it cannot prove they are
true. Two errors that survived a full green suite make the point:

* ``max(uuid)`` was documented as available. PostgreSQL ships no such aggregate on
  any supported version, so the recommended backfill loop would have failed at
  runtime with *function max(uuid) does not exist*.
* "FK constraints on a partitioned table may not be declared NOT VALID" was written
  as an unconditional rule. It holds on 14-17 and is **false** on 18.

Neither is detectable without a server. This module is the only place in the suite
that talks to one.

Discovery order
---------------
1. ``PG_MIGRATION_TEST_PSQL_<major>`` -- a shell command that reads SQL on stdin and
   writes results to stdout, e.g.
   ``docker exec -i pgmig16 psql -U postgres -d pgmig``.
2. ``PG_MIGRATION_TEST_DSN_<major>`` -- a libpq DSN used with a local ``psql``.
3. Running Docker containers named ``pgmig<major>`` (what
   ``scripts/pg_server_harness.sh`` creates).

If none resolve, the matrix **skips**. A skip is not a pass: the runner in
``pg_server_harness.sh`` exits non-zero when it finds no server at all, so an
environment without Docker cannot quietly report the matrix as verified.
"""

from __future__ import annotations

import dataclasses
import os
import shutil
import subprocess

# Majors the skill claims to support. Kept in sync with lint_migration.py by
# test_pg_server_matrix.py::test_supported_range_matches_the_linter.
SUPPORTED = (14, 15, 16, 17, 18)

# Every server call is bounded. A hung container must fail the run, not wedge CI.
CALL_TIMEOUT_S = 60


@dataclasses.dataclass(frozen=True)
class Server:
    major: int
    argv: list[str]
    origin: str  # how it was discovered, for the skip/report message

    def run(self, sql: str, *, on_error_stop: bool = False) -> subprocess.CompletedProcess:
        argv = list(self.argv)
        if on_error_stop:
            argv += ["-v", "ON_ERROR_STOP=1"]
        return subprocess.run(argv, input=sql, capture_output=True, text=True,
                              timeout=CALL_TIMEOUT_S)

    def scalar(self, sql: str) -> str:
        """Run SQL in unaligned tuples-only mode and return the LAST value printed.

        Taking the last line matters: psql echoes a command tag for non-SELECT
        statements (``SET``), so ``SET x = 0; SHOW x`` prints two lines on PG 15+ and
        one on PG 14. Reading the whole buffer would make the same assertion pass on
        one major and fail on another for a reason that has nothing to do with
        PostgreSQL's behaviour.
        """
        r = subprocess.run(self.argv + ["-tAc", sql], capture_output=True, text=True,
                           timeout=CALL_TIMEOUT_S)
        if r.returncode != 0:
            raise RuntimeError(f"PG{self.major}: {sql!r} failed: {r.stderr.strip()}")
        lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
        return lines[-1].strip() if lines else ""

    def rows(self, sql: str) -> list[list[str]]:
        raw = subprocess.run(self.argv + ["-tAF", "\x1f", "-c", sql],
                             capture_output=True, text=True, timeout=CALL_TIMEOUT_S)
        if raw.returncode != 0:
            raise RuntimeError(f"PG{self.major}: {sql!r} failed: {raw.stderr.strip()}")
        return [ln.split("\x1f") for ln in raw.stdout.splitlines() if ln]


def _docker_container_running(name: str) -> bool:
    if not shutil.which("docker"):
        return False
    try:
        r = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", name],
                           capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0 and r.stdout.strip() == "true"


def discover(major: int) -> Server | None:
    cmd = os.environ.get(f"PG_MIGRATION_TEST_PSQL_{major}")
    if cmd:
        return Server(major, cmd.split(), f"$PG_MIGRATION_TEST_PSQL_{major}")

    dsn = os.environ.get(f"PG_MIGRATION_TEST_DSN_{major}")
    if dsn and shutil.which("psql"):
        return Server(major, ["psql", dsn], f"$PG_MIGRATION_TEST_DSN_{major}")

    name = f"pgmig{major}"
    if _docker_container_running(name):
        return Server(major, ["docker", "exec", "-i", name,
                              "psql", "-U", "postgres", "-d", "pgmig"],
                      f"docker container {name}")
    return None


def discover_all() -> dict[int, Server]:
    found = {}
    for major in SUPPORTED:
        srv = discover(major)
        if srv is not None:
            found[major] = srv
    return found


def server_major(srv: Server) -> int:
    """Ask the server its own major version.

    Never trust the container name: a mislabelled container would silently attribute
    one version's behaviour to another, which is precisely the class of error this
    matrix exists to catch.
    """
    return int(srv.scalar("SHOW server_version_num")) // 10000


if __name__ == "__main__":  # `python3 pg_server.py` prints what discovery resolves to
    found = discover_all()
    if not found:
        print("none")
        raise SystemExit(2)
    for major in sorted(found):
        srv = found[major]
        try:
            actual = server_major(srv)
        except Exception as exc:                        # noqa: BLE001 - reported, not raised
            print(f"{major}\tUNREACHABLE\t{srv.origin}\t{exc}")
            continue
        flag = "" if actual == major else f"\tMISLABELLED(reports {actual})"
        print(f"{major}\t{srv.scalar('SHOW server_version')}\t{srv.origin}{flag}")

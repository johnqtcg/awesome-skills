"""Discovery and execution helper for the live-MongoDB test matrix.

Why this exists
---------------
Every other suite in this skill asserts against *our own* description of MongoDB. A
review found that 97 green tests had preserved, intact, a backfill script that cannot
run and a rolling-index-build procedure the server rejects outright. Both were covered
by fixtures; one fixture recorded the broken procedure as "no violations".

The tests could not have caught either, because none of them ran anything. This module
is the only place in the suite that talks to a server.

What a server settles that a document cannot
--------------------------------------------
Measured, not asserted, on live 7.0 and 8.0:

* ``ObjectId.prototype.valueOf()`` returns an **object**, so the shipped
  ``lastId.valueOf().substring(0,24)`` threw ``TypeError`` on the first iteration.
* ``createIndex`` against a replica-set secondary is rejected with
  ``NotWritablePrimary`` — step (b) of the old rolling-build procedure.
* ``collMod`` changes ``expireAfterSeconds`` in place, so "requires dropIndex +
  createIndex" was false for every supported version.
* ``validationLevel: "moderate"`` rejects a non-compliant insert AND an update that
  would break a currently-compliant document; only already-invalid documents are exempt.
* The ticket metric lives at ``wiredTiger.concurrentTransactions`` on 7.0 and at
  ``queues.execution`` on 8.0 — reading the wrong one returns ``undefined``.

Discovery order
---------------
1. ``MONGO_MIGRATION_TEST_MONGOSH_<major>`` -- a shell command that accepts
   ``--quiet --eval``, e.g. ``docker exec mongomig8 mongosh``.
2. ``MONGO_MIGRATION_TEST_URI_<major>`` -- a connection string used with a local
   ``mongosh``.
3. A running Docker container named ``mongomig<major>``.

If none resolve the matrix **skips**, and ``mongo_server_harness.sh`` exits non-zero, so
an environment without Docker cannot quietly report this coverage as achieved.
"""

from __future__ import annotations

import dataclasses
import json
import os
import shutil
import subprocess

# Majors this skill claims to support. 4.4 / 5.0 / 6.0 are EOL as of 2026-08.
SUPPORTED = (7, 8)

CALL_TIMEOUT_S = 120


@dataclasses.dataclass(frozen=True)
class Server:
    major: int
    argv: list[str]
    origin: str
    # Container names of the set's members, when this is a docker-managed 3-node set.
    # Which of them is the secondary is resolved at call time, not cached: an election
    # between discovery and the assertion would otherwise aim a "secondary" probe at the
    # primary and prove nothing.
    members: tuple[str, ...] = ()

    def secondary(self) -> "Server | None":
        """A handle connected DIRECTLY to whichever member is currently a secondary.

        directConnection=true is essential: without it the driver follows the seed list
        to the primary, and "a secondary rejects createIndex" silently tests the primary.
        Returns None when the deployment genuinely has no secondary (a single-node set),
        which the tests that need one report as a FAILURE rather than a skip.
        """
        for name in self.members:
            probe = subprocess.run(
                ["docker", "exec", "-i", name, "mongosh",
                 "mongodb://localhost:27017/test?directConnection=true",
                 "--quiet", "--eval", "print(db.hello().secondary === true)"],
                capture_output=True, text=True, timeout=CALL_TIMEOUT_S)
            if probe.returncode == 0 and probe.stdout.strip().endswith("true"):
                return Server(self.major,
                              ["docker", "exec", "-i", name, "mongosh",
                               "mongodb://localhost:27017/test?directConnection=true"],
                              f"{name} (secondary, direct)")
        return None

    def primary_name(self) -> str | None:
        """Which member currently holds the primary. Reported, never assumed."""
        for name in self.members:
            probe = subprocess.run(
                ["docker", "exec", "-i", name, "mongosh",
                 "mongodb://localhost:27017/test?directConnection=true",
                 "--quiet", "--eval", "print(db.hello().isWritablePrimary === true)"],
                capture_output=True, text=True, timeout=CALL_TIMEOUT_S)
            if probe.returncode == 0 and probe.stdout.strip().endswith("true"):
                return name
        return None

    def eval(self, js: str) -> subprocess.CompletedProcess:
        """Run JavaScript in mongosh. stdout is whatever the script printed."""
        return subprocess.run(self.argv + ["--quiet", "--eval", js],
                              capture_output=True, text=True, timeout=CALL_TIMEOUT_S)

    def value(self, js_expression: str):
        """Evaluate an expression and return it as Python data.

        Goes through EJSON so BSON types survive the trip. A bare `print()` of a
        MongoDB Long renders as {"high":0,"low":7200} and comparing that to 7200 in a
        test is a trap -- the assertion looks right and can never pass.
        """
        js = f"print(EJSON.stringify(({js_expression}), null, 0))"
        r = self.eval(js)
        if r.returncode != 0:
            raise RuntimeError(f"mongo{self.major}: {js_expression!r} failed: "
                               f"{r.stderr.strip() or r.stdout.strip()}")
        out = r.stdout.strip().splitlines()
        if not out:
            raise RuntimeError(f"mongo{self.major}: {js_expression!r} printed nothing")
        return json.loads(out[-1])


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
    cmd = os.environ.get(f"MONGO_MIGRATION_TEST_MONGOSH_{major}")
    if cmd:
        return Server(major, cmd.split(), f"$MONGO_MIGRATION_TEST_MONGOSH_{major}")

    uri = os.environ.get(f"MONGO_MIGRATION_TEST_URI_{major}")
    if uri and shutil.which("mongosh"):
        return Server(major, ["mongosh", uri], f"$MONGO_MIGRATION_TEST_URI_{major}")

    # 3-member layout created by mongo_server_harness.sh.
    #
    # Do NOT assume n1 is the primary. A replica set elects, and it re-elects for
    # ordinary reasons -- a slow heartbeat, a container pause, load. Pinning n1 made the
    # matrix pass on one run and fail 13 tests with NotWritablePrimary on the next, for a
    # reason that had nothing to do with the skill.
    #
    # So: connect through a replica-set SEED LIST, which follows the primary wherever it
    # is, and resolve a secondary dynamically at call time.
    nodes = [f"mongomig{major}n{i}" for i in (1, 2, 3)]
    live = [n for n in nodes if _docker_container_running(n)]
    if live:
        seeds = ",".join(f"{n}:27017" for n in nodes)
        uri = f"mongodb://{seeds}/test?replicaSet=rsmig{major}"
        return Server(major, ["docker", "exec", "-i", live[0], "mongosh", uri],
                      f"docker containers mongomig{major}n1..3 (seed list)",
                      members=tuple(live))

    # Single-node fallback (an earlier layout, or a hand-rolled server).
    name = f"mongomig{major}"
    if _docker_container_running(name):
        return Server(major, ["docker", "exec", "-i", name, "mongosh"],
                      f"docker container {name} (single node -- no secondary)")
    return None


def discover_all() -> dict[int, Server]:
    return {m: s for m in SUPPORTED if (s := discover(m)) is not None}


def server_major(srv: Server) -> int:
    """Ask the server its own major version.

    Never trust the container name: a mislabelled container silently attributes one
    release's behaviour to another, which is the error class this matrix exists to catch.
    """
    return int(str(srv.value("db.version()")).split(".")[0])


if __name__ == "__main__":
    found = discover_all()
    if not found:
        print("none")
        raise SystemExit(2)
    for major in sorted(found):
        srv = found[major]
        try:
            actual = server_major(srv)
            ver = srv.value("db.version()")
        except Exception as exc:                        # noqa: BLE001 - reported, not raised
            print(f"{major}\tUNREACHABLE\t{srv.origin}\t{exc}")
            continue
        flag = "" if actual == major else f"\tMISLABELLED(reports {actual})"
        if srv.members:
            prim = srv.primary_name() or "?"
            sec = srv.secondary()
            topo = f"3-member primary={prim} secondary={'yes' if sec else 'NONE'}"
        else:
            topo = "NO-SECONDARY"
        print(f"{major}\t{ver}\t{srv.origin}\t{topo}{flag}")

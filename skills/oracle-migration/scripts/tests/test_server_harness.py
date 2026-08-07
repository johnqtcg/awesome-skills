"""Integration tests for scripts/verify_against_server.sh.

The harness is the thing that would turn this skill's documentation-derived claims into
measured ones, so its own verdict logic has to be exercised — not just read. These tests
put a stub `sqlplus` on PATH that replays canned server responses, then assert the
harness reaches the right verdict.

Two failure modes are specifically pinned, because the first revision had both:
  * probe order was load-bearing (one shared scratch table, so an early RENAME COLUMN
    broke later probes);
  * a "must fail" probe accepted *any* error as confirmation, so a probe that failed for
    an unrelated reason scored as a verified rejection.
"""

import os
import pathlib
import re
import stat
import subprocess
import sys
import textwrap

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = SKILL_DIR / "scripts" / "verify_against_server.sh"


def parse_probes() -> list:
    """The probe table, read from the script itself."""
    src = SCRIPT.read_text(encoding="utf-8")
    block = re.search(r"PROBE_EOF'\n(.*?)\nPROBE_EOF", src, re.S)
    assert block, "probe heredoc not found"
    rows = []
    for line in block.group(1).splitlines():
        if line.strip():
            rows.append(line.split("|"))
    return rows


PROBES = parse_probes()


class TestProbeTable:
    def test_probes_exist(self):
        assert len(PROBES) >= 10

    def test_every_row_has_five_fields(self):
        for row in PROBES:
            assert len(row) == 5, f"{row[0]}: expected 5 fields, got {len(row)}"

    def test_ids_unique(self):
        ids = [r[0] for r in PROBES]
        assert len(ids) == len(set(ids)), f"duplicate probe ids in {ids}"

    def test_every_must_fail_probe_names_its_ora_code(self):
        """'It errored' is not evidence it errored for the documented reason."""
        for pid, claim, ok, bad, code in PROBES:
            if bad != "-":
                assert re.fullmatch(r"(ORA|PLS|SP2)-\d+", code), (
                    f"{pid} expects a rejection but declares no specific error code "
                    f"(got {code!r}) — any unrelated failure would score as a pass"
                )

    def test_every_probe_asserts_something(self):
        for pid, claim, ok, bad, code in PROBES:
            assert ok != "-" or bad != "-", f"{pid} asserts nothing"

    def test_success_probes_declare_no_error_code(self):
        for pid, claim, ok, bad, code in PROBES:
            if bad == "-":
                assert code == "-", f"{pid} expects success but also names {code}"

    def test_table_placeholder_is_substituted_not_evaluated(self):
        """`eval` on SQL containing quotes and parens is a shell-injection footgun."""
        src = SCRIPT.read_text(encoding="utf-8")
        assert "@T@" in src, "probes should use the @T@ placeholder"
        assert "eval echo" not in src, "probe SQL must not go through eval"

    def test_scratch_table_is_rebuilt_per_probe(self):
        """Probe order must not be load-bearing."""
        src = SCRIPT.read_text(encoding="utf-8")
        loop = src[src.index("while IFS='|' read -r id claim ok bad code"):]
        assert "rebuild_scratch" in loop, (
            "the probe loop must rebuild the scratch table each iteration, or one "
            "probe's DDL changes the schema the next one depends on"
        )


# ======================================================================================
# End-to-end with a stubbed sqlplus
# ======================================================================================


def make_stub(tmp_path: pathlib.Path, body: str) -> dict:
    """Put a fake `sqlplus` on PATH and return an env that finds it."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    stub = bindir / "sqlplus"
    stub.write_text("#!/usr/bin/env bash\n" + textwrap.dedent(body), encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    env = dict(os.environ)
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["ORACLE_TEST_DSN"] = "u/p@//h:1521/s"
    env["ORACLE_ALLOW_DDL"] = "1"
    return env


def run_harness(env) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT)], capture_output=True, text=True, env=env, timeout=120
    )


# The stub reads the SQL sqlplus would have received on stdin and answers from a table.
# The fixture-verification COUNT is answered here so individual stubs need not repeat it;
# STUB_ROWCOUNT lets a test simulate a silently empty scratch table.
_STUB_PREAMBLE = r"""
sql="$(cat)"
emit_ok()  { echo "done"; exit 0; }
emit_err() { echo "$1: simulated"; exit 1; }
case "$sql" in
  *"SELECT COUNT(*)"*) echo "${STUB_ROWCOUNT:-1}"; exit 0 ;;
esac
"""


@pytest.mark.skipif(sys.platform == "win32", reason="bash harness")
class TestHarnessVerdicts:
    def test_all_probes_agreeing_exits_zero(self, tmp_path):
        """Every statement behaves exactly as documented."""
        env = make_stub(tmp_path, _STUB_PREAMBLE + r"""
        case "$sql" in
          *"NUMBER(8,1)"*)        emit_err "ORA-01440" ;;
          *"c_num VARCHAR2(40)"*) emit_err "ORA-01439" ;;
          *"NOT NULL"*)           emit_err "ORA-02296" ;;
          *"VARCHAR2(2)"*)        emit_err "ORA-01441" ;;
          *data_object_id*)       emit_err "ORA-00904" ;;
          *"= 1000001"*)          emit_err "ORA-00068" ;;
          *"= -1"*)               emit_err "ORA-00068" ;;
          *)                      emit_ok ;;
        esac
        """)
        r = run_harness(env)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "agree with the documented behaviour" in r.stdout

    def test_rejection_probe_failing_for_the_wrong_reason_is_caught(self, tmp_path):
        """The exact bug the first revision shipped: ORA-00904 counted as a confirmed ORA-01439."""
        env = make_stub(tmp_path, _STUB_PREAMBLE + r"""
        case "$sql" in
          *"NUMBER(8,1)"*)        emit_err "ORA-01440" ;;
          # The datatype-change probe errors, but with the WRONG code — as it would if a
          # previous probe had renamed the column out from under it.
          *"c_num VARCHAR2(40)"*) emit_err "ORA-00904" ;;
          *"NOT NULL"*)           emit_err "ORA-02296" ;;
          *"VARCHAR2(2)"*)        emit_err "ORA-01441" ;;
          *data_object_id*)       emit_err "ORA-00904" ;;
          *"= 1000001"*)          emit_err "ORA-00068" ;;
          *"= -1"*)               emit_err "ORA-00068" ;;
          *)                      emit_ok ;;
        esac
        """)
        r = run_harness(env)
        assert r.returncode == 1, "a rejection for the wrong reason must not pass"
        assert "want ORA-01439" in r.stdout, r.stdout

    def test_rejection_probe_that_is_accepted_is_caught(self, tmp_path):
        """If the server ACCEPTS what the docs say it rejects, the docs are wrong."""
        env = make_stub(tmp_path, _STUB_PREAMBLE + r"""
        case "$sql" in
          *"c_num VARCHAR2(40)"*) emit_err "ORA-01439" ;;
          *"NOT NULL"*)           emit_err "ORA-02296" ;;
          *"VARCHAR2(2)"*)        emit_err "ORA-01441" ;;
          *data_object_id*)       emit_err "ORA-00904" ;;
          *"= 1000001"*)          emit_err "ORA-00068" ;;
          *"= -1"*)               emit_err "ORA-00068" ;;
          # ORA-01440 case now succeeds — contradicts the documented rejection.
          *)                      emit_ok ;;
        esac
        """)
        r = run_harness(env)
        assert r.returncode == 1
        assert "was-accepted" in r.stdout, r.stdout

    def test_success_probe_that_errors_is_caught(self, tmp_path):
        env = make_stub(tmp_path, _STUB_PREAMBLE + r"""
        case "$sql" in
          *"RENAME COLUMN"*)      emit_err "ORA-00904" ;;
          *"NUMBER(8,1)"*)        emit_err "ORA-01440" ;;
          *"c_num VARCHAR2(40)"*) emit_err "ORA-01439" ;;
          *"NOT NULL"*)           emit_err "ORA-02296" ;;
          *"VARCHAR2(2)"*)        emit_err "ORA-01441" ;;
          *data_object_id*)       emit_err "ORA-00904" ;;
          *"= 1000001"*)          emit_err "ORA-00068" ;;
          *"= -1"*)               emit_err "ORA-00068" ;;
          *)                      emit_ok ;;
        esac
        """)
        r = run_harness(env)
        assert r.returncode == 1
        assert "should-succeed" in r.stdout, r.stdout

    def test_scratch_table_is_recreated_between_probes(self, tmp_path):
        """Count CREATE TABLE calls: one per probe, not one for the whole run."""
        counter = tmp_path / "creates.txt"
        env = make_stub(tmp_path, _STUB_PREAMBLE + f"""
        case "$sql" in
          *"CREATE TABLE"*) echo x >> {counter} ;;
        esac
        """ + r"""
        case "$sql" in
          *"NUMBER(8,1)"*)        emit_err "ORA-01440" ;;
          *"c_num VARCHAR2(40)"*) emit_err "ORA-01439" ;;
          *"NOT NULL"*)           emit_err "ORA-02296" ;;
          *"VARCHAR2(2)"*)        emit_err "ORA-01441" ;;
          *data_object_id*)       emit_err "ORA-00904" ;;
          *"= 1000001"*)          emit_err "ORA-00068" ;;
          *"= -1"*)               emit_err "ORA-00068" ;;
          *)                      emit_ok ;;
        esac
        """)
        r = run_harness(env)
        assert r.returncode == 0, r.stdout + r.stderr
        creates = counter.read_text().count("x") if counter.exists() else 0
        assert creates >= len(PROBES), (
            f"scratch table created {creates} times for {len(PROBES)} probes — "
            "state leaks between probes and probe order becomes load-bearing"
        )

    def test_setup_failure_exits_2_not_1(self, tmp_path):
        """A fixture that cannot be built is a setup error, never a documentation finding.

        sqlplus here runs with WHENEVER SQLERROR CONTINUE NONE + EXIT SUCCESS, so it
        exits 0 even after an ORA- error. An earlier revision judged rebuild_scratch by
        the exit code alone: a privilege/quota/tablespace failure went unnoticed and the
        run then reported a dozen probe failures as "the server contradicts the docs"
        (exit 1). That sends someone to rewrite correct documentation.
        """
        env = make_stub(tmp_path, _STUB_PREAMBLE + r"""
        case "$sql" in
          *"CREATE TABLE"*) echo "ORA-01950: no privileges on tablespace 'USERS'"; exit 0 ;;
          *)                emit_ok ;;
        esac
        """)
        r = run_harness(env)
        assert r.returncode == 2, (
            f"setup failure must exit 2, got {r.returncode}\n{r.stdout}\n{r.stderr}"
        )
        assert "ORA-01950" in r.stderr, r.stderr
        assert "not a finding" in r.stderr.lower()

    def test_silently_empty_fixture_is_a_setup_failure(self, tmp_path):
        """CREATE succeeding is not the same as the probe row existing.

        Without the row, every data-dependent rejection probe would be accepted by the
        server and reported as "the documentation is wrong".
        """
        env = make_stub(tmp_path, _STUB_PREAMBLE + r"""
        emit_ok
        """)
        env["STUB_ROWCOUNT"] = "0"
        r = run_harness(env)
        assert r.returncode == 2, (
            f"an empty fixture must exit 2, got {r.returncode}\n{r.stdout}\n{r.stderr}"
        )
        assert "verification returned" in r.stderr, r.stderr

    def test_probe_contradiction_still_exits_1(self, tmp_path):
        """Guard the guard: the setup path must not swallow genuine findings."""
        env = make_stub(tmp_path, _STUB_PREAMBLE + r"""
        case "$sql" in
          *"c_num VARCHAR2(40)"*) emit_err "ORA-01439" ;;
          *"NOT NULL"*)           emit_err "ORA-02296" ;;
          *"VARCHAR2(2)"*)        emit_err "ORA-01441" ;;
          *data_object_id*)       emit_err "ORA-00904" ;;
          *"= 1000001"*)          emit_err "ORA-00068" ;;
          *"= -1"*)               emit_err "ORA-00068" ;;
          *)                      emit_ok ;;
        esac
        """)
        r = run_harness(env)
        assert r.returncode == 1, "a real contradiction must still be exit 1"
        assert "was-accepted" in r.stdout

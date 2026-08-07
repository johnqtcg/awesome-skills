"""Live-PostgreSQL verification of the claims this skill makes.

Every other suite asserts against our own description of PostgreSQL. This one asserts
against PostgreSQL. It skips when no server is reachable -- see pg_server.py for the
discovery order and why a skip is not treated as a pass.

Bring servers up with::

    bash scripts/pg_server_harness.sh          # start 14-18 and run this matrix
    bash scripts/pg_server_harness.sh --keep   # leave the containers running

Each test states the documented claim it is checking, so a failure names the sentence
in the skill that has gone stale rather than just the SQL that broke.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

import pytest

TESTS_DIR = pathlib.Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent
SKILL_DIR = SCRIPTS_DIR.parent


def _load(name: str, path: pathlib.Path):
    """Load by path: this repo runs pytest with --import-mode=importlib, which breaks
    bare sibling imports. Register in sys.modules before exec_module so dataclasses
    can resolve the module during class creation."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


PGS = _load("pg_migration_pg_server", TESTS_DIR / "pg_server.py")
LINT = _load("pg_lint_migration", SCRIPTS_DIR / "lint_migration.py")

SERVERS = PGS.discover_all()

pytestmark = pytest.mark.skipif(
    not SERVERS,
    reason="no live PostgreSQL reachable; run scripts/pg_server_harness.sh",
)

MAJORS = sorted(SERVERS)


@pytest.fixture(params=MAJORS, ids=[f"pg{m}" for m in MAJORS])
def srv(request):
    return SERVERS[request.param]


DOC_ROLES = ("app_user", "migrator")

# Extensions are DATABASE-scoped, so dropping a schema does not undo a CREATE EXTENSION
# a previous block ran. That leak silently disarmed the version check: once any run had
# installed pg_stat_statements, a later `CREATE EXTENSION IF NOT EXISTS ... VERSION
# '1.10'` short-circuited to a NOTICE instead of the 22023 error it must raise on PG 14.
# A probe whose outcome depends on what ran before it is not a probe.
_RESET_EXTENSIONS = """
DO $x$
DECLARE e text;
BEGIN
  FOR e IN SELECT extname FROM pg_extension WHERE extname <> 'plpgsql' LOOP
    EXECUTE format('DROP EXTENSION IF EXISTS %I CASCADE', e);
  END LOOP;
END $x$;
"""

EXTENSION_PIN_SQL = """
DO $pin$
DECLARE
  want text := '1.9';
  have text;
BEGIN
  SELECT extversion INTO have FROM pg_extension
   WHERE extname = 'pg_stat_statements';

  IF have IS NULL THEN
    IF NOT EXISTS (SELECT 1 FROM pg_available_extension_versions
                   WHERE name = 'pg_stat_statements' AND version = want) THEN
      RAISE EXCEPTION 'pg_stat_statements % is not available', want;
    END IF;
    EXECUTE format('CREATE EXTENSION pg_stat_statements VERSION %L', want);
  ELSIF have <> want THEN
    RAISE EXCEPTION
      'pg_stat_statements is installed at %, expected %; review ALTER EXTENSION UPDATE separately',
      have, want;
  END IF;
END $pin$;
"""


def _fresh_schema(srv, name: str) -> str:
    """Give each test its own schema so tests never collide on table names.

    Also creates the roles the documents name. Without them an RLS or ALTER ROLE
    snippet fails with "role does not exist" -- a fixture gap, not a defect in the
    snippet, and tolerating that SQLSTATE globally would have hidden the extension-
    version bug that shares it (22023).
    """
    roles = "".join(
        f"DO $r$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{r}') "
        f"THEN CREATE ROLE {r}; END IF; END $r$;\n" for r in DOC_ROLES)
    srv.run(roles + _RESET_EXTENSIONS
            + f"DROP SCHEMA IF EXISTS {name} CASCADE; CREATE SCHEMA {name};")
    return name


# ---------------------------------------------------------------------------
# Harness integrity -- these must fail loudly, never skip quietly.
# ---------------------------------------------------------------------------

class TestHarnessIntegrity:
    def test_container_version_matches_its_label(self, srv):
        """A mislabelled container would attribute one version's behaviour to
        another -- the exact error class this matrix exists to catch."""
        actual = PGS.server_major(srv)
        assert actual == srv.major, (
            f"{srv.origin} is labelled PG{srv.major} but reports PG{actual}"
        )

    def test_supported_range_matches_the_linter(self):
        assert PGS.SUPPORTED[0] == LINT.SUPPORTED_PG_MIN
        assert PGS.SUPPORTED[-1] == LINT.SUPPORTED_PG_MAX

    def test_server_actually_executes_sql(self, srv):
        """Guards against a 'connection' that returns empty output for everything,
        which would make every other assertion below vacuously true."""
        assert srv.scalar("SELECT 40 + 2") == "42"


# ---------------------------------------------------------------------------
# §5.1 lock classes. The original defect: FK and CHECK described with one rule.
# ---------------------------------------------------------------------------

LOCK_SETUP = """
CREATE TABLE {s}.parent(id bigint PRIMARY KEY);
CREATE TABLE {s}.child(id bigint PRIMARY KEY, pid bigint, amt int);
INSERT INTO {s}.parent SELECT g FROM generate_series(1,50) g;
INSERT INTO {s}.child SELECT g, g, g FROM generate_series(1,50) g;
"""

LOCK_PROBE = """
BEGIN;
{ddl}
SELECT c.relname || '=' || l.mode
  FROM pg_locks l
  JOIN pg_class c ON c.oid = l.relation
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE l.pid = pg_backend_pid() AND n.nspname = '{s}'
   AND l.mode <> 'AccessShareLock'
 ORDER BY 1;
ROLLBACK;
"""


def _locks(srv, schema: str, ddl: str) -> set[str]:
    out = srv.run(LOCK_PROBE.format(ddl=ddl, s=schema) + "\n", on_error_stop=True)
    assert out.returncode == 0, f"lock probe failed: {out.stderr.strip()}"
    return {ln.strip() for ln in out.stdout.splitlines()
            if "=" in ln and "Lock" in ln}


class TestLockClasses:
    """SKILL.md §5.1 item 1 and AE-18: FK is ShareRowExclusive on BOTH tables;
    CHECK is AccessExclusive. NOT VALID changes the duration, never the class."""

    def test_fk_not_valid_is_share_row_exclusive_on_both_tables(self, srv):
        s = _fresh_schema(srv, "lk_fknv")
        srv.run(LOCK_SETUP.format(s=s), on_error_stop=True)
        got = _locks(srv, s, f"ALTER TABLE {s}.child ADD CONSTRAINT fk1 "
                             f"FOREIGN KEY (pid) REFERENCES {s}.parent(id) NOT VALID;")
        assert "child=ShareRowExclusiveLock" in got, got
        assert "parent=ShareRowExclusiveLock" in got, (
            "the referenced table's write-blocking is the half most reviews miss", got)
        assert not any("child=AccessExclusiveLock" in g for g in got), (
            "FK must NOT be AccessExclusive -- this was the documented error", got)

    def test_fk_validating_is_also_share_row_exclusive_not_access_exclusive(self, srv):
        s = _fresh_schema(srv, "lk_fkval")
        srv.run(LOCK_SETUP.format(s=s), on_error_stop=True)
        got = _locks(srv, s, f"ALTER TABLE {s}.child ADD CONSTRAINT fk2 "
                             f"FOREIGN KEY (pid) REFERENCES {s}.parent(id);")
        assert "child=ShareRowExclusiveLock" in got, got
        assert "child=AccessExclusiveLock" not in got, (
            "AE-2 previously claimed AccessExclusive for a validating FK", got)

    def test_check_not_valid_is_access_exclusive(self, srv):
        s = _fresh_schema(srv, "lk_cknv")
        srv.run(LOCK_SETUP.format(s=s), on_error_stop=True)
        got = _locks(srv, s, f"ALTER TABLE {s}.child ADD CONSTRAINT ck1 "
                             "CHECK (amt >= 0) NOT VALID;")
        assert "child=AccessExclusiveLock" in got, (
            "NOT VALID does not move a CHECK into a cheaper lock class", got)

    def test_validate_constraint_is_share_update_exclusive(self, srv):
        s = _fresh_schema(srv, "lk_val")
        srv.run(LOCK_SETUP.format(s=s), on_error_stop=True)
        srv.run(f"ALTER TABLE {s}.child ADD CONSTRAINT fk3 FOREIGN KEY (pid) "
                f"REFERENCES {s}.parent(id) NOT VALID;", on_error_stop=True)
        got = _locks(srv, s, f"ALTER TABLE {s}.child VALIDATE CONSTRAINT fk3;")
        assert "child=ShareUpdateExclusiveLock" in got, (
            "§5.1 item 4 calls VALIDATE CONSTRAINT non-blocking", got)
        assert "parent=RowShareLock" in got, got

    def test_plain_create_index_takes_share_lock(self, srv):
        s = _fresh_schema(srv, "lk_idx")
        srv.run(LOCK_SETUP.format(s=s), on_error_stop=True)
        got = _locks(srv, s, f"CREATE INDEX ix_amt ON {s}.child (amt);")
        assert "child=ShareLock" in got, ("AE-1 claims ShareLock for a plain build", got)


# ---------------------------------------------------------------------------
# §5.2 item 6 -- which type changes rewrite. Measured, not asserted from prose.
# ---------------------------------------------------------------------------

TYPE_PAIRS = [
    ("int",           "bigint",        True),
    ("varchar(10)",   "varchar(20)",   False),
    ("varchar(20)",   "varchar(5)",    True),
    ("varchar(10)",   "text",          False),
    ("text",          "varchar(10)",   True),
    ("text",          "varchar",       False),
    ("numeric(10,2)", "numeric(12,4)", True),
    ("int",           "text",          True),
]


class TestTypeChangeRewrites:
    """A rewrite is observable: ALTER assigns the table a new relfilenode."""

    @pytest.mark.parametrize("src,dst,expected_rewrite", TYPE_PAIRS,
                             ids=[f"{a}->{b}" for a, b, _ in TYPE_PAIRS])
    def test_rewrite_matches_documentation(self, srv, src, dst, expected_rewrite):
        s = _fresh_schema(srv, "ty")
        srv.run(f"CREATE TABLE {s}.t(c {src});\n"
                f"INSERT INTO {s}.t SELECT NULL FROM generate_series(1,5);",
                on_error_stop=True)
        before = srv.scalar(f"SELECT pg_relation_filenode('{s}.t')")
        r = srv.run(f"ALTER TABLE {s}.t ALTER COLUMN c TYPE {dst};", on_error_stop=True)
        assert r.returncode == 0, f"{src} -> {dst} failed: {r.stderr.strip()}"
        after = srv.scalar(f"SELECT pg_relation_filenode('{s}.t')")
        rewrote = before != after
        assert rewrote == expected_rewrite, (
            f"PG{srv.major}: {src} -> {dst} "
            f"{'REWROTE' if rewrote else 'did not rewrite'}, docs say the opposite"
        )

    @pytest.mark.parametrize("src,dst,expected_rewrite", TYPE_PAIRS,
                             ids=[f"{a}->{b}" for a, b, _ in TYPE_PAIRS])
    def test_linter_verdict_matches_the_server(self, srv, src, dst, expected_rewrite):
        """The checker's static verdict must agree with what the server does. This is
        the link that stops the classifier drifting away from reality."""
        sql = (f"CREATE TABLE t (c {src});\nSET lock_timeout = '3s';\n"
               f"ALTER TABLE t ALTER COLUMN c TYPE {dst};\n")
        codes = {f.code for f in LINT.Linter().lint(sql)}
        if expected_rewrite:
            assert "PG010" in codes, f"server rewrites {src}->{dst}; linter stayed quiet"
        else:
            assert "PG010" not in codes, f"server does not rewrite {src}->{dst}"

    def test_binary_coercible_target_set_matches_the_catalog(self, srv):
        """lint_migration._BINARY_COERCIBLE_TARGETS is generated from this query. If
        a release adds a pair, the classifier's 'unknown' set is stale."""
        rows = srv.rows(
            "SELECT DISTINCT upper(t.typname) FROM pg_cast c "
            "JOIN pg_type s ON s.oid = c.castsource "
            "JOIN pg_type t ON t.oid = c.casttarget "
            "WHERE c.castmethod = 'b'")
        catalog = {r[0] for r in rows}
        missing = catalog - set(LINT._BINARY_COERCIBLE_TARGETS)
        assert not missing, (
            f"PG{srv.major} has binary-coercible casts into {sorted(missing)}, which "
            "the classifier would wrongly report as provable rewrites"
        )


# ---------------------------------------------------------------------------
# §5.1 item 2 / §8 -- the guard forms.
# ---------------------------------------------------------------------------

class TestGuardSemantics:
    def test_set_local_outside_a_transaction_warns_and_does_nothing(self, srv):
        """§5.1 item 2 and the PG001 rule rest on this being a no-op, not an error."""
        r = srv.run("SET LOCAL lock_timeout = '3s';\nSHOW lock_timeout;\n")
        assert "WARNING" in r.stderr.upper() or "WARNING" in r.stdout.upper(), (
            "expected a WARNING for SET LOCAL outside a transaction block", r.stderr)
        assert "3s" not in r.stdout, (
            "the guard must NOT be in effect -- that is why PG001 is critical")

    def test_set_local_inside_a_transaction_takes_effect(self, srv):
        out = srv.run("BEGIN;\nSET LOCAL lock_timeout = '3s';\nSHOW lock_timeout;\n"
                      "COMMIT;\n", on_error_stop=True)
        assert "3s" in out.stdout, out.stdout

    def test_lock_timeout_zero_means_wait_forever(self, srv):
        """The PG019 rule: zero is the documented 'disabled' value, so a checker that
        only asks whether the setting is present scores it as compliant."""
        assert srv.scalar("SET lock_timeout = 0; SHOW lock_timeout") == "0"

    def test_lock_timeout_default_is_zero(self, srv):
        """_timeout_ms() maps DEFAULT to 0 on the strength of this."""
        assert srv.scalar("SHOW lock_timeout") == "0"

    def test_concurrently_cannot_run_in_a_transaction(self, srv):
        s = _fresh_schema(srv, "gd_conc")
        srv.run(f"CREATE TABLE {s}.t(c int);", on_error_stop=True)
        r = srv.run(f"BEGIN;\nCREATE INDEX CONCURRENTLY ix ON {s}.t (c);\nCOMMIT;\n")
        assert "cannot run inside a transaction block" in r.stderr, (
            "PG002 treats this as a hard error", r.stderr)


# ---------------------------------------------------------------------------
# §5.1 item 4 -- the version-gated partitioned FK rule.
# ---------------------------------------------------------------------------

class TestPartitionedForeignKey:
    def test_not_valid_fk_gate_matches_the_documented_version(self, srv):
        """Documented as an absolute prohibition until a live run showed PG 18
        accepts it. The linter's PARTITIONED_FK_NOT_VALID_MIN_PG encodes the boundary;
        this test is what keeps that constant honest."""
        s = _fresh_schema(srv, "pfk")
        srv.run(f"CREATE TABLE {s}.pref(id bigint PRIMARY KEY);\n"
                f"CREATE TABLE {s}.pt(id bigint, pid bigint, ts date) "
                "PARTITION BY RANGE (ts);", on_error_stop=True)
        r = srv.run(f"ALTER TABLE {s}.pt ADD CONSTRAINT fkp FOREIGN KEY (pid) "
                    f"REFERENCES {s}.pref(id) NOT VALID;")
        accepted = "ERROR" not in r.stderr
        should_accept = srv.major >= LINT.PARTITIONED_FK_NOT_VALID_MIN_PG
        assert accepted == should_accept, (
            f"PG{srv.major} {'accepted' if accepted else 'rejected'} a NOT VALID FK on "
            f"a partitioned table; PARTITIONED_FK_NOT_VALID_MIN_PG="
            f"{LINT.PARTITIONED_FK_NOT_VALID_MIN_PG} says the opposite. {r.stderr.strip()}"
        )


# ---------------------------------------------------------------------------
# large-table-migration.md §3 -- the backfill templates must RUN, and must not
# skip rows. The skipping bug is the one a green unit suite cannot see.
# ---------------------------------------------------------------------------

BACKFILL_A = """
DO $$
DECLARE
  batch_size int    := 10;
  last_id    bigint := NULL;
  rows_done  int;
BEGIN
  LOOP
    WITH batch AS (
        SELECT id FROM {s}.target_table
        WHERE new_col IS NULL AND (last_id IS NULL OR id > last_id)
        ORDER BY id LIMIT batch_size
    ),
    upd AS (
        UPDATE {s}.target_table t SET new_col = t.old_col * 2
        FROM batch WHERE t.id = batch.id
        RETURNING t.id
    )
    SELECT count(*), max(id) INTO rows_done, last_id FROM upd;
    EXIT WHEN rows_done = 0;
  END LOOP;
END $$;
"""

# The exact form the documentation used to recommend. Kept as a regression probe:
# it must leave rows behind, which is what makes the fix load-bearing.
BACKFILL_GLOBAL_MAX = """
DO $$
DECLARE
  batch_size int    := 10;
  last_id    bigint := NULL;
  rows_done  int;
BEGIN
  LOOP
    WITH batch AS (
        SELECT id FROM {s}.target_table
        WHERE new_col IS NULL AND (last_id IS NULL OR id > last_id)
        ORDER BY id LIMIT batch_size
    )
    UPDATE {s}.target_table t SET new_col = t.old_col * 2
    FROM batch WHERE t.id = batch.id;
    GET DIAGNOSTICS rows_done = ROW_COUNT;
    EXIT WHEN rows_done = 0;
    SELECT max(id) INTO last_id FROM {s}.target_table WHERE new_col IS NOT NULL;
  END LOOP;
END $$;
"""

BACKFILL_UUID = """
DO $$
DECLARE
  batch_size int  := 10;
  last_id    uuid := NULL;
  rows_done  int;
BEGIN
  LOOP
    WITH batch AS (
        SELECT id FROM {s}.uuid_table
        WHERE new_col IS NULL AND (last_id IS NULL OR id > last_id)
        ORDER BY id LIMIT batch_size
    ),
    upd AS (
        UPDATE {s}.uuid_table t SET new_col = 1
        FROM batch WHERE t.id = batch.id
        RETURNING t.id
    )
    SELECT count(*), (array_agg(id ORDER BY id DESC))[1] INTO rows_done, last_id FROM upd;
    EXIT WHEN rows_done = 0;
  END LOOP;
END $$;
"""

BACKFILL_COMPOSITE = """
DO $$
DECLARE
  batch_size  int    := 10;
  last_tenant bigint := NULL;
  last_id     bigint := NULL;
  rows_done   int;
BEGIN
  LOOP
    WITH batch AS (
        SELECT tenant_id, id FROM {s}.comp_table
        WHERE new_col IS NULL
          AND (last_tenant IS NULL OR (tenant_id, id) > (last_tenant, last_id))
        ORDER BY tenant_id, id LIMIT batch_size
    ),
    upd AS (
        UPDATE {s}.comp_table t SET new_col = 1
        FROM batch b WHERE t.tenant_id = b.tenant_id AND t.id = b.id
        RETURNING t.tenant_id, t.id
    )
    SELECT count(*),
           (array_agg(tenant_id ORDER BY tenant_id DESC, id DESC))[1],
           (array_agg(id        ORDER BY tenant_id DESC, id DESC))[1]
      INTO rows_done, last_tenant, last_id
    FROM upd;
    EXIT WHEN rows_done = 0;
  END LOOP;
END $$;
"""


class TestBackfillTemplates:
    """Each template is executed against a table seeded with the shapes the doc
    claims it handles: sparse ids, negative ids, and a pre-populated high row."""

    def _seed_single(self, srv, s):
        srv.run(f"""
CREATE TABLE {s}.target_table(id bigint PRIMARY KEY, old_col int, new_col int);
INSERT INTO {s}.target_table(id, old_col)
SELECT g * 7 - 40, g FROM generate_series(1, 60) g;
-- A row at the top of the key range that ALREADY has new_col set: an earlier
-- partial run, an app dual-writing, or a DEFAULT. This is what makes a global
-- max(id) resume point skip everything in between.
INSERT INTO {s}.target_table(id, old_col, new_col) VALUES (999999, 5, 10);
""", on_error_stop=True)

    def test_template_a_runs_and_leaves_no_row_behind(self, srv):
        s = _fresh_schema(srv, "bf_a")
        self._seed_single(srv, s)
        r = srv.run(BACKFILL_A.format(s=s), on_error_stop=True)
        assert r.returncode == 0, f"Template A failed to execute: {r.stderr.strip()}"
        left = srv.scalar(f"SELECT count(*) FROM {s}.target_table WHERE new_col IS NULL")
        assert left == "0", f"Template A skipped {left} rows"

    def test_template_a_computed_the_right_values(self, srv):
        """Terminating with no NULLs left is not enough -- assert the values, or a
        template that writes a constant would pass."""
        s = _fresh_schema(srv, "bf_av")
        self._seed_single(srv, s)
        srv.run(BACKFILL_A.format(s=s), on_error_stop=True)
        wrong = srv.scalar(f"SELECT count(*) FROM {s}.target_table "
                           "WHERE id <> 999999 AND new_col <> old_col * 2")
        assert wrong == "0", f"{wrong} rows got the wrong value"

    def test_the_superseded_global_max_form_really_does_skip_rows(self, srv):
        """The reason the fix matters. If this ever stops skipping, the warning in
        large-table-migration.md §3 has become false and must be rewritten."""
        s = _fresh_schema(srv, "bf_bad")
        self._seed_single(srv, s)
        r = srv.run(BACKFILL_GLOBAL_MAX.format(s=s), on_error_stop=True)
        assert r.returncode == 0, r.stderr
        left = int(srv.scalar(f"SELECT count(*) FROM {s}.target_table "
                              "WHERE new_col IS NULL"))
        assert left > 0, (
            "the global-max resume point was expected to skip rows; it did not, so "
            "the documented failure mode needs re-verifying"
        )

    def test_template_b_uuid_runs(self, srv):
        """max(uuid) does not exist, so Template A's form would fail here. This is
        the test that would have caught the original wrong claim."""
        s = _fresh_schema(srv, "bf_b")
        srv.run(f"""
CREATE TABLE {s}.uuid_table(id uuid PRIMARY KEY, new_col int);
INSERT INTO {s}.uuid_table(id) SELECT gen_random_uuid() FROM generate_series(1, 55);
""", on_error_stop=True)
        r = srv.run(BACKFILL_UUID.format(s=s), on_error_stop=True)
        assert r.returncode == 0, f"Template B failed: {r.stderr.strip()}"
        assert srv.scalar(f"SELECT count(*) FROM {s}.uuid_table "
                          "WHERE new_col IS NULL") == "0"

    def test_max_uuid_really_is_absent(self, srv):
        """Pins the fact Template B exists for."""
        r = srv.run("SELECT max(id) FROM (VALUES (gen_random_uuid())) v(id);")
        assert "does not exist" in r.stderr, (
            "max(uuid) now exists; Template B's rationale needs updating", r.stderr)

    def test_template_c_composite_runs_and_covers_every_row(self, srv):
        s = _fresh_schema(srv, "bf_c")
        srv.run(f"""
CREATE TABLE {s}.comp_table(tenant_id bigint, id bigint, new_col int,
                            PRIMARY KEY (tenant_id, id));
INSERT INTO {s}.comp_table(tenant_id, id)
SELECT t, i FROM generate_series(1, 7) t, generate_series(1, 9) i;
""", on_error_stop=True)
        r = srv.run(BACKFILL_COMPOSITE.format(s=s), on_error_stop=True)
        assert r.returncode == 0, f"Template C failed: {r.stderr.strip()}"
        assert srv.scalar(f"SELECT count(*) FROM {s}.comp_table "
                          "WHERE new_col IS NULL") == "0"

    def test_row_value_comparison_is_row_wise_not_columnwise(self, srv):
        """Template C's correctness depends on (a,b) > (x,y) meaning
        'a > x OR (a = x AND b > y)', which is what the doc states."""
        assert srv.scalar("SELECT (1, 9) > (1, 5)") == "t"
        assert srv.scalar("SELECT (2, 1) > (1, 9)") == "t"
        assert srv.scalar("SELECT (1, 1) > (1, 9)") == "f"


# ---------------------------------------------------------------------------
# Syntax validation of every SQL block the skill ships, on every major.
# ---------------------------------------------------------------------------

DOCS = [SKILL_DIR / "SKILL.md"] + sorted((SKILL_DIR / "references").glob("*.md"))
FENCE_RE = re.compile(r"```sql\n(.*?)```", re.S)

# Statements that are deliberately invalid, because the document is showing what NOT
# to write. Each is keyed to the marker comment that introduces it.
_WRONG_MARKER = re.compile(r"^\s*--\s*(WRONG|ALSO WRONG)\b", re.I)

# A block whose first line is `-- excerpt:` shows only the lines that differ from a
# full example elsewhere, so it is not runnable by construction. The marker is an
# escape hatch, and an unbounded escape hatch would let any real syntax error be
# silenced by adding one comment -- hence MAX_EXCERPTS below.
_EXCERPT_MARKER = re.compile(r"^\s*--\s*excerpt\b", re.I)
MAX_EXCERPTS = 3

# PostgreSQL SQLSTATEs.
#
# Rejecting ONLY 42601 (syntax_error) was too narrow, and a review found the gap: a
# hard-coded `CREATE EXTENSION ... VERSION '1.10'` fails on PG 14 with 22023
# (invalid_parameter_value), which the syntax-only check waved through. So the polarity
# is inverted -- TOLERATED lists the states that mean "this snippet refers to objects
# this harness did not create", and anything else is a defect in the snippet.
TOLERATED_SQLSTATES = frozenset({
    "42P01",  # undefined_table      -- snippet references a table we did not create
    "42703",  # undefined_column     -- ditto for a column
    "42883",  # undefined_function   -- e.g. compute_value() in a backfill template
    "42704",  # undefined_object     -- a constraint/index/type the snippet assumes
    "42P07",  # duplicate_table      -- re-running a CREATE inside one probe schema
    "3F000",  # invalid_schema_name
    "42501",  # insufficient_privilege -- e.g. CREATE EXTENSION without the package
    "58P01",  # undefined_file       -- extension not installed in this image
    "42P02",  # undefined_parameter  -- $1 in a snippet meant for a prepared statement
    "25P02",  # in_failed_sql_transaction -- a CONSEQUENCE of an earlier error in the
              #                             same block, never an independent defect
})
SQLSTATE_RE = re.compile(r"^(?:psql:[^:]*:\d+: )?ERROR:\s+([0-9A-Z]{5}):")

# 0A000 (feature_not_supported) covers real defects too, so it is NOT tolerated as a
# class. Only this one message is: a third-party extension the base image does not ship.
# Note the shape of the exemption -- keyed to the message, not the SQLSTATE -- which is
# what keeps "CREATE EXTENSION pg_repack" from also excusing a genuine 0A000.
_MISSING_EXTENSION_RE = re.compile(r'0A000:\s+extension "[^"]+" is not available')


EXCERPTS: list[str] = []


def _statements_expected_to_parse() -> list[tuple[str, int, str]]:
    """Extract SQL statements that the docs present as correct.

    Everything after a `-- WRONG` marker up to the next `-- RIGHT` is skipped: those
    are anti-examples, and several are invalid on purpose (AE-5 ships a syntax error
    as its whole point).
    """
    out = []
    for doc in DOCS:
        for m in FENCE_RE.finditer(doc.read_text(encoding="utf-8")):
            block = m.group(1)
            first = next((ln for ln in block.splitlines() if ln.strip()), "")
            if _EXCERPT_MARKER.match(first):
                EXCERPTS.append(f"{doc.name}")
                continue
            base = doc.read_text(encoding="utf-8")[:m.start()].count("\n") + 2
            skipping = False
            kept = []
            for i, ln in enumerate(block.splitlines()):
                if _WRONG_MARKER.match(ln):
                    skipping = True
                elif re.match(r"^\s*--\s*RIGHT\b", ln, re.I):
                    skipping = False
                if not skipping:
                    kept.append((base + i, ln))
            if kept:
                out.append((doc.name, base, "\n".join(ln for _, ln in kept)))
    return out


PARSE_BLOCKS = _statements_expected_to_parse()


class TestShippedSQLParsesOnEveryVersion:
    """Every SQL block the skill presents as correct must at least parse on every
    supported major. A snippet that is a syntax error on PG 14 is a snippet nobody
    can run, and no amount of unit testing against our own regexes would show it."""

    def test_blocks_were_extracted(self):
        assert len(PARSE_BLOCKS) >= 15, (
            f"only {len(PARSE_BLOCKS)} SQL blocks extracted -- extraction is broken, "
            "so a green result here would prove nothing"
        )

    def test_excerpt_escape_hatch_stays_rare(self):
        """`-- excerpt:` removes a block from syntax checking. Capping it is what
        stops a real syntax error being silenced by adding one comment line."""
        assert len(EXCERPTS) <= MAX_EXCERPTS, (
            f"{len(EXCERPTS)} blocks are marked `-- excerpt:` ({EXCERPTS}); the cap is "
            f"{MAX_EXCERPTS}. Make the block runnable instead of exempting it."
        )

    @pytest.mark.parametrize("doc,line,sql", PARSE_BLOCKS,
                             ids=[f"{d}:{ln}" for d, ln, _ in PARSE_BLOCKS])
    def test_block_has_no_syntax_error(self, srv, doc, line, sql):
        s = _fresh_schema(srv, "syn")
        # ONE execution, with VERBOSITY verbose from the start so the SQLSTATE is on the
        # first error. Running the block once to detect "ERROR" and again to read the
        # code executed it twice, and the first pass changed state the second depended
        # on: a failing `CREATE EXTENSION ... VERSION '1.10'` was followed by a DO block
        # that installed the extension, so the re-run's IF NOT EXISTS short-circuited
        # and the defect vanished between the two passes.
        r = srv.run("\\set VERBOSITY verbose\n"
                    f"SET search_path = {s}, public;\n" + sql)
        if "ERROR" not in r.stderr:
            return
        bad = []
        for ln in r.stderr.splitlines():
            text = ln.strip()
            m = SQLSTATE_RE.match(text)
            if not m or m.group(1) in TOLERATED_SQLSTATES:
                continue
            if _MISSING_EXTENSION_RE.search(text):
                continue      # the image lacks the package; the SQL itself is fine
            bad.append(text)
        assert not bad, (
            f"{doc}:{line} fails on PG{srv.major} for a reason that is not a missing "
            f"object — the snippet itself is wrong:\n" + "\n".join(bad[:3])
        )


# ---------------------------------------------------------------------------
# AE-19 -- idempotency guards that decide on a name. Both holes reproduced live.
# ---------------------------------------------------------------------------

class TestIdempotencyGuardDrift:
    def test_name_only_constraint_guard_skips_a_different_definition(self, srv):
        """The failure PG022 exists for: the migration reports success while leaving
        a constraint that is not the one it asked for."""
        s = _fresh_schema(srv, "drift_c")
        srv.run(f"""
CREATE TABLE {s}.t(id bigint PRIMARY KEY, amt int);
ALTER TABLE {s}.t ADD CONSTRAINT ck_amt CHECK (amt > 100);
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conname = 'ck_amt' AND conrelid = '{s}.t'::regclass) THEN
    ALTER TABLE {s}.t ADD CONSTRAINT ck_amt CHECK (amt >= 0) NOT VALID;
  END IF;
END $$;
""", on_error_stop=True)
        actual = srv.scalar(
            f"SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            f"WHERE conrelid = '{s}.t'::regclass AND conname = 'ck_amt'")
        assert "amt > 100" in actual, (
            "the pre-existing definition was expected to survive the guard", actual)
        assert "amt >= 0" not in actual

    def test_definition_checked_guard_raises_instead_of_skipping(self, srv):
        """The recommended form must actually fail loudly -- a guard that silently
        does the right thing in this test would not prove anything."""
        s = _fresh_schema(srv, "drift_ok")
        srv.run(f"CREATE TABLE {s}.t(id bigint PRIMARY KEY, amt int);\n"
                f"ALTER TABLE {s}.t ADD CONSTRAINT ck_amt CHECK (amt > 100);",
                on_error_stop=True)
        r = srv.run(f"""
DO $$
DECLARE existing text;
BEGIN
  SELECT pg_get_constraintdef(oid) INTO existing FROM pg_constraint
   WHERE conname = 'ck_amt' AND conrelid = '{s}.t'::regclass;
  IF existing IS NULL THEN
    ALTER TABLE {s}.t ADD CONSTRAINT ck_amt CHECK (amt >= 0) NOT VALID;
  ELSIF existing NOT LIKE '%amt >= 0%' THEN
    RAISE EXCEPTION 'ck_amt exists with a different definition: %', existing;
  END IF;
END $$;
""")
        assert "different definition" in r.stderr, (
            "the definition-checked guard must raise, not skip", r.stderr)

    def test_create_index_if_not_exists_matches_on_name_only(self, srv):
        s = _fresh_schema(srv, "drift_i")
        srv.run(f"""
CREATE TABLE {s}.t(id bigint PRIMARY KEY, amt int, note text);
CREATE INDEX idx_x ON {s}.t (amt);
CREATE INDEX IF NOT EXISTS idx_x ON {s}.t (note);
""", on_error_stop=True)
        indexdef = srv.scalar(f"SELECT indexdef FROM pg_indexes "
                              f"WHERE schemaname = '{s}' AND indexname = 'idx_x'")
        assert "(amt)" in indexdef, (
            "IF NOT EXISTS was expected to keep the existing index", indexdef)
        assert "note" not in indexdef, (
            "the intended index on note must NOT have been built -- that is the hole")


# ---------------------------------------------------------------------------
# Facts a review flagged as wrong in the documents. Each is pinned here so the
# corrected wording cannot silently revert.
# ---------------------------------------------------------------------------

class TestCorrectedDocumentClaims:
    def test_extension_pin_creates_requested_version_when_absent(self, srv):
        _fresh_schema(srv, "ext_absent")
        result = srv.run(EXTENSION_PIN_SQL, on_error_stop=True)
        assert result.returncode == 0, result.stderr
        assert srv.scalar(
            "SELECT extversion FROM pg_extension "
            "WHERE extname = 'pg_stat_statements'") == "1.9"

    def test_extension_pin_is_noop_when_installed_version_matches(self, srv):
        _fresh_schema(srv, "ext_match")
        srv.run("CREATE EXTENSION pg_stat_statements VERSION '1.9';",
                on_error_stop=True)
        result = srv.run(EXTENSION_PIN_SQL, on_error_stop=True)
        assert result.returncode == 0, result.stderr
        assert srv.scalar(
            "SELECT extversion FROM pg_extension "
            "WHERE extname = 'pg_stat_statements'") == "1.9"

    def test_extension_pin_rejects_installed_version_mismatch(self, srv):
        _fresh_schema(srv, "ext_mismatch")
        other = srv.scalar(
            "SELECT version FROM pg_available_extension_versions "
            "WHERE name = 'pg_stat_statements' AND version <> '1.9' "
            "ORDER BY version LIMIT 1")
        assert other, "the live image exposes no alternate installable version"
        quoted = other.replace("'", "''")
        srv.run(f"CREATE EXTENSION pg_stat_statements VERSION '{quoted}';",
                on_error_stop=True)

        result = srv.run(EXTENSION_PIN_SQL)

        assert result.returncode != 0
        assert "is installed at" in result.stderr
        assert srv.scalar(
            "SELECT extversion FROM pg_extension "
            "WHERE extname = 'pg_stat_statements'") == other

    def test_extension_destdir_is_not_a_setting(self, srv):
        """replication-rls-extensions.md used to tell the reader to run
        `SHOW extension_destdir` to locate an extension's upgrade scripts. No such GUC
        exists on any supported major, so the instruction could only ever error."""
        assert srv.scalar(
            "SELECT count(*) FROM pg_settings WHERE name = 'extension_destdir'") == "0"

    def test_sharedir_is_the_documented_way_to_find_extension_scripts(self, srv):
        """The replacement instruction has to actually work."""
        sharedir = srv.scalar("SELECT setting FROM pg_config WHERE name = 'SHAREDIR'")
        assert sharedir.startswith("/"), sharedir

    def test_two_arg_setval_on_an_empty_table_skips_the_first_value(self, srv):
        """large-table-migration.md §2 step 4 used the two-argument form, which implies
        is_called = true. On an EMPTY table that burns id 1 -- the swap then starts at
        2 and a fresh table has a gap at its first row."""
        s = _fresh_schema(srv, "sv_bad")
        srv.run(f"""
CREATE TABLE {s}.t(id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY);
SELECT setval(pg_get_serial_sequence('{s}.t','id'),
              (SELECT coalesce(max(id), 1) FROM {s}.t));
INSERT INTO {s}.t DEFAULT VALUES;
""", on_error_stop=True)
        assert srv.scalar(f"SELECT min(id) FROM {s}.t") == "2", (
            "the two-argument form was expected to skip id 1; if it no longer does, "
            "the warning in large-table-migration.md needs rewriting"
        )

    def test_three_arg_setval_with_is_called_false_starts_at_one(self, srv):
        """The corrected form must actually fix it."""
        s = _fresh_schema(srv, "sv_ok")
        srv.run(f"""
CREATE TABLE {s}.t(id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY);
SELECT setval(pg_get_serial_sequence('{s}.t','id'),
              coalesce((SELECT max(id) FROM {s}.t), 1),
              (SELECT count(*) > 0 FROM {s}.t));
INSERT INTO {s}.t DEFAULT VALUES;
""", on_error_stop=True)
        assert srv.scalar(f"SELECT min(id) FROM {s}.t") == "1"

    def test_three_arg_setval_still_advances_a_non_empty_table(self, srv):
        """The empty-table fix must not break the case the statement exists for."""
        s = _fresh_schema(srv, "sv_full")
        srv.run(f"""
CREATE TABLE {s}.t(id bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY);
INSERT INTO {s}.t (id) SELECT g FROM generate_series(1, 10) g;
SELECT setval(pg_get_serial_sequence('{s}.t','id'),
              coalesce((SELECT max(id) FROM {s}.t), 1),
              (SELECT count(*) > 0 FROM {s}.t));
INSERT INTO {s}.t DEFAULT VALUES;
""", on_error_stop=True)
        assert srv.scalar(f"SELECT max(id) FROM {s}.t") == "11", (
            "after a copy the sequence must resume above the copied rows"
        )

    def test_nullable_add_column_still_takes_access_exclusive(self, srv):
        """SKILL.md §3 used to call it 'non-blocking'. It is brief, not blocking-free:
        it takes AccessExclusiveLock and so still queues behind open transactions and
        still needs a lock_timeout."""
        s = _fresh_schema(srv, "ac")
        srv.run(f"CREATE TABLE {s}.t(id bigint);", on_error_stop=True)
        got = _locks(srv, s, f"ALTER TABLE {s}.t ADD COLUMN note text;")
        assert "t=AccessExclusiveLock" in got, got

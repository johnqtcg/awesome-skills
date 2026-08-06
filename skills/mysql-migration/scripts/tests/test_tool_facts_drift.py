"""Drift guard for the gh-ost / pt-osc facts in references/large-table-migration.md.

Sources verified 2026-08-06:
  https://github.com/github/gh-ost  (doc/cheatsheet.md, doc/command-line-flags.md, releases)
  https://docs.percona.com/percona-toolkit/pt-online-schema-change.html

Assertions are scoped to **executable blocks** rather than the whole document.
The document necessarily discusses the wrong invocation in order to correct it,
so a naive "this string must not appear anywhere" test would fire on the very
prose that fixes the bug.
"""

from __future__ import annotations

import pathlib
import re

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
DOC_PATH = SKILL_DIR / "references" / "large-table-migration.md"
DOC = DOC_PATH.read_text(encoding="utf-8")

ANTI_DOC_PATH = SKILL_DIR / "references" / "migration-anti-examples.md"
ANTI_DOC = ANTI_DOC_PATH.read_text(encoding="utf-8")

_NEGATIVE = re.compile(r"\b(WRONG|INVALID|BAD|ALSO WRONG|DO NOT|NEVER)\b", re.I)
_REPLICA_HOST = re.compile(r"--host[=\s]+\S*(replica|slave|reader|standby)", re.I)


def code_blocks(md: str, langs=("bash", "sh", "shell")) -> list[tuple[str, bool]]:
    """Return (block_text, is_negative_example) for fenced blocks in the given langs."""
    out: list[tuple[str, bool]] = []
    lines = md.split("\n")
    i = 0
    while i < len(lines):
        m = re.match(r"^\s*```+\s*([A-Za-z0-9_+-]*)", lines[i])
        if not m:
            i += 1
            continue
        lang = m.group(1).lower()
        j = i + 1
        while j < len(lines) and not re.match(r"^\s*```+\s*$", lines[j]):
            j += 1
        if lang in langs:
            body = "\n".join(lines[i + 1 : j])
            preamble = "\n".join(lines[max(0, i - 3) : i])
            out.append((body, bool(_NEGATIVE.search(body) or _NEGATIVE.search(preamble))))
        i = j + 1
    return out


def join_continuations(text: str) -> list[str]:
    cmds, buf = [], ""
    for line in text.split("\n"):
        buf = (buf[:-1] + " " + line) if buf.rstrip().endswith("\\") else (buf + "\n" + line
                                                                          if buf else line)
        if not buf.rstrip().endswith("\\"):
            cmds.append(buf)
            buf = ""
    if buf:
        cmds.append(buf)
    return cmds


POSITIVE_SHELL = [b for b, neg in code_blocks(DOC) if not neg]
ALL_SHELL = [b for b, _ in code_blocks(DOC)]


class TestGhOstOperationMode:
    """--allow-on-master approves connecting to the MASTER, not to a replica."""

    def test_no_positive_example_pairs_allow_on_master_with_a_replica_host(self):
        offenders = []
        for block in POSITIVE_SHELL:
            for cmd in join_continuations(block):
                if "gh-ost" not in cmd and "--host" not in cmd:
                    continue
                if "--allow-on-master" in cmd and _REPLICA_HOST.search(cmd):
                    offenders.append(cmd.strip()[:160])
        assert not offenders, (
            "gh-ost's default mode already connects to a replica and migrates on the master; "
            "--allow-on-master is the opt-in for pointing --host AT the master. "
            f"Offending recommended commands: {offenders}"
        )

    def test_the_replica_mode_example_omits_the_flag(self):
        replica_cmds = [
            cmd for block in POSITIVE_SHELL for cmd in join_continuations(block)
            if "gh-ost" in cmd and _REPLICA_HOST.search(cmd)
        ]
        assert replica_cmds, "the doc must show the default replica-host invocation"
        for cmd in replica_cmds:
            assert "--allow-on-master" not in cmd

    def test_the_master_mode_example_includes_the_flag(self):
        master_cmds = [
            cmd for block in POSITIVE_SHELL for cmd in join_continuations(block)
            if "gh-ost" in cmd and re.search(r"--host[=\s]+\S*master", cmd, re.I)
        ]
        assert master_cmds, "the doc must show the master-host invocation for contrast"
        assert any("--allow-on-master" in cmd for cmd in master_cmds)

    def test_mode_table_states_omit_for_replica(self):
        rows = [ln for ln in DOC.split("\n") if ln.startswith("|") and "replica" in ln.lower()]
        assert any("omit" in ln.lower() for ln in rows), (
            "the operation-mode table must say the flag is omitted in replica mode"
        )


class TestGhOstDestructiveFlags:
    """Upstream disables these on purpose; they must not appear in a template."""

    DESTRUCTIVE = ("--initially-drop-old-table", "--initially-drop-ghost-table",
                   "--ok-to-drop-table")

    @pytest.mark.parametrize("flag", DESTRUCTIVE)
    def test_flag_absent_from_recommended_commands(self, flag):
        offenders = [
            cmd.strip()[:160] for block in POSITIVE_SHELL for cmd in join_continuations(block)
            if "gh-ost" in cmd and flag in cmd
        ]
        assert not offenders, (
            f"{flag} must not appear in a copy-paste template — the _old table from a prior run "
            f"is often the only surviving pre-migration copy. Offenders: {offenders}"
        )

    @pytest.mark.parametrize("flag", DESTRUCTIVE)
    def test_flag_is_still_explained_somewhere(self, flag):
        assert flag in DOC, (
            f"{flag} must remain documented with its rationale — removing the explanation would "
            "leave readers to rediscover the trap"
        )

    def test_upstream_rationale_is_quoted(self):
        assert "should not take chances" in DOC, (
            "quote upstream's reasoning so the recommendation is traceable, not an opinion"
        )


class TestGhOstVersionGates:
    @pytest.mark.parametrize("feature,version", [
        ("--include-triggers", "1.1.8"),
        ("--attempt-instant-ddl", "1.1.6"),
        ("--resume", "1.1.9"),
        ("--revert", "1.1.9"),
    ])
    def test_flag_table_row_carries_its_minimum_version(self, feature, version):
        """The gate must be on the flag's own table row.

        Stating it only in prose elsewhere is not enough: the table is what gets
        read when someone assembles a command.
        """
        rows = [
            ln for ln in DOC.split("\n")
            if ln.startswith("|") and f"`{feature}`" in ln
        ]
        assert rows, f"{feature} has no row in the gh-ost flag table"
        assert any(version in ln for ln in rows), (
            f"the `{feature}` table row must state gh-ost {version}+; recommending it without "
            f"the gate sends people to a flag their binary does not have. Rows: {rows}"
        )


class TestTriggerHandling:
    def test_does_not_recommend_dropping_business_triggers(self):
        assert "Do not drop business triggers" in DOC, (
            "gh-ost >=1.1.8 supports --include-triggers; dropping a business trigger silently "
            "disables the behaviour it implements for the whole migration window"
        )

    def test_decision_tree_routes_triggers_correctly(self):
        tree = re.search(r"```\n(Is the ALTER INSTANT-eligible.*?)```", DOC, re.S)
        assert tree, "the tool-selection decision tree is missing"
        body = tree.group(1)
        assert "trigger" in body.lower()
        assert "--include-triggers" in body or "include-triggers" in body


class TestBackfillRunnability:
    def test_invalid_loop_is_labelled_invalid(self):
        assert "INVALID outside a stored program" in DOC, (
            "the bare WHILE example must stay explicitly marked invalid"
        )
        assert "ERROR 1064" in DOC

    def test_a_runnable_stored_procedure_form_exists(self):
        assert "CREATE PROCEDURE" in DOC and "DELIMITER" in DOC, (
            "WHILE is only valid inside a stored program; the doc must show that form"
        )

    def test_external_driver_is_the_recommendation(self):
        assert re.search(r"Prefer the external driver", DOC), (
            "the external driver is preferred because it can observe replica lag, persist "
            "progress, and be killed cleanly"
        )

    def test_sql_log_bin_is_not_in_any_recommended_block(self):
        sql_blocks = [b for b, neg in code_blocks(DOC, langs=("sql",)) if not neg]
        offenders = [b for b in sql_blocks if re.search(r"sql_log_bin\s*=\s*0", b, re.I)]
        assert not offenders, (
            "sql_log_bin=0 stops the write replicating and must never sit in a template; "
            f"found in {len(offenders)} recommended block(s)"
        )

    def test_sql_log_bin_risks_are_documented(self):
        for token in ("permanently divergent", "point-in-time recovery", "SYSTEM_VARIABLES_ADMIN"):
            assert token in DOC, f"missing sql_log_bin risk: {token}"


class TestVersionCorrectMonitoring:
    def test_replication_statement_table_covers_all_bands(self):
        for token in ("SHOW SLAVE STATUS", "SHOW REPLICA STATUS",
                      "Seconds_Behind_Master", "Seconds_Behind_Source",
                      "8.0.22", "8.4"):
            assert token in DOC, f"replication compatibility token missing: {token}"

    def test_57_lock_interface_is_documented(self):
        assert "INNODB_LOCKS" in DOC and "INNODB_LOCK_WAITS" in DOC, (
            "performance_schema.data_locks is 8.0+; 5.7 needs the INFORMATION_SCHEMA tables"
        )

    def test_data_locks_is_marked_as_80_only(self):
        rows = [ln for ln in DOC.split("\n") if "data_locks" in ln]
        assert any("8.0" in ln for ln in rows), (
            "every data_locks reference must carry its version gate"
        )


class TestPtOscFacts:
    @pytest.mark.parametrize("flag,default", [
        ("--max-load", "`Threads_running=25`"),
        ("--critical-load", "`Threads_running=50`"),
        ("--max-lag", "`1s`"),
        ("--check-interval", "`1s`"),
        ("--chunk-size", "1000"),
    ])
    def test_upstream_defaults_are_quoted_exactly(self, flag, default):
        """Compare whole table cells.

        A substring test passes when 50 drifts to 500 — the cell must match
        exactly, or the guard silently permits an order-of-magnitude error.
        """
        rows = [
            [c.strip() for c in ln.strip().strip("|").split("|")]
            for ln in DOC.split("\n")
            if ln.startswith("|") and f"`{flag}`" in ln
        ]
        assert rows, f"{flag} has no row in the pt-osc flag table"
        cells = [c for row in rows for c in row]
        assert default in cells, (
            f"upstream default for {flag} is {default}; the table's cells are {cells}"
        )

    def test_lock_wait_timeout_default_is_flagged_as_too_long(self):
        assert "lock_wait_timeout` default is 60s" in DOC or "lock_wait_timeout = 60" in DOC \
            or "lock_wait_timeout=60" in DOC, (
            "pt-osc defaults lock_wait_timeout to 60s, 20x the value this skill requires"
        )

    def test_null_to_not_null_is_marked_dangerous(self):
        assert "--null-to-not-null" in DOC
        assert "silently rewrites data" in DOC or "silently" in DOC


class TestAntiExampleFactsStayCorrected:
    """AE-13 previously recommended an FK path the server rejects."""

    def test_ae13_states_the_manual_rule(self):
        assert "foreign_key_checks` is disabled" in ANTI_DOC or \
               "foreign_key_checks is disabled" in ANTI_DOC
        assert "only the\nCOPY algorithm is supported" in ANTI_DOC or \
               "only the COPY algorithm is supported" in ANTI_DOC

    def test_ae13_does_not_present_bare_inplace_as_the_fix(self):
        """The INPLACE form must be inside a foreign_key_checks=0 block."""
        section = re.search(r"## AE-13:.*?(?=\n## |\Z)", ANTI_DOC, re.S)
        assert section, "AE-13 is missing"
        body = section.group(0)
        for block, neg in code_blocks(body, langs=("sql",)):
            if "ADD CONSTRAINT" in block and "ALGORITHM=INPLACE" in block and not neg:
                assert re.search(r"foreign_key_checks\s*=\s*0", block, re.I), (
                    "a recommended ADD FOREIGN KEY ... ALGORITHM=INPLACE block must disable "
                    "foreign_key_checks first, or the statement fails"
                )

    def test_ae9_says_fulltext_always_blocks_dml(self):
        section = re.search(r"## AE-9:.*?(?=\n## |\Z)", ANTI_DOC, re.S)
        assert section
        body = section.group(0)
        assert "never permit concurrent" in body, (
            "FULLTEXT blocks writes for every index build, not merely the first on the table"
        )

    def test_new_anti_examples_exist(self):
        for ae in ("AE-14", "AE-15", "AE-16", "AE-17"):
            assert f"## {ae}:" in ANTI_DOC, f"{ae} missing"


SKILL_MD = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

# Statement-level DDL that genuinely accepts IF [NOT] EXISTS in MySQL.
_STATEMENT_LEVEL_IF_EXISTS = re.compile(
    r"\b(CREATE|DROP)\s+(TABLE|DATABASE|SCHEMA|VIEW|TRIGGER|PROCEDURE|FUNCTION|EVENT|USER)\b",
    re.I)
# Wording that marks a mention as a correction rather than a recommendation.
_DISCLAIMS = re.compile(
    r"\b(no|not|never|rejects?|invalid|MariaDB|parse error|unsupported|has no|cannot)\b", re.I)


class TestIdempotencyAdviceIsValidMySQL:
    """MySQL ALTER TABLE has no IF [NOT] EXISTS; recommending it emits a parse error.

    Scoped so the sentence that *corrects* the myth cannot satisfy the guard: the
    assertion is that no line RECOMMENDS the clause for ALTER, not that the string
    is absent from the file.
    """

    def test_no_document_recommends_if_not_exists_for_alter(self):
        offenders = []
        for name, doc in (("SKILL.md", SKILL_MD),
                          ("large-table-migration.md", DOC),
                          ("migration-anti-examples.md", ANTI_DOC)):
            for i, line in enumerate(doc.split("\n"), 1):
                if not re.search(r"IF\s+(?:NOT\s+)?EXISTS", line, re.I):
                    continue
                if _DISCLAIMS.search(line):
                    continue
                if _STATEMENT_LEVEL_IF_EXISTS.search(line):
                    continue
                offenders.append(f"{name}:{i}: {line.strip()[:110]}")
        assert not offenders, (
            "MySQL ALTER TABLE has no IF [NOT] EXISTS for columns or indexes; recommending it "
            f"produces a statement the server cannot parse. Offending lines: {offenders}"
        )

    def test_skill_states_the_limitation_and_the_alternative(self):
        assert "has no `IF NOT EXISTS` / `IF EXISTS`" in SKILL_MD
        for alt in ("history table", "information_schema"):
            assert alt in SKILL_MD, f"idempotency alternative not documented: {alt}"

    def test_hygiene_tier_does_not_require_the_invalid_clause(self):
        scorecard = re.search(r"### Hygiene.*?(?=\n---|\n## )", SKILL_MD, re.S)
        assert scorecard, "the Hygiene tier is missing"
        for line in scorecard.group(0).split("\n"):
            if re.search(r"IF\s+\[?NOT\]?\s*EXISTS", line, re.I):
                assert _DISCLAIMS.search(line), (
                    f"the Hygiene checklist must not require a clause ALTER TABLE rejects: {line}"
                )


class TestPtOscPreserveTriggersDocumented:
    """A trigger-carrying table has exactly one pt-osc path, and it has hard constraints."""

    def _section(self):
        m = re.search(r"### 2\.1 .*?(?=\n## |\n---)", DOC, re.S)
        assert m, "the pt-osc trigger path needs its own section, not a passing mention"
        return m.group(0)

    def test_dedicated_section_exists(self):
        assert re.search(r"###\s*2\.1\s*`--preserve-triggers`", DOC)

    @pytest.mark.parametrize("clash", [
        "--no-drop-triggers", "--no-drop-old-table", "--no-swap-tables",
    ])
    def test_each_incompatible_flag_is_named(self, clash):
        assert clash in self._section(), (
            f"upstream forbids combining --preserve-triggers with {clash}; the conflict must be "
            "stated where the flag is recommended"
        )

    def test_the_rollback_tradeoff_is_called_out(self):
        """--no-drop-old-table is recommended earlier in this same file."""
        section = self._section()
        assert "rollback" in section.lower() and "_old" in section, (
            "keeping the _old rollback copy and preserving triggers are mutually exclusive; "
            "a reader following the section 2 template must be told"
        )

    def test_version_floor_is_stated(self):
        assert "5.7.2" in self._section(), "--preserve-triggers requires MySQL 5.7.2+"

    def test_dropped_column_restriction_is_stated(self):
        section = self._section()
        assert "references" in section and "drops a column" in section.lower(), (
            "a trigger reading a column the ALTER drops blocks --preserve-triggers"
        )

    def test_flag_table_row_exists_with_version(self):
        rows = [ln for ln in DOC.split("\n")
                if ln.startswith("|") and "`--preserve-triggers`" in ln]
        assert rows, "--preserve-triggers must appear in the pt-osc flag table"
        assert any("5.7.2" in ln for ln in rows)

    def test_no_drop_old_table_row_warns_about_the_clash(self):
        rows = [ln for ln in DOC.split("\n")
                if ln.startswith("|") and "`--no-drop-old-table`" in ln]
        assert rows and any("preserve-triggers" in ln for ln in rows), (
            "the --no-drop-old-table row must warn that it cannot combine with --preserve-triggers"
        )

    def test_decision_tree_routes_triggers_with_the_constraints(self):
        tree = re.search(r"```\n(Is the ALTER INSTANT-eligible.*?)```", DOC, re.S)
        assert tree, "the tool-selection decision tree is missing"
        body = tree.group(1)
        assert "--preserve-triggers" in body
        assert "5.7.2" in body

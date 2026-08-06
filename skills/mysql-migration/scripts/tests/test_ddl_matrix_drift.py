"""Drift guard for references/ddl-algorithm-matrix.md.

The matrix is transcribed from the official MySQL manual. The values pinned here
are an independent record of that transcription, taken from
https://dev.mysql.com/doc/refman/{5.7,8.0,8.4}/en/innodb-online-ddl-operations.html
on 2026-08-06 (the 8.4 table is byte-identical to 8.0).

If a matrix cell is edited without a corresponding manual re-check, these tests
fail. That is the point: the 2026-08-06 audit found four rows that had drifted
from the manual and nothing in the suite noticed, because the only assertion was
"this phrase appears somewhere in the docs".
"""

from __future__ import annotations

import pathlib
import re

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
MATRIX_PATH = SKILL_DIR / "references" / "ddl-algorithm-matrix.md"
MATRIX = MATRIX_PATH.read_text(encoding="utf-8")


def _tables(md: str) -> list[list[list[str]]]:
    """Extract pipe tables as lists of cell-lists (header row included)."""
    tables, current = [], []
    for line in md.split("\n"):
        if line.strip().startswith("|") and line.strip().endswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue  # separator row
            current.append(cells)
        elif current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    return tables


TABLES = _tables(MATRIX)


def row_for(operation_prefix: str) -> list[str]:
    """Return the first table row whose first cell starts with the given text."""
    for table in TABLES:
        for cells in table:
            if cells and cells[0].lower().startswith(operation_prefix.lower()):
                return cells
    raise AssertionError(
        f"no matrix row starting with {operation_prefix!r}; the row was renamed or removed"
    )


class TestOperationRowsMatchTheManual:
    """Each case: (row prefix, must appear in the row, must NOT appear in the row)."""

    def test_drop_column_is_inplace_not_copy(self):
        """5.7 In Place=Yes / Concurrent DML=Yes; 8.0 INSTANT only from 8.0.29."""
        cells = row_for("DROP COLUMN")
        joined = " ".join(cells)
        assert "INPLACE" in joined, "DROP COLUMN is INPLACE on 5.7 and on 8.0 before 8.0.29"
        assert "8.0.29" in joined, "INSTANT DROP COLUMN is gated at 8.0.29"
        assert not re.search(r"\bCOPY\b", cells[1]), (
            "5.7 DROP COLUMN is not COPY — the manual's own example is "
            "ALTER TABLE t DROP COLUMN c, ALGORITHM=INPLACE, LOCK=NONE"
        )
        assert cells[3].strip().startswith("Yes"), "DROP COLUMN permits concurrent DML"

    def test_varchar_extension_is_never_instant(self):
        cells = row_for("Extend VARCHAR, length bytes unchanged")
        assert "never INSTANT" in " ".join(cells), (
            "the 8.0/8.4 manual lists 'Extending VARCHAR column size' as Instant = No"
        )
        assert "INSTANT" not in cells[1], "5.7 has no INSTANT at all"

    def test_varchar_crossing_boundary_is_copy(self):
        cells = row_for("Extend VARCHAR across")
        assert "COPY" in cells[1] and "COPY" in cells[2]
        assert cells[3].strip().startswith("**No**") or cells[3].strip().startswith("No")

    def test_varchar_shrink_is_copy(self):
        cells = row_for("**Shrink** VARCHAR")
        assert "COPY" in cells[1] and "COPY" in cells[2]

    def test_add_foreign_key_requires_fk_checks_off_for_inplace(self):
        cells = row_for("ADD FOREIGN KEY")
        joined = " ".join(cells)
        assert "foreign_key_checks=0" in joined.replace(" ", "") or \
               "foreign_key_checks" in joined
        assert "COPY" in joined, (
            "with foreign_key_checks enabled only COPY is supported"
        )

    def test_drop_foreign_key_has_no_such_restriction(self):
        cells = row_for("DROP FOREIGN KEY")
        assert "INPLACE" in cells[1] and "INPLACE" in cells[2]
        assert cells[3].strip().startswith("Yes")

    def test_add_primary_key_permits_concurrent_dml(self):
        """Manual: Adding a primary key -> Permits Concurrent DML = Yes."""
        cells = row_for("ADD PRIMARY KEY")
        assert "Yes" in cells[3], (
            "ADD PRIMARY KEY permits concurrent DML, so LOCK=NONE is accepted; "
            "claiming SHARED would wrongly demand a maintenance window"
        )
        assert "Yes" in cells[4], "ADD PRIMARY KEY rebuilds the table"

    def test_drop_primary_key_alone_is_copy_and_blocks_dml(self):
        cells = row_for("DROP PRIMARY KEY (alone)")
        assert "COPY" in cells[1] and "COPY" in cells[2]
        assert "No" in cells[3]

    def test_drop_and_add_primary_key_permits_dml(self):
        cells = row_for("DROP PK + ADD PK")
        assert "Yes" in cells[3]

    def test_fulltext_index_never_permits_concurrent_dml(self):
        """Manual: Adding a FULLTEXT index -> Permits Concurrent DML = No, both versions."""
        cells = row_for("ADD FULLTEXT INDEX")
        assert "No" in cells[3] and "SHARED" in cells[3], (
            "FULLTEXT blocks writes for every index built, not only the first"
        )
        assert "every time" in " ".join(cells) or "not only" in " ".join(cells)

    def test_spatial_index_never_permits_concurrent_dml(self):
        cells = row_for("ADD SPATIAL INDEX")
        assert "No" in cells[3] and "SHARED" in cells[3]

    def test_rename_index_is_not_instant(self):
        cells = row_for("RENAME INDEX")
        assert "Not INSTANT" in " ".join(cells) or "not INSTANT" in " ".join(cells)

    def test_change_index_type_is_instant_on_80(self):
        cells = row_for("Change index type")
        assert "INSTANT" in cells[2]

    def test_convert_charset_is_copy_on_57_and_shared_on_80(self):
        cells = row_for("`CONVERT TO CHARACTER SET")
        assert "COPY" in cells[1], "5.7 lists In Place = No for converting a character set"
        assert "INPLACE" in cells[2]
        assert "SHARED" in cells[3] and "No" in cells[3], (
            "8.0 converts in place but does not permit concurrent DML"
        )

    def test_rename_column_instant_is_gated_at_8028(self):
        cells = row_for("RENAME COLUMN")
        joined = " ".join(cells)
        assert "8.0.28" in joined, "INSTANT rename is gated at 8.0.28"
        assert "CHANGE" in cells[1], (
            "5.7 has no RENAME COLUMN syntax — the 5.7 cell must point at CHANGE"
        )
        assert "8.0+" in joined, "the note must state RENAME COLUMN syntax is 8.0+"

    def test_change_data_type_is_copy_only(self):
        cells = row_for("CHANGE column data type")
        assert "COPY" in cells[1] and "COPY" in cells[2]
        assert "No" in cells[3]

    def test_not_null_change_rebuilds_and_needs_strict_mode(self):
        cells = row_for("MODIFY NULL → NOT NULL")
        joined = " ".join(cells)
        assert "STRICT" in joined
        assert "Yes" in cells[5] or "Yes" in cells[4]

    def test_nullable_change_rebuilds_table(self):
        """The old matrix called this 'metadata only'; the manual says Rebuilds = Yes."""
        cells = row_for("MODIFY NOT NULL → NULL")
        assert cells[4].strip() == "**Yes**", (
            f"Rebuilds? cell must be an emphatic Yes, got {cells[4]!r} — the manual lists "
            "'Making a column NULL' as Rebuilds Table = Yes, so this is not metadata-only"
        )
        assert "metadata-only" in cells[5], (
            "the note must say explicitly that this is not a metadata-only change"
        )

    def test_add_column_auto_increment_blocks_dml(self):
        cells = row_for("ADD COLUMN (last position)")
        assert "AUTO_INCREMENT" in " ".join(cells), (
            "adding an AUTO_INCREMENT column refuses concurrent DML on both versions"
        )


class TestPartitionSection:
    def test_57_partition_clauses_are_default_only(self):
        for clause in ("`ADD PARTITION`", "`DROP PARTITION`", "`REORGANIZE PARTITION`",
                       "`COALESCE PARTITION`", "`REBUILD PARTITION`"):
            cells = row_for(clause)
            assert "DEFAULT" in cells[1] and "only" in cells[1].lower(), (
                f"{clause} accepts only ALGORITHM=DEFAULT, LOCK=DEFAULT on 5.7; got {cells[1]!r}"
            )

    def test_80_reorganize_family_refuses_lock_none(self):
        for clause in ("`REORGANIZE PARTITION`", "`COALESCE PARTITION`", "`REBUILD PARTITION`"):
            cells = row_for(clause)
            assert "NONE" not in cells[2], (
                f"{clause} on 8.0 supports LOCK={{DEFAULT,SHARED,EXCLUSIVE}} — not NONE"
            )
            assert "No" in cells[3]

    def test_80_add_partition_lock_none_is_range_list_only(self):
        cells = row_for("`ADD PARTITION`")
        assert "RANGE" in cells[2] and "HASH" in cells[2]
        assert "RANGE/LIST only" in cells[3]

    def test_drop_partition_semantics_differ_by_algorithm(self):
        note = re.search(
            r"`DROP PARTITION` changes meaning with the algorithm.*?(?=\n\n|\Z)",
            MATRIX, re.S)
        assert note, "the DROP PARTITION algorithm-semantics callout is missing"
        body = note.group(0)
        for token in ("ALGORITHM=INPLACE", "ALGORITHM=COPY", "compatible"):
            assert token in body, (
                f"{token} missing from the DROP PARTITION callout: with COPY the server "
                "rebuilds and moves rows to a compatible partition instead of deleting them"
            )


class TestInstantLimits:
    def test_row_version_budget_is_64(self):
        assert "64" in MATRIX and "TOTAL_ROW_VERSIONS" in MATRIX
        assert "ERROR 4092" in MATRIX

    def test_no_unsourced_one_instant_per_rebuild_claim(self):
        """The manual documents a positional limit before 8.0.29, not a count limit.

        Scoped to bullet lines so the explanatory prose is not what satisfies it.
        """
        bad = [
            ln for ln in MATRIX.split("\n")
            if ln.lstrip().startswith(("-", "*", "|"))
            and re.search(r"only\s+\*{0,2}one\*{0,2}\s+INSTANT", ln, re.I)
        ]
        assert not bad, (
            "the 'only one INSTANT ALTER per table between rebuilds' claim is not in the "
            f"manual; the documented pre-8.0.29 limit is positional. Offending lines: {bad}"
        )

    def test_instant_gates_are_stated(self):
        for gate in ("8.0.12", "8.0.28", "8.0.29"):
            assert gate in MATRIX, f"INSTANT version gate {gate} missing from the matrix"

    def test_instant_clause_introduction_is_8012_not_80(self):
        """The clause arrives whole in 8.0.12 — not only its ADD COLUMN case.

        Saying "8.0 has INSTANT but not for ADD COLUMN" implies 8.0.0-8.0.11
        accept ALGORITHM=INSTANT for other operations. They do not.
        """
        assert "does not exist before MySQL 8.0.12" in MATRIX
        assert "8.0.0–8.0.11 reject the clause for **every**" in MATRIX

    def test_the_six_supported_operations_are_listed(self):
        """Nutshell enumerates exactly what 8.0.12 made INSTANT-capable."""
        for op in ("virtual", "default value", "`ENUM`/`SET`", "index type", "renaming a table"):
            assert op in MATRIX, f"8.0.12 INSTANT operation missing from the matrix: {op}"

    def test_flowchart_marks_8000_to_8011_as_having_no_instant(self):
        chart = re.search(r"0\. What is the exact server version.*?```", MATRIX, re.S)
        assert chart, "the version-selection flowchart is missing"
        body = chart.group(0)
        line = [ln for ln in body.split("\n") if "8.0.0" in ln]
        assert line, "the flowchart must call out the 8.0.0-8.0.11 band"
        assert "no ALGORITHM=INSTANT clause" in line[0], (
            f"8.0.0-8.0.11 has no INSTANT clause at all; flowchart says: {line[0]!r}"
        )

    def test_57_has_no_instant_algorithm(self):
        assert "MySQL 5.7 has no INSTANT algorithm at all" in MATRIX


class TestProvenance:
    def test_source_urls_and_verification_date_present(self):
        for token in ("dev.mysql.com/doc/refman/5.7/en/innodb-online-ddl-operations.html",
                      "dev.mysql.com/doc/refman/8.0/en/innodb-online-ddl-operations.html",
                      "2026-08-06"):
            assert token in MATRIX, f"provenance token missing: {token}"

    def test_84_is_documented_as_identical_to_80(self):
        assert "8.4" in MATRIX and "identical" in MATRIX

    def test_lock_none_derivation_is_explained(self):
        assert "Permits Concurrent DML" in MATRIX, (
            "the LOCK=NONE column is derived from the manual's Permits Concurrent DML column; "
            "the derivation must stay visible or the table becomes unverifiable"
        )

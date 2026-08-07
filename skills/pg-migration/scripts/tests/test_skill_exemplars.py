"""Lint the skill's own SQL exemplars with the skill's own checker.

A skill that ships a recommended snippet its own linter rejects has a defect in
one of the two -- and which one is a question worth being forced to answer. This
suite finds that disagreement automatically instead of trusting either document.

The core invariant, applied to every WRONG/RIGHT anti-example pair:

    findings(RIGHT) must be a strict subset of findings(WRONG)

That is, the corrected form must fix at least one flagged problem and must not
introduce any new one. This is deliberately per-pair rather than "RIGHT has zero
findings": anti-example snippets are fragments and legitimately omit guards that
are not the point of that example.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
DOCS = [SKILL_DIR / "SKILL.md"] + sorted((SKILL_DIR / "references").glob("*.md"))


def _load_linter():
    path = SKILL_DIR / "scripts" / "lint_migration.py"
    spec = importlib.util.spec_from_file_location("pg_lint_exemplar", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pg_lint_exemplar"] = mod
    spec.loader.exec_module(mod)
    return mod


LINT = _load_linter()

FENCE_RE = re.compile(r"```sql\n(.*?)```", re.S)
WRONG_RE = re.compile(r"^\s*--\s*WRONG\b", re.I)
RIGHT_RE = re.compile(r"^\s*--\s*RIGHT\b", re.I)


def _sql_blocks(path: pathlib.Path) -> list[tuple[int, str]]:
    """Return (line_number, block_body) for each ```sql fence."""
    text = path.read_text(encoding="utf-8")
    out = []
    for m in FENCE_RE.finditer(text):
        line = text[: m.start()].count("\n") + 1
        out.append((line, m.group(1)))
    return out


def _split_wrong_right(block: str) -> tuple[str | None, str | None]:
    """Partition a block into its WRONG and RIGHT halves, if both are marked."""
    lines = block.splitlines()
    wrong_at = right_at = None
    for i, ln in enumerate(lines):
        if wrong_at is None and WRONG_RE.match(ln):
            wrong_at = i
        elif right_at is None and RIGHT_RE.match(ln):
            right_at = i
            break
    if wrong_at is None or right_at is None or right_at <= wrong_at:
        return None, None
    return ("\n".join(lines[wrong_at:right_at]),
            "\n".join(lines[right_at:]))


def _strip_wrong_regions(block: str) -> str:
    """Blank out every deliberately-wrong region, keeping line count intact.

    A region runs from a `-- WRONG` marker to the next `-- RIGHT` marker, or to the
    end of the block when the fence contains only the wrong form (AE-12 is shaped
    that way). Removed lines are replaced by empty lines rather than deleted, so
    neighbouring statements cannot be fused into one by the removal.
    """
    out, skipping = [], False
    for ln in block.splitlines():
        if WRONG_RE.match(ln):
            skipping = True
        elif RIGHT_RE.match(ln):
            skipping = False
        out.append("" if skipping else ln)
    return "\n".join(out)


def _pairs() -> list[tuple[str, int, str, str]]:
    found = []
    for path in DOCS:
        for line, block in _sql_blocks(path):
            wrong, right = _split_wrong_right(block)
            if wrong and right:
                found.append((path.name, line, wrong, right))
    return found


PAIRS = _pairs()


def _codes(sql: str) -> set[str]:
    return {f.code for f in LINT.Linter().lint(sql)}


class TestCorpusDiscovered:
    """If the extraction silently finds nothing, every test below passes vacuously."""

    def test_docs_exist(self):
        assert DOCS, "no documentation files found"
        for d in DOCS:
            assert d.exists()

    def test_sql_blocks_found(self):
        total = sum(len(_sql_blocks(p)) for p in DOCS)
        assert total >= 15, f"only {total} sql blocks extracted -- extraction likely broken"

    def test_wrong_right_pairs_found(self):
        assert len(PAIRS) >= 6, (
            f"only {len(PAIRS)} WRONG/RIGHT pairs extracted -- the marker regex is "
            "probably not matching the documents' actual comment style"
        )


@pytest.mark.parametrize(
    "doc,line,wrong,right",
    PAIRS,
    ids=[f"{d}:{ln}" for d, ln, _, _ in PAIRS],
)
class TestAntiExamplePairs:
    def test_wrong_half_is_flagged(self, doc, line, wrong, right):
        """An anti-example whose WRONG half lints clean is not testing anything."""
        assert _codes(wrong), (
            f"{doc}:{line}: the WRONG half produced no findings -- either the "
            "example is not actually wrong, or no rule covers it"
        )

    def test_right_half_improves_on_wrong(self, doc, line, wrong, right):
        bad, good = _codes(wrong), _codes(right)
        assert good < bad, (
            f"{doc}:{line}: RIGHT half did not strictly improve on WRONG.\n"
            f"  WRONG -> {sorted(bad)}\n  RIGHT -> {sorted(good)}\n"
            f"  introduced: {sorted(good - bad)}"
        )

    def test_right_half_introduces_nothing_new(self, doc, line, wrong, right):
        introduced = _codes(right) - _codes(wrong)
        assert not introduced, (
            f"{doc}:{line}: the recommended form triggers new findings "
            f"{sorted(introduced)} -- the skill contradicts its own checker"
        )


class TestNoDocumentedGuardIsANoOp:
    """Scoped to emitted SQL only: a `SET LOCAL` guard placed in front of a
    CONCURRENTLY statement is the top defect this hardening addressed. Prose that
    *explains* the mistake must remain allowed, so only fenced sql blocks are
    scanned, and a block is exempt when it is the WRONG half of a pair.
    """

    def test_no_set_local_guarding_a_concurrently_statement(self):
        offenders = []
        for path in DOCS:
            for line, block in _sql_blocks(path):
                stmts = LINT.split_statements(_strip_wrong_regions(block))
                pending_local = False
                for s in stmts:
                    norm = s.norm
                    if re.match(r"^SET\s+LOCAL\s+(LOCK|STATEMENT)_TIMEOUT", norm):
                        pending_local = not s.in_transaction
                        continue
                    if pending_local and LINT._is_concurrently(norm):
                        offenders.append(f"{path.name}:{line}")
                    if norm:
                        pending_local = False
        assert not offenders, (
            "SET LOCAL used as the guard for a CONCURRENTLY statement in: "
            f"{offenders}. Outside a transaction block SET LOCAL only warns and has "
            "no effect, so the guard does not exist."
        )

    def test_exemption_preserves_line_count(self):
        """Blanking rather than deleting keeps positions honest and stops two
        statements either side of a removed region from fusing into one."""
        block = "-- WRONG: x\nBEGIN;\nCOMMIT;\n-- RIGHT: y\nANALYZE t;\n"
        assert len(_strip_wrong_regions(block).splitlines()) == len(block.splitlines())

    def test_exemption_does_not_blind_the_check(self):
        """Positive control: a violation in the RIGHT half must still be seen.
        Without this, an over-broad exemption would make the two checks above pass
        on any document at all."""
        block = ("-- WRONG: plain build\n"
                 "CREATE INDEX i ON t (c);\n"
                 "-- RIGHT: still broken -- CONCURRENTLY inside a transaction\n"
                 "BEGIN;\n"
                 "CREATE INDEX CONCURRENTLY i ON t (c);\n"
                 "COMMIT;\n")
        kept = _strip_wrong_regions(block)
        assert any(s.in_transaction and LINT._is_concurrently(s.norm)
                   for s in LINT.split_statements(kept)), \
            "the exemption swallowed a genuine violation in the RIGHT half"

    def test_exemption_does_hide_the_wrong_half(self):
        """Negative control: the intentionally-wrong half must be exempt, or every
        anti-example would be reported as a defect."""
        block = ("-- WRONG: CONCURRENTLY cannot run inside a transaction\n"
                 "BEGIN;\n"
                 "CREATE INDEX CONCURRENTLY i ON t (c);\n"
                 "COMMIT;\n")
        kept = _strip_wrong_regions(block)
        assert not any(s.in_transaction and LINT._is_concurrently(s.norm)
                       for s in LINT.split_statements(kept))

    def test_concurrently_never_shown_inside_begin_commit(self):
        offenders = []
        for path in DOCS:
            for line, block in _sql_blocks(path):
                for s in LINT.split_statements(_strip_wrong_regions(block)):
                    if s.in_transaction and LINT._is_concurrently(s.norm):
                        offenders.append(f"{path.name}:{line}")
        assert not offenders, (
            f"CONCURRENTLY shown inside a transaction block in: {offenders}"
        )

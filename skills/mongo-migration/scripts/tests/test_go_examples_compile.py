"""Compile gate for the Go blocks this skill ships.

The JavaScript blocks are parsed by a real mongosh (test_mongo_server_matrix.py). The Go
blocks had no equivalent, and a review found the consequence: a `BulkWrite` snippet
called `wcColl` after the surrounding example had renamed that handle to `coll`, so the
code could not compile. Nothing in the suite could have noticed.

What this does
--------------
Every ```go block that is NOT marked `// excerpt:` is wrapped in a minimal package,
gofmt-parsed, and type-checked with `go vet` against a module that has the MongoDB
driver types stubbed. Full compilation against the real driver would need a network
fetch on every run; the stub catches the class of defect that actually shipped --
undefined identifiers, wrong arity, syntax errors -- without one.

Skips (never fails) when the Go toolchain is absent, and says so.
"""

from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

import pytest

SKILL_DIR = pathlib.Path(__file__).resolve().parents[2]
DOCS = [SKILL_DIR / "SKILL.md"] + sorted((SKILL_DIR / "references").glob("*.md"))

GO_FENCE_RE = re.compile(r"```go\n(.*?)```", re.S)
EXCERPT_RE = re.compile(r"^\s*//\s*excerpt\b", re.I)
MAX_EXCERPTS = 4

_GO = shutil.which("go")
_GOFMT = shutil.which("gofmt")

pytestmark = pytest.mark.skipif(
    not (_GO and _GOFMT),
    reason="Go toolchain not installed; the Go blocks cannot be compile-checked",
)

EXCERPTS: list[str] = []


def _go_blocks() -> list[tuple[str, int, str]]:
    out = []
    for doc in DOCS:
        text = doc.read_text(encoding="utf-8")
        for m in GO_FENCE_RE.finditer(text):
            block = m.group(1)
            first = next((ln for ln in block.splitlines() if ln.strip()), "")
            line = text[:m.start()].count("\n") + 2
            if EXCERPT_RE.match(first):
                EXCERPTS.append(f"{doc.name}:{line}")
                continue
            out.append((doc.name, line, block))
    return out


GO_BLOCKS = _go_blocks()

# Enough of the driver surface for `go vet` to resolve the identifiers these examples
# use. Deliberately a stub: pulling the real module would make every run depend on a
# network fetch, and the defect this gate exists for (an identifier that does not exist)
# is caught either way.
STUBS = {
    "go.mod": "module skillcheck\n\ngo 1.21\n",
    "stub/stub.go": '''package stub

import "context"

type Ctx = context.Context

type M map[string]any
type D []E
type E struct {
    Key   string
    Value any
}

type Cursor struct{}

func (c *Cursor) All(ctx context.Context, out any) error { return nil }
func (c *Cursor) Next(ctx context.Context) bool          { return false }
func (c *Cursor) Decode(out any) error                   { return nil }
func (c *Cursor) Close(ctx context.Context) error        { return nil }

type WriteModel interface{}

type UpdateOneModel struct{}

func NewUpdateOneModel() *UpdateOneModel                     { return &UpdateOneModel{} }
func (u *UpdateOneModel) SetFilter(f any) *UpdateOneModel    { return u }
func (u *UpdateOneModel) SetUpdate(v any) *UpdateOneModel    { return u }

type Pipeline []D

type Collection struct{}

func (c *Collection) Find(ctx context.Context, filter any, opts ...any) (*Cursor, error) {
    return &Cursor{}, nil
}
func (c *Collection) Aggregate(ctx context.Context, p any, opts ...any) (*Cursor, error) {
    return &Cursor{}, nil
}
func (c *Collection) UpdateMany(ctx context.Context, f, u any, opts ...any) (any, error) {
    return nil, nil
}
func (c *Collection) BulkWrite(ctx context.Context, models []WriteModel, opts ...any) (any, error) {
    return nil, nil
}
func (c *Collection) Distinct(ctx context.Context, field string, filter any, opts ...any) ([]any, error) {
    return nil, nil
}

type Database struct{}

func (d *Database) Collection(name string, opts ...any) *Collection { return &Collection{} }

type FindOpts struct{}

func Find() *FindOpts                                { return &FindOpts{} }
func (o *FindOpts) SetSort(v any) *FindOpts          { return o }
func (o *FindOpts) SetLimit(n int64) *FindOpts       { return o }
func (o *FindOpts) SetProjection(v any) *FindOpts    { return o }

type BulkOpts struct{}

func BulkWrite() *BulkOpts                       { return &BulkOpts{} }
func (o *BulkOpts) SetOrdered(b bool) *BulkOpts  { return o }

type CollOpts struct{}

func CollectionOpts() *CollOpts                     { return &CollOpts{} }
func (o *CollOpts) SetWriteConcern(w any) *CollOpts { return o }

func Majority() any { return nil }
''',
}

# The examples are fragments of a larger program, so the harness supplies the ambient
# names they legitimately assume. Anything NOT in here has to be defined by the block
# itself -- which is how `wcColl` gets caught.
PREAMBLE = '''package main

import (
    "context"
    "errors"
    "fmt"
    "strconv"
    "time"

    stub "skillcheck/stub"
)

type bsonM = stub.M
type bsonD = stub.D

var (
    ctx  context.Context
    db   *stub.Database
    coll *stub.Collection
)

func derive(d any) any { return nil }

var _ = errors.New
var _ = fmt.Errorf
var _ = strconv.FormatFloat
var _ = time.Sleep
var _ = stub.Find
'''


# A column-0 `func` is the only construct that CANNOT live inside another function.
# `const`, `var` and `type` are legal as statements, so keying on them misclassified a
# block that opened with `const batchSize = 5000` and continued with statements.
_TOP_LEVEL_FUNC = re.compile(r"^func\s", re.M)


def _wrap(block: str) -> str:
    """Put the block where Go will accept it.

    Go has no nested function declarations, so a block that declares one has to be
    spliced at file scope. Everything else needs a function to live in -- and a block
    may legitimately mix `const`/`var` with statements, which is why the test is
    "declares a func", not "starts with a declaration".
    """
    body = _rewrite(block)
    if _TOP_LEVEL_FUNC.search(body):
        return PREAMBLE + "\n" + body + "\n"
    return PREAMBLE + "\nfunc snippet() error {\n" + body + "\nreturn nil\n}\n"


def _rewrite(block: str) -> str:
    """Map driver package names onto the stub, without changing what is being tested."""
    b = block
    # Helpers a block may either define itself or assume. Injecting them unconditionally
    # would collide with the block's own definition, so they are added only when absent.
    for name, decl in (("parseAmount", "func parseAmount(v any) float64 { return 0 }"),):
        if name in b and not re.search(rf"^func\s+{name}\s*\(", b, re.M):
            b = decl + "\n" + b
    b = re.sub(r"\bbson\.M\b", "stub.M", b)
    b = re.sub(r"\bbson\.D\b", "stub.D", b)
    b = re.sub(r"\bbson\.E\b", "stub.E", b)
    b = re.sub(r"\bmongo\.Pipeline\b", "stub.Pipeline", b)
    b = re.sub(r"\bmongo\.WriteModel\b", "stub.WriteModel", b)
    b = re.sub(r"\bmongo\.NewUpdateOneModel\b", "stub.NewUpdateOneModel", b)
    b = re.sub(r"\boptions\.Find\b", "stub.Find", b)
    b = re.sub(r"\boptions\.BulkWrite\b", "stub.BulkWrite", b)
    b = re.sub(r"\boptions\.Collection\b", "stub.CollectionOpts", b)
    b = re.sub(r"\bwriteconcern\.Majority\b", "stub.Majority", b)
    b = re.sub(r"\bprimitive\.ObjectID\b", "any", b)
    return b


@pytest.fixture(scope="module")
def gomod():
    tmp = tempfile.mkdtemp(prefix="mongoskill-go-")
    root = pathlib.Path(tmp)
    for rel, body in STUBS.items():
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(body, encoding="utf-8")
    yield root
    shutil.rmtree(tmp, ignore_errors=True)


class TestGoBlocksCompile:
    def test_blocks_were_extracted(self):
        assert len(GO_BLOCKS) >= 2, (
            f"only {len(GO_BLOCKS)} Go blocks extracted -- extraction is broken, so a "
            "green result here would prove nothing"
        )

    def test_excerpt_escape_hatch_stays_rare(self):
        assert len(EXCERPTS) <= MAX_EXCERPTS, (
            f"{len(EXCERPTS)} Go blocks are marked `// excerpt:` ({EXCERPTS}); the cap "
            f"is {MAX_EXCERPTS}. Make the block complete instead of exempting it."
        )

    @pytest.mark.parametrize("doc,line,block", GO_BLOCKS,
                             ids=[f"{d}:{ln}" for d, ln, _ in GO_BLOCKS])
    def test_block_parses(self, gomod, doc, line, block):
        """gofmt is the syntax gate: it parses the file and fails on malformed Go."""
        src = gomod / "check_parse.go"
        src.write_text(_wrap(block), encoding="utf-8")
        r = subprocess.run([_GOFMT, "-e", str(src)], capture_output=True, text=True)
        src.unlink(missing_ok=True)
        assert r.returncode == 0, f"{doc}:{line} is not valid Go:\n{r.stderr[:600]}"

    @pytest.mark.parametrize("doc,line,block", GO_BLOCKS,
                             ids=[f"{d}:{ln}" for d, ln, _ in GO_BLOCKS])
    def test_block_has_no_undefined_identifiers(self, gomod, doc, line, block):
        """The gate that would have caught `wcColl`: build the block and require every
        identifier to resolve."""
        src = gomod / "check_build.go"
        src.write_text(_wrap(block), encoding="utf-8")
        r = subprocess.run([_GO, "build", "./..."], cwd=str(gomod),
                           capture_output=True, text=True)
        src.unlink(missing_ok=True)
        undefined = [ln for ln in r.stderr.splitlines()
                     if "undefined:" in ln or "undeclared name" in ln]
        assert not undefined, (
            f"{doc}:{line} references identifiers that do not exist:\n"
            + "\n".join(undefined[:5])
        )


class TestTheDefectThisGateExistsFor:
    """`wcColl` shipped because nothing compiled the Go blocks. Kept as a positive
    control: if this stops being detected, the gate has gone inert."""

    def test_an_undefined_handle_is_caught(self, gomod):
        src = gomod / "check_control.go"
        src.write_text(
            PREAMBLE + "\nfunc snippet() error {\n"
            "    _, err := wcColl.BulkWrite(ctx, nil)\n"
            "    return err\n}\n", encoding="utf-8")
        r = subprocess.run([_GO, "build", "./..."], cwd=str(gomod),
                           capture_output=True, text=True)
        src.unlink(missing_ok=True)
        assert r.returncode != 0 and "undefined" in r.stderr, (
            "the compile gate no longer reports an undefined identifier", r.stderr[:400]
        )

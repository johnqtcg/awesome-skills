#!/usr/bin/env python3
"""Compile every Go snippet embedded in the redis-cache-strategy docs.

Why this exists
---------------
The golden-fixture tests assert on fields of the fixtures themselves, so they
cannot tell whether a Go example in the documentation is even syntactically
valid, let alone whether it calls a real API. A shipped snippet that reads

    var localCache = ristretto.NewCache(&ristretto.Config{...})

is wrong -- NewCache returns (*Cache, error) -- and no amount of fixture
assertion detects it. This gate hands the snippets to the Go compiler, which
is the only authority on the question.

Contract
--------
* Every ```go fenced block in SKILL.md and references/*.md must compile.
* A block that intentionally cannot compile (an anti-example whose defect IS a
  type error) must carry an explicit skip marker on the line before the fence:

      <!-- gocheck:skip <reason> -->

  Skips are counted and reported. test_go_snippets.py asserts the skip count
  and the skipped block inventory, so a skip can never be added silently.

Exit codes
----------
0  all non-skipped snippets compiled
1  at least one snippet failed to compile
3  INCOMPLETE -- toolchain or modules unavailable; NOT a pass
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
DOCS = [SKILL_DIR / "SKILL.md"] + sorted((SKILL_DIR / "references").glob("*.md"))

FENCE_RE = re.compile(r"^```go\s*$")
FENCE_END_RE = re.compile(r"^```\s*$")
SKIP_RE = re.compile(r"<!--\s*gocheck:skip\s+(?P<reason>.+?)\s*-->")

# Identifiers a snippet may reference without declaring. Emitted per snippet,
# minus anything the snippet declares itself (otherwise: duplicate decl).
STUBS: dict[str, str] = {
    "User": "type User struct {\n\tID   string\n\tName string\n}",
    "Entity": "type Entity struct{ ID string }",
    "CachedEntry_marker": "",  # placeholder, never emitted
    "stubDB": """type stubDB struct{}

func (stubDB) QueryUser(ctx context.Context, id string) (*User, error) { return nil, nil }
func (stubDB) UpdateUser(ctx context.Context, u *User) error           { return nil }
func (stubDB) Fetch(ctx context.Context, key string) ([]byte, error)   { return nil, nil }
func (stubDB) Query(id string) []byte                                  { return nil }
func (stubDB) FetchAllIDs() []string                                   { return nil }
func (stubDB) Save(v any) error                                        { return nil }""",
    "db": "var db stubDB",
    "rdb": "var rdb *redis.Client",
    "sfGroup": "var sfGroup singleflight.Group",
    "baseTTL": "var baseTTL = 30 * time.Minute",
    "jitter": "func jitter() time.Duration { return 0 }",
    "jitteredTTL": "func jitteredTTL(base time.Duration) time.Duration { return base }",
    "ErrNotFound": 'var ErrNotFound = errors.New("not found")',
    "ErrCacheUnavailable": 'var ErrCacheUnavailable = errors.New("cache unavailable")',
    "ErrLockHeld": 'var ErrLockHeld = errors.New("lock held")',
    "stubBloom": """type stubBloom struct{}

func (stubBloom) AddAll(ids []string)          {}
func (stubBloom) MayContain(id string) bool    { return true }""",
    "bloom": "var bloom stubBloom",
    "nullMarker": 'const nullMarker = "\\x00null"',
}

# Free variables that statement-fragment snippets reference.
FRAGMENT_VARS = """var (
\tctx                = context.Background()
\tkey                = "k"
\tvalue              = []byte("v")
\tuserData           = []byte("v")
\tsessionData        = []byte("v")
\tnewValue           = []byte("v")
\tfullProfileWithSSN = []byte("v")
\tttl                = time.Minute
\tid                 = "1"
\tstatus             = "active"
\tlimit              = 10
\toffset             = 0
)"""

IMPORTS = """import (
\t"context"
\t"database/sql"
\t"encoding/json"
\t"errors"
\t"fmt"
\t"log/slog"
\t"math/rand"
\t"sync/atomic"
\t"time"

\t"github.com/dgraph-io/ristretto"
\t"github.com/google/uuid"
\t"github.com/redis/go-redis/v9"
\t"golang.org/x/sync/singleflight"
)

var (
\t_ = context.Background
\t_ = sql.ErrNoRows
\t_ = json.Marshal
\t_ = errors.New
\t_ = fmt.Sprintf
\t_ = slog.Info
\t_ = rand.Intn
\t_ = atomic.Uint64{}
\t_ = time.Second
\t_ = ristretto.Config{}
\t_ = uuid.New
\t_ = redis.Nil
\t_ = singleflight.Group{}
)"""

GO_MOD = """module gocheck

go 1.24

require (
\tgithub.com/dgraph-io/ristretto v0.2.0
\tgithub.com/google/uuid v1.6.0
\tgithub.com/redis/go-redis/v9 v9.22.0
\tgolang.org/x/sync v0.22.0
)
"""

TOPLEVEL_RE = re.compile(r"^(func|var|const|type|import|package)\b")
DECL_NAME_RE = re.compile(
    r"^(?:func\s+(?:\([^)]*\)\s*)?(?P<fn>\w+)"
    r"|var\s+(?P<var>\w+)"
    r"|const\s+(?P<const>\w+)"
    r"|type\s+(?P<type>\w+))"
)


class Snippet:
    def __init__(self, doc: Path, line: int, code: str, skip: str | None):
        self.doc = doc
        self.line = line
        self.code = code
        self.skip = skip
        self.pkg = f"s{line}_{doc.stem.replace('-', '_')}"

    @property
    def ref(self) -> str:
        return f"{self.doc.relative_to(SKILL_DIR)}:{self.line}"

    def declared_names(self) -> set[str]:
        names: set[str] = set()
        in_block = False
        for raw in self.code.splitlines():
            if in_block:
                if raw.startswith(")"):
                    in_block = False
                elif raw.startswith("\t") or raw.startswith("    "):
                    m = re.match(r"[\t ]+(\w+)", raw)
                    if m:
                        names.add(m.group(1))
                continue
            if re.match(r"^(var|const|type)\s*\($", raw.strip()):
                in_block = True
                continue
            m = DECL_NAME_RE.match(raw)
            if m:
                names.add(next(v for v in m.groupdict().values() if v))
        return names

    def body(self) -> str:
        """Snippet code with any doc-level import block removed.

        Docs legitimately show `import "golang.org/x/sync/singleflight"` for the
        reader's benefit; the harness supplies its own import block, and Go
        rejects a second one after other declarations.
        """
        lines = self.code.splitlines()
        out: list[str] = []
        i = 0
        while i < len(lines):
            s = lines[i].strip()
            if s.startswith("import ("):
                while i < len(lines) and lines[i].strip() != ")":
                    i += 1
                i += 1
                continue
            if re.match(r'^import\s+(\w+\s+)?"', s):
                i += 1
                continue
            out.append(lines[i])
            i += 1
        return "\n".join(out)

    def is_toplevel(self) -> bool:
        for raw in self.body().splitlines():
            s = raw.strip()
            if not s or s.startswith("//"):
                continue
            return bool(TOPLEVEL_RE.match(s))
        return False

    def render(self) -> str:
        declared = self.declared_names()
        stubs = "\n\n".join(
            body for name, body in STUBS.items() if name not in declared and body
        )
        head = f"package {self.pkg}\n\n{IMPORTS}\n\n{stubs}\n"
        code = self.body()
        if not self.is_toplevel():
            head += f"\n{FRAGMENT_VARS}\n"
            # A fragment often declares a local purely to show the call shape.
            # Go treats an unused local as an error; blank-assign them so the
            # gate reports real defects instead of illustrative style.
            locals_ = sorted(set(re.findall(r"^\s*(\w+)\s*(?::=|,)", code, re.M)))
            uses = "\n".join(
                f"\t_ = {n}" for n in locals_ if n not in ("if", "for", "return", "go", "_")
            )
            return f"{head}\nfunc _fragment() {{\n{code}\n{uses}\n}}\n"
        return f"{head}\n{code}\n"


def extract(doc: Path) -> list[Snippet]:
    lines = doc.read_text(encoding="utf-8").splitlines()
    out: list[Snippet] = []
    i = 0
    while i < len(lines):
        if FENCE_RE.match(lines[i]):
            skip = None
            for back in range(i - 1, max(-1, i - 4), -1):
                m = SKIP_RE.search(lines[back])
                if m:
                    skip = m.group("reason")
                    break
                if lines[back].strip():
                    break
            body: list[str] = []
            j = i + 1
            while j < len(lines) and not FENCE_END_RE.match(lines[j]):
                body.append(lines[j])
                j += 1
            out.append(Snippet(doc, i + 1, "\n".join(body), skip))
            i = j
        i += 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="machine-readable summary")
    ap.add_argument("--keep", action="store_true", help="keep the build dir")
    args = ap.parse_args()

    if shutil.which("go") is None:
        print("INCOMPLETE: go toolchain not found; snippets NOT verified", file=sys.stderr)
        return 3

    snippets: list[Snippet] = []
    for doc in DOCS:
        snippets.extend(extract(doc))

    todo = [s for s in snippets if s.skip is None]
    skipped = [s for s in snippets if s.skip is not None]

    if not todo:
        print("INCOMPLETE: no compilable snippets found -- extractor is broken", file=sys.stderr)
        return 3

    work = Path(tempfile.mkdtemp(prefix="gocheck-"))
    (work / "go.mod").write_text(GO_MOD, encoding="utf-8")
    for s in todo:
        d = work / s.pkg
        d.mkdir(parents=True, exist_ok=True)
        (d / "snippet.go").write_text(s.render(), encoding="utf-8")

    env = dict(os.environ)
    env.pop("GOROOT", None)  # inherited GOROOT breaks a differently-installed toolchain
    env["GOFLAGS"] = "-mod=mod"

    tidy = subprocess.run(
        ["go", "mod", "tidy"], cwd=work, env=env, capture_output=True, text=True
    )
    if tidy.returncode != 0:
        print("INCOMPLETE: `go mod tidy` failed; modules unavailable offline.",
              file=sys.stderr)
        print(tidy.stderr.strip()[:2000], file=sys.stderr)
        return 3

    build = subprocess.run(
        ["go", "build", "./..."], cwd=work, env=env, capture_output=True, text=True
    )

    by_pkg = {s.pkg: s for s in todo}
    failures: list[tuple[str, str]] = []
    for line in build.stderr.splitlines():
        m = re.match(r"^(?:\./)?(s\d+_[\w]+)/snippet\.go:(\d+):(\d+):\s*(.*)$", line.strip())
        if m and m.group(1) in by_pkg:
            failures.append((by_pkg[m.group(1)].ref, m.group(4)))

    ok = build.returncode == 0
    if args.json:
        print(json.dumps({
            "compiled": len(todo),
            "skipped": [{"ref": s.ref, "reason": s.skip} for s in skipped],
            "failures": [{"ref": r, "error": e} for r, e in failures],
            "ok": ok,
        }, indent=2))
    else:
        print(f"go snippets: {len(todo)} compiled, {len(skipped)} skipped")
        for s in skipped:
            print(f"  SKIP {s.ref}: {s.skip}")
        if not ok:
            print("\nFAILURES:")
            for ref, err in failures:
                print(f"  {ref}: {err}")
            if not failures:
                print(build.stderr.strip()[:4000])

    if not args.keep:
        shutil.rmtree(work, ignore_errors=True)
    else:
        print(f"build dir: {work}")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

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

Environment failures are not compile failures
---------------------------------------------
`go build` exits non-zero for reasons that have nothing to do with the code --
a read-only build cache in a sandbox produces

    go: failed to trim cache: open .../trim.txt: operation not permitted

with every package built successfully. Reporting that as "a snippet is broken"
sends the reader hunting a defect that does not exist; reporting it as a pass
would be worse -- and in a mutation sweep, a gate that returns 1 unconditionally
credits itself with every kill.

Three layers, in order of how much they are relied on:

1. **A private, persistent GOCACHE, always.** Not a fallback. The cache trim is
   periodic, not per-invocation: Go records the last trim in `trim.txt` and only
   retries after an interval, so a cheap probe can succeed while the very next
   longer command trips the same unwritable cache. A conditional fallback
   therefore fires only sometimes, which is worse than never -- it makes the
   gate intermittently INCOMPLETE for a reason nobody can reproduce. Owning the
   cache removes the cause instead of detecting it. The directory is stable
   across runs, so it stays warm.
2. **A positive control.** A known-good package is compiled before the snippets.
   If that fails, nothing here is measuring snippets and the gate says so.
3. **Diagnostic-based classification.** A non-zero exit with no `file:line:col:`
   diagnostic anywhere is reported INCOMPLETE (exit 3), never as a broken
   snippet.
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


DIAG_RE = re.compile(r"^(?:\./)?[\w./-]+\.go:\d+:\d+:\s", re.M)


# Stable so the cache stays warm between runs; under the sandbox-writable temp
# dir so it exists whether or not $HOME/Library/Caches is reachable.
PRIVATE_GOCACHE = Path(tempfile.gettempdir()) / "rcs-gocheck-gocache"


def build_env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("GOROOT", None)  # inherited GOROOT breaks a differently-installed toolchain
    env["GOFLAGS"] = "-mod=mod"
    # Unconditional, not a fallback -- see the module docstring. GOMODCACHE is
    # deliberately left alone: module downloads should stay shared, and it is the
    # *build* cache whose trim step needs write access.
    PRIVATE_GOCACHE.mkdir(parents=True, exist_ok=True)
    env["GOCACHE"] = str(PRIVATE_GOCACHE)
    return env


def preflight(env: dict[str, str]) -> tuple[bool, str]:
    """Compile a known-good package that exercises the real dependency path.

    The probe imports one of the same modules the snippets do, so it covers
    `go mod tidy` and the module cache -- not just the compiler. An earlier
    version compiled a dependency-free package, which could succeed while the
    dependency-resolving build that followed failed for an environment reason,
    leaving exactly the ambiguity the probe exists to remove.
    """
    probe = Path(tempfile.mkdtemp(prefix="gocheck-probe-"))
    try:
        (probe / "go.mod").write_text(GO_MOD, encoding="utf-8")
        (probe / "p.go").write_text(
            'package probe\n\nimport "github.com/redis/go-redis/v9"\n\n'
            "func F() error { return redis.Nil }\n",
            encoding="utf-8")
        tidy = subprocess.run(["go", "mod", "tidy"], cwd=probe, env=env,
                              capture_output=True, text=True)
        if tidy.returncode != 0:
            return False, "`go mod tidy` failed on a known-good package:\n" + tidy.stderr.strip()
        r = subprocess.run(["go", "build", "./..."], cwd=probe, env=env,
                           capture_output=True, text=True)
        if r.returncode == 0:
            return True, ""
        if DIAG_RE.search(r.stderr):
            return False, "the toolchain rejects a known-good package:\n" + r.stderr.strip()
        return False, r.stderr.strip() or f"exit {r.returncode} with no diagnostic"
    finally:
        shutil.rmtree(probe, ignore_errors=True)


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

    env = build_env()
    usable, detail = preflight(env)   # mutates env with a private GOCACHE if needed
    if not usable:
        print("INCOMPLETE: the Go toolchain cannot build a known-good package; "
              "snippets NOT verified.", file=sys.stderr)
        print(detail[:2000], file=sys.stderr)
        return 3
    if detail:
        print(f"note: {detail}", file=sys.stderr)

    work = Path(tempfile.mkdtemp(prefix="gocheck-"))
    (work / "go.mod").write_text(GO_MOD, encoding="utf-8")
    for s in todo:
        d = work / s.pkg
        d.mkdir(parents=True, exist_ok=True)
        (d / "snippet.go").write_text(s.render(), encoding="utf-8")

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

    # Non-zero exit with no compiler diagnostic anywhere is an environment
    # problem that survived preflight -- report INCOMPLETE, never a snippet
    # failure. A diagnostic we could not attribute to a package is still a real
    # failure and falls through to exit 1 with the raw stderr.
    if build.returncode != 0 and not DIAG_RE.search(build.stderr):
        print("INCOMPLETE: `go build` failed with no compiler diagnostic; "
              "snippets NOT verified.", file=sys.stderr)
        print(build.stderr.strip()[:2000], file=sys.stderr)
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)
        return 3

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

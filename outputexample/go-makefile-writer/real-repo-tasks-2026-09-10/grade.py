#!/usr/bin/env python3
"""Grade the real-repo task runs. Every check runs a command and reads its
result; nothing is graded by reading the Makefile for a keyword.

Scoring is per assertion, and each assertion names the failure it is meant to
catch, so a pass is evidence of something rather than a tick.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SP = Path("/private/tmp/claude-503/-Users-john-awesome-skills/"
          "27bf3b35-2cf3-4fdb-be74-37049f8999eb/scratchpad")
RUNS = SP / "runs"

# NO GOFLAGS here. `-mod=mod` is REJECTED in workspace mode ("-mod may only be
# set to readonly or vendor when in workspace mode"), which made `go list -m`
# fail, the module list come back empty, and the monorepo run look like a skill
# failure. It was the harness. Worth noting what the generated Makefile did with
# it, though: the empty-list guard fired and the target failed loudly with a
# diagnostic instead of looping zero times and reporting success — the exact
# accident that guard exists for, arriving by accident.
ENV = {**os.environ,
       "GOCACHE": str(SP / ".gc"),
       "GOMODCACHE": str(SP / ".gm")}


def code(repo: Path) -> str:
    """The Makefile with comments stripped.

    Grading the raw text scores the agent's own explanation against it: the
    library run wrote "there is deliberately no -ldflags here" and a substring
    check read that as -ldflags being present.
    """
    mk = repo / "Makefile"
    if not mk.exists():
        return ""
    out = []
    for line in mk.read_text().splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        out.append(line.split(" #", 1)[0] if not line.startswith("\t") else line)
    return "\n".join(out)


def make(repo: Path, *args: str, timeout: int = 300):
    return subprocess.run(["make", *args], cwd=repo, env=ENV,
                          capture_output=True, text=True, timeout=timeout)


def targets(repo: Path) -> set[str]:
    """Real target list from make itself, not from grepping the file."""
    p = subprocess.run(["make", "-qp"], cwd=repo, env=ENV,
                       capture_output=True, text=True, timeout=120)
    found = set()
    for line in p.stdout.splitlines():
        m = re.match(r"^([A-Za-z0-9_.\-/]+):(?!=)", line)
        if m and not m.group(1).startswith("."):
            found.add(m.group(1))
    return found


class Grade:
    def __init__(self, name: str):
        self.name = name
        self.rows: list[tuple[bool, str, str]] = []

    def check(self, ok: bool, what: str, detail: str = ""):
        self.rows.append((bool(ok), what, detail))

    @property
    def passed(self):
        return sum(1 for ok, _, _ in self.rows if ok)

    def report(self):
        print(f"\n### {self.name}  —  {self.passed}/{len(self.rows)}")
        for ok, what, detail in self.rows:
            mark = "PASS" if ok else "FAIL"
            print(f"  [{mark}] {what}")
            if detail and not ok:
                print(f"         {detail[:300]}")


def error_propagation(g: Grade, repo: Path, tg: set[str]):
    """Does the GENERATED Makefile obey the skill's [C] rules?

    This is the dimension the 2026-09 hardening was about, and the one the
    rest of the assertions do not touch: every other check here is satisfied
    by a Makefile that reports success on a broken tree.
    """
    if "fmt-check" not in tg:
        g.check(False, "has a fmt-check gate")
        return
    g.check(make(repo, "fmt-check").returncode == 0,
            "fmt-check passes on the clean tree (no false alarm)")
    broken = repo / "zz_broken.go"
    broken.write_text("package broken\nfunc x( { }\n")
    try:
        r = make(repo, "fmt-check")
        g.check(r.returncode != 0,
                "fmt-check FAILS on a file that does not parse "
                "(gofmt exits 2 with empty stdout — an output-only check passes it)",
                (r.stdout + r.stderr)[-200:])
    finally:
        broken.unlink()


def common(g: Grade, repo: Path):
    mk = repo / "Makefile"
    g.check(mk.exists(), "a Makefile was written")
    if not mk.exists():
        return set()
    p = make(repo, "-n", "help")
    g.check(p.returncode == 0, "the Makefile parses and `help` resolves",
            p.stderr)
    h = make(repo, "help")
    listed = len([l for l in h.stdout.splitlines() if l.strip()])
    g.check(h.returncode == 0 and listed >= 5,
            f"`make help` runs and lists targets (listed {listed})", h.stderr)
    t = make(repo, "test")
    g.check(t.returncode == 0, "`make test` passes on the real code",
            (t.stdout + t.stderr)[-300:])
    tg = targets(repo)
    g.check(".PHONY" in mk.read_text(), "declares .PHONY")
    return tg


def grade_single(repo: Path) -> Grade:
    g = Grade("single — one module, root package main")
    tg = common(g, repo)
    error_propagation(g, repo, tg)
    build = {t for t in tg if t.startswith("build")}
    g.check(bool(build), f"has a build target ({sorted(build)})")
    ran = False
    for t in sorted(build):
        if make(repo, t).returncode == 0:
            ran = True
            break
    g.check(ran, "a build target actually builds")
    # version injection must reach the artifact, not just the Makefile
    bins = [p for p in repo.rglob("*") if p.is_file() and os.access(p, os.X_OK)
            and p.suffix == "" and "/.git" not in str(p) and ".claude" not in str(p)
            and p.name not in ("Makefile",)]
    stamped = False
    for b in bins:
        try:
            out = subprocess.run([str(b)], cwd=repo, capture_output=True,
                                 text=True, timeout=30)
            if out.stdout.strip() and "dev" not in out.stdout.split()[-1]:
                stamped = True
                break
        except Exception:
            pass
    g.check(stamped, "version injection reached the BINARY (not just the Makefile)",
            f"binaries tried: {[b.name for b in bins]}")
    return g


def grade_library(repo: Path) -> Grade:
    g = Grade("library — no package main anywhere")
    tg = common(g, repo)
    error_propagation(g, repo, tg)
    bad = {t for t in tg if t.startswith(("build-", "run-"))} - {"build-all-platforms"}
    g.check(not bad, f"no build-*/run-* targets invented for a library ({sorted(bad)})")
    text = code(repo)
    g.check("-ldflags" not in text,
            "no -ldflags version injection (there is no binary to inject into)")
    g.check("cmd/internal" not in text,
            "the decoy cmd/internal/main.go (package internal) was NOT treated as a program")
    return g


def grade_cgo(repo: Path) -> Grade:
    g = Grade("cgo — import \"C\" in the only program")
    tg = common(g, repo)
    error_propagation(g, repo, tg)
    text = code(repo)
    g.check("CGO_ENABLED=0" not in text,
            "did NOT set CGO_ENABLED=0 (it would break the cgo build)",
            "CGO_ENABLED=0 present")
    cross = {t for t in tg if "linux" in t}
    g.check(bool(cross), f"has a linux target as asked ({sorted(cross)})")
    build = sorted(t for t in tg if t.startswith("build") and "linux" not in t)
    ok = any(make(repo, t).returncode == 0 for t in build) if build else False
    g.check(ok, f"a native build target actually builds the cgo program ({build})")
    return g


def grade_monorepo(repo: Path) -> Grade:
    g = Grade("monorepo — go.work, 2 modules, entry.go program, decoy main.go")
    tg = common(g, repo)
    error_propagation(g, repo, tg)
    # Graded by ARTIFACTS, not by target name or Makefile text. Two earlier
    # versions of these assertions failed the no-skill arm for naming its
    # aggregate `build` instead of `build-all`, and for discovering packages at
    # runtime via a `build/%` pattern rule instead of writing `cmd/api` in the
    # file. Both are fine designs; the assertions were measuring my taste.
    built = set()
    for t in sorted(x for x in tg if x.startswith("build") and "%" not in x):
        if make(repo, t).returncode == 0:
            built |= {f.name for f in repo.rglob("*")
                      if f.is_file() and os.access(f, os.X_OK) and f.suffix == ""
                      and "/.git" not in str(f) and ".claude" not in str(f)}
    g.check("api" in built,
            f"builds the cmd/api program, whose file is entry.go not main.go ({sorted(built)})")
    g.check("worker" in built, f"builds the cmd/worker program ({sorted(built)})")
    # Graded by BEHAVIOUR, not by name: this run called the aggregate `test`
    # with per-module `test-svc-api` / `test-pkglib` beside it, which is a
    # perfectly good design that an assertion demanding `test-all` marked wrong.
    best, hit = None, 0
    for t in sorted(x for x in tg if x.startswith("test")):
        r = make(repo, t)
        if r.returncode != 0:
            continue
        seen = ("svc-api" in r.stdout) + ("pkglib" in r.stdout)
        if seen > hit:
            best, hit = t, seen
    g.check(hit >= 2,
            f"some test target runs BOTH modules (`make {best}`)" if best
            else "some test target runs BOTH modules")
    g.check("queue" not in built,
            f"did NOT build internal/queue/main.go (package queue) as a program ({sorted(built)})")
    return g


def grade_refactor(repo: Path) -> Grade:
    g = Grade("refactor — existing Makefile whose target names CI depends on")
    tg = common(g, repo)
    error_propagation(g, repo, tg)
    for t in ("unit", "vet", "compile"):
        p = make(repo, t)
        g.check(p.returncode == 0, f"CI target `make {t}` still works",
                (p.stdout + p.stderr)[-300:])
    return g


GRADERS = {"single": grade_single, "library": grade_library, "cgoproj": grade_cgo,
           "monorepo": grade_monorepo, "refactor": grade_refactor}
# The no-skill arm is graded by the SAME function on the SAME assertions.
for _n in list(GRADERS):
    GRADERS[f"{_n}-baseline"] = GRADERS[_n]


def main():
    names = sys.argv[1:] or list(GRADERS)
    total_p = total_n = 0
    for name in names:
        repo = RUNS / name
        if not repo.exists():
            print(f"\n### {name} — NOT RUN")
            continue
        g = GRADERS[name](repo)
        g.report()
        total_p += g.passed
        total_n += len(g.rows)
        meta = RUNS / f"{name}.json"
        if meta.exists() and meta.stat().st_size:
            d = json.load(open(meta))
            print(f"  (turns {d.get('num_turns')}, "
                  f"${round(d.get('total_cost_usd') or 0, 2)}, "
                  f"{round((d.get('duration_ms') or 0)/1000)}s)")
    print(f"\n== {total_p}/{total_n} assertions passed ==")


if __name__ == "__main__":
    main()

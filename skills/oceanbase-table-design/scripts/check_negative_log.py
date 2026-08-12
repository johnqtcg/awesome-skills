#!/usr/bin/env python3
"""Per-case verdict for negative-example logs.

Why we can't just do `grep -c ERROR | compare totals`:
  A total-count comparison has two loopholes --
    1. a negative case unexpectedly **succeeds** while an unrelated error pops
       up elsewhere; the total still matches, so it gets masked as a "pass";
    2. when comparing with `-lt` (not fewer than), an extra unrelated error
       directly breaks the assertion.
  So instead this script does **per-case windowed judging**: a
  `SELECT '@@CASE:<id>' AS marker;` is inserted before every case in the
  negative-example SQL, and this script requires:
    * at least 1 error between each marker and the next one;
    * no errors are allowed before the first marker (that means the
      environment or a preceding statement is broken);
    * the set of markers found in the log must exactly match the expected
      case set.

Usage:
    python3 check_negative_log.py <log> --expect N1,N2,N3
    python3 check_negative_log.py <log> --expect-from <negative-example SQL>   # auto-extract from the SQL
    python3 check_negative_log.py --self-test                       # self-test of the judging logic (10 items)
Exit code: 0 = every negative case errored as expected, 1 = a case unexpectedly succeeded or the environment is abnormal
"""
import os
import re
import sys

MARKER = re.compile(r"@@CASE:([A-Za-z0-9_]+)")
# an obclient error line looks like: ERROR 1234 (HY000) at line 5: ...
ERROR_LINE = re.compile(r"^\s*ERROR[\s\-]", re.I)


def extract_expected(sql_path):
    with open(sql_path, encoding="utf-8", errors="replace") as f:
        return MARKER.findall(f.read())


def parse(log_path):
    """Return (preamble_errors, [(case_id, error_count)]), preserving order of appearance."""
    pre, blocks, cur = [], [], None
    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = MARKER.search(line)
            if m:
                cur = [m.group(1), 0]
                blocks.append(cur)
                continue
            if ERROR_LINE.match(line):
                if cur is None:
                    pre.append(line.rstrip())
                else:
                    cur[1] += 1
    return pre, [(c, n) for c, n in blocks]


def self_test():
    """Verify the judging logic itself using synthetic logs. The verifier must also be continuously tested."""
    import tempfile
    passed = 0

    def run(content, expect, want_ok, label):
        nonlocal passed
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False,
                                         encoding="utf-8") as f:
            f.write(content)
            path = f.name
        try:
            pre, blocks = parse(path)
            seen = [c for c, _ in blocks]
            silent = [c for c, n in blocks if n == 0]
            missing = [c for c in expect if c not in seen]
            extra = [c for c in seen if c not in expect]
            ok = not (pre or silent or missing or extra)
            assert ok == want_ok, (
                f"{label}: expected ok={want_ok}, got ok={ok} "
                f"(pre={len(pre)} silent={silent} missing={missing} extra={extra})")
            passed += 1
        finally:
            os.unlink(path)

    ERR = "ERROR 1503 (HY000) at line 5: A PRIMARY KEY must include all columns\n"
    OK_ = "Query OK, 0 rows affected\n"

    # 1) Normal: each case errors individually
    run(f"@@CASE:N1\n{ERR}@@CASE:N2\n{ERR}", ["N1", "N2"], True, "all errored as expected")

    # 2) A negative case unexpectedly succeeds (the primary reason this judge exists)
    run(f"@@CASE:N1\n{ERR}@@CASE:N2\n{OK_}", ["N1", "N2"], False, "N2 unexpectedly succeeded")

    # 3) Totals match but the distribution is wrong: N1 has two errors, N2 has zero
    #    -- comparing totals with grep -c would misjudge this as a pass;
    #       per-case judging must catch it
    run(f"@@CASE:N1\n{ERR}{ERR}@@CASE:N2\n{OK_}", ["N1", "N2"], False,
        "totals equal but N2 did not error")

    # 4) There is an error before the marker (a preceding statement / environment is broken)
    run(f"{ERR}@@CASE:N1\n{ERR}", ["N1"], False, "preamble has an error")

    # 5) A case's marker never appears (not executed)
    run(f"@@CASE:N1\n{ERR}", ["N1", "N2"], False, "N2 marker missing")

    # 6) An unexpected marker appears
    run(f"@@CASE:N1\n{ERR}@@CASE:N9\n{ERR}", ["N1"], False, "unexpected marker N9 appeared")

    # 7) An unrelated extra error does not affect the verdict (as long as each case has its own error)
    run(f"@@CASE:N1\n{ERR}ERROR 9999 (HY000): unrelated noise\n@@CASE:N2\n{ERR}",
        ["N1", "N2"], True, "an unrelated extra error does not cause a false judgment")

    # 8) Error-line recognition: the ERROR-followed-by-hyphen variant
    run("@@CASE:N1\nERROR-1234: something\n", ["N1"], True, "ERROR- variant is recognized")

    # 9) A non-error line must not be treated as an error (ordinary output containing the word "error")
    run("@@CASE:N1\n| my_error_col |\nQuery OK\n", ["N1"], False,
        "the word error inside ordinary output does not count as an error")

    # 10) --expect-from can extract markers from SQL
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False,
                                     encoding="utf-8") as f:
        f.write("SELECT '@@CASE:N1' AS marker;\nCREATE TABLE x(a int);\n"
                "SELECT '@@CASE:N2' AS marker;\n")
        sqlp = f.name
    try:
        assert extract_expected(sqlp) == ["N1", "N2"], extract_expected(sqlp)
        passed += 1
    finally:
        os.unlink(sqlp)

    print(f"check_negative_log self-test: {passed}/{passed} passed")
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 0
    if sys.argv[1] == "--self-test":
        return self_test()
    log = sys.argv[1]
    expected = []
    if "--expect" in sys.argv:
        expected = [x for x in sys.argv[sys.argv.index("--expect") + 1].split(",") if x]
    elif "--expect-from" in sys.argv:
        expected = extract_expected(sys.argv[sys.argv.index("--expect-from") + 1])
    else:
        print("must provide --expect or --expect-from", file=sys.stderr)
        return 2

    pre, blocks = parse(log)
    seen = [c for c, _ in blocks]
    problems = []

    if pre:
        problems.append(
            f"there were {len(pre)} error(s) before the first case marker "
            f"(preceding statement or environment issue):\n"
            + "\n".join(f"      {x[:140]}" for x in pre[:5]))

    missing = [c for c in expected if c not in seen]
    extra = [c for c in seen if c not in expected]
    if missing:
        problems.append(f"the log is missing markers for these cases (not executed?): {missing}")
    if extra:
        problems.append(f"unexpected case markers appeared in the log: {extra}")

    silent = [c for c, n in blocks if n == 0]
    if silent:
        problems.append(
            f"these negative cases **did not error**, i.e. they succeeded on the target version: {silent}\n"
            f"      -> this means the corresponding L0 rule in references/ no longer matches "
            f"this version's behavior; the rule must be fixed, not the case")

    width = max([len(c) for c in seen] + [6])
    print(f"{'case'.ljust(width)}  errors  verdict")
    for c, n in blocks:
        print(f"{c.ljust(width)}  {n:>6}  {'OK (errored as expected)' if n else 'FAILED (unexpectedly succeeded)'}")
    print(f"\n{len(blocks)} case(s), {sum(1 for _, n in blocks if n)} errored as expected, "
          f"{len(silent)} unexpectedly succeeded, {len(pre)} error(s) before the first marker")

    for p in problems:
        print(f"[error] {p}")
    if problems:
        print("check_negative_log: FAILED")
        return 1
    print("check_negative_log: OK (every negative case was rejected as expected)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

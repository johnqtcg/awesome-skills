#!/usr/bin/env python3
"""Materialise eval fixtures to disk: one directory per fixture, holding the log
file the model will read and the prompt it will be given."""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fixtures import FIXTURES  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dest", required=True, type=pathlib.Path)
    args = ap.parse_args()

    for fx in FIXTURES:
        d = args.dest / fx["id"]
        d.mkdir(parents=True, exist_ok=True)
        log_path = d / fx["log_name"]
        log_path.write_text(fx["log"], encoding="utf-8")
        (d / "prompt.txt").write_text(
            fx["prompt"].format(path=fx["log_name"]), encoding="utf-8")
        print(f"{fx['id']}: {len(fx['log'].splitlines())} log lines -> {log_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

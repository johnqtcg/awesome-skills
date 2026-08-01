#!/usr/bin/env python3
"""Stand-in for local_transcript.py, used to exercise the quality evaluator.

The evaluator's orchestration — argv construction, aggregation, regression
detection, the summary — is the part that actually runs, and it cannot be
covered by testing the CER function. This stub makes it runnable without audio,
an ASR model or an LLM: it writes a canned transcript chosen by mode and by
whether proofreading was disabled.

It deliberately accepts exactly the flags the real transcriber accepts, so an
evaluator that builds a command the real script would reject also fails here.
"""

import argparse
import json
import pathlib

parser = argparse.ArgumentParser()
parser.add_argument("input")
parser.add_argument("--mode", default="balanced")
parser.add_argument("--format", default="txt")
parser.add_argument("--output", required=True)
parser.add_argument("--no-llm-proofread", action="store_true")
parser.add_argument("--language", default=None)
parser.add_argument("--backend", default=None)
parser.add_argument("--llm-backend", default=None)
parser.add_argument("--llm-model", default=None)
args = parser.parse_args()

table = pathlib.Path(args.input).with_suffix(".stub.json")
canned = json.loads(table.read_text(encoding="utf-8"))
key = f"{args.mode}:{'raw' if args.no_llm_proofread else 'clean'}"
pathlib.Path(args.output).write_text(canned[key], encoding="utf-8")

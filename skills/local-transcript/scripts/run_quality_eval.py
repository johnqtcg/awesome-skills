#!/usr/bin/env python3
"""Measure transcription quality against a hand-checked reference corpus.

Everything in `scripts/tests/` proves the wiring: that `accurate` really asks for
beam search, that a changed configuration really gets a different cache key, that
a hallucinating chunk is really rejected. None of it proves the thing a user
cares about — that `accurate` transcribes *better* than `balanced`, or that LLM
proofreading removes more errors than it introduces.

This does, given audio and a human reference. Per mode it reports:

* CER against the reference — character error rate, the standard metric for
  Chinese ASR, since Chinese has no word boundaries to align on. Aggregated
  across samples as total edit distance over total reference length, so a long
  file cannot be outvoted by a short one.
* proper-noun recall for terms the manifest marks as must-get-right, scored
  before and after proofreading. A pass that lowers CER while corrupting names
  is a regression, and is reported as one.
* errors the proofreading pass *introduced*, by scoring two texts separately.

The comparison is **baseline vs proofread**, not raw-ASR vs proofread. The
baseline is produced with `--no-llm-proofread`, which still applies OpenCC
conversion, deterministic replacements, punctuation normalisation and
re-segmentation — it is the pipeline minus the LLM, which is the increment worth
isolating. Pass `--true-raw` to score the untouched ASR output instead, using the
transcriber's `--emit-raw-asr`.

No corpus ships with the skill: audio cannot be committed, and a reference
transcript is only meaningful next to its audio. Point `--corpus` at your own.

Corpus layout:

    corpus/
      manifest.json      [{"audio": "a.m4a", "reference": "a.txt",
                          "proper_nouns": ["哈里斯"], "language": "zh"}]
      a.m4a
      a.txt

Exit codes:
  0  every scenario met its thresholds
  1  a threshold was missed — a real result about quality
  2  setup failure (no corpus, missing audio, transcriber unavailable). Never
     report this as a quality result: nothing was measured.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "local_transcript.py"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def normalize_for_scoring(text: str) -> str:
    """Strip what a transcript reader would not count as an error.

    Punctuation and whitespace are reinserted by the cleaning pass and differ
    between any two humans; scoring them would drown the signal that matters.
    """
    kept = []
    for char in unicodedata.normalize("NFKC", text):
        category = unicodedata.category(char)
        if category.startswith("P") or category.startswith("Z") or char.isspace():
            continue
        kept.append(char)
    return "".join(kept)


def edit_distance(a: str, b: str) -> int:
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + (ca != cb),
            ))
        previous = current
    return previous[-1]


def score_pair(reference: str, hypothesis: str) -> tuple[int, int]:
    """(edit distance, reference length) on normalized text.

    Returned as components rather than a ratio so several samples can be
    aggregated by total distance over total length — averaging per-file CERs
    would weight a ten-second clip the same as a one-hour lecture.
    """
    ref = normalize_for_scoring(reference)
    hyp = normalize_for_scoring(hypothesis)
    return edit_distance(ref, hyp), len(ref)


def character_error_rate(reference: str, hypothesis: str) -> float:
    distance, length = score_pair(reference, hypothesis)
    if not length:
        return 0.0 if not distance else 1.0
    return distance / length


def matched_reference_positions(reference: str, hypothesis: str) -> set[int]:
    """Reference character indices the hypothesis got right, via alignment."""
    import difflib

    matcher = difflib.SequenceMatcher(None, reference, hypothesis, autojunk=False)
    matched: set[int] = set()
    for block in matcher.get_matching_blocks():
        matched.update(range(block.a, block.a + block.size))
    return matched


def error_delta(reference: str, baseline: str, cleaned: str) -> tuple[int, int]:
    """(fixed, introduced) character counts attributable to proofreading.

    Net CER cannot see a pass that repairs one error and creates another: the
    two cancel and the number is unchanged. Aligning each hypothesis to the
    reference separately gives the set of reference positions each got right, so
    a position correct before and wrong after is an *introduced* error however
    the totals move.
    """
    ref = normalize_for_scoring(reference)
    base_ok = matched_reference_positions(ref, normalize_for_scoring(baseline))
    clean_ok = matched_reference_positions(ref, normalize_for_scoring(cleaned))
    return len(clean_ok - base_ok), len(base_ok - clean_ok)


def proper_noun_recall(reference_terms: list[str], hypothesis: str) -> tuple[int, int]:
    """(found, total) — a term the transcript never spells correctly is a miss."""
    if not reference_terms:
        return 0, 0
    found = sum(1 for term in reference_terms if term in hypothesis)
    return found, len(reference_terms)


def aggregate_by_mode(rows: list[dict]) -> dict[str, dict[str, float]]:
    """Length-weighted CER per mode across every sample.

    A dict comprehension keyed on mode keeps only the last row per mode, so the
    headline comparison described the final file in the corpus rather than the
    corpus.
    """
    totals: dict[str, dict[str, float]] = {}
    for row in rows:
        bucket = totals.setdefault(
            row["mode"], {"dist_baseline": 0, "dist_clean": 0, "ref_len": 0, "samples": 0}
        )
        bucket["dist_baseline"] += row["dist_baseline"]
        bucket["dist_clean"] += row["dist_clean"]
        bucket["ref_len"] += row["ref_len"]
        bucket["samples"] += 1
    for bucket in totals.values():
        length = bucket["ref_len"] or 1
        bucket["cer_baseline"] = bucket["dist_baseline"] / length
        bucket["cer_cleaned"] = bucket["dist_clean"] / length
    return totals


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def build_transcribe_command(
    transcriber: Path,
    audio: Path,
    mode: str,
    out: Path,
    extra: list[str],
    use_uv: bool,
    language: str | None = None,
    passthrough: list[str] | None = None,
) -> list[str]:
    """Argv for one transcription run.

    `uv run` is preferred because the transcriber declares its dependencies in a
    PEP 723 header; invoking it with a bare interpreter ignores that block and
    fails on a clean machine for reasons that look like ASR problems.
    """
    runner = ["uv", "run", str(transcriber)] if use_uv else [sys.executable, str(transcriber)]
    return [
        *runner, str(audio),
        "--mode", mode,
        "--format", "txt",          # the transcriber's flag is singular
        "--output", str(out),
        # The manifest's `language` used to be decorative: it was documented but
        # never forwarded, so every sample was auto-detected and a corpus could
        # not pin the language it claimed to.
        *(["--language", language] if language else []),
        *(passthrough or []),
        *extra,
    ]


def run_transcription(
    transcriber: Path,
    audio: Path,
    mode: str,
    extra: list[str],
    workdir: Path,
    use_uv: bool,
    language: str | None = None,
    passthrough: list[str] | None = None,
) -> str:
    out = workdir / f"{audio.stem}.{mode}.{'baseline' if extra else 'clean'}.txt"
    cmd = build_transcribe_command(
        transcriber, audio, mode, out, extra, use_uv, language, passthrough
    )
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists():
        raise RuntimeError(
            f"transcription failed for {audio.name} in {mode} mode\n"
            f"  command: {' '.join(cmd)}\n"
            f"  stdout: {proc.stdout[-600:]}\n  stderr: {proc.stderr[-600:]}"
        )
    return out.read_text(encoding="utf-8")


def evaluate(
    corpus: Path,
    modes: list[str],
    workdir: Path,
    transcriber: Path,
    use_uv: bool,
    passthrough: list[str] | None = None,
    true_raw: bool = False,
) -> list[dict]:
    entries = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    if not entries:
        raise RuntimeError("manifest.json is empty")
    rows = []
    for entry in entries:
        audio = corpus / entry["audio"]
        if not audio.exists():
            raise RuntimeError(f"manifest references missing audio: {audio}")
        reference_path = corpus / entry["reference"]
        if not reference_path.exists():
            raise RuntimeError(f"manifest references missing transcript: {reference_path}")
        reference = reference_path.read_text(encoding="utf-8")
        # An empty reference divides by zero and previously scored CER 0.0 —
        # a corrupt corpus would have exited 0 with a perfect result.
        if not normalize_for_scoring(reference):
            raise RuntimeError(
                f"reference {reference_path.name} is empty after normalisation; "
                "a corpus cannot be scored against nothing"
            )
        terms = entry.get("proper_nouns", [])
        language = entry.get("language")
        for mode in modes:
            cleaned = run_transcription(
                transcriber, audio, mode, [], workdir, use_uv, language, passthrough
            )
            if true_raw:
                raw_path = workdir / f"{audio.stem}.{mode}.trueraw.txt"
                run_transcription(
                    transcriber, audio, mode,
                    ["--no-llm-proofread", "--emit-raw-asr", str(raw_path)],
                    workdir, use_uv, language, passthrough,
                )
                if not raw_path.exists():
                    raise RuntimeError(
                        f"--true-raw requested but the transcriber wrote no raw ASR "
                        f"file for {audio.name}"
                    )
                raw = raw_path.read_text(encoding="utf-8")
            else:
                raw = run_transcription(
                    transcriber, audio, mode, ["--no-llm-proofread"], workdir, use_uv,
                    language, passthrough,
                )
            dist_clean, ref_len = score_pair(reference, cleaned)
            dist_baseline, _ = score_pair(reference, raw)
            fixed, introduced = error_delta(reference, raw, cleaned)
            found, total = proper_noun_recall(terms, cleaned)
            baseline_found, _ = proper_noun_recall(terms, raw)
            rows.append({
                "audio": entry["audio"],
                "mode": mode,
                "dist_baseline": dist_baseline,
                "dist_clean": dist_clean,
                "ref_len": ref_len,
                "cer_baseline": dist_baseline / ref_len if ref_len else 0.0,
                "cer_cleaned": dist_clean / ref_len if ref_len else 0.0,
                "nouns_found": found,
                "nouns_found_baseline": baseline_found,
                "nouns_total": total,
                "chars_fixed": fixed,
                "chars_introduced": introduced,
            })
    return rows


def judge(rows: list[dict], max_cer: float) -> list[tuple[dict, list[str]]]:
    """One verdict per scenario-mode, with every reason it failed.

    Counting rule hits instead meant a row breaching two thresholds subtracted
    two from the total, which could print a negative pass count.
    """
    verdicts = []
    for row in rows:
        reasons = []
        if row["cer_cleaned"] > max_cer:
            reasons.append(f"CER {row['cer_cleaned']:.4f} > {max_cer}")
        if row["cer_cleaned"] > row["cer_baseline"]:
            reasons.append(
                f"proofreading raised CER ({row['cer_baseline']:.4f} -> {row['cer_cleaned']:.4f})"
            )
        introduced = row.get("chars_introduced", 0)
        fixed = row.get("chars_fixed", 0)
        # Net CER hides a pass that repairs one character and breaks another.
        if introduced and introduced >= fixed:
            reasons.append(
                f"proofreading introduced {introduced} character error(s) "
                f"while fixing {fixed}"
            )
        if row["nouns_total"] and row["nouns_found"] < row["nouns_found_baseline"]:
            reasons.append(
                f"proofreading lost proper nouns "
                f"({row['nouns_found_baseline']}/{row['nouns_total']} -> "
                f"{row['nouns_found']}/{row['nouns_total']})"
            )
        verdicts.append((row, reasons))
    return verdicts


def report(verdicts: list[tuple[dict, list[str]]], totals: dict) -> int:
    header = (
        f"{'audio':<22}{'mode':<11}{'CER base':>9}{'CER clean':>11}"
        f"{'nouns base':>11}{'nouns clean':>13}{'fixed':>7}{'introduced':>12}"
    )
    print(header)
    print("-" * len(header))
    for row, reasons in verdicts:
        nouns_base = f"{row['nouns_found_baseline']}/{row['nouns_total']}" if row["nouns_total"] else "n/a"
        nouns = f"{row['nouns_found']}/{row['nouns_total']}" if row["nouns_total"] else "n/a"
        print(
            f"{row['audio']:<22}{row['mode']:<11}"
            f"{row['cer_baseline']:>9.4f}{row['cer_cleaned']:>11.4f}{nouns_base:>11}{nouns:>13}"
            f"{row.get('chars_fixed', 0):>7}{row.get('chars_introduced', 0):>12}"
        )
        for reason in reasons:
            print(f"    FAIL: {reason}")

    print("\nPer-mode totals (length-weighted across all samples):")
    for mode in sorted(totals):
        bucket = totals[mode]
        print(
            f"  {mode:<11} samples={int(bucket['samples']):<3} "
            f"CER base={bucket['cer_baseline']:.4f}  CER cleaned={bucket['cer_cleaned']:.4f}"
        )

    if "accurate" in totals and "balanced" in totals:
        delta = totals["balanced"]["cer_cleaned"] - totals["accurate"]["cer_cleaned"]
        verdict = "accurate better" if delta > 0 else "no measured gain"
        print(f"\naccurate vs balanced (whole corpus): CER delta {delta:+.4f} ({verdict})")

    failed = sum(1 for _, reasons in verdicts if reasons)
    print(f"\n{len(verdicts) - failed}/{len(verdicts)} scenario-modes within thresholds")
    return failed


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--corpus", required=True, help="directory containing manifest.json")
    parser.add_argument("--modes", default="balanced,accurate")
    parser.add_argument("--workdir", default=None)
    parser.add_argument("--max-cer", type=float, default=0.15)
    parser.add_argument(
        "--transcriber", default=str(SCRIPT),
        help="transcriber script to evaluate (overridable so the orchestration "
             "can be exercised without real ASR)",
    )
    parser.add_argument(
        "--backend", default=None, choices=["mlx", "faster-whisper"],
        help="ASR backend to evaluate. Without this the transcriber's default "
             "(mlx, Apple Silicon) is used, so a CPU-only machine would silently "
             "evaluate a backend it cannot run.",
    )
    parser.add_argument("--llm-backend", default=None, choices=["local", "claude", "none"])
    parser.add_argument("--llm-model", default=None)
    parser.add_argument(
        "--transcriber-arg", action="append", default=[], metavar="ARG",
        help="Extra argument passed through to the transcriber verbatim. "
             "Repeatable, and the `=` form is REQUIRED for values that start "
             "with a dash, because argparse otherwise reads them as options: "
             "--transcriber-arg=--model-path --transcriber-arg=/path/to/model",
    )
    parser.add_argument(
        "--true-raw", action="store_true",
        help="Score the untouched ASR text as the baseline instead of the "
             "no-LLM cleaned output, via the transcriber's --emit-raw-asr.",
    )
    parser.add_argument(
        "--no-uv", action="store_true",
        help="invoke the transcriber with this interpreter instead of `uv run`. "
             "The transcriber's PEP 723 dependencies are then your responsibility.",
    )
    args = parser.parse_args(argv[1:])

    corpus = Path(args.corpus).expanduser().resolve()
    if not (corpus / "manifest.json").exists():
        print(
            f"setup: no manifest.json under {corpus}.\n"
            "  Nothing was measured; this is not a quality result.\n"
            "  See the module docstring for the expected corpus layout.",
            file=sys.stderr,
        )
        return 2

    transcriber = Path(args.transcriber).expanduser().resolve()
    if not transcriber.exists():
        print(f"setup: transcriber not found: {transcriber}", file=sys.stderr)
        return 2

    use_uv = not args.no_uv and shutil.which("uv") is not None
    if not args.no_uv and not use_uv:
        print(
            "setup: `uv` is not on PATH, so the transcriber's PEP 723 dependency\n"
            "  block cannot be honoured. Install uv, or pass --no-uv and provide\n"
            "  mlx-whisper / faster-whisper yourself.",
            file=sys.stderr,
        )
        return 2

    workdir = Path(args.workdir).resolve() if args.workdir else corpus / "_eval_out"
    workdir.mkdir(parents=True, exist_ok=True)

    passthrough: list[str] = []
    if args.backend:
        passthrough += ["--backend", args.backend]
    if args.llm_backend:
        passthrough += ["--llm-backend", args.llm_backend]
    if args.llm_model:
        passthrough += ["--llm-model", args.llm_model]
    passthrough += args.transcriber_arg

    try:
        rows = evaluate(
            corpus, [m.strip() for m in args.modes.split(",") if m.strip()],
            workdir, transcriber, use_uv, passthrough, args.true_raw,
        )
    except (RuntimeError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"setup: {exc}", file=sys.stderr)
        return 2

    failed = report(judge(rows, args.max_cer), aggregate_by_mode(rows))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

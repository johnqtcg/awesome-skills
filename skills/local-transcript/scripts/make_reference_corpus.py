#!/usr/bin/env python3
"""Build a reference corpus from a committed script using macOS text-to-speech.

The quality evaluator needs audio plus a transcript known to be correct. Real
recordings cannot be committed (size, licensing, privacy) and hand-transcribing
them is the expensive step this works around: synthesising speech from a script
means the reference transcript is exact by construction, and the corpus is
reproducible from a text file anyone can read and extend.

WHAT THIS CORPUS CAN AND CANNOT TELL YOU

It can: prove the pipeline runs end to end on real audio; compare `fast`,
`balanced` and `accurate` on identical input; show whether LLM proofreading
lowers CER and whether it preserves proper nouns; catch a regression between
versions of this skill.

It cannot: predict accuracy on real speech. Synthetic speech has no accent, no
crosstalk, no room noise, no disfluency and perfectly even pacing, so CER here
is a *floor*, not an estimate. A model that scores well here can still do badly
on a meeting recording. Treat the numbers as a controlled comparison between
configurations, never as an accuracy claim.

Requires macOS `say` AND an installed Chinese voice. `say -v '?'` lists voices
that are merely *available for download*: an uninstalled one silently produces
~0.01 s of audio instead of failing, which would build a corpus of silence and
report a meaningless CER. This script measures every clip it creates and refuses
to write a manifest for one that is implausibly short.

Voices verified to synthesise Chinese on a stock macOS install: Tingting
(default here), Sinji, Meijia, Li-mu. Eddy/Flo/Reed/Grandma are listed but ship
undownloaded; install them under System Settings > Accessibility >
Spoken Content > System Voice > Manage Voices.

Usage:
  make_reference_corpus.py --out ./corpus [--voice Eddy] [--script my_lines.json]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

# Short, self-contained lines with proper nouns worth scoring. Deliberately
# includes homophone-prone words, a mixed CJK/Latin term, and digits — the
# places ASR and an over-eager proofreader both tend to fail.
DEFAULT_SCRIPT = [
    {
        "id": "policy",
        "text": "哈里斯在会议上强调，欧盟的贸易政策需要在二零二六年之前完成调整。",
        "proper_nouns": ["哈里斯", "欧盟"],
    },
    {
        "id": "tech",
        "text": "我们把服务迁移到了 Kubernetes 集群，延迟从三百毫秒降到了八十毫秒。",
        "proper_nouns": ["Kubernetes"],
    },
    {
        "id": "homophone",
        "text": "他噤若寒蝉地站在一旁，没有搭便车，也没有提出任何异议。",
        "proper_nouns": [],
    },
]


# Chinese speech runs roughly 4-6 characters a second, so ~0.17 s/char. Require
# a third of that: enough to catch a silent clip, loose enough for any voice.
MIN_SECONDS_PER_CHAR = 0.05


def clip_duration(path: Path) -> float | None:
    """Duration in seconds via `afinfo`, or None when it cannot be determined."""
    if not shutil.which("afinfo"):
        return None
    proc = subprocess.run(["afinfo", str(path)], capture_output=True, text=True)
    for line in proc.stdout.splitlines():
        if "estimated duration" in line:
            try:
                return float(line.split(":")[1].strip().split()[0])
            except (IndexError, ValueError):
                return None
    return None


def check_clip(path: Path, text: str, voice: str) -> None:
    """Fail loudly on a silent clip rather than shipping a corpus of nothing."""
    duration = clip_duration(path)
    if duration is None:
        # No afinfo: fall back to size. Uncompressed AIFF is ~44 kB/s, so even a
        # very fast voice cannot fit a sentence into a few kilobytes.
        if path.stat().st_size < 8_000 + 400 * len(text):
            raise RuntimeError(
                f"voice {voice!r} produced {path.stat().st_size} bytes for "
                f"{len(text)} characters — almost certainly silence"
            )
        return
    minimum = MIN_SECONDS_PER_CHAR * len(text)
    if duration < minimum:
        raise RuntimeError(
            f"voice {voice!r} produced {duration:.3f}s for {len(text)} characters "
            f"(expected at least {minimum:.1f}s).\n"
            "  The voice is listed but not installed — `say` emits near-silence "
            "instead of failing.\n"
            "  Try --voice Tingting (or Sinji / Meijia / Li-mu), or install it via\n"
            "  System Settings > Accessibility > Spoken Content > Manage Voices."
        )


def build(out_dir: Path, voice: str, script: list[dict]) -> Path:
    if not shutil.which("say"):
        raise RuntimeError("macOS `say` not found; this generator is macOS-only")

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for entry in script:
        stem = entry["id"]
        audio = out_dir / f"{stem}.aiff"
        reference = out_dir / f"{stem}.txt"
        proc = subprocess.run(
            ["say", "-v", voice, "-o", str(audio), entry["text"]],
            capture_output=True, text=True,
        )
        if proc.returncode != 0 or not audio.exists():
            raise RuntimeError(
                f"say failed for {stem} with voice {voice!r}: {proc.stderr.strip()}\n"
                "  List Chinese voices with:  say -v '?' | grep zh_CN"
            )
        check_clip(audio, entry["text"], voice)
        reference.write_text(entry["text"], encoding="utf-8")
        manifest.append({
            "audio": audio.name,
            "reference": reference.name,
            "proper_nouns": entry.get("proper_nouns", []),
            "language": entry.get("language", "zh"),
        })

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest_path


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--voice", default="Tingting",
        help="a zh_CN voice that is actually installed. Tingting, Sinji, Meijia "
             "and Li-mu work on a stock macOS; Eddy/Flo/Reed/Grandma are listed "
             "but ship undownloaded and emit silence.",
    )
    parser.add_argument(
        "--script", default=None,
        help="JSON list of {id, text, proper_nouns} to use instead of the built-in lines",
    )
    args = parser.parse_args(argv[1:])

    script = DEFAULT_SCRIPT
    if args.script:
        script = json.loads(Path(args.script).read_text(encoding="utf-8"))

    try:
        manifest = build(Path(args.out).expanduser().resolve(), args.voice, script)
    except (RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"setup: {exc}", file=sys.stderr)
        return 2

    print(f"Wrote {manifest} with {len(script)} samples.")
    print("\nSynthetic speech: CER measured here is a floor, not an accuracy estimate.")
    print("Next:")
    print(f"  python3 {Path(__file__).parent / 'run_quality_eval.py'} \\")
    print(f"      --corpus {manifest.parent} --modes fast,balanced,accurate")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

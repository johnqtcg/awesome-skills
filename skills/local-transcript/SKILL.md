---
name: local-transcript
description: Transcribe a specified local video or audio file into cleaned final `.txt`, `.pdf`, or `.docx` transcripts using speech recognition with Apple Silicon GPU acceleration and LLM-based proofreading. Use when the user wants text extracted from a local media file path such as `.mp4`, `.mov`, `.mkv`, `.webm`, `.mp3`, `.m4a`, or `.wav`, and the output language should follow the spoken language in the media automatically. Prefer this skill for local-file transcription workflows that should produce cleaned transcripts with natural paragraphs, LLM-corrected Chinese text, and simplified Chinese output for Chinese speech.
disable-model-invocation: true
allowed-tools: Read, Write, Bash(whisper*), Bash(mlx_whisper*), Bash(ffmpeg*), Bash(uv run*)
---

# Local Transcript

## Overview

Use this skill to turn a local media file into cleaned final transcript files in `.txt`, `.pdf`, or `.docx` format. Extract audio with `ffmpeg`, transcribe with `mlx-whisper` (Apple Silicon GPU) or `faster-whisper` (CPU fallback), then clean and proofread the transcript using a two-layer correction pipeline — deterministic replacements for known ASR bugs, then LLM-based contextual proofreading for domain-specific and semantic errors.

## Workflow

1. Validate the input path.
2. Confirm the requested output format.
3. Check dependencies.
4. Resolve the ASR mode: `fast`, `balanced`, or `accurate`.
5. Reuse cached audio/raw transcript/clean transcript layers when available.
6. Extract or reuse 16 kHz mono WAV audio.
7. Transcribe with the selected ASR backend (language auto-detected or user-specified via `--language`).
8. Clean the transcript: simplified Chinese → deterministic replacements → LLM proofreading → post-LLM safety replacements.
9. Paragraphize and write the requested final file(s).

## Format Resolution Gate

- If the user explicitly requests `txt`, `pdf`, or `word/docx`, use that format directly.
- If the user requests multiple formats, generate all requested formats from the same cleaned transcript.
- If the user asks to transcribe a file but does not specify an output format, ask a short follow-up question before execution: `Which output format do you want: txt, pdf, or docx?`
- Do not guess the output format from context alone when the user did not say.

## Dependency Gate

Before running, verify:

- `ffmpeg`
- local Python execution for `scripts/local_transcript.py`
**This is an Apple-Silicon-first tool.** Say so rather than presenting the
fallbacks as an equivalent path — they are usable, not seamless.

| Platform | ASR | LLM proofreading | Chinese PDF |
|---|---|---|---|
| Apple Silicon | `mlx-whisper` (GPU/ANE), default | `mlx-lm` + Qwen2.5, default, no API key | macOS system CJK fonts found automatically |
| Intel Mac / Linux / Windows | `--backend faster-whisper` (CPU, markedly slower) | `--llm-backend claude` (needs the `claude` CLI) or `--no-llm-proofread` | **must install a CJK font**; the built-in candidates are macOS paths |

Packages by platform — do not install the whole list on a non-Mac:

- Always: `opencc-python-reimplemented`, `reportlab`, `python-docx`, plus `ffmpeg`
- Apple Silicon: `mlx-whisper`, `mlx-lm`
- Elsewhere: `faster-whisper` (`mlx-*` will not install and are not needed)

On a non-Apple-Silicon machine the defaults do not apply: pass
`--backend faster-whisper` and either `--llm-backend claude` or
`--no-llm-proofread`, or the run fails on a missing `mlx` import.

The script bootstraps ASR models automatically if missing (downloaded from HuggingFace Hub).

Cache writes go through a temp file and an atomic rename, and a cache file that
fails to parse is discarded and treated as a miss — an interrupted run degrades
to a re-run rather than to a corrupt transcript.

## Quality Evaluation

`scripts/run_quality_eval.py` measures CER and proper-noun recall against a
hand-checked corpus, per mode, and separately for the raw ASR text and the
proofread text — so a proofreading pass that lowers CER overall while corrupting
names shows up rather than averaging out.

No corpus ships with the skill: audio cannot be committed, and a reference
transcript means nothing without its audio. Point `--corpus` at your own; without
one the script exits 2 and grades nothing.

Build a reproducible corpus first — the reference transcript is exact by
construction, so no hand-transcription is needed:

```bash
python3 scripts/make_reference_corpus.py --out ./corpus          # macOS `say`
python3 scripts/run_quality_eval.py --corpus ./corpus --modes fast,balanced,accurate
```

Synthetic speech has no accent, noise or disfluency, so its CER is a **floor,
not an accuracy estimate**. Use it to compare configurations and catch
regressions, not to claim a real-world number. For that, point `--corpus` at
real recordings with hand-checked references.

The evaluator compares **baseline vs proofread**, where the baseline is
`--no-llm-proofread` — the pipeline minus the LLM, not raw ASR (OpenCC,
replacements, punctuation and re-segmentation still run). Use the transcriber's
`--emit-raw-asr` if you need the untouched ASR text.

Run it with `uv run` so the transcriber's PEP 723 dependencies are honoured
(the evaluator does this by default and refuses to proceed without `uv` unless
you pass `--no-uv` and provide the packages yourself):

```bash
python3 scripts/run_quality_eval.py --corpus /path/to/corpus --modes balanced,accurate
```

Both cache and model roots honour `LOCAL_TRANSCRIPT_CACHE` and
`LOCAL_TRANSCRIPT_MODELS`; the defaults under `/tmp` are unchanged. Set them
where `/tmp` is not writable.

**Not yet measured**: the regression suite proves the wiring (that `accurate`
really requests beam search, that each configuration gets its own cache key, that
a hallucinating chunk is rejected). It does not prove that `accurate` yields a
lower CER than `balanced` on real audio, or that proofreading removes more errors
than it introduces. Those need the eval above, run on a real corpus. Running it needs a machine that
this repository's development sandbox does not provide: MLX requires a Metal
device (absent in a headless session) and any backend must reach
`huggingface.co` to fetch its model. The harness reports both as `setup:`
failures and exits 2 rather than emitting a number, so an environment that
cannot measure never looks like an environment that measured well.

If a dependency is missing, stop and say which dependency is unavailable.

## Known Risks and Their Switches

| Behaviour | Default | Why |
|---|---|---|
| Chinese proper-noun unification (`--unify-names`) | **off** | A character-frequency heuristic with no lexicon. Any legitimate low-frequency word one character away from a frequent one is rewritten — with 11 `苹果汁` and one `苹果醋`, the cider becomes juice. Enable only when the audio is name-dense and you will read the run log, which prints every substitution. |
| LLM proofreading of English (`--llm-proofread-en`) | off | ASR is already strong on English; proofreading risks more than it fixes. |
| LLM backend unavailable | **hard failure** | A missing `claude` CLI used to return the text unchanged, report `LLM proofreading: claude`, and cache that un-proofread result. Now it stops and names the fix. Use `--no-llm-proofread` to skip proofreading deliberately. |

## Default Behavior

- Input: one local media file path
- Default output format for direct script usage: `txt`
- Default output file: same directory as the media file, named `<stem>-transcript.<ext>`
- Default ASR backend: `mlx` (Apple Silicon GPU acceleration via mlx-whisper)
- Default and recommended ASR mode: `balanced`
- Mode presets:
  - `fast`: mlx-whisper with `whisper-small`, no LLM proofreading override needed
  - `balanced`: mlx-whisper with `whisper-large-v3-turbo` + LLM proofreading (recommended)
  - `accurate`: mlx-whisper with `whisper-large-v3-turbo`, decoded with `beam_size=5` (same model as `balanced`; the difference is the search, not the weights) + LLM proofreading
- Fallback backend: `--backend faster-whisper` for non-Apple-Silicon machines (CPU-only, slower)
- Default cache behavior: reuse three cache layers for the same unchanged media file
  - extracted WAV audio (validated by RIFF/WAVE header, not merely non-empty)
  - raw ASR transcript
  - cleaned final transcript (separate caches for LLM-proofread and non-proofread)
- LLM proofreading: enabled by default for Chinese transcripts
  - Default backend: `local` — uses `mlx-lm` on Apple Silicon GPU. No API key, no network, no cost.
    - `balanced`/`accurate` mode: `Qwen2.5-7B-Instruct-4bit` (higher quality)
    - `fast` mode: `Qwen2.5-3B-Instruct-4bit` (faster, ~50% less proofreading time)
  - Alternative backend: `claude` — uses `claude -p` CLI (requires API access)
  - Splits text into ~2500-char chunks with 400-char context overlap from the previous chunk
  - Short tail chunks (<500 chars) are automatically merged into the previous chunk to avoid validation failures
  - Video/audio title is passed to the LLM as domain context for better proper-noun correction
  - Output validation: rejects LLM responses that are too short/long or contain meta-commentary
  - Retry: failed/invalid chunks are retried up to 2 times before falling back to the original text
  - Can be disabled with `--no-llm-proofread` or `--llm-backend none`
  - For English transcripts, LLM proofreading is off by default; enable with `--llm-proofread-en` for complex content with non-English proper nouns
  - Custom model: `--llm-model <hf-repo>` to use a different MLX model
- Language: auto-detected from speech, or user-specified via `--language zh` / `--language en`
- Three-layer Chinese correction pipeline:
  1. Deterministic replacements: a curated table of universal Whisper ASR bugs (not video-specific). Supports extra replacements via `--replacements-file <path.json>`.
  2. LLM contextual proofreading: handles domain-specific terms, proper nouns, idioms, and homophones
  3. Post-LLM safety pass: deterministic replacements applied again to catch any regressions
  4. Proper noun unification (**only with `--unify-names`; off by default**): detects near-duplicate CJK names (e.g. 哈萨迪/哈塔尼→哈萨尼) and unifies low-frequency variants to the dominant form. See §Known Risks — it can rewrite a legitimate word.
- Final deliverable: cleaned transcript in the user-requested format(s) only
- PDF output: use a Chinese-capable font when the inferred transcript language is Chinese
- PDF and DOCX output: emit transcript body only, without prepending headers

## Execution

Run (default: mlx backend, balanced mode, LLM proofreading enabled):

```bash
uv run /absolute/path/to/skills/local-transcript/scripts/local_transcript.py "/absolute/path/to/video.mp4"
```

Request PDF output:

```bash
uv run /absolute/path/to/skills/local-transcript/scripts/local_transcript.py "/absolute/path/to/video.mp4" --format pdf
```

Prioritize speed (smaller model, still fast on Apple Silicon):

```bash
uv run /absolute/path/to/skills/local-transcript/scripts/local_transcript.py "/absolute/path/to/video.mp4" --mode fast
```

Disable LLM proofreading (ASR-only output):

```bash
uv run /absolute/path/to/skills/local-transcript/scripts/local_transcript.py "/absolute/path/to/video.mp4" --llm-backend none
```

Use claude CLI for proofreading (requires API access):

```bash
uv run /absolute/path/to/skills/local-transcript/scripts/local_transcript.py "/absolute/path/to/video.mp4" --llm-backend claude
```

Use a different local LLM model:

```bash
uv run /absolute/path/to/skills/local-transcript/scripts/local_transcript.py "/absolute/path/to/video.mp4" --llm-model mlx-community/Qwen2.5-14B-Instruct-4bit
```

Specify language explicitly (skip auto-detection):

```bash
uv run /absolute/path/to/skills/local-transcript/scripts/local_transcript.py "/absolute/path/to/video.mp4" --language zh
```

Enable LLM proofreading for English transcripts (off by default):

```bash
uv run /absolute/path/to/skills/local-transcript/scripts/local_transcript.py "/absolute/path/to/english-video.mp4" --llm-proofread-en
```

Use CPU fallback backend:

```bash
uv run /absolute/path/to/skills/local-transcript/scripts/local_transcript.py "/absolute/path/to/video.mp4" --backend faster-whisper
```

Force a fresh transcription and ignore cache:

```bash
uv run /absolute/path/to/skills/local-transcript/scripts/local_transcript.py "/absolute/path/to/video.mp4" --format pdf --force-transcribe
```

Load extra replacements from a JSON file:

```bash
uv run /absolute/path/to/skills/local-transcript/scripts/local_transcript.py "/absolute/path/to/video.mp4" --replacements-file custom_fixes.json
```

Request multiple formats:

```bash
uv run /absolute/path/to/skills/local-transcript/scripts/local_transcript.py "/absolute/path/to/video.mp4" --format txt --format pdf --format docx
```

## Cleaning Rules

- Remove timestamps if present.
- Collapse caption-style short lines into natural paragraphs.
- For Chinese:
  1. Convert traditional to simplified Chinese.
  2. Apply deterministic replacements for universal Whisper ASR bugs (curated, cross-video).
  3. Run LLM-based contextual proofreading with video title as domain context.
  4. Apply deterministic replacements again as a post-LLM safety net.
  5. Normalize Chinese punctuation.
- The deterministic replacement table contains only universal, cross-video Whisper errors (also available as `scripts/zh_replacements.json`). Video-specific corrections (proper nouns, domain terms) are handled by the LLM layer and proper noun unification pass.
- Users can supply additional replacements via `--replacements-file` for domain-specific corrections.
- Preserve English output as English.
- Strip trailing ASR garbage: repetitive patterns (e.g. "www www www...") from video credits or silence are auto-removed.
- Do not invent missing content.

## Output Contract

For every run, report:

1. Input file
2. Detected or inferred transcript language
3. ASR backend used (mlx or faster-whisper)
4. ASR mode used
5. Model used
6. LLM proofreading status (enabled/disabled)
7. Requested output format(s)
8. Cache status for audio/raw transcript/clean transcript
9. Final output path(s)
10. Total processing time
11. Whether the transcript was cleaned successfully

If execution fails, report the exact failed step and stop.

## Script

Use `scripts/local_transcript.py` for the workflow. Prefer the script over retyping the pipeline manually.

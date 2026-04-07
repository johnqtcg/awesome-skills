---
name: local-transcript
description: Transcribe a specified local video or audio file into cleaned final `.txt`, `.pdf`, or `.docx` transcripts using speech recognition with Apple Silicon GPU acceleration and LLM-based proofreading. Use when the user wants text extracted from a local media file path such as `.mp4`, `.mov`, `.mkv`, `.webm`, `.mp3`, `.m4a`, or `.wav`, and the output language should follow the spoken language in the media automatically. Prefer this skill for local-file transcription workflows that should produce cleaned transcripts with natural paragraphs, LLM-corrected Chinese text, and simplified Chinese output for Chinese speech.
disable-model-invocation: true
allowed-tools: Read, Write, Bash(whisper*), Bash(mlx_whisper*), Bash(ffmpeg*)
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
- Python packages required by the script: `mlx-whisper`, `mlx-lm`, `faster-whisper`, `opencc-python-reimplemented`, `reportlab`, `python-docx`
- LLM proofreading: default `local` backend uses `mlx-lm` + Qwen2.5 on Apple Silicon (no API key needed). Optional `claude` backend requires `claude` CLI with API access.
- For Chinese PDF output, the environment must provide at least one supported CJK font. On macOS the script prefers built-in fonts such as `STHeiti`.

The script bootstraps ASR models automatically if missing (downloaded from HuggingFace Hub).

If a dependency is missing, stop and say which dependency is unavailable.

## Default Behavior

- Input: one local media file path
- Default output format for direct script usage: `txt`
- Default output file: same directory as the media file, named `<stem>-transcript.<ext>`
- Default ASR backend: `mlx` (Apple Silicon GPU acceleration via mlx-whisper)
- Default and recommended ASR mode: `balanced`
- Mode presets:
  - `fast`: mlx-whisper with `whisper-small`, no LLM proofreading override needed
  - `balanced`: mlx-whisper with `whisper-large-v3-turbo` + LLM proofreading (recommended)
  - `accurate`: mlx-whisper with `whisper-large-v3-turbo` + higher beam size + LLM proofreading
- Fallback backend: `--backend faster-whisper` for non-Apple-Silicon machines (CPU-only, slower)
- Default cache behavior: reuse three cache layers for the same unchanged media file
  - extracted WAV audio
  - raw ASR transcript
  - cleaned final transcript (separate caches for LLM-proofread and non-proofread)
- LLM proofreading: enabled by default for Chinese transcripts
  - Default backend: `local` — uses `mlx-lm` on Apple Silicon GPU. No API key, no network, no cost.
    - `balanced`/`accurate` mode: `Qwen2.5-7B-Instruct-4bit` (higher quality)
    - `fast` mode: `Qwen2.5-3B-Instruct-4bit` (faster, ~50% less proofreading time)
  - Alternative backend: `claude` — uses `claude -p` CLI (requires API access)
  - Splits text into ~1500-char chunks with 400-char context overlap from the previous chunk
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
  4. Proper noun unification: automatically detects near-duplicate CJK names (e.g. 哈萨迪/哈塔尼→哈萨尼) and unifies low-frequency variants to the dominant form
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
